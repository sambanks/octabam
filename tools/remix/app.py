#!/usr/bin/env python3
"""The remix workbench: swap effects, hear them, see the panel draw them.

    make remix          (or: .venv/bin/python3 tools/remix/app.py)

ONE page, three panes -- AVAILABLE (what could be in the image), LOADED
(what is), UNIT (the selected effect's knobs and the firmware's own draw of
its page). The loop it exists for is one move long: point at a stock effect,
`enter` to swap one of ours in, `r` to hear it.

THE IMAGE FOLLOWS THE SELECTION. Every selection change rebuilds and
re-boots in the background -- a build is ~0.3 s and a ColdFire boot ~5 s --
so the panel on the right always draws what the middle pane says. There is
no build key and no stale state to reason about; that apparatus existed to
spare the operator a quarter-second and cost more than it saved.

The model layers are headless and live next door: state.py (the composer),
rig.py (categories, knobs), audition.py (rendering). This file is only the
shell. Textual rather than curses: the workbench is already venv-hosted for
the emulator, and the frontend rewrite is where hand-rolled layout stopped
paying its way.
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

try:
    from textual import work
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Horizontal, Vertical
    from textual.screen import ModalScreen, Screen
    from textual.widgets import Footer, Input, OptionList, RichLog, Static
    from textual.widgets.option_list import Option
except ImportError:
    sys.exit("the workbench frontend needs textual -- run: make emu-setup")

from rich.markup import escape  # noqa: E402  (rich ships with textual)

from remix import audition, registry, rig, stock  # noqa: E402
from remix.state import BUILT_IMAGE, ROOT, State  # noqa: E402


def step_label(mod, name, v):
    """A select's value as the manifest labels it, else the raw number."""
    lab = rig.knob_labels(mod, name)
    return lab[v] if lab and v < len(lab) else str(v)


# ---- the palette -----------------------------------------------------------
# COLOUR CARRIES MEANING HERE, it does not decorate. Three axes, and nothing
# else gets colour:
#
#   whose is it   OURS is aqua, the box's own is plain. In a remixer that is
#                 the distinction you scan for -- "which of these did we
#                 write" -- and it was carried by nothing at all.
#   what state    green fits / ochre is a trade or a caution / red blocks.
#   what is live  a soft purple for the one-of-a-kind markers (the fallback).
#
# ⚠️ THESE WERE ANSI NAMES AND THEY CAME OUT AS SATURATED PRIMARIES --
# `cyan` rendered #00ffff, `yellow` #ffff00 -- because Rich resolves a name
# to its standard value rather than delegating to the terminal, so the
# "it wears your palette" reasoning was simply wrong. Against a warm dark
# background that read as a wall of electric blue. These are gruvbox's own
# tones instead: same three axes, desaturated, and chosen to sit on a dark
# ground rather than shout off it.
#
# WHERE colour goes matters as much as which. The knob bars are twelve rows
# deep, so ONE tint across them made the accent the largest thing on screen
# and said nothing -- but neutralising them entirely went too far the other
# way. They are graded by their OWN VALUE instead: a soft warm ramp, so the
# variety comes from the values themselves and a row's colour means
# something. No red in the ramp -- a full LP cutoff is not an alarm.
OURS = "#8ec07c"       # aqua -- a module from modules/
OK = "#b8bb26"         # green -- fits, present, healthy
WARN = "#d79921"       # ochre -- a trade, a caution, a knob that renders dry
BAD = "#fb4934"        # red -- it will not build
MARK = "#d3869b"       # soft purple -- the fallback, and other lone markers
LCD = "#665c54"        # the emulated panel's frame: chrome, so it recedes
SRC = "#83a598"        # muted blue -- the wav you are auditioning on
BAR = ("#b8bb26", "#d79921", "#fe8019")     # the knob ramp, low -> high


def bar_colour(v, hi):
    """A knob's fill colour, from where it sits in its own range."""
    return BAR[min(int(3 * v / max(hi, 1)), 2)]


# Words that are acronyms, not shouting, and stay upper in a title.
_ACRONYMS = {"DJ", "EQ", "FX", "HP", "LP", "MS", "AB"}


def titlecase(s: str) -> str:
    """One naming rule for every name the workbench prints.

    The lists mixed three conventions and it showed: OUR modules carry a
    panel name in camel case (`BongDelay`), the STOCK effects carry the
    firmware's own, which is upper (`DJ EQUALIZER`, `LO-FI`), and a module
    with no chooser row falls back to its directory slug (`tempo-sync`). So
    one column read BongDelay / EQUALIZER / tempo-sync.

    Deliberate inner capitals are LEFT ALONE -- `BongDelay` must not become
    `Bongdelay`, which is the failure mode of a naive .title(). A word is
    only re-cased when it is entirely upper (or entirely lower), and known
    acronyms keep their case.

    ⚠️ This is the WORKBENCH's own text only. The emulated panel draws
    strings captured from the firmware and is never re-cased -- it has to
    show what the unit shows.
    """
    def word(w):
        if not w:
            return w
        if w.upper() in _ACRONYMS:
            return w.upper()
        if not w.isupper() and any(c.isupper() for c in w[1:]):
            return w                      # BongDelay, ChonVerb, WarpFold
        return w[:1].upper() + w[1:].lower()
    parts = re.split(r"([ \-/]+)", s)
    return "".join(word(p) if i % 2 == 0 else p
                   for i, p in enumerate(parts))


def disp(mod) -> str:
    """What to CALL a module on screen: the name the panel shows, not the
    directory slug. `warpfold` is a path; `WarpFold` is what the operator
    reads on the unit."""
    if mod.menu is not None:
        return titlecase(mod.menu.fullname.decode("latin1") or mod.name)
    return titlecase(mod.name)


# Where the SOURCE row browses. out/dry/ is the curated dry set and stays the
# default (31 Aug 2026: test_audio + demo_sources are full of processed
# renders and made the browser unusable), but a bench is used on whatever
# material is to hand, so `d` points it somewhere else and CONFIG remembers.
CONFIG = ROOT / "out" / "_audition" / "workbench.json"
DEFAULT_SOURCE_DIR = ROOT / "out" / "dry"


def load_config():
    """{} on anything unreadable -- a corrupt settings file must not stop the
    workbench opening, it is a convenience, not state anyone can lose work
    from."""
    try:
        return json.loads(CONFIG.read_text())
    except Exception:                                # noqa: BLE001
        return {}


def save_config(cfg):
    try:
        CONFIG.parent.mkdir(parents=True, exist_ok=True)
        CONFIG.write_text(json.dumps(cfg, indent=2) + "\n")
    except OSError:
        pass                                    # not worth an error dialog


def source_dir():
    """The directory the SOURCE row browses, in precedence order: the env
    override, what `d` last chose, then out/dry/."""
    env = os.environ.get("WORKBENCH_SOURCES")
    if env:
        return pathlib.Path(env).expanduser()
    saved = load_config().get("source_dir")
    if saved:
        return pathlib.Path(saved).expanduser()
    return DEFAULT_SOURCE_DIR


def wav_sources(d=None):
    """The wavs in the source directory. Falls back to the old scattered dirs
    only when the chosen one is missing or empty -- a fresh tree, before
    anyone has copied sources in."""
    d = d or source_dir()
    if d.is_dir():
        out = sorted(d.glob("*.wav"))
        if out:
            return out
    out = []
    for name in ("dry", "test_audio", "demo_sources"):
        alt = ROOT / "out" / name
        if alt.is_dir() and alt != d:
            out += sorted(alt.glob("*.wav"))
    return out


# ---- tiny modals -----------------------------------------------------------
class TextPrompt(ModalScreen[str]):
    """One-line text input; dismisses with '' on escape."""

    CSS = """
    TextPrompt { align: center middle; }
    #box { width: 60; height: auto; border: round $primary; padding: 1; }
    """

    def __init__(self, question, value=""):
        super().__init__()
        self.question = question
        self.value = value

    def compose(self) -> ComposeResult:
        with Vertical(id="box"):
            # ESCAPED, because a question is data. A path in the prompt --
            # "source folder [/Users/.../out/dry]:" -- parsed as Rich markup
            # and raised MarkupError: closing tag does not match any open
            # tag. Same family as the 31 Aug pass that escaped every
            # data-driven string in the panes; a prompt is one too.
            yield Static(escape(self.question))
            yield Input(value=self.value)

    def on_input_submitted(self, ev):
        self.dismiss(ev.value.strip())

    def on_key(self, ev):
        if ev.key == "escape":
            ev.stop()
            self.dismiss("")


class Chooser(ModalScreen[str]):
    """Pick one of a list; dismisses with '' on escape."""

    CSS = """
    Chooser { align: center middle; }
    #box { width: 44; height: auto; max-height: 80%;
           border: round $primary; padding: 1; }
    """

    def __init__(self, title, options):
        super().__init__()
        self.title_text = title
        self.options = options            # [(id, label)]

    def compose(self) -> ComposeResult:
        with Vertical(id="box"):
            yield Static(self.title_text)
            yield OptionList(*[Option(lbl, id=i) for i, lbl in self.options])

    def on_mount(self):
        self.query_one(OptionList).focus()

    def on_option_list_option_selected(self, ev):
        self.dismiss(ev.option.id)

    def on_key(self, ev):
        if ev.key == "escape":
            ev.stop()
            self.dismiss("")


HELP = {
    "bench": """[bold]THE BENCH — one page, three panes[/]

[bold]AVAILABLE[/] everything that could be in an image: your modules,
then the stock effects the unit already ships. [bold]LOADED[/] is the
image you are composing, in CHOOSER ORDER — the order here is the order
of rows on the panel, so left/right there is a real edit. [bold]UNIT[/]
follows the cursor: the selected effect's knobs, the firmware's own draw
of its page, and `r` to hear it on the SOURCE wav.

The loop is one move long: point at a stock effect in LOADED, highlight
one of yours in AVAILABLE, `enter`. The image rebuilds and re-boots by
itself, so the panel is never showing something else.

[bold]keys[/]
  tab  pane            up/down  move
  enter  in AVAILABLE: ADD it to the image. On one already in,
         just point at its row -- THE LIBRARY ONLY ADDS.
         in LOADED: remove the row you are on.
  left/right  knob value (UNIT) or row order (LOADED)
              hold to run; SHIFT+left/right steps by TEN
  r  render + hear     space  play last    p  preview mode
  a / b  park what you hear as A / B      , / .  play A / B
  x  apply the ⚠'s own fix
  d  sample folder     l  load remix       s  save remix
  c  full check        f  fallback         k  back to stock
  ?  this

[bold]adding does not displace anything[/]
`enter` used to SWAP -- the new effect took the highlighted row's slot
and that row was dropped. That was the ledger's scarcity applied to your
gesture, where it does not belong: the chooser cave holds 31 rows and a
STOCK row costs zero words (no code placed, no descriptor cloned). Only
WORDS are scarce, and only for modules of ours. So `enter` adds, and the
one line under LOADED speaks up if the budget is actually breached.

[bold]A / B compares two EFFECTS[/]
Not two renders ago against now. `r` to hear one, `a` to park it, point
at the rival, `b` -- which re-renders it on the SAME source -- then `,`
and `.` to flip between them. That is the question a remixer exists to
answer: is mine better than the one the box came with?

[bold]why an effect can render DRY[/]
SIX of the eleven stock effects ship with their wet control at zero —
PHASER, FLANGER, CHORUS and COMB (MIX), SPATIALIZER and DELAY (SEND) —
so `r` on one of them at its defaults plays the source back unchanged.
That is faithful: the defaults are read from the firmware's own
descriptor, and an unmodified unit really does start them fully dry.
The UNIT pane says `⚠ MIX is 0 — this renders DRY` when it applies.

[bold]the SOURCE row[/]
`left`/`right` cycles the wavs in the source folder; `d` points it at
another one and remembers the choice (out/_audition/workbench.json).
`WORKBENCH_SOURCES` overrides both.

[bold]the one line under LOADED[/]
It says the only two things that can stop you: whether the selection
fits the 2,724-word donor region, and — with a ⚠ — the effects you have
to remove before it will build. Everything else the pane used to explain
is here instead.

[bold]why some stock effects go dim[/]
Every image replaces the whole FX2 chooser, but only THREE stock effects
are CONSUMED: PLATE, SPRING and DARK REV, whose code is the donor region
your modules are written over. The other eleven keep their code and knobs
in every image and only lose their chooser row — an old project that
selects one still runs it. Four of them (SPATIALIZER, FLANGER, CHORUS,
COMB FILTER) take a per-track instance buffer at the addresses the servers
hardcode, so they cannot sit beside ChonVerb, Nimbus or BongDelay; that is
what the ⚠ is telling you to remove.

[bold]the fallback[/]
An id the image does not implement aliases to the FALLBACK — normally
SEND, so an old project degrades to a send instead of noise. It is added
for you when a selection needs one; `f` chooses another. ◀fb marks it.

[bold]you cannot get the three reverbs back[/]
Not from here, and it is not the workbench refusing. Every buildable
selection needs a fallback and SEND is the only safe one; SEND carries
DSP code; and `build_bus.py` repoints PLATE/SPRING/DARK REV to the null
stub UNCONDITIONALLY, whether or not code was placed over them. So every
image loses them. PLAN.md §7 has the two build changes that would fix it
and the argument for closing it instead.""",
}


class HelpScreen(ModalScreen[None]):
    """The ? overlay: what this view is, its keys, and the concepts."""

    CSS = """
    HelpScreen { align: center middle; }
    #box { width: 76; height: auto; max-height: 90%;
           border: round $primary; padding: 1 2; }
    """

    def __init__(self, view):
        super().__init__()
        self.view = view

    def compose(self) -> ComposeResult:
        with Vertical(id="box"):
            yield Static(HELP[self.view])
            yield Static("[dim]any key closes[/]")

    def on_key(self, ev):
        ev.stop()
        self.dismiss(None)


# ---- THE BENCH: one page, three panes ---------------------------------------
AVAILABLE, LOADED, UNIT = 0, 1, 2
# The unit's own order: FX1 then FX2 are the two slots on a
# track; MAIN MENU is the odd one out and goes last.
PREVIEWS = ("FX1", "FX2", "MENU")


class BenchScreen(Screen):
    """One page: the library, the image being composed, and the selected unit.

    Three panes, left to right, matching how the work actually goes: what
    COULD be in the image, what IS, and what the selected effect looks like on
    the unit. There is no per-track view -- a remix is a statement about an
    IMAGE, and the eight tracks were a second place to say the same thing.
    Knob values belong to the effect, not to a track.

    The default selection is STOCK: the chooser an unmodified unit shows. You
    add to what the box already does rather than to somebody else's remix.
    """

    BINDINGS = [
        Binding("tab", "pane(1)", "pane"),
        Binding("shift+tab", "pane(-1)", "prev pane", show=False),
        # "swap / remove" was stale from the moment enter stopped swapping.
        Binding("enter", "add_remove", "add / remove"),
        Binding("r", "render", "hear it"),
        Binding("space", "play", "play last"),
        # The sample folder belongs on the footer: it is the one setting that
        # is about YOUR material rather than about the image, so it is the
        # one a new pair of hands looks for and cannot guess.
        Binding("d", "source_dir", "sample folder"),
        Binding("p", "preview", "preview page", show=False),
        Binding("a", "mark('A')", "A = this", show=False),
        Binding("b", "mark('B')", "B = this", show=False),
        Binding("comma", "play_mark('A')", "play A", show=False),
        Binding("full_stop", "play_mark('B')", "play B", show=False),
        Binding("x", "fix", "apply the fix", show=False),
        Binding("c", "build('check')", "full check", show=False),
        Binding("f", "fallback", "fallback", show=False),
        Binding("l", "load", "load"),
        Binding("s", "save", "save"),
        Binding("k", "stock", "reset to stock", show=False),
        Binding("question_mark", "help", "what is this?"),
        Binding("q", "app.quit", "quit"),
    ]

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Static(id="pane_avail")
            yield Static(id="pane_load")
            # The third column is TWO stacked panes: the selected effect, and
            # a standing budget under it. What is left of the image is the
            # context you read every other number against, so it should not
            # be something you have to go and ask for.
            with Vertical(id="col_unit"):
                yield Static(id="pane_unit")
                yield Static(id="pane_budget")
        yield Static(id="status")
        yield RichLog(id="log", highlight=False, markup=False)
        yield Footer()

    def on_mount(self):
        self.pane = LOADED
        self.cur = [0, 0, 0]
        self.preview = "FX2"
        self.rows_mtime = None
        self.built = []                  # (fx2_id, module) from the image
        # The image tracks the selection: `gen` counts selection changes,
        # `synced` is the one the booted image reflects, `syncing` is the one
        # a worker is currently building. A rebuild is kicked whenever they
        # disagree -- see schedule_sync().
        self.gen = 0
        self.synced = None
        self.syncing = None
        self.sync_error = None
        self._panel_cache = (None, None)   # see _panel()
        self._painted = {}                 # see _paint()
        # COALESCED REPAINT. A held arrow key delivers events faster than
        # three panes can be rebuilt, and rendering each one in turn is what
        # makes the UI trail the key and overshoot after release. The VALUE
        # changes on every event; the SCREEN catches up at 60 Hz, however
        # many events arrived in between.
        self._dirty = False
        self.set_interval(1 / 60, self._flush)
        self._run = (None, True, 0.0, 0)   # see _accel()
        # EDIT THE SOURCE IN ANOTHER WINDOW AND THE BENCH FOLLOWS. The image
        # already tracks the SELECTION; it has to track the CODE too, or the
        # panel and every render silently describe the .asm you had a minute
        # ago. Polled rather than watched: one stat sweep of modules/ is
        # ~2 ms, a filesystem-event dependency is not worth adding to a venv
        # that already carries unicorn and textual, and 1.5 s is far below
        # the time it takes to switch windows.
        self._src = audition._newest_input_mtime()
        self.set_interval(1.5, self._poll_source)
        self.measure_all()
        self.query_one("#log", RichLog).display = False
        self.rerender()

    # ---- the rows each pane walks ---------------------------------------
    # Group order for the library pane: the way you meet them -- the two big
    # bus effects, then the inserts that stack, then plumbing, then stock.
    _GROUPS = (rig.SERVER, rig.INSERT, rig.SYSTEM)

    def avail_rows(self):
        """Everything that COULD be in an image: our modules, then stock."""
        mods = [m for m in registry.modules().values() if not m.is_stock]
        mods.sort(key=lambda m: (self._GROUPS.index(rig.category(m)),
                                 disp(m).lower()))
        return mods + list(stock.MODULES)

    def loaded_rows(self):
        st = self.app.state
        return [st.mods[k] for k in st.order]

    def unit_rows(self, mod):
        """What the UNIT cursor walks: the sample to audition, then the
        effect's drawn knobs in slot order. SOURCE is a row rather than a
        hidden setting because "what am I hearing this on" is the first
        question at a bench, and it was the one thing the old per-track view
        got right."""
        rows = [("SOURCE", None)]
        if mod is None or not mod.params:
            return rows
        return rows + [(n, sl) for n, sl in sorted(mod.knob_map().items(),
                                                   key=lambda kv: kv[1])
                       if mod.params[sl].active]

    @staticmethod
    def dry_control(mod, vals):
        """The wet/dry control that is sitting at zero, if one is.

        SIX of the eleven stock effects ship with their wet control at 0 --
        PHASER, FLANGER, CHORUS and COMB (MIX), SPATIALIZER and DELAY (SEND)
        -- so pressing `r` on them plays the source back unchanged. That is
        FAITHFUL: the defaults are read from the firmware's own descriptor
        (tools/remix/stock.py), an unmodified unit really does start them
        fully dry, and seeding a different value here would make the bench
        lie about the page it is drawing beside. But it reads as "this effect
        does nothing", which is what it cost on 2 Sep 2026. So say it.
        """
        if mod is None:
            return None
        for name in ("MIX", "SEND"):
            if name in vals and vals[name] == 0:
                return name
        return None

    def selected_module(self):
        """The unit pane follows whichever pane the cursor is in -- point at
        something in the library and pane 3 previews it before you add it."""
        rows = self.avail_rows() if self.pane == AVAILABLE else self.loaded_rows()
        if self.pane == UNIT:
            rows = self.loaded_rows()
        if not rows:
            return None
        i = min(self.cur[min(self.pane, LOADED)], len(rows) - 1)
        return rows[i]

    def image_rows(self):
        """What the BUILT image offers -- re-read when the image changes."""
        mt = BUILT_IMAGE.stat().st_mtime if BUILT_IMAGE.exists() else None
        if mt != self.rows_mtime:
            self.built, self.rows_mtime = rig.built_chooser(), mt
        return self.built

    def in_image(self, mod):
        """Would this effect's page actually resolve in the image on disk?

        A STOCK effect always does. A remix that leaves one out does not
        REMOVE it -- its code, descriptor and dispatch entry stay stock, and
        an old project that selects it still runs it; it only loses its
        chooser row. So chooser membership is the wrong test for stock, and
        using it made every effect unpreviewable on a fresh all-stock launch.

        One of OURS is another matter: if it was not built, its id resolves
        to the fallback. (The schema forbids our modules on stock ids, so
        these two cases cannot overlap.)
        """
        if mod is None or mod.menu is None:
            return False
        if mod.is_stock:
            return True
        return any(m is not None and m.key == mod.key
                   for _, m in self.image_rows())

    # ---- render ----------------------------------------------------------
    def rerender(self):
        """One pass over the three panes.

        problems() runs the ledger and costs ~2.4 ms (measured 2 Sep 2026);
        three panes asking it independently made every keystroke pay ~7 ms
        for one answer. Compute it here and hand it down.
        """
        st = self.app.state
        probs = st.problems()
        self._pane_available(st)
        self._pane_loaded(st, probs)
        self._pane_unit(st, probs)
        self._pane_budget(st)
        self._paint("#status", f"[dim]{escape(st.msg)}[/]")

    def _paint(self, wid, lines):
        """Update a pane only when its TEXT changed.

        Handing Textual an identical string still costs a Static re-render
        and a screen diff, and a knob keystroke changes ONE pane -- the other
        two were being rebuilt and re-diffed for nothing on every key.
        """
        text = "\n".join(lines) if isinstance(lines, list) else lines
        if self._painted.get(wid) == text:
            return
        self._painted[wid] = text
        self.query_one(wid, Static).update(text)

    def _title(self, text, pane):
        on = self.pane == pane
        return (f"[reverse bold] {escape(text)} [/]" if on
                else f"[bold]{escape(text)}[/]")

    def _pane_available(self, st):
        rows = self.avail_rows()
        out = [self._title("Available", AVAILABLE), ""]
        group = None
        for i, m in enumerate(rows):
            g = "Stock Effects" if m.is_stock else titlecase(rig.category(m))
            if g != group:
                group = g
                out.append(f"[dim {WARN}]── {g} ──[/]")
            here = self.pane == AVAILABLE and i == self.cur[AVAILABLE]
            mark = (f"[{OK}]✓[/]" if m.key in st.sel else " ")
            menus = "+".join(rig.menus(m)) or "—"
            nm = disp(m) if m.is_stock else f"[{OURS}]{disp(m)}[/]"
            pad = " " * max(0, 13 - len(disp(m)))
            line = f" {mark} {nm}{pad} [dim]{menus}[/]"
            out.append(f"[reverse]{line}[/]" if here else line)
        out.append("")
        out.append(f"[dim]enter adds it to the image[/]")
        self._paint("#pane_avail", out)

    def _pane_loaded(self, st, probs):
        rows = self.loaded_rows()
        name = st.loaded_name or "unsaved"
        out = [self._title(f"Loaded · {name}", LOADED), ""]
        pos = 0
        for i, m in enumerate(rows):
            here = self.pane == LOADED and i == self.cur[LOADED]
            if m.menu is not None:
                pos += 1
                row = f"{pos:>2}"
            else:
                row = " ·"                      # no chooser row (a CF patch)
            menus = "+".join(rig.menus(m)) or "—"
            words = st.words.get(m.key)
            cost = f"{words:>5}w" if words else "      "
            fb = f"[{MARK}]◀fb[/]" if st.eff_fallback == m.key else ""
            # No insertion caret any more: `enter` appends, so there is no
            # second cursor in another pane to keep track of.
            nm = disp(m) if m.is_stock else f"[{OURS}]{disp(m)}[/]"
            pad = " " * max(0, 13 - len(disp(m)))
            line = (f" [dim]{row}[/] {nm}{pad}"
                    f"[dim]{menus:<7}{cost}[/]{fb}")
            out.append(f"[reverse]{line}[/]" if here else line)
        if not rows:
            out.append("[dim] (empty — add from the left)[/]")
        # THE THREE REVERBS ARE PART OF A STOCK CHOOSER and belong in this
        # list, not off in the library: an unmodified unit shows fourteen FX2
        # effects, and these are three of them. They leave when something
        # takes their space -- their code IS the donor region our modules are
        # written over -- so showing the trade where it happens is the point.
        # ONE dim line, not three: the old form repeated "taken by <module>"
        # per reverb, which said one thing three times, named an arbitrary
        # module as the taker (eats[0] is just the first selection with DSP
        # code -- nothing here computes a per-reverb attribution), and
        # overran the 38-column pane so its " +1" wrapped onto its own line
        # and read as a fourth mystery row.
        # WHICH REVERBS ARE ACTUALLY GONE, from the build's own report --
        # not "all three, always", which is what this said before 2 Sep 2026
        # and which was the reason the honest answer to "why can I never get
        # the stock verbs back?" was "you cannot". A light selection keeps
        # the ones the placement never reached; they are ordinary stock rows
        # you can add from the library like any other.
        gone = [c for c in stock.CONSUMED
                if c.split()[0] not in st.donors_kept]
        if st.donors_kept or not gone:
            for cname in stock.CONSUMED:
                if cname in st.sel or cname not in gone:
                    continue
                out.append(f"[dim {WARN}] —  {titlecase(cname):<13}"
                           f"donor, taken[/]")
        elif [m for m in st.selected if m.dsp is not None]:
            out.append(f"[dim {WARN}] —  Plate, Spring, Dark Rev (donors)[/]")
        # THE SHARED COST, ONCE. Every module that pins FX2 buffers costs
        # the same seven stock effects, so saying it on each of them read as
        # two bills for one debt -- ChonVerb and BongDelay showed identical
        # lists. It belongs to the image, so the image says it.
        pin = [m for m in st.selected if rig.pins_fx2(m)]
        if pin:
            out.append(f"[dim {WARN}]no room for "
                       f"{escape(rig.allocating_names())} — "
                       f"{escape(disp(pin[0]))}"
                       f"{' and ' + disp(pin[1]) if len(pin) > 1 else ''} "
                       f"pin their slots[/]")
        out.append("")
        out.append(self._ledger_line(st, probs))
        self._paint("#pane_load", out)

    def _ledger_line(self, st, probs):
        """The fit, the blocker and the build state, in ONE line.

        This pane used to close with five: a donor-region budget, a ● legend,
        a "dim = stock" legend, a keys hint and a ⚠ -- roughly half its
        height spent explaining constraints rather than showing the image.
        Only two questions are actually live while swapping: does this fit,
        and is the panel on the right showing it yet. The rest moved to `?`.
        """
        if self.untouched_stock(probs):
            return "[dim]stock — swap a module in to build it[/]"
        if probs:
            return (f"[bold {BAD}]⚠ "
                    f"{escape(self._clash(probs) or probs[0])}[/]")
        if self.syncing is not None or self.synced != self.gen:
            return f"[dim {WARN}]building…[/]"
        if self.sync_error:
            # The build names the payload and the overrun; that IS the
            # actionable sentence, so print it rather than a pointer to it.
            gone = self.blockers([])
            if gone:
                return (f"[bold {BAD}]⚠ x removes "
                        + ", ".join(disp(m) for m in gone)
                        + " — this selection needs its words[/]")
            return f"[bold {BAD}]⚠ {escape(self.sync_error)}[/]"
        # THE BUILD'S OWN NUMBERS, one per payload. Not a sum of st.words
        # against DONOR_WORDS: there are TWO regions of that size and
        # SPEC=1 puts a server on each, so the sum is not a quantity
        # anything has to fit (see state.problems).
        if st.regions:
            # The free-word count is the one number worth a glance, so let
            # its COLOUR carry the answer: comfortable, tight, or spent.
            def one(n, f):
                # Thresholds from what this project actually lives with:
                # payload A has shipped at FREE 4 and B at FREE 5, so double
                # digits is already "spent" and deserves the alarm colour.
                c = OK if f > 400 else WARN if f > 32 else BAD
                return f"{n} [{c}]{f}[/] free"
            return "[dim]" + " · ".join(
                one(n, f) for n, _u, f in st.regions) + "[/]"
        # No build has reported yet. Say which of the two reasons it is --
        # this line used to claim "a stock chooser: 14 effects, no modules"
        # for ANY unmeasured selection, including chongbong, which has three.
        if not [m for m in st.selected if m.dsp is not None]:
            return "[dim]a stock chooser: 14 effects, no modules[/]"
        return "[dim]building…[/]"

    def _pane_budget(self, st):
        """WHAT IS LEFT, standing under the effect you are looking at.

        Every other number in this workbench is read against this one -- "500
        words" means nothing without "and 313 are free" -- and it used to be
        something you inferred from a refusal. Four scarce things, and only
        four: the two donor regions, the FX2 buffer slots per core, the
        chooser rows, and the ColdFire cave. Everything else is unbounded in
        practice.

        Read from the BUILD's own report wherever possible (state.measure),
        because the build is the only thing that knows where the cursor
        actually stopped.
        """
        out = ["[bold]Budget[/]"]
        W = 10                                  # one label column throughout

        def row(label, bar_full, bar_len, colour, tail):
            return (f" {label:<{W}}[{colour}]" + "#" * bar_full + "[/][dim]"
                    + "." * (bar_len - bar_full) + f"[/]  {tail}")

        if st.regions:
            for n, used, free in st.regions:
                fill = min(20, round(20 * used / max(used + free, 1)))
                c = OK if free > 400 else WARN if free > 32 else BAD
                out.append(row(f"words {n}", fill, 20, c, f"{free:>4} free"))
        else:
            out.append(f" {'words':<{W}}[dim]"
                       + "?" * 20 + "[/]  [dim]not built[/]")

        # FX2 buffer slots, per core. Four each, and a pinner takes two or
        # all four of ONE core's -- which is why the two servers coexist.
        for tag, tracks in (("A", "5-8"), ("B", "1-4")):
            taken = 0
            for m in st.selected:
                if not rig.pins_fx2(m):
                    continue
                tr = rig.track_range(m)
                here = (not len(tr) or len(tr) == 8
                        or (tag == "A" and tr.start == 5)
                        or (tag == "B" and tr.start == 1))
                if here:
                    taken = max(taken, rig.pinned_slots(m))
            free = 4 - taken
            c = OK if free > 2 else WARN if free else BAD
            out.append(row(f"FX2 buf {tag}", 5 * taken, 20, c,
                           f"{free} of 4  [dim]tracks {tracks}[/]"))

        # Rows are countable without a build; the cave is not.
        rows = (st.chooser_rows if st.chooser_rows is not None
                else len(st.menu_modules))
        c = OK if rows < 24 else WARN if rows < 31 else BAD
        out.append(f" {'rows':<{W}}[{c}]{rows}[/][dim] of 31 "
                   f"(the long chooser cave)[/]")
        cave = (f"[{OK if st.cave_free > 512 else WARN if st.cave_free else BAD}]"
                f"{st.cave_free:,}[/][dim] B free[/]"
                if st.cave_free is not None else "[dim]not built[/]")
        out.append(f" {'cave':<{W}}{cave}")
        self._paint("#pane_budget", out)

    def _pane_unit(self, st, probs):
        mod = self.selected_module()
        if mod is None:
            self._paint("#pane_unit",
                        self._title("Unit", UNIT) + "\n\n[dim]nothing selected[/]")
            return
        out = [self._title(disp(mod), UNIT), ""]
        bits = [titlecase(rig.category(mod))]
        if mod.menu:
            bits.append(f"id 0x{mod.menu.fx2_id:02x}")
            bits.append("+".join(rig.menus(mod)))
        tr = rig.track_range(mod)
        if len(tr):
            bits.append(f"tracks {tr.start}-{tr.stop - 1}")
        out.append(f"[dim]{' · '.join(bits)}[/]")
        out.append(f"[dim]{escape(mod.doc)}[/]")
        # WHAT IT COSTS, while you are still deciding. "Will this fit beside
        # what I already have" is what the library pane is really asked, and
        # every answer used to arrive only as a refusal after adding it.
        res = rig.resources(mod, st.words.get(mod.key))
        if res:
            out.append(f"[{WARN}]{escape(' · '.join(res))}[/]")
        out.append("")

        knobs = self.unit_rows(mod)
        vals = st.knobs_for(mod)
        for i, (name, slot) in enumerate(knobs):
            here = self.pane == UNIT and i == self.cur[UNIT]
            if name == "SOURCE":
                src = (self.app.source.name if self.app.source
                       else f"(none — no wavs in {source_dir()})")
                line = f" [dim]SOURCE[/] [{SRC}]{escape(src)}[/]"
                out.append(f"[reverse]{line}[/]" if here else line)
                continue
            v = vals.get(name, 0)
            hi = rig.knob_max(mod, name)
            if hi < 8:
                # A SELECT reads as a word, not a level, so it gets the
                # accent and a flat bar -- no fill to imply a range it does
                # not have.
                shown = f"[{WARN}]{step_label(mod, name, v):<7}[/]"
                bar = f"[{LCD}]" + "·" * 12 + "[/]"
            else:
                shown = f"{v:>3}    "
                fill = round(12 * v / max(hi, 1))
                bar = (f"[{bar_colour(v, hi)}]" + "#" * fill + "[/][dim]"
                       + "." * (12 - fill) + "[/]")
            page = "1" if slot < 6 else "2"
            line = f" {name:<6} {shown}[dim]\\[[/]{bar}[dim]] p{page}[/]"
            out.append(f"[reverse]{line}[/]" if here else line)
        if not knobs:
            out.append("[dim] (no drawn parameters)[/]")
        dry = self.dry_control(mod, vals)
        if dry:
            out.append(f"[{WARN}]⚠ {dry} is 0 — this renders DRY[/]")
        if self.pane == UNIT and knobs:
            name, _ = knobs[min(self.cur[UNIT], len(knobs) - 1)]
            hint = (f"the wav auditioned through this effect — left/right "
                    f"cycles {source_dir()}, d changes it"
                    if name == "SOURCE" else rig.knob_doc(mod, name) or "")
            out.append("")
            out.append(f"[dim]? {escape(hint)}[/]")
        out.append("")
        out.append("[dim]← → change · r render + hear · space replay[/]"
                   if self.pane == UNIT else
                   "[dim]tab here to change values and audition[/]")
        out.append("")
        out += self._preview(mod, probs)
        self._paint("#pane_unit", out)

    # ---- the emulated panel ---------------------------------------------
    def _panel(self, mode, effect_id):
        """The firmware's own draw of one page, CACHED.

        ⚠️ This is what made a HELD arrow key lag. render_fx2 costs 15-96 ms
        (mean 32; render_fx1 16, render_menu 8 -- measured 2 Sep 2026), and
        rerender() ran it on every keystroke, so under key repeat the work
        per key exceeded the repeat interval and the UI fell behind the key,
        then kept stepping after release. Single presses always felt fine,
        which is why it read as "slow when holding" rather than as latency.

        Nothing a keystroke does can change this picture: knob VALUES draw as
        dial graphics the string-capture hook cannot read (docs/EMU.md), so
        the page depends only on WHICH page, WHICH effect, and which boot.
        """
        key = (mode, effect_id, self.synced)
        if self._panel_cache[0] == key:
            return self._panel_cache[1]
        import emu_bringup
        r = self.app.boot
        if mode == "MENU":
            draws = emu_bringup.render_menu(r, emu_bringup.MENU_ROOT_DESC, 0)
        elif mode == "FX1":
            draws = emu_bringup.render_fx1(r, track=4, effect_id=0x04)
        else:
            draws = emu_bringup.render_fx2(r, track=4, effect_id=effect_id)
        grid = emu_bringup.layout_screen(draws)
        self._panel_cache = (key, grid)
        return grid

    def _preview(self, mod, probs):
        modes = " ".join(f"[reverse]{m}[/]" if m == self.preview else
                         f"[dim]{m}[/]" for m in PREVIEWS)
        head = [f"preview {modes}  [dim](p)[/]",
                "[dim]— drawn by the firmware, from your selection —[/]"]
        # DO NOT DRAW SOMETHING THAT IS NOT THE SELECTION. The FX2 page
        # includes the firmware's own chooser list, so an image that is not
        # this selection puts a different set of effects on screen beside the
        # LOADED pane and reads as "why are those loaded?". The answer is no
        # longer to explain it -- ensure_sync() rebuilds -- but while that is
        # in flight there is still nothing honest to show.
        self.ensure_sync(probs)
        r = self.app.boot
        if self.untouched_stock(probs):
            return head[:1] + ["[dim]swap a module in and this draws it[/]"]
        if probs:
            return head[:1] + ["[dim]not built — see the ⚠ in LOADED[/]"]
        if self.sync_error:
            return head[:1] + [f"[bold]build failed[/] [dim]— "
                               f"{escape(self.sync_error)}[/]"]
        if self.syncing is not None or r is None:
            return head[:1] + ["[dim]building and booting…[/]"]
        if not r.reached_handoff:
            return head + ["[bold]did not reach the RTOS handoff[/] — a "
                           "patch may have broken early init"]
        effect_id = None
        if self.preview == "FX2":
            if mod.menu is None:
                return head + ["[dim]no chooser row: this module patches the "
                               "firmware rather than adding an effect[/]"]
            if not self.in_image(mod):
                # Rare now that the image follows the selection, but kept:
                # an id the image does not implement resolves to the
                # FALLBACK, so the firmware would draw a convincing picture
                # of the wrong effect (CLAUDE.md, 12 Aug 2026).
                return head[:1] + ["[dim]not in the image yet[/]"]
            effect_id = mod.menu.fx2_id
        grid = self._panel(self.preview, effect_id)
        # The LCD frame is chrome; the firmware's own words are the content.
        edge = f"[{LCD}]"
        return head + [f"{edge}." + "-" * 44 + ".[/]"] + \
            [f"{edge}|[/]" + escape(ln.ljust(44)) + f"{edge}|[/]"
             for ln in grid] + \
            [f"{edge}'" + "-" * 44 + "'[/]"]

    # ---- keeping the image equal to the selection ------------------------
    # There used to be a stale() gate here: the preview refused to draw when
    # the image on disk was not the selection, and printed a bold two-line
    # disclaimer telling the operator to press b. Every fresh launch is
    # stale, so the headline feature opened showing a disclaimer -- and what
    # it was guarding is a 0.26 s build (`make bus` from a touched manifest,
    # measured 2 Sep 2026) plus a 4.6 s ColdFire boot, both already on a
    # worker thread. So the image just follows the selection instead.
    def schedule_sync(self):
        """The selection changed. Rebuild and re-boot, after a short pause so
        a run of swaps costs one build rather than one per keystroke."""
        self.gen += 1
        self.set_timer(0.35, self.ensure_sync)

    def ensure_sync(self, probs=None):
        """Start the rebuild if the image is behind and nothing is in the
        way. Idempotent and cheap -- rerender() calls it, so a kick that
        arrives during a render or a build is simply picked up by the next
        one rather than queued. `probs` is rerender's already-computed
        answer; the timer path has none and pays for its own."""
        if self.syncing is not None or self.synced == self.gen:
            return
        if self.app.rendering:
            return          # both write out/mainos_bus.bin; the render's
                            # closing rerender() will kick this again
        if self.app.state.problems() if probs is None else probs:
            # AND FORGET THE LAST BUILD'S NUMBERS. They describe a different
            # selection, and a budget that silently belongs to the image you
            # had two edits ago is worse than no budget at all.
            self.app.state.forget_build()
            self.synced, self.app.boot = self.gen, None
            return          # it would not build; the ⚠ line says why
        self.syncing = self.gen
        self.sync_worker(self.gen)

    @work(thread=True, group="sync")
    def sync_worker(self, gen):
        """Build the live selection, then boot it.

        state.measure() IS the build -- the same `REMIX=x XBUS=1 SPEC=1
        build_bus.py` that `make bus` runs -- and it parses the per-module
        word counts out of the build report on the way past. So one call
        does what the old b (build) and w (word cost) keys did separately.
        """
        st = self.app.state
        ok, note = st.measure(None)
        r = None
        if ok:
            try:
                import emu_bringup
                r = emu_bringup.boot(str(BUILT_IMAGE))
            except Exception as e:                   # noqa: BLE001
                note = f"emulator unavailable — {e} (make emu-setup)"
        if gen == self.gen:                          # not superseded
            self.app.boot = r
            self.sync_error = None if ok else note
            self.synced = gen
            self.rows_mtime = None                   # chooser rows re-read
            if not ok:
                st.msg = f"build failed: {note}"
        self.syncing = None
        self.app.call_from_thread(self.rerender)

    # ---- input -----------------------------------------------------------
    @work(thread=True, group="words")
    def measure_all(self):
        """Word counts for every module, so the library can say what a thing
        costs BEFORE you add it. ~2 s once, then cached (state.measure_every).
        """
        try:
            self.app.state.measure_every()
        except Exception:                            # noqa: BLE001
            return                     # a cost readout is never worth a crash
        self.app.call_from_thread(self.rerender)

    def _poll_source(self):
        """Rebuild when a module's source changed under us."""
        try:
            now = audition._newest_input_mtime()
        except OSError:
            return                      # mid-write; the next tick catches it
        if now == self._src:
            return
        self._src = now
        self.app.state.msg = "module source changed — rebuilding"
        self.measure_all()             # its word count may have moved too
        # The AUDIO is not re-rendered: it plays out loud and would fire on
        # every save. The image and the panel refresh; `r` is one key.
        self.schedule_sync()
        self.rerender_soon()

    def describe(self):
        """The status line follows the CURSOR, not the last thing you did.

        It was an action log -- "added Nimbus · added Send as the fallback" --
        which is read as context for whatever is under the cursor now, so it
        went stale the moment you scrolled and described a row you had left.
        An action still writes it; moving replaces it.
        """
        st = self.app.state
        mod = self.selected_module()
        if mod is None or self.pane == UNIT:
            return
        bits = [rig.category(mod)]
        if mod.menu is not None:
            bits.append(f"id 0x{mod.menu.fx2_id:02x}")
        bits += rig.resources(mod, st.words.get(mod.key))
        bits.append("in the image" if mod.key in st.sel else "not in the image")
        st.msg = f"{disp(mod)} — {' · '.join(bits)}"

    def rerender_soon(self):
        """Mark the screen stale; _flush draws it on the next frame."""
        self._dirty = True

    def _flush(self):
        if self._dirty:
            self._dirty = False
            self.rerender()

    def action_pane(self, d):
        self.pane = (self.pane + d) % 3
        self.rerender()

    def action_preview(self):
        self.preview = PREVIEWS[(PREVIEWS.index(self.preview) + 1)
                                % len(PREVIEWS)]
        self.rerender()

    def on_key(self, ev):
        st = self.app.state
        rows = (self.avail_rows() if self.pane == AVAILABLE else
                self.loaded_rows() if self.pane == LOADED else
                self.unit_rows(self.selected_module()))
        n = max(len(rows), 1)
        if ev.key in ("down", "j"):
            self.cur[self.pane] = min(n - 1, self.cur[self.pane] + 1)
            self.describe()
        elif ev.key in ("up", "k"):
            self.cur[self.pane] = max(0, self.cur[self.pane] - 1)
            self.describe()
        elif ev.key in ("left", "right", "h", "shift+left", "shift+right"):
            step = 1 if ev.key in ("right", "shift+right") else -1
            if self.pane == UNIT:
                self.adjust(step * (10 if "shift" in ev.key else 1))
            elif self.pane == LOADED:
                self.move_row(step)
            else:
                return
        else:
            return
        # Coalesced: holding a key steps the value every event and repaints
        # once a frame. Every other path still renders immediately.
        self.rerender_soon()

    # A HELD KEY ACCELERATES. The workbench stopped being the limit once the
    # panel render was cached (0.012 ms per key event, 86k/s) -- but macOS
    # repeats a held key at its default ~15/s after a 375 ms delay, so a
    # 0..127 knob still took ~8.5 s to sweep and there is nothing an app can
    # do about the RATE. So change the STEP instead: a run of events close
    # together is a hold, and a hold means "get there", while a single tap
    # still moves exactly one. Sweeps the full range in ~1.3 s at 15/s.
    _RUN_GAP = 0.20              # longer than a 15/s repeat (66 ms), well
                                 # under a deliberate double-tap
    _RUN_STEPS = ((18, 16), (10, 8), (4, 4))   # (events held, multiplier)

    def _accel(self, step, name, hi):
        """The multiplier for this event, given how long the key has been
        down. Only for the ±1 path -- shift is already an explicit ×10."""
        now = time.monotonic()
        same = (name == self._run[0]
                and (step > 0) == self._run[1]
                and now - self._run[2] < self._RUN_GAP)
        run = self._run[3] + 1 if same else 0
        self._run = (name, step > 0, now, run)
        # A SELECT MUST NOT ACCELERATE: MODE has five positions and flying
        # past them is not "faster", it is unusable. hi // 8 is 0 for every
        # stepped slot and 15 for a 0..127 knob, so this gates itself.
        ceiling = max(1, hi // 8)
        for need, mult in self._RUN_STEPS:
            if run >= need:
                return step * min(mult, ceiling)
        return step

    def adjust(self, step):
        """Change the selected row. Knob values live per MODULE."""
        st = self.app.state
        mod = self.selected_module()
        knobs = self.unit_rows(mod)
        if not knobs:
            return
        name, _ = knobs[min(self.cur[UNIT], len(knobs) - 1)]
        if name == "SOURCE":
            # Never accelerated: skipping files is not a faster way to pick
            # one, and the list is short.
            files = wav_sources()
            if files:
                i = (files.index(self.app.source)
                     if self.app.source in files else 0)
                self.app.source = files[(i + (1 if step > 0 else -1))
                                        % len(files)]
            return
        vals = st.knobs_for(mod)
        hi = rig.knob_max(mod, name)
        if abs(step) == 1:
            step = self._accel(step, name, hi)
        vals[name] = max(0, min(hi, vals.get(name, 0) + step))

    def move_row(self, step):
        """Reorder the loaded pane -- chooser ORDER is the panel's row order,
        so this is a real edit, not a view preference."""
        st = self.app.state
        rows = self.loaded_rows()
        if not rows or self.cur[LOADED] >= len(rows):
            return
        i = self.cur[LOADED]
        st.move(rows[i].key, step)
        self.cur[LOADED] = max(0, min(len(rows) - 1, i + step))
        self.schedule_sync()      # placement order changes the image

    def action_add_remove(self):
        st = self.app.state
        if self.pane == AVAILABLE:
            rows = self.avail_rows()
            mod = rows[min(self.cur[AVAILABLE], len(rows) - 1)]
            if mod.key in st.sel:
                # ⚠️ THIS USED TO REMOVE IT, and that cost a chongbong user
                # both servers. A ✓ in the LIBRARY means "already in the
                # image", so `enter` there reads as "select this", not
                # "throw it out" -- and once the first server was gone the ▸
                # had moved onto the OTHER one, so re-adding the first
                # swapped the second away. One keystroke, both servers lost,
                # and nothing on screen said that was the deal.
                # The library ADDS. LOADED removes. Point at the row.
                self.pane = LOADED
                self.cur[LOADED] = st.order.index(mod.key)
                st.msg = (f"{disp(mod)} is already in the image — "
                          f"enter here removes it")
                self.rerender()
                return
            else:
                # ⚠️ THIS USED TO SWAP: the module took the ▸ row's slot and
                # that row was dropped. The justification was "an image is a
                # fixed budget, so putting something in means taking
                # something out" -- which is the LEDGER's scarcity imported
                # into the operator's gesture, where it does not apply.
                # Rows are not the scarce thing: the long-list cave holds 31
                # of them, and a STOCK row costs zero words (no code placed,
                # no descriptor cloned). Only WORDS are scarce, and only for
                # modules of ours. So add, and let the budget speak up if it
                # is actually breached -- which is what the ⚠ line is for.
                st.insert_at(mod.key, len(st.order))
                st.msg = f"added {disp(mod)}"
                st.msg += self.ensure_fallback()
            st.loaded_name = ""
            self.schedule_sync()
        elif self.pane == LOADED:
            rows = self.loaded_rows()
            if not rows or self.cur[LOADED] >= len(rows):
                return
            mod = rows[self.cur[LOADED]]
            st.toggle(mod.key)
            st.loaded_name = ""
            st.msg = f"removed {disp(mod)}"
            self.cur[LOADED] = max(0, self.cur[LOADED] - 1)
            self.schedule_sync()
        self.rerender()

    def ensure_fallback(self):
        """Satisfy the fallback rule rather than demanding a trade for it.

        A chooser row costs nothing (32 fit in the long cave), so making the
        operator sacrifice an effect for SEND was an invention of this UI,
        not a constraint of the image. Add it and say so in four words.

        This is all that survives of knock_ons(), which also REPORTED the
        buffer clashes and the word budget into the status line. Those two
        belong on the ⚠ line beside the rows they are about, where they are
        re-derived every render instead of being a snapshot of the moment
        one swap happened.
        """
        st = self.app.state
        if not any("no fallback" in p for p in st.problems()):
            return ""
        send = st.mods.get("SEND")
        if send is None or send.key in st.sel:
            return ""
        st.insert_at(send.key, len(st.order))
        return " · added Send as the fallback"

    def untouched_stock(self, probs):
        """Is this the LAUNCH state rather than a mistake?

        An untouched stock chooser cannot build and is documented not to
        pretend it can (state.load_stock): a remix must name a fallback for
        the ids it does not implement, and no stock effect is a safe one --
        it would PROCESS the unknown id rather than pass it. But that is the
        state the bench OPENS in, so reporting it as ⚠ makes a fresh launch
        look broken. Say what the next move is instead. The moment a module
        of ours goes in, SEND comes with it and this stops applying.
        """
        return (bool(probs)
                and all("no fallback" in p for p in probs)
                and not any(not m.is_stock for m in self.app.state.selected))

    def blockers(self, probs):
        """The modules whose removal would clear the ⚠, if that is the shape
        of the problem.

        A buffer clash is the one that costs four effects at once: FLANGER,
        CHORUS, SPATIALIZER and COMB each take a per-track instance buffer at
        exactly the addresses ChonVerb's tank and BongDelay's line hardcode.
        Naming them was already better than four walls of text -- but naming
        them still hands the operator a chore. `x` does it.
        """
        st = self.app.state
        names = set()
        for p_ in probs:
            if "stock instance buffer" not in p_:
                continue
            # "stock instance buffer: flanger and chonverb both claim ..."
            names.add(p_.split(":", 1)[1].split(" and ")[0].strip())
        out = [m for m in st.selected
               if m.is_stock and m.name.lower() in names]
        # A DONOR ROW WHOSE WORDS THIS SELECTION TOOK. The build refuses it
        # by name ("PLATE REV is listed in the chooser but this selection
        # places code over it"), and that verdict is exact -- only the
        # placement knows where the cursor stopped -- so read it rather than
        # predicting it here.
        if self.sync_error:
            out += [m for m in st.selected
                    if m.is_stock and m.key in stock.CONSUMED
                    and f"{m.key} is listed" in self.sync_error]
        return out

    def action_fix(self):
        """Apply the ⚠'s own advice."""
        st = self.app.state
        gone = self.blockers(st.problems())
        if not gone:
            gone = self.blockers([])
        if not gone:
            st.msg = "nothing here that removing a row would fix"
            self.rerender()
            return
        for m in gone:
            st.toggle(m.key)
        st.loaded_name = ""
        st.msg = "removed " + ", ".join(disp(m) for m in gone)
        self.cur[LOADED] = min(self.cur[LOADED], max(len(st.order) - 1, 0))
        self.schedule_sync()
        self.rerender()

    def _clash(self, probs):
        """One readable, IMPERATIVE sentence for whatever stands.

        A buffer clash is the expensive one and the ledger states it a PAIR
        at a time -- adding ChonVerb to a stock chooser yields four
        near-identical sentences (FLANGER, CHORUS, SPATIALIZER and COMB all
        take a per-track instance buffer at the addresses its tank
        hardcodes). Four walls of text do not read as "remove those four".
        """
        if not probs:
            return ""
        buf = [p for p in probs if "stock instance buffer" in p]
        if buf:
            gone = self.blockers(probs)
            if gone:
                # NAME THE CULPRIT AND COUNT THEM. Listing seven effects
                # took four lines of the pane and still did not say WHY or
                # WHICH module was doing it -- "why did adding nimbus remove
                # so many?" is the question it produced. The list is one
                # keystroke away and the reason is what is actually wanted.
                # BOTH: the cause AND the names. Listing seven names alone
                # produced "why did adding nimbus remove so many?"; replacing
                # them with a count alone produced "it's worse now that it
                # doesn't show which ones". The reason belongs first because
                # it is the question, and the list belongs after it because
                # it is the answer's evidence.
                st = self.app.state
                pin = [m for m in st.selected
                       if getattr(m, "claims", None) is not None
                       and m.claims.owns_fx2_buffers]
                who = disp(pin[0]) if pin else "this module"
                return (f"{who} pins the buffer these {len(gone)} allocate — "
                        f"x removes " + ", ".join(disp(m) for m in gone))
            names = [p.split(":", 1)[1].split(" and ")[0].strip().upper()
                     for p in buf]
            return "also remove " + ", ".join(names)
        first = probs[0]
        if "exceeds" in first:
            return first + " — remove something else"
        if "no fallback" in first:
            return "needs a fallback — press f to choose one"
        return first

    def action_stock(self):
        self.app.state.load_stock()
        self.cur = [0, 0, 0]
        self.schedule_sync()
        self.rerender()

    def action_fallback(self):
        st = self.app.state
        opts = [(m.key, f"{m.name} (0x{m.menu.fx2_id:02x})")
                for m in st.menu_modules]
        if not opts:
            st.msg = "nothing with a chooser row to fall back to"
            self.rerender()
            return

        def done(key):
            if key:
                st.fallback = key
                st.msg = f"unimplemented ids alias to {key}"
                self.schedule_sync()
            self.rerender()
        self.app.push_screen(Chooser("unimplemented ids alias to:", opts), done)

    def action_source_dir(self):
        """Point the SOURCE row at another folder, and remember it.

        A bench is used on whatever material is to hand; out/dry/ is a good
        default, not a permanent one. Remembered in out/_audition/
        workbench.json, and WORKBENCH_SOURCES overrides both.
        """
        st = self.app.state
        cur = source_dir()

        def chosen(text):
            if not text:
                return
            # RESOLVED before it is stored: a relative path would be read
            # back against whatever directory the workbench is next started
            # from, and `make remix` being run from the repo root is a
            # convention, not a guarantee.
            d = pathlib.Path(text.strip()).expanduser()
            d = d.resolve() if d.exists() else d
            if not d.is_dir():
                st.msg = f"not a directory: {d}"
            elif not sorted(d.glob("*.wav")):
                st.msg = f"no .wav files in {d}"
            else:
                cfg = load_config()
                cfg["source_dir"] = str(d)
                save_config(cfg)
                files = wav_sources(d)
                self.app.source = files[0] if files else None
                st.msg = f"{len(files)} wavs from {d}"
            self.rerender()
        self.app.push_screen(
            TextPrompt("source folder for the SOURCE row:", str(cur)), chosen)

    def action_help(self):
        self.app.push_screen(HelpScreen("bench"))

    # ---- audio -----------------------------------------------------------
    def action_render(self, mark=None):
        app, st = self.app, self.app.state
        mod = self.selected_module()
        if mod is None or rig.category(mod) == rig.SYSTEM:
            st.msg = "that module is plumbing — nothing to hear"
        elif app.source is None:
            st.msg = f"no source wav in {source_dir()} — d changes folder"
        elif app.rendering:
            st.msg = "a render is already running"
        else:
            # An A/B must compare EFFECTS, so B is rendered on A's source
            # rather than on whatever the SOURCE row happens to say now.
            src = app.source
            if mark == "B" and "A" in app.marks:
                src = app.ab_source or src
            elif mark is None:
                app.ab_source = None
            self.render_worker(mod, dict(st.knobs_for(mod)), src, mark)
        self.rerender()

    @work(thread=True, exclusive=True, group="render")
    def render_worker(self, mod, values, source, mark=None):
        app = self.app

        def log(msg):
            app.state.msg = msg
            app.call_from_thread(self.rerender)
        app.rendering = True
        log(f"rendering {mod.name} on {source.name} ...")
        try:
            path = audition.render(mod.key, values, source, log=log)
        except RuntimeError as e:
            app.rendering = False
            log(str(e))
            return
        app.rendering = False
        changed = {n: v for n, v in values.items()
                   if v != rig.default_knobs(mod).get(n)}
        desc = " ".join(f"{n}={v}" for n, v in changed.items()) or "defaults"
        label = f"{disp(mod)} · {desc}"
        app.history.append((label, path))
        app.ab_source = source
        if mark:
            app.marks[mark] = (label, path)
            audition._journal({"event": "mark", "which": mark,
                               "label": label, "out": path.name})
            other = app.marks.get("A" if mark == "B" else "B")
            app.state.msg = (f"{mark} = {label}"
                             + (f"   ·   , and . to A/B against "
                                f"{other[0]}" if other else ""))
        else:
            app.state.msg = f"rendered → {path.name}"
        app.call_from_thread(app.play, path)
        app.call_from_thread(self.rerender)

    def action_play(self):
        app = self.app
        if app.history:
            label, path = app.history[-1]
            app.play(path)
            app.state.msg = f"playing {label}"
        else:
            app.state.msg = "nothing rendered yet"
        self.rerender()

    def action_mark(self, which):
        """Park the last render as A or B.

        The A/B that matters in a REMIXER is not "two renders ago vs now" --
        it is "the box's effect vs mine", which is the whole question an
        upgraded LO-FI asks. So `a` parks what you just heard and `b`
        RE-RENDERS the effect the cursor is on now, on the same source, so
        the pair is always two effects rather than two accidents of history.
        """
        app = self.app
        if which == "A":
            if not app.history:
                app.state.msg = "nothing rendered yet — r first"
                self.rerender()
                return
            label, path = app.history[-1]
            app.marks["A"] = (label, path)
            app.state.msg = f"A = {label} · now point at another effect and b"
            audition._journal({"event": "mark", "which": "A",
                               "label": label, "out": path.name})
            self.rerender()
            return
        # B: render whatever the cursor is on, against the same source.
        if "A" not in app.marks:
            app.state.msg = "mark A first (a), then point at the rival and b"
            self.rerender()
            return
        self.action_render(mark="B")

    def action_play_mark(self, which):
        app = self.app
        got = app.marks.get(which)
        if got:
            label, path = got
            app.play(path)
            app.state.msg = f"{which}: {label}"
        else:
            app.state.msg = f"no {which} yet"
        self.rerender()

    # ---- build, measure, load, save --------------------------------------
    def action_build(self, target):
        st = self.app.state
        probs = st.problems()
        if probs:
            st.msg = f"refusing: {probs[0]}"
            self.rerender()
            return
        st.msg = f"make {target} on the live selection..."
        self.rerender()
        self.build_worker(target)

    @work(thread=True, exclusive=True, group="build")
    def build_worker(self, target):
        st = self.app.state
        log = self.query_one("#log", RichLog)
        self.app.call_from_thread(setattr, log, "display", True)
        name = st.scratch_remix()
        try:
            p = subprocess.Popen(["make", target, f"REMIX={name}"], cwd=ROOT,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, text=True)
            for line in p.stdout:
                self.app.call_from_thread(log.write, line.rstrip())
            rc = p.wait()
        finally:
            st.scratch_cleanup()
        st.msg = f"make {target}: {'OK' if rc == 0 else f'FAILED (rc {rc})'}"
        # `make check` shells out to build_bus.py several times WITHOUT
        # XBUS/SPEC (verify_burn does), so whatever it leaves at the
        # artifact's path is not this selection. Re-sync rather than trust
        # it -- the same reason the Makefile's own check target rebuilds.
        self.synced = None
        self.app.call_from_thread(self.rerender)

    def action_load(self):
        names = [n for n in registry.remix_names() if not n.startswith("_")]

        def done(name):
            if name == "stock":
                self.app.state.load_stock()
            elif name:
                self.app.state.load(name)
            self.cur = [0, 0, 0]
            self.schedule_sync()
            self.rerender()
        self.app.push_screen(
            Chooser("load:", [("stock", "stock (an unmodified unit)")]
                    + [(n, n) for n in names]), done)

    def action_save(self):
        st = self.app.state
        probs = st.problems()
        if probs:
            st.msg = f"refusing to save: {probs[0]}"
            self.rerender()
            return

        def named(name):
            import re
            if not name:
                return
            if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
                st.msg = "name must be lowercase [a-z][a-z0-9_]*"
                self.rerender()
                return

            def documented(doc):
                pth = ROOT / f"remixes/{name}.py"
                pth.write_text(st.as_remix(
                    name, doc or "a selection composed in the workbench"))
                st.loaded_name = name
                st.msg = f"wrote remixes/{name}.py"
                self.rerender()
            self.app.push_screen(TextPrompt("one-line description:"),
                                 documented)
        self.app.push_screen(TextPrompt("save as remix:"), named)


# ---- the app ---------------------------------------------------------------
class Workbench(App):
    TITLE = "remix workbench"
    CSS = """
    /* The panes must FILL the row for their left borders to run the whole
       way down -- a Static is only as tall as its text, so the dividers
       stopped wherever the shortest column ran out. */
    Horizontal { height: 1fr; }
    #pane_avail { width: 32; padding: 0 1; height: 100%; }
    #pane_load  { width: 40; padding: 0 1; height: 100%;
                  border-left: dashed $surface; }
    #col_unit   { width: 1fr; height: 100%;
                  border-left: dashed $surface; }
    #pane_unit  { height: 1fr; padding: 0 1; }
    #pane_budget { height: auto; padding: 0 1;
                   border-top: dashed $surface; }
    #status { height: 1; padding: 0 1; }
    #log { height: 12; border-top: dashed $surface; }
    """
    MODES = {"bench": BenchScreen}
    # App-level so it works from every view; modals handle their own escape
    # first, and no screen binds it, so escape is unambiguous.
    BINDINGS = [Binding("escape", "stop_play", "stop audio")]

    def __init__(self):
        super().__init__()
        self.state = State()
        self.source = (wav_sources() or [None])[0]
        self.history = []                  # [(label, path)]
        self.marks = {}                    # "A"/"B" -> (label, path)
        self.ab_source = None              # the wav an A/B pair shares
        self.status = ""                   # state.msg is the live line now
        self.rendering = False
        self.boot = None                   # the booted image, or None
        self.player = None                 # the running afplay

    def on_mount(self):
        # ansi-dark renders in the TERMINAL's own 16-color palette, so the
        # workbench wears whatever theme Alacritty wears instead of Textual's
        # truecolor default. WORKBENCH_THEME picks any built-in Textual theme
        # (e.g. gruvbox, nord, textual-dark) for anyone who wants otherwise.
        import os
        from textual.theme import BUILTIN_THEMES
        want = os.environ.get("WORKBENCH_THEME", "ansi-dark")
        self.theme = want if want in BUILTIN_THEMES else "ansi-dark"
        self.switch_mode("bench")

    def play(self, path):
        """afplay, one at a time -- a new play stops the old."""
        if shutil.which("afplay") is None:
            self.status = "afplay not found — cannot play (macOS only)"
            return
        self.stop_play()
        self.player = subprocess.Popen(
            ["afplay", str(path)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def stop_play(self):
        """-> True if something was actually playing."""
        if self.player and self.player.poll() is None:
            self.player.terminate()
            return True
        return False

    def action_stop_play(self):
        self.state.msg = ("stopped" if self.stop_play()
                          else "nothing playing")
        scr = self.screen
        if hasattr(scr, "rerender"):
            scr.rerender()

    def on_unmount(self):
        # Quitting must not leave a headless afplay running out the render.
        self.stop_play()


if __name__ == "__main__":
    if not sys.stdout.isatty():
        sys.exit("the remix workbench needs a terminal (try: make remix)")
    Workbench().run()
