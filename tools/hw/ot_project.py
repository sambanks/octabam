#!/usr/bin/env python3
"""Read (and carefully write) Octatrack project/bank files on the CF card.

    python3 tools/hw/ot_project.py report PROJECT_DIR
    python3 tools/hw/ot_project.py set-gain PROJECT_DIR SLOT DB      # e.g. 12 -3.5
    python3 tools/hw/ot_project.py apply PROJECT_DIR PLAN.json       # {"12": -3.5, ...}
    python3 tools/hw/ot_project.py host PROJECT_DIR [REMIX]            # the locked rig: T1 BusDelay, T5 BusVerb, T8 stock DELAY, the rest SEND, then defaults
    python3 tools/hw/ot_project.py stamp-defaults PROJECT_DIR REMIX [--all] [--keep-mode]
        # replaced ids only (the stations); --all = every module of ours
        # including the engines (after a slot re-layout); --keep-mode keeps
        # an in-range MODE byte and applies that mode's ModeView defaults
    python3 tools/hw/ot_project.py stamp-slot PROJECT_DIR MODULE SLOT [VALUE] [--track N[,N]]
    python3 tools/hw/ot_project.py migrate-hosts PROJECT_DIR          # ONCE: a pre-image-71 project's host bytes, carried over
    python3 tools/hw/ot_project.py remap-slot PROJECT_DIR MODULE SLOT old:new,...   # ONCE: a select whose values changed order
    python3 tools/hw/ot_project.py set-fx PROJECT_DIR fx1|fx2 TRACK MODULE [--page V,V,V,V,V,V] [--page2 V,...]
    python3 tools/hw/ot_project.py thru-track PROJECT_DIR TRACK [--page HEX14]
    python3 tools/hw/ot_project.py stored PROJECT_DIR                  # .strd twins (the unit's saved state)
    python3 tools/hw/ot_project.py delaytest SRC_DIR DEST_DIR [SENDER]  # only the delay bus: T1 host, the rest SEND
    python3 tools/hw/ot_project.py clean SRC_DIR DEST_DIR              # a copy with FX1/FX2 = NONE everywhere, pages zero

Writes edit GAIN= lines only, preserve CRLF and byte length discipline of the
rest of the file, and refuse to run without a same-day backup directory
matching /Users/sambanks/octa/backups/*pregain*.
"""
import os
import json, pathlib, re, sys, glob

# ⚠️ EIGHT PART RECORDS, not four: 1-4 are the CURRENT parts and 5-8 are the
# SAVED copies the unit restores on RELOAD PART. Verified against
# 80 bank files -- parts 5-8 are byte-identical to 1-4 in every one of them,
# and part 9 lands in the name trailer (ASCII), so the count is exact. A tool
# that writes only the first four leaves an effect assignment one RELOAD away
# from coming back.
PART_BASE, PART_STRIDE, NPARTS, NPARTS_ALL = 0x8eed6, 0x18bb, 4, 8
FX1_OFF, FX2_OFF, NTRACKS = 0x009, 0x011, 8
P1_OFF, P2_OFF, TRACK_STRIDE = 0x12f, 0x331, 24     # RETRACTED for page 2, see below
P2_OFF, P2_STRIDE = 0x307, 30
FX_NAMES = {0x06: "BusDelay", 0x07: "BusVerb", 0x09: "SEND", 0x00: "-"}
SEND_ID = 0x09                    # FX2 id 0 (NONE) runs SEND's code (the image aliases it)

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

SLOT_OFF = 0x2d3                    # part-relative: track t's 5 slot bytes at +t*5 (SLOT_KIND)
MACHINES = {0: "STATIC", 1: "FLEX", 2: "THRU", 3: "NEIGHBOR", 4: "PICKUP"}


def track_map(pdir):
    """-> {(bank, part): [(track, mtype, slot_1based, path)]} for every bank
    file, parts 1-4 (the live copies). The slot is the machine's own kind
    (STATIC or FLEX); a THRU/NEIGHBOR/PICKUP track has none."""
    pdir = pathlib.Path(pdir)
    _, slots = read_project(pdir)
    by = {(sl["type"], sl["slot"]): sl["path"] for sl in slots}
    out = {}
    for bank in sorted(pdir.glob("bank*.work")):
        b = int(bank.name[4:6]); data = bank.read_bytes()
        for p in range(1, NPARTS + 1):
            base = PART_BASE + (p - 1) * PART_STRIDE
            rows = []
            for t in range(8):
                mt = data[base + MTYPE_OFF + t]
                kind = {0: "static", 1: "flex"}.get(mt)
                slot = data[base + SLOT_OFF + t * 5 + SLOT_KIND[kind]] + 1 if kind else None
                path = by.get((kind.upper(), slot), "") if kind else ""
                rows.append((t + 1, MACHINES.get(mt, str(mt)), slot, path))
            out[(b, p)] = rows
    return out


def cmd_tracks(pdir, grep=None):
    """Per bank and part, each track's machine, slot and sample file."""
    for (b, p), rows in track_map(pdir).items():
        for t, mt, slot, path in rows:
            name = path.split("/")[-1]
            if grep and grep.lower() not in name.lower():
                continue
            if mt in ("STATIC", "FLEX") and name:
                print(f"  {chr(64 + b)} part{p} T{t} {mt:6} slot {slot:3d}  {name}")
            elif not grep and mt not in ("STATIC", "FLEX"):
                print(f"  {chr(64 + b)} part{p} T{t} {mt}")


def clone_samples(src, dest, template, length=64, scale="1/4X"):
    """A fresh project (a copy of `template`, one the unit created on the
    running image, so its parts and pages are that image's defaults) that
    carries `src`'s sample slots and, in every bank and part (live and saved
    copies), each track's machine type and slot bytes, its project-local
    sample files with their .ot attribute files, MASTER_TRACK and TEMPOx24;
    every pattern's length/scale pair set.
    Nothing else of `src` comes across: no trigs,
    locks, knobs, levels, names or tempo -- those are the TEMPLATE's, so it
    must be an untouched fresh project (Bottleservice 26, 25 Sep 2026: the
    template had been a test project; its T1 trigs, hard-left BAL and WOW
    came across and were cleared by hand afterwards)."""
    import shutil
    src, dest, template = (pathlib.Path(x) for x in (src, dest, template))
    if dest.exists():
        sys.exit(f"{dest} exists -- refusing to overwrite")
    for d in (src, template):
        if not (d / "project.work").is_file():
            sys.exit(f"{d} is not an Octatrack project directory")
    shutil.copytree(template, dest)
    # the sample slots: src's [SAMPLE] blocks in place of the template's
    src_raw, src_slots = read_project(src)
    blocks = re.findall(r"\[SAMPLE\].*?\[/SAMPLE\]\r?\n", src_raw, re.S)
    for suffix in ("work", "strd"):
        f = dest / f"project.{suffix}"
        if not f.is_file():
            continue
        raw = f.read_bytes().decode("latin1")
        first = re.search(r"\[SAMPLE\]", raw)
        stripped = re.sub(r"\[SAMPLE\].*?\[/SAMPLE\]\r?\n", "", raw, flags=re.S)
        at = first.start() if first else len(stripped)
        # the strip moved everything after the first block up; recompute
        at = min(at, len(stripped))
        f.write_bytes((stripped[:at] + "".join(blocks) + stripped[at:]).encode("latin1"))
    print(f"{len(blocks)} sample slot(s) from {src.name} ({sum(1 for b in src_slots if b['path'])} with files)")
    # project-local samples (a bare file name, no directory) live in the
    # project's own folder: the unit reported 528 FILE NOT FOUND on the first
    # Bottleservice 26 (25 Sep 2026) for exactly these; pool paths
    # (../AUDIO/...) resolve from any project in the set. 8.3 aliases in a
    # path (RU4REA~7/RU4REA~2.WAV) are the unit's and the Mac cannot see them.
    local = sorted({b["path"] for b in src_slots if b["path"] and "/" not in b["path"]})
    nf = 0
    for name in local:
        for f in (name, pathlib.Path(name).with_suffix(".ot").name):
            # the .ot beside a sample holds its trim, loop, BPM and slices;
            # without it the unit plays default trims at a guessed BPM
            # (Bottleservice 26, 25 Sep 2026: "trimmed short, squealing")
            if (src / f).is_file() and not (dest / f).is_file():
                shutil.copyfile(src / f, dest / f); nf += 1
    print(f"{len(local)} project-local sample(s): {nf} file(s) copied (.wav and .ot)")
    # project-level settings that belong with the samples' layout
    for suffix in ("work", "strd"):
        f = dest / f"project.{suffix}"
        if f.is_file():
            raw = f.read_bytes()
            for key in ("MASTER_TRACK", "TEMPOx24"):        # the tempo the trims-in-bars were made at
                m = re.search(rb"%s=(\d+)" % key.encode(), src_raw.encode("latin1"))
                if m:
                    raw = re.sub(rb"%s=\d+" % key.encode(), key.encode() + b"=" + m.group(1), raw)
            f.write_bytes(raw)
    # machines and slots, every bank the template has
    if isinstance(scale, str):
        scale = SCALE_NAMES.index(scale.upper())
    for bank in sorted(dest.glob("bank*.work")):
        b = int(bank.name[4:6])
        sb = src / bank.name
        if not sb.is_file():
            print(f"  {bank.name}: not in {src.name}, left as the template's")
            continue
        sdata = sb.read_bytes()
        def mut(data, sdata=sdata):
            for p in range(NPARTS_ALL):
                base = PART_BASE + p * PART_STRIDE
                data[base + MTYPE_OFF:base + MTYPE_OFF + 8] = sdata[base + MTYPE_OFF:base + MTYPE_OFF + 8]
                data[base + SLOT_OFF:base + SLOT_OFF + 40] = sdata[base + SLOT_OFF:base + SLOT_OFF + 40]
            for pat in range(16):
                tail = PTRN0 + pat * PTRN_FSTRIDE + PTRN_FSTRIDE - 11
                data[tail + 2] = length; data[tail + 3] = scale
        _bank_write(dest, b, mut, guard=False)
    write_stored(dest)
    # the per-track pair too (ot_spec's "length"/"scale": what the unit shows
    # as 64/64 in per-track scale mode); the pattern pair above is the master
    import subprocess, tempfile
    spec = {"banks": "all", "patterns": {"all": {"tracks": {"all": {"length": length, "scale": SCALE_NAMES[scale]}}}}}
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(spec, f); specf = f.name
    r = subprocess.run([sys.executable, str(pathlib.Path(__file__).with_name("ot_spec.py")), "apply", str(dest), specf],
                       capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"ot_spec apply failed:\n{r.stdout[-800:]}{r.stderr[-800:]}")
    print(r.stdout.strip().splitlines()[-1])
    print(f"{dest}: machines + slots from {src.name}, every pattern and track LEN {length} SCALE {SCALE_NAMES[scale]}")


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
    again across all 80 bank files in the backup set -- every one
    agrees, so a disagreement is this tool's bug and not a format surprise.
    """
    if guard:
        guard_backup()
    for suffix in ("work", "strd"):
        path = pdir / f"bank{banknum:02d}.{suffix}"
        if suffix == "strd" and not path.is_file():
            continue
        data = bytearray(path.read_bytes())
        mutate(data)
        ck = sum(data[0x10:-2]) & 0xFFFF
        data[-2:] = ck.to_bytes(2, "big")
        path.write_bytes(bytes(data))

def set_master_track(pdir, on):
    """MASTER_TRACK=0|1 in project.work and project.strd, byte for byte
    otherwise: the line's CRLF and every other byte are kept (a text
    re-save of the file reads as PARSE ERROR on the unit). The project must
    be closed on the unit (it auto-saves). RETURNS (docs/proposals/
    RETURNS.md) sends the returns through T8 when this is on."""
    n = 0
    for name in ("project.work", "project.strd"):
        path = pdir / name
        if not path.exists():
            continue
        raw = path.read_bytes()
        key = b"\r\nMASTER_TRACK="
        i = raw.find(key)
        if i < 0 or raw.find(key, i + 1) >= 0:
            sys.exit(f"{path}: expected exactly one MASTER_TRACK line")
        j = i + len(key)
        if raw[j:j + 3] not in (b"0\r\n", b"1\r\n"):
            sys.exit(f"{path}: MASTER_TRACK value is {raw[j:j + 3]!r}, not 0/1")
        new = raw[:j] + (b"1" if on else b"0") + raw[j + 1:]
        if new != raw:
            path.write_bytes(new)
            n += 1
        print(f"{path}: MASTER_TRACK={1 if on else 0}")
    return n


def set_part_name(pdir, banknum, part, name):
    name = name.upper()[:6]
    def mut(data):
        off = len(data) - 2 - 4*7 + (part-1)*7
        field = name.encode("latin1") + b"\x00" * (7 - len(name))
        data[off:off+7] = field
    _bank_write(pdir, banknum, mut)
    print(f"bank{banknum:02d} part{part} name -> {name}")

SLOT_KIND = {"static": 0, "flex": 1, "pickup": 4}

def set_track_slot(pdir, banknum, part, track, slot_1based, kind="flex"):
    if not (1 <= part <= NPARTS_ALL and 1 <= track <= 8):
        sys.exit(f"track-slot: part {part} / track {track} must be 1-based")
    def mut(data):
        off = PART_BASE + (part-1)*PART_STRIDE + 0x2d3 + (track-1)*5 + SLOT_KIND[kind]
        data[off] = slot_1based - 1
    _bank_write(pdir, banknum, mut)
    print(f"bank{banknum:02d} part{part} T{track} {kind} slot -> {slot_1based}")

MTYPE_OFF, MTYPE_MIRROR = 0x02b, 4      # + track; part N's saved copy is part N+4

def set_machine_type(pdir, banknum, part, track, mtype, mirror=True, guard=True):
    """part and track are 1-BASED (part 1-4, track 1-8). A track of 0 wrote
    the byte BEFORE T1's (+0x2a, a run of 108s) in three fixtures on 7 Sep
    2026 and was only caught by a raw dump -- hence the check."""
    if not (1 <= part <= NPARTS and 1 <= track <= 8):
        sys.exit(f"machine-type: part {part} / track {track} must be 1-based (1-4 / 1-8)")
    parts = (part, part + MTYPE_MIRROR) if mirror else (part,)
    def mut(data):
        for p in parts:
            data[PART_BASE + (p-1)*PART_STRIDE + MTYPE_OFF + (track-1)] = mtype
    _bank_write(pdir, banknum, mut, guard=guard)
    print(f"bank{banknum:02d} part{','.join(str(p) for p in parts)} "
          f"T{track} machine type -> {mtype}")

PTRN0, PTRN_FSTRIDE, TRAC_FSTRIDE, NMASKS = 0x16, 0x8eec, 0x922, 8

def trac_off(pattern, track):
    """File offset of a pattern's track record DATA (0-based indices).

    ⚠️ The PTRN chunk's header is 8 bytes (tag+len) but a TRAC's is **9** --
    tag, length and one pad byte, the same +9 the PART records carry
    (PART_STRIDE 0x18bb = RAM's 0x18b2 + 9). Reading it as 8 shifts every
    mask one byte and is not obviously wrong: the masks still look like
    plausible trig patterns, and a step you set then lands eight steps away.
    ✅ Settled by loading a project through the real path and reading the RAM
    record back -- the file with +9 matches it byte for byte, +8 does not.
    """
    return PTRN0 + pattern*PTRN_FSTRIDE + 8 + track*TRAC_FSTRIDE + 9

def set_pattern_trig(pdir, banknum, pattern, track, step, mask=0x00, guard=True):
    """Set `step` (1-64) in one TRAC step mask, on disk."""
    def mut(data):
        off = trac_off(pattern, track) + mask + 7 - (step - 1) // 8
        data[off] |= 1 << ((step - 1) % 8)
    _bank_write(pdir, banknum, mut, guard=guard)
    print(f"bank{banknum:02d} pattern{pattern} T{track+1} mask {mask:#04x} "
          f"step {step} set")

SCALE_NAMES = ["2X", "3/2X", "1X", "3/4X", "1/2X", "1/4X", "1/8X"]   # index order INFERRED from two
                                                                     # values (2 = 1X, 5 = 1/4X)

def set_pattern_scale(pdir, banknum, pattern, length, scale, guard=True):
    """Set a pattern's LEN (1-64) and SCALE (index into SCALE_NAMES, or a
    name) in the SECOND of the two length/scale pairs at the PTRN chunk's
    tail (bytes -9/-8 of the chunk; the tail is len1 sc1 len2 sc2 flag 0 0
    0 0 tempo24). Measured (RTOS_FORK section 10.16.5): the
    RIG's A01 carried (0x40, 5) there and stepped at quarter rate; (0x10, 2)
    steps at 1x. The first pair and the flag byte are not understood."""
    if isinstance(scale, str):
        scale = SCALE_NAMES.index(scale.upper())
    def mut(data):
        tail = PTRN0 + pattern * PTRN_FSTRIDE + PTRN_FSTRIDE - 11
        data[tail + 2] = length; data[tail + 3] = scale
    _bank_write(pdir, banknum, mut, guard=guard)
    print(f"bank{banknum:02d} pattern{pattern} LEN {length} SCALE {SCALE_NAMES[scale]} (index {scale})")

REC_FIELDS = ["INAB", "INCD", "RLEN", "TRIG", "SRC3", "LOOP",
              "FIN", "FOUT", "AB", "QREC", "QPL", "CD"]   # descriptor order, RECORDER.md
REC_SETUP_OFF = 0x60b   # part-relative file offset of track 0's 12 recorder-setup bytes
                        # (RAM 0x8f382 vs the machine-type byte's 0x8eda2, + the +9 IFF shift)

def set_recorder_setup(pdir, banknum, part, track, field, value, guard=True):
    """Write one RECORDING SETUP byte for a track, in part `part` (1-4) AND
    its saved mirror (part+4). RLEN is stored raw: display 1..64 -> 0..63,
    MAX -> 64. Measured: the live page at 0x80000cf4 reads back
    these bytes verbatim ([1,1,64,0,0,1 | 0,0,0,255,255,0] for the RIG)."""
    fi = REC_FIELDS.index(field.upper())
    def mut(data):
        for pi in (part - 1, part - 1 + NPARTS):
            off = PART_BASE + pi * PART_STRIDE + REC_SETUP_OFF + track * 12 + fi
            data[off] = value & 0xFF
    _bank_write(pdir, banknum, mut, guard=guard)
    print(f"bank{banknum:02d} part {part}(+{part+NPARTS}) T{track+1} {field.upper()} = {value}")

def tempo24_of(bpm):
    """The UI setter's conversion (0x4009c7c4, measured): 24*whole + (23*tenths+4)//9."""
    whole = int(bpm); tenths = round((bpm - whole) * 10)
    return 24 * whole + (23 * tenths + 4) // 9

def set_tempo(pdir, bpm):
    """Set project.work's TEMPOx24 from a displayed BPM."""
    t = tempo24_of(float(bpm))
    for suffix in ("work", "strd"):            # both states: see _bank_write
        path = pdir / f"project.{suffix}"
        if suffix == "strd" and not path.is_file():
            continue
        raw = path.read_bytes().decode("latin1")
        new, k = re.subn(r"(TEMPOx24=)\d+", lambda m: m.group(1) + str(t), raw, count=1)
        if k != 1:
            sys.exit(f"TEMPOx24 not found in project.{suffix}")
        path.write_bytes(new.encode("latin1"))
    print(f"TEMPOx24={t} ({bpm} BPM)")

def pattern_masks(pdir, banknum):
    """Every non-zero step mask in the bank: {(pattern, track, mask): value}."""
    data = (pdir / f"bank{banknum:02d}.work").read_bytes()
    out = {}
    for pat in range(16):
        for trk in range(8):
            base = trac_off(pat, trk)
            for m in range(NMASKS):
                v = int.from_bytes(data[base + m*8:base + m*8 + 8], "big")
                if v:
                    out[(pat, trk, m*8)] = v
    return out

def pattern_diff(dir_a, dir_b, banknum):
    """Report every step-mask difference between two projects' banks.

    The intended use: save a project from the unit, add ONE trig of the type
    you are hunting, save it again under another name, and run this. The mask
    offset and the step fall out with no reverse engineering at all.
    """
    a, b = pattern_masks(pathlib.Path(dir_a), banknum), pattern_masks(pathlib.Path(dir_b), banknum)
    keys = sorted(set(a) | set(b))
    n = 0
    for k in keys:
        va, vb = a.get(k, 0), b.get(k, 0)
        if va != vb:
            n += 1
            pat, trk, mask = k
            steps = [i + 1 for i in range(64) if ((va ^ vb) >> i) & 1]
            print(f"pattern {pat:2d} T{trk+1} mask {mask:#04x}: "
                  f"{va:016x} -> {vb:016x}  steps {steps}")
    print(f"{n} mask(s) differ in bank{banknum:02d}")
    return n


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
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401  (every tools/ dir on sys.path)
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
    # silently returned the first one in the list. tools/build/cycle_count.py
    # already prices each engine, so ask it rather than approximate it.
    import json as _json, os as _os, subprocess as _sp
    root = pathlib.Path(__file__).resolve().parents[2]
    try:
        r = _sp.run([sys.executable, "tools/build/cycle_count.py", "--json"],
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


def module_defaults(m, knobs=None):
    """The 12 bytes a slot should hold for module `m`: its manifest defaults,
    then the ModeView defaults of the MODE those bytes (or `knobs`) select,
    then `knobs` again so an explicit value beats the view. This is what the
    remixer bench applies when MODE changes (schema.ModeView), so a stamped
    part and the bench agree by construction."""
    vals = [(p.default or 0) & 0x7f for p in m.params] + [0] * 12
    vals = vals[:12]
    kmap = m.knob_map_all() if not getattr(m, "is_stock", False) else {}
    knobs = knobs or {}

    def idx(n):                                  # a knob name, or a slot index
        if isinstance(n, int):
            return n
        if n not in kmap:
            sys.exit(f"{m.key} has no knob {n!r}")
        return kmap[n]
    for n, v in knobs.items():
        vals[idx(n)] = int(v) & 0x7f
    # A mode's view applies only when the MODE was CHOSEN (given in knobs):
    # the manifest defaults are the stamped default, and for a station they
    # are the bit-exact passthrough. Applying the default mode's view stamped
    # Modulation's CHOR at MIX 64 -- a chorus on T5 in every RIG project since
    # the mode-aware stamper -- measured on the 13 Sep ladder as
    # T5 -2.5 dB against the same track with no station (rung E vs F).
    if getattr(m, "mode_slot", None) is not None and m.mode_slot in {idx(n) for n in knobs}:
        view = next((mv for mv in m.mode_views if mv.mode == vals[m.mode_slot]), None)
        if view is not None:
            for slot, v in view.defaults.items():
                vals[slot] = int(v) & 0x7f
            for n, v in knobs.items():
                vals[idx(n)] = int(v) & 0x7f
    return bytes(vals)


def _remix_defaults(remix_name, replaced_only):
    """-> {fx id: 12 default bytes} for the modules this remix places.

    replaced_only=True limits it to modules that REPLACE a stock effect (the
    only ids whose stored bytes are in a foreign layout); False covers every
    module of ours, which is what a freshly stamped test project wants.
    """
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401  (every tools/ dir on sys.path)
    from remix import registry
    remix = registry.remix(remix_name)
    mods = registry.modules()
    out = {}
    for k in remix.modules:
        m = mods.get(k)
        if m is None or m.menu is None:
            continue
        # A stock row's stored bytes are its own on a real set, so
        # replaced_only leaves them alone; a FRESH project (replaced_only=
        # False) writes the stock effect's descriptor defaults too, so the
        # stock DELAY never boots on a foreign layout's bytes (its TAPE/LOCK
        # selects count 2 -- a stored 48 there is an index).
        if getattr(m, "is_stock", False) and replaced_only:
            continue
        if replaced_only and not m.menu.replaces:
            continue
        out[m.menu.fx2_id] = module_defaults(m)
    return out


def stamp_defaults(pdir, remix_name, replaced_only=True, guard=True, keep_mode=False):
    """Write our modules' manifest defaults into every part/track that names
    one of their ids. Returns the number of (part, track, slot) writes.

    keep_mode=True keeps a stored MODE byte that is within its select's count
    and applies that mode's ModeView defaults (a BusDelay in GRAIN keeps
    GRAIN and gets GRAIN's knobs). Off
    by default because a replaced id's stored bytes are the STOCK effect's
    layout, where the byte at the mode slot means something else entirely --
    use it on a part that has already been stamped or edited under ours."""
    pdir = pathlib.Path(pdir)
    defaults = _remix_defaults(remix_name, replaced_only)
    if not defaults:
        sys.exit(f"remix {remix_name!r} has no {'replacing ' if replaced_only else ''}modules to stamp")
    modes = {}
    if keep_mode:
        sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
        from remix import registry
        for m in registry.modules().values():
            if m.menu is not None and m.menu.fx2_id in defaults and getattr(m, "mode_slot", None) is not None:
                modes[m.menu.fx2_id] = (m, m.mode_slot, m.params[m.mode_slot].count or 128)
    total = 0
    for bank in sorted(pdir.glob("bank*.work")):
        num = int(bank.name[4:6])
        done = []

        # _bank_write runs mut() on .work AND its .strd twin, and with
        # --keep-mode the two can hold different MODE bytes, so each file's
        # writes are kept apart: a shared list made .work's read-back fail
        # against .strd's entries (OCTABAM89 bank03 part 2 T5, 16 Sep 2026).
        done_by = {}

        def mut(data):
            mine = done_by.setdefault(bytes(data[:0x10]) + len(done_by).to_bytes(1, "big"), [])
            for p in range(NPARTS_ALL):
                off = PART_BASE + p * PART_STRIDE
                for t in range(NTRACKS):
                    for idoff, sub in ((FX1_OFF, 0), (FX2_OFF, 6)):
                        fid = data[off + idoff + t]
                        # Id 0 (NONE, on either slot) is aliased to SEND in
                        # every image, so SEND's code runs on that slot with
                        # r6 on its stored page: stamp it with SEND's defaults
                        # (all zero). A stale slot-1 byte there was BURN on the
                        # burn image, 16 Sep 2026: step 1 forever.
                        if fid == 0 and SEND_ID in defaults:
                            fid = SEND_ID
                            if sub == 6:
                                # an FX2 stored as 0 gets no page from the
                                # firmware and SEND reads a stale DSP word (T5
                                # "loud with send 0", 16 Sep 2026): store SEND
                                data[off + idoff + t] = SEND_ID
                        if fid not in defaults:
                            continue
                        d = defaults[fid]
                        a = off + P1_OFF + t * TRACK_STRIDE + sub
                        b = off + P2_OFF + t * P2_STRIDE + sub
                        if fid in modes:
                            m, ms, cnt = modes[fid]
                            stored = data[b + ms - 6] if ms >= 6 else data[a + ms]
                            if stored < cnt:
                                d = module_defaults(m, {ms: stored})
                        data[a:a + 6] = d[:6]
                        data[b:b + 6] = d[6:]
                        mine.append((p, t, sub, fid, d))

        _bank_write(pdir, num, mut, guard=guard)
        # READ IT BACK, as testproj does: a write this tool cannot verify is
        # a write you find out about on the unit. Both files, each against
        # its own writes (mut ran on .work first, then .strd).
        files = [bank] + ([bank.with_suffix(".strd")] if bank.with_suffix(".strd").is_file() else [])
        for path, done in zip(files, done_by.values()):
            data = path.read_bytes()
            if int.from_bytes(data[-2:], "big") != (sum(data[0x10:-2]) & 0xFFFF):
                sys.exit(f"{path.name}: checksum did not take -- do NOT use this")
            for p, t, sub, fid, d in done:
                off = PART_BASE + p * PART_STRIDE
                a = off + P1_OFF + t * TRACK_STRIDE + sub
                b = off + P2_OFF + t * P2_STRIDE + sub
                if data[a:a + 6] + data[b:b + 6] != d:
                    sys.exit(f"{path.name} part {p+1} T{t+1}: read-back disagrees")
        done = next(iter(done_by.values()), [])
        total += len(done)
        if done:
            print(f"bank{num:02d}: {len(done)} slots stamped with our defaults")
    print(f"{total} slot(s) stamped for remix {remix_name!r} "
          f"({'replaced ids only' if replaced_only else 'every id of ours'})")
    for line in wrong_core(pdir):
        print(f"WARNING: {line}")
    return total


# Payload A serves tracks 5-8 and B tracks 1-4 (measured 10 Aug 2026); the
# manifests say which payload a module is placed in. An FX2 pick of a
# single-payload module on the other core runs as SEND under SPEC (the
# absent server's id aliases to SEND): nothing hangs, no engine runs.
PAYLOAD_TRACKS = {"A": range(4, 8), "B": range(0, 4)}
# A one-core module runs on its core's first track (the bus engines, locked
# there) unless named here: RETURNS runs on T8's FX2 (r7 == $6b00,
# docs/proposals/RETURNS.md) and does nothing anywhere else.
HOST_TRACK = {"RETURNS": 7}


def wrong_core(pdir):
    """Every (bank, part, track) whose FX2 names a module the other core
    carries -- one line each, for the stamp tools and the set gate."""
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
    from remix import registry
    single = {}
    for m in registry.modules().values():
        if m.menu is None or m.dsp is None or len(m.dsp.payloads) != 1:
            continue
        (pl,) = m.dsp.payloads
        single[m.menu.fx2_id] = (m.key, pl)
    out = []
    for bank in sorted(pathlib.Path(pdir).glob("bank*.work")):
        data = bank.read_bytes()
        for p in range(NPARTS_ALL):
            off = PART_BASE + p * PART_STRIDE
            for t in range(NTRACKS):
                hit = single.get(data[off + FX2_OFF + t])
                if hit is not None and t not in PAYLOAD_TRACKS[hit[1]]:
                    lo, hi = PAYLOAD_TRACKS[hit[1]][0] + 1, PAYLOAD_TRACKS[hit[1]][-1] + 1
                    out.append(f"{bank.name} part {p + 1} T{t + 1}: {hit[0]} runs as SEND "
                               f"there (payload {hit[1]} = T{lo}-T{hi})")
                elif hit is not None and t != HOST_TRACK.get(hit[0], PAYLOAD_TRACKS[hit[1]][0]):
                    # locked to the host slot (schema.Remix.locked, 22 Sep 2026)
                    host = HOST_TRACK.get(hit[0], PAYLOAD_TRACKS[hit[1]][0])
                    out.append(f"{bank.name} part {p + 1} T{t + 1}: {hit[0]} is a dry pass "
                               f"there (locked to T{host + 1})")
    return out


def _resolve_module(which):
    """A module by key ("REVERB SERVER"), name ("busverb") or fx id (0x07 /
    7) -> (fx id, Module or None). Names come from the registry, so a tool
    invocation never carries an id that could go stale."""
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401  (every tools/ dir on sys.path)
    from remix import registry
    mods = registry.modules()
    try:
        fx_id = int(str(which), 0)
        for m in mods.values():
            if m.menu is not None and m.menu.fx2_id == fx_id:
                return fx_id, m
        return fx_id, None
    except ValueError:
        pass
    w = str(which).upper()
    for k, m in mods.items():
        if m.menu is not None and (k.upper() == w or m.name.upper() == w):
            return m.menu.fx2_id, m
    sys.exit(f"no module named {which!r} (keys: "
             f"{', '.join(k for k, m in mods.items() if m.menu is not None)})")


def _resolve_slot(mod, slot):
    """Slot by index (0..11) or by the module's own knob name ("TONE")."""
    try:
        s = int(slot)
    except ValueError:
        if mod is None:
            sys.exit(f"slot {slot!r} needs a module with a manifest, not a bare id")
        names = [p.name.decode("latin1").upper() for p in mod.params]
        if str(slot).upper() not in names:
            sys.exit(f"{mod.key} has no knob {slot!r}; it has {' '.join(names)}")
        s = names.index(str(slot).upper())
    if not 0 <= s < 12:
        sys.exit("slot is 0..11")
    return s


def thru_track(pdir, track, page_hex="017f0000400000", guard=True):
    """Make `track` (1-based) a THRU machine that starts on play: machine
    type 2 in all eight part records of every bank, its THRU playback page
    (seven bytes at Part+0x8edaa + track*30 + 12), and a trig at step 1 in
    pattern 1 of every bank.

    ⚠ The THRU page written here is NOT sufficient to make the track pass
    input at load: the operative INAB byte the
    firmware reads is in the PART record at +0x3f (=1 for A+B), which this
    page-region write does not reach, and the amp gate must be held open too.
    The working recipe (tools/hw/hw_flash7.py) arms the THRU over CC, has the
    unit SAVE the part, then copies that saved part record wholesale. This
    function sets the machine type and a plausible page; treat the input
    routing as unproven until a saved part confirms it."""
    pdir = pathlib.Path(pdir); t = int(track) - 1
    if not 0 <= t < NTRACKS:
        sys.exit("track is 1..8")
    page = bytes.fromhex(page_hex)
    if len(page) != 7:
        sys.exit("--page is 7 bytes (14 hex digits)")
    pb = 0x8edaa - 0x8ed77                      # the PB page, relative to the part record
    for bank in sorted(pdir.glob("bank*.work")):
        num = int(bank.name[4:6])

        def mut(data):
            for p in range(NPARTS_ALL):
                off = PART_BASE + p * PART_STRIDE
                data[off + 0x2b + t] = 2
                data[off + pb + t * 30 + 12: off + pb + t * 30 + 12 + 7] = page
            base = trac_off(0, t) + 0x00 + 7    # pattern 1 (index 0), mask 0x00, step 1
            data[base] |= 1
        _bank_write(pdir, num, mut, guard=guard)
    print(f"T{t+1}: THRU (type 2) in {NPARTS_ALL} parts of every bank, page {page_hex}, trig at step 1 of pattern 1")


def set_fx(pdir, which_slot, track, which, page=None, page2=None, guard=True):
    """Put effect `which` (module key/name or fx id) on `track` (1-based) in
    the FX1 or FX2 slot of EVERY part record (all eight, current + saved) of
    EVERY bank, optionally with its page-1 / page-2 bytes. Every part because
    the part that PLAYS is not the part the load applies: `ot_emu`'s load
    applies bank 1 part 1 and its transport start re-applies the saved bank's
    pattern part (measured, git show 3ceba41:docs/history/COLDFIRE_PORT.md O9d) -- O9c's whole
    fixture round edited part 1 and measured a track whose FX2 was still SEND."""
    pdir = pathlib.Path(pdir)
    fx_id, mod = _resolve_module(which)
    idoff = {"fx1": FX1_OFF, "fx2": FX2_OFF}[which_slot.lower()]
    sub = 0 if which_slot.lower() == "fx1" else 6
    t = int(track) - 1
    if not 0 <= t < NTRACKS:
        sys.exit("track is 1..8")
    if page is not None and len(page) != 6 or page2 is not None and len(page2) != 6:
        sys.exit("--page/--page2 take exactly six values")
    banks = 0
    for bank in sorted(pdir.glob("bank*.work")):
        num = int(bank.name[4:6])

        def mut(data):
            for p in range(NPARTS_ALL):
                off = PART_BASE + p * PART_STRIDE
                data[off + idoff + t] = fx_id
                for s, v in enumerate(page or ()):
                    data[off + P1_OFF + t * TRACK_STRIDE + sub + s] = int(v) & 0x7f
                for s, v in enumerate(page2 or ()):
                    data[off + P2_OFF + t * P2_STRIDE + sub + s] = int(v) & 0x7f
        _bank_write(pdir, num, mut, guard=guard)
        data = bank.read_bytes()
        if int.from_bytes(data[-2:], "big") != (sum(data[0x10:-2]) & 0xFFFF):
            sys.exit(f"{bank.name}: checksum did not take -- do NOT use this")
        banks += 1
    label = mod.key if mod is not None else f"id 0x{fx_id:02x}"
    print(f"T{t+1} {which_slot.upper()} = {label} (0x{fx_id:02x}) in {NPARTS_ALL} parts x {banks} bank(s)"
          + (f", page 1 {list(page)}" if page else "") + (f", page 2 {list(page2)}" if page2 else ""))


def host_rig(pdir, remix_name, guard=True):
    """The locked rig's FX2 assignment in every part of every bank: T1 =
    DELAY SERVER, T5 = REVERB SERVER, T8 = the stock DELAY, every other
    track SEND; then the
    engines' and stations' defaults (stamp-defaults --all --keep-mode). The
    engines have no chooser row since image 52 (22 Sep 2026), so this is
    how a project comes to host them."""
    # T8: RETURNS in a remix that carries it (docs/proposals/RETURNS.md),
    # else the stock DELAY for its beat repeat
    from remix import registry
    t8 = "RETURNS" if remix_name and "RETURNS" in registry.remix(remix_name).modules else "DELAY"
    for t in range(1, NTRACKS + 1):
        set_fx(pdir, "fx2", t, {1: "DELAY SERVER", 5: "REVERB SERVER", 8: t8}.get(t, "SEND"), guard=guard)
    stamp_defaults(pdir, remix_name, replaced_only=False, guard=guard, keep_mode=True)


# Image 71's host layout (PR #441, 26 Sep 2026): the hosts' pages read like
# SEND's (DEL, REV), so three bytes per host track move. old -> new, per
# (FX2 id): the page-1 slot index or ("p2", page-2 slot) of each byte.
HOST_MIGRATION_441 = {
    0x06: (("p1", 1, "p2", 11),          # BusDelay TIME: slot 1 -> slot 11 (WOW dropped)
           ("zero", "p1", 1)),           # slot 1 is REV, the new send into the reverb
    0x07: (("p1", 1, "p2", 11),          # BusVerb TIME: slot 1 -> slot 11
           ("p1", 0, "p1", 1),           # its reverb send: slot 0 -> REV (slot 1)
           ("zero", "p1", 0)),           # slot 0 is DEL, the new send into the delay
}


def migrate_hosts_441(pdir, guard=True):
    """Carry a project saved under the old host layout into image 71's: every
    part and its saved copy, every track whose FX2 is BusDelay or BusVerb,
    each file moving its own bytes. Values are copied, never reset; the two
    new sends start at 0. RUN IT ONCE: a second run would move the moved
    bytes again (it cannot tell the layouts apart from the bytes)."""
    pdir = pathlib.Path(pdir)

    def addr(off, t, page, slot):
        return (off + P1_OFF + t * TRACK_STRIDE + 6 + slot if page == "p1"
                else off + P2_OFF + t * P2_STRIDE + 6 + slot - 6)

    total = 0
    for bank in sorted(pdir.glob("bank*.work")):
        num = int(bank.name[4:6])
        log = []

        def mut(data, log=log):
            rec = not log                              # log the .work pass (the first)
            for p in range(NPARTS_ALL):
                off = PART_BASE + p * PART_STRIDE
                for t in range(NTRACKS):
                    steps = HOST_MIGRATION_441.get(data[off + FX2_OFF + t])
                    if steps is None:
                        continue
                    old = bytes(data)                  # every move reads the pre-move bytes
                    for st in steps:
                        if st[0] == "zero":
                            a = addr(off, t, st[1], st[2])
                            if rec:
                                log.append((p, t, f"{st[1]} {st[2]}", old[a], 0))
                            data[a] = 0
                    for st in steps:
                        if st[0] != "zero":
                            src, dst = addr(off, t, st[0], st[1]), addr(off, t, st[2], st[3])
                            if rec:
                                log.append((p, t, f"{st[0]} {st[1]} -> {st[2]} {st[3]}", old[dst], old[src]))
                            data[dst] = old[src]

        _bank_write(pdir, num, mut, guard=guard)
        data = bank.read_bytes()
        if int.from_bytes(data[-2:], "big") != (sum(data[0x10:-2]) & 0xFFFF):
            sys.exit(f"{bank.name}: checksum did not take -- do NOT use this")
        for p, t, what, was, now in log:
            print(f"bank{num:02d} part {p+1} T{t+1} {what}: {was} -> {now}")
        total += len(log)
    print(f"{total} host byte(s) moved or zeroed (image 71 layout)")
    return total


def remap_slot(pdir, which, slot, mapping, guard=True):
    """Translate ONE knob byte through `mapping` ({old: new}) for every
    part/track naming the module (FX1 or FX2), in .work and .strd, for a
    select whose values changed order (26 Sep 2026: BusVerb SHFT
    +12/+19/+7/-12 -> -12/+5/+7/+12/+19/+24 is 0:3,1:4,2:2,3:0). A byte not in
    the mapping is left alone. RUN IT ONCE: a second run maps again."""
    pdir = pathlib.Path(pdir)
    fx_id, mod = _resolve_module(which)
    slot = _resolve_slot(mod, slot)
    total = 0
    for bank in sorted(pdir.glob("bank*.work")):
        num = int(bank.name[4:6])
        log = []

        def mut(data, log=log):
            rec = not log
            for p in range(NPARTS_ALL):
                off = PART_BASE + p * PART_STRIDE
                for t in range(NTRACKS):
                    for idoff, sub in ((FX1_OFF, 0), (FX2_OFF, 6)):
                        if data[off + idoff + t] != fx_id:
                            continue
                        a = (off + P1_OFF + t * TRACK_STRIDE + sub + slot if slot < 6
                             else off + P2_OFF + t * P2_STRIDE + sub + slot - 6)
                        new = mapping.get(data[a])
                        if new is None:
                            continue
                        if rec:
                            log.append((p, t, data[a], new))
                        data[a] = new

        _bank_write(pdir, num, mut, guard=guard)
        data = bank.read_bytes()
        if int.from_bytes(data[-2:], "big") != (sum(data[0x10:-2]) & 0xFFFF):
            sys.exit(f"{bank.name}: checksum did not take -- do NOT use this")
        for p, t, old, new in log:
            print(f"bank{num:02d} part {p+1} T{t+1} slot {slot}: {old} -> {new}")
        total += len(log)
    print(f"{total} byte(s) remapped")
    return total


def stamp_slot(pdir, which, slot, value=None, guard=True, tracks=None):
    """Write ONE knob byte for every part/track that names the module (FX2
    or FX1), leaving the other eleven alone. `which` is a module key, name
    or fx id; `slot` an index or the knob's manifest name; `value` defaults
    to the manifest default. For a slot whose MEANING changed (5 Sep 2026:
    BusVerb's LP -> -DEL, HP -> TONE; BusDelay's DRV -> -DEL): stamp-defaults
    keeps the engines' bytes deliberately ("Sam's knobs"), and re-stamping all
    twelve would throw those away. Page 1 is slot < 6. `tracks` (1-based,
    e.g. {8}) limits the stamp to those tracks -- the same module on another
    track keeps its byte."""
    pdir = pathlib.Path(pdir)
    fx_id, mod = _resolve_module(which)
    slot = _resolve_slot(mod, slot)
    # A stock entry resolves to a Module whose params carry no names (and a
    # bare id to none at all): neither has a manifest default or a knob name.
    named = (mod is not None and slot < len(mod.params)
             and isinstance(getattr(mod.params[slot], "name", None), (bytes, bytearray)))
    if value is None:
        if not named:
            sys.exit("a bare id / stock entry has no manifest default -- give the value")
        value = mod.params[slot].default or 0
    value = int(value) & 0x7f
    label = (f"{mod.key} {mod.params[slot].name.decode('latin1')}" if named
             else f"{mod.key if mod is not None else 'id'} 0x{fx_id:02x} slot {slot}")
    total = 0
    for bank in sorted(pdir.glob("bank*.work")):
        num = int(bank.name[4:6])
        done = []

        def mut(data):
            for p in range(NPARTS_ALL):
                off = PART_BASE + p * PART_STRIDE
                for t in range(NTRACKS):
                    if tracks is not None and (t + 1) not in tracks:
                        continue
                    for idoff, sub in ((FX1_OFF, 0), (FX2_OFF, 6)):
                        if data[off + idoff + t] != fx_id:
                            continue
                        if slot < 6:
                            a = off + P1_OFF + t * TRACK_STRIDE + sub + slot
                        else:
                            a = off + P2_OFF + t * P2_STRIDE + sub + slot - 6
                        done.append((p, t, a, data[a]))
                        data[a] = value

        # Dry run first: a bank that already holds the value is left alone
        # (no rewrite, no mtime churn -- the unit's save times stay honest).
        mut(bytearray(bank.read_bytes()))
        if all(old == value for _, _, _, old in done):
            if done:
                print(f"bank{num:02d}: {len(done)} slot(s) already {value}, untouched")
            continue
        # _bank_write runs mut over .work AND .strd, so `done` would carry
        # the saved copy's entries too; the read-back below is the .work
        # file's, so it checks the dry run's entries (14 Sep 2026: a .strd
        # whose part named SEND where .work did not made every stamp of
        # OCTABAM_F7TEST abort AFTER both files were written).
        done, dry = [], done
        _bank_write(pdir, num, mut, guard=guard)
        done = dry
        data = bank.read_bytes()
        if int.from_bytes(data[-2:], "big") != (sum(data[0x10:-2]) & 0xFFFF):
            sys.exit(f"{bank.name}: checksum did not take -- do NOT use this")
        for p, t, a, old in done:
            if data[a] != value:
                sys.exit(f"{bank.name} part {p+1} T{t+1}: read-back disagrees")
            print(f"bank{num:02d} part {p+1} T{t+1} {label} (id 0x{fx_id:02x} "
                  f"slot {slot}): {old} -> {value}")
        total += len(done)
    print(f"{total} byte(s) stamped ({label}, slot {slot} = {value}"
          + (f", tracks {sorted(tracks)}" if tracks else "") + ")")
    return total


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
    # And the knobs: every slot that now names one of our ids gets that
    # module's defaults, so no track boots holding another effect's bytes
    # (plan A6 -- the stored layout is the chosen effect's, not ours).
    stamp_defaults(dest, remix_name, replaced_only=False, guard=False)
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


# ---- the RIG project: the set's layout --------------------------------------
# One part = the whole rig on its eight tracks: stations on FX1 everywhere,
# the two engines in T1's and T5's FX2 (each prints its wet on its own track
# since 20 Sep 2026), a SEND on T2-T7, none on T8. A SEND's DEL and REV
# carry the same level: the old single send fed the delay, which passed the
# dry on to the reverb; the chain carries repeats only since 25 Sep 2026, so
# the dry reaches the reverb by REV. Every part of every bank
# gets the same layout, so any pattern is the rig. Knob bytes are the
# manifest defaults with the few deliberate exceptions listed per track.
RIG = (
    (1, ("CHARACTER", {}),                  ("DELAY SERVER", {"DEL": 30})),
    (2, ("SPECTRUM", {}),                   ("SEND", {"DEL": 40, "REV": 40})),
    (3, ("SPECTRUM", {}),                   ("SEND", {"DEL": 30, "REV": 30})),
    (4, ("SPECTRUM", {}),                   ("SEND", {"DEL": 40, "REV": 40})),
    (5, ("MODULATION", {}),                 ("REVERB SERVER", {"REV": 40})),
    (6, ("SPECTRUM", {}),                   ("SEND", {"DEL": 50, "REV": 50})),
    (7, ("SPECTRUM", {}),                   ("SEND", {"DEL": 40, "REV": 40})),    # SPECTRUM, not
    (8, ("CHARACTER", {"COMP": 40}),        (None, {})),   # GLUE by position (14 Sep 2026); no FX2: the SEND is refused on T8 (the master's input is the mix)
)


# ---- the three LFOs per track, in the part record ---------------------------
# octalab's part layout (docs/firmware/PARAM_PAGES.md 5g, RAM offsets; the
# file is +9): LFO page 1 = `+0x11a + track*24` = SPD1 SPD2 SPD3 DEP1 DEP2
# DEP3; `+0x2f2 + track*30` = PMTR1 PMTR2 PMTR3 WAVE1 WAVE2 WAVE3, the
# destination in the scene-byte numbering (16 = AMP BAL, 18..29 the effect
# pages). Read back against the panel: T6 LFO2 = AMP BAL,
# triangle, the bytes said pmtr 16 / wave 1 / spd 18 / dep 21.
LFO_P1_OFF, LFO_PM_OFF = 0x123, 0x2fb


def lfo_report(pdir, banks=None):
    pdir = pathlib.Path(pdir)
    for bank in sorted(pdir.glob("bank*.work")):
        num = int(bank.name[4:6])
        if banks and num not in banks:
            continue
        d = bank.read_bytes()
        for part in range(NPARTS):
            off = PART_BASE + part * PART_STRIDE
            rows = []
            for t in range(NTRACKS):
                p1 = d[off + LFO_P1_OFF + t * 24: off + LFO_P1_OFF + t * 24 + 6]
                pm = d[off + LFO_PM_OFF + t * 30: off + LFO_PM_OFF + t * 30 + 6]
                live = [(n + 1, p1[3 + n], pm[n], p1[n], pm[3 + n]) for n in range(3) if p1[3 + n]]
                if live:
                    rows.append(f"T{t + 1} " + " ".join(f"LFO{n}(dep {dep} pmtr {pmtr} spd {spd} wave {wv})"
                                                        for n, dep, pmtr, spd, wv in live))
            if rows:
                print(f"bank {chr(64 + num)} part {part + 1}: " + "; ".join(rows))


def lfo_clear(pdir, track, lfo, guard=True):
    """Zero LFO `lfo` (1-3) DEPTH on `track` (1-8) in every part record
    (current + saved) of every bank -- the bytes are the part's, so a free-
    running LFO nobody meant (T6 LFO2 on AMP BAL: a DC thump
    every cycle at idle) goes everywhere it was copied."""
    pdir = pathlib.Path(pdir)
    every = str(track) == "all"
    t, n = (0, 0) if every else (int(track) - 1, int(lfo) - 1)
    cells = [(tt, nn) for tt in range(NTRACKS) for nn in range(3)] if every else [(t, n)]
    for bank in sorted(pdir.glob("bank*.work")):
        num = int(bank.name[4:6])

        def mut(data):
            for p in range(NPARTS_ALL):
                off = PART_BASE + p * PART_STRIDE
                for tt, nn in cells:
                    data[off + LFO_P1_OFF + tt * 24 + 3 + nn] = 0
        _bank_write(pdir, num, mut, guard=guard)
        d = bank.read_bytes()
        if int.from_bytes(d[-2:], "big") != (sum(d[0x10:-2]) & 0xFFFF):
            sys.exit(f"{bank.name}: checksum did not take -- do NOT use this")
        for p in range(NPARTS_ALL):
            for tt, nn in cells:
                if d[PART_BASE + p * PART_STRIDE + LFO_P1_OFF + tt * 24 + 3 + nn] != 0:
                    sys.exit(f"{bank.name} part {p + 1}: read-back disagrees")
    print(f"{'every LFO' if every else f'T{track} LFO{lfo}'} depth -> 0 in every part of every bank of {pdir.name}")


def write_stored(pdir):
    """Give every .work file its .strd twin (a byte copy) where one is
    missing. A unit-saved project carries both, identical (RECTRIG,
    6 Sep 2026: bank01/project/arr01 .work == .strd); a project written by
    these tools carried .work only, and the unit showed it as modified with
    RELOAD refusing, there being no stored state to reload (OCTABAM89,
    15 Sep 2026). `_bank_write` keeps a .strd in step once it exists."""
    import shutil
    pdir = pathlib.Path(pdir)
    n = 0
    for w in sorted(pdir.glob("*.work")):
        t = w.with_suffix(".strd")
        if not t.is_file():
            shutil.copy2(w, t); n += 1
    print(f"{n} .strd file(s) written in {pdir}")
    return n


def make_clean_project(src, dest):
    """Copy a project and blank every effect: FX1 = NONE (id 0) and FX2 =
    SEND (id 9, the page all zero -- an FX2 stored as 0 gets no page from
    the firmware and SEND reads a stale word) on every track of every part
    of every bank, every page byte zero. Patterns,
    samples, mixer and the rest untouched. The image runs id 0 as SEND at
    level 0, so the bus carries nothing. A clean baseline for the ear
    (Sam, 16 Sep 2026: "so I can test it clean")."""
    import shutil
    src, dest = pathlib.Path(src), pathlib.Path(dest)
    if dest.exists():
        sys.exit(f"{dest} exists -- refusing to overwrite")
    shutil.copytree(src, dest)
    for bank in sorted(dest.glob("bank*.work")):
        num = int(bank.name[4:6])

        def mut(data):
            for p in range(NPARTS_ALL):
                off = PART_BASE + p * PART_STRIDE
                for i in range(NTRACKS):
                    data[off + FX1_OFF + i] = 0
                    data[off + FX2_OFF + i] = SEND_ID      # never 0: see stamp_defaults
                    a = off + P1_OFF + i * TRACK_STRIDE
                    b = off + P2_OFF + i * P2_STRIDE
                    data[a:a + 12] = bytes(12)
                    data[b:b + 12] = bytes(12)

        _bank_write(dest, num, mut, guard=False)
        for path in (bank, bank.with_suffix(".strd")):
            if not path.is_file():
                continue
            data = path.read_bytes()
            if int.from_bytes(data[-2:], "big") != (sum(data[0x10:-2]) & 0xFFFF):
                sys.exit(f"{path.name}: checksum did not take -- do NOT use this")
            for p in range(NPARTS_ALL):
                off = PART_BASE + p * PART_STRIDE
                if any(data[off + FX1_OFF:off + FX1_OFF + 8]) or any(x != SEND_ID for x in data[off + FX2_OFF:off + FX2_OFF + 8]):
                    sys.exit(f"{path.name} part {p+1}: an id survived")
                for i in range(NTRACKS):
                    a = off + P1_OFF + i * TRACK_STRIDE
                    b = off + P2_OFF + i * P2_STRIDE
                    if any(data[a:a + 12]) or any(data[b:b + 12]):
                        sys.exit(f"{path.name} part {p+1} T{i+1}: a page byte survived")
    write_stored(dest)
    print(f"{dest}: every FX1 = NONE, FX2 = SEND at 0, every page zero, in every part of every bank; .strd twins in step")


def make_delay_test_project(src, dest, remix_name, sender=3):
    """Copy a project (samples included) and put ONLY the delay bus in it:
    T1 = DELAY SERVER on FX2, every other track = SEND on FX2, FX1 = NONE
    everywhere with zeroed page bytes (id 0 runs SEND's proc on a stale
    slot-0 byte otherwise), every part of every bank. Track `sender` sends
    at 100, the rest at 0; no return station, so the delay's wet prints on
    T1's own output. Then the .strd twins."""
    import shutil
    src, dest = pathlib.Path(src), pathlib.Path(dest)
    if dest.exists():
        sys.exit(f"{dest} exists -- refusing to overwrite. Pick a new name.")
    if not (src / "project.work").is_file():
        sys.exit(f"{src} is not an Octatrack project directory")
    shutil.copytree(src, dest)
    for f in dest.glob("._*"):
        f.unlink()
    zeros = [0] * 6
    set_fx(dest, "fx1", 1, 0, page=zeros, page2=zeros, guard=False)
    # page 1: DEL REV FDBK TONE PING WET; page 2: MODE SCTR DENS SIZE PTCH TIME
    set_fx(dest, "fx2", 1, "DELAY SERVER", page=[0, 0, 60, 100, 0, 127], page2=[0, 0, 64, 1, 64, 40], guard=False)
    for t in range(2, 9):
        set_fx(dest, "fx1", t, 0, page=zeros, page2=zeros, guard=False)
        set_fx(dest, "fx2", t, "SEND", page=[100 if t == sender else 0, 0, 0, 0, 0, 0], page2=zeros, guard=False)
    write_stored(dest)
    print(f"delay test project -> {dest}: T1 DELAY SERVER, T2-T8 SEND (T{sender} at 100), FX1 NONE")


def make_rig_project(src, dest, remix_name):
    """Copy a project and write the RIG layout into every part of every bank:
    ids AND knob bytes, both current parts and their saved copies, checksums
    recomputed, everything read back."""
    import shutil
    src, dest = pathlib.Path(src), pathlib.Path(dest)
    if dest.exists():
        sys.exit(f"{dest} exists -- refusing to overwrite. Pick a new name.")
    if not (src / "project.work").is_file():
        sys.exit(f"{src} is not an Octatrack project directory")
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401  (every tools/ dir on sys.path)
    from remix import registry
    remix = registry.remix(remix_name)
    mods = registry.modules()

    def slot(spec):
        key, knobs = spec
        if key is None:
            return 0x00, bytes(12)
        m = mods[key]
        if key not in remix.modules:
            sys.exit(f"rig names {key!r}, which remix {remix_name!r} does not place")
        # manifest defaults, the chosen MODE's view, then the explicit knobs
        return m.menu.fx2_id, module_defaults(m, knobs)

    plan = [(t, slot(f1), slot(f2)) for t, f1, f2 in RIG]
    shutil.copytree(src, dest)
    for bank in sorted(dest.glob("bank*.work")):
        num = int(bank.name[4:6])

        def mut(data):
            for p in range(NPARTS_ALL):
                off = PART_BASE + p * PART_STRIDE
                for t, (id1, v1), (id2, v2) in plan:
                    i = t - 1
                    data[off + FX1_OFF + i] = id1
                    data[off + FX2_OFF + i] = id2
                    for sub, v in ((0, v1), (6, v2)):
                        a = off + P1_OFF + i * TRACK_STRIDE + sub
                        b = off + P2_OFF + i * P2_STRIDE + sub
                        data[a:a + 6] = v[:6]
                        data[b:b + 6] = v[6:]

        _bank_write(dest, num, mut, guard=False)
        data = bank.read_bytes()
        if int.from_bytes(data[-2:], "big") != (sum(data[0x10:-2]) & 0xFFFF):
            sys.exit(f"{bank.name}: checksum did not take -- do NOT use this")
        for p in range(NPARTS_ALL):
            off = PART_BASE + p * PART_STRIDE
            for t, (id1, v1), (id2, v2) in plan:
                i = t - 1
                got = (data[off + FX1_OFF + i], data[off + FX2_OFF + i],
                       bytes(data[off + P1_OFF + i*TRACK_STRIDE: off + P1_OFF + i*TRACK_STRIDE + 12]),
                       bytes(data[off + P2_OFF + i*P2_STRIDE: off + P2_OFF + i*P2_STRIDE + 12]))
                if got != (id1, id2, v1[:6] + v2[:6], v1[6:] + v2[6:]):
                    sys.exit(f"{bank.name} part {p+1} T{t}: read-back disagrees")
    lines = [f"# RIG project for remix {remix_name!r} -- every part of every bank is this:",
             f"# copied from {src}", ""]
    for t, f1, f2 in RIG:
        lines.append(f"T{t}  FX1 {f1[0] or '-':20s} {f1[1]}   FX2 {f2[0] or '-':20s} {f2[1]}")
    lines += ["", "ONE AUX: every track's SEND feeds the delay (T1), then the reverb (T5);",
              "T1 prints the repeats and T5 the tail under their own dry (20 Sep 2026).",
              "T8 has no FX2: the SEND is refused there (the master's input is the mix,",
              "the hosts' wet included). The stations have no sends."]
    (dest / "OCTABAM_RIG_MAP.txt").write_text("\n".join(lines) + "\n")
    print(f"{len(list(dest.glob('bank*.work')))} banks written and verified -> {dest}")
    print(f"map at {dest / 'OCTABAM_RIG_MAP.txt'}")


if __name__ == "__main__":
    cmd = sys.argv[1]; pdir = pathlib.Path(sys.argv[2])
    if cmd == "report": cmd_report(pdir)
    elif cmd == "tracks": cmd_tracks(pdir, sys.argv[3] if len(sys.argv) > 3 else None)
    elif cmd == "clone-samples":
        # clone-samples SRC DEST TEMPLATE [LEN [SCALE]]
        clone_samples(sys.argv[2], sys.argv[3], sys.argv[4],
                      int(sys.argv[5]) if len(sys.argv) > 5 else 64,
                      sys.argv[6] if len(sys.argv) > 6 else "1/4X")
    elif cmd == "set-gain": apply_gains(pdir, {sys.argv[3]: sys.argv[4]})
    elif cmd == "apply": apply_gains(pdir, json.loads(pathlib.Path(sys.argv[3]).read_text()))
    elif cmd == "part-name": set_part_name(pdir, int(sys.argv[3]), int(sys.argv[4]), sys.argv[5])
    elif cmd == "master-track":                                             # <project> on|off
        set_master_track(pdir, {"on": True, "off": False}[sys.argv[3]])
    elif cmd == "track-slot":
        # <project> <bank> <part> <track> <slot_1based> [flex|static|pickup]  (default flex)
        set_track_slot(pdir, int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6]),
                       sys.argv[7] if len(sys.argv) > 7 else "flex")
    elif cmd == "pattern-trig":
        # <project> <bank> <pattern> <track0> <step> [mask]
        set_pattern_trig(pdir, int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]),
                         int(sys.argv[6]),
                         int(sys.argv[7], 0) if len(sys.argv) > 7 else 0x00)
    elif cmd == "pattern-scale":
        # <project> <bank> <pattern> <len 1-64> <scale index or name: 2X 3/2X 1X 3/4X 1/2X 1/4X 1/8X>
        sc = sys.argv[6]
        set_pattern_scale(pdir, int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]),
                          int(sc) if sc.isdigit() else sc)
    elif cmd == "pattern-diff":
        # <projectA> <projectB> <bank>
        pattern_diff(sys.argv[2], sys.argv[3], int(sys.argv[4]))
    elif cmd == "recorder-setup":
        # <project> <bank> <part> <track0> <FIELD> <value>  (RLEN raw: display-1, MAX=64)
        set_recorder_setup(pdir, int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), sys.argv[6], int(sys.argv[7], 0))
    elif cmd == "set-tempo":
        # <project> <bpm>   (TEMPOx24 via the measured UI conversion)
        set_tempo(pdir, sys.argv[3])
    elif cmd == "machine-type":
        # <project> <bank> <part> <track> <type>; writes the part's saved
        # mirror too, the way a bank's eight PART records require
        set_machine_type(pdir, int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6]))
    elif cmd == "testproj": make_test_project(sys.argv[2], sys.argv[3], sys.argv[4])
    elif cmd == "rigproj": make_rig_project(sys.argv[2], sys.argv[3], sys.argv[4]); write_stored(sys.argv[3])
    elif cmd == "stored": write_stored(pdir)                                # .strd twins for every .work
    elif cmd == "clean": make_clean_project(sys.argv[2], sys.argv[3])       # <src> <dest>: no effects anywhere
    elif cmd == "delaytest":                                                # <src> <dest> [sender track]
        make_delay_test_project(sys.argv[2], sys.argv[3], sender=int(sys.argv[4]) if len(sys.argv) > 4 else 3)
    elif cmd == "lfo": lfo_report(pdir)                                      # every live LFO, per part
    elif cmd == "lfo-clear":                                                # <project> <track> <lfo> | <project> all
        lfo_clear(pdir, sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else 0, guard=False)
    elif cmd == "host":                                                     # <project> [remix]: T1 BusDelay, T5 BusVerb, the rest SEND, then defaults
        host_rig(pdir, sys.argv[3] if len(sys.argv) > 3 and not sys.argv[3].startswith("--") else os.environ.get("REMIX"),
                 guard="--no-guard" not in sys.argv)
    elif cmd == "stamp-defaults":
        args = sys.argv[4:]
        stamp_defaults(pdir, sys.argv[3], replaced_only="--all" not in args,
                       keep_mode="--keep-mode" in args)
    elif cmd == "thru-track":
        args = sys.argv[4:]
        page = args[args.index("--page") + 1] if "--page" in args else "00017f00000000"
        thru_track(pdir, int(sys.argv[3]), page, guard="--no-guard" not in args)
    elif cmd == "set-fx":
        args = sys.argv[3:]
        page = page2 = None
        if "--page" in args:
            page = [int(x) for x in args[args.index("--page") + 1].split(",")]
        if "--page2" in args:
            page2 = [int(x) for x in args[args.index("--page2") + 1].split(",")]
        pos = [a for i, a in enumerate(args) if not a.startswith("--") and (i == 0 or not args[i - 1].startswith("--"))]
        set_fx(pdir, pos[0], pos[1], pos[2], page=page, page2=page2, guard="--no-guard" not in args)
    elif cmd == "stamp-slot":
        # one knob byte, every part/track naming that module: for a slot
        # whose meaning changed. Module by key/name/id, slot by name/index,
        # value optional (manifest default). e.g.
        #   stamp-slot PROJ "REVERB SERVER" TONE      -> 64, from the manifest
        #   stamp-slot PROJ busdelay TIME 20
        #   stamp-slot PROJ character COMP 40 --track 8   (the master only)
        args = sys.argv[3:]
        tracks = None
        if "--track" in args:
            i = args.index("--track")
            tracks = {int(x) for x in args[i + 1].split(",")}
            del args[i:i + 2]
        stamp_slot(pdir, args[0], args[1], args[2] if len(args) > 2 else None,
                   tracks=tracks)
    elif cmd == "remap-slot":                                              # <project> MODULE SLOT old:new,...  ONCE
        remap_slot(pdir, sys.argv[3], sys.argv[4],
                   {int(a): int(b) for a, b in (x.split(":") for x in sys.argv[5].split(","))},
                   guard=False)
    elif cmd == "migrate-hosts":                                          # <project>: ONCE, old host layout -> image 71's
        migrate_hosts_441(pdir, guard=False)
    else: sys.exit(f"unknown command {cmd!r}")
