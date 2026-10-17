Provides the native Part-state access used by MIDI Loopback. Include MIDI PART
STATE when selecting MIDI LOOPBACK in a custom remix. It adds no screen or
control of its own.

Routing settings belong to the native Part: Save, Reload, Clear and Paste use
the existing Part operations. Playback reads the Part playing on each MIDI
track, independently of the Part selected for editing.

## Stock Compatibility

Stock 1.40C cold project load clamps the routing flags to zero (EXT). Saving
the bank on stock overwrites its INT/BOTH settings. Loading alone does not
rewrite every bank file. Preserve a separate project backup before returning
to stock if those settings matter.

## Verification

Checked with linked-code tests and native Part operations in the emulator,
including a candidate-to-stock-to-candidate cold-load/save round trip.
Hardware acceptance remains outstanding. Later MIDI consumers and their
combinations need their own verification.
