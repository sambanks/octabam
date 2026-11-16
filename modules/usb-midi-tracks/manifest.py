"""USB MIDI TRACKS -- each audio track's trigs as USB MIDI, USB only.

For every START on an audio track (T1..T8: sequencer trig, panel key or MIDI
IN note alike, they share one funnel) it queues on the USB MIDI module's
transmit queue, on the track's TRIG CHANNEL (OFF sends nothing, as stock):
CC 16..21 (PTCH STRT LEN RATE RTRG RTIM, stock's numbers), read from the
frame's parameter record so locks and the crossfader's morph are in them, and
a note-on whose number is the playing sample's slot, then a note-off a fixed
gate later. The BRAIN setting SEND chooses OFF (the default), NOTES or
NOTES+CC. Nothing is sent to the DIN port. The frame interrupt only queues;
the encoder is kicked from the engine task.

Retrigs: the renderer's own call of the start handler for each repeat is repointed too
(0x4000421e), so each repeat is a note-off and the same note again, and a scene or the
crossfader moving RTRG/RTIM is followed by construction. No detour: the kind table's FLEX and STATIC renderer entries point at it
(the packer calls them twice a frame per track, the second call after the
start handler has set the voice's sample record). SYNTH MACHINE repoints the
same entries, so the two never share an image. See README.md for what is measured and what is not.
"""
from remix.schema import (Apply, Category, Evidence, Gate, Kind, Level, Linked, Module, Option, Scope, Setting,
                          Store, SymbolRef)

H = bytes.fromhex
STORE_ID = "octabam.usb-midi-tracks"


def send_inc(modules, remix):
    """remix.inc: the get_send macro (0 OFF, 1 NOTES, 2 NOTES+CC)."""
    from remix import brain
    mods = modules if isinstance(modules, dict) else {}
    return ("| remix.inc -- USB MIDI TRACKS (modules/usb-midi-tracks/manifest.py)\n"
            + brain.read_macro(remix, mods, STORE_ID, "SEND", "get_send"))


MODULE = Module(
    name="usb-midi-tracks", key="USB MIDI TRACKS", kind=Kind.CF_PATCH,
    category=Category.MIDI_USB, author="siddely",
    author_url="https://github.com/siddely",
    evidence=(Evidence(Level.UNIT, unit="MKII", date="2026-11-15",
                       note="the PR's first build (channel = track, always on, the encoder kicked in the frame "
                            "interrupt), not this one: seen on the host over USB, CC 16..21 for every PLAYBACK page 1 "
                            "value, a note per trig, retrig repeats, and the CCs following scene/fader moves; nothing "
                            "timed or counted"),
              Evidence(Level.EMULATOR, date="2026-11-16", ref="verify_usbmidi_tracks",
                       note="CCs, note-on, note-off on the TRIG CHANNEL in that order and the gate length, under the "
                            "port; retrig repeats (scene-morphed RTRG included) on real projects with the probe")),
    doc="Audio-track trigs out over USB MIDI only, on each track's TRIG CHANNEL, when BRAIN's SEND is on: the trig page as CC 16-21 with the crossfader morph in them, note per sample slot, fixed gate.",
    requires=("USB",),
    linked=(
        Linked("utm", "modules/usb-midi-tracks/utm.s", cpu="54455", dram=True, include=send_inc),
    ),
    gates=(Gate("tools/verify/verify_usbmidi_tracks.py", stage="image"),),
    store=Store(STORE_ID),
    settings=(Setting(1, "SEND", Option("OFF", "NOTES", "NOTES+CC"), default="OFF", scope=Scope.CARD,
                      apply=Apply.LIVE,
                      doc="audio-track trigs out over USB MIDI on each track's TRIG CHANNEL: NOTES (a note per "
                          "sample slot) or NOTES+CC (CC 16..21 first, the same numbers stock's AUDIO CC OUT uses); "
                          "OFF sends nothing. A host that echoes MIDI back plays the OT from these notes"),),
    # The kind table's FLEX and STATIC renderer entries (4-byte data pointers, stock 0x40004008):
    # the packer calls the renderer twice a frame per track, the second call after the start handler.
    symbol_refs=(
        SymbolRef(0x400d6438, 0x40004008, "utm", "utm_render",
                  "kind table FLEX renderer -> utm_render: queue CC 16..21, note-on (USB only) on a start frame, the gated note-off, then the stock renderer"),
        SymbolRef(0x400d6434, 0x40004008, "utm", "utm_render",
                  "kind table STATIC renderer -> utm_render, the same"),
        # The stock renderer's retrig restart: jsr $4000f450 at 0x4000421c, the operand at 0x4000421e.
        SymbolRef(0x4000421e, 0x4000f450, "utm", "utm_retrig",
                  "renderer's start-handler call on a retrig -> utm_retrig: note-off, the CCs and the same note-on again (USB only), then the handler"),
    ),
)
