#!/usr/bin/env python3
"""Flash an Octatrack OS over MIDI, for RECOVERY when a build wedges the unit.

The card path (docs/FLASHING.md 3a) is faster, but it lives inside the
PROJECT menu -- useless if the OS crashes before you get there. This is the
bootloader path: it works even with a corrupt OS, because the Startup Menu is
in a region an OS update never touches.

    On the unit:  power off; hold [FUNC], power on -> STARTUP MENU;
                  [TRIG 3] MIDI UPGRADE -> "READY TO RECEIVE MIDI UPGRADE".
    Then:         python3 tools/midi_flash.py <port> <file.syx> [--ms N] [--list]

The .syx is a stream of ~7,460 small SysEx messages; this sends them one at a
time paced at the DIN rate (~40 ms each, ~5 min for a full OS) so a USB->DIN
bridge (a Midihub, say) never overflows its buffer. Route the OT's MIDI IN to
the chosen port and FILTER MIDI CLOCK on it -- a clock byte in the stream
corrupts the upgrade.

Retry-safe: the bootloader survives a bad send, so if the TRIG lights fill but
the unit never reaches "PREPARING FLASH", re-enter the Startup Menu and run it
again (try --ms 60). ⚠️ DO NOT power off during "PREPARING/UPDATING FLASH".

Rescue images: downloads/extracted/OCTATRACK_OS1.40C.syx (factory) or any
out/OCTATRACK_OS1.40C_OCTABAM<NNN>.syx (a build). After a factory rescue the
PROJECT menu works again, so a good build can go back on via the card.
"""
import argparse
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import ot_midi  # CoreMIDI Out/endpoints (macOS)


def messages(b):
    """Yield each complete F0..F7 SysEx message in order."""
    i = 0
    while i < len(b):
        if b[i] != 0xF0:
            i += 1
            continue
        j = b.index(0xF7, i)
        yield b[i:j + 1]
        i = j + 1


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("port", nargs="?", help="MIDI destination name (e.g. A)")
    ap.add_argument("syx", nargs="?", help="the .syx OS image")
    ap.add_argument("--ms", type=float, default=40.0,
                    help="ms between messages (default 40; raise if it loses sync)")
    ap.add_argument("--list", action="store_true", help="list MIDI destinations and exit")
    a = ap.parse_args()

    if a.list or not (a.port and a.syx):
        print("destinations:", [n for n, _ in ot_midi.endpoints("dst")])
        print("sources:     ", [n for n, _ in ot_midi.endpoints("src")])
        if not a.list:
            ap.error("give a port and a .syx (or --list)")
        return

    b = pathlib.Path(a.syx).read_bytes()
    if not b or b[0] != 0xF0 or b[-1] != 0xF7:
        sys.exit(f"{a.syx}: not a SysEx file (must start F0, end F7)")
    msgs = list(messages(b))
    total = sum(len(m) for m in msgs)
    pace = a.ms / 1000.0
    print(f"{a.syx}: {len(msgs)} messages, {total:,} bytes -> port {a.port!r}, "
          f"{a.ms:.0f} ms/msg  (~{len(msgs) * pace / 60:.1f} min)")
    print("The OT must show READY TO RECEIVE MIDI UPGRADE. Ctrl-C to abort now.")
    out = ot_midi.Out(a.port)
    t0 = time.time()
    for k, m in enumerate(msgs):
        out.send(list(m))
        time.sleep(pace)
        if k % 500 == 0:
            print(f"  {k}/{len(msgs)}  ({k / len(msgs) * 100:.0f}%)", flush=True)
    print(f"done: {len(msgs)} messages in {time.time() - t0:.0f}s. "
          f"Watch the OT: PREPARING FLASH -> UPDATING FLASH -> reboot. "
          f"Do NOT power off during FLASH.")


if __name__ == "__main__":
    main()
