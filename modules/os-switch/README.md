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
| `NOW: NAME.OBI (SPIN)` | this image came from the card; stock's own post-upgrade spin reset the unit |
| `NOW: NAME.OBI (RCR)` | the same, but the reset came from the ~4 s fallback, the reset controller's soft reset |
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

**The reset.** It copies OS UPGRADE's own after-flash sequence
(`0x4007fe6c..0x4007fe7c`: interrupts masked, the panel's UART queue
flushed, then spinning). Something resets the unit from there; the image
does not show what. 🟡 Probably a watchdog that the masked interrupts stop
feeding: neither the OS nor the bootstrap writes the reset controller or
the core watchdog. After about 4 s the switcher requests a soft reset
(RCR SOFTRST, `0xfc0a0000` bit 7). 🟡 From the MCF54455 reference manual;
no site in the image. The mailbox records which one it reached.

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

## Inferred 🟡 / not measured: the hardware checks

1. **SDRAM keeps the stage across the reset.** The bootstrap re-initialises
   the SDRAM controller (`0x288e`: precharge, refresh, mode register) and
   unpacks the OS; nothing in it clears or tests RAM outside TESTMODE.
   Falsified by `NOW: THE FLASHED OS` or `LAST: STAGE LOST (HASH)` right
   after a switch to an image that carries this module.
2. **Something resets the unit.** Falsified by a unit that stays on the
   dialog's `WAIT` for more than about 10 s. Power-cycle; nothing was
   written.
3. **The DSP comes up after a chainloaded boot.** The upload needs both
   cores in their boot ROM, so the reset must reach the DSP. Falsified by a
   unit that boots with no audio, or hangs at the boot logo. Power-cycle.
4. **The caches.** The port has none. The stub invalidates the I-cache
   and branch cache and restores the bootstrap's exit `CACR`. A stale line
   would show as a crash straight after the switch. Power-cycle.

Every failure above ends in the flashed image after a power-cycle: the
flash is never written, and the mailbox is spent before the staged image
runs.
