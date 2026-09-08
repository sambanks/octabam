# Hardware failure modes — the register

One place for "the unit is doing X" → what it means and what clears it, so a
symptom is recognised instead of re-diagnosed. Each entry: **symptom** (what
the panel/audio does), **cause** (measured, inferred, or unknown — marked),
**fix**, and provenance. Add to this the moment a mode is seen on hardware;
do not let it live only in a commit message or one doc.

Confidence, per `CLAUDE.md`: separate measured from inferred. A fix that only
"seems to work" says so until it is confirmed twice.

---

## Audio engine wedged, sequencer alive ✅ CAUSE MEASURED 6 Sep 2026: the MASTER LOOP

> **STRUCTURAL FIX BUILT 7 Sep 2026 (one-aux rig, unflashed):** the
> stations have no sends, and the SEND is REFUSED at track 8's dispatch
> position on payload A whatever its knob says, so the master cannot send
> into the bus it returns. `tools/verify_onebus.py` pins both.

**Symptom.** The sequencer runs (steps advance, transport works), but **no
audio plays** — not the tracks, and a **sample preview triggers but is
silent** too. The **record meters for B/C/D sit lit permanently**. Distinct
from the DSP-hang mode below: there the sequencer freezes; here it runs.

**Cause.** Not established. The frame interrupt is clearly still firing (the
sequencer is clocked by it), so it is the audio path / output mix that is
wedged, not the whole DSP. Candidates, unconfirmed: a cross-core bus /
accumulator wedge (this class has bitten before — `docs/XBUS.md`), a
transient cycle overrun on a core near budget, or stale DSP audio state.

**Fix.** **Power-cycle** — CONFIRMED (5 Sep 2026: wedged mid-play on the
tag-93 rig, a power-cycle brought audio straight back). Recurring; Sam has
seen it before. If it recurs, capture what was playing when it wedged.

**Falsifier / next step.** If it recurs on a specific action (a bank change,
a heavy station turned up, the returns engaging), that names the cause. Log
the trigger here when seen.

**Recurrence, 6 Sep 2026 — WEDGED ON EVERY COLD BOOT INTO OCTABAM_RIG,
three images in a row (tags 16, 17, 18), NOT cleared by power-cycles.**
Localised without a flash:
- The image is innocent: tag 18's DSP is byte-identical to tag 13's, which
  played (807 ColdFire bytes differ, all chooser/descriptor plumbing).
- The project stamp is innocent: PROJECT 260810, stamped the same way, plays.
- A Pheasant set (no octabam engines) plays.
- **Cleared by SWITCHING PROJECTS and back** (Pheasant → 260810 → OCTABAM_RIG:
  "playing now without me doing anything"); reboots are clean since. So it
  is PERSISTENT STATE that the project switch REWROTE — the unit writes the
  current project's files before loading another. The wedging state is in
  the Friday backup (`~/octa/backups/PRESETS_20260905_pretag16/OCTABAM_RIG`)
  and the cleared state is on the card: **diff the two on the next mount
  (project files first, then banks) — the changed bytes name the state.**
- What OCTABAM_RIG has that 260810 does not: the RETURN engaged on every
  part (T8 FX1 = Character, SAT = BUS, RVRB 127, DLY 127 — never before run
  on hardware), and in bank02 the master's own -VRB send at 71 (the loop the
  spec forbade). Sam suspected a loop first; the "a loop would squeal, not
  go silent" dismissal was reasoning, not measurement — RETRACTED. Whether
  either is the cause is NOT established.
- **MEASURED (next mount, 6 Sep):** card vs the wedging backup — banks differ
  ONLY by the stamp (18 bytes each); `project.work` differs in TWO fields:
  the header's OS version string `OCTABAM13` → `OCTABAM18`, and `TRACK=4`
  (T5, the reverb host, selected) → `TRACK=7` (T8). Nothing else. Backup of
  the cleared state: `~/octa/backups/OCTABAM_RIG_20260906_cleared`.
  Prediction to test: tag 17 on the card, project says 18 → if the cold boot
  wedges, the saved-OS-version mismatch is the suspect (and every flash
  needs a project switch after it); if it plays, the selected-track-at-boot
  is what remains (select T5, save, cold boot).
- **✅ MEASURED, 6 Sep 2026 (tag 17, OCTABAM_RIG silent after a project
  switch): turning T8's FX1 -VRB from 71 down to 0 brought the audio back,
  live.** The master's station (Character, SAT = BUS = the return point)
  was SENDING into the reverb bus it RETURNS — the one loop the design
  forbids ("a master that sends into a bus it returns is the one loop
  left"). Sam called it a loop on the first symptom. Why the loop reads as
  SILENCE rather than a squeal is not established (inferred: the bus
  auto-gain / the return's clear-on-read stamp collapsing, not measured).
  The version-string idea was falsified the same hour (switching back under
  a matching tag was still silent) and the one earlier "cleared by a
  switch" was a different bank coming up: bank01's parts have T8 -VRB 0,
  bank02's have 71.
- **Fix, immediate:** T8 -VRB = 0 in every part (a track-filtered
  `stamp-slot`), and SAVE. **Fix, structural:** a station in BUS mode must
  not register or send at all — closes the loop by construction — and the
  spec's rule stands: the master's station carries no sends.
- ⚠️ Two wrong calls made the same day, both logic leaps: "intermittent"
  (it never cleared on a reboot) and "cleared by a power-cycle" (that was
  the 5 Sep instance, not this one). Say only what was observed.

---

## Sequencer stuck on step 1 (DSP hang) — CYCLE OVERRUN or a wild value

**Symptom.** Press play, the playhead lights **step 1 solid and never
advances.** No audio. The sequencer clock is the DSP frame interrupt, so a
hung core looks exactly like a dead transport.

**Cause (measured, 4–5 Sep 2026).** A core cannot finish a block. Two ways:
(1) **cycle overrun** — too much on one core (e.g. three heavy stations
beside an engine priced ~3,106 of 3,120 as a *floor*, over once contention
is added; `tools/cycle_count.py` is a floor, the wall is a cliff); (2) a
**wild stored value** feeding an engine on frame one (an old part's
crossed-slot byte after a layout change — the MODE re-slot family).

**Fix.** Fit the layout (≤ two heavy stations per core — the rig project's
`RIG` table, `tools/ot_project.py`), and **stamp the project** for the
current remix before playing (`ot_project.py rigproj`/`stamp-defaults`) so no
stale byte reaches an engine. The single-core, no-project emulator cannot see
either — only the unit can.

---

## Line-F exception on [PROJ] — a cave pinned in OS .bss

**Symptom.** The OS runs, but hitting **PROJECT throws an exception** and
wedges (recover via the Startup Menu, below).

**Cause (measured, 4 Sep 2026, tag 91).** A ColdFire cave was pinned at
`0x40108800`, inside the OS image's last ~30 KB — a zero run **at rest** that
is really uninitialised OS data (the PROJECT subsystem's RAM). Our cave and
the project collided the instant PROJECT ran. A static zero-check and a
no-project emulator boot both passed; `.bss` was mistaken for free padding.

**Fix / prevention.** `build_bus.SAFE_CAVE_CEIL` (0x400d8000) now refuses any
cave above the decoded free region. Caves belong in `0x400d2000..0x400d8000`.

---

## Garbled / wrong audio straight after an OS upgrade — WARM-UP TAG

**Symptom.** Right after OS UPGRADE, audio is garbled or wrong (worse for the
delay, which recirculates it). Not present after a reboot.

**Cause (inferred, matches the symptom; `docs/FLASHING.md` §3a).** An OS
upgrade rewrites program memory but does NOT clear DSP state RAM. An engine
skips warm-up when its tagged counter holds a valid tag at full count
(BusVerb `$2c0000` at `r7+$82`, BusDelay `$2e0000`, Nimbus `$2d0000`), so it
runs on the previous firmware's buffer contents.

**Fix.** **Power-cycle after every upgrade, before judging anything.** Clears
the tag, warm-up runs, buffers zero. Judge no defect until you have rebooted.

---

## Self-oscillating squeal — a page-2 value out of range, or deep overrun

**Symptom.** A rising/holding squeal.

**Cause.** Two measured sources: (1) a wild page-2 value — e.g. BusVerb DIFF
stamped to 127 self-oscillates the tank (the +0x325/+0x331 stamp-offset bug,
4 Sep 2026); (2) **deep cycle overrun** — the "high-pitch squeal" is the
deep-overrun signature (`docs/CHIP.md`: p3=23 × 32 breakup, 23 Aug 2026).

**Fix.** Re-stamp the project (1); fit the layout (2).

---

## "Z" screen / won't boot — corrupt OS

**Symptom.** A "Z" screen, or the unit will not boot.

**Cause.** The OS flash was interrupted or corrupted.

**Fix (never fails — the bootloader is untouched by an OS update).** Startup
Menu recovery: power off; hold **[FUNC]**, power on → Startup Menu → **[TRIG
3]** MIDI UPGRADE → send a good `.syx` (`make midi-flash PORT=A SYX=...`, or a
SysEx app). Factory rescue: `downloads/extracted/OCTATRACK_OS1.40C.syx`.
`docs/FLASHING.md` §1. Recovered from the tag-91 crash this way, 5 Sep 2026.

---

## Cross-core bus glitch — the accumulators' race 🟡 → ✅ MECHANISM MEASURED under the port, 9 Sep 2026: core 0's housekeeping flips the rotation word in the middle of core 1's frame and every client reads the word directly, so a frame's sends split across two buffers; the reverb (the cross-core reader) gets them a block late/split. `COLDFIRE_PORT.md` O12. ✅ FIXED 9 Sep 2026 (branch `bus-private-rotation`, UNFLASHED): one rotation tracker per core (`build_bus.py` ROTLATCH, payload B), every core-1 client resolves the same buffer per frame under the port; verify-onebus and make check green.

**Symptom.** A tear, stutter or hash on wet audio that crosses cores; often
smeared into a reverb tail so it is hard to localise.

**Cause (measured, 17 Aug 2026, three defects found + fixed through R26; one
residual on T4 + delay MODE 1).** The shared-window accumulators raced across
the two cores. `docs/XBUS.md`.

**Fix.** The shipped fixes (four ACC buffers, per-core rotation tracking).
⚠️ **No local test is evidence here** — `dsp_host` runs both cores only
lock-step or under a guessed interleave (`-skew`), so a bus race that fails
to reproduce locally is not shown absent. A local mismatch under skew IS a
defect. Believe the hardware.

## CONTROL menu shows its stock six rows though the image carries eight 🔴

**Symptom.** MAIN MENU › CONTROL lists AUDIO … PERSONALIZE exactly as stock;
the REVERB / DELAY rows a module appended (modules/busscreen, also
modules/menushortcut's mechanism) are not there. Everything else in the
image works.

**Seen.** Tag 16, 6 Sep 2026. The image was checked afterwards: row count
at 0x400cbd54 = 8, the row pointer at +0x18 repointed to the relocated rows,
both labels present. The bytes are right; the firmware is not reading them.

**Cause.** Unknown (inferred: the CONTROL rows are copied or built elsewhere
-- a RAM copy at boot, a second descriptor, or the menu code takes its count
from another table). Not diagnosed.

**Fix.** None yet. BUS SCREEN is out of the rig (tag 17). Before any flash
that appends CONTROL rows again: navigate to CONTROL in the ColdFire
emulator's own menu and count rows; if it shows six there too, the emulator
can find where the count really comes from. Flash 4 (tag 79, MENU SHORTCUT)
used the same patch -- whether its rows appeared was never recorded.

## The one-aux return never reaches T8: the hosts keep printing their own wet 🔴

**Symptom.** With the one-aux rig on the unit, sending `AUX` from a track
produces wet — but it comes out of **T1 and T5, the engines' own host
tracks**. Muting T1 and T5 removes all wet. Nothing arrives at T8, the
pinned return. Turning the return knob down does silence the wet.

**Seen.** ✅ Flash 6, tag 20, 7 Sep 2026, reported from the unit. Claim ii of
the Flash 6 table ("T2 sends AUX: repeats AND reverb arrive on T8 with
nothing on T1/T5's own outputs"). Claims i (the re-slot) and iv (MIX) passed
in the same session.

**Cause.** 🟡 **INFERRED, not measured.** The symptom is the third falsifier
the claim itself names — *"the hosts still printing (RETV/RETD)"* — i.e. the
return-live stamp is not reaching the engines, so neither host goes quiet and
the return publishes nothing. The stamp has to cross cores here: the return
is a BUS-mode Character pinned to **T8 = payload A / core 0**, while the
delay host sits on **T1 = payload B / core 1**. Nothing has been measured on
the unit to distinguish a lost stamp from a return that never publishes.

✅ **CAUSE MEASURED 8 Sep 2026, under the ColdFire port (`COLDFIRE_PORT.md`
O11), and it is not a cross-core race:** the station pins the return to
track 8 by testing `r7 & 0xff00` against `$6700/$6800`, the harness's
two-per-track model of the dispatcher's state block. The stock dispatcher
bumps its r7 counter THREE times per track (FX1, FX2, and an unconditional
third at P:0x51e), so on the unit track 8's FX1 runs with **r7 = $6a00**,
the pin never matches, `ch_nopos` clears the RET level, the station stamps
nothing, and both hosts keep printing — exactly the symptom, reproduced
with the firmware driving both cores. Fixed: pin `$6a00/$6b00`; the
harness's r7 model corrected (rig_render, verify_onebus, send_probe,
dsp_host's comment); under the port the fixed image returns on T8 with both
hosts silent for 2,000 frames. UNFLASHED. The reading below stands as the
history of the wrong guess.

**⚠️ THE LOCAL GATE IS GREEN ON EXACTLY THIS.** `tools/verify_onebus.py`
asserts "T5 (reverb host) prints nothing while the return is live" and the
same for T1, and both pass — the property hardware falsifies is the property
the gate checks. That is the standing rule in force, not a surprise:
`dsp_host` boots both payloads but runs them in lock-step, so a cross-core
timing defect cannot appear locally. **Believe the hardware.**

**Fix.** None yet, and per the Flash 6 stop condition the next step is
measurement, not code: *"any of ii–iv failing on the unit after passing
`make verify-onebus` locally is a cross-core timing fact — record the exact
configuration (which core, which position) before touching code."* What is
worth having before the next flash: which track the send came from, whether
a send from a **core 0** track (T6/T7) behaves differently from a **core 1**
one (T2–T4), and whether the return is dead or merely intermittent (the
free lever from `docs/XBUS.md` is to change what sits on track 5).

