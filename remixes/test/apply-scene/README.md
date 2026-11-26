# `apply-scene` — APPLY SCENE beside BRAIN, KITS and SCENES P2

The stock chooser plus [APPLY SCENE](../../../modules/apply-scene/README.md) next to the modules that share
its state: KITS (the Part a pattern plays), SCENES P2 (bytes 30-31 of each scene) and BRAIN (the TRACKS
setting). No DSP module; the 14 stock effects keep the FX choosers stock's.

`tools/verify/verify_apply_scene.py` drives the panel under the port on this image: SCENE + YES into the Part
(A, B, the blend, each committed; TRACKS ACTIVE and ALL; page 2), step locks in GRID RECORDING, SCENE + YES ignored while LIVE RECORDING plays, the blend saved into a
scene, KITS' PTN + FUNC + RIGHT followed by SCENE + YES, MIDI mode and stock's own scene keys.

```bash
make image REMIX=test/apply-scene BUILD=1
```
