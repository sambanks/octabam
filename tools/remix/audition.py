"""Render ANY effect on a source wav, knobs addressed by their MANIFEST names.

The one audition entry point for the workbench: chonverb goes through
tools/render_reverb.py (wet extraction, per-mode image cache, ring-out tail),
everything else through tools/send_probe.py --wav. The caller never learns
which -- it says "render warpfold with MIX=127 on this wav" and gets a path.

WHICH IMAGE A RENDER RUNS AGAINST is the part that has burned sessions
(12 + 31 Aug 2026: an id absent from the image aliases to SEND and renders a
plausible dry passthrough). So:

  chonverb   render_reverb's own fingerprinted engine cache.
  bongdelay  the DEV hatch dump (out/dsp/mem_dev_A.mem) -- rebuilt here when
             stale, exactly `make render-delay`'s build line.
  inserts    a per-insert scratch dump (out/dsp/_audition_<name>_A.mem) built
             from a two-module remix (the insert + SEND), because the user's
             shipping remix need not contain the insert being trialled. The
             scratch build necessarily writes out/mainos_bus.bin, so the
             user's image is saved and restored around it -- the emulator
             view boots that file and must not silently boot a scratch.

send_probe's SEND-alias guard backstops all of this: a wrong dump dies
instead of rendering silence-shaped success.

Headless smoke (also the CI-of-one):

    python3 tools/remix/audition.py <module-name> <wav> [NAME=VAL ...]
"""

from __future__ import annotations

import datetime
import json
import os
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from remix import registry, rig  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "out/_audition"
DEV_MEM = ROOT / "out/dsp/mem_dev_A.mem"
IMAGE = ROOT / "out/mainos_bus.bin"


def _die(msg):
    raise RuntimeError(f"audition: {msg}")


def _newest_input_mtime():
    """Newest mtime among everything a build reads that we could go stale
    against. Coarse on purpose: a false 'stale' costs one build (~seconds),
    a false 'fresh' costs a wrong render."""
    newest = (ROOT / "tools/build_bus.py").stat().st_mtime
    for p in (ROOT / "modules").rglob("*"):
        if p.is_file() and "__pycache__" not in p.parts:
            newest = max(newest, p.stat().st_mtime)
    return newest


def _build(env):
    r = subprocess.run([sys.executable, "tools/build_bus.py"], cwd=ROOT,
                       env={**os.environ, **env}, capture_output=True,
                       text=True)
    if r.returncode != 0:
        tail = (r.stdout + r.stderr).strip().splitlines()
        _die("build failed: " + (tail[-1] if tail else "(no output)"))


def _dump(mem):
    sys.path.insert(0, str(ROOT / "tools"))
    import dsp_modmap
    mem.parent.mkdir(parents=True, exist_ok=True)
    dsp_modmap.dumpmem(IMAGE.read_bytes(), ["A", str(mem)])


def _ensure_delay_mem(log=print):
    """`make render-delay`'s build line, run only when the dump is stale."""
    if DEV_MEM.exists() and DEV_MEM.stat().st_mtime > _newest_input_mtime():
        return DEV_MEM
    log("building the DELAY hatch (DEV=1 XBUS=1) ...")
    _build({"DEV": "1", "XBUS": "1"})
    if not DEV_MEM.exists():
        _die(f"build succeeded but {DEV_MEM} was not written")
    return DEV_MEM


def _ensure_insert_mem(mod, log=print):
    """A dump whose payload A really CONTAINS this insert."""
    mem = ROOT / f"out/dsp/_audition_{mod.name}_A.mem"
    if mem.exists() and mem.stat().st_mtime > _newest_input_mtime():
        return mem
    log(f"building a scratch image containing {mod.name} ...")
    send = registry.by_name("send")
    scratch = ROOT / "remixes/_audition.py"
    scratch.write_text(
        f'"""_audition -- scratch: {mod.name} + SEND, for the workbench.\n\n'
        f'Written and removed by tools/remix/audition.py.\n"""\n\n'
        f'from remix.schema import Remix\n\n'
        f'REMIX = Remix(\n'
        f'    name="_audition",\n'
        f'    doc="audition scratch",\n'
        f'    modules=("{mod.key}", "{send.key}"),\n'
        f'    fallback="{send.key}",\n'
        f')\n')
    keep = IMAGE.read_bytes() if IMAGE.exists() else None
    try:
        _build({"REMIX": "_audition", "XBUS": "1", "SPEC": "1"})
        _dump(mem)
    finally:
        scratch.unlink(missing_ok=True)
        for junk in (ROOT / "remixes/__pycache__").glob("_audition*"):
            junk.unlink(missing_ok=True)
        if keep is not None:
            IMAGE.write_bytes(keep)      # the emulator boots this file
    return mem


def _journal(entry):
    """Append one event to the audition journal, out/_audition/log.jsonl.

    The journal is how a listening session becomes addressable: "this
    sounds boxy" plus the tail of this file is a full repro -- track,
    effect, source, wet flag, every knob. One JSON object per line,
    newest last; renders and A/B marks both land here."""
    OUT.mkdir(parents=True, exist_ok=True)
    entry = {"t": datetime.datetime.now().isoformat(timespec="seconds"),
             **entry}
    with open(OUT / "log.jsonl", "a") as f:
        f.write(json.dumps(entry) + "\n")


def render(key, values, source, wet=False, tail=None, label="", log=print):
    """Render module `key` over `source` with manifest-named knob `values`.

    -> the output wav path. Raises RuntimeError with a said-out-loud reason
    on anything that would otherwise produce a wrong-but-plausible file.
    """
    mod = registry.by_key(key)
    if rig.category(mod) == rig.SYSTEM:
        _die(f"{mod.name} is not an effect")
    source = pathlib.Path(source)
    OUT.mkdir(parents=True, exist_ok=True)
    stem = f"{label + '_' if label else ''}{source.stem}_{mod.name}"

    if mod.name == "chonverb":
        sys.path.insert(0, str(ROOT / "tools"))
        import render_reverb
        mode = values.get("MODE", 2)
        base = OUT / stem
        argv = [sys.executable, "tools/render_reverb.py", str(source),
                "--normalize", "--mode", str(mode), "-o", str(base)]
        if wet:
            argv.append("--wet")
        kmap = mod.knob_map()
        for name, v in values.items():
            slot = kmap[name]
            if slot == 7:
                continue                  # MODE went in via --mode
            argv += ["-p", f"{render_reverb.PARAMS[slot][0]}={v}"]
        r = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True)
        if r.returncode != 0:
            tl = (r.stdout + r.stderr).strip().splitlines()
            _die("render_reverb failed: " + (tl[-1] if tl else "(no output)"))
        got = base.with_name(f"{base.name}_{render_reverb.MODES[mode]}.wav")
        if not got.exists():
            _die(f"render_reverb reported success but {got.name} is missing")
        _journal({"event": "render", "label": label, "effect": mod.name,
                  "source": source.name, "wet": wet, "knobs": values,
                  "out": got.name})
        return got

    # Everything else goes through send_probe --wav.
    if mod.name == "bongdelay":
        mem = _ensure_delay_mem(log)
        route = ["--layout", "DS"]        # SEND -> bus -> delay, the rig path
        tail = 3.0 if tail is None else tail
    else:
        mem = _ensure_insert_mem(mod, log)
        route = ["--direct", "--pick", mod.harness.layout_char]
        tail = 1.0 if tail is None else tail
    out = OUT / f"{stem}.wav"
    argv = [sys.executable, "tools/send_probe.py", "--mem", str(mem),
            "--in", str(source), "--wav",
            str(out.relative_to(ROOT)), "--tail", str(tail),
            "--label", f"audition {mod.name}"] + route
    for name, v in values.items():
        # --set=NAME=VAL as ONE token: a knob name may begin with '-'
        # (the delay's -VRB, SEND's -DEL) and a separate argument would
        # parse as an option.
        argv += [f"--set={name}={v}"]
    r = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        tl = (r.stdout + r.stderr).strip().splitlines()
        _die("send_probe failed: " + (tl[-1] if tl else "(no output)"))
    if not out.exists():
        _die(f"send_probe reported success but {out.name} is missing")
    _journal({"event": "render", "label": label, "effect": mod.name,
              "source": source.name, "wet": False, "knobs": values,
              "out": out.name})
    return out


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    mod = registry.by_name(argv[0])
    values = rig.default_knobs(mod)
    for spec in argv[2:]:
        n, _, v = spec.partition("=")
        if n.upper() not in values:
            sys.exit(f"audition: {mod.name} has no knob {n!r} -- "
                     f"{' '.join(sorted(values))}")
        values[n.upper()] = int(v)
    try:
        got = render(mod.key, values, argv[1])
    except RuntimeError as e:
        sys.exit(str(e))
    print(got)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
