# `usb-io-main-ab` — MAIN L/R (two channels) out, a stereo pair into inputs A/B (C/D stay on the jacks), on the stock effects

The stock chooser plus USB MIDI, USB AUDIO OUT MAIN, USB CROSSBAR and USB AUDIO IN AB.

- **USB MIDI** and **USB AUDIO OUT MAIN** (markandrus/octemu's source): USB-MIDI mirroring
  DIN; MAIN L/R (two channels) to the host, 24-bit, every 250 µs.
  [`modules/usb-audio-out`](../../../modules/usb-audio-out/README.md#main).
- **USB CROSSBAR** (Bryan T): the USB controller bursts and goes first on the
  SDRAM and SRAM crossbar ports, set at boot. Without it the IN stream loses
  packet tails under a busy project. [`modules/usb-crossbar`](../../../modules/usb-crossbar/README.md).
- **USB AUDIO IN AB** (Bryan T): a stereo pair into inputs A/B (C/D stay on the jacks), asynchronous with implicit feedback from the
  out stream. [`modules/usb-audio-in`](../../../modules/usb-audio-in/README.md).
- 13 of the 14 stock FX2 effects. SPATIALIZER is on neither menu: its words on
  payload A hold the IN module's RX inject, and a project that still selects
  it runs NONE.

Under the port, `make check REMIX=usb-io-main-ab` runs `verify_usb` (six interfaces
at high speed, five at full) and `verify_usb_in` (the host's channels
bit-exact on the module's inputs, the other inputs untouched, the jacks back
after alt 0). This form has not been flashed.

```
make image REMIX=usb-io-main-ab BUILD=1   # -> out/OCTATRACK_OCTABAM1.bin
```

[BUILDING.md](../../../docs/guide/BUILDING.md) is the walk-through from a
fresh machine to a flashed unit. On the unit: `tools/hw/usb_probe.py`
(sustained, then churn) with the counters before and after, then a host →
inputs → recorder take.
