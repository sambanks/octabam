# Suggestions for other areas, from building fxlive

fxlive keeps to its own folder. Building it turned up a few things that
belong to other people's areas. They are recorded here instead of being
changed from this one, so each owner can take, adapt or decline them. Each
says what was measured, what is inferred, and what fxlive does meanwhile.

## 1. Declare "the sound is made on the ColdFire" in the manifest

**Area:** the module schema (`tools/remix/schema.py`, `Harness`) and Tape
Echo (`modules/tapeecho/`).

TAPE ECHO's DSP dispatch is a passthrough; its sound is made in the stock
delay routine `0x400031a0` on the ColdFire. Two tools now need to know
that, and each keeps its own copy of the fact:

- `tools/remix/audition.py:155` refuses `mod.name == "tapeecho"` by name;
- fxlive keeps `CF_AUDIO` in `fxlive.py` (TAPE ECHO, plus the stock DELAY
  from `stock.NO_DSP`).

A third ColdFire effect would have to be added to both by hand, and
missing either one fails quietly (a dry render). A manifest field, for
example `Harness(cf_audio=True)`, would let both read it from the module.
Until then fxlive keeps its own list, so the decision stays with the
schema and Tape Echo owners.

## 2. Show the assembler's own message when a build fails

**Area:** the build (`tools/build/build_bus.py`, `assemble_syms`).

`assemble_syms` runs `dsp_asm` with `check=True`, so a refused line
surfaces as a `CalledProcessError` naming a temporary file, and the
assembler's message (`445: InvalidInstruction -- "bogusop x0,y9"`) is not
shown. The fix is small: run `dsp_asm` without `check=True` and, when it
refuses, exit with its stderr and the composed source line each message
names (its line numbers are the composed `src.asm`'s, not the module
file's). A successful build would be unchanged. Build-failure output is
not covered by refhash, so whether anything parses the old failure text
should be checked before it lands.

## 3. The stock reverbs render no wet signal under `dsp_host`

**Area:** the harness (`tools/harness/dsp_host/`) and the Analog BD
module's reverb gate (`tools/harness/verify_analog_bd_reverbs.py`).

Draft issue text:

> Measured 9 Oct 2026, with `verify_analog_bd_reverbs`'s own `dsp_host`
> command (two cores, `-audio 0`, `-ctx 372,39b,53e`, `-allocproc end`) on
> the pure stock image, with noise held past the 256-call warm-up: the
> stock PLATE REV at MIX 64 is bit-identical to MIX 0, and at MIX 127 it
> is silence, with no tail after the input stops. So the harness renders
> no wet signal for it. The gate's input ends at block 256, inside the
> warm-up, so its "not silent" assertion is met by a near-silent output
> (peak 1 LSB) on both sides of the comparison. DARK REV was not separated
> this far. The cause is not located. Until it is, no local render says
> anything about a stock reverb's wet sound, and the gate's identity
> check compares silence with silence.

What fxlive does meanwhile: it plays stock PLATE REV and DARK REV as
`dsp_host` renders them. Its README lists that among what it cannot show.

## 4. A public way to reload the module registry

**Area:** the remix engine (`tools/remix/registry.py`).

The registry caches every manifest in a private module global
(`_cache`). fxlive picks up a manifest edit by setting
`registry._cache = None`, which reaches into the registry's internals. A
small public `registry.reload()` (or a cache keyed on the manifests'
mtimes) would let a long-running tool do this without depending on a
private name.

## 5. `out/platform/` is one fixed path

**Area:** the build and the DRAM platform (`tools/remix/`, `out/platform/`).

`BUS_OUT` moves the image, but a DRAM build still writes its runtime to
the fixed `out/platform/` (`runtime.raw`, `layout.json`, the ELF). Two
builds in one worktree, such as fxlive's and a gate's, can pair an image
with the other build's runtime. That happened once while building fxlive:
cf_host crashed at a garbage PC because it was given the wrong runtime.
fxlive copies the runtime away right after its own build, which narrows
the window but does not close it. An output directory that follows
`BUS_OUT` (or its own variable) would close it.

## 6. Tape Echo's ctypes structs live inside its verifier

**Area:** Tape Echo (`tools/verify/verify_tapeecho_cpu.py`).

`State`, `Params` and `RING` mirror `modules/tapeecho/cpu.h` for ctypes,
and they live in the verifier script. fxlive's check imports them from
there, so it depends on another module's test file. That is acceptable
for a check, but if those structs had a home beside `cpu.h` (or were
generated from it), both could share them without one test importing
another.

## 7. Two indexings of the delay's active-track byte

**Area:** Tape Echo's CPU probe (`tools/harness/tapeecho_cpu_probe.cpp`)
and `docs/firmware/COLDFIRE_DELAY.md`.

The probe writes the routine's per-track byte at `0x80000eb4 + 8·ping +
track` in its benchmark (lines 402 and 646) and at `0x80000eb4 + track` in
its end-to-end test (line 569). The doc gives `0x80000eb4 + 8·ping`
(+ track). The end-to-end test calls the per-track hook with that address
already on the stack, so it may not matter there. fxlive's `cf_host`
follows the doc. Worth a note in the probe saying which is the firmware's.
