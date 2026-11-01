"""SCALES -- one catalogue of scales for every module, a chooser, and the
CHROMATIC trig keys lit with the scale.

The catalogue: 52 scales in 9 families (MAJOR and its seven modes,
MELODIC MINOR, HARMONIC MINOR, HARMONIC MAJOR, DOUBLE HARMONIC, PENTATONIC,
BLUES, JAPANESE, SYMMETRIC), each a 12-bit mask over the semitones above
its tonic (IONIAN = 1010 1101 0101), named by an ID that never changes.
Other modules ask it (sc_mask, sc_name, sc_snap, ...) and open its chooser
(sc_pick) rather than carry their own tables: README "Service".

A MIDI track's ARP SETUP KEY: turned, the tonic; pressed, the chooser
(a window of MAIN MENU's size: the families, then the family's scales).
The sequencer's and the arpeggiator's notes snap to the scale. The KEY
keeps stock's and MIDI SCALES' values for their scales; the others keep
their ID in scales.work (a STORE client), no native byte.

The CHROMATIC keys light the scale (the tonic yellow, the scale red, the
rest dark): a MIDI track's, and an audio track's SCALE QUANTIZER SCALE on
its ROOT when the remix has it. KEY OFF, SCALE OFF: stock's C major.
"""

import runpy
from pathlib import Path

from remix.schema import Category, Detour, Gate, Kind, Linked, Module, Poke, Proof, SymbolRef


def _sources(modules, _remix):
    """remix.inc: which modules answer kl_source on the audio side (README "Sources"),
    and SCALES' number in STORE's refusal registry."""
    ids = runpy.run_path(str(Path(__file__).parents[1] / "store/manifest.py"))["CLIENT_IDS"]
    return (f".set HAVE_SCALE_QUANTIZER, {int('SCALE QUANTIZER' in modules)}\n"
            f".set SC_CLIENT, {ids['SCALES']}\n")


MODULE = Module(
    name="scales",
    key="SCALES",
    kind=Kind.CF_PATCH,
    category=Category.MIDI_USB,
    author="djib",
    author_url="https://github.com/Djibdjib",
    proof=Proof.HARDWARE,
    proof_note="djib's MKII, OCTABAM26 (live-djib, BUILD 26), 31 Oct 2026: the chooser, the "
               "snapped notes and LEDs, scales.work across SAVE PROJECT and a power cycle; "
               "verify_scales on MKI and MKII",
    doc="One catalogue of 52 scales in 9 families for every module; ARP SETUP's KEY turns the "
        "tonic and, pressed, opens the scale chooser (the families, then their scales); the "
        "sequencer and the arpeggiator play the scale; the CHROMATIC trig keys light it "
        "(SCALE QUANTIZER's on audio tracks).",
    linked=(Linked("sc", "modules/scales/scales.s", dram=True, include=_sources),),
    pokes=(Poke(0x400D4096, bytes.fromhex("00000019"), bytes.fromhex("00000055"),
                "ARP SETUP KEY: 85 values, stock's 25 and MIDI SCALES' modes"),),
    symbol_refs=(SymbolRef(0x400D40C6, 0x4003B790, "sc", "sc_format",
                           "ARP SETUP KEY formatter: the tonic and the scale's short name"),),
    detours=(
        Detour(0x400442E2, bytes.fromhex("42854284428647f9400135b0"), "sc", "kl_chromatic",
               "trig-LED pass, CHROMATIC branch: the track's scale instead of C major",
               pad_to=12),
        Detour(0x40056AB8, bytes.fromhex("4ab9460d1e4c"), "sc", "kl_tick",
               "UI task's per-tick routine: encoder F pressed in ARP SETUP opens the chooser; "
               "a KEY / SCALE / ROOT turned while in CHROMATIC asks for the trig LEDs"),
        Detour(0x4007A3E2, bytes.fromhex("7205b280660000e4"), "sc", "sc_encoder",
               "ARP SETUP's encoder F: the tonic, the scale kept", pad_to=8),
        Detour(0x4009FB58, bytes.fromhex("4aaeffc06f22"), "sc", "sc_output",
               "stock's output quantization: the notes snap to a scale stock does not play"),
    ),
    conflicts=(("MIDI SCALES", "both own ARP SETUP's KEY; SCALES reads MIDI SCALES' KEY values "
                               "and plays its modes"),),
    requires=("STORE",),
    gates=(Gate("tools/verify/verify_scales.py", venv=True),),
)
