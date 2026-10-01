#!/usr/bin/env python3
"""A raw OS image for OS SWITCH (modules/os-switch): the bytes the bootstrap
would depack to 0x40000400, named for the card root (12 characters at
most, what MAIN MENU > OS shows in one line; `make image` writes one named
after the build's VERSION beside the .bin).

    make obi REMIX=<name> [OBI=NAME]     # out/mainos_bus.bin -> out/NAME.OBI
    make obi-stock                       # your stock MAIN OS -> out/STOCK140.OBI

Checks what the switcher checks before it stops anything, so a file that
passes here is one the unit will offer and stage: the OS entry's first
instruction, a length that fits the stage, and the bootstrap version word
equal to stock 1.40C's (the chainloader compares it with NOR's; a newer one
would reprogram the bootstrap, so it never runs). An .OBI is Elektron's OS
with your changes: like the .bin, it never leaves your machine and your card.
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
INC = ROOT / "modules/os-switch/osw.inc"
STOCK = ROOT / "out/raw/section_3_MAIN_OS.bin"
OS_FIRST = bytes.fromhex("4fefffe4")


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    src, name = pathlib.Path(sys.argv[1]), sys.argv[2]
    c = {m.group(1): int(m.group(2), 0) for m in
         re.finditer(r"^\s*\.set\s+(\w+),\s*(0x[0-9a-fA-F]+|\d+)", INC.read_text(), re.M)}
    base = re.sub(r"[^A-Z0-9_-]", "", name.upper())[:12]
    if not base:
        sys.exit(f"make_obi: {name!r} leaves no name (A-Z 0-9 _ -)")
    img, stock = src.read_bytes(), STOCK.read_bytes()
    ver = c["OS_VEROFF"]
    if img[:4] != OS_FIRST:
        sys.exit(f"make_obi: {src} does not start with the OS entry ({img[:4].hex()}): not a raw MAIN OS")
    if not (ver + 2 <= len(img) <= c["OSW_MAXLEN"]):
        sys.exit(f"make_obi: {src} is {len(img):,} B; the stage holds {c['OSW_MAXLEN']:,}")
    if img[ver:ver + 2] != stock[ver:ver + 2]:
        sys.exit(f"make_obi: {src} carries bootstrap version {img[ver:ver + 2].hex()}, stock 1.40C "
                 f"{stock[ver:ver + 2].hex()}: the chainloader would refuse it (BVER)")
    out = ROOT / "out" / f"{base}.OBI"
    out.write_bytes(img)
    print(f"{out.relative_to(ROOT)}: {len(img):,} B -- copy it to the card ROOT, then "
          f"MAIN MENU > OS")


if __name__ == "__main__":
    main()
