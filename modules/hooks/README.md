# HOOKS

Platform module: the one owner of a stock site that two selected modules both
claim. Nobody selects it; the registry appends it to a remix whenever one of
its bridges has two participants in it, as it appends MEMORY. A remix with one
participant, or none, gets nothing from HOOKS: that module's own claim stands
and its bytes do not move, so a module proven alone on a unit stays exactly what
was proven. A submodule participant's source is not edited; an in-tree
participant builds a bridged form under a flag and is byte-identical alone.

How it relates to STORE, EVENTS and `Override`, and the conflicts still open:
[docs/specs/SHARED_SITES.md](../../docs/specs/SHARED_SITES.md).

Spec: [docs/specs/HOOKS.md](../../docs/specs/HOOKS.md) — every bridge with its site, participants and what HOOKS does, and how to add one.

## Measured

- `tools/verify/verify_hooks.py`: the selection rules; under Unicorn, the
  participants' own sources linked with `bridge.s`, `hk_status_icon` (REC
  THRESHOLD, then FREE LOOP) over 192 states (track, state, FREE LOOP's
  armed / overdub, arm, TRIG, blink phase) against the model and against the
  two routines called in turn, the opposite order losing FREE LOOP's mark
  (REC_TRIG_MUTE's fold was the first participant until its pin moved past
  `553d8d2`, 6 Nov 2026); the [TRACK]-layer table decoded; the frame interrupt's
  entry and epilogue chains (one prologue, one epilogue, each participant's
  work done, registers and stack as found) and the boot chain (the stock
  call made once, STORE's targets set). With a built image of
  [`test/hooks`](../../remixes/test/hooks/README.md) or
  [`test/hooks-core`](../../remixes/test/hooks-core/README.md): stock's six
  records are the ones HOOKS copies, every bridged site holds HOOKS's write,
  and each chain calls its participants at their linked addresses.
- Each participant alone, and `octabam`, `stock-meter-a`, `cfmeter`,
  `remix-switch-trace`, `morph`, `rec-threshold`, `octa303`, `blackpyramids-303`:
  image byte-identical to the branch's base (28 Oct 2026).
- CHROMATIC: under Unicorn, 40 key → pitch cases (a 303 track as OCTA303 alone,
  every other track, scale off and on, as `qz_chrom`) and 48 octave/index/picture
  cases (a BLACKPYRAMIDS track as its own handlers, every other as sanitize then
  SCALE QUANTIZER's); in [`test/hooks-chrom-303`](../../remixes/test/hooks-chrom-303/README.md)
  and [`test/hooks-chrom-bp`](../../remixes/test/hooks-chrom-bp/README.md). One
  difference from BLACKPYRAMIDS alone, by design: FUNC + LEFT/RIGHT on another track
  with an octave of 2 or 3 left by a BLACKPYRAMIDS track lands on 1, not 0.
  BLACKPYRAMIDS's manifest's conflict with SCALE QUANTIZER named `0x4000e746`, which
  SCALE QUANTIZER no longer claims; its wrapper drops that one conflict.
- The UI tick (`ui_tick`): under Unicorn, FREE LOOP's `fl_ui_stub` built with `HK_UI_TICK` and
  RELOAD_FROM_PROJECT's unit linked together: a tick FREE LOOP lets through reaches `rl_uitick`, which
  reads the toast countdown and goes on at `0x40056c2e`; a tick on which FREE LOOP shows a toast
  returns to the task loop, as alone (4 cases); in [`test/hooks-reload`](../../remixes/test/hooks-reload/README.md).
- The boot bridge: under Unicorn, and in [`test/hooks-boot`](../../remixes/test/hooks-boot/README.md)
  (BOOT TRACE beside STORE and MIDI LOOPBACK).
- Machine rows: under Unicorn, each track's row type (static, FLEX, ANALOG BD,
  OCTA-303), the drawer's two stubs over both top rows and every screen row
  (60 cases), ANALOG BD's name and main-commit hooks reaching OCTA303's (row 6
  signs `TB 1`, row 5 `AB 1`, any other row neither, in the Part and its shadow).
  Under the ColdFire port, in [`test/hooks-machines`](../../remixes/test/hooks-machines/README.md)
  with a fresh project: both machines' own UI gates pass on the one image
  (`verify_analog_bassdrum_ui`, `verify_octa303_ui`: OCTA-303's record as UI type 6);
  the list scrolls to OCTA-303 and back, YES on either row commits that machine,
  and reopening on an OCTA-303 track opens scrolled with its row boxed. ANALOG BD
  and OCTA303 alone are byte-identical to the base (28 Oct 2026).
- Machine rows, a chain of three (31 Oct 2026): under Unicorn (`verify_hooks`),
  for ANALOG BD + OCTA303, OCTA303 + CX OSC, ANALOG BD + CX OSC and all three,
  the head's row type for every machine (signatures `AB 1`, `TB 1`, `CX 1`),
  the drawer's stubs over every top row and screen row (108 cases with eight
  rows), each row's name through the chain and in the head's SRC SETUP table,
  and the head's main commit signing each machine's row in the Part and its
  shadow from every starting machine (CX OSC's machine change runs over the
  user's stock image). Under the port with a fresh project, on
  [`test/hooks-machines-cx`](../../remixes/test/hooks-machines-cx/README.md) and
  [`test/hooks-machines-all`](../../remixes/test/hooks-machines-all/README.md):
  `verify_octa303_ui` (its row from the remix, `hooks_flags.image_row`),
  `verify_analog_bassdrum_ui` on the three-machine image, and `verify_cxosc`
  (Unicorn, on each image's runtime, its guard on its own row) pass; choosing CX OSC
  from the panel (the list's last row, YES) stores FLEX signed `CX 1` in the Part
  and its shadow and publishes its page in its row's PB_TABLE slot -- by a scratch
  script run on both images, not a gate. A first run with OCTA303 heading the
  render chain never loaded the project: CX OSC's page code reads its records
  from the words before the FLEX kind entry's renderer, so CX OSC heads that chain.
  ANALOG BD, OCTA303 and CX OSC alone are byte-identical to the base.
- Not flashed. Apart from the machine rows, not run under the ColdFire port with a project.
