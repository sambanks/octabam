# External findings

Reverse-engineering results **from outside this project**, recorded here so
that what we adopted, what we verified, and what we merely repeated are three
distinguishable things.

**This work is by Bryan T**, shared on Discord. It is his finding, not
octabam's, and is recorded here as such — the status key below marks what we
independently confirmed versus what we adopted on his evidence.

Received 30 Aug 2026: `octatrack-delay-architecture.md`, `TABLE_ATLAS.md`
(a revised version of an earlier atlas), `timestretch.md`. All three are
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

*ChonVerb:* there is no expensive shape to table. Its 1,384 cycles are eight
tank lines, four allpass bodies and two rolled groups — memory reads and MACs,
not function evaluation. Its LFO is a triangle, which is cheap by construction
and already shared across lines by the roll.

*BongDelay:* it does have one expensive shape — the **smoothstep** window
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
