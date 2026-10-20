# Test remixes

Each carries one module, or one combination, for that module's gates: `make check REMIX=<name>`. Rendered by `make docs`; the remixes a user flashes are [one level up](../README.md).

| remix | contains | proof |
|---|---|---|
| [`analog-bassdrum`](analog-bassdrum/README.md) | Analog BD source machine, switchable 808/909, stock AMP and FX. | port-gated: source/UI under the port; earlier ANALOGBD1 auditioned on MK1, current revision unflashed |
| [`ata-write-guard`](ata-write-guard/README.md) | Stock effects with the first PIO card write guarded through bookkeeping. | port-gated: forced completion-interrupt gate under the port; not on hardware |
| [`batch-bugfixes`](batch-bugfixes/README.md) | stock effects with BATCH_BUGFIXES: the MIDI Plays-Free trig, empty-pattern LED and Part-change carryover fixes. | `make check` |
| [`bbd`](bbd/README.md) | BBD beside the stock effects (all but SPRING REV and PLATE REV, whose words it takes). | on hardware: JamCones' MKII, BBDOB4 (BUILD 4), 17 Oct 2026 |
| [`blackpyramids-303`](blackpyramids-303/README.md) | BLACKPYRAMIDS_303 (BLKPYRAMD, a TB-303 voice as a track machine) with the stock effects, SPRING REV given up. | `make check` |
| [`buffer-saver`](buffer-saver/README.md) | stock effects with SAVE PROJECT offering to save the recorder buffers' unsaved takes, each assigned to itself. | on hardware: Chupitnik's MKII, 15-16 Oct 2026, AUTOSAVE1 and AUTOSAVE2 from the card (the module under its first name): after a take FUNC + PROJ and PROJECT > SAVE ask SAVE SAMPLES?; YES saves R<n>-YYMMDD-HHMM and assigns it to its buffer, two buffers in one save, an immediate re-save does not ask, a reload brings the takes back, NO saves as stock |
| [`bus`](bus/README.md) | The plain two-server image: BusVerb + BusDelay + send bus + tempo sync. | on hardware: under earlier names |
| [`bus-notempo`](bus-notempo/README.md) | bus with TEMPO SYNC's CAVE pinned OFF (diagnostic). | port-gated |
| [`bus-tempo-replay`](bus-tempo-replay/README.md) | bus with TEMPO SYNC's CAVE pinned REPLAY (diagnostic). | port-gated |
| [`cfmeter`](cfmeter/README.md) | octatrick (less TUNER and the USB input) + CF METER on T8's FX2: ColdFire idle time and frame-interrupt duration, over USB. | port-gated: the readout chain under the port |
| [`cfmeter-port`](cfmeter-port/README.md) | cfmeter without the idle loop: the port gate for the readout chain and the interrupt timing. | port-gated: the readout chain under the port |
| [`cfmeter-post`](cfmeter-post/README.md) | octatrick (less TUNER and the USB input) + CF METER on T8's FX2, with USB TRACKS POST in place of TRACKS MAIN CUE: POST's ColdFire cost, over USB. | port-gated: the readout chain under the port |
| [`cfmeter-tracks`](cfmeter-tracks/README.md) | octatrick (less TUNER and the USB input) + CF METER on T8's FX2, with USB TRACKS in place of TRACKS MAIN CUE: the 16-channel-only stream's ColdFire cost, over USB. | port-gated: the readout chain under the port |
| [`character-txtr`](character-txtr/README.md) | octabam-bus with CHARACTER TXTR (Character + Airwindows Pockey2 texture) on FX1 in place of CHARACTER: the image for measuring the texture stage's cost on a unit. | `make check` |
| [`copy-project`](copy-project/README.md) | stock effects with COPY PROJECT: duplicate a project on the card without loading it. | `make check` |
| [`direct-jump-kyoti`](direct-jump-kyoti/README.md) | stock effects with DIRECT_JUMP_KYOTI: [PTN] + [YES] toggles an immediate, clock-locked pattern change. | `make check` |
| [`erase-empty-trigless-locks`](erase-empty-trigless-locks/README.md) | stock effects with ERASE_EMPTY_TRIGLESS_LOCKS: an emptied trigless lock disappears. | `make check` |
| [`euclid`](euclid/README.md) | Euclid rhythmic modulation: 12 dB LP/BP/HP or AMP, both FX slots. | local render: the module's render gates |
| [`euclid-fill`](euclid-fill/README.md) | stock effects with EUCLID FILL: TRACK+PAGE Euclidean trig-fill page. | `make check` |
| [`gateverb`](gateverb/README.md) | GATE VERB alone: the fixture of its render gate. | local render: `verify_gateverb`; not flashed |
| [`kits`](kits/README.md) | KITS (255 Kits per project) on the stock effects. | port-gated: verify_kits under the port |
| [`kyoti-fixes`](kyoti-fixes/README.md) | stock effects with QUANTIZE_LIVE_REC_TOGGLE, ERASE_EMPTY_TRIGLESS_LOCKS and BATCH_BUGFIXES together. | `make check` |
| [`kyoti-mute-jump`](kyoti-mute-jump/README.md) | stock effects with MUTE_MODES and DIRECT_JUMP_KYOTI together. | `make check` |
| [`kyoti-mute-sidechain`](kyoti-mute-sidechain/README.md) | stock effects with MUTE_MODES and SIDECHAIN_COMPRESSOR together: a muted KEY track keeps feeding the compressor (SC_KEY). | `make check` |
| [`lofi-amf-fix`](lofi-amf-fix/README.md) | Reference minimal build: the LO-FI AMF mpysu->mpyuu fix, alone. | `make check` |
| [`lofi2`](lofi2/README.md) | LOFI2 beside the stock effects (all but PLATE REV and SPRING REV, whose words it takes). | `make check` |
| [`midi-follow`](midi-follow/README.md) | Per-track RFOL source selection on MIDI NOTE SETUP; Part-owned bass following. | port-gated |
| [`midi-loopback`](midi-loopback/README.md) | Stock effects plus the Part-scoped per-track MIDI loopback routing. | on hardware |
| [`midi-scales`](midi-scales/README.md) | All twelve keys and seven modes in the native ARP SETUP KEY control. | port-gated |
| [`midi-scenes`](midi-scenes/README.md) | Reference minimal build: the MIDI SCENES ColdFire patch, plus direct-jump so `swd` runs. | port-gated: `verify_scenes` against MIDISC2.1 under the port; not flashed |
| [`miniverb`](miniverb/README.md) | Minimal allocator-owned FDN reverb. | local render: `make verify-miniverb` |
| [`mods`](mods/README.md) | Every ColdFire mod in one image on the stock effects: MIDI SCENES, KITS, the recorder fixes, the KYOTI direct jump and reload, USB. | port-gated |
| [`mute-modes`](mute-modes/README.md) | stock effects with MUTE_MODES: PERSONALIZE > MUTE MODE (OT, OTFX, OTFX-T, DT-T). | `make check` |
| [`octatrick`](octatrick/README.md) | SYNTH MACHINE + SCALE QUANTIZER + DIRECT JUMP + TUNER + USB (20 channels out, 4 in onto A-D) on the stock effects less SPATIALIZER. | on hardware: Tim's MKI, test build 3.0 b40 (this selection at BUILD 40), 29 Sep 2026: USB AUDIO IN brings the Mac's audio onto the inputs in a one-minute check (long runs not yet tested). The same four modules with the 26 Sep USB AUDIO (out only) ran on the same MKI through the 2.9 test builds; the tuner works on test build 3.0 b40 (UP + TEMPO); the last two 2.9 fixes are not yet confirmed on hardware |
| [`persistent-buffers`](persistent-buffers/README.md) | Recorder buffers BUFFERS/REC1.wav..REC8.wav under the project on SAVE / LOAD. | `make check`: verify_persistent_buffers under the port |
| [`plocks-p2`](plocks-p2/README.md) | Page-2 parameter locks (PLOCKS P2) and page-2 scene locks (SCENES P2), stock effects. | port-gated: verify_plocks_p2 under the port |
| [`quantize-live-rec-toggle`](quantize-live-rec-toggle/README.md) | stock effects with QUANTIZE_LIVE_REC_TOGGLE: QUANTIZE LIVE REC from [REC] + [PLAY]. | `make check` |
| [`rec-threshold`](rec-threshold/README.md) | stock effects with the threshold-armed recorder TRIG THR, its LEV and an IN meter: the image for a unit. | on hardware: Chupitnik's MKII, 11-13 Oct 2026, THR1 to THR9 from the card: armed with TRACK 1 + REC AB, silence never records, the input starts the take, a second press cancels, LEV and IN on RECORDING SETUP 2, TRIG moved off THR while armed drops the arm and the blink, an armed track's icon blinks, armed inside RECORDING SETUP 1 it records; THR9 is this code |
| [`rec-trig-mute`](rec-trig-mute/README.md) | stock effects with REC_TRIG_MUTE: [TRACK]+[NO]/[YES] mute/unmute recorder trigs. | `make check` |
| [`reload-from-project`](reload-from-project/README.md) | stock effects with RELOAD_FROM_PROJECT: reload one track's sequence from the card while the transport runs. | `make check` |
| [`remix-switch`](remix-switch/README.md) | stock effects with BRAIN and REMIX SWITCH: MAIN MENU > BRAIN boots a .RMX from /BRAIN/REMIXES/, no flash write. | port-gated: the chainload under the port (verify_remix_switch) |
| [`remix-switch-trace`](remix-switch-trace/README.md) | remix-switch + BOOT TRACE: a MIDI note per boot stage, to find where a boot after a switch hangs. | port-gated: the notes under the port (verify_boot_trace) |
| [`rig`](rig/README.md) | octabam-bus's delay and reverb bus and FX1 stations, without USB, Octakit or the scene modules: the fixture of the CC MAP, Character and one-aux gates. | `make check` |
| [`rnd-name`](rnd-name/README.md) | smoke: RND NAME alone | local render: RND NAME smoke |
| [`scenes-midisc`](scenes-midisc/README.md) | MIDI SCENES + KITS + page-2 scene locks (SCENES P2) + page-2 parameter locks (PLOCKS P2), stock effects. | port-gated: verify_scenes_p2 and verify_plocks_p2 under the port |
| [`sidechain-compressor`](sidechain-compressor/README.md) | stock effects with SIDECHAIN_COMPRESSOR in COMPRESSOR's row: KEY, KFLT, KGN and MON on page 2. | `make check` |
| [`sos-capture`](sos-capture/README.md) | recorder fixes + USB (TRACKS out, AB in) (stock effects minus SPATIALIZER). | port-gated: `make check` under the port; not on hardware in this form |
| [`stations-fx2`](stations-fx2/README.md) | SPECTRUM, CHARACTER and MODULATION on FX1 and FX2, beside the stock DELAY. | port-gated: `verify_stations_fx2` (dsp_host); not on a unit |
| [`stems`](stems/README.md) | STEM REC on the stock effects: multitrack recording to the card, each track, MAIN, CUE and the inputs as separate WAV files. | on hardware: Yves's MKII, 6 Oct 2026 (STEMS3) |
| [`stems-brain`](stems-brain/README.md) | STEM REC (UP+REC) with BRAIN on the root: coexistence without two menu growers. | port-gated: verify_stems_menu under ot_emu |
| [`tapeecho`](tapeecho/README.md) | Tape Echo replacing Spring Reverb, alone. | on hardware: the author's unit (OCTACLID4): six instances; a seventh freezes it, open |
| [`testgen`](testgen/README.md) | TESTGEN on FX1 beside the stock effects (all but PLATE REV, whose words it takes). | on hardware: Ignorato's MKII, OCTABAM6, 4 Oct 2026 |
| [`transient`](transient/README.md) | TRANSIENT beside the stock effects (all but PLATE REV, whose words it takes). | on hardware: Ignorato's MKII, OCTABAM2, 3 Oct 2026 |
| [`usb-io-main-ab`](usb-io-main-ab/README.md) | stock - SPATIALIZER + USB (MAIN out, AB in). | port-gated: `make check` (verify_usb, verify_usb_in) under the port, 28 Sep 2026; not on hardware in this form |
| [`usb-io-main-abcd`](usb-io-main-abcd/README.md) | stock - SPATIALIZER + USB (MAIN out, ABCD in). | port-gated: `make check` (verify_usb, verify_usb_in) under the port, 28 Sep 2026; not on hardware in this form |
| [`usb-io-main-cd`](usb-io-main-cd/README.md) | stock - SPATIALIZER + USB (MAIN out, CD in). | port-gated: `make check` (verify_usb, verify_usb_in) under the port, 28 Sep 2026; not on hardware in this form |
| [`usb-io-main-cue-ab`](usb-io-main-cue-ab/README.md) | stock - SPATIALIZER + USB (MAIN CUE out, AB in). | port-gated: `make check` (verify_usb, verify_usb_in) under the port, 28 Sep 2026; not on hardware in this form |
| [`usb-io-main-cue-abcd`](usb-io-main-cue-abcd/README.md) | stock - SPATIALIZER + USB (MAIN CUE out, ABCD in). | port-gated: `make check` (verify_usb, verify_usb_in) under the port, 28 Sep 2026; not on hardware in this form |
| [`usb-io-main-cue-cd`](usb-io-main-cue-cd/README.md) | stock - SPATIALIZER + USB (MAIN CUE out, CD in). | port-gated: `make check` (verify_usb, verify_usb_in) under the port, 28 Sep 2026; not on hardware in this form |
| [`usb-io-tracks-ab`](usb-io-tracks-ab/README.md) | stock - SPATIALIZER + USB (TRACKS out, AB in). | port-gated: `make check` (verify_usb, verify_usb_in) under the port, 28 Sep 2026; not on hardware in this form |
| [`usb-io-tracks-abcd`](usb-io-tracks-abcd/README.md) | stock - SPATIALIZER + USB (TRACKS out, ABCD in). | port-gated: `make check` (verify_usb, verify_usb_in) under the port, 28 Sep 2026; not on hardware in this form |
| [`usb-io-tracks-cd`](usb-io-tracks-cd/README.md) | stock - SPATIALIZER + USB (TRACKS out, CD in). | port-gated: `make check` (verify_usb, verify_usb_in) under the port, 28 Sep 2026; not on hardware in this form |
| [`usb-io-tracks-main-cue-ab`](usb-io-tracks-main-cue-ab/README.md) | stock - SPATIALIZER + USB (TRACKS MAIN CUE out, AB in). | port-gated: `make check` (verify_usb, verify_usb_in) under the port, 28 Sep 2026; not on hardware in this form |
| [`usb-io-tracks-main-cue-abcd`](usb-io-tracks-main-cue-abcd/README.md) | stock - SPATIALIZER + USB (TRACKS MAIN CUE out, ABCD in). | port-gated: `make check` (verify_usb, verify_usb_in) under the port, 28 Sep 2026; not on hardware in this form |
| [`usb-io-tracks-main-cue-cd`](usb-io-tracks-main-cue-cd/README.md) | stock - SPATIALIZER + USB (TRACKS MAIN CUE out, CD in). | port-gated: `make check` (verify_usb, verify_usb_in) under the port, 28 Sep 2026; not on hardware in this form |
| [`usb-midi`](usb-midi/README.md) | stock + USB MIDI (class-compliant, mirrors DIN). | `make check` |
| [`usb-out-main`](usb-out-main/README.md) | stock + USB (MAIN) (2 ch: MAIN L/R). | port-gated: `verify_usb` under the port, 28 Sep 2026 |
| [`usb-out-main-cue`](usb-out-main-cue/README.md) | stock + USB (MAIN CUE) (4 ch: MAIN + CUE). | port-gated |
| [`usb-out-master`](usb-out-master/README.md) | stock + USB (MASTER) (2 ch: track 8). | port-gated |
| [`usb-out-tracks`](usb-out-tracks/README.md) | stock + USB (TRACKS) (16 ch: the tracks). | port-gated |
| [`usb-out-tracks-main-cue`](usb-out-tracks-main-cue/README.md) | stock + USB MIDI + USB AUDIO (20 ch: tracks, MAIN, CUE); PLATE REV harvested for USB's words. | port-gated |
| [`usb-out-tracks-post`](usb-out-tracks-post/README.md) | stock + USB (TRACKS POST) (16 ch: the tracks after their own MAIN gain). | on hardware: allmyfriendsaresynths's MKII, P3, 5 Oct 2026 (smoke test: 16 channels, LEVEL/mute/solo/crossfader follow) |
| [`varispeed`](varispeed/README.md) | stock effects with VARISPEED: TSTR VARI, QUAN on PTCH. | `make check` |
| [`vocoder`](vocoder/README.md) | VOCODER beside the stock effects (all but PLATE REV, whose words it takes, and DJ EQ, so its table sits in X). | on hardware: Ignorato's MKII, OCTABAM12 (the earlier positions T1 T2 T5 T6), 4 Oct 2026; the current positions (T2 T4 T6 T8) not flashed |
| [`vocoder-usb`](vocoder-usb/README.md) | The vocoder remix plus USB MIDI and USB audio out, TRACKS MAIN CUE (20 channels over USB: the tracks, MAIN, CUE). | port-gated: make check under the ColdFire port, 10 Oct 2026; not flashed |
| [`wave`](wave/README.md) | Experiment: a 4-voice wavetable synth on FX2, played by a sine on its track; SCALE QUANTIZER, page-2 tools, USB out; DARK and SPRING REV give up their words. | on hardware: Sam's MKII, image 93, 3 Oct 2026: plays, PTCH and the CHROMATIC keys move the pitch |
| [`waveload`](waveload/README.md) | CF METER + WAVE LOAD on stock: T8's FX2 BURN = K 4-voice wave engines per frame interrupt, read over USB. | on hardware: image 92, Sam's MKII, 3 Oct 2026 |
| [`waveload-port`](waveload-port/README.md) | waveload without the idle loop: the port gate for the wave engines in the frame interrupt. | port-gated: the load path under the port |
