#!/usr/bin/env python3
"""USB MIDI pauses while DISK MODE gives the host the card (#1256), under the ColdFire port.

Stock's dormant USB-MIDI encoder writes its packets to 0x4ecc8000 and its EP2
OUT dTD receives into 0x4ecc9000; both sit 64 and 68 KB into the mass-storage
read buffer (0x4ecb8000). A packet encoded during a long READ tore the card's
bytes on the host. modules/usb/usbmidi.s gates on stock's medium word
0x460bb422, which 0x4001eb44 sets for DISK MODE.

Boots out/mainos_bus.bin under --interactive with the USB device model,
enumerates at high speed, and calls the firmware's own routines: the
priority byte sender (0x400108b0) with a clock byte, and the medium setter
(0x4001eb44) with 1 and 0, as DISK MODE's entry and exit call it.
Checked, with a sentinel word planted at 0x4ecc8000 before each step:

- before DISK MODE a clock byte is encoded there (0f f8 00 00);
- after entry neither EP2 direction is primed (ENDPTSTAT), clock bytes leave
  the sentinel alone and count in usbmidi_tx_disk;
- a re-enumeration (SET_CONFIGURATION) inside DISK MODE leaves EP2 OUT
  unprimed;
- after exit EP2 OUT is primed again and the next clock byte is encoded.

What this cannot see: the race itself. The port moves a transfer's bytes when
the dTD is walked, with no DMA timing, so a READ here is never torn with or
without the fix; the gate proves that nothing is written into the read
buffer, which is what the tear needs. SKIPs when the remix has no USB or the
port is not built (`make emu-cf`).
"""
import os
import pathlib
import shutil
import subprocess
import sys
import threading

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
import usb_host  # noqa: E402  (tools/harness)

from remix import registry  # noqa: E402

EMU = ROOT / "out/emu/ot_emu"
IMAGE = ROOT / "out/mainos_bus.bin"
ELF = ROOT / "out/platform/runtime/runtime.elf"
PRIO_SEND = 0x400108B0          # the priority (realtime) byte sender, byte as a long argument
SET_MEDIUM = 0x4001EB44         # DISK MODE's medium setter: 1 on entry (0x4007ebe4), 0 on exit (0x4007ebfe)
MEDIUM = 0x460BB422
TX_BUF = 0x4ECC8000             # the encoder's packet buffer (0x4001d21a)
ENDPTSTAT = 0xFC0B01B8
EP2_OUT, EP2_IN = 1 << 2, 1 << 18
SENTINEL = 0xA5C3E1F7
CLOCK = 0x0FF80000              # cable 0, CIN 0xF, 0xF8
TICKS = 8


def symbols():
    nm = shutil.which("m68k-elf-nm") or shutil.which("m68k-linux-gnu-nm")
    if not nm:
        return None
    out = subprocess.run([nm, str(ELF)], capture_output=True, text=True).stdout
    return {p[2]: int(p[0], 16) for p in (l.split() for l in out.splitlines()) if len(p) == 3}


def main():
    if not EMU.is_file():
        print("  [SKIP] verify_usb_midi_disk: the port is not built (make emu-cf)")
        return 0
    if not IMAGE.is_file():
        print("  [FAIL] verify_usb_midi_disk: no out/mainos_bus.bin (make bus)")
        return 1
    if "USB" not in registry.remix(os.environ.get("REMIX")).modules:
        print("  [SKIP] verify_usb_midi_disk: the remix has no USB")
        return 0
    sym = symbols()
    if not sym or "usbmidi_tx_disk" not in sym:
        print(f"  [FAIL] verify_usb_midi_disk: no usbmidi_tx_disk in {ELF.relative_to(ROOT)} (m68k-elf-nm on PATH?)")
        return 1
    held = sym["usbmidi_tx_disk"]
    sock = f"/tmp/ot-usbdisk-{os.getpid()}.sock"     # sun_path is 104 bytes on macOS
    emu = subprocess.Popen([str(EMU), "--image", str(IMAGE), "--interactive", "--usb-host", sock, "--main-level", "off"],
                           cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
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

    def plant():
        cmd(f"poke {TX_BUF:#x} {SENTINEL:08x}")

    def clock():
        cmd(f"call {PRIO_SEND:#x} 0xf8")
        run(5)

    def enumerate_now():
        res = {}

        def bench():
            res["b"] = usb_host.Bench(sock, timeout=60.0)
            usb_host.enumerate_device(res["b"], hs=True)
        th = threading.Thread(target=bench)
        th.start()
        while th.is_alive():
            run(50)
            th.join(0.01)
        if "b" not in res:
            raise RuntimeError("enumeration did not finish")
        return res["b"]

    def drain(bench):
        """The host reads the waiting EP2 IN transfer, so the transfer slot is free again."""
        res = {}

        def read():
            res["data"] = bench.ep_in(2, 512, timeout=30)
        th = threading.Thread(target=read)
        th.start()
        while th.is_alive():
            run(5)
            th.join(0.01)
        return res.get("data", b"")

    b = b2 = None
    try:
        reply()
        run(3000)
        b = enumerate_now()
        run(50)
        check("after SET_CONFIGURATION EP2 OUT is primed", bool(peek(ENDPTSTAT) & EP2_OUT), f"ENDPTSTAT {peek(ENDPTSTAT):#010x}")

        plant()
        clock()
        word = peek(TX_BUF)
        check(f"outside DISK MODE a clock byte is encoded at {TX_BUF:#x}: {word:#010x}", word == CLOCK)
        got = drain(b)
        check(f"... and the host reads it on EP2 IN: {got.hex()}", got == CLOCK.to_bytes(4, "big"))

        cmd(f"call {SET_MEDIUM:#x} 1")
        run(20)
        check(f"DISK MODE entry: the medium word reads {peek(MEDIUM):#x}", peek(MEDIUM) == 1)
        stat = peek(ENDPTSTAT)
        check(f"DISK MODE entry: neither EP2 direction is primed (ENDPTSTAT {stat:#010x})", not stat & (EP2_OUT | EP2_IN))
        plant()
        n0 = peek(held)
        for _ in range(TICKS):
            clock()
        word = peek(TX_BUF)
        check(f"in DISK MODE {TICKS} clock bytes leave the read buffer alone: {word:#010x}", word == SENTINEL)
        n = peek(held) - n0
        check(f"in DISK MODE the clock bytes are counted in usbmidi_tx_disk: +{n}, want +{TICKS}", n == TICKS)

        b.sock.close()
        b = None
        b2 = enumerate_now()           # a replug or host re-enumeration while the card is the host's
        run(50)
        stat = peek(ENDPTSTAT)
        check(f"SET_CONFIGURATION inside DISK MODE leaves EP2 OUT unprimed (ENDPTSTAT {stat:#010x})", not stat & EP2_OUT)
        plant()
        clock()
        word = peek(TX_BUF)
        check(f"... and a clock byte after it is still not encoded: {word:#010x}", word == SENTINEL)

        cmd(f"call {SET_MEDIUM:#x} 0")
        run(20)
        stat = peek(ENDPTSTAT)
        check(f"DISK MODE exit: EP2 OUT is primed again (ENDPTSTAT {stat:#010x})", bool(stat & EP2_OUT))
        plant()
        clock()
        word = peek(TX_BUF)
        check(f"after DISK MODE a clock byte is encoded again: {word:#010x}", word == CLOCK)
    except Exception as e:  # noqa: BLE001 -- a hang or a stall is the finding
        check(f"the probe completed ({type(e).__name__}: {e})", False)
    finally:
        for x in (b, b2):
            if x is not None:
                x.sock.close()
        try:
            cmd("quit")
            emu.wait(timeout=30)
        except Exception:  # noqa: BLE001
            emu.kill()
    print(f"verify_usb_midi_disk: {'OK' if not fails else str(len(fails)) + ' FAILED'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
