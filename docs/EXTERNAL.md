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

⚠️ Its own caveats are worth keeping: segment boundaries come from a
discontinuity detector and merge smoothly-joined tables, stride findings are
statistical, and Q23 decode is assumed throughout.

---

## 5. A toolchain warning we should heed

🟡 Bryan reports that **`objdump -m m68k:5407` silently mangles
every EMAC region into `.short` garbage**, because the ColdFire here is
V4e-class with a four-accumulator EMAC; `-m m68k:547x` is required. Any prior
ColdFire disassembly is correct for ordinary ISA code and **blind in
MAC-heavy regions** — which is exactly where audio arithmetic lives.

We do not use that flag: `scripts/disasm.sh` drives radare2 with `-a m68k`,
and our cave assembly uses `m68k-elf-as -mcpu=5407` (assembling, not
disassembling, and our caves contain no EMAC). 🟡 **But it is not established
that radare2's plain `m68k` decodes EMAC any better**, so treat our ColdFire
disassembly as potentially blind in MAC regions until someone checks. That is
a live caveat for anyone hunting audio arithmetic on the CPU side.

---

## Open threads worth knowing about

Bryan flags these as still open:

- Who writes the staged delay-time word at `0x80005fa0`, and its units — the
  missing TIME → staging link.
- The gain-to-knob mapping in the delay's EMAC block (FB, VOL, DIR, X);
  needs hand-decoding of EMAC extension words that objdump mangles.
- Whether the second DSP's tracks (5–8) share the delay function or a twin.
- The marker-list writer that BEAT snapping reads, and with it what TSNS
  actually parameterizes (inferred to select snap candidates).
