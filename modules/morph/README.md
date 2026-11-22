# MORPH

A track's scene morph, played by itself. Hold a track key and press **UP**: the MORPH window opens
for that track. Turn A, B, C for STEPS, x, MODE; the window stays open when you let go of the track
key. **YES**: the window closes and, on the next step, the track's scene morph runs by itself,
scene A → B → A, one cycle every **STEPS × x steps** (by default 16 × 8 = 128), starting on A. The
other tracks keep the crossfader. **NO**: the window closes and nothing starts. Either way the track
is now **ARMED**: hold its track key alone for about a second and its morph starts; hold it again
and the morph finishes its cycle on A and stops. That works on the MIXER page too, where the trig
keys mute the tracks. Hold the track key and press **DOWN**: the morph finishes its cycle on A and
the track stays **parked on A**; it follows the crossfader again once the crossfader reaches its A
end, so nothing jumps. The settings, which tracks morph and which are armed are saved with the
project.

**v1.2** adds the way back, on encoders D, E, F: **RET** (how long B → A takes: as long as the way
up, a fraction of it, a bar, a beat, a step, or a cut), **CURV** (LIN, HAND: the way back fast at
first and soft at the end, as a hand pulls a fader; RISE: the way up slow at first; BOTH) and
**END** (LOOP, ONCE: one cycle, then parked on A; **STAY**: up to B and held there until you hold
the track key ~1 s, or press [TRACK] + [DOWN], then back to A over RET). Made for risers: set the
rise, let it climb while you prepare the rest, then let it fall back as if by hand. All three at
their first value (SAME, LIN, LOOP) are v1.1 exactly.

Author: MaMarko (Marko Brajković, [braikomarko-hub](https://github.com/braikomarko-hub)): the idea,
the listening and the tests on the unit. **The code was written by Claude (Anthropic)**: engine,
window, saving, integration and gates.

Inspired by the Korg Electribe's Motion Sequence
(https://support.korguser.net/hc/en-us/articles/205917700-Motion-sequence): there the knob moves
are recorded; here the movement is the ramp between the two scenes the Octatrack already has.

Markers: measured, inferred.

## Using it

| keys | what happens |
|---|---|
| [TRACK] + [UP] | the MORPH window for the held tracks (ARM); it stays open when the keys are let go |
| YES (in the window) | the window closes; the window's tracks start from A on the next step |
| NO or UP (in the window) | the window closes; nothing starts |
| [TRACK] held ~1 s alone, on an armed track | not morphing: it starts from A on the next step (toast T2 MORPH ON). Morphing: it finishes its cycle on A and stops, parked on A (T2 MORPH OFF). END STAY, held on B (TOP): the way back starts on the next step (T2 MORPH OFF) |
| [TRACK] + [UP] on a morphing track | the window over the running morph: changes apply at once, the morph goes on |
| [TRACK] + [DOWN] | stop, on every held track: a morphing one finishes its cycle on A, then is parked on A; one waiting for its step goes back to the crossfader; one held on B (STAY) starts its way back on the next step; one still going up with STAY comes back as soon as it reaches B |
| crossfader to its A end | a parked track follows the crossfader again |
| [STOP] | the morph holds where it is; [PLAY] carries on |

A track is **armed** once it has been in the window (YES or NO); the long press does nothing on a
track that never was. The long press works on the main pages and on the MIXER page; FUNCTION or
CUE held with the track key (mute, cue), another key pressed meanwhile, MIDI mode or the MORPH
window open: no long press, stock keeps the keys. Several tracks can morph at once, each from the
step after its own start (not from the bar), each with its own settings.

The window (hold several track keys and it is for all of them):

```
 MORPH  T1                 ARM      the window's tracks; ARM (in the window) / WAIT (next step) / ON
                                    / STOP (finishing) / PARK / TOP (held on B) / RET (on the way back)
  CYCLE 128           01▸09         STEP 12/128 while morphing, BACK 2/4 on the way back after STAY;
                                    the scenes, as on the main page
  STEPS (A)                 16      encoder A: TRK (the track's length), 1..64
  x (B)                      8      encoder B: 1..100
  MODE (C)              SMOOTH      encoder C: SMOOTH / HOLD (TRIG HOLD)
  RET (D)                 SAME      encoder D: SAME 1/2 1/4 1/8 1/16 BAR BEAT STEP CUT
  CURV (E)                 LIN      encoder E: LIN HAND RISE BOTH
  END (F)                 LOOP      encoder F: LOOP ONCE STAY
```

The right of the second row is the scene indicator of the main page's footer, drawn by the same
firmware calls: scene A, the position between them, scene B (v1.1 drew it at the bottom; v1.2
needs the rows: eight rows 7 pixels apart inside v1.1's y 3..58, no rule under the title, the state
at the title's right, the indicator beside the step). Its position
is the window track's own: where its morph is while it morphs, A while it is parked, else the
crossfader's.

| in the window | what happens |
|---|---|
| A, B, C | STEPS, x, MODE on every window track |
| D, E, F | RET, CURV, END on every window track, one value a click (v1.1 let them through to the page under the window) |
| YES | close; the tracks start on the next step |
| NO, UP | close; nothing starts |
| DOWN | stop, as [TRACK] + [DOWN] |

| setting (per track) | values | default |
|---|---|---|
| STEPS | 0 = TRK, the track's length in the current pattern; 1..64 | 16 |
| x | 1..100: one cycle is STEPS × x steps (at most 6400) | 8 |
| MODE | SMOOTH: the morph moves every frame. HOLD (TRIG HOLD): the step's value for the whole step | SMOOTH |
| RET | the way back B → A: SAME (as long as the way up, v1.1), 1/2, 1/4, 1/8, 1/16 of the way up, BAR (16 steps), BEAT (4), STEP (1), CUT (none) | SAME |
| CURV | LIN; HAND: the way back fast at first, soft at the end; RISE: the way up slow at first, fast at the end; BOTH | LIN |
| END | LOOP: again and again; ONCE: one cycle, then parked on A; STAY: up to B and held there (TOP), back over RET when asked | LOOP |

The way up is always half of STEPS × x (64 steps at 16 × 8); RET sets only the way back, so a
shorter RET makes the cycle shorter: 16 × 8 with RET 1/4 is 64 up + 16 back = 80 steps. When the
two do not add up to whole steps (a way back of 1/16 of 1 × 1, say) the morph stays on A for
what is left of the cycle's last step.

## Saving

 (on the unit, MRPPR1, and in the source simulator) The settings of the eight tracks and which tracks morph go to `morph.work` in
the project directory, beside the bank files, when the Octatrack writes its banks and when the
project is saved; SAVE PROJECT copies it to `morph.strd` and RELOAD brings that copy back, as MIDI
SCENES keeps `scenes.work`. MORPH is a client of STORE (`modules/store`), which holds those sites.

- A project with no `morph.work` (never morphed, or made before MORPH) loads the defaults, and no
  file is written until something changes.
- At a project load (and at power-up) the tracks that were morphing are armed: they start from A
  on the first step after PLAY. A track that was stopping or parked is parked on A.
- A `morph.work` that is not version 1, 2 or 3 or fails its CRC is never written over: STORE lists it
  (MORPH SETTINGS NOT LOADED) and offers to keep it, start fresh, or back it up to `morph.bak`
  first.
- File: `MRPW`, version 2 (v1.1; v1 wrote version 1), payload length 40, CRC-32 of the payload;
  the payload is the eight tracks' STEPS, x, MODE and a pad byte, one byte of the tracks that
  morph (bit t), one byte of the armed tracks (0 in version 1), six zero bytes. A version 1 file
  loads with nothing armed and its 41.625 (x byte 17) as x 42. v1 firmware refuses a version 2
  file (and never writes over it).
- v1.2: version 3, payload length 72: the same 40 bytes, then the eight tracks' RET, CURV, END
  and a pad byte. It is written only when one of those is not at its first value; otherwise the
  file is version 2, as v1.1 writes it, so going back to a v1.1 image keeps the project unless
  the new settings were used (v1.1 refuses version 3, keeps the file and asks). A track held on
  B (STAY) is saved as morphing: at the next load it is armed and rises again from A.

## How it works

- **The weight per track.** The scene morph takes, for each track, a long at
  `0x80003c60 + 4·t`: the high word weights scene A's value, the low word scene B's (the both-scenes
  path at `0x4000ce60`). Only the crossfader writes them (`0x40061e2e`, `0x400626a8`), from the
  curve at `0x400bcd90` (`w = curve[xf]`, `0` … `−32768`; weight `= (w << 16) | ((0xffff8000 − w) &
  0xffff)`); xf 127 is all A, 0 all B. MORPH computes the same word from its own xf.
- **When.** A detour at `0x4000cc62` (`move.l #96,%macsr ; lea 12(%sp),%sp`, both replayed) runs
  once a frame in the frame builder, after its per-track loop and before `0x4000cc6c`, where all six
  paths that read the weights begin. No branch in the image lands inside the 10 bytes. It writes the
  weight of every morphing or parked track, so a crossfader move, which rewrites all ten, is
  undone for those tracks before the morph reads them.
- **The clock.** The cycle counts the sequencer's steps: every frame the step word
  `0x800065b2` (OCTA303's 303 gate reads it on the unit) is compared with the last frame's; a
  change is a step (a jump of more than 8, a restart or a pattern change, counts as one), and the
  frames since the last step are counted while the transport word `0x800065b8` is 1. A track's k is
  its steps since the cycle began; the triangle position is `(k · 256 + f) / N`, 0..255, folded
  into xf 127 → 0 → 127, where f is the fraction of the current step that has gone (SMOOTH:
  `frames × tempo24 × 4329 >> 24`, at most 255; TRIG HOLD: 0). So TRIG HOLD changes exactly on the
  steps, SMOOTH moves every frame, and neither drifts from the pattern over many cycles. One
  division a frame per morphing track; with every track on the fader only the step-word compare
  runs.
- (source simulator) **The way back (v1.2).** The cycle is counted in 1/256 steps: the way up
  is L = N × 128 (N = STEPS × x), the way back T = N × 128 >> RET for SAME .. 1/16, 4096 (BAR),
  1024 (BEAT), 256 (STEP) or 0 (CUT); the cycle is C = ⌈(L + T) / 256⌉ steps (STAY: ⌈L / 256⌉).
  At pos < L the way up: v = pos · 256 / L, xf = 127 − v / 2 (RISE: v² / 512); after it the way
  back: u = (pos − L) · 256 / T (at most 255), xf = u / 2 (HAND: 127 − (255 − u)² / 512). With
  SAME and LIN these are v1.1's `x = pos / N` folded at 128, step for step (floor identities:
  `⌊⌊2p/N⌋/2⌋ = ⌊p/N⌋`), which is why the defaults change nothing. Three new states: TOP (7,
  held on B), RETW (8, the way back asked, waiting for the next step) and RET (9, on the way back,
  then parked on A). Two divisions a frame per morphing track at most.
- **STEPS 0** reads the track's length in the current pattern (bank blob `0x46c82456` + pattern
  `0x100b14d0` × `0x8ed8` + track × `0x91a`, the byte at `+0x50`, 1..64, else 16), as OCTA303's gate
  does, every frame: a pattern change is followed; a k past the new N starts again from A.
- Unconfirmed: **The fraction of a step** assumes the frame builder runs once per 16-sample frame at 44.1 kHz
  (363 µs; a step is `992,250 / tempo24` frames). If it did not, SMOOTH would still land on every
  step (the clock is the step word) and only the motion inside a step would be uneven. That the
  step word counts every 16th of the master length while playing.
- **The keys.** Holding a track key pushes the layer `0x400d164a`, whose table `0x400d1594` has
  six records (STOP, PLAY, BANK, YES, NO, 0x18) and a terminator; UP and DOWN are not in it, so
  stock passes them to the layer below. MORPH carries a copy of the table with UP (`0x33`) and DOWN
  (`0x20`) added, and the layer's keys field `0x400d164e` points at it. The handlers follow stock's
  convention (`handler(keycode, event)`, event 1 = press; Zac Kyoti's REC_TRIG_MUTE uses the same
  table).
- **The window** has the structure of ilia-murzinov's SEQ (`modules/seq`): a
  TEMPO-class window (`0x4005829c` create, `0x40056f4c` frame, `0x40055db4` destroy, class 5:
  another TEMPO-class window takes its place and closes it), an input layer pushed over everything
  while it is open (YES, NO, UP, DOWN; encoders A, B, C; `0x40031494` / `0x4003146c`), the stock
  text, width and rule routines, y counted up from the bottom. A soft timer (`0x40031a0c`, two
  ticks, ~17 ms, as BRAIN's screens use it) repaints when the first track's state, its step or the
  scene indicator changed. v1.1: it stays open after the release; YES closes it and starts its
  held tracks, NO, UP or another TEMPO-class window closes it and starts nothing (a track that was
  parked is parked again); either way its tracks are armed for the long press.
- (port,) **The scene indicator** is the main page footer's: `0x4004d640` sets two
  boxes (`0x40012254` mode 1) x 95..103 and 109..117, y 0..6, and writes scene A and scene B (the
  bytes at bank + part × `0x18b2` + `0x8ed90` / `0x8ed91`, part `0x80000003`, shown from 1) with
  `0x40013904` (the small font, x `0x60` / `0x6e`, y 1, `"%02d"` `0x400b437c` in the width of
  `"00"` `0x400b4382`, inverted); `0x4003577c` sets the box x 104..108, y 0..6, clears y 2..4 and
  draws the 5 × 3 sprite `0x400bcd7c[4 - ((xf + 16) >> 5)]` (0..4) at (104, 2). The window makes
  the same calls 6 to the left and 3 up; on the port its pixels equal the footer's.
- (port,) **The long press** is TRACK MENU's (measured on the owner's MKI, 24 Oct):
  the PRESS field of T1..T8 in the MKI key table `0x400bfc10` and the MKII one `0x400c01f4`
  (stock `0x40040250`) points at `lp_tpress`, which calls stock first, then counts ~1 s with a soft
  timer while that track key stays the only key down (`HELD` and the panel rows `0x46100b18`). The
  MIXER page leaves that table in place: the long press works there too. The toast is stock's
  (`0x4005a2b8`).

## Limits

- **MIDI tracks follow the crossfader, not MORPH**: MIDI SCENES morphs them from the crossfader
  position. SCENES P2 reads the weights after the stock morph and follows MORPH.
- Select parameters (MODE, WAVE…) jump at the middle of the morph, as with the crossfader.
- [TRACK] + [UP]/[DOWN] replace what UP/DOWN did while a track key is held (stock: the layer below,
  e.g. a list's cursor).
- A track key held alone for a second on an armed track toggles its morph at once (with its
  toast). If that same hold then becomes [TRACK] + [UP] or [TRACK] + [DOWN] (a slow combination),
  the toggle is taken back before the window opens or the stop applies; the toast has already
  been shown. Other slow [TRACK] combinations (YES, NO, PLAY, BANK) keep the toggle.
- Opening the window on a track that is finishing its cycle (STOP) lets it carry on morphing, as
  in v1; NO does not stop it again ([TRACK] + [DOWN] does).
- Beside REC_TRIG_MUTE (both change the [TRACK]-layer table) the registry adds
  [HOOKS](../hooks/README.md), whose one table carries MORPH's UP/DOWN and REC_TRIG_MUTE's
  YES/NO; MORPH's own copy is then not read. Under Unicorn only (verify_hooks); not flashed.
  YES and NO inside the open window belong to the window's own key layer, not the [TRACK]
  layer, and the long press is on the T1..T8 key records, so neither goes through HOOKS.
- A track's own scale (×2, ½) is not followed: a step is the master 16th.
- Unconfirmed: A masked bank load other than a project load or the power-up (STORE names reloads) reads
  `morph.work` again, so a running morph would be armed again from A.
- No message at a project load says which tracks will morph (the window shows it); a toast from
  the load, which runs in the engine task, is not a place stock draws from.

## Credits

- Korg, the Electribe's Motion Sequence: the idea.
- Zac Kyoti, REC_TRIG_MUTE (`modules/rec-trig-mute`): the [TRACK]-held layer, its handler
  convention and the toast call.
- ilia-murzinov, SEQ (`modules/seq`): the window's structure, its firmware calls and
  their argument orders, the right-aligned text idiom.
- sambanks, STORE (`modules/store`), and MIDI SCENES' storage (`modules/midi-scenes`,
  bkkbrls-del/midisc): the side file beside the bank files, its `.strd` copy, the refusal and its
  answers.
