"""TUNER -- a guitar-tuner readout of the current audio track: hold UP and
press TEMPO for a window with the note, octave, a +-50 cent needle and the
frequency, from the track's post-FX pre-fader audio, detected on the
ColdFire (McLeod NSDF + YIN refine, integer only) in the UI task. TEMPO,
YES, NO or the chord close it; TEMPO alone, FUNC + TEMPO and UP alone stay
stock.

Source: `upstream/` is Tim Hastie's repository (timhastie/octatrick-modules,
submodule, pinned to v2.14 (39dc5d8) = Octatrick 2.14, 13 Oct 2026). The
declaration is
`upstream/tuner/manifest.py`: one DRAM unit (`tuner.s`, `Linked(dram=True)`,
in the platform reserve with the other DRAM modules) and three detours (the
TEMPO opener's first instruction, frame_isr's tail, the UI task's loop
head); no ROM cave, no pokes. Its source paths are derived from its own
directory, so it is executed here from the source on disk, as the registry
does for every manifest, and this file only re-exports its MODULE. Nothing
inside `upstream/` is edited here. The sources are unchanged since v2.8
(v2.14 included).

Emulator-verified (26 Sep 2026 in Tim's tree; here in remix octatrick,
29 Sep 2026). On hardware: UP + TEMPO opens the window and tunes on Tim's
MKI (test build 3.0 b40 = `octatrick` at BUILD 40, 29 Sep 2026), and in
Modwerk's TUNER 0.1.0 image (tuner.s as at v2.14; MAIN OS SHA-256
66489376...) on 13 Oct 2026, its test sheet reported working.
"""

import dataclasses
import pathlib
import runpy

from remix.schema import Category, Proof

_UPSTREAM = pathlib.Path(__file__).resolve().parent / "upstream" / "tuner" / "manifest.py"

MODULE = runpy.run_path(str(_UPSTREAM), run_name="remix_manifest_tuner")["MODULE"]
# The module table's fields are octabam's (README.md, `make docs`), so they
# are added here rather than in his manifest.
MODULE = dataclasses.replace(
    MODULE, category=Category.MACHINES, author="timhastie/octatrick-modules", author_url="https://github.com/timhastie/octatrick-modules",
    proof=Proof.HARDWARE, proof_note="Tim's MKI, test build 3.0 b40 (`octatrick` at BUILD 40), 29 Sep 2026: UP + TEMPO opens the window and tunes; sources unchanged since 26 Sep; Modwerk's TUNER 0.1.0 (tuner.s as at v2.14, MAIN OS SHA-256 66489376...), his MKI, 13 Oct 2026: its test sheet reported working")
