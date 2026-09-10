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
