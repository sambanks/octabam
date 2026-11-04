#!/usr/bin/env python3
"""Run the gates the selected remix's modules declare (schema.Gate).

    python3 tools/verify/module_gates.py <remix> --stage isolated|image [--remix-only] [--list]
    python3 tools/verify/module_gates.py --shared <remix> [<remix> ...] [--modules A,B] [--list]

`make verify-remix` runs the isolated stage before it restores the
selected image (those gates build their own scratch images, or none) and
the image stage after `make bus` and the shared set gates. A gate declared
by two modules of the selection (the bus's two-core gate) runs once.

A gate with `remix_arg=False` does not depend on the remix: it builds its
own scratch image or checks an author's oracle. `--shared a b c` runs
those once for the union of the modules across the named remixes
(`make verify-shared`, once per `make reach RUN=1`); `--remix-only` runs
the rest for one remix (`make verify-remix`). Without either, a stage runs
both kinds for one remix (`make check` on its own).
A gate with `once=True` takes a remix name but checks the module's own
code, the same in every carrier: `--shared` runs it once, on the named
remix with the fewest modules that carries the module (the smallest image
that proves it); `--remix-only` leaves it out. A single remix without
either flag runs it on that remix.
The runner exports REMIX and BUILD; a gate with `remix_arg` gets the remix
name as argv[1]; one with `venv` runs under .venv/bin/python3 when that
exists (the port's python), else python3 -- the Makefile's $(PY).

A script that does not exist is a FAIL, not a skip: the manifest named a
gate the tree does not carry. A gate's own [SKIP] line stays its own.
"""
import argparse
import os
import pathlib
import re
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import gate_cache  # noqa: E402
import gate_ledger  # noqa: E402
import card_retention  # noqa: E402
from remix import registry  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]


def _globals(m):
    """Names a module's linked units export (`.global` / `.globl`)."""
    import re
    out = set()
    for u in getattr(m, "linked", ()):
        try:
            text = (ROOT / u.source).read_text(errors="replace")
        except OSError:
            continue
        for names in re.findall(r"^\s*\.glob(?:a)?l\s+([^|;#\n]+)", text, re.M):
            out |= {n.strip() for n in names.split(",") if re.fullmatch(r"[A-Za-z_]\w*", n.strip())}
    return out


def coupled(a, b):
    """Why module `a`'s code can change what module `b` does, or None: a
    requires, conflicts or overrides entry naming the other, a formatter
    one registers in the other's descriptor, both on the bus, a fixed write
    span both claim (caves, hooks, detours, symbol and table refs, pokes),
    or a DRAM unit of one whose declared defsym the other defines."""
    for x, y in ((a, b), (b, a)):
        if y.key in getattr(x, "requires", ()):
            return f"{x.key} requires {y.key}"
        if y.key in {k for k, _why in getattr(x, "conflicts", ())}:
            return f"{x.key} conflicts with {y.key}"
        if y.key in {o.module for o in getattr(x, "overrides", ())}:
            return f"{x.key} overrides {y.key}"
        regs = {u.registers_formatter.module for u in (*getattr(x, "linked", ()), *getattr(x, "cf_patches", ()))
                if getattr(u, "registers_formatter", None) is not None}
        if y.key in regs:
            return f"{x.key} registers a formatter in {y.key}'s descriptor"
    from remix.schema import on_the_bus
    if on_the_bus(a) and on_the_bus(b):
        return f"{a.key} and {b.key} share the bus"
    spans_a = [(s, s + n) for _k, s, n, _l in a.write_spans()]
    for _k, s, n, label in b.write_spans():
        if any(s < hi and lo < s + n for lo, hi in spans_a):
            return f"{a.key} and {b.key} write 0x{s:08x} ({label})"
    for x, y in ((a, b), (b, a)):
        names = {n for u in getattr(x, "linked", ()) for n, _v in getattr(u, "defsyms", ())}
        hit = names & _globals(y)
        if hit:
            return f"{x.key} links {sorted(hit)[0]} from {y.key}"
    return None


def reached(keys, modules):
    """The selected modules a change to `keys` reaches: those keys and every
    module coupled() to one of them, transitively. A per-remix gate of any
    other module tests code the change did not touch."""
    by_key = {m.key: m for m in modules}
    out = {k for k in keys if k in by_key}
    todo = list(out)
    while todo:
        a = by_key[todo.pop()]
        for m in modules:
            if m.key not in out and coupled(a, m):
                out.add(m.key)
                todo.append(m.key)
    return out


def collect(modules, stage, remix_arg=None, once=None):
    """The gates of `modules` for one stage, in selection order, each script
    once. `remix_arg` True/False keeps only the gates that take / do not
    take the remix; `once` True/False keeps only the once-per-run / the
    per-remix gates; None keeps both."""
    seen, out = set(), []
    for m in modules:
        for g in getattr(m, "gates", ()):
            if g.stage != stage or g.script in seen:
                continue
            if remix_arg is not None and g.remix_arg != remix_arg:
                continue
            if once is not None and getattr(g, "once", False) != once:
                continue
            seen.add(g.script)
            out.append((m.key, g))
    return out


def union(remixes):
    """The modules of several remixes, each once, in first-seen order."""
    seen, out = set(), []
    for r in remixes:
        for m in registry.selected(r):
            if m.key not in seen:
                seen.add(m.key)
                out.append(m)
    return out


def carrier(module_key, remixes, selected=None):
    """The remix among `remixes` carrying `module_key` with the fewest
    modules (the first on a tie): where a once-per-run gate runs."""
    selected = selected or registry.selected
    carrying = []
    for i, r in enumerate(remixes):
        sel = selected(r)
        if any(m.key == module_key for m in sel):
            carrying.append((len(sel), i, r))
    return min(carrying)[2]


def python_for(gate, root=ROOT):
    venv = root / ".venv/bin/python3"
    if gate.venv and os.access(venv, os.X_OK):
        return str(venv)
    return sys.executable


def command(gate, remix_name, root=ROOT):
    cmd = [python_for(gate, root), str(root / gate.script)]
    if gate.remix_arg:
        cmd.append(remix_name)
    return cmd


_DEPS = None


def shared_cache_key(modules, key, g, cmd, env):
    """The gate_cache key of a remix-independent gate (gate_cache.shared_key):
    its module's directory and those of every module it reaches. None when
    the cache is off."""
    global _DEPS
    if not gate_cache.enabled():
        return None
    if _DEPS is None:
        import reach  # noqa: E402
        _DEPS = reach.scan_deps(ROOT)
    by_key = {m.key: m for m in modules}
    dirs = [f"modules/{by_key[k].name}" for k in sorted(reached({key}, modules)) if k in by_key]
    return gate_cache.shared_key(ROOT, g.script, [pathlib.Path(cmd[0]).name, g.script, *cmd[2:]],
                                 {g.script}, dirs, deps=_DEPS, env=env)


def port_built(root=ROOT):
    """The ColdFire port's binary is there; without it a port gate SKIPs."""
    return (root / "out/emu/ot_emu").exists()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("remix", nargs="*", default=[])
    ap.add_argument("--stage", choices=("isolated", "image"), default="isolated")
    ap.add_argument("--shared", action="store_true",
                    help="the remix-independent isolated gates (remix_arg=False), once across every remix named")
    ap.add_argument("--remix-only", action="store_true",
                    help="only the gates that take the remix (remix_arg=True)")
    ap.add_argument("--list", action="store_true", help="print the commands, run nothing")
    ap.add_argument("--modules", default="",
                    help="only the gates of these comma-separated module keys: with --shared those "
                         "modules' own (make check-shared MODULES=...); per remix, those of every module "
                         "they reach (reached(): make check-remix MODULES=...)")
    ap.add_argument("--only-script", default="",
                    help="only the gates whose script is one of these comma-separated paths (check_shards runs the "
                         "image-stage gates one per job; CI gives a slow shared gate a runner of its own)")
    ap.add_argument("--skip-script", default="",
                    help="every gate but these comma-separated paths (the shared unit the slow gates were cut out of)")
    a = ap.parse_args(argv)
    if a.list:
        return _run(a, dict(os.environ))
    try:
        with card_retention.Gate(ROOT, "module gates", snapshot_cards=False) as owner:
            return _run(a, owner.env)
    except card_retention.RetentionError as exc:
        print(f"[FAIL] card retention: {exc}", flush=True)
        return 2


def _run(a, env):
    env.setdefault("BUILD", "0")
    env.setdefault("PYTHONUNBUFFERED", "1")      # each gate's lines as it prints them, through the tee below
    if a.shared:
        names = a.remix or ([os.environ["REMIX"]] if os.environ.get("REMIX") else [])
        remixes = [registry.remix(n) for n in names] or [registry.remix(None)]
        modules = union(remixes)
        gates = [(k, g, remixes[0].name) for k, g in collect(modules, "isolated", remix_arg=False)]
        gates += [(k, g, carrier(k, remixes).name) for k, g in collect(modules, "isolated", once=True)]
        label = f"shared isolated, {', '.join(r.name for r in remixes)}"
        if a.modules:
            keys = {k for k in a.modules.split(",") if k}
            # by script: a gate two modules declare is listed under the first
            mine = {g.script for m in modules if m.key in keys for g in getattr(m, "gates", ())}
            gates = [x for x in gates if x[1].script in mine]
            label += f", modules {', '.join(sorted(keys))}"
    else:
        remix = registry.remix(a.remix[0] if a.remix else os.environ.get("REMIX"))
        selected = registry.selected(remix)
        gates = [(k, g, remix.name) for k, g in
                 collect(selected, a.stage, True if a.remix_only else None,
                         False if a.remix_only else None)]
        label = a.stage + (" remix-only" if a.remix_only else "")
        if a.modules:
            # the module gates of what a change reaches (reached()); the
            # rest of the per-remix half (the floor) is the Makefile's
            keys = reached({k for k in a.modules.split(",") if k}, selected)
            mine = {g.script for m in selected if m.key in keys for g in getattr(m, "gates", ())}
            gates = [x for x in gates if x[1].script in mine]
            label += f", reached from {a.modules} ({', '.join(sorted(keys)) or 'none here'})"
        env["REMIX"] = remix.name
    if a.only_script:
        only = {x for x in a.only_script.split(",") if x}
        gates = [x for x in gates if x[1].script in only]
        label += f", {a.only_script}"
    if a.skip_script:
        skip = {x for x in a.skip_script.split(",") if x}
        gates = [x for x in gates if x[1].script not in skip]
        label += f", without {a.skip_script}"
    if not gates:
        print(f"module gates ({label}): none declared")
        return 0
    if not a.list and not port_built():
        # A gate that needs the port SKIPs without it, and a run of SKIPs
        # is green: a fresh worktree's reach passed without verify_kits
        # (11 Oct 2026). The port is a requirement here, not an option.
        print(f"  [FAIL] module gates ({label}): the ColdFire port is not built (make emu-cf); "
              f"its gates would SKIP and the run would pass without them")
        return 1
    fails = []
    union_modules = modules if a.shared else None
    for key, g, remix_name in gates:
        cmd = command(g, remix_name)
        if a.shared and g.remix_arg:
            env["REMIX"] = remix_name
        if a.list:
            print(f"{key:16} {' '.join(pathlib.Path(c).name if i == 0 else c for i, c in enumerate(cmd))}")
            continue
        print(f"\n== {key}: {g.script}{' ' + remix_name if g.remix_arg else ''}", flush=True)
        if not (ROOT / g.script).is_file():
            print(f"  [FAIL] {g.script}: no such file (the manifest names a gate the tree does not carry)")
            fails.append(g.script)
            continue
        ck = shared_cache_key(union_modules, key, g, cmd, env) if union_modules is not None and not g.remix_arg else None
        hit = gate_cache.lookup(ck)
        if hit:
            print(f"  gate_cache: a pass at {hit.get('head', '?')} ({hit.get('when', '?')}, {hit.get('seconds', 0):.0f} s), "
                  f"same inputs: not run (key {ck[:12]})")
            for skip in hit.get("skips", []):
                print(skip)
            continue
        t0 = time.monotonic()
        try:
            with card_retention.Gate(ROOT, g.script, env) as cards:
                out = []
                with subprocess.Popen(cmd, cwd=ROOT, env=cards.env, pass_fds=cards.pass_fds,
                                      stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                      text=True, errors="replace") as p:
                    for line in p.stdout:
                        sys.stdout.write(line)
                        sys.stdout.flush()
                        out.append(line)
                    rc = p.wait()
                if rc:
                    print(f"  [FAIL] {g.script} exit {rc}")
                    fails.append(g.script)
                    gate_ledger.record(g.script, remix_name, gate_ledger.first_fail("".join(out)))
                cards.finish(rc == 0 and not any("[FAIL]" in line or "[SKIP]" in line or
                                                 line.lstrip().startswith("SKIP:") for line in out))
                secs = time.monotonic() - t0
                print(f"  gate: {secs:.0f} s  rc={rc}  {g.script}", flush=True)
                if rc == 0 and ck:
                    gate_cache.store(ck, dict(job=g.script, seconds=secs, skips=[
                        l.rstrip() for l in out if re.match(r"\s*(?:\[SKIP\]|SKIP:)", l)]))
        except card_retention.RetentionError as exc:
            print(f"  [FAIL] card retention: {exc}", flush=True)
            fails.append(g.script)
            gate_ledger.record(g.script, remix_name, str(exc))

    if a.list:
        return 0
    print(f"\nmodule gates ({label}): {len(gates)} run, {len(fails)} failed"
          + (": " + ", ".join(fails) if fails else ""))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
