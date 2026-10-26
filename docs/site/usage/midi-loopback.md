Route each MIDI track to external MIDI, the Octatrack's internal MIDI receiver,
or both. For example, an internal MIDI track can sequence audio-track CC
controls while another MIDI track drives external equipment.

## How to use it

1. On a MIDI track, open NOTE SETUP with FUNC + SRC.
2. Choose A: CHAN, then press A to apply it and open ROUTING.
3. Turn A: DEST to EXT (default), INT, or BOTH. Changes apply immediately.
4. Press A, YES or NO to close. Track/page keys close the window first.

CHAN shows an I or B suffix for INT or BOTH. CHAN OFF still disables sequencer
output. Receiver channel assignments and receive switches still apply.
DEST is saved per MIDI track in each native Part. Fresh Parts use EXT.

## Notes

Select STORE alongside MIDI LOOPBACK. This contribution supplies a
standalone test remix; official remix selections are unchanged. MIDI Scenes
needs a later bridge and is currently refused with Loopback.

Held notes are released at their original destination when routes change.
Avoid overlapping internal and external held notes on the same channel/pitch:
the stock receiver merges their held-note state, and the first release ends
the shared note. Independent sustain from each source is not supported. Internal delivery filters out MIDI-track receivers,
so it cannot retrigger a MIDI track through the internal path, even with
matching MIDI/auto-channel assignments. A no-listener internal note-on is
rejected before it can allocate held state without an audio recipient. External echo loops remain
possible when BOTH output returns through a cable or another device; use INT
for internal-only control.
Clock, transport, SysEx and project-wide program-change sync stay global.

Stock 1.40C cold project load resets the destination flags to zero (EXT) in
both working and saved Parts. The native flags field accepts only zero on stock,
whereas STORE allows 0–15; INT/BOTH occupy bits 2–3.
Saving that bank on stock loses its INT/BOTH settings. Other bank files stay
unchanged until saved; keep a separate backup before returning to stock.

The standalone Loopback selection reserves three 6,144-byte sample-arena
pages (18,432 bytes) for runtime code, state and loading. Combined remixes
compute their own reservation from all selected modules.

Sequenced routing follows each MIDI track's applied Part, independently of
an audio voice retaining another Part or a Part selected for editing. Matching
audio and MIDI track numbers do not imply shared playback state.
