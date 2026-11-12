# MORPH

A track's scene morph, played by itself. Hold a track key and press **UP**: the MORPH window opens
and the track is armed. Turn A, B, C for STEPS, x, MODE. Release the track key: the window closes
and, on the next step, the track's scene morph runs by itself, scene A → B → A, one cycle every
**STEPS × x steps** (by default 16 × 8 = 128), starting on A. The other tracks keep the crossfader.
Hold the track key and press **DOWN**: the morph finishes its cycle on A and the track stays
**parked on A**; it follows the crossfader again once the crossfader reaches its A end, so nothing
jumps. The settings, and which tracks morph, are saved with the project.

Author: MaMarko (Marko Brajković, [braikomarko-hub](https://github.com/braikomarko-hub)): the idea,
the listening and the tests on the unit. **The code was written by Claude (Anthropic)**: engine,
window, saving, integration and gates.

Inspired by the Korg Electribe's Motion Sequence
(https://support.korguser.net/hc/en-us/articles/205917700-Motion-sequence): there the knob moves
are recorded; here the movement is the ramp between the two scenes the Octatrack already has.

Markers: ✅ measured, 🟡 inferred.

## Using it

| keys | what happens |
|---|---|
| [TRACK] + [UP] | the MORPH window for the held tracks; they are armed (ARM) |
| release the track keys | the window closes; the armed tracks start from A on the next step |
| [TRACK] + [UP] on a morphing track | the window over the running morph: changes apply at once, the morph goes on |
| [TRACK] + [DOWN] | stop, on every held track: a morphing one finishes its cycle on A, then is parked on A; an armed one goes back to the crossfader |
| crossfader to its A end | a parked track follows the crossfader again |
| [STOP] | the morph holds where it is; [PLAY] carries on |

Several tracks can morph at once, each from the step after its own start (not from the bar), each
with its own settings.

The window (hold several track keys and it is for all of them):

```
 MORPH            T1        the window's tracks
 ──────────────────────
  MORPH           ARM       ARM (in the window) / WAIT (next step) / ON / STOP (finishing) / PARK
  STEPS (A)        16       encoder A: TRK (the track's length), 1..64
  x (B)             8       encoder B: 1..16
  MODE (C)     SMOOTH       encoder C: SMOOTH / HOLD (TRIG HOLD)
  CYCLE 128 STEPS           STEP 12 / 128 while morphing
```

| in the window | what happens |
|---|---|
| A, B, C | STEPS, x, MODE on every window track |
| DOWN | stop, as [TRACK] + [DOWN] |
| NO, UP, or releasing the track keys | the window closes; an armed track starts on the next step, a morphing one goes on |
| YES | nothing (under a held track key stock would arm recording) |

| setting (per track) | values | default |
|---|---|---|
| STEPS | 0 = TRK, the track's length in the current pattern; 1..64 | 16 |
| x | 1..16: one cycle is STEPS × x steps (at most 1024) | 8 |
| MODE | SMOOTH: the morph moves every frame. HOLD (TRIG HOLD): the step's value for the whole step | SMOOTH |

At x 16, keep turning B to the right and it gives in: **41.625** (16 × 41.625 = 666 steps). Left
goes back to 16.

## Saving

✅ (on the unit, MRPPR1, and in the source simulator) The settings of the eight tracks and which tracks morph go to `morph.work` in
the project directory, beside the bank files, when the Octatrack writes its banks and when the
project is saved; SAVE PROJECT copies it to `morph.strd` and RELOAD brings that copy back, as MIDI
SCENES keeps `scenes.work`. MORPH is a client of STORE (`modules/store`), which holds those sites.

- A project with no `morph.work` (never morphed, or made before MORPH) loads the defaults, and no
  file is written until something changes.
- At a project load (and at power-up) the tracks that were morphing are armed: they start from A
  on the first step after PLAY. A track that was stopping or parked is parked on A.
- A `morph.work` that is not version 1 or fails its CRC is never written over: STORE lists it
  (MORPH SETTINGS NOT LOADED) and offers to keep it, start fresh, or back it up to `morph.bak`
  first.
- File: `MRPW`, version 1, payload length 40, CRC-32 of the payload; the payload is the eight
  tracks' STEPS, x, MODE and a pad byte, one byte of the tracks that morph (bit t), seven zero
  bytes.

## How it works

- ✅ **The weight per track.** The scene morph takes, for each track, a long at
  `0x80003c60 + 4·t`: the high word weights scene A's value, the low word scene B's (the both-scenes
  path at `0x4000ce60`). Only the crossfader writes them (`0x40061e2e`, `0x400626a8`), from the
  curve at `0x400bcd90` (`w = curve[xf]`, `0` … `−32768`; weight `= (w << 16) | ((0xffff8000 − w) &
  0xffff)`); xf 127 is all A, 0 all B. MORPH computes the same word from its own xf.
- ✅ **When.** A detour at `0x4000cc62` (`move.l #96,%macsr ; lea 12(%sp),%sp`, both replayed) runs
  once a frame in the frame builder, after its per-track loop and before `0x4000cc6c`, where all six
  paths that read the weights begin. No branch in the image lands inside the 10 bytes. It writes the
  weight of every morphing or parked track, so a crossfader move, which rewrites all ten, is
  undone for those tracks before the morph reads them.
- ✅ **The clock.** The cycle counts the sequencer's steps: every frame the step word
  `0x800065b2` (OCTA303's 303 gate reads it on the unit) is compared with the last frame's; a
  change is a step (a jump of more than 8, a restart or a pattern change, counts as one), and the
  frames since the last step are counted while the transport word `0x800065b8` is 1. A track's k is
  its steps since the cycle began; the triangle position is `(k · 256 + f) / N`, 0..255, folded
  into xf 127 → 0 → 127, where f is the fraction of the current step that has gone (SMOOTH:
  `frames × tempo24 × 4329 >> 24`, at most 255; TRIG HOLD: 0). So TRIG HOLD changes exactly on the
  steps, SMOOTH moves every frame, and neither drifts from the pattern over many cycles. One
  division a frame per morphing track; with every track on the fader only the step-word compare
  runs.
- ✅ **STEPS 0** reads the track's length in the current pattern (bank blob `0x46c82456` + pattern
  `0x100b14d0` × `0x8ed8` + track × `0x91a`, the byte at `+0x50`, 1..64, else 16), as OCTA303's gate
  does, every frame: a pattern change is followed; a k past the new N starts again from A.
- 🟡 **The fraction of a step** assumes the frame builder runs once per 16-sample frame at 44.1 kHz
  (363 µs; a step is `992,250 / tempo24` frames). If it did not, SMOOTH would still land on every
  step (the clock is the step word) and only the motion inside a step would be uneven. 🟡 That the
  step word counts every 16th of the master length while playing.
- ✅ **The keys.** Holding a track key pushes the layer `0x400d164a`, whose table `0x400d1594` has
  six records (STOP, PLAY, BANK, YES, NO, 0x18) and a terminator; UP and DOWN are not in it, so
  stock passes them to the layer below. MORPH carries a copy of the table with UP (`0x33`) and DOWN
  (`0x20`) added, and the layer's keys field `0x400d164e` points at it. The handlers follow stock's
  convention (`handler(keycode, event)`, event 1 = press; Zac Kyoti's REC_TRIG_MUTE uses the same
  table).
- ✅ **The window** has the structure of ilia-murzinov's SEQ (`modules/seq`): a
  TEMPO-class window (`0x4005829c` create, `0x40056f4c` frame, `0x40055db4` destroy, class 5:
  another TEMPO-class window takes its place and closes it), an input layer pushed over everything
  while it is open (YES, NO, UP, DOWN; encoders A, B, C; `0x40031494` / `0x4003146c`), the stock
  text, width and rule routines, y counted up from the bottom. The close on release is a soft timer
  (`0x40031a0c`, two ticks, ~17 ms, as BRAIN's screens use it) that reads the held track keys and
  repaints when the first track's state or step changed; a release handler cannot do it, since the
  held track key keeps the handlers it had when the layer was pushed (`docs/firmware/MAINMENU.md`
  section 6c). Closing the window, however it closes, starts its armed tracks.

## Limits

- **MIDI tracks follow the crossfader, not MORPH**: MIDI SCENES morphs them from the crossfader
  position. SCENES P2 reads the weights after the stock morph and follows MORPH.
- Select parameters (MODE, WAVE…) jump at the middle of the morph, as with the crossfader.
- [TRACK] + [UP]/[DOWN] replace what UP/DOWN did while a track key is held (stock: the layer below,
  e.g. a list's cursor); [YES] inside the window does nothing.
- Beside REC_TRIG_MUTE (both change the [TRACK]-layer table) the registry adds
  [HOOKS](../hooks/README.md), whose one table carries MORPH's UP/DOWN and REC_TRIG_MUTE's
  YES/NO; MORPH's own copy is then not read. Under Unicorn only (verify_hooks); not flashed.
- A track's own scale (×2, ½) is not followed: a step is the master 16th.
- 🟡 A masked bank load other than a project load or the power-up (STORE names reloads) reads
  `morph.work` again, so a running morph would be armed again from A.
- No message at a project load says which tracks will morph (the window shows it); a toast from
  the load, which runs in the engine task, is not a place stock draws from.

## Measured

- ✅ On the owner's MKI, image MRPPR1 (BUILD 98, remix `morph`, from `374d4515`), the owner's MKI, 23 Oct 2026: the window armed while T1 is held and CYCLE following A and B; YES does nothing; the start on the release; the window over a running morph (changes at once, the morph goes on); 41.625 and CYCLE 666 STEPS; T1 and T5 with different settings, SAVE PROJECT, power off and on, PLAY: both start from A with their settings; a change without saving undone by PROJECT > RELOAD; another project with no morph.work on the fader with the defaults, and back to the first: T1 and T5 armed again; TRACK + DOWN ends the cycle on A. By ear and eye.
- ✅ On the owner's MKI, image ACIDV74MP (aCiDtRacK + MORPH), 22 Oct 2026, by ear and eye: the
  window ([TRACK] + [UP], STEPS / x / MODE on A, B, C), the morph at the tempo over STEPS × x
  steps, SMOOTH and TRIG HOLD, several tracks at once (T5 with OCTA303 and T6 on a NEIGHBOR
  machine), STOP / PLAY, [TRACK] + [DOWN] parking on A, the crossfader taking the track back at
  its A end. That image still had YES to start and x up to 8.
- ✅ v0 on the same unit, image ACIDV73MP, 21 Oct 2026: [TRACK] + [UP] runs the track's morph,
  the others keep the fader, [TRACK] + [DOWN] parks it on A.
- ✅ Under the port (`tools/morph/port_morph.py`, with a project, 22 Oct 2026, on the YES form): the
  window opens and draws, the encoders set STEPS 8 and x 2, the morph starts from A and runs at
  the tempo (xf 35 after ~5.6 steps of a 16-step cycle, ~38 expected), T2 keeps the fader, STOP
  holds, PLAY carries on, [T1] + [DOWN] ends parked on A, TRIG HOLD gives one value a step.
- ✅ `tools/morph/test_morph.py`: `morph.s` executed from its source text in OCTA303's source
  simulator (`tools/octa303/sim/cfsim.py`, with its ColdFire lint), against a mock of the firmware
  addresses, a mock sequencer moving the step word at the tempo, and mocks of STORE's file calls:
  the arming in the window and the start on the release; B at step 64 and A again at step 128
  (16 × 8); one xf step per frame at most (SMOOTH) and the triangle's value on each step's first
  frame; TRIG HOLD one value per step; STEPS 0 = the track's length; 512 and 1 steps; the transport
  stop; stop on A, parking, re-attach; x to 16 and 41.625 (a 666-step cycle at STEPS 16); the
  window's paint, encoders, YES swallowed, closing on release, twice, on eviction; saving:
  nothing written for an untouched project, the file's bytes and CRC, no rewrite when nothing
  changed, the copy to `.strd`, the load (settings back, the morphing tracks armed, the others
  parked or on the fader), RELOAD from `.strd`, a bad CRC refused and never written over, the
  BACKUP answer, a project without the file. Not covered: the hook under the real firmware, MACSR
  (the simulator has none), STORE's real file calls.

## Credits

- Korg, the Electribe's Motion Sequence: the idea.
- Zac Kyoti, REC_TRIG_MUTE (`modules/rec-trig-mute`): the [TRACK]-held layer, its handler
  convention and the toast call.
- ilia-murzinov, SEQ (`modules/seq`): the window's structure, its firmware calls and
  their argument orders, the right-aligned text idiom.
- sambanks, STORE (`modules/store`), and MIDI SCENES' storage (`modules/midi-scenes`,
  bkkbrls-del/midisc): the side file beside the bank files, its `.strd` copy, the refusal and its
  answers.
