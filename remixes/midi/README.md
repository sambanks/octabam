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
retained-storage protection when a registered client is selected. Harmony
reserves the current pool’s full 16 KB through that system service; the
implementation lives in STORE and has no MIDI SRAM module dependency.

With HARM OFF and all Loopback routes at EXT, seven GRAV LIVE followers moving four voices
execute 31,974 instructions in the focused probe, versus 25,366 in the
Harmony/Follow control without Loopback. Unchanged-root updates stay at 12,766.
The CPU gate keeps the existing control limits and adds only the measured
routing cost for this composition. Native enqueue/transmission is stubbed;
these are instruction counts, not cycles or hardware capacity. INT/BOTH routing
is functionally checked separately and has no timing qualification here.

The original **20,000-instruction** lifecycle limits are unchanged and the
previously failing gates now pass. Same-Part replacement fell from 32,514 to
6,704 instructions, unrelated-Part replacement from 32,526 to 6,716, and the
Follow fixture's HARM edit from 31,784 to 16,039. A separate initialized-bank
gate checks deferred save/recovery and stays below 10,000 in its measured cases.
Part replacement skips unattached Harmony records; mode edits request the
existing UI poll to save retained data. The full background save cost remains,
and dense active copies can exceed these small-fixture counts. See
[lifecycle instruction bounds](../../modules/midi-harmony/README.md#lifecycle-instruction-bounds)
for the scope and remaining hardware boundary.
