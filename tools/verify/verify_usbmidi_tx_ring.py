#!/usr/bin/env python3
"""USB MIDI transmit of a burst longer than one transfer, under the ColdFire port.

Reported on an MKI (#1016, xynta, 3 Nov 2026): the CC 61 dump is 283 CCs in
about 5 ms and 102 to 172 of them reached the host; `usbmidi_tx_drops` rose by
the rest. usbmidi.s queued a message into one 256-byte accumulator while a
transfer was in flight and dropped (and counted) what did not fit. The queue is
now that accumulator plus a ring of whole messages (RING_CAP bytes).

Cases, each through the firmware's own midi_send, with the host not reading
while the burst is sent:
  * 283 CCs: every message reaches EP2 IN, in order, and usbmidi_tx_drops
    does not move.
  * the ring full (head 0, tail 4093): the next message is dropped and counted.
  * a backlog at a cable pull: nothing queued for the old session reaches the
    new one (the ring is emptied at the session end and at SET_CONFIGURATION).

SKIPs when the remix has no USB or the port is not built (`make emu-cf`).
"""
import os
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
import usb_host  # noqa: E402  (tools/harness)
import verify_usb_midi_replug as rp  # noqa: E402  (KeepBench, drain, symbols, the senders' addresses)

from remix import registry  # noqa: E402

EMU = rp.EMU
IMAGE = rp.IMAGE
fails = rp.fails
check = rp.check


def cc(i):
    """The i-th message: CC number i mod 128, value 1 + i div 128, channel 0."""
    return bytes([0xB0, i % 128, 1 + (i // 128) % 127])


def burst(b, n, first=0):
    for i in range(first, first + n):
        rp.note(b, cc(i))


def drain512(b, seconds):
    """Every EP2 IN event packet until the device stops answering (reads of
    the endpoint's full 512 bytes: rp.drain reads 64 and cuts a coalesced
    transfer short)."""
    pk = []
    for line in b.stray:
        d = bytes.fromhex(line.split()[2]) if len(line.split()) > 2 else b""
        pk += [d[i:i + 4] for i in range(0, len(d) - 3, 4)]
    b.stray.clear()
    end = time.time() + seconds
    while time.time() < end:
        try:
            data = b.ep_in(2, 512, timeout=max(0.1, end - time.time()))
        except TimeoutError:
            break
        pk += [data[i:i + 4] for i in range(0, len(data) - 3, 4)]
    return pk


def received(b, seconds=3.0):
    """Control-change events on EP2 IN as message indices, in arrival order."""
    return [p[1:4] for p in drain512(b, seconds) if p[0] & 0x0F == 0x0B]


def index_of(msg):
    return msg[1] + 128 * (msg[2] - 1)


def drops(b, sym):
    return int.from_bytes(b.peek(sym["usbmidi_tx_drops"], 4), "big")


def run():
    sym = rp.symbols()
    sock = f"/tmp/ot-txring-{os.getpid()}.sock"
    log = ROOT / "out/verify_usbmidi_tx_ring.log"
    with open(log, "w") as lf:
        emu = subprocess.Popen([str(EMU), "--image", str(IMAGE), "--usb-host", sock, "--usb-hold-ms", "300000"],
                               cwd=ROOT, stdout=lf, stderr=subprocess.STDOUT)
    try:
        b = rp.KeepBench(sock, timeout=120.0)
        usb_host.enumerate_device(b, hs=True)

        n = 283
        d0 = drops(b, sym)
        burst(b, n)
        got = received(b)
        idx = [index_of(m) for m in got]
        check(f"{n} CCs sent back to back: all {n} arrive on EP2 IN", len(got) == n, f"{len(got)} arrived")
        check(f"{n} CCs: in send order", idx == list(range(n)), idx[:6])
        check(f"{n} CCs: usbmidi_tx_drops does not move", drops(b, sym) == d0, f"{d0} -> {drops(b, sym)}")

        # the ring full: head 0, tail 4093 leaves 2 free bytes, a 3-byte message needs 4
        b.poke(sym["usbmidi_tx_rhead"], (0).to_bytes(2, "big"))
        b.poke(sym["usbmidi_tx_rtail"], (4093).to_bytes(2, "big"))
        d0 = drops(b, sym)
        rp.note(b, cc(0))
        dd = drops(b, sym) - d0
        b.poke(sym["usbmidi_tx_rtail"], (0).to_bytes(2, "big"))     # empty again before any kick can read the filler
        check("a message the ring has no room for is dropped and counted", dd == 1, f"drops +{dd}")

        # a backlog at the cable pull: nothing queued for the old session goes out in the next
        burst(b, 150)      # 450 B: the stock midi_send path takes about 500 calls in a session without time passing
        b.stray.clear()
        b.unplug()
        b.plug()
        usb_host.enumerate_device(b, hs=True)
        stale = received(b, 2.0)
        check("backlog at a cable pull: no queued CC reaches the new session", not stale, f"{len(stale)} arrived")
        rp.transmits(b, "after the pull")
        b.sock.close()
    except Exception as e:  # noqa: BLE001 -- a hang is the finding
        check(f"the host script completed ({type(e).__name__}: {e})", False)
        emu.kill()
    try:
        emu.wait(timeout=120)
    except subprocess.TimeoutExpired:
        emu.kill()
        emu.wait()


def main():
    if not EMU.is_file():
        print("  [SKIP] verify_usbmidi_tx_ring: the port is not built (make emu-cf)")
        return 0
    if not IMAGE.is_file():
        print("  [FAIL] verify_usbmidi_tx_ring: no out/mainos_bus.bin (make bus)")
        return 1
    if "USB" not in registry.remix(os.environ.get("REMIX")).modules:
        print("  [SKIP] verify_usbmidi_tx_ring: the remix has no USB")
        return 0
    run()
    print(f"verify_usbmidi_tx_ring: {'OK' if not fails else f'{len(fails)} FAILED'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
