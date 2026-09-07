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
                             (BusDelay=0x06, BusVerb=0x07, SEND=0x09)
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
    python3 tools/ot_project.py stamp-defaults PROJECT_DIR REMIX  # station ids only
    python3 tools/ot_project.py stamp-slot PROJECT_DIR MODULE SLOT [VALUE] [--track N[,N]]
        # one knob byte on every part/track naming MODULE (key, name or id);
        # SLOT by manifest name or index; VALUE defaults to the manifest's

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
# THE KNOB VALUES a part stores for each track's two effects (found 3 Sep
# 2026 by pattern, against the ChongBongolo26 backups: stock FILTER's page-1
# defaults 00 7f 00 40 00 40 recur at a 24-byte stride on the tracks whose
# FX1 id is 0x04, and BusVerb's stored page 2 reads back as EXACTLY its
# manifest defaults 00 02 40 00 00 01). Two arrays of eight 24-byte blocks,
# one per track: bytes 0-5 are FX1's six knobs, 6-11 FX2's, 12-23 belong to
# two other pages. Page 1 at P1_OFF, page 2 (slots 6-11, a select stored as
# its index) at P2_OFF. Both relative to the part record.
#
# ⚠️ WHY THIS MATTERS (plan item A6): the bytes are stored under the layout
# of whatever effect the part chose. A station that REPLACES a stock effect
# inherits them raw -- FILTER's DEC=64 on slot 5 becomes ->VRB 64 on every
# melodic track, i.e. a part that never sent anything is suddenly a reverb
# client after the flash. stamp_defaults() writes OUR defaults over them.
P1_OFF, P2_OFF, TRACK_STRIDE = 0x12f, 0x331, 24     # RETRACTED for page 2, see below
# ❌ 4 Sep 2026, found on the flash-4 unit: PAGE 2 IS NOT 24 BYTES PER TRACK.
# Its per-track block is THIRTY bytes -- six FX1 page-2 bytes, six FX2, then
# eighteen that belong to other pages -- and it starts at +0x325, not +0x331.
# Measured on a part the UNIT had written (every track FILTER + DELAY, the
# effects re-selected on the panel): under a 30-byte stride from 0x307, ALL
# EIGHT tracks read FILTER's page-2 descriptor defaults (00 00 01 00 03 00)
# then the DELAY's (00 01 7f 01 00 00), byte for byte; T1's BongDelay in the
# live parts reads its manifest page 2 (30 00 40 01 00 00) and T8's ChonVerb
# its own; and two on-unit re-selects of the DELAY (T4, T7, 4 Sep 2026) wrote
# their rows at exactly 0x367 and 0x3c1 = 0x307 + 6 + 30 * track. Page 1 IS
# 24 from 0x12f (the same part reads eight identical rows).
#
# ⚠️ TWO WRONG LAYOUTS SHIPPED IN ONE DAY. The 24-stride writes landed in
# other tracks' rows (the stock DELAY's DIR, its dry level, read 0 on T2/T4/
# T7: silent until re-selected). The first fix, 0x325 + 30 * track, was
# ONE BLOCK LATE: it wrote every track's page 2 into the NEXT track's block,
# so T4's DELAY row landed on T5's BusVerb (DIFF 127: the tank self-
# oscillates and nothing but a reboot stops it) and T2's on T3's character
# station (RING 127). Seven tracks decoding right under 0x325 was the trap:
# a stride fits at any phase that lands on rows the unit happened to have
# written the same way. What settled it was a write the unit made on a
# NAMED track. Falsifier now: a unit re-select on track t whose row is not
# at 0x307 + 30 * (t - 1) (+6 for FX2).
P2_OFF, P2_STRIDE = 0x307, 30
FX_NAMES = {0x06: "BusDelay", 0x07: "BusVerb", 0x09: "SEND", 0x00: "-"}

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
    # BOTH copies, 7 Sep 2026: `.work` is the working state and `.strd` the
    # SAVED state, and PROJECT -> RELOAD on the unit restores `.strd`. An edit
    # made only in `.work` vanished on the first reload of the SEAMTEST flash
    # (a stale-part freeze on the first PLAY, reload, no trigs anywhere) and
    # cost a card round-trip. The same mutation goes into both so the two
    # states agree; the checksum is fixed up on each.
    for suffix in ("work", "strd"):
        path = pdir / f"bank{banknum:02d}.{suffix}"
        if suffix == "strd" and not path.is_file():
            continue
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

# A track's sample-slot record is FIVE bytes, one per machine type, and the
# firmware indexes it BY THE MACHINE-TYPE VALUE: `0x4000504e..0x4000507e`
# adds the type byte to `blob + part*0x18b2 + track*5 + 0x8f04a` (34 literal
# readers of that base; the PICKUP setter `0x400972fc` writes byte +4 =
# 128+track, its own recorder buffer). So byte +0 is the type-0 machine's
# slot, +1 the type-1 machine's, +4 PICKUP's. Slot bytes are 0-based (0 =
# slot 1, 128 = R1 -- the file's SLOT=129). Measured 7 Sep 2026 on the RIG's
# bank B: T2..T7 carry 128+ values in byte +1 and 1..128 values in byte +0,
# and only a FLEX machine can play a recorder buffer -- so type 1 is FLEX and
# type 0 STATIC (🟡 by that argument; PARAM_PAGES' 0/1 = FLEX/STATIC was an
# inference and is contradicted by this). The earlier form of this function
# wrote byte +0 only, i.e. the STATIC slot, for every caller.
SLOT_KIND = {"static": 0, "flex": 1, "pickup": 4}

# Measured on the unit 7 Sep 2026: the STATIC slot byte is 0-based like the
# FLEX one (byte 1 shows as "static 002"); a STATIC [SAMPLE] entry's PATH is a
# BARE filename ("PLUCK.wav"), and the ../AUDIO/<dir>/<file> form -- which the
# FLEX entries of Sam's projects use -- loads as an EMPTY slot for STATIC.
def set_track_slot(pdir, banknum, part, track, slot_1based, kind="flex"):
    if not (1 <= part <= NPARTS_ALL and 1 <= track <= 8):
        sys.exit(f"track-slot: part {part} / track {track} must be 1-based")
    def mut(data):
        off = PART_BASE + (part-1)*PART_STRIDE + 0x2d3 + (track-1)*5 + SLOT_KIND[kind]
        data[off] = slot_1based - 1
    _bank_write(pdir, banknum, mut)
    print(f"bank{banknum:02d} part{part} T{track} {kind} slot -> {slot_1based}")

# The machine-type byte, one per track per part. RAM offset (EMU.md /
# EXTERNAL.md §6) is `PART_PTR + part*0x18b2 + 0x8eda2 + track`; the file
# offset below is that plus the flat 9-byte IFF chunk header every PART
# chunk carries -- the same +9 that FX1_OFF/FX2_OFF already carry over
# their own RAM-relative 0 and 8. ✅ Verified 6 Sep 2026 by patching one
# track and reading the byte back out of RAM after a real LOAD PROJECT.
#
# The VALUES (measured 7 Sep 2026, RTOS_FORK section 10.13): 0 = STATIC,
# 1 = FLEX, 2 = THRU, 3 = NEIGHBOR, 4 = PICKUP. The trig-side slot lookup
# (0x400050b8..) sends type 0 to the STATIC arena and types 1/4 to the FLEX
# arena (which holds the recorder buffers), and the RIG's bank B carries
# recorder-buffer ids in its type-1 slot bytes. PARAM_PAGES.md's inferred
# 0/1 = FLEX/STATIC was the reverse. Also: the 6 Sep "file says 0, RAM says
# 2" worry was bank A's file against bank B's RAM -- the offset is right.
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

# ---------------------------------------------------------------------------
# PATTERN DATA: the sequencer's own records, and the step masks at their head
#
# A bank file is IFF: sixteen `PTRN` chunks (file stride 0x8eec), each holding
# eight `TRAC` sub-chunks (file stride 0x922) for the audio tracks and then
# eight `MTRA` for the MIDI ones. Every chunk is tag+len, so a record's DATA
# starts 8 bytes past its tag -- which is why the RAM strides are 8 less
# (0x8ed8 per pattern, 0x91a per track: `mulsl #0x91a,%d7` at 0x4009d376 and
# its siblings, with d7 = track).
#
# A TRAC record begins with a run of 64-bit big-endian STEP MASKS at an
# 8-byte stride: bit (step-1), so byte 7 bit 0 = step 1. Mask 0x00 is the
# note/sample trig -- the one `emu_rtos.poke_trig` sets in RAM, and the one
# whose bits you can read straight out of a real project (the rig project's
# track 1 reads 0x0001000100010001: trigs on steps 1, 17, 33 and 49).
# ✅ END TO END: setting step 2 here, on disk, with no RAM poke at all,
# lands `0xd3` on track 0 at frame 344 -- byte, track and frame identical to
# what `--poke-trig 2` produces, which is M6c's own fidelity gate.
# The sequencer ORs
# 0x00/0x08/0x10/0x18 for its "anything on this step" test (0x4009d382..9a)
# and builds a per-track flag word from 0x20 -> bit 12, 0x28 -> bit 13,
# 0x30 -> bit 14, 0x38 -> bits 5+8 (0x4009d93c..0x4009da12).
#
# ⚠️ WHICH MASK IS THE RECORDER TRIG IS NOT KNOWN. 0x40/0x48 are not masks at
# all -- they read as a run of 0xaa, a default-filled per-step byte array.
# The cheap way to settle it is `pattern-diff` below against two projects
# saved from the unit, one with a recorder trig and one without; nothing in
# the emulator identifies it as directly.
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
                                                                     # values (2 = 1X, 5 = 1/4X), 7 Sep 2026

def set_pattern_scale(pdir, banknum, pattern, length, scale, guard=True):
    """Set a pattern's LEN (1-64) and SCALE (index into SCALE_NAMES, or a
    name) in the SECOND of the two length/scale pairs at the PTRN chunk's
    tail (bytes -9/-8 of the chunk; the tail is len1 sc1 len2 sc2 flag 0 0
    0 0 tempo24). Measured 7 Sep 2026 (RTOS_FORK section 10.16.5): the
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
              "FIN", "FOUT", "AB", "QREC", "QPL", "CD"]   # descriptor order, EXTERNAL.md section 6
REC_SETUP_OFF = 0x60b   # part-relative file offset of track 0's 12 recorder-setup bytes
                        # (RAM 0x8f382 vs the machine-type byte's 0x8eda2, + the +9 IFF shift)

def set_recorder_setup(pdir, banknum, part, track, field, value, guard=True):
    """Write one RECORDING SETUP byte for a track, in part `part` (1-4) AND
    its saved mirror (part+4). RLEN is stored raw: display 1..64 -> 0..63,
    MAX -> 64. Measured 6 Sep 2026: the live page at 0x80000cf4 reads back
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


def _remix_defaults(remix_name, replaced_only):
    """-> {fx id: 12 default bytes} for the modules this remix places.

    replaced_only=True limits it to modules that REPLACE a stock effect (the
    only ids whose stored bytes are in a foreign layout); False covers every
    module of ours, which is what a freshly stamped test project wants.
    """
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    from remix import registry
    remix = registry.remix(remix_name)
    mods = registry.modules()
    out = {}
    for k in remix.modules:
        m = mods.get(k)
        if m is None or m.menu is None or getattr(m, "is_stock", False):
            continue
        if replaced_only and not m.menu.replaces:
            continue
        vals = [(p.default or 0) & 0x7f for p in m.params] + [0] * 12
        out[m.menu.fx2_id] = bytes(vals[:12])
    return out


def stamp_defaults(pdir, remix_name, replaced_only=True, guard=True):
    """Write our modules' manifest defaults into every part/track that names
    one of their ids. Returns the number of (part, track, slot) writes."""
    pdir = pathlib.Path(pdir)
    defaults = _remix_defaults(remix_name, replaced_only)
    if not defaults:
        sys.exit(f"remix {remix_name!r} has no {'replacing ' if replaced_only else ''}modules to stamp")
    total = 0
    for bank in sorted(pdir.glob("bank*.work")):
        num = int(bank.name[4:6])
        done = []

        def mut(data):
            for p in range(NPARTS_ALL):
                off = PART_BASE + p * PART_STRIDE
                for t in range(NTRACKS):
                    for idoff, sub in ((FX1_OFF, 0), (FX2_OFF, 6)):
                        fid = data[off + idoff + t]
                        if fid not in defaults:
                            continue
                        d = defaults[fid]
                        a = off + P1_OFF + t * TRACK_STRIDE + sub
                        b = off + P2_OFF + t * P2_STRIDE + sub
                        data[a:a + 6] = d[:6]
                        data[b:b + 6] = d[6:]
                        done.append((p, t, sub, fid))

        _bank_write(pdir, num, mut, guard=guard)
        # READ IT BACK, as testproj does: a write this tool cannot verify is
        # a write you find out about on the unit.
        data = bank.read_bytes()
        if int.from_bytes(data[-2:], "big") != (sum(data[0x10:-2]) & 0xFFFF):
            sys.exit(f"{bank.name}: checksum did not take -- do NOT use this")
        for p, t, sub, fid in done:
            off = PART_BASE + p * PART_STRIDE
            a = off + P1_OFF + t * TRACK_STRIDE + sub
            b = off + P2_OFF + t * P2_STRIDE + sub
            if data[a:a + 6] + data[b:b + 6] != defaults[fid]:
                sys.exit(f"{bank.name} part {p+1} T{t+1}: read-back disagrees")
        total += len(done)
        if done:
            print(f"bank{num:02d}: {len(done)} slots stamped with our defaults")
    print(f"{total} slot(s) stamped for remix {remix_name!r} "
          f"({'replaced ids only' if replaced_only else 'every id of ours'})")
    return total


def _resolve_module(which):
    """A module by key ("REVERB SERVER"), name ("busverb") or fx id (0x07 /
    7) -> (fx id, Module or None). Names come from the registry, so a tool
    invocation never carries an id that could go stale."""
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
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


def stamp_slot(pdir, which, slot, value=None, guard=True, tracks=None):
    """Write ONE knob byte for every part/track that names the module (FX2
    or FX1), leaving the other eleven alone. `which` is a module key, name
    or fx id; `slot` an index or the knob's manifest name; `value` defaults
    to the manifest default. For a slot whose MEANING changed (5 Sep 2026:
    BusVerb's LP -> -DEL, HP -> TONE; BusDelay's DRV -> -DEL): stamp-defaults
    keeps the engines' bytes deliberately ("Sam's knobs"), and re-stamping all
    twelve would throw those away. Page 1 is slot < 6. `tracks` (1-based,
    e.g. {8}) limits the stamp to those tracks -- the same module on another
    track keeps its byte (6 Sep 2026: the MASTER's Character -VRB must be 0,
    T1's Character -VRB is a real send)."""
    pdir = pathlib.Path(pdir)
    fx_id, mod = _resolve_module(which)
    slot = _resolve_slot(mod, slot)
    if value is None:
        if mod is None:
            sys.exit("a bare id has no manifest default -- give the value")
        value = mod.params[slot].default or 0
    value = int(value) & 0x7f
    label = (f"{mod.key} {mod.params[slot].name.decode('latin1')}"
             if mod is not None else f"id 0x{fx_id:02x}")
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
        done = []
        _bank_write(pdir, num, mut, guard=guard)
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


# ---- the RIG project: the set's layout, with the returns wired ------------
# One part = the whole rig on its eight tracks, as designed (the BamSep26
# page and docs/BUS.md "The returns"): stations on FX1 everywhere, the two
# engines in T1's and T5's FX2, the stock delay where a track wants one, and
# T8's Character station in SAT=BUS with both returns up. Every part of every
# bank gets the same layout, so any pattern is the rig. Knob bytes are the
# manifest defaults with the few deliberate exceptions listed per track.
RIG = (
    # track, FX1 (key, {knob: val}),                FX2 (key, {knob: val})
    # FX2 on the six ordinary tracks is SEND (the fallback: two send knobs,
    # drawn blank because hidden). The stock DELAY row is gone after flash 4;
    # the sends live on the FX1 stations. T1 hosts the delay engine, T5 the
    # reverb, T8 (master) has no FX2.
    # ONE AUX (7 Sep 2026): the stations have no sends; every track's one
    # send is FX2's AUX at slot 0, the hosts' included; T8 returns (RET).
    (1, ("CHARACTER", {}),                  ("DELAY SERVER", {"AUX": 30})),
    (2, ("SPECTRUM", {}),                   ("SEND", {"AUX": 40})),
    (3, ("SPECTRUM", {}),                   ("SEND", {"AUX": 30})),
    (4, ("SPECTRUM", {}),                   ("SEND", {"AUX": 40})),
    (5, ("MODULATION", {}),                 ("REVERB SERVER", {"AUX": 40})),
    (6, ("SPECTRUM", {}),                   ("SEND", {"AUX": 50})),
    (7, ("SPECTRUM", {}),                   ("SEND", {"AUX": 40})),    # SPECTRUM, not
    # Character: T5 Modulation + T8 Character are core 0's two heavy already;
    # a third here (was CHARACTER) priced ~3106 of 3120 as a FLOOR and hung
    # the sequencer on frame 1 (tag 91, step 1 solid). Character on T7 for a
    # vocal set is a manual part swap that drops T5 to Spectrum -- design page.
    (8, ("CHARACTER", {"SAT": 3, "RET": 127,
                               "CMOD": 1, "COMP": 40}), (None, {})),   # the return; no FX2 (no send from T8)
)


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
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
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
        vals = [(p.default or 0) & 0x7f for p in m.params] + [0] * 12
        kmap = m.knob_map_all() if not getattr(m, "is_stock", False) else {}
        for n, v in knobs.items():
            if n not in kmap:
                sys.exit(f"{key} has no knob {n!r}")
            vals[kmap[n]] = v
        return m.menu.fx2_id, bytes(vals[:12])

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
    lines += ["", "ONE AUX (7 Sep 2026): every track's AUX feeds the delay (T1), then the",
              "reverb (T5); T8 returns the last live stage (SAT=BUS, RET = CRSH at 127).",
              "Turn T8's RET to 0 and the hosts print again within 3 blocks. T8 has no",
              "FX2: the SEND is refused there anyway, and the stations have no sends."]
    (dest / "OCTABAM_RIG_MAP.txt").write_text("\n".join(lines) + "\n")
    print(f"{len(list(dest.glob('bank*.work')))} banks written and verified -> {dest}")
    print(f"map at {dest / 'OCTABAM_RIG_MAP.txt'}")


if __name__ == "__main__":
    cmd = sys.argv[1]; pdir = pathlib.Path(sys.argv[2])
    if cmd == "report": cmd_report(pdir)
    elif cmd == "set-gain": apply_gains(pdir, {sys.argv[3]: sys.argv[4]})
    elif cmd == "apply": apply_gains(pdir, json.loads(pathlib.Path(sys.argv[3]).read_text()))
    elif cmd == "part-name": set_part_name(pdir, int(sys.argv[3]), int(sys.argv[4]), sys.argv[5])
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
    elif cmd == "rigproj": make_rig_project(sys.argv[2], sys.argv[3], sys.argv[4])
    elif cmd == "stamp-defaults":
        # a REAL set, before its first load on a flashed image: only the ids
        # a station replaced are touched; BusVerb/BusDelay keep Sam's knobs
        stamp_defaults(pdir, sys.argv[3], replaced_only=True)
    elif cmd == "stamp-slot":
        # one knob byte, every part/track naming that module: for a slot
        # whose meaning changed. Module by key/name/id, slot by name/index,
        # value optional (manifest default). e.g.
        #   stamp-slot PROJ "REVERB SERVER" TONE      -> 64, from the manifest
        #   stamp-slot PROJ busdelay -DEL 0
        #   stamp-slot PROJ character -VRB 0 --track 8   (the master only)
        args = sys.argv[3:]
        tracks = None
        if "--track" in args:
            i = args.index("--track")
            tracks = {int(x) for x in args[i + 1].split(",")}
            del args[i:i + 2]
        stamp_slot(pdir, args[0], args[1], args[2] if len(args) > 2 else None,
                   tracks=tracks)
    else: sys.exit(f"unknown command {cmd!r}")
