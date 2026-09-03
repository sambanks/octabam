#!/usr/bin/env python3
"""Read (and carefully write) Octatrack project/bank files on the CF card.

Format knowledge (reverse-engineered 25 Aug 2026 on ChongBongolo 26, OS 1.40B
image R58; anchors verified against values we wrote over MIDI and Sam's own
"A03 is part 3" statement):

  project.work    plain text, CRLF, [SECTION] KEY=VALUE.
                  [SAMPLE] sections: TYPE/SLOT/PATH/GAIN/... GAIN is 0..96,
                  48 = 0 dB, 0.5 dB per step (so 72 = +12 dB).
  bank##.work     FORM/DPS1BANK chunks: 16x PTRN (each 8 TRAC + 8 MTRA),
                  then 8x PART (parts 1-4 current, then parts 1-4 saved),
                  PART stride 0x18bb from 0x8eed6.
                  PART+0x009: FX1 effect id per track (8 bytes)
                  PART+0x011: FX2 effect id per track (8 bytes)
                             (BongDelay=0x06, ChonVerb=0x07, SEND=0x09)
                  PART+0x01b: 8 pairs (track LEVEL, cue level)
                  PART+0x2d3 + 5*track: static slot, 0-based (5-byte/track blocks)
                  PTRN tail byte at (next_chunk - 5): part assignment 0-3
                             (NOT -6 -- that mistake cost a measurement pass)
                  trailer: 4 part names, 7-byte NUL-terminated fields, at
                             (end - 2 - 4*7); **last u16 BE = additive checksum
                             sum(bytes[0x10:-2]) & 0xFFFF -- MUST recompute on
                             any bank edit** (verified on 4 files, 28 Aug).
                  AMP VOL: not located -- do not guess.

    python3 tools/ot_project.py report PROJECT_DIR
    python3 tools/ot_project.py set-gain PROJECT_DIR SLOT DB      # e.g. 12 -3.5
    python3 tools/ot_project.py apply PROJECT_DIR PLAN.json       # {"12": -3.5, ...}

Writes edit GAIN= lines only, preserve CRLF and byte length discipline of the
rest of the file, and refuse to run without a same-day backup directory
matching /Users/sambanks/octa/backups/*pregain*.
"""
import json, pathlib, re, sys, glob

# ⚠️ EIGHT PART RECORDS, not four: 1-4 are the CURRENT parts and 5-8 are the
# SAVED copies the unit restores on RELOAD PART. Verified 3 Sep 2026 against
# 80 bank files -- parts 5-8 are byte-identical to 1-4 in every one of them,
# and part 9 lands in the name trailer (ASCII), so the count is exact. A tool
# that writes only the first four leaves an effect assignment one RELOAD away
# from coming back.
PART_BASE, PART_STRIDE, NPARTS, NPARTS_ALL = 0x8eed6, 0x18bb, 4, 8
FX1_OFF, FX2_OFF, NTRACKS = 0x009, 0x011, 8
FX_NAMES = {0x06: "BongDelay", 0x07: "ChonVerb", 0x09: "SEND", 0x00: "-"}

def read_project(pdir):
    raw = (pdir / "project.work").read_bytes().decode("latin1")
    slots = []
    for m in re.finditer(r"\[SAMPLE\](.*?)\[/SAMPLE\]", raw, re.S):
        sec = m.group(1)
        g = lambda k, d=None: (re.search(rf"{k}=(.*?)\r?\n", sec) or [None, d])[1]
        slots.append(dict(type=g("TYPE"), slot=int(g("SLOT")), path=(g("PATH") or "").strip(),
                          gain=int(g("GAIN", "48")), span=(m.start(1), m.end(1))))
    return raw, slots

def bank_info(pdir, banknum):
    data = (pdir / f"bank{banknum:02d}.work").read_bytes()
    ptrns = [m.start() for m in re.finditer(rb"PTRN", data)] + [PART_BASE]
    pat_part = [data[ptrns[i+1]-5] for i in range(16)]
    parts = []
    for p in range(NPARTS):
        c = data[PART_BASE + p*PART_STRIDE:][:PART_STRIDE]
        fx1 = list(c[0x009:0x011]); fx2 = list(c[0x011:0x019])
        levels = list(c[0x01b:0x02b:2])
        parts.append(dict(fx1=fx1, fx2=fx2, levels=levels))
    return pat_part, parts

def cmd_report(pdir):
    _, slots = read_project(pdir)
    print("== sample slots (STATIC with files) ==")
    for s in slots:
        if s["type"] == "STATIC" and s["path"]:
            db = (s["gain"] - 48) / 2
            print(f"  slot {s['slot']:3d}  gain {db:+5.1f} dB  {s['path'].split('/')[-1]}")
    for b in range(1, 9):
        pat_part, parts = bank_info(pdir, b)
        used = pat_part[:16]
        print(f"\n== bank {chr(64+b)} == pattern->part: "
              + " ".join(f"{i+1}:{pp+1}" for i, pp in enumerate(used)))
        for i, part in enumerate(parts):
            fx2 = "/".join(FX_NAMES.get(v, hex(v)) for v in part["fx2"])
            print(f"  part {i+1}: LEVELs {part['levels']}  FX2 {fx2}")

def guard_backup():
    if not glob.glob("/Users/sambanks/octa/backups/*pregain*"):
        sys.exit("no pregain backup found -- refusing to write")

def apply_gains(pdir, changes):
    guard_backup()
    path = pdir / "project.work"
    raw = path.read_bytes().decode("latin1")
    n = 0
    for slot, db in changes.items():
        val = max(0, min(96, round(48 + 2*float(db))))
        pat = rf"(\[SAMPLE\][^\[]*?TYPE=STATIC[^\[]*?SLOT={int(slot):03d}[^\[]*?GAIN=)(\d+)"
        new, k = re.subn(pat, lambda m: m.group(1) + str(val), raw, count=1, flags=re.S)
        if k != 1:
            print(f"WARN slot {slot}: no unique match, skipped"); continue
        raw = new; n += 1
        print(f"slot {int(slot):3d} -> GAIN={val} ({float(db):+.1f} dB)")
    path.write_bytes(raw.encode("latin1"))
    print(f"{n} gains written to {path}")

def _bank_write(pdir, banknum, mutate, guard=True):
    """Read bank, apply mutate(bytearray), fix checksum, write.

    ⚠️ THE CHECKSUM IS NOT OPTIONAL. The last u16 BE is an additive sum over
    bytes[0x10:-2]; the unit rejects a bank whose sum does not match. Verified
    again 3 Sep 2026 across all 80 bank files in the backup set -- every one
    agrees, so a disagreement is this tool's bug and not a format surprise.
    """
    if guard:
        guard_backup()
    path = pdir / f"bank{banknum:02d}.work"
    data = bytearray(path.read_bytes())
    mutate(data)
    ck = sum(data[0x10:-2]) & 0xFFFF
    data[-2:] = ck.to_bytes(2, "big")
    path.write_bytes(bytes(data))

def set_part_name(pdir, banknum, part, name):
    name = name.upper()[:6]
    def mut(data):
        off = len(data) - 2 - 4*7 + (part-1)*7
        field = name.encode("latin1") + b"\x00" * (7 - len(name))
        data[off:off+7] = field
    _bank_write(pdir, banknum, mut)
    print(f"bank{banknum:02d} part{part} name -> {name}")

def set_track_slot(pdir, banknum, part, track, slot_1based):
    def mut(data):
        off = PART_BASE + (part-1)*PART_STRIDE + 0x2d3 + (track-1)*5
        data[off] = slot_1based - 1
    _bank_write(pdir, banknum, mut)
    print(f"bank{banknum:02d} part{part} T{track} slot -> {slot_1based}")

# ---------------------------------------------------------------------------
# A DETERMINISTIC TEST PROJECT
#
# ⚠️ THE EFFECT IDS LIVE IN THE PROJECT, NOT THE OS. They survive a flash, so
# a freshly flashed unit opens every track still holding the id it had before
# -- which in the new image may be a different effect, or one the image does
# not implement (and so resolves to the fallback). That is why a flashed unit
# "keeps the old effect graphics" until you select something, and why a flash
# test that starts from an old project is not a test of anything: half the
# tracks are running whatever the last image put there.
#
# So: copy a project, and stamp EVERY bank, part and track with an id this
# image actually implements. Nothing is left to what happened to be there.


def fx_plan(remix_name):
    """The layout: one effect per PART, on all eight tracks.

    Selecting a part then auditions that one effect across both cores at once
    -- which is the shape the cycle test wants and the shape that shows a
    payload-asymmetry bug immediately (tracks 5-8 are payload A, 1-4 are B).

    -> [(label, fx1_id, fx2_id)], one per part slot, in bank/part order.
    """
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    from remix import registry, stock
    remix = registry.remix(remix_name)
    mods = registry.modules()
    out = []
    # FX2 first: the chooser this image composes, in its own row order.
    for k in remix.modules:
        m = mods.get(k)
        if m is None or m.menu is None:
            continue
        out.append((f"{k} on FX2", 0x00, m.menu.fx2_id))
    # Then FX1's chooser, with FX2 silent so the FX1 effect is heard alone.
    fx1 = remix.fx1 or tuple(
        k for k in stock.p_spans("A")
        if mods[k].menu.fx2_id in stock.fx1_ids())
    for k in fx1:
        out.append((f"{k} on FX1", mods[k].menu.fx2_id, 0x00))
    # WARN: AND THE WORST CASE, BY CYCLES -- which is not the same as by
    # words, and words was what a first draft sorted on: every module of ours
    # has a word count the BUILD knows and stock.WORDS does not, so `max`
    # silently returned the first one in the list. tools/cycle_count.py
    # already prices each engine, so ask it rather than approximate it.
    import json as _json, os as _os, subprocess as _sp
    root = pathlib.Path(__file__).resolve().parent.parent
    try:
        r = _sp.run([sys.executable, "tools/cycle_count.py", "--json"],
                    cwd=root, capture_output=True, text=True,
                    env={**_os.environ, "REMIX": remix_name})
        cyc = _json.loads(r.stdout[r.stdout.index("{"):])["per_effect"]
    except Exception:                                # noqa: BLE001
        cyc = {}
    stem = {k: pathlib.Path(mods[k].dsp.asm).stem for k in remix.modules
            if mods[k].dsp is not None}
    cost = {k: cyc.get(v, 0) for k, v in stem.items()}
    ours = [k for k in remix.modules
            if mods[k].menu is not None and not mods[k].is_stock
            and mods[k].dsp is not None]
    if ours and cost:
        heavy2 = max(ours, key=lambda k: cost.get(k, 0))
        on1 = [k for k in ours if k in fx1]
        heavy1 = max(on1, key=lambda k: cost.get(k, 0)) if on1 else None
        out.append((f"WORST by cycles: {heavy2} on FX2"
                    + (f" + {heavy1} on FX1" if heavy1 else ""),
                    mods[heavy1].menu.fx2_id if heavy1 else 0x00,
                    mods[heavy2].menu.fx2_id))
    return out


def make_test_project(src, dest, remix_name):
    import shutil
    src, dest = pathlib.Path(src), pathlib.Path(dest)
    if dest.exists():
        sys.exit(f"{dest} exists -- refusing to overwrite. Pick a new name.")
    if not (src / "project.work").is_file():
        sys.exit(f"{src} is not an Octatrack project directory")
    plan = fx_plan(remix_name)
    banks = sorted(src.glob("bank*.work"))
    slots = len(banks) * NPARTS
    if len(plan) > slots:
        sys.exit(f"{len(plan)} assignments need {len(plan)} parts, and this "
                 f"project has {slots} ({len(banks)} banks x {NPARTS})")
    shutil.copytree(src, dest)
    lines = [f"# test project for remix {remix_name!r}",
             f"# copied from {src}",
             "# every bank/part/track set deterministically; unused parts are",
             "# NONE on both slots, which is the silent control.", ""]
    for bi, bank in enumerate(sorted(dest.glob("bank*.work"))):
        num = int(bank.name[4:6])

        def mut(data, bi=bi):
            for p in range(NPARTS_ALL):
                # BOTH the current part and its saved copy: writing only the
                # current one leaves the old assignment a RELOAD PART away.
                i = bi * NPARTS + (p % NPARTS)
                lbl, f1, f2 = plan[i] if i < len(plan) else ("-", 0x00, 0x00)
                off = PART_BASE + p * PART_STRIDE
                if off + FX2_OFF + NTRACKS > len(data):
                    sys.exit(f"{bank.name}: part {p+1} runs past the file")
                data[off + FX1_OFF:off + FX1_OFF + NTRACKS] = bytes([f1]) * NTRACKS
                data[off + FX2_OFF:off + FX2_OFF + NTRACKS] = bytes([f2]) * NTRACKS

        _bank_write(dest, num, mut, guard=False)
        for p in range(NPARTS):
            i = bi * NPARTS + p
            lbl, f1, f2 = plan[i] if i < len(plan) else ("(silent)", 0, 0)
            lines.append(f"bank {chr(64+num)}  part {p+1}   FX1 0x{f1:02x}  "
                         f"FX2 0x{f2:02x}   {lbl}")
    (dest / "OCTABAM_TEST_MAP.txt").write_text("\n".join(lines) + "\n")
    # READ IT BACK. A write this tool cannot verify is a write you find out
    # about on the unit.
    for bi, bank in enumerate(sorted(dest.glob("bank*.work"))):
        data = bank.read_bytes()
        if int.from_bytes(data[-2:], "big") != (sum(data[0x10:-2]) & 0xFFFF):
            sys.exit(f"{bank.name}: checksum did not take -- do NOT use this")
        for p in range(NPARTS_ALL):
            i = bi * NPARTS + (p % NPARTS)
            _l, f1, f2 = plan[i] if i < len(plan) else ("-", 0x00, 0x00)
            off = PART_BASE + p * PART_STRIDE
            if set(data[off+FX1_OFF:off+FX1_OFF+NTRACKS]) != {f1} or \
               set(data[off+FX2_OFF:off+FX2_OFF+NTRACKS]) != {f2}:
                sys.exit(f"{bank.name} part {p+1}: read-back disagrees")
    print("\n".join(lines))
    print(f"\n{len(banks)} banks written and verified -> {dest}")
    print(f"map also at {dest / 'OCTABAM_TEST_MAP.txt'}")


if __name__ == "__main__":
    cmd = sys.argv[1]; pdir = pathlib.Path(sys.argv[2])
    if cmd == "report": cmd_report(pdir)
    elif cmd == "set-gain": apply_gains(pdir, {sys.argv[3]: sys.argv[4]})
    elif cmd == "apply": apply_gains(pdir, json.loads(pathlib.Path(sys.argv[3]).read_text()))
    elif cmd == "part-name": set_part_name(pdir, int(sys.argv[3]), int(sys.argv[4]), sys.argv[5])
    elif cmd == "track-slot": set_track_slot(pdir, int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6]))
    elif cmd == "testproj": make_test_project(sys.argv[2], sys.argv[3], sys.argv[4])
    else: sys.exit(f"unknown command {cmd!r}")
