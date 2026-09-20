# MIDI: how a CC, a scene or a note reaches a parameter the DSP reads

The summary first; the three disassembly records (CC, note, scene) follow
as appendices A-C (they were `midi_re_{cc,note,scene}.md` until 16 Sep
2026). Markers as in `CHIP.md`: ✅
measured / decompiled, 🟡 inferred. r2's m68k backend misdecodes ColdFire
`mvs/mvz/mov3q/mac`; read this code with `m68k-elf-objdump -m m68k:cfv4e`
(`scripts/disasm.sh emac`).

## MIDI in → parameters ✅

UART0 `0xfc060000` is MIDI IN; RX ISR `0x400106ec`, framer `0x40092bf4`
(running status `0x46100b70`), the MIDI thread `0x40005540` dispatching on
`status>>4` via `0x400d6474`: note-off `0x4000db98`, note-on `0x4000e018`,
CC `0x4000e79c`; realtime via `0x40001900` → `0x400d2d98` (F8 →
`0x40005a48`, a clock/tempo estimator writing `0x80001818/14`).

**CC map** (handler `0x4000e79c`): CC 16-45 → `idx = cc−16` (bounds `<
30`), posted as kind `0x40` to the kernel queue `0x460d17ae`; consumer
`0x40062496` maps `idx/6` through `{0,2,1,3,4}` to page_kind, `flat =
page_kind·6 + idx%6`. CC 40-45 = FX2 slots 0-5 (page 1). Other CCs: 7/46
level, 47 cue, 8 AMP BAL, 48 crossfader, 49-51 mute/solo/cue, 52-54 arm,
55/56 scene select, 59/60 synth note on/off, 61 send request, 112-127 →
`0x8000000c`. Unused: 0-6, 9-15, 62-111.

Page 2 is unreachable from stock CC: `cc−16 < 30` and the writer derives
`slot = flat % 6`. `modules/ccpage2` adds CC 62-67 (FX2 page 2) and
68-73 (FX1 page 2).

**The generic writer `FUN_40054cd8(track, flat, value)`** ✅ resolves the
descriptor via `FUN_40031da4(track, flat/6)`, refuses disabled slots,
clamps to `[min, min+count−1]` from `P+0x6a/P+0x9a`, stores to the Part
(`+0x8ee9a + track·24 + flat−6` for AMP/LFO/FX1/FX2), a shadow, and the
live byte `0x80000810[track·72 + flat]`; the frame builder `0x4000c0f0`
copies those `<<8` into the DSP frame every frame (why knobs sit at bits
16-23). The UI knob path is a near-copy, `FUN_40055008(slot, delta)`.
Page 2 is in the same 72-byte block ✅: an FX2 page-2 slot's live byte is
`0x80000810 + track·72 + 32 + slot2` (traced on tracks 0/1/4/7); page 1
occupies `+0..+29`. The FX2 page-2 editor's stores are Part `+0x8f084`,
shadow `0x100a51d2`, lane +0x38; the FX1 page-2 editor `0x4003abe4`
writes Part `+0x8f07e + track·30 + slot`, shadow `0x100a51cc`, lane
+0x32 (`PARAM_PAGES.md`, `FAILURE_MODES.md`).

## Scenes / crossfader ✅

`FUN_4003f1b4` handles only STRT/LEN/RATE. The general morph runs every
DSP frame inside the frame builder `FUN_4000c8a4` (`0x4000cc6c..0x4000cf3e`)
on the ping-pong frame copy; live param words are never touched. Scene
block = 8 tracks × 0x20; byte *k* ↔ frame halfword *k*; bytes 24-29 = FX2
page 1 (`r6+0..5`); the loop stops at halfword 17 of the page block; `0xFF`
= not locked. A lock is the knob byte `<<8` and the whole 16-bit halfword
is lerped (`A·xf/127 + B·(1−xf/127)`, MAC unit, weights `0x80003c60` from
curve `0x400bcd90`), so companion bits become fraction bits: page 2
cannot be scene-locked.

Fader position: `0x460d16c8` (long, 0..127), written by the panel path
(`0x40061e0a`, raw) and by CC 48 (`0x4006269a`, `127−value`); `xf=127` ⇒
scene A. Nothing of ours is hard-locked to the fader, and nothing of ours
reads it on the DSP.

## Notes ✅

Channel→track route `0x46c7febe[16]` from per-track channel
`0x8000003f+t` (−1 off) + auto channel `0x80000047`. Audio note map
(`0x4000e464`): 36-43 = sample trig of track note−36; 72-96 = chromatic
play (`0x4000e6e2`), which p-locks PTCH `64+5·(note−84)`, writes the held
note `0x400d64c2[t]` (byte, `0xFF` on release), a gate bit in
`0x46c7fb08`, and posts event 0x41. Velocity is never retained for audio
tracks. Per-channel held count `0x46c7fe4c[chan·4]`. The per-track loop
`0x4000e724..0x4000e790` writes `0x400d64c2[t]` for every track in the
channel mask with no machine-type test ✅; the only skip is the
panel-selected track when `0x46104cb0` is set and `0x40033970` returns 0
🟡 (an editor guard). On hardware: chromatic notes 72-96 on a track's
channel trigger reliably; sample-trig notes 36-43 never fired on the test
project; a note to the panel-selected track is eaten (keep an empty track
selected while driving notes).

## The DSP record ✅

The record (32 halfwords per track) is fully rewritten every frame
(`0x4000cb6e..0x4000cb7c` copies `0x80000830+72t` into `+0x24..+0x3d`
before `jsr 0x40004bd4`). Every halfword is read by something: `+0x24..
+0x28` (18-20) are the FX1 instance's page 2 (`r6_FX1+$c..$e` = `r6_FX2+
$6..$8`), `+0x2a..+0x2e` (21-23) the AMP page 2 (`r6_block+$15..$17`,
read by the dispatcher at P:0x231), `+0x30..+0x34` (24-26) the FX2 page 2,
`+0x36/+0x38` the ids, `+0x3a..+0x3e` (29-31) the writer's own words: a
per-track table word, the flag/split word (`r2+$1e`) and **tempo24
(`0x8000181c`) at `+0x3e`**, stored by stock at `0x40004d6a` for every
track. Retracted 15 Sep 2026: "`+0x24..+0x2c` are dead" (they were read
by no FX2 effect; the FX1 effect on the same track reads them).

The tempo cave (`modules/tempo-sync/tempo_cave.s`, hooked at `0x40004d40`
in the per-frame voice-record writer, for FX2 id 6) publishes one byte:

```
+0x1b  r6+$1 bits 8-15   held note (0x400d64c2[track]) or 0 on release
                         (the low byte of BusDelay's TIME halfword)
```

BusDelay reads tempo24 at `r6+$13` (`+0x3e`) and derives the MIDI-clock
period (42,336,000 / tempo24, Q12.4) per block. Until 15 Sep 2026 the cave
stored tempo24, the period, fader+1 and the note at `+0x24..+0x2a` (FX2
ids 6 and 7), which clobbered the FX1 page 2 and the AMP page 2's first
halfword on every host track (`docs/remixer/FAILURE_MODES.md`).

The track index is `a0 − 0x80000110` (`moveal %d4,%a0 ; addal
#0x80000110,%a0` at `0x40004d38`).

## Note → pitch on the DSP ✅

BusDelay latches the note in `y:>$090a` (HOLD: the last note sticks after
note-off; a never-received note leaves the PTCH knob in force). In GRAIN
the note drives the continuous pitch, `2^((note−84)/12)`, ±24 semitones.
`tools/verify/verify_midi.py` checks the note against the PTCH knob path
(bit-identical at unison, spectral elsewhere); `DNOTE=n` is the local
override. Hardware-confirmed: +12/+6/0/−5/−12 within 1/4 semitone.

## Hardware findings

- CC 40/41/43/44/45 (page-1 slots 0,1,3,4,5) work un-selected. CC 42 →
  slot 2 (TONE on the delay) lands in the Part (the panel shows the new
  value) but reaches the DSP only while the host track's FX2 page is on
  screen; the reverb's slot 2 (SIZE, T5) takes CC un-selected. Enable
  bitmap and min/count clamp verified sane in the image; the frame-builder
  path for that slot is the suspect. 🟡 untraced, single-slot; not a
  general rule and not page 2's.
- The OT echoes TIME as CC 40 with CC OUT on.
- Transport: the Rytm is clock master over its own USB port
  (`ot_midi.py -p "Elektron Analog Rytm MKII" start|stop`); never send
  start/stop to the OT's own port.
- A Midihub reverts to its stored preset on power/USB blips: save the
  session pipes (FROM A → drop-realtime-only → OCTATRACK).

## Remote CC reference

From the official appendices (OT MKII 1.40A Appendix C, AR MKII 1.72
Appendix C). ✅ = exercised here; 🟡 = manual-only.

**Octatrack, per-track channel:** CC 7 track level (receive-only) ✅, CC
46 track level (trn+rec), CC 8 balance, CC 25 AMP VOL 🟡 (amp page = CC
22-27), playback 16-21, LFO 28-33, FX1 34-39 🟡, FX2 40-45 ✅ (the slot-2
quirk above), CC 47 cue, 48 crossfader ✅, 49/50/51 mute/solo/cue, 55/56
scene A/B select. Pattern select via program change needs PROG CH receive
ON (PROJECT→MIDI→SYNC) 🟡.

**Rytm MKII, per-track channel** (RECEIVE CC/NRPN ON in MIDI CONFIG): CC
95 track LEVEL 🟡, CC 7 amp VOLUME, CC 8x amp page (81 overdrive, 82/83
delay/reverb send), CC 31 sample level, 94/93 mute/solo. FX track channel:
delay 16-23, reverb 24-31, distortion 70-77, compressor 78-85 (78 thresh,
81 makeup, 84 mix, 85 output vol) 🟡. Transport start/stop over its own
USB port only ✅.

---

## Appendix A: Incoming MIDI CC → track parameter (record)

Static disassembly of `out/raw/section_3_MAIN_OS.bin` (base `0x40000400`).
✅ = read off the disassembly or measured on hardware. 🟡 = inferred. Every
cross-reference came from a raw byte scan for the 32-bit operand (r2 finds
no data xrefs on this image and misdecodes the ColdFire-only opcodes).

### 0. The pipeline in one line

```
UART bytes → (parser task) → queue 0x46c7e974 → MIDI-in task 0x40005540
  → dispatch table 0x400d6474[status>>4] → CC handler 0x4000e79c
  → post {kind,track,idx,value} to kernel queue 0x460d17ae (poster 0x400053d8)
  → main/UI task loop 0x40061cd2 → jump table 0x40061cfa[kind-1]
  → kind 0x40 → 0x40062496 → param writer 0x40054cd8(track, flat, value)
  → Part storage + live byte 0x80000810[track*72 + flat] + dirty marker
```

### 1. CC dispatcher ✅

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

### 2. Page/slot mapping — page 1 only ✅

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

### 3. The generic writer ✅

`FUN_40054cd8(int track, int flat, int value)` — callers: `0x40062530`,
`0x400625aa` (CC path) and `0x400a15f0`. The UI knob path does **not** call
it; it has its own near-copy `FUN_40055008(slot, delta)` (`0x40055008`) with
the same body. Steps, all measured:

1. `page_kind = flat/6`, `slot = flat%6`; descriptor `P = FUN_40031da4(track, page_kind)`.
2. Enable bitmap check `0x400a6994(P+0x18a, P+0x18e, slot*4)` bit 0 → else
   returns −1 (`0x40054d26`). A disabled slot is refused, not written.
3. `0x40027e00` / `0x40027e30` (project-dirty flags 🟡).
4. Audio track (`track ≤ 7`): storage address
   - PB page: `Part + 0x8edaa + track*30 + machine*6 + slot` (`0x40054d7e..88`
     computes `(m<<3) − m*2`; octalab's validator reading agrees, `EXTERNAL.md` §9.2)
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
second byte lane at `+0x20` (`0x80000830..`) and six more at `+0x3e`. Page 2
is that `+0x20` lane ✅ (`0x80000810 + track*72 + 0x20 + slot2` for the
PLAYBACK page; FX2 page 2 at `+0x38`, FX1 page 2 at `+0x32`; §6). The `0xa0`
marker array `0x80000db4` is walked by the packer at `0x4000d648`. A CC
write lands in the next frame's record; there is no explicit "publish" call.

### 4. Crossfader and channel→track ✅

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

### 5. What would falsify this

- A CC 40–45 on a track whose FX2 page-2 knob moves: would mean a path
  outside `0x4000e79c` (none found in the dispatch table).
- A CC 62–111 doing anything on an audio track: would mean a compare I
  missed between `0x4000f1ce` and `0x4000f274` (the range test there is
  `cc−0x70 ≤ 7` then `cc ≥ 0x78`).
- A value outside `[min, min+count)` reaching `0x80000810`: would mean the
  clamp at `0x40054dee` is bypassed (only the three callers above exist).

### 6. Page 2 over CC: the mechanism, measured on hardware ✅

Page 2 reaches the engine through the live lane: the per-frame copier
`0x4000cae8` (and its twin `0x40003d14`) ships `0x80000a50`'s halfwords and
the `+0x20`.. lane bytes to the host-port staging every frame,
unconditionally. There is no DSP post on the page-2 path (page 1's writer
calls the resolver `0x4009da20`, which posts a kind-0x0f record to the DSP
parameter queue `0x460d17ee`, consumed at `0x4009204c`). The `0x40170f8a` /
`0x4017107a` "frame builders" are load-time refreshers from project
storage, and the `0x80000db4` marker packer covers page-1 bytes 0..31 only.

Each page has its own editor, and a cave must reproduce that editor's
stores exactly (Part store, shadow, part-changed bits, the global "edited"
flag, the live lane byte); without the bookkeeping stores the Part store is
inert, and a store at the wrong displacement is silent.

| page | editor | Part store | shadow | live lane |
|---|---|---|---|---|
| PLAYBACK page 2 | `0x4003a474 (slot2, delta)` | `DB + part*6322 + 0x8ef5a + track*30 + slot2` (`part` = byte `0x80000003`, `track` = byte `0x80000000`) | `0x100a50a8 + …` | `0x80000830 + track*72 + slot2` (+0x20) |
| FX2 page 2 | `0x4003aab2` | `DB + part*6322 + 0x8f084 + track*30 + slot2` | `0x100a51d2 + …` | +0x38 |
| FX1 page 2 | `0x4003abe4` | `DB + part*6322 + 0x8f07e + track*30 + slot` | `0x100a51cc + …` | +0x32 (`0x80000842 + track*72 + slot`) |

Each editor clamps with the descriptor's min/count at index `slot2+6`
(`a5@(0x6a+(slot+6)*4)`, `+0x9a`), sets `DB+0x95048 |= 1<<part`,
`0x100b145e |= 1<<part`, `DB+0x9b332 = 1` and the global `0x100f8598 = 1`,
writes the lane byte, sets the redraw flag `0x46c7d244[slot2*20+4] = 0x14`
and tail-jumps to the page redraw. The FX2 dial reads the displayed value
from the Part via the page cache.

`modules/ccpage2` (CC 62-67 → FX2 page 2, CC 68-73 → FX1 page 2) makes the
FX2 editor's stores for 62-67 and the FX1 editor's for 68-73. Its first
versions used the PLAYBACK editor's stores (reading `0x4003a474` as "the
page-2 editor"), so CCs corrupted the track's PLAYBACK page-2 byte and never
touched FX2's; confirmed fixed on image 96 (CC 63 on channel 5 moved SHMR
on the panel and the tail's 2-8 kHz bands). Not measured: whether an FX1
page-2 edit at the panel reaches the DSP on a THRU track
(`docs/remixer/FAILURE_MODES.md`).

Tooling: `tools/hw/hw_bus_test.py` (synchronous paired A/B over MIDI with
capture, a page-1 control proving the harness each run), an emulator
write-diff of the editor against the cave (every store, same inputs),
`tools/verify/verify_ccpage2.py` (the cave's writes for all eight tracks
against the FX2 editor under the emulator).


---

## Appendix B: MIDI input path: parser, dispatch, note-on (record)

Tooling: `m68k-elf-objdump -D -b binary -m m68k:cfv4e --adjust-vma=0x40000400
out/raw/section_3_MAIN_OS.bin` (radare2's m68k plugin does not decode the
ColdFire `mvs/mvz/mov3q/mac` forms; objdump does). Every address below is
read from that listing. **M** = measured (instruction sequence quoted or
table read from the image), **I** = inferred.

### 1. Byte parser and dispatch

**UART0 (`0xfc060000`) is MIDI IN** (M): both callers of the UART0 init
`0x40011000` pass baud `0x7a12` = 31250 (`0x4001f9c0`) or 312500/10
(`0x40063456`) and the byte callback `0x40092bbc`.

- **RX ISR `0x400106ec`** (vector 0x5a, installed at `0x400110a6`): reads
  `0xfc06000c` while USR bit 0 (RXRDY); for **`0xF8` only** it latches the
  DMA-timer counter `0xfc07000c` into `0x46c8345a` and the delta into
  `0x46c83466` (`0x40010702..0x4001071e`) — a hardware timestamp per clock
  tick; then calls the callback through `0x460ba97c`.
- **Callback `0x40092bbc`**: 32-byte ring `0x46104c84` (head `0x46100b80`,
  count `0x46100b7c`), then forces INTC source 36 (`or #0x10,0xfc048010`).
- **Framer `0x40092bf4`** (vector 0x64, level 4, installed by `0x40092f08`,
  ends in `rte`): pops the ring and does the MIDI framing:
  - status `0xF8..0xFF` (`and #0xf8; cmp #0xf8`, `0x40092c58`): 1-byte
    ring `0x46104b84[0x46100b64]`, posted immediately to queue
    `0x46c7e974` via `0x40000c3c`.
  - `0xF0`/`0xF7`/`0xF6` sysex handling (`0x40092cac`/`0x40092cc6`/`0x40092d40`).
  - other status: **running status = `0x46100b70`**, "2nd data byte
    pending" = `0x46100b74` (`0x40092d60`). Data bytes: status>>4 in 8..B
    or E → 3-byte message, C/D → 2-byte (`0x40092dda..0x40092e28`); F2 3-byte,
    F1/F3 2-byte. Completed messages are appended to the 8 KB buffer
    `0x46100b84` (write index `0x46100b5c`, read `0x46100b60`) and a pointer
    is posted to queue `0x46c7e974`.
- **MIDI thread `0x40005540`** (created at `0x400054c4`, stack
  `0x46c7ea20`, prio 6): loops `0x40000d00(0x46c7e974)` (blocking receive),
  then `jsr table[status>>4]` with **table `0x400d6474`** (M, read from image):

  | idx | handler | |
  |---|---|---|
  | 0-7 | `0x40001850` | (data bytes, never posted) |
  | 8 | `0x4000db98` | **note off** |
  | 9 | `0x4000e018` | **note on** (vel 0 → falls into `0x4000db98`, `0x4000e044`) |
  | A | `0x4000a640` | poly AT |
  | B | `0x4000e79c` | **CC** |
  | C | `0x4000da40` | program change |
  | D | `0x4000a51c` | channel AT |
  | E | `0x4000a3e0` | pitch bend |
  | F | `0x40001900` | system: `jmp table 0x400d2d98[status&0xF]` |

  Realtime table `0x400d2d98` (M): `F8 → 0x40005a48` (clock), `FA →
  0x4000a274` (start), `FB → 0x4000a200` (continue), `FC → 0x4000a1e0`
  (stop), `F0 → 0x40001918` (sysex), `FE → 0x400019d8` (active sense).

**Clock `0x40005a48`** (M): gated on `0x80000028` bit 0 (CLOCK RECEIVE);
uses the ISR delta `0x46c83466`, a 24-entry ring `0x46104daa`, computes
tempo24 into `0x46104d96`, clamps 600..7320, writes `0x80001818`, and on the
first tick after start clamps 720..7200 into `0x80001814` (`0x40005c4a`) and
posts token `0x400d64bf` to the sequencer queue `0x460d17ae`. (The tempo
cave reads `0x8000181c`; the hand-off `1814/1818 → 181c` is elsewhere — I.)

### 2. Note-on for audio tracks (`0x4000e018`)

Message layout: `a4`=status, `a3`=note, `a5`=velocity. `d4` = channel.

1. `jsr 0x40001854` rebuilds the **channel→track route table
   `0x46c7febe[16]`** (M): for audio track t, byte **`0x8000003f + t` is the
   track's MIDI channel** (0..15, `-1` = off) → bit t; MIDI tracks' channels
   (from part data) → bits 16+t; **auto channel = byte `0x80000047`** → bit 8.
2. `d3 = 0x46c7febe[chan]`. Per-channel note bookkeeping (M):
   `0x46c803d6 + chan*0x200 + note*4` = on-timestamp (long, `-1` when off,
   initialised by `0x400054f4`), and **`0x46c7fe4c[chan*4]` = held-note count
   per channel** (incremented `0x4000e084`, decremented in note-off
   `0x4000dbf6`). These are per CHANNEL, not per track.
3. If `d3.w == 0` → MIDI-thru/MIDI-track path (`0x40010bc8` = UART send).
4. Audio path (`0x4000e34c`, gated on `0x8000004b` ≠ 0, the AUDIO NOTE IN
   setting): octave = note/12, `switch` at `0x4000e464` (M):
   - **notes 24-31** (`0x4000e474`): MIDI-track/part functions
     (`0x4009b290`, `0x4009b5c8`, `0x4009f3a4`).
   - **notes 36-43** (`0x4000e542`): **sample trig of track note-36** —
     `jsr 0x40005030(track, 0x1d, 1, -1)` then event `0x42`. `0x40005030`
     is the voice-command writer: `0x8000186e[t*4]` ← lookup, `0x8000188e[t*4]`
     ← flags|0x100, and a halfword into `0x80000110 + 2*(0xbcf+t)` =
     `0x800018ae + 2t` (machine<<10 | sample) — the mailbox family from
     ARCHITECTURE §6 (M for the stores, I for the naming).
   - **notes 48-55** (`0x4000e5e2`): part/mute functions.
   - **notes 60-71** (`0x4000e668`): events `0x45`/`0x4b` (index note-60/-66).
   - **notes 72-96 = chromatic play** (`0x4000e6e2`, M). For every track t
     whose bit is set in `d3` (or only the active track `0x80000000` when
     the message came on the auto channel):
     ```
     0x4000e746  0x46c80354[t*4]      = 0x1d          ; per-track voice command
     0x4000e758  0x46c7dfda[t*32 + 0] = (5*note-100)&0xFF   ; = 64 + 5*(note-84): PTCH lock byte
     0x4000e75a  0x400d64c2[t]        = note          ; per-track HELD NOTE (byte)
     0x4000e766  0x46c7fb08          |= 1<<t          ; per-track GATE mask (byte)
     0x4000e77e  event 0x41 (t, note, 0, 0x46104cf4)  -> queue 0x460d17ae
     ```
     **Velocity is not stored for audio tracks** (M: the 0x41 event's third
     argument is `clrl`, and `a5@` is only read for the 0x46 MIDI-track
     event). The `0x41` handler (`0x400625b8`, table at `0x40061cfa`) only
     feeds live recording (`0x40042d1c`) when the sequencer is in REC.

   The trigger itself is **not** a mailbox write from the MIDI thread: the
   frame path consumes `0x46c80354[t]` (M): `0x4000b540` tests bit 0,
   `0x4000b760..0x4000b786` copies the 32-byte lock block
   `0x46c7dfda + t*32` to **`0x80001558 + t*32`** and refills the source with
   `-1` (`mov3q #-1`), then clears `0x46c80354[t]` (`0x4000b7bc`). Bit 6
   (`0x40`, written by note-off) is the release (`0x4000b4e4`). So MIDI
   chromatic play = "trigger with a PTCH p-lock", which is why it pitches
   the sample (I for the label "p-lock"; the copy and the -1 refill are M).

**Note-off `0x4000db98`** chromatic case (`0x4000df9e..0x4000dffe`, M): for each
listening track, if `0x400d64c2[t] == note`: `0x46c80354[t*4] = 0x40`,
`0x400d64c2[t] = 0xFF`, clear bit t of `0x46c7fb08`. Trig case (36-43) at
`0x4000de7e`: `0x46c80354[t]=0x40`, clear gate bit.

### 3. Per-frame readable state (for a cave)

| what | address | stride | lifetime | conf. |
|---|---|---|---|---|
| held chromatic note | `0x400d64c2` (byte) | 1 per track, 8 bytes | note while held, `0xFF` after note-off; image initial bytes are `ff×8` (`0x400d64c2..c9`) | M |
| gate mask | `0x46c7fb08` (byte) | bit t | set on note-on, cleared on note-off; also OR-ed into a "track active" test at `0x4000b85a` | M |
| pitch actually applied | `0x80001558 + t*32`, byte 0 | 32 | from trigger until next trigger of that track; `0xFF` = no PTCH lock (sequencer trig without lock) | M copy, I lifetime |
| pending command | `0x46c80354 + t*4` (long) | 4 | one frame (0x1d on, 0x40 off), cleared by the frame path | M |
| held-note count | `0x46c7fe4c + chan*4` | per channel | live | M |
| track MIDI channel | `0x8000003f + t` | 1 | setting | M |
| velocity | — | — | **not retained for audio tracks** | M |

`0x400d64c2` lives inside the OS image's data (written at run time; only 2
code refs, `0x4000dfba` and `0x4000e70a`), so a cave in `0x40004bd2` can
read it with one `move.b 0x400d64c2(track)` — same shape as the tempo cave
reading `0x8000181c`. Mapping note→track is already done by the firmware;
nothing per channel needs decoding.

### 4. Record halfwords +0x24..+0x38 — a correction

The 0x40-byte per-track record (`0x80000110 + ping*0x200 + t*0x40`) is
**fully written every frame** by the frame builder's copy loop at
`0x4000cb2a..0x4000cb98` (same function as the writer call; no `rts`
between `0x4000c8a4` and the `jsr 0x40004bd4` at `0x4000d0e4`, M):

```
4000cb4e  moveml d0-d5,(a0)      ; +0x00..+0x17  <- 0x80000a50+64t [24..47]
4000cb5e  moveml d0-d2,(a0)      ; +0x18..+0x23  <- 0x80000a50+64t [48..59]  (FX2 r6+0..5)
4000cb6e  move.w d1,(a0)+        ; +0x24         <- 0x80000830+72t [18..19]
4000cb70  move.l d2,(a0)+        ; +0x26..+0x29  <-            [20..23]
4000cb74  move.l d0,(a0)+        ; +0x2a..+0x2d  <-            [12..15]
4000cb76  move.w d1,(a0)+        ; +0x2e         <-            [16..17]  (r6+$b)
4000cb7a  move.l d3,(a0)+        ; +0x30..+0x33  <-            [24..27]  (r6+$c,$d)
4000cb7c  move.w d4,(a0)+        ; +0x34         <-            [28..29]  (r6+$e)
```

then `0x40004bd4` writes +0x18/+0x22 (clear on some condition), +0x35 (byte),
+0x36, +0x38, +0x3a, +0x3c, +0x3e (M). So **"record bytes 0x24..0x2c that
nothing writes" (DSP.md 6c-i, build_bus.py comment) is false on the
ColdFire side**: they are re-written every frame from the per-track live
parameter bytes at `0x80000830 + 72t` (byte-indexed param stores, e.g.
`0x4003ad08` into `0x842+72t+idx`, `0x4003af10` into `0x83c+72t+idx`). The
tempo cave works only because the writer — and therefore the cave — runs
**after** the copy loop in the same frame, so its +0x24/+0x26 values win (M
for order). What remains true is the DSP-side claim: stock effects never
read `r6+$6..$a` (DSP.md line 1248, "probed explicitly").

Consequences:
- Candidates with the same status as +0x24/+0x26: **+0x28, +0x2a, +0x2c**
  (`r6+$8,$9,$a`) — overwritten each frame, unread by the DSP, so a cave
  store placed at the hook wins. +0x2e (`r6+$b`) and +0x30..+0x34 are live
  page-2 parameters; +0x36/+0x38 the FX ids; +0x3a..+0x3e the writer's own.
- Nothing in +0x24..+0x38 is unwritten. Any cave value there survives
  exactly one frame and must be re-stored every hook pass (as the tempo
  cave already does).
- What would falsify the "harmless" part: a stock effect that reads
  `r6+$6..$a` — DSP.md says none does; the ColdFire consumer at
  `0x4000d12c..0x4000d156` (staging copy to `0x80001a00`/`0x80001b80`) reads
  only +0x18..+0x23, +0x30..+0x35 and +0x38 (M), so no ColdFire reader of
  +0x24..+0x2f was found either.


---

## Appendix C: Scene morph / crossfader (record)

Static read of `out/raw/section_3_MAIN_OS.bin` (base `0x40000400`), disassembled
with `m68k-elf-objdump -m m68k:cfv4e` (radare2's m68k plugin cannot decode
ColdFire `mvs/mvz/byterev/mac`, which is most of this code). Markers as in
`CHIP.md`: ✅ read from the code, 🟡 inferred, ⬜ not found.

### 0. Headline

* `FUN_4003f1b4` is **not** the general morph. It is a special path for the
  three playback-position parameters (STRT/LEN/RATE) that must reach the voice
  task as a message. **The general morph runs every DSP frame inside the frame
  builder `FUN_4000c8a4` (`0x4000cc6c..0x4000cf3e`)**, on the DSP-bound copy of
  the parameter halfwords, never on the live parameter words.
* A scene block covers **page 1 of five pages only — 30 knobs per track**.
  Page 2 (slots 6..11) and the companion fields are unreachable, and the
  exclusion is structural (block size, buffer size, loop extents), not one
  `cmp`.

### 1. Scene block layout ✅

`base + pattern*0x18b2 + scene*0x100 + 0x8f3e2`, **8 tracks × 0x20 bytes**.
Scene byte *k* of a track is the lock for **DSP-frame halfword *k*** of that
track: the frame builder reads them 1:1 (`movew a2@+` → compute → `movew d3,a1@+`
at `0x4000ce60..0x4000ced4`). Frame halfwords are `knob<<8 | companion`
(ColdFire halfword → DSP 24-bit word `<<8`, `DSP.md` §6c).

| scene bytes | frame halfwords | page |
|---|---|---|
| 0..5 | page-block `0x80000510+ping·0x180+track·0x30`, hw 0..5 | PLAYBACK p1 (byte 1 = STRT, 2 = LEN, 3 = RATE ✅ from the STRT/LEN encoder hooks `0x4003eef0`/`0x4003ec7c` and `FUN_4003f1b4`) |
| 6..11 | same block, hw 6..11 | LFO p1: the LFO engine reads SPD *i* at word 6+i and DEP *i* at 9+i (✅ objdump, `LFO.md` §2) |
| 12..17 | voice record `0x80000110+ping·0x200+track·0x40`, hw 0..5 | AMP p1: PMTR 12–17 write there (✅ objdump, `LFO.md` §5) |
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

### 2. Morph arithmetic ✅

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

### 3. How the position gets there

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

### 4. Assessment for our slots

**None of BusVerb SHMR (6) / MODE (7) / GATE (10), BusDelay FRZE (11) /
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

The tempo cave (`modules/tempo-sync/tempo_cave.s`, hooked at `0x40004d40`,
`a2` = this track's record) publishes `0x460d16c8` + 1 at `+0x28` → `r6+$8`
every frame for the two servers; both the hardware fader and CC 48 feed
`0x460d16c8`. Nothing of ours reads it. Per-track fader values would have a
home in the weight table at `0x80003c60`, indexed per track.

Falsifiers: a hardware flash where the fader at the A end changes a page-1
lock the wrong way (would invert §2's endpoint claim); a `TPROBE`-style capture
showing `r6+$8` not tracking the fader (would mean the cave hook is not
per-frame for that track).
