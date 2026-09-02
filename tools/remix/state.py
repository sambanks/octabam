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
from remix.schema import NO_FALLBACK, on_the_bus  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
DONOR_WORDS = 2724          # per payload; build_bus.py prints the live figure
# The ColdFire cave: the firmware's zero run at 0x400d6b00..0x400d7c3c, which
# is where EVERYTHING a remix plants on the ColdFire lives -- the chooser
# list, the descriptor clones, the caves and the label formatters. The build
# reports what is LEFT of it, never the size, so the total is written down
# here and pinned against build_bus's own NEW_LIST/ZERO_RUN_END by
# tools/remix/selftest.py. Used is derived as CAVE_BYTES - free, which holds
# for both list placements: a long chooser list moves the reported ceiling
# down by exactly the 128 B the list then occupies.
CAVE_BYTES = 0x400d7c3c - 0x400d6b00
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
        # [(payload, total, used, free)] as the last build reported them.
        # TWO regions, one per payload -- see problems(). The TOTAL is read
        # from the build too rather than assumed to be DONOR_WORDS: a DEV
        # build takes CHORUS's module as well, so the size of the region is
        # a property of the build, not a constant of the firmware.
        self.regions: list[tuple[str, int, int, int]] = []
        # Which of PLATE/SPRING/DARK the last build LEFT ALONE, upper-cased
        # as the build names them. Empty until a build has reported.
        self.donors_kept: set[str] = set()
        # Bytes left in the ColdFire cave region and rows in the chooser, as
        # the last build reported them. None until one has.
        self.cave_free: int | None = None
        self.chooser_rows: int | None = None
        self.msg = "enter swaps · r hears it · ? for keys"
        # Per-MODULE knob values, so an effect's settings belong to the effect
        # rather than to a track. (The retired rig kept these per track, which
        # was the redundancy: one knob set per effect is what a remix means.)
        self.knobs: dict[str, dict[str, int]] = {}
        self.loaded_name = ""
        self.load_stock()

    # ---- the default: an unmodified unit --------------------------------
    def load_stock(self):
        """The chooser an UNMODIFIED unit shows: every stock FX2 effect, no
        modules of ours. The honest starting point -- you add to what the box
        already does rather than to somebody else's selection.

        ⚠️ IT BUILDS, since 2 Sep 2026 -- to A 0/2724 · B 0/2724, not one
        word placed, all three reverbs alive: the unit's own chooser rebuilt
        from our tables. It could not, until the fallback stopped having to
        be a module of ours; ids this selection does not implement now
        resolve to the firmware's own NONE (schema.NO_FALLBACK), which is
        what an unassigned track shows on a stock unit anyway. Until then
        the bench opened on a selection it had to apologise for.
        """
        from remix import stock
        self.sel = {m.key for m in stock.MODULES}
        self.order = [m.key for m in stock.MODULES]
        self.fallback = None
        self.loaded_name = "stock"
        self.msg = ("stock: the chooser an unmodified unit shows — "
                    "add modules from the left")

    # ---- selection ----------------------------------------------------
    def load(self, name):
        if not name:
            return
        r = registry.remix(name)
        self.sel = set(r.modules)
        self.order = list(r.modules)
        self.fallback = r.fallback
        self.loaded_name = name
        self.msg = f"loaded remix {name!r}"

    # ---- per-module knob values -----------------------------------------
    def knobs_for(self, mod) -> dict[str, int]:
        """This module's current knob values, seeded from its manifest
        defaults the first time it is asked for. Manifest defaults are the
        honest baseline -- a stale default polluted every shimmer measurement
        until Round 12."""
        from remix import rig
        if mod.key not in self.knobs:
            self.knobs[mod.key] = rig.default_knobs(mod)
        return self.knobs[mod.key]

    def toggle(self, key):
        if key in self.sel:
            self.sel.discard(key)
            self.order.remove(key)
            if self.fallback == key:
                self.fallback = None
        else:
            self.sel.add(key)
            self.order.append(key)

    def insert_at(self, key, i):
        """Add a module at a CHOSEN position. Chooser order is the panel's row
        order, so "which slot" is a real question and appending to the end is
        only ever one answer to it."""
        if key in self.sel:
            return
        self.sel.add(key)
        self.order.insert(max(0, min(len(self.order), i)), key)

    def swap(self, out_key, in_key):
        """Replace one entry with another IN ITS OWN SLOT.

        Composing an image is trading, not accumulating: the donor region is
        2,724 words and the chooser is a list somebody has to scroll, so
        putting something in generally means taking something out. Keeping
        the position is the whole point -- the row number IS the panel slot.
        """
        if out_key not in self.sel or in_key in self.sel:
            return False
        i = self.order.index(out_key)
        self.order[i] = in_key
        self.sel.discard(out_key)
        self.sel.add(in_key)
        if self.fallback == out_key:
            self.fallback = None
        return True

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
        """The fallback to use when none is set explicitly.

        THE FIRMWARE'S OWN NONE, whenever this selection has no bus. An
        unimplemented id then resolves to the descriptor a stock chooser
        carries at row 0 and to the payload's null stub -- an unassigned
        track is simply OFF, exactly as on an unmodified unit -- and it costs
        no words. That is the honest answer for an insert collection, which
        used to be made to carry SEND (215-250 words) for a bus client
        nothing in the image reads. See schema.NO_FALLBACK, which is also
        what refuses this beside a bus participant: with a server or a SEND
        in the image, an unassigned track running nothing would leave the
        rotation unflipped and the accumulators uncleared.

        With a bus, SEND is the safe catch-all -- aliasing to it makes the
        id a harmless dry passthrough rather than garbage -- so prefer it. If
        there is exactly one menu-bearing module, it is the only choice.
        Otherwise there is no safe automatic pick (any real effect would
        PROCESS the unknown id), so return None and let problems() ask.
        """
        if not any(on_the_bus(m) for m in self.selected):
            return NO_FALLBACK
        for k in self.order:
            if self.mods[k].name == "send" and self.mods[k].menu is not None:
                return k
        menu = [m.key for m in self.menu_modules]
        return menu[0] if len(menu) == 1 else None

    @property
    def eff_fallback(self):
        """What the build will actually use: the explicit choice if valid,
        else the intelligent default."""
        # NO_FALLBACK is not a module, so it is valid exactly when the
        # selection still has no bus participant -- otherwise it falls
        # through to the automatic pick, which will be SEND.
        if self.fallback == NO_FALLBACK:
            if not any(on_the_bus(m) for m in self.selected):
                return NO_FALLBACK
        elif self.fallback and self.fallback in self.sel \
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
        # THE WORD BUDGET IS NOT CHECKED HERE, deliberately. It used to be:
        # every module's words summed against ONE 2,724-word region. There
        # are TWO -- one per payload -- and SPEC=1 puts each server on its
        # own, so the sum is not a quantity the image has to fit. It read
        # chongbong, the SHIPPING remix, as "5130 words exceeds the 2724-word
        # donor region by 2406" when the truth was A 2650/74 free and B
        # 2719/5 free. The check was latent while the words were only known
        # after an explicit keypress; it became a permanent false alarm the
        # moment the workbench started measuring on every change.
        #
        # The build is the authority and it refuses per payload ("payload B:
        # RUNGS overruns the region (3599 > 2724 words)"), so an overrun
        # arrives as a build failure with the payload named. measure() keeps
        # the real per-payload numbers in self.regions.
        return out

    def forget_build(self):
        """Drop everything only a build can know. Called when the selection
        stops being buildable: these numbers describe the image you HAD, and
        a budget that silently belongs to two edits ago is worse than none."""
        self.regions = []
        self.cave_free = None
        self.chooser_rows = None
        self.donors_kept = set()

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
            # ⚠️ PARSE THE REPORT EVEN WHEN THE BUILD FAILED. Returning
            # here left every build-derived number -- the donor budget, the
            # cave, the rows, which reverbs survived -- holding the LAST
            # SUCCESSFUL build's values, so a failed selection showed the
            # budget of an image it was not. And the report is usually still
            # informative: a chooser-row refusal happens after the region
            # line is printed, so "726 used, 1998 free" is exactly the fact
            # that tells you the failure is not about space.
            #
            # forget_build() is the other half: when the parse yields
            # nothing, the fields go empty rather than stale.
            failed = r.returncode != 0
            words, regions, payload = {}, [], None
            kept, saw_donor_line = set(), False
            cave_free = rows = None
            for line in r.stdout.splitlines():
                m = re.match(r"\s{2}(\S.*?)\s+P:0x[0-9a-f]+\.\.0x[0-9a-f]+"
                             r"\s+\(\s*(\d+) words\)", line)
                if m and m.group(1).strip() in self.mods:
                    words[m.group(1).strip()] = int(m.group(2))
                m = re.match(r"-- payload (\w+) --", line.strip())
                if m:
                    payload = m.group(1)
                # There is one of these PER PAYLOAD, each its own 2,724-word
                # region. Keeping only the last was how the budget came to be
                # reported as a single pool.
                m = re.search(r"\((\d+) words\)\s+used (\d+)\s+FREE (\d+)",
                              line)
                if m and payload:
                    regions.append((payload, int(m.group(1)),
                                    int(m.group(2)), int(m.group(3))))
                # WHICH DONORS SURVIVED, from the build rather than
                # re-derived here. The three reverbs' code IS the donor
                # region and the build nulls a donor id only where words
                # actually landed, so "are they gone" is a question only the
                # placement can answer -- and the workbench used to assume
                # the answer was always yes.
                m = re.search(r"KEPT STOCK: (\S+)", line)
                if m:
                    kept |= {w.strip() for w in m.group(1).split("/")}
                m = re.search(r"(\d+) B of cave left", line)
                if m:
                    cave_free = int(m.group(1))
                m = re.search(r"chooser list = (\d+) entries", line)
                if m:
                    rows = int(m.group(1))
            self.words.update(words)
            self.words_from = note
            self.regions = regions
            # Both payloads report; a donor survives only if BOTH kept it.
            for line in r.stdout.splitlines():
                if "donor ids" in line:
                    saw_donor_line = True
                    if "KEPT STOCK:" not in line:
                        kept = set()
                        break
            self.donors_kept = kept if saw_donor_line else set()
            self.cave_free = cave_free
            self.chooser_rows = rows
            if failed:
                tail = (r.stdout + r.stderr).strip().splitlines()
                return False, (tail[-1] if tail else "build failed")
            if regions:
                return True, ("assembled: " + " · ".join(
                    f"{n} {u}/{t}" for n, t, u, _f in regions))
            return True, "assembled"
        finally:
            tmp.unlink(missing_ok=True)
            for junk in (ROOT / "remixes/__pycache__").glob("_tui_scratch*"):
                junk.unlink(missing_ok=True)

    def measure_every(self, note=None):
        """Word counts for EVERY module of ours, not just the selection.

        The build only reports what it PLACED, so a module you have not added
        had no number and the pane said "build to measure" -- which is
        circular: the cost is what you want to know BEFORE adding it. Each
        module is assembled once beside SEND, which is what audition.py
        already does for an insert, and one takes ~0.19 s.

        Cached on disk against the newest module source, so it is paid once
        per session and again only when something is edited.
        """
        import json
        newest = 0.0
        for f in (ROOT / "modules").rglob("*"):
            if f.is_file() and "__pycache__" not in f.parts:
                newest = max(newest, f.stat().st_mtime)
        cache = ROOT / "out/_audition/words.json"
        try:
            have = json.loads(cache.read_text())
            if have.get("stamp") == newest:
                self.words.update(have["words"])
                return
        except Exception:                            # noqa: BLE001
            pass
        got = {}
        for key, m in self.mods.items():
            if m.is_stock or m.dsp is None or key in got:
                continue
            mods = (key,) if key == "SEND" else (key, "SEND")
            tmp = ROOT / "remixes/_words.py"
            tmp.write_text(
                f'"""_words -- scratch: one module, to read its word count."""\n'
                f'from remix.schema import Remix\n'
                f'REMIX = Remix(name="_words", doc="one module", '
                f'modules={mods!r}, fallback="SEND")\n')
            try:
                r = subprocess.run(
                    [sys.executable, "tools/build_bus.py"], cwd=ROOT,
                    env={**os.environ, "REMIX": "_words", "XBUS": "1",
                         "SPEC": "1"}, capture_output=True, text=True)
                for line in r.stdout.splitlines():
                    mm = re.match(r"\s{2}(\S.*?)\s+P:0x[0-9a-f]+\.\.0x[0-9a-f]+"
                                  r"\s+\(\s*(\d+) words\)", line)
                    if mm and mm.group(1).strip() in self.mods:
                        got[mm.group(1).strip()] = int(mm.group(2))
            finally:
                tmp.unlink(missing_ok=True)
                for junk in (ROOT / "remixes/__pycache__").glob("_words*"):
                    junk.unlink(missing_ok=True)
        self.words.update(got)
        try:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps({"stamp": newest, "words": got},
                                        indent=2) + "\n")
        except OSError:
            pass

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
