# octabam

A remix of Octatrack OS 1.40C, built from your own copy of it, that adds the
core modules (below) to all 14 stock effects and adds SPECTRUM, CHARACTER and
MODULATION, which are copied into the DSP when a track uses them. It
has no bus and no SEND. See [Where it has run](#where-it-has-run).

## The effects

All 14 stock effects stay in the menus and run as stock. SPECTRUM, CHARACTER and
MODULATION are on FX1 and FX2. Their DSP code is not in the image's
upload: while a track uses one, the ColdFire copies it into the shared P window
(`P:0x30000..0x3ffff`), at offset `0x3820` of one of the four FX2 buffer slots, and
withdraws it when no track does. Until it arrives, about 25 ms, the effect passes
the audio through. Stock PLATE REV, DARK REV and SPRING REV are fronted by a guard
that runs them only while their buffer does not cover loaded code. A block is held by whoever has it first. Choosing one of
a demand effect on a chooser is refused, with a toast, while the FX2 slot that shares
its memory is on a stock reverb, and choosing a stock reverb on that slot is refused while
the effect is loaded. A song that sets both by another route leaves the reverb or the
effect dry, and says which at the next page key. The design and what has been measured:
[`DEMAND_LOAD.md`](../../docs/proposals/DEMAND_LOAD.md).

| effect | FX1 | FX2 | id | what it is | module |
|---|---|---|---|---|---|
| SPECTRUM | ✓ | ✓ | 0x0f | filter: Moog ladder, SEM, Capacitor2, formants | [`spectrum`](../../modules/spectrum/README.md) |
| CHARACTER | ✓ | ✓ | 0x17 | fold, saturation, tilt, compressor, width | [`character`](../../modules/character/README.md) |
| MODULATION | ✓ | ✓ | 0x0e | Juno, Dimension, flanger, phaser, comb | [`modulation`](../../modules/modulation/README.md) |

TRANSIENT, DISTORX and SIDECHAIN_COMPRESSOR are not in this remix; COMPRESSOR runs as stock. Their modules are in the repository.

The stations have their `SLOTS` build setting at `FX1+FX2`. CHARACTER's KEY = T1
needs a BusDelay host, so here it keys on the track's own input. A MODE
turned on the panel re-defaults the knobs around it
([`mode-defaults`](../../modules/mode-defaults/README.md)).

## The core modules

The same set is in [`octabam-bus`](../octabam-bus/README.md), with LOFI AMF FIX
(the stock LO-FI's AMF control).

| group | module | what it does |
|---|---|---|
| platform | [BRAIN](../../modules/brain/README.md) | card-wide settings, defaults and templates, remix switch, TOOLS (MIDI monitor, LOAD) |
| | [STORE](../../modules/store/README.md) | the save, load, copy and Part sites KITS and PLOCKS P2 share |
| | [LOAD METER](../../modules/load-meter/README.md) | the frame interrupt's and each DSP core's busy time, for BRAIN's LOAD view; its DSP half runs from the window |
| demand loader | [DLPUMP](../../modules/dlpump/README.md), [DLCOPY](../../modules/dlcopy/README.md) | the ColdFire half that watches the tracks and sends the code; the DSP half that copies it into the window |
| sequencing | [KITS](../../modules/kits/README.md) | 255 Kits per project; each pattern plays its Kit |
| | [MIDI SCENES](../../modules/midi-scenes/README.md) | scene locks for MIDI tracks |
| | [SCENES P2](../../modules/scenes-p2/README.md), [PLOCKS P2](../../modules/plocks-p2/README.md) | scene locks and parameter locks on FX page 2 |
| | [CC MAP](../../modules/cc-map/README.md), [CC FEEDBACK](../../modules/cc-feedback/README.md) | CC onto page 2; knob changes out as CC |
| | [DIRECT_JUMP_KYOTI](../../modules/direct-jump-kyoti/README.md), [RELOAD_FROM_PROJECT](../../modules/reload-from-project/README.md) | clock-locked direct jump; reload one track from the card |
| | [SCALE QUANTIZER](../../modules/quantizer/README.md), [TUNER](../../modules/tuner/README.md) | scale quantizing on PTCH; a tuner window (UP + TEMPO) |
| USB | [USB](../../modules/usb/README.md) | MIDI both ways; tracks, MAIN and CUE to a computer (TRACKS PRE, MAIN, CUE, MIDI on by default; settings in BRAIN) |
| recorder and fixes | [RECORDER LOOP FIX](../../modules/recorder-loop-fix/README.md), [RLEN PLEN](../../modules/rlen-plen/README.md) | the loop click; RLEN value PLEN |
| | [BATCH_BUGFIXES](../../modules/batch-bugfixes/README.md), [ERASE_EMPTY_TRIGLESS_LOCKS](../../modules/erase-empty-trigless-locks/README.md), [QUANTIZE_LIVE_REC_TOGGLE](../../modules/quantize-live-rec-toggle/README.md), [REC_TRIG_MUTE](../../modules/rec-trig-mute/README.md), [MUTE_MODES](../../modules/mute-modes/README.md) | Zac-Kyoti's fixes and mute modes (MUTE_MODES runs from DRAM) |
| | [ATA WRITE GUARD](../../modules/ata-write-guard/README.md) | keeps the first PIO card write and its bookkeeping atomic against the completion interrupt |

## Where it has run

Sam's MKII, image `OCTABAMR3` (this remix before the rebase onto `fa49e92f`), USB TRACKS PRE, 1 Nov 2026, the hardware
suite ([HARDWARE_SUITE.md](../../docs/contributing/HARDWARE_SUITE.md)): `pre-meter`, `pre-transport`, `pre-usb`
(`underruns=0`) and `dsp-watch` (20 cycles) pass; 74 effect layouts ran with no crash or stall, 39 flagged (CLICKS,
ROUGH, DC, STATIC, CLIP: MODULATION, SPECTRUM and CHARACTER `dear` and mode layouts, DJ EQ, LO-FI); the 20 demand-loader
transitions between BASE, the stock reverbs, MODULATION, SPECTRUM and CHARACTER applied with `bad 0`, each with about
340 ms of silence and a ColdFire run of 404 to 476 us (a frame is 362.8 us); `kits-identity` (603 program changes),
`scenes-sweep` (2,289 operations) and `djump-burst` (536) pass; crossfader to lock CC 0.77 to 0.95 ms median; DIRECT_JUMP
lands within 0 to 5 steps with the toggle on and at the pattern end with it off.

VARISPEED was added and FX2 LOCK removed after `OCTABAMR3`; `OCTABAMV5` (that composition) was flashed on 2 Nov 2026 and FX2 picks take effect; the suite was not run on it. In a loader soak on 2 Nov 2026
the image without VARISPEED left 3 of 32 program changes unapplied and the image with it 4
([FAILURE_MODES.md](../../docs/contributing/FAILURE_MODES.md)).

Not run on this image: `mix-soak` and the [manual plan](../../docs/contributing/HARDWARE_MANUAL.md). The images that
had CX OSC, STEM REC, SCOPE, MIDI SCALES or RND NAME stopped the DSP or left program changes unapplied in the
same probes ([FAILURE_MODES.md](../../docs/contributing/FAILURE_MODES.md)). Not measured on a unit: the stock reverbs'
buffer extents at other settings, the toast wording and width.

Earlier, the loader alone: Sam's MKII, 26 Oct 2026, the images `DLPROBEJ1` to `K1` (`remixes/test/dl-probe`;
[CHANGELOG](../../CHANGELOG.md)).

EDIT EVENTS/PLOCKS: radiohagen, Octatrack MKII, PLK858/build 98, 22 October 2026:
held-edit and trig/track/pattern checks passed
([results](../../modules/plocks-p2/DEVELOPMENT.md#edit-events-hardware-results-22-october-2026)).

## How to flash

[BUILDING.md](../../docs/guide/BUILDING.md) has every step, from what to
install to the way back to stock. For this remix:

1. **Build.** Pick a build number; it becomes the OS version the unit shows.

   ```bash
   make image REMIX=octabam BUILD=91     # -> out/OCTATRACK_OCTABAM91.bin
   ```

2. **Back up the card.** KITS writes `kits.work` into each project it loads.
3. **Old projects.** For a project made before this remix, on the card:

   ```bash
   python3 tools/hw/ot_project.py stamp-defaults "<card>/<set>/<project>" octabam
   ```

4. **Flash from the card** ([BUILDING.md section 5](../../docs/guide/BUILDING.md#5-flash-from-the-card)),
   then power-cycle once more. SYSTEM STATUS → OS VERSION reads `OCTABAM91`.
5. **Back to stock:** [BUILDING.md section 8](../../docs/guide/BUILDING.md#8-back-to-stock-or-another-remix).

If the unit misbehaves, [FAILURE_MODES.md](../../docs/contributing/FAILURE_MODES.md)
is the register of what has gone wrong and why.
