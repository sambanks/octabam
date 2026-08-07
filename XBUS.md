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

## STATE AS OF 7 Aug 2026, END OF SESSION — read this first

**The send path is BROKEN, and it is a REGRESSION.** A `SEND` feeding
`ChonVerb` produces a robotic/metallic/"formanty" artifact — on the plain
build (`BASE30`, scratch at `Y:0x900`), and identically on both XBUS builds.
One trig versus many changes only whether it is a single decaying event or
continuous; the artifact is there either way.

**So none of the cross-core work caused it, and the address was never the
issue.** Two flashes went into chasing `0x3E000` and then `0x36000` before this
was established, because the bus was ASSUMED to work. It had never been shown
to: hardware tests 1–4 in `BUS.md` cover the menu, the ids, both servers on
their OWN tracks, and a SEND cold-boot freeze — none of them is a send being
HEARD reaching a server. The emulator check poked a value INTO the ACC buffer
and watched it come out of the server, which exercises the server's READ, not
the client's WRITE.

**Where the regression must be.** `dsp/send_client.asm` has only ever had two
commits: the original "running on hardware" (`40f7167`) and the XBUS change.
The sender is unchanged from when it worked. So the break is in one of the
**24 commits to `dsp/reverb_server.asm` since `40f7167`** (`git log --oneline
40f7167..HEAD -- dsp/reverb_server.asm`).

Already checked and CLEAN — do not re-check:
- the reverb's bus ACC read inside the sample loop is **byte-identical** to the
  working version
- no r7 slot the bus uses (`$63 $64 $65 $67 $68 $69 $6a $1b`) has been stolen
- the `mpy` mis-encoding is a red herring HERE: `mpysu` is numerically correct
  whenever the second operand is a positive coefficient, which it always is in
  this code, and `reverb_server` has 16 such sites while sounding correct
- SHMR defaulting to 48 (a real bug, now fixed to 0) is NOT the cause — Sam
  confirmed the reverb sounds right on the device, and SHMR does nothing on
  XVerb29

**BISECT IT LOCALLY — no flashes needed.** `dsp_host` takes `-inst N`, and
ChonVerb is its OWN send client (it sums its own dry into the shared ACC and
reads it back), so `-inst 2` puts one instance's audio through the accumulator
into another's — the send path in miniature. Build each of the 24 commits, run
`-inst 1` against `-inst 2`, find where they diverge.

⚠️ **The trap that invalidated the first attempt: the engine stays DRY for 256
CALLS.** A test source that stops inside that window measures only the dry
period — it produced `tail_rms = 0.00000` and looked like a finding. Put the
source AFTER the warm-up and use a tone (a square, for odd harmonics), not
broadband noise, which masks the artifact.

**On the card right now: `OCTATRACK_BASE30.bin`** — the plain build.

## Path, in order, with the gate at each step

0. **Fix the send-path regression** (above). Everything below is blocked on it.
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
