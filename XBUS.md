# The target architecture: one reverb, one delay, all eight tracks

Agreed 7 Aug 2026. This supersedes `BUS.md`'s bank-scoped design, whose founding
constraint — "the two DSPs are a hard boundary" — is now known to be false.

## What we're building

```
CORE 0   track 1   ChonVerb      pools all 4 of core 0's FX2 slots  = 65,536 words = 1.49 s
         2,3,4     Send
CORE 1   track 5   BongDelay     pools all 4 of core 1's FX2 slots  = 65,536 words = 1.49 s
         6,7,8     Send

         every track sends to both, through accumulators in the shared window
         delay wet -> reverb  (series, the direction that is already built)
```

**Two wins, and they are different resources.**

*Cycles*: each core runs ONE effect with its full ~4,535 cycles/sample instead
of both cores running both effects. Roughly doubles the effects budget.

*Memory*: 372 ms → 743 ms (done, the 32K re-layout) → **1.49 s**. Four slots per
core instead of two, because a core no longer has to house a reverb *and* a
delay.

**What the memory actually buys, since this is easy to get wrong: NOT a longer
tail.** The current engine already does 8.7 s RT60 out of 743 ms of buffer —
tail length comes from feedback gain. More memory buys longer taps, longer
pre-delay and lower modal density, i.e. a **bigger, smoother space**. 743 ms is
exactly why `REVERB.md` ruled out Blackhole-class and substituted a
Valhalla-flavoured big mode. 1.49 s reopens that.

## STATE AS OF 7 Aug 2026, SESSION 2 — read this first

**The send path is NOT broken, and there is NO regression in
`reverb_server.asm`.** Both claims from session 1 are now falsified by
measurement. The artifact is real on hardware but is **not reproducible in the
emulator under any send configuration**, so its cause is something `dsp_host`
does not model.

### What was actually built

Session 1's bisect plan could not have worked, for three independent reasons:

- ChonVerb **never writes** the REVERB accumulator. It *reads* it (`r7+$63`)
  and writes the **DELAY** accumulator (`r7+$68`). Only `send_client.asm`
  writes the REVERB one, so with no SEND instance the reverb reads all zeros.
- The server-role lock (`y:>$982`) makes a second REVERB SERVER instance `rts`
  immediately as a dry passthrough — so `-inst 2` gives one working reverb and
  one passthrough, not a send.
- `dsp_host` took ONE `-init`/`-proc` pair, so every instance ran the same
  effect. Its own source said so: *"a true mixed-effect multi-instance run
  isn't possible"*.

`dsp_host` now takes a **list** for `-init`/`-proc` (one entry point per
instance), plus `-inmask` (which instances receive input) and a **per-instance
`-split`** (tracks trig independently, so the per-track frame offset can
differ between the sender and the server). `tools/send_probe.py` drives it:
instance 0 = REVERB SERVER at `r7 0x6200`, instances 1..N = real SEND clients,
the tone fed to the SENDs only so everything in the reverb's output arrived
over the bus.

**This is the first time the send path has been exercised end to end
anywhere** — hardware tests 1–4 never did it, and the earlier emulator check
poked a value into the ACC, exercising the server's read, not the client's
write.

### What was measured

| Question | Result |
|---|---|
| Does the bus carry audio at all? | **Yes.** Reverb with its own input silenced still produced 175,972 non-zero samples. |
| Is the send path faithful? | **Yes.** SEND vs DIRECT input track within **0.3 dB THD at every level** (−11.08 vs −10.81 hot; −36.18 vs −36.17 clean). |
| Is there a regression across the 24 commits? | **No.** THD drifts smoothly with voicing; no step. `40f7167` is itself *worse* than the commit after it. |
| Do mismatched per-track splits break it? | **No.** All combinations ≈ −36.2 dB. |
| Do multiple sends break it? | **No bug.** They sum linearly: 4 sends @0.15 and 2 sends @0.3 give *identically* −6.44 dB (same total level). |
| Cycle budget? | **Not close.** Reverb 33 instr/sample, each SEND 3.7 — ~44 for reverb+3 sends against a ~2400/sample ceiling. |
| `init` re-invoked most blocks? | **Irrelevant.** Both `init` routines are a bare `rts`. |

**Sam listened to all of it** — one send hot, direct-input control, three sends
at 3× overload — and every render **sounds fine**. So the emulator does not
reproduce the artifact.

### One real (separate) finding

The reverb saturates above roughly **0.35 FS input**, and *N* send tracks sum
linearly into it with nothing dividing by *N*. Odd harmonics dominate (3f
strongest), and the single best row in the whole sweep is `729c50a` "Tank input
attenuation: −12 dB of headroom" at −22 dB. This is a genuine gain-staging
weakness worth fixing on its own merits — but it is **not** the reported
artifact, because Sam cannot hear it on musical material.

### WHAT THE ARTIFACT ACTUALLY IS — measured from hardware

Sam recorded the device (`out/hw/fade_send.wav`: ChonVerb on track 1, the
`->REVERB` send faded up on track 2). `tools/capture_hw.py --timeline` reads it.
The artifact enters at ~4.5 s and is **discrete HF lines ADDED ON TOP of an
otherwise intact signal** — not a replacement, not saturation:

| | before | after | change |
|---|---|---|---|
| 2.5–5 kHz | −45.2 dB | −25.1 dB | **+20.1** |
| 5–10 kHz | −56.6 dB | −32.2 dB | **+24.4** |
| 10–20 kHz | −59.8 dB | −40.3 dB | **+19.6** |
| spectral flatness | −56.0 | −47.5 | +8.5 |
| rms | −36.3 | −34.8 | +1.5 |
| **top-8 bins** | **95.3 %** | **95.3 %** | **0.0** |

The music is untouched (top-8 unchanged); ~20 dB of HF arrives alongside it.
HF peak/mean is **40.9 dB**, so these are DISCRETE LINES, not noise.

**Ruled out by this data:** block-rate comb (measured −63 dB, absent — so it is
NOT a per-block indexing fault); saturation (the signal is intact); `MOD` depth
(sweeping it moves HF only ~7 dB against the +20 needed).

**Sam's two observations, which are the best clues available:**
- Severity tracks MODE, **worst at 1 → least bad at 4**, still present at 4.
- It sounds like "an almost audio-rate LFO".

### The `$2f` audio-rate-LFO lead — MEASURED, and it does NOT hold

`x:(r7+$2f)` really is used for two things (the md_ blocks park MODE's LFO rate
scale there; the RATE block at 1229-1231 overwrites it with the final phase
increment). The per-mode scales are ROOM `$599999` (0.70), PLATE `$7fffff`
(1.00), HALL `$399999` (0.45), BIG `$200000` (0.25).

**But rendering all four modes does not support it.** If severity followed the
scale, BIG (0.25) would be the quietest. It is the LOUDEST by ~30 dB:

| UI mode | `$2f` | 2.5–5 kHz | 5–10 kHz | HF peak/mean |
|---|---|---|---|---|
| 1 ROOM | 0.70 | −77.8 | −85.9 | 44.6 dB |
| 2 PLATE | 1.00 | −66.8 | −77.1 | 43.3 dB |
| 3 HALL | 0.45 | −83.0 | −94.0 | 54.9 dB |
| **4 BIG** | **0.25** | **−48.9** | **−52.5** | **11.6 dB** |

Two things are wrong with it as a theory of Sam's artifact: the ordering is
backwards (Sam hears BIG as the MILDEST), and BIG's peak/mean of 11.6 dB is
NOISE-LIKE, whereas the hardware artifact is discrete lines at 40.9 dB.

**Retained as a lead only for BIG's own +30 dB of broadband HF**, which is a
real defect in the emulator and worth explaining on its own — but it is a
different phenomenon from the reported artifact, and no mode reproduces the
hardware's discrete-line signature.

### The `MODE=` override WORKS — a retracted blocker

v115 recorded this as a silent no-op. **That was a testing error, not a tool
bug.** `MODE=n` writes `out/mainos_bus_mode<n>.bin`, NOT `out/mainos_bus.bin`;
the test copied the latter, which a MODE build never touches, and so compared
two copies of the ordinary build. The per-mode images differ correctly (2 bytes,
the substituted immediate), and `render_reverb.py --mode` was right all along —
it reads those per-mode paths deliberately.

So per-mode voicing in `VOICING.md` is **not** invalidated. Retracting that too.

**Verify a MODE build by `cmp`-ing `out/mainos_bus_mode*.bin`** — never
`out/mainos_bus.bin`.

### SHMR: untestable, not excluded

`SHMR` (slot 6 → `r6+$b`) is **not wired on hardware** — Sam confirmed the knob
does nothing at 0 or at maximum. So it sits at the build's default, and the card
runs `OCTATRACK_BASE30.bin` (`0d4248c`), which PREDATES `41d252c` "SHMR defaults
to 0: a fresh part was booting with the shimmer half up". The card therefore
boots with **SHMR = 48, shimmer running, and no way to turn it off**.

In the emulator SHMR=48 adds **+19.8 dB at 2.5–5 kHz**, against the hardware's
+20.1 dB. That is a good match, but it proves nothing on its own: the knob being
dead means the device test could not falsify it either way. **Deciding it needs
a flash with a post-`41d252c` build.** Note `send_probe.py --shmr` drives it
locally; `render_reverb.py`'s PARAMS still mislabels index 6 as "SPEED" (v101
renamed that slot), which is why every earlier render had the shimmer off.

### Other things `dsp_host` still does not model

1. **The real dispatcher.** The manual instance loop hand-rolls the calling
   convention from a reading of the listing, and *"a mistake in that reading is
   invisible here — which is how the A-flag bug survived six builds"*. There is
   already a faithful `-dispatch` mode that runs the host's own dispatcher at
   `P:0x372`, but it has **no audio I/O** and applies one `fxid` to every track.
2. **Payload B / the second core**, which `dsp_host` cannot boot at all.
3. **ColdFire-side parameter delivery.** `-params` pokes `r6` directly and
   bypasses the menu, descriptors and ranges — and the SHMR slot above proves
   the two do NOT agree: a slot dsp_host drives fine can be dead on hardware.

⚠️ **Traps, all of which have now cost a wrong conclusion:**
- **Zeroing a parameter to clean up a metric hides the bug that parameter
  causes.** `MOD=0` and `SHMR=0` were set to keep LFO sidebands out of the THD
  number, and between them they suppressed the two most likely mechanisms for
  most of the session. Measure with parameters at their DEFAULTS first.
- The engine stays **DRY for 256 CALLS**. A source stopping inside that window
  measures only the dry period — it produced `tail_rms = 0.00000` and looked
  like a finding. `send_probe.py` pads past it and treats silence as a FAILED
  measurement, never a clean one.
- **`tools/dsp_host/` is the source of truth but is COPIED into
  `vendor/dsp56300/source/dsp_host/` by `setup.sh`'s `stage_dsp_host`.**
  Building without re-copying silently runs the OLD binary. This invalidated an
  entire first pass of results — the giveaway was two supposedly different
  renders coming out byte-identical. Always `cp` then build, and check a new
  flag actually appears in the output.

**On the card right now: `OCTATRACK_BASE30.bin`** — the plain build.

## Path, in order, with the gate at each step

0. **Find the metallic artifact.** It is NOT a send-path regression — the bus is
   exonerated, and the `$2f` LFO lead is measured and dead (above). What is left:
   (a) explain BIG's +30 dB of broadband HF — a real defect, though not the
   reported one; (b) instrument the LFO phase with `-peekx` to MEASURE its rate
   per mode rather than infer it; (c) flash a post-`41d252c` build to settle
   SHMR, which the dead knob makes untestable any other way. No emulator
   configuration has yet reproduced the hardware's discrete-line signature, so
   the cause is still something dsp_host does not model.
1. **Does the relocated bus still work SAME-CORE?** ← *cannot be judged until 0
   is fixed; the artifact appears on the plain build too.*
   `XBUS28` put the scratch at `0x3E000` and it broke even with both effects
   on ONE core — so cross-core was innocent and the address was the fault.
   `0x3E000` is outside the init pass that zeroes `0x30000-0x37FFF` (so it
   comes up as garbage) and payload A had never been shown to write there at
   all: `alias_probe` only ever tested payload A in the LOWER half. `XBUS29`
   retries at `0x36000` — inside the zeroed region, and between two addresses
   payload A has demonstrably written and read back. **Nothing below means
   anything until this is clean.**
2. **Does a cross-core send arrive?** Send on track 5, reverb on track 1.
   Already known to carry *something* — it scaled with the send dial — so this
   is about whether it arrives *intact*.
3. **Synchronisation.** Expected to be needed. The two cores have independent
   splits and block alignment, and the bus's frame offset is per-track; a
   cross-core send cannot use it. The ICC (cross-core interrupts + data
   registers, RM 1.4.14) is the untouched tool for this.
4. **Re-plan the memory** against `CHIP.md` §3a — four slots per core, in two
   non-contiguous regions, dodging stock's 72-word staging at
   `0x30000-0x30047` (rewritten EVERY FRAME) and using the fact that the
   bootstraps at `0x31000`/`0x32000` are dead after boot.
5. **Then the effects**: the shimmer (the reverb is not finished — the shimmer
   verb is not usable), and BongDelay, which is an untested first draft.

## Constraints that shape it

- **`0x36000` is inside core 0's FX2 slot 4.** Fine while every core-0 track is
  ChonVerb (hardcoded `Y:0x4000`) or a Send (zero-footprint). NOT fine once the
  reverb pools all four slots — the accumulators need a permanent home that is
  not an FX2 slot. Candidate: the free low-Y window `0x795-0xFFF` is core-
  private and therefore useless here; this needs solving in step 4.
- **Modulo addressing needs power-of-2 alignment**, so a 16,384-word buffer in
  the shared window must start at `0x30000` or `0x34000`. `0x34000-0x37FFF` is
  clean; `0x30000-0x33FFF` has the staging in its first 72 words.
- **The two regions are not contiguous** (`0xC000-0x2FFFF` is absent), so no
  single 65,536-word buffer. Irrelevant for a bank of separate lines.
- **Series is one-directional**: delay wet → reverb is allowed and built;
  reverb wet → delay is forbidden, it closes a feedback loop.
- **One block of latency already exists** by design (everyone reads the
  previous block's summed buffer). Cross-core adds at most one more. ~0.36-0.7
  ms; inaudible for a send.
