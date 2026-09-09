# Placement: where a module's code goes, and what is actually free

Every ColdFire-side module has to answer one question: the OS is a fixed
1.1 MB block of Elektron's code — where does *yours* go? octabam gives
three answers, and the build decides which bytes land where; a module
declares what it is, not an address.

## The three placement classes

| class | declared as | where it lands | budget |
|---|---|---|---|
| **ROM cave** | `CavePatch` (pinned hex, or a `.s` source that is the truth) | one of the OS image's free zero runs; floats after what precedes it unless pinned | ~8.4 KB, total, shared by everyone |
| **DRAM unit** | `Linked(..., dram=True)` | linked with every other DRAM unit in the remix as ONE image, packed, appended after the OS behind octabam's loader, depacked at boot into the never-cleared window | ~99 KB, ~28 KB beside Octakit |
| **Appended runtime** | `Runtime` (a recipe: Octakit's `firmware.json`) | its own DRAM window, as a payload of the same loader | the author's |

The OS-image edits every class needs — a detour at a stock instruction,
a poke, a grown table — are `Detour`, `Poke`, `TableGrow`, wired by
symbol. The ledger (`tools/remix/ledger.py`) refuses two modules that
claim one address before a byte is written.

## The free ROM, measured

Three zero runs inside the OS image (`0x400c0000..0x400d8000` scanned for
runs ≥ 64 B; the region above `0x400d8000` reads zero but is the PROJECT
subsystem's RAM and is refused):

```
0x400c45b0..0x400c4702     338 B
0x400d24d0..0x400d2ce0   2,064 B   (the "second zero run")
0x400d2ee6..0x400d3020     314 B
0x400d64da..0x400d7c3c   5,986 B   (the "third zero run"; the FX2 chooser's
                                    NONE row + terminator sit at 0x400d6b00
                                    in EVERY build, and descriptor clones
                                    grow from 0x400d6b20)
```

midi-scenes as a pinned snapshot needed 8,196 of these 8,364 bytes.
That is the whole argument for DRAM.

## The DRAM, measured — and a retraction

Measured 9 Sep 2026 with the ColdFire port (`tools/emu/ot_emu`), boot to the
RTOS handoff, project load and 300 frames of play, with `--watch-pc`
armed before boot and `--mem-dump` at exit:

- **`0x45d0dde0..0x46025de0`** — Octakit's window ("reserved recorder
  pages"). Stock's engine zero-fills exactly this extent at **project
  load**, twice. Her post-clear relocation exists for this; her runtime
  survives because she re-depacks it from a stage copy the OS never
  touches.
- **`0x47502c10..0x47fc7410`** — the stock **delay rings**, 10.8 MB,
  cleared through the uncached alias at boot instruction ~42 M, about
  38 M instructions *after* the boot detour has returned, and live audio
  memory after that. ⚠️ An earlier reading of "8.8 MB free at 0x47700000"
  was made with a watch on cached addresses while the port mapped the
  alias as separate memory; it could not see this clear. **Retracted.**
  The port now folds the alias (`machine.h`, `alias()`), so the
  measurement is repeatable.
  ✅ **Independently confirmed by Bryan T's delay write-up**
  (`docs/firmware/EXTERNAL.md` §1, received 30 Aug 2026, before this
  measurement): the Echo Freeze Delay keeps one ring per track at SDRAM
  `0x4F502C10` — the uncached alias of `0x47502c10` — of 1,411,200 B
  each, **always allocated**. 8 × 1,411,200 = `0xac4400`, so the rings end
  at `0x47fc7010`; the clear the port saw runs 1 KB past that. Two
  readings, two instruments, one region.
- **`0x47fc7410..0x47fe0000`** — the **101,360 B (~99 KB)** between the
  end of the rings and the 128 KiB Octakit keeps below the reset stack
  pointer. Never written in any phase measured. Octakit's stage
  (signature + packed runtime, **72,959 B**) takes the bottom of it when
  she is in the image, leaving 28,401 B; octabam's stage starts at
  `0x47fd9200` (7,680 B) and its runtime window at `0x47fdb000` (20,480 B),
  ceiling `0x47fe0000` — fixed addresses whatever the remix, so that a
  remix without Octakit boots the same bytes to the same places. The
  price of that simplicity: her 73 KB sits idle when she is absent. The
  window could grow to the full ~99 KB in that case; nothing has needed
  it yet.
- **`0x46000000..0x47502c10`** (~21 MB) — outside both big clears and
  **unmeasured**: stock's sample pool may live there. The candidate for
  MB-scale placement, once a run that loads samples and records has been
  watched. Not before.

What the port cannot see: caches (it has none), the recorder (never
exercised), anything after the handoff — and **DMA traffic**: the port
models the eDMA's descriptors and completions but moves no bytes
(`Edma::start` fires callbacks, nothing copies), so a region only DMA
writes to reads as "never written". The rings are known from the CPU's
own memset, not from their audio.

### The SDRAM itself, read from the boot code (10 Sep 2026)

- `0x400e12e8`: `SDCS0 = 0x4000001b` (base `0x40000000`, CSSZ `0x1b`),
  `SDCS1 = 0`. One chip select; per the MCF5445x reference manual's CSSZ
  encoding that is a **256 MB decode window** `0x40000000..0x4fffffff`
  (🟡 the encoding table is from memory — confirm against the RM).
- **Every stock reference to the rings is through the alias**: the
  memset at `0x40002fb4` (`lea 0x4f502c10`; **705,664 × 16 B =
  11,290,624 B = `0xac4800`**, ending at `0x4ffc7410`) and the delay
  frame routine's four `#0x4f502c10` adds (`0x4000330e`, `0x4000331c`,
  `0x4000358c`, `0x400037aa`). Stock never names `0x47502c10`.
- **That the two halves are one memory is proven on hardware by
  Octakit**: her loader writes the runtime through `0x4dd0dde0`
  (`SDRAM_ALIAS_DELTA = 0x08000000` in her `link.ld`) and the OS then
  executes it at `0x45d0dde0`, on her unit, every boot. A 256 MB window
  over a 128 MB part aliases exactly like this; the physical size is
  what the board's SDRAM part number / Elektron's spec would confirm,
  and the reset stack at `0x48000000` says the OS treats 128 MB as the
  top. The "uncached" property of the upper half comes from the MMU
  (`movec %urp` is set; no data ACRs are written), 🟡 inferred.
- Em's stage starts at `0x47fc7410` = the first byte after that memset:
  she measured the same clear.
- Bryan's per-track ring is 1,411,200 B; the memset is 8 × 1,411,328 —
  🟡 a 128 B (16-sample) pad per ring would explain it, consistent with
  his two-tap crossfade reading one frame past the wrap. The stride is
  readable at the four adds above; not done.

### Em's DRAM, exactly (from `m68k-elf-nm` on her `runtime.elf`)

| | range | bytes |
|---|---|---|
| runtime (code + data) | `0x45d0dde0..0x45d32675` | 149,653 |
| code budget (`0x25000`) | ends `0x45d32de0` | 1,899 spare |
| 256 Kits × 6,322 B (`PART_PAYLOAD_SIZE 0x18b2`) | `0x45d32de0..0x45ebdfe0` | 1,618,432 |
| 128 spill payloads (undo, clipboard, rollback) | `..0x45f838e0` | 809,216 |
| descriptors, bitmaps, names, UI rows, undo | `..0x45fb2f42` (`__gk_planned_end`) | ~190,050 |
| slack | `0x45fb2f42..0x4600154b` | 320,009 |
| backup copy of the runtime | `0x4600154b..0x46025de0` | 149,653 |
| **her region** (`RUNTIME_START..RUNTIME_END`, stock's reserved recorder pages, zero-filled at project load) | `0x45d0dde0..0x46025de0` | **3,244,032** |
| her stage (signature + packed runtime) | `0x47fc7410..0x47fd910f` | **72,959** |

So she claims 3,316,991 B (3.16 MB) and uses 2,996,982 of it; the
bytes her loader actually writes at boot are 372,265 (runtime, backup,
stage).

## The loader

`tools/remix/loader.S`, derived from Em's Octakit loader with attribution:
a stub at `0x4010fdf0` (the byte after the OS image) that the boot site's
`jsr 0x40001e50` is redirected into — by her recipe's own wrapper when
Octakit is in the image, by octabam's three-byte poke otherwise. It
replays the boot-continue call, then for each payload in its table:
copies the staged blob (4-byte signature + `GKA3` stream) to its
persistent stage through the uncached alias, hash-gates the packed
stream (rolling ×33, the same function her OS-resident helper computes),
checks the `GKA3` header, depacks with the firmware's own aPLib routine
at `0x400e0aca`, hash-gates the result, and copies a backup if asked.
Any mismatch hangs the boot visibly rather than running half a runtime.
Her runtime is one payload, staged at *her* address so her relocation
still finds it; octabam's runtime is another.

`tools/verify/verify_dram_boot.py` (in `make verify`) boots the built image
under the port and checks that the loader ran once, never hit its hang,
and that every window reads back equal to its linked image — except the
bytes a runtime writes about itself once its hooks run, which are counted
and printed.

## What is still open

- **MB-scale placement.** Two candidate mechanisms, neither measured:
  - *Give up the stock DELAY and take its rings.* A remix with the Echo
    Freeze DELAY off both choosers has no use for the eight 1.4 MB rings;
    a detour at its frame routine (`0x400031a0`, Bryan T) that skips the
    ring work would leave 10.8 MB never written — one detour and one
    boot-to-play measurement under the port. 🟡 Inferred from his
    description of the routine; whether it has duties beyond the delay
    (the clear itself, DMA bookkeeping another consumer relies on) is the
    question the measurement answers.
  - *Wipe-and-reload, generalised.* Octakit survives its project-load
    wipe with a hook that re-depacks from the stage. Anything placed in a
    region stock clears needs the same hook; that mechanism is hers, and
    the one worth building together if the first route is closed.
- **Detour chaining** for the two stock routines three authors hook
  (`apply_part` entry `0x40009094`, the scene-parameter writer
  `0x40052ae8`).
- **Octakit + midi-scenes** stay mutually exclusive: not only the hook,
  but Parts versus Kits — his code addresses the Part window, hers
  replaces it.
