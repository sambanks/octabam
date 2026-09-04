# Hardware failure modes — the register

One place for "the unit is doing X" → what it means and what clears it, so a
symptom is recognised instead of re-diagnosed. Each entry: **symptom** (what
the panel/audio does), **cause** (measured, inferred, or unknown — marked),
**fix**, and provenance. Add to this the moment a mode is seen on hardware;
do not let it live only in a commit message or one doc.

Confidence, per `CLAUDE.md`: separate measured from inferred. A fix that only
"seems to work" says so until it is confirmed twice.

---

## Audio engine wedged, sequencer alive ✅ FIX CONFIRMED, cause open

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

## Cross-core bus glitch — the accumulators' race 🟡

**Symptom.** A tear, stutter or hash on wet audio that crosses cores; often
smeared into a reverb tail so it is hard to localise.

**Cause (measured, 17 Aug 2026, three defects found + fixed through R26; one
residual on T4 + delay MODE 1).** The shared-window accumulators raced across
the two cores. `docs/XBUS.md`.

**Fix.** The shipped fixes (four ACC buffers, per-core rotation tracking).
⚠️ **No local test is evidence here** — `dsp_host` is single-core, so a bus
race never reproduces off the unit. Believe the hardware.
