#!/usr/bin/env python3
"""The per-remix half of `make check` for several remixes, N worktrees at a time.

    python3 tools/verify/check_shards.py [--jobs N] [--keep] [--shards DIR] <remix> ...
    make check-remixes REMIXES="a b c" [JOBS=4]
    make reach RUN=1 JOBS=4            # the check-remix lines through this
    python3 tools/verify/check_shards.py --by-gate [--jobs N] <remix>
    make check-remix-gates REMIX=<name> [JOBS=4]

Every `make check-remix` builds over out/mainos_bus.bin and its verifiers
read out/, so one tree runs one remix at a time; PR #486's 25-remix table
was three worktrees driven by hand. This makes N detached worktrees of HEAD
plus the tree's uncommitted changes under out/shards/<i>, each with the
shared vendor/ and .venv/ links, the stock slice, its submodules and its
own copy of the port (out/emu is never linked between trees: AGENTS.md;
since 12 Oct 2026 the binaries come from tools/emu/port_store.py, built
once per source state for the machine's own architecture, host_arch(),
and copied in), then
hands the remixes out from one queue as shards come free, so the dear ones
(bottleservice, rig-kits) do not decide the wall time. Logs land in
out/check_shards/<remix>.log; one table at the end; exit 1 when a remix
failed. The shards are KEPT between runs (since 28 Sep 2026): a run finds
out/shards/<i> in place and refreshes it -- `git checkout --detach` to this
tree's HEAD plus its uncommitted diff, `git submodule update`, the shard's
out/ wiped except emu/ and raw/, and the port copied from the store --
which turns ~220 s of setup (four worktrees, four `cmake --fresh` builds)
into a few seconds; a new shard costs the copy, not a build (12 Oct 2026:
three new shards took 125 s). `--fresh` rebuilds them from nothing; `--rm` removes them after.

THE LONG POLE IS SPLIT (29 Sep 2026). A remix whose half would set the
wall time runs as its gate jobs (as `--by-gate` below) in the same queue as
the other remixes' whole halves, longest first, so it no longer takes one
shard for the whole run while the others idle. Which remixes: `--split
auto` (the default) splits a remix whose last recorded time
(times_path(): <git common dir>/octabam-gate-times.json, shared by every
worktree since 11 Oct 2026, so a fresh worktree's first run splits too;
out/check_shards/times.json until then) exceeds both 300 s
and the run's total over the shard count; with no record, none (until 6
Oct 2026 the remixes that carried Octakit, whose project load took ~32 s
emulated). `--split none` runs every remix whole; `--split a,b` names
them.

ONE REMIX IS SPLIT TOO (11 Oct 2026). A run of one remix over more than
one shard runs it as gate jobs: run whole it took one shard and left the
rest idle.

A PART OF ONE REMIX (27 Oct 2026). `--only-jobs a,b` / `--skip-jobs a,b`
run a remix as gate jobs, cut to the named ones or without them (CI runs
the two as separate units, reach.SPLIT_REMIX_JOBS). A name that is no gate
job is refused; under `--modules` a name is checked against the remix's
whole job list, and one outside the reached modules is left out of the cut.

CACHED (11 Oct 2026). Each job (a remix's whole half, or one gate job)
builds the remix's image first and looks itself up in
tools/verify/gate_cache.py: a pass recorded for the same image and the
same inputs is reported `cached` and not run. Only passes are stored;
`--no-cache` (or OCTABAM_GATE_CACHE=0) runs everything.

SLOTS (11 Oct 2026). Every job holds one of the machine's gate slots
(tools/verify/slots.py) while it runs, so this run and every other
session's share the cores instead of each sizing for an idle machine.

`--by-gate` shards ONE remix's per-remix half by gate instead: every gate
of `make verify-remix` (plus `make cycles`) is its own job, each shard
restores the remix's image with `make bus` before its job, and the wall
is the longest gate rather than the whole list. The gates never read one
another's results; they only ever shared out/. The image-stage module
gates boot the card verify_set stages (TEMPO BUS): their job stages it
itself (`verify_set.py --stage-only`) and runs on its own shard. The job list mirrors
the `verify-remix` recipe and refuses to run when the two name different
scripts.
"""
import argparse
import contextlib
import fcntl
import json
import os
import pathlib
import queue
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import gate_cache  # noqa: E402
import gate_ledger  # noqa: E402
import card_retention  # noqa: E402
from contextlib import ExitStack
import slots  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
SKIP = re.compile(r"^\s*(?:\[SKIP\]|SKIP:)")
# --modules: the module keys a change touched. Set, a remix's half runs its
# floor and the module gates of what those keys reach (module_gates.reached)
SCOPE = None


def git(*args, cwd=ROOT, check=True):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if check and r.returncode:
        # CalledProcessError's message omits git's own, which is what says why
        print(f"check_shards: git {' '.join(args)} failed ({r.returncode}): {r.stderr.strip()}",
              file=sys.stderr, flush=True)
        raise subprocess.CalledProcessError(r.returncode, r.args, r.stdout, r.stderr)
    return r


@contextlib.contextmanager
def _worktree_lock():
    """One `git worktree add` or `remove` at a time against this repository.
    The shards, refhash's trees and reach's overlap tree are created by
    different processes and threads at once, and `git worktree add` failed
    with status 128 in CI when they overlapped. flock on a file in the git
    common directory: every open file description conflicts, threads and
    processes alike, and every worktree of the repository shares it."""
    common = pathlib.Path(subprocess.check_output(
        ["git", "rev-parse", "--git-common-dir"], cwd=ROOT, text=True).strip())
    common = (ROOT / common).resolve()
    with open(common / "octabam-worktree.lock", "a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def host_arch():
    """The machine's own architecture for CMAKE_OSX_ARCHITECTURES. Under
    Rosetta (an Intel-Homebrew python3, /usr/local/bin) os.uname().machine
    says x86_64 and the port then runs translated: 1.27x slower to the
    handoff, 1.75x on DSP frames (measured 6 Oct 2026, every shard of a
    reach run). Darwin asks the kernel, which answers the same under
    Rosetta; elsewhere uname is the answer."""
    machine = os.uname().machine
    if sys.platform == "darwin":
        r = subprocess.run(["sysctl", "-n", "hw.optional.arm64"], capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip() == "1":
            return "arm64"
    return machine


def shard_ok(path):
    """A registered worktree of this repository at `path`."""
    if not (path / ".git").is_file():
        return False
    r = git("worktree", "list", "--porcelain", check=False)
    return f"worktree {path.resolve()}" in r.stdout.splitlines()


def local_submodule_update():
    """`git submodule update --init` for a shard that clones each submodule
    from the copy this tree already holds, not from GitHub: 16 clones took
    41 s from GitHub and 3 s from here (27 Oct 2026; a CI run's shards were
    ready in 38-50 s). The URLs are per-command (-c): nothing is written to
    the shared git config. A submodule this tree has not cloned keeps its URL."""
    gitdir = pathlib.Path(git("rev-parse", "--absolute-git-dir").stdout.strip())
    names = [line.split()[0][len("submodule."):-len(".path")]
             for line in git("config", "-f", ".gitmodules", "--get-regexp", r"^submodule\..*\.path$",
                             check=False).stdout.splitlines()]
    cmd = ["git", "-c", "protocol.file.allow=always"]
    for name in names:
        if (gitdir / "modules" / name).is_dir():
            cmd += ["-c", f"submodule.{name}.url={gitdir / 'modules' / name}"]
    return cmd + ["submodule", "update", "--init"]


def make_shard(path, log, fresh=False, port=True):
    """A detached worktree of HEAD with this tree's uncommitted changes, the
    shared toolchain links, the stock slice, its submodules and the port
    from the store (`port=False`: none) -- created, or refreshed when one is
    already there."""
    keep = shard_ok(path) and not fresh
    if not keep:
        with _worktree_lock():
            _remove_shard(path)
            git("worktree", "add", "--detach", str(path), "HEAD")
    else:
        # Drop the previous run's applied diff and untracked copies, then
        # move to this tree's HEAD.
        for args in (("reset", "--hard", "--quiet"), ("clean", "-fdq"),
                     ("checkout", "--detach", "--quiet", git("rev-parse", "HEAD").stdout.strip())):
            git(*args, cwd=path)
    diff = subprocess.run(["git", "diff", "HEAD", "--binary", "--ignore-submodules=all"],
                          cwd=ROOT, capture_output=True, check=True).stdout
    if diff.strip():
        subprocess.run(["git", "apply", "--binary"], cwd=path, input=diff, check=True)
    for rel in git("ls-files", "--others", "--exclude-standard", "-z").stdout.split("\0"):
        if rel and (ROOT / rel).is_file():
            (path / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / rel, path / rel)
    for name in ("vendor", ".venv"):
        if (ROOT / name).exists() and not (path / name).exists():
            os.symlink(os.path.realpath(ROOT / name), path / name)
    out = path / "out"
    if keep:
        # No gate may read a previous run's artifact; the port build and
        # the stock slice are the two things worth keeping.
        for child in out.iterdir() if out.is_dir() else ():
            if child.name not in ("emu", "raw"):
                shutil.rmtree(child, ignore_errors=True) if child.is_dir() else child.unlink()
    (out / "raw").mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "out/raw/section_3_MAIN_OS.bin", out / "raw/section_3_MAIN_OS.bin")
    # The port from the store (tools/emu/port_store.py): built once per
    # source state for every worktree and shard, copied in (until 12 Oct
    # 2026 each new shard ran its own cmake build, ~40 s each).
    # port=False: a tree that only builds images (refhash's scratch trees)
    cmds = [local_submodule_update()]
    if port:
        cmds += [[sys.executable, "tools/emu/port_store.py", "install"],
                 ["./out/emu/ot_emu", "--image", "out/raw/section_3_MAIN_OS.bin"]]
    with log.open("w") as f:
        f.write(f"# {'refreshed' if keep else 'created'} {path}\n")
        for cmd in cmds:
            f.write(f"$ {' '.join(cmd)}\n")
            f.flush()
            r = subprocess.run(cmd, cwd=path, stdout=f, stderr=subprocess.STDOUT, env=clean_env())
            if r.returncode and "protocol.file.allow=always" in cmd:
                f.write("# a local clone failed: from the URLs\n$ git submodule update --init\n")
                f.flush()
                r = subprocess.run(["git", "submodule", "update", "--init"], cwd=path, stdout=f,
                                   stderr=subprocess.STDOUT, env=clean_env())
            if r.returncode:
                raise SystemExit(f"check_shards: {' '.join(cmd)} failed in {path} ({r.returncode}): {log}")


def _remove_shard(path):
    if path.exists():
        git("worktree", "remove", "--force", str(path), check=False)
        shutil.rmtree(path, ignore_errors=True)
    git("worktree", "prune", check=False)


def remove_shard(path):
    with _worktree_lock():
        _remove_shard(path)


def clean_env():
    env = dict(os.environ)
    for var in ("MAKEFLAGS", "MFLAGS", "MAKEOVERRIDES"):
        env.pop(var, None)
    # every shard builds from this tree's memo (tools/remix/pack.CACHE)
    env.setdefault("OCTABAM_CACHE", str(ROOT / "out/cache"))
    # the project as the Makefile finds it: a gate job runs its script
    # directly, outside make, and the set gates SKIP without one
    project = gate_cache.project_dir()
    if project and not env.get("OT_PROJECT"):
        env["OT_PROJECT"] = str(project)
    return env


def run_remix(shard, remix, logdir, deps=None, owner=None):
    log = logdir / f"{remix}.log"
    t0 = time.monotonic()
    k = None
    rc = 0
    with slots.slot(f"check-remix {remix}") as env_slot, log.open("w") as f:
        env = clean_env()
        if owner:
            env["OCTABAM_CARD_LOCK"] = owner.env["OCTABAM_CARD_LOCK"]
        env.update({k: v for k, v in env_slot.items() if k == "OCTABAM_SLOT"})
        argv = ["make", "check-remix", f"REMIX={remix}"] + ([f"MODULES={','.join(SCOPE)}"] if SCOPE else [])
        try:
            with card_retention.Gate(shard, f"check-remix {remix}", env) as cards:
                if deps is not None:
                    k, cached = lookup(shard, remix, "check-remix", [argv], remix_scripts(remix), deps, f, cards.env)
                    if cached:
                        return dict(remix=remix, rc=0, seconds=time.monotonic() - t0, skips=cached.get("skips", []),
                                    log=log, cached=cached)
                rc = subprocess.run(argv, cwd=shard, stdout=f, stderr=subprocess.STDOUT,
                                    env=cards.env, pass_fds=cards.pass_fds).returncode
                f.flush()
                text = log.read_text(errors="replace")
                cards.finish(rc == 0 and not any(SKIP.match(l) for l in text.splitlines()) and "[FAIL]" not in text,
                             include_modified=True)
        except card_retention.RetentionError as exc:
            f.write(f"[FAIL] card retention: {exc}\n")
            rc = 2
    text = log.read_text(errors="replace")
    skips = [l.strip() for l in text.splitlines() if SKIP.match(l)]
    res = dict(remix=remix, rc=rc, seconds=time.monotonic() - t0, skips=skips, log=log)
    if rc:
        gate_ledger.record("check-remix", remix, gate_ledger.first_fail(text), shard)
    if rc == 0 and k:
        gate_cache.store(k, dict(remix=remix, job="check-remix", seconds=res["seconds"], skips=skips))
    return res


FAIL_LINE = re.compile(r"\[FAIL\]|FAILED|Traceback|Error\b|error:|\*\*\*", re.I)


def failure_excerpt(text, fails=30, tail=40):
    """What a failed job's log says about why: its failure lines (first `fails`)
    and its last `tail` lines, in log order, each once."""
    lines = text.splitlines()
    keep = {i for i, l in enumerate(lines) if FAIL_LINE.search(l)}
    keep = set(sorted(keep)[:fails]) | set(range(max(0, len(lines) - tail), len(lines)))
    return [lines[i] for i in sorted(keep)]


def make_text():
    return (ROOT / "Makefile").read_text()


def job_scripts(cmds):
    """The repo scripts a job's commands run: tools/... arguments, and the
    scripts in the recipe of each `make <target>`."""
    sys.path.insert(0, str(ROOT / "tools/verify"))
    from reach import recipe_scripts  # noqa: E402
    out = set()
    for cmd in cmds:
        if cmd and cmd[0] == "make":
            for t in cmd[1:]:
                if "=" not in t:
                    out |= recipe_scripts(make_text(), t)
            continue
        for a in cmd:
            m = re.search(r"(tools/\S+\.py)$", a)
            if m:
                out.add(m.group(1))
    return out


def remix_scripts(remix_name):
    """Every script `make check-remix` runs for the remix: the recipes of
    bus, cycles and verify-remix, and every gate its modules declare."""
    sys.path.insert(0, str(ROOT / "tools")); import toolpath  # noqa: E402,F401
    from remix import registry  # noqa: E402
    scripts = job_scripts([["make", "bus", "cycles", "verify-remix"]])
    for m in registry.selected(registry.remix(remix_name)):
        scripts |= {g.script for g in getattr(m, "gates", ())}
    return scripts


def lookup(shard, remix, job, cmds, scripts, deps, f, env):
    """Build the remix's image in the shard and look the job up: (key,
    the cached record or None). The build's output goes to the job's log."""
    f.write(f"$ make bus REMIX={remix}\n"); f.flush()
    r = subprocess.run(["make", "bus", f"REMIX={remix}"], cwd=shard, stdout=f, stderr=subprocess.STDOUT, env=env)
    if r.returncode:
        return None, None
    flat = [a for cmd in cmds for a in cmd]
    k = gate_cache.key(shard, remix, job, flat, scripts, deps, env)
    hit = gate_cache.lookup(k)
    if hit:
        f.write(f"gate_cache: a pass of {remix}:{job} at {hit.get('head', '?')} ({hit.get('when', '?')}, "
                f"{hit.get('seconds', 0):.0f} s), same image and inputs: not run (key {k[:12]})\n")
        for skip in hit.get("skips", []):
            f.write(skip + "\n")
    return k, hit


def remix_jobs(remix_name, shard):
    """The per-remix half as independent jobs: (name, [argv, ...], env,
    {recipe scripts the job stands for}). Mirrors `make verify-remix` +
    `make cycles`; `check_recipe` refuses drift."""
    sys.path.insert(0, str(ROOT / "tools")); import toolpath  # noqa: E402,F401
    from remix import registry  # noqa: E402
    import module_gates  # noqa: E402
    py = sys.executable
    venv = shard / ".venv/bin/python3"       # the shard links ROOT's .venv
    has_venv = (ROOT / ".venv/bin/python3").exists()
    PY = str(venv) if has_venv else py        # the Makefile's $(PY)
    env = {"REMIX": remix_name, "BUILD": os.environ.get("BUILD", "0")}
    V = "tools/verify"
    def job(name, cmds, *scripts):
        return (name, cmds, env, set(scripts))
    jobs = [
        job("cycles", [["make", "cycles", f"REMIX={remix_name}"]]),
        job("dirty-state", [[py, f"{V}/verify_dirty_state.py", remix_name]], f"{V}/verify_dirty_state.py"),
        job("init-regs", [[py, f"{V}/verify_init_regs.py", remix_name]], f"{V}/verify_init_regs.py"),
        job("dram-boot", [[py, f"{V}/verify_dram_boot.py"]], f"{V}/verify_dram_boot.py"),
    ]
    for name in ("labels", "mode_names", "hidden"):
        # as the Makefile: SKIP without the .venv, and the job still stands for the script
        jobs.append(job(name.replace("_", "-"), [[str(venv), f"{V}/verify_{name}.py", remix_name]] if has_venv
                        else [["echo", f"  [SKIP] {name}: no .venv (make emu-setup)"]], f"{V}/verify_{name}.py"))
    remix = registry.remix(remix_name)
    # once=False: a once-per-run gate runs in the shared half (module_gates
    # --shared), as `make check-remix`'s --remix-only leaves it out; until
    # 11 Oct 2026 a split remix ran verify_kits here as well (625-1,172 s)
    selected = registry.selected(remix)
    mine = None
    if SCOPE:
        keys = module_gates.reached(set(SCOPE), selected)
        mine = {g.script for m in selected if m.key in keys for g in getattr(m, "gates", ())}
    for key, g in module_gates.collect(selected, "isolated", True, once=False):
        if mine is not None and g.script not in mine:
            continue
        # As `make verify-remix` runs them: module_gates.py under $(PY), so a
        # gate without `venv` inherits the driver's interpreter. The script
        # path is relative so it runs in the shard's own tree.
        cmd = module_gates.command(g, remix_name, root=ROOT)
        cmd[0] = cmd[0] if g.venv else PY
        cmd[1] = str(g.script)
        jobs.append(job(pathlib.Path(g.script).stem.removeprefix("verify_").replace("_", "-"), [cmd], f"{V}/module_gates.py"))
    jobs.append(job("menu", [[py, f"{V}/verify_menu.py"], [py, f"{V}/verify_replaces.py", "--image", remix_name]],
                    f"{V}/verify_menu.py", f"{V}/verify_replaces.py"))
    jobs.append(job("set", [[py, f"{V}/verify_set.py", remix_name]], f"{V}/verify_set.py"))
    # The image-stage module gates, one job each (until 4 Nov 2026 one `image`
    # job ran them serially: 2723 s of a 3031 s unit). A gate that boots the
    # card verify_set stages (TEMPO BUS) stages it first, in its own job;
    # verify_set --stage-only stages the same image and card without running.
    for _key, g in module_gates.collect(selected, "image"):
        if mine is not None and g.script not in mine:
            continue
        try:
            boots_card = "verify_set" in (ROOT / g.script).read_text(errors="replace")
        except OSError:
            boots_card = True       # unreadable: stage it, as the single job did
        stage = [[py, f"{V}/verify_set.py", remix_name, "--stage-only"]] if boots_card else []
        jobs.append(job("image:" + pathlib.Path(g.script).stem.removeprefix("verify_").replace("_", "-"),
                        stage + [[PY, f"{V}/module_gates.py", remix_name, "--stage", "image", "--only-script", str(g.script)]],
                        f"{V}/module_gates.py"))
    jobs.append(job("usb", [[py, f"{V}/verify_usb.py"]], f"{V}/verify_usb.py"))
    # reach.SPLIT_EXTRA_UNITS: a gate that runs only in its own unit, with a generated project
    from reach import SPLIT_EXTRA_UNITS  # noqa: E402
    for name, (module, command) in SPLIT_EXTRA_UNITS.get(remix_name, {}).items():
        if SCOPE is None or module in SCOPE:
            argv = shlex.split(command)
            jobs.append(job(name, [[PY, *argv[1:]]], *[a for a in argv if a.startswith("tools/")]))
    return jobs


def pick_jobs(jobs, only, skip, known=None):
    """`jobs` (remix_jobs) cut to the named ones, or without the skipped
    ones. A name that is no job is refused: a renamed gate would otherwise
    fall out of the part that ran it, and into neither. `known` is every
    job name the remix has: with --modules, `jobs` holds only the reached
    modules' jobs, and a name of another module's job (plocks-p2 under
    --modules BRAIN) is a job that is not in this cut, not a missing one."""
    have = {j[0] for j in jobs}
    unknown = sorted((set(only) | set(skip)) - (known or have))
    if unknown:
        raise SystemExit(f"check_shards: no gate job {', '.join(unknown)} (have: {', '.join(sorted(known or have))})")
    return [j for j in jobs if (not only or j[0] in only) and j[0] not in skip]


def all_job_names(remix_name, shard):
    """Every gate job name of the remix, whatever --modules cut the run to."""
    global SCOPE
    scope, SCOPE = SCOPE, None
    try:
        return {j[0] for j in remix_jobs(remix_name, shard)}
    finally:
        SCOPE = scope


def choose_split(remixes, spec, times, jobs):
    """The remixes to run as gate jobs: named, none, or (auto) a remix run
    alone, and those whose last recorded time would set the wall time;
    with no record, none."""
    if spec == "none":
        return set()
    if spec != "auto":
        return {r for r in spec.split(",") if r in remixes}
    if len(remixes) == 1:
        return set(remixes)
    known = {r: times[r] for r in remixes if r in times}
    if len(known) == len(remixes):
        floor = max(300.0, sum(known.values()) / jobs)
        return {r for r, s in known.items() if s > floor}
    return set()


def check_recipe(jobs):
    """Every script the Makefile's verify-remix recipe runs is in the job
    list (module_gates.py stands for the gates it runs)."""
    sys.path.insert(0, str(ROOT / "tools/verify"))
    from reach import recipe_scripts  # noqa: E402
    recipe = recipe_scripts((ROOT / "Makefile").read_text(), "verify-remix")
    named = set().union(*(scripts for _n, _c, _e, scripts in jobs))
    # The serial recipe's timed card wrapper is replaced by run_job's own
    # card retention around each isolated job.
    named.update({"tools/verify/step.py", "tools/verify/card_retention.py"})
    missing = recipe - named
    if missing:
        raise SystemExit(f"check_shards: verify-remix runs {sorted(missing)} and the by-gate job list does not; "
                         f"add the job (check_shards.remix_jobs)")


def run_job(shard, remix, job, logdir, deps=None, owner=None):
    name, cmds, env_add, scripts = job
    log = logdir / f"{name.replace(':', '_')}.log"
    t0 = time.monotonic()
    rc = 0
    k = None
    with slots.slot(f"{remix}:{name}") as env_slot, log.open("w") as f:
        env = clean_env()
        env.update(env_add)
        if owner:
            env["OCTABAM_CARD_LOCK"] = owner.env["OCTABAM_CARD_LOCK"]
        env.update({x: v for x, v in env_slot.items() if x == "OCTABAM_SLOT"})
        try:
            with card_retention.Gate(shard, f"{remix}:{name}", env) as cards:
                if deps is not None:
                    k, cached = lookup(shard, remix, name, cmds, job_scripts(cmds) | scripts, deps, f, cards.env)
                    if cached:
                        return dict(remix=name, rc=0, seconds=time.monotonic() - t0, skips=cached.get("skips", []),
                                    log=log, cached=cached)
                for cmd in ([] if k else [["make", "bus", f"REMIX={remix}"]]) + cmds:
                    f.write(f"$ {' '.join(cmd)}\n")
                    f.flush()
                    rc = subprocess.run(cmd, cwd=shard, stdout=f, stderr=subprocess.STDOUT,
                                        env=cards.env, pass_fds=cards.pass_fds).returncode
                    if rc:
                        break
                f.flush()
                text = log.read_text(errors="replace")
                cards.finish(rc == 0 and not any(SKIP.match(l) for l in text.splitlines()) and "[FAIL]" not in text,
                             include_modified=True)
        except card_retention.RetentionError as exc:
            f.write(f"[FAIL] card retention: {exc}\n")
            rc = 2
    text = log.read_text(errors="replace")
    skips = [l.strip() for l in text.splitlines() if SKIP.match(l)]
    res = dict(remix=name, rc=rc, seconds=time.monotonic() - t0, skips=skips, log=log)
    if rc:
        gate_ledger.record(f"job:{name}", remix, gate_ledger.first_fail(text), shard)
    if rc == 0 and k:
        gate_cache.store(k, dict(remix=remix, job=name, seconds=res["seconds"], skips=skips))
    return res


def times_path(root=ROOT):
    """The recorded job durations, shared by every worktree of the
    repository (gate_cache.store_dir's neighbour)."""
    return gate_cache.store_dir(root).parent / "octabam-gate-times.json"


def read_times(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def write_times(path, run):
    """Merge this run's durations into the shared record: under an flock,
    so two runs finishing together keep both, and by an atomic replace, so
    a reader never sees half a file."""
    import fcntl
    import tempfile
    try:
        with open(path.with_suffix(".lock"), "a+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            times = read_times(path)
            times.update({k: round(v, 1) for k, v in run.items()})
            fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".")
            with os.fdopen(fd, "w") as f:
                f.write(json.dumps(dict(sorted(times.items())), indent=1) + "\n")
            os.replace(tmp, path)
    except OSError:
        pass


def status_of(res):
    if res["rc"]:
        return f"FAILED ({res['rc']})"
    return "cached" if res.get("cached") else "ok"


def main(argv=None):
    try:
        with ExitStack() as owners:
            return _main(argv, owners)
    except card_retention.RetentionError as exc:
        print(f"[FAIL] card retention: {exc}", file=sys.stderr)
        return 2


def _main(argv, owners):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("remixes", nargs="+")
    ap.add_argument("--jobs", type=int, default=4, help="worktrees at a time")
    ap.add_argument("--shards", type=pathlib.Path, default=ROOT / "out/shards")
    ap.add_argument("--keep", action="store_true", help="(the default since 28 Sep 2026; kept for callers)")
    ap.add_argument("--fresh", action="store_true", help="recreate the shards instead of refreshing the kept ones")
    ap.add_argument("--rm", action="store_true", help="remove the shards after the run")
    ap.add_argument("--by-gate", action="store_true",
                    help="one remix: its per-remix half as one job per gate over the shards")
    ap.add_argument("--no-cache", action="store_true",
                    help="run every job (tools/verify/gate_cache.py; OCTABAM_GATE_CACHE=0 does the same)")
    ap.add_argument("--modules", default="",
                    help="comma-separated module keys a change touched: each remix runs its floor and the "
                         "module gates of what they reach (module_gates.reached); unset, every gate")
    ap.add_argument("--split", default="auto",
                    help="auto (the default): split the remixes that would set the wall time into gate jobs; "
                         "none; or a comma-separated list")
    ap.add_argument("--only-jobs", default="",
                    help="one remix: run only these comma-separated gate jobs (as gate jobs, whatever --split says)")
    ap.add_argument("--skip-jobs", default="",
                    help="one remix: run every gate job but these (as gate jobs, whatever --split says)")
    a = ap.parse_args(argv)
    only_jobs = [j for j in a.only_jobs.split(",") if j]
    skip_jobs = [j for j in a.skip_jobs.split(",") if j]
    if (only_jobs or skip_jobs) and (len(set(a.remixes)) != 1 or a.by_gate):
        sys.exit("check_shards: --only-jobs and --skip-jobs take exactly one remix, without --by-gate")
    # reach runs the shared gates in ROOT while this coordinator dispatches
    # jobs to separate shard worktrees. Own the coordinator's logs/schedule,
    # not ROOT's card output; each shard still takes its normal card lock.
    owners.enter_context(card_retention.Gate(ROOT, "check_shards", snapshot_cards=False,
                                            scope="shard-coordinator"))
    global SCOPE
    SCOPE = sorted(k for k in a.modules.split(",") if k) or None
    remixes = list(dict.fromkeys(a.remixes))
    if not (ROOT / "out/raw/section_3_MAIN_OS.bin").is_file():
        sys.exit("check_shards: out/raw/section_3_MAIN_OS.bin is missing (make os && make recon)")
    if a.by_gate:
        if len(remixes) != 1:
            sys.exit("check_shards: --by-gate takes exactly one remix")
        gate_jobs = remix_jobs(remixes[0], a.shards / "0")
        check_recipe(gate_jobs)
    shared_times = times_path()
    times = read_times(shared_times)
    split = set()
    if only_jobs or skip_jobs:
        split = set(remixes)
    elif not a.by_gate and a.jobs > 1:
        split = choose_split(remixes, a.split, times, a.jobs)
    if a.by_gate:
        work = [("gate", remixes[0], j) for j in gate_jobs]
    else:
        work = []
        for r in remixes:
            if r in split:
                gj = remix_jobs(r, a.shards / "0")
                check_recipe(gj)
                gj = pick_jobs(gj, only_jobs, skip_jobs, all_job_names(r, a.shards / "0"))
                work += [("gate", r, j) for j in gj]
            else:
                work.append(("remix", r, None))
        # longest first (the last recorded times; unknown last, in the given order)
        est = lambda w: times.get(w[1] if w[0] == "remix" else f"{w[1]}:{w[2][0]}", -1.0)
        work.sort(key=est, reverse=True)
    jobs = max(1, min(a.jobs, len(work)))
    a.shards.mkdir(parents=True, exist_ok=True)
    logdir = ROOT / "out/check_shards" / (remixes[0] if a.by_gate else "")
    logdir.mkdir(parents=True, exist_ok=True)
    for r in split:
        (ROOT / "out/check_shards" / r).mkdir(parents=True, exist_ok=True)
    shards = [a.shards / str(i) for i in range(jobs)]
    # Own every shard before setup; keep ownership between jobs and through
    # --rm. Another driver (even from a different root) cannot refresh it.
    leases = [owners.enter_context(card_retention.Gate(s, "check_shards setup", snapshot_cards=False))
              for s in shards]

    what = (f"{len(work)} gates of {remixes[0]}" if a.by_gate else f"{len(remixes)} remixes"
            + (f" ({', '.join(sorted(split))} split into gate jobs)" if split else ""))
    print(f"check_shards: {what} over {jobs} shards under {a.shards} "
          f"({'refreshing kept shards' if all(shard_ok(s) for s in shards) and not a.fresh else 'setup: worktree + submodules + port build each'})", flush=True)
    t_setup = time.monotonic()
    errors = []
    deps = None
    if not a.no_cache and gate_cache.enabled():
        # the tools/ graph once (the shards are this tree's HEAD plus its
        # diff), and the registry loaded before the worker threads use it
        sys.path.insert(0, str(ROOT / "tools/verify"))
        import reach  # noqa: E402
        from remix import registry  # noqa: E402
        deps = reach.scan_deps(ROOT)
        registry.modules()

    def setup(i):
        try:
            make_shard(shards[i], a.shards / f"{i}.setup.log", fresh=a.fresh)
        except (SystemExit, subprocess.CalledProcessError, OSError) as exc:
            errors.append(str(exc))
    threads = [threading.Thread(target=setup, args=(i,)) for i in range(jobs)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    if errors:
        sys.exit("check_shards: " + "; ".join(errors))
    print(f"check_shards: shards ready in {time.monotonic() - t_setup:.0f} s", flush=True)

    todo = queue.Queue()
    for w in work:
        todo.put(w)
    results = {}
    lock = threading.Lock()

    def worker(i):
        while True:
            try:
                item = todo.get_nowait()
            except queue.Empty:
                return
            kind, rname, job = item
            if kind == "gate":
                res = run_job(shards[i], rname, job, ROOT / "out/check_shards" / rname, deps, owner=leases[i])
                remix = job[0] if a.by_gate else f"{rname}:{job[0]}"
            else:
                remix = rname
                res = run_remix(shards[i], remix, logdir, deps, owner=leases[i])
            res["shard"] = i
            status = status_of(res)
            with lock:
                results[remix] = res
                print(f"check_shards: {status:12} {res['seconds']:6.0f} s  {remix:20} shard {i}"
                      + (f"  {len(res['skips'])} SKIP" if res["skips"] else ""), flush=True)
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(jobs)]
    t0 = time.monotonic()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    wall = time.monotonic() - t0

    names = [w[2][0] if a.by_gate else (w[1] if w[0] == "remix" else f"{w[1]}:{w[2][0]}") for w in work]
    # the durations for the next run's split and order: every job by its
    # key ("remix" or "remix:gate"), and a split remix's total
    run = {}
    for n, r in results.items():
        if r.get("cached"):
            continue            # a cache hit is not the job's duration
        key = f"{remixes[0]}:{n}" if a.by_gate else n
        run[key] = r["seconds"]
    for rname in ({remixes[0]} if a.by_gate else () if only_jobs or skip_jobs else split):
        parts = [s for k, s in run.items() if k.startswith(rname + ":")]
        if parts and not any(r.get("cached") for n, r in results.items()
                             if (f"{remixes[0]}:{n}" if a.by_gate else n).startswith(rname + ":")):
            run[rname] = sum(parts)
    write_times(shared_times, run)
    print(f"\ncheck_shards: results ({wall:.0f} s wall, {sum(r['seconds'] for r in results.values()):.0f} s of "
          f"{'gate' if a.by_gate else 'remix'} time)")
    for remix in names:
        r = results[remix]
        status = status_of(r)
        print(f"  {status:12} {r['seconds']:6.0f} s  {remix:20} {r['log'].relative_to(ROOT)}"
              + (f"  (pass at {r['cached'].get('head', '?')}, {r['cached'].get('seconds', 0):.0f} s)" if r.get("cached") else ""))
        for s in r["skips"]:
            print(f"               {s}")
    for remix in names:
        r = results[remix]
        if r["rc"]:
            print(f"\ncheck_shards: {remix} failed (exit {r['rc']}); the failure lines and the last lines of "
                  f"{r['log'].relative_to(ROOT)}:")
            for l in failure_excerpt(r["log"].read_text(errors="replace")):
                print(f"  | {l}")
    if a.rm:
        for s in shards:
            remove_shard(s)
    hits = sum(1 for r in results.values() if r.get("cached"))
    if hits:
        print(f"check_shards: {hits} of {len(results)} {'gates' if a.by_gate else 'jobs'} cached "
              f"(tools/verify/gate_cache.py: the same image and inputs passed before; --no-cache runs them)")
    bad = [r for r in results.values() if r["rc"]]
    unit = "gates" if a.by_gate else ("jobs" if split else "remixes")
    if bad:
        print(f"check_shards: {len(bad)} of {len(results)} {unit} failed")
        return 1
    print(f"check_shards: every {'gate of ' + remixes[0] if a.by_gate else 'remix'} passed"
          + ("" if a.by_gate else " its per-remix half"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
