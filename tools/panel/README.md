# The virtual front panel

By **Tim Hastie**, from his fork of octabam,
[timhastie/octa-panel](https://github.com/timhastie/octa-panel) at
`be68244` (10-25 Sep 2026; MIT, as octabam). The panel (`tools/panel/`),
the macOS app (`tools/panel/app/`), the key/LED map and its evidence
(`KEYMAP.md`, `docs/firmware/PANEL.md` section 9, `key_map.json`, `param_map.json`) and the
port features the panel runs on (`tools/emu/ot_emu`: `--interactive`,
pacing, the RTC, the DMA timers, bursts, the page table, `--dsp-rt`, card
write-back, the memory-to-memory eDMA, per-track taps; the dsp56300 hunks
for `--dsp-rt` in `tools/patches/dsp56300.patch`) are his. His milestone
records O14i-O24 are `git show 666b6154:docs/firmware/COLDFIRE_PORT.md`;
the features still in the port are `tools/emu/README.md` "Port features".
Everything below
"The panel, as he wrote it" is his README, unedited.

**The face** (25 Sep 2026) is Mark Roberts' MKII panel from
[markandrus/octemu](https://github.com/markandrus/octemu) (`tools/panel/skin/gen_svg.py`,
MIT), in octabam's dark palette: the server generates it into `out/panel_skin/`
and serves it as `/skin.js`; the page lays its keys, knobs, fader and LEDs over
the drawing as transparent hit areas and lights the drawing's own `lit` classes.
On an MKI port (the default until `--mkii` decodes the MKII panel), PROJ, PART
and ARR send the MKI's FUNC chords (FUNC+MIXER, FUNC+MIDI, FUNC+PATTERN); AED and
REC3 have no MKI equivalent.

## In octabam

`tools/emu/README.md` lists the other ways to run the port (`make
emu-live`, scripted runs, the gates).

Route A (`emu_rtos.py`) was retired on 26 Sep 2026: the panel runs the
port only. `--backend`, `--no-rtc`, `install_rtc` and `/press` went with
it; `/transport` taps the matrix keys. His text below still describes
both backends.

```sh
make panel REMIX=octabam-bus                       # OT_PROJECT=<dir>, or the path in ~/.octabam_project
make panel REMIX=octabam-bus PANEL_PORT=8571 PANELARGS='--sound off'
make panel-app                                   # out/Virtual Panel.app (File > Open Firmware Image: out/panel_<remix>.bin)
```

- The port runs as an MKII (`ot_emu --mkii`, `docs/firmware/PANEL.md`
  section 4c): the page draws PROJ / PART / AED / ARR / REC3 and the PAGE legend
  and `/map` returns `"model": "mkii"`. `PANELARGS=--mki` runs it as an
  MKI (the MKI keymap; those keys do nothing there). `tools/emu/live.py`
  also passes `--mkii` by default (`--mki` to drop it); the keys are
  `key_map.json` `proj`/`part`/`aed`/`arr`/`rec3`/`page`. `panel_check.py`
  opens the PROJECT menu with PROJ on an MKII (FUNC + MIXER does not open
  it there); both models pass all five checks. The gates (`verify_set`,
  the port's self-tests) run as an MKI.
- `make panel` builds the remix (`XBUS=1 SPEC=1`), copies it to
  `out/panel_<remix>.bin` (a later build into `out/mainos_bus.bin` cannot
  change what a running panel respawns) and starts `panel_server.py` on
  <http://localhost:8563/>.
- The card is `out/cards/<project folder name>.img` (`PANEL_CARD=` for
  another). The first run creates it from the project and its sibling
  `AUDIO/`; every later run boots the file as it is, with write-back, so
  a project saved on the unit (FUNC+MIXER, PROJECT, SAVE) is there next
  time. Delete the `.img` (and its `.json` sidecar) to start again from
  the project folder.
- The SET DATE/TIME dialog the firmware opens at boot is closed with YES
  by the server; the port answers the RTC with the Mac's clock under
  `--interactive`, so the dialog shows today's date.
- Sound: the child runs `--dsp-rt`. The output device needs `sounddevice`
  in `.venv` (`make emu-setup`); without it the capture, takes and the
  HEADPHONES jack (WebAudio in the page) still work.
- `tools/panel/panel_check.py` drives a running server over HTTP: the
  screen decodes, a key changes it, a knob changes a value in the
  firmware's memory, SAVE PROJECT writes the card; `--phase persist`
  against a restarted server checks the saved value is still there.

Measured 25 Sep 2026 on a MacBook Air (arm64), bamsep26 +
`OCTABAM89_setgate`, and the stock image + the ot-tools OTLIVE fixture:

- Paced, playing, `--dsp-rt`: 1.000x real time on the panel's own meter
  (20.1 s wall, 20,155 emulated ms), child busy 7.8 s of the 20 s.
- Unpaced, playing OTLIVE, `--dsp-rt` driven over the pipe: 475-684
  emulated ms per wall second over five runs (5-10 s emulated each, load
  average ~6 from other work on the machine); main out non-zero (899,484
  of 943,772 samples over 10 s). His own build on the same Mac, the same
  runs interleaved: 421-597, the same sample counts. His measurement on
  his machine was 1,208 (O17b); this Mac does not play OTLIVE in real
  time with the cores.
- `OCTABAM89_setgate`'s main out is all zero in both DSP modes (its
  samples are not on the card; the set gate's own TX0 count is zero too).

What changed on the way in (the port was three-way merged against the
fork's base, 9a49f21, keeping everything octabam gained since):

- His four DMA timers replace octabam's single DTIM1 (PR #424). DTIM1
  now counts the 132 MHz bus clock (his evidence: DTRR2 = 132,000,000 for
  the one-second soft timer), so the UI tick is 120 Hz where #424 ran 240
  Hz off the PIT's 264 MHz.
- Read watches (`--watch-read`) send data reads down the slow path, as
  write watches do under his page table.
- The `--live` FIFO poll and the USB host's I/O run on an instruction
  schedule that the bursts stop at; the USB start-of-frame and iso polls
  are on the burst horizon. `--fast` is gone: the bursts are exact.
- The dsp56300 hunks were rebased from his pin (3c01813f) onto ours
  (8ccdd843): upstream already carries the MPYI sign, the dynamic
  fast-interrupt return PC and the pending-request-at-arm service, so
  those are not in the patch; the rest is (`scripts/setup.sh` lists it).
  Existing trees: `make dsp-repatch`, then `make emu-cf`.
- `app/build.sh` takes `swiftc` from `xcrun` (the CommandLineTools
  compiler refused Xcode's SDK here).
- His firmware modules were ported afterwards (PR #458): `modules/direct-jump`,
  `modules/quantizer`, `modules/synth`; remixes `octatrick`, `octatrick-usb`.

---

## The panel, as he wrote it

A clickable Octatrack, driven by the real firmware under an emulator — the
C++ ColdFire port (`out/emu/ot_emu --interactive`, the default since 12 Sep
2026) or the route-A oracle (`tools/emu/emu_rtos.py`). The screen is what
the firmware sends its LCD; the keys, knobs and LEDs go over the panel's own
wire. It is a way to *operate* a built image before flashing — walk menus,
open pages, turn knobs, start the sequencer — not just boot it.

**As an app (macOS):** `bash tools/panel/app/build.sh` once, then open
`out/Virtual Panel.app` — a native window that starts the server itself,
loads the default project (`out/_projects/otlive/…`) and offers
File ▸ Open Project… (`tools/panel/app/README.md`).

**In a browser:**

```sh
.venv/bin/python3 tools/panel/panel_server.py                 # stock OS image
.venv/bin/python3 tools/panel/panel_server.py --image out/mainos_bus.bin   # a built remix
.venv/bin/python3 tools/panel/panel_server.py --project ~/octa/backups/<snap>/<project>
.venv/bin/python3 tools/panel/panel_server.py --project <dir> --audio ~/samples   # more WAV/AIFF on the card
.venv/bin/python3 tools/panel/panel_server.py --card out/cards/OTLIVE-PROJECT.img --project <dir> --set OTLIVE --name PROJECT
                                              # a PERSISTENT card: what the unit saves stays ("Your card" below)
```

Open <http://localhost:8563/>. Under the port, boot is ~3 s and boot + the
fixture project ~21 s wall (measured 12 Sep 2026); under route A ~5 s and
~1½ min (the page says so). The SET DATE/TIME dialog the firmware opens on
every boot is closed for you with YES (which stores the clock in RAM and
leaves a `DATE/TIME STORED` box on the track screen until the first key,
on either backend).

Almost every control is wired (`tools/panel/key_map.json`, 47 keys, 7
encoders and 40 LEDs measured — `KEYMAP.md` has the evidence): keys press,
encoders turn with the mouse wheel or a vertical drag (endless, as on the
unit; a double-click puts the parameter the encoder controls back to its
init value, through the firmware, and with a TRIG key held a double-click
is the encoder's PUSH: it removes that step's lock on the parameter --
"Parameter locks" below), the crossfader drags (left = scene A, right =
scene B; its value is in its tooltip), LEDs follow the firmware. Unwired:
REC AB/CD and SCALE SETUP are inferred from their FUNC layers.

The top bar (13 Sep 2026): the status pills (image, phase, x real time),
**SOUND** (a drawer with SOUND ON/OFF: reboot the unit with or without the
DSP cores) and the hint line; the small chevron tab at the top right
hides the bar so the panel takes the whole window (remembered per
browser; a drawer opening shows it again). The AUDIO POOL drawer opens
from the COMPACT FLASH slot on the rear edge; listening is the
HEAD-PHONES jack (VOLUME is its gain, the meter beside it the level).
The MAP KEYS / EXPORT MAP / RUN buttons and the drawer's plug button,
readouts and takes list are gone -- scripts have `/key`, `/knob`, `/run`,
`/audio.wav?take=N`, and the app's Audio menu saves the takes.

## What is real, and what it took to find

**The screen** is decoded from what the firmware sends the panel processor
over UART@`0xfc064000` (`tools/panel/panel_link.py`, protocol in
`docs/firmware/PANEL.md` section 9): `0x10`–`0x17 <column> <8 bytes>` LCD blocks (page = opcode
& 7, page 7 on top, bit 0 the top pixel of a band), `0x2r <mask>` LED bitmap
rows, `0x3n <id>` LED levels, a few one-byte commands. Rendering the RAM
framebuffer at `0x460d1f80` instead comes out with lines rotated (the
firmware's page order on screen is not fixed), which is what the first
version did — kept only as a fallback.

**The keys** are matrix reports on the same UART: `<row> <column-bitmask>`,
a set bit held, a cleared bit released — rows `0x20`/`0x21` the trig keys,
`0x22` the track keys, `0x23`–`0x26` everything else. The server keeps
per-row state so held chords (FUNC+…) work. **Encoders** are rows
`0x30`–`0x36` with a signed detent delta as the second byte.

**The LEDs** are the `0x2r <mask>` rows: `key_map.json` names each LED as
`[row, bit]`; `/leds` returns the 17 row bytes.

The older jump-table path (`press_key_live`, `git show 3ceba41:docs/history/RTOS_FORK.md` section 9) is kept in
the server as `press()` — it calls a key's handler directly, which changes
state but does not redraw under route A, so the UART path is the real one.

## One backend, the port

The panel runs the port (`out/emu/ot_emu --interactive`, built here when
missing); `--backend` was removed with route A on 26 Sep 2026. The `Panel`
code drives the port through `PortRt`, an object with the
handful of things the panel uses of `emu_rtos.Rtos` (`run(ms=)`,
`uart64.rx/tx`, `uc.mem_read/mem_write`, `sample`, `frame`,
`pattern_base()`, `poke_trig()`).

**The port** (`tools/emu/ot_emu`, `git show 666b6154:docs/firmware/COLDFIRE_PORT.md`) runs as
a child process speaking a line protocol over pipes (the `PortProc`
docstring in `panel_server.py` is the contract; the port's side was built
against the same text): `run <ms>`, `key <row> <mask>`, `midi <hex>...`, `knob <row>
<delta>`, `tx`, `peek`/`poke`, `frame on|off`, `status`, `quit`, one line
back per command. The child boots and loads the project itself
(`--card --mount --set --project`, the card image being `stage_project`'s
own bytes written to `out/_panel_card_<port>.img`); the server then sends
the same YES and **the child paces itself** (`pace on`, O15f in
`git show 666b6154:docs/firmware/COLDFIRE_PORT.md`, 12 Sep 2026): while its stdin is empty it advances
emulated time in 10 ms slices so that it tracks its own wall clock —
sleeping inside `poll()` on stdin when ahead (a command wakes it at
once), flat out when the core is slower than real time, re-anchoring past
250 ms of lag — and the server's emu thread only serves the clicks and,
every 20 ms, drains `tx` and audio, reads `pacestatus` and renders. So
the unit runs at **1.00x real time** whenever the core can (idle always,
and playing without the DSP cores on the M5: 999.7 emulated ms per wall
s over 30 s of play, `rt` 0.998–1.003), and at the core's own rate when
it cannot (playing with the cores: ~0.15x). Measured 12 Sep 2026 on the
OTLIVE fixture: MIXER, T3, knob A (PTCH on the PLAYBACK page) and PLAY
all work through the matrix; a page click reaches the firmware within
one slice (`/key` round trip 4 ms idle); STOP takes the frame clock off.
Before O15f the server pumped `run 25` + a 30 ms sleep (0.69x idle
without the cores, 1.02x in bursts of 0.85–2.0x with them) and slowed
that pump for 0.5 s after a track key so a page double-click could land
(`SLOW_PUMP_MS`, gone: the double-tap window is a wall-time property
now, see "Loading samples"). Route A keeps the pump.
A child that answers nothing for 20 s (`ACTION_LIMIT`) is killed by the
watchdog and respawned — boot, load and YES again, `restarts` counts it in
`/status` — as is one that exits. Nothing is left running unseen
(29 Oct 2026, after a hand-started panel's child held three cores for
eight hours): `--parent-pid <pid>` stops the server and its child when
that process is gone (a bench or the app passes its own pid), and
`--idle-timeout <min>` (default 60, `0` = never) stops a server no HTTP
request has reached for that long, with `panel: exiting: …` in its log.
An open page polls `/status`, so a panel someone is looking at stays up.
`--port-bin` names another binary (a
`.py` stand-in runs under the server's Python; `out/_agents/server/
fake_ot_emu.py` speaks the protocol from a route-A capture); `--port-arg`
passes extra flags to the child (`--port-arg=--dsp`). No jump-table path
over the pipe: `/press` answers with a note, `/transport` taps the matrix
keys instead. The port models the RTC on its DSPI too (`--rtc host|off|<epoch>`,
host time under `--interactive`), so the dialog reads the real date; YES
closes it just the same.

Each server port stages into its own `out/_panel_stage_<port>` (two
servers started together raced on the shared tree).

## Mapping the rest of the panel

`tools/panel/key_map.json` is the map (`keys`: id -> [row, bit] of the
matrix report; `knobs`: id -> encoder row; `knob_push`: id -> [0x27, bit];
`leds`: id -> [bitmap row, bit]); the page reads it through `/map` when it
loads, so an edit needs a reload, not a restart. To probe an unknown cell,
tap it from a script (`/key?row=0x23&bit=4&down=1`, then `down=0`; an
encoder `/knob?row=0x36&delta=1`) and read `/screen.txt`, `/leds` and
`/peek` -- `KEYMAP.md` is the evidence per entry and the method. (The
click-to-bind MAP KEYS drawer and EXPORT MAP went 13 Sep 2026.) A
completed entry is a good PR — pure discovery, no firmware bytes.

## Endpoints (for scripting)

| route | does |
|---|---|
| `GET /screen.png` | current LCD as a 128×64 PNG |
| `GET /screen.txt` | the same frame as 64 lines of 128 `#` (dark) / `.` — for agents that grep |
| `GET /status` | `{booted, seq, ran_ms, fault, image, phase, backend, backend_note, speed, rt, pace, restarts, card_busy, card, card_mode, card_rw, card_ejected, card_mount, project}` — **`card`** the image file, `card_mode` `persistent` (`--card`) or `fresh`, `card_rw` the child writes through, `card_ejected` / `card_mount` the eject state, `project` `{set, name}` (O19); `seq` bumps on any screen change; **`rt`** is x real time by the wall clock (emulated ms per wall s over the last second / 1000: 1.0 = the unit's own clock; null under route A and before the pacer is up); `speed` is the older meter, emulated ms per wall second *inside the emulation* over the last 5 s — idle slices are instant, so it reads high (thousands) idle and only approaches `rt × 1000` while playing; kept for scripts; `pace` is the child's last `pacestatus` (`on, rate, ratio, lag_ms, slices, reanchors, slept_s, busy_s, stop`); `card_busy` while a `/samples/commit` reboots (`booted` is false through any reboot, respawn or re-insert) |
| `GET /key?row=0x26&bit=0&down=1` | one matrix key edge |
| `GET /tap?row=0x22&bit=0&n=2&hold=50&gap=150` | `n` presses of one key inside one action (the double-tap chords, see "Loading samples") |
| `GET /knob?row=0x30&delta=2` | one encoder report (rows 0x30–0x36, signed delta) |
| `GET /knob/reset?row=0x33` | the parameter this encoder edits on the CURRENT page back to its init value, done by the firmware (detent reports until the page descriptor's default is reached): `{ok, note, knob, name, page, track, addr, before, after, init, range, sent}`; `ok: false` + `note` and nothing sent on a SETUP window, the MIXER, a menu, MIDI mode, or a dead slot (AMP F/XVOL). "Scenes and the crossfader" below, `param_map.json` |
| `GET /knob/press?row=0x30&hold=60` | the encoder's PUSH switch (key-matrix row 0x27, bit = row - 0x30): down, `hold` ms, up, through the same per-row state as `/key`, so a TRIG key held by `/key` stays held around it -- with a trig held in GRID RECORDING the firmware toggles that step's lock on the parameter the encoder edits (removes it; with none there, sets one at the current value), the unit's [TRIG] + knob press; with a SCENE key held it removes the scene lock. `{ok, row, bit, cell, hold_ms, sent, held, trig_held, scene_held, note}`. "Parameter locks" below |
| `GET /xfader?pos=64` | the crossfader: `pos` 0..127 (0 = leftmost = scene A, 127 = rightmost = scene B, the MIDI CC 48 scale) goes out as the panel board's own fader report `0x40 <byte>`; without `pos` it only reads. Answers the firmware's value `{ok, pos, xf, cc48, byte, scene_a, scene_b}` (`xf` = the firmware's 0x460d16c8, 127 at A; `scene_a/b` = the Part's assigned scenes, 1-based) |
| `GET /samples` | the sample pool: `{pool, staged, files: [{name, bytes, format, on_card, removing}], pending, removed, busy, phase, card, card_mode, card_rw, card_ejected}` -- on a persistent card `files` is the image's `<SET>/AUDIO` (read directly, `on_card: true`) plus the pool's pending files |
| `GET /samples/add?path=<abs>` | copy a Mac file into the pool (converted when needed): `{ok, name, converted, note, format, bytes, pending}` (+ `cmd`, afconvert's argv, when converted) or `{ok: false, error}` |
| `POST /samples/upload?name=<n>` | the same with the raw file bytes as the body (one file per request, no multipart) |
| `GET /samples/remove?name=<n>` | take a file out of the pool; on a persistent card an on-card file is marked for deletion at the next re-insert (again = un-mark) |
| `GET /samples/commit` | re-insert the card: `{ok, phase}`, then `/status phase` shows the reboot (a persistent card is not rebuilt: the pool is copied onto it through a mount while the child is stopped) |
| `GET /card` | the card (O19): `{card, mode, sidecar, meta, project, rw, flush, ejected, mount, pool, audio: {name: {bytes, format}}, removals, sets: {set: [projects]}, busy, phase}` -- `flush` is the child's last `card flush` line (`ok rw=1 through=<sectors in the file> errors=0`), `sets` what the image holds |
| `GET /card/eject?open=1` | flush, stop the child, mount the image on the Mac (browsable; `open=0` leaves Finder alone): `{ok, phase, mount}`; `/status card_ejected`/`card_mount` when done |
| `GET /card/insert` | clean the volume, detach, boot the child again: `{ok, phase}` |
| `GET /keys` | the jump-table handlers (the `press()` fallback) |
| `GET /transport?k=play\|rec\|stop` | PLAY/REC/STOP as matrix taps |
| `GET /leds` | parsed LED bitmap + per-id values |
| `GET /run?ms=1000` | advance emulated time (the sequencer runs here) |
| `GET /peek?addr=0x460d175c&len=4` | read memory (either backend), hex |
| `GET /midi?hex=b04464` | MIDI bytes into the unit's MIDI IN (UART0), the port's `midi` command; `hex` is the raw message |
| `GET /port` | the port child: pid, argv, its own `status` line, report tail, `restarts` |
| `GET /project`, `/map`, `/stack`, `/poke_trig?step=1` | the load report, `key_map.json`, thread stacks, a trig on track 1 |

## Loading samples

On the unit, samples live on the CF card in the set's AUDIO folder: copy
files there over USB, then load them into FLEX/STATIC slots with the
firmware's own file browser. The panel does the same in two steps, because
the card is a FAT image built at boot and the emulator has no hot-plug:

1. **Into the pool.** `/samples/add?path=<abs>` (a file on the Mac) or
   `POST /samples/upload?name=<n>` (the bytes) put a file in
   `out/_panel_pool_<port>/`, the AUDIO folder the card is built from. The
   unit reads WAV and AIFF, 16 or 24 bit, 44.1 kHz, mono or stereo (a
   WAVE_FORMAT_EXTENSIBLE header with a PCM SubFormat included — it loaded
   one, footer `44.1k 16b 2Ch`, 12 Sep 2026 — listed as `… WAV
   (extensible)`); anything else (mp3, aac, flac, 48 kHz, 32-bit float,
   AIFC, 8-bit, more than two channels …) is converted with `afconvert -f
   WAVE -d LEI16@44100 in out` (channels kept, `-c 2` above two;
   `converted: true`, the command in `note` with the file as you named it
   and the pool file it became, afconvert's argv exactly as run in `cmd`; a
   failure answers `ok: false` with afconvert's stderr). Names keep their long form (the
   card is VFAT), the extension is normalised (`.wav`, `.aif`/`.aiff`) and
   characters outside `[A-Za-z0-9._ -]` become `_`; a name already in the
   pool is refused unless the bytes are identical. `/samples` lists the
   pool with each file's header (`16-bit 44.1 kHz stereo WAV`) and what is
   `pending` (not on the card yet) or `removed`. The pool is per server
   port and re-seeded at start from the project's sibling `AUDIO/` and
   every `--audio <dir>`; a running server's additions never touch the
   fixture folder.
2. **Re-insert the card.** `/samples/commit` writes the whole pool into the
   staging tree, rebuilds the image and reboots the unit on it, exactly
   the watchdog's respawn: `/status phase` reads `re-inserting the card
   (reboot, ~40 s)`, then the clock dialog closes, then `ready` (41 s on
   the OTLIVE fixture, 12 Sep 2026). Adds, removes and a second commit
   answer `ok: false` meanwhile. Same on route A (a fresh attach).

Then load a slot through the matrix, measured 12 Sep 2026 on the port
with the OTLIVE fixture (`out/_agents/samples/`: `scan.py`, `drive.py`,
shots `r*` `s*` `t*` `u*`; re-run after the fixes in
`out/_agents/samples-fix/`, shots `f*` — as PNG and `/screen.txt`):

| step | keys | screen |
|---|---|---|
| open the slot list of a track | the **track key twice** — a double-click on T1–T8 in the page, or `/tap?row=0x22&bit=<t-1>&n=2` (one action, 200 ms press to press) from a script. Two `/key` taps land by wall time now that the child is paced (O15f): 0.15 s of wall apart = 150–154 emulated ms press to press, the list opens; 0.30 s = 290–304 ms, it does not (12 Sep 2026, with and without the DSP cores) — the unit's own window, between 191 and 242 emulated ms. Before that the server slowed its idle pump for 0.5 s after a track key (`SLOW_PUMP_MS`, gone) so 0.45 s of wall reached the firmware as 191 ms | `<< MACHINE:STATIC` (or `FLEX`, the track's machine — the OTLIVE fixture boots with T5 current, T1–T4 STATIC, T5 FLEX), `SLOT / BPM / SIZE`, the track's slot highlighted |
| pick a slot | DOWN `0x24.0` / UP `0x26.3` | |
| open the file browser on it | RIGHT `0x24.1` (YES `0x26.1` does the same) | `LOAD FILE TO STATIC 5`, folder `OTLIVE>AUDIO`, the files in name order, the cursor where it was last; the footer reads the highlighted file's header (`44.1k 16b 2Ch`) |
| find the file | DOWN / UP (no wrap; the list is in name order, `extra-1` … `extra-32` numerically, and starts at the top after a boot: 35 taps from `extra-1.wav` to the first file after `fourth-0.wav`) | `clap.aiff`, `sine48k24.wav`, `Upload Sine 48k.wav` were all listed with their 0.33 MB; an unconverted extensible WAV reads `44.1k 16b 2Ch` (16-bit) / `44.1k 24b 2Ch` (24-bit) in the footer |
| load it | YES | back in the list: `5>Upload Sine 48  120  0.33`, `6>clap.aiff  120  0.33`; after the fixes `5>fxext16.wav  0.08`, `6>fxext24  0.12`, `7>Upload Fx 48k.  120  0.33` |
| the other list | LEFT `0x26.4` on the `<<` opens `SELECT MACHINE TYPE` (STATIC/FLEX/THRU/NEIGHBOR/PICKUP): the list follows the track's machine | |
| leave | NO `0x26.2` once — a second NO on the main screen draws `DISARM ALL` (KEYMAP.md) | |

How the opener was found: a PC watch on the list's window store
(`0x4007920c`, in the handler at `0x40077b00` that draws `« MACHINE:%s`)
under a pumpless `ot_emu --interactive` on the empty card, then every
key alone, held 1.2 s, twice, and under 20 held modifiers — only the
double tap of T1–T8 hit. KEYMAP.md's "UP held + track key" (E3) was two
T2 taps that happened to fall inside the window.

## Your card: saving projects and samples

Until 13 Sep 2026 the card was rebuilt from the fixture at every server
start and the port child never wrote its card back to the file, so the
unit's own SAVE landed in RAM and a quit lost the project and every sample
added. Now (O19 in `git show 666b6154:docs/firmware/COLDFIRE_PORT.md`) **the card is a
file that persists, like the CF card in the unit**:

```sh
.venv/bin/python3 tools/panel/panel_server.py --card out/cards/OTLIVE-PROJECT.img \
    --project out/_projects/otlive/OTLIVE/PROJECT --set OTLIVE --name PROJECT
```

- `--card <file.img>` boots that image **as it is** with the child's
  write-back on (`ot_emu --card-rw`: every sector the firmware writes is
  `pwrite()`n to the file as the WRITE SECTORS completes; `card flush` =
  fsync, sent after every action batch, every 3 s idle, and before the
  child is stopped). A missing file is created once from `--project` and
  its sibling `AUDIO` (plus `--audio`), exactly as the per-port card is,
  and a sidecar **`<file.img>.json`** records the set and project names
  (and the removals marked for the next re-insert); later starts need
  only `--card` -- the names come from the sidecar. The firmware does
  not reload its last project by itself in emulation (tested 13 Sep
  2026: a bare boot on the saved card leaves the SET/PROJECT names empty
  with the card ready; the "last set" record the manual describes is not
  on the card), so the sidecar is what boots you back into your project;
  it follows the unit when you change project there (the names at
  `0x100f8480` / `0x100f8378` are read at every flush). **Without
  `--card` nothing changes**: a fresh `out/_panel_card_<port>.img` every
  start, the pool wiped and re-seeded, as every script and the oracle
  expect. `--card` needs the port backend and a binary that knows
  `--card-rw` (an older `out/emu/ot_emu` boots the card read-only and
  `/status card_rw` is false, with the reason in `backend_note`).
- **Saving on the unit**, as in the manual (8.4): **FUNC + MIXER** opens
  the PROJECT menu (`OTLIVE/PROJECT` in the header, PROJECT / SYSTEM /
  CONTROL / MIDI at the left), **RIGHT** enters the PROJECT list (CHANGE,
  SAVE, RELOAD, SYNC TO CARD, SAVE TO NEW, ...), **DOWN** to SAVE,
  **YES**, and **YES** again on `SAVE PROJECT -- ANY PREVIOUSLY SAVED
  STATE WILL BE LOST. CONTINUE?`. Measured 13 Sep 2026 on the OTLIVE
  fixture (`out/_agents/persist/verify.py`, its log, `verify.json` and
  the screens in `shots-verify/`): a first burst of sectors at once, the
  16 bank files ~2 s later -- **20,030 sectors (10.3 MB) in the file**
  3.3 s after the second YES (22,752 in the by-hand run: the save's size
  depends on what changed), the image's md5 changed; SIGTERM to the
  server (what the app's Quit sends) exits in 78 ms with the child gone;
  the next start on `--card` alone boots into `OTLIVE/PROJECT` in 7 s
  with the trig placed on step 3 still there (the trig-3 LED off until
  REC, lit in GRID RECORDING). As on the hardware, what you do not SAVE
  (or SYNC TO CARD) is in RAM: quitting is switching the unit off.
- **Samples** go the same two steps as before (`/samples/add`, then
  RE-INSERT CARD), but the re-insert **no longer rebuilds** anything: the
  server flushes and stops the child, mounts the image on the Mac
  (`hdiutil attach -imagekey diskimage-class=CRawDiskImage`, `-nobrowse`,
  verified to mount the builder's image as FDisk + DOS_FAT_16), copies
  the pool's pending files into `<SET>/AUDIO` (VFAT long names), deletes
  the files marked with `/samples/remove`, removes what macOS drops on a
  FAT volume (`.fseventsd`, `.Spotlight-V100`, `.Trashes`, `._*`,
  `.DS_Store` -- the unit's file browser would list them), detaches and
  boots the child again on the same file. The pool is
  **`<file.img>.pool/`** (never wiped; a file leaves it when it lands
  on the card). `/samples` lists what is on the card by reading the
  image's `<SET>/AUDIO` directly (`Fat16Image` in the server: MBR,
  BPB, FAT, LFN entries; no mount, safe beside the running child) plus
  the pool's pending files; `/samples/remove` of an on-card file marks
  it (a second call un-marks). Measured: a generated WAV added, the
  re-insert + boot 9.1 s, the file listed `on_card`, the pool empty, 38
  files in the image's AUDIO, the firmware's file browser (`T1` twice,
  RIGHT, UP to the top of the list: `AAA persist 440.wav 0.08`, footer
  `44.1k 16b 2Ch`; `shots-verify/J2`) showing it; still there after a
  quit and a restart.
- **Eject / insert** (`/card/eject`, `/card/insert`; the app's File
  menu): eject = flush + stop the child, mount the image **browsable**
  and open it in Finder (`?open=0` skips the `open`) -- copy samples,
  projects or whole sets in and out as with a CF card in a reader; the
  page shows the empty slot and where the volume is, every key answers
  `ok: false` ("the card is ejected") and nothing respawns; insert =
  clean, detach (with `-force` on a second try when a Finder window
  holds a file), re-list, boot. Measured: ejected in 0.5 s at
  `/Volumes/OCTABAM`, a WAV copied into `OTLIVE/AUDIO` by hand, inserted
  and booted in 8.1 s with both files on the card and the image's root
  clean (`OTLIVE` alone). A server started on a card the previous one
  left mounted detaches it first (never two writers).
- **Where the card lives, backing it up.** The app makes
  `out/cards/<Set>-<Project>.img` (configurable: `--card` takes any
  path). The image is the whole card, 64 MB by default (more when the
  samples need it): **copy the `.img` to back it up** (and its `.json`
  sidecar to keep the names; a copy without one is booted into the
  first set and project found on it). Never in git (`out/` is ignored
  and the image holds no firmware).

## Hearing the unit

With the port backend the server starts the child with `--dsp-rt` by
default (`--sound on`; `--sound off` boots without the cores): the two DSP56303 cores
render under the vendored JIT on two worker threads driven by the
ColdFire's own schedule (O17 in `git show 666b6154:docs/firmware/COLDFIRE_PORT.md`), and core 0's
**main L/R** — the words the ESAI puts out to the DAC, 16-bit (the 24-bit
word's top two bytes), 44100 Hz — comes over the `--interactive` pipe
(`audio start main` / `audio read`, O14k). Core 1 is not captured, and
cue is not in the ring -- but with an output device on ("Recording into a
DAW" below) the child streams all eight ESAI words and cue L/R goes to
the device's channels 3-4. An rt child that cannot start (a binary without `--dsp-rt`, a
host whose DSP memory is not MMU-backed, a boot that faults before
`ready`) is respawned with the lockstep `--dsp` and `/status sound_note`
says so; `--port-arg=--dsp` asks for the lockstep cores explicitly;
`/status sound_rt` says which the current child runs, `/rtstatus` is the
child's own line (MIPS per core, waits, edges, faults).

**Playback note (13 Sep 2026, O17b).** With `--dsp-rt` the unit plays
at real time on the M5: `bench.py --dsp --dsp-rt` 1042–1058 emulated ms
per wall s flat out with LTO (O17: 664; 1357 without the cores, 208 with
the lockstep `--dsp`), and under the panel's pacer a 3-minute PLAY held
`/status rt` median 0.981 (0.905–1.080; 986 emulated ms per wall s with
the test's own `/leds` and audio polling on the same machine, 1000 and
`rt` 0.999 over a 10 s PLAY without it) with 44,100 audio frames per
emulated second captured, none dropped, and the trig-row running light
sweeping every 1.94–2.03 s of wall (125 ms per 16th at the fixture's
120 BPM, nominal 2.00 s). What made it: the cores run up to a whole
frame ahead of the ColdFire's clock, core 0's bank word is fenced on the
frame handler's own end-of-exchange mark (the unmask of its interrupt
source), the frame interrupt is delivered at the sample the DSP's clock
says, and the host port's rings and DMA move blocks in bursts
(`git show 666b6154:docs/firmware/COLDFIRE_PORT.md` O17b). The sound is the same content as the lockstep
capture — onset within 2 samples, the same loops at the same time — but
1.3 dB quieter in RMS on the clipping OTLIVE fixture (fewer full-scale
samples; the DSP's output limiter runs on its own history under a
different core interleave), not byte-identical. The lockstep fallback is
~0.2x.

**Priority matters more than you would think** (O15f, 12 Sep 2026): a
server started as a zsh background job (`… &`) runs at nice 5 (`BG_NICE`
is on by default) — harmless on an idle machine, slower whenever anything
else wants the CPU; `/status nice` reports it and the server warns at
start. The darwin *background* class (`taskpolicy -b`, what a
background-QoS or napped app hands its children: efficiency cores) is
3.5–3.7x slower; the server spawns the child with a `preexec_fn` that
leaves that class (`setpriority(PRIO_DARWIN_PROCESS, 0, 0)`), measured
back at full speed under `taskpolicy -b`. What the cores cost
(13 Sep 2026): with `--dsp-rt` boot + fixture load ~7 s (the JIT
compiles the payloads' blocks as they run; ~15 s with the lockstep
`--dsp`, ~6 without the cores), and while the sequencer plays the unit
runs at 1.0x real time (`/status rt`; the lockstep child at ~0.2x); idle
it is paced to 1.00x like everything else. The two DSP worker threads
spin while host traffic is flowing (a command, a push or a pull within
the last 2 ms) and park 200 µs after it stops, so at 1.00x the child is
~260 % of a core while the sequencer plays (O17b's panel run) and ~70 %
idle.

The server drains the child's ring after every pump (25 ms of firmware)
and every action into a ring of its own — the last **180 s**, addressed
by absolute frame number since the capture began (the count keeps rising
across respawns, re-inserts and sound switches; the child's own ring
restarts each time) — and, from PLAY to STOP, into a **take**:
**PLAY opens `out/_panel_takes_<port>/take-NNN.wav`, STOP closes it.**
That is the hardware feeling: press PLAY, the unit plays, press STOP, you
have what it played. The file is 16-bit stereo 44.1 kHz with its RIFF
sizes re-patched after every append, so it is a valid WAV at every
moment (a reader mid-take gets what is there so far); a take open at a
reboot or at exit is closed as it stands. Takes are numbered on from what
the folder already holds and never wiped.

**Manual trigs (23 Sep 2026).** With the cores the child runs in frame
mode from the boot, not only from PLAY to STOP (`/status frame_always`;
`playing` is PLAY..STOP). The DSP frame interrupt runs the firmware's
frame builder, the only thing that turns the mailbox a [TRIG] key posts
into a voice -- with frame mode off the press sat there until the
release overwrote it and the key was silent while the sequencer was
stopped (measured through `/peek`: mailbox `0x46c80354[track]` = `0x40`,
the voice struct idle). And the keys are the unit's: in the TRACKS trig
mode **[TRIG 9-16] play tracks 1-8's samples** and [TRIG 1-8] are the
recorder trigs (the firmware's split at `0x40044584`), so [TRIG 15]
plays T7 and [TRIG 7] does not; FUNC+DOWN held about half a second
steps the trig mode (CHROMATIC next: [TRIG 13] is the root, the others
semitones).

| route | does |
|---|---|
| `GET /status` | adds `sound` (the child runs `--dsp` and its capture is on) and `sound_note` (why not, when not) |
| `GET /audio/status` | `{sound, on, rate: 44100, captured, end, first, cap, dropped, peak: [l, r], take, takes, note}` — `end` = frames ever captured, `first` = the oldest still in the ring, `cap` = 7 938 000, `dropped` = frames the child overwrote unread, `peak` of the last non-empty read, `take` = `{n, recording, frames, seconds, file, start}` while one is open (else null), `takes` = every take as `{n, file, frames, seconds}`; plus `busy`/`phase` (a reboot in progress), `takes_dir`, and `drain` (what the drain itself costs the pump: reads, wall_ms, max_ms); since 13 Sep 2026 also `capture` (`main` \| `all` \| `tracks`: the words per frame the child streams, `tracks` while an output device is on -- O23, the eight ESAI words plus the eight per-track stems -- or `all` on an older child), `words` (2 \| 8 \| 24), `peak_cue` (the cue pair's peak of the last multi-word read) and `output` (the device stream with its `map` and `layout`, "Recording into a DAW" below) |
| `GET /audio/pcm?from=<frame>&max=<frames>` | raw LE int16 stereo frames from `max(from, first)`, at most `max` (default 88 200, cap 441 000), `application/octet-stream` with `X-Audio-From` (where the body really starts), `X-Audio-Frames`, `X-Audio-End`, `X-Audio-Rate`; **204** with `X-Audio-End` when `from >= end`. Served from the ring on the HTTP thread: 1–2 ms for 2 s of audio |
| `GET /audio.wav?take=N` | that take as `audio/wav`, `Content-Disposition: attachment; filename="octatrack-take-NNN.wav"`; a missing take is a 404 JSON |
| `GET /audio.wav?from=&to=` | ring frames as `octatrack-main-out.wav` (default: everything held); an empty range is a 404 JSON |
| `GET /audio/enable?on=1\|0` | reboot the child with/without `--dsp`, the card re-insert's own mechanics: `/status phase` reads `switching sound on (reboot, ~1 min)` / `switching sound off (reboot, ~40 s)`, `booted` false meanwhile, the clock dialog closed after; `ok: false` + `note` while a re-insert or switch runs, while booting, when already in that state, or under route A. Takes and the ring survive it |
| `GET /audio/devices` | the output-capable audio devices PortAudio sees: `{ok, available, devices: [{index, name, channels, rate, default, hostapi}], output, capture, note}` -- rescanned on every call while no stream is open (PortAudio only enumerates at init), so a device plugged in appears once the output is off; `available: false` + `error` without the `sounddevice` package |
| `GET /audio/output?device=<index\|name\|off>` | start the stream on that device (a name matches exactly, then case-insensitively, then as a unique substring: `device=blackhole`), or stop it; answers `{ok, output, capture, note}` -- `note` reads `already on <name>` when that device is already running (the stream is left alone), a 404 JSON with the `devices` names for an unknown one, 500 with `error` when the package is missing or the device would not open. Without `device=`: the state |

Measured 12 Sep 2026 on the OTLIVE fixture (`out/_agents/monitor-server/`,
`verify.py`, logs beside it): the drain costs the idle pump ~0.3 ms per
25 ms of firmware once the pipe reader was buffered (it was 2.2 ms with
`readline()` on the raw pipe, a syscall per byte); playing, `end` grows
at 44 100 per emulated second (`/status ran_ms` deltas); the take opens
with 0 frames at the PLAY key and the first sound is at frame 81 (1.8 ms
after it, the pattern's saved trig on step 1); a take of 2.65 emulated s
took 25.8 s of wall.

**The honest playback note.** The pacer (O15f) holds the unit at 1.00x
only when the core keeps up; with the DSP cores it plays at ~0.15x real
time (the toolbar badge beside the phase shows the live figure, green at
>= 0.97x, yellow below), so anyone *listening* live is behind, and in
bursts — the page's headphones (the HEAD-PHONES jack) play what has
arrived and wait when it runs dry; a replayed take plays at real time. Two more things the fixture taught: `/audio/status peak` at
32767 means the DSP itself is clipping (the fixture's slots 1 and 2 loop
`first-0`/`second-0` at GAIN 75/72 from step 1 — the spike's `tree2`
copy, `out/_agents/audio/tree2`, has them at 48 with looping off, which
is where the `third-0.wav x 0.70` figure comes from); and the VOLUME pot
on the panel is the monitor's gain only, as the hardware pot sits after
the DAC.

## Recording into a DAW

Since 13 Sep 2026 the unit's outputs can go to an audio device on the Mac
in real time: a virtual device such as
[BlackHole](https://github.com/ExistentialAudio/BlackHole) (`brew install
blackhole-16ch`; the DAW records BlackHole's input) or the speakers.
The server opens a PortAudio output stream (the `sounddevice` package,
which bundles PortAudio; it is in the `emu` extra of `pyproject.toml`, so
`uv sync --extra emu` brings it, or into an existing venv `uv pip install
--python .venv/bin/python3 sounddevice` -- without it `/audio/devices`
answers `available: false` and everything else works as before) at
44.1 kHz, int16, 512-frame callbacks, fed from the same drain as the ring
and the takes. In the app: **Audio ▸ Output Device** (Off, then each
device; the choice is remembered and re-sent whenever the unit returns
to ready); by hand:

```sh
curl 'http://localhost:8563/audio/devices'
curl 'http://localhost:8563/audio/output?device=BlackHole%2016ch'   # or device=blackhole, or the index
curl 'http://localhost:8563/audio/status' | python3 -m json.tool      # "output": {...}
curl 'http://localhost:8563/audio/output?device=off'
```

**The channel map.** With a device on the child's capture switches to
`audio start tracks` (O23, 13 Sep 2026) -- the EIGHT ESAI words per
frame (O14k) followed by the EIGHT PER-TRACK STEMS, 24 words a frame --
and the drain lays them out on the device: **main L/R → channels 1-2,
cue L/R → 3-4, tracks 1-8 as stereo pairs → 5-20 (T1 on 5-6 … T8 on
19-20), ESAI words 0/1 → 21-22, words 6/7 → 23-24** (the last two pairs
are zero on the stock firmware; a future mod that uses them is heard), as
many of those pairs as the device has channels for -- a 2-channel device
(BlackHole 2ch, the speakers) gets main L/R, an 8-channel one main, cue
and tracks 1-2, **BlackHole 16ch main, cue and tracks 1-6**, the 64ch
edition everything -- and the stream is opened with exactly that many
channels, so anything further on the device is silent. The stems are
**per-track outputs the hardware does not have**: on the unit only MAIN
and CUE exist, but inside the DSP each track's audio is a block of
samples after its FX1/FX2 chain (and the ColdFire's delay) that the
mixdown multiplies by the track's level and sums into main; the emulator
taps each track's own term there (`git show 666b6154:docs/firmware/COLDFIRE_PORT.md` O23; the buffer map is `docs/firmware/DSP.md` "Core 0's frame"), so a stem is exactly what that track
contributes to main -- muting a track (FUNC + track) silences its stem,
the eight stems sum to the main pair to within the mixdown's own rounding
(−52 dB: each stem's word is truncated where the mixdown truncates the
sum once, a −7..0 LSB bias; the main pair's limiter and the two input
words are the only things a stem does not carry), and a track that is
silent gives zeros. An
older child (`--port-bin`) without `tracks` gets `all` (main, cue and the
ESAI words, 8 words) and `/audio/status` says so in `output.note`. The
ring, the takes and `/audio/pcm` get main L/R de-interleaved from the
24-word frames, byte for byte what the `main` capture gave (a take made
with a device on fits the clean fixture at the same −33.0 dB); the switch
itself restarts the child's ring, so up to one pacer slice (~10 ms) of an
open take is lost at the moment a device is chosen or dropped.
`/audio/status` `output` says how it is going: `device`, `channels`
(opened) and `device_channels`, `running`, `latency_ms` (PortAudio's
figure for the device), `buffered_ms` (queued, ahead of the callback),
`underruns` (callbacks the queue could not fill: zeros went out, then the
stream re-primes on 100 ms), `dropped` (frames discarded oldest-first
beyond 250 ms queued while playing: an audible skip), `trimmed` (the
same while re-priming after a gap -- the fresh child's boot burst after
a reboot, nothing was due), `pa_underflows` (PortAudio's own flag),
`pushed` / `played`, `words` (what the child streams: 24 with the stems,
8, or 2), `map` (each device pair by name) and `layout` (the pair names
in device order), `note`; beside it `capture` (`tracks` | `all` | `main`)
and `words`. A device that goes away
(unplugged, or taken by another app) stops the stream with a `note`
after 3 s without a callback, nothing else; the server keeps the stream
across its child's reboots (respawn, re-insert, sound switch: the fresh
child picks the 24-word capture itself) and only forgets it when it
exits.

**Drift.** Two clocks meet here: the child's pacer, which delivers
44,100 frames per wall second, and the device's own sample clock. Over a
long session their difference accumulates and shows up, now and then, as
one underrun (a re-prime: ~100 ms of silence) or a drop of the oldest
frames -- the counters say which and how often; a DAW recording of an
hour may carry a handful of such seams. Nothing resamples. The latency
from the PLAY key to the device is the prime (100 ms) plus the drain's
cadence (20 ms) plus the device's own (11.6 ms on BlackHole).

Measured 13 Sep 2026 (`out/_agents/output/verify.py`, `verify.log`,
`verify.json`; port 8596, the clean OTLIVE fixture `out/_agents/audio/
tree2`, `--sound on`, the `--dsp-rt` child): ready in 7.1 s;
`/audio/devices` listed BlackHole 2ch, External Headphones (default),
MacBook Pro Speakers, Microsoft Teams Audio (1 ch), two Multi-Output
Devices; `device=BlackHole 2ch` opened 2 channels at 11.6 ms latency and
`/audio/status` read `capture: all`, `words: 8` 1.5 s later; a 30 s PLAY
held `/status rt` 0.993-1.004 with the stream at **underruns 0, dropped
0, pa_underflows 0, buffered 48-80 ms**, the drain's worst pump 4.1 ms,
`/audio/pcm` answering 44,100 frames mid-play (the page's headphones
monitor is unchanged); the take (30.164 s) fits `third-0.wav` at
**−33.0 dB** (`fit.py`: onset 81, gain 0.7032); `peak_cue` mid-play
[12765, 12714] against main [18278, 18205], i.e. the fixture's cue words
carry the second pair 3.1 dB below main; `device=off` stopped the stream
and the capture was `main` again within a second; an unknown name is a
404 JSON. Not verified: what the device *receives* -- the independent
witness (`rec.py`, an input stream on BlackHole from a second process)
recorded silence, and so does `loop_probe.py` with no emulator at all
(a sine from one process, a recording from another), which is macOS's
Microphone permission for the process's host app (every audio input,
virtual devices included, is silent without it), not the stream; grant
it and run `verify.py` again for the onset/RMS comparison. Channels 3-4
were not exercised: this Mac has BlackHole 2ch, not 16ch.

## No unit to hand? Real projects from public test fixtures

Two open-source Octatrack tools ship projects saved on real units (OS
1.40B, VERSION=19) as test data — GPL-licensed, fine to use locally:

| source | what | where it lands |
|---|---|---|
| [ot-tools](https://gitlab.com/ot-tools/ot-tools) `ot-tools-operations/test-data/copy-redo-live` | a full project (16 banks, `.work` + `.strd`, arrangements, markers) **with its AUDIO pool** (4 samples in slots) | `out/_projects/otlive/OTLIVE/{PROJECT,AUDIO}` |
| ot-tools `ot-tools-io/test-data/blank-project` | a blank project, all files | `out/_projects/blank/BLANK` |
| [octatrack-manager](https://github.com/davidferlay/octatrack-manager) `src-tauri/tests/fixtures/real_device` | one bank + project/markers/arr01 | `out/_projects/real_device` |

```sh
.venv/bin/python3 tools/panel/panel_server.py --project out/_projects/otlive/OTLIVE/PROJECT --set OTLIVE --name PROJECT
```

The full project loads under either backend (the port's own boot does the
mount and LOAD PROJECT, `/project` shows its report: `posted`, `saved_bank`
0, `final_bank` 0; under route A the M6b gate passes: mount, LOAD PROJECT,
bank A parsed) and the panel stages its AUDIO pool automatically.

## Scenes and the crossfader

Measured 13 Sep 2026 on the port with the OTLIVE fixture and the DSP cores
(`out/_agents/panel-ctl/`: `lab_params.py` maps the encoders and finds the
fader message, `lab_scenes.py` is the end-to-end run, `check_reset.py` the
double-click, logs / JSON / `S_*` `R_*` screens beside them; the evidence
is in `KEYMAP.md` and `param_map.json`).

**The crossfader is the panel board's pot, reported as `0x40 <adc>` on the
panel UART** (the same wire as the keys and encoders: docs/firmware/PANEL.md section 9). The
firmware scales the byte by a calibration record in its boot flash
(`0x1ffffe`, none under emulation, so `value >> 1`), posts sys message kind
4, stores the position in `0x460d16c8` (127 = scene A, 0 = scene B),
rebuilds the morph weights and redraws the fader icon in the LCD's bottom
right. `/xfader?pos=` sends exactly that byte; the page's fader is a drag
(the handle, or a click in the bed), a wheel (Shift = 8 steps) or, after a
click on it, the Left/Right arrows (otherwise the keyboard's four arrow
keys press the panel's arrows, held while held), with the position (0 = A at the left,
127 = B at the right, the CC 48 value) and the two assigned scenes in its
tooltip (the readout under the bed went 13 Sep 2026). Nothing is remembered across reloads: the page asks the firmware
where the fader is on load and every few seconds while idle.

**The flow, as on the unit** (manual 10.3; every step through the matrix,
Shift HOLDS FUNCTION for as long as it is down, so Shift + click = a FUNC combination; Option-click (or A + click) latches any other key, green, until it is clicked again, Escape or Shift up (Escape lets go of latched keys when any are held; with none held it presses NO, and Enter presses YES); holding Z and clicking holds the key only while Z is down):

1. Option-click **SCENE A**, click **TRIG 2**, click SCENE A again to let go:
   scene 2 is in slot A (the Part byte `blob+0x8ed90` 0 -> 1, the page's
   fader's tooltip says `scenes 2 / 9`). While SCENE A is held the
   trig LEDs show the slots: red = the scene in this slot, green = the
   other slot's (1 and 9 after a load: rows `01 00 02`).
2. The same with **SCENE B** + **TRIG 3**: `blob+0x8ed91` -> 2.
3. **A scene lock**: hold SCENE A (Option-click), turn a page encoder --
   AMP page, knob D (VOL) down 64 detents -- and let go. The box draws
   inverted with the locked value while the key is held (manual 10.3.1),
   the Part's own VOL byte does not move (a lock, not an edit), and the
   scene block gets the value: `blob + pattern*0x18b2 + scene*0x100 +
   0x8f3e2 + track*0x20 + (page*6 + slot)` with page 0 PLAYBACK, 1 LFO,
   2 AMP, 3 FX1, 4 FX2 -- byte 15 for AMP VOL, `0xff` = not locked
   (`docs/firmware/MIDI.md` appendix C). Measured on T1..T4: `..ff 14 ff..` /
   `..ff 00 ff..` at `0x401716d1/f1/711/731`.
4. **Move the fader**: the firmware morphs between the A locks and the B
   locks (or the Part value where a side has none) every DSP frame. With
   the cores on, a take at each position (PLAY 3 s, STOP): fader at A
   (`/xfader?pos=0`) **-7.7 dBFS** RMS, at B (127) **-3.3 dBFS**, mid (64)
   **-5.5 dBFS** -- the four VOL locks (20/0/0/0 in scene 2 against the
   Part's 84/64/64/64) take 4.4 dB off the mix at A and half of it half
   way, exactly the manual's interpolation. The LCD shows the fader icon
   moving (x 104-108, y 59-61); the parameter boxes keep showing the
   Part values (the morph writes the DSP-bound copy, not the page).

**Double-click an encoder = init value** (deliverable of the same day):
the server resolves what the encoder edits on the current page -- the
track (`0x100b14cc`), the page kind (`0x460d1684`), the track's machine
or effect, the firmware's own page descriptor with its init value, min and
count (`param_map.json`, from the knob handler `0x40055008`) -- reads the
Part byte, and sends the difference as detent reports (at most 64 each, 30
ms of firmware between, re-reading until the value is the init or stops
moving), so the LCD and the sound follow because the firmware did it.
Measured (`check_reset.py`): AMP VOL 84 -> 64 (`sent [-20]`, the VOL box
redrawn), PLAYBACK PTCH 70 -> 64 (`[-6, -1]`: its hook steps in fractions,
hence the second round), STRT 33 -> 0, LEVEL 93 -> 108 (init 108: every
track of the BLANK fixture). Refused with `ok: false` and nothing sent: a
SETUP window (second press of a page key), the MIXER, TEMPO or a menu
(the popup record's geometry), MIDI mode (the MIDI-track pages take
another branch of the handler, not mapped), the master track, and a slot
the descriptor marks dead (AMP F = XVOL: nibble 8 in the enable long).
The encoders themselves are endless now: no end stops, every detent goes
out (a wheel burst is capped at +-64 per report), the indicator turns 15
degrees per detent and returns to 12 o'clock on a reset; VOLUME is a pot
and unchanged (the monitor's gain, double-click = 75 %).

## Parameter locks

Measured 13 Sep 2026 on the port with the OTLIVE fixture (`out/_agents/plock/`:
`verify_plock.py` the scripted run, `probe2.py`, `flash_stream.log`; the
evidence is the last section of `KEYMAP.md`).

**As on the unit** (manual 12.5): REC for GRID RECORDING, hold a [TRIG]
key of a placed trig and turn a DATA ENTRY knob -- the box inverts with
the locked value and the trig LED flashes (here: a green blink on the red
LED twice a second, on the LED stream). **Remove a single lock by holding
[TRIG] and pressing that knob.** In the page: Option-click the trig key
(it latches, green), turn the encoder, then **double-click the encoder
while the trig is latched** -- that is the encoder's push, sent as
`/knob/press` (the panel's own report for the push switch: key-matrix row
`0x27`, bit = the encoder, found this day; the parser has no other push
message), and the lock goes: the box is drawn normal, the LED stops
blinking, the trig itself stays. Click the latched trig to let go. A
double-click with no trig held is still the init-value reset.

The firmware's push is a toggle: a push on a parameter with NO lock on
that step sets one at the current value (the box inverts), the next push
removes it -- the page passes that through unchanged. With a SCENE key
held instead, the push removes the scene lock (manual 10.3.1); LEVEL's
push is bit 6. Measured: PTCH lock byte `0xff -> 0x45` on the turn,
`-> 0xff` on the push, the step's trig mask unchanged; the lock bytes are
`track record + 0x59 + slot` on the PLAYBACK page. TRIG LOCK CLEAR (trig
held + PLAY, manual 12.9.10) clears all of a trig's locks and is a plain
chord here (Option-click the trig, click PLAY -- or hold Shift, which holds FUNCTION, and click the trig then PLAY).

## Limits

Everything the emulator cannot see is still invisible here — audio (the
port's `--dsp` cores are not on by default: `--port-arg=--dsp`; use the DSP
harness for listening), cross-core timing, the recorder arm path. And a
project must be one **saved on a real unit** (`--project`) for the
sequencer to promote its tracks; the empty default card boots to SET
DATE/TIME.
