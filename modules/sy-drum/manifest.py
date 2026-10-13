"""SY DRUM -- a drum machine in the track's machine list, the row after FM
SYNTH: one voice a track, two oscillators, a sweep, a two-pole filter opened
by the decay, six modes, PTCH MODE WDTH SWEP SPED DEC on its PLAYBACK page
(stock p-locks, LFOs and scenes reach them), and a dedicated LFO / S&H on its
PLAYBACK SETUP page (LSPD LDEP WAVE S&H), lockable per step in GRID and LIVE
RECORDING (the locks follow copy / paste / clear / shift and are saved in
sylockNN files beside the project's banks, only for banks that hold one).
Modelled on the 1979 Pearl Syncussion SY-1; not affiliated with or endorsed
by Pearl or Behringer; Syncussion is a trademark of its owner. It runs on
SYNTH MACHINE's engine and requires it in the remix.

Source: `upstream/` is Tim Hastie's repository (timhastie/octatrick-modules,
submodule, pinned to v2.14 (39dc5d8) = Octatrick 2.14, 13 Oct 2026). The
declaration is `upstream/sy-drum/manifest.py`: one DRAM unit (`sydrum.s`,
`Linked(dram=True)`, its `remix.inc` generated per remix with SYNTH
MACHINE's shared equates), a 2 MiB DramRegion (the step-lock table) and 53
detours (the page resolver, the setup editor and the step locks' hooks); it
declares the conflicts with KITS, PLOCKS P2 and STEM REC. Its source paths
are derived from its own directory, so it is executed here from the source
on disk, as the registry does for every manifest, and this file only
re-exports its MODULE. Nothing inside `upstream/` is edited here.

Verified on the ColdFire port, 8 - 9 Oct 2026 (renders sample-identical to
the author's development build, the machine-list walks, the step-lock
walks, save / reload). The 2.11 module ran on his MKI on 10 Oct 2026 in a
Modwerk test image with FM SYNTH (MAIN OS SHA-256 b9b65cd9...), not in an
octabam build: no issues but the machine-change init, which 2.12 adds in
SYNTH MACHINE (sydrum.s is the same at v2.11, v2.12 and v2.13); 2.12's init:
on his MKI on 13 Oct 2026 (below). 2.14 (13 Oct 2026) changes only this module's card code: the step
locks' WORK files are also written while the sequencer plays (one detour
more, 0x4005224a, the UI tick's transport test), so a power-off without
SAVE keeps the PLAYBACK SETUP locks -- found by the author on his MKI in a
Modwerk test image (MAIN OS SHA-256 d0dab5fe...), the fix confirmed there
in an `octatrick` build with it (MAIN OS SHA-256 05f0e015...: locks kept,
no crackling on a STATIC track); and the lock files are read whenever a
project loads, also beside a missing or damaged stock bank file (emulator
only). 2.14 on his MKI, 13 Oct 2026, reported working: Modwerk's SY DRUM
0.1.0 with FM Synth 0.1.5 (MAIN OS SHA-256 27c213b2...) and OCTATRICK 2.14
(`octatrick` at v2.14, MAIN OS SHA-256 c367d8bc..., this tree's bus): the
locks kept over a power-off without SAVE while playing, no crackle on a
STATIC track, the machine-change init with the locks kept.
"""

import dataclasses
import pathlib
import runpy

from remix.schema import Category, Proof

_UPSTREAM = pathlib.Path(__file__).resolve().parent / "upstream" / "sy-drum" / "manifest.py"

MODULE = runpy.run_path(str(_UPSTREAM), run_name="remix_manifest_sy_drum")["MODULE"]
# The module table's fields are octabam's (README.md, `make docs`), so they
# are added here rather than in his manifest.
MODULE = dataclasses.replace(
    MODULE, category=Category.MACHINES, author="timhastie/octatrick-modules", author_url="https://github.com/timhastie/octatrick-modules",
    proof=Proof.HARDWARE, proof_note="his MKI, 10 Oct 2026, the 2.11 module in a Modwerk test image with FM SYNTH (MAIN OS SHA-256 b9b65cd9...), not an octabam build: no issues but the machine-change init, which 2.12 adds; 2.14 with 2.12's init: his MKI, 13 Oct 2026, in Modwerk's SY DRUM 0.1.0 with FM Synth 0.1.5 (MAIN OS SHA-256 27c213b2...) and OCTATRICK 2.14 (`octatrick` at v2.14, c367d8bc..., this tree's bus): the init with the locks kept, the locks kept over a power-off without SAVE while playing, no crackle on a STATIC track (the WORK write first confirmed 12 Oct 2026 in an `octatrick` build, 05f0e015...); its bank-file guard: emulator only")
