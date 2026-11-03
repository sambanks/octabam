# MIDI

The combined MIDI remix: **MIDI HARMONY**, **MIDI FOLLOW**, **MIDI SCALES** and
**MIDI LOOPBACK**, with all fourteen stock effects. STORE and EVENTS provide
the shared Part, retained-storage and lifecycle support automatically.

## Musical workflow

- **Scales** sets the key and one of seven diatonic modes on ARP SETUP.
- **Harmony** turns scale-degree roots into melodies or chords, with voicing,
  Chord Play and per-step degree accumulation.
- **Follow** lets other tracks interpret the progression with their own rhythms,
  registers and Harmony settings: for example, a bass line, chord stabs and an arp.
- **Loopback** sends a MIDI track to external instruments, the Octatrack's internal
  receiver, or both. Internal routing can sequence audio-track controls without
  a loopback cable; receive channels, switches and note maps still apply.

For example, use T1 for a minor-key degree progression, T2 as a NOTE bass
following T1, T3 for following CHORD stabs, and T4 with INT routing to animate
an audio track's filter. RFOL OFF keeps a track independent; HARM OFF keeps
native note playback. Loopback starts at EXT, so internal routing is opt-in.

See the controls and project-compatibility notes for
[Harmony](../../modules/midi-harmony/README.md),
[Follow](../../modules/midi-follow/README.md),
[Scales](../../modules/midi-scales/README.md) and
[Loopback](../../modules/midi-loopback/README.md).

## Verification boundary

This combined selection has not been tested on hardware. Individual module
hardware reports do not qualify the combination or its maximum load.
The focused carriers under `remixes/test` retain separate checks for Harmony
without Follow, native KEY without Scales, and each module in isolation.
There is no separately selectable MIDI SRAM module; STORE includes the
retained-storage protection when Harmony is selected.
