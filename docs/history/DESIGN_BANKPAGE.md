# Design — Live Bank Paging (sibling-project bank pages)

> **SHELVED (not shipped).** This feature was explored, reverse-engineered, and partly built
> (hardware-validated: sibling banks load from CF with no audio stop), then **cancelled** for a
> fundamental reason worth recording:
>
> The root problem it aimed at is that **loading a new project stops the audio**. Bank paging
> only avoids that stop by requiring sibling projects to **share the sample pool** — because
> `PROJECT → CHANGE` stops playback precisely to reload the **audiopool** (the samples), which
> paging deliberately does not touch. So paging can only bring in new *patterns/parts* that reuse
> the *same samples*; it cannot bring in new sonic material. That makes it too limiting to justify
> the complexity, and it does not solve the real problem. **The real frontier is a live audiopool
> swap** (loading a new project's Flex/Static samples without stopping playback) — a much larger,
> unsolved effort. The RE below is kept for reference and reuse.

---

Load a fresh page of 16 banks from a **sibling project** on the CF card into the
resident bank RAM **without stopping the audio/sequencer**, driven from the SELECT
BANK screen with the [PAGE] key. Educational, for the author's own MKII.

Status: **de-risking done (hardware-validated)**; RE of the plumbing in progress;
this doc is the plan. Nothing shipped yet.

---

## 1. Feature spec (from the user)

Sibling projects share a base name and differ only by a trailing `_N` suffix
(`mi_proyecto`, `mi_proyecto_2`, `mi_proyecto_3`, `mi_proyecto_4`). The base may be
unsuffixed or `_1`; page projects add `_2`.._N.

User flow:
1. Load the base project. Any project that is **not** a base (no siblings) behaves
   exactly like stock — no paging.
2. In the SELECT BANK screen ([BANK] pressed), press **[PAGE]** instead of a bank
   trig. If a sibling for the next page exists, the page LED advances and a
   **"Load banks? YES/NO"** popup appears.
3. **YES** → load that sibling's 16 banks (minus the playing bank) **without stopping
   audio**, then return to the SELECT BANK screen so the user picks a bank + pattern
   as if they'd just pressed [BANK].
4. **NO** → abort, back to the sequencer.
5. [PAGE] again cycles to the next sibling (`_3`, `_4`, …), each with its own confirm.
6/7. When no further sibling exists, wrap back to the base (page 1) and confirm.

Independence: `_1`.._N remain independently editable projects; paging is a
live-performance overlay only available while the base project is loaded.

---

## 2. Proven foundation (hardware-validated)

See `NOTES.md` → "HARDWARE-VALIDATED: non-playing bank loads from CF without stopping
audio". Confirmed on a real MKII:

- The async loader task (FUN_4008445c) fills a **non-playing** bank's disjoint RAM
  region (`0x400e21e0 + bank*0x9b340`) concurrently with audio — **no audio stop**.
- The only two things that cut audio are avoidable:
  - the confirm-menu **pre-step FUN_400a10c8** (synchronous per-track note/voice reset),
  - the end-of-load **re-sync FUN_400238a4**.
  Skipping both, and keeping the **playing bank out of the mask**, gives glitch-free
  background loading (v3 experiment: audio kept playing through the entire load).
- The masked loader already loops 16 banks: FUN_4008f0b0 (`.strd→.work` copy) and
  FUN_400905d4 (`.work`→RAM via FUN_4008ded0). Filenames built from FUN_40025230(0,0)
  (current project) + `bank%02d.work/.strd`.

---

## 3. Hard constraints / caveats (must document for the user)

- **Shared sample pool.** Sample slots (Flex/Static) are PROJECT-level; parts reference
  samples by slot. Sibling projects **must share the same sample pool / slot assignments
  / Flex assignments**, or paged banks play the wrong or absent samples. Natural if
  siblings are made with SAVE PROJECT AS from the base and only patterns/parts differ.
- **Paging is ephemeral / performance-only (v1).** After paging, the RAM bank slots hold
  the sibling's content. A SAVE PROJECT / SAVE BANK while paged would write that content
  into the **base** project's files. v1 must guard against saving while off the base page
  (block or warn), to avoid cross-contaminating siblings.
- **Playing bank is not paged under your feet.** It is excluded from the mask; it keeps
  the current page's content until you switch away from it.
- **The 16th (playing) bank — catch-up on bank change.** Loading the current bank while it
  plays would replace the pattern under the playhead → inherent audio stop, so it is excluded
  from the page load (15 banks). It is loaded from the sibling **once it stops playing**: when
  the user selects a new bank (the intended post-page flow), the just-vacated bank is now idle
  and a single-bank load from the current page catches it up in the background. All 16 converge
  progressively; by the time you cycle back to it, it holds the sibling's content.
- **Load is not instant.** ~635 KB/bank from CF; a full 15-bank page takes seconds
  (background, no audio stop). Use model: page ahead, keep playing, switch once loaded.

---

## 4. Architecture (patch shape)

All new code lives in a code cave (like the arp/lazy patches), reached by detours.
Pieces:

1. **Sibling detection** — on/after project load, derive the base name from the current
   project name, scan the CF for `<base>_2..N`, record which pages exist and the count.
   State: current page index, page count, base-project flag.
   *(RE: project-name global, FS dir-enumeration primitive — TODO §6)*
2. **PAGE interception in SELECT BANK mode** — detour the SELECT BANK input handler: if
   [PAGE] pressed and base-project-with-siblings, advance page index (mod count), light
   the page LED, and invoke the confirm popup.
   *(RE: SELECT BANK handler, PAGE scan code, LED primitive — TODO §6)*
3. **Confirm popup** — reuse the native YES/NO dialog (FUN_4006d57c) with "Load banks?".
   On YES → step 4; on NO → return to sequencer.
   *(RE: FUN_4006d57c calling convention from injected code — TODO §6)*
4. **Redirected masked load** — build/post the load job for the selected sibling page:
   - redirect the bank-file path to the sibling project dir (or pre-copy its `.work`
     files), *(RE: filename-format substitution point — TODO §6)*
   - mask = all 16 banks **minus the playing bank** (`0xffff & ~(1<<playingbank)`),
   - **skip the pre-step**, and **skip the re-sync** (conditionally, since the playing
     bank is excluded) — both proven necessary in de-risking.
5. **Return to SELECT BANK** — after posting/finishing, leave the UI in SELECT BANK.
   *(RE: re-enter SELECT BANK state — TODO §6)*
6. **Save guard** — while page != base, block/deny SAVE PROJECT / SAVE BANK (or warn).

---

## 5. Staged implementation + test plan

Build and hardware-test in stages (each stage independently verifiable), like the arp
and lazy features. Emulate stubs where possible (Unicorn), compose-test the image, then
flash.

- **S1 — Redirected load, triggered crudely. ✅ HARDWARE-VALIDATED.** `tools/patch_bankpage_s1.s`
  + `tools/build_bankpage_s1.py`: gate FUN_40025230 @0x40025244 with `g_redirect`; trigger at
  FUN_40063bf8 @0x40063bfe (skip pre-step, sprintf `<name>_2`, arm redirect, mask=all-but-playing,
  post); done at FUN_40023998 @0x400239a2 (clear redirect + skip re-sync). Result: RELOAD gesture
  loaded the sibling `_2`'s 15 non-playing banks from CF with **no audio stop**, and switching to a
  paged bank showed the sibling's patterns. Redirect + masked multi-bank load confirmed working.
- **S2 — Sibling detection (folded into S3/deferred).** Existence check recipe: build `<name>_N`,
  `FUN_40025230(0,name)`→path, `FUN_40025650(path)`. Not yet wired (vtable not emulator-testable;
  on PAGE critical path) — the top hardware-test-required addition.
- **S3 — PAGE + popup UX. ✅ S3a HARDWARE-VALIDATED; S3b emulator-validated.** Intercept [PAGE]
  in SELECT BANK (FUN_4004ffc4, keycode 0x1b), page cycling 1→2→3→4→1, confirm dialog showing the
  target project name, YES→redirected load / NO→abort, re-enter SELECT BANK (FUN_4007af80).
  Shipped in R12 (tools/patch_bankpage.s). Deferred: existence gate, skip-missing, page LED.
- **S4 — Catch-up + save guard + polish.** Catch-up the vacated bank on bank-change (hook the
  playing-bank switch; if paged, single-bank load the just-freed bank from the current page).
  Block save while paged; edge cases (wrap-around, no-siblings, paging while on the last bank).

Throwaway experiment tooling (`tools/build_exp.py`, `tools/patch_exp_bankload.s`) is the
starting point for S1.

---

## 6. Open RE items (being closed now — fill in with findings)

- [x] **Project name** = C string @`0x100f8378`; base/set path @`0x100f8480`; `FUN_40025230(base,proj)` builds `<base>/<proj>` into scratch `0x460bf112` (proj=0 → uses 0x100f8378).
- [x] **Redirect = gate FUN_40025230**: global `g_redirect` (char*, default 0); if `projname==0 && g_redirect!=0` use it. Set before posting the load job, clear in the done callback. Read path only (non-destructive). Load site: FUN_400905d4 @0x40090668.
- [x] **Sibling detection**: existence primitive `_DAT_46c823fa(path)` (nonzero=exists) or predicate `FUN_40025650(fullpath)` (valid-project check). Build name via sprintf(scratch,"%s_2",0x100f8378).
- [x] **SELECT BANK detect**: `_DAT_460d1e5c!=0 && _DAT_460d1e60==0x4007b408`. **[PAGE]** = keycode 0x1b, press-handler **FUN_4004ffc4** (hook its entry; gate on edge==1 + select-bank test). Popup doesn't eat keys.
- [x] **Confirm popup**: `FUN_4006d57c(title, nLines, linesArray, 3, handler)`; YES→handler(0), NO→handler(1); guard `_DAT_460e5cd0==0`. Lines built via FUN_40020898.
- [x] **LED**: `FUN_400135b0(id, 0xF)` on / `FUN_400131c8(id)` off (brightness cache DAT_400b9714).
- [x] **Re-enter SELECT BANK**: call `FUN_4007af80()` (re-opens the window as a fresh [BANK] press).

*(These are under active reverse-engineering; §4/§5 get concrete addresses once closed.)*
