# MIDI

The full **OCTABAM** instrument with **MIDI HARMONY**, **MIDI FOLLOW** and
**MIDI LOOPBACK** added. It inherits OCTABAM's effects, USB configuration,
MIDI Scenes, **SCALES** and **CHORDS FACTORY** directly from the base remix.

## Musical workflow

- SCALES supplies all 52 scales for ordinary tracks. Harmony uses its seven
  diatonic modes; MIDI SCALES remains a supported alternative in custom builds.
- Harmony turns degree patterns into melodies, chord stabs and arpeggios, with
  inversions, voice leading, spread and per-step degree accumulation.
- Follow gives a bass, chord and arp track independent rhythms while sharing
  a source progression. RFOL OFF keeps each track independent.
- Factory provides hand-built absolute chords on HARM OFF tracks. CHORDS and
  Harmony's CHORD PLAY both remain available in the trig-mode menu.
- Loopback routes notes and controls to external instruments, the internal
  receiver, or both. MIDI Scenes' CC output follows the same per-track route
  using the actual mix Part. EXT is the default; internal routing is opt-in.

For example, program a minor-key progression on T1, a following NOTE bass on
T2 and following CHORD stabs on T3. Use T4 with HARM OFF for Factory chords,
and T5 with INT routing and MIDI Scenes to animate an audio track's filter.
Internal receive channels, switches and note maps still apply.

Unsupported Harmony scales produce an explicit message and suppress new
Harmony notes without rewriting degree data. Choose a supported local or
followed scale before changing HARM, including turning it OFF. Factory refuses
live playing/recording or pattern insertion onto HARM-enabled tracks.

See [Harmony](../../modules/midi-harmony/README.md),
[Follow](../../modules/midi-follow/README.md),
[SCALES](../../modules/scales/README.md),
[Factory](../../modules/chords/README.md) and
[Loopback](../../modules/midi-loopback/README.md).

## Verification boundary

This combined selection has not been tested on hardware. Individual module
hardware reports do not qualify its maximum load. Focused carriers under
`remixes/test` cover Harmony without Follow, native KEY, MIDI SCALES and SCALES.
TRIG MODES owns the shared menu/dispatch; STORE owns Part and retained storage.
There is no separately selectable MIDI SRAM or Loopback/Scenes bridge module.

Instruction ceilings remain unchanged. Focused lifecycle and CPU results are
reported for their exact image; instruction counts are not hardware timing.
Full-remix qualification runs in CI. Physical MIDI routing, project recovery
and maximum-load acceptance remain separate hardware checks.
