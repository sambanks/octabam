#!/usr/bin/env python3
"""
BUS.md tasks 11 + 13: the full three-entry FX2 menu, both payloads, with the
three servers' own DSP code actually placed and dispatched.

    python3 tools/build_bus.py

Builds on tools/build_menu.py's already-verified ColdFire menu tables (same
constants, reproduced here rather than imported so this stays a single
self-contained build script like every other tools/build_*.py in this
project) and adds what task 11 explicitly deferred: placing
dsp/reverb_server.asm / delay_server.asm / send_client.asm's assembled code
in real P memory, for BOTH payloads, and repointing X:0x215/X:0x235 so the
three new ids (0x01 DELAY SERVER, 0x02 REVERB SERVER, 0x03 SEND) actually run
them instead of whatever the byte-donor used to be.

DSP-side donor choice (P-code space only -- unrelated to the ColdFire
descriptor-clone donors task 11 already picked):

  REVERB SERVER (1215 words) <- SPRING + DARK's front, exactly the
    combined-budget technique tools/build_reverb.py already proved safe on
    hardware (2037 words available, SPRING's own inbound callers are from
    stock DARK alone, and DARK's own front is the same "974-word helper
    boundary" already measured). This build does NOT repeat that script's
    choice to repoint SPRING/DARK's OWN ids at the new code -- see below.
  DELAY SERVER (453 words) <- PLATE REV's module (594 words, confirmed no
    inbound branches at all -- tools/build_reverb.py's own relocatability
    note). Comfortable single-module fit, no spillover needed.
  SEND (127 words) <- CHORUS's module (329 words, confirmed clean by
    tools/build_dspprobe.py's relocatability scan: "no absolute internal
    jumps, nothing branches into it"). Same donor that script used to prove
    the whole assemble -> insert -> dispatch -> flash pipeline on real
    hardware, just for a different purpose here (byte space, not a probe).

**Donor ids get repointed to the SAME null stub tools/build_dspprobe.py
already used and proved silent on hardware (P:0x007c8/0x007c9 payload A,
P:0x00588/0x00589 payload B -- stock DELAY's own dispatch, already a no-op
by design), not to the new server code.** This is a deliberate departure
from tools/build_reverb.py, which repoints SPRING/DARK's own ids at the new
reverb engine -- fine there because nothing else in this project offers
those ids any more once this build's three-entry menu replaces the whole FX2
chooser. But FX1's chooser is untouched (BUS.md's "FX1 is untouched"
promise) and can still select CHORUS, PLATE REV, SPRING REV or DARK REV by
name -- if their dispatch pointed at our servers, selecting one on FX1 would
run the SAME hardcoded-Y-base engine a second, uncontrolled time on whatever
track holds it, exactly the multi-instance collision the hardcoded-base
design assumes can't happen (BUS.md's Memory section). Silencing them
avoids that: FX1 selecting any of the four donor names now gets harmless
silence, the same already-hardware-proven behaviour stock DELAY has always
had.

DELAY SERVER's Y-memory base literal is the one place this script differs
per payload in the ASSEMBLED CODE itself (not just where it's placed):
dsp/delay_server.asm hardcodes `$30000`, correct for payload A only (Known
limitations in BUS.md already flagged this). Payload B needs `$38000`
instead, so this script substitutes the literal in the source text before
assembling payload B's copy -- the same class of per-payload text edit
tools/gen_reverb.py already does for its own parameters, just a straight
substitution here since there's exactly one occurrence.
"""
import pathlib, subprocess, sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from dsp_modmap import BASE, IMG, PAYLOADS, modules  # noqa: E402

OUT = pathlib.Path("out/mainos_bus.bin")
DIS = pathlib.Path("vendor/dsp56300/build/source/dsp_host/dsp_asm")

# ---- ColdFire menu tables (task 11, tools/build_menu.py, reproduced here) --
FX2_IDS = 0x400d5fdc
FX2_LIST = 0x400d6090
ID2POS = 0x400d6150
LIST_REFS = [0x400375f4, 0x40052496, 0x40059a42]
DESC_LEN = 0x192
NEW_LIST = 0x400d6b00
CLONE_BASE = 0x400d6b20
CLONE_STRIDE = 0x1a0

DESC_DONORS = {"DELAY SERVER": 0x400d5726,   # SPRING REV
               "REVERB SERVER": 0x400d58b8,  # DARK REV
               "SEND": 0x400d4772}           # FILTER

# The chooser's viewport height: FUN_4005996c pushes a literal 7 to
# FUN_4007ec60, which stores it as the number of rows FUN_40037590's draw loop
# iterates -- independently of the real list length. With a short list the
# extra rows read past the terminator and render raw memory as text (the
# "bunch of symbols" of hardware test 1). Patching the immediate to match the
# real list is the clean fix; it sits inside the FX2-specific setup function,
# so FX1's menu is unaffected. `pea (0x7).w` = 4878 0007 at 0x40059a54.
ROWCOUNT_AT = 0x40059a56        # the 16-bit immediate itself
ROWCOUNT_INSN = 0x40059a54
NONE_ID = 0x00                  # a fresh part's FX2 id -- aliased to SEND below

ORDER = ["REVERB SERVER", "DELAY SERVER", "SEND"]   # ChongVerb first, by preference
# 0x06/0x07/0x09, not 0x01/0x02/0x03: the first hardware test used
# 0x01/0x02/0x03 and got correct chooser names but no working knobs and
# garbage/uninitialized-feeling audio on all three. Ids 0x00-0x03 are the
# specific four values stock firmware has always treated as bare synonyms
# for "no effect" (ColdFire logic elsewhere very likely does a raw "id < 4"
# check, not just a NONE-descriptor lookup), unlike other currently-free ids
# that happen to map to NONE today without carrying that special meaning.
# 0x06 is the exact id tools/build_dspprobe.py already proved runs custom
# DSP code correctly on real hardware -- reusing that specific precedent.
NEW_IDS = {"DELAY SERVER": 0x06, "REVERB SERVER": 0x07, "SEND": 0x09}

RENAMES = {
    "DELAY SERVER": [
        (1, b"FDBK"), (2, b"TONE"), (3, b"PING"), (4, b"MIX"), (5, b"VRBW"),
        (6, b""), (7, b""), (8, b"VRBD"),
    ],
    "REVERB SERVER": [
        (1, b"MOD"), (2, b"SIZE"),
        # Page 2 rejig (v92). Even slots are knob fields (0..127, measured);
        # odd slots are companion fields in the same word and are only proven
        # to carry a SMALL step count -- see PAGE2_COUNTS below.
        (6, b"SPEED"),          # slot 6 -> r6+$b        MOD rate
        (7, b"MODE"),           # slot 7 -> r6+$c b8-15  character select
        (8, b"DIFF"),           # slot 8 -> r6+$d knob   allpass coefficient
        (9, b"WIDTH"),          # slot 9 -> r6+$d low
        (10, b"PRE"),           # slot 10 -> r6+$e knob
        (11, b"-DEL"),          # slot 11 -> r6+$e low
    ],
    "SEND": [
        (0, b"-DEL"), (1, b"-VRB"),
        (2, b""), (3, b""), (4, b""), (5, b""),
        (6, b""), (7, b""), (8, b""), (9, b""), (10, b""), (11, b""),
    ],
}
ABBR = {"DELAY SERVER": b"BDLY", "REVERB SERVER": b"CVRB", "SEND": b"SEND"}
# BUILD TAG, stamped into the effect's displayed name. Three rounds were lost
# to not being able to tell WHICH build was running on the unit: a symptom
# ("knobs unchanged") is ambiguous between "the change did not work" and "the
# flash did not apply", and those need opposite responses. The name field is
# 13 bytes and always on screen, so it costs nothing to carry the answer.
# BUMP THIS EVERY TIME A .bin IS WRAPPED FOR FLASHING.
BUILD_TAG = b"20"

FULLNAME = {"DELAY SERVER": b"BongDelay", "REVERB SERVER": b"ChonVerb" + BUILD_TAG,
            "SEND": b"Send"}
# Explicit per-knob defaults -- NOT the donor's, which are for a different
# algorithm on that slot. DARK REV's MIX default is 0 (a freshly selected
# REVERB SERVER would be silent) and SPRING's TONE-slot default is 0 (our
# darkest setting); both look exactly like "the effect does nothing".
DEFAULTS = {
    "DELAY SERVER": [(0, 40), (1, 60), (2, 100), (3, 64), (4, 90), (5, 0), (8, 0)],
    # EVERY page-2 slot needs an explicit default now that all twelve are
    # enabled: an unlisted slot keeps the DONOR's default, which is sized for
    # DARK REV's value counts, not ours. And a default outside its own count
    # is used as an index -- that shipped once (slot 7: default 64, count 5)
    # and stalled the sequencer on hardware. verify_menu.py now checks it.
    "REVERB SERVER": [(0, 64), (1, 30), (2, 100), (3, 0), (4, 100), (5, 64),
                      (6, 48),   # SPEED  slow-ish
                      (7, 2),    # MODE   HALL, the most generally useful
                      (8, 64),   # DIFF   mid
                      (9, 127),  # WIDTH  full
                      (10, 0),   # PRE    none
                      (11, 0)],  # -DEL   off
    "SEND": [(0, 0), (1, 0)],
}

# ---- P-relative field offsets (PARAM_PAGES.md section 5b) ------------------
# The record's canonical base is P = E + 0x38 and it is 0x192 bytes long
# MEASURED FROM P, so section 2's E-relative table is 0x38 high throughout.
P_ID_BYTE, P_ABBR, P_FULLNAME = 0x03, 0x04, 0x09
P_PARAM_NAMES, P_DEFAULTS = 0x16, 0x5e
# per-parameter enable bitmap, one nibble each, bit 0 = "draw this knob".
# P+0x18e = params 0..7 (low nibble = param 0), P+0x18a = params 8..11.
# Copying from E instead of P loses these (they sit in the record's last
# 0x38 bytes) and every knob silently disappears -- the bug the first two
# hardware flashes shipped. See BUS.md's "Hardware test 1/2" section.
P_PENABLE_LO, P_PENABLE_HI = 0x18e, 0x18a


def penable(active):
    lo = hi = 0
    for i in active:
        if i < 8:
            lo |= 1 << (4 * i)
        else:
            hi |= 1 << (4 * (i - 8))
    return lo, hi


# Which knobs each effect's DSP code actually reads. Page-1 indices 0..5 are
# r6+0..5; page-2 index 6 = r6+$c, 7 = r6+$b, 8 = r6+$d (DSP.md section 9).
ACTIVE_PARAMS = {
    "DELAY SERVER": [0, 1, 2, 3, 4, 5, 8],
    "REVERB SERVER": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],  # all twelve (v92)
    "SEND": [0, 1],
}

# Page-2 value counts for REVERB SERVER (v92). Even slots take the full 0..127
# knob range, which is measured. Odd slots are COMPANION fields sharing the
# even slot's word, and the only counts ever confirmed on hardware for them are
# small ones -- tools/build_bus.py's own probe used count 3, whatever DSP.md
# section 9's prose says about "a full 0..127 range". So they get modest step
# counts here and the DSP scales them back up (asl #$13). If a larger count is
# ever confirmed, raise these and drop the DSP shift to #$10; nothing else
# changes.
# count IS the value range, drawn on a 0..127 scale -- a count of 16 gives 16
# steps over one eighth of the knob's travel, which is what WIDTH and ->DEL
# did on hardware. Only MODE wants a small count: that is exactly how stock
# encodes a selector (CHORUS TAPS is count 5, FILTER NUM is count 5, both with
# enable nibble 1 and min 0 -- there is no separate "selector" type field).
# THREE KNOBS + THREE SELECTS is the hardware budget (DSP.md section 9), not
# six knobs. The knob fields ($b/$d/$e bits 16-22) take 128; the companion
# fields are eight-bit selects and take a small step count. Setting a
# companion slot to 128 does not make it continuous -- it stays a select and
# reads as a near-boolean, which is what hardware showed.
PAGE2_COUNTS = {"REVERB SERVER": {6: 128,   # SPEED  knob
                                  7: 4,     # MODE   select: ROOM/PLATE/HALL/BIG
                                  8: 128,   # DIFF   knob
                                  9: 128,   # WIDTH  full knob
                                  10: 128,  # PRE    knob
                                  11: 128}} # -DEL   full knob

# ---- PROBE MODE (PROBE=1): swap ChongVerb for dsp/page2_probe.asm and expose
# all six page-2 display slots, to measure display-slot -> r6-offset directly.
# Temporary diagnostic; the normal build is unaffected.
import os
if os.environ.get("PROBE") == "1" or os.environ.get("XPROBE") == "1":
    FULLNAME["REVERB SERVER"] = b"X MEM PROBE" if os.environ.get("XPROBE") == "1" else b"P2 PROBE"
    ABBR["REVERB SERVER"] = b"PROB"
    ACTIVE_PARAMS["REVERB SERVER"] = [6, 7, 8, 9, 10, 11]   # page 2 only
    RENAMES["REVERB SERVER"] = [(i, b"") for i in range(6)] + \
                              [(i, f"P{i}".encode()) for i in range(6, 12)]
    DEFAULTS["REVERB SERVER"] = [(i, 0) for i in range(6, 12)]
    # Slots 9 and 11 inherit DARK's value COUNT of 2 (booleans, 0/1) -- and a
    # knob that maxes at 1 can never cross the probe's >64 threshold, so they
    # read as "does nothing" whether or not they are wired. Force every page-2
    # slot to a full 0..127 range so all six are actually sweepable.
    PROBE_COUNTS = {6: 128, 7: 3, 8: 128, 9: 3, 10: 128, 11: 3}

# ---- DSP code placement (task 13) ------------------------------------------
ASM_SRC = {"DELAY SERVER": "dsp/delay_server.asm",
           "REVERB SERVER": ("dsp/xmem_probe.asm" if os.environ.get("XPROBE") == "1"
                             else "dsp/page2_probe.asm" if os.environ.get("PROBE") == "1"
                             else "dsp/reverb_server.asm"),
           "SEND": "dsp/send_client.asm"}

# per payload: donor P addresses for CODE space, the proven null stub, the
# X:0x215/X:0x235 module address, and DELAY SERVER's payload-specific Y base
PP = {
    "A": dict(chorus=0x00eb7, plate=0x01000, spring=0x01252, dark=0x01679,
              nul_i=0x007c8, nul_p=0x007c9, xtab=0x400e2345, ybase=0x30000),
    "B": dict(chorus=0x00c77, plate=0x00dc0, spring=0x01012, dark=0x01439,
              nul_i=0x00588, nul_p=0x00589, xtab=0x400f5a10, ybase=0x38000),
}
DONOR_IDS = {"chorus": 0x12, "plate": 0x14, "spring": 0x15, "dark": 0x16}


def assemble(src_text, org):
    tmp = pathlib.Path("/tmp/build_bus_src.asm")
    tmp.write_text(src_text)
    subprocess.run([str(DIS), "-in", str(tmp), "-org", f"{org:x}",
                    "-out", "/tmp/build_bus.bin", "-sym", "/tmp/build_bus.sym"],
                   check=True, capture_output=True)
    blob = pathlib.Path("/tmp/build_bus.bin").read_bytes()
    words = [blob[i] | (blob[i + 1] << 8) | (blob[i + 2] << 16)
             for i in range(0, len(blob), 3)]
    syms = dict((k, int(v, 16)) for k, v in
                (l.split() for l in
                 pathlib.Path("/tmp/build_bus.sym").read_text().split("\n") if l))
    return words, syms["init"], syms["proc"]


def main():
    if not DIS.exists():
        sys.exit(f"missing {DIS} -- run ./setup.sh")
    img = bytearray(IMG.read_bytes())

    def rd32(a):
        return int.from_bytes(img[a - BASE:a - BASE + 4], "big")

    def wr32(a, v):
        img[a - BASE:a - BASE + 4] = v.to_bytes(4, "big")

    def wrw_p(a, v):
        i = a - BASE
        img[i], img[i + 1], img[i + 2] = v & 0xff, (v >> 8) & 0xff, (v >> 16) & 0xff

    # ==== 1. ColdFire menu tables (task 11) =================================
    cave_end = CLONE_BASE + CLONE_STRIDE * len(ORDER)
    if any(img[NEW_LIST - BASE:cave_end - BASE]):
        sys.exit("menu cave not free")

    clone_addr = {}
    print("=== ColdFire: three cloned descriptors (task 11) ===")
    for i, name in enumerate(ORDER):
        # from the donor's P, not its E -- the record is 0x192 bytes measured
        # FROM P, and its tail carries the parameter enable bitmap
        donor_P = DESC_DONORS[name] + 0x38
        clone_P = CLONE_BASE + i * CLONE_STRIDE
        img[clone_P - BASE:clone_P - BASE + DESC_LEN] = \
            img[donor_P - BASE:donor_P - BASE + DESC_LEN]
        new_id = NEW_IDS[name]
        img[clone_P - BASE + P_ID_BYTE] = new_id
        img[clone_P - BASE + P_ABBR:clone_P - BASE + P_ABBR + 5] = ABBR[name].ljust(5, b"\0")[:5]
        img[clone_P - BASE + P_FULLNAME:clone_P - BASE + P_FULLNAME + 13] = \
            FULLNAME[name].ljust(13, b"\0")[:13]
        for idx, label in RENAMES[name]:
            a = clone_P + P_PARAM_NAMES + idx * 6
            img[a - BASE:a - BASE + 6] = label.ljust(6, b"\0")[:6]
        for idx, val in DEFAULTS.get(name, []):
            img[clone_P - BASE + P_DEFAULTS + idx] = val
        # PER-PARAMETER DISPLAY FORMATTERS, P+0x0ca and P+0x0fa (12 x u32 each).
        # A cloned descriptor inherits the DONOR's formatter for every slot, and
        # the formatter decides how the value is drawn -- overriding the value
        # count entirely. DARK's slot 8 (MONO) and slot 11 (MIXF) carry
        # non-zero formatters, so our DIFF drew like an on/off and our ->DEL
        # drew as "MIX / SEND" no matter what count it was given. Stock uses 0
        # for a plain numeric parameter, so zero them for every slot we renamed.
        #
        # These arrays sit at offsets 2 mod 4, which is why a 4-aligned scan of
        # the record found "no pointer fields" and sent this investigation down
        # a blind alley for two rounds.
        if name == "REVERB SERVER":
            for idx in range(12):
                wr32(clone_P + 0x0ca + idx * 4, 0)
                wr32(clone_P + 0x0fa + idx * 4, 0)
            # MODE gets a STEPPED formatter rather than a plain knob. Surveyed
            # every stock effect: 0x4003c718 is what CHORUS.TAPS and SPRING
            # REV.TYPE use, and it copes with counts 3, 5 and 128 -- i.e. it is
            # the enumerated-selector renderer, which is the "like taps on
            # chorus" Sam asked for.
            # The alternative, 0x4003bc60 (FILTER.Q, count 4), draws real word
            # labels but they read "none|HP|LP|BOTH", which would be actively
            # wrong on a mode selector. Numbers beat wrong words.
            # BOTH arrays, not just 0x0ca. Setting 0x0ca alone reproduces
            # DELAY.TIME exactly -- formatter 0x4003c718 with 0x0fa = 0 -- and
            # DELAY.TIME renders as a PLAIN KNOB, which is what MODE did.
            # Every enumerated control in stock has both set:
            #   CHORUS.TAPS      count 5  0x4003c718 + 0x40047254
            #   SPRING REV.TYPE  count 3  0x4003c718 + 0x40047424
            #   FILTER.Q         count 4  0x4003bc60 + 0x40046c28
            #   DELAY.TIME       count 128 0x4003c718 + 0        <- plain knob
            # Taking CHORUS.TAPS's pair, the control Sam named.
            wr32(clone_P + 0x0ca + 7 * 4, 0x4003c718)
            wr32(clone_P + 0x0fa + 7 * 4, 0x40047254)
            # ...and P+0x12a MUST BE ZERO for a stepped control. Surveyed all
            # 20 stepped params in stock FX2 (count < 128): every single one
            # has 0x12a = 0, no exceptions. MODE sits in slot 7 and inherited
            # DARK's 0x400328e4 there, which is why it kept drawing as a plain
            # knob even with the right formatter pair.
            #
            # Only slot 7 is touched. Slots 6 and 8 also carry a non-zero
            # 0x12a and are working full-travel knobs on hardware, so a
            # non-zero value is fine FOR A KNOB -- it is specifically stepped
            # rendering that requires zero. Change one thing.
            wr32(clone_P + 0x12a + 7 * 4, 0)
        for idx, cnt in PAGE2_COUNTS.get(name, {}).items():
            wr32(clone_P + 0x9a + idx * 4, cnt)     # P+0x9a = value-count array
            wr32(clone_P + 0x6a + idx * 4, 0)       # min 0
        if os.environ.get("PROBE") == "1" and name == "REVERB SERVER":
            for idx, cnt in PROBE_COUNTS.items():
                wr32(clone_P + 0x9a + idx * 4, cnt)
                wr32(clone_P + 0x6a + idx * 4, 0)   # min 0: slot 7 showed -64   # P+0x9a = count array
        lo, hi = penable(ACTIVE_PARAMS[name])
        wr32(clone_P + P_PENABLE_LO, lo)
        wr32(clone_P + P_PENABLE_HI, hi)
        clone_addr[name] = clone_P
        print(f"  {name:14s} id 0x{new_id:02x}  clone P=0x{clone_P:08x}  "
              f"knobs {ACTIVE_PARAMS[name]}")

    for name in ORDER:
        wr32(FX2_IDS + NEW_IDS[name] * 4, clone_addr[name])

    # Exactly the three real entries -- no NONE. SEND with both levels at 0 is
    # already identical to "no effect" (it never writes the audio buffer, only
    # taps it), and unlike NONE it performs the per-block bus housekeeping, so
    # making every unassigned track a SEND removes the "first track set to NONE
    # stalls the bus" hazard by construction rather than patching around it.
    real = [(n, clone_addr[n]) for n in ORDER]
    entries = [p for _, p in real] + [0]
    assert len(entries) * 4 <= CLONE_BASE - NEW_LIST, "list overruns the clone cave"
    for i, v in enumerate(entries):
        wr32(NEW_LIST + i * 4, v)
    # and shrink the viewport to match, so there are no rows left to pad
    if rd32(ROWCOUNT_INSN) != 0x48780007:
        sys.exit(f"row-count site 0x{ROWCOUNT_INSN:08x} is not `pea (0x7).w` -- refusing")
    img[ROWCOUNT_AT - BASE:ROWCOUNT_AT - BASE + 2] = len(real).to_bytes(2, "big")
    for r in LIST_REFS:
        if rd32(r) != FX2_LIST:
            sys.exit(f"list ref at 0x{r:08x} not stock FX2_LIST -- refusing")
        wr32(r, NEW_LIST)
    for pos, name in enumerate(ORDER):
        wr32(ID2POS + NEW_IDS[name] * 4, pos)
    # A fresh part's FX2 id is 0. Rather than hunt down the part-init template,
    # alias id 0 to SEND: its descriptor, its cursor position, and (below) its
    # DSP dispatch. Every unassigned track is then a SEND automatically.
    wr32(FX2_IDS + NONE_ID * 4, clone_addr["SEND"])
    wr32(ID2POS + NONE_ID * 4, ORDER.index("SEND"))
    print(f"  chooser list = {len(real)} entries, no NONE, viewport shrunk to "
          f"{len(real)} rows (no padding)")
    print(f"  id 0x00 aliased to SEND: a fresh/unassigned track is a send\n")

    # ==== 2. DSP code placement + dispatch (task 13) ========================
    print("=== DSP: code placed, dispatch wired, both payloads ===")
    delay_src = pathlib.Path(ASM_SRC["DELAY SERVER"]).read_text()
    reverb_src = pathlib.Path(ASM_SRC["REVERB SERVER"]).read_text()
    if os.environ.get("PROBE") == "1":
        print("  *** PROBE BUILD: ChongVerb replaced by dsp/page2_probe.asm ***")
    send_src = pathlib.Path(ASM_SRC["SEND"]).read_text()
    # MODE=n substitutes a literal for the page-2 MODE read, so each character
    # can be auditioned locally. dsp_host cannot drive companion fields (its
    # -params only writes value<<16 into knob fields), so this is the only way
    # to hear the modes without a flash. Diagnostic only -- the normal build
    # reads the real slot.
    mode_env = os.environ.get("MODE")
    if mode_env is not None:
        assert reverb_src.count("; MODE_OVERRIDE") == 1
        reverb_src = reverb_src.replace(
            "; MODE_OVERRIDE", "        move    #>$%x,a" % int(mode_env))
        print(f"  *** MODE OVERRIDE: forced to {int(mode_env)} ***")

    if delay_src.count("$30000") != 1:
        sys.exit("expected exactly one $30000 literal in delay_server.asm")

    for tag, va, ln in PAYLOADS:
        pp = PP[tag]
        mods, _ = modules(bytes(img), va, ln)

        def record(addr):
            rec = [m for m in mods if m[0] == 0 and m[1] == addr]
            if len(rec) != 1:
                sys.exit(f"payload {tag}: expected one P module at 0x{addr:05x}")
            return rec[0]

        print(f"-- payload {tag} --")

        # ---- SEND -> CHORUS's module -----------------------------------
        _, _, cnt, off = record(pp["chorus"])
        words, init_a, proc_a = assemble(send_src, pp["chorus"])
        if len(words) > cnt:
            sys.exit(f"payload {tag}: SEND {len(words)} words > CHORUS's {cnt}")
        for i, w in enumerate(words):
            wrw_p(va + off + i * 3, w)
        wrw_p(pp["xtab"] + NEW_IDS["SEND"] * 3, init_a)
        wrw_p(pp["xtab"] + (32 + NEW_IDS["SEND"]) * 3, proc_a)
        wrw_p(pp["xtab"] + NONE_ID * 3, init_a)          # id 0 alias -> SEND,
        wrw_p(pp["xtab"] + (32 + NONE_ID) * 3, proc_a)   # so a fresh part sends
        print(f"  SEND          -> CHORUS  P:0x{pp['chorus']:05x} "
              f"({len(words)}/{cnt} words)  id 0x{NEW_IDS['SEND']:02x}")

        # ---- DELAY SERVER -> PLATE's module -----------------------------
        _, _, cnt, off = record(pp["plate"])
        src = delay_src.replace("$30000", f"${pp['ybase']:x}")
        words, init_a, proc_a = assemble(src, pp["plate"])
        if len(words) > cnt:
            sys.exit(f"payload {tag}: DELAY SERVER {len(words)} words > PLATE's {cnt}")
        for i, w in enumerate(words):
            wrw_p(va + off + i * 3, w)
        wrw_p(pp["xtab"] + NEW_IDS["DELAY SERVER"] * 3, init_a)
        wrw_p(pp["xtab"] + (32 + NEW_IDS["DELAY SERVER"]) * 3, proc_a)
        print(f"  DELAY SERVER  -> PLATE   P:0x{pp['plate']:05x} "
              f"({len(words)}/{cnt} words)  id 0x{NEW_IDS['DELAY SERVER']:02x}  "
              f"Y base 0x{pp['ybase']:x}")

        # ---- REVERB SERVER -> SPRING + DARK's front, same budget --------
        _, _, s_cnt, s_off = record(pp["spring"])
        _, _, d_cnt, d_off = record(pp["dark"])
        words, init_a, proc_a = assemble(reverb_src, pp["spring"])
        budget = s_cnt + d_cnt
        if len(words) > budget:
            sys.exit(f"payload {tag}: REVERB SERVER {len(words)} words > "
                      f"SPRING+DARK budget {budget}")
        head, tail = words[:s_cnt], words[s_cnt:]
        for i, w in enumerate(head):
            wrw_p(va + s_off + i * 3, w)
        for i, w in enumerate(tail):
            wrw_p(va + d_off + i * 3, w)
        wrw_p(pp["xtab"] + NEW_IDS["REVERB SERVER"] * 3, init_a)
        wrw_p(pp["xtab"] + (32 + NEW_IDS["REVERB SERVER"]) * 3, proc_a)
        print(f"  REVERB SERVER -> SPRING+DARK  {len(words)}/{budget} words  "
              f"id 0x{NEW_IDS['REVERB SERVER']:02x}")

        # ---- donor ids -> the proven-silent null stub, not our code ------
        for donor, eid in DONOR_IDS.items():
            wrw_p(pp["xtab"] + eid * 3, pp["nul_i"])
            wrw_p(pp["xtab"] + (32 + eid) * 3, pp["nul_p"])
        print(f"  donor ids (CHORUS/PLATE/SPRING/DARK) -> null stub "
              f"P:0x{pp['nul_i']:05x}/0x{pp['nul_p']:05x} -- FX1 selecting "
              f"any of them by name is now silent, not our code")

    # A MODE-forced build ignores the real page-2 slot, so it must never end up
    # wrapped and flashed -- it would look like a MODE knob that does nothing.
    # Give it its own path rather than overwriting the flashable image.
    out = OUT if mode_env is None else pathlib.Path(
        "out/mainos_bus_mode%d.bin" % int(mode_env))
    out.write_bytes(bytes(img))
    d = sum(1 for x, y in zip(IMG.read_bytes(), img) if x != y)
    print(f"\n{out}: {len(img):,} bytes, {d} changed"
          + ("   *** DIAGNOSTIC, MODE FORCED -- DO NOT FLASH ***"
             if mode_env is not None else ""))


if __name__ == "__main__":
    main()
