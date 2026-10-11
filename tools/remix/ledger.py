"""Cross-module resource collisions, caught before a byte is written.

The build refuses to start when two selected modules claim the same
resource, and says which two.

Checked, and how it knows:

  DSP priority       declared (DspSection.priority). Two sections on one
                     priority and one payload are packed in the remix's
                     module order; the number must say it.
  fx2 ids            declared. Two modules on one id would overwrite each
                     other's descriptor and dispatch.
  declared conflicts declared (Module.conflicts). Two modules that touch no
                     common byte but must not share an image.
  fixed-address      declared. Every byte span a module rewrites at a fixed
  writes             address -- pinned caves, cave hooks and detours (their
                     whole written span: hook_stock, pad_to), table refs,
                     symbol refs, plain pokes and emit() pokes -- against
                     every other module's. Two
                     hooks on one instruction: the second jsr overwrites the
                     first and the first never runs; two pokes on one word:
                     the build's second expect assert fails.
  kept bytes         declared (Module.keeps). Stock bytes a module relies on
                     and does not write, against every other module's
                     writes; two keepers must expect the same stock.
  grown tables       declared (TableGrow). Two modules relocating one stock
                     array would each carry a copy, and the refs disagree.
  overrides          a bridge's claim stands in for the overridden module's
                     at that site; a bridge naming a module the remix does
                     not carry is refused.
  DSP hook sites     declared (DspSection.hooks), per payload (DspHook.site
                     may differ per payload). Two hooks whose two-word jsr
                     spans share a stock P word on one payload: the second
                     jsr overwrites the first.
  on-chip SRAM       declared (Claims.sram). A DMA engine's descriptors and
                     buffers there; two modules on one window corrupt each
                     other's transfers.
  core-private Y     derived by scanning the module's source for `y:>$09xx`.
                     Low Y is per core, not per instance, so every effect
                     sharing a core shares these words.
  stock buffers      declared (Claims.stock_instance_buffer). A stock effect
                     that takes an instance buffer from the host's bump
                     allocator gets a per-track base -- the addresses
                     BusVerb and BusDelay hardcode -- and the chooser
                     is one list for all eight tracks, so the build cannot
                     know which track it lands on. Refused beside any module
                     with fixed Y buffers.
  DSP data ranges    declared (Claims.dsp_ranges), per payload below the
                     shared window and across both cores inside it (X, Y
                     and P alias there), against every other module's
                     ranges, FX2 buffer region and core-private Y words,
                     the bus scratch Y:0x36000-0x361FF (bus participants
                     share it by protocol), stock's per-frame staging
                     0x30000-0x30047 and stock's core 1 -> core 0 mailbox
                     0x37F00-0x37F0F. verify_set measures the shared
                     window's writes under the port and holds them to these
                     (tools/remix/dsp_ranges.py).
  arena reserve      the platform's pages must leave the unit sample memory.

Derived beats declared where possible: a scan cannot go stale. Its limit is
that it sees only what the code references, so a word a module means to
reserve but does not yet touch is declared (Claims.reserved_private_y).

Not checked: the P donor region, where placement refuses to overrun,
exactly; writes the build itself makes (menu clones, label caves, arena
literals), which the build's final Keep assert covers.
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
        declared = any(r.space == "x" and not r.half_relative and _overlap(r.start, r.length, lo, hi - lo)
                       for r in (m.claims.dsp_ranges if m.claims is not None else ()))
        if declared or any(lo <= int(next(h for h in g if h), 16) < hi
                           for g in _X_ADDR.findall(code)):
            hard.append(m.name)
    return tables, hard


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

    # ---- DSP priority (DspSection.priority) -------------------------------
    # The build packs each payload's sections in priority order with a stable
    # sort, so a tie falls back to the remix's module order.
    dsp_mods = [m for m in selected if getattr(m, "dsp", None) is not None]
    for i, a in enumerate(dsp_mods):
        for b in dsp_mods[i + 1:]:
            if a.dsp.priority == b.dsp.priority and a.dsp.payloads & b.dsp.payloads:
                clash("DSP priority", a.name, b.name,
                      f"priority {a.dsp.priority} on payload "
                      f"{'/'.join(sorted(a.dsp.payloads & b.dsp.payloads))}")

    # ---- bridges: what they stand in for must be there ---------------------
    keys = {m.key for m in selected}
    for m in selected:
        for need in getattr(m, "requires", ()):
            if need not in keys:
                problems.append(f"{m.name} requires {need} in the remix")

    # ---- declared conflicts (Module.conflicts) ------------------------------
    by_key = {m.key: m for m in selected}
    seen_pairs: set[frozenset[str]] = set()
    for m in selected:
        for other, why in getattr(m, "conflicts", ()):
            pair = frozenset((m.key, other))
            if other in by_key and pair not in seen_pairs:
                seen_pairs.add(pair)
                problems.append(f"declared conflict: {m.name} cannot share an image with "
                                f"{by_key[other].name} -- {why}")

    # ---- Part-window bytes (Claims.part_window) -----------------------------
    regions: list[tuple[int, int, str, str]] = []
    for m in selected:
        for off, length, what in (m.claims.part_window if m.claims else ()):
            for o2, l2, owner, w2 in regions:
                if _overlap(o2, l2, off, length):
                    clash("Part window", f"{owner}'s {w2}", f"{m.name}'s {what}",
                          f"bytes +0x{max(o2, off):05x}.. of every Part")
            regions.append((off, length, m.name, what))

    # ---- DSP hook sites (DspSection.hooks), per payload ---------------------
    # A hook writes two words (jsr >label), so two hooks clash when their
    # word pairs share a word.
    dsp_hooks: dict[tuple[str, int], str] = {}
    for m in selected:
        for h in (m.dsp.hooks if m.dsp is not None else ()):
            for pl in sorted(m.dsp.payloads):
                site = h.site_on(pl)
                hit = next((w for w in (site, site + 1) if (pl, w) in dsp_hooks), None)
                if hit is not None:
                    clash("DSP hook site", dsp_hooks[(pl, hit)], m.name,
                          f"P:0x{site:05x} on payload {pl} -- the second jsr "
                          f"overwrites the first, so the first section never runs")
                for w in (site, site + 1):
                    dsp_hooks[(pl, w)] = m.name
    # A pinned section (schema.DspSection.pins) owns words in the dead vector
    # runs it was placed in. Two modules pinned at one address are refused
    # here by name; an OVERLAP that is not an exact match is caught in
    # build_bus, which refuses to pin over anything that is not still the
    # stock self-jump it was audited as.
    for m in selected:
        for _pin in (m.dsp.pins if m.dsp is not None else ()):
            for pl in sorted(m.dsp.payloads):
                if (pl, _pin) in dsp_hooks:
                    clash("DSP pin", dsp_hooks[(pl, _pin)], m.name,
                          f"P:0x{_pin:05x} on payload {pl} -- both want the words there")
                dsp_hooks[(pl, _pin)] = m.name

    # ---- on-chip SRAM windows (Claims.sram) --------------------------------
    sram: list[tuple[int, int, str, str]] = []
    for m in selected:
        for base, length, what in (m.claims.sram if m.claims else ()):
            for b2, l2, owner, w2 in sram:
                if _overlap(b2, l2, base, length):
                    clash("on-chip SRAM", f"{owner}'s {w2}", f"{m.name}'s {what}",
                          f"0x{max(b2, base):08x}..")
            sram.append((base, length, m.name, what))

    # ---- ColdFire caves and hook sites ------------------------------------
    caves: list[tuple[int, int, str, str]] = []
    hooks: dict[int, str] = {}
    for m in selected:
        for c in m.cf_patches:
            if c.cave_addr is not None:  # pinned: check for overlap against
                for start, length, owner, label in caves:  # every pinned cave
                    if _overlap(start, length, c.cave_addr, c.claim_len):
                        clash("ColdFire cave", f"{owner}'s {label}",
                              f"{m.name}'s {c.label}",
                              f"0x{max(start, c.cave_addr):08x}")
                caves.append((c.cave_addr, c.claim_len, m.name, c.label))
            # A hook site is a fixed address whether or not the CAVE that
            # receives the jsr floats. Until this fix a `continue` for a
            # floating cave returned before this check too, so its hook_addr
            # was never registered -- and every hook-based CavePatch floats
            # (27 Sep 2026: flex-seekbind, flex-seekbind-ctr, recorder-hold,
            # recorder-spacing, rlen-plen, tempo-sync), so NO hook site was
            # ever checked against anything. Found on branch crosscheck (12
            # Sep 2026) demonstrating STEM REC beside CF PROBE, a module of
            # that branch: both hook the frame site 0x40004b12 (a Detour and
            # a CavePatch hook naming the same address) and composed silently
            # -- the exact "two hooks, one site" hazard this dict catches.
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
    for m in selected:
        for o in getattr(m, "overrides", ()):
            if o.module not in keys:
                clash("override", m.name, f"(no {o.module})",
                      f"0x{o.site:08x} -- it bridges {o.module}, which this remix "
                      f"does not carry")
            overridden_detours.add((o.site, o.module))

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
    # address purely to learn its sites.
    PROBE_ADDR = 0x400D7000
    emit_spans: list[tuple[str, int, int, str, str]] = []   # (kind, start, length, owner, label)
    for m in selected:
        for c in m.cf_patches:
            if c.emit is None:
                continue
            _, cpokes = c.emit(c.cave_addr if c.cave_addr is not None else PROBE_ADDR)
            for pa, expect, _write in cpokes:
                emit_spans.append(("emit poke", pa, len(expect), m.name, c.label))
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

    # ---- the audio page arena ---------------------------------------------
    # The one thing to refuse here is a reservation that leaves the unit
    # too little for samples and recorders. The platform's pages count
    # whenever DRAM units exist.
    from remix import arena
    reservations = []
    if any(u.dram for m in selected for u in getattr(m, "linked", ())):
        reservations.append(("octabam platform", "bottom", arena.PLATFORM_PAGES))
    if reservations:
        try:
            arena.layout(reservations)
        except SystemExit as e:
            problems.append(str(e))

    # ---- every fixed-address span against every other module's -------------
    # The passes above compare emit pokes with everything,
    # caves with caves and hooks by their first address. This one compares
    # the rest by the bytes each claim actually writes: plain pokes, table
    # and symbol refs against each other and against caves and hooks, and
    # hooks and detours by their whole span (hook_stock, pad_to). A pair the
    # passes above already reported is not reported twice.
    spans: list[tuple[str, int, int, str, str]] = []          # (kind, start, length, owner, label)
    for m in selected:
        for kind, start, length, label in m.write_spans():
            if kind == "detour" and (start, m.key) in overridden_detours:
                continue
            spans.append((kind, start, length, m.name, label))
        for u in getattr(m, "linked", ()):
            if u.cave_addr is not None:
                spans.append(("cave", u.cave_addr, 6, m.name, f"linked unit {u.label}"))
    spans += emit_spans

    _HOOKS = ("hook", "detour")
    _POKES = ("poke", "table ref", "symbol ref", "emit poke")

    def _reported(a, b) -> bool:
        """Did a pass above already report this overlapping pair?"""
        ka, kb = a[0], b[0]
        if ka == "cave" and kb == "cave":
            return True
        if ka in _HOOKS and kb in _HOOKS and a[1] == b[1]:
            return True
        for x, y in ((a, b), (b, a)):
            if x[0] == "emit poke":
                if y[0] == "cave" or y[0] in _POKES:
                    return True
                if y[0] in _HOOKS:
                    return _overlap(y[1], 6, x[1], x[2])
        return False

    for i, a in enumerate(spans):
        for b in spans[i + 1:]:
            if a[3] == b[3] or not _overlap(a[1], a[2], b[1], b[2]) or _reported(a, b):
                continue
            at = f"0x{max(a[1], b[1]):08x}"
            if "cave" in (a[0], b[0]):
                clash("ColdFire cave", f"{a[3]}'s {a[0]} {a[4]}", f"{b[3]}'s {b[0]} {b[4]}", at)
            elif a[0] in _HOOKS or b[0] in _HOOKS:
                clash("hook site", f"{a[3]} ({a[0]} {a[4]})", f"{b[3]} ({b[0]} {b[4]})",
                      f"{at} -- both rewrite the same instruction")
            else:
                clash("poke site", f"{a[3]} ({a[0]} {a[4]})", f"{b[3]} ({b[0]} {b[4]})",
                      f"{at} -- both rewrite the same bytes")

    # ---- kept bytes (Module.keeps) -----------------------------------------
    kept = [(k.addr, k.expect, m.name, k.note or f"kept bytes at 0x{k.addr:08x}")
            for m in selected for k in getattr(m, "keeps", ())]
    for i, (ka, kexp, kowner, knote) in enumerate(kept):
        for oa, oexp, oowner, onote in kept[i + 1:]:
            if oowner == kowner or not _overlap(ka, len(kexp), oa, len(oexp)):
                continue
            lo, hi = max(ka, oa), min(ka + len(kexp), oa + len(oexp))
            if kexp[lo - ka:hi - ka] != oexp[lo - oa:hi - oa]:
                clash("kept bytes", f"{kowner}'s {knote}", f"{oowner}'s {onote}",
                      f"0x{lo:08x} -- they expect different stock bytes there, "
                      f"so one of them is wrong about 1.40C")
        for kind, start, length, owner, label in spans:
            if owner != kowner and _overlap(ka, len(kexp), start, length):
                clash("kept bytes", f"{kowner}'s {knote}", f"{owner} ({kind} {label})",
                      f"0x{max(ka, start):08x} -- {kowner} relies on these bytes "
                      f"staying stock")

    # ---- grown tables (TableGrow) ------------------------------------------
    grown: list[tuple[int, int, str, str]] = []
    for m in selected:
        for t in getattr(m, "tables", ()):
            for start, length, owner, label in grown:
                if owner != m.name and _overlap(start, length, t.old, 4 * t.count):
                    clash("grown table", f"{owner}'s {label}", f"{m.name}'s {t.label}",
                          f"stock array 0x{max(start, t.old):08x} -- each would relocate "
                          f"its own copy and repoint different refs")
            grown.append((t.old, 4 * t.count, m.name, t.label))

    # ---- the per-core FX2 instance buffer region --------------------------
    # Y:0x4000-0xBFFF is TWO FX2 instance slots of 16,384 words, per core and
    # not per instance in any sense a module can rely on: BusVerb hardcodes
    # its tank there, and a second module with fixed buffers there writes
    # over it. Each works perfectly alone.
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

    # ---- DRAM regions (schema.DramRegion) ---------------------------------
    # A region is a linker symbol; two modules defining the same one would
    # both link against whichever --defsym came last, silently sharing it.
    dram_owner: dict[str, str] = {}
    for m in selected:
        for r in getattr(m, "dram_regions", ()):
            if r.symbol in dram_owner:
                clash("DRAM region", dram_owner[r.symbol], m.name,
                      f"the symbol {r.symbol}")
            dram_owner[r.symbol] = m.name

    # ---- DSP data ranges (Claims.dsp_ranges) -------------------------------
    # Each declared range against everything else that owns DSP data words:
    # other modules' declared ranges, FX2 buffer regions and core-private Y
    # words (on the payloads both run on), the bus scratch (when the remix
    # has a bus and the module is not part of it), stock's per-frame staging
    # and its mailbox. The derived claims are checked among themselves above.
    from remix import dsp_ranges
    owned = dsp_ranges.owners(selected)
    for i, a in enumerate(owned):
        if not a.declared:
            continue
        for j, b in enumerate(owned):
            if i == j or a.owner == b.owner or a.domain != b.domain:
                continue
            if b.declared and j < i:
                continue                 # reported from the other side
            if b.bus_shared and a.bus_member:
                continue                 # the bus scratch is shared by protocol
            if _overlap(a.start, a.end - a.start, b.start, b.end - b.start):
                where = "shared window" if a.domain == "shared" else f"payload {a.domain}"
                clash("DSP data", f"{a.owner}'s {a.what}", f"{b.owner}'s {b.what}",
                      f"{where} 0x{max(a.start, b.start):05x}.. -- both write these words")

    return problems
