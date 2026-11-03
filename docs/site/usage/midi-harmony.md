Turns scale-degree roots into notes or chords using the MIDI ARP KEY, with
inversions, automatic voice leading, spread and root placement.

Supported scales are the seven diatonic modes: Major, Dorian, Phrygian,
Lydian, Mixolydian, natural Minor and Locrian. The selected scale module must
provide a compatible integration; additional catalogue scales are not yet
supported by Harmony. Existing project formats are unchanged.

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

![MIDI NOTE SETUP with HARM CHORD](../../img/midi-harmony/note-setup.png)

Press **F** on NOTE SETUP to open **HARMONY**.
UP/DOWN selects CHORD or ACCUM. HARM OFF/NOTE/CHORD stays on the parent page.

![Harmony chord settings](../../img/midi-harmony/chord.png)

![Harmony accumulator settings](../../img/midi-harmony/accum.png)
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
See [Voicing](https://github.com/radiohagen/octatrack-modules/blob/cb11475731eab5dc35f1ec6a93a497e6dcaaf77b/modules/midi-harmony/VOICING.md) for the musical rules.

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

Follow is optional. When selected, it supplies the source note set.
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

Requires **STORE** (including native Part access), **MIDI SRAM** and **EVENTS**.
HARM and PLOCKS P2 register independently with EVENTS;
no combination-specific bridge is selected. KITS libraries are per
project; recalling a kit supplies Part defaults while pattern locks stay with
the patterns. See [storage](https://github.com/radiohagen/octatrack-modules/blob/cb11475731eab5dc35f1ec6a93a497e6dcaaf77b/modules/midi-harmony/DEVELOPMENT.md#compact-harmony-storage) and [KITS](https://github.com/radiohagen/octatrack-modules/blob/cb11475731eab5dc35f1ec6a93a497e6dcaaf77b/modules/midi-harmony/KITS.md).

[Implementation, provenance and verification](https://github.com/radiohagen/octatrack-modules/blob/cb11475731eab5dc35f1ec6a93a497e6dcaaf77b/modules/midi-harmony/DEVELOPMENT.md).
