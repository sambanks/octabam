# `usb-midi-tracks` -- USB MIDI TRACKS

Each audio track's trigs as USB MIDI, USB only (nothing goes to the DIN
port). Requires USB MIDI, whose transmit queue it calls.

For every START on T1..T8 (a sequencer trig, a panel key or a MIDI IN note:
they share one funnel) it sends, on MIDI channel = track number:

| message | data |
|---|---|
| CC 16 | PTCH, raw 4..124, 64 = unpitched, 5 = a semitone (+/-12) |
| CC 17 | STRT, raw: with SLIC ON the slice, raw/2 + 1 |
| CC 18 | LEN |
| CC 19 | RATE |
| CC 20 | RTRG, raw: the panel shows raw + 1, 127 = INF |
| CC 21 | RTIM |
| note-on, velocity 100 | note = the playing sample's slot, 0..127 |
| note-off, a fixed 160 frames (about 58 ms) later | a new START closes a pending note first |

The six are PLAYBACK page 1, with stock's numbers and raw values (the ones the
unit sends on a turn and CC FEEDBACK sends). They are read from the frame's
parameter record, not the live lane, so each carries what the voice gets at that
note: the trig's locks, the crossfader's morph between scenes, and an LFO on the
knob. SLIC has no CC: it is the page-2 ON/OFF switch, and the slice is chosen with
STRT. Until 3 Nov 2026 this module sent PTCH on CC 20 and SLIC on CC 21, which are
RTRG and RTIM everywhere else.

Each retrig repeat is the same thing again: the note-off if the gate has not
run out yet, then the six CCs and the note-on. A scene or the crossfader moving
RTRG or RTIM is followed, because nothing is latched here: one repeat of the
audio is one note. RTRG shows raw + 1, so the panel's minimum 1 is raw 0, one
play and no repeat. A voice started at exactly that value gets no repeats, in the
audio too, even if the fader then raises RTRG (the renderer latches a zero
count); with the fader even slightly off that end at the trig the morph works.

Constants (`CC_FIRST`, `VEL`, `GATE_FRAMES`) are `.set`s at the top of `utm.s`.

## How it hooks

No detour. The kind table's FLEX and STATIC renderer entries (`0x400d6438`,
`0x400d6434`, stock `0x40004008`) point at `utm_render`, which does its work
and tail-jumps to the stock renderer. The packer calls a track's renderer
twice a frame and runs the start handler between the calls, so on the second
call of a start frame (bit 4 of the nibble byte `0x46104d0c[t]`) the voice
struct holds the new sample's record, and the call comes every frame, which
times the gate. SYNTH MACHINE repoints the same entries, so the ledger
refuses the pair.

(A first version hooked the command-byte copy at `0x4000c634`: measured under
the port it ran once, at the START only, and the sample record was still the
previous one's, 0 on a first trig.)

Repeats: the operand of the stock renderer's `jsr 0x4000f450` at `0x4000421c`
(`0x4000421e`) points at `utm_retrig`, which sends and tail-jumps to the handler.
The renderer makes that call once per repeat and only for a repeat: the packer's
own START reaches `0x4000f450` through its table at `0x400d6454`.

The message batch goes through `usbmidi_tx_append` (len in d0, buffer in a0),
exported from `usbmidi.s` by one `.global` line: no byte of the linked unit
changes, so its `reference` hash still holds.

## On a unit (MKII, 15 Nov 2026)

Owner report, seen on the host over USB MIDI: CC 16..21 for every value on
PLAYBACK page 1, a note for each trig, retrig repeats, and the CCs following
the crossfader between scenes. Nothing on the unit was timed or counted: the
gate length, repeat spacing, `usbmidi_tx_drops` and the INF burst are port
numbers only.

## Measured (under the port, 3 Nov 2026)

With `tools/verify/probe_usbmidi_tracks_project.py`, on two real projects with
one generated WAV behind every sample slot:

- Notes match the bank data (lock slot 31 = sample slot), note-offs pair, the six
  CCs arrive with each note-on (their order in the stream is not asserted).
- Trig locks on PTCH, STRT, LEN, RATE, RTRG, RTIM: every CC reads the lock of its own
  trig, repeats included, fader on the unlocked scene end.
- A scene on five knobs plus RTRG with the fader sweeping: all six move with the
  fader note by note. Stock's rest position under the port is the middle
  (0x460d16c8 = 64): the test project's scene B locks T1 RATE to 0, so a RATE
  lock of 120 reads 60 there, 120 at the scene A end and 0 at the B end.
- RTRG raw 3 (panel 4) locked, RTIM 4 and 110: every trig gives 3 repeats, 4 note-ons, 4 note-offs
  (110 has the gate close between repeats).
- A real scene (RTRG raw 1 on scene A, 5 on scene B) with the crossfader sweeping
  during the bursts, RTIM 72: repeats moved with the live fader in both
  directions after the count was latched (latched 1: 2 repeats; latched 4: 2
  repeats). Channel 1 read 90 note-ons, 90 note-offs.
- Repeat spacing measured against RTIM: 4 -> about 35 samples, 72 -> 1776, 90 -> 5040,
  doubling every 12 RTIM. Bank 10 of the test project, tempo not read: it may
  scale this.
- RTRG raw 127 (INF), RTIM 4: 4465 repeats in about 3.5 s, each 24 bytes,
  `usbmidi_tx_drops` 0. The port's host is not a real host's scheduler.

## Inferred and to be measured

- An LFO on one of the six is in the CC (`docs/firmware/LFO.md`: it writes the same
  record). Read from the code, no test project has one.
- A track on another machine is not hooked for STARTs. PICKUP shares the stock
  renderer, so `utm_retrig` does run there; a recorder buffer's record gives no
  note. Not run.
- A START from the panel sends notes as well as a sequencer trig.
- The encoder is entered from the frame interrupt, in `utm_render` as in
  `utm_retrig`; `usbmidi.s`'s own senders run from task context. Measured only
  under the port. A batch that overflows `TX_CAP` is dropped whole, its
  note-off with it.
- Audio onsets: the repeats are read from the renderer's state and calls, not yet
  heard in the port's audio (`probe_usbmidi_retrig_audio.py` read silence, cause
  not checked since the fixture fix below).

## Open

- AMP page CCs (22..27, the voice record). FX are out of scope.
- Gate length from the trig or AMP HOLD, rather than fixed.
- Sharing the site with SYNTH MACHINE (a chained detour).
