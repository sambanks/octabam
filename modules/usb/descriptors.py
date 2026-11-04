"""The USB configuration descriptors the responder serves, for every
runtime setting combination the unit can hold.

markandrus/octemu's `custom/usb-midi.py` and `custom/usb-audio.py`
(`config_descriptor`, MIT), as the text of USB MIDI's descriptor unit:
the build calls `remix_inc(modules, remix)` and writes it beside `cfg.s`
as `remix.inc` (schema.Linked.include). Every configuration keeps the stock
MSC interface byte for byte at the front.

The runtime settings are six checkboxes (manifest.py): TRACKS (OFF / PRE /
POST, 16 channels), MAIN (2), CUE (2), MASTER (2, track 8's L/R), IN (OFF /
AB / CD / ABCD, the host -> device stream) and MIDI (ON / OFF). Any
combination is one set of four configuration tables (fs, hs, os_fs, os_hs):

  MSC only                the stock one-interface 32-byte shape, when every
                          stream is off (no MIDI, no audio)
  + USB MIDI              + AudioControl + MIDIStreaming with EP2 bulk
                          in/out: three interfaces, 124 bytes
  + USB AUDIO OUT         a UAC2 AudioControl (clock source, input
                          terminal, USB streaming output terminal) +
                          AudioStreaming (alt 0 idle, alt 1 with the iso IN
                          EP3). Its channel count is the sum of the output
                          checkboxes: 16 for TRACKS, 2 each for MAIN, CUE,
                          MASTER, in slot order (tracks, MAIN, CUE, MASTER
                          on the wire). High speed carries them all; full
                          speed the 8-byte stereo sum (the producer's sum
                          priority: tracks > MAIN > CUE > MASTER). 24-bit
                          samples in 4-byte subslots everywhere.
  + USB AUDIO IN          the other direction beside it, at high speed: a
                          USB streaming input terminal -> line output
                          terminal, and AudioStreaming interface 5 with EP3
                          OUT (2 channels for AB/CD, 4 for ABCD, standing
                          in for inputs A/B, C/D or A-D by the IN setting).

Every set is in every image. One length `cfg_len` serves every table (each
is zero-padded to it; the responder's two clamp shims compare wLength
against the symbol, and a host never asks past a config's own
wTotalLength). `set_ptrs` is the 256 x 4-long table of pointers into the
deduplicated tables: set index = trk | main<<2 | cue<<3 | master<<4 |
in<<5 | midi<<7 (each the setting's value byte). The responder's four
sites push a pointer from it (manifest.py SELECTOR_DETOURS, the stubs in
usbaudio.s), so the served descriptors follow the six bytes at run time.

TRACKS with MASTER is refused (MASTER is track 8's L/R, which TRACKS
already carries; it was a layout from before the checkboxes, and the only
combination over 20 channels): the build refuses the resolved pair here,
the brain's SETTINGS page refuses the move, and cfgsel clears MASTER when
TRACKS is on, so a set with both serves the one without MASTER. Every
combo polls EP3 IN at bInterval 2 (250 us): at most 20 ch x 4 B x 12
frames = 960 B a poll. The EP3 OUT endpoint keeps bInterval 2 in every set
(12 x 4 B x its 2 or 4 channels is 192 B at most).

`audio_remix_inc(modules, remix)` is usbaudio.s's include: the resolved
values (usb_trk_def etc., the fallback the unit boots with when the CS1
block is invalid), the six settings' CS1 addresses, and the early block's
entries for the header sum.
"""
import struct

# 24-bit samples in 4-byte subslots. 20 ch x 4 B x 44.1 kHz is 3,528 B/ms,
# and one high-speed isochronous transaction carries at most 1,024 B, so
# the endpoint is polled every 250 us (bInterval 2): 11.025 frames x 80 B,
# at most 12 frames = 960 B a packet.
SUBSLOT, BITS = 4, 24
FS_CHANNELS, FS_MAXPKT, FS_BINTERVAL = 2, 45 * 8, 1       # 44/45 stereo frames x 8 B every 1 ms
HS_BINTERVAL = 2                                          # 250 us, every set
FRONT_LR = 0x3                                             # bmChannelConfig: front left, front right
UAC2_CLOCK_ID, UAC2_IT_ID, UAC2_OT_ID = 0x10, 0x11, 0x12
USBIN_IT_ID, USBIN_OT_ID = 0x13, 0x14

TRK_LABELS = ("OFF", "PRE", "POST")
IN_LABELS = ("OFF", "AB", "CD", "ABCD")
CH_OUT = {"TRACKS": 16, "MAIN": 2, "CUE": 2, "MASTER": 2}
IN_CH = {"AB": 2, "CD": 2, "ABCD": 4}

_DEFAULTS = (1, 1, 1, 0, 0, 1)       # TRACKS PRE, MAIN, CUE, IN OFF, MIDI (the manifest's defaults)


def _resolved(remix, mods):
    """The six setting values after the remix's layers, as (trk, main, cue,
    master, in_, midi) value bytes (an Option as its index, a Binary as
    0/1); the defaults without a remix (the include tests call with none)."""
    if remix is None:
        return _DEFAULTS
    from remix import brain
    want = dict.fromkeys(("TRACKS", "MAIN", "CUE", "MASTER", "IN", "MIDI"))
    for r, _s in brain.resolve(remix, mods):
        if r.store_id == "octabam.usb" and r.name in want:
            want[r.name] = r.value
    assert all(v is not None for v in want.values()), \
        "USB: the remix resolves no TRACKS / MAIN / CUE / MASTER / IN / MIDI (the module is selected)"
    return tuple(want[k] for k in ("TRACKS", "MAIN", "CUE", "MASTER", "IN", "MIDI"))


def _bytes(vals):
    """The six resolved values (an Option as its index, a Binary as 0/1) as
    value bytes (the set-index bits and the CS1 block's bytes)."""
    return (vals[0], vals[1], vals[2], vals[3], vals[4], vals[5])


def _early(remix, mods):
    """(base, {(store id, key): CS1 address}, [(address, size)...]) of the
    early block; (0, {}, []) without the brain or a remix. The entries are
    in early_layout's offset order, for the header sum."""
    if remix is None:
        return 0, {}, []
    from remix import brain
    if not brain.has_brain(remix):
        return 0, {}, []
    base, offs = brain.early_layout(remix, mods)
    ents = [(off, s.size) for m, s in brain.early_settings(remix, mods)
            for off in [offs.get((m.store.id, s.key), 0)] if off]
    return base, offs, ents


def _ep(addr, pkt):
    return bytes([7, 5, addr, 2]) + struct.pack("<H", pkt) + bytes([0])


def _ep_midi(addr, pkt):
    return bytes([9, 5, addr, 2]) + struct.pack("<H", pkt) + bytes(3)


_MS_CLASS = (bytes([7, 0x24, 1, 0, 1, 37, 0]) +           # MS header
             bytes([6, 0x24, 2, 1, 1, 0]) +               # IN jack, embedded 1
             bytes([6, 0x24, 2, 2, 2, 0]) +               # IN jack, external 2
             bytes([9, 0x24, 3, 1, 3, 1, 2, 1, 0]) +      # OUT jack, embedded 3
             bytes([9, 0x24, 3, 2, 4, 1, 1, 1, 0]))       # OUT jack, external 4


def msc_only_config(hs, other_speed=False):
    """MSC alone: the stock one-interface configuration, 32 bytes. Two
    endpoints, as stock's four MSC interface descriptors declare (bulk IN
    0x81, bulk OUT 0x01); 1 until 4 Nov 2026 failed USBSTOR on Windows (#1039)."""
    bulk = 512 if hs else 64
    body = (bytes([9, 4, 0, 0, 2, 8, 6, 0x50, 0]) +
            _ep(0x81, bulk) + _ep(0x01, bulk))
    total = 9 + len(body)
    hdr = bytes([9, 7 if other_speed else 2]) + struct.pack("<H", total) + bytes([1, 1, 0, 0xC0, 3])
    return hdr + body


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


def audio_config(hs, other_speed=False, nch=20, chcfg=0, in_ch=0, midi=True):
    """The MIDI composite (when midi) plus a UAC2 audio function.

    Two SEPARATE functions under interface associations, the shape of a
    device macOS accepts (his measurement against an Elektron Digitone):
    one AudioControl collecting the MIDIStreaming interface, another
    collecting the AudioStreaming one. The clock source is read-only
    (bmControls 0b01) with one rate. Read-only does not stop a host SETting
    it: the Elektron Outbox 8 sends SET CUR 44100 (a control OUT with a
    4-byte data stage), which the stock EP0 stack cannot receive; usbaudio.s
    takes it (44100 acknowledged, any other rate STALLed).

    `nch` / `chcfg`: the AudioStreaming channel count and cluster: 0 for
    any set with TRACKS in it or a mixed cluster, FRONT_LR for the 2-ch
    MAIN and MASTER sets.

    `in_ch`: 0, 2 or 4 -- at high speed, add the host -> device path (IT
    0x13 -> OT 0x14, AudioStreaming interface ii with EP3 OUT, 2 or 4
    channels) and mark EP3 IN as its implicit-feedback source. The
    full-speed configuration is the one without it. HIGH SPEED ONLY: the
    full-speed configurations carry no IN interface (the unit does not
    serve it), so a full-speed host is never offered one.

    `midi`: with the MIDI function gone the audio interfaces renumber
    (AC 3/AS 4/IN 5 -> 1/2/3); usbaudio.s's cfgsel latches the numbers the
    shims compare against.
    """
    in_ch = in_ch if hs else 0
    if hs:
        nch, chcfg = nch, chcfg
    else:
        nch, chcfg = FS_CHANNELS, chcfg            # the stereo sum
    bulk = 512 if hs else 64
    ac = 3 if midi else 1
    as_ = ac + 1
    ii = as_ + 1
    clk, it, ot = UAC2_CLOCK_ID, UAC2_IT_ID, UAC2_OT_ID
    clock = bytes([8, 0x24, 0x0A, clk, 0x01, 0x05, 0, 0])
    in_term = (bytes([17, 0x24, 0x02, it]) + struct.pack("<H", 0x0603) +
               bytes([0, clk, nch]) + struct.pack("<I", chcfg) +
               bytes([0]) + struct.pack("<H", 0) + bytes([0]))
    out_term = (bytes([12, 0x24, 0x03, ot]) + struct.pack("<H", 0x0101) +
                bytes([0, it, clk]) + struct.pack("<H", 0) + bytes([0]))
    in_path = b""
    if in_ch:
        # host -> device: a USB streaming input terminal feeding a line
        # output terminal, on the same (read-only) clock
        in_cfg = FRONT_LR if in_ch == 2 else 0
        in_path = (bytes([17, 0x24, 0x02, USBIN_IT_ID]) + struct.pack("<H", 0x0101) +
                   bytes([0, clk, in_ch]) + struct.pack("<I", in_cfg) +
                   bytes([0]) + struct.pack("<H", 0) + bytes([0]) +
                   bytes([12, 0x24, 0x03, USBIN_OT_ID]) + struct.pack("<H", 0x0603) +
                   bytes([0, USBIN_IT_ID, clk]) + struct.pack("<H", 0) + bytes([0]))
    ac_audio_total = 9 + len(clock) + len(in_term) + len(out_term) + len(in_path)
    ac_audio = (bytes([9, 0x24, 1]) + struct.pack("<H", 0x0200) + bytes([0x0A]) +
                struct.pack("<H", ac_audio_total) + bytes([0]) + clock + in_term + out_term + in_path)
    # EP3 IN: 12 x the frame bytes a 250 us poll (at most 20 ch: 960 B)
    fb = 4 * nch
    if hs:
        assert 12 * fb <= 1024, f"{nch} channels do not fit a 250 us poll"
        maxpkt, bint = 12 * fb, HS_BINTERVAL
    else:
        maxpkt, bint = FS_MAXPKT, FS_BINTERVAL
    as_iface = (
        bytes([9, 4, as_, 0, 0, 1, 2, 0x20, 0]) +
        bytes([9, 4, as_, 1, 1, 1, 2, 0x20, 0]) +
        bytes([16, 0x24, 1, ot, 0, 1]) + struct.pack("<I", 1) +
        bytes([nch]) + struct.pack("<I", chcfg) + bytes([0]) +
        bytes([6, 0x24, 2, 1, SUBSLOT, BITS]) +
        # bmAttributes: isochronous, asynchronous; + usage "implicit
        # feedback data" (bits 5:4 = 10) when USB AUDIO IN pairs with it
        bytes([7, 5, 0x83, 0x25 if in_ch else 0x05]) + struct.pack("<H", maxpkt) +
        bytes([bint]) +
        bytes([8, 0x25, 1, 0, 0, 0]) + struct.pack("<H", 0))
    if in_ch:
        as_iface += (
            bytes([9, 4, ii, 0, 0, 1, 2, 0x20, 0]) +
            bytes([9, 4, ii, 1, 1, 1, 2, 0x20, 0]) +
            bytes([16, 0x24, 1, USBIN_IT_ID, 0, 1]) + struct.pack("<I", 1) +
            bytes([in_ch]) + struct.pack("<I", FRONT_LR if in_ch == 2 else 0) + bytes([0]) +
            bytes([6, 0x24, 2, 1, SUBSLOT, BITS]) +
            bytes([7, 5, 0x03, 0x05]) +                      # iso, asynchronous, data
            struct.pack("<H", 12 * in_ch * SUBSLOT) +       # 96 B for a pair, 192 for four
            bytes([HS_BINTERVAL]) +
            bytes([8, 0x25, 1, 0, 0, 0]) + struct.pack("<H", 0))
    body = bytes([9, 4, 0, 0, 2, 8, 6, 0x50, 0]) + \
        _ep(0x81, bulk) + _ep(0x01, bulk)
    if midi:
        ac_midi = bytes([9, 0x24, 1, 0, 1]) + struct.pack("<H", 9) + bytes([1, 2])
        iad_midi = bytes([8, 0x0B, 1, 2, 0x01, 0x00, 0x00, 0])
        body += (iad_midi +
                 bytes([9, 4, 1, 0, 0, 1, 1, 0, 0]) + ac_midi +
                 bytes([9, 4, 2, 0, 2, 1, 3, 0, 0]) +
                 _MS_CLASS +
                 _ep_midi(0x02, bulk) + bytes([5, 0x25, 1, 1, 1]) +
                 _ep_midi(0x82, bulk) + bytes([5, 0x25, 1, 1, 3]))
    iad_audio = bytes([8, 0x0B, ac, 3 if in_ch else 2, 0x01, 0x00, 0x20, 0])
    body += (iad_audio +
             bytes([9, 4, ac, 0, 0, 1, 1, 0x20, 0]) + ac_audio +
             as_iface)
    # MSC + (AC + MS with MIDI) + AC + AS (+ the IN AS): 3 or 4 without MIDI, 5 or 6 with it
    # (2 or 3 without MIDI until 4 Nov 2026, one short: #1039's check found it)
    nif = (6 if in_ch else 5) if midi else (4 if in_ch else 3)
    total = 9 + len(body)
    hdr = bytes([9, 7 if other_speed else 2]) + struct.pack("<H", total) + bytes([nif, 1, 0, 0xC0, 3])
    return hdr + body


def _chcfg(trk, main, cue, master):
    """The cluster for the combo: 0 with TRACKS in the stream or a mixed
    cluster; FRONT_LR for the 2-ch MAIN and MASTER sets."""
    if trk:
        return 0
    nch = 2 * (main + cue + master)
    if nch == 2 and (main or master):
        return FRONT_LR
    return 0


def _set_tables(trk, main, cue, master, in_, midi):
    """The four configs (fs, hs, os_fs, os_hs) of one value-byte
    combination. IN without an output stream is unreachable (the brain's
    pair rule and cfgsel's guard both refuse it): its row serves the
    no-audio config of the same MIDI value. TRACKS with MASTER is
    unreachable too (refused the same three ways): its row serves the set
    without MASTER."""
    if trk:
        master = 0
    nch = 16 * (trk != 0) + 2 * (main + cue + master)
    if nch == 0:
        f = (lambda hs, other_speed=False:
             midi_config(hs, other_speed) if midi else msc_only_config(hs, other_speed))
    else:
        in_ch = IN_CH[IN_LABELS[in_]] if in_ else 0
        chcfg = _chcfg(trk, main, cue, master)
        f = lambda hs, other_speed=False: audio_config(hs, other_speed, nch, chcfg, in_ch, midi)
    return [f(False), f(True), f(False, True), f(True, True)]


def check_config(cfg):
    """Refuse a configuration descriptor whose counts disagree with what
    follows: wTotalLength with its length, bNumInterfaces with the distinct
    interface numbers, and each interface descriptor's bNumEndpoints with the
    endpoint descriptors before the next interface descriptor (class-specific
    endpoint descriptors, type 0x25, are not endpoints). A host trusts the
    counts: Windows' USBSTOR failed with Code 10 on an MSC interface that
    declared one endpoint and was followed by two (#1039). Returns cfg."""
    if len(cfg) < 9 or cfg[0] != 9 or cfg[1] not in (2, 7):
        raise ValueError(f"USB config: no configuration header ({cfg[:9].hex()})")
    total, nif = cfg[2] | cfg[3] << 8, cfg[4]
    if total != len(cfg):
        raise ValueError(f"USB config: wTotalLength {total}, but {len(cfg)} bytes")
    i, ifaces, cur = 9, set(), None      # cur: [interface, alt, declared, counted]
    found = []
    while i < len(cfg):
        n, t = cfg[i], cfg[i + 1] if i + 1 < len(cfg) else None
        if n < 2 or i + n > len(cfg):
            raise ValueError(f"USB config: descriptor at {i} has length {n} past the end")
        if t == 4:
            if cur:
                found.append(cur)
            cur = [cfg[i + 2], cfg[i + 3], cfg[i + 4], 0]
            ifaces.add(cfg[i + 2])
        elif t == 5:
            if cur is None:
                raise ValueError(f"USB config: endpoint 0x{cfg[i + 2]:02x} before any interface")
            cur[3] += 1
        i += n
    if cur:
        found.append(cur)
    for num, alt, declared, counted in found:
        if declared != counted:
            raise ValueError(f"USB config: interface {num} alt {alt} declares {declared} "
                             f"endpoint(s), {counted} follow")
    if nif != len(ifaces):
        raise ValueError(f"USB config: bNumInterfaces {nif}, but {len(ifaces)} interfaces")
    return cfg


def _blob():
    """All 256 sets: every table zero-padded to one cfg_len, deduplicated
    (AB and CD share a set; every audio set shares its full-speed pair),
    with the 256 x 4-long pointer table in front. Returns (cfg_len, rows,
    pointer table) where rows is label -> bytes."""
    sets = [_set_tables(i & 3, (i >> 2) & 1, (i >> 3) & 1, (i >> 4) & 1, (i >> 5) & 3, (i >> 7) & 1)
            for i in range(256)]
    for i, s in enumerate(sets):       # every table of every set, before padding (#1039)
        for which, t in zip(("fs", "hs", "os_fs", "os_hs"), s):
            try:
                check_config(t)
            except ValueError as e:
                raise ValueError(f"set {i} ({which}): {e}") from None
    length = max(len(t) for s in sets for t in s)
    tables, ptrs = {}, []
    for s in sets:
        row = []
        for t in s:
            t = t + bytes(length - len(t))
            if t not in tables:
                tables[t] = f"t{len(tables)}"
            row.append(tables[t])
        ptrs.append(row)
    return length, tables, ptrs


def remix_inc(modules, remix):
    """cfg.s's remix.inc: the blob, the pointer table and `cfg_len`. The
    resolved IN-without-an-output pair is refused here (EP3 IN is the
    implicit-feedback source)."""
    trk, main, cue, master, in_, midi = _resolved(remix, modules)
    if in_ and not (trk or main or cue or master):
        raise ValueError(f"USB: IN {IN_LABELS[in_]} needs an output stream beside it: EP3 IN is "
                         "its implicit-feedback source")
    if trk and master:
        raise ValueError("USB: TRACKS and MASTER cannot both be on: MASTER is track 8's L/R, "
                         "which TRACKS already carries")
    length, tables, ptrs = _blob()
    lines = ["| remix.inc -- every configuration of every setting combination,",
             "| generated by modules/usb/descriptors.py; the build rewrites it.",
             f"    .global cfg_len", f"    .set cfg_len, {length}",
             f"    .set SET_STRIDE, {length}", "    .set SETS_N, 256", "",
             "| the 256 sets: set index = trk | main<<2 | cue<<3 | master<<4 |",
             "| in<<5 | midi<<7; each row is that set's fs, hs, os_fs, os_hs table",
             "    .text", "    .balign 4", "    .globl  set_ptrs", "set_ptrs:"]
    for row in ptrs:
        lines.append("    .long   " + ", ".join(row))
    lines += ["", "| the tables, deduplicated, each SET_STRIDE bytes (a host never",
              "| asks past a config's own wTotalLength)"]
    for blob, label in sorted(tables.items(), key=lambda kv: kv[1]):
        lines += ["    .balign 4", f"{label}:"]
        for i in range(0, len(blob), 16):
            lines.append("    .byte " + ", ".join(f"0x{b:02x}" for b in blob[i:i + 16]))
        lines.append("")
    return "\n".join(lines) + "\n"


def audio_remix_inc(modules, remix):
    """usbaudio.s's remix.inc: the resolved values (the fallback the unit
    boots with when the CS1 block is invalid), the six settings' CS1
    addresses, the block's base and the entries for the header sum."""
    b = _bytes(_resolved(remix, modules))
    base, offs, ents = _early(remix, modules)
    names = ("TRK", "MAIN", "CUE", "MASTER", "IN", "MIDI")
    lines = ["| remix.inc -- usbaudio.s's runtime knobs (modules/usb/descriptors.py)"]
    for n, v in zip(("trk", "main", "cue", "master", "in", "midi"), b):
        lines.append(f"    .set usb_{n}_def, {v}")
    for n, key in zip(names, range(7, 13)):
        at = offs.get(('octabam.usb', key))
        lines.append(f"    .set CS1_USB_{n}, {-1 if at is None else at - base}")   # -1: fixed in the image (pinned)
    lines += ["| the CS1 early block's base (remix.brain.early_layout; 0 = no brain,",
              "| cfgsel takes the resolved defaults and never re-reads)",
              "    .globl  usb_cs1_base",
              f"usb_cs1_base: .long {base}",
              "| the CS1 early block's entries as (offset from usb_cs1_base, size)",
              "| long pairs, 0-terminated: the block header's sum is over these",
              "| value bytes (brain.c write_early_block)",
              "    .globl  cs1_early_ents",
              "cs1_early_ents:"]
    for off, size in ents:
        lines.append(f"    .long   {off - base}, {size}")
    lines.append("    .long   0")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    length, tables, ptrs = _blob()
    print(f"cfg_len {length}  tables {len(tables)}  sets {len(ptrs)}")
    for i, row in enumerate(ptrs):
        print(f"set {i:3d}: {row}")
