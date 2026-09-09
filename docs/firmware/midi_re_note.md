# MIDI input path in OS 1.40C (ColdFire) — RE note, 24 Aug 2026

Tooling: `m68k-elf-objdump -D -b binary -m m68k:cfv4e --adjust-vma=0x40000400
out/raw/section_3_MAIN_OS.bin` (radare2's m68k plugin does not decode the
ColdFire `mvs/mvz/mov3q/mac` forms; objdump does). Every address below is
read from that listing. **M** = measured (instruction sequence quoted or
table read from the image), **I** = inferred.

## 1. Byte parser and dispatch

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

## 2. Note-on for audio tracks (`0x4000e018`)

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

## 3. Per-frame readable state (for a cave)

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

## 4. Record halfwords +0x24..+0x38 — a correction

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
