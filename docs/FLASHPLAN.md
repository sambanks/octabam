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
| BusDelay R59–R62 | GRAIN density was a 2-position switch (now a full dial) + makeup gain; REVERSE default = 93 ms segment; the −19 interval swap | never |
| Stepped-select labels (PLAN §6) | twelve selects print words instead of `1 2 3` — `Param.labels` was authored, schema-checked and never read until 2 Sep | never |

### C. New capability, never on hardware at all — flashes 2 and 3

| | claim | evidence so far |
|---|---|---|
| Stock effects listable | our servers and stock effects coexist on one chooser; the reverbs come back where the placement never reached them | build + ledger only |
| The insert card | five inserts of ours stack, and four copies of the dearest fit one core's cycle budget | `cycle_count` is a **floor**, not a measurement |
| A module on FX1 | FX1's chooser relocated into the cave, its three `lea` refs repointed, its own id **and cursor** tables written | ColdFire emulator only |
| A donor region beyond the reverbs | any stock effect's words can be taken; every one is self-contained | `dsp_reach` over both payloads — **static** |
| Hello World (Bryan T) | builds and runs | flashed on **his** unit, not Sam's |
| **The returns** (3 Sep 2026) | the engines' wet arrives once, at the master, through the Character station in BUS mode (RVRB/DLY); the hosts go quiet ONLY while a return is live, and print as before otherwise | `tools/verify_returns.py` 18/18 and `make verify-bus` 19/19 — single-core: the delay's wet and its RETD stamp both cross cores on the unit, which no local test can see; and `0x360d3-5` next door was dead on hardware for R36 |

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
    ~/octa/backups/<a project you trust> /Volumes/<card>/OCTABAM_T1 bus
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

Make a fresh one per flash — `bus`, then `restored`, then `fieldtest` —
because each image implements a different set of ids.

---

## Flash 1 — the accumulated shipping build

**Image:** `bus`, the plain two-server image (the shape of tag 77), at HEAD. Bump `BUILD` to 79.

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
2. **The chooser reads `BusVerb79 / BusDelay79 / Send`.** The tag is how you
   know which build is running — three rounds were lost to not being able to
   tell "the change did not work" from "the flash did not apply".
3. **Every stepped select prints words.** WarpFold is not in this image;
   check BusDelay's `MODE`, `RATE`, `FRZE` and BusVerb's `MODE`, `SHFT`,
   `RATE`. ⚠️ **Falsifier: a select still showing `1 2 3`.** That is the
   formatter not taking, and it is a descriptor field a clone inherits from
   its donor — the 17 Aug class of bug.
4. **BusDelay GRAIN `DENS` sweeps.** It behaved as a two-position switch
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

**Image:** `restored` — bus plus the seven stock effects that can
coexist with the servers. Bump `BUILD` to 80.

**What it proves.** That a stock effect and one of ours can share a chooser
and a bank at all. Everything about that is currently build-time reasoning:
the ledger refuses the pairs it believes collide and permits these seven, and
nothing has ever checked the permission on hardware.

**Checks:**

1. **The chooser lists both.** Seven stock rows plus BusVerb / BusDelay /
   Send, in the order `restored` declares.
2. **Each stock row actually runs.** Select FILTER, EQUALIZER, DJ EQ, PHASER,
   COMPRESSOR, LO-FI and DELAY in turn on **tracks 1–4** and confirm each is
   its own effect and not silence, noise, or another effect's algorithm.
   ⚠️ **Falsifier: a listed stock effect that is silent** — that is its
   dispatch pointing at the null stub, i.e. the build nulled something it
   should not have.
3. **A stock effect on tracks 1–4 while BusVerb runs on 5–8.** This is the
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

## Flash 4 — the rig: BamSep26 with the returns (OCTABAM79)

**The image:** `make image` on `main` at tag 79 — `REMIX` defaults to
`bamsep26` now. **The project:** the set's real layout, written into every
part of every bank so any pattern is the rig:

```bash
python3 tools/ot_project.py rigproj ~/octa/backups/<trusted project> /Volumes/<card>/OCTABAM_RIG bamsep26
```

| track | FX1 | FX2 | what it is |
|---|---|---|---|
| T1 | character stn, →VRB 30 | **BusDelay** | the delay's host — plays its own material DRY while T8 returns |
| T2 | filter stn, →VRB 40 →DEL 30 | stock DELAY | synths in |
| T3 | filter stn, →VRB 30 | character stn | bass |
| T4 | filter stn, →DEL 40 | stock DELAY | lead |
| T5 | modulation stn, →VRB 40 | **BusVerb** | the reverb's host, dry likewise |
| T6 | filter stn, →VRB 50 | stock DELAY | melodic |
| T7 | character stn, →VRB 40 →DEL 20 | stock DELAY | vocal / guitar |
| T8 | character stn, **SAT=BUS**, RVRB 127, DLY 127, GLUE, COMP 40 | — | the master: glue, and the only place the wet enters |

For a REAL set (not the rig project), run `stamp-defaults` on a copy first —
the parts hold FILTER/LO-FI/CHORUS knob bytes under the stock layouts, and the
stations would read them raw (FILTER's DEC=64 → a →VRB send of 64 on every
melodic track):

```bash
python3 tools/ot_project.py stamp-defaults /Volumes/<card>/<set copy> bamsep26
```

**Claims, stacked so failures stay distinguishable.** Test in this order;
each one's failure has a different shape from the next.

| | claim | how to see it | falsified by |
|---|---|---|---|
| i | six descriptor clones + floated caves; label formatters and the FX1 list in the SECOND zero run | every station's page draws all twelve names; MODE/SAT/CMOD print words; BusDelay TIME prints `1/8`; FX1 chooser = NONE + three stations | garbage names, a select printing a number, a chooser with junk rows |
| ii | FX1 default = Spectrum station, dry at defaults | a part that chose FILTER runs the station and sounds unchanged | any tone change on a track at station defaults |
| iii | the Modulation station is dry on FX2 and modulates on FX1 | T5's FX1 modulation audible in CHOR; the same module chosen on T3's FX2 is a dry pass | **test on T7/T8 first** — a wrong FX1 detection on tracks 5–6 writes into BusVerb's tank |
| iv | harvested ids from an old project = silence, not noise | load the untouched set: tracks that named PLATE/SPRING/COMB etc. are silent | noise, a hang |
| v | **an FX1 station sending on T5** — a bus participant on FX1 has never run on hardware | T5's →VRB reaches the reverb; sweep tracks × modes and listen for the rotation-class artefacts (stutter, a block-rate buzz) | stutter that follows dispatch position |
| vi | stock DELAY on FX2 beside a sending station on FX1 | T2: delay repeats in the mix, the reverb of the DRY signal on the bus, not of the repeats | silence on FX2, or the repeats reaching the reverb |
| vii | GRAIN v5 by ear | BusDelay MODE=GRAIN, PTCH around 64 | (tomorrow's listening) |
| viii | **THE RETURNS** — the reverb and delay arrive once, at T8; T1 and T5 leave dry; hosts print again when the return goes | mute T8: the reverb and delay vanish from the mix. Turn T8's RVRB to 0: within 3 blocks the reverb comes back out of T5. Mute T5 with RVRB up: the reverb stays (it is T8's now) | reverb audible from BOTH T5 and T8 (a lost stamp); the delay's return stuttering or torn (the wet crossing cores — the accumulators' race in a new place); nothing returning at all (suspect `0x360d3-5`, dead on hardware for R36, next door to the new words) |
| ix | MAIN MENU > CONTROL > REVERB / DELAY | the rows exist and open the host's FX2 page | (~65%: the open/close path is untested) |

viii's three listening tests take a minute and separate the three failure
modes completely: double = stamp, torn = race, silent = memory. Write down
which.

---

## Flash 6 — THE ONE AUX RIG (bamsep27, 7 Sep 2026) — NEXT

**The image:** `REMIX=bamsep27 make image` on branch `onebus` (PR pending).
What it changes against tag 17 on the unit: ONE `AUX` send per track (SEND's
one knob; the hosts' slot 0), the chain delay → reverb hardwired through a
chain buffer with liveness stamps, `MIX` on both engines, ONE return (`RET`,
the CRSH knob of a BUS-mode Character) pinned to track 8, the SEND refused
on track 8, the stations without sends. `docs/BUS.md` "The one aux bus".

**Before play, no exceptions — the re-slot.** Page 1 of both engines shifted
right by one (AUX took slot 0): a part saved under tag 17 hands TIME to AUX,
MOD to TIME, … and the delay's old PTCH byte to MIX. The MODE re-slot stalled
the sequencer on the first play for exactly this reason.

```bash
python3 tools/ot_project.py rigproj ~/octa/backups/OCTABAM_RIG_20260906_cleared /Volumes/<card>/OCTABAM_ONEAUX bamsep27
# or, for a real set on a copy:
python3 tools/ot_project.py stamp-defaults /Volumes/<card>/<set copy> bamsep27
```

`rigproj` writes the new RIG table: stations with no sends, SEND `AUX`
30–50 on T2–T4/T6–T7, the hosts' `AUX` on T1/T5, T8 = Character SAT=BUS
RET 127 and NO FX2 (nothing to refuse). T8's old `-VRB 71` (the master loop)
cannot exist: the station has no send slot and the SEND is refused there.
**Prepared 7 Sep 2026: `out/projects/OCTABAM_ONEAUX`** (from the 6 Sep
cleared backup, 16 banks written and read back) — copy it to the card as is.

**STAGED ON THE CARD 7 Sep 2026 (tag 20).** `/Volumes/OCTATRACK` carries
`OCTATRACK_OCTABAM20.bin` at the root (tag 19 removed; rebuild it with
`REMIX=seamtest BUILD=19 make image` if the seam cave is wanted back) and the
project `PRESETS/OCTABAM_ONEAUX`, byte-verified against
`out/projects/OCTABAM_ONEAUX`, sidecars killed. **Load that project, not the
old one:** every other project on the card that HOSTS an engine still stores
the tag-17 slot order, so page 1 arrives shifted by one — BusVerb's TIME
lands on AUX, the delay's PTCH byte on MIX. Affected: `ChongBongolo 26`,
`OCTABAM_RIG`, `OCTATRACK`, `PROJECT 260804`, `PROJECT 260810`,
`Pheasant - 2026 2`. Fix any of them with
`ot_project.py stamp-defaults <project> bamsep27` on a copy. A SEND track is
benign (its old `→DEL` byte becomes AUX, which is the same gesture) and a
station is inert by construction (its send slots are blank and its levels are
forced to 0 in code — gated).

**Claims, in this order (each failure has its own shape):**

| | claim | how to see it | falsified by |
|---|---|---|---|
| i | the re-slot | every host page reads AUX TIME MOD SIZE TONE MIX / AUX TIME FDBK TONE PING MIX; the delay's page 2 ends PTCH FRZE | a knob doing its neighbour's job |
| ii | the chain | T2 sends AUX: repeats AND reverb arrive on T8 with nothing on T1/T5's own outputs | reverb without repeats (chain buffer), repeats without reverb (stamp), or the hosts still printing (RETV/RETD) |
| iii | last live stage | select NONE on T5 (no reverb): the repeats still return; NONE on T1 too: silence, not garbage | silence with the delay alone (the fall-through), garbage with neither (the level gate) |
| iv | MIX | delay MIX 0: the reverb of the DRY sends, no repeats; reverb MIX 64: repeats under the tail | MIX changing level but not blend |
| v | the refusal | put SEND on T8's FX2 with AUX 127: nothing changes; the same on T4: it sends | T8 audible in the return (the position pin is wrong) |
| vi | stations silent | a station on any track with its old send bytes (a tag-17 part, unstamped, on a scratch copy) sends nothing | a station's track in the reverb with its AUX at 0 |
| vii | the return pin | a BUS-mode Character on T7 or T4: returns nothing; on T8: returns | a return from T7 or T4 |
| vii-b | a wrong-track station does not kill the return | a BUS-mode Character on T4 AND the T8 return together: T8 still returns (✅ 9 Sep 2026 under the port after the fix; before it T8 went silent) | T8 silent with a BUS station elsewhere |
| viii | cross-core stamps | play for minutes: no flicker of the return, no host print creeping back | the return dropping out and back (a stamp lost > 3 blocks) |

**Stop condition:** any of ii–iv failing on the unit after passing
`make verify-onebus` locally is a cross-core timing fact — record the exact
configuration (which core, which position) before touching code.

---

## Flash 7 — the one-aux rig with the port's two fixes (bamsep27, 9 Sep 2026) — NEXT

**The image:** `REMIX=bamsep27 make image` on `main` after #160, #163
(and #164, harness only). Against tag 20 on the unit it changes THREE
things, all found by running the shipping image under the ColdFire port
(`docs/COLDFIRE_PORT.md` O11/O12), none by guessing:

1. **The return's pin and the track-8 refusal use the dispatcher's real
   r7** (`$6a00/$6b00`; three r7 blocks per track, not two). Tag 20's
   "hosts keep printing, nothing on T8" was this: the station never
   matched, cleared its RET level, stamped nothing.
2. **One rotation tracker per core** (`build_bus.py` ROTLATCH, payload B):
   the fourth core-1 client (T4) landed one buffer late every frame under
   the firmware's timing; all four now resolve the same buffer.
3. **A BUS-mode station off track 8 no longer silences the return** (it
   stole the engines' clear-on-read liveness stamps; `character.asm` now
   touches them only with a RET level up). Found by running flash 6's own
   claim vii under the port with T8 present.
4. Nothing in the part layout: no re-slot, no stamp needed beyond what
   flash 6 already required. `OCTABAM_ONEAUX` on the card loads as is.

✅ **The image is the tested image (9 Sep 2026):** `REMIX=bamsep27 make
bus` on `main` (after #166) produces `out/mainos_bus.bin` **byte-identical**
to `out/o9d/mainos_flash7b.bin`, the file every O12/O13 port measurement
and the claims sweep ran on (`cmp`, 1,112,560 bytes). ⚠️ `make image`
itself was broken on the default `BUILD` line (a trailing comment put
spaces into the version and the recipe split on `.bin`); fixed on the
O13 branch — bump `BUILD` by editing the number only.

**Pre-flash evidence, under the port (no unit):** Sam's RIG project as
backed up (master on, T1/T2 THRU on the two input pairs), tones on all
inputs, 1,500 frames on this image: T1 and T2 pass their inputs (−23.8 /
−23.0 dBFS out), **T5 prints nothing, T1 prints nothing but its dry, T8
carries the return**, no fault, no stall. With the master off the return
alone on T8 builds as a reverb should; the delay path through the bus is
bit-identical to `dsp_host` (−120 to −200 dB); the reverb path matches it
within its free-running modulation.

**Claims, in flash 6's order — what changes:**

| | claim | expected now |
|---|---|---|
| ii | the chain | PASSES on the unit for the first time: repeats and reverb on T8, T1/T5 silent. Falsified by the hosts still printing → the r7 stride on the unit differs from the port's (measure it: `--dsp-pcwatch`'s r7 column against a station's own stamp) |
| v | the refusal | T8's SEND at AUX 127 changes nothing (pin `$6b00`); T4 sends |
| viii | cross-core stamps | no flicker; ALSO: T4's send arrives in step with T2/T3's (it was a block late) |

Everything else as flash 6. **Stop condition unchanged**, with one
addition: if ii fails, the port has a measurement for it in under an hour
— bring the exact part and pattern back, not a theory.

### The automated run (`tools/hw_flash7.py`, 9 Sep 2026)

The claims above are driven over MIDI and read off the interface, so the
human does the flash, the cables and the project load and nothing else. The
manual (OT MKII 1.40C Appendix C) puts every MAIN-page knob, mute, solo and
level on the track's trig channel and the pattern on program change; it puts
NO effect type, part or page-2 knob anywhere. So the claims that need a
different effect on a track live in **parts 2–4 of the test project's bank
A**, reached by program change, and each part carries a signature (T1's
LEVEL 108/64/84/48) the run measures before trusting the claim.

**The image: `out/OCTATRACK_OCTABAM21.bin`** (`REMIX=bamsep27 BUILD=21 make
image`). Its DSP and ColdFire bytes are the tested `mainos_flash7b.bin`
except the ten bytes of the five effect-name tags (`cmp -l`: exactly 10,
all `79` → `21`).

**The project: `OCTABAM_F7TEST`** (`hw_flash7.py stage`, from the one-aux
rig): bank A patterns 1–4 → parts 1–4; pattern 1 is the rig; part 2 = SEND
on T8's FX2 at AUX 127 (claim v); part 3 = a BUS-mode Character on T4 with
RET 127 (vii, vii-b); part 4 = NONE on T5 (iii). Patterns 2–4 carry pattern
1's T1 trig so the THRU passes the drums. `hw_flash7.py card` copies image
and project to the mounted card, verifies both, removes the old firmware
and the sidecars, ejects.

**Human steps, in order:** flash OCTABAM21 from the card; power-cycle;
PROJECT → LOAD `OCTABAM_F7TEST`; PROJECT → MIDI: CONTROL → AUDIO CC IN on,
SYNC → PROG CH RECEIVE on (both were on for the 24 Aug session); Rytm into
inputs A/B, main outs into the MicroBook; Midihub on port A; then
`hw_flash7.py check` (ports, interface, a level) and `hw_flash7.py run`.

**What the run does (about six minutes), each with its falsifier:**

| step | drive | reads | falsified by |
|---|---|---|---|
| S0 | T8 soloed, T1 AUX 127, RET 127 | T8 > −55 dBFS | silence = flash 6's shape |
| ii-a | T8 soloed; RET 127↔0 (control), T1 AUX 127↔0 (test) | both \|t\| ≥ 3 | the AUX not moving T8 |
| ii-b | T1 soloed; LEVEL 108↔64 (control), T1 AUX 127↔0 (test) | control moves, test < 0.5 dB | the host printing its wet (flash 6) → the r7 stride differs on the unit |
| ii-c | T5 soloed | < −60 dBFS | T5 printing |
| iv | T8 soloed; delay MIX 127↔0, reverb MIX 127↔0 | both \|t\| ≥ 3 | an engine missing from the chain |
| PC 1 | pattern 2 | T1 −8.3 dB | signature absent = PROG CH RECEIVE off / wrong project |
| v | T8 soloed; RET (control), T8 AUX 0↔127 (test) | test \|t\| < 3 | T8 audible in its own return = the pin is wrong |
| PC 2 | pattern 3 | T1 −3.6 dB | |
| vii / vii-b | T4 soloed; T8 soloed | T4 < −60; T8 within 4 dB of S0 | a T4 return; T8 silent = the stolen stamps |
| PC 3 | pattern 4 | T1 −13.3 dB | |
| iii | T8 soloed; delay MIX and reverb MIX toggles | T8 > −55, delay moves, reverb does not | silence = the fall-through |
| viii | pattern 1, 90 s | no 2 s window 12 dB under the median | a dropout = a lost stamp |

The run restores nothing soloed, T1 AUX 30, MIX 127/127, RET 127, pattern
A01, and writes `out/hw/flash7/run_<stamp>.log` beside every recording. Every
"no change" verdict stands beside a control that did change, so a dead
cable reads INCONCLUSIVE, not PASS.

---

## Flash 5 — the ColdFire headroom probe (cfprobe)

**The image:** `REMIX=cfprobe make image` — the rig plus HELLO WORLD and
CF PROBE. **The question:** how much of each audio frame a ColdFire-side
machine could take (PLAN §8: a Braids port, a Pickup-machine descendant).
`modules/cfprobe/README.md` is the full procedure; `tools/verify_cfprobe.py`
(22 checks, emulator-driven) is the gate.

Independent of flash 4's claims and cheap to stack on the same day, but a
SEPARATE image: the burn is the crossfader and the readout is a diagnostic
knob, so it is not something to leave on the unit.

| | claim | how to see it | falsified by |
|---|---|---|---|
| i | the hook runs once per 16-sample frame at a 132 MHz bus clock | HELLO WORLD's GAIN at 0–31 prints ≈ `47891` | a clean multiple (the interrupt runs per DMA block: still a measurement, bigger frame); any other value (the clock inference is wrong; the ratios still hold); `-` after ten seconds (the hook is not running per frame at all) |
| ii | the delay routine's cost at rest | GAIN 64–95 prints `r<pct>`; GAIN 96–127 prints the same `t<pct>` at fader 0 | `t` ≠ `r` at fader 0 — the probe is wrong, stop |
| iii | the routine has no expensive occasional path | GAIN 32–63 `x` ≈ `r` at rest; move a stock DELAY's TIME and watch `x` | `x` ≫ `r` |
| iv | **the starvation point and what starves first** | full set playing, sample streaming, MIDI clock in, UI scrolling; fader up 8 steps at a time, record `t`/`x` and the first symptom | (this is the measurement) — UI lag, streaming stutter, MIDI drift, audio crackle, hang, in rising order of what it would mean |

Write down `t` at the first symptom and `r` at rest: the difference is the
frame fraction a ColdFire machine may take. Core cycles ≈ 2× the ticks 🟡.

---

## Flash 5 — the rig with the bus screens — ❌ BLOCKED (tag 91 crashed on [PROJ])

tag 91 (`bamsep27` with the screen) was built and flashed, and **crashed with
a line-F exception the moment [PROJ] was pressed.** Cause: the screen's cave
was pinned at `0x40108800`, inside the OS image's `.bss` tail — a zero run at
rest that the PROJECT subsystem uses as RAM once a project is loaded. Our cave
and the project's own memory collided. The single-core, no-project emulator
could not see it, and the "proven dead" test never opened PROJECT. The
tag-91/92 images are quarantined in `out/BAD_DO_NOT_FLASH/`.

Fixed and prevented: `build_bus` now refuses a cave at or above
`SAFE_CAVE_CEIL` (0x400d8000). But the rig has no safe hole for the
2,296-byte cave, so **screen-in-rig is deferred** — `bamsep27` is back to
MENU SHORTCUT, which is what flash 4 shipped and is known good. The plain
`busscreen` remix carries the full screen safely (tags 85–90).

⬜ **Before any rig-with-screen flash again:** the cave must live in the
decoded free band (split across the 1,988- and 1,609-byte holes, or the rig
trimmed to make one hole), and the PROJECT menu must be exercised in the
emulator — the gate that was blind here. Until then flash 5 is the plain
`busscreen` screen (already validated on the unit) or the shortcut rig.

## The MODE re-slot — two claims, BOTH CONFIRMED on tag 84 (4 Sep 2026)## The MODE re-slot — two claims, BOTH CONFIRMED on tag 84 (4 Sep 2026)

✅ **Flashed as `OCTATRACK_OCTABAM84.bin` (remix `bus`, PR #95) the same
afternoon. Both claims held: MODE draws and steps as a 3-way select on slot
6, SHMR / MDEP sweep smoothly from slot 7.** So the 10 Aug "near-boolean
companion" reading is retired: it was the inherited formatter.

⚠️ **AND THEN THE SEQUENCER STALLED — 1, 2, back to 1, solid — on the
first play.** 🟡 Inferred cause, matching a trap already on record
(`docs/MODULES.md`: a select value outside its count is used as an index and
stalled the sequencer after two steps): every part saved under the OLD layout
still held its slot-6 byte, which was SHMR (0–127) or MDEP (48 by default),
and the panel now reads that slot with a count of 3. Re-selecting on the one
track under test is not enough — the sequencer runs every track of the part.
A project refreshed for this build ran clean ("confirmed working"), which is
consistent with the cause and does not prove it; the falsifier is a stall on
a project whose every BusVerb/BusDelay slot has been stamped.
**Before playing a pre-84 project on this or any later image: `python3
tools/ot_project.py stamp-defaults <project> bus`, or re-select the effect on
every track of every part that carries it.**

Both bus engines moved MODE to page-2 slot 6 and SHMR / MDEP to slot 7
(`docs/MAINMENU.md` §9c-ii, `docs/PARAM_PAGES.md`). Locally bit-identical in
every mode through the new fields; what only the panel can show:

1. **MODE draws as a 3-way select on slot 6** and steps ROOM/PLATE/BIG
   (CLEAN/GRAIN/REVRS) with the engine following. Falsifier: a dial, or a
   select that draws but the sound does not change. The renderer pair is
   stock CHORUS TAPS's, a slot-6 control, so a dial here would mean the
   clone's slot-6 formatter fields were not written.
2. **SHMR (BusVerb) and MDEP (BusDelay) sweep smoothly from slot 7.** Turn
   SHMR 0 → 127 on a held chord: the octave-up bloom should grow
   continuously. Falsifier: off-then-full at some threshold — the 10 Aug
   "near-boolean companion" reading — in which case SHMR becomes a
   small-count select and MODE stays where it is.

Do this on a **freshly re-selected** BusVerb / BusDelay: a part saved before
the swap has its slot-6/7 bytes crossed — and see the stall above: stamp the
WHOLE project before pressing play, not just the track you are looking at.

## Tag 16 — the rig with real send knobs on the host pages (5 Sep 2026)

`bamsep27`, `BUILD=16`. On top of tag 15 (bus screen in the rig, page-2
store at +0, SEND labelled): each host's FX2 page now carries its own send
pair, per Sam's call — "delay drive and reverb single tone".

| engine | slot | was | now |
|---|---|---|---|
| BusVerb | 3 | HP | **TONE** — 0..64 = old LP 0..127 (dark → flat), 64..127 = old HP 0..126 (flat → thin); **64 = old HP 0 / LP 127 bit-identical** |
| BusVerb | 4 | LP | **-DEL** — dry send into the delay bus, default 0 |
| BusDelay | 10 | DRV | **-DEL** — dry send into its own delay (the retired IN path), default 0; drive pinned to 0 |

⚠️ **STAMP-DEFAULTS BEFORE PLAY, no exceptions.** A part saved under tag ≤15
holds LP=127 in slot 4 and HP=0 in slot 3: under tag 16 that is **-DEL 127
(the reverb host sending full-tilt into the delay) and TONE 0 (a fully dark
tail)** on every BusVerb track of every part — legal values, so nothing
refuses, it just sounds wrong and blames the engine. And BusDelay's old DRV
byte becomes its send level. ⚠️ `stamp-defaults` does NOT do this: it
touches only the ids a station replaced and keeps the engines' bytes on
purpose. Use the targeted `stamp-slot` (added 5 Sep 2026), which writes one
byte and leaves the other eleven knobs as Sam set them:

```sh
# module by key/name, knob by its manifest name, value = the manifest default
python3 tools/ot_project.py stamp-slot "<project>" busverb  TONE
python3 tools/ot_project.py stamp-slot "<project>" busverb  -DEL
python3 tools/ot_project.py stamp-slot "<project>" busdelay -DEL
```

**Done on the card 5 Sep 2026** for all three projects that name the
engines: `PRESETS/OCTABAM_RIG` (THE rig project, in use that day — 16 banks
× 8 parts, every T5 BusVerb stored HP 0 / **LP 127**, BusDelay's slot 10
already 0), `PROJECT 260810` (T5 BusVerb 0 / **127**, T1 BusDelay DRV
**87**) and `PROJECT 260804` (T1 BusVerb 0 / **93**) — every one would have
loaded as a hot send. Backup: `~/octa/backups/PRESETS_20260905_pretag16/`.
(The first pass missed OCTABAM_RIG: a `find | head -20` cut the listing
short. List the whole set; the loaded project is the one with today's bank
mtimes.)

Claims to settle on the unit (emulator says: reverb host `-DEL` 100/127 =
a SEND client at 100/127 exactly; two clients = two SENDs; `-DEL` 0 silent;
`verify-bus` 19/19; TONE 64 render bit-identical to tag 15):
- [ ] ⚠️ In `bamsep27` the hosts are HIDDEN and their twelve names BLANK
      (remix docstring): T5's FX2 page draws six unlabelled dials, and that
      is BY DESIGN (seen 6 Sep 2026, tag 16 — it read as "still got all the
      blank knobs"). The labelled view is the bus screen: MAIN MENU →
      CONTROL → REVERB reads TIME MOD SIZE **TONE -DEL** IN / MODE SHMR DIFF
      SHFT GATE RATE; CONTROL → DELAY reads TIME FDBK TONE PING -VRB PTCH /
      MODE MDEP MRAT SIZE **-DEL** FRZE. TONE 64, both -DEL 0 (the stamp).
- [ ] T5 `-DEL` up: T5's dry audible in the delay on T1, at the level a
      station's `->DEL` at the same value gives. **This is the cross-core
      claim no local test can reach**: the client flag is a per-block write
      on core 0 read per block on core 1 (`Y:0x941`, RETV's shape).
      Falsifier: the send arrives but the delay's level drops when it does
      (flag seen, contribution not) or the send never arrives (contribution
      not seen); either way say which.
- [ ] T5 `-DEL` at 0 with a station sending: the delay's level is what tag
      15 gave (no phantom client).
- [ ] TONE: 64 sounds like tag 15's default; sweep down darkens, up thins;
      nothing steps or clicks at 64 (the two halves meet there).
- [ ] T1 `-DEL` up on the delay host: T1's dry repeats; at 0, nothing.
- [ ] Bus screen (CONTROL → REVERB / DELAY) rows 3/4 and 10 draw the new
      names and edit them (tag 15's own claims still open, see Flash 5).

### Tag 16 on the unit (6 Sep 2026) -- ❌ two findings, the rest not reached

- ❌ **The host pages drew six dials with NO labels** (photo: FX2 > BusVerb16
  on T5). That was the remix's design (hidden = blank names) and it is the
  worst outcome the panel can show -- Sam: "blank labels but with knobs
  still showing is the worst result possible". The spec (the BamSep26 design
  page) says a host page shows the two labelled send knobs and nothing else,
  like SEND's; "nothing else" had been built as "nothing".
- ❌ **CONTROL showed no REVERB / DELAY rows.** The image carries the patch
  (row count 6→8 and the pointer at 0x400cbd54, labels present), so the
  firmware reads its CONTROL menu from somewhere the patch does not reach.
  `docs/FAILURE_MODES.md`. Not diagnosed; the emulator's own menu is the
  place to look before another flash.
- The send / TONE / bus-screen claims were not reached.

## Tag 17 -- the hosts NAMED, the bus screen out (6 Sep 2026)

`bamsep27`, `BUILD=17`. Sam's fallback: "if we have to go back to them
displaying on the host I could live with it." The engines stay off the
chooser (`hidden`) and keep their names (`named`): T5's FX2 page reads TIME
MOD SIZE TONE -DEL IN / MODE SHMR DIFF SHFT GATE RATE, T1's TIME FDBK TONE
PING -VRB PTCH / MODE MDEP MRAT SIZE -DEL FRZE. BUS SCREEN is out of the
remix. Nothing else changed from tag 16: same DSP, same slot meanings, so
**no stamp is needed** (the tag-16 stamp stands). `make check` green (291),
`refhash` 26/26, `verify_hidden` renders both host pages in the ColdFire
emulator and sees every page-1 name.

Claims:
- [x] ✅ **CONFIRMED ON THE UNIT, 6 Sep 2026** (Sam: "knobs show as
      described"): T5 FX2 page 1/2 and T1 FX2 page 1/2 draw the names above,
      with values (TONE 64, both -DEL 0). The first correct host pages since
      flash 4.
      ⚠️ The rest of tag 17's claims were never reached: the session found the
      master loop instead, and the rig has since been redirected to the ONE
      AUX BUS (PLAN.md's banner). These slot meanings are what the card's
      projects are stamped for. Selects print words (MODE, SHFT, RATE, SIZE,
      FRZE), BusDelay TIME prints a division.
- [ ] The FX2 chooser still has ONE row (SEND); FX1 = NONE + three stations.
- [ ] T5 `-DEL` up: T5's dry audible in T1's delay at a station-send level
      (the cross-core flag, `Y:0x941`); at 0 with a station sending, no
      level drop on the delay.
- [ ] TONE: 64 = tag 15/16 default; down darkens, up thins, no step at 64.
- [ ] T1 `-DEL` up: T1's dry repeats; at 0 nothing.
- [ ] Sequencer plays through a part change with no stall.

## Before every flash

From `docs/FLASHING.md` and the card workflow this project already uses:

- [ ] `make check` and `scripts/refhash.sh check` both green.
- [ ] **A test project stamped for THIS image** (step 0b; for the rig,
      `rigproj`). Without it you are testing whatever ids the last image
      left in the parts — and since 3 Sep 2026 whatever KNOB BYTES too:
      `stamp-defaults` a copy of any real set before its first load.
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

- ~~The main-menu shortcut — not built~~ Built 3 Sep 2026 and in the rig:
  flash 4's claim ix.
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

## Flash — the recorder seam cave, tag 19 (`seamtest` = bus + `recorder-seam`), staged 7 Sep 2026

On the card: `OCTATRACK_OCTABAM19.bin` at the root (tag 17 removed) and
project `PRESETS/SEAMTEST` = the hardware `RECTRIG128` with A01 at 1X / 16
steps, T1 recorder trigs at 2/6/10/14 with RLEN 4, T2 FLEX-on-R1 play trigs
at 2/6/10/14, 128 BPM. `stamp-defaults` had nothing to stamp (no replacing
modules in this remix). **Ran on Sam's unit, 7 Sep 2026 — the smoke test passed, the ear test did
not happen here.** Tag 19 boots, loads SEAMTEST, runs the pattern and
records with the cave live — no fault, no stall, so the cave's stack offset
(`160(%sp)`) and lane assumption hold on real hardware, which was the real
first-flash risk. The A/B click test could NOT be isolated on this rig: the
project resampled an internal track (only drums on input 1), so source and
recording were the same sound, and muting the source killed the recorder
pickup. Two process lessons landed instead — `ot_project` wrote only
`.work` and a RELOAD reverted every edit (fixed, PR #130, writes `.strd`
too), and STATIC slots are 0-based with a bare-filename PATH (measured).

**The click A/B is handed to Bryan** (his sound-on-sound rig, his ear). He
is on the shared tree: `modules/recorder-seam/`, remix `seamtest`, mechanism
in RTOS_FORK §10.16.4–§10.17. **Claim:** the click at 128 / RLEN 4, once
every 2 bars, is gone. **Falsifier:** it persists → the seam is not the
recorder length; or a per-track-scale pattern faults → the lane-index
assumption is wrong. **Control:** 120 BPM unchanged.

**❌ FALSIFIED on Bryan's unit, 7–8 Sep 2026 (tag 21, same module bytes,
cave verified in the image; his Moog on the inputs, sound-on-sound).** 128 /
RLEN 4 with rec + play trigs every 4 steps: **clicks** (onset varies run to
run, one run around the sixth repeat). 128 / RLEN 16, one rec + play trig
on step 1: clicks on the first repeat. 128 / RLEN MAX, rec trigs every 4
steps: **clicks** — no end post, the cave never runs, §10.16.6 had called
it seam-free by construction. 120 / MAX and 120 / RLEN 4, same trigs: no
clicks. The click follows the tempo, not the length converter; the cave is
not the fix and the seam model is not the click. His projects were rebuilt
from this description, not copied from the card; AUX at 0 throughout.
Hardware facts and what route A found next: RTOS_FORK §10.18.
