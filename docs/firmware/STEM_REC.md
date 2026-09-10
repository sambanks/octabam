# The stock facts STEM REC stands on

Every address, argument and behaviour the STEM REC module
(`modules/stems/`, design in `docs/superpowers/specs/2026-09-10-stem-rec-poc-design.md`)
relies on, with the evidence for each.

**Method.** Read from `out/raw/section_3_MAIN_OS.bin`, SHA-256
`164f31224bf61181e3f50e7dec40df9afcae5b16dbf6e4c0d0cc5e986af0a84e`, load base
`0x40000400`, with `scripts/disasm.sh emac` (objdump `-m m68k:cfv4e`), never r2.
Confidence markers as in `CHIP.md`: ✅ measured, 🟡 inferred with a
falsifier stated, ❌ retracted.

## 1. The transport word

### 1.0 The plan's rule does not hold. Read this first.

The STEM REC plan assumes `tst.l TRANSPORT` with zero meaning stopped. That
rule is **wrong**, and a hook built on it never sees the stop edge.

`0x800065b8` is a longword with **three** states, not two:

| value | meaning | written by |
|---|---|---|
| `0` | stopped and rewound. Also the state at engine init. | seven `clrl` sites |
| `1` | running | five sites |
| `2` | stopped by the STOP key, position kept | one site, `0x4009f5c6` |

The STOP key's own path writes **2**, never 0. The rule that does hold is
**running if and only if the word is 1**. Both edges the per-frame hook needs
are therefore transitions in and out of the value 1, not in and out of zero.
Section 1.7 gives the corrected interface. Task 14's hook must be revised
before it is written.

### 1.1 Size ✅

Every one of the 33 references in the image is a longword form: `movel`,
`clrl`, `tstl`, `cmpl` or `orl`. There is no byte or word access to
`0x800065b8` anywhere in the image.

This confirms the warning already in `tools/emu/emu_rtos.py` and
`RTOS_FORK.md` §10.1: reading this address one byte at a time reports a flat
0 no matter what the firmware does, because the value lands in `0x800065bb`.

### 1.2 Every reference, classified ✅

`refs.sh 0x800065b8` returns 33 hits. Each hit is an instruction operand.
Each was decoded from five different earlier start addresses (the hit minus
`0x50`, `0x40`, `0x30`, `0x24` and `0x1c`); all five agree at all 33 sites,
so no boundary here is in doubt.

The hit column is the operand address that `refs.sh` prints. The instruction
column is where the instruction that uses it begins, two bytes earlier in
every case.

| hit | instruction | bytes | mnemonic | class |
|---|---|---|---|---|
| `0x40005092` | `0x40005090` | `b2b9 8000 65b8` | `cmpl 0x800065b8,%d1` | read, against 1 |
| `0x400050a6` | `0x400050a4` | `b0b9 8000 65b8` | `cmpl 0x800065b8,%d0` | read, against 1 |
| `0x40005192` | `0x40005190` | `b0b9 8000 65b8` | `cmpl 0x800065b8,%d0` | read, against 1 |
| `0x400052cc` | `0x400052ca` | `b2b9 8000 65b8` | `cmpl 0x800065b8,%d1` | read, against 1 |
| `0x4000a16c` | `0x4000a16a` | `4ab9 8000 65b8` | `tstl 0x800065b8` | read |
| `0x4000a36e` | `0x4000a36c` | `b4b9 8000 65b8` | `cmpl 0x800065b8,%d2` | read, against 1 |
| `0x4005205e` | `0x4005205c` | `4ab9 8000 65b8` | `tstl 0x800065b8` | read |
| `0x4009b288` | `0x4009b286` | `80b9 8000 65b8` | `orl 0x800065b8,%d0` | read, see below |
| `0x4009b298` | `0x4009b296` | `2039 8000 65b8` | `movel 0x800065b8,%d0` | read, the getter |
| `0x4009b64e` | `0x4009b64c` | `beb9 8000 65b8` | `cmpl 0x800065b8,%d7` | read, against 1 |
| `0x4009b9cc` | `0x4009b9ca` | `2039 8000 65b8` | `movel 0x800065b8,%d0` | read, the state switch |
| `0x4009baf2` | `0x4009baf0` | `42b9 8000 65b8` | `clrl 0x800065b8` | **write 0** |
| `0x4009bbcc` | `0x4009bbca` | `42b9 8000 65b8` | `clrl 0x800065b8` | **write 0** |
| `0x4009c3d6` | `0x4009c3d4` | `23c0 8000 65b8` | `movel %d0,0x800065b8` | **write 1** |
| `0x4009c3f4` | `0x4009c3f2` | `42b9 8000 65b8` | `clrl 0x800065b8` | **write 0** |
| `0x4009c4d6` | `0x4009c4d4` | `23c0 8000 65b8` | `movel %d0,0x800065b8` | **write 1** |
| `0x4009c51a` | `0x4009c518` | `b2b9 8000 65b8` | `cmpl 0x800065b8,%d1` | read, against 2 |
| `0x4009f476` | `0x4009f474` | `b2b9 8000 65b8` | `cmpl 0x800065b8,%d1` | read, against 1 |
| `0x4009f5c8` | `0x4009f5c6` | `23c0 8000 65b8` | `movel %d0,0x800065b8` | **write 2** |
| `0x400a0194` | `0x400a0192` | `b0b9 8000 65b8` | `cmpl 0x800065b8,%d0` | read, against 1 |
| `0x400a0372` | `0x400a0370` | `b0b9 8000 65b8` | `cmpl 0x800065b8,%d0` | read, against 1 |
| `0x400a05ac` | `0x400a05aa` | `b0b9 8000 65b8` | `cmpl 0x800065b8,%d0` | read, against 1 |
| `0x400a1052` | `0x400a1050` | `42b9 8000 65b8` | `clrl 0x800065b8` | **write 0** |
| `0x400a10d2` | `0x400a10d0` | `4ab9 8000 65b8` | `tstl 0x800065b8` | read |
| `0x400a11a8` | `0x400a11a6` | `42b9 8000 65b8` | `clrl 0x800065b8` | **write 0** |
| `0x400a12ae` | `0x400a12ac` | `42b9 8000 65b8` | `clrl 0x800065b8` | **write 0** |
| `0x400a1f2e` | `0x400a1f2c` | `b4b9 8000 65b8` | `cmpl 0x800065b8,%d2` | read, against 1 |
| `0x400a220c` | `0x400a220a` | `23c1 8000 65b8` | `movel %d1,0x800065b8` | **write 1** |
| `0x400a24d2` | `0x400a24d0` | `23c1 8000 65b8` | `movel %d1,0x800065b8` | **write 1** |
| `0x400a27e4` | `0x400a27e2` | `23c5 8000 65b8` | `movel %d5,0x800065b8` | **write 1** |
| `0x400a3f98` | `0x400a3f96` | `b0b9 8000 65b8` | `cmpl 0x800065b8,%d0` | read, against 1 |
| `0x400a4068` | `0x400a4066` | `42b9 8000 65b8` | `clrl 0x800065b8` | **write 0** |
| `0x400a4e14` | `0x400a4e12` | `b8b9 8000 65b8` | `cmpl 0x800065b8,%d4` | read, against 1 |

Totals: 20 reads, 7 writes of 0, 5 writes of 1, 1 write of 2.

#### Is that census complete? Mostly ✅, with one gap 🟡

`refs.sh` matches 32-bit literals. It cannot see a store formed as
`lea <base>,%aN` plus a displacement, so "every writer" needs its own
evidence. Four checks, all against the image:

**1. No pointer to the word itself.** No `lea 0x800065b8` and no
`movea.l #0x800065b8` appears anywhere. ✅

**2. No misaligned store from below overlaps it.** The bytes immediately
under the word are accessed at widths that stop at `0x800065b7`:

```
4009be96:	33c0 8000 65b2 	movew %d0,0x800065b2
4009be8e:	33c0 8000 65b4 	movew %d0,0x800065b4
4009bebe:	13c1 8000 65b6 	moveb %d1,0x800065b6
```

Counted two ways that agree: a 32-bit literal scan of the whole image (the
`refs.sh` algorithm) and a `grep` over the linear disassembly for every
instruction naming the address.

| address | references | breakdown | widest access |
|---|---|---|---|
| `0x800065b2` | 17 | 1 `lea`, 8 word writes, 8 word reads | word |
| `0x800065b4` | 6 | 5 word writes, 1 word read | word |
| `0x800065b6` | 15 | 10 byte writes, 2 byte reads, 3 `tstb` | byte |
| `0x800065b7` | 0 | nothing at all | none |

Each count is the number of instructions in the image that name that address
as an absolute operand, reads and writes together, not writes alone. The
widest access at `0x800065b2` is a word, so it ends at `0x800065b3`; at
`0x800065b4` a word, ending at `0x800065b5`; at `0x800065b6` a byte, ending
there. `0x800065b7` is never touched. Nothing below reaches into
`0x800065b8`. ✅

(The `lea` at `0x800065b2` is the one site check 3 resolves. It is counted
here as a reference but it is not an access.)

**3. Every absolute base near the word, checked.** Enumerating every
`lea`/`movea.l` of a literal in `0x80006400` to `0x800065b8` gives 15
distinct bases across 56 sites. The nearest one below the word, and the only
one within longword reach of it, is `lea 0x800065b2,%a0` at `0x400a4226`. It
is used once:

```
400a4226:	41f9 8000 65b2 	lea 0x800065b2,%a0
400a422c:	33d0 8000 65b4 	movew %a0@,0x800065b4
400a4232:	3039 8000 65b2 	movew 0x800065b2,%d0
```

`%a0` is loaded, read once at displacement 0, never incremented, and next
reloaded with an unrelated base (`lea 0x400abae4,%a0` at `0x400a4264`). The
code reverts to absolute addressing immediately. It never reaches
`0x800065b8`. ✅

**4. No pointer walk crosses it.** No `cmpal` loop terminator anywhere in
the image falls in `0x80006510` to `0x800065c0`, so no walk in this
neighbourhood runs up to or past the word. The two walks nearby both miss
it: the per-track array walks stop at `0x80006510`, which is `0xa8` below,
and the eight-entry walk over `0x80006646` to `0x8000664e` (writing
`%a0@(-8)` and `%a0@`) sits `0x8e` above. ✅

🟡 **What remains unseen.** A store through a base register whose value is
computed at run time rather than loaded from a literal, for example a struct
pointer read out of memory, would be invisible to all four checks. So would
a base outside the `0x80006400` to `0x800065b8` range that reaches the word
by a large displacement.
**Falsifier:** a write watch over `0x800065b8,4` under the port reporting a
store from a PC that is not one of the 13 writers listed above.

Two reads deserve names, because later tasks will meet them.

`0x4009b270` is a predicate, "is anything active". It ORs the 16 per-track
bytes at `0x80006500` together and then ORs the transport word in:

```
4009b270:	41f9 8000 6500 	lea 0x80006500,%a0
4009b276:	4281           	clrl %d1
4009b278:	7198           	mvzb %a0@+,%d0
4009b27a:	8280           	orl %d0,%d1
4009b27c:	b1fc 8000 6510 	cmpal #-2147457776,%a0
4009b282:	66f4           	bnes 0x4009b278
4009b284:	2001           	movel %d1,%d0
4009b286:	80b9 8000 65b8 	orl 0x800065b8,%d0
4009b28c:	4e75           	rts
```

`0x4009b290` is the getter. With a negative argument it returns the transport
word; otherwise it returns the per-track byte `0x80006500[arg & 15]`. The
transport dispatchers call it as `getter(-1)` and compare the result with 1:

```
4009b290:	202f 0004      	movel %sp@(4),%d0
4009b294:	6c08           	bges 0x4009b29e
4009b296:	2039 8000 65b8 	movel 0x800065b8,%d0
4009b29c:	4e75           	rts
```

### 1.3 The writers ✅

**Write 1, the transport starts.** Five sites. Two are inside `0x4009b964`,
the routine `emu_rtos.py` calls `FW_TRANSPORT`:

```
4009c3d2:	7001           	moveq #1,%d0
4009c3d4:	23c0 8000 65b8 	movel %d0,0x800065b8
```

```
4009c4d2:	7001           	moveq #1,%d0
4009c4d4:	23c0 8000 65b8 	movel %d0,0x800065b8
```

`0x4009c3d4` is its cold start branch and `0x4009c4d4` its resume branch.

The other three all sit inside one very large routine, the sequencer's timer
interrupt handler. Its entry is `0x400a1e0c`, registered on vector `0x60` at
`0x400a1094`:

```
400a1e0c:	46fc 2700      	movew #9984,%sr
400a1e10:	4fef ff30      	lea %sp@(-208),%sp
400a1e14:	48d7 7fff      	moveml %d0-%fp,%sp@
400a1e18:	70fe           	moveq #-2,%d0
400a1e1a:	c1b9 fc04 8010 	andl %d0,0xfc048010
```

There is no `rts` between that entry and `0x400a4070`, so everything below
belongs to it. The three stores are:

```
400a2208:	7201           	moveq #1,%d1
400a220a:	23c1 8000 65b8 	movel %d1,0x800065b8
400a2210:	41f9 4610 757c 	lea 0x4610757c,%a0
400a2216:	23d0 46c7 75ce 	movel %a0@,0x46c775ce
400a221c:	4a39 8000 002a 	tstb 0x8000002a
400a2222:	670c           	beqs 0x400a2230
400a2224:	4878 00fa      	pea 0xfa
400a2228:	4eb9 4001 08b0 	jsr 0x400108b0
```

```
400a24ce:	7201           	moveq #1,%d1
400a24d0:	23c1 8000 65b8 	movel %d1,0x800065b8
```

```
400a27e0:	7a01           	moveq #1,%d5
400a27e2:	23c5 8000 65b8 	movel %d5,0x800065b8
```

The handler tests the transport word against 1 at `0x400a1f2c`, and it
transmits `0xfa` (MIDI Start) at `0x400a2224` and `0x400a28c2`, and `0xfb`
(MIDI Continue) at `0x400a1f52`. Only the first pairing is straight-line and
therefore certain: `0x400a220a` falls through to the `0xfa` at `0x400a2224`,
as the listing above shows.

🟡 Which transmission belongs with `0x400a24d0` and with `0x400a27e2` was
not traced through the handler's branches.
**Falsifier:** a trace through `0x400a1e0c` showing either store reaching a
different transmission, or none. This does not affect the interface, because
all three store the same value.

The store at `0x4009c3d4` is the one the port has already caught.
`RTOS_FORK.md` §9.4 and §10.1 record `[0x800065b8] <- 0x1 (4)` at pc
`0x4009c3d4` in task main, measured 6 Sep 2026 against `out/_testproj`. That
is an independent confirmation of both the size (4 bytes) and the running
value (1) at one of the five sites listed here. ✅

**Write 2, the STOP key.** One site, at the head of `0x4009f5bc`:

```
4009f5bc:	4fef ffe0      	lea %sp@(-32),%sp
4009f5c0:	48d7 3c3c      	moveml %d2-%d5/%a2-%a5,%sp@
4009f5c4:	7002           	moveq #2,%d0
4009f5c6:	23c0 8000 65b8 	movel %d0,0x800065b8
4009f5cc:	7202           	moveq #2,%d1
4009f5ce:	13c1 8000 6510 	moveb %d1,0x80006510
```

That routine transmits MIDI Stop before it returns:

```
4009f6e4:	4a39 8000 002a 	tstb 0x8000002a
4009f6ea:	670c           	beqs 0x4009f6f8
4009f6ec:	4878 00fc      	pea 0xfc
4009f6f0:	4eb9 4001 08b0 	jsr 0x400108b0
```

`0xfc` is MIDI System Real Time Stop. Section 1.5 follows the key path into
it.

**Write 0, seven sites.** Three are abort paths inside `FW_TRANSPORT`
(`0x4009baf0`, `0x4009bbca`, `0x4009c3f2`). All three share one idiom: clear
the 16 per-track bytes, clear the transport word, then clear `0x80006510`.

```
4009c3e8:	4218           	clrb %a0@+
4009c3ea:	b1fc 8000 6510 	cmpal #-2147457776,%a0
4009c3f0:	66f6           	bnes 0x4009c3e8
4009c3f2:	42b9 8000 65b8 	clrl 0x800065b8
4009c3f8:	4210           	clrb %a0@
```

`0x400a1050` is the sequencer engine's init entry. It clears the transport
word first, then `0x80006546`, `0x8000654a` and `0x8000654e`, sets
`0x800065bc` to `-1`, and ends by setting the `0x46c77bf6` flag that
`FW_TRANSPORT` tests before it will do anything. This is why the word reads 0
from boot.

`0x400a11a6` and `0x400a12ac` are both inside `0x400a10c8`, the stop and
rewind primitive:

```
400a10c8:	4fef ffdc      	lea %sp@(-36),%sp
400a10cc:	48d7 7c3c      	moveml %d2-%d5/%a2-%fp,%sp@
400a10d0:	4ab9 8000 65b8 	tstl 0x800065b8
400a10d6:	6600 00ce      	bnew 0x400a11a6
```

```
400a11a6:	42b9 8000 65b8 	clrl 0x800065b8
400a11ac:	41fa fe82      	lea %pc@(0x400a1030),%a0
```

```
400a12a2:	4218           	clrb %a0@+
400a12a4:	b1fc 8000 6510 	cmpal #-2147457776,%a0
400a12aa:	66f6           	bnes 0x400a12a2
400a12ac:	42b9 8000 65b8 	clrl 0x800065b8
400a12b2:	4210           	clrb %a0@
```

The two clears are on different branches, and the routine reaches at least
one of them either way. Here is the whole control flow of
`0x400a10c8` through `0x400a12b4`, every branch it contains:

```
400a10d0:	4ab9 8000 65b8 	tstl 0x800065b8
400a10d6:	6600 00ce      	bnew 0x400a11a6
400a10e0:	6766           	beqs 0x400a1148
400a111a:	66f4           	bnes 0x400a1110
400a1138:	6608           	bnes 0x400a1142
400a1144:	6000 0150      	braw 0x400a1296
400a114e:	6748           	beqs 0x400a1198
400a11a2:	6000 00f2      	braw 0x400a1296
400a11a6:	42b9 8000 65b8 	clrl 0x800065b8
400a11b6:	6700 00a8      	beqw 0x400a1260
400a122e:	6710           	beqs 0x400a1240
400a123e:	6010           	bras 0x400a1250
400a1256:	6d1c           	blts 0x400a1274
400a125e:	6014           	bras 0x400a1274
400a12aa:	66f6           	bnes 0x400a12a2
400a12ac:	42b9 8000 65b8 	clrl 0x800065b8
```

Reading it: the zero branch falls through from `0x400a10d0` and leaves by
one of the two `braw 0x400a1296` at `0x400a1144` and `0x400a11a2`, so it
clears once, at `0x400a12ac`. The non-zero branch is sent to `0x400a11a6`,
clears there, and then every one of its own exits (`0x400a11b6` to
`0x400a1260`, and `0x400a1256` and `0x400a125e` to `0x400a1274`) runs on
into `0x400a1296` by fall-through, so it clears a second time at
`0x400a12ac`. There is no `rts` in the whole span.

So the routine always leaves the word at 0, by one clear on the zero branch
and two on the non-zero branch. ✅

It also transmits MIDI Stop, at `0x400a1426`. That site is inside
`0x400a10c8`: the routine's only `rts` is at `0x400a14a0`, after the
matching `moveml %sp@,%d2-%d5/%a2-%fp` at `0x400a1498`, and there is no
other return between `0x400a10c8` and it.

`0x400a4066` is an automatic stop, inside the same timer interrupt handler
at `0x400a1e0c` that holds three of the write-1 sites. Its test at
`0x400a3f96` compares the word against 1 and leaves if it is anything else.
It transmits MIDI Stop at `0x400a4022`, `0x44` bytes earlier, and then
clears:

```
400a4022:	4878 00fc      	pea 0xfc
400a4026:	4eb9 4001 08b0 	jsr 0x400108b0
...
400a4066:	42b9 8000 65b8 	clrl 0x800065b8
400a406c:	4210           	clrb %a0@
```

### 1.4 What the three values mean ✅

`FW_TRANSPORT` switches on the word at its head. This is the clearest
statement of the state machine in the image:

```
4009b9ca:	2039 8000 65b8 	movel 0x800065b8,%d0
4009b9d0:	7201           	moveq #1,%d1
4009b9d2:	b280           	cmpl %d0,%d1
4009b9d4:	6700 0a62      	beqw 0x4009c438
4009b9d8:	7402           	moveq #2,%d2
4009b9da:	b480           	cmpl %d0,%d2
4009b9dc:	660a           	bnes 0x4009b9e8
4009b9de:	4a39 8000 668b 	tstb 0x8000668b
4009b9e4:	6700 0a52      	beqw 0x4009c438
```

Value 1 and value 2 both take the `0x4009c438` branch. Value 0 falls through
to the long branch. The two branches differ in exactly the way MIDI
distinguishes Start from Continue:

- The `0x4009c438` branch, entered from 1 or 2, transmits `0xfb` (Continue)
  at `0x4009c450`, converts every per-track byte that reads 2 back to 1
  (`0x4009c4aa`, `0x4009c4ba`), and writes 1 at `0x4009c4d4`.
- The fall-through branch, entered from 0, transmits `0xfa` (Start) at
  `0x4009c160` unless the arranger words `0x800066cc` and `0x800066d4` say
  otherwise, and writes 1 at `0x4009c3d4`.

So value 0 means "at the top of the sequence", value 1 means "running", and
value 2 means "stopped, with the position kept, so the next start is a
Continue". The per-track byte array at `0x80006500` carries the same 0, 1
and 2 encoding for each of the 16 lanes.

### 1.5 The stop edge ✅, with the key's identity 🟡

The per-key jump table is at `0x400d2d54`, holding 4-byte handler pointers.
The three transport keys are consecutive:

| index | address | entry | key |
|---|---|---|---|
| 27 | `0x400d2dc0` | `0x4000a274` | REC |
| 28 | `0x400d2dc4` | `0x4000a200` | PLAY |
| 29 | `0x400d2dc8` | `0x4000a1e0` | STOP |

❌ **Correction to two existing notes.** The task brief and the comment by
`UI_QUEUE` in `tools/emu/emu_rtos.py` both put REC, PLAY and STOP at indices
24, 25 and 26. They are at 27, 28 and 29. Index 26 is `0x400d2dbc`, and it
holds `0x400019d0`, which is a bare `rts`:

```
400019d0:	4e75           	rts
400019d2:	0000           	.short 0x0000
```

The addresses in `RTOS_FORK.md` §9.3 are right; only the index arithmetic
was wrong. `emu_rtos.py`'s constants `KEY_REC`, `KEY_PLAY` and `KEY_STOP`
are unaffected, because they hold the addresses, not the indices. This
document does not edit either file.

The STOP handler is short and has no state of its own:

```
4000a1e0:	4a39 8000 0029 	tstb 0x80000029
4000a1e6:	6716           	beqs 0x4000a1fe
4000a1e8:	4eb9 4003 3968 	jsr 0x40033968
4000a1ee:	4a80           	tstl %d0
4000a1f0:	6706           	beqs 0x4000a1f8
4000a1f2:	4ef9 4009 f784 	jmp 0x4009f784
4000a1f8:	4ef9 4009 f5bc 	jmp 0x4009f5bc
4000a1fe:	4e75           	rts
```

`0x40033968` is a one-line getter that returns `0x460d1aec`:

```
40033968:	2039 460d 1aec 	movel 0x460d1aec,%d0
4003396e:	4e75           	rts
```

`0x4009f784` is `0x4009f5bc` plus one extra store:

```
4009f784:	4eba fe36      	jsr %pc@(0x4009f5bc)
4009f788:	7002           	moveq #2,%d0
4009f78a:	23c0 8000 66a0 	movel %d0,0x800066a0
4009f790:	4e75           	rts
```

So **both** branches of the STOP handler reach `0x4009f5bc`, and
`0x4009f5bc` writes **2** into `0x800065b8`. There is no store of 0 anywhere
on this path, and the handler is stateless, so a second press behaves like
the first. ✅

🟡 **That `0x4000a1e0` is the STOP key is inferred, not measured.** The
evidence is strong but indirect: it is the third of three consecutive table
entries whose other two are the measured REC and PLAY handlers, and it is
the only one of the three that reaches a routine transmitting MIDI Stop
(`0xfc` at `0x4009f6ec`). `RTOS_FORK.md` §9.3 reached the same conclusion
from the table shape alone and marked it inferred; this adds the MIDI
evidence and keeps the marker.
**Falsifier:** a run under the port that presses `0x4000a1e0` while the
transport is running and shows the word going to anything other than 2, or
that shows a real STOP key press reaching a different handler.

The word does return to 0, but only on the other three stop paths:
`0x400a10c8` (stop and rewind, which REC's own handler calls at `0x4000a336`
before it starts), `0x400a4066` (the sequencer's automatic stop) and
`0x400a1050` (engine init). None of these is reached from the STOP key.

### 1.6 Not measured under the port 🟡

Step 3 of this task could not run. No Octatrack project folder exists on
this machine, and `ot_emu` needs one for `--card`, `--set` and `--project`.
Nothing in this section has been confirmed against a running image by this
pass. The one port measurement that already exists is `RTOS_FORK.md` §9.4's
`[0x800065b8] <- 0x1 (4)` at pc `0x4009c3d4`, from 6 Sep 2026, cited in
section 1.3 and **not re-measured here**.

Two commands will close this, once a card with a project exists.

The start edge, and every write during a sequencer run:

```bash
out/emu/ot_emu --image out/raw/section_3_MAIN_OS.bin --card <card.img> \
  --set <SET> --project <PROJ> --sequencer --frames 50 --load-ms 20000 \
  --watch-mem 0x800065b8,4
```

⚠️ `--peek` is the wrong instrument here, and the task brief's command would
have read as "the word never changed". `--peek ADDR[,ADDR...]` prints one
32-bit word per address **once, after the load and before the sequencer
starts** (`tools/emu/ot_emu/main.cpp` line 447, inside the load block; the
comment at line 101 says so outright). It cannot show the transport start.
`--watch-mem ADDR,LEN` logs every write into the range with its value, size,
PC and task, which is what this needs.

The stop edge needs a key press, and `ot_emu` has no flag for one. Route A
does: `tools/emu/emu_rtos.py` exposes `press_key_live(KEY_STOP)` with
`KEY_STOP = 0x4000a1e0`, and `_word(rt, TRANSPORT)` reads the longword.
Press STOP while the transport is running and read the word before and
after.

**Falsifier for this whole section:** a transport stop from the STOP key
that leaves the word at 0 rather than 2, or a running transport whose word
is anything other than 1. Either would restore the plan's original rule and
retract section 1.0.

### 1.7 Interface

```asm
| The sequencer transport state. A LONGWORD, not a byte: reading it a byte
| at a time reports a flat 0, because the value lands in 0x800065bb.
.equ	TRANSPORT,		0x800065b8

| Stopped AND rewound. The state at engine init, after REC's stop and
| rewind, and after the sequencer's own end of sequence stop.
.equ	TRANSPORT_REWOUND,	0

| Running. The ONLY value that means the sequencer is playing.
.equ	TRANSPORT_RUNNING,	1

| Stopped by the STOP key, with the position kept. Non-zero, which is why
| a tst.l cannot be used to detect a stop.
.equ	TRANSPORT_STOPPED,	2
```

The test the per-frame hook must use, in place of the plan's `tst.l`:

```asm
	move.l	TRANSPORT,%d0		| running iff this is exactly 1
	subq.l	#TRANSPORT_RUNNING,%d0	| Z set while the sequencer plays
```

The start edge is any value going to 1. The stop edge is 1 going to anything
else, and the value it goes to says which stop it was: 2 for the STOP key, 0
for the sequencer's own end of sequence stop, for REC's stop and rewind, and
for engine init.

## 2. The read-back half

### 2.0 The plan's rule holds. Read this first.

The plan's interface is right, and Task 14's `.Lh_room` block does **not**
need to change. The stock frame routine forms the half base as

```
0x80003190 + (longword at 0x800000e0) * 0x400
```

with no mask and no inversion. The firmware bounds that longword to 0 or 1
itself, with a `halt` if it is anything else (section 2.3), so the plan's
`half = (PING ^ 0) & 1` gives the same answer. `PING_XOR` is **0**. The
`and #1` is redundant, not wrong.

Two things about the word are not what its name suggests, and section 2.5
spells them out. The word is not toggled by the frame routine or by the
interrupt that calls it. It is written once per frame, in a **different**
interrupt, which also restarts the chain that leads to the frame routine.
That interrupt runs at level 5 and the frame routine runs with the interrupt
mask at 5, so the word cannot change under the hook. The hook reads the same
half the stock routine reads, in the same frame.

One instruction detail for Task 14: ColdFire immediate shift counts stop at
8. The stock code shifts by 10 through a register, and the hook must do the
same. Section 2.8 gives the exact sequence.

### 2.1 The frame routine and its one caller ✅

`0x400031a0` is called from exactly one place in the image:

```
40004b12:	4eba e68c      	jsr %pc@(0x400031a0)
```

That is the only match for the routine's address in a full linear
disassembly of the image, apart from the routine's own first instruction.
The call is PC-relative, so `refs.sh` cannot see it. The search was a `grep`
over the objdump listing, which prints the resolved target.

The routine runs from `0x400031a0` to its single `rts`:

```
400031a0:	4fef ff6c      	lea %sp@(-148),%sp
400031a4:	48d7 7cfc      	moveml %d2-%d7/%a2-%fp,%sp@
...
40003850:	4cd7 7cfc      	moveml %sp@,%d2-%d7/%a2-%fp
40003854:	4fef 0094      	lea %sp@(148),%sp
40003858:	4e75           	rts
```

There is no other `rts` in that span, so everything between belongs to it.
It saves and restores the whole EMAC state around its body
(`0x400031ac` to `0x400031c4`, and `0x4000383c` to `0x4000384e`), which is
what an audio routine called from an interrupt has to do.

### 2.2 How the half is computed ✅

The routine reads the word once, at the top, and parks it in a stack slot:

```
400031d0:	2039 8000 00e0 	movel 0x800000e0,%d0
400031d6:	2f40 002c      	movel %d0,%sp@(44)
```

`%sp@(44)` is the plan's lead, and it is read back twice. The first use is a
different table, and it is worth recording because it shows the same index
selecting several parallel structures:

```
40003214:	242f 002c      	movel %sp@(44),%d2
40003218:	e78a           	lsll #3,%d2
4000321a:	2f42 006c      	movel %d2,%sp@(108)
4000321e:	2a3c 8000 0eb4 	movel #-2147479884,%d5
40003224:	dbaf 006c      	addl %d5,%sp@(108)
```

That is `0x80000eb4 + half * 8`.

The second use is the read-back block, and it is the rule the hook needs:

```
400033fc:	202f 002c      	movel %sp@(44),%d0
40003400:	720a           	moveq #10,%d1
40003402:	e3a8           	lsll %d1,%d0
40003404:	2f40 0060      	movel %d0,%sp@(96)
40003408:	243c 8000 3190 	movel #-2147470960,%d2
4000340e:	d5af 0060      	addl %d2,%sp@(96)
```

`0x80003190` is `-2147470960` as a signed longword. So
`%sp@(96) = 0x80003190 + half * 0x400`, formed by a shift of 10 with no
masking of any kind.

Note the shift form. `e3a8` is `lsl.l %d1,%d0`, a register count, because
the ColdFire immediate shift `lsl.l #n,%dm` only encodes `n` in 1 to 8. A
hook that writes `lsl.l #10,%d0` will not assemble.

`%sp@(96)` is used as the read pointer, and it is a read, not a write:

```
40003704:	226f 0060      	moveal %sp@(96),%a1
...
40003734:	2019           	movel %a1@+,%d0
40003736:	7410           	moveq #16,%d2
40003738:	a003 0810      	macl %d3,%d0,%acc2
...
40003746:	a099 090b      	msacl %a3,%d0,%a1@+,%d0,%acc0
...
40003756:	a019 190b      	msacl %a3,%d1,%a1@+,%d0,%acc1
40003776:	5382           	subql #1,%d2
40003778:	66be           	bnes 0x40003738
```

Sixteen passes, two post-increment loads of `%a1` each, so 32 longwords or
`0x80` bytes consumed per track.

The outer loop confirms the stride and the count:

```
40003806:	2a3c 0000 0080 	movel #128,%d5
4000380c:	dbaf 0060      	addl %d5,%sp@(96)
...
4000381c:	7008           	moveq #8,%d0
4000381e:	b0af 0070      	cmpl %sp@(112),%d0
40003822:	6600 fc0a      	bnew 0x4000342e
```

Eight tracks, `0x80` bytes each, `0x400` bytes for the half. That is the
whole half, and it agrees with `DSP.md`: tracks 1 to 4 at `0x80003190` and
tracks 5 to 8 at `0x80003390`, which is `0x80003190 + 0x200`.

🟡 **Which loop iteration is track 1 is not settled here.** The loop starts
at offset 0 and steps by `0x80`, and `DSP.md` puts tracks 1 to 4 in the
first `0x200`, so iteration 0 is expected to be track 1. Task 4 owns this.
**Falsifier:** a port run with a known signal on one track showing the
signal at an offset other than `track_index * 0x80`.

### 2.3 The word is 0 or 1, and the firmware says so ✅

The absence of a mask is safe because the firmware checks the range itself
and halts:

```
4000ab30:	7001           	moveq #1,%d0
4000ab32:	23c0 4610 4d4e 	movel %d0,0x46104d4e
4000ab38:	b0b9 8000 00e0 	cmpl 0x800000e0,%d0
4000ab3e:	6402           	bccs 0x4000ab42
4000ab40:	4ac8           	halt
```

`cmpl 0x800000e0,%d0` computes `1 - value`, and `bcc` takes the branch when
there was no borrow, that is when `1 >= value` unsigned. Any value above 1
runs into the `halt`. The check sits four instructions after the only write
to the word, so it guards every value the word can take.

### 2.4 Every writer of `0x800000e0`, classified ✅

`refs.sh 0x800000e0` returns 35 hits. The helper was checked first on
`0x800065b8`, which gave the expected 33.

Thirty-four of the 35 are reads. Every one is a `movel <abs>,Dn` in one of
its register encodings (`2039`, `2239`, `2439`, `2639`, `2839`, `2a39`,
`2e39`), a push (`2f39`, at `0x4000d364` and `0x4000d524`), a compare
(`b0b9`, at `0x4000ab38`), or an `lea` (`41f9` at `0x4000aaee`, `43f9` at
`0x4000caf4`). Neither `lea` is used to store. `%a0` at `0x4000aaee` is read
once at displacement 0 on the next instruction, and `%a1` at `0x4000caf4` is
read once and then reloaded from `%d1` at `0x4000cb16`.

There is exactly one write:

```
4000aaee:	41f9 8000 00e0 	lea 0x800000e0,%a0
4000aaf4:	23d0 8000 00e4 	movel %a0@,0x800000e4
4000aafa:	3039 2000 001c 	movew 0x2000001c,%d0
4000ab00:	7140           	mvsw %d0,%d0
4000ab02:	23c0 8000 00e0 	movel %d0,0x800000e0
```

Read it in order. The old half index is copied to `0x800000e4`. A word is
read from the DSP host port at `0x2000001c` and sign extended. That word
becomes the new half index. So the DSP publishes the half, and the ColdFire
keeps the previous one next door.

`0x800000e4` has the same shape: 13 references in the image, of which
`0x4000aaf4` above is the only write. The other 12 are `movel <abs>,Dn` or
pushes. The DMA setup steps use it for the buffers the DSP is still filling
(`0x400048f6`, `0x40004964`, `0x40004a48`, `0x40004ab2`).

#### Displacement forms, checked ✅

`refs.sh` matches 32-bit literals, so a store written as `lea 0x80000000,%aN`
plus a displacement of `0xe0` would be invisible to it. A `grep` over the
full linear disassembly for `%aN@(224)` returns three sites, and none of them
has `0x80000000` in the base register:

```
40084438:	2029 00e0      	movel %a1@(224),%d0
4008443e:	2340 00e0      	movel %d0,%a1@(224)
400d867e:	2268 00e0      	moveal %a0@(224),%a1
```

At `0x40084438` the same `%a1` is used at displacements `0xcc`, `0xd0`,
`0xd8` and `0xdc` in the surrounding lines, so it is a structure pointer.
At `0x400d867e` the access is a load of a pointer, not a store.

🟡 **What remains unseen.** A store through a base register computed at run
time, for example a struct pointer read out of memory, would be invisible to
both checks.
**Falsifier:** a write watch over `0x800000e0,4` under the port reporting a
store from a PC other than `0x4000ab02`.

### 2.5 Where the write sits, relative to the `jsr` ✅

The write is not in the interrupt that calls the frame routine. It is in a
different one, and that one runs first.

**The writer's interrupt.** `0x4000aad0` is an exception handler, not a
subroutine. It saves every register at entry and its only exit is an `rte`:

```
4000aad0:	4fef ff04      	lea %sp@(-252),%sp
4000aad4:	48d7 7fff      	moveml %d0-%fp,%sp@
...
4000d9a6:	4cd7 7fff      	moveml %sp@,%d0-%fp
4000d9aa:	4fef 00fc      	lea %sp@(252),%sp
4000d9ae:	4e73           	rte
```

It is installed on vector `0x41` at level 5:

```
4001fbf8:	4879 4000 aad0 	pea 0x4000aad0
4001fbfe:	4878 0041      	pea 0x41
4001fc02:	4eb9 4000 0d50 	jsr 0x40000d50
...
4001fc2e:	7005           	moveq #5,%d0
4001fc30:	13c0 fc04 8041 	moveb %d0,0xfc048041
```

`0x40000d50` is a three-line vector installer. It takes the vector number in
`%sp@(4)` and the handler in `%sp@(8)` and stores the handler into the table
whose base is at `0x400b9668`:

```
40000d50:	202f 0004      	movel %sp@(4),%d0
40000d54:	2079 400b 9668 	moveal 0x400b9668,%a0
40000d5a:	43ef 0008      	lea %sp@(8),%a1
40000d5e:	2191 0c00      	movel %a1@,%a0@(0,%d0:l:4)
40000d62:	4e75           	rts
```

Vector `0x41` is 65, which is interrupt source 1, whose control register is
`0xfc048041`. The value written there is 5, so the handler runs at
**level 5**.

**The caller's interrupt.** The `jsr` at `0x40004b12` is inside a second
handler that entered at `0x40004840`:

```
40004840:	4fef fff0      	lea %sp@(-16),%sp
40004844:	48d7 0303      	moveml %d0-%d1/%a0-%a1,%sp@
40004848:	4200           	clrb %d0
4000484a:	13c0 fc04 401c 	moveb %d0,0xfc04401c
40004850:	2039 4610 4d3e 	movel 0x46104d3e,%d0
40004856:	41f9 400a b61a 	lea 0x400ab61a,%a0
4000485c:	2070 0c00      	moveal %a0@(0,%d0:l:4),%a0
40004860:	4ed0           	jmp %a0@
```

It is a jump table on a step counter at `0x46104d3e`. The table at
`0x400ab61a` holds:

| step | target |
|---|---|
| 0 | `0x40004862` |
| 1 | `0x400048da` |
| 2 | `0x4000495c` |
| 3 | `0x400049ca` |
| 4 | `0x40004a38` |
| 5 | `0x40004aaa` |
| 6 | `0x40004b36` |
| 7 | `0x40004bc0` |

Each step programs one transfer and bumps the counter, so the chain walks
itself on successive DMA completions.

The handler is installed on three vectors, all at level 6:

```
40009798:	487a b0a6      	pea %pc@(0x40004840)
4000979c:	4878 0048      	pea 0x48
400097a8:	487a b096      	pea %pc@(0x40004840)
400097ac:	4878 0049      	pea 0x49
400097b2:	487a b08c      	pea %pc@(0x40004840)
400097b6:	4878 004f      	pea 0x4f
400097bc:	7406           	moveq #6,%d2
400097be:	13c2 fc04 8048 	moveb %d2,0xfc048048
400097c4:	13c2 fc04 8049 	moveb %d2,0xfc048049
400097ca:	13c2 fc04 804f 	moveb %d2,0xfc04804f
```

**The `jsr` is in step 5.** Step 5 enters at `0x40004aaa`, programs a
transfer at `0x800000e4 * 0x200 + 0x80000210`, and falls through into the
block the plan names:

```
40004af0:	303c 8004      	movew #-32764,%d0
40004af4:	33c0 fc04 5014 	movew %d0,0xfc045014
40004afa:	33c0 fc04 501c 	movew %d0,0xfc04501c
40004b00:	4201           	clrb %d1
40004b02:	13c1 fc04 401e 	moveb %d1,0xfc04401e
40004b08:	52b9 4610 4d3e 	addql #1,0x46104d3e
40004b0e:	46fc 2500      	movew #9472,%sr
40004b12:	4eba e68c      	jsr %pc@(0x400031a0)
40004b16:	46fc 2700      	movew #9984,%sr
40004b1a:	2039 4610 4d3e 	movel 0x46104d3e,%d0
40004b20:	7206           	moveq #6,%d1
40004b22:	b280           	cmpl %d0,%d1
40004b24:	6600 00a2      	bnew 0x40004bc8
```

So between the handler's entry and the `jsr`, on the pass that reaches it:
the DMA interrupt flags at `0xfc045014` and `0xfc04501c` are acknowledged,
`0xfc04401e` is cleared, the step counter goes from 5 to 6, and the status
register is lowered from `0x2700` to `0x2500`. **Nothing on that path
touches `0x800000e0`.**

Between the `jsr` returning and the `rte`: the status register goes back to
`0x2700`, the step counter is compared with 6, and if the DMA status word at
`0xfc04501e` has a negative top byte the handler runs step 6's body inline at
`0x40004b44`. That body programs the next transfer **into** the same half the
frame routine has just read:

```
40004b58:	2039 8000 00e0 	movel 0x800000e0,%d0
40004b5e:	323c 000a      	movew #10,%d1
40004b62:	e3a8           	lsll %d1,%d0
40004b64:	0680 8000 3190 	addil #-2147470960,%d0
40004b6a:	23c0 fc04 5000 	movel %d0,0xfc045000
```

It reads `0x800000e0`, it does not write it. The handler then falls to the
common exit:

```
40004bc8:	4cd7 0303      	moveml %sp@,%d0-%d1/%a0-%a1
40004bcc:	4fef 0010      	lea %sp@(16),%sp
40004bd0:	4e73           	rte
```

**The write comes before the `jsr`, in the level 5 handler, and that handler
is what starts the chain.** The handler reaches the reset of the step counter
past three decision points, and here are all three:

```
4000ab02:	23c0 8000 00e0 	movel %d0,0x800000e0
4000ab08:	4eb9 4001 c9b0 	jsr 0x4001c9b0
4000ab0e:	4a80           	tstl %d0
4000ab10:	6708           	beqs 0x4000ab1a
4000ab12:	4eba fde8      	jsr %pc@(0x4000a8fc)
4000ab16:	6000 2e8e      	braw 0x4000d9a6
4000ab1a:	327c 008c      	moveaw #140,%a1
4000ab1e:	33c9 2000 0004 	movew %a1,0x20000004
4000ab24:	51fc           	tpf
4000ab26:	3039 2000 0004 	movew 0x20000004,%d0
4000ab2c:	4a00           	tstb %d0
4000ab2e:	6df6           	blts 0x4000ab26
```

`0x4000ab10` is an error exit, covered below. `0x4000ab2e` is a spin on the
DSP command vector register at `0x20000004`, waiting for the host command
`0x8c` to be taken. `0x4000ab3e` is the range guard quoted in section 2.3,
whose other arm is the `halt`.

From `0x4000ab42` to `0x4000ac32` there is no branch, jump, call or return
at all. That was checked over the whole 240-byte span, not sampled. The span
ends:

```
4000ac2c:	42b9 4610 4d3a 	clrl 0x46104d3a
4000ac32:	42b9 4610 4d3e 	clrl 0x46104d3e
```

So on the working path the write and the reset always happen together, in
that order.

🟡 **The error exit at `0x4000ab12` writes the word and does not reset the
counter.** On that path `0x800000e0` has already changed while a step chain
from the previous frame may still be walking, so the frame routine could
read a half that chain did not fill. The path calls `0x4000a8fc` and leaves
by `braw 0x4000d9a6`, which is the handler's register restore and `rte`, so
it also skips the increment of `0x80004800` at `0x4000d98e`. It is a fault
path, and a hook cannot do better than the stock routine on it, because the
stock routine reads the same word.
**Falsifier:** a port run reaching `0x4000ab12` during normal playback.

`0x46104d3e` is the counter the level 6 handler dispatches on. Clearing it
sends the next DMA completion to step 0. Step 0 programs the transfer that
fills the half:

```
400048a2:	2039 8000 00e0 	movel 0x800000e0,%d0
400048a8:	720a           	moveq #10,%d1
400048aa:	e3a8           	lsll %d1,%d0
400048ac:	0680 8000 3190 	addil #-2147470960,%d0
400048b2:	23c0 fc04 5030 	movel %d0,0xfc045030
```

and the level 5 handler itself programs the companion transfer into
`0x80003390 + half * 0x400`, the second `0x200` of the same block:

```
4000aba2:	2039 8000 00e0 	movel 0x800000e0,%d0
4000aba8:	720a           	moveq #10,%d1
4000abaa:	e3a8           	lsll %d1,%d0
4000abac:	0680 8000 3390 	addil #-2147470448,%d0
4000abb2:	23c0 fc04 5030 	movel %d0,0xfc045030
```

That matches `DSP.md`: `0x80003190` is core 1 with tracks 1 to 4, and
`0x80003390` is core 0 with tracks 5 to 8.

So the order within one frame is:

1. Level 5 handler `0x4000aad0` entered.
2. `0x4000aaf4` copies the old half index to `0x800000e4`.
3. `0x4000ab02` writes the new half index to `0x800000e0`.
4. `0x4000ab38` halts if it is not 0 or 1.
5. `0x4000abb2` programs the transfer into `0x80003390 + half * 0x400`.
6. `0x4000ac32` resets the step counter, so the chain restarts at step 0.
7. `rte`.
8. Level 6 handler, step 0, programs the transfer into
   `0x80003190 + half * 0x400`.
9. Steps 1 to 4 program the other transfers.
10. Step 5 falls through to `0x40004af0`, lowers the mask to 5, and calls
    `0x400031a0` at `0x40004b12`.
11. `0x400031a0` reads `0x800000e0` at `0x400031d0` and walks
    `0x80003190 + half * 0x400`.

**The hook runs at point 10, one instruction before the `jsr`. It sees the
value written at point 3, and so does the stock routine at point 11. Same
value, same half, no inversion.**

🟡 **That the level 5 handler runs once per audio frame is inferred.** What
is measured is that it resets the step chain, takes a fresh half index from
the DSP host port, and programs the frame's transfers. That is a frame's
worth of work, and nothing else in the image resets the counter except the
one `clrl` at `0x4000ac32`.
**Falsifier:** a port run counting entries to `0x4000aad0` against frames and
finding a different rate.

### 2.6 The word cannot change under the hook ✅

The hook is detoured at `0x40004b12`, which is after the
`movew #9472,%sr` at `0x40004b0e`. `9472` is `0x2500`, so the supervisor bit
is set and the interrupt priority mask is 5.

A ColdFire interrupt is taken only when its level is **greater** than the
mask, level 7 excepted. The only writer of `0x800000e0` is in the level 5
handler on vector `0x41`. Level 5 is not greater than 5, so that handler
cannot preempt the hook or the frame routine.

The level 6 DMA handler can preempt, and so can the level 7 handler at
`0x4001fca0` that `0x4001f814` installs on vector `0x47`, but neither writes
the word. Section 2.4's census is what makes that a fact rather than a hope.
There is one writer in the whole image.

So the hook may read the word once and use that value for its whole copy.
That is what the stock routine does.

### 2.7 What the port cannot show 🟡

Nothing in this section was run. No Octatrack project folder exists on this
machine, and `ot_emu` needs one for `--card`, `--set` and `--project`. The
static reading is the evidence.

The port would be a weak instrument here even with a project. Under the port
a DMA completes instantly, so no half is ever torn and no half is ever
stale. A hook that reads the wrong half renders correct audio one frame
late, and one frame is 16 samples. That is inaudible in a render and
invisible to any byte comparison that does not align the frames. This is the
instrument blindness trap in `CLAUDE.md`: a lock-step emulator cannot show a
race, and a green local result is not evidence that the half choice is
right.

What a port run could add, once a card exists, is the value the word
actually takes and an independent writer census:

```bash
out/emu/ot_emu --image out/raw/section_3_MAIN_OS.bin --card <card.img> \
  --set <SET> --project <PROJ> --frames 50 --load-ms 20000 \
  --watch-mem 0x800000e0,4
```

Every write should come from `0x4000ab02`, and every value should be 0 or 1.
Any other PC retracts section 2.4.

### 2.8 Interface

```asm
| The read-back half index the DSP publishes each frame. A LONGWORD holding
| 0 or 1; the firmware halts at 0x4000ab40 if it is anything else. Written
| at exactly one site, 0x4000ab02, in the level 5 handler on vector 0x41.
.equ	PING,		0x800000e0

| No inversion. The hook runs at 0x40004b12 with the interrupt mask at 5,
| which locks out the only writer, so the hook and the stock frame routine
| read the same value in the same frame.
.equ	PING_XOR,	0

| Base of the read-back block, half 0. Tracks 1 to 4 here, tracks 5 to 8 at
| RDBK_BASE + 0x200.
.equ	RDBK_BASE,	0x80003190

| Bytes per half: 8 tracks of RDBK_TRACK.
.equ	RDBK_HALF,	0x400

| Bytes per track inside a half: 16 samples, stereo, one longword each.
.equ	RDBK_TRACK,	0x80
```

The rule, as the plan states it: `half = (PING ^ PING_XOR) & 1`, byte offset
`half * RDBK_HALF`. The `& 1` is redundant because the firmware bounds the
word to 0 or 1, and the stock routine omits it.

The arithmetic a hook can execute, matching `0x400033fc` instruction for
instruction. The shift count goes through a register because a ColdFire
immediate shift only encodes 1 to 8:

```asm
	move.l	PING,%d0		| 0 or 1
	moveq	#10,%d1
	lsl.l	%d1,%d0			| times RDBK_HALF
	add.l	#RDBK_BASE,%d0		| half base
	add.l	#RDBK_TRACK*N,%d0	| track N, N from section 3
```

## 3. Creating a task

### 3.0 The capacity question, answered first ✅

The ready structure is **a circular doubly linked list of task control
blocks, one list per priority, with no capacity field and no bitmap**. A
priority holds as many tasks as are linked into its ring. Priority 1 already
holds three, and a fourth needs nothing beyond the same two calls stock
makes. Task 15's design stands.

Section 3.5 shows the insertion code. Nothing in it counts, compares against
a limit, or fails.

One bound does exist, and it is on the priority number, not on the task
count. The list heads are an array of **eight** longwords at `0x800068dc`,
priorities 0 to 7. The create routine indexes it with no check. Priority 1
is inside the array, so this does not constrain STEM REC. Section 3.5 gives
the evidence.

Term note. A **task control block**, TCB below, is the 84 byte structure the
kernel keeps per task: its two ring links, its priority, its saved
registers, and its state. A **ready list** is the ring of TCBs at one
priority that are eligible to run.

### 3.1 The two routines and every call site ✅

`0x400005fc` creates a task. `0x4000063c` makes it runnable. Both are called
only in that pair, and always in that order.

`refs.sh 0x400005fc` returns 7 hits and `refs.sh 0x4000063c` returns 7. Each
hit is the operand of either a `jsr` to the absolute address or a `lea` that
loads the address into an address register for repeated use. The two `lea`
sites carry five calls between them, which is the "five more call through a
register" the task lead named. Counting calls rather than literals gives
**ten create calls at seven literal sites**.

| # | create call | form | tcb | entry | prio | stack | size |
|---|---|---|---|---|---|---|---|
| 1 | `0x400054dc` | `jsr 0x400005fc` | `0x46c7fb0c` | `0x40005540` | 6 | `0x46c7ea20` | `0x1000` |
| 2 | `0x4001dfec` | `jsr 0x400005fc` | `0x460bcc2c` | `0x4001ee30` | 5 | `0x460bc42c` | `0x800` |
| 3 | `0x400403f0` | `jsr %a2@` | `0x460d4f80` | `0x4005593c` | 4 | `0x460d4780` | `0x800` |
| 4 | `0x4004041a` | `jsr %a2@` | `0x460d59d4` | `0x40056c40` | 3 | `0x460d51d4` | `0x800` |
| 5 | `0x40040cdc` | `jsr %a3@` | `0x460ddde4` | `0x4008445c` | 1 | `0x460d9de4` | `0x4000` |
| 6 | `0x40040d06` | `jsr %a3@` | `0x460e0e38` | `0x4009203c` | 2 | `0x460dee38` | `0x2000` |
| 7 | `0x40040d2e` | `jsr %a3@` | `0x46c7bed8` | `0x40061a94` | 1 | `0x460d6de4` | `0x2000` |
| 8 | `0x40091d00` | `jsr 0x400005fc` | `0x460fab80` | `0x40091d18` | 2 | `0x460fabd4` | `0x2000` |
| 9 | `0x400921a8` | `jsr 0x400005fc` | `0x460ffd44` | `0x400921c4` | 2 | `0x460fdd44` | `0x2000` |
| 10 | `0x40098a44` | `jsr 0x400005fc` | `0x46105508` | `0x40098a5c` | 1 | `0x4610555c` | `0x2000` |

Rows 3 and 4 sit in one routine that holds create in `%a2` and start in
`%a3`. Rows 5, 6 and 7 sit in another that holds create in `%a3` and start
in `%a2`. The register assignment is swapped between the two routines, so
reading one and assuming the other is a mistake.

```
400403ea:	45f9 4000 05fc 	lea 0x400005fc,%a2
400403f0:	4e92           	jsr %a2@
400403f8:	47f9 4000 063c 	lea 0x4000063c,%a3
400403fe:	4e93           	jsr %a3@
```

```
40040cd6:	47f9 4000 05fc 	lea 0x400005fc,%a3
40040cdc:	4e93           	jsr %a3@
40040ce4:	45f9 4000 063c 	lea 0x4000063c,%a2
40040cea:	4e92           	jsr %a2@
```

Every create call is followed by a start call on the same TCB. The ten start
calls are `0x400054e8`, `0x4001dffc`, `0x400403fe`, `0x40040426`,
`0x40040cea`, `0x40040d12`, `0x40040d36`, `0x40091d0c`, `0x400921b8` and
`0x40098a50`.

One task is not created by `0x400005fc` at all. The boot code hand builds it
and calls only start:

```
40000e34:	4879 46c7 ae84 	pea 0x46c7ae84
40000e3a:	4eba f800      	jsr %pc@(0x4000063c)
```

Section 3.3 uses that hand built task as a second, independent reading of
the frame layout.

Priority 1 therefore holds three tasks in stock: rows 5, 7 and 10. That is
the count the plan assumed, confirmed from the image.

#### Is the census complete? ✅ for direct and PC relative calls, 🟡 beyond

`refs.sh` matches 32 bit literals, so a PC relative call is invisible to it.
Two further checks were run.

**1. Every PC relative call form, scanned by bytes.** A scan of every even
offset in the image for `jsr %pc@(d16)` (`0x4eba`), `bsr.b`, `bsr.w` and
`bsr.l`, resolving each displacement, finds **exactly one** call to either
address: the boot's `0x40000e3a` above. There are **zero** occurrences of
the word `0x4ebb`, which is `jsr %pc@(d8,Xn)`, at any even offset in the
image, so the indexed PC relative form is not used anywhere. ✅

**2. A linear disassembly of the whole image**, grepped for both addresses
in objdump's resolved target column, returns the same set and nothing else.
✅

🟡 **What remains unseen.** A call through an address register whose value
came from memory rather than from a `lea` of a literal would be invisible to
all three checks. So would a call through a dispatch table built at run
time.
**Falsifier:** a program counter watch on `0x400005fc` under the port
reporting an entry from a program counter that is not one of the ten call
sites above.

### 3.2 K_CREATE, the argument list ✅

The whole routine, 64 bytes:

```
400005fc:	226f 0004      	moveal %sp@(4),%a1
40000600:	202f 000c      	movel %sp@(12),%d0
40000604:	72fc           	moveq #-4,%d1
40000606:	c2af 0014      	andl %sp@(20),%d1
4000060a:	d2af 0010      	addl %sp@(16),%d1
4000060e:	e588           	lsll #2,%d0
40000610:	0680 8000 68dc 	addil #-2147456804,%d0
40000616:	2340 0008      	movel %d0,%a1@(8)
4000061a:	2041           	moveal %d1,%a0
4000061c:	213c 4000 06e4 	movel #1073743588,%a0@-
40000622:	212f 0008      	movel %sp@(8),%a0@-
40000626:	213c 407c 2000 	movel #1081876480,%a0@-
4000062c:	2348 0048      	movel %a0,%a1@(72)
40000630:	42a9 004c      	clrl %a1@(76)
40000634:	42a9 0050      	clrl %a1@(80)
40000638:	7001           	moveq #1,%d0
4000063a:	4e75           	rts
```

There is no `link`, so `%sp@(0)` is the return address and the arguments
start at `%sp@(4)`. Five longwords, in this order:

| slot | name | meaning |
|---|---|---|
| `%sp@(4)` | `tcb` | address of an 84 byte TCB the caller owns. See section 3.6. |
| `%sp@(8)` | `entry` | address of the task function. It is called with **no arguments**. |
| `%sp@(12)` | `prio` | priority, 0 to 7. Higher number wins. See section 3.5. |
| `%sp@(16)` | `stack` | **base** of the stack, its lowest address. |
| `%sp@(20)` | `size` | stack length in **bytes**. |

C calling convention, so arguments are pushed right to left and the caller
pops them. A call is five `pea` instructions in reverse order, then `jsr`,
then a 20 byte stack adjustment. Row 1's call, in full:

```
400054c4:	4878 1000      	pea 0x1000
400054c8:	4879 46c7 ea20 	pea 0x46c7ea20
400054ce:	4878 0006      	pea 0x6
400054d2:	487a 006c      	pea %pc@(0x40005540)
400054d6:	4879 46c7 fb0c 	pea 0x46c7fb0c
400054dc:	4eb9 4000 05fc 	jsr 0x400005fc
```

**The stack pointer convention, exactly.** `stack` names the base and `size`
counts bytes, so the top is `stack + size`. The routine computes it in three
instructions and rounds only `size` down to a multiple of 4, never `stack`:

```
40000604:	72fc           	moveq #-4,%d1          | d1 = 0xfffffffc
40000606:	c2af 0014      	andl %sp@(20),%d1      | d1 = size & ~3
4000060a:	d2af 0010      	addl %sp@(16),%d1      | d1 = stack + (size & ~3)
```

The caller must therefore pass a 4 byte aligned `stack`. Every stock call
does. Three longwords are then pushed with `%a0@-`, so the value stored in
the TCB is

```
initial SP = stack + (size & ~3) - 12
```

⚠️ **The mask is on `size`, not on the sum.** An unaligned `stack` produces
an unaligned stack pointer and an address error on the task's first push.
Align the base. Do not rely on the mask.

**Return value ✅.** `moveq #1,%d0` at `0x40000638` is unconditional and the
only exit is the `rts` after it. `K_CREATE` **always returns 1 in `%d0`.
There is no failure path.** Nothing is validated: not the priority, not the
stack alignment, not the TCB address. A caller cannot learn that it got
something wrong.

**What create writes into the TCB ✅.** Four fields, and nothing else:

| offset | value |
|---|---|
| `+8` | `0x800068dc + 4 * prio`, the address of this priority's list head |
| `+72` | the initial stack pointer computed above |
| `+76` | 0 |
| `+80` | 0 |

`+0` and `+4`, the ring links, are **not** written by create. Start writes
them. The saved register block at `+12` through `+71` is not written either.
Section 3.8 says what follows from that.

### 3.3 The first frame, and what the entry function sees ✅

Three longwords are pushed at the stack top, from high address to low:

```
4000061c:	213c 4000 06e4 	movel #1073743588,%a0@-   | 0x400006e4
40000622:	212f 0008      	movel %sp@(8),%a0@-       | entry
40000626:	213c 407c 2000 	movel #1081876480,%a0@-   | 0x407c2000
```

Laid out, with `top = stack + (size & ~3)`:

| address | longword | role |
|---|---|---|
| `top - 4` | `0x400006e4` | return address for the entry function |
| `top - 8` | `entry` | the program counter the `rte` loads |
| `top - 12` | `0x407c2000` | ColdFire exception frame format word, then SR |

The scheduler restores a task by loading its registers, including `%sp`,
from the TCB, and then executing `rte`. The `rte` pops the format and SR
longword and then the program counter:

```
400005a0:	4ce8 ffff 000c 	moveml %a0@(12),%d0-%sp
400005a6:	4e73           	rte
```

So on the task's first instruction `%sp` is `top - 4` and `%sp@(0)` is
`0x400006e4`. **The entry function is entered exactly as if it had been
called with `jsr` and no arguments.** ✅ Task 15's entry must take no
parameters.

`0x400006e4` is the task exit stub. It reads the current TCB from
`0x800068fc`, clears `+76`, unlinks the TCB from its ready ring, and traps
into the scheduler, which never comes back:

```
400006e4:	2f0a           	movel %a2,%sp@-
400006e8:	2479 8000 68fc 	moveal 0x800068fc,%a2
400006f0:	46fc 2700      	movew #9984,%sr
400006f4:	42aa 004c      	clrl %a2@(76)
40000732:	4e40           	trap #0
```

So an entry function that returns deletes its own task cleanly. It does not
free the TCB or the stack. ✅

**The SR the task starts with ✅.** The low word of `0x407c2000` is `0x2000`:
supervisor set, trace off, interrupt mask 0. The task runs with all
interrupts enabled.

🟡 **The high word `0x407c`.** Read against the ColdFire frame layout it is
format 4, fault status 0, vector 31. Only the format field and the SR matter
to `rte`. Task 15 must push the same constant rather than reason about it.
**Falsifier:** a format field the V4e `rte` rejects would raise a format
error at the task's first dispatch instead of entering the task.

**A second, independent reading of the same frame ✅.** The boot code builds
one by hand for the `main` task, TCB `0x46c7ae84`, and never calls create:

```
40000df8:	203c 4000 06e4 	movel #1073743588,%d0
40000dfe:	23c0 46c7 bed4 	movel %d0,0x46c7bed4      | top-4  = 0x400006e4
40000e04:	223c 4001 f834 	movel #1073870900,%d1
40000e0a:	23c1 46c7 bed0 	movel %d1,0x46c7bed0      | top-8  = entry
40000e10:	203c 407c 2000 	movel #1081876480,%d0
40000e16:	23c0 46c7 becc 	movel %d0,0x46c7becc      | top-12 = 0x407c2000
40000e1c:	223c 46c7 becc 	movel #1187495628,%d1
40000e22:	23c1 46c7 aecc 	movel %d1,0x46c7aecc      | tcb+72 = top-12
40000e28:	42b9 46c7 aed0 	clrl 0x46c7aed0           | tcb+76 = 0
40000e2e:	42b9 46c7 aed4 	clrl 0x46c7aed4           | tcb+80 = 0
40000e34:	4879 46c7 ae84 	pea 0x46c7ae84
40000e3a:	4eba f800      	jsr %pc@(0x4000063c)
```

`0x46c7aecc - 0x46c7ae84 = 72`, `0x46c7aed0 - 0x46c7ae84 = 76`, and
`0x46c7aed4 - 0x46c7ae84 = 80`. Every offset and every constant matches what
create does, from a code path that never touches create.

The priority field is written a few instructions earlier, and it matches
`K_CREATE`'s own formula exactly ✅:

```
40000dec:	223c 8000 68dc 	movel #-2147456804,%d1
40000df2:	23c1 46c7 ae8c 	movel %d1,0x46c7ae8c      | tcb+8 = 0x800068dc
```

`0x46c7ae8c - 0x46c7ae84 = 8`, and `0x800068dc` is what create's formula
`0x800068dc + 4 * prio` gives for priority 0. So `main` runs at priority 0,
and the boot writes the same four fields create writes, with the same
values, computed the same way.

### 3.4 K_START, the whole routine ✅

```
4000063c:	2f0a           	movel %a2,%sp@-
4000063e:	246f 0008      	moveal %sp@(8),%a2      | a2 = tcb
40000642:	40c1           	movew %sr,%d1           | save the caller's SR
40000644:	46fc 2700      	movew #9984,%sr         | mask to level 7
40000648:	202a 0008      	movel %a2@(8),%d0       | d0 = this priority's head address
4000064c:	b0b9 8000 68d8 	cmpl 0x800068d8,%d0
40000652:	6306           	blss 0x4000065a
40000654:	23c0 8000 68d8 	movel %d0,0x800068d8    | raise the top-priority pointer
4000065a:	7001           	moveq #1,%d0
4000065c:	2540 004c      	movel %d0,%a2@(76)      | tcb+76 = 1, the task is ready
40000660:	226a 0008      	moveal %a2@(8),%a1      | a1 = &head
40000664:	2011           	movel %a1@,%d0          | d0 = head
40000666:	660a           	bnes 0x40000672
40000668:	228a           	movel %a2,%a1@          | empty: head = tcb
4000066a:	248a           	movel %a2,%a2@          |        tcb->next = tcb
4000066c:	254a 0004      	movel %a2,%a2@(4)       |        tcb->prev = tcb
40000670:	6014           	bras 0x40000686
40000672:	2540 0004      	movel %d0,%a2@(4)       | tcb->prev = head
40000676:	2051           	moveal %a1@,%a0
40000678:	2490           	movel %a0@,%a2@         | tcb->next = head->next
4000067a:	2051           	moveal %a1@,%a0
4000067c:	2050           	moveal %a0@,%a0
4000067e:	214a 0004      	movel %a2,%a0@(4)       | head->next->prev = tcb
40000682:	2051           	moveal %a1@,%a0
40000684:	208a           	movel %a2,%a0@          | head->next = tcb
40000686:	46c1           	movew %d1,%sr           | restore the caller's SR
40000688:	245f           	moveal %sp@+,%a2
4000068a:	4e75           	rts
```

**One argument**, the same `tcb` create was given. It is at `%sp@(8)` and not
`%sp@(4)` because `%a2` was pushed first. A call is one `pea` and a `jsr`,
then a 4 byte stack adjustment.

**Return value ✅.** `moveq #1,%d0` at `0x4000065a` is on both paths of the
branch above it, and nothing after it writes `%d0`. `K_START` **always
returns 1 in `%d0`**. Like create, it has no failure path.

**It does not force a context switch ✅.** There is no `trap #0` anywhere in
`0x4000063c` to `0x4000068a`, and no write to the software interrupt bit at
`0xfc04c010` that the kernel's post routines use to request one. A newly
started task runs at the next scheduling point, not at the `jsr`. This holds
even when the new task outranks its creator.

### 3.5 The ready structure, and why it has no capacity ✅

Three facts, all from the code above.

**1. Each priority's ready list is a circular doubly linked ring of TCBs.**
`tcb+0` is the forward link and `tcb+4` the backward link. The empty case at
`0x40000668` points both at the TCB itself. The non empty case at
`0x40000672` splices the new TCB in between the head and the head's
successor. There is no counter, no array of slots and no bitmap. **A
priority holds any number of tasks.** ✅

**2. The head array is eight longwords, priorities 0 to 7.** The kernel's
init clears exactly that range:

```
40000dd0:	41f9 8000 68dc 	lea 0x800068dc,%a0
40000dd6:	4298           	clrl %a0@+
40000dd8:	b1fc 8000 68fc 	cmpal #-2147456772,%a0
40000dde:	66f6           	bnes 0x40000dd6
```

`0x800068dc` to `0x800068fb`, eight entries. `0x800068fc`, the loop's limit,
is the current TCB pointer, so a priority of 8 would overwrite it. Create
does not check:

```
4000060e:	e588           	lsll #2,%d0
40000610:	0680 8000 68dc 	addil #-2147456804,%d0
```

Priority 1 gives `0x800068e0`, well inside the array. ✅

**3. Higher priority number wins, and the scheduler is round robin inside a
priority.** `0x800068d8`, one longword below the array, holds the **address**
of the highest numbered non empty head. `K_START` raises it. The trap 0
handler reads it, takes the head's successor, and makes that successor the
new head:

```
4000056c:	2279 8000 68d8 	moveal 0x800068d8,%a1
40000576:	2051           	moveal %a1@,%a0       | a0 = head
4000057c:	2050           	moveal %a0@,%a0       | a0 = head->next
4000058e:	23c8 8000 68fc 	movel %a0,0x800068fc  | current = it
40000594:	2288           	movel %a0,%a1@        | head = it
```

The unblock paths walk **down** from `0x800068d8` looking for a non empty
head, which is only consistent with a higher number meaning a higher
priority:

```
400007e0:	4aa1           	tstl %a1@-
400007e2:	67fc           	beqs 0x400007e0
400007e4:	23c9 8000 68d8 	movel %a1,0x800068d8
```

So priority 1 is second lowest of eight. A priority 1 task runs whenever no
task at priority 2 through 7 is ready, and it shares its ring round robin
with the three tasks already there. ✅

⚠️ For Task 15. The UI task runs at **priority 3**, row 4 of the census, TCB
`0x460d59d4`. A menu action that creates a priority 1 task therefore does not
lose the processor at the `jsr`, and the new task first runs when the UI task
blocks or yields. That is the intended behaviour and it matches what stock
does at all ten of its sites.

### 3.6 The TCB is 84 bytes, measured two ways that agree ✅

**Way 1: the largest offset any kernel routine touches, rounded up to 4.**

Every routine in `0x40000550` to `0x40000d4c` was disassembled and every
`%aN@(disp)` displacement counted. Discarding the two that are vector table
writes rather than TCB accesses, `%a0@(684)` at `0x400005d8` and
`%a0@(128)` at `0x400005dc`, vectors 171 and 32, both pointing at the trap 0
handler, and the queue object fields at `+16` to `+28` in `0x40000bd4`, the
TCB offsets in use are 0, 4, 8, 12, 44, 72, 76 and 80.

| offset | width | field | touched by |
|---|---|---|---|
| `+0` | long | ring forward link | start, delete, the block and unblock paths |
| `+4` | long | ring backward link | the same |
| `+8` | long | `0x800068dc + 4 * prio` | create, and the set priority helper `0x40000744` |
| `+12` .. `+71` | 60 | saved `%d0` to `%d7` and `%a0` to `%a6` | the trap 0 handler |
| `+72` | long | saved `%a7`, the task's stack pointer | create, then the trap 0 handler |
| `+76` | long | ready flag, 1 when linked, 0 when blocked | create, start, delete, block, unblock |
| `+80` | long | next waiter, for the mutex and event queues | `0x400009f4`, read by `0x40000ab4` and `0x40000b4c` |

The `+12` to `+72` block is one instruction at each end, and it fixes the
layout exactly. Sixteen registers, `%d0` through `%a7`:

```
40000560:	48e8 ffff 000c 	moveml %d0-%sp,%a0@(12)
400005a0:	4ce8 ffff 000c 	moveml %a0@(12),%d0-%sp
```

`%a7` is the sixteenth, at `12 + 15 * 4 = 72`, which is the slot create
writes. `%a0` is the ninth, at `12 + 8 * 4 = 44`, which is the slot the
handler patches after stashing `%a0` in scratch:

```
40000572:	2140 002c      	movel %d0,%a0@(44)
```

The largest offset touched is `+80`, a longword, so the structure runs to
byte 83. Rounded up to 4: **84**. ✅

**Way 2: the gaps between stock TCBs.**

The census in section 3.1 gives each task's TCB and stack. In eight of the
ten rows the two are adjacent, and in two of those eight the TCB is the
lower object, which bounds its size directly:

| row | tcb | stack | relation |
|---|---|---|---|
| 2 | `0x460bcc2c` | `0x460bc42c` + `0x800` | tcb = stack + size |
| 3 | `0x460d4f80` | `0x460d4780` + `0x800` | tcb = stack + size |
| 4 | `0x460d59d4` | `0x460d51d4` + `0x800` | tcb = stack + size |
| 5 | `0x460ddde4` | `0x460d9de4` + `0x4000` | tcb = stack + size |
| 6 | `0x460e0e38` | `0x460dee38` + `0x2000` | tcb = stack + size |
| 9 | `0x460ffd44` | `0x460fdd44` + `0x2000` | tcb = stack + size |
| 8 | `0x460fab80` | `0x460fabd4` | **stack = tcb + 0x54** |
| 10 | `0x46105508` | `0x4610555c` | **stack = tcb + 0x54** |

The six "tcb = stack + size" rows only prove the TCB begins where the stack
ends, which bounds the stack and not the TCB. They do confirm the stack
convention of section 3.2 a second time, from the linker's layout rather
than from the arithmetic. Rows 8 and 10 are the informative ones for size:
the stack is the next object above the TCB, so the TCB occupies `0x54`
bytes, **84**.

A third gap agrees, and it comes from the boot code rather than from a
create call. The boot's two TCBs are consecutive in one static area:

```
40000de0:	203c 46c7 ae30 	movel #1187491376,%d0
40000de6:	23c0 8000 68fc 	movel %d0,0x800068fc     | current = 0x46c7ae30
40000e34:	4879 46c7 ae84 	pea 0x46c7ae84            | main    = 0x46c7ae84
```

`0x46c7ae84 - 0x46c7ae30 = 0x54`, **84**, the same stride.
(`0x46c7ae30` is the pre multitasking context the first `trap #0` saves into.
It is never linked into a ready list, but the trap 0 handler writes its
register block, so it is a TCB sized object.) ✅

Both ways give 84 and there is nothing to prefer between them. `TCB_SIZE` is
**84**.

⚠️ Reserve it as 84 bytes aligned to 4, in the module's own data, and never
read or write inside it. Every field belongs to the kernel.

### 3.7 Interrupts, locks, and what else a task needs ✅

**Neither routine needs interrupts enabled, and neither needs a particular
SR.** ✅

`K_CREATE` contains no `movew %sr` in either direction. It inherits whatever
mask the caller has and leaves it alone. It is safe because it touches no
shared state: the four fields it writes are in the caller's own TCB, and
that TCB is on no list until start links it, so nothing else can see it.

`K_START` masks and restores around its own critical section:

```
40000642:	40c1           	movew %sr,%d1
40000644:	46fc 2700      	movew #9984,%sr
40000686:	46c1           	movew %d1,%sr
```

`0x2700` is interrupt mask 7 with supervisor set. Because start saves the
caller's SR and puts it back, it is safe at any interrupt level, including
inside a handler and including with interrupts already masked. ✅

**Neither routine takes a lock.** ✅ There is no call out of either one. The
interrupt mask is the mutual exclusion, and only start needs it.

🟡 Both routines execute `movew %sr,%dN` and `movew #imm,%sr`, which are
privileged on ColdFire, so both must be called in supervisor mode. Every
task in this firmware is supervisor, because the SR create puts in the first
frame is `0x2000` with the S bit set. This is not a constraint in practice.
**Falsifier:** a privilege violation exception, vector 8, from a call to
either address.

**Nothing else is needed to make a task run.** ✅ Stock's own sequence is the
oracle, and the storage task is the clearest one because it is created from
exactly one place, reached from exactly one place.

The task lead named `0x40061a94` for this. ❌ **`0x40061a94` is not a create
site.** It is the **entry of the task that does the creating**, the `sys`
task, row 7 of the census in section 3.1: created at `0x40040d2e` with TCB
`0x46c7bed8`, priority 1, and that entry address. Its first instruction is a
function prologue and there is no `jsr` to `0x400005fc` anywhere in it:

```
40061a94:	4e56 ffa4      	linkw %fp,#-92
40061a98:	48d7 3cfc      	moveml %d2-%d7/%a2-%a5,%sp@
```

The chain from there to the create is **one hop**, and every step is unique
✅:

```
40061b64:	4eb9 4001 dfbc 	jsr 0x4001dfbc
```

- `0x4001dfbc` has **exactly one caller in the image**: `0x40061b64` above.
  Checked three ways, as in section 3.1: `refs.sh 0x4001dfbc` gives one hit,
  the even offset scan for `jsr %pc@(d16)` and `bsr` gives zero, and the
  linear disassembly grep agrees.
- `0x40061b64` lies **inside** the `0x40061a94` function. The only `linkw`,
  `unlk`, `rts` or `rte` between the two addresses is the prologue's `linkw`
  at `0x40061a94` itself, so there is no function boundary in between.
- The storage TCB `0x460bcc2c` is named at **exactly two** places in the
  whole image, both inside `0x4001dfbc`: the `pea` at `0x4001dfe6` that
  hands it to create, and the `movel #imm,%sp@` at `0x4001dff6` that hands
  it to start.

So `sys` (entry `0x40061a94`) calls `0x4001dfbc`, which creates and starts
the storage task. Here is `0x4001dfbc` in full, with everything before and
after the pair:

```
4001dfbc:	4878 0400      	pea 0x400              | queue capacity
4001dfc0:	4879 460b b42c 	pea 0x460bb42c         | queue storage
4001dfc6:	42a7           	clrl %sp@-             | 0
4001dfc8:	4879 460b b3a0 	pea 0x460bb3a0         | queue object
4001dfce:	4eb9 4000 0bd4 	jsr 0x40000bd4         | queue init
4001dfd4:	4878 0800      	pea 0x800              | size
4001dfd8:	4879 460b c42c 	pea 0x460bc42c         | stack
4001dfde:	4878 0005      	pea 0x5                | prio
4001dfe2:	487a 0e4c      	pea %pc@(0x4001ee30)   | entry
4001dfe6:	4879 460b cc2c 	pea 0x460bcc2c         | tcb
4001dfec:	4eb9 4000 05fc 	jsr 0x400005fc         | CREATE
4001dff2:	4fef 0020      	lea %sp@(32),%sp
4001dff6:	2ebc 460b cc2c 	movel #1175178284,%sp@ | tcb again
4001dffc:	4eb9 4000 063c 	jsr 0x4000063c         | START
4001e002:	4878 0001      	pea 0x1
4001e006:	4879 46c8 ce20 	pea 0x46c8ce20
4001e00c:	4eb9 4000 0794 	jsr 0x40000794         | event init, an unrelated object
4001e012:	487a 0580      	pea %pc@(0x4001e594)
4001e016:	4878 00af      	pea 0xaf
4001e01a:	4eb9 4000 0d50 	jsr 0x40000d50         | install the vector 0xaf handler
```

**Between create and start there is not one call.** ✅ Only the stack
adjustment: the four queue arguments and the five create arguments are 36
bytes, `lea %sp@(32),%sp` pops 32 of them, and the last 4 byte slot is
overwritten in place with start's single argument. The arithmetic closes
exactly, so nothing is hidden inside it.

The queue init before create prepares an object the task will use. It is not
part of making the task runnable, and the other nine sites prove it: rows 1,
3, 4, 5, 6, 7, 8 and 10 call create with no preceding queue init at all.

There is **no name registration, no enable bit and no scheduler kick**. ✅
The set priority helper at `0x40000744` has **zero callers** in the image:
`refs.sh` returns 0 hits, the PC relative byte scan finds 0 calls, and so
does the linear disassembly grep. Priority is never changed after create
either. The get priority helper at `0x4000075c` has zero callers too.

**The full sequence Task 15 must emit, and nothing more:**

```asm
	pea	size
	pea	stack
	pea	prio
	pea	entry
	pea	tcb
	jsr	K_CREATE
	lea	%sp@(20),%sp
	pea	tcb
	jsr	K_START
	addq.l	#4,%sp
```

### 3.8 What create does not do ✅, and what follows for Task 15 🟡

**Create does not clear `+12` to `+71`.** ✅ It writes `+8`, `+72`, `+76` and
`+80` and nothing else, so the saved register block holds whatever was in
the TCB's memory. The scheduler restores `%d0` to `%a6` from it on the
task's first dispatch. That is harmless because the entry function reads
none of them, and loading a garbage value into an address register raises
nothing on ColdFire. Stock relies on this at all ten sites.
🟡 Zero the TCB anyway in Task 15, once, before the create. It costs 21
longwords and removes a class of question from any later trace.
**Falsifier:** a TCB zeroed before create behaving differently from one that
was not, which would mean some field outside the four is read.

**Neither routine checks whether the TCB is already in use.** ✅ `K_START`
unconditionally rewrites `tcb+0` and `tcb+4` and splices the TCB into the
ring. Called a second time on a TCB that is already linked, it links the same
node into the ring twice.
🟡 The result is a ring in which one node's forward and backward links no
longer agree, which the round robin walk at `0x4000057c` and the unlink at
`0x40000672` would both follow into inconsistency.
⚠️ **Task 15's `stems_task_create` must run at most once.** Guard it with a
flag in the module's own data, set after start returns, and test it before
the create. The STEM REC design already creates the task the first time the
action is selected, so the guard is the whole of the "first time".
**Falsifier:** a second create and start on a live TCB, under the port,
leaving `tcb+0` and `tcb+4` mutually consistent with every task still
reachable from its head.

### 3.9 Not measured under the port 🟡

Nothing in this section was run. No Octatrack project folder exists on this
machine, so `ot_emu` cannot be given `--card`, and this section is a static
reading of the image only.

Three checks will close it once a project folder exists.

The argument order and the initial stack pointer, from a real call:

```bash
out/emu/ot_emu --image out/raw/section_3_MAIN_OS.bin --card <card.img> \
  --set <SET> --project <PROJ> --watch-pc 0x400005fc
```

The priority 1 ready ring holding four tasks, by walking `tcb+0` from
`0x800068e0` after a create:

```bash
out/emu/ot_emu ... --watch-mem 0x800068e0,4
```

The TCB size, by watching for any access outside `tcb` to `tcb+83`:

```bash
out/emu/ot_emu ... --watch-mem <tcb>,88
```

Route A can do the first two today. `tools/emu/emu_rtos.py` already names
`CREATE = 0x400005fc`, `LIST_HEADS = 0x800068dc` and `TCB_A7 = 0x48`, and its
`EXPECTED_TASKS` table lists the same ten tasks with the same priorities,
stacks and sizes this section derived. That is an independent agreement on
the census, from a document written before it, but it is not a fresh
measurement.

**Falsifier for this whole section:** a create call whose fifth argument is
not a byte count, an initial stack pointer that is not
`stack + (size & ~3) - 12`, or a fourth task at priority 1 that the
scheduler never dispatches.

### 3.10 Interface

```asm
| Create one task. Five longword arguments, C order, so they are pushed
| right to left: pea size / pea stack / pea prio / pea entry / pea tcb /
| jsr K_CREATE, then the caller pops 20 bytes.
|   tcb    a TCB_SIZE block the caller owns, aligned to 4.
|   entry  the task function. It is entered with NO arguments, and its
|          return address is the kernel's task exit stub at 0x400006e4,
|          so returning from it deletes the task cleanly.
|   prio   0 to 7, higher number wins. NOT range checked.
|   stack  the LOWEST address of the stack. Must be 4 byte aligned: the
|          routine rounds size down to a multiple of 4 but never the base.
|   size   the stack length in BYTES. The initial stack pointer is
|          stack + (size & ~3) - 12, and the three longwords below the top
|          are the task's first exception frame.
| Always returns 1 in %d0. There is no failure path and nothing is
| validated. Touches no shared state, so it needs no interrupt mask and
| takes no lock.
.equ	K_CREATE,	0x400005fc

| Make a created task runnable. One longword argument, the same tcb:
| pea tcb / jsr K_START, then the caller pops 4 bytes. Links the TCB into
| the circular ready ring for its priority, sets tcb+76 to 1, and raises
| the top-priority pointer at 0x800068d8 if this priority now outranks it.
| Saves, masks to level 7, and restores the SR itself, so it is safe at any
| interrupt level and takes no lock. Does NOT force a context switch: the
| new task runs at the next scheduling point, even if it outranks its
| creator. Always returns 1 in %d0. Never call it twice on one TCB.
.equ	K_START,	0x4000063c

| Bytes of task control block to reserve, aligned to 4. Measured two ways
| that agree: the largest offset any kernel routine touches is +80, a
| longword, and two stock TCBs sit exactly 0x54 below their own stacks.
| Every byte belongs to the kernel. Reserve it and never read or write it.
.equ	TCB_SIZE,	84
```

## 4. Sleeping for N ticks

### 4.0 The answer, and the shape it is not ✅

**There is no `K_DELAY` in the kernel.** No kernel routine takes a tick
count, no task control block holds a tick counter, and there is no delay
list anywhere. The tick exists, it is 9.99 ms, and its only job is
preemption.

The image does contain exactly one timed wait, and it is the routine the
plan retracted. `0x40020c7c` **is** a sleep. It blocks the calling task,
the task leaves its ready ring, every other task runs, and a timer
interrupt wakes it. The plan read the lock and the hardware timer
correctly and drew the wrong conclusion from them.

❌ **Retract "`0x40020c7c` is not a sleep, it is a timed hardware wait"**
(the plan's section 6, and this task's brief). It is a timed hardware
wait **that blocks**. Section 4.4 is the whole routine and section 4.6 is
what happens to the caller.

Two things follow that change what Task 15 writes.

1. The argument is in **microseconds**, not ticks. `TASK_TICKS` keeps its
   name in the interface but carries 10,000, not 1.
2. The routine's timer object is **shared and single user**, and it is
   reset on every call. A second caller entering while a first is asleep
   destroys the first task's wake-up. Section 4.7 is the evidence, the
   exposure and what to do about it.

Term note. A **tick** here is one expiry of PIT0, the periodic interval
timer the kernel uses to preempt tasks. An **event object** is the two
longword structure the kernel's `0x40000818` blocks on and `0x40000968`
posts. Both are defined below.

### 4.1 The kernel has no tick counter and no delay list ✅

The kernel installs one handler for both the software trap and the tick:

```
400005cc:	2079 400b 9668 	moveal 0x400b9668,%a0
400005d2:	203c 4000 0550 	movel #1073743184,%d0
400005d8:	2140 02ac      	movel %d0,%a0@(684)
400005dc:	2140 0080      	movel %d0,%a0@(128)
```

`0x400b9668` holds the vector base register's value. `684 / 4 = 171` and
`128 / 4 = 32`, so vector 171 and vector 32 both get `0x40000550`. Vector
32 is `trap #0`. Vector 171 is PIT0's, and section 4.3 shows why.

That handler, in full, is a context switch and nothing else:

```
40000550:	46fc 2700      	movew #9984,%sr
40000554:	23c8 8000 6900 	movel %a0,0x80006900
4000055a:	2079 8000 68fc 	moveal 0x800068fc,%a0
40000560:	48e8 ffff 000c 	moveml %d0-%sp,%a0@(12)
40000566:	2039 8000 6900 	movel 0x80006900,%d0
4000056c:	2279 8000 68d8 	moveal 0x800068d8,%a1
40000572:	2140 002c      	movel %d0,%a0@(44)
40000576:	2051           	moveal %a1@,%a0
40000578:	717c f7ff      	mvsw #-2049,%d0
4000057c:	2050           	moveal %a0@,%a0
4000057e:	323c 0b3f      	movew #2879,%d1
40000582:	c1b9 fc04 c010 	andl %d0,0xfc04c010
40000588:	33c1 fc08 0000 	movew %d1,0xfc080000
4000058e:	23c8 8000 68fc 	movel %a0,0x800068fc
40000594:	2288           	movel %a0,%a1@
40000596:	203c a40c e000 	movel #-1542660096,%d0
4000059c:	4e7b 0002      	movec %d0,%cacr
400005a0:	4ce8 ffff 000c 	moveml %a0@(12),%d0-%sp
400005a6:	4e73           	rte
```

It saves the outgoing task's registers, takes the top priority ring's
head and steps to `head->next`, makes that the current task and the new
head, acknowledges the timer, invalidates the cache, and returns. It
decrements nothing, walks no list, and reads no per task counter. ✅

`0x40000582` clears bit 11 of `0xfc04c010`, which section 4.3 identifies
as INTC1's force register, and `0x40000588` writes PIT0's control
register. Both are acknowledgements.

**Nothing re-installs vector 171.** ✅ The set vector routine
`0x40000d50` takes the vector number as its first argument, and a byte
scan of the whole image finds **zero** occurrences of either way to push
171 as an immediate: `4878 00ab` for `pea 0xab`, and `2f3c 0000 00ab` for
`movel #0xab,%sp@-`. It finds exactly one `4878 00ac`, vector 172, which
is PIT1's and belongs to section 4.4. `moveq` cannot produce 171, because
it sign extends, so those two forms are the only immediate ones. Reading
the `pea` in front of each of the seventeen literal sites that reach
`0x40000d50` agrees: the numbers seen are `0x40`, `0x41`, `0x47`, `0x49`,
`0x4f`, `0x56`, `0x5a`, `0x5b`, `0x5c`, `0x60`, `0x61`, `0x62`, `0x64`,
`0x65`, `0xac`, `0xaf`, `0xb1`, `0xb6` and zero.

🟡 A vector number computed in a register rather than written as an
immediate would be invisible to both checks. **Falsifier:** a write watch
on the vector table entry for 171, at the vector base register's value
plus 684, firing after the kernel's own write at `0x400005d8`.

**No stock task sleeps on a tick.** ✅ Every stock task blocks on an
object, not on time. The key repeat task the brief named is the clearest
example. It creates a semaphore, then loops on it forever:

```
4005593c:	2f0b           	movel %a3,%sp@-
4005593e:	2f0a           	movel %a2,%sp@-
40055940:	42a7           	clrl %sp@-
40055942:	4879 46c7 e0e2 	pea 0x46c7e0e2
40055948:	4eb9 4000 0794 	jsr 0x40000794
4005594e:	508f           	addql #8,%sp
40055950:	47f9 4000 07a4 	lea 0x400007a4,%a3
40055956:	45f9 4001 387c 	lea 0x4001387c,%a2
4005595c:	4879 46c7 e0e2 	pea 0x46c7e0e2
40055962:	4e93           	jsr %a3@
40055964:	51fc           	tpf
40055966:	4e92           	jsr %a2@
40055968:	588f           	addql #4,%sp
4005596a:	60f0           	bras 0x4005595c
```

`0x40000794` initialises the object with count 0, `0x400007a4` blocks on
it, and `0x4001387c` does the work. There is no time in it.

**What posts that semaphore** ✅, because a task that never wakes would
prove nothing. A 32 bit scan of the image finds exactly three references
to `0x46c7e0e2`: the `pea` in the init above, the `pea` in the wait
above, and one more, at `0x40055cfe`. It is inside an interrupt handler:

```
40055cfe:	4879 46c7 e0e2 	pea 0x46c7e0e2
40055d04:	4eb9 4000 0888 	jsr 0x40000888
40055d0a:	7002           	moveq #2,%d0
40055d0c:	13c0 fc07 4003 	moveb %d0,0xfc074003
40055d12:	4cef 0703 0004 	moveml %sp@(4),%d0-%d1/%a0-%a2
40055d18:	4fef 0018      	lea %sp@(24),%sp
40055d1c:	4e73           	rte
```

`0x40000888` is the counting semaphore post. The handler begins at
`0x40055cb8`, and its install is the same self checking pattern as
section 4.3's:

```
40040478:	4879 4005 5cb8 	pea 0x40055cb8
4004047e:	4878 0061      	pea 0x61
40040482:	4eb9 4000 0d50 	jsr 0x40000d50
40040488:	7003           	moveq #3,%d0
4004048a:	13c0 fc04 8061 	moveb %d0,0xfc048061
40040490:	7021           	moveq #33,%d0
```

`0x61 = 97 = 64 + 33`, and `0xfc048061` is INTC0's ICR33, set to level 3.
So **the key repeat task is woken by INTC0 source 33, at interrupt level
3**, and its period is that interrupt's, not the kernel's tick. ✅

🟡 The handler looks periodic rather than one shot: it runs a countdown
at `0x400c0cf0`, sending two queue messages and reloading the count with
2 each time it reaches zero, and it acknowledges a peripheral at
`0xfc074003` on the way out. **Falsifier:** a program counter watch on
`0x40055cb8` under the port showing it entered once and never again.

⚠️ This gives STEM REC nothing to reuse. The semaphore belongs to the key
layer, and posting it would inject key repeats.

**The census of blocking calls from outside the kernel** is short and it
says the same thing everywhere.

❌ **Retract the first version's counts, "three, ten and five, eighteen
in all".** They counted only `jsr` to a literal address and missed every
call made through an address register. The method that catches those:
grep the linear disassembly for each primitive's address, which finds the
`jsr` sites and also the `lea` and `moveal` instructions that load it into
a register; then, for each register load, scan forward in the same
function for `jsr %aN@` until that register is reloaded.

| primitive | direct `jsr` | register loads | calls through them | total |
|---|---|---|---|---|
| `0x400007a4` | 0 | 3 | 4 | **4** |
| `0x40000818` | 10 | 0 | 0 | **10** |
| `0x40000d00` | 4 | 2 | 2 | **6** |

The register loads and what they carry, all outside the kernel:

| load | calls |
|---|---|
| `0x4001ee42`, `lea 0x400007a4,%a4` | `0x4001f076`, `0x4001f170` |
| `0x4005592a`, `lea 0x400007a4,%a2` | `0x40055936` |
| `0x40055950`, `lea 0x400007a4,%a3` | `0x40055962`, quoted above |
| `0x4000554c`, `lea 0x40000d00,%a3` | `0x4000555e` |
| `0x400921cc`, `lea 0x40000d00,%a4` | `0x400921de` |

Two references are inside the kernel and are not calls from a task:
`jsr %pc@(0x400007a4)` at `0x40000c0e`, in the kernel's own queue helper
`0x40000c00`, and `lea %pc@(0x40000818),%a3` at `0x40000d10`, inside
`0x40000d00` itself.

**Twenty calls, and every one of them pushes exactly one longword, an
object address.** ✅ Fourteen push it with `pea` on a literal. The other
six, all in `0x40015xxx`, load a pointer from memory first, with
`movel %a2@(10),%d0` or `movel 0x46c8c598,%d0`, and push that.
**None passes a time.**

### 4.2 The three blocking primitives, and their objects ✅

None of the three takes a timeout. That is the finding, and it is why
step 1 of this task ends here rather than in a convention.

**`0x400007a4`, a counting semaphore wait.** One longword argument, the
object. Section 4.1 quotes a call.

```
400007a4:	226f 0004      	moveal %sp@(4),%a1
400007a8:	40c1           	movew %sr,%d1
400007aa:	46fc 2700      	movew #9984,%sr
400007ae:	2011           	movel %a1@,%d0
400007b0:	6f06           	bles 0x400007b8
400007b2:	5380           	subql #1,%d0
400007b4:	2280           	movel %d0,%a1@
400007b6:	605a           	bras 0x40000812
```

A count above zero is decremented and the caller returns. A count of zero
or less blocks. No argument carries a limit.

**`0x40000818`, an event wait.** One longword argument, the object. This
is the one the timed wait uses.

```
40000818:	226f 0004      	moveal %sp@(4),%a1
4000081c:	40c0           	movew %sr,%d0
4000081e:	46fc 2700      	movew #9984,%sr
40000822:	4a91           	tstl %a1@
40000824:	6f04           	bles 0x4000082a
40000826:	4291           	clrl %a1@
40000828:	605a           	bras 0x40000884
4000082a:	2079 8000 68fc 	moveal 0x800068fc,%a0
40000830:	2348 0004      	movel %a0,%a1@(4)
```

The flag is **latched**. A set flag is consumed and the caller does not
block, so a post that arrives before the wait is not lost. A clear flag
parks the current task control block in `obj+4` and blocks. `obj+4` is
**one slot, not a list**, so an object holds exactly one waiter and a
second waiter overwrites the first. ✅

**`0x40000d00`, a queue receive.** **One longword**, the object. It loops
on `0x40000818` against `obj+8` while the queue count at `obj+4` is zero,
then pops one entry and returns it in `%d0`.

```
40000d00:	4fef fff4      	lea %sp@(-12),%sp
40000d04:	48d7 0c04      	moveml %d2/%a2-%a3,%sp@
40000d08:	246f 0010      	moveal %sp@(16),%a2
40000d0c:	240a           	movel %a2,%d2
40000d0e:	5082           	addql #8,%d2
40000d10:	47fa fb06      	lea %pc@(0x40000818),%a3
40000d14:	6006           	bras 0x40000d1c
40000d16:	2f02           	movel %d2,%sp@-
40000d18:	4e93           	jsr %a3@
40000d1a:	588f           	addql #4,%sp
40000d1c:	4aaa 0004      	tstl %a2@(4)
40000d20:	67f4           	beqs 0x40000d16
```

❌ **Retract "three longwords", which the first version of this section
said.** The routine reserves 12 bytes and saves three registers into them
before it reads an argument, so `%sp@(0)` through `%sp@(11)` hold `%d2`,
`%a2` and `%a3`, `%sp@(12)` is the return address, and `%sp@(16)` is
**the first and only argument**. The exit is symmetric and confirms the
frame:

```
40000d44:	4cd7 0c04      	moveml %sp@,%d2/%a2-%a3
40000d48:	4fef 000c      	lea %sp@(12),%sp
40000d4c:	4e75           	rts
```

Everything else the routine touches is a **field of the object**, not a
stack slot: `obj+4` the count, `obj+8` the event it blocks on, `obj+16`
the index mask, `obj+20` the buffer and `obj+28` the read index.

```
40000d28:	222a 001c      	movel %a2@(28),%d1
40000d2c:	206a 0014      	moveal %a2@(20),%a0
40000d30:	2030 1c00      	movel %a0@(0,%d1:l:4),%d0
40000d34:	5281           	addql #1,%d1
40000d36:	c2aa 0010      	andl %a2@(16),%d1
40000d3a:	2541 001c      	movel %d1,%a2@(28)
40000d3e:	53aa 0004      	subql #1,%a2@(4)
```

The callers agree. Each of the four direct ones pushes one `pea`, takes
the entry out of `%d0`, and pops four bytes:

```
4009204a:	4879 460d 17ee 	pea 0x460d17ee
40092050:	4eb9 4000 0d00 	jsr 0x40000d00
40092056:	2440           	moveal %d0,%a2
40092058:	588f           	addql #4,%sp
```

The two that call through a register, `0x4000555e` and `0x400921de`, push
one longword too and fold the four byte pop into a later multi-argument
`lea %sp@(n),%sp`.

It inherits `0x40000818`'s behaviour and adds no time.

**Object sizes and their initialisers**, for a module that wants a private
one. ✅

| object | bytes | initialiser | arguments |
|---|---|---|---|
| event or counting semaphore | 8 | `0x40000794` | `obj`, initial count |
| mutex | 12 | `0x400009e4` | `obj` |
| queue | 32 | `0x40000bd4` | `obj`, one unused slot, buffer, capacity |

The event initialiser is four instructions, which fixes the layout:

```
40000794:	206f 0004      	moveal %sp@(4),%a0
40000798:	20af 0008      	movel %sp@(8),%a0@
4000079c:	42a8 0004      	clrl %a0@(4)
400007a0:	4e75           	rts
```

`obj+0` is the count or flag, `obj+4` is the single waiter. Eight bytes.
A statically zeroed eight byte block is already a valid empty event
object, so `.long 0, 0` in the module's own data needs no initialiser
call at all. ✅

⚠️ **A private object that nothing posts is a permanent block, not a
timeout.** The brief asks for that sequence if a timeout were the only
timed wait available. It is not, and the sequence has no use here.
Written down so nobody reaches for it: `pea obj` then `jsr 0x40000818` on
an object no code posts parks the task forever, and `0x400006e4`, the
task exit path, is the only way back.

### 4.3 The tick, from its own register writes ✅ and 🟡

PIT0 is programmed once, in the kernel's timer init:

```
400005a8:	2f02           	movel %d2,%sp@-
400005aa:	43f9 fc08 0000 	lea 0xfc080000,%a1
400005b0:	32bc 0b36      	movew #2870,%a1@
400005b4:	2039 400b 9654 	movel 0x400b9654,%d0
400005ba:	243c 0006 4000 	movel #409600,%d2
400005c0:	4c42 0000      	remul %d2,%d0,%d0
400005c4:	5380           	subql #1,%d0
400005c6:	33c0 fc08 0002 	movew %d0,0xfc080002
```

⚠️ `4c42 0000` is **`divu.l %d2,%d0`**, an unsigned 32 bit divide leaving
the quotient in `%d0`. objdump prints it as `remul`, which is the 64 bit
form's name. `m68k-elf-as -mcpu=5407` assembles `divu.l %d2,%d0` to those
exact four bytes, which is the check the preamble asks for.

**The register values, read off those lines.** ✅

| register | value | meaning |
|---|---|---|
| PCSR, `0xfc080000` | `0x0b36` | PRE = 11, OVW = 1, RLD = 1, PIF written to clear it, EN = 0 |
| PMR, `0xfc080002` | `0x400b9654 / 409600 - 1` | the modulus |

The enable arrives at the end of the same routine, together with the
interrupt wiring:

```
400005e0:	7201           	moveq #1,%d1
400005e2:	13c1 fc04 c06b 	moveb %d1,0xfc04c06b
400005e8:	742b           	moveq #43,%d2
400005ea:	13c2 fc04 c01d 	moveb %d2,0xfc04c01d
400005f0:	3011           	movew %a1@,%d0
400005f2:	7209           	moveq #9,%d1
400005f4:	8081           	orl %d1,%d0
400005f6:	3280           	movew %d0,%a1@
```

`0x0009` sets EN and PIE. The two byte writes name the interrupt, and
they are self checking. ✅

- `0xfc04c000` is INTC1, not INTC0. The UART driver settles it: it writes
  `0xfc04805c` and `0xfc04801d` for vector `0x5c`, and `0x5c = 92 =
  64 + 28`, so `0xfc048000` is INTC0 with vectors at 64 plus the source.
  INTC1's vectors start at 128.
- `0xfc04c06b` is INTC1's ICR43, at `0x40 + 43`. It is set to 1, which is
  interrupt level 1.
- `0xfc04c01d` is INTC1's CIMR, the clear interrupt mask register, and it
  is written with 43, which unmasks source 43.
- `128 + 43 = 171`, the vector section 4.1 shows the switcher installed
  at.

So **the tick is INTC1 source 43, level 1, vector 171, and PIT0 drives
it.** ✅ Each of those four numbers is confirmed by another.

The same reading explains the switcher's `andl %d0,0xfc04c010` at
`0x40000582`. `0xfc04c010` is INTC1's INTFRCH, which forces sources 32 to
63, and bit 11 is source 43. So **the kernel's "reschedule now" is a
forged PIT0 interrupt**, and the switcher clears it on the way out. ✅
Section 4.6 uses that.

**The modulus and the period.** `0x400b9654` holds the CPU clock. The boot
computes it:

```
40000418:	2439 fc0c 4000 	movel 0xfc0c4000,%d2
4000041e:	7018           	moveq #24,%d0
40000420:	e0aa           	lsrl %d0,%d2
40000422:	203c 00b7 1b00 	movel #12000000,%d0
40000428:	4c00 2800      	mulsl %d0,%d2
4000042c:	23c2 400b 9654 	movel %d2,0x400b9654
```

and a later check refuses to run on anything else. When the comparison
fails it falls through to two error calls and then to `0x4000fa8c`, a
`bras` to itself:

```
4000fa72:	203c 0fbc 5200 	movel #264000000,%d0
4000fa78:	b0b9 400b 9654 	cmpl 0x400b9654,%d0
4000fa7e:	670e           	beqs 0x4000fa8e
```

So the CPU clock is **264,000,000**. ✅

The internal bus clock is half of that, and the firmware says so twice.
The UART baud setup halves the stored value before dividing by 32 times
the baud rate, which is the ColdFire UART's own formula against the bus
clock:

```
40010d3a:	2239 400b 9654 	movel 0x400b9654,%d1
40010d40:	e289           	lsrl #1,%d1
40010d42:	eb88           	lsll #5,%d0
40010d44:	4c40 1001      	remul %d0,%d1,%d1
```

and two sites write the literal 132,000,000 into a peripheral's clock
rate word, for example

```
40040438:	203c 07de 2900 	movel #132000000,%d0
4004043e:	23c0 fc07 8004 	movel %d0,0xfc078004
```

`264,000,000` appears in the image only in the boot's own arithmetic and
that guard. **The internal bus clock is 132 MHz.** ✅ This agrees with
`CHIP.md`, which derives it the same way.

The arithmetic, then:

```
PMR   = 264,000,000 / 409,600 - 1 = 644 - 1 = 643      (unsigned, truncating)
tick  = (PMR + 1) * 2^PRE / f_bus = 644 * 2048 / 132,000,000
      = 1,318,912 / 132,000,000 = 9.9918 ms, a 100.08 Hz tick
```

🟡 **The period in milliseconds rests on two facts that are not in the
image**: that PIT0 counts the internal bus clock, and that the PCSR
prescaler field divides by 2^PRE rather than by 2^(PRE+1). Both come from
the MCF54455 reference manual, by way of `CHIP.md`. Every candidate
reading is a power of two away from every other, so **no constant in the
firmware can break the tie**, and three attempts to break it failed:

- PIT2, which the firmware programs at `0x400630a0` with `PCSR = 0x0533`,
  PRE 5, and `PMR = 4124`. Under the reading above, `4125 * 32 = 132,000`
  is exactly one millisecond of bus clock. Exact, and exact under the
  alternatives too, at 0.5 ms and at 2 ms.
- The delay routine's own unit, section 4.5. Under the reading above it
  is exactly 1 µs. Under the alternatives it is 0.5 µs or 2 µs.
- The 15,000 threshold of section 4.5, which sits just under the fine
  timer's 16 bit overflow. It fits every reading, because it scales with
  the unit.

**Falsifier:** a hardware measurement of the unit's tick rate, or a PIT
clock source on this part that is not the internal bus.

⚠️ **Two documents in this repository disagree today, and neither has
been corrected.** `RTOS_FORK.md` section 3 says **5.0 ms**, marked ✅,
which is this arithmetic against the CPU clock. `CHIP.md` says **9.99
ms**, marked 🟡 and flagged there as "not acted on and not yet reviewed".
This section is a third derivation and it lands on `CHIP.md`'s number.
Nothing here edits either file.

**Why STEM REC survives the ambiguity.** The whole family scales
together. The argument this section hands Task 15 is 10,000, and it
produces a sleep of 5 ms, 10 ms or 20 ms depending on which reading is
right. A 64 KB chunk fills every 371 ms at 176,400 B/s, so all three are
ample and none is expensive. ✅ Task 15's loop does not depend on
resolving it.

### 4.4 K_DELAY, the whole routine ✅

`0x40020c7c`. Two longword arguments, C order, and `%d2` is pushed first,
so the arguments sit at `%sp@(8)` and `%sp@(12)`.

```
40020c7c:	2f02           	movel %d2,%sp@-
40020c7e:	242f 0008      	movel %sp@(8),%d2
40020c82:	4aaf 000c      	tstl %sp@(12)
40020c86:	661a           	bnes 0x40020ca2
40020c88:	4879 460b cda8 	pea 0x460bcda8
40020c8e:	4eb9 4000 0a94 	jsr 0x40000a94
40020c94:	588f           	addql #4,%sp
40020c96:	7201           	moveq #1,%d1
40020c98:	b280           	cmpl %d0,%d1
40020c9a:	6714           	beqs 0x40020cb0
40020c9c:	70ff           	moveq #-1,%d0
40020c9e:	6000 0094      	braw 0x40020d34
40020ca2:	4879 460b cda8 	pea 0x460bcda8
40020ca8:	4eb9 4000 09f4 	jsr 0x400009f4
40020cae:	588f           	addql #4,%sp
40020cb0:	4eba ff8a      	jsr %pc@(0x40020c3c)
40020cb4:	0c82 0000 3a98 	cmpil #15000,%d2
40020cba:	6324           	blss 0x40020ce0
40020cbc:	303c 0b3a      	movew #2874,%d0
40020cc0:	33c0 fc08 4000 	movew %d0,0xfc084000
40020cc6:	223c 0000 07de 	movel #2014,%d1
40020ccc:	4c01 2800      	mulsl %d1,%d2
40020cd0:	2002           	movel %d2,%d0
40020cd2:	0680 0000 7a11 	addil #31249,%d0
40020cd8:	243c 0000 7a12 	movel #31250,%d2
40020cde:	601e           	bras 0x40020cfe
40020ce0:	303c 053a      	movew #1338,%d0
40020ce4:	33c0 fc08 4000 	movew %d0,0xfc084000
40020cea:	223c 0000 019c 	movel #412,%d1
40020cf0:	4c01 2800      	mulsl %d1,%d2
40020cf4:	2002           	movel %d2,%d0
40020cf6:	0680 0000 0063 	addil #99,%d0
40020cfc:	7464           	moveq #100,%d2
40020cfe:	4c42 0000      	remul %d2,%d0,%d0
40020d02:	33c0 fc08 4002 	movew %d0,0xfc084002
40020d08:	3039 fc08 4000 	movew 0xfc084000,%d0
40020d0e:	7201           	moveq #1,%d1
40020d10:	8081           	orl %d1,%d0
40020d12:	33c0 fc08 4000 	movew %d0,0xfc084000
40020d18:	4879 460b cdb4 	pea 0x460bcdb4
40020d1e:	4eb9 4000 0818 	jsr 0x40000818
40020d24:	4879 460b cda8 	pea 0x460bcda8
40020d2a:	4eb9 4000 0ab4 	jsr 0x40000ab4
40020d30:	4280           	clrl %d0
40020d32:	508f           	addql #8,%sp
40020d34:	241f           	movel %sp@+,%d2
40020d36:	4e75           	rts
```

**The arguments.** ✅

| slot | name | meaning |
|---|---|---|
| `%sp@(8)` | `us` | how long to sleep, in microseconds. See section 4.5. |
| `%sp@(12)` | `wait` | 0 tries the shared timer's mutex and gives up; anything else waits for it. |

A call is two `pea` instructions in reverse order, then `jsr`, then an
8 byte stack adjustment. Both stock call sites have that shape. The one
that reads most like Task 15's loop is

```
4008046a:	42a7           	clrl %sp@-
4008046c:	4878 2710      	pea 0x2710
40080470:	4e92           	jsr %a2@
40080472:	508f           	addql #8,%sp
```

`%a2` was loaded with `0x40020c7c` at `0x40080462`. `0x2710` is 10,000,
the `us` argument, and the zero pushed before it is `wait`.

**The return value.** ✅ `moveq #-1,%d0` at `0x40020c9c` is the only other
exit, and it is reached only when `wait` was 0 and the mutex was held.
Otherwise `clrl %d0` at `0x40020d30` runs. So **0 means the sleep
happened and -1 means it did not**. There is no other failure path, and
nothing else is validated: not the range of `us`, and not its sign.

**`%d2` is saved and restored. Everything else is caller saved.** `%d0`
carries the result, and `%d1`, `%a0` and `%a1` are clobbered by the
routine and by the kernel calls it makes.

**The re-initialiser at `0x40020cb0`.** ✅ Every call runs it, and it is
not guarded.

```
40020c3c:	4879 460b cda8 	pea 0x460bcda8
40020c42:	4eb9 4000 09e4 	jsr 0x400009e4
40020c48:	42a7           	clrl %sp@-
40020c4a:	4879 460b cdb4 	pea 0x460bcdb4
40020c50:	4eb9 4000 0794 	jsr 0x40000794
40020c56:	487a 00e0      	pea %pc@(0x40020d38)
40020c5a:	4878 00ac      	pea 0xac
40020c5e:	4eb9 4000 0d50 	jsr 0x40000d50
40020c64:	7002           	moveq #2,%d0
40020c66:	13c0 fc04 c06c 	moveb %d0,0xfc04c06c
40020c6c:	702c           	moveq #44,%d0
40020c6e:	13c0 fc04 c01d 	moveb %d0,0xfc04c01d
40020c74:	4fef 0014      	lea %sp@(20),%sp
40020c78:	4e75           	rts
```

It clears the mutex at `0x460bcda8`, clears the event object at
`0x460bcdb4`, installs `0x40020d38` at vector `0xac`, sets INTC1's ICR44
to level 2 and unmasks source 44. By the arithmetic of section 4.3,
`0xac = 172 = 128 + 44`, so **PIT1 is INTC1 source 44 at level 2**. ✅

Clearing the event object before arming PIT1 is why a stale expiry cannot
make the next sleep return early. Clearing the mutex is section 4.7's
problem.

**The interrupt handler.** ✅

```
40020d38:	4fef fff0      	lea %sp@(-16),%sp
40020d3c:	48d7 0303      	moveml %d0-%d1/%a0-%a1,%sp@
40020d40:	41f9 fc08 4000 	lea 0xfc084000,%a0
40020d46:	3010           	movew %a0@,%d0
40020d48:	7204           	moveq #4,%d1
40020d4a:	8081           	orl %d1,%d0
40020d4c:	3080           	movew %d0,%a0@
40020d4e:	3010           	movew %a0@,%d0
40020d50:	72fe           	moveq #-2,%d1
40020d52:	c081           	andl %d1,%d0
40020d54:	3080           	movew %d0,%a0@
40020d56:	4879 460b cdb4 	pea 0x460bcdb4
40020d5c:	4eb9 4000 0968 	jsr 0x40000968
40020d62:	4cef 0303 0004 	moveml %sp@(4),%d0-%d1/%a0-%a1
40020d68:	4fef 0014      	lea %sp@(20),%sp
40020d6c:	4e73           	rte
```

Set PIF to clear it, clear EN to stop the timer, post the event. The
restore reads from `%sp@(4)` and pops 20 rather than 16 because the `pea`
at `0x40020d56` is still on the stack. So **one call means exactly one
interrupt**, even though RLD is set in PCSR. ✅

### 4.5 The unit is microseconds ✅

Two paths, chosen by `cmpil #15000,%d2` and `blss`, which is an unsigned
"lower or same". Values up to and including 15,000 take the fine path.

| | fine, `us <= 15000` | coarse, `us > 15000` |
|---|---|---|
| PCSR | `0x053a`, PRE 5, prescaler 32 | `0x0b3a`, PRE 11, prescaler 2048 |
| counter clock | 132 MHz / 32 = 4,125,000 Hz | 132 MHz / 2048 = 64,453.125 Hz |
| PMR | `(us * 412 + 99) / 100` | `(us * 2014 + 31249) / 31250` |
| counts per µs, exact | 4.125 | 0.064453125 |
| counts per µs, as coded | 4.12 | 0.0644480 |
| error | 0.12 % short | 0.008 % short |

Both factors are the counts per microsecond of their own prescaler, to
within the rounding the integer arithmetic forces. **The argument is
microseconds.** ✅ The `+ 99 / 100` and `+ 31249 / 31250` are round-up
divides, so the routine never rounds a request down to nothing.

The threshold is where the fine timer would overflow. PMR is 16 bits,
written with `movew`, and `15000 * 4.12 = 61,800`, just under 65,535. The
next thousand microseconds would pass it. ✅

Worked values, for the record:

| `us` | path | PMR | actual sleep |
|---|---|---|---|
| 25 | fine | 103 | 25.21 µs |
| 10,000 | fine | 41,200 | 9.988 ms |
| 100,000 | coarse | 6,445 | 100.01 ms |

⚠️ **The upper limit is about one second.** PMR passes the 16 bit
write's range at 1,016,850 µs, and `mulsl` is a signed 32 bit multiply,
so `us * 2014` overflows a positive 32 bit result at 1,066,278 and up.
Neither is checked, and the first one binds. Stay under 1,000,000.

⚠️ **`us = 0` is not "return at once".** It takes the fine path, PMR
becomes 0, and the caller still blocks for one counter period, about
0.24 µs, plus a full context switch each way.

### 4.6 What happens to the calling task, and what wakes it ✅

**Which queue it joins.** `0x40000818`, called at `0x40020d1e`, does five
things under interrupt mask 7:

```
4000082a:	2079 8000 68fc 	moveal 0x800068fc,%a0
40000830:	2348 0004      	movel %a0,%a1@(4)
```

```
40000878:	2079 8000 68fc 	moveal 0x800068fc,%a0
4000087e:	42a8 004c      	clrl %a0@(76)
40000882:	4e40           	trap #0
```

1. Parks the current task control block's address in the event object's
   single waiter slot, `0x460bcdb4 + 4`.
2. Unlinks the task control block from its priority's ready ring, which
   is the splice of section 3.5 run in reverse.
3. If that emptied the ring, clears the ring head and walks the top
   priority pointer at `0x800068d8` down to the next non empty head.
4. Clears `tcb+76`, the ready flag.
5. Executes `trap #0`, which is the switcher of section 4.1.

So the task is **on no ready ring while it sleeps**, and every other task,
at every priority, runs normally. ✅ That is the property the plan
doubted.

**What wakes it.** The handler's post, `0x40000968`:

```
40000968:	2f0a           	movel %a2,%sp@-
4000096a:	206f 0008      	moveal %sp@(8),%a0
4000096e:	40c1           	movew %sr,%d1
40000970:	46fc 2700      	movew #9984,%sr
40000974:	7001           	moveq #1,%d0
40000976:	2080           	movel %d0,%a0@
40000978:	4aa8 0004      	tstl %a0@(4)
4000097c:	6758           	beqs 0x400009d6
4000097e:	4290           	clrl %a0@
40000980:	2468 0004      	moveal %a0@(4),%a2
40000984:	42a8 0004      	clrl %a0@(4)
40000988:	7001           	moveq #1,%d0
4000098a:	2540 004c      	movel %d0,%a2@(76)
```

then the ring splice, then

```
400009c6:	2039 fc04 c010 	movel 0xfc04c010,%d0
400009cc:	08c0 000b      	bset #11,%d0
400009d0:	23c0 fc04 c010 	movel %d0,0xfc04c010
```

It sets the flag, relinks the sleeper into its ready ring, raises
`0x800068d8` if that ring now outranks the current top, and forges the
source 43 interrupt of section 4.3.

**The wake latency is not one tick. It is immediate.** ✅ The forced
interrupt is level 1. PIT1's handler runs at level 2, and its `rte`
restores the interrupted context's mask, so the forced interrupt is taken
at the next instruction boundary that allows it, and the switcher runs.
The sleeper is dispatched as soon as no higher priority task is ready.
Nothing waits for PIT0 to expire.

⚠️ For Task 15. The writer task is priority 1 and shares its ring with
three stock tasks. It wakes at once but is dispatched round robin within
priority 1, and it yields to priorities 2 through 7. Treat the sleep as
"at least `us`, and then when the machine is free", never as a deadline.

**Interrupt state and locks.** ✅

- `0x40020c7c` saves and restores no SR of its own. The kernel routines it
  calls, `0x40000818` and the mutex pair, each mask to level 7 and restore
  the caller's mask, so the routine is safe at any interrupt level the
  caller holds.
- 🟡 It must be called in **supervisor mode**, because those kernel
  routines execute `movew %sr,%dn`, which is privileged on ColdFire. Every
  task in this firmware is supervisor: the SR `K_CREATE` puts in the first
  frame is `0x2000`. **Falsifier:** a privilege violation, vector 8, from
  the call.
- ⚠️ **Do not call it with the interrupt mask above level 2.** PIT1
  interrupts at level 2. A caller that masked higher and is the only
  runnable task would never be woken. A task created by `K_CREATE` starts
  at SR `0x2000`, level 0, so this needs no action unless Task 15 masks
  deliberately.
- ❌ **It is not callable from an interrupt handler.** It blocks the
  current task, and inside a handler the current task is whoever was
  interrupted.

### 4.7 The shared timer is single user, and that is the real risk ⚠️ ✅

`0x40020cb0` re-runs the initialiser on every call, and the initialiser
clears the event object's waiter slot:

```
40000794:	206f 0004      	moveal %sp@(4),%a0
40000798:	20af 0008      	movel %sp@(8),%a0@
4000079c:	42a8 0004      	clrl %a0@(4)
```

Two consequences, both read off the code above. ✅

**1. The mutex does not exclude anything.** The initialiser calls
`0x400009e4` on `0x460bcda8`, which clears `obj+0`, and `obj+0` is the
mutex's owner field. So the owner is cleared immediately after being
taken, the next caller's try-lock at `0x40000a94` always succeeds, and the
unlock at `0x40020d2a` finds it is not the owner and does nothing. The
`wait` argument is therefore close to dead: `wait = 0` will not return -1
in practice.

**2. A second caller destroys the first caller's wake-up.** The sleeping
task's address lives only in `0x460bcdb4 + 4`. The second call clears that
slot before arming PIT1 for its own interval. When PIT1 expires,
`0x40000968` wakes whoever is in the slot, which is the second caller.
**The first task is left unlinked from every ready ring with its ready
flag clear, and nothing will ever relink it.** It is gone until the unit
restarts.

**Who else calls it, and when.** Only two sites load the address. ✅

| site | call | context |
|---|---|---|
| `0x40015ff4` | `us` 25, `wait` 1 | the CompactFlash reset path. It writes `0x90000024`, the ATA device control register in the FlexBus task file window, around the delay. Reached from `0x40061692`, a card probe that calls it twice and then reads the drive's identity. |
| `0x4008046a` | `us` 10,000, `wait` 0 | the OS upgrade path. It polls a work semaphore's count until a queue drains. The routine at `0x40080434` is reached only from `0x4008075a` and `0x4008077e`, and it passes the string `OS UPGRADE`, at `0x400b5839`, at `0x400804b4`. |

```
40015fe4:	4200           	clrb %d0
40015fe6:	13c0 9000 0024 	moveb %d0,0x90000024
40015fec:	4878 0001      	pea 0x1
40015ff0:	4878 0019      	pea 0x19
40015ff4:	4e90           	jsr %a0@
```

**The steady state card path does not use this timer.** ✅ The sector read
and write routines are in `0x40014xxx`, and neither of the two sites that
load `0x40020c7c` is among them. So a stem recording that is writing to
the card is not racing the driver on every sector.

**The exposure, stated plainly.** 🟡 A writer task that sleeps 10 ms
between chunks is asleep on this object almost all of the time. The two
stock callers are a card probe, which happens on insert or mount, and an
OS upgrade. Both are already incompatible with a recording in progress: a
card leaving mid-recording ends the recording anyway, and an OS upgrade is
a modal operation. So the collision is unlikely, and its consequence when
it happens is a permanently blocked writer task, not corrupted audio.
**Falsifier:** a program counter watch on `0x40020c7c` under the port
during a recording, showing an entry from any task other than the writer.

⚠️ **If Task 15 wants no exposure at all**, the clean alternative is a
private timer. PIT3 at `0xfc08c000` has **zero references anywhere in the
image**, from a 32 bit scan of the whole file, so it is free. The module
would program it exactly as section 4.4's routine programs PIT1, install
its own handler on its own vector, and post its own eight byte event
object. 🟡 PIT3's interrupt source and vector are inferred from PIT0 at 43
and PIT1 at 44, so 45 and 46 for PIT2 and PIT3, giving vector 174.
**Falsifier:** installing at vector 174 and never seeing the handler run.
That is more code than this proof of concept needs, and it is recorded
here so that using the shared timer is a choice rather than an oversight.

### 4.8 A bare yield, if the loop ever wants one ✅

`trap #0` from a task is a cooperative yield. Vector 32 is the switcher of
section 4.1, which advances the top priority ring by one and dispatches
`head->next`. The caller stays linked and ready, so it runs again on the
ring's next pass.

```
40000730:	46c2           	movew %d2,%sr
40000732:	4e40           	trap #0
```

Every `trap #0` in the image is inside the kernel, at `0x400006e0`,
`0x40000732`, `0x40000810`, `0x40000882`, `0x40000a78`, `0x40000b40`,
`0x40000ba8` and `0x40000e46`. No application code uses it directly, so a
module that does is doing something stock does not. ✅

⚠️ A loop of `trap #0` never idles the processor. It is a spin at
priority 1 that yields to priorities 2 through 7 and starves priority 0.
Use `K_DELAY`. This is here because the switcher's behaviour is worth
recording, not as a recommendation.

### 4.9 Not measured under the port 🟡

Nothing in this section was run. No Octatrack project folder exists on
this machine, so `ot_emu` cannot be given `--card`.

Three checks will close it.

The sleep really blocks, and for the right length, by watching the
routine's entry and exit and the timer's modulus:

```bash
out/emu/ot_emu --image out/raw/section_3_MAIN_OS.bin --card <card.img> \
  --set <SET> --project <PROJ> --watch-pc 0x40020c7c --watch-mem 0xfc084002,2
```

The tick period, which is the open question of section 4.3, by counting
entries to `0x40000550` from vector 171 over a known number of audio
frames:

```bash
out/emu/ot_emu ... --dsp-pcwatch --watch-pc 0x40000550
```

⚠️ That second one is **structurally blind** in the way `CLAUDE.md` warns
about. The port's PIT clock is a flag, `--pit-clock`, and both emulators
share it, so the port can only report the number it was told. It cannot
settle section 4.3. Only hardware can, by timing something the tick paces.

Whether any task other than the writer enters `0x40020c7c` during a
recording, which is section 4.7's falsifier, needs the same run with a
recording actually happening, so it waits for Phase D.

**Falsifier for this whole section:** a call to `0x40020c7c` that returns
without the caller having left its ready ring, an argument that is not
microseconds, or a wake that waits for the next PIT0 expiry rather than
arriving through the forced source 43.

### 4.10 Interface

```asm
| Sleep, and let every other task run. The only timed wait in the image.
| Two longword arguments, C order, so they are pushed right to left:
| pea wait / pea us / jsr K_DELAY, then the caller pops 8 bytes.
|   us    how long to sleep, in MICROSECONDS. Not in kernel ticks. Keep it
|         under 1,000,000: nothing is range checked and the routine's
|         multiply is a signed 32 bit one. Values above 15,000 switch to a
|         coarser prescaler inside the routine, automatically.
|   wait  0 gives up and returns -1 if the shared timer is busy, anything
|         else waits for it. Use 0.
| Returns 0 in %d0 for a completed sleep, -1 for the give-up case. Saves
| and restores %d2 only; %d0, %d1, %a0 and %a1 are clobbered.
| The caller leaves its ready ring for the duration, so every other task
| runs. PIT1's handler wakes it and forces a reschedule, so the wake is
| immediate, not rounded up to a tick. Call it in supervisor mode with the
| SR K_CREATE gives a task, 0x2000. Never from an interrupt handler, and
| never with the interrupt mask above level 2, because PIT1 is level 2.
| ⚠️ The timer object is SHARED and holds ONE waiter, and every call
| resets it. If another task enters this routine while you are asleep,
| your wake-up is destroyed and your task never runs again. The only stock
| callers are the CompactFlash probe and the OS upgrade. See section 4.7.
.equ	K_DELAY,	0x40020c7c

| K_DELAY's second argument.
.equ	K_DELAY_TRY,	0
.equ	K_DELAY_WAIT,	1

| One pass of the writer loop. The plan's name is kept; the unit is
| MICROSECONDS, not the kernel's preemption tick. 10,000 becomes a 9.988 ms
| sleep. A 64 KB chunk fills every 371 ms at 176,400 B/s, so this is ample
| whichever way the factor of two in section 4.3 resolves.
.equ	TASK_TICKS,	10000

| The kernel's preemption tick, in microseconds. PIT0, prescaler 2048,
| PMR 643, at the 132 MHz internal bus clock. NOTHING COUNTS IT: there is
| no tick counter, no delay list and no per-task tick field anywhere in
| the kernel. It exists only to preempt. Recorded for sizing, not for use.
.equ	K_TICK_US,	9992

| An event object is EIGHT bytes: +0 the latched flag, +4 the one and only
| waiter's TCB address. A statically zeroed 8 byte block is already valid,
| so the initialiser call is optional.
|   pea count / pea obj / jsr K_EVENT_INIT / addq.l #8,%sp
.equ	K_EVENT_INIT,	0x40000794
| Block until the flag is set, then consume it. A set flag returns at once,
| so a post that arrives first is not lost. NO TIMEOUT: on a private object
| nothing posts, this blocks forever.
|   pea obj / jsr K_EVENT_PEND / addq.l #4,%sp
.equ	K_EVENT_PEND,	0x40000818
| Set the flag, wake the waiter, and force a reschedule. Safe from an
| interrupt handler.
|   pea obj / jsr K_EVENT_POST / addq.l #4,%sp
.equ	K_EVENT_POST,	0x40000968
```
