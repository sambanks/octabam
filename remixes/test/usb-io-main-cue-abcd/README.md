# `usb-io-main-cue-abcd` — MAIN L/R and CUE L/R (four channels) out, four channels into inputs A-D, on the stock effects

The stock chooser plus USB (LAYOUT MAIN CUE, INPUTS ABCD).

- **USB** (markandrus/octemu's source) at LAYOUT MAIN CUE, INPUTS ABCD: USB-MIDI mirroring
  DIN; MAIN L/R and CUE L/R (four channels) to the host, 24-bit, every 250 µs.
  [`USB`](../../../modules/usb/README.md#main-cue).
- USB's crossbar (Bryan T): the USB controller bursts and goes first on the
  SDRAM and SRAM crossbar ports, set at boot. Without it the IN stream loses
  packet tails under a busy project. [`USB`](../../../modules/usb/README.md#crossbar).
- USB's audio in (Bryan T) at INPUTS ABCD: four channels into inputs A-D, asynchronous with implicit feedback from the
  out stream. [`USB`](../../../modules/usb/README.md#abcd).
- 13 of the 14 stock FX2 effects. SPATIALIZER is on neither menu: its words on
  payload A hold USB's RX inject, and a project that still selects
  it runs NONE.

Under the port, `make check REMIX=usb-io-main-cue-abcd` runs `verify_usb` (six interfaces
at high speed, five at full) and `verify_usb_in` (the host's channels
bit-exact on the module's inputs, the other inputs untouched, the jacks back
after alt 0). This form has not been flashed.

Bryan T's usbin-test `usb-io` (builds 12–16) was this
combination with the inject poked into SPATIALIZER's words: on his MKII about
5 million host packets with no bad packet, underrun or overrun, DISK MODE in
and out with the stream back afterwards, a round trip through the two rings
of about 31 ms. This build of it has not been flashed.

```
make image REMIX=usb-io-main-cue-abcd BUILD=1   # -> out/OCTATRACK_OCTABAM1.bin
```

[BUILDING.md](../../../docs/guide/BUILDING.md) is the walk-through from a
fresh machine to a flashed unit. On the unit: `tools/hw/usb_probe.py`
(sustained, then churn) with the counters before and after, then a host →
inputs → recorder take.
