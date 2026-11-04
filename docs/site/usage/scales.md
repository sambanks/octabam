SCALES gives a MIDI track 52 scales, a chooser to pick them, and a
CHROMATIC keyboard that lights the scale. Other modules can use the same
scales and the same chooser.

## Choosing a scale

Select a MIDI track and open MIDI ARP SETUP with **FUNC + AMP**. Encoder
**F** is KEY:

- **Turn F** to choose the tonic: OFF, then C to B. The scale stays.
- **Press and release F** to open the SCALES window. It lists the
  families; move with UP / DOWN and enter one with **RIGHT** (or **YES**).
  The family's scales follow; **LEFT** goes back to the families. **YES**
  on a scale chooses it and closes the window; **NO** closes it and
  changes nothing. The scale in use shows its short name on its family's
  row and a ticked box on its own row.

The KEY field then shows the tonic and the scale's short name, for
example **C#** and **PHRD** for C# Phrygian Dominant. The sequencer's and
the arpeggiator's notes move to the nearest note of the scale (the lower
one when two are as near).

| family | scales |
| --- | --- |
| MAJOR | Ionian (Major), Dorian, Phrygian, Lydian, Mixolydian, Aeolian (Minor), Locrian |
| MELODIC MINOR | Melodic Minor, Dorian b2, Lydian Augmented, Lydian Dominant, Mixolydian b6, Locrian #2, Superlocrian (the altered scale) |
| HARMONIC MINOR | Harmonic Minor, Locrian #6, Ionian #5, Dorian #4, Phrygian Dominant, Lydian #2, Altered bb7 |
| HARMONIC MAJOR | Harmonic Major, Dorian b5, Phrygian b4, Lydian b3, Mixolydian b2, Lydian Aug #2, Locrian bb7 |
| DOUBLE HARMONIC | Double Harmonic, Lydian #2 #6, Ultraphrygian, Hungarian Minor, Oriental, Ionian #2 #5, Locrian bb3 bb7 |
| PENTATONIC | Major Pentatonic, Egyptian, Man Gong, Ritusen, Minor Pentatonic |
| BLUES | Blues, Major Blues |
| JAPANESE | Hirajoshi, In-Sen, Iwato, Kumoi, Pelog |
| SYMMETRIC | Whole Tone, Diminished W-H, Diminished H-W, Augmented, Chromatic |

The scale is saved with the Part, like the KEY. A project made with
[MIDI Scales](midi-scales.md) keeps its modes.

## The CHROMATIC keyboard

Hold the track key and choose **CHROMATIC** in the trig-mode list: the
trig keys light the track's scale. The tonic is yellow, the scale's other
notes red, and the notes outside it dark, the same colours stock uses for
C major. On a MIDI track key 1 is always C, as on stock's keyboard.

On an audio track, with [Scale Quantizer](quantizer.md) in the remix, the
keys light its **SCALE** on its **ROOT** (PROJECT > CONTROL > SEQUENCER).
Scale Quantizer's keyboard plays ROOT on key 1, so keys 1 and 13 stay
yellow.

The keys follow a KEY, SCALE or ROOT you change while CHROMATIC is shown.
KEY OFF and SCALE OFF keep stock's C major.

## On stock firmware

A project saved with SCALES opens on stock 1.40C. A track with one of the
seven diatonic modes keeps stock's Major or Minor for it (as with MIDI
Scales); a track with another scale plays the KEY's tonic in Major or
Minor. The scale comes back when the project is opened with SCALES again,
as long as the bank was not saved on stock with another choice.

SCALES keeps the scale of each track and Part in `scales.work`, in the
project folder, written when you save. A scale picked and not saved is
lost at power-off: the track then plays its KEY's Major or Minor until you
pick the scale again.

## Verification limits

Checked under the emulator on both models: every scale picked from ARP
SETUP's keys and read back, saved in `scales.work` and loaded again, the snapped notes for every
scale, tonic and note, and the trig LEDs. The keyboard's colours and their
refresh were tested on a unit; the chooser and the snapped notes not yet.
