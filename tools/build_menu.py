#!/usr/bin/env python3
"""
SUPERSEDED by tools/build_bus.py (the shipping builder) -- kept as the
ColdFire-menu-integration record. Comments below predate two corrections:
the FX1 menu NEVER listed the reverbs or DELAY (they are FX2-only; "FX1's
DARK REV entry" below is wrong), and defaults here are frozen at their
task-11 values (e.g. LP=100; the shipping default is 127, build_bus.py).

BUS.md task 11: replace FX2's chooser list with exactly three entries --
DELAY SERVER, REVERB SERVER, SEND.

    python3 tools/build_menu.py

Scope, deliberately narrow: this is the ColdFire-side MENU integration only
(BUS.md's five tables -- PARAM_PAGES.md section 5e). It makes the three roles
selectable, correctly named, with correctly counted/ranged knobs, verified by
walking the real chooser-scan and id-store functions in Unicorn
(tools/verify_menu.py) before ever flashing. It does NOT yet place
dsp/reverb_server.asm / delay_server.asm / send_client.asm's assembled code in
P memory or repoint the X:0x215/X:0x235 dispatch tables -- that needs a P-memory
budget decision of its own and is a follow-up task. Selecting any of the three
new entries right now would run whatever init/proc the CLONED descriptor's
donor id used to point at, which is wrong; this build is a ColdFire-only proof,
not yet flashable as a working effect.

**"FX1 is untouched" stays literally true here**, not just structurally: each
new entry is a fresh CLONE of a donor descriptor's bytes at a brand-new address,
under a brand-new id that FX1's own (unedited) id lookup and chooser list
(0x400d5f58 / 0x400d6060) can never reach. The donor's OWN id/descriptor/chooser
entry is left completely alone, so FX1's menu for that donor effect keeps its
original name and knob labels. (This is a deliberate correction from the
current shipped reverb build, which reuses DARK REV's own id/descriptor and so
DOES bleed into FX1's DARK REV entry -- accepted there because it already
shipped and was hardware-confirmed before this menu redesign existed. Not
repeated here now that ColdFire changes are in scope anyway.)

Donor choice only matters for which of the two page-2 "shapes" a clone
inherits (DSP.md section 9 / REVERB.md's parameter table -- only $b/$c/$d/$e are
real page-2 slots, and which text label sits on which of those four is fixed
by the donor's own descriptor bytes, not something this script controls):

  REVERB SERVER <- clone of DARK REV's bytes (cls 0x400328e4). Already uses
    all of page 1 (r6+0..5: TIME/MOD/SIZE/HP/LP/MIX) plus BAL (r6+$b, WIDTH)
    and PRE (r6+$c) for real, working knobs (dsp/reverb_server.asm). Only
    MONO (r6+$d) is repurposed here, for the ->DELAY send this file already
    reads from that exact offset (BUS.md task 10) -- confirmed dead on
    hardware, per REVERB.md, so free to relabel.
  DELAY SERVER  <- clone of SPRING REV's bytes (same cls, same safe page-2
    shape). Page 1 is renamed wholesale (dsp/delay_server.asm's own layout);
    the spare "MONO"-equivalent slot (r6+$d) carries ->VERB DRY. TYPE/BAL
    (r6+$c/$b) are blanked -- unread by our algorithm, harmless if left, but
    blanking avoids a mystery live knob in the UI.
  SEND          <- clone of FILTER's bytes (cls 0x40032814). Only needs page 1
    slots 0/1 (dsp/send_client.asm), which is the universally-confirmed-safe
    straight r6+i mapping regardless of donor class, so the donor choice here
    carries no risk either way.

Defaults: touched in exactly one place, deliberately -- SEND's inherited
->REVERB default (FLTR's WDTH default, 127) would default a fresh SEND
instance to full reverb blast. Zeroed. Every other default/count is left as
the donor's own, unread by our code as long as it stays a continuous 0-127
slot (independently confirmed already for every offset used, see above) --
same conservative style build_reverb.py already used for DARK REV's renames.
"""
import pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from dsp_modmap import BASE, IMG  # noqa: E402

OUT = pathlib.Path("out/mainos_menu.bin")

FX2_IDS = 0x400d5fdc
FX2_LIST = 0x400d6090
ID2POS = 0x400d6150
LIST_REFS = [0x400375f4, 0x40052496, 0x40059a42]
DESC_LEN = 0x192

# fresh cave, confirmed zero for 0x113c bytes from here (tools/build_menu.py's
# own -check, and previously by build_dspprobe.py's neighbouring 0x400d7000 use)
NEW_LIST = 0x400d6b00
CLONE_BASE = 0x400d6b20
CLONE_STRIDE = 0x1a0                    # > DESC_LEN, comfortable spacing

DONORS = {"DELAY SERVER": 0x400d5726,   # SPRING REV
          "REVERB SERVER": 0x400d58b8,  # DARK REV
          "SEND": 0x400d4772}           # FILTER

# stock NONE descriptor's P pointer (E=0x400d45e0 + 0x38) -- used both to pad
# the chooser list (below) and picked as the "id family" our own three ids
# deliberately avoid (see NEW_IDS comment)
NONE_P = 0x400d4618

# chooser order per BUS.md's Menu and slot layout section
ORDER = ["DELAY SERVER", "REVERB SERVER", "SEND"]
# 0x06/0x07/0x09: unused gap ids (PARAM_PAGES.md's sparse-id list), NOT
# 0x01/0x02/0x03. First hardware test used 0x01/0x02/0x03 and got the chooser
# names right but silent/uninitialized-feeling audio and unresponsive knobs on
# ALL three -- and ids 0x00-0x03 turn out to be the specific four values stock
# firmware has ALWAYS treated as bare synonyms for "no effect" (all four map
# to the same NONE descriptor, unlike other currently-unused ids which also
# happen to map to NONE today but were never given that special meaning by
# the numbers themselves). 0x06 is the exact id tools/build_dspprobe.py
# already proved runs custom DSP code correctly on real hardware -- reusing
# that specific precedent rather than a fresh guess.
NEW_IDS = {"DELAY SERVER": 0x06, "REVERB SERVER": 0x07, "SEND": 0x09}

# (page-array index, new 6-byte NUL-padded label or None to leave alone)
RENAMES = {
    "DELAY SERVER": [
        (1, b"FDBK"), (2, b"TONE"), (3, b"PING"), (4, b"MIX"), (5, b"VRBW"),
        (6, b""), (7, b""), (8, b"VRBD"),
    ],
    "REVERB SERVER": [
        (1, b"MOD"), (2, b"SIZE"),          # already-shipped build_reverb.py renames
        (8, b"-DEL"),                        # BUS.md task 10's ->DELAY send
    ],
    "SEND": [
        (0, b"-DEL"), (1, b"-VRB"),
        (2, b""), (3, b""), (4, b""), (5, b""),
        (6, b""), (7, b""), (8, b""), (9, b""), (10, b""), (11, b""),
    ],
}
ABBR = {"DELAY SERVER": b"BDLY", "REVERB SERVER": b"BVRB", "SEND": b"SEND"}
FULLNAME = {"DELAY SERVER": b"BusDelay", "REVERB SERVER": b"BusVerb",
            "SEND": b"Send"}

# (page-array index, default byte). Set explicitly for every knob we enable,
# rather than inheriting the donor's -- the donor's defaults are for a
# DIFFERENT algorithm on that slot and several are actively wrong for ours.
# In particular DARK REV's MIX default is 0, which would make a freshly
# selected REVERB SERVER completely silent, and SPRING's TONE-slot default
# is 0, which is our darkest possible setting. Both would look exactly like
# "the effect does nothing" on hardware.
DEFAULTS = {
    "DELAY SERVER": [(0, 40),    # TIME  ~ 5k samples, an obvious echo
                     (1, 60),    # FDBK  a few audible repeats, well short of runaway
                     (2, 100),   # TONE  bright enough to hear the repeats clearly
                     (3, 64),    # PING  mid crossfeed, so ping-pong is audible
                     (4, 90),    # MIX   clearly wet but dry still present
                     (5, 0),     # ->VERB WET  off: cross-bus sends stay opt-in
                     (8, 0)],    # ->VERB DRY  off
    "REVERB SERVER": [(0, 64),   # TIME  mid decay
                      (1, 30),   # MOD   gentle
                      (2, 100),  # SIZE  large
                      (3, 0),    # HP/LO no low cut
                      (4, 100),  # LP/HI mostly bright
                      (5, 64),   # MIX   audible wet -- NOT DARK's 0
                      (6, 0),    # PRE   no pre-delay
                      (7, 64),   # BAL/WIDTH  full stereo
                      (8, 0)],   # ->DELAY  off
    "SEND": [(0, 0), (1, 0)],    # both sends off: a fresh SEND must be silent
}

# ---- P-relative field offsets (PARAM_PAGES.md section 5b) ------------------
# The canonical record base is P = E + 0x38, and the record is 0x192 bytes
# long MEASURED FROM P. PARAM_PAGES.md section 2's table is E-relative, so
# every offset there is 0x38 higher than its true P-relative form.
P_ID_BYTE = 0x03            # E+0x3b
P_ABBR = 0x04               # E+0x3c, 5 B
P_FULLNAME = 0x09           # E+0x41, 13 B
P_PARAM_NAMES = 0x16        # E+0x4e, 12 x 6 B
P_DEFAULTS = 0x5e           # E+0x96, 12 x u8
P_MIN = 0x6a                # E+0xa2, matches section 5b's "min = P+0x6a"
P_COUNT = 0x9a              # E+0xd2, matches section 5b's "count = P+0x9a"
# The per-parameter ENABLE BITMAP -- one nibble per parameter, bit 0 = "this
# knob exists, draw it". P+0x18e holds params 0..7 (low nibble = param 0),
# P+0x18a holds params 8..11. FUN_400326d4 and FUN_40037590 both pass these
# two words to FUN_400a6994(lo, hi, paramIndex) and gate on the returned
# bit 0; a zero nibble is exactly what a "---" slot has in every stock
# descriptor (verified against SPRG/PLTE/DARK/FLTR -- every empty name has
# nibble 0, every real knob has bit 0 set).
#
# THIS IS WHAT THE FIRST TWO HARDWARE FLASHES GOT WRONG. Both copied
# E..E+0x192 instead of P..P+0x192, so the clone started 0x38 bytes too
# early AND ended 0x38 bytes short -- and 0x18a/0x18e sit in exactly that
# missing tail. The clones read cave zeros there, which means "this effect
# has no parameters at all", which is precisely the observed symptom: names
# rendered fine (P+0x16 was inside the copied range) but not one knob drawn.
P_PENABLE_LO = 0x18e        # params 0..7
P_PENABLE_HI = 0x18a        # params 8..11

def penable(active):
    """(lo, hi) enable words for a set of active parameter indices."""
    lo = hi = 0
    for i in active:
        if i < 8:
            lo |= 1 << (4 * i)
        else:
            hi |= 1 << (4 * (i - 8))
    return lo, hi

# Which knobs each effect actually reads. Set explicitly rather than
# inherited from the donor, so a knob can never appear that our DSP code
# does not read (and vice versa). Page-1 indices 0..5 map straight to
# r6+0..5; page-2 index 6 = r6+$c, 7 = r6+$b, 8 = r6+$d, 11 = r6+$e
# (DSP.md section 9's measured, NOT-in-display-order mapping).
ACTIVE_PARAMS = {
    # TIME FDBK TONE PING MIX ->VERB WET (0..5), + ->VERB DRY on r6+$d (8)
    "DELAY SERVER": [0, 1, 2, 3, 4, 5, 8],
    # TIME MOD SIZE HP LP MIX (0..5), PRE=r6+$c (6), WIDTH=r6+$b (7),
    # ->DELAY=r6+$d (8). MIXF/r6+$e (11) stays off -- we never read it.
    "REVERB SERVER": [0, 1, 2, 3, 4, 5, 6, 7, 8],
    # only the two send levels, r6+0 and r6+1
    "SEND": [0, 1],
}


def main():
    img = bytearray(IMG.read_bytes())

    def rd32(a):
        return int.from_bytes(img[a - BASE:a - BASE + 4], "big")

    def wr32(a, v):
        img[a - BASE:a - BASE + 4] = v.to_bytes(4, "big")

    cave_end = CLONE_BASE + CLONE_STRIDE * len(ORDER)
    if any(img[NEW_LIST - BASE:cave_end - BASE]):
        sys.exit("cave not free")

    clone_addr = {}
    print("=== ColdFire: three cloned descriptors (BUS.md task 11) ===")
    for i, name in enumerate(ORDER):
        # Copy from the donor's P, not its E: the record is 0x192 bytes
        # measured FROM P (PARAM_PAGES.md section 5b). CLONE_BASE is itself a
        # P address -- the value that goes straight into the tables.
        donor_P = DONORS[name] + 0x38
        clone_P = CLONE_BASE + i * CLONE_STRIDE
        img[clone_P - BASE:clone_P - BASE + DESC_LEN] = \
            img[donor_P - BASE:donor_P - BASE + DESC_LEN]

        new_id = NEW_IDS[name]
        img[clone_P - BASE + P_ID_BYTE] = new_id
        abbr = ABBR[name].ljust(5, b"\0")[:5]
        full = FULLNAME[name].ljust(13, b"\0")[:13]
        img[clone_P - BASE + P_ABBR:clone_P - BASE + P_ABBR + 5] = abbr
        img[clone_P - BASE + P_FULLNAME:clone_P - BASE + P_FULLNAME + 13] = full
        for idx, label in RENAMES[name]:
            a = clone_P + P_PARAM_NAMES + idx * 6
            img[a - BASE:a - BASE + 6] = label.ljust(6, b"\0")[:6]
        for idx, val in DEFAULTS.get(name, []):
            img[clone_P - BASE + P_DEFAULTS + idx] = val

        # the enable bitmap -- without this every knob stays hidden
        lo, hi = penable(ACTIVE_PARAMS[name])
        wr32(clone_P + P_PENABLE_LO, lo)
        wr32(clone_P + P_PENABLE_HI, hi)

        clone_addr[name] = clone_P
        print(f"  {name:14s} id 0x{new_id:02x}  donor P=0x{donor_P:08x}  "
              f"-> clone P=0x{clone_P:08x}")
        print(f"                 knobs {ACTIVE_PARAMS[name]}  "
              f"enable lo=0x{lo:08x} hi=0x{hi:08x}")

    print("\n=== 1. id lookup (FX2_IDS) ===")
    for name in ORDER:
        new_id, P = NEW_IDS[name], clone_addr[name]
        wr32(FX2_IDS + new_id * 4, P)
        print(f"  id 0x{new_id:02x} -> 0x{P:08x}  ({name})")

    print("\n=== 2. chooser list (FX2_LIST), full replacement ===")
    # NONE goes FIRST, exactly as the stock list has it -- without it there is
    # no way to turn FX2 off at all (first two hardware flashes had no
    # selectable NONE, and clicking a bare padding row appeared to do nothing
    # because it stores id 0, whose ID2POS entry then snapped the cursor back
    # to position 0 -- which was DELAY SERVER rather than NONE).
    #
    # The list renderer (FUN_40037590, via the hardcoded literal 7 passed to
    # FUN_4007ec60) always draws a FIXED 7-row viewport regardless of the real
    # scanned list length -- harmless with the stock 15-entry list, but a
    # short list leaves the remaining rows reading raw memory past our
    # terminator and rendering it as garbage ("a bunch of symbols", first
    # hardware test). Pad to 7 rows with NONE so those rows are blank and
    # harmless: selecting one stores id 0 and lands on the real NONE at
    # position 0. NEW_LIST has exactly 0x20 bytes of cave before CLONE_BASE,
    # precisely 8 words (7 entries + terminator), no slack either way.
    PAD_TO = 7
    real = [("NONE", NONE_P)] + [(n, clone_addr[n]) for n in ORDER]
    entries = [p for _, p in real] + [NONE_P] * (PAD_TO - len(real)) + [0]
    assert len(entries) * 4 <= CLONE_BASE - NEW_LIST, "list overruns the clone cave"
    for i, v in enumerate(entries):
        wr32(NEW_LIST + i * 4, v)
    for pos, (n, p) in enumerate(real):
        print(f"  pos {pos}: 0x{p:08x}  ({n})")
    for pos in range(len(real), PAD_TO):
        print(f"  pos {pos}: 0x{NONE_P:08x}  (padding NONE -- fills the fixed 7-row viewport)")
    print(f"  pos {PAD_TO}: 0x00000000  (terminator)")

    for r in LIST_REFS:
        if rd32(r) != FX2_LIST:
            sys.exit(f"list ref at 0x{r:08x} did not point at stock FX2_LIST "
                      f"as expected -- refusing to overwrite blind")
        wr32(r, NEW_LIST)
    print(f"  repointed {len(LIST_REFS)} refs -> 0x{NEW_LIST:08x} "
          f"(FX1's own tables at 0x400d5f58 / 0x400d6060 untouched)")

    print("\n=== 5. id -> cursor position (ID2POS) ===")
    # id 0 (NONE) must map to NONE's own position, or selecting it bounces.
    wr32(ID2POS + 0 * 4, 0)
    print(f"  id 0x00 = pos 0  (NONE)")
    for pos, name in enumerate(ORDER, start=1):
        wr32(ID2POS + NEW_IDS[name] * 4, pos)
        print(f"  id 0x{NEW_IDS[name]:02x} = pos {pos}  ({name})")

    OUT.write_bytes(bytes(img))
    d = sum(1 for x, y in zip(IMG.read_bytes(), img) if x != y)
    print(f"\n{OUT}: {len(img):,} bytes, {d} changed")
    print("\nNOT flashable as a working effect yet: DSP dispatch (X:0x215/")
    print("X:0x235) still points at each donor's OWN init/proc. Placing")
    print("dsp/reverb_server.asm / delay_server.asm / send_client.asm in P")
    print("memory and repointing dispatch for the new ids is the next,")
    print("not-yet-scoped step. This build proves the MENU mechanism only --")
    print("see tools/verify_menu.py, checked against the real chooser functions")
    print("decompiled via tools/GhidraMenuFuncs.java.")


if __name__ == "__main__":
    main()
