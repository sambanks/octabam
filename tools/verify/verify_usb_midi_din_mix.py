#!/usr/bin/env python3
"""USB-MIDI and DIN MIDI together under the ColdFire port: a USB message leaves
DIN's running status and half-received message as they were (#1248).
Both inputs reach one FIFO and one framer (0x40092bf4), whose running status
(0x46100b70) and "second data byte pending" flag (0x46100b74) were shared: a USB
program change between DIN's running-status bytes made every later DIN data
byte a program change, each a pattern change.
Boots out/mainos_bus.bin with the USB device model under --interactive (time
advances only on `run`), enumerates at high speed, then sends DIN bytes one at
a time with USB messages between them, and reads back the framer's completed
messages (the buffer at 0x46100b84, write index 0x46100b5c):
  rs       DIN 90 3c 64, then running-status pairs 3d 64, 3e 64, 3f 64 with a
           USB program change C0 05 between the first two pairs
  mid      DIN 90 40 64, then 41 | USB C0 06 | 64: the USB message lands
           between a DIN message's two data bytes
  cc3      the same with a three-byte USB message (B1 07 40) between pairs
  sysex    DIN F0 01 02 F7 (no running status after it), a USB C0 07, then a
           stray DIN data byte 10: dropped as DIN's own, not a program change
SKIPs when the remix has no USB or the port is not built (`make emu-cf`).
What this cannot see: the UART's timing on a unit (here each DIN byte is
handed over between USB transfers, never during one), and a DIN byte
arriving inside the masked span on the unit (the UART holds it).
"""
import os
import pathlib
import subprocess
import sys
import threading

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
import usb_host  # noqa: E402  (tools/harness)
from remix import registry  # noqa: E402

EMU = ROOT / "out/emu/ot_emu"
IMAGE = ROOT / "out/mainos_bus.bin"
RS_STATUS = 0x46100b70
MSG_BUF, MSG_WIDX = 0x46100b84, 0x46100b5c


def main():
    if not EMU.is_file():
        print("  [SKIP] verify_usb_midi_din_mix: the port is not built (make emu-cf)")
        return 0
    if not IMAGE.is_file():
        print("  [FAIL] verify_usb_midi_din_mix: no out/mainos_bus.bin (make bus)")
        return 1
    if "USB" not in registry.remix(os.environ.get("REMIX") or (sys.argv[1] if len(sys.argv) > 1 else None)).modules:
        print("  [SKIP] verify_usb_midi_din_mix: the remix has no USB")
        return 0
    sock = f"/tmp/ot-usbmix-{os.getpid()}.sock"     # sun_path is 104 bytes on macOS
    emu = subprocess.Popen([str(EMU), "--image", str(IMAGE), "--interactive", "--usb-host", sock, "--main-level", "off"],
                           cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           text=True, bufsize=1)
    fails = []

    def check(what, ok, detail=""):
        print(f"  [{'PASS' if ok else 'FAIL'}] {what}{'  ' + detail if detail else ''}")
        if not ok:
            fails.append(what)

    def reply():
        while True:
            line = emu.stdout.readline()
            if not line:
                raise RuntimeError("the port exited")
            if line.startswith(("ready", "ok", "err", "peek", "status")):
                return line.split()

    def cmd(c):
        emu.stdin.write(c + "\n")
        emu.stdin.flush()
        r = reply()
        if r[0] == "err":
            raise RuntimeError(f"{c}: {' '.join(r)}")
        return r

    def run(ms):
        cmd(f"run {ms}")

    def peek(addr, n=4):
        return int(cmd(f"peek {addr:#x} {n}")[1], 16)

    def din(*bs):
        for x in bs:
            cmd(f"midi {x:02x}")
            run(1)

    def usb(b, *msg):
        pkt = bytes([msg[0] >> 4, *msg]) + bytes(3 - len(msg))
        b.sock.sendall(f"out 2 {pkt.hex()}\n".encode())
        # The port takes the request only if it is in the socket when a run polls (every 256
        # instructions): run in 1 ms steps until the bench has the reply, or a run can end first.
        line = None
        for _ in range(200):
            run(1)
            try:
                line = b.wait("out 2", timeout=0.05)
                break
            except TimeoutError:
                continue
        if line is None:
            raise RuntimeError("EP2 OUT never took the transfer in 200 ms of port time")
        taken = int(line.split()[2])
        if taken != 4:
            raise RuntimeError(f"EP2 OUT took {taken} of 4 bytes")

    def parsed(fn):
        """The framer's messages while fn runs (the buffer does not wrap in a run this short)."""
        w0 = peek(MSG_WIDX)
        fn()
        run(50)
        w1 = peek(MSG_WIDX)
        if w1 <= w0:
            return b""
        return bytes.fromhex(cmd(f"peek {MSG_BUF + w0:#x} {w1 - w0}")[1].rjust(2 * (w1 - w0), "0"))

    b = None
    try:
        reply()
        run(3000)
        res = {}

        def bench():
            res["b"] = usb_host.Bench(sock, timeout=60.0)
            usb_host.enumerate_device(res["b"], hs=True)
        th = threading.Thread(target=bench)
        th.start()
        while th.is_alive():
            run(50)
            th.join(0.01)
        b = res["b"]
        run(200)

        got = parsed(lambda: (din(0x90, 0x3c, 0x64, 0x3d, 0x64), usb(b, 0xc0, 0x05), din(0x3e, 0x64, 0x3f, 0x64)))
        want = bytes.fromhex("903c64 903d64 c005 903e64 903f64")
        check("rs: a USB program change between DIN's running-status pairs leaves them note-ons",
              got == want, got.hex(" "))

        got = parsed(lambda: (din(0x90, 0x40, 0x64, 0x41), usb(b, 0xc0, 0x06), din(0x64)))
        want = bytes.fromhex("904064 c006 904164")
        check("mid: a USB program change between a DIN message's two data bytes leaves it whole",
              got == want, got.hex(" "))

        got = parsed(lambda: (din(0x90, 0x42, 0x64), usb(b, 0xb1, 0x07, 0x40), din(0x43, 0x64)))
        want = bytes.fromhex("904264 b10740 904364")
        check("cc3: a three-byte USB message between DIN pairs leaves DIN's running status",
              got == want, got.hex(" "))

        got = parsed(lambda: (din(0xf0, 0x01, 0x02, 0xf7), usb(b, 0xc0, 0x07), din(0x10)))
        check("sysex: after a DIN SysEx, a USB program change does not make a stray DIN byte one",
              b"\xc0\x07" in got and b"\xc0\x10" not in got, f"{got.hex(' ')}, running status {peek(RS_STATUS):#x}")
    except Exception as e:  # noqa: BLE001 -- a hang or a stall is the finding
        check(f"the probe completed ({type(e).__name__}: {e})", False)
    finally:
        if b is not None:
            b.sock.close()
        try:
            cmd("quit")
            emu.wait(timeout=30)
        except Exception:  # noqa: BLE001
            emu.kill()
    if fails:
        print(f"  [FAIL] verify_usb_midi_din_mix: {len(fails)} check(s) failed")
        return 1
    print("  [PASS] verify_usb_midi_din_mix")
    return 0


if __name__ == "__main__":
    sys.exit(main())
