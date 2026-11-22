# Test remixes

Each carries one module, or one combination, for that module's gates: `make check REMIX=<name>`. Rendered by `make docs`; the remixes a user flashes are [one level up](../README.md).

| remix | contains |
|---|---|
| [`analog-bassdrum`](analog-bassdrum/README.md) | Analog BD source machine, switchable 808/909, stock AMP and FX. |
| [`ata-write-guard`](ata-write-guard/README.md) | Stock effects with the first PIO card write guarded through bookkeeping. |
| [`bar-led`](bar-led/README.md) | stock effects with BAR LED: the tempo LED flashes green on the pattern's 1 while playing. |
| [`batch-bugfixes`](batch-bugfixes/README.md) | stock effects with BATCH_BUGFIXES: the MIDI Plays-Free trig, empty-pattern LED and Part-change carryover fixes. |
| [`bbd`](bbd/README.md) | BBD beside the stock effects (all but SPRING REV and PLATE REV, whose words it takes). |
| [`blackpyramids-303`](blackpyramids-303/README.md) | BLACKPYRAMIDS_303 (BLKPYRAMD, a TB-303 voice as a track machine) with the stock effects, SPRING REV given up. |
| [`buffer-saver`](buffer-saver/README.md) | stock effects with SAVE PROJECT offering to save the recorder buffers' unsaved takes, each assigned to itself. |
| [`bus`](bus/README.md) | The plain two-server image: BusVerb + BusDelay + send bus + tempo sync. |
| [`bus-notempo`](bus-notempo/README.md) | bus with TEMPO SYNC's CAVE pinned OFF (diagnostic). |
| [`bus-tempo-replay`](bus-tempo-replay/README.md) | bus with TEMPO SYNC's CAVE pinned REPLAY (diagnostic). |
| [`cfmeter`](cfmeter/README.md) | octatrick (less TUNER and the USB input) + CF METER on T8's FX2: ColdFire idle time and frame-interrupt duration, over USB. |
| [`cfmeter-port`](cfmeter-port/README.md) | cfmeter without the idle loop: the port gate for the readout chain and the interrupt timing. |
| [`cfmeter-post`](cfmeter-post/README.md) | octatrick (less TUNER and the USB input) + CF METER on T8's FX2, with USB TRACKS POST in place of TRACKS MAIN CUE: POST's ColdFire cost, over USB. |
| [`cfmeter-tracks`](cfmeter-tracks/README.md) | octatrick (less TUNER and the USB input) + CF METER on T8's FX2, with USB TRACKS in place of TRACKS MAIN CUE: the 16-channel-only stream's ColdFire cost, over USB. |
| [`character-key`](character-key/README.md) | stock effects with KEYBUS and CHARACTER: CHARACTER's KEY reads T1..T8 from KEYBUS's shared key words. |
| [`character-txtr`](character-txtr/README.md) | octabam-bus with CHARACTER TXTR (Character + Airwindows Pockey2 texture) on FX1 in place of CHARACTER: the image for measuring the texture stage's cost on a unit. |
| [`chop-tempo`](chop-tempo/README.md) | stock effects with LAZY CHOP and LAZY CHOP TEMPO (BPM popup after YES). |
| [`chords`](chords/README.md) | CHORDS FACTORY with SCALES, on the 14 stock effects: the chord atelier on SRC, a chord step played as written, the FUNC keyboard in the scale's colours. |
| [`chords-alone`](chords-alone/README.md) | CHORDS FACTORY without SCALES, on the 14 stock effects: the atelier alone on SRC, chords played as written (no scale). |
| [`copy-project`](copy-project/README.md) | stock effects with COPY PROJECT: duplicate a project on the card without loading it. |
| [`cxosc`](cxosc/README.md) | CX OSC (machine list, no marker): PLAYBACK PTCH RATO INDX FINE FOLD MIX; SETUP CAR MOD DEC SYMM FDBK PWM; stock FX. |
| [`devilish`](devilish/README.md) | OCTA303 and dEVILish (the Devil Fish mods on FX1 or FX2 of an OCTA-303 track) beside the stock effects but PHASER. |
| [`direct-jump-kyoti`](direct-jump-kyoti/README.md) | stock effects with DIRECT_JUMP_KYOTI: [PTN] + [YES] toggles an immediate, clock-locked pattern change. |
| [`distorx`](distorx/README.md) | DISTORX on FX1 and FX2, beside the stock effects but CHORUS, PLATE REV and SPRING REV, whose words it takes. |
| [`dl-probe`](dl-probe/README.md) | octabam with DLPROBE on FX1 in place of EQUALIZER (the loader as in octabam). |
| [`dl-probe-any`](dl-probe-any/README.md) | octabam with DLPROBE on FX1 in place of EQUALIZER, and the loader sending on every frame. |
| [`dlspike`](dlspike/README.md) | Demand-load spike: MODULATION loaded on demand. |
| [`drummer`](drummer/README.md) | DRUMMER alone: T1's sliced loop played as a drummer. |
| [`drummer-probe`](drummer-probe/README.md) | DRUMMER PROBE alone: trigs added and moved after the step builder, the FLEX start's slice forced. |
| [`erase-empty-trigless-locks`](erase-empty-trigless-locks/README.md) | stock effects with ERASE_EMPTY_TRIGLESS_LOCKS: an emptied trigless lock disappears. |
| [`euclid`](euclid/README.md) | Euclid rhythmic modulation: 12 dB LP/BP/HP or AMP, both FX slots. |
| [`events-clients`](events-clients/README.md) | EVENTS with EUCLID in both FX slots, PLOCKS P2, USB MAIN/CUE and LOAD METER. |
| [`events-empty`](events-empty/README.md) | EVENTS with no clients: no event hooks or dispatcher code. |
| [`ext-probe`](ext-probe/README.md) | octabam's core and stock effects (EQUALIZER's id is the probe's) with EXTPROBE on FX1: the highest window word a reverb writes. |
| [`frame-guard`](frame-guard/README.md) | Stock effects with a late frame interrupt held out of the DSP's stall window. |
| [`free-loop`](free-loop/README.md) | stock effects with FREE LOOP: a loop pedal per track, the first free loop sets the tempo. |
| [`hooks`](hooks/README.md) | REC THRESHOLD and FREE LOOP together (HOOKS bridges the status icons) with STORE and the stock effects. |
| [`hooks-boot`](hooks-boot/README.md) | BOOT TRACE beside STORE and MIDI LOOPBACK: HOOKS runs both at the boot's post-loader call. |
| [`hooks-chrom-303`](hooks-chrom-303/README.md) | OCTA303 (the OCTA-303 machine) beside SCALE QUANTIZER: HOOKS gives a 303 track's CHROMATIC keys to OCTA303 and every other track's to SCALE QUANTIZER. |
| [`hooks-chrom-bp`](hooks-chrom-bp/README.md) | BLACKPYRAMIDS_303 beside SCALE QUANTIZER: HOOKS gives a BLACKPYRAMIDS track's CHROMATIC octave keys, key index and keyboard picture to it and every other track's to SCALE QUANTIZER; SPRING REV given up. |
| [`hooks-core`](hooks-core/README.md) | CORE + MORPH, REC THRESHOLD, CF METER, CF METER IDLE and BOOT TRACE: HOOKS owns the sites they share with CORE. |
| [`hooks-free-loop`](hooks-free-loop/README.md) | FREE LOOP beside REC_TRIG_MUTE and REC THRESHOLD: HOOKS chains the status icons (REC THRESHOLD, FREE LOOP) and the step handler's recorder-trig test (FREE LOOP, REC_TRIG_MUTE). |
| [`hooks-machines`](hooks-machines/README.md) | ANALOG BD and OCTA303 in one image: HOOKS gives the track's machine list seven rows, ANALOG BD on row 5 and OCTA-303 on row 6, and the list scrolls. |
| [`hooks-machines-all`](hooks-machines-all/README.md) | ANALOG BD, OCTA303 and CX OSC in one image: HOOKS gives the track's machine list eight rows, ANALOG BD on row 5, OCTA-303 on row 6 and CX OSC on row 7, and the list scrolls. |
| [`hooks-machines-cx`](hooks-machines-cx/README.md) | OCTA303 and CX OSC in one image: HOOKS gives the track's machine list seven rows, OCTA-303 on row 5 and CX OSC on row 6, and the list scrolls. |
| [`hooks-reload`](hooks-reload/README.md) | FREE LOOP beside RELOAD_FROM_PROJECT: HOOKS chains the UI task's tick 0x40056c28 (FREE LOOP, then RELOAD_FROM_PROJECT). |
| [`ids64`](ids64/README.md) | BBD on FX2 id 0x25 in a 64-id image (DSP dispatch and ColdFire tables grown). |
| [`keybus`](keybus/README.md) | KEYBUS alone (every track's key level in eight shared words) on the stock effects. |
| [`kits`](kits/README.md) | KITS (255 Kits per project) on the stock effects. |
| [`kyoti-fixes`](kyoti-fixes/README.md) | stock effects with QUANTIZE_LIVE_REC_TOGGLE, ERASE_EMPTY_TRIGLESS_LOCKS and BATCH_BUGFIXES together. |
| [`kyoti-mute-jump`](kyoti-mute-jump/README.md) | stock effects with MUTE_MODES and DIRECT_JUMP_KYOTI together. |
| [`kyoti-mute-sidechain`](kyoti-mute-sidechain/README.md) | stock effects with MUTE_MODES and SIDECHAIN_COMPRESSOR together: a muted KEY track keeps feeding the compressor (SC_KEY). |
| [`lazy-chop`](lazy-chop/README.md) | stock effects with LAZY CHOP (tap TRIG 1..16 to slice a take) and BUFFER SAVER. |
| [`lock-edit`](lock-edit/README.md) | stock effects with LOCK EDIT ([TRIG]+[BANK] in grid recording opens the audio editor on the step's sample and slice). |
| [`lofi-amf-fix`](lofi-amf-fix/README.md) | Reference minimal build: the LO-FI AMF mpysu->mpyuu fix, alone. |
| [`lofi2`](lofi2/README.md) | LOFI2 beside the stock effects (all but PLATE REV and SPRING REV, whose words it takes). |
| [`midi-follow`](midi-follow/README.md) | Per-track RFOL source selection on MIDI NOTE SETUP; Part-owned bass following. |
| [`midi-follow-events`](midi-follow-events/README.md) | MIDI Follow with EUCLID and PLOCKS P2 sharing EVENTS notifications. |
| [`midi-loopback`](midi-loopback/README.md) | Stock effects plus the Part-scoped per-track MIDI loopback routing. |
| [`midi-scales`](midi-scales/README.md) | All twelve keys and seven modes in the native ARP SETUP KEY control. |
| [`midi-scenes`](midi-scenes/README.md) | Reference minimal build: the MIDI SCENES ColdFire patch, plus direct-jump so `swd` runs. |
| [`miniverb`](miniverb/README.md) | Minimal allocator-owned FDN reverb. |
| [`mods`](mods/README.md) | Every ColdFire mod in one image on the stock effects: MIDI SCENES, KITS, the recorder fixes, the KYOTI direct jump and reload, USB. |
| [`morph`](morph/README.md) | MORPH (track + UP / DOWN: the scene morph by itself, saved with the project) with STORE and the stock effects. |
| [`mute-modes`](mute-modes/README.md) | stock effects with MUTE_MODES: PERSONALIZE > MUTE MODE (OT, OTFX, OTFX-T, DT-T). |
| [`octa303`](octa303/README.md) | the OCTA-303 machine (a circuit-modelled TB-303 voice on the ColdFire) with the stock effects. |
| [`octatrick`](octatrick/README.md) | SYNTH MACHINE + SCALE QUANTIZER + DIRECT JUMP + TUNER + USB (20 channels out, 4 in onto A-D) on the stock effects less SPATIALIZER. |
| [`page-loop`](page-loop/README.md) | stock effects with PAGE LOOP: loop one page of one track, in time. |
| [`pattern-mute`](pattern-mute/README.md) | smoke: PATTERN MUTE alone, with STORE (pmute.work) |
| [`pattern-mute-modes`](pattern-mute-modes/README.md) | smoke: PATTERN MUTE and MUTE_MODES together, stock effects |
| [`persistent-buffers`](persistent-buffers/README.md) | Recorder buffers BUFFERS/REC1.wav..REC8.wav under the project on SAVE / LOAD. |
| [`pext-probe`](pext-probe/README.md) | PEXT PROBE on FX1 and USB audio out (TRACKS) beside the stock effects (all but EQUALIZER, whose id it takes, and PLATE REV and SPRING REV, whose words it takes). |
| [`plocks-p2`](plocks-p2/README.md) | Page-2 parameter locks (PLOCKS P2) and page-2 scene locks (SCENES P2), stock effects. |
| [`quantize-live-rec-toggle`](quantize-live-rec-toggle/README.md) | stock effects with QUANTIZE_LIVE_REC_TOGGLE: QUANTIZE LIVE REC from [REC] + [PLAY]. |
| [`rec-cs1-skip`](rec-cs1-skip/README.md) | stock effects with REC CS1 SKIP: the recorder's control-record update without its redundant CS1 writes. |
| [`rec-threshold`](rec-threshold/README.md) | stock effects with the threshold-armed recorder TRIG THR, its LEV and an IN meter: the image for a unit. |
| [`rec-trig-mute`](rec-trig-mute/README.md) | stock effects with REC_TRIG_MUTE: [TRACK]+[REC] mutes/unmutes a track's recorder trigs. |
| [`reload-from-project`](reload-from-project/README.md) | stock effects with RELOAD_FROM_PROJECT: reload one track's sequence from the card while the transport runs. |
| [`remix-switch`](remix-switch/README.md) | stock effects with BRAIN and REMIX SWITCH: MAIN MENU > BRAIN boots a .RMX from /BRAIN/REMIXES/, no flash write. |
| [`remix-switch-trace`](remix-switch-trace/README.md) | remix-switch + BOOT TRACE: a MIDI note per boot stage, to find where a boot after a switch hangs. |
| [`remote`](remote/README.md) | Stock effects with REMOTE's event ring, read over USB. |
| [`resonator`](resonator/README.md) | RESONATOR on FX1 beside the stock effects (all but PLATE REV). |
| [`rig`](rig/README.md) | octabam-bus's delay and reverb bus and FX1 stations, without USB, Octakit or the scene modules: the fixture of the CC MAP, Character and one-aux gates. |
| [`rnd-name`](rnd-name/README.md) | smoke: RND NAME alone |
| [`rs64`](rs64/README.md) | remix-switch with id_space=64 and BBD on FX2 id 0x25 in the shared window: the gate for REMIX SWITCH's DSP upload in a grown image. |
| [`scales`](scales/README.md) | SCALES alone, on the 14 stock effects: ARP SETUP's KEY, the chooser, the snapped notes and the CHROMATIC keys. |
| [`scales-quantizer`](scales-quantizer/README.md) | SCALES beside SCALE QUANTIZER: the audio tracks' CHROMATIC keys light SCALE on ROOT. |
| [`scenes-midisc`](scenes-midisc/README.md) | MIDI SCENES + KITS + page-2 scene locks (SCENES P2) + page-2 parameter locks (PLOCKS P2), stock effects. |
| [`scope`](scope/README.md) | stock effects with SCOPE and TUNER sharing the TEMPO, frame and UI hooks. |
| [`scope-alone`](scope-alone/README.md) | stock effects with standalone SCOPE and no TUNER module. |
| [`screen`](screen/README.md) | stock effects with SCREEN. |
| [`screen-usb`](screen-usb/README.md) | stock + USB MIDI + SCREEN. |
| [`seq`](seq/README.md) | STORE + SEQ (euclid.work client) with the stock effects. |
| [`shatter`](shatter/README.md) | SHATTER beside the stock effects (all but PLATE REV, whose words it takes). |
| [`sidechain-compressor`](sidechain-compressor/README.md) | stock effects with SIDECHAIN_COMPRESSOR in COMPRESSOR's row: MON, KEY, KGN, KBAS and KWID on page 2. |
| [`slow-lfo`](slow-lfo/README.md) | stock effects with SLOW LFO: LFO MULT gains 1/2X, 1/4X and 1/8X on audio and MIDI tracks. |
| [`sos-capture`](sos-capture/README.md) | recorder fixes + USB (TRACKS out, AB in) (stock effects minus SPATIALIZER). |
| [`src3-key`](src3-key/README.md) | stock effects with SRC3 KEY ([MIDI] in the audio editor records SRC3 on the MKI). |
| [`stations-fx2`](stations-fx2/README.md) | SPECTRUM, CHARACTER and MODULATION on FX1 and FX2, beside the stock DELAY. |
| [`stems`](stems/README.md) | STEM REC on the stock effects: multitrack recording to the card, each track, MAIN, CUE and the inputs as separate WAV files. |
| [`stems-brain`](stems-brain/README.md) | STEM REC (UP+REC) with BRAIN on the root: coexistence without two menu growers. |
| [`stock-meter-a`](stock-meter-a/README.md) | CORE with LOAD METER and the stock effects except PHASER. |
| [`stock-meter-b`](stock-meter-b/README.md) | CORE with LOAD METER and the stock effects except SPATIALIZER. |
| [`stuttr`](stuttr/README.md) | STUTTR beside the stock effects (all but PLATE REV, whose words it takes). |
| [`tapeecho`](tapeecho/README.md) | Tape Echo replacing Spring Reverb, alone. |
| [`testgen`](testgen/README.md) | TESTGEN on FX1 beside the stock effects (all but PLATE REV, whose words it takes). |
| [`track-trig-mode`](track-trig-mode/README.md) | stock effects with TRACK TRIG MODE: Hteah's single-mode track trig editing. |
| [`trackpatterns`](trackpatterns/README.md) | TRACK PATTERNS with the stock effects: hold TRACK + PATTERN + TRIG for a pattern per track. |
| [`trackpatterns-core`](trackpatterns-core/README.md) | TRACK PATTERNS on the core modules (KITS, DIRECT_JUMP_KYOTI and the other core modules). |
| [`transient`](transient/README.md) | TRANSIENT beside the stock effects (all but PLATE REV, whose words it takes). |
| [`trig-mute`](trig-mute/README.md) | stock effects with TRIG MUTE: mute a single trig without deleting it. |
| [`usb-io-main-ab`](usb-io-main-ab/README.md) | stock - SPATIALIZER + USB (MAIN out, AB in). |
| [`usb-io-main-abcd`](usb-io-main-abcd/README.md) | stock - SPATIALIZER + USB (MAIN out, ABCD in). |
| [`usb-io-main-cd`](usb-io-main-cd/README.md) | stock - SPATIALIZER + USB (MAIN out, CD in). |
| [`usb-io-main-cue-ab`](usb-io-main-cue-ab/README.md) | stock - SPATIALIZER + USB (MAIN CUE out, AB in). |
| [`usb-io-main-cue-abcd`](usb-io-main-cue-abcd/README.md) | stock - SPATIALIZER + USB (MAIN CUE out, ABCD in). |
| [`usb-io-main-cue-cd`](usb-io-main-cue-cd/README.md) | stock - SPATIALIZER + USB (MAIN CUE out, CD in). |
| [`usb-io-stock14`](usb-io-stock14/README.md) | stock (all 14) + USB (MAIN CUE out, ABCD in), the inject at payload A's tail. |
| [`usb-io-tracks-ab`](usb-io-tracks-ab/README.md) | stock - SPATIALIZER + USB (TRACKS out, AB in). |
| [`usb-io-tracks-abcd`](usb-io-tracks-abcd/README.md) | stock - SPATIALIZER + USB (TRACKS out, ABCD in). |
| [`usb-io-tracks-cd`](usb-io-tracks-cd/README.md) | stock - SPATIALIZER + USB (TRACKS out, CD in). |
| [`usb-io-tracks-main-cue-ab`](usb-io-tracks-main-cue-ab/README.md) | stock - SPATIALIZER + USB (TRACKS MAIN CUE out, AB in). |
| [`usb-io-tracks-main-cue-abcd`](usb-io-tracks-main-cue-abcd/README.md) | stock - SPATIALIZER + USB (TRACKS MAIN CUE out, ABCD in). |
| [`usb-io-tracks-main-cue-cd`](usb-io-tracks-main-cue-cd/README.md) | stock - SPATIALIZER + USB (TRACKS MAIN CUE out, CD in). |
| [`usb-midi`](usb-midi/README.md) | stock + USB MIDI (class-compliant, mirrors DIN). |
| [`usb-out-main`](usb-out-main/README.md) | stock + USB (MAIN) (2 ch: MAIN L/R). |
| [`usb-out-main-cue`](usb-out-main-cue/README.md) | stock + USB (MAIN CUE) (4 ch: MAIN + CUE). |
| [`usb-out-master`](usb-out-master/README.md) | stock + USB (MASTER) (2 ch: track 8). |
| [`usb-out-tracks`](usb-out-tracks/README.md) | stock + USB (TRACKS) (16 ch: the tracks). |
| [`usb-out-tracks-main-cue`](usb-out-tracks-main-cue/README.md) | stock + USB MIDI + USB AUDIO (20 ch: tracks, MAIN, CUE); PLATE REV harvested for USB's words. |
| [`usb-out-tracks-post`](usb-out-tracks-post/README.md) | stock + USB (TRACKS POST) (16 ch: the tracks after their own MAIN gain). |
| [`varispeed`](varispeed/README.md) | stock effects with VARISPEED: TSTR VARI, QUAN on PTCH. |
| [`verberation`](verberation/README.md) | VERBERATION alone: the fixture of its render gate. |
| [`vibrato`](vibrato/README.md) | VIBRATO on FX1 beside the stock effects (all but PLATE REV). |
| [`vibrato-fx2`](vibrato-fx2/README.md) | VIBRATO live on FX1 and FX2 beside the stock effects (all but PLATE REV). |
| [`vocoder`](vocoder/README.md) | VOCODER beside the stock effects (all but PLATE REV, whose words it takes, and DJ EQ, so its table sits in X). |
| [`vocoder-usb`](vocoder-usb/README.md) | The vocoder remix plus USB MIDI and USB audio out, TRACKS MAIN CUE (20 channels over USB: the tracks, MAIN, CUE). |
| [`void`](void/README.md) | VOID replaces COMB FILTER; PLATE REV words host its DSP. |
| [`wavecf`](wavecf/README.md) | the WAVE machine (a 4-voice wavetable voice on the ColdFire) with the stock effects. |
| [`wavecf-octa303`](wavecf-octa303/README.md) | WAVE and OCTA303 in one image: HOOKS gives the track's machine list seven rows, OCTA-303 on row 5 and WAVE on row 6; a Part holds two machines of either kind. |
| [`waveload`](waveload/README.md) | CF METER + WAVE LOAD on stock: T8's FX2 BURN = K 4-voice wave engines per frame interrupt, read over USB. |
| [`waveload-port`](waveload-port/README.md) | waveload without the idle loop: the port gate for the wave engines in the frame interrupt. |
| [`window-ctl`](window-ctl/README.md) | CORE with LOAD METER and MODULATION in the shared window beside the stock effects (all but CHORUS, whose id it takes, and the three reverbs). |
| [`window-mod`](window-mod/README.md) | CORE with LOAD METER and MODULATION in the shared window beside the stock effects (all but CHORUS, whose id it takes, and the three reverbs). |
| [`xfcurve`](xfcurve/README.md) | XF CURVE (the crossfader's curve, a BRAIN setting) with BRAIN, STORE and the stock effects. |
| [`xfcurve-scurve`](xfcurve-scurve/README.md) | XF CURVE pinned to S-CURVE, without BRAIN, on the stock effects. |
| [`zoom-keep`](zoom-keep/README.md) | stock effects with ZOOM KEEP (the audio editor keeps its zoom when a slice is auditioned). |
