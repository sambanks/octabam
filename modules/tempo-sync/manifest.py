"""TEMPO SYNC -- two ColdFire DRAM units: BusDelay learns the held MIDI note, and
its TIME draws as a division.

The publish cave hooks the per-frame voice-record writer at the instruction
that stores the FX2 id, replays it, and for FX2 id 6 (DELAY SERVER) stores
the held MIDI note into the low byte of record halfword 13 (+0x1b): the DSP
reads it at r6+$1 bits 8-15, under TIME's knob field. The tempo itself is
stock's: the writer stores tempo24 into halfword 31 of every track's record
(0x40004d6a) and BusDelay reads it at r6+$13, deriving samples per MIDI
clock (Q12.4) on the DSP.

Until 15 Sep 2026 the cave stored tempo24, the clock period, the crossfader
and the note into halfwords 18-21 (+0x24..+0x2a), believed unread. Halfwords
18-20 are the FX1 instance's page 2 and 21 the AMP page 2's first word, so
on a delay or reverb host every FX1 effect's page 2 was the tempo bytes
(docs/contributing/FAILURE_MODES.md, "An FX1 station's page 2 does not reach the
DSP on a bus host"; measured under the port).

The cave filters on FX2 id 6, compiled into tempo_cave.s (`cmpi.w #6,%d2`):
a module that changes its fx2 id must change that compare, or the DSP never
sees a note.

The formatter cave is BusDelay TIME's display: it prints the division name
("1/8") while the DSP's sticky snap holds one and milliseconds otherwise,
from the same integers as the DSP rule. Position-independent; its two state
longs live inside the cave.

Both are DRAM units; the publish cave is entered by a jsr at the hook (a
floating ROM cave in the stock zero run until 12 Oct 2026).

The CAVE build setting selects diagnostics (remixes/test/bus-notempo and
bus-tempo-replay; NOTEMPO=1 and TEMPOCAVE=replay in the environment until
11 Oct 2026, and those acted on every module's caves):
  ON      the publish cave and the formatter (the default).
  OFF     no hook, and the formatter linked but not registered: the DSP
          reads no note and TIME draws in milliseconds.
  REPLAY  a cave that only replays the displaced instructions, isolating the
          hook from the store; the formatter stays.
BusDelay's panel name says which diagnostic is running (BusDlyNOC,
BusDlyRPL).
"""

import dataclasses
import hashlib

from remix.schema import (Apply, Category, Detour, FormatterReg, Gate, Kind, Linked, Module, Option, Proof,
                          Setting, Store)

# The per-frame voice-record writer, at the instruction that publishes the
# FX2 id. Ten bytes: three instructions, replayed by the unit.
TEMPO_HOOK = 0x40004d40
TEMPO_HOOK_STOCK = bytes.fromhex("14280dbc" "4882" "35420038")

TIME_FMT_BYTES = bytes.fromhex("4fefffec48d7043c202f001c45fa011a2200e189068100000040b0926748248042aa0004243980001814673a263c0285ff004c4230032401e88a41fa008878007a001a184c035000e88d9a816a024485ba8264082544000452aa000452840c840000000c66da202a0004672241fa006232300afe02810000ffffd1c12f48001c4cd7043c4fef00144ef940013a08700a4c001000203c000001b94c4010012f41001c4cd7043c4fef00142f2f00084879400b465d2f2f000c4eb940013a084fef000c4e750203040608090c10121820240018001e00230029002e00330039003d00420047004b0050312f33325400312f333200312f31365400312f313600312f385400312f31362e00312f3800312f345400312f382e00312f3400312f325400312f342e00000000ffffffff00000000")

STORE_ID = "octabam.tempo-sync"
CAVE_MODES = ("ON", "OFF", "REPLAY")

TIME_FMT = Linked("time_fmt", "modules/tempo-sync/time_fmt.s", dram=True,
                  reference=(0x400d7800, hashlib.sha256(TIME_FMT_BYTES).hexdigest()),
                  registers_formatter=FormatterReg(module="DELAY SERVER", slot=11,
                                                   symbol="time_fmt"))

TEMPO_CAVE = Linked("tempo_cave", "modules/tempo-sync/tempo_cave.s", dram=True)


def tempo_hook(symbol):
    return Detour(TEMPO_HOOK, TEMPO_HOOK_STOCK, "tempo_cave", symbol,
                  "per-frame voice-record writer: publish the held note (id 6)", kind="jsr", pad_to=10)


def _variant(values):
    """CAVE -> the units and the detour the build installs."""
    mode = values["CAVE"]
    if mode == "OFF":
        # the formatter and the cave stay linked, unregistered and unhooked,
        # so the image's layout (a DRAM runtime with the clones in it) is
        # the ON build's
        return {"detours": (), "linked": (TEMPO_CAVE, dataclasses.replace(TIME_FMT, registers_formatter=None))}
    if mode == "REPLAY":
        return {"detours": (tempo_hook("replay"),)}
    return {}


MODULE = Module(
    name="tempo-sync",
    key="TEMPO SYNC",
    kind=Kind.CF_PATCH,
    category=Category.BUS, author="sambanks", author_url="https://github.com/sambanks",
    proof=Proof.HARDWARE, proof_note="Sam's MKII",
    doc="ColdFire DRAM units: publishes the held MIDI note to BusDelay, and draws "
        "BusDelay TIME as a tempo division.",
    # BusDelay TIME's formatter: a DRAM unit since 8 Oct 2026 (a floating
    # ROM cave until then). A (P+0x0ca) points at `time_fmt` and B (P+0x0fa)
    # stays zero -- stock DELAY TIME's own configuration. TIME is page-2
    # slot 11 since 26 Sep 2026 (slot 1 from the one-aux re-slot, 7 Sep
    # 2026; at slot 0 the division labels drew on SEND, seen on the unit,
    # 15 Sep 2026).
    linked=(TEMPO_CAVE, TIME_FMT),
    detours=(tempo_hook("cave"),),
    gates=(Gate("tools/verify/verify_tempo_publish.py", venv=True, stage="image"),),
    store=Store(STORE_ID),
    settings=(Setting(1, "CAVE", Option(*CAVE_MODES), default="ON", apply=Apply.BUILD,
                      doc="ON: the publish cave and TIME's formatter; OFF: no cave and "
                          "the formatter unregistered (diagnostic); REPLAY: a cave that only replays the hooked "
                          "instructions (diagnostic)"),),
    variant=_variant,
)
