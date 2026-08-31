#!/usr/bin/env python3
"""The remix workbench: compose a selection, see what it costs, build it.

    make remix          (or: python3 tools/remix/tui.py)

WHY THIS EXISTS. `make modules` prints the index and `make bus REMIX=<name>`
builds one, which is enough while there are two remixes and one author. It
stops being enough the moment a selection is a real choice: the things you
want to know before building -- do these modules collide, does the set fit
the donor region, what does the panel end up looking like -- are spread
across the ledger, the build report and the manifests, and the only way to
see them together was to run a build and read 200 lines of output.

So this is a composer, not a launcher. Toggle modules, and the panel on the
right answers those three questions continuously, from the same statements
the build reads (`registry`, `ledger`, and each module's manifest). Nothing
here re-derives a fact the build derives -- a second copy of the knob map or
the id table is precisely the defect the manifest was introduced to end.
The word counts are the one thing it cannot know without assembling, so it
assembles them: `w` runs a real build and keeps the reported figures.

CURSES, not a framework, because the repo has no runtime dependencies and
this is not worth acquiring one for.

KEYS
    up/down k j    move          space  toggle the module under the cursor
    a / n          all / none    f      make it the fallback
    l              load a remix  s      save the selection as a remix
    w              assemble and report words (a real build)
    b              build the image        c   make check
    e              boot the built image in the Tier-0 emulator (docs/EMU.md)
    v              source wav browser: preview + render through ChonVerb
    q              quit
"""

from __future__ import annotations

import curses
import os
import pathlib
import re
import shutil
import subprocess
import sys
import textwrap

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from remix import ledger, registry  # noqa: E402
import emu_bringup  # noqa: E402  (Tier-0 ColdFire emulator; docs/EMU.md)

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
        self.fallback = r.fallback
        self.msg = f"loaded remix {name!r}"

    def toggle(self, key):
        if key in self.sel:
            self.sel.discard(key)
            if self.fallback == key:
                self.fallback = None
        else:
            self.sel.add(key)

    @property
    def selected(self):
        return [self.mods[k] for k in self.keys if k in self.sel]

    @property
    def menu_modules(self):
        """Selected modules that appear in the FX2 chooser, in panel order."""
        return [m for m in self.selected if m.menu is not None]

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
        if self.fallback is None:
            out.append("no fallback: an id this image does not implement "
                       "would dispatch into whatever occupies its slot")
        elif self.fallback not in self.sel:
            out.append(f"fallback {self.fallback!r} is not in the selection")
        elif self.mods[self.fallback].menu is None:
            out.append(f"fallback {self.fallback!r} has no menu entry, so "
                       f"ids aliased to it would dispatch nowhere")
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
        if self.fallback is None or self.fallback not in self.sel:
            return False, ("set a fallback first (f on a selected module "
                           "with a menu entry) — the build needs one")
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

    # ---- saving ---------------------------------------------------------
    def as_remix(self, name, doc):
        mods = ", ".join(f'"{k}"' for k in self.keys if k in self.sel)
        fb = f'"{self.fallback}"' if self.fallback else "None"
        return (f'"""{name} -- {doc}\n\n'
                f'Written by tools/remix/tui.py. Edit freely: the docstring\n'
                f'is the only thing here a human is expected to improve.\n'
                f'"""\n\n'
                f'from remix.schema import Remix\n\n'
                f'REMIX = Remix(\n'
                f'    name="{name}",\n'
                f'    doc="{doc}",\n'
                f'    modules=({mods},),\n'
                f'    fallback={fb},\n'
                f')\n')


# ---- drawing ---------------------------------------------------------------
def draw(scr, st):
    scr.erase()
    h, w = scr.getmaxyx()
    if h < 12 or w < 76:
        scr.addstr(0, 0, "window too small (needs 76x12)"[:max(w - 1, 0)])
        scr.refresh()
        return
    left = min(46, w // 2)

    def put(y, x, s, attr=0, width=None):
        limit = (width if width is not None else w - x) - 1
        if 0 <= y < h and limit > 0:
            scr.addstr(y, x, s[:limit], attr)

    put(0, 0, " remix workbench ".ljust(w - 1), curses.A_REVERSE)

    # ---- module list --------------------------------------------------
    put(2, 0, "MODULES", curses.A_BOLD)
    y = 3
    for i, k in enumerate(st.keys):
        m = st.mods[k]
        on = k in st.sel
        mark = "x" if on else " "
        fb = "*" if st.fallback == k else " "
        wd = f"{st.words[k]:>5}w" if k in st.words else "     -"
        idtxt = f"0x{m.menu.fx2_id:02x}" if m.menu else " -- "
        line = f" [{mark}]{fb} {m.name:<11} {idtxt} {wd}"
        attr = curses.A_REVERSE if i == st.cursor else (
            curses.A_BOLD if on else curses.A_DIM)
        put(y, 0, line.ljust(left - 1), attr, left)
        y += 1

    y += 1
    put(y, 0, "REMIXES", curses.A_BOLD); y += 1
    names = registry.remix_names()
    put(y, 1, textwrap.shorten(" ".join(n for n in names
                                        if not n.startswith("_")),
                               left - 3, placeholder=" ..."), 0, left)

    # ---- the panel: what this selection IS ----------------------------
    x = left + 1
    for row in range(2, h - 3):
        put(row, left, "|", curses.A_DIM)
    ry = 2
    put(ry, x, "THIS SELECTION", curses.A_BOLD); ry += 2

    menu = st.menu_modules
    put(ry, x, f"panel: {len(menu)} entries" + (
        "" if menu else "  (nothing selectable!)")); ry += 1
    for i, m in enumerate(menu):
        star = " <- fallback" if m.key == st.fallback else ""
        put(ry, x + 2, f"{i}. {m.menu.fullname.decode('latin1'):<13}"
                       f"0x{m.menu.fx2_id:02x}{star}")
        ry += 1
    absent = [m for m in st.mods.values()
              if m.menu is not None and m.key not in st.sel]
    if absent and st.fallback:
        ry += 1
        put(ry, x, f"{len(absent)} absent id(s) alias to "
                   f"{st.mods[st.fallback].name}", curses.A_DIM); ry += 1

    # words
    ry += 1
    dsp = [m for m in st.selected if m.dsp is not None]
    known = [m for m in dsp if m.key in st.words]
    if known:
        total = sum(st.words[m.key] for m in known)
        partial = "" if len(known) == len(dsp) else \
                  f" ({len(known)}/{len(dsp)} measured)"
        put(ry, x, f"program: {total} of {DONOR_WORDS} words{partial}",
            curses.A_BOLD if total > DONOR_WORDS else 0); ry += 1
        bar_w = max(10, min(w - x - 2, 40))
        fill = min(bar_w, round(bar_w * total / DONOR_WORDS))
        put(ry, x, "[" + "#" * fill + "." * (bar_w - fill) + "]",
            curses.A_REVERSE if total > DONOR_WORDS else 0); ry += 1
        if st.words_from:
            put(ry, x, f"measured from: {st.words_from}", curses.A_DIM); ry += 1
    else:
        put(ry, x, "program: press w to assemble and measure",
            curses.A_DIM); ry += 1

    # problems -- the whole point
    ry += 1
    probs = st.problems()
    if probs:
        put(ry, x, f"WILL NOT BUILD ({len(probs)})", curses.A_BOLD); ry += 1
        for p in probs:
            for chunk in textwrap.wrap(p, max(20, w - x - 3))[:3]:
                put(ry, x + 1, chunk); ry += 1
    else:
        put(ry, x, "no LEDGER collisions -- this selection builds",
            curses.A_BOLD); ry += 1
        # ⚠️ NEVER let that read as "this selection is safe". The ledger does
        # not check the shared 64K window or the FX2 instance buffers, and
        # those are where the expensive overlaps have actually happened --
        # a delay based on the reverb's buffers, a bus scratch swept every
        # 16,384 samples. Modules that own memory say so in prose, so the
        # panel says which ones and lets the reader do the arithmetic the
        # tool cannot. Naming the specific claimants beats a generic
        # disclaimer, which is the kind of warning people learn to skip.
        put(ry, x, "not checked: the shared 64K window", curses.A_DIM)
        ry += 1
        put(ry, x, "(PLAN.md) -- see CLAUDE.md for who owns what",
            curses.A_DIM); ry += 1
        buffered = [m for m in st.selected
                    if getattr(m, "claims", None) is not None
                    and m.claims.owns_fx2_buffers]
        if buffered:
            ry += 1
            put(ry, x, f"{buffered[0].name} owns Y:0x4000-0xBFFF, so it "
                       f"must be", curses.A_DIM); ry += 1
            put(ry, x, "the only such module on its core", curses.A_DIM)
            ry += 1

    put(h - 2, 0, st.msg[:w - 1], curses.A_DIM)
    put(h - 1, 0, (" space toggle  f fallback  w words  b build  e emu  "
                   "v wavs  l load  s save  q quit").ljust(w - 1),
        curses.A_REVERSE)
    scr.refresh()


def prompt(scr, question):
    h, w = scr.getmaxyx()
    curses.echo()
    scr.addstr(h - 2, 0, (question + " ").ljust(w - 1), curses.A_REVERSE)
    scr.clrtoeol()
    try:
        s = scr.getstr(h - 2, len(question) + 1, 40).decode().strip()
    except Exception:
        s = ""
    curses.noecho()
    return s


def shell_out(scr, argv, env=None):
    """Drop out of curses to run a build, so its output is the real thing."""
    curses.endwin()
    print("\n$ " + " ".join(argv) + "\n")
    r = subprocess.run(argv, cwd=ROOT, env={**os.environ, **(env or {})})
    input("\n[enter] to return to the workbench ")
    scr.clear()
    curses.doupdate()
    return r.returncode


def _lcd(scr, draws, y0, x0, sel_label=""):
    """Draw captured (x,y,text) as a framed 128x64-proportioned LCD panel."""
    h, w = scr.getmaxyx()
    grid = emu_bringup.layout_screen(draws)
    width = 46

    def put(y, x, s, attr=0):
        if 0 <= y < h and 0 <= x < w - 1:
            scr.addstr(y, x, s[:w - x - 1], attr)
    put(y0 - 1, x0, "." + "-" * width + ".", curses.A_DIM)
    for i, line in enumerate(grid):
        put(y0 + i, x0, "|", curses.A_DIM)
        attr = (curses.A_REVERSE if sel_label and line.strip() == sel_label
                else 0)
        put(y0 + i, x0 + 1, line.ljust(width), attr)
        put(y0 + i, x0 + width + 1, "|", curses.A_DIM)
    put(y0 + len(grid), x0, "'" + "-" * width + "'", curses.A_DIM)
    return y0 + len(grid) + 1


def emu_view(scr, image):
    """Boot a built image in the Tier-0 emulator and NAVIGATE its firmware UI:
    the MAIN MENU (up/down/enter/back through real rendered screens) and the
    FX2 dials page, both drawn by the real firmware (docs/EMU.md). A patched-in
    entry shows up as the firmware would draw it. Booting also IS the no-flash
    gate: a cave that breaks early init faults here, not on the unit.
    """
    h, w = scr.getmaxyx()
    scr.erase()
    scr.addstr(0, 0, f" emulator: booting {image.name} ... ".ljust(w - 1),
               curses.A_REVERSE)
    scr.addstr(2, 2, "running the real firmware to the RTOS handoff (~4s)")
    scr.refresh()

    r = emu_bringup.boot(str(image))
    ok = r.clean
    roots = emu_bringup.menu_children(r) if r.uc and r.reached_handoff else []
    cursor = 0
    mode = "menu"          # "menu" or "fx2"

    def put(y, x, s, attr=0):
        if 0 <= y < h and 0 <= x < w - 1:
            scr.addstr(y, x, s[:w - x - 1], attr)

    while True:
        scr.erase()
        head = f" emulator — {image.name} — " + ("BOOTS CLEAN" if ok else "FAULT")
        put(0, 0, head.ljust(w - 1),
            curses.A_REVERSE | (0 if ok else curses.A_BOLD))
        put(1, 2, f"{r.instrs:,} instrs · {r.stopped}", curses.A_DIM)

        if not r.uc or not r.reached_handoff:
            put(4, 2, "emulator unavailable — run: make emu-setup"
                if not r.uc else "did not reach the RTOS handoff — a patch may "
                "have broken early init.", curses.A_BOLD)
        elif mode == "fx2":
            put(3, 2, "FX2 SETUP — the built remix's own effects & dials "
                      "(track 5):", curses.A_BOLD)
            _lcd(scr, emu_bringup.render_fx2(r), 6, 4)
            put(h - 3, 2, "the chooser lists THIS image's effects; the labels "
                          "are the FX2 param row.", curses.A_DIM)
        else:
            sel = roots[cursor][0] if roots else ""
            put(3, 2, "MAIN MENU — the firmware's own render "
                      f"(selected: {sel}):", curses.A_BOLD)
            draws = emu_bringup.render_menu(r, emu_bringup.MENU_ROOT_DESC, cursor)
            ny = _lcd(scr, draws, 6, 4, sel_label=sel)
            # the right LCD pane previews the selected category's submenu, as
            # on the unit; move the cursor to browse each one.
            added = [k[0] for k in roots if k[0] not in STOCK_ROOTS]
            if added:
                put(ny + 1, 2, "patched-in: " + ", ".join(added), curses.A_BOLD)

        keys = (" up/down browse categories   f FX2 dials   q back "
                "to workbench ") if mode == "menu" else \
               (" m back to menu   q back to workbench ")
        put(h - 1, 0, keys.ljust(w - 1), curses.A_REVERSE)
        scr.refresh()

        c = scr.getch()
        if c in (ord("q"), 27):
            return
        if mode == "fx2":
            if c in (ord("m"), ord("f")):
                mode = "menu"
            continue
        if c in (curses.KEY_DOWN, ord("j")) and roots:
            cursor = (cursor + 1) % len(roots)
        elif c in (curses.KEY_UP, ord("k")) and roots:
            cursor = (cursor - 1) % len(roots)
        elif c == ord("f"):
            mode = "fx2"


def _wav_sources():
    """Source WAVs to audition, test_audio first (Sam's preferred set)."""
    out = []
    for sub in ("test_audio", "demo_sources"):
        d = ROOT / "out" / sub
        if d.is_dir():
            for p in sorted(d.glob("*.wav")):
                out.append(p)
    return out


def wav_browser(scr):
    """Browse the project's source WAVs, preview them, and render one through
    ChonVerb (the DSP emulator) to hear the effect — the compose/build/hear
    loop, in the workbench. Playback is afplay (macOS); rendering shells out to
    tools/render_reverb.py.
    """
    have_afplay = shutil.which("afplay") is not None
    files = _wav_sources()
    cur, top = 0, 0
    wet = True
    msg = ("space/p preview · r render through ChonVerb · w wet/dry toggle"
           if have_afplay else "afplay not found — preview/playback disabled")
    h, w = scr.getmaxyx()

    def put(y, x, s, attr=0):
        if 0 <= y < h and 0 <= x < w - 1:
            scr.addstr(y, x, s[:w - x - 1], attr)

    while True:
        scr.erase()
        put(0, 0, " source wav browser ".ljust(w - 1), curses.A_REVERSE)
        put(1, 2, f"{len(files)} sources in out/test_audio + out/demo_sources"
                  f"   render: {'WET only' if wet else 'full (dry+wet)'}",
            curses.A_DIM)
        view_h = h - 5
        if cur < top:
            top = cur
        elif cur >= top + view_h:
            top = cur - view_h + 1
        for i in range(top, min(len(files), top + view_h)):
            p = files[i]
            kb = p.stat().st_size // 1024
            label = f"{p.parent.name}/{p.name}"
            put(3 + i - top, 2, f"{label:<48}{kb:>5} kB",
                curses.A_REVERSE if i == cur else 0)
        put(h - 2, 0, msg[:w - 1], curses.A_DIM)
        put(h - 1, 0, (" up/down  p preview  r render+play  w wet/dry  "
                       "q back ").ljust(w - 1), curses.A_REVERSE)
        scr.refresh()
        c = scr.getch()
        if c in (ord("q"), 27):
            return
        elif c in (curses.KEY_DOWN, ord("j")) and files:
            cur = min(len(files) - 1, cur + 1)
        elif c in (curses.KEY_UP, ord("k")) and files:
            cur = max(0, cur - 1)
        elif c == ord("w"):
            wet = not wet
        elif c in (ord("p"), ord(" ")) and files and have_afplay:
            shell_out(scr, ["afplay", str(files[cur])])
        elif c == ord("r") and files and have_afplay:
            src = files[cur]
            outp = ROOT / "out" / f"_browser_{src.stem}_chonverb.wav"
            argv = [sys.executable, "tools/render_reverb.py", str(src),
                    "--normalize", "-o", str(outp)]
            if wet:
                argv.append("--wet")
            rc = shell_out(scr, argv)
            if rc == 0 and outp.exists():
                shell_out(scr, ["afplay", str(outp)])
                msg = f"rendered + played {outp.name}"
            else:
                msg = "render failed — see output above"


def main(scr):
    curses.curs_set(0)
    st = State()
    while True:
        draw(scr, st)
        try:
            c = scr.getch()
        except KeyboardInterrupt:
            return
        k = st.keys[st.cursor] if st.keys else None
        if c in (ord("q"), 27):
            return
        elif c in (curses.KEY_DOWN, ord("j")):
            st.cursor = min(len(st.keys) - 1, st.cursor + 1)
        elif c in (curses.KEY_UP, ord("k")):
            st.cursor = max(0, st.cursor - 1)
        elif c == ord(" ") and k:
            st.toggle(k)
        elif c == ord("a"):
            st.sel = set(st.keys)
        elif c == ord("n"):
            st.sel, st.fallback = set(), None
        elif c == ord("f") and k:
            if k in st.sel and st.mods[k].menu is not None:
                st.fallback = k
                st.msg = f"fallback: {st.mods[k].name}"
            else:
                st.msg = "the fallback must be selected and have a menu entry"
        elif c == ord("l"):
            name = prompt(scr, "load remix:")
            if name:
                try:
                    st.load(name)
                except SystemExit as e:
                    st.msg = str(e)
        elif c == ord("s"):
            probs = st.problems()
            if probs:
                st.msg = f"refusing to save: {probs[0]}"
            else:
                name = prompt(scr, "save as remix:")
                if name:
                    if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
                        st.msg = "name must be lowercase [a-z][a-z0-9_]*"
                    else:
                        doc = prompt(scr, "one-line description:") or \
                              "a selection composed in the remix TUI"
                        p = ROOT / f"remixes/{name}.py"
                        if p.exists() and prompt(
                                scr, f"{name}.py exists -- overwrite? [y/N]"
                        ).lower() != "y":
                            st.msg = "not saved"
                        else:
                            p.write_text(st.as_remix(name, doc))
                            st.msg = f"wrote remixes/{name}.py"
        elif c == ord("w"):
            st.msg = "assembling..."
            draw(scr, st)
            ok, msg = st.measure("this selection")
            st.msg = msg
        elif c in (ord("b"), ord("c")):
            probs = st.problems()
            if probs:
                st.msg = f"refusing: {probs[0]}"
                continue
            name = prompt(scr, "build which saved remix? [name]:")
            if not name:
                st.msg = ("build runs a SAVED remix -- press s to save this "
                          "selection first")
                continue
            target = "bus" if c == ord("b") else "check"
            shell_out(scr, ["make", target, f"REMIX={name}"])
            st.msg = f"make {target} REMIX={name} finished"
        elif c == ord("e"):
            if not BUILT_IMAGE.exists():
                st.msg = "no built image yet — press b to build first"
            else:
                emu_view(scr, BUILT_IMAGE)
                st.msg = f"emulator: booted {BUILT_IMAGE.name}"
        elif c == ord("v"):
            wav_browser(scr)
            st.msg = "source wav browser"


if __name__ == "__main__":
    if not sys.stdout.isatty():
        sys.exit("the remix workbench needs a terminal (try: make remix)")
    curses.wrapper(main)
