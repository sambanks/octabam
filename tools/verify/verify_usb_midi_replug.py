#!/usr/bin/env python3
"""USB MIDI transmit after a cable pull and a replug, under the ColdFire port.

Measured on a unit (Ignorato's MKII, OCTABAM14 = usb-win-out, 7-9 Oct 2026, macOS
and two Windows 10 hosts): unit-to-host USB MIDI works on the first connection
after boot and never again after the cable is unplugged and replugged; only a
power cycle brings it back. A bus reset with the cable left in does not do it.

Each cycle here is what a unit that sends MIDI clock sees when the cable is
pulled: on odd cycles a clock byte is primed on EP2 IN with no host reading
it (the transfer the cable pull leaves in flight), on even cycles EP2 IN is
idle at the pull (the host had read everything); then the bench's `unplug`
(OTGSC.BSVIS, B-session invalid: the stock session-end path), one more clock
byte while unplugged, `plug` (session valid again), one more clock byte, a
bus reset and a full enumeration, then a
channel message and a clock byte through the firmware's own senders, each of
which must arrive on EP2 IN, and a channel message into EP2 OUT, which must
reach the firmware's MIDI receive FIFO. Four cycles, then a bus reset with the
cable in (re-enumeration without a pull); the first connection is
checked first, the same way.

Checked per cycle, from the port's USB trace (OT_USB_TRACE): no EP2 IN prime
(ENDPTPRIME bit 18) from the session end to the host's SET_CONFIGURATION,
and the first transfer after the replug carries only the new message, not
bytes queued for the old session. On usbmidi.s alone (before
usbmidi_rx_bus_end) both fail: usbmidi_up outlives the session, the unit
primes EP2 IN with USBCMD.RS clear, and the stale clocks go out after
SET_CONFIGURATION.

What the port models and what it does not: the session end and the session
start run the stock ISR paths (USBCMD.RS and USBINTR cleared; USBMODE,
EPLISTADDR, RS and USBINTR written back, no controller reset); priming,
flushing and ENDPTSTAT are modelled per register, a flush completes at once
and cancels a pending prime, and a bus reset clears ENDPTSTAT. So the port
does NOT reproduce the hang itself: it has no data toggles, no NAK timing,
no host queue of outstanding reads, and none of silicon's handling of a
prime the controller has not taken or of a queue head rewritten under a
primed endpoint. It checks the preconditions the fix removes.

SKIPs when the remix has no USB or the port is not built (`make emu-cf`).
"""
import os
import pathlib
import shutil
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
import usb_host  # noqa: E402  (tools/harness)

from remix import registry  # noqa: E402

EMU = ROOT / "out/emu/ot_emu"
IMAGE = pathlib.Path(os.environ.get("OT_IMAGE", ROOT / "out/mainos_bus.bin"))
ELF = ROOT / "out/platform/runtime/runtime.elf"
SETCFG = "cmd setup 0009010000000000"   # SET_CONFIGURATION(1) as the bench logs it
PRIO_SENDER = 0x400108b0        # the priority (realtime) byte sender, usbmidi_prio_shim's site
MIDI_SEND = 0x40010bc8          # midi_send(len, buf), usbmidi_send_shim's site
STAGING = 0x400d807c            # midi_send's outbound staging buffer (verify_usb)
MIDI_FIFO_HEAD = 0x46100b80     # +1 per byte midi_rx_enqueue takes (verify_usb)
CLOCK = bytes([0x0f, 0xf8, 0x00, 0x00])
CYCLES = 4                      # odd: a clock transfer in flight at the pull; even: EP2 IN idle at the pull
fails = []


def check(what, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {what}{'  ' + str(detail) if detail else ''}")
    if not ok:
        fails.append(what)


def symbols():
    nm = shutil.which("m68k-elf-nm") or shutil.which("m68k-linux-gnu-nm")
    if not nm:
        print("  [FAIL] verify_usb_midi_replug: neither m68k-elf-nm nor m68k-linux-gnu-nm is on PATH")
        sys.exit(1)
    out = subprocess.run([nm, str(ELF)], capture_output=True, text=True).stdout
    return {p[2]: int(p[0], 16) for p in (l.split() for l in out.splitlines()) if len(p) == 3}


class KeepBench(usb_host.Bench):
    """Keeps EP2 IN replies that land while another reply is awaited: the
    base Bench drops a line it is not waiting for, and a send's packet can
    answer the read a previous drain left pending while `call` is awaited."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.stray = []

    def wait(self, prefix, timeout=None):
        while True:
            line = super().wait(prefix if prefix.startswith("in 2") else "", timeout)
            if line.startswith(prefix) or line == "ok":
                return line
            if line.startswith("in 2"):
                self.stray.append(line)


def drain(b, seconds=1.5):
    """Every EP2 IN event packet until the device stops answering."""
    pk = []
    for line in b.stray:
        d = bytes.fromhex(line.split()[2]) if len(line.split()) > 2 else b""
        pk += [d[i:i + 4] for i in range(0, len(d) - 3, 4)]
    b.stray.clear()
    end = time.time() + seconds
    while time.time() < end:
        try:
            data = b.ep_in(2, 64, timeout=max(0.1, end - time.time()))
        except TimeoutError:
            break
        pk += [data[i:i + 4] for i in range(0, len(data) - 3, 4)]
    return pk


def clock(b):
    b.call(PRIO_SENDER, 0xF8)


def note(b, raw):
    b.poke(STAGING, raw)
    b.call(MIDI_SEND, len(raw), STAGING)


def transmits(b, tag, fresh=False):
    """A note-on, then a clock byte, each drained on its own: a transfer that
    is lost leaves tx_busy set, which shows from the second send on. With
    `fresh`, the note-on must be the only thing the first drain gets (no
    bytes queued for the previous session)."""
    on = bytes([0x90, 0x3c, 0x64])
    note(b, on)
    p1 = drain(b)
    clock(b)
    p2 = drain(b)
    ok1, ok2 = bytes([0x09]) + on in p1, CLOCK in p2
    check(f"{tag}: midi_send's note-on arrives on EP2 IN", ok1, [p.hex() for p in p1])
    check(f"{tag}: the next clock byte arrives on EP2 IN", ok2, [p.hex() for p in p2])
    if fresh:
        check(f"{tag}: nothing queued for the old session goes out after the replug",
              p1 == [bytes([0x09]) + on], [p.hex() for p in p1])
    return ok1 and ok2


def run():
    sym = symbols()
    tag = "replug"
    ring = ("usbmidi_tx_acc_len", "usbmidi_tx_used", "usbmidi_tx_head", "usbmidi_tx_tail")
    check("usbmidi.s exports the TX ring's state (usbmidi_rx_bus_end empties it by name, #1016)",
          all(s in sym for s in ring), ", ".join(s for s in ring if s not in sym))
    sock = f"/tmp/ot-replug-{os.getpid()}-{tag}.sock"
    log = ROOT / f"out/verify_usb_midi_replug_{tag}.log"
    watch = f"{sym['usbmidi_up']:#x},2;{MIDI_FIFO_HEAD:#x},4"
    env = dict(os.environ, OT_USB_TRACE="1")
    with open(log, "w") as lf:
        emu = subprocess.Popen([str(EMU), "--image", str(IMAGE), "--usb-host", sock, "--usb-hold-ms", "300000",
                                "--watch-mem", watch],
                               cwd=ROOT, stdout=lf, stderr=subprocess.STDOUT, env=env)
    print(f"== first connection, then {CYCLES} cable pulls (odd: a clock transfer in flight at the pull; even: EP2 IN idle)")
    try:
        b = KeepBench(sock, timeout=60.0)
        usb_host.enumerate_device(b, hs=True)
        transmits(b, f"{tag}, first connection")
        for n in range(1, CYCLES + 1):
            clock(b)                         # answers the read the last drain left outstanding
            if n % 2:
                clock(b)                     # odd cycles: primed, nobody reading, in flight at the pull
            b.stray.clear()                  # delivered in the old session, to the read left outstanding
            b.unplug()                       # session end
            clock(b)                         # the unit keeps sending while unplugged
            b.plug()                         # session valid again
            clock(b)                         # between the session start and SET_CONFIGURATION
            usb_host.enumerate_device(b, hs=True)
            transmits(b, f"{tag}, replug {n}", fresh=True)
            usb_host.midi_send(b, bytes.fromhex("903c64"))
        # a bus reset with the cable in (libusb's re-enumeration, which on
        # the unit never lost transmit): a clock in flight, then reset and
        # enumerate without unplug/plug
        clock(b)
        clock(b)
        b.stray.clear()
        usb_host.enumerate_device(b, hs=True)
        transmits(b, f"{tag}, bus reset with the cable in", fresh=True)
        b.sock.close()
    except Exception as e:  # noqa: BLE001 -- a hang is the finding
        check(f"{tag}: the host script completed ({type(e).__name__}: {e})", False)
        emu.kill()
    try:
        emu.wait(timeout=120)
    except subprocess.TimeoutExpired:
        emu.kill()
        emu.wait()
    text = log.read_text(errors="replace")
    rx = [l for l in text.splitlines() if f"[{MIDI_FIFO_HEAD:#x}]" in l]
    check(f"{tag}: EP2 OUT still feeds the MIDI receive FIFO after each replug ({3 * CYCLES} bytes)",
          len(rx) == 3 * CYCLES, f"{len(rx)} write(s)")
    bad = [l for l in text.splitlines() if "UNINITIALIZED" in l]
    check(f"{tag}: no uninitialised queue head was primed", not bad, bad[:1])
    # EP2 IN primes between each session end and the next SET_CONFIGURATION
    stray, window, n = [], False, 0
    for l in text.splitlines():
        if "usb-trace" not in l:
            continue
        if "cmd unplug" in l:
            window, n = True, n + 1
        elif SETCFG in l:
            window = False
        elif window and " wr 0x1b0 <- " in l and int(l.rsplit("<- ", 1)[1], 16) & (1 << 18):
            stray.append(n)
    check(f"{tag}: EP2 IN is never primed from the session end to the next SET_CONFIGURATION ({n} sessions)",
          n == CYCLES and not stray, f"primes in session(s) {stray}" if stray else f"{n} session end(s) seen")


def main():
    if not EMU.is_file():
        print("  [SKIP] verify_usb_midi_replug: the port is not built (make emu-cf)")
        return 0
    if not IMAGE.is_file():
        print("  [FAIL] verify_usb_midi_replug: no out/mainos_bus.bin (make bus)")
        return 1
    if "USB" not in registry.remix(os.environ.get("REMIX")).modules:
        print("  [SKIP] verify_usb_midi_replug: the remix has no USB")
        return 0
    run()
    print(f"verify_usb_midi_replug: {'OK' if not fails else f'{len(fails)} FAILED'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
