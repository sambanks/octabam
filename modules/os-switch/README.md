# OS SWITCH

Boot another OS image from the card without writing the flash.
**MAIN MENU > OS** lists the `.OBI` files in the card root; [YES] on one
asks `BOOT <NAME>?` and boots it. A power-cycle always comes back to the
image in the flash. Every image built in this repo carries it
(`schema.Remix.os_switch`), and `make image` writes the `.OBI` beside the
`.bin`, so any build can be tried by switching to it instead of flashing it.

The design, and the firmware facts it rests on, are in
[`docs/proposals/FIRMWARE_SWITCHER.md`](../../docs/proposals/FIRMWARE_SWITCHER.md).
Markers as in `docs/firmware/CHIP.md`: ✅ measured (on the unit where it
says so, else under the ColdFire port or read from the image), 🟡 inferred,
with what would falsify it.

## Use

```bash
make image REMIX=<name> BUILD=<nn>        # out/OCTATRACK_OCTABAM<nn>.bin AND out/OCTABAM<nn>.OBI
make obi-stock                            # out/STOCK140.OBI: your stock 1.40C
make obi REMIX=<any remix> OBI=NAME       # out/NAME.OBI: any build, 12-character name
```

1. Copy the `.OBI` files to the card root.
2. MAIN MENU > OS. The pane's two headings: `NOW <NAME>`, the image
   running (its build's VERSION), and `HOME <NAME>`, the flashed one a
   power-cycle returns to (carried in the mailbox across a switch). Then a
   line if the last switch was refused, then every `.OBI`, sorted, without
   the extension. It is read again each time MAIN MENU opens, without
   disturbing the stock browsers' listing (the scan's global name pool and
   cache are saved and restored around it, `docs/contributing/FAILURE_MODES.md`).
3. [YES] on a file: `BOOT <NAME>?` / `PLAYBACK WILL STOP` / `POWER-CYCLE:
   BACK HOME`. [YES] stops playback, syncs the project (as OS UPGRADE
   does), loads the file and resets the unit.
4. A power-cycle boots the flashed image again.

### At power-on: the boot picker

When the unit powers on with a project named, the card mounted and at
least one `.OBI` in the root that is not this image, the stock confirm
dialog comes up **before the project loads**:

```
        OS SWITCH
  BOOT <NAME>?
  NO: STAY <THIS IMAGE>
  <> MORE  STAY IN 3
       [YES]   [NO]
```

- **Untouched,** the countdown runs out in 3 s and this image boots
  (`STAY IN 3`).
- **Arrows** (any of the four) step through the other images (the image's
  own `.OBI` is skipped) and start the countdown again, now for the image
  shown (`BOOT IN 3`): browse to one and let go, and 3 s after the last
  press it switches to it.
- **YES** switches to the image shown, as the pane does but without the
  project sync (nothing is loaded yet, and the next image boots from the
  same battery SRAM; syncing there made the engine report `INVALID STATE`
  on the unit, `docs/contributing/FAILURE_MODES.md`).
- **NO** boots this image at once: what the boot would have posted is
  posted as stock would have posted it.

The picker does not open, and the boot is stock's, when this boot is itself
a switch (the choice was made already), when no project is named, when a
stock dialog is already up, when the last set or project would not mount
(stock's own NO SET / missing-project dialog comes instead: the stock
dialog drops a request while another is open, so the picker steps aside),
or when there is no other image on the card. It opens once per power-on;
the USB-disk exit and a card re-insert reload the project as stock does.

Why here: the project load (and, on a real card, its samples) is the
longest part of a boot, and a switch made from the pane throws it away.
The picker holds the load back instead. See **How** for the mechanism,
and `docs/proposals/BOOT_DEFAULT.md` for the designs it was chosen over.

An `.OBI` is the raw image the bootstrap would unpack to `0x40000400`. It is
Elektron's OS with your changes, so like the `.bin` it never leaves your
machine and your card. `make obi` makes the same three checks the unit
makes: the OS entry's first instruction, a length that fits the stage
(2,706,400 B), and the bootstrap version (below). A target does not need
this module: stock 1.40C is a valid target, but it has no OS category, so
from stock you power-cycle to come back.

A remix that keeps every stock DSP effect has no DSP words for the park
code (below) and sets `os_switch=False`; its `.OBI` is still a valid
target. `OCTABAM_NO_OS_SWITCH=1` builds without it everywhere.

The version string on the boot screen is the FLASHED image's, whichever OS
runs. ✅ Measured on an MKII, 29 Sep 2026: a switch to `DSPRESET.OBI` came
up with `BSRET3OS2` under the logo, and a switch to `BASE1` did the same.
The pane's `NOW` line is the one that names the running image -- and it
names it after the build's `VERSION`, which is why `make obi OBI=NAME` now
builds with `VERSION=NAME`: before that fix the file was `BASE1.OBI` and
the pane said `OCTABAM79` (an MKII, 29 Sep 2026). Neither `1.40C` nor the `-V` string is
in the MAIN OS image, so it is read from the flash header 🟡. Trust the
pane's `NOW` line instead. (SYSTEM STATUS after a switch is still
unmeasured.)

## How

| piece | where | what |
|---|---|---|
| `chain.s` | the loader (`Linked(loader=True)`: assembled into `tools/remix/loader.S`, appended after the OS unpacked), detour at `0x40000412` | the gate, at the OS entry after it parks the bootstrap's argument. Without a mailbox it records the boot (`NONE`, or `RUN` right after a handover) and resumes. With one it spends it first, checks that the chainloader's body at `0x49200400` is whole (its longs sum to the mailbox's), and runs it. It lives in the loader because ROM caves are what full remixes run out of (bottleservice: 274 B of chainloader cost MODULATION's label formatter its place) |
| `switch.s`: `osw_body` | copied to `0x49200400` by the switcher | the chainloader's body, position-independent: the check word, the length, the bootstrap version against NOR's word at `0x3ffc`, the hash over the stage; then a 40-byte stub at `0x49200100` copies the stage over `0x40000400` with the caches off and invalidated, restores the bootstrap's exit `CACR` (`0x0008c000`) and calls the entry with the bootstrap's argument. A refusal writes why and returns to the gate |
| `switch.s` | the platform runtime (DRAM) | MAIN MENU > OS: the root's four stock rows from your image (`.incbin`), then OS (rows pointer `0x400cbda4`, count `0x400cbd8c` 4 → 5, a swap-arrows icon in stock's 19×9 form); the scan at MAIN MENU's opening (detour `0x40064c32`, the stock dir scan `0x4007f598`); the dialog (`0x4006d57c`); the load, the reset and the DSP park |
| `switch.s`: the boot picker | detours `0x4002574c` and `0x4002573e` (a `jsr`) | Two posts can start a boot's loading, and which comes depends on the battery SRAM. Sys's media case asks `0x4004abcc` whether the card is the one the SRAM last saw (its id at `0x100f8584`): **the same card** (every power-on after the first) keeps the project in SRAM and only mounts the last set (`0x400256b8`), which posts the engine's LOADING FILES job at `0x4002573e`; **an empty id** (fresh SRAM) reloads the project through `0x4002574c` ("if a project is named, post LOAD PROJECT") first. Whichever hook is the boot's first opens the dialog and returns without posting; the other is held while it is up, and NO posts what was held in stock's order, the files job once per post held, so the boot after NO is stock's boot. The arrows are an input layer on top of the dialog's (TEMPO BUS's form), which keeps YES and NO. The countdown is a soft timer on the sys tick (`0x40031a0c(period, fn)`, cancelled with `0x40031abc(handle)`; stock's own screens redraw this way), 12 ticks per 100 ms step: ✅ the tick is ~117 Hz on an MKII (the first unit build used 6, assuming 60 Hz, and counted 3 s down in 1.54 s); at zero it cancels itself by clearing its slot's function word, which the timer service checks before re-linking the node (`0x40031994`), and answers through the dialog's own close: NO untouched (`0x4006d4a8`, the USB-disk exit's), YES on the image shown after an arrow (`0x4006d47c`, then the answer). Before it opens it runs the set mount's two checks (`0x40025650`: the set and its `AUDIO`; `0x400255ec`: the project), as the USB-disk exit does before it posts |
| `dsp_park.asm` | both DSP payloads, WHOLLY in stock's dead interrupt vectors: entry on `P:$1E`, 31 words at `P:$20..$3E`, a one-word bridge, 8 words at `P:$06..$0D` | the park (below). It costs the effect region nothing, so a remix that harvests nothing can carry the switcher (`remixes/base/`) |
| `osw.inc` | all of them | the stage layout and the status words; the gate parses it |

**The stage** is the top of the platform reserve: mailbox `0x49200000`,
stub `0x49200100`, the chainloader's body `0x49200400`, image `0x49201000..0x49495de0` (uncached aliases). Stock
never touches the reserve, and nothing between a reset and the OS entry
writes it (the bootstrap only unpacks the image). The gate checks that the
remix's own runtime ends below the mailbox.

**Why the OS entry and not the boot detour.** The DSP upload at
`0x40001e50` assumes both cores sit in their HI08 boot ROM, which only a
hardware reset gives. At `0x40000412` nothing has run: no upload, no
cache set-up, no interrupts. The staged image does all of it itself, from
the state the bootstrap left.

**The bootstrap version guard.** The OS entry compares the bootstrap
version the image carries (`0x400dea48`, `0x0408` in 1.40C) with NOR's
`0x3ffc`. If the image's is newer, it reprograms the bootstrap sector
(`0x4000f9b4`), which holds the Startup Menu and the MIDI recovery. The
chainloader runs only an image whose word equals NOR's. `make obi` refuses
any other.

**Where the park's words come from.** None (29 Sep 2026). Not one word of
the effect region, where it used to cost 40. Stock leaves a run of interrupt vectors as `jmp *` -- a
self-jump that would freeze the core if that interrupt ever fired, which is
how you know it never does -- so the handler's 22 words live there
(`P:$20..$35`, entered by `jsr` at `P:$1E`, host command `$0F`) and only
the 18-word boot-ROM loader is packed into the harvested region. The park
splits at `osw_ldr` and each half is assembled at its real address; the
head's one `#>osw_ldr` reference is rewritten to wherever the tail landed
(`schema.DspSection.pin`, `pin_split_label`).

That is safe only while nothing arms an interrupt in the run, and once code
lives there the freeze that would announce one is gone -- so
`tools/verify/verify_dspvectors.py` audits it on every build: the runs are
all self-jumps, no DMA whose vector is in one has DIE set, no ESAI control
word has an interrupt enable, and the set of peripherals either payload
configures is the audited one. ✅ Under the port every OS SWITCH check
passes with the park in the vectors, including both cores taking the park
command at `$1E` and re-entering their payload starts. ✅ **On an MKII, 29
Sep 2026**: `bottleservice-ret` built this way (`BSRETVEC`, reached by a
switch, no flash) booted, played a session with the park resident in the
vector table, and switched away to the flashed image with audio working --
which is the park running from the vectors, and the chip taking a host
command at a vector stock never uses. Its payload A went from 2 free words
to 24.

**The DSP.** The soft reset restarts the ColdFire, not the DSP, and the
next OS's upload (`0x40001e50`) assumes a chip reset: each core in its
HI08 boot ROM, the host port in the ROM's mode and empty. ✅ Measured on
the unit (BOOT TRACE, builds 4-14; the whole story is
`docs/contributing/FAILURE_MODES.md`). So before the reset `osw_park` sends
each core host command `$0F` (vector `P:$1E`, stock's dead DMA3 slot, a
`DspHook` in both payloads), and `dsp_park.asm`:
- masks interrupts, stops DMA 0-5 and both ESAI ports;
- clears HPCR bit 7, which the payload's start set (`P:$30016..$30018`):
  in that mode the ColdFire read every record echo as `0x010101`, and the
  record sender (`0x40001b18`) silently abandoned the upload (build 12);
- leaves the interrupt (`move ssh,x0` / `move x0,ssh` / `rti`: the
  vendored emulator runs no peripheral inside a long interrupt, and the
  chip does not care);
- loads as the boot ROM does: a count, an address, that many words (into
  the shared window through X), then `jmp (r1)` into the stock bootstrap
  the OS sent, which loads the payload as at power-on.
`osw_park` then drains each core's host-side receive register (build 12
found two stale words on core 0). Every instruction form has a stock site
except `bclr #7` on HPCR (the payload's own `bset #7` and `bclr #5`/`#6`
there are); the HRDF waits are written with a numeric displacement because
`dsp_asm` encodes a label there as an absolute address.

**The reset.** Stock never resets the unit after OS UPGRADE: it shows
`UPGRADE DONE` / `PLEASE REBOOT!` and waits for a power-cycle. So the
switcher masks interrupts, drains the panel's UART queue (OS UPGRADE's
first two steps), and requests a soft reset (RCR SOFTRST, `0xfc0a0000`
bit 7, MCF54455 RM). ✅ Measured on an MKII (builds 1-14, 29 Sep 2026):
the unit resets at once and the bootstrap runs again. On an MKII the
switcher first sends the panel `60 02`, the byte pair the OS's own loader
handshake (`0x4001f4dc`) opens with. ❌ Retracted: build 1's "the panel
controller is not reset and the bootstrap blocks in its first panel
exchange"; the hang was the DSP (above). Whether `60 02` is needed at all
is not measured; it is harmless (the OS sends it at boot). An MKI's panel
is sent nothing (untested on an MKI).

## Measured ✅ (under the ColdFire port, `tools/verify/verify_osswitch.py`)

- **The menu, the load and the reset sequence run from the panel.** Keys
  NO, PROJ (the MKII's MAIN MENU), DOWN ×4 (OS), YES, YES, YES on a card
  holding `STOCK140.OBI`: MAIN MENU's scan, the row's pick, the dialog's
  answer, the deferred load and the reset all run. The stage reads back
  equal to the file (1,112,560 B); the chainloader's body sits at
  `0x49200400` with its length and sum in the mailbox, beside the image's
  length, hash `0xb2fc346b`, check word and name. The port does not reset,
  so the switcher reaches the RCR fallback and records `RCR `.
- **The chainload, fed exactly the memory the switcher left.** The gate
  and the body run, the stub runs from the stage, and stock's entry runs a
  second time. The home image's loader never runs, `0x40000412` holds
  stock's instruction again, and stock 1.40C reaches the RTOS handoff.
  The hash over 1.1 MB costs about 8.9 M instructions.
- **An image that carries OS SWITCH, staged as its own target,** reports
  `RUN `. The mailbox is spent and its loader runs once.
- **Refusals.** Each one boots the flashed image and names its reason: no
  mailbox `NONE`, one flipped byte in the stage `HASH` (the mailbox still
  spent), one flipped byte in the body `HASH` (spent before the body is
  checked), NOR's version absent `BVER`, a length past the stage `SIZE`.
- **The boot picker from SRAM that knows the card** (30 Sep 2026, after
  the unit showed BSRET6BP never opening it: `docs/contributing/FAILURE_MODES.md`).
  Booted from a first boot's SRAM, dumped: the set mount's files post opens
  it, no LOAD PROJECT is posted, and after the countdown both files posts
  it held (the boot mounts the set twice) are posted.
- **The boot picker** (30 Sep 2026; `ot_emu --boot-load`, a power-on
  whose only LOAD PROJECT is the firmware's own). On a real project
  (a set with its `AUDIO`, three `.OBI` files, one named as this image) and
  on the gate's synthetic card: the dialog opens after the card mount and
  before anything is posted; untouched, it counts exactly 30 ticks, answers
  NO, and LOAD PROJECT then LOADING FILES are posted and the load runs; NO
  does the same at once; RIGHT skips this image's own name and YES stages
  the image shown (`STOCK140.OBI`, 1,112,560 B) with nothing loaded; a set
  without `AUDIO` gets no picker and stock's own dialogs. Rendered from the
  LCD: `BOOT BSRET4B?` / `NO: STAY OCTABAM0` / `<> MORE  AUTO 3`, then
  `BOOT STOCK140?` without the countdown after RIGHT. Before the files job
  was held too, it ran during the countdown and its LOADING FILES window
  covered the dialog, and the load waited behind it (~2.3 s).
- **The screens,** rendered from the port's LCD (29 Sep 2026): MAIN MENU
  with OS and its icon, the pane (`NOW FLASHED`, five files sorted, the
  cursor on the first), the dialog.
- **Every remix builds with it** (26 of 37; the other 11 keep every stock
  DSP effect and opt out), and with `OCTABAM_NO_OS_SWITCH=1` all 24
  `scripts/refhash.sh` configurations are bit-identical to the tree before
  it (the loader-unit machinery changes nothing on its own).

## Measured ✅ on the unit (an MKII, 29 Sep 2026, build 14 with BOOT TRACE)

1. **SDRAM keeps the stage across the reset,** and the chainload runs:
   the staged image's entry runs ~190 ms after the flashed image's, and
   the dialog reports the switch.
2. **The DSP comes back:** after a switch to `HOME.OBI` both payload
   uploads complete in ~60 ms (final echo 3 on each core, as at
   power-on) and audio frames run.
3. **The OS runs normally after it:** audio and play work. A switch to
   `STOCK140.OBI` boots stock 1.40C.

## Not yet measured 🟡

1. **Endurance:** a project load and five minutes of play after a switch,
   and several switches each way between two different remixes.
2. **The caches.** The stub invalidates the I-cache and branch cache and
   restores the bootstrap's exit `CACR`; nothing has shown a stale line.
3. **The version string** after a switch to stock (which the flash header
   probably keeps; see Use).
4. **An MKI.**
5. **The boot picker on the unit:** that the dialog draws and takes keys
   at that point of a real boot, and the time from power-on to the picker
   and from NO to the loaded project. The BOOT TRACE build
   (`remixes/test/os-switch-trace`) sends note 26 when the picker is
   reached (velocity 0: it opened; 1 no project, 2 this boot is a switch,
   3 no file system yet, 4 a dialog is up, 5 the set or project would not
   mount, 6 no other image, 7 the dialog did not open) and note 27 with
   the answer (0 YES, 1 NO, 2 the countdown's NO, 3 the countdown's YES).

Every failure above ends in the flashed image after a power-cycle: the
flash is never written, and the mailbox is spent before the staged image
runs.
