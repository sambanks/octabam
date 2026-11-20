# `cxosc-core`

**cxosc-core** combines **CORE**, **REMIX SWITCH**, **CX OSC**, and the SEQ
pattern tool with the stock effects.

Machine-list signature `"CX",1` (no marker). PLAYBACK: PTCH RATO INDX FOLD SYMM FDBK.
RATO free 0.25..4; FUNC snaps classic table ≤4.01 (rounded). FOLD drive eased.
Mono; stock LFOs.

The older `CXOSC C28.RMX` image predates SEQ. Ilia reported that CX OSC sounded
good on an MKII with that image. On `CXSEQ CV.RMX` (BUILD 79, 20 Nov 2026),
Ilia confirmed that INDX changes the saw and triangle carrier waveforms. This
report covers those CX OSC behaviors; it does not report a SEQ behavior check.

```bash
make rmx REMIX=cxosc-core RMX='CXSEQ CV'
```
