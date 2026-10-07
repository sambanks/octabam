# Switching OS images from the card, without flashing

A technical proposition, with a working prototype. It says what the
firmware already does, what the prototype does with it, what the ColdFire
port has measured, and what only the unit can answer, in the order to ask
it. The prototype is `modules/os-switch` and the remix `os-switch`. It has
run on an MKII (29 Sep 2026, build 14): a switch to the flashed image's
own `.OBI` and to stock 1.40C, each with audio and play working, the flash
never written (section 5).

Confidence markers as in `docs/firmware/CHIP.md`: ✅ measured (on the unit
where section 5 says so, else under the port or read from the image by
disassembly), 🟡 inferred, with what would
falsify it, and ❌ retracted.

---

## 1. The wish, in one sentence

Keep several OS images on the card and move between them without writing
the flash: build, copy, switch; power-cycle to come back.

Today every image change is an OS UPGRADE: a flash write, a reboot and a
power-cycle, and a stock `.bin` to get back. That makes an A/B between two
builds a minute of ritual each way. It also means every experiment puts
the recovery path one bad write away, even though the Startup Menu has
never failed us.

---

## 2. What the firmware already does

All of this is in stock 1.40C. Read 29 Sep 2026 from the MAIN OS image and
from the bootstrap copy it carries (`0x400dea4c..0x400e1ec4`, linked at 0).

### 2.1 The OS is unpacked into SDRAM at every reset ✅

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

### 2.2 The OS entry, instruction by instruction ✅

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

### 2.3 OS UPGRADE is most of a switcher already ✅

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

A switcher reuses all of it except the programming, and has to bring its
own reset (5).


### 2.4 Memory the OS never touches ✅

The platform reserve (`docs/contributing/PLACEMENT.md`) is the bottom 1,707
pages of the audio page arena, `0x40a955e0..0x41495de0`, in every remix
that carries a DRAM unit. Stock never touches it once the base literal
moves. Its top 2.6 MB is room for an image.

---

## 3. The prototype

```
running OS                                   next boot
----------                                   ---------
MAIN MENU > OS (a list of /*.OBI)           bootstrap unpacks NOR -> 0x40000400
  (stock dir scan, at each menu opening)     OS entry parks its argument
  dialog: BOOT X? (stock dialog)             0x40000412 -> gate (in the loader)
  YES: stop playback (stock)                   mailbox? spend it; body whole?
  deferred: sync, wait card (stock)          body (copied to the stage page):
  read X.OBI -> stage (reserve top)            length, NOR version, hash
  mailbox: len, hash, check, name,             stub -> 0x49200100
    the body's length and sum                stub: caches off, copy stage -> 0x40000400,
  DSP: park both cores (host command $12)          CACR = 0x0008c000, jsr 0x40000400
  reset: MKII panel `60 02`, RCR SOFTRST     staged OS boots from the start
```

- **An `.OBI`** is the raw image the bootstrap would unpack: the build's
  `out/mainos_bus.bin` (`make obi`) or stock's MAIN OS (`make
  obi-stock`). A target needs nothing from this module. Stock 1.40C is a
  valid target; it just has no OS category to switch back with, and a
  power-cycle does that.
- **One-shot.** The mailbox is cleared before the staged image runs, so a
  target that hangs costs one reset, never a loop.
- **Every refusal boots the flashed image** and leaves a status word
  (`NONE`, `HASH`, `BVER`, `SIZE`). A target that carries OS SWITCH
  reports `RUN` plus the reset path that brought it (`RCR`) on its
  dialog's third line. That line doubles as the hardware probe.
- **What it costs:**
  - no ROM cave: the gate is ~110 B in octabam's loader (a new
    `Linked(loader=True)` form), the body ~230 B in the runtime;
  - a DRAM unit of a few KB, packed in the image;
  - 40 DSP words in each payload for the park (70 until the build-15
    compaction, 29 Sep 2026; so a remix that keeps
    every stock effect cannot carry it);
  - two detours (`0x40000412`, `0x40064c32`), one row pointer
    (`0x400cbda4`), one count poke (`0x400cbd8c`, the root 4 → 5);
  - the top 2.6 MB of the platform reserve, which the gate keeps clear.
  (❌ The first prototype was a seventh CONTROL row with a one-file-at-a-
  time dialog and a 274 B ROM cave; the cave did not fit beside
  bottleservice's label formatters.)

Why the OS entry, and not octabam's boot detour at `0x4000050c`? The
detour's first act is the DSP upload (2.2). At `0x40000412` nothing has
touched the DSP, the caches or the interrupts. The staged image then starts
from the state the bootstrap hands over, minus one parked argument and the
28 bytes of stack the entry took, and it takes those again itself.

---

## 4. What is measured ✅ (the port, `tools/verify/verify_osswitch.py`, 16 checks)

- The panel drives the row, the dialog, the deferred load and the reset
  sequence on a card holding `STOCK140.OBI`. The stage reads back equal
  to the file, 1,112,560 B. The mailbox holds its length, hash, check word
  and name. The port does not reset, so the switcher records its RCR
  fallback.
- The home image is booted again with exactly the memory that run left.
  The chainloader runs, the stub runs from the stage, and stock's entry
  runs a second time. The home loader never runs, `0x40000412` holds
  stock's instruction again, and stock reaches the RTOS handoff.
- The home image staged as its own target reports `RUN`, with the
  mailbox spent and the loader run once.
- `NONE`, `HASH` (one flipped byte, mailbox still spent), `BVER` and
  `SIZE` each boot the flashed image.
- The platform runtime ends below the mailbox (`0x40a9788d` in this
  remix).
- `make check REMIX=os-switch`.

Two changes to the port came with it (`tools/emu/README.md`):
- `--preload ADDR=FILE`, memory as a reset leaves it. It also gives NOR's
  version word, without which every port boot takes the
  bootstrap-reprogramming branch: an existing divergence from the unit,
  now documented.
- The stall detector counts an address register that walked 4 KB as
  progress, like the memset rule. The chainloader's hash is a
  read-only walk.

## 5. What must be measured on the unit, in order

**Build 1 (29 Sep 2026, an MKII).** The switch ran, the load ran, and
after ~4 s the RCR soft reset restarted the unit: the bootstrap drew the
OCTABAM1 screen (the version string is NOR's, as predicted in step 4 of
the list below), then hung with every key a dimmer white than at power-on,
the same for `STOCK140.OBI` and `HOME.OBI`. ✅ Two facts from it:
- stock's spin never resets the unit; `PLEASE REBOOT!` means it;
- a soft reset does not reset the MKII panel controller, and the
  bootstrap blocks in its first panel exchange (`0x128`, no timeout).

**Build 3** (the MKII panel's `60 02` before the reset): the same hang.
**Build 4** (BOOT TRACE, a MIDI note per boot stage off MIDI OUT, recorded
on the Mac): ✅ after the switch the flashed image's entry ran, the
staged image's own entry ran 103 ms later (the stage SURVIVES the soft
reset and the chainload works on the unit), the DSP upload started and
never returned. ✅ The soft reset does not reset the DSP; its HI08
bootstrap ROM only listens after a chip reset. ❌ Retracted: "the MKII
panel is not reset" (this unit is flagged an MKI; build 3's panel bytes
were never sent). ❌ Also retracted: "flagged an MKI" (the handshake note
appears on only some boots, power-on included).

**Build 6**: before the reset each core is parked in a boot-ROM loader of
its own (`dsp_park.asm`: host command `$12` on stock's unused vector
`P:$24`; DMA and ESAI stopped; the interrupt left; count, address, words,
jump). Under the port both cores take it, the stock upload completes
through the loaders, and each core enters its stock bootstrap and payload
start again (`verify_osswitch`'s `dsp` case). The steps below stand, for
build 6 (with BOOT TRACE: `os-switch-trace`):

**Builds 7-14, on the unit** (BOOT TRACE throughout; the whole story is
`docs/contributing/FAILURE_MODES.md`'s OS SWITCH entry):
- ✅ Builds 7-10: both cores take the park command (note 13 = 3), the
  loaders take the bootstraps and jump, and the upload still stalls.
- ✅ Build 12: two stale words in core 0's host-side receive register
  (drained since), and every first record echo read `0x010101` where a
  power-on reads `0x000001`: the payload's host-port mode (HPCR bit 7).
  The record sender abandons an upload on a bad echo and its caller
  ignores it, so builds 11-12 came up with no DSP program and hung on
  play.
- ✅ Build 13 (bit 7 cleared): the echoes are right.
- ✅ **Build 14** (the parked loader hands the upload to the stock
  bootstrap, as the ROM does): after a switch to `HOME.OBI` both uploads
  complete in ~60 ms (final echo 3 on each core, as at power-on), audio
  frames run, the dialog reports the switch, audio and play work. A
  switch to `STOCK140.OBI` boots stock 1.40C. Steps 1-3 below pass for
  that much; step 3's five minutes and a project load, step 4 and step 5
  are not yet run.

Each step is one flash of the `os-switch` image, or none. Every failure
ends in the flashed image after a power-cycle.

1. **The reset comes back up.** MAIN MENU > OS > `STOCK140` >
   YES. Expect a reboot within a second or two of `WAIT`, into stock.
   Falsified by build 1's hang (OCTABAM screen, dim keys): power-cycle
   and report.
2. **SDRAM keeps the stage.** Switch to `HOME.OBI` (`make obi
   REMIX=os-switch OBI=HOME`, the flashed image itself). After the reboot,
   OS SWITCH's dialog should read `NOW: HOME.OBI (RCR)`.
   `NOW: THE FLASHED OS` means the mailbox was lost; `LAST: STAGE LOST
   (HASH)` means part of the stage was.
3. **The DSP and the caches.** After step 2, and after a switch to
   `STOCK140.OBI`: audio plays, FX work, and the unit survives a project
   load and five minutes of play. A hang at the logo or silence is the DSP
   not reset; a crash straight after the switch is a stale cache line.
4. **The version string.** 🟡 The boot screen keeps the flashed image's
   string whatever runs, because the MAIN OS image carries neither
   `1.40C` nor the `-V` string. Falsified by `1.40C` after a switch to
   stock.
5. **A real pair.** Two different remixes as `.OBI`s, several switches
   each way, with a project. The garbled-audio-after-upgrade trap
   (`FAILURE_MODES.md`) is the same DSP state carried across a reset. If
   it shows here it is the same cause, not a new one.

## 6. What this is not

- **Not a bootloader.** The bootstrap and NOR are untouched. The flashed
  image is the one that boots at power-on, and the only one a failed
  switch can land in.
- **Not persistent.** A power-cycle forgets the switch. A "boot X at
  power-on" option would mean the flashed image reading a choice from the
  card and switching at once, which roughly doubles boot time. Deliberately
  left out.
- **Not a way to run a newer bootstrap's OS.** `BVER` refuses it by
  design.

## 7. Questions back

- Is a fifth MAIN MENU category the right home (the root window was built
  five tall), or should it sit in SYSTEM beside OS UPGRADE (MAINMENU.md
  warns against growing SYSTEM)?
- OS SWITCH in every image by default (`schema.Remix.os_switch`): is that
  the maintainer's call to make upstream, or a local build option?
- Should the platform reserve's top 2.6 MB be reserved for the switch in
  every remix (a platform guard in `platform_build.py`), rather than
  checked by this module's gate only? Today no runtime comes near it.
- `Category.REFERENCE` is a stand-in; there is no "system" category.

## 8. Corrections this reading made to existing docs

`docs/firmware/ARCHITECTURE.md`:
- ❌ "The OS is loaded from CompactFlash via the ATA controller". It is
  unpacked from NOR (2.1).
- ❌ OS UPGRADE "writes the CF via ATA". It writes and verifies NOR
  (2.3).
- ❌ "The current MAIN OS is 1,112,560 B, 53% of the 2,080,768 B window".
  NOR holds the packed container; stock's `.bin` is 470 KB.
- The bootstrap's copy loop, listed as "not located", is `0x22a2` →
  `0x207e`.
