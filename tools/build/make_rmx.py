#!/usr/bin/env python3
"""A raw OS image for REMIX SWITCH (modules/remix-switch): the bytes the bootstrap
would depack to 0x40000400, for /BRAIN/REMIXES/ on the card. The file is
named as the image names itself (remix.brain.image_name: `<REMIX> <BUILD>`,
A-Z 0-9 space . _ -, 15 characters), so REMIX SWITCH can tell the running
image's row; `make image` writes one beside the .bin.

    make rmx REMIX=<name> [RMX=NAME]     # out/mainos_bus.bin -> out/<NAME>.RMX
    make rmx-stock                       # your stock MAIN OS -> out/STOCK 1.40C.RMX

Checks what the switcher checks before it stops anything, so a file that
passes here is one the unit will offer and stage: the OS entry's first
instruction, a length that fits the stage, and the bootstrap version word
equal to stock 1.40C's (the chainloader compares it with NOR's; a newer one
would reprogram the bootstrap, so it never runs). An .RMX is Elektron's OS
with your changes: like the .bin, it never leaves your machine and your card.
"""
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

ROOT = pathlib.Path(__file__).resolve().parents[2]
INC = ROOT / "modules/remix-switch/osw.inc"
STOCK = ROOT / "out/raw/section_3_MAIN_OS.bin"
OS_FIRST = bytes.fromhex("4fefffe4")


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    src, name = pathlib.Path(sys.argv[1]), sys.argv[2]
    c = {m.group(1): int(m.group(2), 0) for m in
         re.finditer(r"^\s*\.set\s+(\w+),\s*(0x[0-9a-fA-F]+|\d+)", INC.read_text(), re.M)}
    from remix import brain
    base = re.sub(r"[^A-Z0-9 ._-]", "", name.upper()).strip()
    if not base or len(base) > brain.IMAGE_NAME_MAX:
        sys.exit(f"make_rmx: {name!r} is not a name of 1-{brain.IMAGE_NAME_MAX} characters "
                 f"(A-Z 0-9 space . _ -)")
    img, stock = src.read_bytes(), STOCK.read_bytes()
    ver = c["OS_VEROFF"]
    if img[:4] != OS_FIRST:
        sys.exit(f"make_rmx: {src} does not start with the OS entry ({img[:4].hex()}): not a raw MAIN OS")
    if not (ver + 2 <= len(img) <= c["OSW_MAXLEN"]):
        sys.exit(f"make_rmx: {src} is {len(img):,} B; the stage holds {c['OSW_MAXLEN']:,}")
    if img[ver:ver + 2] != stock[ver:ver + 2]:
        sys.exit(f"make_rmx: {src} carries bootstrap version {img[ver:ver + 2].hex()}, stock 1.40C "
                 f"{stock[ver:ver + 2].hex()}: the chainloader would refuse it (BVER)")
    out = ROOT / "out" / f"{base}.RMX"
    out.write_bytes(img)
    print(f"{out.relative_to(ROOT)}: {len(img):,} B -- copy it to /BRAIN/REMIXES/ on the card, then "
          f"MAIN MENU > BRAIN")


if __name__ == "__main__":
    main()
