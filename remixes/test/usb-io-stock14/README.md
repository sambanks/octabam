# `usb-io-stock14` — MAIN L/R and CUE L/R out, four channels into inputs A-D, on all fourteen stock effects

The stock chooser, all fourteen effects, plus USB (MAIN and CUE out, IN ABCD, USB MIDI).

- **USB** at MAIN CUE, IN ABCD: USB-MIDI mirroring DIN; MAIN L/R and CUE L/R
  to the host; the host's four channels into inputs A-D (the jacks while its
  stream is closed). [`USB`](../../../modules/usb/README.md).
- All 14 stock FX2 effects, SPATIALIZER included. Nothing is harvested, so
  there is no donor region: USB's RX inject (29 words) goes above payload
  A's code, `P:$1fdf..$1ffb`, in a load record of its own. A pre-boot copy of
  payload A carries the record, and the DSP boot's upload pointer is poked
  at it (`DspSection.tail`, `docs/contributing/PLACEMENT.md`). The copy costs
  a 167,318 B DRAM region, 28 sample pages.

Under the port, `make check REMIX=usb-io-stock14` runs `verify_usb` and
`verify_usb_in` (the host's channels bit-exact on inputs A-D through the
inject at the tail). On Bryan T's MKII (OCTABAM4, macOS),
`tools/hw/usb_in_tones.py` reads the same as the donor-region injects did:
each input at -18.1 dBFS on its own side, the other side below -178 dB, the
rest within +-1.5 LSB. So the chip runs code at `P:$1fdf..$1fff`, and the DSP
boots from the pre-boot copy.

```
make image REMIX=usb-io-stock14 BUILD=1   # -> out/OCTATRACK_OCTABAM1.bin
```
