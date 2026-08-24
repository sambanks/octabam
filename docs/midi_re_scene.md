# Scene morph / crossfader — RE scout (24 Aug 2026)

Static read of `out/raw/section_3_MAIN_OS.bin` (base `0x40000400`), disassembled
with `m68k-elf-objdump -m m68k:cfv4e` (radare2's m68k plugin cannot decode
ColdFire `mvs/mvz/byterev/mac`, which is most of this code). Markers as in
`CHIP.md`: ✅ read from the code, 🟡 inferred, ⬜ not found.

## 0. Headline

* `FUN_4003f1b4` is **not** the general morph. It is a special path for the
  three playback-position parameters (STRT/LEN/RATE) that must reach the voice
  task as a message. **The general morph runs every DSP frame inside the frame
  builder `FUN_4000c8a4` (`0x4000cc6c..0x4000cf3e`)**, on the DSP-bound copy of
  the parameter halfwords, never on the live parameter words.
* A scene block covers **page 1 of five pages only — 30 knobs per track**.
  Page 2 (slots 6..11) and the companion fields are unreachable, and the
  exclusion is structural (block size, buffer size, loop extents), not one
  `cmp`. Recommendation: **Tier 2 (publish the fader value) — three
  instructions in the existing tempo cave.**

## 1. Scene block layout ✅

`base + pattern*0x18b2 + scene*0x100 + 0x8f3e2`, **8 tracks × 0x20 bytes**.
Scene byte *k* of a track is the lock for **DSP-frame halfword *k*** of that
track: the frame builder reads them 1:1 (`movew a2@+` → compute → `movew d3,a1@+`
at `0x4000ce60..0x4000ced4`). Frame halfwords are `knob<<8 | companion`
(ColdFire halfword → DSP 24-bit word `<<8`, `DSP.md` §6c).

| scene bytes | frame halfwords | page |
|---|---|---|
| 0..5 | page-block `0x80000510+ping·0x180+track·0x30`, hw 0..5 | PLAYBACK p1 (byte 1 = STRT, 2 = LEN, 3 = RATE ✅ from the STRT/LEN encoder hooks `0x4003eef0`/`0x4003ec7c` and `FUN_4003f1b4`) |
| 6..11 | same block, hw 6..11 | 🟡 AMP or LFO p1 |
| 12..17 | voice record `0x80000110+ping·0x200+track·0x40`, hw 0..5 | 🟡 the remaining one of AMP/LFO |
| 18..23 | voice record hw 6..11 | FX1 page 1 (`r6+0..5`) ✅ |
| 24..29 | voice record hw 12..17 | **FX2 page 1 (`r6+0..5`)** ✅ |
| 30..31 | — | **skipped**: `addql #4,%a2` at `0x4000cef6` |

**Not-locked sentinel: any negative byte (bit 7 set, i.e. `0xFF`)** — every
reader tests with `blt`/`bge` after a sign-extending load (`mvsb`). A lock is
the 0..127 knob value; it is shifted `<<8` into the halfword, so **a lock only
ever represents the knob byte**. FX2 page 2 (`r6+$c..$e` = voice-record
halfwords 24..26) has no scene byte, and the morph loop stops at halfword 17.

Shared-RAM working copy ✅: `0x80000ed4 + track*0x40`, bytes interleaved
`[A_k, B_k]` (A = scene selected at `+0x8ed90`, B = `+0x8ed91`). Filled by
apply-part (`0x40009424`, `0x40009bee`), pattern change (`0x4000225a`), the
frame builder itself on a selection change (`0x4000c24a`), and patched in place
by the scene editor (`0x40053a2c`: `0x80000ed5 + slot*2` for B). Exactly 32
pairs; no spare.

## 2. Morph arithmetic ✅

Crossfader position: **`0x460d16c8`, long, 0..127**. On every write the
handlers rebuild a **per-track weight table `0x80003c60`, 10 longs** (all the
same value today) — `0x40061e34`, `0x400626ae`:

```
T   = word table 0x400bcd90[xf]      = -258*xf  (T[127] = -0x8000)   -- linear
hi  = T[xf]                            (Q15: -xf/127)
lo  = (0x8000 - T[xf]) & 0xffff        (Q15: xf/127 - 1)
```

Frame builder, `macsr=0x60`, `msac` (multiply-subtract) on 16-bit halves,
one weight long per track. Per halfword (`0x4000ce60..`):

| A lock | B lock | result |
|---|---|---|
| yes | yes | `A·xf/127 + B·(1-xf/127)` |
| yes | no  | `A·xf/127 + knob·(1-xf/127)` |
| no  | yes | `knob·xf/127 + B·(1-xf/127)` |
| no  | no  | `knob` (× `0x8000` = 1.0, exact passthrough) |

So **xf = 127 ⇒ the `+0x8ed90` scene, xf = 0 ⇒ the `+0x8ed91` scene**, linear
in between, no rounding beyond the MAC's, **no clamp against the descriptor
count** (the lerp cannot leave `[min,max]` of its endpoints). The whole
16-bit halfword is interpolated, so for a locked knob the low byte
(companion / DSP bits 8-15) becomes fraction bits — harmless on page 1 where
the low byte is unused, fatal for any scheme that wanted to lock a companion.

Where it writes ✅: into the **ping-pong DSP frame** (`0x80000510+…` and the
voice records `0x80000110+…`), which the builder re-copies each frame from the
live blocks (`0x80000a50`/`0x80000830`, copy loop `0x4000cb2a`). The live
per-track parameter words (what the panel edits and the record writer
`0x40004bd2` publishes ids into) are never modified. Every frame, all 8 tracks.

Scene disable flags ✅: `0x80000006` / `0x80000007` (toggled by `0x4004d928` /
`0x4004d908`, mirrored at `0x100b14d2/d3`). One set → that scene is treated as
absent (branches `0x4000cd7a` = A-only, `0x4000cc96` = B-only, same maths,
`byterev` to pick the byte). Both set → morph skipped and the crossfader-volume
words forced to `0x7f00`. XVOL is a separate A/B halfword array `0x800010d4`
(10 entries) → `0x80000c80` (`0x4000cd22`, `0x4000cefc`) — that is where
`AMP p5 XVOL` goes, confirming `PARAM_PAGES.md`'s warning.

`FUN_4003f1b4` ✅: runs only when `0x460d16c8 != 0x400c0c44` (last value),
loops 8 tracks, reads scene bytes 1..3 of A and B, defaults from Part
`+0x8edab/ac/ad + track*0x1e`, same lerp (`(B−A)·2T + B<<16`, rounded), and
posts message type `0x0e` (STRT/LEN/RATE + sample slot) to queue `0x460d17ee`
via `0x40000c3c`. Callers: the two fader-event handlers (`0x400626de`) and
`0x40055fa6`. Tail-jumps to `0x4003577c` = crossfader display (icon
`0x400bcd7c[4 − (xf+16)>>5]`).

## 3. How the position gets there

Event loop `FUN_40061a94`, queue `0x460d17ae`, jump table `0x40061cfa`
(index = type − 1):

* **type 4 → `0x40061e0a`** ✅: `xf = a2@(1)` raw, **gated on `0x8000004a`
  bit 0**; rebuilds weights, draws UI element `0x30` with `127 − xf`, then
  `FUN_4003f1b4`. **Producer of the type-4 event ⬜ not located** — no static
  message buffer in the image carries type 4, and it is not the DSPI RTC/panel
  helpers at `0x4001c360..`. Likely a dynamic buffer from the panel/ADC task;
  find by breakpointing `0x40061e0a` or by the `0x8000004a` writer.
* **type 0x44 → `0x4006269a`** ✅: `xf = 127 − a2@(3)`, same weights, same
  `FUN_4003f1b4`. Produced by the **MIDI CC parser at `0x4000ec60`**:
  `moveq #48; cmp d1` → gated by `FUN_40033970` / bit 8 of the track's MIDI
  word / `0x80000049` → `FUN_400053d8(0x44, 0, 0, value, 0, 0)` (generic
  poster, ring of 12-byte messages at `0x46c7ff7e`). **So MIDI CC 48 writes the
  same variable, inverted.** 🟡 If CC48 = 0 is "scene A" per the manual, then
  xf = 127 is the A end and `NOTES.md`'s A = `+0x8ed90` labelling holds.

## 4. Assessment for our slots

**None of ChonVerb SHMR (6) / MODE (7) / GATE (10), BongDelay FRZE (11) /
MODE (7) can be scene-locked**, and nothing on page 1 can carry a companion
lock either. Page-1 slots 0..5 of both effects morph today with no work.

Where the exclusion lives — all would have to change together:
1. Block size: 0x20 bytes/track/scene in the project (`0x8f3e2` stride, 24 code
   sites incl. copy/paste/undo at `0x40025b40`, `0x400274cc`, `0x400275a0`).
2. Working copy `0x80000ed4`: 0x40/track, 32 pairs, all fillers assume 32.
3. Frame-builder extents: `moveq #6` (page block) and `moveq #9` (voice
   record) at `0x4000ccb6/0x4000cd0e`, `0x4000cd96/0x4000cdea`,
   `0x4000ce5e/0x4000cee8`; skip at `0x4000cef6`. Halfwords 24..26 are 7 longs
   past where the record pass stops.
4. The scene editor's slot→byte map (`0x40053a2c` region) and the two
   encoder-hook descriptors at `P+0x12a` that call the STRT/LEN morph.
5. The arithmetic itself, to leave the low byte alone.

Two spare bytes per track could host **one** extra halfword, not three, and
the DSP-side companion packing would still be lost at every intermediate
position. Not worth it.

**Do instead (Tier 2)** 🟡: in `cf/tempo_cave.s` (hooked at `0x40004d40`,
`a2` = this track's record) add `move.l 0x460d16c8,%d0 ; move.w %d0,0x28(%a2)`
inside the id-6/7 branch → `r6+$8` (documented dead) carries 0..127 every
frame for our servers. The DSP thresholds FREEZE/MODE with hysteresis, and
because `0x460d16c8` is fed by both the hardware fader and CC 48, MIDI comes
for free. Per-track fader values, if ever wanted, already have a home: the
weight table at `0x80003c60` is indexed per track.

Falsifiers: a hardware flash where the fader at the A end changes a page-1
lock the wrong way (would invert §2's endpoint claim); a `TPROBE`-style capture
showing `r6+$8` not tracking the fader (would mean the cave hook is not
per-frame for that track).
