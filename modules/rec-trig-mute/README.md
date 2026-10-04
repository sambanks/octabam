# `rec-trig-mute` -- REC_TRIG_MUTE

Mute a track's recorder trigs without deleting them. Hold `[TRACK]` and press `[NO]`: the held tracks' recorder trigs stop firing -- a recording already running finishes -- and a toast reads `REC TRIGS MUTED`. `[TRACK]` + `[YES]` brings them back (`REC TRIGS UNMUTED`). Any screen, grid recording or not; it holds across pattern changes until you unmute, and every track starts unmuted at power-on. A muted track shows two dots beside its play/stop icon at the screen edge (`..■` / `..▶`). MIDI CC 80: 0 unmutes, 1-127 mutes, on a track's channel (AUTO channel = the active track), with AUDIO CC IN on; the keys send CC 80 (1 / 0) on each held track's channel, with AUDIO CC OUT on. `[FUNC]` + `[YES]` / `[NO]` stay stock; `[TRACK]` + `[YES]` / `[NO]` no longer arm/disarm recorder one-shots.

Built from [Zac-Kyoti/octatrack-kyoti-fw](https://github.com/Zac-Kyoti/octatrack-kyoti-fw)
(submodule `upstream/`, pinned to `9ea9a11`). `Kind.CF_PATCH`. One DRAM unit (`patch_rec_trig_mute.s`, built with `--defsym OCTABAM_UNIT`), four detours, four `SymbolRef`s.
`upstream/octabam-modules/rec-trig-mute/README.md` is the full description, with what was measured and what was inferred.

## Measured

- Every build re-links the unit and compares it with the author's own bytes (`reference`,
  built by `tools/build_rec_trig_mute.py` upstream with this repo's DRAM-unit oracle recipe);
  a difference refuses the build.
- `make check REMIX=rec-trig-mute` (`remixes/test/rec-trig-mute/`) builds and boots the
  image under the ColdFire port.

## On the unit

- 2 Oct 2026: the standalone image on the author's MKI (keys, toasts, the edge icons, a
  running recording finishing and nothing new starting).
- 3 Oct 2026: inside KYOTI V1.0, the same, beside the other KYOTI modules.
- MIDI CC 80 has not been tried on hardware, and this DRAM form has not been flashed.
