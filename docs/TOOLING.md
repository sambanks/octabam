# The tooling, end to end

Nothing in this project uses a normal embedded toolchain, so this page walks
all of it — what each tool is, why it exists, and where it sits in the
pipeline. If you have never touched a DSP56300 or unpacked a firmware image,
start here; the deep dive on the audition/measurement rig specifically is
`docs/HARNESS.md`.

The pipeline, left to right:

```
acquire ──► unpack ──► understand ──► build ──► hear/measure ──► verify ──► flash ──► capture
scripts/     scripts/    dsp_modmap     build_bus   dsp_host +      verify_*    docs/       capture_hw
fetch-os     analyze     disasm         make image  wrappers        cycles      FLASHING    ot_midi …
```

`make help` lists the entry points; almost everything below is behind a make
target.

## The chip, in one paragraph

The Octatrack's audio runs on a Freescale **DSP56721**: two DSP56300-family
cores, 24-bit fixed-point, with three separate memory spaces per core — P
(program), X and Y (data) — and hardware loops and modulo addressing that
the effects lean on heavily. There is no C compiler in this pipeline;
effects are written directly in DSP56300 assembly, one module per
directory (`modules/<name>/*.asm`; `dsp/` keeps the shared probes and the
null stub). The
ColdFire (a 68k-family CPU) runs the OS, UI and sequencer and is a
completely separate instruction set and toolchain.

## 1. Toolchain (`make setup`, `scripts/setup.sh`)

Idempotent; assumes macOS + Homebrew (Linux substitutions are the obvious
ones — the DSP toolchain itself is plain CMake). It builds:

| tool | from | what it is |
|---|---|---|
| `dsp_asm` | `vendor/dsp56300` | the DSP56300 assembler. ⚠️ It **mis-encodes some instructions silently** — `CLAUDE.md`'s trap list is required reading before trusting it |
| `dsp_host` | `tools/dsp_host/` (staged into `vendor/dsp56300` and built there) | this project's emulator harness: runs assembled effects on the dsp56300 emulator core. `docs/HARNESS.md` |
| `elektron-firmware-tool` | `vendor/elektron-firmware-tool` (patched) | packs/unpacks Elektron's OS container formats |

The disassembler from the same dsp56300 project is the other half of the
deal: **disassemble what you assemble** is a project rule, not advice,
because the assembler's failure mode is clean assembly of wrong machine
code.

## 2. Acquiring and unpacking an OS

No Elektron binary lives in this repository — you fetch your own copy and
every build derives from it reproducibly.

| tool | what it does |
|---|---|
| `scripts/fetch-os.sh` (`make os`) | downloads the official OS from Elektron's site and prints its SHA256 — the hash is what makes any build claim checkable by someone else |
| `scripts/analyze.sh` (`make recon`) | static recon: entropy, binwalk, strings, container unpack → **`out/raw/section_3_MAIN_OS.bin`**, the decompressed 1.1 MB ColdFire image every build script reads as its base |
| `tools/bin_decode.py` | offline decoder for the `.bin` (ELUP) transport: strips the header, undoes the XOR-with-feedback obfuscation, verifies the additive checksum — a reimplementation of the firmware's own update validator, so a passing checksum proves the decode is right |
| `tools/make_bin.py` | the reverse: wraps a patched container back into an ELUP `.bin` for the fast CF-card OS UPGRADE path (SysEx flashing takes minutes; the card path doesn't) |
| `tools/entropy.py` | sliding-window Shannon entropy scanner — how the compressed region was located in the first place |
| `tools/find_base.py` | recovers a raw image's load address by pointer→string correlation (how `0x40000400` was established) |

The container formats themselves (ELUP/ELEK/aPLib) are documented in
`docs/ARCHITECTURE.md` §3.

## 3. Understanding the firmware

Two instruction sets, two toolchains:

| tool | side | what it does |
|---|---|---|
| `tools/dsp_modmap.py` (`make modmap`) | DSP | recovers the **module load map** — which bytes of the image load to which DSP address in which memory space. Everything DSP-side depends on it; a disassembly at the wrong PC is worthless. Also produces the `.mem` memory dumps `dsp_host` boots |
| `tools/dsp_disasm_all.py` | DSP | disassembles every P module of both payloads at its true load address — one `.asm` per payload plus per-module binaries |
| `tools/dsp_reach.py` | DSP | control-flow reachability sweep from the real entry points (dispatch tables, vectors, bootstraps) — separates live code from dead space |
| `scripts/disasm.sh` (`make disasm`) | ColdFire | opens radare2 on the decompressed MAIN OS with the right arch and base (m68k BE @ `0x40000400`) |

## 4. Building firmware

**`tools/build_bus.py` is THE builder** (`make bus` = `XBUS=1 SPEC=1`). What
it builds is a **remix**: a named selection of modules (`make bus
REMIX=<name>`, default `chongbong`; `make modules` lists both). Each
`modules/<name>/manifest.py` declares one contribution — menu entry,
parameters, DSP source, ColdFire caves — against the schema in
`tools/remix/schema.py`, and `tools/remix/ledger.py` refuses a selection
whose modules collide on an FX2 id, cave, hook site or core-private Y word.
`docs/MODULES.md` is the contributor guide. The builder then assembles the
selected effects, places them into each payload's donor region in declared
priority order, wires the dispatch tables, patches the ColdFire-side menu
descriptors, and census-checks itself (it will refuse a build whose source trips one of its
guards — that is the guard working). It is driven entirely by env flags —
`DEV`, `NOSHIM`, `MODE`, `DFRZAT`, `TPROBE` and more; grep `environ` in the
file for the full set, and note the render cache fingerprints every one of
them (`docs/HARNESS.md`). `make image` then repacks the result into a
card-flashable `.bin` with the build number stamped into the OS version
string — a unit whose version you cannot map to a commit is a unit you are
guessing about. `docs/FLASHING.md` before writing anything to hardware.

Earlier and special-purpose builders are kept as records, not entry points:
`build_menu.py` (superseded by build_bus; the ColdFire menu-integration
record), `build_reverb.py` (the pre-bus single-effect build),
`build_fx1.py` (an FX1-slot experiment), `build_dspprobe.py` +
`gen_probe.py` (hardware memory probes), `gen_reverb.py` (the legacy
four-line engine generator; its probe-derived constraints remain the
provenance record).

## 5. Hearing and measuring locally

The core of the project's method: render on the desktop at ~6× real time
instead of flashing. Covered in depth by `docs/HARNESS.md`; the short
version:

| tool | what it does |
|---|---|
| `tools/dsp_host` | the emulator harness itself — boots a payload dump, calls effects through the recovered ABI, captures audio, polices memory |
| `tools/render_reverb.py` (`make reverb IN=..`) | wav → ChonVerb → wav, knobs by name, sweeps, wet-only — the voicing instrument |
| `tools/send_probe.py` (`make render`, `make render-delay`) | renders a real SEND→bus→server path and measures it numerically |
| `scripts/make_test_audio.py` | synthesises the standard audition material into `out/test_audio/` |

## 6. Verifying

`make check` is the floor for any change. The family, and what each proves:

| tool | proves |
|---|---|
| `tools/cycle_count.py` (`make cycles`) | static per-sample cycle count of each server against the measured budget — static because the emulator's instruction counter cannot measure this |
| `tools/verify_roll.py` / `verify_delay.py` | an alternate reverb / delay engine is **bit-identical** to the shipping one — the gate every refactor passes before landing |
| `tools/verify_bus.py` (`make verify-bus`) | a bus-layout change is behaviour-preserving: 17 layouts, stamp-edit-compare (`docs/XBUS.md`) |
| `tools/verify_menu.py` | the ColdFire menu edits against the real chooser mechanism, decompiled from the firmware — including the descriptor traps (formatter vs count) |
| `tools/verify_slots.py` | static dead-store/aliasing check on the r7 state block — the family of bugs where one slot means two things |
| `tools/verify_midi.py` | the note→PITCH interval path, locally, via a build override |
| `tools/verify_burn.py` | the cycle-burn probe is the shipping engine plus an inert knob (currently SKIPs — the probe does not place) |
| `tools/remix/selftest.py` | the resource ledger still catches every collision it claims to (part of `make check`) |
| `scripts/refhash.sh` | a change to the BUILD (not a module) changed nothing: 23+ configurations, artifacts *and* build reports, bit-identical — save a baseline on a tree you trust first |

## 7. Hardware measurement and control

For the claims the emulator structurally cannot make (`docs/HARNESS.md`,
last section), the hardware rig — protocol in `docs/CAPTURE.md`:

| tool | what it does |
|---|---|
| `tools/capture_hw.py` | records the unit through an audio interface and analyses the capture numerically |
| `tools/rec.swift` | drop-free CoreAudio recorder (compiled on demand). Exists because the ffmpeg/avfoundation path **drops samples** — measured, do not go back to it |
| `tools/ot_midi.py` | drives the Octatrack over CoreMIDI from the CLI: CC, notes, raw bytes — what makes hardware sweeps scriptable |
| `tools/hw_sweep.py` | scripted sweeps: MIDI steps + capture + per-step metrics in one process |
| `tools/level_cap.py` | quick capture with peak/RMS/crest/clip-run reporting per channel |
| `tools/gain_pass.py` | gain-matches a whole project bank-by-bank over MIDI |
| `tools/ot_project.py` | reads (and carefully writes) Octatrack project/bank files on the CF card — reverse-engineered format |
| `tools/decode_tempo_probe.py` | decodes captures from the tempo probe build, which streams the DSP's parameter staging block out through the audio |

## Conventions the tooling enforces

- **Measured beats inferred**, and the tools say which they are producing.
  Confidence markers (✅/🟡/⚠️) follow `docs/CHIP.md`'s scheme.
- **Silence is a failure, not a pass** — the measurement tools check for it
  first, because a silent render scores perfectly on most metrics.
- **Entry points come from the dispatch tables, never hardcoded** — code
  moves; a stale address silently measures the wrong routine.
- **Builds are reproducible and fingerprinted** — same tree, same flags,
  same bytes; the render cache refuses to serve stale audio.
- Several tools cite probes (`dsp/baseprobe.asm`, `dsp/r7probe.asm`, …)
  that were pruned from the tree; they live in git history and the
  citations are the provenance of measured numbers — recover with
  `git show <sha>:dsp/<name>.asm` (see `CLAUDE.md` §History).
