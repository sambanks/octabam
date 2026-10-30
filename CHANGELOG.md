# Changelog

One entry per image that reached a unit, newest first; `Unreleased` is what
main carries that no flashed image has yet. The version the panel shows is
`BUILD` (`make image BUILD=N`); git tags exist for images 28, 29, 38, 42
and 43 (`OCTABAM<N>`, the commit the image was built from). Image numbers
repeat: 43 has two entries (21 Sep `OCTABAM43`; 25 Sep `padfix`), 94 has two
(`OCTABAM94`, 26-27 Sep; `sos-capture` BUILD=94, 3 Oct), and 95 names
`sos-capture` BUILD=95 (3 Oct) and, in the image A0 entry, one of the
3-4 Oct bottleservice images 95-99. The 22-25 Sep diagnostic run wrapped
past 108 to 19, so its numbers (81-99, 100-108, 19-42, in the
"Images 55-108 and 19-42" entry) overlap the numbered entries around it,
including Image 90 (`usb-lean`). Other documents cite 94, 96 and 99 for
13 Sep builds that have no entry here (`docs/contributing/FAILURE_MODES.md`,
`modules/cc-map/manifest.py`). Each heading gives the date and remix.

The full text before this rewrite: `git show 666b6154:CHANGELOG.md`.

## Unreleased

- DISTORX v10 (`modules/distorx`): the RAT and SD-1 sample loops split into settled (MIX 127, the wet alone), calm (d = 0, the MIX blend) and fading, with a leaner stage; bit for bit v9 in the emulator, static cost 291 → 223 (RAT, settled) and 227 → 181 (SD-1). Not flashed: v9's 9.45 % of core 0 at its dearest is the only unit figure, and `dear` is now MIX 126.
- **USB** (`modules/usb`): less ColdFire time per frame. USB IN writes the
  DSP's block to on-chip SRAM (`0x80007880`) instead of SDRAM through the
  uncached alias, one long load a sample; USB OUT's dTDs are in on-chip
  SRAM (`0x800079c0`), and the producer writes each frame in the stream's
  wire layout straight into the ring (through the alias), the packets sent
  from there: no copy. On Bryan T's MKII (IN ABCD, OUT MAIN CUE, images
  with a frame profiler, 27 Oct 2026): USB's share of the frame interrupt
  about 34 -> 24 us a frame; two 20-minute round-trip soaks, idle and with
  three recorder loops, every click at one latency and every IN/OUT
  counter +0 (on images that also carried the profiler's timer reads,
  which this change does not).
- **USB**: TRACKS with MASTER is refused (build, SETTINGS, cfgsel), at
  Sam's request: the 22-channel combination is gone, and every combination
  polls at 250 us. With TRACKS on, MASTER's channels had never carried
  track 8 (the old producer stored the pair into the next frame's track 8
  field).
- SIDECHAIN_COMPRESSOR (`modules/sidechain-compressor`, `b0d49bf`): on the author's MKI as OCTABAM33 (`remixes/test/sidechain-compressor`, mainos `6cfe4121…`, 26 Oct 2026): KBAS and KWID across their range with MON on and off, MON's switch and its OFF on a project saved with an earlier version, KEY's pressed turn, the MON and KEY fades, all good. The module's proof is now hardware.
- MIDI Follow: LIVE commits GRAV history once per receiver update, preserving
  Part-replacement validation and release-only behavior. Seven four-voice
  receivers use 29,041 measured instructions, down from 41,858; emulator
  instruction counts exclude native MIDI transmission.

- MIDI Follow now applies inherited source KEY after TRAN, matching stock;
  native-only KEY display/locking and drift-free LIVE voice correction.

- STORE: optional native Part access replaces MIDI PART STATE. Registered clients share edited/playing context lookup, bounded native field writes with dirty/CS1 updates, outgoing snapshots during native replacement and per-Part replacement counters. MIDI Follow, Loopback and Scales integrations use the service; saved bytes are unchanged. Existing STORE selections without these clients gain no Part hooks or snapshot storage. Emulator qualification and limited MKII Part save/reload and power-cycle checks (MFOL29U/FA); broader hardware coverage remains unverified.

- MIDI Follow: per-track RFOL source, FIXED/GRAV/SOURCE register and TRIG/LIVE updates. Followers use the source's native N1–4 pitches with their own rhythm and TRAN; settings belong to the Part. Requires STORE native Part access and EVENTS. Standalone and combined EVENTS-client test remixes only; no standard remix gains it. Linked-code and full-firmware emulator checks; limited MKII four-note USB output, STOP releases and Part persistence checks (MFOL29U/FA).

- SIDECHAIN_COMPRESSOR (`modules/sidechain-compressor`, submodule `554ca1c` → `b0d49bf`): KBAS and KWID work in this form. The key-filter table's base came from `lua (r1+$10),r1` after the gain store had already moved r1, so the filters read their coefficients from unrelated P memory: silence, level jumps and squeals on the author's MKI (OCTABAM31, 24 Oct 2026). The table is now the module's `ptable2`, loaded by its own literal as in the standalone image; the image changes in two DSP words per core. MON shows OFF on the left and ON on the right (it stores 2 / 3; `sc_norm` turns any other value OFF, so a COMPRESSOR saved with an earlier version comes up with MON OFF); KEY gets its own step handler (`word_12a`), so a pressed turn moves one position per detent instead of stock's 7; switching MON, or changing KEY while MON is on, fades over 256 samples (was 64). `sc_cf` grows to 698 B. On the author's MKI: the table fix as OCTABAM32 (25 Oct 2026); MON, KEY and the fades in the author's standalone image `140C_SCKD3` (25 Oct 2026), not yet in this form.
- **EVENTS** replaces SEQUENCER EVENTS with separate transport,
  MIDI notification and editor contracts. EUCLID and PLOCKS P2 register as
  consumers. Unused events install no hooks or code; active events use generated
  direct calls. PLOCKS mirrors native trig-undo snapshots so page-two locks
  restore with page one. [Tests on radiohagen's MKII](remixes/test/events-clients/README.md#hardware-results)
  cover controlled trig undo, CONTINUE and sustained audio.

- OCTA303 v7.1 (`modules/octa303`, MaMarko; code by Claude): on an OCTA-303 track, held trig + UP / DOWN moves each held step's TUNE an octave, as the TB-303's UP and DOWN (stock opens the sample-lock list, which a machine without samples has no use for; every other track is unchanged), with a toast naming the note (`C4 +OCT`); a new trigless trig or trigless lock gets the TUNE lock of the note it slides from at once (the previous step with a trig or a slide, else the Part's TUNE), so a slide ties into that note until another is chosen; LFO SETUP names the PLAYBACK destinations TUNE CUT RES ENV DEC ACC (was FLEX's PTCH STRT LEN RATE RTRG RTIM: the modulation was right, the names were not). Five new detours, read from the user's 1.40C: `0x400434d8` (the held-trig layer's UP / DOWN), `0x40060b58` / `0x40060b3e` (the trig keys' press and the release handler's tail), `0x4003bff0` (the LFO PMTR formatter, the site BLACKPYRAMIDS_303 also uses). `test_octa303` 108/108; `tools/octa303/port_o3keys.py` drives the panel under the port. On the owner's MKI as image O3V71 (BUILD A0, `remixes/test/octa303`, 23 Oct 2026): every step of the checklist.
- MORPH (`modules/morph`, MaMarko; code by Claude): a track's scene morph played by itself, A → B → A once every STEPS × x sequencer steps (16 × 8 by default; STEPS 1..64 or the track's length, x 1..16), counted on the sequencer's step word, starting on A; the other tracks keep the crossfader. [TRACK] + [UP] opens a window (STEPS, x, MODE SMOOTH / TRIG HOLD on A, B, C) and arms the held tracks, which start on the step after the track keys are released; [TRACK] + [DOWN] finishes the cycle on A and parks the track there until the crossfader reaches A. The settings and which tracks morph are saved in `morph.work` beside the bank files (`.strd` at SAVE PROJECT, back at RELOAD); MORPH is STORE's client 4, a bad file is listed and never written over. Inspired by the Korg Electribe's Motion Sequence. Conflicts with REC_TRIG_MUTE (both rewrite the [TRACK]-layer table). `remixes/test/morph`; gates `test_morph` (source simulator) and `port_morph` (port). On the owner's MKI as image MRPPR1 (BUILD 98, `remixes/test/morph`, 23 Oct 2026): the window, the start on the release, x to 16 and 41.625, the settings and the morphing tracks kept through SAVE PROJECT and a power cycle, RELOAD back to the saved copy, another project on the defaults; before, inside aCiDtRacK (ACIDV74MP, 22 Oct): several tracks at once, SMOOTH and TRIG HOLD.
- `octabam-core`: USB IN is selectable (default OFF), no longer pinned. The 29-word inject goes above payload A's code through `DspSection.tail`. The platform reserve is unchanged at 1,707 pages (12,895 left for samples); the tail's 167,318 B pre-boot region fits inside it. Two build fixes it needed: the pre-boot table's entries now precede the runtime's blob in the loader (a 79,748 B runtime put `pretable` out of the 16-bit PC-relative reach of `lea`), and the first platform link assembles the loader with the pre-boot code (REMIX SWITCH's `osw_resume` and `osw_chain` sit after it, and moved between the two links). Under the port only; not on a unit in this remix.
- DSP tail placement (`DspSection.tail`): where a remix keeps all fourteen stock effects, so nothing is harvested, a tail section goes above the payload's code (payload A `P:$1fdf..$1fff`, 33 words) in a load record of its own. The build splices the record into a copy of the payload, ships the copy as a pre-boot payload of octabam's loader into a DRAM region (167,318 B for payload A, 28 sample pages), and pokes the DSP boot's upload pointer at it, ANALOG BD's route (Sam B, #854); stock bytes and payload B do not move. A remix with a donor region places the section there as before, so no remix that built before changes. USB's RX inject is the one user: `remixes/test/usb-io-stock14` carries USB IN on all fourteen effects, and `verify_usb_in` passes under the port. On Bryan T's MKII (OCTABAM4, 22 Oct 2026) `tools/hw/usb_in_tones.py` reads the same as with the inject in a donor region, so the chip runs code at `P:$1fdf..$1fff`. Refhash: 24 configurations bit-identical.
- USB IN: the DSP inject (`modules/usb/rx_inject.asm`) is 29 words on payload A, was 39, and runs 9 instructions a sample in its loop, was 15 (ABCD: 304 a frame, was 496). Each sample is joined from its two host-port halfwords with one `insert` instead of shift, mask and add, the stores walk `(r1)+` instead of a displaced store, and one outer `do #2` runs both passes over the same loop (no `bsr`, `X:$202` read once). Bit-exact against the previous inject in the emulator over every IN value, both banks and all nine RX blocks (5,000 random frame-head states, stale bytes included), and `verify_usb_in` passes. On Bryan T's MKII (`usb-io-main-cue-abcd`, OCTABAM1 against OCTABAM2 from main, 21 Oct 2026) the new `tools/hw/usb_in_tones.py` reads the same for both: each input at unity on its own side, the rest within rounding. It also found a DC offset on MAIN R (about -410 LSB) with either inject while the host sends zeros; its source is not read.
- DISTORX (`modules/distorx`, MaMarko; code by Claude): the BOSS SD-1, the Pro Co RAT and the Turbo RAT in one FX1/FX2 insert, each modelled from its part values; MODE picks the pedal (OFF, the default, runs nothing) with a 2.9 ms fade through the dry signal at every change. On SPATIALIZER's id `0x05` (`replaces="SPATIALIZER"`); a conflict with SHATTER (both per-track dirt inserts). `remixes/test/distorx` gives up SPATIALIZER, CHORUS, PLATE REV and SPRING REV (its 1,586 words in one run; DARK REV stays). Gate `verify_distorx` (dsp_host, bit-exact against its model). On the owner's MKI as image DTXPR3 (BUILD 96, on `0x05`, 22 Oct 2026): T1 for more than four minutes with four DISTORX at once over both cores, no clicks; before, as DTXPR1 (on `0x0a`, 21 Oct): every knob in every MODE, an LFO, a scene, save and reload.
- DEVILISH (`modules/devilish`, MaMarko; code by Claude): Robin Whittle's Devil Fish mods for OCTA-303 tracks, an FX on PHASER's id `0x10` (`replaces="PHASER"`) whose twelve knobs the OCTA303 voice reads; its DSP half is a pass-through. OCTA303 now reads dEVILish's page 1 from the DSP voice record (locks, scenes and LFOs applied), so an LFO on a dEVILish knob reaches the 303 (before, the voice morphed the lane bytes itself and no LFO reached it). `remixes/test/devilish` gives up PHASER. The build: a remix whose descriptor clones' bytes pack past the sized platform reserve is built again a page bigger (OCTA303 + DEVILISH ended 74 B over; every other build unchanged, refhash 24/24). On the owner's MKI as image DEVPR2 (BUILD 93, 22 Oct 2026): every knob, an LFO, a scene, a lock, save and reload.
- BLACKPYRAMIDS_303 (`modules/blackpyramids-303`, submodule `5af46f8` → `b0530d3`): the voice recalibrated on the TB-303's own circuit (Roland's service notes, the x0xb0x schematics, Robin Whittle's notes) and fitted against Din Sync's recordings of a real TB-303, every behaviour chosen by the author's ear. The couplings around the filter where the circuit has them (0.7 Hz in, 55 Hz in the resonance loop, 110 Hz out); the filter closes to 70 Hz; the 303's accent sweep capacitor (accents in a row stack into its rising sweep); the 303's accent and VCA decays; CUT on the real 303's range on 0–100 and one octave beyond on 101–127 (the top of RES eased there); RES and ACC on the real 303's range, spaced so every step does as much; GATE and SLID default to the 303's; loudness steadier across CUT; 3 dB more into the VOL drive, ramped from VOL 65, and a click-free VOL 64 / 65 crossing. Data and ColdFire words only: the DSP code and its cycles are unchanged, its constant (X) words carry the new couplings and cutoff table. The runtime grows from 32,364 B to 39,736 B; detours and pokes are unchanged. On the author's MKI, 21 Oct 2026: the standalone image and this octabam form (`remixes/test/blackpyramids-303`), all good.
- SYNTH MACHINE: a `PLACE` setting (`timhastie.synth`; DRAM, the default, links the page into the platform runtime; CAVE is the author's bytes). The cave at `0x400d24d0` sits where the stock DELAY reads past its coefficient table, so a remix with SYNTH MACHINE computes a different DELAY at slow tempo and long TIME (issue #771: `verify_tapeecho_cpu` failed in `octabam-experimental`). The stock DELAY now keeps `0x400d24d0..0x400d24df` (`stock.py`): a remix that lists DELAY refuses a module writing there, so SYNTH MACHINE with CAVE is refused beside it. With DRAM the TAPE ECHO + SYNTH MACHINE remix passes, and the synth pages render pixel for pixel as the cave form's (port). No shipping remix carries SYNTH MACHINE; `octatrick` and the `cfmeter` test remixes now build with the DRAM page. Not on a unit.
- BUFFER SAVER: PROJECT > SAVE TO NEW asks SAVE SAMPLES? too (it saved without the takes; found on Chupitnik's MKII, 17 Oct); stock's copy then carries them into the new project (port: PROJ DIR and AUD POOL). The take hook moved from `0x400069d6` to `0x400069e4`, so REC THRESHOLD's gate passes in a remix with both. `verify_buffer_saver` is six short boots. README: after a power cycle nothing is offered (the buffers do not survive it); how RELOAD (port), SYNC TO CARD and EXPORT TO SET (read) behave; the merged head as flashed.
- BLACKPYRAMIDS_303 (`modules/blackpyramids-303`, submodule `7d9e121` → `5af46f8`): BLKPYRAMD keeps its knobs when the track switches to another machine and back, as every stock machine does; before, coming back reset them to the defaults. The knobs live in FLEX's bytes while the track is the machine, so on leaving they are now kept in NEIGHBOR's unused bytes (FLEX's own values go back as before). SRC SETUP's BLKPYRAMD row on another machine's track shows and edits those kept values; it used to write FLEX's SETUP bytes. The runtime grows from 31,512 B to 32,364 B. This octabam form was flashed on the author's MKI (19 Oct 2026): every check passes.
- BRAIN: USB's IN refusal ("IN NEEDS AN OUTPUT STREAM") works. `usb_pair_ok` compared the settings' keys with 1-5 where `modules/usb/manifest.py` numbers them 7-11, found none, and allowed every change; IN went to AB with TRACKS, MAIN, CUE and MASTER all OFF (emulator, 19 Oct 2026). `verify_brain` now drives the sequence from the panel. Port only, not flashed.
- PLOCKS: releasing a held trig after editing an FX page-two lock keeps the new lock; a later bare trig tap still clears it. The editor now mirrors the native edited flag and pending-tap reset. Hardware tested by radiohagen on an Octatrack MKII (Core, 17 Oct 2026; source `b6a9d17`, local build label `OCTABAMP4`): hold/edit/release/rehold, FX SETUP display and stock-like hold timing checks passed. Numeric timing and Bus/Inserts checks remain emulator evidence.
- BUFFER SAVER (`modules/buffer-saver`, Chupitnik): SAVE PROJECT (PROJECT > SAVE and FUNC + PROJ) asks SAVE SAMPLES? when a recorder buffer holds a take not yet saved. YES saves each such buffer under stock's name `R<n>-YYMMDD-HHMM` (`-2`, `-3` … when taken, never an overwrite), assigned to itself through stock's own save-and-assign (SAVE ALL RECORDINGS' mode 2), then saves the project; NO saves as stock. `remixes/test/buffer-saver`; gate `verify_buffer_saver` (port). On a unit, images AUTOSAVE1 and AUTOSAVE2 below.
- VOCODER 0.2 (`modules/vocoder`, Ignorato, #784): page 1 NOTE, BEND, GEND, WHSP, DRY, CONS; page 2 MODE, SCAL, GLDE, RANG, KEY; LEVL removed (the track's AMP sets the level). BEND is ±12 semitones on NOTE (RANG: 6, 12 or 24); GEND scales the formants; WHSP blends the carrier to white noise; SCAL and KEY snap NOTE to a scale; GLDE glides; GEND, WHSP, DRY and CONS follow their knobs over about 8 ms. Value 0 of each new select renders bit for bit as 0.1. VOCODER now runs on FX2 of T2, T4, T6 and T8 (0.1: T2, T3, T6, T7); on T3 and T7 it passes dry. A Part saved under 0.1 needs `tools/hw/ot_project.py stamp-defaults <project> vocoder` before it plays. `remixes/test/vocoder-usb` added. Heard on Ignorato's MKII (OCTABAM27, 18 Oct 2026).
- Arena: PURGE SAMPLES froze the unit in every remix with a DRAM reservation. `tools/remix/arena.py` moved `cmpal #0x40a955e0` at `0x400254f8` with the arena base, but it ends PURGE's walk over the 16 banks (their end is the stock base only by layout), so the walk ran off the end of RAM. That site stays stock now (27 words rewritten, was 28), and `pokes()` asserts it is never listed. Seen on Chupitnik's MKII (image AUTOSAVE1); the port: stock and the fixed image leave the walk at `0x40025502`, the old image ran on to `0x69f72010`; fixed on the unit (AUTOSAVE2, PURGE finishes, 16 Oct).
- BLACKPYRAMIDS_303 (`modules/blackpyramids-303`, Zac Kyoti, submodule at `7d9e121`): BLKPYRAMD, a TB-303 voice (Robin Schmidt's Open303 on the DSP56300) as a track machine, one per DSP core, played by the sequencer (notes, accents, slides, ties), the chromatic keys and MIDI. One DRAM unit (the author's runtime, `reference` byte for byte), 44 detours, 7 pokes, the FLEX renderer slot, and its DSP voice over SPRING REV's words. Its remix gives up SPRING REV and carries no other DSP module (`remixes/test/blackpyramids-303`). The author's standalone images run on their MKI (14–16 Oct); this form is not flashed.
- Build: `Module.dsp_source` names a module's DSP integrate step, called last in `build_bus.py` where the ANALOG BD hook was hard-wired. ANALOG BD declares `tools/build/ab_image.py` through it and builds identical (`remixes/test/analog-bassdrum`: `ece7075f` before and after). The build refuses two source machines in one remix.

- Removed REPITCH_REPEAT98_KYOTI (`modules/repitch-repeat98-kyoti/`, its submodule mount and `remixes/test/repitch-repeat98-kyoti/`) at its author's request; `octabam-inserts` no longer carries it. Its ColdFire core started from repeat98's REPITCH, and its author is rewriting it without that code.
- GATE VERB (`modules/gateverb`): a gated plate reverb for FX2 on PLATE REV's id, built on the reverb stage of Mutable Instruments Clouds (Emilie Gillet), ported to fixed point. Six knobs: AMNT GAIN TIME DIFF TONE GATE (the gate is new: hold 52 to 784 ms after the input falls quiet, then a 3 ms close; the tank keeps ringing). One FX2 slot per instance; in `octabam-inserts`. Under `dsp_host` only: a float model agrees to 58 dB (63 dB with the gate), the gate closes to exact silence, no write outside its 16,120-word ring. Not heard, not on a unit.
- Stations: a `SLOTS` build setting on SPECTRUM, CHARACTER and MODULATION (`FX1`, the default, or `FX1+FX2`); `FX1+FX2` runs an FX2 instance live and lists the FX2 row. `tools/verify/verify_stations_fx2.py` (remix `stations-fx2`) renders FX2 against FX1, bit for bit. CHARACTER is a bus reader (`Harness.bus_reader`), not a client: a remix with CHARACTER and no server uses fallback NONE with no SEND, and the build turns its KEY = T1 into SELF there. `octabam-inserts`: stations on both menus, the stock DELAY, no SEND.
- Removed `remixes/test/brain` and the example image templates `templates/amp-short.json` and `templates/midi-drums.json`. `verify_brain` and `verify_loadmeter` default to `octabam-bus`; `verify_brain` skips its image-template checks on a remix with no `templates`.
- Remixes: `octabam-bus` and `octabam-inserts` (the core ColdFire modules with the bus, and with the inserts; port gates only, not flashed). `bottleservice` and `ok-ms` retired. `octatrick`, `analog-bassdrum` and `wave` moved to `remixes/test/` with their selections.
- Ledger: LOAD METER (declared range `X:0x37F10..0x37F2F`, no FX2 buffers) no longer refuses the FX2 rows of the buffered stock effects. Measured under the port, none writes at or above `0x37F00` (highest in the slot: DARK REV `0x37DA2`; `docs/firmware/DSP.md` section 5, `stock.SLOT_EXTENT`). A module with no declared range (SEND) still refuses them.
- Removed repeat98's REPITCH module (`modules/repitch/`) and `remixes/test/repitch/`; REPITCH_REPEAT98_KYOTI is the repitch. `remixes/test/mods` no longer carries a repitch. `docs/firmware/REPITCH.md` (stock facts) and the `verify_repitch*` fixtures stay.
- Build: a selected module whose menu entry is `stock_dsp` keeps the stock effect it replaces out of the harvest (`stock.harvested`). SIDECHAIN_COMPRESSOR with COMPRESSOR on neither chooser wrote over its own `scdet` hook and the build refused. No existing remix changes (refhash 24/24; `sidechain-compressor` and `kyoti-mute-sidechain` list COMPRESSOR and build identical).
- BRAIN: TOOLS > MIDI MONITOR (the last three messages, live) and TOOLS > LOAD (the frame interrupt's share, live; FUNC + LEVEL push on an MKII); LOAD METER (new) measures it (11 Oct, port: `verify_brain`).
- BRAIN: SETTINGS list (PROJ, BRAIN, SETTINGS) with card-stored settings, a run-time value table and `remix.brain.read_macro` for modules; MIDI LOG and DEFAULTS are BRAIN's first two settings. Measured under the port only.
- BRAIN: project pair (`brain.work`/`brain.strd` in the project folder), the project record written at SAVE PROJECT and compared at each load, TOOLS > PROJECT CHECK. Measured under the port only.
- Analog BD: engine selection now lives only in the pool-style browser; the
  former SRC SETUP MODEL control and its encoder editing path are removed.
  Both source outputs are 12.04 dB louder than the 29 September revision,
  with matching default hit energy (within 0.03 dB over 500 ms) and default
  peaks of −7.31/−1.59 dBFS for 808/909. The post-desk gains preserve every
  internal state; 909 overloads limit at full scale. The 808 uses the same
  three output instructions; the 909 adds four instructions per sample.

Remixes
- `remixes/test/rec-threshold`: REC THRESHOLD on the stock effects (11-14 Oct, THR1 to THR9 above).
- `remixes/test/brain`: bottleservice + BRAIN (7 Oct, port only).
- Every remix that carried a USB AUDIO OUT or IN variant selects USB AUDIO OUT / USB AUDIO IN and pins LAYOUT / INPUTS; each image byte-identical to before (6 Oct, `make identity`).
- KITS replaces OCTAKIT, SCENES KITS, SCENES P2 KITS and KITS RELOAD in bottleservice, ok-ms, mods and character-txtr; mods also carries DIRECT_JUMP_KYOTI and RELOAD_FROM_PROJECT; `remixes/test/octakit` removed, `remixes/test/kits` added (6 Oct, port only).
- `usb-out-tracks-post`: stock + USB MIDI + USB AUDIO OUT TRACKS POST (5 Oct).
- bottleservice takes the computer's stereo output onto inputs C/D (USB AUDIO IN CD + USB CROSSBAR); USB AUDIO OUT MASTER polls every 250 µs (28 Sep). Both IN modules out again on 4 Oct (#575, image A0 below).
- bottleservice keeps the stock DELAY's FX2 chooser row; `BUILD` tags past 99 are a letter and a digit (`A0` = 100) (4 Oct, #576).
- `stems`: STEM REC on the stock effects; STEMS1 listed STEM REC alone and drew a one-row FX2 chooser (1 Oct).
- Twelve `usb-io-<out>-<in>` test remixes and `usb-out-main`; USB remixes named by direction (`usb-full` → `usb-out-tracks`, `usb-lean` → `usb-out-tracks-main-cue`, `usb-master` → `usb-out-master`, `usb-mc` → `usb-out-main-cue`) (28 Sep).
- `remixes/test/` holds the one-module carriers; `mods` moved there, `restock` removed (28–30 Sep).
- `octatrick` carries SYNTH MACHINE, SCALE QUANTIZER, DIRECT JUMP, TUNER, USB MIDI, USB AUDIO OUT TRACKS MAIN CUE and USB AUDIO IN ABCD + USB CROSSBAR on the stock effects less SPATIALIZER (its payload-A words hold the IN inject); `octatrick-usb` folded into it and removed (Tim Hastie, 29 Sep, #526).
- `remixes/test/scenes-midisc`: MIDI SCENES + KITS + SCENES P2 + PLOCKS P2 on the stock effects (10 Oct, port only).
- bottleservice carries PLOCKS P2 (3 Oct, #555).
- Removed: `bamsep26` (bottleservice is its superset), `mutables`, `nimbus`, `hello`, `hello-dram` (27 Sep).

Modules
- SCENES P2: page-2 scene locks move from the 144-byte pool at Part `+0x17a2` (stock's LFO designs of MIDI tracks 2–8) to bytes 30 and 31 of the stock scene block, eight a scene; stock scene copy, paste, undo and clear carry them; builds beside MIDI SCENES. Locks saved by earlier images are not read (10 Oct, port only).
- STEM REC: MAIN MENU > STEMS records every track to the card while the sequencer plays, one 16-bit stereo file per track, streamed, up to 60 min (Yves Rosius, 26-30 Sep).
- STEM REC, piece 5: every track after its fader (its share of MAIN, from core 0's own gain arithmetic redone in the frame hook), MAIN, CUE and the inputs AB/CD as sources (stereo or mono), 24-bit files, an 8 MiB ring; the menu's labels keep moving when the card falls behind (Yves Rosius, 1-4 Oct).
- BRAIN (new): the settings store on the unit (`docs/proposals/BRAIN.md`): card-wide knob defaults from `BRAIN/card.work` at each project load (MODE views through MODE DEFAULTS), SAVE AS DEFAULT and CLEAR DEFAULT in a BRAIN MAIN MENU category as engine-task jobs, `card.strd` at SAVE PROJECT (6-7 Oct, port: `verify_brain`).
- USB AUDIO OUT (LAYOUT) and USB AUDIO IN (INPUTS) replace the five `usb-audio-out-*` and three `usb-audio-in-*` modules: a build-time setting chooses the code (`Module.variant`) (6 Oct); USB AUDIO OUT TRACKS POST became its sixth LAYOUT (8 Oct).
- BRAIN: WRITE DEBUG LOG writes the last 256 MIDI messages, each with the sync flags and the playing and next pattern after its handler ran, to `/BRAIN/debug.txt` (7 Oct, image B1).
- REMIX SWITCH (sanderlegit's OS SWITCH, PR #542, renamed): MAIN MENU > BRAIN > REMIXES lists the `.RMX` images in `/BRAIN/REMIXES/`, each named `<REMIX> <BUILD>`, and boots one without writing the flash; every remix with BRAIN carries it; PR #542's power-on picker is left out. Its DSP park sits in stock's dead interrupt vectors (`DspSection.pins`, `verify_dspvectors`), its chainloader in octabam's loader (`Linked.loader`). BOOT TRACE (sanderlegit) is its boot-stage probe. `make rmx`, `make rmx-stock`; `make image` writes the `.RMX` (8 Oct, port: `verify_remixswitch`; on an MKII as OS SWITCH, its own category, 29-30 Sep; under BRAIN as image B2, a switch on an MKII, 8 Oct).
- BRAIN: the page shortcut (hold a page key + FUNC: SAVE AS DEFAULT, CLEAR DEFAULT, SAVE/LOAD/DELETE TEMPLATE over the page), FX templates as records in `card.work` applied through the stock writers, and a boot screen (a brain over OCTABAM, PIRATE FLAG's frame hook) (10 Oct, port: `verify_brain`).
- BRAIN's pane: DEFAULTS, REMIXES and TOOLS sub-lists, each a row array BRAIN's list descriptor is repointed at (the stock menu engine has two levels) (8 Oct).
- KITS (new): 256 Kits per project through the stock Part slots: each pattern's Kit is copied into a slot nothing plays before the pattern is scheduled; LOAD/SAVE KIT on the stock list menu with Octakit's key map, UNDO KIT, list copy/paste/clear/undo, AUTOSAVE and KEEP LEVELS, the pattern clipboard carrying the Kit, FUNC+PASTE+PART, PTN+FUNC+RIGHT, PTN+FUNC+TRIG; kits.work/kits.strd, migration of the stock Parts, import of Octakit's kits3a/b.work; no `illegal` (6 Oct, port: `verify_kits`, 89 checks; on the unit in image A6).
- OCTAKIT, SCENES KITS, SCENES P2 KITS, KITS RELOAD removed, with the build's Runtime/ArenaReserve machinery (every other remix's image and report bit-identical; refhash 24/24); TEMPO BUS and MODE DEFAULTS no longer push Octakit's token (6 Oct).
- USB AUDIO OUT TRACKS POST: the sixteen track channels after each track's own MAIN gain (LEVEL, mute, solo, XLV, core 0's 16-sample ramp; MAIN_LEVEL left out), `USB_LAYOUT = 5` of the shared source; every other layout byte-identical (5 Oct; on a MKII as P3, below; streaming cost +2.8 µs a frame over OUT TRACKS on the unit, the no-host cost not measured; MASTER TRACK checked under the port only).
- OCTAKIT: patch 0002, a track button within ~250 ms of a queued pattern change ran her Part-refresh writer into its context fatal (BUSY during the handoff; ems-octakit#5's setting); on BUSY the writer now runs stock unwrapped (5 Oct, port-measured).
- USB AUDIO OUT (every layout): the producer runs only while the host asks for the stream, with the 64-slot start cushion zeroed at the first produced block (5 Oct, port only); Bryan T measured the always-on producer at 13–25 µs of frame interrupt per frame with no host.
- USB AUDIO IN (AB, CD, ABCD): the per-frame transfer to core 0 stops once a block with word 0 = 0 has landed while the stream is closed (5 Oct, port only).
- USB AUDIO IN AB / CD / ABCD: host channels onto the inputs, the inject a placed DSP section behind a ledger-checked hook (`schema.DspHook`) (28 Sep).
- USB CROSSBAR: the SCM/XBS setting that cured lost packet tails, written at USB controller init (28 Sep).
- USB AUDIO OUT MAIN: MAIN L/R alone every 250 µs (28 Sep).
- USB AUDIO OUT TRACKS MAIN CUE writes MAIN/CUE one block behind the tracks' slot; `verify_usb_align` reads 0 lag under the port (28 Sep).
- USB AUDIO OUT: consumer anchored at the host's first EP3 IN poll (28 Sep, #514); proportional servo, targets 64/96 frames, ~3.6 ms round trip (Bryan T, 30 Sep, #518).
- USB AUDIO OUT TRACKS MAIN CUE / OUT MAIN CUE: CUE written two blocks later while MASTER TRACK is on, where the mixdown's master path had it 32 samples ahead of MAIN (Bryan T, 29 Sep, #533).
- CC FEEDBACK: the OT transmits a CC for every live knob byte that changes, page 1 as CC 16-45, page 2 as 62-73 (28 Sep).
- SCENES P2: the page-2 editor-entry detours displace eight bytes; at twelve every page-2 turn under Octakit halted (28 Sep, port).
- Character: KEY (SELF / T1) and KLVL on page 2, the compressor keyed from T1's level (29 Sep, #521); 355 → 241 static cycles/sample, bit-identical (27 Sep).
- Spectrum: MODE is LADR SEM ISO VOWL; SEM's SHPE sweeps LP → BP → HP; saved parts: `ot_project.py remap-slot <project> SPECTRUM MODE 2:1,3:2,4:3` (27 Sep).
- BusVerb: tank loop stores each line's output into its Hadamard slot through r4, 1,090 → 1,064 static cycles/sample, bit-identical (commit `7e0a236a`, `modules/busverb/README.md`; 5 Oct).
- FX2 LOCK: the FX2 chooser cannot change a track's effect; YES's key-table entry points at NO's handler (bottleservice; 4 Oct, #579; image A1).
- Character, Spectrum: the per-block decode is skipped for inactive modes; the static per-sample cycle count is unchanged (5 Oct, #607).
- BusVerb: wet feedback limiter at −2 dBFS (0 railed samples at a 0 dBFS send, was 7,463 / 11,762); slot pass and parallel-move folding, 1,166 → 1,090 static cycles/sample (27 Sep).
- Modulation: LINE 404 → 354, PHSR 394 → 298, COMB 339 → 329 words/sample; four beside the reverb priced inside the budget (27 Sep).
- PLOCKS P2: parameter locks on FX1/FX2 page 2, held trigs + a knob on the SETUP page; trig and pattern operations carry them, `p2lkNN.work` / `.strd` save them, a sparse copy in CS1 keeps the current bank's over a power-off (2–3 Oct, #549, #550, port-gated). `ot_emu --cs1-in` / `--no-post` model a power cycle (#550).
- CF METER: ColdFire frame-interrupt and idle time read out as audio on T8 (probe, 27 Sep).
- Removed: WarpFold, Ripple, Rungs, Streamz, BodeShift, NIMBUS, HELLO WORLD, HELLO DRAM; their FX2 ids return to stock's entries (27 Sep).
- Octatrick 2.9: `timhastie/octatrick-modules` `v9.1` → `v2.9` (`525f4b1`): MIDI IN, chord recording with inversions, LEG modes, sample-track glide, step transpose, SCALE / GLIDE in battery RAM (2.8); ROOT, the quantizer as a DRAM unit (ROM 3,319 → 243 B), FINE 0c on a new synth track, no limiter, the engine owns the AMP envelope, `po_retrig`, the index ramp (2.9). TUNER added: UP + TEMPO, one DRAM unit, three detours (Tim Hastie, 29 Sep, #526).
- RECORDER LOOP FIX: FLEX SEEK BIND, FLEX SEEK BIND CTR, RECORDER SPACING and RECORDER HOLD merged into one module, every cave's bytes and placement unchanged (`mods` and `sos-capture` images byte-identical) (4 Oct).
- RECORDER HOLD: two caves on the copies' cap at END, the zero after a second transport start or a recorder reallocation (4 Oct, #564; on Bryan T's unit, sos-capture BUILD=95).
- Not in any flashed remix: RLEN PLEN (26 Sep, port-gated); MIDI SCENES re-pinned to 1.40MIDISC8.2 (25 Sep).

Gates and tools
- `make check` is `check-shared` + `check-remix`; manifests name their gates (`schema.Gate`) and dear settings (`Module.dear`); no default remix (27 Sep).
- `make accept REMIXES=...` runs the shared half once; `JOBS=n` over shard worktrees (`check_shards.py`); `pressure.py render --jobs` (28 Sep).
- `make reach` places a change by its dependency graph (28 Sep), is quick by default with `FULL=1` manual (29 Sep), and leaves out `remixes/test/` unless `TESTS=1` (30 Sep).
- Build memo under `out/cache/` keyed by input sha256; bottleservice 9 s cold, 1.7 s warm, byte-identical (28 Sep).
- Port: LOAD PROJECT runs until the engine is idle, ATA latency 8 samples (28 Sep); follows a detoured idle park (28 Sep); `--step`, `--live-script`, `--midi-out` (28 Sep); `--scenario` forks one child per run from one load, DSP memory unshared per child (29 Sep).
- Shards: image-stage gates on their own shard, long-pole remixes split into gate jobs; the cover 681 s → 530 s (29 Sep).
- Tape Echo probe: glibc `random()` vectors on every host, oracle built `-fwrapv` (27 Sep).
- `tools/verify/verify_usb_post.py` (USB AUDIO OUT TRACKS POST's stems against core 0's MAIN under the port, on the tone project) and `tools/harness/usb_post_model.py` (5 Oct).
- `tools/hw/bcr2000.py` (28 Sep), `tools/hw/usb_probe.py` (Bryan T, 28 Sep), `tools/harness/usb_align.py` (28 Sep), `tools/ghidra` (roblg, #483, 28 Sep).
- `verify_docs` exempts the dated plans and specs under `docs/superpowers/`, records like this file (1 Oct).
- `verify_docs` checks every relative Markdown link; the remixer TUI draws again (30 Sep).
- `Formatter.PLAIN` zeroes a clone's formatter words on any module, not only one with a stepped slot (5 Oct); refhash 24/24 bit-identical, no shipping module changed.

Docs
- `docs/guide/` (BUILDING, REMIXER) and `docs/contributing/` (MODULES, PLACEMENT, TESTING, TOOLING, FAILURE_MODES cut to Seen / Cause / Fix / Check); tool docs beside the tools (30 Sep).
- `docs/contributing/TESTING.md`: every gate, how to write one, what it costs (29 Sep).
- ColdFire load on a unit: Bryan T's CF METER takes (4 Oct; `docs/firmware/ARCHITECTURE.md` section 6): ~16.5 µs per playing voice at CPI ~4.4 against the port, no first-voice premium (the morning's +37 µs retracted the same evening), the USB stack ~14 µs idle / ~25 µs playing, no crossbar contention; OUT TRACKS MAIN CUE costs 27–50 µs of frame interrupt over OUT MAIN CUE, most of it with no host connected; TSTR and the stock DELAY not measurable; interrupt levels from the ICR writes in `KERNEL.md`.
- Removed: `PLAN.md`, `docs/TIMESTRETCH_PIPELINE.md` (27 Sep).
- Demand loader (`modules/dlpump`, `modules/dlcopy`, `modules/dlprobe`; `docs/proposals/DEMAND_LOAD.md`): `octabam` copies SPECTRUM, CHARACTER, MODULATION and TRANSIENT into the DSP's shared window while a track uses them and withdraws them 10 s after the last use. All 14 stock effects stay; the stock reverbs run behind a guard that keeps them off loaded code. A block is held by whoever has it first: the FX1 and FX2 choosers refuse an effect whose block is under PLATE, DARK or SPRING REV, and a reverb on the block of a loaded effect a track uses, each with a toast (`NEEDS Tn FX2 FREE`, `Tn HOLDS <effect>`); other routes toast at the next page key. `octabam` lists the stations on FX1 (it offered SPECTRUM and CHARACTER on FX2 only, where they render dry). GATE VERB is not in `octabam`. New builder fields `Remix.window_demand`, `window_guard`, `window_loader`; the build refuses an uploaded window record above `0x37f00`. DLPROBE and `tools/hw/dl_state.py` (USB `0xc0/0x57` block 3) read the counters on a unit. Gates `verify_dlstub`, `verify_dlwrap`, `verify_dlload`, `verify_dlprobe`.

## STEMS11 — 28 Oct 2026 (local remix `lm-stems`, branch `stems-next`, PR #965)

On the unit (Yves's MKII, flash K): each take wrote its own folder.
Eleven files at 24 bits, every track a Static machine with every trig
filled, ran 49 s with the ring at most 34% full, and no take reached 100%
(his report). The logs hold one eleven-file take, so the peak from take
to take isn't measured on the unit yet. The `.ot`
files hold the take's tempo and +12 dB. `lm-stems` is `octabam` plus STEM
REC and MEMORY, with LOAD METER's refusal of STEM REC lifted in that build
only; it isn't committed (`modules/stems/FLASH.md` flash K).
- STEM REC: a folder for each take, `<set>/AUDIO/!STEMS/<take>/<take>-<source>.wav`; T1 alone at 24 bits at boot.

## STEMS10 — 27 Oct 2026 (local remix `lm-stems`, branch `stems-next`)

On the unit (flash J): twelve takes, "everything looking good". The double
tap armed (`yes gap` 160 to 171 ms), and split pairs wrote `A.wav` to
`D.wav`. With every take's files in one `!STEMS` folder, each take's start
slowed as it filled: eleven files at 24 bits peaked at 36%, 37%, 60% and
89%, then `RING FULL` after 2.9 s with 88 files there.
- STEM REC: STEMS drawn as SYSTEM > PERSONAL SETTINGS (15 rows, a row for each input pair, LEFT and RIGHT pick a checkbox), the folder `!STEMS` (it sorts first), no flicker, the double tap within 0.5 s and the `yes gap` log line (flash I's fixes; STEMS9 never went on the unit).

## STEMS8 — 27 Oct 2026 (`stems`, branch `stems-next`)

On the unit (flash H): the `.ot` files' tempo and gain, and the naming,
were right. Four faults, fixed in STEMS10: `_STEMS` sorted after the
letter folders, a column of pixels flickered each second, BRAIN was
missing (`stems` doesn't carry it), and the double tap of YES didn't arm.
- STEM REC, Yves's six notes of 26 Oct: a `.ot` beside each WAV (the take's tempo, +12 dB), the log in `/BRAIN/STEMS/<take>.TXT`, a flatter folder, a window that redraws itself and no reset on open, a double tap of YES on the main page to arm.

## Images DLPROBEJ1..K1 (26 Oct 2026, `remixes/test/dl-probe` and `dl-probe-any`)

Sam's MKII, one image after another with the project `MXDLPR01` / `MXDLPR02` (DLPROBE on T1's FX1; MODULATION, SPECTRUM, CHARACTER on FX1 or FX2 of other tracks, TRANSIENT on T6's FX2), read over USB (`modules/dlprobe/decode.py`, `tools/hw/dl_state.py`, `tools/hw/load_meter.py`):

- `DLPROBEJ1`: all four effects unbound, received 0.
- `DLPROBEJ3`: the pump ran (the ping word alternated 0 and 1; 4 loads, 180 chunks, 8 doorbells sent); the doorbell word read `0x40a55a` and stayed non-zero (~77,000 frames): the byte above a host word's 16 bits is stale on the unit, and the copier compared the full word. The unit froze once on this image (13:27, cause not found).
- `DLPROBEJ5`: with the doorbell and header masked, all four effects BOUND, every block's sum matched, published equal to received. SPECTRUM and CHARACTER on FX2 cost a dry slot's 116..119 counts (`fx1_only`).
- `DLPROBEJ7`: the stations on FX1. CHARACTER (core A) 5,147 counts a frame, SPECTRUM (core B) 4,062, TRANSIENT (core A, FX2) 3,616, MODULATION (core B) 323, a dry slot 89..147: the code runs, on core A as written by core B.
- `DLPANYJ9` (the pump sends on every frame): blocks refused for their sum (MODULATION received 4, refused 3, published 1; SPECTRUM 2, 2, 0; TRANSIENT 2, 1, 1; CHARACTER received nothing). The ping-0 rule holds on the unit.
- `DLPROBEK0`: with a 2 s grace, a project load withdrew and reloaded all four effects: the ids sit at their defaults for 3.8 s.
- `DLPROBEK1`: the 10 s grace; 4 loads, 0 withdrawals, received 2, refused 0, published 2 per effect, all four running.

## AUTOSAVE1 and AUTOSAVE2 — 15-16 Oct 2026 (`rec-buffer-autosave`, now `buffer-saver`, Chupitnik's builds)

On Chupitnik's MKII, each flashed from the card, under the module's first
name REC BUFFER AUTOSAVE (`make image REMIX=rec-buffer-autosave BUILD=N
VERSION=AUTOSAVEN`). The code is BUFFER SAVER's; the rename changed no
byte of behaviour.
- AUTOSAVE1 (BUILD 1): after a take, FUNC + PROJ asks SAVE SAMPLES?; YES saved the take with the real date and time and assigned it to its buffer; PROJECT > SAVE with two buffers saved both; an immediate re-save did not ask; a reload brought the takes back; NO saved as stock. Fault: PURGE SAMPLES froze the unit. It was not this module: the build moved the purge's end-of-banks compare (`0x400254f8`) with the arena base, in every remix with a DRAM reservation (fixed separately, `tools/remix/arena.py`).
- AUTOSAVE2 (BUILD 2): AUTOSAVE1 plus that arena fix. PURGE SAMPLES finishes ("REMOVED 0 SAMPLES" in that project: PURGE clears unused slots and deletes no card file, as stock); the autosave checks again, all fine (16 Oct).

## THR1 to THR9 — 11-14 Oct 2026 (`rec-threshold`, Chupitnik's builds)

On Chupitnik's MKII, each flashed from the card; the first boot of THR1 ran
1.40C's own BOOTSTRAP UPGRADE. Built from his branch before it was squashed
into this module's commit (`make image REMIX=rec-threshold BUILD=N
VERSION=THRN`, the remix then named `rec-threshold-fixed` for THR1 to THR4).
THR5 is the module's commit; THR6 to THR9 led to the armed indicator and
the faster IN fall.
- THR1: REC THRESHOLD at a fixed −30 dB. THR shows on RECORDING SETUP; armed with TRACK 1 + REC AB, silence never records, the input starts the take, a second press cancels, a drum hit's attack is whole by ear.
- THR2: LEV (−40 to −6 dB) and IN on RECORDING SETUP 2. Both work; the floor too high for quiet sources, IN too jittery.
- THR3: LEV −58 to −7 dB, −40 when TRIG becomes THR; IN holds ~0.5 s and falls ~12 dB/s. The meter right; the range wanted −60 to 0.
- THR4: LEV −60 to 0 dB (4 dB steps to −8, then 2 dB). Working. (Its "armed from inside a recording page it starts only sometimes" is retracted below: GRID RECORDING was on.)
- THR5: after review, a crossing fires at or over LEV and only for a track still on THR with its recorder idle. The THR4 checks again; LEV 0 dB, an ordinary source does not start it; TRIG moved from THR to ONE while armed, the input then records nothing, and the next press records at once as ONE. With RECORDING SETUP 1 or 2 open, TRIG ONE and THR record (12 Oct), as stock 1.40C does on the same unit: the THR1 to THR4 reading that the REC keys record nothing with a page open is retracted (`docs/contributing/FAILURE_MODES.md`); its cause, found 13 Oct, was GRID RECORDING.
- THR6: an armed track's status icon blinks. Armed in silence, track 1's icon blinks; a second press, or the take starting, stops it. Fault: TRIG moved from THR to ONE while armed, the icon keeps blinking. From inside RECORDING SETUP 1 and 2 every TRIG records (12 Oct, retested).
- THR7: the TRIG edit itself drops the arm. From inside RECORDING SETUP 1 the REC keys recorded nothing, TRIG ONE or THR (12 Oct). ❌ Not THR7's code: GRID RECORDING was on. Stock's REC keys do nothing inside RECORDING SETUP while GRID RECORDING is on (`0x460d1736`, with `0x460d5db4 == 3`; `0x400836e4`, `0x40030ed0`); RECORD off, they record (13 Oct, on THR8).
- THR8: the icon renderer drops an arm whose TRIG is no longer THR (THR7's editor hook removed). Recording from inside RECORDING SETUP works with GRID RECORDING off (13 Oct).
- THR9: IN falls ~29 dB/s (was ~12). On the unit, 13 Oct: IN reaches `---` in under 2 s; armed, the icon blinks; TRIG moved to ONE while armed stops the blink and the input records nothing; a take, a cancel, and THR armed inside RECORDING SETUP 1 all as expected.
  14 Oct, THR9's code: several tracks armed at once each start their own take, into their own buffer with their own RLEN.

## STEMS7 — 8 Oct 2026 (`stems` at `92959832`, PR #644)

On the unit (Yves's MKII, flash G): T1 to T8 at 24 bits on a project of
eight Static tracks ran 61 s with `DONE`, the ring at most 21% full;
twelve files at 24 bits stopped with RING FULL after 4.3 s. Every file
whole: MAIN minus the stems' sum is 0 to 7 at every sample
(`docs/firmware/STEM_REC.md` 17.6).
- STEM REC, zero copy: the frame hook writes each file's bytes into the file's own ring through the uncached alias, and the writer hands the card whole sectors straight from the rings; `STATS.TXT` gives the card's time while recording and while saving.

## STEMS5 — 8 Oct 2026 (`stems` at `19a3a113`)

On the unit (flash E): the same eight tracks at 24 bits ran 18 s before
RING FULL; six tracks and fewer at 24 bits, and eight at 16 bits, held.
`STATS.TXT` showed the writer waiting for the processor (STEM_REC.md 17.5).
- STEM REC: every sample in its file's byte order, the writer's copy in whole longs; `STATS.TXT` adds the copy's fastest frame and the card's fastest write.

## STEMS4 — 8 Oct 2026 (`stems` at `ad73ee89`)

On the unit (flash D): T1 to T8 at 24 bits on a project of eight Static
tracks stopped with RING FULL after 6.75 s, every file whole; the first
`STATS.TXT` put the limit in the writer's copy (STEM_REC.md 17.4).
- STEM REC, the perf round: a lighter frame hook (staged a frame early, no limit where it can't act, the mirror's EMAC only on a multiply), `STATS.TXT` in each take's folder, T8 shown as `T8 MASTER` and left out of a take while MASTER TRACK is on.

## L1, C1 and C2 — 7 Oct 2026 (`usb-out-tracks-main-cue`, `cfmeter-tracks`, `cfmeter-post`, allmyfriendsaresynths's builds for #625)

On allmyfriendsaresynths's (@clickysteve) MKII, built on main `6f9e5bc9`.
- L1 (`usb-out-tracks-main-cue`): MAIN against T1 by `tools/hw/usb_offset.py`, three takes with the USB cable replugged between them: 0 samples on all 30 clicks, both sides.
- C1 (`cfmeter-tracks`) and C2 (`cfmeter-post`), the same project loaded fresh on each, three 8 s streaming takes: frame interrupt 238.2 µs and 241.0 µs (balanced means), POST +2.8 µs; TUE/ROE 0. No-host takes not run.

## STEMS3 — 6 Oct 2026 (`stems` at `fc7baad`)

On the unit (Yves's MKII, reported 6 Oct): T1 to T8 record from Static and
THRU machines, and so do MAIN and AB in stereo. A stem follows its track's
LEVEL, AMP VOL, and BAL. On a light project, eleven stereo files peaked the
ring at 10% at 16 bits and 13 to 16% at 24 bits. On a busy project at 24
bits the ring filled: RING FULL, and the files saved, cut where it filled
(open; `docs/firmware/STEM_REC.md` section 17.3).
- STEM REC, piece 5: every track after its fader, MAIN, CUE and the inputs, 24 bits, the 8 MiB ring.

## Image A6 (106) — 6 Oct 2026 (`bottleservice` at `e2e1d60f`)

On the unit (Sam's MKII): KITS in place of Octakit, main `36a056c5` (#627)
plus gate-only changes. No halt in the import of Bottleservice 2026's
Octakit Kits, ems-octakit #5's chain and track-button sequence, STOP /
PTN+TRIG / PLAY with the Rytm as master (A5's halt), PROJECT STRAND's
rejected bank file (A4's halt), power cycles saved and unsaved, SAVE
PROJECT, SAVE KIT, quick save, UNDO KIT, FUNC+CUE (`modules/kits/README.md`
"On the unit"). Not run: an unattended BCR2000 run.
## P3 and P2 — 5 Oct 2026 (`usb-out-tracks-post`, allmyfriendsaresynths's builds)

On allmyfriendsaresynths's (@clickysteve) MKII.
- P3 (`usb-out-tracks-post` from this change's source; `OCTATRACK_OCTABAMP3.bin`
  SHA-256 `85333db1…09a4`): smoke test. Boots and runs normally; the host
  sees sixteen channels, each track on its own pair; LEVEL, mute/unmute,
  solo and the scene/crossfader level follow in the stems; no instability
  or audio fault heard.
- P2 (a 20-channel diagnostic build, not in the tree: these sixteen stems
  plus MAIN and CUE): a 196 s take nulled the stems against MAIN, 99.995%
  of ~17.3 M samples within 0..7 LSB, no gain/block misalignment at
  ~16,700 level edges (`modules/usb-audio-out/README.md`, TRACKS POST).
- Not run on a unit: MASTER TRACK, CF METER, a soak.

## sos-capture BUILD=94 and BUILD=95 — 3 Oct 2026 (Bryan T's builds)

On Bryan T's MKII, the sound-on-sound loop (SOSCAP: T1 FLEX on R1, PLAY +
REC1 + REC3 with SRC3 = T1 on step 1, 128 BPM, RLEN 16, 24-bit recorders)
captured sample-exact over USB AUDIO OUT TRACKS.
- BUILD=94 (`f6ce41d6`, three hold caves): in steady state every long-pass
  wrap is an exact repeat; after a recorder reallocation every long-pass
  wrap is one sample of zero, for the whole take (two reallocations).
- BUILD=95 (`cd017851`, PR #564, five hold caves): no zero in any take
  (16 → 24-bit reallocation, 24-bit off/on + reload, STOP/PLAY three times,
  steady state, RLEN 4 trigs 1/5/9/13 after a reallocation); 120 BPM has no
  event at any wrap. Every 128 / RLEN 16 wrap is a repeat (lag 82,687 →
  82,688) or a skip (82,688 → 82,687). Real audio at 128 / RLEN 16 and
  224 / RLEN 4: no audible loop point.
- Not run: STOP/PLAY on BUILD=94. The repeated sample is recorded into the
  buffer and replays until the next pair (RLEN 4: 35.2 % of tone rms at the
  stored seam, 18.8 % at the skip).

## Image A4 (104) — 5 Oct 2026

Entry built from the citing documents; the commit the image was built
from is not recorded in the tree. On the unit (Sam's MKII), per
`modules/octakit/README.md` ("Patches on her runtime") and
`docs/contributing/FAILURE_MODES.md` (the Octakit stranded-session entry):
the rejected `bank01.work` staged as `PROJECT STRAND`; the load reports
PARSE ERROR, then PLAY halts at
`gk_stock_audio_pattern_primary_begin_report_fatal` (VEC:04, D0 = −1). The
patch `modules/octakit/patches/0001-banks-load-error-applies-current-bank.patch`
(#595, merged 5 Oct) is the one those two documents describe on the unit;
the other contents of A4 are not stated.

## Image A3 (103) — 4 Oct 2026

Entry built from `modules/cc-feedback/README.md` ("On the unit") and
`docs/contributing/FAILURE_MODES.md` (the BCR2000 entry). CC FEEDBACK
paced to one message per UI tick (#584, commit `41765855`); the cc-feedback
README names A3 as the image that carried it. The BCR2000 dark/deaf cases
(A02, B1) were seen on images A0-A3 and attributed to the OT's Program
Change on pattern change (PROG CH SEND), not to this module.

## Image A2 (102) — 4 Oct 2026

Entry built from `modules/cc-feedback/README.md` and
`modules/cc-feedback/cc_feedback.s`. CC FEEDBACK sweeping the Part's knob
bytes, unpaced (#583, commit `f87bc580`). On Sam's MKII with a BCR2000: no
stream while B1 played untouched (a Midihub export held only the knob
turns, CC 22 and CC 46); the BCR2000 locked up the moment the bank changed,
on a dump of up to 336 messages in about a second.

## Image A1 (101) — 4 Oct 2026

Entry built from `remixes/bottleservice/remix.py` and
`modules/cc-feedback/cc_feedback.s`. bottleservice with FX2 LOCK (#579,
commit `dc1d2938`, 18:16 on 4 Oct) and CC FEEDBACK's lane-watching sweep.
On Sam's MKII, with a Midihub capture of the OT's output: the sweep
streamed 60 CCs a second on a pattern with locks on two of T1's knobs until
the BCR2000 locked up, each CC went out twice (AMP and LFO blocks swapped
in the map), and the lane rewrites overwrote incoming CCs
(`modules/cc-feedback/README.md`, "On the unit"). FX2 LOCK itself: the
cited documents record no hardware result for it.

## Image A0 (100) — 4 Oct 2026 (`bottleservice` at `feb52f5f`)

On the unit (Sam's MKII): boots into a re-hosted project, pattern paste
works. bottleservice less USB AUDIO IN CD and USB CROSSBAR; the stock
DELAY in the FX2 chooser (SEND, DELAY); PLOCKS P2, Octakit, the rig.
- Images 95–99 (3–4 Oct, same remix with the two USB IN modules): PLAY
  halted with a computer on USB (image 97); on image 99 the unit wrote a
  bank file short one 64-byte burst with the card's MBR in its place, the
  firmware rejected it on every later boot, and Octakit stayed stranded
  QUIESCED for the session (silent songs, a halt on pattern paste) --
  `docs/contributing/FAILURE_MODES.md`, the two Octakit entries.
- The stranded-load path in Octakit is open (a failed stock bank load has
  no recovery); the bad project stays off the unit.

## Image 93 — 3 Oct 2026 (`wave` at `e90912d9`)

On the unit (Sam's MKII): WAVE, a 4-voice wavetable synth on FX2 (ported
from CHOMPI Club's WAVE firmware, MIT), played by WAVCAR.wav on a FLEX track with loop
on. It plays; PTCH and the CHROMATIC keys move the pitch; with AMP REL at
INF the note holds until the AMP envelope ends it. DSP headroom not
measured.
- The remix: WAVE + SCALE QUANTIZER + CC MAP + SCENES P2 + PLOCKS P2 + USB MIDI + USB AUDIO OUT TRACKS MAIN CUE; the stock effects less DARK REV and SPRING REV.
- The carrier goes in the set's audio pool (`<set>/AUDIO/`), not the card root's `AUDIO`.

## Image 92 — 3 Oct 2026 (`waveload` at `d99fa690`)

On the unit (Sam's MKII), CF METER's first readings; T8 FX2 = CF Meter,
read over USB channels 15/16, a fresh project with samples on tracks 1–4:

| state | idle | frame interrupt mean | longest | period |
|---|---|---|---|---|
| stopped, BURN 0 | 49.6 % | 123.1 µs | 208.2 µs | 362.8 µs |
| playing, BURN 0 | 28.0 % | 213.5 µs | 272.7 µs | 362.8 µs |
| playing, BURN 1 (one 4-voice WAVE LOAD engine) | 10.9 % | 282.7 µs | 329.5 µs | 362.8 µs |

One 4-voice engine: +69.2 µs a frame; tracks 1–4 played clean at
BURN 1. BURN 2 not tried (predicted mean ~352 µs, longest ~400 µs).
Sam's bottleservice project squealed on PLAY on this image before CF Meter was
selected; a fresh project did not (cause not measured).
- The remix: stock effects + USB MIDI + USB AUDIO OUT TRACKS MAIN CUE + CF METER + CF METER IDLE + WAVE LOAD.

## STEMS2 — 1 Oct 2026 (`stems` at `d646e83`)

On the unit (Yves's MKII): it flashed, and FX2's page shows the stock
effects again. The first boot played audio. A stem doesn't follow its
track's LEVEL, as designed so far (`docs/firmware/STEM_REC.md` section 17.2).
- The remix: STEM REC on the 14 stock effects; STEM REC's code is STEMS1's.

## STEMS1 — 30 Sep 2026 (`stems` at `4ec1276`)

On the unit (Yves's MKII): T1 alone, then T1-T8 for about two minutes, every
take whole; stopping the sequencer ended the take; every file plays. The first
boot had no audio until a power cycle (open). FX2's chooser had one row. The
stems sit about 12 dB under normal playback, by ear
(`docs/firmware/STEM_REC.md` section 17.1).
- The remix: STEM REC alone. MAIN MENU > STEMS: REC, a status row, T1-T8, PEAK.

## Image 88 — 27 Sep 2026 (`bottleservice` at `d6867bd`)

On the unit (Sam's MKII): load, play; a fourth MODULATION beside the
reverb overran the DSP, three fit. Which of TEMPO BUS, SCENES P2, CC MAP,
RIG HOSTS, the tokened Octakit writer and USB AUDIO were exercised is not
recorded.
- The remix: the delay and reverb bus (BusDelay on T1's FX2, BusVerb on T5's FX2, SEND on every other track's FX2, the stock DELAY on T8) + SPECTRUM, CHARACTER and MODULATION on FX1 + USB MIDI + USB AUDIO OUT MASTER (1 ms poll) + Octakit; TEMPO BUS and MODE DEFAULTS push Octakit's page-1 writer token.
- SEND is two knobs, DEL (slot 0) and REV (slot 1); BusVerb's DLY (page-2 slot 10) sets the delay→reverb chain.
- The host pages draw DEL / REV only (T1 BusDelay, T5 BusVerb); TIME on page-2 slot 11; every other engine knob is on the TEMPO window. Older projects: `ot_project.py migrate-hosts`, then stamp.
- Per-sample ramps on every continuous DSP knob (`make verify-knobs`: 55 of 134 cases stepped per block, 0 after); BusVerb SHFT six intervals (−12, +5, +7, +12, +19, +24).
- The DSP loops pointer-addressed (Spectrum, Character, Modulation, BusVerb, BusDelay, 22–23 Sep); Spectrum SEM with SHPE; Character DRV +12 dB of drive at 127; LADR RES makeup.
- SCENES P2 (twelve-byte detours), CC MAP, RIG HOSTS in its image-53 form.

## usbin-test builds 12–16 and OCTABAM94 — 26–27 Sep 2026 (Bryan T's PR #495 branch)

On the unit: Bryan T's MKII, about 5 million packets, underruns and
overruns 0 after the crossbar setting, DISK MODE in and out with the stream
back. nordseele's MKI (`OCTABAM94`, the same build): enumerated, lit input A
from host channel 1; CoreAudio restarted the IO context hundreds of times,
playback at about half speed.
- USB AUDIO OUT / IN: four host channels into inputs A-D, the inject poked into SPATIALIZER's words; the SCM/XBS crossbar setting at stream-up.

## OCTATRICK9 — 26 Sep 2026 (`octatrick-usb`, Tim Hastie's build)

On the unit (Tim's MKI): the synth, the quantizer and direct jump work; USB
audio on all 20 channels, the first MKI run of the stream. MAIN/CUE silent
until a full power-off after the OS upgrade.
- SYNTH MACHINE, SCALE QUANTIZER, DIRECT JUMP (timhastie/octatrick-modules v9) + USB MIDI + USB AUDIO.

## Image 90 — 25 Sep 2026 (`usb-lean`, Bryan T's build)

On the unit (Bryan T's MKII): MAIN on channels 17-18, CUE on 19-20, levels
follow. MAIN lags the tracks (heard; one block under the port).
- USB AUDIO: 20 channels at high speed, the 16 tracks then MAIN L/R and CUE L/R; 80-byte ring slot.

## Image 69 — 25 Sep 2026 (`usb-audio`)

On the unit (Sam's MKII): 16 channels at 24 bits, every channel its track's
tone; 3 minutes (USBSIG 60 s, USBLOAD 120 s) without a discontinuity after
0.76 s; 0 underruns, 0 overruns. The start-of-stream reorder is still
present, right channel only (`docs/contributing/FAILURE_MODES.md`).
- USB AUDIO: 24-bit samples in 4-byte subslots, 250 µs poll, four packets queued, DMA structures through the uncached alias.

## Image 64 — 25 Sep 2026 (`usb-audio`)

On the unit (Sam's MKII): enumerates as a 16-channel 44.1 kHz input and a
MIDI port at high speed; every channel carries its track; 9.6 minutes over
four takes with zero discontinuities after the first 1.6 s; a 180 s take
on the USBLOAD project (locks every step at 200 BPM, 7,950 USB-MIDI msg/s
in) clean; counters 0 underruns, 0 overruns. Open: reordered samples in the
first 1.5 s of most streams. octemu's own image (65) never installed its
audio function on this MKII.
- USB MIDI (class-compliant, mirroring DIN) and USB AUDIO (UAC2, 16 channels post-FX pre-fader), markandrus/octemu's work on the DRAM platform.
- USB AUDIO's counters over a vendor control request (`tools/hw/usb_counters.py`).

## Image 43, second (BUILD=43) — 25 Sep 2026 (branch `padfix`, PR #408)

On the unit: a 10-minute take, 0 frames of junk on main R (baseline 5).
- BusDelay: 8,192 NOPs after the sample loop, before the rts (two samples, 11 % of core 1's frame), so the ColdFire's pull of core 1's read-back finishes before the dispatcher's copy.

## Images 55–108 and 19–42 — 22–25 Sep 2026 (probe and diagnostic builds)

On the unit, by series:
- 55–63 (22 Sep, PROBE builds, branch `probe55`): DSP core clock 199.9 MHz, 4,532 cycles a sample; a register or pointer move 2.00 cycles, a one-word displaced move 3.98, a two-word 6.01.
- 58–66 (22–23 Sep): a click once per block while a level knob moved; the per-sample level ramps of 23 Sep are the fix.
- 81–99 (23–24 Sep, branches `diag91`..`diag98`, `core1scratch99`, `nolock94`, `fix97`): the reverb host's bursts need the delay's DSP code past its preamble (95 and 96 read 0 in 12 minutes); cause open (`docs/contributing/FAILURE_MODES.md`).
- 100–108 (BUILD=10..18) and 19–42 (24–25 Sep): the junk on main R bisected to the read-back pull; 37 and 38 (DMA guards) and 39–42 (a frame-end detour; 39 wedged) did not fix it.

## Image 52 — 22 Sep 2026 (`bamsep26`)

On the unit: a new project hosts BusDelay on T1, BusVerb on T5, the stock
DELAY on T8. Spectrum (FILTER's id) came up with FILTER's page bytes, muted,
quiet and modulated until re-selected; the engines had the stock DELAY's
page bytes (image 53 fixes both, measured under the port, not flashed).
- BusVerb and BusDelay hidden from the FX2 chooser (one row, SEND).
- RIG HOSTS: a detour at `0x40005688` writes the FX2 id by track; `ot_project.py host <project>` for older projects.
- From image 51 (not recorded on the unit): the engines locked to T1 and T5 (a dry pass elsewhere), the stock DELAY row out of the chooser; Character's TXTR removed after a squeal on the master, WDTH in its slot.

## Image 50 — 22 Sep 2026 (probe, branch `probe50`)

On the unit: the dispatcher's call pattern matches stock's on a fresh
project; every tested configuration clean on a fresh project. The THRU-host
wash of images 40–49 reproduced only in project OCTABAM91.

## Image 49 — 22 Sep 2026 (`bamsep26`)

On the unit: the THRU-host wash in project OCTABAM91, as on 40–48.
- Eight accumulator buffers (`Y:0x901..0x980`) and eight chain buffers (`Y:0x9d8..0xa57`); a server reads three back, the housekeeper clears two on; a core-1 client counts its own blocks from a seed read at init.
- Bus latency 48 samples (32 before); BusVerb's SEND field `0x941` → `0x981`.

## Image 48 — 21 Sep 2026 (`bamsep26`)

On the unit: the THRU-host wash in project OCTABAM91, as on 40–47.
- SEND returns at proc entry on an FX1 r7 (`0x6100/0x6400/0x6700/0x6a00`): FX1 NONE is id 0 = SEND, which had run on every empty FX1 slot.
- The tracker's self-check of images 44–46 removed.

## Image 47 — 21 Sep 2026 (probe, branch `probe47`)

On the unit: a marker tone on a wiped stamp sounded on every block of plain
play: the core-1 tracker one step ahead.

## Image 46 — 21 Sep 2026 (`bamsep26`)

On the unit: played; static and the wash on a T2 THRU host; audio in the bus
with every SEND at 0.
- The tracker's check masks the client's last write offset (`and #>$30`) before it becomes an address.

## Image 45 — 21 Sep 2026 (`bamsep26`)

On the unit: sequencer stuck on step 1 at the first play.
- The stamp clear with post-increment stores (`move a,y:(r3)+`).

## Image 44 — 21 Sep 2026 (`bamsep26`)

On the unit: sequencer stuck on step 1 at the first play (one-word displaced
Y stores, a form no stock site runs; inferred).
- The core-1 rotation tracker heals a lead of one within a frame (stamps in the cleared buffers, a hold flag).

## Analog BD1 — MK1 audition reported 28 Sep 2026

- `OCTATRACK_ANALOGBD1.bin`, SHA256
  `3672634dedb8ce0138d7cf4216bd051a47afac6601dcd2a3c1830def24f39704`.
  mathgonzlez reported that every parameter worked and tweaking caused no
  glitches or unexpected sounds; parameter labels were close to the area edge.
- This is the earlier standalone Analog BD image. The later engine browser,
  horizontal navigation and eight-track admission were not in this report.
  Save/reload, eight simultaneous voices and every FX combination remain
  outside its reported coverage. See `modules/analog-bassdrum/README.md`.


## Image 43 — 21 Sep 2026 (`OCTABAM43`, bamsep26 at `b3f6471`)

On the unit: the sample-host wash gone (T3 STATIC, a trig every step, eight
loops and a reload clean; the FX2 change on T1 clean). Still washing: a THRU
host past position 0 with a trig on every step.
- The bus participants (SEND, BusDelay, BusVerb) take a split block's frame offset from `r0` instead of a stash in `$65/$66`.

## Image 42 — 21 Sep 2026 (`OCTABAM42`, bamsep26 at `d3fceaf`)

On the unit: the delay on a trig host clean (T2 THRU and T3 STATIC with a
trig every step, two loops, project OCTABAM91). Before play:
`stamp-defaults <project> bamsep26 --all --keep-mode`.
- BusDelay: the four init stores of PR #344 removed (38 clean, 39/40/41 wash, 42 = 41 minus the stores clean).

## Image 41 — 21 Sep 2026 (`bamsep26`)

On the unit: the white-noise wash on a trig host, as 39 and 40.
- BusDelay: nothing at `r7+$84` or above; five words moved to raw `$0c $20 $2a $6d $83` (PR #346).

## Image 40 — 21 Sep 2026 (`bamsep26`)

On the unit: BusDelay on T3 STATIC with a trig every step washes from the
second pass; LEVEL kills it, FDBK does not touch it, STOP does not end it.
- BusDelay: the glides run once per block (the a=0 call only); a minimum TIME step of 1/16 sample per block; the glide state guarded against boot garbage (PR #345).

## Image 39 — 21 Sep 2026 (`bamsep26`)

On the unit: the same wash as 40.
- BusDelay: the TIME glide ramps within the block (spikes per 1,000 samples in REVERSE 24 → 6 under the port); init zeroes the glided coefficients (PR #344).
- Names per mode (SIZE draws GLEN / SLEN, FREQ draws VOWL, TONE draws BRIT); every knob a mode never reads is named `---`.
- Character: TONE back on page-1 slot 4, WDTH page-2 slot 7.

## Image 38 — 20 Sep 2026 (`OCTABAM38`, bamsep26 at `60f41b0`)

On the unit: the reverb on T5 clean (Sam: "verb sounds clean on t5 now").
TIME or FDBK moves crackle; reverting does not clear it (fixed in 39).
Before play: `stamp-defaults <project> bamsep26 --all --keep-mode`.
- The bus returns on its hosts: T1-4's BusDelay prints the repeats, T5-8's BusVerb the tail; the T8 return and Character's RET removed; SEND still refused on T8.
- Character RET draws `---` off the master.
- Payload A FREE 706 → 918, B 1,240 → 1,519; static cycles reverb 1,159 → 1,135, delay 1,129 → 1,109.

## Image 35 — 20 Sep 2026 (`bamsep26`)

On the unit: the return on T8 duller and grainier than the dry, worse after
knob presses (removed in 38).
- Character RET defaults to 127; its name blank off the master.

## Image 34 — 20 Sep 2026 (`bamsep26`)

On the unit: flashed; Sam: "wow back freeze gone".
- BusDelay: the tape wow on page-2 slot 11 (0 .. ±254 samples, 0.8 Hz + 7.3 Hz); the freeze removed; CC 67 is WOW.
- BusDelay: the glide's fraction and lag moved to `$2b/$2c` (image 33 read GRAIN's window as its fraction); the TIME glide snaps onto its target within one step.

## Image 33 — 20 Sep 2026 (`bamsep26`)

On the unit: the knob-turn crackles gone (Sam).
- Knob glides: BusDelay reads its tap between samples at the glide's fraction and glides FDBK/TONE/PING/WET; BusVerb glides SIZE and TONE/DIFF/SHMR/WET.

## Image 32 — 16 Sep 2026 (`bamsep26`)

On the unit: T5 and T7 loud through BusDelay at SEND 0 on project OCTABAM89
until CLEAR PATTERN (16 Sep); on a clean project (20 Sep) the reverb,
Character and four Spectrums clean, the delay clean at rest, TIME and FDBK
moves crackle. Image 32B (the first burn image) held the sequencer on step 1
on two projects with every stored page byte zero.
- BusVerb +6 dB on the wet (WET 127 = ×2).
- MODE top left on page 2 of every effect; Modulation MIX on page-1 slot 5.

## Image 31 — 16 Sep 2026 (`bamsep26`)

On the unit: Sam, "reverb is still too quiet".

## Image 29 — 16 Sep 2026 (`OCTABAM29`, bamsep26 at `ed27afe`)

On the unit: the link brackets draw, SHFT draws its words on page 1, the
`---` names draw. Before play: `stamp-defaults <project> bamsep26 --all
--keep-mode`.
- The knob pass: every effect's page 1 and page 2 re-laid, links (`Param(link=True)`) on BusDelay and Spectrum, the first stepped select on a page 1 (SHFT).
- Modulation: ENS removed, MODE = JUNO DIM FLNG COMB PHSR, per-mode output trims, LOFI on page-2 slot 8.
- BusDelay: the tape wow knobs removed. BusVerb: MOD / RATE removed, SHMR on page-1 slot 2.
- `make check`: the ColdFire-port gates run unmasked; `make image` requires `BUILD=N`.

## Image 28 — 15 Sep 2026 (`OCTABAM28`, bamsep26 at `7b5da98`)

On the unit: the 32K delay lines, TAME gone and MODE over CC confirmed
(Sam: "sounds fantastic now").
- BusDelay: two 32K lines, TIME to 741 ms; a stored TIME byte means twice the time.
- Spectrum: TAME removed.
- MODE set over CC 62/68 re-defaults the mode's knobs, as the panel does.

## Image 27 — 15 Sep 2026

On the unit: select names confirmed.
- Only the MODE select names itself (SIZE / FRZE / SHFT keep their names).

## Image 26 — 15 Sep 2026

On the unit: MODE DEFAULTS confirmed. Static after some knob moves with the
reverb host's SEND and both WETs up, cleared by a transport restart
(project OCTABAM89 C02).
- MODE DEFAULTS: a MODE turned on the panel re-defaults its knobs.

## Image 25 — 15 Sep 2026

On the unit: flashed with image 24.
- The bus engines are add-only pedals with WET knobs; SEND on every track; host print only while no return.

## Image 24 — 15 Sep 2026

On the unit: flashed.
- The tempo cave no longer clobbers an FX1 station's page 2 on a bus host (note-only cave; the DSP reads tempo from stock).

Earlier images (the 13 Sep 96–100 series, flash 7 = `OCTABAM21`, and before)
are in `docs/contributing/FAILURE_MODES.md`, the module READMEs and the git log
(`git show 3ceba41:docs/history/VOICING.md` for the ear rounds up to 16 Sep 2026).
