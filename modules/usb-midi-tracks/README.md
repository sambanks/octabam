# `usb-midi-tracks` -- USB MIDI TRACKS

Each audio track's trigs as USB MIDI, USB only (nothing goes to the DIN
port). Requires USB MIDI, whose transmit queue it calls.

Stock sends MIDI notes for [TRIG] key presses only (AUDIO NOTE OUT), and
CC 16..21 when a knob moves (AUDIO CC OUT); it sends nothing for a sequencer
trig. This module fills that gap. For every START on T1..T8 (a sequencer
trig, a panel key or a MIDI IN note: they share one funnel) it sends, on the
track's **TRIG CHANNEL** (PROJECT > MIDI > CHANNELS; OFF sends nothing, as
stock does):

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

## The SEND setting

PROJ > BRAIN > SETTINGS > SEND, stored on the card (in a remix without BRAIN, the value the remix pins):

| SEND | sends |
|---|---|
| OFF (default) | nothing |
| NOTES | the note-on and note-off |
| NOTES+CC | the six CCs, then the note-on, and the note-off |

A note-off already owed is sent whatever SEND says, so turning SEND off never
leaves a note hanging on the host.

**CC numbers are shared with stock.** CC 16..21 are the numbers stock's AUDIO
CC OUT sends on a knob move, on the same channel. With AUDIO CC OUT on and SEND
at NOTES+CC, the host gets both and cannot tell a knob move from a trig's
value. Choose NOTES, or set AUDIO CC OUT to INT, if that matters.

## Failure mode: a host that echoes MIDI back

USB MIDI IN reaches the OT through the same funnel as DIN, and an audio track
answers on its TRIG CHANNEL. A host or DAW that echoes this module's output
back over USB (a MIDI THRU, a track monitoring its input) makes the OT play
its own notes:

- In the default STANDARD note map, notes 24..31 play tracks 1..8 (each of
  which sends again), 33/34/35 are SEQUENCER STOP/START/RESTART, and 60..71 are
  recorder and mute functions. A sample in slot 34 sends note 33 and stops the
  sequencer.
- In SLOTS mode every echoed note retriggers a sample.
- Echoed CC 16..21 write the trig's lock values into the live knobs (AUDIO CC
  IN), the same mechanism as the BCR2000 echo in
  [`FAILURE_MODES.md`](../../docs/contributing/FAILURE_MODES.md).

Turn the echo off on the host, or SEND to OFF. AUDIO NOTE IN / AUDIO CC IN OFF
also stop the OT acting on it, for every MIDI source.

## Note numbers

The note is the slot number, as the manual's SLOTS note map numbers slots
(appendix C.3). FLEX slot n and STATIC slot n send the same note: the
channel says which track, not which list. Tell them apart by the track.

## Retrigs

Each retrig repeat is the same thing again: the note-off if the gate has not
run out yet, then the CCs and the note-on. A scene or the crossfader moving
RTRG or RTIM is followed, because nothing is latched here: one repeat of the
audio is one note. RTRG shows raw + 1, so the panel's minimum 1 is raw 0, one
play and no repeat. A voice started at exactly that value gets no repeats, in the
audio too, even if the fader then raises RTRG (the renderer latches a zero
count); with the fader even slightly off that end at the trig the morph works.

On a START frame the renderer's first call also restarts the old voice
through the retrig call; that one is not sent (the START's own note follows in
the same frame), so the host never gets on(old), off(old), on(new) at once.

The six are PLAYBACK page 1, with stock's numbers and raw values (the ones the
unit sends on a turn and CC FEEDBACK sends). They are read from the frame's
parameter record, not the live lane, so each carries what the voice gets at that
note: the trig's locks, the crossfader's morph between scenes, and an LFO on the
knob. SLIC has no CC: it is the page-2 ON/OFF switch, and the slice is chosen with
STRT. Until 3 Nov 2026 this module sent PTCH on CC 20 and SLIC on CC 21, which are
RTRG and RTIM everywhere else.

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

**No encoder in the frame interrupt.** Both entry points run inside the frame
interrupt. They queue with `usbmidi_tx_queue` (USB MIDI's queue without its
kick) and post `utm_kick` to the engine task through stock's deferred-call
queue (`0x40000c3c`, record type 21, the post stock's frame interrupt, REMOTE
and REMIX SWITCH make), at most one post outstanding. `utm_kick` runs
`usbmidi_tx_kick` in that task; while a transfer is in flight, the EP2 IN
completion's own kick sends the rest. Stock's encoder runs unmasked, and
running it in the frame interrupt is the late-entry mechanism of
[trap-late-frame](../../docs/contributing/TRAPS.md#trap-late-frame).

**Stuck notes.** A track whose machine leaves FLEX/STATIC (a part, kit or
machine change, a project load) stops reaching `utm_render`, so its own gate
would never count down. `utm_seen` holds a bit per track rendered in the
current frame; the second call that finds its own bit already set opens a new
frame and first closes the note of every track not seen in the frame before.
Left open: with no FLEX/STATIC track at all, nothing here runs, and the note is
closed at the next render of any track. A load that stops every renderer
holds the note for the load's length plus what is left of its gate.

A batch that does not fit USB MIDI's 256-byte accumulator goes into its 4 KB
ring; only a batch the ring has no room for is dropped, whole, and counted in
`usbmidi_tx_drops`.

## On a unit (MKII, 15 Nov 2026)

Owner report, with the PR's first build (channel = track number, always on,
the encoder kicked in the frame interrupt), not with this one: seen on the
host over USB MIDI, CC 16..21 for every value on PLAYBACK page 1, a note for
each trig, retrig repeats, and the CCs following the crossfader between
scenes. Nothing on the unit was timed or counted: the gate length, repeat
spacing, `usbmidi_tx_drops` and the INF burst are port numbers only. The
present build (TRIG CHANNEL, SEND, the deferred kick, the sweep) has not been
flashed.

## Measured (under the port)

`tools/verify/verify_usbmidi_tracks.py`, 16 Nov 2026, on this build, no
project (CI runs it):

- T1's TRIG CHANNEL set to 13: one START gives CC 16..21 in that order, the
  note-on (velocity 100), then the note-off for the same note, all on channel
  13 and nothing on any other. Note-off 52 ms of port time after the note-on
  (160 frames = 58.0 ms; the stamps are 2 ms steps).
- The bytes reach the host with the kick posted to the task (`utm_dbg`: kicks
  posted 2 for one note).
- T1's renderer pointer moved off `utm_render` 12 ms into a gate and T2's onto
  it: the note-off arrives at 12 ms, not a gate later; one note swept.

With `tools/verify/probe_usbmidi_tracks_project.py`, 3 Nov 2026 (the build
before the channel, SEND and deferred-kick changes), on two real projects
with one generated WAV behind every sample slot:

- Notes match the bank data (lock slot 31 = sample slot), note-offs pair, the six
  CCs arrive with each note-on.
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

- On a unit: frame-interrupt lateness with dense trigs and INF retrig on
  several tracks (`tools/hw/framelog.patch`), now that the encoder is out of
  the interrupt; and the latency the deferred kick adds when EP2 IN is idle
  (the engine task's turn), not measured anywhere.
- An LFO on one of the six is in the CC (`docs/firmware/LFO.md`: it writes the same
  record). Read from the code, no test project has one.
- A track on another machine is not hooked for STARTs. PICKUP shares the stock
  renderer, so `utm_retrig` does run there; a recorder buffer's record gives no
  note. Not run.
- A START from the panel sends notes as well as a sequencer trig.
- Audio onsets: the repeats are read from the renderer's state and calls, not yet
  heard in the port's audio (`probe_usbmidi_retrig_audio.py` read silence, cause
  not checked since the fixture fix below).

## Open

- AMP page CCs (22..27, the voice record). FX are out of scope.
- Gate length from the trig or AMP HOLD, rather than fixed.
- Sharing the site with SYNTH MACHINE (a chained detour).
