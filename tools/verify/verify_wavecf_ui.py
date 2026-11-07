#!/usr/bin/env python3
"""WAVE (modules/wavecf) through the stock panel under the port.

Boots of the emulated unit on a fixture project (OT_PROJECT), with real key and encoder events, then the
Part, its shadow, the live lane and the published page record:

1. T1 -> FUNC+SRC -> the last row of the machine list -> YES: the track is FLEX signed 'W','V',1 in the Part
   and its shadow with WAVE's PLAYBACK defaults (TUNE FRAM CHRD VOIC ATK REL = 64 0 3 2 20 60; SETUP VIBR VRAT OCT FINE COMP MODE = 0 40 1 64 0 0) and the live
   lane; the row's UI type record is WAVE's.
2. The same selection, then another machine: the signature is cleared in both copies.
3. The Part validator (0x40002318) keeps a signed track's PLAYBACK and SETUP bytes, which the stock validator
   clamps on an unsigned track (SETUP: FLEX's ranges).
4. The limit: a Part holds at most MC_LIMIT machines, counted over every kind; a third pick is refused.
5. The validator unsigns a third signed track of a loaded Part.
6. Beside OCTA303 (image of remix wavecf-octa303): T1 OCTA-303 and T2 WAVE, a third pick is refused; with
   T1 alone it is not.

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

OUT = pathlib.Path(os.environ.get("WCF_UI_OUT", ROOT / "out/wavecf/ui-gate")).resolve()
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
    # the runtime.elf of the image under test (WCF_RUNTIME_ELF), else the last build's
    out = subprocess.check_output([nm, os.environ.get("WCF_RUNTIME_ELF", str(ROOT / "out/platform/runtime/runtime.elf"))], text=True)
    return {l.split()[-1]: int(l.split()[0], 16) for l in out.splitlines() if len(l.split()) == 3}


def run(name, card, image, script, steps=(), extra=()):
    global PART
    d = OUT / name
    d.mkdir(parents=True, exist_ok=True)
    spans = (f"{PART:#x},6322={d}/part.bin;{SHADOW:#x},6322={d}/shadow.bin;0x46c82456,4={d}/bank.bin;"
             f"{LANE:#x},600={d}/lane.bin;{PB_TABLE5:#x},4={d}/page.bin")
    cmd = [os.environ.get("WCF_EMU", str(ROOT / "out/emu/ot_emu")), "--image", str(image), "--card", str(card),
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
        print("[SKIP] WAVE panel: set OT_PROJECT to a stock project fixture")
        return
    emu = pathlib.Path(os.environ.get("WCF_EMU", str(ROOT / "out/emu/ot_emu")))
    if not emu.exists():
        print(f"[SKIP] WAVE panel: no port at {emu} (make emu)")
        return
    OUT.mkdir(parents=True, exist_ok=True)
    fixture = prepare(src, OUT / "project")
    card = OUT / "card.img"
    subprocess.run([sys.executable, str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(fixture), "OCTABAM", "RIG",
                    "--tree", str(OUT / "tree"), "--out", str(card)], check=True, cwd=ROOT)
    image = OUT / "image.bin"
    shutil.copy2(os.environ.get("WCF_IMAGE", ROOT / "out/mainos_bus.bin"), image)
    # Beside other machines (modules/hooks machine_rows) OCTA-303 is a later row of a longer list,
    # its UI type its row: the machine list's row count, poked at 0x40079248, says how long, and
    # the remix the image was built from says where (hooks_flags.image_row). SELECT's six DOWNs
    # land on the last row; short UPs (a 0.25 s hold repeats) climb to ours.
    global PB_TABLE5, SELECT
    sys.path.insert(0, str(ROOT / "tools"))
    from remix import hooks_flags
    rows = image.read_bytes()[0x40079248 - 0x40000400 + 3]
    o3_row = hooks_flags.image_row("WAVE CF", ROOT) if not os.environ.get("WCF_IMAGE") else rows - 1
    SELECT = SELECT[:-2] + [e for _ in range(rows - 1 - o3_row) for e in key(0x33, 0.25, 0.06)] + SELECT[-2:]
    PB_TABLE5 = 0x400D5F38 + 4 * o3_row
    sym = symbols()
    rec = sym["wc_desc"] + 0x194          # the machine's record (wc_desc's second, WC_DLEN apart)

    # 1. select WAVE
    rd, log, d = run("select", card, image, SELECT)
    assert "ended on quit" in log, "select: the script did not finish"
    bank = int.from_bytes(rd("bank.bin"), "big")
    if bank + 0x8ED80 != PART:              # another remix's arena: part 0 elsewhere, run again there
        PART = bank + 0x8ED80
        rd, log, d = run("select", card, image, SELECT)
    part, shadow, lane = rd("part.bin"), rd("shadow.bin"), rd("lane.bin")
    want_pb = [64, 0, 3, 2, 20, 60]
    for nm, p in (("part", part), ("shadow", shadow)):
        assert p[0x22] == 1, (nm, "machine byte", p[0x22])
        assert p[0x3C:0x3F] == b"WV\x01", (nm, "signature", p[0x3C:0x3F])
        assert list(p[0x30:0x36]) == want_pb, (nm, "PLAYBACK", list(p[0x30:0x36]))
    assert list(lane[0:6]) == want_pb, ("live lane", list(lane[0:6]))
    want_su = [0, 40, 1, 64, 0, 0]          # SETUP: VIBR VRAT OCT FINE COMP MODE
    for nm, p in (("part", part), ("shadow", shadow)):
        assert list(p[0x1E0:0x1E6]) == want_su, (nm, "SETUP", list(p[0x1E0:0x1E6]))
    assert list(lane[0x20:0x26]) == want_su, ("live lane SETUP", list(lane[0x20:0x26]))
    want_amp = [0, 40, 56]                  # ATK HOLD REL: finite, the stock page holds a note forever
    for nm, p in (("part", part), ("shadow", shadow)):
        assert list(p[0x120:0x123]) == want_amp, (nm, "AMP ATK HOLD REL", list(p[0x120:0x123]))
    assert list(lane[12:15]) == want_amp, ("live lane AMP", list(lane[12:15]))
    assert int.from_bytes(rd("page.bin"), "big") == rec, (f"UI type {o3_row}'s record", rd("page.bin").hex(), hex(rec))
    print(f"PASS select: FLEX signed W V 1, PLAYBACK defaults {want_pb} and SETUP {want_su}, AMP ATK HOLD REL {want_amp} in the Part, its shadow and the live lane; "
          f"UI type {o3_row} = WAVE's record")

    # 1b. the SRC page: the page resolver (0x40031ed6, after its table load) hands back WAVE's record, not FLEX's
    #     (OCTA303's resolver once clobbered a1 and, for an empty slot, never passed the track on: stock labels)
    rd, log, d = run("srcpage", card, image, SELECT + key(0x32, 1.5, 0.4) + key(0x22, 1.5, 0.5) + [(4.0, "poke 0x100b14cf=0")],
                     extra=("--watch-pc", "0x40031ed6"))
    assert "ended on quit" in log, "srcpage: the script did not finish"
    import re as _re
    ret = [int(m.group(1), 16) for m in _re.finditer(r"at 0x40031ed6 d0=(?:0x)?([0-9a-f]+)", log)]
    assert ret, ("srcpage: the page resolver was never reached", log[-800:])
    assert rec in ret, ("srcpage: the resolver never returned WAVE's record", hex(rec), sorted({hex(x) for x in ret})[:6])
    print(f"PASS srcpage: pressing SRC on the WAVE track, the page resolver returns WAVE's record ({ret.count(rec)} of {len(ret)} calls)")

    # 2. select, then another machine
    rd, log, _ = run("unsign", card, image, SELECT + key(0x32) + FUNC_SRC +
                     [e for _ in range(4) for e in key(0x33, 0.25, 0.25)] + key(0x31))
    part, shadow = rd("part.bin"), rd("shadow.bin")
    assert part[0x3C:0x3F] == bytes(3) and shadow[0x3C:0x3F] == bytes(3), \
        ("signature not cleared", part[0x3C:0x3F], shadow[0x3C:0x3F])
    print("PASS unsign: choosing another machine clears the signature in both copies")

    # 3. the Part validator
    P = PART
    values = [70, 127, 31, 3, 127, 127]
    setup = [127, 127, 2, 127, 127, 1]
    pk = [f"{P + 0x3C:#x}=0x57", f"{P + 0x3D:#x}=0x56", f"{P + 0x3E:#x}=1"]
    for i, v in enumerate(values):
        pk.append(f"{P + 0x30 + i:#x}={v}")                   # T1, signed
        pk.append(f"{P + 0x30 + 30 + i:#x}={v}")              # T2, the same bytes unsigned
    for i, v in enumerate(setup):
        pk.append(f"{P + 0x1E0 + i:#x}={v}")
        pk.append(f"{P + 0x1E0 + 30 + i:#x}={v}")
    rd, log, _ = run("validate", card, image, None,
                     (f"-:poke:{';'.join(pk)}", f"-:call:0x40002318,{P:#x}", f"-:dump:{P:#x},6322={OUT}/validate/after.bin"))
    after = rd("after.bin")
    assert list(after[0x30:0x36]) == values, ("a signed track's PLAYBACK was clamped", list(after[0x30:0x36]))
    assert list(after[0x1E0:0x1E6]) == setup, ("a signed track's SETUP was clamped", list(after[0x1E0:0x1E6]))
    assert list(after[0x1E0 + 30:0x1E6 + 30]) != setup, ("the validator clamps no SETUP byte: this check proves nothing",
                                                         list(after[0x1E0 + 30:0x1E6 + 30]))
    print(f"PASS validate: a signed track keeps PLAYBACK {values} and SETUP {setup}; the same SETUP bytes unsigned become "
          f"{list(after[0x1E0 + 30:0x1E6 + 30])} (the stock validator's FLEX ranges)")

    # 4. the limit: at most MC_LIMIT machines a Part, a third pick is refused with the stock toast
    NOTIFY = 0x4005A2B8
    sig = lambda base, t, b=(0x57, 0x56, 1): [f"{base + 0x3C + 30 * t + i:#x}={v:#x}" for i, v in enumerate(b)]
    pick_t3 = key(0x12) + SELECT[len(key(0x10)):]
    cases = [("limit", ((0, (0x57, 0x56, 1)), (1, (0x57, 0x56, 1)))), ("limit-control", ((0, (0x57, 0x56, 1)),))]
    if rows - 5 >= 2:                                  # beside OCTA303 (remix wavecf-octa303)
        cases += [("limit-mixed", ((0, (0x54, 0x42, 1)), (1, (0x57, 0x56, 1)))), ("limit-mixed-control", ((0, (0x54, 0x42, 1)),))]
    for name, signed in cases:
        pokes = ";".join(x for t, b in signed for base in (PART, SHADOW) for x in sig(base, t, b))
        rd, log, d = run(name, card, image, [(0.5, f"poke {pokes}")] + pick_t3, extra=("--watch-pc", f"{NOTIFY:#x}"))
        assert "ended on quit" in log, f"{name}: the script did not finish"
        part, shadow = rd("part.bin"), rd("shadow.bin")
        hits = [l for l in log.splitlines() if l.startswith("watch-pc") and "hit(s)" in l]
        n = int(hits[0].split(":")[1].split()[0]) if hits else 0
        t3 = (part[0x3C + 60:0x3F + 60], shadow[0x3C + 60:0x3F + 60])
        if len(signed) == 2:
            assert t3 == (bytes(3), bytes(3)), (name, "T3 was signed past the limit", t3)
            assert n > 0, (name, "no toast: NOTIFY was not called")
            print(f"PASS {name}: two machines in the Part, T3 refused (no signature in either copy), toast called {n}x")
        else:
            assert t3 == (b"WV\x01", b"WV\x01"), (name, "control: T3 should be signed with one other machine", t3)
            print(f"PASS {name}: one other machine, T3 is signed")

    # 5. the validator unsigns a third signed track of a loaded Part
    pk = [x for t in (0, 1, 2) for x in sig(PART, t)]
    rd, log, _ = run("limit-validate", card, image, None,
                     (f"-:poke:{';'.join(pk)}", f"-:call:0x40002318,{PART:#x}", f"-:dump:{PART:#x},6322={OUT}/limit-validate/after.bin"))
    after = rd("after.bin")
    for t in (0, 1):
        assert after[0x3C + 30 * t:0x3F + 30 * t] == b"WV\x01", ("limit-validate", f"T{t + 1} lost its signature")
    assert after[0x3C + 60:0x3F + 60] == bytes(3), ("limit-validate", "T3 still signed", after[0x3C + 60:0x3F + 60])
    print("PASS limit-validate: the Part validator keeps the first two signed tracks and unsigns the third")

    if rows - 5 >= 2:
        pk = [x for t, b in ((0, (0x54, 0x42, 1)), (1, (0x57, 0x56, 1)), (2, (0x57, 0x56, 1))) for x in sig(PART, t, b)]
        rd, log, _ = run("limit-mixed-validate", card, image, None,
                         (f"-:poke:{';'.join(pk)}", f"-:call:0x40002318,{PART:#x}", f"-:dump:{PART:#x},6322={OUT}/limit-mixed-validate/after.bin"))
        after = rd("after.bin")
        assert after[0x3C:0x3F] == b"TB\x01" and after[0x3C + 30:0x3F + 30] == b"WV\x01", ("limit-mixed-validate", "a kept track lost its signature")
        assert after[0x3C + 60:0x3F + 60] == bytes(3), ("limit-mixed-validate", "T3 still signed", after[0x3C + 60:0x3F + 60])
        print("PASS limit-mixed-validate: T1 OCTA-303 and T2 WAVE kept, a third WAVE track unsigned")


if __name__ == "__main__":
    main()
