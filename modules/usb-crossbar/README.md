# `usb-crossbar` — USB CROSSBAR

The USB controller bursts over the crossbar and is served first on the
SDRAM and SRAM-backdoor slaves. Written once at the stock USB controller
init (`0x4001e030`) and left on.

| register | stock | this module | meaning |
|---|---|---|---|
| SCM BCR `0xfc040024` | `0` (reset; nothing sets it) | `0x3ff` | USB bursts to and from every slave |
| XBS PRS2 / PRS4 | `0x65403210` (USB level 6 of 7) | `0x60504321` (USB level 0) | master priority on SDRAM (slave 2) and the SRAM backdoor (slave 4) |
| XBS CRS2 / CRS4 | `0x110` (round robin) | `0x10` (fixed, park on last) | arbitration mode |

## Measured

The boot-time write has run under the port only (the port does not model SCM or XBS registers).

## On the unit

Bryan T's MKII, usbin-test builds 12-14, 26 Sep 2026. Same busy project, one minute per row unless stated:

| setting | bad OUT packets |
|---|---|
| stock | 1,189 / min |
| BCR 0x3ff | 5-11 / min |
| BCR 0x3ff + USB first (this module's values) | 0 in 10 min, no audible or UI change |

Ruled out on the way: the cable and port, USBMODE.SDIS, RXPBURST 1-8 (16
exceeds the FIFO), packet buffers in SRAM alone, a four-channel IN stream
alone, bit errors.

In those builds the registers were written when the host opened the
stream, from the frame-transfer interrupt, and never restored; DISK MODE
and a further session ran under them (build 16, 27 Sep 2026). This module
writes the same values at boot instead, so the setting does not depend on
which module opens a stream.

erreye's MK1, 7 Oct 2026: the same remix (`felipe`, a local branch with
USB AUDIO OUT TRACKS POST) without this module (OCTABAM3) and with it
(OCTABAM4), one after the other, a 2 m cable straight into an M1 Mac, Live
holding the stream open:

| image | time | EP 0x83 transaction errors (macOS) | device counters |
|---|---|---|---|
| OCTABAM3, without | ~5 min | 0 | 0 underruns, 0 overruns, 0 bankdup, fill 240–271 |
| OCTABAM4, with | ~4 min | 0 | 0 underruns, 0 overruns, 0 bankdup, fill 238–265 |

No difference on that unit and cable. Their 5 Oct before/after (~2,270
errors a minute, then 0) is retracted by them: the earlier image (OCTABAM2
or 3) was not recorded and a 3 m cable they also used was bad
(`docs/contributing/FAILURE_MODES.md`, "A marginal USB cable"). Streaming
and DISK MODE ran normally with this module on the MK1.

The voice path under this priority (Bryan T's CF METER takes, 4 Oct 2026,
`docs/firmware/ARCHITECTURE.md` "ColdFire time per frame on a unit"): each
added FLEX voice costs the frame interrupt 16.6 µs with the USB cable out
and 16.9 µs with a host streaming both directions, so USB DMA on the SDRAM
slave does not stall the renderer measurably. The USB stack itself (IN
ABCD + OUT TRACKS MAIN CUE) costs ~14 µs of mean ISR per frame idle and
~24–26 µs once anything plays; OUT MAIN CUE in its place reads 27–50 µs
less (the OUT TRACKS MAIN CUE README, *On the unit*). The
stock DELAY on T1–T4 with seven FLEX voices and USB streaming added
nothing measurable to the ISR mean.

## Open

- CAPTURE and card writes under this priority on a MKI (nordseele's review
  of PR #468, 27 Sep 2026); DISK MODE ran on erreye's MK1.
- Whether a MK1 under a busy project shows the MKII's bad OUT packets with
  BCR 0: erreye's remix has no USB AUDIO IN, so their A/B streamed
  device to host (EP 0x83) only; the MKII's errors were on host-to-device
  packets.
- The stock DELAY on eight tracks with Flex playback (SDRAM-heavy DMA)
  under USB-first arbitration: four tracks with seven voices measured
  clean on the ISR mean (above); eight tracks, and the routine's own
  eDMA waits, not.

## Why

In device mode the controller has one 16-byte RX FIFO (MCF54455RM 10.4.3),
about 270 ns of slack at 480 Mbit/s. With BCR 0 it is emptied one beat at a
time; under a busy project it overflowed near the end of an isochronous OUT
packet and the controller flagged a transaction error (CRC), 2 to 12 bytes
short. Stock's own USB traffic is bulk and retried, so stock never showed
it.

## Ground

| what | where |
|---|---|
| code | DRAM unit `usbcrossbar`, 10 instructions |
| hook | `0x4001e030`, the USB controller init's `movel #0x08000000,%d0`, replayed |
