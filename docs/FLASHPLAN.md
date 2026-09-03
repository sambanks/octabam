# The flash plan — clearing the backlog on hardware

**What is on the unit today: tag 77 / R58, flashed 24 August 2026.** Since
then, 134 commits on `main` plus the current branch. None of it has been on
Sam's Octatrack.

This page is the plan for putting it there: what is untested, which flashes
prove which claims, what to listen for, and — the part that matters — **what
would falsify each claim.** Flash cycles are the expensive resource here
(each one is a manual firmware write), so the images are shaped to stack as
many independent claims as possible *while keeping their failures
distinguishable*. `docs/FLASHING.md` is the procedure; this is the schedule.

---

## 0. What is actually unflashed

Three classes, and only two of them need hardware.

### A. Proven not to change the image — no flash needed

The modules/remixes platform, the remixer, the ColdFire emulator, the FX1
plumbing at its default, and the dynamic-donor refactor at its default are
all **bit-identical** to what they replaced: `scripts/refhash.sh check`, 26
configurations, artifacts *and* build reports. That is the whole point of
that gate. Nothing below tests them, because there is nothing to test.

⚠️ What refhash proves is that a *default* selection is unchanged. It says
nothing about a selection that uses the new capability — which is what
flashes 2 and 3 are for.

### B. Changes the shipping image — flash 1

| | what it changes | first flashed |
|---|---|---|
| BongDelay R59–R62 | GRAIN density was a 2-position switch (now a full dial) + makeup gain; REVERSE default = 93 ms segment; the −19 interval swap | never |
| Stepped-select labels (PLAN §6) | twelve selects print words instead of `1 2 3` — `Param.labels` was authored, schema-checked and never read until 2 Sep | never |

### C. New capability, never on hardware at all — flashes 2 and 3

| | claim | evidence so far |
|---|---|---|
| Stock effects listable | our servers and stock effects coexist on one chooser; the reverbs come back where the placement never reached them | build + ledger only |
| The insert card | five inserts of ours stack, and four copies of the dearest fit one core's cycle budget | `cycle_count` is a **floor**, not a measurement |
| A module on FX1 | FX1's chooser relocated into the cave, its three `lea` refs repointed, its own id **and cursor** tables written | ColdFire emulator only |
| A donor region beyond the reverbs | any stock effect's words can be taken; every one is self-contained | `dsp_reach` over both payloads — **static** |
| Hello World (Bryan T) | builds and runs | flashed on **his** unit, not Sam's |
| **The returns** (3 Sep 2026) | the engines' wet arrives once, at the master, through the character station in BUS mode (RVRB/DLY); the hosts go quiet ONLY while a return is live, and print as before otherwise | `tools/verify_returns.py` 18/18 and `make verify-bus` 19/19 — single-core: the delay's wet and its RETD stamp both cross cores on the unit, which no local test can see; and `0x360d3-5` next door was dead on hardware for R36 |

---

## Step 0b — a project whose effects are actually set

⚠️ **The effect ids live in the PROJECT, not the OS.** They survive a flash,
so a freshly flashed unit opens every track still holding the id it had
before — which in the new image may be a different effect, or one the image
does not implement (and so resolves to the fallback). That is why a flashed
unit *"keeps the old effect graphics"* until you select something, and it is
why **a flash test that starts from an old project is not a test of
anything**: half the tracks are running whatever the last image left there.

So before flash 1, make a project whose every bank, part and track is stamped
with an id this image implements:

```bash
python3 tools/ot_project.py testproj \
    ~/octa/backups/<a project you trust> /Volumes/<card>/OCTABAM_T1 chongbong
```

It copies (never edits the source), lays out **one effect per part on all
eight tracks**, writes both the current parts and their saved copies,
recomputes each bank's checksum, reads everything back, and drops
`OCTABAM_TEST_MAP.txt` in the project so you can see at the unit what each
part is:

```
bank A  part 1   FX1 0x00  FX2 0x0a   WARPFOLD on FX2
bank B  part 2   FX1 0x04  FX2 0x00   FILTER on FX1
bank D  part 3   FX1 0x0a  FX2 0x0f   WORST by cycles: BODESHIFT on FX2 + WARPFOLD on FX1
```

One effect per part **on all eight tracks** is deliberate: selecting a part
then auditions that effect across both cores at once, which is the shape the
cycle test wants and the shape that shows a payload asymmetry immediately —
tracks 5–8 are payload A, 1–4 are payload B. Parts past the end of the plan
are NONE on both slots, which is the silent control.

⚠️ **Both the current parts and the saved copies.** A bank holds eight PART
records: 1–4 current, 5–8 the copies the unit restores on RELOAD PART.
Writing only the first four leaves the old assignment one keypress away.
(Verified against 80 bank files: 5–8 are byte-identical to 1–4 in every one.)

⚠️ **The checksum is not optional** — the last `u16` BE is an additive sum
over `bytes[0x10:-2]` and the unit rejects a bank whose sum does not match.
The tool recomputes it and then reads the file back; a mismatch aborts rather
than handing you a card that fails on load.

Measured on a real project: **1,968 bytes changed across sixteen banks, none
of them outside the FX id fields**, and no other file touched.

Make a fresh one per flash — `chongbong`, then `restored`, then `fieldtest` —
because each image implements a different set of ids.

---

## Flash 1 — the accumulated shipping build

**Image:** `chongbong`, the shipping remix, at HEAD. Bump `BUILD` to 79.

```bash
make check && scripts/refhash.sh check     # both must be green
BUILD=79 make image
```

**Why first, and alone.** It is the same *shape* as what is on the unit —
three modules, the same donor region, the same chooser — so it is the lowest
risk of anything here, and it is the gate: if the accumulated tree does not
work, nothing after it is worth flashing. It proves class B and, incidentally,
that the platform refactor really was inert.

**Checks, in order:**

1. **It boots.** Anything else is moot. The emulator has already reached the
   RTOS handoff on this image (`make remix`, the CHOOSERS line ends `boots`),
   so a failure here means something the emulator cannot see.
2. **The chooser reads `ChonVerb79 / BongDelay79 / Send`.** The tag is how you
   know which build is running — three rounds were lost to not being able to
   tell "the change did not work" from "the flash did not apply".
3. **Every stepped select prints words.** WarpFold is not in this image;
   check BongDelay's `MODE`, `RATE`, `FRZE` and ChonVerb's `MODE`, `SHFT`,
   `RATE`. ⚠️ **Falsifier: a select still showing `1 2 3`.** That is the
   formatter not taking, and it is a descriptor field a clone inherits from
   its donor — the 17 Aug class of bug.
4. **BongDelay GRAIN `DENS` sweeps.** It behaved as a two-position switch
   before R61. Turn it slowly across the full range and listen for continuous
   change. ⚠️ **Falsifier: it still jumps between two densities.**
5. **Levels.** R61 added makeup gain to keep GRAIN level-flat (±1.2 dB
   measured locally). Sweep DENS with a steady source and listen for a level
   jump. ⚠️ **Falsifier: an audible level step across the sweep.**
6. **REVERSE default.** R62 set it to the 93 ms segment. Check it sounds like
   a segment reverse, not a whole-buffer one.
7. **Test the reverb on TRACK 5, not track 1.** Payload A serves tracks 5–8.
   This has cost a session before.

**Stop condition:** if it does not boot, or if the reverb or delay is
audibly broken on its own track, **stop and do not flash 2**. Recover with
`downloads/extracted/OCTATRACK_OS1.40C.syx` and bisect locally — 134 commits
is a wide net, but `git bisect` with `make render` is cheap.

---

## Flash 2 — stock effects beside ours

**Image:** `restored` — chongbong plus the seven stock effects that can
coexist with the servers. Bump `BUILD` to 80.

**What it proves.** That a stock effect and one of ours can share a chooser
and a bank at all. Everything about that is currently build-time reasoning:
the ledger refuses the pairs it believes collide and permits these seven, and
nothing has ever checked the permission on hardware.

**Checks:**

1. **The chooser lists both.** Seven stock rows plus ChonVerb / BongDelay /
   Send, in the order `restored` declares.
2. **Each stock row actually runs.** Select FILTER, EQUALIZER, DJ EQ, PHASER,
   COMPRESSOR, LO-FI and DELAY in turn on **tracks 1–4** and confirm each is
   its own effect and not silence, noise, or another effect's algorithm.
   ⚠️ **Falsifier: a listed stock effect that is silent** — that is its
   dispatch pointing at the null stub, i.e. the build nulled something it
   should not have.
3. **A stock effect on tracks 1–4 while ChonVerb runs on 5–8.** This is the
   coexistence claim in the shape that matters. Play both. ⚠️ **Falsifier:
   tank corruption on the reverb** — a rising, grainy or metallic tail that
   is not there when tracks 1–4 are silent. That is the buffer collision the
   ledger exists to prevent, appearing on a pair it believed safe.
4. **Which reverbs survived.** The build report names them (`KEPT STOCK:`).
   If any survived, select it and confirm it is the real reverb.

**Stop condition:** tank corruption in (3) invalidates the ledger's
coexistence table, which is upstream of a lot. Stop, and record exactly which
pair and which tracks.

---

## Flash 3 — the field test: inserts, FX1, and a donor beyond the reverbs

**Image:** `remixes/fieldtest.py`. Bump `BUILD` to 81.

Three never-flashed claims in one image, shaped so a failure says which one
broke:

```
 region P:0x00d96..0x01aa4 (3342 words)  used 2195  FREE 1147
 donor ids taken (FLANGER/CHORUS/PLATE/SPRING) ... KEPT STOCK: DARK
 FX1 chooser = 10 rows (NONE + … + WARPFOLD), 3 refs repointed
```

**1. The insert card.** Five inserts on the FX2 chooser. Put **BodeShift on
all four tracks of one core** (5–8) — `cycle_count` says that plus four
WarpFolds on FX1 is the worst case at 1,780 of the 3,120 usable, but that
figure is a *floor*: exact for the code, optimistic about memory contention,
and it does not count stock's own FX1 load at all.
⚠️ **Falsifier: the unit wedges or the audio stops.** PLAN §2 says the wall
is a **cliff**, not a slope — +200 cycles was a hard hang with no warning.
If it wedges, that is the first real cycle measurement since 23 August and
worth more than the test that failed.

**2. WarpFold on FX1.** It is row 9 of a ten-row FX1 chooser.
- The row is **there** and reads `WarpFold81`.
- Selecting it draws **its own** knob names (`DRV FREQ TONE MODE MIX`), not
  the previous effect's.
- The cursor opens **on its row**, not row 0. ⚠️ That is `FX1_ID2POS`, which
  `tools/build_fx1.py`'s original experiment never wrote — the one thing in
  the FX1 path with no precedent at all.
- It **processes audio** on an FX1 slot.
⚠️ **Falsifier: a garbled FX1 chooser** — rows of symbols past the end of the
list. That is the viewport literal at `0x40059be6` not taking, and it is the
"bunch of symbols" failure FX2 had on hardware test 1.

**3. A donor region beyond the reverbs.** CHORUS and FLANGER are on neither
chooser, so their words are the region and our code sits at FLANGER's
address. **Nothing has ever overwritten a non-reverb stock effect on
hardware.** The static evidence is good — every effect is self-contained in
both payloads, no control flow leaves its span, nothing enters it but its own
dispatch entry — but static reachability cannot follow a computed jump or the
DSP's own self-modification (`dsp_reach.py` says so itself).
⚠️ **Falsifier: anything ELSE misbehaving** — an unrelated stock effect
wrong, a crash on part load, noise that does not follow a track. Check
FILTER, EQUALIZER, DJ EQ, PHASER, COMPRESSOR and LO-FI still sound right;
they are the neighbours whose code sits either side of the region.
- Also select CHORUS and FLANGER **from an old project** that has them
  stored. They have no row, and their id should resolve to **silence**, not
  noise. That is the null stub doing its job.

⚠️ **Why CHORUS and FLANGER and not FILTER.** FILTER is the default FX1
effect — every project touches it — so taking its words first would make any
failure maximally confusing and maximally destructive. These two are the
cheapest non-reverbs to be wrong about.

**Stop condition:** a wedge in (1) is *information*, not a failure to hide
from — record the exact configuration. Anything in (3) stops the dynamic
donor work until it is understood.

---

## Before every flash

From `docs/FLASHING.md` and the card workflow this project already uses:

- [ ] `make check` and `scripts/refhash.sh check` both green.
- [ ] **A test project stamped for THIS image** (step 0b). Without it you are
      testing whatever ids the last image left in the parts.
- [ ] **Bump `BUILD`.** The tag is stamped into the effect name; a unit whose
      version you cannot map to a commit is a unit you are guessing about.
- [ ] `make image` — `.bin` for the CF-card path (recommended), `.syx` for MIDI.
- [ ] The rescue firmware to hand: `downloads/extracted/OCTATRACK_OS1.40C.syx`,
      and a **DIN** MIDI path for it. USB-MIDI does not work for the upgrade.
- [ ] Card: copy, `cmp` against the source, remove the old image, `sync`,
      eject. Kill any `._` sidecars.
- [ ] Stable power.
- [ ] **A capture rig ready before the flash, not after** — `tools/rec.swift`
      via the MicroBook, never `ffmpeg avfoundation` (it drops samples).
- [ ] ⚠️ A capture inherits every stored knob on the part. **Re-select the
      effect** for fresh defaults before judging it.

## After every flash

Write the result down the same evening, in the repo, beside the claim it
tests — that habit is why this page could be written at all. A pass is one
line; a failure is the configuration, the track, and what it sounded like.

Mark each item in §0 as ✅ measured or ❌ falsified. **Do not leave a claim
in the "flashed, seemed fine" state** — that is how a stale confident number
gets written down, which this project has been burned by more than once.

---

## What is deliberately not in this plan

- **The main-menu shortcut** (PLAN §5) — not built, so nothing to flash.
- **An FX1 chooser SHORTER than the viewport.** `fieldtest` lists ten, above
  the seven-row window, so the shrink path is exercised but not the extreme.
  A three-row FX1 list is the interesting case for the viewport literal and
  is worth its own flash later, not a shared one.
- **The cross-core bus residual** (T4 + delay MODE 1). Standing open item;
  it needs a track × mode sweep, which is a listening session rather than a
  flash test.
- **MK1.** Every flash here has been on an MKII. The OS is the same
  hash-identical 1.40C image on both marks, so an octabam image is
  *plausibly* MK1-compatible 🟡 — but that remains inferred, and an MK1 owner
  flashing it is the test pilot.
