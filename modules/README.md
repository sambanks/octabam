# Modules

A module is one contribution: an effect, a machine, a sequencer or MIDI feature, a fix, or a service other modules use. Each is `modules/<name>/` with a `manifest.py` and a `README.md`. What each does on the unit is in the [manual](https://sambanks.github.io/octabam/); writing one is [MODULES.md](../docs/contributing/MODULES.md). Rendered from the manifests by `make docs`.

## Effects: the bus

| module | author | what it does |
|---|---|---|
| [**DELAY SERVER**](busdelay/README.md) | [Sam Banks](https://github.com/sambanks) | Multi-mode delay: CLEAN / pitched GRAIN cloud / REVERSE, tape wow. |
| [**REVERB SERVER**](busverb/README.md) | [Sam Banks](https://github.com/sambanks) | Eight-line FDN reverb: ROOM/PLATE/BIG, shimmer, gate, mid/side width. |
| [**FX2 LOCK**](fx2-lock/README.md) | [Sam Banks](https://github.com/sambanks) | Locks each track's FX2 effect: the FX2 chooser cannot change it. |
| [**MODE DEFAULTS**](mode-defaults/README.md) | [Sam Banks](https://github.com/sambanks) | Turning a MODE knob resets the knobs around it to that mode's defaults, on FX1 and FX2. |
| [**RIG HOSTS**](rig-hosts/README.md) | [Sam Banks](https://github.com/sambanks) | A new Part starts wired for the bus: the bus delay on T1's FX2, the bus reverb on T5's, the stock DELAY on T8's and SEND on the rest. |
| [**SEND**](send/README.md) | [Sam Banks](https://github.com/sambanks) | Bus client: DEL into the delay, REV into the reverb, from any track. The default effect. |
| [**TEMPO BUS**](tempo-bus/README.md) | [Sam Banks](https://github.com/sambanks) | The TEMPO window lists and edits BusDelay's and BusVerb's knobs (UP/DOWN = row, A or B = value, LEFT/RIGHT = engine, FUNC + LEVEL = 0.1 BPM). |
| [**TEMPO SYNC**](tempo-sync/README.md) | [Sam Banks](https://github.com/sambanks) | Syncs the bus delay to the tempo: TIME shows as a tempo division, and the held MIDI note reaches the delay. |

## Effects: on a track

| module | author | what it does |
|---|---|---|
| [**BBD**](bbd/README.md) | [JamCones](https://github.com/JamCones) | Clocked BBD delay: compander, clock/3 filters, bucket noise, freeze, governor; FX2. |
| [**CHARACTER**](character/README.md) | [Sam Banks](https://github.com/sambanks) | Channel strip: fold, saturation, tilt, compressor and width. |
| [**CHARACTER TXTR**](character-txtr/README.md) | [Sam Banks](https://github.com/sambanks) | Character plus TXTR (Airwindows Pockey2): fold, texture, saturation, tilt, compressor, width. |
| [**DEVILISH**](devilish/README.md) | [MaMarko](https://github.com/braikomarko-hub) | The Devil Fish mods (Robin Whittle) for an OCTA303 track: twelve knobs read by the 303 voice; the DSP passes the audio through. |
| [**DISTORX**](distorx/README.md) | [MaMarko](https://github.com/braikomarko-hub) | SD-1 + RAT + Turbo RAT in one insert: MODE picks the pedal (OFF first), a 3 ms fade between them. |
| [**DLPROBE**](dlprobe/README.md) | [Sam Banks](https://github.com/sambanks) | Measurement instrument: the demand loader's per-effect counters, in the track's audio. |
| [**EUCLID**](euclid/README.md) | [repeat98](https://github.com/repeat98) | Euclidean LP/BP/HP/notch/amp sequencer: swing, envelope, gate, random and loop. |
| [**EXTPROBE**](extprobe/README.md) | [Sam Banks](https://github.com/sambanks) | Measurement instrument: the highest window word a reverb on T8's FX2 writes, in the track's audio. |
| [**LOFI2**](lofi2/README.md) | [Bryan T](https://github.com/bryantysinger) | Ring mod or frequency shifter, then sample-rate and bit reduction. |
| [**MINIVERB**](miniverb/README.md) | [repeat98](https://github.com/repeat98) | Modulated diffused FDN reverb; independent FX2 buffers, smoothed controls. |
| [**MODULATION**](modulation/README.md) | [Sam Banks](https://github.com/sambanks) | Modulation pedal: Juno chorus, Dimension, flanger, phaser and comb. |
| [**PEXT PROBE**](pextprobe/README.md) | [Sam Banks](https://github.com/sambanks) | Measurement instrument: tests P memory above P:0x2000 and code in the shared window, and reports it in the track's audio. |
| [**RESONATOR**](resonator/README.md) | [ilia-murzinov](https://github.com/ilia-murzinov) | Four pitched resonant band-pass filters in the style of the Torso S-4's RING, with decay and a limiter. FX1 only. |
| [**SHATTER**](shatter/README.md) | [ilia-murzinov](https://github.com/ilia-murzinov) | Crush insert: fold, clip, crush, chaotic FDBK, stereo peak limiter after MIX. |
| [**SIDECHAIN_COMPRESSOR**](sidechain-compressor/README.md) | [Zac Kyoti](https://github.com/Zac-Kyoti) | Stock COMPRESSOR with a side-chain KEY from any of T1-T8, key gain, a base-width key filter (KBAS high-pass in Hz, KWID low-pass in octaves above it) and a key listen switch on page 2. |
| [**SPECTRUM**](spectrum/README.md) | [Sam Banks](https://github.com/sambanks) | Filter: Moog ladder, SEM state-variable, isolator (Airwindows Capacitor2) and formant bank, with an envelope and an LFO on the cutoff, and stereo width. |
| [**STUTTR**](stuttr/README.md) | [ilia-murzinov](https://github.com/ilia-murzinov) | Chance grain repeater: RATE/CHNC grab, HOLD loop, MODE rate, REV. |
| [**TAPE ECHO**](tapeecho/README.md) | [repeat98](https://github.com/repeat98) | Economy CPU tape echo: two biquads, simple FREE slew, snapped BEAT TIME and page-1 AGE. |
| [**TESTGEN**](testgen/README.md) | [Ignorato](https://github.com/Ignorato) | Measurement source: a sine, sweep, pink or white noise, impulses, a needle pulse train or DC replace the track's audio. |
| [**TRANSIENT**](transient/README.md) | [Ignorato](https://github.com/Ignorato) | Transient shaper: ATCK and SUST reshape onsets and tails, level-independent. |
| [**VERBERATION**](verberation/README.md) | [Sam Banks](https://github.com/sambanks) | A plate reverb for rooms to halls, after the reverb stage of Mutable Instruments Clouds (Emilie Gillet; Griesinger topology), with a desk-style gate: amount, gain, time, diffusion, tone, gate; size, low cut, modulation depth and rate. One FX2 slot per instance. |
| [**VERB HALL**](verberation-hall/README.md) | [Sam Banks](https://github.com/sambanks) | Not a separate reverb: a second chooser row for VERBERATION, on DARK REV's id, with MODE set to HALL (long, dark, slowly modulated), so a Part saved with DARK REV opens on it. |
| [**VERB PLATE**](verberation-plate/README.md) | [Sam Banks](https://github.com/sambanks) | Not a separate reverb: a second chooser row for VERBERATION, on PLATE REV's id, with MODE set to PLATE (a full plate), so a Part saved with PLATE REV opens on it. |
| [**VERB ROOM**](verberation-room/README.md) | [Sam Banks](https://github.com/sambanks) | Not a separate reverb: a second chooser row for VERBERATION, on SPRING REV's id, with MODE set to ROOM (small, bright and short), so a Part saved with SPRING REV opens on it. |
| [**VIBRATO**](vibrato/README.md) | [Bryan T](https://github.com/bryantysinger) | Pitch vibrato on FX1, or FX1 and FX2 (SLOTS) -- sine, triangle, square trill or random; depth in cents. |
| [**VOCODER**](vocoder/README.md) | [Ignorato](https://github.com/Ignorato) | Ten-band vocoder after the Roland VP-330: the track's voice, a built-in carrier at NOTE or input B. FX2 of tracks 2, 4, 6 and 8 only. |
| [**VOID**](void/README.md) | [ilia-murzinov](https://github.com/ilia-murzinov) | Noise texture: blends the track with noise shaped by an LFO or another track's level, with drive, feedback and stereo width. |

## Machines and the sequencer

| module | author | what it does |
|---|---|---|
| [**ANALOG BD**](analog-bassdrum/README.md) | [repeat98](https://github.com/repeat98) | Analog BD track machine: switchable 808/909 circuit-informed synthesis. |
| [**BAR LED**](bar-led/README.md) | [nathangroth](https://github.com/nathangroth) | The tempo LED flashes green on the pattern's 1 while playing; the other beats stay red. |
| [**BLACKPYRAMIDS_303**](blackpyramids-303/README.md) | [Zac Kyoti](https://github.com/Zac-Kyoti) | BLKPYRAMD: a TB-303 voice (built on Open303, recalibrated on the TB-303 circuit) as a track machine, one per DSP core, played by the sequencer, the chromatic keys and MIDI. |
| [**CX OSC**](cxosc/README.md) | [ilia-murzinov](https://github.com/ilia-murzinov) | Buchla-style complex oscillator as a machine: FM, a wavefolder, waveform morphs and feedback. |
| [**DIRECT JUMP**](direct-jump/README.md) | [timhastie](https://github.com/timhastie) | CHAIN AFTER: DIRECT (its unused value 1) -- a pattern change lands at the next step, the step count continuing (A4/Rytm direct jump). |
| [**DIRECT_JUMP_KYOTI**](direct-jump-kyoti/README.md) | [Zac Kyoti](https://github.com/Zac-Kyoti) | Clock-locked DIRECT JUMP ([PTN]+[YES]): a cued pattern lands on the next step exactly where it would be had it played since PLAY or the last pattern change. |
| [**DRUMMER**](drummer/README.md) | [djib](https://github.com/Djibdjib) | DRUMMER machine: a sliced FLEX drum loop played as a drummer (styles, humanisation, BRK breaks on the crossfader). |
| [**ERASE_EMPTY_TRIGLESS_LOCKS**](erase-empty-trigless-locks/README.md) | [Zac Kyoti](https://github.com/Zac-Kyoti) | Bug fix: a trigless lock whose last parameter lock is erased stops staying lit on the trig row (audio and MIDI tracks). |
| [**MUTE_MODES**](mute-modes/README.md) | [Zac Kyoti](https://github.com/Zac-Kyoti) | PERSONALIZE -> MUTE MODE: OT (stock) / OTFX / OTFX-T / DT-T -- dry cut with FX tails, trig suppression, or a Digitakt-style sequencer mute. |
| [**OCTA303**](octa303/README.md) | [MaMarko](https://github.com/braikomarko-hub) | A TB-303 voice: OCTA-303 as its own machine, or a FLEX track whose sample is named TB303*. Accent is an ACC lock, slide a trigless PTCH lock; dEVILish on FX1 or FX2 adds the Devil Fish mods. |
| [**PAGE LOOP**](page-loop/README.md) | [Hteah](https://github.com/Hteah) | GRID REC: PAGE + trig 1-4 loops that page of the current track, in time; again to stop. |
| [**PATTERN MUTE**](pattern-mute/README.md) | [Sam Banks](https://github.com/sambanks) | Double-press FUNC: mute edits go to a PATTERN layer kept per pattern, beside the GLOBAL layer (Digitakt II PATTERN MUTE / GLOBAL MUTE). |
| [**PLOCKS P2**](plocks-p2/README.md) | [Sam Banks](https://github.com/sambanks) | Parameter locks on FX1/FX2 page 2 (hold trigs, turn a knob on the SETUP page). |
| [**QUANTIZE_LIVE_REC_TOGGLE**](quantize-live-rec-toggle/README.md) | [Zac Kyoti](https://github.com/Zac-Kyoti) | QUANTIZE LIVE REC from the front panel: hold [REC], tap [PLAY] to see it, tap again while the toast is up to invert it. |
| [**SCALE QUANTIZER**](quantizer/README.md) | [timhastie](https://github.com/timhastie) | PROJECT > CONTROL > SEQUENCER > SCALE: the PTCH knob and CHROMATIC trig keys quantize to a scale (24 scales, OFF = stock); > ROOT: the note the scale is built on (C..B; key 1 of the CHROMATIC keyboard sounds it); > GLIDE: the synth's glide time (OFF, 1..127; the legato switch is the synth track's LEG setting); polyphonic chromatic keys on a synth track whose VOIC is 2..4; on a synth track PTCH is semitones (-64..+63) and the CHROMATIC octave runs -4..+4. |
| [**REC THRESHOLD**](rec-threshold/README.md) | [Chupitnik](https://github.com/Chupitnik) | Recorder TRIG value THR: a REC press arms, and recording starts when the input passes the track's LEV (RECORDING SETUP 2, beside a live IN meter). |
| [**REC_TRIG_MUTE**](rec-trig-mute/README.md) | [Zac Kyoti](https://github.com/Zac-Kyoti) | [TRACK]+[REC] mutes/unmutes the held tracks' recorder trigs; MIDI CC 80; '..' beside a muted track's tab letter. |
| [**RELOAD_FROM_PROJECT**](reload-from-project/README.md) | [Zac Kyoti](https://github.com/Zac-Kyoti) | Reload from the card without stopping the transport: [PTN]+[TRACK n] a track's sequence, [BANK]+[TRACK n] with its machine and effects too, [PTN]+[BANK]+trig a whole pattern (then the OT goes to it). |
| [**RLEN PLEN**](rlen-plen/README.md) | [Sam Banks](https://github.com/sambanks) | Adds PLEN to RLEN: a recording lasts one loop of the track's pattern, so TRIG ONE with QREC PLEN records the next pass and stops. |
| [**SEQ**](seq/README.md) | [ilia-murzinov](https://github.com/ilia-murzinov) | TRACK + PAGE opens SEQ: Euclidean rhythms, lock rhythms, and generated melodies and chords, for audio and MIDI tracks. |
| [**SLOW LFO**](slow-lfo/README.md) | [nathangroth](https://github.com/nathangroth) | LFO MULT gains 1/2X, 1/4X and 1/8X on audio and MIDI tracks: LFOs up to eight times slower. |
| [**STEM REC**](stems/README.md) | [yvesrosius](https://github.com/yvesrosius) | Multitrack recording to the card: each track (after its fader), MAIN, CUE and the inputs as separate WAV files, 16 or 24 bits, up to 60 minutes. UP + REC opens STEMS. |
| [**SYNTH MACHINE**](synth/README.md) | [timhastie](https://github.com/timhastie) | A FLEX track whose sample is named SYNTH* plays a two-operator FM voice (STRT/LEN/RTRG/RTIM = ratio/index/feedback/decay); the DSP shapes and effects it as a sample. Its PLAYBACK page reads RATO/INDX/FDBK/DEC with icons and the title FM SYNTH; PTCH is semitones (-64..+63) and RATE is FINE (cents) on a synth track, 0c the moment a track becomes one. A FLEX or STATIC sample track with LEG MONO and GLIDE slides its pitch (2.8). |
| [**TRACK TRIG MODE**](track-trig-mode/README.md) | [Hteah](https://github.com/Hteah) | Each audio track keeps its own CHROMATIC / SLOTS / SLICES trig mode, saved with the project. |
| [**TRACK PATTERNS**](trackpatterns/README.md) | [pgstath](https://github.com/pgstath) | Each track plays its own pattern of the playing bank; changes land at the track's loop end. |
| [**TRIG MUTE**](trig-mute/README.md) | [Hteah](https://github.com/Hteah) | GRID REC: hold a step + FUNC mutes or unmutes its trig (kept with the pattern; the LED blinks). |
| [**TUNER**](tuner/README.md) | [timhastie](https://github.com/timhastie) | UP + TEMPO: a tuner window for the current audio track -- note, octave, cents, needle, Hz (McLeod NSDF + YIN refine on the ColdFire, in the UI task). |
| [**VARISPEED**](varispeed/README.md) | [Zac Kyoti](https://github.com/Zac-Kyoti) | STATIC/FLEX TSTR VARI: dry, tempo-locked varispeed with QUAN ratios on PTCH (the plain build of VARISPEED_EMUS: nothing emulated, stock DSP). |
| [**WAVE CF**](wavecf/README.md) | [Sam Banks](https://github.com/sambanks) | WAVE: a 4-voice wavetable machine, a row of the track's machine list. PLAYBACK: TUNE FRAM CHRD VOIC SPRD GLID: FRAM morphs eight frames, CHRD one of 32 chords, VOIC 1-4 of its notes, SPRD opens the voicing. SETUP: VIBR VRAT OCT DETN COMP MODE (CHORD or POLY). Notes follow SCALE QUANTIZER's scale. No filter: the Octatrack's own FX and AMP follow. |

## Parts, Kits and scenes

| module | author | what it does |
|---|---|---|
| [**EVENTS**](events/README.md) | [radiohagen](https://github.com/radiohagen) | System: transport and MIDI notifications, held-step ownership and copy notifications. |
| [**KITS**](kits/README.md) | [Sam Banks](https://github.com/sambanks) | 255 Kits per project: PART = LOAD KIT, FUNC+PART = SAVE KIT (MKI: FUNC+MIDI, then FUNC+BANK); each pattern plays its Kit through the stock Part slots. |
| [**MIDI SCENES**](midi-scenes/README.md) | [bkkbrls-del](https://github.com/bkkbrls-del) | Scene locks for the MIDI tracks (hold-to-lock, readout, unlock, lock LEDs, XF morph, scene clear / copy / paste), kept per Part in scenes.work and CS1. Port of bkkbrls-del's midisc project. |
| [**MORPH**](morph/README.md) | [MaMarko](https://github.com/braikomarko-hub) | Hold a track key and press UP: the window; YES and from the next step that track's scene morph runs by itself, A -> B -> A over STEPS x x steps, starting on A; the other tracks keep the crossfader. Then the track key held ~1 s turns it on and off. Track + DOWN finishes the cycle on A and parks the track there until the crossfader reaches A. D, E, F: how it comes back (RET, CURV) and whether it loops, plays once or stays on B (END). Settings saved with the project. Inspired by the Korg Electribe's Motion Sequence. |
| [**SCENES P2**](scenes-p2/README.md) | [Sam Banks](https://github.com/sambanks) | Scene locks and the crossfader on FX1/FX2 page 2 (hold a scene, turn a page-2 knob). |
| [**STORE**](store/README.md) | [Sam Banks](https://github.com/sambanks) | Platform: the stock save, load, copy, CS1 and Part sites STORE clients share. |
| [**VERB PARTS**](verb-parts/README.md) | [Sam Banks](https://github.com/sambanks) | A Part saved with PLATE, SPRING or DARK REV opens on its VERBERATION row (VERB PLATE, ROOM, HALL) at that row's defaults. |
| [**XF CURVE**](xfcurve/README.md) | [Bryan T](https://github.com/bryantysinger) | The crossfader's curve, chosen in BRAIN: LINEAR (stock), four S-curves (S SOFT to S HARD), their inverses (INV SOFT to INV HARD), CUT, CUT A, CUT B, SLOW A or SLOW B. Applies to scene locks, XVOL and the playback morph alike. |

## MIDI and USB

| module | author | what it does |
|---|---|---|
| [**CC FEEDBACK**](cc-feedback/README.md) | [Sam Banks](https://github.com/sambanks) | Every knob value change is transmitted as its CC (page 1: 16-45; page 2: CC MAP's 102-111, 14, 15), so a controller's encoders follow the unit. |
| [**CC MAP**](cc-map/README.md) | [Sam Banks](https://github.com/sambanks) | MIDI CC 102-107 drive the FX2 engine's page-2 slots 6-11; CC 108-111, 14 and 15 the FX1 station's. |
| [**CHORDS FACTORY**](chords/README.md) | [djib](https://github.com/Djibdjib) | Chord progressions for a MIDI track: sixteen slots per bank on the trig keys, each chord built (root, type, inversion, spread, octave), typed on the trig keys (FUNC) or voiced from the slot before by voice leading (the smoothest first, then the next ones); a voice moved by hand (FUNC + A-D); the bass free or the root; the scale's chords from SCALES (FUNC + F). Heard on the track's channel while a trig key is held. Saved in chords.work (a STORE client). The page: SRC again on MIDI NOTE (a PAGES client). CHORDS is also a MIDI trig mode (FUNC + DOWN): the trig keys play the slots, green, through stock's CHROMATIC note (the arpeggiator follows); live recording or TRIG + UP (a chooser window) puts a chord on a trig. |
| [**FREE LOOP**](free-loop/README.md) | [djib](https://github.com/Djibdjib) | Loop pedals per track on its channel: CC 90 REC (a FREE track's first free loop sets the tempo, the pattern length and starts the sequencer; then arm / cut the overdub; held: clear a muted or stopped loop), CC 91 PLAY/STOP (play, mute / unmute, held: END), CC 92 UNDO / REDO, CC 93 END (mute / unmute at the loop's start). TRACK + UP: the track's ROLE, SIGN, BARS, BPM range and the pattern's ENTRY mode. CC 83-89 on PROG CH: PLAY/STOP, clear, pattern and bank steps. |
| [**MIDI FOLLOW**](midi-follow/README.md) | [radiohagen](https://github.com/radiohagen) | RFOL follows source notes; press D for FIXED/GRAV/SOURCE register, OCT/OFFS and TRIG/LIVE updates. |
| [**MIDI LOOPBACK**](midi-loopback/README.md) | [radiohagen](https://github.com/radiohagen) | Press CHAN for per-Part EXT/INT/BOTH routing of MIDI-track notes and controls. |
| [**MIDI SCALES**](midi-scales/README.md) | [radiohagen](https://github.com/radiohagen) | Stock MIDI ARP SETUP KEY: OFF plus all 12 keys in seven diatonic modes, stored in the Part. |
| [**SCALES**](scales/README.md) | [djib](https://github.com/Djibdjib) | One catalogue of 52 scales in 9 families for every module; ARP SETUP's KEY turns the tonic and, pressed, opens the scale chooser (the families, then their scales); the sequencer and the arpeggiator play the scale; the CHROMATIC trig keys light it (SCALE QUANTIZER's on audio tracks). |
| [**SCREEN**](screen/README.md) | [Sam Banks](https://github.com/sambanks) | Answers the Elektron screenshot SysEx request on MIDI OUT with the 128x64 screen, windows and popups included. |
| [**USB**](usb/README.md) | [markandrus](https://github.com/markandrus) | USB MIDI in and out, and USB audio to and from a computer, on the Octatrack's own USB port, with its channels set in BRAIN (built on markandrus/octemu; bryantysinger's input path and crossbar; allmyfriendsaresynths's post-fader stems). |

## Fixes

| module | author | what it does |
|---|---|---|
| [**ATA WRITE GUARD**](ata-write-guard/README.md) | [Sam Banks](https://github.com/sambanks) | Keeps the first PIO card sector and its pointer/count update atomic against interrupts; restores the caller's interrupt mask before returning. |
| [**BATCH_BUGFIXES**](batch-bugfixes/README.md) | [Zac Kyoti](https://github.com/Zac-Kyoti) | Three stock 1.40C bug fixes in one module: MIDI Plays-Free trig, empty-pattern LED, and Part-change carryover. |
| [**FRAME GUARD**](frame-guard/README.md) | [Sam Banks](https://github.com/sambanks) | A late frame interrupt waits out the window in which the DSP's frame exchange stalls at START and at a program change. |
| [**LOFI AMF FIX**](lofi-amf-fix/README.md) | [Bryan T](https://github.com/bryantysinger) | Fixes stock LO-FI's AMF knob. Ported from bryantysinger/octa-bt-pt. |
| [**REC CS1 SKIP**](rec-cs1-skip/README.md) | [Bryan T](https://github.com/bryantysinger) | The recorder's per-frame control-record update without its redundant CS1 writes: less ColdFire time per recording track. |
| [**RECORDER LOOP FIX**](recorder-loop-fix/README.md) | [Sam Banks](https://github.com/sambanks) | Fixes the recorder's loop click: a re-bound sample keeps its place, a take is exactly the arm spacing, and sound-on-sound no longer plays a zero at the seam. |

## Settings

| module | author | what it does |
|---|---|---|
| [**BRAIN**](brain/README.md) | [Sam Banks](https://github.com/sambanks) | The settings store: card-wide settings and knob defaults kept on the card and read at each project load, behind the PROJ → BRAIN menu. |
| [**HOOKS**](hooks/README.md) | [Sam Banks](https://github.com/sambanks) | Platform: owns a stock site two selected modules both claim, and calls each one's routine there. |
| [**MEMORY**](memory/README.md) | [Sam Banks](https://github.com/sambanks) | Platform: the DRAM reserve in stock's audio page arena, sized from what the remix's modules claim. |
| [**PAGES**](pages/README.md) | [djib](https://github.com/Djibdjib) | System: the extra pages a page key cycles through (SRC again on MIDI NOTE: CHORDS FACTORY ...). |
| [**PERSISTENT BUFFERS**](persistent-buffers/README.md) | [ilia-murzinov](https://github.com/ilia-murzinov) | On project save, dump non-empty recorder buffers to BUFFERS/REC1.wav..REC8.wav (overwrite); on project load, restore them. |

## Utilities

| module | author | what it does |
|---|---|---|
| [**BUFFER SAVER**](buffer-saver/README.md) | [Chupitnik](https://github.com/Chupitnik) | SAVE PROJECT (and SAVE TO NEW) offers to save unsaved recorder takes, each back into its own buffer, so they reload with the project. |
| [**LAZY CHOP TEMPO**](chop-tempo/README.md) | [8thmyth](https://github.com/8thmyth) | After LAZY CHOP's YES and its slice-count popup, a popup with the tempo the chops point to (BPM 115 (58)) until the next key. |
| [**COPY PROJECT**](copy-project/README.md) | [ilia-murzinov](https://github.com/ilia-murzinov) | CHANGE project list > FUNC+BANK > COPY: duplicate the selected project folder on the card. |
| [**LAZY CHOP**](lazy-chop/README.md) | [8thmyth](https://github.com/8thmyth) | Slice a sample by tapping TRIG 1..16 (four pages, 64 slices) while it plays, from the audio editor's slice menu. |
| [**LOCK EDIT**](lock-edit/README.md) | [8thmyth](https://github.com/8thmyth) | [TRIG]+[BANK] in grid recording opens the audio editor on the step's sample, its slice selected and in view. |
| [**REMIX SWITCH**](remix-switch/README.md) | [sanderlegit](https://github.com/sanderlegit) | MAIN MENU > BRAIN lists the raw OS images (.RMX) in /BRAIN/REMIXES/ and boots the one picked without writing the flash; remembers the choice across reboots. |
| [**RND NAME**](rnd-name/README.md) | [ilia-murzinov](https://github.com/ilia-murzinov) | FUNC + CUE in a project-name editor fills in the date and a random name. |
| [**SCOPE**](scope/README.md) | [ilia-murzinov](https://github.com/ilia-murzinov) | Full-screen scope of the track's audio (DOWN + TEMPO): waveform, XY or both, with gain and time on A and B. |
| [**SRC3 KEY**](src3-key/README.md) | [8thmyth](https://github.com/8thmyth) | [MIDI] in the audio editor starts / stops a SRC3 recording on the track's recorder (MKI has no [REC3]). |
| [**ZOOM KEEP**](zoom-keep/README.md) | [8thmyth](https://github.com/8thmyth) | The audio editor keeps its zoom when a slice is auditioned (SLICES trig mode; the slice start scrolls into view), and every page (TRIM, SLICE, EDIT) keeps its own zoom and place in time across tracks. |

## Reference

| module | author | what it does |
|---|---|---|
| [**BOOT TRACE**](boot-trace/) | [sanderlegit](https://github.com/sanderlegit) | Probe: a MIDI note on MIDI OUT at each boot stage, the DSP upload's record echoes and any stall, for finding where a boot hangs. |
| [**CF METER**](cfmeter/README.md) | [Sam Banks](https://github.com/sambanks) | Probe: frame-interrupt duration and (with CF METER IDLE) idle time, plus core 0's frame spin count, ESAI underrun/overrun frames and frame period, printed as audio on T8's FX2. |
| [**CF METER IDLE**](cfmeter-idle/README.md) | [Sam Banks](https://github.com/sambanks) | Probe: main's idle loop timed, for CF METER's idle-time slot. |
| [**DLCOPY**](dlcopy/README.md) | [Sam Banks](https://github.com/sambanks) | Frame hook on payload B: copies a staged block into the shared window (demand loader). |
| [**DLPUMP**](dlpump/README.md) | [Sam Banks](https://github.com/sambanks) | Host-writes a staged block to a DSP core, a chunk per frame interrupt (demand loader). |
| [**DRUMMER PROBE**](drummer-probe/) | [djib](https://github.com/Djibdjib) | DRUMMER phase 2 probe: trigs added and moved after the step builder, the FLEX start's slice forced (measurement only). |
| [**KEYBUS**](keybus/README.md) | [Sam Banks](https://github.com/sambanks) | Every track's key level (block peak of \|mono\|) each block, in eight shared words for DSP readers on either core. |
| [**LOAD METER**](load-meter/README.md) | [Sam Banks](https://github.com/sambanks) | The frame interrupt's share of the ColdFire, each DSP core's busy time per frame and each effect call's cost, for BRAIN's OTOP screen. |
| [**REMOTE**](remote/README.md) | [Sam Banks](https://github.com/sambanks) | Project loads, saves, transport, pattern changes and screen redraws as timestamped records a host reads over USB. |
| [**SC KEYBUS BRIDGE**](sc-keybus-bridge/README.md) | [Sam Banks](https://github.com/sambanks) | Shares the dispatcher's per-track site between SIDECHAIN_COMPRESSOR's sctap and KEYBUS's tap. |
| [**SC LOAD METER BRIDGE**](sc-loadmeter-bridge/README.md) | [Sam Banks](https://github.com/sambanks) | Shares the FX2 commit site between SIDECHAIN_COMPRESSOR's moncommit and LOAD METER's otop_e2. |
| [**WAVE LOAD**](waveload/README.md) | [Sam Banks](https://github.com/sambanks) | Probe: K 4-voice wave engines per frame interrupt (CF METER's BURN), for CF METER's duration readout. |
