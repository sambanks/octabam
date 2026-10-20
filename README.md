# octabam

[![CI](https://github.com/sambanks/octabam/actions/workflows/ci.yml/badge.svg)](https://github.com/sambanks/octabam/actions/workflows/ci.yml)

An unofficial community remixer for the Elektron Octatrack's operating
system, not affiliated with Elektron: pick the modifications you want and
build them into one firmware image from your own copy of OS 1.40C.

A modification is a **module** (`modules/<name>/`). A named selection of
modules is a **remix** (`remixes/<name>/`). `make image REMIX=<name>`
composes a remix into a card-flashable image: it places the code, wires
the hooks by symbol, refuses collisions by name, and proves every ported
module against its author's own build byte for byte. No firmware is
distributed here; every image is derived from the user's own 1.40C on the
user's machine, and a built image must never be shared.

Every module is contributed by its author and credited in the table below.
Pull requests are accepted: a module, a port of an existing mod, a fix, a
doc correction. [GitHub Issues](https://github.com/sambanks/octabam/issues)
take bug reports, module proposals and hardware test reports; each has a
form (`.github/ISSUE_TEMPLATE/`) asking for the remix, image build,
hardware model and steps to reproduce.
The licence is MIT.

## Start here

| you want to | read |
|---|---|
| put a remix on your Octatrack | [docs/guide/BUILDING.md](docs/guide/BUILDING.md): a fresh machine to a flashed unit, step by step, with the recovery path |
| see what remixes exist and what is in each | [remixes/README.md](remixes/README.md), then the remix's own page in `remixes/<name>/README.md` |
| see every module and how far it is proven | the table below; each module's `modules/<name>/README.md` has the measurements |
| compose your own selection | [docs/guide/REMIXER.md](docs/guide/REMIXER.md): `make remix`, the interactive remixer, or a `remix.py` by hand |
| write a module or port an existing mod | [CONTRIBUTING.md](CONTRIBUTING.md) (the contract), [docs/contributing/MODULES.md](docs/contributing/MODULES.md) (the guide), [docs/contributing/TESTING.md](docs/contributing/TESTING.md) (what the gates prove) |
| understand the firmware | [docs/firmware/ARCHITECTURE.md](docs/firmware/ARCHITECTURE.md) and its neighbours; [docs/contributing/TOOLING.md](docs/contributing/TOOLING.md) for the tools |
| find any other doc | [docs/README.md](docs/README.md) |

## Quick start

[docs/guide/BUILDING.md](docs/guide/BUILDING.md) has every step. Section 0 is what
to install first: on macOS the Xcode Command Line Tools
(`xcode-select --install`) and Homebrew, then `make setup-mac`; on Linux
or WSL2 `make setup-linux`. Then `make emu-setup`,
`make os && make recon`, `make image REMIX=<name> BUILD=1`, and the flash
from the card (section 5).

<!-- modules:begin -->

### Effects: the bus

| module | author | what it does | proof |
|---|---|---|---|
| [**DELAY SERVER**](modules/busdelay/README.md) | [sambanks](https://github.com/sambanks) | Multi-mode delay: CLEAN / pitched GRAIN cloud / REVERSE, tape wow. | on hardware: Sam's MKII |
| [**REVERB SERVER**](modules/busverb/README.md) | [sambanks](https://github.com/sambanks) | Eight-line FDN reverb: ROOM/PLATE/BIG, shimmer, gate, mid/side width. | on hardware: Sam's MKII |
| [**FX2 LOCK**](modules/fx2-lock/README.md) | [sambanks](https://github.com/sambanks) | The FX2 chooser cannot change a track's effect: YES's key-table entry points at NO's close handler, so the select handler never runs. | on hardware: cursory testing on Sam's MKII (owner report, 16 Oct 2026); verify_fx2_lock under the port, 4 Oct 2026 |
| [**MODE DEFAULTS**](modules/mode-defaults/README.md) | [sambanks](https://github.com/sambanks) | A MODE turned on the panel re-defaults the knobs around it (the manifests' ModeViews), on FX1 and FX2. | on hardware: Sam's MKII (images 26/27, 15 Sep 2026) |
| [**RIG HOSTS**](modules/rig-hosts/README.md) | [sambanks](https://github.com/sambanks) | A new part is born hosted: T1 FX2 = BusDelay, T5 = BusVerb, T8 = the stock DELAY, the rest SEND. | on hardware: cursory testing on Sam's MKII (owner report, 16 Oct 2026); a new project born hosted under the port |
| [**SEND**](modules/send/README.md) | [sambanks](https://github.com/sambanks) | Bus client: DEL into the delay, REV into the reverb, from any track. The default effect. | on hardware: Sam's MKII |
| [**TEMPO BUS**](modules/tempo-bus/README.md) | [sambanks](https://github.com/sambanks) | The TEMPO window lists and edits BusDelay's and BusVerb's knobs (UP/DOWN = row, A or B = value, LEFT/RIGHT = engine, FUNC + LEVEL = 0.1 BPM). | on hardware: cursory testing on Sam's MKII (owner report, 16 Oct 2026); `verify_set`; carried by image 88 on Sam's MKII |
| [**TEMPO SYNC**](modules/tempo-sync/README.md) | [sambanks](https://github.com/sambanks) | ColdFire DRAM units: publishes the held MIDI note to BusDelay, and draws BusDelay TIME as a tempo division. | on hardware: Sam's MKII |

### Effects: on a track

| module | author | what it does | proof |
|---|---|---|---|
| [**BBD**](modules/bbd/README.md) | [JamCones](https://github.com/JamCones) | Clocked BBD delay: compander, clock/3 filters, bucket noise, freeze, governor; FX2. | on hardware: JamCones' MKII, BBDOB4 (remixes/test/bbd, BUILD 4), 17 Oct 2026 |
| [**CHARACTER**](modules/character/README.md) | [sambanks](https://github.com/sambanks) | FX1 station: fold, saturation, tilt, compressor, width. | on hardware: Sam's MKII |
| [**CHARACTER TXTR**](modules/character-txtr/README.md) | [sambanks](https://github.com/sambanks) | Character plus TXTR (Airwindows Pockey2): fold, texture, saturation, tilt, compressor, width. | on hardware: cursory testing on Sam's MKII (owner report, 16 Oct 2026) |
| [**EUCLID**](modules/euclid/README.md) | [repeat98](https://github.com/repeat98) | Euclidean LP/BP/HP/notch/amp sequencer: swing, envelope, gate, random and loop. | on hardware: cursory testing on Sam's MKII (owner report, 16 Oct 2026); its own render gates |
| [**GATE VERB**](modules/gateverb/README.md) | [Emilie Gillet (Mutable Instruments), ported here](https://github.com/pichenettes/eurorack) | A gated plate reverb (Griesinger topology, after the reverb stage of Mutable Instruments Clouds): amount, input gain, time, diffusion, tone, gate. One FX2 slot per instance. | on hardware: cursory testing on Sam's MKII (owner report, 16 Oct 2026); `verify_gateverb` (dsp_host, against a float model of Clouds' reverb) |
| [**LOFI2**](modules/lofi2/README.md) | [Bryan T](https://github.com/bryantysinger) | Ring mod or frequency shifter, then sample-rate and bit reduction. | on hardware: Bryan T's MKII, images 96-99 (Oct 2026, this tree): tracks 1 and 5, five instances at once; `_bt_oct` build 11 (12 Oct 2026, the 414-cycle loop): eight in SHIFT at once, four per core, UP/DOWN switched while playing |
| [**MINIVERB**](modules/miniverb/README.md) | [repeat98](https://github.com/repeat98) | Modulated diffused FDN reverb; independent FX2 buffers, smoothed controls. | on hardware: cursory testing on Sam's MKII (owner report, 16 Oct 2026); `make verify-miniverb` |
| [**MODULATION**](modules/modulation/README.md) | [sambanks](https://github.com/sambanks) | FX1 station: a modulation pedal -- Juno, Dimension, flanger, phaser, comb; FX1 only. | on hardware: Sam's MKII |
| [**SIDECHAIN_COMPRESSOR**](modules/sidechain-compressor/README.md) | [Zac Kyoti](https://github.com/Zac-Kyoti) | Stock COMPRESSOR with a side-chain KEY from any of T1-T8, a key filter, key gain and a key listen switch on page 2. | on hardware: the author's MKI, 4 Oct 2026, an octabam image with all six KYOTI modules and REC_TRIG_MUTE: ducking on one core and across cores both ways, KFLT/KGN/MON, a muted KEY in every MUTE MODE |
| [**SPECTRUM**](modules/spectrum/README.md) | [sambanks](https://github.com/sambanks) | FX1 station: a filter pedal -- the Moog ladder, SEM (LP -> BP -> HP by SHPE), Airwindows Capacitor2, formants; ENV and LFO onto the cutoff; width. | on hardware: Sam's MKII |
| [**TAPE ECHO**](modules/tapeecho/README.md) | [repeat98](https://github.com/repeat98) | Economy CPU tape echo: two biquads, simple FREE slew, snapped BEAT TIME and page-1 AGE. | on hardware: the author's unit (OCTACLID4): six instances run, a seventh freezes it, open |
| [**TESTGEN**](modules/testgen/README.md) | [Ignorato](https://github.com/Ignorato) | Measurement source: a sine, sweep, pink or white noise, impulses, a needle pulse train or DC replace the track's audio. | on hardware: Ignorato's MKII, images OCTABAM4-6 and 10 (remix testgen), 3-4 Oct 2026; 0.1 measured at the main outs; FX1-only in the emulator so far |
| [**TRANSIENT**](modules/transient/README.md) | [Ignorato](https://github.com/Ignorato) | Transient shaper: ATCK and SUST reshape onsets and tails, level-independent. | on hardware: Ignorato's MKII, images OCTABAM2 and OCTABAM3 (remix transient), 3 Oct 2026 |
| [**VOCODER**](modules/vocoder/README.md) | [Ignorato](https://github.com/Ignorato) | Ten-band vocoder after the Roland VP-330: the track's voice, a built-in carrier at NOTE or input B. FX2 of tracks 2, 4, 6 and 8 only. | local render: 0.2 at T2 T4 T6 T8 in dsp_host and under the ColdFire port (verify_vocoder, make check), 11 Oct 2026; SCAL, KEY and RANG in dsp_host and under the port, 18 Oct 2026 (value 0 bit for bit the build before them); not flashed, T4 and T8 not heard, the selectors not heard. The 0.2 code before the de-zipper was heard on Ignorato's MKII at T2 T3 (OCTABAM20, 5 Oct 2026, by ear); 0.1 ran on OCTABAM12 |
| [**WAVE**](modules/wave/README.md) | [sambanks](https://github.com/sambanks) | Experiment: a 4-voice wavetable synth on FX2; a sine on the track sets its pitch and level. | on hardware: Sam's MKII, image 93, 3 Oct 2026: plays, PTCH and the CHROMATIC keys move the pitch |

### Machines and the sequencer

| module | author | what it does | proof |
|---|---|---|---|
| [**ANALOG BD**](modules/analog-bassdrum/README.md) | [repeat98](https://github.com/repeat98) | Analog BD track machine: switchable 808/909 circuit-informed synthesis. | on hardware: cursory testing on Sam's MKII (owner report, 16 Oct 2026); source/AMP/main on both cores and engine-browser/hidden-control gates |
| [**BLACKPYRAMIDS_303**](modules/blackpyramids-303/README.md) | [Zac Kyoti](https://github.com/Zac-Kyoti) | BLKPYRAMD: a TB-303 voice (Open303) as a track machine, one per DSP core, played by the sequencer, the chromatic keys and MIDI. | on hardware: the author's MKI: standalone images 14-16 Oct 2026, this octabam form 19 Oct 2026 |
| [**DIRECT JUMP**](modules/direct-jump/README.md) | [timhastie/octatrick-modules](https://github.com/timhastie/octatrick-modules) | CHAIN AFTER: DIRECT (its unused value 1) -- a pattern change lands at the next step, the step count continuing (A4/Rytm direct jump). | on hardware: `octatrick-usb` on his MKI, 26 Sep 2026 (OCTATRICK9) through 2.9; the last two 2.9 fixes under the port |
| [**DIRECT_JUMP_KYOTI**](modules/direct-jump-kyoti/README.md) | [Zac Kyoti](https://github.com/Zac-Kyoti) | Clock-locked DIRECT JUMP ([PTN]+[YES]): a cued pattern lands on the next step exactly where it would be had it played since START. | on hardware: the author's MKI, 27-28 Sep 2026 (standalone 140C_KDJ7 and the KYOTI V1.0 combined image) and 1 Oct 2026 from DRAM (an octabam image with all six KYOTI modules); Program Change re-cues, MIDI tracks, START SILENT and the trig-condition reset emulator-verified |
| [**ERASE_EMPTY_TRIGLESS_LOCKS**](modules/erase-empty-trigless-locks/README.md) | [Zac Kyoti](https://github.com/Zac-Kyoti) | Bug fix: a trigless lock whose last parameter lock is erased stops staying lit on the trig row. | on hardware: the author's MKI (standalone image) |
| [**EUCLID FILL**](modules/euclid-fill/README.md) | [ilia-murzinov](https://github.com/ilia-murzinov) | TRACK + PAGE: Euclidean sample-trig fill (STEPS=pattern len / PULSE / ROT / RAND VEL / RAND PTCH; CUE = random k-subset; RAND VEL = VOL locks; RAND PTCH = in-scale range around Part PLAYBACK PTCH). | on hardware: YES/CUE with RAND PTCH>0 on sample + FM (SY encoding path in source, not tried on an SY track), SCALE on/off, relative RAND VEL — author BUILD 34 / minimal on CF, MKII, 16 Oct 2026; also cursory on Sam's MKII (owner report, 16 Oct 2026); builds and boots under the port; fill math gated in verify_euclid_fill |
| [**MUTE_MODES**](modules/mute-modes/README.md) | [Zac Kyoti](https://github.com/Zac-Kyoti) | PERSONALIZE -> MUTE MODE: OT (stock) / OTFX / OTFX-T / DT-T -- dry cut with FX tails, trig suppression, or a Digitakt-style sequencer mute. | on hardware: the author's MKI (standalone image and the KYOTI V1.0 combined image) |
| [**PLOCKS P2**](modules/plocks-p2/README.md) | [sambanks](https://github.com/sambanks) | Parameter locks on FX1/FX2 page 2 (hold trigs, turn a knob on the SETUP page). | on hardware: cursory testing on Sam's MKII (owner report, 16 Oct 2026) |
| [**QUANTIZE_LIVE_REC_TOGGLE**](modules/quantize-live-rec-toggle/README.md) | [Zac Kyoti](https://github.com/Zac-Kyoti) | QUANTIZE LIVE REC from the front panel: hold [REC], tap [PLAY] to see it, tap again while the toast is up to invert it. | on hardware: the author's MKI, 25 Sep 2026 (gesture) and 30 Sep 2026 (setting survives a power cycle) |
| [**SCALE QUANTIZER**](modules/quantizer/README.md) | [timhastie/octatrick-modules](https://github.com/timhastie/octatrick-modules) | PROJECT > CONTROL > SEQUENCER > SCALE: the PTCH knob and CHROMATIC trig keys quantize to a scale (24 scales, OFF = stock); > ROOT: the note the scale is built on (C..B; key 1 of the CHROMATIC keyboard sounds it); > GLIDE: the synth's glide time (OFF, 1..127; the legato switch is the synth track's LEG setting); polyphonic chromatic keys on a synth track whose VOIC is 2..4; on a synth track PTCH is semitones (-64..+63) and the CHROMATIC octave runs -4..+4. | on hardware: `octatrick-usb` on his MKI, 26 Sep 2026 (OCTATRICK9) through 2.9; the last two 2.9 fixes under the port |
| [**REC THRESHOLD**](modules/rec-threshold/README.md) | [Chupitnik](https://github.com/Chupitnik) | Recorder TRIG value THR: a REC press arms, and recording starts when the input passes the track's LEV (RECORDING SETUP 2, beside a live IN meter). | on hardware: Chupitnik's MKII, 11-13 Oct 2026, THR1 to THR9 from the card: armed with TRACK 1 + REC AB, silence never records, the input starts the take, a second press cancels, LEV and IN on RECORDING SETUP 2, TRIG moved off THR while armed drops the arm and the blink, an armed track's icon blinks, armed inside RECORDING SETUP 1 it records; THR9 is this code |
| [**REC_TRIG_MUTE**](modules/rec-trig-mute/README.md) | [Zac Kyoti](https://github.com/Zac-Kyoti) | [TRACK]+[NO]/[YES] mute/unmute the held tracks' recorder trigs; MIDI CC 80; '..' beside a muted track's status icon. | on hardware: the author's MKI, 2-3 Oct 2026 (standalone image and KYOTI V1.0; MIDI CC 80 not tried) |
| [**RELOAD_FROM_PROJECT**](modules/reload-from-project/README.md) | [Zac Kyoti](https://github.com/Zac-Kyoti) | Reload one track's sequence from the card without stopping the transport: [PTN]+[TRACK n], or [BANK]+[TRACK n] to re-apply the Part. | on hardware: the author's MKI (standalone image), sequencer and metronome phase kept; 1 Oct 2026 from DRAM in an octabam image with all six KYOTI modules |
| [**RLEN PLEN**](modules/rlen-plen/README.md) | [sambanks](https://github.com/sambanks) | ColdFire cave: RLEN value PLEN (past MAX) = one loop of the track's pattern on its own scale, so TRIG ONE + QREC PLEN records the next pass and stops. | on hardware: cursory testing on Sam's MKII (owner report, 16 Oct 2026); 26 Sep 2026 |
| [**STEM REC**](modules/stems/README.md) | [yvesrosius](https://github.com/yvesrosius) | Multitrack recording to the card: each track (after its fader), MAIN, CUE and the inputs as separate WAV files, 16 or 24 bits, up to 60 minutes. UP + REC opens STEMS. | on hardware: Yves's MKII: STEMS1 (30 Sep 2026), T1-T8 for about two minutes; STEMS3 (6 Oct 2026), T1-T8 after the fader, MAIN and AB at 16 and 24 bits |
| [**SYNTH MACHINE**](modules/synth/README.md) | [timhastie/octatrick-modules](https://github.com/timhastie/octatrick-modules) | A FLEX track whose sample is named SYNTH* plays a two-operator FM voice (STRT/LEN/RTRG/RTIM = ratio/index/feedback/decay); the DSP shapes and effects it as a sample. Its PLAYBACK page reads RATO/INDX/FDBK/DEC with icons and the title FM SYNTH; PTCH is semitones (-64..+63) and RATE is FINE (cents) on a synth track, 0c the moment a track becomes one. A FLEX or STATIC sample track with LEG MONO and GLIDE slides its pitch (2.8). | on hardware: `octatrick-usb` on his MKI, 26 Sep 2026 (OCTATRICK9) through 2.9; the last two 2.9 fixes under the port |
| [**TUNER**](modules/tuner/README.md) | [timhastie/octatrick-modules](https://github.com/timhastie/octatrick-modules) | UP + TEMPO: a tuner window for the current audio track -- note, octave, cents, needle, Hz (McLeod NSDF + YIN refine on the ColdFire, in the UI task). | on hardware: Tim's MKI, test build 3.0 b40 (`octatrick` at BUILD 40), 29 Sep 2026: UP + TEMPO opens the window and tunes; sources unchanged since 26 Sep |
| [**VARISPEED**](modules/varispeed/README.md) | [Zac Kyoti](https://github.com/Zac-Kyoti) | STATIC/FLEX TSTR VARI: dry, tempo-locked varispeed with QUAN ratios on PTCH (the plain build of VARISPEED_EMUS: nothing emulated, stock DSP). | on hardware: the author's MKI, 15 Oct 2026 (the VARI1 build, standalone image) |

### Parts, Kits and scenes

| module | author | what it does | proof |
|---|---|---|---|
| [**KITS**](modules/kits/README.md) | [sambanks](https://github.com/sambanks) | 255 Kits per project: PART = LOAD KIT, FUNC+PART = SAVE KIT (MKI: FUNC+MIDI, then FUNC+BANK); each pattern plays its Kit through the stock Part slots. Replaces the earlier Octakit implementation. | on hardware: Sam's MKII (image A6, 6 Oct 2026): importing Octakit-format kit files, ems-octakit #5, STOP/PTN+TRIG/PLAY with the Rytm, a rejected bank file, power cycles; `verify_kits` under the port |
| [**MIDI PART STATE**](modules/midi-part-state/README.md) | [radiohagen](https://github.com/radiohagen/octatrack-modules) | Shared native Part settings and coherent copy/clear publication; no KITS dependency. | on hardware |
| [**MIDI SCENES**](modules/midi-scenes/README.md) | [bkkbrls-del/midisc](https://github.com/bkkbrls-del/midisc) | Scene locks for the MIDI tracks (hold-to-lock, readout, unlock, lock LEDs, XF morph, scene clear / copy / paste), kept per Part in scenes.work and CS1. Port of bkkbrls-del's midisc project. | on hardware: cursory testing on Sam's MKII (owner report, 16 Oct 2026); `verify_scenes` against MIDISC2.1 under the port, phase 1 scenarios (b1, b7, b3, b29copy, b29clear); MIDISC 2.0 ran on the author's unit as `ok-ms` (14 Sep 2026) |
| [**SCENES P2**](modules/scenes-p2/README.md) | [sambanks](https://github.com/sambanks) | Scene locks and the crossfader on FX1/FX2 page 2 (hold a scene, turn a page-2 knob). | on hardware: cursory testing on Sam's MKII (owner report, 16 Oct 2026); 26 Sep 2026 |
| [**STORE**](modules/store/README.md) | [sambanks](https://github.com/sambanks) | Platform: the stock save, load, copy, CS1 and Part sites STORE clients share. | on hardware: cursory testing on Sam's MKII (owner report, 16 Oct 2026) |

### MIDI and USB

| module | author | what it does | proof |
|---|---|---|---|
| [**CC FEEDBACK**](modules/cc-feedback/README.md) | [sambanks](https://github.com/sambanks) | Every knob value change is transmitted as its CC (page 1: 16-45; page 2: CC MAP's 62-73), so a controller's encoders follow the unit. | on hardware: cursory testing on Sam's MKII (owner report, 16 Oct 2026); `verify_ccfeedback` (Unicorn) and `verify_set` (the port's MIDI OUT bytes) |
| [**CC MAP**](modules/cc-map/README.md) | [sambanks](https://github.com/sambanks) | MIDI CC 62-67 drive the FX2 engine's page-2 slots 6-11; CC 68-73 the FX1 station's. | on hardware: Sam's MKII (image 96, 13 Sep 2026) |
| [**MIDI FOLLOW**](modules/midi-follow/README.md) | [radiohagen](https://github.com/radiohagen/octatrack-modules) | RFOL follows source notes; press D for FIXED/GRAV/SOURCE register, OCT/OFFS and TRIG/LIVE updates. | port-gated |
| [**MIDI LOOPBACK**](modules/midi-loopback/README.md) | [radiohagen](https://github.com/radiohagen/octatrack-modules) | Press CHAN for per-Part EXT/INT/BOTH routing of MIDI-track notes and controls. | on hardware |
| [**MIDI SCALES**](modules/midi-scales/README.md) | [radiohagen](https://github.com/radiohagen/octatrack-modules) | Stock MIDI ARP SETUP KEY: OFF plus all 12 keys in seven diatonic modes, stored in the Part. | port-gated |
| [**USB**](modules/usb/README.md) | [markandrus/octemu](https://github.com/markandrus/octemu) | Class-compliant USB-MIDI in/out plus UAC2 audio to and from the host on the OT's own USB port (markandrus/octemu; the input path and crossbar bryantysinger's; the TRACKS POST stems allmyfriendsaresynths's), by its TRACKS / MAIN / CUE / MASTER / IN / MIDI checkboxes. | on hardware: Sam's MKII, octabam-core OCTABAMB5 (main 11d9f129), macOS on an arm64 Mac, 19 Oct 2026, with TRACKS PRE, MAIN, CUE and MIDI at their defaults (20 channels): enumeration (the MIDI port and a 20-channel input); MIDI in (notes trig tracks 3, 4, 5 and 8 on their own channels, and again after a replug); MIDI out clock at 48-49 per second, back after each of three cable replugs; audio after a replug with 0 overruns and 0 underruns; DISK MODE in and out (the image read back off the card, `cmp` equal, then MIDI, audio and counters clean); not run on a unit that day: TRACKS OFF and POST, MASTER, MAIN or CUE off, MIDI off, IN (octabam-core fixes it OFF), a Windows host, an MKI; earlier: cursory testing on Sam's MKII (owner report, 16 Oct 2026); `verify_usb` for every combination and `verify_usb_in` for every IN value under the port; on units: MIDI in/out on Sam's MKII (image 64, 25 Sep 2026), Tim's MKI (OCTATRICK9, 26 Sep 2026) and Ignorato's MKII (OCTABAM21, 9 Oct 2026, transmit after three replugs, macOS and Windows 10), USB clock tempo on Kazeko's MKI (#633, 6 Oct 2026); TRACKS MAIN CUE on Sam's MKII and Tim's MKI, MAIN CUE and the ABCD inject on Bryan T's MKII (build 16, 27 Sep 2026), TRACKS POST on allmyfriendsaresynths's MKII (P3, 5 Oct 2026); the crossbar values at stream-up on Bryan T's MKII (usbin-test 12-16, 26-27 Sep 2026); README.md per combination and direction |

### Fixes

| module | author | what it does | proof |
|---|---|---|---|
| [**ATA WRITE GUARD**](modules/ata-write-guard/README.md) | [sambanks](https://github.com/sambanks) | Keeps the first PIO card sector and its pointer/count update atomic against interrupts; restores the caller's interrupt mask before returning. | on hardware: cursory testing on Sam's MKII (owner report, 16 Oct 2026); forced completion interrupt and full DSP-enabled project load under the port, 15 Oct 2026; not on hardware |
| [**BATCH_BUGFIXES**](modules/batch-bugfixes/README.md) | [Zac Kyoti](https://github.com/Zac-Kyoti) | Three stock 1.40C bug fixes in one module: MIDI Plays-Free trig, empty-pattern LED, and Part-change carryover. | on hardware: the author's MKI (bugs 1 and 3, and bug 2's [BANK]-held stall ended); bug 2's [PTN] answers emulator-verified identical to its earlier hardware-confirmed version |
| [**LOFI AMF FIX**](modules/lofi-amf-fix/README.md) | [bryantysinger/octa-bt-pt](https://github.com/bryantysinger/octa-bt-pt) | Fixes stock LO-FI's AMF knob: mpysu -> mpyuu, both payloads. Ported from bryantysinger/octa-bt-pt. | on hardware: cursory testing on Sam's MKII (owner report, 16 Oct 2026); both words disassembled against stock |
| [**RECORDER LOOP FIX**](modules/recorder-loop-fix/README.md) | [sambanks](https://github.com/sambanks) | ColdFire caves: the recorder loop click -- seek on a same-sample FLEX re-bind, keep its counter, record exactly the arm spacing, and repeat the last sample where sound-on-sound would play a zero. | on hardware: OCTABAM83, 12 Sep 2026 (self-loop); Bryan T's MKII, sos-capture BUILD=95, 3 Oct 2026 (sound-on-sound) |

### Settings

| module | author | what it does | proof |
|---|---|---|---|
| [**BRAIN**](modules/brain/README.md) | [Sam Banks](https://github.com/sambanks) | The settings store on the unit: card-wide knob defaults read from BRAIN/card.work at each project load (docs/proposals/BRAIN.md). | on hardware: cursory testing on Sam's MKII (owner report, 16 Oct 2026); `verify_brain` under the port (6 Oct 2026) |
| [**MEMORY**](modules/memory/README.md) | [Sam Banks](https://github.com/sambanks) | Platform: the DRAM reserve in stock's audio page arena, sized from what the remix's modules claim. | on hardware: cursory testing on Sam's MKII (owner report, 16 Oct 2026); the reserve's size per remix in the build report; `verify_dram_boot` under the port |
| [**PERSISTENT BUFFERS**](modules/persistent-buffers/README.md) | [ilia-murzinov](https://github.com/ilia-murzinov) | On project save, dump non-empty recorder buffers to BUFFERS/REC1.wav..REC8.wav (overwrite); on project load, restore them. | `make check`: verify_persistent_buffers: symbols + port save/load; author MKII R2–R6 (17 Oct 2026): head is R6, path BUFFERS/RECn.wav (no !) |

### Utilities

| module | author | what it does | proof |
|---|---|---|---|
| [**BUFFER SAVER**](modules/buffer-saver/README.md) | [Chupitnik](https://github.com/Chupitnik) | SAVE PROJECT offers to save unsaved recorder takes, each back into its own buffer, so they reload with the project. | on hardware: Chupitnik's MKII, 15-16 Oct 2026, AUTOSAVE1 and AUTOSAVE2 from the card (the module under its first name): after a take FUNC + PROJ and PROJECT > SAVE ask SAVE SAMPLES?; YES saves R<n>-YYMMDD-HHMM and assigns it to its buffer, two buffers in one save, an immediate re-save does not ask, a reload brings the takes back, NO saves as stock |
| [**COPY PROJECT**](modules/copy-project/README.md) | [iliamurzinov](https://github.com/ilia-murzinov) | PROJECT > COPY PROJECT: duplicate a project folder on the card without loading it. | on hardware: flashed with CF card update and tested on author's MKII (17 Oct 2026); BUILD not recorded |
| [**REMIX SWITCH**](modules/remix-switch/README.md) | [sanderlegit](https://github.com/sanderlegit) | MAIN MENU > BRAIN lists the raw OS images (.RMX) in /BRAIN/REMIXES/ and boots the one picked without writing the flash; remembers the choice across reboots. | on hardware: an MKII, 29 Sep 2026 (OCTABAM14 with BOOT TRACE): switched to its own image and to stock 1.40C, audio and play working; and with the park moved into the dead vector run (BSRETVEC) booted, played and switched away again -- 40 region words down to 18; `verify_remix_switch`. The list in BRAIN's pane and /BRAIN/REMIXES/ (8 Oct 2026), and the persisted selection (#743): under the port only |
| [**RND NAME**](modules/rnd-name/README.md) | [iliamurzinov](https://github.com/ilia-murzinov) | Project name editors: FUNC+CUE fills YYMMDD + random pool name. | on hardware: cursory testing on Sam's MKII (owner report, 16 Oct 2026); FUNC+CUE on CREATE / SAVE PROJECT AS / CHOOSE NEW PROJECT NAME under the port (verify_rnd_name); pools from unit |

### Reference

| module | author | what it does | proof |
|---|---|---|---|
| [**BOOT TRACE**](modules/boot-trace/) | [sanderlegit](https://github.com/sanderlegit) | Probe: a MIDI note on MIDI OUT at each boot stage, the DSP upload's record echoes and any stall, for finding where a boot hangs. | on hardware: an MKII, 29 Sep 2026 (OCTABAM4-14); `verify_boot_trace` |
| [**CF METER**](modules/cfmeter/README.md) | [sambanks](https://github.com/sambanks) | Probe: frame-interrupt duration and (with CF METER IDLE) idle time, plus core 0's frame spin count, ESAI underrun/overrun frames and frame period, printed as audio on T8's FX2. | on hardware: cursory testing on Sam's MKII (owner report, 16 Oct 2026); ColdFire half on image 92 (Sam's MKII, 3 Oct 2026: interrupt 123.1 us stopped, 213.5 us playing); the DSP slots and DBRN under the port only (4 Oct 2026) |
| [**CF METER IDLE**](modules/cfmeter-idle/README.md) | [sambanks](https://github.com/sambanks) | Probe: main's idle loop timed, for CF METER's idle-time slot. | on hardware: cursory testing on Sam's MKII (owner report, 16 Oct 2026); boots and loads a project under the port (28 Sep 2026) |
| [**LOAD METER**](modules/load-meter/README.md) | [sambanks](https://github.com/sambanks) | The frame interrupt's share of the ColdFire, each DSP core's busy time per frame and each effect call's cost, for BRAIN's OTOP screen. | on hardware: cursory testing on Sam's MKII (owner report, 16 Oct 2026); the window and both DSP cores' figures under the port (verify_load_meter, verify_brain) |
| [**WAVE LOAD**](modules/waveload/README.md) | [sambanks](https://github.com/sambanks) | Probe: K 4-voice wave engines per frame interrupt (CF METER's BURN), for CF METER's duration readout. | on hardware: image 92, Sam's MKII, 3 Oct 2026: one 4-voice engine 69.2 us of the 362.8 us frame, clean beside four sample tracks |

<!-- modules:end -->

## How it works

```
modules/<name>/manifest.py   what a module is and what it claims (yours, or a pointer into an author's repo)
remixes/<name>/remix.py      which modules, in which chooser order; README.md beside it
remixes/test/<name>/         a remix of one module, for that module's gates
tools/remix/ledger.py        refuses two modules that claim one address, hook, id or buffer, by name
tools/build/build_bus.py     the build: assembles, links, places, wires, verifies -> out/mainos_bus.bin
tools/verify/*               the gates: oracles, the boot under the ColdFire port, menu, cycles, identity
```

A module's code lands in one of two places; the build decides which bytes
go where, and a module declares what it is, not an address:

| class | declared as | where |
|---|---|---|
| ROM cave | `CavePatch`: a `.s` source, or ratified hex | one of the OS image's free zero runs, ~8 KB total shared by everyone |
| DRAM unit | `Linked(..., dram=True)`: a GNU-as unit | linked with every other DRAM unit in the remix into one runtime, packed, appended behind octabam's loader, depacked at boot into a 10 MB reserve carved off stock's 85.5 MB sample/recorder pool |

The OS-image edits every class needs (a detour at a stock instruction, a
poke, a grown table) are `Detour`, `Poke`, `TableGrow`, wired by symbol and
asserted against stock before a byte is written. `docs/contributing/PLACEMENT.md`
is the map of what is free and what was measured.

**A port is a proof.** The build re-links every unit at the author's own
address and compares, and refuses on any drift.

**Where a module's state lives.** An effect's twelve knobs are Part
parameters and stay in the Part. Personal material (KITS's library) is in
files the module owns and formats. A module's settings (menu options, a USB
profile) live in BRAIN (`modules/brain`), the settings, defaults and
templates store: SETTINGS, MIDI LOG, DEFAULTS, the project pair and TOOLS,
designed in
[docs/proposals/BRAIN.md](docs/proposals/BRAIN.md) (6 Oct 2026, starting
from nordseele's
[OTX proposal](docs/proposals/OTX_PROJECT_PROPOSAL.md)). Measured under the
port only; not on a unit.

## Checking without a flash

Everything is checked on your machine against your own 1.40C
([docs/contributing/TESTING.md](docs/contributing/TESTING.md)). The DSP side renders
locally on the assembled instruction stream (`make render`, `make render-rig`;
[tools/harness/README.md](tools/harness/README.md)). The whole machine, the
ColdFire, both DSP cores, the card, the panel, MIDI and USB, runs under a
port of it (`tools/emu/ot_emu`, `make emu-cf`; [tools/emu/README.md](tools/emu/README.md)):

```bash
make check REMIX=<name>             # build + every gate + boot under the port; OT_PROJECT=<dir> adds a real project
make reach                          # the gates this branch's diff reaches, in order; RUN=1 runs them
make panel REMIX=<name>             # the virtual front panel with sound at localhost:8563 (tools/panel/README.md)
make emu-live REMIX=<name>          # the screen and keys in a window, no sound
```

CI (`.github/workflows/ci.yml`, `make ci`) runs the checks that need no
firmware. What the emulators cannot see (caches, the recorder's DMA,
cross-core timing) is listed beside every gate that is blind to it.

## Before you flash anything

**Writing a non-official OS to an Octatrack can leave it unusable and puts
your warranty in question.** Nothing here is endorsed by, supported by, or
affiliated with Elektron. [BUILDING.md](docs/guide/BUILDING.md) has the
recovery path (section 7).

**No Elektron binary is redistributed here, and none may be.** A built
`.bin` or `.syx` contains Elektron's OS: do not share built images. Share
the repo; everyone builds their own.

*Octatrack* and *Elektron* are trademarks of Elektron Music Machines MAV
AB, used here only to identify the hardware this project targets.

## Documentation

[docs/README.md](docs/README.md) lists every doc by who it is for. Each
module's page is `modules/<name>/README.md`, each remix's
`remixes/<name>/README.md`, and each tool's `tools/<dir>/README.md`.

## Repository layout

```
CONTRIBUTING.md    your first PR, the module contract, the oracle rule, the gates, what CI checks
AGENTS.md          working rules and the trap index for coding agents (CLAUDE.md imports it; the full register: docs/contributing/TRAPS.md)
.github/           CI (Ubuntu + macOS, SHA-pinned actions), the PR template
modules/           the contributions, one directory each, each with its README
remixes/           one directory per remix: remix.py (the selection, in chooser order) and README.md; README.md here is the index
remixes/test/      the one-module remixes, for their modules' gates (make check REMIX=<name>)
docs/guide/        building, flashing and composing a remix
docs/contributing/ writing a module, testing, placement, tooling, the failure register
docs/firmware/     the firmware, reverse-engineered
docs/proposals/    technical propositions
tools/remix/       the toolkit: schema, registry, ledger, the loader, the DRAM platform, the TUI
tools/build/       the image build (build_bus.py) and the tools that understand the OS layout
tools/verify/      the gates
tools/harness/     hear and measure the DSP side locally (dsp_host, send_probe, rig_render)
tools/emu/         the ColdFire emulators: the headless port (ot_emu) and the Unicorn bring-up
tools/panel/       the virtual front panel over the port, with sound
tools/hw/          the unit and its card: MIDI control, capture, project files, MIDI flashing
tools/ghidra/      one Ghidra project over the OS and both DSP payloads
tools/patches/     local patches to the vendored toolchains
scripts/           toolchain setup, vendored pins (vendor.sh), OS fetch and recon, the bit-identity gate
dsp/               shared DSP infrastructure: the null stub and the probes
```

## Credit

**Em** ([emuyia](https://github.com/emuyia)) designed Octakit and the
loader-appended DRAM runtime octabam adopted as its large-payload placement;
`tools/remix/loader.S` and the payload packer (`tools/remix/pack.py`) are
derived from hers with attribution. Octakit was carried here as a
submodule until 6 Oct 2026; KITS (`modules/kits`) follows its key map and
reads its `kits3a/b.work` files.

This began as a fork of [mxldyn/octamax](https://github.com/mxldyn/octamax)
by Maxolydian, whose reverse engineering of the OS format, memory map and
parameter tables made any of this reachable; the upstream history is in
this repository's log.

BRAIN's LOAD view (`modules/load-meter`) follows the LOAD view design for the
Machinedrum by Hamish Renton ([SamplesAndSnacks](https://github.com/SamplesAndSnacks)): the bounded
reads, the `-` and `?` states, the refresh counter and the zero-cost close.

`vendor/` pulls in [dsp56300](https://github.com/dsp56300/dsp56300),
[mc68k](https://github.com/joelanders/mc68k-md-mm) and
[elektron-firmware-tool](https://github.com/mischa85/elektron-firmware-tool).

## License

[MIT](LICENSE) for this repository's own code and documentation. It does
not extend to Elektron's firmware, which is not distributed here, nor to
the repositories referenced as submodules, which remain their authors'
under their own terms.
[THIRD_PARTY.md](THIRD_PARTY.md) lists every transcribed DSP source
(Airwindows, JClones, Mutable Instruments, ChowDSP, jpcima, audiojs), the
submodules and the vendored tools, each with its licence.
