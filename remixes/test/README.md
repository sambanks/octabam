# Test remixes

Each carries one module, or one combination, for that module's gates: `make check REMIX=<name>`. Rendered by `make docs`; the remixes a user flashes are [one level up](../README.md).

| remix | contains | proof |
|---|---|---|
| [`batch-bugfixes`](batch-bugfixes/README.md) | stock effects with BATCH_BUGFIXES: the MIDI Plays-Free trig, empty-pattern LED and Part-change carryover fixes. | `make check` |
| [`bus`](bus/README.md) | The plain two-server image: BusVerb + BusDelay + send bus + tempo sync. | on hardware: under earlier names |
| [`cfmeter`](cfmeter/README.md) | octatrick (less TUNER and USB AUDIO IN) + CF METER on T8's FX2: ColdFire idle time and frame-interrupt duration, over USB. | port-gated: the readout chain under the port |
| [`cfmeter-port`](cfmeter-port/README.md) | cfmeter without the idle loop: the port gate for the readout chain and the interrupt timing. | port-gated: the readout chain under the port |
| [`cfmeter-post`](cfmeter-post/README.md) | octatrick (less TUNER and USB AUDIO IN) + CF METER on T8's FX2, with USB AUDIO OUT TRACKS POST in place of TRACKS MAIN CUE: the layout's ColdFire cost, over USB. | port-gated: the readout chain under the port |
| [`cfmeter-tracks`](cfmeter-tracks/README.md) | octatrick (less TUNER and USB AUDIO IN) + CF METER on T8's FX2, with USB AUDIO OUT TRACKS in place of TRACKS MAIN CUE: the layout's ColdFire cost, over USB. | port-gated: the readout chain under the port |
| [`character-txtr`](character-txtr/README.md) | bottleservice with CHARACTER TXTR (Character + Airwindows Pockey2 texture) on FX1 in place of CHARACTER: the image for measuring the texture stage's cost on a unit. | `make check` |
| [`direct-jump-kyoti`](direct-jump-kyoti/README.md) | stock effects with DIRECT_JUMP_KYOTI: [PTN] + [YES] toggles an immediate, clock-locked pattern change. | `make check` |
| [`erase-empty-trigless-locks`](erase-empty-trigless-locks/README.md) | stock effects with ERASE_EMPTY_TRIGLESS_LOCKS: an emptied trigless lock disappears. | `make check` |
| [`euclid`](euclid/README.md) | Euclid rhythmic modulation: 12 dB LP/BP/HP or AMP, both FX slots. | local render: the module's render gates |
| [`kits`](kits/README.md) | KITS (255 Kits per project) on the stock effects. | port-gated: verify_kits under the port |
| [`kyoti-fixes`](kyoti-fixes/README.md) | stock effects with QUANTIZE_LIVE_REC_TOGGLE, ERASE_EMPTY_TRIGLESS_LOCKS and BATCH_BUGFIXES together. | `make check` |
| [`kyoti-mute-jump`](kyoti-mute-jump/README.md) | stock effects with MUTE_MODES and DIRECT_JUMP_KYOTI together. | `make check` |
| [`kyoti-mute-sidechain`](kyoti-mute-sidechain/README.md) | stock effects with MUTE_MODES and SIDECHAIN_COMPRESSOR together: a muted KEY track keeps feeding the compressor (SC_KEY). | `make check` |
| [`lofi-amf-fix`](lofi-amf-fix/README.md) | Reference minimal build: the LO-FI AMF mpysu->mpyuu fix, alone. | `make check` |
| [`midi-scenes`](midi-scenes/README.md) | Reference minimal build: the MIDI SCENES ColdFire patch, alone. | port-gated: `verify_scenes` against MIDISC2.1 under the port; not flashed |
| [`miniverb`](miniverb/README.md) | Minimal allocator-owned FDN reverb. | local render: `make verify-miniverb` |
| [`mods`](mods/README.md) | Every ColdFire mod in one image on the stock effects: MIDI SCENES, KITS, the recorder fixes, REPITCH, the KYOTI direct jump and reload, USB MIDI + AUDIO. | port-gated |
| [`mute-modes`](mute-modes/README.md) | stock effects with MUTE_MODES: PERSONALIZE > MUTE MODE (OT, OTFX, OTFX-T, DT-T). | `make check` |
| [`plocks-p2`](plocks-p2/README.md) | Page-2 parameter locks (PLOCKS P2) and page-2 scene locks (SCENES P2), stock effects. | port-gated: verify_plocksp2 under the port |
| [`quantize-live-rec-toggle`](quantize-live-rec-toggle/README.md) | stock effects with QUANTIZE_LIVE_REC_TOGGLE: QUANTIZE LIVE REC from [REC] + [PLAY]. | `make check` |
| [`rec-trig-mute`](rec-trig-mute/README.md) | stock effects with REC_TRIG_MUTE: [TRACK]+[NO]/[YES] mute/unmute recorder trigs. | `make check` |
| [`reload-from-project`](reload-from-project/README.md) | stock effects with RELOAD_FROM_PROJECT: reload one track's sequence from the card while the transport runs. | `make check` |
| [`repitch`](repitch/README.md) | stock effects with variable-speed REPITCH in the TSTR selector. | on hardware: MKII, unit undetermined, 16 Sep 2026 (OCTABAM81) |
| [`repitch-repeat98-kyoti`](repitch-repeat98-kyoti/README.md) | stock effects with REPITCH_REPEAT98_KYOTI: RPCH / RPS9 / RPSP and QUAN; SPRING REV gives up its words: its P run for the DSP kernel, its own X data for the two table blocks (#603). | `make check` |
| [`rig`](rig/README.md) | bottleservice's delay and reverb bus and FX1 stations, without USB, Octakit or the scene modules: the fixture of the CC MAP, Character and one-aux gates. | `make check` |
| [`scenes-midisc`](scenes-midisc/README.md) | MIDI SCENES + KITS + page-2 scene locks (SCENES P2) + page-2 parameter locks (PLOCKS P2), stock effects. | port-gated: verify_scenesp2 and verify_plocksp2 under the port |
| [`sidechain-compressor`](sidechain-compressor/README.md) | stock effects with SIDECHAIN_COMPRESSOR in COMPRESSOR's row: KEY, KFLT, KGN and MON on page 2. | `make check` |
| [`sos-capture`](sos-capture/README.md) | recorder fixes + USB MIDI + USB AUDIO OUT TRACKS + USB CROSSBAR + USB AUDIO IN AB (stock effects minus SPATIALIZER). | port-gated: `make check` under the port; not on hardware in this form |
| [`stems`](stems/README.md) | STEM REC on the stock effects: multitrack recording to the card, each track, MAIN, CUE and the inputs as separate WAV files. | on hardware: Yves's MKII, 6 Oct 2026 (STEMS3) |
| [`tapeecho`](tapeecho/README.md) | Tape Echo replacing Spring Reverb, alone. | on hardware: the author's unit (OCTACLID4): six instances; a seventh freezes it, open |
| [`testgen`](testgen/README.md) | TESTGEN on FX1 beside the stock effects (all but PLATE REV, whose words it takes). | on hardware: Ignorato's MKII, OCTABAM6, 4 Oct 2026 |
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
| [`usb-out-tracks-post`](usb-out-tracks-post/README.md) | stock + USB MIDI + USB AUDIO OUT TRACKS POST (16 ch: the tracks after their own MAIN gain). | on hardware: allmyfriendsaresynths's MKII, P3, 5 Oct 2026 (smoke test: 16 channels, LEVEL/mute/solo/crossfader follow) |
| [`vocoder`](vocoder/README.md) | VOCODER beside the stock effects (all but PLATE REV, whose words it takes, and DJ EQ, so its table sits in X). | on hardware: Ignorato's MKII, OCTABAM12 (the earlier positions T1 T2 T5 T6), 4 Oct 2026; the current positions not flashed on this build |
| [`waveload`](waveload/README.md) | CF METER + WAVE LOAD on stock: T8's FX2 BURN = K 4-voice wave engines per frame interrupt, read over USB. | on hardware: image 92, Sam's MKII, 3 Oct 2026 |
| [`waveload-port`](waveload-port/README.md) | waveload without the idle loop: the port gate for the wave engines in the frame interrupt. | port-gated: the load path under the port |
