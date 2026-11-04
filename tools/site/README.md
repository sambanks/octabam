# The manual site

The musician-facing manual, built with MkDocs with the shadcn theme and deployed to
GitHub Pages by `.github/workflows/pages.yml` on pushes to main. The same
build, without the deploy, runs as the `site` job on every PR
(`.github/workflows/ci.yml`).

`release.py` says what the site publishes: one release (`v0.3`, the git tag
the web builder's patches are built from) of one remix (`octabam`). A remix
that is not listed (`octabam-bus`, `cxosc-core`) has no manual, no overview
row and no builder entry; it stays in the repository.

`gen_pages.py` renders the generated pages from this commit's manifests
(`tools/remix/index.py`, the registry). The generated files sit under
`reference/` in the site directory, are gitignored, and never appear in
the tree, so the site and the manifests cannot drift: a merge to main
rebuilds them.

Generated, gitignored:

- the manual of each published remix, `reference/manual/<remix>/` (below)
- `modules.md`, the Feature Directory (in the nav under More): what is in the published
  remix by the manual's sections, linked to the manual pages, then every other contributed
  module by category, linked to its own page
- `modules/<name>.md`, one page per contributed module: the usage fragment, whether the
  module is in the published remix (and its manual page), and its facts; no test status.
  The pages are not in the nav (each carries a `not_in_nav` line); the directory reaches them
- `_remix-<name>.md`: the module table of the remix's overview page
  (`remix-<name>.md`, hand-written), each row linked to its manual page;
  stock effects read `stock` in the author column

## The remix manual

`gen_manual.py` (run by `gen_pages.py`) writes the manual of each published
remix under `reference/manual/<remix>/`:

- `index.md`: the introduction (hand-written, below), conventions, the
  contents, installing
- one page per module, in the section `PLACE` gives it: `effects/`,
  `machines/`, `sequencer/`, `parts/`, `midi-usb/`, `utilities/`, `fixes/`,
  `inside/` ("Behind the scenes"). A module that `PLACE` does not name goes by
  its category, so a new module is not left out
- `brain/`: BRAIN, one page per part of it (index, templates, remixes,
  settings, performance, log, about, files), from the hand-written fragments
  `docs/site/manual/brain-<part>.md`
- `credits.md`: the authors, one entry each (two spellings of one GitHub
  account are one entry)

Stock effects are not documented. No page carries a test status.

Each module page is, from the manifest, never typed: the byline, which chooser
an effect is in (FX1, FX2, read from the remix's `fx1` and the module's `SLOTS`
setting), the knob layout (name, values, default, one-line meaning) with what a
MODE renames, the settings a musician can change with the value this remix gives
them (build-time settings are not shown), and what the module needs. From the
hand-written usage fragment (`docs/site/usage/<name>.md`): the prose, with its
site links rewritten for the page's depth. A fragment's own `## Parameters` table
is dropped from the manual, because the knob tables come from the manifest. A
sibling link in a fragment (`kits.md`) points at that module's page, or loses its
link when the module is not in this manual. A module with no fragment shows its
manifest line, so the manual has no hole. `HIDE_SHOTS` in `gen_manual.py` lists a
screenshot that shows another remix's screen.

The introduction is hand-written, one file per remix in the site's manual
directory (`octabam.md`). Write it as sections `### About ...`, `### What changes
...` for the page it lands in, so its links are relative to
`reference/manual/<remix>/` (`../../../safety.md` reaches the site root); the
generator adds the conventions, the contents and installing.

To improve a knob's row in the manual, edit the `Param` `doc` in the manifest.
To improve a module's prose, edit its usage fragment. The remix's own paragraph
is `Remix.doc`.

The pages are listed by hand under the manual in `mkdocs.yml`:
`python3 tools/site/gen_manual.py --nav` prints the block. `verify_docs.py`
refuses a nav that differs from the pages the manifests produce, naming the
page.

## The web builder

`docs/site/builder/` holds the builder's page script, the patch of each published
remix (`patches/<remix>.obp`) and `manifest.json`. They are built by
`make webpatch BUILD=<nn>` (`tools/web/publish.py`) on a clean tree at the release
tag, so a published patch names a commit anyone can check out; the manifest names
the release. `tools/web/stale.py --check` verifies the committed patches in CI;
a manifest that names a release is locked to it, and later changes are listed,
not warned about.

## Rules the doclinks gate forces on these files

`tools/verify/doclinks.py` scans every tracked text file, these pages
included. Three consequences:

- The `REPOPATH` rule matches any `docs/…md`, `tools/…md`,
  `modules/…md` or `remixes/…md` string anywhere in a tracked file and
  requires the path to exist. The remix pages are therefore named flat at
  the site root (`remix-octabam.md`) so
  the nav needs no `remixes/…` entry, and links into the repository are
  written as full `https://github.com/sambanks/octabam/…` URLs.
  `reference/…` paths are safe (not in the alternation). `gen_pages.py`
  builds all paths with pathlib joins and all GitHub links as f-strings
  (strings containing `{}` are exempt), so it stays quiet too.
- Markdown links in a tracked page must resolve from the page's own
  directory, and `#anchor` targets must match a heading under GitHub's
  slug rule. The hand-written remix pages link into `reference/`, whose
  files are generated and untracked, so `tools/verify/verify_docs.py`
  renders them (quietly) before it resolves links — as does CI's docs
  job.
- No section sign in any tracked page ("section N" instead).

`mkdocs build --strict` is the complementary gate: it fails on a broken
site link or a broken snippet include (it does not check anchors;
doclinks does).

## Build

```bash
python3 -m venv .venv-site
.venv-site/bin/pip install -r docs/site/requirements.txt
python3 tools/site/gen_pages.py
.venv-site/bin/mkdocs serve --config-file docs/site/mkdocs.yml   # http://127.0.0.1:8000
.venv-site/bin/mkdocs build --strict --config-file docs/site/mkdocs.yml
```

`gen_pages.py` needs the submodules initialized (`git submodule update
--init`): the registry execs the authors' manifests.

## LCD illustrations

The manual uses exact firmware captures rendered in black on white.
`tools/emu/lcd_view.py` now defaults to the white palette; `--palette yellow`
selects the former LCD colours for PNG output. `live_shots.py` uses that
renderer, so new scripted captures also default to white.

Take fresh captures from the emulator's actual panel UART with:

```bash
python3 tools/site/capture_manual.py core features inserts bus extras machines probes
```

The command uses `OT_PROJECT` or `~/.octabam_project`, or accepts
`--project <path>`. It copies the project and stages private cards beneath
`out/manual-captures/`; the user's project is never edited. Each capture
is recorded in `screenshots.json`, including the firmware hash and remix.
The generated module galleries and screenshot coverage index read this
manifest. `screen-notes.json` accounts for modules without a separate LCD
interface and records blocked captures explicitly. Review the captured
screens before publishing: a successful key sequence alone does not prove
it reached the intended page. The `probes` group captures CF meter from
the standalone `cfmeter` remix; the `waveload` image does not assemble
(`meter.s:91`, short branch displacement 130).

Keep image assets included in the site; only usage and remix fragments
belong in `exclude_docs`.

Usage fragments are included beneath a generated page title. Start them
with an introduction, not another H1. Link screenshots relative to the
resulting generated module page. Main manual chapters use their own local
image paths. `manual.css` handles reading width, spacing and image framing
while retaining the theme's typeface and colour tokens.
