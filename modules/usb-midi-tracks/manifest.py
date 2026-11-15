"""USB MIDI TRACKS -- each audio track's trigs as USB MIDI, USB only.

For every START on an audio track (T1..T8: sequencer trig, panel key or MIDI
IN note alike, they share one funnel) it queues on the USB MIDI module's
transmit accumulator: CC 16..21 (PTCH STRT LEN RATE RTRG RTIM, stock's numbers),
read from the frame's parameter record so locks and the crossfader's morph are in them, and a
note-on whose number is the playing sample's slot, then a note-off a fixed
gate later. Channel n carries track n. Nothing is sent to the DIN port.

Retrigs: the renderer's own call of the start handler for each repeat is repointed too
(0x4000421e), so each repeat is a note-off and the same note again, and a scene or the
crossfader moving RTRG/RTIM is followed by construction. No detour: the kind table's FLEX and STATIC renderer entries point at it
(the packer calls them twice a frame per track, the second call after the
start handler has set the voice's sample record). SYNTH MACHINE repoints the
same entries, so the two never share an image. See README.md for what is measured and what is not.
"""
from remix.schema import Category, Evidence, Gate, Kind, Level, Linked, Module, SymbolRef

H = bytes.fromhex

MODULE = Module(
    name="usb-midi-tracks", key="USB MIDI TRACKS", kind=Kind.CF_PATCH,
    category=Category.MIDI_USB, author="siddely",
    author_url="https://github.com/siddely",
    evidence=(Evidence(Level.UNIT, unit="MKII", date="2026-11-15",
                       note="seen on the host over USB: CC 16..21 for every PLAYBACK page 1 value, a note per trig, "
                            "retrig repeats, and the CCs following scene/fader moves; nothing timed or counted"),
              Evidence(Level.EMULATOR, date="2026-11-15", ref="verify_usbmidi_tracks",
                       note="notes, CCs, gate and retrig repeats (scene-morphed RTRG included) measured under the port on real projects")),
    doc="Audio-track trigs out over USB MIDI only: the trig page as CC 16-21 with the crossfader morph in them, note per sample slot, fixed gate.",
    requires=("USB",),
    linked=(
        Linked("utm", "modules/usb-midi-tracks/utm.s", cpu="54455", dram=True),
    ),
    gates=(Gate("tools/verify/verify_usbmidi_tracks.py", stage="image"),),
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
