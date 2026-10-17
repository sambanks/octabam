# MIDI Part State

Shared native Part storage for MIDI modules. It adds no panel controls and
does not require KITS.

- Edits affect the selected working Part; playback reads each track's playing Part.
- Part save/reload/clear, copy/paste and project storage carry the settings.
- Readers see a complete outgoing snapshot while a Part is being replaced.
  Modules remain responsible for releasing their own held notes.
- Loopback stores DEST in a shared flags byte. Fresh Parts use EXT; other
  consumers retain ownership of their own bits and fields.

Stock 1.40C resets the shared flags byte to zero on load. Saving the current
bank on stock persists that reset, including Loopback's return to EXT. Other
bank files are not rewritten merely by loading. Keep a separate project copy
when preserving module settings matters.

[API, storage layout, provenance and verification](DEVELOPMENT.md).
