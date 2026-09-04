#!/usr/bin/env python3
"""
BUS.md tasks 11 + 13: the full three-entry FX2 menu, both payloads, with the
three servers' own DSP code actually placed and dispatched.

    python3 tools/build_bus.py

Builds on tools/build_menu.py's already-verified ColdFire menu tables (same
constants, reproduced here rather than imported so this stays a single
self-contained build script like every other tools/build_*.py in this
project) and adds what task 11 explicitly deferred: placing
the selected modules' assembled DSP code (modules/<name>/*.asm)
in real P memory, for BOTH payloads, and repointing X:0x215/X:0x235 so the
three new ids (0x01 DELAY SERVER, 0x02 REVERB SERVER, 0x03 SEND) actually run
them instead of whatever the byte-donor used to be.

DSP-side donor choice (P-code space only -- unrelated to the ColdFire
descriptor-clone donors task 11 already picked).

**v98: CHORUS IS NO LONGER A DONOR AND IS FULLY RESTORED.** All three servers
now pack into the PLATE + SPRING + DARK region alone -- 2724 contiguous words
against the code (2,692 words as of 11 Aug 2026 -- the build report is the live number), so everything fits in space that was already spent on
replacing the three stock reverbs. SEND used to sit in CHORUS's 329-word
module, which cost FX1 its chorus to house 166 words; that was collateral,
not a considered trade. The three reverbs are the trade: we replaced them
with a better one.

Layout, in address order from PLATE's base:

  SEND           166 words
  REVERB SERVER 1999
  DELAY SERVER   507   <- last DELIBERATELY: BusDelay is the algorithm still
                          to be designed, so it gets the trailing free words
                          (see the build report for the live count) and is
                          adjacent to COMPRESSOR's module if
                          the region is ever extended rightward. Growing it
                          then moves nothing else.

The three records are contiguous in LOADED P memory but separated by headers
in the file, so a stream spanning them is split per record on the way in --
the technique tools/build_reverb.py proved on hardware for SPRING+DARK, just
generalised to three. Contiguity is asserted at build time rather than
assumed.

**Donor ids get repointed to the SAME null stub tools/build_dspprobe.py
already used and proved silent on hardware (P:0x007c8/0x007c9 payload A,
P:0x00588/0x00589 payload B -- stock DELAY's own dispatch, already a no-op
by design), not to the new server code.** This is a deliberate departure
from tools/build_reverb.py, which repoints SPRING/DARK's own ids at the new
reverb engine -- fine there because nothing else in this project offers
those ids any more once this build's three-entry menu replaces the whole FX2
chooser. The FX1 menu never listed the reverbs or DELAY -- they are FX2-only
(Sam, corrected repeatedly; do not write "FX1 selecting PLATE..." again) --
so no selector should ever reach the donor ids. The null stub is defensive
insurance for exactly that assumption: if ANY dispatch path did resolve a
donor id (a saved part, an id poked by something we haven't mapped), pointing
it at our servers would run the SAME hardcoded-Y-base engine a second,
uncontrolled time on whatever track holds it -- the multi-instance collision
the hardcoded-base design assumes can't happen (BUS.md's Memory section).
Silencing them makes any such path harmless silence, the same
already-hardware-proven behaviour stock DELAY has always had.

CHORUS (id 0x12) is deliberately NOT in that list any more. Its code is
untouched and its dispatch entries keep the values the stock image ships, so
FX1 selecting CHORUS gets the real chorus back. Nothing has to be restored
to make that work -- every build starts from a pristine
out/raw/section_3_MAIN_OS.bin, so the stock code was never destroyed, only
overwritten on the way out.

The shared-window Y base is the one place this script differs per payload in
the ASSEMBLED CODE itself (not just where it's placed). Payload A's half of
the 64K shared window is 0x30000-0x37FFF and payload B's is 0x38000-0x3FFFF,
so `_sub` (below) rewrites the literal `$30000` to PP[tag]["ybase"] in the
source text before assembling.

⚠️ It is a BLANKET string replace over the whole source, not a single
targeted occurrence, and under XBUS it is applied to SEND and REVERB SERVER
as well as DELAY SERVER. Two consequences:

  - Any of those files that wants a shared-window address which must NOT
    move to the other half on payload B cannot spell it `$30000`. Use an
    offset from a register-held base, or a literal that is not `$30000`.
  - It rewrites comment text too. Harmless, but do not read a disassembly
    comment as evidence of what was substituted.

✅ Verified in the emitted image 9 Aug 2026 rather than by reading this
code: payload B's placed P words carry 0x38000 five times and 0x30000 zero
times. The old docstring here claimed "exactly one occurrence", which was
never true for the XBUS path.
"""
import dataclasses, os, pathlib, re, subprocess, sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
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

# ---- ColdFire menu tables (task 11, tools/build_menu.py, reproduced here) --
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
# what tools/build_fx1.py's experiment needed, because it ADDS entries --
# the list ends at 0x400d608c and the FX2 list starts at 0x400d6090.)
FX1_IDS = 0x400d5f58        # id-indexed, 32 slots; NONE for an FX2-only effect
FX1_LIST = 0x400d6060       # the chooser list FX1 scrolls, NUL-terminated
FX1_NONE = 0x400d4618       # the descriptor every unused id points at
# FX1's OWN cursor-position table, the exact analogue of ID2POS below, found
# 3 Sep 2026 by reading the four tables in address order: FX1_LIST (11
# entries) at 0x400d6060, FX2_LIST (15) at 0x400d6090, then two 32-entry
# id->row tables back to back. It is FX1's because its FX2-only ids are all
# zero -- DELAY (0x08) and the three reverbs (0x14-0x16) -- where ID2POS
# gives them rows 0x0b and 0x0c-0x0e. tools/build_fx1.py's experiment never
# wrote it, which is a real gap: without it a project that has one of our
# effects stored on FX1 opens the chooser with the cursor on row 0.
FX1_ID2POS = 0x400d60d0
# The `lea.l FX1_LIST,aN` sites, the FX1 counterparts of LIST_REFS. Measured
# by tools/build_fx1.py, which repoints exactly these three.
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
# The other unclaimed zero run docs/MAINMENU.md section 5 names -- 2,064 bytes
# at 0x400d24d0. The menu shortcut cave is pinned at its start; label
# formatters overflow into it when the clone window is full (the character
# station's BUS-mode renames tipped the rig over by 56 bytes, 3 Sep 2026).
OVERFLOW_RUN = 0x400d24d0
OVERFLOW_RUN_END = 0x400d2ce0
CLONE_BASE = 0x400d6b20
CLONE_STRIDE = 0x1a0
# NEW_LIST holds SEVEN rows plus its terminator before it runs into the
# first clone. A remix that keeps stock effects in the chooser (2 Sep 2026)
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

# DESC_DONORS, NEW_IDS, RENAMES, ABBR, FULLNAME, DEFAULTS, ACTIVE_PARAMS,
# PAGE2_COUNTS and STEPPED_SLOTS are no longer written here. Each module
# declares them in modules/<name>/manifest.py and they are derived below,
# after BUILD_TAG. See tools/remix/schema.py for what a manifest may say.

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

# BUILD TAG, stamped into the effect's displayed name. Three rounds were lost
# to not being able to tell WHICH build was running on the unit: a symptom
# ("knobs unchanged") is ambiguous between "the change did not work" and "the
# flash did not apply", and those need opposite responses. The name field is
# 13 bytes and always on screen, so it costs nothing to carry the answer.
# BUMP THIS EVERY TIME A .bin IS WRAPPED FOR FLASHING.
# 31 -> 32, 10 Aug 2026: 31 covered BOTH the working 7 Aug flashes and the
# dead R13 flash, which cost a session of "which build is this" -- the exact
# ambiguity this tag exists to prevent. 32 -> 33: the post-marker product
# build (mapping documented, real names under SPEC). 33 -> 34: LFO roll
# + wet makeup, the R15 flash.
# 37 -> 38, 13 Aug 2026: 35-37 were stamped for reverb rounds R16/R17/R18 and
# NONE of them ever reached a card, so 37's contents kept growing under a tag
# that had already been "assigned" -- by the time it was wrapped it also
# carried the whole of BusDelay v2 (five modes, GRAIN through 5g). A tag that
# names two different images is the failure at 31 all over again, so the wrap
# gets a fresh number: 38 == OCTABAMR19 == everything through R18 plus
# BusDelay v2. 35, 36 and 37 were never on hardware and never will be.
# 40 was allocated to the HKB=1 DIAGNOSTIC wrap (OCTABAMR21, 17 Aug) -- an
# image that swaps which payload housekeeps, built as a falsifier and never
# flashed. It is superseded: the race was confirmed for free by moving
# BusDelay between tracks 1 and 4, and the falsifier was weaker than it
# looked anyway (swapping the housekeeper TRANSPOSES the hazard rather than
# removing it). Tag 40 is burned rather than reused, because a tag that names
# two different images is the failure at 31 all over again.
# 41 == OCTABAMR22 == R20 plus the four-buffer cross-core race fix and the
# phantom-client gate. R22 CONFIRMED THE RACE FIX ON HARDWARE (Sam: track 1 is
# clean), and exposed the next defect in the same breath: "the signal is much
# quieter".
# 42 == OCTABAMR23 == R22 plus SEND registering per bus and only when sending.
# ⚠️ THIS ONE IS MUCH LOUDER -- up to +17 dB for a real sender in a sparse
# bank, because idle tracks (which alias to SEND) were each taking a 1/N share.
# Send knobs and track faders set against R22 will be wrong, and BusVerb's
# BIG mode clips at a 0.25-0.5 FS input, so back it off by hand.
# R23 is also the image that FOUND the second cross-core defect: static that
# needed a specific (core-1 track, delay mode) pair, moved when either changed,
# and vanished when track 5 -- core 0's housekeeper -- stopped being a BusVerb.
# 43 == OCTABAMR24 == R23 plus per-core rotation tracking, the fix for it.
# R24 took the artifact from moving across the whole sweep to ONE combination
# in fifteen: T4 sending, delay MODE 1. T4 is the LAST core-1 track and CLEAN
# the cheapest mode, i.e. where core 1 runs furthest ahead of core 0.
# ⚠️ R25 SHIPPED A COLD-BOOT BUG: the tracked rotation was never initialised,
# and a client booting one step ahead is indistinguishable from one legitimately
# reading pre-flip, so it stuck -- and with the clear moved ahead, a stuck
# client writes exactly the buffer being cleared. Metallic on every power cycle,
# cured by re-selecting the effect. Do not flash 44.
# 45 == OCTABAMR26 == R25 plus seeding that value at init. R26 is the image on
# which Sam swept T2/T3/T4 x MODE 1..5 and found ALL MODES GOOD ON ALL TRACKS
# -- the three cross-core defects are closed.
# 46 == OCTABAMR27 == R26 plus the auto-gain law 1/sqrt(N) instead of 1/N.
# 47 == OCTABAMR28 == R27 plus the page-2 companion-field fix: the companion is
# BITS 8-15, not the low byte. Wakes five knobs that have NEVER worked on
# hardware -- delay WOW/PTCH/FRZE, reverb WIDTH and ->DEL. All five CONFIRMED
# on the unit, 17 Aug.
# 48 == OCTABAMR29 == R28 plus BusVerb v4: the RETURN conversion. The reverb
# now mirrors the delay -- wet-only output, MIX -> IN (default 0), host counted
# as a client only while sending. ⚠️ A reverb track with audio and IN=0 is
# SILENT by design; reverb level rides the track fader now. Ear-passed by Sam
# on hardware, 17 Aug ("sounds pretty good").
# 49 == OCTABAMR30 == R29 plus -VRB: the delay's ->VERB send is a KNOB again
# (p5, default 0, registration follows it). ⚠️ NO WASH out of the box until
# -VRB comes up -- and see docs/FLASHING.md's "first load of an existing
# project" step: old VRBW/MIX values load as -VRB/IN.
# 50 == OCTABAMR31 == R30 minus BusVerb's ->DEL send (the vestige twin of
# VRBD; retired, slot 11 blank). The reverb writes NO bus at all now -- the
# only wet-crossing edge is delay->reverb, under the -VRB knob.
# ⚠️ R30 AND R31 CARRY A BROKEN DELAY IN (the -VRB splice deleted its decode;
# $76 never written). NEITHER WAS FLASHED. Do not flash either; tag 51 fixes.
# ⚠️ R36'S DPTH/RATE/DRV WERE DEAD ON HARDWARE (shared-window Y state at
# 0x360d3-5 -- writes and in-loop reads never meet on silicon; mechanism
# unknown). 56 == OCTABAMR37 == R36 with that state moved to core-private Y
# 0901-0903h (the old bus range). Flash R37; discard R36.
# 55 == OCTABAMR36 == R35 plus DRIVE (p10 = DRV outside GRAIN; loop-stable
# blend toward the 2x curve; default 0 = exact bypass; GRAIN keeps SPRA).
# 54 == OCTABAMR35 == R34 plus the TAPE retirement: DPTH (was WOW) + RATE are
# global modulation across every delay mode; TAPE's position aliases CLEAN
# (bit-identically, knobs matched); saturation keys on DPTH>0.
# 53 == OCTABAMR34 == R33 with BIG's trim softened -6 -> -3 (ear: "a bit of a
# volume drop"; the +8.4 measurement was part-state-inflated).
# 52 == OCTABAMR33 == R32 plus voicing round 1 from the hardware captures:
# BIG wet -6 dB, GRAIN +6 dB, and RATE (MOD speed select, reverb p11).
# 51 == OCTABAMR32 == R31 plus the IN fix and the IN/-VRB slot swap (IN
# bottom-right on BOTH effects: delay IN p4->p5, -VRB p5->p4).
# ⚠️ LOUDER AGAIN with several senders: up to +9 dB at eight tracks of real
# (uncorrelated) material. Correlated content now UNDER-corrects and can clip.
# 44 == OCTABAMR25 == R24 plus clearing the buffer written NEXT block, which
# closes clear-vs-WRITE -- the one hazard of the family still open, and the
# one that pairing is exactly where you would expect to bite.
# ⚠️ The artifact RELOCATES, so testing this needs a SWEEP of track/mode
# combinations. One clean configuration is what let it survive R23.
# 57 == R38 == DIAGNOSTIC (hardwired mod) -- discard. Its result: constants
# changed nothing, which is what exposed that the DEPTH LAW was the "defect".
# 58 == OCTABAMR39 == R37 content plus the x8 depth relaw, per-sample lag
# clamp, 4x drive knee, and the modtap roll. Flash R39; discard R36-R38.
# 59 == OCTABAMR40 == R39 plus the reverb MOD relaw (ROOM x4 / PLATE x2.9 /
# BIG x2) and DRIVE's d relocated to r7+$83 (Y-in-callee measured dead on hw).
# 60 == OCTABAMR41 == R40 plus the drive OUTPUT makeup (wet x (1 + d/2)).
# 66 == OCTABAMR47 == R46 plus the DELAY's IN-keyed wet makeup (23 Aug 2026,
# "delay wet is quiet"): out += 2*IN*wet -- additive from the PRE-drive wet,
# so IN=0 is bit-identical INCLUDING under hot drive (measured: +9.5 dB at
# IN=127, +6.0 at 64, 0.0 at 0). Found and fixed on the way: send_probe's
# --din drove SLOT 4 (-VRB) since the 18 Aug IN/-VRB swap -- the makeup
# measured +0.0 dB until the harness was fixed; verify_delay's SLOT map had
# the same stale 4. verify_bus was correct all along (its DS IN case was the
# real safety net). Fixture dmix 127 -> 40: at 127 the x3 makeup railed
# every D layout and a clipped fixture is a blind fixture.
# 65 == OCTABAMR46 also carries THE BURN-SWEEP UNBLOCK (23 Aug, all
# BIT-IDENTICAL -- placement, not behavior; verified by image-vs-image render
# hashes across every mode/interval/gate state):
#   * phead roll: the PITCH head body (62 words) appeared FOUR times in the
#     delay; rolled -> payload B FREE 220.
#   * md_done hoist: all three reverb modes stored the same five constants
#     (diffuser taps + RATE scale); hoisted past the fork. rp_tail: ROOM and
#     PLATE shared three more ($20/$3f/$73). g_off: one $400000 load now
#     serves GCNT and GHOLD. Payload A FREE 74.
#   * verify_burn: GREEN for the first time -- the burn probe builds fit and
#     all four checks pass; the alias-probe combo alone still needs ~42 words
#     and now SKIPs granularly instead of masking the sweep.
# ⚠️ cycle_count now OVERPRICES the delay by ~264 (it mis-attributes the
# rolled phead calls); actual cycles unchanged. The BURN=1 hardware sweep is
# the real measurement and is READY: TPROBE-style one flash, sweep p3.
# 65 == OCTABAMR46 == R45 plus the GATE threshold fix (23 Aug 2026): the
# trigger bar drops 0.094 -> 0.004 FS (-20.5 -> -48 dBFS). MEASURED defect:
# at GATE>0, material under the old bar rendered the wet DIGITALLY SILENT
# until something crossed -20.5 (a -24 dBFS melody at GATE=12 = pure
# silence); the fixed threshold keeps quiet material alive and the clap
# chop intact (hold unchanged -- the hold is the musical part). ⚠️ Whether
# this silent-wet mode is the R44/R45 field incident is UNRESOLVED: it
# matches every symptom (wet dead / dry passing / sends useless / delay
# fine / re-select cures via GATE=0 defaults), but Sam suspects a
# sequencer/track interaction -- ColdFire-side, investigation PAUSED at
# Sam's request. The incident stays open either way.
# 64 == OCTABAMR45 == R44 plus Sam's R44 hardware feedback (23 Aug 2026):
# wet makeup steepened to x(1 + 2*IN) -- +9.5 dB at full IN ("could still be
# mixed louder"; IN=0 still EXACTLY x1). Measured: percussive wet now 11 dB
# under dry at full IN (was 20 pre-makeup), no clipping; hot SUSTAINED
# material clips the store above IN~90 -- knob territory, documented, not
# guarded (dry ducking was explicitly rejected: "don't back down that
# [crossfade] road"). Shifter-input HP corner 570 -> ~280 Hz, ear-picked
# from a 4-corner wet-only ladder ("second one is good"). ⚠️ OPEN INCIDENT,
# now TWICE on hardware (R44/R45 era): the reverb's WET dies -- dry keeps
# passing, sends into it do nothing -- until the effect is re-selected on
# the track. Sequencer unaffected. NOT double-select (Sam confirmed), NOT
# reproducibly triggered (once correlated with turning SIZE up). Model
# analysis: the only state that PERSISTS like this is "core 0's bus
# housekeeping stopped" -- the role locks then hold a stale owner, every
# instance takes the duplicate exit (rts = dry passthrough) and nobody
# consumes the ACC. The election should self-heal that, so hardware is
# doing something the single-core emulator cannot see. NEXT OCCURRENCE'S
# ONE DIAGNOSTIC: check whether tracks 1-4 sends -> BusDelay ALSO died.
# The same housekeeper serves both buses: delay dead too = housekeeping
# died (mechanism located); delay alive = reverb-instance-local. (The
# duplicate-instance case itself is verified INERT in-model: an RRS layout
# renders stable for 8 s, second instance = clean dry passthrough.)
# 63 == OCTABAMR44 == R43 plus the reverb v7 trio (23 Aug 2026, Sam's picks):
# (1) IN-KEYED WET MAKEUP -- wet x (1 + IN), +6 dB at full IN, EXACTLY x1 at
# IN=0 (the R29 return level is preserved to the bit; measured x1.99 from
# sample one at IN=127). (2) SHFT replaces WIDTH: slot 9 selects the shimmer
# interval +12/+19/+7/-12 via a fractional read phase (core-private 0905h);
# +12 is BIT-IDENTICAL to the R18 shimmer (hash-gated); width is pinned wide
# (the old default). All four intervals verified spectrally on a tone.
# (3) SHIFTER-INPUT HP (the R18 "airier octave" item, unblocked): one-pole,
# corner ~560 Hz, state at 0906h, on the shimmer feed only -- a VOICING
# CONSTANT awaiting Sam's ear (A/B pair rendered). PAID FOR by the apbody
# roll (the input-diffuser allpass body appeared 4x; payload A FREE 18
# after everything). verify-bus restamped: every reverb-analyzed layout
# changed by exactly the makeup (fixture drives IN=127), every
# delay-analyzed layout bit-identical.
# 62 == OCTABAMR43 == R42 plus the FREEZE seam crossfade (v6, 23 Aug 2026):
# engaging FREEZE used to capture a step between the loop's newest and oldest
# sample and replay it every lap (measured with the new DFRZAT repro hook:
# one ~0.14 FS discontinuity per TIME+64 samples on a pure tone, forever).
# The hold's write now crossfades from the live chain into the tap over
# ~1.5 ms at engage (ramp r in core-private Y, armed while running, decaying
# only while frozen), so the captured loop never contains a step; after the
# fade the write is the tap TO THE BIT, so the hold still neither decays nor
# grows. Running path bit-identical (verify_delay all modes + verify-bus
# 19/19, no restamp). PAID FOR by the smoothw roll -- the 17-instruction
# smoothstepped-triangle window appeared five times in the delay (wow,
# flutter, GRAIN, REVERSE x2); rolled to one subroutine, payload B FREE
# 1 -> 51 net. Also fixed: verify_delay's mode_count undercounted since
# TAPE's retirement, so REVERSE was silently skipped by every run since
# 18 Aug -- both REVERSE cases are live again.
# 61 == OCTABAMR42 == R41 plus v5 dry passthrough on BOTH hosts (23 Aug 2026):
# each server's own track prints its dry at unity under the wet, so IN=0 is an
# exact passthrough instead of silence. Bus arithmetic untouched (IN still
# gates engine feed and client registration); GATE still scales wet only. Net
# ZERO words on payload B (the drive-makeup a/b dance collapsed to `add x0,a`),
# +4 on payload A. With a silent host track the output is bit-identical to R41.
# 78 == OCTABAMR62 == tag-77 content plus R61 and R62 (31 Aug 2026):
# R61 = GRAIN density decode fix (the DENS/DPTH gate compared knob>>1
# against a 3-bit draw, so >=15 was always full density; now knob>>4, the
# full dial) + the density MAKEUP (coeff 1/2 + (7-dens3)/14 into the grain
# gain word; level flat +-1.2 dB across the dial, was -7.1 dB of sag).
# R62 = REVERSE size-table indices 0/1 swapped so the panel default
# (PTCH=1) is the 93 ms musical segment, 46 ms on index 0. CLEAN/PITCH/
# REVERSE proven bit-identical through R61, and R62's swap proven an exact
# exchange. ⚠️ Stored parts with DPTH ~48 in GRAIN come up MID density on
# this tag -- the knob working for the first time; the makeup holds level.
# 79 == OCTABAM79 == the BamSep26 rig + THE RETURNS (3 Sep 2026): three
# stations (FILTER/LO-FI/CHORUS replaced, all bus senders), BusDelay v5,
# the Character station returning both wets on the master (RVRB/DLY in
# SAT=BUS), hosts quiet only while a return is live; label formatters
# overflow into the second zero run. Flash 4, docs/FLASHPLAN.md.
BUILD_TAG = b"79"

# ---- the module tables, derived from modules/*/manifest.py ------------------
# One statement per fact, living in the module that owns it. These dicts keep
# their old shapes because the writers below are unchanged: what moved is
# where the data lives, not what it says.
#
# Ids are 0x06/0x07/0x09 rather than 0x01/0x02/0x03 because the first hardware
# test used the latter and got correct chooser names with dead knobs and
# garbage audio: 0x00-0x03 are the four values stock has always treated as
# bare synonyms for "no effect". 0x06 is the exact id tools/build_dspprobe.py
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
RENAMES = {m.key: ([(i, b"") for i in range(12)] if m.key in HIDDEN else
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
# Value counts. Page 2 is THREE KNOBS AND THREE SELECTS: the knob fields take
# 128, the companion byte fields take a small step count. Setting a companion
# to 128 does not make it continuous -- it stays a select and reads as a
# near-boolean, which is what hardware showed.
PAGE2_COUNTS = {m.key: {i: p.count for i, p in enumerate(m.params)
                        if p.count is not None} for m in _CLONED}
# Membership here also GATES the display-formatter pass below: a module with
# no stepped slot keeps its donor's formatters untouched, which is what SEND
# wants (FILTER's plain-numeric zeros, hardware-confirmed).
STEPPED_SLOTS = {m.key: m.stepped_slots for m in _CLONED if m.stepped_slots}
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


def penable(active):
    lo = hi = 0
    for i in active:
        if i < 8:
            lo |= 1 << (4 * i)
        else:
            hi |= 1 << (4 * (i - 8))
    return lo, hi



                                            # (was -DEL until 18 Aug 2026)


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
        # SPEC/DEV: BOTH servers are real -- the product names, tag-stamped.
        # (The XVerb/NotUsed names below date from the v111 architecture test,
        # where the delay really was a stub. Leaving "NotUsed" on a real
        # BusDelay cost a debugging round on 10 Aug 2026.)
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
# Diagnostic for the R13 hardware deadness (10 Aug 2026): the same payload
# renders in the emulator, so three marks report BY EAR how far proc() gets
# on the unit. Named so the panel cannot be mistaken for a product build.
if os.environ.get("MARKER") == "1":
    FULLNAME["REVERB SERVER"] = b"MrkVerb" + BUILD_TAG
    ABBR["REVERB SERVER"] = b"MRKV"

if os.environ.get("BURN") == "1":
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

    # Round 3's two diagnostic knobs. REPLACE by index rather than append --
    # the BURN block's first draft assigned fresh lists to REVERB SERVER and
    # silently dropped p9/p10's names and p7's MODE default, which
    # verify_menu.py caught. An out-of-range page-2 default is not cosmetic:
    # it is used as an index and stalled the sequencer on hardware once.
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
# XBUS=1 stubs the DELAY SERVER out (see ASM_SRC below), and the specialized
# build that follows it puts BusDelay in payload B ONLY. Both leave the delay
# with NO REAL CODE IN PAYLOAD A -- and tools/dsp_host cannot boot payload B at
# all (REVERB.md). So the moment the architecture lands, the delay loses its
# local render loop and goes back to one hardware flash per iteration, which is
# the expensive path this project exists to avoid.
#
# DEV=1 keeps all three servers real in BOTH payloads, so payload A's .mem dump
# always contains a driveable DELAY SERVER for tools/send_probe.py.
#
# It pays for the space by taking CHORUS's module back as a fourth donor. That
# is 329 words immediately BELOW PLATE and contiguous with it (v98 gave it back
# because the product build no longer needed it). SEND + REVERB + a gated DELAY
# is 2744 words against the 2724 the three reverbs alone provide -- 20 over --
# so without this the hatch simply would not assemble under XBUS=1.
#
# Taking CHORUS costs FX1 its chorus, which is why this build is NEVER FLASHED:
# it writes out/mainos_bus_dev.bin, not out/mainos_bus.bin, and dumps the
# payload A .mem beside it.
DEV = os.environ.get("DEV") == "1"
if DEV:
    _clash = [v for v in ("BURN", "PROBE", "XPROBE", "TPROBE", "DELAYPROBE")
              if os.environ.get(v) == "1"]
    if _clash:
        sys.exit(f"DEV=1 is a local render build and cannot be combined with "
                 f"{'/'.join(_clash)}=1 -- those replace a server with a probe, "
                 f"which is the opposite of what DEV is for")

# ---- SPEC=1: SPECIALIZE THE PAYLOADS ---------------------------------------
# One server per core. Payload A carries SEND + BusVerb; payload B carries
# SEND + BusDelay. Neither carries the other's engine.
#
# TRACK MAPPING -- MEASURED, 10 Aug 2026, and INVERTED from what every doc
# assumed: payload A serves TRACKS 5-8 and payload B serves TRACKS 1-4.
# Established by the MrkVerb32 marker flash: proc-entry marks fired on tracks
# 5-8 only (track 5 = position 0, full engine; 6-8 = duplicate-role rts).
# No pre-SPEC build could have revealed this -- both payloads carried every
# effect, so the mapping was unobservable. Deliberately NOT swapped: the
# reverb belongs downstream of the delay (delay wet -> reverb, series), so
# serving the delay from the low tracks is the wanted topology.
#
# WHY IT IS FREE. build_bus.py has always assembled and placed each payload
# independently -- its own `for tag, va, ln in PAYLOADS` pass, its own region,
# its own placement -- and the 2,724-word donor region is PER CORE. Both
# payloads carrying all three servers was never a requirement, only a habit.
# Dropping the engine each core does not run costs nothing and returns the
# region that engine occupied.
#
# IT ONLY MEANS ANYTHING WITH XBUS=1. The bus accumulators live at Y:0x900 in
# a plain build, which is CORE-PRIVATE low Y: one core's sends would write
# their own private copy, which the other core's server cannot see.
# Specializing without relocating the bus into the shared window does not
# build the target architecture, it builds "each half of the tracks reaches
# one effect and cannot send to the other" -- strictly worse than today, and
# it would look like it worked. So require the flag rather than silently
# producing that.
#
# THE ABSENT SERVER'S ID IS ALIASED TO SEND, deliberately (XBUS.md risk 3).
# The FX2 chooser is one ColdFire list shared by all eight tracks, so nothing
# stops a user selecting BusVerb on track 6. Its id must dispatch to
# SOMETHING on payload B; left alone it would run whatever code now occupies
# that address. Aliasing to SEND is the same fail-safe mechanism id 0 already
# uses, and it degrades in the useful direction: the track feeds the bus.
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
    _clash = [v for v in ("BURN", "PROBE", "XPROBE", "TPROBE", "DELAYPROBE")
              if os.environ.get(v) == "1"]
    if _clash:
        sys.exit(f"SPEC=1 cannot be combined with {'/'.join(_clash)}=1 -- "
                 f"those replace a server with a probe")

# ---- DSP code placement (task 13) ------------------------------------------
           # DLSRC= swaps the delay engine for an alternate source file --
           # the same mechanism as RVSRC below, for the same reason: the
           # BusDelay v2 refactor gate (tools/verify_delay.py) builds and
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
           # BURN is NOT a separate source any more -- see BURN_INJECT below.
           #
           # RVSRC= swaps the reverb engine for an alternate source file. It
           # exists so two engines can be built and rendered in ONE script and
           # compared byte-for-byte (tools/verify_roll.py) -- the refactor gate
           # PLAN.md sets for rolling the tank. Everything else about the build
           # is unchanged, which is the point: the only difference between the
           # two renders must be the engine source.
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
# the donor region (12 Aug 2026, v2 stage 2 opener). The hatch region capped
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

# Ids whose algorithm we overwrite, and which must therefore be silenced on
# FX1. CHORUS (0x12) was here until v98 and is deliberately gone: we no longer
# take its code, so its stock dispatch entries stand and FX1 gets it back.
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
    # NFRZAT=n engages Nimbus's FREEZE after n post-warm-up BLOCKS instead of
    # from sample 0. Without it the frozen cloud cannot be heard locally at
    # all: a static FRZE=1 holds the silence the warm-up just cleared, so the
    # only thing a render proves is that the write head stopped. Exactly the
    # gap DFRZAT was built to close for BusDelay, and the same shape of fix.
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
    # DELAYPROBE=silence  id 0x08 -> a stub that writes zeros (round 1)
    # DELAYPROBE=send     id 0x08 -> the SEND client, which passes audio and
    #                     only taps it, so the track stays alive. Round 1 came
    #                     back "silent", which mostly proves the insert is in
    #                     the audio path -- it cannot tell us where the delay
    #                     is. This one asks the question that matters instead:
    #                     can our code hold id 0x08 AND leave the delay working?
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
    # Diagnostic tempo-cave variants stamp the panel name so the running
    # firmware is unmistakable (the R48/R49 isolation, 24 Aug 2026).
    # 11 chars + a 2-char tag is 13, which FILLS the 13-byte field and leaves
    # no NUL -- the defect Bryan T's HELLO WORLD contribution found on the
    # abbr field (5 chars in 5 bytes, crash on LFO modulation). Bounded to 10
    # so the tagged name still terminates. The check below enforces it for
    # every arm that writes a name, not just these two.
    if os.environ.get("TEMPOCAVE") == "replay":
        FULLNAME["DELAY SERVER"] = b"BusDlyRPL" + BUILD_TAG
    elif os.environ.get("NOTEMPO") == "1":
        FULLNAME["DELAY SERVER"] = b"BusDlyNOC" + BUILD_TAG
    cave_end = CLONE_BASE + CLONE_STRIDE * len(CLONED_ORDER)
    if any(img[NEW_LIST - BASE:cave_end - BASE]):
        sys.exit("menu cave not free")

    # ---- both name fields are NUL-TERMINATED --------------------------------
    # The schema checks what a MANIFEST declares; this checks what the build
    # actually writes, which is not the same string -- the panel name is
    # rewritten from six different places depending on the flags, and the
    # build tag is appended after all of them. A name that exactly fills its
    # field leaves no terminator, and the firmware's string read runs off the
    # end of it: 5 chars in the 5-byte abbr crashed a real unit on LFO
    # modulation (2 Sep 2026, Bryan T -- schema.MenuEntry has the writeup).
    # Two diagnostic delay names had been doing it to the 13-byte fullname
    # since 24 Aug 2026, found by that contribution and shortened above.
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
        #
        # ⚠️ THIS PASS RAN FOR THE REVERB ONLY UNTIL 17 Aug 2026, and the delay
        # paid for it on the first flash that had page 2 enabled (R19). Cloning
        # SPRING REV, BusDelay inherited SPRING's formatters verbatim:
        #   slot 6  WOW  count 128, inherited SPRING TYPE's WORD-LABEL pair
        #                (0x4003c718 + 0x40047424, a 3-entry table) -- an
        #                enumerated renderer asked to draw 0..127 from three
        #                labels DREW NOTHING AT ALL. Reported as "WOW has no
        #                dial on the display".
        #   slot 7  MODE count 5, inherited SPRING BAL's bipolar pair
        #                (0x4003c7a0) AND a non-zero 0x12a -- so the engine
        #                select drew as a BALANCE DIAL reading -64..-60.
        #   slot 9  PTCH count 4, inherited an unused slot's zeros -- a plain
        #                numeric dial reading 0..3 instead of a select.
        # The counts were right and reaching the panel in every case; only the
        # renderer was wrong. The control that proves it: the reverb's SHMR is
        # ALSO slot 6 at count 128, and draws as a normal knob -- same slot,
        # same count, formatters zeroed. (Sam, on the R19 flash, 17 Aug 2026.)
        if name in STEPPED_SLOTS:
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
            # R16: WIDTH (9) and ->DEL (11) are now 4-step SELECTS too (the
            # companion low-byte fields do not publish as smooth knobs on
            # hardware), so they get the same stepped renderer -- otherwise a
            # count-4 knob crams its four values into the first ~3% of travel.
            for step_slot in STEPPED_SLOTS[name]:
                wr32(clone_P + 0x0ca + step_slot * 4, 0x4003c718)
                wr32(clone_P + 0x0fa + step_slot * 4, 0x40047254)
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
                  f"relocated; see tools/build_fx1.py)")
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
                     f"it buffer-free (docs/MODULES.md, 'only a buffer-free "
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
    fb_pos = 0 if NO_FB else ORDER.index(REMIX.fallback)
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
    _caves = [c for k in REMIX.modules for c in remix_modules()[k].cf_patches]
    _replay = os.environ.get("TEMPOCAVE") == "replay"
    # TEMPOCAVE=replay: the hook with a cave that ONLY replays the displaced
    # instructions -- isolates the hook mechanism from the stores (R48/R49
    # killed the voices on the unit; docs/DSP.md 6c-i).
    _plan = []
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
    # The SECOND zero run (docs/MAINMENU.md section 5, 0x400d24d0..0x400d2ce0):
    # pinned caves may live there, and since 3 Sep 2026 label formatters that
    # no longer fit the clone window overflow into it, above whatever cave
    # already sits there. _ovf_top is the first free byte of that run.
    _ovf_top = OVERFLOW_RUN
    for _c, _b in _plan:
        if _c.cave_addr is None:
            # FLOATING (schema.CavePatch): first free address after what
            # precedes it, rounded up to 0x80. With three clones this is
            # 0x400d7000 then 0x400d7080 -- the addresses the shipping
            # image pinned -- and with six it clears the clone block that
            # used to run straight into them.
            _c = dataclasses.replace(_c, cave_addr=(_cave_top + 0x7f) & ~0x7f)
        # ⚠️ A CAVE MAY LIVE OUTSIDE THE CLONE WINDOW. The region from
        # CLONE_BASE to the chooser list is crowded -- six descriptor clones
        # and fifteen label formatters left 84 bytes on the rig -- and
        # docs/MAINMENU.md names two other unclaimed runs. A cave pinned into
        # one of those is checked for being FREE (below) and for not
        # overlapping another module's cave (the ledger), but it neither
        # follows nor advances this region's cursor.
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
        # The bytes are PINNED so the build needs no m68k toolchain; when one
        # is present the source is re-assembled and compared, so a source that
        # has drifted from what we ship cannot pass unnoticed.
        if (_c.source and _c.emit is None and not _replay
                and shutil.which("m68k-elf-as")
                and shutil.which("m68k-elf-objcopy")):
            with tempfile.TemporaryDirectory() as td:
                o, bp = os.path.join(td, "c.o"), os.path.join(td, "c.bin")
                subprocess.run(["m68k-elf-as", "-mcpu=5407", "-o", o,
                                _c.source], check=True)
                subprocess.run(["m68k-elf-objcopy", "-O", "binary", "-j",
                                ".text", o, bp], check=True)
                if pathlib.Path(bp).read_bytes() != _c.pinned:
                    sys.exit(f"{_c.source} no longer assembles to its "
                             f"pinned bytes -- re-pin them in the "
                             f"manifest deliberately")
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
        # A formatter registration names the module it draws for, so a remix
        # that omits that module skips the write instead of pointing into a
        # descriptor which was never cloned.
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
    # The bytes come from tools/label_fmt.py rather than a pinned CavePatch:
    # twelve caves whose contents vary with the labels cannot be hand-pinned,
    # and emit() is re-derived through m68k-elf-as whenever one is on PATH.
    _lbl_top = max(_cave_top, cave_end)
    _lbl = []
    for name in CLONED_ORDER:
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
    # is not new -- tools/build_fx1.py proved it standalone against the stock
    # image (data only, 74 bytes changed) and it still applies today.
    #
    # It costs NO WORDS. The code is in the image either way; this is four
    # bytes of cave per row plus the relocated list. What it does cost is
    # CYCLES: an FX1 effect runs on a track that is already running an FX2
    # one, so the worst per-core load can gain four more copies of it
    # (tools/cycle_count.py, which prices FX1 slots for exactly this reason).
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
            if _n not in ORDER:
                sys.exit(f"fx1={_n!r}: it has no FX2 chooser row, so there "
                         f"is no descriptor clone for FX1 to point at")
            # A REPLACEMENT is listed by its own key. The composed list is
            # rebuilt from scratch in the cave, so the stock row its id
            # inherited (the in-place repoint above edits the STOCK list,
            # which the three `lea` refs no longer point at) cannot show
            # beside it. Until 3 Sep 2026 this exited as "would show it
            # twice", which was true of the stock list and false of the
            # composed one.
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
        _ours = [n for n in _fx1 if not _MODS[n].is_stock]
        print(f"  FX1 chooser = {len(_new) - 1} rows at 0x{_fx1_addr:08x} "
              f"(NONE + {', '.join(_fx1)}), {len(FX1_LIST_REFS)} refs "
              f"repointed, viewport {_fx1_rows}, id and cursor tables "
              f"written -- {len(_ours)} of ours, no words: their code is "
              f"already placed")

    # ALWAYS report the headroom, even when nothing was planted. It used to
    # ride on the label-formatter line, so a remix with no labelled select
    # (SEND alone, say) reported no cave figure at all and the remixer's
    # budget had a hole in it -- for a selection that builds perfectly well.
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
    # remix did to all fourteen before 2 Sep 2026, and it is what keeps
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
        print(f"  placed but NOT LISTED: {', '.join(HIDDEN)} -- code, id and "
              f"clone present, no chooser row, twelve names blanked so the "
              f"track page draws nothing")
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
    # MODE=n substitutes a literal for the page-2 MODE read, so each character
    # can be auditioned locally. (dsp_host HAS driven companion fields via
    # -params indices 7/9/11 since 17 Aug 2026; these overrides predate that
    # and force the decoded VALUE -- so DFRZ=2 is FROZEN, not SYNC. To test
    # SYNC locally pass index 11 = 2 in -params, as the 24 Aug measurement
    # did.) dsp_host once could not drive companion fields (its
    # -params only writes value<<16 into knob fields), so this is the only way
    # to hear the modes without a flash. Diagnostic only -- the normal build
    # reads the real slot.
    # NOSHIM=1: physically EXCISE the shimmer if it needs to come out
    # (e.g. to reclaim the 2048-word Y buffer or the ~130 words of program).
    # SHIMMER is now IN by default. The metallic artifact was the OLD shimmer
    # (v119 and earlier) which spliced dry samples into the tail; this one was
    # built from scratch (v3) and is clean in isolation. See VOICING.md.
    if os.environ.get("NOSHIM") == "1":
        i = reverb_src.index("; SHIMMER_BEGIN")
        j = reverb_src.index("; SHIMMER_END") + len("; SHIMMER_END")
        cut = reverb_src[i:j].count("\n")
        reverb_src = reverb_src[:i] + "; SHIMMER REMOVED (NOSHIM=1)" + reverb_src[j:]
        print(f"  shimmer excised ({cut} lines) -- NOSHIM=1 set")
    elif reverb_src is not None:
        print("  shimmer IN (default) -- NOSHIM=1 to excise")

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
    # It used to be dsp/burn_probe.asm, a verbatim COPY of reverb_server.asm
    # plus two blocks. That copy silently went stale: it was forked before
    # v121, so it carries no bus auto-gain, and its own header still claims it
    # is "reverb_server.asm verbatim except the two marked BURN PROBE blocks".
    #
    # A cycle meter that measures an engine we do not ship is worse than no
    # meter -- the whole point is that (ceiling with burn) - (ceiling without)
    # prices the REAL configuration. So the two blocks now live in
    # dsp/burn_block{1,2}.inc and are spliced into the current source at build
    # time, against anchors asserted to exist exactly once. If the engine moves
    # under them the build FAILS rather than measuring the wrong thing.
    if os.environ.get("BURN") == "1":
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
            # << 16: the dispatch compares against SHORT immediates, which the
            # DSP56300 places MSB-aligned, and the extract above is `asl #$8`
            # to match. A low-aligned override would miss every compare and
            # land on BIG -- exactly the bug 2da90f0 fixed.
            # DECIMAL immediate: MODE=3 << 16 spelled $30000 is the payload-A
            # Y base literal, which the XBUS _sub would rewrite to $38000
            # (mode 0x38). Latent-only since the HALL cut (MODE stops at 2),
            # found 12 Aug 2026 when DMODE=3 tripped the delay-source census.
            "        move    #>%d,a" % (int(mode_env) << 16))
        print(f"  *** MODE OVERRIDE: forced to {int(mode_env)} ***")

    # WIDTH is a companion field like MODE (v92): dsp_host writes only the
    # knob field, so every local render before this override was MONO --
    # +1.00 L/R correlation in every measured row through Round 12, while
    # VintageVerb's field is decorrelated. Same mechanism as MODE=: clobber
    # a with the immediate right before the store to $2c. << 16 puts the
    # 0..127 value where the knob-field extraction above lands it.
    if os.environ.get("WIDTH") is not None:
        sys.exit("WIDTH= is retired (v6, 23 Aug 2026): the knob is SHFT, the "
                 "shimmer interval select, and dsp_host drives companion "
                 "fields directly -- use render_reverb -p SHFT=n")

    # DMODE=n forces BusDelay's MODE select, same mechanism and reason as
    # MODE= above: dsp_host writes only the knob field of a param word, so a
    # companion-field select cannot be driven by -params at all. The v2 engine
    # (PLAN.md 3.1) reads its MODE from r6+$c bits 8-15 exactly like BusVerb;
    # << 16 makes the immediate MSB-aligned to match the `asl #$8` extract.
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
    # interval (branch midi, 24 Aug 2026). Same immediate-substitution
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

    # DFRZAT=n engages FREEZE after n post-warm-up BLOCKS instead of from
    # sample 0 -- the missing repro lever PLAN.md's "FREEZE cannot be
    # auditioned locally" names: a static DFRZ=1 freeze holds the silence the
    # warm-up just cleared. DEV-ONLY (guarded below): the emitted code keeps a
    # block counter in one word of payload A's owned shared-window half
    # (Y:0x37FFE -- init-zeroed, above the bus scratch at 0x360d2, below the
    # DEV delay lines at their shipping base; nothing else touches it in a DEV
    # layout). Branchless: sub sets N once, the two Tcc read it, and the
    # interleaved immediate moves do not disturb the condition codes -- the
    # same shared-flag idiom as the sample loop, with nothing between the pair.
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
    # The accumulators live at Y:0x900-0x9d2, which is CORE-PRIVATE low Y --
    # one core's sends write their own copy and the other core's server cannot
    # see it. Same address, different physical memory. Relocating them into the
    # shared 64K is the whole architectural change; everything else about the
    # bus is already written and hardware-proven.
    #
    # 0x36000 -- and the FIRST choice, 0x3E000, was WRONG. Hardware, 7 Aug:
    # the bus broke even SAME-CORE. The gate was provably inert in that test
    # (both effects were payload A, where it falls through), so the address was
    # the only remaining variable. Two things were wrong with it, and both are
    # checks that "the manual says the window is shared" let me skip:
    #
    #   * 0x3E000 is OUTSIDE the init pass. Init zeroes 0x30000-0x37FFF (32768
    #     words from 0x30000), so 0x3E000 comes up holding garbage.
    #   * payload A had never been shown to write there. dsp/alias_probe.asm
    #     tested payload A at 0x31000/0x33000/0x35000/0x37000 -- all the LOWER
    #     half. 0x38000-0x3FFFF was only ever exercised from payload B.
    #
    # 0x36000 fixes both: inside the zeroed region, and between two addresses
    # payload A has demonstrably written and read back. Still clear of stock's
    # per-frame staging (0x30000-0x30047, rewritten EVERY FRAME), both
    # bootstraps (0x31000/0x32000) and payload B's stub (0x38000), and still
    # its own 8K block (0x36000-0x37FFF) for the manual's "no bus contentions
    # when the two cores access different 8K blocks".
    #
    # NOTE for any real build: 0x36000 is inside core 0's FX2 SLOT 4
    # (0x34000-0x37FFF). Harmless while every core-0 track is BusVerb
    # (hardcoded Y:0x4000) or a SEND (zero-footprint), but it is not free
    # ground and BusDelay would contend for it.
    #
    # The map is mechanical: new = 0x3E000 + (old - 0x900), so the whole 0x900
    # -0x9d2 layout keeps its shape and all three files stay in agreement --
    # which they must, or the buses will not find each other.
    if os.environ.get("XBUS") == "1":
        # Overridable so the next round is a one-liner, not a code edit.
        XBUS_BASE = int(os.environ.get("XBUS_BASE", "36000"), 16)

        def xbus(src, name, label):
            n = len(re.findall(r"\$9[0-9a-f]{2}\b", src))
            if not n:
                sys.exit(f"XBUS: {name} has no bus scratch literals to move")
            # ⚠️ `$09xx` (zero-padded) literals are DELIBERATELY outside this
            # pattern: the delay's RATE/DRV state lives at CORE-PRIVATE Y
            # $0901-$0903 after the shared-window words at 0x360d3-5 proved
            # dead on hardware (R36; mechanism unknown, docs/PARAM_PAGES.md
            # sibling note in the source). Relocating them would aim the
            # writes into the shared REVERB accumulator. The census below
            # pins the count so drift is loud.
            n_priv = len(re.findall(r"\$09[0-9a-f]{2}\b", src))
            # RATE increments are 4 refs; a v6+ source adds 4 more for the
            # freeze-crossfade ramp (satdrv tail load/store, per-block re-arm
            # load/store). Keyed on the ramp word's presence so verify_delay
            # can still build a pre-v6 REFERENCE source.
            n_want = 8 if "y:>$0904" in src else 4
            # + 2 for the TIME slew state (load + store, 24 Aug 2026)
            n_want += 2 if "y:>$0907" in src else 0
            # + 4 for the sticky-snap state: last knob + held division,
            # load + store each (24 Aug 2026)
            n_want += 4 if "y:>$0908" in src else 0
            # + 3 for the MIDI branch (24 Aug 2026): latched note $090a,
            # load + store, and since 3 Sep 2026 the warm-up's clear (the
            # emulator's core-private Y is boot garbage, and a garbage
            # note drove GRAIN's pitch in every local render)
            # (2 for a source without the warm-up clear, so verify_delay can
            # still build a pre-v5 reference)
            n_want += (3 if "note starts at NONE" in src else 2) \
                if "y:>$090a" in src else 0
            # + 5 for the RETD return-liveness state (3 Sep 2026): the grace
            # counter $090b (load + store) and this block's host print gain
            # $090c (store, then one load per channel in the output stage)
            n_want += 5 if "y:>$090b" in src else 0
            if name == "DELAY SERVER" and n_priv != n_want:
                sys.exit(f"XBUS: {name} expected exactly {n_want} core-private "
                         f"$09xx refs (RATE/DRV state"
                         f"{' + freeze ramp' if n_want == 8 else ''}), "
                         f"found {n_priv}")
            src = re.sub(r"\$9([0-9a-f]{2})\b",
                         lambda m: "$%x" % (XBUS_BASE + int(m.group(1), 16)), src)
            if src.count("; XBUS_GATE") != 1:
                sys.exit(f"XBUS: {name} is missing its ; XBUS_GATE marker")
            # ⚠️ HKB=1 SWAPS WHICH PAYLOAD HOUSEKEEPS. A DIAGNOSTIC, not a
            # feature -- see the XBUS.md entry on the cross-core accumulator
            # race. Housekeeping (the parity flip AND the clearing of the new
            # write buffer) has always run on payload A, which is also where
            # BusVerb lives -- so the reverb is inherently in lockstep with
            # it and can never race. BusDelay is on payload B and reads
            # buffers the OTHER core flips and zeroes asynchronously, which is
            # the leading explanation for the metallic hash Sam measured on
            # the delay bus (+22..31 dB of inharmonic HF vs the host path).
            # With HKB=1 the roles swap: payload B housekeeps and payload A
            # becomes the racer. If the artifact FOLLOWS the core -- delay
            # clean, reverb now carrying it -- the race is confirmed.
            #
            # ⚠️ It has to be done by INVERTING THE BRANCH, not by changing
            # the comparand. The first operand's $30000 is the payload's OWN
            # base and is rewritten to $38000 for payload B by the blanket
            # substitution -- writing $30000 as the comparand too would get
            # rewritten with it and compare the base against itself, gating
            # BOTH payloads out and killing the bus. beq -> bne is the whole
            # change: A ($30000) != $38000 so A skips, B ($38000) == so B runs.
            # ⚠️ THE GATE IS NO LONGER INJECTED HERE. It used to be a RUNTIME
            # test of the payload's own base literal, emitted identically into
            # both payloads and substituted per payload afterwards -- which
            # means the ungated payload carried four instructions that could
            # never branch. build_bus knows which payload it is emitting, so
            # the payload loop now emits an unconditional `bra` for the gated
            # one and NOTHING for the other: 6 words -> 2 on one payload and
            # -> 0 on the other. That is where payload A's headroom came from
            # (it was at FREE 0), and it is behaviourally identical because the
            # comparison's outcome was already fixed at build time.
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
        # what every remix did before 3 Sep 2026 -- so a default selection
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
        # own end (docs/DSP.md s8) -- so keying the region by effect would
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
        # ⚠️ A GAP IS TWO RUNS, NOT A SMALLER REGION. A module of ours is one
        # code stream, so it must fit inside a single run -- but different
        # modules can sit in different runs, and the placer below packs them
        # that way. Until 3 Sep 2026 this refused any gap and the caller
        # handed us the largest run alone, so harvesting two separated groups
        # gave up the smaller one for nothing (Sam, 3 Sep: "when I remove some
        # reverb it only shows the free reverb space"). Splitting here is what
        # makes every harvested word placeable; the only residual cost of a
        # gap is FRAGMENTATION, which the placer reports by name.
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
        # THE SECOND CROSS-CORE DEFECT (docs/XBUS.md step 3, hardware-confirmed
        # 17 Aug 2026). Every bus client used to read the shared rotation word
        # at its own dispatch time. Core 0 owns the flip, so core 0's clients --
        # dispatched right after the housekeeper -- always see the post-flip
        # value. Core 1's clients read it asynchronously, so whichever one's
        # execution window STRADDLES the flip sees the old rotation on some
        # blocks and the new one on others, and its contribution lands in an
        # already-consumed buffer half the time. Block-rate amplitude jitter:
        # broadband hash, linear in the send level, character invariant.
        #
        # Proven by changing track 5 -- core 0's POSITION 0, i.e. the
        # housekeeper -- from BusVerb to Send, which cured static on a core-1
        # path with nothing on core 1 touched.
        #
        # PAYLOAD A NEEDS NOTHING and pays 6 words for the uniform interface;
        # it is in lockstep with the flip by construction. PAYLOAD B tracks its
        # own rotation: advance exactly one step per block, and trust that
        # rather than the shared word unless the shared word says we are more
        # than one step out.
        #
        # ⚠️ THE KEEP CONDITION IS ASYMMETRIC ON PURPOSE. `S == R + one step`
        # is the pre-flip read -- the normal core-1 case, and the whole thing
        # we are immunising against -- so it keeps S. EVERYTHING else snaps to
        # R, which is what makes it self-healing: a client that misses a block
        # falls one behind, reads R == S + one step next block, and snaps.
        # 🟡 One state is stable and wrong: S stuck exactly one step AHEAD is
        # indistinguishable from a legitimate pre-flip read. It is harmless --
        # that client's audio lands in a buffer read one block (~0.36 ms) later
        # than everyone else's, CONSTANT rather than jittering, and never in
        # the buffer being read. Constant offsets are inaudible; jitter is not.
        # It cannot arise in the emulator (single core, always post-flip, S
        # tracks R exactly from the first block), which is what keeps the
        # bit-identity gate meaningful.
        #
        # ⚠️ ASSUMES THE CORES ARE RATE-LOCKED and merely phase-offset. If they
        # can actually drift, "advance one per block" diverges and this needs a
        # real elastic buffer instead. UNVERIFIED -- no local test can reach it.
        # ⚠️ THE ROTATION WORD'S ADDRESS MUST BE SPELLED RELOCATED HERE.
        # This substitution runs INSIDE the payload loop, which is AFTER the
        # XBUS pass has already rewritten every `$9xx` literal in the source to
        # XBUS_BASE + 0x9xx. Text inserted now is not seen by that pass, so a
        # bare `$900` in the body below would read CORE-PRIVATE Y:0x900 instead
        # of the shared rotation -- resolving the offset to zero on every block
        # while the housekeeper rotates, which silently breaks every client.
        # Cost the first build of this fix an hour; the bus gate caught it as
        # nine dead renders. Same family as every other blanket-substitution
        # trap in CLAUDE.md.
        # ⚠️ AND THE MAP IS `base + (old - 0x900)`, NOT `base + old`. The whole
        # 0x900..0x9ff page relocates onto XBUS_BASE..+0xff, so the rotation
        # word -- $900, the first word of the page -- lands on XBUS_BASE
        # EXACTLY. Adding the full 0x900 pointed at unowned memory 0x900 words
        # past the scratch and resolved every offset from garbage. Caught by
        # reading the GENERATED source and seeing the neighbouring hand-written
        # line relocate to a different address than mine.
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
            body = (f"        bra     {_GATE_LABEL[name]}         "
                    f"; payload {tag} never housekeeps" if gated else
                    f";  (payload {tag} housekeeps: no gate emitted)")
            return src.replace("; XBUS_GATE", body, 1)

        def _rotinit(src, name, slot):
            """Seed the tracked rotation at init. PAYLOAD B ONLY."""
            if "; ROTINIT" not in src:
                return src
            as_b = (tag == "B") or (DEV and name == "DELAY SERVER")
            if not as_b:
                return src.replace("; ROTINIT",
                                   f";  (payload {tag} recomputes every block: "
                                   f"nothing to seed)", 1)
            # ⚠️ GUARDED ON r7 LOOKING LIKE A REAL FX2 STATE BLOCK. dsp_host
            # sets r7 before calling init, but that is the EMULATOR'S instance
            # model -- the hardware evidence for r7 (dsp/r7probe.asm, 0x6200
            # for the first FX2 instance) was taken in PROC, not init. An
            # unguarded store here would be a wild X write if hardware leaves
            # r7 alone until proc, which is the family that froze the unit
            # once already. LOWER BOUND ONLY, for words: it catches the boot
            # states that actually occur (zero and small leftovers). An
            # implausibly HIGH r7 would still store out of range -- accepted,
            # and recorded here rather than left silent. If r7 is implausible we seed nothing: the tracked
            # value stays garbage and the effect behaves as it did before this
            # fix -- a known state rather than a hang.
            # ⚠️ `seedskip` and not `initrts`: `init` is an existing label and
            # dsp_asm resolves labels by PREFIX, so `initrts` assembled to
            # init's address with "rts" appended. Caught at assembly, which is
            # the cheap case, but it is the same trap that once branched into
            # hyperspace.
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
                body = "\n".join([
                    "        move    x:(r7+$67),a        ; ROTLATCH: payload B",
                    "        tst     a",
                    "        bne     rotdone             ; not the block's first call",
                    f"        move    x:(r7+${slot:02x}),a",
                    "        add     #>$10,a             ; advance exactly one step",
                    "        and     #>$30,a             ; per block, mod 4",
                    "        move    a,x1                ; x1 = S'",
                    f"        move    y:>${_rot:x},a         ; the shared rotation, ONCE",
                    "        move    a,x0                ; x0 = R, the snap target",
                    "        add     #>$10,a",
                    "        and     #>$30,a             ; a = R + one step",
                    "        move    a,y0",
                    "        move    x1,a                ; a = S'",
                    "        cmp     y0,a                ; S' == R+step: a pre-flip",
                    "        tne     x0,a                ; read, so KEEP S'. else snap",
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

        # The DELAY is substituted unconditionally: without XBUS it carries its
        # own Y base, with XBUS it is either a literal-free stub (a no-op
        # substitution) or, under DEV, base + gate discriminator, both of which
        # want rewriting to this payload's base.
        #
        # ...EXCEPT under DEV, where the delay is placed in payload A but must
        # keep its SHIPPING address, 0x38000 (payload B's half) -- found 12 Aug
        # 2026 after the RDS layout rendered full-scale garbage. Payload A's
        # half of the window is FULLY OWNED: BusVerb's relocated buffers sit
        # at 0x30000/0x34000 and the bus scratch at XBUS_BASE (0x36000), so a
        # delay based at 0x30000 writes its 32K lines straight through both --
        # LineR alone crosses the parity word, all four ACC buffers and both
        # role locks every 16384 samples. Substituting 0x38000 for BOTH payloads
        # makes the DEV delay byte-identical to the one that ships: same line
        # addresses, same gate discriminator (it never housekeeps -- the SEND's
        # self-healing election covers that, exactly as on hardware).
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
        # LFO roll table (10 Aug 2026): reverb_server.asm's rolled lines 2-7
        # read per-line [rate const, phase slot, int slot, frac slot] from a
        # 24-word P table via p:(r5)+. Placed immediately BEFORE the module so
        # the address is known pre-assembly; the source's $facade literal is
        # rewritten to it. dsp_asm has no dc directive, hence raw words here.
        # 17 Aug 2026: lines 0 and 1 joined the roll, in their own two-trip
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
        for name, src in plan:
            if "$facade" in src and src.count("$facade") != 1:
                sys.exit(f"payload {tag}: {name} has multiple $facade "
                         f"LFOTAB literals -- expected exactly one")
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
                words, init_a, proc_a = assemble(src, DEV_DELAY_P)
                if DEV_DELAY_P + len(words) >= 0x20000:
                    sys.exit(f"payload {tag}: DEV delay overruns the "
                             f"entry-point plausibility bound "
                             f"(0x{DEV_DELAY_P + len(words):05x} >= 0x20000)")
                wrw_p(pp["xtab"] + NEW_IDS[name] * 3, init_a)
                wrw_p(pp["xtab"] + (32 + NEW_IDS[name]) * 3, proc_a)
                if tag == "A":
                    dev_delay = words
                print(f"  {name:13} P:0x{DEV_DELAY_P:05x}..0x"
                      f"{DEV_DELAY_P + len(words):05x} ({len(words):4} words)"
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
            for _r in runs:
                _c, _end = _r["cursor"], _r["base"] + _r["words"]
                _tab, _s2 = None, src
                if "$facade" in src:
                    _tab = (LFO01 + LFOTAB) if LFO01_MARK in src else LFOTAB
                    if _c + len(_tab) > _end:
                        continue
                    _s2 = src.replace("$facade", f"${_c:x}")
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
            if tab is not None:
                place(tab, _r["cursor"])
                print(f"  LFOTAB        P:0x{_r['cursor']:05x}.."
                      f"0x{_r['cursor'] + len(tab):05x} "
                      f"({len(tab):4d} words)  rolled LFO lines "
                      f"{'0-7' if LFO01_MARK in src else '2-7'}")
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
        # This used to null all three unconditionally, so a build that placed
        # 250 words silenced 2,724 words' worth of reverb -- and the answer
        # to "why can I never get the stock verbs back?" was "you cannot,
        # ever". PLAN §7 item 2. The precedent is CHORUS, which got its stock
        # dispatch back the moment the build stopped taking its code.
        #
        # The stream is contiguous from base_a, so the written span is
        # [base_a, cursor) and a donor whose record STARTS at or after the
        # cursor still holds its own code, untouched. Give it back.
        # ⚠️ BY SPAN, NOT BY A HAND-WRITTEN DONOR LIST. Every harvested
        # effect whose code the stream did not reach keeps its algorithm and
        # its dispatch; every one it did reach is silenced. That is what the
        # three reverbs have always done, now true of whatever was harvested.
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
        # ⚠️ A REPLACED effect's dispatch is OURS, not the null stub's.
        # A module with MenuEntry(replaces=...) carries the stock id and
        # the placement above already wrote its entries there; its
        # stock code is harvested ground like any other. This pass ran
        # AFTER placement and, by span, nulled the very entry it had
        # just written -- found by tracing on 3 Sep 2026, never hit
        # because no shipped module replaced anything yet.
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
    out.write_bytes(bytes(img))
    d = sum(1 for x, y in zip(IMG.read_bytes(), img) if x != y)
    note = ""
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
                  f"  python3 tools/send_probe.py --mem {mem}\n"
                  f"  python3 tools/render_reverb.py loop.wav --mem {mem}\n"
                  f"DELAY SERVER is id 0x{NEW_IDS['DELAY SERVER']:02x}; "
                  f"send_probe's entry_points() resolves it from the dump.")
        else:
            print(f"\nDEV dump ready ({REMIX.name} carries no DELAY SERVER):\n"
                  f"  drive dsp_host against {mem} directly, or through "
                  f"send_probe for the modules it knows.")


if __name__ == "__main__":
    main()
