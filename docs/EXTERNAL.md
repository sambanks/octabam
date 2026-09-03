# External findings

Reverse-engineering results **from outside this project**, recorded here so
that what we adopted, what we verified, and what we merely repeated are three
distinguishable things.

**This work is by Bryan T**, shared on Discord. It is his finding, not
octabam's, and is recorded here as such — the status key below marks what we
independently confirmed versus what we adopted on his evidence.

Received 30 Aug 2026: `octatrack-delay-architecture.md`, `TABLE_ATLAS.md`
(a revised version of an earlier atlas), `timestretch.md`; **2 Sep 2026:
`octatrack-recorder-architecture.md`** (§6). All are
careful work: they mark their own claims
`[measured]` / `[inferred]` / `[open]`, state their method, and are explicit
about what would falsify them — the same discipline `CLAUDE.md` asks for here.
Each was derived from the officially distributed OS 1.40C, hash-verified
against stock, and the hash they quote matches our own canonical
`section_3_MAIN_OS.bin`.

**Status key:** ✅ we re-verified it ourselves · 🟡 adopted on Bryan's
evidence, not re-verified · ❌ it retracts something we had written.

---

## 1. The Echo Freeze Delay: solved, and it was never on the DSP

**This closes the project's oldest open question.** We had established a wall
of negatives — no DSP code, no parameter reads, no id-8 gate, no delay-sized
buffer — and concluded correctly that it was not on the DSP, without ever
finding where it *was*.

🟡 **It is on the ColdFire, as per-frame DMA descriptor arithmetic over
per-track circular buffers in SDRAM**, with an EMAC loop for the gain and mix
work. The "algorithm" is mostly address computation: once per frame the CPU
works out where "delay-time ago" lives in each track's ring and points the DMA
engine at it. The audio itself is moved by hardware, which is why no
per-sample delay code exists anywhere the obvious searches looked.

Load-bearing specifics, all marked `[measured]` in Bryan's write-up:

| | |
|---|---|
| frame routine | `0x400031a0` (body to ~`0x40003900`) |
| ring base | SDRAM `0x4F502C10` — outside the `0x46xxxxxx` globals region every address sweep covered |
| ring size | 1,411,200 bytes per track = 176,400 × 8 = 4 s × stereo × 4 bytes |
| the 4-second cap | `if (samples > 176400) samples = 176400`, as a literal |
| read head | `read_pos = write_pos − delay_samples × 8`, wrapping at the ring size |
| DMA | registers `0xfc045040/50/60/70`, count/control at `0xfc04505e/7e` |
| tap processing | EMAC loop at `0x40003664`; two cascaded first-order sections, coefficients per track via `0x80006180` |
| mix and feedback | EMAC loop at `0x40003734`; four gains, each linearly ramped across the frame |

Two structural points worth carrying:

- **There is no fractional-delay interpolation.** The read pointer is whole
  8-byte frames. Time changes are handled by a **two-tap crossfade in time** —
  this frame's and last frame's delay positions, both DMA-fetched, crossfaded
  with a per-sample linear ramp across the 16-sample frame. TAPE off snaps the
  length (an audible buffer discontinuity); TAPE on glides it, so the
  inter-tap crossfade fires continuously and the tape-like repitch is a
  staircase of integer jumps smoothed by frame-rate crossfades.
- **Feedback is not recursive code.** There is no per-sample feedback loop
  anywhere. Regeneration exists only because the ring's write stream contains
  a scaled copy of its own filtered read stream, one frame-trip at a time.

### What it changes for us

Nothing in what we build — our effects are DSP-side and the delay never
competed with them. But it retires a standing mystery, and it explains the
thing that always looked wrong: **eight tracks can sustain full 4-second
delays simultaneously** because each has its own ~1.4 MB ring in CPU SDRAM,
always allocated. That was never a DSP budget question.

❌ It also falsifies a claim of ours by name: *"the ColdFire does no
per-sample audio arithmetic."* That was verified only for the audio ISR at
`0x4000aad0` and does not survive this function.

---

## 2. ❌ The ESAI carries audio — RETRACTED, and re-verified here

`docs/DSP.md` concluded that audio does **not** arrive over the serial audio
interface, reasoning from the interrupt vector table: the ESAI vectors
`0x30`–`0x3e` are all `jmp` to themselves, the unused-vector idiom.

**The vector reading is right and the inference is wrong. A DMA-serviced
peripheral needs no interrupt vectors at all.**

✅ **We confirmed this ourselves** rather than adopting it, in our own
`out/dsp/payload_A.asm`. Both ESAIs are fully configured at boot from
`P:0x30026`:

```
030026: movep #>$40,x:<<M_SAICR
03002c: movep #>$37d01,x:<<M_TCR    ; M_TE0 enabled, M_TMOD=1 (network), M_TSWS=$1f
030036: movep #>$ff,x:<<M_TSMA      ; all 8 transmit slots enabled
030045: movep a,x:<<M_TX0           ; and it transmits
```

with a second port configured identically right after (`M_*_1`). `M_TDC=$7`
is 8 slots — the "8-slot network mode" the external note describes.

**The lesson is the general one this project keeps relearning:** we drew a
strong negative from an instrument that was structurally blind to the thing
being ruled out. And the contradiction was already sitting in our own tree —
`CHIP.md` has labelled that module "host-port loader + **ESAI setup**" the
whole time. Two documents disagreed for weeks and nobody read them together.

---

## 3. Timestretch is a ColdFire feature

🟡 The CPU renders the grains, including the crossfades, and ships finished
audio to the DSP every frame. The per-track block crossing the chip boundary
is **the next frame's audio**, not a parameter program. The DSP's playback
engine is a 2-tap linear interpolator over a 128-word ring: it applies pitch
and nothing else — no gain, no window, no position autonomy.

- The crossfade is a numerically exact **Hann window** on the ColdFire: a
  512-entry table at `0x80004000`, fitted as `T[i] = round(2³¹·sin²(π/2·(i+1)/513))`
  with zero error on all 512 entries, and exactly complementary
  (`T[i] + T[511−i] = 2³¹`). Fixed 512-source-sample (~11.6 ms) fade, minimum
  grain body 2,048 samples (~46 ms) — constants, not tempo- or TSNS-dependent.
- **No pre-analysis, definitively.** The `.ot` serializer persists only 64
  slice records, trim points and a checksum. BEAT mode's "transients" are
  slice markers, not detected onsets; transients stay hard because the read
  head is *re-anchored* at each marker.
- Segments within a frame are butt-spliced on the DSP; overlap-add happens on
  the CPU before the audio ever arrives.

### 🟡 Corrections to our `docs/DSP.md` module labels

Adopted on Bryan's evidence, not re-verified by us, and applied in place:

| module | we called it | it actually is |
|---|---|---|
| `P:0x3a1` | "parameter unpacking" | the **voice playback engine** (2-tap linear interpolator over the 128-word ring) |
| `P:0x2bf` | "MAC/pointer-walk resampler" | the **summing mixdown** |
| `func_00055a` | a 16-iteration gain routine | the **24-bit ↔ dual-16-bit host packer** (fixed power-of-two scaling, no gain) |

None of this disturbs the conclusion those labels were serving — that no
module on either payload is the delay.

---

## 4. Data-table atlas

**The catalogue itself now lives in `docs/TABLES.md`**, merged with what we
re-derived, so a question like "what is at `X:0x08722`?" has an answer in our
own tree rather than in a downloaded file. What follows is the summary and
what it changed.

🟡 A shape-level catalog of every X/Y data module the ColdFire uploads at
boot, from the payload module records with Q23 decode. Deliberately
shape-only: it does not attribute tables to effects except where earlier work
already had.

Points that matter if we ever go looking for a table:

- **Every substantive data module is byte-identical between payloads**, at
  shifted addresses (upper X cluster: B = A − 0x540). The only real
  per-chip differences are four small config/state modules.
- `X:0x04840` is a **32 × 128-entry curve bank**, knob-indexed 0–127 — a
  ready-made source of parameter warps.
- `X:0x06c00` is now fully segmented, including a **single-cycle ramp/saw
  wavetable at `0x7000`** beside the known sine at `0x6c00` — together they
  read as an LFO waveform bank.
- One prior guess is corrected: the curve at `X:0x01bd9` was attributed to
  FRQ1 and is actually **GN1/GN2**; FRQ reads `X:0x015c7` with a ×4 index
  (2 extra bits of resolution, unexplained).

### ✅ Evaluated against our own modules, 31 Aug 2026

The atlas is shape-only, so the question it leaves open is *"is any of this
useful to us?"*. Measured, not guessed:

**The 32 × 128 bank is mostly one-pole COEFFICIENT PAIRS, not knob warps.**
Extracted and characterised all 32: they come in pairs — a near-1.0 falling
curve beside a small rising one — which is the (pole radius, complementary
gain) shape you index by a knob to sweep a one-pole filter. Useful to a future
module that wants a cutoff map with the stock feel; not what we assumed.

**Not worth swapping our existing tapers, and this is a negative result worth
recording so nobody re-runs it.** Fitting every curve (plus reversals and
inversions) against the shapes our modules compute by hand:

| our taper | best stock curve | RMS error | verdict |
|---|---|---|---|
| `k²` (BodeShift FREQ, Ripple FREQ, Rungs FREQ) | 14 | 0.040 | rough — audible difference in feel |
| `(1−k)³` (Streamz FALL) | 12 reversed | 0.040 | rough |
| an exponential we do *not* currently use | 0 | 0.016 | usable, if a module wants that shape |

And the arithmetic goes the wrong way regardless: `k²` is **three
instructions** (`move`, `move`, `mpy`) with no address register, while a table
read costs ~5 *and* an AGU register. Computing wins for cheap shapes. Tables
only pay for shapes that are expensive to compute.

**Which is exactly BodeShift's sine.** ✅ The 1,024-point sine at `X:0x06c00`
is at **the same address in BOTH payloads** (checked — so an insert, which
must live in both, may use it) and is exact to 1.75e-7, i.e. Q23 quantisation.
BodeShift computes its carrier with a refined parabola instead: **21
instructions, twice per sample**, for a max error of 1.09e-3 (≈ −59 dB).

Swapping it for a table lookup with modulo addressing (`m = 1023` makes the
wrap free; r1–r3 are unused in that module) would be **cheaper *and* cleaner** —
roughly 20 of its 344 cycles back, and the oscillator's distortion drops ~76 dB,
below the Hilbert pair's own residual, so the shifter's sideband suppression
would be limited by the pair alone rather than by its oscillator.

🟡 **Not done.** BodeShift is verified as it stands, and this would need the
sideband and shift-accuracy measurements re-run. Logged as a priced option,
not a pending change.

**And nothing for the two servers — checked, both negative.**

*BusVerb:* there is no expensive shape to table. Its 1,384 cycles are eight
tank lines, four allpass bodies and two rolled groups — memory reads and MACs,
not function evaluation. Its LFO is a triangle, which is cheap by construction
and already shared across lines by the roll.

*BusDelay:* it does have one expensive shape — the **smoothstep** window
PITCH and GRAIN evaluate per head per sample — and it should **not** be
tabled, for two independent reasons. No stock table is close: the best
complementarity error among the candidate 128-word curves is 0.24 and the best
shape match is 0.43 RMS, both nowhere near usable. And more importantly, the
engine leans on `s(g) + s(1−g) = 1` holding **exactly** — that is what makes
`g0 + g1 == 1` at every age, which is what bounds the loop gain and lets PITCH
inherit CLEAN's stability. An approximate table would silently trade a proved
stability bound for a handful of cycles. (Bryan's CPU-side crossfade table
*is* exactly complementary, but it lives in CPU shared RAM at `0x80004000`,
not in the DSP-visible X space, so it is not available to us.)

The delay's own 1/√N reciprocal table is rebuilt per block, eight entries —
already negligible.

⚠️ Its own caveats are worth keeping: segment boundaries come from a
discontinuity detector and merge smoothly-joined tables, stride findings are
statistical, and Q23 decode is assumed throughout.

---

## 5. ✅ The EMAC toolchain warning — CHECKED, and we were worse off

🟡 Bryan reports that **`objdump -m m68k:5407` silently mangles every EMAC
region into `.short` garbage**, because the ColdFire here is V4e-class with a
four-accumulator EMAC; `-m m68k:547x` is required.

✅ **Confirmed, and worse than reported — but we already knew, and had
mislaid it.** `docs/midi_re_note.md`, `docs/midi_re_scene.md` and
`docs/MIDI.md` all say plainly that radare2's m68k plugin cannot decode the
ColdFire `mvs`/`mvz`/`mov3q`/`mac` forms and that the MIDI scouts used
`m68k-elf-objdump -m m68k:cfv4e` instead. That was August. The finding stayed
in the MIDI corner: `scripts/disasm.sh` went on driving r2 with no warning,
and this file's first draft asked whether r2 was affected as though it were
an open question. It was not open; it was stranded — the exact failure mode
`CLAUDE.md` collects under stale forks.

Measured on the delay's tap loop at `0x40003664`:

| | first four instructions |
|---|---|
| **`m68k:547x`** | `msacl %d0,%a1,%acc2` · `msacl %d0,%a2,%acc3` · `macl %d2,%a1,%a5@+,%a1,%acc0` · `msacl %d5,%a1,%a0@+,%a1,%acc0` |
| **`m68k:5407`** | `msacl %d0,%a1` · `.short 0xa4c0` · `btst %d4,%a0@` · `macl %d2,%a1,%a5@+,%a1` |
| **radare2 `-a m68k`** | `invalid` · `btst.l d4,(a0)` · `invalid` · `btst.l d4,(a0)` |

Two distinct failures, and the second is the dangerous one:

1. **The EMAC ops are lost.** 5407 drops the accumulator operand (so you
   cannot tell `acc0` from `acc3` — i.e. cannot tell the stereo halves
   apart); r2 loses the instruction entirely.
2. **The stream DESYNCHRONISES and invents plausible code.** Both decoders
   treat the opcode as 2 bytes, so each 2-byte *extension word* is then read
   as its own instruction. `0910` becomes `btst %d4,%a0@` — an ordinary,
   unremarkable-looking instruction that is not in the program at all.
   Nothing announces the error.

**And it is not only the EMAC.** Across the code region below `0x40098000`:
**6,757 instructions r2 cannot decode, 4,543 of them longer than two bytes**
(each desynchronising what follows), over 149 pages. EMAC is a small minority
— the bulk is `mvz` (4,539) and `mvs` (1,834), ordinary ColdFire ISA_B moves
used everywhere. **r2's reading of this firmware is unreliable almost
anywhere, not merely in audio code.**

The EMAC instructions specifically, 791 of them, concentrate in the audio
code:

| region | EMAC ops | what lives there |
|---|---|---|
| `0x40001000` | 48 | the timestretch crossfade mixers |
| `0x40003000` | 62 | the Echo Freeze Delay's tap and mix loops |
| `0x40004000` | 50 | frame builder |
| `0x40007000` | **98** | the trig-handler region — the densest in the image |
| `0x4000c000`–`0x4000d000` | 47 | grain engine / frame staging |

(Counts from a linear disassembly, so hits in the data regions above
`0x40098000` are false positives — data decoded as instructions. The code-region
clusters above are the real ones, and they land on Bryan's landmarks
independently.) Note that `0x40007000` being the densest is itself a small
corroboration of his open thread: that is where he expects the marker-list
writer, and so TSNS's consumer, to be.

**Fix, landed:** `scripts/disasm.sh emac <addr> [bytes]` disassembles a span
with `m68k-elf-objdump -m m68k:cfv4e` — the same flag the MIDI work already
used — and the script now carries the warning at the top, which is where it
should have been in August.

### ✅ What this does NOT overturn — the re-check

Every ColdFire address our docs cite in `0x40000400`–`0x4000dfff` (90 of
them) was re-disassembled with `cfv4e` and compared against r2. **No
conclusion of ours is falsified.** The differences are almost entirely
notation (`movel %a2,%sp@-` vs `move.l a2,-(a7)`). Only four cited addresses
sit on an instruction r2 genuinely cannot read, and none of them breaks a
claim:

| address | r2 | actually | our claim |
|---|---|---|---|
| `0x4000b786` | `invalid` | `mov3ql #-1,%a1@+` | `midi_re_note.md` **already says `mov3q #-1`** — read correctly at the time |
| `0x4000c24a` | `invalid` | `mvsb %a3@(0,%d1:l),%d0` | a sign-extended indexed byte load, consistent with the scene-pair fill claimed there |
| `0x40003664`, `0x40003900` | `invalid` | EMAC / coprocessor | Bryan's addresses, from his disassembly not ours |

Two things carried the load and neither was r2: the menu and descriptor work
was **Ghidra** (`tools/GhidraMenuFuncs.java`, cited in `verify_menu.py` and
`BUS.md`), and the MIDI work was **objdump `cfv4e`**. ✅ Our own tempo-sync
cave hook at `0x40004d40` also re-reads exactly as documented — the three
displaced instructions are `moveb %a0@(3516),%d2 / extw %d2 /
movew %d2,%a2@(56)`, which is what the cave replays, and it is
hardware-confirmed besides.

**The lesson is not "r2 lied to us" — it is that we knew and the knowledge sat
in one document.** Nothing consumed it: not the script that drives r2, not
`DSP.md`, not this file's first draft.

## 6. Track recorders: the control path (received 2 Sep 2026)

`octatrack-recorder-architecture.md` ("Session 1"). Same author, same
discipline, same hash-verified image. **Scope is the recorder's control
path only** — parameters, storage, triggering, and the engine's arm/open
machinery. The audio write path (where samples land in RAM) and the buffer
addresses are explicitly *not* traced; §9 of his document lists them open.

His motivation is the community's "clickless recorder" technique, which
works at some Tempo/RLEN combinations and not others — so the tempo-dependent
length arithmetic is what he went looking for. Ours is different: it is the
first time a **non-FX setup page** has been followed from descriptor to
shared RAM, and it fixes three labels of ours along the way.

### ✅ Re-verified here, 2 Sep 2026

All against our canonical `section_3_MAIN_OS.bin` (SHA-256 `164f3122…af0a84e`,
the hash he quotes), read with Python at file offset `addr − 0x40000400` and
`scripts/disasm.sh emac` (objdump `m68k:547x`):

| his claim | what we read |
|---|---|
| descriptor entry 8 at `E = 0x400d3c74`, labels `INAB INCD RLEN TRIG SRC3 LOOP / FIN FOUT AB QREC QPL CD` | byte-identical |
| defaults `E+0x96` | `1 1 64 1 0 1 0 0 0 255 255 0` |
| min `E+0xa2` (u32 ×12) | `−1` for QREC and QPL only, else 0 |
| count `E+0xd2` (u32 ×12) | `5 5 65 3 11 2 113 113 128 18 18 128` |
| formatter `E+0x11a` | `0x4003b18c` |
| QREC/QPL ladder at `0x400d80e0`, `0xFFFFFFFF` sentinel before it | `1 2 3 4 6 8 12 16 24 32 48 64 96 128 192 256` |
| one-hot class table at `0x400d8120` | `1 2 4 1024 8 2048 16 4096 32 8192 64 16384 128 32768 256 65536 512` |
| tempo chain `0x4000ca94..cabc` and publisher call at `0x4000cac2` | exact: `1814→181c`, `1818→1824`, `d1 = 0x80000000 ÷ [181c] → 1820`; then `pea 0x60 / pea 0x80000c94 / dest 0x80000cf4 + page×96` |
| RLEN conversion at `0x4006e3b2` | exact: `mvsb 0x80000cf4(2,track)`, gate `≤ 63`, `(raw+1) × 63504000`, `remul` by `[0x80001814] << 2`, floor `64` |
| arm caller `0x40005ff0` | exact: `[0x100b14cf] × 6322 + [0x46c82456] + track + 0x8eda2 == 4` gate; `a3 = 0x80000cf4 + 12·track + 96·page`; `L = table[a3@(7)]`; `addl d1,d1`; `macl d1, −[0x80001820]`; `(x+1)>>1` |
| step ladder at `0x400ab63a` | `992250 × L`, 113 entries: `0, 1..32, 34..64 by 2, 68..128 by 4, 136..256 by 8, 272..512 by 16, 544..1024 by 32`, zeros after |

### ✅ Three of his open items, closed from our side

**(a) The `remsl` question is settled: it is a signed divide, quotient kept.**
He flagged that everything in §8 hinges on whether ColdFire's `4c40/1801`
encoding with `Dr == Dq` returns the quotient or the remainder, because
objdump prints it `remsl`. Measured with the assembler rather than the
manual: `m68k-elf-as -mcpu=5475` encodes `divs.l %d2,%d1` — the 32/32→32q
form — as `4c42 1801`, **byte-identical to what objdump labels
`remsl %d2,%d1,%d1`**, and it *rejects* `divs.l %d2,%d3:%d1` because ColdFire
has no 64/32 divide. So `Dr == Dq` *is* `DIVS.L`; objdump's `remsl` is a
disassembler tie-break over a shared opcode, not the ISA. Hence
`[0x80001820] = −2³¹ / tempo24`, a negative Q31 reciprocal, exactly the
"only self-consistent reading" he arrived at — and `DSP.md` §6c had already
read the same word as the sequencer's phase increment from the other
direction (sign corrected there today: it is stored negative, the consumers
`negl` it).

**(b) The units are samples, because we know what the tempo word is.**
`[0x80001814]` is **BPM × 24**, clamped 720..7200 — measured on hardware by
the tempo-sync work (`DSP.md` §6c, R56 on the unit). Put that into his RLEN
conversion:

```
(raw+1) × 63504000 / (4 × 24 × BPM)  =  (raw+1) × 661500 / BPM
661500 / BPM  =  44100 × 60 / (4 × BPM)  =  samples in one 16th-note step
```

**So recorder lengths are in 44.1 kHz samples, RLEN raw+1 is in sequencer
steps, and the 64-unit floor is 64 samples = four 16-sample frames.** The
`992250 = 22.5 × 44100` constant is the same identity at 1/16 of a step:
`992250 / 24 = 41343.75 = 661500 / 16`, so `table[L] / tempo24` is
`L/16` steps in samples.

**(c) The `0x400ab63a` ladder IS the FIN/FOUT series, and the pickup arm
length is FOUT in samples.** The table has 113 entries — the FIN/FOUT value
count — and displayed as `L/16` steps it reads `0, 0.063, 0.125, …, 64`
(`1/16`, `2/16`, … `1024/16`), which is the series he confirmed on the
hardware menu. He had it as "a fade-length-shaped quantity" [inferred]; it
is the exact display ladder. And the arithmetic in `0x40005ff0` nets to
`round(table[FOUT] / tempo24)`: the explicit `addl d1,d1` doubles so that the
trailing `(x+1) >> 1` rounds to nearest. ⚠️ One inference remains inside
that: the EMAC `macl` must be running in *fractional* mode (product `>> 31`)
for the result to land on the display series. It is the only mode that
does, and it is the same left-shift-by-one alignment our own DSP trap about
reading `a0` is made of — but nobody has read `MACSR`. **Why a pickup
machine's arm length comes from the FOUT slot is open**; his display-order =
raw-order check covered TRIG/RLEN/INAB/INCD, not slot 7.

### ✅ "Current pattern" was the current PART — a label error of ours, found while checking

His document says `[0x80000003]` and `0x100b14cf` are the current *part*.
Our `ARCHITECTURE.md`, `EMU.md` and `tools/emu_bringup.py` all called them
the current *pattern*. The writer at `0x40062120..48` settles it:

```
mvzb 0x80000004,%d0            ; index
mulsl #0x8ed8,%d0              ; × 36568
addl  0x46c82456,%d0           ; + bank blob
moveb %a0@(0x8e56 + 1),%d0     ; a byte inside that record
moveb %d0,0x80000003
moveb %d0,0x100b14cf
```

`16 × 0x8ed8 = 0x8ed80` exactly: the sixteen pattern records fill
`blob + 0 .. 0x8ed80`, and the `0x18b2`-stride records that start at
`blob + 0x8ed80` — where the FX ids, machine types and recorder settings all
live — are the four **parts**. So `[0x80000004]` is the current pattern, and
`0x80000003` / `0x100b14cf` hold **the part that pattern is linked to**,
which is what a part is in the manual's model. Corrected in place in all
three files. It changes no result: the emulator writes 0 to both, and pattern
0 links to part 0 in a fresh bank.

The same fix reaches `docs/history/NOTES.md`, where "per-track pattern data
`0x46c82456 + pat×0x18b2 + trk×0xc (+0x8f385)` — sequenced data" is,
by his §4, the recorder **TRIG** byte (`+0x8f382 + 3`, read through his `+2`
base and `@(1)` displacement) indexed by part. Annotated there, not rewritten.

### 🟡 Adopted on his evidence

- **Three storage tiers** for the twelve bytes: persistent in the bank blob
  (`+0x8f382 + part×6322 + track×12`, through `[0x46c82456]`), a live SRAM
  mirror at `0x100a54d0 + …`, and a **published copy in shared RAM** at
  `0x80000cf4 + track×12 + page×96`, refreshed every frame from a staging
  block at `0x80000c94` by the frame builder — `[0x800000e0]` is the same
  page flip our DSP-frame work and his delay routine both key on. The
  staging block's writer is open.
- **`FUN_40005178` is the QREC scheduler.** We had it since the Ghidra pass
  as "writes voice mailboxes" at `0x46c7e9fa` / `0x800018be` / `0x800018de`
  without distinguishing them. His reading gives the three their roles:
  `0x800018be/de` are the *staged, quantised* action (class word + value),
  `0x46c7e9fa` the *immediate* one, and the per-tick comparator at
  `0x4000b308` (class mask `[0x46c7fe94]`) moves the former into the latter
  when its quantise class fires. The frame builder consumes only the
  immediate array. Both descriptions are true; his is the finer one.
- **His "bit semantics open" and our flag labels are the same bits.**
  `ARCHITECTURE.md` §6 records the trig→voice path emitting `0x80` = start
  and `0x10`/`0x8010`/`0xf010` = one-shot/hold/stop/retrig through that
  function; he sees TRIG=ONE post `0x10|x`, ONE2 post `0x80`, other paths OR
  in `0x40`. Neither side has verified the other's labels 🟡.
- **The engine task.** His `0x460d17ce` queue, task loop `0x4008484e` and
  46-entry jump table are inside the task `NOTES.md` calls `FUN_4008445c` —
  the RELOAD BANK consumer (message types `0x14` and `6`). His "central
  engine-command queue, not recorder-private" is therefore corroborated from
  our side: bank reloads and recorder arms go through the same queue.
- **Recorder buffers are object ids 128–135** in one 136-entry state-record
  arena shared with the sample slots (`0x100b14f0 + id×1096`, control records
  `0x46c922c4 + id×44`), armed by opcode `0x25` through the same open/arm
  function as a sample slot. Arm floors the length at 64 and records LOOP
  at state `+292`.
- **The defaults anomaly is real and open**: a fresh part shows TRIG=ONE and
  SRC3=MAIN where the descriptor says ONE2 and "–"; the initialiser copies
  the descriptor verbatim to a *different* structure, and no template with
  the hardware values exists in the image.

### ❌ What it retracts of ours

| where | we said | it is |
|---|---|---|
| `ARCHITECTURE.md` §7, `EMU.md`, `tools/emu_bringup.py` | `0x80000003` / `0x100b14cf` = current pattern | current **part** (✅ measured above) |
| `history/NOTES.md` map | `+0x8f385` = sequenced trig/param data | recorder **TRIG** byte, part-indexed |
| `DSP.md` §6c | `0x400060c4` reads `0x80001820` for "the timestretch/trig position" | the **PICKUP-machine record length**, FOUT ÷ tempo24, in samples (✅ code read above); the sibling `0x40006d48` is not re-read |
| `DSP.md` §6c | `0x80001820 = 2³¹/tempo24` | `−2³¹/tempo24`; consumers negate it |
| `DSP.md` §6c | only two tempo readers outside the sequencer, both UI | a third, `0x4006e3b2`, feeds the recorder; the conclusion (rates, not BPM, reach the DSP) stands |

### What it changes for us

Nothing we build — the recorder is CPU-side machinery around a write path
that is still unlocated. What it hands us is a **mapped publish path for a
setup page** (`0x80000c94` → `0x80000cf4` per frame) and the recorder's
length arithmetic in known units, which is where any "clickless loop" patch
would go. Neither is on the plan.

### Notes back to Bryan

Findings flow back as notes, by agreement. Worth sending, all measured here:

1. `Dr == Dq` is `DIVS.L` (gas encodes `divs.l %d2,%d1` to `4c42 1801`);
   `[0x80001820] = −2³¹/tempo24`.
2. `[0x80001814] = BPM × 24` (hardware-confirmed, clamps 720..7200 = 30..300
   BPM). Lengths are samples; `63504000/96 = 661500 = 44100 × 60/4`.
3. `0x400ab63a` is the FIN/FOUT display ladder (`L/16` steps, 113 entries);
   `0x40005ff0` nets to `round(table[FOUT]/tempo24)` — the `addl` and the
   `(x+1)>>1` cancel.
4. `[0x80000004]` is the current pattern; `0x80000003`/`0x100b14cf` are the
   part it links to, written at `0x40062142..48` from pattern record byte
   `+0x8e57`. Pattern records are `0x8ed8` bytes, parts `0x18b2`, parts start
   at `blob + 0x8ed80`.
5. The trig→voice path's flag words (`0x80` start; `0x10`/`0x8010`/`0xf010`
   one-shot/hold/stop/retrig) — our labels for his open bit semantics.
6. `0x460d17ce`'s consumer also handles RELOAD BANK (types `0x14`, `6`).

## Open threads worth knowing about

Bryan flags these as still open:

- ~~Who writes the staged delay-time word at `0x80005fa0`~~ ✅ **CLOSED here,
  31 Aug 2026**: the delay routine writes it itself, at `0x40003284..88`,
  copying a word from the per-track record at `0x80001a00 + 96*track` — on the
  branch taken when the gate byte is 8 but the second condition fails. Units
  still open. (`PLAN.md` work order §4 has the full decode, including the gate
  byte's own provenance.)
- The gain-to-knob mapping in the delay's EMAC block (FB, VOL, DIR, X);
  needs hand-decoding of EMAC extension words that objdump mangles.
- Whether the second DSP's tracks (5–8) share the delay function or a twin.
- The marker-list writer that BEAT snapping reads, and with it what TSNS
  actually parameterizes (inferred to select snap candidates).

From the recorder session (2 Sep), still open on both sides:

- **The audio write path and the recorder buffer addresses** — nothing in
  the session touched the code that moves samples into the buffers. His
  expectation is a frame-rate DMA sibling of `0x400031a0`; the state-record
  length fields (`+300/304/308`) and the pointer at control `+20` are the
  likely route.
- The TRIG=ONE / SRC3=MAIN default fixup that the descriptor does not carry.
- SRC3 routing, the AB/CD gain application point, FIN/FOUT fade generation,
  QPL playback machinery (state `+297`), the ONE2 two-phase behaviour, and
  why the pickup arm reads the FOUT slot.
- The remaining 45 engine opcodes (we know two more than he lists: `0x14`
  and `6` are RELOAD BANK); the other nine arm callers; who sets the
  per-tick class mask `[0x46c7fe94]`.
