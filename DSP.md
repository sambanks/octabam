# DSP56300 side — module load map (step 1)

The effects and timestretch run on the DSP, not on the ColdFire. `COVERAGE.md`
records that the DSP program was located and extracted but never disassembled,
and identifies the blocker: without knowing which bytes load to which DSP address
in which memory space, a disassembly is at the wrong PC and is worthless.

**That blocker is now cleared.** This document is the map.

Addresses are ColdFire virtual addresses (`file_offset = vaddr − 0x40000400`)
unless prefixed `P:` / `X:` / `Y:`, which are DSP word addresses.

---

## 1. Boot sequence

`FUN_40001e50`, called from the boot path at `0x4000050c`:

```asm
move.b #0,(0xfc0a400c)                       ; GPIO select
move.w #0x81,(0x20000000)                    ; DSP control: start
FUN_40001d4c(0x400e21e0, 0x96,  0x31000)     ; bootstrap A -> P:0x31000  (50 words)
                                             ; ~10,000-iteration delay loop
FUN_40001b18(0x400e2324)                     ; payload A  (79,563 B)
move.b #1,(0xfc0a400c)                       ; GPIO select -- FLIPPED
move.w #0x81,(0x20000000)                    ; DSP control: start
FUN_40001d4c(0x400e2276, 0xae,  0x32000)     ; bootstrap B -> P:0x32000  (58 words)
                                             ; delay loop
FUN_40001b18(0x400f59ef)                     ; payload B  (77,061 B)
move.l #0xfff0000,(0xfc00801c)               ; FlexBus / chip-select config
```

**Two DSPs (or two banks), not one.** The sequence runs twice, identically, with
the GPIO at `0xfc0a400c` toggled between passes, and each pass has its own
bootstrap and payload. `ARCHITECTURE.md` assumes a single DSP56xxx. The two
payloads have near-identical X/Y layouts (matching module sizes 6305, 198, 4096,
3730, 384, 384, 258, …) at slightly different base addresses, which is what two
instances splitting the work would look like. *Inference from the load map, not
confirmed against hardware.*

### The blobs are relocated before the bank RAM eats them

Boot code at `0x40000450` `memcpy`s all four blobs from the image tail to
`0x40a955e0` **before** they are uploaded. `0x40a955e0` is exactly
`0x400e21e0 + 16 * 0x9b340` — the end of the 16 resident bank blobs. So the DSP
program shares an address range with bank 0 and the firmware moves it out of the
way first. This confirms the RAM-reuse inference in `PARAM_PAGES.md`: after boot
the DSP program no longer exists at `0x400e21e0`, only in the DSP and at the
relocated copy.

## 2. Payload format

`FUN_40001b18` takes **only a pointer** — the payloads are self-describing.
Decompiled, it walks **24-bit little-endian** words (`b[0] | b[1]<<8 | b[2]<<16`):

```
optional header word 3   (skip 6 bytes)
optional header word 4   (skip 6 bytes)
repeat:
    word  memory space   0 = P, 1 = X, 2 = Y;  > 3 terminates
    word  load address   (DSP word address)
    word  count          (in 24-bit words)
    count * 3 bytes of data
```

The field order (address before count) was ambiguous in the decompilation, so
`tools/dsp_modmap.py` tries both and keeps the one that parses. The result is not
a judgement call:

| payload | records | bytes consumed |
|---|---|---|
| A `0x400e2324` | 98 | 79,557 / 79,563 = **100.0%** |
| B `0x400f59ef` | 91 | 77,055 / 77,061 = **100.0%** |

A wrong record layout does not land exactly on the end of the blob twice.

    python3 tools/dsp_modmap.py        # prints the full map

## 3. What the map shows

**Payload A** — 98 modules, 26,221 words. X data `0x0020f`–`0x08d64`, Y data
`0x00200`–`0x00715`, then P (code) from `0x00000`:

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
P:0x30000    171 words   <- separate region, payload A only
P:0x38000     19 words   <- separate region, payload A only
```

**Payload B** — 91 modules, similar shape, P code from `0x00000` to ~`0x00c77`,
no `0x30000`/`0x38000` regions.

The largest P modules (`P:0x01252`, `P:0x01679`, ~1,065 words each) are the
obvious first disassembly targets — big enough to be real signal-processing code.

### A hypothesis that did not survive

Each payload contains a run of **15 consecutive one-word P records** (A:
`P:0x006e5`–`0x006f3`, B: `P:0x004a5`–`0x004b3`). Fifteen is also the number of
effect descriptors, so this looked like a static effect dispatch table. **It is
not** — every one of the 30 words is `0x000000`. They are zero-initialised
scratch words. If a dispatch table exists it is built at runtime.

## 4. Disassembly (step 2 — done)

Neither Ghidra nor radare2 ships a DSP56300 target. `setup.sh` now clones and
builds the disassembler from the Access Virus emulator project
(<https://github.com/dsp56300/dsp56300>) into
`vendor/dsp56300/build/source/disassemble/dsp56kDisassemble`.

```sh
./setup.sh                                        # clones + builds it
python3 tools/dsp_modmap.py                       # the full module map
python3 tools/dsp_modmap.py --extract A 1252 out/dsp/A_P1252.bin
vendor/dsp56300/build/source/disassemble/dsp56kDisassemble \
    -in out/dsp/A_P1252.bin -pc 1252 -le
```

**The `-le` is required.** Module data is 24-bit **little-endian**, matching how
`FUN_40001b18` maps bytes onto the three 8-bit ports (`0x20000014` gets bits
23–16 from `b[i+5]`, `0x18` gets 15–8 from `b[i+4]`, `0x1c` gets 7–0 from
`b[i+3]`). Big-endian produces plausible-looking garbage — exactly the trap the
module map exists to avoid. (`NOTES.md` describes the boot blobs as big-endian;
that reading does not hold for the payload modules.)

### Validation

`P:0x01252` disassembles into obviously real code from the first instruction —
an `r7` stack frame, a hardware `do` loop whose bounds land exactly on its body,
and `move x:>$213,r2` reading X memory at `0x213`, inside a mapped X module.

Decode quality across four P modules, 2,871 instructions:

| module | lines | undecodable |
|---|---|---|
| `P:0x01252` | 901 | **0** |
| `P:0x01679` | 848 | **0** |
| `P:0x01000` | 485 | **0** |
| `P:0x007d1` | 637 | **0** |

Zero `dc` fallbacks anywhere. Wrong addresses or wrong endianness would litter
the output with them, so this validates the module map, the byte order and the
disassembler together.

## 5. The effect dispatch (step 3 — done)

`tools/dsp_disasm_all.py` disassembles every P module at its correct address
(payload A: 68 modules / 6,817 instructions; payload B: 46 / 6,251; **zero**
undecodable). The dispatch is in `P:0x0041e`, and it is the only one — six
`jsr (r2)` sites in each payload, no others anywhere:

```asm
0004ac: move    x:(r6+$1b),b      ; the effect id field
0004ad: asr     #$8,b,b           ; extract the byte
0004b0: move    b,r1              ; r1 = effect id
0004b4: move    x:(r1+$235),r2    ; r2 = PROCESS_TABLE[id]
0004be: jsr     (r2)              ; call every frame
...
0004c9: cmp     x0,b              ; did the id change since last frame?
0004ca: beq     ...               ; no -> skip
0004cb: move    x:(r1+$215),r2    ; r2 = INIT_TABLE[id]
0004cd: jsr     (r2)              ; call only on change
```

**Two 32-entry function-pointer tables in X memory, indexed by the raw effect
id** — `X:0x215` = init (called when the id changes), `X:0x235` = process (called
every frame). They are `0x20` apart and the load map carries them as one record,
`X:0x00215, 64 words`, at image `0x400e2345` (A) / `0x400f5a10` (B). So both
tables are **plain data in the payload**, editable with the existing toolchain.

### The tables (payload A; B is identical in structure)

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
| **all 19 others** | `P:0x007c8` | `P:0x007c9` | **null stub** |

**13 effects are implemented on the DSP.** Every other id — including `0x08`
DELAY and `0x19` MULTIBCOMP — points at the null stub.

### Why DELAY was silent on FX1 — solved

The null stub is not silence, it is a **passthrough**:

```asm
0007c8: rts                       ; init: nothing
0007c9: move r0,r1                ; process: copy input to output
0007ca: do   n7,>$7d0
0007cc: move x:(r0)+,a
0007cd: move x:(r0)+,b            ; two interleaved channels
0007ce: move a,x:(r1)+
0007cf: move b,x:(r1)+
0007d0: rts
```

Which is exactly the observed behaviour: the parameter page worked, the audio was
untouched. `0x08` has no implementation in *either* payload.

Yet DELAY demonstrably works on FX2 in stock firmware. Since this is the only
dispatch in either payload, **the delay must be implemented outside the
per-effect insert chain** — a dedicated stage in the audio graph that the FX2
slot enables, rather than a table-dispatched insert. That also explains why
adding `0x08` to the FX1 list changed nothing: the dispatch handed it the
passthrough, and the dedicated stage only watches the FX2 slot. *(Best-supported
inference. Direct evidence: `0x08` → passthrough in both tables, and delay works
on FX2.)*

`MULTIBCOMP` (`0x19`) also points at the stub, confirming the "unfinished
placeholder" reading of its copied-from-DJ-EQ parameter labels — and retiring the
probe idea, which would have found nothing but passthrough on all 19 free ids.

### The stub is also the ABI specification

Those seven instructions are a complete worked example of an effect's process
routine: **`r0` = input buffer, `r1` = output buffer, `n7` = sample count, two
interleaved channels, `rts` when done.** Any new effect has to satisfy that
contract, and here it is in full.

## 6. How parameters reach the algorithm (step 4 — done)

The dispatcher sets `r6` before calling, and effects read their parameters from
it. From `P:0x0041e`:

```asm
0004a7: move    x:>$208,r6        ; r6 = base of the per-instance block
0004a9: move    #$6,n6            ; FX1 stride (the FX2 block uses #$c)
0004ac: move    x:(r6+$1b),b      ; FX1 effect id   (FX2 reads +$1c)
0004b1: move    (r6)+n6           ; r6 += 6  -> FX1 params  (FX2: += 12)
0004be: jsr     (r2)              ; routine sees r6 pointing at ITS parameters
```

So relative to `x:>$208`: FX1's parameters start at `+6`, FX2's at `+12`, and the
two effect ids sit at `+0x1b` / `+0x1c` — the same adjacent-pair arrangement the
ColdFire uses at `0x80000ec4` / `0x80000ecc`.

### Parameter layout, confirmed against the descriptors

Inside a routine, **page-1 parameter *i* is at `x:(r6+i)`, positionally**, empty
slots included. Four independent confirmations, each an effect whose descriptor
has a `---` slot and whose code skips exactly that offset:

| effect | descriptor page 1 | offsets read | skipped |
|---|---|---|---|
| COMB | `PTCH TUNE LP FB --- MIX` | `00 01 02 03 05` | **`04`** |
| DJ EQ | `LS F --- HS F LOWG MIDG HI G` | `00 02 03 04 05` | **`01`** |
| SPRING | `TIME --- --- HP LP MIX` | `00 03 04 05` | **`01 02`** |
| FLANGER | page 2 entirely `---` | nothing at `0c+` | **all of page 2** |

Page-2 parameters start at `x:(r6+0x0c)`. There they appear to be **packed**,
skipping empty slots — CHORUS (`TAPS --- --- FBLP --- ---`) reads `+0x0c` and
`+0x0d`, which fits packed but not positional. Less certain than the page-1
result; verify before relying on it.

### Value convention

Parameters arrive as 24-bit words with the 0–127 value in the **high byte**
(`value << 16`), i.e. DSP fractional format:

```asm
and     #>$7f0000,a       ; mask to the 0..127 range        (LO-FI)
sub     #>$400000,b       ; recentre: 64<<16 -> bipolar     (FILTER, FLANGER)
asr     #$e,a,a           ; scale down for use as a coefficient
mpyi    #>$e00000,x1,a    ; fractional multiply
```

`0x7f0000` is 127, `0x400000` is 64 — the centre of a `0..127` control.

### The complete effect ABI

Everything a new algorithm needs to satisfy:

| register | meaning |
|---|---|
| `r0` | input buffer (two interleaved channels) |
| `r1` | output buffer |
| `n7` | sample count for the `do` loop |
| `r6` | this instance's parameter block |
| `x:(r6+0)` … `x:(r6+5)` | page-1 parameters, `value << 16` |
| `x:(r6+0x0c)` … | page-2 parameters |
| — | return with `rts` |

The null stub (§5) is a working minimal implementation of exactly this contract.

## 7. Where a new effect can go, and what fits

### Internal P memory is contiguous and full

| payload | internal P modules | words used | top | gaps |
|---|---|---|---|---|
| A | 66 | 8,159 | `P:0x01fdf` | **none** |
| B | 46 | 7,583 | `P:0x01d9f` | **none** |

Not one hole in either image. Payload A ends at `0x01fdf`, which is 99.6% of
`0x2000` — that reads as **8 K words of internal P RAM, essentially full**, and
would leave **33 free words in A** and 609 in B.

> **This is an inference, not a datasheet fact.** The evidence is the packing
> (perfectly contiguous, stopping 33 words short of an 8 K boundary) plus
> `P:0x30000`/`P:0x38000` being a separate external region for the host-port
> bootstrap. If the part actually has 16 K words, there are 8,225 words free at
> `P:0x01fdf` and a new effect can simply be appended.
>
> **Cheap decisive test**: append a module that loads a *copy* of an existing
> effect at `P:0x02000+`, and point a spare id's dispatch entries at the copy.
> If that id produces the effect, P RAM extends past 8 K. If it is silent or
> crashes, it does not. One flash settles it.

### If 8 K is right: replace, don't append

Effect code is 6,158 of the 8,159 words — **75% of the whole program**. So the
room is in the effects themselves, and the move is to overwrite one you never
use and repoint its two dispatch entries:

| effect | code | | effect | code |
|---|---|---|---|---|
| DARK REV | 1,067 words | | CHORUS | 329 |
| SPRING REV | 1,063 | | FLANGER | 289 |
| FILTER | 727 | | EQUALIZER | 282 |
| PLATE REV | 594 | | COMB | 277 |
| LO-FI | 537 | | SPATIALIZER | 261 |
| DJ EQ | 345 | | PHASER | 207 |
| | | | COMPRESSOR | 180 |

Replacing DJ EQ or SPATIALIZER is the obvious opening move: few people would miss
them, and 261–345 words is a generous budget for a simple algorithm.

### What fits, by cost

Code size alone is not cost; the per-sample work is. Counting `do` loops in each
process routine:

| effect | process words | `do` loops | tightest loop body |
|---|---|---|---|
| SPRING REV | 1,117 | **26** | 3 |
| DARK REV | 918 | **22** | 4 |
| PLATE REV | 617 | **21** | 3 |
| FILTER | 725 | 12 | 4 |
| LO-FI | 520 | 11 | 5 |
| COMB | 259 | 9 | 3 |
| PHASER | 203 | 12 | 3 |
| COMPRESSOR | 196 | 8 | 3 |

The three reverbs top both measures — and they are exactly the three that glitch
when two run at once. That correlation makes the ranking usable as a budget: an
effect in the COMPRESSOR/PHASER class (~200 words, ~8–12 loops, 3-instruction
inner loops) is comfortably affordable; anything reverb-shaped is not.

**A first effect should be cheap per sample** — a bitcrusher, waveshaper or
ring-modulator is a few instructions inside one `do` loop and lands well inside
the budget. Anything needing a long delay line is the wrong first target, both
for cycles and because delay-line memory is the one resource we have not mapped.

## 8. Next steps — writing an effect

The path is now mapped end to end:

1. Write init + process routines in DSP56300 assembly against the ABI above.
2. Place them in free P memory. The payload is a **record list**, so a new module
   can simply be appended before the terminator — no gap-hunting needed. (Check
   what P addresses are real internal RAM first: modules run to ~`P:0x01fdf`,
   with `P:0x30000`/`P:0x38000` being the host-port bootstrap in a separate
   external region.)
3. Point `X:0x215[id]` and `X:0x235[id]` at the new code — two words of data.
4. Add the ColdFire-side descriptor and chooser entry (`PARAM_PAGES.md`).

Do it for **both** payloads, or the effect exists on only one of the two DSPs.

Still unknown, and needed before step 1 is real: how the 12 descriptor parameters
reach the algorithm, and how much DSP cycle budget is actually free — the FX1
reverb test showed two reverbs already glitch, so the headroom is not generous.

Note the ColdFire uploads the payloads verbatim from the image, so a modified DSP
program only needs the payload rewritten in place — the record format is
understood in both directions, and the loader does no checksumming of its own.
The outer ELEK/aPLib container is rebuilt by the existing toolchain.
