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
doc correction. Issues are disabled and there is no request queue. The
licence is MIT; a fork that takes requests and tracks issues is allowed.

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
(`xcode-select --install`), Homebrew, Python 3.10+ and
`brew install cmake uv`. Then `make setup`, `make emu-setup`,
`make os && make recon`, `make image REMIX=<name> BUILD=1`, and the flash
from the card (section 5).

<!-- modules:begin -->

### Effects: the bus

| module | author | what it does | proof |
|---|---|---|---|
| [**DELAY SERVER**](modules/busdelay/README.md) | [sambanks](https://github.com/sambanks) | Multi-mode delay: CLEAN / pitched GRAIN cloud / REVERSE, tape wow. | on hardware: Sam's MKII |
| [**REVERB SERVER**](modules/busverb/README.md) | [sambanks](https://github.com/sambanks) | Eight-line FDN reverb: ROOM/PLATE/BIG, shimmer, gate, mid/side width. | on hardware: Sam's MKII |
| [**FX2 LOCK**](modules/fx2-lock/README.md) | [sambanks](https://github.com/sambanks) | The FX2 chooser cannot change a track's effect: YES's key-table entry points at NO's close handler, so the select handler never runs. | port-gated: verify_fx2lock under the port, 4 Oct 2026 |
| [**MODE DEFAULTS**](modules/mode-defaults/README.md) | [sambanks](https://github.com/sambanks) | A MODE turned on the panel re-defaults the knobs around it (the manifests' ModeViews), on FX1 and FX2. | on hardware: Sam's MKII (images 26/27, 15 Sep 2026) |
| [**RIG HOSTS**](modules/rig-hosts/README.md) | [sambanks](https://github.com/sambanks) | A new part is born hosted: T1 FX2 = BusDelay, T5 = BusVerb, T8 = the stock DELAY, the rest SEND. | port-gated: a new project born hosted under the port |
| [**SEND**](modules/send/README.md) | [sambanks](https://github.com/sambanks) | Bus client: DEL into the delay, REV into the reverb, from any track. The default effect. | on hardware: Sam's MKII |
| [**TEMPO BUS**](modules/tempo-bus/README.md) | [sambanks](https://github.com/sambanks) | The TEMPO window lists and edits BusDelay's and BusVerb's knobs (UP/DOWN = row, A or B = value, LEFT/RIGHT = engine, FUNC + LEVEL = 0.1 BPM). | port-gated: `verify_set`; carried by image 88 on Sam's MKII, not exercised there |
| [**TEMPO SYNC**](modules/tempo-sync/README.md) | [sambanks](https://github.com/sambanks) | ColdFire caves: publishes the held MIDI note to BusDelay, and draws BusDelay TIME as a tempo division. | on hardware: Sam's MKII |

### Effects: on a track

| module | author | what it does | proof |
|---|---|---|---|
| [**CHARACTER**](modules/character/README.md) | [sambanks](https://github.com/sambanks) | FX1 station: fold, saturation, tilt, compressor, width. | on hardware: Sam's MKII |
| [**CHARACTER TXTR**](modules/character-txtr/README.md) | [sambanks](https://github.com/sambanks) | Character plus TXTR (Airwindows Pockey2): fold, texture, saturation, tilt, compressor, width. For testing: 4x this beside the reverb is unmeasured on hardware. | `make check` |
| [**EUCLID**](modules/euclid/README.md) | [repeat98](https://github.com/repeat98) | Euclidean LP/BP/HP/notch/amp sequencer: swing, envelope, gate, random and loop. | local render: its own render gates; not on hardware |
| [**MINIVERB**](modules/miniverb/README.md) | [repeat98](https://github.com/repeat98) | Modulated diffused FDN reverb; independent FX2 buffers, smoothed controls. | local render: `make verify-miniverb`; not flashed |
| [**MODULATION**](modules/modulation/README.md) | [sambanks](https://github.com/sambanks) | FX1 station: a modulation pedal -- Juno, Dimension, flanger, phaser, comb; FX1 only. | on hardware: Sam's MKII |
| [**SIDECHAIN_COMPRESSOR**](modules/sidechain-compressor/README.md) | [Zac-Kyoti/octatrack-kyoti-fw](https://github.com/Zac-Kyoti/octatrack-kyoti-fw) | Stock COMPRESSOR with a side-chain KEY from any of T1-T8, a key filter, key gain and a key listen switch on page 2. | on hardware: the author's MKI, 4 Oct 2026, an octabam image with all six KYOTI modules and REC_TRIG_MUTE: ducking on one core and across cores both ways, KFLT/KGN/MON, a muted KEY in every MUTE MODE |
| [**SPECTRUM**](modules/spectrum/README.md) | [sambanks](https://github.com/sambanks) | FX1 station: a filter pedal -- the Moog ladder, SEM (LP -> BP -> HP by SHPE), Airwindows Capacitor2, formants; ENV and LFO onto the cutoff; width. | on hardware: Sam's MKII |
| [**TAPE ECHO**](modules/tapeecho/README.md) | [repeat98](https://github.com/repeat98) | Economy CPU tape echo: two biquads, simple FREE slew, snapped BEAT TIME and page-1 AGE. | on hardware: the author's unit (OCTACLID4): six instances run, a seventh freezes it, open |
| [**TESTGEN**](modules/testgen/README.md) | [Ignorato](https://github.com/Ignorato) | Measurement source: a sine, sweep, pink or white noise, impulses, a needle pulse train or DC replace the track's audio. | on hardware: Ignorato's MKII, images OCTABAM4-6 and 10 (remix testgen), 3-4 Oct 2026; 0.1 measured at the main outs; FX1-only in the emulator so far |
| [**TRANSIENT**](modules/transient/README.md) | [Ignorato](https://github.com/Ignorato) | Transient shaper: ATCK and SUST reshape onsets and tails, level-independent. | on hardware: Ignorato's MKII, images OCTABAM2 and OCTABAM3 (remix transient), 3 Oct 2026 |
| [**VOCODER**](modules/vocoder/README.md) | [Ignorato](https://github.com/Ignorato) | Ten-band vocoder after the Roland VP-330: the track's voice, a built-in carrier at NOTE or input B. FX2 of tracks 2, 3, 6 and 7 only. | on hardware: Ignorato's MKII, 4-5 Oct 2026, by ear: OCTABAM12 at the earlier positions T1 T2 T5 T6, stable on all eight tracks; this build at T2 T3 T6 T7 not flashed; those positions heard clean on the 0.2 code only (OCTABAM20, branch vocoder-0.2 at f83463c8) |
| [**WAVE**](modules/wave/README.md) | [sambanks](https://github.com/sambanks) | Experiment: a 4-voice wavetable synth on FX2; a sine on the track sets its pitch and level. | on hardware: Sam's MKII, image 93, 3 Oct 2026: plays, PTCH and the CHROMATIC keys move the pitch |

### Machines and the sequencer

| module | author | what it does | proof |
|---|---|---|---|
| [**ANALOG BD**](modules/analog-bassdrum/README.md) | [repeat98](https://github.com/repeat98) | Analog BD track machine: switchable 808/909 circuit-informed synthesis. | port-gated: source/AMP/main on both cores and engine-browser/hidden-control gates; hardware matching pending |
| [**DIRECT JUMP**](modules/direct-jump/README.md) | [timhastie/octatrick-modules](https://github.com/timhastie/octatrick-modules) | CHAIN AFTER: DIRECT (its unused value 1) -- a pattern change lands at the next step, the step count continuing (A4/Rytm direct jump). | on hardware: `octatrick-usb` on his MKI, 26 Sep 2026 (OCTATRICK9) through 2.9; the last two 2.9 fixes under the port |
| [**DIRECT_JUMP_KYOTI**](modules/direct-jump-kyoti/README.md) | [Zac-Kyoti/octatrack-kyoti-fw](https://github.com/Zac-Kyoti/octatrack-kyoti-fw) | Clock-locked DIRECT JUMP ([PTN]+[YES]): a cued pattern lands on the next step exactly where it would be had it played since START. | on hardware: the author's MKI, 27-28 Sep 2026 (standalone 140C_KDJ7 and the KYOTI V1.0 combined image) and 1 Oct 2026 from DRAM (an octabam image with all six KYOTI modules); Program Change re-cues, MIDI tracks, START SILENT and the trig-condition reset emulator-verified |
| [**MUTE_MODES**](modules/mute-modes/README.md) | [Zac-Kyoti/octatrack-kyoti-fw](https://github.com/Zac-Kyoti/octatrack-kyoti-fw) | PERSONALIZE -> MUTE MODE: OT (stock) / OTFX / OTFX-T / DT-T -- dry cut with FX tails, trig suppression, or a Digitakt-style sequencer mute. | on hardware: the author's MKI (standalone image and the KYOTI V1.0 combined image) |
| [**PLOCKS P2**](modules/plocks-p2/README.md) | [sambanks](https://github.com/sambanks) | Parameter locks on FX1/FX2 page 2 (hold trigs, turn a knob on the SETUP page). | port-gated |
| [**QUANTIZE_LIVE_REC_TOGGLE**](modules/quantize-live-rec-toggle/README.md) | [Zac-Kyoti/octatrack-kyoti-fw](https://github.com/Zac-Kyoti/octatrack-kyoti-fw) | QUANTIZE LIVE REC from the front panel: hold [REC], tap [PLAY] to see it, tap again while the toast is up to invert it. | on hardware: the author's MKI, 25 Sep 2026 (gesture) and 30 Sep 2026 (setting survives a power cycle) |
| [**SCALE QUANTIZER**](modules/quantizer/README.md) | [timhastie/octatrick-modules](https://github.com/timhastie/octatrick-modules) | PROJECT > CONTROL > SEQUENCER > SCALE: the PTCH knob and CHROMATIC trig keys quantize to a scale (24 scales, OFF = stock); > ROOT: the note the scale is built on (C..B; key 1 of the CHROMATIC keyboard sounds it); > GLIDE: the synth's glide time (OFF, 1..127; the legato switch is the synth track's LEG setting); polyphonic chromatic keys on a synth track whose VOIC is 2..4; on a synth track PTCH is semitones (-64..+63) and the CHROMATIC octave runs -4..+4. | on hardware: `octatrick-usb` on his MKI, 26 Sep 2026 (OCTATRICK9) through 2.9; the last two 2.9 fixes under the port |
| [**REC_TRIG_MUTE**](modules/rec-trig-mute/README.md) | [Zac-Kyoti/octatrack-kyoti-fw](https://github.com/Zac-Kyoti/octatrack-kyoti-fw) | [TRACK]+[NO]/[YES] mute/unmute the held tracks' recorder trigs; MIDI CC 80; '..' beside a muted track's status icon. | on hardware: the author's MKI, 2-3 Oct 2026 (standalone image and KYOTI V1.0; MIDI CC 80 not tried) |
| [**RELOAD_FROM_PROJECT**](modules/reload-from-project/README.md) | [Zac-Kyoti/octatrack-kyoti-fw](https://github.com/Zac-Kyoti/octatrack-kyoti-fw) | Reload one track's sequence from the card without stopping the transport: [PTN]+[TRACK n], or [BANK]+[TRACK n] to re-apply the Part. | on hardware: the author's MKI (standalone image), sequencer and metronome phase kept; 1 Oct 2026 from DRAM in an octabam image with all six KYOTI modules |
| [**REPITCH**](modules/repitch/README.md) | [repeat98](https://github.com/repeat98) | Adds TSTR REPITCH (STATIC/FLEX and the sample's own TIMESTRETCH): project-tempo following by playback speed, without grains; PTCH off. | on hardware: an MKII, 16 Sep 2026 (OCTABAM81); `verify_repitch` |
| [**REPITCH_REPEAT98_KYOTI**](modules/repitch-repeat98-kyoti/README.md) | [Zac-Kyoti/octatrack-kyoti-fw](https://github.com/Zac-Kyoti/octatrack-kyoti-fw) | TSTR RPCH / RPS9 / RPSP: tempo-locked varispeed with S900/S950 and SP-1200 repitch emulations, and QUAN ratios on PTCH. | on hardware: the author's MKI, 5-8 Oct 2026, octabam images with every KYOTI module, REC_TRIG_MUTE and SIDECHAIN_COMPRESSOR, only SPRING REV given up: RPCH/QUAN, RPS9/RPSP, on T5-T8 beside SIDECHAIN, TSTR across a Part reload; four RPSP tracks per core with DARK REV, and up to three DJ EQs on T5-T8 |
| [**RLEN PLEN**](modules/rlen-plen/README.md) | [sambanks](https://github.com/sambanks) | ColdFire cave: RLEN value PLEN (past MAX) = one loop of the track's pattern on its own scale, so TRIG ONE + QREC PLEN records the next pass and stops. | port-gated: 26 Sep 2026 |
| [**STEM REC**](modules/stems/README.md) | [yvesrosius](https://github.com/yvesrosius) | Multitrack recording to the card: each track (after its fader), MAIN, CUE and the inputs as separate WAV files, 16 or 24 bits, up to 60 minutes. MAIN MENU > STEMS. | on hardware: Yves's MKII: STEMS1 (30 Sep 2026), T1-T8 for about two minutes; STEMS3 (6 Oct 2026), T1-T8 after the fader, MAIN and AB at 16 and 24 bits |
| [**SYNTH MACHINE**](modules/synth/README.md) | [timhastie/octatrick-modules](https://github.com/timhastie/octatrick-modules) | A FLEX track whose sample is named SYNTH* plays a two-operator FM voice (STRT/LEN/RTRG/RTIM = ratio/index/feedback/decay); the DSP shapes and effects it as a sample. Its PLAYBACK page reads RATO/INDX/FDBK/DEC with icons and the title FM SYNTH; PTCH is semitones (-64..+63) and RATE is FINE (cents) on a synth track, 0c the moment a track becomes one. A FLEX or STATIC sample track with LEG MONO and GLIDE slides its pitch (2.8). | on hardware: `octatrick-usb` on his MKI, 26 Sep 2026 (OCTATRICK9) through 2.9; the last two 2.9 fixes under the port |
| [**TUNER**](modules/tuner/README.md) | [timhastie/octatrick-modules](https://github.com/timhastie/octatrick-modules) | UP + TEMPO: a tuner window for the current audio track -- note, octave, cents, needle, Hz (McLeod NSDF + YIN refine on the ColdFire, in the UI task). | on hardware: Tim's MKI, test build 3.0 b40 (`octatrick` at BUILD 40), 29 Sep 2026: UP + TEMPO opens the window and tunes; sources unchanged since 26 Sep |

### Parts, Kits and scenes

| module | author | what it does | proof |
|---|---|---|---|
| [**KITS**](modules/kits/README.md) | [sambanks](https://github.com/sambanks) | 255 Kits per project: PART = LOAD KIT, FUNC+PART = SAVE KIT (MKI: FUNC+MIDI, then FUNC+BANK); each pattern plays its Kit through the stock Part slots. After Em's Octakit. | on hardware: Sam's MKII (image A6, 6 Oct 2026): the Octakit import, ems-octakit #5, STOP/PTN+TRIG/PLAY with the Rytm, a rejected bank file, power cycles; `verify_kits` under the port |
| [**MIDI SCENES**](modules/midi-scenes/README.md) | [bkkbrls-del/midisc](https://github.com/bkkbrls-del/midisc) | Scene locks for the MIDI tracks (hold-to-lock, readout, unlock, lock LEDs, XF morph, scene clear / copy / paste), kept per Part in scenes.work and CS1. After bkkbrls-del's midisc. | port-gated: `verify_scenes` against MIDISC2.1 under the port, phase 1 scenarios (b1, b7, b3, b29copy, b29clear); the earlier 2.0 build ran on his unit as `ok-ms`, 14 Sep 2026 |
| [**SCENES P2**](modules/scenes-p2/README.md) | [sambanks](https://github.com/sambanks) | Scene locks and the crossfader on FX1/FX2 page 2 (hold a scene, turn a page-2 knob). | port-gated: 26 Sep 2026 |
| [**STORE**](modules/store/README.md) | [sambanks](https://github.com/sambanks) | Platform: the stock save, load, copy, CS1 and Part sites KITS and PLOCKS P2 share. | port-gated |

### MIDI and USB

| module | author | what it does | proof |
|---|---|---|---|
| [**CC FEEDBACK**](modules/cc-feedback/README.md) | [sambanks](https://github.com/sambanks) | Every knob value change is transmitted as its CC (page 1: 16-45; page 2: CC MAP's 62-73), so a controller's encoders follow the unit. | port-gated: `verify_ccfeedback` (Unicorn) and `verify_set` (the port's MIDI OUT bytes) |
| [**CC MAP**](modules/cc-map/README.md) | [sambanks](https://github.com/sambanks) | MIDI CC 62-67 drive the FX2 engine's page-2 slots 6-11; CC 68-73 the FX1 station's. | on hardware: Sam's MKII (image 96, 13 Sep 2026) |
| [**USB AUDIO IN AB**](modules/usb-audio-in-ab/README.md) | [bryantysinger](https://github.com/bryantysinger) | A stereo pair from the host into inputs A/B (UAC2 EP3 OUT, implicit feedback); the jacks while the stream is closed. C/D stay on the jacks. | port-gated: `verify_usb_in` under the port (28 Sep 2026); the four-channel form ran on Bryan T's MKII as usbin-test build 16 (27 Sep 2026) |
| [**USB AUDIO IN ABCD**](modules/usb-audio-in-abcd/README.md) | [bryantysinger](https://github.com/bryantysinger) | Four channels from the host into inputs A-D (UAC2 EP3 OUT, implicit feedback); the jacks while the stream is closed. | port-gated: `verify_usb_in` under the port (28 Sep 2026); this channel set ran on Bryan T's MKII as usbin-test build 16 (27 Sep 2026), with its inject poked into SPATIALIZER's words |
| [**USB AUDIO IN CD**](modules/usb-audio-in-cd/README.md) | [bryantysinger](https://github.com/bryantysinger) | A stereo pair from the host into inputs C/D (UAC2 EP3 OUT, implicit feedback); the jacks while the stream is closed. A/B stay on the jacks. | port-gated: `verify_usb_in` under the port (28 Sep 2026); the four-channel form ran on Bryan T's MKII as usbin-test build 16 (27 Sep 2026) |
| [**USB AUDIO OUT MAIN**](modules/usb-audio-out-main/README.md) | [markandrus/octemu](https://github.com/markandrus/octemu) | MAIN L/R over USB (UAC2, 2 channels, 24-bit) every 250 us; the stereo pairing for USB AUDIO IN (markandrus/octemu's source, the MAIN layout ours). | port-gated: `verify_usb` under the port (28 Sep 2026); not on a unit |
| [**USB AUDIO OUT MAIN CUE**](modules/usb-audio-out-main-cue/README.md) | [markandrus/octemu](https://github.com/markandrus/octemu) | MAIN and CUE over USB (UAC2, 4 channels, 24-bit) every 250 us; full speed carries MAIN alone (markandrus/octemu; the MAIN + CUE variant Bryan T's, from usbin-test's AUD_IN4). | on hardware: Bryan T's MKII, build 16 (usb-io), 27 Sep 2026, high speed; the full-speed MAIN-only path not run on a unit |
| [**USB AUDIO OUT MASTER**](modules/usb-audio-out-master/README.md) | [markandrus/octemu](https://github.com/markandrus/octemu) | Track 8's L/R over USB (UAC2, 2 channels, 24-bit): the master track, post-FX pre-fader; USB AUDIO OUT TRACKS MAIN CUE's source, the T8 variant Sam Banks's. | port-gated: `verify_usb` under the port (27 Sep 2026); not on hardware |
| [**USB AUDIO OUT TRACKS**](modules/usb-audio-out-tracks/README.md) | [markandrus/octemu](https://github.com/markandrus/octemu) | Sixteen 24-bit channels over USB (UAC2): the tracks post-FX pre-fader, no MAIN/CUE; the stereo sum at full speed (markandrus/octemu). | port-gated: `verify_usb` under the port (27 Sep 2026); this build not on hardware (image 69 ran the 16-channel layout from earlier source) |
| [**USB AUDIO OUT TRACKS MAIN CUE**](modules/usb-audio-out-tracks-main-cue/README.md) | [markandrus/octemu](https://github.com/markandrus/octemu) | Twenty 24-bit channels over USB (UAC2): the tracks post-FX pre-fader, MAIN, CUE; the stereo sum at full speed (markandrus/octemu). Costs the ColdFire 27-50 us of each 362.8 us frame over OUT MAIN CUE, host or not (one MKII, 4 Oct 2026). | port-gated: bus reset and session-end shims (audio_reset_shim, audio_sessend_shim): the alt 0 request `verify_usb` under the port only, the `usbmidi_rx_bus_end` call on Ignorato's MKII (OCTABAM21, 9 Oct 2026, three replugs); the rest ran on Sam's MKII (image 64, 25 Sep 2026) and Tim's MKI (OCTATRICK9, 26 Sep 2026) |
| [**USB AUDIO OUT TRACKS POST**](modules/usb-audio-out-tracks-post/README.md) | [markandrus/octemu](https://github.com/markandrus/octemu) | Sixteen 24-bit channels over USB (UAC2): each track after its own MAIN gain (LEVEL, mute, solo, XLV; MAIN_LEVEL left out); the stems' stereo sum at full speed. USB AUDIO OUT TRACKS MAIN CUE's source (markandrus/octemu), the POST layout allmyfriendsaresynths's (@clickysteve). | on hardware: allmyfriendsaresynths's MKII, P3 (usb-out-tracks-post), 5 Oct 2026: 16 channels, each track on its pair, LEVEL/mute/solo/crossfader follow; the gain engine nulled against MAIN in a 20-channel diagnostic build; 7 Oct 2026: streaming costs +2.8 µs a frame over OUT TRACKS (CF METER); MASTER TRACK and the no-host cost not on a unit |
| [**USB CROSSBAR**](modules/usb-crossbar/README.md) | [bryantysinger](https://github.com/bryantysinger) | The USB controller bursts and arbitrates first on the SDRAM and SRAM crossbar ports (SCM BCR, XBS PRS/CRS), set at boot; cures lost isochronous packet tails. | on hardware: the register values, written at stream-up by usbin-test builds 12-16 on Bryan T's MKII (26-27 Sep 2026); this boot-time write under the port only |
| [**USB MIDI**](modules/usb-midi/README.md) | [markandrus/octemu](https://github.com/markandrus/octemu) | Class-compliant USB-MIDI in and out on the OT's own USB port, mirroring the DIN ports (markandrus/octemu). | on hardware: Sam's MKII (image 64, 25 Sep 2026: enumerates, receives 7,950 msg/s); Tim's MKI (OCTATRICK9, 26 Sep 2026); USB clock tempo on Kazeko's MKI (#633, 6 Oct 2026); transmit, and transmit after three cable replugs, on Ignorato's MKII (OCTABAM21, 9 Oct 2026, macOS and Windows 10) |

### Fixes

| module | author | what it does | proof |
|---|---|---|---|
| [**BATCH_BUGFIXES**](modules/batch-bugfixes/README.md) | [Zac-Kyoti/octatrack-kyoti-fw](https://github.com/Zac-Kyoti/octatrack-kyoti-fw) | Three stock 1.40C bug fixes in one module: MIDI Plays-Free trig, empty-pattern LED, and Part-change carryover. | on hardware: the author's MKI (bugs 1 and 3, and bug 2's [BANK]-held stall ended); bug 2's [PTN] answers emulator-verified identical to its earlier hardware-confirmed version |
| [**ERASE_EMPTY_TRIGLESS_LOCKS**](modules/erase-empty-trigless-locks/README.md) | [Zac-Kyoti/octatrack-kyoti-fw](https://github.com/Zac-Kyoti/octatrack-kyoti-fw) | Bug fix: a trigless lock whose last parameter lock is erased stops staying lit on the trig row. | on hardware: the author's MKI (standalone image) |
| [**LOFI AMF FIX**](modules/lofi-amf-fix/README.md) | [bryantysinger/octa-bt-pt](https://github.com/bryantysinger/octa-bt-pt) | Fixes stock LO-FI's AMF knob: mpysu -> mpyuu, both payloads. Ported from bryantysinger/octa-bt-pt. | `make check`: both words disassembled against stock |
| [**RECORDER LOOP FIX**](modules/recorder-loop-fix/README.md) | [sambanks](https://github.com/sambanks) | ColdFire caves: the recorder loop click -- seek on a same-sample FLEX re-bind, keep its counter, record exactly the arm spacing, and repeat the last sample where sound-on-sound would play a zero. | on hardware: OCTABAM83, 12 Sep 2026 (self-loop); Bryan T's MKII, sos-capture BUILD=95, 3 Oct 2026 (sound-on-sound) |

### Reference

| module | author | what it does | proof |
|---|---|---|---|
| [**CF METER**](modules/cfmeter/README.md) | [sambanks](https://github.com/sambanks) | Probe: frame-interrupt duration and (with CF METER IDLE) idle time, plus core 0's frame spin count, ESAI underrun/overrun frames and frame period, printed as audio on T8's FX2. | port-gated: ColdFire half on image 92 (Sam's MKII, 3 Oct 2026: interrupt 123.1 us stopped, 213.5 us playing); the DSP slots and DBRN under the port only (4 Oct 2026) |
| [**CF METER IDLE**](modules/cfmeter-idle/README.md) | [sambanks](https://github.com/sambanks) | Probe: main's idle loop timed, for CF METER's idle-time slot. | `make check`: boots and loads a project under the port (28 Sep 2026); the idle number needs the unit |
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
parameters and stay in the Part. Personal material (KITS's library,
octalab's grooves) is in files the module owns and formats. A module's
settings (menu options, a USB profile) have no shared home yet; the store
for settings, defaults and templates is designed in
[docs/proposals/STORE.md](docs/proposals/STORE.md) (6 Oct 2026, starting
from nordseele's
[OTX proposal](docs/proposals/OTX_PROJECT_PROPOSAL.md)), and is not implemented.

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
AGENTS.md          instructions and traps for coding agents (CLAUDE.md imports it)
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
