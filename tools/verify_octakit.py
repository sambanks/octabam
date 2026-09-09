#!/usr/bin/env python3
"""The Octakit port's one exact claim, checked: stock 1.40C + Em's writes
+ Em's append -- and NOTHING of octabam's -- is byte-identical to the
combined OS her own repository builds (`output.os` in her firmware.json).

`make bus REMIX=octakit` cannot show this, because an octabam image always
carries the build's own FX2 chooser and DSP null-stub edits on top. This
applies her recipe alone, through the same tools/remix/runtime_build.py
the build uses (so the compiler, the packer port and the guard/write
discipline are all under test), and compares.

SKIPs, rather than fails, when the toolchain or the submodule is absent:
`make verify` runs on machines that never asked for Octakit.
"""
import hashlib
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from remix import registry, runtime_build  # noqa: E402

mod = registry.modules().get("OCTAKIT")
if mod is None or mod.runtime is None:
    print("  [SKIP] verify_octakit: no OCTAKIT module")
    sys.exit(0)
if not (ROOT / mod.runtime.recipe).exists():
    print("  [SKIP] verify_octakit: submodule not checked out "
          "(git submodule update --init modules/octakit/upstream)")
    sys.exit(0)
if any(shutil.which(t) is None for t in runtime_build.TOOLS):
    print("  [SKIP] verify_octakit: m68k-elf toolchain not installed (make setup)")
    sys.exit(0)

stock = (ROOT / "out/raw/section_3_MAIN_OS.bin").read_bytes()
writes, append, info = runtime_build.build(mod.runtime, stock,
                                           ROOT / "out/runtime/_verify_octakit")
img = bytearray(stock)
for va, expect, write, name in writes:
    off = va - 0x40000400
    assert bytes(img[off:off + len(expect)]) == expect, name
    img[off:off + len(write)] = write
img.extend(append)
got = hashlib.sha256(bytes(img)).hexdigest()
want = info["output_os"]["sha256"]
ok = got == want and len(img) == info["output_os"]["size"]
print(f"  [{'PASS' if ok else 'FAIL'}] verify_octakit: stock + {len(writes)} writes + "
      f"{len(append):,} B append == Em's own combined OS ({info['id']} {info['version']}, "
      f"m68k-elf-gcc {info['gcc']} vs her pinned {info['gcc_pinned']})")
if not ok:
    print(f"         got  {len(img)} B {got}\n         want {info['output_os']['size']} B {want}")
    sys.exit(1)
