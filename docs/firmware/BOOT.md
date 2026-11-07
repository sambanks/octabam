# Boot path and OS entry

Read 29 Sep 2026 from the MAIN OS image and from the bootstrap copy it carries (`0x400dea4c..0x400e1ec4`, linked at 0).
✅ read from the image, 🟡 inferred, ❓ open. Moved here from the REMIX SWITCH design records (`git show 76fd8466:docs/proposals/FIRMWARE_SWITCHER.md`
sections 2.1-2.4, `git show 76fd8466:docs/proposals/BOOT_DEFAULT.md` sections 2 and 3); what the module does with these facts is in
[`modules/remix-switch/README.md`](../../modules/remix-switch/README.md).

## The OS is unpacked into SDRAM at every reset ✅

The reset vector (`0x2d4a` in the bootstrap) runs these steps:
- PLL, then RAMBAR1;
- `0x2920`: GPIO, the SDRAM controller (`0x288e`: precharge, two
  refreshes, mode register), the panel link, the Startup Menu on a held
  key;
- `0x22a2`: caches on, then unpack NOR `0x4012` into `0x40000400` with
  the routine at `0x207e` (the image's copy of it is `0x400e0aca`,
  `tools/remix/loader.S`'s depacker), then ACR0/ACR1 = 0 and
  `CACR = 0x0008c000`;
- `move.l 0x8000050a,-(%sp) ; jsr 0x40000400`.

The OS never runs in place from flash. Whatever sits at `0x40000400` when
that `jsr` lands **is** the OS. Nothing on this path writes SDRAM outside
the unpacked image, except the Startup Menu's TESTMODE RAM test (`0x784`),
which runs only when chosen.

## The OS entry, instruction by instruction ✅

```
40000400  lea (-28,%sp),%sp ; movem.l ...        the bootstrap's argument at 32(%sp)
4000040c  move.l (%a0),0x400b9650                 parked
40000412  movea.l #0x48000000,%sp                 <- OS SWITCH's detour
40000418  PLL -> 0x400b9654
40000432  NOR 0x3ffc vs 0x400dea48                bootstrap versions: flash vs image
40000444  bcs -> 0x40000450: 0x4000f9b4           REPROGRAMS THE BOOTSTRAP if the image's is newer
4000044c  264 MHz ? -> 0x4000050c
4000050c  jsr 0x40001e50                          the DSP upload (octabam's boot detour)
40000518  zero-fill 0x46025de0..0x4763d580        globals and heap
4000053c  jsr 0x40000db0                          main
```

Two consequences:
- **The DSP upload assumes a reset DSP.** `0x40001e50` sends both cores
  their bootstrap through the HI08 boot ROM (`docs/firmware/DSP.md`).
  Only a board reset puts them there, so a switch has to reset the unit.
  A jump into a new OS from a running one cannot work.
- **An image whose bootstrap version is newer than NOR's rewrites the
  bootstrap sector**, which holds the Startup Menu and the MIDI recovery.
  Every image built here carries 1.40C's `0x0408`. A switcher must refuse
  any other, and the prototype does (`BVER`).

## OS UPGRADE ✅

`0x400636bc` → `0x40063660` stops playback → deferred through the UI task's
queue (`0x40000c3c`) → `0x40080640`. From there:
- it lists `/*.BIN` (`0x4007f598`);
- it syncs the project and waits for the card to go idle
  (`0x40080444..0x40080480`);
- it reads the file through the FS vtable (`0x46c8242a` open, `0x46c8241e`
  size, `0x46c82426` read in 8-sector chunks, `0x46c82422` close);
- it programs NOR from `0x4000` and verifies it word by word
  (`0x4007fcb2`);
- it ends on `UPGRADE DONE` / `PLEASE REBOOT!` and `move.w #0x2700,%sr ;
  jsr 0x40010a4c ; bra .`: stock never resets the unit; the user
  power-cycles.

REMIX SWITCH reuses all of it except the programming, and brings its own reset.

## Memory the OS never touches ✅

The platform reserve (`docs/contributing/PLACEMENT.md`) is the bottom of
the audio page arena, `0x40a955e0` upward. Stock never touches it once the
base literal moves. REMIX SWITCH declares its image stage,
`0x41200000..0x41495de0` (2.6 MB), as an ArenaReserve, so MEMORY keeps the
reserve reaching past it (the bottom 1,707 pages, as in every DRAM remix
before 11 Oct 2026).

## What a boot default needs, read from the image ✅

Read from the user's own image, 29 Sep 2026. Bootstrap addresses are
relative to its copy at `0x400dea4c` (linked at 0); the image address is
given where it matters.

- **The chainloader runs before there is a filesystem.** Its gate is a
  detour at the OS entry's second instruction, `0x40000412`
  (`modules/remix-switch/manifest.py:119`), and the OS entry's own path is
  `0x4000050c` the DSP upload → `0x40000518` the globals/heap zero-fill →
  `0x4000053c jsr 0x40000db0` main ("The OS entry" above). At the
  gate no DSP, no cache set-up, no interrupts and no ATA stack have run.
  The switcher's own load path needs the FS vtable
  (`modules/remix-switch/switch.s:155-161` refuses to scan while
  `0x46c8240e` or `0x46c8242a` is still zero) and OS UPGRADE's
  stop/sync/wait-for-idle sequence `0x40080444..0x40080480`
  (`switch.s:621-633`). None of that exists at the gate. **Falsified by** a
  card read that succeeds from a detour at `0x40000412`.
- **The mailbox is DRAM and a power-on is treated as having none.** The
  stage lives at a fixed address in the platform reserve, `OSW_MBOX 0x49200000`
  (`modules/remix-switch/osw.inc`), and the gate's no-mailbox path records
  `ST_NONE` and resumes (`chain.s:55-64`). Whether a *quick* power-cycle
  keeps DRAM is unmeasured: `chain.s:11-12` says it does, and
  `docs/firmware/ARCHITECTURE.md:158-164` marks the refresh-gap question
  `~, unmeasured`. It does not matter for safety — the gate clears
  `MB_MAGIC` before anything below it can fail (`chain.s:38`) — but it
  means a boot default cannot be carried in the mailbox from one power-on
  to the next.

So a boot default is: the flashed image boots, reads a choice from the
card, stages the target and resets; the target boots. **Two boots per
power-on, always** — including the boots where you wanted the flashed image
anyway, unless the default can name it.

## A held key at power-on ✅

The bootstrap reads the panel before it unpacks the OS, and the results sit
in two SRAM bytes that nothing else touches:

- `0x128` (image `0x400deb74`) clears `0x80000200` and `0x80000508`, sends
  the panel `0x60 0x00`, then reads tagged pairs: tag `0x25`'s byte is
  stored at `0x80000200` (`0x170`), tag `0x26`'s at `0x80000508`
  (`0x17e`), tag `0x27` ends it. The loop exits when `0x80000200` is
  nonzero or the terminator arrives, **with no timeout** — the hazard
  `switch.s:29-31` names and build 1 hit from the other side.
- `0x2abc` (image `0x400e1508`): if `0x80000200` is `0x20` the bootstrap
  draws its own menu (strings at `0x305a` `"  STARTUP MENU  "` and
  `0x306b` `"\n1..TESTMODE\n2..EMPTY RESET\n3..MIDI UPGRADE\n4..SEND
  UPGRADE\n5..EXIT"`) and loops reading the panel, storing the selection
  masked with `0x1f` at `0x80000200` (`0x2b16`, `0x2b20`). **If the first
  byte is anything else, `0x2b40` clears `0x80000200`** — so a bare held
  key leaves no trace at all.
- `0x2b4c..0x2b8c` dispatches that byte: `1` → TESTMODE (`0x2846`), `2` →
  `orl #1,0x8000050a`, `4` → MIDI UPGRADE (`0x1f34`), `8` → SEND UPGRADE
  (`0x1d54`). `0x2b8e`: `0x80000508 == 2` → `orl #2,0x8000050a`.
- `0x2d30` sets RAMBAR1, `0x2d34` runs the panel/menu path, `0x2d38`
  unpacks NOR, and `0x2d3c` is `movel 0x8000050a,%sp@- ; jsr 0x40000400`.
  The OS entry parks that long at `0x400b9650` in the instruction
  immediately before our detour (`0x40000408 lea %sp@(32),%a0 ;
  0x4000040c movel %a0@,0x400b9650`).
- The OS reads the parked long at three sites: `0x4001fa2c` (`== 1` →
  clear `0x10000000..0x100fff00`, which is EMPTY RESET), `0x4001faec`,
  `0x4001fb6a`.
- ✅ **The MAIN OS image contains no code reference to `0x80000200`,
  `0x80000508` or `0x8000050a` outside the bootstrap's own copy** (a
  literal search of all four-byte occurrences: the nine other hits, at
  `0x400c401d`…`0x400c4069`, are odd-addressed and inside data). At the
  gate the cells are certainly the bootstrap's, since no OS instruction has
  run. **Falsified by** a write-watch on `0x80000200` under the port over a
  boot and a project load — the neighbourhood *is* live OS RAM
  (`0x80000003` the current part, `0x80000034` MASTER_TRACK,
  `0x80000810` the live block), so a computed write is entirely plausible
  and a literal search cannot see one. This is why the gate should copy the
  byte into the mailbox rather than let the OS read it later.

**The consequence.** `0x80000200 == 0x10` at the OS entry means the user
came through STARTUP MENU > 5 EXIT: a value the bootstrap has no case for,
which falls through `0x2b4c`'s dispatch and boots normally. 🟡 `0x10` is
EXIT's bit, inferred from the `0x1f` mask and the four cases the dispatch
does handle; **falsified by** a probe that reads the byte after EXIT and
finds something else. The gesture is two presses on a path the manual
already documents for recovery (`docs/contributing/FAILURE_MODES.md`, "Z"
screen: hold [FUNC], power on, then a TRIG).

❓ Whether a *bare* held key could serve instead — one press, no menu. The
gate could redo the bootstrap's own exchange on UART1 (`0xfc064004`
status, `0xfc06400c` transmit, the registers `switch.s:62-63` already
uses) and read the full rows. What would answer it: write the exchange with
a timeout (build 1's hang is exactly what a missing one costs) and measure
under the port with `--live-script` key lines, then on the unit with BOOT
TRACE reporting the byte as a velocity. Until it is measured, the STARTUP
MENU byte is the escape hatch that already exists.
