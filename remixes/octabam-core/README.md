# octabam-core

A remix of Octatrack OS 1.40C, built from your own copy of it, that adds the
core modules below and changes no effect: all 14 stock effects and both
effect menus stay as stock has them, with stock LO-FI's AMF knob fixed
([`lofi-amf-fix`](../../modules/lofi-amf-fix/README.md)). The other official
remixes add effects to this set: [`octabam-inserts`](../octabam-inserts/README.md)
(effects that run on any track) and [`octabam-bus`](../octabam-bus/README.md)
(a delay and reverb bus). See [Where it has run](#where-it-has-run).

## The core modules

| group | module | what it does |
|---|---|---|
| platform | [BRAIN](../../modules/brain/README.md) | card-wide settings, defaults and templates, remix switch, TOOLS (MIDI monitor, LOAD) |
| | [STORE](../../modules/store/README.md) | the save, load, copy and Part sites KITS and PLOCKS P2 share |
| sequencing | [KITS](../../modules/kits/README.md) | 255 Kits per project; each pattern plays its Kit |
| | [MIDI SCENES](../../modules/midi-scenes/README.md) | scene locks for MIDI tracks |
| | [SCENES P2](../../modules/scenes-p2/README.md), [PLOCKS P2](../../modules/plocks-p2/README.md) | scene locks and parameter locks on FX page 2 |
| | [CC MAP](../../modules/cc-map/README.md), [CC FEEDBACK](../../modules/cc-feedback/README.md) | CC onto page 2; knob changes out as CC |
| | [DIRECT_JUMP_KYOTI](../../modules/direct-jump-kyoti/README.md), [RELOAD_FROM_PROJECT](../../modules/reload-from-project/README.md) | clock-locked direct jump; reload one track from the card |
| | [SCALE QUANTIZER](../../modules/quantizer/README.md), [TUNER](../../modules/tuner/README.md) | scale quantizing on PTCH; a tuner window (UP + TEMPO) |
| USB | [USB](../../modules/usb/README.md) | MIDI both ways; tracks, MAIN and CUE to a computer, and the computer's channels into inputs A-D (TRACKS PRE, MAIN, CUE, MIDI on, IN off by default; settings in BRAIN) |
| recorder and fixes | [RECORDER LOOP FIX](../../modules/recorder-loop-fix/README.md), [RLEN PLEN](../../modules/rlen-plen/README.md) | the loop click; RLEN value PLEN |
| | [BATCH_BUGFIXES](../../modules/batch-bugfixes/README.md), [ERASE_EMPTY_TRIGLESS_LOCKS](../../modules/erase-empty-trigless-locks/README.md), [QUANTIZE_LIVE_REC_TOGGLE](../../modules/quantize-live-rec-toggle/README.md), [REC_TRIG_MUTE](../../modules/rec-trig-mute/README.md), [MUTE_MODES](../../modules/mute-modes/README.md) | Zac-Kyoti's fixes and mute modes (MUTE_MODES runs from DRAM) |
| | [ATA WRITE GUARD](../../modules/ata-write-guard/README.md) | keeps the first PIO card write and its bookkeeping atomic against the completion interrupt |

## What it costs

| | stock | octabam-core |
|---|---|---|
| sample and recorder memory | 14,602 pages | 12,895 pages (the platform reserve) |
| DSP words free | | 0: LOAD METER does not fit, so core has no LOAD view DSP rows. USB IN's 29-word inject sits above payload A's code (`P:$1fdf`), in a load record of its own |

## Where it has run

Cursory testing on an MKII (owner report, 16 Oct 2026). USB IN in this remix has run under the port only; the same placement has run on Bryan T's MKII in [`usb-io-stock14`](../test/usb-io-stock14/README.md) (22 Oct 2026). Port gates:
`make check REMIX=octabam-core` and the reach round.

EDIT EVENTS/PLOCKS: radiohagen, Octatrack MKII, PLK858/build 98, 22 October 2026:
held-edit and trig/track/pattern checks passed
([results](../../modules/plocks-p2/DEVELOPMENT.md#edit-events-hardware-results-22-october-2026)).

## How to flash

[BUILDING.md](../../docs/guide/BUILDING.md) has every step, from what to
install to the way back to stock. For this remix:

1. **Build.** Pick a build number; it becomes the OS version the unit shows.

   ```bash
   make image REMIX=octabam-core BUILD=91        # -> out/OCTATRACK_OCTABAM91.bin
   ```

2. **Back up the card.** KITS writes `kits.work` into each project it loads.
3. **Flash from the card** ([BUILDING.md section 5](../../docs/guide/BUILDING.md#5-flash-from-the-card)),
   then power-cycle once more. SYSTEM STATUS → OS VERSION reads `OCTABAM91`.
4. **Back to stock:** [BUILDING.md section 8](../../docs/guide/BUILDING.md#8-back-to-stock-or-another-remix).

If the unit misbehaves, [FAILURE_MODES.md](../../docs/contributing/FAILURE_MODES.md)
is the register of what has gone wrong and why.
