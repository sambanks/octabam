# The harness: hearing and measuring the effects without hardware

The harness runs the real assembled instruction stream on a cycle-exact
DSP56300 emulator ([dsp56300](https://github.com/dsp56300/dsp56300)'s core)
at roughly 6× real time. A render is the module, not a model of it; its
blind spots are listed at the end.

Needs `make setup` (builds `dsp_asm` and `dsp_host`), `make os && make
recon`, and for the measurement tools (`abkit`, `station_laws`,
`click_scan`, `clock_probe`, `cfmeter`) numpy from `make emu-setup`
(run them with `.venv/bin/python3`). `play`/`abkit play` use `afplay`
(macOS).

## The stack

```
modules/*/*.asm (+ dsp/ probes)
          ──dsp_asm──► tools/build/build_bus.py ──► out/mainos_bus.bin   (the firmware)
                              │
                              └─► out/dsp/mem_*.mem      (payload memory dumps,
                                        │                 via dsp_modmap --dumpmem)
                                        ▼
                            tools/harness/dsp_host  (C++, vendor/dsp56300 emulator)
                              loads the dumps, seeds the frame context,
                              calls init/proc through the recovered ABI,
                              captures the audio buffer every block
                                        │
                    ┌───────────────────┴────────────────────┐
                    ▼                                        ▼
        render_reverb.py / rig_render.py            send_probe.py
        wav in → wav out, by ear                   tone in → numbers out
        (make reverb, make render-rig)             (make render / render-delay)
```

```bash
make reverb IN=loop.wav ARGS='--wet --mode all'   # hear BusVerb
make render REMIX=<name>                          # the full bus, SEND → REVERB
make render-delay REMIX=<name>                    # BusDelay via the DEV hatch
make render-rig REMIX=<name>                      # eight tracks on both cores
python3 tools/harness/send_probe.py --mem out/dsp/mem_dev_A.mem --direct --pick 2   # an insert (Character) on its own track
```

An insert has no bus accumulator, so `send_probe` refuses a layout of
nothing but inserts; `--direct` renders it on its own track. The letter (a
digit for the stations) is the module's `harness.layout_char`; build a DEV
image for a remix that
contains it first (`REMIX=<name> DEV=1 XBUS=1 SPEC=1 python3
tools/build/build_bus.py`).

## dsp_host

`tools/harness/dsp_host/dsp_host.cpp`; its comments are the detailed
reference.

- **Loads a payload memory dump** (`dsp_modmap.py --dumpmem`): every
  module's P/X/Y words at the addresses the DSP's own loader places them.
- **Seeds the frame context by running the DSP's own setup routine**
  (`P:0x372..0x39e` in payload A, `P:0x17a` in B, found by opcode pattern),
  which derives the frame count, buffer strides and state-table pointers
  from two loaded pointers as hardware does.
- **Calls effects through the recovered ABI:**

  ```
  r0 = audio block base (interleaved stereo, processed in place)
  n7 = frame count
  r6 = parameter block; x:(r6+0..5) page 1, values 0..127 << 16
  r7 = per-instance state block
  rts to return
  ```

  Page 2 is three words `r6+$c/$d/$e`, each a KNOB field (bits 16-23) and
  a COMPANION field (bits 8-15) (`docs/firmware/PARAM_PAGES.md`). `-tempo
  BPM` publishes tempo24 at `r6+$13` (record halfword 31) as the stock
  frame builder does.
- **Runs multiple instances the way the dispatcher does**: every init
  first, then each block handed to every instance in turn, each with its
  own r7 state block, allocator entry and audio buffer (the instance model
  is measured: `dsp/r7probe.asm`, `dsp/baseprobe.asm`, in git history).
  `-init`/`-proc` take lists, one entry point per instance. `-inmask`
  silences chosen instances' own input so a server's output is only what
  arrived over the bus.
- **Models the trig split.** The dispatcher makes up to two calls per
  block, an `a=0` sub-block call for frames before a trig's landing offset
  and the `a=1` call for the rest; `-split` reproduces that per instance.
- **Polices memory.** `-guard` shadows real Y and the loaded P image and
  reports, after every call, any word that changed outside the calling
  instance's own window (a stray write vs a clobber of a loaded module).
  `-dirty` pre-fills Y with garbage, as hardware never zeroes a buffer.
- **Streams** (`-stream`, for `fxlive/`): runs until stdin closes. Each
  block in: 12 knob values then the frames as interleaved int32. Each
  block out: the track's frames, then the instructions its core ran.
  Text goes to stderr.
- **Instrumentation:** `-track` dumps r7-relative state words every block,
  `-peekx/-peeky/-pokey` read and seed words, `-dumpy` writes a region,
  `-trace` logs the first N instructions; every run reports
  instructions/sample per instance. `-dispatch` runs the payload's own
  dispatcher loop instead of the hand-rolled calling convention.
- **Two cores:** `-mem A.mem -memB B.mem` boots both payloads in one
  process with X/Y `0x30000-0x3FFFF` of core 1 redirected into core 0's
  arrays (`tools/patches/dsp56300.patch`; X with X, Y with Y, P private).
  `-core` assigns each instance to a core, positions counted per core;
  `-audioidx` lets two instances share one audio buffer in order (a
  track's FX1 then its FX2). Lock-step by default (core 0's whole block,
  then core 1's); `-skew N` interleaves instruction by instruction, core 0
  N ahead: a fuzz of the hardware's timing, not the timing. Identity under
  skew proves nothing; a mismatch is a defect. `-meter FILE` prints, per
  core, the maximum and mean instructions per block: instructions, not
  cycles, no contention stall modelled, so a floor.
- **The dispatcher's r7 is the port's business.** `dsp_host` hands every
  effect an r7 it computes; the stock dispatcher bumps r7 three times per
  track, so module logic keyed on a dispatcher fact (r7, r6, X:0x213,
  instance blocks) is measured under `ot_emu --dsp-pcwatch`, never here.

### Blocks: 15 frames in the gates, 16 in the voicing wrappers

The setup routine masks the frame count with `& 0xf`, so `dsp_host`'s
own block is 15 frames where hardware runs 16 (the nibble the harness
seeds is the dispatcher's SPLIT, not a length; 0 = a whole block, measured
under the port). `-frames 16` runs whole frames. `send_probe` and every
bit-identity gate built on it are pinned at 15 (bus latency exactly 2
blocks: 30 samples, 32 on hardware); `rig_render` and `render_reverb`
default to 16 so a voicing render's rates and latencies are the unit's;
`--frames 15` is the old harness. The warm-up pad is 256 calls in blocks
of the chosen length (4,096 samples at 16).

## render_reverb.py

`make reverb IN=loop.wav` pushes a wav through BusVerb and writes a wav
back. `-p NAME=VAL` sets knobs by name, `--sweep NAME=a,b,c` renders one
file per value, `--wet` isolates the tail, `--mode all` renders every
character. Renders are provenance-stamped: the cache is keyed on a content
fingerprint of everything that can change the instruction stream (every
module and `dsp/` source, the manifests and remix selections, the build
engine, every env var the builder branches on); a mismatch forces a
rebuild. The knob table is derived from the manifest; audit the wrappers
after every knob change.

## send_probe.py

`make render` builds the DEV image and runs the real send path (SEND
client → shared bus accumulator → REVERB server) with the tone fed only to
the SEND instance, so everything in the server's output crossed the bus.
`--layout` is a string of dispatch slots in hardware order, slot 0 being
position 0 (the housekeeper): `RS`, `.RS` and `SSR` are different
machines. The alphabet is derived from the manifests (`harness.layout_char`;
`.` = a track running neither); only modules whose harness says
`is_server` can be the target of a measurement. Entry points are read from
the dump's own dispatch tables; `--direct` bypasses the bus. `--set
NAME=VAL` / `--set LETTER:NAME=VAL` drives any knob by its manifest name;
`--feed` chooses the fed track.

The metric: a bin-centred 438.75 Hz sine through a linear system comes back
as one FFT bin; total non-fundamental energy relative to the fundamental
is the artifact number. Silence is checked first and reported as a failed
measurement.

### The DEV hatch (`make render-delay`)

The shipping build (`SPEC=1`) puts BusDelay in payload B only, and a SPEC
dump aliases the absent delay's dispatch id to the SEND client, which
locally renders a plausible dry passthrough. A `DEV=1` build places a real
delay at `P:0x04000` in payload A's dump, outside the donor region, and
`send_probe` refuses to run a delay layout against a SPEC dump. Every
single-core gate is stamped against the hatch; the two-core path renders
payload B's own copy.

## rig_render.py

`make render-rig`; `--tracks T1=D,T2=S,…` (or `T3=L+S` for FILTER on FX1
into a SEND on FX2), or `--project DIR --bank N --part N` for the ids and
knob bytes of a real part; stems per track; T1-T4 on core 1, T5-T8 on
core 0 in dispatch order; an empty FX2 slot modelled as the fallback SEND
the unit dispatches there (without it a layout with nothing at core 0's
position 0 has no housekeeper and the bus never rotates). Out come
`T1.wav…T8.wav` (each track's chain output, before LEVEL), `mix.wav` (the
main out: every track through LEVEL², summed, saturated as a 24-bit sum,
clips counted) and `meter.txt`. About real time for eight tracks. A
`--set` that picks a module's MODE also applies that mode's
`ModeView.defaults` to every knob not set explicitly.

**The mixer model** (`tools/harness/mixer.py`, measured under the ColdFire
port, 26 runs, residuals −100 dB and better): AMP VOL is (v/127)² and AMP
BAL a balance (near side unity, far side to zero on a cubic), both applied
before the FX chain by stock DSP code `dsp_host` never runs; track LEVEL is
(L/128)², applied after, at the mix. `rig_render` applies them by default:
the stem through VOL² and the balance per side into the chain (`dsp_host
-stereo`), each track's chain output through LEVEL² into `mix.wav`. Values
come from the part with `--project` (the AMP row six bytes before the FX1
row, the LEVEL pair at +0x1b) or the unit's defaults (VOL 64 = −11.9 dB,
BAL 64, LEVEL 108 = −3.0 dB); `--mix T1:VOL=127,BAL=64,LEVEL=100`
overrides; `--mixer off` is the old harness (`--amp 0.5`, no AMP stage,
5.9 dB hotter than the unit; every voicing note before 12 Sep 2026
inherited that). A 0 dBFS stem enters the engine at 0.254 FS at the
default VOL. Not modelled here: the main level, the cue mix, the master
track — the same `(L/128)²` law, measured on MAIN/CUE by hardware capture
rather than under the port (`docs/firmware/LEVEL_LAW.md`); the AMP stage
was measured on a THRU and is inferred for FLEX/STATIC.

**bottleservice's layout on a real set:** `tools/hw/ot_project.py rigproj SONGSET
out/set/RIGSONG bottleservice` writes that layout (ids, defaults, mode
views) into every part of a copy of the song set;
`tools/harness/set_stems.py out/set/RIGSONG --bank B --part P --audio DIR
--out D/stems` writes T1..T8 from each track's STATIC sample at its slot
gain; `rig_render --project out/set/RIGSONG --bank B --part P --stems
D/stems` renders the part with its own knobs.

**The bus and FX1 stations' floor, metered** (the RIG table with eight stems): core 0
(Modulation + BusVerb on T5, Spectrum + SEND on T6/T7, Character + the
fallback SEND on T8) 1,570 instructions/sample at its worst block; core 1
(Character + BusDelay on T1, Spectrum + SEND on T2-T4) 702. The 3,120
wall was triangulated in `cycle_count.py`'s units (words in the sample
loop), so the static sum is the comparable floor. The ColdFire port
measured the same layout under the firmware's own dispatch (`--dsp-stopwatch`,
`git show 3ceba41:docs/history/COLDFIRE_PORT.md` O13): core 0 24,654 a frame against the
meter's 24,971, core 1 15,177 against 14,880: the meter reads the real
load within 2 %.

`tools/verify/verify_twocore.py` (in `make check`): SEND and BusDelay on the
real payload B feeding BusVerb on payload A (the send hop, the delay hop,
the delay→reverb series hop) render bit-identical to the same layouts on
one core through the DEV hatch, and under four skews.
`tools/verify/verify_onebus.py` (in `make check`): the one-aux bus's chain,
its liveness stamp, WET passthrough, each host's print, the track-8 send
refusal and station silence, senders and delay on payload B, reverb on payload A.

## port_compare.py

`make port-compare PROJECT=dir [IMAGE=... REMIX=...]` runs one part under
the ColdFire port (the firmware booting the image, loading the project from
a staged card, the sequencer running with a probe on the ESAI inputs) and
under `rig_render` on the same image with each track's chain input (the
port's own 84-word record audio) as its stem, and fits the two per track
(lag, least-squares scale, per-window residual) and the port's TX0 main
slot against `mix.wav`. ~90 s. A linear chain fits to 0.00 dB and −100 dB
or better; an engine with history (the reverb's free-running allpass
modulator, the delay's LFO) matches in scale and not in residual.

| fixture | track | scale | residual |
|---|---|---|---|
| stock image, T1 THRU: SEND + EQ flat, tone | T1 chain | −0.001 dB | −121 dB |
| same | mix (TX0 slot 2 vs `mix.wav` L) | −0.001 dB | −113 dB |
| the one-aux bus, kick on T2's inputs | T2 chain (SPECTRUM + SEND) | −0.001 dB | −137 dB |
| same | T8 return (delay → reverb, history; the return gone 20 Sep 2026) | −0.083 dB | −8 dB |
| same | mix | −0.001 dB | −90 dB |

A track whose record carries audio but whose chain output is digital zero
is a non-THRU machine's record and is listed, not compared; a host or a
return is compared on its output with a silent stem; the lag search is
±96 (a periodic probe is ambiguous modulo its period); the master track
is turned off in the copy of the project the port loads. Use a transient
probe (`--tone out/o9d/kickAB_late.wav`) for anything with a delay in it.

## pressure.py

`python3 tools/harness/pressure.py price --remix bottleservice` enumerates every
per-core layout the remix lets a user select (four tracks × FX1 ∈ {none,
the FX1 rows of ours} × FX2 ∈ {SEND, this core's server, ours on the FX2
chooser, stock rows at 0}, at most one server per core) and sums the static
per-sample cost of each pick at its worst mode loop (`cycle_count.py`),
against 3,120 (USABLE, `docs/firmware/CHIP.md` section 2). Tag 91 hung the sequencer with three
stations beside the reverb at a static 3,106, under both lines, which
points at the counter's known error (the reverb ~270 low, the delay ~260
high); the burn sweep settles both. `out/pressure/<remix>_layouts.tsv` has
every layout.

`pressure.py render --top N --sample M` runs the dearest N layouts per
core and M random others through `rig_render` on the real image with every
knob at its dearest setting under `dsp_host -guard -dirty` and the meter. A
red is a hang, a clobber of a loaded module, or a stray write from an
insert; a server's strays (the bus scratch, the reverb's relocated
buffers) are expected. The render pass proves memory; the meter's
instructions/sample is the relative load for the burn sweep.

## abkit.py and station_laws.py

`abkit.py sweep --station SPECTRUM --stem … --knob FREQ=20,40,… --out
out/ab/spec_freq` renders a knob sweep on T1's FX1 through `rig_render`,
level-matches (every file to the same active RMS, then one joint trim so
the loudest peak sits at −1 dBFS; `--no-match` keeps rendered levels),
`measure` reports active RMS, centroid and peak per file, `play` plays
A/B/A/B one `afplay` at a time. `station_laws.py` renders white noise
through a station per knob value and reports the −3 dB corner, the peak of
|H| and its bandwidth, and the level at 100 Hz / 1 kHz / 10 kHz.

## stress_project.py: a stress project for `make accept`

Generate a local Octatrack project with eight simultaneous FLEX tracks, three active LFOs per track, 15 locked parameter slots per step (14 on the tracks `verify_set` probes), and the remix's costly DSP paths:

```sh
python3 tools/harness/stress_project.py --remix bottleservice            # writes out/stress-project
python3 tools/harness/stress_project.py --remix miniverb --layout   # print the placement, write nothing
```

The script copies only the `.work` and `.strd` files of a local project (`--source`; the default `template_project/Drum Template TGM` is gitignored, a project you place there yourself), inserts a generated stereo loop, sets 120 BPM, and writes `out/stress-project`. It refuses to overwrite an existing output. Use `--source` for another locally saved Octatrack project and `--out` for a new destination. No project file or stock firmware is committed.

The placement is derived from the selection (`layout`):

- each server on the first track of its core (payload B serves T1-4, A T5-8: T1 and T5);
- SEND on every other FX2 slot when the remix carries it; otherwise the remix's FX2 inserts round-robin, dearest first; otherwise NONE;
- per core, the FX1 combination with the most different modules that prices under the static wall beside that core's FX2, then the dearest such set (the pressure pricer's arithmetic, `tools/harness/pressure.py`).

Every knob sits at its module's dearest setting (`schema.Module.dear`; the defaults for a module without one), and a MODE select walks its positions with the Part and the track, so switching A01-A04 also changes engines. `STRESS_README.txt` in the output records the placement, counts and the audio hash.

Bank A is the test bank. A01 has 16 locked trigs on each track, A02 has 32, A03 has 64, and A04 has 16 trigs plus 48 trigless lock steps per track. Each pattern selects its matching Part. Other banks are cleared of inherited trigs and locks. All bank Parts, including saved mirrors, carry the same eight-track layout.

The generator reads every written bank back and checks effect IDs, FLEX types, LFO depths, pattern-to-Part mapping, trig/lock counts, and checksums.

FX2 slot 0 (DEL) on T2 and on every server's track has no lock or LFO: `verify_set` sends CC 40 there and reads back the value it sent. Those tracks' third LFO targets FX1 instead; all 24 LFOs remain active.

For a local playback check, create `out/stress-run`, stage the card there, and run the port:

```sh
mkdir -p out/stress-run
python3 tools/emu/ot_emu/stage_card.py out/stress-project OCTABAM STRESS \
  --tree out/stress-run/card-tree --out out/stress-run/card.img \
  --audio out/stress-project/AUDIO/STRESS_LOOP.wav:STRESS/AUDIO/STRESS_LOOP.wav
out/emu/ot_emu --image out/mainos_bus.bin --card out/stress-run/card.img \
  --set OCTABAM --project STRESS --sequencer --internal-clock \
  --frames 2500 --load-ms 90000 --dsp --main-level 64 \
  --audio-out out/stress-run/smoke
```

Check for `run ended REACHED` and nonzero audio. On hardware, copy the generated `.work` and `.strd` files into a project directory under your set, and keep the generated `AUDIO` folder inside that project so `AUDIO/STRESS_LOOP.wav` resolves. Select A01, then switch through A02-A04. Lower monitoring level before starting: eight tracks at their dearest settings sum loudly. Watch for a freeze, dropout, incorrect Part/effect mode, or a parameter that stops following locks or LFOs. Repeat after each feature change and compare with the same image and project. The emulator run checks loading and short playback; a long hardware soak and manual pattern switching remain separate checks.

## The burn knob (hardware)

`make burn` / `make burn-image BUILD=N` (`BURN=1` with `SPEC=1`: the
shipping remix plus a `BURN` knob on SEND's second slot). SEND is on every
track of every core, so either core's ceiling can be measured on demand:
set up the configuration, sweep that SEND's `BURN` until the audio breaks,
and `24 × BURN` = cycles/sample spare on that core in that configuration
(a three-word body, `dsp/burn_send.inc`; the reverb's old two-block probe
was 32/step, the original 16). `verify_burn.py` proves the knob inert at 0
and 127 and the step exact on both cores. The difference between two
configurations is the cost of the change, the only way to price a stock
effect (instruction count is not cycles: one rewrite moved instructions
508 → 512 while cycles fell 735 → 731). A configuration that freezes at
`BURN = 0` is already over budget. The current numbers it produced are
`docs/firmware/CHIP.md` section 2.

Measured with the original probe (before the 22 Sep 2026 clock
measurement, on a 4,535-cycle frame):

| configuration | result | spare |
|---|---|---|
| FILTER on all four tracks | froze at `BURN = 87` (16× scale) | 1,392 ✅ |
| FILTER disabled everywhere | froze at `BURN = 76` (32× scale) | 2,432 ✅ |

Four FILTERs cost 1,040 cycles/sample by difference (❌ superseded: one
FILTER measures 192, `CHIP.md` section 2). FX2 bank (static) 957
+ 4 × FILTER 1,040 + burn at the freeze 1,392 = 3,389 accounted; stock's
own per-track work by difference ~1,150 of 4,535. The 16× probe topped out
at 2,032 and the filters-off configuration passed it, so the absolute
ceiling is unmeasured by it. ❌ "There is not real headroom": retracted.

## What the harness cannot see

- **The hardware's cross-core timing.** Two emulated cores run lock-step or
  under a chosen interleave, never under the chip's skew, and no SRAM
  contention is modelled. A local clean under every `-skew` is not evidence
  a race fix holds (`modules/send/README.md`).
- **The cycle budget.** The emulator renders an engine the chip cannot
  afford. `make cycles` bounds it; hardware proves it.
- **The ColdFire side.** `-params` pokes r6 directly, bypassing menus,
  descriptors, ranges and scene logic; the gain chain around the chain is
  modelled, the main level and the cue are not. A slot can draw a knob and
  publish nothing (`docs/firmware/PARAM_PAGES.md`).
- **Whatever the metric is structurally blind to.** The spur metric sums
  energy against a 438 Hz fundamental; it reported −45 dB on audio hardware
  showed carrying +22 dB of inharmonic block-rate hash (~2940 Hz is not a
  harmonic of 438 Hz).
- **The stock DELAY's audio, under the ColdFire port.** Its ring arithmetic
  runs but the eDMA channel that moves audio through the SDRAM rings is not
  modelled, so a part carrying stock DELAY renders no repeats under
  `ot_emu` (inferred from the silence).
- **What only ears catch.** GRAIN's right-channel hiss passed every
  automated check and was found by listening. The listening protocol:
  one file per play, say what it is and what to listen for before it plays,
  level-match (active RMS) before any A/B, judge modes wet-only, ~9 s of a
  sustained source, A/B/A/B.

`docs/firmware/DSP.md` section 6b is the bring-up of `dsp_host` and the ABI; the
functional baseline (`TESTPASS.md`) and the hardware-measurement protocol
(`CAPTURE_18AUG.md`) are in git history (`git show 3ceba41:docs/history/<name>`).
