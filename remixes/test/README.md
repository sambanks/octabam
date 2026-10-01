# Test remixes

Each carries one module, or one combination, for that module's gates: `make check REMIX=<name>`. Rendered by `make docs`; the remixes a user flashes are [one level up](../README.md).

| remix | contains | proof |
|---|---|---|
| [`bus`](bus/README.md) | The plain two-server image: BusVerb + BusDelay + send bus + tempo sync. | on hardware: under earlier names |
| [`cfmeter`](cfmeter/README.md) | octatrick (less TUNER and USB AUDIO IN) + CF METER on T8's FX2: ColdFire idle time and frame-interrupt duration, over USB. | port-gated: the readout chain under the port |
| [`cfmeter-port`](cfmeter-port/README.md) | cfmeter without the idle loop: the port gate for the readout chain and the interrupt timing. | port-gated: the readout chain under the port |
| [`dsp-reset`](dsp-reset/README.md) | probe: RSTOUT (RCR bit 6) against the DSP's boot ROM, reported on MIDI OUT at boot. | port-gated: the probe reports both ways under the port (verify_dspreset) |
| [`dsp-reset-pc`](dsp-reset-pc/README.md) | dsp-reset plus OS SWITCH: the probe's positive control, a parked core that must answer, so the no is worth something. | port-gated: the negative, the modelled positive and the PARKED positive, all under the port (verify_dspreset) |
| [`euclid`](euclid/README.md) | Euclid rhythmic modulation: 12 dB LP/BP/HP or AMP, both FX slots. | local render: the module's render gates |
| [`lofi-amf-fix`](lofi-amf-fix/README.md) | Reference minimal build: the LO-FI AMF mpysu->mpyuu fix, alone. | `make check` |
| [`midi-scenes`](midi-scenes/README.md) | Reference minimal build: the MIDI SCENES ColdFire patch, alone. | `make check`: on hardware inside `ok-ms` |
| [`miniverb`](miniverb/README.md) | Minimal allocator-owned FDN reverb. | local render: `make verify-miniverb` |
| [`mods`](mods/README.md) | Every ColdFire mod in one image on the stock effects: MIDI SCENES, Octakit, the recorder fixes, REPITCH, USB MIDI + AUDIO (octatrick's three cannot join it). | port-gated |
| [`octakit`](octakit/README.md) | Em's Octakit alone -- must reproduce her own build byte for byte. | `make check`: on hardware inside `ok-ms` |
| [`os-switch`](os-switch/README.md) | stock effects with CONTROL > OS SWITCH: boot a .OBI from the card root, no flash write. | port-gated: the chainload under the port (verify_osswitch) |
| [`os-switch-trace`](os-switch-trace/README.md) | os-switch + BOOT TRACE: a MIDI note per boot stage, to find where a boot after a switch hangs. | port-gated: the notes under the port (verify_boottrace) |
| [`pirate-flag`](pirate-flag/README.md) | base + PIRATE FLAG: the boot animation becomes a waving Jolly Roger. | `make check`: the flag under the port (verify_pirateflag) |
| [`repitch`](repitch/README.md) | stock effects with variable-speed REPITCH in the TSTR selector. | on hardware: repeat98's MKII, 16 Sep 2026 (OCTABAM81) |
| [`rig`](rig/README.md) | The rig without a ColdFire runtime: the fixture of the CC MAP, Character and one-aux gates. | `make check` |
| [`sos-capture`](sos-capture/README.md) | recorder fixes + USB MIDI + USB AUDIO OUT TRACKS + USB CROSSBAR + USB AUDIO IN AB (stock effects minus SPATIALIZER). | port-gated: `make check` under the port; not on hardware in this form |
| [`tapeecho`](tapeecho/README.md) | Tape Echo replacing Spring Reverb, alone. | on hardware: the author's unit (OCTACLID4): six instances; a seventh freezes it, open |
| [`usb-io-main-ab`](usb-io-main-ab/README.md) | stock - SPATIALIZER + USB MIDI + USB AUDIO OUT MAIN + USB CROSSBAR + USB AUDIO IN AB. | port-gated: `make check` (verify_usb, verify_usb_in) under the port, 28 Sep 2026; not on hardware in this form |
| [`usb-io-main-abcd`](usb-io-main-abcd/README.md) | stock - SPATIALIZER + USB MIDI + USB AUDIO OUT MAIN + USB CROSSBAR + USB AUDIO IN ABCD. | port-gated: `make check` (verify_usb, verify_usb_in) under the port, 28 Sep 2026; not on hardware in this form |
| [`usb-io-main-cd`](usb-io-main-cd/README.md) | stock - SPATIALIZER + USB MIDI + USB AUDIO OUT MAIN + USB CROSSBAR + USB AUDIO IN CD. | port-gated: `make check` (verify_usb, verify_usb_in) under the port, 28 Sep 2026; not on hardware in this form |
| [`usb-io-main-cue-ab`](usb-io-main-cue-ab/README.md) | stock - SPATIALIZER + USB MIDI + USB AUDIO OUT MAIN CUE + USB CROSSBAR + USB AUDIO IN AB. | port-gated: `make check` (verify_usb, verify_usb_in) under the port, 28 Sep 2026; not on hardware in this form |
| [`usb-io-main-cue-abcd`](usb-io-main-cue-abcd/README.md) | stock - SPATIALIZER + USB MIDI + USB AUDIO OUT MAIN CUE + USB CROSSBAR + USB AUDIO IN ABCD. | port-gated: `make check` (verify_usb, verify_usb_in) under the port, 28 Sep 2026; not on hardware in this form |
| [`usb-io-main-cue-cd`](usb-io-main-cue-cd/README.md) | stock - SPATIALIZER + USB MIDI + USB AUDIO OUT MAIN CUE + USB CROSSBAR + USB AUDIO IN CD. | port-gated: `make check` (verify_usb, verify_usb_in) under the port, 28 Sep 2026; not on hardware in this form |
| [`usb-io-tracks-ab`](usb-io-tracks-ab/README.md) | stock - SPATIALIZER + USB MIDI + USB AUDIO OUT TRACKS + USB CROSSBAR + USB AUDIO IN AB. | port-gated: `make check` (verify_usb, verify_usb_in) under the port, 28 Sep 2026; not on hardware in this form |
| [`usb-io-tracks-abcd`](usb-io-tracks-abcd/README.md) | stock - SPATIALIZER + USB MIDI + USB AUDIO OUT TRACKS + USB CROSSBAR + USB AUDIO IN ABCD. | port-gated: `make check` (verify_usb, verify_usb_in) under the port, 28 Sep 2026; not on hardware in this form |
| [`usb-io-tracks-cd`](usb-io-tracks-cd/README.md) | stock - SPATIALIZER + USB MIDI + USB AUDIO OUT TRACKS + USB CROSSBAR + USB AUDIO IN CD. | port-gated: `make check` (verify_usb, verify_usb_in) under the port, 28 Sep 2026; not on hardware in this form |
| [`usb-io-tracks-main-cue-ab`](usb-io-tracks-main-cue-ab/README.md) | stock - SPATIALIZER + USB MIDI + USB AUDIO OUT TRACKS MAIN CUE + USB CROSSBAR + USB AUDIO IN AB. | port-gated: `make check` (verify_usb, verify_usb_in) under the port, 28 Sep 2026; not on hardware in this form |
| [`usb-io-tracks-main-cue-abcd`](usb-io-tracks-main-cue-abcd/README.md) | stock - SPATIALIZER + USB MIDI + USB AUDIO OUT TRACKS MAIN CUE + USB CROSSBAR + USB AUDIO IN ABCD. | port-gated: `make check` (verify_usb, verify_usb_in) under the port, 28 Sep 2026; not on hardware in this form |
| [`usb-io-tracks-main-cue-cd`](usb-io-tracks-main-cue-cd/README.md) | stock - SPATIALIZER + USB MIDI + USB AUDIO OUT TRACKS MAIN CUE + USB CROSSBAR + USB AUDIO IN CD. | port-gated: `make check` (verify_usb, verify_usb_in) under the port, 28 Sep 2026; not on hardware in this form |
| [`usb-midi`](usb-midi/README.md) | stock + USB MIDI (class-compliant, mirrors DIN). | `make check` |
| [`usb-out-main`](usb-out-main/README.md) | stock + USB MIDI + USB AUDIO OUT MAIN (2 ch: MAIN L/R). | port-gated: `verify_usb` under the port, 28 Sep 2026 |
| [`usb-out-main-cue`](usb-out-main-cue/README.md) | stock + USB MIDI + USB AUDIO OUT MAIN CUE (4 ch: MAIN + CUE). | port-gated |
| [`usb-out-master`](usb-out-master/README.md) | stock + USB MIDI + USB AUDIO OUT MASTER (2 ch: track 8). | port-gated |
| [`usb-out-tracks`](usb-out-tracks/README.md) | stock + USB MIDI + USB AUDIO OUT TRACKS (16 ch: the tracks). | port-gated |
| [`usb-out-tracks-main-cue`](usb-out-tracks-main-cue/README.md) | stock + USB MIDI + USB AUDIO (20 ch: tracks, MAIN, CUE). | port-gated |
