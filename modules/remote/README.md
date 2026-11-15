# `remote` — REMOTE

Event records, a frame trace, memory reads and four commands for a host driving a unit over USB, so a
hardware test waits for the event it caused instead of for a time. ColdFire only; no DSP code or state,
nothing on the panel. Author: Sam Banks. Closes issue #978 (PEEK, COMMAND).
Under the port only (`verify_remote`); not run on a unit.

Needs [STORE](../store/README.md) and [USB](../usb/README.md). Command 3 and 4 need
[REMIX SWITCH](../remix-switch/README.md) in the image and are refused without it.

## What it keeps

`RMT_RING` (in DRAM) is a 32-byte header and 256 records.

| header long | holds |
|---|---|
| 0 | magic `RMT1` |
| 1 | `head`: the count of records written; record n is at index n & 255 |
| 2 | the screen count: LCD front-buffer pointer (`0x400b970c`) changes |
| 3 | DMA timer 3's count at the last change |
| 4 | address of `RMT_TRACE` |
| 5, 6 | addresses of REMIX SWITCH's name list and its count (0 without it) |
| 7 | 0 |

A record is 8 bytes: seq (16 bits, the low half of its number), kind (8), arg (8), stamp (32 bits of DMA
timer 3, 132 MHz, wrapping every 32.5 s). A host that last saw head H reads records H..head-1 and has lost
head-H-256 of them when that is positive. Screen redraws are a count, not records: about 70 a second while
playing under the port, which would turn the ring over in under 4 s.

| kind | name | from | arg |
|---|---|---|---|
| 1 | LOADALL | STORE `loadall_post` | 0 |
| 2 | LOADMASK | STORE `loadmask_post` | the mask's low byte |
| 3 | NEWPROJ | STORE `newproj` | 0 |
| 4 | BANKW | STORE `bankw_post` | 0 |
| 5 | PSTORE | STORE `pstore_post` | 0 |
| 6 | PRELOAD | STORE `preload_post` | 0 |
| 8 | COMMAND | a COMMAND ran in the UI task | its id |
| 16 | PLAYING | `0x800065b8` changed | the new value |
| 17 | BANK | `0x800065bd` changed | the new value |
| 18 | PATTERN | `0x800065be` changed | the new value |
| 19 | QBANK | `0x800065bf` changed | the new value |
| 20 | QPATTERN | `0x800065c0` changed | the new value |

Kinds 16 to 20 come from the frame interrupt's entry (`0x4000aad0`, about 2,756 a second): the five bytes
are compared with their values at the previous entry. Nothing else is detoured; the STORE events come from
STORE's client calls.

`RMT_TRACE` is `{count, 0, 512 × {interrupted PC, DMA timer 3's count}}`, written at every frame
interrupt's entry (the PC from the exception frame: `sp+256`, `sp+260` under HOOKS). The last 512 are kept
(186 ms).

## The requests

The USB module answers on EP0 (`modules/usb/usbaudio.s`). A reply is at most 255 bytes and never a
multiple of 64 (TRAPS `trap-ep0-dma`).

| request | does |
|---|---|
| `0xc0/0x5a` | the ring's bytes from byte offset `wValue` |
| `0xc0/0x58` PEEK | memory at `wValue:wIndex` (high:low), inside `0x40000000..0x48000000`, `0x80000000..0x80008000`, `0x10000000..0x10100000`; any other address STALLs; a read stops at a window's end |
| `0xc0/0x59` COMMAND | `wValue` low byte = id, high byte = the id's parameter, `wIndex` = its argument. One-byte reply: 0 taken, 1 refused |

COMMAND posts its routine to the UI task through the stock deferred-call queue (`0x40000c3c`); the routine
runs there and a COMMAND record (arg = id) follows.

| id | does | refused when |
|---|---|---|
| 1 | enter USB DISK MODE (`0x4007eb34`) | an earlier command is pending; already in the mode (`0x460e76a0`) |
| 2 | leave it (stock `0x4007eb18`: closes the mode's dialog, whose callback leaves the mode and reloads the project) | pending |
| 3 | boot `/BRAIN/REMIXES/<name>.RMX` through REMIX SWITCH's YES path (`osw_answer(0)`): file checks, card sync, reset | no REMIX SWITCH; index ≥ list count; hash of the name at that index ≠ `wIndex`; pending |
| 4 | rescan the list (`osw_scan`), for after a file was copied in disk mode | no REMIX SWITCH; pending |

Command 3 addressing: `wValue` high byte is the file's index in REMIX SWITCH's list, `wIndex` the 16-bit
hash of its name (`h = h*33 + byte`). The host reads the list with PEEK (`ot_events.remixes`), so it sends
the order the unit holds; a list that changed since fails the hash. Id 0 and ids ≥ 5 are refused.

## The file sink

At each STORE event the handler flushes the records not yet logged through the stock card logger
(`0x4001ffe4(level 2, "RMT %d %d %d %d", seq, kind, arg, stamp)`), which appends a line to `/LOG <date>.txt`
(`docs/firmware/STORAGE.md`). The stamp prints signed.

## Host side

`tools/hw/ot_events.py` (`Events.poll`, `wait_for`, `wait_screen`, `trace`, `peek`, `command`, `remixes`,
`boot`), `tools/verify/verify_remote.py` (the gate), `remixes/test/remote`.

## Measured

Under the port, 13 to 15 Nov 2026, `verify_remote` on `remote` (27 checks) and on `octabam`, `octabam-bus`
and `octabam-verbs` (29 checks each), project `OCTABAM89_setgate`:

- the block's header, request sizes (255 bytes for 256 asked, 63 for 64), an offset at the block's end STALLs,
  head over USB equals the cell;
- a project load reads back as NEWPROJ, LOADMASK 255, LOADMASK 251 (no LOADALL);
- PLAY → PLAYING 1, STOP → PLAYING 0, a program change → PATTERN, each through `wait_for`;
- the screen count rises after a key that redraws; record numbers are consecutive;
- PEEK returns the header; a peripheral register, flash and the uncached view STALL;
- the last 64 trace entries: every PC in SDRAM, the count rises;
- the card log holds the load's `RMT` lines, equal to the records read over USB;
- SAVE PROJECT from the panel reads back as BANKW and PSTORE, and the card log then holds every record up to
  the save's last, PLAYING and PATTERN among them;
- COMMAND: the command table holds none of OS UPGRADE's routines (`0x400636bc`, `0x40063660`, `0x4006370c`,
  `0x40080640`); 1 enters USB DISK MODE and the ring still answers; 1 again does nothing; 2 leaves, the
  project reloads, no dialog stays open;
- COMMAND 4 then the list over PEEK is the card's two `.RMX` files; 3 with another name's hash, an index past
  the list or an absent name is refused; 3 for a listed file stages it (mailbox name and length) and reaches
  the reset sequence (the port does not reset, so the boot of the staged image is not exercised).

Frame interrupt entries 47,891 timer counts apart (362.8 µs) under the port, both builds.

## On the unit

MKII, 15 Nov 2026, image N1 (`octabam` at commit 95e52aee), project `RMT_SFX_01` (the suite's `SFX_01`), USB
TRACKS PRE; the control N2 is `octabam` without REMOTE.

- The ring over `0xc0/0x5a`: header and records, 0 lost. A menu load of the project reads LOADMASK 254,
  BANKW, LOADALL, NEWPROJ, LOADMASK 255.
- `wait_for` after a MIDI START (host clock): PLAYING 1 in 7 to 8 ms; after a program change: PATTERN in 7.9
  and 8.0 s (the pattern's end), QPATTERN first.
- A MIDI STOP writes PLAYING 2. PLAYING 0 follows one frame before the next START, and on entering USB DISK
  MODE.
- The trace: 461 consecutive entries 354.0 to 372.5 µs apart, mean 362.8 µs.
- The file sink: `/LOG 261115.txt` held records 0 to 16 as `RMT` lines, equal to the ring; lines written in
  one flush carry that flush's time.
- COMMAND 1: the card mounted on the host 4.5 s later. COMMAND 2: the project reloaded, LOADMASK 255 after
  9.9 s; the command stays pending until then, so a command sent before it is refused.
- COMMAND 4: the list over PEEK holds the card's 10 files. The list is empty after a boot until MAIN MENU
  opens or COMMAND 4 runs.
- COMMAND 3: 6 boots (5 of N1's file, 1 of N2's); the ring answered 7.0 and 8.0 s after the command. It
  saves the selection as the panel's YES does: a power-cycle then boots the commanded file. One of the 6
  stopped on the boot screen and did not return to USB (`docs/contributing/FAILURE_MODES.md`).
- The ring does not survive a boot: its cells are the runtime's `.data`, which a boot loads again (read
  from the source; the head after each boot was 0 or 1).
- LOAD METER's ColdFire share, N1 against N2: playing, 30 s, 64.48 % and 64.94 % (two runs) against
  64.85 %; fresh after the load, stopped, 26.08 % (15 s) against 25.7 % (one reading). The longest run
  playing: 492 and 485 µs against 424 µs.
- FRAME GUARD's first-START assay (`ot_stall.py`, 20 channels, one trial a power-cycle): 8 of 8 ok.

## Open

- The freeze after one COMMAND 3 boot: not repeated in 5 more; its cause is not known.
- The file sink's write time: not measured.
- N2's stopped share from more than one reading.
- A host cannot leave an image without REMOTE: the panel's FLASHED row or FUNC at power-on.
- EMPTY RESET, project delete and card format are not located, so the command table's forbidden set holds OS
  UPGRADE's four routines only.
