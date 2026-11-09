#!/usr/bin/env python3
"""DRUMMER's drummer.work under the port: edit a kit on the panel, SAVE PROJECT, boot on the saved card.

    .venv/bin/python3 modules/drummer/verify_store.py [--image out/mainos_bus.bin]
        [--card out/drummer/port/groove/card.img]

The card is verify_port.py's groove (the user's sample, T1 a DRUMMER track). Run 1, the panel: T1, TRIG 1 +
BANK (the KIT window on slice 1), page 1: A +1 (KICK -> SNARE); RIGHT, page 2: A +10 (ALIGN 20 ms),
B -3 (GAIN -3 dB), E +3 (SCENE 3), F -1 (DOSE 95 %); RIGHT, page 3: A +1 (SHIFT), C -2 (SIMILAR 4),
D +1 (LINK), F +1 (REDRUM, image 77); YES, then PROJECT > SAVE PROJECT (pattern-mute's keys); the
card the firmware leaves is read back: drummer.work's header (magic DRMK, version 5, 4728 bytes, its CRC), T1's
record and its GAIN, SCENE, DOSE, SIMILAR and REDRUM rows. Run 2 boots that card: T1's kit in RAM (dr_kit, dr_align,
dr_shift, dr_gain, dr_scene, dr_dose, dr_simtol, dr_simmode, dr_redrum, dr_kit_ready) must be what run 1 saved, T2-T8's
SIMILAR at its default (6, OUT).
"""
import argparse, pathlib, struct, subprocess, sys, zlib

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import toolpath  # noqa: E402,F401
from emu import emu_card  # noqa: E402

EMU = ROOT / "out/emu/ot_emu"
OUT = ROOT / "out/drummer/store"
T1, TRIG1, BANK, YES, PROJ, RIGHT, DOWN = 0x10, 0x00, 0x2F, 0x31, 0x1C, 0x21, 0x20
SNARE = 1
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
    sys.exit(f"verify_store: {name} not in the runtime map")


def script(events):
    t, lines = 1500.0, []
    for gap, ev in events:
        lines.append(f"{t:.0f} {ev}")
        t += gap
    return "\n".join(lines + [f"{t + 1500:.0f} quit"]) + "\n"


def tap(k, gap=400):
    return [(40, f"key {k:#x} down"), (gap, f"key {k:#x} up")]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--image", default=str(ROOT / "out/mainos_bus.bin"))
    ap.add_argument("--card", default=str(ROOT / "out/drummer/port/groove/card.img"))
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    ev = tap(T1, 600) + [(300, f"key {TRIG1:#x} down"), (40, f"key {BANK:#x} down"), (200, f"key {BANK:#x} up"),
                         (400, f"key {TRIG1:#x} up"), (600, "enc 0 1")]
    ev += tap(RIGHT, 500) + [(300, "enc 0 10"), (300, "enc 1 -1"), (200, "enc 1 -1"), (200, "enc 1 -1"),
                             (300, "enc 4 1"), (200, "enc 4 1"), (200, "enc 4 1"), (300, "enc 5 -1")]
    ev += tap(RIGHT, 500) + [(300, "enc 0 1"), (300, "enc 2 -1"), (300, "enc 2 -1"), (300, "enc 3 1"), (300, "enc 5 1")]
    ev += tap(YES, 800) + tap(PROJ, 1000) + tap(RIGHT, 700) + tap(DOWN, 500) + tap(YES, 1100) + tap(YES, 30000)
    (OUT / "save.script").write_text(script(ev))
    saved = OUT / "save.img"
    cmd = [str(EMU), "--image", a.image, "--card", a.card, "--set", "OCTABAM", "--project", "RIG",
           "--load-ms", "90000", "--main-level", "64", "--live-script", str(OUT / "save.script"),
           "--card-out", str(saved), "--mkii", "--lcd", str(OUT / "save.lcd")]
    with open(OUT / "save.txt", "w") as f:
        rc = subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT).returncode
    check("run 1 (edit, SAVE PROJECT) ran", rc == 0 and saved.is_file(), f"exit {rc}")
    if not saved.is_file():
        return 1
    files = emu_card.extract_image(saved.read_bytes())
    work = files.get("OCTABAM/RIG/drummer.work")
    check("drummer.work written", work is not None, ", ".join(sorted(k for k in files if "RIG/" in k))[:400])
    if not work:
        return 1
    magic, ver, size, crc = struct.unpack(">4I", work[:16])
    body = work[16:]
    check("header: DRMK, version 5, 4728 bytes", (magic, ver, size, len(body)) == (0x44524D4B, 5, 4728, 4728),
          f"{magic:#x} {ver} {size} {len(body)}")
    check("its CRC is zlib's CRC-32 of the payload", crc == zlib.crc32(body), f"{crc:#x} vs {zlib.crc32(body):#x}")
    t1 = body[:332]
    zone, role, align = t1[0:64], t1[64:128], t1[256:320]
    shift, phrase, ready = t1[329], t1[330], t1[331]
    check("T1: slice 1 SNARE, ALIGN 20 ms, SHIFT, PHRASE 4, a kit", (zone[0], align[0], shift, phrase, ready)
          == (SNARE, 20, 1, 4, 1), f"zone {zone[0]} align {align[0]} shift {shift} phrase {phrase} ready {ready}")
    check("T1: the other slices are the built-in kit", list(zone[1:4]) == [8, 1, 0] and role[0] == 0,
          f"zones {list(zone[:4])} role0 {role[0]}")
    check("T2-T8: no kit", all(body[332 * t + 331] == 0 for t in range(1, 8)))
    gain = body[2656:2656 + 64]
    check("T1: slice 1 GAIN -3 dB, the others 0", gain[0] == 0xFD and not any(gain[1:]) and not any(body[2656 + 64:3168]),
          f"gain {list(gain[:4])}")
    scene, dose = body[3168:3168 + 64], body[3680:3680 + 64]
    check("T1: slice 1 SCENE 3 DOSE 95 %, the others none", (scene[0], dose[0]) == (3, 95) and not any(scene[1:])
          and not any(dose[1:]) and not any(body[3168 + 64:3680]) and not any(body[3680 + 64:4192]),
          f"scene {list(scene[:4])} dose {list(dose[:4])}")
    tol, mode = body[4704:4712], body[4712:4720]
    check("T1: SIMILAR 4 LINK, no groups (the built-in kit); T2-T8 none saved", (tol[0], mode[0]) == (4, 1)
          and not any(tol[1:]) and not any(mode[1:]) and not any(body[4192:4704]), f"tol {list(tol)} mode {list(mode)}")
    check("T1: REDRUM on (page 3's F, image 77), T2-T8 off", list(body[4720:4728]) == [1] + [0] * 7,
          str(list(body[4720:4728])))
    strd = files.get("OCTABAM/RIG/drummer.strd")
    check("drummer.strd = drummer.work (the project store)", strd == work)

    kit, al, sh, rd = symbol("dr_kit"), symbol("dr_align"), symbol("dr_shift"), symbol("dr_kit_ready")
    gn, sc, do = symbol("dr_gain"), symbol("dr_scene"), symbol("dr_dose")
    st, sm, rr = symbol("dr_simtol"), symbol("dr_simmode"), symbol("dr_redrum")
    dumps = (f"{kit:#x},268={OUT}/kit.bin;{al:#x},64={OUT}/align.bin;{sh:#x},8={OUT}/shift.bin;{rd:#x},8={OUT}/ready.bin;"
             f"{gn:#x},64={OUT}/gain.bin;{sc:#x},64={OUT}/scene.bin;{do:#x},64={OUT}/dose.bin;"
             f"{st:#x},8={OUT}/simtol.bin;{sm:#x},8={OUT}/simmode.bin;{rr:#x},8={OUT}/redrum.bin")
    cmd = [str(EMU), "--image", a.image, "--card", str(saved), "--set", "OCTABAM", "--project", "RIG", "--mkii",
           "--load-ms", "90000", "--main-level", "64", "--sequencer", "--internal-clock", "--frames", "200",
           "--mem-dump", dumps]
    with open(OUT / "boot.txt", "w") as f:
        rc = subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT).returncode
    k = (OUT / "kit.bin").read_bytes() if (OUT / "kit.bin").is_file() else b""
    check("run 2 (boot on the saved card) ran", rc == 0 and len(k) == 268, f"exit {rc}")
    if len(k) == 268:
        check("T1's kit back in RAM: zones and roles as saved", k[:128] == bytes(zone) + bytes(role))
        check("T1's ALIGN, SHIFT and kit flag back", (OUT / "align.bin").read_bytes() == bytes(align)
              and (OUT / "shift.bin").read_bytes()[0] == 1 and (OUT / "ready.bin").read_bytes()[0] == 1)
        check("T1's GAIN back", (OUT / "gain.bin").read_bytes() == bytes(gain))
        check("T1's SCENE and DOSE back", (OUT / "scene.bin").read_bytes() == bytes(scene)
              and (OUT / "dose.bin").read_bytes() == bytes(dose))
        tb, mb = (OUT / "simtol.bin").read_bytes(), (OUT / "simmode.bin").read_bytes()
        check("T1's SIMILAR back (4 LINK), T2-T8 at the default (6 OUT)",
              list(tb) == [4] + [6] * 7 and list(mb) == [1] + [0] * 7, f"tol {list(tb)} mode {list(mb)}")
        rb = (OUT / "redrum.bin").read_bytes()
        check("T1's REDRUM back (on), T2-T8 off", list(rb) == [1] + [0] * 7, str(list(rb)))
    print(f"{'PASS' if not FAILS else 'FAIL'}: DRUMMER drummer.work")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
