"""Can this machine build a remix at all? -- the every-remix sweeps' skip list.

`make verify` builds every remix (tools/verify/verify_replaces.py), and two
kinds of module cannot build on every machine for reasons that have nothing
to do with octabam's code:

  * a module whose sources are a git SUBMODULE that is not checked out
    (midi-scenes' upstream is a private repository; not everyone can fetch
    it), and
  * a module with an appended runtime (schema.Runtime -- Octakit), which is
    compiled from its author's sources and checked against the identities her
    recipe pins. That is measured byte-identical only with a BARE-METAL
    m68k-elf toolchain (Homebrew's, 9 Sep 2026). Ubuntu's m68k-linux-gnu
    toolchain, symlinked to the m68k-elf names, stops on runtime.S line 438
    ("value of fffffbbe too large for field of 1 byte", binutils 2.46,
    11 Sep 2026), so it is treated as absent.

`unbuildable(name)` names the reason, or returns None. It is for SWEEPS only:
a remix the caller named explicitly is always built, so `make bus REMIX=kits`
still fails loudly on a machine that cannot build it. A skip is never silent
-- every caller prints the remix and the reason.
"""

from __future__ import annotations

import functools
import pathlib
import re
import shutil
import subprocess

from remix import registry, runtime_build

ROOT = pathlib.Path(__file__).resolve().parents[2]


@functools.cache
def _submodule_paths() -> tuple[str, ...]:
    gm = ROOT / ".gitmodules"
    if not gm.exists():
        return ()
    return tuple(re.findall(r"^\s*path\s*=\s*(\S+)\s*$", gm.read_text(), re.M))


def missing_submodule(mod) -> str | None:
    """The first submodule under this module's directory that has no files."""
    here = f"modules/{mod.name}/"
    for path in _submodule_paths():
        if not path.startswith(here):
            continue
        d = ROOT / path
        if not d.is_dir() or not any(d.iterdir()):
            return (f"submodule {path} is not checked out "
                    f"(git submodule update --init {path})")
    return None


@functools.cache
def runtime_toolchain_problem() -> str | None:
    """Why a schema.Runtime cannot be built here, or None.

    Only a POSITIVE identification skips: an assembler whose version text
    names no target is left to build (and to fail loudly if it cannot)."""
    missing = [t for t in runtime_build.TOOLS if shutil.which(t) is None]
    if missing:
        return f"m68k-elf toolchain not installed ({', '.join(missing)})"
    try:
        out = subprocess.run(["m68k-elf-as", "--version"], capture_output=True,
                             text=True, timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    m = re.search(r"configured for a target of [`'](\S+?)'", out)
    if m and not re.fullmatch(r"m68k(-\w+)*-elf", m.group(1)):
        return (f"its runtime needs a bare-metal m68k-elf toolchain; "
                f"m68k-elf-as here targets {m.group(1)}")
    return None


def unbuildable(name: str) -> str | None:
    """Why remix `name` cannot be built on this machine, or None."""
    for mod in registry.selected(registry.remix(name)):
        if mod.is_stock:
            continue
        why = missing_submodule(mod)
        if why:
            return f"{mod.key}: {why}"
        if mod.runtime is not None:
            why = runtime_toolchain_problem()
            if why:
                return f"{mod.key}: {why}"
    return None
