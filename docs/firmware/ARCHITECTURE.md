# Elektron Octatrack firmware architecture (OS 1.40C, ColdFire side)

Hardware, OS format, kernel, storage, audio engine, sequencer and memory
map, as verified. ✓ = checksum from the firmware itself, byte-exact
decompilation or direct disassembly; ~ = inferred. The DSP side is
`docs/firmware/DSP.md`; the tools are in `docs/contributing/TOOLING.md`.

## 1. Summary

An 8-track sampler/sequencer. The firmware runs on a Freescale ColdFire
CPU (68k family, big-endian, 266 MHz) with a two-core Freescale DSP56xxx
for real-time audio, under a proprietary preemptive microkernel. The OS
lives in NOR flash, packed, and the bootstrap unpacks it into SDRAM at
every reset (section 3a); the CompactFlash carries projects, samples and the
`.bin` an OS UPGRADE reads. (❌ Retracted 29 Sep 2026: "the OS is loaded
from CompactFlash via the ColdFire's on-chip ATA controller" -- the unit
boots to DEMO without a card, and the bootstrap's load reads NOR.) The
architecture is producer/consumer decoupled by buffers in RAM: the same
kernel message-queue pattern appears in storage I/O and in the audio
pipeline.

## 2. Hardware

| Component | Detail | Confidence |
|---|---|---|
| CPU | Freescale ColdFire **MCF5445AVR266** (32-bit, big-endian, 266 MHz) | ✓ (board photo; the on-chip ATA controller at MBAR `0xFC04_51xx` is the MCF5445x's) |
| Audio DSP | Freescale Symphony **DSP56721** (`DSPB56721AG`): two DSP5636x cores, 200 MHz each, no external memory controller | ✓ (board photo) |
| RAM | 128 MB SDRAM at `0x40000000` (`docs/contributing/PLACEMENT.md`) | ✓ |
| Storage | CompactFlash (FAT16/32), OS and data; boots to DEMO without CF | ✓ |
| NOR flash | CS0 at `0x00000000`, 8 MB decode; Spansion S29GL-N ID check, size not read (section 3a) | ~ |
| Expansion bus | FlexBus (chip selects for ATA, DSP, RAM) | ✓ |

## 3. OS format and update chain ✓

Elektron distributes a ZIP with two transports of the same OS, a `.bin`
and a `.syx`; both wrap one compressed container that decompresses to the
MAIN OS (1,112,560 B, SHA256 `164f3122…`).

```
.bin  = [ELUP hdr][seed] + XOR-feedback( [len] + ELEK( aPLib( MAIN OS ) ) ) + checksum
.syx  = SysEx 7-bit(              ELEK( aPLib( MAIN OS ) )              )
```

- ELUP (`.bin`): XOR obfuscation with feedback (constants
  `0x9E3B16A2`/`0x764E28CA`, mixers `C3=0x360FA955`/`C7=0xEF4A9AB6`) and an
  additive checksum. `tools/build/bin_decode.py` reimplements it; the
  firmware's own checksum validates the result.
- ELEK: a container with a section compressed in aPLib.
- No cryptographic signature in any layer; `elektron-firmware-tool`
  rebuilds a `.syx` with recalculated checksums.

OS validation on update (`FUN_4007f748`), error codes: `-1` IO, `-2` not
a valid OS, `-3` length, `-4` checksum, `-5` MK1 not allowed (version code
< "0156"), `-6` cannot downgrade (< "0178"). The MKI and MKII download
pages serve the byte-identical 1.40C file (SHA256 `370c55a3…`), so `-5`
compares the incoming file's version code and rejects pre-unification
MK1-era files (inferred); octabam images keep code 0178.

UI → write flow: OS UPGRADE menu → confirm → `os_upgrade` (stops audio,
"WORKING PLEASE WAIT", enqueues a task) → scans the CF, validates →
`os_apply_flash` (critical section) → writes NOR → reboot. ✓ Read 29 Sep
2026 (`docs/proposals/FIRMWARE_SWITCHER.md`): the menu handler
`0x400636bc` stops playback (`0x40063660`) and defers `0x4006370c` →
`0x40080640`, which lists `/*.BIN` (`0x4007f598`) and keeps the best
validation result; the file is read in 8-sector chunks through the
uncached bounce buffer `0x4f4ede10` into `0x46949e80` (the task stacks,
which is why the flow never returns), decoded in place, programmed and
verified word by word against NOR from `0x4000` (`0x4007fcb2..`). A file
over 1 MB + 12 B is refused (`-3`, `0x4007f796`). The reboot is
`move.w #0x2700,%sr ; jsr 0x40010a4c` (flush the panel's UART1 queue) `;
bra .` (`0x4007fe6c..0x4007fe7c`), after the screen `UPGRADE DONE` /
`PLEASE REBOOT!` (`0x4007fab4`): stock never resets the unit, the user
power-cycles. (❌ Retracted: "writes the CF via ATA"; and, the same day,
this doc's "something resets the unit from there, probably a watchdog":
an MKII sat in that kind of spin until a power-cycle, OS SWITCH build 1,
29 Sep 2026.)

## 3a. NOR flash ~

Read from the 1.40C MAIN OS image (objdump listing, absolute-operand
scan), 24 Sep 2026, after Andreas (Discord) reported an 8 MB NOR with
~1.1 MB used. Nothing here is measured on a unit. objdump decodes the
bootstrap copy and the ID-check region misaligned, so the addresses
given for entry points there are ± a few bytes.

**Chip select.** The bootstrap init (`0x400e0a1c..`) sets CSAR0 = 0,
CSMR0 = `0x007F0001` (8 MB decode, valid), CSCR0 = `0x0C8015B0` (16-bit
port, 5 wait states). A decode size is not a part size: SDCS0 decodes
256 MB over a 128 MB SDRAM (`docs/contributing/PLACEMENT.md`). CS1 =
`0x10000000`, 1 MB decode; CS2 = `0x20000000`, 256 MB decode.

**Part.** JEDEC command set: unlock writes at byte `0xAAAA`/`0x5554`
(word `0x5555`/`0x2AAA`; only A10:A0 are decoded, so Spansion's
`0x555`/`0x2AA` parts accept them), sector erase `0x80`/`0x30` polled
for `0xFFFF`, word program `0xA0` polled for data. The OS reads the ID
(`~0x400202f4`): manufacturer `0x0001` and device `0x227E` set
`0x400b9874` = 1 and select write-buffer programming (`0x25`, 128 words,
`0x29`); any other ID programs word by word. So at least two parts are
expected across production. `0x227E` is the Spansion S29GL-N family
(S29GL064N / 128N / 256N = 8 / 16 / 32 MB); the extended ID words that
tell them apart are never read, so the part size is not known from the
image.

**Layout.**

| Flash range | Contents | Source |
|---|---|---|
| `0x000000..0x003fff` | bootstrap, linked at 0; its copy sits in the OS image at `~0x400de7dc..0x400e21e0` and carries the "BOOTSTRAP UPGRADE" string and the SysEx OS upgrade path. ✓ The OS entry programs `0x400dea4c..0x400e1ec4` into it from `0` when NOR's version word `0x3ffc` is below the image's `0x400dea48` (`0x0408` in 1.40C), or the PLL reads other than 264 MHz (`0x40000432..0x4000044c` → `0x4000f9b4`) | ~ / ✓ |
| `0x004000..0x1fffff` | the OS region: the OS's sector table at `0x400a91c0` has 37 entries, `0x4000`, `0x6000..0xe000` (6 × 8 KB), `0x10000..0x1f0000` (31 × 64 KB) = 2,080,768 B. The bootstrap's SysEx path programs the OS from `0x4000` (`0x400e011a..`, `pea %a0@(16384)`, +2 per word). The table is followed by "ELFU" and the `.bin` cipher constants (section 3) | ~ |
| `0x1ffffa..0x1fffff` | three words: magic `0x1234` at `0x1ffffa`, two words after it; the bootstrap also programs `0xabcd`/`0xdcba` markers here | ~ |
| `0x200000..` | magic "EFGH", a count n, then n × 28-byte records, copied to `0x46ceb400` by `0x4001b9b4`; contents unidentified | ~ |
| above the EFGH table | no reference in the OS image | ~ |

~ The window holds the OS PACKED: the bootstrap unpacks it from NOR `0x4012`
(its depacker at `0x207e` skips an 8-byte header; the OS image carries the
same routine at `0x400e0aca`, which `tools/remix/loader.S` calls) into
`0x40000400`, and stock 1.40C's `.bin` is 470 KB. Roughly 1.6 MB of the
window is unused by 1.40C, and OS UPGRADE refuses a file over 1 MB + 12 B.
(❌ Retracted 29 Sep 2026: "the current MAIN OS is 1,112,560 B, 53% of the
2,080,768 B window; 968,208 B of the window is unused" -- it measured the
unpacked image against the window that holds the packed one.)

✓ **The reset path** (the bootstrap, read at its copy in the image, 29 Sep
2026): reset vector `0x2d4a` → PLL, RAMBAR1 → `0x2920` (GPIO, the SDRAM
controller at `0x288e`: precharge, two refreshes, mode register; the panel
link; the Startup Menu on a held key) → `0x22a2` (caches on, unpack NOR
`0x4012` → `0x40000400`, ACR0/ACR1 = 0, `CACR = 0x0008c000`) → `move.l
0x8000050a,-(%sp) ; jsr 0x40000400`. Nothing on it clears or tests SDRAM
outside the Startup Menu's TESTMODE (`0x784`, `0x834`), so what the OS
image does not cover keeps its contents across a reset if the refresh gap
is short enough (~, unmeasured). A second entry at `0x22ea` unpacks from
RAM `0x40200000` instead, behind a `halt` (a debugger path; `0x10adc0de`).
`modules/os-switch` builds on this path.

**Constraints on using it.**

- The OS executes from SDRAM (load base `0x40000400`, section 7), not in place
  from flash. Code stored in flash runs only after something copies it to
  RAM: the bootstrap does this for the OS region (✓ `0x22a2` → `0x207e`, above); anything above
  `0x200000` needs its own loader (the DRAM platform's boot detour is
  where one would sit, `docs/contributing/PLACEMENT.md`).
- An image up to 2,080,768 B fits the region the OS already erases and
  programs. Past that, the image would overwrite the `0x1ffffa` words
  and the EFGH table, and the OS's sector table ends at `0x1f0000`.
- The bootstrap at `0..0x3fff` holds the SysEx upgrade path; erasing or
  mis-programming it removes the recovery route for a bad OS image.
- Erase granularity above `0x10000` is 64 KB. S29GL-N datasheet figures
  (part not confirmed on a unit): ~0.5 s typical per sector erase,
  100,000 erase cycles per sector. A setting stored in flash rewrites a
  whole sector per change; the card is the store for anything written
  often (samples, recordings, projects).
- The OS's own upgrade flow stops audio before it writes (section 3). Whether a
  program or erase can run with audio running is not measured.
- Capacity: 8 MB decoded; the part may be larger than the decode, and a
  larger part's upper half is unreachable at this CSMR0 setting. Sample
  storage stays on the CompactFlash (8 MB = ~95 s mono or ~48 s stereo at 16-bit 44.1 kHz).

**To find out.**

- The contents from `0x200000` to the end of the decode, and the EFGH
  records: a read-only dump (a DRAM module copying `0..0x7fffff` to the
  card) answers both.
- The part fitted (8 / 16 / 32 MB): the extended ID words at `0x0E`/`0x0F`
  in autoselect mode.
- The bootstrap's own erase loop runs 21 entries from a table at flash
  `0x2e38`, which the image copy does not carry. 21 sectors from `0x4000`
  would end at `0xfffff`, below the end of the current OS.
- ~~Which device `os_apply_flash` writes~~: NOR, verified word by word
  from `0x4000` (section 3, 29 Sep 2026).
- ~~What resets the unit after OS UPGRADE's final spin~~: nothing; it asks
  for a power-cycle (section 3).
- ✅ A soft reset (RCR SOFTRST) restarts the ColdFire and the bootstrap,
  and keeps SDRAM, but does not reset the DSP: the next OS's DSP upload
  (`0x40001e50`) starts and never returns (BOOT TRACE on the unit, OS
  SWITCH build 4, 29 Sep 2026; `docs/contributing/FAILURE_MODES.md`). ❌ Retracted the same
  day: "does not reset the MKII's panel controller" (the panel was never
  the hang; ❌ also retracted: "the unit is flagged an MKI", read from a
  handshake note that appears on only some boots). ✅ What the DSP needs
  after it, measured on the unit (OS SWITCH builds 12-14): the host-side
  receive register drained, HPCR bit 7 cleared, and each core parked in a
  loader that hands the upload to the stock bootstrap
  (`docs/contributing/FAILURE_MODES.md`).
- ~~Whether SDRAM keeps its contents across that reset~~: it does. OS
  SWITCH's 1.1 MB stage passed its hash after the reset and the staged
  image ran (BOOT TRACE, builds 4-14; the dialog reported the switch,
  build 14, 29 Sep 2026).

## 4. Kernel: a proprietary preemptive microkernel ✓

No third-party RTOS signatures (banner `ElektronOctatrack DPS-1`).

- Task Control Block: state @`0x13` (0 = blocked, 1 = ready), priority
  @`2`, list pointers @`0`/`1`. Current task `_DAT_800068fc`; top priority
  `_DAT_800068d8`.
- Per-priority ready queues (doubly-linked circular lists).
- Context switch via `TRAP #0` (`FUN_40000818`, wait/yield).
- Message queues with blocking receive (`FUN_40000c3c`, post): wakes the
  waiting task and forces a reschedule with `0xFC04_C010 |= 0x800`.

Scheduler (`FUN_4000056e`, reached by `TRAP #0` and by the timer): saves
D0-D7, A0-A7 into the current TCB at `0x0c`-`0x4b` (SP at `0x48`; SR
travels in the exception frame the `rte` pops; layout in
`git show 3ceba41:docs/history/RTOS_FORK.md` section 2); takes the highest-priority ready task;
clears the reschedule bit and re-arms the PIT `0xFC08_0000` (reload
`0xb3f`), the time-slice quantum; switches `_DAT_800068fc` and restores.
The ATA async queues and the audio voice mailboxes are its message
queues.

## 5. Storage: the ATA/CompactFlash stack ✓

```
filesystem → async command queue (FUN_4001568c, +event) → dispatcher (FUN_40015098)
 → dispatch by ATA opcode → handler → ATA task-file registers @ 0x90000000 (PIO)
```

ATA commands dispatched: `0x20` READ SECT, `0x30` WRITE SECT, `0xC8` READ
DMA, `0xCA` WRITE DMA, `0xE0` STANDBY. A driver vtable (`FUN_40015e28`)
with hardware variant detection from an IDENTIFY descriptor. Task-file
registers at `0x9000_00xx`: data `a0`, seccount `a8`, LBA `ac/b0/b4`,
device `b8` (`|0xE0` = LBA), command `bc`, status `d8` (BSY/DRDY/DRQ). ATA
host control in the MBAR `0xFC04_51xx`. Above it: the filesystem vtable,
the slot loader and the card's files, `STORAGE.md`.

## 6. Audio engine and sequencer ✓

Engine data structures, all in the `0x80000000` RAM window:

| Structure | Address / layout |
|---|---|
| Per-track voice state | base `0x800049d8`, stride `0xA8`, ×8; byte[0] = active |
| MIDI track state | `0x80006500[t]`, global `0x800065b8` |
| Voice command mailboxes | `0x46c7e9fa` / `0x800018be` / `0x800018de` `[t*4]` |
| Per-track pattern data | `_DAT_46c82456 + pattern*0x18b2 + track*0xc` |
| Globals | current track `0x100b14cc`, current part `0x80000003` (mirror `0x100b14cf`), current pattern `0x80000004` |

Control path:

```
sequencer trig
 → FUN_40005178 writes a voice mailbox: quantised actions are staged at
   0x800018be/de and moved into the immediate array 0x46c7e9fa by the
   per-tick comparator at 0x4000b308 when their quantise class fires
   (RECORDER.md)
   → the frame ISR 0x4000aad0..0x4000d9b0, its frame builder (control
     rate; "FUN_4000c8a4" is mid-operand, MIDI.md): consumes mailboxes,
     updates 8 voices, assembles a parameter frame in a double buffer in
     shared RAM 0x80000000 (ping-pong 0x800000e0)
     → the DSP host port at 0x20000000
       → the DSP reads the frame and synthesises (playback, time-stretch,
         filters, FX)
```

**The DSP interface at `0x20000000`** is the HI08 host-side register file
of the core the GPIO byte at `0xfc0a400c` selects: one byte register per
4-byte stride on a 16-bit FlexBus port (CS2, `CSCR2 = 0x180`); a 16-bit
bus cycle delivers its two bytes to two adjacent registers (measured under
the port, `git show 3ceba41:docs/history/COLDFIRE_PORT.md`; an earlier reading of "command
0x81 / 0x8C, status bit 6" is retracted):

- `0x2000_0000` ICR: `0x81` = INIT|RREQ, an interface reset before each
  upload
- `0x2000_0004` CVR: `0x8c` = host command HC | vector 0x0c (P:0x18) once
  per frame; `0x88` / `0x89` = vectors 0x10 / 0x12, "DMA a block in / out";
  bit 7 (HC) polled until the DSP takes it
- `0x2000_0008` ISR: bits 1|2 (TXDE|TRDY) polled before every word, bit 0
  (RXDF) for a reply
- `0x2000_0014`/`0x18`/`0x1c` TXH/TXM/TXL (RXH/RXM/RXL on read): a halfword
  write to `+0x1c` sends TXH:D15:8:D7:0 as one 24-bit word, a longword
  write sends two; the per-frame blocks are 16-bit values, two per
  longword

**DSP boot** (`FUN_40001d4c`): uploads the program 3 bytes at a time
(24-bit words) through the port with a handshake on TXDE|TRDY, after an
interface reset. Args: program, length, load address. The first 50/58
words go to the chip's own HI08 bootstrap ROM (count, address, words,
jump); the payload then goes through that bootstrap's loader, which echoes
each record's space word. The payloads live inside the MAIN OS image;
`docs/firmware/DSP.md` sections 1-3.

**Trig → voice** (`FUN_400977cc`, dispatched by machine type): reads the
track's machine state (`FUN_40097168` → 0-4) and emits the voice command
via `FUN_40005178` with flags (`0x80` start, `0x10`/`0x8010`/`0xf010` =
one-shot/hold/stop/retrig, labels unverified; the recorder's TRIG-mode
branch at `0x40083544` posts the same bits).

### ColdFire time per frame

Jannik Aßfalg's exclusive profile (23 Sep 2026). 🟡: his port build carries a
`--work-profile` PC counter that is not in this tree.
- Fixture: eight FLEX tracks looping a 440 Hz sample at 120 BPM, trigs on
  steps 1–4, DELAY on T1–T7, PLATE on T8.
- 5,600 frames after a 20 s load.
- The counts are instructions, not cycles.

| ColdFire scope | instructions / frame | share |
|---|---:|---:|
| frame ISR `0x4000aad0..0x4000d9b0` | 10,720 | 26.2% |
| eight-track delay `0x400031a0..0x4000385a` | 7,665 | 18.7% |
| sample analysis `0x40098388..0x400985ac` | 5,643 | 13.8% |
| voice renderer `0x40007960..0x40008f82` | 5,605 | 13.7% |
| correlation search | 2,196 | 5.4% |
| total | 40,903 | |

Ranges are half-open and exclude callees. The four boundaries were checked
by objdump ✅:
- the ISR ends in `rte` at `0x4000d9ae`;
- the delay ends in `rts` at `0x40003858`;
- the renderer ends in `rts` at `0x40008f80`;
- the analysis routine is a `lea -36(%sp)` frame ending in `rts` at
  `0x400985aa`.

What "sample analysis" and the "correlation search" do is his reading,
unverified here.

The lockstep port measured 23,946 instructions per 16-sample frame
(17 Sep 2026, stock image, the port's `RIG` fixture project). The hottest loop is the stock
delay's EMAC mix at `0x40003734` (`COLDFIRE_DELAY.md`).

### ColdFire time per frame on a unit ✅ (Bryan T, 4 Oct 2026)

CF METER + CF METER IDLE (`modules/cfmeter/README.md`) on Bryan T's MKII,
his remix `bt_oct_stress` (not in the tree: RECORDER LOOP FIX, LOFI AMF
FIX, USB MIDI, USB AUDIO OUT TRACKS MAIN CUE, USB CROSSBAR, USB AUDIO IN
ABCD, the stock effects less SPATIALIZER, CF METER, CF METER IDLE). ISR =
the frame interrupt, vector `0x41` entry to the epilogue at `0x4000d9a6`,
on DTIM3; the frame is 362.8 µs. Capture `tools/hw/rec 8 <out>.wav
Octatrack`, decoded by `tools/harness/cfmeter.py`. Both USB directions
streamed in every take: macOS opens the host → OT stream when `rec`
starts I/O (`tools/hw/usb_counters.py --in --watch 1`: USB AUDIO IN's
`produced` rose ~44,100 frames/s, `pkts` ~4,000/s, for exactly the take),
so every number carries the full USB stack with USB CROSSBAR's priorities.
Project: T1–T7 FLEX (STATIC where stated), each a long sample recorded at
137 BPM, project at 120 BPM, all voices sounding for the take; FX1 FILTER,
FX2 NONE except the DELAY takes, TSTR OFF except the TSTR take. Cells are
the three 2 s cycles.

| take | idle % | ISR mean µs | ISR max µs |
|---|---|---|---|
| near-empty project, stopped | 46.2 / 46.4 / 46.4 | 119 / 119 / 119 | 198 / 205 / 201 |
| 7 FLEX, TSTR off, stopped | 42.2 / 42.0 / 41.8 | 143 / 142 / 143 | 218 / 217 / 218 |
| 7 FLEX, TSTR off, playing | 11.0 / 7.6 / 11.3 | 268 / 244 / 264 | 306 / 291 / 301 |
| 7 FLEX, TSTR AUTO (137 → 120, audibly stretching) | 16.9 / 13.3 / 19.4 | 261 / 278 / 257 | 307 / 313 / 308 |
| 7 FLEX + DELAY on T1 | 10.1 / 6.2 / 11.3 | 237 / 268 / 245 | 292 / 302 / 291 |
| 7 FLEX + DELAY on T1–T4 | 15.3 / 6.8 / 15.9 | 237 / 270 / 242 | 292 / 306 / 292 |
| 7 FLEX + DELAY on T1, TIME swept by hand | 13.6 / 20.9 / 12.2 | 269 / 240 / 271 | 314 / 291 / 306 |
| 7 STATIC, one sample slot | 10.0 / 10.5 / 8.5 | 256 / 277 / 266 | 314 / 335 / 327 |
| 7 STATIC, seven different samples | 0.0 / 0.0 / 0.0 | 256 / 285 / 270 | 307 / 330 / 321 |

Voice count, transport running, trigs cleared per take:

| voices | idle % | ISR mean µs | ISR max µs |
|---|---|---|---|
| 0 | 42.2 / 42.1 / 42.0 | 139 / 139 / 138 | 218 / 221 / 216 |
| 1 (T1) | 35.4 / 34.9 / 34.8 | 173 / 182 / 174 | 259 / 257 / 255 |
| 1 (T5) | 36.5 / 37.4 / 36.3 | 180 / 169 / 180 | 251 / 260 / 255 |
| 4 (T1–T4) | 24.3 / 28.5 / 26.9 | 233 / 220 / 228 | 284 / 274 / 283 |
| 7 (T1–T7) | 17.8 / 17.8 / 16.8 | 265 / 247 / 267 | 302 / 288 / 307 |
| 7, seven different samples | 20.4 / 14.8 / 17.1 | 246 / 268 / 250 | 292 / 318 / 294 |

The same projects under the port (`verify_set.py bt_oct_stress --project
<dir> --frames 17000`, `cfmeter.py --dump`): the port advances one step per
instruction at `--ips 3990`, so instructions = port µs × 176; unit cycles =
unit µs × 264.

| | port ISR | instructions | unit ISR | unit cycles | CPI |
|---|---|---|---|---|---|
| 0 voices | 144.7 µs | ~25,470 | 138.6 µs | ~36,590 | ~1.4 ❌ (history-contaminated; the follow-up below has 106.5 µs unplugged, CPI ~1.1) |
| 0 → 1 voice | +6.3 µs | ~1,110 | +37.4 µs | ~9,870 | ~8.9 ❌ (retracted the same evening: +14.6 µs, CPI ~3.5) |
| each voice, 1 → 7 | +5.7 µs | ~1,000 | +13.9 µs | ~3,660 | ~3.7 ❌ (revised: +16.5 µs, CPI ~4.4) |

Port points: 0 voices 144.7, T1 151.0, T1 + T5 156.6, 4 voices 168.2, 7
voices 185.2 µs; 1,009 instructions per voice over 1 → 4 and 994 over
4 → 7. On the unit 1 → 4 gives CPI ~4.4 and 4 → 7 ~2.9, a spread the size
of the unit's cycle-to-cycle noise.

- **Voice cost.** ❌ The morning reading, a first-voice premium of +37 µs
  then 11–17 µs per voice, was retracted the same evening: the 0- and
  1-voice takes were taken after seven tracks had played and had their
  trigs cleared, and fresh loads read 121 and 146 µs with USB streaming
  (the follow-up below). Every voice costs the same, ~16.5 µs. Still
  standing from the morning: seven voices put the ISR at 255–260 µs of
  362.8; equal on either DSP core (T1 alone = T5 alone), equal with one
  shared sample or seven (259 vs 255 µs); the running transport with no
  voice costs nothing (139 µs vs 143 stopped).
- **The voice path is memory-bound; the rest of the ISR is not.** The port
  prices every voice at ~1,000–1,100 instructions; on the unit the
  baseline runs at CPI ~1.1 and each voice at ~4.4 (~4,360 cycles for
  ~1,000 instructions; the follow-up's figures). Candidates: SDRAM line
  fills (CACR `0xA50CE100`, ACR0 `0x4007E020`, written at `0x4001f3e0`
  and `0x4001fc44` ✅: SDRAM `0x40000000..0x47FFFFFF` cached copyback,
  everything else cache-inhibited) and uncached accesses. SDRAM contention
  with USB DMA is ruled out by the follow-up: the per-voice slope is 16.6 µs
  unplugged and 16.9 µs with USB streaming.
- **A loaded, stopped project costs ~24 µs per frame** over a near-empty
  one (143 vs 119 µs).
- **Timestretch at 137 → 120 BPM adds nothing measurable.** The renderer
  (`0x40007960`) runs inside the ISR: the per-track dispatch `jsr %a3@` at
  `0x4000d340` / `0x4000d36c` and `%a4@` at `0x4000d35a` goes through the
  machine-type table `0x400d6434` (`lea` at `0x4000bff0`); types 0, 1 and 4
  point at `0x40004008`, which calls the renderer 🟡 (read from the image
  5 Oct 2026, the table's entries not re-read here). Untested: stretch
  beyond 2× (voice `+3`, a separate renderer path, `REPITCH.md`).
- **The stock DELAY adds nothing measurable** on one track or four, settled
  or with TIME moving. The routine `0x400031a0` is called from transfer
  state 5 of the level-6 eDMA chain (state entry `0x40004aaa`, the `jsr` at
  `0x40004b12` ✅), which can nest inside the measured span; its cost is a
  fixed per-frame amount in every baseline either way. The profile's
  7,665-instruction row above is not visible as ISR time on the unit;
  neither is the sample analysis / correlation search under stretch.
- **STATIC streaming leaves the ISR mean alone and adds spikes:** max
  +25–35 µs over FLEX (335 µs in one cycle). ATA is level 5, the frame
  interrupt's own level (`KERNEL.md`), so ATA handler time cannot nest
  inside the span: the spikes are stalls.
- **Seven distinct STATIC files drive idle to 0.00 % with the UI
  responsive** (fast knob turns, the file browser). Idle % is not a
  screen-lag predictor; the ISR share is the limit, since no task runs
  while it does.
- **Spin-waits inside the ISR: two**, both polling the host port's HC bit
  (`movew 0x20000004,%d0` at `0x4000ab26` and `0x4000a90c` ✅), per frame.
  The ISR arms eDMA channels 1, 6 and 7 and leaves; the chain's two
  eDMA-status spins are in the delay routine (`0x400035a8`, `0x40003780`)
  🟡 (read from the image 5 Oct 2026, not re-read for this entry).
- **DSP core 0, every take:** TUE 0, ROE 0, spin min 2,017–2,262 polls.
  Its frame period reads 362–363 µs stopped and with T1–T4 playing (ISR
  227 µs), ~345–385 µs when T5–T7 play. No underruns. (An earlier reading,
  long ColdFire ISRs delaying frame delivery, is retracted.)
- **The ISR mean alternates ~240 / ~268 µs between consecutive 2 s cycles**
  in most playing takes; one bar at 120 BPM is 2 s. Not investigated.

#### Follow-up the same evening: USB and the crossbar ✅ (Bryan T, 4 Oct 2026)

Same image and unit, T8 alone on CUE, CUE L/R into an SSL 12 (`tools/hw/rec
20 <out>.wav "SSL 12"`, `cfmeter.py --lr 2,3`), so the USB cable can be out.
"USB streaming" = cable in and a dummy `rec 60` on the Octatrack device in
another window (both directions open); "unplugged" = cable out, the OUT
producer and USB IN's per-frame transfer still running. Every take from a
freshly loaded project (no trigs / T1 / T1–T7, one long sample), 20 s = 9
cycles; the ISR mean alternates between consecutive 2 s windows (~3 µs at 1
voice, ~18 µs unplugged and ~27 µs with USB at 7), so each figure is the
mean of the two phases' means. The analog path reads ~0.6 % high (the frame
period reads 365.0 for 362.8); raw below, ×0.994 where marked. The decoder
needed a wider sync window for the analog path (`cfmeter.py --analog`).
Validation: 7 voices with USB streaming, 252.7 µs here against 259.3 over
USB in the morning.

| fresh load | unplugged | USB streaming | USB cost |
|---|---|---|---|
| no voices | 107.1 µs | 121.2 µs | 14.1 µs |
| T1 | 121.8 µs | 145.7 µs | 23.9 µs |
| T1–T7 | 221.4 µs | 247.0 µs | 25.6 µs |

×0.994: 106.5 / 120.5, 121.1 / 144.8, 220.1 / 245.5 µs. Repeatability: no
voices unplugged, 9 cycles within ±0.5 µs; T1 unplugged, three fresh loads
122.0 / 121.7 / 121.8 µs. ISR max: no voices ~127 unplugged, ~201–209 with
USB; T1 ~148 or ~200 alternating (a trig in the window or not) unplugged,
~223–246 with USB; T1–T7 ~253–274 / ~282–314.

| | unit (×0.994) | cycles | port instructions | CPI |
|---|---|---|---|---|
| baseline ISR, no voices | 106.5 µs | ~28,100 | ~25,470 | ~1.1 |
| first voice | +14.6 µs | ~3,850 | ~1,110 | ~3.5 |
| each further voice, T1 → T1–T7 | +16.5 µs | ~4,360 | ~1,000 | ~4.4 |

- **No crossbar contention on the voice path:** 16.6 µs per added voice
  unplugged, 16.9 µs with USB streaming.
- **The USB stack costs** ~14 µs of mean ISR per frame with nothing
  playing, ~24–26 µs as soon as anything plays, flat from 1 to 7 voices.
  The ~10 µs step at the first voice is repeatable and unexplained.
- **The worst frame is set by trigs** when anything plays (the frame that
  starts a voice); at idle USB's own spikes set it (~127 → ~205 µs). The
  mean, not the max, prices USB.
- **Tracks that have played keep costing after they fall silent:** ~18 µs
  across seven tracks with none sounding, ~30 µs with one; the source of
  the morning's first-voice premium.
- Guidance: ~15–17 µs of mean ISR per playing voice, no first-voice
  premium, plus ~24–26 µs for the USB stack while a host streams and
  anything plays.

#### Third note: 4 in / 20 out against 4 in / 4 out ✅ (Bryan T, 4 Oct 2026)

Two images from the same module set, differing only in the OUT layout:
USB AUDIO OUT TRACKS MAIN CUE (eight track pairs + MAIN + CUE) against OUT
MAIN CUE (MAIN + CUE), both beside USB AUDIO IN ABCD, USB MIDI, USB
CROSSBAR, CF METER + CF METER IDLE and the stock effects. Same unit, same
fresh-loaded projects, 20 s takes balanced over the alternating windows; the
20-out takes through the analog CUE path (×0.994), the 4-out takes over USB
(CUE on host channels 3/4); the two methods agreed where they overlapped.
Repeat loads within ±0.5 µs.

| fresh load | 20 out, unplugged | 20 out, streaming | 4 out, streaming | 20 out streaming − 4 out |
|---|---|---|---|---|
| no voices | 106.5 µs | 120.5 µs | 93.8 µs | 26.7 µs |
| T1 | 121.1 µs | 144.8 µs | 110.3 µs | 34.5 µs |
| T1–T7 | 220.1 µs | 245.5 µs | 195.3 µs | 50.2 µs |
| per voice, T1 → T1–T7 | 16.5 µs | 16.8 µs | 14.2 µs | |

Seven voices: 68 % of the frame in the ISR with 20 out, 54 % with 4 out.
Worst frame per window: no voices ~201–209 µs (20 out) against ~114–121 (4
out); seven voices ~282–314 against ~231–272.

- **Most of the 20-out cost is paid with no host connected:** 4 out
  streaming sits 13 µs below 20 out unplugged with no voices and 25 µs
  below with seven. That is the OUT TRACKS MAIN CUE producer, which runs
  every block whether or not a host listens (~2,710 instructions and 320
  read-back words per block, against 64 words for MAIN CUE); packet
  building is only part of it.
- **20 out makes each voice dearer:** 16.5–16.8 µs per voice with it, cable
  in or out, against 14.2 µs with 4 out. Cache pressure from the 320 words
  per block is his candidate, not measured; a probe walking the same
  footprint without USB would test it.
- **The ~10 µs step at the first voice** in the follow-up above belongs to
  the 20-out layout: no voices → T1 is +24.3 µs with 20 out streaming,
  +14.6 unplugged, +16.5 with 4 out streaming.
- Not measured: 4 out unplugged; recording; the ColdFire DELAY; one MKII.

Method, port side: `verify_set` pokes a trig on T1 step 2 by default, so
every port run has T1 playing; `--poke-trig 0` (since 5 Oct 2026) is the
zero-voice run. The gate stages samples from the SAVED part of pattern 1 and
plays pattern 1; working-part edits or a setup on another pattern give
silent tracks with `0 failure(s)`. The OT's SAVE AS NEW leaves later edits
in the original project (`ot_bank.trigs(data, 0, track)` reads a copy's
trigs). `cfmeter.py --dump` needs two sync → reference edges: 17,000 frames
gives two rows, 2,000 none.

## 7. Memory map

| Window | Use |
|---|---|
| `0x00000000` | NOR flash, CS0, 8 MB decode (section 3a) |
| `0x10000000` | CS1, 1 MB decode |
| `0x40000000` | SDRAM: code (OS image at `0x40000400`), data/BSS, the audio page arena, the delay rings (`docs/contributing/PLACEMENT.md`) |
| `0x48000000` | the same SDRAM, uncached |
| `0x20000000` | the DSP host port (HI08) |
| `0x80000000` | fast/shared RAM: voice state, kernel TCBs, the double-buffered DSP frames |
| `0x90000000` | ATA task-file (CompactFlash) via FlexBus |
| `0x100b0000` | small globals (current track/pattern) |
| `0xFC000000` | ColdFire on-chip peripherals (MBAR): ATA host `FC0451xx`, IRQ controller `FC04C010`, PIT `FC080000` |

Image load base `0x40000400` (1,441 string pointers resolve with it).

## 8. Tools

`docs/contributing/TOOLING.md`. In git history: `decode_elek.c` (the ELEK
container), `string_func_map.py`, the `Ghidra*.java` headless scripts.

## 9. Open

- The trig dispatch source (internal tempo clock or MIDI clock 0xF8): the
  tempo/project-BPM path is read end-to-end (`docs/firmware/DSP.md` section 6c);
  the dispatch itself is not.
- Remaining ATA handlers; large functions the decompiler does not lift.
- The vector table (`0x400` preamble, not in this section).
- ColdFire load (the CF METER takes above): why the voice path stalls
  (~4,360 cycles for ~1,000 instructions per voice; USB contention ruled
  out), and whether its data can move to SRAM; ns per cache line fill on
  cached SDRAM, the uncached alias (`+0x08000000`) and on-chip SRAM
  `0x80000000` (CF METER's MEM/SRC knobs, not yet run on a unit); DTIM3
  around the two HC polls and inside the level-6 handlers, for the nested
  share; the ~10 µs USB step when anything starts playing (the 20-out
  layout's, by the third note); whether 320 read-back words per block cost
  the renderer cache lines (20 out: 16.5 µs per voice, 4 out: 14.2); why
  tracks that have played keep costing after they fall silent (a fresh no-voice
  project, measure, a bar of T1, clear it, measure again); the alternating
  2 s windows (a 4 s period, the swing growing with voices); a recording
  take (the 8-recorder SOS project).
