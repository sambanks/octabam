# `cxosc-core`

**cxosc-core** combines **CORE**, **REMIX SWITCH**, **CX OSC**, and the SEQ
pattern tool with the stock effects.

Machine-list signature `"CX",1` (no marker). PLAYBACK: PTCH RATO INDX FOLD SYMM FDBK.
RATO free 0.25..4; FUNC snaps classic table ≤4.01 (rounded). FOLD drive eased.
Mono; stock LFOs.

The older `CXOSC C28.RMX` image predates SEQ. Ilia reported that CX OSC sounded
good on an MKII with that image. The current combination has not been measured
on hardware.

```bash
make rmx REMIX=cxosc-core RMX='CXSEQ CV'
```
