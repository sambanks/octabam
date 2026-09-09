# The plan: one toolkit for the Octatrack's OS mods

**This is the cold-start document.** It says what octabam is for now, where
that stands, what is measured about the ground the work happens on, and
what is next, in order. `docs/remixer/PLACEMENT.md` is the architecture
record for *where code goes*; `docs/history/PLAN_EFFECTS.md` is the plan
this file replaced — the DSP-effects programme, feature-complete and
hardware-confirmed, whose open items are still open and still listed there.

---

## The programme

Several people modify the Octatrack's 1.40C firmware, and they all started
from the same reverse-engineering — this repository's. Each went their own
way with their own build: a Python encoder writing fixed addresses
(midisc), a Rust patcher with a compiled runtime in DRAM (Octakit), GNU
`as` plus hand-placed caves (octamax), a preference generator (octa-bt-pt).
Each picked the same few kilobytes of free ROM independently, so no two of
them can go on one unit, and none of them can be *composed*.

octabam becomes the thing they compose in. **A mod is a module; a remix is
a selection of modules; the build turns a remix and the user's own copy of
the stock OS into one image.** The build places code, wires hooks by
symbol, refuses collisions by name, and re-derives every identity an
author has ratified, so a port is a *proof* — the author's own build and
ours agree byte for byte — not a copy. Nothing compiled is ever
distributed: everyone builds from their own 1.40C, and the repo carries
none of Elektron's bytes.

Sam's constraints, kept: the module format is octabam's (nobody's private
build convention is pulled in "unless there is no other way"); the TUI
remixer stays; where someone else's mechanism is better it is adopted —
Em's loader-appended DRAM runtime is now octabam's own large-payload
placement, and the m68k-elf toolchain is a standard dependency.

## Where it stands (10 Sep 2026)

**Built, gated, unflashed.** Every gate below is local: the ColdFire port
(`tools/emu/ot_emu`) boots the built image, the bit-identity gate proves
the build changed nothing for the twenty-six existing configurations, and
each port's own oracle holds. **Nothing from the new pipeline has been
written to a unit yet.** The authors' own builds are what has run on
hardware.

| module | from | what it is | proof |
|---|---|---|---|
| `midi-scenes` | [bkkbrls-del/midisc](https://github.com/bkkbrls-del/midisc), via Sam's fork branch `octabam-gas` (submodule) | MIDI-driven scene locks: seven GNU-as units in DRAM, 35 detours, 2 pokes; 207 B changed inside the OS | every region assembles to his encoder's bytes at his addresses; boots under the port, his hooks run from DRAM |
| `octakit` | [emuyia/ems-octakit](https://github.com/emuyia/ems-octakit) (submodule) | Em's Octakit: 256 Kits per Project, a 150 KB runtime in DRAM | stock + her writes + her append == her own `output.os`; her runtime rides octabam's loader and reads back byte-identical at boot |
| `lofi-amf-fix` | [bryantysinger/octa-bt-pt](https://github.com/bryantysinger/octa-bt-pt) | the one objective bug fix in his tool: LO-FI's AMF `mpysu` → `mpyuu`, two DSP words | both words disassembled against stock; composes with everything |
| `hello-dram` | here | one DRAM unit, no hooks — the loader's canary | boots; window equals the linked image |
| octamax | [mxldyn/octamax](https://github.com/mxldyn/octamax) | **deferred** on branch `octamax-deferred` (commit `d952976`): ported (six units, all reproduce his build), then parked pending a conversation Sam is having with the author. Not on the main line; do not contact him. | — |

octabam's own modules — the bus engines, the inserts, the ColdFire patches
(tempo sync, the bus screen, CC→page 2) — are unchanged and still listed by
`make modules`; the effects programme's state is in `docs/history/PLAN_EFFECTS.md`.

What the platform now has, all in `tools/remix/`:

- **`schema.Linked`** — a GNU-as unit the build assembles and links where
  *it* places it; **`Detour`** (jmp / jsr / lea, asserted against stock,
  padded), **`Poke`**, **`TableGrow`** — the OS-image edits, wired by symbol.
  `Linked(dram=True)` puts the unit in the platform runtime.
- **`schema.Runtime`** — a recipe-built DRAM runtime (Em's `firmware.json`),
  compiled, packed and identity-checked by `runtime_build.py`.
- **The loader** (`loader.S`, derived from Em's with attribution) at
  `0x4010fdf0`, carrying an N-payload table: octabam's runtime and Octakit's
  each staged, hash-gated, depacked with the firmware's own aPLib routine,
  and verified after the depack; a mismatch hangs the boot rather than
  running half a runtime. `platform_build.py` links every DRAM unit in the
  remix as one image at `0x47fdb000`.
- **CavePatch "source is the truth"** — every ROM cave with a `.s` is
  assembled and linked at its resolved address and *those* bytes are
  written; `pinned` / `reference(addr)` is the ratified oracle.
- The **ledger** sees all of it (detour sites, pokes, runtime writes, one
  runtime per image), and `make modules` prints the pairwise
  **compatibility matrix** from the same call the build makes.
- The **ColdFire port** models the uncached SDRAM alias, which is what made
  the DRAM measurement below possible; `tools/verify/verify_dram_boot.py`
  (in `make verify`) boots every DRAM remix and checks each window.

## The ground: what is actually free

Every number here is from `docs/remixer/PLACEMENT.md`, measured under the
port on 9 Sep 2026 unless marked.

| where | how much | status |
|---|---|---|
| **ROM**: the OS image's free zero runs (`0x400c45b0`, `0x400d24d0`, `0x400d2ee6`, `0x400d64da`) | ~8.4 KB total, shared by every ROM-resident cave and the chooser clones | ✅ measured; the scarce thing every author fought over |
| **DRAM window** `0x47fc7410..0x47fe0000` | ~99 KB never written in any phase measured; Octakit's stage takes 73 KB of it when she is in the image, leaving ~28 KB for octabam's runtime beside her; ~99 KB alone | ✅ measured (boot, project load, 300 frames of play); the recorder and caches not exercised |
| **Octakit's window** `0x45d0dde0..0x46025de0` | 150 KB, zero-filled by stock at project load; her post-clear relocation re-depacks it | ✅ measured, hers |
| **The delay rings** `0x47502c10..0x47fc7410` | 10.8 MB — the eight per-track Echo Freeze rings (Bryan T: base `0x4F502C10` = the uncached alias, 1,411,200 B × 8 = `0xac4400`, which lands 1 KB short of the clear's end), always allocated, cleared through the alias at boot instruction ~42 M | ✅ measured + ✅ his; **not free** — the "8.8 MB at 0x47700000" reading is retracted |
| `0x46000000..0x47502c10` | ~21 MB, outside both big clears | ⚠️ **unmeasured**; probably the sample pool. Not to be used before a run that loads samples and records has been watched |

## Work order

1. **Flash the DRAM platform, cheapest claim first.** `hello-dram` (one
   unit, one boot-site poke: does the loader run on silicon and does the
   unit boot on?), then `midi-scenes` (his features through our loader —
   he can compare against his own build on his own unit), then `octakit`
   (her runtime through our loader; she has the project-migration test
   set). Bump `BUILD`, stamp projects, `docs/remixer/FLASHING.md`.
2. **Detour chaining** for the two stock routines three authors hook:
   `apply_part` entry `0x40009094` (midi-scenes, octakit, octamax) and the
   scene-parameter writer `0x40052ae8` (octakit, octamax). Until then
   Octakit and midi-scenes are mutually exclusive — and note the second
   reason: Parts versus Kits. His code addresses the Part window; hers
   replaces it. A Kits-aware midi-scenes is his and Sam's to write.
3. **MB-scale DRAM.** Two candidate mechanisms, neither measured: (a) a
   remix that gives up the stock DELAY (off both choosers) detours its
   frame routine (`0x400031a0`) so the rings are never touched, and
   inherits 10.8 MB — a small mechanism, if the routine's other duties
   allow it; (b) Em's wipe-and-reload generalised for a window inside a
   region stock clears. (a) first; it is one detour and one measurement.
4. **Upstream.** The PR to bkkbrls-del once he has finished his own
   changes (rebase `octabam-gas`, then `tools/gas_port.py` + `gas/` to him).
   An optional tidy PR to Em splitting her loader infrastructure so the
   shared loader is one file in one place. Neither blocks anything here.
5. **The remixer TUI** shows ColdFire modules as first-class rows with
   the matrix's verdicts at the keystroke (it already runs the ledger; the
   view is what lags).
6. **Measure `0x46000000..0x47502c10`** with samples loaded and the
   recorder running, under the port, before anyone places there.
7. **octamax**, if and when Sam confirms with the author: the branch is
   ported and gated; it rebases.

## Gates and rules

- `make check` is the floor, for every remix you touched: `make check
  REMIX=<name>`. It builds, prices cycles, runs the ledger selftest, the
  menu verification, each port's oracle and the boot verifier.
- **A change to the BUILD proves it changed nothing**: `scripts/refhash.sh
  save` on a tree you trust, then `check` — 26 configurations, artifacts
  and build reports, bit-identical. Every step of the platform work landed
  under it.
- **The author's build is the oracle.** A port is done when their output
  and ours agree byte for byte (or, where the build places code elsewhere,
  when each unit re-linked at their address matches). `pinned`,
  `reference(addr)`, `Linked.reference` and Em's recipe identities are the
  four forms of the same rule.
- **Measured beats inferred, and says which it is.** Confidence markers as
  in `docs/firmware/CHIP.md`; retractions propagate to every document that
  repeated the number.
- **Never an Elektron byte in the repo** — not an image, not a slice, not
  a `.syx`. `.incbin` from the user's own stock image at build time is the
  pattern (Octakit's 411 routines).
- The DSP-side gates and rules (`verify-roll`, `verify-delay`,
  `verify-bus`, stamping projects after a slot change) are unchanged:
  `docs/history/PLAN_EFFECTS.md` "Gates and rules".

## Build commands

```sh
make modules                  # the index, the compatibility matrix, the remixes
make bus REMIX=ported         # build a selection (default: bamsep26, the rig)
make check REMIX=midi-scenes  # everything that can be checked without hardware
make image REMIX=octakit BUILD=101   # repack as a flashable .bin, version-stamped
make remix                    # the TUI remixer
scripts/refhash.sh check      # after a change to the build itself
```
