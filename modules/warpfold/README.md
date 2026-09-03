# WarpFold

A Mutable-Instruments-Warps-flavoured **ring modulator / wavefolder**, and the
first module built entirely against the manifest contract (`docs/MODULES.md`)
with no build knowledge of its own.

Unlike BusVerb and BusDelay it is a plain **per-track insert**: no bus role,
no shared-window buffers, placed in **both payloads**, so it runs on any of
the eight tracks and several tracks can host their own instance at once. All
state lives in the instance's own r7 block.

## Knobs

| slot | name | what |
|---|---|---|
| p0 | DRV  | fold drive, 1–7.9×. 0 = the folder is an identity (±1 LSB) |
| p1 | FREQ | ring carrier ~5 Hz–2.95 kHz, squared taper |
| p2 | TONE | one-pole lowpass on the wet; 127 ≈ transparent |
| p3 | MIX  | dry/wet; 0 = exact passthrough |
| p7 | MODE | FOLD / RING / BOTH (fold, then ring the folded signal) |

## Status

- Assembles, places in both payloads (`make bus REMIX=warped`), disassembly
  audited: every `mpy` encodes signed, no label-prefix hazards.
- Rendered locally through `dsp_host` (payload A): MIX=0 null, DRV=0 FOLD
  null, RING sideband placement, fold harmonics — see the build/verify notes
  in the repo history for the measurements.
- **Not yet flashed.** Descriptor behaviour (MODE select drawing as a 3-way,
  knob publishes) needs the standing on-unit reconfirm any new parameter
  rides (`docs/PARAM_PAGES.md`).

## Open

- Voicing pass by ear (fold curve steepness, carrier shape) once it has been
  heard on hardware.
- Warps' full crossfade/algorithm sweep (XFADE, analog drive model) is out of
  scope for v1 — this is the two characters that earn the insert its slot.
