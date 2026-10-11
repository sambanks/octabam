"""TEMPO SYNC -- two ColdFire caves: BusDelay learns the held MIDI note, and
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

The cave filters on FX2 id 6, compiled into the pinned bytes (`cmpi.w
#6,%d2` in tempo_cave.s): a module that changes its fx2 id must re-assemble
and re-pin this cave, or the DSP never sees a note.

The formatter cave is BusDelay TIME's display: it prints the division name
("1/8") while the DSP's sticky snap holds one and milliseconds otherwise,
from the same integers as the DSP rule. Position-independent; its two state
longs live inside the cave.

The publish cave floats in the stock zero run past the descriptor clones;
the formatter is a DRAM unit. NOTEMPO=1 installs neither; the DSP then reads no note and TIME draws in
milliseconds.
"""

import hashlib

from remix.schema import Category, Proof, CavePatch, FormatterReg, Kind, Linked, Module

# The per-frame voice-record writer, at the instruction that publishes the
# FX2 id. Ten bytes: three instructions, displaced into the cave.
TEMPO_HOOK = 0x40004d40
TEMPO_HOOK_STOCK = bytes.fromhex("14280dbc" "4882" "35420038")

TEMPO_CAVE_BYTES = bytes.fromhex(
    "14280dbc" "4882" "35420038"           # displaced: id -> +0x38
    "0c420006" "6626"                      # id != 6 -> skip
    "2f00"
    "2f08" "41f9400d64c2" "10304800" "205f"  # held note[d4] ...
    "0280000000ff" "0c80000000ff" "6602" "4280"  # 0xff (released) -> 0
    "1540001b"                             # ... -> +0x1b (r6+$1 bits 8-15)
    "201f" "4e75")

TIME_FMT_BYTES = bytes.fromhex("4fefffec48d7043c202f001c45fa011a2200e189068100000040b0926748248042aa0004243980001814673a263c0285ff004c4230032401e88a41fa008878007a001a184c035000e88d9a816a024485ba8264082544000452aa000452840c840000000c66da202a0004672241fa006232300afe02810000ffffd1c12f48001c4cd7043c4fef00144ef940013a08700a4c001000203c000001b94c4010012f41001c4cd7043c4fef00142f2f00084879400b465d2f2f000c4eb940013a084fef000c4e750203040608090c10121820240018001e00230029002e00330039003d00420047004b0050312f33325400312f333200312f31365400312f313600312f385400312f31362e00312f3800312f345400312f382e00312f3400312f325400312f342e00000000ffffffff00000000")

MODULE = Module(
    name="tempo-sync",
    key="TEMPO SYNC",
    kind=Kind.CF_PATCH,
    category=Category.BUS, author="sambanks", author_url="https://github.com/sambanks",
    proof=Proof.HARDWARE, proof_note="Sam's MKII",
    doc="ColdFire caves: publishes the held MIDI note to BusDelay, and draws "
        "BusDelay TIME as a tempo division.",
    cf_patches=(
        CavePatch(
            label="tempo cave",
            cave_addr=None,          # floats: 0x400d7000 behind three clones
            pinned=TEMPO_CAVE_BYTES,
            source="modules/tempo-sync/tempo_cave.s",
            hook_addr=TEMPO_HOOK,
            hook_stock=TEMPO_HOOK_STOCK,
            report_note=" (held note -> r6+$1 bits 8-15; id 6)",
        ),
    ),
    # BusDelay TIME's formatter: a DRAM unit since 8 Oct 2026 (a floating
    # ROM cave until then). A (P+0x0ca) points at `time_fmt` and B (P+0x0fa)
    # stays zero -- stock DELAY TIME's own configuration. TIME is page-2
    # slot 11 since 26 Sep 2026 (slot 1 from the one-aux re-slot, 7 Sep
    # 2026; at slot 0 the division labels drew on SEND, seen on the unit,
    # 15 Sep 2026).
    linked=(Linked("time_fmt", "modules/tempo-sync/time_fmt.s", dram=True,
                   reference=(0x400d7800, hashlib.sha256(TIME_FMT_BYTES).hexdigest()),
                   registers_formatter=FormatterReg(module="DELAY SERVER", slot=11,
                                                    symbol="time_fmt")),),
)
