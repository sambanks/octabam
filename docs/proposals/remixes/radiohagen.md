# radiohagen

Requested by radiohagen (received): the modules they run now.

## Selection

[`bottleservice`](../../../remixes/octabam-bus/README.md) plus RLEN PLEN
and TUNER.

| module | in bottleservice | proof (module table |
|---|---|---|
| [DELAY SERVER](../../../modules/busdelay/README.md), [REVERB SERVER](../../../modules/busverb/README.md), [SEND](../../../modules/send/README.md) and the rig modules | yes | on hardware: Sam's MKII |
| [SPECTRUM](../../../modules/spectrum/README.md), [CHARACTER](../../../modules/character/README.md), [MODULATION](../../../modules/modulation/README.md) | yes | on hardware: Sam's MKII |
| [RLEN PLEN](../../../modules/rlen-plen/README.md) | no | port-gated |
| [TUNER](../../../modules/tuner/README.md) | no | on hardware: Tim's MKI |

radiohagen's own MIDI development is not part of this selection.

Later candidates named in the request, not yet tried by radiohagen:
SYNTH MACHINE, MIDI SCENES, USB AUDIO OUT. Vocoder and side-chain
compression are out of reach in their configuration.

## Stage 2: composes

Built from `origin/main` at `2f89c186`, `make bus` on a
`remix.py` copied from bottleservice with modules added:

| selection | result |
|---|---|
| bottleservice + TUNER | builds |
| bottleservice + RLEN PLEN | refused: `label formatters do not fit: MODULATION slot 6 needs 454 B; the clone window ends at 0x400d7c3c and the overflow run at 0x400d2ce0 (next free 0x400d2c74)` |
| bottleservice − KITS + RLEN PLEN + TUNER | refused, same message |
| bottleservice − USB MIDI − USB AUDIO OUT MASTER + RLEN PLEN + TUNER | refused, same message |
| bottleservice − SCENES P2 − PLOCKS P2 + RLEN PLEN + TUNER | refused, same message |
| bottleservice + SYNTH MACHINE | refused: `synth's synth page and tempo-bus's linked unit helpers both claim 0x400d24d0` |
| bottleservice + MIDI SCENES | refused: `midi-scenes's MSC freeze twin + sparse blob and scenes-p2's page-2 scene lock pool both claim bytes +0x90522.. of every Part` |

RLEN PLEN's cave is 298 B of ROM (`rlen plen cave: 298 bytes at
0x400d7980`); with it placed, MODULATION's slot 6 formatter (454 B) has
108 B left in the overflow run, 346 B short.

With the ColdFire caves moved to DRAM, `make bus`:

| selection | result |
|---|---|
| bottleservice + RLEN PLEN + TUNER | builds, 224 B of the clone window left |
| bottleservice + SYNTH MACHINE | builds, 224 B left |

MIDI SCENES' collision is a Part-window claim, which the move does not change.

## To find out

- Which MIDI CC or USB modules radiohagen's MIDI development needs alongside
  this selection.
