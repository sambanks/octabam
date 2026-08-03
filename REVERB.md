# ChonVerb — the custom reverb

A four-line FDN reverb. It now ships as **ChonVerb**, one of the three effects
on the shared send bus (`BUS.md`), running on the FX2 slot of any track in a
bank. Built by `tools/build_bus.py`; source `dsp/reverb_server.asm`.

> **The old standalone DARK REV replacement is retired.** Earlier builds
> (`dsp/reverb88.asm` via `tools/build_reverb.py`) replaced stock DARK REV in
> place, inheriting its descriptor and knob labels. That is no longer the
> product and is not being maintained — ChonVerb has its own cloned descriptor,
> its own id, and its own knob layout. Where this document still describes the
> old build, it is history; the sections below marked **current** are not.

> **Status, 4 Aug 2026 (`ChonVerb19`, on hardware).** Structure, parameters and
> the MODE select are all working on the unit. The four modes' constants are
> first-pass values chosen by analysis rather than by ear, so per-mode voicing
> is the live work — see "Planned design" at the end.

For how the DSP subsystem works — boot, payload format, the dispatcher ABI,
the allocator, the memory map — see `DSP.md`. For the bus itself see `BUS.md`.
For the reverse-engineering that got us here, `REVERB_LOG.md` (historical).

---

## Signal path

```
in ─► pre-delay ─► 4 series allpasses ─► ┌─ FDN tank ──────────┐ ─► width ─► mix ─► out
        (PRE)        (input diffusion)   │ 4 lines, modulated  │
                                         │ 4x4 Hadamard        │
                                         │ HI damping          │  all inside the
                                         │ LO cut              │  feedback loop
                                         │ 2 in-loop allpasses │
                                         └─────────────────────┘
```

* **Pre-delay** — up to 4096 samples (93 ms), modulo buffer on r6.
* **Diffusers** — four series allpasses, g = 0.703, taps 1994/1706/1438/1226,
  packed to a 1.6:1 ratio so they nearly fill their 2048-word buffers.
* **Tank** — four delay lines with a 4×4 Hadamard feedback matrix. All four
  reads are **interpolated and LFO-modulated**, with the LFO phases crosswise
  (lines 0 and 2 on the inverse triangle, 1 and 3 on the forward) so lines
  sharing tap factors move in opposition.
* **In the loop** — a one-pole low-pass (HI) and a one-pole high-pass (LO)
  per line, so the decay is shaped per band rather than the output EQ'd.
* **In-loop allpasses** — two, 2048 words each, taps 298/446, on lines 0
  and 1. An allpass in the feedback path multiplies echo density on every
  circulation, which is how a smooth tail comes out of finite memory. Note
  the proportion matters: too long relative to the line and it becomes a
  dispersive element, which is what a spring reverb is.
* **Early reflections** — six taps off the pre-delay buffer, alternating L/R
  with decaying gains, level set by MODE. Costs no memory: the pre-delay
  already held 93 ms of input history and was read once.
* **Out** — mid/side width, then a dry/wet crossfade.

## Parameters (current)

All twelve are live — six on page 1, six on page 2 — and the page-2 mapping
was **measured**, not inferred (`DSP.md` §9). Hardware-confirmed as shipped in
`ChonVerb19`.

| page | slot | label | reads | what it does |
|---|---|---|---|---|
| 1 | 0 | TIME | `r6+$0` | feedback → RT60 |
| 1 | 1 | MOD | `r6+$1` | modulation depth |
| 1 | 2 | SIZE | `r6+$2` | scales all four tap lengths, within the current MODE |
| 1 | 3 | HP | `r6+$3` | **LO** — high-pass inside the feedback path |
| 1 | 4 | LP | `r6+$4` | **HI** — high-cut damping inside the feedback path |
| 1 | 5 | MIX | `r6+$5` | dry/wet **crossfade** |
| 2 | 6 | SPEED | `r6+$b` | LFO rate, ~0.13–1.9 Hz |
| 2 | 7 | MODE | `$c` bits 8-15 | **stepped select**: 0 ROOM, 1 PLATE, 2 HALL, 3 BIG |
| 2 | 8 | DIFF | `r6+$d` knob | allpass coefficient, ~0.38–0.80 |
| 2 | 9 | WIDTH | `r6+$d` low | mid/side, 0 = mono |
| 2 | 10 | PRE | `r6+$e` knob | pre-delay, 0–93 ms |
| 2 | 11 | -DEL | `r6+$e` low | dry send into the DELAY bus (`BUS.md`) |

**Five of the six page-2 controls are full-travel knobs**, including two in
*companion* fields. `DSP.md` §9 used to say the budget was three knobs plus
three small selects; that was inferred from stock's usage, and hardware
falsified it. Only MODE is deliberately stepped.

**Page-2 slots pair up**: a knob arrives as `value<<16` occupying bits 16-22,
leaving the low bits of the same word as an independent field. Even slot =
knob field, odd slot = companion field of the same word. Both can carry a
full 0–127 value; mask the companion with `#>$7f` and shift it up by 16.

**PRE lives on `$e`, not `$c`.** Nothing drives `$c`'s knob field usefully.
Stock DARK reads *its* pre-delay from `$c`, which is why older builds did.
Do not "fix" this back.

### Making a cloned descriptor draw correctly

This cost six hardware flashes to establish, so it is written out in full.
Four per-parameter arrays matter, each 12 × u32, `P`-relative:

| offset | what it is |
|---|---|
| `P+0x9a` | **value count** — the parameter's range, drawn on a fixed 0–127 scale. A count of 16 gives 16 values over ⅛ of the knob's travel, *not* 16 nicely-spaced steps. |
| `P+0x0ca` | **display formatter**, a function pointer. `0` = plain numeric knob. |
| `P+0x0fa` | **formatter's partner**, also a function pointer. Both must be set for stepped rendering. |
| `P+0x12a` | **must be `0` for a stepped control.** Surveyed all 20 stepped params in stock FX2: 20 of 20 have it zero. |

**A clone inherits all four from its donor**, and the donor's values are for a
different algorithm. That is what made `→DEL` render as DARK's "MIX / SEND"
however large a count it was given, and what kept MODE a plain knob for three
builds. Zero `0x0ca`/`0x0fa` for every renamed slot; for a stepped control,
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

`BUS.md` allocates the server **32,768 words** at the hardcoded base `Y:0x4000`
(spanning `0x4000–0xBFFF`), and since the 32K re-layout the engine uses all of
them:

| offset | size | what |
|---|---|---|
| `base+0x0000` | 4 × 4096 | tank lines, taps 3958/3386/2894/2474 scaled by SIZE |
| `base+0x4000` | 4 × 2048 | input allpasses, taps 1994/1706/1438/1226 |
| `base+0x6000` | 4096 | pre-delay |
| `base+0x7000` | 2 × 2048 | in-loop allpasses, taps 298/446 |

**All persistent state lives in the r7 block**, which is per-instance and
survives between calls — `$82` is the warm-up counter (tagged
`$2c0000 | count`), `$83` the tank phase, and `$10..$61` the working set
including the four LFO phases and the one-pole states. There is no Y state
block; it was round-tripped needlessly until v74.

## The 32K re-layout (done, emulator-verified, not yet flashed)

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

**The in-loop allpass taps DID double, 149/223 → 298/446.** The plan didn't
say so, and their `n5` had to be recomputed for the bigger buffer either way.
What v85 fixed there was a *proportion* — ~15% of the line the allpass feeds,
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
* **The bus plumbing is untouched.** The `→DELAY` dry send still lands on
  `BUS.md`'s exact hand-derivable value (`0x0c8000` = dry 0.125 × level
  0.78125 × `0x800000`), bit-identical between the old and new builds.

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
problem the same session turned up is under "Known limits" below, and is the
next thing to fix.

**Not yet flashed.** Nothing here needs a flash to hear; the cycle budget
still does.

## Register map inside the sample loop

Every address register is committed; this is the constraint any change works
against.

| reg | use | modulo |
|---|---|---|
| r0 / n0 | audio buffer, stereo stride | linear |
| r1–r4 / n1–n4 | tank line pointers; nK = read offset | m1–m4 = `$fff` |
| r5 / n5 | allpass pointer; n5 = 2048−tap, rewritten per allpass | m5 = `$7ff` |
| r6 / n6 | pre-delay pointer and offset | m6 = `$fff` |
| r7 | state block | — |
| n7 | frame count, from the dispatcher | — |

## Build, verify, flash

ChonVerb ships through the bus build, not the retired `build_reverb.py` path:

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
`r6` — indices 0–5 are page 1, then 6–9 land on `r6+$b..$e`. It handles the
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

**Superseded: "four instances per DSP".** The engine was shaped around fitting
four reverb instances on one chip — that is what forced the density pass
(432 → 297 cycles/sample) and what made every feature look unaffordable. The
bus design retired it: **one ChonVerb per bank**, enforced by the server-role
lock in `BUS.md`. A bank's four FX2 slots hold one reverb, one delay and two
sends, not four reverbs.

Counted statically from the sample loops (two-word `#>` immediates costed as
two cycles):

| | instructions | cycles/sample |
|---|---|---|
| `reverb_server` | 367 | 381 |
| `delay_server` | 107 | 112 |
| `send_client` | 16 | 18 |
| **a full bank** (1 + 1 + 2 sends) | | **529** |
| budget per DSP (`stageprobe5/6`) | | ~1080 |
| **headroom** | | **~551** |

That is **1.4× the entire current reverb engine**, free. Under the old
assumption a bank cost 4 × 381 = 1524 and did not fit at all, which is why
the engine has been living well below its means.

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

Recomputed against the real constants (the previously recorded 4,493 samples
/ 9.8 Hz / overlap 0.06 belonged to the tap set *two* generations back —
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

1. **Spend freed cycles on more delay lines.** The density pass left
   headroom that did not exist before; v84 uses 341 of it. Still open.
2. ~~**Trade instance count for tank size**~~ — **taken.** This used to be a
   plan to patch the allocator table at `X:0x255` (8 modest instances, or 4
   large at 2 × 32K per DSP, or 2 very large at 1 × 45K). `BUS.md` reached
   the same 32K per server without touching `X:0x255` at all — the menu
   collapsed to two servers plus client stubs, so each server just hardcodes
   its own fixed base and takes half the bank's pool — and the re-layout
   above spends it. The 45K variant would still need the FX1 region and an
   allocator edit, and is not planned.

Smaller items: MOD depth's range wants calibrating by ear (this was recorded
for years as "SHVG's range" — SHVG is a *stock DARK REV* knob label the
retired build inherited, and ChonVerb names its own knobs, so the item is
just MOD); and there is an unexplained emulator-only divergence between one
and two instances under a nonzero split.

The old note that "MIXF (`$e`) is dead" is also gone: `$e` carries PRE in its
knob field and →DEL in its companion field, both live.


## Tuning: what is known

Several of these cost a hardware flash each and none are obvious from the
code. The measurements come from a spectral-flatness harness (see below for
its limits).

**Seasickness is RATE, not depth.** Pitch shift is `-d(delay)/dt`, so it
depends on how fast the delay moves, not how far. 63 samples at 2.84 Hz is
~28 cents of vibrato and sounds seasick; the same 63 samples at 0.25 Hz is
~2.5 cents and is inaudible. Depth is what smears the modes. Coupling MOD
to both — which v64 did as a workaround for an inaudible control — means
turning it up adds wobble faster than it adds smearing. **Keep the rate
slow and fixed; let MOD move depth alone.**

**Small SIZE is inherently bad.** At the original floor the whole tank was
566 samples: a mode spacing of 78 Hz, which is a comb, not a reverb. The
floor is now `f = 0.4` so the bottom of the knob is ~1,810 samples at 24 Hz.
Confirmed by ear ("smallest size sounds worst") before it was fixed.

**Modulation must never reach zero.** A completely static tank rings — its
modes are audible as pitched resonance. Some residual sweep is needed at
MOD=0.

**The interpolation fraction rule:** integer part via `asl #n`, fraction
masked with `2^(24-n)-1` and shifted by **n-1**, never by `n`. Shifting by
`n` pushes the top half past `0x800000`, where a 24-bit fractional reads
NEGATIVE, and the interpolation jumps backwards once per integer LFO step —
heard as a fast flutter. This bug was live from v72 to v79.

**That bug was also doing something useful**, which is the uncomfortable
part: it is a noise source, and interpolation dither is a real technique for
breaking up delay-line artifacts. Every build the user liked had it. Fixing
it was correct and immediately exposed ringing that had been masked. If the
tail needs more smearing than slow deep modulation provides, *deliberate*
randomisation is the principled replacement.

**Spectral flatness cannot tell diffusion from distortion.** It rewards
broadband noise, so it ranked the flutter builds highly and dropped when the
flutter was fixed. It is useful for comparing structural changes, and
misleading for anything that adds noise. **When it and the ear disagree, the
ear is the measurement.** Early crest factor is the better companion metric.

**In-loop allpass proportion matters.** An allpass inside the feedback loop
is a dispersive element — the mechanism spring reverbs are built on. At 15%
of the line it feeds it is diffusion; ours ran 26–64% and were suspected of
producing a spring/plate ring. Removing them was tested (v82/v83) but
bundled with other changes, so the result is not clean.

**Pack the buffers.** Both the tank lines and the input diffusers were
allocated equal power-of-two buffers but given taps spanning a 2.1:1 and
2.7:1 ratio, so roughly 40% of the delay memory was never read. Tightening
both to ~1.6:1 recovered it for nothing — no cycles, no memory, no loss of
instances — and was worth more than any other single change of the voicing
pass. **When a design allocates equal buffers for unequal contents, check
the utilisation.**

**Input diffusion and in-loop diffusion are not interchangeable.** Moving
input allpasses into the loop (v87) improved mode spacing but doubled the
early crest factor: the input chain smooths the attack, the in-loop chain
thins the modes. Pack both; do not trade one for the other.

**Averaging more tank lines into each output does not help** (v89). The
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
New-at-0 dB against old-at−12 dB: **"same"**. That is the acceptance test —
the engine now behaves at full input the way it used to behave only with
12 dB of external trim.

### How this was found, and the trap in it

An FDN's steady-state gain is `1/(1-g)`, and nothing compensated for it:
+30 dB at TIME=64, +66 dB at TIME=127. Measured on a dense synth loop at
TIME=110, 6 dB less input gave only 2.3 dB less output. A pure sine at the
same peak level is linear to within 0.1 dB, so it is **density**, not peak
level, that drives this — a sine test misses it entirely.

The controlled trim test predicted, in advance, that 0 dB and −12 dB would
differ and that −12 dB and −24 dB would not. Both held ("very audible",
"identical"), which is what identifies the mechanism as saturation and
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

Still true and still not acted on: MIX adds wet on top of *unity* dry rather
than crossfading, so `dry + 0.78×wet` must clip a hot source at high MIX.
That is a voicing decision, not a bug fix, and there is no ear evidence it
matters yet.

**Change one thing per flash.** Between v77 and v83 five things changed and
the result was worse in a way that could not be attributed. The recovery was
to reflash v77, confirm the baseline, and move one variable at a time.

## Planned design (agreed, not yet built)

**One FDN engine with a MODE select**, covering standard characters *and* the
largest space this hardware supports — rather than choosing between them. The
three free page-2 selects exist precisely for this; MODE is the obvious first.

* **Standard characters**: room / plate / hall, in the spirit of a Chase Bliss
  CXM 1978. Comfortably within budget — these want density, not length.
* **Big mode**: **Valhalla-flavoured, not Blackhole.** Deliberate: Blackhole's
  character comes substantially from raw allocation, and 743 ms is the hard
  ceiling (`DSP.md` §7c — the high X region was probed and is not real).
  Valhalla's large spaces get their scale from long feedback, heavy modulation
  and dense diffusion, which is both achievable here and a match for the FDN
  structure already in place. Expect genuinely large and smooth; not infinite.

MODE should reconfigure tap lengths, diffusion depth, damping and modulation
together — not merely rescale SIZE.

**Built as of `ChonVerb19`**: the MODE select exists and works on hardware
(slot 7, stepped, four values). Its per-mode constants — tap scale, early-
reflection level, diffusion offset — are first-pass and want tuning by ear.

**Order of work:**
1. ~~The 32K re-layout~~ — **built and emulator-verified**, see above. It
   still needs a flash: by ear is what tells you how far the hardware
   actually goes, and nothing before that does.
2. Measure real cycle cost with both effects live. Every figure taken so far
   has been dominated by warm-up and is meaningless; `DSP.md` §12's rule
   (measure, don't guess) applies.
3. Then design the modes against what steps 1 and 2 reveal.
