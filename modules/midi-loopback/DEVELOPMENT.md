# midi-loopback implementation and verification

Internal routing of MIDI-track sequenced and live notes, CCs, pitch bend,
channel pressure and Part bank/program changes through the normal MIDI receiver. All eight source
tracks and output channels 1–16 are supported at these producer boundaries.
The receiver's channel assignments, CC/note receive switches and note maps
still decide which audio controls respond. The routing window does not block
native received-MIDI track-selection commands.

## On the Octatrack

On a MIDI track, open **NOTE SETUP** with **FUNC + SRC**. Turn **A: CHAN**
to choose its output channel, then **press A**. The press applies the pending
channel exactly as before and opens **ROUTING** for that track.

Turn **A: DEST** in the window:

| DEST | Track output |
|---|---|
| EXT | Existing DIN/USB output only; default. |
| INT | Internal delivery; bypass the shared DIN/USB sender. |
| BOTH | One internal copy plus existing DIN/USB output. |

Edits apply immediately. A press, YES or NO closes the window. A track key
closes it and selects the requested track in one press. A page key closes it
first; a second press changes page. B–F are inactive;
transport and chromatic keys pass through. CHAN shows an **I** suffix for INT
or **B** for BOTH (for example `2I`); EXT keeps the normal channel display.
CHAN OFF still disables sequencer output.

DEST belongs to each MIDI track in each native Part. Part Save/Reload/Clear,
copy/paste and project save/load use the existing native storage. Playback
reads each track's playing Part, independently of the Part selected for editing.
Fresh Parts use EXT. No parameter locks or separate settings file are added.
The shared `STORE` module is required; KITS is not required; its combination is not qualified here.

Changing the playing destination releases held notes at their original
channel/destinations. Part replacement also releases the outgoing ownership;
late stock releases are consumed without sending a second note-off. A channel
change is observed at the next sequencer boundary, or immediately after the
CHAN press. Other tracks' notes remain owned by their original tracks.

For example, M1 on channel 1 with INT and CC1 assigned to CC 34 can sequence
T1 FILTER BASE, provided T1 receives channel 1 and audio CC reception is on.
M2 can remain EXT for an external synth. Stock arbitration between tracks
sharing a channel, pitch or CC still happens before these hooks; routes do
not create independent copies of the stock note pool or CC cache.

## Boundaries

The destination covers sequencer and arp output, live trig keys and preview,
CC locks/LFOs and panel controls, pitch bend, channel pressure, Part
BANK/SBNK/PROG and STOP's
CC123 panic. Held releases retain their original destinations. Two-byte
pressure/program packets and paired bank messages retain their wire lengths.

Clock, transport, song position, SysEx and the project-wide program-change
sync sender are global rather than MIDI-track output; their behavior stays
unchanged. Received-MIDI forwarding, CC Direct Connect and audio-knob
feedback are input/feedback paths, not new internally copied track events.
The generic received-parameter setter remains excluded to prevent recirculation.
For internal packets, the receiver uses a private channel map containing audio
listeners and audio-mode auto-channel only. MIDI-track forwarding/recording is
excluded, so internal packets cannot escape through input echo or feed back
through another MIDI track. Normal DIN/USB input retains the native channel map.

Use dedicated channels/pitches without overlapping external held notes.
Stock's incoming-note bookkeeping is shared by channel and pitch; receiver
ownership across independent external and internal senders is not separated.
Two overlapping external/internal note-ons for the same channel/pitch coalesce:
**the first note-off ends the shared note**, even if the other sender still
holds it. Compiled-code/native-receiver tests cover both arrival/release orders,
16 channels, INT/BOTH and both note-off encodings (256 cases). They leave no
held count and both sources can play a fresh note afterwards. This pins an
early-release limitation, not independent voice ownership or a hardware result.

The feedback regression tests 512 configurations: all 16 channels, both UI
modes, all eight source tracks and INT/BOTH, with all MIDI tracks sharing the
source channel and auto-channel collision. Seven channel-message kinds cannot
re-enter the internal queue or echo through MIDI-track forwarding. External
positive controls still forward. Audio-mode auto-channel events remain valid.
Two negative controls modify only a disposable emulator instance before its
first dispatch: removing the MIDI-listener mask causes external echo, and
removing the no-listener early return allocates native held state without an
audio listener. The matching release clears this control count; it is not a
permanent held-note leak.
The intact build rejects a no-listener internal note-on before it can allocate
that state. These controls establish that the checks detect the guarded faults.
External cable/software echoes re-enter as native input, outside the internal
origin guard; BOTH is not an external MIDI feedback suppressor.
A separate external/internal ownership layer is not added: it would change
native receiver semantics beyond this routing change. Dense traffic and
physical receiver behavior still require hardware checks.
Changing audio receive assignments while notes are held and cross-project
transitions during playback remain unproved. Audio locks/scenes and dense
simultaneous external traffic still need separate integration tests.

## Implementation

Four ColdFire DRAM units, no DSP effect slot. SETUP offset 12 is owned by
STORE: DEST uses bits 2–3 and preserves the other bits. Bits 0–1 are reserved
for future shared MIDI settings. DEST 3 or invalid flags decode as EXT. `lb_routes[8]` is an applied
runtime cache; tools must use `lb_dest_write(track, route)` to edit native
settings. `lb_set_route` remains the low-level cache/cleanup helper.

Boundaries:

| Boundary | Purpose |
|---|---|
| Pinned sender operands in track producers and cleanup routines | Route complete channel messages before `midi_send` at `0x40010bc8`, leaving USB-MIDI's entry hook intact. |
| `0x4009f794` | Synchronize native Part destinations and effective output channels at sequencer entry. |
| `0x40005558` | Alternate native and internal messages in the MIDI task, then use the installed dispatch table and handlers. |
| `0x4009f26e` and cached live sender operands | Capture live CC/bend/pressure before the tail restores source track. |
| `0x4009ecb4` | Part setup sender: track in `a3`, bank/Part from its arguments. |
| `0x4009ea68`, `0x4009ea96`, `0x4009eb50` | Live notes: source track in `d5`, UI Part destination. |
| `0x4009f288` | STOP panic combines routes of tracks assigned to each channel. |

The live branches retain track identity in `d7` and qualify the parent
return address `0x4005542c`. Trig preview (`0x40043b0e`) also qualifies. The generic received-MIDI setter
(`0x40054f74`) is excluded without a global origin flag. The MIDI LFO engine
writes the modulated parameter array used by the two sequencer CC producers.
All patched operands and displaced instructions are pinned in the manifest.

The byte parser is untouched. A 256-entry ring holds complete messages.
The consumer copies each message to a stable slot before releasing capacity.
One coalesced wake token uses the native MIDI queue; a full native queue does
not receive an extra token. Internal and native messages alternate while both
are available. The wake token never reaches the MIDI handler table.

The ownership table covers all 2,048 channel/pitch pairs, storing source track
and the destinations used at note-on. New internal note-ons/controllers stop at 127
pending messages; at most 128 internally held pitches reserve 128 release
slots across all channels. An INT admission failure leaves a tombstone so
its later release does not leak externally; BOTH still sends the event
externally. Counters expose accepted/delivered messages, drops and high water.
Eight 16-bit volatile counters track live ownership per source track, including
EXT notes. They are updated together with ownership under the same interrupt
mask. Duplicate notes and release/drop tombstones add no count; releases debit
the recorded owner, independently of the releasing producer. An empty track
skips the ownership scan without clearing its late-release tombstones. A track
with live notes still scans the bounded ownership table with interrupts masked
and uses the stock sender for external releases. The counters use 16 bytes
inside the existing platform reserve, with no allocation or storage-format change.
Worst-case hardware cost and UART backpressure are not yet measured.

The earlier MIDI PART STATE selection reserved three 6,144-byte sample-arena pages
(18,432 bytes). Its linked runtime was 9,444 bytes; the reservation also holds
loading and runtime state. The old fixed 10 MiB reserve predates per-remix
sizing. Combined selections compute their own reservation; consult
`out/platform/layout.json` and the build report for the selected image.

## Author source

Pinned source: the `upstream` submodule gitlink beside this document.
Review both modules in that narrow author history alongside these adapters.
The cold-entry reference is enforced at build time; the combined cross-unit
runtime reference is enforced by `verify_midi_loopback_reference.py`. A native
source build and the adapter build are compared at the same upstream base.

## Current routing and startup qualification

Sequenced routing uses native MIDI-track bank/Part latches at `0x8000666e`
and `0x80006676`, with the native applied-engine fallback before the first
trig. The audio-track latches can retain the outgoing Part and are not MIDI
context. `verify_midi_loopback_context.py` checks conflicting audio/UI states,
each MIDI track independently, invalid contexts and original-note cleanup.
`verify_midi_loopback_transitions.py --help` describes the native first-note
and stopped/playing transition regression, with and without the audio trig.

The Part activation helper is resident beside its early entry gates; the
build resolves its callback pointers after linking the selected runtime and
refuses size or export movement. The shared loader and stock continuation
are unchanged. `verify_midi_part_activation.py` checks the installed call and
96 register/status/stack/publication comparisons, plus a corrupted callback
negative control. An unused runtime activation copy remains to preserve the
qualified runtime layout; removing it requires fresh image qualification.
