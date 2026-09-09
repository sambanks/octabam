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
                     a PER-TRACK base -- the very addresses BusVerb,
                     Nimbus and BusDelay hardcode -- and the chooser is
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


def runtime_write_spans(m) -> list[tuple[int, int, str]]:
    """(vaddr, length, patch name) for every sparse write a runtime's recipe
    makes into the OS image -- its fixed-address claims, read from the
    recipe itself so a claim cannot drift from what the build writes."""
    import json
    spec = json.loads((ROOT / m.runtime.recipe).read_text())
    base = spec["format"]["os_load_address"]
    return [(base + w["offset"], len(bytes.fromhex(w["data"])), p["name"])
            for p in spec["patches"] for w in p["writes"]]


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
            if c.cave_addr is None:      # floating: the build allocates
                continue                 # it after everything pinned
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

    # ---- emit() pokes of PINNED caves ---------------------------------------
    # A cave with an emit callable and a fixed address can be asked for its
    # pokes without a build: those are fixed-address byte claims exactly
    # like a hook site, and until 9 Sep 2026 the ledger could not see them
    # -- midi-scenes' 35 redirects and lofi-amf-fix's two DSP words were
    # invisible, and midi-scenes + octakit (both rewrite the apply_part
    # entry 0x40009094) passed as clean. A FLOATING emit cave (cave_addr
    # None) cannot be evaluated before placement and is still skipped.
    # ---- linker-backed units, detours, grown tables, plain pokes -----------
    # A PINNED Linked unit is a cave whose length is only known after the
    # link, so it is claimed here as a 6-byte marker at its address (the
    # build's own free-space check covers the real extent); a floating one
    # is skipped like a floating cave. Detour sites are hook sites. Table
    # refs and Pokes are fixed rewrites, checked as pokes below.
    for m in selected:
        for u in getattr(m, "linked", ()):
            if u.cave_addr is None:
                continue
            for start, length, owner, label in caves:
                if _overlap(start, length, u.cave_addr, 6):
                    clash("ColdFire cave", f"{owner}'s {label}",
                          f"{m.name}'s linked unit {u.label}",
                          f"0x{u.cave_addr:08x}")
            caves.append((u.cave_addr, 6, m.name, f"linked unit {u.label}"))
        for d in getattr(m, "detours", ()):
            if d.site in hooks:
                clash("hook site", hooks[d.site], m.name,
                      f"0x{d.site:08x} -- the second jmp overwrites the first")
            hooks[d.site] = m.name
    pokes: list[tuple[int, int, str, str]] = []
    for m in selected:
        for t in getattr(m, "tables", ()):
            for addr, _old in t.refs:
                pokes.append((addr, 4, m.name, f"table ref ({t.label})"))
        for p in getattr(m, "pokes", ()):
            pokes.append((p.addr, len(p.expect), m.name, f"poke {p.note or hex(p.addr)}"))
    for m in selected:
        for c in m.cf_patches:
            if c.emit is None or c.cave_addr is None:
                continue
            _, cpokes = c.emit(c.cave_addr)
            for pa, expect, _write in cpokes:
                span = (pa, len(expect), m.name, c.label)
                for start, length, owner, label in caves:
                    if owner != m.name and _overlap(start, length, pa, len(expect)):
                        clash("ColdFire cave", f"{owner}'s {label}",
                              f"{m.name}'s poke at 0x{pa:08x} ({c.label})",
                              f"0x{max(start, pa):08x}")
                for haddr, owner in hooks.items():
                    if owner != m.name and _overlap(haddr, 6, pa, len(expect)):
                        clash("hook site", owner, f"{m.name}'s poke ({c.label})",
                              f"0x{haddr:08x} -- both rewrite the same instruction")
                for ostart, olength, oowner, olabel in pokes:
                    if oowner != m.name and _overlap(ostart, olength, pa, len(expect)):
                        clash("poke site", f"{oowner} ({olabel})", f"{m.name} ({c.label})",
                              f"0x{max(ostart, pa):08x} -- both rewrite the same bytes")
                pokes.append(span)

    # ---- loader-appended runtimes (schema.Runtime) ------------------------
    # The append sits at the end of the OS image and its loader owns one
    # DRAM window, so an image carries at most one. Its recipe's sparse
    # writes are fixed-address byte claims like any pinned cave, so they are
    # checked against every pinned cave, hook site and emit poke above --
    # the apply_part entry (0x40009094) is a real three-way conflict between
    # midi-scenes, octamax and octakit, and this is where it is refused.
    runtimes = [m for m in selected if getattr(m, "runtime", None) is not None]
    hosts = {m.key for m in runtimes}
    for m in selected:
        x = getattr(m, "runtime_ext", None)
        if x is not None and x.host not in hosts:
            clash("runtime extension", m.name, f"(no {x.host})",
                  f"a DRAM host it extends -- {x.host} is not in this remix")
    for i, a in enumerate(runtimes):
        for b in runtimes[i + 1:]:
            clash("appended runtime", a.name, b.name,
                  "the end of the OS image and the loader's DRAM window -- "
                  "one runtime per image")
    for m in runtimes:
        for start, length, label in runtime_write_spans(m):
            for cstart, clength, owner, clabel in caves:
                if _overlap(cstart, clength, start, length):
                    clash("ColdFire cave", f"{owner}'s {clabel}",
                          f"{m.name}'s runtime write {label}",
                          f"0x{max(cstart, start):08x}")
            for haddr, owner in hooks.items():
                if _overlap(haddr, 6, start, length):
                    clash("hook site", owner, f"{m.name} (runtime write {label})",
                          f"0x{haddr:08x} -- both rewrite the same instruction")
            for pstart, plength, powner, plabel in pokes:
                if _overlap(pstart, plength, start, length):
                    clash("poke site", f"{powner} ({plabel})",
                          f"{m.name} (runtime write {label})",
                          f"0x{max(pstart, start):08x} -- both rewrite the same bytes")

    # ---- the per-core FX2 instance buffer region --------------------------
    # Y:0x4000-0xBFFF is TWO FX2 instance slots of 16,384 words, per core and
    # not per instance in any sense a module can rely on: BusVerb hardcodes
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
    #   BusVerb   all four of its core's -- tank in tracks 1-2's slots,
    #              relocated buffers in tracks 3-4's. No track on that core
    #              can host an allocating stock effect.
    #   Nimbus     tracks 1-2's slots of whichever core hosts it.
    #   BusDelay  tracks 3-4's (its lines are based at 0x38000/0x3c000), so
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
    # An FX1-ONLY allocator reader (Claims.fx1_only) is exempt: on an FX2
    # slot it writes nothing, and on FX1 the allocator tops out at 0x3fff,
    # below every buffer a module of ours pins. Its render gate proves
    # the dry FX2 pass; the ledger takes the declaration.
    stocked = [m for m in selected
               if getattr(m, "claims", None) is not None
               and m.claims.stock_instance_buffer
               and not m.claims.fx1_only]
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
