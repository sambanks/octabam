#!/usr/bin/env python3
"""USB-MIDI receive: an EP2 OUT completion that lands between the two
ENDPTCOMPLETE reads is decoded once, and the 512-byte dTD is primed again (#1017).

    REMIX=<name> python3 tools/verify/verify_usbmidi_late.py

usbmidi_rx.s's ISR shim takes EP2 OUT completions, re-primes the 512-byte dTD
and hands over to usbmidi.s's usbmidi_isr_shim, which reads ENDPTCOMPLETE again
and takes bit 2 the 64-byte way: decode 64 - remaining bytes (none, or the first
n - 448 of a longer transfer), then the stock usb_midi_rx_prime (0x4001d184).
usbmidi_rx_late_shim is the detour on that routine. This gate puts the machine
where that branch leaves it -- usbmidi_rx_state 2, a completed 512-byte dTD
token, event packets at RX_BUF -- and calls 0x4001d184 on the booted image under
unicorn, as usbmidi_isr_shim does, recording each byte midi_rx_enqueue receives:

  * a 16-byte transfer (n <= 448): its 4 events' bytes, once each, in order;
  * a 464-byte transfer (n > 448): only the bytes past the 16 that usbmidi.s's
    own decoder took;
  * an errored dTD: nothing decoded, usbmidi_rx_errs + 1;
  * a dTD still ACTIVE (nothing completed): nothing decoded, the dTD untouched;
  * usbmidi_rx_state 0 (full speed): the stock 64-byte prime runs as before.

After each completed case the dTD token is the 512-byte ACTIVE one and the state
is 2. What this cannot see: the race's timing on the unit. The reporter's paced
bench (12,348 of 12,348 bytes, 500 late branches) is the measurement of that.
"""
import os
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
try:
    import emu_bringup as emu
    from unicorn import UC_HOOK_CODE
    from unicorn.m68k_const import UC_M68K_REG_A7
except ImportError:
    print("  [SKIP] verify_usbmidi_late: no unicorn (the .venv: make emu-setup)")
    sys.exit(0)

from remix import registry  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
IMAGE = ROOT / "out/mainos_bus.bin"
RUNTIME = ROOT / "out/platform/runtime/runtime.elf"
RX_PRIME = 0x4001d184       # usb_midi_rx_prime(buf): the detoured entry
RX_ENQUEUE = 0x40092bbc     # midi_rx_enqueue(byte as a long)
FIFO_COUNT = 0x46100b7c
RX_BUF = 0x4ecc9000
EP2_RX_TD = 0x4ec953e4      # token: remaining << 16, status in 7:0
TD_512 = 0x02008080
TD_STOCK64 = 0x00408080


def token(remaining, status=0):
    return (remaining << 16) | status


def main():
    remix = os.environ.get("REMIX") or (sys.argv[1] if len(sys.argv) > 1 else None)
    if "USB" not in registry.remix(remix).modules:
        print("  [SKIP] verify_usbmidi_late: the remix has no USB")
        return 0
    if not IMAGE.is_file() or not RUNTIME.is_file():
        print("  [FAIL] verify_usbmidi_late: no out/mainos_bus.bin or runtime (make bus)")
        return 1
    nm = subprocess.run(["m68k-elf-nm", str(RUNTIME)], capture_output=True, text=True).stdout
    syms = {f[2]: int(f[0], 16) for f in (l.split() for l in nm.splitlines()) if len(f) == 3}
    missing = [s for s in ("usbmidi_rx_state", "usbmidi_rx_late", "usbmidi_rx_errs") if s not in syms]
    if missing:
        print(f"  [FAIL] verify_usbmidi_late: the runtime has no {', '.join(missing)}")
        return 1
    uc = emu.boot(str(IMAGE)).uc
    got = []

    def on_enqueue(u, addr, size, user):
        sp = u.reg_read(UC_M68K_REG_A7)
        got.append(int.from_bytes(u.mem_read(sp + 4, 4), "big") & 0xff)

    uc.hook_add(UC_HOOK_CODE, on_enqueue, begin=RX_ENQUEUE, end=RX_ENQUEUE)
    rd = lambda a: int.from_bytes(uc.mem_read(a, 4), "big")          # noqa: E731
    wr = lambda a, v: uc.mem_write(a, (v & 0xffffffff).to_bytes(4, "big"))  # noqa: E731
    fails = []

    def check(what, ok, detail=""):
        print(f"  [{'PASS' if ok else 'FAIL'}] {what}{'  ' + detail if detail else ''}")
        if not ok:
            fails.append(what)

    def note(i):    # a USB-MIDI note-on event (cable 0, CIN 9) and its 3 MIDI bytes
        return bytes([0x09, 0x90, 0x30 + i, 0x40 + i]), bytes([0x90, 0x30 + i, 0x40 + i])

    def run(state, tok, buf):
        got.clear()
        uc.mem_write(syms["usbmidi_rx_state"], bytes([state]))
        wr(FIFO_COUNT, 0)
        wr(EP2_RX_TD, tok)
        uc.mem_write(RX_BUF, buf + bytes(512 - len(buf)))
        late, errs = rd(syms["usbmidi_rx_late"]), rd(syms["usbmidi_rx_errs"])
        emu._call(uc, RX_PRIME, (RX_BUF,))
        return rd(syms["usbmidi_rx_late"]) - late, rd(syms["usbmidi_rx_errs"]) - errs

    # n <= 448: usbmidi.s decoded nothing, so every byte is decoded here
    ev, want = zip(*(note(i) for i in range(4)))
    late, errs = run(2, token(512 - 16), b"".join(ev))
    check("16-byte late transfer: its 12 MIDI bytes, once each, in order", bytes(got) == b"".join(want),
          f"got {bytes(got).hex()}")
    check("16-byte late transfer: counted in usbmidi_rx_late, the 512-byte dTD primed again, state 2",
          late == 1 and rd(EP2_RX_TD) == TD_512 and uc.mem_read(syms["usbmidi_rx_state"], 1)[0] == 2,
          f"late +{late}, token 0x{rd(EP2_RX_TD):08x}")
    # n > 448: usbmidi.s decoded the first n - 448 = 16 bytes itself; only the rest is decoded here
    head, _ = zip(*(note(i) for i in range(4)))
    tail_ev, tail_want = zip(*(note(i) for i in range(4, 6)))
    pad = bytes(464 - 16 - 8)                          # CIN 0 events: no MIDI bytes
    run(2, token(512 - 464), b"".join(head) + pad + b"".join(tail_ev))
    check("464-byte late transfer: only the bytes past usbmidi.s's 16", bytes(got) == b"".join(tail_want),
          f"got {bytes(got).hex()}")
    # an errored dTD: counted, not decoded, primed again
    late, errs = run(2, token(512 - 16, 0x08), b"".join(ev))
    check("errored late transfer: not decoded, usbmidi_rx_errs + 1, the 512-byte dTD primed again",
          not got and errs == 1 and rd(EP2_RX_TD) == TD_512, f"got {bytes(got).hex()}, errs +{errs}")
    # still ACTIVE: nothing completed, the dTD stays as it is
    late, errs = run(2, TD_512, b"".join(ev))
    check("ACTIVE dTD: nothing decoded, the token untouched, not counted",
          not got and late == 0 and rd(EP2_RX_TD) == TD_512, f"token 0x{rd(EP2_RX_TD):08x}, late +{late}")
    # full speed: the stock 64-byte prime
    late, errs = run(0, token(0), b"".join(ev))
    check("state 0 (full speed): the stock 64-byte prime runs", not got and late == 0 and rd(EP2_RX_TD) == TD_STOCK64,
          f"token 0x{rd(EP2_RX_TD):08x}")
    print(f"verify_usbmidi_late: {'OK' if not fails else str(len(fails)) + ' FAILED'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
