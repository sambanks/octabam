#!/usr/bin/env python3
"""Gate results keyed by their inputs, shared by every worktree of the repository.

    python3 tools/verify/gate_cache.py key <remix> <job> [script ...]   # the key, in the current tree
    python3 tools/verify/gate_cache.py list                              # the cached passes, newest first
    python3 tools/verify/gate_cache.py clear

`check_shards.py` (and so `make reach RUN=1`) looks a job up after the
job's `make bus` and skips it on a hit: a rebase that leaves a remix's image
and a gate's inputs as they were reruns nothing. Only passes are stored.

The key is a sha256 over:
  - the built image (out/mainos_bus.bin) after `make bus REMIX=<remix>`;
  - the content of every file the job's scripts reach in the tools/ graph
    (reach.scan_deps: imports and the paths the code runs or reads), the
    Makefile, pyproject.toml and uv.lock;
  - every tracked file under the remix's directory and under the directory
    of each module it carries (gates render module sources themselves), and
    the manifest of every module (the registry loads all of them: 27 Oct
    2026, a trace of dlstub, dlwrap, menu and labels read 52 manifests of
    modules the remix does not carry that the key did not cover), and the
    data files in tools/remix/ (stock_labels.json: opened by a path the
    import graph does not see);
  - the port's source digest (reach.port_digest) and the host architecture;
  - dsp_asm and dsp_host, by content (the binary is not the source:
    AGENTS.md);
  - the project the set gates load (OT_PROJECT, else ~/.octabam_project):
    every file's path, size and mtime;
  - the .venv's interpreter (its resolved path), or none;
  - BUILD, OT_BANK, the job's name and argv.

What the key cannot see: a file a gate reads that is not in the graph (a
path built at run time from pieces), and anything outside the repository
other than the toolchain and the project above. `OCTABAM_GATE_CACHE=0`
(`make reach ... CACHE=0`) runs every job.

The store is <git common dir>/octabam-gate-cache/<key>.json, so a pass in
one worktree is a hit in another on the same machine. A pass with [SKIP]
lines replays them; the machine's own reasons to skip (no .venv, no
project) are in the key.
"""
import hashlib
import json
import os
import pathlib
import platform
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401

ROOT = pathlib.Path(__file__).resolve().parents[2]
ALWAYS = ("Makefile", "pyproject.toml", "uv.lock", "tools/toolpath.py")
TOOLCHAIN = ("vendor/dsp56300/build/source/dsp_host/dsp_asm", "vendor/dsp56300/build/source/dsp_host/dsp_host")


def enabled():
    return os.environ.get("OCTABAM_GATE_CACHE", "1") != "0"


def store_dir(root=ROOT):
    r = subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
                       cwd=root, capture_output=True, text=True, check=True)
    return pathlib.Path(r.stdout.strip()) / "octabam-gate-cache"


def closure(scripts, deps):
    """The scripts and every file they reach in the tools/ graph."""
    seen, todo = set(), [s for s in scripts if s]
    while todo:
        p = todo.pop()
        if p in seen:
            continue
        seen.add(p)
        todo.extend(deps.get(p, ()))
    return seen


def tracked(root, *dirs):
    """The tracked files under `dirs`, less the Markdown: a README under a
    module or a remix is read by verify_docs and the site build, which are
    their own CI jobs, and by no gate (4 Nov 2026: a README edit moved the
    key of every job of the remix). No `dirs`, no files (`git ls-files --`
    alone lists the whole tree)."""
    if not dirs:
        return []
    r = subprocess.run(["git", "ls-files", "-z", "--", *dirs], cwd=root, capture_output=True, text=True, check=True)
    return [p for p in r.stdout.split("\0") if p and not p.endswith(".md")]


def project_dir():
    p = os.environ.get("OT_PROJECT", "")
    if not p:
        f = pathlib.Path.home() / ".octabam_project"
        p = f.read_text().strip() if f.is_file() else ""
    return pathlib.Path(p).expanduser() if p else None


def project_stamp(path):
    """Every file's path, size and mtime: a project holds samples, and an
    edit on the card or in the port changes the mtime."""
    if path is None or not path.is_dir():
        return "none"
    # A project tools/hw/ot_fresh.py made (or copied from its cache) carries
    # the key of what made it, next to the project: the same inputs, the same
    # project, whatever the files' times (a restored cache has new ones).
    marker = path.parent / "fresh.key"
    if marker.is_file():
        h = hashlib.sha256()
        for f in sorted(path.rglob("*")):
            if f.is_file():
                h.update(f"{f.relative_to(path)}\0{f.stat().st_size}\n".encode())
        return f"fresh:{marker.read_text().strip()}:{h.hexdigest()}"
    h = hashlib.sha256()
    for f in sorted(path.rglob("*")):
        if f.is_file():
            st = f.stat()
            h.update(f"{f.relative_to(path)}\0{st.st_size}\0{st.st_mtime_ns}\n".encode())
    return f"{path.resolve()}:{h.hexdigest()}"


def file_digest(path):
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
    except OSError:
        return "missing"
    return h.hexdigest()


def inputs(root, remix, scripts, deps):
    """The repository files a job's key covers, relative to `root`."""
    from remix import registry  # noqa: E402
    files = set(ALWAYS) | closure(scripts, deps)
    # the shard is this tree's HEAD plus its diff, so the registry here
    # names the same files
    rdir = registry.remix_dir(remix)
    dirs = [rdir.relative_to(registry.ROOT).as_posix()] if rdir else [f"remixes/{remix}.py"]
    dirs += [f"modules/{m.name}" for m in registry.selected(registry.remix(remix))]
    files |= set(tracked(root, *dirs))
    files |= set(tracked(root, "modules/*/manifest.py", "tools/remix/*.json"))
    return files


def key(root, remix, job, argv, scripts, deps=None, env=None):
    """The job's key in the tree at `root` (a shard, or this tree), after
    `make bus REMIX=<remix>` there, for a job run with `env` (the project
    is the job's OT_PROJECT, not this process's); None when the image is
    missing."""
    env = os.environ if env is None else env
    import reach  # noqa: E402  (tools/verify; the graph and the port digest)
    root = pathlib.Path(root)
    image = root / "out/mainos_bus.bin"
    if not image.is_file():
        return None
    deps = reach.scan_deps(root) if deps is None else deps
    files = inputs(root, remix, scripts, deps)
    h = hashlib.sha256()

    def put(label, value):
        h.update(label.encode()); h.update(b"\0"); h.update(str(value).encode()); h.update(b"\n")
    put("v", 1)
    put("remix", remix)
    put("job", job)
    put("argv", json.dumps([pathlib.Path(a).name if os.path.isabs(a) else a for a in argv]))
    put("image", file_digest(image))
    for f in sorted(files):
        put(f, file_digest(root / f))
    put("port", reach.port_digest(root / "tools/emu/ot_emu"))
    put("arch", platform.machine() + "/" + platform.system())
    for t in TOOLCHAIN:
        put(t, file_digest(root / t))
    venv = root / ".venv/bin/python3"
    put("venv", os.path.realpath(venv) if venv.exists() else "none")
    project = env.get("OT_PROJECT", "")
    put("project", project_stamp(pathlib.Path(project).expanduser() if project else None))
    for var in ("BUILD", "OT_BANK"):
        put(var, env.get(var, ""))
    return h.hexdigest()


# Trees a gate's scratch image is built from, beyond its own module's directory.
BUILD_TREES = ("dsp", "tools/build", "tools/remix", "tools/harness")
STOCK_SLICE = "out/raw/section_3_MAIN_OS.bin"


def build_files(root, deps):
    """The tracked files of BUILD_TREES a scratch image can depend on: every
    file that is not Python (sources, tables, data: read by paths the graph
    may not see), and the Python the build reaches from reach.BUILD_ROOTS,
    the closure reach itself calls the build. A Python file the build does
    not reach is a tool or a gate (selftest, the harness probes): the gate's
    own closure covers it when the gate uses it (4 Nov 2026: main's
    one-line edit of tools/remix/selftest.py moved the key of every shared
    module gate, 1356 s rerun for nothing)."""
    import reach  # noqa: E402
    built = closure(reach.BUILD_ROOTS, deps)
    return {f for f in tracked(root, *BUILD_TREES) if not f.endswith(".py") or f in built}


def shared_key(root, name, argv, scripts, module_dirs, deps=None, env=None):
    """The key of a gate that takes no remix and builds its own scratch image
    (module_gates --shared): no image or remix in it. It covers the gate's
    script closure, BUILD_TREES, the directories in `module_dirs` (the gate's
    module and the modules it reaches), the manifests, the stock OS slice
    the scratch image is built from, the port, the toolchain, the venv, the
    project and BUILD/OT_BANK."""
    env = os.environ if env is None else env
    import reach  # noqa: E402
    root = pathlib.Path(root)
    deps = reach.scan_deps(root) if deps is None else deps
    files = set(ALWAYS) | closure(scripts, deps)
    # no global manifest glob (inputs() has one): a module's manifest is in its directory, and
    # another module's edit cannot change this gate's scratch image (4 Nov 2026: three
    # unrelated manifests moved the key of OCTA303 and MORPH)
    files |= set(tracked(root, *module_dirs))
    files |= build_files(root, deps)
    h = hashlib.sha256()

    def put(label, value):
        h.update(label.encode()); h.update(b"\0"); h.update(str(value).encode()); h.update(b"\n")
    put("v", 2)
    put("shared", name)
    put("argv", json.dumps([pathlib.Path(a).name if os.path.isabs(a) else a for a in argv]))
    put("stock", file_digest(root / STOCK_SLICE))
    for f in sorted(files):
        put(f, file_digest(root / f))
    put("port", reach.port_digest(root / "tools/emu/ot_emu"))
    put("arch", platform.machine() + "/" + platform.system())
    for t in TOOLCHAIN:
        put(t, file_digest(root / t))
    venv = root / ".venv/bin/python3"
    put("venv", os.path.realpath(venv) if venv.exists() else "none")
    project = env.get("OT_PROJECT", "")
    put("project", project_stamp(pathlib.Path(project).expanduser() if project else None))
    for var in ("BUILD", "OT_BANK"):
        put(var, env.get(var, ""))
    return h.hexdigest()


def lookup(k, root=ROOT):
    if not k or not enabled():
        return None
    try:
        return json.loads((store_dir(root) / f"{k}.json").read_text())
    except (OSError, ValueError):
        return None


def store(k, record, root=ROOT):
    if not k or not enabled():
        return
    d = store_dir(root)
    d.mkdir(parents=True, exist_ok=True)
    head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=root, capture_output=True, text=True).stdout.strip()
    rec = dict(record, head=head, when=time.strftime("%Y-%m-%d %H:%M"))
    tmp = d / f".{k}.{os.getpid()}"
    tmp.write_text(json.dumps(rec, indent=1) + "\n")
    tmp.replace(d / f"{k}.json")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] not in ("key", "list", "clear"):
        print(__doc__)
        return 2
    d = store_dir()
    if argv[0] == "key":
        print(key(ROOT, argv[1], argv[2], [], argv[3:]))
    elif argv[0] == "list":
        recs = sorted(d.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True) if d.is_dir() else []
        for p in recs:
            r = json.loads(p.read_text())
            print(f"{r.get('when', '?'):16}  {r.get('head', '?'):10} {r.get('seconds', 0):6.0f} s  "
                  f"{r.get('remix', '?')}:{r.get('job', '?')}  {p.stem[:12]}")
    else:
        n = 0
        for p in d.glob("*.json") if d.is_dir() else ():
            p.unlink(); n += 1
        print(f"gate_cache: {n} entries removed from {d}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
