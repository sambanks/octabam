#!/usr/bin/env python3
"""The remix workbench, organized the way an Octatrack user thinks: TRACKS.

    make remix          (or: .venv/bin/python3 tools/remix/app.py)

Three views, one rig:

  RIG (home)   eight tracks, an effect on each. Pick a track, see the
               effect's real param pages (manifest names, page 1 = knobs
               A-F), dial values, render through the DSP emulator, hear it,
               A/B renders. This is the trial-a-sound loop and the reason
               the workbench exists.
  REMIX        the composer: which modules the IMAGE contains, grouped as an
               operator meets them -- bus servers (with their track range),
               inserts (any track), system plumbing. Collisions, fit, save/
               load, build and check -- on the LIVE selection, no save needed.
  EMU          the built image booted in the Tier-0 ColdFire emulator
               (docs/EMU.md), showing the firmware's own menu and param page
               renders for the rig's selected track. Booting IS the no-flash
               gate; the boot is cached until the image changes.

The model layers are headless and live next door: state.py (the composer),
rig.py (tracks), audition.py (rendering). This file is only the shell.
Textual rather than curses: the workbench is already venv-hosted for the
emulator, and the frontend rewrite is where hand-rolled layout stopped
paying its way.
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys

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

from remix import audition, registry, rig  # noqa: E402
from remix.state import (BUILT_IMAGE, DONOR_WORDS, ROOT,  # noqa: E402
                         STOCK_ROOTS, State)

def step_label(mod, name, v):
    """A select's value as the manifest labels it, else the raw number."""
    lab = rig.knob_labels(mod, name)
    return lab[v] if lab and v < len(lab) else str(v)


def wav_sources():
    """Source WAVs to audition: out/dry/ -- the curated DRY set (31 Aug 2026;
    test_audio + demo_sources are full of processed renders and made the
    browser unusable). Falls back to the old dirs only when out/dry is
    missing or empty (a fresh tree before anyone copies sources in)."""
    d = ROOT / "out" / "dry"
    if d.is_dir():
        out = sorted(d.glob("*.wav"))
        if out:
            return out
    out = []
    for sub in ("test_audio", "demo_sources"):
        d = ROOT / "out" / sub
        if d.is_dir():
            out += sorted(d.glob("*.wav"))
    return out


# ---- tiny modals -----------------------------------------------------------
class TextPrompt(ModalScreen[str]):
    """One-line text input; dismisses with '' on escape."""

    CSS = """
    TextPrompt { align: center middle; }
    #box { width: 60; height: auto; border: round $primary; padding: 1; }
    """

    def __init__(self, question):
        super().__init__()
        self.question = question

    def compose(self) -> ComposeResult:
        with Vertical(id="box"):
            yield Static(self.question)
            yield Input()

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
    "rig": """[bold]THE RIG — your bench, not the unit[/]

Assign an effect to a track, dial its knobs, render a source wav through
the effect's real DSP code and hear it. Audio comes from the local DSP
emulator (~6x real time); nothing here touches hardware.

[bold]keys[/]
  1-8       select track             enter      pick the track's effect
  up/down   move between rows        left/right adjust (shift = coarse)
  r         render + play            space      replay the last render
  a / b     mark the last render     , / .      replay mark A / B
  esc       stop audio               backspace  clear the effect
  x         the remix composer       e          the emulated unit

[bold]why some effects are missing on a track[/]
The two BUS EFFECTS each live on one of the unit's two DSP cores:
ChonVerb serves tracks 5-8 and BongDelay tracks 1-4 (measured, and
inverted from what you'd guess). INSERTS run on any track. The knob
rows mirror the unit's two FX2 SETUP pages: page 1 = encoders A-F,
page 2 alternates knob/select. The dim ? line explains whichever
knob the cursor is on.""",
    "remix": """[bold]THE COMPOSER — what the firmware image contains[/]

A remix is a named selection of modules built into one firmware image.
Toggle modules here; the right panel answers, continuously: what the
FX2 chooser will show on the unit, whether anything collides (the same
ledger the build runs), and whether the DSP fits the 2724-word donor
region (w assembles for real numbers).

Effects the image leaves out don't vanish on the unit: an old project
selecting an absent id is aliased to the FALLBACK (normally SEND), so
it degrades to a send instead of noise. * marks an explicit fallback,
~ an automatic one.

[bold]what happens to the stock effects[/]
Every image replaces the whole FX2 chooser, but only THREE stock
effects are consumed -- PLATE, SPRING and DARK REV, whose code is the
donor region the modules pack into. The other eleven keep their code
and knobs in every image and only lose their row. Toggle one under
STOCK FX2 to keep its row: it costs nothing. Four of them (SPAT, FLNG,
CHOR, COMB) take a per-track buffer where the servers keep theirs, so
they are refused beside ChonVerb, Nimbus or BongDelay. Row order is
selection order; [ and ] move the cursored module. More than seven
rows and the chooser scrolls, as stock's does.

[bold]keys[/]
  space  toggle module        f  make it the fallback
  [ / ]  move earlier/later   w  assemble + measure
  b      build the selection  c  build + full check
  l      load a saved remix   s  save this selection
  v      rig                  e  emulated unit""",
    "emu": """[bold]THE EMULATED UNIT — the real firmware, screen only[/]

Your built image, booted in a local ColdFire emulator, drawing its own
screens: the MAIN MENU (patched-in entries render exactly as the unit
would), the FX2/FX1 SETUP pages and the PLAYBACK page. There is no
audio and no key matrix — this view is the no-flash confidence check:
does the image boot cleanly, does the panel draw what the manifests
promised.

Knob VALUES draw as dial graphics the text capture cannot read, so the
rig's numbers are always the truth for values. The boot is cached and
repeats only when the image changes.

[bold]keys[/]
  m  main menu      f  FX2 (follows the rig's track + effect)
  o  FX1 (stock)    p  playback page
  1-8  track        up/down  menu cursor   left/right  cycle""",
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


# ---- RIG -------------------------------------------------------------------
class RigScreen(Screen):
    """Eight tracks; the selected one shows its pages and renders."""

    BINDINGS = [
        Binding("r", "render", "render+hear"),
        Binding("space", "play", "play last"),
        Binding("enter", "pick_effect", "effect"),
        Binding("backspace", "clear_effect", "clear fx", show=False),
        Binding("a", "mark('A')", "mark A"),
        Binding("b", "mark('B')", "mark B"),
        Binding("comma", "play_mark('A')", "play A"),
        Binding("full_stop", "play_mark('B')", "play B"),
        Binding("x", "app.switch_mode('remix')", "remix"),
        Binding("e", "app.switch_mode('emu')", "emu"),
        Binding("question_mark", "help('rig')", "what is this?"),
        Binding("q", "app.quit", "quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Static(id="strip")
        yield Static(id="detail")
        yield Static(id="history")
        yield Static(id="status")
        yield Footer()

    def on_mount(self):
        self.cursor = 0                     # row in the detail list
        self.rerender()

    # ---- the rows the cursor walks (SOURCE, WET, then the knobs) --------
    def rows(self):
        app = self.app
        mod = app.rig.effect(app.track)
        rows = [("SOURCE", None), ("WET", None)]
        if mod:
            for name, slot in sorted(mod.knob_map().items(),
                                     key=lambda kv: kv[1]):
                if mod.params[slot].active:
                    rows.append((name, slot))
        return rows

    def rerender(self):
        app = self.app
        r = app.rig
        # -- strip ---------------------------------------------------------
        cells = []
        for t in rig.TRACKS:
            mod = r.effect(t)
            name = (mod.menu.abbr.decode("latin1") if mod and mod.menu
                    else "--")
            sel = "reverse bold" if t == app.track else "dim"
            cells.append(f"[{sel}] T{t} {name:<5}[/]")
        self.query_one("#strip", Static).update(
            "  ".join(cells) + "\n" + "─" * 78)

        # -- detail --------------------------------------------------------
        mod = r.effect(app.track)
        lines = []
        tr = f"T{app.track}"
        if mod:
            full = mod.menu.fullname.decode("latin1")
            lines.append(f"[bold]{tr} · {escape(full)}[/]   "
                         f"(tracks {rig.track_range(mod).start}-"
                         f"{rig.track_range(mod).stop - 1})")
        else:
            avail = ", ".join(m.name for m in rig.available(app.track))
            lines.append(f"[bold]{tr} · no effect[/]   (here: {avail})")
        lines.append("")
        rows = self.rows()
        for i, (name, slot) in enumerate(rows):
            cur = i == self.cursor
            mark = "[reverse]" if cur else ""
            end = "[/]" if cur else ""
            if name == "SOURCE":
                src = app.source.name if app.source else "(none — add wavs "\
                    "to out/dry/)"
                lines.append(f" {mark}SOURCE  {escape(src)}{end}")
            elif name == "WET":
                w = "WET only (reverb render)" if app.wet else "full (dry+wet)"
                lines.append(f" {mark}RENDER  {w}{end}")
            else:
                v = r.knobs[app.track].get(name, 0)
                hi = rig.knob_max(mod, name)
                if hi < 8:                                # a select
                    val = f"{step_label(mod, name, v):<6}"
                    bar = "·" * 16
                else:
                    val = f"{v:>3}   "
                    fill = round(16 * v / max(hi, 1))
                    bar = "#" * fill + "." * (16 - fill)
                page = "1" if slot < 6 else "2"
                knob = "ABCDEF"[slot % 6]
                lines.append(f" {mark}{name:<6} {val} \\[{bar}]  "
                             f"p{page}·{knob}{end}")
        # -- the "what is this?" line for whatever the cursor is on ------
        name, slot = rows[self.cursor]
        if name == "SOURCE":
            hint = ("the wav rendered through the effect -- drop files in "
                    "out/dry/; left/right cycles")
        elif name == "WET":
            hint = ("WET = the reverb's wet alone (exact dry subtraction); "
                    "other effects always render their normal output")
        elif mod:
            hint = rig.knob_doc(mod, name) or "(this knob has no doc yet)"
        else:
            hint = ""
        lines.append("")
        lines.append(f"[dim]? {escape(hint)}[/]")
        if mod and mod.name == "chonverb":
            lines.append("[dim]MODE renders as its own image (cached per "
                         "mode); WET applies to the reverb only.[/]")
        self.query_one("#detail", Static).update("\n".join(lines))

        # -- history -------------------------------------------------------
        h = ["[bold]RENDERS[/]"]
        for i, (label, path) in enumerate(reversed(app.history[-6:])):
            marks = "".join(m for m, p in app.marks.items() if p == path)
            h.append(f" {('\\[' + marks + '] ') if marks else '    '}"
                     f"{escape(label)}")
        self.query_one("#history", Static).update(
            "\n".join(h) if len(h) > 1 else
            "[dim]r renders the selected track; a/b mark a render, "
            ", . replay the marks[/]")
        self.query_one("#status", Static).update(
            f"[dim]{escape(app.status)}[/]")

    # ---- input ----------------------------------------------------------
    def on_key(self, ev):
        app = self.app
        if ev.key in tuple("12345678"):
            app.track = int(ev.key)
            self.cursor = 0
            self.rerender()
            return
        rows = self.rows()
        if ev.key in ("down", "j"):
            self.cursor = min(len(rows) - 1, self.cursor + 1)
        elif ev.key in ("up", "k"):
            self.cursor = max(0, self.cursor - 1)
        elif ev.key in ("left", "right", "h", "l",
                        "shift+left", "shift+right"):
            step = 1 if ev.key in ("right", "l", "shift+right") else -1
            if "shift" in ev.key:
                step *= 10
            self.adjust(rows[self.cursor], step)
        else:
            return
        self.rerender()

    def adjust(self, row, step):
        app = self.app
        name, slot = row
        if name == "SOURCE":
            files = wav_sources()
            if files:
                i = files.index(app.source) if app.source in files else 0
                app.source = files[(i + step) % len(files)]
        elif name == "WET":
            app.wet = not app.wet
        else:
            mod = app.rig.effect(app.track)
            hi = rig.knob_max(mod, name)
            v = app.rig.knobs[app.track].get(name, 0)
            app.rig.knobs[app.track][name] = max(0, min(hi, v + step))
            app.rig.save()

    def action_pick_effect(self):
        app = self.app
        opts = [(m.key, f"{escape(m.menu.fullname.decode('latin1')):<13} "
                        f"\\[{rig.category(m)}]\n[dim]{escape(m.doc)}[/]")
                for m in rig.available(app.track)] + [("__none__", "(none)")]

        def done(key):
            if key:
                app.rig.set_effect(app.track,
                                   None if key == "__none__" else key)
                app.rig.save()
                self.cursor = 0
                self.rerender()
        app.push_screen(Chooser(f"FX2 on T{app.track}:", opts), done)

    def action_clear_effect(self):
        self.app.rig.set_effect(self.app.track, None)
        self.app.rig.save()
        self.cursor = 0
        self.rerender()

    def action_help(self, view):
        self.app.push_screen(HelpScreen(view))

    def action_render(self):
        app = self.app
        mod = app.rig.effect(app.track)
        if mod is None:
            app.status = "no effect on this track — enter picks one"
        elif app.source is None:
            app.status = "no source wav — put some in out/dry/"
        elif app.rendering:
            app.status = "a render is already running"
        else:
            self.render_worker(mod, dict(app.rig.knobs[app.track]),
                               app.source, app.wet, app.track)
        self.rerender()

    @work(thread=True, exclusive=True, group="render")
    def render_worker(self, mod, values, source, wet, track):
        app = self.app

        def log(msg):
            app.call_from_thread(self.set_status, msg)
        app.rendering = True
        log(f"rendering {mod.name} on {source.name} ...")
        try:
            path = audition.render(mod.key, values, source, wet=wet,
                                   label=f"T{track}", log=log)
        except RuntimeError as e:
            app.rendering = False
            log(str(e))
            return
        app.rendering = False
        changed = {n: v for n, v in values.items()
                   if v != rig.default_knobs(mod).get(n)}
        desc = " ".join(f"{n}={v}" for n, v in changed.items()) or "defaults"
        app.history.append((f"T{track} {mod.name} · {desc}", path))
        app.call_from_thread(self.set_status, f"rendered → {path.name}")
        app.call_from_thread(app.play, path)
        app.call_from_thread(self.rerender)

    def set_status(self, msg):
        self.app.status = msg
        self.rerender()

    def action_play(self):
        app = self.app
        if app.history:
            app.play(app.history[-1][1])
            app.status = f"playing {app.history[-1][1].name}"
        else:
            app.status = "nothing rendered yet"
        self.rerender()

    def action_mark(self, which):
        app = self.app
        if app.history:
            label, path = app.history[-1]
            app.marks[which] = path
            app.status = f"marked {which}: {label}"
            audition._journal({"event": "mark", "which": which,
                               "label": label, "out": path.name})
        self.rerender()

    def action_play_mark(self, which):
        app = self.app
        p = app.marks.get(which)
        if p:
            app.play(p)
            app.status = f"playing {which}: {p.name}"
        else:
            app.status = f"no {which} mark yet — render, then press "\
                         f"{'a' if which == 'A' else 'b'}"
        self.rerender()


# ---- REMIX -----------------------------------------------------------------
class RemixScreen(Screen):
    """The composer: what the image contains, whether it builds, what it costs.

    Grouped the way an operator meets the modules -- servers with their track
    range, inserts, then the system plumbing that never sits on a track."""

    BINDINGS = [
        Binding("space", "toggle", "toggle"),
        Binding("f", "fallback", "fallback"),
        Binding("w", "measure", "words"),
        Binding("b", "build('bus')", "build"),
        Binding("c", "build('check')", "check"),
        Binding("l", "load", "load"),
        Binding("s", "save", "save"),
        Binding("v", "app.switch_mode('rig')", "rig"),
        Binding("e", "app.switch_mode('emu')", "emu"),
        Binding("question_mark", "help('remix')", "what is this?"),
        Binding("q", "app.quit", "quit"),
    ]

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Static(id="mods")
            yield Static(id="panel")
        yield RichLog(id="log", max_lines=400, wrap=True)
        yield Footer()

    def on_mount(self):
        self.cursor = 0
        log = self.query_one("#log", RichLog)
        log.display = False
        self.rerender()

    def grouped(self):
        """[(key or None, line-label)] with None rows as group headers."""
        st = self.app.state
        cats = {rig.SERVER: [], rig.INSERT: [], rig.STOCK: [],
                rig.SYSTEM: []}
        for k in st.keys:
            cats[rig.category(st.mods[k])].append(k)
        # Stock rows in stock's own chooser order, not alphabetical.
        from remix import stock
        cats[rig.STOCK] = [m.key for m in stock.MODULES]
        out = []
        for cat, title in ((rig.SERVER, "BUS EFFECTS (one per payload)"),
                           (rig.INSERT, "INSERTS (any track)"),
                           (rig.STOCK, "STOCK FX2 (in every image; "
                                       "toggle = keep its row, free)"),
                           (rig.SYSTEM, "SYSTEM (never on a track)")):
            if cats[cat]:
                out.append((None, title))
                out += [(k, "") for k in cats[cat]]
        return out

    def key_rows(self):
        return [i for i, (k, _) in enumerate(self.grouped()) if k]

    def rerender(self):
        st = self.app.state
        rows = self.grouped()
        krows = self.key_rows()
        self.cursor = min(self.cursor, len(krows) - 1)
        lines = ["[bold]THE IMAGE[/] — modules composed into the firmware\n"]
        for i, (k, title) in enumerate(rows):
            if k is None:
                lines.append(f"[bold dim]{title}[/]")
                continue
            m = st.mods[k]
            on = "x" if k in st.sel else " "
            fb = ("*" if st.fallback == k
                  else "~" if k == st.eff_fallback else " ")
            tr = rig.track_range(m)
            trs = f"T{tr.start}-{tr.stop - 1}" if len(tr) else "     "
            wd = (" stock" if m.is_stock
                  else f"{st.words[k]:>5}w" if k in st.words else "     -")
            cur = krows[self.cursor] == i
            mark = "[reverse]" if cur else ("" if k in st.sel else "[dim]")
            end = "[/]" if mark else ""
            lines.append(f" {mark}\\[{on}]{fb} {m.name:<11}{trs} {wd}{end}")
        lines.append("")
        lines.append("[bold dim]REMIXES[/] [dim]" + " ".join(
            n for n in registry.remix_names() if not n.startswith("_"))
            + "[/]")
        lines.append("")
        lines.append(f"[dim]? {escape(st.mods[self.current_key()].doc)}[/]")
        self.query_one("#mods", Static).update("\n".join(lines))

        # -- right panel: the unit's FX2 menu + fit + problems --------------
        p = ["[bold]THE FX2 MENU[/] — as the unit will show it\n"]
        for i, m in enumerate(st.menu_modules):
            star = ""
            if m.key == st.eff_fallback:
                star = (" ← fallback (auto)" if st.fallback_is_auto
                        else " ← fallback")
            p.append(f"  {i}. {escape(m.menu.fullname.decode('latin1')):<13} "
                     f"0x{m.menu.fx2_id:02x}{star}")
        from remix import stock
        n_menu = len(st.menu_modules)
        if n_menu > 7:
            p.append(f"  [dim]{n_menu} rows: the panel shows 7 and scrolls[/]")
        absent = [m for m in st.mods.values()
                  if m.menu is not None and m.key not in st.sel
                  and not m.is_stock]
        if absent and st.eff_fallback:
            p.append(f"  [dim]{len(absent)} absent module id(s) alias to "
                     f"{st.mods[st.eff_fallback].name}[/]")
        hidden = [m.key for m in stock.MODULES if m.key not in st.sel]
        if hidden:
            p.append(f"  [dim]{len(hidden)} stock effects hidden (no row; "
                     f"still run for old projects)[/]")
        p.append(f"  [dim]consumed by every remix: {', '.join(stock.CONSUMED)}"
                 f" — their code is the donor region[/]")
        p.append("")
        dsp = [m for m in st.selected if m.dsp is not None]
        known = [m for m in dsp if m.key in st.words]
        if known:
            total = sum(st.words[m.key] for m in known)
            partial = ("" if len(known) == len(dsp)
                       else f" ({len(known)}/{len(dsp)} measured)")
            fill = min(30, round(30 * total / DONOR_WORDS))
            over = total > DONOR_WORDS
            p.append(f"program: [{'bold red' if over else 'bold'}]{total}[/] "
                     f"of {DONOR_WORDS} words{partial}")
            p.append("[" + "#" * fill + "." * (30 - fill) + "]")
        else:
            p.append("[dim]program: press w to assemble and measure[/]")
        p.append("")
        probs = st.problems()
        if probs:
            p.append(f"[bold red]WILL NOT BUILD ({len(probs)})[/]")
            p += [f"  {escape(x)}" for x in probs]
        else:
            p.append("[bold green]no LEDGER collisions — this selection "
                     "builds[/]")
            p.append("[dim]not checked: the shared 64K window "
                     "(see CLAUDE.md for who owns what)[/]")
            buffered = [m for m in st.selected
                        if m.claims is not None and m.claims.owns_fx2_buffers]
            if buffered:
                p.append(f"[dim]{buffered[0].name} owns Y:0x4000-0xBFFF — "
                         f"the only such module on its core[/]")
        p.append("")
        p.append(f"[dim]{escape(st.msg)}[/]")
        self.query_one("#panel", Static).update("\n".join(p))

    def on_key(self, ev):
        krows = self.key_rows()
        if ev.key in ("down", "j"):
            self.cursor = min(len(krows) - 1, self.cursor + 1)
        elif ev.key in ("up", "k"):
            self.cursor = max(0, self.cursor - 1)
        elif ev.character in ("[", "]"):
            self.app.state.move(self.current_key(),
                                -1 if ev.character == "[" else +1)
        else:
            return
        self.rerender()

    def current_key(self):
        return self.grouped()[self.key_rows()[self.cursor]][0]

    def action_help(self, view):
        self.app.push_screen(HelpScreen(view))

    def action_toggle(self):
        st = self.app.state
        k = self.current_key()
        st.toggle(k)
        if k in st.sel and st.mods[k].is_stock:
            st.msg = f"{k}: stock row kept -- no code, no words, no clone"
        self.rerender()

    def action_fallback(self):
        st = self.app.state
        k = self.current_key()
        if k in st.sel and st.mods[k].menu is not None:
            st.fallback = k
            st.msg = f"fallback: {st.mods[k].name}"
        else:
            st.msg = "the fallback must be selected and have a menu entry"
        self.rerender()

    def action_measure(self):
        st = self.app.state
        st.msg = "assembling..."
        self.rerender()
        self.measure_worker()

    @work(thread=True, exclusive=True, group="build")
    def measure_worker(self):
        st = self.app.state
        ok, msg = st.measure("this selection")
        st.msg = msg
        self.app.call_from_thread(self.rerender)

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
        st.msg = (f"make {target}: {'OK' if rc == 0 else f'FAILED (rc {rc})'}"
                  f" — the built image is this selection")
        if rc == 0:
            self.app.boot = None          # the emu view must re-boot
        self.app.call_from_thread(self.rerender)

    def action_load(self):
        names = [n for n in registry.remix_names() if not n.startswith("_")]

        def done(name):
            if name:
                self.app.state.load(name)
                self.rerender()
        self.app.push_screen(
            Chooser("load remix:", [(n, n) for n in names]), done)

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
                p = ROOT / f"remixes/{name}.py"
                p.write_text(st.as_remix(
                    name, doc or "a selection composed in the workbench"))
                st.msg = f"wrote remixes/{name}.py"
                self.rerender()
            self.app.push_screen(TextPrompt("one-line description:"),
                                 documented)
        self.app.push_screen(TextPrompt("save as remix:"), named)


# ---- EMU -------------------------------------------------------------------
class EmuScreen(Screen):
    """The built image, booted and drawing its own screens (docs/EMU.md)."""

    BINDINGS = [
        Binding("m", "view('menu')", "menu"),
        Binding("f", "view('fx2')", "FX2"),
        Binding("left,right", "noop", "cycle effect"),
        Binding("o", "view('fx1')", "FX1"),
        Binding("p", "view('play')", "playback"),
        Binding("v", "app.switch_mode('rig')", "rig"),
        Binding("x", "app.switch_mode('remix')", "remix"),
        Binding("question_mark", "help('emu')", "what is this?"),
        Binding("q", "app.switch_mode('rig')", "back"),
    ]

    def compose(self) -> ComposeResult:
        yield Static(id="emuhead")
        yield Static(id="lcd")
        yield Static(id="emunote")
        yield Footer()

    def on_mount(self):
        self.view = "fx2"
        self.cursor = 0
        self.eff = {"fx1": 0x04, "play": 1}
        self.rows = []                 # the built image's FX2 chooser
        self.rowi = 0
        self.rows_mtime = None
        self.pending = ""               # what the last selection did
        self.booting = False
        self.ensure_boot()

    def on_screen_resume(self):
        # The rig's selection is this view's default subject.
        self.view = "fx2"
        self.sync_row()
        self.ensure_boot()

    def chooser(self):
        """The built image's FX2 rows, re-read whenever the image changes."""
        mt = BUILT_IMAGE.stat().st_mtime if BUILT_IMAGE.exists() else None
        if mt != self.rows_mtime:
            self.rows, self.rows_mtime = rig.built_chooser(), mt
            self.rowi = 0
            self.sync_row()
        return self.rows

    def sync_row(self):
        """Point the cursor at whatever the rig has on this track, if the
        image offers it -- so entering the view shows the rig's subject and
        cycling starts from there rather than from row 0."""
        mod = self.app.rig.effect(self.app.track)
        if mod is None:
            return
        for i, (_, m) in enumerate(self.rows):
            if m is not None and m.key == mod.key:
                self.rowi = i
                return

    def select_row(self):
        """Write the cycled-to effect back to the RIG, so the emu view and
        the rig are one selection rather than two. Returns a note saying what
        happened -- including the cases where the rig cannot hold it, which
        are NOT errors: the unit's chooser is one list for all eight tracks
        and will happily let you pick any row on any track.
        """
        app = self.app
        if not self.rows:
            return ""
        eid, mod = self.rows[self.rowi]
        if mod is None:
            return f"id 0x{eid:02x} is in the list but no manifest claims it"
        if rig.category(mod) == rig.SYSTEM:
            return (f"{mod.key} is plumbing, not a track effect — the unit "
                    f"lists it, the rig does not hold it")
        if app.track not in rig.track_range(mod):
            tr = rig.track_range(mod)
            return (f"selected on the unit, but {mod.name} is a SERVER on "
                    f"tracks {tr.start}-{tr.stop - 1} — on T{app.track} its "
                    f"id aliases to the fallback and the track becomes a send")
        app.rig.set_effect(app.track, mod.key)
        app.rig.save()
        return f"assigned {mod.key} to T{app.track} — the rig followed"

    def ensure_boot(self):
        app = self.app
        if not BUILT_IMAGE.exists():
            self.query_one("#emuhead", Static).update(
                "[bold]no built image[/] — build one from the REMIX view (b)")
            return
        mtime = BUILT_IMAGE.stat().st_mtime
        if app.boot is not None and app.boot_mtime == mtime:
            self.rerender()
            return
        if not self.booting:
            self.booting = True
            self.query_one("#emuhead", Static).update(
                f"booting {BUILT_IMAGE.name} in the Tier-0 emulator (~4 s)...")
            self.boot_worker(mtime)

    @work(thread=True, exclusive=True, group="boot")
    def boot_worker(self, mtime):
        app = self.app
        try:
            import emu_bringup
            r = emu_bringup.boot(str(BUILT_IMAGE))
        except Exception as e:                       # noqa: BLE001
            r = None
            app.call_from_thread(
                self.query_one("#emuhead", Static).update,
                f"[bold]emulator unavailable[/] — {e} (make emu-setup)")
        self.booting = False
        if r is not None:
            app.boot, app.boot_mtime = r, mtime
            app.call_from_thread(self.rerender)

    def rerender(self):
        app = self.app
        r = app.boot
        if r is None:
            return
        import emu_bringup
        head = (f"[bold]{'BOOTS CLEAN' if r.clean else 'FAULT'}[/] · "
                f"{r.instrs:,} instrs · {r.stopped} · cached until rebuilt")
        self.query_one("#emuhead", Static).update(head)
        note = ""
        if not r.uc or not r.reached_handoff:
            self.query_one("#lcd", Static).update(
                "[bold]did not reach the RTOS handoff — a patch may have "
                "broken early init.[/]")
            self.query_one("#emunote", Static).update("")
            return
        track0 = app.track - 1               # emu_bringup tracks are 0-based
        if self.view == "menu":
            roots = emu_bringup.menu_children(r)
            self.cursor %= max(len(roots), 1)
            draws = emu_bringup.render_menu(r, emu_bringup.MENU_ROOT_DESC,
                                            self.cursor)
            added = [k[0] for k in roots if k[0] not in STOCK_ROOTS]
            note = ("patched-in: " + ", ".join(added)) if added else ""
            title = "MAIN MENU — the firmware's own render"
        elif self.view == "fx2":
            rows = self.chooser()
            if not rows:
                self.query_one("#lcd", Static).update(
                    "[bold]the built image offers no FX2 chooser rows[/] — "
                    "build one from the REMIX view (b)")
                self.query_one("#emunote", Static).update("")
                return
            self.rowi %= len(rows)
            eid, mod = rows[self.rowi]
            draws = emu_bringup.render_fx2(r, track=track0, effect_id=eid)
            name = (mod.menu.fullname.decode("latin1") if mod
                    else f"unclaimed 0x{eid:02x}")
            title = (f"FX2 SETUP — T{app.track}, row {self.rowi + 1}/"
                     f"{len(rows)}: {name} (0x{eid:02x})")
            note = (self.pending or
                    "left/right cycles the image's chooser · 1-8 changes "
                    "track · values draw as dials the string hook cannot "
                    "read, so the rig's numbers are the truth")
            if mod and mod.name == "bongdelay":
                note = ("a SPEC image aliases the delay's DSP to SEND on "
                        "payload A — the page may draw empty; " + note)
        elif self.view == "fx1":
            draws = emu_bringup.render_fx1(r, track=track0,
                                           effect_id=self.eff["fx1"])
            title = (f"FX1 SETUP — T{app.track}, effect "
                     f"0x{self.eff['fx1']:02x} (left/right cycles)")
        else:
            names = ["FLEX", "STATIC", "THRU", "NEIGHBOR"]
            mi = self.eff["play"]
            draws = emu_bringup.render_playback(r, track=track0, machine=mi)
            title = f"PLAYBACK — T{app.track}, {names[mi]} (left/right cycles)"
        grid = emu_bringup.layout_screen(draws)
        lcd = "\n".join(["[bold]" + escape(title) + "[/]", "",
                         "." + "-" * 46 + "."]
                        + ["|" + escape(ln.ljust(46)) + "|" for ln in grid]
                        + ["'" + "-" * 46 + "'"])
        self.query_one("#lcd", Static).update(lcd)
        self.query_one("#emunote", Static).update(f"[dim]{note}[/]")

    def action_help(self, view):
        self.app.push_screen(HelpScreen(view))

    def action_view(self, v):
        self.view = v
        self.rerender()

    def action_noop(self):
        """left/right are handled in on_key; the binding exists so the footer
        advertises them."""

    def on_key(self, ev):
        app = self.app
        self.pending = ""
        if ev.key in tuple("12345678"):
            app.track = int(ev.key)
            if self.view == "fx2":
                self.sync_row()
                self.pending = self.select_row()
        elif self.view == "fx2" and ev.key in ("left", "right", "h", "l"):
            rows = self.chooser()
            if not rows:
                return
            self.rowi = (self.rowi + (1 if ev.key in ("right", "l") else -1)) \
                % len(rows)
            self.pending = self.select_row()
        elif self.view == "menu" and ev.key in ("down", "j"):
            self.cursor += 1
        elif self.view == "menu" and ev.key in ("up", "k"):
            self.cursor -= 1
        elif self.view == "fx1" and ev.key in ("left", "right", "h", "l"):
            d = 1 if ev.key in ("right", "l") else -1
            e = self.eff["fx1"] + d
            self.eff["fx1"] = 0x04 if e > 0x0f else 0x0f if e < 0x04 else e
        elif self.view == "play" and ev.key in ("left", "right", "h", "l"):
            d = 1 if ev.key in ("right", "l") else -1
            self.eff["play"] = (self.eff["play"] + d) % 4
        else:
            return
        self.rerender()


# ---- the app ---------------------------------------------------------------
class Workbench(App):
    TITLE = "remix workbench"
    CSS = """
    #strip { height: 2; padding: 0 1; }
    #detail { height: 1fr; padding: 0 2; }
    #history { height: 8; padding: 0 2; border-top: dashed $surface; }
    #status { height: 1; padding: 0 1; }
    #mods { width: 44; padding: 0 1; }
    #panel { width: 1fr; padding: 0 1; border-left: dashed $surface; }
    #log { height: 12; border-top: dashed $surface; }
    #emuhead { height: 2; padding: 0 2; }
    #lcd { height: 1fr; padding: 0 2; }
    #emunote { height: 2; padding: 0 2; }
    """
    MODES = {"rig": RigScreen, "remix": RemixScreen, "emu": EmuScreen}
    # App-level so it works from every view; modals handle their own escape
    # first, and no screen binds it, so escape is unambiguous.
    BINDINGS = [Binding("escape", "stop_play", "stop audio")]

    def __init__(self):
        super().__init__()
        self.state = State()
        self.rig = rig.Rig()
        self.track = 5                     # ChonVerb's home; T5 is the test track
        self.source = (wav_sources() or [None])[0]
        self.wet = False
        self.history = []                  # [(label, path)]
        self.marks = {}                    # "A"/"B" -> path
        self.status = ("1-8 pick a track · enter picks its effect · "
                       "r renders · x composes the image")
        self.rendering = False
        self.boot = None                   # cached emulator BootResult
        self.boot_mtime = None
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
        self.switch_mode("rig")

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
        self.status = ("stopped" if self.stop_play()
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
