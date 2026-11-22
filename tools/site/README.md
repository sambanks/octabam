# The manual site

The musician-facing manual, built with MkDocs with the shadcn theme and deployed to
GitHub Pages by `.github/workflows/pages.yml` on pushes to main. The same
build, without the deploy, runs as the `site` job on every PR
(`.github/workflows/ci.yml`).

`release.py` says what the site publishes: one release (`v0.5`, the git tag
the web builder's patches are built from) of three remixes (`octabam`, `octabam-verbs`,
`octabam-bus`). A remix
that is not listed (`cxosc-core`, the test remixes) is not in the manual, has no
overview page and no builder entry; it stays in the repository.

`gen_pages.py` renders the generated pages from this commit's manifests
(`tools/remix/index.py`, the registry). The generated files sit under
`reference/` in the site directory, are gitignored, and never appear in
the tree, so the site and the manifests cannot drift: a merge to main
rebuilds them.

Generated, gitignored:

- the manual, `reference/manual/` (below): one manual for every published remix
- `modules.md`, the Feature Directory (in the nav under More): what is in the release by the
  manual's sections, with the remixes that have each feature, linked to the manual, then every
  other contributed module by category, linked to its own page
- `modules/<name>.md`, one page per contributed module: the usage fragment, which published
  remixes have it (and its manual page), and its facts; no test status.
  The pages are not in the nav (each carries a `not_in_nav` line); the directory reaches them
- `_remix-<name>.md`: the feature table of the remix's overview page
  (`remix-<name>.md`, hand-written), each row linked to the manual; the
  stock effects the remix keeps are one row

## The manual

The published remixes share most of their features, so they share one
manual (`gen_manual.py`, run by `gen_pages.py`), written under
`reference/manual/`. Each page says which remixes have its feature. What is
particular to one remix, and how to install it, is on that remix's
hand-written overview page (`remix-octabam.md`), which the manual's
introduction links; there is no per-remix copy of the manual.

- `index.md`: the introduction: the remixes (`SUMMARY`), conventions, the
  table of which remix has which feature, installing
- one page per feature a musician operates, in the section `PLACE` gives it:
  `effects/`, `bus/`, `machines/`, `sequencer/`, `parts/`, `midi-usb/`,
  `utilities/`. A module `PLACE` does not name goes by its category, so a new
  module is not left out
- `fixes.md` and `inside.md` ("Behind the scenes"): one page each, a section
  per module. A fix or a service other features rely on (STORE, EVENTS, the
  effect loader, the bridges) has nothing to operate, so it is explained and
  credited there rather than given a chapter
- a module that is part of another feature's use is a section of that
  feature's page (`FOLD`: RIG HOSTS and FX2 LOCK on SEND, TEMPO SYNC on the
  bus delay, the VERB rows and VERB PARTS on VERBERATION). A folded row of a
  chooser lists only the starting values that differ from its host's
- `brain/`: BRAIN, one page per part of it (index, templates, remixes,
  settings, performance, log, about, files), from the hand-written fragments
  `docs/site/manual/brain-<part>.md`
- `credits.md`: the authors, one entry per GitHub account however the
  manifests spell it (`gen_pages.who`: a name with a space over a handle,
  never `account/repository`; the repository is named in the byline)

Stock effects are not documented. No page carries a test status.

Each feature page is, from the manifest, never typed: the byline and the
remixes that have it, which chooser an effect is in (FX1, FX2, read from each
remix's `fx1` and the module's `SLOTS` setting; per remix when they differ),
the knob layout (name, values, default, one-line meaning) with what a MODE
renames, and the settings a musician can change with the value each remix
starts them at (build-time settings are not shown). What a module needs is
not shown: the image is built. From the hand-written usage fragment
(`docs/site/usage/<name>.md`): the prose, with its site links rewritten for
the page's depth. The fragment's own `## Parameters` table is dropped, because
the knob tables come from the manifest, and so are its development sections
(`DROP_SECTIONS`: `## Changed on ...`, `## Checked`, `## Verification ...`,
`## Hardware ...`), which stay on the module's Feature Directory page. A
sibling link in a fragment (`kits.md`) points at that module's page or
section, or loses its link when the module is not in the manual. A module
with no fragment shows its manifest line, so the manual has no hole.
`HIDE_SHOTS` in `gen_manual.py` lists a screenshot not to show.

`verify_docs.py` refuses a manual page that carries build or test text
(`gen_manual.LEAKS`): a test remix, an emulator result, "in the same image",
a dated change note, a timing in µs, a Python bytes value, "not in an
official remix". Fix the usage fragment (or the manifest line), not the
check. A fragment serves the Feature Directory too, so write it for a
musician.

To improve a knob's row in the manual, edit the `Param` `doc` in the manifest.
To improve a module's prose, edit its usage fragment. A page title is
`_label` in `gen_pages.py` (`MANUAL_LABEL` in `gen_manual.py` where the
directory needs a longer one to tell two modules apart).

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
