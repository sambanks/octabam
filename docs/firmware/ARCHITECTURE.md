# Elektron Octatrack firmware architecture (OS 1.40C, ColdFire side)

Hardware, OS format, kernel, storage, audio engine, sequencer and memory
map, as verified. ✓ = checksum from the firmware itself, byte-exact
decompilation or direct disassembly; ~ = inferred. The DSP side is
`docs/firmware/DSP.md`; the tools are in `docs/remixer/TOOLING.md`.

## 1. Summary

An 8-track sampler/sequencer. The firmware runs on a Freescale ColdFire
CPU (68k family, big-endian, 266 MHz) with a two-core Freescale DSP56xxx
for real-time audio, under a proprietary preemptive microkernel. The OS
is loaded from CompactFlash via the ColdFire's on-chip ATA controller. The
architecture is producer/consumer decoupled by buffers in RAM: the same
kernel message-queue pattern appears in storage I/O and in the audio
pipeline.

## 2. Hardware

| Component | Detail | Confidence |
|---|---|---|
| CPU | Freescale ColdFire **MCF5445AVR266** (32-bit, big-endian, 266 MHz) | ✓ (board photo; the on-chip ATA controller at MBAR `0xFC04_51xx` is the MCF5445x's) |
| Audio DSP | Freescale Symphony **DSP56721** (`DSPB56721AG`): two DSP5636x cores, 200 MHz each, no external memory controller | ✓ (board photo) |
| RAM | 128 MB SDRAM at `0x40000000` (`docs/remixer/PLACEMENT.md`) | ✓ |
| Storage | CompactFlash (FAT16/32), OS and data; boots to DEMO without CF | ✓ |
| NOR flash | CS0 at `0x00000000`, 8 MB decode; Spansion S29GL-N ID check, size not read (§3a) | ~ |
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
`os_apply_flash` (critical section) → writes the CF via ATA → reboot.

## 3a. NOR flash ~

Read from the 1.40C MAIN OS image (objdump listing, absolute-operand
scan), 24 Sep 2026, after Andreas (Discord) reported an 8 MB NOR with
~1.1 MB used. Nothing here is measured on a unit. objdump decodes the
bootstrap copy and the ID-check region misaligned, so the addresses
given for entry points there are ± a few bytes.

**Chip select.** The bootstrap init (`0x400e0a1c..`) sets CSAR0 = 0,
CSMR0 = `0x007F0001` (8 MB decode, valid), CSCR0 = `0x0C8015B0` (16-bit
port, 5 wait states). A decode size is not a part size: SDCS0 decodes
256 MB over a 128 MB SDRAM (`docs/remixer/PLACEMENT.md`). CS1 =
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
| `0x000000..0x003fff` | bootstrap, linked at 0; its copy sits in the OS image at `~0x400de7dc..0x400e21e0` and carries the "BOOTSTRAP UPGRADE" string and the SysEx OS upgrade path | ~ |
| `0x004000..0x1fffff` | the OS region: the OS's sector table at `0x400a91c0` has 37 entries, `0x4000`, `0x6000..0xe000` (6 × 8 KB), `0x10000..0x1f0000` (31 × 64 KB) = 2,080,768 B. The bootstrap's SysEx path programs the OS from `0x4000` (`0x400e011a..`, `pea %a0@(16384)`, +2 per word). The table is followed by "ELFU" and the `.bin` cipher constants (§3) | ~ |
| `0x1ffffa..0x1fffff` | three words: magic `0x1234` at `0x1ffffa`, two words after it; the bootstrap also programs `0xabcd`/`0xdcba` markers here | ~ |
| `0x200000..` | magic "EFGH", a count n, then n × 28-byte records, copied to `0x46ceb400` by `0x4001b9b4`; contents unidentified | ~ |
| above the EFGH table | no reference in the OS image | ~ |

The current MAIN OS is 1,112,560 B, 53% of the 2,080,768 B window;
968,208 B of the window is unused by 1.40C.

**Constraints on using it.**

- The OS executes from SDRAM (load base `0x40000400`, §7), not in place
  from flash. Code stored in flash runs only after something copies it to
  RAM: the bootstrap does this for the OS region (inferred: the copy loop is not located); anything above
  `0x200000` needs its own loader (the DRAM platform's boot detour is
  where one would sit, `docs/remixer/PLACEMENT.md`).
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
- The OS's own upgrade flow stops audio before it writes (§3). Whether a
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
- §3's write flow says `os_apply_flash` writes via ATA; the OS carries
  this NOR driver and sector table. Which device `os_apply_flash` writes
  is not traced.

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
`docs/history/RTOS_FORK.md` §2); takes the highest-priority ready task;
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
the port, `docs/history/COLDFIRE_PORT.md`; an earlier reading of "command
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
`docs/firmware/DSP.md` §§1-3.

**Trig → voice** (`FUN_400977cc`, dispatched by machine type): reads the
track's machine state (`FUN_40097168` → 0-4) and emits the voice command
via `FUN_40005178` with flags (`0x80` start, `0x10`/`0x8010`/`0xf010` =
one-shot/hold/stop/retrig, labels unverified; the recorder's TRIG-mode
branch at `0x40083544` posts the same bits).

## 7. Memory map

| Window | Use |
|---|---|
| `0x00000000` | NOR flash, CS0, 8 MB decode (§3a) |
| `0x10000000` | CS1, 1 MB decode |
| `0x40000000` | SDRAM: code (OS image at `0x40000400`), data/BSS, the audio page arena, the delay rings (`docs/remixer/PLACEMENT.md`) |
| `0x48000000` | the same SDRAM, uncached |
| `0x20000000` | the DSP host port (HI08) |
| `0x80000000` | fast/shared RAM: voice state, kernel TCBs, the double-buffered DSP frames |
| `0x90000000` | ATA task-file (CompactFlash) via FlexBus |
| `0x100b0000` | small globals (current track/pattern) |
| `0xFC000000` | ColdFire on-chip peripherals (MBAR): ATA host `FC0451xx`, IRQ controller `FC04C010`, PIT `FC080000` |

Image load base `0x40000400` (1,441 string pointers resolve with it).

## 8. Tools

`scripts/fetch-os.sh` / `analyze.sh` (download, entropy, binwalk,
decompression), `tools/build/bin_decode.py` (the ELUP `.bin`),
`tools/build/find_base.py` (the load base), `scripts/disasm.sh` (radare2 at
the right arch and base; `emac` for objdump, the only decoder that reads
the ColdFire V4e extensions). In git history: `decode_elek.c` (the ELEK
container), `string_func_map.py`, the `Ghidra*.java` headless scripts.

## 9. Open

- The trig dispatch source (internal tempo clock or MIDI clock 0xF8): the
  tempo/project-BPM path is read end-to-end (`docs/firmware/DSP.md` §6c);
  the dispatch itself is not.
- Remaining ATA handlers; large functions the decompiler does not lift.
- The vector table (`0x400` preamble, not in this section).
