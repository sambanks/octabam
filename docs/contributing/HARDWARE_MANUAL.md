# Manual test plan for the `octabam` remix

What [the hardware suite](HARDWARE_SUITE.md) cannot do: the panel, the card, the ears, and anything the unit
shows only on the LCD. Run it on the image the suite ran on, after the suite passes.

Record per item: PASS, FAIL, or NOT RUN, the image tag, the unit (MKI or MKII), the project. A FAIL gets an
entry in [FAILURE_MODES.md](FAILURE_MODES.md).

Setup: image flashed, `SYSTEM STATUS` shows the tag, power-cycled once after the flash. Use `SFX_01` (stimuli on
all eight tracks) unless the item names another project. Back up the card first: KITS writes `kits.work` into
each project it loads.

## 1. Boot and platform

| # | step | expected |
|---|---|---|
| 1.1 | power on | boots to the project screen; no freeze |
| 1.2 | PROJ > BRAIN > ABOUT > IMAGE | name, remix `octabam`, stock OS `1.40C`, module count |
| 1.3 | BRAIN > PERFORMANCE > LOAD | CFIRE and DSP bars move; with all 8 tracks playing, neither core at 100 % |
| 1.4 | BRAIN > SETTINGS | rows for BRAIN, USB; YES steps a value; value survives a power-cycle |
| 1.5 | BRAIN > LOG > EVENTS | events listed newest first with uptime |
| 1.6 | BRAIN > TEMPLATES | four tabs; NEW, open, rename, delete a template |
| 1.7 | BRAIN > REMIXES | each `.RMX` in `/BRAIN/REMIXES/`; the running one marked RUNNING; YES asks `BOOT <NAME>?`; NO cancels |
| 1.8 | SAVE FX DEFAULT on a track; load another project | the effect's default is the saved one; APPLY DEFAULTS off gives the image defaults |
| 1.9 | MODE turned on an effect page | the knobs around it re-default (MODE DEFAULTS) |

## 2. Effects (listening; the suite measured the signal)

For each effect in FX1 and FX2 on a track playing the `hits`, `pink` and `sweep` stimuli:

| # | step | expected |
|---|---|---|
| 2.1 | open the effect, turn every knob end to end | no click, no dropout; the screen labels match the module README |
| 2.2 | turn MODE through every value while playing | no click at the change; mode defaults applied |
| 2.3 | assign an LFO to two knobs of the effect | modulation follows; no stuck value |
| 2.4 | scene A with one MODE, scene B with another, move the crossfader | no click across the change |
| 2.5 | save the project, reload it | knobs, MODE and LFOs return |
| 2.6 | the same effect on 4 tracks at once, 5 minutes | stable audio, LOAD METER below 95 % per core |

Effects: the 14 stock effects and SPECTRUM, CHARACTER, MODULATION (`remixes/octabam/remix.py` has the current list).

### 2a. Demand loader (SPECTRUM, CHARACTER, MODULATION)

| # | step | expected |
|---|---|---|
| 2a.1 | choose one of the three on a track | the effect passes audio dry for about 25 ms, then runs |
| 2a.2 | remove it from every track | the block is released; a stock reverb can then be chosen on the FX2 slot that shares its memory |
| 2a.3 | with a stock reverb on that FX2 slot, choose one of the three | refused, with a toast |
| 2a.4 | with one of the three loaded, choose a stock reverb on the sharing FX2 slot | refused, with a toast |
| 2a.5 | all three at once on different tracks, then two on the same block (homes in `window_homes`) | each runs; the holder keeps the block; the second goes to its next home or is refused with a toast |
| 2a.6 | open a song that sets both by another route | the reverb or the effect is dry, and the next page key says which |
| 2a.7 | CHARACTER KEY = T1 | keys on the track's own input (no BusDelay host in this remix) |
| 2a.8 | stock reverb size and decay sweeps at each setting, then load and withdraw an effect | no reverb crash or silence |

## 3. Sequencing

### 3.1 KITS

| # | step | expected |
|---|---|---|
| 3.1.1 | first load of a project without `kits.work` | the stock Parts migrate; Kit `4 * bank + part` is that Part |
| 3.1.2 | change pattern by the panel and by program change | the pattern's Kit loads into the Part slot |
| 3.1.3 | LOAD KIT, SAVE KIT | the Kit is written and read back |
| 3.1.4 | the list: copy, paste, clear, undo | each acts on the selected Kit; undo restores |
| 3.1.5 | assign a Kit to a pattern, change pattern | that Kit loads |
| 3.1.6 | 255 Kits in a project | the 255th saves and loads |
| 3.1.7 | save, power-cycle, reload | Kits and assignments return |
| 3.1.8 | new project, then bank change | no corruption of the bank file (field report, 11 Oct) |
| 3.1.9 | PROJECT load of a pre-KITS project after `stamp-defaults` | loads; sequencer plays |

### 3.2 MIDI SCENES, SCENES P2, PLOCKS P2

| # | step | expected |
|---|---|---|
| 3.2.1 | MIDI track: set a scene lock by hand | value stored; crossfader moves the CC |
| 3.2.2 | copy and paste a scene | the cells equal the source |
| 3.2.3 | scene locks inside Kits | the Kit carries them |
| 3.2.4 | FX page 2: scene A held, turn a knob | one cell written; FUNC + turn clears it; with 8 cells taken, a turn is dropped |
| 3.2.5 | FX page 2: hold a trig, turn a knob | a lock on that step; FUNC + turn removes it; the next trig restores the Part value |
| 3.2.6 | hold a trig with a P2 lock | the value shows after the page-1 delay, highlighted |

### 3.3 DIRECT_JUMP_KYOTI and RELOAD_FROM_PROJECT

| # | step | expected |
|---|---|---|
| 3.3.1 | power on | toggle OFF |
| 3.3.2 | [PTN] + [YES] | toggle on; indicator as in the module README |
| 3.3.3 | cue another pattern with tracks of different lengths and scales | takes over on the next step at the position it would be at since START |
| 3.3.4 | the trig key lights during a burst of program changes | whether the display lags or jumps (seen 25 Oct, not located) |
| 3.3.5 | [PTN] + [TRACK n] | track n's card-saved sequence reloads with the Part untouched; toast; transport and metronome keep phase |
| 3.3.6 | [BANK] + [TRACK n] | the saved Part is re-applied; knobs show the reloaded values |
| 3.3.7 | the same two chords on a MIDI track | the MIDI track reloads |
| 3.3.8 | [CUE] + [TRACK n] | stock cue, no reload |

### 3.4 Recorder, sequencer and bug fixes

| # | step | expected |
|---|---|---|
| 3.4.1 | RECORDER LOOP FIX: a FLEX track playing its own recorder buffer every bar at 128 BPM, 10 minutes | no click at the loop point; no hash at the seam |
| 3.4.2 | RLEN PLEN: 1/4X track, 16-bar pattern, TRIG ONE, QREC PLEN | one REC press records exactly one pass and stops |
| 3.4.3 | the same on a 48-step 1/2X pattern at 128 BPM | 6 bars |
| 3.4.4 | BATCH_BUGFIXES: Plays-Free MIDI track, trig quantize DIRECT, scale PER TRACK | no stall after the first step |
| 3.4.5 | BATCH_BUGFIXES: a pattern holding only parameter locks | its [BANK] grid LED reads as used |
| 3.4.6 | ERASE_EMPTY_TRIGLESS_LOCKS: erase the last lock of a trigless lock | it leaves the trig row; FUNC + TRIG empty lock stays |
| 3.4.7 | QUANTIZE_LIVE_REC_TOGGLE: [REC] held, tap [PLAY] | toast `LIVE REC: QUANTIZED` or `UNQUANTIZED`; tap again inverts; PERSONALIZE check follows; survives a power-cycle |
| 3.4.8 | REC_TRIG_MUTE: [TRACK] + [REC] | `REC TRIGS MUTED`; a running recording finishes; none start; again unmutes |
| 3.4.9 | MUTE_MODES: PERSONALIZE > MUTE MODE, each of OT, OTFX, OTFX-T, DT-T | behaviour as the module README; survives a power-cycle |
| 3.4.10 | SCALE QUANTIZER: SCALE, ROOT, GLIDE rows in PROJECT > CONTROL > SEQUENCER | PTCH knob snaps to degrees; chromatic keys snap; key 1 sounds the root; GLIDE on the synth |
| 3.4.11 | TUNER: hold UP, press TEMPO | window with track, note, cents, Hz; TEMPO, YES, NO or UP + TEMPO closes; TEMPO alone, FUNC + TEMPO stay stock |

## 4. MIDI and USB beyond the suite

| # | step | expected |
|---|---|---|
| 4.1 | CC MAP: send CC 102-107 and 108-111, 14, 15 on a track's channel from a controller | FX2 / FX1 page-2 slots 6-11 move |
| 4.2 | CC 64 (sustain) on a track's channel | no knob moves |
| 4.3 | CC FEEDBACK: a BCR2000 on the unit's MIDI out; change pattern, part, load a project, turn page-2 knobs | encoders follow, paced over about 3 s on a Kit change; no lock-up |
| 4.4 | MIDI loopback and MIDI thru as configured in BRAIN | as the module README |
| 4.5 | USB settings in BRAIN (TRACKS, MAIN, CUE, MASTER, IN) | channel count of the audio device changes; IN OFF by default |
| 4.6 | DIN MIDI clock and USB MIDI clock together | tempo pinned; USB audio unaffected (port test 28 Oct) |
| 4.7 | unplug and replug USB during play | the unit keeps playing; the host reconnects |
| 4.8 | an MKI and an MKII (both if available) | same results; record which |

## 5. Card and project

| # | step | expected |
|---|---|---|
| 5.1 | project load, 60 s of play, save, load again | files intact; no freeze at load (ATA WRITE GUARD: the failure was a hung LOAD PROJECT) |
| 5.2 | load and save each of SFX_01, SSCN, SDJ ten times | no hang; the card checks clean on the Mac |
| 5.3 | pre-remix project: `ot_project.py stamp-defaults <dir> octabam`, load | plays |
| 5.4 | back to stock ([BUILDING.md](../guide/BUILDING.md) section 8) | stock image boots; project loads |

## 6. Soak with hands off

| # | step | expected |
|---|---|---|
| 6.1 | SFX_01, the heaviest layout from the `fx` reports, 2 hours | audio continuous; LOAD METER healthy at 120 min |
| 6.2 | idle with the transport stopped, 1 hour | no tick, no freeze (`ot_soak.py` if the audio interface is attached) |

## Not run on any unit (1 Nov 2026)

The suite and this plan have not been run. Open from [HARDWARE_MATRIX.md](HARDWARE_MATRIX.md) and
`remixes/octabam/README.md`: nothing of the demand loader has run on a unit (the host write to the DSP, copying
into the window, the window's wait-state cost, the stock effects' buffer extents at other settings).
