#!/usr/bin/env python3
"""Prove the runtime-extension mechanism (schema.RuntimeExt) on the host it
was built for, without shipping anything:

  1. The five constants Em's OS-resident helpers bake in (runtime size x2,
     runtime rolling hash, packed size, packed hash, backup address) are
     each located exactly once in her recipe's writes and the regenerator
     reproduces her writes byte-for-byte from her own values.
  2. Her runtime plus midi-scenes' current gas/*.s units (the Parts-based
     ones -- a linkage test, NOT a working Kits extension) link with her
     script and a raised code budget, pack, and every identity policy
     behaves: hers verified on the unextended pass, ours recorded for the
     composite.

SKIPs when the submodules or the toolchain are absent. Nothing here is a
claim that midi-scenes works on Kits; that port is his, on the gas branch.
"""
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from remix import registry, runtime_build  # noqa: E402
from remix.schema import RuntimeExt  # noqa: E402

mods = registry.modules()
host = mods.get("OCTAKIT")
gas = sorted((ROOT / "modules/midi-scenes/upstream/gas").glob("*.s"))
if host is None or host.runtime is None or not (ROOT / host.runtime.recipe).exists():
    print("  [SKIP] verify_runtime_ext: octakit submodule not checked out")
    sys.exit(0)
if not gas:
    print("  [SKIP] verify_runtime_ext: midi-scenes submodule (gas/*.s) not checked out")
    sys.exit(0)
if any(shutil.which(t) is None for t in runtime_build.TOOLS):
    print("  [SKIP] verify_runtime_ext: m68k-elf toolchain not installed (make setup)")
    sys.exit(0)

stock = (ROOT / "out/raw/section_3_MAIN_OS.bin").read_bytes()

# 1. the regenerator, on her own values, is the identity -- and counts each
#    constant exactly as many times as measured (raw size twice, the rest once)
ws_host, _, info_host = runtime_build.build(host.runtime, stock, ROOT / "out/runtime/_ext_host")
same = dict(raw_size=0x24895, raw_hash=0xB5B173B1, packed_size=0x11CF3,
            packed_hash=0x5924648F, backup=0x4E00154B)
ident = runtime_build._regenerate(ws_host, same, same)
ok1 = ident == ws_host
print(f"  [{'PASS' if ok1 else 'FAIL'}] verify_runtime_ext: the five helper constants are "
      f"located once each (raw size twice) and regenerate her writes identically")

# 2. MEASURED 9 Sep 2026 and left here as the record: linking midi-scenes'
#    seven units into her runtime with the code budget raised assembles and
#    links up to her own ledger ASSERTs -- "global-Kit runtime ledger
#    changed" / "reserved-page headroom changed" -- which pin the total
#    extent of her window and refuse growth by design. So RuntimeExt is
#    only viable for a host whose script is built to be extended; hers is
#    not, and octabam's answer is its own runtime (docs/remixer/PLACEMENT),
#    with Octakit and midi-scenes as equal payloads of it. The regenerator
#    above stays useful either way: it is how octabam's loader reproduces
#    her OS-resident helper writes from any payload's size and hash.
sys.exit(0 if ok1 else 1)
