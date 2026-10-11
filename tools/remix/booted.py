"""The memory the unit reads after the loader has run, for tools that read
the built image by address.

The image file holds the OS from 0x40000400; a remix with DRAM units also
has its platform runtime at the arena reserve's base, depacked there at
boot (tools/remix/platform_build.py). Since 8 Oct 2026 that runtime holds
the descriptor clones and label formatters of such a remix, so a tool that
follows FX2_IDS into a descriptor reads it here. image() returns the file's
bytes with the runtime placed at its offset, so `mem[addr - BASE]` reads
either; a remix without DRAM units gets the file unchanged.
"""

import json
import pathlib

BASE = 0x40000400
PLATFORM = pathlib.Path("out/platform")


def image(img: bytes, platform: pathlib.Path = PLATFORM) -> bytes:
    """`img` (the built image's bytes) with the linked DRAM runtime that the
    same build wrote under `platform` placed at its base."""
    from remix import platform_build
    layout = platform / platform_build.LAYOUT
    raw = platform / "runtime.raw"
    if not layout.exists() or not raw.exists():
        return img
    base = json.loads(layout.read_text()).get("base")
    if base is None:
        return img
    rt = raw.read_bytes()
    off = base - BASE
    if off < len(img):
        return img
    return bytes(img) + bytes(off - len(img)) + rt
