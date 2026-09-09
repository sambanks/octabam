# MIDI scenes

MIDI-driven scene locks, built from
[bkkbrls-del/midisc](https://github.com/bkkbrls-del/midisc) — via Sam's
fork, branch `octabam-gas`, checked out here as the submodule `upstream/`
(`git submodule update --init`). `Kind.CF_PATCH`: seven linker-placed
units, 35 detours, two pokes. No DSP code, no menu row.

Octatrack 1.40C has no per-scene parameter lock over MIDI — XF morph reads
one live 8×30 lock table that only the panel can write. midisc adds a
second, addressable table (`MSC`, `scene<<8 | track<<5 | flat`, 4 KB) and
rewires scene hold, XF morph, part save/reload and the scene
clear/copy/paste menu rows to read and write it when a MIDI event — not
the panel — is driving. The panel path is untouched.

## How it is built, and the branch that waits for him

His caves are written in a small Python encoder (`tools/ot3_asm.py`) and
linked into fixed addresses by his `build.py`. The `octabam-gas` branch
adds one file, `tools/gas_port.py`, which drives his own `build_*`
functions with an encoder subclass that also records one GNU-as line per
instruction, writes `gas/*.s` (one per cave region, plus `msc.s` and
`state.s`), then assembles and links every region at **his** address and
compares — all five code regions reproduce his bytes exactly. Cross-cave
references are linker symbols in the `.s` form (his `SENT_*` sentinels,
the addresses `build.py` hands to builders, the MSC table, the four state
bytes), so octabam can place each region where there is room. His
`build.py` is untouched: the `.s` files are generated *from* it. The PR to
him waits until he has finished his own changes; the branch then rebases.

octabam's manifest lists the seven units as `dram=True`: the build links
them together as its **platform runtime**, packs it (~4 KB), appends it
behind octabam's loader and depacks it at boot into the never-cleared
DRAM window above stock's delay-ring clear (`0x47fdb000`, ~13 KB with its
stage copy — `docs/remixer/PLACEMENT.md`). MSC's 0xff fill is just part
of the image, so nothing needs initialising at boot. The 35 hook sites
are wired by symbol with the right instruction for each — `jmp` for stubs
that replay what they displaced, `jsr` for callable ones, one `lea`
operand rewrite, two `bne→bra` flips — and, without Octakit in the image,
the boot site's three-byte redirect into the loader. That is the whole
footprint inside the OS: **207 bytes** (the pinned snapshot changed
7,946 and filled the OS's free runs to within 52 bytes).

## Measured vs inferred

**Measured:**
- `tools/verify_midiscenes.py` (in `make verify`): every region assembles
  and links to his encoder's bytes at his addresses, and the committed
  `gas/*.s` are what `gas_port.py` regenerates.
- `make check REMIX=midi-scenes` passes; every detour's expect bytes match
  stock. `ported` (+ the LO-FI AMF fix) composes.
- **Booted under the ColdFire port** (`tools/verify_dram_boot.py`, in
  `make verify`): the boot detour reaches octabam's loader, the loader
  calls the stock depacker with our stage and window, the boot reaches
  the RTOS handoff with the loader's hash gates all passing, and the
  window reads back equal to the linked image in 8,494 of 8,502 bytes —
  the 8 that differ are his state words (`last_part`, `apply_ret`), i.e.
  his code ran **from DRAM** through the `apply_part` detour during boot.
- His `apply_part` hook (`0x40009094`) is shared with Octakit and octamax;
  the ledger refuses those combinations by name.

**Inferred / not measured:** nothing built by this pipeline has been
flashed; his own builds are what has run on hardware. That the linked
layout behaves identically to his fixed one follows from the per-region
identity plus the linker resolving the same symbols — it is not a
separate measurement.

## Open

- **MSC in DRAM.** The 4 KB table is what fills the last free run. His
  DRAM state already carries a validity magic; MSC could live in the
  `Runtime` window the same way and free the run entirely. His call.
- Detour chaining for `0x40009094`, so this can share an image with
  Octakit.
- The PR upstream, once he's done: `tools/gas_port.py` + `gas/`, and
  optionally `build.py` consuming the `.s` form.
