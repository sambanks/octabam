# Remixes

A remix is a named selection of modules; `make image REMIX=<name>` builds it into a card-flashable image from your own OS 1.40C. [BUILDING.md](BUILDING.md) is the step-by-step guide. `make modules` prints the same index from the registry.

## The remixes

| remix | contains | on hardware |
|---|---|---|
| [`ok-ms`](ok-ms.md) | Octakit + MIDI SCENES, stock effects | ✅ 14 Sep 2026 (midisc's author) |
| [`mods`](mods.md) | + the LO-FI AMF fix + CC→page 2, bridged | port only |
| [`scenes`](scenes.md) | MIDI SCENES + LO-FI fix + CC→page 2 | port only |
| [`kits`](kits.md) | Octakit + LO-FI fix + CC→page 2, bridged | port only |
| [`midi-scenes`](midi-scenes.md) | MIDI SCENES alone | in `ok-ms` |
| [`octakit`](octakit.md) | Octakit alone | in `ok-ms` |
| [`lofi-amf-fix`](lofi-amf-fix.md) | the LO-FI AMF fix alone | no |
| [`recfix`](recfix.md) | the recorder loop click fix, stock effects | ✅ 12 Sep 2026 with the bus (OCTABAM83) |
| [`repitch`](repitch.md) | REPITCH in the TSTR selector, stock effects | ✅ 16 Sep 2026 (OCTABAM81, repeat98's MKII) |
| [`octatrick`](octatrick.md) / [`octatrick-usb`](octatrick.md) | SYNTH MACHINE + SCALE QUANTIZER + DIRECT JUMP on the stock effects / + USB MIDI + USB AUDIO | `octatrick-usb` ✅ 26 Sep 2026 (OCTATRICK9, Tim's MKI, USB audio on all 20 channels); `octatrick` no |
| [`bamsep26`](bamsep26.md) | the rig: BusVerb + BusDelay + three stations + stock delay | ✅ Sam's unit |
| [`usb`](usb.md) / [`usb-audio`](usb.md) | the rig + USB MIDI / + 20-channel USB audio (tracks, MAIN, CUE) | `usb-audio` ✅ 25 Sep 2026 (image 64); `usb` no |
| [`bottleservice`](bottleservice.md) | `usb-audio` + Octakit (SCENES KITS bridged) | no (port: `make check` with the stress project, Kit save/reload/copy) |
| [`bus`](bus.md) | BusVerb + BusDelay + Send + tempo sync | ✅ (earlier names) |
| [`mutables`](mutables.md) | WarpFold, Ripple, Rungs, Streamz, BodeShift | no |
| [`nimbus`](nimbus.md) | Nimbus alone | no |
| [`rig-scenes`](rig-scenes.md) / [`rig-kits`](rig-kits.md) / [`rig-mods`](rig-mods.md) | the rig + a family | no |

## Reference

| remix | contains | on hardware |
|---|---|---|
| [`hello`](hello.md) | one DSP knob | no |
| [`hello-dram`](hello-dram.md) | one DRAM unit | no |
| [`restock`](restock.md) | the stock chooser, nothing added | no |

Never share a built image: it contains Elektron's OS.
