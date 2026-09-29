# `bottleservice-ret` -- bottleservice-rec-plen plus RETURNS

[`bottleservice-rec-plen`](../bottleservice-rec-plen/README.md) plus
[RETURNS](../../modules/returns/manifest.py), stage A of
[docs/proposals/RETURNS.md](../../docs/proposals/RETURNS.md): the reverb's
return leaves T5 and gets its own level, VRB, on T8's FX2 page (page 1, so
scene locks, the crossfader, LFOs and CC reach it).

- MASTER TRACK on: the return goes into T8's input with the other tracks,
  so T8's FX1 (a master filter) and its fader process it.
  `tools/hw/ot_project.py master-track <project> on` sets it on a copy.
- MASTER TRACK off: the return goes into MAIN.
- T5 is an ordinary track: its LEVEL, mute and cue act on its own sound.
- The delay still prints on T1 (stage B).
- A project needs `ot_project.py host <project> bottleservice-ret` (T8's
  FX2 becomes RETURNS); without RETURNS on T8 the reverb prints on T5 as in
  bottleservice.

- **MODE DEFAULTS is not in it**: a MODE turn does not re-default the
  knobs around it. The ROM its unit held is RETURNS' page; it comes back
  once the ROM is freed.

## Where it has run

Not flashed.
