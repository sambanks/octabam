Native Part access is now part of **STORE**. MIDI LOOPBACK requires STORE;
there is no MIDI PART STATE module to select. The service supplies explicit
edited, playing and saved Part contexts to registered clients.

Routing settings belong to the native Part: Save, Reload, Clear and Paste use
the existing Part operations. Each producer chooses its own context; Loopback
reads the actual playing or edited Part, independently of audio-track latches.

Stock 1.40C cold project load clamps routing flags to zero (EXT). Saving the
bank on stock overwrites INT/BOTH settings; loading alone does not rewrite
every bank file. Preserve a separate project copy when returning to stock.
