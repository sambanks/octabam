# `synth` — SYNTH MACHINE

A two-operator FM synth machine for FLEX tracks, built from
[timhastie/octatrick-modules](https://github.com/timhastie/octatrick-modules)
(submodule `upstream/`, pinned to `v2.9` (`525f4b1`)). `Kind.CF_PATCH`: the voice engine as
a DRAM unit (`poly.s`), the page code as a pinned ROM cave (`page.s`; the
page descriptor itself is cloned from the unit's own ROM at first use, so no
stock bytes ship in the repo), a `SymbolRef` on the kind table's FLEX
renderer entry (and the STATIC entry, for the sample-track glide), detours
and pokes. No DSP code, no FX2 row. Since 2.9 the engine owns the AMP
envelope of a synth track and there is no peak limiter.

Any FLEX track whose sample is named FMSYNTH*.wav becomes a synth (a
silent 4 s marker file will do; SYNTH*.wav is still accepted, and the
marker's length never ends the note): the DSP shapes and effects the voice
as a sample. Its PLAYBACK page reads PTCH RATO INDX FINE FDBK DEC (title FM
SYNTH; PTCH in semitones, FINE in cents); on the LFO page VOIC (1 = mono,
2..4 = paraphonic) and CHRD (32 chord shapes in Syntakt order, each with
three inversions on the knob, lockable per step, snapped onto SCALE
QUANTIZER's scale); GLIDE from the quantizer's row. Since 2.8: MIDI IN
plays a synth track like the CHROMATIC keys (one voice a note up to VOIC, a
note-off releases it); a chord fingered on the keys or over MIDI during live
recording is recorded as PTCH / CHRD / VOIC locks (the bass, the shape and
its inversion, the voices heard; keys within a rolling 150 ms join, a
legato hand-over records single notes); LEG on every audio track's AMP
SETUP page (OFF / MONO on a sample track, OFF / MONO / POLY on a synth
track) is the legato switch, GLIDE the slide time, and a FLEX or STATIC
track with LEG MONO slides every pitch change over GLIDE; in GRID
RECORDING a held trig + FUNC + DOWN / UP moves its PTCH lock an octave.
Since 2.9: the engine owns the AMP envelope -- ATK / HOLD / REL are read
from the AMP page (locks, scenes and LFOs included) and applied in the
engine with the DSP's own laws, the DSP seeing an always-open envelope, so
a voice is never cut: a re-press continues the sounding oscillator from its
level, a faded note starts from silence over 16 frames, a release is at
least 1 ms, stealing and VOIC hand-overs fade, STOP kills at the stock
voice kill; the peak limiter is gone (the 1/sqrt(VOIC) level law stays, a
4-note chord about -10 dBFS); FINE reads 0c the moment a track becomes a
synth track (a file-browser load into a new project included); a sequencer
trig on a still-sounding note is delivered in the panel key's form
(`po_retrig`) so the DSP keeps its voice; a warm START ramps the FM index
envelope over 16 frames; chords snap onto SCALE QUANTIZER's root. Known
limit: a MACHINE change while a REL INF note sounds leaves it sounding
until the next key. `upstream/synth/README.md` is the full description
(the five phases, the voice model, what was measured and what was
inferred).

## How it is built

Source: `upstream/` is Tim's repository (submodule, pinned to `v2.9` (`525f4b1`)).
Nothing inside `upstream/` is edited here. The manifest here
(`manifest.py`) executes `upstream/synth/manifest.py` from the source on
disk and re-exports its `MODULE`; that manifest derives its source paths
from its own directory, so the same file builds at `modules/synth/` in
Tim's tree and at `modules/synth/upstream/synth/` here. The engine is
`Linked(dram=True)`: linked into the platform runtime with the other DRAM
units and depacked at boot into the arena reserve
(`docs/contributing/PLACEMENT.md`). The page is pinned at `0x400d24d0`, the
start of the second free gap.

`PLACE` (setting `timhastie.synth`, Apply.BUILD, default `DRAM`) chooses where the
page lives. `DRAM`: `page.s` is linked into the platform runtime with `poly.s`, the resolver at `0x40031ece`
is a detour to `pg_resolve`, and the zero run is left alone. `CAVE`: the author's
pinned ROM cave at `0x400d24d0`, which the ledger refuses in a remix that lists the
stock DELAY (`Keep` on `0x400d24d0..0x400d2ca8`, `tools/remix/stock.py`). The stock DELAY
reads that whole run as table data (issue #1007; its first words when the delay is long and the
tempo slow), so with `CAVE` the DELAY computes a different output (issue #771,
`docs/contributing/FAILURE_MODES.md`). Measured under the port: the DRAM form
renders the PLAYBACK and LFO pages pixel for pixel as the cave form, and TAPE ECHO
+ SYNTH MACHINE passes `verify_tapeecho_cpu` with it. Not on a unit; the DRAM
form has no author reference bytes (the cave form's are `PINNED_PAGE`).

## Collisions

`tempo-bus` also uses the second free gap, so the ledger refuses that pair.
The engine shares the platform reserve with the other DRAM modules (USB
MIDI, USB, MIDI SCENES) inside one runtime.

## Updating

Bump the submodule pin and rebuild; the pinned page bytes and the engine's
reads of SCALE QUANTIZER's pinned addresses either hold or the build
refuses.
