"""Tempo sync -- the project's first ColdFire code caves.

This module adds no effect. It changes what the firmware DOES, which makes it
the worked example of the other kind of contribution: two patches into the
ColdFire main OS, one hooking a per-frame routine, one supplying a display
formatter.

THE PROBLEM IT SOLVES. The DSP is never told the tempo -- the ColdFire
computes every tempo-derived rate itself, so a DSP effect has no way to know
what a bar is. The publish cave hooks the per-frame voice-record writer at
the instruction that stores the FX2 id, replays that instruction, and then
also stores tempo24, samples-per-MIDI-clock (Q12.4), the crossfader position
and any held MIDI note into four halfwords of the record that are written
every frame and never read. Those land on the DSP side as r6+$6..$9.

⚠️ THE CAVE FILTERS ON FX2 IDS 6 AND 7, AND THOSE IDS ARE COMPILED INTO THE
PINNED BYTES (`subq.l #6,%d0; cmpi.l #1,%d0` in tempo_cave.s). A module that
changes its fx2 id does not change this cave, and the two then disagree
silently -- the DSP simply never sees a tempo. Until the build can patch
values into a cave, an id change here means re-assembling and re-pinning.

The formatter cave is BongDelay TIME's display: it prints the division name
("1/8") while the DSP's sticky snap holds one and milliseconds otherwise,
using the same integers as the DSP rule. It is position-independent and its
two state longs live inside the cave.

Both caves sit in the stock zero run at 0x400d6b00-0x400d7c3c, past the
descriptor clones. NOTEMPO=1 installs neither, and the DSP side then reads
zeros and SYNC becomes a no-op by design.
"""

from remix.schema import CavePatch, FormatterReg, Kind, Module

# The per-frame voice-record writer, at the instruction that publishes the
# FX2 id. Ten bytes: three instructions, displaced into the cave.
TEMPO_HOOK = 0x40004d40
TEMPO_HOOK_STOCK = bytes.fromhex("14280dbc" "4882" "35420038")

TEMPO_CAVE_BYTES = bytes.fromhex(
    "14280dbc" "4882" "35420038"           # displaced: id -> +0x38
    "2f00" "2002" "5d80" "0c8000000001" "624c"   # id-6 > 1 -> skip
    "2f01"
    "2039460d16c8" "5280" "35400028"       # fader+1 -> +0x28 (r6+$8)
    "2f08" "41f9400d64c2" "10304800" "205f"  # held note[d4] ...
    "0280000000ff" "0c80000000ff" "6602" "4280"  # 0xff (released) -> 0
    "3540002a"                             # ... -> +0x2a (r6+$9)
    "20398000181c" "6712"                  # tempo24; 0 -> nodiv (R48
                                           # HUNG AT BOOT on divu.l by 0)
    "35400024"                             # tempo24 -> +0x24 (r6+$6)
    "223c0285ff00" "4c401001" "35410026"   # 42336000/tempo24 -> +0x26
    "221f" "201f" "4e75")

TIME_FMT_BYTES = bytes.fromhex("4fefffec48d7043c202f001c45fa010a2200ef89068100000040b0926748248042aa0004243980001814673a263c0285ff004c4230032401e88a41fa008878007a001a184c035000e88d9a816a024485ba8264082544000452aa000452840c840000000a66da202a0004672241fa006032300afe02810000ffffd1c12f48001c4cd7043c4fef00144ef940013a08700a4c001000203c000001b94c4010012f41001c4cd7043c4fef00142f2f00084879400b465d2f2f000c4eb940013a084fef000c4e750203040608090c1012180014001a001f0025002a002f00350039003e0043312f33325400312f333200312f31365400312f313600312f385400312f31362e00312f3800312f345400312f382e00312f3400000000ffffffff00000000")

MODULE = Module(
    name="tempo-sync",
    key="TEMPO SYNC",
    kind=Kind.CF_PATCH,
    doc="ColdFire caves: publishes tempo/fader/note to the DSP, and draws "
        "BongDelay TIME as a tempo division.",
    cf_patches=(
        CavePatch(
            label="tempo cave",
            cave_addr=0x400d7000,
            pinned=TEMPO_CAVE_BYTES,
            source="modules/tempo-sync/tempo_cave.s",
            hook_addr=TEMPO_HOOK,
            hook_stock=TEMPO_HOOK_STOCK,
        ),
        CavePatch(
            label="time_fmt cave",
            # Moved here 24 Aug 2026 when the tempo cave grew to 104 bytes.
            cave_addr=0x400d7080,
            pinned=TIME_FMT_BYTES,
            source="modules/tempo-sync/time_fmt.s",
            # A (P+0x0ca) points at the cave and B (P+0x0fa) stays zero --
            # stock DELAY TIME's own configuration.
            registers_formatter=FormatterReg(module="DELAY SERVER", slot=0),
        ),
    ),
)
