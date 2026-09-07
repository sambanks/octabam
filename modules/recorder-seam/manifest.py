"""Recorder seam -- a ColdFire cave that sizes a fixed-RLEN recording from
the sequencer's own next event, so a looping recorder trig never leaves a
one-sample hole or overlap at the seam (RTOS_FORK 10.17, 7 Sep 2026).

THE PROBLEM. The recorder length converter (0x40006dfc) computes
round(RLEN x 15,876,000 / tempo24) once per pass, through a truncated
reciprocal; the sequencer fires each trig at floor(event) of an EXACT
fractional event. With a recorder trig every N steps the spacing between
arms alternates between floor and ceil of the period, the recording is
one sample short or long once every 1/eps passes, and that is a click:
128 BPM / RLEN 4 overlaps by one sample every 8 passes, 128 / RLEN 16 has
a one-sample hole on alternate passes (RTOS_FORK 10.16.4-5, emulator).

THE CAVE. Hooked at the converter's tail (0x40006e0c, the three
instructions that finish the length), it replays them and then recomputes
the length from the lane table's next step event with the frame builder's
own arithmetic (cf8 + 16 + floor((event - lookahead) / tempo24)) minus the
arm sample the firmware keeps per track (0x46c7fa84). The result replaces
the stock length only when it is within one sample of it, so a recording
whose next step is not its re-trig keeps its RLEN. The converter runs
twice per frame for the whole recording and the end test reads its result,
so the substitution is live by the frame the end is decided.

Measured in route A (RTOS_FORK 10.17): with the cave, 128 / RLEN 4 / 1x
writes 20,671 on the eighth pass and the seam is 0 on every pass.
UNFLASHED. The lane index (= track) is inferred from a fixture where
every lane held the same event; a per-track-scale pattern is the falsifier.
"""

from remix.schema import CavePatch, Kind, Module

SEAM_HOOK = 0x40006e0c
SEAM_HOOK_STOCK = bytes.fromhex("2800" "5284" "e284")     # movel d0,d4; addql #1,d4; asrl #1,d4

SEAM_CAVE_BYTES = bytes.fromhex(
    "2800" "5284" "e284"                     # displaced: L = (product + 1) >> 1
    "4fefffec" "48d7010f"                    # save d0-d3/a0
    "262f00a0"                               # d3 = track (caller's sp(136) + 4 + 20)
    "2003" "e588" "41f980001904" "20300800"  # d0 = lane[track] (next step event)
    "90b946104cf0"                           # - lookahead
    "223980001820" "4481"                    # d1 = 2^31 / tempo24
    "a2000800" "a1c0"                        # n = floor(diff / tempo24)  (fractional macl)
    "d0b946104cf8" "5080" "5080"             # s_next = cf8 + 16 + n
    "2203" "e589" "41f946c7fa84" "90b01800"  # L' = s_next - arm sample[track]
    "2200" "9284" "5281" "0c8100000002" "6202"  # |L' - L| <= 1 ?
    "2800"                                   # d4 = L'
    "4cd7010f" "4fef0014" "4e75")            # restore, rts

MODULE = Module(
    name="recorder-seam",
    key="RECORDER SEAM",
    kind=Kind.CF_PATCH,
    doc="ColdFire cave: sizes a fixed-RLEN recording from the sequencer's next "
        "event so a looping recorder trig has no one-sample seam.",
    cf_patches=(
        CavePatch(
            label="seam cave",
            cave_addr=None,
            pinned=SEAM_CAVE_BYTES,
            source="modules/recorder-seam/seam_cave.s",
            hook_addr=SEAM_HOOK,
            hook_stock=SEAM_HOOK_STOCK,
            report_note=" (fixed-RLEN length := next-step spacing when within 1 sample)",
        ),
    ),
)
