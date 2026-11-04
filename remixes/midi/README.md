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

With HARM OFF and all Loopback routes at EXT, seven GRAV LIVE followers moving four voices
execute 31,974 instructions in the focused probe, versus 25,366 in the
Harmony/Follow control without Loopback. Unchanged-root updates stay at 12,766.
The CPU gate keeps the existing control limits and adds only the measured
routing cost for this composition. Native enqueue/transmission is stubbed;
these are instruction counts, not cycles or hardware capacity. INT/BOTH routing
is functionally checked separately and has no timing qualification here.

The generic lifecycle gate limit remains **20,000 instructions**. The temporary
40,000 allowance introduced during integration has been removed; the affected
Harmony mode-change and Part-copy gates currently fail. This is unresolved
implementation work, not a passing performance qualification.

Diagnostic probes on the merged image measured 32,514 instructions for the
Follow fixture's Part copy (3,408 with standalone Follow), and 31,784 for its
HARM mode edit. Those fixtures did not initialize Harmony's retained data:
the mode edit's payload pack rejects the input and exits early. After running
Harmony initialization, mode edits instead take about **649,000 instructions**,
mostly full-bank retained packing/validation/writing; an inactive Part copy
takes **24,322**. These are emulator instruction counts, not hardware timing.
See the [lifecycle investigation](../../modules/midi-harmony/README.md#lifecycle-cost-investigation)
for the work to remove before accepting the integration.
