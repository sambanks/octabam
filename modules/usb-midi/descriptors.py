"""The USB configuration descriptors the responder serves, per remix.

markandrus/octemu's `custom/usb-midi.py` and `custom/usb-audio.py`
(`config_descriptor`, MIT), as the text of USB MIDI's descriptor unit:
the build calls `remix_inc(modules)` and writes it beside `cfg.s` as
`remix.inc` (schema.Linked.include). Every configuration keeps the stock
MSC interface byte for byte at the front:

  MSC only (stock)      one interface, 32 bytes
  + USB MIDI            + AudioControl [2] + MIDIStreaming with EP2 bulk
                        in/out: three interfaces, 124 bytes
  + USB AUDIO OUT       the MIDI function under an interface association,
                        then a second: a UAC2 AudioControl (clock source,
                        input terminal, USB streaming output terminal) +
                        AudioStreaming (alt 0 idle, alt 1 with the iso IN
                        EP3): five interfaces, 250 bytes. Its LAYOUT
                        setting sets the channels: TRACKS MAIN CUE twenty at
                        high speed (tracks, MAIN, CUE), TRACKS sixteen (the
                        tracks), both with the stereo sum at full speed;
                        MASTER track 8's L/R at both speeds and MAIN MAIN
                        alone, each a front-left/front-right cluster; MAIN
                        CUE MAIN + CUE, with MAIN at full speed. 24-bit
                        samples in 4-byte subslots in every layout.
  + USB AUDIO IN        the other direction beside it, at high speed: a
                        USB streaming input terminal -> line output terminal,
                        and AudioStreaming interface 5 with EP3 OUT (a stereo
                        pair or four channels from the host, standing in for
                        inputs A/B, C/D or A-D by its INPUTS setting): six
                        interfaces.

`cfg_len` is exported as an absolute symbol: the responder's two clamp
shims (usbmidi.s) compare wLength against it, since the stock `moveq #32`
cannot hold either grown length above 127.
"""
import struct

# 24-bit samples in 4-byte subslots. 16 ch x 4 B x 44.1 kHz is 2,822 B/ms,
# and one high-speed isochronous transaction carries at most 1,024 B, so the
# endpoint is polled every 250 us (bInterval 2): 11.025 frames x 64 B, at
# most 12 frames = 768 B a packet.
SUBSLOT, BITS = 4, 24
HS_CHANNELS, HS_MAXPKT, HS_BINTERVAL = 20, 12 * 80, 2     # 11/12 frames x 80 B every 250 us (16 tracks + MAIN + CUE)
FS_CHANNELS, FS_MAXPKT, FS_BINTERVAL = 2, 45 * 8, 1       # 44/45 stereo frames x 8 B every 1 ms
# per audio module: (channels, max packet) at high speed; full speed is FS_*
HS_LAYOUT = {"USB AUDIO OUT TRACKS MAIN CUE": (HS_CHANNELS, HS_MAXPKT),
             "USB AUDIO OUT TRACKS": (16, 12 * 64),                # 11/12 frames x 64 B (16 tracks) every 250 us
             "USB AUDIO OUT TRACKS POST": (16, 12 * 64),           # the same sixteen channels, after each track's MAIN gain
             "USB AUDIO OUT MASTER": (2, 12 * 8),                # 11/12 frames x 8 B (T8) every 250 us (1 ms until 28 Sep 2026)
             "USB AUDIO OUT MAIN CUE": (4, 12 * 16),                   # 11/12 frames x 16 B (MAIN + CUE) every 250 us
             "USB AUDIO OUT MAIN": (2, 12 * 8)}                        # 11/12 frames x 8 B (MAIN) every 250 us
FRONT_LR = 0x3                                             # bmChannelConfig: front left, front right (OUT MASTER, IN)
UAC2_AC_IFACE, UAC2_AS_IFACE = 3, 4                        # usbaudio.s .set: the same numbers
UAC2_CLOCK_ID, UAC2_IT_ID, UAC2_OT_ID = 0x10, 0x11, 0x12

# USB AUDIO IN (Bryan T, 26 Sep 2026; AB / CD / ABCD 28 Sep): the host's
# channels standing in for inputs. AudioStreaming interface 5, EP3
# OUT (the only free endpoint: EP1 is mass storage, EP2 USB MIDI, EP3 IN the
# input stream). Asynchronous with IMPLICIT feedback: no endpoint is left
# for an explicit feedback IN, so EP3 IN is marked as the implicit-feedback
# data endpoint and the host sizes each OUT packet from EP3 IN's. Same
# clock source. It needs a USB AUDIO input layout for that feedback, one
# that polls every 250 us as this stream does (every out layout since 28 Sep 2026).
# HIGH SPEED ONLY: the full-speed configurations carry no interface 5 (the
# unit does not serve it), so a full-speed host is never offered one.
USBIN_AS_IFACE = 5
USBIN_IT_ID, USBIN_OT_ID = 0x13, 0x14
# USB AUDIO IN by its INPUTS setting: host channels -> inputs (the DSP
# inject's slots). HS_LAYOUT and IN_LAYOUT are keyed "USB AUDIO OUT <LAYOUT>"
# and "USB AUDIO IN <INPUTS>", the module keys of the layouts until 6 Oct 2026.
IN_LAYOUT = {"USB AUDIO IN AB": 2, "USB AUDIO IN CD": 2, "USB AUDIO IN ABCD": 4}


def _bound_value(modules, key, name):
    """The build-time value `name` of module `key` in a selection (a dict of
    bound modules, as the build passes an include); the setting's default
    when the module is unbound; None when the module is not selected."""
    if key not in modules:
        return None
    m = modules[key] if isinstance(modules, dict) else None
    if m is not None and name in m.build_values:
        return m.build_values[name]
    from remix import registry
    s = next(s for s in registry.by_key(key).settings if s.name == name)
    return s.kind.labels[s.default]


def audio_key(modules):
    layout = _bound_value(modules, "USB AUDIO OUT", "LAYOUT")
    return None if layout is None else f"USB AUDIO OUT {layout}"


def in_key(modules):
    inputs = _bound_value(modules, "USB AUDIO IN", "INPUTS")
    return None if inputs is None else f"USB AUDIO IN {inputs}"


def _ep(addr, pkt):
    return bytes([7, 5, addr, 2]) + struct.pack("<H", pkt) + bytes([0])


def _ep_midi(addr, pkt):
    return bytes([9, 5, addr, 2]) + struct.pack("<H", pkt) + bytes(3)


_MS_CLASS = (bytes([7, 0x24, 1, 0, 1, 37, 0]) +           # MS header
             bytes([6, 0x24, 2, 1, 1, 0]) +               # IN jack, embedded 1
             bytes([6, 0x24, 2, 2, 2, 0]) +               # IN jack, external 2
             bytes([9, 0x24, 3, 1, 3, 1, 2, 1, 0]) +      # OUT jack, embedded 3
             bytes([9, 0x24, 3, 2, 4, 1, 1, 1, 0]))       # OUT jack, external 4


def midi_config(hs, other_speed=False):
    """MSC + AudioControl + MIDIStreaming, 124 bytes (usb-midi.py)."""
    bulk = 512 if hs else 64
    body = (bytes([9, 4, 0, 0, 2, 8, 6, 0x50, 0]) +
            _ep(0x81, bulk) + _ep(0x01, bulk) +
            bytes([9, 4, 1, 0, 0, 1, 1, 0, 0]) +
            bytes([9, 0x24, 1, 0, 1, 9, 0, 1, 2]) +
            bytes([9, 4, 2, 0, 2, 1, 3, 0, 0]) +
            _MS_CLASS +
            _ep_midi(0x02, bulk) + bytes([5, 0x25, 1, 1, 1]) +
            _ep_midi(0x82, bulk) + bytes([5, 0x25, 1, 1, 3]))
    total = 9 + len(body)
    hdr = bytes([9, 7 if other_speed else 2]) + struct.pack("<H", total) + bytes([3, 1, 0, 0xC0, 3])
    return hdr + body


def audio_config(hs, other_speed=False, key="USB AUDIO OUT TRACKS MAIN CUE", with_in=None):
    """The MIDI composite plus a UAC2 audio function, 250 bytes (usb-audio.py).

    Two SEPARATE functions under interface associations, the shape of a
    device macOS accepts (his measurement against an Elektron Digitone):
    one AudioControl collecting the MIDIStreaming interface, another
    collecting the AudioStreaming one. The clock source is read-only
    (bmControls 0b01) with one rate. Read-only does not stop a host SETting
    it: the Elektron Outbox 8 sends SET CUR 44100 (a control OUT with a
    4-byte data stage), which the stock EP0 stack cannot receive; usbaudio.s
    takes it (44100 acknowledged, any other rate STALLed).

    `key` is the audio module: USB AUDIO OUT MASTER declares its two channels
    front left / front right (the standard stereo cluster); the other two
    keep bmChannelConfig 0 as his descriptors have it.

    `with_in`: the USB AUDIO IN module's key (IN_LAYOUT), or None -- at high
    speed, add the host -> device path (IT 0x13 -> OT 0x14, AudioStreaming
    interface 5 with EP3 OUT, 2 or 4 channels) and mark EP3 IN as its
    implicit-feedback source. The full-speed configuration is the one
    without it.
    """
    with_in = with_in if hs else None
    in_ch = IN_LAYOUT[with_in] if with_in else 0
    in_cfg = FRONT_LR if in_ch == 2 else 0
    bulk = 512 if hs else 64
    nch, maxpkt = HS_LAYOUT[key] if hs else (FS_CHANNELS, FS_MAXPKT)
    chcfg = FRONT_LR if key in ("USB AUDIO OUT MASTER", "USB AUDIO OUT MAIN") else 0
    clk, it, ot = UAC2_CLOCK_ID, UAC2_IT_ID, UAC2_OT_ID
    clock = bytes([8, 0x24, 0x0A, clk, 0x01, 0x05, 0, 0])
    in_term = (bytes([17, 0x24, 0x02, it]) + struct.pack("<H", 0x0603) +
               bytes([0, clk, nch]) + struct.pack("<I", chcfg) +
               bytes([0]) + struct.pack("<H", 0) + bytes([0]))
    out_term = (bytes([12, 0x24, 0x03, ot]) + struct.pack("<H", 0x0101) +
                bytes([0, it, clk]) + struct.pack("<H", 0) + bytes([0]))
    in_path = b""
    if with_in:
        # host -> device: a USB streaming input terminal feeding a line
        # output terminal, on the same (read-only) clock
        in_path = (bytes([17, 0x24, 0x02, USBIN_IT_ID]) + struct.pack("<H", 0x0101) +
                   bytes([0, clk, in_ch]) + struct.pack("<I", in_cfg) +
                   bytes([0]) + struct.pack("<H", 0) + bytes([0]) +
                   bytes([12, 0x24, 0x03, USBIN_OT_ID]) + struct.pack("<H", 0x0603) +
                   bytes([0, USBIN_IT_ID, clk]) + struct.pack("<H", 0) + bytes([0]))
    ac_audio_total = 9 + len(clock) + len(in_term) + len(out_term) + len(in_path)
    ac_audio = (bytes([9, 0x24, 1]) + struct.pack("<H", 0x0200) + bytes([0x0A]) +
                struct.pack("<H", ac_audio_total) + bytes([0]) + clock + in_term + out_term + in_path)
    ac, as_ = UAC2_AC_IFACE, UAC2_AS_IFACE
    as_iface = (
        bytes([9, 4, as_, 0, 0, 1, 2, 0x20, 0]) +
        bytes([9, 4, as_, 1, 1, 1, 2, 0x20, 0]) +
        bytes([16, 0x24, 1, ot, 0, 1]) + struct.pack("<I", 1) +
        bytes([nch]) + struct.pack("<I", chcfg) + bytes([0]) +
        bytes([6, 0x24, 2, 1, SUBSLOT, BITS]) +
        # bmAttributes: isochronous, asynchronous; + usage "implicit
        # feedback data" (bits 5:4 = 10) when USB AUDIO IN pairs with it
        bytes([7, 5, 0x83, 0x25 if with_in else 0x05]) + struct.pack("<H", maxpkt) +
        bytes([HS_BINTERVAL if hs else FS_BINTERVAL]) +
        bytes([8, 0x25, 1, 0, 0, 0]) + struct.pack("<H", 0))
    if with_in:
        ii = USBIN_AS_IFACE
        as_iface += (
            bytes([9, 4, ii, 0, 0, 1, 2, 0x20, 0]) +
            bytes([9, 4, ii, 1, 1, 1, 2, 0x20, 0]) +
            bytes([16, 0x24, 1, USBIN_IT_ID, 0, 1]) + struct.pack("<I", 1) +
            bytes([in_ch]) + struct.pack("<I", in_cfg) + bytes([0]) +
            bytes([6, 0x24, 2, 1, SUBSLOT, BITS]) +
            bytes([7, 5, 0x03, 0x05]) +                      # iso, asynchronous, data
            struct.pack("<H", 12 * in_ch * SUBSLOT) +       # 96 B for a pair, 192 for four
            bytes([HS_BINTERVAL]) +
            bytes([8, 0x25, 1, 0, 0, 0]) + struct.pack("<H", 0))
    ac_midi = bytes([9, 0x24, 1, 0, 1]) + struct.pack("<H", 9) + bytes([1, 2])
    iad_midi = bytes([8, 0x0B, 1, 2, 0x01, 0x00, 0x00, 0])
    iad_audio = bytes([8, 0x0B, ac, 3 if with_in else 2, 0x01, 0x00, 0x20, 0])
    body = (bytes([9, 4, 0, 0, 2, 8, 6, 0x50, 0]) +
            _ep(0x81, bulk) + _ep(0x01, bulk) +
            iad_midi +
            bytes([9, 4, 1, 0, 0, 1, 1, 0, 0]) + ac_midi +
            bytes([9, 4, 2, 0, 2, 1, 3, 0, 0]) +
            _MS_CLASS +
            _ep_midi(0x02, bulk) + bytes([5, 0x25, 1, 1, 1]) +
            _ep_midi(0x82, bulk) + bytes([5, 0x25, 1, 1, 3]) +
            iad_audio +
            bytes([9, 4, ac, 0, 0, 1, 1, 0x20, 0]) + ac_audio +
            as_iface)
    total = 9 + len(body)
    hdr = bytes([9, 7 if other_speed else 2]) + struct.pack("<H", total) + bytes([6 if with_in else 5, 1, 0, 0xC0, 3])
    return hdr + body


def configs(audio=None, with_in=None):
    """`audio`: the remix's audio module key, or None for USB MIDI alone;
    `with_in`: the USB AUDIO IN module's key beside it, or None."""
    if audio:
        def f(hs, other_speed=False):
            return audio_config(hs, other_speed, audio, with_in)
    else:
        f = midi_config
    out = {"cfg_fs": f(False), "cfg_hs": f(True), "cfg_os_fs": f(False, True), "cfg_os_hs": f(True, True)}
    lengths = {len(v) for v in out.values()}
    # One clamp (cfg_len) serves all four replies: min(wLength, cfg_len). A
    # host asks for a configuration's wTotalLength, so a table shorter than
    # cfg_len is sent whole and its zero pad is never requested. Without USB
    # AUDIO IN the four are one length as they always were; with it the
    # high-speed pair carries interface 5 and the full-speed pair does not.
    if not with_in:
        assert len(lengths) == 1, "the four configurations must share one length (one clamp)"
    length = max(lengths)
    return {k: v + bytes(length - len(v)) for k, v in out.items()}, length


def remix_inc(modules):
    audio = audio_key(modules)
    with_in = in_key(modules)
    if with_in:
        assert audio, (f"{with_in} needs a USB AUDIO OUT module beside it: EP3 IN is "
                       "its implicit-feedback source")
    tables, length = configs(audio, with_in)
    what = ("USB MIDI + " + audio if audio else "USB MIDI") + (f" + {with_in}" if with_in else "")
    lines = [f"| remix.inc -- the configuration descriptors for this remix ({what}),",
             "| generated by modules/usb-midi/descriptors.py; the build rewrites it.",
             f"    .global cfg_len", f"    .set cfg_len, {length}", "",
             "    .text", "    .global cfg_fs, cfg_hs, cfg_os_fs, cfg_os_hs", ""]
    for name, blob in tables.items():
        lines.append("    .balign 4")
        lines.append(f"{name}:")
        for i in range(0, len(blob), 16):
            lines.append("    .byte " + ", ".join(f"0x{b:02x}" for b in blob[i:i + 16]))
        lines.append("")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    import sys
    print(remix_inc({"USB MIDI", "USB AUDIO OUT"} if "--audio" in sys.argv else {"USB MIDI"}))
