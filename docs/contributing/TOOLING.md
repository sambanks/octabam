# The tooling, end to end

What each tool is and where it sits in the pipeline. The audition and
measurement harness in depth: `tools/harness/README.md`.

The pipeline, left to right:

```
acquire ──► unpack ──► understand ──► build ──► hear/measure ──► verify ──► flash ──► capture
scripts/     scripts/    tools/build    tools/build tools/harness   tools/      docs/guide/ tools/hw
fetch-os     analyze     dsp_modmap     build_bus   dsp_host +      verify/*    BUILDING.md capture_hw
                         disasm         make image  tools/emu       cycles                  ot_midi …
```

`make help` lists the entry points; almost everything below is behind a make
target.

## Where the tools live

`tools/` is grouped by what a tool is for. Every group directory is on
`sys.path` for every tool (`tools/toolpath.py`), so tools import one
another by bare name wherever they sit; a new script opens with the one
line `verify_dram_boot.py` does.

| directory | what is in it | its doc |
|---|---|---|
| `tools/remix/` | **the toolkit**: the module schema, the registry, the ledger, the stock-effect list, the loader (`loader.S`), the DRAM platform (`platform_build.py`), the payload packer (`pack.py`), the TUI (`app.py`), auditioning, the index and the selftest | [`tools/remix/README.md`](../../tools/remix/README.md) |
| `tools/build/` | **the build** (`build_bus.py`) and the tools that understand the OS layout: the DSP load map, disassembly, reachability, the ELUP/`.bin` codecs, label and formatter emitters, cycle pricing | section 4 below |
| `tools/verify/` | **the gates**: one `verify_*.py` per property, run by `make verify` | [`TESTING.md`](TESTING.md) |
| `tools/harness/` | **hearing and measuring the DSP side** locally: the emulator harness (`dsp_host/`), `send_probe`, `render_reverb`, `rig_render`, `pressure`, `stress_project` | [`tools/harness/README.md`](../../tools/harness/README.md) |
| `tools/emu/` | **the ColdFire emulators**: the headless machine port (`ot_emu/`, C++) and the Unicorn bring-up (`emu_bringup`, `emu_card`) | [`tools/emu/README.md`](../../tools/emu/README.md) |
| `tools/panel/` | **the virtual front panel** over the port: browser and macOS app | [`tools/panel/README.md`](../../tools/panel/README.md) |
| `tools/ghidra/` | the Ghidra project import and the DSP56300 SLEIGH spec | [`tools/ghidra/README.md`](../../tools/ghidra/README.md) |
| `tools/hw/` | **the unit and its card**: MIDI control, capture, sweeps, project files, MIDI flashing | section 7 below |
| `tools/patches/` | local patches to the vendored toolchains (dsp56300, elektron-firmware-tool, unicorn) | section 1 below |

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

Idempotent. What to install before it: [BUILDING.md section 0](../guide/BUILDING.md#0-what-you-need). It builds:

| tool | from | what it is |
|---|---|---|
| `dsp_asm` | `vendor/dsp56300` | the DSP56300 assembler. It mis-encodes some instructions silently (`AGENTS.md`'s trap list). `tools/patches/dsp56300.patch` adds the chip's one-word displaced move (displacement −64..63, data-ALU register); a word or cycle figure recorded before 14 Sep 2026 counts such a move as 2 |
| `dsp_host` | `tools/harness/dsp_host/` (staged into `vendor/dsp56300` and built there) | the emulator harness written here: runs assembled effects on the dsp56300 emulator core. `tools/harness/README.md` |
| `emu_bringup.py` | `tools/emu/` | Tier-0 ColdFire bring-up: boots the MAIN OS image on Unicorn's CFV4E core to the RTOS handoff (the remixer's emulator view). Needs `unicorn`: `make emu-setup` (uv, the `emu` extra). `tools/emu/README.md` |
| `ot_emu` | `tools/emu/ot_emu/` (`make emu-cf`) | the headless C++ port of the machine: boots the built image, loads a project from a staged card, runs the sequencer and both DSP cores. `tools/emu/README.md` |
| `ot_brain` | `tools/hw/ot_brain.py` | brain files (`.work`, `.strd`, `.brain`): `dump` to JSON, `build` from JSON (a record it cannot read kept as its bytes, so a round trip is byte for byte), `pair` (what the core does with a directory's `.work` / `.strd`; `docs/proposals/BRAIN.md` section 6.2) |
| `ot_spec` | `tools/hw/ot_spec.py` | one JSON spec over a project's parts and patterns: `apply` (FX ids by module name, every knob by name, machine type, part names; per pattern track: length, scale, trigs, locks on every page by knob name — PLAYBACK, LFO, AMP, FX1, FX2 — with `clear`; the lock-trig mask follows), `report` (the same shape back), `diff` (two projects, field by field); checksum + read-back on `.work` and `.strd` |
| `ot_bank` | `tools/hw/ot_bank.py` | the bank file's pattern records: `report` lock counts per page, `strip --pages fx1,fx2` clears them in every pattern (the stamper never touches patterns) |
| `verify_character` / `verify_spectrum` / `verify_modulation` | `tools/verify/verify_<module>.py` | the module rendered through `dsp_host` on the audition's scratch image against predictable arithmetic or a float reference (in `make check` since 16 Sep 2026; Character's master path reads the shipping build) |
| `verify_spectrum_ident` | `tools/verify/verify_spectrum_ident.py` | bit-identity of a rewritten Spectrum against a saved reference (`make verify-spectrum-ident SAVE=1`, then without) |
| `verify_usb` | `tools/verify/verify_usb.py` | the built image enumerated as a USB device under the port: Elektron 1935:0002, the MSC interface, INQUIRY and its CSW over EP1, no uninitialised queue head (`make verify`, 3 s) |
| `usb_host` | `tools/harness/usb_host.py` | the scripted USB host for the port's bench (`ot_emu --usb-host SOCKET`): enumerate, mass storage, USB-MIDI in/out, drain an isochronous endpoint; octemu's protocol |
| `verify_set` | `tools/verify/verify_set.py` | a real project on the built image under the port: ids, page-2 delivery, chain audio, the main out (`OT_PROJECT=<dir> make check`, or the path in `~/.octabam_project`) |
| `elektron-firmware-tool` | `vendor/elektron-firmware-tool` (patched) | packs/unpacks Elektron's OS container formats |

The disassembler from the same dsp56300 project is the other half:
disassemble what you assemble, because the assembler's failure mode is
clean assembly of wrong machine code. Every `build_bus.assemble()` call
runs `dsp_asm -list` against an independent `dsp56kDisassemble` decode of
the same bytes and compares mnemonics (Jannik Aßfalg, PR #380, 22 Sep
2026): a mismatch fails the build. `mpy` encoded as `mpysu` is the one
mismatch the shipping code carries on purpose (AGENTS.md: second operand
always non-negative at every site); those sites are counted per module in
`build_bus.MPYSU_AUDITED`, a count that differs from the table fails the
build with the site list, and a matching count prints nothing. A build
under a flag that substitutes source (`PROBE`, `NOSHIM`, `MARKER`, a
candidate engine) prints its counts instead of enforcing the table.
`NOROUNDTRIP=1` disables the check. It cannot see a resolver picking the
wrong ADDRESS for a symbolic operand (both tools decode the bytes dsp_asm
wrote), the label-prefix trap: that one is still read by hand.

## 2. Acquiring and unpacking an OS

No Elektron binary lives in this repository; every build derives from the
user's own copy.

| tool | what it does |
|---|---|
| `scripts/fetch-os.sh` (`make os`) | downloads the official OS from Elektron's site and prints its SHA256 |
| `scripts/analyze.sh` (`make recon`) | static recon: entropy, binwalk, strings, container unpack → **`out/raw/section_3_MAIN_OS.bin`**, the decompressed 1.1 MB ColdFire image every build script reads as its base |
| `tools/build/bin_decode.py` | offline decoder for the `.bin` (ELUP) transport: strips the header, undoes the XOR-with-feedback obfuscation, verifies the additive checksum the firmware's own update validator checks |
| `tools/build/make_bin.py` | the reverse: wraps a patched container into an ELUP `.bin` for the CF-card OS UPGRADE path |
| `tools/build/entropy.py` | sliding-window Shannon entropy scanner |
| `tools/build/find_base.py` | recovers a raw image's load address by pointer→string correlation (`0x40000400`) |

The container formats themselves (ELUP/ELEK/aPLib) are documented in
`docs/firmware/ARCHITECTURE.md` section 3.

## 3. Understanding the firmware

Two instruction sets, two toolchains:

| tool | side | what it does |
|---|---|---|
| `tools/build/dsp_modmap.py` (`make modmap`) | DSP | the module load map: which bytes of the image load to which DSP address in which memory space. Also produces the `.mem` dumps `dsp_host` boots |
| `tools/build/dsp_disasm_all.py` | DSP | disassembles every P module of both payloads at its load address: one `.asm` per payload plus per-module binaries |
| `tools/build/dsp_reach.py` | DSP | control-flow reachability sweep from the real entry points (dispatch tables, vectors, bootstraps) |
| `scripts/disasm.sh` (`make disasm`) | ColdFire | radare2 on the decompressed MAIN OS with the right arch and base (m68k BE @ `0x40000400`); `emac` uses objdump, the only decoder that reads the ColdFire V4e extensions |
| `tools/ghidra/ot_ghidra.py` (`make ghidra GHIDRA=<dir> [IMAGE=out/mainos_bus.bin]`) | both | one Ghidra project holding the MAIN OS and both DSP payloads, each with its memory map, peripheral names and vectors, and the dispatch tables' effects named, plus a built image with its DRAM runtimes unpacked (`tools/ghidra/README.md`). The DSP programs need the DSP56300 processor module in `tools/ghidra/processors/`: `make ghidra-install GHIDRA=<stock 12.1.4>` makes a copy of your Ghidra with it and the ColdFire EMAC patch |
| `tools/build/where.py` (`make where A=<addr> [N=bytes]`) | ColdFire | every doc paragraph citing that address (file:line first), the nearest other cited addresses, and a `scripts/disasm.sh emac` window, in one command (Jannik Aßfalg, PR #380). The docs are scanned on each call; there is no index file to keep in step, and a finding about an address goes in its topical doc |

### Disassembling the ColdFire ✅ (Bryan T, 30 Aug 2026; re-read here)

`objdump -m m68k:5407` mangles EMAC regions; `m68k:547x` / `m68k:cfv4e`
(the same decoder) is required. radare2's m68k backend cannot decode
`mvs`/`mvz`/`mov3q`/EMAC and, assuming 2-byte opcodes, reads each
extension word as an instruction: 6,757 undecodable instructions below
`0x40098000`, 4,543 of them longer than two bytes (`mvz` 4,539, `mvs`
1,834, EMAC 791; EMAC clusters: `0x40001000` 48, `0x40003000` 62,
`0x40004000` 50, `0x40007000` 98, `0x4000c000–d000` 47). At `0x40003664`:

| | first four instructions |
|---|---|
| `m68k:547x` | `msacl %d0,%a1,%acc2` · `msacl %d0,%a2,%acc3` · `macl %d2,%a1,%a5@+,%a1,%acc0` · `msacl %d5,%a1,%a0@+,%a1,%acc0` |
| `m68k:5407` | `msacl %d0,%a1` · `.short 0xa4c0` · `btst %d4,%a0@` · `macl %d2,%a1,%a5@+,%a1` |
| radare2 | `invalid` · `btst.l d4,(a0)` · `invalid` · `btst.l d4,(a0)` |

`scripts/disasm.sh emac <addr> [bytes]` uses `m68k-elf-objdump -m
m68k:cfv4e`. All 90 ColdFire addresses our docs cited in
`0x40000400`–`0x4000dfff` were re-read with `cfv4e` (30 Aug 2026); no
conclusion changed (the four r2-unreadable sites: `0x4000b786` `mov3ql
#-1,%a1@+`, `0x4000c24a` `mvsb %a3@(0,%d1:l),%d0`, `0x40003664`/`0x40003900`
EMAC). The menu and descriptor work was Ghidra; the MIDI work was objdump
`cfv4e`. The Unicorn bring-up needs the CFV4E model for the same reason:
the default m68k core does not decode this CPU.

## 4. Building firmware

`tools/build/build_bus.py` is the builder (`make bus` = `XBUS=1 SPEC=1`).
It builds a remix: a named selection of modules (`make bus REMIX=<name>`,
no default; `make modules` lists the modules and the remixes,
`make remix` composes one interactively). Each `modules/<name>/manifest.py`
declares one contribution against `tools/remix/schema.py`, and
`tools/remix/ledger.py` refuses a selection whose modules collide.
`docs/contributing/MODULES.md` is the contributor guide. The builder assembles
the selected effects, places them into each payload's donor region in
priority order, wires the dispatch tables, patches the ColdFire-side menu
descriptors, installs caves, detours and the DRAM platform, and
census-checks itself. It is driven by env flags (`DEV`, `NOSHIM`, `MODE`,
`DNOTE`, `TPROBE`, …; grep `environ` in the file); the render cache
fingerprints every one (`tools/harness/README.md`). `make image` repacks
the result into a card-flashable `.bin` with the build number stamped into
the OS version string. `docs/guide/BUILDING.md` before writing to
hardware.

## 5. Hearing and measuring locally

Render on the desktop at ~6× real time instead of flashing.
`tools/harness/README.md` in depth:

| tool | what it does |
|---|---|
| `tools/harness/dsp_host` | the emulator harness: boots a payload dump (both payloads, `-memB`, shared window shared), calls effects through the recovered ABI, captures audio, polices memory, meters instructions per block |
| `tools/harness/rig_render.py` (`make render-rig`) | all eight tracks locally on both cores, FX1→FX2 chained per track, ids and knobs from a project part or by name, stems in, per-track + mix wavs and `meter.txt` out |
| `tools/verify/verify_twocore.py` (`make verify-twocore`, in `make check`) | the two-core gate: the servers on their real cores render bit-identical to the DEV hatch, and under four interleave skews |
| `tools/verify/verify_onebus.py` (`make verify-onebus`, in `make check`) | the one aux bus on both cores: the chain, each host's print, WET passthrough (sample-exact), the track-8 send refusal, a stored RET byte inert, stations without sends, four skews |
| `tools/harness/render_reverb.py` (`make reverb IN=..`) | wav → BusVerb → wav, knobs by name, sweeps, wet-only |
| `tools/harness/send_probe.py` (`make render`, `make render-delay`) | renders a SEND→bus→server path and measures it numerically; `--direct` puts audio through one module on its own track, the way an insert is rendered |
| `tools/harness/abkit.py`, `station_laws.py`, `pressure.py`, `port_compare.py` | A/B kits for voicing by ear; a station's control laws read off noise; every selectable layout priced and the dearest rendered; the harness against the ColdFire port on one part |
| `scripts/make_test_audio.py` | synthesises the standard audition material into `out/test_audio/` |

## 6. Verifying

`make check` is the floor for any change; `docs/contributing/TESTING.md` is the
mechanism (the two halves, module gates, `make reach`, shards, `make accept`,
CI). The family, and what each proves:

| tool | proves |
|---|---|
| `tools/build/cycle_count.py` (`make cycles`) | static per-sample cycle count of every module in the selected remix, plus the worst load one core can be asked for |
| `tools/verify/verify_roll.py` / `verify_delay.py` | an alternate reverb / delay engine is bit-identical to the shipping one |
| `tools/verify/verify_bus.py` (`make verify-bus`) | a bus-layout change is behaviour-preserving over its case list (34 layouts on 28 Sep 2026), stamp-edit-compare (`modules/send/README.md`) |
| `tools/verify/verify_menu.py` | the built choosers and descriptor clones against the chooser mechanism decompiled from the firmware, including formatter vs count and the name-field lengths |
| `tools/verify/verify_slots.py` | static dead-store check on the reverb's r7 state block |
| `tools/verify/verify_midi.py` | the note→PITCH interval path, locally, via a build override |
| `tools/verify/verify_burn.py` | the cycle-burn probe is the shipping engine plus an inert knob |
| `tools/verify/verify_dram_boot.py` | every DRAM remix booted under the port and its window read back |
| `tools/verify/verify_kits.py` | KITS under the port: staging, LOAD/SAVE KIT, the files, migration and Octakit import |
| `tools/verify/verify_dirtystate.py`, `verify_initregs.py`, `verify_replaces.py`, `verify_labels.py`, `verify_modenames.py`, `verify_hidden.py`, `verify_grains.py`, `verify_twocore.py`, `verify_onebus.py`, the per-module render gates | every module silent from a garbage block; no init writes r1; no stock effect hijacked; selects print their words on the emulated firmware; the mode formatter renames; hidden engines; the grain lever; both cores; the bus |
| `tools/remix/selftest.py` | the resource ledger catches every collision it claims to, and every shipped remix is clean (part of `make check`) |
| `scripts/refhash.sh` | a change to the build (not a module) changed nothing: 24 configurations, artifacts and build reports, bit-identical; save a baseline on a tree you trust first |

## 7. Hardware measurement and control

For the claims the emulator structurally cannot make (`tools/harness/README.md`,
last section), the hardware capture setup — protocol in `docs/history/CAPTURE_18AUG.md`:

| tool | what it does |
|---|---|
| `tools/hw/capture_hw.py` | records the unit through an audio interface and analyses the capture numerically |
| `tools/hw/usb_counters.py` | USB AUDIO's ring counters (`--in`: USB AUDIO IN's) over their vendor requests, once or `--watch` |
| `tools/hw/usb_probe.py` | a host session (sustained tone or open/close churn) against a unit on `usb-io`, both rings' counters polled while the stream is open, a verdict and a JSON report |
| `tools/hw/sos_capture.py` | the sound-on-sound loop sample-exact: a fixture project, a tone + sample-index-ramp signal, a capture over USB AUDIO IN AB / OUT TRACKS (remix `sos-capture`), the same project and signal under the port, a compare that finds the arm, aligns unit and port and lists where recirculating passes or the two runs differ, and `wraps`, which classifies each wrap (repeat, skip, a sample neither lag explains) from the loop's own lag, on any audio |
| `tools/hw/usb_offset.py` | the offset in samples between two channels of one recording, per click (cross-correlation and onset): a click on one track recorded with `tools/rec`, for example a track channel against MAIN in the twenty-channel stream; `--selftest` |
| `tools/harness/usb_align.py` | the twenty-channel stream's MAIN-to-track alignment under the port: the tone project on a staged card, EP3 IN drained once the sequencer plays, the lag from each tone's phase in its track channel and in MAIN |
| `tools/hw/rec.swift` | drop-free CoreAudio HAL recorder (compiled on demand); the ffmpeg/avfoundation path drops samples |
| `tools/hw/ot_midi.py` | drives the Octatrack over CoreMIDI from the CLI: CC, notes, raw bytes |
| `tools/hw/bcr2000.py` | programs a Behringer BCR2000 for bottleservice: BCL from the manifests (page-1 CCs + CC MAP's page 2), sent over SysEx with per-line acks or written for BC Manager |
| `tools/hw/hw_sweep.py` | scripted sweeps: MIDI steps + capture + per-step metrics in one process |
| `tools/hw/level_cap.py` | quick capture with peak/RMS/crest/clip-run reporting per channel |
| `tools/hw/gain_pass.py` | gain-matches a whole project bank-by-bank over MIDI |
| `tools/hw/ot_project.py` | reads and writes Octatrack project/bank files on the CF card: `stamp-defaults` after a layout change, `set-fx`, `stamp-slot`, `rigproj` |
| `tools/hw/ot_soak.py`, `hw_bus_test.py`, `hw_knob_sweep.py`, `hw_flash7.py`, `midi_flash.py`, `ot_clock.py` | a soak run that reports a freeze or the idle tick; synchronous-detection A/B of a parameter over MIDI; every knob's liveness; the one-aux bus claims driven over MIDI; OS flashing over MIDI; transport |
| `tools/hw/ot_ladder.py` | the LADDER: one configuration per bank in a card project (effect selection without the panel), stepped by program change, each rung measured by level, spectrum and the tail after STOP (bus connected, reverb T60, delay time); `proj` / `run` / `analyse` / `summary` |
| `tools/hw/decode_tempo_probe.py` | decodes captures from the tempo probe build, which streams the DSP's parameter staging block out through the audio |

## Conventions the tooling enforces

- Measured beats inferred, and the tools say which they are producing;
  confidence markers follow `docs/firmware/CHIP.md`.
- Silence is a failure, not a pass: the measurement tools check for it
  first.
- Entry points come from the dispatch tables, never hardcoded.
- Builds are reproducible and fingerprinted; the render cache refuses to
  serve stale audio.
- Comments cite probes and tools that were pruned from the tree
  (`dsp/baseprobe.asm`, `tools/build/build_menu.py`, …); they live in git
  history as the provenance of measured numbers: `git show <sha>:<path>`.
- Every DSP module `build_bus.py` assembles is disassembled and compared
  against its own listing before the build finishes; `make where A=<addr>`
  is the ColdFire-side lookup, on demand.
