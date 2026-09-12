"""Recorder spacing -- a ColdFire cave that makes a fixed-RLEN recording
exactly as long as the gap to the next arm, computed from the CURRENT arm
with no lane, no lookahead and no stored state (RTOS_FORK 10.56, 12 Sep 2026).

THE PROBLEM. The length converter (0x40006dfc) returns one CONSTANT length
for a whole loop -- 82,687 at 128 BPM / RLEN 16, through a truncated
reciprocal -- while the sequencer arms at floor(k x period) of an EXACT
fractional period, so consecutive arms are alternately 82,687 and 82,688
samples apart. On the passes where the two disagree the buffer's wrap
splices two input moments two samples apart instead of one, and the
free-running read head of OCTABAM82 walks straight through it: the -26 dB,
~1 ms scuff on ALTERNATE BARS measured on Sam's unit and confirmed by the
tempo test (RTOS_FORK 10.53). At a tempo whose period is an integer --
65.6, 120, 125, 126, 135, 140, 144, 150 -- there is nothing to skip, which
is why those are clean and 128 is not.

WHY NOT recorder-seam. That cave asks the LANE for the next step event and
is FALSIFIED (10.55): on a one-trig-per-bar lane the event resolves to the
PAST and recedes 16 samples per frame, so its L' comes out 0 and its guard
correctly refuses -- 0 substitutes in 1,200 calls under the port.

THE CAVE. Same hook, no lane. The sequencer arms at floor(k x N/D) with
N = RLEN x 15,876,000 and D = tempo24, so with q, r = divmod(N, D) every
spacing is q plus a Bresenham overflow, and the residue is recoverable from
the CURRENT arm alone: arm_k = k x q + floor(k x r/D) with floor(k x r/D)
< q, making k = arm/q exact. RLEN is recovered from the stock length
(RLEN = round(L x D / 15,876,000)), which is what makes the cave state-free
-- no scratch word, no residue across passes, no claim but the hook.

    L' = q + floor((k+1)r/D) - floor(k x r/D),  k = arm/q

VALIDATED, not measured on hardware: L' equals the sequencer's own next
spacing on 115,200 (tempo, RLEN, pass) triples -- 12 tempi x 8 RLENs x
1,200 consecutive passes -- both as the model (out/hw/softretrig/lever_e.py)
and as an instruction-accurate simulation of this cave's assembled bytes.
Over all 11,208 (tempo, RLEN) pairs in 60.0..200.0: q == the stock length at
every tempo whose period is an integer, so the cave writes back the value
that was already there and the GOLDEN CASE CANNOT REGRESS; and
|L' - L| <= 1 everywhere, so the +/-1 guard is kept as a safety net.

Exactness bound: k = arm/q holds while floor(k x r/D) < q -- past 165,000
passes at RLEN 16 / 128 BPM (86 hours) and 23,600 at RLEN 4 (3 hours); the
arm counter's own 32-bit wrap comes first at ~27 hours.

UNFLASHED and unmeasured on hardware. The route to the reader IS measured:
the bind copies the voice's data-END bound from the write-position table at
0x4000f89e and that still runs under 82's caves (10.56), so one extra
recorded sample moves the reader's wrap one sample at the next bind.

Reads: 0x80001814 (tempo24), 0x46c7fa84[track] (arm sample), 164(%sp).
Writes: nothing but d4, the length.

Assemble: `m68k-elf-as -mcpu=5475 -o spacing.o spacing_cave.s`; the build
re-assembles and compares against the pinned bytes below.
"""

from remix.schema import CavePatch, Kind, Module

SPACING_HOOK = 0x40006e0c
SPACING_HOOK_STOCK = bytes.fromhex("2800" "5284" "e284")   # movel d0,d4; addql #1,d4; asrl #1,d4

# ⚠️ objdump prints every divu.l here as `remul` -- 0x4c4x is one encoding
# family and GNU names it after the remainder form. With the extension's Dq
# and Dr fields equal (4c41 0000 = both d0) ColdFire writes the QUOTIENT,
# which is what this cave uses; see spacing_cave.s for the full note.
SPACING_CAVE_BYTES = bytes.fromhex(
    "2800" "5284" "e284"                     # displaced: L = (product + 1) >> 1
    "4fefffe8" "48d7030f"                    # save d0-d3/a0-a1 (24 bytes)
    "2239" "80001814" "6700" "0072"          # d1 = tempo24; 0 -> keep
    "2004" "4c010000"                        # d0 = L x D
    "0680" "00791fd0"                        # + 7,938,000  (round to nearest)
    "243c" "00f23fa0"                        # d2 = 15,876,000
    "4c420000" "6700" "0058"                 # d0 = RLEN = (L x D + K/2) / K; 0 -> keep
    "4c020000" "2600"                        # d0 = N = RLEN x K; d3 = N
    "4c410000" "6700" "004a"                 # d0 = q = N / D; 0 -> keep
    "2400" "4c010000" "9680" "6700" "002c"   # d2 = q; d3 = r = N - q x D; 0 -> guard
    "202f00a4" "e588"                        # d0 = track x 4  (caller's sp(136) + 4 + 24)
    "41f946c7fa84" "20300800"                # d0 = arm sample[track]
    "4c420000"                               # d0 = k = arm / q
    "4c030000" "2240"                        # d0 = k x r; a1 = k x r
    "d083" "2609"                            # d0 = (k+1) x r; d3 = k x r
    "4c410000" "4c413003"                    # d0 = floor((k+1)r/D); d3 = floor(k x r/D)
    "9083" "d480"                            # d0 = overflow (0|1); d2 = L' = q + overflow
    "2002" "9084" "5280" "0c8000000002" "6200" "0004"  # |L' - L| <= 1 ?
    "2802"                                   # d4 = L'
    "4cd7030f" "4fef0018" "4e75")            # restore, rts

MODULE = Module(
    name="recorder-spacing",
    key="RECORDER SPACING",
    kind=Kind.CF_PATCH,
    doc="ColdFire cave: a fixed-RLEN recording is exactly as long as the gap to "
        "the next arm, derived from the current arm -- no lane, no stored state.",
    cf_patches=(
        CavePatch(
            label="spacing cave",
            cave_addr=None,
            pinned=SPACING_CAVE_BYTES,
            source="modules/recorder-spacing/spacing_cave.s",
            hook_addr=SPACING_HOOK,
            hook_stock=SPACING_HOOK_STOCK,
            report_note=" (fixed-RLEN length := the next arm's spacing, from the current arm)",
        ),
    ),
)
