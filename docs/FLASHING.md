# Safe flashing guide — octabam builds on the Octatrack MKII

How to get an octabam image onto your Octatrack MKII, with a full safety net —
and how to get back off it.

> **⚠️ This is not official Elektron firmware.** Flashing a modified OS can
> leave the unit unusable until you recover it, and puts your warranty in
> question. Nothing here is endorsed by, supported by, or affiliated with
> Elektron. You flash entirely at your own risk.
>
> **Do not redistribute images you build.** A built `.bin`/`.syx` contains
> Elektron's copyrighted OS with patches applied. This project shares tooling
> and patches only — everyone builds against their own downloaded copy
> (`make os`).

> This document once described the upstream **octamax** ColdFire feature set
> (lazy Part transitions, sticky scenes, bank paging, `MAXO_*` images). Those
> features are octamax's, not octabam's — an octabam image contains the DSP
> effects and their menu plumbing, nothing else. The old guide is preserved in
> this repository's history (`git log -- docs/FLASHING.md`).

**Guiding principle: learn how to recover BEFORE flashing.** A brick here is
*soft and recoverable* — the Startup Menu (bootloader) lives in a region that
the OS update doesn't touch, so you can always return to the official OS over
MIDI. Read §1 first.

---

## 0. What you need (checklist)

- [ ] **An Octatrack — every test so far has been on an MKII.** The base
      image is OS 1.40C, and ✅ measured: **Elektron's MKI and MKII download
      pages serve the byte-identical file** (SHA256 `370c55a3…`, both pages,
      compared 19 Aug 2026) — the OS is one unified image for both marks.
      ❌ This retracts two earlier claims here: "will NOT work on the MKI"
      (asserted without a reason) and "the MKI runs its own 1.40C binary"
      (asserted from a wrong inference, falsified by the hash comparison).
      What remains true: **octabam has only ever been flashed on an MKII.**
      Since the MKI runs the same stock image, the patched image is
      plausibly compatible as-is 🟡 — but an MKI owner flashing it is the
      test pilot. (The updater's decompiled error −5 "MK1 not allowed"
      compares the *incoming file's* version code against "0156", so it
      rejects pre-unification MK1-era OS files, not MK1 units 🟡 inferred;
      octabam images keep 1.40C's internal code 0178 and validate normally.
      `docs/ARCHITECTURE.md`.)
- [ ] **The built image**: `make image` produces both delivery formats —
      `out/OCTATRACK_OCTABAM<NNN>.bin` (CF-card path, recommended) and
      `out/OCTATRACK_OS1.40C_OCTABAM<NNN>.syx` (MIDI path).
      `<NNN>` is the `BUILD` number from the Makefile — bump it every flash:
      a unit whose version string you cannot map back to a commit is a unit
      you are guessing about.
- [ ] **The official rescue firmware** (essential!):
      `downloads/extracted/OCTATRACK_OS1.40C.syx` — you have it after
      `make os`.
- [ ] For the MIDI path (and for recovery): a **5-pin MIDI (DIN) interface**
      into the Octatrack's MIDI IN, and an app that sends `.syx` files
      (SysEx Librarian on macOS is the usual choice).
      ⚠️ **The MIDI upgrade does NOT work over USB-MIDI to the OT's own USB
      port** — it has to be DIN.
- [ ] **Stable power** — no dubious power strip, and don't move the unit
      during flashing.

---

## 1. Safety net — the recovery path (READ THIS FIRST)

If something goes wrong (a "Z" screen, won't boot, a hang), **don't panic**:

1. Turn off the Octatrack.
2. Holding **[FUNC]**, turn it on → the **STARTUP MENU** appears.
3. Press **[TRIG 3]** → **MIDI UPGRADE** → "READY TO RECEIVE MIDI UPGRADE…".
4. Send the **official rescue OS**
   (`downloads/extracted/OCTATRACK_OS1.40C.syx`) from your SysEx app.
5. Wait through "PREPARING FLASH" → "UPDATING FLASH". **Don't power off.**
   You're back on the factory OS.

This menu works **even if the OS is corrupt** — it's the bootloader, and a
normal OS update never touches it. That's why the real risk of losing the
unit is very low.

> **Also**: [TRIG 2] = EMPTY RESET (resets the battery-backed RAM and clears
> settings, **but NOT the CF card**). Rarely needed, but it's there.

---

## 2. Before flashing — backup

Flashing the OS **does not touch the CF card** (sets, projects and samples
live there and stay intact). Even so:

- [ ] Back up your CF card to the computer (USB DISK MODE, copy everything),
      or at least the projects that matter.
- [ ] Optional but recommended: a **RESTORE POINT** of your active project.

---

## 3a. Flash from the CF card — the fast way (recommended)

Manual §8.5.2. Reads the file off the card instead of trickling it over MIDI
at 31250 baud, so it takes seconds rather than minutes.

1. Connect the OT over USB, select **USB DISK MODE**, press **[YES]**. The
   CF card appears as a drive.
2. Copy **`out/OCTATRACK_OCTABAM<NNN>.bin`** to the **ROOT** of the card —
   not inside any folder.
3. **Eject the card properly** on the computer, then leave USB DISK MODE on
   the OT. Skipping the eject can leave the write in cache and the OT reads
   a truncated file.
4. **PROJECT → OS UPGRADE → [YES]**, confirm the prompt. (The active project
   is synced to the card automatically first.)
5. ⚠️ **POWER-CYCLE THE UNIT BEFORE JUDGING ANYTHING.** Not optional, and
   not superstition — garbled audio straight after an upgrade has happened
   twice, cleared by a reboot both times.

   🟡 The mechanism, inferred from the code and matching the symptom exactly
   (not yet measured on hardware): an engine skips warm-up when its tagged
   counter holds a valid tag at full count — BusVerb `$2c0000` at `r7+$82`,
   BusDelay `$2e0000`, Nimbus `$2d0000` at `r7+$31`. **Any module that
   tags warm-up state in r7 inherits this**, so if yours does, expect it. **An OS upgrade rewrites program memory
   but does not clear DSP state RAM.** If that word survives with a valid
   tag, the engine concludes it is already warmed up and runs on whatever is
   in its buffers — the previous firmware's contents, or boot garbage. The
   delay's own source note spells out why that is worse than a single
   glitch: "this engine has real feedback, so uncleared garbage would
   recirculate rather than just play once and vanish."

   A power cycle clears the tag, warm-up runs, buffers are zeroed. **Judge
   no audio, and report no defect, until you have rebooted after an
   upgrade** — otherwise you are auditioning the previous build's leftovers.

   Falsifier, if anyone wants to close it properly: peek `r7+$82` on the
   first block after an upgrade and see whether the tag compare passes.

> This path needs a unit that boots. If it doesn't, use the MIDI path in
> §3b — the Startup Menu is in a region the OS update never touches.

`tools/make_bin.py` builds the `.bin`. Its correctness is not assumed: it
regenerates Elektron's own official `.bin` byte-for-byte from that file's own
container before it will produce a modified one.

---

## 3b. Flash over MIDI — for recovery, or if the card path fails

1. **Connect MIDI**: your interface's MIDI OUT → the Octatrack's **MIDI IN**
   (DIN, not USB).
2. In your SysEx app, choose the output port connected to the OT and load
   `out/OCTATRACK_OS1.40C_OCTABAM<NNN>.syx`.
3. On the Octatrack: power off, hold **[FUNC]**, power on → **STARTUP MENU**.
4. Press **[TRIG 3]** (MIDI UPGRADE) → **"READY TO RECEIVE MIDI UPGRADE…"**.
5. Send the file. The **[TRIG]** lights come on one by one as it receives —
   it takes a while. **From this repo you can drive the send** instead of a
   SysEx app: `make midi-flash PORT=A SYX=downloads/extracted/OCTATRACK_OS1.40C.syx`
   (`tools/midi_flash.py`) paces the ~7,460 messages at the DIN rate through a
   named MIDI destination. FILTER MIDI CLOCK on that port. Retry-safe: on a
   lost send, re-enter the Startup Menu and run it again (`--ms 60` to slow it).
6. When the transfer finishes: **"PREPARING FLASH"**, then **"UPDATING
   FLASH"**. **⚠️ DO NOT POWER OFF OR DISCONNECT** during "…FLASH" —
   interrupting here corrupts the OS (→ "Z" screen, → §1).
7. The OT may update its bootstrap after flashing. Wait for it to finish
   booting, then power-cycle (§3a step 5 applies here too).

> If the sender goes too fast and the OT loses sync, increase the pause
> between messages in the app's preferences (e.g. 100–300 ms).

---

## 4. Verify the flash took

1. **Version string.** The boot screen and **SYSTEM STATUS → OS VERSION**
   should read **`OCTABAM<NNN>`** — the `-V` stamp from `make image`. If it
   still says `1.40C`, the official OS is running, not your build.
**Which of the steps below apply depends on what your remix contains.** An
insert-only image (`mutables`, `warped`, `nimbus`) has no reverb, no delay
and no bus to check — steps 2–4 simply do not apply to it, and step 5 is the
whole test.

2. **A bank-bound server is restricted to its payload's tracks.** BusVerb
   runs on **tracks 5–8** (payload A runs the high tracks — measured, and
   inverted from what you'd guess); BusDelay on **tracks 1–4**. Picking one
   on the wrong bank falls back to a SEND, deliberately, so a wrong guess
   makes a send rather than silence. Assign BusVerb on track 5, feed it via
   `IN`, step **MODE**: distinct ROOM → PLATE → BIG spaces.
3. **The two servers are returns with a unity dry passthrough** (v5, 23 Aug
   2026): the host track's own audio passes untouched and `IN` adds it into
   the engine on top, so `IN` at 0 is an exact passthrough. This is a
   property of the SERVERS, not of every module — an insert processes the
   host track's audio directly and has its own MIX.
4. **The bus.** Put SEND on any other track and drive `→REVERB` /
   `→DELAY` — those are two separate knobs, and driving the wrong one
   renders silence that reads as a broken algorithm.
5. **An insert: select it on any track.** Inserts are placed in both
   payloads, so any of the eight tracks will do, and several tracks may run
   the same one or different ones. Expect it to process that track's own
   audio. Then check the two things **no local test can see**: that each
   page-2 select draws as a select (not a dial, not nothing — a formatter
   outranks the value count beside it), and that every knob actually reaches
   the DSP. A slot can draw a knob and publish nothing; `dsp_host` pokes
   `r6` directly, so both faults are invisible until this moment.

`docs/BUS.md` has the menu layout; `docs/PARAM_PAGES.md` explains how a knob
reaches the DSP; `docs/MODULES.md` is what to read before writing one.

### While you are at the unit — the hardware-only questions

These cannot be answered anywhere else, so they are worth queueing onto any
flash rather than spending a cycle of their own (`PLAN.md` work order):

- **Sweep the cycle ceiling.** A `make burn` image puts the burn on `p3` at
  32 cycles/step. The number prices every FX1 decision.
- **Does the stock delay's enable track the FX2 id?** Select DELAY on a
  track, read the per-track record byte the delay gates on; select BusVerb
  and read it again. If it is written separately from the dispatch id, then
  a cave can enable the CPU-side delay *downstream of our reverb* — a
  series routing the stock firmware has no path for. If it simply mirrors
  the id, the idea is dead and should be recorded as such.
- **Any new module's page-2 selects and knob publishes.** A slot can draw a
  knob and publish nothing, and a formatter outranks the value count beside
  it; both are invisible locally.

---

## 5. Reverting to the official firmware

Whenever you want: reflash following the same steps in §3, but with
`downloads/extracted/OCTATRACK_OS1.40C.syx` (MIDI) or the official `.bin`
from Elektron's zip (card). Your CF card and projects are not affected.

---

## Risk notes (honest)

- This firmware is **modified by you, for your own unit, for study
  purposes.** It is not official Elektron firmware and has no support from
  anyone — Elektron least of all.
- Everything checkable without hardware is checked — `make check`, the
  verify gates, and whatever local render your modules support (`make render`
  for the bus, `send_probe --direct` for an insert) — but the emulator is
  **single-core**, so
  no local test can reproduce a cross-core bus timing defect, and its mpy
  semantics and truncation are its own. Treat emulator green as necessary,
  not sufficient, and go in with the recovery net ready.
- The only truly delicate moment is **"UPDATING FLASH"**: don't cut power
  there.
- Residual risk of a *hard* (unrecoverable) brick: very low — the rescue
  bootloader is not touched in a normal OS update.

---

## ⚠️ First load of a project saved on an older (pre-return) image

There is **no migration mechanism**: the unit stores each part's knob VALUES,
and our descriptors only supply defaults when an effect is freshly selected.
So a project saved on an older image loads with values that may now mean
something else:

1. **BusVerb tracks that carried their own audio keep the dry again** (v5,
   23 Aug 2026): the host's dry passes at unity under the wet. (In the
   R29–R41 window the return printed the wet alone and such tracks went
   silent — that behaviour is retired.) Note the dry is NOT the old MIX law:
   it is always unity, and the wet rides on top.
1b. **Old stored WIDTH values load as SHFT** (p9, since R44): the reverb's
   width is pinned wide and slot 9 selects the shimmer interval. A stored
   WIDTH of 3 (the old default) reads as −12, the sub-octave — silent unless
   SHMR is up, and the first-load re-select fixes it like everything else.
2. **Old stored MIX values load as IN** (p5). On a pure return track this is
   inaudible — but it silently registers the host as a bus client and dilutes
   the real senders. Zero it, or use step 4.
3. **The delay's p4/p5 have both changed meaning.** An old project's stored
   MIX (p4) loads as `-VRB` — a typical MIX value washes the delay into the
   reverb on load — and stored VRBW (p5) loads as `IN`, silently registering
   the host as a bus client.
4. **The one-step fix per track: re-select the effect** (switch the FX2 away
   and back). The id-store fires on change and applies fresh defaults.

Same class as the power-cycle step above: known, cheap, and it reads as a
defect if you don't know it's coming.
