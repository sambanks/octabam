# Placement: where a module's code goes, and what is free

The OS is a fixed 1.1 MB block of Elektron's code. A module declares what
it is, not an address; the build decides which bytes land where.

## The two placement classes

| class | declared as | where it lands | budget |
|---|---|---|---|
| **ROM cave** | `CavePatch` (pinned hex, or a `.s` source that is the truth) | one of the OS image's free zero runs; floats after what precedes it unless pinned | ~8.4 KB total, shared by everyone |
| **DRAM unit** | `Linked(..., dram=True)` | linked with every other DRAM unit in the remix as one image, packed, appended after the OS behind octabam's loader, depacked at boot into the platform's arena reserve | 10 MiB, off the unit's sample/recorder pool |

Until 6 Oct 2026 there was a third, the appended runtime (`Runtime` + 
`ArenaReserve`): Em's Octakit, built from her recipe and carried as a
payload of the same loader in its own 528 pages of the arena. KITS
(`modules/kits`) replaced it; the class went with it (`git show
2063370f:tools/remix/schema.py`).

The OS-image edits every class needs (a detour at a stock instruction, a
poke, a grown table) are `Detour`, `Poke`, `TableGrow`, wired by symbol;
stock bytes a module relies on without writing are a `Keep`.
`tools/remix/ledger.py` refuses two modules that claim one byte before
a byte is written.

## The free ROM (measured)

Zero runs inside the OS image (`0x400c0000..0x400d8000` scanned for runs
≥ 64 B). The region above `0x400d8000` reads zero but is the PROJECT
subsystem's RAM and is refused: octalab put a menu table in the 15 KB zero
run at `0x401087e4` and the unit raised `VEC:03` in the menu draw loop
(octalab, 13 Sep 2026).

```
0x400c45b0..0x400c4702     338 B
0x400d24d0..0x400d2ce0   2,064 B
0x400d2ee6..0x400d3020     314 B   (refused at placement by the build, 25 Sep 2026:
                                    a live descriptor, modules/midi-scenes' CAVE2 note)
0x400d64da..0x400d7c3c   5,986 B   (the FX2 chooser's NONE row + terminator sit at
                                    0x400d6b00 in every build; descriptor clones
                                    grow from 0x400d6b20)
```

midi-scenes as a pinned ROM snapshot needed 8,196 of these 8,364 bytes.

## The DRAM (measured under the ColdFire port unless marked)

Measured with `tools/emu/ot_emu`: boot to the RTOS handoff, project load
and 300-2,000 frames of play, `--watch-pc` armed before boot, `--mem-dump`
at exit, the write watch folding the uncached alias.

| range | what | status |
|---|---|---|
| `0x40000000..0x47ffffff` | the cached SDRAM, 128 MB | boot code (ACR0 mask) + hardware |
| `0x48000000..0x4fffffff` | the same memory uncached: `SDCS0 = 0x4000001b` is a 256 MB decode over a 128 MB part (NXP's own example uses `0x1a` for 128 MB); `CACR = 0xa50ce100` has `DDCM_P` (default data mode cache-inhibited) and `ACR0 = 0x4007e020` covers only the lower 128 MB copyback; no MMU | boot code; hardware (Octakit writes through `0x4dd0dde0` and executes at `0x45d0dde0`; mxldyn's canary at `0x47800000` was clobbered by the rings the OS addresses at `0x4f8…`) |
| `0x40a955e0..0x46025de0` | the audio page arena: 14,602 × 6,144 B = 89,720,832 B = 85.56 MiB, Elektron's "85.5 MB" (cold init `0x40096f7a`: count `0x390a`, free-list fill to 14,603, `memset(0x40a955e0, 0x05590800)` at `0x40097006`; the Flex cap is the `0x04000000` literal at `0x40004028`). Octakit took the top 528 pages (until 6 Oct 2026), octamax 2.0 the bottom 64 (base moved to `0x40af55e0`), the platform reserve the bottom 1,707 | measured; both authors' placements hardware-proven |
| `0x45d0dde0..0x46025de0` | Octakit's window until 6 Oct 2026 ("reserved recorder pages"). Stock's engine zero-fills exactly this extent at project load, twice; her post-clear relocation re-depacks from a stage the OS never touches | measured |
| `0x46025de0..0x4763d580` | zero-filled at boot by the loop after the boot detour (`0x40000518`); the base of stock's object pool (`pool_init(0x46025de0)` at `0x4002000e`): globals and heap. Not free; its first long is also zeroed by every clear that ends at the arena's top (the stock `memset` writes one long past a length that is a multiple of 16; `docs/firmware/STEM_REC.md` section 19.1) | static |
| `0x47500a10` | an 8,704 B sector bounce buffer just below the rings (`0x4f500a10 − (offset & 511)` at `0x40091f94`) | static |
| `0x47502c10..0x47fc7410` | the stock delay rings, 10.8 MB: eight rings of 1,411,200 B (wrap `cmpil #1411200` at `0x4000359e`) at a stride of 1,411,328 (`addil #1411328` at `0x40003386`; 128 B, one 16-sample frame, of pad); the boot memset at `0x40002fb4` (`lea 0x4f502c10`, 705,664 × 16 B) ends at `0x47fc7410`; the delay frame routine's four `#0x4f502c10` adds. Stock never names `0x47502c10`; every reference is through the alias. Cleared ~38 M instructions after the boot detour returns; live audio memory after that. Not free | static + port + Bryan T's write-up (`docs/firmware/COLDFIRE_DELAY.md`) + mxldyn's hardware. An earlier "8.8 MB free at 0x47700000" was a watch on cached addresses blind to the clear through the alias: retracted |
| `0x47fc7410..0x47fe0000` | 101,360 B between the end of the rings and the 128 KiB Octakit kept below the reset stack (until 6 Oct 2026). Octakit's boot-time stage (72,959 B) at the bottom. Not clean: stock's engine task names four buffers inside it through the alias (`0x4ffc7610`, `0x4ffc9010` sector bounce buffers; `0x4ffcb220`, `0x4ffce230` two arrays of 769 × 16 B descriptors), and with static samples in the project the port fills `0x47fc8fe4..0x47fcd9e4` (18,944 B, 37 sectors, the PIO sector loop `0x40015472..0x4001548e`) at project load, inside her stage from `+0x1bd4`. Nothing seen above `0x47fcd9e4`; no literal names anything above `0x47fd1240` | measured on the port's PIO path; a DMA-capable card and play-time streaming unexercised. Em (12 Sep 2026): the stage is needed on boot only, so the fills after boot are a non-issue for Octakit; whether her wrapper's re-hash at project load (`0x40013304`) tolerates a clobbered stage is unconfirmed |
| `0x46000000..0x47502c10` | ~21 MB outside both big clears | unmeasured; stock's sample pool may live there. Measure with samples loaded and the recorder running before placing anything |

What the port cannot see: caches (it has none), the recorder, anything
after the handoff, and DMA traffic (the eDMA's descriptors and completions
are modelled but no bytes move, so a region only DMA writes to reads as
never written). The rings are known from the CPU's own memset.

### Em's DRAM (`m68k-elf-nm` on her `runtime.elf`; Octakit, until 6 Oct 2026)

| | range | bytes |
|---|---|---|
| runtime (code + data) | `0x45d0dde0..0x45d32675` | 149,653 |
| code budget (`0x25000`) | ends `0x45d32de0` | 1,899 spare |
| 256 Kits × 6,322 B (`PART_PAYLOAD_SIZE 0x18b2`) | `0x45d32de0..0x45ebdfe0` | 1,618,432 |
| 128 spill payloads (undo, clipboard, rollback) | `..0x45f838e0` | 809,216 |
| descriptors, bitmaps, names, UI rows, undo | `..0x45fb2f42` (`__gk_planned_end`) | ~190,050 |
| slack | `0x45fb2f42..0x4600154b` | 320,009 |
| backup copy of the runtime | `0x4600154b..0x46025de0` | 149,653 |
| her region (`RUNTIME_START..RUNTIME_END`) | `0x45d0dde0..0x46025de0` | 3,244,032 |
| her stage (signature + packed runtime) | `0x47fc7410..0x47fd910f` | 72,959 |

(Sizes as of her ec70dda; ot-26914's runtime is 154,718 B.)

## The platform reserve

Hardware: an image built at origin `9a49f21` (loader at `0x4010fdf0`,
boot site `0x4000050c`, the 10 MiB reserve at `0x40a955e0`, FX2 chooser
rebuilt with 15 rows at `0x400d7bbc`) ran on nordseele's Octatrack MKI on
11 Sep 2026 as octalab: the first hardware run of the DRAM platform, on
the model we cannot test. ❌ Retracted on that run: `FLASHPLAN.md`'s
"MEMORY reports ~75 MB" — the MEMORY page still shows 85.5 MB total while
the Flex list reads FREE MEM 71.4 MB; the page count `0x390a` appears at
18 sites and which one the page reads is unpinned. Their standalone cave
`0x400d64e0..0x400d7bf5` straddles the FX2 chooser's NONE row at
`0x400d6b00`; as a module they claim `LAB_MENU`, 402 B at
`0x400d64e0..0x400d6671`.

octabam's runtime and stage live in 1,707 pages (10,487,808 B) taken off
the bottom of the audio page arena, `0x40a955e0..0x41495de0`
(`tools/remix/arena.py`, `PLATFORM_PAGES`), the way octamax 2.0 takes its
64. The base literal moves up by that much at its 24 sites (23 direct plus
`lea base+6144` at `0x40094a62`), and the four geometry words (page count,
free-list fill limit, arena clear length, recorder page cap) are computed
from the reservation (`tools/remix/arena.py` stacks any number; until 6
Oct 2026 Octakit's 528 at the top were the other one, and the `octakit`
remix alone yielded exactly her four words `36fa / 36fb / 05278800 /
36fa`). `midi-scenes` yields base `0x41495de0` and 12,895 pages (75 MB)
left. The runtime is linked at the reserve's base; the stage follows it
page-aligned; the ceiling is the reserve's end; a unit's `.bss` must end
below it. KITS's library (1,622,944 B) and PLOCKS P2's table (1,572,864 B)
are `.bss` there.

The OS never touches a reservation again: the arena clear starts at the
new base, the boot-time copies follow the literal, and the page allocator
hands out only indexes below the new count. The cost is 10 MB of an
85.5 MB pool, off the recorder share by default.

Measured under the port on the static-sample card (boot → LOAD PROJECT →
400 frames): the `hello-dram` image reproduces the stock run to the count
(6,232 ATA commands, 30,573 sectors read, 292 written, the same five
tracks armed at frame 0, the same 18,005 bytes landing in the old top
window) with 0 writes into the reserve and the runtime read back
identical. The `midi-scenes` image has no stock write into the reserve
(28,700 writes, all from his own code: the MSC table and his state).

Against his 1.40MIDISC, same card, the `hello-dram` control rebuilt
bit-identical:

| image | ATA cmds | sectors read | written | armed at frame 0 |
|---|---|---|---|---|
| `hello-dram` (control) | 6,189 | 30,467 | 297 | 5: tracks 0,1,2,4,7 |
| midi-scenes 1.40MSC | 5,234 | 21,958 | 0 | 3: tracks 0,5,7 |
| midi-scenes 1.40MIDISC | 6,189 | 30,467 | 297 | 3: tracks 0,5,7 |

The card I/O difference was his: `bank_switch` / `bank_invalidate`
preserved only `d0` across a `jsr` that replaced a plain `move.l
d0,(BANK_PTR).l`; 1.40MIDISC saves `d1-d7/a0-a6`. The arming difference
was the port's: its saved-bank watch was keyed on the stock PC of the
`BANK_PTR` store at `0x40087d44`, which his cave makes from its own PC, so
the port played bank 0 pattern 0; with the watch following the detour,
1.40MIDISC5 and 1.40MSCN6 arm the control's five. His hardware symptom
("save on bank 1 reloads clean, others corrupt") is unmeasured here. (A
bisect that landed on `0x40087d44` and a PR to him built on it were
retracted.)

## The loader

`tools/remix/loader.S`, derived from Em's Octakit loader with attribution:
a stub at `0x4010fdf0` (the byte after the OS image) that the boot site's
`jsr 0x40001e50` is redirected into by octabam's three-byte poke. It
replays the boot-continue call, then for each payload in its table: copies
the staged blob (4-byte signature + `GKA3` stream) to its persistent stage
through the uncached alias, hash-gates the packed stream (rolling ×33, the
same function her OS-resident helper computes), checks the `GKA3` header,
depacks with the firmware's own aPLib routine at `0x400e0aca`, hash-gates
the result, and copies a backup if asked. Any mismatch hangs the boot
visibly. octabam's runtime is the one payload today (Octakit's runtime was
another until 6 Oct 2026).

`tools/verify/verify_dram_boot.py` (in `make verify`) boots the built image
under the port and checks that the loader ran once, never hit its hang,
and that every window reads back equal to its linked image except the
bytes a runtime writes about itself.

## Shared sites: the bridges

In the free ROM, SCALE QUANTIZER's 2,916 B unit beside REPITCH's 576 B
leaves CC MAP's 724 B cave no run (measured 28 Sep 2026), so `mods`
carries REPITCH and CC MAP without the quantizer.

A stock site claimed by two mods is refused by the ledger unless a bridge
carries it. A bridge is a stub that does what both hooks did, in an order
that respects each protocol, declared through `schema.Override` so the
build skips the overridden detour.

Until 6 Oct 2026 three bridges carried Octakit's shared sites:
`scenes-kits` (the MIDI CC dispatch entry `0x400d64a0`, CC MAP's cave in
front of her handler), `scenes-p2-kits` (the two page-2 editor entries)
and `kits-reload` (OKMS1 trapped on the first Part Reload: her
replacement of the stock reload validated its caller's return address and
midisc's `reload` stub substitutes it; the ledger carried the class as
`Runtime.pinned_returns` against `Detour.subst_return`). KITS leaves the
stock Part routines and the CC dispatch as stock, so none is needed (`git show 2063370f:modules/kits-reload/README.md`).

## Open

- More than 10 MB is a bigger `PLATFORM_PAGES` (the ledger refuses below
  2,048 pages left). The route that costs no sample memory (a remix with
  the stock DELAY off both choosers detouring its frame routine
  `0x400031a0` so the eight rings are never written, 10.8 MB) is
  unmeasured; whether the routine has duties beyond the delay is the
  question.
- `0x46000000..0x47502c10`: measure with samples loaded and the recorder
  running before placing there.
