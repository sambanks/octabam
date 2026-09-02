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

from remix import audition, registry, rig, stock  # noqa: E402
from remix.state import (BUILT_IMAGE, DONOR_WORDS, ROOT,  # noqa: E402
                         STOCK_ROOTS, State)

def step_label(mod, name, v):
    """A select's value as the manifest labels it, else the raw number."""
    lab = rig.knob_labels(mod, name)
    return lab[v] if lab and v < len(lab) else str(v)


def disp(mod) -> str:
    """What to CALL a module on screen: the name the panel shows, not the
    directory slug. `warpfold` is a path; `WarpFold` is what the operator
    reads on the unit."""
    if mod.menu is not None:
        return mod.menu.fullname.decode("latin1") or mod.name
    return mod.name


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
    "bench": """[bold]THE BENCH — one page, three panes[/]

[bold]AVAILABLE[/] everything that could be in an image: your modules,
then the stock effects the unit already ships. [bold]LOADED[/] is the
image you are composing, in CHOOSER ORDER — the order here is the order
of rows on the panel, so left/right there is a real edit. [bold]UNIT[/]
follows the cursor: the selected effect's knobs, and the firmware's own
draw of its page.

You start at [bold]stock[/] — the chooser an unmodified unit shows. Add
to what the box already does. A remix must name a fallback for ids it
does not implement (SEND is the safe one), so adding a module means
adding SEND too; the LOADED pane says so when it matters.

● in the LOADED pane means "in the image on disk". An effect that is
loaded but not built is not previewed: its id is not in the image, so
the firmware would draw a convincing picture of the WRONG effect.

[bold]keys[/]
  tab  pane            up/down  move
  enter  add / remove  left/right  knob value (UNIT) or row order (LOADED)
  p  preview mode      r  render + hear     space  play last
  b  build             c  check             w  word cost
  l  load remix        s  save remix        f  fallback
  k  back to stock     ?  this""",
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

[bold]The FX2 view is the whole loop.[/] left/right cycles every effect
the image offers AND every module that could be added; picking one the
image HAS assigns it to the track (the rig follows). Picking one it does
NOT have is not drawn — an id the image lacks resolves to the fallback,
so the firmware would draw a convincing picture of the wrong effect —
so [bold]a[/] stages it in the composer and [bold]b[/] builds and re-boots.
Cycling past several unbuilt effects costs nothing; only b builds.

[bold]keys[/]
  m  main menu      f  FX2 (cycles effects; the rig follows)
  o  FX1 (stock)    p  playback page
  a  stage an unbuilt effect     b  build the selection + re-boot
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
        Binding("enter", "add_remove", "add / remove"),
        Binding("p", "preview", "preview"),
        Binding("r", "render", "render+hear"),
        Binding("space", "play", "play last"),
        Binding("a", "mark('A')", "mark A", show=False),
        Binding("comma", "play_mark('A')", "play A", show=False),
        Binding("full_stop", "play_mark('B')", "play B", show=False),
        Binding("b", "build('bus')", "build"),
        Binding("c", "build('check')", "check", show=False),
        Binding("w", "measure", "word cost", show=False),
        Binding("f", "fallback", "fallback", show=False),
        Binding("l", "load", "load remix"),
        Binding("s", "save", "save remix"),
        Binding("k", "stock", "reset to stock", show=False),
        Binding("question_mark", "help", "what is this?"),
        Binding("q", "app.quit", "quit"),
    ]

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Static(id="pane_avail")
            yield Static(id="pane_load")
            yield Static(id="pane_unit")
        yield Static(id="status")
        yield RichLog(id="log", highlight=False, markup=False)
        yield Footer()

    def on_mount(self):
        self.pane = LOADED
        self.cur = [0, 0, 0]
        self.preview = "FX2"
        self.booting = False
        self.rows_mtime = None
        self.built = []                  # (fx2_id, module) from the image
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
        st = self.app.state
        self._pane_available(st)
        self._pane_loaded(st)
        self._pane_unit(st)
        self.query_one("#status", Static).update(f"[dim]{escape(st.msg)}[/]")

    def _title(self, text, pane):
        on = self.pane == pane
        return (f"[reverse bold] {escape(text)} [/]" if on
                else f"[bold]{escape(text)}[/]")

    def _pane_available(self, st):
        rows = self.avail_rows()
        out = [self._title("AVAILABLE", AVAILABLE), ""]
        group = None
        for i, m in enumerate(rows):
            g = "stock effects" if m.is_stock else rig.category(m)
            if g != group:
                group = g
                out.append(f"[dim]── {g} ──[/]")
            here = self.pane == AVAILABLE and i == self.cur[AVAILABLE]
            mark = "✓" if m.key in st.sel else " "
            menus = "+".join(rig.menus(m)) or "—"
            line = f" {mark} {disp(m):<13} [dim]{menus}[/]"
            out.append(f"[reverse]{line}[/]" if here else line)
        # The three stock REVERBS are absent from every list above, and their
        # absence is the kind that reads as a bug. Say where they went -- and
        # say it CONDITIONALLY, because "consumed" is a property of the
        # SELECTION, not a law. Their code is the region our modules are
        # written over, so a selection carrying no module of ours takes
        # nothing from them. (Precedent: CHORUS was a donor until v98 and got
        # its dispatch back the moment we stopped taking its code.)
        eats = [m for m in st.selected if m.dsp is not None]
        out.append("[dim]── the three reverbs ──[/]")
        for name in stock.CONSUMED:
            out.append(f"[dim]   {name:<13} —[/]")
        if eats:
            out.append("[dim]   their code is the region")
            out.append(f"   {escape(disp(eats[0]))} and "
                       f"{len(eats) - 1} other" +
                       ("s" if len(eats) != 2 else "") + " sit in[/]"
                       if len(eats) > 1 else
                       f"   {escape(disp(eats[0]))} sits in[/]")
        else:
            out.append("[dim]   nothing here takes their code —")
            out.append("   a stock-only image would keep")
            out.append("   them, but cannot be built yet[/]")
        out.append("")
        out.append("[dim]enter adds at ▸ in LOADED[/]")
        self.query_one("#pane_avail", Static).update("\n".join(out))

    def _pane_loaded(self, st):
        rows = self.loaded_rows()
        name = st.loaded_name or "unsaved"
        out = [self._title(f"LOADED · {name}", LOADED), ""]
        pos = 0
        at = min(self.cur[LOADED], len(rows))      # the insertion point
        for i, m in enumerate(rows):
            here = self.pane == LOADED and i == self.cur[LOADED]
            if m.menu is not None:
                pos += 1
                row = f"{pos:>2}"
            else:
                row = " ·"                      # no chooser row (a CF patch)
            menus = "+".join(rig.menus(m)) or "—"
            words = st.words.get(m.key)
            cost = f"[dim]{words:>5}w[/]" if words else "      "
            built = "●" if self.in_image(m) else " "
            fb = "◀fb" if st.eff_fallback == m.key else "   "
            # ▸ marks where an `enter` from the library would land. It has
            # to be visible from the OTHER pane too -- "adds at the LOADED
            # cursor" is useless advice when the cursor is only drawn on the
            # pane you are standing in.
            caret = "▸" if i == at else " "
            line = f"{caret}{row} {built} {disp(m):<13}[dim]{menus:<7}[/]{cost}{fb}"
            out.append(f"[reverse]{line}[/]" if here else line)
        if at >= len(rows):
            tail = "▸    [dim](end)[/]"
            out.append(f"[reverse]{tail}[/]"
                       if self.pane == LOADED else tail)
        if not rows:
            out.append("[dim] (empty — add from the left)[/]")
        probs = st.problems()
        out.append("")
        out.append("[dim]● = in the built image · ◀fb = fallback[/]")
        out.append("[dim]← → moves this row (= its panel slot)[/]"
                   if self.pane == LOADED else
                   "[dim]tab here to reorder or remove[/]")
        if probs:
            out.append(f"[bold]⚠ {escape(probs[0])}[/]")
        self.query_one("#pane_load", Static).update("\n".join(out))

    def _pane_unit(self, st):
        mod = self.selected_module()
        if mod is None:
            self.query_one("#pane_unit", Static).update(
                self._title("UNIT", UNIT) + "\n\n[dim]nothing selected[/]")
            return
        out = [self._title(disp(mod), UNIT), ""]
        bits = [rig.category(mod)]
        if mod.menu:
            bits.append(f"id 0x{mod.menu.fx2_id:02x}")
            bits.append("+".join(rig.menus(mod)))
        tr = rig.track_range(mod)
        if len(tr):
            bits.append(f"tracks {tr.start}-{tr.stop - 1}")
        out.append(f"[dim]{' · '.join(bits)}[/]")
        out.append(f"[dim]{escape(mod.doc)}[/]")
        out.append("")

        knobs = self.unit_rows(mod)
        vals = st.knobs_for(mod)
        for i, (name, slot) in enumerate(knobs):
            here = self.pane == UNIT and i == self.cur[UNIT]
            if name == "SOURCE":
                src = (self.app.source.name if self.app.source
                       else "(none — put wavs in out/dry/)")
                line = f" SOURCE {escape(src)}"
                out.append(f"[reverse]{line}[/]" if here else line)
                continue
            v = vals.get(name, 0)
            hi = rig.knob_max(mod, name)
            if hi < 8:
                shown = f"{step_label(mod, name, v):<7}"
                bar = "·" * 12
            else:
                shown = f"{v:>3}    "
                fill = round(12 * v / max(hi, 1))
                bar = "#" * fill + "." * (12 - fill)
            page = "1" if slot < 6 else "2"
            line = f" {name:<6} {shown}\\[{bar}] [dim]p{page}[/]"
            out.append(f"[reverse]{line}[/]" if here else line)
        if not knobs:
            out.append("[dim] (no drawn parameters)[/]")
        if self.pane == UNIT and knobs:
            name, _ = knobs[min(self.cur[UNIT], len(knobs) - 1)]
            hint = ("the wav auditioned through this effect — left/right "
                    "cycles what is in out/dry/" if name == "SOURCE"
                    else rig.knob_doc(mod, name) or "")
            out.append("")
            out.append(f"[dim]? {escape(hint)}[/]")
        out.append("")
        out.append("[dim]← → change · r render + hear · space replay[/]"
                   if self.pane == UNIT else
                   "[dim]tab here to change values and audition[/]")
        out.append("")
        out += self._preview(mod)
        self.query_one("#pane_unit", Static).update("\n".join(out))

    # ---- the emulated panel ---------------------------------------------
    def stale(self):
        """Does the image on disk still match the selection? The preview
        draws the IMAGE, and when the two disagree it shows one set of
        effects while the LOADED pane shows another -- which reads as a bug
        rather than as staleness unless it is said out loud."""
        want = [m.key for m in self.app.state.menu_modules if not m.is_stock]
        got = [m.key for _, m in self.image_rows() if m is not None
               and not m.is_stock]
        return want != got

    def _preview(self, mod):
        modes = " ".join(f"[reverse]{m}[/]" if m == self.preview else
                         f"[dim]{m}[/]" for m in PREVIEWS)
        head = [f"preview {modes}  [dim](p)[/]",
                "[dim]— drawn by the firmware, from the image on disk —[/]"]
        # STALE MEANS DO NOT DRAW. Labelling it was not enough: the FX2 page
        # includes the firmware's own chooser list, so a stale image puts a
        # different set of effects on screen beside the LOADED pane and reads
        # as "why are those loaded?". Same principle the unbuilt-module case
        # already used -- do not draw a convincing picture of the wrong thing.
        # ⚠️ Boot FIRST, then decide what to show. Returning early on stale
        # skipped ensure_boot() entirely, so a workbench that opened stale --
        # which is every fresh launch -- never started the emulator at all,
        # and the preview stayed dead for the whole session.
        r = self.app.boot
        if r is None:
            self.ensure_boot()
            return head + ["[dim]booting the emulator...[/]"]
        if self.stale():
            return head[:1] + [
                "[bold]the image on disk is not this selection[/]",
                "[dim]b builds it, then this shows YOUR image[/]"]
        if not r.reached_handoff:
            return head + ["[bold]did not reach the RTOS handoff[/] — a "
                           "patch may have broken early init"]
        import emu_bringup
        if self.preview == "MENU":
            draws = emu_bringup.render_menu(r, emu_bringup.MENU_ROOT_DESC, 0)
        elif self.preview == "FX1":
            draws = emu_bringup.render_fx1(r, track=4, effect_id=0x04)
        else:
            if mod.menu is None:
                return head + ["[dim]no chooser row: this module patches the "
                               "firmware rather than adding an effect[/]"]
            if not self.in_image(mod):
                return head + [
                    f"[bold]not in the built image[/] — b builds the "
                    f"selection",
                    "[dim]the page is not drawn: an id the image does not",
                    "implement resolves to the fallback, so the firmware",
                    "would draw the WRONG effect (CLAUDE.md, 12 Aug).[/]"]
            draws = emu_bringup.render_fx2(r, track=4,
                                           effect_id=mod.menu.fx2_id)
        grid = emu_bringup.layout_screen(draws)
        return head + ["." + "-" * 44 + "."] + \
            ["|" + escape(ln.ljust(44)) + "|" for ln in grid] + \
            ["'" + "-" * 44 + "'"]

    def ensure_boot(self):
        if not BUILT_IMAGE.exists() or self.booting:
            return
        mtime = BUILT_IMAGE.stat().st_mtime
        if self.app.boot is not None and self.app.boot_mtime == mtime:
            return
        self.booting = True
        self.boot_worker(mtime)

    @work(thread=True, exclusive=True, group="boot")
    def boot_worker(self, mtime):
        app = self.app
        try:
            import emu_bringup
            r = emu_bringup.boot(str(BUILT_IMAGE))
        except Exception as e:                       # noqa: BLE001
            r = None
            app.state.msg = f"emulator unavailable — {e} (make emu-setup)"
        self.booting = False
        if r is not None:
            app.boot, app.boot_mtime = r, mtime
        app.call_from_thread(self.rerender)

    # ---- input -----------------------------------------------------------
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
        # LOADED gets one extra position, past the last row: that is "append",
        # and without it there is no way to add at the end.
        n = max(len(rows) + (1 if self.pane == LOADED else 0), 1)
        if ev.key in ("down", "j"):
            self.cur[self.pane] = min(n - 1, self.cur[self.pane] + 1)
        elif ev.key in ("up", "k"):
            self.cur[self.pane] = max(0, self.cur[self.pane] - 1)
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
        self.rerender()

    def adjust(self, step):
        """Change the selected row. Knob values live per MODULE."""
        st = self.app.state
        mod = self.selected_module()
        knobs = self.unit_rows(mod)
        if not knobs:
            return
        name, _ = knobs[min(self.cur[UNIT], len(knobs) - 1)]
        if name == "SOURCE":
            files = wav_sources()
            if files:
                i = (files.index(self.app.source)
                     if self.app.source in files else 0)
                self.app.source = files[(i + step) % len(files)]
            return
        vals = st.knobs_for(mod)
        hi = rig.knob_max(mod, name)
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

    def action_add_remove(self):
        st = self.app.state
        if self.pane == AVAILABLE:
            rows = self.avail_rows()
            mod = rows[min(self.cur[AVAILABLE], len(rows) - 1)]
            if mod.key in st.sel:
                st.toggle(mod.key)
                st.msg = f"removed {disp(mod)}"
            else:
                # AT THE LOADED CURSOR, not appended. Chooser order is the
                # panel's row order, so where it lands is the question.
                at = min(self.cur[LOADED], len(st.order))
                st.insert_at(mod.key, at)
                rowno = len([k for k in st.order[:at + 1]
                              if st.mods[k].menu is not None])
                st.msg = (f"added {disp(mod)} at chooser row {rowno}"
                          if mod.menu is not None
                          else f"added {disp(mod)} (no chooser row)")
            st.loaded_name = ""
        elif self.pane == LOADED:
            rows = self.loaded_rows()
            if not rows or self.cur[LOADED] >= len(rows):
                return                       # the append position: no row
            mod = rows[self.cur[LOADED]]
            st.toggle(mod.key)
            st.loaded_name = ""
            st.msg = f"removed {mod.key}"
            self.cur[LOADED] = max(0, self.cur[LOADED] - 1)
        self.rerender()

    def action_stock(self):
        self.app.state.load_stock()
        self.cur = [0, 0, 0]
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
            self.rerender()
        self.app.push_screen(Chooser("unimplemented ids alias to:", opts), done)

    def action_help(self):
        self.app.push_screen(HelpScreen("bench"))

    # ---- audio -----------------------------------------------------------
    def action_render(self):
        app, st = self.app, self.app.state
        mod = self.selected_module()
        if mod is None or rig.category(mod) == rig.SYSTEM:
            st.msg = "that module is plumbing — nothing to hear"
        elif app.source is None:
            st.msg = "no source wav — put some in out/dry/"
        elif app.rendering:
            st.msg = "a render is already running"
        else:
            self.render_worker(mod, dict(st.knobs_for(mod)), app.source)
        self.rerender()

    @work(thread=True, exclusive=True, group="render")
    def render_worker(self, mod, values, source):
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
        app.history.append((f"{mod.name} · {desc}", path))
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
        app = self.app
        if app.history:
            label, path = app.history[-1]
            app.marks[which] = path
            app.state.msg = f"marked {which}: {label}"
            audition._journal({"event": "mark", "which": which,
                               "label": label, "out": path.name})
        self.rerender()

    def action_play_mark(self, which):
        app = self.app
        p = app.marks.get(which)
        if p:
            app.play(p)
            app.state.msg = f"playing {which}: {p.name}"
        else:
            app.state.msg = f"no {which} mark yet"
        self.rerender()

    # ---- build, measure, load, save --------------------------------------
    def action_measure(self):
        st = self.app.state
        st.msg = "assembling for word counts..."
        self.rerender()
        self.measure_worker()

    @work(thread=True, exclusive=True, group="measure")
    def measure_worker(self):
        st = self.app.state
        st.measure(None)
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
            self.app.boot = None          # the preview must re-boot
            self.rows_mtime = None        # and the ● markers re-read
        self.app.call_from_thread(self.rerender)

    def action_load(self):
        names = [n for n in registry.remix_names() if not n.startswith("_")]

        def done(name):
            if name == "stock":
                self.app.state.load_stock()
            elif name:
                self.app.state.load(name)
            self.cur = [0, 0, 0]
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
    #pane_avail { width: 32; padding: 0 1; }
    #pane_load  { width: 40; padding: 0 1; border-left: dashed $surface; }
    #pane_unit  { width: 1fr; padding: 0 1; border-left: dashed $surface; }
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
        self.marks = {}                    # "A"/"B" -> path
        self.status = ""                   # state.msg is the live line now
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
