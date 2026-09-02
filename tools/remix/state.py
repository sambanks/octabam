"""The composer's model: a module selection and what it costs to build.

Extracted verbatim from the curses workbench (tools/remix/tui.py, retired by
the track-centric app) so the Textual frontend and any headless caller share
one model. Everything here is pure: no UI import, no terminal assumption.

The word counts are the one thing the model cannot know without assembling,
so `measure()` assembles: it writes a scratch remix and runs the real build,
because the placement order, the payload gating and the per-module
substitutions all affect the count and only the build knows them.
"""

from __future__ import annotations

import os
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from remix import ledger, registry  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
DONOR_WORDS = 2724          # per payload; build_bus.py prints the live figure
BUILT_IMAGE = ROOT / "out/mainos_bus.bin"
# Stock top-level menu, to highlight what a patch adds (docs/MAINMENU.md).
STOCK_ROOTS = {"PROJECT", "SYSTEM", "CONTROL", "MIDI"}


class State:
    def __init__(self):
        self.mods = registry.modules()
        self.keys = sorted(self.mods)
        self.sel: set[str] = set()
        # Chooser ORDER. A remix's module list is ordered and that order is
        # the panel's row order, so the composer keeps it too -- the old set
        # alone wrote every saved remix alphabetically, which silently
        # reordered the chooser on save.
        self.order: list[str] = []
        self.fallback: str | None = None
        self.cursor = 0
        self.words: dict[str, int] = {}      # key -> words, from a real build
        self.words_from = ""                 # which remix produced them
        self.msg = "space toggles; w assembles for word counts; ? for keys"
        self.load("chongbong" if "chongbong" in registry.remix_names()
                  else (registry.remix_names() or [None])[0])

    # ---- selection ----------------------------------------------------
    def load(self, name):
        if not name:
            return
        r = registry.remix(name)
        self.sel = set(r.modules)
        self.order = list(r.modules)
        self.fallback = r.fallback
        self.msg = f"loaded remix {name!r}"

    def toggle(self, key):
        if key in self.sel:
            self.sel.discard(key)
            self.order.remove(key)
            if self.fallback == key:
                self.fallback = None
        else:
            self.sel.add(key)
            self.order.append(key)

    def move(self, key, delta):
        """Shift a selected module earlier (-1) or later (+1) in chooser order."""
        if key not in self.sel:
            self.msg = "select it first -- only selected modules have a row"
            return
        i = self.order.index(key)
        j = max(0, min(len(self.order) - 1, i + delta))
        self.order[i], self.order[j] = self.order[j], self.order[i]
        rows = [m.key for m in self.menu_modules]
        self.msg = (f"{self.mods[key].name} -> chooser row {rows.index(key)}"
                    if key in rows else "no menu entry: order is moot")

    @property
    def selected(self):
        """Selected modules in CHOOSER order (the remix's declared order)."""
        return [self.mods[k] for k in self.order]

    @property
    def menu_modules(self):
        """Selected modules that appear in the FX2 chooser, in panel order."""
        return [m for m in self.selected if m.menu is not None]

    def auto_fallback(self):
        """The fallback to use when none is set explicitly. SEND is the safe
        catch-all -- an unimplemented id aliased to it becomes a harmless dry
        passthrough, not garbage -- so prefer it; if there is exactly one
        menu-bearing module, it is the only choice. Otherwise there is no safe
        automatic pick (any real effect would PROCESS the unknown id), so
        return None and let problems() ask for an explicit choice.
        """
        for k in self.order:
            if self.mods[k].name == "send" and self.mods[k].menu is not None:
                return k
        menu = [m.key for m in self.menu_modules]
        return menu[0] if len(menu) == 1 else None

    @property
    def eff_fallback(self):
        """What the build will actually use: the explicit choice if valid,
        else the intelligent default."""
        if self.fallback and self.fallback in self.sel \
                and self.mods[self.fallback].menu is not None:
            return self.fallback
        return self.auto_fallback()

    @property
    def fallback_is_auto(self):
        return self.eff_fallback is not None and self.eff_fallback != self.fallback

    # ---- what the selection costs and whether it is legal ---------------
    def problems(self):
        """Everything that would stop this selection building, in one list.

        The collisions come from the ledger -- the same call the build makes,
        not a reimplementation. The rest are the two rules a remix has to
        satisfy that the ledger does not speak to.
        """
        out = list(ledger.check(self.selected))
        if not self.menu_modules:
            out.append("no module with a menu entry: nothing would be "
                       "selectable on the panel")
        if self.eff_fallback is None:
            out.append("no fallback and none can be picked automatically "
                       "(no SEND, and several effects) — press f to choose "
                       "which effect unimplemented ids alias to")
        # A module whose words we know, summed against the region it must fit.
        known = [k for k in self.sel if k in self.words]
        if known and len(known) == len([k for k in self.sel
                                        if self.mods[k].dsp is not None]):
            total = sum(self.words[k] for k in known)
            if total > DONOR_WORDS:
                out.append(f"{total} words exceeds the {DONOR_WORDS}-word "
                           f"donor region by {total - DONOR_WORDS}")
        return out

    # ---- the one thing that needs a real build --------------------------
    def measure(self, note):
        """Assemble this selection and keep the words the build reports.

        Writes a scratch remix rather than guessing: the placement order,
        the payload gating and the per-module substitutions all affect the
        count, and only the build knows them. The build report is API
        (verify_delay and friends parse it), which is why this can parse it.
        """
        if self.eff_fallback is None:
            return False, ("no fallback and none can be auto-picked — press "
                           "f to choose one")
        tmp = ROOT / "remixes/_tui_scratch.py"
        tmp.write_text(self.as_remix("_tui_scratch",
                                     "scratch selection from the remix TUI"))
        try:
            env = {**os.environ, "REMIX": "_tui_scratch",
                   "XBUS": "1", "SPEC": "1"}
            r = subprocess.run([sys.executable, "tools/build_bus.py"],
                               cwd=ROOT, env=env, capture_output=True,
                               text=True)
            if r.returncode != 0:
                tail = (r.stdout + r.stderr).strip().splitlines()
                return False, (tail[-1] if tail else "build failed")
            words, free = {}, None
            for line in r.stdout.splitlines():
                m = re.match(r"\s{2}(\S.*?)\s+P:0x[0-9a-f]+\.\.0x[0-9a-f]+"
                             r"\s+\(\s*(\d+) words\)", line)
                if m and m.group(1).strip() in self.mods:
                    words[m.group(1).strip()] = int(m.group(2))
                m = re.search(r"used (\d+)\s+FREE (\d+)", line)
                if m:
                    free = (int(m.group(1)), int(m.group(2)))
            self.words.update(words)
            self.words_from = note
            if free:
                return True, (f"assembled: {free[0]} words used, "
                              f"{free[1]} free in the donor region")
            return True, "assembled"
        finally:
            tmp.unlink(missing_ok=True)
            for junk in (ROOT / "remixes/__pycache__").glob("_tui_scratch*"):
                junk.unlink(missing_ok=True)

    # ---- scratch builds --------------------------------------------------
    def scratch_remix(self):
        """Write the live selection as the scratch remix and return its NAME,
        so `make bus`/`make check` can run the selection without saving it.
        The caller removes the file when the build is done (same contract as
        measure(), which inlines this dance for its own build).
        """
        tmp = ROOT / "remixes/_tui_scratch.py"
        tmp.write_text(self.as_remix("_tui_scratch",
                                     "scratch selection from the workbench"))
        return "_tui_scratch"

    def scratch_cleanup(self):
        (ROOT / "remixes/_tui_scratch.py").unlink(missing_ok=True)
        for junk in (ROOT / "remixes/__pycache__").glob("_tui_scratch*"):
            junk.unlink(missing_ok=True)

    # ---- saving ---------------------------------------------------------
    def as_remix(self, name, doc):
        mods = ", ".join(f'"{k}"' for k in self.order)
        fb = f'"{self.eff_fallback}"' if self.eff_fallback else "None"
        return (f'"""{name} -- {doc}\n\n'
                f'Written by the remix workbench. Edit freely: the docstring\n'
                f'is the only thing here a human is expected to improve.\n'
                f'"""\n\n'
                f'from remix.schema import Remix\n\n'
                f'REMIX = Remix(\n'
                f'    name="{name}",\n'
                f'    doc="{doc}",\n'
                f'    modules=({mods},),\n'
                f'    fallback={fb},\n'
                f')\n')
