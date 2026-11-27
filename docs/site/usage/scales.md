SCALES gives a MIDI track 52 scales, a chooser to pick them, and a
CHROMATIC keyboard that lights the scale. Other modules can use the same
scales and the same chooser.

## Choosing a scale

Select a MIDI track and open MIDI ARP SETUP with **FUNC + AMP**. Encoder
**F** is KEY:

- **Turn F** to choose the tonic: OFF, then C through B. The selected scale
  stays unchanged.
- **Press and release F** to open the SCALES window. It lists the scale
  families; move with UP / DOWN and open a family with **RIGHT** (or **YES**).
  Press **LEFT** to return to the families list. Pressing **YES** on a scale
  selects it and closes the window; pressing **NO** closes the window without
  changing the scale. The active scale shows its short name on its family's
  row and a ticked box on its own row.

The KEY field then shows the tonic and the scale's short name, for example
**C#** and **PHRD** for C# Phrygian Dominant. Notes from the sequencer and the
arpeggiator are quantized to the nearest note in the scale (rounding down on a
tie). When CHORDS FACTORY is included in the remix, any step containing a
chord (NOT2, NOT3, or NOT4 set) plays as written regardless of KEY so the
chord keeps its voicing.

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

Hold the track key and choose **CHROMATIC** in the trig-mode list to light the
trig keys according to the track's scale. The tonic is lit yellow, other notes
in the scale are red, and notes outside the scale stay unlit, matching the
stock colours for C major. On a MIDI track, key 1 is always C, just as on the
stock keyboard.

On an audio track, when [Scale Quantizer](quantizer.md) is included in the
remix, the keys light its **SCALE** on its **ROOT** (under PROJECT > CONTROL >
SEQUENCER). Because Scale Quantizer's keyboard maps ROOT to key 1, keys 1 and
13 stay yellow.

The lit keys update immediately if you change KEY, SCALE, or ROOT while
CHROMATIC mode is active. When KEY or SCALE is set to OFF, the keyboard falls
back to the stock C major layout.

Other modules can also light the trig keys using this same keyboard layout
starting from any note (via the `sc_keyboard` service) and mark their own
notes in green; CHORDS FACTORY uses this when FUNC enters a chord's notes.

## On stock firmware

Projects saved with SCALES can still be opened on stock 1.40C. A track using
one of the seven diatonic modes maps to stock's Major or Minor scale (as with
MIDI Scales), while any other scale falls back to Major or Minor on the KEY
tonic. The original scale returns when you reopen the project with SCALES,
provided the bank was not re-saved on stock firmware with a different choice.

SCALES stores each track and Part's scale in `scales.work` inside the project
folder whenever you save. Any scale selection that has not been saved is lost
on power-off, and the track reverts to Major or Minor on its KEY until you
select the scale again.
