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
  stock buffers      declared (Claims.stock_instance_buffer, from a scan
                     of the payload disassembly). A stock effect that takes
                     an instance buffer from the host's bump allocator gets
                     a PER-TRACK base -- the very addresses ChonVerb,
                     Nimbus and BongDelay hardcode -- and the chooser is
                     one list for all eight tracks, so the build cannot
                     know which track it lands on. Refused beside any
                     module with fixed Y buffers.

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

from remix.schema import YBase

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

    # ---- the per-core FX2 instance buffer region --------------------------
    # Y:0x4000-0xBFFF is TWO FX2 instance slots of 16,384 words, per core and
    # not per instance in any sense a module can rely on: ChonVerb hardcodes
    # its tank there and Nimbus hardcodes its granular line there, so two of
    # them on one core write over each other. Each works perfectly alone.
    # Declared rather than scanned -- see Claims.owns_fx2_buffers for why a
    # scan cannot tell an address from a mask.
    buf = [m for m in selected
           if getattr(m, "claims", None) is not None
           and m.claims.owns_fx2_buffers]
    for i, a in enumerate(buf):
        for b in buf[i + 1:]:
            clash("FX2 instance buffers", a.name, b.name,
                  "Y:0x4000-0xBFFF -- that region is per CORE, so only one "
                  "of them can be hosted on a given core; each works alone")

    # ---- stock effects that allocate an instance buffer -------------------
    # The allocator's bases are per TRACK SLOT, and this is MEASURED -- read
    # from X:0x255 in BOTH payloads of the pristine image, 2 Sep 2026 (the
    # words are little-endian, which only shows above 0x10000, and reading
    # them big-endian gives a plausible 0x00003 instead of 0x30000):
    #
    #   core 0 FX2:  0x4000  0x8000  0x30000  0x34000
    #   core 1 FX2:  0x4000  0x8000  0x38000  0x3c000
    #
    # ⚠️ AND THE SLOTS ARE ONE PER TRACK, not a pool: each track allocates
    # FX1 then FX2, so track k's FX2 effect always gets entry 1+2k
    # (docs/DSP.md, "the allocator's instance model"). Nothing is first-come.
    #
    #   ChonVerb   all four of its core's -- tank in tracks 1-2's slots,
    #              relocated buffers in tracks 3-4's. No track on that core
    #              can host an allocating stock effect.
    #   Nimbus     tracks 1-2's slots of whichever core hosts it.
    #   BongDelay  tracks 3-4's (its lines are based at 0x38000/0x3c000), so
    #              on ITS core an allocating stock effect is safe on tracks
    #              1-2 and collides on 3-4.
    #
    # THAT IS STILL A REFUSAL, because the chooser is ONE LIST for all eight
    # tracks: the image cannot say "FLANGER, but only on tracks 1-2". Each
    # works perfectly alone, which is the worst shape a defect can have.
    fixed = [m for m in selected
             if (getattr(m, "claims", None) is not None
                 and m.claims.owns_fx2_buffers)
             or (m.dsp is not None and m.dsp.ybase is not YBase.NEVER)]
    stocked = [m for m in selected
               if getattr(m, "claims", None) is not None
               and m.claims.stock_instance_buffer]
    # ⚠️ THIS REFUSES AN FX2 CHOOSER ROW, NOT THE EFFECT. A stock effect left
    # out of a remix keeps its code, descriptor and dispatch, so the four
    # dual-menu ones are still on FX1 and still work -- and the collision
    # cannot follow them there, because the allocator keeps SEPARATE tables
    # and an FX1 slot tops out at 0x3fff while every FX2 buffer a module of
    # ours pins starts at 0x4000 or in the shared window.
    for a in stocked:
        for b in fixed:
            clash("stock instance buffer", a.name, b.name,
                  "the allocator's per-track FX2 buffer slots -- the stock "
                  "effect's buffer lands on whichever track hosts it and "
                  "that is where the module's fixed buffers are; the chooser "
                  "cannot keep them on different cores. Its FX2 ROW is what "
                  "is refused: on FX1 it keeps working, out of reach")

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
