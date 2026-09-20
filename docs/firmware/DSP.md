# DSP56300 side: load map, dispatch, parameters, memory

Addresses are ColdFire virtual addresses (`file_offset = vaddr −
0x40000400`) unless prefixed `P:` / `X:` / `Y:` (DSP word addresses).
Markers as in `CHIP.md`: ✅ measured / read from the listing, 🟡 inferred.
The build side of this (`DspSection`, ids, placement) is
`docs/remixer/MODULES.md` and `docs/remixer/PLACEMENT.md`.

## 1. Boot sequence ✅

`FUN_40001e50`, called from `0x4000050c`:

```asm
move.b #0,(0xfc0a400c)                       ; GPIO select (core A)
move.w #0x81,(0x20000000)                    ; HI08 ICR: INIT|RREQ
FUN_40001d4c(0x400e21e0, 0x96,  0x31000)     ; bootstrap A -> P:0x31000 (50 words, via the boot ROM)
                                             ; ~10,000-iteration delay loop
FUN_40001b18(0x400e2324)                     ; payload A (79,563 B)
move.b #1,(0xfc0a400c)                       ; GPIO select (core B)
move.w #0x81,(0x20000000)
FUN_40001d4c(0x400e2276, 0xae,  0x32000)     ; bootstrap B -> P:0x32000 (58 words)
FUN_40001b18(0x400f59ef)                     ; payload B (77,061 B)
move.l #0xfff0000,(0xfc00801c)               ; FlexBus / chip-select config
```

Retracted 8 Sep 2026: "`0x81` = DSP control: start" (the window is the
HI08 register file). The sequence runs in the ColdFire port against two
emulated cores and lands every byte (`COLDFIRE_PORT.md` O8). Payload B's
entry `P:0x38000` is written by payload A's upload: the shared window is one
memory for both cores, P/X/Y.

Two DSP cores, one payload each; payload A serves tracks 5–8, payload B
tracks 1–4 (✅ MrkVerb32 marker flash, 10 Aug 2026). Boot code at
`0x40000450` copies all four blobs from the image tail to `0x40a955e0`
(= `0x400e21e0 + 16 × 0x9b340`, the end of the 16 resident bank blobs)
before upload; after boot the DSP program exists only in the DSPs and at
that copy.

## 2. Payload format ✅

`FUN_40001b18(ptr)` walks 24-bit little-endian words (`b[0] | b[1]<<8 |
b[2]<<16`):

```
optional header word 3   (skip 6 bytes)
optional header word 4   (skip 6 bytes)
repeat:
    word  memory space   0 = P, 1 = X, 2 = Y;  > 3 terminates
    word  load address   (DSP word address)
    word  count          (24-bit words)
    count * 3 bytes of data
```

`tools/build/dsp_modmap.py` parses both field orders and keeps the one that
consumes the blob: A 98 records, 79,557 / 79,563 bytes; B 91 records,
77,055 / 77,061.

## 3. Load map ✅

Payload A: 98 modules, 26,221 words; X data `0x0020f`–`0x08d64`, Y data
`0x00200`–`0x00715`, P from `0x00000`:

```
P:0x00000     64 words     P:0x007d1    727 words
P:0x00040    544 words     P:0x00aa8    261 words
P:0x002bf    226 words     P:0x00bad    282 words
P:0x003a1    125 words     P:0x00cc7    157 words
P:0x0041e    429 words     P:0x00d96    289 words
P:0x005cb    282 words     P:0x00eb7    329 words
P:0x006f4    102 words     P:0x01000    594 words
P:0x00773     85 words     P:0x01252  1,063 words
                           P:0x01679  1,067 words
                           P:0x01b58    537 words
                           P:0x01d71    345 words
                           P:0x01eca    277 words
P:0x30000    171 words   <- payload A only (host-port loader + ESAI setup)
P:0x38000     19 words   <- payload A only
```

Payload B: 91 modules, P `0x00000`–~`0x00c77`, no `0x30000`/`0x38000`
records. The X/Y data blocks differ in address between payloads: curve bank
`X:0x438` in A, `X:0x42b` in B; Y tables shift by 16 (`TABLES.md`,
`EXTERNAL.md` §10). The 15 consecutive one-word P records (A
`P:0x006e5`–`0x006f3`, B `P:0x004a5`–`0x004b3`) are all zero: scratch, not
a dispatch table.

Internal P is contiguous with no gaps: A 66 modules, 8,159 words, top
`P:0x01fdf`; B 46 modules, 7,583 words, top `P:0x01d9f`. `P:0x2000` is
executable (CHORUS relocated there ran on the unit, `tools/build_dsptest.py`
in git history); upper bound unmeasured. No external memory; the shared
window runs at internal speed (`CHIP.md`).

Non-effect modules (payload A): `0x2bf` summing mixdown, `0x3a1` voice
playback engine (2-tap linear interpolator over a 128-word ring), `0x5cb`
flag handling off `r6+$1e`, `0x6f4` a small MAC helper, `func_00055a` the
24-bit ↔ dual-16-bit host packer (🟡 the first two and the packer from
`EXTERNAL.md`, 30 Aug 2026). The DSP self-modifies: frame setup writes
`move x0,p:>$58c` and `p:>$59b`.

## 4. Disassembly ✅

The vendored dsp56300 project (`vendor/dsp56300/build/source/disassemble/
dsp56kDisassemble`, built by `make setup`):

```sh
python3 tools/build/dsp_modmap.py                       # the module map
python3 tools/build/dsp_modmap.py --extract A 1252 out/dsp/A_P1252.bin
vendor/dsp56300/build/source/disassemble/dsp56kDisassemble -in out/dsp/A_P1252.bin -pc 1252 -le
python3 tools/build/dsp_disasm_all.py                   # every P module -> out/dsp/payload_{A,B}.asm
```

`-le` is required (bytes map onto the three 8-bit ports `0x20000014/18/1c`
as 23–16 / 15–8 / 7–0). `dsp_disasm_all.py`: A 68 modules / 6,817
instructions, B 46 / 6,251, zero undecodable.

## 5. The effect dispatch ✅

`P:0x0041e` holds the only dispatch: six `jsr (r2)` sites per payload.

```asm
0004a7: move    x:>$208,r6        ; r6 = per-instance parameter block
0004a9: move    #$6,n6            ; FX1 stride (FX2 uses #$c)
0004ac: move    x:(r6+$1b),b      ; FX1 effect id (FX2: +$1c)
0004ad: asr     #$8,b,b
0004b0: move    b,r1              ; r1 = effect id
0004b1: move    (r6)+n6           ; r6 += 6 -> FX1 params (FX2: += 12)
0004b4: move    x:(r1+$235),r2    ; PROCESS_TABLE[id]
0004be: jsr     (r2)              ; every frame
...
0004c9: cmp     x0,b              ; id changed since last frame?
0004cb: move    x:(r1+$215),r2    ; INIT_TABLE[id]
0004cd: jsr     (r2)              ; on change only
```

Two 32-entry pointer tables in X, indexed by the raw id, one load record
(`X:0x00215`, 64 words; image `0x400e2345` A / `0x400f5a10` B). Both
menus index the same tables (`CLAUDE.md`, "an FX2 id is also an FX1 id").
The FX1 dispatcher keeps the id in r1 across the init call (`P:0x4c8..0x4d7`);
an init that moves r1 sends the proc call through P:0 (`CLAUDE.md`,
`verify_initregs`).

| id | init | process | effect |
|---|---|---|---|
| `0x04` | `P:0x007d1` | `P:0x007dd` | FILTER |
| `0x05` | `P:0x00aa8` | `P:0x00ab2` | SPATIALIZER |
| `0x0c` | `P:0x00bad` | `P:0x00bb2` | EQUALIZER |
| `0x0d` | `P:0x01d71` | `P:0x01d7d` | DJ EQ |
| `0x10` | `P:0x00cc7` | `P:0x00cd8` | PHASER |
| `0x11` | `P:0x00d96` | `P:0x00da3` | FLANGER |
| `0x12` | `P:0x00eb7` | `P:0x00ed7` | CHORUS |
| `0x13` | `P:0x01eca` | `P:0x01edc` | COMB |
| `0x14` | `P:0x01000` | `P:0x01055` | PLATE REV |
| `0x15` | `P:0x01252` | `P:0x012be` | SPRING REV |
| `0x16` | `P:0x01679` | `P:0x0171b` | DARK REV |
| `0x18` | `P:0x01aa4` | `P:0x01ab1` | COMPRESSOR |
| `0x1c` | `P:0x01b58` | `P:0x01b75` | LO-FI |
| all 19 others (incl. `0x08` DELAY, `0x19` MULTIBCOMP) | `P:0x007c8` | `P:0x007c9` | null stub |

The null stub is a passthrough:

```asm
0007c8: rts                       ; init
0007c9: move r0,r1                ; process
0007ca: do   n7,>$7d0
0007cc: move x:(r0)+,a
0007cd: move x:(r0)+,b            ; two interleaved channels
0007ce: move a,x:(r1)+
0007cf: move b,x:(r1)+
0007d0: rts
```

MULTIBCOMP (`0x19`) is in neither manual list, labels copied from DJ EQ;
distinct from COMPRESSOR `0x18`.

### The stock DELAY

Runs on the ColdFire: per-frame DMA descriptor arithmetic over per-track
rings in SDRAM at `0x4F502C10` (10.8 MB, `0x477...` cached alias), EMAC loop
for gain and mix, frame routine `0x400031a0` consuming the post-FX2 read-back
block (§6c) and returning 512 words to core 0 at `X:0x4400` (🟡 adopted from
Bryan T, `EXTERNAL.md`; `docs/history/RTOS_FORK.md` §10.16.2). The DSP is
ruled out ✅: one dispatch, no `cmp` against id 8, per-track path FX1 → FX2 →
packer → `jmp int_00004a`, reachability from the tables/vectors/bootstraps
covers 95.8% (A) / 98.5% (B) of instructions with every unreached run ≤ 112
instructions, largest modulo buffer 128 words (`m6=$7f`), one firmware
section (`elektron-firmware-tool -i`: `id 3 MAIN OS, 1112560 B`). The
ColdFire's per-track "FX2 is DELAY" bitmask `0x460d1700` (built at
`0x400405ba`/`0x400452b8` from `Part+0x8ed88 == 8`) has seven users, all
UI (`0x40040xxx`–`0x40045xxx`, the DELAY CTRL trig-key mode; table
`0x400beb76`). The published id arrays `0x80000ec4/ecc` are write-only from
the CPU.

Hardware, id `0x08`'s dispatch substituted (`DELAYPROBE=stock|silence|send`,
stock DELAY restored to the chooser):

| id `0x08` runs | result |
|---|---|
| stock passthrough | delay works |
| a stub writing zeros | the whole track silent, dry included; other tracks fine; DELAY CTRL keys lit |
| the SEND client | delay works; the send taps pre-delay (the reverb receives dry) |

So the stock delay is downstream of the FX2 insert; nothing we can place
taps its output; a track can run the stock delay and feed a bus from the
same slot. The send client's levels on that id are DELAY's own `p0 TIME` /
`p1 FB` (its page: TIME 47, FB 0, VOL 127, BASE 0, WDTH 127, SEND 0 | X 0,
TAPE 1, DIR 127, SYNC 1, LOCK 0, PASS 0).

### Module records are not routine boundaries ✅

Records are laid down contiguously and code runs across seams. PHASER's
record is `0x00cc7`–`0x00d64` (157 words) and its control flow reaches
`0x00d89`: the four small modules `0x00d64/0x00d6a/0x00d70` (6 words) and
`0x00d76` (32), absent from both tables, are PHASER's unrolled biquad
cascade (no `rts`, last block `bra $7b0` into the 85-word shared module
`0x00773`–`0x007c8`). PHASER's extent is `0x00cc7`–`0x00d96`, 207 words.
Every other effect's max control-flow target is inside its record (FILTER
`0x00a3d`, SPAT `0x00baa`, EQ `0x00cc5`, FLANGER `0x00e9c`, COMP `0x01b55`,
LO-FI `0x01d6b`, DJ EQ `0x01ec7`, COMB `0x01fd4`). Match `do/rep/jmp/jsr/
bra/bsr/Jcc` operands only; `move #>$2000,x0` is an immediate. Disassemble a
neighbour before overwriting it.

### `X:0x30000` staging and aliasing ✅

Frame setup copies 72 words from `X:0x30000` to `y:0x1b8` and writes
parameter values back into `X:0x30000` (`P:0xa8..0xb6`). The allocator
also hands out `Y:0x30000` as an FX2 base. X, Y and P alias in the shared
window `0x30000`–`0x3FFFF` (`dsp/alias_probe.asm`, `CHIP.md`); `dsp_host`
keeps the spaces separate and cannot show aliasing.

## 6. Parameters ✅

Relative to `x:>$208`: FX1 params at `+6`, FX2 at `+12`, ids at `+0x1b`/
`+0x1c`. Inside a routine page-1 slot *i* is `x:(r6+i)`, positionally,
empty slots included (COMB `PTCH TUNE LP FB --- MIX` reads `00 01 02 03
05`; DJ EQ skips `01`; SPRING skips `01 02`; FLANGER reads nothing at
`0c+`). Values are `value << 16` (`and #>$7f0000`; `sub #>$400000` recentres
64). Each 16-bit halfword of the ColdFire's per-voice record is one DSP word
`<< 8`, which is why knobs sit at bits 16–23 and companions at 8–15 and the
low byte is never published.

| register | meaning |
|---|---|
| `r6` | this instance's parameter block |
| `r7` | per-instance state block, `x:0x20a + 0x100·k`; the dispatcher bumps it three times per track (`CLAUDE.md`, "the harness's model of the dispatcher is not the dispatcher") |
| `n7` | frame count (also `x:0x20c`; 0 skips the effect) |
| `r0` | audio block: the dispatcher passes `r0 = 0`, 16 interleaved L/R samples at `X:0`; stock code scratches `X:0x20–0xff` (`CLAUDE.md`, `dsp_host -audio 0`) |
| `r1` | effect id across the FX1 init call |

The stub's `r0` in / `r1` out is the stub's convention; DARK REV saves `r0`
to `x:(r7+$17)` and works from `#$a0` / `#>$110`.

### Page 2: `r6+$b..$e` ✅

Not `r6+6` and not display order. Measured with `dsp/pagemap_probe.asm`
and `dsp/page2_probe.asm` (git history), and the slot map in
`PARAM_PAGES.md` §6. The two instances of a track overlap: the FX2 block
starts six words after the FX1 block, so `r6_FX2+$6..$8` IS the FX1
effect's page 2 and `r6_FX2+$9..$b` the AMP page 2 (record halfwords
18-23). Retracted 15 Sep 2026: "`r6+$6..$a` are read by nothing on the
DSP" -- true of every FX2 effect, and the tempo cave that relied on it
overwrote the FX1 station's page 2 on every delay and reverb host
(`docs/remixer/FAILURE_MODES.md`).

| display slot | field |
|---|---|
| 6 | `r6+$c` bits 16–23 (also echoed in `$b`; an engine reading `$b` alone is silent on hardware) |
| 7 | `r6+$c` bits 8–15 |
| 8 | `r6+$d` bits 16–23 |
| 9 | `r6+$d` bits 8–15 |
| 10 | `r6+$e` bits 16–23 |
| 11 | `r6+$e` bits 8–15 |

Decode a companion with `and #>$7f00` then `asr #$8`. Every field takes a
full 0–127 knob (✅ tag 84: SHMR/MDEP on slot 7). Retracted: bits 0–7 for
companions (never worked on hardware); "a count-128 companion publishes
near-boolean" (the inherited formatter). DARK REV's labels: displayed `PRE`
drives `$e`, displayed `MIXF` drives `$c`; its algorithm reads its pre-delay
from `$c`. Page-class A (`0x40032814`) donors render one page-2 knob when
cloned (the class sources its layout from `0x46c7d244`): clone class B. A
probe comparing whole words against `64<<16` cannot see a companion field.
A generator that interpolates an offset as `$12` gets hex 18: format
`{x}`.

## 6c. Frames, tempo, read-back ✅

The transfer routine `0x40004860` is a 7-step state machine (`0x46104d3e`)
over eDMA channel 0 (TCD `0xFC045000`, DADDR the port `0x2000001c`, 16-byte
bursts, 4 minor loops); before each DMA it writes the DSP destination
(`0x6000 | X address`) and the halfword count to the port. Per ping
(`0x800000e0`/`e4`), per core (chip-select `0xFC0A400C`):

| ColdFire source | words | DSP dest | what |
|---|---|---|---|
| `0x800021d0` (A) / `0x80001c90` (B) + ping·`0xa80` | 336 | `X:0x080` | four 84-word per-track records |
| `0x80000110` / `0x80000210` + ping·`0x200` | 64 | `X:0x000` | four 16-word per-voice records |
| `0x80005460` + slot·`0x80` | 32 | `X:0x800` | a sample-slot record, on demand |
| `0x80003190` + ping·`0x400` | 256 | ← `X:0x4600` (A) / `X:0x2600` (B) | read-back: four per-track post-FX2 blocks (below); core 1's lands at `0x80003190`, core 0's at `+0x200`; the 512 words go back to core 0 every frame |
| `0x80005460..0x80005e60`, page-stepped | 128 | ← | the eight ESAI input slots × 16 samples (eDMA ch 7) |

Retracted: "`X:0x400`" for the read-back (never located; `X:0x415`–`0x41f`
are dispatcher variables). The 336-word block is built by the packer
`0x4000d3fc`–`0x4000d55e` from the machine-type handler table `0x400d61d0`
(rotated from `0x400d61f0`), record pointer `0x80001c80`; the DSP's 72-word
`X:0x30000` staging is that record after unpack.

Read-back: the dispatcher (`P:0x54`/`0x64`) loads `r5 = X:0x4600` (A) /
`X:0x2600` (B), saved at `X:0x206`; after each FX2 call (`P:0x50d`)
`P:0x50e`–`0x514` calls the copy at `P:0x55a` with `r0 = X:0x206`, source
`X:0`: 16 interleaved samples, each 24-bit sample stored as two words (`mpy`
by `0x8000` and `0x80`), 64 words per track, `add #>$40` at `P:0x52b`. Four
straight-line calls at `P:0x2df/0x2e2/0x2e6/0x2eb` fill the upper 256 words.
Payload B's sites are 0x20b lower (`P:0x303`, `0x309`, `0x34f`). 🟡 Whether
track LEVEL is applied before this point is unread.

ESAI: both cores configure it at boot (`P:0x30026` and the second port:
`M_TMOD=1`, `M_TDC=$7`, `M_TSMA=$ff`, TX and RX enabled, live `movep
a,x:<<M_TX0`). Retracted 30 Aug 2026: "audio does not arrive over the ESAI"
(inferred from dead ESAI vectors `0x30`–`0x3e`; a DMA-serviced peripheral
needs none). The live vectors `0x10`–`0x1c` are host-port handlers that
program DMA0 (`P:0x588..0x592`: destination from `M_HORX` into `M_DDR0`,
count into `M_DCO0`, `movep #>$8e82c0,x:<<M_DCR0`; `x:>$41f` ping-pong
selector at `P:0x5c1/0x5c4`).

Tempo: `0x80001814` = BPM × 24, clamped `0x2d0..0x1c20` at both writers
(`0x40005c4a`, `0x4004bc7e`), shadow `0x80000020`, latched per frame into
`0x8000181c`; sequencer phase increment `0x80001820 = −2³¹/tempo24`
(signed `divs.l` that objdump prints as `remsl`). Setter
`0x4009c7c4(bpm, tenths)`: `24·bpm + (23·tenths + 4)/9`, so tenths 0..9 →
`0 3 5 8 10 13 15 18 20 23`; `0x4009c5f4` displays it back; `0x4009c5b8`
returns the pattern's own word (`blob + pattern×0x8ed8 + 0x8e58`) when
`[0x80000024]` is set; `0x4004bc54` scales by `[0x46c7d328]/1000` (🟡 nudge,
clamp ≤ 1100). No code path copies tempo24 into a frame record: the
ColdFire ships rates. Consumers: the recorder's FIN/FOUT fade generator
`0x400074a0`/`0x40007502` (`tempo24 << 18` × `table[FIN]`/`table[FOUT]`
from `a4@(6)`/`a4@(7)`, `0x400ab83a` = `ceil(1134693784 / n)`, entry 0
`0xFFFFFFFF`; ❌ until 21 Sep 2026 this read "LFO speed" and "MULT table"
— the LFOs are `LFO.md`, their rate is `SPD × tempo24 × 4` and MULT is a
shift); `0x40006d48`
reads the phase increment into per-voice records; `0x40004bd2` advances a
playback position by `tempo24 << 4` per frame when byte `+0x2b` of the
per-voice record is set, else `0xb40`; UI `0x40031d70` (bars) and
`0x4002f7ec` (`%ds`); recorder `0x4006e3b2` (`(raw+1) × 63504000 /
(4·tempo24)`) and `0x40006dfc` (rounds; the one that reaches `arm()`).
Retracted 2 Sep 2026: `0x400060c4` as a tempo→frame site (it is the
PICKUP recorder arm length, `EXTERNAL.md` §6).

The tempo reaches the DSP from stock: the per-frame voice-record writer
stores tempo24 (`0x8000181c`, BPM*24) into halfword 31 of every track's
record (`0x40004d6a`, `move.w %a0,0x3e(%a2)`), `r6+$13` of the FX2
instance; BusDelay derives `42,336,000 / tempo24` (samples per MIDI clock,
Q12.4) per block with a 24-step `div`. The note cave
(`modules/tempo-sync/tempo_cave.s`) hooks `0x40004d40` in the same writer
(replaces `move.b 0xdbc(a0),d2 / ext.w d2 / move.w d2,0x38(a2)` with `jsr`
+ two `nop`s, replays them) and for FX2 id 6 stores the held MIDI note
into the low byte of halfword 13 (`r6+$1` bits 8-15); `MIDI.md`. Until
15 Sep 2026 the cave stored tempo24 and the period at `+0x24/+0x26`
(`r6+$6/$7`): the FX1 instance's page 2. The cave floats past the
descriptor clones (`0x400d7000` in the shipping image). An init that built a
division table in Y through `(r1)+` killed every voice on three flashes
(R48–R50, 24 Aug 2026); `m1` is not guaranteed linear at init; replaced by
an immediate `cmp`/`tge` chain. The panel's `time_fmt.s` formatter prints
the division (`PARAM_PAGES.md` §7); the DSP-side snap rule is in
`modules/busdelay/README.md`.

## 7. Memory ✅

Effect code sizes (words): DARK 1,067, SPRING 1,063, FILTER 727, PLATE 594,
LO-FI 537, DJ EQ 345, CHORUS 329, FLANGER 289, EQ 282, COMB 277, SPAT 261,
PHASER 207, COMP 180. `do` loops per process routine: SPRING 26, DARK 22,
PLATE 21, FILTER 12, PHASER 12, LO-FI 11, COMB 9, COMP 8. Two stock reverbs
at once glitch (`PARAM_PAGES.md` §5e); the cycle budget is in `CHIP.md`.

X: `0x01d9f–0x0483f` (10,913 words) delay region for PLATE/DARK;
`0x05840–0x06bff` per-instance state (`x:0x20a` = `0x6000`); `0x07a92–0x0857f`
2,798 words; `0x08d98–0x0ffff` 29,288 words unreferenced. `X:0x4000`,
`0xc000`, `0xf000` respond on hardware (single-word probes), but 1024-word
walking-value blocks at `0x0C000` and `0x0F000` (`dsp/xmem_probe.asm`,
validated in `dsp_host` first) fail: high X is not usable memory. The
stock reverbs compute buffer addresses at runtime (DARK's lengths from the
table at `X:0x8cfb`: `28 36 58 82 126 190 250 408 646 922 1376 2047 608 896
1292 2047`; longest line 2,047 words); DARK's delay memory ≈ 7,600 words.
An effect's memory ceiling is its allocation: 16,384 words per FX2 slot as
pooled, 65,536 shared-window words per server since the XBUS split.

Y, measured end to end (`dsp/ymemprobe.asm`, wet-only echo, `base = (p0+1)
<< 10` then `<< 12`):

| Y range | what |
|---|---|
| `0x00000–0x00794` (A) / `0x007a4` (B) | system + loaded modules; B loads 21 modules below `0x1000`, A 5 |
| `0x00795–0x00FFF` | free (`0x07a5+` in B): absolute scratch must sit at `0x800` or above |
| `0x01000–0x03FFF` | 4 FX1 slots × 3072 |
| `0x04000–0x0BFFF` | 2 FX2 slots × 16384 |
| `0x0C000–0x2FFFF` | absent (silence) |
| `0x30000–0x3FFFF` | 64K words shared window, 4 more FX2 slots; `0x30000` exactly buzzed on the probe |
| `0x40000+` | absent (freezes) |

Allocator: `X:0x20a` (state block, `+= 0x100` per effect) and `X:0x213`
(pointer into the base table, `+= 1`), both initialised in `P:0x002bf`,
advanced in `P:0x0041e` before process is called. Base table `X:0x255`
(8 words): `0x01000 0x04000 0x01c00 0x08000 0x02800 0x30000 0x03400
0x34000`, interleaved FX1/FX2 (FX1 stride `0xc00`, FX2 `0x4000`). Payload B
takes `0x38000`/`0x3c000` for its shared-window slots. FX2 instance *k* =
table entry `1 + 2k`, `r7 = 0x6000 + (2 + 2k)·0x100`:

| | entry | base A | base B | r7 |
|---|---|---|---|---|
| bank track 1 FX2 | 1 | `0x04000` | `0x04000` | `0x6200` |
| bank track 2 FX2 | 3 | `0x08000` | `0x08000` | `0x6400` |
| bank track 3 FX2 | 5 | `0x30000` | `0x38000` | `0x6600` |
| bank track 4 FX2 | 7 | `0x34000` | `0x3c000` | `0x6800` |

Read the base in init (`move x:>$213,r4 / move x:(r4),x0`) and carry it to
process; in process the pointer is another instance's (one effect works by
luck, two share an entry and one writes 14K words through memory it does
not own). `base = x:(0x255 + ((r7 − 0x6000) >> 8))` is wrong (r7 `0x6200`
pairs with entry 1, not 2). `r7+$84..$8a` do not persist across calls
(hangs; DARK's init steps around `$85..$8a`); `r7+$83` and `r7+$71..$78`
do. A per-instance stash at `Y:(0x735 + (r7 >> 8))` works on payload A and
lands inside a live coefficient table on payload B. `dsp_host -inst N
-guard` names a write over a loaded module. Bring-up hangs (three
attempts, cause not isolated): executing at `P:0x2000` with low X as delay
memory (🟡 P/X alias), a `do` loop-end assembled at the wrong org, a
hardcoded entry offset.

## 8. Standing rules

Each established on hardware:

- `mpy` does not double when `a1` is read (0.5·0.5 = `$200000`); `a0`
  exposes the shift (`CLAUDE.md`).
- Let the AGU do address work; hand-rolled modulo cost 135 cycles/sample.
- `dsp_asm` mis-encodes illegal parallel moves silently: `x:(rN+disp)` is
  never parallel; `mpy y0,x0,a` takes a parallel move, `mpy x0,y0,a`
  discards it; XY dual moves need the X pointer in R0–R3 and Y in R4–R7.
  Disassemble what you assemble.
- Two data moves between writing an address register and using it, never
  an M-register write there; no M-register write inside the sample loop.
- A modulo offset larger than the buffer is undefined: silent, not an
  error.
- Absolute Y scratch at `0x800` or above; `X:0x213` valid in init only.
- When a register holding a constant is repurposed, grep every read.
- Check the assembler's exit status, not the generator's; `| grep` masks a
  failed assemble.
- With an impulse input, a flat RMS envelope is instability, not a long
  tail.
- A harness special case is not the dispatcher; measure dispatcher facts
  under the port (`ot_emu --dsp-pcwatch`).
