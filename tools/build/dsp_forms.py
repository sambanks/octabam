#!/usr/bin/env python3
"""DSP instruction forms with no stock site (docs/firmware/CHIP.md, the instruction-form register).

usage: python3 tools/build/dsp_forms.py out/dsp/payload_A.asm out/dsp/payload_B.asm <hex words file> <pc, hex>

The two stock listings come from tools/build/dsp_disasm_all.py; the words file holds the module's code words
(not its tables) as space-separated hex, e.g. from out/dsp/demand_records.json or window_records.json.
A form is the disassembled text with immediates, addresses and displacements blanked (registers, spaces and
addressing modes kept) plus the instruction's word count, so a short and a long encoding are different forms.
"""
import re
import subprocess
import sys

DIS = "vendor/dsp56300/build/source/disassemble/dsp56kDisassemble"
LINE = re.compile(r"^([0-9a-f]{5,6}):\s+(.*?)\s*;\s*([0-9a-f]{6})(?:\s+([0-9a-f]{6}))?\s*$")


def form(text, nwords):
    t = re.sub(r"\s+", " ", text.strip())
    t = re.sub(r"\b(func|loc|sub|lab)_[0-9a-f]+\b", "L", t)   # branch targets
    t = re.sub(r"\(r([0-7])-", r"(r\1+", t)              # a displacement's sign is not a form
    t = re.sub(r"[<>]?\$[0-9a-f]+", "N", t)          # immediates, addresses, displacements
    t = re.sub(r"#[<>]?-?[0-9]+\b", "#N", t)
    t = re.sub(r"\+-?[0-9]+\)", "+N)", t)
    return f"{t}  [{nwords}w]"


def forms_of(lines):
    out = {}
    for l in lines:
        m = LINE.match(l)
        if not m:
            continue
        f = form(m.group(2), 2 if m.group(4) else 1)
        out.setdefault(f, m.group(0))
    return out


stock = {}
for p in sys.argv[1:3]:
    stock.update(forms_of(open(p).read().splitlines()))
r = subprocess.run([DIS, "-in", sys.argv[3], "-pc", sys.argv[4]], capture_output=True, text=True)
mine = forms_of(r.stdout.splitlines())
new = {f: ex for f, ex in mine.items() if f not in stock}
print(f"{len(mine)} forms, {len(new)} with no stock site")
for f, ex in sorted(new.items()):
    print(f"  {f:60s} e.g. {ex.split(';')[0].strip()}")
