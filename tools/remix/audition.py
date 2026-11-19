"""Render any effect on a source wav, knobs addressed by their manifest names.

The one audition entry point for the remixer: busverb goes through
tools/harness/render_reverb.py (wet extraction, per-mode image cache,
ring-out tail), everything else through tools/harness/send_probe.py --wav.

Which image a render runs against (an id absent from the image aliases to
SEND and renders a plausible dry passthrough):

  busverb   render_reverb's own fingerprinted engine cache.
  busdelay  the DEV hatch dump (out/dsp/mem_dev_A.mem), rebuilt here when
             stale with `make render-delay`'s build line.
  inserts    a per-insert scratch dump (out/dsp/_audition_<name>_A.mem, and
             _B.mem for payload B) built from a two-module remix (the insert +
             SEND). The scratch
             build writes out/mainos_bus.bin, so the user's image is saved
             and restored around it: the emulator view boots that file.

send_probe's SEND-alias guard backstops all of this: a wrong dump dies
instead of rendering silence-shaped success.

    python3 tools/remix/audition.py <module-name> <wav> [NAME=VAL ...]
"""

from __future__ import annotations

import datetime
import json
import os
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401  (every tools/ dir on sys.path)
from remix import registry, rig, stock  # noqa: E402

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
    newest = (ROOT / "tools/build/build_bus.py").stat().st_mtime
    for p in (ROOT / "modules").rglob("*"):
        if p.is_file() and "__pycache__" not in p.parts:
            newest = max(newest, p.stat().st_mtime)
    return newest


def _build(env):
    r = subprocess.run([sys.executable, "tools/build/build_bus.py"], cwd=ROOT,
                       env={**os.environ, **env}, capture_output=True,
                       text=True)
    if r.returncode != 0:
        tail = (r.stdout + r.stderr).strip().splitlines()
        _die("build failed: " + (tail[-1] if tail else "(no output)"))


def _dump(mem, payload="A"):
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401  (every tools/ dir on sys.path)
    import dsp_modmap
    mem.parent.mkdir(parents=True, exist_ok=True)
    dsp_modmap.dumpmem(IMAGE.read_bytes(), [payload, str(mem)])


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
    """A dump whose payload A really CONTAINS this insert. Payload B's dump
    of the same scratch image goes beside it (_B.mem), for the identity
    gate's core-1 renders (tools/verify/verify_ident.py)."""
    mem = ROOT / f"out/dsp/_audition_{mod.name}_A.mem"
    mem_b = mem.with_name(f"_audition_{mod.name}_B.mem")
    if mem.exists() and mem_b.exists() and mem.stat().st_mtime > _newest_input_mtime():
        return mem
    log(f"building a scratch image containing {mod.name} ...")
    send = registry.by_name("send")
    # SEND refuses the FX2 row of a module that owns an allocator buffer (its
    # scratch lies in the slots), so such a module is auditioned alone with
    # the firmware's NONE as the fallback.
    alone = bool(mod.claims is not None and mod.claims.stock_instance_buffer
                 and not mod.claims.fx1_only)
    modules = f'("{mod.key}",)' if alone else f'("{mod.key}", "{send.key}")'
    fallback = "NONE" if alone else send.key
    scratch = ROOT / "remixes/_audition.py"
    scratch.write_text(
        f'"""_audition -- scratch: {mod.name}{"" if alone else " + SEND"}, for the remixer.\n\n'
        f'Written and removed by tools/remix/audition.py.\n"""\n\n'
        f'from remix.schema import Remix\n\n'
        f'REMIX = Remix(\n'
        f'    name="_audition",\n'
        f'    doc="audition scratch",\n'
        f'    modules={modules},\n'
        f'    fallback="{fallback}",\n'
        f')\n')
    keep = IMAGE.read_bytes() if IMAGE.exists() else None
    try:
        _build({"REMIX": "_audition", "XBUS": "1", "SPEC": "1"})
        _dump(mem)
        _dump(mem_b, "B")
    finally:
        scratch.unlink(missing_ok=True)
        for junk in (ROOT / "remixes/__pycache__").glob("_audition*"):
            junk.unlink(missing_ok=True)
        if keep is not None:
            IMAGE.write_bytes(keep)      # the emulator boots this file
    return mem


def _ensure_stock_mem(log=print):
    """A dump of the PRISTINE image's payload A: every stock effect's code
    and dispatch exactly as the unit ships them, independent of whatever
    remix is currently built. (A DEV build takes CHORUS's module as a fourth
    donor, and every build null-stubs the three reverbs, so no built image
    is the right source for this.)"""
    mem = ROOT / "out/dsp/_stock_A.mem"
    if mem.exists() and mem.stat().st_mtime > stock.STOCK_IMAGE.stat().st_mtime:
        return mem
    log("dumping the stock image's payload A ...")
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401  (every tools/ dir on sys.path)
    import dsp_modmap
    mem.parent.mkdir(parents=True, exist_ok=True)
    dsp_modmap.dumpmem(stock.STOCK_IMAGE.read_bytes(), ["A", str(mem)])
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
    if mod.name == "tapeecho":
        _die("Tape Echo now runs on the CPU. This DSP-only audition would render "
             "dry audio; run tools/verify/verify_tapeecho_cpu.py instead.")
    if rig.category(mod) == rig.STOCK and mod.key in stock.NO_DSP:
        _die(f"{mod.key} runs on the ColdFire (DMA over SDRAM rings), not the "
             f"DSP -- its DSP dispatch is stock's passthrough stub, so there "
             f"is nothing here to render. It works from its chooser row on "
             f"the unit.")
    source = pathlib.Path(source)
    OUT.mkdir(parents=True, exist_ok=True)
    stem = f"{label + '_' if label else ''}{source.stem}_{mod.name}"

    if mod.name == "busverb":
        sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401  (every tools/ dir on sys.path)
        import render_reverb
        mode = values.get("MODE", 2)
        base = OUT / stem
        argv = [sys.executable, "tools/harness/render_reverb.py", str(source),
                "--normalize", "--mode", str(mode), "-o", str(base)]
        if wet:
            argv.append("--wet")
        kmap = mod.knob_map()
        for name, v in values.items():
            slot = kmap[name]
            if name == "MODE":
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
    if mod.name == "busdelay":
        mem = _ensure_delay_mem(log)
        route = ["--layout", "DS"]        # SEND -> bus -> delay, the rig path
        tail = 3.0 if tail is None else tail
    elif mod.is_stock:
        mem = _ensure_stock_mem(log)
        route = ["--direct", "--pick", mod.harness.layout_char]
        tail = 1.0 if tail is None else tail
    else:
        mem = _ensure_insert_mem(mod, log)
        route = ["--direct", "--pick", mod.harness.layout_char]
        tail = 1.0 if tail is None else tail
    out = OUT / f"{stem}.wav"
    argv = [sys.executable, "tools/harness/send_probe.py", "--mem", str(mem),
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
