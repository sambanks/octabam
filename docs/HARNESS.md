# The harness — hearing and measuring the effects without hardware

Flash cycles are expensive: every hardware test is a manual firmware write.
The harness exists so that almost every judgement — voicing, gain structure,
knob behaviour, refactor safety — can be made on the desktop, and flashes are
spent only on the things no emulator can prove (see the last section, which
is as important as the rest of this page).

The one-line claim, and why it is trustworthy: **the harness runs the real
assembled instruction stream on a cycle-exact DSP56300 emulator.** It is not
a model of the reverb; it is the reverb, executed by
[dsp56300](https://github.com/dsp56300/dsp56300)'s emulator core at roughly
6× real time. When a render sounds wrong, the code is wrong — modulo the
blind spots listed at the end.

## The stack

```
modules/*/*.asm (+ dsp/ probes)
          ──dsp_asm──► tools/build_bus.py ──► out/mainos_bus.bin   (the firmware)
                              │
                              └─► out/dsp/mem_*.mem      (payload A memory dump,
                                        │                 via dsp_modmap --dumpmem)
                                        ▼
                            tools/dsp_host  (C++, vendor/dsp56300 emulator)
                              loads the dump, seeds the frame context,
                              calls init/proc through the recovered ABI,
                              captures the audio buffer every block
                                        │
                    ┌───────────────────┴────────────────────┐
                    ▼                                        ▼
        tools/render_reverb.py                     tools/send_probe.py
        wav in → wav out, by ear                   tone in → numbers out
        (make reverb IN=..)                        (make render / render-delay)
```

Three commands cover most days:

```bash
make reverb IN=loop.wav ARGS='--wet --mode all'   # hear ChonVerb
make render                                       # the full bus, SEND → REVERB
make render-delay                                 # BongDelay via the DEV hatch
```

## dsp_host — the emulator harness

`tools/dsp_host/dsp_host.cpp` (~900 lines, heavily commented — the comments
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
`docs/PARAM_PAGES.md`): three words `r6+$c/$d/$e`, each carrying a KNOB field
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

### Blocks are 15 frames here, 16 on hardware

The setup routine masks the frame count with `& 0xf`, so dsp_host caps a
block at 15 frames where hardware runs 16. Nothing audible depends on it,
but sample-exact measurements shift: the bus latency is exactly 2 blocks —
**30 samples locally, 32 on hardware** (measured to the sample, see
`docs/TESTPASS.md`).

## render_reverb.py — judging by ear

`make reverb IN=loop.wav` pushes a wav through ChonVerb and writes a wav
back. `-p NAME=VAL` sets knobs by name, `--sweep NAME=a,b,c` renders one file
per value, `--wet` isolates the tail, `--mode all` renders every character.
Voicing decisions in `docs/VOICING.md` are all listening results from this
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
slots in hardware order — `R`=reverb, `D`=delay, `S`=send, `.`=neither, slot
0 being position 0, the housekeeper — so `RS`, `.RS` and `SSR` are different
machines, not different spellings; entry points are
read from the dump's own dispatch tables, never hardcoded, and a `--direct`
control run bypasses the bus for comparison.

The metric: a bin-centred 438.75 Hz sine through a linear system should come
back as one FFT bin. Total non-fundamental energy relative to the
fundamental is the artifact number. Silence is checked *first* and reported
as a failed measurement, never as a clean one — a silent render scores
perfectly on any spur metric.

### The DEV hatch (`make render-delay`)

The shipping build (`SPEC=1`) puts BongDelay in payload B only — and
dsp_host cannot boot payload B. Worse, a SPEC dump *aliases* the absent
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

## What the harness cannot see

Every item here has cost a real session at least once. Local-clean does not
mean hardware-clean; when the two disagree, believe the hardware.

* **Anything between two cores.** dsp_host boots one core and cannot boot
  payload B at all. No local test will ever reproduce a cross-core race —
  the XBUS accumulator race shipped for months behind a local "clean"
  (`docs/XBUS.md`).
* **The cycle budget.** The emulator happily renders an engine the chip
  cannot afford; 432 cycles/sample over once froze the unit. `make cycles`
  bounds it, hardware proves it.
* **The ColdFire side.** `-params` pokes r6 directly, bypassing menus,
  descriptors, ranges and scene logic entirely. A slot can draw a knob and
  publish nothing, or publish and draw wrongly — the panel and the DSP are
  separate mechanisms and the harness only exercises one of them
  (`docs/PARAM_PAGES.md`).
* **Whatever the metric is structurally blind to.** The spur metric sums
  energy against a 438 Hz fundamental; it reported −45 dB "clean" on audio
  hardware later showed carrying +22 dB of inharmonic block-rate hash,
  because a ~2940 Hz discontinuity is not a harmonic of 438 Hz. Before
  trusting a null result, ask what the instrument physically cannot see.
* **What only ears catch.** GRAIN's right-channel hiss (a re-latching bug)
  passed every automated check green and was found by listening. The
  listening protocol in `docs/VOICING.md` is part of the harness, not an
  afterthought.

The functional baseline for "what the sim can prove" is `docs/TESTPASS.md`
(24 checks, plus the instrument bugs found before any code was blamed). The
protocol for the measurements that *do* need hardware is `docs/CAPTURE.md` —
predictions committed before measuring. The bring-up history of dsp_host,
including how the ABI was recovered and why the stock effects cannot be run
locally (their audio arrives by ColdFire-programmed DMA), is `docs/DSP.md`
§6b.
