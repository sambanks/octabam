# MIDI Harmony

Turns scale-degree roots into notes or chords using the MIDI ARP KEY, with
inversions, automatic voice leading, spread and root placement.

Supported scales are the seven diatonic modes: Major, Dorian, Phrygian,
Lydian, Mixolydian, natural Minor and Locrian. The selected scale module must
provide a compatible integration; additional catalogue scales are not yet
supported by Harmony. Existing project formats are unchanged.

The [combined MIDI remix](../../remixes/midi/README.md) brings Harmony, Follow, Scales and Loopback together.
Harmony also works independently; the smaller combinations are test carriers.

## Start playing

1. Set the MIDI track's output channel and choose **KEY** on **ARP SETUP**
   (**FUNC + AMP**). MIDI Scales adds five more modes to Major and Minor.
2. Open **NOTE SETUP** with **FUNC + SRC** and turn **F: HARM**:

| HARM | Result |
| --- | --- |
| OFF | Native NOTE and NOT2–4. |
| NOTE | One scale-degree root; the NOTE page shows DEG. |
| CHORD | A chord from that root; the NOTE page shows DEG and CHRD. |

3. Program DEG 1, 4 and 5 on three trigs. In C minor with CHRD TRI, these
   play Cm, Fm and Gm. Changing KEY to D minor gives Dm, Gm and Am.

DEG `1:3` means degree 1 in tonic octave 3. Turn DEG to move through the scale;
**FUNC + DEG** changes only the octave. Hold steps to edit DEG/CHRD locks;
press the corresponding encoder while holding steps to toggle the locks.

Press **F** on NOTE SETUP to open **HARMONY**.
UP/DOWN selects CHORD or ACCUM. HARM OFF/NOTE/CHORD stays on the parent page.
CHORD controls follow the displayed positions: A/B/C across the top and D
at bottom left. Empty E/F cells ignore turns.

| Encoder | Control | Choices |
| --- | --- | --- |
| A | VOIC | ROOT, AUTO voice leading, 1ST, 2ND or 3RD inversion. |
| B | SPRD | CLOSE, OPEN or WIDE. |
| C | ROOT | KEEP, OMIT, -1 OCT or -2 OCT. |
| D | SIZE | NAT recipe size, or 2, 3 or 4 voices. |

These are track settings affecting CHORD, not NOTE.
Existing held notes retain their original releases.
See [Voicing](https://github.com/radiohagen/octatrack-modules/blob/9da50248a263650afcad41895b7f6fc83e0296d5/modules/midi-harmony/VOICING.md) for the musical rules.

## Degree accumulator

**NOTE MAIN E: ACC** edits the pattern/track's
default amount: OFF or −7…−1 / +1…+7 scale degrees. Hold trigs and turn E for
independent step overrides; press E while holding trigs to add/remove locks.
An unlocked step inherits the default. OFF is an explicit override, not a
zero/freeze setting.

Each step's first sounding occurrence is unshifted. Its amount then advances
the next occurrence. Rests, failed conditions and suppressed outputs do not
advance it; chord voices and arp repeats share the same captured root shift.
Live keyboard notes do not accumulate.

Select ACCUM in the Harmony window:

The left CHORD/ACCUM menu remains visible. Controls use the native six-position
encoder grid: A/B/C across the top and D/E/F below, with E/F empty and inactive.
Each title sits above its native dial (LOW/HIGH) or four-way switch
(BOUND/RESET), followed by the value. ACCUM omits the footer to keep those
three bands separate; CHORD retains its existing footer.

| Encoder | Setting | Values; default |
| --- | --- | --- |
| A | LOW | −21…0 degrees; 0 |
| B | HIGH | 0…21 degrees; 7 |
| C | BOUND | WRAP / BOUNC / HOLD / ZERO; WRAP |
| D | RESET | NONE / START / PAT / BOTH; BOTH |

Seven scale degrees are one octave, so each limit allows up to three octaves.

These settings cannot be step-locked. Limits include both endpoints. WRAP
wraps the overshoot, BOUNC reflects it and reverses direction, HOLD clamps,
and ZERO returns to zero. START resets on transport start/resume; PAT resets
when the track changes pattern; BOTH combines them. NONE carries each step
number's running offset across patterns. Changing an amount resets that step;
changing the default or limits/policy resets the playing track's offsets.

Follow supplies root/register and KEY first, then ACC shifts in degrees,
then native semitone TRAN and scale correction apply before chord/arp output.
ACC settings and overrides belong to the pattern/track, not to a Part or Kit.
Copy/paste/undo includes them; clearing step locks restores inheritance.
Configuration survives save/reload and retained restart; running offsets are
volatile and start at zero after project load or power-on.

## MIDI Follow

Both modules register with [EVENTS](https://github.com/radiohagen/octatrack-modules/blob/9da50248a263650afcad41895b7f6fc83e0296d5/docs/SYSTEM_EVENTS.md)
to share transport and successful-note events. Follow supplies a source note set.
A HARM OFF source supplies N1–4; a HARM NOTE/CHORD source supplies only its
resolved degree:oct root as Note 1. HARM OFF on the follower plays the supplied
set. HARM NOTE/CHORD on the follower generates its own notes from that root.
The source's generated chord voices are ignored.

With Follow UPDT set to LIVE, held scale chords move by scale degree,
keeping their inversion and octave spread. For example, C–E–G becomes D–F–A
in C major. Explicit MAJ/MIN/DOM7 chords and KEY OFF retain chromatic intervals.
Cached arp notes use the same movement without resetting the arp clock; note-off
ownership and the original release deadlines remain attached to the held notes.

## Chord Play

With HARM CHORD, select **CHORD PLAY** using FUNC + UP/DOWN.

- Trigs 1–8 play scale roots from tonic to the next octave.
- Trigs 9–16 select TRI, 7TH, ADD9, SUS2, SUS4, MAJ, MIN and DOM7.
- Pressing a variation changes held chords immediately. Releasing it is silent;
  the next root uses the latest still-held variation, or the base CHRD.
- Live recording stores root degree and chord choice, not generated chord tones.
- FUNC + LEFT/RIGHT changes the playing octave. The display shows the sounding chord.

TRI/7TH/ADD9/SUS choices follow the scale. Explicit MAJ/MIN/DOM7 keep their
chromatic intervals. KEY OFF uses C major for degree mapping. With Follow,
the root and KEY come from the source; rhythm and chord settings remain local.

## Storage and compatibility

HARM, KEY, voicing, SIZE and default DEG/CHRD are native Part settings.
Pattern DEG/CHRD locks and accumulator configuration live in the project's `hdeg01.work`–`hdeg16.work` and
their `.strd` companions. Keep them with the project. Incompatible companions
are protected from overwrite. Runtime accumulator offsets restart at zero;
only the configuration is saved.

Turning HARM OFF writes resolved roots back to native NOTE. It preserves
NOT2–4 but does not render generated chords into those fields.

**Keep a separate project copy for stock firmware.** With HARM active, native
NOTE fields are storage mirrors and can play different pitches on stock.
Stock also resets voicing/spread/root choices and clamps extended KEY modes
to B Minor; saving persists those changes for the bank written.

Requires **STORE** and **EVENTS**. STORE automatically includes native Part
access and retained MIDI storage when Harmony is selected; there is no extra
storage module to select. Harmony registers its existing full 16 KB layout
with STORE’s retained-memory service; STORE owns the code and reservation
checks independently of Harmony. MIDI Follow and MIDI Scales remain optional.
HARM and PLOCKS P2 register independently with EVENTS;
no combination-specific bridge is selected. KITS libraries are per
project; recalling a kit supplies Part defaults while pattern locks stay with
the patterns. See [storage](https://github.com/radiohagen/octatrack-modules/blob/9da50248a263650afcad41895b7f6fc83e0296d5/modules/midi-harmony/DEVELOPMENT.md#compact-harmony-storage) and [KITS](https://github.com/radiohagen/octatrack-modules/blob/9da50248a263650afcad41895b7f6fc83e0296d5/modules/midi-harmony/KITS.md).

[Implementation, provenance and verification](https://github.com/radiohagen/octatrack-modules/blob/9da50248a263650afcad41895b7f6fc83e0296d5/modules/midi-harmony/DEVELOPMENT.md).

## Verification boundary

This integration is checked in software; it has not been flashed on an Octatrack.
Standalone Harmony and Harmony with Follow are separate test selections, each
with stock KEY and with MIDI Scales. Follow is optional. Fresh author-source
assembly is compared with the bytes unpacked from the built firmware.

The native Part field and retained allocation contracts remain unchanged.
Guarded STORE callbacks refuse writes to incompatible companions and propagate
copy failures. Playback, ownership, corruption and native copy/clear checks
exercise the declared module gates; these do not measure hardware timing.

### Measured Follow composition cost

Installing Harmony adds Part-safe pitch-policy checks even when all HARM
controls are OFF. The counts below execute the installed code with MIDI queue
I/O stubbed; they are instructions, not processor cycles or hardware latency.
Both columns use author source `cb114757` on Octabam `5a18f0ce`, with MIDI Scales.

| Case | Follow | Follow + Harmony |
|---|---:|---:|
| All receivers OFF, warm tick | 1,776 | 1,776 |
| One FIXED receiver, warm root, KEY OFF | 641 | 828 |
| One FIXED receiver, warm extra voice through Scales | 942 | 1,318 |
| Seven FIXED receivers, unchanged LIVE root | 5,038 | 6,452 |
| Seven GRAV receivers, unchanged LIVE root | 11,352 | 12,766 |
| Seven GRAV receivers, four moved LIVE voices | 23,245 | 25,366 |

Standalone Follow retains its existing optimization limits. The first Harmony
composition establishes separate exact ceilings for all 79 native-KEY and 143
MIDI Scales cases in `tools/verify/harmony_follow_cpu_baseline.json`; it also
retains the earlier combined LIVE batching limits. The report keeps the
standalone thresholds and their excesses visible (54 cases with Scales).
These ceilings prevent further instruction regressions; they do not establish
hardware capacity or imply that the added policy is free.

## Lifecycle instruction bounds

Harmony source is pinned to `9da50248a263650afcad41895b7f6fc83e0296d5`. Its lifecycle changes are
[reviewable against the prior pin](https://github.com/radiohagen/octatrack-modules/compare/cb11475731eab5dc35f1ec6a93a497e6dcaaf77b...9da50248a263650afcad41895b7f6fc83e0296d5).
The original **20,000-instruction** call limits are unchanged. The temporary
40,000 override has been removed; the previously failing lifecycle gates now
pass through implementation changes.

| Operation in the earlier MIDI-only composition | Before | After |
| --- | ---: | ---: |
| Follow fixture: same-Part replacement | 32,514 | 6,704 |
| Follow fixture: unrelated-Part replacement | 32,526 | 6,716 |
| Follow register fixture: HARM mode edit | 31,784 | 16,039 |

Those original Follow fixtures do not initialize the complete Harmony bank.
The new lifecycle gate also starts with initialized retention and an empty
native bank: mode edits measure 3,021 / 9,202 / 9,734, inactive Part copies
7,839 / 7,747, attached mode edits 2,939 and a restored Part copy 8,422.
Every measured operation must complete under the same 20,000 limit. The gate
checks immediate invalidation, coalesced saves, restore of the latest degree,
reattachment after restore and early exit on invalid payloads.

Part replacement now uses a 256-byte runtime bitmap to visit attached Harmony
provenance, preserving cross-bank Follow dependencies and outgoing KEY capture.
Reset and load clear the index; playback rebuilds it. It is not saved.
Mode edits still convert notes immediately and invalidate the old checkpoint,
but request serialization at the existing UI poll. Repeated edits coalesce;
explicit saves remain synchronous. A request during an existing write forces
the writer to retry. Failed root packing stops before accumulator packing.

The background full-bank save still costs hundreds of thousands of
instructions; it has been removed from the immediate mode-edit call, not
eliminated. The separate eight-active-track interrupted-copy gate measures
24,245–26,989 instructions under its existing bound. The 20,000 limits above
cover the named fixtures, not every possible dense-bank operation. Retained
formats and commit ordering are unchanged. Incomplete checkpoints retain the
existing validated-companion fallback. Emulator instruction counts do not
establish processor cycles or hardware latency; physical qualification remains
open.

CHORDS FACTORY and Harmony coexist through TRIG MODES. Factory's CHORDS
(mode 2) stores absolute pitches on HARM OFF tracks; Harmony's CHORD PLAY
(mode 6) stores degrees and chord choices on other tracks. Factory refuses
live playing/recording and pattern insertion on HARM-enabled tracks with
CHORDS NEEDS HARM OFF. Atelier preview remains an audition.

SCALES and MIDI SCALES are both supported providers. SCALES retains all 52
choices on ordinary tracks; HARM requires one of the seven diatonic modes,
including when KEY is inherited through FOLLOW. Unsupported combinations show
HARM NEEDS DIATONIC SCALE and suppress new Harmony notes while retaining degree
data. Choose a supported scale before changing HARM, including turning it OFF.
Existing note releases remain valid. No persisted layout changes.
