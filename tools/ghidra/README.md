# Ghidra: the MAIN OS and both DSP payloads, one project

```bash
make ghidra-install GHIDRA=~/ghidra_12.1.4_PUBLIC   # once: a copy with the processor modules below
make ghidra GHIDRA=out/ghidra/ghidra_12.1.4_PUBLIC-octabam [IMAGE=out/mainos_bus.bin]
python3 tools/ghidra/ot_ghidra.py import --ghidra DIR [--project DIR] [--only DSP_A,DSP_B] [--image [PATH]] [--no-analysis]
python3 tools/ghidra/ot_ghidra.py layout [--image [PATH]]  # the memory images + layout files only, no Ghidra
```

Needs `out/raw/section_3_MAIN_OS.bin` (`make os && make recon`) and a
JDK that your Ghidra accepts. The project is `out/ghidra/octatrack.gpr`. A
worktree under `.claude/` gets it in the temp directory instead, because
Ghidra refuses any path element that starts with `.`. Each program's
headless log is `out/ghidra/<program>.log`. `DEBUG=1` streams Ghidra's
output and lists every layout directive as it is applied.

| program | language | what is in it |
|---|---|---|
| `MAIN_OS` | `68000:BE:32:Coldfire_EMAC_frac`, else `68000:BE:32:Coldfire` | the image at `0x40000400`; the board map (`ARCHITECTURE.md` section 7) as blocks, including `0x48000000`, the uncached view of SDRAM, as an empty block of its own (a byte-mapped copy doubled the analysis); the peripheral registers the docs read; the interrupt handlers (`KERNEL.md`); the DSP boot routines; the four DSP blobs marked as data; every stock address a module names with `.set`/`.equ` (the source file is in a repeatable comment) |
| `DSP_A`, `DSP_B` | `DSP56300:LE:24:default` | P/X/Y as the ColdFire uploads them (`dsp_modmap.py`), each load record's source address commented; internal memory to the default map's extents (P 8K, X 36K, Y 48K words, `CHIP.md` section 3); the shared window `0x30000`–`0x3FFFF` with both bootstraps and payload A's shared records, X and Y mapped onto P there (they alias on the chip); the X/Y I/O registers; the vectors; both dispatch tables with every effect's init and process named (`DSP.md` section 5); payload A's named routines |
| `REMIX` (with `--image`/`IMAGE=`) | as `MAIN_OS` | a built image (default `out/mainos_bus.bin`) under `MAIN_OS`'s layout; the bytes the build appends after the OS are one data block (`build_appended`), and each runtime in the loader's table is unpacked (`depack.py`) into its own block `DRAM_RUNTIME_n` at the address the loader copies it to, so a module's calls into stock (and the stock callers it detours) are in one listing |

Nothing from the image is committed. The tool reads your image, writes
`out/ghidra/load/`, and `OtLayout.java` applies the layout as
`analyzeHeadless`'s pre-script, so analysis starts from the right map.
`OtReport.java` prints each program's function, instruction and
error-bookmark counts. A layout file is plain text: add a finding to the
tables in `ot_ghidra.py` and re-import.

## The processor modules

Stock Ghidra has no DSP56300 and decodes the ColdFire's EMAC wrongly. Both
are here, in the form they are offered to Ghidra upstream (`roblg/ghidra`
#3 and #2):

| here | what it adds |
|---|---|
| `processors/DSP56300/` | the DSP56300 processor: P/X/Y word spaces, parallel moves, hardware loops, a loop-end analyzer; languages `DSP56300:LE:24:default` (linear AGU, what the import uses) and `DSP56300:LE:24:modulo` (every address update through the user op `agu_modulo`) |
| `patches/coldfire-emac.patch` | ColdFire ISA_C and EMAC decoding and semantics in `Ghidra/Processors/68000`, and the `68000:BE:32:Coldfire_EMAC_frac` variant (`MACSR` fractional, as this firmware runs it) |

`make ghidra-install GHIDRA=<stock install>` (`install.sh`) never touches
the stock install. It copies it to `out/ghidra/<name>-octabam`
(`GHIDRA_DEST=` to choose), applies the patch, adds the module without its
`build.gradle` (the distribution's `support/gradle` includes every
directory holding one, and the module's needs a source tree), compiles
both processors' SLEIGH with the release's own compiler and the loop-end
analyzer against the release's jars (`lib/DSP56300.jar`), and builds the
native decompiler with the release's gradle wrapper
(`support/gradle/gradlew buildNatives`) when the release has none for the
machine (the platform of the JDK's `java`, as Ghidra picks it, so an
x86_64 `bash` under Rosetta still gets `mac_arm_64`). The 12.1.4 release ships them for `linux_x86_64` and
`win_x86_64` only; without one no DSP function decompiles and MAIN_OS
drops to 2,147 functions / 181,378 instructions, two of the three callers
of `0x40054cd8` missing (measured without one in
sambanks/octabam#483). That build needs
a C++ toolchain (Xcode's command line tools on macOS) and the network for
gradle, and takes about two minutes. It needs a JDK 21+ (`JAVA_HOME`).
`DEBUG=1` streams every step; otherwise the output goes to
`<dest>.install.log`.

It is written against the 12.1.4 release, whose `68000.sinc` and
`68000.ldefs` are byte-identical to the patch's base; another version is
attempted only if the patch applies. With a stock Ghidra the MAIN OS still
imports, as `68000:BE:32:Coldfire`, and the DSP programs are skipped with a
message.

Not here: the decompiler printing `__Y(*p)` for a dereference outside the
default data space (`roblg/ghidra` #1, `decomp-space-qualifier`). It changes
the native decompiler, so it waits for upstream; without it X and Y reads
print as plain `*p`.

## What the import prints

With `make ghidra-install` on Ghidra 12.1.4 and OS 1.40C, each program
reports 0 layout warnings. The error bookmarks are flows into memory the
image does not hold:

| program | functions | instructions | error bookmarks |
|---|---|---|---|
| `MAIN_OS` | 2,176 | 191,064 | 9: calls into flash (`jsr 0x0000eae0`) and into `0x40000000`, below the image |
| `DSP_A` | 109 | 6,921 | 1: `P:0`'s `jmp $fff000`, the boot ROM |
| `DSP_B` | 102 | 6,377 | 1: the same |

Measured 26 Sep 2026, macOS arm64, Ghidra 12.1.4 (the release zip, the
decompiler built by `install.sh`). Every non-thunk function decompiles
(20 s timeout each): 107 in DSP_A, 100 in DSP_B, 2,171 in MAIN_OS. The same
programs on Ghidra 12.3-DEV with the `roblg/ghidra` branches merged
(26 Sep 2026): MAIN_OS 2,175 / 190,956 / 9, DSP_A 109 / 6,921 / 1, DSP_B
102 / 6,377 / 1.

`IMAGE=out/mainos_bus.bin` after `make check` (the shipping build,
`bamsep26` BUILD 79) adds `REMIX`: 2,228 functions, 192,175 instructions,
the same 9 error bookmarks as MAIN_OS, 0 layout warnings. Its one DRAM
runtime (2,612 bytes at `0x40a955e0`, where scenes-p2's detour at
`0x4000cf40` jumps) holds 18 functions / 497 instructions. The page-1
writer `0x40054cd8` has the three stock callers (`0x40062530`,
`0x400625aa`, `0x400a15f0`) and a fourth, `0x400d75d6`, in the ColdFire
cave the build fills (`0x400d6b00`..`0x400d7c3c`, `tools/remix/state.py`).

## Reading the DSP programs

- Addresses are words: `P:0x7d1` is word `0x7d1`. The DSP is little-endian,
  three bytes per word, as the payloads store it.
- `X:0x30000` is `P:0x30000` (byte-mapped). A write through Y shows up in
  P's listing at the same address, which is what the chip does.
- The DSP56300 names in the listing come from the DSP56362 register map,
  the same names `dsp56kDisassemble` prints. The DSP56720's ESAI and host
  port read correctly under them (`DSP.md` section 6c); a register the docs have
  not read is unverified on this chip.
- The vectors are labelled `vec_XX` and not named. The DSP56720's vector
  map differs from the DSP56362's: the live vectors are `0x10`–`0x1c`, the
  host-port handlers (`DSP.md` section 6c).
- `fx_null_init`/`fx_null_process` is the passthrough every unused id
  points at, DELAY (`0x08`) included: the stock DELAY runs on the ColdFire.

## Export for the symbol database

`OtExport.java` is a post-script beside `OtReport.java`: it writes `out/ghidra/symbols.tsv` (`cf`, address, size,
name) for each function of MAIN_OS or REMIX and `xrefs.tsv` (`cf`, from, to, kind) for the references to each
function's entry. `python3 tools/build/symdb.py build --ghidra` reads them (`docs/contributing/TOOLING.md`).
`ot_ghidra.py import` runs it after `OtReport.java` on MAIN_OS and, with `--image`, REMIX (the last one imported leaves the files; `--no-analysis` skips it). `OtCode.java` follows it on MAIN_OS and writes `out/ghidra/code_runs.tsv`: the address runs of instructions the analysis found, no bytes (`tools/build/cf_code_runs.tsv` is the committed copy the ColdFire form gate reads, `docs/contributing/TESTING.md`). Run in Ghidra 12.1.4 (this machine, 15 Nov 2026), MAIN_OS: 2,179 functions and 13,654 references to them; `symdb.py build --ghidra` loads them and `sym.py --callers 0x4001ffe4` lists the 43 references to the stock logger.

