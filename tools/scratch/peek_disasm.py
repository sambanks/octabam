#!/usr/bin/env python3
"""Disassemble `--dsp-peek core:P:addr,len` lines out of an ot_emu report
(the built image's payloads as loaded, not the stock module map).
  peek_disasm.py REPORT [grep]"""
import sys, re, pathlib, subprocess, tempfile
DIS = "vendor/dsp56300/build/source/disassemble/dsp56kDisassemble"
pat = sys.argv[2] if len(sys.argv) > 2 else None
for line in open(sys.argv[1]):
    m = re.match(r"\s*core (\d) P:0x([0-9a-f]+):((?: [0-9a-f]{6})+)", line)
    if not m: continue
    core, addr, ws = int(m.group(1)), int(m.group(2), 16), m.group(3).split()
    blob = b"".join(int(w, 16).to_bytes(3, "little") for w in ws)   # -le: little-endian words
    with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f: f.write(blob); path = f.name
    r = subprocess.run([DIS, "-in", path, "-pc", f"{addr:x}", "-le"], capture_output=True, text=True)
    print(f"; core {core} P:{addr:#07x} ({len(ws)} words)")
    for l in r.stdout.splitlines():
        if l[:6].strip() and all(c in "0123456789abcdef" for c in l[:6]) and (pat is None or re.search(pat, l)):
            print("   " + l)
