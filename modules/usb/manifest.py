"""USB -- the composite USB device: MIDI in/out on EP2, the host as audio
out (EP3 IN) and in (EP3 OUT), one module where four stood until 14 Oct 2026
(USB MIDI, USB AUDIO OUT, USB AUDIO IN, USB CROSSBAR).

Six checkboxes (run-time settings, Apply.NEXT_BOOT, kept in the CS1 early
block): at crossbar init the unit reads the block and serves the
descriptors, producer and input path of the values it holds; without a
valid block it serves the image's resolved values. Every combination is in
every image -- the one composable producer, the input path and USB MIDI's
units, and the memory claims are the ABCD maxima.

  TRACKS            the 16 track channels to the host, PRE (the read-back
                    arena) or POST (post-fader, each track times its own
                    MAIN gain), or OFF
  MAIN              the 2-channel MAIN mix in the stream
  CUE               the 2-channel CUE mix in the stream
  MASTER            track 8's L/R as a 2-channel pair in the stream (not
                    with TRACKS, which already carries track 8)
  IN                which inputs the host's channels stand in for (AB, CD,
                    ABCD), or OFF for no host -> device stream
  MIDI              USB MIDI in/out, or OFF (the device is MSC only, or
                    MSC + audio)

The stream is the checked boxes in slot order (TRACKS, MAIN, CUE, MASTER):
0, 2, 4, 6, 16, 18 or 20 channels, 24-bit samples in 4-byte subslots at
high speed, the 8-byte stereo sum at full speed (sum priority: TRACKS >
MAIN > CUE > MASTER). IN needs an output stream beside it (EP3 IN is the
implicit-feedback source for EP3 OUT): the build refuses a resolved pair
(descriptors.remix_inc), the unit's SETTINGS page refuses the move
(brain.c), and cfgsel forces IN off on a bad block. TRACKS with MASTER is
refused the same three ways (cfgsel clears MASTER). The defaults (TRACKS
PRE, MAIN, CUE, MIDI) are the released image's TRACKS MAIN CUE. With MIDI
off the audio interfaces renumber (AC 3/AS 4/IN 5 -> 1/2/3). Every combo
polls EP3 IN at bInterval 2 (250 us). README.md has the design
and what was measured per combo, per direction, and on units.
"""
import importlib.util
import math
import pathlib

from remix import schema, stock
from remix.schema import (Apply, Binary, Category, Claims, Detour, DspHook, DspSection, Gate,
                          Kind, Linked, Module, Option, Poke, Proof, Setting, Store)

H = bytes.fromhex

# The descriptor generator beside this file, loaded by path.
_spec = importlib.util.spec_from_file_location(
    "usb_descriptors", pathlib.Path(schema.__file__).resolve().parents[2] / "modules/usb/descriptors.py")
descriptors = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(descriptors)

SOURCE = "modules/usb"                       # every linked unit lives in this module's directory
STORE_ID = "octabam.usb"

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
        raise ValueError("USB TRACKS POST: payload A has no X record over X:0x6c00..0x6cff")
    for i, w in enumerate(words):
        want = round(math.sin(2 * math.pi * i / 1024) * 0x7fffff)
        if abs(w - want) > 64 or (i and w <= words[i - 1]):
            raise ValueError(f"USB TRACKS POST: X:0x{XLV_ADDR + i:04x} = 0x{w:06x} is not the "
                             f"sine core 0's XLV curve reads (expected about 0x{want:06x})")
    return words


def audio_inc(modules, remix):
    """usbaudio.s's remix.inc: the TRACKS POST XLV curve (every producer is
    compiled) and descriptors.py's runtime knobs (the resolved values, the
    CS1 offsets, the early block's entries)."""
    words = xlv_table()
    lines = ["| the XLV curve: payload A X:0x6c00..0x6cff from the user's stock image (manifest.py)",
             ".macro POST_XLV_TABLE"]
    for i in range(0, XLV_WORDS, 8):
        lines.append("    .long " + ", ".join(f"0x{w:06x}" for w in words[i:i + 8]))
    lines.append(".endm")
    return "\n".join(lines) + descriptors.audio_remix_inc(modules, remix)


# ---- the linked units, in the order the four modules linked them ------------
# The DRAM units share one link, so this order is the address order of every
# image: USB MIDI's four, then usbaudio, then crossbar, then usbaudio_in.

LINKED = (
    # his unit, verbatim: the build re-links it at his zone address and
    # compares with his usb-midi.py's blob (1,124 B, from our stock bytes)
    Linked("usbmidi", f"{SOURCE}/usbmidi.s", cpu="54455", dram=True,
           reference=(0x400d24f0, "6291d91e923145be62719eee56c2ca823d36c2d71ae538550e70b5533d404e60")),
    Linked("usbmidi_rx", f"{SOURCE}/usbmidi_rx.s", cpu="54455", dram=True),
    Linked("usbmidi_clamp", f"{SOURCE}/clamp.s", cpu="54455", dram=True),
    # every configuration of every setting combination, one length
    # (descriptors.remix_inc), and the absolute `cfg_len` the clamps read
    Linked("usbmidi_cfg", f"{SOURCE}/cfg.s", cpu="5475", dram=True,
           include=descriptors.remix_inc),
    # usb_trk..usb_hs_step: the settings, interface numbers, cfg_sel pointers
    # and geometry cfgsel writes before the handoff (40 B, contiguous)
    Linked("usbaudio", f"{SOURCE}/usbaudio.s", cpu="5475", dram=True,
           include=audio_inc, boot_mutable=(("usb_trk", 40),),
           defsyms=(("LM_STATS", 0), ("LM_DSP", 0), ("LM_OT", 0), ("DL_DIAG", 0))),   # LOAD METER's blocks, 0 without it
    Linked("usbcrossbar", f"{SOURCE}/usbcrossbar.s", cpu="5475", dram=True),
    Linked("usbaudio_in", f"{SOURCE}/usbaudio_in.s", cpu="5475", dram=True),
)


# ---- the detour sets --------------------------------------------------------
# USB MIDI's ten sites; the ISR, bus-reset and session-end shims of the old
# USB AUDIO OUT module replace these three (they chain to usbmidi_rx_bus_end
# by symbol, as they did as separate modules).

MIDI_DETOURS = (
    Detour(0x4001d9ca, H("4879400b9868"), "usbmidi_rx", "usbmidi_rx_setcfg_shim",
           "SET_CONFIGURATION body: note the speed, then usbmidi's EP2 bring-up (512-byte packets at high speed)"),
    Detour(0x4001e606, H("2039fc0b01ac"), "usbmidi_rx", "usbmidi_rx_isr_shim",
           "usb_isr UI path: EP2 OUT completions -> decode with FIFO room / re-prime, then usbmidi's EP2 IN kick"),
    Detour(0x4001d184, H("203c00408080"), "usbmidi_rx", "usbmidi_rx_late_shim",
           "usb_midi_rx_prime entry: at state 2 it is usbmidi_isr_shim's 64-byte branch for a completion after "
           "the first ENDPTCOMPLETE read -- decode it and re-prime 512 (#1017)"),
    Detour(0x40010bc8, H("4fefffec48d7043c"), "usbmidi", "usbmidi_send_shim",
           "midi_send entry: queue the message for the USB encoder", pad_to=8),
    Detour(0x400108b0, H("2f02122f000b"), "usbmidi", "usbmidi_prio_shim",
           "priority (realtime) byte sender: queue the byte for the USB encoder"),
    Detour(0x4001e91c, H("4ebaed9a7040"), "usbmidi_rx", "usbmidi_rx_reset_shim",
           "USBSTS.URI handler: a bus reset takes EP2 down until the next SET_CONFIGURATION"),
    Detour(0x4001e952, H("2039fc0b0140"), "usbmidi_rx", "usbmidi_rx_sessend_shim",
           "OTGSC.BSVIS session end (cable pulled): the same, before USBCMD.RS is cleared"),
    Detour(0x4001daec, H("303946c8ce0c"), "usbmidi", "usbmidi_clrfeat_shim",
           "CLEAR_FEATURE(ENDPOINT_HALT): answer for EP2 instead of stalling"),
    # GET_DESCRIPTOR(CONFIG / OTHER_SPEED): the responder's two hardcoded
    # clamps (moveq #32,d0 / cmpl d2,d0 / bcs +4) become min(wLength, cfg_len)
    Detour(0x4001d858, H("7020b0826504"), "usbmidi_clamp", "usbmidi_clamp1_shim",
           "config responder: clamp the reply to the grown configuration's length"),
    Detour(0x4001d896, H("7020b0826504"), "usbmidi_clamp", "usbmidi_clamp2_shim",
           "other-speed responder: the same clamp"),
)

AUDIO_DETOURS = (
    Detour(0x4001dd04, H("2039fc0b01c4"), "usbaudio", "audio_setiface_shim",
           "SET_INTERFACE: the AS interface (4, or 2 without MIDI) alt 1 brings the stream up, alt 0 down; others stock"),
    Detour(0x4001d824, H("4879400e20a1"), "usbaudio", "audio_getiface_shim",
           "GET_INTERFACE: the audio interfaces report the alt setting the host asked for"),
    Detour(0x4001de64, H("2039fc0b01c0"), "usbaudio", "audio_ctrl_shim",
           "class requests to the clock source (sample rate CUR/RANGE, validity); the rest STALL as stock"),
    Detour(0x4001e91c, H("4ebaed9a7040"), "usbaudio", "audio_reset_shim",
           "USBSTS.URI handler: bus reset puts the audio interfaces back to alt 0"),
    Detour(0x4001e952, H("2039fc0b0140"), "usbaudio", "audio_sessend_shim",
           "OTGSC.BSVIS session end: the same, before USBCMD.RS is cleared"),
    Detour(0x4001d4b2, H("23d04ec95028"), "usbaudio", "audio_ep0page_shim",
           "usb_ep0_send fills the dTD's buffer page 1 too: a configuration straddling a 4 KB page transmitted truncated"),
    Detour(0x4000d9a0, H("42b946104d4e"), "usbaudio", "audio_frame_shim",
           "frame_isr's last instruction: the per-block producer and the packet builder (the checked boxes choose what the producer writes)"),
    Detour(0x4001e606, H("2039fc0b01ac"), "usbaudio", "audio_isr_shim",
           "usb_isr UI path: retire EP3 IN completions, then USB MIDI's shim"),
)

# The four config responders (GET_DESCRIPTOR CONFIG / OTHER_SPEED, both
# speeds): each site pea'd its baked table and branched to the shared
# `movel d1,sp@- / jsr a0@` at 0x4001d88e. A stub pushes the pointer the
# runtime settings chose (usb_cfg_sel_*), drops its own return
# address and jumps to that tail: usb_ep0_send returns to the site's own
# continuation, with the stock stack.
SELECTOR_DETOURS = (
    Detour(0x4001d880, H("4879400e201c6006"), "usbaudio", "stub_fs_config",
           "GET_DESCRIPTOR(CONFIG, full speed): serve the config the runtime settings chose",
           kind="jsr", pad_to=8),
    Detour(0x4001d888, H("4879400e203c"), "usbaudio", "stub_hs_config",
           "GET_DESCRIPTOR(CONFIG, high speed): the same", kind="jsr", pad_to=6),
    Detour(0x4001d8be, H("4879400e207c60c8"), "usbaudio", "stub_os_hs",
           "GET_DESCRIPTOR(OTHER_SPEED, high-speed table): the same", kind="jsr", pad_to=8),
    Detour(0x4001d8c6, H("4879400e205c60c0"), "usbaudio", "stub_os_fs",
           "GET_DESCRIPTOR(OTHER_SPEED, full-speed table): the same", kind="jsr", pad_to=8),
)

CROSSBAR_DETOUR = (
    Detour(0x4001e030, H("203c08000000"), "usbcrossbar", "crossbar_init_shim",
           "USB controller init: read the CS1 block (cfgsel), then SCM BCR and XBS PRS/CRS for slaves 2 and 4, then the displaced load"),
)

IN_DETOURS = (
    Detour(0x4001dd0a, H("008000400040"), "usbaudio_in", "in_setiface_shim",
           "SET_INTERFACE: the IN interface (5, or 3 without MIDI) alt 0/1 records the alt and ACKs, other alts STALL; the rest goes on to stock"),
    Detour(0x40004bc0, H("720113c1fc04801d"), "usbaudio_in", "in_state7_shim",
           "frame transfer state 7: EP3 OUT, the ring, and one more transfer to core 0 at $6320",
           pad_to=8),
    Detour(0x4001de6e, H("23c0fc0b01c0"), "usbaudio_in", "in_ctrl_shim",
           "EP0 stall store: vendor GET 0x56 answers the IN counters instead"),
)

_SHARED = {0x4001e606, 0x4001e91c, 0x4001e952}   # the three sites the audio shims take over from MIDI's
_AUDIO_AT_SITE = {d.site: d for d in AUDIO_DETOURS if d.site in _SHARED}
_AUDIO_EXTRA = tuple(d for d in AUDIO_DETOURS if d.site not in _SHARED)


def _dsp():
    """Core 0 receives the ESAI at the RX block and injects the host's
    channels over inputs A/B, C/D or A-D by the IN byte (the inject
    reads word 1 of in_tx, written by usbaudio_in.s's in_build)."""
    return DspSection(
        asm=f"{SOURCE}/rx_inject.asm",
        priority=9,         # remix-switch's park holds 20 (appended with every
                            # BRAIN), 10-21 are taken; the inject needs no
                            # trailing free words
        payloads=frozenset({"A"}),          # core 0 receives the ESAI
        tail=True,          # every stock effect kept: P:$1fdf, a record of its own
        hooks=(DspHook(0x88, (0x627000, 0x000204), "inject",
                       "frame head: the RX block is written before any reader runs"),),
    )


# The ABCD maxima in every image: the build refuses two modules claiming the
# same SRAM, and IN is one run-time setting, not a re-claim.
CLAIMS = Claims(sram=((0x80007c00, 0x80, "EP3 OUT dTDs"),
                      (0x80007c80, 0x300, "EP3 OUT packet buffers"),
                      (0x80007f80, 0x40, "EP0 reply for vendor 0x56"),
                      (0x80007880, 0x140, "USB IN's host-port block for the DSP (TX_BYTES)"),
                      (0x800079c0, 0x80, "EP3 IN dTDs (USB OUT)"),
                      (0x80007a40, 0x20, "USB OUT producer state (prod_*)")))

MIDI_GATES = (Gate("tools/verify/verify_usbmidi_rx.py", stage="image"),
              Gate("tools/verify/verify_usb_midi_clock.py", stage="image"),
              Gate("tools/verify/verify_usb_midi_replug.py", stage="image"),
              Gate("tools/verify/verify_usbmidi_late.py", venv=True, stage="image"))
# MAIN/CUE aligned with the tracks (skips without a source project)
GATE_ALIGN = Gate("tools/verify/verify_usb_align.py", remix_arg=False, venv=True, stage="image")
# the stems against core 0's own MAIN, sample by sample, under the port (skips without a source project)
GATE_POST = Gate("tools/verify/verify_usb_post.py", remix_arg=False, venv=True, stage="image")
GATE_IN = Gate("tools/verify/verify_usb_in.py", remix_arg=False, venv=True, stage="image")

POKE_COMPOSITE = Poke(0x400e2004, H("000000"), H("ef0201"),
                      "device descriptor: class/subclass/protocol = interface-association composite")

MODULE = Module(
    name="usb", key="USB", kind=Kind.HYBRID,
    category=Category.MIDI_USB, author="markandrus/octemu", author_url="https://github.com/markandrus/octemu",
    proof=Proof.HARDWARE,
    proof_note="Sam's MKII, octabam-core OCTABAMB5 (main 11d9f129), macOS on an arm64 Mac, 19 Oct 2026, with TRACKS PRE, MAIN, CUE and MIDI at their defaults (20 channels): enumeration (the MIDI port and a 20-channel input); MIDI in (notes trig tracks 3, 4, 5 and 8 on their own channels, and again after a replug); MIDI out clock at 48-49 per second, back after each of three cable replugs; audio after a replug with 0 overruns and 0 underruns; DISK MODE in and out (the image read back off the card, `cmp` equal, then MIDI, audio and counters clean); not run on a unit that day: TRACKS OFF and POST, MASTER, MAIN or CUE off, MIDI off, IN (octabam-core fixes it OFF), a Windows host, an MKI; earlier: cursory testing on Sam's MKII (owner report, 16 Oct 2026); `verify_usb` for every combination and `verify_usb_in` for every IN value under the port; on units: MIDI in/out on Sam's MKII (image 64, 25 Sep 2026), Tim's MKI (OCTATRICK9, 26 Sep 2026) and Ignorato's MKII (OCTABAM21, 9 Oct 2026, transmit after three replugs, macOS and Windows 10), USB clock tempo on Kazeko's MKI (#633, 6 Oct 2026); TRACKS MAIN CUE on Sam's MKII and Tim's MKI, MAIN CUE and the ABCD inject on Bryan T's MKII (build 16, 27 Sep 2026), TRACKS POST on allmyfriendsaresynths's MKII (P3, 5 Oct 2026); the crossbar values at stream-up on Bryan T's MKII (usbin-test 12-16, 26-27 Sep 2026); README.md per combination and direction",
    doc="Class-compliant USB-MIDI in/out plus UAC2 audio to and from the host on the OT's own USB port (markandrus/octemu; the input path and crossbar bryantysinger's; the TRACKS POST stems allmyfriendsaresynths's), by its TRACKS / MAIN / CUE / MASTER / IN / MIDI checkboxes.",
    linked=LINKED,
    detours=tuple(_AUDIO_AT_SITE.get(d.site, d) for d in MIDI_DETOURS) + _AUDIO_EXTRA
    + SELECTOR_DETOURS + CROSSBAR_DETOUR + IN_DETOURS,
    pokes=(POKE_COMPOSITE,),
    dsp=_dsp(),
    claims=CLAIMS,
    gates=MIDI_GATES + (GATE_ALIGN, GATE_POST, GATE_IN),
    dsp_if=lambda fixed: fixed.get("IN", "AB") != "OFF",   # no inject where IN is fixed OFF
    store=Store(STORE_ID),
    settings=(Setting(7, "TRACKS", Option("OFF", "PRE", "POST"), default="PRE", apply=Apply.NEXT_BOOT,
                      early=True,
                      doc="the 16 track channels to the host, PRE (the read-back arena) or POST (post-fader, each track times its own MAIN gain), or OFF; takes effect at the next boot"),
              Setting(8, "MAIN", Binary(), default=1, apply=Apply.NEXT_BOOT,
                      early=True,
                      doc="the 2-channel MAIN mix in the host stream; takes effect at the next boot"),
              Setting(9, "CUE", Binary(), default=1, apply=Apply.NEXT_BOOT,
                      early=True,
                      doc="the 2-channel CUE mix in the host stream; takes effect at the next boot"),
              Setting(10, "MASTER", Binary(), default=0, apply=Apply.NEXT_BOOT,
                      early=True,
                      doc="track 8's L/R as a 2-channel pair in the host stream (refused with TRACKS on); takes effect at the next boot"),
              Setting(11, "IN", Option("OFF", "AB", "CD", "ABCD"), default="OFF", apply=Apply.NEXT_BOOT,
                      early=True,
                      doc="which inputs the host's channels stand in for (AB, CD, ABCD), or OFF for no host -> device stream; needs an output stream beside it; takes effect at the next boot"),
              Setting(12, "MIDI", Binary(), default=1, apply=Apply.NEXT_BOOT,
                      early=True,
                      doc="USB MIDI in/out on the device, or OFF for MSC + audio only; takes effect at the next boot")),
)
