# The oracle — the regression gate for `ot_emu` core work

    tools/emu/ot_emu/oracle/oracle.sh [REF] CAND [--build-dir <cand cmake tree>] [--fresh] [--tag name] \
        [--stamp-tol N] [--frame-tol N] [--audio-tol L] [--wav-tol L] [--audio-frac P] \
        [--ref BIN] [--image BIN] [--card IMG] [--card2 IMG] [--set NAME] [--project NAME] [--out DIR]

    tools/emu/ot_emu/oracle/phase_b.sh CAND [--build-dir <tree>] [--tag name] # the Phase B gate, both references

Exit 0 = every check PASS. The report is echoed and saved under
`out/_oracle/reports/<stamp>[-tag].txt`; per-binary outputs are cached under
`out/_oracle/runs/<sha256[:12]>/<check>/` (a binary with the same bytes is
never rerun unless `--fresh` or its inputs' size/mtime changed; reference ==
candidate reruns the candidate side into `runs/<sha>-b/` as the determinism
check). Written by Tim Hastie as `out/_agents/speed-oracle/`
for the speed work (O15a–O15f), moved here with audio tolerances for
Phase B (O16a); the milestone records are
`git show 666b6154:docs/firmware/COLDFIRE_PORT.md`.

## Inputs — nothing here is in git

| input | flag | environment | default |
|---|---|---|---|
| reference binary | first positional, or `--ref` | `OT_ORACLE_REF` | `out/emu/ot_emu.ref-73c2815` |
| firmware image | `--image` | `OT_ORACLE_IMAGE` | `out/raw/section_3_MAIN_OS.bin` (Elektron bytes: never copied, never committed) |
| card for `card`/`inter`/`interdsp` | `--card` | `OT_ORACLE_CARD` | `out/_agents/port/otlive.img` |
| card for `render` | `--card2` | `OT_ORACLE_CARD2` | `out/_agents/audio/otlive2.img` |
| set / project on the cards | `--set` / `--project` | `OT_ORACLE_SET` / `OT_ORACLE_PROJECT` | `OTLIVE` / `PROJECT` |
| cache + reports | `--out` | `OT_ORACLE_OUT` | `out/_oracle` |
| python | – | `OT_ORACLE_PY` | `.venv/bin/python3`, else `python3` |

## The two frozen references (untracked under `out/emu/`, keep both)

- `out/emu/ot_emu.ref-1e76ac5` — the pre-speed binary (before O15a), the
  gate for the whole of Phase A.
- `out/emu/ot_emu.ref-73c2815` — Phase A's result: the PGO binary built by
  `pgo.sh` at HEAD `73c2815` (sha256 `3c7d2111891c…`), the binary the last
  Phase A report gated 28/28 against `ref-1e76ac5`. Made by
  `cp -p out/emu/ot_emu out/emu/ot_emu.ref-73c2815; chmod a-w`.

The two are byte-identical on every check (28 PASS, strict, report
`20260912-131027-b0-1e76ac5-vs-73c2815`), so either is the reference for the
non-audio checks; **Phase B steps are gated against BOTH** (`phase_b.sh`):
strict on everything but the two audio captures, the audio within the Phase B
tolerance against either. The second pass costs only the comparisons — the
candidate's runs are cached.

## The battery (all jobs in parallel; ~50 s wall with the Phase A binary on both sides, ~110 s with `ref-1e76ac5` on one)

| check | command (both binaries) | compared |
|---|---|---|
| `stock` | `--image <image> --ms 1000 --serial-out --golden` (the ctest `rtos` gate through the CLI) | boot log (paths normalised), `serial.a` / `serial.b` bytes, `golden.json` bytes |
| `card` | the O14i standard: `--card <card> --mount --set <set> --project <project> --ms 1000 --serial-out --golden` | the same |
| `render` | the O14k reference: `--card <card2> --mount --set <set> --project <project> --dsp --sequencer --internal-clock --poke-trig 5 --main-level 64 --audio-out <d>/run3 --frames 3000 --pre-roll 200` | `run3_core0.wav` (7,936,292 bytes: 330,677 frames x 8 slots x 24-bit) through `cmp_audio.py` with `--wav-tol`, the batch log |
| `inter` | `--interactive --card <card> --mount --set <set> --project <project> --internal-clock --rtc 1000000000`, `drive.py`'s sequence: `status`, `frame on`, YES, MIXER, NO, T1 double tap (50 ms down / 150 up / 50 down / 100 up), DOWN, RIGHT, NO, NO, PLAY, 20 x `run 100`, STOP, 5 x `run 100`, `status`, `quit`; `tx` + 9 `peek`s after every step | `ready` line, boot log, every reply (`run` stamps and `wall=`/`idle=` cut out), the UART A byte stream (`tx.bin`, 18.3 KB) and its per-step split, the peeks (sequencer STEP/TICK/TRANSPORT, clock record, UI window, popup record, current track, page kind, PART_PTR, CUR_PATTERN, gain table), the `run` stamps (sample + frame count per run: strict unless `--stamp-tol`/`--frame-tol`) |
| `interdsp` | the same with `--dsp`, `audio start main` before PLAY, `audio read` after every `run` | everything above plus `audio.pcm` (LE s16 stereo, 2.82 s from PLAY through STOP+500 ms = 497,788 B = 124,447 frames) through `cmp_audio.py` with `--audio-tol`, and `audio status` (captured/pending/dropped) |
| `ctest` | `ctest` in `--build-dir` | `100% tests passed`, `out of 7` |

28 checks with `--build-dir`, 27 without.

## Tolerances — all default 0 (byte-strict); only the audio and the stamps have any

| flag | what may move | check |
|---|---|---|
| `--stamp-tol S` | `run` sample stamps, by S samples | `cmp_stamps.py` |
| `--frame-tol N` | `run` frame counts by N; the audio captures' LENGTH by N frames (the trailing frames are not compared) | `cmp_stamps.py`, `cmp_audio.py --len-tol` |
| `--audio-tol L` | `interdsp.pcm`: max abs diff L in 16-bit LSB | `cmp_audio.py` |
| `--wav-tol L` | `render.wav`: max abs diff L in 24-bit words | `cmp_audio.py` |
| `--audio-frac P` | at most P percent of the compared samples differ (both captures) | `cmp_audio.py` |

`cmp_audio.py A B [--fmt s16|wav24|auto] [--tol L] [--frac P] [--len-tol N]`
prints one line — frames per side, max abs diff, differing count and
percent, the first differing frame (channel, both values), the onset frame
(first frame with any non-zero sample) on each side, trailing length
difference, and a SHIFT HINT when B equals A displaced by ±1..3 frames — then
PASS/FAIL. **Alignment is never tolerated:** the onset frame must be
identical on both sides (a schedule change may move an LSB, it may not move
WHEN the audio starts). Byte-identical files short-circuit (no decode).
Everything else — logs, serial, goldens, UART stream, per-step
sizes, peeks, replies, `ready` — is always byte-strict, whatever the flags.

**The Phase B contract** (`phase_b.sh`, O16a):
`--audio-tol 2 --wav-tol 8 --audio-frac 0.5 --frame-tol 1`, against both
references. Steps that change no schedule (B0, B1) are held at 0. Phase B
changes the DSP pair's scheduling, and any change of the core interleave
(quanta 1 / 64 / 2,000 / 50,000, measured in O12) moves a few samples of a
reverb return by one LSB at a host-frame edge; the hardware runs the two
cores in parallel. What is held byte-strict is the firmware's observable
behaviour: screens, LEDs, sequencer timing, the goldens' dispatch order.
The audio must stay sample-aligned, and the `run` frame counts and capture
lengths may move by 1 only where a frame edge lands on a run boundary.

Checked on real captures (the Phase A `interdsp.pcm` and
`run3_core0.wav`): identical → `PASS` in 0.02 s / 0.04 s; 300 samples moved by
±1..2 → `max 2, 0.1125 %`, FAIL strict, PASS at `--tol 2 --frac 0.5`; the
same moved by +3 → FAIL `max 3 > 2`; the PCM shifted by one frame → FAIL
`onset moved: frame 98 vs 99` with `SHIFT HINT: B == A shifted -1 frame(s)`;
one frame shorter → FAIL at `--len-tol 0`, PASS at `--len-tol 1` (frame
count 124447 / 124446, 0 samples differ); 500 words of the WAV moved by
±3..8 → `max 8, 0.0189 %`, decode + compare of 2,645,416 24-bit samples in
0.4 s (pure Python, no numpy in the venv).

## What "byte-identical" legitimately excludes

- `status wall=` (wall-clock seconds inside `run`) and `status idle=` (the
  emulator's own idle-skip count: a mechanism, not firmware behaviour) — cut
  from the replies; `wall.txt` (boot / run wall, idle= / wall= per
  interactive run) is reported, never compared.
- The RTC: the batch default is `--rtc off` (DSPI chip-select 2 = loopback,
  the dialog reads 2000-00-00); `--interactive` defaults to the HOST clock, so
  the oracle pins `--rtc 1000000000` (SUNDAY 2001-09-09 01:46:40 UTC, frozen)
  — the same dialog, clock record (`07d1 09 09 01 2e 28`) and LCD bytes on
  every machine and run.
- Output-file paths in the batch logs (`serial out :`, `golden     :`,
  `audio out  :`) and the binary's own path — normalised to `<OUT>`/`<EMU>`.
- ctest timing lines.
- `--main-level` defaults to 64 under `--interactive` (O14k); both sides get it.

## Not covered (say so when a change touches it)

- Knobs/encoders (rows 0x30-0x36), FUNC chords, SETUP pages, the file
  browser, the crossfader, audio IN (`--audio-in`), core 1 / `audio start
  cue|all`, `--frame-timer` with `--dsp`, `--boot-logo`, long play (RSS growth),
  `pace on` (the wall pacer is off in every job), threads and shutdown
  timing (a change that adds threads is checked separately: a
  `-fsanitize=thread` Debug build through `drive.py`, a measured
  quit/EOF/SIGTERM).
- The panel server's own endpoints (`/screen.txt`, `/leds`, takes) are
  decodes of the same UART stream by `tools/panel/panel_link.py`; the UART
  byte diff subsumes them, the server's wall pacing is not exercised.
- A change that legitimately moves sample stamps (O14j's DMA timers moved
  batch stamps ~140 samples) must be run with `--stamp-tol`; the gate then
  still holds the UART, peeks, goldens and audio (to their tolerance) — and
  the goldens will FAIL on any stamp move, which is the point: such a change
  needs a new reference binary, agreed and named, not a wider tolerance.
- The audio tolerance is a bound on |diff| and on how many samples differ; it
  does not measure whether a small diff is audible or structured. A step that
  needs it must say where the diff sits (`cmp_audio.py`'s first differing
  frame) and why (O12: the reverb's LSB at a host-frame edge).

## Files

- `oracle.sh` — the gate. `phase_b.sh` — both references with the Phase B
  tolerances. `drive.py` — the `--interactive` battery for one binary.
  `tmo.py` — timeout runner (process group kill; macOS has no `timeout`).
  `cmp_text.py` — normalised text diff, first differing line.
  `cmp_stamps.py` — stamp diff with tolerance. `cmp_audio.py` — audio diff
  with tolerance + alignment. All children are started in their own process
  groups and killed by pid on timeout or Ctrl-C; nothing listens on a port.
