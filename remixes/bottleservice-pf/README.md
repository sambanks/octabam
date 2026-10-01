# `bottleservice-pf` -- bottleservice-ret plus POST FADER

[`bottleservice-ret`](../bottleservice-ret/README.md) plus
[POST FADER](../../modules/post-fader/manifest.py): every bus send (SEND's
DEL and REV, and the hosts' own) follows its track's fader, mute and solo,
the way an aux send does on a mixer. The knobs on the panel keep their
values; only what the DSP hears is scaled, by (LEVEL/128)^2 -- the mixer's
own law. A muted (or unsoloed) track sends nothing and does not count as a
sender, so the others keep their level.

A scene or the crossfader on a track's LEVEL moves its sends too.

## Where it has run

- **RIGPF3BP** (branch `rig-bootpick`: `rig-latest` + OS SWITCH's boot
  picker, `OSW_TRACE=1`, BUILD=11): flashed on an MKII, 30 Sep 2026, as the
  home image. Under the port: `make check` with a stress project
  (`tools/harness/stress_project.py` from a copy of the owner's MODLIIVE)
  584 PASS, the one failure verify_set's stray MIDI CC (0, 0), as on every
  rig build. On the unit, with the test set RIGTEST (T1-T7 STATIC loops with
  trigs, every DEL/REV at 0, T8 RETURNS, MASTER TRACK on): T1 and T5 play
  samples with trigs and no click, their level and mute act on their own
  sound only, and the returns work on T8 -- the THRU-only rule for T1/T5
  does not apply with RETURNS. The boot picker ran in every mode.
- **RIGPF4BP** (the same + OCTAKIT MIRROR, BUILD=12): flashed on the MKII,
  30 Sep 2026; page-key + CLEAR, which halted RIGPF3BP with VEC:04 in
  Octakit's page-clipboard check, works.
- ⚠️ USB disk mode on it once returned corrupted reads (about one in four,
  `docs/contributing/FAILURE_MODES.md`); later in the day it read clean. Cause
  open; suspected: the USB audio state (a DAW holding the unit as its audio
  device) when disk mode starts.
- **RIGPF5BP** (on current main, Character KEY included, + MODE DEFAULTS,
  BUILD=13): flashed on the MKII, 30 Sep 2026; boot, RETURNS, MODE turns
  re-defaulting their knobs (FX1 and FX2) and page CLEAR confirmed. Payload A
  1 word free: REVERB SERVER's return path lost 10 words, RETURNS 4, and 42
  branches in the two took the one-word form.
- **RIGPF6BP** (RETURNS listed on the FX2 chooser, BUILD=14): any FX2 switch
  halted with VEC:04 at 0x45D222B0, Octakit's `gk_machine_selection_fatal`:
  her chooser wrapper refuses an effect id above 28 and RETURNS was 0x1e.
- **RIGPF7BP** (RETURNS on 0x1b, a no-op on T1-T4, BUILD=15): flashed on the
  MKII, 30 Sep 2026; FX2 switching works. Projects that stored RETURNS as
  0x1e were rewritten to 0x1b on the card (they need RIGPF7BP or later).
  Open then: a switch on T1 or T5 removed that track's server, and the
  chooser had no row to put it back.
- **RIGPF8BP** (+ HOST LOCK, BUILD=16): flashed on the MKII, 30 Sep 2026;
  on T1 and T5 the FX2 chooser changes nothing, the servers stay.
