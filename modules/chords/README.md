# CHORDS FACTORY

Chord progressions for a MIDI track. Each bank holds sixteen chord slots,
one per trig key. A chord is built (root, type, inversion, spread, octave),
typed on the trig keys, or voiced from the slot before it by voice leading:
the module offers the voicings that move the voices least (common notes
kept, no crossing), best first. At most four voices: one MIDI trig's NOTE
and NOT2-4. The slots are saved with the project (`chords.work`, a STORE
client).

## The page

SRC pressed again on MIDI NOTE opens the atelier (a PAGES client); again
closes it. The band shows `CHORDS n/16` and the slot's chord name, then
the four notes, the sixteen slots, and six cells:

| encoder | | with FUNC held |
| --- | --- | --- |
| A | ROOT | VX1: voice 1 a semitone up / down (EDIT) |
| B | TYPE (21 types: MAJ, MIN, 7, MAJ7, MIN7, HDIM, DIM, DIM7, AUG, SUS2, SUS4, 7SU4, 6, MIN6, ADD9, MAD9, MMA7, 9, MIN9, MAJ9, 5) | VX2 |
| C | INV | VX3 |
| D | SPRD: CLS, DRP2, DRP3, OPEN, BASS (OPEN, its bass an octave down), 10E (the bass, the rest an octave up), WIDE (voice k k octaves up) | VX4 |
| E | OCT | BASS: free or the root |
| F | VOIX: the next / previous voice-leading answer, from any chord after a slot that holds one | GAMME: the scale's chord on the next degree (SCALES) |

A slot is **built** (ROOT .. OCT), **led** (VOIX) or **edited** (notes
moved or typed by hand). INV, SPRD and OCT only shape a built chord: on a
led or edited one their cells are empty, and turning one builds the chord
again.

The trig keys: alone, the slot is chosen and heard while held (on the
track's MIDI channel); with FUNC held they are a keyboard from the slot
octave's C (key 1 = C), a key adds or removes its note. While FUNC is held
the keys light as that keyboard: the chord's notes green and, with SCALES,
the track's scale in its CHROMATIC colours (`sc_keyboard`: tonic yellow,
scale red); without SCALES or on KEY OFF, C major in the same colours.

## The trig mode

CHORDS is a MIDI trig mode (FUNC + DOWN's list: TRACKS, CHROMATIC, CHORDS,
QUICK MUTE; mode 2, which is SLOTS on the audio tracks). The trig keys
play the bank's slots through stock's CHROMATIC note, one call per voice,
so the arpeggiator and the KEY take the chord as keys held. LEDs: green
for a slot that holds a chord, yellow while held. The trig mode box on the
main screen shows `n/16`, the chord last played (name and bass, under them
the spread of a built chord, `VOIX n` or `EDIT`) and the sixteen slots.

A chord goes on a trig by live recording (one trig: NOTE and NOT2-4) or,
in GRID RECORDING, with trigs held and **UP**: a chooser of MAIN MENU's
size lists the bank's chords (UP / DOWN, heard; YES places it on the held
trigs, NO closes it). Beside SCALES a chord step plays as written
(SCALES' `HAVE_CHORDS`).

## Detours and pokes

| site | | |
| --- | --- | --- |
| `0x400359fa` | `ch_lbl_list` | the trig modes' list: mode 2 named CHORDS in MIDI mode |
| `0x40036046` | `ch_lbl_bar` | the trig mode's name on the screen |
| `0x40050294` | `ch_mode_key` | the trig key handler's mode 2: a slot's chord in MIDI mode, SLOTS in audio |
| `0x400441f6` | `ch_mode_led` | the trig LED pass's mode 2: the slots' LEDs in MIDI mode |
| `0x40044006` | `ch_kbd_pass` | the LED pass's trig mode test: the keyboard while the page types notes |
| `0x40035f92` | `ch_box_head` | the trig mode box's header for mode 2 |
| `0x40044b74` | `ch_box_pic` | the trig mode box's picture for mode 2 |
| `0x40045502` | `ch_box_bar` | the box's sample play bar (modes 2 / 3): none in MIDI mode |
| `0x4005872e` | poke `7003` -> `7004` | the MIDI trig modes' list has four rows |
| `0x40035a24`, `0x40051efc`, `0x40051f6c` | `ch_midimodes` | the MIDI trig modes: 0, 1, 2, 4 |

## Measured

- Stock's CHROMATIC note `0x40043664` keeps held notes in 16 cells
  (note % 16): two voices 16 apart collide and one is left on. CHORDS
  calls the note routine `0x4009e9a8` directly ✅ (image 37 on the unit).
- `0x4009e9a8` posts its note events from one static record
  (`0x46c77bea`); for live recording CHORDS posts its own events per voice
  to the system queue `0x460d17ae`, and stock's recorder `0x40041bc4`
  writes NOTE and NOT2-4 ✅.
- The MIDI track record of a pattern: `pattern + 0x48d0 + t * 0x8b0`,
  locks at `+0x30 + step * 32`, its CS1 copy at `0x1001614e` ✅.
- Mode 2's refresh (`0x400454c4`) draws the audio sample's play bar
  (`fill(0x3d, 8, 0x75, 9)` at `0x40045502`) ✅.
- The trig LED pass is `0x40043fdc`; its mode dispatch is at `0x40044006`,
  its common end at `0x400444f8` ✅.

## Status

On the owner's MKII in the live-djib rig, OCTABAM36-43 (3-5 Nov 2026,
with SCALES): the page, voice leading, the trig mode, live recording,
TRIG + UP, the FUNC keyboard. Gates: `modules/chords/verify.py` (the
engine on the host: every type, root, inversion and spread; voice
leading), `tools/verify/verify_chords.py` (the port: test remixes
`chords`, with SCALES, and `chords-alone`, without it).
