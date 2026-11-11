#!/usr/bin/env python3
"""DRUMMER's kit file (image 68): NAME.drk beside the sample, written and read by the engine task.

    .venv/bin/python3 modules/drummer/verify_drk.py [--image out/mainos_bus.bin]
        [--card out/drummer/port/groove/card.img]

The card is verify_port.py's groove (the user's sample as AUDIO/DRUMMER_TEST.wav, T1 a DRUMMER track
with a kit in drummer.work). Three runs under the port:

  1. save   T1, TRIG 1 + BANK (the KIT), A turns slice 1's ZONE, RIGHT RIGHT (page 3), E turned: the
            SAVE KIT FILE? box, YES. The card the firmware leaves holds AUDIO/DRUMMER_TEST.drk: magic DRKT,
            version 1, 468 bytes, its CRC-32; the kit in RAM (slice 1's new ZONE), the slot's slice count
            and the CRC-32 of the slices' bounds (FLEX settings + 312, 12 bytes a slice).
  2. load   that card (drummer.work still the kit before the edit): T1 shown, its kit poked "none yet"
            (dr_kit_ready 2) -> the kit from the file (slice 1's ZONE the file's), no box asked.
  3. stale  the same with slice 1's start poked one frame on (the slices changed since): the file is
            not applied, the AUTO box asks (DIALOG_OPEN), the kit stays "none yet".
"""
import argparse, pathlib, struct, subprocess, sys, zlib

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import toolpath  # noqa: E402,F401
from emu import emu_card  # noqa: E402

EMU = ROOT / "out/emu/ot_emu"
OUT = ROOT / "out/drummer/drk"
T1, TRIG1, BANK, YES, RIGHT = 0x10, 0x00, 0x2F, 0x31, 0x21
FLEX_SET, DIALOG_OPEN = 0x100B14F0, 0x460E5CD0
DRK = "OCTABAM/AUDIO/DRUMMER_TEST.drk"
FAILS = []


def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" -- {detail}" if detail else ""))
    if not ok:
        FAILS.append(name)


def symbol(name):
    for line in (ROOT / "out/platform/runtime/runtime.map").read_text().splitlines():
        w = line.split()
        if len(w) == 2 and w[1] == name and w[0].startswith("0x"):
            return int(w[0], 16)
    sys.exit(f"verify_drk: {name} not in the runtime map")


def script(events):
    t, lines = 1500.0, []
    for gap, ev in events:
        lines.append(f"{t:.0f} {ev}")
        t += gap
    return "\n".join(lines + [f"{t + 1500:.0f} quit"]) + "\n"


def tap(k, gap=400):
    return [(40, f"key {k:#x} down"), (gap, f"key {k:#x} up")]


def run(a, name, card, events, extra=()):
    (OUT / f"{name}.script").write_text(script(events))
    kit, ready = symbol("dr_kit"), symbol("dr_kit_ready")
    dump = (f"{kit:#x},268={OUT}/{name}_kit.bin;{ready:#x},8={OUT}/{name}_ready.bin;"
            f"{FLEX_SET + 312:#x},780={OUT}/{name}_slices.bin;{DIALOG_OPEN:#x},4={OUT}/{name}_dialog.bin")
    cmd = [str(EMU), "--image", a.image, "--card", str(card), "--set", "OCTABAM", "--project", "RIG", "--mkii",
           "--load-ms", "90000", "--live-script", str(OUT / f"{name}.script"), "--lcd", str(OUT / f"{name}.lcd"),
           "--mem-dump", dump, *extra]
    with open(OUT / f"{name}.txt", "w") as f:
        rc = subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT).returncode
    subprocess.run([str(ROOT / ".venv/bin/python3"), str(ROOT / "tools/emu/lcd_view.py"), str(OUT / f"{name}.lcd"),
                    "--png", str(OUT / f"{name}.png")], cwd=ROOT, capture_output=True)
    rd = lambda s: (OUT / f"{name}_{s}.bin").read_bytes() if (OUT / f"{name}_{s}.bin").is_file() else b""
    return rc, rd("kit"), rd("ready"), rd("slices"), rd("dialog")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--image", default=str(ROOT / "out/mainos_bus.bin"))
    ap.add_argument("--card", default=str(ROOT / "out/drummer/port/groove/card.img"))
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    ready_at = symbol("dr_kit_ready")

    # 1. SAVE KIT on the panel
    ev = tap(T1, 600) + [(300, f"key {TRIG1:#x} down"), (40, f"key {BANK:#x} down"), (200, f"key {BANK:#x} up"),
                         (400, f"key {TRIG1:#x} up"), (600, "enc 0 1")]
    ev += tap(RIGHT, 500) + tap(RIGHT, 500) + [(800, "enc 4 1")] + tap(YES, 4000)
    saved = OUT / "save.img"
    rc, kit, ready, slices, _ = run(a, "save", a.card, ev, ("--card-out", str(saved)))
    check("run 1 (KIT page 3, E, YES) ran", rc == 0 and saved.is_file() and len(kit) == 268, f"exit {rc}")
    if FAILS:
        return 1
    files = emu_card.extract_image(saved.read_bytes())
    drk = files.get(DRK)
    check(f"{DRK} written beside the sample", drk is not None, f"files: {sorted(p for p in files if 'AUDIO' in p)}")
    if drk is None:
        return 1
    magic, ver, size, crc = struct.unpack(">4sIII", drk[:16])
    body = drk[16:]
    check("header DRKT, version 1, 468 bytes, its CRC-32", magic == b"DRKT" and ver == 1 and size == 468
          and len(body) == 468 and zlib.crc32(body) == crc, f"{magic} v{ver} {size} ({len(body)}) crc ok {zlib.crc32(body) == crc}")
    n, sig = body[0], struct.unpack(">I", body[4:8])[0]
    want_sig = zlib.crc32(slices[:12 * n])
    check("the slices it fits: their count and the CRC-32 of their bounds", n > 0 and sig == want_sig,
          f"n {n} sig {sig:#x} want {want_sig:#x}")
    edited = kit[0]
    check("the kit as the panel left it (slice 1's ZONE turned)", body[8:8 + 64] == kit[:64] and body[72:136] == kit[64:128],
          f"file zone 1 {body[8]} RAM {edited}")

    # 2. load: the file's kit on a track poked "no kit yet"
    ev = tap(T1, 600) + [(1500, f"poke {ready_at:#x}=2"), (5000, "key 0x30 up")]
    rc, kit2, ready2, _, dialog2 = run(a, "load", saved, ev)
    ok = rc == 0 and len(kit2) == 268
    check("run 2 ran", ok, f"exit {rc}")
    if ok:
        check("load: the kit from the file, no box (ready 1, slice 1's ZONE the file's, DIALOG_OPEN 0)",
              ready2[0] == 1 and kit2[0] == body[8] and kit2[:64] == body[8:72] and dialog2 == b"\0\0\0\0",
              f"ready {ready2[0]} zone 1 {kit2[0]} (file {body[8]}) dialog {dialog2.hex()}")

    # 3. stale: the slices changed since the save
    s0 = struct.unpack(">I", slices[:4])[0]
    ev = tap(T1, 600) + [(1500, f"poke {FLEX_SET + 315:#x}={(s0 + 1) & 0xff};{ready_at:#x}=2"), (5000, "key 0x30 up")]
    rc, kit3, ready3, _, dialog3 = run(a, "stale", saved, ev)
    ok = rc == 0 and len(kit3) == 268
    check("run 3 ran", ok, f"exit {rc}")
    if ok:
        check("stale: the file not applied, AUTO asked (ready 2, DIALOG_OPEN set)",
              ready3[0] == 2 and dialog3 != b"\0\0\0\0", f"ready {ready3[0]} dialog {dialog3.hex()}")

    print("PASS: DRUMMER kit file" if not FAILS else f"FAIL: DRUMMER kit file ({len(FAILS)})")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
