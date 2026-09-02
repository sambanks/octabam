# The workbench — `make remix`

The interactive front end of the project, organized the way an Octatrack
user thinks: **tracks and effects**, not modules and payloads. Shipped
31 Aug 2026 (PRs #40–#44), replacing the curses composer; PLAN.md §5 is the
decision record, this page is the manual.

What it is for, in priority order (Sam's, stated when the redesign was
commissioned):

1. **Trial sounds** — put an effect on a track, dial its real knobs, render
   a wav through the actual DSP code and hear it. A/B alternatives.
2. **Build and save remixes** — compose the firmware image with collision
   and fit feedback.
3. **No-flash confidence** — boot the built image in the local ColdFire
   emulator and see the firmware draw its own screens.

Audio comes from the local DSP emulator (~6× real time, `docs/HARNESS.md`);
the ColdFire emulator (`docs/EMU.md`) provides the screens. Nothing in the
workbench touches hardware.

## Setup

```bash
make emu-setup      # uv provisions .venv with unicorn + textual
make remix          # the workbench (make bus first if out/mainos_bus.bin
                    # doesn't exist yet — the EMU view boots it)
```

The frontend is `tools/remix/app.py` (Textual). `make remix` prefers
`.venv/bin/python3`; on bare `python3` it exits with the setup hint. The
build and every check remain dependency-free — only the interactive
workbench lives in the venv.

Playback is `afplay`, so hearing renders is macOS-only; everything else
works anywhere the DSP toolchain does.

## One page, three panes

`make remix` opens a single screen. `tab` moves between panes, `up`/`down`
moves within one, `?` opens this page's short form, `esc` stops audio, `q`
quits. **There is no per-track view** — the eight-track rig was retired 2 Sep
2026 because it was a second place to say what a remix already says, and
knob values belong to the effect rather than to a track.

```
┌ AVAILABLE ───────┬ LOADED · chongbong ────┬ ChonVerb ────────────────────┐
│ ── server ──     │ ▸1 ChonVerb  FX2  2411w│ server · id 0x07 · tracks 5-8│
│    BongDelay FX2 │  2 BongDelay FX2  2469w│ TIME  64  [######......] p1  │
│    ChonVerb  FX2 │  3 Send      FX2   250w│ MOD   30  [###.........] p1  │
│ ── insert ──     │  · tempo-sync −     ◀fb│ …                            │
│    WarpFold  FX2 │ —  PLATE, SPRING, DARK │ preview  FX1 FX2 MENU        │
│ ── stock ──      │                        │ .--------------------------. │
│  ✓ FILTER FX1+FX2│ A 74 free · B 5 free   │ | EFFECT 2 SETUP           | │
└──────────────────┴────────────────────────┴──────────────────────────────┘
```

### AVAILABLE — the library

Everything that *could* be in an image: your modules grouped **server** /
**insert** / **system**, then the stock effects the unit already ships. `✓`
marks what the current selection holds.

**`enter` SWAPS the `▸` row in LOADED for the highlighted module.** Composing
an image is *trading*, not accumulating: the donor region is 2,724 words and
the chooser is a list somebody has to scroll, so putting something in
normally means taking something out — and the new effect takes the old one's
**slot**, because the row number *is* the panel position. The status line
says what happened ("swapped FILTER → WarpFold at chooser row 1").

The `▸` is drawn from either pane, because an insertion point you can only
see while standing on it is no help when you are choosing from the library.
It can sit one past the last row: that position is `(end)`, and there `enter`
appends instead of swapping. `left`/`right` in LOADED moves a row afterwards,
and `enter` on an already-selected module removes it.

**Rows are not the currency — words are.** The pane's one status line shows
the budget the way the build reports it — **per payload**, `A 74 free · B 5
free` — and this is the thing to watch, because:

- a **chooser row costs nothing** (seven fit in place, up to 32 in the long
  cave), and
- a **stock effect costs nothing at all** — its code is already in the image
  whether or not it has a row. **Swapping a stock effect out frees zero
  words.** The swap gesture is about the panel SLOT, not about space.

⚠️ **There are TWO 2,724-word regions, one per payload**, and `SPEC=1` puts
each server on its own. Summing every module's words against a single region
is wrong, and the pane used to do it: it read `chongbong`, the *shipping*
remix, as `5130 words exceeds the 2724-word donor region by 2406` when the
truth was A 2,650/74 free and B 2,719/5 free. Fixed 2 Sep 2026 by reporting
the build's own per-payload figures and deleting the reimplemented check
(`state.problems`). An overrun now arrives as the build's own refusal, which
names the payload: `payload B: RUNGS overruns the region (3599 > 2724
words)`.

So the words are spent only by modules of ours, and a swap is only
1-for-1 in *rows*: Nimbus (500) could equally be Streamz (255) + WarpFold
(322), or Hello World (27) + Ripple (347). Measured costs, payload A:
Hello World 27, Streamz 255, WarpFold 322, Ripple 347, BodeShift 391,
Nimbus 500, Rungs 880, Send 215, ChonVerb 2,411 (+24 LFO table), BongDelay
2,469 (payload B).

**One trade is often not enough**, and the status line names the next one
rather than leaving it to the build to refuse:

| after the swap | what happens |
|---|---|
| no safe fallback | **SEND is added** — the status line says `added Send as the fallback`. A row is free, so sacrificing an effect for it would be this UI's invention, not the image's constraint |
| a buffer clash | the ⚠ line reads `also remove FLANGER, CHORUS, SPATIALIZER, COMB` |
| past a payload's region | the build refuses and names it: `payload B: RUNGS overruns the region (3599 > 2724 words)` |

**The consequence goes on the ⚠ line, not in the status bar.** Appending it
to "swapped X → Y" produced a run-on the status bar then truncated — and the
half it cut was the only actionable one. The ⚠ line sits under the rows it
is about and is re-derived every render rather than being a snapshot of the
moment one swap happened.

**The buffer clash is the expensive one, and it is why adding ChonVerb to a
stock chooser costs four effects.** FLANGER, CHORUS, SPATIALIZER and COMB
each take a per-track instance buffer from the host's bump allocator, at
exactly the addresses ChonVerb's tank hardcodes — so the ledger refuses each
pair, and the chooser is one list for all eight tracks so the image cannot
keep them apart. The ledger states it one PAIR at a time, which is four
near-identical walls of text; the pane aggregates them into the sentence
above. What you are left with — ChonVerb, the seven stock effects that can
coexist, and Send — *is* `remixes/restored.py`.

The three stock **reverbs** are not here — they are in LOADED, because they
are part of a stock chooser. See below.

The `FX1+FX2` column is which **chooser** the effect has a row on, derived
from the pristine image rather than written down (`stock.fx1_ids()`). Stock
gives the two slots different lists: ten effects on FX1, those ten plus
DELAY and the three reverbs on FX2 — which is why taking the reverbs as
donors cost FX1 nothing. **Our own modules are FX2-only, and that is a build
limit, not a hardware one**: the DSP dispatch tables are indexed by the raw
id and shared between the menus, so a module's code already runs from FX1
the moment FX1 selects its id. What is missing is the panel side — FX1's
15-entry chooser cannot grow in place and must be relocated to a cave
(`tools/build_fx1.py` proved it can be), and no manifest field asks for a
row. The real ceiling is cycles ×4 (`PLAN.md` §2).

### LOADED — the image being composed

The selection, **in chooser order** — the order here *is* the order of rows
on the panel, so `left`/`right` is a real edit, not a view preference. The
number column is the panel row; `·` means no chooser row at all (a ColdFire
patch). `◀fb` marks the fallback. Each module's word cost comes from the real
assembly the background rebuild runs, so it is always filled in.

**The three reverbs live here.** An unmodified unit shows **fourteen** FX2
effects, and PLATE, SPRING and DARK REV are three of them — so a stock
selection lists all fourteen. They leave when something takes their space:
their code *is* the 2,724-word donor region our modules are written over, so
adding one drops them to a single dim line, `— PLATE, SPRING, DARK REV
(donors)`. That is the trade, shown where it happens rather than as a rule
you have to know. The precedent is CHORUS, which was a donor until v98 and
got its stock dispatch back the moment the build stopped taking its code.

⚠️ It used to be three lines, one per reverb, each reading `– PLATE REV
taken by BongDelay +1`. That said one thing three times; it named an
arbitrary module as the taker (`eats[0]` is just the first selection with DSP
code — **nothing computes a per-reverb attribution**, and the `+1` was SEND);
and at 40 columns the ` +1` wrapped onto its own line, so it read as a fourth
mystery row. Corrected 2 Sep 2026.

⚠️ A stock selection that keeps all three **cannot be built yet** — a remix
must name a fallback and no stock effect is a safe one. `PLAN.md` §7 has the
two changes that would fix it, and the argument for closing it instead.

**You start at `stock`** — the chooser an unmodified unit shows, no modules
of ours. You add to what the box already does rather than to somebody else's
remix. That selection deliberately cannot build as it stands: a remix must
name a fallback for the ids it does not implement, and no stock effect is a
safe one (it would *process* the unknown id), so the moment you add a module
you add SEND too. The pane says so.

`l` loads a remix (or `stock`), `s` saves the selection as one, `k` resets to
stock, `f` picks the fallback explicitly, `c` runs `make check`. **There is no
build key** — see below.

**The pane closes with ONE line**, which is either the per-payload budget, a
`⚠` naming what to remove, or `building…`. It used to close with five — a
budget, a `●` legend, a "dim = stock" legend, a keys hint and a `⚠` — which
was roughly half the pane's height spent explaining constraints rather than
showing the image. The explanations are in `?`.

### UNIT — the selected effect

Follows the cursor, so pointing at something in the library previews it
before you add it. Shows its kind, id, menus and track range, its one-line
doc, and its drawn parameters with values — `left`/`right` adjusts,
`shift` for ×10. **Values live per module**, seeded from the manifest
defaults (a stale default polluted every shimmer measurement until Round 12).

**`SOURCE` is the first row**: `left`/`right` cycles the wavs in `out/dry/`,
so choosing what you audition on is one keypress from the knobs. `r` renders
the effect over it and plays it; `space` replays.

Below that, `p` cycles the **preview** in the unit's own order — `FX1`,
`FX2`, then `MENU` — showing the firmware's own draw of that page.

⚠️ **The FX and MENU page entry points TOGGLE**: calling one opens the page,
calling it again closes it, so consecutive renders used to alternate between
a full screen and an empty one (26 draws, 0, 26, 0). A workbench that
re-renders on every keystroke therefore showed a blank LCD about half the
time, and the MAIN MENU never drew at all — FX2 is the default view, so the
menu render was always the second call and an FX page had already taken the
window. `emu_bringup` now re-issues the call when nothing was captured
(`_call_page`, `_open_menu_window`). Found 2 Sep 2026 by rendering each view
four times in a row and counting the draws.

**The image follows the selection.** Every selection change rebuilds and
re-boots on a worker thread after a 0.35 s debounce, so the preview always
draws what LOADED says. There is no build key and no staleness to reason
about.

⚠️ This replaced a `stale()` gate that refused to draw when the image on disk
was not the selection, printing a bold `the image on disk is not this
selection / b builds it`. The gate's *reasoning* was right — the FX2 page
includes the firmware's own chooser list, so a stale image puts a different
set of effects on screen beside LOADED and reads as "why are those loaded?"
— but **every fresh launch is stale**, so the headline feature opened showing
a disclaimer, and what it was guarding is a **0.26 s build** plus a 4.6 s
ColdFire boot, both already on a worker thread (measured 2 Sep 2026). Changed
the same day: rebuild instead of explaining.

The build is `state.measure()`, which is the same `REMIX=x XBUS=1 SPEC=1
build_bus.py` that `make bus` runs and which parses the per-module word
counts out of the build report on the way past — so one call does what the
old `b` (build) and `w` (word cost) keys did separately. A selection that
cannot build is not drawn: the `⚠` line says why, and `c` still runs the full
`make check` with its log.

- **MAIN MENU** is the no-flash gate for ColdFire cave work — a patched-in
  top-level row draws here exactly as the unit would draw it.
- **FX1** shows that chooser as stock ships it, which is what FX1 rows would
  have to be added to.
- **FX2** draws the selected effect's page — *unless it is one of ours that
  is not in the image*, in which case it is deliberately not drawn. An id the
  image does not implement resolves to the fallback and the firmware would
  draw a convincing picture of the wrong effect (`CLAUDE.md`, 12 Aug 2026).
  Rare now that the image follows the selection, but kept: it is a real
  safety property, not a staleness message. A **stock** effect always draws:
  a remix that leaves one out does not remove it — its code, descriptor and
  dispatch stay stock and an old project that selects it still runs it; it
  only loses its chooser row.

The rebuild is 0.26 s and the boot 4.6 s (measured 2 Sep 2026), both on a
worker thread; a run of swaps costs one rebuild, not one per keystroke.

⚠️ **An untouched `stock` selection is not previewed, and that is not the
staleness gate coming back.** It genuinely cannot build: a remix must name a
fallback for the ids it does not implement, and no stock effect is a safe one
(it would *process* the unknown id) — `state.load_stock` is explicit that it
"should not pretend to". So the launch state says `stock — swap a module in
to build it` rather than `⚠`, because it is where the bench opens, not a
mistake. One swap resolves it: SEND comes with the first module of ours.

Honest limits (`docs/EMU.md`): no audio and no key matrix in the emulator —
navigation is poking state and re-calling draw functions. Knob **values**
draw as dial graphics the string-capture hook cannot read, so the numbers in
this pane are the truth for values, not the picture. In a SPEC image the
delay's DSP in payload A is the SEND alias, so its page can draw empty.
Item-level menu descent needs the real key handler (`FUN_40064e64`) and is
not built. The PLAYBACK page render was dropped with the rig — it proved the
detour could draw a non-FX page and had no role in composing an image.

## The audition backend

`tools/remix/audition.py` is the one render entry point; the UI never knows
which harness ran. All knobs are addressed by **manifest names** —
`Module.knob_map()` (schema.py) is the single source of the name→slot map.

| effect | path |
|---|---|
| chonverb | `tools/render_reverb.py` — manifest slot → its positional param name (the two tables are proven slot-aligned by the selftest); MODE via `--mode`, wet via `--wet` |
| bongdelay | the DEV hatch (`DEV=1 XBUS=1` build → `out/dsp/mem_dev_A.mem`, rebuilt when stale) then `send_probe --layout DS --in … --wav …` |
| inserts | a per-insert scratch image (`_audition` remix = the insert + SEND), dumped to `out/dsp/_audition_<name>_A.mem`; the build saves and restores `out/mainos_bus.bin` so the EMU view never silently boots a scratch |

Knob overrides ride `send_probe --set=NAME=VAL` (one token — the delay's
`-VRB` begins with a dash), resolved through the rendered module's own
`knob_map()`; an unknown name dies rather than driving the wrong slot.

**The SEND-alias guard is general.** An id absent from an image dispatches
to the fallback, which renders a *plausible dry passthrough* — peak equals
the input amplitude, THD at the noise floor, no error anywhere (this cost a
session on 12 Aug 2026 and was reproduced live on 31 Aug with `--pick B`
against a chongbong image). `send_probe` now refuses to render **any**
module whose dispatch entry equals SEND's.

Renders land in `out/_audition/`.

## The journal

Every render — and every A/B mark — appends one JSON line to
`out/_audition/log.jsonl`:

```json
{"t": "2026-08-31T12:45:41", "event": "render", "label": "T5",
 "effect": "chonverb", "source": "bass.wav", "wet": false,
 "knobs": {"TIME": 80, "...": 0}, "out": "T5_bass_chonverb_BIG.wav"}
```

That makes a listening session addressable: "this sounds boxy" plus the
journal tail is a full repro — track, effect, source, every knob. It is
also how demo takes get captioned after the fact.

## Knob values

Values live **per module**, in the session, seeded from that module's
manifest defaults the first time you look at it. They are a bench fixture,
not a firmware statement: a remix file says what the image *contains*, never
what the operator had a knob set to. Nothing about them is written into the
image, and a render is the only thing that consumes them.

⚠️ `out/_rig.json` and the per-track rig it persisted are **gone** (2 Sep
2026). Eight tracks with an effect on each was a second place to say what a
remix already says, and it forced a knob set per track when what an operator
actually tunes is an effect. An old `_rig.json` on disk is inert and can be
deleted.

## Theming

The app renders in the **terminal's own 16-color ANSI palette** (Textual's
`ansi-dark` theme), so it wears whatever colorscheme the terminal wears,
background included. `WORKBENCH_THEME=<name> make remix` picks any
built-in Textual theme (`gruvbox`, `nord`, `tokyo-night`, `textual-dark`
for Textual's stock look, …); unknown names fall back to `ansi-dark`.

## Architecture and guarantees

The UI is a shell; the model layers are headless and importable:

| layer | file | job |
|---|---|---|
| composer | `tools/remix/state.py` | selection, `problems()`, `measure()`, scratch builds (extracted unchanged from the old TUI) |
| tracks | `tools/remix/rig.py` | category + track-range derivation, per-track state, knob docs/labels/maxima |
| rendering | `tools/remix/audition.py` | the per-effect dispatch above, the journal, a `__main__` for headless renders |
| shell | `tools/remix/app.py` | Textual only — screens, keys, workers |

Categories and track ranges are **derived from manifests**, never declared
in the UI: `harness.is_server` + `dsp.payloads` (each server declares its
single payload; a server without one is refused, not guessed at) →
SERVER/T5-8 or T1-4; `DSP_EFFECT` with a menu → INSERT/any track;
`Kind.STOCK` → STOCK/any track (no knobs, no render); everything else →
SYSTEM/no track.

Three `Param` fields exist purely for the workbench and are **proven
display-only** — `scripts/refhash.sh check` ran bit-identical (26/26)
after each manifest change that introduced them:

- `payloads` (on `DspSection`) — the server's core, hence its tracks.
- `doc` — the one-line "what is this knob?" shown under the cursor.
- `labels` — per-value labels for a stepped select (length pinned to
  `count` by the schema).

`tools/remix/selftest.py` (in `make verify`) holds the lines: the
category/track-range derivation matches the measured facts for every
module; a payload-less server is refused; chonverb's manifest slots stay
aligned with `render_reverb`'s positional table; and **every named, drawn
param of every menu-bearing module must carry a `doc`** — an undocumented
knob fails the build's checks.

UI regressions are caught headlessly with Textual's Pilot (`run_test`):
scripts drive keys and assert on rendered text. The markup-artifacting fix
(PR #42 — literal `[x]` parsed as a Rich style tag and bled styling across
rows) is pinned that way; anything data-driven that reaches markup goes
through `rich.markup.escape`.

## Known gaps

- DELAY (stock) has no local render (ColdFire-side); LO-FI renders at
  +6 dB at zero settings (unexplained).
- A/B marks attach only to the most recent render (no history cursor).
- No browse-anywhere source picker (one fixed directory, `out/dry/`).
- Wet-only rendering is ChonVerb-only.
- The emulator limits listed above (values, key injection, delay page
  under SPEC).
