#!/usr/bin/env python3
"""USB MIDI TRACKS under the ColdFire port: an audio-track START becomes a
CC 16..21 and a note-on on EP2 IN, and a note-off a gate later.

It boots out/mainos_bus.bin under
--interactive with the USB device model, enumerates, sets T1's MIDI trig
channel (0x8000003f) to channel 1 and sends a chromatic note-on over USB (a
START of T1 through the same funnel as a sequencer trig), then lets the port
run and prints every USB-MIDI packet the device sends. It passes when CC 16..21
and a note-on arrive on channel 1 in that order, then a note-off for
the same note.

Without a project there may be no sample on T1: the module sends nothing for
a START whose voice has no sample record, and the port may not START at all.
A FAIL here with no packets at all is that, not necessarily a fault; the
printed packets are the finding either way.

With OT_PROJECT (OT_BANK, default 1) it also runs that project with RTRG locked on T1
through probe_usbmidi_tracks_project.py and checks the repeats reach USB: at
least one, every queued note on the wire, nothing dropped. That part needs a
project, so CI has no retrig coverage; moved fader cases are the probe's --fader.

SKIPs when the remix has no USB MIDI TRACKS or the port is not built
(`make emu-cf`).
"""
import os
import pathlib
import re
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
MIDI_TRIG_CH1 = 0x8000003f      # audio track 1's MIDI channel (0..15, -1 = off)
CC_FIRST = 16
NOTE_ON_KEY = 84                # chromatic range 72..96: a START of the track with a PTCH lock
RUN_MS = 400


ELF = ROOT / "out/platform/runtime/runtime.elf"


def symbol(name):
    """An address from the linked runtime's symbol table (needs m68k-elf-nm on PATH)."""
    nm = shutil.which("m68k-elf-nm") or shutil.which("m68k-linux-gnu-nm")
    if nm is None or not ELF.is_file():
        return None
    for line in subprocess.run([nm, str(ELF)], capture_output=True, text=True).stdout.splitlines():
        f = line.split()
        if len(f) == 3 and f[2] == name:
            return int(f[0], 16)
    return None


def main():
    if not EMU.is_file():
        print("  [SKIP] verify_usbmidi_tracks: the port is not built (make emu-cf)")
        return 0
    if not IMAGE.is_file():
        print("  [FAIL] verify_usbmidi_tracks: no out/mainos_bus.bin (make bus)")
        return 1
    if "USB MIDI TRACKS" not in registry.remix(os.environ.get("REMIX")).modules:
        print("  [SKIP] verify_usbmidi_tracks: the remix has no USB MIDI TRACKS")
        return 0
    sock = f"/tmp/ot-usbtrk-{os.getpid()}.sock"
    emu = subprocess.Popen([str(EMU), "--image", str(IMAGE), "--interactive", "--frame", "--usb-host", sock, "--main-level", "off"],
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
        return cmd(f"run {ms}")

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
        cmd(f"poke {MIDI_TRIG_CH1:#x} 00")
        # one chromatic note-on, channel 1, over USB: a START of T1. As the clock
        # gate does it: the request is in the socket, the port takes it at the
        # run's first poll, and only then is the reply read.
        b.sock.sendall(f"out 2 {bytes([0x09, 0x90, NOTE_ON_KEY, 0x64]).hex()}\n".encode())
        run(50)
        taken = int(b.wait("out 2", timeout=10).split()[2])
        check("the note-on was taken whole by EP2 OUT", taken == 4, f"{taken} of 4 bytes")
        # then listen on EP2 IN while the port runs: midi_recv waits in wall
        # time, the port's own time only advances on `run`
        packets = []

        def reader():
            try:
                packets.extend(usb_host.midi_recv(b, 4.0))
            except Exception as e:  # noqa: BLE001
                print(f"  reader: {type(e).__name__}: {e}")
        th = threading.Thread(target=reader)
        th.start()
        while th.is_alive():
            run(20)
            th.join(0.01)
        dbg = symbol("utm_dbg")
        if dbg is None:
            print("  (no utm_dbg symbol: m68k-elf-nm or out/platform/runtime/runtime.elf missing)")
        else:
            w = [int(cmd(f"peek {dbg + 4 * i:#x} 4")[1], 16) for i in range(4)]
            print(f"  utm_dbg @ {dbg:#x}: renderer second calls {w[0]}, STARTs {w[1]}, "
                  f"last sample record {w[2]:#x}, notes queued {w[3]}")
        msgs = [(p[1], p[2], p[3]) for p in packets if len(p) == 4]
        print(f"  packets from the device: {[p.hex() for p in packets]}")
        check("some USB MIDI came out", bool(msgs))
        cc = [m for m in msgs if m[0] == 0xB0]
        on = [m for m in msgs if m[0] == 0x90]
        off = [m for m in msgs if m[0] == 0x80]
        check("CC 16..21 (PLAYBACK page 1) on channel 1", {m[1] for m in cc} == set(range(CC_FIRST, CC_FIRST + 6)), str(sorted({m[1] for m in cc})))
        check("a note-on on channel 1, velocity 100", any(m[2] == 100 for m in on), str(on))
        check("a note-off for the same note", bool(on) and any(m[1] == on[0][1] for m in off), str(off))
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
    project = os.environ.get("OT_PROJECT")
    if project:
        r = subprocess.run([sys.executable, str(ROOT / "tools/verify/probe_usbmidi_tracks_project.py"), "--project", project,
                            "--bank", os.environ.get("OT_BANK", "1"), "--gen-wav", "--rt", "3,16", "--ticks", "200"],
                           cwd=ROOT, capture_output=True, text=True)
        o = r.stdout
        m = re.search(r"notes queued (\d+), repeats (\d+)", o)
        d = re.search(r"usbmidi_tx_drops (\d+)", o)
        ons = sum(int(x) for x in re.findall(r"\): (\d+) note-on", o))
        offs = sum(int(x) for x in re.findall(r"(\d+) note-off", o))
        check("the project probe ran", r.returncode == 0 and bool(m), r.stderr[-200:])
        if m:
            check("RTRG on T1 reaches USB as repeats", int(m[2]) > 0, f"repeats {m[2]}")
            check("every queued note is on the wire", ons == int(m[1]), f"{ons} note-on, {m[1]} queued")
            check("every note closes (those inside the last gate excepted)", 0 <= ons - offs <= 8, f"{ons} on, {offs} off")
            check("nothing dropped", bool(d) and int(d[1]) == 0, d[0] if d else "no symbol")
    print(f"verify_usbmidi_tracks: {'OK' if not fails else str(len(fails)) + ' FAILED'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
