# MIDI Follow

Each MIDI track can follow another MIDI track's logical note set while keeping its
own rhythm, velocity and note length. By default, FIXED octave 3 with TRAN=0 uses MIDI notes 36–47 for the root:
C → F → G gives 36 → 41 → 43. The follower's TRAN adds a signed semitone
offset after its register choice. Scale Quantizer is not required.

## Composition and controls

Select `MIDI FOLLOW` with `STORE` and `EVENTS`. Scales and KITS
are optional. RFOL is a persistent source choice, not a held modifier. Pressing
D opens its editor; TRIG/LIVE is a per-receiver setting. Start with TRIG so
roots change only at your programmed rhythm, then try LIVE for sustained bass.

## Register choice

On the receiving track, press **knob D (RFOL) on NOTE SETUP** to open FOLLOW.
Knob **B: REG** selects FIXED, GRAV or SOURCE. Knob **C: OCT/OFFS** sets the register:

| REG | C control | Effect |
| --- | --- | --- |
| FIXED (default) | 0–10; default 3 | Keep the source pitch class in this octave, regardless of its original octave |
| GRAV | OCT 0–10; default 3 | Prefer this octave while minimizing root movement |
| SOURCE | OFFS -2, -1, 0, +1, +2; default 0 | Follow the source's complete root pitch, shifted by this many octaves |

For source notes C3 then C5 (MIDI 36 then 60): FIXED 3 produces C3 then C3;
SOURCE 0 produces C3 then C5; SOURCE -1 produces C2 then C4.
Octave names here use C0 = MIDI 0. Octave 10 is partial: only C–G fit MIDI.
Each mode remembers its own value when switching modes. A/B/C follow the
top row; D is lower-left UPDT. All six encoder cells remain visible;
the unused E/F cells are empty. Full native dials use fixed
layout flag 8 and range-scaled needle positions, with independent real-value
formatters. REG uses the native three-position widget; UPDT uses two.

The receiver applies register choice first, then its native TRAN/P-lock offset.
Out-of-range final roots are silent, never wrapped or clamped. Settings affect
the next receiver note trig; already-held notes keep their original releases.
A chain uses the ultimate source's root and the final receiver's register and
TRAN; intermediate receiver offsets do not accumulate.

Source register refers to the source's first NOTE before arpeggiation, not
whichever chord or arp note is lowest. Source sequence TRAN/scale processing
happens before capture.

RFOL, REG, three remembered register values and TRIG/LIVE response are native
Part settings per MIDI track. They are not parameter locked. UI edits use the
selected working Part; playback uses each track's playing Part. KITS carries
these native bytes but is not required. Existing stock controls and the source
selector remain in place. NO/YES/D or a track/page key closes the
window; transport and chromatic playing continue through it.

## On the Octatrack

1. Select the follower, for example **MIDI T2**.
2. Open **NOTE SETUP** with **FUNC + SRC** (or double-tap SRC).
3. Turn **knob D, RFOL**, from **OFF** to **T1**.
4. Program T1's C/F/G NOTE locks and optional NOTE2–4 chord tones. Its arp can
   play those chords. Program T2's rhythm; leave the follower's arp OFF.
5. Give the two tracks different output MIDI channels, then play.
6. On the follower's **ARP MAIN** page, use **TRAN** for relative pitch:
   **0** = root, **+7** = perfect fifth, **+12** = octave above, **-12** = octave
   below. Set it for the whole track, or hold a step and parameter-lock TRAN.
   A locked value replaces the track's base TRAN for that step; it is not added
   to the base. The follower's arp remains OFF.

RFOL appears on all eight MIDI tracks. It selects a **track**, independently of
its output CHAN. Several followers can select the same source. The selector
skips the track itself and choices that would create a circular dependency.
Chains resolve to their final source: T3 → T2 → T1 follows T1's root.

- **OFF** plays the track's original notes. Fresh Parts default to OFF.
- Root means the source's first NOTE, with its stock transpose/scale processing;
  it does not infer the root from a chord inversion. C–E–G arp notes leave the
  bass on C. A new F–A–C chord moves it to F.
- The source publishes its effective NOTE1–4 pitch set. The follower uses those
  intervals around its selected register and TRAN; its own NOT2–4 do not add
  another chord. Before the first eligible source trigger, native playback
  passes through unchanged.
- The next follower trig uses the selected source's latest root and the receiver's register choice. A held bass
  keeps its original note-off, including when RFOL changes or switches OFF.
- The follower's NOTE does not set an interval: use TRAN. Its live value,
  including parameter locks, is added after register selection. Each voice then
  passes through the inherited source KEY correction. Native values 1–24 use
  the stock rotation and correction table at `0x400d80a0`, matching the stock
  output path at `0x4009fb58`; OFF is chromatic. Additional MIDI Scales values
  use its extension. TRAN remains a semitone input, not a scale-degree offset.
  LIVE retains each voice's raw-minus-corrected pitch so repeated movements
  reapply KEY without accumulating rounding drift.
  Pitches outside MIDI 0–127 are suppressed instead of wrapped. Before stock
  scans the chord slots, Follow enables only slots backed by valid source notes;
  their final pitches still pass through stock note ownership and release.
- A dependency chain uses the ultimate source root plus the final follower's
  own register choice and TRAN; intermediate followers' offsets do not accumulate.
- Ordinary same-tick source trigs are captured before any track emits, so
  **T2 following T8** sees the new root on that tick. Earlier microtimed bass
  trigs still use the previous root.
- Roots latch through rests and transport stops and remain runtime state.
  Configuration belongs to the native Part; roots and held-note ownership are
  not copied or persisted with it. This greenfield format has no migration
  from the previous Follow packed format. Native Part operations own persistence.
- **Muting a source silences its sequenced MIDI output but keeps its root
  progression available to followers**, including when playback starts muted.
  Muting a follower independently silences that follower. Mute/unmute does not
  reset the remembered root or change the ownership of already sounding notes.
- Disabled tracks, CHAN OFF, zero velocity, invalid notes and rests still leave
  the previous root in place. Ordinary track mute is covered in linked and
  full-firmware emulator tests; unusual mute/plays-free modes remain untested
  on hardware.

MIDI Follow copies native one-to-four-note sets. Audio following and
manually held receiver keyboard notes are outside its scope.
Shared output channels have ownership stress coverage; physical MIDI timing
requires instrument validation.

## Implementation

The module uses the linked ColdFire pattern from `modules/repitch` and the
stock NOTE descriptor, drawer and encoder dispatch. No DSP code is added.

- `0x4009f986`: before the output loop, capture eligible ordinary note sets
  for all tracks. Uses the stock trigger mask, enabled-track checks,
  output channel and velocity. The mute mask is intentionally left to stock
  output handling. Original NOTE lanes already contain the locks.
- `0x4009fb00`: capture each eligible source event, including arp ticks, from
  the original NOTE lane, not the arp's scratch output. Apply the stock
  transpose and scale correction. Enable source-backed N2–4 slots before
  stock skips absent follower slots.
- `0x4009fb80`: resolve a follower's source, add its live TRAN (`a5+0x22c`,
  biased by 64), and replace each scratch pitch with the source's native
  effective interval before
  stock note ownership and release bookkeeping (`0x4009fbbc` / `0x4009fd04`).
  Chained resolution has a defensive eight-hop bound.
- EVENTS owns transport start/resume (`0x4009c3d4` / `0x4009c4d4`) and
  accepted-note boundaries (`0x4009fbb2` / `0x4009fcfa`). Follow registers
  `bf_seq_start`, `bf_seq_resume` and `bf_seq_note_accepted`. Transport
  notifications reset GRAV after the native PLAYING write, before the native
  continuation. Accepted-note notifications commit GRAV only for nonzero
  velocity and pool kinds other than live keyboard arp (1).
  Callbacks update Follow history only; native packet and release ownership
  remain unchanged. Other subscribers, including EUCLID, receive their own
  notification through the same dispatcher.
- NOTE SETUP's unused D slot is labelled RFOL and enabled. Its encoder callback
  at `0x400bc64e` points to the module; its formatter prints OFF/T1–T8.
  The drawer detour at `0x40036674` reads RFOL from the selected native Part.

Native MIDI SETUP stores RFOL at offset 3 and response in offset 12 bit 1.
Offset 13 packs FIXED octave in bits 0–3 and SOURCE offset+2 in bits 4–6.
Offset 15 packs GRAV home octave in bits 0–3 and REG (FIXED=0, GRAV=1,
SOURCE=2) in bits 4–5. Native ranges are 80 and 48; each getter also
validates its own subfield. Defaults are 0x23 and 0x03. Offset 12 bit 0
is reserved; response and Loopback bits are untouched. This is greenfield,
without legacy migration. UI reads use the selected Part;
playback uses each MIDI track's playing Part through STORE.
`bf_roots[8]` holds the source's bass pitch or 0xff (unknown), and
`bf_pitches[8]` retains full MIDI root pitches. `bf_intervals[8][3]` holds
effective source N2–4 offsets from that root, with 0x80 for absent voices.
These histories are runtime-only.
Native Part operations own persistence, with or without KITS. The generic
MIDI sender is not hooked. The existing DRAM platform reserves about 10 MB of sample RAM;
this small module shares that reserve when composed with other DRAM modules.

## GRAV calculation and lifecycle

For every valid MIDI pitch of the source root's pitch class, calculate
`(candidate - previous)^2 + distance_outside_home_octave^2`. Choose the
lowest score, then the smallest outside distance, then the lower pitch.
Without a previous root, movement is zero. This also gives a valid start
for A–B in partial OCT10. All arithmetic is integer; at most 11 candidates.
There is no PULL, hard range, per-step setting, heap allocation or saved history.

`gravity.c` owns eight 16-byte records (128 runtime bytes). Each records
context/Part epoch, configuration, previous root and a cached proposal.
`bf_register_begin` invalidates the proposal at an ordinary receiver trig;
source pitch-class changes invalidate it for LIVE response. Queries and arp
repeats reuse the proposal, including after it has sounded. The shared
EVENTS accepted-note notifications commit it only for nonzero
velocity sequenced output; the LIVE sender commits only actual note-ons.
The remembered root precedes the follower's TRAN offset.
Native transport start/resume resets all history. Playing Part/epoch and
source/mode/home changes invalidate the affected receiver; unrelated UI
Parts and ordinary pattern changes do not.

Run `python3 modules/midi-follow/upstream/modules/midi-follow/generate.py --check`
for generated assembly, `verify_midi_follow_gravity.py` for linked policy/lifecycle/packing, and
`verify_midi_follow_gravity_port.py --project DIR` for emulated panel events
and full-firmware MIDI output. These are emulator proofs, not hardware tests.

## Root update timing: TRIG / LIVE

Press D on MIDI NOTE SETUP to open RFOL, then turn D inside the window
(**UPDT**, lower left). A/B/C are RFOL, REG and OCT/OFFS.

- **TRIG** is the fresh-Part default and keeps the original behavior: the receiver
  uses the latest source root on its next scheduled note.
- **LIVE** also moves an already-sounding sequenced bass when the ultimate
  source changes root. It sends note-off for the old pitch and note-on for
  the new one, restarting the synth envelope. Rests stay silent. The original
  release deadline and the next programmed trig stay in place.

The setting belongs to each receiver in the native Part and takes effect
from its next ordinary trig (not an arp-only tick).
Source-root changes are handled on the next sequencer service pass, not
held until the next receiver trig. This is not a measured zero-latency claim.
A source change coinciding with a scheduled receiver event does not add an
extra retrigger. Muted/disabled receivers and CHAN OFF do not generate notes.
Only voices owned by that receiver may move; occupied channel/note pairs
are not stolen. Out-of-range voices are omitted rather than wrapped.

LIVE shifts the currently sounding chord by the source-root interval; the
next ordinary trig uses the current source note set. With an arp, its clock/order
are retained and outgoing cached-pool notes track the changed root. It does not trigger during an arp rest or
restart the arp. This control targets sequenced/arp receivers; it does not
retune manually held receiver keyboard notes.

`tools/verify/verify_midi_follow_response.py` checks linked machine code,
release deadlines, silence gates and MIDI ownership. The companion
`tools/verify/verify_midi_follow_response_port.py --project /path/to/project`
operates emulated encoder D and captures the full firmware's MIDI output.
These tests do not establish physical MIDI latency or external-synth timing.


## Eight-track routing stress

`tools/verify/verify_midi_follow_stress.py` is an image gate. It tests all
40,320 permutations of a full eight-track chain, 12,000 seeded live routing
edits, and 56,080 routed outputs with register/transpose extremes, unknown
roots, cycles and invalid links. The independent graph model checks that
editing one receiver cannot change another, no selectable route introduces
a cycle, and runtime fallback terminates without writing outside its scratch
and stack. Run it on both `midi-follow` and `midi-follow-events`.
This exercises linked ColdFire code, not physical outgoing-MIDI timing.

## Instruction budgets

`tools/verify/verify_midi_follow_cpu.py` measures the installed image without
building it. It counts executed guest instructions from each entry through its
return or native continuation, excluding the stopping instruction. The MIDI
enqueue routine is replaced by a packet-recording stub, so queue execution,
wire transmission, interrupt timing and hardware cache effects are excluded.
Cold and warm cases refer to Follow's initialized state, not the processor
instruction cache. These counts do not establish CPU utilization or deadlines.

### LIVE history commit

The LIVE sender commits one shared GRAV root proposal after the voice loop,
only when at least one note-on was emitted. It retains full Part, epoch and
route validation at that commit. GRAV also reuses HOME from the configuration
validated by the current query. Per-service lifecycle checks remain in place;
no routing or Part cache is retained across calls.

Measured on 30 October 2026, relative to source `15e9b168`:

| Case | Before | After |
| --- | ---: | ---: |
| Direct GRAV LIVE, four moving voices | 7,502 | 5,671 |
| Seven-link GRAV LIVE, four moving voices | 11,492 | 7,951 |
| Seven GRAV LIVE receivers, four voices each | 41,858 | 29,041 |
| Seven GRAV LIVE receivers, committed history | 42,089 | 29,272 |
| Seven GRAV LIVE receivers, unchanged source | 11,359 | 11,352 |
| Empty pre-capture pass, RFOL OFF | 1,853 | 1,853 |

The before image is `336e094bf302df58dc06f69d28f1eaba2ffd9b5caafa481c65dd18e0c700d354`;
the after image is `8d6b5b346cffe9265dffdd172374f46f8d6c0b00df8d1984ef9867098d257b23`.
Six LIVE movement budgets require at least 20% fewer instructions than the
before image; that image passes the behavior assertions but fails all six
new budgets. The combined gate passes 143 cases; standalone passes 79.

Regression cases check first-voice collisions, release-only movement, an
upper voice sounding while lower voices are absent/out of range, and Part
epoch publication during a note-on. History advances only for emitted notes;
a replacement discards the stale proposal. Targeted controls that skip or
force a commit, or omit its final synchronization, fail these assertions.
Both selections pass the GRAV policy/lifecycle and LIVE response gates.
The combined full-firmware GRAV capture passes four register/update scenarios
with balanced releases. These optimizations have not been tested on hardware.

### Earlier instruction baseline

On 26 October 2026, all 139 cases passed for the optimized `midi-follow-events`
image. Selected warmed counts compared with commit `f79ad3ca`:

| Case | Before | After |
| --- | ---: | ---: |
| Empty pre-capture pass, RFOL OFF / TRIG | 2,213 | 1,853 |
| Direct FIXED root, KEY OFF | 925 | 612 |
| Seven-link GRAV root, KEY OFF | 3,203 | 2,232 |
| Seven-link GRAV root through MIDI Scales, KEY 25 | 4,144 | 3,141 |
| Unchanged seven-link GRAV LIVE receiver | 5,384 | 4,855 |
| Seven-link GRAV LIVE receiver moving four held voices | 15,309 | 11,492 |
| Seven GRAV LIVE receivers each moving four held voices | 48,609 | 41,858 |
| Direct GRAV LIVE, committed history, four held voices | 8,808 | 7,535 |
| Seven-link GRAV LIVE, committed history, four held voices | 15,342 | 11,525 |
| Seven GRAV LIVE receivers, committed history, four voices each | 48,840 | 42,089 |

The original LIVE cases retain their initially uncommitted GRAV proposals.
The three additional committed-history cases first commit the previously
sounded root, then verify the movement's packets, held voices and unchanged
release deadlines. Their budgets require at least a 10% instruction reduction.

The original image SHA-256 is
`9b476627e979949177a8e87a10a6d048fe6a209f9e21799f00a2a856e0d7b695`;
the optimized combined image is
`2ee2f33f896dccad2f13f455cdbbe5c15790913fcb3ee0eff66e8bdc0984aa39`.
The standalone `midi-follow` image is `1947d51c1f840f2196e6341c9c54074faad711753e27c4fd8fe552e19ce4e6e5`;
its 75 instruction/lifecycle cases and 59 measured-path budgets also pass.
Both images pass the 28,800-case native KEY oracle. The combined image additionally
passes the six STORE Part gates, Follow routing/notes/register/response/GRAV/stress,
and Loopback settings/context checks. Five project-backed commands cover native
Part save/reload/clear/paste, four-voice playback, all 12 TRIG/LIVE response cases,
register controls and GRAV, with balanced note releases. These are focused
software checks; the CI whole-remix matrix, hardware timing and maximum load are
separate qualification.

The gate enforces 123 measured-path budgets: at least a 10% reduction from the
original counts, except unchanged/settled long-chain and seven-receiver GRAV,
which require at least 8%. An unchanged source token cannot safely skip target
validation: TRAN can move the effective note out of range, and Part changes can
invalidate a held-note anchor. Those checks remain. The preserved original
image reproduces every recorded baseline count and fails all 123 performance
budgets, while passing the musical-behavior assertions.

Regression cases also cover a LIVE Part changing to a TRIG Part and back without
a new trig, pending GRAV proposals invalidated before accepted-note callbacks,
source/register edits, and enabling a follower during a rest after its muted
source was captured. STORE retains its shared system hooks, coherent Part APIs,
snapshot publication and replacement epochs. Only absent optional companion
callbacks and their empty setup/replacement walk are compiled out; the shared
service remains available.

After building the desired composition, run:

```sh
.venv/bin/python tools/verify/verify_midi_follow_cpu.py midi-follow-events
```

The receipt is `out/midi-follow-events-follow-cpu.json`, including image/runtime
hashes, per-case counts, called-symbol histograms and budgets. Use
`--artifact-root PATH/out --record-only --output PATH.json` to measure a
preserved image without enforcing the optimized budgets. Preserve its
`mainos_bus.remix` marker alongside the image, layout and runtime files: the
gate checks the requested remix and image hash, and refuses artifacts changed
during measurement. The same command with
`midi-follow` checks a built standalone image.

## Verification

Run `make check REMIX=midi-follow` for the standalone module. The manifest
runs linked routing, register, response, graph stress and instruction-budget
checks. With a prepared
project copy, `verify_midi_follow_response_port.py --project DIR` checks LIVE
response through emulated panel events and captured MIDI output.

### Limited MKII hardware pass, 29 October 2026

MFOL29U / BUILD FA is the USB MIDI test selection based on implementation commit
`c89b1e59`, with source pin `15e9b168`. Image SHA-256:
`67e25a32515128f3f6e9de7343215160d6c948b45c9b98fa59415ac813beffdd`.
The operator confirmed the MKII model and loaded candidate/project; image identity
was not read back from the device.

- Two complete source/follower cycles at OCT 3: 128 USB MIDI note events,
  matching the expected four-note chords and independent follower rhythm.
- Three STOP-while-held runs: 72 events, with all four held follower voices
  released and no subsequent note-ons before the next START.
- Part SAVE at OCT 4, change to OCT 5, RELOAD: OCT 4 returned on the device display.
- Project save and power-cycle: OCT 4 remained on the device display; a further
  two-cycle capture (128 events) matched the expected OCT 4 chords.

All three captures had balanced releases, no duplicate note-ons, unexpected
channels or parser/callback errors. The driver sent only START/STOP. Persistence
is supported by physical UI observations and the post-reboot MIDI output; the
power-cycle was performed on the device. Host timestamps do not measure
DIN latency. Visual KEY locking, MKI, sustained maximum load and the broader
composition matrix remain unverified on hardware.


## Octabam composition and full-firmware captures

EVENTS owns the shared transport and accepted-note hooks. The `midi-follow-events`
test remix combines Follow with EUCLID, PLOCKS P2, MIDI Scales and MIDI Loopback;
no EUCLID runtime change or separate bridge is required. The Scales adapter keeps
its standalone author reference and uses installed-image gates when resolving
Follow symbols. The builder preserves the final runtime provider's exports when
relinking resident imports, so EUCLID descriptor references retain their final
addresses alongside STORE native Part access.

Build the selected remix, then run the project-backed checks on a disposable
template with `--project DIR`: `verify_midi_follow.py midi-follow-events`,
`verify_midi_follow_register_port.py`, `verify_midi_follow_response_port.py`,
`verify_midi_follow_gravity_port.py` and `verify_midi_follow_voices_port.py`.
All are under `tools/verify/`. They cover routing and OFF equivalence, three-mode
packing and control isolation, native chord TRIG/LIVE response, GRAV movement,
four-voice output into empty follower slots, and matching note releases.

EUCLID currently has no declared worst-case `Module.dear` settings. The combined
remix can run functional and project-backed checks, but the strict acceptance
runner reports its pressure stages blocked until that profile is supplied.
The limited MKII checks above do not qualify this combined remix on hardware.
