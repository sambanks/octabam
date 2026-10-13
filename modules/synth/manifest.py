"""SYNTH MACHINE -- a two-operator FM synth machine: FM SYNTH in the track's
machine list (the row after PICKUP in SRC SETUP and SELECT MACHINE TYPE,
since 2.10), or a FLEX track whose sample is named FMSYNTH*.wav (or
SYNTH*.wav), plays an FM voice instead of a sample, with its own PLAYBACK
page (PTCH RATO INDX FINE FDBK DEC) and, on the LFO page, VOIC (1 = mono,
2..4 = paraphonic) and CHRD (32 chord shapes with three inversions each,
lockable per step, snapped onto SCALE QUANTIZER's scale and root); MIDI IN
plays it like the keys, fingered chords are recorded as PTCH / CHRD / VOIC
locks, LEG (AMP SETUP) is a legato switch on every audio track, and a held
trig + FUNC + UP / DOWN transposes its lock. Since 2.9 the engine owns the
AMP envelope (ATK / HOLD / REL from the AMP page, the DSP's laws), no voice
is ever cut, the peak limiter is gone, FINE reads 0c the moment a track
becomes a synth track, a sequencer trig on a sounding note is delivered in
the panel key's form, and a warm START ramps the index envelope. Since 2.10:
the machine-list row (adapted from Modwerk's FM Synth module, MIT), DEC 127 =
HOLD, no note-start click (attacks of at least one carrier period), the LFO
destination list names the FM parameters, a held CHROMATIC key is the gate,
and 6 dB of headroom (VOL 0 the reference). Since 2.11: the rows after PICKUP
are a table filled per remix (FM SYNTH, then SY DRUM when the remix has it),
SELECT MACHINE TYPE scrolls, and the engine is byte for byte 2.10's; the
conflict with ANALOG BD (the same chooser sites) is declared. Since 2.12:
the metronome no longer releases a held note (2.9's po_stop hook on the
click word is gone), and a machine change to or from FM SYNTH / SY DRUM
resets the track's machine parameters (PLAYBACK, PLAYBACK SETUP, AMP, LFO
and their SETUP pages) to the new machine's init; step and scene locks and
FX slots are kept.

Source: `upstream/` is Tim Hastie's repository (timhastie/octatrick-modules,
submodule, pinned to v2.14 (39dc5d8) = Octatrick 2.14, 13 Oct 2026; the test
builds 2.3 .. 2.8 and the 2.9 line up to its previous build flashed on his
MKI; the 2.10 engine (8 Oct 2026) and the 2.11 engine (10 Oct 2026) ran on
his MKI in Modwerk test images; 2.12 on his MKI on 13 Oct 2026). The
declaration is
`upstream/synth/manifest.py`: the voice engine as a DRAM unit (`poly.s`,
`Linked(dram=True)`, in the platform reserve with the other DRAM modules),
the machine list as a second DRAM unit (`machine.s`, since 2.10; its row
table generated per remix), the page as a pinned ROM cave (`page.s` at
0x400d24d0, the start of the second free gap; its FM SYNTH descriptor a
runtime clone of the stock record), a SymbolRef on the kind table's FLEX and STATIC renderer entries,
detours and pokes. Its source paths are derived from its own directory, so
it is executed here from the source on disk, as the registry does for every
manifest, and this file only re-exports its MODULE. Nothing inside
`upstream/` is edited here.

2.9's engine (poly.s): sy_render presents the DSP with an always-open AMP
envelope on a synth track and applies ATK / HOLD / REL from the live lane
itself with the DSP's laws as measured (ATK linear, HOLD a timer from the
START, REL exponential floored at 1 ms; 127 = INF); a voice that still
sounds continues its oscillator from its current level, a faded one starts
from silence over 16 frames; voice stealing and hand-overs fade (8 frames,
2.9 ms); a VOIC change hands the sounding tone over; STOP ends the engine's
voices at the stock voice kill. The per-frame peak limiter is removed (the
sum is clamped; the 1/sqrt(VOIC) level law stays, a 4-note chord about
-10 dBFS). po_retrig rewrites a sequencer START on a sounding synth track
to the panel key's form so the DSP keeps its voice (the +5.6 dB bump at
every trig on a still-audible note gone: x24.8 -> x1.01 the tone's slope);
a warm START ramps the FM index envelope over 16 frames (x7.5 -> x1.07).
Cost against 2.8 (static count): +6 instructions a sample a voice in the
FM loops with the limiter's per-sample stage gone, about +15-20 % of a
VOIC 1 synth track's frame work, ~0.1-0.2 % of the frame budget; the
platform reserve and FREE MEM unchanged. Known limit: a MACHINE change
while a REL INF note sounds leaves it sounding until the next key.

On hardware as OCTATRICK9 (remix octatrick-usb) on Tim's MKI, 26 Sep 2026,
and every test build 2.3 .. 2.8 since; the 2.9 line up to the build before its
last two fixes (ROOT, the DRAM quantizer, FINE 0c, the envelope engine, no
limiter) has run on the same MKI. The 2.10 engine ran on his MKI on 8 Oct
2026 in a Modwerk test image (MAIN OS SHA-256 161d781d...), and the 2.11
engine on 10 Oct 2026 as Modwerk's FM Synth 0.1.4 (MAIN OS SHA-256
248d987e...), not in an octabam build: the held note it cut at each
metronome click is 2.12's fix. 2.12 on his MKI on 13 Oct 2026, reported
working: OCTATRICK 2.14 (`octatrick` at v2.14, MAIN OS SHA-256 c367d8bc...,
byte for byte this tree's bus), Modwerk's FM Synth 0.1.5 (37661aee...) and
SY DRUM 0.1.0 with it (27c213b2...). The engine is the same at
v2.12, v2.13 and v2.14 (2.13 and 2.14 change no file under synth/).
"""

import dataclasses
import pathlib
import runpy

from remix.schema import Category, Proof

_UPSTREAM = pathlib.Path(__file__).resolve().parent / "upstream" / "synth" / "manifest.py"

MODULE = runpy.run_path(str(_UPSTREAM), run_name="remix_manifest_synth")["MODULE"]
# The module table's fields are octabam's (README.md, `make docs`), so they
# are added here rather than in his manifest.
MODULE = dataclasses.replace(
    MODULE, category=Category.MACHINES, author="timhastie/octatrick-modules", author_url="https://github.com/timhastie/octatrick-modules",
    proof=Proof.HARDWARE, proof_note="`octatrick-usb` on his MKI, 26 Sep 2026 (OCTATRICK9) through 2.9; the 2.10 engine (8 Oct 2026, MAIN OS SHA-256 161d781d...) and the 2.11 engine (10 Oct 2026, Modwerk's FM Synth 0.1.4, MAIN OS SHA-256 248d987e...) ran on his MKI in Modwerk test images, not in an octabam build; 2.12 (the metronome fix found there, the machine-change init): his MKI, 13 Oct 2026, in OCTATRICK 2.14 (`octatrick` at v2.14, MAIN OS SHA-256 c367d8bc..., this tree's bus) and in Modwerk test images (FM Synth 0.1.5, 37661aee...; SY DRUM 0.1.0 with it, 27c213b2...): reported working")
