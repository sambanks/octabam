#!/usr/bin/env python3
"""OCTA-303 (modules/octa303, v7.0) through the stock panel under the port.

Three boots of the emulated unit on a fixture project (OT_PROJECT), with real key and encoder
events, then the Part, its shadow, the live lane, the published page record and the screen:

1. T1 -> FUNC+SRC -> the sixth row -> YES, then SETUP's FINE +10 and ACCV -20: the track is FLEX
   signed 'T','B',1 in the Part and its shadow, with OCTA-303's defaults (PLAYBACK 64 64 64 64 64 0,
   SETUP 0 0 64 0 0 64) then the edits (FINE 74, ACCV 44) in the Part, the shadow and the live lane;
   UI type 5's record (0x400d5f4c) is OCTA303's machine record, named OCTA-303, with SETUP's names.
2. The same selection, then another machine (four rows up): the signature is cleared in both copies.
3. The Part validator (0x40002318) on a Part with a signed track keeps its SETUP bytes
   (FINE/SLID/DRIV 100/90/120); on the unsigned track next to it the same bytes clamp to FLEX's.

Skips without OT_PROJECT (a stock project directory to copy; it is not modified).
"""
import os
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/harness"))
from ab_fixture import prepare  # noqa: E402  (Analog BD's: FLEX tracks, no signatures, no FX)

OUT = pathlib.Path(os.environ.get("O3_UI_OUT", ROOT / "out/octa303/ui-gate")).resolve()
PART = 0x40170F60            # part 0's Part' (BANK + 0x8ed80); found again from the dumped BANK pointer
SHADOW = 0x100A4ECE
LANE = 0x80000810
PB_TABLE5 = 0x400D5F4C


def key(code, gap=0.6, hold=0.4):
    return [(gap, f"key {code:#x} down"), (hold, f"key {code:#x} up")]


FUNC_SRC = [(0.6, "key 0x2d down"), (0.3, "key 0x22 down"), (0.3, "key 0x22 up"), (0.3, "key 0x2d up")]
SELECT = key(0x10) + FUNC_SRC + [e for _ in range(6) for e in key(0x20, 0.25, 0.25)] + key(0x31)


def symbols():
    nm = shutil.which("m68k-elf-nm") or "m68k-elf-nm"
    out = subprocess.check_output([nm, str(ROOT / "out/platform/runtime/runtime.elf")], text=True)
    return {l.split()[-1]: int(l.split()[0], 16) for l in out.splitlines() if len(l.split()) == 3}


def run(name, card, image, script, steps=(), extra=()):
    global PART
    d = OUT / name
    d.mkdir(parents=True, exist_ok=True)
    spans = (f"{PART:#x},6322={d}/part.bin;{SHADOW:#x},6322={d}/shadow.bin;0x46c82456,4={d}/bank.bin;"
             f"{LANE:#x},600={d}/lane.bin;{PB_TABLE5:#x},4={d}/page.bin")
    cmd = [os.environ.get("O3_EMU", str(ROOT / "out/emu/ot_emu")), "--image", str(image), "--card", str(card),
           "--set", "OCTABAM", "--project", "RIG", "--load-ms", "20000", "--dsp", "--mem-dump", spans,
           "--lcd", str(d / "lcd.bin"), *extra]
    if script:
        t, ev = 0, []
        for delay, e in script + [(1.0, "quit")]:
            t += round(delay * 1000)
            ev.append(f"{t} {e}\n")
        (d / "events.txt").write_text("".join(ev))
        cmd += ["--live-script", str(d / "events.txt")]
    else:
        cmd += ["--sequencer", "--internal-clock", "--frames", "2", "--main-level", "64"]
        for s in steps:
            cmd += ["--step", s]
    with (d / "port.log").open("w") as log:
        subprocess.run(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=900, check=True)
    log = (d / "port.log").read_text()
    assert "ILLEGAL" not in log, f"{name}: an illegal instruction ({d / 'port.log'})"
    rd = lambda f: (d / f).read_bytes() if (d / f).exists() else b""
    return rd, log, d


def main():
    global PART
    src = os.environ.get("OT_PROJECT")
    if not src:
        print("[SKIP] OCTA-303 panel: set OT_PROJECT to a stock project fixture")
        return
    emu = pathlib.Path(os.environ.get("O3_EMU", str(ROOT / "out/emu/ot_emu")))
    if not emu.exists():
        print(f"[SKIP] OCTA-303 panel: no port at {emu} (make emu)")
        return
    OUT.mkdir(parents=True, exist_ok=True)
    fixture = prepare(src, OUT / "project")
    card = OUT / "card.img"
    subprocess.run([sys.executable, str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(fixture), "OCTABAM", "RIG",
                    "--tree", str(OUT / "tree"), "--out", str(card)], check=True, cwd=ROOT)
    image = OUT / "image.bin"
    shutil.copy2(os.environ.get("O3_IMAGE", ROOT / "out/mainos_bus.bin"), image)
    # Beside other machines (modules/hooks machine_rows) OCTA-303 is a later row of a longer list,
    # its UI type its row: the machine list's row count, poked at 0x40079248, says how long, and
    # the remix the image was built from says where (hooks_flags.image_row). SELECT's six DOWNs
    # land on the last row; short UPs (a 0.25 s hold repeats) climb to ours.
    global PB_TABLE5, SELECT
    sys.path.insert(0, str(ROOT / "tools"))
    from remix import hooks_flags
    rows = image.read_bytes()[0x40079248 - 0x40000400 + 3]
    o3_row = hooks_flags.image_row("OCTA303", ROOT) if not os.environ.get("O3_IMAGE") else rows - 1
    SELECT = SELECT[:-2] + [e for _ in range(rows - 1 - o3_row) for e in key(0x33, 0.25, 0.06)] + SELECT[-2:]
    PB_TABLE5 = 0x400D5F38 + 4 * o3_row
    sym = symbols()
    rec = sym["o3_desc"]                  # the machine's record (v7.9: o3_desc holds that one record only)

    # 1. select OCTA-303, edit SETUP
    script = SELECT + [(0.8, "enc 2 10"), (0.5, "enc 5 -20")]
    rd, log, d = run("select", card, image, script)
    assert "ended on quit" in log, "select: the script did not finish"
    bank = int.from_bytes(rd("bank.bin"), "big")
    if bank + 0x8ED80 != PART:              # another remix's arena: part 0 elsewhere, run again there
        PART = bank + 0x8ED80
        rd, log, d = run("select", card, image, script)
    part, shadow, lane = rd("part.bin"), rd("shadow.bin"), rd("lane.bin")
    want_pb, want_su = [64, 64, 64, 64, 64, 0], [0, 0, 74, 0, 0, 44]
    for nm, p in (("part", part), ("shadow", shadow)):
        assert p[0x22] == 1, (nm, "machine byte", p[0x22])
        assert p[0x3C:0x3F] == b"TB\x01", (nm, "signature", p[0x3C:0x3F])
        assert list(p[0x30:0x36]) == want_pb, (nm, "PLAYBACK", list(p[0x30:0x36]))
        assert list(p[0x1E0:0x1E6]) == want_su, (nm, "SETUP", list(p[0x1E0:0x1E6]))
    assert list(lane[0:6]) == want_pb and list(lane[0x20:0x26]) == [0, 0, 74, 0, 0, 44], \
        ("live lane", list(lane[0:6]), list(lane[0x20:0x26]))
    assert int.from_bytes(rd("page.bin"), "big") == rec, (f"UI type {o3_row}'s record", rd("page.bin").hex(), hex(rec))
    print("PASS select: FLEX signed T B 1, defaults then FINE 74 / ACCV 44 in the Part, its shadow and the "
          f"live lane; UI type {o3_row} = OCTA303's record")

    # 2. select, then another machine
    rd, log, _ = run("unsign", card, image, SELECT + key(0x32) + FUNC_SRC +
                     [e for _ in range(4) for e in key(0x33, 0.25, 0.25)] + key(0x31))
    part, shadow = rd("part.bin"), rd("shadow.bin")
    assert part[0x3C:0x3F] == bytes(3) and shadow[0x3C:0x3F] == bytes(3), \
        ("signature not cleared", part[0x3C:0x3F], shadow[0x3C:0x3F])
    print("PASS unsign: choosing another machine clears the signature in both copies")

    # 3. the Part validator
    P = PART
    pk = [f"{P + 0x3C:#x}=0x54", f"{P + 0x3D:#x}=0x42", f"{P + 0x3E:#x}=1"]
    for i, v in enumerate((3, 1, 100, 90, 120, 10)):
        pk.append(f"{P + 0x1E0 + i:#x}={v}")
    pk.append(f"{P + 0x1E0 + 30 + 2:#x}=100")               # T2, unsigned: clamps
    rd, log, _ = run("validate", card, image, None,
                     (f"-:poke:{';'.join(pk)}", f"-:call:0x40002318,{P:#x}", f"-:dump:{P:#x},6322={OUT}/validate/after.bin"))
    after = rd("after.bin")
    assert list(after[0x1E0:0x1E6]) == [3, 1, 100, 90, 120, 10], ("signed track clamped", list(after[0x1E0:0x1E6]))
    assert after[0x1E0 + 30 + 2] <= 3, ("the unsigned track was not validated", after[0x1E0 + 32])
    print("PASS validate: a signed track keeps FINE/SLID/DRIV 100/90/120; the unsigned one clamps "
          f"(T2 LEN 100 -> {after[0x1E0 + 32]})")

    # 4. the limit: a Part holds at most O3_MAX signed tracks; a third pick is refused with the stock toast
    NOTIFY = 0x4005A2B8
    sig = lambda base, t: [f"{base + 0x3C + 30 * t + i:#x}={v:#x}" for i, v in enumerate((0x54, 0x42, 1))]
    pick_t3 = key(0x12) + SELECT[len(key(0x10)):]
    for name, signed in (("limit", (0, 1)), ("limit-control", (0,))):
        pokes = ";".join(x for t in signed for base in (PART, SHADOW) for x in sig(base, t))
        rd, log, d = run(name, card, image, [(0.5, f"poke {pokes}")] + pick_t3, extra=("--watch-pc", f"{NOTIFY:#x}"))
        assert "ended on quit" in log, f"{name}: the script did not finish"
        part, shadow = rd("part.bin"), rd("shadow.bin")
        hits = [l for l in log.splitlines() if l.startswith("watch-pc") and "hit(s)" in l]
        n = int(hits[0].split(":")[1].split()[0]) if hits else 0
        for nm, p in (("part", part), ("shadow", shadow)):
            for t in signed:
                assert p[0x3C + 30 * t:0x3F + 30 * t] == b"TB\x01", (name, nm, f"T{t + 1} lost its signature")
            assert p[0x22 + 2] == 1, (name, nm, "T3's machine byte", p[0x22 + 2])
        t3 = (part[0x3C + 60:0x3F + 60], shadow[0x3C + 60:0x3F + 60])
        if len(signed) == 2:
            assert t3 == (bytes(3), bytes(3)), (name, "T3 was signed past the limit", t3)
            assert n > 0, (name, "no toast: NOTIFY was not called")
            print(f"PASS limit: T1 and T2 signed, T3 refused (FLEX, no signature, in both copies), toast called {n}x")
        else:
            assert t3 == (b"TB\x01", b"TB\x01"), (name, "control: T3 should be signed with one other machine", t3)
            print("PASS limit control: with one other machine T3 is signed")

    # 5. the Part validator unsigns a third signed track of a loaded Part
    pk = [x for t in (0, 1, 2) for x in sig(PART, t)]
    rd, log, _ = run("limit-validate", card, image, None,
                     (f"-:poke:{';'.join(pk)}", f"-:call:0x40002318,{PART:#x}", f"-:dump:{PART:#x},6322={OUT}/limit-validate/after.bin"))
    after = rd("after.bin")
    for t in (0, 1):
        assert after[0x3C + 30 * t:0x3F + 30 * t] == b"TB\x01", ("limit-validate", f"T{t + 1} lost its signature")
    assert after[0x3C + 60:0x3F + 60] == bytes(3), ("limit-validate", "T3 still signed", after[0x3C + 60:0x3F + 60])
    print("PASS limit-validate: the Part validator keeps the first two signed tracks and unsigns the third")

    # 6. beside another machine the limit counts every kind (modules/hooks MC_LIMIT, mc_sig_table):
    #    T1 signed by ANALOG BD ('A','B',1) and T2 by OCTA303, so a third pick is refused; with T1 alone it is not
    if rows - 5 >= 2:
        absig = lambda base, t: [f"{base + 0x3C + 30 * t + i:#x}={v:#x}" for i, v in enumerate((0x41, 0x42, 1))]
        for name, ours in (("limit-mixed", (1,)), ("limit-mixed-control", ())):
            pokes = ";".join(x for base in (PART, SHADOW) for x in absig(base, 0) + [y for t in ours for y in sig(base, t)])
            rd, log, d = run(name, card, image, [(0.5, f"poke {pokes}")] + pick_t3, extra=("--watch-pc", f"{NOTIFY:#x}"))
            assert "ended on quit" in log, f"{name}: the script did not finish"
            part, shadow = rd("part.bin"), rd("shadow.bin")
            hits = [l for l in log.splitlines() if l.startswith("watch-pc") and "hit(s)" in l]
            n = int(hits[0].split(":")[1].split()[0]) if hits else 0
            t3 = (part[0x3C + 60:0x3F + 60], shadow[0x3C + 60:0x3F + 60])
            if ours:
                assert t3 == (bytes(3), bytes(3)), (name, "T3 was signed past the limit", t3)
                assert n > 0, (name, "no toast: NOTIFY was not called")
                print(f"PASS {name}: T1 ANALOG BD and T2 OCTA-303, T3 refused, toast called {n}x")
            else:
                assert t3 == (b"TB\x01", b"TB\x01"), (name, "control: T3 should be signed beside one ANALOG BD track", t3)
                print(f"PASS {name}: T1 ANALOG BD alone, T3 is signed")
        pk = [x for t in (0, 1, 2) for x in (absig(PART, t) if t == 0 else sig(PART, t))]
        rd, log, _ = run("limit-mixed-validate", card, image, None,
                         (f"-:poke:{';'.join(pk)}", f"-:call:0x40002318,{PART:#x}", f"-:dump:{PART:#x},6322={OUT}/limit-mixed-validate/after.bin"))
        after = rd("after.bin")
        assert after[0x3C:0x3F] == b"AB\x01", ("limit-mixed-validate", "T1 lost its signature", after[0x3C:0x3F])
        assert after[0x3C + 30:0x3F + 30] == b"TB\x01", ("limit-mixed-validate", "T2 lost its signature")
        assert after[0x3C + 60:0x3F + 60] == bytes(3), ("limit-mixed-validate", "T3 still signed", after[0x3C + 60:0x3F + 60])
        print("PASS limit-mixed-validate: T1 ANALOG BD and T2 OCTA-303 kept, a third OCTA-303 track unsigned")


if __name__ == "__main__":
    main()
