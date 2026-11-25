# TRIG MODES

System service for registered MIDI playing modes. One owner installs the
mode list, names, icons and navigation, and dispatches keys, LEDs and cleanup
to the selected clients. Audio modes retain their native meaning.

Clients register stable mode IDs separately from menu order. CHORDS FACTORY
uses MIDI mode 2; Harmony's CHORD PLAY uses mode 6. The menu contains both
when both clients are selected. It maps the active ID back to its row when
opened, rather than clamping an ID into the list.

Clients retain their musical engines and note ownership. Cleanup reaches
every selected client with the original track, including after a mode change.
No clients means no code or firmware patches from this service.

Independent synthetic clients exercise sparse IDs, dispatch, native fallbacks
and cleanup. Combined Factory/Harmony panel checks exercise actual playback
and recording. No hardware acceptance is claimed.
