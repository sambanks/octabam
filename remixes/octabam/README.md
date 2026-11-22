# octabam

A remix of Octatrack OS 1.40C, built from your own copy of it. It adds the core
modules (below), SCOPE and TUNER, keeps all 14 stock effects, and adds SPECTRUM,
CHARACTER, MODULATION and SHATTER, which are copied into the DSP when a track
uses them. It has no bus and no SEND.

## The effects

All 14 stock effects stay in the menus and run as stock. SPECTRUM, CHARACTER and
MODULATION are on FX1 and FX2; SHATTER is on FX2. Their DSP code is not in the image's
upload: while a track uses one, the ColdFire copies it into the shared P window
(`P:0x30000..0x3ffff`), at offset `0x3820` of one of the four FX2 buffer slots, and
withdraws it when no track does. Until it arrives, about 25 ms, the effect passes
the audio through. Stock PLATE REV, DARK REV and SPRING REV are fronted by a guard
that runs them only while their buffer does not cover loaded code. A block is held by whoever has it first. Choosing one of
a demand effect on a chooser is refused, with a toast, while the FX2 slot that shares
its memory is on a stock reverb, and choosing a stock reverb on that slot is refused while
the effect is loaded. A song that sets both by another route leaves the reverb or the
effect dry, and says which at the next page key. The design:
[DEMAND_LOADER.md](../../docs/contributing/DEMAND_LOADER.md).

| effect | FX1 | FX2 | id | what it is | module |
|---|---|---|---|---|---|
| SPECTRUM | ✓ | ✓ | 0x0f | filter: Moog ladder, SEM, Capacitor2, formants | [`spectrum`](../../modules/spectrum/README.md) |
| CHARACTER | ✓ | ✓ | 0x17 | fold, saturation, tilt, compressor, width | [`character`](../../modules/character/README.md) |
| MODULATION | ✓ | ✓ | 0x0e | Juno, Dimension, flanger, phaser, comb | [`modulation`](../../modules/modulation/README.md) |
| SHATTER | | ✓ | 0x0a | fold, clip, bit and sample-rate crush, chaotic feedback | [`shatter`](../../modules/shatter/README.md) |

COMPRESSOR is [SIDECHAIN_COMPRESSOR](../../modules/sidechain-compressor/README.md): stock COMPRESSOR with a
side-chain KEY on page 2. Its DSP code (1,711 words) is loaded the same way, into the top of T4's FX2 block, while a
track uses COMPRESSOR; until it is, or while DARK REV on T4's FX2 or another loaded effect holds that block,
COMPRESSOR runs as stock, KEY reads `--` and a toast says `SC KEY OFF`.

TRANSIENT and DISTORX are not in this remix. Their modules are in the repository.

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
| | [SCALE QUANTIZER](../../modules/quantizer/README.md), [TUNER](../../modules/tuner/README.md), [SCOPE](../../modules/scope/README.md) | scale quantizing on PTCH; a tuner window (**[UP]** + **[TEMPO]**); full-screen track audio (**[DOWN]** + **[TEMPO]**) |
| | [SCALES](../../modules/scales/README.md) | 52 scales for a MIDI track's ARP SETUP KEY, a scale chooser, the CHROMATIC trig keys lit with the scale (SCALE QUANTIZER's on audio tracks) |
| | [CHORDS FACTORY](../../modules/chords/README.md), [PAGES](../../modules/pages/README.md) | chord progressions for a MIDI track, sixteen slots a bank, voice-led; PAGES is the page-key cycle its page joins |
| | [SLOW LFO](../../modules/slow-lfo/README.md), [BAR LED](../../modules/bar-led/README.md) | LFO MULT 1/2X, 1/4X, 1/8X; the tempo LED green on the pattern's 1 |
| | [SCREEN](../../modules/screen/README.md) | answers Elektron's screenshot SysEx request with the screen |
| USB | [USB](../../modules/usb/README.md) | MIDI both ways; tracks, MAIN and CUE to a computer (TRACKS PRE, MAIN, CUE, MIDI on by default; settings in BRAIN) |
| recorder and fixes | [RECORDER LOOP FIX](../../modules/recorder-loop-fix/README.md), [RLEN PLEN](../../modules/rlen-plen/README.md) | the loop click; RLEN value PLEN |
| | [BATCH_BUGFIXES](../../modules/batch-bugfixes/README.md), [ERASE_EMPTY_TRIGLESS_LOCKS](../../modules/erase-empty-trigless-locks/README.md), [QUANTIZE_LIVE_REC_TOGGLE](../../modules/quantize-live-rec-toggle/README.md), [REC_TRIG_MUTE](../../modules/rec-trig-mute/README.md), [MUTE_MODES](../../modules/mute-modes/README.md) | Zac-Kyoti's fixes and mute modes (MUTE_MODES runs from DRAM) |
| | [ATA WRITE GUARD](../../modules/ata-write-guard/README.md) | keeps the first PIO card write and its bookkeeping atomic against the completion interrupt |
| | [FRAME GUARD](../../modules/frame-guard/README.md) | a frame interrupt that enters late at START or a program change waits out the window in which the DSP's frame exchange stalls |
| | [REC CS1 SKIP](../../modules/rec-cs1-skip/README.md) | the recorder's per-frame update without its redundant CS1 writes |

## Known fault

The DSP can stop when a program change puts DARK REV on several tracks while
MODULATION is loaded (in use on a track, or in the 10 s after the last track
stops using it), followed by PLAY. The sound stops; the panel and USB still
answer; a power-cycle clears it. The cause is not known. Avoid DARK REV on
many tracks in a song that uses MODULATION.
[FAILURE_MODES.md](../../docs/contributing/FAILURE_MODES.md) has the entry.

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
