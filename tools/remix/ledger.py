"""Cross-module resource collisions, caught before a byte is written.

The build refuses to start when two selected modules claim the same
resource, and says which two.

Checked, and how it knows:

  fx2 ids            declared. Two modules on one id would overwrite each
                     other's descriptor and dispatch.
  ColdFire caves     declared. Overlapping machine code is silent and fatal.
  hook sites         declared. Two modules hooking one instruction: the
                     second overwrites the first's jsr and the first never
                     runs.
  detours, pokes,    declared. Fixed-address rewrites, checked against every
  table refs,        cave, hook site and emit poke; a runtime's recipe
  runtime writes     writes are claims of the same kind.
  overrides          a bridge's claim stands in for the overridden module's
                     at that site; a bridge naming a module the remix does
                     not carry is refused.
  core-private Y     derived by scanning the module's source for `y:>$09xx`.
                     Low Y is per core, not per instance, so every effect
                     sharing a core shares these words.
  stock buffers      declared (Claims.stock_instance_buffer). A stock effect
                     that takes an instance buffer from the host's bump
                     allocator gets a per-track base -- the addresses
                     BusVerb, Nimbus and BusDelay hardcode -- and the chooser
                     is one list for all eight tracks, so the build cannot
                     know which track it lands on. Refused beside any module
                     with fixed Y buffers.
  appended runtimes  one per image (the end of the OS and the loader's
                     window).
  arena reserves     the total must leave the unit sample memory.

Derived beats declared where possible: a scan cannot go stale. Its limit is
that it sees only what the code references, so a word a module means to
reserve but does not yet touch is declared (Claims.reserved_private_y).

Not checked: the shared 64K window (Y:0x30000-0x3FFFF); the two servers'
buffer extents there are not established well enough to write down. The P
donor region is not here either: placement refuses to overrun it, exactly.
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


# An X-space reference by literal: absolute, register-relative with a
# displacement, or an immediate into an address/offset register.
_X_ADDR = re.compile(r"x:>\$([0-9a-f]{1,6})\b|x:\(r[0-7]\+\$([0-9a-f]{1,6})\)"
                     r"|#>\$([0-9a-f]{1,6}),[rn][0-7]\b", re.I)


def curve_bank_claims(selected) -> tuple[list[str], list[str]]:
    """(names of modules whose table the build may park in the stock curve
    bank, names of modules whose source addresses that record itself),
    both scanned from the modules' sources -- see check() for the rule."""
    from remix import stock
    lo, hi = stock.CURVE_BANK[0], stock.CURVE_BANK[0] + stock.CURVE_BANK[1]
    tables, hard = [], []
    for m in selected:
        if m.dsp is None:
            continue
        src = ROOT / m.dsp.asm
        code = ""
        if src.exists():
            code = "\n".join(l.split(";", 1)[0]
                             for l in src.read_text().splitlines())
        if m.dsp.ptable or "$facade" in code:
            tables.append(m.name)
        for g in _X_ADDR.findall(code):
            if lo <= int(next(h for h in g if h), 16) < hi:
                hard.append(m.name)
                break
    return tables, hard


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
    # ---- linker-backed units, detours, grown tables, plain pokes -----------
    # A PINNED Linked unit is a cave whose length is only known after the
    # link, so it is claimed here as a 6-byte marker at its address (the
    # build's own free-space check covers the real extent); a floating one
    # is skipped like a floating cave. Detour sites are hook sites. Table
    # refs and Pokes are fixed rewrites, checked as pokes below.
    # ---- overrides (schema.Override): a bridge's claim stands in ---------
    # The overridden module's detour or recipe write at that site is not a
    # claim any more; the bridge's own detour is. A bridge naming a module
    # the remix does not carry is refused: there is nothing to bridge.
    keys = {m.key for m in selected}
    overridden_detours: set[tuple[int, str]] = set()      # (site, module key)
    overridden_writes: set[tuple[str, str]] = set()       # (module key, write name)
    for m in selected:
        for o in getattr(m, "overrides", ()):
            if o.module not in keys:
                clash("override", m.name, f"(no {o.module})",
                      f"0x{o.site:08x} -- it bridges {o.module}, which this remix "
                      f"does not carry")
            if o.write is None:
                overridden_detours.add((o.site, o.module))
            else:
                overridden_writes.add((o.module, o.write))

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
            if (d.site, m.key) in overridden_detours:
                continue                 # a bridge's stub stands in for it
            if d.site in hooks:
                clash("hook site", hooks[d.site], m.name,
                      f"0x{d.site:08x} -- the second jmp overwrites the first")
            hooks[d.site] = m.name
    pokes: list[tuple[int, int, str, str]] = []
    for m in selected:
        for t in getattr(m, "tables", ()):
            for addr, _old in t.refs:
                pokes.append((addr, 4, m.name, f"table ref ({t.label})"))
        for r in getattr(m, "symbol_refs", ()):
            pokes.append((r.addr, 4, m.name,
                          f"symbol ref {r.unit}:{r.symbol} ({r.note or hex(r.addr)})"))
        for p in getattr(m, "pokes", ()):
            pokes.append((p.addr, len(p.expect), m.name, f"poke {p.note or hex(p.addr)}"))
    # A FLOATING emit cave's poke ADDRESSES do not depend on where the cave
    # lands -- only the values written do -- so it is evaluated at a probe
    # address purely to learn its sites. Until it was skipped,
    # and the matrix said Octakit and CC PAGE 2 compose while the build
    # refused them: both rewrite the MIDI control-parameter dispatch entry
    # at 0x400d64a0 (her seven midi-control-parameter writes, its repoint).
    PROBE_ADDR = 0x400D7000
    for m in selected:
        for c in m.cf_patches:
            if c.emit is None:
                continue
            _, cpokes = c.emit(c.cave_addr if c.cave_addr is not None else PROBE_ADDR)
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

    # ---- pinned return addresses (schema.Runtime.pinned_returns) ----------
    # A runtime's replacement routine may validate its CALLER: Octakit's
    # part reload reads the return address off the stack and traps on any
    # but the two stock sites' own. A detour of that `jsr` whose stub
    # returns the callee through its own continuation (Detour.subst_return
    # -- midisc's `reload`) trips it, and no byte overlaps: OKMS1 ran until
    # the first Part Reload (14 Sep 2026, VEC:04 in her report_fatal with
    # D0 = his rel_after). Refused by name unless a bridge overrides the
    # detour (modules/kits-reload).
    for r in selected:
        pins = getattr(getattr(r, "runtime", None), "pinned_returns", ())
        if not pins:
            continue
        for m in selected:
            if m is r:
                continue
            for d in getattr(m, "detours", ()):
                if not d.subst_return or (d.site, m.key) in overridden_detours:
                    continue
                span = d.pad_to or len(d.expect)
                for ret in pins:
                    if d.site < ret <= d.site + span:
                        clash("pinned return", r.name, m.name,
                              f"0x{ret:08x} -- {r.name}'s callee validates the return "
                              f"address of the jsr at 0x{d.site:08x} and traps on any "
                              f"other; {m.name}'s stub ({d.note or d.symbol}) returns it "
                              f"through its own -- bridge the site")

    # ---- loader-appended runtimes (schema.Runtime) ------------------------
    # The append sits at the end of the OS image and its loader owns one
    # DRAM window, so an image carries at most one. Its recipe's sparse
    # writes are fixed-address byte claims like any pinned cave, so they are
    # checked against every pinned cave, hook site and emit poke above --
    # the apply_part entry (0x40009094) is a real three-way conflict between
    # midi-scenes, octamax and octakit, and this is where it is refused.
    runtimes = [m for m in selected if getattr(m, "runtime", None) is not None]
    hosts = {m.key for m in runtimes}
    for i, a in enumerate(runtimes):
        for b in runtimes[i + 1:]:
            clash("appended runtime", a.name, b.name,
                  "the end of the OS image and the loader's DRAM window -- "
                  "one runtime per image")
    # ---- the audio page arena (schema.ArenaReserve) -----------------------
    # Every reservation is stacked by the build; the one thing to refuse
    # here is a total that leaves the unit too little for samples and
    # recorders. The platform's own pages count whenever DRAM units exist.
    from remix import arena
    reservations = [(m.name, m.arena.where, m.arena.pages)
                    for m in selected if getattr(m, "arena", None) is not None]
    if any(u.dram for m in selected for u in getattr(m, "linked", ())):
        reservations.append(("octabam platform", "bottom", arena.PLATFORM_PAGES))
    if reservations:
        try:
            arena.layout(reservations)
        except SystemExit as e:
            problems.append(str(e))

    for m in runtimes:
        skip = set(getattr(getattr(m, "arena", None), "recipe_writes", ()))
        skip |= {w for k, w in overridden_writes if k == m.key}
        for start, length, label in runtime_write_spans(m):
            if label in skip:
                continue                 # computed by the build (arena geometry), or bridged
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
    # Per CORE: two owners on DIFFERENT payloads never meet (BusVerb's tank
    # on A, BusDelay's LineR on B under SPEC). A module without a DspSection
    # or with no payload set counts as on both.
    buf = [m for m in selected
           if getattr(m, "claims", None) is not None
           and m.claims.owns_fx2_buffers]

    def _pay(m):
        p = getattr(getattr(m, "dsp", None), "payloads", None)
        return frozenset(p) if p else frozenset({"A", "B"})
    for i, a in enumerate(buf):
        for b in buf[i + 1:]:
            if not (_pay(a) & _pay(b)):
                continue
            clash("FX2 instance buffers", a.name, b.name,
                  "Y:0x4000-0xBFFF -- that region is per CORE, so only one "
                  "of them can be hosted on a given core; each works alone")

    # ---- stock effects that allocate an instance buffer -------------------
    # The allocator's bases are per TRACK SLOT, and this is MEASURED -- read
    # from X:0x255 in BOTH payloads of the pristine image (the
    # words are little-endian, which only shows above 0x10000, and reading
    # them big-endian gives a plausible 0x00003 instead of 0x30000):
    #
    #   core 0 FX2:  0x4000  0x8000  0x30000  0x34000
    #   core 1 FX2:  0x4000  0x8000  0x38000  0x3c000
    #
    # ⚠️ AND THE SLOTS ARE ONE PER TRACK, not a pool: each track allocates
    # FX1 then FX2, so track k's FX2 effect always gets entry 1+2k
    # (docs/firmware/DSP.md, "the allocator's instance model"). Nothing is first-come.
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

    # ---- the stock curve bank, X:0x4840 (4,096 words) ----------------------
    # Since the build parks the modules' P tables (a
    # DspSection.ptable, the reverb's LFOTAB) in this stock data record
    # instead of the donor region, whenever no stock effect that reads it
    # survives in the image (stock.curve_bank_readers; the build keeps the
    # tables in P otherwise, and says so). That makes the record a resource
    # with claimants, all DERIVED:
    #   * a module with a table (ptable, or a `$facade` literal in its source);
    #   * a module that ADDRESSES the record itself -- an X-space literal in
    #     its source inside the range: `x:>$`, `x:(rN+$`, or an immediate
    #     loaded into an address register. (An immediate into an
    #     accumulator is not one: the reverb's `#>$5000,a` is a Y line base.)
    # Tables are packed by the build and cannot overlap each other; a table
    # beside a module that addresses the record is a collision, because the
    # build would write the table under that module's reference. A kept
    # stock reader beside a table is NOT refused here: the build falls back
    # to P placement for it.
    tables, hard = curve_bank_claims(selected)
    for h in hard:
        for t in tables:
            clash("X:0x4840 curve bank", t, h,
                  "the stock curve bank X:0x4840 -- the build parks the "
                  "first's table there and the second addresses it directly")

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
