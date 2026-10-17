Route each MIDI track to external MIDI, the Octatrack's internal MIDI receiver,
or both. For example, an internal MIDI track can sequence audio-track CC
controls while another MIDI track drives external equipment.

## How to Use It

1. On a MIDI track, open NOTE SETUP with FUNC + SRC.
2. Choose A: CHAN, then press A to apply it and open ROUTING.
3. Turn A: DEST to EXT (default), INT, or BOTH. Changes apply immediately.
4. Press A, YES or NO to close. Track/page keys close the window first.

CHAN shows an I or B suffix for INT or BOTH. CHAN OFF still disables sequencer
output. Receiver channel assignments and receive switches still apply.
DEST is saved per MIDI track in each native Part. Fresh Parts use EXT.

## Notes

Select MIDI PART STATE alongside MIDI LOOPBACK. This contribution supplies a
standalone test remix; official remix selections are unchanged. MIDI Scenes
needs a later bridge and is currently refused with Loopback.

Held notes are released at their original destination when routes change.
Avoid overlapping internal and external held notes on the same channel/pitch:
the stock receiver merges their held-note state, and the first release ends
the shared note. Emulator checks found no remaining held count and subsequent
notes recovered in both arrival/release orders. Independent sustain from each
source is not supported. Internal delivery filters out MIDI-track receivers,
so it cannot retrigger a MIDI track through the internal path.
Clock, transport, SysEx and project-wide program-change sync stay global.

Stock 1.40C cold project load resets the destination flags to zero (EXT).
Saving that bank on stock loses its INT/BOTH settings. Other bank files stay
unchanged until saved; keep a separate backup before returning to stock.

Verified under the emulator only; hardware timing and interrupt latency remain
unmeasured. The platform reserve reduces available sample memory by about 10 MB
when added to an otherwise stock selection.
