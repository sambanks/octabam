#!/usr/bin/env python3
"""USB-MIDI transmit: a burst longer than one transfer is queued whole, not cut (#1016).

    REMIX=<name> python3 tools/verify/verify_usbmidi_tx.py

Both senders (midi_send's detour and the priority byte sender's) append whole
messages to usbmidi.s's TX ring, and the kick moves whole messages, at most
TX_SND bytes, into one transfer. Until 4 Nov 2026 the queue was one 256-byte
accumulator: CC 61's 283-CC dump (849 MIDI bytes) reached the host with 102 to
172 messages on an MKI (xynta's report). Under unicorn, on the built image's
stock midi_send (0x40010bc8, whose entry is the USB detour), with EP2 IN busy
so nothing leaves the ring:

  * the 283 CCs are all queued: 849 bytes, no drop;
  * filling the ring past TX_RING drops exactly the messages that do not fit,
    and counts each in usbmidi_tx_drops;
  * with EP2 IN free, one more send kicks one transfer of whole messages, at
    most TX_SND bytes, in order: the encoder's first USB-MIDI event is the
    first CC, and the ring keeps the rest;
  * a message longer than TX_SND is dropped and counted, never split.

What this cannot see: the host's EP2 IN timing (how fast the ring drains), and
a clock byte's latency behind a backlog. The reporter's port bench and MKI runs
(283 of 283, 1,981 of 1,981) are the measurement of the drain.
"""
import json
import os
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import toolpath  # noqa: E402,F401
try:
    from unicorn import Uc, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
    from unicorn.m68k_const import UC_CPU_M68K_CFV4E, UC_M68K_REG_A7, UC_M68K_REG_SR, UC_M68K_REG_PC
except ImportError:
    print("  [SKIP] verify_usbmidi_tx: no unicorn (the .venv: make emu-setup)")
    sys.exit(0)
from midi_machine import dram_map_size  # noqa: E402
from remix import registry  # noqa: E402

MIDI_SEND = 0x40010bc8      # midi_send(len, buf): the USB detour at its entry
ENC_OUT = 0x4ecc8000        # the encoder's USB-MIDI event buffer
STACK, DONE, MSG = 0x47008000, 0x4700fff0, 0x47001000
TX_RING, TX_SND = 4096, 512


def symbols():
    nm = subprocess.check_output(["m68k-elf-nm", str(ROOT / "out/platform/runtime/runtime.elf")], text=True)
    return {n: int(a, 16) for a, n in re.findall(r"^([0-9a-f]+) [TtDdBb] (usbmidi_\w+)$", nm, re.M)}


class Machine:
    def __init__(self):
        self.sym = symbols()
        u = self.u = Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN)
        u.ctl_set_cpu_model(UC_CPU_M68K_CFV4E)
        layout = json.loads((ROOT / "out/platform/layout.json").read_text())
        dram = dram_map_size(layout)
        regions = [(0x40000000, dram), (0x46000000, 0x200000), (0x46c70000, 0x20000), (0x47000000, 0x10000),
                   (0x10000000, 0x200000), (0x80000000, 0x10000), (0xfc000000, 0x1000000)]
        if 0x40000000 + dram <= 0x4ec80000:
            regions.append((0x4ec80000, 0x80000))   # the EP2 dTDs and the encoder's buffer
        for a, size in regions:
            u.mem_map(a, size)
        u.mem_write(0x40000400, (ROOT / "out/mainos_bus.bin").read_bytes())
        u.mem_write(layout["base"], (ROOT / "out/platform/runtime/runtime.bin").read_bytes())
        u.hook_add(UC_HOOK_CODE, lambda uc, pc, n, d: uc.emu_stop() if pc == DONE else None)
        self.put(0x400b966c, 0x47004000)    # the UART TX ring midi_send's DIN half writes
        self.put(0x400b9678, 4095)
        self.put("usbmidi_up", 1, 1)
        # stock's encode-and-prime (0x4001d3ee) loads the EP2 IN queue head from this
        # global and writes its next-dTD word; unset it is 0 and the write is at 0x8
        self.put(0x46c8ce1c, 0x4ec94900)

    def put(self, at, value, size=4):
        self.u.mem_write(self.sym.get(at, at), value.to_bytes(size, "big"))

    def get(self, at, size=4):
        return int.from_bytes(self.u.mem_read(self.sym.get(at, at), size), "big")

    def send(self, msg):
        u = self.u
        self.put(0x400b967c, 0)             # the DIN ring empty again: only USB is under test
        u.mem_write(MSG, bytes(msg))
        u.reg_write(UC_M68K_REG_SR, 0x2000)
        u.reg_write(UC_M68K_REG_A7, STACK)
        self.put(STACK, DONE)
        self.put(STACK + 4, len(msg))
        self.put(STACK + 8, MSG)
        u.emu_start(MIDI_SEND, 0, count=2_000_000)
        assert u.reg_read(UC_M68K_REG_PC) == DONE, hex(u.reg_read(UC_M68K_REG_PC))


def main():
    remix = os.environ.get("REMIX") or (sys.argv[1] if len(sys.argv) > 1 else None)
    if "USB" not in registry.remix(remix).modules:
        print("  [SKIP] verify_usbmidi_tx: the remix has no USB")
        return 0
    fails = []

    def check(what, ok, detail=""):
        print(f"  [{'PASS' if ok else 'FAIL'}] {what}{'  ' + detail if detail else ''}")
        if not ok:
            fails.append(what)

    ccs = [(0xb0 | (i % 16), i % 120, (3 * i) & 0x7f) for i in range(283)]

    # 1. CC 61's dump while a transfer is in flight: every message queued
    m = Machine()
    m.put("usbmidi_tx_busy", 1, 1)
    for cc in ccs:
        m.send(cc)
    check("283 CCs with EP2 IN busy: 849 bytes queued, none dropped",
          m.get("usbmidi_tx_acc_len", 2) == 849 and m.get("usbmidi_tx_drops") == 0,
          f"queued {m.get('usbmidi_tx_acc_len', 2)}, drops {m.get('usbmidi_tx_drops')}")
    # 2. past the ring: exactly the records that do not fit are dropped, each counted
    fit = TX_RING // 5                      # 5-byte records: 2-byte length + 3-byte CC
    for i in range(fit - 283 + 50):
        m.send((0xb0, 1, i & 0x7f))
    check(f"the ring holds {fit} 3-byte messages; the next 50 are dropped and counted",
          m.get("usbmidi_tx_acc_len", 2) == 3 * fit and m.get("usbmidi_tx_drops") == 50,
          f"queued {m.get('usbmidi_tx_acc_len', 2)}, drops {m.get('usbmidi_tx_drops')}")
    # 3. EP2 IN free: one send kicks one transfer of whole messages, in order
    m = Machine()
    m.put("usbmidi_tx_busy", 1, 1)
    for cc in ccs:
        m.send(cc)
    m.u.mem_write(ENC_OUT, bytes(16))
    m.put("usbmidi_tx_busy", 0, 1)
    m.send((0xb0, 0, 0))                    # appended behind the 283, then the kick
    n = TX_SND // 3                         # whole 3-byte messages in one transfer
    first = ccs[0]
    check(f"the kick sends {n} whole messages ({3 * n} bytes) as one transfer, the oldest first",
          m.get("usbmidi_tx_snd_len", 2) == 3 * n and m.get("usbmidi_tx_busy", 1) == 1
          and bytes(m.u.mem_read(ENC_OUT, 4)) == bytes([first[0] >> 4]) + bytes(first),
          f"snd {m.get('usbmidi_tx_snd_len', 2)}, busy {m.get('usbmidi_tx_busy', 1)}, "
          f"first event {bytes(m.u.mem_read(ENC_OUT, 4)).hex()}")
    check("the ring keeps the rest for the next completion",
          m.get("usbmidi_tx_acc_len", 2) == 3 * (284 - n), f"queued {m.get('usbmidi_tx_acc_len', 2)}")
    # 4. a message longer than TX_SND can never go out whole: dropped, counted
    m = Machine()
    m.put("usbmidi_tx_busy", 1, 1)
    m.send(bytes([0xf0]) + bytes(TX_SND) + bytes([0xf7]))
    check(f"a {TX_SND + 2}-byte SysEx is dropped and counted, not split",
          m.get("usbmidi_tx_acc_len", 2) == 0 and m.get("usbmidi_tx_drops") == 1,
          f"queued {m.get('usbmidi_tx_acc_len', 2)}, drops {m.get('usbmidi_tx_drops')}")
    print(f"verify_usbmidi_tx: {'OK' if not fails else str(len(fails)) + ' FAILED'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
