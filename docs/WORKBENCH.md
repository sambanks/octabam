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
┌ AVAILABLE ───────┬ LOADED · stock ────────┬ FILTER ──────────────────────┐
│ ── server ──     │  1 ● FILTER    FX1+FX2 │ stock · id 0x04 · FX1+FX2    │
│    BongDelay FX2 │  2 ● EQUALIZER FX1+FX2 │ BASE   0  [............] p1  │
│    ChonVerb  FX2 │  3 ● DJ EQ     FX1+FX2 │ WDTH 127  [############] p1  │
│ ── insert ──     │  …                     │ …                            │
│    WarpFold  FX2 │ 11 ● DELAY     FX2     │ preview: FX2 MENU FX1        │
│ ── stock ──      │                        │ .--------------------------. │
│  ✓ FILTER FX1+FX2│ ● = in the built image │ | EFFECT 2 SETUP           | │
└──────────────────┴────────────────────────┴──────────────────────────────┘
```

### AVAILABLE — the library

Everything that *could* be in an image: your modules grouped **server** /
**insert** / **system**, then the stock effects the unit already ships. `✓`
marks what the current selection holds.

**`enter` adds at the `▸` in the LOADED pane**, not at the end — chooser
order *is* the panel's row order, so "which slot" is the question, and the
status line answers it ("added ChonVerb at chooser row 3"). The `▸` is drawn
from either pane, because an insertion point you can only see while standing
on it is no help when you are adding from the library. It can sit one past
the last row — that position is `(end)`, and it is how you append.
`left`/`right` in LOADED moves a row afterwards.

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
patch). `●` means the effect resolves in the image on disk. `◀fb` marks the
fallback. `w` fills in each module's word cost by running a real assembly.

**The three reverbs live here.** An unmodified unit shows **fourteen** FX2
effects, and PLATE, SPRING and DARK REV are three of them — so a stock
selection lists all fourteen. They leave when something takes their space:
their code *is* the 2,724-word donor region our modules are written over, so
adding one drops them in place with the reason (`– PLATE REV taken by
WarpFold`). That is the trade, shown where it happens rather than as a rule
you have to know. The precedent is CHORUS, which was a donor until v98 and
got its stock dispatch back the moment the build stopped taking its code.

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
stock, `f` picks the fallback explicitly, `b` builds, `c` runs `make check`.

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

⚠️ **The preview is a picture of the IMAGE ON DISK, not of the selection**,
and it says so. The FX2 page includes the firmware's own chooser list, so a
freshly launched workbench showing `stock` in LOADED while the preview lists
`ChonVerb78 / BongDelay78 / Send` is not a bug — it is last week's build. The
pane warns when the two disagree, and `b` rebuilds.

- **MAIN MENU** is the no-flash gate for ColdFire cave work — a patched-in
  top-level row draws here exactly as the unit would draw it.
- **FX1** shows that chooser as stock ships it, which is what FX1 rows would
  have to be added to.
- **FX2** draws the selected effect's page — *unless it is one of ours that
  has not been built*, in which case it is deliberately not drawn. An id the
  image does not implement resolves to the fallback and the firmware would
  draw a convincing picture of the wrong effect (`CLAUDE.md`, 12 Aug 2026).
  A **stock** effect always draws: a remix that leaves one out does not
  remove it — its code, descriptor and dispatch stay stock and an old
  project that selects it still runs it; it only loses its chooser row.

The boot (~4 s) is cached and repeats only when the image changes.

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
