"""Cross-module resource collisions, caught before a byte is written.

Nearly every expensive failure in this project's history was two things
quietly sharing one resource: a delay based where the reverb's buffers lived,
a scratch slot used twice, a literal rewritten by a substitution meant for
something else. With one author and two effects that is survivable, because
one person holds the whole map. With contributed modules it is not, and the
symptom is never "your module is wrong" -- it is somebody else's effect
sounding broken.

So the build refuses to start when two selected modules claim the same
resource, and says which two.

WHAT IS CHECKED, and how it knows:

  fx2 ids            declared. Two modules answering to one id would
                     overwrite each other's descriptor and dispatch.
  ColdFire caves     declared. Overlapping machine code is silent and fatal.
  hook sites         declared. Two modules hooking one instruction: the
                     second overwrites the first's jsr, and the first module
                     simply never runs.
  core-private Y     DERIVED by scanning the module's own source for
                     `y:>$09xx`. Low Y is per CORE, not per instance, so
                     every effect sharing a core shares these words.

Derived beats declared wherever it is possible: a scan cannot go stale. Its
limit is that it only sees what the code actually references, so a word a
module means to RESERVE but does not yet touch has to be declared -- that is
what Claims.reserved_private_y is for.

WHAT IS NOT CHECKED YET, and why not. The shared 64K window (Y:0x30000-
0x3FFFF) is the biggest genuine hazard and is absent here on purpose: the
exact extents of the two servers' buffers are not established well enough to
write down, and a claim that is merely plausible is worse than none, because
it reads like a guarantee. The P donor region is not here either -- placement
already refuses to overrun it, and that check is exact.
"""

from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]

_PRIVATE_Y = re.compile(r"y:>\$(09[0-9a-f]{2})\b", re.I)


def private_y(m) -> set[int]:
    """Core-private Y words this module touches, scanned from its source."""
    words: set[int] = set()
    if m.dsp is not None:
        src = ROOT / m.dsp.asm
        if src.exists():
            words |= {int(h, 16) for h in _PRIVATE_Y.findall(src.read_text())}
    if getattr(m, "claims", None) is not None:
        words |= set(m.claims.reserved_private_y)
    return words


def _overlap(a_start, a_len, b_start, b_len) -> bool:
    return a_start < b_start + b_len and b_start < a_start + a_len


def check(selected) -> list[str]:
    """Return a list of collisions among these modules. Empty means clean."""
    problems: list[str] = []

    def clash(what, owner_a, owner_b, detail):
        problems.append(f"{what}: {owner_a} and {owner_b} both claim {detail}")

    # ---- FX2 ids ----------------------------------------------------------
    ids: dict[int, str] = {}
    for m in selected:
        if m.menu is None:
            continue
        if m.menu.fx2_id in ids:
            clash("fx2 id", ids[m.menu.fx2_id], m.name,
                  f"0x{m.menu.fx2_id:02x}")
        ids[m.menu.fx2_id] = m.name

    # ---- ColdFire caves and hook sites ------------------------------------
    caves: list[tuple[int, int, str, str]] = []
    hooks: dict[int, str] = {}
    for m in selected:
        for c in m.cf_patches:
            for start, length, owner, label in caves:
                if _overlap(start, length, c.cave_addr, len(c.pinned)):
                    clash("ColdFire cave", f"{owner}'s {label}",
                          f"{m.name}'s {c.label}",
                          f"0x{max(start, c.cave_addr):08x}")
            caves.append((c.cave_addr, len(c.pinned), m.name, c.label))
            if c.hook_addr is not None:
                if c.hook_addr in hooks:
                    clash("hook site", hooks[c.hook_addr], m.name,
                          f"0x{c.hook_addr:08x} -- the second jsr overwrites "
                          f"the first, so the first module never runs")
                hooks[c.hook_addr] = m.name

    # ---- core-private Y ---------------------------------------------------
    # Low Y is per CORE. Two effects that can share a core share these words,
    # so this is checked across every selected module, not per payload.
    owner: dict[int, str] = {}
    for m in selected:
        for w in sorted(private_y(m)):
            if w in owner:
                clash("core-private Y", owner[w], m.name,
                      f"y:$0{w:03x} -- low Y is per core, so effects sharing "
                      f"a core share this word")
            owner[w] = m.name

    return problems
