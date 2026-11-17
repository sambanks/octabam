# OT Gate -- split an Octatrack track's audio by the slot each trig plays

Two Max for Live devices for Ableton Live that use what
[USB MIDI TRACKS](../../README.md) sends. One Octatrack track playing several
samples comes into Live as one USB audio channel. OT Gate opens that channel
only while the notes say the sample (slot) you chose is playing, so each sound
can have its own Live track, effects and mix. A reference for building on the
module from a host. They are not part of the firmware and no image carries them.

By siddely. MIT, as the rest of the repository.

## What they need

- An image with **USB MIDI TRACKS** and **USB audio with the track channels**
  (USB's TRACKS setting PRE or POST), so Live gets each OT track as its own
  input pair.
- BRAIN > SETTINGS > **SEND** at NOTES (slot gating) or NOTES+CC (the Matrix
  view's CC rows too). The module's default is OFF.
- Ableton Live with Max for Live.

## The files

| file | goes in Live's User Library | does |
|---|---|---|
| `OT Gate Source.amxd` | MIDI Effects > Max MIDI Effect | on one MIDI track whose input is the Octatrack (monitor In): hands every note and CC to the OT Gate devices, by MIDI channel |
| `OT Gate.amxd` | Audio Effects > Max Audio Effect | on each audio track you split, whose input is that OT track's USB channel pair: the gate |
| `otgate_logic.js` | next to `OT Gate.amxd` | the matching and the view switching OT Gate runs; keep it in the same folder (or open OT Gate in Max and Freeze Device, which makes it one file) |

One OT Gate Source serves every OT Gate in the set.

## Using it

- **Track** is the MIDI channel the notes come on, which is the OT track's
  **TRIG CHANNEL** (PROJECT > MIDI > CHANNELS). With the default channels,
  track n is channel n.
- **Slots view:** a toggle and a slot menu per slot. The gate opens for a note
  whose number is a ticked slot (the note is the slot number; menus show it + 1).
  **Learn** adds the next slot that plays.
- **Matrix view:** slots by CC rows (16 PTCH .. 21 RTIM preset). A lit cell is
  "that slot AND that CC in its range"; lit cells are OR'ed; nothing lit opens
  for every note.
- **Fade In / Fade Out** smooth the gate's edges.
- **Offset** lines the notes up with the audio. MIDI and the USB audio reach
  Live by different paths, so the right value depends on the set: on the one
  setup measured it was -87 ms (MIDI slightly ahead). Clear Live's track delays
  before adjusting it; a 1.29 s misalignment on that setup was a track delay,
  not the devices.
- The **Gate** parameter can be recorded as automation.

The controls are native Live objects (no drawn UI), so the devices can be
restyled in Max; keep the objects' scripting names, which `otgate_logic.js`
shows and hides by name.

## Status

Used on an MKII with Live (owner reports): 14 Nov 2026 with the module's
first build (notes on channel = track), and 17 Nov 2026 with the reviewed
build (TRIG CHANNEL, SEND on), splitting as expected. Nothing was timed or
counted beyond the Offset reading above.
