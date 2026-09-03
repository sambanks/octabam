# DSP56300 side — module load map

The effects and timestretch run on the DSP, not on the ColdFire. Disassembling
the DSP program requires knowing which bytes load to which DSP address in which
memory space — at the wrong PC a disassembly is worthless. This document is the
map.

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
instances splitting the work would look like. *Inferred from the load map;
borne out by the per-chip memory model in §11 and the measured track↔chip
mapping (payload A serves tracks 5–8, payload B tracks 1–4).*

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

### The 15 one-word records are NOT a dispatch table

Each payload contains a run of **15 consecutive one-word P records** (A:
`P:0x006e5`–`0x006f3`, B: `P:0x004a5`–`0x004b3`). Fifteen is also the number of
effect descriptors, so this looked like a static effect dispatch table. **It is
not** — every one of the 30 words is `0x000000`. They are zero-initialised
scratch words. If a dispatch table exists it is built at runtime.

## 4. Disassembly

Neither Ghidra nor radare2 ships a DSP56300 target. `setup.sh` now clones and
builds the disassembler from the Access Virus emulator project
(<https://github.com/dsp56300/dsp56300>) into
`vendor/dsp56300/build/source/disassemble/dsp56kDisassemble`.

```sh
make setup                                        # clones + builds it
python3 tools/dsp_modmap.py                       # the full module map
python3 tools/dsp_modmap.py --extract A 1252 out/dsp/A_P1252.bin
vendor/dsp56300/build/source/disassemble/dsp56kDisassemble \
    -in out/dsp/A_P1252.bin -pc 1252 -le
```

**The `-le` is required.** Module data is 24-bit **little-endian**, matching how
`FUN_40001b18` maps bytes onto the three 8-bit ports (`0x20000014` gets bits
23–16 from `b[i+5]`, `0x18` gets 15–8 from `b[i+4]`, `0x1c` gets 7–0 from
`b[i+3]`). Big-endian produces plausible-looking garbage — exactly the trap the
module map exists to avoid. (`history/NOTES.md` describes the boot blobs as
big-endian; that reading does not hold for the payload modules.)

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

## 5. The effect dispatch

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

### Why DELAY is silent as a DSP insert

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

Which is exactly the observed behaviour: the parameter page works, the audio is
untouched. `0x08` has no implementation in *either* payload.

### Where DELAY actually is — ✅ ANSWERED 30 Aug 2026, externally

**It is on the ColdFire: per-frame DMA descriptor arithmetic over per-track
circular buffers in SDRAM based at `0x4F502C10`, with an EMAC loop doing the
gain and mix work.** The frame routine is `0x400031a0`. Full summary and
provenance in **`docs/EXTERNAL.md`** — this is other people's work, adopted
on their evidence and not re-verified by us (🟡).

Everything below stands: every negative in this section was correct, and the
DSP genuinely is ruled out. What the section lacked was the positive answer,
and the reason it stayed missing is worth keeping — the searches keyed on
parameter-storage addresses (the routine reads a *derived* time word), on the
FX2-id field offset (the gate is a `moveq #8` against a copied byte), and on
the `0x46xxxxxx` globals region (the rings are nowhere near it). What cracked
it was searching for the **physics** — the literals 176400 and 1,411,200 —
rather than the plumbing.

One claim of ours does not survive it: *"the ColdFire does no per-sample audio
arithmetic"* was verified only for the audio ISR at `0x4000aad0`, and the
delay's EMAC loops are per-sample arithmetic outside it. ❌

The old framing follows, still accurate as a record of what was ruled out:

A tempting explanation — "a dedicated stage in the audio graph that the FX2
slot enables" — **is an inference that a full search failed to support**; do not
re-adopt it without new evidence. What follows is what has actually been
checked.

Echo Freeze Delay is a normal per-track FX2 effect — manual §11.4.10 lists it
under "FX2 effects", alongside the three reverbs. So the contradiction is real:
a documented per-track insert whose id resolves to a passthrough.

**Ruled out, by measurement:**

* **Both slots share one dispatch.** Six `jsr (r2)` sites, all in `P:0x0041e`,
  all indexing `X:0x215`/`X:0x235`. FX1 takes the id from `r6+$1b`, FX2 from
  `r6+$1c` — that is the *only* difference between the slots.
* **No special case.** No `cmp` against id 8 anywhere in the core modules.
* **No extra stage.** The per-track path is FX1 → FX2 → a 16-iteration gain
  routine (`func_00055a`) → bookkeeping → `jmp int_00004a`. The frame loop
  (`P:0x40`) makes one call, to the unpack routine.
* **No hidden code.** A reachability sweep from the dispatch tables, the
  interrupt vectors and the bootstraps reaches **95.8%** of payload A's
  instructions and **98.5%** of payload B's. Every unreached run is small
  (≤112 instructions) and sits inside a module that is otherwise reached.
  There is no delay-sized body of unreferenced code.
* **No delay buffer.** Every non-effect module characterised: `0x2bf`, `0x3a1`,
  `0x5cb` flag handling off `r6+$1e`, `0x6f4` a small MAC helper.
  🟡 **Two of those labels are corrected by external work** (`docs/EXTERNAL.md`,
  30 Aug 2026, not re-verified by us): `0x3a1` is the **voice playback
  engine** — a 2-tap linear interpolator over the 128-word ring — not
  "parameter unpacking"; `0x2bf` is the **summing mixdown**, not a resampler.
  `func_00055a` (below) is the 24-bit ↔ dual-16-bit host packer rather than a
  gain routine. The *conclusion* of this bullet is untouched: none of them is
  a delay. **The largest modulo
  buffer anywhere in the program is 128 words** (`m6=$7f`). A delay needs
  thousands.
* **No third program.** Payloads A and B are back-to-back and the image tail
  after B is 93% zeros. A and B are the two DSP *chips*, and neither has it.

**A lead that is nothing.** `PARAM_PAGES.md` flagged `FUN_40005638` as
referencing the FILTER and DELAY descriptors directly, "outside the id tables —
the only two effects that get that treatment", suggesting buffer setup. It is
not: it is the **part defaults initialiser**, copying `E+0x3b` out of each. A
fresh part just defaults to **FX1 = FILTER, FX2 = DELAY**.

**So the delay is not dispatched as a DSP insert.** Where it *is* remains open.
Two hypotheses are ruled out below; do not mark this solved on the strength of
a third without measurement.

**Hypothesis 1 — a dedicated DSP stage.** Dead, see above.

**Hypothesis 2 — it runs on the ColdFire.** Attractive (a delay wants a buffer
bigger than the 32,768-word DSP ceiling, and SDRAM is on the CPU side), but the
evidence went against it. The audio frame ISR at `0x4000aad0` is **DMA
orchestration** — ColdFire peripheral registers `0xfc04503e` / `0xfc0450de` /
`0xfc0450fe`, host-port handshake, buffer flips — with no per-sample arithmetic
anywhere in it. Below even odds.

**The trig-key lead, also a dead end but worth recording.** `DELAY CTRL` is a
trig-key mode (table at `0x400beb76`: TRACKS / CHROMATIC / SLOTS / SLICES /
QUICK MUTE / DELAY CTRL, six 20-byte records). It looked promising because no
other effect has bespoke UI. Manual §12.7.6 settles it: the mode only sets
**TIME**, plus **SEND or VOL** depending on LOCK — ordinary parameters through
the ordinary path. The code around the table is UI drawing indexed by a RAM mode
variable. **The delay has no privileged control channel.**

### The ColdFire side — searched, and not found there either

**There is exactly one firmware section.** `elektron-firmware-tool -i` reports
`id 3 MAIN OS, 1112560 B` and nothing else. ColdFire code and both DSP payloads
are all in the file we have been searching. **No other binary is hiding it.**

**Do not anchor searches on `part+0x08`.** It comes from the *defaults
initialiser* (`FUN_40005638`) and is not the live location; any search keyed on
it returns zero, correctly. The real locations are in `PARAM_PAGES.md` §5c:

| | FX1 | FX2 |
|---|---|---|
| stored, in Part data | `Part+0x8ed80` | `Part+0x8ed88` |
| published to shared RAM | `0x80000ec4[track]` | `0x80000ecc[track]` |

**The published array is write-only from the CPU.** All 8 references to
`0x80000ecc` are stores; nothing on the ColdFire ever reads it back. **The DSP
is its only consumer.**

**The "is this track's FX2 the delay" test exists, and it is UI.** Two sites read
`Part+0x8ed88` and compare against 8 — `0x400405ba` sets a bit, `0x400452b8`
tests one — maintaining a per-track bitmask at **`0x460d1700`** = tracks whose
FX2 is the Echo Freeze Delay. All seven users of that mask are in the
`0x40040xxx`–`0x40045xxx` UI/key-handling region (build, set, clear, test).
**Nothing in the audio path reads it.** That is the DELAY CTRL green-key
machinery and nothing more.

So: the CPU knows which tracks carry the delay, for lighting keys. It hands the
id to the DSP. The DSP dispatches it to a passthrough. **No code on either
processor does anything audible with that fact.**

**The remaining thread — find the parameter consumer.** DELAY declares all
twelve parameters and they are published into the DSP param block like any other
effect's. Parameters that nothing reads would be strange. The passthrough stub
reads none of them, so **whatever reads the delay's parameters is the delay.**
That is a search for the consumer of data we know is published, rather than for
a comparison that may not exist. Working hypothesis (it fits the
FREEZE behaviour): it shares the **sampling/recorder** machinery rather than the
FX chain — a delay is re-reading recorded audio, which is what the voice path
already does.

### Hardware evidence: substituting id `0x08`'s dispatch

Three builds, each stamping its own effect name so the unit says which is
running (`DELAYPROBE=stock|silence|send` in `tools/build_bus.py`). All three
restore stock DELAY to the FX2 chooser as a 4th entry; they differ only in what
id `0x08` dispatches to.

| build | id `0x08` runs | result on the unit |
|---|---|---|
| control | stock passthrough | **delay WORKS** |
| silence | a stub writing zeros | **the whole track goes silent** (dry included); other tracks unaffected; DELAY CTRL keys still lit |

**What the control establishes.** Without it, "the delay went silent" could not
be told apart from "the delay never worked under this firmware at all". With
it: **the chooser replacement wires up a stock effect correctly** — DELAY
picked from the 4-entry menu behaves normally when its dispatch is left alone.
That is what makes the `send` build below a meaningful test rather than a shot
in the dark.

**The silence build says nothing about where the delay is.** The FX2 insert is
a series insert; writing zeros there kills the track's audio whether the delay
sits upstream of it, downstream of it, or anywhere else. Both surviving
hypotheses predict exactly what was observed. The experiment could only ever
have been informative if the delay had *survived*. In particular the result
does **not** support reading the delay as a send rather than a series insert —
the dry that survives is on *other* tracks, not on the track carrying the
delay.

**Confirmed and standing:** the DELAY CTRL keys stay lit under the silence
build. Those come from the stored Part id and the `0x460d1700` bitmask, which
no DSP dispatch change can reach — exactly what the static analysis predicts,
observed on hardware.

### Our code can hold the delay's slot

| build | id `0x08` runs | result |
|---|---|---|
| send | the SEND client | **delay still WORKS** |

**What this establishes, exactly:** id `0x08`'s DSP slot can run our code and the
stock Echo Freeze Delay keeps working, **provided that code passes the audio
through unchanged.** That is the question BUS.md's parked design needed
answered, and the answer is yes.

**And a structural fact about where the delay is.** By listening test: the
send taps **pre-delay** — the reverb receives dry, not repeats. So the stock
delay is applied **downstream of the FX2 insert**, in the output/mix path
rather than in the insert chain — the one positive constraint on its location
that static search never produced.

It also explains the silence result: zeroing the insert starves everything
downstream of it, the delay included.

**Consequence for anything we build: we cannot tap the stock delay's output.**
Every slot we can reach is upstream of it. A "delay into reverb" routing is
therefore impossible with the *stock* delay — it is only available via our own
`DELAY SERVER`, whose `→VERB` cross-send exists for exactly that (`BUS.md`).

**What it does NOT establish — and the temptation is to claim it.** The send
client leaves the buffer contents byte-identical to the passthrough; it only
taps. So this says *nothing* about whether the delay reads that buffer, nor
where the delay is implemented. Silence killed it and passthrough-plus-tap did
not, which is exactly what "the delay is fed by the track's audio" predicts and
is equally consistent with every remaining hypothesis about *where*. The
location question is still open.

**Design consequence.** A track can run
the stock delay on FX2 *and* feed the BusVerb bus from the same slot — so the
FX1 filter is no longer the price. See BUS.md.

**Confirmed end-to-end.** With a BusVerb server on another track
in the bank and DELAY's `FB` knob turned up, the reverb send audibly works from
inside the delay's slot. So our send client is not merely dispatched there — it
is tapping the audio and reaching the bus, while the stock delay runs.

**A track can therefore have the stock Echo Freeze Delay AND the shared reverb
at once**, which stock hardware cannot do at all (`PARAM_PAGES.md` §5d), at the
cost of neither the FX1 filter nor any additional stock effect.

**The catch, which is a real design problem, not a detail.** The send client
reads its two levels from `p0`/`p1`, and on this id those are DELAY's own knobs:

| | | | | | |
|---|---|---|---|---|---|
| p0 `TIME` (47) | p1 `FB` (0) | p2 `VOL` (127) | p3 `BASE` (0) | p4 `WDTH` (127) | p5 `SEND` (0) |
| p6 `X` (0) | p7 `TAPE` (1) | p8 `DIR` (127) | p9 `SYNC` (1) | p10 `LOCK` (0) | p11 `PASS` (0) |

`p0`/`p1` are TIME and FB — the two you would least want to lose, and **FB is
worst of all because it couples the two things that must be independent**: FB at
0 means no repeats *and* no send; FB up means repeats *and* send. They cannot be
set separately.

DELAY declares all twelve parameters, so any offset we read is one of its
controls. Options: a fixed level; a deliberately chosen sacrificial parameter
(`p6 X` and `p11 PASS` both default to 0 and are the least obviously essential,
though what they do is unverified); or sourcing the level outside the param
block entirely. **Unresolved.**

### Two limits on the sweep above — do not over-read it

**The DSP self-modifies.** Frame setup writes `move x0,p:>$58c` and
`p:>$59b` — it patches its own instructions at runtime. Static reachability
cannot see paths the program creates for itself, so "95.8% reached" bounds how
much *unreferenced* code exists; it does not prove all behaviour is accounted
for.

**"No large modulo buffer" is NOT evidence of no delay line.** Nothing in the
program uses a modulo bigger than `m6=$7f` (128 words), but it does not follow
that no delay line exists: a delay line needs no modulo at all. Module `0x2bf`
walks the shared window with `m0` linear, which is exactly how a long buffer
would be read. (🟡 `0x2bf` is now externally identified as the summing
mixdown — `docs/EXTERNAL.md`. The caution in this paragraph stands on its own
reasoning regardless.) (There is no external memory on this board; the shared window
runs at the same speed as internal memory — see `CHIP.md`.) The reachability
sweep and the module-by-module characterisation are what carry the conclusion,
not the modulo scan.

### Stock uses `X:0x30000` as per-frame parameter staging

This matters for `modules/busdelay/delay_server.asm`. Frame setup copies 72 words out of
`X:0x30000` into `y:0x1b8`, then writes parameter values back into `X:0x30000`:

```asm
0000a8: move  #>$30000,r1
0000ac: do    #<$48,>$b0
0000ae: move  x:(r1)+,x0
0000af: move  x0,y:(r4)+        ; -> y:0x1b8
...
0000b6: move  a1,x:(r1)+        ; and writes params back into 0x30000
```

**BusDelay hardcodes `Y:0x30000` / `Y:0x38000` as its delay-line base — and
X, Y and P DO alias in the shared window `0x30000`–`0x3FFFF`.** Measured with
`dsp/alias_probe.asm`; see `CHIP.md`. The per-server ceiling there is
**65,536 shared-window words (1.49 s)**. Reason about the shared window as ONE
memory.

A superficially convincing argument that the spaces could not alias is
falsified by that measurement, and is worth recording so it is not re-derived:
the allocator table at `X:0x255` gives FX2 bases `0x4000`, `0x8000`,
**`0x30000`**, `0x34000` (§10), so stock places a 16,384-word **`Y:0x30000`**
effect buffer under the same addresses the frame setup stages parameters
through in **`X:0x30000`** — which looks like proof the spaces must be
separate. They are not; the probe wins.

**The emulator cannot answer aliasing questions either way**: `dsp_host` keeps
X and Y as separate arrays by construction — the `.mem` format tags every
module with its space — so it reports "no aliasing" regardless of what the
board does.

`MULTIBCOMP` (`0x19`) also points at the stub. It appears in **neither** of the
manual's FX1/FX2 lists and its parameter labels are copied from DJ EQ — an
unfinished entry that was never exposed, and **distinct from the Dynamix
Compressor**, which is `0x18` and has real code (180 words at `0x01aa4`).

### The stub is also the ABI specification

Those seven instructions are a complete worked example of an effect's process
routine: **`r0` = input buffer, `r1` = output buffer, `n7` = sample count, two
interleaved channels, `rts` when done.** Any new effect has to satisfy that
contract, and here it is in full.

### Module records are NOT routine boundaries

Measured while sizing how much program space could be reclaimed.
**A payload module record says where a chunk of words is loaded,
nothing more.** The loader lays consecutive records down contiguously, and an
effect's code runs straight across the seam. So:

* **"No id points at this module" is not evidence the module is dead.**
* **A module's word count is not the effect's size.**

The case that proves it. Four small P modules — `0x00d64`, `0x00d6a`, `0x00d70`
(6 words each) and `0x00d76` (32) — have **no entry in either dispatch table**.
They look free. They are **PHASER's**, and PHASER reaches them by falling off the
end of its own record:

```asm
do  #<$2,>$d89     ; PHASER's loop end -- inside the 32-word block
do  n7,>$d84       ; likewise
```

They read as mid-routine too: biquad `mpy`/`mac` cascades, **no `rts` anywhere**,
three identical 6-word sections falling through into each other, the last block
ending `bra $7b0`. That is an unrolled cascade entered at a computed offset —
jump in N sections from the end, fall through to a shared tail.

**PHASER's true extent is `0x00cc7`–`0x00d96` = 207 words, not the 157 its record
claims.**

Every other DSP-implemented effect was checked the same way — disassemble the
module, take the maximum *control-flow* target, compare against the record end:

| effect | module span | max CF target | |
|---|---|---|---|
| FILTER | `0x007d1`–`0x00aa8` (727) | `0x00a3d` | inside |
| SPATIALIZER | `0x00aa8`–`0x00bad` (261) | `0x00baa` | inside |
| EQUALIZER | `0x00bad`–`0x00cc7` (282) | `0x00cc5` | inside |
| **PHASER** | `0x00cc7`–`0x00d64` (157) | **`0x00d89`** | **runs past** |
| FLANGER | `0x00d96`–`0x00eb7` (289) | `0x00e9c` | inside |
| COMPRESSOR | `0x01aa4`–`0x01b58` (180) | `0x01b55` | inside |
| LO-FI | `0x01b58`–`0x01d71` (537) | `0x01d6b` | inside |
| DJ EQ | `0x01d71`–`0x01eca` (345) | `0x01ec7` | inside |
| COMB | `0x01eca`–`0x01fdf` (277) | `0x01fd4` | inside |

**PHASER is the only one that spans records**, so the other eight can be sized by
their records after all.

**Match on control flow only.** A first pass matched every `>$…` operand and
flagged four effects as running past. Those were long immediates — `move
#>$2000,x0` — not branch targets. The tell was targets at `0x02000`, past the end
of the whole FX region. Restrict to `do`/`rep`/`jmp`/`jsr`/`bra`/`bsr`/`Jcc`.

**There is shared code below the FX region.** PHASER's `bra $7b0` lands inside the
85-word module at `0x00773`–`0x007c8`, under where the algorithms start and right
below the null stub. At least one effect calls out to common routines, so that
region is not free either. Who else does is unmapped.

**Rule before overwriting any neighbour: disassemble it and check its
control-flow targets.** The module map alone will mislead you.

## 6. How parameters reach the algorithm

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

### The effect ABI — partly settled

| register | meaning | confidence |
|---|---|---|
| `r6` | this instance's parameter block | **confirmed** — dispatcher sets it, effects read `x:(r6+0..5)` |
| `x:(r6+0)` … `x:(r6+5)` | page-1 parameters, `value << 16` | **confirmed** four ways (§6) |
| `r7` | per-instance state block | **confirmed** — dispatcher sets `r7 = x:0x20a + 0x100` |
| `n7` | frame count | confirmed for the stub; effects also read `x:0x20c` |
| `r0` | audio buffer | **NOT as first documented — see below** |

> **`r0` = input / `r1` = output is the passthrough STUB's convention, and the
> stub is the degenerate case — it is not the effect ABI.** Real effects do not
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

> **This section is the bring-up record, kept for provenance.** The plan at
> its end ("develop in isolation, integrate by imitation") is what was built,
> and the harness has long since validated far more than a reverb — the
> current description of the working system is **`docs/HARNESS.md`**, and the
> functional baseline it can prove is `docs/TESTPASS.md`.

**Working**: memory loading, the emulator, single-stepped calls via the DSP's own
`jsr`, output capture. The passthrough stub returns exactly the two impulse
samples it should, and that is a genuine end-to-end validation of the plumbing.

**Frame context.** The effects depend on control words no module
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

**Not working** *(as of this snapshot — RETRACTED since; see the note at the
top of §6b)*: real effects run without faulting but produce no tail, because
the audio buffer convention above is unresolved. Until that is closed the harness
cannot validate a reverb, which was the whole point of building it. *(Closed by
route 1 below: the new effects use our own convention, and the harness now
renders the full bus — `docs/HARNESS.md`.)*

⚠️ **TOOLING, before you read any ColdFire disassembly below.** radare2's
m68k backend cannot decode this CPU's ColdFire V4e extensions — `mvs`, `mvz`,
`mov3q` and the EMAC ops all come back `invalid`, and because r2 assumes two
bytes, the following extension word is decoded as a *separate, ordinary
looking* instruction. The stream desynchronises and shows code that is not
there. **6,757 such instructions exist below `0x40098000`, over 149 pages.**
Use `scripts/disasm.sh emac <addr>` (objdump `-m m68k:cfv4e`). The load-bearing
ColdFire work here came from Ghidra or from objdump and was re-checked
30 Aug 2026 — see `docs/EXTERNAL.md` §5.

### Why address-guessing kept failing: the audio is DMA'd in

❌ **RETRACTED 30 Aug 2026 — "audio does not arrive over the ESAI" was
WRONG, and the reasoning below is the trap.** The vector reading is accurate;
the inference from it is not. **A DMA-serviced peripheral needs no interrupt
vectors at all**, so dead ESAI vectors say nothing about whether the ESAI
carries audio. It does: both DSPs fully configure their ESAIs at boot
(payload A `P:0x30026`, and a second port right after it) —
`M_TMOD=1` network mode, `M_TDC=$7` (8 slots), `M_TSMA=$ff` enabling all
eight, transmit and receive both enabled, and a live `movep a,x:<<M_TX0`.
✅ **Verified in our own `payload_A.asm`**, prompted by an external finding
(`docs/EXTERNAL.md`). Note the standing internal contradiction this leaves
in the record: `CHIP.md` has labelled that very module "host-port loader +
**ESAI setup**" the whole time, and nobody noticed the two documents
disagreeing.

The host-port/DMA path described below is real and still stands — it is how
the *frame blocks* move. What is retracted is the exclusivity: the DMA path
is not the only audio path, and the ESAI is not idle.

The interrupt vector table at `P:0x00000` decodes cleanly. The ESAI vectors
(`0x30`–`0x3e`) are all `jmp` to themselves — the unused-vector idiom — which
was read (wrongly, see above) as meaning audio
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
is exactly why guessing addresses (`X:0`, `0xa0`, `0xb0`,
`0x110`, both ping-pong states) produces silence. The buffer addresses, the
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

## 6c. Tempo and the DSP — the ColdFire side, read (24 Aug 2026)

Sam wants tempo sync for BusDelay. The question is whether the DSP is ever
told the tempo. This is a **static** pass over the ColdFire image with r2
(`scripts/disasm.sh`; Ghidra is no longer installed here). Every claim below
is *read from code*, not measured on hardware; the TPROBE flash
(`dsp/tempoprobe.asm`) is the measurement, and it was built and staged as
`out/OCTATRACK_OCTABAMT1.bin` the same day, unflashed.

**What the tempo is.** `_DAT_80001814` holds **BPM × 24**, clamped to
`0x2d0..0x1c20` (720..7200 = 30..300 BPM) at both writers (`0x40005c4a`,
`0x4004bc7e`). It is shadowed to `0x80000020` and latched per frame into
`0x8000181c`; the sequencer's phase increment is `0x80001820 = −2³¹/tempo24`
(`NOTES.md`, and the frame builder at `0x4000ca96`; stored *negative* — a
signed `divs.l` of `0x80000000` that objdump prints as `remsl`, settled
2 Sep 2026 in `EXTERNAL.md` §6 — and negated by its consumers).

**How a frame reaches the DSP** — the transfer routine at `0x40004860`, a
7-step state machine (`0x46104d3e`) over eDMA channel 0 (TCD at
`0xFC045000`, DADDR fixed at the port `0x2000001c`, 16-byte bursts,
4 minor loops). Before each DMA it writes two halfwords to the port: the DSP
destination (`0x6000 | X address`) and the count in halfwords (two per
24-bit word). Per ping (`0x800000e0`/`e4` select), per DSP (chip-select
`0xFC0A400C`):

| ColdFire source | words | DSP dest | what |
|---|---|---|---|
| `0x800021d0` (A) / `0x80001c90` (B) + ping·`0xa80` | 336 | `X:0x080` | **four 84-word per-track records** (`0x150` bytes each) |
| `0x80000110` / `0x80000210` + ping·`0x200` | 64 | `X:0x000` | four 16-word per-voice records |
| `0x80005460` + slot·`0x80` | 32 | `X:0x800` | a sample-slot record, on demand |
| `0x80003190` + ping·`0x400` | 256 | ← `X:0x400` | read-back (DSP → CPU) |

The 336-word block is assembled by the packer at `0x4000d3fc`–`0x4000d55e`:
for each of 8 tracks it calls the machine-type handler from the table at
`0x400d61d0` (rotated from `0x400d61f0`), with the record pointer parked at
`0x80001c80`. The 72-word staging block the DSP copies out of `X:0x30000`
(§5) is the 84-word record after the DSP's unpack; the packer also steps a
second per-track cursor by `0x48` = 72.

**What consumes the tempo inside the packer's handlers** — three sites, all
turning tempo into a *rate*, none copying it:

* `0x400074a0` / `0x40007502` — LFO speed: `tempo24 << 18`, a MULT table at
  `0x400ab83a`, and a ×`0x55555556` (÷3) step for the triplet multipliers.
  The DSP receives an LFO phase increment.
* `0x400060c4` / `0x40006d48` — read the phase increment `0x80001820`
  (negated) into per-voice records: the timestretch/trig position.
  ❌ **Retracted for `0x400060c4`, 2 Sep 2026**: that site is the
  PICKUP-machine recorder arm length — the FIN/FOUT ladder entry ÷ tempo24,
  in samples, fed to the arm function (`EXTERNAL.md` §6). The value still
  never reaches a frame record. `0x40006d48` has not been re-read.
* `0x40004bd2` (runs right after the transfer) — advances a playback
  position by `tempo24 << 4` per frame **only when byte `+0x2b` of the
  per-voice record is set**, else by the constant `0xb40` (= 120 BPM × 24).
  So a "follow tempo" voice gets its *position* from tempo; the DSP still
  never sees BPM.

The two remaining tempo readers outside the sequencer are UI: `0x40031d70`
(`((x+1102)·2205/tempo24 + 3600)·7200`, one caller, a `sprintf` of
`%03d/%03d` — sample length in bars) and `0x4002f7ec` (a `%ds` display).
A third non-UI reader turned up 2 Sep 2026: `0x4006e3b2` converts the
recorder's RLEN to samples, `(raw+1) × 63504000 / (4·tempo24)`
(`EXTERNAL.md` §6). It feeds the CPU-side recorder, not a frame record, so
the conclusion below is unchanged.

**Conclusion of the static pass (inferred, one flash from measured):** the
ColdFire computes every tempo-derived rate itself and ships rates, not BPM.
No code path found copies `0x80001814`, `0x8000181c` or `0x80000020` into
a frame record. **What would falsify it:** a word in the TPROBE capture
whose 60→180 BPM ratio is 3 (or ⅓). A word that *scales* with tempo but is
not the tempo — an LFO increment on a track with a tempo-synced LFO — is
the expected false positive; run the probe with the LFO off.

**If falsified: cheap.** Read the word in BusDelay; ~40 words of payload B.
**If confirmed: a ColdFire code patch** — the first in this project — to
store `tempo24` into a spare word of the per-track record inside the
packer (the record is 84 words, the DSP stages 72; whether the tail 12 are
free is the next thing to read, in the handler at `0x400068e4`). It is one
`move.l` plus finding the slot; the risk is that it is a new class of edit.

**Ceiling either way:** a server owns 65,536 shared-window words = 1.49 s
(`CHIP.md`). At 120 BPM a bar is 2 s, so sync divisions stop around a
dotted half; the division table must saturate, not wrap.

### 6c-i. The patch, built (24 Aug 2026, same day — unflashed)

Sam chose the patch without waiting for the probe, and it turned out not to
need the 84-word record at all: **the per-voice record is the better
vehicle.** The routine at `0x40004bd2` writes the FX ids into the 0x40-byte
per-voice record at `0x80000110 + ping·0x200 + track·0x40` (+0x36/+0x38 —
which are `x:$208+$1b/$1c`, the ids the DSP reads). Each **16-bit halfword
of that record is one DSP word, `<< 8`** — that is why knobs sit at bits
16–23 and companions at 8–15, and why the low byte "is never published"
(`PARAM_PAGES.md`). So FX2's `x:(r6+i)` is halfword `12+i`, and the
documented-dead `r6+$6..$a` are record bytes `0x24..0x2c` that nothing
**reads** — but, corrected 24 Aug 2026 (`docs/midi_re_note.md`): the frame
builder REWRITES the whole record every frame (`0x4000cb6e..0x4000cb7c`
copies `0x80000830+72t` into `+0x24..+0x35` before `jsr 0x40004bd4`), so a
cave must re-store its value on every pass — which the tempo cave does,
because the hook runs after the copy. Still free on those terms:
`+0x28/+0x2a/+0x2c` (`r6+$8/$9/$a`).

`modules/tempo-sync/tempo_cave.s` (56 bytes, `m68k-elf-as -mcpu=5407`, bytes pinned in
`build_bus.py` and re-checked against a fresh assembly when the toolchain
is present) FLOATS: it is planted at the first 0x80-aligned address past the
descriptor clones, inside the stock zero run `0x400d6b00..0x400d7c3c` —
`0x400d7000` in the shipping image, whose three clones end exactly there
(pinned until 3 Sep 2026, when a fourth clone ran into it). The hook replaces the
three instructions at `0x40004d40` (`move.b 0xdbc(a0),d2 / ext.w d2 /
move.w d2,0x38(a2)`) with `jsr cave` + two `nop`s; the cave replays them,
then **only for FX2 id 6 or 7** stores `tempo24` to `+0x24` (`r6+$6`) and
`42,336,000 / tempo24` — samples per MIDI clock in Q12.4, fits 16 bits
down to 30 BPM — to `+0x26` (`r6+$7`), using the ColdFire's `divu.l`. d0/d1
saved; ~40 cycles per our-track per frame. `NOTEMPO=1` omits it.

DSP side (`modules/busdelay/delay_server.asm`, the block after the TIME decode), final
form after three revisions in the day — **TIME is a free dial with a STICKY
SNAP** (R56): `free = knob·128+64`, `tol = free/16`; the last division
M ∈ {2,3,4,6,8,9,12,16,18,24} clocks (1/32T … 1/4) with `|ticks·M − free|
< tol` becomes *held* when the knob moves, and held survives tempo changes
until the knob moves again; `TIME = held ? min(ticks·held, 16320) : free`.
Branch-free (one signed `mpy` + `abs`/`cmp`/`tlt` per candidate), state at
Y `0908h`/`0909h` with absolute addressing, per core not per instance (two
delays on one core re-evaluate every block — correct, not sticky; one
server per core is the design). Unpublished ticks → free, unchanged
behaviour. The earlier forms — a SYNC bit in FRZE (R53: position 2 froze
on the unit, unexplained) and an always-synced 12-zone TIME (R54: worked,
but "steps on a free dial" felt wrong) — are in the history. 1/2T and 1/4.
are not candidates (never fit the line below ~170 BPM).

**The panel prints the division** (`modules/tempo-sync/time_fmt.s`, a second ColdFire cave
floating behind the tempo cave — `0x400d7080` in the shipping image (moved 24 Aug when the tempo cave grew to 104 bytes; was `0x400d7040`), 288 bytes, registered as TIME's `A` formatter with `B=0` —
stock DELAY TIME's shape): the same rule with the same integers, its own
`last/held` in cave RAM (per panel), `"1/8"` etc. while held, else ms.
`PARAM_PAGES.md` §7 has the formatter ABI. `verify_menu` allows exactly
this one exception to "a count-128 knob has zero formatters".

**Measured locally, 120 BPM, all 128 knob positions:** every position
matches the rule (59 snap, 69 free), the free fallback is unchanged. **R56 confirmed on the unit the same evening**: labels draw, snap holds
through tempo changes, audio clean. Sam's question, answered: no
longer repeats were lost — the dial's 370 ms ceiling is the line's, and
the snap only replaces values near a division.

**TIME slew (R55, same day).** TIME crackled when turned — pre-existing:
it is applied per block, so the read head stepped. Now a one-pole per
block, 1/1024 in Q8, state at Y `0907h` (absolute addressing beside the
proven `0901h–0904h`; zero seeds from the target). Worst case ~1
sample/sample (an octave, gone in a few blocks); a one-zone synced step
bends ~2 semitones and settles in ~1 s. The emulator exercises only the
seed path (every render starts at the target) — the glide itself is
hardware-judged.

**Measured locally (emulator, impulse, FDBK 0), 120 BPM (both ends of every
zone) and 97.3 BPM:** every knob zone lands on `int(ticks·M)` to the sample, the top zones saturate
at 16,320, and SYNC with nothing published reproduces the SYNC-off echo
time exactly. What the emulator cannot show: whether the ColdFire hook is
reached and whether `0x8000181c` holds tempo24 at that moment — that is the
R48 flash. Falsifier: with SYNC on and the knob swept, the echo time on
hardware follows the knob linearly (the fallback) instead of stepping.
⚠️ `DFRZ=2` does NOT test SYNC — the override forces the decoded flag
VALUE, so 2 is "frozen"; drive SYNC locally with `-params` index 11 = 2.

**R48–R50 killed every voice** (24 Aug: B/C/D input lights on at boot,
UI and sequencer alive, stems will not start). Bisected by flash: R49 (the
divide guarded) same; **R50 (`NOTEMPO=1`, ColdFire untouched) same; R52
(= R47, HEAD) works.** So the DSP-side change did it, and its only new
memory writes were the init-built division table at Y `0910h–091fh`
through `(r1)+` — `m1` is not guaranteed linear at init, and "stock does
not use that Y range" was a disassembly grep, not a measurement. R53
replaces the table with a cmp/`tge` immediate chain: no memory writes, no
address registers. The paragraph below records the divide-by-zero theory
that R49 falsified; the guard stays because the defect is real.

**R48's first theory (falsified as THE cause, kept as a defect).** Inferred
cause — not measured, but a real defect either way: `0x8000181c` is only
latched at the end of the frame builder's voice pass, so the hooked
routine can run against a zero tempo before that, and `divu.l` by zero
TRAPS. The emulator is structurally blind to this (it never runs the
ColdFire). R49 = the same cave with `beq` past the divide on zero (58
bytes). Falsifier: if R49 hangs the same way, the cause is elsewhere in
the hook (context, stack, or the cave region not being what the running
image executes) and the next step is a cave that does nothing but replay
the displaced instructions.

## 7. Where a new effect can go, and what fits

### Internal P memory is contiguous and full

| payload | internal P modules | words used | top | gaps |
|---|---|---|---|---|
| A | 66 | 8,159 | `P:0x01fdf` | **none** |
| B | 46 | 7,583 | `P:0x01d9f` | **none** |

Not one hole in either image. Payload A ends at `0x01fdf`, which is 99.6% of
`0x2000` — which looks like an 8 K internal P RAM essentially full. It is not:

### There is memory above 8K (hardware-measured)

`tools/build_dsptest.py` (in git history) relocated CHORUS from `P:0x00eb7` to `P:0x02000` (three
words per payload: the module's load-address field and its two dispatch entries).
Flashed to the MKII: **CHORUS works normally.**

So `P:0x2000` is real, usable, executable memory. The program ending at `0x01fdf`
is where this build happens to stop, not a hardware boundary. **A new effect can
simply be appended** rather than having to displace an existing one — the much
easier workflow.

Proven usable so far: `P:0x02000`–`P:0x02149` (CHORUS's 329 words). The upper
bound is unknown; relocating several clean effects to `0x4000`, `0x8000`, `0xc000`
in one build would bracket it in a single flash, if it ever matters.

There is no external memory on this board and no speed penalty above the
internal range: the shared window runs at the same speed as internal memory
(see `CHIP.md`).

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

## 7c. Delay memory

Two corrections to figures produced by scanning immediates too loosely:

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

**RESOLVED, negatively (`dsp/xmem_probe.asm`): the high X region is NOT
usable memory on hardware.**

A single-word probe cannot earn that conclusion, and its blind spots are worth
keeping: one of three single-word test addresses (`X:0x09000`) turns out to be
clobbered even in the *emulator*, where only the DSP's own setup routine and
the effect run — so "unreferenced anywhere" from a static scan was already
wrong, exactly as this section warns for the stock reverbs. Per-address
signatures also make a single-address failure sound identical to total
failure, and readbacks must be A2-cleaned like everything else.

The probe as written earns the conclusion instead:
* writes and verifies a full **1024-word block** at `0x0C000` and another at
  `0x0F000`, not isolated words;
* uses a **walking value**, so no two words share a pattern and a dead address
  whose bus merely holds the last value written cannot pass;
* A2-cleans every readback before comparing;
* signals pass as half-volume and each block's failure on a *separate*
  channel, so the outcomes are audibly distinct;
* **and was validated in `tools/dsp_host` first**, where X memory is real: it
  passes there, output exactly half of input. A probe that always fails is
  indistinguishable from real failure unless you check this.

On hardware both blocks fail. High X buys nothing: **a reverb's memory ceiling
is its FX2 allocation — 32,768 words (743 ms) as originally pooled, and
65,536 shared-window words (1.49 s) per server since the XBUS split (see
`CHIP.md`).** A Blackhole-class allocation in high X is off the table. Do not
re-chase this without reading the above.

## 7d. HARDWARE: custom DSP code runs

`dsp/probe.asm` — 17 words, written by us — assembled, inserted over CHORUS's
module, dispatched via a new effect id `0x06` with its own descriptor, and
**audibly distorting on a real MKII**. The whole path works end to end:

    assemble -> insert module -> dispatch tables -> 5 ColdFire tables -> flash -> sound

It also proves **X:0x4000 is real read/write memory**, since the probe stamps a
mask there in init and reads it back in process to use as the audio mask.

### Bring-up hangs: the candidate causes

Three bring-up attempts hung the DSP (audio stops, sequencer freezes on trig 1
-- the sequencer is clocked by the DSP frame interrupt, so a DSP stall looks
exactly like that). The working attempt removed three things at once, so which
one mattered is not established. The candidates, in order of suspicion:

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

The process rule: change one variable per hardware iteration, and run the
control first -- probing addresses known to exist is what converts "the memory
must be absent" into "the code is wrong".

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

### That budget does not belong to effects

The figures below are correct as measurements but do not mean 664 ms of delay
memory is available to an effect. X:0x4000/0xc000/0xf000 respond to reads and
writes, but the region is not *allocated* to effects, and using it does not
work: a self-chosen buffer neither persists reliably nor is safe to write in
bulk.

How the stock reverbs actually do it, from DARK REV's disassembly:

* it never loads an address above 0x200 into an address register, apart from two
  loaded lookup tables;
* it reads its modulo registers from a table -- `move #>$8cf3,r3` then
  `move x:(r3+$8),m4`;
* that table at X:0x8cfb is a list of DELAY LENGTHS:
  `28 36 58 82 126 190 250 408 646 922 1376 2047 608 896 1292 2047`
* and it makes heavy use of Y memory (103 instructions) at low addresses.

So effects are given small buffers in low Y memory and take their delay lengths
from a table. The longest line DARK uses is 2,047 words -- about 46 ms, not
664 ms. A reverb here is built from a few thousand words in total, which
is why the stock ones sound small.

Four 4096-word lines in self-chosen X memory would be roughly 8x more delay
memory than the hardware actually hands an effect, in a memory space that is
not the effect's.

### The measured figures, which stand as measurements

| resource | available | stock comparison |
|---|---|---|
| free delay memory | **29,288 words / 664 ms** | DARK REV uses ~7,600 / 172 ms |
| plus the shared gap `0x1d9f–0x483f` | 10,913 / 247 ms | currently PLATE + DARK |
| code space (replace DARK) | 1,067 words | — |
| code space (all three reverbs) | 2,724 words | — |
| cycle budget | since measured — see `CHIP.md` | two stock reverbs already glitch |

The cycle budget has since been measured (`CHIP.md`); the one empirical
calibration visible from stock alone is that two stock reverbs at once glitch.

### Development loop

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

Note the ColdFire uploads the payloads verbatim from the image, so a modified DSP
program only needs the payload rewritten in place — the record format is
understood in both directions, and the loader does no checksumming of its own.
The outer ELEK/aPLib container is rebuilt by the existing toolchain.

## 8. HARDWARE: Y memory ends at 0xC000

`dsp/ymemprobe.asm` (in git history) settles the question for Y, which is
where the delay buffers actually live.

The probe is a **wet-only** echo whose buffer base is chosen by `p0`:

    base = (p0 + 1) << 10          p0=0 -> Y:0x400  ...  p0=127 -> Y:0x20000

1024 words at that base, tap 1000, feedback 0.5. Wet-only is the point: it turns
a judgement call about echo quality into a yes/no, because silence is then a real
answer rather than an ambiguous one. Sweep `p0` and note where it stops.

**Result: clean echo up to p0=46, silence from p0=47.** So Y is real through
`0xBFFF` and absent at `0xC000` — **48K words**. Loaded modules end at `0x794`,
so `0x795–0xBFFF` is free: **46K words, roughly 1.04 s of delay at 44.1 kHz** —
*internal only; there is another 64K shared window at `0x30000`, see the warning below*.

> ⚠️ **INCOMPLETE — this probe stopped at `0x20000` and missed a whole region.**
> A `<<12` re-sweep on hardware found a **second region — the shared window at
> `0x30000–0x3FFFF`: 64K words**, echoing cleanly, freezing only at `0x40000`.
> That is where the allocator's other four FX2 slots live; an effect that
> treats them as absent silently runs dry on half the tracks.
> See "Y memory, measured end to end" below.

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

> **This table is knob-LABEL to offset, and stock's labels are misleading.**
> `$c` is the slot DARK's algorithm reads its pre-delay from, but the knob
> *displayed* as `PRE` drives `$e`; `$c` is driven by the knob displayed as
> `MIXF`. Both statements are true at once and they are easy to conflate --
> "correcting" this table the wrong way and renaming page-2 slots against the
> mapping produces page-2 knobs that do nothing. `REVERB.md` warns about
> precisely this: page 2 is left unrenamed because the descriptor's display
> order conflicts with the probed mapping. This table is label-to-offset
> only; the display-SLOT-index to offset mapping is measured in the next
> section.

### Page-2 DISPLAY SLOT -> offset, measured (dsp/page2_probe.asm)

The table above is knob-LABEL to offset. What a clone actually needs is
display-SLOT-INDEX to offset -- and inferring it
from stock's labels gets it wrong. Measured with `dsp/page2_probe.asm`: give
each offset a distinct audible signature, expose all six page-2 slots with a
full 0..127 range, flash once, sweep each knob.

| page-2 display slot | drives |
|---|---|
| 6 | **`r6+$c`** bits 16-22 (knob field; also appears in `$b`) |
| 7 | **`r6+$c`** bits 8-15 |
| 8 | **`r6+$d`** knob field |
| 9 | **`r6+$d`** low bits |
| 10 | **`r6+$e`** knob field |
| 11 | **`r6+$e`** low bits |

**All six page-2 slots reach the DSP.** The reasoning matters as much as the
table:

* A knob arrives as `value<<16`, occupying bits 16-22. **The low bits of the
  same word are a separate, independently addressable field** — this is what
  stock means by "`$e` is a FLAG word" read with `btst #$8`. One word carries
  a continuous control AND a small select. That is how stock FILTER shows six
  page-2 controls (four of them count-2 booleans) while its DSP reads only
  `$c`, `$d`, `$e`.
* Slots therefore pair up: **even slot = knob field, odd slot = companion
  field of the same word.** 8/9 share `$d`, 10/11 share `$e`.
* **A probe that only compares the whole word against `64<<16` cannot see the
  companion field at all** — and wrongly concludes slots 7/9/11 are dead and
  `$c` unreachable. Both conclusions are wrong.
* `r6+$6..$a` really are dead — probed explicitly, nothing responds.
* Page-class A (`0x40032814`, e.g. FILTER) is **not** a richer alternative:
  cloning a class-A donor rendered only one page-2 knob, because that class
  sources its page layout from the 20-byte-stride array at `0x46c7d244`
  (`PARAM_PAGES.md` §4) which a cloned descriptor does not populate. Stay on
  class B for cloned effects.
* Watch the **value COUNT and MIN**: slots inheriting count 2 are booleans a
  threshold probe can never trip, and a non-zero min makes a slot display a
  negative range (slot 7 showed -64..-62 until min was forced to 0).

Slot 6 moves `$c` bits 16-22 and slot 7 moves `$c` bits
8-15 — different fields, so both are independently usable.

> ⚠️ **Do not rely on `$b` for a page-2 knob.** An earlier probe result said
> slot 6's value also appears at `$b`; on hardware, an engine reading a
> page-2 knob from `$b` alone is **dead silent** while the panel demonstrably
> publishes (MODE — `$c` mid — and the `$e` knob both respond). Slot 6 lands
> in `$c`'s **knob field**, as the table says. BusVerb reads SHMR from the
> `$c` knob field OR'd with `$b` (robust to either).

> **All six page-2 slots can be full-range knobs — measured on hardware.**
> The "three knobs plus three companion selects" split reflects how *stock*
> uses the fields; it is not a hardware limit. Five full 0–127 controls, two
> of them in companion fields, have run on the unit at once. (Both shipping
> effects nonetheless give every companion field a small-count select —
> BusVerb WIDTH/RATE, BusDelay MODE/PTCH/FRZE — following an on-unit
> reading that a count-128 companion publishes **near-boolean**;
> `build_bus.py`'s `PAGE2_COUNTS` carries that rationale. That reading and
> the full-range measurement above have not been reconciled against each
> other — re-test before designing a smooth companion knob. `$e`'s knob
> field carries GATE.)
>
> What makes a companion field *look* like a two-state control is the
> **per-parameter display formatter at `P+0x0ca`**, inherited from the donor
> descriptor — DARK's `MIXF` formatter draws a knob as "MIX / SEND" no matter
> what value count it is given. Zero that array (and its partner at `P+0x0fa`)
> and the same field draws as an ordinary knob. See `REVERB.md`.

**Six page-2 controls per effect** — three continuous knobs in
the knob fields of `$b`/`$d`/`$e` (or `$c`), plus three companion fields
(each usable as a select or, per the note above, as a full-range knob):

| control | read it from | decode |
|---|---|---|
| knob A | `x:(r6+$b)` or `$c` | value<<16, use as Q1.23 directly |
| knob B | `x:(r6+$d)` | value<<16 |
| knob C | `x:(r6+$e)` | value<<16 |
| select A | `x:(r6+$c)` | `and #>$00ff00` then `asr #$8` |
| select B | `x:(r6+$d)` | `and #>$7f00` then `asr #$8` (**bits 8–15**) |
| select C | `x:(r6+$e)` | `and #>$7f00` then `asr #$8` (**bits 8–15**) |

⚠️ An earlier version of this table decoded selects B/C from the LOW field
(bits 0–7) — everything that read bits 0–7 had never worked on hardware.
The settled map is bits 8–15 for every companion field
(`PARAM_PAGES.md`), and the shipping code reads them that way.

All four offsets (`$b`, `$c`, `$d`, `$e`) and all six display slots are
reachable. A probe that watches only the knob field concludes that `$c` is
unreachable and that only three page-2 offsets exist -- both artefacts of the
probe, not facts about the hardware (see the bullets above).

`r6+6..$a` is touched by nothing. What lives there is still unknown.

**Symptom if you get this wrong**: the parameters silently read whatever is in
those slots and never change. Page-2 knobs simply do nothing, with no error.

One trap when fixing it in `tools/gen_reverb.py`: the offset is interpolated into
the assembly as text, so `P_RATE = 12` formats as `$12`, which the assembler reads
as **hex 18**. It needs `{P_RATE:x}`. That produces a working build that quietly
reads the wrong slot.

## 10. Per-instance buffers: the host runs a bump allocator

Hardcoding absolute Y addresses works for exactly one
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
   `0x30000` — which is real and measured (the first probe stopped at
   `0x20000` and never reached it).

### Y memory, measured end to end (`dsp/ymemprobe.asm` on hardware; file in git history)

| Y range | what | |
|---|---|---|
| `0x00000–0x00794` | system + loaded modules | internal |
| `0x00795–0x00FFF` | free | internal |
| `0x01000–0x03FFF` | 4 FX1 slots x 3072 | internal |
| `0x04000–0x0BFFF` | 2 FX2 slots x 16384 | internal |
| `0x0C000–0x2FFFF` | **absent** (silence) | — |
| `0x30000–0x3FFFF` | **64K words, 4 more FX2 slots** | **shared window** |
| `0x40000+` | **absent** (freezes) | — |

Swept by TIME as `base = (p0+1) << 12`: sound at 0–10, silence through the
gap, **sound again at 47–62**, freeze at 63. TIME=47 is `0x30000` exactly and
buzzed continuously while 48–62 were clean — worth remembering if anything
odd shows up at the very start of the external region.

The internal 48K is **per-DSP** (both payloads use `0x4000`/`0x8000` and do not
clash, because they are different chips). The 64K window is **shared between
the chips**, which
is why the payloads are given different halves: A takes `0x30000`/`0x34000`,
B takes `0x38000`/`0x3c000`. Every one of the 8 tracks therefore has a full
16,384-word FX2 slot, and an effect that refuses the shared-window slots
silently gives up half the machine.
3. Our 40K layout was about 2.5x an instance's entire allocation.

### The relocatable layout

All buffers become offsets from the base, and all persistent state moves out of
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

Two plausible claims reasoned from the dispatcher listing are both
wrong, with the same failure mode in
each case — a build that is clean in the emulator and unusable on hardware.

**Wrong claim 1: the base can be derived from r7.** X:0x20a and X:0x213 do
advance together, so `n = (r7 - 0x6000) >> 8; base = x:(0x255 + n)` looks sound.
Measured with `dsp/r7probe.asm` (in git history) — 49 words that pass audio only when the TIME
knob equals `r7 >> 8`, so the knob position reads the register directly — r7 is
**0x6200**. The arithmetic was right, but `table[2]` is `0x1c00`, a 3072-word
**FX1** slot. A 16K layout starting there runs to `0x53ff`, through the other FX1
buffers and into FX2 slot 0. FX2 effects do not take even table entries.

**Wrong claim 2: persistent state can live anywhere in the r7 block.** Bisected:

| build | base | state | result |
|---|---|---|---|
| 1 | derived | `r7+$84..$8a` | hangs |
| 2 | hardcoded | `r7+$84..$8a` | hangs → base innocent |
| 3 | hardcoded | absolute Y | runs → state is the fault |

`r7+$71..$78` is fine *within* one call and `r7+$83` persists, but `r7+$84..$8a`
does not. DARK REV's init writes `$1a $1b $1f $82 $83 $84 $8b` and steps around
`$85..$8a` — it was avoiding host-owned words.

**What works**, measured with `dsp/baseprobe.asm` (in git history; same trick, TIME matched
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

Reading it in process hangs the machine — and not because of cycles; it is
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

Read the base and derive all seven buffer addresses in init -- 31
instructions, no loop -- and store them in the r7 block. Process just uses them,
which is also cheaper than recomputing per block.

### One trap worth its own paragraph

A modulo offset larger than the buffer is **undefined** on the DSP56300. Shrinking
the pre-delay to 2048 words while leaving the knob scaled to `v*128` meant PRE=32
asked for 4096 samples through `y:(r5+n5)` under `m5`. It does not wrap and it
does not clamp: the read returns nothing, the tank gets no input, and the reverb
goes **completely silent** — which looks nothing like an addressing bug.

## 11. HARDWARE: the two payloads have DIFFERENT Y module maps

The two DSP program payloads are not two copies of the same layout. Below
Y:0x1000 — the region above the loaded coefficient modules and beneath the FX1
buffers, which is the only absolute scratch an effect can use — they differ:

| payload | Y modules below 0x1000 | highest loaded word | free window |
|---|---|---|---|
| A | 5 | Y:0x0794 | Y:0x0795..0x0FFF |
| B | **21** | **Y:0x07a4** | Y:0x07a5..0x0FFF |

**This is a real failure mode.** An init that carries its buffer base
across to process through a per-instance stash at `Y:(0x735 + (r7 >> 8))` — an
address chosen against payload A's map and verified on payload A — lands, on
payload B,
inside a live 128-word coefficient table at every one of those addresses. The
effect corrupts another algorithm's coefficients, then reads that algorithm's
data back as its own buffer base and writes 14K words from wherever it points.

One instance never shows it, because one instance is one payload.

Anything absolute in Y must sit at **0x800 or above** to be safe in both, and the
usable window is only `0x7a5..0x0FFF` — 2139 words.

### X:0x213 is per-instance during init and NOT during process

The dispatcher advances the allocator pointer per effect, so once blocks are
running it sits wherever the last init left it. Reading it in process gives:

* one effect loaded → still a valid FX2 slot → **works, by luck**
* two effects loaded → both instances read the **same** entry → one of them
  writes 14K words through memory it does not own

Read it in init and carry the value across. This is what the stock reverbs do.

### The allocator's instance model

Each track allocates an FX1 slot and *then* an FX2 slot, so the two pointers step
by two per track from an FX2 effect's point of view. FX2 instance `k` gets table
entry `1 + 2k` and state block `0x6000 + (2 + 2k) * 0x100`:

| | alloc entry | base (A) | base (B) | r7 |
|---|---|---|---|---|
| track 1 FX2 | 1 | 0x04000 | 0x04000 | 0x6200 |
| track 2 FX2 | 3 | 0x08000 | 0x08000 | 0x6400 |
| track 3 FX2 | 5 | 0x30000 | **0x38000** | 0x6600 |
| track 4 FX2 | 7 | 0x34000 | **0x3c000** | 0x6800 |

("Track *n*" here is the *n*-th track of the chip's own bank of four. The
track↔chip mapping is measured: payload A serves tracks 5–8, payload B serves
tracks 1–4.)

That model reproduces both hardware measurements: `dsp/r7probe.asm` returned
0x6200, and `dsp/baseprobe.asm` returned 0x4000 and 0x8000 on two tracks
(both probes in git history).

> **Both payloads are live at once** — two separate DSP chips,
> four tracks each, each with its own on-chip RAM, so `Y:0x4000` on chip A and
> `Y:0x4000` on chip B are different physical memory. (The low two FX2 slots
> being the same Y addresses in both payloads does NOT mean only one payload
> can be live at a time.)
>
> **The machine: 8 tracks, each with one FX1 slot and one FX2 slot.** FX1 is
> 3072 words (~70 ms) — fine for chorus, phaser, comb, EQ, and far too small for
> a reverb or a delay, which is why every stock reverb and the delay are FX2-only.
> FX2 is 16,384 words and can hold them.
>
> Eight tracks therefore need eight FX2 slots, and the memory closes exactly:
>
> | | slots | where |
> |---|---|---|
> | DSP A, 4 tracks | `0x4000` `0x8000` | internal, on-chip |
> | | `0x30000` `0x34000` | shared-window SRAM |
> | DSP B, 4 tracks | `0x4000` `0x8000` | internal, its own on-chip |
> | | `0x38000` `0x3c000` | shared-window SRAM |
>
> Internal memory supplies only four of the eight, so **the shared window is
> not optional — it is required for 8 tracks to have reverb at all.** That is an
> independent confirmation that it is real and that stock uses it, and it is the
> reason the payloads partition it: a shared resource is what gets divided.

Deriving the base as `x:(0x255 + ((r7 - 0x6000) >> 8))` looks sound and is wrong:
r7 = 0x6200 pairs with table[**1**], not table[2]. table[2] is 0x1c00, a
3072-word FX1 slot, and a 16K layout there runs to 0x53ff through the other FX1
buffers and into FX2 slot 0.

### Finding this class of bug without a mount cycle

`tools/dsp_host/dsp_host.cpp -inst N -guard` runs N instances the way the
dispatcher does and shadows Y:0x0000..0xBFFF plus the loaded part of P from
before the first init. It separates a *stray* write (outside the instance's
buffer — the stash is deliberately one of these) from a *clobber* (landing on a
word a loaded module put there, which is never legitimate) and names it:

```
!! CLOBBER inst 0 init wrote Y:0x00737 -- OVER A LOADED MODULE
```

Bisect builds can be broken by their own instrumentation — one put the level
read inside the pre-delay setup so n5
came from the knob, another clobbered x0 between the base derivation and the
state load — invalidating their hardware results. Run the guard first.

## 12. Standing rules for writing DSP code here

Learned by freezing the machine; each of these was established on hardware.

* **`mpy` does NOT double.** Measured: 0.5*0.5 = $200000 exactly. The
  "fractional multiply shifts left" theory is wrong. Coefficients are
  plain fractions.
* **Let the AGU do address work.** Modulo wraps, adds the base and masks
  for free. Doing it by hand cost 135 cycles/sample — 31% of the engine.
  An interpolated read does NOT need two addresses: the read pointer
  advances one per sample, so `d1` this sample is `d0` last sample.
* **`dsp_asm` silently mis-encodes illegal parallel moves.** It emits a
  different instruction rather than erroring. `x:(rN+displacement)` can
  never be parallel; operand order matters (`mpy y0,x0,a` takes a parallel
  move, `mpy x0,y0,a` discards it); XY dual moves need the X pointer in
  R0-R3 and the Y pointer in R4-R7. Verify every one by disassembling.
* **When a register holding a constant is repurposed, grep every read of
  it.** Two real clobbers came from exactly that — one produced
  344 stray writes, the other broke only when PRE was off-centre.
* **A workaround for a disproven theory does not remove itself.** An
  arithmetic-addressing workaround added for a disproven modulo theory
  outlived the theory and eventually cost an instance.
* **Sanity-check a surprising emulator result against the instrument.**
  A harness modelling a special case instead of the dispatcher can invent
  behaviour — a spurious self-oscillation, for instance — that a listening
  test falsifies immediately.

* two instructions between writing r5 and using it — and they must be **data
  moves**, never M-register writes (an M load interlocks with its address
  register; this froze one track)
* no M-register write inside the sample loop
* a modulo offset larger than the buffer is undefined: silent, not an error
* absolute Y scratch must sit at 0x800 or above — payload B loads modules to
  Y:0x7a4 where payload A stops at 0x794 (violating this has hung the unit)
* X:0x213 is only valid during init; reading it in process gives whatever the
  last init left (this too has hung the unit)
* check the generated assembly and the assembler's exit status, not the
  generator. `build_reverb.py | grep` masks a failed assemble and the emulator
  will then happily "verify" a stale image.
