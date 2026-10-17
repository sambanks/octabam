"""Shared virtual-project fixture and MIDI capture decoder for module gates."""
import re

def fixture(source, dest, arp=False, leader=0, offsets=None):
    import ab_fixture
    from hw import ot_project as otp
    ab_fixture.prepare(source, dest)
    # Serialized MIDI data: MTRA has three masks then 64 x 32-byte locks.
    # Part MIDI page-1 = body+0x3e2, setup = body+0x4e2 (36 bytes/track).
    # Proven below by the stock image's notes/channels/velocities on UART0.
    steps = ({2: 60, 4: 65, 8: 67},
             {0: 48, 2: 48, 3: 48, 6: 48, 8: 48, 10: 48},
             {1: 72, 5: 74, 9: 76})
    steps = {leader: steps[0], 1: steps[1], 2: steps[2]}
    for path in dest.glob('bank*.work'):
        def mutate(data):
            for part in range(8):
                base = otp.PART_BASE + part * otp.PART_STRIDE + 9
                for t in range(8):
                    at = base + 0x3e2 + 32 * t
                    data[at:at+32] = bytes.fromhex(
                        '3c 64 06 40 40 40 20 20 20 00 00 00 40 00 00 05 '
                        '00 06 40 00 7f 00 00 40 00 00 00 00 00 00 00 00')
                    if arp and t == leader:
                        data[at+2] = 18  # enough time for the arp to walk the chord
                        data[at+3:at+5] = bytes((68, 71))  # major third and fifth
                        data[at+14] = 1  # UP
                        data[at+15] = 3  # fast enough for three notes before F
                    if t == 1 and offsets is not None:
                        data[at+12] = 71  # whole-track TRAN +7; unlocked steps inherit
                    channel = {7: 13, 1: 5, 2: 3}.get(t, 0) if leader == 7 else t + 1
                    data[base + 0x4e2 + 36*t] = channel if t in steps else 0
                    # Fresh native custom settings, independent of the template.
                    # The stock control ignores/clamps these blank SETUP fields.
                    for field,value in ((3,0),(5,0),(12,0),(13,3),(15,2),(16,0),(18,0),(19,0)):
                        data[base + 0x4e2 + 36*t + field] = value
            for p in range(16):
                # Explicit normal scale mode, 64-step cycle at 1x. Otherwise
                # an advanced-mode template can wrap during the MIDI capture.
                end = 0x16 + (p + 1) * 0x8eec
                data[end-11:end-6] = bytes((16, 2, 64, 2, 0))
                for t in range(8):
                    at = 0x492e + p * 0x8eec + t * 0x8b9
                    assert data[at:at+4] == b'MTRA'
                    data[at+9:at+33] = bytes(24)
                    data[at+0x39:at+0x839] = b'\xff' * 2048
                    data[at+0x31:at+0x33] = bytes((16, 2))
                    if p == 0 and t in steps:
                        data[at+9:at+17] = sum(1 << s for s in steps[t]).to_bytes(8, 'big')
                        for s, n in steps[t].items():
                            lock = at + 0x39 + s * 32
                            data[lock:lock+2] = bytes((n, 90+t))
                            if t == 1 and offsets is not None and s in offsets:
                                data[lock+12] = 64 + offsets[s]
                            if t == 1 and s == 3:
                                data[lock+2] = 12  # held across the F root change
                            if t == leader and s == 4:
                                data[lock+3] = 68  # F + A: first NOTE remains root
                            if t == 1 and s == 8:
                                data[lock+3] = 71  # extra fifth suppressed in bass mode
        otp._bank_write(dest, int(path.stem[4:]), mutate, guard=False)
    for path in dest.glob('project.*'):
        raw = re.sub(rb'\[SAMPLE\].*?\[/SAMPLE\]\r?\n', b'', path.read_bytes(), flags=re.S)
        # Fixed clock makes frame 1500 land inside the held step-4 bass note.
        raw = re.sub(rb'TEMPOx24=\d+', b'TEMPOx24=2880', raw)
        raw = re.sub(rb'PATTERN_TEMPO_ENABLED=\d+', b'PATTERN_TEMPO_ENABLED=0', raw)
        path.write_bytes(raw)


def notes(raw):
    """Decode running status; discard real-time bytes without losing state."""
    status, data, result, sysex = None, [], [], False
    for b in raw:
        if b >= 0xf8:
            continue
        if b == 0xf0:
            status, data, sysex = None, [], True
        elif b == 0xf7:
            sysex = False
        elif sysex:
            continue
        elif b & 128:
            status, data = (b if b < 0xf0 else None), []
        elif status is not None:
            data.append(b)
            if len(data) == (1 if status & 0xf0 in (0xc0, 0xd0) else 2):
                if status & 0xf0 in (0x80, 0x90):
                    result.append(('on' if status & 0xf0 == 0x90 and data[1] else 'off',
                                   (status & 15)+1, data[0], data[1]))
                data = []
    return result
