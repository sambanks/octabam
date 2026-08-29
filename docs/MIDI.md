# MIDI — plan (branch `midi`, opened 24 Aug 2026)

Three things, all hanging off one question: **how does a value get from a MIDI
CC, a scene, or a MIDI note into a parameter slot the DSP reads — and does that
path reach OUR descriptors and the page-2 companion bits (8–15 of `r6+$c/$d/$e`)?**
Answered 24 Aug 2026 by three disassembly passes over the ColdFire OS:
`docs/midi_re_cc.md`, `docs/midi_re_scene.md`, `docs/midi_re_note.md` (kept as
the evidence record; this file is the plan).

Confidence markers as in `docs/CHIP.md`: ✅ measured / decompiled, 🟡 inferred,
⬜ not yet looked at. Tooling note: r2's m68k backend misdecodes ColdFire
`mvs/mvz/mov3q/mac`; the scouts used `m68k-elf-objdump -m m68k:cfv4e` on the
raw image. `aaa` segfaults on this image.

## Decisions (Sam, 24 Aug 2026)

1. **Tier 1 — CC → knobs.** Page-2 shortlist that MUST become reachable:
   **FRZE, MODE (both effects), SHMR, GATE, DRV**. DPTH/RATE/DIFF/PTCH/SHFT
   are nice-to-have.
2. **Tier 2 — crossfader.** ❌ **NOTHING hard-locked to the fader** (Sam,
   24 Aug, second decision, overriding the first): the want was scene-style
   selective assignment like any stock effect. Page 1 already scene-locks;
   page 2 cannot; so nothing is done. (The cave still publishes fader+1 at
   `r6+$8`, unread — a spare word, not a feature.)
3. **Tier 3 — notes.** **Note → BongDelay PITCH interval** first ("funnest").
   HOLD semantics: the last note sticks after note-off; retune by tapping.
   A never-received note (0) → the PTCH select behaves exactly as today.
4. `midi` off `main` @ `1a1929b`; caves in `modules/tempo-sync/` (originally `cf/`); the level-voicing session
   stays on `main` (parked, `tools/level_cap.py`).

## What the ColdFire says

### MIDI in → parameters ✅
UART0 `0xfc060000` is MIDI IN; RX ISR `0x400106ec`, framer `0x40092bf4`
(running status `0x46100b70`), MIDI thread `0x40005540` dispatching on
`status>>4` via `0x400d6474`: note-off `0x4000db98`, note-on `0x4000e018`,
CC `0x4000e79c`; realtime via `0x40001900` → `0x400d2d98` (F8 → `0x40005a48`,
a clock/tempo estimator writing `0x80001818/14`).

**CC map** (handler `0x4000e79c`): CC 16–45 → `idx = cc−16` (bounds `< 30`),
posted as kind `0x40` to the kernel queue `0x460d17ae`; consumer `0x40062496`
maps `idx/6` through `{0,2,1,3,4}` to page_kind, `flat = page_kind·6 + idx%6`.
**CC 40–45 = FX2 slots 0–5** — our page-1 knobs (ChonVerb TIME/MOD/SIZE/HP/LP/IN,
BongDelay TIME/FDBK/TONE/PING/-VRB/IN, SEND -DEL/-VRB) should be live TODAY;
unverified on hardware ⬜. Other CCs: 7/46 level, 47 cue, 8 AMP BAL, **48
crossfader**, 49–51 mute/solo/cue, 52–54 arm, 55/56 scene select, 59/60 synth
note on/off, 61 send request, 112–127 → `0x8000000c`.
**Unused: 0–6, 9–15, 62–111** (50 contiguous from 62).

**Page 2 is unreachable from CC, structurally**: `cc−16 < 30` and the writer
derives `slot = flat % 6`. Slots 6–11 cannot be expressed.

**Generic writer `FUN_40054cd8(track, flat, value)`** ✅: resolves the
descriptor via `FUN_40031da4(track, flat/6)`, refuses disabled slots, clamps to
`[min, min+count−1]` from `P+0x6a/P+0x9a`, stores to the Part
(`+0x8ee9a + track·24 + flat−6` for AMP/LFO/FX1/FX2), a shadow, and the **live
byte `0x80000810[track·72 + flat]`**; the frame builder `0x4000c0f0` copies
those `<<8` into the DSP frame every frame (that is why knobs sit at bits
16–23). The UI knob path is a near-copy `FUN_40055008(slot, delta)`. **Page-2
storage is untraced** — likely Part `+0x8ef5a` 🟡; the live-byte block is 72
per track, which is 6 × 12 🟡 — page 2 may live in the same block at `+6..+11`
of each 12. ⬜ The single RE item that gates tier 1.

### Scenes / crossfader ✅ (corrects `docs/history/NOTES.md`)
`FUN_4003f1b4` is NOT the general morph — it handles only STRT/LEN/RATE. The
general morph runs **every DSP frame inside the frame builder `FUN_4000c8a4`
(`0x4000cc6c..0x4000cf3e`)** on the ping-pong frame copy; live param words are
never touched. Scene block = 8 tracks × 0x20; byte *k* ↔ frame halfword *k*;
bytes 24–29 = **FX2 page 1** (`r6+0..5`); loop stops at halfword 17 of the
page block; `0xFF` = not locked. A lock is the knob byte `<<8` and the WHOLE
16-bit halfword is lerped (`A·xf/127 + B·(1−xf/127)`, MAC unit, weights
`0x80003c60` from curve `0x400bcd90`), so **companion bits become fraction
bits: page 2 cannot be scene-locked even in principle**, and the exclusion is
spread over ≥5 sites. Not worth patching.

**Fader position: `0x460d16c8` (long, 0..127)** — written by the panel path
(`0x40061e0a`, raw) and by CC 48 (`0x4006269a`, `127−value`). One variable,
both sources. `xf=127` ⇒ scene A side. The physical ADC → event producer was
not located (not needed).

### Notes ✅
Channel→track route `0x46c7febe[16]` from per-track channel `0x8000003f+t`
(−1 off) + auto channel `0x80000047`. Audio note map (`0x4000e464`): **36–43
= sample trig of track note−36; 72–96 = chromatic play** (`0x4000e6e2`),
which p-locks PTCH `64+5·(note−84)`, writes **held note `0x400d64c2[t]`**
(byte, `0xFF` on release), gate bit in `0x46c7fb08`, and posts event 0x41.
Velocity is NEVER retained for audio tracks. Per-channel held count
`0x46c7fe4c[chan·4]`.

### The DSP record ✅ (corrects `docs/DSP.md` §6c-i)
The record is fully rewritten every frame (`0x4000cb6e..0x4000cb7c` copies
`0x80000830+72t` into `+0x24..+0x35` before `jsr 0x40004bd4`). "Dead" means
never READ; a cave must re-store every pass, as the tempo cave already does.
**Free on those terms: `+0x28, +0x2a, +0x2c` = `r6+$8, $9, $a`.**
`+0x2e..+0x34` are live page-2 params, `+0x36/+0x38` ids.

## Design

### One cave, three words
Extend `modules/tempo-sync/tempo_cave.s`'s id-6/7 branch (a2 = record, a0 = id base; the
track index is `a0 − 0x80000110`):
```
    +0x28  r6+$8   fader     move.l 0x460d16c8,%d0 ; move.w %d0,0x28(%a2)   (0..127)
    +0x2a  r6+$9   note      0x400d64c2(track) as a word; 0xFF → publish 0
    +0x2c  r6+$a   spare
```
The DSP latches the note (HOLD): `if word≠0 → Y-state slot = word`. No
ColdFire RAM needed, no per-track shadow. Both effects can read the fader.
Cave grows ~24 bytes; it sits in the zero run `0x400d6b00..0x400d7c3c`.
Relocation to the `0xff` padding at `0x400c4702` (PLAN.md next-session item)
happens in the same edit.

### Tier 3 DSP: note → PITCH step
`n = note − 84`, clamped ±12 (chromatic range is 72–96, so the clamp is
belt-and-braces). `step = $1000 × (2^(n/12) − 1)`: a **13-word P table** of
`$1000·2^(k/12)`, k = 0..12, read with `p:(r5)+`/indexed exactly as LFOTAB is
placed by `build_bus.py` (raw words before the module, literal rewritten);
`n<0` → `table[n+12]` then `asr` once; subtract `$1000`; store `r7+$6a/$6b`
as the existing decode does. One new branch in the PTCH decode, taken when the
latched note ≠ 0. ~35 words 🟡 against **payload B FREE 87** ✅. Per-block
cost only. Local verification: `dsp_host` pokes `r6+$9`, render PITCH mode
with a tone, measure the shifted partial against `2^(n/12)`.

### Tier 2 DSP: fader → FREEZE (and more)
BongDelay: `FRZE = knob select OR (fader ≥ 96 with release at ≤ 80)` — the
existing freeze crossfade handles engage/disengage. ~12 words. Later: fader →
`-VRB` blend, reverb SHMR, a runaway feedback — each a few words, all voicing.

### Tier 1: CC → page 2
A CC-handler patch: CCs **62–73** → FX2 page-2 slots 6–11 (and 74–85 → FX1's,
if ever wanted). Requires the page-2 writer/live-byte path, untraced. Two
routes: (a) find the UI page-2 knob writer (the `FUN_40055008` analog for page
2) and call it; (b) if page 2 shares the 72-byte live block, call
`FUN_40054cd8` with the right index and let the frame builder publish. Gated
on the RE below.

## Status (24 Aug 2026) — note → interval ON THE UNIT (R57, tag 76), hardware-confirmed

- **Cave v2** (`modules/tempo-sync/tempo_cave.s`, 104 bytes at `0x400d7000`; the TIME
  formatter cave moved to `0x400d7080`): `r6+$8` = fader+1 (1 = fully B,
  128 = fully A, 0 = no cave), `r6+$9` = held note or 0. Bytes pinned in
  `build_bus.py`. ✅ assembled, ⬜ hardware.
- **Note → PITCH interval** (`modules/bongdelay/delay_server.asm` after `pintend`): the
  DSP latches the note in `y:>$090a` (HOLD); iterative `2^(-1/12)` multiply,
  ≤ 25 mpys per block. ✅ `make verify-midi`: notes 96/91/72/84 land within
  15 cents of the +12/+7/−12/unison selects; no-note is bit-identical.
- ~~Fader → FREEZE~~ built and then REMOVED the same evening (Sam: no
  hard-locks to the fader). Its A/B (fader 1 ≡ FRZE etc.) passed before
  removal, for the record.
- Cost: **payload B FREE 87 → 43** (44 words for the note path). `make
  check` green.
- Local override: `DNOTE=n` (plain note).

**Hardware checklist for the first flash** (needs Sam at the unit):
2. Does a note on the delay host's channel latch on a RETURN track? Read
   24 Aug: the per-track loop at `0x4000e724..0x4000e790` writes
   `0x400d64c2[t]` (`moveb %a3@,%a2@` at `0x4000e75a`) for EVERY track in
   the channel mask with **no machine-type test** ✅; the only skip is the
   currently-selected track when global `0x46104cb0` is set and
   `0x40033970` returns 0 🟡 (unread — likely an editor/chromatic-mode
   guard). Upstream filtering in the `0x4000e464` switch is by note range
   only per the scout. Expect it to work; if the selected track misbehaves,
   select a different track while playing.
4. `TPROBE`-style read of `r6+$8/$9` is NOT needed if 1–2 behave; keep it
   as the fallback diagnostic.

## Work order

1. ✅ **Tier-1 page 1 on hardware (24 Aug, no flash)**: CC 40 on T3's channel moved BongDelay TIME, CC 7 moved LEVEL; the OT echoes TIME as CC 40 with CC OUT on. Driven from `tools/ot_midi.py` (CoreMIDI via ctypes, no deps) through a Midihub `FROM A → FILTER(drop realtime) → OCTATRACK` pipe. Previously: ⬜: CC 40–45 on T1's channel
   → BongDelay TIME etc. (Sam, any controller.) Falsifier: nothing moves →
   the descriptor enable bitmap or the writer's disabled-slot check bites us.
2. ✅ **Cave v2** (built; relocation to the `0xff` padding deferred — the zero-run site is hardware-proven) (`modules/tempo-sync/tempo_cave.s`): fader + note words, relocate to the
   `0xff` padding. `make check` + hardware: `TPROBE`-style probe reading
   `r6+$8/$9` (`dsp/tempoprobe.asm` is the template).
3. ✅ **Tier 3 DSP** — built, local-verified, flashed as R57 and ear-confirmed on the unit 24 Aug (the fun one): table + decode branch, local render, ear
   pass, flash.
4. ❌ **Tier 2 DSP** built then removed (no fader hard-locks): fader → FREEZE with hysteresis; then voicing uses.
5. ❌ **DROPPED** (Sam, 24 Aug): CC → page 2 was only wanted for scene-style gestures, which the fader publish now covers; no external-controller use case.
6. ⬜ Docs: fold the corrections into `docs/history/NOTES.md` (scene morph)
   — DSP.md §6c-i and build_bus.py's comment were corrected 24 Aug.

## What would falsify the plan
- The cave's track index: `a0 − 0x80000110` is inferred from
  `modules/tempo-sync/tempo_cave.s`'s comment 🟡 — confirm in the writer before reading
  `0x400d64c2(track)`.
- Chromatic note-on on a **return** track (no sample) may be filtered before
  `0x400d64c2` is written (the switch at `0x4000e464` runs per listening
  track; whether it checks machine type is unread ⬜). If so, the delay host
  needs a sample machine with nothing loaded, or the cave reads the note from
  a different track (the source track) — a design choice, not a blocker.
- Page-2 live bytes not in the 72-byte block → tier 1 costs a real writer.

## Hardware findings — full MIDI-driven voice pass (24 Aug 2026 evening)

- **CC 40/41/43/44/45 (page-1 slots 0,1,3,4,5) work un-selected. CC 42 ->
  slot 2 (TONE) is the exception: the write lands in the Part (panel shows
  the new value) but reaches the DSP only while the host track's FX2 page
  is ON SCREEN.** Hand-turns always work (the page is necessarily up).
  Delay-specific: the reverb's slot 2 (SIZE, T5) takes CC fine un-selected.
  Enable bitmap, min/count clamp all verified sane in the image; the
  frame-builder path for this one slot is the remaining suspect. 🟡 UNTRACED.
  Practical rule for sets: automate TIME/FDBK/PING/-VRB/IN freely; TONE by
  hand.
- Chromatic notes 72-96 on a track's channel are the reliable remote
  trigger; **sample-trig notes 36-43 never fired on this project** (and a
  THRU track has nothing to trig). A note to the panel-SELECTED track is
  eaten (editor guard) — keep an empty track selected while driving notes.
- The note->PITCH interval latch (R57) re-measured exact on real sources:
  +12/+6/0/−5/−12 within 1/4 semitone (see VOICING.md).
- Transport: drive the RYTM over USB (`ot_midi.py -p "Elektron Analog Rytm
  MKII" start|stop`) — it is clock master; the OT follows. Never send
  start/stop to the OT's own port.
- **Midihub reverts to its stored preset on power/USB blips: SAVE the
  session pipes** (FROM A -> drop-realtime-only -> OCTATRACK). The reverted
  preset passed CC 40-48 but blocked notes and CC 49/50 — a very confusing
  partial failure.

## Remote CC reference (manual-confirmed 24 Aug 2026, for the gain-match session)

From the official appendices (OT MKII 1.40A Appendix C, AR MKII 1.72
Appendix C — URLs in the memory note `octabam-midi-cc-reference`). ✅ =
also exercised on our hardware; 🟡 = manual-only, unverified here.

**Octatrack, per-track channel**: CC 7 track level (receive-only) ✅,
CC 46 track level (trn+rec), CC 8 balance, **CC 25 AMP VOL** 🟡 (amp page =
CC 22–27), playback 16–21, LFO 28–33, FX1 34–39 🟡, FX2 40–45 ✅ (slot-2
on-screen quirk, above), CC 47 cue, 48 crossfader ✅, 49/50/51
mute/solo/cue, 55/56 scene A/B select. Pattern select via program change
needs PROG CH receive ON (PROJECT→MIDI→SYNC) 🟡.

**Rytm MKII, per-track channel** (needs RECEIVE CC/NRPN ON in MIDI
CONFIG): **CC 95 track LEVEL** 🟡, CC 7 amp VOLUME, CC 8x amp page (81
overdrive, 82/83 delay/reverb send), CC 31 sample level, 94/93
mute/solo. FX track channel: delay 16–23, reverb 24–31, distortion
70–77, **compressor 78–85** (78 thresh, 81 makeup, 84 mix, 85 output
vol) 🟡. Transport start/stop over its own USB port only ✅ — it is clock
master; never send start/stop to the OT.
