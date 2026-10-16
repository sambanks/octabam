# `tempo-sync` — TEMPO SYNC

Feeds the held MIDI note to BusDelay and draws BusDelay's TIME knob as a
tempo division. Two ColdFire units in DRAM.

## On the unit

Since 24 Aug 2026 as a publish of tempo24, the period, fader+1 and the
note into halfwords 18-21 (`+0x24..+0x2a`, FX2 ids 6 and 7); note-only since 15 Sep 2026 (image 24): halfwords 18-20
are the FX1 instance's page 2 and 21 the AMP page 2's first halfword, so
on a delay or reverb host every FX1 effect's page 2 read the tempo bytes
(`docs/contributing/FAILURE_MODES.md`, "An FX1 station's page 2 does not reach
the DSP on a bus host").

## Open

The note unit filters on FX2 id 6 (`cmpi.w #6,%d2` in `tempo_cave.s`). A
module that changes its id must change that compare.

## The units

**The note unit** (`tempo_cave.s`, a DRAM unit; a floating ROM cave until 12 Oct 2026) is entered from the per-frame voice-record writer
at `0x40004d40` (replacing `move.b 0xdbc(a0),d2 / ext.w d2 / move.w
d2,0x38(a2)` with `jsr` + two `nop`s; the unit replays them), and for a track
whose FX2 is BusDelay (id 6) stores the held MIDI note
(`0x400d64c2[track]`, 0 on release) into record byte `+0x1b`, the low byte
of halfword 13 (`r6+$1` bits 8-15 on the DSP, under TIME's knob field).

**The formatter unit** draws BusDelay's TIME knob: the division name while
the DSP's sticky snap holds one, milliseconds otherwise.

The tempo itself is stock's: the writer stores tempo24 (`0x8000181c`) into
halfword 31 (`+0x3e`) of every track's record (`0x40004d6a`) and BusDelay
reads it at `r6+$13`, deriving the MIDI-clock period (42,336,000 /
tempo24, Q12.4) per block on the DSP.

The `CAVE` build setting (store `octabam.tempo-sync`) selects two
diagnostics. `OFF` installs no hook and leaves the formatter linked
but unregistered (no note reaches the DSP; TIME draws in milliseconds;
BusDelay reads `BusDlyNOC`): `remixes/test/bus-notempo`.
`REPLAY` hooks a symbol that only replays the displaced instructions,
isolating the hook mechanism from the store (`BusDlyRPL`):
`remixes/test/bus-tempo-replay`. Until 11 Oct 2026 these were `NOTEMPO=1`
and `TEMPOCAVE=replay` in the environment, which acted on every module's
caves; the build now refuses both variables.

Background: [`docs/firmware/DSP.md`](../../docs/firmware/DSP.md) section 6c,
[`docs/firmware/PARAM_PAGES.md`](../../docs/firmware/PARAM_PAGES.md) section 7,
[`docs/firmware/MIDI.md`](../../docs/firmware/MIDI.md).

[Installed-hook regression notes](DEVELOPMENT.md).
