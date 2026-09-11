# Octakit

Em's Octakit — 256 Kits per Project in place of 64 bank-tied Parts — built
by octabam straight from her repository,
[emuyia/ems-octakit](https://github.com/emuyia/ems-octakit), which lives here
as the git submodule `upstream/` (pinned; `git submodule update --init`).
`Kind.CF_PATCH` with a `Runtime`: 598 guarded sparse writes into the OS
image plus a 73,111-byte append. No DSP code, no menu row.

Her README is the user-facing description (LOAD/SAVE KIT on PART /
FUNC+PART, FUNC+CUE reload, names, copy/paste/clear/undo, automatic Parts→
Kits migration of old projects). **Back up projects before flashing this;
downgrading to stock may lose Kit data.** Those are her words and they
apply unchanged.

## Why this one is built differently from every other module

Every other ColdFire mod here (midi-scenes, octamax, busscreen, tempo-sync)
fights over ~6 KB of free zero runs in the OS image. Octakit doesn't touch
them: one boot-path write detours into a small early loader appended past
the end of the image; the loader depacks a 149,653-byte runtime with the
firmware's *own* aPLib routine into the reserved recorder pages at
`0x45d0dde0` and runs it from DRAM. The 411 Elektron routines the runtime
needs are `.incbin`'d out of *your* stock 1.40C at build time (copied or
PC-relative-relocated per the recipe) — her repo carries none of Elektron's
bytes, and neither does this one.

That design is now octabam's third placement class, `schema.Runtime`,
implemented in `tools/remix/runtime_build.py`: compile and link her sources
with her linker script, pack with her encoder (ported to Python,
deterministic), link again with the packed blob, append. Every stage is
checked against the identity her `firmware.json` pins; a mismatch stops the
build with both digests. The image repacker (`elektron-firmware-tool`)
already accepts the grown section — tested.

## Measured vs inferred

**Measured (9 Sep 2026, code pinned at `ca3b527`; submodule at `ec70dda`,
her README's flex-pool note, no code change):**
- Homebrew's `m68k-elf-gcc` 16.2.0 rebuilds the runtime **byte-identical**
  to her pinned 16.1.0 build (`sha256 dda11aca…`, 149,653 B; all 411 stock
  slices reproduce), and so do the packed runtime and the append.
- `tools/verify/verify_octakit.py` (in `make verify`): stock + her 650 writes +
  her append, and nothing else, reproduces her whole combined OS image
  exactly (`output.os` identity), from this repo's own copy of stock
  1.40C. An octabam *image* is never identical to hers — even the solo
  `octakit` remix carries octabam's own FX2 chooser and DSP null-stub
  edits — and the build prints that rather than pretending otherwise.
- Her Rust patcher is not needed: it applied this same recipe in a browser;
  the OS-image half is ~250 lines of Python here.
- **Her runtime rides octabam's loader as a payload, and it boots.** Her
  own append (loader + stage + packed runtime) is replaced by octabam's
  loader (`tools/remix/loader.S`, derived from hers) with her packed
  runtime staged at *her* stage address so her post-clear relocation
  still finds it; her 650 writes are untouched. Under the ColdFire port
  (`tools/verify/verify_dram_boot.py`): her wrapper calls our loader, the stock
  depacker runs with her stage and window, her authentication gate and
  post-load entry run with her hash `0xb5b173b1`, the boot reaches the
  RTOS handoff, and her window reads back **byte-identical** to her
  runtime (149,653 B, 0 differing).
- Against every other module in this repo, her writes collide at exactly
  two stock routines: `apply_part` entry `0x40009094` (midi-scenes,
  octamax) and the scene-parameter writer `0x40052ae8` (octamax). The
  ledger refuses those combinations. `lofi-amf-fix` composes freely.

**Inferred / not measured:** nothing built by this pipeline has been
flashed; her own development builds are what has run on hardware. The
gcc pin in her recipe (16.1.0) is not enforced here because the identity
checks are the stronger statement — a future compiler that does not
reproduce her bytes fails loudly.

## Open

- Detour chaining, so a shared hook site (`0x40009094`) can carry more
  than one module — the thing that would let Octakit and midi-scenes share
  an image.
- One runtime per image today (one append, one DRAM window). A second
  runtime module would need its own window or to co-link into hers.
- Updating: bump the submodule, rebuild; if her recipe's interface_version
  changes, `runtime_build.py` refuses until taught the new one.

## Open, and what would need to come from her

- ✅ **The stage overlap is a NON-ISSUE — answered by Em, 12 Sep 2026.**
  Octakit needs `0x47fc7410..0x47fd910f` **on boot only**; after that her
  code lives in the reserved flex-pool space and the temporary copy is no
  longer needed. The bounce-buffer fills we measured happen at PROJECT
  LOAD, i.e. after boot, so nothing of hers is live there. The
  measurement itself stands (`docs/remixer/PLACEMENT.md`) — it is the
  *consequence* that is retracted. ⚠️ One thing still worth checking on
  our side: we recorded her wrapper as re-hashing the stage at every
  project load (`0x40013304`); if that is right, a clobbered stage would
  meet a hash gate. Either our reading of that site is wrong or the gate
  tolerates it — unresolved, and ours to confirm, not hers.
- ✅ **Both kit questions ANSWERED by Em, 12 Sep 2026.** (1) **Kits retain
  the part layout and offsets** — an offset valid inside a part is valid
  inside a kit. (2) Saved kit data is at **`__gk_canonical_payloads`**,
  indexed exactly as `persistence.c` does it:
  `__gk_canonical_payloads + kit * PART_PAYLOAD_SIZE` (`0x18b2`), a flat
  256-entry array. So the READ side needs only a different base, as the
  stride match suggested.
- ⚠️ **But the WRITE side is not a base change, and that retracts the
  optimistic framing.** Em: *the saved kit and the active working kit are
  separate*, so changes must go through Octakit's editing functions to be
  included when the kit is saved. Her sequence, in order:
  `gk_workspace_prepare` → `gk_physical_acquire` →
  `gk_descriptor_store_byte` **for each changed byte** →
  `gk_workspace_mark_dirty_pending` → `gk_workspace_commit_update` →
  `gk_descriptor_release`. All six are `.global` in her runtime.
  midisc's `pack` writes its sparse bytes directly, so under Kits it
  would have to drive that bracket instead — up to `SPARSE_BYTES` (144)
  `gk_descriptor_store_byte` calls per part. Tractable, but it is a
  protocol, not an address. The matching ask on his side is in
  `modules/midi-scenes/README.md`. Nothing is needed for the two to
  coexist today (`remixes/mods.py`); this is persistence, not the live
  path — her active path still applies the STOCK Part window.
