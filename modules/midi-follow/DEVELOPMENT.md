# MIDI Follow

Each MIDI track can follow another MIDI track's logical note set while keeping its
own rhythm, velocity and note length. By default, FIXED octave 3 with TRAN=0 uses MIDI notes 36–47 for the root:
C → F → G gives 36 → 41 → 43. The follower's TRAN adds a signed semitone
offset after its register choice. Scale Quantizer is not required.

## Composition and controls

Select `MIDI FOLLOW` with `MIDI PART STATE` and `EVENTS`. Scales and KITS
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
  including parameter locks, is added after root selection without an additional
  scale correction. These are chromatic semitones, not scale degrees; +7 is
  always a perfect fifth, even when that pitch falls outside the source scale.
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
playback uses each MIDI track's playing Part through MIDI PART STATE.
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

## Verification

Run `make check REMIX=midi-follow` for the standalone module. The manifest
runs linked routing, register, response and graph stress checks. With a prepared
project copy, `verify_midi_follow_response_port.py --project DIR` checks LIVE
response through emulated panel events and captured MIDI output. Hardware
validation of boot, controls, persistence, MIDI timing and note releases remains
outstanding.


## Octabam composition and full-firmware captures

EVENTS owns the shared transport and accepted-note hooks. The `midi-follow-events`
test remix combines Follow with EUCLID, PLOCKS P2, MIDI Scales and MIDI Loopback;
no EUCLID runtime change or separate bridge is required. The Scales adapter keeps
its standalone author reference and uses installed-image gates when resolving
Follow symbols. The builder preserves the final runtime provider's exports when
relinking resident imports, so EUCLID descriptor references retain their final
addresses alongside MIDI Part State.

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
This is separate from Follow's hardware acceptance, which remains outstanding.
