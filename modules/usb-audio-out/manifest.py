"""USB AUDIO OUT -- the unit as a UAC2 audio input at 44.1 kHz 24-bit, in one of six layouts.

One source (usbaudio.s, markandrus/octemu, MIT) assembled with the LAYOUT
setting as USB_LAYOUT, an Apply.BUILD setting a remix pins:

  TRACKS MAIN CUE  20 channels at high speed: the tracks' L/R (post-FX,
                   pre-fader) on 1-16, MAIN 17-18, CUE 19-20 (MAIN/CUE Bryan T);
                   full speed the tracks' stereo sum
  TRACKS           16 channels, the tracks; full speed their sum
  MASTER           2 channels, track 8's L/R at both speeds (Sam Banks)
  MAIN CUE         4 channels, MAIN + CUE; full speed MAIN (Bryan T)
  MAIN             2 channels, MAIN at both speeds
  TRACKS POST      16 channels, each track after its own MAIN gain (LEVEL,
                   mute, solo, XLV; MAIN_LEVEL left out); full speed their
                   sum (allmyfriendsaresynths, @clickysteve)

A DRAM unit with build-time detours. Needs USB MIDI: the audio function
joins its composite, and the ISR shim chains to USB MIDI's. Until 8 Oct 2026
the layouts were six modules (USB AUDIO OUT TRACKS MAIN CUE, ... OUT MAIN,
OUT TRACKS POST). README.md has the design and what was measured per layout.
"""
import dataclasses
import math
import pathlib

from remix import schema, stock
from remix.schema import (Apply, Category, Detour, Gate, Kind, Linked, Module, Option,
                          Override, Poke, Proof, Setting, Store)

H = bytes.fromhex


SOURCE = "modules/usb-audio-out/usbaudio.s"


# LAYOUT's labels in USB_LAYOUT order: the index is the assembler's value.
LAYOUTS = ("TRACKS MAIN CUE", "TRACKS", "MASTER", "MAIN CUE", "MAIN", "TRACKS POST")
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


_ROOT = pathlib.Path(schema.__file__).resolve().parents[2]
XLV_ADDR, XLV_WORDS = 0x6c00, 256           # X:0x6c00.., indexed by XLV >> 7 (0..254 in use)


def xlv_table(image=None):
    """TRACKS POST: payload A's X:0x6c00..0x6cff as 24-bit words, from the
    user's stock image. Refuses unless they are the first quarter of a sine
    (the curve core 0 applies to the MAIN gain): the image or the parse is
    wrong otherwise, and the stems would be silently mis-scaled."""
    import sys
    sys.path.insert(0, str(_ROOT / "tools/build"))
    import dsp_modmap
    img = image if image is not None else stock.STOCK_IMAGE.read_bytes()
    tag, va, ln = dsp_modmap.PAYLOADS[0]
    assert tag == "A"
    mods, blob = dsp_modmap.modules(img, va, ln)
    for sp, addr, cnt, data in mods:
        if sp == 1 and addr <= XLV_ADDR and XLV_ADDR + XLV_WORDS <= addr + cnt:
            off = data + (XLV_ADDR - addr) * 3
            words = [dsp_modmap.w24(blob, off + 3 * i) for i in range(XLV_WORDS)]
            break
    else:
        raise ValueError("USB AUDIO OUT TRACKS POST: payload A has no X record over X:0x6c00..0x6cff")
    for i, w in enumerate(words):
        want = round(math.sin(2 * math.pi * i / 1024) * 0x7fffff)
        if abs(w - want) > 64 or (i and w <= words[i - 1]):
            raise ValueError(f"USB AUDIO OUT TRACKS POST: X:0x{XLV_ADDR + i:04x} = 0x{w:06x} is not the "
                             f"sine core 0's XLV curve reads (expected about 0x{want:06x})")
    return words


def post_inc(modules):
    """TRACKS POST's remix.inc: layout 5, plus the XLV table as a macro the
    data section expands (post_xlv)."""
    words = xlv_table()
    lines = ["| the XLV curve: payload A X:0x6c00..0x6cff from the user's stock image (manifest.py)",
             ".macro POST_XLV_TABLE"]
    for i in range(0, XLV_WORDS, 8):
        lines.append("    .long " + ", ".join(f"0x{w:06x}" for w in words[i:i + 8]))
    lines.append(".endm")
    return layout_inc(LAYOUTS.index("TRACKS POST"))(modules) + "\n".join(lines) + "\n"


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
    "TRACKS POST": "the per-track MAIN gains (every block) and the per-block producer (16 channels: the tracks after their gains; + the sum into the rings) and the packet builder",
}


def _variant(values):
    """LAYOUT -> the unit's include and the producer detour's note; the
    alignment gate belongs to the twenty-channel layout alone."""
    layout = values["LAYOUT"]
    inc = post_inc if layout == "TRACKS POST" else layout_inc(LAYOUTS.index(layout))
    return {
        "linked": (Linked("usbaudio", SOURCE, cpu="5475", dram=True, include=inc),),
        "detours": tuple(dataclasses.replace(d, note="frame_isr's last instruction: " + _PRODUCER_NOTE[layout])
                         if d.site == _PRODUCER else d for d in DETOURS),
        "gates": _GATES.get(layout, ()),
    }


# MAIN/CUE aligned with the tracks (skips without a source project)
_GATES = {
    "TRACKS MAIN CUE": (Gate("tools/verify/verify_usb_align.py", remix_arg=False, venv=True, stage="image"),),
    # the stems against core 0's own MAIN, sample by sample, under the port (skips without a source project)
    "TRACKS POST": (Gate("tools/verify/verify_usb_post.py", remix_arg=False, venv=True, stage="image"),),
}

MODULE = Module(
    name="usb-audio-out", key="USB AUDIO OUT", kind=Kind.CF_PATCH,
    category=Category.MIDI_USB, author="markandrus/octemu", author_url="https://github.com/markandrus/octemu",
    proof=Proof.PORT,
    proof_note="each layout under the port (`verify_usb`); on a unit: TRACKS MAIN CUE on Sam's MKII (image 64, 25 Sep 2026) and Tim's MKI (OCTATRICK9, 26 Sep 2026), MAIN CUE on Bryan T's MKII (build 16, 27 Sep 2026), TRACKS POST on allmyfriendsaresynths's MKII (P3, 5 Oct 2026); the bus reset and session-end shims: the `usbmidi_rx_bus_end` call on Ignorato's MKII (OCTABAM21, 9 Oct 2026, three replugs); README.md per layout",
    doc="The tracks, MAIN, CUE or track 8 over USB (UAC2, 2 to 20 channels, 24-bit), by its LAYOUT setting (markandrus/octemu; the POST layout allmyfriendsaresynths's, @clickysteve).",
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
                      doc="which channels go to the host: the six layouts above"),),
    variant=_variant,
)
