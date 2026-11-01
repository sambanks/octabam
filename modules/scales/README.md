# SCALES

One catalogue of scales that every module can use, a scale chooser of
MAIN MENU's size, and the CHROMATIC trig keys lit with the scale.

- **The catalogue**: 52 scales in 9 families, each a 12-bit mask over the
  semitones above its tonic (IONIAN, written from the tonic up, is
  `1010 1101 0101`: C . D . E F . G . A . B). A scale's ID names it for
  good: a saved ID never changes meaning, a new scale takes the next ID.
- **The chooser**: a window of MAIN MENU's size, drawn as SYSTEM >
  PERSONALIZE is (the band, the title, an icon, five rows, the scroll
  arrows), in two levels: the families, then one family's scales. RIGHT
  or YES enters a family, LEFT goes back to the families, YES picks a
  scale, NO closes it. The scale in use is marked: its short name on its
  family's row, a ticked box on its own row. A module opens it with
  `sc_pick` and gets the ID.
- **ARP SETUP's KEY** (a MIDI track, FUNC + AMP, encoder F): turned, the
  tonic (OFF, C .. B), one a detent, the scale kept (no quick edit: a
  turn with F pushed is one step too); pressed and released without a
  turn, the chooser. The sequencer's and the arpeggiator's notes snap to
  the scale (nearest note, ties downward). The field shows the tonic and
  the scale's short name (`C#` `PHRD`).
- **The CHROMATIC keys** light the track's scale in stock's colours: the
  tonic yellow, the scale's other notes red, the rest dark. On a MIDI
  track key 1 is C, as stock's keyboard is; on an audio track with
  [SCALE QUANTIZER](../quantizer/README.md) in the remix, its SCALE on its
  ROOT, key 1 = ROOT, as its keyboard plays.

KEY OFF, SCALE OFF and an audio track without SCALE QUANTIZER keep stock's
C major. `Kind.CF_PATCH`: one DRAM unit (`scales.s`, about 4.3 KB), four
detours, a poke and a pointer.

| family | scales (ID, short name) |
| --- | --- |
| MAJOR | 1 IONIAN (MAJOR) `MAJ`, 2 DORIAN `DOR`, 3 PHRYGIAN `PHR`, 4 LYDIAN `LYD`, 5 MIXOLYDIAN `MIX`, 6 AEOLIAN (MINOR) `MIN`, 7 LOCRIAN `LOC` |
| MELODIC MINOR | 8 MELODIC MINOR `MMIN`, 9 DORIAN b2 `DOb2`, 10 LYDIAN AUGMENTED `LYD+`, 11 LYDIAN DOMINANT `LYDD`, 12 MIXOLYDIAN b6 `MXb6`, 13 LOCRIAN #2 `LC#2`, 14 SUPERLOCRIAN `ALT` (the altered scale) |
| HARMONIC MINOR | 15 HARMONIC MINOR `HMIN`, 16 LOCRIAN #6 `LC#6`, 17 IONIAN #5 `IO#5`, 18 DORIAN #4 `DO#4`, 19 PHRYGIAN DOMINANT `PHRD`, 20 LYDIAN #2 `LY#2`, 21 ALTERED bb7 `ALT7` |
| HARMONIC MAJOR | 22 HARMONIC MAJOR `HMAJ`, 23 DORIAN b5 `DOb5`, 24 PHRYGIAN b4 `PHb4`, 25 LYDIAN b3 `LYb3`, 26 MIXOLYDIAN b2 `MXb2`, 27 LYDIAN AUG #2 `LA#2`, 28 LOCRIAN bb7 `LCb7` |
| DOUBLE HARMONIC | 29 DOUBLE HARMONIC `DHAR`, 30 LYDIAN #2 #6 `L#26`, 31 ULTRAPHRYGIAN `UPHR`, 32 HUNGARIAN MINOR `HUNG`, 33 ORIENTAL `ORNT`, 34 IONIAN #2 #5 `I#25`, 35 LOCRIAN bb3 bb7 `LC37` |
| PENTATONIC | 36 MAJOR PENTATONIC `PMAJ`, 37 EGYPTIAN `EGYP`, 38 MAN GONG `MGNG`, 39 RITUSEN `RITU`, 40 MINOR PENTATONIC `PMIN` |
| BLUES | 41 BLUES `BLUS`, 42 MAJOR BLUES `BMAJ` |
| JAPANESE | 43 HIRAJOSHI `HIRA`, 44 IN-SEN `INSN`, 45 IWATO `IWAT`, 46 KUMOI `KUMO`, 47 PELOG `PELG` |
| SYMMETRIC | 48 WHOLE TONE `WHOL`, 49 DIMINISHED W-H `DWH`, 50 DIMINISHED H-W `DHW`, 51 AUGMENTED `AUG`, 52 CHROMATIC `CHRM` |

A family with modes lists them in the order of its parent scale's degrees.
SCALE QUANTIZER's 24 scales are all in the catalogue.

**IDs.** A scale's ID is what a project keeps (`scales.work`) and what
other modules name it by, so a published ID never changes meaning and is
never reused; a name can still be corrected, nothing stores it. IDs
1..127 are the catalogue's: a new scale takes the next one. IDs 128..254
are kept for scales a module declares (none yet); 0 (the KEY's own mode)
and 255 are never a scale. The chooser's rows come from `sc_order`, each
family's IDs in turn, not from the IDs, so a scale added later can join
any family at any row.

## Service

For other modules: register calls, d0-d1 / a0-a1 scratch, the rest kept.

| entry | input | result |
| --- | --- | --- |
| `sc_count` | | d0 = the number of IDs (52) |
| `sc_mask` | d0 ID | d0 = its mask (bit d = d semitones above the tonic), 0 for no such ID |
| `sc_name` | d0 ID | a0 = its name, as the chooser lists it; d0 = 0 for no such ID |
| `sc_short` | d0 ID | a0 = its 4-character name (NUL-padded), d0 = 0 for no such ID |
| `sc_family` | d0 ID | d0 = its family 0..8, -1 for no such ID |
| `sc_snap` | d0 note 0..127, d1 = ID << 4 \| tonic | d0 = the nearest note of the scale, ties downward; every other register kept |
| `sc_track` | d0 MIDI track 0..7 | d0 = ID << 4 \| tonic of its KEY, -1 for KEY OFF |
| `sc_pick` | d0 the ID shown first, a0 the routine to call | the chooser (UI task only); a0 is called with the chosen ID in d0, as a C routine |

A module that needs a scale asks here rather than carrying its own table,
and one that lets the player choose a scale calls `sc_pick` rather than
drawing its own list. A module's new scales come here: the catalogue's
next IDs, or later IDs from 128 that the module declares.

## A MIDI track's scale

The KEY (setup record `+0x11`) keeps what stock (1..24: 12 tonics x Major /
Minor) and [MIDI SCALES](../midi-scales/README.md) (25..84: Dorian,
Phrygian, Lydian, Mixolydian and Locrian per tonic) wrote, so a project
saved with either plays the same. The KEY is stored as stock's ARP SETUP
writer stores it (`0x4007a3ea..`): the Part byte, the CS1 mirror, the four
unsaved flags, `0x40027e00`, the live byte.

A scale outside the seven diatonic modes keeps its ID in `sc_lib`, one
byte per bank, Part and MIDI track (512 bytes), saved with the project in
`scales.work`; the KEY then holds the tonic in Major or Minor (Minor when
the scale has a minor third and no major one), which is what stock plays
for it. The native setup record has no byte to spare: its four setup
pages' empty slots (NOTE SETUP D and F, ARP SETUP A, B, D and E, CTRL1
SETUP A and B, read from the pages drawn under the port) are MIDI FOLLOW's
and MIDI HARMONY's (`modules/store/parts.py`). SCALES wrote `+0x12` until
MIDI HARMONY's byte 18 was found there (#980), and now writes no native
byte beyond the KEY.

**The ID holds while the KEY agrees with it**: KEY OFF (the ID waits for a
tonic), or the Major or Minor that stands for it, on any tonic. A KEY
changed another way (a Part reload or paste, a KEY turned on stock, a
MIDI SCALES mode) gives the KEY's own mode back, so `sc_lib` never plays
a scale the Part no longer asks for.

**Which Part.** The playing notes use the Part the MIDI engine plays
(`store_part_midi_context`), the KEY field, the chooser and the keys the
Part the UI edits (`store_part_ui_context`); the KEY is read through
STORE (`store_part_midi_key`). SCALES is registered as a STORE Part client
with the MIDI setup window to read and no byte to write.

**scales.work** (a STORE client, `modules/store`): a 16-byte header
(`SCLS`, version 1, length 512, the CRC-32 of the IDs) then `sc_lib`,
beside the bank files. Written by the bank writer and before the project
store when an ID changed; `scales.strd` is its copy at the project store,
copied back at a project reload. A load of every bank reads every bank, a
masked load those banks; no file is no scale past the KEY's own. Part
Clear empties that Part's IDs. A file that is not version 1 or fails its
CRC is refused: STORE's prompt (client 6, SCALES NOT LOADED), never
written over unless the answer says so.

## How

| site | what |
| --- | --- |
| `0x400442e2` (12 bytes: `clrl %d5; clrl %d4; clrl %d6; lea 0x400135b0,%a3`) | the trig-LED pass's CHROMATIC branch: `kl_chromatic` |
| `0x40056ab8` (6 bytes: `tstl 0x460d1e4c`) | the UI task's per-tick routine: `kl_tick` (the chooser's push, the LED refresh) |
| `0x4007a3e2` (8 bytes: `moveq #5,%d1; cmpl %d0,%d1; bnew 0x4007a4cc`) | ARP SETUP's encoder handler: `sc_encoder`, encoder F |
| `0x4009fb58` (6 bytes: `tstl %fp@(-64); bles 0x4009fb80`) | stock's output quantization: `sc_output` |
| poke `0x400d4096` 25 -> 85 | ARP SETUP KEY's value count |
| pointer `0x400d40c6` `0x4003b790` -> `sc_format` | ARP SETUP KEY's formatter |

The encoder and output sites and the poke are MIDI SCALES' own, which
SCALES takes over (it reads MIDI SCALES' values and plays its modes).

**The push.** Stock does nothing on encoder F's push in ARP SETUP (under
the port, 30 Oct 2026: the KEY byte written by the turn, never by the
push). `kl_tick` watches the push switch's key record (code `0x3d`,
`0x46c7d8de + 0x10 + code * 0x18`, as CXOSC reads it) while ARP SETUP is
open (`0x400cfebe` nonzero) in MIDI mode; a release with no F turn since
the push (stock's quick edit turns with the knob pushed) and no list,
dialog or text editor open (`0x460e5e30`, `0x460e5cd0`, `0x460e7612`)
opens the chooser, from the UI task.

**The chooser** is STEMS's window recipe (`docs/firmware/MAINMENU.md`
section 5): `0x4005829c(118, 64, -1, 0, 5, sc_close)`, its own key layer
pushed (`0x40031494`: UP, DOWN, LEFT, RIGHT, YES, NO), and each key ends
in `sc_draw`, which draws as MAIN MENU draws PERSONALIZE: MAIN MENU's band
(`<set>/<project>`), the inside cleared, the title right-aligned (SCALES,
or the family), the icon, a rule, five rows from the top row with the
cursor's inverted from x 3 to 107, the scroll arrows. NO and a pick
destroy the window (`0x40055db4`) and pop the layer. A level's rows are a
run of one table of name pointers, so nothing is built at run time.

**The turn.** `sc_encoder` maps the KEY to an ordinal (OFF, C .. B), adds
stock's detent accumulator's step (`0x40032510(5, movement, 1024)`, four
counts a step, one step a report, as MIDI SCALES does), and gives stock's
store the change in d5. The mode is kept; from OFF it is `sc_lib`'s
scale's (Major for none).

**The output.** `sc_output` snaps the note at `(a2)` for track d7 when the
scale is one stock does not play (MIDI SCALES' modes, `sc_lib`'s IDs);
stock's Major / Minor and OFF go to stock's own path.

**The keys.** `kl_chromatic` asks `kl_source` for the current track's
(`0x80000000`) scale and sets the 32 levels and bits as stock's loop does,
then goes where stock goes after the 16th key (`0x400444f4`, d3 = 0);
without an answer stock's loop runs. Stock runs the pass when a key or a
mode change asks the LED dispatcher (`0x4007e998(slot)`), not when a KEY,
a SCALE or a ROOT is turned, so `kl_tick`, in CHROMATIC, asks `kl_source`
each tick and calls `0x4007e998(0)` when the answer differs from the one
the keys show.

## Sources

The keys ask one question; the answers are chosen at build time
(`remix.inc`, `manifest._sources`).

| entry | input | result in d0 |
| --- | --- | --- |
| `kl_source` | d0 = track 0..7, d1 = 0 audio / 1 MIDI | `mask << 8 \| key1 << 4 \| tonic`: mask bit p = pitch class p is in the scale, key1 = the pitch class trig key 1 sounds, tonic = the scale's (C = 0 .. B = 11); or -1: stock's keyboard |

| side | in the remix | the source |
| --- | --- | --- |
| MIDI | always | `sc_track`: the KEY and `sc_lib`, key 1 = C |
| audio | SCALE QUANTIZER | its own `SCALE_AT` (`0x400d2ca8`, the pinned `jmp qz_scale_mask`: the SCALE's pitch classes rotated by ROOT, 0 = OFF) and ROOT (`0x100b14ee`); its keyboard plays ROOT on key 1 (its README), so key1 = tonic = ROOT |
| audio | otherwise | none: stock's keyboard |

A module that knows a track's scale answers here instead of drawing LEDs
of its own: one more `HAVE_<NAME>` in `_sources` and its branch in
`kl_source`, calling the module's own routine.

## Guards

- **Every table index is checked.** An ID outside 1..52 is refused by
  every service entry; a KEY past 84 or 0 is OFF; an ID in `sc_lib` past
  52, or one the KEY does not agree with, means the KEY's own mode.
- **Stock's scales stay stock's.** KEY 1..24 with no ID goes to stock's
  output path, as without the module.
- **The push is only a press.** A push with a turn is stock's quick edit;
  nothing opens over the chooser, stock's list window, a dialog or a text
  editor, or outside ARP SETUP on a MIDI track.
- **No native byte but the KEY.** The setup record's other bytes are
  stock's or other modules' (`+0x12` is MIDI HARMONY's); the gate checks
  every chooser run leaves `+0x12` as the project had it. On stock, a
  track with an ID plays the KEY's Major or Minor, and stock leaves
  `scales.work` alone.
- **Only the CHROMATIC branch.** The other trig modes, the running light
  and every other LED are untouched.

## Conflicts

MIDI SCALES, declared: both own ARP SETUP's KEY (the same encoder and
output detours and poke). SCALES reads MIDI SCALES' KEY values and plays
its modes, so a project made with MIDI SCALES keeps its scales.
BLACKPYRAMIDS_303 detours the trig-LED pass at `0x40044006`, a different
span.

SCALE QUANTIZER as pinned (v2.9) does not snap MIDI tracks' notes. Its
author's later line does, at `0x4009fb80` (timhastie, #980), where
`sc_output` (`0x4009fb58`) ends: with that line in the same image,
SCALES' scale applies first and SCALE QUANTIZER's SCALE / ROOT after it,
the order SCALE QUANTIZER documents for stock's KEY. Inferred from the
two sites; not run until that line is pinned.

## Measured

- `tools/verify/verify_scales.py`, its model built from music (each
  family's modes as rotations of its parent scale, the others as semitone
  lists, SCALE QUANTIZER's 24 from its README), not from the module's
  tables:
  - the linked code under unicorn, the image's own bytes: every ID's mask,
    family and names, the refusals; `sc_snap` for every ID x tonic x note
    (79,872); `sc_track` for every KEY 0..255 x 9 IDs in `sc_lib` (the ID
    held only while the KEY agrees); the installed output on 8 tracks
    (3,840 notes, stock's paths included); the installed encoder for every
    KEY 0..84 x 5 IDs x 7 movements (2,975); the formatter's two strings
    and its bounds; the contexts and the KEY through STORE;
  - under the ColdFire port, MKI and MKII, on `test/scales`: the trig
    LEDs from the panel stream for every KEY 0..84 and every ID 8..52 on a
    tonic, a KEY turned while CHROMATIC is shown; the chooser driven from
    ARP SETUP's keys for each of the 52 IDs, the KEY read back from the
    Part, the CS1 mirror and the live copy, the ID from `sc_lib`, `+0x12`
    unchanged; reopened (YES YES keeps the scale), NO, F turned while
    pushed (no window), the window left open after a plain push, RIGHT
    into a family and LEFT back; CTRL1 SETUP's YES. 132 LED and 58
    chooser runs per model, all equal;
  - `scales.work` under the port, MKII: a scale picked then SAVE PROJECT
    writes `scales.work` and `scales.strd` (header, CRC-32, the ID in bank
    1 Part 1 track 1, nothing else); the saved card booted again gives the
    ID and the KEY back; a run with no save writes no file. The window's six
    states drawn under the port and looked at (families, a family, back,
    scrolled, reopened with the marks).
  - On `test/scales-quantizer`, the audio side as well: every SCALE 0..24
    on ROOT C and A and every ROOT in MINOR, key k = ROOT + k.
- Planted defects: the CS1 store removed fails every chooser run's CS1
  read-back; the dispatcher call removed fails `refresh-midi`; the KEY /
  ID agreement removed fails the unicorn checks; YES giving row + 1 as the
  ID instead of `sc_order`'s fails the chooser-order check (every family
  reversed in `sc_order`).
- The keys' display and refresh (KEY LEDS, the module this one grew from)
  on the user's MKII (OCTABAM22, 30 Oct 2026): the keys follow KEY, SCALE
  and ROOT, MIDI and audio, without a key press.
- On the user's MKII: the chooser in stock's list window, the KEY's turn,
  the snapped notes and the keys (OCTABAM23, 30 Oct 2026); the window of
  MAIN MENU's size (OCTABAM24, 30 Oct 2026); with the IDs in `scales.work`
  (OCTABAM26, 31 Oct 2026): the chooser, the snapped notes and the keys,
  the scale back after SAVE PROJECT and a power cycle; that image already
  had FREE LOOP as STORE's client 5 and SCALES as 6, as `main` has now.
- SCALE QUANTIZER's 24 scales against the catalogue, by its author
  (timhastie, #980, at `b9cd1bc`): each matches one ID bit for bit, and
  his snap (the pitch class to the nearest degree of the scale rotated to
  ROOT, the lower on a tie) and `sc_snap` agree on all 52 masks, 12
  tonics and 128 notes.

## Inferred, open

- The short names in the KEY field: the formatter's two 5-byte strings
  draw 4 characters under the port (`PHRD`); lowercase `b` in names
  (`DOb2`) is drawn by the port's font as the unit's is assumed to.
- An unsaved ID does not survive a power cycle: the KEY does (stock's CS1
  mirror), the ID is read from `scales.work` at the next load, so the track
  plays the KEY's Major or Minor until the scale is picked again. A CS1
  copy would need a CS1 range no module holds; none is claimed.
- A Part reload or paste that leaves the KEY on the same Major / Minor
  keeps the destination's ID: `sc_lib` follows Part Clear, not copies.
