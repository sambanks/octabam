#!/usr/bin/env python3
"""verify_pirateflag -- PIRATE FLAG (modules/pirate-flag) under the port.

    python3 tools/verify/verify_pirateflag.py [REMIX]     (default: pirate-flag)

Boots the image with the boot animation running (ot_emu --boot-logo: the
2.8 s on DTIM3 the port otherwise skips) and checks that the per-frame
detour ran every frame and that frame 280 -- which pirate_frame keeps in
pirate_snap -- is art.py's flag with the cloth moved exactly as flag.s's
integer wave says, bit for bit. The PNG goes to out/pirate-flag/frame280.png.

What it cannot show: the panel itself (the port's plane is what the
firmware sends; that the unit shows it upright is PANEL.md's measurement,
not this gate's), and the bootstrap's logo before the OS, which is NOR's.
"""
import math
import os
import pathlib
import re
import struct
import subprocess
import sys
import tempfile
import zlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
from remix import registry  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
EMU = ROOT / "out/emu/ot_emu"
STOCK = ROOT / "out/raw/section_3_MAIN_OS.bin"
sys.path.insert(0, str(ROOT / "modules/pirate-flag"))
import art  # noqa: E402

FRAME = 280


def expected(frame):
    sin = [round(32 * math.sin(2 * math.pi * i / 64)) for i in range(64)]
    out = bytearray()
    for x, (hi, lo) in enumerate(art.columns()):
        v = (hi << 32) | lo
        if x >= art.CLOTH:
            p = sin[(x - frame) & 63] * (x - art.CLOTH)
            k = abs(p) // 1200 * (1 if p >= 0 else -1)      # divs.l truncates toward zero
            v = v >> k if k > 0 else (v << -k) & 0xFFFFFFFFFFFFFFFF
        out += struct.pack(">Q", v)
    return bytes(out)


def png(path, plane):
    S, rows = 4, []
    for y in range(64):
        c = 63 - y
        r = b"".join((b"\xf0\xf0\x40" if plane[x * 8 + (c >> 3)] & (0x80 >> (c & 7)) else b"\x10\x14\x0c") * S
                     for x in range(128))
        rows += [r] * S
    raw = b"".join(b"\0" + r for r in rows)
    ch = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    pathlib.Path(path).write_bytes(b"\x89PNG\r\n\x1a\n" + ch(b"IHDR", struct.pack(">IIBBBBB", 512, 256, 8, 2, 0, 0, 0))
                                   + ch(b"IDAT", zlib.compress(raw)) + ch(b"IEND", b""))


def main():
    remix = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("REMIX", "pirate-flag")
    if "PIRATE FLAG" not in registry.remix(remix).modules:
        print(f"  [SKIP] verify_pirateflag: {remix} does not carry PIRATE FLAG")
        return 0
    if not EMU.exists():
        print("  [SKIP] verify_pirateflag: the ColdFire port is not built (make emu-cf)")
        return 0
    env = dict(os.environ, REMIX=remix, XBUS="1", SPEC="1")
    env.setdefault("BUILD", "0")
    r = subprocess.run([sys.executable, str(ROOT / "tools/build/build_bus.py")], env=env,
                       capture_output=True, text=True, cwd=ROOT)
    if r.returncode:
        sys.exit(f"verify_pirateflag: building {remix} failed:\n{(r.stdout + r.stderr)[-1500:]}")
    work = pathlib.Path(tempfile.mkdtemp(prefix="pflag."))
    image = work / "image.bin"
    image.write_bytes((ROOT / "out/mainos_bus.bin").read_bytes())
    nm = subprocess.run(["m68k-elf-nm", str(ROOT / "out/platform/runtime/runtime.elf")],
                        capture_output=True, text=True).stdout
    sym = {f[2]: int(f[0], 16) for f in (l.split() for l in nm.splitlines()) if len(f) == 3}
    norver = work / "norver.bin"
    norver.write_bytes(STOCK.read_bytes()[0xDE648:0xDE64A])
    # a card with an empty set: without a card and a mount the port's
    # animation stalls on one frame (its clock is DTIM3's, and that run
    # never gets past frame 162), with one it runs to 559 as the unit does
    import emu_card
    (work / "tree" / "OSW" / "AUDIO").mkdir(parents=True)
    (work / "tree" / "OSW" / "P").mkdir()
    card = work / "card.img"
    card.write_bytes(emu_card.build_image(str(work / "tree"), size_mb=64))
    script = work / "q.txt"
    script.write_text("6000 quit\n")
    snap = work / "snap.bin"
    out = subprocess.run([str(EMU), "--image", str(image), "--max", "3000000000",
                          "--preload", f"0x3ffc={norver}", "--card", str(card), "--mount", "--boot-load",
                          "--set", "/OSW", "--project", "P", "--mkii", "--load-ms", "60000", "--boot-logo",
                          "--live-script", str(script), "--watch-pc", f"0x{sym['pirate_frame']:x}",
                          "--mem-dump", f"0x{sym['pirate_snap']:x},1024={snap}"],
                         capture_output=True, text=True, cwd=ROOT).stdout
    (work / "run.log").write_text(out)
    fails = 0

    def check(label, ok, detail=""):
        nonlocal fails
        fails += 0 if ok else 1
        print(f"  [{'PASS' if ok else 'FAIL'}] verify_pirateflag: {label}{'  (' + detail + ')' if detail else ''}")

    frames = re.findall(rf"\] at 0x{sym['pirate_frame']:x} .*?d2-7 (0x[0-9a-f]+|\d+)", out)
    last = int(frames[-1], 0) if frames else -1
    check("the animation's flush reached pirate_frame every frame, to its last (559)",
          len(frames) > 0 and last == 559, f"{len(frames)} calls, last frame {last}")
    got = snap.read_bytes() if snap.exists() else b""
    want = expected(FRAME)
    out_dir = ROOT / "out/pirate-flag"
    out_dir.mkdir(parents=True, exist_ok=True)
    if len(got) == 1024:
        png(out_dir / "frame280.png", got)
    check(f"frame {FRAME} is the flag with its cloth waved as flag.s computes, bit for bit",
          got == want, f"{sum(a != b for a, b in zip(got, want))} byte(s) differ" if got else "no snapshot")
    print(f"  verify_pirateflag: {'PASS' if not fails else f'{fails} FAIL'} (work {work})")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
