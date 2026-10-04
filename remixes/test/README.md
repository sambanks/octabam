# Test remixes

Each carries one module, or one combination, for that module's gates: `make check REMIX=<name>`. Rendered by `make docs`; the remixes a user flashes are [one level up](../README.md).

| remix | contains | proof |
|---|---|---|
| [`batch-bugfixes`](batch-bugfixes/README.md) | stock effects with BATCH_BUGFIXES: the MIDI Plays-Free trig, empty-pattern LED and Part-change carryover fixes. | `make check` |
| [`bus`](bus/README.md) | The plain two-server image: BusVerb + BusDelay + send bus + tempo sync. | on hardware: under earlier names |
| [`cfmeter`](cfmeter/README.md) | octatrick (less TUNER and USB AUDIO IN) + CF METER on T8's FX2: ColdFire idle time and frame-interrupt duration, over USB. | port-gated: the readout chain under the port |
| [`cfmeter-port`](cfmeter-port/README.md) | cfmeter without the idle loop: the port gate for the readout chain and the interrupt timing. | port-gated: the readout chain under the port |
| [`direct-jump-kyoti`](direct-jump-kyoti/README.md) | stock effects with DIRECT_JUMP_KYOTI: [PTN] + [YES] toggles an immediate, clock-locked pattern change. | `make check` |
| [`erase-empty-trigless-locks`](erase-empty-trigless-locks/README.md) | stock effects with ERASE_EMPTY_TRIGLESS_LOCKS: an emptied trigless lock disappears. | `make check` |
| [`euclid`](euclid/README.md) | Euclid rhythmic modulation: 12 dB LP/BP/HP or AMP, both FX slots. | local render: the module's render gates |
| [`kyoti-fixes`](kyoti-fixes/README.md) | stock effects with QUANTIZE_LIVE_REC_TOGGLE, ERASE_EMPTY_TRIGLESS_LOCKS and BATCH_BUGFIXES together. | `make check` |
| [`kyoti-mute-jump`](kyoti-mute-jump/README.md) | stock effects with MUTE_MODES and DIRECT_JUMP_KYOTI together. | `make check` |
| [`lofi-amf-fix`](lofi-amf-fix/README.md) | Reference minimal build: the LO-FI AMF mpysu->mpyuu fix, alone. | `make check` |
| [`midi-scenes`](midi-scenes/README.md) | Reference minimal build: the MIDI SCENES ColdFire patch, alone. | `make check`: on hardware inside `ok-ms` |
| [`miniverb`](miniverb/README.md) | Minimal allocator-owned FDN reverb. | local render: `make verify-miniverb` |
| [`mods`](mods/README.md) | Every ColdFire mod in one image on the stock effects: MIDI SCENES, Octakit, the recorder fixes, REPITCH, USB MIDI + AUDIO (octatrick's three cannot join it). | port-gated |
| [`mute-modes`](mute-modes/README.md) | stock effects with MUTE_MODES: PERSONALIZE > MUTE MODE (OT, OTFX, OTFX-T, DT-T). | `make check` |
| [`octakit`](octakit/README.md) | Em's Octakit alone -- must reproduce her own build byte for byte. | `make check`: on hardware inside `ok-ms` |
| [`plocks-p2`](plocks-p2/README.md) | Page-2 parameter locks (PLOCKS P2) and page-2 scene locks (SCENES P2), stock effects. | port-gated: verify_plocksp2 under the port |
| [`quantize-live-rec-toggle`](quantize-live-rec-toggle/README.md) | stock effects with QUANTIZE_LIVE_REC_TOGGLE: QUANTIZE LIVE REC from [REC] + [PLAY]. | `make check` |
| [`rec-trig-mute`](rec-trig-mute/README.md) | stock effects with REC_TRIG_MUTE: [TRACK]+[NO]/[YES] mute/unmute recorder trigs. | `make check` |
| [`reload-from-project`](reload-from-project/README.md) | stock effects with RELOAD_FROM_PROJECT: reload one track's sequence from the card while the transport runs. | `make check` |
| [`repitch`](repitch/README.md) | stock effects with variable-speed REPITCH in the TSTR selector. | on hardware: repeat98's MKII, 16 Sep 2026 (OCTABAM81) |
| [`rig`](rig/README.md) | bottleservice's delay and reverb bus and FX1 stations, without USB, Octakit or the scene modules: the fixture of the CC MAP, Character and one-aux gates. | `make check` |
| [`sos-capture`](sos-capture/README.md) | recorder fixes + USB MIDI + USB AUDIO OUT TRACKS + USB CROSSBAR + USB AUDIO IN AB (stock effects minus SPATIALIZER). | port-gated: `make check` under the port; not on hardware in this form |
| [`tapeecho`](tapeecho/README.md) | Tape Echo replacing Spring Reverb, alone. | on hardware: the author's unit (OCTACLID4): six instances; a seventh freezes it, open |
| [`transient`](transient/README.md) | TRANSIENT beside the stock effects (all but PLATE REV, whose words it takes). | on hardware: Ignorato's MKII, OCTABAM2, 3 Oct 2026 |
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
| [`waveload`](waveload/README.md) | CF METER + WAVE LOAD on stock: T8's FX2 BURN = K 4-voice wave engines per frame interrupt, read over USB. | on hardware: image 92, Sam's MKII, 3 Oct 2026 |
| [`waveload-port`](waveload-port/README.md) | waveload without the idle loop: the port gate for the wave engines in the frame interrupt. | port-gated: the load path under the port |
