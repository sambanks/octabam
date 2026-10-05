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

- Analog BD: engine selection now lives only in the pool-style browser; the
  former SRC SETUP MODEL control and its encoder editing path are removed.
  Both source outputs are 12.04 dB louder than the 29 September revision,
  with matching default hit energy (within 0.03 dB over 500 ms) and default
  peaks of −7.31/−1.59 dBFS for 808/909. The post-desk gains preserve every
  internal state; 909 overloads limit at full scale. The 808 uses the same
  three output instructions; the 909 adds four instructions per sample.

Remixes
- bottleservice takes the computer's stereo output onto inputs C/D (USB AUDIO IN CD + USB CROSSBAR); USB AUDIO OUT MASTER polls every 250 µs (28 Sep). Both IN modules out again on 4 Oct (#575, image A0 below).
- bottleservice keeps the stock DELAY's FX2 chooser row; `BUILD` tags past 99 are a letter and a digit (`A0` = 100) (4 Oct, #576).
- Twelve `usb-io-<out>-<in>` test remixes and `usb-out-main`; USB remixes named by direction (`usb-full` → `usb-out-tracks`, `usb-lean` → `usb-out-tracks-main-cue`, `usb-master` → `usb-out-master`, `usb-mc` → `usb-out-main-cue`) (28 Sep).
- `remixes/test/` holds the one-module carriers; `mods` moved there, `restock` removed (28–30 Sep).
- `octatrick` carries SYNTH MACHINE, SCALE QUANTIZER, DIRECT JUMP, TUNER, USB MIDI, USB AUDIO OUT TRACKS MAIN CUE and USB AUDIO IN ABCD + USB CROSSBAR on the stock effects less SPATIALIZER (its payload-A words hold the IN inject); `octatrick-usb` folded into it and removed (Tim Hastie, 29 Sep, #526).
- bottleservice carries PLOCKS P2 (3 Oct, #555).
- Removed: `bamsep26` (bottleservice is its superset), `mutables`, `nimbus`, `hello`, `hello-dram` (27 Sep).

Modules
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
- `tools/hw/bcr2000.py` (28 Sep), `tools/hw/usb_probe.py` (Bryan T, 28 Sep), `tools/harness/usb_align.py` (28 Sep), `tools/ghidra` (roblg, #483, 28 Sep).
- `verify_docs` checks every relative Markdown link; the remixer TUI draws again (30 Sep).
- `Formatter.PLAIN` zeroes a clone's formatter words on any module, not only one with a stepped slot (5 Oct); refhash 24/24 bit-identical, no shipping module changed.

Docs
- `docs/guide/` (BUILDING, REMIXER) and `docs/contributing/` (MODULES, PLACEMENT, TESTING, TOOLING, FAILURE_MODES cut to Seen / Cause / Fix / Check); tool docs beside the tools (30 Sep).
- `docs/contributing/TESTING.md`: every gate, how to write one, what it costs (29 Sep).
- ColdFire load on a unit: Bryan T's CF METER takes (4 Oct; `docs/firmware/ARCHITECTURE.md` section 6): ~16.5 µs per playing voice at CPI ~4.4 against the port, no first-voice premium (the morning's +37 µs retracted the same evening), the USB stack ~14 µs idle / ~25 µs playing, no crossbar contention; OUT TRACKS MAIN CUE costs 27–50 µs of frame interrupt over OUT MAIN CUE, most of it with no host connected; TSTR and the stock DELAY not measurable; interrupt levels from the ICR writes in `KERNEL.md`.
- Removed: `PLAN.md`, `docs/TIMESTRETCH_PIPELINE.md` (27 Sep).

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
