"""CHORDS FACTORY -- a bank of chord progressions, voiced by voice leading.

Sixteen chord slots per bank, one per trig key, played in order as a
progression. A chord is built (root, type, inversion, spread, octave), typed
on the trig keys (FUNC held: a chromatic keyboard), or -- after a slot that
holds one -- voiced from it: the module offers the voicings that move the
voices least (common notes kept, no crossing), best first, and any voice can
then be moved by hand. At most four voices: one MIDI trig's NOTE and NOT2-4.
The atelier is a page of its own (PAGES: SRC again on MIDI NOTE, after
any other client's); a held trig key sounds its slot on the track's MIDI channel. The
slots are saved with the project in chords.work (a STORE client).

CHORDS is also a trig mode of the MIDI tracks (FUNC + DOWN: TRACKS,
CHROMATIC, CHORDS, QUICK MUTE; mode 2, SLOTS on the audio tracks): the trig
keys play the bank's slots, green when they hold a chord, yellow while held,
through stock's CHROMATIC note -- the arpeggiator and the KEY take the
chord's notes as keys held. A chord goes on a trig by live recording (one
trig, NOTE and NOT2-4) or, in GRID RECORDING, with trigs held and UP: a
chooser of MAIN MENU's size lists the bank's chords (UP / DOWN, heard; YES
places it). Beside SCALES a chord step plays as built (SCALES' HAVE_CHORDS),
and with FUNC held on the page the trig keys light as the keyboard they type
on (SCALES' sc_keyboard, the chord green; C major without SCALES). The engine
is C (chords.c, host-tested by verify.py);
generate.py builds chords_unit.s from it, adapter.c and hooks.s.
"""

import runpy
from pathlib import Path

from remix.schema import Category, Detour, Gate, Kind, Linked, Module, Proof

H = bytes.fromhex
MIDI_MODES = 0x400A74C0                 # stock's MIDI trig modes: 0, 1, 4 (TRACKS, CHROMATIC, QUICK MUTE)


def _inc(modules, _remix):
    """remix.inc: whether SCALES answers ch_scale, and the module's number in
    STORE's refusal registry."""
    ids = runpy.run_path(str(Path(__file__).parents[1] / "store/manifest.py"))["CLIENT_IDS"]
    return f".set HAVE_MIDI_SCALES, {int('MIDI SCALES' in modules)}\n.set HAVE_HARMONY, {int('MIDI HARMONY' in modules)}\n.set HAVE_SCALES, {int('SCALES' in modules)}\n.set CH_CLIENT, {ids['CHORDS FACTORY']}\n"


MODULE = Module(
    name="chords",
    key="CHORDS FACTORY",
    kind=Kind.CF_PATCH,
    category=Category.MIDI_USB,
    author="djib",
    author_url="https://github.com/Djibdjib",
    proof=Proof.HARDWARE,
    proof_note="the owner's MKII, OCTABAM36-43 (3-5 Nov 2026, the live-djib rig, with SCALES): the page, "
               "the slots, voice leading, the trig mode, live recording, TRIG + UP, the FUNC keyboard; "
               "verify_chords (the port), verify.py (the engine). Shared TRIG MODES and Harmony/provider "
               "integration: emulator checks only; those changes have not been flashed",
    doc="Chord progressions for a MIDI track: sixteen slots per bank on the trig keys, each chord "
        "built (root, type, inversion, spread, octave), typed on the trig keys (FUNC) or voiced from "
        "the slot before by voice leading (the smoothest first, then the next ones); a voice moved by "
        "hand (FUNC + A-D); the bass free or the root; the scale's chords from SCALES (FUNC + F). "
        "Heard on the track's channel while a trig key is held. Saved in chords.work (a STORE client). "
        "The page: SRC again on MIDI NOTE (a PAGES client). CHORDS is also a MIDI trig mode (FUNC + DOWN): "
        "the trig keys play the slots, green, through stock's CHROMATIC note (the arpeggiator follows); "
        "live recording or TRIG + UP (a chooser window) puts a chord on a trig.",
    linked=(Linked("ch", "modules/chords/chords_unit.s", cpu="5475", dram=True, include=_inc),),
    detours=(
        Detour(0x40035F92, H("2039460d16f8"), "ch", "ch_box_head",
               "the trig mode box's header for mode 2: the slots holding a chord, n/16, in MIDI mode"),
        Detour(0x40044B74, H("4878000a4878003d"), "ch", "ch_box_pic",
               "the trig mode box's picture for mode 2: the chord last played and the sixteen slots, in MIDI mode",
               pad_to=8),
        Detour(0x40045502, H("4878000148780009"), "ch", "ch_box_bar",
               "the trig mode box's sample bar for modes 2 / 3: none in MIDI mode (CHORDS plays no sample)",
               pad_to=8),
    ),
    requires=("STORE", "PAGES", "TRIG MODES"),
    gates=(Gate("modules/chords/verify.py", remix_arg=False),
           Gate("tools/verify/verify_chords.py", venv=True, stage="image")),
)
