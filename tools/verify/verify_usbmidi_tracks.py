#!/usr/bin/env python3
"""USB MIDI TRACKS under the ColdFire port: an audio-track START becomes a
CC 16..21 and a note-on on EP2 IN, and a note-off a gate later.

It boots out/mainos_bus.bin under
--interactive with the USB device model, enumerates, sets T1's MIDI trig
channel (0x8000003f) to channel 13, not the track's number nor any track's
default, and sends a chromatic note-on on channel 13 over USB (a START of T1 through the same funnel
as a sequencer trig), then lets the port run in 2 ms steps and stamps every
USB-MIDI packet the device sends with the port time it arrived in. It passes
when, on channel 13 and nothing on any other channel, CC 16..21 arrive in that
order, then the note-on, then a note-off for the same note, with the note-off
GATE_MS (160 frames of 16 samples at 44.1 kHz) after the note-on, within
GATE_TOL_MS. Then a second START, and 12 ms into its gate T1's renderer
pointer is moved off utm_render (as a machine or part change does) and T2's
onto it: the note must close at once, from T2's next frame, not a gate later.
The test remix pins SEND to NOTES+CC.

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
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
import usb_host  # noqa: E402  (tools/harness)

from remix import registry  # noqa: E402

EMU = ROOT / "out/emu/ot_emu"
IMAGE = ROOT / "out/mainos_bus.bin"
MIDI_TRIG_CH1 = 0x8000003f      # audio track 1's MIDI channel (0..15, -1 = off)
CC_FIRST = 16
CHANNEL = 12                    # MIDI channel 13: not track 1's number, and no track's default (1..8), so
                                # one START, and the TRIG CHANNEL is what is read
GATE_MS = 160 * 16 / 44.1       # utm.s GATE_FRAMES frames: 58.0 ms
GATE_TOL_MS = 12                # the 2 ms run step, the deferred kick, and the reader thread's lag: a packet is
                                # stamped when the reader gets it (50 and 52 ms read on this build, 16 Nov 2026)
NOTE_ON_KEY = 84                # chromatic range 72..96: a START of the track with a PTCH lock
RUN_MS = 400
RENDER_PTRS = 0x400d61f0        # the packer's per-track renderer pointers (stock, lea at 0x4000bff6)
SWAP_MS = 12                    # phase 2: T1 leaves utm_render this far into its gate


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
        cmd(f"poke {MIDI_TRIG_CH1:#x} {CHANNEL:02x}")
        def start_t1():
            """One chromatic note-on on T1's trig channel, over USB: a START of T1. As
            the clock gate does it: the request is in the socket, the port takes it
            at the run's first poll, and only then is the reply read."""
            b.sock.sendall(f"out 2 {bytes([0x09, 0x90 | CHANNEL, NOTE_ON_KEY, 0x64]).hex()}\n".encode())
            run(2)                      # the port takes it here; the clock below starts at this run's end
            return int(b.wait("out 2", timeout=10).split()[2])

        def listen(at=None):
            """EP2 IN while the port runs in 2 ms steps: the reader waits in wall
            time, the port's own time only advances on `run`. Each packet is
            stamped with the port time of the run in progress when it arrived;
            at = {port ms: action} runs between steps."""
            packets, clock = [], {"ms": 2}

            def reader():
                end = time.time() + 4.0
                try:
                    while time.time() < end:
                        try:
                            data = b.ep_in(2, 512, timeout=max(0.1, end - time.time()))   # a whole HS packet
                        except TimeoutError:
                            break
                        for i in range(0, len(data) - 3, 4):
                            packets.append((clock["ms"], data[i:i + 4]))
                except Exception as e:  # noqa: BLE001
                    print(f"  reader: {type(e).__name__}: {e}")
            th = threading.Thread(target=reader)
            th.start()
            while th.is_alive():
                run(2)
                clock["ms"] += 2
                if at and clock["ms"] in at:
                    at[clock["ms"]]()
                th.join(0.005)
            print(f"  packets from the device: {[(t, p.hex()) for t, p in packets]}")
            return [(t, p[1], p[2], p[3]) for t, p in packets if len(p) == 4]

        def dbg_words():
            dbg = symbol("utm_dbg")
            if dbg is None:
                print("  (no utm_dbg symbol: m68k-elf-nm or out/platform/runtime/runtime.elf missing)")
                return None
            w = [int(cmd(f"peek {dbg + 4 * i:#x} 4")[1], 16) for i in range(7)]
            print(f"  utm_dbg @ {dbg:#x}: renderer second calls {w[0]}, STARTs {w[1]}, "
                  f"last sample record {w[2]:#x}, notes queued {w[3]}, repeats {w[4]}, "
                  f"notes swept {w[5]}, kicks posted {w[6]}")
            return w

        want = [0xB0] * 6 + [0x90, 0x80]
        # ---- 1. a START: the CCs, the note-on, the note-off a gate later
        taken = start_t1()
        check("the note-on was taken whole by EP2 OUT", taken == 4, f"{taken} of 4 bytes")
        msgs = listen()
        dbg_words()
        check("some USB MIDI came out", bool(msgs))
        check(f"everything on channel {CHANNEL + 1} (TRIG CHANNEL), none on the track's number",
              bool(msgs) and all(m[1] & 0x0f == CHANNEL for m in msgs), str(sorted({m[1] for m in msgs})))
        kinds = [m[1] & 0xf0 for m in msgs]
        check("CC x6, note-on, note-off, in that order", kinds[:8] == want, str([hex(k) for k in kinds[:8]]))
        if kinds[:8] == want:
            cc, on, off = msgs[:6], msgs[6], msgs[7]
            check("CC 16..21 (PLAYBACK page 1) in order", [m[2] for m in cc] == list(range(CC_FIRST, CC_FIRST + 6)),
                  str([m[2] for m in cc]))
            check("note-on velocity 100", on[3] == 100, str(on))
            check("the note-off is for the same note", off[2] == on[2], f"on {on[2]}, off {off[2]}")
            gate = off[0] - on[0]
            check(f"the gate is {GATE_MS:.1f} ms (160 frames) of port time", abs(gate - GATE_MS) <= GATE_TOL_MS,
                  f"{gate} ms, note-on at {on[0]} ms")
        # ---- 2. a track that stops reaching utm_render mid-gate has its note closed
        # The packer calls each track through its renderer pointer (RENDER_PTRS + 4t,
        # set from the kind table at 0x4000c004); in this boot only T1's points at
        # utm_render. SWAP_MS into the gate T2's is pointed at it and T1's at T2's old
        # (idle) one: T1 leaves as on a machine or part change, T2 is the track whose
        # next frame finds T1 missing.
        render = symbol("utm_render")
        check("utm_render's address (m68k-elf-nm, runtime.elf)", render is not None)
        if render is not None:
            t1, t2 = (int(cmd(f"peek {RENDER_PTRS + 4 * t:#x} 4")[1], 16) for t in (0, 1))
            check("T1 renders through utm_render, T2 does not", t1 == render and t2 != render, f"{t1:#x} {t2:#x}")

            def swap():
                cmd(f"poke {RENDER_PTRS + 4:#x} {render:08x}")
                cmd(f"poke {RENDER_PTRS:#x} {t2:08x}")
            taken = start_t1()
            msgs = listen({SWAP_MS: swap})
            w = dbg_words()
            for t in (0, 1):            # put the tracks back as they were
                cmd(f"poke {RENDER_PTRS + 4 * t:#x} {(t1, t2)[t]:08x}")
            kinds = [m[1] & 0xf0 for m in msgs]
            check("T1 leaving: CC x6, note-on, note-off", kinds[:8] == want, str([hex(k) for k in kinds[:8]]))
            if kinds[:8] == want:
                on, off = msgs[6], msgs[7]
                check("the note-off is for the same note, on its channel", off[1:3] == (0x80 | CHANNEL, on[2]), str(off))
                check(f"it comes when T1 leaves ({SWAP_MS} ms), not a gate later",
                      SWAP_MS <= off[0] <= SWAP_MS + 4, f"{off[0]} ms")
            check("utm_dbg counts one note swept", w is not None and w[5] == 1, str(w and w[5]))
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
