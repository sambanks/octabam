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

`refs.sh` sees absolute operands only. No `lea` or `movea.l` of `0x800065b8`
appears in the image, so there is no access through an address register to
miss, and no displacement access either: the neighbouring base `0x80006500`
is a separate 16-byte per-track array, and every reference to it is a `lea`
into that array whose loop stops at `0x80006510`, well below `0x800065b8`.

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

Both branches of `0x400a10c8` reach `0x400a12ac`, so the routine always
leaves the word at 0. It also transmits MIDI Stop, at `0x400a1426`. That
site is inside `0x400a10c8`: the routine's only `rts` is at `0x400a14a0`,
after the matching `moveml %sp@,%d2-%d5/%a2-%fp` at `0x400a1498`, and there
is no other return between `0x400a10c8` and it.

`0x400a4066` is an automatic stop, inside the same timer interrupt handler
at `0x400a1e0c` that holds three of the write-1 sites. Its test at
`0x400a3f96` compares the word against 1 and leaves if it is anything else.
It transmits MIDI Stop 64 bytes earlier and then clears:

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

| The three states. 0 is stopped and rewound, 2 is stopped by the STOP key
| with the position kept, so ONLY 1 means running.
.equ	TRANSPORT_REWOUND,	0
.equ	TRANSPORT_RUNNING,	1
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
