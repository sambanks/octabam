#!/usr/bin/env python3
"""Print the module index and the available remixes; render the copies.

    python3 tools/remix/index.py            # the index, the matrix, the remixes
    python3 tools/remix/index.py --write    # README.md's module table,
                                            # remixes/README.md and
                                            # remixes/test/README.md (make docs)
    python3 tools/remix/index.py --check    # 1 if any copy is stale

The manifests are the authoritative list; the two Markdown tables are
copies, rendered here and held current by tools/verify/verify_docs.py.
"""

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401  (every tools/ dir on sys.path)

from remix import registry  # noqa: E402
from remix.schema import CATEGORY_TITLE, PROOF_TEXT, Category, Proof  # noqa: E402


from remix.rig import touches_coldfire  # noqa: E402


def matrix(mods):
    """The compatibility matrix: every pair of ColdFire-side modules through
    the ledger -- the same call the build makes, so a cell here IS what
    `make bus` would say. Printed rather than written down because a table
    in a README is a copy, and this one changes every time a module lands.
    """
    from remix import ledger
    cf = sorted((m for m in mods.values() if not m.is_stock and touches_coldfire(m)),
                key=lambda m: m.name)
    if len(cf) < 2:
        return
    # A BRIDGE (schema.Override) exists to let two other modules share a
    # site, and is refused unless both are in the remix. So a bridge's cell
    # is checked with its parties present, and a pair that a bridge joins is
    # marked ✓* -- refused alone, clean with the bridge.
    parties = {m.key: [mods[o.module] for o in (m.overrides or ())
                       if o.module in mods] for m in cf}
    # Each cell carries the pair's `requires` closure (and MEMORY, which the
    # registry appends to any remix with a DRAM unit): without it a pair whose
    # module needs STORE or EVENTS reports that need and hides the real clash.
    by_key = {m.key: m for m in mods.values()}

    def closure(ms):
        out = {m.key: m for m in ms}
        if "MEMORY" in by_key:
            out.setdefault("MEMORY", by_key["MEMORY"])
        todo = list(out.values())
        while todo:
            for need in getattr(todo.pop(), "requires", ()):
                if need in by_key and need not in out:
                    out[need] = by_key[need]
                    todo.append(by_key[need])
        return list(out.values())
    bridges = [m for m in cf if parties[m.key]]
    print("COMPATIBILITY  (the ledger, pairwise: which ColdFire-side modules "
          "can share an image)\n")
    short = [m.name[:9] for m in cf]
    w = max(len(s) for s in short)
    print("  " + " " * (w + 2) + " ".join(f"{s[:3]:>3}" for s in short))
    reasons, joined = {}, {}
    for a in cf:
        row = []
        for b in cf:
            if a is b:
                row.append("  ·")
                continue
            # A bridge's parties join one at a time, each only where the cell
            # stays clean: two parties of different bridges may exclude each
            # other (ANALOG BD and BLACKPYRAMIDS_303), and the cell asks whether
            # the pair shares an image, not whether every party does.
            base = [a, b]
            for p in parties[a.key] + parties[b.key]:
                if p not in base and not ledger.check(closure(base + [p])):
                    base.append(p)
            sel = {m.key: m for m in closure(base)}
            probs = ledger.check(list(sel.values()))
            key = tuple(sorted((a.name, b.name)))
            if probs:
                fix = next((br for br in bridges if br not in (a, b)
                            and not ledger.check(list({**sel, br.key: br}.values()))),
                           None)
                if fix is not None:
                    row.append(" ✓*")
                    joined.setdefault(key, fix.name)
                else:
                    row.append("  x")
                    reasons.setdefault(key, probs[0])
            else:
                row.append("  ✓")
        print(f"  {a.name[:9]:<{w + 2}}" + " ".join(row))
    print()
    for (a, b), why in sorted(reasons.items()):
        print(f"  x {a} + {b}: {why}")
    for (a, b), br in sorted(joined.items()):
        print(f"  ✓* {a} + {b}: with {br}")
    if reasons or joined:
        print()
    print("  (a x is refused at build time, by name; ✓* needs the named bridge; "
          "a bridge's own row is\n   checked with the modules it bridges present. "
          "Anything not listed here is a DSP effect,\n   which the ledger checks "
          "by FX2 id, buffer region and private Y instead)\n")


BEGIN, END = "<!-- modules:begin -->", "<!-- modules:end -->"
FAMILIES = (("rig", "The delay and reverb bus"), ("effects", "Effects"),
            ("mods", "Firmware mods on the stock effects"),
            ("reference", "Reference"), ("probes", "Probes"))


def proof_text(x) -> str:
    if x.proof is None:
        return "?"
    return PROOF_TEXT[x.proof] + (f": {x.proof_note}" if x.proof_note else "")


def by_category(mods):
    """Non-stock modules grouped in Category order, by name within a group."""
    out = {c: [] for c in Category if c is not Category.STOCK}
    for m in mods.values():
        if not m.is_stock:
            out[m.category or Category.REFERENCE].append(m)
    for c in out:
        out[c].sort(key=lambda m: m.name)
    return out


def module_table(mods) -> str:
    lines = [BEGIN, ""]
    for cat, ms in by_category(mods).items():
        if not ms:
            continue
        lines += [f"### {CATEGORY_TITLE[cat]}", "",
                  "| module | author | what it does | proof |", "|---|---|---|---|"]
        for m in ms:
            author = f"[{m.author}]({m.author_url})" if m.author_url else m.author
            doc = m.doc.replace("|", "\\|")
            d = f"modules/{m.name}"
            link = f"{d}/README.md" if (ROOT / d / "README.md").exists() else f"{d}/"
            lines.append(f"| [**{m.key}**]({link}) | {author} | {doc} | {proof_text(m)} |")
        lines.append("")
    lines.append(END)
    return "\n".join(lines)


REMIXES = ROOT / "remixes"


def _rows(rs, base):
    out = ["| remix | contains | proof |", "|---|---|---|"]
    for r in rs:
        doc = r.doc.replace("|", "\\|")
        link = registry.remix_dir(r.name).relative_to(base)
        out.append(f"| [`{r.name}`]({link}/README.md) | {doc} | {proof_text(r)} |")
    return out + [""]


def remix_index() -> str:
    """remixes/README.md: the remixes a user flashes."""
    lines = ["# Remixes", "",
             "A remix is a named selection of modules; `make image REMIX=<name> "
             "BUILD=<n>` builds it into a card-flashable image from your own "
             "OS 1.40C. Each remix is a directory here: `remix.py` is the "
             "selection, `README.md` says what is in it, where it has run and "
             "how to flash it. This index is rendered from the selections "
             "(`make docs`).", "",
             "- What to install first (the Xcode Command Line Tools, Homebrew, "
             "Python 3.10+, `cmake`, `uv`) and every step to a flashed unit: "
             "[BUILDING.md](../docs/guide/BUILDING.md).",
             "- Composing your own: [COMPOSING.md](../docs/guide/COMPOSING.md).",
             "- The remixes that carry one module for its gates: "
             "[test/](test/README.md).", ""]
    for fam, title in FAMILIES:
        rs = [r for r in _remixes(False) if (r.family or "reference") == fam]
        if rs:
            lines += [f"## {title}", ""] + _rows(rs, REMIXES)
    lines += ["Never share a built image: it contains Elektron's OS.", ""]
    return "\n".join(lines)


def test_index() -> str:
    """remixes/test/README.md: the remixes that carry a module for its gates."""
    lines = ["# Test remixes", "",
             "Each carries one module, or one combination, for that module's "
             "gates: `make check REMIX=<name>`. Rendered by `make docs`; the "
             "remixes a user flashes are [one level up](../README.md).", ""]
    return "\n".join(lines + _rows(_remixes(True), REMIXES / "test"))


def _remixes(test):
    return [r for r in (registry.remix(n) for n in registry.remix_names())
            if registry.is_test(r.name) == test]


def rendered() -> dict:
    """{path: text} of every copy as the manifests say it should read."""
    readme = ROOT / "README.md"
    cur = readme.read_text()
    a, b = cur.index(BEGIN), cur.index(END) + len(END)
    return {readme: cur[:a] + module_table(registry.modules()) + cur[b:],
            REMIXES / "README.md": remix_index(),
            REMIXES / "test" / "README.md": test_index()}


def stale() -> list:
    return [p for p, text in rendered().items() if p.read_text() != text]


def main():
    if "--write" in sys.argv:
        for p, text in rendered().items():
            p.write_text(text); print(f"wrote {p.relative_to(ROOT)}")
        return 0
    if "--check" in sys.argv:
        bad = stale()
        for p in bad:
            print(f"  [FAIL] {p.relative_to(ROOT)} is stale: make docs")
        return 1 if bad else 0
    mods = registry.modules()
    print("MODULES  (modules/<name>/manifest.py, by category)\n")
    for cat, ms in by_category(mods).items():
        if ms:
            print(f"  -- {CATEGORY_TITLE[cat]} --\n")
        for m in ms:
            _print_module(m)
    _print_stock()
    matrix(registry.defaulted())   # judged as a remix that sets no Apply.BUILD setting builds them
    _print_remixes()
    print("Build one with:  make bus REMIX=<name>")
    return 0


def _print_module(m):
    bits = []
    if m.menu is not None:
        bits.append(f"FX2 id 0x{m.menu.fx2_id:02x}")
        bits.append(f"{len(m.active_params)} knobs")
    if m.dsp is not None:
        bits.append(f"asm {m.dsp.asm}")
    if m.cf_patches:
        bits.append(f"{len(m.cf_patches)} ColdFire cave"
                    f"{'s' if len(m.cf_patches) > 1 else ''}")
    print(f"  {m.name:<12} {m.kind.value:<10} [{m.key}]  {m.author}  {proof_text(m)}")
    print(f"      {m.doc}")
    print(f"      {' | '.join(bits)}")
    if m.menu is not None:
        knobs = ", ".join(f"{n}@{i}" for n, i in sorted(
            m.knob_map().items(), key=lambda kv: kv[1]))
        print(f"      knobs: {knobs}")
    print()


def _print_stock():
    from remix import stock
    print("STOCK FX2 EFFECTS  (tools/remix/stock.py -- already in every image;\n"
          "list one in a remix to KEEP its chooser row, by key)\n")
    for m in stock.MODULES:
        buf = "  [instance buffer -- not beside BusVerb/BusDelay]" \
            if m.claims is not None and m.claims.stock_instance_buffer else ""
        print(f"  {m.key:<12} FX2 id 0x{m.menu.fx2_id:02x}  {m.doc}{buf}")
        if m.params:
            knobs = ", ".join(f"{n}@{i}" for n, i in sorted(
                m.knob_map().items(), key=lambda kv: kv[1]))
            print(f"      knobs: {knobs}")
    # ⚠️ NOT "every remix" any more: what a remix gives up is DERIVED from
    # its two choosers -- an effect on neither is one it does not want -- and
    # each remix's is printed with it below when it differs from these.
    print(f"\n  given up by most remixes (on neither chooser): "
          f"{', '.join(stock.CONSUMED)}\n")


def _print_remixes():
    from remix import stock
    print("REMIXES  (remixes/<name>/remix.py; remixes/test/<name>/remix.py carries one module for its gates)\n")
    for name in registry.remix_names():
        r = registry.remix(name)
        print(f"  {r.name:<12} {r.doc}")
        fam = "test" if registry.is_test(name) else (r.family or "reference")
        print(f"      {fam} | {proof_text(r)}")
        print(f"      modules: {', '.join(r.modules)}")
        if r.fx1:
            print(f"      also on the FX1 chooser: {', '.join(r.fx1)}")
        _hv = stock.region_of(stock.harvested(
            set(r.modules) | set(r.fx1 or [
                k for k in stock.p_spans("A")
                if registry.modules()[k].menu.fx2_id in stock.fx1_ids()])))
        if tuple(_hv) != stock.CONSUMED:
            print(f"      gives up (on neither chooser): "
                  f"{', '.join(_hv) or 'nothing'}")
        print(f"      unimplemented ids fall back to: {r.fallback}")
        print()


if __name__ == "__main__":
    sys.exit(main())
