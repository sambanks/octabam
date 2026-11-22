# The track recorders

OS 1.40C, ColdFire side: the recorder page's descriptor and storage, the
length arithmetic, the buffer pool, the write path and the loop point.
Read out of the binary by Bryan T over five Discord sessions and re-read here against our image the same week; the loop click
itself, fixed on hardware is `modules/recorder-loop-fix/README.md`. The
frame-phase model and its simulation are in git history
(`git show 3ceba41:docs/history/EXTERNAL_INGEST.md`).

## 1. Control path

| claim | read here |
|---|---|
| descriptor entry 8 `E = 0x400d3c74`, `INAB INCD RLEN TRIG SRC3 LOOP / FIN FOUT AB QREC QPL CD` | byte-identical |
| defaults `E+0x96` | `1 1 64 1 0 1 0 0 0 255 255 0` |
| min `E+0xa2` | `−1` for QREC/QPL only |
| count `E+0xd2` | `5 5 65 3 11 2 113 113 128 18 18 128` |
| formatter `E+0x11a` | `0x4003b18c` |
| QREC/QPL ladder `0x400d80e0` (`0xFFFFFFFF` sentinel before) | `1 2 3 4 6 8 12 16 24 32 48 64 96 128 192 256` |
| one-hot class table `0x400d8120` | `1 2 4 1024 8 2048 16 4096 32 8192 64 16384 128 32768 256 65536 512` |
| tempo chain `0x4000ca94..cabc`, publisher call `0x4000cac2` | `1814→181c`, `1818→1824`, `d1 = 0x80000000 ÷ [181c] → 1820`; `pea 0x60 / pea 0x80000c94 / dest 0x80000cf4 + page×96` |
| RLEN conversion `0x4006e3b2` | `mvsb 0x80000cf4(2,track)`, gate `≤ 63`, `(raw+1) × 63504000`, `remul` by `[0x80001814] << 2`, floor 64 |
| arm caller `0x40005ff0` | `[0x100b14cf] × 6322 + [0x46c82456] + track + 0x8eda2 == 4` gate; `a3 = 0x80000cf4 + 12·track + 96·page`; `L = table[a3@(7)]`; `addl d1,d1`; `macl d1, −[0x80001820]`; `(x+1)>>1` |
| step ladder `0x400ab63a` | `992250 × L`, 113 entries: `0, 1..32, 34..64 by 2, 68..128 by 4, 136..256 by 8, 272..512 by 16, 544..1024 by 32` |

Closed in the re-read here: `Dr == Dq` in `4c40/1801` is `DIVS.L` (gas encodes
`divs.l %d2,%d1` as `4c42 1801`; objdump prints `remsl`), so
`[0x80001820] = −2³¹/tempo24`. `[0x80001814]` = BPM × 24 (clamp 720..7200),
so recorder lengths are 44.1 kHz samples, RLEN raw+1 is sequencer steps
(`661500 / BPM` samples per 16th), the 64 floor is four frames, and
`992250 = 22.5 × 44100` gives `table[L] / tempo24 = L/16` steps. The
`0x400ab63a` ladder is the FIN/FOUT display series (`0, 0.063, 0.125 … 64`);
`0x40005ff0` nets to `round(table[FOUT] / tempo24)`. `MACSR = 0x20`
(`0x4000cf60` `moveq #32 / movel %d0,%macsr`; `0x4000d3ae` `movel
#32,%macsr`): fractional, signed, no saturation, truncating. Why the pickup
arm reads the FOUT slot is open.

Unconfirmed: Adopted: three storage tiers (bank `+0x8f382 + part×6322 + track×12`
via `[0x46c82456]`, SRAM `0x100a54d0 + …`, published `0x80000cf4 + track×12
+ page×96` refreshed per frame from `0x80000c94`); `FUN_40005178` is the
QREC scheduler (`0x800018be/de` staged, `0x46c7e9fa` immediate, comparator
`0x4000b308`, class mask `[0x46c7fe94]`); the engine queue `0x460d17ce` /
task loop `0x4008484e` / 46-entry jump table is `FUN_4008445c` (also RELOAD
BANK, types `0x14`, `6`); recorder buffers are object ids 128–135 in the
136-entry arena `0x100b14f0 + id×1096` (control records `0x46c922c4 +
id×44`), armed by opcode `0x25`, length floored at 64, LOOP at state
`+292`; the TRIG=ONE / SRC3=MAIN default fixup is not in the image.

## 2. Pool, write path, loop point bytes, reading

| claim | read here |
|---|---|
| pool cold init `0x40096f7a`: cursor `0x8000691c := 0`, count 14602 → `0x80006920`, block array `0x46c2e9c0`, index table `0x46c2e580` | byte-identical |
| block address `= blk×6144 + 0x40A955E0` (`lsll #13` − `lsll #11` at `0x400963b4`) | exact |
| recorder row `(track+2) × 14602` at `0x40095aa4` and `0x40006fc4` | exact |
| segment emission `0x40007298` | exact |
| lazy allocation `0x40007196–e2` (`tstb 0x80000052` = `DYNAMIC_RECORDERS`) | exact |
| pack loop `0x40007854`: 6 B per 24-bit stereo frame | exact |
| position advance `0x400072ba–be`; loop point `clrl %fp@(24)` at `0x4000703c`; ping-pong flip `0x40007032–36`; wrap test `0x40007004` | exact |
| 16-sample limit extension `0x40006e2a–4c` | exact; runs at arm time (inside the arm-calling converter, before `jsr arm` at `0x40006edc`), not per wrap |
| converter that feeds `arm()`, `0x40006dfc–10`: `#31752000 / mulsl / macl / movclrl / addql #1 / asrl #1` | exact |
| one `andil #-16` in the image, `0x40003646` | exact |
| settings keys `RECORD_24BIT`, `DYNAMIC_RECORDERS`, `RESERVED_RECORDER_COUNT/LENGTH`; metadata `BPMx24`, `LOOP_BARSx100`, `TSMODE`, `LOOPMODE` | `0x400b7d49–0x400b7d80`, `0x400b79fc–0x400b7a26` |
| `0x40A955E0` literal | 23 sites (22 the arena base; `0x400254f8` is the end of the 16 banks, `tools/remix/arena.py`) |
| per-frame dispatcher `0x4000d2a0–86`: 8 × { `0x400068e4(track, page e4, 0, nibble)`; if `word & 0xd0`: `0x40005ff0(track, word)`; `0x400068e4(track, page e0, nibble, 16)` } | exact |

Recorder buffers are chains of 6144-byte blocks from one pool of 14,602
at `0x40A955E0` (85.56 MiB, the Flex RAM figure; `PLACEMENT.md`), rows at
`0x46c2e9c0` (0–1 the free/sample map, 2–9 recorder tracks). The write
path is a read-modify-write in `0x400068e4` (unpack `0x400072f2`, EMAC mix
of four sources `0x40007680` → `0x800062cc`, pack `0x40007826`); the loop
point is a hard cut inside the frame (up to four segments per 16-sample
call). Length arithmetic, final form:

```
tempo24 = 24·bpm + (23·tenths + 4)/9                       0x4009c7c4 (tenths 0..9 → 0 3 5 8 10 13 15 18 20 23)
Q       = trunc(2³¹ / tempo24)                              0x4000cab8
L       = ( ((steps × 31,752,000) × Q >> 31) + 1 ) >> 1     0x40006dfc..e10
```

An exact x.5 quotient rounds down (128/16 → 82,687). The truncating
`0x4006e3b2`'s consumer is open.

**Reserve size (nordseele, emulator).** In an emulated
OS 1.40C project at default recorder settings, each of the eight recorder
buffers held 460 blocks of 0x1800 bytes: 2,826,240 bytes, 16.0 s of 16-bit
stereo at 44.1 kHz. The length and cap arrays are `0x461053a8` and
`0x461053e8` (14 and 6 literal references in the image). One
configuration in an emulator; no `RESERVED_RECORDER_LENGTH` setting (section 1's
keys) has been measured on hardware.

### 2a. The MEMORY page and RLEN MAX

CONTROL > MEMORY stores five bytes, written in key order by the page's
apply handler `0x40066466–0x400664ba` (mirrored to `0x100b14b1..b6`):

| byte | setting | key |
|---|---|---|
| `0x80000051` | LOAD 24BIT FLEX | `LOAD_24BIT_FLEX` |
| `0x80000052` | DYNAMIC RECORDERS | `DYNAMIC_RECORDERS` |
| `0x80000053` | RECORDER FORMAT | `RECORD_24BIT` |
| `0x80000054` | RESERVE RECORDINGS | `RESERVED_RECORDER_COUNT` |
| `0x80000056` (word) | RESERVE LENGTH, seconds | `RESERVED_RECORDER_LENGTH` |

Cap at a MAX arm (`0x400069b2`, code read): DYNAMIC set → (free pool
blocks + the recorder's own blocks) × samples per block from
`0x80003c20`; clear → tracks at or above RESERVE RECORDINGS get 0, the
rest RESERVE LENGTH × 44,100. A fixed RLEN takes the tempo converter
(`0x400069fc`) and no cap. A block draw that finds the pool empty
(`0x40007234`) calls `0x40005e48`, posts to the engine queue
`0x460d17ae` and leaves the write path — a stop, not a wrap (never
reached in the runs below).

Measured under the port (stock 1.40C, RECTRIG backup: DYNAMIC 1, 24-bit,
RESERVE 8 × 16 s; T1 FLEX, one REC1 + PLAY trig on step 1, 64 steps,
RLEN MAX, watches on `0x80004a3c` END, `0x46c7fe24` LIMIT, `0x80006920`
pool cursor, `0x461053a8/e8`):

| scale, BPM | length per pass (END at re-arm) | passes | blocks drawn | buffer after |
|---|---|---|---|---|
| 1/4X, 120.0 | 1,411,200 = 32.000 s = 16 bars, 88,200 frames | 3 identical | 689 | 1,379 |
| 1/8X, 120.0 | 2,822,400 = 64.000 s = 32 bars, 176,400 frames | 2 identical | 2,067 | 2,757 |
| 1/8X, 128.0 | 2,646,000 = 60.000 s = 32 bars, 165,375 frames | 2 identical | 1,894 | 2,584 |

- A MAX recording is the trig spacing on the track's own scale, to the
  sample; 1/8X is the slowest scale, so 64 steps at 1/8X (32 bars) is the
  longest one trig per pattern gives.
- With DYNAMIC on the cap array `0x461053e8[track]` reads 14,602 (the whole
  pool); the reserve is still allocated at load (460 blocks, then 690 once
  24-bit is applied, = 16.0 s either way). Draws start when the reserve
  fills (16.0 s into the first pass, `0x400071cc`, one block per 1,024
  24-bit frames); pool free 9,081 → 7,015 at 32 bars. The grown buffer is
  kept across re-arms: passes after the first draw nothing.
- LIMIT `0x46c7fe24[track]` is written 0 at the first MAX arm and the
  previous pass's length at each later one (`0x400069d6`).
- Not measured: DYNAMIC off (the RESERVE LENGTH cap), the pool-empty
  stop, and whether the grown buffer is released on a fixed RLEN or a
  project reload.

### 2b. RLEN PLEN

The fixed-length path, the sequencer's pattern length and scale, and the
module's measurements: `modules/rlen-plen/README.md`.

## 3. Recording length arithmetic

Bryan T's *Sound-on-Sound Looping with the Octatrack* (PDF) and
`octatrack_clickless_loops.xlsx` (his files, not in this repo) use the
firmware's arithmetic:
- length = RLEN × 15,876,000 / tempo24 (= `0x4006e3b2`'s `(raw+1) ×
  63,504,000 / (tempo24 << 2)`); clean ⇔ `MOD(8·RLEN·15,876,000,
  8·M·tempo24) = 0`. His 5,279 clean pairs, 60 golden tempos and 86
  bar-length tempos all reproduce here.
- The converter runs on the arm path (`0x40006dfc`, per frame; never at
  RLEN MAX).
- Displayed BPM ≠ actual (`.6` = 65 + 15/24).
- RLEN is measured against the master clock, with no per-track scale
  term.
- At MAX the recording ends at the next trig.
- ❓ "The filter introduces clicks at the loop point": open.
- Under the emulator (
  `git show 3ceba41:docs/history/RTOS_FORK.md` section 10.16): 128 BPM / RLEN 4
  writes 20,672 every pass with arm spacings 20,672 ×7 then 20,671; 128 /
  16 writes 82,687 with trigs at ⌊event⌋ (offsets 15, 15, 14, 14).
