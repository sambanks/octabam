"""FLEX soft retrigger -- a ColdFire cave that keeps a looping FLEX voice on a
recorder buffer running through a PLAY trig that would only have restarted it
at (or within a sample of) its own loop point (RTOS_FORK 10.47, 10 Sep 2026).

THE PROBLEM (RTOS_FORK 10.42, measured on hardware and in the port). At a
non-golden tempo a bar is a fractional number of samples (82,687.5 at 128
BPM) while the recording is an integer (82,687). The PLAY trig that re-binds
the voice each bar hard-resets its read position to the loop start, so the
reset lands alternately one sample before and after the voice's own wrap,
consecutive loops differ by a sample, and the loop point is a new transient
every bar -- Bryan's click. Golden tempos make the bar an integer and the
reset a no-op.

THE CAVE. Hooked on the bind's three position stores (0x4000f820), it skips
them when the bind's own "same slot, type, generation" verdict (its sp@55)
holds, the voice is active, on a recorder buffer, FLEX, and its read position
is within 64 samples of the new start or of its window end -- i.e. the trig
coincides with the voice's natural wrap. The voice then free-runs at its
integer loop length (the firmware's normal looped-FLEX state) and drifts half
a sample per bar against the sequencer; the reset happens again once the
drift exceeds 64 samples (~2 minutes at 128 BPM) instead of every bar. On a
golden tempo the condition is met with zero drift and the cave changes
nothing. Everything else the bind does (write-position bounds, generation,
DSP flags) still runs.

SOUND-ON-SOUND (not measured): the REC trig still restarts the recording on
the bar while playback is up to 64 samples ahead, so layered passes smear by
half a sample per pass instead of clicking. Bryan should hear that before it
ships. UNFLASHED.
"""

from remix.schema import CavePatch, Kind, Module

HOOK = 0x4000f820
HOOK_STOCK = bytes.fromhex("25480040" "25480044" "25480048")   # movel a0,(64,a2)/(68,a2)/(72,a2)

CAVE_BYTES = bytes.fromhex("2f004a2f003f67344a1267304a2a00156a2a712a00140c8000000001661e202a004890880c8000000040631c202a003490aa00480c8000000040630c254800402548004425480048201f4e75")

MODULE = Module(
    name="flex-softretrig",
    key="FLEX SOFT RETRIG",
    kind=Kind.CF_PATCH,
    doc="ColdFire cave: a PLAY trig that lands at a looping recorder-buffer FLEX "
        "voice's own loop point leaves the voice running instead of resetting it.",
    cf_patches=(
        CavePatch(
            label="soft retrigger cave",
            cave_addr=None,
            pinned=CAVE_BYTES,
            source="modules/flex-softretrig/softretrig.s",
            hook_addr=HOOK,
            hook_stock=HOOK_STOCK,
            report_note=" (FLEX re-bind within 64 samples of its wrap keeps running)",
        ),
    ),
)
