> ⚠️ **9 Sep 2026: `dsp_host`'s own block is 15 samples; the unit's is 16.** The frame-context nibble the harness seeds is the dispatcher's SPLIT, not a length (0 = a whole 16-sample block, measured under the ColdFire port). `dsp_host -frames 16` runs whole blocks exactly as the firmware does (the delay bus then lands at exactly one frame of lag against the port). **Since 12 Sep 2026 the voicing wrappers — `rig_render`, `render_reverb` (`make render-rig`, `make reverb`) — default to 16**; `--frames 15` is the old harness. The bit-identity gates (`send_probe`: `make render`, `verify-bus`, `verify-twocore`, …) are still pinned at 15 and self-consistent there; every per-block rate in THOSE is 16/15 of the unit's and every bus latency carries a sub-frame offset. `docs/firmware/COLDFIRE_PORT.md` O12.

# The harness — hearing and measuring the effects without hardware

Flash cycles are expensive: every hardware test is a manual firmware write.
The harness exists so that almost every judgement — voicing, gain structure,
knob behaviour, refactor safety — can be made on the desktop, and flashes are
spent only on the things no emulator can prove (see the last section, which
is as important as the rest of this page).

The one-line claim, and why it is trustworthy: **the harness runs the real
assembled instruction stream on a cycle-exact DSP56300 emulator.** It is not
a model of your module; it is your module, executed by
[dsp56300](https://github.com/dsp56300/dsp56300)'s emulator core at roughly
6× real time. When a render sounds wrong, the code is wrong — modulo the
blind spots listed at the end.

## The stack

```
modules/*/*.asm (+ dsp/ probes)
          ──dsp_asm──► tools/build/build_bus.py ──► out/mainos_bus.bin   (the firmware)
                              │
                              └─► out/dsp/mem_*.mem      (payload A memory dump,
                                        │                 via dsp_modmap --dumpmem)
                                        ▼
                            tools/harness/dsp_host  (C++, vendor/dsp56300 emulator)
                              loads the dump, seeds the frame context,
                              calls init/proc through the recovered ABI,
                              captures the audio buffer every block
                                        │
                    ┌───────────────────┴────────────────────┐
                    ▼                                        ▼
        tools/harness/render_reverb.py                     tools/harness/send_probe.py
        wav in → wav out, by ear                   tone in → numbers out
        (make reverb IN=..)                        (make render / render-delay)
```

Three commands cover most days **if you are working on a bus server**:

```bash
make reverb IN=loop.wav ARGS='--wet --mode all'   # hear BusVerb
make render                                       # the full bus, SEND → REVERB
make render-delay                                 # BusDelay via the DEV hatch
```

**An INSERT is rendered differently, and none of those three do it.** An
insert has no bus accumulator, so there is nothing for `send_probe`'s bus
analysis to read — it will refuse a layout of nothing but inserts, and say
so. Render one on its own track instead:

```bash
# the tone (or a wav) straight into the module on its own track
python3 tools/harness/send_probe.py --mem out/dsp/mem_dev_A.mem --direct --pick W

# or drive the emulator yourself, which is what the module authors did:
#   -inst 1 -r7 2 -alloc 1 -inmask 1, entry points from the dump
```

The letter (`W` above) is the module's `harness.layout_char`. Build the DEV
image for a remix that contains it first — `REMIX=<name> DEV=1 XBUS=1 SPEC=1
python3 tools/build/build_bus.py`.

## dsp_host — the emulator harness

`tools/harness/dsp_host/dsp_host.cpp` (~900 lines, heavily commented — the comments
are the detailed reference; this page is the map). What it does:

**Loads a payload memory dump** produced by `dsp_modmap.py --dumpmem`: every
module's P/X/Y words at the addresses the DSP's own loader would place them.

**Seeds the frame context by running the DSP's own setup routine**
(`P:0x372..0x39e`) rather than reconstructing its control words by hand. The
routine derives the frame count, buffer strides and state-table pointers from
two loaded pointers, exactly as hardware does.

**Calls effects through the recovered ABI:**

```
r0 = audio block base (interleaved stereo, processed IN PLACE)
n7 = frame count
r6 = parameter block; x:(r6+0..5) page 1, values 0..127 << 16
r7 = per-instance state block
rts to return
```

Page 2 uses the real map settled on hardware 17 Aug 2026 (see
`docs/firmware/PARAM_PAGES.md`): three words `r6+$c/$d/$e`, each carrying a KNOB field
(bits 16–23) and a COMPANION field (bits 8–15), so companion selects like the
reverb's SHFT are drivable locally. `-tempo BPM` publishes the tempo words at
`r6+$6/$7` the way the ColdFire cave does on hardware.

**Runs multiple instances the way the dispatcher does**: every init first,
then each block handed to every instance in turn, each with its own r7 state
block, allocator entry and audio buffer. The instance model is measured, not
assumed — the r7 and base-table values came from probes (`dsp/r7probe.asm`,
`dsp/baseprobe.asm`, both in git history). `-init`/`-proc` take *lists*, one
entry point per instance, which is what lets a real SEND client and a real
SERVER share one session — the only way to exercise the shared bus end to
end locally. `-inmask` silences chosen instances' own input so a server's
output is provably *only* what arrived over the bus.

**Models the trig split.** The hardware dispatcher makes up to two calls per
block — an `a=0` sub-block call for frames before a trig's landing offset,
then the `a=1` call for the rest. `-split` reproduces that, per instance,
because tracks trig independently. Without `-split` the `a=0` call is
skipped, which is exactly what hardware does at split 0.

**Polices memory.** `-guard` shadows all of real Y and the loaded P image and
reports, after every call, any word that changed outside the calling
instance's own window — distinguishing a *stray* write from a *clobber* of a
loaded module, the two bugs that hang this DSP with no symptom at the point
of failure. `-dirty` pre-fills Y with garbage, because hardware never hands
an effect a zeroed buffer and the emulator otherwise does.

**Instrumentation:** `-track` dumps chosen r7-relative state words every
block (so a rate can be measured by differencing — `-peekx` only snapshots
once, at the end), `-peekx/-peeky/-pokey` read and seed individual words,
`-dumpy` writes a raw memory region, `-trace` logs the first N instructions,
and every run reports instructions/sample per instance. `-dispatch` is
faithful mode: instead of hand-rolling the calling convention, it runs the
payload's *own* dispatcher loop and lets it make every call — the mode that
caught an ABI misreading the hand-rolled path could never see.

### Blocks are 15 frames in the gates, 16 in the voicing wrappers

The setup routine masks the frame count with `& 0xf`, so dsp_host's own
block is 15 frames where hardware runs 16; `-frames 16` overrides it and
runs whole frames (O12). `send_probe` and every bit-identity gate built on
it are pinned at 15 (the bus latency there is exactly 2 blocks — **30
samples, 32 on hardware**, `docs/remixer/TESTPASS.md`); `rig_render` and
`render_reverb` run 16 since 12 Sep 2026 so a voicing render's rates and
latencies are the unit's. Their warm-up pad is 256 CALLS, i.e. in blocks
of the chosen length — at 16 it is 4,096 samples, and until 12 Sep the pad
was fixed at 260 × 15, which left 196 samples of the engines' dry warm-up
at the head of every `--frames 16` render.

## render_reverb.py — judging by ear

`make reverb IN=loop.wav` pushes a wav through BusVerb and writes a wav
back. `-p NAME=VAL` sets knobs by name, `--sweep NAME=a,b,c` renders one file
per value, `--wet` isolates the tail, `--mode all` renders every character.
Voicing decisions in `docs/effects/VOICING.md` are all listening results from this
tool.

Two design points worth knowing, both scars:

* **Renders are provenance-stamped.** An evening was once spent A/B-ing
  byte-identical files because an edit hadn't actually been rebuilt. The
  cache is keyed on a content fingerprint of *everything* that can change
  the instruction stream — every module and `dsp/` source, the manifests
  and remix selections, the build engine, and every env var the builder
  branches on — and a mismatch forces a rebuild. mtimes cannot do this job.
  The fingerprint is part of any build change: when a source moves or an
  env flag is added, `render_reverb.py`'s globs and `BUILD_ENV` move with
  it (both have been caught stale — same-bug twice).
* **The knob table drifts when the DSP-side map changes**, and a stale
  wrapper renders confidently with the wrong knob wired (18 Aug 2026: `-p
  GATE=n` was landing on WIDTH's companion — four such bugs in one audit).
  The rule since: audit the wrappers after every knob change.

## send_probe.py — the bus, measured

`make render` builds the DEV image and runs the real send path — SEND client
→ shared bus accumulator → REVERB server — with the tone fed *only* to the
SEND instance, so everything in the server's output crossed the bus. That is
what makes the measurement unambiguous. `--layout` is a string of dispatch
slots in hardware order, one character per dispatch slot, slot 0 being
position 0 (the housekeeper) — so `RS`, `.RS` and `SSR` are different
machines, not different spellings.

**The alphabet is DERIVED from the manifests**, not a fixed list: every
module that declares a `harness.layout_char` gets its letter, and `.` means a
track running neither (NONE, or a stock effect). Today that is `R` reverb,
`D` delay, `S` send, and `W F M G B N` for the six inserts — but read
`harness.layout_char` in the manifests rather than trusting this sentence,
which is exactly the kind that goes stale. It did: the alphabet was a
hard-coded `"RDS."` until 29 Aug 2026, which silently dropped every module
outside it from every layout string.

`send_probe` ANALYSES a bus accumulator, so only modules whose harness says
`is_server` can be the target of a measurement; ask for a layout without one
and it refuses with the reason. Entry points are read from the dump's own
dispatch tables, never hardcoded, and `--direct` bypasses the bus — a control
run for a server, and the ordinary way to render an insert.

The metric: a bin-centred 438.75 Hz sine through a linear system should come
back as one FFT bin. Total non-fundamental energy relative to the
fundamental is the artifact number. Silence is checked *first* and reported
as a failed measurement, never as a clean one — a silent render scores
perfectly on any spur metric.

### The DEV hatch (`make render-delay`)

The shipping build (`SPEC=1`) puts BusDelay in payload B only — and until
7 Sep 2026 dsp_host could not boot payload B (it can now: see "Two cores"
below; the hatch stays because every single-core gate is stamped against
it). Worse, a SPEC dump *aliases* the absent
delay's dispatch id to the SEND client (deliberately, so a wrong chooser
pick becomes a send), which locally renders a plausible dry passthrough: the
12 Aug 2026 "delay outputs nothing" session measured a SEND all day. So
delay work runs through the hatch: a `DEV=1` build places a real delay at
`P:0x04000` in payload A's dump, outside the donor region (the emulator has
no 8K wall), and send_probe refuses to run a delay layout against a SPEC
dump so the mistake dies loudly instead of rendering.

## The verification suite

`make check` is the floor for any change — build, cycle budget, ColdFire
menu verification, no hardware needed. On top of it:

| command | proves |
|---|---|
| `make cycles` | per-effect cycle cost against the measured per-core budget |
| `make verify-bus` | a bus-layout change is behaviour-preserving: 17 layouts rendered and hash-compared bit-for-bit against a stamp taken before the edit (`SAVE=1` first). On demand, not in `make check`, because the hashes cover the whole render and any deliberate voicing change fails it |
| `make verify-roll CAND=..` / `make verify-delay CAND=..` | an engine refactor is bit-identical to the reference — the strongest claim the emulator can make, and how every space-saving roll was proven safe |
| `make verify-midi` | the note→PITCH interval path, locally, via a build-time override |
| `make verify` | the ColdFire-side edits: slot tables, menu descriptors, formatter-vs-count consistency |

Bit-identity is the harness's superpower: because the arithmetic is emulated
exactly, "same output hashes" means "same machine behaviour", which turns
refactoring risk into a mechanical check.

## Two cores — the whole rig locally (7 Sep 2026)

`dsp_host -mem A.mem -memB B.mem` boots **both payloads** as two complete
DSPs in one process, with X/Y `0x30000–0x3FFFF` of core 1 redirected into
core 0's arrays (a patch to the vendored emulator's `Memory`,
`tools/patches/dsp56300.patch`) so the shared window really is shared. ⚠️ That is
X with X and Y with Y, P private -- which renders bit-identically and
cannot answer aliasing questions. The ColdFire port's DSP pair
(`tools/emu/ot_emu/dsp.h`, O8) uses the same patch's THREE-WAY form, P/X/Y one
memory, because the firmware's own boot needs it (`docs/firmware/COLDFIRE_PORT.md`).
The patch also carries the host-stepped mode that port drives the cores in;
`dsp_host` is untouched by it. Each core
runs its **own** setup routine: the harness finds it by opcode pattern —
payload B keeps it at `P:0x17a` where A's is at `P:0x372`, the same code
relocated (✅ measured by matching the instruction sequence; the old
"cannot boot payload B" was three hardcoded payload-A addresses). `-core`
assigns each instance to a core, positions counted per core; `-audioidx`
lets two instances share one audio buffer in order — a track's FX1 then its
FX2.

**What it proved on the first day** (`tools/verify/verify_twocore.py`, in `make
check`): SEND and BusDelay on the *real* payload B feeding BusVerb on
payload A — the send hop, the delay hop and the delay→reverb series hop —
render **bit-identical** to the same layouts on one core through the DEV
hatch. That is the harness proven (a window not shared or a context address
wrong would show) *and* payload B's copy of the delay proven: its `$38000`
base substitution and SPEC placement had only ever been checked statically.

**Scheduling.** Lock-step by default (core 0's whole block, then core 1's),
which is what one core always saw and is blind to the race by construction.
`-skew N` **interleaves** the two instruction by instruction, core 0 N
ahead. That is a *fuzz* of the hardware's timing, not the timing: identity
under skew proves nothing (the gate's four skews all match), a mismatch is a
real defect — and no local test could show one before.

**The meter.** Every run prints, per core, the maximum and mean instructions
per block for *this layout* (`-meter FILE` for every block). Instructions,
not cycles — no contention stall is modelled — so it is a floor like
`tools/build/cycle_count.py`, but per block with every instance's real work and
any init that lands inside a block. The wall is `docs/firmware/CHIP.md`'s measured
budget; the emulator never sees the cliff.

**`tools/harness/rig_render.py`** drives it track by track: `--tracks T1=D,T2=S,…`
(or `T3=L+S` for FILTER on FX1 into a SEND on FX2), or `--project DIR
--bank N --part N` for the ids **and knob bytes** of a real part; stems per
track; T1–T4 on core 1, T5–T8 on core 0 in dispatch order, and an empty
FX2 slot modelled as the fallback SEND the unit dispatches there (without
it a layout with nothing at core 0's position 0 had no housekeeper and the
bus never rotated — a delay-only render was silent, 7 Sep 2026); out come
`T1.wav…T8.wav`, `mix.wav` (unity sum, −6 dB) and `meter.txt`. About real
time for eight tracks on two cores. `make render-rig`.

**The rig's floor, metered (7 Sep 2026, `bamsep27`, the RIG table with
eight stems):** core 0 (Modulation + BusVerb on T5, Spectrum + SEND on T6/T7,
Character BUS + the fallback SEND on T8) **1,570 instructions/sample** at
its worst block; core 1 (Character + BusDelay on T1, Spectrum + SEND on
T2–T4) **702**. ⚠️ Instructions, not cycles — and the 3,120 wall was
triangulated in `tools/build/cycle_count.py`'s units (words in the sample loop),
so the STATIC sum is the comparable floor: for this layout **core 0 = 3,005**
(BusVerb 1,408 + Modulation 434 + 2 × Spectrum 341 + Character 436 + 3 × SEND
15) and **core 1 = 2,812** (BusDelay 1,308 + Character + 3 × Spectrum + 3 ×
SEND). Core 0 sits 115 under the wall before contention — the same class as
the tag-91 hang at 3,106. The meter reads about half the static count
(multi-word instructions count once) and is the per-block, init-inclusive
shape of the load, not a second calibration. The ColdFire port measured the
same rig under the firmware's own dispatch (`--dsp-stopwatch` on the four
call sites, `docs/firmware/COLDFIRE_PORT.md` O13, 9 Sep 2026): core 0 24,654 a frame
against the meter's 24,971, core 1 15,177 against 14,880 once T1's
CHARACTER is live on both — the meter reads the real load within 2 %.

**The mixer model (12 Sep 2026, `tools/harness/mixer.py`).** The unit's
gain chain around the DSP, measured under the ColdFire port
(`docs/firmware/COLDFIRE_PORT.md` O14, 26 runs, residuals −100 dB and
better): **AMP VOL is (v/127)² and AMP BAL a balance (near side unity, far
side to zero on a cubic), both applied BEFORE the FX chain by the stock DSP
code `dsp_host` never runs; track LEVEL is (L/128)², applied AFTER, at the
mix.** `rig_render` applies them by default — the stem through VOL² and the
balance per side into the chain (`dsp_host -stereo`), each track's chain
output through LEVEL² into `mix.wav`, which is now the main out (saturated
as a 24-bit sum, clips counted) and not a −6 dB unity sum. The values come
from the part with `--project` (the AMP row six bytes before the FX1 row,
the LEVEL pair at +0x1b) or the unit's defaults (VOL 64 = −11.9 dB, BAL
64, LEVEL 108 = −3.0 dB); `--mix T1:VOL=127,BAL=64,LEVEL=100` overrides;
`--mixer off` is the old harness to the bit. A stem is the VOICE at its
sample GAIN (`--amp` defaults to 1.0 with the model on), so a 0 dBFS file
enters the engine at 0.254 FS at the default VOL — the old default
(`--amp 0.5`, no AMP stage) drove every engine 5.9 dB hotter than the
unit does, which every voicing note before this date inherited. `T*.wav`
stay the chain output (before LEVEL). Not modelled: the main level (scales
trigged voices, not THRUs — unity here), the cue mix, the master track;
and the AMP stage was measured on a THRU and is inferred for FLEX/STATIC
(falsifier in `mixer.py`'s docstring).

What it still is not: the ColdFire. Knobs are poked into `r6`, samples do
not play (stems stand in), and the stock DELAY is not on the DSP at all.

**The first thing it was built for** (`tools/verify/verify_onebus.py`, in `make
check`, same day): the one-aux rig's chain, liveness stamps, MIX
passthrough, last-live-stage return, track-8 send refusal and station
silence, all with the senders and the delay on payload B and the reverb and
the return on payload A — `docs/effects/BUS.md` "The one aux bus".

## port_compare.py — the harness against the firmware, one part (12 Sep 2026)

`make port-compare PROJECT=dir [IMAGE=... REMIX=...]` runs ONE part under
the ColdFire port (the firmware booting the image, loading the project
from a staged card, the sequencer running with a probe on the ESAI inputs)
and under `rig_render` on the same image with each track's chain input —
the port's own 84-word record audio — as its stem, and fits the two per
track (lag, least-squares scale, per-window residual) and the port's TX0
main slot against `mix.wav`. ~90 s. Read it as: a linear chain fits to
0.00 dB and −100 dB or better (the mixer model, the parameter path and the
dispatch all agreeing with the firmware); an engine with history — the
reverb's free-running allpass modulator, the delay's LFO — matches in
**scale** and not in residual (O12), so read the scale there; a scale that
is not 0 dB on a linear chain is a finding. Measured on the day it landed:

| fixture | track | scale | residual |
|---|---|---|---|
| O9d's (stock image, T1 THRU: SEND + EQ flat, tone) | T1 chain | −0.001 dB | −121 dB |
| same | mix (TX0 slot 2 vs `mix.wav` L) | −0.001 dB | −113 dB |
| the one-aux rig, flash-7 image, kick on T2's inputs | T2 chain (SPECTRUM + SEND) | −0.001 dB | −137 dB |
| same | T8 return (delay → reverb, history) | −0.083 dB | −8 dB |
| same | mix | −0.001 dB | −90 dB |

Rules it learned: a track whose record carries audio but whose chain
output is digital zero is a non-THRU machine's record (not that track's
chain input, O10) and is listed, not compared; a host or a return has
output and no input of its own and is compared on its output with a
silent stem; the lag search is ±96 because on a periodic probe the fit is
ambiguous modulo the period (147 samples at 300 Hz — the first run
reported −179 for the 32-sample record pipeline); the master track is
turned off in the COPY of the project the port loads, so TX0 is the mix
(the RIG's T8 master carries stock LO-FI). Use a transient probe
(`--tone out/o9d/kickAB_late.wav`, after the knob slew) for anything
with a delay in it — a tone cannot separate a gain from the phase of a
repeat.

## What the harness cannot see

Every item here has cost a real session at least once. Local-clean does not
mean hardware-clean; when the two disagree, believe the hardware.

* **The hardware's cross-core timing.** Two emulated cores run lock-step
  or under a chosen interleave, never under the chip's real skew, and no
  SRAM contention is modelled. A local "clean" under every `-skew` is still
  not evidence the race fix holds — the XBUS accumulator race shipped for
  months behind a local "clean" (`docs/effects/XBUS.md`), and it would again.
* **The cycle budget.** The emulator happily renders an engine the chip
  cannot afford; 432 cycles/sample over once froze the unit. `make cycles`
  bounds it, hardware proves it.
* **The ColdFire side.** `-params` pokes r6 directly, bypassing menus,
  descriptors, ranges and scene logic entirely (the gain chain around the
  chain — AMP VOL/BAL, LEVEL — is measured and modelled since 12 Sep 2026;
  the main level and the cue are not). A slot can draw a knob and
  publish nothing, or publish and draw wrongly — the panel and the DSP are
  separate mechanisms and the harness only exercises one of them
  (`docs/firmware/PARAM_PAGES.md`).
* **Whatever the metric is structurally blind to.** The spur metric sums
  energy against a 438 Hz fundamental; it reported −45 dB "clean" on audio
  hardware later showed carrying +22 dB of inharmonic block-rate hash,
  because a ~2940 Hz discontinuity is not a harmonic of 438 Hz. Before
  trusting a null result, ask what the instrument physically cannot see.
* **What only ears catch.** GRAIN's right-channel hiss (a re-latching bug)
  passed every automated check green and was found by listening. The
  listening protocol in `docs/effects/VOICING.md` is part of the harness, not an
  afterthought.

The functional baseline for "what the sim can prove" is `docs/remixer/TESTPASS.md`
(24 checks, plus the instrument bugs found before any code was blamed). The
protocol for the measurements that *do* need hardware is `docs/effects/CAPTURE.md` —
predictions committed before measuring. The bring-up history of dsp_host,
including how the ABI was recovered and why the stock effects cannot be run
locally (their audio arrives by ColdFire-programmed DMA), is `docs/firmware/DSP.md`
§6b.
