# Incoming MIDI CC → track parameter (OS 1.40C, ColdFire) — RE notes

Static disassembly of `out/raw/section_3_MAIN_OS.bin` (base `0x40000400`),
24 Aug 2026. ✅ = read straight off the disassembly. 🟡 = inferred.
Nothing here was run on a unit.

Tooling note: r2's m68k backend prints ColdFire-only opcodes (`mvs`/`mvz`,
`mulu.l`/`divu.l` with two ext words) as `invalid`; a small wrapper that
re-decodes them was used for every listing below. `aaa` segfaults on this
image; `aa` finds no data xrefs, so every cross-reference below came from a
raw byte scan for the 32-bit operand.

## 0. The pipeline in one line

```
UART bytes → (parser task) → queue 0x46c7e974 → MIDI-in task 0x40005540
  → dispatch table 0x400d6474[status>>4] → CC handler 0x4000e79c
  → post {kind,track,idx,value} to kernel queue 0x460d17ae (poster 0x400053d8)
  → main/UI task loop 0x40061cd2 → jump table 0x40061cfa[kind-1]
  → kind 0x40 → 0x40062496 → param writer 0x40054cd8(track, flat, value)
  → Part storage + live byte 0x80000810[track*72 + flat] + dirty marker
```

## 1. CC dispatcher ✅

**MIDI-in task** `0x40005540` (created at `0x400054c4`, stack `0x46c7ea20`,
prio 6): loops on blocking receive `0x40000d00(0x46c7e974)`, gets a 3-byte
event `{status, data1, data2}`, then

```
4000556a  mvz.b (a0),d0 ; lsr.l #4,d0
40005572  movea.l (a2,d0.l*4),a0     ; a2 = 0x400d6474
40005576  jsr (a0)
```

Dispatch table `0x400d6474` (status high nibble): 0..7 → `0x40001850` (rts),
8 → `0x4000db98` note-off, 9 → `0x4000e018` note-on, A → `0x4000a640`,
**B → `0x4000e79c` (CC)**, C → `0x4000da40` prog-change, D → `0x4000a51c`,
E → `0x4000a3e0` pitch-bend, F → `0x40001900` system.

**CC handler `FUN_4000e79c(msg*)`.** First it rebuilds the channel→track map
by calling `0x40001854`, which fills `0x46c7febe[16]` (one u32 per channel):

| bit | meaning | source |
|---|---|---|
| 0–7 | audio track t listens on this channel | `0x8000003f+t` = `MIDI_TRIG_CH1..8` (−1 = off) |
| 8 | this is the AUTO channel | `0x80000047` = `MIDI_AUTO_CHANNEL` |
| 16–23 | MIDI track t's channel | Part data `0x46c82456 + pat*0x18b2 + 0x8f262 + t*0x24` (0 = off, else ch+1) |

(Setting → variable mapping read from the project-settings parser at
`0x400873d0..0x40087e6e`; e.g. `MIDI_AUDIO_TRK_CC_IN` → byte `0x80000049`,
`MIDI_AUDIO_TRK_CC_OUT` → `0x8000004a`, `MIDI_MODE` → long `0x80000012`.)

Then it switches on the CC number. Everything below is gated on
`0x80000049` (AUDIO CC IN) except the auto-channel shortcut. `d7` = channel
mask, `d2 = d7 & 0x100` (auto channel); when the auto bit is set the track
argument is **8** ("current track"), otherwise the loop posts once per set
track bit.

| CC | code | what is posted / done |
|---|---|---|
| 7 (0x07), 46 (0x2e) | `0x4000ea4a` | track level: byte `0x80000c50+2t`, pattern copy, kind `0x43` |
| 47 (0x2f) | `0x4000eb54` | same, odd byte `0x80000c51+2t` (cue level 🟡) |
| 8 (0x08) | `0x4000e9d0` | `post(0x40, track, 10, value)` → AMP BAL |
| **16–45** | `0x4000e91c` | `idx = cc−16` (checked `< 30` at `0x4000e928`), `post(0x40, track, idx, value, stamp, 0)` |
| 48 (0x30) | `0x4000ec60` | `post(0x44, 0,0, value)` crossfader |
| 49/50/51 | `0x4000ec98` | mute/solo/cue bits in `0x80000008` (bits 8+t / t / 16+t) |
| 52/53 | `0x4000ed7e` | word masks `0x46c803d4` / `0x46c7fe22` (bit t / t+8) |
| 54 | `0x4000ee10` | set both masks to 0xff |
| 55/56 | `0x4000ee48` | scene A/B select, value clamped 0..15, `0x40170f70[...]` |
| 57/58 | `0x4000ef8c` | per-track byte in `0x4017156a`/`0x4017156c` (pickup 🟡) |
| 59/60 | `0x4000f10a`/`f14c` | synthesise note-on/off `{ch, value, 127}` → `0x4000e018`/`0x4000db98` |
| 61 | `0x4000f18c` | value 0 → post static msg `0x400d64c0` (send request 🟡) |
| 112–119 / 120–127 | `0x4000f1ce`/`f210` | bits 8–15 / 0–7 of `0x8000000c` (MIDI-track mute/solo 🟡) |

**Unused audio-track CCs in 0..119: 0–6, 9–15, 62–111** (50 contiguous free
numbers from 62). They fall through every compare to the `rts` at
`0x4000f274`. ✅

MIDI-track channels (mask bits 16+): the CC is copied to `0x400d2e79` and
handed to `0x40010bc8(3, buf)` (`0x4000e886`) — a pass-through, not a
CTRL-page write.

## 2. Page/slot mapping — page 1 only ✅

Poster `0x400053d8(kind, a, b, c, stamp, x)` writes a 12-byte record
`{kind, a, b, c, u32 stamp, u32 x}` into ring `0x46c7ff7e[64]` and posts its
pointer to queue `0x460d17ae` (`FUN_40000c3c`).

Consumer (main task, `0x40061cd2`): `kind−1` indexes the word jump table at
`0x40061cfa`. Kind `0x40` → `0x40062496`:

```
400624a6  d2 = msg[2]                   ; idx 0..29
400624ae  d1 = idx / 6                  ; CC group: 0 PB, 1 AMP, 2 LFO, 3 FX1, 4 FX2
400624c0  d0 = 0x400a7280[d1]           ; = {0, 2, 1, 3, 4}  → page_kind
400624cc  d3 = page_kind*6 + (idx − 6*d1)   ; "flat" index
400624dc  track = msg[1]; 8 → current track 0x80000000 (+8 if MIDI_MODE)
```

The table `0x400a7280 = {0,2,1,3,4}` re-orders the manual's CC groups
(PB, AMP, LFO, FX1, FX2) into the descriptor `page_kind` of `FUN_40031da4`
(0 PB, 1 LFO, 2 AMP, 3 FX1, 4 FX2). So:

| CC | page_kind | flat | slot |
|---|---|---|---|
| 16–21 | 0 PLAYBACK | 0–5 | 0–5 |
| 22–27 | 2 AMP | 12–17 | 0–5 |
| 28–33 | 1 LFO | 6–11 | 0–5 |
| 34–39 | 3 FX1 | 18–23 | 0–5 |
| **40–45** | **4 FX2** | **24–29** | **0–5 (page 1)** |

**No CC reaches page-2 slots 6..11.** The handler admits only `cc−16 < 30`,
and the writer's slot is `flat % 6`, so slots 6–11 are unrepresentable on
this path. ✅ (The knob path `0x40055008` uses the same `page*6+slot`
addressing off the six-entry encoder table `0x400c085a`; page-2 editing
goes through other code — the Part region at `+0x8ef5a`, read by
`0x4003a55a`, `0x4003ed34` etc., is the likely page-2 store 🟡, not
examined.)

## 3. The generic writer ✅

`FUN_40054cd8(int track, int flat, int value)` — callers: `0x40062530`,
`0x400625aa` (CC path) and `0x400a15f0`. The UI knob path does **not** call
it; it has its own near-copy `FUN_40055008(slot, delta)` (`0x40055008`) with
the same body. Steps, all measured:

1. `page_kind = flat/6`, `slot = flat%6`; descriptor `P = FUN_40031da4(track, page_kind)`.
2. Enable bitmap check `0x400a6994(P+0x18a, P+0x18e, slot*4)` bit 0 → else
   returns −1 (`0x40054d26`). A disabled slot is refused, not written.
3. `0x40027e00` / `0x40027e30` (project-dirty flags 🟡).
4. Audio track (`track ≤ 7`): storage address
   - PB page: `Part + 0x8edaa + track*30 + machine*7 + slot`
   - others: `Part + 0x8ee9a + track*24 + (flat − 6)` (24 B/track = AMP·LFO·FX1·FX2 × 6)
   plus a shadow copy at `0x100a4ef8`/`0x100a4fe8` + same offset.
5. Clears a per-track lock bit `0x80001538[t] &= ~(1<<flat)` and byte
   `0x80001658[t*32+flat]` (p-lock/override state 🟡).
6. **Clamp** (`0x40054dee`): `v = min(max(value, P+0x6a[slot]), P+0x6a[slot] + P+0x9a[slot] − 1)` — the descriptor's min and count are applied.
7. Stores `v` to Part, shadow and the **live byte `0x80000810[track*72 + flat]`**;
   writes `0xa0` to `0x80000db4[track*72 + (flat/4)*4]` (per-4-param group marker).
8. `0x4009da20(track)`; if the page is on screen (`0x460d1684 == page_kind`,
   current track) also marks `0x46c7d244[2*slot+1] = 0x14` (knob redraw).

MIDI tracks (`track ≥ 8`, `0x40054ea6`) go to `Part + 0x8f162 + (t−8)*32 + flat`
and call `0x4009eec8`.

**DSP publish**: the writer does not touch the DSP. The frame builder
(`0x4000c0f0..`) copies `0x80000810[track*72 + 0..29]` into the halfword
array `0x80000a50` as `value << 8` — which is exactly why knob values sit at
bits 16–23 of the DSP word (`PARAM_PAGES.md`). The same loop also fills a
second byte lane at `+0x20` (`0x80000830..`) from `0x4017113a`/`0x40171252`
and six more at `+0x3e`; that lane is the natural home of the page-2 /
companion bytes 🟡 (its source arrays were not traced). The `0xa0` marker
array `0x80000db4` is walked by the packer at `0x4000d648`. So a CC write
lands in the next frame's record; there is no explicit "publish" call.

## 4. Crossfader and channel→track ✅

CC 48 → kind `0x44` → `0x4006269a`: `0x460d16c8 = 127 − value`, then
rebuilds the 10-entry gain table `0x80003c60..0x80003c88` from the curve
`0x400bcd90[pos]` and calls `0x4003f1b4`.

The panel crossfader arrives as kind **`0x04`** → `0x40061e0a`, which is the
same code with `0x460d16c8 = msg[1]` (no inversion) and, if
`MIDI_AUDIO_TRK_CC_OUT` (`0x8000004a` bit 0), emits
`0x40033e3c(8, 0x30, 127 − v)` — CC 48 out — before jumping to `0x400626de`.
**Same variable, same table, same `0x4003f1b4`.** The poster of kind 4 (the
ADC scanner) was not located; the identification rests on the CC-48-out
echo and the shared body 🟡.

Readers of `0x460d16c8` (scene interpolation): `0x4003ee4c`, `0x4003f0d0`,
`0x4006ff34`, `0x400935a8`, `0x4009dd30`, `0x400a3126`, `0x400357cc`.

Channel → track: see §1 table; the map is rebuilt from `MIDI_TRIG_CHn`
(`0x8000003f+t`) on every CC, so it is always live. `MIDI_MODE`
(`0x80000012` ≠ 0) makes the auto channel address MIDI track
`current+8` (`0x40062502`) and, in the CC handler, short-circuits
CC 16–45 on the auto channel to track 8 regardless of AUDIO CC IN
(`0x4000e930`).

## 5. What would falsify this

- A CC 40–45 on a track whose FX2 page-2 knob moves: would mean a path
  outside `0x4000e79c` (none found in the dispatch table).
- A CC 62–111 doing anything on an audio track: would mean a compare I
  missed between `0x4000f1ce` and `0x4000f274` (the range test there is
  `cc−0x70 ≤ 7` then `cc ≥ 0x78`).
- A value outside `[min, min+count)` reaching `0x80000810`: would mean the
  clamp at `0x40054dee` is bypassed (only the three callers above exist).
