# `rec-trig-mute` -- REC_TRIG_MUTE

Mute a track's recorder trigs without deleting them. Hold `[TRACK]` and press `[REC]`: that track's recorder trigs stop firing -- a recording already running finishes -- and a toast reads `REC TRIGS MUTED`. Press it again to bring them back (`REC TRIGS UNMUTED`). Each track keeps its own state: with several track keys held, each one flips (`REC TRIGS TOGGLED` when they end up mixed). The toast stays up while the track key is held, up to 1 s, and closes when it is let go. While a track key is held, `[REC]` does not switch grid recording; on its own `[REC]` is stock. Any screen; it holds across pattern changes until you unmute, and every track starts unmuted at power-on. A muted track shows two dots beside its play/stop icon at the screen edge (`..■` / `..▶`). MIDI CC 80: 0 unmutes, 1-127 mutes, on a track's channel (AUTO channel = the active track), with AUDIO CC IN on; the keys send CC 80 (1 muted / 0 unmuted) on each held track's channel, with AUDIO CC OUT on. `[TRACK]` + `[YES]` / `[NO]` and `[FUNC]` + `[YES]` / `[NO]` stay stock.

Built from [Zac-Kyoti/octatrack-kyoti-fw](https://github.com/Zac-Kyoti/octatrack-kyoti-fw)
(submodule `upstream/`, pinned to `553d8d2`). `Kind.CF_PATCH`. One DRAM unit (`patch_rec_trig_mute.s`, built with `--defsym OCTABAM_UNIT`), five detours, four `SymbolRef`s (the T1 / T2 keymaps' `[REC]` records; `rtm_rec` hands every event but a track-held press back to stock's `0x40048774`, so STEM REC's detour there still runs).
`upstream/octabam-modules/rec-trig-mute/README.md` is the full description, with what was measured and what was inferred.

## Measured

- Every build re-links the unit and compares it with the author's own bytes (`reference`,
  built by `tools/build_rec_trig_mute.py` upstream with this repo's DRAM-unit oracle recipe);
  a difference refuses the build.
- `make check REMIX=rec-trig-mute` (`remixes/test/rec-trig-mute/`) builds and boots the
  image under the ColdFire port.

## On the unit

- 2-3 Oct 2026: the earlier gesture (`[TRACK]` + `[NO]` / `[YES]`) on the author's MKI, as the
  standalone image and inside KYOTI V1.0 (keys, toasts, the edge icons, a running recording
  finishing and nothing new starting).
- 29 Oct 2026: the `[TRACK]` + `[REC]` form (the per-track toggle, the 1 s toast that closes
  on release) inside KYOTI V1.6, flashed twice ("all good").
- MIDI CC 80 has not been tried on hardware, and this DRAM form has not been flashed.
