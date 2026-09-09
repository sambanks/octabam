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
exercised), and anything after the handoff.

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
