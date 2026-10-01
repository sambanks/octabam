# Remixes

A remix is a named selection of modules; `make image REMIX=<name> BUILD=<n>` builds it into a card-flashable image from your own OS 1.40C. Each remix is a directory here: `remix.py` is the selection, `README.md` says what is in it, where it has run and how to flash it. This index is rendered from the selections (`make docs`).

- What to install first (the Xcode Command Line Tools, Homebrew, Python 3.10+, `cmake`, `uv`) and every step to a flashed unit: [BUILDING.md](../docs/guide/BUILDING.md).
- Composing your own: [REMIXER.md](../docs/guide/REMIXER.md).
- The remixes that carry one module for its gates: [test/](test/README.md).

## The rig

| remix | contains | proof |
|---|---|---|
| [`bottleservice`](bottleservice/README.md) | The rig + USB MIDI + USB AUDIO OUT MASTER (T8 to the computer) + USB AUDIO IN CD (the computer onto inputs C/D) + Octakit. | on hardware: Sam's MKII, image 88, 27 Sep 2026 |
| [`bottleservice-pf`](bottleservice-pf/README.md) | bottleservice-ret + POST FADER: the bus sends follow each track's fader, mute and solo. | on hardware: an MKII, RIGPF7BP, 30 Sep 2026 |
| [`bottleservice-pf-flag`](bottleservice-pf-flag/README.md) | bottleservice-pf + PIRATE FLAG; bottleservice-ret + POST FADER: the bus sends follow each track's fader, mute and solo. | `make check`: make check, 29 Sep 2026; not flashed |
| [`bottleservice-rec`](bottleservice-rec/README.md) | bottleservice with 20-channel USB AUDIO OUT (tracks, MAIN, CUE) and the recorder click fixes. | on hardware: an MKII, OCTABAM1, 29 Sep 2026 |
| [`bottleservice-rec-plen`](bottleservice-rec-plen/README.md) | bottleservice-rec + RLEN PLEN (RLEN value PLEN: one pattern loop per take). | on hardware: an MKII, OCTABAM2, 29 Sep 2026 |
| [`bottleservice-ret`](bottleservice-ret/README.md) | bottleservice-rec-plen + RETURNS: the reverb return on T8's FX2 (VRB), into T8's input or MAIN, not onto T5. | on hardware: an MKII, BSRET3, 29 Sep 2026 |

## Firmware mods on the stock effects

| remix | contains | proof |
|---|---|---|
| [`analog-bassdrum`](analog-bassdrum/README.md) | Analog BD source machine, switchable 808/909, stock AMP and FX. | port-gated: source/UI under the port; earlier ANALOGBD1 auditioned on MK1, current revision unflashed |
| [`octatrick`](octatrick/README.md) | SYNTH MACHINE + SCALE QUANTIZER + DIRECT JUMP + TUNER + USB MIDI + USB AUDIO (20 channels out, 4 in onto A-D) on the stock effects less SPATIALIZER. | on hardware: Tim's MKI, test build 3.0 b40 (this selection at BUILD 40), 29 Sep 2026: USB AUDIO IN brings the Mac's audio onto the inputs in a one-minute check (long runs not yet tested). The same four modules with the 26 Sep USB AUDIO (out only) ran on the same MKI through the 2.9 test builds; the last two 2.9 fixes and the tuner's function are not yet confirmed on hardware |
| [`ok-ms`](ok-ms/README.md) | Octakit + MIDI SCENES on the stock effects: the two mods alone. | on hardware: midisc's author's unit, 14 Sep 2026 (OKMS2) |

## Reference

| remix | contains | proof |
|---|---|---|
| [`base`](base/README.md) | stock's fourteen effects, whole, plus MAIN MENU > OS: the smallest image that can boot another one. | port-gated: verify_osswitch and verify_dspvectors; the same park ran on an MKII 29 Sep 2026 in bottleservice-ret |
| [`doom`](doom/README.md) | Doom on the panel, with sound: an .OBI that the OS SWITCH boots into Doom; QUIT goes home. | on hardware: an MKII, 1 Oct 2026 (ffa6ff78): Doom with music, through OS SWITCH |

Never share a built image: it contains Elektron's OS.
