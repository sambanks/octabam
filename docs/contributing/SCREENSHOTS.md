# Screenshots for the manual site

The manual site (`docs/site/`) shows LCD screens captured from the emulator
through the panel UART. Two tools capture; the final image names come from
one of them.

| tool | what it does | writes |
|---|---|---|
| `tools/site/capture_manual.py` | builds a remix, boots it, drives the panel with named steps per module, renders black-on-white PNGs | `docs/site/img/<module>/<screen>.png` and a record in `docs/site/screenshots.json` |
| `tools/emu/live_shots.py` + `tools/site/shots/*.script` | replays a key script on the port (`ot_emu`); one `shot` line per PNG | `docs/site/img/<module>/<screen>.png` for the `shot <module>/<screen>` names in the script |

`capture_manual.py` is the capture path for the manual. The four scripts in
`tools/site/shots/` write 70 of their shots under `raw/` and `raw2/`
(probe walks, measured: no `raw/` or `raw2/` directory is in the tree, and
no tool or doc maps those names to a final name). Those shots are scratch.
A screen that goes in the manual is a step in `capture_manual.py`, whose
`shot(p, module, name, caption, remix)` call sets the final name.

Confidence markers: **measured** = checked in the tree or on a run; **read**
= from the source of the tool, not run for this document.

## When to re-capture

Re-capture in the same PR when the diff changes anything a shot shows:

- a module's menu rows, names, value formatters, pages or `FxPage` layout;
- BRAIN screens;
- a remix's module set, where it changes what a screen lists;
- the panel steps a capture function relies on (menu rows, popup geometry).

After a rebase onto `origin/main`, check whether main changed any of those
since the merge-base:

```bash
git diff --stat $(git merge-base HEAD origin/main) origin/main -- \
  modules/*/manifest.py modules/brain tools/site docs/site/usage docs/site/img docs/site/screenshots.json
```

A non-empty result touching a module your branch also touches means
re-capture that module's group.

`mkdocs build --strict` checks that image links resolve. It does not compare
a PNG with the current UI; a stale shot passes CI.

## Run (read, from `tools/site/README.md` and `capture_manual.py`)

```bash
python3 tools/site/capture_manual.py <group> [<group> ...] [--project <dir>]
```

Groups and what each captures, from the `shot(...)` calls:

| group | remix built | modules shot |
|---|---|---|
| `core` | `octabam` | rec-trig-mute, quantize-live-rec-toggle, mute-modes, quantizer, rlen-plen, midi-scenes, scenes-p2, plocks-p2, direct-jump-kyoti, reload-from-project |
| `plocks` | `octabam`, PLATE REV on track 1 | plocks-p2 held lock and released Part value; use a disposable project with trig 1 empty |
| `features` | `octabam` with REC THRESHOLD, EUCLID FILL, RND NAME and STEM REC added and REC TRIG MUTE and LOAD METER removed (a scratch selection; THR and REC_TRIG_MUTE share a hook, and LOAD METER declares a conflict with STEM REC) | euclid-fill, rec-threshold, stems, rnd-name |
| `inserts` | `octabam`, one effect per track | setup and main pages of SPECTRUM, CHARACTER, MODULATION, TRANSIENT, GATE VERB, DELAY |
| `bus` | `octabam-bus` | fx2-lock, tempo-bus, load-meter, memory, usb, and the DELAY SERVER, SEND and REVERB SERVER pages |
| `extras` | one test remix per module (character-txtr, testgen, sidechain-compressor, miniverb, tapeecho, vocoder, wave, distorx, devilish; also alone as `distorx`) | setup and main page of each |
| `machines` | `analog-bassdrum`, `octatrick`, `blackpyramids-303`, `octa303`, `cxosc` | analog-bassdrum, synth, direct-jump, blackpyramids-303, octa303, cxosc |
| `octa303` | `octa303` (test remix) | octa303 alone (its two pages), without re-capturing the other machines |
| `morph` | `morph` (test remix) | morph: the window on T1 armed, then STEPS 8 and x 2 |
| `midi-loopback` | `midi-loopback` | midi-loopback (EXT/INT/BOTH windows and CHAN indicators) |
| `midi-follow` | `midi-follow` | midi-follow (source selection and FOLLOW register window) |
| `midi-scales` | `midi-scales` | midi-scales (OFF, Major, Dorian, Mixolydian) |
| `probes` | `cfmeter` | CF METER |
| `utilities` | `buffer-saver` | buffer-saver (a one-second take, then FUNC + PROJ: the SAVE SAMPLES? question) |

The project is `--project`, `OT_PROJECT`, or the path in
`~/.octabam_project`. The tool copies it to `out/manual-captures/<remix>/project`
and edits only the copy: it assigns each track's effect with
`ot_project.set_fx` (so the project needs no pre-arranged layout), builds
with `BUILD=91 XBUS=1 SPEC=1`, and stages a card with `stage_card.py`.
Logs: `build.log`, `stage.log`, `port.log` beside the image.

Prerequisites: a worktree with `vendor/`, `.venv/` and
`out/raw/section_3_MAIN_OS.bin` (`AGENTS.md`, "Worktrees and the shared
checkout"), and the submodules initialised (`git submodule update --init`).

## Records and coverage

- `docs/site/screenshots.json`: one entry per image: file, caption, remix, source, and the sha256 of the firmware image it was taken on. Commit it with the PNGs.
- `docs/site/screen-notes.json`: for a module with no LCD screen of its own, the sentence that says why. The generated `reference/screenshots.md` page shows the record count, else the note, else "Capture pending."

A new module is therefore one of: a capture step in `capture_manual.py` and
its PNGs, or an entry in `screen-notes.json`. Without either it shows as
"Capture pending."

## Review each capture

A key sequence that ran does not show that it reached the intended page.
Open every changed PNG before committing.

## The probe scripts

Use `live_shots.py` when walking the panel to find out what a key does:

```bash
OT_PROJECT=<dir> .venv/bin/python3 tools/emu/live_shots.py <remix> \
  --script tools/site/shots/<remix>.script
```

The directives are in the `live_shots.py` docstring (`key`, `chord`, `hold`,
`release`, `enc`, `wait`, `shot <module>/<screen>`, `quit`). Each script
header records the walk it was written for. Key codes used there: `0x25`
FX1, `0x26` FX2, `0x10` `0x11` `0x12` tracks 1-3, `0x32` NO, `0x28` PROJ.
`shot raw/<name>` writes `docs/site/img/raw/<name>.png`, which is not
gitignored (measured: `git check-ignore` is silent); delete `raw/` and
`raw2/` before committing.

FX page behaviour, measured on the port 16 Oct 2026:

- Boot restores the FX1 setup on **page 2** (the routing grid).
- Track keys switch tracks on both pages.
- FX2 from FX1's page 2 opens FX2's page 2 (stateful).
- NO on page 2 goes to page 1; YES on page 2 opens the routing-cell editor.
- FX from page 1 stays on page 1; page 2 is reached only from boot or from the other FX slot's page 2.
- The bus FX2 servers have one page and no routing page.
- The tuner shows `--` under the live path: the port's DSP track chain produced no output (tone on the DSP input, gain table filled, TX0 ring all zero, 16 Oct 2026).

## Before the PR

```bash
git status --short docs/site                # the PNGs and the two JSON files you meant to change
mkdocs build --strict --config-file docs/site/mkdocs.yml
```

Name the groups, project and remix in the PR body.

The `midi-loopback` group uses a sample-free fixture starting on audio track 1,
with MIDI channel 1 and routing EXT. Pass that local fixture with `--project`.

The `midi-scales` group uses a sample-free fixture starting on audio track 1,
with MIDI KEY OFF. Pass that local fixture with `--project`.
