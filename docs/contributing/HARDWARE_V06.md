# v0.6 unit checks: what was run, and what is left for the panel

The 16 items labelled `needs unit test` for v0.6, one row each. The expected results are the ones the PRs state;
a key sequence the PR does not give is not invented here: see the module's usage page
(`docs/site/usage/<module>.md`). Cable-driven runs use `tools/hw/ot_v06.py` ([HARDWARE_SUITE.md](HARDWARE_SUITE.md));
the manual plan for everything else is [HARDWARE_MANUAL.md](HARDWARE_MANUAL.md).

Tick a row when it passes; write the image, the unit (MKI or MKII) and the result beside it.

## Run over the cable (27 Nov 2026, one MKII)

Per-track checks use the unit's USB audio (track `t` is channels `2t-2` and `2t-1`) and USB MIDI: `ot_v06_audio.py`,
`ot_v06_midi.py`. A project is loaded with `ot_card.py load`, which first moves the unit to bank H: leaving DISK MODE reloads
every bank but the current one, so a bank that is current keeps its old RAM (27 Nov 2026: edits to bank A never reached the
unit until this).

| item | what ran | result |
|---|---|---|
| #1247, #1233, #1272 REMIX SWITCH | `ot_v06.py switch`: COMMAND 3 to the running image's own `.RMX`, idle unit, 22 switches without the USB reset, 170 with it (#1292) | 6 stops in 22 without; 3 in 170 with. MB_PARK 3 after every switch that returned. Open: one switch whose DSP never started (no REMOTE records from the new image), the `SYNCING PROJECT` hang (once), a boot-screen stall (twice) |
| #1255 FRAME GUARD | stalled-unit frame log, then the edge back to 110 µs (#1295) | the stalling entry was 135.6 µs late, below the 140 µs edge; with 110 µs, no stall in about 30 program changes (3 in about 30 at 140 µs). Not enough cycles to count |
| #1232 WAVE STOP | WAVE on T1 and T2, AMP HOLD and REL INF by CC, STOP once and twice, the tail on T1 and T2 | fixed image: digital silence after STOP. Image from before the fix: T1 and T2 keep sounding at -34.9 dBFS, the playing level. The check sees the bug |
| #1263 CX OSC FOLD | CX OSC on T1 (the module's seeds, DEC at HOLD), FOLD static and swept 0 to 127 by CC, clicks on T1's channels | fixed image: 0 click events in 4 sweeps. Image from before the fix: 8, 16 and 14 events in 3 sweeps (static FOLD: 0). The check sees the bug |
| #1234 VERBERATION: AMNT | the dry hit and the wet on T6 at AMNT 0, 32, 64, 96, 127 | the dry holds to AMNT 64 (-0.2 dB), then -6.7 dB at 96 and -27.6 dB at 127; the wet is full from 64. As the PR states |
| #1234 VERBERATION: stop kill, PRE | tail after a single and a double MIDI STOP; PRE 0 against 127 | not shown. A single MIDI STOP already gives digital silence, so there is no tail to cut; after STOP, STOP every track holds a DC offset of about -77 dBFS (not in the PR). The PRE windows overlapped the impulse stimulus, which is a burst and not a click |
| #1219 VCA160 KEY | VCA160 on FX1 of T2 (steady noise), T1 hits every half second; the KEY knob swept by CC | KEY at the T1 position: T2's level follows T1's hits (correlation -0.72, T2's envelope range 23.5 dB); other positions and KEY untouched: no relation (about +0.03, 3 dB). Not run: CHARACTER's KEY and VOID still reading the peak; no image from before the change |
| #1266 MIDI LOOPBACK | MIDI track 1 (channel 11, trigs on steps 4, 8, 12, 16, a CC 1 scene lock), DEST EXT, INT, BOTH, crossfader swept, the unit's USB MIDI out counted | EXT and BOTH: 4 note-ons, 4 note-offs and 75 to 77 CCs on channel 11. INT: none of either. Not shown: INT's notes reaching the unit's own receiver; no image from before the change |
| #1270 OCTA303 v10.0 (PR branch merged onto main as `OCTABAM O3`; the images before are main's v7.1) | OCTA-303 on T1 and T2 with CUT, RES, ENV at 127: the 11.025 kHz bin over its band (9 to 13 kHz median) on T1; and with the accent knob at 127, ACCV 110 against ACCV 64: click events on T1 and clipped samples | the whistle: 23.0 and 20.2 dB on v7.1, 4.0 and 4.2 dB on v10.0. Not shown: the crack with ACCV over 64 (ACCV 110 and ACCV 64 give the same click counts on both images: 292 to 392 on v7.1, 116 to 246 against 138 to 152 on v10.0), clipping or wrapping (0 clipped samples on both). Not run: GATE 303's first trig after PLAY, dEVILish FM at high RES and ENV, the `TB303*` sample track now playing its sample, the ColdFire cost |
| #1264 USB MIDI paused in DISK MODE | CLOCK SEND on, `ot_v06.py diskread`: one 36 MB file read 6 times in 1 MB requests with the Mac's cache bypassed (`F_NOCACHE`), every 64 KB block compared across the reads | fixed image: 551 blocks x 6 reads, 0 differing, 0 with `0f f8 00 00`; the unit sent 131 clock bytes, all before COMMAND 1. Image from before the fix: 79 differing blocks, 65 with `0f f8 00 00` over the first word in one read only (2.0 % of 3,306), 662 clock bytes. 64 KB requests do not trigger it (0 differing on the old image) |

Every audio check plays once first and discards it: the first START after a project load is silent on every image.

## Check by hand

What the cable runs above did not cover: the panel gestures, and the parts of the cable rows marked not shown.

### #1270 OCTA303 v10.0 and OCTA303 SEAM, what the cable did not show (image: `octabam` with the PR; SEAM only in `test/octa303-seam`)

- [ ] ACCV over 64 on an accented step (an ACC lock on the step): no crack; the VCA does not clip or wrap.
- [ ] GATE 303: the first trig after PLAY sounds.
- [ ] dEVILish FM high with high RES and ENV: wild but pitched, not static. FM 0 unchanged.
- [ ] A FLEX track on a sample named `TB303*` now plays its sample; the OCTA-303 machine is the way in.
- [ ] Six tracks of OCTA-303: the ColdFire share in LOAD METER (v8.2 to v10.0 do less work for the same output).

### #1234 VERBERATION, what the cable did not show (image: `octabam-verbs`)

- [ ] STOP, STOP cuts the tail, as on the stock reverbs (a single MIDI STOP already gives silence on the cable, so a panel double STOP is the test).
- [ ] PRE works at every SIZE, including SIZE 127, and glides when turned (listen, or a single-click stimulus).
- [ ] MODE is an algorithm: ROOM early reflections, PLATE unchanged, HALL modulated, 80S gates on each hit.
- [ ] Four VERBERATION on a core's FX2 slots plus four MODULATION on its FX1 slots: DSP busy under 95 % (the PR says about 94.6 %).
- [ ] After STOP, STOP, a DC offset of about -77 dBFS is left on every track (seen on the cable): confirm it is inaudible.

### #1219 KEYBUS, what the cable did not show

- [ ] CHARACTER's KEY and VOID still read the peak.
- [ ] LOAD METER: KEYBUS adds about 11 cycles a sample per core.

### #1266 MIDI LOOPBACK, what the cable did not show (image: `octabam`, `octabam-verbs`)

- [ ] A MIDI track set to INT: its notes reach the Octatrack's own receiver (an audio track listening on the track's channel plays them).
- [ ] BOTH: out and internal at once.

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
