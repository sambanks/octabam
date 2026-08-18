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

- [ ] **Octatrack MKII.** The base image is OS 1.40C **for the MKII** — the
      built image will not work on the MKI, because the MKI runs its own
      1.40C binary (Elektron ships separate downloads per model) and every
      ColdFire patch address here was derived from the MKII image; the
      updater also enforces the model split (`docs/ARCHITECTURE.md`: error
      −5, "MK1 not allowed"). The *effects* are a different question — both
      marks share the same-family ColdFire and the same two-core DSP56721
      audio engine, so a port against the MKI image is plausible: the
      DSP-side payloads likely carry over, and the recon tooling
      (`make recon`, `tools/find_base.py`, `tools/verify_menu.py`) is
      exactly what re-deriving the ColdFire addresses would take. Nobody
      has attempted it; if you do, you are the test pilot.
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
   (not yet measured on hardware): both engines skip warm-up when their
   tagged counter at `r7+$82` holds a valid tag at full count — ChonVerb
   `$2c0000`, BongDelay `$2e0000`. **An OS upgrade rewrites program memory
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
   it takes a while.
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
2. **The reverb, on track 5.** Assign ChonVerb to an FX2 slot on one of
   **tracks 5–8** (payload A runs the high tracks — measured, and inverted
   from what you'd guess; on tracks 1–4 the pick falls back to a SEND).
   Feed it audio via `IN` and step **MODE**: you
   should hear distinct ROOM → PLATE → BIG spaces. Both effects are
   **returns** (wet-only output): a reverb track with `IN` at 0 is silent by
   design.
3. **The delay, on tracks 1–4.** BongDelay lives on the low tracks (payload
   B). Same deal: it is a return, fed over the bus.
4. **The bus.** Put SEND on any other track and drive `→REVERB` /
   `→DELAY` — those are two separate knobs, and driving the wrong one
   renders silence that reads as a broken algorithm.

`docs/BUS.md` has the menu layout; `docs/PARAM_PAGES.md` explains how a knob
reaches the DSP.

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
- Everything checkable without hardware is checked (`make check`,
  `make render`, the verify gates) — but the emulator is **single-core**, so
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

1. **ChonVerb tracks that carried their own audio lose the dry.** The reverb
   is a RETURN now (wet-only output). Old "insert" usage must be re-rigged as
   a send, or accepted as wet-only.
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
