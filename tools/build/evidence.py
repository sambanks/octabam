#!/usr/bin/env python3
"""Every module's and remix's proof level, and the modules whose sources changed after their proof.

    python3 tools/build/evidence.py [--json]            # the table: level, unit, who, image, date, ref
    python3 tools/build/evidence.py stale [--json]      # modules at Level.UNIT or above whose sources have a
                                                        # commit after Evidence.commit (or Evidence.date)
    make evidence

`stale` reports and exits 0: a source change after a unit run does not lower the level, it lists the module
for a rerun. A module's sources are its DspSection.asm, its Linked units and its cave sources.
"""
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from remix import registry  # noqa: E402
from remix.schema import Level, best  # noqa: E402


def sources(m):
    out = []
    if m.dsp is not None:
        out.append(m.dsp.asm)
    out += [u.source for u in m.linked]
    out += [c.source for c in m.cf_patches if c.source]
    return sorted({s for s in out if (ROOT / s).exists() and not s.startswith("out/")})


def commits_after(e, paths):
    """Commits touching `paths` after the evidence: [(sha, date, subject)]."""
    if not paths or not (e.commit or e.date):
        return None
    rng = [f"{e.commit}..HEAD"] if e.commit else [f"--since={e.date}T23:59:59"]
    r = subprocess.run(["git", "log", "--format=%h\t%as\t%s", *rng, "--", *paths], cwd=ROOT, capture_output=True, text=True)
    return [tuple(l.split("\t", 2)) for l in r.stdout.splitlines() if l]


def table():
    rows = []
    for m in sorted(registry.modules().values(), key=lambda m: m.key):
        e = best(m.evidence)
        rows.append({"key": m.key, "level": e.level.name if e else None, "unit": e.unit if e else "", "who": e.who if e else "",
                     "image": e.image if e else "", "date": e.date if e else "", "ref": e.ref if e else ""})
    return rows


def stale():
    out = []
    for m in sorted(registry.modules().values(), key=lambda m: m.key):
        e = best(m.evidence)
        if e is None or e.level.rank < Level.UNIT.rank:
            continue
        src = sources(m)
        c = commits_after(e, src)
        if c is None:
            if src:
                out.append({"key": m.key, "why": "no commit and no date on its evidence", "sources": src, "commits": []})
        elif c:
            out.append({"key": m.key, "why": f"{len(c)} commit(s) after {e.commit or e.date}", "sources": src,
                        "commits": [{"sha": s, "date": d, "subject": t} for s, d, t in c]})
    return out


def main(argv):
    js = "--json" in argv
    if argv and argv[0] == "stale":
        rows = stale()
        if js:
            print(json.dumps(rows, indent=1))
        else:
            for r in rows:
                print(f"{r['key']}: {r['why']}")
                for c in r["commits"][:5]:
                    print(f"    {c['sha']} {c['date']} {c['subject'][:90]}")
            print(f"evidence: {len(rows)} module(s) proven on a unit have sources changed since, or no date to compare")
        return 0
    rows = table()
    if js:
        print(json.dumps(rows, indent=1))
    else:
        for r in rows:
            print(f"{r['key']:28s} {r['level'] or '-':14s} {r['unit']:5s} {r['who']:14s} {r['image']:12s} {r['date']:10s} {r['ref']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
