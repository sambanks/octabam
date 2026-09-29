# OS SWITCH

Boot another OS image from the card without writing the flash.
**MAIN MENU > CONTROL > OS SWITCH** lists the `.OBI` files in the card
root. [YES] boots the one offered and [NO] offers the next. A power-cycle
always comes back to the image in the flash.

The design, and the firmware facts it rests on, are in
[`docs/proposals/FIRMWARE_SWITCHER.md`](../../docs/proposals/FIRMWARE_SWITCHER.md).
Markers as in `docs/firmware/CHIP.md`: ✅ measured (here: under the ColdFire
port, or read from the image), 🟡 inferred, with what would falsify it.

## Use

```bash
make image REMIX=os-switch BUILD=<nn>     # the HOME image: flash it once (FLASHING.md)
make obi-stock                            # out/STOCK140.OBI: your stock 1.40C
make obi REMIX=<any remix> OBI=NAME       # out/NAME.OBI: any build, 8-character name
```

1. Copy the `.OBI` files to the card root.
2. MAIN MENU > CONTROL > OS SWITCH, then [YES]. The dialog reads
   `BOOT NAME.OBI?`, `NO: NEXT FILE i/N`, and a line that says what is
   running (see below).
3. [YES] stops playback, syncs the project (as OS UPGRADE does), loads
   the file and resets the unit.
4. A power-cycle boots the flashed image again.

An `.OBI` is the raw image the bootstrap would unpack to `0x40000400`. It is
Elektron's OS with your changes, so like the `.bin` it never leaves your
machine and your card. `make obi` makes the same three checks the unit
makes: the OS entry's first instruction, a length that fits the stage
(2,706,400 B), and the bootstrap version (below). A target does not need
this module. Stock 1.40C is a valid target, but it has no OS SWITCH row:
from stock, power-cycle to come back.

The dialog's third line:

| line | means |
|---|---|
| `NOW: THE FLASHED OS` | no switch reached this boot (a power-on, or the stage did not survive the reset) |
| `NOW: NAME.OBI (RCR)` | this image came from the card, through the reset controller's soft reset |
| `NOW: NAME.OBI (SPIN)` | the same, but the soft reset was never recorded as requested (not expected) |
| `LAST: STAGE LOST (HASH)` | the stage changed across the reset; the flashed image booted |
| `LAST: WRONG BOOTSTRAP` / `LAST: BAD SIZE` | the chainloader refused the stage |

The version string on the boot screen and in SYSTEM STATUS is probably the
flashed image's, whichever OS runs. 🟡 Neither `1.40C` nor the `-V`
string is in the MAIN OS image, so it is read from the flash header.
Falsified if a switch to `STOCK140.OBI` shows `1.40C`. Trust the dialog's
third line instead.

## How

| piece | where | what |
|---|---|---|
| `chain.s` | a ROM cave, detour at `0x40000412` | the OS entry, after it parks the bootstrap's argument in `0x400b9650`. If the mailbox holds a switch, it spends the mailbox, then checks the length, the bootstrap version against NOR's word at `0x3ffc`, and the hash over the stage. It then copies a 40-byte stub to `0x49200100`; the stub copies the stage over `0x40000400` with the caches off and invalidated, restores the bootstrap's exit `CACR` (`0x0008c000`) and calls the entry with the bootstrap's argument. Any refusal replays the displaced `movea.l #0x48000000,%sp` and boots on |
| `switch.s` | the platform runtime (DRAM) | the CONTROL row. Stock's six rows come from your image at build time (`.incbin`); `osw_rows` is `SymbolRef`'d into `0x400cbd6c` and the count at `0x400cbd54` poked 6 → 7. It also has the picker (the stock dir scan `0x4007f598` for `OBI`, the stock confirm dialog `0x4006d57c`), the load and the reset |
| `osw.inc` | both | the stage layout and the status words; the gate parses it |

**The stage** is the top of the platform reserve: mailbox `0x49200000`,
stub `0x49200100`, image `0x49201000..0x49495de0` (uncached aliases). Stock
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

**The DSP.** The soft reset restarts the ColdFire, not the DSP, and the
next OS's upload (`0x40001e50`) assumes a chip reset: each core in its
HI08 boot ROM, the host port in the ROM's mode and empty. ✅ Measured on
the unit (BOOT TRACE, builds 4-14; the whole story is
`docs/remixer/FAILURE_MODES.md`). So before the reset `osw_park` sends
each core host command `$12` (vector `P:$24`, stock's unused
`reserved24`, a `DspHook` in both payloads), and `dsp_park.asm`:
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

- **The row, the picker, the load and the reset sequence run from the
  panel.** Keys NO, FUNC+MIXER, DOWN ×2, YES, DOWN ×6, YES, YES on a card
  holding `STOCK140.OBI`. The stage reads back equal to the file
  (1,112,560 B). The mailbox holds its length, hash `0xb2fc346b`, check
  word and name. The port does not reset, so the switcher reaches the RCR
  fallback and records `RCR `.
- **The chainload, fed exactly the memory the switcher left.** The
  chainloader runs, the stub runs from the stage, and stock's entry runs a
  second time. The home image's loader never runs, `0x40000412` holds
  stock's instruction again, and stock 1.40C reaches the RTOS handoff.
  The hash over 1.1 MB costs about 8.9 M instructions.
- **An image that carries OS SWITCH, staged as its own target,** reports
  `RUN `. The mailbox is spent and its loader runs once.
- **Refusals.** Each one boots the flashed image and names its reason:
  no mailbox `NONE`, one flipped byte `HASH` (the mailbox is still
  spent), NOR's version absent `BVER`, a length past the stage `SIZE`.
- **The screens,** rendered from the port's LCD: the CONTROL menu with the
  seventh row, and the dialog.

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

Every failure above ends in the flashed image after a power-cycle: the
flash is never written, and the mailbox is spent before the staged image
runs.
