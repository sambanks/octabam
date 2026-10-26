# Placement: where a module's code goes, and what is free

The OS is a fixed 1.1 MB block of Elektron's code. A module declares what
it is, not an address; the build decides which bytes land where.

## The two placement classes

| class | declared as | where it lands | budget |
|---|---|---|---|
| **ROM cave** | `CavePatch` (pinned hex, or a `.s` source that is the truth) | one of the OS image's free zero runs; floats after what precedes it unless pinned | ~8.4 KB total, shared by everyone |
| **DRAM unit** | `Linked(..., dram=True)` | linked with every other DRAM unit in the remix as one image, packed, appended after the OS behind octabam's loader, depacked at boot into the platform's arena reserve | the pages the remix claims (MEMORY), off the unit's sample/recorder pool |

Until 6 Oct 2026 there was a third, the appended runtime (`Runtime` + 
`ArenaReserve`): Em's Octakit, built from her recipe and carried as a
payload of the same loader in its own 528 pages of the arena. KITS
(`modules/kits`) replaced it; the class went with it (`git show
2063370f:tools/remix/schema.py`).

A DSP-side class exists for one kind of code (sanderlegit, PR #542):

| class | declared as | where it lands | budget |
|---|---|---|---|
| **Pinned DSP section** | `DspSection(pins=(...), pin_split_label=...)` | fixed P addresses instead of the harvested effect region: the interrupt vectors stock leaves as `jmp *`. One address per piece, cut at one label with a one-word bridge jump, so a section can span two runs and cost the region nothing | ✅ read from the image: payload A 50 dead words (`$02..$0F`, `$1A..$1B`, `$1E..$3F`), payload B 58 (`$02..$0F`, `$14..$3F`) |
| **Tail DSP section** | `DspSection(tail=True)` | where the payload harvests nothing: above the payload's code in internal P, in a load record of its own that a pre-boot copy of the payload carries (below) | payload A 33 words (`$1fdf..$1fff`), payload B 609 (`$1da0..$1fff`); costs a DRAM region of about twice the payload |

Stock's unused vectors are self-jumps: an interrupt that fired there would
spin the core in it for good, so stock never enables them.
`tools/verify/verify_dsp_vectors.py` checks that on every build (the runs
are all self-jumps; no DMA whose vector is in one has DIE set; no ESAI
control word has an interrupt enable; the set of peripherals either
payload configures is the audited one), and that gate is the licence for
the class. The build refuses to pin over anything that is not still the
stock pattern and asserts that both pieces assemble to the same length at
either origin. The ledger claims the pin by name.

REMIX SWITCH's DSP park is the one user: 31 words at `P:$20..$3E` (entered by
`jsr` at `P:$1E`, host command `$0F`), a one-word bridge, and 8 words at
`P:$06..$0D`. `$02` (stack error) and `$04` (illegal instruction) stay
stock's freeze-traps. ✅ On an MKII, 29 Sep 2026: an image with stock's
fourteen effects and the park wholly in dead vectors booted from a switch,
played, and switched away again, so the chip runs code in the
exception-vector slots and takes the bridge jump between two runs.

The top of P is free. ✅ Measured 29 Sep 2026: the core's default map gives
8K words of P (`0x2000`; and 25 Oct 2026 on the unit: a word written at
`P:0x2000`, `0x2100`, `0x2400`, `0x2800`, `0x3000` or `0x3800` does not read back,
while the spare `P:0x1fe0` does, `modules/pextprobe`); payload A's code ends at `0x01fdf` (33 words
spare, `0x01fdf..0x01fff`), payload B's at `0x01d9f` (609). Stock's low P
is full: A loads all 8,159 words in 66 records, B all 7,583 in 46, with no
holes. No record covers the spare words, and growing payload A's blob in
place would shift B (it begins on the byte A's ends), the
`FUN_40001b18(0x400f59ef)` call site, the boot copy and the immediates in
the bootstrap-reprogram path at `0x40000450` (A's size `0x136cb` at
`0x40000476` and `0x400004d4`, `79563` at `0x40000488`, B's address at
`0x400004b0` and `0x40000500`; that path runs only when `0x3ffc` is below
`0x400dea48`; Sam B, #854).

**The tail** (`DspSection(tail=True)`, 22 Oct 2026) reaches it without
moving anything. The normal boot hands the DSP loader only a pointer
(`pea 0x400e2324; jsr 0x40001b18`, the pointer at `0x40001e8e`; B's at
`0x40001ed4`), and the records end at the first space word above 2. Where
a payload harvests nothing (every stock effect kept), the build assembles
a tail section at the first word above the payload's internal-P records,
splices one P record holding it in front of a COPY of the payload's
terminator, ships the copy as a pre-boot payload of octabam's loader into
a DRAM region of the platform arena (`dsp_tail_A`: the payload's length
plus 4 KB, twice, unpacked then packed: 167,318 B, 28 pages for payload
A), and pokes the pointer at it: the route ANALOG BD's builder
(`tools/build/ab_image.py`) takes for its X record. Stock bytes and
payload B stay where they are. A remix with a donor region places the
section there instead, so no remix that built before moves a byte. USB's
RX inject (29 words) is the one user; `remixes/test/usb-io-stock14`.
✅ On an MKII, 22 Oct 2026 (Bryan T, OCTABAM4): the inject at
`P:$1fdf..$1ffb` delivered the host's four channels as the donor-region
inject does (`tools/hw/usb_in_tones.py`), so the chip runs code at the top
of internal P and the DSP boots from the poked pointer's copy. Refhash: all
24 configurations bit-identical with the change.
Not covered: the reprogram path above uploads from its immediates, so if
it ever ran it would load payload A without the tail record (ANALOG BD's
uploads have the same exposure); and tools that read a payload from the
image's own records (`dsp_modmap`) do not see the tail.

The OS-image edits every class needs (a detour at a stock instruction, a
poke, a grown table) are `Detour`, `Poke`, `TableGrow`, wired by symbol;
stock bytes a module relies on without writing are a `Keep`.
`tools/remix/ledger.py` refuses two modules that claim one byte before
a byte is written.

## Code in the shared window (measured 25 Oct 2026, unmeasured where marked)

A DSP core's P ends at `P:0x1fff` on the default map (`DSP.md` section 3), so
code that is not in the image's P records has to run from the shared window,
`P:0x30000..0x3ffff`. ✅ On the unit (PEXT PROBE v2, image P2, 25 Oct 2026,
`modules/pextprobe`): each core wrote a three-word routine (`move #>$a5a5a5,x0`
/ `rts`) at `P:0x30100`, `0x35900`, `0x36300`, `0x36800`, `0x37000`, `0x37800` and
`0x37e00`, called it with `jsr (r5)` and read `x0` back: seven of seven, on core 0
(track 5) and on core 1 (track 1), so core 1 runs code that sits in payload A's
half. The window is one memory: the words are visible to both cores, so one copy
of a routine serves both.

Which words are free, from `tools/remix/dsp_ranges.py` (the ledger's claims, not a
measurement):

| remix | payload A's half `0x30000..0x37fff` | payload B's half `0x38000..0x3ffff` |
|---|---|---|
| `octabam-bus` | free: `0x30048..0x30800` (1,976 words), `0x35800..0x36000` (2,048), `0x36200..0x37f00` (7,424); 11,448 in all. Owned: stock staging `0x30000..0x30048`, BusVerb `0x30800..0x35800`, the bus scratch `0x36000..0x36200`, the mailbox `0x37f00..0x37f10`, LOAD METER's figures `0x37f10..0x37f50` | BusDelay's LineL, all of it |
| `octabam-inserts` | MODULATION and GATE VERB claim the whole half as the allocator's FX2 buffers (`Claims.stock_instance_buffer`); the tail a given effect leaves unused is not in the ledger | the same |

Not measured: the cost of running an effect from the window (`CHIP.md` records one wait
state as P against none as X or Y, and contention per 8 K block when both cores use the
same block), and whether the stock effects a remix keeps use any of the words
the ledger shows as free.

The other lever in `CHIP.md` is the OMR memory switch (MS, MSW1:MSW0), which would give
a core 16 K, 24 K or 32 K words of P at the cost of Y (48 K, 40 K, 32 K, 24 K);
nothing writes OMR in either payload and it has not been tried. The bus remix's
BusVerb and BusDelay own `Y:0x4000..0xc000` on each core.

## The 64-id layout

`Remix.id_space = 64` (`tools/build/idspace.py`). The build works on the stock
layout throughout, writes the tables it grows into a virtual window, and
`idspace.convert` turns the finished image into this layout:

- Each payload gets one more X load record at `X:0x8da0` (129 words:
  INIT[64], PROC[64], a spare), appended before its terminator (+396 B each).
  The six `move x:(r1+$215|$235),r2` words of the dispatcher (A `P:0x4b4`,
  `0x4cb`, `0x4ce`, `0x4ea`, `0x501`, `0x504`; B `0x2a9`, `0x2c0`, `0x2c3`,
  `0x2df`, `0x2f6`, `0x2f9`) are repointed. The old record stays, holding the
  entries for ids below 32, so tools that read `X:0x215` see them.
- B moves by A's growth. The boot copy sites take the new lengths and starts
  (`0x40000478`, `0x4000048a`, `0x400004d6`: A; `0x400004ac`, `0x400004fa`: B;
  `0x400004b2`, `0x40000502`, `0x40001ed4`: B's start). The image keeps its
  size: B's end now covers the head of the SRAM-init image (`0x401086f4`
  onward), whose first 792 bytes are zero but for eight at offset `0xe8`. The
  routine at `0x4000f938` that copies that image to SRAM is replaced by a
  60-byte cave at `0x400d797c` that zeroes the covered head, writes the eight
  bytes and copies from B's new end.
- `FX2_IDS` and `ID2POS` are written at `0x400d79bc` and `0x400d7abc` (256 B
  each, just below the long chooser list) and the nine stock `lea` sites that
  read them (`idspace.LEA_SITES`) are repointed. The three regions are
  reserved: the build ends its caves at `0x400d797c`. FX1's tables stay at
  their stock addresses.

Measured in the port (22 Oct 2026): the image boots and loads a project as
stock does; id `0x25` poked into T1 makes core 1 run BBD's process entry every
frame with `r1 = 0x25`; the firmware's resolver `0x40031da4` returns BBD's
descriptor for it; `make check REMIX=ids64` passes. Not measured: a boot on
hardware, that `X:0x8da0..0x8e21` is physical X RAM on the chip (X above
`0x8d8b` holds no loaded record today and `docs/firmware/DSP.md` section 7
says high X is not usable memory), the chooser and UI with ids of 32 or more,
and the FX1 side. A 62-byte per-frame SRAM buffer at `0x800017d6` differs
between the stock and the grown image after the same emulated time (the stock
image is deterministic; the cause was not confirmed).

Hardware step 1 was run on 27 Oct 2026 (an MKII, image `test/bus-usb` P3: the `bus` remix with USB added, REVERB SERVER
replaced by `dsp/xmem_probe_ids64.asm`; T5 playing a noise loop, captured over USB). T5's left channel carried signal and
its right channel had no non-zero samples, and MAIN, which is T5 at the centre pan law, matched. By the
probe's rule that is: the 129-word record `X:0x8da0..0x8e20` read back every walking value (good), and the 1,024 words above
it (`0x8e21..0x9220`) did not. The one block the layout needs behaves as X RAM; the memory above it does not read back, so the
record would sit at the end of the X RAM that exists (inferred from the two results). This shows the words behave as RAM while the probe runs; it does not show
that stock never uses them for something else. An earlier build on the `bus` remix without USB (image P1, flashed, not
measurable) is not used.

Hardware, in this order (each step isolates one unknown; step 1 is done):

1. `X:0x8da0..0x8e20` is X RAM. `XBUS=1 XPROBE=1 XPROBE_SRC=dsp/xmem_probe_ids64.asm
   REMIX=bus python3 tools/build/build_bus.py` builds a stock-layout image whose
   REVERB SERVER is `dsp/xmem_probe_ids64.asm`: half volume on a track carrying
   it (T5-T8) is both blocks good, LEFT silent is the 129-word block bad, RIGHT
   silent is the 1,024 words above it bad. The probe builds; it has not been
   rendered.
2. The grown image boots: `make image REMIX=ids64`, load a project, play. This
   exercises the shifted blob chain, the lengths the boot copy takes and the
   SRAM-init cave.
3. BBD selected on id `0x25` from the chooser on a track: audible, knobs
   respond, the stop kill silences it (`kill.s` compares against the id the
   remix gave it).

## The free ROM (measured)

Zero runs inside the OS image (`0x400c0000..0x400d8000` scanned for runs
≥ 64 B). The region above `0x400d8000` reads zero but is the PROJECT
subsystem's RAM and is refused: octalab put a menu table in the 15 KB zero
run at `0x401087e4` and the unit raised `VEC:03` in the menu draw loop
(octalab, 13 Sep 2026).

```
0x400c45b0..0x400c4702     338 B
0x400d24d0..0x400d2ce0   2,064 B   (the first words are READ by the stock DELAY as table data: its
                                    coefficient table ends here and an index up to 511 runs past it;
                                    a cave there changes the DELAY's output. Measured 21 Oct 2026, issue #771.
                                    Keep 0x400d24d0..0x400d24df zero.)
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
| `0x40a955e0..0x46025de0` | the audio page arena: 14,602 × 6,144 B = 89,720,832 B = 85.56 MiB, Elektron's "85.5 MB" (cold init `0x40096f7a`: count `0x390a`, free-list fill to 14,603, `memset(0x40a955e0, 0x05590800)` at `0x40097006`; the Flex cap is the `0x04000000` literal at `0x40004028`). Octakit took the top 528 pages (until 6 Oct 2026), octamax 2.0 the bottom 64 (base moved to `0x40af55e0`), the platform reserve the bottom pages its remix claims (1,707 in every DRAM remix until 11 Oct 2026; MEMORY) | measured; both authors' placements hardware-proven |
| `0x45d0dde0..0x46025de0` | Octakit's window until 6 Oct 2026 ("reserved recorder pages"). Stock's engine zero-fills exactly this extent at project load, twice; her post-clear relocation re-depacks from a stage the OS never touches | measured |
| `0x46025de0..0x4763d580` | zero-filled at boot by the loop after the boot detour (`0x40000518`); the base of stock's object pool (`pool_init(0x46025de0)` at `0x4002000e`): globals and heap. Not free; its first long is also zeroed by every clear that ends at the arena's top (the stock `memset` writes one long past a length that is a multiple of 16; `docs/firmware/STEM_REC.md` section 19.1) | static |
| `0x47500a10` | an 8,704 B sector bounce buffer just below the rings (`0x4f500a10 − (offset & 511)` at `0x40091f94`) | static |
| `0x47502c10..0x47fc7410` | the stock delay rings, 10.8 MB: eight rings of 1,411,200 B (wrap `cmpil #1411200` at `0x4000359e`) at a stride of 1,411,328 (`addil #1411328` at `0x40003386`; 128 B, one 16-sample frame, of pad); the boot memset at `0x40002fb4` (`lea 0x4f502c10`, 705,664 × 16 B) ends at `0x47fc7410`; the delay frame routine's four `#0x4f502c10` adds. Stock never names `0x47502c10`; every reference is through the alias. Cleared ~38 M instructions after the boot detour returns; live audio memory after that. Not free | static + port + Bryan T's write-up (`docs/firmware/COLDFIRE_DELAY.md`) + mxldyn's hardware. An earlier "8.8 MB free at 0x47700000" was a watch on cached addresses blind to the clear through the alias: retracted |
| `0x47fc7410..0x47fe0000` | 101,360 B between the end of the rings and the 128 KiB Octakit kept below the reset stack (until 6 Oct 2026). Octakit's boot-time stage (72,959 B) at the bottom. Not clean: stock's engine task names four buffers inside it through the alias (`0x4ffc7610`, `0x4ffc9010` sector bounce buffers; `0x4ffcb220`, `0x4ffce230` two arrays of 769 × 16 B descriptors), and with static samples in the project the port fills `0x47fc8fe4..0x47fcd9e4` (18,944 B, 37 sectors, the PIO sector loop `0x40015472..0x4001548e`) at project load, inside her stage from `+0x1bd4`. Nothing seen above `0x47fcd9e4`; no literal names anything above `0x47fd1240` | measured on the port's PIO path; a DMA-capable card and play-time streaming unexercised. Em (12 Sep 2026): the stage is needed on boot only, so the fills after boot are a non-issue for Octakit; whether her wrapper's re-hash at project load (`0x40013304`) tolerates a clobbered stage is unconfirmed |
| `0x46000000..0x47502c10` | ~21 MB outside both big clears | unmeasured; stock's sample pool may live there. Measure with samples loaded and the recorder running before placing anything |
| inside the row above | fixed firmware buffers named by static reads (addresses are the uncached alias; cached = minus `0x08000000`). Sizes unmeasured. `0x4ec94004`/`0x4ec94008`: READ CAPACITY(10) reply, 8 B (`0x4001e350`, `0x4001e35a`). `0x4ec94800`: USB dQH list (`usbaudio_in.s`). `0x4ec94900..`, `0x4ecc8000`, `0x4ecc9000`: EP2 dQHs, dTDs and buffers (`modules/usb/README.md`). `0x4ecb8000`: the USB mass-storage worker's sector buffer (`0x4001eed8`, `STEM_REC.md` section 7.7). `0x4ecd3000`: the buffered file layer's staging buffer (`STEM_REC.md` section 7.5) | static; not placed on |

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

octabam's runtime and stage live in pages taken off the bottom of the
audio page arena at `0x40a955e0` (`tools/remix/arena.py`), the way
octamax 2.0 takes its 64. MEMORY (`modules/memory/README.md`) sizes the
reserve per remix from the claims: the linked runtime, its stage and
`.bss`, every DramRegion and every fixed-address ArenaReserve (a fixed
1,707 pages, 10,487,808 B, `0x40a955e0..0x41495de0`, until 11 Oct 2026).
The base literal moves up by that much at its 23 sites (22 direct plus
`lea base+6144` at `0x40094a62`; the literal's other use, `cmpal` at
`0x400254f8`, is the end of PURGE SAMPLES' walk over the banks and stays
stock: moved, the walk ran off the end of RAM, `tools/remix/arena.py`), and the four geometry words (page count,
free-list fill limit, arena clear length, recorder page cap) are computed
from the reservation (`tools/remix/arena.py` stacks any number; until 6
Oct 2026 Octakit's 528 at the top were the other one, and the `octakit`
remix alone yielded exactly her four words `36fa / 36fb / 05278800 /
36fa`). `midi-scenes` yields base `0x41495de0` and 12,895 pages (75 MB)
left. The runtime is linked at the reserve's base; the stage follows it
page-aligned; the ceiling is the reserve's end; a unit's `.bss` must end
below it. KITS's library (1,622,944 B) and PLOCKS P2's table (1,572,864 B)
are `.bss` there.

**REMIX SWITCH's stage** (`modules/remix-switch`) is the top of this reserve,
`0x41200000..0x41495de0`: a 64-byte mailbox, a 40-byte copy stub at
`+0x100`, the staged image from `+0x1000` (2,706,400 B). The running OS
writes it just before a reset and the next boot's OS entry reads it before
anything else runs; nothing between a reset and the OS entry writes SDRAM
outside the image the bootstrap unpacks (`docs/firmware/ARCHITECTURE.md`
section 3a). In a remix carrying the module, `verify_remix_switch` refuses a
runtime and stage that reach the mailbox.

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

- The reserve is what the remix claims (MEMORY); the ledger refuses
  claims that leave fewer than 2,048 pages. The route that costs no sample memory (a remix with
  the stock DELAY off both choosers detouring its frame routine
  `0x400031a0` so the eight rings are never written, 10.8 MB) is
  unmeasured; whether the routine has duties beyond the delay is the
  question.
- `0x46000000..0x47502c10`: measure with samples loaded and the recorder
  running before placing there.
