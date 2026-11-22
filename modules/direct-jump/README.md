# `direct-jump` — DIRECT JUMP

A pattern change lands at the next step instead of at the pattern's end,
the Analog Four / Rytm direct jump: CHAIN AFTER's unused value 1 becomes
DIRECT. Built from
[timhastie/octatrick-modules](https://github.com/timhastie/octatrick-modules)
(submodule `upstream/`, pinned to `v2.9` (`525f4b1`)). `Kind.CF_PATCH`: one floating ROM
cave on the pattern-queue setter and the tick handler, four fixed pokes (step and label table entries, the menu setter, the project loader). No DSP code, no menu row of its
own (the option appears in PROJECT > CONTROL > SEQUENCER > CHAIN AFTER as
option 2, between PAT.LEN and 2/16).

A pattern chosen while the sequencer runs ([PATTERN] + [TRIG], [BANK] +
[TRIG], MIDI program change) takes over at the next step boundary, at the
step count the old pattern had reached, instead of at the old pattern's end
or after its CHAIN AFTER length -- the Analog Four / Analog Rytm direct
jump. Off by default: DIRECT is a position of a setting every project
already stores, so a project that never selects it plays exactly as stock.
`upstream/direct-jump/README.md` is the full description, with what was
measured (audio-measured hand-over timing, 26 Sep 2026) and what was
inferred.

## How it is built

Source: `upstream/` is Tim's repository (submodule, pinned to `v2.9` (`525f4b1`)).
Nothing inside `upstream/` is edited here. The manifest here
(`manifest.py`) executes `upstream/direct-jump/manifest.py` from the source
on disk and re-exports its `MODULE`; that manifest derives its source paths
from its own directory, so the same file builds at `modules/direct-jump/`
in Tim's tree and at `modules/direct-jump/upstream/direct-jump/` here. The
cave's ratified bytes (`pinned`) are re-linked from `direct_jump.s` and
compared on every build.

## Updating

Bump the submodule pin; the pinned bytes either re-link or the build
refuses.
