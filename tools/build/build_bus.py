#!/usr/bin/env python3
"""THE build: a remix and the user's stock OS image -> out/mainos_bus.bin.

    REMIX=<name> [BUILD=nn] [XBUS=1 SPEC=1 DEV=1 ...] python3 tools/build/build_bus.py

Assembles every selected DSP module, places it in the donor region (the
three stock reverbs' P code, and any other stock effect on neither chooser)
of each payload, writes the FX2/FX1 choosers and the descriptor clones,
installs every ColdFire cave, detour, poke and table, links the DRAM units
into the platform runtime and appends it behind the loader with any other
payload, and prints a report every gate parses. `make bus` is XBUS=1
SPEC=1; `make check` runs the gates over it.

Module order in a payload is `DspSection.priority`; the report shows the
live word count per module and the region's FREE. The records are
contiguous in loaded P memory but separated by headers in the file, so a
stream spanning them is split per record on the way in; contiguity is
asserted, not assumed.

Payload A's half of the 64K shared window is 0x30000-0x37FFF and payload
B's 0x38000-0x3FFFF, so `_sub` rewrites the literal `$30000` to
PP[tag]["ybase"] in a module's source text before assembling. It is a
blanket string replace over the whole source, comments included, applied
under XBUS to SEND and REVERB SERVER as well as DELAY SERVER: a
shared-window address that must not move on payload B is spelled as an
offset from a register-held base, never as `$30000`, and the count of that
literal is censused.
"""
import dataclasses, hashlib, json, os, pathlib, re, subprocess, sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401  (every tools/ dir on sys.path)
from dsp_modmap import BASE, IMG, PAYLOADS, modules  # noqa: E402
from remix import registry as remix_registry  # noqa: E402
from remix.registry import modules as remix_modules  # noqa: E402
from remix.schema import (DEFAULT_HARVEST, NO_FALLBACK, BusRole,  # noqa: E402
                          YBase)
from remix.state import fx1_hazard  # noqa: E402
from remix import stock as stock_mod  # noqa: E402
import label_fmt  # noqa: E402
import mode_names  # noqa: E402
from remix import ledger  # noqa: E402

OUT = pathlib.Path("out/mainos_bus.bin")
DIS = pathlib.Path("vendor/dsp56300/build/source/dsp_host/dsp_asm")

# ---- ColdFire menu tables (task 11, tools/build/build_menu.py, reproduced here) --
FX2_IDS = 0x400d5fdc
# ---- FX1's OWN descriptor tables ------------------------------------------
# The DSP dispatch is ONE table shared by both menus, but the descriptors are
# not: FX1 resolves its own. So a module replacing a stock effect runs from
# FX1 the moment it takes the id, while FX1's PAGE would still draw the stock
# effect's knob names unless these two are repointed as well -- the "a slot
# can draw a knob and publish nothing" family, in reverse.
#
# For a REPLACEMENT both writes are IN PLACE, because the effect is already
# on FX1: there is no list to grow and no cave to relocate into. (That is
# what tools/build/build_fx1.py's experiment needed, because it ADDS entries --
# the list ends at 0x400d608c and the FX2 list starts at 0x400d6090.)
FX1_IDS = 0x400d5f58        # id-indexed, 32 slots; NONE for an FX2-only effect
FX1_LIST = 0x400d6060       # the chooser list FX1 scrolls, NUL-terminated
FX1_NONE = 0x400d4618       # the descriptor every unused id points at
# FX1's OWN cursor-position table, the exact analogue of ID2POS below, found
# by reading the four tables in address order: FX1_LIST (11
# entries) at 0x400d6060, FX2_LIST (15) at 0x400d6090, then two 32-entry
# id->row tables back to back. It is FX1's because its FX2-only ids are all
# zero -- DELAY (0x08) and the three reverbs (0x14-0x16) -- where ID2POS
# gives them rows 0x0b and 0x0c-0x0e. tools/build/build_fx1.py's experiment never
# wrote it, which is a real gap: without it a project that has one of our
# effects stored on FX1 opens the chooser with the cursor on row 0.
FX1_ID2POS = 0x400d60d0
# The `lea.l FX1_LIST,aN` sites, the FX1 counterparts of LIST_REFS. Measured
# by tools/build/build_fx1.py, which repoints exactly these three.
FX1_LIST_REFS = [0x40037990, 0x40052706, 0x40059bd2]
# FX1's viewport literal, the analogue of ROWCOUNT_AT below. Located 3 Sep
# 2026: FX1's setup code is BYTE-IDENTICAL to FX2's apart from the list
# address, and this sits at the identical offset (+0x14) from FX1's own list
# reference, as `pea (0x7).w` = 4878 0007. It is what makes an FX1 list
# SHORTER than stock's eleven safe.
FX1_ROWCOUNT_INSN = 0x40059be4
FX1_ROWCOUNT_AT = 0x40059be6
FX2_LIST = 0x400d6090
ID2POS = 0x400d6150
LIST_REFS = [0x400375f4, 0x40052496, 0x40059a42]
DESC_LEN = 0x192
NEW_LIST = 0x400d6b00
# The other unclaimed zero run docs/firmware/MAINMENU.md section 5 names -- 2,064 bytes
# at 0x400d24d0. The menu shortcut cave is pinned at its start; label
# formatters overflow into it when the clone window is full (the character
# station's BUS-mode renames tipped the rig over by 56 bytes).
OVERFLOW_RUN = 0x400d24d0
OVERFLOW_RUN_END = 0x400d2ce0
SAFE_CAVE_CEIL = 0x400d8000
CLONE_BASE = 0x400d6b20
CLONE_STRIDE = 0x1a0
# NEW_LIST holds SEVEN rows plus its terminator before it runs into the
# first clone. A remix that keeps stock effects in the chooser
# can have more, so a longer list goes at the tail of the stock zero run
# instead -- 0x400d7bbc..0x400d7c3c, 32 entries -- and the clones and caves
# must stay below it. A list of seven or fewer stays at NEW_LIST, so every
# image that could be built before is byte-identical (refhash).
LONG_LIST = 0x400d7bbc
ZERO_RUN_END = 0x400d7c3c
# The chooser draws this many rows and scrolls a longer list, as stock does
# with its fifteen. A shorter list shrinks the viewport to match (below);
# a longer one must NOT grow it past the screen.
CHOOSER_ROWS = 7


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

# WHICH MODULES THIS IMAGE CARRIES. REMIX=<name> selects remixes/<name>.py;
# bus is the plain two-server selection and the one every refactor proves
# itself against (scripts/refhash.sh); bamsep26, the rig, is make's default. A module with no menu entry (a ColdFire patch) takes no chooser row,
# so ORDER is the menu modules alone, in the remix's declared order.
REMIX = remix_registry.remix(os.environ.get("REMIX")
                             or remix_registry.DEFAULT_REMIX)
ORDER = [k for k in REMIX.modules
         if remix_modules()[k].menu is not None]
# A HIDDEN module (schema.Remix.hidden) is placed, dispatched and cloned but
# takes no chooser row: it reaches a track through the project's stored id,
# never through the panel. ORDER is what the chooser lists; CARRIED is what
# gets a clone, code and a dispatch entry.
CARRIED = ORDER
HIDDEN = [k for k in CARRIED if k in REMIX.hidden]
ORDER = [k for k in CARRIED if k not in HIDDEN]
# THE FIRMWARE'S OWN NONE AS THE FALLBACK, for a remix with no bus (see
# schema.NO_FALLBACK, which is also what refuses it beside a bus
# participant). Unimplemented ids -- and id 0, a fresh part's -- then resolve
# to stock's NONE descriptor and to the payload's null stub, instead of to a
# module of ours that has to be listed and placed. The one thing it costs is
# a chooser row, restored at position 0 where a stock unit has it.
NO_FB = REMIX.fallback == NO_FALLBACK

BUILD_TAG = os.environ.get("BUILD", "79").encode()
if not (BUILD_TAG.isdigit() and 1 <= len(BUILD_TAG) <= 2):
    sys.exit(f"BUILD={BUILD_TAG.decode()!r}: the tag is appended to a 13-byte "
             f"name field, so it must be one or two digits")

# ---- the module tables, derived from modules/*/manifest.py ------------------
# One statement per fact, living in the module that owns it. These dicts keep
# their old shapes because the writers below are unchanged: what moved is
# where the data lives, not what it says.
#
# Ids are 0x06/0x07/0x09 rather than 0x01/0x02/0x03 because the first hardware
# test used the latter and got correct chooser names with dead knobs and
# garbage audio: 0x00-0x03 are the four values stock has always treated as
# bare synonyms for "no effect". 0x06 is the exact id tools/build/build_dspprobe.py
# proved runs custom DSP code on real hardware. schema.py enforces the range.
_MODS = remix_modules()
_SEL = [_MODS[k] for k in CARRIED]
# A STOCK row (tools/remix/stock.py) gets no clone, no code and no words:
# its descriptor and dispatch are where stock put them. The build writes
# its list row and cursor position and nothing else, so everything derived
# below that feeds a clone or a placement is over the CLONED modules only.
_CLONED = [m for m in _SEL if not m.is_stock]
CLONED_ORDER = [m.key for m in _CLONED]
STOCK_ROWS = [m.key for m in _SEL if m.is_stock]

DESC_DONORS = {m.key: m.menu.donor_desc for m in _CLONED}
NEW_IDS = {m.key: m.menu.fx2_id for m in _SEL}
ABBR = {m.key: m.menu.abbr for m in _CLONED}
FULLNAME = {m.key: m.menu.fullname + (BUILD_TAG if m.menu.build_tag else b"")
            for m in _CLONED}
# A name of None means "leave the donor's", which is a different thing from
# b"" (blank the slot). Both are in use: SEND blanks ten of FILTER's names.
# A HIDDEN module's twelve names are blanked (b"" -- not None, which would
# leave the donor's), so its track page draws no knobs. Counts, defaults and
# enable bits are untouched, which is what keeps the parameter writer and the
# frame builder working for the menu screen that edits it.
# ⚠️ NOT EVERY HIDDEN MODULE GETS BLANK NAMES. One descriptor serves BOTH
# menus, so blanking a module that is also on the FX1 chooser would empty its
# FX1 page too. A hidden module on FX1 loses its FX2 row and keeps its names;
# only a hidden module that is nowhere on FX1 is drawn empty.
BLANKED = [k for k in HIDDEN if k in REMIX.blanked]   # schema.Remix.blanked
RENAMES = {m.key: ([(i, b"") for i in range(12)] if m.key in BLANKED else
                   [(i, p.name) for i, p in enumerate(m.params)
                    if p.name is not None]) for m in _CLONED}
# Explicit per-knob defaults -- NOT the donor's, which are sized for a
# different algorithm on that slot. DARK REV's MIX default is 0 (a freshly
# selected reverb would be silent) and SPRING's TONE-slot default is 0 (our
# darkest setting); both look exactly like "the effect does nothing".
DEFAULTS = {m.key: [(i, p.default) for i, p in enumerate(m.params)
                    if p.default is not None] for m in _CLONED}
# The enable bitmap. A slot missing here is unreachable on hardware no matter
# how completely it is named, defaulted, counted and implemented -- and the
# inverse of the trap that a slot can draw a knob and publish nothing. Both
# have shipped.
ACTIVE_PARAMS = {m.key: m.active_params for m in _CLONED}
LINKED_PARAMS = {m.key: m.linked_params for m in _CLONED}
# Value counts. Page 2 pairs a knob field and a companion field per word (any
# count on either -- stock puts selects on even slots and knobs on odd; see
# docs/firmware/MAINMENU.md 9e). Historically "three knobs and three selects": the knob fields take
# 128, the companion byte fields take a small step count. Setting a companion
# to 128 does not make it continuous -- it stays a select and reads as a
# near-boolean, which is what hardware showed.
PAGE2_COUNTS = {m.key: {i: p.count for i, p in enumerate(m.params)
                        if p.count is not None} for m in _CLONED}
# Membership here also GATES the display-formatter pass below: a module with
# no stepped slot keeps its donor's formatters untouched, which is what SEND
# wants (FILTER's plain-numeric zeros, hardware-confirmed).
STEPPED_SLOTS = {m.key: m.stepped_slots for m in _CLONED if m.stepped_slots}
BIPOLAR_SLOTS = {m.key: m.bipolar_slots for m in _CLONED if m.bipolar_slots}
_DEF_ASM = {m.key: m.dsp.asm for m in _CLONED}


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


def penable(active, linked=()):
    """The two enable words: bit 0 of a slot's nibble draws it, bit 1 draws
    the link element to its left neighbour (PARAM_PAGES.md 3b)."""
    lo = hi = 0
    for i in active:
        bits = 3 if i in linked else 1
        if i < 8:
            lo |= bits << (4 * i)
        else:
            hi |= bits << (4 * (i - 8))
    return lo, hi


# ---- PROBE MODE (PROBE=1): swap BusVerb for dsp/page2_probe.asm and expose
# all six page-2 display slots, to measure display-slot -> r6-offset directly.
# Temporary diagnostic; the normal build is unaffected.
#
# Slots 9 and 11 inherit DARK's value COUNT of 2 (booleans, 0/1) -- and a knob
# that maxes at 1 can never cross the probe's >64 threshold, so they read as
# "does nothing" whether or not they are wired. Force every page-2 slot to a
# full 0..127 range so all six are actually sweepable.
#
# ⚠️ AT MODULE LEVEL DELIBERATELY. This sat INSIDE the TPROBE block below,
# where it was defined for the one mode that never reads it and undefined for
# the mode that does -- so PROBE=1 died on a NameError at the point of use,
# in every combination, for as long as anyone can tell. Only the PROBE arm
# applies these counts; keeping the table unconditional is what stops the
# definition and the use drifting into different branches again.
PROBE_COUNTS = {6: 128, 7: 3, 8: 128, 9: 3, 10: 128, 11: 3}

# True when the reverb's engine has been swapped for a diagnostic. Read below
# where the bus relocation is applied: a probe is not a bus client, so it is
# exempt from a check that exists to catch a real server reading the wrong
# memory.
_REVERB_IS_PROBE = any(os.environ.get(v) == "1"
                       for v in ("PROBE", "XPROBE", "TPROBE"))

if os.environ.get("PROBE") == "1" or os.environ.get("XPROBE") == "1":
    FULLNAME["REVERB SERVER"] = b"X MEM PROBE" if os.environ.get("XPROBE") == "1" else b"P2 PROBE"
if os.environ.get("TPROBE") == "1":
    FULLNAME["REVERB SERVER"] = b"TEMPO PROBE"    # streams the 0x30000 staging
                                                  # block; see dsp/tempoprobe.asm
    ABBR["REVERB SERVER"] = b"PROB"
    ACTIVE_PARAMS["REVERB SERVER"] = [6, 7, 8, 9, 10, 11]   # page 2 only
    RENAMES["REVERB SERVER"] = [(i, b"") for i in range(6)] + \
                              [(i, f"P{i}".encode()) for i in range(6, 12)]
    DEFAULTS["REVERB SERVER"] = [(i, 0) for i in range(6, 12)]

# ---- BURN MODE (BURN=1): swap BusVerb for dsp/burn_probe.asm, the same
# engine plus a knob-swept cycle burn on p3. Measures the per-DSP cycle
# ceiling, which has never actually been measured -- 1080 is a figure that was
# SURVIVED (REVERB_LOG.md, stageprobe5), not a wall anyone found. The knob is
# renamed BURN so the panel cannot be misread as a working LO control; its
# filter is bypassed in the asm. Everything else about the build is normal, on
# purpose: the number is only meaningful if the engine under it is the real one.
# ---- XBUS MODE (XBUS=1): the CROSS-CORE BUS test ---------------------------
# The bus accumulators move from core-private Y:0x900 into the shared window,
# and housekeeping is gated to payload A. Names say so on the panel, because
# this build's BusVerb is NOT the shipping one and BusDelay is a bare stub.
if os.environ.get("XBUS") == "1":
    if os.environ.get("SPEC") == "1" or os.environ.get("DEV") == "1":
        FULLNAME["REVERB SERVER"] = b"BusVerb" + BUILD_TAG
        FULLNAME["DELAY SERVER"] = b"BusDelay" + BUILD_TAG
    elif not _REVERB_IS_PROBE:
        # ⚠️ `elif not _REVERB_IS_PROBE`, not `else`. This block runs AFTER the
        # probe naming above, so a plain `else` renamed a PROBE build's reverb
        # slot to XVerb -- a diagnostic image whose panel claimed to be the
        # architecture test. That is the exact ambiguity BUILD_TAG exists to
        # remove, and it is worse here than a missing name: three debugging
        # rounds have already been lost to not knowing which firmware was
        # running. A probe keeps the name that says what it is.
        FULLNAME["REVERB SERVER"] = b"XVerb" + BUILD_TAG
        ABBR["REVERB SERVER"] = b"XVRB"
        FULLNAME["DELAY SERVER"] = b"NotUsed" + BUILD_TAG
        ABBR["DELAY SERVER"] = b"NONE"

# ---- MARKER MODE (MARKER=1): staged audible execution markers --------------
if os.environ.get("MARKER") == "1":
    FULLNAME["REVERB SERVER"] = b"MrkVerb" + BUILD_TAG
    ABBR["REVERB SERVER"] = b"MRKV"

# BURN=1 has two shapes. With SPEC=1 it is the RIG BURN: the
# shipping image plus a cycle-burn knob on SEND's second slot, on every core,
# so the burn sweep prices the real rig on the core it is dialled on (the
# worst layout is the DELAY core's, where the reverb's knob never was). The
# servers are untouched. Without SPEC it is the older diagnostic image: the
# reverb's own burn blocks and the alias probe in the delay's slot.
RIG_BURN = os.environ.get("BURN") == "1" and os.environ.get("SPEC") == "1"
if RIG_BURN and "SEND" not in ACTIVE_PARAMS:
    sys.exit(f"BURN=1 SPEC=1: remix {REMIX.name!r} carries no SEND -- the rig burn "
             f"has no knob to sit on; nothing to build")
if RIG_BURN:
    # BURN is SEND's PAGE-2 slot 6 ($c's knob field, CC 62). It was page-1
    # slot 1 until 16 Sep 2026 (image 32B, step 1 forever on two stamped
    # projects): under the port the word at x:(r6+$1) read 0x378f00 with
    # every stored byte 0 and 0x69f400 with one track's byte at 100 -- the
    # same word on every track, whatever the donor -- so the burn ran 7,111
    # loops at "0" and the frame never finished. A page-2 knob field is what
    # verify_set proves raw, byte for byte, for every track of a real project.
    RENAMES["SEND"] = [(i, v) for i, v in RENAMES.get("SEND", []) if i != 6] + [(6, b"BURN")]
    ACTIVE_PARAMS["SEND"] = sorted(set(ACTIVE_PARAMS["SEND"]) | {6})
    DEFAULTS["SEND"] = [(i, v) for i, v in DEFAULTS.get("SEND", []) if i != 6] + [(6, 0)]
    PAGE2_COUNTS.setdefault("SEND", {})[6] = 128

    FULLNAME["SEND"] = b"SendBurn" + BUILD_TAG
elif os.environ.get("BURN") == "1":
    FULLNAME["REVERB SERVER"] = b"BurnProb" + BUILD_TAG
    ABBR["REVERB SERVER"] = b"BURN"
    # BusDelay's slot carries the X/Y ALIAS probe in this build. It is a
    # placeholder algorithm, so its 507 words are the cheapest diagnostic space
    # on the chip. dsp/alias_probe.asm rides the SAME per-payload
    # $30000 -> $38000 substitution DELAY SERVER already uses, but as a BASE
    # rather than a role select: payload A tests its own half of the shared
    # window, payload B tests its own. Both are valid alias tests and it needs
    # no new build machinery.
    #
    # It replaced dsp/shared_probe.asm, which needed TWO instances (a writer
    # and a reader) and so could never run -- two copies of the same effect
    # corrupt audio after ~5.45 s, on the same bank or across banks, whatever
    # address they use (hardware, 7 Aug). The alias question needs only one.
    FULLNAME["DELAY SERVER"] = b"AliasPrb" + BUILD_TAG
    ABBR["DELAY SERVER"] = b"ALIA"

    def _set(table, name, idx, val):
        table[name] = [(i, v) for i, v in table[name] if i != idx] + [(idx, val)]

    _set(RENAMES, "DELAY SERVER", 1, b"ADDR")   # base + 0x1000/3000/5000/7000
    _set(RENAMES, "DELAY SERVER", 2, b"SPACE")  # 0 = read back via X, >0 via P
    _set(DEFAULTS, "DELAY SERVER", 1, 0)        # base + 0x1000
    _set(DEFAULTS, "DELAY SERVER", 2, 0)        # X first -- the safe one
    # APPEND, do not replace. Assigning a fresh list here dropped p9/p10's
    # names and p7's MODE default on the first attempt, and verify_menu.py
    # caught all three -- an out-of-range page-2 default is not cosmetic, it
    # is used as an index and stalled the sequencer on hardware once already.
    RENAMES["REVERB SERVER"].append((3, b"BURN"))
    # DEFAULTS already carries (3, 0), so the knob boots at zero burn with no
    # override needed -- which is the one value that must be safe.

# ---- DEV=1: the local-render escape hatch -----------------------------------
DEV = os.environ.get("DEV") == "1"
if DEV:
    _clash = [v for v in ("BURN", "PROBE", "XPROBE", "TPROBE", "DELAYPROBE")
              if os.environ.get(v) == "1"]
    if _clash:
        sys.exit(f"DEV=1 is a local render build and cannot be combined with "
                 f"{'/'.join(_clash)}=1 -- those replace a server with a probe, "
                 f"which is the opposite of what DEV is for")

# ---- SPEC=1: SPECIALIZE THE PAYLOADS ---------------------------------------
SPEC = os.environ.get("SPEC") == "1"
if SPEC:
    if os.environ.get("XBUS") != "1":
        sys.exit("SPEC=1 requires XBUS=1. Specializing without relocating the "
                 "bus into the shared window leaves the accumulators in "
                 "core-private Y:0x900, so each core's tracks would feed only "
                 "the one server their own core carries and could never reach "
                 "the other. That is not the target architecture and it would "
                 "still make sound, which is the dangerous part -- run "
                 "XBUS=1 SPEC=1")
    if DEV:
        # DEV=1 + SPEC=1: payload placement follows SPEC rules (reverb→A,
        # delay→B) but the build writes the DEV output paths. dsp_host can
        # still render the reverb from payload A; the delay has no local
        # render any more -- it outgrew payload A with the 8-line engine.
        print("  DEV=1 + SPEC=1: rendering reverb only (delay is on payload B, "
              "which dsp_host cannot boot)")
    _clash = [v for v in ("PROBE", "XPROBE", "TPROBE", "DELAYPROBE")
              if os.environ.get(v) == "1"]
    if _clash:
        sys.exit(f"SPEC=1 cannot be combined with {'/'.join(_clash)}=1 -- "
                 f"those replace a server with a probe (BURN=1 is allowed: "
                 f"with SPEC it is the rig burn on SEND, see RIG_BURN)")

# ---- DSP code placement (task 13) ------------------------------------------
           # DLSRC= swaps the delay engine for an alternate source file --
           # the same mechanism as RVSRC below, for the same reason: the
           # BusDelay v2 refactor gate (tools/verify/verify_delay.py) builds and
           # renders two engines in one script and compares byte-for-byte.
           # It only means anything where the real delay is placed (DEV/SPEC/
           # plain); the XBUS stub and BURN probe arms ignore it.
           # Any module the three special cases below do not name (a remix
           # contribution like a new insert) builds from its manifest's
           # declared source, unconditionally -- the probe/override arms are
           # all reverb- or delay-shaped and do not apply to it.
ASM_SRC = {k: v for k, v in {**_DEF_ASM,
           "DELAY SERVER": ((os.environ.get("DLSRC") or _DEF_ASM.get("DELAY SERVER"))
                            if DEV or SPEC
                            else "dsp/silence_stub.asm" if os.environ.get("XBUS") == "1"
                            else "dsp/alias_probe.asm" if os.environ.get("BURN") == "1"
                            else os.environ.get("DLSRC") or _DEF_ASM.get("DELAY SERVER")),
           "REVERB SERVER": ("dsp/xmem_probe.asm" if os.environ.get("XPROBE") == "1"
                             else "dsp/page2_probe.asm" if os.environ.get("PROBE") == "1"
                             else "dsp/tempoprobe.asm" if os.environ.get("TPROBE") == "1"
                             else os.environ.get("RVSRC") or _DEF_ASM.get("REVERB SERVER")),
           "SEND": _DEF_ASM.get("SEND")}.items() if k in CARRIED}

# per payload: donor P addresses for CODE space, the proven null stub, the
# X:0x215/X:0x235 module address, and DELAY SERVER's payload-specific Y base
PP = {
    "A": dict(chorus=0x00eb7, plate=0x01000, spring=0x01252, dark=0x01679,
              nul_i=0x007c8, nul_p=0x007c9, xtab=0x400e2345, ybase=0x30000),
    "B": dict(chorus=0x00c77, plate=0x00dc0, spring=0x01012, dark=0x01439,
              nul_i=0x00588, nul_p=0x00589, xtab=0x400f5a10, ybase=0x38000),
}
# DEV only: where the DELAY SERVER's code lives when it is NOT packed into
# the donor region. The hatch region capped
# the delay at ~583 words (24 free after stage 1) vs payload B's ~1,953 --
# the redesign would have outgrown its own render loop one stage in. dsp_host
# has NO 8K P wall and no OMR model (P is flat 0x80000 words, measured
# 12 Aug), so a DEV build can run the delay from any address; the payload
# itself has no room for a new module record (6 bytes of slack, measured), so
# the record is appended to the .mem DUMP instead -- the dump is the only
# thing dsp_host boots, and a DEV image is never flashed. 0x04000 is clear of
# every P record dsp_host loads (stock tops out at 0x01fdf below the shared
# window) and below send_probe's `init < 0x20000` plausibility bound. On
# hardware this address does not exist (the 8K OMR wall) -- which is fine,
# because on hardware the delay ships IN REGION in payload B, unchanged.
DEV_DELAY_P = 0x04000

DONOR_IDS = {"plate": 0x14, "spring": 0x15, "dark": 0x16}
if DEV:
    DONOR_IDS["chorus"] = 0x12      # DEV takes CHORUS's module for the space

# Stock Echo Freeze Delay. Untouched by a normal build: its descriptor, its
# FX2_IDS entry and its (passthrough) dispatch are all stock. DELAYPROBE=1 puts
# it back in the menu and points its dispatch at dsp/silence_stub.asm -- see
# that file for what each audible outcome would mean.
STOCK_DELAY_ID = 0x08
STOCK_DELAY_P = 0x400d4ace          # DELAY's E (0x400d4a96) + 0x38


# ---- DEV repro hooks for outsider modules ----------------------------------
# The three core sources have their override arms written out at the top of
# main() (MODE, DMODE, DFRZAT and the rest). A module that arrives later needs
# the same kind of lever without another special case in the placement loop,
# so it declares a marker in its source and a rule here.
#
# ⚠️ EVERY HOOK HERE IS DEV-ONLY, for the reason DFRZAT is: the counter word
# lives at Y:0x37FFE in payload A's owned half of the shared window (init-
# zeroed, above the bus scratch at 0x360d2), which is free ground in a DEV
# layout and is NOT a promise about any shipping one.
def _dev_hooks(key, src):
    if key != "NIMBUS":
        return src
    at = os.environ.get("NFRZAT")
    if at is None:
        return src
    if os.environ.get("DEV") is None:
        sys.exit("NFRZAT=n is a DEV-only repro hook (its counter word lives "
                 "in payload A's shared-window half) -- set DEV=1")
    if src.count("; NFRZ_OVERRIDE") != 1:
        sys.exit("NFRZAT=n set but the NIMBUS source has no single "
                 "; NFRZ_OVERRIDE marker")
    # Branchless, and the same shared-flag idiom as everywhere else: `sub`
    # sets N once, the two Tcc read it, and the interleaved immediate moves
    # do not disturb the condition codes.
    src = src.replace(
        "; NFRZ_OVERRIDE",
        "        move    y:>$37ffe,a\n"
        "        add     #>1,a\n"
        "        move    a,y:>$37ffe\n"
        "        move    #>%d,x0\n"
        "        sub     x0,a\n"
        "        move    #>0,x0\n"
        "        tmi     x0,a\n"
        "        move    #>1,x0\n"
        "        tpl     x0,a" % int(at))
    print(f"  *** NFRZAT OVERRIDE: Nimbus freezes after {int(at)} "
          f"post-warm blocks ***")
    return src


_SCRATCH = None


def assemble(src_text, org):
    global _SCRATCH
    if _SCRATCH is None:
        import tempfile
        _SCRATCH = pathlib.Path(tempfile.mkdtemp(prefix="build_bus."))
    tmp, binf, symf = (_SCRATCH / n for n in ("src.asm", "out.bin", "out.sym"))
    tmp.write_text(src_text)
    subprocess.run([str(DIS), "-in", str(tmp), "-org", f"{org:x}",
                    "-out", str(binf), "-sym", str(symf)],
                   check=True, capture_output=True)
    blob = binf.read_bytes()
    words = [blob[i] | (blob[i + 1] << 8) | (blob[i + 2] << 16)
             for i in range(0, len(blob), 3)]
    syms = dict((k, int(v, 16)) for k, v in
                (l.split() for l in symf.read_text().split("\n") if l))
    return words, syms["init"], syms["proc"]


def main():
    _p = os.environ.get("DELAYPROBE", "")
    probe = {"1": "silence", "silence": "silence", "send": "send",
             "stock": "stock"}.get(_p)
    if _p and not probe:
        sys.exit("DELAYPROBE must be 'stock', 'silence' or 'send'")
    delayprobe = probe is not None
    if delayprobe:
        # Make it unmistakable ON THE UNIT which firmware is running. Three
        # debugging rounds were lost to exactly this ambiguity, and a probe
        # build that reads "BusVerb22" like the product build is that hazard
        # in its worst form -- this one deliberately silences a stock effect.
        FULLNAME["REVERB SERVER"] = (b"BusVerb" + BUILD_TAG +
                                     {"silence": b"P", "send": b"S",
                                      "stock": b"C"}[probe])
    if not DIS.exists():
        sys.exit(f"missing {DIS} -- run 'make setup'")
    # Resource collisions between the selected modules, BEFORE a byte is
    # written. Silent when clean: the build report is parsed by other tools,
    # so a check that passes says nothing.
    _clashes = ledger.check([remix_modules()[k] for k in REMIX.modules])
    if _clashes:
        sys.exit("remix %r has colliding modules:\n  %s"
                 % (REMIX.name, "\n  ".join(_clashes)))
    img = bytearray(IMG.read_bytes())

    def rd32(a):
        return int.from_bytes(img[a - BASE:a - BASE + 4], "big")

    def wr32(a, v):
        img[a - BASE:a - BASE + 4] = v.to_bytes(4, "big")

    def wrw_p(a, v):
        i = a - BASE
        img[i], img[i + 1], img[i + 2] = v & 0xff, (v >> 8) & 0xff, (v >> 16) & 0xff

    # ==== 1. ColdFire menu tables (task 11) =================================
    if os.environ.get("TEMPOCAVE") == "replay":
        FULLNAME["DELAY SERVER"] = b"BusDlyRPL" + BUILD_TAG
    elif os.environ.get("NOTEMPO") == "1":
        FULLNAME["DELAY SERVER"] = b"BusDlyNOC" + BUILD_TAG
    cave_end = CLONE_BASE + CLONE_STRIDE * len(CLONED_ORDER)
    if any(img[NEW_LIST - BASE:cave_end - BASE]):
        sys.exit("menu cave not free")

    # ---- both name fields are NUL-TERMINATED --------------------------------
    for name in CLONED_ORDER:
        if len(ABBR[name]) > 4:
            sys.exit(f"abbr {ABBR[name]!r} for {name} is {len(ABBR[name])} "
                     f"characters -- the field is 5 bytes NUL-terminated, so "
                     f"4 is the maximum")
        if len(FULLNAME[name]) > 12:
            sys.exit(f"panel name {FULLNAME[name]!r} for {name} is "
                     f"{len(FULLNAME[name])} characters (build tag included) "
                     f"-- the field is 13 bytes NUL-terminated, so 12 is the "
                     f"maximum")

    clone_addr = {}
    print("=== ColdFire: three cloned descriptors (task 11) ===")
    for i, name in enumerate(CLONED_ORDER):
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
        if name in STEPPED_SLOTS:
            for idx in range(12):
                wr32(clone_P + 0x0ca + idx * 4, 0)
                wr32(clone_P + 0x0fa + idx * 4, 0)
            for step_slot in STEPPED_SLOTS[name]:
                wr32(clone_P + 0x0ca + step_slot * 4, 0x4003c718)
                # CHORUS.TAPS' tick widget has five positions hard-coded and
                # draws nothing above value 4. Wider selects use the plain
                # dial (B=0) while their A formatter still prints each label.
                _count = _MODS[name].params[step_slot].count
                wr32(clone_P + 0x0fa + step_slot * 4,
                     0x40047254 if _count is not None and _count <= 5 else 0)
            # ...and P+0x12a MUST BE ZERO for a stepped control. Surveyed all
            # 20 stepped params in stock FX2 (count < 128): every single one
            # has 0x12a = 0, no exceptions. MODE sits in slot 7 and inherited
            # DARK's 0x400328e4 there, which is why it kept drawing as a plain
            # knob even with the right formatter pair. Slots 9 and 11 already
            # inherit 0x12a = 0 from DARK (its slots 9/11 are 0), so only slot 7
            # needs zeroing -- but do all three explicitly, it is idempotent.
            # The delay needed exactly the same one slot: SPRING's BAL sits in
            # slot 7 too, and carries the same 0x400328e4.
            for step_slot in STEPPED_SLOTS[name]:
                wr32(clone_P + 0x12a + step_slot * 4, 0)
        # A BIPOLAR knob (14 Sep 2026: Character's WDTH and TONE, "0 at
        # neutral, negative for mono"): SPRING BAL's exact triple, read from
        # the stock descriptor at donor_desc + 0x38 -- A = 0x4003c7a0 (the
        # balance dial), B = 0, and 0x12a = 0x400328e4 (the signed number
        # renderer, which DARK's slot 5 already carried). The value the DSP
        # reads is still 0..127; only the drawing changes.
        for bi_slot in BIPOLAR_SLOTS.get(name, ()):
            wr32(clone_P + 0x0ca + bi_slot * 4, 0x4003c7a0)
            wr32(clone_P + 0x0fa + bi_slot * 4, 0)
            wr32(clone_P + 0x12a + bi_slot * 4, 0x400328e4)
        for idx, cnt in PAGE2_COUNTS.get(name, {}).items():
            wr32(clone_P + 0x9a + idx * 4, cnt)     # P+0x9a = value-count array
            wr32(clone_P + 0x6a + idx * 4, 0)       # min 0
        if os.environ.get("PROBE") == "1" and name == "REVERB SERVER":
            for idx, cnt in PROBE_COUNTS.items():
                wr32(clone_P + 0x9a + idx * 4, cnt)
                wr32(clone_P + 0x6a + idx * 4, 0)   # min 0: slot 7 showed -64   # P+0x9a = count array
        lo, hi = penable(ACTIVE_PARAMS[name], LINKED_PARAMS.get(name, ()))
        wr32(clone_P + P_PENABLE_LO, lo)
        wr32(clone_P + P_PENABLE_HI, hi)
        clone_addr[name] = clone_P
        print(f"  {name:14s} id 0x{new_id:02x}  clone P=0x{clone_P:08x}  "
              f"knobs {ACTIVE_PARAMS[name]}")

    for name in CLONED_ORDER:
        wr32(FX2_IDS + NEW_IDS[name] * 4, clone_addr[name])
    # ---- a REPLACEMENT also takes over the stock effect's FX1 page --------
    for name in CLONED_ORDER:
        rep = _MODS[name].menu.replaces
        if not rep:
            continue
        stock_P = _MODS[rep].menu.donor_desc + 0x38
        slot = FX1_IDS + NEW_IDS[name] * 4
        cur = rd32(slot)
        if cur == FX1_NONE:
            print(f"  {name:14s} replaces {rep}, which FX1 does not list -- "
                  f"its FX1 page is left alone (adding a row needs the list "
                  f"relocated; see tools/build/build_fx1.py)")
            continue
        if cur != stock_P:
            sys.exit(f"{name}: FX1_IDS[0x{NEW_IDS[name]:02x}] is 0x{cur:08x}, "
                     f"not stock {rep}'s 0x{stock_P:08x} -- refusing to "
                     f"repoint a table that is not where we think it is")
        # ⚠️ AN INHERITED FX1 ROW IS STILL AN FX1 ROW. This is the path the
        # schema's `replaces` note described as "Nothing checks this": the
        # module lands on FX1 whether or not it can survive there, and the
        # three ways it cannot are the same three Remix.fx1 refuses. The
        # difference is that here the row is not asked for -- it comes with
        # the id -- so the refusal has to name the way out.
        _hz = fx1_hazard(_MODS[name])
        if _hz:
            sys.exit(f"{name}: replacing {rep} puts it on FX1 too, and "
                     f"{_hz}. Either take an id FX1 does not list, or make "
                     f"it buffer-free (docs/remixer/MODULES.md, 'only a buffer-free "
                     f"insert may take an FX1 row')")
        wr32(slot, clone_addr[name])
        # ...and the row the encoder scrolls, which holds the descriptor
        # pointer directly. Exactly one entry may match, or the assumption
        # about this table is wrong and nothing should be written.
        hits = []
        a = FX1_LIST
        while rd32(a) != 0:
            if rd32(a) == stock_P:
                hits.append(a)
            a += 4
            if a > FX1_LIST + 32 * 4:
                sys.exit("FX1 chooser list has no terminator")
        if len(hits) != 1:
            sys.exit(f"{name}: {rep} appears {len(hits)} times in the FX1 "
                     f"chooser list -- expected exactly one")
        wr32(hits[0], clone_addr[name])
        print(f"  {name:14s} REPLACES stock {rep} on FX1 too: id table "
              f"0x{slot:08x} and chooser row 0x{hits[0]:08x} -> "
              f"0x{clone_addr[name]:08x}")
    # A stock row's descriptor is the one stock ships, at P = E + 0x38, and
    # its FX2_IDS entry must still be stock's -- the two are the same
    # pointer on a pristine image, and nothing above may have touched it.
    for name in STOCK_ROWS:
        stock_P = _MODS[name].menu.donor_desc + 0x38
        if rd32(FX2_IDS + NEW_IDS[name] * 4) != stock_P:
            sys.exit(f"{name}: FX2_IDS[0x{NEW_IDS[name]:02x}] is not its "
                     f"stock descriptor -- refusing to list it")
        clone_addr[name] = stock_P
        print(f"  {name:14s} id 0x{NEW_IDS[name]:02x}  STOCK P=0x{stock_P:08x}"
              f"  (no clone, no code: the row is the only edit)")
    if delayprobe == "send" and NO_FB:
        sys.exit("DELAYPROBE=send reuses the SEND client, and this remix has "
                 f"no SEND (fallback={NO_FALLBACK})")
    if delayprobe and "DELAY" in ORDER:
        sys.exit("DELAYPROBE puts stock DELAY back in the menu, but this remix "
                 "already lists it -- drop one")

    # Exactly the three real entries -- no NONE. SEND with both levels at 0 is
    # already identical to "no effect" (it never writes the audio buffer, only
    # taps it), and unlike NONE it performs the per-block bus housekeeping, so
    # making every unassigned track a SEND removes the "first track set to NONE
    # stalls the bus" hazard by construction rather than patching around it.
    real = [(n, clone_addr[n]) for n in ORDER]
    if NO_FB:
        # NONE goes back where stock has it: list position 0. It clones no
        # descriptor and places no code -- FX1_NONE is the firmware's own,
        # already in the image -- so the row is four bytes of cave and the
        # only edit.
        real = [("NONE", FX1_NONE)] + real
    if delayprobe:
        # Stock DELAY needs no clone -- it has its own descriptor and its own
        # FX2_IDS entry, both untouched by this build. It only needs putting
        # back in the list so it can be selected.
        real = real + [("DELAY (stock)", STOCK_DELAY_P)]
    entries = [p for _, p in real] + [0]
    if len(entries) * 4 <= CLONE_BASE - NEW_LIST:
        list_addr, cave_limit = NEW_LIST, ZERO_RUN_END
    else:
        # More than seven rows: the list moves to the tail of the zero run
        # and everything else (clones, caves) has to end below it.
        list_addr, cave_limit = LONG_LIST, LONG_LIST
        if len(entries) * 4 > ZERO_RUN_END - LONG_LIST:
            sys.exit(f"chooser list of {len(real)} rows overruns the long "
                     f"list cave ({(ZERO_RUN_END - LONG_LIST) // 4 - 1} max)")
        if any(img[LONG_LIST - BASE:ZERO_RUN_END - BASE]):
            sys.exit("long chooser list cave not free")
        if cave_end > LONG_LIST:
            sys.exit(f"{len(CLONED_ORDER)} descriptor clones run into the "
                     f"long chooser list at 0x{LONG_LIST:08x}")
    for i, v in enumerate(entries):
        wr32(list_addr + i * 4, v)

    # Octakit's machine-selection runtime hardcodes the stock FX2 chooser
    # table at 0x400d6090 and accepts cursor positions 0..14. OCTABAM moves
    # the live chooser elsewhere, so mirror the active list back into the
    # original 15-row stock table when Octakit is present. This keeps
    # Octakit's descriptor/payload validation coherent without modifying
    # Octakit itself.
    if "OCTAKIT" in REMIX.modules:
        if len(real) > 15:
            sys.exit(
                "OCTAKIT supports at most 15 FX2 chooser rows: "
                "its machine-selection runtime accepts cursor 0..14"
            )

        for i in range(16):
            wr32(FX2_LIST + i * 4,
                 entries[i] if i < len(entries) else 0)

    # and size the viewport: shrink it to a short list so there are no rows
    # left to pad, never grow it past the seven the screen has -- a longer
    # list scrolls, as stock's fifteen-entry list does.
    if rd32(ROWCOUNT_INSN) != 0x48780007:
        sys.exit(f"row-count site 0x{ROWCOUNT_INSN:08x} is not `pea (0x7).w` -- refusing")
    rows = min(CHOOSER_ROWS, len(real))
    img[ROWCOUNT_AT - BASE:ROWCOUNT_AT - BASE + 2] = rows.to_bytes(2, "big")
    for r in LIST_REFS:
        if rd32(r) != FX2_LIST:
            sys.exit(f"list ref at 0x{r:08x} not stock FX2_LIST -- refusing")
        wr32(r, list_addr)
    # The fallback's cursor position. A HIDDEN fallback has no row of its
    # own, so there is no position to point at: park the cursor at 0. A
    # fresh track then dispatches to the fallback's code and its chooser
    # opens on row 0, which in a remix that hides its fallback is whatever
    # row 0 is -- or nothing, if the chooser is empty by design.
    fb_pos = (0 if (NO_FB or REMIX.fallback in HIDDEN)
              else ORDER.index(REMIX.fallback))
    # The cursor position of every listed effect, past the NONE row if one
    # was restored -- ID2POS is an index into `real`, not into ORDER.
    for pos, name in enumerate(ORDER):
        wr32(ID2POS + NEW_IDS[name] * 4, pos + (1 if NO_FB else 0))
    # A HIDDEN module has no row, so it has no cursor position of its own.
    # Point it at the fallback's, so opening the chooser on the track that
    # hosts it lands somewhere real instead of on whatever stock left there.
    for name in HIDDEN:
        wr32(ID2POS + NEW_IDS[name] * 4, fb_pos)
    # ==== 1b. ColdFire caves, from whichever modules carry them =============
    # A cave is how a module changes the firmware's BEHAVIOUR rather than
    # adding an effect: assert the hook site still holds the stock bytes,
    # plant a jsr to the cave, and let the cave replay what it displaced
    # before doing its own work. The addresses, the pinned machine code, the
    # .s sources and the reasoning all live in the owning module's manifest.
    # This is only the installer, and it is generic: a module contributing
    # caves needs no change here.
    #
    # No cave is installed if NOTEMPO=1, and none if the remix carries no
    # module that has any -- in both cases the DSP side reads zeros and SYNC
    # is a no-op by design.
    import shutil, tempfile
    _sym = {}                       # cave/unit label -> {symbol: address}
    _exports = {}                   # GLOBAL symbols of every unit linked so
                                    # far -> the --defsym set later units
                                    # resolve their cross-unit references from

    def _link(src, at, cpu, work, sections=(), defsyms=(), incdir=None):
        """Assemble `src` and link it at `at`; return (bytes, symbols,
        globals). `sections` = objcopy -j selection (empty = every alloc
        section). `defsyms` = (name, value) pairs for symbols defined by
        units already placed. `incdir` = an `.include` search directory
        (a per-remix generated include, schema.Linked.include)."""
        work = pathlib.Path(work)
        work.mkdir(parents=True, exist_ok=True)
        o, e, b = work / "u.o", work / "u.elf", work / "u.bin"
        _ld = ["m68k-elf-ld", f"-Ttext=0x{at:x}"] + \
              [f"--defsym={n}=0x{v:x}" for n, v in defsyms] + ["-o", e, o]
        _oc = ["m68k-elf-objcopy", "-O", "binary"] + \
              [x for s in sections for x in ("-j", s)] + [e, b]
        _as = ["m68k-elf-as", f"-mcpu={cpu}"] + (["-I", incdir] if incdir else []) + ["-o", o, src]
        for _args in (_as, _ld, _oc):
            _r = subprocess.run([str(a) for a in _args], capture_output=True, text=True)
            if _r.returncode:
                sys.exit(f"{src}: {_args[0]} failed\n{_r.stderr[-2000:]}")
        _nm = subprocess.run(["m68k-elf-nm", str(e)], capture_output=True, text=True).stdout
        _rows = [f for f in (l.split() for l in _nm.splitlines()) if len(f) == 3]
        return (pathlib.Path(b).read_bytes(),
                {f[2]: int(f[0], 16) for f in _rows},
                {f[2]: int(f[0], 16) for f in _rows if f[1].isupper() and f[1] != "U"})

    _toolchain = all(shutil.which(t) for t in
                     ("m68k-elf-as", "m68k-elf-ld", "m68k-elf-objcopy", "m68k-elf-nm"))
    _caves = [c for k in REMIX.modules for c in remix_modules()[k].cf_patches]
    # A cave that exists only to draw a BLANKED module's slot (a formatter
    # registration naming a module whose page draws no knobs) is dead
    # weight: drop it before it is placed (5 Sep 2026 -- BusDelay's TIME
    # formatter, 288 B the bus screen needs on the rig).
    _caves = [c for c in _caves
              if not (c.registers_formatter is not None
                      and c.registers_formatter.module in BLANKED)]
    _replay = os.environ.get("TEMPOCAVE") == "replay"
    _plan = []
    # ---- overrides (schema.Override): a bridge stands in at a shared site --
    # Collected before anything is written: which detours to skip, which
    # recipe writes to skip, and the continuation symbols the bridge's stub
    # and any overridden cave link against -- the TARGET the skipped write
    # carried (a `jmp abs.l`'s address, or a 4-byte pointer entry).
    _ovr_detours: set[tuple[int, str]] = set()          # (site, module key)
    _ovr_writes: dict[str, set[str]] = {}               # module key -> write names
    _defsym_ovr: dict[str, int] = {}                    # symbol -> target
    for _k in REMIX.modules:
        for _o in getattr(remix_modules()[_k], "overrides", ()):
            if _o.module not in REMIX.modules:
                sys.exit(f"{_k} overrides {_o.module} at 0x{_o.site:08x}, which this "
                         f"remix does not carry -- nothing to bridge; drop {_k}")
            if _o.write is None:
                _ovr_detours.add((_o.site, _o.module))
                continue
            _ovr_writes.setdefault(_o.module, set()).add(_o.write)
            if _o.defsym:
                _rt = getattr(remix_modules()[_o.module], "runtime", None)
                if _rt is None:
                    sys.exit(f"{_k}: override names write {_o.write!r} of {_o.module}, "
                             f"which has no runtime recipe")
                _spec = json.loads(pathlib.Path(_rt.recipe).read_text())
                _data = None
                for _p in _spec["patches"]:
                    if _p["name"] == _o.write:
                        _wl = [w for w in _p["writes"]
                               if _spec["format"]["os_load_address"] + w["offset"] == _o.site]
                        if _wl:
                            _data = bytes.fromhex(_wl[0]["data"])
                if _data is None:
                    sys.exit(f"{_k}: {_o.module} has no write {_o.write!r} at 0x{_o.site:08x}")
                if _data[:2] == b"\x4e\xf9" and len(_data) >= 6:
                    _defsym_ovr[_o.defsym] = int.from_bytes(_data[2:6], "big")   # jmp abs.l
                elif len(_data) == 4:
                    _defsym_ovr[_o.defsym] = int.from_bytes(_data, "big")       # a pointer
                else:
                    sys.exit(f"{_k}: cannot read a target out of {_o.module}'s write "
                             f"{_o.write!r} ({_data.hex()}) -- not a jmp abs.l or a pointer")
                print(f"  {_k}: {_o.defsym} = 0x{_defsym_ovr[_o.defsym]:08x} "
                      f"({_o.module}'s {_o.write} at 0x{_o.site:08x}, bridged)")

    for _c in _caves:
        _b = _c.pinned
        if _replay and _c.hook_addr is not None:
            # Replaying displaced bytes at the cave's address only works for
            # position-independent stock. cfprobe displaces a pc-relative
            # jsr, which replayed from the cave would land in hyperspace
            # inside the audio interrupt -- refuse rather than build that.
            if _c.hook_stock[:2] in (b"\x4e\xba", b"\x4e\xbb") \
                    or _c.hook_stock[:1] == b"\x61":
                sys.exit(f"{_c.label}: TEMPOCAVE=replay cannot replay "
                         f"pc-relative stock ({_c.hook_stock.hex()})")
            _b = _c.hook_stock + bytes.fromhex("4e75")
            print(f"  {_c.label}: REPLAY-ONLY diagnostic (TEMPOCAVE=replay)")
        _plan.append((_c, _b))
    if os.environ.get("NOTEMPO") == "1":
        print("  tempo cave OFF (NOTEMPO=1) -- SYNC reads zeros")
        _plan = []
    _cave_top = cave_end            # caves start past the descriptor clones
    _ovf_top = OVERFLOW_RUN
    # ROM-placed linked units go FIRST, so a cave may name a unit's global
    # (ccpage2's CC_MODEDEF*, resolved to mode-defaults' cc_fx2 / cc_fx1 when
    # the module is in the image, its stub `rts` otherwise). Floating caves
    # take the run after them. 15 Sep 2026; until then units floated after
    # the caves, which is why no cave could reach one.
    _all_units = [(remix_modules()[_k], _u) for _k in REMIX.modules
                  for _u in getattr(remix_modules()[_k], "linked", ())]
    _units = [(m, u) for m, u in _all_units if not u.dram]      # ROM-placed
    _dram = [(m, u) for m, u in _all_units if u.dram]           # platform runtime (1e)
    if _all_units and not _toolchain:
        sys.exit("linked units need m68k-elf-as/ld/objcopy/nm -- run `make setup` "
                 "(Homebrew: brew install m68k-elf-gcc)")
    for _m, _u in _units:
        _work = pathlib.Path("out/linked") / _m.name / _u.label
        _work.mkdir(parents=True, exist_ok=True)
        _src = pathlib.Path(_u.source)
        _defs = tuple(_exports.items())
        _inc = None
        if _u.include is not None:
            _inc = _work
            (_work / "remix.inc").write_text(
                _u.include({_k: remix_modules()[_k] for _k in REMIX.modules}))
        if _u.reference is not None:
            _ra, _rsha = _u.reference
            (_work / "ref").mkdir(exist_ok=True)
            _rb, _, _ = _link(_src, _ra, _u.cpu, _work / "ref", defsyms=_defs, incdir=_inc)
            _got = hashlib.sha256(_rb).hexdigest()
            if _got != _rsha:
                sys.exit(f"{_m.key} {_u.label}: linked at the author's address "
                         f"0x{_ra:08x} it is {len(_rb)} B sha256 {_got}, not the "
                         f"author's {_rsha} -- source or toolchain drift; refusing")
        _at = _u.cave_addr if _u.cave_addr is not None else (_cave_top + 0x7f) & ~0x7f
        _b, _syms, _glob = _link(_src, _at, _u.cpu, _work, defsyms=_defs, incdir=_inc)
        _exports.update(_glob)
        if _at >= SAFE_CAVE_CEIL:
            sys.exit(f"{_u.label}: linked at 0x{_at:08x}, above the safe ceiling")
        if any(img[_at - BASE:_at - BASE + len(_b)]):
            sys.exit(f"{_m.key} {_u.label} at 0x{_at:08x} not free")
        _in = CLONE_BASE <= _at < cave_limit
        if _in and _at + len(_b) > cave_limit:
            sys.exit(f"{_u.label}: past the stock zero run")
        img[_at - BASE:_at - BASE + len(_b)] = _b
        _sym[_u.label] = _syms
        print(f"  {_m.key}: {_u.label} {len(_b)} B linked at 0x{_at:08x}"
              f"{' (pinned)' if _u.cave_addr is not None else ''}"
              f"{' -- matches the author\'s build at 0x%08x' % _u.reference[0] if _u.reference else ''}")
        if _in:
            _cave_top = max(_cave_top, _at + len(_b))
        elif OVERFLOW_RUN <= _at < OVERFLOW_RUN_END:
            _ovf_top = max(_ovf_top, (_at + len(_b) + 3) & ~3)

    for _c, _b in _plan:
        _floating = _c.cave_addr is None
        if _floating:
            _c = dataclasses.replace(_c, cave_addr=(_cave_top + 0x7f) & ~0x7f)
        # ⚠️ A CAVE MAY LIVE OUTSIDE THE CLONE WINDOW. The region from
        # CLONE_BASE to the chooser list is crowded -- six descriptor clones
        # and fifteen label formatters left 84 bytes on the rig -- and
        # docs/firmware/MAINMENU.md names two other unclaimed runs. A cave pinned into
        # one of those is checked for being FREE (below) and for not
        # overlapping another module's cave (the ledger), but it neither
        # follows nor advances this region's cursor.
        if _c.cave_addr >= SAFE_CAVE_CEIL:
            sys.exit(
                f"{_c.label}: cave pinned at 0x{_c.cave_addr:08x}, at or above "
                f"the safe ceiling 0x{SAFE_CAVE_CEIL:08x}. That is OS image "
                f"data (bss), not free space -- it reads zero at rest and the "
                f"PROJECT subsystem clobbers it at runtime (tag 91 crashed on "
                f"[PROJ]). Place the cave in the decoded 0x400d2000..0x400d8000 "
                f"free region.")
        _inside = CLONE_BASE <= _c.cave_addr < cave_limit
        if _inside:
            assert _c.cave_addr >= _cave_top, \
                f"{_c.label} overlaps what precedes it"
            assert _c.cave_addr + len(_b) <= cave_limit, \
                "past the stock zero run (or into the long chooser list)"
        if _c.hook_addr is not None:
            got = bytes(img[_c.hook_addr - BASE:
                            _c.hook_addr - BASE + len(_c.hook_stock)])
            if got != _c.hook_stock:
                sys.exit(f"{_c.label} hook site 0x{_c.hook_addr:08x} is not "
                         f"stock ({got.hex()}) -- refusing")
        _pokes = ()
        if _c.emit is not None:
            # A cave that points at itself: its bytes are a function of the
            # address the line above just resolved (schema.CavePatch.emit).
            _b, _pokes = _c.emit(_c.cave_addr)
        if any(img[_c.cave_addr - BASE:_c.cave_addr - BASE + len(_b)]):
            sys.exit(f"{_c.label} not free")
        if OVERFLOW_RUN <= _c.cave_addr < OVERFLOW_RUN_END:
            _ovf_top = max(_ovf_top, (_c.cave_addr + len(_b) + 3) & ~3)
        # SOURCE IS THE TRUTH when a toolchain is present (schema.CavePatch):
        # the cave is assembled and LINKED at the address just resolved and
        # those bytes are written; the reference -- `pinned`, or the bytes an
        # emit() returned -- must match or the build refuses. An emit() that
        # returns b"" hands the bytes to the source entirely (its pokes still
        # apply). An emit() that returns bytes is the legacy hand-assembled
        # path and is left exactly alone. Without a toolchain the reference
        # is written, as it always was.
        _legacy_emit = _c.emit is not None and len(_b) > 0
        if _c.source and not _replay and _toolchain and not _legacy_emit:
            # A bridge may redefine one of this cave's defsyms (CC_NEXT):
            # the linked bytes then differ from the ratified form by exactly
            # that address, so the oracle is set aside for it and said so.
            _bridged = [n for n, _v in _c.defsyms if n in _defsym_ovr or n in _exports]
            _cdefs = tuple((n, _defsym_ovr.get(n, _exports.get(n, v))) for n, v in _c.defsyms)
            _lb, _lsyms, _lglob = _link(
                _c.source, _c.cave_addr, _c.cpu,
                pathlib.Path("out/linked/caves") / re.sub(r"\W+", "_", _c.label),
                sections=(".text",), defsyms=_cdefs + tuple(_exports.items()))
            _exports.update(_lglob)
            _ref = (_c.reference(_c.cave_addr) if _c.reference is not None
                    else _c.pinned if _c.emit is None else _b)
            if _bridged:
                print(f"  {_c.label}: {', '.join(f'{n} -> 0x{_defsym_ovr.get(n, _exports.get(n, 0)):08x}' for n in _bridged)}"
                      f" (bridged; the ratified-bytes oracle is set aside for this cave)")
                _ref = b""
            if _ref and _lb != _ref:
                sys.exit(f"{_c.source} linked at 0x{_c.cave_addr:08x} no longer "
                         f"matches the bytes the manifest ratifies ({len(_lb)} vs "
                         f"{len(_ref)} B) -- re-pin them in the manifest deliberately")
            if not _ref and not _lb:
                sys.exit(f"{_c.label}: source produced no bytes")
            if _floating and _inside and _c.cave_addr + len(_lb) > cave_limit:
                # A floating source cave that no longer fits the clone window
                # (the ROM units come first since 15 Sep 2026) goes to the
                # second zero run, as the label formatters do; re-linked
                # there, since its absolute references follow the address.
                _at2 = (_ovf_top + 3) & ~3
                if _at2 + len(_lb) > OVERFLOW_RUN_END:
                    sys.exit(f"{_c.label}: {len(_lb)} B fits neither the clone "
                             f"window (from 0x{_c.cave_addr:08x}) nor the overflow run")
                _c = dataclasses.replace(_c, cave_addr=_at2)
                _inside = False
                _lb, _lsyms, _lglob = _link(
                    _c.source, _c.cave_addr, _c.cpu,
                    pathlib.Path("out/linked/caves") / re.sub(r"\W+", "_", _c.label),
                    sections=(".text",), defsyms=_cdefs + tuple(_exports.items()))
                _exports.update(_lglob)
                if _ref and _c.reference is not None:
                    _ref = _c.reference(_c.cave_addr)
                    if _lb != _ref:
                        sys.exit(f"{_c.source} linked at 0x{_c.cave_addr:08x} no longer "
                                 f"matches the bytes the manifest ratifies")
                _ovf_top = (_c.cave_addr + len(_lb) + 3) & ~3
                if _c.emit is not None:
                    _, _pokes = _c.emit(_c.cave_addr)     # the dispatch repoint follows the cave
                print(f"  {_c.label}: past the clone window, placed in the overflow run")
            if any(img[_c.cave_addr - BASE:_c.cave_addr - BASE + len(_lb)]):
                sys.exit(f"{_c.label} not free")
            _b = _lb
            _sym[_c.label] = _lsyms
        elif _c.source and not _replay and not _legacy_emit and not _b:
            sys.exit(f"{_c.label}: its source is the only truth and there is no "
                     f"m68k-elf toolchain -- run `make setup`")
        img[_c.cave_addr - BASE:_c.cave_addr - BASE + len(_b)] = _b
        for _pa, _expect, _write in _pokes:
            _got = bytes(img[_pa - BASE:_pa - BASE + len(_expect)])
            if _got != _expect:
                sys.exit(f"{_c.label}: 0x{_pa:08x} holds {_got.hex()}, not "
                         f"stock {_expect.hex()} -- refusing to write over a "
                         f"table that is not where we think it is")
            img[_pa - BASE:_pa - BASE + len(_write)] = _write
            print(f"    poke 0x{_pa:08x}: {_expect.hex()} -> {_write.hex()}")
        if _c.hook_addr is not None:
            # The jsr is six bytes; the rest of the displaced span is nops.
            # hook_stock is whole instructions, so its length is the span:
            # ten for both tempo-sync caves, eight for cfprobe (a jsr plus
            # a move-to-SR). Anything shorter than the jsr, or odd, is a
            # manifest error.
            _n = len(_c.hook_stock)
            assert _n >= 6 and _n % 2 == 0, \
                f"{_c.label}: hook_stock must be >= 6 even bytes, got {_n}"
            img[_c.hook_addr - BASE:_c.hook_addr - BASE + _n] = \
                b"\x4e\xb9" + _c.cave_addr.to_bytes(4, "big") \
                + b"\x4e\x71" * ((_n - 6) // 2)
        _reg = _c.registers_formatter
        if _reg is not None and _reg.module in clone_addr:
            wr32(clone_addr[_reg.module] + 0x0ca + _reg.slot * 4,
                 _c.cave_addr + _reg.offset)
            wr32(clone_addr[_reg.module] + 0x0fa + _reg.slot * 4, 0)
        _hook = (f", hook at 0x{_c.hook_addr:08x}"
                 if _c.hook_addr is not None else "")
        print(f"  {_c.label}: {len(_b)} bytes at 0x{_c.cave_addr:08x}"
              f"{_hook}{_c.report_note}")
        if _inside:
            _cave_top = _c.cave_addr + len(_b)

    # ==== 1c. loader-appended DRAM runtimes (schema.Runtime) =================
    # The third placement class: the OS image GROWS by an append (early
    # loader + stage + packed runtime) and the runtime executes from DRAM.
    # Its recipe's sparse writes into the image are pokes with the same
    # assert-before-write discipline as a cave's; the append is stitched on
    # at the very end, after every other pass has seen the stock-length
    # image. tools/remix/runtime_build.py re-derives every identity the
    # recipe pins, so nothing lands here that does not match the author's
    # own build byte for byte. Nothing runs for a remix without a runtime.
    _appends = []
    _payloads = []                  # runtimes carried by octabam's loader (1e)
    for _k in REMIX.modules:
        _m = remix_modules()[_k]
        _rt = getattr(_m, "runtime", None)
        if _rt is None:
            continue
        from remix import runtime_build
        _work = pathlib.Path("out/runtime") / _m.name
        # A runtime whose recipe writes the arena geometry (Octakit's four)
        # declares them in its ArenaReserve; the build computes those
        # literals from EVERY reservation in the remix (1e) instead.
        _skip = tuple(getattr(getattr(_m, "arena", None), "recipe_writes", ())) + \
            tuple(_ovr_writes.get(_m.key, ()))                 # bridged (schema.Override)
        _writes, _append, _info = runtime_build.build(_rt, IMG.read_bytes(), _work,
                                                      skip=_skip)
        _sym[_m.key] = _info["symbols"]
        _exports.update({k: v for k, v in _info["symbols"].items()
                         if not k.startswith("_") or k.startswith("__gk_")})
        for _va, _expect, _write, _name in _writes:
            _got = bytes(img[_va - BASE:_va - BASE + len(_expect)])
            if _got != _expect:
                sys.exit(f"{_m.key}: runtime write {_name} at 0x{_va:08x} finds "
                         f"{_got.hex()}, not stock {_expect.hex()} -- another module "
                         f"got there first; refusing")
            img[_va - BASE:_va - BASE + len(_write)] = _write
        # Her append (loader + stage + packed runtime) is NOT stitched on:
        # her runtime becomes a PAYLOAD of octabam's loader (section 1e),
        # staged at her own stage address so her relocation still finds it.
        _payloads.append(_info["payload"])
        print(f"  {_m.key}: {len(_writes)} writes into the image, runtime "
              f"{_info['runtime_size']:,} B -> packed {_info['packed_size']:,} B "
              f"(m68k-elf-gcc {_info['gcc']}, recipe pins {_info['gcc_pinned']}; "
              f"rebuilt runtime, packed runtime and append all match the "
              f"recipe) -- carried as a payload of octabam's loader{_rt.report_note}")

    # ==== 1d. linker-backed units (schema.Linked/Detour/TableGrow/Poke) =====
    # Placement by the BUILD: each unit is assembled and linked at the
    # address it is given here -- floating ones after whatever precedes them
    # in the clone window, exactly like a floating cave -- and everything
    # that points into it (detours, grown tables) resolves through the
    # linker's symbol table, never through an address the author wrote
    # down. A unit that declares a `reference` (address, sha256) is ALSO
    # linked at that address, in a scratch file, and compared: that is the
    # author's own build output, so a source or toolchain drift from the
    # bytes they ratified fails here even though the image carries the unit
    # elsewhere. Nothing runs for a remix without linked units.
    if _payloads and not _toolchain:
        sys.exit("linked units need m68k-elf-as/ld/objcopy/nm -- run `make setup` "
                 "(Homebrew: brew install m68k-elf-gcc)")

    # ==== 1e. the platform runtime: DRAM units + other payloads, one loader ==
    # Every `dram=True` unit in the remix is linked as ONE image at the
    # base of the platform's arena reserve, packed and carried behind
    # octabam's loader together with any runtime built in 1c (Octakit) --
    # equal payloads, one boot detour. The loader itself is the append;
    # nothing here touches the OS zero runs.
    # ---- the audio page arena: every reservation, one geometry -----------
    # Modules that live in the arena declare their pages (Octakit: the top
    # 528); the platform reserves its own at the bottom whenever the remix
    # carries DRAM units. tools/remix/arena.py stacks them and yields the
    # writes: the base literal at its 24 sites and the four geometry words.
    from remix import arena
    _reservations = [(_m.name, _m.arena.where, _m.arena.pages)
                     for _k in REMIX.modules for _m in (remix_modules()[_k],)
                     if getattr(_m, "arena", None) is not None]
    if _dram:
        _reservations.append(("octabam platform", "bottom", arena.PLATFORM_PAGES))
    _reserve = None
    if _reservations:
        _placed, _abase, _acount = arena.layout(_reservations)
        for _pa, _pexp, _pw, _pnote in arena.pokes(_reservations):
            _got = bytes(img[_pa - BASE:_pa - BASE + len(_pexp)])
            if _got != _pexp:
                sys.exit(f"arena: 0x{_pa:08x} ({_pnote}) holds {_got.hex()}, not stock "
                         f"{_pexp.hex()} -- another module got there first; refusing")
            img[_pa - BASE:_pa - BASE + len(_pw)] = _pw
        for _p in _placed:
            print(f"  arena: {_p.owner} takes {_p.pages} pages at the {_p.where}, "
                  f"0x{_p.start:08x}..0x{_p.end:08x} ({_p.pages * arena.PAGE:,} B)")
            if _p.owner == "octabam platform":
                _reserve = (_p.start, _p.end - _p.start)
        print(f"  arena: base 0x{_abase:08x}, {_acount:,} pages "
              f"({_acount * arena.PAGE // 1048576} MB) left for samples and recorders "
              f"(stock {arena.PAGES:,}); {len(arena.pokes(_reservations))} words rewritten")

    if _dram or _payloads:
        from remix import platform_build
        _pappend, _psyms, _boot, _pnames = platform_build.build(
            [(_m.key, _u) for _m, _u in _dram], _payloads, pathlib.Path("out/platform"),
            reserve=_reserve, defsyms=_defsym_ovr)
        for _m, _u in _dram:
            _sym[_u.label] = _psyms          # detours name units; one table serves all
        _exports.update(_psyms)
        for _p in _payloads:
            _exports.update({k: v for k, v in _p.get("symbols", {}).items() if k.startswith("gk_")})
        _appends.append(("octabam loader + payloads (" + ", ".join(_pnames) + ")", _pappend))
        if "OCTAKIT" not in REMIX.modules:
            # Octakit's own recipe already routes the boot site through her
            # wrapper, which calls the loader at its fixed address; without
            # her, the redirect is ours to make.
            _ba, _bexp, _bw, _bnote = _boot
            _got = bytes(img[_ba - BASE:_ba - BASE + len(_bexp)])
            if _got != _bexp:
                sys.exit(f"boot site 0x{_ba:08x} holds {_got.hex()}, not stock "
                         f"{_bexp.hex()} -- refusing to redirect boot")
            img[_ba - BASE:_ba - BASE + len(_bw)] = _bw
            print(f"    poke 0x{_ba:08x}: {_bexp.hex()} -> {_bw.hex()}  {_bnote}")
        _dsize = sum(1 for _ in _dram)
        print(f"  platform runtime: {_dsize} DRAM unit(s) linked at "
              f"0x{_reserve[0]:08x}, payloads {', '.join(_pnames)}, "
              f"append {len(_pappend):,} B at 0x{platform_build.LOADER_AT:08x}"
              if _reserve else
              f"  platform loader: payloads {', '.join(_pnames)}, "
              f"append {len(_pappend):,} B at 0x{platform_build.LOADER_AT:08x}")

    for _m, _t in [(remix_modules()[_k], _t) for _k in REMIX.modules
                   for _t in getattr(remix_modules()[_k], "tables", ())]:
        _ents = [rd32(_t.old + i * 4) for i in range(_t.count)]
        _ents += [_sym[u][s] for u, s in _t.symbols]
        _blob = b"".join(v.to_bytes(4, "big") for v in _ents)
        _at = (_cave_top + 0x7f) & ~0x7f
        if any(img[_at - BASE:_at - BASE + len(_blob)]):
            sys.exit(f"{_m.key} table {_t.label} at 0x{_at:08x} not free")
        img[_at - BASE:_at - BASE + len(_blob)] = _blob
        _cave_top = _at + len(_blob)
        for _ra, _old in _t.refs:
            if rd32(_ra) != _old:
                sys.exit(f"{_m.key} table {_t.label}: ref 0x{_ra:08x} holds "
                         f"0x{rd32(_ra):08x}, not 0x{_old:08x}; refusing")
            wr32(_ra, _at)
        print(f"  {_m.key}: table {_t.label} {_t.count}+{len(_t.symbols)} entries at "
              f"0x{_at:08x}, {len(_t.refs)} refs repointed")

    for _m, _d in [(remix_modules()[_k], _d) for _k in REMIX.modules
                   for _d in getattr(remix_modules()[_k], "detours", ())]:
        if (_d.site, _m.key) in _ovr_detours:
            print(f"  {_m.key}: detour at 0x{_d.site:08x} bridged -- another module's stub "
                  f"stands in for it")
            continue
        _got = bytes(img[_d.site - BASE:_d.site - BASE + len(_d.expect)])
        if _got != _d.expect:
            sys.exit(f"{_m.key} detour {_d.note or _d.symbol} at 0x{_d.site:08x} finds "
                     f"{_got.hex()}, not {_d.expect.hex()}; refusing")
        _target = _d.target if _d.target is not None else _sym[_d.unit][_d.symbol]
        _op = {"jmp": b"\x4e\xf9", "jsr": b"\x4e\xb9", "lea": _d.expect[:2]}[_d.kind]
        _w = _op + _target.to_bytes(4, "big")
        _n = _d.pad_to or 6
        assert _n >= 6 and _n % 2 == 0, \
            f"{_m.key} detour at 0x{_d.site:08x}: pad_to {_n} must be an even count >= 6"
        img[_d.site - BASE:_d.site - BASE + _n] = _w + b"\x4e\x71" * ((_n - 6) // 2)
        _what = f"{_d.unit}:{_d.symbol}" if _d.target is None else "stock"
        print(f"  {_m.key}: {_d.kind} 0x{_d.site:08x} -> {_what} 0x{_target:08x}  {_d.note}")

    for _m, _r in [(remix_modules()[_k], _r) for _k in REMIX.modules
                   for _r in getattr(remix_modules()[_k], "symbol_refs", ())]:
        _got = rd32(_r.addr)
        if _got != _r.expect:
            sys.exit(f"{_m.key} symbol ref {_r.note or _r.symbol} at "
                     f"0x{_r.addr:08x} finds 0x{_got:08x}, not "
                     f"0x{_r.expect:08x}; refusing")
        _target = _sym[_r.unit][_r.symbol] + _r.addend
        wr32(_r.addr, _target)
        print(f"    ref 0x{_r.addr:08x}: 0x{_r.expect:08x} -> "
              f"{_r.unit}:{_r.symbol} 0x{_target:08x}  {_r.note}")

    for _m, _p in [(remix_modules()[_k], _p) for _k in REMIX.modules
                   for _p in getattr(remix_modules()[_k], "pokes", ())]:
        _got = bytes(img[_p.addr - BASE:_p.addr - BASE + len(_p.expect)])
        if _got != _p.expect:
            sys.exit(f"{_m.key} poke {_p.note} at 0x{_p.addr:08x} finds {_got.hex()}, "
                     f"not {_p.expect.hex()}; refusing")
        img[_p.addr - BASE:_p.addr - BASE + len(_p.write)] = _p.write
        print(f"    poke 0x{_p.addr:08x}: {_p.expect.hex()} -> {_p.write.hex()}  {_p.note}")

    # ---- PLAN §6: the mode selects print their WORDS ---------------------
    # Every stepped select drew as a bare number -- WarpFold's MODE as `1 2 3`
    # where the manifest has said FOLD RING BOTH all along -- because
    # Param.labels was authored, schema-checked against count, and then never
    # read. This is the pass that makes it load-bearing.
    #
    # Only the "A" array (P+0x0ca) moves. B stays 0x40047254, the CHORUS.TAPS
    # tick widget the clone loop already chose: the ticks are the right
    # picture for an enumerated control, and B=0 would drop back to a plain
    # dial. So this replaces WHAT IS PRINTED, not how it is drawn.
    #
    # The bytes come from tools/build/label_fmt.py rather than a pinned CavePatch:
    # twelve caves whose contents vary with the labels cannot be hand-pinned,
    # and emit() is re-derived through m68k-elf-as whenever one is on PATH.
    _lbl_top = max(_cave_top, cave_end)
    _lbl = []
    for name in CLONED_ORDER:
        # A BLANKED module's page draws no knobs, so nothing ever calls its
        # label formatters: skip them. On the rig that is the
        # two hosts' six select labels, ~500 B the bus screen needs. The
        # screen prints its own words (busscreen VERB_SELECTS / DLY_SELECTS).
        if name in BLANKED:
            continue
        for _i, _p in enumerate(_MODS[name].params):
            if not (_p.active and _p.labels):
                continue
            # A MODE select with views gets the BIGGER cave: it renames the
            # knobs around it before printing its own word, so the panel
            # stops calling BusDelay's grain scatter "MDEP" (tools/
            # mode_names.py). Everything else keeps the plain label cave.
            _mod = _MODS[name]
            _ren = (mode_names.complete(_mod)
                    if _i == _mod.mode_slot and _mod.mode_views else {})
            # Only the MODE select names itself (15 Sep 2026, image 26): a
            # select whose word is not self-explaining (SIZE, FRZE, SHFT,
            # RATE) keeps its name, the tick widget flashing the word.
            if _i == _mod.mode_slot:
                _ren = mode_names.with_selfname(_ren, _i, _p.labels)
            if _ren:
                _desc = clone_addr[name] + mode_names.NAMES_AT
                _bytes = mode_names.emit(_p.labels, _desc, _ren)
                mode_names.verify(_p.labels, _desc, _ren)
            else:
                _bytes = label_fmt.emit(_p.labels)
                label_fmt.verify(_p.labels)
            # Past the clone window? Into the second zero run, above the
            # caves pinned there. Either region is checked free; a formatter
            # is position independent (pc-relative tables, absolute OS
            # targets), so it neither knows nor cares which run it is in.
            _at = _lbl_top
            _ovf = _lbl_top + len(_bytes) > cave_limit
            if _ovf:
                _at = _ovf_top
                if _at + len(_bytes) > OVERFLOW_RUN_END:
                    sys.exit(f"label formatters do not fit: {name} slot {_i} "
                             f"needs {len(_bytes)} B; the clone window ends at "
                             f"0x{cave_limit:08x} and the overflow run at "
                             f"0x{OVERFLOW_RUN_END:08x} (next free "
                             f"0x{_at:08x})")
            if any(img[_at - BASE:_at - BASE + len(_bytes)]):
                sys.exit(f"label cave at 0x{_at:08x} is not free")
            img[_at - BASE:_at - BASE + len(_bytes)] = _bytes
            wr32(clone_addr[name] + 0x0ca + _i * 4, _at)
            _lbl.append((name, _i, _p.name.decode("latin1"), _at,
                         len(_bytes), _p.labels, bool(_ren)))
            if _ovf:
                _ovf_top = (_at + len(_bytes) + 3) & ~3
            else:
                _lbl_top += len(_bytes)
    for _n, _i, _nm, _a, _sz, _labels, _rn in _lbl:
        print(f"  {_n:13s} slot {_i:<2} {_nm:<5} prints "
              f"{'|'.join(_labels)}  ({_sz} B at 0x{_a:08x})"
              + (" + RENAMES its neighbours per mode" if _rn else ""))
    if _lbl:
        print(f"  {len(_lbl)} label formatters, "
              f"0x{max(_cave_top, cave_end):08x}..0x{_lbl_top:08x} "
              f"({_lbl_top - max(_cave_top, cave_end)} B)"
              + (f"; {sum(1 for x in _lbl if x[3] >= OVERFLOW_RUN and x[3] < OVERFLOW_RUN_END)} "
                 f"overflowed into 0x{OVERFLOW_RUN:08x}.. (next free 0x{_ovf_top:08x})"
                 if _ovf_top > OVERFLOW_RUN else ""))
    # ==== 1d. FX1 ROWS, for modules that asked for one =====================
    # THE OTHER HALF OF "BOTH SLOTS". The DSP dispatch is ONE table indexed by
    # the raw id and shared by the menus, so a module's CODE already runs from
    # FX1 the moment FX1 selects its id -- and a REPLACEMENT already gets the
    # row, because it inherits the stock effect's (above, in place). What was
    # missing is a row for a module on a NEW id, and it was missing for one
    # mechanical reason: FX1's list ends at 0x400d608c and FX2's begins at
    # 0x400d6090, so it cannot grow where it is.
    #
    # So it moves, exactly as the FX2 list does when it outgrows NEW_LIST:
    # rebuilt in the cave, three `lea` references repointed. That relocation
    # is not new -- tools/build/build_fx1.py proved it standalone against the stock
    # image (data only, 74 bytes changed) and it still applies today.
    #
    # It costs NO WORDS. The code is in the image either way; this is four
    # bytes of cave per row plus the relocated list. What it does cost is
    # CYCLES: an FX1 effect runs on a track that is already running an FX2
    # one, so the worst per-core load can gain four more copies of it
    # (tools/build/cycle_count.py, which prices FX1 slots for exactly this reason).
    _fx1 = list(REMIX.fx1)
    if _fx1:
        # WHAT EACH ROW MAY BE. A module of ours needs an FX2 row, because
        # that is where its descriptor CLONE comes from, and must survive on
        # FX1 at all (state.fx1_hazard: not an allocator reader, not fixed
        # FX2 buffers, not a bus server). A stock effect must be one FX1
        # already lists -- DELAY and the three reverbs are FX2-only on a
        # stock unit for exactly the reason our allocator readers are, they
        # do not fit a 3,072-word FX1 allocation.
        _fx1_desc = []
        for _n in _fx1:
            _m = _MODS.get(_n)
            if _m is None:
                sys.exit(f"fx1={_n!r}: no such effect")
            if _m.is_stock:
                _rep = [k for k in CARRIED if _MODS[k].menu is not None
                        and _MODS[k].menu.replaces == _n]
                if _rep:
                    sys.exit(f"fx1={_n!r}: {_rep[0]} replaces it in this "
                             f"remix, so its row would draw the stock name "
                             f"over our code -- list {_rep[0]!r} instead")
                if _m.menu.fx2_id not in stock_mod.fx1_ids():
                    sys.exit(f"fx1={_n!r}: stock does not list it on FX1, "
                             f"and it is FX2-only because it does not fit a "
                             f"3,072-word FX1 allocation")
                _fx1_desc.append(_m.menu.donor_desc + 0x38)
                continue
            if _n not in CARRIED:
                sys.exit(f"fx1={_n!r}: this remix does not carry it, so "
                         f"there is no descriptor clone for FX1 to point at")
            _hz = fx1_hazard(_m)
            if _hz:
                sys.exit(f"fx1={_n!r}: {_hz}")
            _fx1_desc.append(clone_addr[_n])

        # THE FIRMWARE'S OWN NONE IS ALWAYS ROW 0. It is how the slot is
        # turned off, stock has it there, and a remix naming effects must not
        # be able to lose it by omission.
        _new = [FX1_NONE] + _fx1_desc + [0]
        _need = len(_new) * 4
        # A table of absolute pointers: position independent, so it takes
        # the overflow run when the clone window is full, like a formatter.
        _fx1_addr, _fx1_ovf = _lbl_top, False
        if _lbl_top + _need > cave_limit:
            _fx1_addr, _fx1_ovf = _ovf_top, True
            if _fx1_addr + _need > OVERFLOW_RUN_END:
                sys.exit(f"FX1 chooser list of {len(_new) - 1} rows needs "
                         f"{_need} B; the clone window ends at "
                         f"0x{cave_limit:08x} and the overflow run at "
                         f"0x{OVERFLOW_RUN_END:08x}")
        if any(img[_fx1_addr - BASE:_fx1_addr - BASE + _need]):
            sys.exit(f"FX1 chooser list cave at 0x{_fx1_addr:08x} is not free")
        for _i, _v in enumerate(_new):
            wr32(_fx1_addr + _i * 4, _v)
        if _fx1_ovf:
            _ovf_top = (_fx1_addr + _need + 3) & ~3
        else:
            _lbl_top += _need
        # REPOINT, having proved each site is what we think it is. A `lea.l
        # <abs>.l,aN` is 0x4?f9 followed by the address, so the two bytes
        # before the operand pin the instruction as well as the value.
        for _r in FX1_LIST_REFS:
            if rd32(_r) != FX1_LIST:
                sys.exit(f"FX1 list ref at 0x{_r:08x} is 0x{rd32(_r):08x}, "
                         f"not stock FX1_LIST -- refusing")
            if bytes(img[_r - BASE - 2:_r - BASE]) not in (
                    b"\x41\xf9", b"\x47\xf9", b"\x4b\xf9"):
                sys.exit(f"FX1 list ref at 0x{_r:08x} is not preceded by a "
                         f"lea.l opcode -- refusing")
            wr32(_r, _fx1_addr)
        # AND SIZE THE VIEWPORT, which is what makes a list SHORTER than
        # stock's safe: the draw loop iterates this literal independently of
        # the real length, so a short list has it reading past the terminator
        # and rendering raw memory as text (the "bunch of symbols" of
        # hardware test 1, on FX2). Same instruction, same offset from the
        # list reference, same bytes -- FX1's setup function differs from
        # FX2's only in the list address.
        if rd32(FX1_ROWCOUNT_INSN) != 0x48780007:
            sys.exit(f"FX1 row-count site 0x{FX1_ROWCOUNT_INSN:08x} is not "
                     f"`pea (0x7).w` -- refusing")
        _fx1_rows = min(CHOOSER_ROWS, len(_new) - 1)
        img[FX1_ROWCOUNT_AT - BASE:FX1_ROWCOUNT_AT - BASE + 2] = \
            _fx1_rows.to_bytes(2, "big")
        # FX1 RESOLVES ITS OWN DESCRIPTOR AND ITS OWN CURSOR ROW. Writing
        # only the list would draw the row and then open the stock NONE page
        # under it -- "a slot can draw a knob and publish nothing", one table
        # further along.
        #
        # ⚠️ AND EVERY OTHER ID IS CLAMPED TO ROW 0, which the FX2 path does
        # NOT do. FX2 has only ever been able to grow its list from three
        # rows, so a stale position could not point past the end; FX1 can now
        # be made SHORTER than stock's eleven, and an old project holding an
        # id this list dropped would seed the cursor past the last row.
        for _i in range(0x20):
            wr32(FX1_ID2POS + _i * 4, 0)
        for _pos, _n in enumerate(_fx1):
            _m = _MODS[_n]
            _eid = _m.menu.fx2_id
            if not _m.is_stock:
                _slot = FX1_IDS + _eid * 4
                # A replacement's slot already holds its clone: the
                # repoint above wrote it there in place of stock's.
                if rd32(_slot) not in (FX1_NONE, clone_addr[_n]):
                    sys.exit(f"{_n}: FX1_IDS[0x{_eid:02x}] is "
                             f"0x{rd32(_slot):08x}, not NONE -- this id is "
                             f"already on FX1 and the row would be a "
                             f"duplicate")
                wr32(_slot, clone_addr[_n])
            wr32(FX1_ID2POS + _eid * 4, _pos + 1)      # past NONE at row 0
        # Octakit's machine-selection runtime hardcodes the stock FX1 table
        # too (0x400d6060, cursor 0..10), so the relocated list is mirrored
        # back the same way as the FX2 one above. Unmirrored, a cursor
        # position resolves to whatever stock row sat there: Octakit's
        # validation passes on that descriptor and it identifies the wrong
        # machine, silently.
        if "OCTAKIT" in REMIX.modules:
            if len(_new) - 1 > 11:
                sys.exit(
                    "OCTAKIT supports at most 11 FX1 chooser rows (NONE "
                    "included): its machine-selection runtime accepts "
                    "cursor 0..10"
                )
            for _i in range(12):
                wr32(FX1_LIST + _i * 4, _new[_i] if _i < len(_new) else 0)
        _ours = [n for n in _fx1 if not _MODS[n].is_stock]
        print(f"  FX1 chooser = {len(_new) - 1} rows at 0x{_fx1_addr:08x} "
              f"(NONE + {', '.join(_fx1)}), {len(FX1_LIST_REFS)} refs "
              f"repointed, viewport {_fx1_rows}, id and cursor tables "
              f"written -- {len(_ours)} of ours, no words: their code is "
              f"already placed")

    print(f"  cave: 0x{_lbl_top:08x}..0x{cave_limit:08x}, "
          f"{cave_limit - _lbl_top} B of cave left")

    # A fresh part's FX2 id is 0. Rather than hunt down the part-init template,
    # alias id 0 to SEND: its descriptor, its cursor position, and (below) its
    # DSP dispatch. Every unassigned track is then a SEND automatically.
    fb_desc = FX1_NONE if NO_FB else clone_addr[REMIX.fallback]
    wr32(FX2_IDS + NONE_ID * 4, fb_desc)
    wr32(ID2POS + NONE_ID * 4, fb_pos)
    # A module this remix leaves out still owns an id, and a saved project can
    # carry it. Alias it to the fallback for exactly the reason id 0 is
    # aliased: the alternative is a chooser entry dispatching into whatever
    # code now occupies that address. Empty whenever the remix carries every
    # module the registry knows.
    # A STOCK effect the remix leaves out is NOT aliased: its descriptor,
    # id entry and dispatch stay stock, so an old project that selects it
    # still runs it -- it simply has no chooser row. That is what every
    # remix did to all fourteen before, and it is what keeps
    # FX1 (which shares the dispatch tables) whole.
    _omitted = [m for m in remix_modules().values()
                if m.menu is not None and m.key not in REMIX.modules
                and not m.is_stock]
    # ⚠️ A REPLACEMENT THAT IS NOT IN THIS REMIX LEAVES STOCK ALONE. Aliasing
    # its id to the fallback would take the stock effect away from BOTH menus
    # -- which is exactly what happened for four days when Rungs sat on
    # EQUALIZER's 0x0c: the remixes without Rungs aliased 0x0c to SEND, so
    # the shipping image had no EQUALIZER on FX1 either. The id belongs to a
    # stock effect; absent our replacement, it goes back to being one.
    _restored = [m for m in _omitted if m.menu.replaces]
    _omitted = [m for m in _omitted if not m.menu.replaces]
    for _m in _omitted:
        wr32(FX2_IDS + _m.menu.fx2_id * 4, fb_desc)
        wr32(ID2POS + _m.menu.fx2_id * 4, fb_pos)
    if _restored:
        print(f"  not in this remix, LEFT STOCK: "
              f"{', '.join(sorted(m.key for m in _restored))} -- each replaces "
              f"a stock effect, so its id keeps that effect's descriptor and "
              f"dispatch on both menus")
    if _omitted:
        print(f"  not in this remix: "
              f"{', '.join(sorted(m.key for m in _omitted))} -- their ids "
              f"alias to {REMIX.fallback}")
    if delayprobe:
        wr32(ID2POS + STOCK_DELAY_ID * 4, len(real) - 1)
        if rd32(FX2_IDS + STOCK_DELAY_ID * 4) != STOCK_DELAY_P:
            sys.exit("DELAY's FX2_IDS entry is not stock -- refusing to probe")
        print(f"  *** DELAY PROBE: stock DELAY restored to the menu at "
              f"position {len(real) - 1} ***")
    _none = "with NONE at row 0" if NO_FB else "no NONE"
    print(f"  chooser list = {len(real)} entries, {_none}, viewport shrunk to "
          f"{len(real)} rows (no padding)" if len(real) <= CHOOSER_ROWS else
          f"  chooser list = {len(real)} entries at 0x{list_addr:08x} (the "
          f"long list cave), {_none}, viewport {rows} rows -- it scrolls")
    if HIDDEN:
        _b = [k for k in HIDDEN if k in BLANKED]
        _f = [k for k in HIDDEN if k not in BLANKED and k in REMIX.fx1]
        _n = [k for k in HIDDEN if k not in BLANKED and k not in REMIX.fx1]
        print(f"  placed but NOT LISTED on FX2: {', '.join(HIDDEN)} -- code, "
              f"id and clone present, no chooser row"
              + (f"; names blanked (page draws nothing): {', '.join(_b)}" if _b
                 else "")
              + (f"; names KEPT (on the FX1 chooser): {', '.join(_f)}" if _f
                 else "")
              + (f"; names KEPT (NAMED: the host page draws all twelve): "
                 f"{', '.join(_n)}" if _n else ""))
    if STOCK_ROWS:
        print(f"  stock rows kept: {', '.join(STOCK_ROWS)} -- descriptors, "
              f"code and dispatch untouched on both cores")
    # ⚠️ WORDING FROZEN for the SEND arm: the build report is API (refhash
    # hashes it verbatim). Only the NONE arm is new.
    print(f"  id 0x00 aliased to NONE: a fresh/unassigned track is off, as "
          f"on a stock unit\n" if NO_FB else
          f"  id 0x00 aliased to SEND: a fresh/unassigned track is a send\n")

    # ==== 2. DSP code placement + dispatch (task 13) ========================
    print("=== DSP: code placed, dispatch wired, both payloads ===")
    delay_src = (pathlib.Path(ASM_SRC["DELAY SERVER"]).read_text()
                 if "DELAY SERVER" in ASM_SRC else None)
    if delay_src is not None:
        # The line geometry follows the placement: `; @B` lines ship (two
        # 32K lines, LineR in core 1's private FX2 buffer region), `; @DEV`
        # lines are the hatch's (payload A beside the reverb's tank: the two
        # 16K lines in the shared half). tools/remix/geom.py.
        from remix import geom as _geom
        _nb, _nd = _geom.census(delay_src)
        delay_src = _geom.select(delay_src, DEV)
        print(f"  DELAY SERVER: line geometry {'DEV (16K lines, payload A)' if DEV else 'shipping (32K lines, LineR private)'}"
              f" -- {_nd if DEV else _nb} placement lines kept, {_nb if DEV else _nd} dropped")
    if delay_src is None:
        # The overrides below splice into the delay's source. Asking for one
        # in a remix that has no delay is a mistake worth naming, not a
        # traceback.
        _dset = [v for v in ("DMODE", "DINT", "DFRZ", "DNOTE", "DFRZAT")
                 if os.environ.get(v) is not None]
        if _dset:
            sys.exit(f"{'/'.join(_dset)} set, but remix {REMIX.name!r} "
                     f"carries no DELAY SERVER")
    reverb_src = (pathlib.Path(ASM_SRC["REVERB SERVER"]).read_text()
                  if "REVERB SERVER" in ASM_SRC else None)
    if reverb_src is None:
        # Same courtesy as the delay's guard above: every one of these arms
        # splices into or substitutes the reverb's source, so asking for one
        # in a remix that has no reverb is a mistake worth naming.
        _rset = [v for v in ("NOSHIM", "MARKER", "BURN", "MODE", "PROBE",
                             "XPROBE", "TPROBE", "RVSRC")
                 if os.environ.get(v) is not None]
        if _rset:
            sys.exit(f"{'/'.join(_rset)} set, but remix {REMIX.name!r} "
                     f"carries no REVERB SERVER")
    if os.environ.get("PROBE") == "1":
        print("  *** PROBE BUILD: BusVerb replaced by dsp/page2_probe.asm ***")
    send_src = (pathlib.Path(ASM_SRC["SEND"]).read_text()
                if "SEND" in ASM_SRC else None)
    if os.environ.get("NOSHIM") == "1":
        i = reverb_src.index("; SHIMMER_BEGIN")
        j = reverb_src.index("; SHIMMER_END") + len("; SHIMMER_END")
        cut = reverb_src[i:j].count("\n")
        reverb_src = reverb_src[:i] + "; SHIMMER REMOVED (NOSHIM=1)" + reverb_src[j:]
        print(f"  shimmer excised ({cut} lines) -- NOSHIM=1 set")
    elif reverb_src is not None:
        print("  shimmer IN (default) -- NOSHIM=1 to excise")
    if RIG_BURN and send_src is not None:
        _anchor = ("        clr     a\n"
                   "        move    a,x:(r7+$67)             ; default: offset 0 (first call)\n")
        if send_src.count(_anchor) != 1:
            sys.exit(f"RIG BURN: the SEND anchor appears {send_src.count(_anchor)} "
                     f"times in {ASM_SRC['SEND']}, expected exactly 1 -- re-cut it")
        send_src = send_src.replace(_anchor, pathlib.Path("dsp/burn_send.inc").read_text() + _anchor, 1)
        print("  RIG BURN: cycle burn injected into SEND (both cores); page-2 slot 6 = BURN, 24 cycles/step")

    # ---- MARKER=1: inject the staged audible execution marks ---------------
    # See the MARKER MODE naming block above. Three marks, three sites in
    # modules/busverb/reverb_server.asm, each a distinct sound so one flash reports how
    # far proc() executes on hardware:
    #   M1 proc entry      -> whole block asr #2   = -12 dB, always
    #   M2 past role lock  -> extra -6 dB on alternating calls = ~1.4 kHz AM
    #   M3 past warm-up    -> first 4 frames zeroed = ~2.8 kHz gap train
    # The block buffer is 16 stereo frames at X:0 (dispatcher ABI, see the
    # proc: header), so the marks use absolute addresses -- no register
    # copies. M1 sits AFTER the incoming-a capture, which it would clobber.
    # CORRECTION 10 Aug: r7+$0a is NOT free -- it is a per-block tap temp for
    # line 6 (the whole r7 block $00..$83 is now full). Harmless here by
    # ordering: the engine rewrites the temp after this point and before it
    # reads it, so the engine is unaffected; the cost is that M2's flutter
    # alternation is erratic (the toggle reads the temp's LSB, not its own
    # last value). Fine for a diagnostic; do NOT copy this slot choice.
    if os.environ.get("MARKER") == "1":
        if os.environ.get("NOSHIM") != "1":
            sys.exit("MARKER=1 needs NOSHIM=1 -- the marks cost ~38 words and "
                     "payload A free words are in the build report; NOSHIM frees ~2k")
        _marks = {
            # The buffer base comes from r0 (dispatcher ABI) so the marks work
            # in BOTH the emulator harness and on hardware, and the loop count
            # from n7 (2*n7 words = this call's frames) so a split call can
            # never write past its sub-buffer.
            "; MARKER_ENTRY": """\
; ---- MARKER M1 (diagnostic): proc ran -> this call's frames -12 dB -------
        move    #>$ffffff,m5
        move    r0,x0
        move    x0,r5
        move    n7,a
        asl     #$1,a,a
        do      a,>mken
        move    x:(r5),a
        asr     #$2,a,a
        move    a,x:(r5)+
mken:""",
            "; MARKER_LOCK": """\
; ---- MARKER M2 (diagnostic): role lock passed -> alternating -6 dB -------
        move    x:(r7+$0a),a
        and     #>$1,a
        move    a1,x0
        move    x0,a
        tst     a
        beq     mkset
        clr     a
        move    a,x:(r7+$0a)
        move    #>$ffffff,m5
        move    r0,x0
        move    x0,r5
        move    n7,a
        asl     #$1,a,a
        do      a,>mkflu
        move    x:(r5),a
        asr     #$1,a,a
        move    a,x:(r5)+
mkflu:
        bra     mkgo
mkset:
        move    #>$1,a
        move    a,x:(r7+$0a)
mkgo:""",
            "; MARKER_WARM": """\
; ---- MARKER M3 (diagnostic): warm-up complete -> loud 2.8 kHz pulse ------
; A +0.5 pulse overwrites this call's first frame: unmissable, and it fires
; even if the wet path is silent -- it is what separates "stuck in warm-up"
; (no pulse) from "engine ran but wet is dead" (pulse, no tail).
        move    #>$ffffff,m5
        move    r0,x0
        move    x0,r5
        move    #>$400000,a
        move    a,x:(r5)+
        move    a,x:(r5)+""",
        }
        for _tag, _code in _marks.items():
            if reverb_src.count(_tag) != 1:
                sys.exit(f"MARKER: expected exactly one '{_tag}' in "
                         f"{ASM_SRC['REVERB SERVER']}")
            reverb_src = reverb_src.replace(_tag, _code)
        print("  *** MARKER BUILD: staged audible marks injected -- "
              "diagnostic, NOT a product build ***")

    # ---- BURN=1: INJECT the cycle burn into the LIVE engine ----------------
    if os.environ.get("BURN") == "1" and not RIG_BURN:
        _anchors = [
            # block 1 goes AFTER the call-flag stash at the top of proc: `a` is
            # already saved and nothing else is live, which is what makes the
            # register state trivially known there.
            ("dsp/burn_block1.inc",
             "        move    a,x:(r7+$14)            ; call flag: $010000 = the a=1 call\n"
             "                                        ; (the dispatcher's #$1 is left-\n"
             "                                        ; aligned), 0 = the split sub-call\n"),
            # block 2 goes after the LO filter's own comment, forcing p3's
            # coefficient to its documented exact bypass so sweeping the burn
            # knob cannot change the timbre.
            # ...and block 2 AFTER the engine's own coefficient write, not
            # before it: injected before, the real coefficient overwrites the
            # forced bypass on the next line and the burn knob keeps filtering.
            ("dsp/burn_block2.inc",
             "        move    a,x:(r7+$40)            ; LO coefficient\n"),
        ]
        for inc, anchor in _anchors:
            if reverb_src.count(anchor) != 1:
                sys.exit(f"BURN: anchor for {inc} appears "
                         f"{reverb_src.count(anchor)} times in "
                         f"{ASM_SRC['REVERB SERVER']}, expected exactly 1. The "
                         f"engine moved under the probe -- re-cut the anchor "
                         f"rather than measuring a stale copy")
            reverb_src = reverb_src.replace(
                anchor, anchor + pathlib.Path(inc).read_text(), 1)
        print("  BURN: cycle burn injected into the LIVE engine "
              "(dsp/burn_block1.inc + burn_block2.inc); p3 is the burn knob, "
              "32 cycles/step, and its filter is forced to exact bypass")

    mode_env = os.environ.get("MODE")
    if mode_env is not None:
        assert reverb_src.count("; MODE_OVERRIDE") == 1
        reverb_src = reverb_src.replace(
            "; MODE_OVERRIDE",
            "        move    #>%d,a" % (int(mode_env) << 16))
        print(f"  *** MODE OVERRIDE: forced to {int(mode_env)} ***")

    if os.environ.get("WIDTH") is not None:
        sys.exit("WIDTH= is retired (v6, 23 Aug 2026): the knob is SHFT, the "
                 "shimmer interval select, and dsp_host drives companion "
                 "fields directly -- use render_reverb -p SHFT=n")

    dmode_env = os.environ.get("DMODE")
    if dmode_env is not None:
        if delay_src.count("; DMODE_OVERRIDE") != 1:
            sys.exit("DMODE=n set but the DELAY source has no single "
                     "; DMODE_OVERRIDE marker -- a v1 delay_server.asm cannot "
                     "take a mode override")
        # DECIMAL immediate, deliberately: mode 3 << 16 is 0x30000, which
        # spelled as $30000 is indistinguishable from the payload-A Y base --
        # the census below would refuse the build, and worse, the blanket
        # $30000 -> $38000 payload substitution would rewrite the mode to
        # 0x38. dsp_asm takes decimal immediates (move #>1407,a is shipped
        # code); the string "196608" collides with nothing.
        delay_src = delay_src.replace(
            "; DMODE_OVERRIDE",
            "        move    #>%d,a" % (int(dmode_env) << 16))
        print(f"  *** DMODE OVERRIDE: BusDelay MODE forced to {int(dmode_env)} ***")

    # DINT=n forces BusDelay's PITCH interval select (0=+12, 1=+7, 2=-12,
    # 3=detune), same mechanism and reason as DMODE: the select is a companion
    # LOW-byte field (r6+$d), which dsp_host's -params cannot drive. Plain
    # small index, decimal for consistency with the DMODE precedent.
    dint_env = os.environ.get("DINT")
    if dint_env is not None:
        if delay_src.count("; DINT_OVERRIDE") != 1:
            sys.exit("DINT=n set but the DELAY source has no single "
                     "; DINT_OVERRIDE marker -- a pre-stage-2 delay_server.asm "
                     "cannot take an interval override")
        delay_src = delay_src.replace(
            "; DINT_OVERRIDE",
            "        move    #>%d,a" % int(dint_env))
        print(f"  *** DINT OVERRIDE: BusDelay PITCH interval forced to {int(dint_env)} ***")

    # DFRZ=n forces BusDelay's FREEZE select (0 = running, nonzero = hold),
    # same mechanism and reason as DMODE/DINT: slot 11 is a companion LOW-byte
    # field (r6+$e) and dsp_host's -params cannot drive it.
    dfrz_env = os.environ.get("DFRZ")
    if dfrz_env is not None:
        if delay_src.count("; DFRZ_OVERRIDE") != 1:
            sys.exit("DFRZ=n set but the DELAY source has no single "
                     "; DFRZ_OVERRIDE marker -- a pre-stage-3 delay_server.asm "
                     "cannot take a freeze override")
        delay_src = delay_src.replace(
            "; DFRZ_OVERRIDE",
            "        move    #>%d,a" % int(dfrz_env))
        print(f"  *** DFRZ OVERRIDE: BusDelay FREEZE forced to {int(dfrz_env)} ***")

    # DNOTE=n forces the MIDI-note word the ColdFire cave publishes at r6+$9
    # (0 = no note ever; 72..96 = the OT's chromatic range, 84 = unison).
    # dsp_host has no cave, so this is the only local way to hear note ->
    # interval (branch midi). Same immediate-substitution
    # mechanism as DMODE/DINT/DFRZ; the marker follows the asr, so the
    # plain value (DINT's precedent).
    dnote_env = os.environ.get("DNOTE")
    if dnote_env is not None:
        if delay_src.count("; DNOTE_OVERRIDE") != 1:
            sys.exit("DNOTE=n set but the DELAY source has no single "
                     "; DNOTE_OVERRIDE marker")
        delay_src = delay_src.replace(
            "; DNOTE_OVERRIDE", "        move    #>%d,a" % int(dnote_env))
        print(f"  *** DNOTE OVERRIDE: BusDelay MIDI note word forced to {int(dnote_env)} ***")

    dfrzat_env = os.environ.get("DFRZAT")
    if dfrzat_env is not None:
        if dfrz_env is not None:
            sys.exit("DFRZ and DFRZAT are mutually exclusive -- one freeze "
                     "override at a time")
        if os.environ.get("DEV") is None:
            sys.exit("DFRZAT=n is a DEV-only repro hook (its counter word "
                     "lives in payload A's shared-window half and its words "
                     "do not fit the shipping payload B region) -- set DEV=1")
        if delay_src.count("; DFRZ_OVERRIDE") != 1:
            sys.exit("DFRZAT=n set but the DELAY source has no single "
                     "; DFRZ_OVERRIDE marker")
        delay_src = delay_src.replace(
            "; DFRZ_OVERRIDE",
            "        move    y:>$37ffe,a\n"
            "        add     #>1,a\n"
            "        move    a,y:>$37ffe\n"
            "        move    #>%d,x0\n"
            "        sub     x0,a\n"
            "        move    #>0,x0\n"
            "        tmi     x0,a\n"
            "        move    #>1,x0\n"
            "        tpl     x0,a" % int(dfrzat_env))
        print(f"  *** DFRZAT OVERRIDE: BusDelay freezes after "
              f"{int(dfrzat_env)} post-warm blocks ***")

    # ---- XBUS=1: move the bus scratch into the SHARED window ---------------
    if os.environ.get("XBUS") == "1":
        # Overridable so the next round is a one-liner, not a code edit.
        XBUS_BASE = int(os.environ.get("XBUS_BASE", "36000"), 16)

        def xbus(src, name, label):
            n = len(re.findall(r"\$9[0-9a-f]{2}\b", src))
            if not n:
                sys.exit(f"XBUS: {name} has no bus scratch literals to move")
            n_priv = len(re.findall(r"\$09[0-9a-f]{2}\b", src))
            # RATE increments were 4 refs (0901h/0902h) until the wow went,
            # 15 Sep 2026; a v6+ source has 4 for the freeze-crossfade ramp
            # (satdrv tail load/store, per-block re-arm load/store). Keyed on
            # the words' presence so verify_delay can still build an older
            # REFERENCE source.
            n_want = (4 if "y:>$0901" in src else 0) + (4 if "y:>$0904" in src else 0)
            # + 2 for the TIME slew state (load + store)
            n_want += 2 if "y:>$0907" in src else 0
            # + 4 for the sticky-snap state: last knob + held division,
            # load + store each
            n_want += 4 if "y:>$0908" in src else 0
            n_want += (3 if "note starts at NONE" in src else 2) \
                if "y:>$090a" in src else 0
            # + 5 for the RETD return-liveness state: the grace
            # counter $090b (load + store) and this block's host print gain
            # $090c (store, then one load per channel in the output stage)
            n_want += 5 if "y:>$090b" in src else 0
            # + 3 for the MIDI-clock period derived from stock's tempo24:
            # $090d (store, then the two sticky-snap reads)
            n_want += 3 if "y:>$090d" in src else 0
            if name == "DELAY SERVER" and n_priv != n_want:
                sys.exit(f"XBUS: {name} expected exactly {n_want} core-private "
                         f"$09xx refs (RATE state, freeze ramp, slew, snap, note, RETD, tempo), "
                         f"found {n_priv}")
            src = re.sub(r"\$9([0-9a-f]{2})\b",
                         lambda m: "$%x" % (XBUS_BASE + int(m.group(1), 16)), src)
            if src.count("; XBUS_GATE") != 1:
                sys.exit(f"XBUS: {name} is missing its ; XBUS_GATE marker")
            hkb = os.environ.get("HKB") == "1"
            print(f"  XBUS: {name} -- {n} scratch refs moved to 0x{XBUS_BASE:05x}, "
                  f"housekeeping gated to payload {'B  *** HKB=1 DIAGNOSTIC ***' if hkb else 'A'}")
            return src

        # DELAY SERVER is dropped for this test -- it is an untested first
        # draft and the architecture question needs only a SERVER and a SENDER.
        # Its words are what pays for the gates (historical sizing: 507 words
        # against a region that then had 11 free).
        if send_src is not None:
            send_src = xbus(send_src, "SEND", "notfirst")
        # A PROBE build replaces the reverb's engine with a diagnostic that is
        # not a bus client at all: it has no scratch literals to relocate and
        # no housekeeping to gate, so xbus() would refuse it for lacking the
        # very things it correctly does not have. That refusal is what made
        # PROBE/XPROBE/TPROBE unbuildable in the one layout where they fit --
        # the layout that stubs the delay and leaves room for them.
        #
        # The guard stays exactly as strict for every real engine: this skips
        # the treatment for a substituted probe source, it does not weaken the
        # check for anything that is actually on the bus.
        if reverb_src is None:
            pass                    # this remix carries no reverb at all
        elif not _REVERB_IS_PROBE:
            reverb_src = xbus(reverb_src, "REVERB SERVER", "bus_notfirst")
        else:
            print("  XBUS: REVERB SERVER is a PROBE -- no bus scratch to move, "
                  "no housekeeping to gate")
        # ...except under DEV, where the delay IS present and must reach the
        # same relocated scratch as everyone else -- 14 scratch refs and a
        # ; XBUS_GATE marker are already in modules/busdelay/delay_server.asm, and its
        # housekeeping block exits to bus_notfirst exactly like the reverb's.
        # A delay that still read Y:0x900 would find an empty accumulator and
        # render silence, which is the failure this hatch exists to prevent.
        # ...and under SPEC for the same reason: payload B's BusDelay IS a real
        # server reading the shared accumulator, so it needs the identical
        # relocation. Its housekeeping gate is what keeps payload B from
        # zeroing buffers payload A owns.
        if (DEV or SPEC) and delay_src is not None:
            delay_src = xbus(delay_src, "DELAY SERVER", "bus_notfirst")

    # Every source now carries a $30000 that must be substituted per payload,
    # not just DELAY SERVER's Y base -- the gate above uses the same literal as
    # its payload discriminator, which is why this count is 2 under XBUS.
    # Plain build: 1 (the Y base). XBUS: 0, the source is a stub. XBUS+DEV: 2 --
    # the Y base AND the payload-discriminator literal the gate injection just
    # added, and _sub below is meant to rewrite BOTH (base -> 0x38000 is
    # correct for payload B's delay; discriminator -> 0x38000 is what makes the
    # gate compare equal there).
    # Was 2 under XBUS+DEV/SPEC when the gate injection added a second
    # $30000 as its payload discriminator. The gate is emitted per payload now
    # and carries no literal, so only the Y base remains.
    _want = (1 if DEV or SPEC else 0) if os.environ.get("XBUS") == "1" else 1
    if delay_src is not None and delay_src.count("$30000") != _want:
        sys.exit(f"expected exactly {_want} $30000 literal(s) in the DELAY source")

    dev_delay = None            # (words) for the .mem dump append, DEV only
    for tag, va, ln in PAYLOADS:
        pp = PP[tag]
        mods, _ = modules(bytes(img), va, ln)

        def record(addr):
            rec = [m for m in mods if m[0] == 0 and m[1] == addr]
            if len(rec) != 1:
                sys.exit(f"payload {tag}: expected one P module at 0x{addr:05x}")
            return rec[0]

        print(f"-- payload {tag} --")

        # ---- the servers pack into the HARVESTED effects' code -----------
        # The donor region is not a place, it is a choice: the thirteen DSP
        # effects are contiguous and each is self-contained, so any unbroken
        # run of them is placeable ground (schema.Remix.harvest,
        # stock.p_spans). `DEFAULT_HARVEST` is the three reverbs, which is
        # what every remix did before -- so a default selection
        # writes the same bytes it always has (refhash).
        #
        # DEV=1 adds CHORUS, which sits immediately BELOW PLATE; the
        # contiguity assert is what proves that rather than assuming it.
        # Dev-only; the flashable build leaves CHORUS alone unless a remix
        # asks for it.
        # ⚠️ DERIVED FROM THE TWO CHOOSERS. An effect on neither is one this
        # remix does not want, and giving up its words is the same decision
        # -- see stock.harvested(). The largest contiguous run of them is the
        # region; the rest are simply unlisted and keep their code.
        _listed = set(REMIX.modules) | set(
            REMIX.fx1 or [k for k in stock_mod.p_spans("A")
                          if _MODS[k].menu.fx2_id in stock_mod.fx1_ids()])
        # ⚠️ IN ADDRESS ORDER. DEV's CHORUS sits BELOW the reverbs, and the
        # report lists the donors in this order -- appending it put CHORUS
        # last and changed every DEV case's report hash (refhash caught it).
        _derived = stock_mod.region_of(stock_mod.harvested(_listed))
        _dev_chorus = DEV and "CHORUS" not in _derived
        _harvest = sorted(
            set(_derived)
            # DEV takes CHORUS whether or not a chooser lists it -- that is
            # the hatch's whole point, and why a DEV build is never flashed
            # ("taking CHORUS costs FX1 its chorus", the module docstring).
            | ({"CHORUS"} if DEV else set()),
            key=lambda k: stock_mod.p_spans(tag)[k][0])
        if not _harvest:
            # Nothing harvested is the honest default for a stock chooser --
            # every word belongs to a stock effect that is using it -- but a
            # module of ours has to go somewhere.
            _need = [m for m in _SEL if m.dsp is not None]
            if _need:
                sys.exit(f"payload {tag}: nothing is harvested, so there is "
                         f"nowhere to place "
                         f"{', '.join(sorted(m.key for m in _need))}. Name "
                         f"the stock effects whose words this remix may take "
                         f"Take one off both choosers to give up "
                         f"its words.")
        _sp = stock_mod.p_spans(tag)
        for _k in _harvest:
            if _k not in _sp:
                sys.exit(f"harvest={_k!r}: not a stock effect with DSP code "
                         f"in payload {tag} (have: "
                         f"{', '.join(sorted(_sp))})")
        # ⚠️ EVERY RECORD INSIDE A HARVESTED SPAN, not one per effect. PHASER
        # is FIVE records -- its true extent runs 41 words past the one that
        # bears its name, into four small blocks it enters by falling off its
        # own end (docs/firmware/DSP.md s8) -- so keying the region by effect would
        # have placed 157 of its 207 words and left the rest as a hole in the
        # middle of the stream.
        _want = [_sp[k] for k in _harvest]
        region = sorted((m for m in mods if m[0] == 0
                         and any(a <= m[1] < a + n for a, n in _want)),
                        key=lambda m: m[1])
        _have = sum(m[2] for m in region)
        if _have != sum(n for _a, n in _want):
            sys.exit(f"payload {tag}: the harvested spans cover "
                     f"{sum(n for _a, n in _want)} words but their P records "
                     f"total {_have} -- the module map and stock.p_spans "
                     f"disagree")
        runs = []
        for _rec in region:
            if runs and runs[-1]["base"] + runs[-1]["words"] == _rec[1]:
                runs[-1]["words"] += _rec[2]
            else:
                runs.append({"base": _rec[1], "words": _rec[2]})
        for _r in runs:
            _r["cursor"] = _r["base"]
        # With nothing harvested there is no region at all -- legal, and
        # what a pure stock chooser is. `_need` above has already refused it
        # if anything wanted placing, so the rest of this runs over an empty
        # stream and writes nothing.
        base_a = region[0][1] if region else 0
        budget = sum(m[2] for m in region)

        def _end_of_run(a):
            """End address of the run containing `a` (its own value if none)."""
            for r in runs:
                if r["base"] <= a < r["base"] + r["words"]:
                    return r["base"] + r["words"]
            return a

        def _written(a):
            """Did the placed code actually reach address `a`?"""
            for r in runs:
                if r["base"] <= a < r["base"] + r["words"]:
                    return a < r["cursor"]
            return False

        def place(words, start):
            """Write a contiguous word stream at P address `start`.

            The records load back-to-back but are separated by headers in the
            file, so the stream is cut at each record boundary.
            """
            i = 0
            for _, a, cnt, off in region:
                if i >= len(words):
                    break
                pos = start + i
                if not (a <= pos < a + cnt):
                    continue
                n = min(len(words) - i, a + cnt - pos)
                for k in range(n):
                    wrw_p(va + off + (pos - a + k) * 3, words[i + k])
                i += n
            if i != len(words):
                sys.exit(f"payload {tag}: placement ran past the region")

        # SEND first, DELAY SERVER last so the trailing free words belong to
        # the algorithm still to be designed.
        # Under XBUS every source carries the payload discriminator, so all
        # three get the substitution rather than DELAY SERVER alone.
        # Under XBUS the SENDER and SERVER carry the payload discriminator, so
        # they get the substitution; the delay slot is a bare stub.
        _sub = lambda s: s.replace("$30000", f"${pp['ybase']:x}")
        _x = os.environ.get("XBUS") == "1"

        # ---- ROTLATCH: resolve this block's write offset, per payload ------
        _rot = XBUS_BASE if os.environ.get("XBUS") == "1" else 0x900

        # ---- the XBUS payload gate, emitted per payload --------------------
        # Exactly ONE payload housekeeps. The other is sent straight to its
        # notfirst label so it still finds this block's buffers but never flips
        # the rotation or clears anything -- both cores number their instances
        # from zero, so without this each core's position 0 would believe it is
        # the housekeeper and they would flip the shared rotation twice a block.
        # HKB=1 swaps which payload is gated (a DIAGNOSTIC, never shipped).
        _GATE_LABEL = {"SEND": "notfirst", "REVERB SERVER": "bus_notfirst",
                       "DELAY SERVER": "bus_notfirst"}
        _hkb = os.environ.get("HKB") == "1"

        def _gate(src, name):
            if "; XBUS_GATE" not in src:
                return src
            # DEV places the delay in payload A but it must behave as payload B
            # -- it is not the housekeeper there either; SEND's self-healing
            # election covers that, exactly as on hardware.
            gated = (tag == ("A" if _hkb else "B")) or (DEV and name == "DELAY SERVER")
            label = _GATE_LABEL[name]
            if not gated:
                return src.replace("; XBUS_GATE",
                                   f";  (payload {tag} housekeeps: no gate emitted)", 1)
            # ⚠️ EXCISED, NOT BRANCHED OVER. Until then the
            # gated payload carried the whole housekeeping block behind a
            # 2-word `bra <label>`: 72 dead words in SEND, 70 in the delay,
            # on a payload that was at FREE 5 once and 193 the day this
            # landed. The block runs from the marker to its exit label and
            # nothing outside it reaches in -- checked HERE, not assumed:
            # every label the span defines must be referenced only inside
            # it, and every r7 slot it STORES must be read nowhere outside
            # (SEND's last-seen rotation at r7+$68 and the delay's at
            # r7+$88 are the block's own; the delay's later r7+$68 is its
            # LineR base, a different slot in a different file). The exit
            # label itself is kept: the block below it is the everyone-path.
            # Behaviourally identical to the bra: the branch was
            # unconditional, so no instruction in the span could execute.
            i = src.index("; XBUS_GATE")
            j = src.find(f"\n{label}:", i)
            if j < 0:
                sys.exit(f"XBUS: {name}: no `{label}:` after its ; XBUS_GATE marker")
            j += 1                              # keep the exit label's line
            span, rest = src[i:j], src[:i] + src[j:]
            _code = lambda s: "\n".join(l.split(";", 1)[0] for l in s.splitlines())
            _rest_code = _code(rest)
            for lab in re.findall(r"^([A-Za-z_]\w*):", _code(span), re.M):
                if re.search(rf"\b{re.escape(lab)}\b", _rest_code):
                    sys.exit(f"XBUS: {name}: label `{lab}` inside the gated "
                             f"housekeeping block is referenced outside it -- "
                             f"the block cannot be excised")
            for slot in set(re.findall(r",x:\(r7\+\$([0-9a-f]+)\)", _code(span))):
                if re.search(rf"x:\(r7\+\${slot}\)", _rest_code):
                    sys.exit(f"XBUS: {name}: r7+${slot} is stored by the gated "
                             f"housekeeping block and read outside it -- "
                             f"the block cannot be excised")
            _n = sum(1 for l in _code(span).splitlines()
                     if l.strip() and not re.match(r"^\w+:\s*$", l.strip()))
            return (src[:i]
                    + f";  payload {tag} never housekeeps: the housekeeping "
                      f"block ({_n} instructions, marker -> {label}) is "
                      f"EXCISED by build_bus.py, not branched over\n"
                    + src[j:])

        def _rotinit(src, name, slot):
            """Seed the tracked rotation at init. PAYLOAD B ONLY."""
            if "; ROTINIT" not in src:
                return src
            as_b = (tag == "B") or (DEV and name == "DELAY SERVER")
            if not as_b:
                return src.replace("; ROTINIT",
                                   f";  (payload {tag} recomputes every block: "
                                   f"nothing to seed)", 1)
            body = "\n".join([
                "        move    r7,a                ; ROTINIT (payload B)",
                "        move    #>$6200,x0",
                "        cmp     x0,a",
                "        blt     seedskip            ; implausible r7: seed nothing",
                f"        move    y:>${_rot:x},a",
                "        and     #>$30,a",
                f"        move    a,x:(r7+${slot:02x})",
                "seedskip:"])
            return src.replace("; ROTINIT", body, 1)

        def _rotlatch(src, name, slot):
            if "; ROTLATCH" not in src:
                return src
            # DEV places the delay in payload A but it behaves as payload B in
            # every other respect (its gate compares equal, so it never
            # housekeeps) -- so it takes payload B's body wherever it sits.
            as_b = (tag == "B") or (DEV and name == "DELAY SERVER")
            if as_b:
                _latch = _rot + 0xc6
                body = "\n".join([
                    "        move    x:(r7+$67),a        ; ROTLATCH: payload B, ONE tracker per core",
                    "        tst     a",
                    "        bne     rotdone             ; not the block's first call",
                    "        move    r7,a",
                    "        move    #>$6200,x0",
                    "        cmp     x0,a                ; position 0's FX2 (the rig's delay host)",
                    "        bne     rotchk              ; advances the core's tracker once a frame",
                    f"        move    y:>${_latch:x},a",
                    "        add     #>$10,a             ; T' = T + one step",
                    "        and     #>$30,a",
                    "        move    a1,x0",
                    "        move    x0,a                ; A2-clean",
                    f"        move    a,y:>${_latch:x}",
                    "rotchk:",
                    f"        move    y:>${_latch:x},a",
                    "        move    a,x1                ; x1 = T, the core's tracked rotation",
                    f"        move    y:>${_rot:x},a         ; R, the shared word (pre- or post-flip)",
                    "        and     #>$30,a",
                    "        move    a1,x0",
                    "        move    x0,a                ; x0 = R",
                    "        cmp     x1,a",
                    "        beq     rotuse              ; T == R: aligned, use T",
                    "        add     #>$10,a",
                    "        and     #>$30,a",
                    "        move    a1,y0               ; y0 = R + one step",
                    "        move    x1,a",
                    "        cmp     y0,a",
                    "        beq     rotuse              ; T == R+1: a pre-flip read, keep T",
                    "        move    x0,a                ; anything else: T is stale, snap to R",
                    f"        move    a,y:>${_latch:x}",
                    "rotuse:",
                    f"        move    y:>${_latch:x},a",
                    f"        move    a,x:(r7+${slot:02x})",
                    "rotdone:",
                    f"        move    x:(r7+${slot:02x}),a"])
            else:
                body = "\n".join([
                    f"        move    y:>${_rot:x},a       ; ROTLATCH: payload A is in",
                    "        and     #>$30,a             ; lockstep with the flip, so",
                    f"        move    a,x:(r7+${slot:02x})       ; the shared word is stable"])
            out = src.replace("; ROTLATCH", body, 1)
            # Guard the trap above: under XBUS no bare $9xx may survive, in the
            # body or anywhere else. A stale one reads core-private memory.
            if os.environ.get("XBUS") == "1" and re.search(r"\$9[0-9a-f]{2}\b", body):
                sys.exit(f"ROTLATCH: {name}'s body still has an unrelocated "
                         f"$9xx literal -- it would read core-private Y")
            return out

        # ⚠️ NOT assigned back to send_src/delay_src: this loop runs once per
        # payload, and mutating the module-level source would make payload B
        # substitute into payload A's already-substituted text. The result is
        # threaded through `plan` below as a local instead.
        # ⚠️ Substituted unconditionally, not only under XBUS: the sites that
        # read the resolved slot exist in every build, so leaving the marker
        # as a bare comment would have them reading an uninitialised r7 word.

        def _prep(src, name, slot):
            if _x:
                src = _gate(src, name)
            if slot is not None:
                src = _rotinit(src, name, slot)
                src = _rotlatch(src, name, slot)
            return src

        # The placement plan, built from the manifests rather than spelled
        # out. Order is DspSection.priority and it is BYTE-LOAD-BEARING: the
        # region is packed in this order, so SEND first (the fallback alias
        # needs its entry points to exist) and the delay last, so the region's
        # trailing free words belong to the algorithm still being designed.
        _texts = {}
        if send_src is not None:
            _texts["SEND"] = send_src
        if reverb_src is not None:
            _texts["REVERB SERVER"] = reverb_src
        if delay_src is not None:
            _texts["DELAY SERVER"] = delay_src
        # Any other selected module with DSP code loads straight from its
        # manifest's source. A module that is a BUS CLIENT without being one
        # of the three (a BamSep26 station: Harness.bus_client on an insert)
        # gets the one bus treatment it needs -- its `$9xx` scratch literals
        # relocated to the shared window under XBUS, exactly SEND's regex --
        # and NOT the housekeeping gate, because a station never elects (its
        # source has no XBUS_GATE marker and reads the rotation only). Its
        # ROTINIT / ROTLATCH markers are substituted by _prep like SEND's.
        # It MAY also declare its own DEV repro hooks below -- the generic version of the arms the three
        # core sources have at the top of main().
        for _k in CARRIED:
            if _k not in _texts and _k in ASM_SRC:
                _src_k = _dev_hooks(_k, pathlib.Path(ASM_SRC[_k]).read_text())
                _mk = remix_modules().get(_k)
                if (_x and _mk is not None and _mk.harness is not None
                        and _mk.harness.bus_client):
                    _n9 = len(re.findall(r"\$9[0-9a-f]{2}\b", _src_k))
                    if not _n9:
                        sys.exit(f"XBUS: {_k} is a bus client with no bus scratch "
                                 f"literals to move")
                    _src_k = re.sub(r"\$9([0-9a-f]{2})\b",
                                    lambda m: "$%x" % (XBUS_BASE + int(m.group(1), 16)),
                                    _src_k)
                    print(f"  XBUS: {_k} -- {_n9} scratch refs moved to 0x{XBUS_BASE:x}, "
                          f"a client that never housekeeps")
                _texts[_k] = _src_k

        def _ybase(m, src):
            if DEV and m.dsp.dev_pin_ybase is not None:
                return src.replace("$30000", f"${m.dsp.dev_pin_ybase:x}")
            if m.dsp.ybase is YBase.ALWAYS or (m.dsp.ybase is YBase.XBUS and _x):
                return _sub(src)
            return src

        # ---- GRAINS: BusDelay's GRAIN reader, four per line or two -------
        # A CYCLE LEVER (schema.Remix.grains). The substitution itself lives
        # in tools/remix/grains.py, imported by the PRICER too -- they
        # disagreed the first time this was written, and an image rolled to
        # two grains that `make cycles` still prices at four hides the exact
        # saving the lever exists for.
        if REMIX.grains != 4 and "DELAY SERVER" in _texts:
            from remix import grains as _grains
            try:
                _texts["DELAY SERVER"] = _grains.roll(_texts["DELAY SERVER"],
                                                      REMIX.grains)
            except ValueError as _e:
                sys.exit(f"grains={REMIX.grains}: {_e} -- the GRAIN reader "
                         f"moved under the lever")
            print(f"  GRAINS: BusDelay's GRAIN reader rolled to "
                  f"{REMIX.grains} per line (offset G/2, makeup doubled)")

        # ---- HOSTGUARD: a HIDDEN engine runs on its host slot only --------
        # A hidden engine (schema.Remix.hidden) is hosted by the project's
        # stamp, not by the chooser. Dispatch is per id and shared by every
        # track, so an old part naming that id on another track would get a
        # SECOND instance sharing this one's hardcoded Y base -- two reverbs
        # writing one tank. The gate is r7 == 0x6200, the bank's first FX2
        # state block (docs/firmware/DSP.md "The allocator's instance model"), which
        # is exactly the condition the engines' position-0 housekeeping
        # election already uses, so the two can never disagree.
        #
        # ⚠️ SUBSTITUTED, NOT SHIPPED IN THE SOURCE, and the local render
        # harness is why: render_reverb.py runs the reverb at -r7 4, the
        # bank's SECOND slot, so a guard compiled in unconditionally would
        # render every voicing pass and every verify_roll comparison DRY.
        # It goes in only for a remix that asks, and `hidden` is the ask.
        # A module OPTS IN by carrying the marker. Hiding alone must not
        # gate anything: SEND is hidden in a remix whose FX2 pages are all
        # blank, and it still has to run on every track -- a fresh track IS
        # a send, and it does the bus housekeeping.
        for _k in HIDDEN:
            if _k not in _texts or "; HOSTGUARD\n" not in _texts[_k]:
                continue
            if _texts[_k].count("; HOSTGUARD\n") != 1:
                sys.exit(f"{_k}: more than one ; HOSTGUARD marker")
            _texts[_k] = _texts[_k].replace("; HOSTGUARD\n", """
        move    r7,a
        move    #>$6200,x0
        cmp     x0,a
        bne     hostquit                ; not the host slot: exact dry pass
""", 1) + """
hostquit:
        rts
"""
            print(f"  HOSTGUARD: {_k} runs on r7=0x6200 only, dry elsewhere")

        plan = tuple(
            (m.key, _prep(_ybase(m, _texts[m.key]), m.key, m.dsp.r7_latch_slot))
            for m in sorted((remix_modules()[k] for k in CARRIED
                             if k in _texts), key=lambda m: m.dsp.priority))
        if _x:
            _g = [n for n, t in plan if "never housekeeps" in t]
            print(f"  payload {tag}: housekeeping "
                  f"{'GATED OUT of ' + ', '.join(_g) if _g else 'ENABLED (this payload housekeeps)'}")
        # SPEC: each core carries only the engine it actually runs. Payload A
        # keeps the reverb, payload B the delay; the other is not placed at all
        # and its id is aliased to the fallback after placement (it needs its
        # which only exists once SEND has been assembled at this cursor).
        absent = None
        if SPEC:
            absent = "DELAY SERVER" if tag == "A" else "REVERB SERVER"
            plan = tuple(p for p in plan if p[0] != absent)
            # A remix that never carried that module has nothing to specialize
            # away, and its id is already handled by the omitted-id alias.
            if absent not in NEW_IDS:
                absent = None
        if NO_FB:
            # The DSP half of the NONE fallback, and it needs no new code:
            # the per-payload null stub is already in the image and is what
            # the build points a silenced donor id at, described there as
            # proven. Set before placement because nothing below assigns
            # fb_init/fb_proc when the fallback is not a module.
            fb_init, fb_proc = pp["nul_i"], pp["nul_p"]
            wrw_p(pp["xtab"] + NONE_ID * 3, fb_init)
            wrw_p(pp["xtab"] + (32 + NONE_ID) * 3, fb_proc)
        cursor = base_a
        # LFO roll table: reverb_server.asm's rolled lines 2-7
        # read per-line [rate const, phase slot, int slot, frac slot] from a
        # 24-word P table via p:(r5)+. Placed immediately BEFORE the module so
        # the address is known pre-assembly; the source's $facade literal is
        # rewritten to it. dsp_asm has no dc directive, hence raw words here.
        #: lines 0 and 1 joined the roll, in their own two-trip
        # loop. They carry SIX-word records -- they drive the in-loop ALLPASS
        # modulator as well as the tank one, which is why the 10 Aug pass left
        # them out. Their records come FIRST so one r5 walks straight from
        # record 1 into record 2 and the two loops share their whole setup.
        # [rate const, phase slot, AP int, AP frac, MOD int, MOD frac]
        LFO01 = [0x7f0000, 0x3e, 0x52, 0x53, 0x21, 0x22,   # line 0  1.000x
                 0x6cc000, 0x4f, 0x54, 0x55, 0x23, 0x24]   # line 1  1.168x
        LFOTAB = [0x5b0000, 0x50, 0x56, 0x57,   # line 2  0.711x
                  0x4a0000, 0x51, 0x58, 0x59,   # line 3  0.578x
                  0x760000, 0x47, 0x00, 0x01,   # line 4  0.922x
                  0x610000, 0x48, 0x02, 0x03,   # line 5  0.758x
                  0x4d0000, 0x49, 0x04, 0x05,   # line 6  0.602x
                  0x370000, 0x4a, 0x06, 0x07]   # line 7  0.430x
        # ⚠️ THE TABLE MUST FOLLOW THE SOURCE. An engine that has not been
        # through the 17 Aug 0-1 roll reads record 2 FIRST, so prefixing the
        # 0/1 records unconditionally would feed line 0's data to line 2 --
        # silently, and in a build that still assembles. Keyed off a marker
        # the rolled source carries, so verify_roll can hold BOTH engines at
        # once and compare them.
        LFO01_MARK = "LFO lines 0-1: ROLLED TOO"
        PTABLE_MARK = "$fab1e0"          # schema.DspSection.ptable's literal

        # ---- XTABLE: the P tables go to the stock curve bank ------------
        _xt_base, _xt_words = stock_mod.CURVE_BANK
        _xt_readers = stock_mod.curve_bank_readers()
        _xt_kept = sorted({k for ks in _xt_readers.values() for k in ks
                           if k == "OUTSIDE-DONOR" or k in _listed})
        _xt_tables = [k for k in sorted((k for k in CARRIED if k in _texts),
                                        key=lambda k: _MODS[k].dsp.priority)
                      if "$facade" in _texts[k] or PTABLE_MARK in _texts[k]]
        _pristine = IMG.read_bytes()
        _xt_rec = {t: stock_mod.curve_bank_record(_pristine, t) for t in "AB"}
        _xt_same = (all(_xt_rec.values()) and
                    _pristine[_xt_rec["A"][0]:_xt_rec["A"][0] + _xt_words * 3]
                    == _pristine[_xt_rec["B"][0]:_xt_rec["B"][0] + _xt_words * 3])
        _xt_layout, _xt_sites = {}, {}
        if _xt_tables and _xt_kept:
            print(f"  XTABLE: P tables stay in P -- "
                  f"{', '.join(_xt_kept)} reads the stock curve bank "
                  f"X:0x{_xt_base:05x} and is kept in the image")
        elif _xt_tables and not _xt_same:
            print(f"  XTABLE: P tables stay in P -- the stock curve bank "
                  f"X:0x{_xt_base:05x} is not one identical 4,096-word "
                  f"record in both payloads of this image")
        elif _xt_tables:
            _xa = _xt_base
            for _k in _xt_tables:
                _t = _texts[_k]
                # A module may carry BOTH the LFO table and its own ptable
                # (the reverb): they go in one slot, LFOTAB
                # first, and each literal is rewritten to its own start.
                _n = ((len(LFO01 + LFOTAB) if LFO01_MARK in _t else len(LFOTAB))
                      if "$facade" in _t else 0) \
                    + (len(_MODS[_k].dsp.ptable) if PTABLE_MARK in _t else 0)
                _xt_layout[_k] = (_xa, _n)
                _xa += _n
            if _xa > _xt_base + _xt_words:
                sys.exit(f"payload {tag}: the P tables ({_xa - _xt_base} words) "
                         f"overrun the stock curve bank ({_xt_words} words)")
            print(f"  XTABLE: P tables parked in the stock curve bank "
                  f"X:0x{_xt_base:05x}..0x{_xa:05x} ({_xa - _xt_base} words) -- "
                  f"every stock reader of it "
                  f"({'/'.join(sorted({k for ks in _xt_readers.values() for k in ks}))}) "
                  f"is harvested (static scan, not a read-watch)")

        def place_x(words, start):
            """Write table words into this payload's copy of the curve bank."""
            off, cnt = _xt_rec[tag]
            if not (_xt_base <= start and start + len(words) <= _xt_base + cnt):
                sys.exit(f"payload {tag}: X table at 0x{start:05x} runs past "
                         f"the curve bank record")
            for k, w in enumerate(words):
                wrw_p(BASE + off + (start - _xt_base + k) * 3, w)

        def _p2x(src, name):
            """Every `p:(` table read in the CODE becomes `x:(`; comments
            are left alone. Returns (source, sites)."""
            out, n = [], 0
            for l in src.split("\n"):
                code, sep, cmt = l.partition(";")
                if re.search(r"\bp:", code) and "p:(" not in code:
                    sys.exit(f"XTABLE: {name} reads P memory other than "
                             f"through p:(rN) -- {l.strip()!r}; a module "
                             f"with a table may read P for nothing else")
                n += code.count("p:(")
                out.append(code.replace("p:(", "x:(") + sep + cmt)
            if not n:
                sys.exit(f"XTABLE: {name} has a table but no p:( read of it")
            return "\n".join(out), n

        for name, src in plan:
            if "$facade" in src and src.count("$facade") != 1:
                sys.exit(f"payload {tag}: {name} has multiple $facade "
                         f"LFOTAB literals -- expected exactly one")
            _ptab = list(remix_modules()[name].dsp.ptable) if name in remix_modules() else []
            if PTABLE_MARK in src and (not _ptab or src.count(PTABLE_MARK) > 1):
                sys.exit(f"payload {tag}: {name}: a DspSection.ptable and exactly one "
                         f"{PTABLE_MARK} literal in the source go together "
                         f"(table {len(_ptab)} words, literal x{src.count(PTABLE_MARK)})")
            if _ptab and PTABLE_MARK not in src:
                # The manifest declares a table this SOURCE never reads: an
                # alternate engine (RVSRC= / DLSRC=, the reference side of
                # verify_roll / verify_delay) from before the module owned
                # one. Keyed on the source, like the LFO table, so the two
                # engines build through one manifest.
                print(f"  {name}: declares a {len(_ptab)}-word ptable the "
                      f"source does not read -- not placed")
                _ptab = []
            if DEV and name == "DELAY SERVER":
                # DEV: the delay does NOT go in the donor region. It is
                # assembled at DEV_DELAY_P (see that constant) and its module
                # record is appended to the .mem dump after the image is
                # written -- the payload has no slack for a new record, and
                # dsp_host boots the dump, not the image. The dispatch
                # entries in THIS image do point at DEV_DELAY_P, so the DEV
                # .bin carries a dangling dispatch: one more reason it is
                # never flashed. The region below now carries only SEND +
                # LFOTAB + reverb, so the delay's growth budget is payload
                # B's, not the hatch's.
                # Its table:
                # parked in the stock curve bank like everyone else's when
                # the bank is free, else it LEADS the out-of-region record
                # at DEV_DELAY_P and the code follows it -- the dump's one
                # P record carries both, at the origin the code was
                # assembled against.
                _xa, _at, _lead = _xt_layout.get(name), DEV_DELAY_P, []
                if _ptab and _xa is not None:
                    src, _xt_sites[name] = _p2x(
                        src.replace(PTABLE_MARK, f"${_xa[0]:x}"), name)
                    if len(_ptab) != _xa[1]:
                        sys.exit(f"payload {tag}: {name}'s table is "
                                 f"{len(_ptab)} words, its X slot {_xa[1]}")
                    place_x(_ptab, _xa[0])
                    print(f"  {'PTABLE':13} X:0x{_xa[0]:05x}..0x{_xa[0] + len(_ptab):05x} "
                          f"({len(_ptab):4d} words)  {name}'s table  in the stock "
                          f"curve bank, {_xt_sites[name]} p:( reads -> x:(")
                elif _ptab:
                    src = src.replace(PTABLE_MARK, f"${DEV_DELAY_P:x}")
                    _at, _lead = DEV_DELAY_P + len(_ptab), list(_ptab)
                    print(f"  {'PTABLE':13} P:0x{DEV_DELAY_P:05x}..0x{_at:05x} "
                          f"({len(_ptab):4d} words)  {name}'s table  (DEV: leads "
                          f"the out-of-region record)")
                words, init_a, proc_a = assemble(src, _at)
                if _at + len(words) >= 0x20000:
                    sys.exit(f"payload {tag}: DEV delay overruns the "
                             f"entry-point plausibility bound "
                             f"(0x{_at + len(words):05x} >= 0x20000)")
                wrw_p(pp["xtab"] + NEW_IDS[name] * 3, init_a)
                wrw_p(pp["xtab"] + (32 + NEW_IDS[name]) * 3, proc_a)
                if tag == "A":
                    dev_delay = _lead + list(words)
                print(f"  {name:13} P:0x{_at:05x}..0x"
                      f"{_at + len(words):05x} ({len(words):4} words)"
                      f"  id 0x{NEW_IDS[name]:02x}  Y base 0x38000  "
                      f"(DEV: OUT OF REGION, code lives in the .mem dump)")
                continue
            # ---- pick a RUN that fits, lowest address first --------------
            # A module is one code stream, so it goes wholly inside one run.
            # First-fit in address order: with a single run this is exactly
            # the old bump cursor, byte for byte (refhash). The LFO table
            # rides with its module so the address the module was assembled
            # against is always in the same run.
            # ⚠️ THE MODULE IS ASSEMBLED ONCE PER CANDIDATE, because its
            # origin is an argument -- cheap (the whole build is ~0.3 s) and
            # it keeps the length honest instead of assuming origin-invariant
            # encoding, which is exactly the kind of assumption this codebase
            # has been burned by.
            _fit, _last = None, None
            _xa = _xt_layout.get(name)          # (X address, words) or None
            for _r in runs:
                _c, _end = _r["cursor"], _r["base"] + _r["words"]
                _tab, _s2, _lfo = None, src, "$facade" in src
                # LFOTAB, the module's ptable, or BOTH in one slot (LFOTAB
                # first; each literal rewritten to its own start).
                _ltab = ((LFO01 + LFOTAB) if LFO01_MARK in src else LFOTAB) \
                    if _lfo else []
                if _lfo or _ptab:
                    _tab = _ltab + _ptab
                    _at = _xa[0] if _xa is not None else _c
                    if _xa is None and _c + len(_tab) > _end:
                        continue
                    if _lfo:
                        _s2 = _s2.replace("$facade", f"${_at:x}")
                    if _ptab:
                        _s2 = _s2.replace(PTABLE_MARK, f"${_at + len(_ltab):x}")
                    if _xa is not None:
                        _s2, _xt_sites[name] = _p2x(_s2, name)
                    else:
                        _c += len(_tab)
                _w, _ia, _pa = assemble(_s2, _c)
                _last = (_c, len(_w))
                if _c + len(_w) <= _end:
                    _fit = (_r, _tab, _s2, _c, _w, _ia, _pa)
                    break
            if _fit is None:
                if len(runs) < 2 and _last is not None:
                    # ⚠️ WORDING FROZEN: the build report is API (refhash
                    # hashes the failure text of the overrun cases too).
                    sys.exit(f"payload {tag}: {name} overruns the region "
                             f"({_last[0] + _last[1] - base_a} > {budget} "
                             f"words)")
                _big = max((r["base"] + r["words"] - r["cursor"]
                            for r in runs), default=0)
                _tot = sum(r["base"] + r["words"] - r["cursor"] for r in runs)
                sys.exit(f"payload {tag}: {name} does not fit any harvested "
                         f"run -- {_tot} words are free across {len(runs)} "
                         f"separate runs but the largest single opening has "
                         f"only {_big}; harvest an effect BETWEEN two runs to "
                         f"join them into one")
            _r, tab, src, cursor, words, init_a, proc_a = _fit
            if tab is not None and _xa is not None:
                if len(tab) != _xa[1]:
                    sys.exit(f"payload {tag}: {name}'s table is {len(tab)} "
                             f"words, its X slot {_xa[1]}")
                place_x(tab, _xa[0])
                _both = _lfo and bool(_ptab)
                print(f"  {'LFOTAB+PTABLE' if _both else 'LFOTAB' if _lfo else 'PTABLE':13} "
                      f"X:0x{_xa[0]:05x}..0x{_xa[0] + len(tab):05x} "
                      f"({len(tab):4d} words)  "
                      + (f"rolled LFO lines {'0-7' if LFO01_MARK in src else '2-7'}"
                         if _lfo else "")
                      + (" + " if _both else "")
                      + (f"{name}'s table" if _ptab else "")
                      + f"  in the stock curve bank, {_xt_sites[name]} p:( "
                        f"reads -> x:(")
            elif tab is not None:
                place(tab, _r["cursor"])
                _both = _lfo and bool(_ptab)
                if _lfo:
                    print(f"  {'LFOTAB+PTABLE' if _both else 'LFOTAB':13} "
                          f"P:0x{_r['cursor']:05x}.."
                          f"0x{_r['cursor'] + len(tab):05x} "
                          f"({len(tab):4d} words)  rolled LFO lines "
                          f"{'0-7' if LFO01_MARK in src else '2-7'}"
                          + (f" + {name}'s table" if _both else ""))
                else:
                    print(f"  PTABLE        P:0x{_r['cursor']:05x}.."
                          f"0x{_r['cursor'] + len(tab):05x} "
                          f"({len(tab):4d} words)  {name}'s table")
            place(words, cursor)
            _r["cursor"] = cursor + len(words)
            wrw_p(pp["xtab"] + NEW_IDS[name] * 3, init_a)
            wrw_p(pp["xtab"] + (32 + NEW_IDS[name]) * 3, proc_a)
            if name == REMIX.fallback:
                wrw_p(pp["xtab"] + NONE_ID * 3, init_a)          # id 0 alias,
                wrw_p(pp["xtab"] + (32 + NONE_ID) * 3, proc_a)   # fresh = send
                fb_init, fb_proc = init_a, proc_a
            extra = (f"  Y base 0x{0x38000 if DEV else pp['ybase']:x}"
                     + ("  (shipping payload-B address, see plan above)"
                        if DEV and pp['ybase'] != 0x38000 else "")
                     if name == "DELAY SERVER" else "")
            print(f"  {name:13} P:0x{cursor:05x}..0x{cursor + len(words):05x} "
                  f"({len(words):4} words)  id 0x{NEW_IDS[name]:02x}{extra}")
            cursor += len(words)

        for _m in _omitted:
            # Same fail-safe on the DSP side: the id resolves to the fallback's
            # entry points rather than to whatever occupies its dispatch slot.
            wrw_p(pp["xtab"] + _m.menu.fx2_id * 3, fb_init)
            wrw_p(pp["xtab"] + (32 + _m.menu.fx2_id) * 3, fb_proc)

        if absent is not None:
            # The absent engine's id must still dispatch to something on this
            # core -- the chooser list is shared across all eight tracks and
            # nothing stops it being selected here. Point it at the SEND client
            # already placed above: same fail-safe id 0 uses, and a track that
            # selects the "wrong" server becomes a send to the right one.
            wrw_p(pp["xtab"] + NEW_IDS[absent] * 3, fb_init)
            wrw_p(pp["xtab"] + (32 + NEW_IDS[absent]) * 3, fb_proc)
            print(f"  {absent:13} NOT PLACED on this core -- id "
                  f"0x{NEW_IDS[absent]:02x} aliased to SEND P:0x{fb_init:05x} "
                  f"(selecting it here makes the track a send, not silence)")

        if probe == "silence":
            words, init_a, proc_a = assemble(
                pathlib.Path("dsp/silence_stub.asm").read_text(), cursor)
            if cursor + len(words) > _end_of_run(cursor):
                sys.exit("silence stub does not fit the region's free tail")
            place(words, cursor)
            wrw_p(pp["xtab"] + STOCK_DELAY_ID * 3, init_a)
            wrw_p(pp["xtab"] + (32 + STOCK_DELAY_ID) * 3, proc_a)
            print(f"  {'SILENCE STUB':13} P:0x{cursor:05x}..0x{cursor + len(words):05x} "
                  f"({len(words):4} words)  id 0x{STOCK_DELAY_ID:02x} "
                  f"*** DELAY now writes silence, NOT passthrough ***")
            cursor += len(words)
        elif probe == "stock":
            # THE CONTROL. DELAY is back in the menu but its dispatch is left
            # exactly as stock -- the passthrough at P:0x007c8. This is the
            # build that had to come FIRST and did not: without it, "the delay
            # went silent" cannot be told apart from "the delay never worked
            # under our firmware in the first place" (its VOL/SEND could simply
            # be 0, or selecting it from our replaced chooser could skip setup).
            print(f"  {'DELAY':13} dispatch left STOCK (passthrough) "
                  f"id 0x{STOCK_DELAY_ID:02x}  *** CONTROL BUILD ***")
        elif probe == "send":
            # No new code: point id 0x08 at the SEND client already placed
            # above. It passes the audio through and only taps it, so a track
            # with FX2 = DELAY stays audible.
            #
            # CAVEAT for reading the result: SEND reads its two send levels
            # from p0/p1, and on this id those are DELAY's OWN knobs (TIME and
            # its neighbour), not send levels. So the send AMOUNT is whatever
            # those happen to be -- uncontrolled. The question this build
            # answers is only "does the delay survive our code in its slot",
            # not "is the send level right".
            wrw_p(pp["xtab"] + STOCK_DELAY_ID * 3, fb_init)
            wrw_p(pp["xtab"] + (32 + STOCK_DELAY_ID) * 3, fb_proc)
            print(f"  {'SEND @ 0x08':13} P:0x{fb_init:05x} "
                  f"(reuses the SEND client)  id 0x{STOCK_DELAY_ID:02x} "
                  f"*** DELAY's slot now runs SEND; audio passes through ***")
        if len(runs) < 2:
            # ⚠️ WORDING FROZEN for a single run: the build report is API
            # (refhash hashes it verbatim, verify_* parse it).
            print(f"  region P:0x{base_a:05x}..0x{base_a + budget:05x} "
                  f"({budget} words)  used {cursor - base_a}  "
                  f"FREE {base_a + budget - cursor}")
        else:
            # ⚠️ THE SUMMARY KEEPS THE SINGLE-RUN SHAPE `(N words) used U
            # FREE F` -- state.measure() reads the budget off it, and there
            # must be exactly ONE such line per payload. The per-run lines
            # below are deliberately spelled so they do NOT match it.
            _used = sum(r["cursor"] - r["base"] for r in runs)
            print(f"  region {len(runs)} runs ({budget} words)  "
                  f"used {_used}  FREE {budget - _used}")
            for _i, _r in enumerate(runs, 1):
                _e = _r["base"] + _r["words"]
                _in = "/".join(k for k in _harvest
                               if _r["base"] <= _sp[k][0] < _e)
                print(f"    run {_i} P:0x{_r['base']:05x}..0x{_e:05x} "
                      f"{_r['words']:5d} w  used "
                      f"{_r['cursor'] - _r['base']:5d}  spare "
                      f"{_e - _r['cursor']:5d}  {_in}")

        # ---- donor ids -> the null stub, BUT ONLY WHERE OUR CODE LANDED --
        _hv = {k: _sp[k] for k in _harvest}
        # ⚠️ THE REPORT NAMES ARE ONE WORD, and that is load-bearing rather
        # than cosmetic: state.measure() reads `KEPT STOCK: (\S+)` and splits
        # on "/", so a name with a space in it truncates the whole list at
        # the first one. The old code took the lowercase donor keys and
        # upper-cased them ("plate" -> "PLATE"); the module keys are "PLATE
        # REV", so the first word is what keeps every existing report line
        # byte-identical (refhash) and every existing parser working.
        _short = {k: k.split()[0].upper() for k in _hv}
        # ⚠️ PER RUN. One global cursor was right only while the region was
        # one run; with two, an effect in a run we never opened is untouched
        # however far the other run was packed.
        _replaced = {_MODS[n].menu.replaces: n for n in CLONED_ORDER
                     if _MODS[n].menu.replaces}
        # (kept = harvested, unreached, and NOT replaced: a replaced effect's
        # code may be untouched but its dispatch is ours, so it is not
        # stock any more and must not be reported as kept.)
        kept = [d for d, (a, _n) in _hv.items()
                if not _written(a) and d not in _replaced]
        # A harvested reader of the curve bank whose code the stream never
        # reached would keep its stock dispatch and read our tables as its
        # curves. Its code is untouched, its data is not: null it, and say so.
        for d in [d for d in kept if _xt_layout and d in _xt_readers.get(tag, ())]:
            kept.remove(d)
            print(f"  {d}: code untouched, but the stock curve bank "
                  f"X:0x{_xt_base:05x} it reads now carries our tables -- "
                  f"dispatch nulled")
        for donor, (a, _n) in _hv.items():
            if donor in kept or donor in _replaced:
                continue
            eid = _MODS[donor].menu.fx2_id
            wrw_p(pp["xtab"] + eid * 3, pp["nul_i"])
            wrw_p(pp["xtab"] + (32 + eid) * 3, pp["nul_p"])
        if not kept:
            # ⚠️ WORDING FROZEN for the default harvest: the build report is
            # API (refhash hashes it, and verify_* parse it). Every shipping
            # layout packs past all three, so this is the line every existing
            # case still prints.
            # ⚠️ WORDING FROZEN for the default: the report is API (refhash
            # hashes it verbatim). DEV's CHORUS is named by the prefix, so it
            # must not also appear in the list behind it.
            _rest = [k for k in _harvest if not (_dev_chorus and k == "CHORUS")]
            _dflt = list(_rest) == list(DEFAULT_HARVEST)
            _all = ("CHORUS/" if _dev_chorus else "") + (
                "PLATE/SPRING/DARK REV" if _dflt
                else "/".join(_short[k] for k in _rest))
            print(f"  donor ids ({_all}) "
                  f"-> null stub P:0x{pp['nul_i']:05x}/0x{pp['nul_p']:05x} -- any "
                  f"path resolving a donor id gets silence, not our code "
                  f"(defensive: the FX1 menu never listed the reverbs)")
        else:
            _gone = [_short[d] for d in _hv if d not in kept]
            print(f"  donor ids taken ({'/'.join(_gone) or 'none'}) "
                  f"-> null stub P:0x{pp['nul_i']:05x}/0x{pp['nul_p']:05x}; "
                  f"KEPT STOCK: {'/'.join(_short[k] for k in kept)} -- this selection "
                  + (f"stops at P:0x{cursor:05x} and never touched their code"
                     if len(runs) < 2 else
                     f"never reached into their runs"))
        if any(d in _replaced for d in _hv):
            # Its own clause, emitted only when a replacement is selected,
            # so every existing report line stays byte-identical.
            print("  REPLACED: " + ", ".join(
                f"{_short[d]}->{_replaced[d]}" for d in _hv if d in _replaced)
                + " -- dispatch is the replacement's, not the null stub")
        # A chooser row for a reverb whose words we just overwrote would
        # point at a live descriptor over dead code: the panel would draw
        # PLATE REV and the DSP would run ours. Refuse, loudly.
        # ⚠️ NAME EVERY OFFENDER, NOT THE FIRST. Exiting on the first one
        # made the operator iterate: remove PLATE, rebuild, fail on SPRING,
        # remove that, rebuild, fail on DARK. The build knows all three the
        # moment it knows the cursor, and the remixer's one-key fix can
        # only remove what the build named.
        _over = [(_name, _hv[_name][0] - base_a) for _name in STOCK_ROWS
                 if _name in _hv and _name not in kept]
        if _over:
            _list = ", ".join(f"{n} (starts at {a})" for n, a in _over)
            sys.exit(f"payload {tag}: {_list} "
                     f"{'are' if len(_over) > 1 else 'is'} listed in the "
                     f"chooser but this selection places code over "
                     f"{'them' if len(_over) > 1 else 'it'} (region used "
                     f"{cursor - base_a} words) -- remove the row"
                     f"{'s' if len(_over) > 1 else ''} or free the words")
        if DEV:
            print(f"  *** CHORUS (id 0x12) TAKEN as a fourth donor -- FX1 loses "
                  f"its chorus. DEV builds are never flashed. ***")
        else:
            print(f"  CHORUS (id 0x12) UNTOUCHED -- code and dispatch are stock, "
                  f"FX1 gets the real chorus back")

    # A MODE-forced build ignores the real page-2 slot, so it must never end up
    # wrapped and flashed -- it would look like a MODE knob that does nothing.
    # Give it its own path rather than overwriting the flashable image.
    out = OUT
    if mode_env is not None:
        out = pathlib.Path("out/mainos_bus_mode%d.bin" % int(mode_env))
    if delayprobe:
        out = pathlib.Path(f"out/mainos_bus_delayprobe_{probe}.bin")
    if DEV:
        # Never OUT. A DEV image has CHORUS overwritten and is for dsp_host
        # only; letting it land on the flashable path is the one way this
        # hatch could do harm.
        out = pathlib.Path("out/mainos_bus_dev.bin")
    # A loader-appended runtime grows the image here, last of all: every
    # pass above worked on the stock-length image. The combined OS must
    # match the identity the recipe pins for exactly this (single-runtime)
    # composition; a remix that combines the runtime with other modules
    # cannot match it, and says so instead of failing.
    _grown = ""
    for _aname, _append in _appends:
        img.extend(_append)
        _grown += f" (+{len(_append):,} B {_aname} appended)"
    out.write_bytes(bytes(img))
    out.with_suffix(".remix").write_text(
        f"{REMIX.name} {hashlib.sha256(bytes(img)).hexdigest()}\n")
    d = sum(1 for x, y in zip(IMG.read_bytes(), img) if x != y)
    note = _grown
    if mode_env is not None:
        note = "   *** DIAGNOSTIC, MODE FORCED -- DO NOT FLASH ***"
    elif probe == "silence":
        note = ("   *** DIAGNOSTIC DELAY PROBE -- flashable, but stock DELAY "
                "writes SILENCE. Not a product build. ***")
    elif probe == "send":
        note = ("   *** DIAGNOSTIC DELAY PROBE -- flashable; stock DELAY's "
                "slot runs SEND. Not a product build. ***")
    elif probe == "stock":
        note = ("   *** CONTROL BUILD -- DELAY in the menu, dispatch STOCK. "
                "Flash this FIRST. Not a product build. ***")
    elif DEV:
        note = ("   *** DEV BUILD -- local render only, DO NOT FLASH "
                "(CHORUS is overwritten). ***")
    print(f"\n{out}: {len(img):,} bytes, {d} changed" + note)

    if DEV:
        # Dump payload A straight away. The whole point of the hatch is that
        # send_probe.py / render_reverb.py can drive the delay, and both take a
        # .mem -- making the developer remember a separate dsp_modmap
        # incantation after every build is how the hatch stops being used.
        import dsp_modmap
        mem = pathlib.Path("out/dsp/mem_dev_A.mem")
        mem.parent.mkdir(parents=True, exist_ok=True)
        dsp_modmap.dumpmem(bytes(img), ["A", str(mem)])
        if dev_delay is not None:
            # The delay's code is not IN the payload (no record slack; see
            # DEV_DELAY_P) -- append its module record to the dump, the same
            # [u8 space][u32 addr][u32 count][count*u32] format dumpmem
            # writes. Absent under DEV+SPEC, where payload A legitimately
            # carries no delay and dev_delay stays None.
            import struct
            term = struct.pack("<BII", 0xff, 0, 0)
            blob = mem.read_bytes()
            if not blob.endswith(term):
                sys.exit("mem dump does not end with the 0xff terminator "
                         "record -- dumpmem's format changed under us")
            with open(mem, "wb") as fh:
                fh.write(blob[:-len(term)])
                fh.write(struct.pack("<BII", 0, DEV_DELAY_P, len(dev_delay)))
                for w in dev_delay:
                    fh.write(struct.pack("<I", w))
                fh.write(term)
            print(f"  + DELAY SERVER record appended to the dump: "
                  f"P:0x{DEV_DELAY_P:05x} ({len(dev_delay)} words)")
        if "DELAY SERVER" in NEW_IDS:
            print(f"\nDEV hatch ready. All three servers are real in payload A:\n"
                  f"  python3 tools/harness/send_probe.py --mem {mem}\n"
                  f"  python3 tools/harness/render_reverb.py loop.wav --mem {mem}\n"
                  f"DELAY SERVER is id 0x{NEW_IDS['DELAY SERVER']:02x}; "
                  f"send_probe's entry_points() resolves it from the dump.")
        else:
            print(f"\nDEV dump ready ({REMIX.name} carries no DELAY SERVER):\n"
                  f"  drive dsp_host against {mem} directly, or through "
                  f"send_probe for the modules it knows.")


if __name__ == "__main__":
    main()
