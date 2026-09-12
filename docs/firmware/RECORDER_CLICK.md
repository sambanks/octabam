# The recorder loop click — what it is, and how to test the fix

**For Bryan T, and anyone else who records loops on the Octatrack's recorder.**

You reported a click at the loop point when recording a bar into the
recorder and looping it back — sound-on-sound. 128 BPM clicks, 120 BPM does
not. This is what it turned out to be and how to check whether the patch
fixes it on your unit, because **it is not fixed until it is fixed on
somebody else's machine.**

> ⚠️ This is not official Elektron firmware. Flashing a modified OS can leave
> the unit unusable until you recover it, and puts your warranty in question.
> Nothing here is endorsed by, supported by, or affiliated with Elektron.
> Read `docs/remixer/FLASHING.md` — especially how to recover — BEFORE you
> flash. Build your own image from your own copy of the OS; we do not
> distribute images.

---

## 1. What it is

**A bar is not always a whole number of samples.**

At 128 BPM a bar is exactly **82,687.5** samples. The recorder can only
write whole samples, so the length converter writes **82,687** every pass.
But the sequencer keeps the halves and fires each recorder trig at
`floor(k × 82,687.5)`, so consecutive arms are **alternately 82,687 and
82,688 samples apart**.

On every pass where the arm came one sample later than the recording ended,
**one sample of your input is never recorded**, and the loop's wrap splices
two moments that are two samples apart instead of one. That is the click.

At 120 BPM a bar is 88,200 samples — exact — so the arms are evenly spaced,
nothing is skipped, and it is clean. That is your own control, explained.

Your `~6th repeat` onset at RLEN 4 is the same arithmetic with a different
fraction: at RLEN 4 the period is 20,671.**875** samples, so the sample is
lost once every **eight** passes rather than every other one.

**Only 46 of the 1,401 tempi from 60.0 to 200.0 give a whole-number bar.**
128 is not one of them. 120, 125, 126, 135, 140, 144 and 150 are — so
**you can dodge this today with no patch at all** by working at one of those.
The full list is `out/hw/softretrig/tempo_seam.py` (run it with no
arguments).

There were two other, louder faults stacked on top of this one — the voice
was being restarted from scratch at every loop (a chirp and a burst of
hash) and the read pointer was being reset onto alternating samples. Those
are separate fixes (`FLEX SEEK BIND`, `FLEX SEEK BIND CTR`) and they are
**not** in the image below. See §4.

## 2. The patch

`modules/recorder-spacing` — one ColdFire code cave, 146 bytes, hooked on
the last three instructions of the length converter. It works out where the
next arm will land from where the **current** one did (the sequencer's own
`floor(k × period)` grid, reconstructed by integer arithmetic) and makes the
recording exactly that long. No prediction, no lookahead, no state kept
between passes.

At any tempo whose bar is already a whole number of samples it writes back
the length that was already there — a **bit-exact no-op**, proven for all
11,208 (tempo, RLEN) pairs and observed over 21,000 emulator calls at 65.6.

Build the minimal image — this cave and **nothing else**, so the FX2 list
and every other behaviour stay stock:

```bash
make os                                  # extracts your own downloaded 1.40C
make check REMIX=recfix                  # every gate, no hardware
make image REMIX=recfix BUILD=84         # -> out/OCTATRACK_OCTABAM84.bin
```

Sam's build of that image is sha256 `2f38d9d1…` — yours should match if your
stock 1.40C does (`370c55a3…`); if it does not, say so before flashing, because
that is a difference worth understanding.

Then `docs/remixer/FLASHING.md`. Card route: copy the one `.bin` to the card
root, power off, hold **FUNC**, power on → STARTUP MENU → **CARD UPGRADE**.

## 3. How to test it

**The fixture.** One track doing both jobs, which is the sound-on-sound
shape:

- T1 = **FLEX** machine, pointed at its own recorder buffer (**R1**)
- recorder source **INAB**, **RLEN 16** (then repeat at **RLEN 4**)
- a **RECORDER trig and a PLAY trig on T1, on step 1**, pattern 1X/16 steps
- **internal clock, 128.0 BPM**
- **FX1 and FX2 off** on T1 — a reverb smears a discontinuity and will hide
  the very thing you are listening for
- feed A/B with something continuous. A steady tone is the most revealing
  (a click is obvious against it); a sustained pad works; a drum loop is the
  worst choice, because the click hides under the transients.

**Listen for:** a tick, once per bar, at the loop point. Before the patch it
is there at 128 and absent at 120. After the patch it should be absent at
both.

**The three checks that matter**, in order:

| # | do this | before the patch | after, if it works |
|---|---|---|---|
| 1 | 128.0 BPM, RLEN 16 | tick every bar | nothing |
| 2 | **120.0 BPM**, same | already clean | **still clean** — if 120 got *worse*, stop and tell us; the patch is supposed to do nothing at all there |
| 3 | 128.0 BPM, **RLEN 4** | tick roughly every 8th pass (your "~6th repeat") | nothing |

Check 2 is the important one. The patch is a no-op at 120 by construction,
so a change there means something is wrong that our own testing did not see.

**If you can record the output**, `out/hw/softretrig/` has the instruments we
used: `gaps.py` predicts each sample from one tone period earlier, so a
steady tone cancels and a hole or a step becomes a spike; `perbar.py` prints
the worst 1 ms of each bar, which is what makes the every-other-bar pattern
visible. A capture beats an opinion, but your ear is the thing we cannot
reproduce here — say what you hear even if you cannot measure it.

## 4. What we have and have not proven

**Measured on one unit (Sam's MKII), 12 Sep 2026**, with a 1 kHz tone into
the self-recording loop, 90 s takes:

| | before | after |
|---|---|---|
| worst 1 ms in each bar, even bars | 1.10× the noise floor | 1.10× |
| worst 1 ms in each bar, **odd bars** | **1.70×** (worst bar 11.5×) | **1.10×** (worst bar 1.11×) |
| bars with anything above 1.25× the floor | 16 of 23 | **0 of 46** |
| 65.6 BPM control | clean | clean, identical floor |
| 132.0 BPM (a different fraction) | — | clean |

After the patch, 128 BPM reads **identically to a whole-number tempo** — same
noise floor, no per-bar event at any threshold.

**Not proven, and this is why we are asking you:**

- **One unit, one fixture, one session.** Only ever flashed on an **MKII**.
  The MKI runs the byte-identical stock OS so it is plausibly fine, but
  nobody has done it.
- **Tested stacked, not alone.** The hardware result above is from an image
  carrying this cave *plus* the two other fixes from §1. `recfix` is this
  cave **by itself** and has been gated in the emulator only — whether it is
  enough on its own is exactly what your test answers. If you still hear a
  chirp-then-click rather than a clean tick, that is the voice-restart fault
  and you need the other two as well; say so and we will build that image.
- **Real material over long periods.** Our measurements are a tone for 90
  seconds. Whether a half-hour of layering stays clean, nobody knows.
- One isolated blip (2.3× the floor, one bar in 47) turned up in the 132 BPM
  take and is unexplained. It is not bar-periodic and looks like a dropout
  rather than the seam, but it is on the record.

If it does not fix it for you, that is the useful result — the arithmetic
above is exact and measurable, so a click that survives it is a *different*
click, and knowing that is worth more than a confirmation.

## 5. Where the detail is

- `docs/firmware/RTOS_FORK.md` §10.53 (the diagnosis and the tempo table),
  §10.55 (a fix that failed, and why), §10.56–10.57 (this cave and its
  gates), §10.58 (the hardware result)
- `modules/recorder-spacing/` — the cave, its source and its arithmetic
- `out/hw/softretrig/tempo_seam.py` — which tempi are affected, any RLEN
- `out/hw/softretrig/lever_e.py` — the arithmetic gate, 115,200 cases
