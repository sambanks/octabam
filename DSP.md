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

### The effect ABI — partly settled, and one claim CORRECTED

| register | meaning | confidence |
|---|---|---|
| `r6` | this instance's parameter block | **confirmed** — dispatcher sets it, effects read `x:(r6+0..5)` |
| `x:(r6+0)` … `x:(r6+5)` | page-1 parameters, `value << 16` | **confirmed** four ways (§6) |
| `r7` | per-instance state block | **confirmed** — dispatcher sets `r7 = x:0x20a + 0x100` |
| `n7` | frame count | confirmed for the stub; effects also read `x:0x20c` |
| `r0` | audio buffer | **NOT as first documented — see below** |

> **Correction.** An earlier version of this section stated `r0` = input buffer
> and `r1` = output buffer as "the complete effect ABI". That is the **passthrough
> stub's** convention, and the stub is the degenerate case. Real effects do not
> follow it. DARK REV's entry saves the incoming `r0` into its state
> (`move r0,x:(r7+$17)`) and then works from **fixed addresses**:
>
> ```asm
> 00171e: move r6,x:(r7+$18)
> 00172e: move #$a0,r2
> 00172f: move #>$110,r4
> ```
>
> So where a real effect reads and writes audio is **still unresolved**. Writing
> the test impulse at `X:0` and at `X:0xa0` both fail to produce a reverb tail,
> though tracing confirms the effect does read the impulse (a helper at `P:0x9ad`
> returns it) and does write into the `0xa0`–`0x110` region.

## 6b. Harness status (`tools/dsp_host`)

**Working**: memory loading, the emulator, single-stepped calls via the DSP's own
`jsr`, output capture. The passthrough stub returns exactly the two impulse
samples it should, and that is a genuine end-to-end validation of the plumbing.

**Frame context — solved.** The effects depend on control words no module
initialises. Rather than reconstruct them by hand, the harness runs the DSP's own
setup routine at `P:0x372..0x39e`, which derives them from two loaded pointers:

```
x:0x415 = 0x35d -> x:0x419      x:0x416 = 0x2dd -> x:0x208
x:0x20a = 0x6000 (state base)   x:0x213 = 0x255
x:0x20c = frame count, from (x:(x:0x419+0x1e) >> 8) & 0xf   -- capped at 15
x:0x20d = 0x10 - count          x:0x20e = count * 2
```

Verified: the harness now reports exactly the values the hardware would compute,
and derives `r6 = x:0x208 + 6` and `r7 = x:0x20a + 0x100` the way the dispatcher
does. Note `x:0x20c` being zero makes the dispatcher **skip the effect entirely**,
which is why an unseeded context produced silence.

**Not working**: real effects run without faulting but produce no tail, because
the audio buffer convention above is unresolved. Until that is closed the harness
cannot validate a reverb, which was the whole point of building it.

### Why address-guessing kept failing: the audio is DMA'd in

The interrupt vector table at `P:0x00000` decodes cleanly. The ESAI vectors
(`0x30`–`0x3e`) are all `jmp` to themselves — the unused-vector idiom — so audio
does **not** arrive over the serial audio interface. The live vectors are
`0x10`–`0x1c`, and they are host-port handlers that program the DMA controller:

```asm
000588: move a1,x:>$200          ; IRQA: DMA0 setup
00058a: movep x:<<M_HORX,a1      ;   word 1 from the host ...
00058d: movep a1,x:<<M_DDR0      ;   ... is the DMA DESTINATION ADDRESS
00058e: movep x:<<M_HORX,a1      ;   word 2 ...
000591: movep a1,x:<<M_DCO0      ;   ... is the transfer count
000592: movep #>$8e82c0,x:<<M_DCR0 ; enable DMA0
0005c1/0005c4: move x0,x:>$41f   ; DMA-complete: ping-pong buffer selector
```

So **the ColdFire DMAs audio into the DSP's X memory and tells it the destination
address at runtime**. There is no fixed audio buffer constant to discover, which
is exactly why eight rounds of guessing addresses (`X:0`, `0xa0`, `0xb0`,
`0x110`, both ping-pong states) all produced silence. The buffer addresses, the
control blocks and the per-track state all arrive over the host port.

Reconstructing that faithfully means emulating the ColdFire→DSP protocol — a
substantial job requiring the ColdFire-side frame builder (`FUN_4000c8a4`) to be
replayed. It is not a couple more constants.

### The way around it: we do not need to run the STOCK effects

The harness exists to develop a **new** algorithm, and a new algorithm's
interface is ours to choose while developing it:

1. **Develop in isolation.** Write the reverb as a self-contained routine, feed
   it audio and capture output through the harness on our own convention. This
   works *today* — the emulator, memory loading, call/return and capture are all
   validated.
2. **Integrate by imitation.** At integration time, prepend the buffer-acquisition
   prologue from an existing reverb. We have DARK REV's disassembly; whatever it
   does to locate its buffers (`move r0,x:(r7+$17)`, the pointer table at
   `X:0x130`, `#$a0`/`#>$110`), we replicate verbatim. We do not have to
   *understand* the convention to *copy* it.
3. **Validate on hardware**, where the real ColdFire supplies the real DMA setup.

That keeps the desktop loop for the part that actually needs iterating — the
algorithm and its tuning — and confines the unknown to a prologue we can lift
wholesale.

## 7. Where a new effect can go, and what fits

### Internal P memory is contiguous and full

| payload | internal P modules | words used | top | gaps |
|---|---|---|---|---|
| A | 66 | 8,159 | `P:0x01fdf` | **none** |
| B | 46 | 7,583 | `P:0x01d9f` | **none** |

Not one hole in either image. Payload A ends at `0x01fdf`, which is 99.6% of
`0x2000`, and that looked like an 8 K internal P RAM essentially full.

### HARDWARE RESULT: there is memory above 8K — that inference was WRONG

`tools/build_dsptest.py` relocated CHORUS from `P:0x00eb7` to `P:0x02000` (three
words per payload: the module's load-address field and its two dispatch entries).
Flashed to the MKII: **CHORUS works normally.**

So `P:0x2000` is real, usable, executable memory. The program ending at `0x01fdf`
is where this build happens to stop, not a hardware boundary. **A new effect can
simply be appended** rather than having to displace an existing one — the much
easier workflow.

Proven usable so far: `P:0x02000`–`P:0x02149` (CHORUS's 329 words). The upper
bound is unknown; relocating several clean effects to `0x4000`, `0x8000`, `0xc000`
in one build would bracket it in a single flash, if it ever matters.

Unsettled nuance: on a DSP56300, addresses beyond internal RAM fall through to
external memory, which is slower. CHORUS running cleanly says `0x2000` works, not
that it runs at full internal speed. For a cheap effect this is unlikely to
matter; for something cycle-critical it would need checking.

### The fallback, if space above ever runs out: replace

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

## 7b. We can write DSP56300 code — validated

`dsp56kEmu` ships an assembler as well as an emulator. `tools/dsp_host/dsp_asm.cpp`
wraps it with two-pass label resolution and emits a module blob in the payload's
24-bit little-endian packing.

**Validation**: reassembling the stock passthrough stub from source reproduces
all 9 words **byte for byte**, including the two-word `do n7,>$7d0` (`06df00
0007cf`). So the write side of the toolchain is correct against known-good
firmware bytes, not merely plausible.

```sh
dsp_asm -in dsp/passthrough.asm -org 7c8 -list -out blob.bin
```

## 7c. Delay memory — earlier figures CORRECTED

Two mistakes in §7, both from scanning immediates too loosely:

1. The buffer ladders attributed to the reverbs mixed **coefficient tables** in
   with delay lines. `X:0x438` (6,305 words, 99% non-zero, a decaying curve),
   `X:0x4840` (4,096) and `X:0x6c00` (3,730) are loaded data, not buffers. DARK
   REV's real delay memory is roughly 7,600 words (**~172 ms**), not the 416 ms
   quoted.
2. Some "buffer bases" were not addresses at all — SPRING's `0x7f00` is
   `and #>$7f00,b`, a bitmask. Filtering to immediates loaded into address
   registers leaves very few, because **the reverbs compute their buffer
   addresses at runtime** rather than loading constants. Static scanning cannot
   locate their delay lines.

The uninitialised X regions, which is what actually matters:

| region | words | ms @44.1k | use |
|---|---|---|---|
| `0x01d9f–0x0483f` | 10,913 | 247 | main delay region (PLATE, DARK) |
| `0x05840–0x06bff` | 5,056 | 115 | per-instance state blocks (`x:0x20a` = 0x6000) |
| `0x07a92–0x0857f` | 2,798 | 63 | |
| **`0x08d98–0x0ffff`** | **29,288** | **664** | **unreferenced anywhere** |

If that last region is real memory, a new reverb can have several times the stock
delay allocation — which is what a Blackhole-class space needs. Whether it exists
is unresolved: relocating a stock reverb's buffers to test it is not viable,
since those addresses are computed rather than stored.

**Better test, which also proves the pipeline**: write a small probe effect that
stores a pattern high in X, reads it back, and passes audio only if it matches.
Point a free effect id at it, flash, listen. That answers the memory question and
exercises the entire write → assemble → insert → dispatch → ColdFire descriptor →
flash path with ~20 instructions of risk instead of a thousand-word reverb.

## 7d. HARDWARE: custom DSP code runs

`dsp/probe.asm` — 17 words, written by us — assembled, inserted over CHORUS's
module, dispatched via a new effect id `0x06` with its own descriptor, and
**audibly distorting on a real MKII**. The whole path works end to end:

    assemble -> insert module -> dispatch tables -> 5 ColdFire tables -> flash -> sound

It also proves **X:0x4000 is real read/write memory**, since the probe stamps a
mask there in init and reads it back in process to use as the audio mask.

### What the four attempts cost, and the actual lesson

Attempts 1-3 hung the DSP (audio stops, sequencer freezes on trig 1 -- the
sequencer is clocked by the DSP frame interrupt, so a DSP stall looks exactly
like that). Attempt 4 worked after removing three things at once, so which one
mattered is not established. The candidates, in order of suspicion:

1. **Executing at `P:0x2000`.** Every failed attempt relocated the donor module
   there. `PRAMTEST` proved code *executes* at `P:0x2000`, but that test kept
   CHORUS's own code and dispatch. A plausible mechanism: if `P:0x2000` and
   `X:0x2000` alias to the same external memory, the control probe's
   `move x0,x:>$2000` overwrote its own first instruction. **Untested, and
   important** -- it would rule out putting new code above the internal P range
   while using low X as delay memory.
2. **The blob is position-dependent even without branches**, because `do` encodes
   an absolute loop-end address. One blob was being assembled at payload A's org
   and written into payload B at a different address.
3. **A hardcoded entry point** (`ORG + 9`) that silently became wrong when the
   probe shrank from 9 init words to 5.

The process lesson is the real one: changing several variables per hardware
iteration turned a two-flash question into four. The control run -- probing
addresses known to exist -- was what converted "the memory must be absent" into
"our code is wrong", and should have come first.

## 7e. HARDWARE: the delay-memory budget, confirmed

Probing one address per flash, with identical branch-free code so the address is
the only variable:

| address | result |
|---|---|
| `X:0x4000` | distortion — real |
| `X:0xc000` | distortion — real |
| `X:0xf000` | distortion — real |

So X memory covers at least `0x0000`–`0xf000`, and the region the firmware never
references — **`0x08d98`–`0x0ffff`, 29,288 words, 664 ms at 44.1 kHz** — is real,
writable, and entirely free.

### CORRECTION: that budget does not belong to effects

The figures below were measured correctly but interpreted wrongly, and the reverb
work proved it. Probing showed X:0x4000/0xc000/0xf000 respond to reads and
writes, and I concluded 664 ms of delay memory was available. It is not
*allocated* to effects, and using it does not work: a self-chosen buffer neither
persists reliably nor is safe to write in bulk.

How the stock reverbs actually do it, from DARK REV's disassembly:

* it never loads an address above 0x200 into an address register, apart from two
  loaded lookup tables;
* it reads its modulo registers from a table -- `move #>$8cf3,r3` then
  `move x:(r3+$8),m4`;
* that table at X:0x8cfb is a list of DELAY LENGTHS:
  `28 36 58 82 126 190 250 408 646 922 1376 2047 608 896 1292 2047`
* and it makes heavy use of Y memory (103 instructions) at low addresses.

So effects are given small buffers in low Y memory and take their delay lengths
from a table. The longest line DARK uses is 2,047 words -- about 46 ms, not the
664 ms I quoted. A reverb here is built from a few thousand words in total, which
is why the stock ones sound small.

This invalidates the design premise of reverb v1-v4: four 4096-word lines in
self-chosen X memory is roughly 8x more delay memory than the hardware actually
hands an effect, in a memory space that is not ours.

### The measured figures, which stand as measurements

| resource | available | stock comparison |
|---|---|---|
| free delay memory | **29,288 words / 664 ms** | DARK REV uses ~7,600 / 172 ms |
| plus the shared gap `0x1d9f–0x483f` | 10,913 / 247 ms | currently PLATE + DARK |
| code space (replace DARK) | 1,067 words | — |
| code space (all three reverbs) | 2,724 words | — |
| cycle budget | **unmeasured** | two stock reverbs already glitch |

Using the free `0x8d98+` region rather than the stock buffers means a new reverb
**does not disturb the existing ones**, so it can be developed and flashed
alongside working firmware instead of replacing something first.

The cycle budget is now the only unquantified constraint, and the only
calibration is empirical: two stock reverbs at once glitch. That will shape how
much modulation and diffusion is affordable, and it is the thing most likely to
force compromises during tuning.

### Development loop, now that it exists

The probe runs identically in `tools/dsp_host` and on hardware using the same
convention (`r0` = interleaved block processed in place, `n7` = frames). Since a
new algorithm's interface is ours to choose, the harness can host the reverb
during development — feed audio, capture output, iterate on the desktop — and
hardware is only needed when the result is worth listening to.

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

## 8. HARDWARE: Y memory ends at 0xC000

The reverb's tank was 1024-word lines because that was all §7's uncertain X-memory
figures could justify. `dsp/ymemprobe.asm` settles it for Y, which is where the
delay buffers actually live.

The probe is a **wet-only** echo whose buffer base is chosen by `p0`:

    base = (p0 + 1) << 10          p0=0 -> Y:0x400  ...  p0=127 -> Y:0x20000

1024 words at that base, tap 1000, feedback 0.5. Wet-only is the point: it turns
a judgement call about echo quality into a yes/no, because silence is then a real
answer rather than an ambiguous one. Sweep `p0` and note where it stops.

**Result: clean echo up to p0=46, silence from p0=47.** So Y is real through
`0xBFFF` and absent at `0xC000` — **48K words**. Loaded modules end at `0x794`,
so `0x795–0xBFFF` is free: **46K words, roughly 1.04 s of delay at 44.1 kHz.**

That is about 8x what the reverb had been using, and it is what makes a
Blackhole-class space possible. `tools/gen_reverb.py` now sizes against it:

| | words | Y range | |
|---|---|---|---|
| 4 tank lines | 4096 each | `0x1000–0x4fff` | taps 3121/2477/1949/1453 (71/56/44/33 ms) |
| 4 allpasses | 2048 each | `0x5000–0x6fff` | taps 1051/773/557/379 (24/17.5/12.6/8.6 ms) |
| free | 20,480 | `0x7000–0xBFFF` | 465 ms, earmarked for pre-delay |

Note the diffusers are long *on purpose*. Four lines at ~50 ms is only ~80 echoes
a second, which on its own reads as a stutter rather than a wash; the density has
to come from diffusion, not from the tank.

### Two structural faults the emulator caught, both inaudible on a bench test

Worth recording because neither is a coding error — both are topology mistakes
that only show up when you measure the impulse response, and the harness's
default input is a single impulse followed by silence, which makes them obvious.

1. **A 104 ms hole.** Injecting the input into line 0 only — the thing that
   produces the bloom — starves every other line until line 0's tap fires (71 ms),
   and the output line's tap then adds its own delay. First wet energy arrived at
   104 ms. Fixed by injecting into all four lines, two at full and two at half:
   the level gradient preserves the build-up, but every line has energy at once.
2. **A 56 ms channel offset.** L was tapped from a line with no direct injection,
   so L started at 89 ms and R at 33 ms — which reads as the right side arriving
   first, not as width. Fixed by summing two tank taps per channel and giving each
   output pair one fully-injected and one half-injected line. Now 44 ms L / 33 ms
   R, and the channels sit 1.1–1.5 dB apart.

### The emulator also catches runaway feedback

An early modulation build self-oscillated on hardware. It was visible in the
harness the whole time as an envelope that never decayed (RMS pinned near 4M at
1 s), and was misread as a long tail. With an impulse input, **a flat envelope is
proof of instability**. Check it on every build.

## 9. Page-2 parameters: r6+$b..$e, and NOT in display order

Page 1's six values are `x:(r6+0)` through `x:(r6+5)`, which §6 already had. Page
2 — the screen you land on when you select the effect — is **not** at `r6+6`, and
crucially it is **not in display order** either.

Surveying r6-relative reads in the stock code gets you close but not there: DARK
REV and PLATE REV each read `r6+0..5`, plus `r6+$c` and `r6+$e`. That is enough to
know page 2 is somewhere around `$b..$e`, and no more — two different orderings
fit it, and picking the sensible-looking one is wrong.

Measured instead, with `dsp/pagemap_probe.asm`: put an unmistakable, *different*
behaviour on each candidate offset, flash once, and read the answer off the
knobs. Page 2 shows four controls, the last of them a boolean:

| knob | offset |
|---|---|
| `PRE` | **`r6+$e`** |
| `BAL` | **`r6+$b`** |
| `MONO` | **`r6+$d`** |
| `MIXF` | **`r6+$c`** (boolean mix/send) |

That also explains the stock reads: `$c` and `$e` are the mix/send mode and the
`PRE` knob, which really is DARK REV's pre-delay. Both are things a reverb needs.
BAL and MONO it leaves to the host.

`r6+6..$a` is touched by nothing. What lives there is still unknown.

**Symptom if you get this wrong**: the parameters silently read whatever is in
those slots and never change. Page-2 knobs simply do nothing, with no error.

One trap when fixing it in `tools/gen_reverb.py`: the offset is interpolated into
the assembly as text, so `P_RATE = 12` formats as `$12`, which the assembler reads
as **hex 18**. It needs `{P_RATE:x}`. That produces a working build that quietly
reads the wrong slot.

## 10. Per-instance buffers: the host runs a bump allocator

Every build up to v22 hardcoded absolute Y addresses. That works for exactly one
instance and writes through everything else. Here is how the stock effects do it.

### The mechanism

Two globals, both initialised in `P:0x002bf` and advanced by the dispatcher in
`P:0x0041e` once per effect:

    X:0x20a = 0x6000    per-instance STATE block (r7), += 0x100 each
    X:0x213 = 0x255     pointer into a TABLE of per-instance BUFFER BASES, += 1

An effect reads its own base in two instructions:

    move    x:>$213,r4
    move    x:(r4),x0           ; x0 = this instance's buffer base

and then places every buffer at `base + a fixed offset`. DARK REV's offsets are
`0x0000 0x0300 0x0320 0x0348 0x0350 0x0800 0x1000 0x2000 0x2800 0x3800 0x3a00
0x3b00 0x3c00 0x3c80 0x3d00 0x3d40 0x3d80 0x3da0`.

The dispatcher advances both pointers **twice** per loop iteration, once for FX1
and once for FX2, calling `x:(r1+$215)` (init) and `x:(r1+$235)` (process) for
each.

### The table, and what it tells you

`X:0x255` is a loaded module, 8 words, and it is the whole memory map:

    0x01000  0x04000  0x01c00  0x08000  0x02800  0x30000  0x03400  0x34000

Interleaved FX1/FX2. Separating them:

    FX1:  0x1000  0x1c00  0x2800  0x3400     stride 0xc00   =  3072 words
    FX2:  0x4000  0x8000  0x30000 0x34000    stride 0x4000  = 16384 words

which lays out as:

| Y range | |
|---|---|
| `0x0000–0x0FFF` | system, loaded modules |
| `0x1000–0x3FFF` | 4 FX1 instances, 3072 words each |
| `0x4000–0xBFFF` | 2 FX2 instances, 16384 words each |
| `0x30000+` | 2 more FX2 instances |

Three things follow:

1. **An FX2 effect gets 0x4000 words; FX1 gets 0xc00.** That is why the reverbs
   are FX2-only — they do not fit in an FX1 allocation.
2. **`0x8000 + 0x4000 = 0xC000`**, exactly where §8's probe found Y ends. The
   allocator fills Y to the last word and then jumps to a second region at
   `0x30000`, which the probe never reached (it stopped at `0x20000`).
3. Our 40K layout was about 2.5x an instance's entire allocation.

### What v23 does

All buffers are offsets from the base, and all persistent state moved out of
absolute Y into the r7 block, which is already per-instance:

    lines      base+0x0000  4 x 2048    taps 1567 1249 977 733
    allpasses  base+0x2000  4 x 1024    taps 907 673 487 331
    pre-delay  base+0x3000  1 x 2048    46 ms
                                        total 0x3800 of 0x4000

    r7+$83        tank write phase
    r7+$84..$8a   allpass phase, LFO phase, pre-delay phase, 4 damping states
    r7+$71..$78   the instance base and everything derived from it

Cost: nothing per sample. The bases are computed once per block, so the loop is
still 300 instructions. The sonic cost is real though — tank taps drop from
71 ms to 35 ms and pre-delay from 369 ms to 46 ms.

**Verification that actually proves it**: run the same build at two different
table entries (`DSP_ALLOC_IDX` in `dsp_host`) and compare the output. Base
`0x4000` and base `0x8000` produce byte-identical audio.

### Getting the base from init to process, measured not deduced

Two claims in this section were reasoned from the dispatcher listing and both
were wrong. Recording how they failed, because the failure mode is identical in
each case — a build that is clean in the emulator and unusable on hardware.

**Wrong claim 1: the base can be derived from r7.** X:0x20a and X:0x213 do
advance together, so `n = (r7 - 0x6000) >> 8; base = x:(0x255 + n)` looks sound.
Measured with `dsp/r7probe.asm` — 49 words that pass audio only when the TIME
knob equals `r7 >> 8`, so the knob position reads the register directly — r7 is
**0x6200**. The arithmetic was right, but `table[2]` is `0x1c00`, a 3072-word
**FX1** slot. A 16K layout starting there runs to `0x53ff`, through the other FX1
buffers and into FX2 slot 0. FX2 effects do not take even table entries.

**Wrong claim 2: persistent state can live anywhere in the r7 block.** Bisected:

| build | base | state | result |
|---|---|---|---|
| v25 | derived | `r7+$84..$8a` | hangs |
| v26 | hardcoded | `r7+$84..$8a` | hangs → base innocent |
| v27 | hardcoded | absolute Y | runs → state is the fault |

`r7+$71..$78` is fine *within* one call and `r7+$83` persists, but `r7+$84..$8a`
does not. DARK REV's init writes `$1a $1b $1f $82 $83 $84 $8b` and steps around
`$85..$8a` — it was avoiding host-owned words.

**What works**, measured with `dsp/baseprobe.asm` (same trick, TIME matched
against `base >> 9`): init reads `X:0x213` and stashes the base in absolute Y at

    Y:(0x735 + (r7 >> 8))    ->  0x795..0x79d for r7 = 0x6000..0x6800

the free window above the loaded coefficient module at `0x715..0x794`. The
address is absolute, but there is one word per instance, so instances do not
collide. It returns **0x4000** on hardware — an FX2 slot — and survives the trip
into process.

That leaves the phases, and one persistent word turns out to be enough: the tank,
allpass and pre-delay phases all advance by 1 per sample and differ only in mask,
so they are the same counter, and `r1` already carries it. The LFO phase and four
damping states go in the instance's own Y region, loaded and saved once per block.

### The base MUST be read in init, not in process

v23 hung. The loop was still 300 instructions, so it was never cycles -- it was
*when* the base is read.

The dispatcher advances `X:0x213` **before** it calls process:

    0004d8  x:$213 -> b ; +1 ; -> x:$213      advance
    0004f4  jsr (r2)                          call PROCESS

so by the time process runs, the pointer refers to a different instance's entry.
Reading it there returns a base that is neither yours nor necessarily aligned,
and since the tank pointers use modulo addressing, an unaligned base makes r1-r4
wander out of the buffer and into loaded modules.

The stock code says the same thing plainly, once you check the dispatch table:
DARK REV's init is `P:0x01679-0x0171a` and its process starts at `P:0x0171b`, and
the base read at `P:0x01692` is **inside init**.

v24 reads the base and derives all seven buffer addresses in init -- 31
instructions, no loop -- and stores them in the r7 block. Process just uses them,
which is also cheaper than recomputing per block.

### One trap worth its own paragraph

A modulo offset larger than the buffer is **undefined** on the DSP56300. Shrinking
the pre-delay to 2048 words while leaving the knob scaled to `v*128` meant PRE=32
asked for 4096 samples through `y:(r5+n5)` under `m5`. It does not wrap and it
does not clamp: the read returns nothing, the tank gets no input, and the reverb
goes **completely silent** — which looks nothing like an addressing bug.
