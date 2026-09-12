# The recorder loop click — what it is, and how to test the fix

**For anyone who records loops on the Octatrack's recorder.**

The reported symptom: a click at the loop point when recording a bar into
the recorder and looping it back — sound-on-sound. 128 BPM clicks, 120 BPM
does not. This is what it turned out to be, and how to check whether the
patch fixes it on your unit — because **it is not fixed until it is fixed on
a machine other than the one it was developed on.**

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
nothing is skipped, and it is clean. That explains the original report's own
control: 120 was never a lucky tempo, it is an exact one.

It also explains why the click was first noticed "around the sixth repeat"
at RLEN 4 rather than immediately: at RLEN 4 the period is 20,671.**875**
samples, so the fraction accumulates and the sample is lost once every
**eight** passes instead of every other one.

**Only 46 of the 1,401 tempi from 60.0 to 200.0 give a whole-number bar.**
128 is not one of them. 120, 125, 126, 135, 140, 144 and 150 are — so
**you can dodge this today with no patch at all** by working at one of those.
The full list is `out/hw/softretrig/tempo_seam.py` (run it with no
arguments).

**And it was not the only fault.** Two louder ones sat on top of it:

1. **The voice was restarted from scratch every loop** — the DSP was told the
   re-bind was a brand new note, so it re-primed the voice: a chirp, then a
   burst of hash at 140 % of the signal's own level over 300 samples.
2. **The read pointer was reset** onto that same alternating grid, giving a
   ±1.5-sample lurch every bar.

Each was loud enough to hide the ones beneath it, which is why this kept
"not being fixed". **All three fixes are in the image below.**

## 2. The patch

Three ColdFire code caves, **186 bytes of code between them**, and no DSP
code at all:

| module | what it does |
|---|---|
| `FLEX SEEK BIND` | a re-bind on the same buffer is a **seek** for the DSP, not a new note — so the voice is not re-primed |
| `FLEX SEEK BIND CTR` | holds the per-bind counter, so the read pointer is **not reset** — the read head free-runs |
| `RECORDER SPACING` | makes each pass exactly as long as the gap to its next arm, worked out from where the **current** arm landed (the sequencer's own `floor(k × period)` grid, reconstructed by integer arithmetic). No prediction, no lookahead, no state kept between passes |

At any tempo whose bar is already a whole number of samples, `RECORDER
SPACING` writes back the length that was already there — a **bit-exact
no-op**, proven for all 11,208 (tempo, RLEN) pairs and observed over 21,000
emulator calls at 65.6.

The `recfix` build is **these three and nothing else of ours**. It also lists
the fourteen stock FX2 effects, which costs nothing at all and is what keeps
your unit normal: every octabam image rebuilds the FX2 chooser from the
remix's contents, so without that line the FX2 list would come up empty and
you could not select an effect (your saved projects would still play — the
effect code and dispatch are untouched — but you could not change one).

```bash
git clone --recurse-submodules https://github.com/sambanks/octabam
cd octabam
make setup                               # vendored tools
make os                                  # extracts YOUR OWN downloaded 1.40C
make check REMIX=recfix                  # every gate, no hardware needed
make image REMIX=recfix BUILD=84         # -> out/OCTATRACK_OCTABAM84.bin
```

**On the submodules** (verified on a fresh clone, 12 Sep 2026): `make bus
REMIX=recfix` builds fine **without** them, but `make check` runs every remix
in the repo — including two that wrap other people's code — so it needs them
even though `recfix` does not. If you cloned without `--recurse-submodules`:

```bash
git submodule update --init --recursive
```

`make check` now says exactly that if they are missing, rather than throwing a
Python traceback at you (it used to; sorry).

**Always pass `REMIX=recfix`** -- to `make check`, `make bus` and `make image`
alike. The Makefile's default is a different remix, and every verifier reads
the one image at `out/mainos_bus.bin`, so a bare `make bus` (or `make -j`,
which runs the build and the checks at once) leaves another remix's image
for the checks to read. That looked like "32 fails in verify_menu, garbage
past index 2" on 12 Sep 2026 -- the garbage was the other remix's descriptor
text. The build now records which remix wrote the image
(`out/mainos_bus.remix`) and `verify_menu` says so in one line instead.

`make check` is the floor — it builds the image and runs every gate in the
repo without touching hardware. If it is not green, do not flash. Expect
**303 PASS** and `EXIT=0` for `recfix`.

Sam's build of that image is sha256 `ecb574a9…` — yours should match if your
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
| 3 | 128.0 BPM, **RLEN 4** | tick roughly every 8th pass (the "~6th repeat" of the original report) | nothing |

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
- ✅ **`recfix` itself is now measured, not just the image it came from.**
  The table above was OCTABAM83, which carried these three caves *plus* our
  DSP effects. `recfix` (OCTABAM84) drops those, and re-flashing and
  repeating the capture gives **even bars 1.10× / odd bars 1.10×** with a
  residual floor of **2.67 % of rms — identical to 83's**. So the build you
  are being handed is the one that was measured. (RTOS_FORK §10.59.)
- **We do not know whether all three fixes are needed.** They have only ever
  been tested together. If you are curious, the individual modules can be
  built separately — but start with all three.
- **Real material over long periods.** Our measurements are a tone for 90
  seconds. Whether a half-hour of layering stays clean, nobody knows.
- **A sporadic blip, about one per 45–90 s take, that we cannot account for.**
  It shows up on every image — including the *broken* one — at roughly one
  isolated event per take (1.6× to 11.5× the noise floor), at no repeating
  bar position. The seam's signature was 16 of 23 bars on a regular grid, so
  this is something else: a dropout somewhere in the capture or output path
  is the guess, and nobody has tested it. If you hear an occasional tick that
  is clearly *not* once-per-bar, that is probably this and it is not new.

If it does not fix it for you, that is the useful result — the arithmetic
above is exact and measurable, so a click that survives it is a *different*
click, and knowing that is worth more than a confirmation.

## 5. Where the detail is

- `docs/firmware/RTOS_FORK.md` §10.53 (the diagnosis and the tempo table),
  §10.55 (a fix that failed, and why), §10.56–10.57 (this cave and its
  gates), §10.58 (the hardware result)
- `modules/recorder-spacing/`, `modules/flex-seekbind/`,
  `modules/flex-seekbind-ctr/` — the three caves, their sources and their
  arithmetic
- `remixes/recfix.py` — what is and is not in the image, and why
- `out/hw/softretrig/tempo_seam.py` — which tempi are affected, any RLEN
- `out/hw/softretrig/lever_e.py` — the arithmetic gate, 115,200 cases
