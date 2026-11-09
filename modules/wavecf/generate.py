#!/usr/bin/env python3
"""Compile engine.c + wcf.c + wcf_data.c (one translation unit) and add tables.s: the block between the
GENERATED ENGINE markers of wavecf.s.  --check refuses a stale wavecf.s.

    python3 modules/wavecf/generate.py            # rewrites the block
    python3 modules/wavecf/generate.py --check
"""
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
FLAGS = ["-mcpu=54455", "-O2", "-ffreestanding", "-fno-builtin", "-fno-common",
         "-fno-jump-tables", "-fno-asynchronous-unwind-tables", "-fno-ident",
         "-fomit-frame-pointer", "-fno-zero-initialized-in-bss", "-Wall", "-Wextra", "-Werror"]
BEGIN = "| >>> GENERATED ENGINE (modules/wavecf/generate.py) -- do not edit by hand\n"
END = "| <<< GENERATED ENGINE\n"


def block():
    unit = '#include "engine.c"\n#include "wcf.c"\n#include "wcf_data.c"\n'
    # run in HERE with relative names: the inline asm's line markers carry the source path
    cc = subprocess.run(["m68k-elf-gcc", *FLAGS, "-I", ".", "-S", "-x", "c", "-o", "-", "-"],
                        input=unit, text=True, check=True, cwd=HERE, capture_output=True).stdout
    return BEGIN + cc + "\n" + (HERE / "tables.s").read_text() + END


def main():
    p = HERE / "wavecf.s"
    s = p.read_text()
    a, b = s.index(BEGIN), s.index(END) + len(END)
    new = s[:a] + block() + s[b:]
    if "--check" in sys.argv:
        if new != s:
            raise SystemExit(f"stale: {p}")
        print("WAVE generated engine matches")
    else:
        p.write_text(new)
        print("WAVE engine generated into wavecf.s")


if __name__ == "__main__":
    main()
