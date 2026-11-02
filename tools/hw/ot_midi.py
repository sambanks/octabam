#!/usr/bin/env python3
"""Drive the Octatrack over CoreMIDI from the command line (macOS, no deps).

    python3 tools/hw/ot_midi.py list
    python3 tools/hw/ot_midi.py -p A cc  <ch> <cc> <val>      # e.g. -p A cc 1 40 64
    python3 tools/hw/ot_midi.py -p A note <ch> <note> [vel] [hold_s]
    python3 tools/hw/ot_midi.py -p A raw  B0 28 40             # hex bytes
    python3 tools/hw/ot_midi.py -p A start | stop
    python3 tools/hw/ot_midi.py -p A listen [seconds]          # dump incoming; clock (F8) and
                                                               # active sensing (FE) are counted, not printed

OT map (manual + docs/firmware/MIDI.md appendix A): FX2 params 1-6 = CC 40-45 on the
track's channel (SEND: 40 = -DEL, 41 = -VRB); FX1 = CC 34-39; level CC 7;
mute/solo CC 49/50; crossfader CC 48; sample trig = note 36+track;
chromatic = notes 72-96 (84 = unison).
"""
import ctypes, ctypes.util, platform, sys, time

cm = ctypes.cdll.LoadLibrary('/System/Library/Frameworks/CoreMIDI.framework/CoreMIDI')
cf = ctypes.cdll.LoadLibrary('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
UTF8 = 0x08000100
for f in (cm.MIDIGetNumberOfSources, cm.MIDIGetNumberOfDestinations):
    f.restype = ctypes.c_ulong
for f in (cm.MIDIGetSource, cm.MIDIGetDestination):
    f.restype = ctypes.c_uint32
cf.CFStringCreateWithCString.restype = ctypes.c_void_p
cf.CFStringGetCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_long, ctypes.c_uint32]
cm.MIDIObjectGetStringProperty.argtypes = [ctypes.c_uint32, ctypes.c_void_p, ctypes.c_void_p]
cm.MIDIClientCreate.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
cm.MIDIOutputPortCreate.argtypes = [ctypes.c_uint32, ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
cm.MIDIPacketListInit.restype = ctypes.c_void_p
cm.MIDIPacketListAdd.restype = ctypes.c_void_p
cm.MIDIPacketListAdd.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_uint64, ctypes.c_ulong, ctypes.c_char_p]
cm.MIDISend.argtypes = [ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
cm.MIDIInputPortCreate.argtypes = [ctypes.c_uint32, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
cm.MIDIPortConnectSource.argtypes = [ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
READPROC = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)


def find(kind, name, wait=3.0):
    """The endpoint called `name`, or None. A new process can see an empty endpoint
    list for the first moments (seen 19 Oct 2026, one run in several), so poll."""
    t0 = time.time()
    while True:
        m = [ep for n, ep in endpoints(kind) if n == name]
        if m or time.time() - t0 >= wait:
            return m[0] if m else None
        time.sleep(0.1)


# MIDIServices.h's MIDIPacketNext: packets 4-byte aligned on an ARM CPU, packed on Intel
PACKETS_ALIGNED = platform.machine() == "arm64"


def _walk(pktlist, aligned):
    """The packets' (address, length), each next one after the data (aligned: at the next 4-byte
    boundary), or None when one of them cannot be a packet: a length of 0 or over 256, or data
    that starts with a byte below 0x80 outside a SysEx. Reads 3 bytes a packet before trusting it."""
    n = ctypes.cast(pktlist, ctypes.POINTER(ctypes.c_uint32))[0]
    p, out, sysex = pktlist + 4, [], False
    for _ in range(n):
        length = ctypes.cast(p + 8, ctypes.POINTER(ctypes.c_uint16))[0]
        if not 0 < length <= 256 or (ctypes.string_at(p + 10, 1)[0] < 0x80 and not sysex):
            return None
        for b in ctypes.string_at(p + 10, length):
            if b == 0xF0 or b == 0xF7:
                sysex = b == 0xF0                       # a packet may end inside a SysEx
        out.append((p, length))
        end = p + 10 + length
        p = (end + 3) & ~3 if aligned else end
    return out


def packets(pktlist):
    """Each MIDIPacket's data in a MIDIPacketList: an 8-byte timestamp, a 2-byte length, the data.
    A virtual source's lists follow PACKETS_ALIGNED (read packed on ARM, the packet after a START
    came out one byte early). The unit's own bursts were once reported packed on ARM, so a list
    that does not read whole as aligned is read packed; probing an aligned list packed stays
    inside it, each packed address being at or before the aligned one."""
    walk = (_walk(pktlist, True) if PACKETS_ALIGNED else None) or _walk(pktlist, False) or []
    for p, length in walk:
        yield ctypes.string_at(p + 10, length)


class In:
    """Source `port_name`'s bytes, one packet at a time, to `on_bytes(data)`. CoreMIDI calls it on
    threads of its own (measured: they keep coming while the caller sleeps), so its timestamps do
    not wait for the caller and anything it shares with the caller needs a lock.
    pump() runs this thread's run loop, which delivers the endpoint list's changes."""

    def __init__(self, port_name, on_bytes):
        self.client = ctypes.c_uint32(); self.port = ctypes.c_uint32()
        cm.MIDIClientCreate(cfstr("octabam-in"), None, None, ctypes.byref(self.client))

        def cb(pktlist, _a, _b):
            for data in packets(pktlist):
                on_bytes(data)
        self.proc = READPROC(cb)                        # kept: CoreMIDI holds only the pointer
        cm.MIDIInputPortCreate(self.client, cfstr("in"), self.proc, None, ctypes.byref(self.port))
        self.src = find("src", port_name)
        if self.src is None:
            sys.exit(f"no MIDI source named {port_name!r}")
        cm.MIDIPortConnectSource(self.port, self.src, None)

    def close(self):
        """No more deliveries. Keep the object: CoreMIDI may hold the callback's pointer until the port goes."""
        cm.MIDIPortDisconnectSource.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
        cm.MIDIPortDisconnectSource(self.port, self.src)
        cm.MIDIPortDispose.argtypes = [ctypes.c_uint32]
        cm.MIDIPortDispose(self.port)

    @staticmethod
    def pump(seconds):
        cf.CFRunLoopRunInMode.argtypes = [ctypes.c_void_p, ctypes.c_double, ctypes.c_bool]
        cf.CFRunLoopRunInMode(cfstr("kCFRunLoopDefaultMode"), seconds, False)


def listen(port_name, seconds):
    """Print incoming events from source `port_name` for `seconds`; F8 and FE are only counted."""
    t0 = time.time()
    skipped = {0xF8: 0, 0xFE: 0}

    def show(data):
        for b in data:
            if b in skipped:
                skipped[b] += 1
        rest = bytes(b for b in data if b not in skipped)
        if rest:
            print(f"{time.time()-t0:7.3f}  {rest.hex(' ')}", flush=True)
    inp = In(port_name, show)                           # held: its callback must outlive the loop
    while time.time() - t0 < seconds:
        inp.pump(0.1)
    print(f"not printed: {skipped[0xF8]} clock (F8), {skipped[0xFE]} active sensing (FE)")


def cfstr(s):
    return cf.CFStringCreateWithCString(None, s.encode(), UTF8)


_NAME = cfstr("name")                                   # one key for every lookup: each cfstr is a copy


def name_of(ep):
    """The endpoint's name, or None when it has gone: a source that left between the count and here
    gave no string, and reading the null crashed the process (a unit's source going away)."""
    out = ctypes.c_void_p()
    if not ep or cm.MIDIObjectGetStringProperty(ep, _NAME, ctypes.byref(out)) != 0 or not out.value:
        return None
    buf = ctypes.create_string_buffer(256)
    cf.CFStringGetCString(out, buf, 256, UTF8)
    cf.CFRelease.argtypes = [ctypes.c_void_p]
    cf.CFRelease(out)                                   # the property is a copy the caller owns
    return buf.value.decode()


def endpoints(kind):
    n, get = ((cm.MIDIGetNumberOfSources, cm.MIDIGetSource) if kind == "src"
              else (cm.MIDIGetNumberOfDestinations, cm.MIDIGetDestination))
    eps = [get(i) for i in range(n())]
    return [(name, ep) for ep in eps if (name := name_of(ep)) is not None]


class Out:
    def __init__(self, port_name):
        self.client = ctypes.c_uint32(); self.port = ctypes.c_uint32()
        cm.MIDIClientCreate(cfstr("octabam"), None, None, ctypes.byref(self.client))
        cm.MIDIOutputPortCreate(self.client, cfstr("out"), ctypes.byref(self.port))
        self.dest = find("dst", port_name)
        if self.dest is None:
            sys.exit(f"no MIDI destination named {port_name!r}; have "
                     f"{[n for n, _ in endpoints('dst')]}")

    def send(self, data):
        buf = ctypes.create_string_buffer(1024)
        pkt = cm.MIDIPacketListInit(buf)
        cm.MIDIPacketListAdd(buf, 1024, pkt, 0, len(data), bytes(data))
        cm.MIDISend(self.port, self.dest, buf)


def main():
    a = sys.argv[1:]
    port = "A"
    if a and a[0] == "-p":
        port = a[1]; a = a[2:]
    if not a or a[0] == "list":
        print("sources:     ", [n for n, _ in endpoints("src")])
        print("destinations:", [n for n, _ in endpoints("dst")]); return
    cmd, args = a[0], a[1:]
    if cmd == "listen":
        listen(port, float(args[0]) if args else 10); return
    out = Out(port)
    if cmd == "cc":
        ch, cc, val = map(int, args)
        out.send([0xB0 | (ch - 1), cc, val])
    elif cmd == "note":
        ch, note = int(args[0]), int(args[1])
        vel = int(args[2]) if len(args) > 2 else 100
        hold = float(args[3]) if len(args) > 3 else 0.2
        out.send([0x90 | (ch - 1), note, vel]); time.sleep(hold)
        out.send([0x80 | (ch - 1), note, 0])
    elif cmd == "raw":
        out.send([int(x, 16) for x in args])
    elif cmd == "start":
        out.send([0xFA])
    elif cmd == "stop":
        out.send([0xFC])
    else:
        sys.exit(__doc__)
    time.sleep(0.05)


if __name__ == "__main__":
    main()
