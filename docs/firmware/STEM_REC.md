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

### 1.6 Measured under the port ✅, with one new open question 🟡

Task 10 added four `ot_emu` flags (`--card-out`, `--call-before-play`, `--at`,
`--card-fail-after`) and staged a project card (set `STEMS`, project `ULTFX`,
from `out/projects/Ultimate FX 1.5.3`) to close this section. Command run
(12 Sep 2026):

```bash
out/emu/ot_emu --image out/raw/section_3_MAIN_OS.bin --card out/stems_card.img \
  --set STEMS --project ULTFX --sequencer --frames 400 --load-ms 20000 \
  --at 200:0x4000a1e0:0 --card-out out/task10/after.img \
  --watch-mem 0x800065b8,4 --mem-dump 0x100f8480,64=out/task10/setpath.bin
```

`--at 200:0x4000a1e0:0` calls the STOP handler with `callAsMain`, the same
call shape `press_key_live(KEY_STOP)` uses in `emu_rtos.py`, at frame 200
after the transport start.

**The start edge is confirmed. ✅** `--watch-mem` shows exactly two writes
over the whole run:

```
[    8707.8] [0x800065b8] <- 0 (4) at pc 0x400a1050 in main  i=44915230
[  895721.0] [0x800065b8] <- 0x1 (4) at pc 0x4009c3d4 in main  i=443500349
```

The first is engine init (section 1.3's `0x400a1050`); the second is
`FW_TRANSPORT`'s cold-start write of 1, at the transport start. This matches
`RTOS_FORK.md` §9.4 exactly (same pc, same value) against a different
project, so the 0->1 transition is now measured twice, against two
projects.

**The literal STOP call is a no-op on this project.** The call returns
(`call : 0x4000a1e0(0x0) at frame 200 -> returned, d0 0x3fb6`), but
`--watch-mem` shows no third write: the word stays at 1. `--watch-pc` on the
handler's three exits (`0x4000a1fe`, `0x4000a1f8`, `0x4000a1f2`) shows the
call landed at `0x4000a1fe`, the bare `rts` from section 1.5's disassembly:

```
tstb 0x80000029 / beqs 0x4000a1fe   -- taken
```

`--peek 80000029` (a 32-bit read starting at that address) reads
`0x00010209`, so the single byte at `0x80000029` itself is `0x00`. A
`--mem-dump 0x80000028,8` at the end of a full 400-frame run with no STOP
call at all shows the same byte still `0x00`: nothing in this project's load
or its first 400 frames ever sets it.

**With the gate forced open, the write-2 path is confirmed. ✅** Poking the
byte before the call (`--poke 0x80000029=1`) reaches the code section 1.5
already disassembled:

```
[    8707.8] [0x800065b8] <- 0 (4) at pc 0x400a1050 in main  i=44915230
[  895721.0] [0x800065b8] <- 0x1 (4) at pc 0x4009c3d4 in main  i=443500349
[  898942.4] [0x800065b8] <- 0x2 (4) at pc 0x4009f5c6 in main  i=449759644
```

`0x4009f5c6` is exactly the "write 2" site section 1.2 classified from the
static read. So the 0/1/2 state machine in sections 1.0, 1.4 and 1.7 is
now measured end to end, and the falsifier below is not triggered: a
running transport (word 1) that receives a real STOP call, with its own
precondition satisfied, does write 2 and nothing else.

**🟡 New question: what sets `0x80000029`, and why is it already set on one
project and not another?** `RTOS_FORK.md` §9.4 measured this same byte as
already `0x01` right after `load_project_live` on `out/_testproj`, with no
extra setup. On `Ultimate FX 1.5.3`, staged the same way, it reads `0x00`
after the same kind of load and stays `0x00` through 400 frames of the
sequencer running. `startTransportLive()` (what `--sequencer` uses to start
the transport) calls `FW_TRANSPORT` directly and does not go through the
real `KEY_PLAY` handler, so whatever sets `0x80000029` may be a side effect
of the real PLAY key path, of a specific project setting, or of both;
this pass did not chase it further. **Concern for Tasks 13 to 15:** a raw
`callAsMain` on `0x4000a1e0` (or any project-dependent equivalent) is not on
its own proof that STOP was pressed; check `0x80000029` first, or drive
STOP through the real key path.
**Falsifier:** a write to `0x80000029` found in the image, or a run on a
third project where the byte is set after load without the poke.

**Falsifier for this whole section (unchanged, and not triggered):** a
transport stop from the STOP key that leaves the word at 0 rather than 2, or
a running transport whose word is anything other than 1. Neither happened:
every write measured matches sections 1.0, 1.4, 1.5 and 1.7.

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

## 5. The name and the path

### 5.0 The plan's set folder rule is a detour. Read this first.

The plan's Task 15 says "set folder = project directory up to its last `/`",
with the project directory from `0x40025230`. That arithmetic does hold, but
it is the long way round, and it copies out of a buffer that the next caller
overwrites.

**The set folder has its own source, and the stock sample save uses it
directly.** It is a plain C string buffer at `0x100f8480`. `0x40025230` is
built on top of that buffer: it formats `"%s/%s"` from `0x100f8480` and the
project name at `0x100f8378`. So `stems_make_path` should read `0x100f8480`
and never call `0x40025230` at all.

Three other things Task 15 needs, each different from what the brief assumed:

1. `0x4001c4d8` **takes a blocking mutex**, and it is an SPI transaction, not
   an I2C one. Section 5.2. The writer task is safe against the UI task, but
   only because it calls this routine rather than the registers.
2. The clock field indices in the plan are correct. Section 5.4 measures them
   from the name builder's own calls and from a sibling routine that prints
   seconds.
3. The lead address `0x40084e24` in the brief is not a path build. It is the
   file open. The path builds are at `0x400241b8`, `0x400242e4`, `0x40076440`
   and `0x40076536`. Section 5.6.

Term note. The **set** is the top level folder on the CompactFlash card. The
**pool** is the `AUDIO` folder inside it, where samples live. A **project** is
a folder beside `AUDIO` inside the set. **cdecl** here means arguments pushed
right to left and popped by the caller, which is what every routine in this
section uses.

### 5.1 The name builder, whole ✅

`0x400819fc` is 128 bytes and has exactly one caller, a `jsr` at `0x40023eba`.
Measured two ways that agree: `refs.sh 0x400819fc` returns one hit, and a
linear objdump of the whole image
(`m68k-elf-objdump -D -b binary -m m68k:cfv4e --adjust-vma=0x40000400`)
grepped for `400819fc` returns two lines, the routine's own label and that one
`jsr`. The linear pass is the one that would catch a register indirect call,
and there is none.

```
400819fc:	4fef ffe8      	lea %sp@(-24),%sp
40081a00:	48d7 0c3c      	moveml %d2-%d5/%a2-%a3,%sp@
40081a04:	4878 0002      	pea 0x2
40081a08:	47f9 4001 c4d8 	lea 0x4001c4d8,%a3
40081a0e:	4e93           	jsr %a3@
40081a10:	2f00           	movel %d0,%sp@-
40081a12:	45f9 4001 c31c 	lea 0x4001c31c,%a2
40081a18:	4e92           	jsr %a2@
40081a1a:	2a00           	movel %d0,%d5
40081a1c:	4878 0003      	pea 0x3
40081a20:	4e93           	jsr %a3@
40081a22:	2f00           	movel %d0,%sp@-
40081a24:	4e92           	jsr %a2@
40081a26:	2800           	movel %d0,%d4
40081a28:	4878 0005      	pea 0x5
40081a2c:	4e93           	jsr %a3@
40081a2e:	2f00           	movel %d0,%sp@-
40081a30:	4e92           	jsr %a2@
40081a32:	2600           	movel %d0,%d3
40081a34:	4878 0006      	pea 0x6
40081a38:	4e93           	jsr %a3@
40081a3a:	2f00           	movel %d0,%sp@-
40081a3c:	4e92           	jsr %a2@
40081a3e:	2400           	movel %d0,%d2
40081a40:	4fef 0020      	lea %sp@(32),%sp
40081a44:	4878 0007      	pea 0x7
40081a48:	4e93           	jsr %a3@
40081a4a:	2f00           	movel %d0,%sp@-
40081a4c:	4e92           	jsr %a2@
40081a4e:	2f05           	movel %d5,%sp@-
40081a50:	2f04           	movel %d4,%sp@-
40081a52:	2f03           	movel %d3,%sp@-
40081a54:	2f02           	movel %d2,%sp@-
40081a56:	2f00           	movel %d0,%sp@-
40081a58:	4879 400b 77bb 	pea 0x400b77bb
40081a5e:	4879 460f aab4 	pea 0x460faab4
40081a64:	4eb9 4001 3a08 	jsr 0x40013a08
40081a6a:	203c 460f aab4 	movel #1175431860,%d0
40081a70:	4cef 0c3c 0024 	moveml %sp@(36),%d2-%d5/%a2-%a3
40081a76:	4fef 003c      	lea %sp@(60),%sp
40081a7a:	4e75           	rts
```

Five facts follow, all ✅.

- **It takes no arguments.** Nothing reads `%sp@(4)`.
- **It returns a pointer in `%d0`**, to the static buffer `0x460faab4`.
  `0x40081a6a` loads that address as a literal. objdump prints the immediate in
  decimal, 1175431860; the operand bytes `460f aab4` are the address.
- **The buffer is private to this routine and is overwritten on every call.**
  The whole image references `0x460faab4` from one instruction,
  `pea 0x460faab4` at `0x40081a5e`. Copy the string out before anything else
  can call the builder.
- **Every helper call is cdecl and the caller pops.** The two `lea %sp@(...)`
  at `0x40081a40` and `0x40081a76` do all the popping. Follow the stack
  pointer from entry: 24 bytes of saved registers, then eight pushes of four
  bytes each, then `lea %sp@(32),%sp` puts it back exactly where the saved
  registers begin. The final `moveml %sp@(36)` then lands on those same saved
  registers, because seven more pushes have happened since. The frame closes
  with `lea %sp@(60),%sp`, which is 24 plus 36.
- **`0x4001c4d8` and `0x4001c31c` preserve `%d2`, `%d3`, `%d4`, `%d5`, `%a2`
  and `%a3`.** This is measured, not assumed. `%a3` is loaded once at
  `0x40081a08` and re-used at `0x40081a20`, `0x40081a38` and `0x40081a48`,
  across intervening `jsr %a2@` calls. `%d5` is written at `0x40081a1a` and is
  still live at `0x40081a4e`, across eight calls.

Four sibling routines sit next to it and share the same shape. They are useful
as cross checks, and section 5.4 uses them.

| address | format string | fields it reads |
|---|---|---|
| `0x40081968`, tail at `0x400819d0` | `0x400b779d`, `"%04d-%02d-%02d %02d:%02d:%02d"` | 1, 2, 3, 5, 6, 7 |
| `0x400819fc` | `0x400b77bb`, `"%02d%02d%02d-%02d%02d"` | 2, 3, 5, 6, 7 |
| `0x40081a7c` | `0x400b77ac`, `"%02d:%02d:%02d"` | 1, 2, 3 |
| `0x40081adc` | `0x400b77c8`, `"%02d%02d"` | 2, 3 |
| `0x40081b30` | `0x400b77d1`, `"%02d%02d%02d"` | 5, 6, 7 |

The timestamp routine's tail is the only place `2000` is added:

```
400819d0:	0680 0000 07d0 	addil #2000,%d0
400819d6:	2f00           	movel %d0,%sp@-
400819d8:	4879 400b 779d 	pea 0x400b779d
400819de:	4879 460f aa94 	pea 0x460faa94
400819e4:	4eb9 4001 3a08 	jsr 0x40013a08
```

✅ The name builder does not add it. It prints the clock's two digit year with
`%02d`, which is what makes the name `YYMMDD-HHMM`.

### 5.2 The clock read takes a blocking mutex, and it is SPI ✅

```
4001c4d8:	2f02           	movel %d2,%sp@-
4001c4da:	242f 0008      	movel %sp@(8),%d2
4001c4de:	4879 46c8 c5f4 	pea 0x46c8c5f4
4001c4e4:	4eb9 4000 09f4 	jsr 0x400009f4
4001c4ea:	0082 9002 0000 	oril #-1878917120,%d2
4001c4f0:	23c2 fc05 c034 	movel %d2,0xfc05c034
4001c4f6:	203c 1002 0000 	movel #268566528,%d0
4001c4fc:	23c0 fc05 c034 	movel %d0,0xfc05c034
4001c502:	588f           	addql #4,%sp
4001c504:	2039 fc05 c02c 	movel 0xfc05c02c,%d0
4001c50a:	e888           	lsrl #4,%d0
4001c50c:	720f           	moveq #15,%d1
4001c50e:	c081           	andl %d1,%d0
4001c510:	123c 0002      	moveb #2,%d1
4001c514:	b280           	cmpl %d0,%d1
4001c516:	66ec           	bnes 0x4001c504
4001c518:	2039 fc05 c038 	movel 0xfc05c038,%d0
4001c51e:	2439 fc05 c038 	movel 0xfc05c038,%d2
4001c524:	7002           	moveq #2,%d0
4001c526:	4840           	swap %d0
4001c528:	23c0 fc05 c02c 	movel %d0,0xfc05c02c
4001c52e:	4879 46c8 c5f4 	pea 0x46c8c5f4
4001c534:	4eb9 4000 0ab4 	jsr 0x40000ab4
4001c53a:	588f           	addql #4,%sp
4001c53c:	7182           	mvzb %d2,%d0
4001c53e:	241f           	movel %sp@+,%d2
4001c540:	4e75           	rts
```

**The argument.** ✅ One longword at `%sp@(8)`, which is `%sp@(4)` at entry,
because `%d2` was pushed first. It is the field index, and it goes into the
transmit word unchanged.

**The return.** ✅ `mvzb %d2,%d0` at `0x4001c53c` zero extends the low byte of
the second received word into `%d0`. So `%d0` holds the clock's raw byte in the
range 0 to 255, in binary coded decimal, with bits 8 to 31 clear. `0x4001c31c`
needs exactly that, because it uses `asrl` on the whole longword.

**The clobbers.** ✅ `%d2` is saved and restored. Nothing else is. The two
helper calls save `%d2`, `%a2` and `%a3` themselves. So the routine preserves
`%d2` through `%d7` and `%a2` through `%a6`, and clobbers `%d0`, `%d1`, `%a0`
and `%a1`. This matches what section 5.1 measured from the caller.

**The lock.** ✅ `0x400009f4` is a blocking mutex acquire. Its object is three
longwords: the owning task at `+0`, and a waiter list at `+4` and `+8`.

```
40000a00:	40c2           	movew %sr,%d2
40000a02:	46fc 2700      	movew #9984,%sr
40000a06:	4a93           	tstl %a3@
40000a08:	6608           	bnes 0x40000a12
40000a0a:	26b9 8000 68fc 	movel 0x800068fc,%a3@
40000a10:	6068           	bras 0x40000a7a
```

If the owner word is zero it stores the current task control block address
from `0x800068fc` and returns. Otherwise it links the caller onto the waiter
list, unlinks the caller from its ready ring, and executes `trap #0` at
`0x40000a78`, which section 4.1 shows is the context switch. The release
`0x40000ab4` puts the head waiter back on its ready ring, and traps again if
that waiter outranks the current task. `0x400009e4` is the initialiser, three
`clr`s, and `0x4001f926` calls it on this object during start-up.

Two consequences for Task 15.

- **The writer task is safe against the UI task**, and it is safe because the
  mutex serialises the whole transaction, not because the transaction is
  atomic. It is not atomic. `movew #9984,%sr` is `0x2700`, which masks
  interrupts to level 7, but only inside the acquire and the release, and the
  status register is restored before the transfer starts. So the poll loop at
  `0x4001c504` runs with interrupts enabled, and the caller can be preempted in
  the middle of the transfer.
- **This routine can block, so it must be called from a task.** Never from an
  interrupt handler, never from the per-frame DSP hook of section 2, and never
  with the interrupt mask raised. It is also not recursive: the acquire has no
  "already mine" case, so a second entry from the same task deadlocks.

**It is DSPI, not I2C.** ✅ The three registers are `+0x2c`, `+0x34` and
`+0x38` of the module at `0xfc05c000`. On this part that module is the DSPI,
the serial peripheral interface, and those offsets are its status, transmit
FIFO push, and receive FIFO pop registers. The behaviour matches: two pushes
whose upper halves are `0x90020000` and `0x10020000`, which set the continue
bit and chip select 1 on the first word and drop the continue bit on the
second; then a poll of the nibble at bits 7 to 4 of the status until it reads
2, which is the receive FIFO count; then two pops; then a write of
`0x00020000` to the status to clear the receive flag. `RTOS_FORK.md` line 272
already names `0xfc05c000` as the DSPI, from the emulator's own modelling of it
as a loopback FIFO whose sites wait for two or three received frames.

❌ **Retract `SAMPLE_SAVE.md` section 6's "It is an I2C transaction".** The
addresses in that sentence are right and its conclusion about BCD is right.
The bus is wrong. The I2C module on this part is at `0xfc058000`, and nothing
in this path touches it.

The correction changes no calling convention, but it changes the risk picture.
An SPI FIFO read is a four step sequence, and the poll loop has no timeout. If
the receive FIFO never reaches two entries the routine spins forever with the
mutex held, and every other task that wants the clock blocks behind it.
🟡 That has never been observed. Falsifier: run the port with a watch on
`0x4001c504` and count iterations across a boot.

The same module has a write path at `0x4001c468`, which takes two arguments and
uses the same mutex. STEM REC has no reason to call it. It is recorded here
only so nobody mistakes it for the read.

### 5.3 The BCD conversion ✅

```
4001c31c:	2f02           	movel %d2,%sp@-
4001c31e:	202f 0008      	movel %sp@(8),%d0
4001c322:	2400           	movel %d0,%d2
4001c324:	e882           	asrl #4,%d2
4001c326:	2202           	movel %d2,%d1
4001c328:	e789           	lsll #3,%d1
4001c32a:	2241           	moveal %d1,%a1
4001c32c:	41f1 2a00      	lea %a1@(0,%d2:l:2),%a0
4001c330:	720f           	moveq #15,%d1
4001c332:	c081           	andl %d1,%d0
4001c334:	d088           	addl %a0,%d0
4001c336:	241f           	movel %sp@+,%d2
4001c338:	4e75           	rts
```

✅ One longword argument at `%sp@(8)`, which is `%sp@(4)` at entry. The value
is `(v >> 4) * 8 + (v >> 4) * 2 + (v & 15)`, which is
`(v >> 4) * 10 + (v & 15)`. Returned in `%d0`, binary. Preserves `%d2`;
clobbers `%d0`, `%d1`, `%a0` and `%a1`. cdecl, caller pops.

⚠️ `asrl` is arithmetic. Pass it the zero extended byte that `0x4001c4d8`
returns and nothing else. A value with bit 31 set converts to nonsense.

The inverse, binary to BCD, is at `0x4001c33c`. STEM REC does not need it.

### 5.4 The field indices, and the format's argument order ✅

The name builder pushes the sprintf arguments right to left, so the last push
before the format string is the first conversion. Reading `0x40081a4e` to
`0x40081a5e` from the bottom up:

| position in `"%02d%02d%02d-%02d%02d"` | register | clock index | field |
|---|---|---|---|
| 1 | `%d0` | 7 | year, two digits |
| 2 | `%d2` | 6 | month |
| 3 | `%d3` | 5 | day of month |
| 4 | `%d4` | 3 | hour |
| 5 | `%d5` | 2 | minute |

✅ So the name is `YYMMDD-HHMM`, and the plan's placeholder indices 2, 3, 5, 6
and 7 are the real ones.

The meanings are pinned by the sibling at `0x40081a7c`, which reads indices 1,
2 and 3 into a format that is unambiguously `HH:MM:SS`:

```
40081ab2:	2f03           	movel %d3,%sp@-
40081ab4:	2f02           	movel %d2,%sp@-
40081ab6:	2f00           	movel %d0,%sp@-
40081ab8:	4879 400b 77ac 	pea 0x400b77ac
```

`%d3` came from index 1, `%d2` from index 2 and `%d0` from index 3, and the
first conversion is the hour. So index 3 is the hour, index 2 the minute, and
index 1 the second. ✅ The date sibling at `0x40081b30` reads 5, 6 and 7 into
`"%02d%02d%02d"`, in that same day, month, year order.

🟡 Index 4 is day of week, and index 0 is unidentified. Neither routine reads
either. Falsifier: call `0x4001c4d8(4)` under the port and compare against a
known date. This repeats what `SAMPLE_SAVE.md` section 6 already says, and
nothing here changes it.

The exact bytes of the format string, so a module can carry its own copy rather
than depend on the address:

```
0x400b77bb  25 30 32 64 25 30 32 64 25 30 32 64 2d 25 30 32 64 25 30 32 64 00
            "%02d%02d%02d-%02d%02d"
```

✅ 21 characters and a terminator. `refs.sh 0x400b77bb` returns exactly one
hit, `0x40081a5a`, the operand of the `pea` at `0x40081a58`.

### 5.5 sprintf ✅

```
40013a08:	4e56 0000      	linkw %fp,#0
40013a0c:	486e 0010      	pea %fp@(16)
40013a10:	2f2e 000c      	movel %fp@(12),%sp@-
40013a14:	2f2e 0008      	movel %fp@(8),%sp@-
40013a18:	4eba d6ea      	jsr %pc@(0x40011104)
40013a1c:	4fef 000c      	lea %sp@(12),%sp
40013a20:	4e5e           	unlk %fp
40013a22:	4e75           	rts
```

✅ `sprintf(dest, fmt, ...)`, cdecl, caller pops, ordinary C varargs: the
wrapper hands the inner formatter a pointer to the first vararg at `%fp@(16)`.
It returns whatever the inner routine returns in `%d0`, which no caller in this
section reads.

✅ It preserves `%d2` through `%d7` and `%a2` through `%a6`. Measured at a call
site rather than assumed: the routine at `0x40024180` loads `%a2` before the
sprintf at `0x400241cc` and dereferences `%a2` at `0x40024202`, after it. The
inner formatter at `0x40013a24` saves `%d2` to `%d5` and `%a2` to `%a5` in its
own prologue.

⚠️ There is no length limit. This is `sprintf`, not `snprintf`. Size the
destination for the worst case yourself.

### 5.6 The stock save's path build, both branches ✅

The brief's lead `0x40084e24` is the file open, not the path build:

```
40084e0e:	4879 400b 328b 	pea 0x400b328b
40084e14:	4879 4603 63e0 	pea 0x460363e0
40084e1a:	260e           	movel %fp,%d3
40084e1c:	0683 ffff ffe2 	addil #-30,%d3
40084e22:	2f03           	movel %d3,%sp@-
40084e24:	4eb9 4001 6864 	jsr 0x40016864
```

`0x400b328b` is `"w"`, so that is `0x40016864` opening an already built path for
writing. The path itself is built elsewhere.

`refs.sh 0x400b3a85` finds four uses of `"%s/AUDIO/%s.wav"`, at `0x400241c2`,
`0x400242f2`, `0x4007644a` and `0x40076544`. All four sit in the same shape.
Here is the first, whole:

```
400241a6:	4ab9 8000 00a4 	tstl 0x800000a4
400241ac:	670a           	beqs 0x400241b8
400241ae:	4eb9 4002 4eec 	jsr 0x40024eec
400241b4:	4a80           	tstl %d0
400241b6:	6620           	bnes 0x400241d8
400241b8:	2f02           	movel %d2,%sp@-
400241ba:	4879 100f 8480 	pea 0x100f8480
400241c0:	4879 400b 3a85 	pea 0x400b3a85
400241c6:	4879 460b e79c 	pea 0x460be79c
400241cc:	4eb9 4001 3a08 	jsr 0x40013a08
400241d2:	4fef 0010      	lea %sp@(16),%sp
400241d6:	6024           	bras 0x400241fc
400241d8:	42a7           	clrl %sp@-
400241da:	42a7           	clrl %sp@-
400241dc:	4eb9 4002 5230 	jsr 0x40025230
400241e2:	2f02           	movel %d2,%sp@-
400241e4:	2f00           	movel %d0,%sp@-
400241e6:	4879 400b 3a95 	pea 0x400b3a95
400241ec:	4879 460b e79c 	pea 0x460be79c
400241f2:	4eb9 4001 3a08 	jsr 0x40013a08
400241f8:	4fef 0018      	lea %sp@(24),%sp
```

Reading it out, all ✅.

- **The first `%s` of `"%s/AUDIO/%s.wav"` is the buffer at `0x100f8480`.** `pea`
  pushes the address, so `0x100f8480` is where the characters are, not a
  pointer to them.
- **`0x800000a4` chooses the branch.** It is a personal setting with two
  values. Its own display routine names them:

```
40068b82:	2239 8000 00a4 	movel 0x800000a4,%d1
40068b88:	203c 400b 62b4 	movel #1074487988,%d0
40068b8e:	4a81           	tstl %d1
40068b90:	6712           	beqs 0x40068ba4
40068b92:	203c 400b 62bd 	movel #1074487997,%d0
```

  `0x400b62b4` is `"AUD POOL"` and `0x400b62bd` is `"PROJ DIR"`. So zero means
  the pool and one means the project folder. The setting is written at one
  site, `0x40068b70`, and mirrored to `0x100fff34`.
- **`0x40024eec` asks whether a project name exists**, and it reads the same
  buffer that `0x40025230` defaults to:

```
40024eec:	4a39 100f 8378 	tstb 0x100f8378
40024ef2:	56c0           	sne %d0
40024ef4:	7100           	mvsb %d0,%d0
40024ef6:	4480           	negl %d0
40024ef8:	4e75           	rts
```

- **So the rule is:** save to `<set>/<project>/<name>.wav` when the setting is
  PROJ DIR and the project name is not empty, and to `<set>/AUDIO/<name>.wav`
  otherwise.
- **`0x40025230` returns in `%d0`, and the caller does not pop before the next
  push.** `0x400241e4` pushes `%d0` straight in as the first `%s`, and the
  single `lea %sp@(24),%sp` at `0x400241f8` pops all six longwords: the two
  zero arguments, `%d2`, `%d0`, the format and the destination.
- **`0x40025230` preserves `%d2`.** `%d2` holds the name across the call and is
  pushed at `0x400241e2`.

One corroboration from elsewhere in the image, which fixes the folder layout
rather than only the format string. A different routine stores the slot's own
filename, relative to wherever the slot record is read from:

```
40023f94:	2f04           	movel %d4,%sp@-
40023f96:	4879 400b 3a11 	pea 0x400b3a11
40023f9c:	6008           	bras 0x40023fa6
40023f9e:	2f04           	movel %d4,%sp@-
40023fa0:	4879 400b 3a1a 	pea 0x400b3a1a
```

`0x400b3a11` is `"../AUDIO/%s.wav"` and `0x400b3a1a` is `"%s.wav"`, chosen by
the same two tests. ✅ So `AUDIO` is one level up from a project folder, and
both sit directly inside the set.

The exact bytes of the two path formats:

```
0x400b3a85  25 73 2f 41 55 44 49 4f 2f 25 73 2e 77 61 76 00   "%s/AUDIO/%s.wav"
0x400b3a95  25 73 2f 25 73 2e 77 61 76 00                     "%s/%s.wav"
```

### 5.7 The project directory routine, whole ✅

```
40025230:	202f 0004      	movel %sp@(4),%d0
40025234:	206f 0008      	moveal %sp@(8),%a0
40025238:	6606           	bnes 0x40025240
4002523a:	203c 100f 8480 	movel #269452416,%d0
40025240:	4a88           	tstl %a0
40025242:	6606           	bnes 0x4002524a
40025244:	41f9 100f 8378 	lea 0x100f8378,%a0
4002524a:	43f9 4001 3a08 	lea 0x40013a08,%a1
40025250:	4a10           	tstb %a0@
40025252:	6718           	beqs 0x4002526c
40025254:	2f08           	movel %a0,%sp@-
40025256:	2f00           	movel %d0,%sp@-
40025258:	4879 400b 86c1 	pea 0x400b86c1
4002525e:	4879 460b f112 	pea 0x460bf112
40025264:	4e91           	jsr %a1@
40025266:	4fef 0010      	lea %sp@(16),%sp
4002526a:	6014           	bras 0x40025280
4002526c:	2f00           	movel %d0,%sp@-
4002526e:	4879 400b 3f82 	pea 0x400b3f82
40025274:	4879 460b f112 	pea 0x460bf112
4002527a:	4e91           	jsr %a1@
4002527c:	4fef 000c      	lea %sp@(12),%sp
40025280:	203c 460b f112 	movel #1175187730,%d0
40025286:	4e75           	rts
```

✅ **Two longword arguments, cdecl.** The first is a set path string, defaulted
to `0x100f8480` when it is zero. The second is a project name string, defaulted
to `0x100f8378` when it is zero. The `bnes` at `0x40025238` tests `%d0`, because
`moveal` does not touch the condition codes on this core.

✅ **`0x400b86c1` is `"%s/%s"` and `0x400b3f82` is `"%s/UNTITLED"`.** So the
result is `<set>/<project>`, or `<set>/UNTITLED` when the project name is the
empty string.

✅ **The return is `%d0`, and only `%d0`.** `0x40025280` loads the literal
`0x460bf112`, which is the destination it just formatted into. objdump prints
the immediate in decimal, 1175187730; the operand bytes `460b f112` are the
address. `%a0` holds the project name string at that point, not the result, and
`%a1` holds sprintf's address. Nothing else is set. This answers step 3 of the
brief: `%d0`, not `%a0`, not both.

✅ **The result buffer is a shared static, `0x460bf112`.** The whole image
references it from two instructions, both inside this routine, so it is this
routine's output buffer and nothing else's. But 45 sites in the image name
this routine. Counted from the linear objdump, which catches the
`lea 0x40025230,%aN` loads and the `jsr %pc@` form at `0x400255f6` that
`refs.sh` cannot see; `refs.sh` alone finds 51 raw occurrences of the address,
some of them table data. Some of the 45 are register loads that feed more than
one call, so the number of calls is 45 or more. Any of them can overwrite the
buffer. Copy the string out immediately.

✅ **It clobbers `%d0`, `%d1`, `%a0` and `%a1` only.** It saves nothing, and it
calls only sprintf, which preserves `%d2` upward.

🟡 **It takes no lock and cannot block on its own.** It reads two globals and
calls sprintf. Falsifier: a lock inside sprintf's inner formatter, which is not
disassembled here.

### 5.8 The set folder, and what Task 15 must use ✅ with two 🟡

✅ **The set folder is the C string at `0x100f8480`.** The linear objdump finds
49 instructions naming it, and every one of them is `pea 0x100f8480`. Not one
loads from it as a variable. A `pea` in a sprintf argument list is a `%s`
pointer, so the address is the first character of the string.

There is a fiftieth site, which objdump prints with a decimal immediate, so a
grep for the hex misses it. It is `0x4002523a`, `movel #269452416,%d0` inside
`0x40025230`, and it uses the same address the same way.

✅ **`0x100f8378` is the project name**, by the same reasoning, plus
`0x40024eec` testing its first byte for the empty string.

✅ **Both live outside this image section.** The section covers `0x40000400`
through `0x4010f9b0`. `0x100f8480` is in the settings block region, above the
128 slot table, and its contents are runtime state. So the addresses are
measured and the contents are not, and cannot be, from a static read.

✅ **`0x100f8480` is a complete path prefix, not a bare folder name.** The mount
check `0x40025650` takes it as its only argument, formats `"%s/AUDIO"` from it
into a 260 byte stack buffer, and asks the file layer whether both the set path
and that pool path exist:

```
40025650:	4fef fefc      	lea %sp@(-260),%sp
40025658:	242f 0110      	movel %sp@(272),%d2
4002565c:	2f02           	movel %d2,%sp@-
4002565e:	4879 400b 7758 	pea 0x400b7758
40025664:	260f           	movel %sp,%d3
40025666:	0683 0000 0010 	addil #16,%d3
4002566c:	2f03           	movel %d3,%sp@-
4002566e:	4eb9 4001 3a08 	jsr 0x40013a08
40025674:	2f02           	movel %d2,%sp@-
40025676:	4eb9 4001 3db0 	jsr 0x40013db0
```

`0x400b7758` is `"%s/AUDIO"`. Three call sites pass `0x100f8480` to it,
`0x40021e78`, `0x40023dd8` and `0x400256be`, and the failure message they show
is `"NO SET IS MOUNTED!"` at `0x400b3766`. So the string is what the file layer
accepts as the head of a path.

✅ **It begins with `/` and has no trailing `/`.** Measured under the port,
12 Sep 2026: a project staged as set `STEMS`, project `ULTFX`
(`out/projects/Ultimate FX 1.5.3`), loaded and run under `ot_emu`
(`--card out/stems_card.img --set STEMS --project ULTFX --sequencer`), then
`--mem-dump 0x100f8480,64` dumped as `2f5354454d53 00...` --
`b'/STEMS'` followed by zero bytes. The first byte is `/`, and the string
ends at the terminator with no trailing `/`, confirming both halves of this
claim. octamax logged the path the stock loader resolved on hardware as
`/universi/UNTITLED`, through a hook on all seven path taking file routines
(`octamax/NOTES.md`, around line 470), which agrees. ems-octakit appends
`"/kits3a.work"` to `0x40025230(0, 0)` and opens the result successfully
(`ems-octakit/runtime/persistence.c` line 425, with the ABI equate in
`runtime/abi.inc` line 486), which also agrees.

**What Task 15 must do.** Build the path as
`sprintf(buf, "%s/AUDIO/%s/T1.wav", 0x100f8480, name)`, or with the folder
dropped if Task 7 finds no folder routine. Do not call `0x40025230`, and do not
trim its result back to its last `/`. The plan's rule gives the same answer,
because `0x40025230` always appends exactly one `/` and one name component, but
it goes through a buffer that 45 other sites share, and it behaves differently
when the project name is empty, where it appends `UNTITLED` rather than nothing.

🟡 **Nothing locks `0x100f8480`.** No call site takes a mutex around it. The UI
task can in principle rewrite it while the writer task is formatting. The window
is the length of one sprintf, and the only writer is a set change, which the
user cannot do while the sequencer is running, so the exposure is small.
Falsifier: find a write to `0x100f8480` that is reachable during playback.

🟡 **`0x800000a4` is not STEM REC's business.** STEM REC writes stems to the
pool unconditionally, so it should ignore the AUD POOL and PROJ DIR setting.
Recorded so that nobody wires it in by analogy with the stock save. Falsifier: a
decision that stems should follow the setting, which is a design question, not a
firmware one.

### 5.9 The table Task 15 codes against ✅

| routine | address | arguments | returns | preserves | blocks |
|---|---|---|---|---|---|
| clock read | `0x4001c4d8` | one longword, the field index | `%d0`, one BCD byte, zero extended | `%d2`-`%d7`, `%a2`-`%a6` | yes, a mutex |
| BCD to binary | `0x4001c31c` | one longword, the byte | `%d0`, binary | `%d2`-`%d7`, `%a2`-`%a6` | no |
| sprintf | `0x40013a08` | dest, format, varargs | `%d0`, unused here | `%d2`-`%d7`, `%a2`-`%a6` | no |
| name builder | `0x400819fc` | none | `%d0`, pointer to `0x460faab4` | `%d2`-`%d7`, `%a2`-`%a6` | yes, through the clock |
| project directory | `0x40025230` | set path or 0, project name or 0 | `%d0`, pointer to `0x460bf112` | `%d2`-`%d7`, `%a2`-`%a6` | no |
| set mounted | `0x40025650` | set path | `%d0`, non-zero if mounted | `%d2`, `%d3` measured; rest not | 🟡 not measured |

Every one is cdecl and the caller pops. Every one clobbers `%d0`, `%d1`, `%a0`
and `%a1`.

Two static buffers, each overwritten on every call to its owner: `0x460faab4`
for the name, and `0x460bf112` for the project directory.

### 5.10 Not measured under the port 🟡

No project folder exists on this machine, so nothing here was executed. Four
things a port run would settle, in the order they matter:

1. ✅ **Done for `0x100f8480`, 12 Sep 2026 (Task 10).** `--mem-dump
   0x100f8480,64` after a real load reads `/STEMS`, settling the leading
   slash question in 5.8. `0x100f8378` (the project name) was not dumped in
   this pass and is still open.
2. **One call of `0x400819fc` from a scratch task, and the string it leaves at
   `0x460faab4`.** This confirms the field map end to end against the unit's own
   clock, including index 4.
3. **Whether the clock mutex is ever contended.** Watch `0x400009f4` with
   `0x46c8c5f4` as its argument, and count the times it takes the blocking path.
   If the answer is never, the writer task's clock read is free. If the answer
   is often, the writer task should read the clock once per take rather than
   once per file.
4. **The iteration count of the poll loop at `0x4001c504`.** A high count means
   the transfer is slow enough to matter inside a priority 1 task.

### 5.11 Interface

```asm
| Read one field of the real time clock. ONE longword argument on the stack,
| the field index. Returns that field's RAW BCD BYTE, zero extended, in %d0.
| cdecl, the caller pops:
|   pea index / jsr CLK_READ / addq.l #4,%sp
| Preserves %d2-%d7 and %a2-%a6. Clobbers %d0, %d1, %a0, %a1.
| ⚠️ IT TAKES A BLOCKING MUTEX (object 0x46c8c5f4, acquire 0x400009f4) and then
| runs a four step DSPI transfer with interrupts ENABLED. So: call it from a
| task, in supervisor mode, never from an interrupt handler, never from the
| per-frame DSP hook, and never re-entrantly, because the mutex is not
| recursive.
.equ	CLK_READ,	0x4001c4d8

| The field indices CLK_READ takes. Measured from the name builder's own calls
| and from the HH:MM:SS sibling at 0x40081a7c.
.equ	CLK_SEC,	1
.equ	CLK_MIN,	2
.equ	CLK_HOUR,	3
.equ	CLK_DAY,	5
.equ	CLK_MONTH,	6
.equ	CLK_YEAR,	7	| TWO DIGITS. Nothing adds 2000 for a file name.

| Convert one BCD byte to binary: (v >> 4) * 10 + (v & 15). One longword
| argument, result in %d0. cdecl. Preserves %d2-%d7 and %a2-%a6.
| ⚠️ It uses asrl on the whole longword. Feed it ONLY the zero extended byte
| that CLK_READ returns.
.equ	BCD2BIN,	0x4001c31c

| "%02d%02d%02d-%02d%02d", 21 characters and a terminator. Its arguments in
| order are year, month, day, hour, minute, all binary, so the result is
| YYMMDD-HHMM. Referenced from exactly one site in the image.
.equ	NAME_FMT,	0x400b77bb

| sprintf(dest, fmt, ...). cdecl varargs, caller pops. Preserves %d2-%d7 and
| %a2-%a6. ⚠️ NO LENGTH LIMIT. Size the destination yourself.
.equ	SPRINTF,	0x40013a08

| The stock recording name builder. NO arguments. Returns a pointer to its own
| static buffer 0x460faab4 in %d0, holding YYMMDD-HHMM. Blocks, because it
| calls CLK_READ five times.
| ⚠️ The buffer is overwritten on every call. Copy the string out at once.
| Use this OR build the name from CLK_READ directly. Both are recorded so that
| a module can avoid depending on a routine it does not need.
.equ	NAME_BUILD,	0x400819fc
.equ	NAME_BUF,	0x460faab4

| The CURRENT SET PATH, as a C string in place. This is the set folder, and it
| is what stems_make_path must use. It carries no trailing '/'.
| ✅ It begins with '/'. Measured under the port: see section 5.8.
.equ	SET_PATH,	0x100f8480

| The CURRENT PROJECT NAME, as a C string in place. Empty means no project.
.equ	PROJ_NAME,	0x100f8378

| The project directory: "<set>/<project>", or "<set>/UNTITLED" when the
| project name is empty. Two longword arguments, each 0 for the default:
|   clr.l -(%sp) / clr.l -(%sp) / jsr PROJ_DIR / addq.l #8,%sp
| Returns a pointer to the SHARED static buffer 0x460bf112 in %d0, and in %d0
| ONLY. Does not block. Preserves %d2-%d7 and %a2-%a6.
| ⚠️ 45 other sites share that buffer. STEM REC does not need this routine:
| build from SET_PATH instead. It is recorded because the plan named it.
.equ	PROJ_DIR,	0x40025230
.equ	PROJ_DIR_BUF,	0x460bf112

| Is a set mounted, with its AUDIO folder present? One argument, the set path.
| Returns non-zero in %d0 if both the set path and "<set>/AUDIO" exist. A cheap
| precondition before a take:
|   pea SET_PATH / jsr SET_MOUNTED / addq.l #4,%sp / tst.l %d0
.equ	SET_MOUNTED,	0x40025650

| The stock save's path formats, for reference. STEM REC needs its own,
| "%s/AUDIO/%s/T1.wav", because it writes a folder per take.
.equ	PATH_FMT_POOL,	0x400b3a85	| "%s/AUDIO/%s.wav"
.equ	PATH_FMT_PROJ,	0x400b3a95	| "%s/%s.wav"

| The personal setting that picks between them: 0 is AUD POOL, 1 is PROJ DIR.
| STEM REC IGNORES IT and always writes to the pool.
.equ	REC_SAVE_LOC,	0x800000a4
```

## 6. Creating a folder

STEM REC writes `<set>/AUDIO/YYMMDD-HHMM/T1.wav`, so it has to create the folder
`<set>/AUDIO/YYMMDD-HHMM` first. A folder-creation routine exists, it does
nothing but create the folder, and STEM REC can call it. `HAVE_MKDIR` is 1.

### 6.0 The answer, first ✅

The file layer is a table of function pointers in RAM. The folder-creation
entry is the pointer at `0x46c8240a`. On a card it holds `0x4001b0ac`. One
longword argument, the path. Returns 0 in `%d0` on success and a negative code
on failure. The parent must already exist, the path must not, and the path must
not end in `/`. It does not change the file layer's current directory. It takes
the same mutex as open, read and write, and it reads the real time clock, so it
blocks.

The rest of this section is the evidence, and the five stock call sites that fix
the convention.

### 6.1 How the routine was found ✅

The search started from the new-project path, as the brief's Step 1 directs.

✅ **The disassembler gate passed first.** `scripts/disasm.sh emac 0x40003664 8`
printed `msacl`, and the image's SHA-256 matched the header's. Every
disassembly in this section follows from that gate.

✅ **A byte search for `project.work` and `markers.work` found the creator's
neighbour, not the creator.** `"%s/%s/project.work"` sits at `0x400b5ccd`, with
one reference, `0x400646bc`. The routine that reads it, `0x40064624`, turned
out to be the project BROWSER, not CREATE NEW PROJECT. It was still useful: it
calls a file test through a pointer in RAM, `0x46c823fa`, not through a fixed
entry point. That is the pointer table 6.2 documents next.

✅ **Following the pointer led to its installer, then to a per-slot census.**
`0x4001451c` writes `0x46c823fa` and its neighbours, branching at `0x40014520`
to `0x40014636` depending on its argument, and `0x4001474c` is a separate
stub-table installer (6.2 has the detail). A linear objdump of the whole
image, grepped for every `moveal 0x46c82xxx`, split the sites inside the
installer's own range `0x40014000`-`0x40017000` from the sites outside it,
which gave a per-slot census of callers.

✅ **The census pointed at slot `0x46c8240a`.** Its neighbour `0x46c82406`
turned out to be a folder removal: `0x4008ec4c` deletes a project's `.work`
and `.strd` files and then calls `0x46c82406` on `"%s/%s"`. `0x46c8240a` had
five callers, all shaped "format a path, test exists, create" (6.3).

✅ **`0x40080fa4` settled it.** CREATE NEW SET makes `"/%s"` and then
`"/%s/AUDIO"` through slot `0x46c8240a`, parent first, with `"ERROR CREATING
SET DIR."` on failure (6.3). Nothing but a folder-creation routine has that
shape, so the search stopped there and moved to confirming the convention.

✅ **The last step disassembled the routine whole.** The card backend
`0x4001b0ac` behind the slot, and the path resolver `0x4001aa70` it calls,
gave the calling convention, the return codes and the attribute byte that the
rest of this section documents.

### 6.2 The file layer is a table of pointers, not a set of fixed entry points ✅

The routine at `0x4001451c` installs 23 function pointers into RAM, at
`0x46c823fa`, `0x46c823fe` and then `0x46c82402` through `0x46c82452` in steps
of 4. It has one longword argument and picks one of two backends from it:

```
4001451c:	4aaf 0004      	tstl %sp@(4)
40014520:	6600 0114      	bnew 0x40014636
```

The two installs of the slot this section is about:

```
40014584:	203c 4001 b874 	movel #1073854580,%d0
4001458a:	23c0 46c8 240a 	movel %d0,0x46c8240a
```

```
40014696:	203c 4001 b0ac 	movel #1073852588,%d0
4001469c:	23c0 46c8 240a 	movel %d0,0x46c8240a
```

objdump prints the immediates in decimal. 1073854580 is `0x4001b874` and
1073852588 is `0x4001b0ac`, which are also the operand bytes of the two `movel`
instructions.

✅ **The zero-argument backend is a stub set.** `0x4001b874` is two
instructions:

```
4001b874:	70ff           	moveq #-1,%d0
4001b876:	4e75           	rts
```

Its neighbours at `0x4001b878`, `0x4001b87c`, `0x4001b880` and `0x4001b884` are
the same two instructions, four bytes apart.

✅ **The card installs the non-zero backend.** `0x400169d4` calls the installer
with 1, right after a mount succeeds:

```
400169c2:	4879 460b ac0c 	pea 0x460bac0c
400169c8:	4eb9 4001 7ad4 	jsr 0x40017ad4
400169ce:	2400           	movel %d0,%d2
400169d0:	588f           	addql #4,%sp
400169d2:	660e           	bnes 0x400169e2
400169d4:	4878 0001      	pea 0x1
400169d8:	4eba db42      	jsr %pc@(0x4001451c)
```

The only other caller passes zero, in a mode that then writes 2 to
`0x460d1cb8`:

```
400616f2:	42a7           	clrl %sp@-
400616f4:	4eb9 4001 451c 	jsr 0x4001451c
400616fa:	7002           	moveq #2,%d0
400616fc:	23c0 460d 1cb8 	movel %d0,0x460d1cb8
```

🟡 **That second mode is believed to be the USB disk mode.** It is not needed
here. Falsifier: read `0x460d1cb8` under the port in both states.

There is a third install routine, at `0x4001474c`, whose whole table points into
`0x40014878` through `0x400148d0`, a run of 4-byte stubs. Four sites call it,
one of them at `0x40061714`, right after the teardown at `0x40014960`. 🟡 It is
the unmount table. Falsifier: a port run that unmounts and reads `0x46c8240a`.

**What follows for STEM REC.** The pointer is the interface, not the address
behind it. Read `0x46c8240a` and call through it, the way all five stock call
sites do, and check the return: in the stub state the call returns -1 rather
than crashing.

### 6.3 Slot `0x46c8240a` is the folder-creation routine ✅

Five instructions in the image read that slot. Counted from a linear objdump of
the whole image (`m68k-elf-objdump -D -b binary -m m68k:cfv4e
--adjust-vma=0x40000400`) grepped for `moveal 0x46c8240a`, which is the only
form any of them uses. A byte search for the address finds those five plus the
three installs (`0x4001458a`, `0x4001469c` and `0x400147b2`, the last being the
unmount table below), and nothing else. The five are `0x40063dd0`,
`0x400645a0`, `0x40080fa6`, `0x40080fc2` and `0x40090c24`.

All five have one shape: format a path, ask the "does it exist" slot
`0x46c823fa`, and on "no" call `0x46c8240a` with that path.

✅ **The decisive site is CREATE NEW SET**, because it creates two nested
folders in one routine, parent first:

```
40080f42:	4879 460f aa44 	pea 0x460faa44
40080f48:	4879 400b 79f0 	pea 0x400b79f0
40080f4e:	240e           	movel %fp,%d2
40080f50:	0682 ffff ffa8 	addil #-88,%d2
40080f56:	2f02           	movel %d2,%sp@-
40080f58:	45f9 4001 3a08 	lea 0x40013a08,%a2
40080f5e:	4e92           	jsr %a2@
40080f60:	2f02           	movel %d2,%sp@-
40080f62:	2079 46c8 23fa 	moveal 0x46c823fa,%a0
40080f68:	4e90           	jsr %a0@
40080f6a:	4fef 0010      	lea %sp@(16),%sp
40080f6e:	4a80           	tstl %d0
40080f70:	6732           	beqs 0x40080fa4
```

```
40080fa4:	2f02           	movel %d2,%sp@-
40080fa6:	2079 46c8 240a 	moveal 0x46c8240a,%a0
40080fac:	4e90           	jsr %a0@
40080fae:	2600           	movel %d0,%d3
40080fb0:	4879 460f aa44 	pea 0x460faa44
40080fb6:	4879 400b 7757 	pea 0x400b7757
40080fbc:	2f02           	movel %d2,%sp@-
40080fbe:	4e92           	jsr %a2@
40080fc0:	2f02           	movel %d2,%sp@-
40080fc2:	2079 46c8 240a 	moveal 0x46c8240a,%a0
40080fc8:	4e90           	jsr %a0@
40080fca:	4fef 0014      	lea %sp@(20),%sp
40080fce:	4a80           	tstl %d0
40080fd0:	6d04           	blts 0x40080fd6
40080fd2:	4a83           	tstl %d3
40080fd4:	6c30           	bges 0x40081006
```

`0x400b79f0` is `"/%s"` and `0x400b7757` is `"/%s/AUDIO"`. `0x400b7761`, the
message the failure branch shows, is `"ERROR CREATING SET DIR."`. So creating a
set is: make `/NAME`, then make `/NAME/AUDIO`, through the same slot, parent
first. Nothing but a folder-creation routine has that shape.

✅ **CREATE NEW PROJECT is the second proof**, with the error strings naming
what the slot did:

```
4006455e:	4879 100f 8480 	pea 0x100f8480
40064564:	4879 400b 86c1 	pea 0x400b86c1
4006456a:	240e           	movel %fp,%d2
4006456c:	0682 ffff ffa8 	addil #-88,%d2
40064572:	2f02           	movel %d2,%sp@-
40064574:	4eb9 4001 3a08 	jsr 0x40013a08
4006457a:	2f02           	movel %d2,%sp@-
4006457c:	2079 46c8 23fa 	moveal 0x46c823fa,%a0
40064582:	4e90           	jsr %a0@
40064584:	4fef 001c      	lea %sp@(28),%sp
40064588:	4a80           	tstl %d0
4006458a:	6712           	beqs 0x4006459e
4006458c:	203c 400b 58d3 	movel #1074485459,%d0
40064592:	2d40 fff8      	movel %d0,%fp@(-8)
40064596:	203c 400b 58e8 	movel #1074485480,%d0
4006459c:	6020           	bras 0x400645be
4006459e:	2f02           	movel %d2,%sp@-
400645a0:	2079 46c8 240a 	moveal 0x46c8240a,%a0
400645a6:	4e90           	jsr %a0@
400645a8:	588f           	addql #4,%sp
400645aa:	4a80           	tstl %d0
400645ac:	6c32           	bges 0x400645e0
400645ae:	203c 400b 58fa 	movel #1074485498,%d0
400645b4:	2d40 fff8      	movel %d0,%fp@(-8)
400645b8:	203c 400b 5cb5 	movel #1074486453,%d0
```

`0x400b86c1` is `"%s/%s"` and `0x100f8480` is the set path from section 5.8. The
argument pushed just before it, at `0x40064558`, is `0x460e436a`, the name the
user typed. The four message strings are:

```
0x400b58d3  'NAME ALREADY IN USE!'
0x400b58e8  'PLEASE TRY AGAIN.'
0x400b58fa  'ERROR CREATING PROJECT.'
0x400b5cb5  'CHECK CARD! (FULL?)'
```

So the exists slot guards the name and the `0x46c8240a` slot creates
`<set>/<project>`. `0x40063dce` is the same code again under SAVE TO NEW
(`0x400b58c7`), and `0x40090c22` is a third instance, with `"/"` at
`0x400b36a6`.

✅ **The neighbouring slot `0x46c82406` removes a folder**, which corroborates
the pair. The routine at `0x4008ec4c` deletes `project.work`, `project.strd`,
`markers.work`, `markers.strd`, `bank%02d.work` and `bank%02d.strd` for 16
banks, and `arr%02d.work` and `arr%02d.strd` for 8, and then does this:

```
4008ed5e:	2f2f 0018      	movel %sp@(24),%sp@-
4008ed62:	2f2f 0020      	movel %sp@(32),%sp@-
4008ed66:	4879 400b 86c1 	pea 0x400b86c1
4008ed6c:	240f           	movel %sp,%d2
4008ed6e:	0682 0000 002c 	addil #44,%d2
4008ed74:	2f02           	movel %d2,%sp@-
4008ed76:	4eb9 4001 3a08 	jsr 0x40013a08
4008ed7c:	2f02           	movel %d2,%sp@-
4008ed7e:	2079 46c8 2406 	moveal 0x46c82406,%a0
4008ed84:	4e90           	jsr %a0@
```

Empty the folder, then call `0x46c82406` on `"%s/%s"`. That is a folder removal,
and `0x46c8240a` is its neighbour in both backend tables.

### 6.4 It writes a directory entry with attribute `0x10` ✅

Step 2 of the brief is confirmed statically, in the card backend `0x4001b0ac`,
three times. Offset 11 of a 32-byte FAT directory entry is the attribute byte,
and bit 4 (`0x10`) marks the entry as a directory.

**The new entry in the parent's sector buffer.** `%d2` is the entry index,
`lsll #5,%d2` multiplies it by 32, and `0x4eceb200` is the sector buffer:

```
4001b1e0:	eb8a           	lsll #5,%d2
4001b1e2:	2042           	moveal %d2,%a0
4001b1e4:	d1fc 4ece b200 	addal #1322168832,%a0
4001b1ea:	1028 000b      	moveb %a0@(11),%d0
4001b1ee:	7a10           	moveq #16,%d5
4001b1f0:	8085           	orl %d5,%d0
4001b1f2:	1140 000b      	moveb %d0,%a0@(11)
```

1322168832 is `0x4eceb200`, which is also the operand bytes of the `addal`.

**The `"."` entry in the new cluster**, built at `0x4ece3200`. `0x400abdba` is
its 11-byte name field:

```
4001b27e:	4878 000b      	pea 0xb
4001b282:	4879 400a bdba 	pea 0x400abdba
4001b288:	4879 4ece 3200 	pea 0x4ece3200
4001b28e:	4eb9 4002 0898 	jsr 0x40020898
4001b294:	7210           	moveq #16,%d1
4001b296:	13c1 4ece 320b 	moveb %d1,0x4ece320b
```

`0x4ece320b` is `0x4ece3200 + 11`.

**The `".."` entry**, 32 bytes later at `0x4ece3220`:

```
4001b338:	4878 000b      	pea 0xb
4001b33c:	4879 400a bdc5 	pea 0x400abdc5
4001b342:	4879 4ece 3220 	pea 0x4ece3220
4001b348:	4eb9 4002 0898 	jsr 0x40020898
4001b34e:	7010           	moveq #16,%d0
4001b350:	13c0 4ece 322b 	moveb %d0,0x4ece322b
```

The first-cluster numbers go in at `+0x14` and `+0x1a` of each entry
(`0x4ece3214`, `0x4ece321a`, `0x4ece3234` and `0x4ece323a`), which is the FAT
split of a cluster number into a high word and a low word. The packed date and
time go to `+0x16` and `+0x18` (`0x4ece3216`, `0x4ece3218`, `0x4ece3236` and
`0x4ece3238`), from the two clock helpers in 6.8.

That is a FAT directory creation, written out longhand. No port run is needed
for step 2 of the brief.

### 6.5 Arguments, return and errors ✅

✅ **One longword argument, the path, cdecl, the caller pops.** cdecl here
means the caller pushes the arguments right to left and pops them after the
call (5.0's term note defines it the same way). Every one of the five call
sites pushes one longword and pops four bytes. The plainest:

```
40063dce:	2f02           	movel %d2,%sp@-
40063dd0:	2079 46c8 240a 	moveal 0x46c8240a,%a0
40063dd6:	4e90           	jsr %a0@
40063dd8:	588f           	addql #4,%sp
40063dda:	4a80           	tstl %d0
40063ddc:	6d10           	blts 0x40063dee
```

✅ **The return is `%d0`. Zero is success and negative is failure.** In the card
backend `%d4` is the return value, and it is written at exactly five places.
Here is the whole set, from a grep of the linear objdump restricted to
`0x4001b0ac` through `0x4001b3f2`:

```
4001b0c6:	78fc           	moveq #-4,%d4
4001b0e0:	78e8           	moveq #-24,%d4
4001b10a:	78f1           	moveq #-15,%d4
4001b120:	2800           	movel %d0,%d4
4001b15a:	78e7           	moveq #-25,%d4
4001b3e8:	2004           	movel %d4,%d0
```

Nothing else in the routine names `%d4`, and every callee preserves it, so the
success path carries out the zero that `0x4001b120` stored.

| value | site | what it means |
|---|---|---|
| 0 | falls through from `0x4001b120` | the folder was created ✅ |
| -4 | `0x4001b0c6` | the FAT mutex could not be taken ✅ |
| -24 | `0x4001b0e0` | no volume is mounted, `0x460bae2c` is zero ✅ |
| -15 | `0x4001b10a` | the path did not resolve to "only the last component is missing". The name exists already, or a parent does not, or the path ends in `/` ✅ |
| -25 | `0x4001b15a` | the cluster allocator at `0x400174ec` or `0x4001748c` returned -1 ✅ |
| other negative | `0x4001b120` | the directory-entry allocator `0x4001a1f8` failed 🟡 |

The first five are read straight off the branches that reach them. The last is
🟡 only in its name: what `0x4001a1f8` does was not disassembled, and
`"CHECK CARD! (FULL?)"` is the message its caller shows. Falsifier: fill a card
image under the port and read the code that comes back.

The lock-failure and not-mounted paths, whole:

```
4001b0b4:	4879 4610 79c0 	pea 0x461079c0
4001b0ba:	4eb9 4000 09f4 	jsr 0x400009f4
4001b0c0:	588f           	addql #4,%sp
4001b0c2:	4a80           	tstl %d0
4001b0c4:	6606           	bnes 0x4001b0cc
4001b0c6:	78fc           	moveq #-4,%d4
4001b0c8:	6000 031e      	braw 0x4001b3e8
4001b0cc:	4ab9 460b ae2c 	tstl 0x460bae2c
4001b0d2:	6610           	bnes 0x4001b0e4
4001b0d4:	4879 4610 79c0 	pea 0x461079c0
4001b0da:	4eb9 4000 0ab4 	jsr 0x40000ab4
4001b0e0:	78e8           	moveq #-24,%d4
```

✅ **It preserves `%d2` through `%d5`.** They are saved on entry and restored on
exit:

```
4001b0ac:	4e56 feb0      	linkw %fp,#-336
4001b0b0:	48d7 003c      	moveml %d2-%d5,%sp@
```

```
4001b3ea:	4cee 003c feb0 	moveml %fp@(-336),%d2-%d5
4001b3f0:	4e5e           	unlk %fp
4001b3f2:	4e75           	rts
```

🟡 **It preserves `%d6`, `%d7` and `%a2` through `%a6` as well.** No instruction
between `0x4001b0ac` and `0x4001b3f2` names any of them, and its callees follow
the same convention (`0x4001c5b8` and `0x4001c544` each save `%d2`, `%a2` and
`%a3`). Falsifier: one callee that does not. This is the only register claim in
the section that is not read off a save and a restore, so save them yourself if
that is cheap.

### 6.6 The path convention ✅

The path resolver is `0x4001aa70`. It takes the path and a 300-plus byte output
structure, and its return code is the only thing the folder routine tests:

```
4001b0e4:	240e           	movel %fp,%d2
4001b0e6:	0682 ffff fec2 	addil #-318,%d2
4001b0ec:	2f02           	movel %d2,%sp@-
4001b0ee:	2f2e 0008      	movel %fp@(8),%sp@-
4001b0f2:	4eba f97c      	jsr %pc@(0x4001aa70)
4001b0f6:	508f           	addql #8,%sp
4001b0f8:	72fd           	moveq #-3,%d1
4001b0fa:	b280           	cmpl %d0,%d1
4001b0fc:	6714           	beqs 0x4001b112
```

Anything but -3 becomes the -15 return. So the whole path convention is the
resolver's convention.

✅ **A leading `/` resolves from the root. Anything else resolves from the
current directory.** 47 is the ASCII code for `/`:

```
4001aa80:	7192           	mvzb %a2@,%d0
4001aa82:	722f           	moveq #47,%d1
4001aa84:	b280           	cmpl %d0,%d1
4001aa86:	6632           	bnes 0x4001aaba
4001aa88:	42ae fff4      	clrl %fp@(-12)
4001aa8c:	42ae fff8      	clrl %fp@(-8)
4001aa90:	42ae fffc      	clrl %fp@(-4)
```

```
4001aaba:	4878 000c      	pea 0xc
4001aabe:	4879 460b ae38 	pea 0x460bae38
4001aac4:	486e fff4      	pea %fp@(-12)
4001aac8:	4eb9 4002 0898 	jsr 0x40020898
```

The absolute case zeroes the 12 bytes of walking state. The relative case copies
them from `0x460bae38`, which is the current directory.

✅ **The parent must exist.** When a component is not found, the resolver looks
at the next character. If that character is `/`, so the missing component is not
the last one, it returns -2, and the folder routine turns that into -15:

```
4001ab3e:	72ff           	moveq #-1,%d1
4001ab40:	b280           	cmpl %d0,%d1
4001ab42:	66d0           	bnes 0x4001ab14
4001ab44:	7192           	mvzb %a2@,%d0
4001ab46:	742f           	moveq #47,%d2
4001ab48:	b480           	cmpl %d0,%d2
4001ab4a:	6604           	bnes 0x4001ab50
4001ab4c:	70fe           	moveq #-2,%d0
4001ab4e:	6056           	bras 0x4001aba6
4001ab50:	4878 0100      	pea 0x100
4001ab54:	4879 460b ae44 	pea 0x460bae44
4001ab5a:	2f0b           	movel %a3,%sp@-
4001ab5c:	4eb9 4001 3f5c 	jsr 0x40013f5c
4001ab62:	276e fff4 0132 	movel %fp@(-12),%a3@(306)
4001ab68:	70fd           	moveq #-3,%d0
```

-3 is also the only code that copies the missing name out to the caller, at
`0x4001ab5c`. That name is what the folder routine then creates.

✅ **No trailing `/`.** After a component the resolver skips separators and then
tests for the end of the string:

```
4001ab70:	528a           	addql #1,%a2
4001ab72:	1212           	moveb %a2@,%d1
4001ab74:	7181           	mvzb %d1,%d0
4001ab76:	782f           	moveq #47,%d4
4001ab78:	b880           	cmpl %d0,%d4
4001ab7a:	67f4           	beqs 0x4001ab70
4001ab7c:	4a01           	tstb %d1
4001ab7e:	671a           	beqs 0x4001ab9a
```

```
4001ab9a:	4a2b 010d      	tstb %a3@(269)
4001ab9e:	57c0           	seq %d0
4001aba0:	7100           	mvsb %d0,%d0
4001aba2:	7201           	moveq #1,%d1
4001aba4:	8081           	orl %d1,%d0
```

A path that ends in `/` reaches `0x4001ab9a` and returns 1 or -1, never -3. So
`"<set>/AUDIO/260910-1432/"` fails with -15, and
`"<set>/AUDIO/260910-1432"` is the form to pass.

✅ **The name must not exist already**, by the same rule: a resolved path
returns 1 or 0, not -3. The exists slot `0x46c823fa` in front of the call is the
stock way to tell that case apart, and it answers for a folder as well as a
file, which is what the "NAME ALREADY IN USE!" branch in 6.3 depends on.

**What Task 15 must pass.** `<set>/AUDIO/YYMMDD-HHMM`, built from `SET_PATH` as
section 5.8 says, with no trailing `/`, and only once `<set>/AUDIO` exists.

🟡 **`<set>/AUDIO` can be assumed to exist whenever a set is mounted.** Stock
creates it with the set (6.3), and the mount check `0x40025650` in section 5.8
formats `"%s/AUDIO"` and tests it. Falsifier: a user who deletes `AUDIO` from a
computer and then mounts the card. Cheap defence: call the exists slot on
`<set>/AUDIO` first and create it if it is missing, before creating the take
folder. It is the same call, so it costs a few instructions.

**One corroboration for section 5.8's leading-slash 🟡.** CREATE NEW SET formats
the folder it makes as `"/%s"` (6.3), so the folder stock creates for a set is
`/NAME`, at the root. That does not prove what `0x100f8480` holds afterwards,
which is still the port run listed in 5.10. It does mean that a set path without
a leading `/` would resolve against the current directory, which is a second
reason to settle 5.8 before flashing.

### 6.7 It does not change the current directory ✅

The current directory is the 12 bytes at `0x460bae38`, read by the resolver at
`0x4001aabe` above. Five instructions in the whole image name it, found by
grepping the linear objdump for the operand bytes `460b ae38`:

```
40016f48:	23c0 460b ae38 	movel %d0,0x460bae38
40017cfa:	42b9 460b ae38 	clrl 0x460bae38
40017de8:	42b9 460b ae38 	clrl 0x460bae38
4001aabe:	4879 460b ae38 	pea 0x460bae38
4001b540:	23c0 460b ae38 	movel %d0,0x460bae38
```

✅ **None of them is inside `0x4001b0ac` through `0x4001b3f2`.** The folder
routine reads the current directory through the resolver and never writes it.
Spec section 6 is satisfied by calling the slot as documented.

🟡 **`0x4001b540` is the change-directory routine's write.** It sits inside the
routine that begins at `0x4001b4f4`, which the installer puts in slot
`0x46c8242e`. STEM REC must never call slot `0x46c8242e`. Falsifier: a caller of
that slot that is not a directory change. The two `clrl` sites at `0x40017cfa`
and `0x40017de8` are 🟡 a mount or a media change resetting to the root.

### 6.8 It takes the same mutex as open, read and write, and it reads the clock ✅

✅ **The mutex object is `0x461079c0`**, acquired with `0x400009f4` and released
with `0x40000ab4`. Both routines are already ✅ in this document: section 5.2
measured `0x400009f4` as a blocking mutex acquire and `0x40000ab4` as the
release that hands the lock to the head waiter. The folder routine takes the
mutex at `0x4001b0b4`
(quoted in 6.5) and releases it on every exit, the last of them here:

```
4001b3d8:	4879 4610 79c0 	pea 0x461079c0
4001b3de:	4eb9 4000 0ab4 	jsr 0x40000ab4
4001b3e4:	4fef 0014      	lea %sp@(20),%sp
4001b3e8:	2004           	movel %d4,%d0
```

✅ **It is the same lock the rest of the file layer takes.** The card backend for
open takes it as its first act:

```
4001b57c:	4879 4610 79c0 	pea 0x461079c0
4001b582:	4eb9 4000 09f4 	jsr 0x400009f4
```

`0x4001b570` is slot `0x46c8242a`, the open. The write backend `0x40018a84`
(slot `0x46c82402`) takes it at `0x40018a98`, and the read backend `0x40018e40`
(slot `0x46c82426`) at `0x40018e50`. There are 34 `pea 0x461079c0` sites in
`0x4001b000` through `0x4001bfff` alone, and 113 occurrences of the address in
the image. So the FAT layer is one big lock, and the folder routine is inside it
exactly as open and write are. Task 8 owns the lock's own reading. This is the
pend seen on the way.

✅ **It also reads the real time clock, six times.** Two helpers fill the date
and the time before the entries are written:

```
4001b2a0:	486e fff8      	pea %fp@(-8)
4001b2a4:	4eb9 4001 c5b8 	jsr 0x4001c5b8
4001b2aa:	486e fffd      	pea %fp@(-3)
4001b2ae:	4eb9 4001 c544 	jsr 0x4001c544
```

`0x4001c5b8` calls `0x4001c4d8` with field indices 7, 6 and 5 and adds 2000 to
the year. `0x4001c544` calls it with 3, 2 and 1. `0x4001c4d8` is `CLK_READ` from
section 5.1, which takes the blocking SPI mutex `0x46c8c5f4` and runs a DSPI
transfer.

**What follows.** The call blocks, twice over. Call it from the writer task at
priority 1, the way section 5.2 says to call the clock. Never from the DSP hook
or an interrupt, and never while holding anything the UI task needs. Call it
once per take, before the file is opened, and never in the sample loop.

### 6.9 What else it does, and what it costs ✅ and 🟡

✅ **It creates a folder and nothing else.** No template is copied, no project
files are written, no setting is touched. The project files are written by the
CALLER, after the folder exists: `0x4008eda4` and `0x4008ee74` build
`"%s/bank%02d.work"` and the rest and write them through the buffered file API.
So the controller's "unless the extra work is harmless" clause does not apply.
`HAVE_MKDIR` is 1.

🟡 **Budget at least 1 KB of stack for the call.** The measured frames on the
path are 336 bytes for the folder routine itself (`linkw %fp,#-336`), 40 for the
resolver (`linkw %fp,#-40`), and 164 for the entry allocator
(`4001a1f8: linkw %fp,#-164`), plus their own callees, which were not walked to
the bottom. Falsifier, and the cheap check: a stack-watermark read under the
port after one call. This matters because section 3 sizes the writer task's
stack.

⚠️ **The sector buffers are shared.** `0x4eceb200` and `0x4ece3200` are the file
layer's own scratch, used under the mutex. That is one more reason not to hold
the call across anything.

### 6.10 Not measured under the port 🟡

No project folder exists on this machine, so nothing in this section was
executed. Four things a port run would settle, in the order they matter:

1. **One call on a scratch card, and the image read back.** Create
   `/SET/AUDIO/260910-1432` and read the directory entry with the FAT reader
   Task 9 adds. That turns 6.4's static reading into a measurement, and confirms
   the entry's attribute byte reaches the card as `0x10`, not only the buffer.
2. **The failure codes.** Call it twice with the same path and check that the
   second returns -15. Call it with a missing parent, and with a trailing `/`,
   and check both give -15.
3. **`0x46c8240a` after a mount, and after an unmount.** Confirm it holds
   `0x4001b0ac` while a card is mounted, which is what makes 6.2's stub warning
   real or idle.
4. **The stack watermark**, for 6.9.

### 6.11 Interface

```asm
| CREATE ONE FOLDER. This is a POINTER in RAM, not a fixed entry point: the
| file layer installs a backend when a card is mounted. Read the pointer and
| call through it, and check the return, because in the unmounted state the
| pointer holds a stub that returns -1.
|   movea.l FS_MKDIR_PTR,%a0
|   pea     path
|   jsr     %a0@
|   addq.l  #4,%sp
|   tst.l   %d0            | 0 created, negative failed
| ONE longword argument, a NUL terminated path. cdecl, the caller pops.
| Returns 0 in %d0 on success and a negative code on failure. Preserves
| %d2-%d5 measured, and %d6-%d7 and %a2-%a6 by inspection (6.5).
| The path is absolute if it begins with '/', otherwise it is relative to the
| file layer's current directory. THE PARENT MUST EXIST. The path must NOT
| exist already. NO trailing '/'. It does NOT change the current directory.
| ⚠️ IT BLOCKS TWICE: it takes the FAT mutex FS_LOCK, the one open, read and
| write also take, and it reads the clock six times through CLK_READ, which
| takes the SPI mutex. Call it from the writer task, once per take, before the
| file is opened. Never from the DSP hook or an interrupt.
.equ	HAVE_MKDIR,	1
.equ	FS_MKDIR_PTR,	0x46c8240a

| The brief's name for this interface resolves to the pointer slot above. The
| call form is the one already documented: movea.l FS_MKDIR_PTR,%a0 / jsr %a0@.
.equ	FS_MKDIR,	FS_MKDIR_PTR

| The card backend behind that pointer, for a port watch or a disassembly.
| DO NOT call it directly: it is only the right routine while a card is
| mounted.
.equ	FS_MKDIR_CARD,	0x4001b0ac

| The failure codes, read off FS_MKDIR_CARD (6.5).
.equ	FS_ERR_LOCK,	-4	| the FAT mutex could not be taken
.equ	FS_ERR_NOVOL,	-24	| no volume mounted
.equ	FS_ERR_PATH,	-15	| exists, or parent missing, or trailing '/'
.equ	FS_ERR_NOCLUST,	-25	| no free cluster

| DOES A PATH EXIST? Same table, same shape: one longword path argument, and
| non-zero in %d0 if it exists. It answers for a FOLDER as well as a file.
| Call it before FS_MKDIR_PTR, the way all five stock sites do, and call it on
| "<set>/AUDIO" too if you want to be safe about the pool folder (6.6).
.equ	FS_EXISTS_PTR,	0x46c823fa

| Remove an EMPTY folder. Recorded for completeness. STEM REC does not use it.
.equ	FS_RMDIR_PTR,	0x46c82406

| CHANGE DIRECTORY. ⚠️ NEVER CALL THIS. It writes FS_CWD, and spec section 6
| says STEM REC must never change the file layer's current directory.
.equ	FS_CHDIR_PTR,	0x46c8242e

| The file layer's current directory, 12 bytes, and its one big mutex. Both
| are here so that a port watch can prove STEM REC leaves them alone.
.equ	FS_CWD,		0x460bae38
.equ	FS_LOCK,	0x461079c0
```

## 7. Two tasks on one card

STEM REC's writer task and the stock storage task both call the buffered file
API. Section 6 already measured one lock, `FS_LOCK` (`0x461079c0`), taken by
the folder-creation routine. This section measures the same lock for open,
write, seek and close, and asks whether it is enough.

### 7.0 The answer, first ✅

Yes, with the FAT lock. Open, the buffered write's flush, seek, and the
buffered close's flush all reach a raw card-backend routine that takes
`FS_LOCK` as its first act and holds it across that backend's whole body,
releasing on every exit path this section found. Two tasks calling OPEN,
WRITE, SEEK or CLOSE at the same time cannot corrupt the FAT structures: the
lock serialises them, the same way section 6 measured for folder creation.
One correction from the review round: a READ-mode open reaches TWO such
backends, one after the other, with a gap between the two holds where
`FS_LOCK` is free (section 7.1). Nothing FAT-structural is exposed in that
gap; STEM REC opens only in write mode, where the wrapper reaches exactly
one backend, so this does not apply to STEM REC's own calls.

One thing changes the picture. The buffered layer stages every block of data
through one shared global buffer, `0x4ecd3000`, before the raw call that takes
the lock. That copy is unprotected. Two tasks whose buffered writes (or a
write and a read) fill or flush at the same instant can corrupt each other's
in-flight DATA, even though the FAT METADATA stays correct because the lock
still serialises the actual sector operation. Section 7.5 has the evidence.
This belongs in the flash notes as a real, if narrow, exposure: it needs two
tasks racing on the SAME shared buffer, not merely two tasks holding open
files.

### 7.1 The four routines the brief names are a buffered layer, and none of them takes FS_LOCK ✅

Open (`0x40016864`), the buffered write (`0x400166b8`), seek (`0x4001660c`)
and the buffered close (`0x4001677c`) are a small stdio-like layer over the
pointer-table backends section 6.2 already found. None of them pushes
`0x461079c0`; each forwards to the pointer-table slot instead. Read whole,
open:

```
40016864:	4fef fff4      	lea %sp@(-12),%sp
40016868:	48d7 0c04      	moveml %d2/%a2-%a3,%sp@
4001686c:	246f 0010      	moveal %sp@(16),%a2
40016870:	266f 0018      	moveal %sp@(24),%a3
40016874:	4a8a           	tstl %a2
40016876:	675c           	beqs 0x400168d4
40016878:	256f 001c 0004 	movel %sp@(28),%a2@(4)
4001687e:	256f 0020 0008 	movel %sp@(32),%a2@(8)
40016884:	42aa 0010      	clrl %a2@(16)
40016888:	2f0b           	movel %a3,%sp@-
4001688a:	2f2f 0018      	movel %sp@(24),%sp@-
4001688e:	2079 46c8 242a 	moveal 0x46c8242a,%a0
40016894:	4e90           	jsr %a0@
```

`0x46c8242a` is the same open slot section 6.8 measured, behind which is
`0x4001b570`. `%a2` is the caller's file object (five fields are visible
here: offset 4 the I/O buffer pointer, offset 8 the buffer size, offset 16
cleared, and later offset 0 the handle and offset 20 the mode byte). `%a3` is
the mode string; its first byte is stored into `%a2@(20)` a few lines further
down, and the SAME byte, pushed again, becomes the raw open's second argument.

✅ **Open calls a SIXTH slot after the raw open already released `FS_LOCK`,
on a read-mode open.** The rest of the wrapper, read whole:

```
40016896:	2200           	movel %d0,%d1
40016898:	508f           	addql #8,%sp
4001689a:	6d3e           	blts 0x400168da
4001689c:	2480           	movel %d0,%a2@
4001689e:	1553 0014      	moveb %a3@,%a2@(20)
400168a2:	5380           	subql #1,%d0
400168a4:	0c80 0000 01fe 	cmpil #510,%d0
400168aa:	6228           	bhis 0x400168d4
400168ac:	42aa 000c      	clrl %a2@(12)
400168b0:	7113           	mvsb %a3@,%d0
400168b2:	7472           	moveq #114,%d2
400168b4:	b480           	cmpl %d0,%d2
400168b6:	6620           	bnes 0x400168d8
400168b8:	2f01           	movel %d1,%sp@-
400168ba:	2079 46c8 241e 	moveal 0x46c8241e,%a0
400168c0:	4e90           	jsr %a0@
400168c2:	588f           	addql #4,%sp
400168c4:	4a80           	tstl %d0
400168c6:	6610           	bnes 0x400168d8
400168c8:	2f0a           	movel %a2,%sp@-
400168ca:	4eba feb0      	jsr %pc@(0x4001677c)
400168ce:	72f6           	moveq #-10,%d1
400168d0:	588f           	addql #4,%sp
400168d2:	6006           	bras 0x400168da
400168d4:	72fe           	moveq #-2,%d1
400168d6:	6002           	bras 0x400168da
400168d8:	7201           	moveq #1,%d1
400168da:	2001           	movel %d1,%d0
```

`0x72` is `114` decimal, ASCII `'r'`, which is exactly the immediate
`moveq #114,%d2` encodes as opcode `7472` (`0x72` in the low byte). The
byte-level encoding of the compare settles the direction: `cmpl %d0,%d2` is
opcode `0xb480` = `1011 010 010 000 000`, which decodes to register field
`010` (`%d2`, the destination) and effective-address field `000 000`
(`%d0`, data-register-direct, the source), so the instruction computes
`%d2 - %d0` and `bnes` (branch on `Z` clear) is taken when the mode byte is
**NOT** `'r'`. **So the call to slot `0x46c8241e` happens on a
READ-mode open, not a write-mode one** (the sample save's own call, section
5.6, mode `"w"`, never reaches it). `0x46c8241e`'s card backend is
`0x40018a0c`:

```
40018a0c:	2f03           	movel %d3,%sp@-
40018a0e:	2f02           	movel %d2,%sp@-
40018a10:	242f 000c      	movel %sp@(12),%d2
40018a14:	4879 4610 79c0 	pea 0x461079c0
40018a1a:	4eb9 4000 09f4 	jsr 0x400009f4
40018a20:	588f           	addql #4,%sp
40018a22:	4a80           	tstl %d0
40018a24:	6756           	beqs 0x40018a7c
...
40018a32:	4879 4610 79c0 	pea 0x461079c0
40018a38:	4eb9 4000 0ab4 	jsr 0x40000ab4
40018a3e:	6024           	bras 0x40018a64
...
40018a5c:	4879 4610 79c0 	pea 0x461079c0
40018a62:	4e90           	jsr %a0@
...
40018a68:	4879 4610 79c0 	pea 0x461079c0
40018a6e:	4e90           	jsr %a0@
```

✅ `0x40018a0c` DOES take `FS_LOCK` (`0x461079c0`), as its first act, and
releases it on every exit found (three release sites: the immediate-fail
skip at `0x40018a24` needs none, and three `pea`/`jsr` pairs at `0x40018a32`,
`0x40018a5c`-`0x40018a62`, and `0x40018a68`-`0x40018a6e` cover the rest).
**This is a SECOND, independent acquire/release cycle, not a continuation of
open's hold**: the raw open backend (`0x4001b570`) already released
`FS_LOCK` at its own exit (section 7.2) before the wrapper reaches this
point, so there is a GAP between the two holds during which `FS_LOCK` is
free. If it returns 0 (invalid/empty), the wrapper closes the file it just
opened, recursing into the close wrapper (`0x4001677c`, at `0x400168ca`),
and returns `-10`. **The close wrapper's own body does not take `FS_LOCK`**
(7.1 already established this for all four wrapper bodies), but tracing THIS
specific call, in execution order:

`%a2@` (offset 0, the handle) is NOT zero here. Open stored the raw open's
return there and range-checked it before the recursive close:

```
40016896:	2200           	movel %d0,%d1
40016898:	508f           	addql #8,%sp
4001689a:	6d3e           	blts 0x400168da
4001689c:	2480           	movel %d0,%a2@
...
400168a2:	5380           	subql #1,%d0
400168a4:	0c80 0000 01fe 	cmpil #510,%d0
400168aa:	6228           	bhis 0x400168d4
```

So close's own handle range check on `%a2@`, its first test after the mode
check, is not taken (the handle is valid):

```
400167a4:	2012           	movel %a2@,%d0
400167a6:	5380           	subql #1,%d0
400167a8:	0c80 0000 01fe 	cmpil #510,%d0
400167ae:	6200 00aa      	bhiw 0x4001685a
```

**The field that gates the flush skip is `%a2@(12)`, not `%a2@`.** Open
clears it unconditionally, right after the handle range check above passes:

```
400168ac:	42aa 000c      	clrl %a2@(12)
```

Nothing between there and the recursive close call (`0x400168ca`) writes it
again (the intervening code only reads `%a3@`, the mode byte, and calls the
sixth-slot check, 7.1). Close reads the SAME field next and skips the
write-flush test when it is zero:

```
400167b2:	222a 000c      	movel %a2@(12),%d1
400167b6:	675e           	beqs 0x40016816
```

`%a2@(12)` is still `0` on this path, so the branch IS taken.

✅ `%a2@(12)` is the buffered write's fill position: the number of bytes
staged in the file object's own buffer since the last flush. The evidence
is the write wrapper, `0x400166b8` (`scripts/disasm.sh emac 0x400166b8 168`,
gate run first). For each byte of the caller's data, it reads the field,
uses it as the index into the buffer at `%a2@(4)`, stores the byte there,
increments the field and writes it back. It then compares the field with
the buffer size at `%a2@(8)`, and skips the flush while the size is still
greater:

```
400166e2:	202a 000c      	movel %a2@(12),%d0
400166e6:	206a 0004      	moveal %a2@(4),%a0
400166ea:	43f4 2800      	lea %a4@(0,%d2:l),%a1
400166ee:	1191 0800      	moveb %a1@,%a0@(0,%d0:l)
400166f2:	5280           	addql #1,%d0
400166f4:	2540 000c      	movel %d0,%a2@(12)
400166f8:	222a 0008      	movel %a2@(8),%d1
400166fc:	b280           	cmpl %d0,%d1
400166fe:	6e3a           	bgts 0x4001673a
```

When the buffer is full, the wrapper flushes it through the write slot
(`0x40016700`-`0x40016726`, quoted later in this section). Right after
that call it clears the field on both outcomes: `0x40016730` on the failure
exit, `0x40016736` on the success path. On the success path the loop then
repeats for the next byte until `%d2` reaches the caller's count at
`%sp@(28)`:

```
4001672c:	4a80           	tstl %d0
4001672e:	6c06           	bges 0x40016736
40016730:	42aa 000c      	clrl %a2@(12)
40016734:	6016           	bras 0x4001674c
40016736:	42aa 000c      	clrl %a2@(12)
4001673a:	52aa 0010      	addql #1,%a2@(16)
4001673e:	5282           	addql #1,%d2
40016740:	b4af 001c      	cmpl %sp@(28),%d2
40016744:	659c           	bcss 0x400166e2
```

So mode `'r'` and `%a2@(12) == 0`, not "buffer position 0"
on `%a2@` (which is the handle, and is valid), make close skip the
write-flush test entirely and fall straight to the handle release, slot
`0x46c82422`, backend `0x40019900`, whole:

```
40019900:	4e56 ffe0      	linkw %fp,#-32
40019904:	48d7 0c3c      	moveml %d2-%d5/%a2-%a3,%sp@
40019908:	262e 0008      	movel %fp@(8),%d3
4001990c:	4879 4610 79c0 	pea 0x461079c0
40019912:	4eb9 4000 09f4 	jsr 0x400009f4
40019918:	588f           	addql #4,%sp
4001991a:	4a80           	tstl %d0
4001991c:	6606           	bnes 0x40019924
4001991e:	70fc           	moveq #-4,%d0
40019920:	6000 0282      	braw 0x40019ba4
```

✅ `0x40019900` DOES take `FS_LOCK` as its first act, so close's read-mode
error path takes and releases it a THIRD time for this one open call, but
through `0x40019900`, not through the wrapper's own body. Two release sites
found:

```
40019930:	4879 4610 79c0 	pea 0x461079c0
40019936:	4eb9 4000 0ab4 	jsr 0x40000ab4
4001993c:	70f5           	moveq #-11,%d0
4001993e:	6000 0262      	braw 0x40019ba2
```
```
40019984:	4879 4610 79c0 	pea 0x461079c0
4001998a:	4eb9 4000 0ab4 	jsr 0x40000ab4
40019990:	70fd           	moveq #-3,%d0
40019992:	6000 020e      	braw 0x40019ba2
```

🟡 Only the first ~150 bytes of `0x40019900` were read; the routine
continues past `0x400199c2` into work not disassembled here (it reads a
per-descriptor flag at `%d1@(24)` and, on one path, indirects through
`0x4694886e`, the same table write's backend used, section 7.2). The two
releases above are not necessarily every exit; falsifier: read the rest of
`0x40019900` and confirm every remaining path releases before returning. The
table entry for `0x46c82422` in 7.1 is corrected below: partially
disassembled now, for its lock bracket only.

⚠️ **What is, and is not, at risk in the gap.** Nothing FAT-structural: the
gap is bounded by two lock-protected operations that each leave the FAT
consistent on their own exit, so another task's open/write/close between
them sees a consistent filesystem either way. This is not a hole in the
FAT locking, only a loss of ATOMICITY across the open-then-check sequence
as a whole. What it does mean: a file this wrapper just opened for reading
could, in principle, be renamed, truncated, or reopened by another task
between the raw open's release and `0x40018a0c`'s acquire, and the read-mode
check would then run against whatever state the file is in at that later
instant, not the state at open time. STEM REC opens only in write mode
(spec section 6), so this specific gap does not apply to its own calls; it
matters only if the design later reads a file through this same wrapper.

The buffered write's flush and the buffered close's flush both forward to the
same write slot, `0x46c82402` (`0x40018a84`, also measured in section 6.8):

```
40016700:	2f01           	movel %d1,%sp@-
40016702:	2f2a 0004      	movel %a2@(4),%sp@-
40016706:	4879 4ecd 3000 	pea 0x4ecd3000
4001670c:	4e93           	jsr %a3@
4001670e:	202a 0008      	movel %a2@(8),%d0
40016712:	7209           	moveq #9,%d1
40016714:	e2a0           	asrl %d1,%d0
40016716:	2f00           	movel %d0,%sp@-
40016718:	4879 4ecd 3000 	pea 0x4ecd3000
4001671e:	2f12           	movel %a2@,%sp@-
40016720:	2079 46c8 2402 	moveal 0x46c82402,%a0
40016726:	4e90           	jsr %a0@
```

```
400167f0:	4879 4ecd 3000 	pea 0x4ecd3000
400167f6:	4eb9 4002 08d4 	jsr 0x400208d4
400167fc:	2f02           	movel %d2,%sp@-
400167fe:	4879 4ecd 3000 	pea 0x4ecd3000
40016804:	2f12           	movel %a2@,%sp@-
40016806:	2079 46c8 2402 	moveal 0x46c82402,%a0
4001680c:	4e90           	jsr %a0@
```

Close also calls two more slots after the flush, `0x46c82436` (only on a
successful write flush) and `0x46c82422` unconditionally, the second being
the handle release:

```
4001683c:	2f12           	movel %a2@,%sp@-
4001683e:	2079 46c8 2422 	moveal 0x46c82422,%a0
40016844:	4e90           	jsr %a0@
```

Seek forwards to a fifth slot, `0x46c8243e` (`0x4001858c`), with a tail call
rather than a call-and-return:

```
40016678:	2f42 0010      	movel %d2,%sp@(16)
4001667c:	2f52 000c      	movel %a2@,%sp@(12)
40016680:	2279 46c8 243e 	moveal 0x46c8243e,%a1
40016686:	241f           	movel %sp@+,%d2
40016688:	245f           	moveal %sp@+,%a2
4001668a:	4ed1           	jmp %a1@
```

The slot table itself was read from the card-mode installer, `0x40014636`
onward (the argument-1 branch of `0x4001451c`, section 6.2's installer), the
same way section 6.2 read `0x46c8240a`. The SIX slots this section needs, all
confirmed by their address appearing as the `movel`'d immediate at the
matching `.equ` line:

| slot | card backend |
|---|---|
| `0x46c8242a` (open) | `0x4001b570` |
| `0x46c8241e` (read-mode open's post-check) | `0x40018a0c` |
| `0x46c82402` (write) | `0x40018a84` |
| `0x46c8243e` (seek) | `0x4001858c` |
| `0x46c82436` (finalize on write close) | `0x40018788`, not disassembled here |
| `0x46c82422` (release handle) | `0x40019900`, lock bracket only (below) |

None of the four wrapper bodies (`0x40016864`-`0x400168e6`, `0x400166b8`-
`0x40016758`, `0x4001660c`-`0x40016694`, `0x4001677c`-`0x40016864`) contains
the byte sequence for `0x461079c0`, read from each routine's full
disassembly above. The lock is entirely the raw and post-check backends'
business, and one open (in read mode) can reach it twice, in two separate
holds (above).

### 7.2 Each raw backend holds the lock across its OWN body, released on every exit ✅

This is the corrected claim: `FS_LOCK` is held across the whole body of
EACH raw backend, not across the whole WRAPPER call. For write, seek, and a
write-mode open, that is the same thing, because the wrapper reaches exactly
one lock-taking backend. For a READ-mode open it is not: 7.1 already showed
two separate holds with a gap between them (the raw open, then, only on a
successful read-mode open, `0x40018a0c`). Read each backend on its own
terms.

**Open**, `0x4001b570`-`0x4001b722`. Section 6.8 already quoted the acquire;
repeated here because this section's claim is about the WHOLE routine, not
just the first instruction:

```
4001b57c:	4879 4610 79c0 	pea 0x461079c0
4001b582:	4eb9 4000 09f4 	jsr 0x400009f4
4001b588:	588f           	addql #4,%sp
4001b58a:	4a80           	tstl %d0
4001b58c:	6606           	bnes 0x4001b594
4001b58e:	74fc           	moveq #-4,%d2
4001b590:	6000 0176      	braw 0x4001b708
```

`0x400009f4` returns 0 when the mutex could not be taken (this is section
5.2's blocking acquire; the 0 case is a defensive check, not a timeout, since
`0x400009f4` blocks rather than fails). If it returns non-zero the routine
falls through holding the lock, and calls the shared path resolver
(`0x4001aa70`, section 6.6) and, on the create path, the directory-entry
allocator (`0x4001a1f8`, the same routine section 6.5 named but did not
disassemble), both WHILE HOLDING the lock:

```
4001b5b2:	4eba f4bc      	jsr %pc@(0x4001aa70)
...
4001b5da:	4eba ec1c      	jsr %pc@(0x4001a1f8)
```

Four release sites, each pairing `pea 0x461079c0` with `jsr 0x40000ab4`
(section 5.2's release) before returning:

```
4001b5ee:	4879 4610 79c0 	pea 0x461079c0
4001b5f4:	4eb9 4000 0ab4 	jsr 0x40000ab4
4001b5fa:	74f4           	moveq #-12,%d2
4001b5fc:	6000 0108      	braw 0x4001b706
```
```
4001b606:	4879 4610 79c0 	pea 0x461079c0
4001b60c:	4eb9 4000 0ab4 	jsr 0x40000ab4
4001b612:	74ee           	moveq #-18,%d2
4001b614:	6000 00f0      	braw 0x4001b706
```
```
4001b6fa:	4879 4610 79c0 	pea 0x461079c0
4001b700:	4eb9 4000 0ab4 	jsr 0x40000ab4
4001b706:	588f           	addql #4,%sp
4001b708:	2002           	movel %d2,%d0
4001b70a:	4cd7 041c      	moveml %sp@,%d2-%d4/%a2
4001b70e:	4fef 0148      	lea %sp@(328),%sp
4001b712:	4e75           	rts
```
```
4001b714:	4879 4610 79c0 	pea 0x461079c0
4001b71a:	4eb9 4000 0ab4 	jsr 0x40000ab4
4001b720:	74ef           	moveq #-17,%d2
4001b722:	60e2           	bras 0x4001b706
```

Every exit checked: the immediate acquire-fail path (no release, correct,
because the lock was never taken) plus these four, and nothing between the
acquire and any of the four releases returns without going through one of
them. ✅ **This ONE backend holds `FS_LOCK` across its WHOLE body**, not
narrowly around a sector-I/O step: path resolution and directory-entry
allocation both happen while it is held. ⚠️ It is not the whole `0x40016864`
wrapper call: on a read-mode open, the wrapper reaches this backend, lets it
release, and then reaches a SECOND lock-taking backend (`0x40018a0c`, 7.1)
with a gap between the two holds.

**Write**, `0x40018a84`. Same shape, acquire first:

```
40018a98:	4879 4610 79c0 	pea 0x461079c0
40018a9e:	4eb9 4000 09f4 	jsr 0x400009f4
40018aa4:	588f           	addql #4,%sp
40018aa6:	4a80           	tstl %d0
40018aa8:	6606           	bnes 0x40018ab0
40018aaa:	70fc           	moveq #-4,%d0
40018aac:	6000 0386      	braw 0x40018e34
```

Five release sites, each `pea 0x461079c0` / `jsr 0x40000ab4`, four failures
and the success exit:

```
40018abc:	4879 4610 79c0 	pea 0x461079c0
40018ac2:	4eb9 4000 0ab4 	jsr 0x40000ab4
40018ac8:	70f5           	moveq #-11,%d0
40018aca:	6000 0366      	braw 0x40018e32
```
```
40018aee:	4879 4610 79c0 	pea 0x461079c0
40018af4:	4eb9 4000 0ab4 	jsr 0x40000ab4
40018afa:	70fd           	moveq #-3,%d0
40018afc:	6000 0334      	braw 0x40018e32
```
```
40018b30:	4879 4610 79c0 	pea 0x461079c0
40018b36:	4eb9 4000 0ab4 	jsr 0x40000ab4
40018b3c:	70e8           	moveq #-24,%d0
40018b3e:	6000 02f2      	braw 0x40018e32
```
```
40018d92:	4879 4610 79c0 	pea 0x461079c0
40018d98:	4eb9 4000 0ab4 	jsr 0x40000ab4
40018d9e:	70e7           	moveq #-25,%d0
40018da0:	6000 0090      	braw 0x40018e32
```
```
40018e1c:	4879 4610 79c0 	pea 0x461079c0
40018e22:	4eb9 4000 0ab4 	jsr 0x40000ab4
40018e28:	71b9 4610 7990 	mvzb 0x46107990,%d0
40018e2e:	7209           	moveq #9,%d1
40018e30:	e3a8           	lsll %d1,%d0
40018e32:	588f           	addql #4,%sp
```

`-24` matches the folder routine's "no volume mounted" code (section 6.5's
table), read from the same `tstl 0x460bae2c` idiom. Between the acquire and
the final release, write calls a cluster allocator PC-relative
(`0x4001754c`, the write-side sibling of the folder routine's allocator) and,
further on, an indirect call through a per-descriptor function-pointer table:

```
40018b42:	4eba ea08      	jsr %pc@(0x4001754c)
...
40018dc8:	4e90           	jsr %a0@
```

`%a0` there is loaded through two indirections, `moveal 0x4694886e,%a0` then
`moveal %a0@(4),%a0`. 🟡 This was not traced to a name; its position (between
the cluster allocator and the final directory-entry bookkeeping, all still
inside the lock) is consistent with the actual sector write, but that is
inferred, not confirmed. Falsifier: disassemble the target and confirm it
reaches the ATA WRITE SECTORS handler section EMU.md names (`0x40014c48`).
✅ What IS confirmed: nothing between the acquire (`0x40018a98`) and the five
releases returns without releasing, so write also holds `FS_LOCK` across its
whole call, cluster allocation and the indirect call both included.

**Seek**, `0x4001858c`. Same acquire-first shape:

```
4001859c:	4879 4610 79c0 	pea 0x461079c0
400185a2:	4eb9 4000 09f4 	jsr 0x400009f4
400185a8:	588f           	addql #4,%sp
400185aa:	4a80           	tstl %d0
400185ac:	6606           	bnes 0x400185b4
400185ae:	70fc           	moveq #-4,%d0
400185b0:	6000 01cc      	braw 0x4001877e
```

Three release sites found in the disassembled range:

```
400185c0:	4879 4610 79c0 	pea 0x461079c0
400185c6:	4eb9 4000 0ab4 	jsr 0x40000ab4
400185cc:	70f5           	moveq #-11,%d0
400185ce:	6000 01ac      	braw 0x4001877c
```
```
400185ec:	4879 4610 79c0 	pea 0x461079c0
400185f2:	4eb9 4000 0ab4 	jsr 0x40000ab4
400185f8:	70fd           	moveq #-3,%d0
400185fa:	6000 0180      	braw 0x4001877c
```
```
40018610:	4879 4610 79c0 	pea 0x461079c0
40018616:	4eb9 4000 0ab4 	jsr 0x40000ab4
4001861c:	70fe           	moveq #-2,%d0
4001861e:	6000 015c      	braw 0x4001877c
```

🟡 **The success exit was not reached.** Seek's body continues past
`0x400186c6` into position-update work not disassembled here, so this
section did not read its final release. Falsifier: disassemble
`0x4001858c` through its `rts` and confirm a fourth `pea 0x461079c0` /
`jsr 0x40000ab4` pair guards the success path the same way open's and
write's do. Given the consistent shape of the other two, and that seek has
no reason to hold the lock past updating its own position field, this is
treated as the same pattern, not as measured.

Open (`0x4001b570`), write (`0x40018a84`) and seek (`0x4001858c`) are each
named by exactly one `jsr` in the whole image, per a linear-objdump grep of
each address: their own label line, and nothing else. ✅ The pointer-table
slot is the ONLY way to reach them, so the buffered wrapper is the sole path
in, and `FS_LOCK` guards every reachable route to the FAT-touching work.

### 7.3 The ATA lock is a separate, lower, non-blocking lock, and it never appears in the FAT-layer code ✅ with one 🟡

The ATA lock EMU.md names, `0x460bae18`, is not the same object as `FS_LOCK`.
It is a try-lock, not a blocking mutex: it masks interrupts, tests-and-sets
the word, and on failure returns instead of blocking:

```
400150ac:	40c1           	movew %sr,%d1
400150ae:	46fc 2700      	movew #9984,%sr
400150b2:	2039 460b ae18 	movel 0x460bae18,%d0
400150b8:	6704           	beqs 0x400150be
400150ba:	4280           	clrl %d0
400150bc:	6008           	bras 0x400150c6
400150be:	7001           	moveq #1,%d0
400150c0:	23c0 460b ae18 	movel %d0,0x460bae18
400150c6:	46c1           	movew %d1,%sr
400150c8:	4a80           	tstl %d0
400150ca:	6700 01c4      	beqw 0x40015290
```

`refs.sh 0x460bae18` finds 17 hits, all of them between `0x400150b4` and
`0x4001611c`. ✅ That whole range is the ATA driver EMU.md describes (the PIO
handlers it names, `0x40014b94`, `0x40014c48`, `0x400159bc`, sit just below
it). None of the 17 falls inside any of the FAT-layer addresses this section
or section 6 disassembled: not the four wrappers, not open, write, seek, or
folder-create.

🟡 **Nesting is inferred, not traced.** This section confirmed the ATA lock's
code never appears in the FAT-layer routines by ADDRESS, and separately that
write's raw backend makes an indirect call, still holding `FS_LOCK`, to
something not identified by name (7.2). It did not trace that indirect call
down to `0x400150ac` itself. The architectural picture, consistent with
EMU.md's description of the ATA layer as a register-pushing driver with no
knowledge of paths or files, is that `FS_LOCK` is the outer lock and the ATA
lock is inner, taken only during the sector transfer a FAT routine already
holds `FS_LOCK` to perform. Falsifier: a port run with a write-watch on both
locks during one write, showing the ATA lock is never held while `FS_LOCK` is
free, and never taken by anything that is not already inside a `FS_LOCK`
critical section.

### 7.4 The current directory is read, never written, by open, write or seek ✅

Section 6.7 already found the whole image's five writers of `FS_CWD`
(`0x460bae38`): `0x40016f48`, `0x40017cfa`, `0x40017de8`, `0x4001aabe`, and
`0x4001b540`. None of those five addresses falls inside open
(`0x4001b570`-`0x4001b722`), write (`0x40018a84`-`0x40018e34`) or seek
(`0x4001858c`-`0x40018700`, the range disassembled). ✅ The one READ of
`FS_CWD`, `0x4001aabe`, is inside the shared path resolver, and section 7.2
shows the resolver is only reached from open while `FS_LOCK` is held. So the
current directory is touched by these three routines exactly the way the
folder routine touches it: read under the lock, never written.

### 7.5 The shared sector staging buffer is touched OUTSIDE the lock 🟡

Both flushes quoted in 7.1 copy the caller's data into ONE fixed address,
`0x4ecd3000`, through a plain memcpy, BEFORE the call that takes `FS_LOCK`:

```
40016706:	4879 4ecd 3000 	pea 0x4ecd3000
4001670c:	4e93           	jsr %a3@
```

`%a3` was loaded earlier in the same routine as `lea 0x400208d4,%a3`
(section's write-flush quote in 7.1), so the call is `0x400208d4`, whole:

```
400208d4:	4fef fff0      	lea %sp@(-16),%sp
400208d8:	48d7 003c      	moveml %d2-%d5,%sp@
400208dc:	226f 0014      	moveal %sp@(20),%a1
400208e0:	206f 0018      	moveal %sp@(24),%a0
400208e4:	2a2f 001c      	movel %sp@(28),%d5
400208e8:	7010           	moveq #16,%d0
400208ea:	600c           	bras 0x400208f8
400208ec:	4cd0 001e      	moveml %a0@,%d1-%d4
400208f0:	d1c0           	addal %d0,%a0
400208f2:	48d1 001e      	moveml %d1-%d4,%a1@
400208f6:	d3c0           	addal %d0,%a1
400208f8:	9a80           	subl %d0,%d5
400208fa:	6cf0           	bges 0x400208ec
400208fc:	4cd7 003c      	moveml %sp@,%d2-%d5
40020900:	4fef 0010      	lea %sp@(16),%sp
40020904:	4e75           	rts
```

✅ **This is memcpy(dest, src, n)**, 16 bytes per iteration. cdecl argument
order (caller pushes right to left) puts `0x4ecd3000` in `%a1` (dest) and the
caller's own buffer, `%a2@(4)`, in `%a0` (src). So the write-flush and
close-flush paths copy the CALLER's buffered bytes INTO the shared address
`0x4ecd3000` before the raw write backend (which takes `FS_LOCK` as its first
act, section 7.2) reads that same address back out to build the sector
payload:

```
40016718:	4879 4ecd 3000 	pea 0x4ecd3000
4001671e:	2f12           	movel %a2@,%sp@-
40016720:	2079 46c8 2402 	moveal 0x46c82402,%a0
40016726:	4e90           	jsr %a0@
```

✅ **`refs.sh 0x4ecd3000` finds 12 hits**, clustered in two ranges:
`0x400162d0`-`0x40016310` and `0x4001648c`-`0x400165c0` (both outside the
routines this section disassembled, and by their position between open and
seek in the address map, likely the buffered READ's equivalent fill step,
not measured here), plus the four sites already shown, two in write-flush
(`0x40016708`, `0x4001671a`) and two in close-flush (`0x400167f2`,
`0x40016800`).

🟡 **The exposure.** The memcpy into `0x4ecd3000` happens BEFORE `FS_LOCK` is
acquired (the acquire is inside the raw write backend, called after the
memcpy returns). If two tasks both reach a write-flush or close-flush at
overlapping instants, whichever finishes its memcpy last overwrites the
other's staged bytes before either takes the lock, and the raw backend that
runs first will write the WRONG task's data to its own file's sectors. This
follows from the code shape; it has not been observed, because nothing in
this document's reading found two tasks that are known to call the buffered
write path concurrently today. Falsifier: a port run with a write-watch on
`0x4ecd3000` while the writer task's flush and the storage task's own
buffered I/O (if it uses this same layer, not yet confirmed) are scheduled to
interleave.

### 7.6 Per-caller state does not collide ✅

Open writes exactly two kinds of thing outside its own locals: the caller's
file object (`%a2`, the pointer passed as its first argument) and, inside
the raw backend, under `FS_LOCK`, the file layer's own open-file table at
`0x46c8657e` / `0x46c86592` / `0x46c8659e` (indexed by handle, quoted in
section 7.2's open-backend excerpt via `0x46c8657e` arithmetic; also visible
in write's and seek's descriptor lookups, which use the same base). It never
writes to a fixed global buffer address of its own: the I/O buffer address
comes from the CALLER's argument, stored into `%a2@(4)` at
`0x40016878` (7.1's open quote).

The stock sample save supplies its own 64 KB buffer, `0x460263e0`, as that
argument:

```
40084e02:	2f3c 0001 0000 	movel #65536,%sp@-
40084e08:	4879 4602 63e0 	pea 0x460263e0
40084e0e:	4879 400b 328b 	pea 0x400b328b
40084e14:	4879 4603 63e0 	pea 0x460363e0
40084e1a:	260e           	movel %fp,%d3
40084e1c:	0683 ffff ffe2 	addil #-30,%d3
40084e22:	2f03           	movel %d3,%sp@-
40084e24:	4eb9 4001 6864 	jsr 0x40016864
```

✅ **This corrects an ambiguity in how section 5.6 was read.** `0x460363e0`
is the PATH argument (built by the `sprintf`-like call at `0x40084dee` just
above), not the buffer; `0x460263e0` is the buffer, pushed with its size
(`0x10000`) as the two arguments the wrapper stores into `%a2@(4)` and
`%a2@(8)`. The file object itself is `%fp@(-30)`, a stack-local 30-plus byte
structure inside the caller's own frame, not a fixed address at all.

So STEM REC's own file object and its own I/O buffer (spec section 6), as
long as neither is `0x460263e0` and neither aliases the stock save's stack
frame, do not collide with the stock save's state. The only addresses every
caller of this layer shares are the open-file table (written only under
`FS_LOCK`, 7.2) and the staging buffer `0x4ecd3000` (written outside it,
7.5).

### 7.7 The buffered API has other stock callers today, and the storage task's real-time path bypasses it entirely ✅

This resolves, statically, the question the first pass of this section could
only defer to the port: does the section 7.5 exposure ever have two real
callers to race?

**The caller census, by the preamble's linear-objdump method** (grep the
whole image for the wrapper's address, which catches both a direct `jsr` and
a `lea`/`movea.l` register load; a call through a register loaded this way
is counted once per load found, following section 5.7's own precedent for
an approximate count of "N or more calls"):

| wrapper | total occurrences (own label + every caller reference) |
|---|---|
| open `0x40016864` | 18 |
| write `0x400166b8` | 57 |
| close `0x4001677c` | 22 |

✅ These are not small numbers: dozens of stock call sites exist beyond the
sample save section 5.6 already measured (`0x40084e24`/`0x40084e02` open,
`0x40084e52` close). Four clusters, by address range:

1. **`0x40084e02`-`0x40084ec6`, the stock sample save**, already measured in
   section 5.6 and 7.6.
2. **`0x4001ff50`-`0x4001ffd6`, a small self-contained routine** immediately
   after the storage task's own code (7.7 below), with its OWN 512-byte
   buffer `0x460261e0` (distinct from both the sample save's `0x460263e0`
   and the shared staging buffer `0x4ecd3000`), opening in `"w"` mode
   (`0x400b328b`), writing, and closing:
   ```
   4001ff60:	4878 0200      	pea 0x200
   4001ff64:	4879 4602 61e0 	pea 0x460261e0
   4001ff6a:	4879 400b 328b 	pea 0x400b328b
   ...
   4001ff7c:	4eb9 4001 6864 	jsr 0x40016864
   ...
   4001ffa0:	4eb9 4001 660c 	jsr 0x4001660c
   ...
   4001ffae:	4eb9 4001 677c 	jsr 0x4001677c
   ...
   4001ffc4:	4eb9 4001 66b8 	jsr 0x400166b8
   ...
   4001ffd6:	4e90           	jsr %a0@
   ```
   🟡 Not traced to a name or a caller. Its size (one 512-byte record) and
   position right next to the storage task's own code are consistent with
   EMU.md's "the firmware's own log on the card records each missing
   sample", but that is a guess, not a measurement. It is NOT inside the
   storage task's own loop (7.7 below establishes the loop never returns via
   `rts`, and this routine does, at `0x4001ffe2`), so it is a distinct,
   ordinarily-called subroutine, not the real-time streaming path.
3. **`0x4008fbfc`-`0x40090650`, roughly eight to nine paired open/write/close
   sites**, each shaped like items 1 and 2 above (an open, some writes, a
   close). 🟡 Not individually disassembled. Their position, right after the
   folder-removal and project-file-deletion routines section 6.3 already
   placed nearby (`0x4008ec4c`), and section 6.9's own finding that
   "`0x4008eda4` and `0x4008ee74` build `%s/bank%02d.work` and the rest and
   write them through the buffered file API" together make "one open/write/
   close cycle per project file (`project.work`, `markers.work`, sixteen
   bank files, eight arrangement files)" the working guess, not a measured
   fact.
4. **`0x400882ba`-`0x4008b47c`, ~50 WRITE-only call sites, no matching open
   or close density in the same range.** This is the cluster the review
   round asked about. 🟡 One write roughly every 200 bytes of code, with no
   open/close nearby, is consistent with a routine that opens ONCE (or reuses
   an already-open handle from a caller) and then serialises many small
   fields, one `WRITE` call per field (a text or binary record serializer,
   probably the same project/bank-file writer as item 3's cluster), working on
   one already-open handle. Not individually disassembled; this is a shape
   argument, not a name.

✅ **Conclusion for the exposure itself**: several stock callers of the
buffered API exist today, independent of STEM REC and independent of each
other (the sample save, the small log-writer, the project/bank-file saver).
The section 7.5 exposure is real AMONG THEM: if the project/bank-file saver
and the sample save (or STEM REC) ever run their buffered writes on two
different tasks at an overlapping instant, they race on `0x4ecd3000`. This
was true before this review round; the census only makes it countable.

**The storage task's real-time sample path, from the other direction.**
RTOS_FORK.md names its entry `0x4001ee30` (TCB `0x460bcc2c`, priority 5,
`sys` at `0x40061a94` creates it via `0x4001dfbc`, per STEM_REC.md section
3.7). Its loop, read whole from its entry:

```
4001ee5c:	4879 460b b3a0 	pea 0x460bb3a0
4001ee62:	4eb9 4000 0d00 	jsr 0x40000d00
4001ee68:	2440           	moveal %d0,%a2
4001ee6a:	588f           	addql #4,%sp
4001ee6c:	2012           	movel %a2@,%d0
4001ee6e:	5380           	subql #1,%d0
4001ee70:	7206           	moveq #6,%d1
4001ee72:	b280           	cmpl %d0,%d1
4001ee74:	65e6           	bcss 0x4001ee5c
4001ee76:	303b 0a08      	movew %pc@(0x4001ee80,%d0:l:2),%d0
4001ee7a:	48c0           	extl %d0
4001ee7c:	4efb 0802      	jmp %pc@(0x4001ee80,%d0:l)
```

✅ Same shape as 8.3's UI dispatcher: blocking `QUEUE_RECEIVE` (`0x40000d00`)
against the storage task's own queue `0x460bb3a0`, then an opcode-indexed
jump table (7 entries here). One case does the actual sector transfer:

```
4001eecc:	2f00           	movel %d0,%sp@-
4001eece:	2f01           	movel %d1,%sp@-
4001eed0:	2047           	moveal %d7,%a0
4001eed2:	4e90           	jsr %a0@
4001eed4:	4878 0002      	pea 0x2
4001eed8:	4879 4ecb 8000 	pea 0x4ecb8000
4001eede:	2f39 460b b41a 	movel 0x460bb41a,%sp@-
4001eee4:	2f39 460b b41e 	movel 0x460bb41e,%sp@-
4001eeea:	2079 460d 16cc 	moveal 0x460d16cc,%a0
4001eef0:	2050           	moveal %a0@,%a0
4001eef2:	4e90           	jsr %a0@
4001eef4:	4fef 001c      	lea %sp@(28),%sp
4001eef8:	6000 ff62      	braw 0x4001ee5c
```

✅ **The storage task's sector transfer goes through NEITHER the buffered API
NOR the raw FAT backends.** It calls through `0x460d16cc` (the same word
section 8.2 already found is the target of `0x40015e28`'s return, written by
the mount routine), double-indirected (`moveal 0x460d16cc,%a0 / moveal
%a0@,%a0 / jsr %a0@`): a block-device vtable call, not a path-based file
open. Its own buffer is `0x4ecb8000`, a DIFFERENT fixed address from the
buffered layer's shared staging buffer `0x4ecd3000`. None of `0x40016864`,
`0x400166b8`, `0x4001677c`, `0x461079c0` or `0x4ecd3000` appears anywhere in
the loop `0x4001ee5c`-`0x4001ef04` (the case bodies disassembled). The loop
also never executes `rts`: every case ends in `braw 0x4001ee5c` back to the
top, confirming it is the whole task body, not a subroutine that returns
into something else that might call the buffered API afterward.

✅ **This settles the open question the first pass deferred.** The section
7.5 exposure does NOT apply between STEM REC's writer task and the stock
storage task's real-time sample streaming: they use entirely different
buffers and entirely different call paths. It remains real among the OTHER
buffered-API callers this section found (the sample save, the project/bank
saver, and whatever calls the small log-writer at item 2), none of which
run at the storage task's priority or on its real-time schedule, but all of
which could in principle overlap with STEM REC's own writer task.

### 7.8 Not measured under the port 🟡

No project folder exists on this machine. Three things a port run would
settle, in the order they matter:

1. **Seek's success-path release**, 7.2's one open question.
2. **The write backend's indirect call at `0x40018dc8`**, to confirm it
   reaches the ATA WRITE SECTORS handler and takes the ATA lock while
   `FS_LOCK` is held (7.3).
3. **A scheduling trace of the writer task's flush against the project/bank
   saver's or the sample save's own I/O**, to see whether they can actually
   interleave on `0x4ecd3000` given their priorities and the kernel's
   preemption (section 4). 7.7 established that these are the real
   candidates now, not the storage task.

### 7.9 What follows for the design

Two tasks calling OPEN, WRITE, SEEK or CLOSE concurrently is safe for the
FAT structures: `FS_LOCK` serialises every routine that touches them, held
across each raw backend's own body, not narrowly around sector I/O (7.2).
The design proceeds. The flash notes should carry the 7.5 exposure (the
shared staging buffer, `0x4ecd3000`, is unprotected) as a known risk, first
flash on a spare card, so that in the unlikely event two buffered-I/O
flushes truly interleave, the failure is a corrupted stem or corrupted stock
sample data, not a wedged FAT mutex or a hung card. Section 7.7 narrows WHO
that risk is between: not STEM REC against the storage task's real-time
sample streaming (confirmed to use a different buffer and a different call
path entirely), but STEM REC against whichever of the stock buffered-API
callers (the sample save, the project/bank-file saver, the small log-writer)
happens to run on another task at the same instant.

## 8. Is a card mounted

### 8.0 The answer, first ✅

`0x460d1cb8` is a LONGWORD. Every one of its nine accesses in the image uses
a 4-byte form (`movel`, `clrl` or `cmpl`); none uses a byte or word form. It
is written 0 (not mounted, or just unmounted), 1 (mounted as an ATA card) or
2 (believed USB disk mode, section 6.2's 🟡, now corroborated below). No
hardware card-removal path was found: the only writer of 0 at runtime is a
software unmount sequence, reached from the boot sequence and from at least
one menu action, never from an interrupt or a poll. Task 13's action should
use `tst.l`.

### 8.1 The size: longword, from every access's own width ✅

`refs.sh 0x460d1cb8` (sanity-checked against the known 33-hit and 113-hit
counts for two other addresses first, per the preamble) returns 9 hits. A
linear-objdump grep for the same address independently returns 9 lines, so
none of the 9 is a register-indirect access refs.sh would miss (the preamble
names this as a risk for other addresses; here the two methods agree). Each
hit resolves to the instruction starting 2 bytes earlier:

| address | instruction |
|---|---|
| `0x40032384` | `movel 0x460d1cb8,%d0` |
| `0x4003ec30` | `cmpl 0x460d1cb8,%d0` |
| `0x40061654` | `clrl 0x460d1cb8` |
| `0x400616d4` | `movel %d0,0x460d1cb8` |
| `0x400616fc` | `movel %d0,0x460d1cb8` |
| `0x40061726` | `clrl 0x460d1cb8` |
| `0x40061740` | `clrl 0x460d1cb8` |
| `0x4006176c` | `movel %d0,0x460d1cb8` |
| `0x40061f8c` | `cmpl 0x460d1cb8,%d0` |

✅ `movel`, `clrl` and `cmpl` are all longword forms on this core. No `moveb`,
`clrb`, `cmpb`, `movew`, `clrw` or `cmpw` form appears anywhere against this
address. `tst.l CARD_MOUNTED` is the correct test.

### 8.2 The writers, and the values ✅

Two routines write it, both reached only through the pointer-table pattern
this document has already seen elsewhere (a literal `jsr` or a `lea`-then-
`jsr %aN@`): `0x40061648`, which takes one argument, and `0x40061740`, which
takes none.

`0x40061648`, whole:

```
40061648:	4fef fff4      	lea %sp@(-12),%sp
4006164c:	48d7 0c04      	moveml %d2/%a2-%a3,%sp@
40061650:	202f 0010      	movel %sp@(16),%d0
40061654:	42b9 460d 1cb8 	clrl 0x460d1cb8
4006165a:	7201           	moveq #1,%d1
4006165c:	b280           	cmpl %d0,%d1
4006165e:	667e           	bnes 0x400616de
40061660:	1039 fc0a 4039 	moveb 0xfc0a4039,%d0
40061666:	44c0           	movew %d0,%ccr
40061668:	6b00 00c8      	bmiw 0x40061732
4006166c:	4eb9 4001 4a94 	jsr 0x40014a94
...
400616d0:	4e90           	jsr %a0@
400616d2:	7001           	moveq #1,%d0
400616d4:	23c0 460d 1cb8 	movel %d0,0x460d1cb8
400616da:	4200           	clrb %d0
400616dc:	6056           	bras 0x40061734
400616de:	7202           	moveq #2,%d1
400616e0:	b280           	cmpl %d0,%d1
400616e2:	6622           	bnes 0x40061706
400616e4:	42a7           	clrl %sp@-
400616e6:	4eb9 4001 bdb4 	jsr 0x4001bdb4
400616ec:	588f           	addql #4,%sp
400616ee:	4a80           	tstl %d0
400616f0:	6d40           	blts 0x40061732
400616f2:	42a7           	clrl %sp@-
400616f4:	4eb9 4001 451c 	jsr 0x4001451c
400616fa:	7002           	moveq #2,%d0
400616fc:	23c0 460d 1cb8 	movel %d0,0x460d1cb8
40061702:	4200           	clrb %d0
40061704:	6028           	bras 0x4006172e
40061706:	4eb9 4001 61dc 	jsr 0x400161dc
4006170c:	42a7           	clrl %sp@-
4006170e:	4eb9 4001 4960 	jsr 0x40014960
40061714:	4eb9 4001 474c 	jsr 0x4001474c
4006171a:	4eb9 4001 61cc 	jsr 0x400161cc
40061720:	42b9 460d 16cc 	clrl 0x460d16cc
40061726:	42b9 460d 1cb8 	clrl 0x460d1cb8
4006172c:	4280           	clrl %d0
```

✅ **Always clears first, then dispatches on its one argument.** `0x460d1cb8`
is cleared unconditionally at entry (`0x40061654`), before the argument is
even tested, so the word reads 0 for the whole duration of every call to this
routine. Then: argument 1 falls through into an ATA IDENTIFY sequence
(`0x40014a94`, matching EMU.md's description of the mount sequence) and, on
success, writes 1 (`0x400616d4`). Argument 2 calls `0x4001bdb4` and, if it
returns non-negative, calls the STUB-table installer `0x4001451c` with 0
(section 6.2: "the zero-argument backend is a stub set") and writes 2
(`0x400616fc`). Any OTHER argument (including the boot call's literal 0,
below) falls to `0x40061706`: it calls the teardown at `0x40014960` and the
unmount-table installer `0x4001474c` (the SAME pair section 6.2 already
flagged as "0x40061714, right after the teardown at 0x40014960 ... believed
to be the unmount table"), then clears `0x460d16cc` and `0x460d1cb8`
explicitly (`0x40061726`, redundant with the entry `clrl` but present) and
returns 0.

🟡 **Argument 2 is corroborated, not directly proven, as USB disk mode.**
Section 6.2 already marked this 🟡. New evidence here: the ONLY caller of
`0x40061648` with a literal 2 is in the boot sequence's fallback (8.3), and
the SECOND writer routine (below) is reached exclusively from a handler whose
own confirm-dialog string is `"USB DISK MODE"` (read from the image at
`0x400b5844`). Falsifier unchanged from section 6.2: read `0x460d1cb8` under
the port in both states.

`0x40061740`, the second writer, no argument, called only when the word
already reads 1:

```
40061740:	42b9 460d 1cb8 	clrl 0x460d1cb8
40061746:	4eb9 4001 61dc 	jsr 0x400161dc
4006174c:	2f39 460d 16cc 	movel 0x460d16cc,%sp@-
40061752:	4eba fe74      	jsr %pc@(0x400615c8)
40061756:	588f           	addql #4,%sp
40061758:	41f9 4001 61cc 	lea 0x400161cc,%a0
4006175e:	4a80           	tstl %d0
40061760:	6706           	beqs 0x40061768
40061762:	4e90           	jsr %a0@
40061764:	70ff           	moveq #-1,%d0
40061766:	4e75           	rts
40061768:	4e90           	jsr %a0@
4006176a:	7001           	moveq #1,%d0
4006176c:	23c0 460d 1cb8 	movel %d0,0x460d1cb8
40061772:	4200           	clrb %d0
40061774:	4e75           	rts
```

✅ Same pattern: clear first (`0x40061740`), re-verify, then set back to 1 on
success (`0x4006176c`) or leave it at 0 and return -1 on failure. This is a
re-check, not a fresh mount: it is only reached from two call sites, both
guarded by "the word already reads 1" (8.3).

### 8.3 The callers, and what they say about removal ✅ with two 🟡

`0x40061648` has FOUR callers in the whole image. Re-run for this fix round,
a linear-objdump grep for its address returns exactly FOUR lines:

```
40061648:	4fef fff4      	lea %sp@(-12),%sp
40061c1e:	45fa fa28      	lea %pc@(0x40061648),%a2
40061f98:	4eba f6ae      	jsr %pc@(0x40061648)
400620b6:	4eba f590      	jsr %pc@(0x40061648)
```

The FIRST line is the routine's own label. The SECOND is the `lea` that
loads `%a2`, and it is reused for BOTH boot-time calls (mode 0 and mode 2
below share the one register load, so they produce only one grep line
between them, not two). The THIRD and FOURTH are the two `jsr %pc@(...)`
sites, one per remaining caller. So four lines map to four callers: two
share a line (the boot block, one `lea` feeding two calls through `%a2`),
and two each have their own `jsr %pc@(...)` line. Four callers, four
lines, four DISTINCT call sites for this routine (the boot block's two
calls, at different program-counter addresses, are still two separate
call sites even though they share one register load):

- **`0x40061c1c`-`0x40061c22`, the boot sequence, argument literal 0**:
  `clrl %sp@- / lea %pc@(0x40061648),%a2 / jsr %a2@`. This is the FIRST call
  in the image's boot path (after three subsystem-init calls with no
  arguments), and its argument (0) is neither 1 nor 2, so it takes the
  unmount-table branch: `0x460d1cb8` starts, and after this call remains, at
  0.
- **The same boot block, argument 2, conditionally**: after the mode-0 call
  returns, the ATA host status byte (`0xfc0a4039`) is tested; if it shows a
  fault (`bpls` not taken) AND a personal setting `0x80000088` is non-zero,
  a second call follows: `pea 0x2 / jsr %a2@` (same `%a2`, still
  `0x40061648`). This is the boot-time USB-mode fallback when no ATA card
  answers.
- **`0x40061f8e`, a lazy-mount gate, argument 1, conditionally**:
  `cmpl 0x460d1cb8,%d0` (`%d0` = 1) `/ beqs +0xa / pea 0x1 / jsr %pc@(...)`.
  This calls mode 1 ONLY when the word does not already read 1, so it never
  writes 0 or 2 itself; it is a read-then-maybe-mount, not a removal path.
- **`0x400620b6`, argument literal 0, unconditionally**: `clrl %sp@- / jsr
  %pc@(0x40061648)`. This one is inside a large opcode-dispatched case
  handler, quoted below, reached only through a task's own message queue,
  not an interrupt, not a poll.

`0x400620b6`'s enclosing case is one entry of a **77-entry jump table**
(`0x40061cfa`) at the top of a task loop that blocks on the kernel's queue
receive primitive (`0x40000d00`, the same blocking primitive section 4's
census names) against queue object `0x460d17ae`:

```
40061cd2:	4879 460d 17ae 	pea 0x460d17ae
40061cd8:	4eb9 4000 0d00 	jsr 0x40000d00
40061cde:	2440           	moveal %d0,%a2
40061ce0:	588f           	addql #4,%sp
40061ce2:	1012           	moveb %a2@,%d0
40061ce4:	5380           	subql #1,%d0
40061ce6:	7180           	mvzb %d0,%d0
40061ce8:	784d           	moveq #77,%d4
40061cea:	b880           	cmpl %d0,%d4
40061cec:	6500 102e      	bcsw 0x40062d1c
40061cf0:	303b 0a08      	movew %pc@(0x40061cfa,%d0:l:2),%d0
40061cf4:	48c0           	extl %d0
40061cf6:	4efb 0802      	jmp %pc@(0x40061cfa,%d0:l)
```

✅ The first byte of the received message selects the case (`%a2@`, the
opcode, minus 1, indexes the word table at `0x40061cfa`). Decoding the table
directly from the image (not from the garbled disassembly a data table
prints as): index 15 (opcode 16) holds the word `0x0282`, and
`0x40061cfa + 0x0282 = 0x40061f7c`, the case that CONTAINS `0x400620b6`
further down its own branch. `refs.sh 0x460d17ae` finds 87 hits across the
image: a widely shared queue, consistent with it being a general UI/task
event queue, not a private one-purpose object.

✅ **This is task-context, message-driven code, not an interrupt handler and
not a poll.** The one fact that matters for the removal question: the whole
switch runs only after `0x40000d00` returns with a message already
DEQUEUED, which is section 4's blocking receive primitive, called from a
task. There is no timer, no ATA interrupt vector, and no busy-wait anywhere
in this path: the case body only runs when something POSTS a message to
`0x460d17ae`, which is what happens on a menu action or a mode switch.
🟡 Which specific keypress or menu action posts opcode 16 was not traced
among the 87 references (that count includes many unrelated cases sharing
the same queue); falsifier: a port run posting to `0x460d17ae` with opcode
16 and observing what the display shows. The architectural point (queue
message, not interrupt, not a background poll) is ✅ regardless of which
exact menu entry it is.

`0x40061740` has two callers, both guarded the same way as `0x40061f8e`
above (read the word, compare to 1, call only if equal):

- **`0x4006bac4`**, inside a routine that first checks `0x40032384()` (the
  bare accessor quoted in 8.1's table): `jsr 0x40032384 / ... / cmpl %d0,%d1
  (%d1=1) / bnes +6 / jsr 0x40061740`. 🟡 What triggers this routine was not
  traced past this point; falsifier: a port run tracing its caller.
- **`0x4007ec12`**, inside a handler whose own confirm-dialog string reads
  `"USB DISK MODE"` (`0x400b5844`, found by reading the bytes at that
  address): the handler starts a subsystem (`0x40055d20`), clears an
  unrelated flag (`0x460e76a0`), then does the same
  `jsr 0x40032384 / cmpl / bnes / jsr 0x40061740` gate.

🟡 **No card-removal or media-detect caller was found, against all SIX call
sites now census'd** (the fourth caller above added one, not removed any).
The census is every caller of both writers, from a linear-objdump grep
(which catches register-indirect calls the preamble warns refs.sh alone
would miss; the boot call to mode 0, and the new `0x400620b6` call, are both
exactly such a case). None of the six call sites is inside an interrupt
handler or a polling loop: three are boot-sequence code, two are dialog/menu
handlers with visible UI strings, and the new one is a task's own queued
message dispatch, confirmed above to run only when something POSTS a
message, never on a timer or a hardware event. **The removal verdict
stands, now against a wider and more careful census**: the stock firmware,
as measured here, does not appear to auto-detect a card being pulled while
mounted. `0x460d1cb8` would stay 1 until the next call that clears it, and
every one of those six calls is boot-time or menu-driven, never automatic.
**Falsifier, and the one thing that matters most for the flash notes:** a
port run that mounts a card, then removes it without any UI action, and
reads `0x460d1cb8` before the next menu action. If it still reads 1, this is
confirmed, and STEM REC's mounted check (Task 13) can pass on a card that
was just pulled.

### 8.4 What follows for the design

The mounted check is real, and cheap: `tst.l CARD_MOUNTED` before arming,
exactly as the brief's interface line already assumes. Its blind spot is
mid-session removal, not first-mount: nothing found here clears the word on
a physical pull, only on the next explicit unmount call. This does not
change Task 13's action (there is no cheaper or more complete static check
available), but it belongs in the flash notes next to the FS_LOCK risk from
section 7: a card pulled mid-take will not be caught by this check, and the
failure mode is whatever the write backend's FAT-mutex path does when the
ATA layer stops answering (not measured here; section 7.3's falsifier
list applies).

### 8.5 Not measured under the port 🟡

No project folder exists on this machine. Three things a port run would
settle, in the order they matter:

1. **`0x460d1cb8` read after a real removal**, 8.3's falsifier, the one that
   decides whether the crash-safety picture needs a stronger check than
   `tst.l CARD_MOUNTED`.
2. **`0x460d1cb8` in both the 1 and 2 states**, to settle whether 2 really is
   USB disk mode (8.2's 🟡), by comparing against the port's own USB-mode
   trigger if one exists.
3. **What `0x40061648`'s trigger for argument 2 actually reads** at
   `0x80000088`, to confirm it is the personal setting believed here, not
   something else that happens to be non-zero at the same boot point.

### 8.6 Interface

```asm
| Is a card mounted? LONGWORD. 0 = not mounted (boot default, and the state
| after every unmount). 1 = mounted as an ATA card. 2 = believed USB disk
| mode (🟡, section 8.2). Written only by 0x40061648(mode) and by
| 0x40061740's re-check; both are reached only through boot, a lazy-mount
| gate, or a menu action (section 8.3). NO CARD-REMOVAL WRITER was found:
| this word can stay 1 after a physical pull. Test with tst.l, not tst.b.
|   tst.l	CARD_MOUNTED
|   beq	not_mounted
.equ	CARD_MOUNTED,	0x460d1cb8
.equ	CARD_MOUNTED_NONE,	0	| not mounted, or just unmounted
.equ	CARD_MOUNTED_CARD,	1	| mounted as an ATA card
.equ	CARD_MOUNTED_USB,	2	| 🟡 believed USB disk mode, not directly proven

| The FAT layer's one lock, already equated in section 6 as FS_LOCK. Open,
| the buffered write's flush, seek and the folder routine (section 6) each
| reach a raw backend that takes it as its first act and holds it across
| that backend's own body (section 7.2). A READ-mode open reaches TWO such
| backends with a gap between the two holds (section 7.1); STEM REC opens
| only in write mode, where the wrapper reaches exactly one. Two tasks
| calling the buffered file API concurrently are safe for the FAT
| structures because of this lock.
| ⚠️ NOT covered by this lock: the shared sector staging buffer FS_STAGE_BUF
| (section 7.5), touched by a plain memcpy before the lock is taken. Real
| stock callers of the buffered API exist today beyond the sample save
| (section 7.7); the stock storage task's real-time sample path is NOT one
| of them, confirmed by reading its loop (section 7.7).
.equ	FS_STAGE_BUF,	0x4ecd3000	| shared, UNPROTECTED sector staging buffer
```
