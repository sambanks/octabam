#!/usr/bin/env python3
"""USB-MIDI usb_isr hook: ENDPTCOMPLETE is read once, and only the bits read are
cleared and handled (#1017).

    REMIX=<name> python3 tools/verify/verify_usbmidi_isr.py

usbmidi_rx_isr_shim (the detour at 0x4001e606) reads ENDPTCOMPLETE, w1c's the EP2
bits it saw (OUT = bit 2, IN = bit 18) in one write and handles both from that
snapshot. #1017: the hand-over shim it replaced read the register a second time and
took bit 2 the 64-byte way, so a transfer completing between the reads was never
decoded and the next one replayed an older transfer's tail.

The gate runs the shim on the booted image under unicorn. The shim's closing
`jmp 0x4001e60c` is stopped there; the EPCOMPLETE reads and writes and the call to
the firmware's TX encoder are recorded; midi_rx_enqueue is recorded for the bytes
decoded.

  * one read of ENDPTCOMPLETE per entry, in every case below;
  * the write is exactly the EP2 bits seen (EP0 / EP1 bits are left alone), and no
    write when none is set;
  * a 16-byte and a 464-byte transfer at high speed: every byte once, in order, the
    512-byte dTD primed again (the 464-byte case is the one the second read lost);
  * an errored dTD: nothing decoded, usbmidi_rx_errs + 1;
  * full speed: the stock 64-byte prime;
  * an EP2 IN completion: usbmidi_tx_busy cleared and the queued bytes handed to
    the encoder as one transfer;
  * session down (usbmidi_up = 0): the bits are cleared, nothing is decoded or sent.

What this cannot see: the race's timing on the unit, and that a completion after
the read raises a new UI interrupt (inferred from stock clearing USBSTS.UI at
0x4001e600, before the hook).
"""
import os
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
try:
    import emu_bringup as emu
    from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
    from unicorn.m68k_const import UC_M68K_REG_A7, UC_M68K_REG_PC
except ImportError:
    print("  [SKIP] verify_usbmidi_isr: no unicorn (the .venv: make emu-setup)")
    sys.exit(0)

from remix import registry  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
IMAGE = ROOT / "out/mainos_bus.bin"
RUNTIME = ROOT / "out/platform/runtime/runtime.elf"
STOCK_TAIL = 0x4001e60c     # where the shim's closing jmp goes
ENCODER = 0x4001d204        # usb_midi_encoder(len, buf)
RX_ENQUEUE = 0x40092bbc     # midi_rx_enqueue(byte as a long)
FIFO_COUNT = 0x46100b7c
RX_BUF = 0x4ecc9000
EP2_RX_TD = 0x4ec953e4      # token: remaining << 16, status in 7:0
EPCOMPLETE = 0xfc0b01bc
TD_512 = 0x02008080
TD_STOCK64 = 0x00408080
EP2_OUT, EP2_IN = 0x4, 0x40000


def token(remaining, status=0):
    return (remaining << 16) | status


def main():
    remix = os.environ.get("REMIX") or (sys.argv[1] if len(sys.argv) > 1 else None)
    if "USB" not in registry.remix(remix).modules:
        print("  [SKIP] verify_usbmidi_isr: the remix has no USB")
        return 0
    if not IMAGE.is_file() or not RUNTIME.is_file():
        print("  [FAIL] verify_usbmidi_isr: no out/mainos_bus.bin or runtime (make bus)")
        return 1
    nm = subprocess.run(["m68k-elf-nm", str(RUNTIME)], capture_output=True, text=True).stdout
    syms = {f[2]: int(f[0], 16) for f in (l.split() for l in nm.splitlines()) if len(f) == 3}
    need = ("usbmidi_rx_isr_shim", "usbmidi_rx_state", "usbmidi_rx_errs", "usbmidi_up", "usbmidi_tx_busy",
            "usbmidi_tx_acc_len", "usbmidi_tx_acc", "usbmidi_tx_snd_len", "usbmidi_tx_snd")
    missing = [s for s in need if s not in syms]
    if missing:
        print(f"  [FAIL] verify_usbmidi_isr: the runtime has no {', '.join(missing)}")
        return 1
    ep = {"v": 0}
    emu.EXTRA_OVERRIDES[EPCOMPLETE] = lambda u, a, size: ep["v"]      # the controller register: MMIO, all-ones by default
    uc = emu.boot(str(IMAGE)).uc
    got, reads, writes, encodes = [], [], [], []

    def on_enqueue(u, addr, size, user):
        sp = u.reg_read(UC_M68K_REG_A7)
        got.append(int.from_bytes(u.mem_read(sp + 4, 4), "big") & 0xff)

    def on_tail(u, addr, size, user):             # the shim ends here: back to the caller
        u.reg_write(UC_M68K_REG_PC, emu.CALL_RET)

    def on_encoder(u, addr, size, user):          # record the transfer, return without running it
        sp = u.reg_read(UC_M68K_REG_A7)
        ret = int.from_bytes(u.mem_read(sp, 4), "big")
        ln = int.from_bytes(u.mem_read(sp + 4, 4), "big")
        buf = int.from_bytes(u.mem_read(sp + 8, 4), "big")
        encodes.append(bytes(u.mem_read(buf, ln)))
        u.reg_write(UC_M68K_REG_A7, sp + 4)
        u.reg_write(UC_M68K_REG_PC, ret)

    def on_read(u, access, addr, size, value, user):
        if addr == EPCOMPLETE:
            reads.append(1)

    def on_write(u, access, addr, size, value, user):
        if addr == EPCOMPLETE:
            writes.append(value & 0xffffffff)

    uc.hook_add(UC_HOOK_CODE, on_enqueue, begin=RX_ENQUEUE, end=RX_ENQUEUE)
    uc.hook_add(UC_HOOK_CODE, on_tail, begin=STOCK_TAIL, end=STOCK_TAIL)
    uc.hook_add(UC_HOOK_CODE, on_encoder, begin=ENCODER, end=ENCODER)
    uc.hook_add(UC_HOOK_MEM_READ, on_read, begin=EPCOMPLETE, end=EPCOMPLETE + 3)
    uc.hook_add(UC_HOOK_MEM_WRITE, on_write, begin=EPCOMPLETE, end=EPCOMPLETE + 3)
    rd = lambda a: int.from_bytes(uc.mem_read(a, 4), "big")                       # noqa: E731
    wr = lambda a, v: uc.mem_write(a, (v & 0xffffffff).to_bytes(4, "big"))       # noqa: E731
    fails = []

    def check(what, ok, detail=""):
        print(f"  [{'PASS' if ok else 'FAIL'}] {what}{'  ' + detail if detail else ''}")
        if not ok:
            fails.append(what)

    def note(i):    # a USB-MIDI note-on event (cable 0, CIN 9) and its 3 MIDI bytes
        return bytes([0x09, 0x90, 0x30 + i, 0x40 + i]), bytes([0x90, 0x30 + i, 0x40 + i])

    def run(complete, state=2, tok=None, buf=b"", up=1, acc=b"", busy=0):
        got.clear(); reads.clear(); writes.clear(); encodes.clear()
        ep["v"] = complete
        uc.mem_write(syms["usbmidi_up"], bytes([up]))
        uc.mem_write(syms["usbmidi_tx_busy"], bytes([busy]))
        uc.mem_write(syms["usbmidi_rx_state"], bytes([state]))
        uc.mem_write(syms["usbmidi_tx_acc_len"], len(acc).to_bytes(2, "big"))
        uc.mem_write(syms["usbmidi_tx_acc"], acc)
        wr(FIFO_COUNT, 0)
        wr(EP2_RX_TD, TD_512 if tok is None else tok)
        uc.mem_write(RX_BUF, buf + bytes(512 - len(buf)))
        errs = rd(syms["usbmidi_rx_errs"])
        emu._call(uc, syms["usbmidi_rx_isr_shim"], ())
        return rd(syms["usbmidi_rx_errs"]) - errs

    ev, want = zip(*(note(i) for i in range(4)))
    # 16 bytes at high speed
    run(EP2_OUT, tok=token(512 - 16), buf=b"".join(ev))
    check("16-byte transfer: its 12 MIDI bytes, once each, in order", bytes(got) == b"".join(want), f"got {bytes(got).hex()}")
    check("16-byte transfer: one ENDPTCOMPLETE read, one write of exactly bit 2",
          len(reads) == 1 and writes == [EP2_OUT], f"reads {len(reads)}, writes {[hex(w) for w in writes]}")
    check("16-byte transfer: the 512-byte dTD primed again", rd(EP2_RX_TD) == TD_512, f"token 0x{rd(EP2_RX_TD):08x}")
    # 464 bytes: the transfer the second read used to lose its first 448 bytes of
    head = [note(i) for i in range(4)]
    tail = [note(i) for i in range(4, 6)]
    pad = bytes(464 - 24)
    run(EP2_OUT, tok=token(512 - 464), buf=b"".join(e for e, _ in head) + pad + b"".join(e for e, _ in tail))
    want464 = b"".join(w for _, w in head) + b"".join(w for _, w in tail)
    check("464-byte transfer: every byte once, in order", bytes(got) == want464, f"got {bytes(got).hex()}")
    # EP0 / EP1 bits beside the EP2 bits stay untouched
    run(0x00030003 | EP2_OUT, tok=token(512 - 16), buf=b"".join(ev))
    check("EP0 and EP1 bits set beside EP2: only the EP2 bits written", writes == [EP2_OUT], f"writes {[hex(w) for w in writes]}")
    run(0x00030003)
    check("no EP2 bit set: no write, one read", not writes and len(reads) == 1, f"writes {[hex(w) for w in writes]}")
    # errored dTD
    errs = run(EP2_OUT, tok=token(512 - 16, 0x08), buf=b"".join(ev))
    check("errored transfer: not decoded, usbmidi_rx_errs + 1, primed again",
          not got and errs == 1 and rd(EP2_RX_TD) == TD_512, f"got {bytes(got).hex()}, errs +{errs}")
    # full speed
    run(EP2_OUT, state=0, tok=token(64 - 16), buf=b"".join(ev))
    check("full speed: the 16 bytes decoded and the stock 64-byte prime", bytes(got) == b"".join(want) and rd(EP2_RX_TD) == TD_STOCK64,
          f"token 0x{rd(EP2_RX_TD):08x}")
    # EP2 IN completion with bytes queued
    queued = bytes([0x09, 0x90, 0x3c, 0x64])[1:]
    run(EP2_IN, acc=queued, busy=1)
    check("EP2 IN completion: the queued message goes to the encoder as one transfer", encodes == [queued], f"{[e.hex() for e in encodes]}")
    check("EP2 IN completion: one read, one write of exactly bit 18, the transfer slot taken again",
          len(reads) == 1 and writes == [EP2_IN] and uc.mem_read(syms["usbmidi_tx_busy"], 1)[0] == 1,
          f"writes {[hex(w) for w in writes]}")
    run(EP2_IN, busy=1)
    check("EP2 IN completion with nothing queued: the slot is free", not encodes and uc.mem_read(syms["usbmidi_tx_busy"], 1)[0] == 0)
    # both at once, from the one read
    run(EP2_OUT | EP2_IN, tok=token(512 - 16), buf=b"".join(ev), acc=queued, busy=1)
    check("OUT and IN together: both handled from one read and one write",
          bytes(got) == b"".join(want) and encodes == [queued] and len(reads) == 1 and writes == [EP2_OUT | EP2_IN],
          f"reads {len(reads)}, writes {[hex(w) for w in writes]}")
    # session down: cleared, not handled
    run(EP2_OUT | EP2_IN, up=0, tok=token(512 - 16), buf=b"".join(ev), acc=queued)
    check("session down: the EP2 bits are cleared, nothing is decoded or sent",
          writes == [EP2_OUT | EP2_IN] and not got and not encodes, f"writes {[hex(w) for w in writes]}")
    print(f"verify_usbmidi_isr: {'OK' if not fails else str(len(fails)) + ' FAILED'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
