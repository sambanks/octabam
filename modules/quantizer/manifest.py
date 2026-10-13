"""SCALE QUANTIZER -- a SCALE row in PROJECT > CONTROL > SEQUENCER (OFF, then
24 scales) and, since 2.9, a ROOT row under it (C .. B): the PTCH knob,
parameter locks and CHROMATIC trig keys snap to the scale built on the root,
key 1 of the CHROMATIC keyboard sounds the root, and a sample track's
keyboard plays the one complete root-to-root octave; a GLIDE row (OFF,
1..127) is the slide time of the synth's and a sample track's legato (the
LEG box on AMP SETUP); polyphonic chromatic keys on a synth track whose VOIC
is 2..4; the three bytes survive a power cycle in battery RAM. Since 2.13
SCALE and ROOT act on the MIDI tracks too: the NOTE knob and NOTE locks
(GRID and LIVE RECORDING) step by scale degree from ROOT, and the MIDI
CHROMATIC keyboard plays the scale from ROOT (key 1 = the root; the readout
"A 3" where stock reads "3"); NOT2..4, TRAN, the arpeggiator's own notes and
MIDI IN stay stock, SCALE OFF is stock.

Source: `upstream/` is Tim Hastie's repository (timhastie/octatrick-modules,
submodule, pinned to v2.14 (39dc5d8) = Octatrick 2.14, 13 Oct 2026; the test
builds 2.3 .. 2.8 and the 2.9 line up to its previous build flashed on his
MKI, this module's 2.10 / 2.11 changes emulator-verified, 2.13's on his MKI
on 13 Oct 2026; its sources are
the same at v2.11 and v2.12, 2.13 changes them, and v2.14 leaves them
as at 2.13). The declaration is
`upstream/quantizer/manifest.py`: since 2.9 the quantizer itself is a DRAM
unit (`quantizer.s`, `Linked(dram=True)`, in the platform reserve with the
synth's engine), and the OS image keeps a 192-byte ROM core (`core.s`: the
boot clamps, the defaults, the root-rotated scale mask) and the two pinned
stubs (`keys.s` at KEYS_AT, `scale.s` at SCALE_AT, the trampolines the
synth's engine reads); detours, pokes and a TableGrow for the menu rows
(3 + 3 since ROOT). SCALE, GLIDE and ROOT are battery-RAM bytes
(0x100b14ec / ed / ee). The ROM footprint went from 3,319 B at 2.8 to 243 B.
Since 2.10 a track with FM SYNTH chosen in the machine list (the Part's
"FM", 1) is a synth track for the PTCH knob and the CHROMATIC keys as a
marker-file track is; since 2.11 a SY DRUM track ("SY", 1) is one too
(semitone PTCH, the keys, MIDI), mono (VOIC is FM's), its legato keys
reaching the engine -- assembled only when SY DRUM is
in the remix (`HAVE_SYDRUM` in the unit's remix.inc; 0 assembles 2.10's
unit).
2.13 adds three hooks for the MIDI tracks: 0x40055382 (the knob
handler's clamp to the max, one step before the store 0x4005538a, which
stays stock), 0x40050b98 (the MIDI p-lock editor's store) and 0x400436a8
(the MIDI CHROMATIC key press). The knob hook sits before the store because
octabam's MIDI SCENES detours the store itself (scn_pwrite at 0x4005538a):
the two compose, this module decides the value and MIDI SCENES' detour
stores it, and the ledger accepts the pair (a scene lock on NOTE is not
snapped). 2.13 also takes Modwerk's #264 form of the CHROMATIC drawer hook
(qz_octnum at the common push 0x400449be, 0x400449b8 until 2.12): stock's
MIDI branch jumps to 0x400449be, so with the old site entering CHROMATIC on
a MIDI track froze the unit (every tag 2.9 .. 2.12; the fix found by the
Modwerk contributors, repeat98/modwerk #264, MIT).
Its source paths are derived from its own directory, so it is executed here
from the source on disk, as the registry does for every manifest, and this
file only re-exports its MODULE. Nothing inside `upstream/` is edited here.

On hardware as OCTATRICK9 (remix octatrick-usb) on Tim's MKI, 26 Sep 2026,
and every test build 2.3 .. 2.8 since; the 2.9 line up to the build before its
last two fixes (ROOT, the DRAM quantizer, FINE 0c, the envelope engine, no
limiter) has run on the same MKI; the last two 2.9 fixes and the 2.10 /
2.11 machine-list reads are emulator-verified only. 2.13's MIDI tracks ran
on his MKI on 13 Oct 2026, reported working: Modwerk's FM Synth 0.1.5 (the
2.13 quantizer bundled; MAIN OS SHA-256 37661aee...: the NOTE knob and NOTE
locks through the scale, the CHROMATIC keys following ROOT, CHROMATIC on a
MIDI track no longer freezing, SCALE OFF as before) and OCTATRICK 2.14
(`octatrick` at v2.14, MAIN OS SHA-256 c367d8bc..., this tree's bus).
"""

import dataclasses
import pathlib
import runpy

from remix.schema import Category, Proof

_UPSTREAM = pathlib.Path(__file__).resolve().parent / "upstream" / "quantizer" / "manifest.py"

MODULE = runpy.run_path(str(_UPSTREAM), run_name="remix_manifest_quantizer")["MODULE"]
# The module table's fields are octabam's (README.md, `make docs`), so they
# are added here rather than in his manifest.
MODULE = dataclasses.replace(
    MODULE, category=Category.MACHINES, author="timhastie/octatrick-modules", author_url="https://github.com/timhastie/octatrick-modules",
    proof=Proof.HARDWARE, proof_note="`octatrick-usb` on his MKI, 26 Sep 2026 (OCTATRICK9) through 2.9; the machine-list reads of 2.10 / 2.11 under the port; the MIDI tracks of 2.13 on his MKI, 13 Oct 2026, in Modwerk's FM Synth 0.1.5 (MAIN OS SHA-256 37661aee...) and OCTATRICK 2.14 (`octatrick` at v2.14, c367d8bc..., this tree's bus): reported working")
