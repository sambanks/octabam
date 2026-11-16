#!/usr/bin/env python3
"""PROBE (not a gate): USB MIDI TRACKS on a real project, under the ColdFire port.

Stages an Octatrack project onto a virtual card (verify_set's stage()), boots
the image under --interactive --frame with the USB device model, enumerates,
starts the sequencer with a MIDI START and 0xF8 ticks, and records every
USB-MIDI packet the device sends on EP2 IN. Prints, per channel (= the track's TRIG CHANNEL: track n on channel n in a default project), the
note-ons, note-offs and CCs, and the module's debug counters.

    OT_PROJECT=<project dir> python3 tools/verify/probe_usbmidi_tracks_project.py [--part N] [--bank N] [--ticks N]

Needs `make emu-cf`, `make emu-setup` (the .venv stage_card.py runs in) and an
image built from a remix with USB MIDI TRACKS (out/mainos_bus.bin).
Pattern 1 of the saved bank plays; the part is the pattern's part unless --part.

Retrigs: --gen-wav --rt 1,72 --scene-rtrg 1,5 --fader 0=255,25=1,... moves RTRG with a
real scene while bursts play; --watchmem 0x800048a0,4 --watchmem 0x8000489c,4 times
T1's repeats (pc 40004160) and latched counts (pc 4000d4ee). Without --gen-wav a
voice whose sample is not on the card stops at once and no repeat happens.
"""
import argparse
import importlib.util
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import threading
import collections

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
import usb_host  # noqa: E402  (tools/harness)
import ot_project as otp  # noqa: E402

spec = importlib.util.spec_from_file_location("verify_set", ROOT / "tools/verify/verify_set.py")
vs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vs)

EMU = ROOT / "out/emu/ot_emu"
IMAGE = ROOT / "out/mainos_bus.bin"
ELF = ROOT / "out/platform/runtime/runtime.elf"
# one scratch directory per process (TRAPS trap-tmp-race): two probes at once must not share the card image
OUT = pathlib.Path(tempfile.mkdtemp(prefix="usbtracks_probe_", dir=ROOT / "out"))
CLOCK_RECEIVE = 0x80000028
TYPE = {0: "STATIC", 1: "FLEX", 2: "THRU", 3: "NEIGH", 4: "PICKUP"}


def symbol(name):
    import shutil
    nm = shutil.which("m68k-elf-nm") or shutil.which("m68k-linux-gnu-nm")
    if nm is None or not ELF.is_file():
        return None
    for line in subprocess.run([nm, str(ELF)], capture_output=True, text=True).stdout.splitlines():
        f = line.split()
        if len(f) == 3 and f[2] == name:
            return int(f[0], 16)
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", default=os.environ.get("OT_PROJECT", ""))
    ap.add_argument("--bank", type=int, default=1)
    ap.add_argument("--part", type=int, default=0, help="1-based part to read the track setup from (default: pattern 1's)")
    ap.add_argument("--ticks", type=int, default=300, help="chunks of --tick-ms to run after PLAY")
    ap.add_argument("--tick-ms", type=float, default=50.0)
    ap.add_argument("--poke", action="append", default=[], help="ADDR=HEXBYTE written after PLAY and before every chunk (repeatable)")
    ap.add_argument("--gen-wav", action="store_true", help="write a 3 s sine WAV for every STATIC/FLEX sample the part uses and stage it (the project's own audio is not on this machine)")
    ap.add_argument("--rt", default="", help="RTRG,RTIM: lock them (slots 4,5) on every trig of T1, pattern 1 (needs --gen-wav: it edits the scratch copy)")
    ap.add_argument("--watch", default="", help="ADDR,LEN: print this many bytes (hex) after every chunk, with the frame count")
    ap.add_argument("--watchmem", action="append", default=[], help="ADDR,LEN: log every write into the range (the port's own write watch), printed at the end with the writing PC")
    ap.add_argument("--strt-locks", action="store_true", help="lock T1's trigs: PTCH 30, 32.., STRT 2, 4.., LEN 10, 11.., RATE 120, 119..; use with --rt")
    ap.add_argument("--scene-rtrg", default="", help="A,B: T1's RTRG scene locks, scene A (1) and scene B (9), in every Part (needs --gen-wav; a modern bank layout)")
    ap.add_argument("--scene-lock", action="append", default=[], help="SLOT,A,B: T1's scene locks for a page-1 slot (0..5), as --scene-rtrg")
    ap.add_argument("--fader", default="", help="TICK=BYTE,...: the crossfader's panel report (row 0x40, 255 = scene A, 1 = scene B) at that chunk after PLAY; before PLAY it sits at 255")
    a = ap.parse_args()
    if not a.project:
        print("probe: OT_PROJECT=<dir> or --project")
        return 1
    for need, hint in ((EMU, "make emu-cf"), (IMAGE, "make image REMIX=usb-midi-tracks BUILD=1"), (vs.PY, "make emu-setup")):
        if not need.exists():
            print(f"probe: {need} is missing ({hint})")
            return 1
    pdir = pathlib.Path(a.project).expanduser()
    part_no = a.part
    if not part_no:
        pat_part, _ = otp.bank_info(pdir, a.bank)
        part_no = pat_part[0] + 1
        if not 1 <= part_no <= 4:
            print(f"probe: pattern 1's part reads as {pat_part[0]} (an old project?); using part 1, pass --part to change")
            part_no = 1
    part = vs.part_of(pdir, a.bank, part_no)
    print("part", part_no, "machines", [TYPE.get(m, m) for m in part["mtype"]],
          "flex slots (1-based)", [s + 1 for s in part["flex"]], "static slots (1-based)", [s + 1 for s in part["static"]])
    OUT.mkdir(parents=True, exist_ok=True)
    if a.gen_wav:
        import shutil, struct, math, wave
        cp = OUT / "projsrc"
        if cp.exists():
            shutil.rmtree(cp)
        shutil.copytree(pdir, cp)
        pdir = cp
        if a.rt:
            import ot_bank as ob
            rt = [int(x, 0) for x in a.rt.split(",")]
            rtrg, rtim = rt[0], rt[1]
            hold = rt[2] if len(rt) > 2 else None

            def mut(data):
                for i, st in enumerate(ob.trigs(data, 0, 0)):
                    base = ob.trac(0, 0) + ob.LOCKS + st * ob.LOCK_LEN
                    if a.strt_locks:
                        data[base + 0] = 30 + 2 * i
                        data[base + 1] = 2 * (i + 1) & 0x7f
                        data[base + 2] = 10 + i
                        data[base + 3] = 120 - i
                    data[base + 4] = rtrg
                    data[base + 5] = rtim
                    data[base + 31] = 0                 # sample lock: slot 1, which has a PATH (an empty slot's voice stops at once)
                    if hold is not None:
                        data[base + 13] = hold          # AMP HOLD (lock slot 13): 127 = infinite
            otp._bank_write(pdir, a.bank, mut, guard=False)
            print("locked RTRG", rtrg, "RTIM", rtim, "on T1's trigs", ob.trigs(pdir_bytes := (pdir / f"bank{a.bank:02d}.work").read_bytes(), 0, 0))
        locks = [(4, *(int(x, 0) for x in a.scene_rtrg.split(",")))] if a.scene_rtrg else []
        locks += [tuple(int(x, 0) for x in sl.split(",")) for sl in a.scene_lock]
        if locks:
            p = pdir / f"bank{a.bank:02d}.work"
            d = bytearray(p.read_bytes())
            for pt in range(8):                     # verify_scenes.fixture's layout: Part + 9 in the file
                o = 0x8eed6 + pt * 0x18bb + 9
                d[o + 0x11] = 8                     # scene B = scene 9
                for slot, ra, rb in locks:          # scene block: scene * 0x100 + track * 0x20, byte k = slot k
                    d[o + 0x662 + slot] = ra
                    d[o + 0x662 + 0x800 + slot] = rb
            d[-2:] = (sum(d[0x10:-2]) & 0xffff).to_bytes(2, "big")
            p.write_bytes(bytes(d))
        # One WAV behind every sample slot, FLEX and STATIC: the part the port plays is not always
        # the part read here (old layouts, trap-otemu-part) and a missing file kills the voice on
        # its first frame (descriptor +8 = 3, stop routine 0x40006820), retrigs and all.
        rel = "../AUDIO/utm_probe.wav"
        pw = pdir / "project.work"
        pw.write_bytes(re.sub(rb"PATH=[^\r\n]+", b"PATH=" + rel.encode(), pw.read_bytes()))
        f = (pdir / rel).resolve()
        f.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(f), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(44100)
            w.writeframes(b"".join(struct.pack("<h", int(12000 * math.sin(2 * math.pi * 220 * i / 44100))) for i in range(44100 * 3)))
        print("generated", f)
    card = OUT / "card.img"
    audio, mb = vs.stage(pdir, part, "OCTABAM", "RIG", OUT / "tree", 64, a.bank, card)
    print(f"card: {mb} MB, {len(audio)} sample file(s) staged")
    sock = f"/tmp/ot-trkprobe-{os.getpid()}.sock"
    emu = subprocess.Popen([str(EMU), "--image", str(IMAGE), "--card", str(card), "--mount", "--set", "OCTABAM", "--project", "RIG",
                            "--interactive", "--frame", "--usb-host", sock, "--load-ms", "90000", "--main-level", "64"],
                           cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)

    def reply():
        while True:
            line = emu.stdout.readline()
            if not line:
                raise RuntimeError("the port exited")
            if line.startswith(("ready", "ok", "err", "peek", "status", "writes")):
                return line.split()

    def cmd(c):
        emu.stdin.write(c + "\n")
        emu.stdin.flush()
        r = reply()
        if r[0] == "err":
            raise RuntimeError(f"{c}: {' '.join(r)}")
        return r

    b = None
    packets = []
    stop = threading.Event()
    try:
        print("port:", " ".join(reply()))
        print("run 3000:", " ".join(cmd("run 3000")))
        print("status:", " ".join(cmd("status")))
        res = {}

        def bench():
            res["b"] = usb_host.Bench(sock, timeout=120.0)
            usb_host.enumerate_device(res["b"], hs=True)
        th = threading.Thread(target=bench)
        th.start()
        while th.is_alive():
            cmd("run 50")
            th.join(0.01)
        b = res["b"]
        print("status after enumeration:", " ".join(cmd("status")))

        def reader():
            while not stop.is_set():
                try:
                    data = b.ep_in(2, 512, timeout=0.2)   # a high-speed bulk packet: a whole transfer, as a host reads it
                except Exception:  # noqa: BLE001 -- a timeout is just no packet yet
                    continue
                for i in range(0, len(data) - 3, 4):
                    packets.append(data[i:i + 4])
        rt = threading.Thread(target=reader, daemon=True)
        rt.start()
        for wm in a.watchmem:
            cmd(f"watchmem {' '.join(wm.split(','))}")
        cur = int(cmd(f"peek {CLOCK_RECEIVE:#x} 1")[1], 16)
        cmd(f"poke {CLOCK_RECEIVE:#x} {cur & 0xfe:02x}")   # internal clock
        fader = {int(k): int(v, 0) for k, v in (x.split("=") for x in a.fader.split(",") if x)}
        if fader:
            cmd("key 0x40 255")
            cmd("run 100")
        cmd("key 0x25 1")                                   # PLAY down (row 0x25, bit 0)
        cmd("run 50")
        cmd("key 0x25 0")                                   # PLAY up
        wa = wl = None
        if a.watch:
            ptr = a.watch.startswith("*")
            wa, wl = (int(x, 0) for x in a.watch.lstrip("*").split(","))
        for tick in range(a.ticks):                         # --ticks x --tick-ms of playing
            if tick in fader:
                cmd(f"key 0x40 {fader[tick]}")
            for pk in a.poke:
                ad, v = pk.split("=")
                cmd(f"poke {int(ad, 0):#x} {int(v, 16):02x}")
            r = cmd(f"run {a.tick_ms}")
            if wa is not None:
                base = int(cmd(f"peek {wa:#x} 4")[1], 16) if ptr else wa
                words = ([f"@{base:x}"] if ptr else []) + [cmd(f"peek {base + i:#x} 4")[1] for i in range(0, 64 if ptr else wl, 4)]
                print("watch", r[2], len(packets), " ".join(words))
        print("run 500:", " ".join(cmd("run 500")))
        print("status at the end:", " ".join(cmd("status")))
        if a.watchmem:
            ws = cmd("writes")
            print(ws[0], ws[1])
            for rec in ws[2:]:
                smp, pc, ad, val, sz, tcb = rec.split(":")
                print(f"  {smp} pc {pc} [{ad}] <- {val} ({sz})")
        stop.set()
        rt.join(timeout=5)
        def words(ad, n):
            return [int(cmd(f"peek {ad + i:#x} 4")[1], 16) for i in range(0, n, 4)]
        v = words(0x800049d8, 32)
        print("T1 voice", " ".join(f"{x:08x}" for x in v))
        for nm, ad in (("voice+4", v[1]), ("voice+8 record", v[2]), ("FLEX record 0", 0x100b14f0)):
            if ad:
                print(f"{nm} @{ad:#x}", " ".join(f"{x:08x}" for x in words(ad, 48)))
        dbg = symbol("utm_dbg")
        if dbg is not None:
            w = words(dbg, 20)
            print(f"utm_dbg: renderer second calls {w[0]}, STARTs {w[1]}, last record {w[2]:#x}, notes queued {w[3]}, repeats {w[4]}")
        drops = symbol("usbmidi_tx_drops")
        if drops is not None:
            print("usbmidi_tx_drops", words(drops, 4)[0])
    finally:
        stop.set()
        if b is not None:
            b.sock.close()
        try:
            cmd("quit")
            emu.wait(timeout=30)
        except Exception:  # noqa: BLE001
            emu.kill()

    per = collections.defaultdict(lambda: collections.defaultdict(list))
    for p in packets:
        st, d1, d2 = p[1], p[2], p[3]
        kind = {0x90: "on", 0x80: "off", 0xB0: "cc"}.get(st & 0xF0)
        if kind:
            per[(st & 0x0F) + 1][kind].append((d1, d2))
    print(f"{len(packets)} packet(s)")
    for ch in sorted(per):
        d = per[ch]
        print(f"  ch {ch} (T{ch}): {len(d['on'])} note-on {sorted(set(n for n, v in d['on']))}, {len(d['off'])} note-off")
        for c, n in zip(range(16, 22), ("PTCH", "STRT", "LEN", "RATE", "RTRG", "RTIM")):
            print(f"    {n} CC{c} {[v for k, v in d['cc'] if k == c]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
