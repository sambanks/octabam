# MIDI Loopback

Routes MIDI-track output into the Octatrack's own MIDI receiver, with optional
DIN/USB output. Use it to sequence audio-track controls without a loopback cable.

## Use

1. Open a MIDI track's **NOTE SETUP** with **FUNC + SRC**.
2. Set **A: CHAN**, then press A to apply the channel and open **ROUTING**.
3. Turn **A: DEST**:

| DEST | Output |
| --- | --- |
| EXT | DIN/USB only; the default. |
| INT | Internal receiver only. |
| BOTH | One internal copy plus DIN/USB output. |

Edits apply immediately. Press A, YES or NO to close. A track key closes
the window and selects that track. A page key closes the window first; press it
again to change page. CHAN shows **I** for INT
or **B** for BOTH. CHAN OFF disables sequencer output.

For example, MIDI T1 on channel 1 with INT and CC 34 can control audio T1's
FILTER BASE when that track receives channel 1 and audio CC reception is enabled.

## Routing behavior

- Covers sequencer/arp notes, live trig keys, preview, track CCs and LFOs,
  pitch bend, channel pressure, Part bank/program messages and STOP panic.
- Internal events reach audio listeners and the audio-mode auto-channel.
  They do not feed MIDI-track forwarding or recording back into the route.
- Audio receive channels, receive switches and note maps still determine the
  response. Normal DIN/USB input retains its native routing.
- Clock, transport, SysEx and project-wide program-change sync are unchanged.
  Audio-knob feedback and CC Direct Connect are separate paths.
- Changing DEST or replacing a Part releases held notes through their original
  routes. Internal queue overload can drop new events; BOTH still sends externally.

**Avoid overlapping internal and external notes on the same channel and pitch.**
They share the native receiver's note state: the first note-off ends the note,
even if the other source still holds it.

## Storage and composition

DEST is stored per MIDI track in each native Part. Part save/reload/clear,
copy/paste and project save/load carry it; fresh Parts use EXT. Playback uses
the playing Part, independently of the Part selected for editing.

Requires **MIDI Part State**. With MIDI Scenes, select the **MIDI Loopback /
MIDI Scenes bridge** to route its additional producers. KITS is not required.

Stock 1.40C resets the routing flags to EXT when loading. Saving the current
bank on stock persists that reset. Keep a separate project copy to preserve routes.

[Implementation, provenance and verification](DEVELOPMENT.md).
