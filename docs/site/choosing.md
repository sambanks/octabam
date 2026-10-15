# Choosing a remix

Three remixes are built from the same core modules; they differ in what they
do with the effects. One keeps stock exactly as stock has it. One adds
insert effects that run on any track, on FX1 and FX2. One adds the delay and
reverb bus and keeps three of the inserts on FX1.

| | octabam-core | octabam-inserts | octabam-bus |
|---|---|---|---|
| stock effects | all 14, unchanged (LO-FI's AMF knob fixed) | the stock DELAY; the other 13 give up their DSP words | the stock DELAY on track 8; the other 13 give up their DSP words |
| new effects | none | SPECTRUM, CHARACTER, MODULATION, TRANSIENT and EUCLID on FX1 and FX2; GATE VERB and LOFI2 on FX2 | SPECTRUM, CHARACTER and MODULATION on FX1; DELAY and REVERB engines on tracks 1 and 5; SEND on tracks 2–4, 6–7 |
| bus | no | no | yes: DELAY (track 1), REVERB (track 5), SEND elsewhere |
| LOAD METER | not in the image | in the image | in the image |
| DSP words free, payload A / B | 0 | 363 / 363 | 44 / 605 |
| sample and recorder memory | 12,895 pages | 12,895 pages | 12,895 pages |
| where it has run | port gates only; not on a unit | port gates only; not on a unit | port gates only; not on a unit |

Sample and recorder memory is the platform reserve, the same in all three:
stock's 14,602 pages down to 12,895.

The core modules are the same set in all three remixes (octabam-core has no
LOAD METER: its DSP half needs 156 words per payload, and the 14 stock
effects leave none). They cover: BRAIN (settings, defaults, templates and
the remix switch), KITS (255 Kits per project), scene and parameter locks on
page 2, MIDI scenes, USB MIDI and USB audio, and a set of fixes to stock
behaviour.

Pick:

- octabam-core if you want the platform features and no change to the
  effects.
- octabam-inserts if you want new effects per track, on FX1 and FX2, with no
  bus wiring to set up.
- octabam-bus if you want the delay and reverb bus: tracks 1 and 5 become
  the two engines, every other track gets a SEND with two knobs, DEL and
  REV. Its FX1 keeps three of the inserts: SPECTRUM, CHARACTER, MODULATION.

Each remix's page lists its modules and how to flash it:

- [octabam-core](remix-core.md)
- [octabam-inserts](remix-inserts.md)
- [octabam-bus](remix-bus.md)

All three are verified under the port only. None has run on a unit.
