# MIDI Loopback

Routes MIDI-track output into the Octatrack's own MIDI receiver, with optional
DIN/USB output. Use it to sequence audio-track controls without a loopback cable.

The current STORE integration has passed native Part and playback-context checks
in the emulator. Hardware testing of this integration remains outstanding;
[earlier hardware reports](DEVELOPMENT.md) refer to their recorded images.

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

### Feedback and held notes

- Internal delivery excludes MIDI-track listeners and the MIDI-mode auto-channel.
  No selectable channel or mode can retrigger a MIDI track through this internal
  path. Audio listeners and the audio-mode auto-channel remain available.
- Internal note-ons without an eligible audio listener are discarded before
  allocating held-note state. Route and Part changes release owned notes
  through their original destinations.
- External DIN/USB input keeps its native routing. A cable or echo device can
  return BOTH's external copy as fresh input; the internal guard cannot identify
  that round trip. Use INT for internal-only control and avoid external echo loops.
- **Avoid overlapping internal and external notes on the same channel and pitch.**
  The native receiver merges them: the first note-off ends the shared note even
  if the other source still holds it. Separate receive channels or pitches when
  independent sustain is needed. The module does not add separate voice ownership.

## Storage and composition

DEST is stored per MIDI track in each native Part. Part save/reload/clear,
copy/paste and project save/load carry it; fresh Parts use EXT. Playback uses
each MIDI track's applied Part, independently of retained audio voices and
the Part selected for editing.

Requires **STORE**. Combining MIDI Loopback with MIDI Scenes is not supported;
the build rejects that selection. KITS is not required.

### Returning to stock 1.40C

STORE native Part access changes the allowed-value count at `0x400d4082` from 1 to
`0x10`: the Part's MIDI SETUP flags byte accepts 0–15 instead of only zero.
DEST occupies bits 2–3 (INT = 4, BOTH = 8); EXT is zero. This uses an existing
Part field and does not enlarge the file format.

Stock 1.40C loads such a Part but clamps the entire flags byte to zero, in
**both working and saved Part copies**. INT and BOTH therefore become EXT:
MIDI-track output goes to the normal external destination. Saving the current
bank/project on stock writes that reset into its `.work` and `.strd` bank
files. Returning to Loopback cannot recover those saved routes. Loading alone
does not rewrite the other bank files; this is not a promise that later edits
or saves will preserve their flags.

Keep a separate project backup before returning to stock.

[Implementation, provenance and verification](DEVELOPMENT.md).
