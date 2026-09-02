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

## The three views

`x` / `v` / `e` move between them; `?` on any view opens an overlay with
this page's short form; `esc` stops audio from anywhere; `q` quits (from
EMU, `q` returns to the rig).

### RIG — the home view

Eight tracks across the top, an effect assigned to each, the selected
track's controls below. This is the trial-a-sound loop.

![The RIG view: Nimbus on T6, its page-1 knobs and FRZE select, the
per-knob help line, and the render history](img/workbench-rig.png)

| key | action |
|---|---|
| `1`–`8` | select track |
| `enter` | pick the track's effect (only effects that can run there) |
| `backspace` | clear the track's effect |
| `up/down` (`j/k`) | move between rows: SOURCE, RENDER, then the knobs |
| `left/right` (`h/l`) | adjust the row; `shift` steps by 10 |
| `r` | render the track's effect over the source, then play it |
| `space` | replay the last render |
| `a` / `b` | mark the last render as A / B |
| `,` / `.` | replay mark A / mark B |
| `esc` | stop playback |

Row notes:

- **SOURCE** cycles every `.wav` in `out/dry/` — the curated DRY set
  (31 Aug 2026; the old `out/test_audio/` + `out/demo_sources/` browse
  mixed ~50 processed renders in with the dozen dry sources). Drop files
  in `out/dry/` and restart. If `out/dry/` is missing or empty the old
  two-directory browse comes back as the fallback. (No browse-anywhere
  picker yet.)
- **RENDER wet/full** applies to ChonVerb only (`render_reverb --wet`, an
  exact dry subtraction). Other effects always render their normal output.
- **Knob rows** carry the manifest's names in the unit's own page layout:
  slots 0–5 = page 1, encoders A–F; slots 6–11 = page 2, knob/select
  alternation. Selects show their manifest labels (the delay's MODE reads
  CLEAN/PITCH/(tape)/GRAIN/REVRS, not 0–4). The dim `?` line under the
  rows explains whichever row the cursor is on — the text comes from
  `Param.doc` in the effect's manifest.
- ChonVerb's MODE renders as its own image, cached per mode
  (`render_reverb`'s engine cache) — the first render after a MODE flip
  pays a build, later ones don't.

The RENDERS panel lists recent renders with the knobs that differed from
defaults; `[A]`/`[B]` show where the marks sit. Marks always attach to the
**most recent** render — walk-the-history marking is a known gap.

**Why some effects are missing on some tracks:** the two bus servers each
live on one DSP core, and the cores serve fixed track halves — ChonVerb
(payload A) on **tracks 5–8**, BongDelay (payload B) on **tracks 1–4** —
the measured 10 Aug 2026 track↔core inversion. Inserts run anywhere.
SYSTEM modules (SEND, tempo-sync) are plumbing and never appear in the
picker.

### REMIX — the composer

The old workbench's job, reframed. Left: the modules, grouped **BUS
EFFECTS** (with track range) / **INSERTS** (any track) / **STOCK FX2** /
**SYSTEM**, with the cursored module's one-line doc below. Right: what the
selection *is* — the FX2 chooser exactly as the unit will show it, in
**selection order** (`[` / `]` move the cursored module; a saved remix
keeps that order), the program-fit bar against the donor region, and the
ledger's collision verdict (the same `ledger.check` the build runs, not a
reimplementation).

**STOCK FX2** (since 2 Sep 2026) is the eleven stock effects the image
would otherwise hide: every image replaces the whole chooser, but only
PLATE/SPRING/DARK REV are actually consumed (their code is the donor
region), and the panel now says so. Toggling a stock row costs nothing —
no code, no words, no clone; the row is the only edit. The four that
allocate a per-track buffer (SPAT, FLNG, CHOR, COMB) are refused beside
ChonVerb, Nimbus or BongDelay, with the reason. Past seven rows the panel
scrolls, and the composer says that too. `docs/MODULES.md` has the rules.

In the RIG a stock effect shows its **real knobs** — names, defaults and
value counts read from the stock descriptor in the pristine image (a
select shows its count, not stock's word labels) — and **renders** like
an insert, from a one-time dump of the stock image's payload A
(`out/dsp/_stock_A.mem`), so nothing about the currently built remix
matters. Nine of the eleven render credibly (2 Sep 2026: FILTER, EQ,
DJ EQ, PHASER, CHORUS, SPATIALIZER, COMB, COMPRESSOR, LO-FI — LO-FI
needed an emulator patch, `tools/dsp56300.patch`, for the `mpyri`
instruction). Two do not: **DELAY** runs on the ColdFire, so there is no
DSP code to render and the audition says so; **FLANGER** renders but its
output is not credible — MIX=0 is not dry and DEP=0/FB=0 still measures
as broadband hash — cause open (`docs/MODULES.md`).

![The REMIX view: modules grouped by category with track ranges, the FX2
menu as the unit will draw it, and the ledger's verdict —
chongbong loaded](img/workbench-remix.png)

| key | action |
|---|---|
| `space` | toggle the module under the cursor |
| `[` / `]` | move it earlier / later in the chooser |
| `f` | make it the fallback (absent ids alias to the fallback — normally SEND, so a stale project degrades to a send, not noise; `*` explicit, `~` auto) |
| `w` | assemble the selection and keep the real word counts |
| `b` / `c` | `make bus` / `make check` on the **live** selection (via the scratch-remix mechanism — no save needed) |
| `l` / `s` | load / save a remix file |

A successful `b`/`c` invalidates the EMU view's cached boot, so `e` shows
the image you just built.

The panel's "no LEDGER collisions" deliberately names what is *not*
checked (the shared 64K window) and which selected module owns the
per-core FX2 buffer region — see CLAUDE.md for why that caveat is written
out each time.

### EMU — the emulated unit

The built image (`out/mainos_bus.bin`) booted in the Tier-0 ColdFire
emulator, drawing **its own screens**: the MAIN MENU (patched-in entries
render as the firmware would draw them), FX2/FX1 SETUP, and the PLAYBACK
page. Booting is itself the no-flash gate — a cave that breaks early init
faults here, not on the unit.

| key | action |
|---|---|
| `m` | main menu (`up/down` moves the cursor) |
| `f` | FX2 SETUP — follows the rig's selected track and its assigned effect |
| `o` | FX1 SETUP (stock effects; `left/right` cycles the id) |
| `p` | PLAYBACK page (`left/right` cycles FLEX/STATIC/THRU/NEIGHBOR) |
| `1`–`8` | change track |

The boot (~4 s) is cached at app level and repeats only when the image's
mtime changes.

Honest limits (all recorded in `docs/EMU.md`): no audio, no key matrix —
navigation is done by poking state and re-calling draw functions. Knob
**values** draw as dial graphics the string-capture hook cannot read, so
the rig's numbers are always the truth for values. In a SPEC image the
delay's DSP in payload A is the SEND alias, so its FX2 page can draw
empty. Item-level menu descent needs the real key handler
(`FUN_40064e64`) and is not built.

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

## The rig file

`out/_rig.json` persists the per-track assignments and knob values across
restarts. It is a **bench fixture, not a firmware statement** — remix
files say what the image contains; the rig says what the operator was
listening to. Loading validates against the current manifests: a renamed
knob does not resurrect a stale value under its old meaning, and an
assignment a module can no longer honour is dropped.

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

- DELAY (stock) has no local render (ColdFire-side); FLANGER's local
  render is not credible (open). Stock select labels are counts, not
  stock's word labels.
- A/B marks attach only to the most recent render (no history cursor).
- No browse-anywhere source picker (one fixed directory, `out/dry/`).
- Wet-only rendering is ChonVerb-only.
- The emulator limits listed above (values, key injection, delay page
  under SPEC).
