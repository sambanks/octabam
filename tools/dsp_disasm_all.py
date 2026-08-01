#!/usr/bin/env python3
"""
Disassemble every P (program) module of both DSP payloads at its correct address.

Uses the load map from dsp_modmap.py, so each module is disassembled at the -pc
the DSP will actually run it at. Output is one .asm per payload, in address
order, plus the per-module .bin files.

    python3 tools/dsp_disasm_all.py        # -> out/dsp/payload_{A,B}.asm
"""
import pathlib, subprocess, sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from dsp_modmap import BASE, IMG, PAYLOADS, SPACE, modules  # noqa: E402

DIS = pathlib.Path("vendor/dsp56300/build/source/disassemble/dsp56kDisassemble")
OUTDIR = pathlib.Path("out/dsp")


def main():
    if not DIS.exists():
        sys.exit(f"missing {DIS} — run ./setup.sh")
    img = IMG.read_bytes()
    OUTDIR.mkdir(parents=True, exist_ok=True)

    for tag, va, ln in PAYLOADS:
        mods, b = modules(img, va, ln)
        pmods = [m for m in mods if m[0] == 0]
        asm = OUTDIR / f"payload_{tag}.asm"
        total_lines = total_dc = 0
        with asm.open("w") as fh:
            fh.write(f"; payload {tag} @0x{va:08x} — {len(pmods)} P modules\n")
            for sp, addr, cnt, data in pmods:
                blob = b[data:data + cnt * 3]
                mb = OUTDIR / f"{tag}_P{addr:05x}.bin"
                mb.write_bytes(blob)
                r = subprocess.run([str(DIS), "-in", str(mb), "-pc", f"{addr:x}", "-le"],
                                   capture_output=True, text=True)
                lines = [l for l in r.stdout.splitlines() if l[:6].strip()
                         and all(c in "0123456789abcdef" for c in l[:6])]
                dc = sum(1 for l in lines if " dc " in l)
                total_lines += len(lines)
                total_dc += dc
                fh.write(f"\n; ==== P:0x{addr:05x}  {cnt} words  "
                         f"({len(lines)} instr, {dc} dc) ====\n")
                fh.write("\n".join(lines) + "\n")
        print(f"payload {tag}: {len(pmods):3d} P modules, {total_lines:6,} instructions, "
              f"{total_dc} undecodable -> {asm}")


if __name__ == "__main__":
    main()
