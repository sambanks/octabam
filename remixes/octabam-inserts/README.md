# octabam-inserts

A remix of Octatrack OS 1.40C, built from your own copy of it, that adds the
core modules (below) and a set of effects that run on any track, on FX1
and FX2, with the stock DELAY. It has no bus and no SEND: every effect is an
insert on its own track. See [Where it has run](#where-it-has-run).

## The effects

Every effect below is an insert: it runs on any track, on the menus marked.
The stock DELAY stays; the other stock effects give up their DSP words.
No SIDECHAIN_COMPRESSOR: it overlaps CHARACTER's own compressor, so stock
COMPRESSOR keeps its id, undisturbed, with no side-chain KEY.

| effect | FX1 | FX2 | what it is | module |
|---|---|---|---|---|
| SPECTRUM | ✓ | ✓ | filter: Moog ladder, SEM, Capacitor2, formants | [`spectrum`](../../modules/spectrum/README.md) |
| CHARACTER | ✓ | ✓ | fold, saturation, tilt, compressor, width | [`character`](../../modules/character/README.md) |
| MODULATION | ✓ | ✓ | Juno, Dimension, flanger, phaser, comb | [`modulation`](../../modules/modulation/README.md) |
| TRANSIENT | ✓ | ✓ | transient shaper (Ignorato) | [`transient`](../../modules/transient/README.md) |
| EUCLID | ✓ | ✓ | Euclidean filter / amp sequencer (repeat98) | [`euclid`](../../modules/euclid/README.md) |
| LOFI2 | | ✓ | ring mod or stereo frequency shifter into sample-rate and bit reduction on stock LO-FI's curves, plus a high-shelf cut: FREQ, MIX, FDBK/GAIN, SRR, BRR, LPF, RANGE, MODE, AMPH | [`lofi2`](../../modules/lofi2/README.md) |
| DELAY | | ✓ | stock | |
| GATE VERB | | ✓ | gated plate reverb (the reverb stage of Mutable Instruments Clouds plus a gate): AMNT, GAIN, TIME, DIFF, TONE, GATE | [`gateverb`](../../modules/gateverb/README.md) |

The three stations are FX1-only in the bus remix; here each has its `SLOTS`
build setting at `FX1+FX2`, so an FX2 instance runs live. LOFI2 is FX2-only
in this remix: eight instances (FX1+FX2 on all four tracks of a core) would
cost 3,328 cycles of the 3,120 usable; four (FX2) cost 1,664, and the worst
core is then 2,984 with four MODULATIONs on FX1. CHARACTER's KEY
= T1 needs a BusDelay host, so in this remix it keys on the track's own
input. The FX1 chooser lists NONE and the effects marked FX1; the FX2
chooser lists the effects marked FX2. A MODE turned on the panel re-defaults
the knobs around it ([`mode-defaults`](../../modules/mode-defaults/README.md)).

## The core modules

The same set is in [`octabam-bus`](../octabam-bus/README.md).

| group | module | what it does |
|---|---|---|
| platform | [BRAIN](../../modules/brain/README.md) | card-wide settings, defaults and templates, remix switch, TOOLS (MIDI monitor, LOAD) |
| | [STORE](../../modules/store/README.md) | the save, load, copy and Part sites KITS and PLOCKS P2 share |
| | [LOAD METER](../../modules/load-meter/README.md) | the frame interrupt's and each DSP core's busy time, for BRAIN's LOAD view |
| sequencing | [KITS](../../modules/kits/README.md) | 255 Kits per project; each pattern plays its Kit |
| | [MIDI SCENES](../../modules/midi-scenes/README.md) | scene locks for MIDI tracks |
| | [SCENES P2](../../modules/scenes-p2/README.md), [PLOCKS P2](../../modules/plocks-p2/README.md) | scene locks and parameter locks on FX page 2 |
| | [CC MAP](../../modules/cc-map/README.md), [CC FEEDBACK](../../modules/cc-feedback/README.md) | CC onto page 2; knob changes out as CC |
| | [DIRECT_JUMP_KYOTI](../../modules/direct-jump-kyoti/README.md), [RELOAD_FROM_PROJECT](../../modules/reload-from-project/README.md) | clock-locked direct jump; reload one track from the card |
| | [SCALE QUANTIZER](../../modules/quantizer/README.md), [TUNER](../../modules/tuner/README.md) | scale quantizing on PTCH; a tuner window (UP + TEMPO) |
| USB | [USB](../../modules/usb/README.md) | MIDI both ways; tracks, MAIN and CUE to a computer (TRACKS PRE, MAIN, CUE, MIDI on by default; settings in BRAIN) |
| recorder and fixes | [RECORDER LOOP FIX](../../modules/recorder-loop-fix/README.md), [RLEN PLEN](../../modules/rlen-plen/README.md) | the loop click; RLEN value PLEN |
| | [BATCH_BUGFIXES](../../modules/batch-bugfixes/README.md), [ERASE_EMPTY_TRIGLESS_LOCKS](../../modules/erase-empty-trigless-locks/README.md), [QUANTIZE_LIVE_REC_TOGGLE](../../modules/quantize-live-rec-toggle/README.md), [REC_TRIG_MUTE](../../modules/rec-trig-mute/README.md), [MUTE_MODES](../../modules/mute-modes/README.md) | Zac-Kyoti's fixes and mute modes (MUTE_MODES runs from DRAM) |
| | [PATTERN MUTE](../../modules/pattern-mute/README.md) | a second mute layer saved with the pattern, as on the Digitakt II; double-press FUNC chooses the layer |
| | [ATA WRITE GUARD](../../modules/ata-write-guard/README.md) | keeps the first PIO card write and its bookkeeping atomic against the completion interrupt |

## What it costs

| | stock | octabam-inserts |
|---|---|---|
| sample and recorder memory | 14,602 pages | 12,895 pages (the platform reserve) |
| DSP words free, payload A / B | | 363 / 363 |

## Where it has run

Cursory testing on an MKII (owner report, 16 Oct 2026). Port gates:
`make check REMIX=octabam-inserts` and the reach round. MUTE_MODES from DRAM,
BRAIN and CC MAP's regenerated bytes have not run on a unit.

## How to flash

[BUILDING.md](../../docs/guide/BUILDING.md) has every step, from what to
install to the way back to stock. For this remix:

1. **Build.** Pick a build number; it becomes the OS version the unit shows.

   ```bash
   make image REMIX=octabam-inserts BUILD=91     # -> out/OCTATRACK_OCTABAM91.bin
   ```

2. **Back up the card.** KITS writes `kits.work` into each project it loads.
3. **Old projects.** For a project made before this remix, on the card:

   ```bash
   python3 tools/hw/ot_project.py stamp-defaults "<card>/<set>/<project>" octabam-inserts
   ```

4. **Flash from the card** ([BUILDING.md section 5](../../docs/guide/BUILDING.md#5-flash-from-the-card)),
   then power-cycle once more. SYSTEM STATUS → OS VERSION reads `OCTABAM91`.
5. **Back to stock:** [BUILDING.md section 8](../../docs/guide/BUILDING.md#8-back-to-stock-or-another-remix).

If the unit misbehaves, [FAILURE_MODES.md](../../docs/contributing/FAILURE_MODES.md)
is the register of what has gone wrong and why.
