#!/usr/bin/env python3
"""Execute the built loopback and stock queue/receive code. No firmware bundled.

Default: narrow machine gates. --project DIR also runs the real sequencer,
RTOS and UART receiver under the ColdFire port on a disposable project copy.
"""
import argparse
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import toolpath  # noqa: E402,F401
from unicorn import Uc, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE, UC_HOOK_MEM_READ
from unicorn.m68k_const import *
from midi_machine import dram_map_size

Q = 0x46c7e974
STACK, DONE, MSG = 0x47008000, 0x4700fff0, 0x47001000
REGS = [UC_M68K_REG_D0, UC_M68K_REG_D1, UC_M68K_REG_D2,
        UC_M68K_REG_D3, UC_M68K_REG_D4, UC_M68K_REG_D5,
        UC_M68K_REG_D6, UC_M68K_REG_D7, UC_M68K_REG_A0,
        UC_M68K_REG_A1, UC_M68K_REG_A2, UC_M68K_REG_A3,
        UC_M68K_REG_A4, UC_M68K_REG_A5, UC_M68K_REG_A6]


def symbols():
    nm = subprocess.check_output(["m68k-elf-nm", str(ROOT / "out/platform/runtime/runtime.elf")], text=True)
    return {n: int(a, 16) for a, n in re.findall(r"^([0-9a-f]+) [Tt] ((?:lb|usbmidi)_\w+)$", nm, re.M)}


class Machine:
    def __init__(self, *, symbol_table=None):
        self.sym = symbols() if symbol_table is None else dict(symbol_table)
        u = self.u = Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN)
        u.ctl_set_cpu_model(UC_CPU_M68K_CFV4E)
        layout = json.loads((ROOT / "out/platform/layout.json").read_text())
        for a, size in ((0x40000000, dram_map_size(layout)), (0x46000000, 0x200000),
                        (0x46c70000, 0x20000), (0x47000000, 0x10000),
                        (0x10000000, 0x200000),
                        (0x80000000, 0x10000), (0xfc000000, 0x1000000)):
            u.mem_map(a, size)
        image = (ROOT / "out/mainos_bus.bin").read_bytes()
        u.mem_write(0x40000400, image)
        u.mem_write(layout["base"], (ROOT / "out/platform/runtime/runtime.bin").read_bytes())
        for site, symbol in ((0x4009f794, "lb_tick"), (0x40005558, "lb_receive"),
                             (0x4009f26e, "lb_control_tail"),):
            assert u.mem_read(site, 6) == b"\x4e\xf9" + self.sym[symbol].to_bytes(4, "big")
        for site in (0x4009fbae, 0x4009fcf6, 0x4009feee, 0x4009ffba,
                     0x4009f8be, 0x4009fc50, 0x4009fcd4, 0x4009f328, 0x400a0020):
            assert int.from_bytes(u.mem_read(site, 4), "big") == self.sym["lb_send"]
        self.stops = {DONE}
        self.arrived = None
        u.hook_add(UC_HOOK_CODE, self.stop)
        self.queue(Q, 0x47002000)
        self.queue(0x460d17ae, 0x47003000)
        self.put(0x400b966c, 0x47004000)  # UART TX ring
        self.put(0x400b9678, 4095)

    def stop(self, u, pc, size, data):
        if pc in self.stops:
            self.arrived = pc
            u.emu_stop()

    def put(self, at, value, size=4):
        self.u.mem_write(self.sym.get(at, at), value.to_bytes(size, "big"))

    def get(self, at, size=4):
        return int.from_bytes(self.u.mem_read(self.sym.get(at, at), size), "big")

    def queue(self, at, storage):
        self.u.mem_write(at, bytes(32))
        self.put(at + 16, 255)
        self.put(at + 20, storage)

    def call(self, at, args=(), regs=None, stop=DONE, return_pc=DONE):
        u = self.u
        self.stops, self.arrived = {stop}, None
        u.reg_write(UC_M68K_REG_SR, 0x2000)
        u.reg_write(UC_M68K_REG_A7, STACK)
        self.put(STACK, return_pc)
        for i, value in enumerate(args):
            self.put(STACK + 4 + i * 4, value)
        for reg, value in (regs or {}).items():
            u.reg_write(reg, value)
        u.emu_start(self.sym.get(at, at), 0, count=1000000)
        assert self.arrived == stop, (at, hex(u.reg_read(UC_M68K_REG_PC)))
        return u.reg_read(UC_M68K_REG_D0)

    def capture(self, msg, source=0x4009fbb2, track=0):
        self.u.mem_write(MSG, bytes(msg))
        return self.call("lb_capture", regs={UC_M68K_REG_D0: source,
                  UC_M68K_REG_D1: track, UC_M68K_REG_D2: len(msg), UC_M68K_REG_A0: MSG})

    def next(self):
        return bytes(self.u.mem_read(self.call("lb_next"), 3))

    def receiver_setup(self):
        self.put(0x46c82456, 0x40100000)
        self.u.mem_write(0x8000003f, bytes((0, 1, 2, 3, 4, 5, 6, 7)))
        self.put(0x80000047, 10, 1)
        self.put(0x80000049, 1, 1)
        self.put(0x8000004b, 1, 1)
        self.put(0x80000000, 7, 1)
        self.call(0x400054f4)  # stock incoming-note bookkeeping init

    def dispatch(self, msg):
        self.u.mem_write(MSG, bytes(msg))
        handler = self.get(0x400d6474 + (msg[0] >> 4) * 4)
        self.call(handler, (MSG, 0))


def machine_gate():
    m = Machine()
    assert m.get("lb_routes", 1) == 0
    m.capture((0x90, 84, 100))
    assert m.get("lb_accepted") == 0
    m.capture((0x80, 84, 0), 0x4009f8c2)
    m.put("lb_routes", 2, 1)
    for msg, pc, track in [((0x90, 84, 100), 0x4000e11a, 0),
                           ((0x90, 83, 100), 0x4009fbb2, 1),
                           ((0xe0, 84, 100), 0x4009fbb2, 0),
                           ((0xb0, 46, 70), 0x40040aa4, 0),
                           ((0xf8,), 0x4009fbb2, 0),
                           ((0x90, 128, 100), 0x4009fbb2, 0)]:
        m.capture(msg, pc, track)
    assert m.get("lb_accepted") == 0
    m.capture((0x80, 83, 0), 0x4009f8c2)
    m.capture((0x90, 84, 100))
    m.capture((0xb0, 46, 70), 0x4009fef2)
    assert m.get(Q + 4) == 1, "only one wake token"
    assert m.next() == bytes((0x90, 84, 100))
    assert m.next() == bytes((0xb0, 46, 70))
    m.put("lb_routes", 0, 1)
    m.capture((0x90, 84, 0), 0x4009f8c2)
    assert m.next() == bytes((0x90, 84, 0)), "OFF must still release owned notes"
    assert bytes(m.u.mem_read(m.sym["lb_owned"], 2048)) == bytes(2048)
    print("  [ok] source/track/channel filters, wake coalescing, OFF and note ownership")

    # Execute real stock queue receive, alternating external and internal.
    m = Machine(); m.put("lb_routes", 2, 1)
    m.u.mem_write(MSG + 16, bytes((0x91, 60, 90)))
    m.call(0x40000c3c, (Q, MSG + 16))
    m.capture((0xb0, 46, 20), 0x4009fef2)
    m.capture((0xb0, 46, 30), 0x4009ffbe)
    assert m.next() == bytes((0xb0, 46, 20))
    assert m.next() == bytes((0x91, 60, 90))
    assert m.next() == bytes((0xb0, 46, 30))
    print("  [ok] native/internal fairness and complete-message ordering")

    m = Machine(); m.put("lb_routes", 2, 1)
    m.put(0x46100b70, 0x91)  # DIN running status and half-message state
    m.put(0x46100b74, 60)
    for _ in range(256):
        m.call(0x40000c3c, (Q, MSG + 16))
    m.capture((0xb0, 46, 70), 0x4009fef2)
    assert m.get(Q + 4) == 256 and m.get("lb_wake_pending", 1) == 0
    assert m.next() == bytes((0xb0, 46, 70))
    assert m.get(0x46100b70) == 0x91 and m.get(0x46100b74) == 60
    print("  [ok] full native queue is not overrun; DIN framing state stays untouched")

    m = Machine(); m.put("lb_routes", 2, 1)
    for note in range(127):
        m.capture((0x90, note, 100))
    m.capture((0xb0, 46, 70), 0x4009fef2)
    assert m.get("lb_dropped") == 1
    for note in range(127):
        m.capture((0x80, note, 0), 0x4009f8c2)
    assert m.get("lb_highwater") == 254
    for status in (0x90, 0x80):
        for note in range(127):
            assert m.next() == bytes((status, note, 100 if status == 0x90 else 0))
    for i in range(300):
        m.capture((0xb0, 46, i % 128), 0x4009fef2)
        assert m.next() == bytes((0xb0, 46, i % 128))
    assert m.get("lb_head") == m.get("lb_tail")
    assert m.get("lb_accepted") == m.get("lb_delivered") == 554
    print("  [ok] saturation reserves releases, whole-message drop, ring wrap and recovery")

    # Run the sender wrapper, not only its helper. Caller is a proven
    # stock send site; stop at return before the sequencer continues.
    m = Machine(); m.put("lb_routes", 2, 1)
    m.u.mem_write(MSG, bytes((0x90, 84, 100)))
    regs = {reg: 0x12340000 + i for i, reg in enumerate(REGS)}
    regs[UC_M68K_REG_D7] = 0
    m.call("lb_send", (3, MSG), regs, stop=0x4009fbb2, return_pc=0x4009fbb2)
    for reg in REGS[2:8] + REGS[10:]:
        assert m.u.reg_read(reg) == regs[reg], reg
    assert m.get("lb_accepted") == 1
    assert m.get(0x400b967c) == 3
    assert bytes(m.u.mem_read(0x47004000 + 4093, 3))[::-1] == bytes((0x90, 84, 100))
    print("  [ok] installed sender preserves callee registers and actual stock UART bytes")

    # Both deliveries execute the installed stock handlers. Their deferred
    # RTOS/main-task continuation is additionally covered by --project.
    direct, internal = Machine(), Machine()
    for machine in (direct, internal):
        machine.receiver_setup()
    internal.put("lb_routes", 2, 1)
    for msg, pc in [((0xb0, 46, 70), 0x4009fef2),
                    ((0x90, 84, 100), 0x4009fbb2),
                    ((0x80, 84, 0), 0x4009f8c2)]:
        direct.dispatch(msg)
        internal.capture(msg, pc)
        internal.dispatch(internal.next())
        for at, n in ((0x80000c50, 16), (0x400d64c2, 8), (0x46c7fb08, 1),
                      (0x46c80354, 32), (0x46c7fe4c, 64)):
            assert direct.u.mem_read(at, n) == internal.u.mem_read(at, n), hex(at)
        if msg[0] == 0x90:
            assert direct.get(0x400d64c2, 1) == 84
            assert direct.get(0x46c7fe4c) == 1
    assert direct.get(0x80000c50, 1) == 70
    assert direct.get(0x400d64c2, 1) == 255
    assert direct.get(0x46c7fe4c) == 0
    print("  [ok] CC46 and chromatic on/off match stock handler state and release count")

    # Run the stock live CC producer through both installed branches. The
    # parent return PC distinguishes the panel from the generic MIDI setter.
    for tail, param in ((tail, param) for tail in (False, True) for param in range(20, 30)):
        cases = [(0x4005542c, 2, 0, 1)]
        if param == 20:
            cases = [(0x4005542c, route, track, int(route != 0))
                     for route in range(3) for track in range(8)]
            cases += [(0x40054f74, 2, 0, 0), (0x40043b0e, 2, 0, 1)]
        for parent, route, track, admitted in cases:
            m = Machine(); m.put(0x40171442 + 36*track + 12, route*4, 1)
            flag_byte, flag_bit = (0, param-18) if param < 24 else (1, param-24)
            for t in range(8):
                m.put(0x40171442 + 36*t, 1, 1)
                m.put(0x40171360 + 32*t + flag_byte, 1 << flag_bit, 1)
                m.put(0x46c76dc0 + 68*t + 30 + flag_byte, 1 << flag_bit, 1)
                m.put(0x46c76dc0 + 68*t + 32, 1, 1)
                m.put(0x46c76dc0 + 68*t + 52 + param-20, 34, 1)
            other = (track + 1) % 8
            m.put(0x8000000c, (255 ^ (1 << (other if tail else track))) << 8)
            usb = "usbmidi_up" in m.sym
            if usb:
                m.put("usbmidi_up", 1, 1)
                m.put("usbmidi_tx_busy", 1, 1)
            visited = []
            hook = m.u.hook_add(UC_HOOK_CODE, lambda u, pc, n, data:
                               visited.append(pc) if pc in (0x4009f22a, 0x4009f25e) else None)
            m.call(0x4009eec8, (track, param, 80, 0), stop=parent, return_pc=parent)
            m.u.hook_del(hook)
            assert visited == [0x4009f25e if tail else 0x4009f22a], visited
            assert m.get("lb_accepted") == admitted, (tail, parent, route, track)
            external = 0 if route == 1 and admitted else 3
            assert m.get(0x400b967c) == external
            if usb:
                assert m.get("usbmidi_tx_acc_len", 2) == external
            if admitted:
                assert m.next() == bytes((0xb0, 34, 80))
    print("  [ok] CC1-10 cached/tail panel paths, all-track routing and generic-setter feedback exclusion")


def routing_machine_gate():
    # Exercise every track/channel/route through the installed producer target,
    # including the USB entry mirror when present in the composed image.
    m = Machine()
    for track in range(8):
        for channel in range(16):
            for route in range(3):
                m.put(m.sym["lb_routes"] + track, route, 1)
                before = m.get("lb_accepted")
                tx = m.get(0x400b967c)
                usb = "usbmidi_up" in m.sym
                if usb:
                    m.put("usbmidi_up", 1, 1)
                    m.put("usbmidi_tx_busy", 1, 1)
                    m.put("usbmidi_tx_acc_len", 0, 2)
                events = [(0x90 | channel, 84, 100), (0xb0 | channel, 34, 70),
                          (0x80 | channel, 84, 0)]
                for msg, pc, operand in zip(events,
                        (0x4009fbb2, 0x4009fef2, 0x4009f8c2),
                        (0x4009fbae, 0x4009feee, 0x4009f8be)):
                    m.u.mem_write(MSG, bytes(msg))
                    m.call(m.get(operand), (3, MSG), {UC_M68K_REG_D7: track}, stop=pc, return_pc=pc)
                assert m.get("lb_accepted") - before == (3 if route else 0), (track, channel, route)
                assert m.get(0x400b967c) - tx == (0 if route == 1 else 9), (track, channel, route)
                if usb:
                    assert m.get("usbmidi_tx_acc_len", 2) == (0 if route == 1 else 9)
                    if route != 1:
                        assert bytes(m.u.mem_read(m.sym["usbmidi_tx_acc"], 9)) == bytes(sum((list(x) for x in events), []))
                if route:
                    assert [m.next() for _ in events] == [bytes(x) for x in events]
                assert m.get("lb_internal_held") == 0
    print("  [ok] M1-M8, channels 1-16, EXT/INT/BOTH notes/CCs and DIN" + ("/USB suppression" if usb else ""))

    m = Machine(); m.put("lb_routes", 1, 1)
    for note in range(128):
        assert m.capture((0x90, note, 100)) == 0
        assert m.next() == bytes((0x90, note, 100))
    assert m.get("lb_internal_held") == 128
    assert m.capture((0x91, 0, 100)) == 0
    assert m.get("lb_dropped") == 1
    assert m.capture((0x81, 0, 0), 0x4009f8c2) == 0
    assert m.get("lb_internal_held") == 128
    m.call("lb_set_route", (0, 0))
    assert m.get("lb_internal_held") == 0
    for note in range(128):
        assert m.next() == bytes((0x80, note, 0))
    assert m.get("lb_accepted") == m.get("lb_delivered") == 256
    print("  [ok] cross-channel held-note cap, INT drop tombstone and complete cleanup")

    # Setter cleanup follows the original route and channel. The old stock
    # release is consumed once; another track's held note is untouched.
    for old in range(3):
        for new in range(3):
            if old == new:
                continue
            m = Machine()
            m.call("lb_sync")
            if "usbmidi_up" in m.sym:
                m.put("usbmidi_up", 1, 1)
                m.put("usbmidi_tx_busy", 1, 1)
            m.call("lb_set_route", (0, old))
            m.put(m.sym["lb_routes"] + 7, 1, 1)
            m.capture((0x9f, 84, 100))
            m.capture((0x97, 85, 100), track=7)
            if old:
                assert m.next() == bytes((0x9f, 84, 100))
            assert m.next() == bytes((0x97, 85, 100))
            m.call("lb_set_route", (0, new))
            assert m.get("lb_internal_held") == 1
            assert m.get(0x400b967c) == (0 if old == 1 else 3)
            if "usbmidi_up" in m.sym:
                assert m.get("usbmidi_tx_acc_len", 2) == (0 if old == 1 else 3)
            if old:
                assert m.next() == bytes((0x8f, 84, 0))
            before = m.get("lb_accepted")
            assert m.capture((0x9f, 84, 0), 0x4009f8c2) == 0
            assert m.get("lb_accepted") == before
            m.capture((0x87, 85, 0), 0x4009f8c2)
            assert m.next() == bytes((0x87, 85, 0))
            assert m.get("lb_internal_held") == 0
    for channel in (0, 2, 16):
        m = Machine()
        m.put(0x46c76de0, 1, 1)
        m.call("lb_sync")
        m.call("lb_set_route", (0, 1))
        m.capture((0x90, 84, 100))
        assert m.next() == bytes((0x90, 84, 100))
        m.put(0x46c76de0, channel, 1)
        m.call("lb_sync")
        assert m.next() == bytes((0x80, 84, 0))
        assert m.get("lb_internal_held") == 0
        assert m.capture((0x90, 84, 0), 0x4009f8c2) == 0
        assert m.get(0x400b967c) == 0
    print("  [ok] all route transitions, channel changes/OFF, original-destination release and late-release suppression")


def fixture(source, dest, length=6, control=None, all_tracks=False):
    import ab_fixture
    from hw import ot_project as otp
    ab_fixture.prepare(source, dest)
    for path in dest.glob("bank*.work"):
        def mutate(data):
            for part in range(8):
                base = otp.PART_BASE + part * otp.PART_STRIDE + 9
                for t in range(8):
                    at = base + 0x3e2 + 32 * t
                    data[at:at+32] = bytes.fromhex(
                        "54 64 06 40 40 40 20 20 20 00 00 00 40 00 00 05 "
                        "00 06 40 00 46 00 00 40 00 00 00 00 00 00 04 00")
                    data[at+2] = length
                    setup = base + 0x4e2 + 36 * t
                    data[setup] = t + 1 if all_tracks else (1 if t == 0 else 0)
                    data[setup + 12] = 0  # EXT, Follow flags off
                    data[setup + 2] = 128  # PROG OFF
                    data[setup + 20] = 46  # CTRL1 CC1 setup, runtime +0x34
                    if control:
                        data[at+6:at+12] = bytes(6)  # all MIDI LFO speed/depth
                        if t == 0:
                            data[setup+20] = 34  # FX1 parameter 1: FILTER BASE
                            data[at+20] = 64
                            if control == "lfo":
                                data[at+6], data[at+9] = 32, 24  # SPD1, DEP1
                                data[setup+6] = 20  # PMTR = CC1
                                data[setup+9] = 0  # TRI
                                data[setup+30] = 4  # MULT x16
                                data[setup+33] = 0  # FREE
                if control:
                    data[base] = 4  # T1 FX1 FILTER
                    page = base + 0x11a
                    data[page+12:page+18] = bytes((20, 100, 0, 0, 0, 0))
            for p in range(16):
                end = 0x16 + (p + 1) * 0x8eec
                data[end-11:end-6] = bytes((16, 2, 64, 2, 0))
                for t in range(8):
                    at = 0x492e + p * 0x8eec + t * 0x8b9
                    assert data[at:at+4] == b"MTRA"
                    data[at+9:at+33] = bytes(24)
                    data[at+0x39:at+0x839] = b"\xff" * 2048
                    data[at+0x31:at+0x33] = bytes((16, 2))
                    if p == 0 and (t == 0 or all_tracks):
                        data[at+9:at+17] = (1).to_bytes(8, "big")
                        data[at+0x39:at+0x3c] = bytes((84, 100, length))
                        data[at+0x39+20] = 70
                        if control:
                            data[at+9:at+17] = (5 if control != "knob" else 0).to_bytes(8, "big")
                            data[at+0x39+20] = 32
                            data[at+0x39+64+20] = 96  # step 3 CC lock
        otp._bank_write(dest, int(path.stem[4:]), mutate, guard=False)
    values = dict(TRACK=7, MIDI_MODE=0, MIDI_AUTO_CHANNEL=10,
                  MIDI_AUDIO_TRK_CC_IN=1, MIDI_AUDIO_TRK_NOTE_IN=1,
                  # Isolate MIDI-track routing from audio CC Feedback.
                  MIDI_AUDIO_TRK_CC_OUT=0, MIDI_AUDIO_TRK_NOTE_OUT=0,
                  MIDI_CLOCK_RECEIVE=0, MIDI_TRANSPORT_RECEIVE=0,
                  MIDI_CLOCK_SEND=0, MIDI_TRANSPORT_SEND=0,
                  MIDI_PROGRAM_CHANGE_SEND=0, PATTERN_TEMPO_ENABLED=0,
                  TEMPOx24=2880)
    values.update({f"MIDI_TRIG_CH{i+1}": i for i in range(8)})
    if control == "knob":
        values.update(TRACK=0, MIDI_MODE=1)
    for path in dest.glob("project.*"):
        raw = re.sub(rb"\[SAMPLE\].*?\[/SAMPLE\]\r?\n", b"", path.read_bytes(), flags=re.S)
        for key, value in values.items():
            raw, count = re.subn(rb"(?m)^" + key.encode() + rb"=[^\r\n]*",
                                 key.encode() + b"=" + str(value).encode(), raw)
            assert count == 1, key
        path.write_bytes(raw)


def decode(raw, start=0):
    status, data, result = None, [], []
    for index, byte in enumerate(raw):
        if byte >= 0xf8:
            continue
        if byte & 128:
            status, data = (byte if byte < 0xf0 else None), []
        elif status is not None:
            data.append(byte)
            if len(data) == (1 if status & 0xf0 in (0xc0, 0xd0) else 2):
                if index >= start:
                    result.append([status, *data])
                data = []
    return result


def transport_midi(capture, log):
    """Keep every transport message, retaining pre-transport running status.

    CC Feedback can send boot defaults before the project disables audio
    output. Preserve the complete file, but don't count boot as track output.
    """
    raw = capture.read_bytes()
    match = re.search(r'midi out\s+: (\d+) byte\(s\) on UART0 \((\d+) after the transport start\)', log)
    assert match, 'missing transport capture boundary'
    total, after = map(int, match.groups())
    assert total == len(raw) and 0 <= after <= total
    return decode(raw, start=total-after)


def port_gate(source, remix):
    import hashlib
    import emu_card
    # Keep standalone and USB receipts/captures separate.
    assert re.fullmatch(r"[a-z0-9-]+", remix), remix
    out = ROOT / "out" / remix
    out.mkdir(parents=True, exist_ok=True)
    fixture(source, out / "project")
    card, _ = emu_card.stage_project(out / "project", "OCTABAM", "LOOPBACK", tree=out / "tree")
    (out / "card.img").write_bytes(card)
    sym = symbols()
    outcomes = {}
    for label in ("off", "internal", "int-only", "uart", "disable", "channel", "channel-off", "stop"):
        log, capture = out / f"{label}.log", out / f"{label}.midi"
        dumps = {key: out / f"{label}-{key}.bin" for key in ("level", "note", "held", "stats")}
        cmd = [str(ROOT / "out/emu/ot_emu"), "--image", str(ROOT / "out/mainos_bus.bin"),
               "--card", str(out / "card.img"), "--set", "OCTABAM", "--project", "LOOPBACK",
               "--sequencer", "--internal-clock", "--frames", "1200", "--load-ms", "90000",
               "--midi-out", str(capture), "--watch-mem", "0x400d64c2,1;0x80000c50,1",
               "--mem-dump", f"0x80000c50,16={dumps['level']};0x400d64c2,8={dumps['note']};"
               f"0x46c7fe4c,64={dumps['held']};{sym['lb_head']:#x},24={dumps['stats']}"]
        if label in ("internal", "int-only", "disable", "channel", "channel-off", "stop"):
            cmd += ["--step", f"-:call:{sym['lb_dest_write']:#x},0,2"]
        if label == "int-only":
            cmd += ["--step", f"-:call:{sym['lb_dest_write']:#x},0,1"]
        if label in ("channel", "channel-off"):
            channel = 2 if label == "channel" else 0
            cmd += ["--step", f"4:dump:0x400d64c2,1={out / (label + '-before.bin')}",
                    "--step", f"5:poke:0x40171442={channel}",
                    "--step", f"5:poke:0x46c76de0={channel}"]
        if label == "disable":
            cmd += ["--step", f"4:dump:0x400d64c2,1={out / 'before-disable.bin'}",
                    "--step", f"5:call:{sym['lb_dest_write']:#x},0,0"]
        if label == "stop":
            fixture(source, out / "held-project", length=127)
            held_card, _ = emu_card.stage_project(out / "held-project", "OCTABAM", "LOOPBACK", tree=out / "held-tree")
            (out / "held-card.img").write_bytes(held_card)
            cmd[cmd.index("--card") + 1] = str(out / "held-card.img")
            cmd += ["--step", f"60:dump:0x400d64c2,1={out / 'before-stop.bin'}",
                    "--step", "80:poke:0x80000029=1", "--step", "80:call:0x4000a1e0,0"]
        if label == "uart":
            midi = out / "reference.midi"
            midi.write_text("40 b0 2e 46\n80 90 54 64\n500 80 54 00\n")
            cmd += ["--midi", str(midi)]
        with log.open("w") as stream:
            result = subprocess.run(cmd, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, timeout=180)
        text = log.read_text()
        assert result.returncode == 0 and "run ended REACHED" in text, str(log)
        assert "load run ended: LOAD PROJECT handled" in text, str(log)
        outcomes[label] = {key: path.read_bytes().hex() for key, path in dumps.items()}
        outcomes[label]["midi"] = transport_midi(capture, text)
        print(f"  [port] {label}: level={dumps['level'].read_bytes()[0]}, "
              f"stats={outcomes[label]['stats']}, MIDI={outcomes[label]['midi']}", flush=True)
    off, internal, uart = (outcomes[k] for k in ("off", "internal", "uart"))
    assert off["level"][:2] == "7f"
    assert internal["level"] == uart["level"] and internal["level"][:2] == "46"
    assert internal["note"] == uart["note"] == "ff" * 8
    assert internal["held"] == uart["held"] == "00" * 64
    assert internal["midi"] == off["midi"], "internal mirror changed external MIDI"
    assert (out / "internal.midi").read_bytes() == (out / "off.midi").read_bytes(), "complete UART capture changed"
    assert outcomes["int-only"]["level"] == internal["level"]
    assert outcomes["int-only"]["note"] == internal["note"]
    assert outcomes["int-only"]["held"] == internal["held"]
    assert outcomes["int-only"]["midi"] == [], outcomes["int-only"]
    for label in ("channel", "channel-off"):
        assert (out / (label + "-before.bin")).read_bytes() == bytes((84,))
        assert outcomes[label]["note"] == "ff" * 8
        assert outcomes[label]["held"] == "00" * 64
        assert [0x80, 84, 0] in outcomes[label]["midi"], outcomes[label]
        assert [0x90, 84, 0] not in outcomes[label]["midi"], "late release duplicated cleanup"
    assert [0x90, 84, 100] in internal["midi"]
    assert [0xb0, 46, 70] in internal["midi"]
    assert outcomes["disable"]["note"] == outcomes["stop"]["note"] == "ff" * 8
    assert outcomes["disable"]["held"] == outcomes["stop"]["held"] == "00" * 64
    assert (out / "before-stop.bin").read_bytes() == bytes((84,)), "STOP test must start with a held note"
    assert (out / "before-disable.bin").read_bytes() == bytes((84,)), "OFF test must start with a held note"
    stats = bytes.fromhex(internal["stats"])
    vals = [int.from_bytes(stats[i:i+4], "big") for i in range(0, 24, 4)]
    assert vals[0] == vals[1] and vals[2] == vals[3] >= 3 and vals[4] == 0, vals
    receipt = {"image_sha256": hashlib.sha256((ROOT / "out/mainos_bus.bin").read_bytes()).hexdigest(),
               "runtime_sha256": hashlib.sha256((ROOT / "out/platform/runtime/runtime.bin").read_bytes()).hexdigest(),
               "stock_sha256": hashlib.sha256((ROOT / "out/raw/section_3_MAIN_OS.bin").read_bytes()).hexdigest(),
               "outcomes": outcomes, "scope": "ColdFire RTOS/sequencer and UART receiver; no DSP/audio or hardware proof"}
    (out / "result.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print("  [ok] real sequencer -> internal queue -> MIDI task -> audio state matches UART input")


def routing_port_gate(source, remix):
    """Eight simultaneous stock sequencer sources using mixed destinations."""
    import hashlib
    import emu_card
    assert re.fullmatch(r"[a-z0-9-]+", remix), remix
    out = ROOT / "out" / remix / "routing"
    out.mkdir(parents=True, exist_ok=True)
    fixture(source, out / "project", all_tracks=True)
    card, _ = emu_card.stage_project(out / "project", "OCTABAM", "LOOPBACK", tree=out / "tree")
    (out / "card.img").write_bytes(card)
    sym = symbols()
    routes = (0, 1, 2, 0, 1, 2, 0, 1)
    dumps = {k: out / (k + ".bin") for k in ("level", "note", "held", "stats")}
    cmd = [str(ROOT / "out/emu/ot_emu"), "--image", str(ROOT / "out/mainos_bus.bin"),
           "--card", str(out / "card.img"), "--set", "OCTABAM", "--project", "LOOPBACK",
           "--sequencer", "--internal-clock", "--frames", "1200", "--load-ms", "90000",
           "--midi-out", str(out / "wire.midi"), "--mem-dump",
           f"0x80000c50,16={dumps['level']};0x400d64c2,8={dumps['note']};"
           f"0x46c7fe4c,64={dumps['held']};{sym['lb_head']:#x},24={dumps['stats']}"]
    for track, route in enumerate(routes):
        cmd += ["--step", f"-:call:{sym['lb_dest_write']:#x},{track},{route}"]
    with (out / "run.log").open("w") as log:
        result = subprocess.run(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=180)
    text = (out / "run.log").read_text()
    assert result.returncode == 0 and "run ended REACHED" in text
    assert "load run ended: LOAD PROJECT handled" in text
    midi = transport_midi(out / "wire.midi", text)
    has_scenes = b'scn_ccnote' in subprocess.check_output(['m68k-elf-nm', str(ROOT/'out/platform/runtime/runtime.elf')])
    for track, route in enumerate(routes):
        events = [msg for msg in midi if msg[0] & 15 == track]
        note_on, cc, note_off = [0x90 | track, 84, 100], [0xb0 | track, 46, 70], [0x90 | track, 84, 0]
        # MIDI Scenes deliberately sends the CC loop before note-on.
        expected = [cc, note_on, note_off] if has_scenes else [note_on, cc, note_off]
        assert events == ([] if route == 1 else expected), (track, route, events)
        assert dumps["level"].read_bytes()[track * 2] == (70 if route else 127), (track, route)
    assert dumps["note"].read_bytes() == bytes([255] * 8)
    assert dumps["held"].read_bytes() == bytes(64)
    stats = dumps["stats"].read_bytes()
    counts = [int.from_bytes(stats[i:i+4], "big") for i in range(0, 24, 4)]
    assert counts[:4] == [15] * 4 and counts[4] == 0, counts
    receipt = dict(image_sha256=hashlib.sha256((ROOT / "out/mainos_bus.bin").read_bytes()).hexdigest(),
                   routes=routes, midi=midi, levels=list(dumps["level"].read_bytes()[::2]), stats=counts,
                   scope="eight-track ColdFire RTOS routing; no rendered audio or hardware proof")
    (out / "result.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print("  [ok] eight simultaneous tracks: exact mixed-route wire events, audio levels and clean note release", flush=True)


def controls_gate(source, remix, only=None):
    """Real MIDI locks/LFO and the panel's encoder routine into T1 FILTER BASE."""
    import hashlib
    import emu_card
    assert re.fullmatch(r"[a-z0-9-]+", remix), remix
    out = ROOT / "out" / remix / "controls"
    out.mkdir(parents=True, exist_ok=True)
    sym, outcomes = symbols(), {}
    kinds = (only,) if only else ("locks", "lfo", "knob")
    for kind in kinds:
        fixture(source, out / f"{kind}-project", control=kind)
        card, _ = emu_card.stage_project(out / f"{kind}-project", "OCTABAM", "LOOPBACK", tree=out / f"{kind}-tree")
        card_path = out / f"{kind}-card.img"
        card_path.write_bytes(card)
        modes = {"locks": ("off", "on", "int"), "lfo": ("off", "on", "int", "receive-off"),
                 "knob": ("off", "on", "int", "incoming", "direct")}[kind]
        for mode in modes:
            label = f"{kind}-{mode}"
            log, capture = out / f"{label}.log", out / f"{label}.midi"
            state, stats = out / f"{label}-filter.bin", out / f"{label}-stats.bin"
            cmd = [str(ROOT / "out/emu/ot_emu"), "--image", str(ROOT / "out/mainos_bus.bin"),
                   "--card", str(card_path), "--set", "OCTABAM", "--project", "LOOPBACK",
                   "--sequencer", "--internal-clock", "--frames", "1200", "--load-ms", "90000",
                   "--midi-out", str(capture), "--watch-mem", "0x80000822,1",
                   "--mem-dump", f"0x80000822,1={state};{sym['lb_head']:#x},24={stats}"]
            # Every comparison takes one native setup call. Omitting it for
            # EXT or doing two for INT shifts the free-running LFO's phase
            # relative to the finite capture and can add a final CC to EXT.
            destination = 0 if mode == "off" else 1 if mode == "int" else 2
            cmd += ["--step", f"-:call:{sym['lb_dest_write']:#x},0,{destination}"]
            if mode == "receive-off":
                cmd += ["--step", "-:poke:0x80000049=0"]
            if kind == "knob":
                # CTRL1 page, encoder C = CC1, +16 from the Part's 64.
                cmd += ["--step", "-:poke:0x460d1687=3"]
                if mode in ("incoming", "direct"):
                    # Auto-channel CC36 changes M1 CC1 through the generic
                    # setter. Its external CC must not become new loopback.
                    midi_in = out / "incoming.midi"
                    midi_in.write_text("400 ba 24 50\n")
                    cmd += ["--midi", str(midi_in), "--step",
                            f"-:poke:0x8000004d={1 if mode == 'direct' else 0}"]
                else:
                    cmd += ["--step", "400:call:0x40055008,2,16"]
            with log.open("w") as stream:
                result = subprocess.run(cmd, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, timeout=180)
            text = log.read_text()
            assert result.returncode == 0 and "run ended REACHED" in text, str(log)
            assert "load run ended: LOAD PROJECT handled" in text, str(log)
            raw = stats.read_bytes()
            counts = [int.from_bytes(raw[i:i+4], "big") for i in range(0, 24, 4)]
            midi = transport_midi(capture, text)
            ccs = [msg[2] for msg in midi if msg[:2] == [0xb0, 34]]
            # Only the receiver's generic parameter writer, excluding load and
            # frame refresh stores. Compare every value, in order, with the wire.
            writes = [int(value, 16) for value in re.findall(
                r"\[0x80000822\] <- (0x[0-9a-f]+|0) \(1\) at pc 0x40054e22", text)]
            expected = outcomes[f"{kind}-on"]["cc_values"] if mode == "int" else (ccs if mode == "on" else [])
            assert writes == expected, (label, writes, expected)
            outcomes[label] = dict(filter=state.read_bytes()[0], stats=counts, midi=midi, cc_values=ccs, filter_writes=writes)
            print(f"  [controls] {label}: filter={outcomes[label]['filter']}, CC34={ccs}, stats={counts}", flush=True)
        off, on = outcomes[f"{kind}-off"], outcomes[f"{kind}-on"]
        assert off["filter"] == 20, off
        assert on["cc_values"] and on["filter"] == on["cc_values"][-1], on
        assert on["midi"] == off["midi"], f"{kind}: external MIDI changed"
        assert (out / f"{kind}-on.midi").read_bytes() == (out / f"{kind}-off.midi").read_bytes(), f"{kind}: complete UART capture changed"
        assert on["stats"][2] == on["stats"][3] > 0 and on["stats"][4] == 0, on
        assert off["stats"][2] == 0, off
        internal = outcomes[f"{kind}-int"]
        assert internal["midi"] == [] and internal["filter"] == on["filter"], internal
        assert internal["stats"][2:5] == on["stats"][2:5], internal
        if kind == "locks":
            assert on["cc_values"] == [32, 96], on
            assert 32 in on["filter_writes"] and 96 in on["filter_writes"], on
        if kind == "lfo":
            assert len(set(on["cc_values"])) >= 8, on
            assert len(set(on["filter_writes"])) >= 8, on
            assert outcomes["lfo-receive-off"]["filter"] == 20
            assert outcomes["lfo-receive-off"]["stats"][3] > 0
        if kind == "knob":
            assert 80 in on["cc_values"] and 80 in on["filter_writes"], on
            incoming = outcomes["knob-incoming"]
            assert incoming["cc_values"] == [80] and incoming["filter"] == 20, incoming
            assert incoming["stats"][2] == 0, incoming
            direct = outcomes["knob-direct"]
            assert direct["midi"] == [[0xb0, 36, 80]] and direct["filter"] == 20, direct
            assert direct["stats"][2] == 0, direct
    receipt = dict(image_sha256=hashlib.sha256((ROOT / "out/mainos_bus.bin").read_bytes()).hexdigest(),
                   runtime_sha256=hashlib.sha256((ROOT / "out/platform/runtime/runtime.bin").read_bytes()).hexdigest(),
                   stock_sha256=hashlib.sha256((ROOT / "out/raw/section_3_MAIN_OS.bin").read_bytes()).hexdigest(),
                   outcomes=outcomes, scope="ColdFire control state; no rendered audio or hardware proof")
    (out / (f"result-{only}.json" if only else "result.json")).write_text(json.dumps(receipt, indent=2) + "\n")
    print(f"  [ok] filter control scenarios passed: {', '.join(kinds)}")


def owned_counts(m):
    """Audit the cleanup shortcut against actual ownership, including EXT."""
    expected = [0] * 8
    for owner in m.u.mem_read(m.sym['lb_owned'], 2048):
        if owner & 3:
            expected[(owner >> 4) - 1] += 1
    actual = [m.get(m.sym['lb_owned_counts'] + 2*t, 2) for t in range(8)]
    assert actual == expected, (actual, expected)
    return actual


def cleanup_machine_gate():
    for track in range(8):
        for route in range(3):
            m = Machine()
            m.put(m.sym['lb_routes'] + track, route, 1)
            assert owned_counts(m) == [0]*8
            m.capture((0x93, 60, 100), track=track)
            assert owned_counts(m)[track] == 1
            # Duplicate ownership does not add a count or change the owner.
            other = (track + 1) % 8
            m.capture((0x93, 60, 100), track=other)
            assert owned_counts(m)[track] == 1
            assert owned_counts(m)[other] == 0
            m.capture((0xb3, 34, 99), 0x4009fef2, track)
            assert owned_counts(m)[track] == 1
            # Release provenance can name a different track: use saved owner.
            m.capture((0x83, 60, 0), 0x4009f8c2, other)
            assert owned_counts(m) == [0]*8
            while m.get('lb_tail') != m.get('lb_head'):
                m.next()
            m.capture((0x93, 61, 100), track=track)
            assert owned_counts(m)[track] == 1
            m.call('lb_flush', (track,))
            assert owned_counts(m) == [0]*8
            tombstones = bytes(m.u.mem_read(m.sym['lb_owned'], 2048))
            accepted, external = m.get('lb_accepted'), m.get(0x400b967c)
            # Repeated empty cleanup preserves late-release suppression.
            reads = []
            handle = m.u.hook_add(UC_HOOK_MEM_READ,
                lambda u, access, addr, size, value, data: reads.append(addr),
                begin=m.sym['lb_owned'], end=m.sym['lb_owned'] + 2047)
            m.call('lb_flush', (track,))
            m.u.hook_del(handle)
            assert not reads, 'empty cleanup scanned the ownership table'
            assert bytes(m.u.mem_read(m.sym['lb_owned'], 2048)) == tombstones
            assert m.get('lb_accepted') == accepted
            assert m.get(0x400b967c) == external == (3 if route != 1 else 0)
            assert m.capture((0x83, 61, 0), 0x4009f8c2, track) == 0
            assert owned_counts(m) == [0]*8
            # A fresh owner can overwrite a tombstone before its late release.
            m.capture((0x93, 61, 100), track=track)
            m.call('lb_flush', (track,))
            assert owned_counts(m) == [0]*8
            m.capture((0x93, 61, 100), track=other)
            assert owned_counts(m)[other] == 1
            m.capture((0x93, 61, 0), 0x4009f8c2, other)
            assert owned_counts(m) == [0]*8
    print('  [ok] per-track cleanup counts: EXT/INT/BOTH, duplicates, controls, original owner, repeated cleanup and late releases')

    for route in (1, 2):
        m = Machine()
        m.put('lb_routes', route, 1)
        # Full non-release queue: INT leaves only a tombstone; BOTH owns EXT.
        for n in range(127):
            m.capture((0xb0, 34, n), 0x4009fef2)
        m.capture((0x90, 60, 100))
        assert owned_counts(m)[0] == (1 if route == 2 else 0)
        m.call('lb_flush', (0,))
        assert owned_counts(m) == [0]*8
        assert m.get(0x400b967c) == (3 if route == 2 else 0)
        assert m.capture((0x80, 60, 0), 0x4009f8c2) == 0
        assert owned_counts(m) == [0]*8

    m = Machine()
    # External ownership can exceed 255; counters must not wrap at one byte.
    for channel in range(16):
        for pitch in range(128):
            m.capture((0x90 | channel, pitch, 100), track=7)
    assert owned_counts(m)[7] == 2048
    for channel in range(16):
        for pitch in range(128):
            m.capture((0x80 | channel, pitch, 0), 0x4009f8c2, track=0)
    assert owned_counts(m) == [0]*8
    print('  [ok] dropped INT/BOTH ownership, release suppression, and 2048-entry external count/release')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("remix", nargs="?", default="midi-loopback")
    parser.add_argument("--project", type=pathlib.Path)
    parser.add_argument("--routing", action="store_true", help="run the simultaneous eight-track project scenario")
    parser.add_argument("--controls", action="store_true", help="run filter-control project scenarios instead of note lifecycle scenarios")
    parser.add_argument("--control-kind", choices=("locks", "lfo", "knob"), help="rerun one control group; requires --controls")
    args = parser.parse_args()
    if args.routing and (not args.project or args.controls):
        parser.error("--routing requires --project and cannot combine with --controls")
    if args.controls and not args.project:
        parser.error("--controls requires --project DIR")
    if args.control_kind and not args.controls:
        parser.error("--control-kind requires --controls")
    machine_gate()
    routing_machine_gate()
    cleanup_machine_gate()
    if args.project:
        if args.routing:
            routing_port_gate(args.project, args.remix)
        elif args.controls:
            controls_gate(args.project, args.remix, args.control_kind)
        else:
            port_gate(args.project, args.remix)
    else:
        print("  [not run] full RTOS/project gate: supply --project DIR")


if __name__ == "__main__":
    main()
