# v0.6 unit checks: what was run, and what is left for the panel

The 16 items labelled `needs unit test` for v0.6, one row each. The expected results are the ones the PRs state;
a key sequence the PR does not give is not invented here: see the module's usage page
(`docs/site/usage/<module>.md`). Cable-driven runs use `tools/hw/ot_v06.py` ([HARDWARE_SUITE.md](HARDWARE_SUITE.md));
the manual plan for everything else is [HARDWARE_MANUAL.md](HARDWARE_MANUAL.md).

Tick a row when it passes; write the image, the unit (MKI or MKII) and the result beside it.

## Run over the cable (27 Nov 2026, one MKII)

| item | what ran | result |
|---|---|---|
| #1247, #1233, #1272 REMIX SWITCH | `ot_v06.py switch`: COMMAND 3 to the running image's own `.RMX`, idle unit, 22 switches without the USB reset, 170 with it (#1292) | 6 stops in 22 without; 3 in 170 with. MB_PARK 3 after every switch that returned. Open: one switch whose DSP never started (no REMOTE records from the new image), the `SYNCING PROJECT` hang (once), a boot-screen stall (twice) |
| #1255 FRAME GUARD | stalled-unit frame log, then the edge back to 110 µs (#1295) | the stalling entry was 135.6 µs late, below the 140 µs edge; with 110 µs, no stall in about 30 program changes (3 in about 30 at 140 µs). Not enough cycles to count |
| #1264 USB MIDI paused in DISK MODE | not run | needs CLOCK SEND on and the sequencer playing at COMMAND 1: `ot_v06.py diskread` (the suite loads `V06_DISK` for it) |

Not valid, do not read as passes: the matrix runs of #1219 (VCA160), #1232 and #1270 (WAVE, OCTA303), #1234
(VERBERATION) and #1263 (CX OSC). Every layout read the same as BASE, which a neutral-default effect also does, and
the machine layouts were not shown to differ. No effect or machine layout has been confirmed on the unit.

## Check by hand

### #1270 OCTA303 v10.0 and OCTA303 SEAM (image: `octabam`; SEAM only in `test/octa303-seam`)

- [ ] CUT, RES and ENV high: no 11.025 kHz whistle.
- [ ] ACCV over 64: no crack; the VCA does not clip or wrap.
- [ ] GATE 303: the first trig after PLAY sounds.
- [ ] dEVILish FM high with high RES and ENV: wild but pitched, not static. FM 0 unchanged.
- [ ] A FLEX track on a sample named `TB303*` now plays its sample; the OCTA-303 machine is the way in.
- [ ] Six tracks of OCTA-303: the ColdFire share in LOAD METER (v8.2 to v10.0 do less work for the same output).

### #1263 CX OSC (image: `cxosc`, or `V06-RIG`)

- [ ] DEC at HOLD (127), a note held, FOLD (PLAYBACK E) moved: no click or dropout.
- [ ] FOLD automated across frame-aligned trigs: no click.
- [ ] Six tracks with MOD morph at 0: ColdFire share (the PR reports 71.4 % mean, 73.6 % max); above 0 has not been measured.

### #1232 WAVE (image: `octabam`)

- [ ] A WAVE track with AMP at HOLD INF and REL INF, playing: STOP ends the voices (a single STOP; a double STOP).
- [ ] PLAY after it starts cold.
- [ ] A live note played with the transport already stopped is not cut.

### #1234 VERBERATION (image: `octabam-verbs`)

- [ ] STOP, STOP cuts the tail, as on the stock reverbs.
- [ ] AMNT: 0 to 64 the wet rises over the dry; 64 to 127 the dry fades out. Defaults 35, 41, 64 by mode.
- [ ] PRE works at every SIZE, including SIZE 127, and glides when turned.
- [ ] MODE is an algorithm: ROOM early reflections, PLATE unchanged, HALL modulated, 80S gates on each hit.
- [ ] Four VERBERATION on a core's FX2 slots plus four MODULATION on its FX1 slots: DSP busy under 95 % (the PR says about 94.6 %).

### #1219 KEYBUS and VCA160's KEY (image: `V06-RIG` or `test/vca160`; VCA160 is not in `octabam`)

- [ ] VCA160 on FX1 or FX2 with KEY set to a track T1 to T8: the gain follows that track's loudness.
- [ ] CHARACTER's KEY and VOID still read the peak.
- [ ] LOAD METER: KEYBUS adds about 11 cycles a sample per core.

### #1266 MIDI LOOPBACK with MIDI SCENES (image: `octabam`, `octabam-verbs`)

- [ ] A MIDI track set to INT (CHAN on its NOTE SETUP: EXT, INT or BOTH per Part): with a MIDI monitor on DIN and USB, neither its notes nor its scene CCs go out.
- [ ] EXT: both go out. BOTH: both go out and arrive internally.
- [ ] Scene CCs arrive before the note-on, locked or not.

### #1252 TEMPLATES FX tab and #1251 KIT templates (image: `octabam`)

- [ ] Tab order: KIT, FX, MIDI, PROJECT.
- [ ] NEW FX TEMPLATE in a Part: one record with the FX1 and FX2 ids and both pages of all eight tracks.
- [ ] APPLY TO FX in another Part: ids and values arrive on every track. Not measured before: non-zero ids.
- [ ] An id not in the image refuses with `EFFECT NOT IN IMAGE`. RENAME and DELETE work.
- [ ] On an FX1 or FX2 page FUNC lists SAVE FX DEFAULT and CLEAR FX DEFAULT only.
- [ ] KIT template: SRC pages of STATIC, FLEX, THRU, NEIGHBOR and PICKUP, and AMP pages 1 and 2. WHOLE KIT includes AMP; sample slots and levels are not carried.
- [ ] Each section alone (FROM Tn ONTO Tm), and the FLEX/STATIC and AMP group screens.

### #1250 and #1229 TEMPO BUS (image: `octabam-bus`, MKII keymap)

- [ ] FUNC+REC copies the window's values; FUNC+STOP pastes; a second FUNC+STOP undoes. Toasts BUS COPIED, BUS PASTED, UNDO.
- [ ] A copy made in one Part pastes into another. A box whose engine is on no track of the Part is skipped.
- [ ] With scene A or B held, FUNC+REC and FUNC+STOP do nothing. A knob turn in the window ends the undo. FUNC+UP and DOWN still step 0.1 BPM.
- [ ] With scene A or B held, A or B in the TEMPO window sets that scene's lock on the selected delay or reverb parameter; press and release the knob without turning to remove it; the rows show the locks while the scene is held.
- [ ] The window can be opened before or after the scene press. Pressing a scene with the window open writes no lock on the hidden page's knob A.
- [ ] Page 2 (MODE, TIME, TONE) locks are SCENES P2 cells. SCENES P2: with SCENE B held, a turn on an FX1 or FX2 SETUP page 2 writes a lock; the lock view follows the held scene.

### #1246 AED freeze (any unit)

- [ ] Build `octabam` through the browser builder at the reported commit, enter AED in a project: no freeze. Compare the image with a local build of the same commit. Reported on a browser-built 0.5 image only; unit model unknown.

### #1272 REMIX SWITCH on an MKI (needs an MKI)

- [ ] Switch remix repeatedly from BRAIN > REMIXES: the unit returns each time, not stopped on the boot screen. The `60 02` before the reset is sent on an MKI too since #1272; whether an MKI panel needs it is not confirmed.

### #1233 REMIX SWITCH with a stalled DSP

- [ ] With the DSP stopped (a stall, sequencer on step 1), choose a remix: the switcher shows `DSP STOPPED: REBOOT` and does not reset.
- [ ] A short card read at the load: `IO ERROR` and no boot.
