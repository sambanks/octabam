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

## 5. Next steps

1. **Find the effect dispatch** — the code that reads the effect id the ColdFire
   publishes to `0x80000ec4[track]` / `0x80000ecc[track]` (see `PARAM_PAGES.md`)
   and branches to an algorithm. Answers, in one go, why DELAY is silent on FX1
   and whether an unused id can be given an implementation.
2. **Map the parameter frame** — how the 12 descriptor parameters arrive at the
   algorithm, which is what any new effect has to consume.
3. **Find free P memory** and a splice point for a new algorithm.

Only step 3 amounts to "write a new effect"; step 1 is where the answers are.

Note the ColdFire uploads the payloads verbatim from the image, so a modified DSP
program only needs the payload rewritten in place — the record format is
understood in both directions, and the loader does no checksumming of its own.
The outer ELEK/aPLib container is rebuilt by the existing toolchain.
