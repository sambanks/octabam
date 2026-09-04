# BusVerb — the custom reverb

An eight-line FDN reverb (an earlier four-line engine's source is deleted —
recover it with `git show c1ce08d:dsp/reverb_server.asm`, in git history). It
ships as **BusVerb**, one of the three effects
on the shared send bus (`BUS.md`), running on the FX2 slot of any track in a
bank. Built by `tools/build_bus.py`; source `modules/busverb/reverb_server.asm`.

> ⚠️ **Reading this file:** sections below describing the four-line tank, the
> six-tap early-reflection section, the HALL mode, or the 2048-word static
> in-loop allpasses describe the **deleted engine**. The shipping engine is
> eight lines, 8×8 FWHT, **three** modes (ROOM/PLATE/BIG), ER removed in
> favour of a short Dattorro-scale input diffuser (taps 179/293/419/547 =
> 4.1–12.4 ms), and 512-word **modulated** in-loop allpasses — and it is a
> **RETURN with a unity dry passthrough** (v5, 23 Aug 2026): the output is
> the host track's own dry untouched plus the wet, and p5 is **IN** (this
> track's own send into its reverb), not a MIX crossfade. (v4, R29–R41,
> printed the wet alone and a host track with audio was silent at IN=0.) The signal path and parameter
> table here are current; deeper sections are corrected where marked,
> historical otherwise — in particular, anything describing MIX describes
> the retired insert-era law.

> **The old standalone DARK REV replacement is retired.** Earlier builds
> (`dsp/reverb88.asm` via `tools/build_reverb.py`) replaced stock DARK REV in
> place, inheriting its descriptor and knob labels. That is no longer the
> product and is not being maintained — BusVerb has its own cloned descriptor,
> its own id, and its own knob layout. Where this document still describes the
> old build, it is history; the sections below marked **current** are not.

> ✅ **On hardware, confirmed by ear:** structure, parameters and the MODE
> select all work on the unit; the tail crackle is fixed; the modes are
> genuinely distinct (RT60 2.7 / 4.7 / 7.7 / 10.0 s across ROOM→BIG on the
> four-mode engine of the time, plus per-mode ER arrivals, diffuser taps, tap
> spread, LFO rate and damping); and the then-MIX held dry at unity to
> half-travel before crossfading (MIX has since become IN — see the banner
> above).
>
> Per-mode voicing is not the blocking work. What remains is measured but
> unacted-on: modal prominence 8–11 dB over the local envelope, whose only
> structural lever is more total delay against a 32K hard ceiling — see
> `VOICING.md` for why no fix is worth making at this budget.

For how the DSP subsystem works — boot, payload format, the dispatcher ABI,
the allocator, the memory map — see `DSP.md`. For the bus itself see `BUS.md`.
For the reverse-engineering that got us here, `REVERB_LOG.md` (historical).

---

## Signal path

```
bus Σ + IN ─► 4 series allpasses ─► ┌─ FDN tank ──────────┐ ─► width ─► wet out
              (input diffusion,     │ 8 lines, modulated  │    (RETURN —
               4–13 ms Dattorro)    │ 8x8 FWHT            │     no dry path)
                                    │ HI damping          │
                                    │ LO cut              │  all inside the
                                    │ 2 in-loop allpasses │  feedback loop
                                    └─────────────────────┘
```

(The pre-delay stage that used to open this chain is retired with the PRE
knob; its buffer is still mapped but never read.)

* **Pre-delay** — up to 4096 samples (93 ms), modulo buffer on r6.
* **Diffusers** — four series allpasses, taps 179/293/419/547 (4.1–12.4 ms,
  Dattorro-scale; the original 1994/1706/1438/1226 dispersed rather than
  diffused and were replaced when the ER section was removed, the short
  diffusers taking over its role). Coefficient per mode via `$3f`.
* **Tank** — eight delay lines with an 8×8 Walsh-Hadamard feedback matrix
  (24 butterflies, decay constants scaled 2/√8). All eight reads are
  **interpolated and LFO-modulated**, each line free-running on its own LFO
  rate, the multipliers prime-relative so the periods never align. Per-line
  state lives in a Y table at `base+0x7F00` (table A) and `base+0x7F30`
  (table B: input weights and per-line decay gains).
* **In the loop** — a one-pole low-pass (HI) and a one-pole high-pass (LO)
  per line, so the decay is shaped per band rather than the output EQ'd.
  ⚠️ One shared damping coefficient per pass.
* **In-loop allpasses** — two, **512 words each, LFO-modulated** (fixed
  depth, never zero — a static tank rings), on lines 0 and 1. An allpass in
  the feedback path multiplies echo density on every circulation. The
  proportion matters: too long relative to the line and it becomes a
  dispersive element, which is what a spring reverb is — the reason both the
  original 2048-word versions and the long input diffusers were cut.
* **Early reflections** — **removed.** The six discrete taps were a flutter
  echo (`VOICING.md`); the short input diffuser fills the early-energy role.
* **Out** — L/R tap sums taken **before** the FWHT (a Hadamard row applied
  after the transform collapses to a single line), sign patterns `+−+−+−+−`
  and `++−−++−−`; then mid/side width, then a dry/wet crossfade.

## Parameters (current)

All twelve are live — six on page 1, six on page 2 — and the page-2 mapping
was **measured**, not inferred (`DSP.md` §9). Hardware-confirmed.

| page | slot | label | reads | what it does |
|---|---|---|---|---|
| 1 | 0 | TIME | `r6+$0` | feedback → RT60 |
| 1 | 1 | MOD | `r6+$1` | modulation depth |
| 1 | 2 | SIZE | `r6+$2` | scales all four tap lengths, within the current MODE |
| 1 | 3 | HP | `r6+$3` | **LO** — high-pass inside the feedback path |
| 1 | 4 | LP | `r6+$4` | **HI** — high-cut damping inside the feedback path |
| 1 | 5 | IN | `r6+$5` | **this track's own send** into the reverb (default 0). The host's dry always passes at unity (v5); IN adds it into the engine on top, **and scales the wet's output makeup ×(1+IN)** (v7 — +6 dB at full, exactly ×1 at 0). IN>0 also registers the host as a bus client, so a non-zero default would dilute real senders |
| 2 | 6 | MODE | `$c` bits 16-23 | **stepped select**: 0 ROOM, 1 PLATE, 2 BIG. Slot 6 since v7 (4 Sep 2026; slot 7 / bits 8-15 before): an EVEN slot is one the panel's page-2 knob editor can write, so a main-menu screen can set MODE through the firmware's own routine (`docs/MAINMENU.md` §9c-ii) |
| 2 | 7 | SHMR | `$c` bits 8-15 | shimmer amount, 0 = off (slot 6 / the knob field until v7). A 128-count knob in a companion field — stock does this (FILTER DIST on 11, CHORUS FBLP on 9) and DSP.md records two full-range companion knobs measured on the unit; the 10 Aug "near-boolean" reading predates the field-map and formatter fixes. ⬜ First flash: sweep SHMR and confirm it is smooth |
| 2 | 8 | DIFF | `r6+$d` knob | allpass coefficient, ~0.38–0.80 |
| 2 | 9 | SHFT | `r6+$d` low | **4-step select** (v7, 23 Aug 2026 — was WIDTH, retired; width is pinned wide): the shimmer interval, **+12 / +19 / +7 / −12**, default +12 = the R18 voicing bit-exactly. Companion fields read near-boolean at count 128 on hardware, so a small count publishes |
| 2 | 10 | GATE | `r6+$e` knob | **gated reverb** (Phil-Collins slam). 0 = off; up = hold time (~46 ms–780 ms) before the wet slams shut. Envelope keyed on the tank input ($1b, so sends trigger it), fast attack + ~20 ms eased release, applied as a per-sample multiply on the wet L/R. Replaced PRE (pre-delay was buffer-capped at 93 ms, not worth a knob) |
| 2 | 11 | RATE | `r6+$e` low | **4-step select** for the tank-mod LFO speed: 0.5×/1×/2×/4× of the pinned base rate — companion field, same reason as WIDTH. (This slot previously carried a `→DEL` send select, retired because a return reverb's dry is normally silence) |

**Page-2 fields: three knob fields + three companion fields, any count on
either** (retracted 4 Sep 2026: "three smooth knobs + three selects" was our
convention, not the panel's — stock CHORUS TAPS is a select on slot 6 and
FILTER DIST a smooth knob on slot 11). Since v7 the knob fields carry MODE
(`$c`), DIFF (`$d`) and GATE (`$e`); the companion fields carry SHMR (`$c`),
SHFT (`$d`) and RATE (`$e`). The old "a smooth knob in a companion field
reads near-boolean" reading (10 Aug 2026) came from before the bits-8–15
field map and the formatter fix-up; DSP.md's later measurement of two
full-range companion knobs on the unit contradicts it, and SHMR on slot 7 is
the re-test.

**Page-2 slots pair up**: a knob arrives as `value<<16` occupying bits 16-22,
leaving the low bits of the same word as an independent field. Even slot =
knob field, odd slot = companion field of the same word. Both can carry a
full 0–127 value; mask the companion with `#>$7f` and shift it up by 16.

**The `$e` knob field carries GATE.** PRE, which used to live on `$e`, was
retired (buffer-capped at 93 ms, not worth a knob) and its slot became GATE.
Stock DARK reads *its* pre-delay from `$c`, which is why older builds drove
`$c`; do not "fix" that back.

### Making a cloned descriptor draw correctly

This was expensive to establish on hardware, so it is written out in full.
Four per-parameter arrays matter, each 12 × u32, `P`-relative:

| offset | what it is |
|---|---|
| `P+0x9a` | **value count** — the parameter's range, drawn on a fixed 0–127 scale. A count of 16 gives 16 values over ⅛ of the knob's travel, *not* 16 nicely-spaced steps. |
| `P+0x0ca` | **display formatter**, a function pointer. `0` = plain numeric knob. |
| `P+0x0fa` | **formatter's partner**, also a function pointer. Both must be set for stepped rendering. |
| `P+0x12a` | **must be `0` for a stepped control.** Surveyed all 20 stepped params in stock FX2: 20 of 20 have it zero. |

**A clone inherits all four from its donor**, and the donor's values are for a
different algorithm. That is what made an early `→DEL` send select render as
DARK's "MIX / SEND" however large a count it was given, and what kept MODE
drawing as a plain knob. Zero `0x0ca`/`0x0fa` for every renamed slot; for a stepped control,
set both to a stock pair *and* zero `0x12a`.

Working stepped pairs, for reference:

| source | count | `0x0ca` | `0x0fa` |
|---|---|---|---|
| CHORUS.TAPS | 5 | `0x4003c718` | `0x40047254` | ← MODE uses this |
| SPATIALIZER.PHSE | 4 | `0x4003bbc0` | `0x400467a4` |
| FILTER.Q | 4 | `0x4003bc60` | `0x40046c28` |

There is **no value-name table** in the descriptor: names like FILTER Q's
`none|HP|LP|BOTH` come from the renderer function itself, so a cloned selector
shows numbers. Giving MODE FILTER.Q's pair would draw *those* words, which
would be worse than numbers.

**`DEFAULTS` must be in range.** A default outside its own value count is used
as an index and stalled the sequencer on hardware. Every enabled slot needs an
explicit default — an unlisted one silently keeps the donor's.
`tools/verify_menu.py` now enforces this.

## Memory layout

**Current layout (✅ measured; map from `modules/busverb/reverb_server.asm`'s
header):** the private allocation at the hardcoded
base `Y:0x4000` (32,768 words, `0x4000–0xBFFF`) now carries tank lines only;
every other buffer moved to the shared window, giving **65,536 words (1.49 s)
per server** in total:

| location | size | what |
|---|---|---|
| `base+0x0000..0x7fff` | 8 × 4096 | tank lines, taps to ~3914 (89 ms) at SIZE max |
| `shared+0x2000..0x3fff` | 4 × 2048 | input allpasses, taps 179/293/419/547 |
| `shared+0x1000..0x1fff` | 4096 | former pre-delay (93 ms) — PRE retired, buffer no longer read |
| `shared+0x0800..` | 2048 | shimmer line (excised by `NOSHIM=1`) |
| `shared+0x4000` / `0x4200` | 2 × 512 | in-loop allpasses, modulated, taps 298/446 |
| `shared+0x4500..` | 13 words/line | tank state tables A and B (see below) |

❌ Old layout (32K-era, four-line engine — historical; does not describe the
shipping build):

| offset | size | what |
|---|---|---|
| `base+0x0000` | 4 × 4096 | tank lines, taps 3958/3386/2894/2474 scaled by SIZE |
| `base+0x4000` | 4 × 2048 | input allpasses, taps 1994/1706/1438/1226 |
| `base+0x6000` | 4096 | pre-delay |
| `base+0x7000` | 2 × 2048 | in-loop allpasses, taps 298/446 |

**Persistent state is split** (the four-line engine kept it all in the r7
block; the shipping engine does not).
The r7 block is per-instance and was **completely full** until 18 Aug 2026;
`$68`/`$69`/`$6a` were freed by the →DEL retirement and `$71` by the v4 MIX
removal, so there are ordinary free slots again — do not reach for the
risky parking pattern before checking. Historically: (`$00..$83` all taken;
`$84+` hangs the unit) — `$82` is the warm-up counter (tagged
`$2c0000 | count`), `$83` the tank phase. Per-line tank state lives in the
**Y state tables A and B at `shared+0x4500`** (13 words per line), because the
rolled tank loops need state they can index, which a fixed r7 displacement can
never be.

## The 32K re-layout (historical — replaced by the 8-line layout above)

The layout above used only 16,384 of the 32,768 words `BUS.md` allocates —
half the allocation sat unused. `DSP.md` §7c's high-X region was probed and is
not real, so 32K is the hard ceiling, and taking it was the whole remaining
memory gain. Every buffer doubled:

| offset | size | what | what changed |
|---|---|---|---|
| `base+0x0000` | 4 × 4096 | tank lines | modulo `$7ff` → `$fff`; line spacing `$800` → `$1000` |
| `base+0x4000` | 4 × 2048 | input allpasses | bases `$4000`/`$4800`/`$5000`/`$5800`; `m5` `$3ff` → `$7ff`; every `n5` doubled to `2048 - 2*tap` |
| `base+0x6000` | 4096 | pre-delay | `m6` `$7ff` → `$fff`; PRE scale `v*16` → `v*32` (0–93 ms), i.e. `asr #$c` → `asr #$b` |
| `base+0x7000` | 2 × 2048 | in-loop allpasses | base `$3800` → `$7000`, spacing `$400` → `$800` |

**The tank tap constants did not change.** They are stored as fractions of the
line length (`$3DD800` = 1979 × 2048), so the same word yields 3958 against a
4096-word line — but only because the shift that turns the product back into
an integer tap moved with it: **`asr #$b` → `asr #$a`** on all four taps, and
`2048 - tap` → `4096 - tap`. The constants are untouched; the scaling around
them is not.

**The in-loop allpass taps DID double, 149/223 → 298/446**, and their `n5`
had to be recomputed for the bigger buffer either way.
What matters there is a *proportion* — ~15% of the line the allpass feeds,
above which it disperses instead of diffusing — so holding 9.7%/14.5% against
a line that is now twice as long means doubling the tap. Leaving them at
149/223 would have halved the proportion to 4.8%/7.3%, a character change the
re-layout is specifically meant not to make.

Also done: the warm-up clear covers the whole allocation (`asl #$6` → `asl
#$7`, `do #64` → `do #128`, keeping 256 blocks × 128 = 32,768), and the
saved-phase mask (`$7ff`, guarding the two-track freeze) → `$fff` in all three
places it appears — the load, the pre-delay pointer derivation, and the save.
The in-loop allpass phase mask went `$3ff` → `$7ff` to match `m5`.

**Care was needed and still is:** `$7ff`, `$800` and `$1000` each appear in
*several unrelated roles* in `reverb_server.asm` — line modulo, pre-delay
modulo, line spacing, phase mask, allpass modulo. Blind search-and-replace
would silently corrupt it. Each was changed by role.

### What the emulator says

All runs `guard clean`, `0 CLOBBERING a loaded module`, no hang, at
`-guard 32768`, including two instances with poisoned `-r7 2,5`,
`-dirty 0xBEEF` and `-split 5`.

* **The tail lengthens, as intended.** Impulse at TIME=64, SIZE=127, MOD=40:
  RT60 **5.4 s → 8.7 s** on the same knob setting, because the loop time
  doubled and decay is `g^n` in *passes*, not seconds.
* **It stays stable.** Decay is monotone across the whole sweep; at TIME=127
  (the near-infinite setting) the new build sits at −20 dB after 8 s, the same
  as the old one and not growing, and no output sample exceeds the dry input.
  Swept SIZE 0/32/64/96/127 × MOD 0/127: every combination guard-clean, no
  silence, no runaway.
* **PRE doubled exactly.** Knob 0 → 127 moves the wet onset by 2032 samples on
  the old build and **4064** on the new one, and max PRE is not silent — which
  is the failure mode if the modulo offset ever exceeds the buffer.
* **The bus plumbing of the time was untouched.** The then-present `→DELAY`
  dry send still landed on `BUS.md`'s exact hand-derivable value (`0x0c8000`
  = dry 0.125 × level 0.78125 × `0x800000`), bit-identical between the old
  and new builds. (The reverb no longer writes any bus; the send was later
  retired.)

Code size is unchanged — 1269/2130 words of the SPRING+DARK budget, same as
before, since every change was a constant or a shift count.

### And by ear

A/B'd through `tools/render_reverb.py` on a real pitched synth loop — same
source, same knobs, wet only, old build against new. **The old 16K build is
audibly worse**: what it does to a sustained tonal source reads as
distortion. The new one is clearly cleaner on the same material.

Measured on that A/B, the new tail is **3× flatter** (spectral flatness
0.00003 vs 0.00001). Note these are far below the 0.0014–0.0066 this document
records elsewhere, because those came from impulse tests and a pitched loop
concentrates energy in its harmonics — only the *ratio* between two builds on
the same source means anything.

Neither render clipped (peak 0.36 FS, nothing at the rail), so the roughness
on the old build is mode sparseness, not saturation. The separate saturation
problem is recorded under "Tuning" below (since fixed).

## Register map inside the sample loop

Every address register is committed; this is the constraint any change works
against.

> 🟡 **Pre-roll register map, kept as history** — this is the four-line
> engine's assignment. The 8-line rolled tank walks the Y state table at
> `shared+0x4500` instead of holding line pointers in r1–r4.

| reg | use | modulo |
|---|---|---|
| r0 / n0 | audio buffer, stereo stride | linear |
| r1–r4 / n1–n4 | tank line pointers; nK = read offset | m1–m4 = `$fff` |
| r5 / n5 | allpass pointer; n5 = 2048−tap, rewritten per allpass | m5 = `$7ff` |
| r6 / n6 | pre-delay pointer and offset | m6 = `$fff` |
| r7 | state block | — |
| n7 | frame count, from the dispatcher | — |

## Build, verify, flash

BusVerb ships through the bus build, not the retired `build_reverb.py` path:

```sh
python3 tools/build_bus.py                          # -> out/mainos_bus.bin
```

The container/flash steps below are the old standalone recipe, kept for the
shape of the commands; substitute `out/mainos_bus.bin`.

```sh
python3 tools/build_reverb.py dsp/reverb88.asm      # RETIRED path
EFT_EMIT_CONTAINER=out/elek_v88.bin \
  vendor/elektron-firmware-tool/elektron-firmware-tool \
  -i downloads/extracted/OCTATRACK_OS1.40C.syx -c 3 out/mainos_reverb.bin \
  -V MAXOLYDIAN -o out/OCTATRACK_OS1.40C_V88.syx
python3 tools/make_bin.py out/elek_v88.bin -o out/OCTATRACK_V88.bin
```

Then copy the `.bin` to the **root** of the CF card (one only), and on the
device: PROJECT → OS UPGRADE → YES.

Before flashing, always run the emulator check — two instances, poisoned
state words, dirty memory, and a nonzero split. `tools/dsp_modmap.py`'s
`dumpmem` takes the image bytes as an argument, so the payload can be dumped
straight out of the bus build:

```sh
python3 -c "import sys,pathlib; sys.path.insert(0,'tools'); import dsp_modmap; \
  dsp_modmap.dumpmem(pathlib.Path('out/mainos_bus.bin').read_bytes(), \
                     ['A','out/dsp/mem_reverb_server_A.mem'])"

dsp_host -mem out/dsp/mem_reverb_server_A.mem -init 1252 -proc 1253 \
         -inst 2 -r7 2,5 -guard 32768 -dirty 0xBEEF -split 5 -blocks 900
```

`-guard 32768`, not 16384 — the server owns the whole 32K since the
re-layout. It must report **guard clean** and no hang.

## Voicing without flashing

**Judge the sound in the emulator; spend flashes on what it cannot test.**
`tools/dsp_host` runs the real assembled instruction stream with exact
DSP56300 arithmetic — which this document already relies on ("for a pure
optimization the output should be bit-identical") — at about **6× real
time**. `tools/render_reverb.py` wraps it:

```sh
python3 tools/render_reverb.py loop.wav                      # wet+dry
python3 tools/render_reverb.py loop.wav -p TIME=100 -p SIZE=127 -p MIX=80
python3 tools/render_reverb.py loop.wav --sweep SIZE=0,64,127 --wet
python3 tools/render_reverb.py loop.wav --build              # rebuild first
```

Knobs are named, not indexed, because `-params` is *not* a linear map onto
`r6` — indices 0–5 are page 1, then the page-2 slots interleave: 6/8/10 are the
KNOB fields of `r6+$c`/`$d`/`$e` and 7/9/11 are their companion fields
(bits 8–15). ❌ The old "6–9 land on `$b..$e`" reading is wrong and was
expensive: `$b` is not a page-2 word at all, which is why the delay's WOW
worked locally and never on hardware, and why `-p GATE=n` silently drove
WIDTH's companion instead of the gate. It handles the
256-call warm-up by padding and trimming, and `--wet` recovers the wet signal
exactly by subtracting the dry path. `--wet -p MIX=0` renders **digital
silence**, which is the standing self-check: it confirms both the dry
subtraction and the sample alignment in one run.

Do **not** shortcut this by rendering one impulse response and convolving it
against material offline — the tank is modulated, so it is time-varying and
an IR does not capture it. Feed the real audio through.

**What still needs hardware**, and cannot be faked here:

* **The cycle budget.** This harness will happily render an engine that
  cannot run: 432 cycles/sample froze the chip once already. Anything that
  adds cost needs one flash to confirm eight tracks still play.
* **Everything ColdFire-side** — menu, descriptors, knob labels, parameter
  ranges. `-params` pokes `r6` directly and bypasses all of it.
* **Payload B**, which `dsp_host` cannot boot at all (`BUS.md`).
* **Multi-instance under a nonzero split**, where there is a known
  unexplained one-vs-two-instance divergence. For a pure optimization, also
diff the output against the previous build: it should be **bit-identical**,
and any difference is a bug. See `DSP.md` §6b for the harness reference and
its traps.

## The cycle budget — measured, and much larger than assumed

**There is one BusVerb per bank**, enforced by the server-role lock in
`BUS.md` — a bank's four FX2 slots hold one reverb, one delay and two sends,
not four reverbs. The engine was originally shaped around fitting four reverb
instances on one chip — that is what forced the density pass
(432 → 297 cycles/sample) and what made every feature look unaffordable; the
bus design retired that constraint.

Counted by `tools/cycle_count.py`, which assembles each server, injects a label
after its `do n7,>END` sample loop and takes the word span. **Run it after any
change to a sample loop** — hand counts here have been wrong more than once,
in different ways.

> ❌ **Old accounting — the whole table describes the four-line engine.** The
> ~1080 "budget per DSP" is wrong; the measured budget is 4,535 cycles/core,
> with 819/sample of room for new work. See `CHIP.md` for the live numbers.
> Table kept as history.

| | instructions | cycles/sample |
|---|---|---|
| `reverb_server` | 470 | 660 |
| `delay_server` | 107 | 163 |
| `send_client` | 16 | 18 |
| **a full bank** (1 + 1 + 2 sends) | | **859** |
| budget per DSP (`stageprobe5/6`) | | ~1080 |
| **headroom** | | **~221** (80% used) |

(A later pass took the reverb 731 -> 660 and the bank 930 -> 859: the early-reflection
block was building all six tap addresses by hand -- subtract, `and #>$fff` to
wrap, clean A2, add the base, load r5 -- when **r6 already indexes the
pre-delay buffer under `m6 = $fff`**, which is the addressing the pre-delay's
own read two lines above uses. **This is exactly the pattern the density pass
removed everywhere else, worth 135 cycles there (`DSP.md`); the ER block was
written afterwards and repeated it.** Storing `(4096 - tap)` instead of `tap`
drops the constant straight into `n6`. 254 -> ~181 cycles, **bit-identical
across all four modes and a max-feedback wet render.** The one cost: the ER taps
borrow `n6`, so the pre-delay reloads it each sample -- 2 words against 71.

735 for the reverb / 934 a bank before the Hadamard rewrite below. Note
that rewrite moved the instruction count the *other* way — 508 → 512 — while
cycles fell 735 → 731. **Instructions are not cycles here**, and a count of
them would have scored a real speed-up as a regression.)

**The earlier 529/551 figures were wrong, and the correction has two
independent halves.**

*The engine really did grow*: 367 → 508 instructions across the per-mode
voicing work on `reverb_server.asm`. Six per-mode levers are not free.

*And the old model under-costed the code.* It charged two cycles only for `#>`
long immediates and missed that **`x:(rn+$disp)` is also a two-word, two-cycle
instruction** — which is how every access to the r7 state block is written.
`delay_server.asm` is the control that proves this: it has **not been touched
since that count** (`git log ea1800d..HEAD` is empty for it), its instruction
count is 107 both times, and yet it costs 163 cycles rather than the 112
recorded. The old pass found 5 two-word instructions in it where there are 56.

Cross-checked three ways before being believed: the assembler's own symbol
span, an independent disassembly of the same bytes (`dsp56kDisassemble`, which
prints each instruction's word count), and a source-line count — 508
instructions and 735 words agree exactly across all three.

**Treat 934 as a floor, not a ceiling.** The count is exact for the code but
models no memory-contention stalls, so the figure under load can only be
higher. The old headroom claim — "1.4× the entire reverb engine, free" — is
gone: at 86% of budget (❌ old-budget accounting — the ~1080 figure;
see `CHIP.md`) with two effects and two sends live, a bank is much
closer to its limit than anything in these docs has assumed, and adding
delay lines on the strength of the old number would have overrun it.

**The one large lever, measured but not taken.** 208 of the reverb loop's 735
cycles are long-displacement accesses to the r7 state block, spread over 75
distinct offsets; every register-indirect form (`(rn)`, `(rn)+`, `(rn+n)`) is
one word instead of two. Meanwhile **r0–r4 and r6 are nearly idle inside the
loop** — 3 to 7 references each, against r7's 208. Pointing spare registers at
hot clusters of the state block would convert two-word accesses into one-word
ones.

The arithmetic ceiling is 133 cycles (208 accesses − 75 one-off setups). **That
ceiling is not reachable, and the best cluster has now been converted to find
out by how much.**

**Done: the 4×4 Hadamard, `$16..$1d`.** The most favourable cluster in the
loop — 13 accesses over 9 contiguous offsets, the only run of that quality.
d0..d3 and u0..u3 are adjacent, so one `lua` pointer reads the four inputs and
walks straight into the four outputs, and copying the operand to B removes the
two reloads (A takes the sum, B the difference). **24 words → 16.**

**But the saving is 4, not 8, and `m6` is why.** It holds `$fff` for the
pre-delay's modulo-4096, and the AGU applies the modifier to post-increments.
An eight-word walk is therefore only safe if `(r7+$16) & $fff <= $ff7` — a
property of the *host-assigned* `r7`, not of this code, and not verifiable from
the emulator, whose base is one sample of one. Forcing `m6` linear and putting
it back costs 4 words, halving the win. **Every further cluster pays this same
tax** unless it can live inside a register whose modifier is already linear.

Verified bit-identical across all four modes and a `TIME=127 SIZE=127 DIFF=127`
wet render. Bank total **934 → 930** (❌ old-budget accounting — see
`CHIP.md`).

**Extrapolate down, not up.** This was the best case in the loop and it
returned 4 cycles. 31 of the 75 offsets are touched exactly once and can never
repay a pointer setup; most of the rest are not adjacent enough to walk; and
only five or six registers are spare. The realistic total for the whole lever
is a few tens of cycles, not 133 — worth having if cycles ever get tight,
**not worth spending a flash to chase now**.

**Trap: this assembler silently encodes
`tfr a,b` as `rnd b`** (opcode `200019`, confirmed by disassembling the output).
No error, no warning. B never receives A, the FDN matrix stops being orthogonal,
and the symptom is not a crash but a **40% shift in RT60** — the sort of thing
that reads as "voicing changed" rather than "code is wrong". Use `move a,b`;
`tfr y1,a` and `tfr y1,b` do encode correctly. No shipped source used `tfr`
before this, so nothing else is affected. **Disassemble what you assembled
before trusting a hand-written optimisation** — `dsp56kDisassemble` prints each
instruction with its word count and would have caught this in seconds.

**And the control that made the result trustworthy**: inserting a single `nop`
in the loop and demanding a bit-identical render. That proves the harness is
sensitive to code changes only through *behaviour*, not through layout or
timing — without it, "bit-identical" would have been an untested claim about
the test rather than about the change.

**Do not measure this in `tools/dsp_host`.** Its `instructions/sample` figure
is `g_lastCycles / procCalls / frames`, and `g_lastCycles` does not scale with
the frame count — measured, it reports a flat ~376 per call at 1, 3, 5, 10 and
15 frames, so the per-sample figure is simply the constant divided by however
many frames were requested. The engine itself is fine (the wet is present in
every frame; zeros are evenly distributed across all 15 positions mod 15, with
no periodicity). It is the counter that cannot see inside the `do` loop. Count
the loop statically instead.

## Known limits and open work

**The tank rings**, and this is a memory limit rather than a bug. An FDN
sounds smooth when its modes overlap — mode spacing is `sr / total_delay`,
mode bandwidth is `2.2 / RT60`.

> ❌ **32K-era analysis (four-line engine), kept as history.** The engine is
> now 8 × 4096-word lines in a 65,536-word (1.49 s) per-server allocation
> since the XBUS shared-window split; the numbers below describe the retired
> layout.

**Say which number you mean.** "32K" is the **allocation**, and only a
quarter of it is ever heard as tail length:

| | words | ms |
|---|---|---|
| allocation (what `BUS.md` hands the server) | 32,768 | 743 |
| tank lines (the only part that sets tail length) | 16,384 | 372 |
| **total delay actually read at SIZE max** | 12,574 | **285** |
| diffusers + pre-delay + in-loop allpasses | 16,384 | 372 |

The last row buys density and pre-delay, not decay. Mode spacing is computed
from the **third** row, so quoting the allocation — or `DSP.md` §7c's "743 ms
ceiling", which is the first row — overstates the space by about 2.6×.

Recomputed against the real constants (an earlier recorded 4,493 samples
/ 9.8 Hz / overlap 0.06 belonged to an older tap set —
1567/1249/977/733 — and understated the build it was attached to):

| | total delay | spacing | overlap @ RT60 = 4 s |
|---|---|---|---|
| pre-re-layout | 6,286 | 7.0 Hz | 0.078 |
| **post-re-layout** | **12,574** | **3.5 Hz** | **0.157** |

**The 32K re-layout halves the gap and exhausts the lever.** Overlap doubles,
and that is the ceiling: 32K is the whole allocation and `DSP.md` §7c's
high-X region is not real, so there is no third doubling to take. Still ~6×
short of the overlap ≥ 1 that reads as smooth (it was ~13× short), and a
4-second decay would want ~1.8 s of total delay against the 285 ms available.
Modulation and diffusion have to cover the rest — which is the whole argument
for a Valhalla-flavoured big mode rather than a Blackhole-flavoured one.

The measurements below predate the re-layout and have not been retaken.

Measured confirmation: spectral flatness rises monotonically with SIZE
(0.0014 → 0.0066 from SIZE 32 to 127) and with shorter decay. Modulation
smears the modes and is the only structural fix at this budget — worth ~9×
flatness — but it saturates.

**Practical consequence: run SIZE high.** It is not just a bigger space, it
is a measurably smoother one.

One lever is left, and one is spent:

1. ~~**Spend freed cycles on more delay lines.**~~ — **taken**: the
   eight-line tank shipped. (The density pass left headroom that did not
   exist before; an earlier build spent 341 of it.)
2. ~~**Trade instance count for tank size**~~ — **taken.** This used to be a
   plan to patch the allocator table at `X:0x255` (8 modest instances, or 4
   large at 2 × 32K per DSP, or 2 very large at 1 × 45K). `BUS.md` reached
   the same 32K per server without touching `X:0x255` at all — the menu
   collapsed to two servers plus client stubs, so each server just hardcodes
   its own fixed base and takes half the bank's pool — and the re-layout
   above spends it. The 45K variant would still need the FX1 region and an
   allocator edit, and is not planned.

Smaller items: MOD depth's range wants calibrating by ear (older records call
this "SHVG's range" — SHVG is a *stock DARK REV* knob label the retired build
inherited, and BusVerb names its own knobs, so the item is just MOD); and
there is an unexplained emulator-only divergence between one and two
instances under a nonzero split.

`$e` is not dead: it carries GATE in its knob field and RATE in its companion
field, both live.


## Tuning: what is known

Several of these cost a hardware flash each and none are obvious from the
code. The measurements come from a spectral-flatness harness (see below for
its limits).

**Seasickness is RATE, not depth.** Pitch shift is `-d(delay)/dt`, so it
depends on how fast the delay moves, not how far. 63 samples at 2.84 Hz is
~28 cents of vibrato and sounds seasick; the same 63 samples at 0.25 Hz is
~2.5 cents and is inaudible. Depth is what smears the modes. Coupling MOD
to both — once done as a workaround for an inaudible control — means
turning it up adds wobble faster than it adds smearing. **Keep the rate
slow and fixed; let MOD move depth alone.**

❌ **REVERSED by Round 13** (`VOICING.md`). The rate pinned near 0.4 Hz was
measured as *the binding cause* of the metallic end-ring; the base rate went
×8 to ~2.2 Hz with the depth scales trimmed — fast-SHALLOW rather than
slow-deep — and ROOM's crest fell 65 → 49, the largest single movement of
any lever in the voicing log. RATE is a live 0.5/1/2/4× select besides. The
advice above would send you straight back into the ring it removed.

**Small SIZE is inherently bad.** At the original floor the whole tank was
566 samples: a mode spacing of 78 Hz, which is a comb, not a reverb. The
floor is now `f = 0.4` so the bottom of the knob is ~1,810 samples at 24 Hz.
Confirmed by ear before it was fixed.

**Modulation must never reach zero.** A completely static tank rings — its
modes are audible as pitched resonance. Some residual sweep is needed at
MOD=0.

**The interpolation fraction rule:** integer part via `asl #n`, fraction
masked with `2^(24-n)-1` and shifted by **n-1**, never by `n`. Shifting by
`n` pushes the top half past `0x800000`, where a 24-bit fractional reads
NEGATIVE, and the interpolation jumps backwards once per integer LFO step —
heard as a fast flutter.

**That bug was also doing something useful**, which is the uncomfortable
part: it is a noise source, and interpolation dither is a real technique for
breaking up delay-line artifacts. Every build preferred by ear had it. Fixing
it was correct and immediately exposed ringing that had been masked. If the
tail needs more smearing than slow deep modulation provides, *deliberate*
randomisation is the principled replacement.

**The carried interpolation partner is NOT the crackle — measured, −64 dB.**
Every interpolated read in the engine gets its `d1` for free by carrying
forward last sample's `d0`, on the argument that the read pointer advances
exactly one per sample. That argument holds only while the read OFFSET holds
still, so it was the standing suspect for the crackle: the LFOs step the
offset, and each step should invalidate one interpolation.

It is a real defect, but a tiny one, and only in one place:

* The four **tank** lines were never exposed. They are seeded before the
  loop, one sample further back with the *new* offset, which is exactly the
  block boundary the argument fails at — and the offsets cannot change
  mid-block, because the LFOs advance once per block. Deleting the four seed
  reads does change the output, so that priming is load-bearing, not
  vestigial.
* The two **in-loop allpasses** used the same trick and never got the
  same seeding. Now they do.

Cost of priming them: 28 instructions per BLOCK, outside the sample loop, so
zero against the table above. The in-loop comment's "every N register is
committed, so there is no other way to do this" is true per sample and false
once per block — which is where the fix lives.

Two things worth keeping from how this was settled, because both are reusable:

* **Verify address arithmetic by making the change a no-op.** With the
  allpass LFO depth forced to zero the offset never steps, so a correct
  prime must reproduce the stale carry *exactly* — ref and fixed renders
  come out bit-identical. A wrong address would differ even with a static
  offset. That separates "I changed something" from "I read the right word".
* **Isolate with MOD=0.** The tank's modulation follows MOD but the
  allpasses' depth is fixed and never zero, so at MOD=0 the only thing still
  stepping an offset is the allpass pair. The ref-vs-fix difference there is
  the defect alone, with no tank divergence mixed in.

Measured that way, the correction *is* a click train — crest 28.0 dB against
the tail's 10.8 dB, the exact shape predicted — but it sits at −94.7 dBFS
RMS under a −30.5 dBFS tail: ~64 dB down, peaks ~36 dB under the tail's RMS.
Far too quiet to be the audible fault. **Cross the interpolation partner off
the crackle suspect list; the fix is a correctness fix, not a voicing one.**
Also note this is a case where the raw ref-vs-fix diff is *misleading*: at
MOD=127 it reads −50 dB, but nearly all of that is chaotic divergence of a
feedback system, not artifact. The crest factor is what distinguishes them.

**And an independent confirmation that was already on file.** `VOICING.md`
records, by ear, that the crackle is *gone at MOD=0*. The allpass
depth is fixed and never follows MOD, so the allpass carry defect is fully
active at MOD=0 — it therefore cannot be a fault that disappears there. The
same test kills the tank's carry as a candidate from the other direction,
since the tank carries are primed. So the isolation trick above is not just
a convenient way to measure this bug; MOD=0 was already the observation that
ruled it out.

**The block-stepped LFO is not the fault either.** It was the leading
candidate by elimination, but built and measured it sits at
**−62.5 dB**, for 64 cycles/sample. The staircase
moves the delay by only ~0.026 of a sample across one block, which was never
going to be a crackle. Not kept. `VOICING.md` has the implementation
and the invariant that verified it (at MOD=0 there is nothing to ramp, and
the ramped engine comes out bit-identical to the stepped one).

**The offset/fraction PAIRING RULE — this one was the real fault.** Each
line's interpolation fraction must come from the same LFO as the integer
offset its `nK` was built from: `n1←$23/$24`, `n2←$21/$22`, `n3←$56/$57`,
`n4←$58/$59`. Lines 0 and 2 had B's and C's fractions swapped, so their
effective delay was `tap + offset_B + fraction_C`. A foreign fraction is a
sawtooth that wraps whenever *its own* LFO's integer part steps, which put a
**1-sample sawtooth at ~76 Hz** on two of the four lines.

Measured at **−29.6 dB**, against −62.5 dB for the staircase and −64 dB for
the allpass carry: 33 dB louder than either, and the only candidate with the
magnitude to be audible at all. It also passes every negative test recorded
in `VOICING.md` — gone at MOD=0, signal-proportional, broadband, not
the sample. The fix is a two-slot swap: no cycles, no words.

The four LFO *phases* are deliberately crosswise (see Signal path); the two
halves of one offset are not.

**Confirmed by ear, both halves.** The crackle is fixed, and the caution
above — that removing an accidental noise source exposes ringing it was
masking — **did not hold here**: on the 4–12 s tail the ringing is unchanged.
Deliberate randomisation is therefore NOT needed. The caution is real and
came from a real case, but it is something to **check**, not something to
assume; checking it costs a couple of listens. See `VOICING.md`.

The tail no longer has broadband noise in it, so the per-mode constants can
be judged on their own terms.

## What MODE actually varies

Six levers. With only the first three, the modes sounded alike by ear; all
six make them genuinely distinct.

(The HALL column is kept as history; shipping modes are ROOM/PLATE/BIG.)

❌ **THE WHOLE TABLE IS THE PRE-ROUND-7/13/R18 CONSTANT SET, not just the HALL
column.** The qualifier above implies the other columns are current; they are
not. Verified against the engine, 30 Aug 2026:

- **ER was REMOVED** (Round 7) — `$6c` is a freed slot. The "ER level" and
  "ER arrivals" rows describe a stage that no longer exists, and this
  document says so itself further up.
- **ROOM's tap scale is 0.60**, not 0.45 (`reverb_server.asm`: "tap scale
  0.60 (Round 13, was 0.45)").
- **All modes share the diffuser taps 641/1051/1511/1949** (Round 13, 3.6×
  longer), so the per-mode "diffuser taps" row is gone.
- **All modes run LFO rate scale 1.0** (Round 13). BIG's 0.25 was killed
  explicitly — "a huge space barely moves … left a near-static tank, and a
  static tank rings".
- **BIG's decay scale is 0.67578** (R18), not 1.00.
- ROOM and PLATE now share a diffusion coefficient, and BIG was raised.

`modules/busverb/reverb_server.asm` is the authority for every one of these
and `docs/VOICING.md` records why each moved. The table is kept below because
the *structure* — which levers MODE varies — is still right, and because the
starting point is worth seeing; **read no constant out of it.**

| lever | ROOM | PLATE | HALL | BIG |
|---|---|---|---|---|
| tap scale (size) | 0.45 | 0.5625 | 0.71875 | 1.00 |
| ER level | 0.75 | 0 | 0.25 | 0 |
| diffusion coefficient | high | highest | medium | lowest |
| **tap spread** | 1.60:1 | 1.24:1 | 1.92:1 | 1.69:1 |
| **ER arrivals** | 4.5–21 ms | — | 20–77 ms | — |
| **diffuser taps** | 1607.. | 1447.. | 1994.. | 2011.. |
| **LFO rate** | 0.70 | 1.00 | 0.45 | 0.25 |
| **decay scale → RT60** | 0.92 → 2.7 s | 0.965 → 4.7 s | 0.99 → 7.7 s | 1.00 → 10.0 s |

**Decay was the one MODE never touched**, and it is the biggest room-vs-hall
cue — every mode used to decay at whatever TIME said (6.9–11.6 s measured), so
ROOM vs HALL stayed the weakest pair however the others were set.

**Two invariants hold the per-mode work honest.** The mean tap is 3178 in every
mode, so tap scale and tap spread stay independent; and ROOM's spread is the
original set, so ROOM must render *bit-identical* whenever the indirection is
touched.

**The r7 state block is NO LONGER FULL** (`$68`/`$69`/`$6a`/`$71` freed
18 Aug 2026). What follows described the full state: `$7e..$81` were the last free slots. `r7+$84`
and up **hang the DSP** (host-owned — see `DSP.md`). Anything further that needs per-mode state must use the parking
pattern: `md_*` writes its scale into a slot a later parameter block is going to
overwrite anyway (`$2f` rate, `$1e` decay), and that block folds it into its own
multiply. `md_*` runs before every parameter block, which is what makes it safe.

**Spectral flatness cannot tell diffusion from distortion.** It rewards
broadband noise, so it ranked the flutter builds highly and dropped when the
flutter was fixed. It is useful for comparing structural changes, and
misleading for anything that adds noise. **When it and the ear disagree, the
ear is the measurement.** Early crest factor is the better companion metric.

**In-loop allpass proportion matters.** An allpass inside the feedback loop
is a dispersive element — the mechanism spring reverbs are built on. At 15%
of the line it feeds it is diffusion; ours ran 26–64% and were suspected of
producing a spring/plate ring. Removing them was tested but
bundled with other changes, so the result is not clean.

**Pack the buffers.** Both the tank lines and the input diffusers were
allocated equal power-of-two buffers but given taps spanning a 2.1:1 and
2.7:1 ratio, so roughly 40% of the delay memory was never read. Tightening
both to ~1.6:1 recovered it for nothing — no cycles, no memory, no loss of
instances — and was worth more than any other single change of the voicing
pass. **When a design allocates equal buffers for unequal contents, check
the utilisation.**

**Input diffusion and in-loop diffusion are not interchangeable.** Moving
input allpasses into the loop improved mode spacing but doubled the
early crest factor: the input chain smooths the attack, the in-loop chain
thins the modes. Pack both; do not trade one for the other.

**Averaging more tank lines into each output does not help.** The
lines share a feedback matrix, so they are not independent; orthogonal
4-line output taps concentrated energy rather than smoothing it, and gave
no stereo benefit over disjoint 2-line pairs.

**The tank had no input scaling, and at long TIME it saturated.** Fixed —
the engine now attenuates its diffused input by 12 dB before the tank, and
the four-line output sum no longer divides by 4. Those cancel exactly, so
output level and the shared WET bus are unchanged and the whole 12 dB is
spent on headroom inside the loop. One `asr` added, two removed: the build
got a word *smaller*.

**Accepted by ear, on the source where the fault was audible.** Three
loudness-matched renders of the synth pluck: old engine at 0 dB (the fault),
new engine at 0 dB, old engine at −12 dB trim (the known-good reference).
New-at-0 dB is indistinguishable from old-at−12 dB. That is the acceptance test —
the engine now behaves at full input the way it used to behave only with
12 dB of external trim.

### How this was found, and the trap in it

An FDN's steady-state gain is `1/(1-g)`, and nothing compensated for it:
+30 dB at TIME=64, +66 dB at TIME=127. Measured on a dense synth loop at
TIME=110, 6 dB less input gave only 2.3 dB less output. A pure sine at the
same peak level is linear to within 0.1 dB, so it is **density**, not peak
level, that drives this — a sine test misses it entirely.

The controlled trim test predicted, in advance, that 0 dB and −12 dB would
differ and that −12 dB and −24 dB would not. Both held by
ear, which is what identifies the mechanism as saturation and
nothing else.

**Then the measurements led the work astray, and this is the part worth
remembering.** Bass measured far worse than anything else — 26,741 clipped
samples at 0 dB against 680 for drums and 6 for the synth, a knee at −36 dB
rather than −12 dB, and a knee that tracked HP across a 24 dB range. A whole
argument was built on it: that no single constant could work, that a
LO-coefficient floor was needed, that MIX should become a crossfade.

**None of it was audible.** The bass renders sounded identical to each other
throughout — saturated, clean, old engine, new engine. So that entire branch
was measurement-led, and this file's own rule already covered it: *when the
measurement and the ear disagree, the ear is the measurement.*

Two concrete cautions that came out of it:

* **Clipped-sample counts predict audibility badly here.** 26,741 clipped on
  bass was inaudible; the audible synth fault came with only 6. The counter
  measures the *output* rail, while the audible fault was *loop* compression
  — different things, and it is the loop that matters.
* **Removing the saturation makes the output louder**, because the
  saturation was acting as a limiter — clip counts go *up* after the fix
  (synth 6 → 74, bass at −6 dB 0 → 2,920). This was called a blocker on the
  strength of those counts. By ear it is not one: the fixed engine at 0 dB
  is indistinguishable from the reference. Same shape as the interpolation
  bug recorded above — fixing something correct exposed what it had been
  masking — but here what it exposed does not matter.

**MIX: a plain crossfade is the wrong shape here** *(historical — the MIX
knob no longer exists; the reverb is a return and p5 is IN. Kept for the
level-law reasoning.)* A first fix made it a
straight `dry*(1-MIX) + wet*MIX` crossfade, because the old additive law left
dry at full scale forever and the top of the knob was never actually *wet*.
That motive was sound and the result was not: measured, the knob got **7 dB
QUIETER as it was turned up** (−22.0 dBFS at MIX=0 → −28.8 at 96). This is not
the usual −3 dB crossfade dip. **A reverb's wet is inherently far below its
dry** — the tail spreads the same energy over seconds — so swapping one for the
other at equal gain loses real level, and turning a reverb up should never
shrink the sound. The shipping law holds the dry at unity for the bottom half
and crossfades it away over the top half:

    dry = 1              MIX <= 64      pure "mix more in"
        = 2 * (1 - MIX)  MIX >  64      still reaches fully wet at the top

Flat to within 0.1 dB across the bottom half, peak unchanged at 0.70–0.71, and
it keeps what the plain crossfade was after. The plain crossfade was judged
unintuitive by ear before it was measured; the measurement agreed.
That is a voicing decision, not a bug fix, and there is no ear evidence it
matters yet.

**Change one thing per flash.** When five things changed between two builds,
the result was worse in a way that could not be attributed; the recovery was
to reflash the older build, confirm the baseline, and move one variable at a
time.

## The design, as built

**One FDN engine with a MODE select**, covering standard characters *and* the
largest space this hardware supports — rather than choosing between them. The
three free page-2 selects exist precisely for this; MODE is the obvious first.

* **Standard characters**: room / plate / big (a fourth HALL mode was cut as
  indistinguishable from BIG in blind A/B), in the spirit of a Chase Bliss
  CXM 1978. Comfortably within budget — these want density, not length.
* **Big mode**: **Valhalla-flavoured, not Blackhole.** Deliberate: Blackhole's
  character comes substantially from raw allocation, and 743 ms was the hard
  ceiling when the mode was designed (`DSP.md` §7c — the high X region was
  probed and is not real; the allocation is 1.49 s per server since the XBUS
  shared-window split).
  Valhalla's large spaces get their scale from long feedback, heavy modulation
  and dense diffusion, which is both achievable here and a match for the FDN
  structure already in place. Expect genuinely large and smooth; not infinite.

MODE should reconfigure tap lengths, diffusion depth, damping and modulation
together — not merely rescale SIZE.

> 🟡 **Historical:** the hardware confirmation below is real, but it describes
> the retired four-mode, four-line engine; the shipping engine is the
> eight-line tank.

**All of the above was built and confirmed on hardware.** MODE varies **six**
levers, not the original three: tap scale and spread, ER level and arrival times,
diffusion coefficient and diffuser taps, LFO rate, damping, and decay time.
RT60 runs 2.7 / 4.7 / 7.7 / 10.0 s across ROOM → BIG. Decay time was the lever
MODE had never touched and the one that mattered most — every mode used to
decay at whatever TIME said, which is why ROOM vs HALL stayed the weakest pair
however the others were set. Full record in `VOICING.md`.

**Order of work — where it stands:**
1. ~~The 32K re-layout~~ — **done**, flashed, confirmed by ear.
2. ~~Design the modes~~ — **done**, recorded in `VOICING.md`.
3. ~~Measure real cycle cost with both effects live~~ — **counted**, and the
   answer changed the picture: **934 of ~1080, 86% used** (❌ old-budget
   accounting — see `CHIP.md`), not the 529 or ~700
   earlier records carried. `tools/cycle_count.py` makes it reproducible.
   What is still flash-only is confirming it under load — the static count
   models no memory-contention stalls, so it is a floor.

**Also still open**, both small and both with their evidence recorded above:
MOD depth's range wants calibrating by ear (measured flattening after ~64, so
the top half of the knob may be doing nothing — `VOICING.md`); and the
unexplained emulator-only divergence between one and two instances under a
nonzero split. Two things the emulator cannot check at all: item 3 above, and
the front-panel UI surface for the companion-field selects (**WIDTH**,
**RATE** — see `PARAM_PAGES.md` for what the harness can and cannot drive).
❌ WIDTH was **RETIRED** in v7 (23 Aug 2026): width is pinned wide and that
companion field carries SHFT, the shimmer interval. It is listed here as
live open work and this document's own parameter table has it right.
(Historically: WIDTH was confirmed moving on-unit as its 4-step select.)

**Closed, do not re-chase:** modal prominence (8–11 dB over the local envelope,
monotonic in total delay, no structural lever left under the 32K ceiling —
`VOICING.md`); tank saturation; the tail crackle; the MIX law.
