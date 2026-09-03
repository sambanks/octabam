"""CF PROBE -- ColdFire headroom probe: a timing cave around the per-frame
delay routine, a fader-driven burn inside it, and a readout on HELLO WORLD.

THE QUESTION IT ANSWERS. A ColdFire-side machine (a Braids port, a Pickup
donor) would live in the audio interrupt's per-frame routine, where the
stock Echo Freeze delay already does per-sample EMAC work
(docs/EXTERNAL.md section 1). Nothing in the project measures how much of
each 16-sample frame that routine already takes, or how much more the rest
of the firmware -- sequencer, UI, card streaming, MIDI -- can lose to it
before it starves. The emulator cannot answer either: Unicorn runs the EMAC
exactly and at no fixed rate. This module is the flash that answers both.

WHAT IT DOES, per frame (modules/cfprobe/cfprobe.s carries the detail):
    t0 = DTCN3 ; jsr 0x400031a0 ; t1 = DTCN3 ; burn ; t2 = DTCN3
accumulated over 1,024-frame windows, and drawn on HELLO WORLD's GAIN by
band: 96..127 mean total busy %, 64..95 mean routine busy %, 32..63 worst
frame %, 0..31 mean period in bus-clock ticks (47,891 expected at 132 MHz).
The burn is the crossfader, iterations = fader * 128, inside the
measurement, so the sweep reads its own cost. Fader 0 is a pure measurement.

THE HOOK is the frame routine's ONLY call site, 0x40004b12 inside the audio
interrupt at IPL 5: `jsr %pc@(0x400031a0)` and the `move.w #0x2700,%sr`
after it, eight bytes, the first hook in the project that is not ten. The
cave makes the call itself and replays the SR write last, so the burn runs
at the routine's own interrupt level -- exactly where added code would.

THE CLOCK is DMA timer 3, free running at the bus clock (DTMR3 = 0x000b,
DTRR3 never written). The firmware zeroes DTCN3 itself on some event; the
cave discards any frame whose period is implausible.

WHAT IT CANNOT TELL YOU. Which task starves first, and at what reading.
That is the point of the sweep: raise the fader on a full project until
something audibly or visibly gives, then read GAIN 127's band. It runs at
IPL 5, above the RTOS time slice and the level-4 MIDI framer, so expect the
UI or card streaming to give before audio does; if audio gives first, the
audio DMA sits below level 5 and every added cycle is paid by audio.

TEMPOCAVE=replay does not apply to this cave (the displaced jsr is
pc-relative) and the build refuses it. NOTEMPO=1 installs nothing, as for
every cave.
"""

from remix.schema import CavePatch, FormatterReg, Kind, Module

# 0x40004b12: `jsr %pc@(0x400031a0)` then `move.w #0x2700,%sr`. Both are
# displaced; the cave performs both. Execution resumes at 0x40004b1a,
# `move.l 0x46104d3e,%d0`, which reloads d0 -- nothing the cave clobbers is
# live there (docs/EXTERNAL.md section 1 for the routine, the disassembly
# at 0x40004b00 for the site).
PROBE_HOOK = 0x40004b12
PROBE_HOOK_STOCK = bytes.fromhex("4ebae68c" "46fc2700")

# The formatter's entry inside the cave: `.org 0x100` in cfprobe.s.
FMT_OFFSET = 0x100

PROBE_CAVE_BYTES = bytes.fromhex(
    "2f022f032439fc07c00c4eb9400031a02639fc07c00c2039460d16c802800000"
    "007fef88670c5281528152815281538066f42239fc07c00c41fa016e96829282"
    "2002909020820c80001000006260b280625cd7a80004d3a80008d1a8000cb2a8"
    "001063042141001052a80014202800140c800000040066362168000400182168"
    "0008001c2168000c002021680010002421680014002842a8000442a8000842a8"
    "000c42a8001042a8001452a8002c261f241f46fc27004e750000000000000000"
    "0000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000000000"
    "2f02202f000c41fa00a0242800286772ea88660e222800204c42100143fa0084"
    "604a53806620242800204c682002002867502228002470644c0010004c421001"
    "43fa005c60262428002072644c41200267305380660a2228001843fa003e6008"
    "2228001c43fa00304c421001241f2f012f092f2f000c4eb940013a084fef000c"
    "4e75241f487a001f2f2f00084eb940013a08508f4e7574256400722564007825"
    "64002564002d0000000000000000000000000000000000000000000000000000"
    "000000000000000000000000000000000000000000000000"
)
assert len(PROBE_CAVE_BYTES) > FMT_OFFSET

MODULE = Module(
    name="cfprobe",
    key="CF PROBE",
    kind=Kind.CF_PATCH,
    doc="ColdFire headroom probe: times the per-frame delay routine, burns "
        "on the fader, reads out on HELLO WORLD's GAIN.",
    cf_patches=(
        CavePatch(
            label="cf probe cave",
            cave_addr=None,          # floats: pc-relative state, OS absolutes
            pinned=PROBE_CAVE_BYTES,
            source="modules/cfprobe/cfprobe.s",
            hook_addr=PROBE_HOOK,
            hook_stock=PROBE_HOOK_STOCK,
            registers_formatter=FormatterReg(module="HELLO WORLD", slot=0,
                                             offset=FMT_OFFSET),
            report_note=" (times 0x400031a0 per frame; burn = fader*128; "
                        "readout on HELLO WORLD GAIN: t/r/x %, period ticks)",
        ),
    ),
)
