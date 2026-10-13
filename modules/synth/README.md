# `synth` — SYNTH MACHINE

A two-operator FM synth machine for FLEX tracks, built from
[timhastie/octatrick-modules](https://github.com/timhastie/octatrick-modules)
(submodule `upstream/`, pinned to `v2.14` (`39dc5d8`)). `Kind.CF_PATCH`: the voice engine as
a DRAM unit (`poly.s`), the machine list as a second DRAM unit (`machine.s`,
since 2.10), the page code as a pinned ROM cave (`page.s`; the
page descriptor itself is cloned from the unit's own ROM at first use, so no
stock bytes ship in the repo), a `SymbolRef` on the kind table's FLEX
renderer entry (and the STATIC entry, for the sample-track glide), detours
and pokes. No DSP code, no FX2 row. Since 2.9 the engine owns the AMP
envelope of a synth track and there is no peak limiter.

Since 2.10, FM SYNTH is a row of the track's machine list: the row after
PICKUP in SRC SETUP (FUNC + PLAYBACK) and in SELECT MACHINE TYPE (the track
key twice, `<< MACHINE`), on every track, with no sample and no marker file
(the chooser adapted from Modwerk's FM Synth module, MIT, Modwerk
contributors). The choice is stored as FLEX with `F`, `M`, 1 in the track's
NEIGHBOR column; a build without the module reads such a track as a plain
FLEX track (choose FLEX or STATIC before downgrading). Since 2.11 the rows
after PICKUP are a table filled per remix (FM SYNTH, then SY DRUM when the
remix carries [`sy-drum`](../sy-drum/README.md)), the six row-count pokes of
2.10 are detours that read the count, and SELECT MACHINE TYPE scrolls (its
six visible rows reach the seventh); with FM SYNTH alone every list behaves
as 2.10's and the engine assembles byte for byte as 2.10's. Since 2.12 a
machine change to or from FM SYNTH or SY DRUM (either list, or a marker
file) resets the track's machine parameters (PLAYBACK, PLAYBACK SETUP, AMP,
LFO and their SETUP pages) to the new machine's init, the values a new
project gives a track; step and scene locks are kept, as in the stock
firmware, and FX slots are kept. A change between stock machines is stock's.

Any FLEX track whose sample is named FMSYNTH*.wav also becomes a synth (a
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
envelope over 16 frames; chords snap onto SCALE QUANTIZER's root. Since
2.10: DEC 127 is HOLD (the index holds; 0 is the shortest decay, 1..126
unchanged); the note-start click is gone (every attack lasts at least one
carrier period and is S-shaped, a pitch change on a sounding mono note
crossfades, a stolen voice fades over a period); LFO SETUP's destination
list on a synth track names the FM SYNTH page's parameters; a held
CHROMATIC key sustains and releases at the key-up (HOLD gates sequencer
trigs only); after the author's test of the 2.10 engine, a note
restarted while it still sounds no longer clicks at a short DEC, a second
key inside a paraphonic voice's fade no longer drops the first, and a
live-recorded legato phrase no longer goes silent at its first trigless
step; and the engine leaves 6 dB of headroom (the mono voice and each
paraphonic voice 6.02 dB lower: VOL 0 is the reference, VOL up to about +6
stays clean). Known limit: a MACHINE change while a REL INF note sounds
leaves it sounding until the next key. Since 2.12 the metronome no longer
releases a held note: 2.9's `po_stop` hooked the frame builder's clear of
the metronome's click word (`0x46c80350` at `0x4000b2c8`), taking it for
the sequencer's STOP word, so with the metronome on every click released
the held keys and the sequencer's notes; the hook is gone, that site is
stock, and STOP still ends the voices at the stock voice kill.
`upstream/synth/README.md` is the full description
(the five phases, the voice model, what was measured and what was
inferred).

## Measured

- At `v9.1`, remixes `octatrick` and `octatrick-usb` built byte-identical
  with the module sources as a plain `modules/<name>/` directory and as this
  wrapper over the submodule (same base, same build reports), and
  byte-identical to the OCTATRICK9 images Tim flashed (built on
  upstream `0e93543`; upstream's changes since touch modules these
  remixes do not carry).
- The 2.8 features (MIDI IN, chord recording with inversions, the LEG
  modes, the sample-track glide, step transpose, the chord order) and the
  2.9 engine (the envelope laws against the DSP's, the START rule, the
  fades, STOP, `po_retrig`, the index ramp: the step / slope and |d2|
  figures) were each measured in the port through the virtual panel; the
  tables are in `upstream/synth/README.md`, per feature, with what is open.
- 2.10 and 2.11 (8 - 9 Oct 2026, the pinned `ot_emu`, in the author's tree
  and in `octatrick`): FM SYNTH chosen in either list, saved and
  cold-booted, plays as the marker-file track (the click and gate tables
  within 0.2 dB); the 6 dB is -6.02 dB on each of eighteen renders, every
  sample the old one halved within 1 LSB; with FM SYNTH alone the 2.11
  engine is byte for byte 2.10's (the FM gate harness: 512 of 512 cases,
  its state hash 2.10's); the list scrolls to the seventh row and every row is reachable
  and committable with SY DRUM in the remix; no code symbol and no detour
  target at an odd address (`upstream/tools/align_check.py`: the emulator
  does not model the ColdFire's address error, so the build is checked
  instead).
- 2.12 (10 - 11 Oct 2026, the pinned `ot_emu`): with the metronome on and
  the sequencer playing, a held key at REL INF and a held VOIC 4 chord
  sound as with the metronome off over 18 beats (2.11: cut at the first
  click), the click still sounds, and STOP still ends the voices at the
  stock voice kill; a grid trig, a held key and a live-recorded trig of the
  same note at the same VOIC measured equal (within 0.01 dB); the
  machine-change init on every route (both lists, QUICK ASSIGN, the file
  browser) writes a new project's values into the Part and its battery-RAM
  copy, keeps FX and every lock, and survives SAVE and a cold boot;
  Modwerk's synth harnesses' PCM and SY DRUM's renders are 2.11's.
- Cost against 2.8 (a static count of the FM loops): +6 instructions a
  sample a voice with the limiter's per-sample stage gone, about +15-20 %
  of a VOIC 1 synth track's frame work, ~0.1-0.2 % of the frame budget; the
  platform reserve and FREE MEM unchanged; the OS image's ROM section about
  3 KB smaller (the quantizer's move), the DRAM append a few KB larger.

## On the unit

- 26 Sep 2026: `OCTATRICK9` (remix `octatrick-usb`) on Tim's Octatrack
  MKI: the synth, the quantizer and direct jump, and USB audio on all 20
  channels on the MKI.
- Every test build since, 2.3 .. 2.8, flashed on the same MKI from Tim's
  own tree ([timhastie/octatrick](https://github.com/timhastie/octatrick),
  the same wrappers over the same submodule), and the 2.9 line up to the
  build before its last two fixes: ROOT, the DRAM quantizer, FINE 0c, the
  envelope engine and the limiter's removal ran on the MKI (the held-chord
  crackle gone, the live-key pops gone, by ear). The last two fixes (the
  sequencer trigs, the index ramp) ran on the MKI with the 2.10 engine
  (next item).
- The 2.10 engine ran on his MKI on 8 Oct 2026 in a Modwerk test image
  (MAIN OS SHA-256 `161d781d...`), not in an octabam build.
- The 2.11 engine ran on his MKI on 10 Oct 2026 as Modwerk's FM Synth
  0.1.4 (MAIN OS SHA-256 `248d987e...`), not in an octabam build: with the
  metronome on, a held note or chord was cut as if released -- 2.12's fix;
  steps entered in GRID sounded softer than played notes -- not reproduced
  by him later, and measured equal (above). The same engine ran with SY
  DRUM (MAIN OS SHA-256 `b9b65cd9...`), where he asked for the
  machine-change init that 2.12 adds.
- 2.12, 13 Oct 2026, reported by the author on the same MKI: OCTATRICK
  2.14 (`octatrick` at `v2.14`, built by his own tree from octabam
  `6e4aeb76`; MAIN OS SHA-256 `c367d8bc...`, byte for byte this tree's
  `octatrick` bus), its test sheet worked; and in Modwerk test images, not
  octabam builds: FM Synth 0.1.5 (this engine as at `v2.12` with the 2.13
  quantizer; MAIN OS SHA-256 `37661aee...`) and SY DRUM 0.1.0 with FM Synth
  0.1.5 (`27c213b2...`: a held note with the metronome on, SY DRUM -> FM
  SYNTH -> SY DRUM to the new machine's init with the step locks kept).
  Play time, MIDI gear and track counts were not recorded. The engine is
  the same at `v2.12`, `v2.13` and `v2.14` (2.13 and 2.14 change no file
  under `synth/`; Modwerk's FM gate harness: the same state hash).

## How it is built

Source: `upstream/` is Tim's repository (submodule, pinned to `v2.14` (`39dc5d8`)).
Nothing inside `upstream/` is edited here. The manifest here
(`manifest.py`) executes `upstream/synth/manifest.py` from the source on
disk and re-exports its `MODULE`; that manifest derives its source paths
from its own directory, so the same file builds at `modules/synth/` in
Tim's tree and at `modules/synth/upstream/synth/` here. The engine is
`Linked(dram=True)`: linked into the platform runtime with the other DRAM
units and depacked at boot into the arena reserve
(`docs/contributing/PLACEMENT.md`); so is the machine list (`machine.s`),
whose row table and row count are assembled per remix (`remix.inc`,
`HAVE_SYDRUM`). The page is pinned at `0x400d24d0`, the start of the second
free gap.

## Collisions

`tempo-bus` also uses the second free gap, so the ledger refuses that pair.
ANALOG BD owns the same machine-list sites; the conflict is declared (since
2.11), so the ledger names the reason.
The engine shares the platform reserve with the other DRAM modules (USB
MIDI, USB AUDIO, MIDI SCENES) inside one runtime.

## Updating

Bump the submodule pin and rebuild; the pinned page bytes and the engine's
reads of SCALE QUANTIZER's pinned addresses either hold or the build
refuses.
