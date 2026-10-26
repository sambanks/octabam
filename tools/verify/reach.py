#!/usr/bin/env python3
"""Which gates a change reaches, in two tiers.

QUICK (the default, 29 Sep 2026) is for working: a module change checks the
remixes carrying it that users flash (remixes/), or, when only test remixes
carry it, the smallest of those; the floor for tool and build changes is
the one cover remix carrying the most modules; a build change runs refhash
but not `make identity` (every remix built twice); no `make accept` (the
stress fixture and the pressure stages); a shard per gate slot no other
session holds (at least two); every command at
nice 10 on the performance cores, so the machine stays usable.
FULL (`make reach FULL=1`, `--full`) is everything below, at full speed, and
only ever a manual choice.

Which gates a change reaches: the diff against main, classified by what
depends on each changed file.

    python3 tools/verify/reach.py [--base origin/main] [--run] [--paths ...]
    make reach [BASE=origin/main] [RUN=1] [KEEP=1] [JOBS=n]

CONTRIBUTING's "every remix the change can reach" was worked out by hand:
a module's remixes from the selections, a build change's refhash, a
verifier's callers. This reads the changed paths (committed and not,
against the merge-base with `--base`) and prints the commands, one line
each, with the paths that put them there; `--run` runs them in order and
stops at the first failure (`--keep-going`: every one, then a table).
The default remix is `octabam` (DEFAULT_REMIX, the golden master, 27 Oct
2026): QUICK checks it, and only it, for every module it carries, and it is
the floor. A module it does not carry is checked on the remixes that do.
Otherwise (FULL, or no `octabam`) there is no default remix. The FLOOR --
what a change to the build, the
port, a shared tool or an unclassified path reaches -- is the COVER: the
fewest remixes that between them carry every module (greedy from the
registry, 9 of 27 on 28 Sep 2026), so every module's gates and every kind
of per-remix gate run at least once. `--all` makes it every remix. A
change to the BUILD adds `image_identity.py`: every remix built from the
base and from this tree, and `--run` then checks the ones whose image
moved (dry mode says so). Together with refhash (the flag matrix of one
layout) that replaces "every remix" for a build change; before 28 Sep
2026 every such change ran all 25-27 remixes' checks.

HOW A PATH IS PLACED (28 Sep 2026; before, by directory):

  modules/<name>/           the remixes carrying the module: the shared half
                            scoped to the module (MODULES=<key>), the
                            per-remix half and make accept for each
  remixes/<name>/remix.py   that remix (remixes/test/<name>/remix.py too)
  tools/, scripts/          by DEPENDENCY: the Python imports (`from remix
                            import`, `import send_probe`) and the
                            `tools/x/y.py` path strings in every tools/ file
                            are a graph; a changed file reaches the gates
                            that transitively depend on it --
                              the build (build_bus.py, cycle_count.py, dsp/)
                                -> refhash, identity (then the changed remixes'
                                   checks), the runner tests, check-shared once
                                   for the cover
                              a gate of the SHARED half (the verify-shared
                              recipe: selftest, slots, replaces, docs,
                              label_fmt, the knob census; a manifest gate
                              with remix_arg=False)
                                -> make check-shared once (for the cover) / its owners
                              a gate of the PER-REMIX half (the verify-remix
                              recipe: dirty-state, init-regs, dram-boot, labels,
                              mode-names, hidden, menu, set, usb)
                                -> make check-remix for the cover
                              a manifest gate with remix_arg=True
                                -> make check-remix for its owners' remixes
                                   (once=True: the shared half, scoped)
                              the acceptance machinery (acceptance.py,
                              module_gates.py, stress_project.py, pressure.py)
                                -> the runner tests, the cover, accept for the cover
                              a file no gate depends on (bcr2000.py, a render
                              tool a `make render*` target runs)
                                -> nothing, and the note says so
                            tools/emu/ (the port) is the cover's per-remix
                            half plus ci-emu and emu-cf; tools/harness/dsp_host,
                            tools/patches, setup.sh, vendor.sh are ci-dsp
                            plus the cover (identity cannot see a toolchain
                            change: both trees build with the same binary)
  Makefile                  by TARGET: the targets whose recipe or
                            prerequisites changed against the base --
                            the check graph (bus, cycles, verify*, check*)
                            reaches identity, the cover and make ci; the
                            runner's targets (accept, reach, check-remixes,
                            test-acceptance) the runner tests; the ci
                            targets make ci; any other target nothing; a
                            changed variable or define, identity + the cover
  docs/, *.md               verify_docs
  .github/                  make ci
  anything else             the cover, named unclassified

It refuses a tree that is not rebased onto the base (the base must be an
ancestor of HEAD): gates run before a rebase are not a result (PR #396).
CI plans with `--json` and runs each unit of its `matrix` with `--run --only
NAME` on a runner of its own (the `gates` jobs fetch the 1.40C into the runner
each run); for pushes to main and every pull request.

Two or more remixes to check are printed as one `make check-shared
REMIXES="..."` (once) and a `make check-remix REMIX=<r>` each; one remix
alone stays `make check`. `make accept` runs both halves itself (the shared
half once for every remix it is given), so with STRESS_SOURCE set a remix
that reaches accept has no separate check line and the accept remixes are
one `make accept REMIXES="..."`; without it the check lines stay and the
accept line is listed as blocked. `--run --jobs N` runs the check-remix
lines through `check_shards.py`, N worktrees at a time; a lone `make check`
becomes its shared half and one remix split by gate. Each command run in
this tree holds a machine gate slot (slots.py); check_shards takes one per
job and skips a job whose pass is cached (gate_cache.py, `--no-cache`).
`--run` starts the `check-shared` line and the `check_shards` line together: the
shards build in their own worktrees and the shared half in this one.
"""
import argparse
import ast
import concurrent.futures as cf
import contextlib
import hashlib
import shutil
import json
import os
import pathlib
import re
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/verify"))
import slots  # noqa: E402
import check_shards  # noqa: E402
import gate_ledger  # noqa: E402

# One command per gate; the order is the order they run in.
OVERLAP = ("test-acceptance", "refhash", "verify-bus", "check-shared")
BUILDS = ("refhash", "verify-bus", "check-shared")


def is_shards(item):
    return item[0] == "check-remix" and "check_shards.py" in item[1]


ORDER = ("verify_docs", "selftest", "test-acceptance", "ci-dsp", "ci-emu", "emu-cf", "emu-get", "refhash", "verify-bus", "identity", "check-shared", "check", "check-remix", "accept", "ci")

# The build: a change here is every remix, both halves, and refhash proves
# the artifacts identical. dsp/ holds the sources build_bus assembles.
BUILD_ROOTS = ("tools/build/build_bus.py", "tools/build/cycle_count.py")
# The acceptance runner and what it drives: the runner tests, then accept
# for every remix (which runs both halves of every check itself).
ACCEPTANCE = ("tools/verify/acceptance.py", "tools/verify/module_gates.py",
              "tools/harness/stress_project.py", "tools/harness/pressure.py")
CLASSIFIER = ("tools/verify/reach.py",)
# The bus's bit-identity gate, and the remix whose modules reach it.
BUS_GATE = "tools/verify/verify_bus.py"
BUS_REMIX = "bus"


# The golden master: QUICK checks this remix for every module it carries and
# takes it as the floor (the cover stands in when it does not exist).
DEFAULT_REMIX = "octabam"


def bus_modules():
    """The module keys of remix `bus` (the gate's subject)."""
    sys.path.insert(0, str(ROOT / "tools"))
    from remix import registry
    return set(registry.remix(BUS_REMIX).modules)
# QUICK runs every command at nice 10: the performance cores, below the
# desktop; the shards are the gate slots free at the start, so the run takes
# part of the machine, not all of it.
# (Background QoS, taskpolicy -b, moved it onto the efficiency cores and was
# several times slower: 28-29 Sep 2026.) FULL runs at nice 0.
BACKGROUND = "nice -n 10" if shutil.which("nice") else ""
# Makefile targets by what a change to them reaches.
MAKE_CHECK = {"bus", "cycles", "verify", "verify-shared", "verify-remix", "check", "check-shared", "check-remix",
              "need-remix", "os", "recon"}
MAKE_RUNNER = {"accept", "test-acceptance", "reach", "check-remixes"}
MAKE_CI = {"ci", "ci-dsp", "ci-emu", "emu-cf", "check-asm"}


def cmd_check(remix):
    return ("check", f"make check REMIX={remix}")


def cmd_check_remix(remix, modules=None):
    """A remix's per-remix half; with `modules` (a module change), its floor
    and the module gates of what those modules reach (12 Oct 2026)."""
    line = f"make check-remix REMIX={remix}"
    if modules:
        line += f' MODULES="{",".join(sorted(set(modules)))}"'
    return ("check-remix", line)


def shards_line(command):
    """A check_shards line's (remixes, modules or None); --only-jobs and
    --skip-jobs (a unit's share of one remix, entries()) are not read."""
    import shlex
    words = shlex.split(command.split("check_shards.py", 1)[1])
    remixes, modules, i = [], None, 0
    while i < len(words):
        if words[i] in ("--jobs", "--modules", "--only-jobs", "--skip-jobs"):
            if words[i] == "--modules":
                modules = words[i + 1].split(",")
            i += 2
            continue
        remixes.append(words[i]); i += 1
    return remixes, modules


def cmd_check_shared(remixes, modules=None):
    """The shared half once for `remixes`; with `modules`, only those
    modules' shared gates (MODULES: a module change, 11 Oct 2026)."""
    line = f'make check-shared REMIXES="{" ".join(sorted(remixes))}"'
    if modules:
        line += f' MODULES="{",".join(sorted(set(modules)))}"'
    return ("check-shared", line)


def shared_modules(command):
    """A check-shared line's MODULES, or None for the whole shared half."""
    return command.split('MODULES="')[1].split('"')[0].split(",") if 'MODULES="' in command else None


def cmd_accept(remix):
    return ("accept", f"make accept REMIX={remix} STRESS_SOURCE=${{STRESS_SOURCE}}")


def accept_remix(command):
    return command.split("REMIX=")[1].split()[0]


def shared_remixes(command):
    return command.split('REMIXES="')[1].split('"')[0].split()


CMD = {
    "verify_docs": ("verify_docs", "python3 tools/verify/verify_docs.py"),
    "selftest": ("selftest", "python3 tools/remix/selftest.py"),
    "test-acceptance": ("test-acceptance", "make test-acceptance"),
    "ci-dsp": ("ci-dsp", "make ci-dsp"),
    "ci-emu": ("ci-emu", "make ci-emu"),
    "emu-cf": ("emu-cf", "make emu-cf"),
    "emu-get": ("emu-get", "make emu-get"),
    "refhash": ("refhash", "scripts/refhash.sh check"),
    # Names the remixes whose IMAGE the change moved; --run then checks
    # those (dry mode says so). scripts/refhash.sh pins the build FLAGS of
    # one layout, this pins the 27 remixes: together they replace "every
    # remix" for a build change.
    "identity": ("identity", "python3 tools/verify/image_identity.py --base ${BASE}"),
    # The bus's audio bit-identity: the DEV hatch of remix `bus` built from
    # the merge-base and from this tree, every case rendered on both
    # (tools/verify/verify_bus.py). A change to the build, the DSP
    # toolchain, a module of `bus` or the gate itself reaches it.
    "verify-bus": ("verify-bus", "python3 tools/verify/verify_bus.py --base ${BASE}"),
    "ci": ("ci", "make ci"),
}

# ---- the dependency graph over tools/ ------------------------------------

IMPORT = re.compile(r"^\s*(?:from\s+([A-Za-z_][\w.]*)\s+import\s+([\w, ]+)|import\s+([A-Za-z_][\w.]*))", re.M)
PATHREF = re.compile(r"\b((?:tools|scripts|dsp)/[A-Za-z0-9_./-]+\.[A-Za-z0-9]+)\b")
# A path string is a dependency when the code RUNS or READS it: an argument
# of one of these calls (an argv list inside subprocess.run counts), or a
# `ROOT / "tools/x/y.py"`. A path in a comment, a docstring, a message or a
# build-report hint is prose (build_bus.py names render_reverb.py and
# verify_delay.py in hints, and every remix "depended" on both).
RUNS_OR_READS = {"run", "Popen", "check_output", "check_call", "call", "open", "Path", "PurePath",
                 "read_text", "read_bytes", "exists", "is_file", "glob", "rglob", "joinpath", "execv", "execvp"}


def path_refs(text):
    """The repo paths a Python source runs or reads (see RUNS_OR_READS)."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return set()
    parents = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    out = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
            continue
        refs = PATHREF.findall(node.value)
        if not refs:
            continue
        p = parents.get(node)
        while p is not None and not isinstance(p, ast.stmt):
            if isinstance(p, ast.BinOp) and isinstance(p.op, ast.Div):
                out.update(refs); break
            if isinstance(p, ast.Call):
                f = p.func
                name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
                if name in RUNS_OR_READS:
                    out.update(refs); break
            p = parents.get(p)
    return out


def resolve_import(module, names, exists):
    """The repo files an import statement names, by toolpath's rules: the
    `remix` package under tools/, every group directory by bare name."""
    out = set()
    parts = module.split(".")
    base = "tools/" + "/".join(parts)
    if exists(base + ".py"):
        out.add(base + ".py")
    if exists(base + "/__init__.py"):
        out.add(base + "/__init__.py")
    for n in names:                     # `from hw import ot_bank`: tools/hw has no __init__
        if exists(f"{base}/{n}.py"):
            out.add(f"{base}/{n}.py")
    if len(parts) == 1:
        for g in ("build", "harness", "emu", "hw", "verify"):
            if exists(f"tools/{g}/{module}.py"):
                out.add(f"tools/{g}/{module}.py")
    return out


def scan_deps(root=ROOT):
    """{file: set(files it imports or names by path)} over tools/**/*.py and
    scripts/*.sh; a submodule's files are not ours."""
    files = [p for p in root.glob("tools/**/*.py") if "upstream" not in p.parts]
    files += list(root.glob("scripts/*.sh"))
    rel = lambda p: p.relative_to(root).as_posix()
    known = {rel(p) for p in files}
    exists = lambda path: path in known or (root / path).is_file()
    deps = {}
    for p in files:
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        d = set()
        if p.suffix == ".py":
            for m in IMPORT.finditer(text):
                if m.group(1):
                    d |= resolve_import(m.group(1), [n.strip().split(" as ")[0] for n in m.group(2).split(",")], exists)
                else:
                    d |= resolve_import(m.group(3), [], exists)
        refs = path_refs(text) if p.suffix == ".py" else {
            r for line in text.splitlines() if not line.lstrip().startswith("#") for r in PATHREF.findall(line)}
        for ref in refs:
            if exists(ref):
                d.add(ref)
        d.discard(rel(p))
        deps[rel(p)] = d
    return deps


def makefile_targets(text):
    """{target: its prerequisites + recipe text}, {variable: its line},
    {define: its body} from a Makefile's text; comments, blanks and .PHONY
    lines are not a change."""
    targets, variables, defines = {}, {}, {}
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r"^define\s+(\S+)", line)
        if m:
            body = []
            i += 1
            while i < len(lines) and not lines[i].startswith("endef"):
                body.append(lines[i]); i += 1
            defines[m.group(1)] = "\n".join(body)
            i += 1
            continue
        m = re.match(r"^([A-Za-z_][\w-]*)\s*[?:+]?=(.*)$", line)
        if m:
            variables[m.group(1)] = line.strip()
            i += 1
            continue
        m = re.match(r"^([A-Za-z0-9_.-]+):(?!=)(.*)$", line)
        if m and not line.startswith((".PHONY", "\t")):
            recipe = [m.group(2).split("##")[0].strip()]
            i += 1
            while i < len(lines) and lines[i].startswith("\t"):
                recipe.append(lines[i].strip()); i += 1
            targets[m.group(1)] = "\n".join(recipe)
            continue
        i += 1
    return targets, variables, defines


def makefile_changes(base_text, head_text):
    """(changed targets, changed variables or defines) between two Makefiles."""
    bt, bv, bd = makefile_targets(base_text or "")
    ht, hv, hd = makefile_targets(head_text or "")
    targets = sorted(k for k in set(bt) | set(ht) if bt.get(k) != ht.get(k))
    other = sorted(k for k in set(bv) | set(hv) if bv.get(k) != hv.get(k))
    other += sorted(k for k in set(bd) | set(hd) if bd.get(k) != hd.get(k))
    return targets, other


def recipe_scripts(make_text, target):
    m = re.search(r"^%s:([^\n]*)\n((?:\t[^\n]*\n)*)" % re.escape(target), make_text, re.M)
    if not m:
        return set()
    scripts = set(re.findall(r"tools/\S+\.py", m.group(2)))
    # Card-retention wrappers delegate to the serial implementation recipe.
    if re.search(r"\$\(MAKE\)[^\n]*\b" + re.escape(target + "-impl") + r"(?:\s|$)", m.group(2)):
        scripts |= recipe_scripts(make_text, target + "-impl")
    # An implementation recipe cut into halves lists them as prerequisites
    # (verify-shared-impl: verify-shared-rest-impl verify-shared-modules-impl).
    if target.endswith("-impl"):
        for half in re.findall(r"\b%s-[\w-]+-impl\b" % re.escape(target[:-len("-impl")]), m.group(1)):
            scripts |= recipe_scripts(make_text, half)
    return scripts


def variant_gates(m):
    """Every gate the module declares, in every build variant: a variant
    (schema.Module.variant) can name gates the unbound module does not
    carry (USB's verify_usb_post and verify_usb_align, by output combo). Until
    12 Oct 2026 a change to such a gate reached nothing. Each Apply.BUILD
    Option takes every label and a Binary 0 and 1; any other kind keeps
    its default. A combination the variant refuses (the build refuses it
    too) runs in no remix and has no gates of its own."""
    import itertools
    from remix.schema import Apply, Binary, Option
    gates = list(getattr(m, "gates", ()))
    if getattr(m, "variant", None) is None:
        return gates
    axes = []
    for st in m.settings:
        if st.apply is not Apply.BUILD:
            continue
        if isinstance(st.kind, Option):
            axes.append([(st.name, label) for label in st.kind.labels])
        elif isinstance(st.kind, Binary):
            axes.append([(st.name, 0), (st.name, 1)])
        else:
            axes.append([(st.name, st.default)])
    for combo in itertools.product(*axes):
        try:
            bound = m.bind(dict(combo))
        except ValueError:
            continue
        for g in bound.gates:
            if g not in gates:
                gates.append(g)
    return gates


class Context:
    """What the classifier needs from the registry and the tree, so tests
    can fake it."""

    def __init__(self, module_key, remixes_of, gate_owners, remixes, exists=None, deps=None,
                 shared_scripts=(), remix_scripts=(), gate_shared=None, make_base=None, make_head=None,
                 all_remixes=False, read=None, read_base=None, quick=False, test_remixes=(),
                 test_carriers=None, include_tests=True, gate_once=None, gate_remixes=None):
        self.module_key = module_key        # module directory -> key
        self.remixes_of = remixes_of        # key -> sorted remix names carrying it
        self.gate_owners = gate_owners      # verifier path -> keys whose manifests name it
        self.remixes = remixes              # every remix
        # The floor, since nothing is the default remix: every remix with
        # --all, else the cover -- the fewest remixes that between them carry
        # every module, so every module's gates and every kind of per-remix
        # gate run at least once (28 Sep 2026; 9 of 27 that day).
        self.quick = quick
        self.test_remixes = set(test_remixes)
        self.include_tests = include_tests
        self.test_carriers = test_carriers or {}   # key -> test remixes carrying it (when they are left out)
        self.floor = list(remixes) if all_remixes else self.cover()
        if quick and not all_remixes and DEFAULT_REMIX in remixes:
            self.floor = [DEFAULT_REMIX]
        elif quick and not all_remixes and self.floor:
            # QUICK: the one cover remix carrying the most modules stands for
            # the cover (FULL=1 runs the cover)
            self.floor = [max(self.floor, key=lambda r: (self._modules_of().get(r, 0), r))]
        self.exists = exists or (lambda path: (ROOT / path).exists())
        self.deps = deps or {}              # file -> files it depends on
        self.shared_scripts = set(shared_scripts) - set(ACCEPTANCE)   # the verify-shared recipe's
        self.remix_scripts = set(remix_scripts) - set(ACCEPTANCE)     # the verify-remix recipe's
        self.gate_shared = gate_shared or {}   # manifest gate script -> True when remix_arg=False
        self.gate_once = gate_once or {}       # manifest gate script -> True when once=True
        self.gate_remixes = gate_remixes or {}   # a variant-only gate -> the remixes whose bound module carries it
        self.make_base, self.make_head = make_base, make_head
        self.read = read or (lambda path: (ROOT / path).read_text() if (ROOT / path).is_file() else None)
        self.read_base = read_base or (lambda path: None)   # the file at the base commit, or None
        self._dependents = None

    def keys_of(self, remix):
        """The module keys `remix` carries."""
        return {k for k, names in self.remixes_of.items() if remix in names}

    def _modules_of(self):
        n = {}
        for names in self.remixes_of.values():
            for r in names:
                n[r] = n.get(r, 0) + 1
        return n

    def carriers(self, remixes):
        """The remixes a module change checks: all of them (FULL), or
        (quick) the default remix when it carries the module, else the
        user-facing ones, else the smallest test remix."""
        if not self.quick or len(remixes) <= 1:
            return remixes
        if DEFAULT_REMIX in remixes:
            return [DEFAULT_REMIX]
        user = [r for r in remixes if r not in self.test_remixes]
        if user:
            return user
        count = self._modules_of()
        return [min(remixes, key=lambda r: (count.get(r, 0), r))]

    def cover(self):
        """Greedy set cover of the modules by the remixes: the remix adding
        the most uncovered modules first (ties by name), until every module
        some remix carries is covered."""
        modules_of = {}
        for key, names in self.remixes_of.items():
            for n in names:
                modules_of.setdefault(n, set()).add(key)
        left = set().union(*modules_of.values()) if modules_of else set()
        picked = []
        while left:
            name = min(modules_of, key=lambda n: (-len(modules_of[n] & left), n))
            if not modules_of[name] & left:
                break
            picked.append(name)
            left -= modules_of[name]
        return sorted(picked)

    def floor_note(self):
        return ("every remix" if len(self.floor) == len(self.remixes)
                else f"the cover ({len(self.floor)} of {len(self.remixes)} remixes)")

    def every(self):
        """The floor, both halves (plan() folds these into one check-shared
        and a check-remix each)."""
        return [cmd_check(r) for r in self.floor]

    def every_remix(self):
        return [cmd_check_remix(r) for r in self.floor]

    def identity(self):
        """`make identity` over the remixes in play (the test remixes left out
        unless TESTS=1)."""
        kind, cmd = CMD["identity"]
        if self.include_tests:
            return (kind, cmd)
        return (kind, cmd + " --remixes " + " ".join(sorted(self.remixes)))

    def build_change(self):
        """A change to the build: refhash (the flag matrix), identity (the
        remixes whose image moved, checked by --run), the shared half once
        for the floor."""
        if self.quick:
            # QUICK: refhash pins the build's flag matrix; `make identity`
            # (every remix built twice) is FULL=1's
            return [CMD["refhash"], CMD["verify-bus"], CMD["test-acceptance"], cmd_check_shared(self.floor)]
        return [CMD["refhash"], CMD["verify-bus"], self.identity(), CMD["test-acceptance"],
                cmd_check_shared(self.floor)]

    def dependents(self, path):
        """Every file that depends on `path`, transitively."""
        if self._dependents is None:
            rev = {}
            for f, ds in self.deps.items():
                for d in ds:
                    rev.setdefault(d, set()).add(f)
            self._dependents = rev
        seen, todo = set(), [path]
        while todo:
            p = todo.pop()
            for f in self._dependents.get(p, ()):
                if f not in seen:
                    seen.add(f); todo.append(f)
        return seen

    @classmethod
    def from_registry(cls, base=None, all_remixes=False, quick=False, include_tests=False):
        from remix import registry
        mods = registry.modules()
        module_key = {m.name: m.key for m in mods.values()}
        # The remixes in play: remixes/ only, unless TESTS=1 (the one-module
        # remixes under remixes/test/ are left out of every list, 30 Sep 2026)
        tests = [n for n in registry.remix_names() if registry.is_test(n)]
        names = [n for n in registry.remix_names() if include_tests or n not in tests]
        remixes_of = {k: [] for k in mods}
        test_carriers = {}
        for name in registry.remix_names():
            for k in registry.remix(name).modules:
                if name in names:
                    remixes_of.setdefault(k, []).append(name)
                else:
                    test_carriers.setdefault(k, []).append(name)
        gate_owners, gate_shared, gate_once = {}, {}, {}
        plain = {g.script for m in mods.values() for g in getattr(m, "gates", ())}
        def add_gate(key, g):
            owners = gate_owners.setdefault(g.script, [])
            if key not in owners:
                owners.append(key)
            gate_shared[g.script] = (gate_shared.get(g.script, True) and not g.remix_arg
                                     and g.stage == "isolated")
            gate_once[g.script] = gate_once.get(g.script, False) or getattr(g, "once", False)

        for m in mods.values():
            for g in variant_gates(m):
                add_gate(m.key, g)
        # Both build variants and selection callbacks can add gates. Discover
        # the latter from actual bound selections, then route each optional
        # gate only to remixes that install it (including test-only clients).
        gate_remixes = {}
        for name in registry.remix_names():
            r = registry.remix(name)
            b = registry.bound(r)
            for k in r.modules:
                for g in getattr(b[k], "gates", ()):
                    add_gate(k, g)
                    if g.script not in plain:
                        gate_remixes.setdefault(g.script, set()).add(name)
        make_head = (ROOT / "Makefile").read_text()
        make_base = None

        def read_base(path):
            if not base:
                return None
            r = subprocess.run(["git", "show", f"{base}:{path}"], cwd=ROOT, capture_output=True, text=True)
            return r.stdout if r.returncode == 0 else None
        make_base = read_base("Makefile")
        return cls(module_key, {k: sorted(v) for k, v in remixes_of.items()}, gate_owners,
                   names, deps=scan_deps(),
                   shared_scripts=recipe_scripts(make_head, "verify-shared"),
                   remix_scripts=recipe_scripts(make_head, "verify-remix"),
                   gate_shared=gate_shared, make_base=make_base, make_head=make_head,
                   all_remixes=all_remixes, read_base=read_base, quick=quick,
                   test_remixes=tests, test_carriers=test_carriers, include_tests=include_tests,
                   gate_once=gate_once, gate_remixes=gate_remixes)


def route_tool(path, ctx):
    """A tools/ or scripts/ file: the gates that depend on it."""
    if path.startswith("dsp/") or path in BUILD_ROOTS:
        return ctx.build_change(), f"the build: refhash the flag matrix, identity the remixes whose image moved (their checks follow), the shared half once for {ctx.floor_note()}"
    if path in CLASSIFIER or path.startswith("tools/verify/tests/"):
        return [CMD["test-acceptance"]], "the classifier and its tests: their own tests are the gate"
    if path in ACCEPTANCE:
        return [CMD["test-acceptance"]] + ctx.every() + [cmd_accept(r) for r in ctx.floor], f"the acceptance machinery: {ctx.floor_note()}"
    if path.startswith("tools/emu/ot_emu/"):
        return [CMD["ci-emu"], CMD["emu-cf"]] + ctx.every_remix(), f"the ColdFire port: the per-remix half of {ctx.floor_note()} (the set gates need OT_PROJECT)"
    if path.startswith(("tools/harness/dsp_host/", "tools/patches/")) or path in ("scripts/setup.sh", "scripts/vendor.sh"):
        return [CMD["ci-dsp"], CMD["verify-bus"]] + ctx.every(), f"the DSP toolchain: rebuild it first (scripts/setup.sh; a dsp_host change in an isolated tree, AGENTS.md); {ctx.floor_note()}"
    if path == "scripts/refhash.sh":
        return [CMD["refhash"]], ""
    users = ctx.dependents(path) | {path}
    gates, notes = [], []
    if users & set(BUILD_ROOTS):
        return ctx.build_change(), f"the build depends on it: refhash, identity (the remixes whose image moved are checked), the shared half once for {ctx.floor_note()}"
    if users & set(ACCEPTANCE):
        gates += [CMD["test-acceptance"]] + ctx.every() + [cmd_accept(r) for r in ctx.floor]
        notes.append(f"the acceptance machinery depends on it: {ctx.floor_note()}")
    if users & set(CLASSIFIER):
        gates.append(CMD["test-acceptance"])
    if BUS_GATE in users:
        gates.append(CMD["verify-bus"])
        notes.append("the bus's bit-identity gate depends on it")
    if users & ctx.shared_scripts:
        # once; REMIXES only picks the module union for the isolated gates,
        # and the floor's union is every module
        gates.append(cmd_check_shared(ctx.floor))
        notes.append("a gate of the shared half: " + ", ".join(sorted(pathlib.PurePosixPath(u).stem for u in users & ctx.shared_scripts)))
    if users & ctx.remix_scripts:
        gates += ctx.every_remix()
        notes.append(f"a gate of the per-remix half, run for {ctx.floor_note()}: " + ", ".join(sorted(pathlib.PurePosixPath(u).stem for u in users & ctx.remix_scripts)))
    for script in sorted(users & set(ctx.gate_owners)):
        owners = ctx.gate_owners[script]
        if script in ctx.gate_remixes:
            remixes = sorted(ctx.carriers(sorted(ctx.gate_remixes[script])))
        else:
            remixes = sorted({r for k in owners for r in ctx.carriers(ctx.remixes_of.get(k, []))})
        if not remixes:
            continue
        if ctx.gate_shared.get(script) or ctx.gate_once.get(script):
            # remix_arg=False or once=True: run by the shared half
            gates.append(cmd_check_shared(remixes, owners))
        else:
            gates += [cmd_check_remix(r, owners) for r in remixes]
        notes.append(f"{pathlib.PurePosixPath(script).stem}, a gate of " + ", ".join(owners))
    if path.startswith("tools/verify/") and not gates and path.startswith("tools/verify/verify_"):
        notes.append("a verifier no recipe or manifest runs (its own make target)")
    if not gates and not notes:
        notes.append("no gate depends on it")
    return gates, "; ".join(notes)


def route_makefile(ctx):
    if ctx.make_base is None:
        return ctx.every() + [CMD["ci"]], f"the Makefile (no base to diff against): {ctx.floor_note()}"
    targets, other = makefile_changes(ctx.make_base, ctx.make_head)
    gates, notes = [], []
    # A variable or a check target can change what the build writes (a
    # flag default) or how a gate runs: identity names the moved images,
    # the floor runs the gates.
    if other:
        gates += ([] if ctx.quick else [ctx.identity()]) + ctx.every() + [CMD["ci"]]
        notes.append("variables or defines changed: " + ", ".join(other) + f": identity + {ctx.floor_note()}")
    check = [t for t in targets if t in MAKE_CHECK]
    if check:
        gates += ([] if ctx.quick else [ctx.identity()]) + ctx.every() + [CMD["ci"]]
        notes.append("the check graph: " + ", ".join(check) + f": identity + {ctx.floor_note()}")
    runner = [t for t in targets if t in MAKE_RUNNER]
    if runner:
        gates.append(CMD["test-acceptance"])
        notes.append("the runner's targets: " + ", ".join(runner))
    ci = [t for t in targets if t in MAKE_CI]
    if ci:
        gates.append(CMD["ci"])
        notes.append("ci targets: " + ", ".join(ci))
    rest = [t for t in targets if t not in MAKE_CHECK | MAKE_RUNNER | MAKE_CI]
    if rest:
        notes.append("targets outside the check graph: " + ", ".join(rest) + ": no gate")
    if not targets and not other:
        notes.append("no target, variable or define changed")
    return gates, "; ".join(notes)


DISPLAY_FIELDS = {"doc", "proof", "proof_note", "author", "author_url", "category"}


def manifest_display_only(base_src, head_src):
    """True when two manifests differ only in docstrings and the display
    fields (DISPLAY_FIELDS, on any call: Module, Param, ...). A new or
    unparsable manifest is a real change."""
    if base_src is None or head_src is None:
        return False

    def normal(src):
        tree = ast.parse(src)
        for node in ast.walk(tree):
            body = getattr(node, "body", None)
            if isinstance(body, list) and body and isinstance(body[0], ast.Expr) \
                    and isinstance(getattr(body[0], "value", None), ast.Constant) \
                    and isinstance(body[0].value.value, str):
                del body[0]
            if isinstance(node, ast.Call):
                node.keywords = [k for k in node.keywords if k.arg not in DISPLAY_FIELDS]
        return ast.dump(tree)
    try:
        return normal(base_src) == normal(head_src)
    except SyntaxError:
        return False


PORT_STAMP = "out/emu/.sources.sha256"      # written by `make emu-cf`: the digest of the sources it built


def port_sources(src):
    return sorted(p for p in src.rglob("*") if p.is_file()
                  and not {"build", "out"} & set(p.relative_to(src).parts))


def port_digest(src=None):
    """One digest over the port's sources (paths and contents)."""
    src = src or ROOT / "tools/emu/ot_emu"
    h = hashlib.sha256()
    for p in port_sources(src):
        h.update(str(p.relative_to(src)).encode()); h.update(b"\0"); h.update(p.read_bytes()); h.update(b"\0")
    return h.hexdigest()


def stamp_port(src=None, stamp=None):
    stamp = stamp or ROOT / PORT_STAMP
    stamp.parent.mkdir(parents=True, exist_ok=True)
    stamp.write_text(port_digest(src) + "\n")


def port_is_stale(exe=None, src=None, stamp=None):
    """The port binary was not built from these sources: a rebase brought
    emulator changes the root tree never rebuilt (28 Sep 2026: four false
    reds in one run; the shards rebuild theirs). With the stamp `make
    emu-cf` writes, by content; without one, by mtime -- which a fresh
    worktree checkout always fails, 50 s of rebuild for the same bytes
    (6 Oct 2026). A missing binary is stale: without it every port gate
    SKIPs and the run is green (a fresh worktree's reach passed without
    verify_kits, 11 Oct 2026)."""
    exe = exe or ROOT / "out/emu/ot_emu"
    src = src or ROOT / "tools/emu/ot_emu"
    stamp = stamp or exe.parent / pathlib.Path(PORT_STAMP).name     # beside the binary it describes
    if not src.is_dir():
        return False
    if not exe.is_file():
        return True
    if stamp.is_file():
        return stamp.read_text().strip() != port_digest(src)
    built = exe.stat().st_mtime
    return any(p.stat().st_mtime > built for p in port_sources(src))


# The steps that fetch, check out or patch vendor/ (scripts/vendor.sh) or build in
# it (vendor/dsp56300/build). In a worktree vendor/ is a symlink to the main
# checkout's, so running them rewrites every session's toolchain.
VENDOR_WRITERS = ("ci", "ci-dsp", "ci-emu")


def shared_vendor(root=None):
    """vendor/ here is another checkout's (a worktree)."""
    return ((root or ROOT) / "vendor").is_symlink()


def vendor_safe(kind, command, shared):
    """-> (the command to run or None, a note): what `reach --run` does with
    a step that writes vendor/ when vendor/ is shared. ci-emu becomes
    ci-emu-tree (the same build and tests into this tree's out/emu-ci, no
    fetch); ci-dsp and ci are left to CI, named in the output and the table."""
    if not shared or kind not in VENDOR_WRITERS:
        return command, None
    if kind == "ci-emu":
        return "make ci-emu-tree", ("vendor/ is shared with the main checkout: `make ci-emu` runs scripts/vendor.sh into it; "
                                    "running `make ci-emu-tree` (the same build and tests in this tree's out/emu-ci)")
    return None, (f"`{command}` is left to CI: it would fetch, patch and build in vendor/, which every worktree shares "
                  f"(run it from the main checkout if you need it here)")


PORT_KINDS = ("check", "check-shared", "check-remix", "accept")     # the shared half runs port gates too (verify_kits)


def classify(paths, ctx):
    """[(path, [(kind, command), ...], note)] for each changed path."""
    out = []
    for path in paths:
        parts = pathlib.PurePosixPath(path).parts
        gates, note = [], ""
        top = parts[0] if parts else ""
        if top == "modules" and len(parts) >= 2:
            d = parts[1]
            if d.startswith("_"):
                note = "template: skipped by the registry"
            elif parts[-1].endswith(".md"):
                # A module's README is rendered nowhere; the index reads the
                # manifest. Same as a remix's README.
                gates = [CMD["verify_docs"]]
            elif parts[-1] == "manifest.py" and d in ctx.module_key and \
                    manifest_display_only(ctx.read_base(path), ctx.read(path)):
                # Only the fields the README table and the remixer draw
                # changed (doc, proof, proof_note, author, author_url,
                # category, a docstring): the image, the gates and the
                # dearest settings are what they were.
                gates = [CMD["verify_docs"]]
                note = f"{ctx.module_key[d]}: display fields only"
            elif d in ctx.module_key:
                key = ctx.module_key[d]
                remixes = ctx.carriers(ctx.remixes_of.get(key, []))
                if remixes:
                    # the shared half for this module's own shared gates
                    # only; the other modules' are what they were on main
                    gates = ([cmd_check_shared(remixes, [key])] + [cmd_check_remix(r, [key]) for r in remixes]
                             + [cmd_accept(r) for r in remixes])
                    note = f"{key} -> " + ", ".join(remixes)
                elif ctx.test_carriers.get(key):
                    note = f"{key}: carried only by test remixes ({', '.join(sorted(ctx.test_carriers[key]))}): not checked; TESTS=1 runs them"
                    gates = [CMD["selftest"]]
                else:
                    note = f"{key}: no remix carries it (the selftest refuses this)"
                    gates = [CMD["selftest"]]
                if key in bus_modules():
                    gates = gates + [CMD["verify-bus"]]
                    note += "; a module of remix bus: the bus's bit-identity gate"
            elif not ctx.exists(f"modules/{d}"):
                # A removed (or renamed) module: the registry no longer knows
                # it, and the remixes that carried it changed their remix.py
                # in the same diff (the selftest refuses an unknown module),
                # which routes their checks. Nothing more to run for the
                # directory itself.
                note = "removed module directory: its remixes' selections are in the diff"
            else:
                note = "unknown module directory"
                gates = ctx.every()
        elif top == "remixes" and len(parts) >= 2:
            # remixes/<name>/..., remixes/test/<name>/..., or a flat remixes/<name>.py
            name = parts[2] if parts[1] == "test" and len(parts) >= 3 else parts[1]
            name = name[:-3] if name.endswith(".py") else name
            rdir = "/".join(parts[:3] if parts[1] == "test" else parts[:2])
            if parts[-1] == "README.md":
                gates = [CMD["verify_docs"]]
            elif not ctx.exists(rdir):
                # A removed remix: nothing to build. The selftest refuses a
                # module the deletion orphaned, and the index is re-rendered
                # (verify_docs).
                note = "removed remix: the selftest and the index"
                gates = [CMD["selftest"], CMD["verify_docs"]]
            elif parts[-1].endswith(".py") and \
                    manifest_display_only(ctx.read_base(path), ctx.read(path)):
                # Only the fields the index draws changed (doc, proof,
                # proof_note, a docstring): the selection and the image are
                # what they were.
                gates = [CMD["verify_docs"]]
                note = f"{name}: display fields only"
            elif name in ctx.test_remixes and not ctx.include_tests:
                note = "a test remix: not checked (TESTS=1 runs it)"
                gates = [CMD["selftest"], CMD["verify_docs"]]
            else:
                gates = [cmd_check(name), cmd_accept(name)]
        elif top in ("tools", "scripts", "dsp"):
            gates, note = route_tool(path, ctx)
        elif path == "Makefile":
            gates, note = route_makefile(ctx)
        elif path.startswith(".github/"):
            gates = [CMD["ci"]]
        elif path.endswith(".md") or path.startswith("docs/"):
            gates = [CMD["verify_docs"]]
        elif path in ("pyproject.toml", "uv.lock", "LICENSE", ".gitignore", ".gitmodules"):
            gates = ctx.every()
        else:
            gates = ctx.every()
            note = f"unclassified: {ctx.floor_note()}"
        out.append((path, gates, note))
    return out


def plan(rows, accept_runs_check=True, keys_of=None):
    """The commands in run order, each once, with the paths that put it
    there. Two or more remixes to check become ONE `make check-shared`
    (the remix-independent gates, once) and a `make check-remix` each; a
    single full check alone stays `make check`. Two or more remixes to
    accept become ONE `make accept REMIXES="..."` (the runner runs the
    shared half once), and with `accept_runs_check` (STRESS_SOURCE is set,
    so the accept line will run) a remix that is accepted is not checked
    separately: accept runs both halves of its check itself. `keys_of`
    (remix -> its module keys) lets a merged shared half stay scoped: an
    unscoped line stands for every module of ITS remixes, not of all."""
    by_cmd = {}
    for path, gates, _ in rows:
        for kind, command in gates:
            by_cmd.setdefault((kind, command), []).append(path)
    accepts = {k: v for k, v in by_cmd.items() if k[0] == "accept"}
    accepted = []
    if accepts:
        accepted = sorted(accept_remix(c) for _, c in accepts)
        paths = sorted({p for v in accepts.values() for p in v})
        for k in accepts:
            del by_cmd[k]
        if len(accepted) > 1:
            by_cmd[("accept", f'make accept REMIXES="{" ".join(accepted)}" STRESS_SOURCE=${{STRESS_SOURCE}}')] = paths
        else:
            by_cmd[cmd_accept(accepted[0])] = paths
        if accept_runs_check:
            for k in [k for k in by_cmd if k[0] in ("check", "check-remix") and accept_remix(k[1]) in accepted]:
                del by_cmd[k]
            # a module's scoped shared half: accept runs the whole shared half
            for k in [k for k in by_cmd if k[0] == "check-shared" and shared_modules(k[1])
                      and set(shared_remixes(k[1])) <= set(accepted)]:
                del by_cmd[k]
    checks = {k: v for k, v in by_cmd.items() if k[0] == "check"}
    halves = [k for k in by_cmd if k[0] in ("check-shared", "check-remix")]
    if len(checks) > 1 or (checks and halves):
        # full checks beside other halves: every full check is its two halves
        for (k, c), v in checks.items():
            del by_cmd[(k, c)]
            r = accept_remix(c)
            by_cmd.setdefault(cmd_check_shared([r]), []).extend(v)
            by_cmd.setdefault(cmd_check_remix(r), []).extend(v)
    # one per-remix line per remix: the union of its scopes, or the whole
    # half when any line checks it whole
    per = {}
    for (k, c), v in list(by_cmd.items()):
        if k == "check-remix":
            per.setdefault(accept_remix(c), []).append((c, v))
    for r, entries in per.items():
        if len(entries) < 2:
            continue
        scopes = [shared_modules(c) for c, _ in entries]
        merged = None if any(m is None for m in scopes) else sorted({k for m in scopes for k in m})
        paths = sorted({p for _, v in entries for p in v})
        for c, _ in entries:
            del by_cmd[("check-remix", c)]
        by_cmd[cmd_check_remix(r, merged)] = paths
    shared = {k: v for k, v in by_cmd.items() if k[0] == "check-shared"}
    if len(shared) > 1:
        names = sorted({r for _, c in shared for r in shared_remixes(c)})
        scopes = [shared_modules(c) for _, c in shared]
        # An unscoped line is every module of its own remixes; a scoped one
        # its keys. Until 12 Oct 2026 one unscoped line (a tool change's
        # floor, octatrick) made the merged line the whole shared half of
        # every remix in it, so a tool change beside a bottleservice module
        # change ran verify_kits (739 s) though neither reached KITS.
        if all(m is None for m in scopes) or keys_of is None and any(m is None for m in scopes):
            modules = None
        else:
            modules = sorted({k for (_, c), m in zip(shared, scopes)
                              for k in (m if m is not None else
                                        {k for r in shared_remixes(c) for k in keys_of(r)})})
        paths = sorted({p for v in shared.values() for p in v})
        for k in shared:
            del by_cmd[k]
        by_cmd[cmd_check_shared(names, modules)] = paths
    keyed = sorted(by_cmd.items(), key=lambda kv: (ORDER.index(kv[0][0]), kv[0][1]))
    return [(kind, command, sorted(set(paths))) for (kind, command), paths in keyed]


def remixes_reached(rows):
    out = set()
    for _, gates, _ in rows:
        for kind, command in gates:
            if kind in ("check", "check-remix"):
                out.add(accept_remix(command))
            elif kind == "check-shared":
                out |= set(shared_remixes(command))
    return sorted(out)


def sharded(items, jobs):
    """The check-remix lines as one `check_shards.py --jobs N` line, in
    the first one's place: each remix's half in its own worktree, N at a
    time (the halves all write out/mainos_bus.bin, so one tree runs one).
    An accept line over several remixes gets `JOBS=N`: the runner runs
    their per-remix halves the same way."""
    items = [(k, c + f" JOBS={jobs}", p) if k == "accept" and "REMIXES=" in c and "JOBS=" not in c else (k, c, p)
             for k, c, p in items]
    # a lone `make check` is its two halves, so its per-remix half splits
    # over the shards by gate (11 Oct 2026: run whole, one remix took one
    # shard and left the rest idle)
    halves = []
    for k, c, p in items:
        if k == "check":
            r = accept_remix(c)
            halves += [(*cmd_check_shared([r]), p), (*cmd_check_remix(r), p)]
        else:
            halves.append((k, c, p))
    items = halves
    lines = [c for k, c, _ in items if k == "check-remix"]
    remixes = [accept_remix(c) for c in lines]
    if not remixes:
        return items
    scopes = [shared_modules(c) for c in lines]
    # one module list for the run: the union, or every gate when any remix
    # is checked whole
    modules = None if any(m is None for m in scopes) else sorted({k for m in scopes for k in m})
    out, done = [], False
    for kind, command, paths in items:
        if kind != "check-remix":
            out.append((kind, command, paths))
        elif not done:
            all_paths = sorted({p for k, _, ps in items if k == "check-remix" for p in ps})
            out.append(("check-remix", f"python3 tools/verify/check_shards.py --jobs {jobs} "
                        + (f'--modules "{",".join(modules)}" ' if modules else "") + " ".join(remixes), all_paths))
            done = True
    return out


def unsharded(items):
    """The inverse of sharded(): a check_shards line back into its
    check-remix lines, an accept line without its JOBS."""
    out = []
    for kind, command, paths in items:
        if kind == "check-remix" and "check_shards.py" in command:
            remixes, modules = shards_line(command)
            for r in remixes:
                out.append((kind, cmd_check_remix(r, modules)[1], paths))
        elif kind == "accept" and " JOBS=" in command:
            out.append((kind, command.split(" JOBS=")[0], paths))
        else:
            out.append((kind, command, paths))
    return out


def replan(queue, extra, stress, jobs, keys_of=None):
    """The remaining queue plus identity's extra gates, planned again as
    one: the extra checks fold into the accept line (with STRESS_SOURCE)
    and the check-remix lines into the shards, instead of running one
    full `make check` per moved remix after the fact (28 Sep 2026: 34
    serial checks, then the same 34 inside accept)."""
    rows = []
    for kind, command, paths in unsharded(queue):
        path = paths[0] if paths else ""
        if kind == "accept" and 'REMIXES="' in command:
            rows += [(path, [cmd_accept(r)], "") for r in shared_remixes(command)]
        else:
            rows.append((path, [(kind, command)], ""))
    rows += [("image_identity", [g], "") for g in extra]
    items = plan(rows, accept_runs_check=bool(stress), keys_of=keys_of)
    return sharded(items, jobs) if jobs > 1 else items


# The commands that take seconds and share one entry; every other command
# is an entry of its own (a CI runner each, with the whole setup).
LIGHT = ("selftest",)

# Commands a CI job of its own runs for every diff that plans them, so the
# matrix has no unit for them (a local `make reach RUN=1` still runs them):
# verify_docs and test-acceptance by Docs, Site and Web Patches (always; the
# acceptance step when `acceptance` is affected), ci-dsp by DSP Toolchain, ci-emu
# by ColdFire Port Unit Tests, and ci (ci-dsp, ci-emu, test-acceptance,
# verify-docs) by those. The path prefixes (tools/verify/ci_paths.py) of
# those jobs cover every path that plans these commands: the Makefile and
# .github/ plan `ci`; tools/harness/dsp_host, tools/patches and
# scripts/{setup,vendor}.sh plan ci-dsp; tools/emu/ot_emu plans ci-emu.
DEDICATED = ("verify_docs", "test-acceptance", "ci", "ci-dsp", "ci-emu")


def entry_name(kind, command):
    if kind in ("check", "check-remix", "accept") and "REMIX=" in command:
        return f"{kind} {accept_remix(command)}"
    return kind


# Units that would set the wall time on one runner, cut up (a CI runner each).
# A remix: each part is the gate jobs named here (check_shards --only-jobs, the
# unit `check-remix <remix> (<part>)`), the unit `check-remix <remix>` every
# other (--skip-jobs); a name that is no gate job is refused there, so a
# rename cannot drop a gate. The `project` part is the jobs that read
# OT_PROJECT: its unit alone gets the generated project (ci.yml, tools/hw/
# ot_fresh.py, 255 s on a runner), the others run as they did without one.
# `image` is not in it: with a project its verify_brain fails and the job took
# 2869 s on cxosc-core (27 Oct 2026). The shared half: its module_gates step on
# one unit, every other step on the other (Makefile SHARED_PART). Times of run
# 40467801048: remix-switch 481 s of octabam's 1886 s over 3 shards (the other
# jobs: 1405 s, 468 s over 3 shards); module_gates --shared 353 s of the shared
# half's 645 s, run serially.
SPLIT_REMIX_JOBS = {"octabam": {"long": ("remix-switch",), "project": ("set", "mode-defaults", "plocks-p2")}}

# A unit that runs one gate on its own, with a generated project, beside the units above: `check-remix <remix> (<name>)`
# is COMMAND. It is additive (the remix's other units still run that gate, without a project), so it exists only when
# MODULE is reached. `brain`: BRAIN's image-stage gate, verify_brain, needs a project; the `image` job cannot take one, and
# scoping it with --modules does not narrow it (that is "reached from BRAIN": 9 gates of ten modules, 4581 s, with
# verify_usb_post, verify_load_meter and verify_usb_load_meter failing on a generated project, run 40640514673), so the
# unit runs verify_brain alone. It builds its own image and reads OT_PROJECT, which ci.yml sets for a `(brain)` unit.
SPLIT_EXTRA_UNITS = {"octabam": {"brain": ("BRAIN", ".venv/bin/python3 tools/verify/verify_brain.py octabam")}}


def entries(items, jobs):
    """The plan as units that run independently, for a caller that gives
    each its own machine (the CI matrix): [{"name", "items"}], `items` as
    in the plan. The quick commands (LIGHT) are one entry, `selftest`; DEDICATED ones are none; a check_shards
    line becomes one line per remix (`--jobs` shards on that machine); every
    other command is its own entry. `selftest` comes last: the dear units start first. A unit is run alone with `--only NAME`,
    which plans again from the same diff: `jobs` must match between the two
    calls. `identity` still queues the checks of the remixes it names inside
    its own entry."""
    out, light = [], []
    for item in items:
        kind, command, paths = item
        if kind in DEDICATED:
            continue
        if kind in LIGHT:
            light.append(item)
        elif is_shards(item):
            remixes, modules = shards_line(command)
            for r in remixes:
                line = lambda extra="": (f"python3 tools/verify/check_shards.py --jobs {jobs} "
                                         + (f'--modules "{",".join(modules)}" ' if modules else "") + extra + r)
                if r in SPLIT_REMIX_JOBS:
                    parts = SPLIT_REMIX_JOBS[r]
                    every = ",".join(n for names in parts.values() for n in names)
                    out.append({"name": f"check-remix {r}", "items": [(kind, line(f"--skip-jobs {every} "), paths)]})
                    for part, names in parts.items():
                        out.append({"name": f"check-remix {r} ({part})",
                                    "items": [(kind, line(f"--only-jobs {','.join(names)} "), paths)]})
                    for name, (module, command) in SPLIT_EXTRA_UNITS.get(r, {}).items():
                        if modules is None or module in modules:
                            out.append({"name": f"check-remix {r} ({name})", "items": [(kind, command, paths)]})
                else:
                    out.append({"name": f"check-remix {r}", "items": [(kind, line(), paths)]})
        elif kind == "check-shared":
            out.append({"name": "check-shared", "items": [(kind, command + " SHARED_PART=rest", paths)]})
            out.append({"name": "check-shared (module gates)", "items": [(kind, command + " SHARED_PART=modules", paths)]})
        else:
            out.append({"name": entry_name(kind, command), "items": [item]})
    if light:
        out.append({"name": "selftest", "items": light})
    seen = {}
    for e in out:
        n = seen[e["name"]] = seen.get(e["name"], 0) + 1
        if n > 1:
            e["name"] += f" #{n}"
    return out


def plan_json(base, merge_base, quick, jobs, remixes, items):
    """The plan as data, for a caller that fans the gates out (a CI matrix):
    `gates`, one entry per command in run order with the paths that put it
    there, and `matrix`, the units entries() makes of them. `${STRESS_SOURCE}`
    and `${BASE}` are left in the commands as printed; --run substitutes them."""
    return {"base": base, "merge_base": merge_base, "tier": "quick" if quick else "full", "jobs": jobs,
            "remixes": remixes,
            "gates": [{"kind": k, "command": c, "paths": list(ps)} for k, c, ps in items],
            "matrix": [{"name": e["name"], "commands": [c for _, c, _ in e["items"]]} for e in entries(items, jobs)]}


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


def changed_paths(base):
    mb = git("merge-base", base, "HEAD")
    if mb.returncode:
        sys.exit(f"reach: no merge-base with {base}: {mb.stderr.strip()} (git fetch origin?)")
    merge_base = mb.stdout.strip()
    if git("merge-base", "--is-ancestor", base, "HEAD").returncode:
        sys.exit(f"reach: {base} is not an ancestor of HEAD -- rebase first; gates run "
                 f"before the rebase are not a result (CONTRIBUTING.md)")
    diff = git("diff", "--name-only", merge_base).stdout.split()
    untracked = git("ls-files", "--others", "--exclude-standard").stdout.split()
    return merge_base, sorted(set(diff) | set(untracked))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default="origin/main")
    ap.add_argument("--paths", nargs="*", help="classify these paths instead of the diff")
    ap.add_argument("--run", action="store_true", help="run the commands, in order, stopping at the first failure")
    ap.add_argument("--keep-going", action="store_true", help="with --run: run every command, then one table")
    ap.add_argument("--jobs", type=int, default=1,
                    help="with --run: the check-remix lines through check_shards.py, N worktrees at a time")
    ap.add_argument("--tests", action="store_true",
                    help="include the remixes under remixes/test/ (left out by default)")
    ap.add_argument("--full", action="store_true",
                    help="every gate a change reaches: the cover, identity, accept, every carrying remix, full speed "
                         "(the default is quick: see the module docstring)")
    ap.add_argument("--all", action="store_true",
                    help="the floor is every remix instead of the cover (the remixes that between them carry every module)")
    ap.add_argument("--no-cache", action="store_true",
                    help="with --run: run every gate job (check_shards' cache of passes, tools/verify/gate_cache.py)")
    ap.add_argument("--only", metavar="NAME",
                    help="plan as usual, then keep only the unit NAME of the matrix in --json (entries()); "
                         "with --run, run just that unit")
    ap.add_argument("--json", action="store_true",
                    help="print the plan as one JSON object on stdout (the report goes to stderr) and exit; not with --run")
    ap.add_argument("--stamp-port", action="store_true",
                    help=f"record the port sources' digest at {PORT_STAMP} (make emu-cf, after its build) and exit")
    a = ap.parse_args(argv)
    if a.json and a.run:
        ap.error("--json prints the plan and runs nothing: not with --run")
    if a.stamp_port:
        stamp_port()
        return 0
    if a.paths is not None:
        merge_base, paths = None, sorted(set(a.paths))
    else:
        merge_base, paths = changed_paths(a.base)
    quick = not a.full
    report_to = sys.stdout
    if a.json:
        sys.stdout = sys.stderr
    if quick and a.jobs == 1:
        # the machine's gate slots no other session holds now, at least two
        # (a fixed 2 until 11 Oct 2026, with 60-70% of the CPU idle while
        # one remix's half ran alone); the slots still cap what runs at once
        a.jobs = max(2, slots.count() - len(slots.holders()))
    ctx = Context.from_registry(base=merge_base or a.base, all_remixes=a.all, quick=quick, include_tests=a.tests)
    rows = classify(paths, ctx)
    if merge_base:
        print(f"reach: {len(paths)} changed path{'s' if len(paths) != 1 else ''} against {a.base} ({merge_base[:10]})")
    for path, _, note in rows:
        print(f"  {path}" + (f"   [{note}]" if note else ""))
    if not rows:
        print("  (nothing changed)")
        if a.json:
            sys.stdout = report_to
            print(json.dumps(plan_json(a.base, merge_base, quick, a.jobs, [], []), indent=2))
        return 0
    print("\nremixes reached: " + (", ".join(remixes_reached(rows)) or "none"))
    print("\ngates, in order:")
    stress = os.environ.get("STRESS_SOURCE")
    items = plan(rows, accept_runs_check=bool(stress) and not quick, keys_of=ctx.keys_of)
    if quick:
        items = [it for it in items if it[0] != "accept"]
    if a.jobs > 1:
        items = sharded(items, a.jobs)
    if a.only is not None:
        by_name = {e["name"]: e for e in entries(items, a.jobs)}
        if a.only not in by_name:
            sys.exit(f"reach: --only {a.only!r}: no such unit; this plan has " + (", ".join(map(repr, by_name)) or "none"))
        items = by_name[a.only]["items"]
    for kind, command, from_paths in items:
        why = from_paths[0] + (f" +{len(from_paths) - 1}" if len(from_paths) > 1 else "")
        print(f"  {command:56}  # {why}")
    if not items:
        print("  (none: no gate depends on what changed)")
    if any(k == "identity" for k, _, _ in items):
        print(f"  then: make check REMIX=<r> for each remix image_identity names (--run does this; the floor is {ctx.floor_note()})")
    print(f"\n{'QUICK' if quick else 'FULL'}: " + ("the carrying remixes (user-facing first), one floor remix, no identity, "
          f"no accept, {a.jobs} shards, nice 10; FULL=1 for the lot" if quick else "every gate the change reaches"))
    if any(k == "accept" for k, _, _ in items) and not stress:
        print("\nSTRESS_SOURCE is unset: point it at a local project (never committed) for the accept line"
              " (it then runs the accepted remixes' checks itself).")
    if a.json:
        sys.stdout = report_to
        print(json.dumps(plan_json(a.base, merge_base, quick, a.jobs, remixes_reached(rows), items), indent=2))
        return 0
    if not a.run:
        return 0
    print()
    results = []
    queue = list(items)
    if any(k in PORT_KINDS for k, _, _ in queue) and not any(k == "emu-cf" for k, _, _ in queue) and port_is_stale():
        print("reach: out/emu/ot_emu is missing or older than tools/emu/ot_emu: the port from the store first")
        queue.insert(0, ("emu-get", CMD["emu-get"][1], ["tools/emu/ot_emu"]))
    def overlap_tree(kind):
        """A scratch worktree of this tree for a build step that runs beside another."""
        path = ROOT / "out/overlap" / kind
        (ROOT / "out/overlap").mkdir(parents=True, exist_ok=True)
        check_shards.make_shard(path, ROOT / f"out/overlap/{kind}.setup.log")
        return path

    def run_command(kind, command, cwd=None):
        """-> (the command as run, its exit code, seconds); `cwd` a scratch
        tree of this one (overlap_tree) when the step runs beside another."""
        cmd = command.replace("${STRESS_SOURCE}", stress or "").replace("${BASE}", a.base)
        print(f"reach: running {cmd}", flush=True)
        t0 = time.monotonic()
        if quick and BACKGROUND:
            cmd = f"{BACKGROUND} {cmd}"      # nice 10: the performance cores, below the desktop
        env = dict(os.environ) if cwd is None else check_shards.clean_env()
        if a.no_cache:
            env["OCTABAM_GATE_CACHE"] = "0"
        # QUICK skips what a gate marks FULL only (verify_kits --quick); FULL runs it all
        env["OCTABAM_QUICK"] = "1" if quick else "0"
        # A command run in this tree holds one of the machine's gate slots
        # (tools/verify/slots.py); check_shards and accept take theirs per
        # job, so holding one around them could leave every slot held by
        # a parent waiting on its own children.
        own_slots = "check_shards.py" in command or kind == "accept"
        with (contextlib.nullcontext(env) if own_slots else slots.slot(f"reach {command}")) as env_slot:
            env.update({k: v for k, v in env_slot.items() if k == "OCTABAM_SLOT"})
            r = subprocess.run(cmd, shell=True, cwd=cwd or ROOT, env=env)
        return cmd, r.returncode, time.monotonic() - t0

    def record(command, cmd, rc, seconds):
        results.append((command, "ok" if rc == 0 else f"FAILED ({rc})", seconds))
        if rc:
            print(f"reach: FAILED ({rc}) {cmd}")
            # module_gates and check_shards record their own gates' and jobs'
            # failures; this records the step (selftest, refhash, docs, ...)
            gate_ledger.record(f"reach:{command}", "", f"exit {rc}")

    left_to_ci = []
    while queue:
        kind, command, _ = queue.pop(0)
        safe, note = vendor_safe(kind, command, shared_vendor())
        if note:
            print(f"reach: {note}", flush=True)
            if safe is None:
                left_to_ci.append(command)
                results.append((command, "LEFT TO CI", 0.0))
                continue
            command = safe
        if kind == "accept" and not stress:
            print(f"reach: BLOCKED {command}: STRESS_SOURCE is unset")
            if not a.keep_going:
                return 2
            results.append((command, "BLOCKED", 0.0))
            continue
        # Steps that do not depend on one another run together: the unit
        # tests, refhash, the bus gate, the shared half and the shards. The
        # steps that build (refhash, the bus gate, the shared half) write
        # out/ and read their own artifacts back, so the first stays in this
        # tree and each other one runs in a scratch copy of it
        # (check_shards.make_shard, out/overlap/); the shards already work
        # in their own worktrees. identity, the checks and accept stay in
        # order.
        group = [(kind, command)]
        if kind in OVERLAP:
            while queue and (queue[0][0] in OVERLAP or is_shards(queue[0])):
                group.append(queue.pop(0)[:2])
        if len(group) > 1:
            # the scratch trees are made inside each step's own thread (a
            # worktree, its submodules and a port boot take about a minute
            # the first time: made first they delayed every step)
            tasks, in_root = [], False
            for k, c in group:
                scratch = k in BUILDS and in_root
                in_root = in_root or k in BUILDS
                tasks.append((k, c, scratch))
            with cf.ThreadPoolExecutor(max_workers=len(tasks)) as ex:
                futures = [(c, ex.submit(lambda k=k, c=c, sc=sc: run_command(k, c, overlap_tree(k) if sc else None)))
                           for k, c, sc in tasks]
                done = [(c, f.result()) for c, f in futures]
            for c, (cmd, rc, secs) in done:
                record(c, cmd, rc, secs)
            if any(rc for _, (_, rc, _) in done) and not a.keep_going:
                return 1
            continue
        cmd, rc, secs = run_command(kind, command)
        record(command, cmd, rc, secs)
        if rc:
            if not a.keep_going:
                return 1
        elif kind == "identity":
            # The remixes whose image moved: their full check (and accept,
            # with STRESS_SOURCE) join the queue in the floor's place.
            changed = json.loads((ROOT / "out/identity/changed.json").read_text())
            extra = [cmd_check(r) for r in changed] + ([cmd_accept(r) for r in changed] if stress else [])
            done = {c for c, _, _ in results}
            before = len(queue)
            queue = [it for it in replan(queue, extra, stress, a.jobs, ctx.keys_of) if it[1] not in done]
            print(f"reach: identity names {len(changed)} changed remix{'es' if len(changed) != 1 else ''}"
                  + (": " + ", ".join(changed) if changed else "")
                  + f" -> {len(queue) - before:+d} gate{'s' if abs(len(queue) - before) != 1 else ''} in the queue")
    if left_to_ci:
        print("\nreach: NOT RUN here, left to CI (vendor/ is shared): " + "; ".join(left_to_ci))
    if a.keep_going:
        print("\nreach: results")
        for command, status, seconds in results:
            print(f"  {status:12} {seconds:7.0f} s  {command}")
    bad = [r for r in results if r[1] not in ("ok", "LEFT TO CI")]
    if bad:
        print(f"reach: {len(bad)} of {len(results)} gates did not pass")
        return 2 if all(r[1] == "BLOCKED" for r in bad) else 1
    print("reach: every gate passed" if not left_to_ci else
          f"reach: every gate that runs here passed; {len(left_to_ci)} left to CI")
    return 0


if __name__ == "__main__":
    sys.exit(main())
