"""USB AUDIO OUT -- the unit as a UAC2 audio input at 44.1 kHz 24-bit, in one of five layouts.

One source (usbaudio.s, markandrus/octemu, MIT) assembled with the LAYOUT
setting as USB_LAYOUT, an Apply.BUILD setting a remix pins:

  TRACKS MAIN CUE  20 channels at high speed: the tracks' L/R (post-FX,
                   pre-fader) on 1-16, MAIN 17-18, CUE 19-20 (MAIN/CUE Bryan T);
                   full speed the tracks' stereo sum
  TRACKS           16 channels, the tracks; full speed their sum
  MASTER           2 channels, track 8's L/R at both speeds (Sam Banks)
  MAIN CUE         4 channels, MAIN + CUE; full speed MAIN (Bryan T)
  MAIN             2 channels, MAIN at both speeds

A DRAM unit with build-time detours. Needs USB MIDI: the audio function
joins its composite, and the ISR shim chains to USB MIDI's. Until 6 Oct 2026
the five layouts were five modules (USB AUDIO OUT TRACKS MAIN CUE, ... OUT
MAIN). README.md has the design and what was measured per layout.
"""
import dataclasses

from remix.schema import (Apply, Category, Detour, Gate, Kind, Linked, Module, Option,
                          Override, Poke, Proof, Setting, Store)

H = bytes.fromhex


SOURCE = "modules/usb-audio-out/usbaudio.s"


# LAYOUT's labels in USB_LAYOUT order: the index is the assembler's value.
LAYOUTS = ("TRACKS MAIN CUE", "TRACKS", "MASTER", "MAIN CUE", "MAIN")
STORE_ID = "octabam.usb-audio-out"


def layout_inc(layout):
    """The `remix.inc` usbaudio.s includes: USB_LAYOUT (the index of LAYOUTS);
    USB_IN 1 when USB AUDIO IN is in the remix (usbaudio.s then answers
    GET_INTERFACE(5) from that unit's in_alt)."""
    def inc(modules):
        usb_in = int("USB AUDIO IN" in modules)
        return (f"| remix.inc -- usbaudio.s's layout\n    .set USB_LAYOUT, {layout}\n"
                f"    .set USB_IN, {usb_in}\n")
    return inc


DETOURS = (
    Detour(0x4001dd04, H("2039fc0b01c4"), "usbaudio", "audio_setiface_shim",
           "SET_INTERFACE: interface 4 alt 1 brings the stream up, alt 0 down; others stock"),
    Detour(0x4001d824, H("4879400e20a1"), "usbaudio", "audio_getiface_shim",
           "GET_INTERFACE: interface 4 reports the alt setting the host asked for"),
    Detour(0x4001de64, H("2039fc0b01c0"), "usbaudio", "audio_ctrl_shim",
           "class requests to the clock source (sample rate CUR/RANGE, validity); the rest STALL as stock"),
    Detour(0x4001e91c, H("4ebaed9a7040"), "usbaudio", "audio_reset_shim",
           "USBSTS.URI handler: bus reset puts the audio interfaces (4, and 5 with USB AUDIO IN) back to alt 0"),
    Detour(0x4001e952, H("2039fc0b0140"), "usbaudio", "audio_sessend_shim",
           "OTGSC.BSVIS session end: the same, before USBCMD.RS is cleared"),
    Detour(0x4001d4b2, H("23d04ec95028"), "usbaudio", "audio_ep0page_shim",
           "usb_ep0_send fills the dTD's buffer page 1 too: a configuration straddling a 4 KB page transmitted truncated"),
    Detour(0x4000d9a0, H("42b946104d4e"), "usbaudio", "audio_frame_shim",
           "frame_isr's last instruction: the per-block producer (20 channels: tracks, MAIN, CUE; + the sum into the rings) and the packet builder"),
    Detour(0x4001e606, H("2039fc0b01ac"), "usbaudio", "audio_isr_shim",
           "usb_isr UI path: retire EP3 IN completions, then USB MIDI's shim"),
)

_PRODUCER = 0x4000d9a0
_PRODUCER_NOTE = {
    "TRACKS MAIN CUE": "the per-block producer (20 channels: tracks, MAIN, CUE; + the sum into the rings) and the packet builder",
    "TRACKS": "the per-block producer (16 channels: the tracks; + the sum into the rings) and the packet builder",
    "MASTER": "the per-block producer (track 8's L/R) and the packet builder",
    "MAIN CUE": "the per-block producer (MAIN L/R + CUE L/R) and the packet builder",
    "MAIN": "the per-block producer (MAIN L/R) and the packet builder",
}


def _variant(values):
    """LAYOUT -> the unit's include and the producer detour's note; the
    alignment gate belongs to the twenty-channel layout alone."""
    layout = values["LAYOUT"]
    return {
        "linked": (Linked("usbaudio", SOURCE, cpu="5475", dram=True,
                          include=layout_inc(LAYOUTS.index(layout))),),
        "detours": tuple(dataclasses.replace(d, note="frame_isr's last instruction: " + _PRODUCER_NOTE[layout])
                         if d.site == _PRODUCER else d for d in DETOURS),
        "gates": _GATES if layout == "TRACKS MAIN CUE" else (),
    }


# MAIN/CUE aligned with the tracks (skips without a source project)
_GATES = (Gate("tools/verify/verify_usb_align.py", remix_arg=False, venv=True, stage="image"),)

MODULE = Module(
    name="usb-audio-out", key="USB AUDIO OUT", kind=Kind.CF_PATCH,
    category=Category.MIDI_USB, author="markandrus/octemu", author_url="https://github.com/markandrus/octemu",
    proof=Proof.PORT,
    proof_note="each layout under the port (`verify_usb`); on a unit: TRACKS MAIN CUE on Sam's MKII (image 64, 25 Sep 2026) and Tim's MKI (OCTATRICK9, 26 Sep 2026), MAIN CUE on Bryan T's MKII (build 16, 27 Sep 2026); the bus reset and session-end shims: the alt 0 request under the port only, the `usbmidi_rx_bus_end` call on Ignorato's MKII (OCTABAM21, 9 Oct 2026, three replugs); README.md per layout",
    doc="The tracks, MAIN, CUE or track 8 over USB (UAC2, 2 to 20 channels, 24-bit), by its LAYOUT setting (markandrus/octemu).",
    linked=(Linked("usbaudio", SOURCE, cpu="5475", dram=True, include=layout_inc(0)),),
    detours=DETOURS,
    # The ISR site is USB MIDI's; this shim does its EP3 work and jumps to
    # USB MIDI's shim by symbol (the units link together).
    # The ISR site is USB MIDI's. The bus reset and session-end sites are
    # USB MIDI's too: usbaudio.s's shims call usbmidi_rx_bus_end beside
    # their own alt 0 request.
    overrides=(Override(0x4001e606, "USB MIDI"), Override(0x4001e91c, "USB MIDI"), Override(0x4001e952, "USB MIDI")),
    pokes=(Poke(0x400e2004, H("000000"), H("ef0201"),
                "device descriptor: class/subclass/protocol = interface-association composite"),),
    store=Store(STORE_ID),
    settings=(Setting(1, "LAYOUT", Option(*LAYOUTS), default="TRACKS MAIN CUE", apply=Apply.BUILD,
                      doc="which channels go to the host: the five layouts above"),),
    variant=_variant,
)
