#!/usr/bin/env python3
"""Enumerate the image just built as a USB device under the ColdFire port.

Boots out/mainos_bus.bin with the device-controller model and its bench
(tools/emu/ot_emu/usb.h), then acts as the host: bus reset, GET_DESCRIPTOR,
SET_ADDRESS, SET_CONFIGURATION, a mass-storage INQUIRY and TEST UNIT READY
over EP1. The firmware's own USB stack answers every step, so this checks:

  * the stock control path is intact in the built image (a module that
    moves a descriptor table, hooks the ISR or grows a configuration shows
    up here as a wrong VID/PID, a short config or a hang);
  * the model's queue-head and transfer-descriptor walk agrees with what
    the firmware builds (the INQUIRY data + CSW chain, both directions);
  * no primed queue head was left uninitialised (the defect that crashed a
    unit under octemu's USB-audio payload).

SKIPs when the port is not built (`make emu-cf`). What this cannot see:
timing (the port serialises the host's polls against the frame interrupt)
and anything a real host does beyond these requests.
"""
import os
import pathlib
import re
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
import usb_host  # noqa: E402  (tools/harness)

from remix import registry, brain  # noqa: E402

EMU = ROOT / "out/emu/ot_emu"
IMAGE = ROOT / "out/mainos_bus.bin"
MIDI_FIFO_HEAD = 0x46100b80         # midi_rx_fifo_head: +1 per byte midi_rx_enqueue (0x40092bbc) takes

# The servo's target, from the source, so the checks follow it.
AUD_TARGET = int(re.search(r"^\.set AUD_TARGET,\s+(\d+)", (ROOT / "modules/usb/usbaudio.s").read_text(), re.M).group(1))
RB_BASE, MAIN_CUE_BASE = 0x80003190, 0x80005e60   # the tracks' read-back arena (2 banks) and MAIN/CUE (usbaudio.s)

# The six runtime settings (modules/usb/manifest.py): TRACKS OFF/PRE/POST,
# MAIN / CUE / MASTER / MIDI on/off, IN OFF/AB/CD/ABCD. The stream is
# nch = 16 x [TRACKS on] + 2 x (MAIN + CUE + MASTER) channels in slot order
# (tracks, MAIN, CUE, MASTER on the wire). High speed carries them all: at
# most 12 frames of 4 x nch bytes per 250 us poll (1,024 B a transaction);
# the 22-channel combos poll at 125 us (bInterval 1), 6 frames = 528 B.
# Full speed carries the 8-byte stereo sum (priority tracks > MAIN > CUE >
# MASTER) in 1 ms packets. Source 0-7 = track 1-8's read-back words, 8 =
# MAIN, 9 = CUE; MASTER re-reads track 8's words.
TRK_LABELS = ("OFF", "PRE", "POST")
IN_LABELS = ("OFF", "AB", "CD", "ABCD")
IN_CH = {"AB": 2, "CD": 2, "ABCD": 4}
CH_OUT = {"TRACKS": 16, "MAIN": 2, "CUE": 2, "MASTER": 2}


def geom(trk, main, cue, master):
    """(nch, maxpkt, bInterval) of the output combo, as usbaudio.s's cfgsel
    and descriptors.py's audio_config compute them."""
    nch = CH_OUT["TRACKS"] * (trk != 0) + 2 * (main + cue + master)
    if nch == 0:
        return 0, 0, 2
    return nch, 12 * 4 * nch, 2            # 20 channels at most (TRACKS with MASTER is refused): 960 B


def wire_taps(trk, main, cue, master):
    """What each channel carries, in wire order (the slot order)."""
    taps = []
    if trk:
        taps += [(t, c) for t in range(8) for c in (0, 1)]
    if main:
        taps += [(8, 0), (8, 1)]
    if cue:
        taps += [(9, 0), (9, 1)]
    if master:
        taps += [(7, 0), (7, 1)]
    return taps


def chcfg(trk, main, cue, master):
    """The AS_GENERAL cluster (descriptors.py _chcfg): FRONT_LR for the
    2-ch MAIN and MASTER sets, 0 for CUE-only and every mixed set."""
    return 3 if not trk and main + cue + master == 1 and (main or master) else 0


def tap_word(src, lr, frame):
    """A read-back word that names its source, side and frame; the producer
    keeps the top 24 bits."""
    return ((0x10 + src) << 24) | ((0x20 + lr) << 16) | ((0x30 + frame) << 8) | 0x77


# Tracks 0-6 only: the stock frame routine's echo-freeze mix rewrites arena
# region 7 (the track-8 block of both banks -- the producer's t7 and MASTER
# read it) every frame from its own staging at 0x800039a0/0x80003a40, so that
# block and the staging are poked zero: zero in, zero out, and the wire's
# t7/MASTER channels must read 0.
TAP_RB = b"".join((0 if t == 7 else tap_word(t, c, f)).to_bytes(4, "big")
                  for _bank in range(2) for t in range(8) for f in range(16) for c in (0, 1))
TAP_RB += bytes(0x80003ad0 - 0x800039a0)   # the mix's staging, 0x800039a0..0x80003acf
TAP_MC = b"".join(tap_word(8 + k, c, f).to_bytes(4, "big") for k in (0, 1) for f in range(16) for c in (0, 1))

# USB AUDIO OUT TRACKS POST multiplies each track by its own MAIN gain, so a
# word cannot name its source: the taps are amplitudes instead, source k =
# 2t + c at (k + 1) << 17, and every track's gain at the boot defaults (LEVEL
# 108, nothing muted or soloed, XLV unlocked once the crossfader's weights
# exist) is one G. Channel k then carries floor(g (k + 1) / 16) with g within
# 15 of G (core 0's ramp settles up to 15 below its target), ranges far apart.
POST_TAP = lambda k: (k + 1) << 17
TAP_RB_POST = b"".join((0 if t == 7 else (POST_TAP(t * 2 + c) << 8)).to_bytes(4, "big", signed=True)
                       for _bank in range(2) for t in range(8) for f in range(16) for c in (0, 1))
TAP_RB_POST += bytes(0x80003ad0 - 0x800039a0)
XFADE_WEIGHTS, XFADE_64 = 0x80003c60, bytes.fromhex("bf7fc081") * 10   # the crossfader at 64: unlocked XLV = 0x7f00


def post_g_default():
    """G for the boot defaults (MAIN word 0x6c00, XLV 0x7f00), as the unit's
    post_frame computes it, from the XLV table the build extracts."""
    import importlib.util
    sys.path.insert(0, str(ROOT / "tools/harness"))
    import usb_post_model
    spec = importlib.util.spec_from_file_location("usb_manifest", ROOT / "modules/usb/manifest.py")
    man = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(man)
    return usb_post_model.target(0x6c00, 0x7f00, man.xlv_table())


def early_block(remix, mods):
    """(base, [(module, Setting, CS1 offset)], {id(Setting): Resolved}) of the
    CS1 early block the runtime rows write (brain.early_layout)."""
    base, offs = brain.early_layout(remix, mods)
    early = [(m, s, offs.get((m.store.id, s.key))) for m, s in brain.early_settings(remix, mods)]
    resolved = {id(s): r for r, s in brain.resolve(remix, mods)}
    return base, early, resolved


def cs1_boot(image):
    """CS1 as `image`'s boot leaves it with no CS1 file: the boot finds no
    valid settings tail, wipes CS1 and writes its defaults (584,212 non-zero
    bytes on octabam-bus, 16 Oct 2026). Cached per image hash under out/."""
    import hashlib
    path = pathlib.Path(image)
    out = ROOT / f"out/cs1_boot_{hashlib.sha256(path.read_bytes()).hexdigest()[:12]}.bin"
    if not out.is_file():
        tmp = out.with_suffix(".part")
        subprocess.run([str(EMU), "--image", str(path), "--frames", "50",
                        "--mem-dump", f"0x10000000,0x100000={tmp}"],
                       cwd=ROOT, check=True, capture_output=True)
        tmp.rename(out)
    return out.read_bytes()


def has_early_slot(early):
    """True when some early setting has a CS1 offset: a remix whose USB settings are all
    fixed values or pins has `early` entries without one, and no block to write."""
    return any(at is not None for _m, _s, at in early)


def _cs1_lay(cs1, base, early, resolved, overrides):
    """The early block into `cs1` (a bytearray from 0x10000000)."""
    cs1[base - 0x10000000] = 0xea
    cs1[base - 0x10000000 + 1] = 1
    total = 0
    for m_, s_, at in early:
        if at is None:
            continue
        if m_.store.id == "octabam.usb" and s_.name in overrides:
            v = overrides[s_.name]
        else:
            r = resolved.get(id(s_))
            v = r.value if r else 0
        total += v & ((1 << (8 * s_.size)) - 1)
        cs1[at - 0x10000000:at - 0x10000000 + s_.size] = v.to_bytes(s_.size, "big", signed=True)
    cs1[base - 0x10000000 + 2] = (total & 0xffff) >> 8
    cs1[base - 0x10000000 + 3] = total & 0xff


def cs1_block(base, early, resolved, overrides, template=None):
    """The CS1 early block bytes holding `overrides` ({name: value} on
    octabam.usb settings) and every other early setting's resolved value:
    magic 0xea, version 1, then the 16-bit big-endian sum of the value bytes
    (cfgsel's header check), then each entry's bytes at its offset.
    `template` (cs1_boot) is CS1 after a boot: the block is laid over it and
    its settings tail is kept, so stock's own settings hold their defaults
    (a zero CS1 with a valid tail boots them as zeros: input gain 0)."""
    if template is not None:
        cs1 = bytearray(template)
        _cs1_lay(cs1, base, early, resolved, overrides)
        return bytes(cs1)
    cs1 = bytearray(max(at for _, _, at in early if at is not None) - 0x10000000 + 1)
    _cs1_lay(cs1, base, early, resolved, overrides)
    # The boot wipes ALL of CS1 (0x10000000..0x100ffeff) when the settings
    # tail is invalid: the checksum long at 0x100fff00 over 0x100fff04..
    # 0x100fffff and the version word 36 at 0x100fff0e (the clrl loops at
    # 0x4001fa76 and 0x4001faae). A wipe would take the early block with it
    # and cfgsel would serve the baked defaults. A valid tail models a unit
    # whose settings store survived power-off -- the boot leaves CS1 alone.
    # The tail is the boot's own re-init shape (0x4001f298): "ANDY", 100,
    # word 3, word 36, zeros, long 2 at +0x5c; the checksum is byte i XOR i
    # for i in 1..252, summed, + 514 (0x4001f306), a big-endian long.
    cs1 += bytes(0x100000 - len(cs1))
    cs1[0xFFF04:0xFFF08] = b"ANDY"
    cs1[0xFFF08:0xFFF0C] = (100).to_bytes(4, "big")
    cs1[0xFFF0C:0xFFF0E] = (3).to_bytes(2, "big")
    cs1[0xFFF0E:0xFFF10] = (36).to_bytes(2, "big")
    cs1[0xFFF60:0xFFF64] = (2).to_bytes(4, "big")
    cs1[0xFFF00:0xFFF04] = (514 + sum(cs1[0xFFF04 + i] ^ (i + 1) for i in range(252))).to_bytes(4, "big")
    return bytes(cs1)


def main():
    if not EMU.is_file():
        print("  [SKIP] verify_usb: the port is not built (make emu-cf)")
        return 0
    if not IMAGE.is_file():
        print("  [FAIL] verify_usb: no out/mainos_bus.bin (make bus)")
        return 1
    remix = registry.remix(os.environ.get("REMIX"))
    mods = registry.modules()
    usb = "USB" in remix.modules
    get = lambda n: brain.value(remix, mods, "octabam.usb", n) if usb else None
    trk_v, main_v, cue_v, master_v, in_v, midi_v = (get(n) for n in ("TRACKS", "MAIN", "CUE", "MASTER", "IN", "MIDI"))
    trk = TRK_LABELS.index(trk_v) if trk_v else 0
    main = main_v or 0
    cue = cue_v or 0
    master = master_v or 0
    inp = IN_LABELS.index(in_v) if in_v else 0
    midi = usb and midi_v == 1
    nch, maxpkt, bint = geom(trk, main, cue, master)
    audio = nch > 0
    ain = in_v if in_v != "OFF" else None          # + AudioStreaming ii, EP3 OUT (implicit feedback)
    in_ch = IN_CH[ain] if ain else 0
    ac = 3 if midi else 1                          # the audio AC/AS/IN interface numbers (cfgsel)
    as_ = ac + 1
    ii = as_ + 1
    if audio:
        nif = (6 if in_ch else 5) if midi else (4 if in_ch else 3)   # MSC, AC, AS (+ IN AS); #1039
    else:
        nif = 3 if midi else 1
    sock = f"/tmp/ot-usb-{os.getpid()}.sock"     # sun_path is 104 bytes on macOS; the scratch dirs are longer
    log = ROOT / "out/verify_usb.log"
    with open(log, "w") as lf:
        # --frame: the audio producer runs from the frame interrupt, which
        # the port leaves off unless asked (no card, no transport: the
        # tracks are silent, the stream is not).
        emu = subprocess.Popen([str(EMU), "--image", str(IMAGE), "--usb-host", sock, "--usb-hold-ms", "120000",
                                "--watch-mem", ";".join([f"{MIDI_FIFO_HEAD:#x},4", "0x40ad342c,4",
                                                           "0x40aeb438,1", "0x800000e4,4"])]
                               + (["--frame"] if audio else []),
                               cwd=ROOT, stdout=lf, stderr=subprocess.STDOUT)
    fails = []
    stalls_expected = 0     # EP0 STALLs this gate elicits on purpose (SET CUR of an unoffered rate)

    def check(what, ok, detail=""):
        print(f"  [{'PASS' if ok else 'FAIL'}] {what}{'  ' + detail if detail else ''}")
        if not ok:
            fails.append(what)

    try:
        b = usb_host.Bench(sock, timeout=60.0)
        dev, cfg = usb_host.enumerate_device(b, hs=True)
        vid, pid = dev[8] | dev[9] << 8, dev[10] | dev[11] << 8
        check("device descriptor: Elektron 1935:0002, USB 2.00", (vid, pid, dev[2], dev[3]) == (0x1935, 0x0002, 0x00, 0x02),
              f"got {vid:04x}:{pid:04x} bcdUSB {dev[3]:x}.{dev[2]:02x}")
        ifaces = [d for t, d in usb_host.descriptors(cfg) if t == 4]
        eps = [d for t, d in usb_host.descriptors(cfg) if t == 5]
        msc = [d for d in ifaces if d[5:8] == bytes([8, 6, 0x50])]
        check("a mass-storage SCSI/BOT interface is in the configuration", len(msc) == 1,
              f"{len(ifaces)} interface(s), {len(cfg)} bytes")
        bulk = sorted((d[2], d[3] & 3, d[4] | d[5] << 8) for d in eps if d[2] in (0x81, 0x01))
        check("EP 0x81/0x01 bulk, 512 bytes at high speed", bulk == [(0x01, 2, 512), (0x81, 2, 512)], str(bulk))
        ok = usb_host.msc_test(b)
        check("INQUIRY answers 36 bytes with a good CSW", ok)
        if midi:
            ms = [d for d in ifaces if d[5:7] == bytes([1, 3])]
            acm = [d for d in ifaces if d[5:8] == bytes([1, 1, 0])]    # the MIDI function's (the audio one is protocol 0x20)
            check("USB MIDI: an AudioControl and a MIDIStreaming interface follow the MSC one",
                  len(acm) == 1 and len(ms) == 1 and cfg[4] == nif, f"bNumInterfaces {cfg[4]}")
            ep2 = sorted((d[2], d[3] & 3, d[4] | d[5] << 8) for d in eps if d[2] in (0x82, 0x02))
            check("USB MIDI: EP 0x82/0x02 bulk, 512 bytes", ep2 == [(0x02, 2, 512), (0x82, 2, 512)], str(ep2))
            # receive: two channel messages in -> six bytes through midi_rx_enqueue (the log's watch)
            usb_host.midi_send(b, bytes.fromhex("903c64b03c40"))
            # transmit: the firmware's own midi_send on a message in its staging buffer -> one event packet out
            raw = bytes([0x90, 0x3c, 0x64])
            b.poke(0x400d807c, raw)
            b.call(0x40010bc8, len(raw), 0x400d807c)
            pk = usb_host.midi_recv(b, 2.0)
            check("USB MIDI: midi_send reaches EP2 IN as one event packet", bytes([0x09]) + raw in pk, str([p.hex() for p in pk]))
        elif usb:
            check("USB MIDI OFF: no MIDI interfaces" + ("; the audio interfaces renumber to 1/2/3" if audio else ""),
                  cfg[4] == nif, f"bNumInterfaces {cfg[4]}")
        else:
            check("stock: one interface only", cfg[4] == 1, f"bNumInterfaces {cfg[4]}")
        if audio:
            check("USB AUDIO: the device descriptor is the interface-association composite", dev[4:7] == bytes([0xef, 2, 1]), dev[4:7].hex())
            asn = as_                                   # the AS interface number (cfgsel): 4 with MIDI, 2 without
            asl = [d for d in ifaces if d[5:7] == bytes([1, 2])]
            check("USB AUDIO: a UAC2 AudioStreaming interface " + str(asn) + " with alt 0 and alt 1" + (", and " + str(ii) + " (IN)" if ain else ""),
                  sorted((d[2], d[3]) for d in asl) == [(asn, 0), (asn, 1)] + ([(ii, 0), (ii, 1)] if ain else []),
                  str([(d[2], d[3]) for d in asl]))
            frame_b = 4 * nch
            per = (10, 11, 12) if bint == 2 else (5, 6)     # frames per packet the servo can send
            iso = [d for d in eps if d[2] == 0x83]
            if iso:                                              # poll at the rate the descriptor asks for
                b.iso_hz(8000 // (1 << (iso[0][6] - 1)))
            check(f"USB AUDIO: EP 0x83 isochronous, {maxpkt} bytes, bInterval {bint}",
                  len(iso) == 1 and (iso[0][3] & 3, iso[0][4] | iso[0][5] << 8, iso[0][6]) == (1, maxpkt, bint),
                  str([(d[3], d[4] | d[5] << 8, d[6]) for d in iso]))
            if ain:
                check(f"USB AUDIO: EP 0x83 marked implicit-feedback data (EP3 OUT's feedback source)",
                      len(iso) == 1 and (iso[0][3] >> 4 & 3) == 2, str([hex(d[3]) for d in iso]))
                ison = [d for d in eps if d[2] == 0x03]
                check(f"USB AUDIO: EP 0x03 isochronous asynchronous data, {12 * 4 * in_ch} bytes, bInterval 2",
                      len(ison) == 1 and (ison[0][3], ison[0][4] | ison[0][5] << 8, ison[0][6]) == (0x05, 12 * 4 * in_ch, 2),
                      str([(d[3], d[4] | d[5] << 8, d[6]) for d in ison]))
                asg_i = cfg.find(bytes([16, 0x24, 1, 0x13]))     # AS_GENERAL linked to the host -> device input terminal
                check(f"USB AUDIO: AS_GENERAL declares {in_ch} channels" + (", front left + front right" if in_ch == 2 else ""),
                      asg_i >= 0 and cfg[asg_i + 10] == in_ch and cfg[asg_i + 11] == (3 if in_ch == 2 else 0),
                      f"bNrChannels {cfg[asg_i + 10] if asg_i >= 0 else None}")
                # the full-speed configuration (served as OTHER_SPEED at high
                # speed) carries no interface ii: the unit serves it at high speed only
                ocfg = b.ctrl_in(0x80, 6, 0x0700, 0, 512)
                check(f"USB AUDIO: no interface {ii} in the other-speed (full-speed) configuration",
                      len(ocfg) >= 9 and ocfg[4] == (5 if midi else 3) and bytes([16, 0x24, 1, 0x13]) not in ocfg,
                      f"bNumInterfaces {ocfg[4] if len(ocfg) >= 9 else None}")
            asg = cfg.find(bytes([16, 0x24, 1]))                 # CS AS_GENERAL: bNrChannels at +10, bmChannelConfig +11
            check(f"USB AUDIO: AS_GENERAL declares {nch} channels",
                  asg >= 0 and cfg[asg + 10] == nch, f"bNrChannels {cfg[asg + 10] if asg >= 0 else None}")
            if nch == 2:
                cc = int.from_bytes(cfg[asg + 11:asg + 15], "little") if asg >= 0 else None
                check(f"USB AUDIO: AS_GENERAL bmChannelConfig = {hex(chcfg(trk, main, cue, master))}",
                      cc == chcfg(trk, main, cue, master), f"{cc}")
            fmt24, fmt16 = bytes([6, 0x24, 2, 1, 4, 24]), bytes([6, 0x24, 2, 1, 2, 16])   # FORMAT_TYPE_I: subslot, bits
            check("USB AUDIO: FORMAT_TYPE_I, 24-bit samples in 4-byte subslots",
                  cfg.count(fmt24) == (2 if ain else 1) and fmt16 not in cfg)
            # the clock source answers its sample rate; SET_INTERFACE alt 1 brings EP3 up
            cur = b.ctrl_in(0xa1, 1, 0x0100, 0x1000 | 3, 4)
            check("USB AUDIO: CS_SAM_FREQ_CONTROL CUR = 44100", cur == (44100).to_bytes(4, "little"), cur.hex())
            # SET CUR of the (fixed, read-only) rate: some UAC2 hosts send it
            # with the rate they have just read and give the audio function up
            # if it STALLs (the Elektron Outbox 8: modules/usb/README.md).
            # 44100 is acknowledged; any other rate STALLs the status stage.
            # Before the fix the stock handler STALLed only EP0 IN, so the
            # data stage was never accepted and the host timed out.
            def set_cur_freq(rate):
                b.setup(0x21, 1, 0x0100, 0x1000 | 3, 4)
                try:
                    b.ep_out(0, rate.to_bytes(4, "little"), timeout=10.0)   # a data-stage STALL raises
                except TimeoutError:
                    return "data stage never accepted (timeout)"
                try:
                    b.ep_in(0, 64)                          # status stage
                    return "ACK"
                except usb_host.Stall:
                    return "status STALL"
            for rate, want in ((44100, "ACK"), (48000, "status STALL")):
                stalls_expected += want == "status STALL"
                try:
                    got = set_cur_freq(rate)
                except usb_host.Stall as e:
                    got = f"data-stage STALL ({e})"
                check(f"USB AUDIO: SET CUR sample frequency {rate} -> {want}", got == want, got)
                cur = b.ctrl_in(0xa1, 1, 0x0100, 0x1000 | 3, 4)
                check(f"USB AUDIO: EP0 answers after SET CUR {rate} (CUR = 44100)",
                      cur == (44100).to_bytes(4, "little"), cur.hex())
            b.ctrl_nodata(0x01, 0x0b, 1, asn)
            alt = b.ctrl_in(0x81, 0x0a, 0, asn, 1)
            check("USB AUDIO: GET_INTERFACE reports alt 1", alt == b"\x01", alt.hex())
            got = [b.ep_in(3, 1024) for _ in range(800)]        # 200 ms of device time at the endpoint's poll rate
            sizes = sorted({len(g) for g in got[10:]})           # the first polls may land before the first prime
            check(f"USB AUDIO: 800 polls on EP3 carry {per[0]}-{per[-1]}-frame packets of {frame_b} B and none empty after the first ten",
                  bool(sizes) and all(s in [n * frame_b for n in per] for s in sizes), f"sizes {sizes}")
            words = b"".join(got[10:])
            low = sum(1 for i in range(0, len(words), 4) if words[i])
            check("USB AUDIO: every 4-byte subslot's low byte is zero (24 bits, left-justified)",
                  bool(words) and low == 0, f"{low} of {len(words) // 4} subslots")
            c = usb_host.counters(b)
            print("  counters: " + " ".join(f"{k}={v}" for k, v in c.items()))
            # An overrun is the ring lapping a host that stopped draining. The
            # port holds device time for the bench's next IN (usb.h, isoPoll),
            # so a slow bench never shows as one.
            check("USB AUDIO: the vendor request reads the counters back: frames produced and consumed, no overrun",
                  c["produced"] > c["consumed"] > 0 and c["overruns"] == 0,
                  f"produced {c['produced']} consumed {c['consumed']} overruns {c['overruns']} underruns {c['underruns']} bankdup {c['bankdup']}")
            # (after the counters: re-poking between polls slows the bench's
            # polling, and the port counts the polls it skips as overruns)
            # Which taps stream: the read-back arena (both banks) and MAIN/CUE
            # re-poked before every poll with words naming their source, so
            # the producer reads them whichever bank the eDMA left it (the
            # eDMA rewrites the current bank each frame). Every channel must
            # carry only its own source's words, and every source it should --
            # except t7/MASTER: region 7 is the stock mix's block, poked zero
            # and expected zero (TAP_RB above).
            taps = wire_taps(trk, main, cue, master)
            tapped = []
            post = trk_v == "POST"
            if post:
                b.poke(XFADE_WEIGHTS, XFADE_64)
            for _ in range(1200):
                b.poke(RB_BASE, TAP_RB_POST if post else TAP_RB)
                b.poke(MAIN_CUE_BASE, TAP_MC)
                tapped.append(b.ep_in(3, 1024))
            tw = [int.from_bytes(w[i:i + 4], "little") for w in tapped[-400:] for i in range(0, len(w), 4)]
            seen, wrong = [0] * nch, []
            if post:
                g = post_g_default()
                band = [((g - 15) * (k + 1) >> 4, g * (k + 1) >> 4) for k in range(16)]
            for i, w in enumerate(tw):
                pos = i % nch
                if taps[pos][0] == 7:      # t7/MASTER: region 7 is the mix's; zero poked -> zero expected
                    if w == 0:
                        seen[pos] += 1
                    else:
                        wrong.append((pos, f"{w:08x}"))
                    continue
                if post:
                    v = (w >> 8) - (1 << 24) if w & 0x80000000 else w >> 8
                    k = next((k for k, (lo, hi) in enumerate(band) if lo <= v <= hi), None)
                    if k is None:
                        continue
                    src, lr = divmod(k, 2)
                else:
                    src, lr = (w >> 24) - 0x10, ((w >> 16) & 0xff) - 0x20
                if 0 <= src < 10 and lr in (0, 1):
                    if (src, lr) == taps[pos]:
                        seen[pos] += 1
                    else:
                        wrong.append((pos, f"{w:08x}"))
            names = ["T%d %s" % (s + 1, "LR"[c]) if s < 8 else ("MAIN", "CUE")[s - 8] + " " + "LR"[c] for s, c in taps]
            check(f"USB AUDIO: channels 1-{nch} carry {', '.join(names) if nch <= 4 else names[0] + ' .. ' + names[-1]}, each its own source's words only"
                  + (f" (POST: tap k at (k+1)<<17 times the boot gain G = 0x{post_g_default():06x})" if post else ""),
                  not wrong and all(n >= 100 for n in seen), f"per-channel hits {seen}; wrong {wrong[:6]}")
            b.ctrl_nodata(0x01, 0x0b, 0, asn)
            after = [len(b.ep_in(3, 1024)) for _ in range(8)]
            check("USB AUDIO: alt 0 stops the stream (empty polls)", all(a == 0 for a in after[2:]), str(after))
            # THE FIRST POLL SETS THE CUSHION (usbaudio_kick). A host that
            # starts polling late finds the ring AUD_TARGET behind the
            # producer, not AUD_TARGET plus what it produced while the host was
            # getting ready: the consumer is re-anchored at the first retired
            # packet and the frames between are skipped, counted in `anchor`.
            # Here the bench is that late host: alt 1 again, then no EP3 poll
            # until 600 frames have been produced (EP0 keeps answering), so
            # the port logs one run of missed polls for this phase.
            b.ctrl_nodata(0x01, 0x0b, 1, asn)
            c0 = usb_host.counters(b)
            while usb_host.counters(b)["produced"] - c0["produced"] < 600:
                pass
            first = [len(b.ep_in(3, 1024)) for _ in range(4)]
            c1 = usb_host.counters(b)
            gap = c1["produced"] - c0["produced"]
            check(f"USB AUDIO: a first poll {gap} frames after alt 1 re-anchors the cushion at {AUD_TARGET}: {c1['anchor']} frames skipped, lastfill {c1['lastfill']}",
                  480 <= c1["anchor"] <= gap + 32 and abs(c1["lastfill"] - AUD_TARGET) <= AUD_TARGET // 2 and any(first),
                  f"anchor {c1['anchor']} gap {gap} lastfill {c1['lastfill']} first polls {first}")
            for _ in range(400):
                b.ep_in(3, 1024)
            c2 = usb_host.counters(b)
            # The floor only: a poll the bench host misses drains nothing, so
            # bench lag can only RAISE the fill (maxfill 678 and 698 with 106
            # and 351 missed polls, four shards, 28 Sep 2026). maxfill is printed.
            # Floor AUD_TARGET / 2. Measured under the port (usb-out-tracks-main-cue,
            # AUD_TARGET 64, 5 Oct 2026, three runs): lastfill 79, 63, 63 (band
            # 32..96); minfill 64, 53, 63 (floor 32).
            check(f"USB AUDIO: 400 polls on, the fill held near the target: min {c2['minfill']} (floor {AUD_TARGET // 2}), max {c2['maxfill']}, no underrun",
                  c2["underruns"] == 0 and c2["minfill"] >= AUD_TARGET // 2,
                  f"minfill {c2['minfill']} maxfill {c2['maxfill']} underruns {c2['underruns']}")
            # Bus reset with the stream open and no alt 0 from the host (a
            # cable pull or a host crash): USB 2.0 9.1.1.5 puts the interface
            # back to alt 0. The stock URI handler writes no alt byte
            # (audio_reset_shim does), so before it GET_INTERFACE(as_) answered
            # 1 and the stream went on.
            b.reset()
            alt = b.ctrl_in(0x81, 0x0a, 0, asn, 1)
            check("USB AUDIO: GET_INTERFACE reports alt 0 after a bus reset", alt == b"\x00", alt.hex())
            after = [len(b.ep_in(3, 1024)) for _ in range(8)]
            check("USB AUDIO: a bus reset stops the stream (empty polls)", all(a == 0 for a in after[2:]), str(after))
            b.ctrl_nodata(0x01, 0x0b, 1, asn)
            got = [len(b.ep_in(3, 1024)) for _ in range(400)]
            check("USB AUDIO: SET_INTERFACE alt 1 after the reset brings the stream back, none of the last 300 polls empty",
                  all(g > 0 for g in got[100:]), f"empty polls after the first 100: {sum(1 for g in got[100:] if g == 0)}")
            b.ctrl_nodata(0x01, 0x0b, 0, asn)
            # Full speed: the same device re-enumerated. The stereo sum of the
            # priority source (tracks > MAIN > CUE > MASTER) in 44/45-frame
            # 1 ms packets of 8-byte frames.
            usb_host.enumerate_device(b, hs=False)
            b.iso_hz(0)                                          # bInterval 1 at full speed: 1 ms
            b.ctrl_nodata(0x01, 0x0b, 1, asn)
            fs = []
            for _ in range(300):
                if nch == 2:                                     # a single-pair combo: the sum is that pair
                    b.poke(MAIN_CUE_BASE, TAP_MC) if taps[0][0] >= 8 else b.poke(RB_BASE, TAP_RB)
                fs.append(b.ep_in(3, 1024))
            fsizes = sorted({len(g) for g in fs[10:]})
            check(f"USB AUDIO: full speed: 1 ms packets of 43-46 8-byte frames, none empty after the first ten",
                  bool(fsizes) and all(s in (344, 352, 360, 368) for s in fsizes), f"sizes {fsizes}")
            if nch == 2:
                fw = [int.from_bytes(w[i:i + 4], "little") for w in fs[-150:] for i in range(0, len(w), 4)]
                fseen, fwrong = [0, 0], []
                for i, w in enumerate(fw):
                    pos = i % 2
                    if taps[pos][0] == 7:      # MASTER as the priority source: region 7 reads 0
                        if w == 0:
                            fseen[pos] += 1
                        else:
                            fwrong.append((pos, f"{w:08x}"))
                        continue
                    src, lr = (w >> 24) - 0x10, ((w >> 16) & 0xff) - 0x20
                    if 0 <= src < 10 and lr in (0, 1):
                        if (src, lr) == taps[pos]:
                            fseen[i % 2] += 1
                        else:
                            fwrong.append((i % 2, f"{w:08x}"))
                _src = {7: "T8", 8: "MAIN", 9: "CUE"}.get(taps[0][0], f"source {taps[0][0]}")
                check(f"USB AUDIO: full speed: channels 1/2 carry {_src} L/R, its own words only",
                      not fwrong and all(n >= 100 for n in fseen), f"per-channel hits {fseen}; wrong {fwrong[:6]}")
            b.ctrl_nodata(0x01, 0x0b, 0, asn)
    except Exception as e:  # noqa: BLE001 -- a hang or a stall is the finding
        check(f"the host script completed ({type(e).__name__}: {e})", False)
    finally:
        try:
            b.sock.close()          # the hangup ends the port's hold
        except NameError:
            emu.kill()
    try:
        rc = emu.wait(timeout=120)
    except subprocess.TimeoutExpired:
        emu.kill()
        rc = -1
    check("the port exited cleanly after the client hung up", rc == 0, f"exit {rc}")
    text = log.read_text(errors="replace")
    summary = [l for l in text.splitlines() if l.startswith("usb        : USBCMD")]
    if midi:
        writes = [l for l in text.splitlines() if f"[{MIDI_FIFO_HEAD:#x}]" in l]
        check("USB MIDI: six bytes enqueued into the firmware's MIDI receive FIFO", len(writes) == 6, f"{len(writes)} write(s)")
    check("the port printed its USB summary", bool(summary))
    if summary:
        s = summary[-1]
        print("  " + s)
        check("no uninitialised queue head was primed", "UNINITIALIZED" not in s)
        check("no EP0 stall during enumeration" + (f" (only the {stalls_expected} the gate asks for)" if stalls_expected else ""),
              f" {stalls_expected} stall(s)" in s)
    # ---- runtime: 16 combinations, via the CS1 early block ----------------
    # The settings are NEXT_BOOT (the CS1 early block at usb_cs1_base, read
    # by cfgsel at the USB controller init). A prepared block holding one
    # combination is booted per row: the SERVED configuration must be that
    # row's shape, not the image's resolved one (a row whose bytes differ
    # from the resolved ones proves the runtime read). The pair guard is
    # bracketed: IN with every output off (refused in SETTINGS, brain.c
    # usb_pair_ok) must serve MIDI alone, and IN beside the 20-channel
    # combo must serve the audio set. MIDI off proves the interface
    # renumber (AC 1 / AS 2 / IN 3). TRACKS with MASTER (refused in SETTINGS,
    # brain.c usb_master_ok) must serve the set without MASTER: cfgsel
    # clears it.
    base, early, resolved = early_block(remix, mods)
    if base and usb and has_early_slot(early):
        # (tag, trk, main, cue, master, in, midi) as the block's value bytes
        rows = [
            ("TRACKS PRE", 1, 0, 0, 0, 0, 1),
            ("TRACKS POST", 2, 0, 0, 0, 0, 1),
            ("MAIN", 0, 1, 0, 0, 0, 1),
            ("CUE", 0, 0, 1, 0, 0, 1),
            ("MASTER", 0, 0, 0, 1, 0, 1),
            ("MAIN CUE", 0, 1, 1, 0, 0, 1),
            ("TRACKS MAIN CUE", 1, 1, 1, 0, 0, 1),
            ("TRACKS MAIN CUE + MASTER (the guard: MASTER cleared)", 1, 1, 1, 1, 0, 1),
            ("TRACKS MAIN CUE + IN AB", 1, 1, 1, 0, 1, 1),
            ("TRACKS MAIN CUE + IN CD", 1, 1, 1, 0, 2, 1),
            ("TRACKS MAIN CUE + IN ABCD", 1, 1, 1, 0, 3, 1),
            ("TRACKS MAIN CUE, MIDI OFF", 1, 1, 1, 0, 0, 0),
            ("TRACKS MAIN CUE + IN AB, MIDI OFF", 1, 1, 1, 0, 1, 0),
            ("IN AB without an output (the guard)", 0, 0, 0, 0, 1, 1),
            ("ALL OFF", 0, 0, 0, 0, 0, 1),
            ("MSC ONLY", 0, 0, 0, 0, 0, 0),
        ]
        in_settable = any(_s.name == "IN" and at is not None for _m, _s, at in early)
        if not in_settable:
            print("  [SKIP] runtime rows with IN on: IN is fixed in this image (pinned), no CS1 entry to write")
        for k, row in enumerate(rows):
            tag, trk_i, m_i, c_i, s_i, in_i, midi_i = row
            if in_i and not in_settable:
                continue
            vals = dict(zip(("TRACKS", "MAIN", "CUE", "MASTER", "IN", "MIDI"), row[1:]))
            if trk_i:
                s_i = 0                         # the guard: cfgsel serves the set without MASTER
            rnch, rmax, rbint = geom(trk_i, m_i, c_i, s_i)
            rin = IN_LABELS[in_i]
            rin_ch = IN_CH[rin] if in_i else 0
            racc = 3 if midi_i else 1
            ras = racc + 1
            rii = ras + 1
            if rnch:
                rnif = (6 if rin_ch else 5) if midi_i else (4 if rin_ch else 3)
            else:
                rnif = 3 if midi_i else 1
            cs1_file = ROOT / f"out/verify_usb_cs1_{k}.bin"
            cs1_file.write_bytes(cs1_block(base, early, resolved, vals))
            sock = f"/tmp/ot-usb-rt-{os.getpid()}-{k}.sock"
            log = ROOT / f"out/verify_usb_rt_{k}.log"
            with open(log, "w") as lf:
                emu = subprocess.Popen([str(EMU), "--image", str(IMAGE), "--usb-host", sock,
                                        "--usb-hold-ms", "60000", "--cs1-in", str(cs1_file)]
                                       + (["--frame"] if rnch else []),
                                       cwd=ROOT, stdout=lf, stderr=subprocess.STDOUT)
            try:
                b = usb_host.Bench(sock, timeout=60.0)
                dev, cfg = usb_host.enumerate_device(b, hs=True)
                ifaces = [d for t, d in usb_host.descriptors(cfg) if t == 4]
                eps = [d for t, d in usb_host.descriptors(cfg) if t == 5]
                as_ = [d for d in ifaces if d[5:7] == bytes([1, 2])]
                iso = [d for d in eps if d[2] == 0x83]
                ison = [d for d in eps if d[2] == 0x03]
                if rnch == 0:
                    check(f"runtime {tag}: {'USB MIDI alone (MSC + MIDI)' if midi_i else 'MSC only'}"
                          + " (no audio interfaces, no EP 0x83/0x03)",
                          cfg[4] == rnif and not as_ and not iso and not ison,
                          f"bNumInterfaces {cfg[4]} audio {len(as_)} EP0x83 {len(iso)} EP0x03 {len(ison)}")
                else:
                    check(f"runtime {tag}: bNumInterfaces {rnif}, interface {ras} alt 0/1"
                          + (f", interface {rii} alt 0/1" if rin_ch else ""),
                          cfg[4] == rnif and
                          sorted((d[2], d[3]) for d in as_) == [(ras, 0), (ras, 1)] + ([(rii, 0), (rii, 1)] if rin_ch else []),
                          f"bNumInterfaces {cfg[4]} {[(d[2], d[3]) for d in as_]}")
                    asg = cfg.find(bytes([16, 0x24, 1]))
                    cc = int.from_bytes(cfg[asg + 11:asg + 15], "little") if asg >= 0 and rnch == 2 else None
                    check(f"runtime {tag}: AS_GENERAL {rnch} channels, bmChannelConfig {hex(chcfg(trk_i, m_i, c_i, s_i))}",
                          asg >= 0 and cfg[asg + 10] == rnch and (rnch != 2 or cc == chcfg(trk_i, m_i, c_i, s_i)),
                          f"bNrChannels {cfg[asg + 10] if asg >= 0 else None} config {cc}")
                    check(f"runtime {tag}: EP 0x83 isochronous, {rmax} bytes, bInterval {rbint}"
                          + (", implicit-feedback data" if rin_ch else ""),
                          len(iso) == 1 and (iso[0][3] & 3, iso[0][4] | iso[0][5] << 8, iso[0][6]) == (1, rmax, rbint)
                          and ((iso[0][3] >> 4 & 3) == 2 if rin_ch else True),
                          str([(d[3], d[4] | d[5] << 8, d[6]) for d in iso]))
                    if rin_ch:
                        check(f"runtime {tag}: EP 0x03 isochronous data, {12 * 4 * rin_ch} bytes, bInterval 2",
                              len(ison) == 1 and (ison[0][3], ison[0][4] | ison[0][5] << 8, ison[0][6]) == (0x05, 12 * 4 * rin_ch, 2),
                              str([(d[3], d[4] | d[5] << 8, d[6]) for d in ison]))
                    # the full-speed (other-speed) configuration: 2 channels,
                    # 360-byte EP 0x83 at 1 ms, and no IN interface (served at
                    # high speed only) -- every audio set shares this pair
                    ocfg = b.ctrl_in(0x80, 6, 0x0700, 0, 512)
                    of = [d for t, d in usb_host.descriptors(ocfg) if t == 5]
                    check(f"runtime {tag}: the other-speed config is the shared full-speed pair "
                          f"(bNumInterfaces {5 if midi_i else 2}, EP 0x83 360 B at 1 ms, no IN interface)",
                          len(ocfg) >= 9 and ocfg[4] == (5 if midi_i else 2) and bytes([16, 0x24, 1, 0x13]) not in ocfg
                          and [(d[2], d[3] & 3, d[4] | d[5] << 8, d[6]) for d in of if d[2] == 0x83] == [(0x83, 1, 360, 1)],
                          f"bNumInterfaces {ocfg[4] if len(ocfg) >= 9 else None} EP {[(d[2], d[4] | d[5] << 8, d[6]) for d in of if d[2] == 0x83]}")
                b.sock.close()
            except Exception as e:  # noqa: BLE001
                check(f"runtime {tag}: the host script completed ({type(e).__name__}: {e})", False)
            try:
                rc = emu.wait(timeout=120)
            except subprocess.TimeoutExpired:
                emu.kill()
                rc = -1
            check(f"runtime {tag}: the port exited cleanly", rc == 0, f"exit {rc}")
    else:
        print("  [SKIP] runtime: no brain, no USB module, or no USB setting with an early CS1 entry (the resolved values stand)")
    print(f"verify_usb: {'OK' if not fails else str(len(fails)) + ' FAILED'} ({log})")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
