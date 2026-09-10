# Placement: where a module's code goes, and what is actually free

Every ColdFire-side module has to answer one question: the OS is a fixed
1.1 MB block of Elektron's code — where does *yours* go? octabam gives
three answers, and the build decides which bytes land where; a module
declares what it is, not an address.

## The three placement classes

| class | declared as | where it lands | budget |
|---|---|---|---|
| **ROM cave** | `CavePatch` (pinned hex, or a `.s` source that is the truth) | one of the OS image's free zero runs; floats after what precedes it unless pinned | ~8.4 KB, total, shared by everyone |
| **DRAM unit** | `Linked(..., dram=True)` | linked with every other DRAM unit in the remix as ONE image, packed, appended after the OS behind octabam's loader, depacked at boot into the **platform's arena reserve** (below) | 10 MiB, off the unit's sample/recorder pool |
| **Appended runtime** | `Runtime` (a recipe: Octakit's `firmware.json`) + `ArenaReserve` | its own pages of the same arena, as a payload of the same loader | the author's (Octakit: 528 pages) |

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
  pointer. Octakit's stage (signature + packed runtime, **72,959 B**)
  takes the bottom of it when she is in the image, leaving 28,401 B;
  octabam's stage starts at `0x47fd9200` (7,680 B) and its runtime window
  at `0x47fdb000` (20,480 B), ceiling `0x47fe0000` — fixed addresses
  whatever the remix.
  ❌ **"Never written in any phase measured" is RETRACTED (10 Sep 2026).**
  It held for a project with no samples. Stock's engine task names four
  buffers *inside* this window, all through the alias — `0x4ffc7610`
  and `0x4ffc9010` (sector bounce buffers: `base − (file offset & 511)`),
  `0x4ffcb220` and `0x4ffce230` (two arrays of 769 × 16 B, a
  double-buffered descriptor list) — from routines under the engine
  task `0x4008445c` (Bryan's 46-opcode dispatcher). With a project whose
  slots hold **static samples**, the port fills **`0x47fc8fe4..0x47fcd9e4`
  (18,944 B = 37 sectors) at PROJECT LOAD** — 43,008 word stores from
  the PIO sector loop `0x40015472..0x4001548e`, the first of them
  `RIFF…WAVEfmt `, the static sample's own header — identically for
  400 and 2,000 frames of play (the same 5,969 ATA reads: it is the
  load, not streaming, and streaming itself never started in the port).
  ⚠️ The port's write-watch missed every one of these until 10 Sep
  2026: it compared the *unfolded* alias address, so a watch on
  `0x47fc…` could not see a store to `0x4ffc…` (`machine.cpp`,
  `noteWatchedWrite`) — the dump caught it, the watch now folds. That range is **inside Octakit's stage** (from
  `+0x1bd4`) and **47 KB below octabam's stage**; nothing has been seen
  above `0x47fcd9e4`, and no literal in the OS names anything above
  `0x47fd1240` (the second descriptor array's end). ⚠️ Two caveats: the
  port's card advertises no DMA, so the OS took its PIO path — a
  DMA-capable card may use the other bounce buffer (`0x4ffc7610`) or
  the READ DMA path; and streaming during play is unexercised. Her
  wrapper re-hashes the stage at every project load (`0x40013304`), so
  on hardware this either does not happen on her users' cards or her
  gate copes; the test is one LOAD PROJECT after another with static
  slots, and Bryan-style: the firmware-armed hardware watchpoint mxldyn
  proved (his `build_diag_bugA5.py`) on `0x47fc7410..` would settle it
  in one flash.
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
  `SDCS1 = 0`. One chip select; a **256 MB decode window**
  `0x40000000..0x4fffffff` — ✅ NXP's own DDR2 example (AN3522 §3.3)
  writes `SDCS0 = 0x4000001A` for 128 MB, so `0x1b` is the next size.
- **The cache map, decoded with the kernel's own definitions**
  (`arch/m68k/include/asm/m54xxacr.h`): runtime `CACR = 0xa50ce100` =
  DEC | DESB | **DDCM_P (`0x04000000`, default data mode = cache-
  inhibited precise)** | DCINVA | BEC | BCINVA | IEC | DNFB | ICINVA;
  `ACR0 = 0x4007e020` = base `0x40`, mask `0x07`, ENABLE, any mode,
  **copyback** → `0x40000000..0x47ffffff` is the cached SDRAM — exactly
  128 MB, Elektron's own statement of the RAM's extent; `ACR1 =
  0x0000e020` = `0x00000000..0x00ffffff` copyback. Nothing else is
  cacheable, so `0x48000000..0x4fffffff` is the **uncached alias** by
  the CACR default. No instruction ACRs, no MMUBAR: the MMU is unused.
- Physical size **128 MB**: ✅ ACR0's mask + the reset stack at
  `0x48000000`; ✅ hardware, twice — Octakit's runtime is written through
  `0x4dd0dde0` and executed at `0x45d0dde0` on her units, and mxldyn's
  canary at `0x47800000` was clobbered on his MKII by the rings the OS
  addresses at `0x4f8…`. The part number on the board would make it
  three.
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
  top. The "uncached" property of the upper half is the CACR default
  (`DDCM_P`) with ACR0 covering only the lower 128 MB — see "The SDRAM
  itself" above; the earlier "comes from the MMU" reading is withdrawn
  (`0x806` is a 68040 register number objdump named `urp`; the ColdFire
  has no such register and no MMUBAR is ever written).
- Em's stage starts at `0x47fc7410` = the first byte after that memset:
  she measured the same clear.
- Bryan's per-track ring is 1,411,200 B (the wrap length: `cmpil
  #1411200` at `0x4000359e`, `addil #1411200` at `0x400032f8`); the
  **stride is 1,411,328** (`addil #1411328,%d5` at `0x40003386`, `movel
  #1411328,%d4` at `0x400037f8`) — 128 B, one 16-sample frame, of pad per
  ring, and 8 × 1,411,328 = the memset exactly. ✅ measured.
- ✅ **Hardware, from mxldyn (10 Sep 2026, via the octamax review):** his
  canary at `0x47800000` and his first 256-slot home at `0x47700000` were
  both clobbered at runtime on his MKII — ring 2 spans
  `0x4765b490..0x477b3d10`. The rings are live memory on silicon.

### The rest of the map, read from the boot code

- `0x40a955e0..0x46025de0` — the **audio page arena**: 14,602 pages ×
  6,144 B = 89,720,832 B = **85.56 MiB, Elektron's "85.5 MB"** (cold init
  `0x40096f7a`: count `0x390a`, free-list fill to 14,603, `memset(
  0x40a955e0, 0x05590800)` at `0x40097006`). Flex samples and the track
  recorders share it (the default Flex cap is the `0x04000000` = 64 MB
  literal at `0x40004028`). ✅ measured, and it is where both DRAM mods
  actually live:
  - **Octakit takes the TOP 528 pages** — her four writes cut the count
    to 14,074 (`0x36fa`), the free-list fill to 14,075, the arena clear
    to `0x05278800` and the recorder cap to match: 528 × 6,144 =
    3,244,032 B = `0x45d0dde0..0x46025de0`, her `RUNTIME_START..END`
    exactly. **Octakit costs the unit 3.09 MiB of sample/recorder
    memory.** ✅ from her recipe against stock's bytes.
  - **octamax 2.0 takes the BOTTOM 64 pages** (`0x390a → 0x38ca`, pool
    base moved to `0x40af55e0`): a 384 KB reserve, hardware-confirmed.
  Two authors, one mechanism, both proven on units. This — not the top
  window — is the placement with a hardware record.
- `0x46025de0..0x4763d580` — zero-filled at boot by the loop right after
  the boot detour (`0x40000518`), and the base of stock's object pool
  (`pool_init(0x46025de0)` at `0x4002000e`): the OS's own globals and
  heap, the `0x46xxxxxx` addresses all over this project's notes. Not
  free. (Its end overlaps the first 1.29 MB of ring 0; both are zeroed,
  nothing follows from it.)
- `0x47500a10` — an 8,704 B sector bounce buffer just below the rings
  (`0x4f500a10 − (offset & 511)` at `0x40091f94`).

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

## The platform reserve (10 Sep 2026, Sam: "10 MB of the arena")

octabam's runtime and stage live in **1,707 pages (10,487,808 B) taken off
the BOTTOM of the audio page arena**, `0x40a955e0..0x41495de0`
(`tools/remix/arena.py`, `PLATFORM_PAGES`), the way octamax 2.0 takes its
64. The base literal moves up by that much at its 24 sites (23 direct
plus `lea base+6144` at `0x40094a62`, which a "23 operands" port misses),
and the four geometry words — page count, free-list fill limit, arena
clear length, recorder page cap — are computed from **every** reservation
in the remix: Octakit's 528 at the top are declared by her module
(`ArenaReserve(528, "top", recipe_writes=…)`), her four recipe writes
are skipped, and the build writes the combined values. Proof of the
composition: the `octakit` remix alone yields exactly her four words
(`36fa / 36fb / 05278800 / 36fa`); `midi-scenes` yields base `0x41495de0`
and 12,895 pages (75 MB) left. The runtime is linked at the reserve's
base; the stage follows it page-aligned; the ceiling is the reserve's end.

Why this and not the top window: it is the one DRAM placement with a
hardware record (two authors, two units), the OS never touches a
reservation again (the clear starts at the new base, the boot-time copies
follow the literal, the allocator cannot hand out an index above the new
count), and the cost is honest — 10 MB of an 85.5 MB pool, off the
recorder share by default. The old top-window constants are gone from
`platform_build.py`. Octakit's stage stays at `0x47fc7410` because her
own relocation re-depacks from there; that is hers to move.

Fixed addresses whatever the remix, as before: the reserve is always
the first 1,707 pages, so a remix without Octakit boots the same bytes to
the same places.

✅ **Measured under the port, with the alias-folding watch, on the
static-sample card** (boot → LOAD PROJECT → 400 frames): the `hello-dram`
image reproduces the stock run to the count — 6,232 ATA commands, 30,573
sectors read, 292 written, the same five tracks armed at frame 0, the
same 18,005 bytes landing in the old top window — with **0 writes into
the reserve** and the runtime read back identical. The `midi-scenes`
image likewise has no stock write into the reserve (28,700 writes, all
from his own code running in DRAM: the MSC table and his state); on that
image tracks 1–2 do not arm at frame 0 and ~8,600 fewer sectors are read
— his `apply_part` wrapper and reload hooks changing part application
under the port, not the arena (the control says so). Reported to him.

✅ **Re-measured 10 Sep 2026 on the same card, against his 1.40MIDISC**
(the `hello-dram` control rebuilt bit-identical, and the 1.40MSC image
rebuilt bit-identical to the one first measured, so only his sources
differ):

| image | ATA cmds | sectors read | written | armed at frame 0 |
|---|---|---|---|---|
| `hello-dram` (control) | 6,189 | 30,467 | 297 | 5 — tracks 0,1,2,4,7 |
| midi-scenes 1.40MSC | 5,234 | 21,958 | 0 | 3 — tracks 0,5,7 |
| midi-scenes 1.40MIDISC | 6,189 | 30,467 | 297 | 3 — tracks 0,5,7 |

**The card I/O half is FIXED** — every counter on his new image equals the
control's exactly, not approximately. The cause was his own: `bank_switch`
/ `bank_invalidate` preserved only `d0` across a `jsr` that had replaced a
plain `move.l d0,(BANK_PTR).l`, so the sample load lost registers; 1.40MIDISC
saves `d1-d7/a0-a6` (his comment: "sample load").

⚠️ **The arming half is NOT fixed and is a SEPARATE defect** — identical on
both his images, so it is not the register clobber.

✅ **BISECTED to ONE site: `0x40087d44`** (10 Sep 2026, same fixture). Built
one image per dropped hook group, then per site, from the same tree:

| dropped | armed @ frame 0 |
|---|---|
| nothing (1.40MIDISC) | 3 — 0,5,7 |
| all 38 sites | 5 — 0,1,2,4,7 |
| lifecycle group (apply/reload/save/clr_pt/2 pokes) | 3 |
| scene group (scene_done ×2, write_mix, plock) | 3 |
| everything else (hold/dial/addi/LED/menus/enc/morph/xf) | 3 |
| **bank group (bank_sw ×2, bank_inv ×2)** | **5** |
| bank_sw A `0x400622aa` only | 3 |
| **bank_sw B `0x40087d44` only** | **5** |
| bank_inv A / B / both | 3 |

Dropping the all-38 image restores 5, so the DRAM units alone are innocent
and the instrument can see the effect. The two `bank_sw` sites carry the
SAME cave, and only one of them breaks arming — so it is the SITE, not the
routine in isolation. Watched (`--watch-pc`): `0x40087d44` fires **once**,
at instruction 60,393,356 (transport start), with `d0` = the arena base +
1×635,712, i.e. bank index 1; `0x400622aa` fires once just after with bank
index 0; the four `bank_inv` hits all precede both.

**WHAT THE SIGNAL MEANS, and the symptom.** The frame-0 `FW_LIVE_NIBBLE`
writes are the step-1 trigs of the bank being played (`RTOS_FORK.md`, the
fixture table). The midisc set *gains* a track, so this is different
PATTERN DATA being read, not tracks failing to start. Checked against the
fixture's own banks, excluding track 8 (whose write comes from a different
pc, `0x4000bd7e` vs `0x4000b9bc`):

| | step-1 trig tracks | matches |
|---|---|---|
| control | 1,2,3,5 | **bank 3 pattern 1** — where the project was saved |
| midisc | 1,6 | **bank 1 pattern 0** — the default position |

So in use this would read as: load a project, press PLAY, and the sequencer
starts at the top of bank 1 instead of the pattern you left it on. ⚠️ Two
independent sets each matching a real pattern is strong, but the write is
NOT traced, and the `--watch-pc` capture showed `d0` carrying bank index 1,
which does not obviously line up with landing on bank 1 pattern 0. Well
supported, not established. The persistence risk is the larger one: `pack`
performs a durable stock SAVE, so this site writes during a bank switch
with the bank state mid-flight.

Stock's two sites differ, which is the lead: `0x400622aa` is guarded by a
`cmpl`/`beqs` that skips unless the bank actually CHANGED, and publishes the
current-bank byte `0x80000002` *after* the store; `0x40087d44` is an
unconditional clamp-and-set path that publishes `0x80000002` and
`0x100b14ce` *before* the store. His cave replaces a plain `move.l
d0,(BANK_PTR).l` with `pack` — which by his own docstring performs a durable
STOCK SAVE (shadow + staging + `9b312`) — then the store, then `unpack`.

⚠️ **INFERRED, not established: WHICH of those does the damage.** Candidates
are the SAVE's side effects, `unpack` overwriting part state the load has
just written, and the site being unguarded so it fires when nothing changed.
Not traced to a write. Note `pack` early-outs when `LAST_PART == 0xFF` and
every `bank_inv` hit (which sets it) precedes this one, so `unpack` is the
likelier half — but that turns on whether an `apply_part` reset `LAST_PART`
in between, which was not checked. His code and his intent; handed over as
the one site.

Whether either half reproduces on hardware is still not known — this is the port, and the counts above are
its counts, not a unit's. (These absolute numbers differ slightly from the
9 Sep run above because the build has moved since; the three rows here are
one contemporaneous set and only they should be compared with each other.)

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

## Shared sites: the bridge (10 Sep 2026)

Two stock sites are claimed by more than one mod, and until today the
ledger's only answer was to refuse the pair. `modules/scenes-kits` is the
first **bridge**: a stub that does what both hooks did, in an order that
respects each one's protocol, declared through `schema.Override` so the
build skips the overridden detour or recipe write and hands the stub the
skipped claim's target as a link-time symbol (`CHAIN_APPLY_NEXT`,
`CC_NEXT`). Sites, protocols and the guard her boot-time path forces are
in `modules/scenes-kits/README.md`.

✅ **Measured under the port** (`mods` image — MIDI SCENES + Octakit + the
LO-FI fix + CC→page 2 — on the static-sample card, boot → LOAD PROJECT →
400 frames): six `apply_part` calls, and every one went site → bridge stub
→ her entry → her trampoline (stock's body); her fatal 0×, the loader's
fatal 0×; once her lifecycle was active his `pack` ran (2×, one from his
`bank_sw` path) and his `after` 1×; her window and ours read back as
their own state words only. Not measured: MIDI CCs through the chained
dispatch (the port has no MIDI in), his Part save/reload menu hooks
against her Kit menus, hardware.

## What is still open

- **More than 10 MB** is the same mechanism with a bigger
  `PLATFORM_PAGES` (the ledger refuses below 2,048 pages left). The
  route that costs no sample memory — a remix with the stock DELAY off
  both choosers detouring its frame routine (`0x400031a0`) so the eight
  rings are never written, 10.8 MB — stays unmeasured; whether the
  routine has duties beyond the delay is the question one detour and one
  port run would answer.
- **Octakit's stage at `0x47fc7410`** sits under stock's sector bounce
  buffer (above). Hers to move — the arena is where the rest of her
  already lives.
- **Detour chaining** for the two stock routines three authors hook
  (`apply_part` entry `0x40009094`, the scene-parameter writer
  `0x40052ae8`).
- **Octakit + midi-scenes** stay mutually exclusive: not only the hook,
  but Parts versus Kits — his code addresses the Part window, hers
  replaces it.
