# Virtual Panel, the macOS app

The browser front panel (`tools/panel/`) in its own window instead of a
browser tab. One Cocoa window with a `WKWebView`; the app starts
`panel_server.py` itself, waits for `/status`, then shows the page. Single
Swift file, compiled with `swiftc` the way `tools/hw/rec.swift` is -- no
Xcode project.

```sh
bash tools/panel/app/build.sh          # -> out/Virtual Panel.app (ad-hoc signed)
open "out/Virtual Panel.app"
```

## What it does

- Spawns `<repo>/.venv/bin/python3 tools/panel/panel_server.py --port 8563
  [--card IMG] [--project DIR --set SET --name NAME]` with `/opt/homebrew/bin`
  first on `PATH`, stdout/stderr appended to `out/panel_app.log` (the app's
  own lines are in the same file, prefixed `app:`). With a card chosen
  (below) the server boots that image as it is; the project arguments are
  only given when the image has to be created.
- Shows "Booting the firmware..." with the app-side phase until `GET /status`
  answers (polled every 500 ms), then loads `http://127.0.0.1:8563/`; the
  page itself shows the firmware phase (booting, loading project, ready).
- If something already answers on the port when the app starts, it attaches
  to that server and leaves it running on quit.
- The spawned server is terminated on quit, on window close and on
  SIGTERM/SIGINT/SIGHUP to the app (SIGTERM to the server, which handles
  it since O19: `card flush` + `quit` to its child -- the child fsyncs the
  card image before its `ok` -- and the card's sidecar written; measured: the app gone 0.8 s after its SIGTERM with `server pid ...
  stopped (signal 15)`, no server and no `ot_emu` on the card left, the
  image not mounted). Only `kill -9` of the app orphans it
  (`pkill -f panel_server.py`). `kill -USR1 <app pid>` is File > Reload
  and `kill -USR2 <app pid>` File > Show Card Audio Folder, for scripts
  (the menus themselves need the Accessibility grant to drive).
- A sheet that is up when the app is asked to quit (the "N files added"
  alert, an open panel) is ended first, as Later / Cancel: AppKit refuses
  `terminate:` while a sheet is attached to the window. Quit Virtual Panel (cmd-Q) and the
  three signals go through the app's own `quit()`, which ends the sheet and
  then calls `terminate:`; measured after the change, the app was gone
  291-356 ms after the signal in every run, the server stopped, and the
  direct-exit fallback behind `terminate:` was never needed. The Dock's
  Quit and an AppleScript `quit` call `terminate:` directly and stay
  refused while a sheet is up, as in any Cocoa app.
- When the spawned server dies the placeholder says how, with the log tail:
  `status N` for an exit code, `signal N (SIGxxx)` when a signal ended it
  (a bind failure on a busy port ends in the interpreter's SIGBUS, measured, which used to read "status 10").
- `VIRTUAL_PANEL_PORT=8571` in the environment picks another port
  (`open --env VIRTUAL_PANEL_PORT=8571 "out/Virtual Panel.app"`, or run
  `out/Virtual Panel.app/Contents/MacOS/VirtualPanel` from a shell).
- The repo root is baked into `Contents/Resources/repo_root` by `build.sh`;
  if that path no longer has a `pyproject.toml` the app walks up from the
  bundle's location instead.
- First launch from Finder or `open`, with the repo under `~/Downloads` (or
  another folder macOS guards): the system asks whether Virtual Panel may
  access that folder, and the app waits on the dialog before its window
  appears (measured: the main thread blocks in `open()` of
  `out/panel_app.log` until the dialog is answered). Allow it once. An
  instance started from a terminal inherits the terminal's grant and never
  sees the dialog.

## Menus

- **The card.** The unit's CF card is a file that
  persists -- what you SAVE on the unit (PROJECT menu: FUNC + MIXER,
  RIGHT, DOWN to SAVE, YES, YES) and the samples you put on the card are
  there at the next launch; `tools/panel/README.md` "Your card" has the
  whole story and the measurements.
  - **File > New Card from Project...** (cmd-N): a project folder saved on
    a unit (SET/PROJECT, as Open Project) -> the server creates
    `out/cards/<Set>-<Project>.img` from it and its sibling AUDIO (once)
    and boots it; the choice is remembered (UserDefaults `cardPath`) and
    booted at every later launch. An image of that name that exists is
    offered as it is (Open Existing -- what the unit saved stays) or
    replaced (Replace deletes the `.img` and its `.json`).
  - **File > Open Card...** (cmd-shift-O): an existing `.img` (`out/cards/`
    first); its sidecar names the project, and a card without one is
    booted into the first set/project the server finds on it.
  - **File > Show Card in Finder**: reveals the `.img` (copy it to back the
    card up; the `.json` beside it keeps the names).
  - **File > Eject Card** (cmd-E) / **Insert Card** (the same item; the
    title follows `/status card_ejected`, enabled with a persistent card
    at phase `ready`, or while ejected): Eject asks first, then `GET
    /card/eject?open=0` -- the server flushes, stops the child and mounts
    the image on the Mac -- and once `/status` says `card_ejected` the
    volume is opened in Finder (`/Volumes/OCTABAM`): copy samples into
    `<SET>/AUDIO`, projects into `<SET>/`, or whole sets, as with a CF
    card in a reader; the page shows the empty slot. Insert is `GET
    /card/insert`: the server removes what macOS dropped on the volume,
    detaches it and boots the unit again (~15 s). A detach refused (a
    Finder window holding a file) is a sheet; the card stays ejected.
  - With no card ever chosen (or after **Open Project (scratch card)...**,
    which forgets the card), the old behaviour: the remembered project on
    a fresh per-port image, nothing persists.
  - `VIRTUAL_PANEL_CARD=<img>` boots that card for one launch (created from
    the default project if missing; not remembered);
    `VIRTUAL_PANEL_PORT_BIN=<bin>` passes `--port-bin` (a build of `ot_emu`
    that knows `--card-rw` before `out/emu` is rebuilt). Measured (port 8598, `out/_agents/persist/`): the spawn line carried
    `--port-bin ... --card .../OTLIVE-PROJECT.img`, `/status` read
    `card_mode persistent, card_rw true` and the item logged `Eject Card,
    enabled` at `ready` (+8 s); `/card/eject` from a script had the item
    read `Insert Card, enabled` with `EJECTED at /Volumes/OCTABAM` in the
    log, `/card/insert` brought it back to `Eject Card`; SIGTERM to the
    app stopped the server and the child.
- **File > Open Project (scratch card)...** (cmd-O): a project folder saved on a unit;
  `--set` is its parent folder's name, `--name` the folder's own. The server
  is restarted with it and the choice is remembered (UserDefaults
  `projectDir` under `io.octabam.virtual-panel`) for the next launch. When
  nothing is remembered and `out/_projects/otlive/OTLIVE/PROJECT` exists
  (the ot-tools fixture, `tools/panel/README.md`), that is loaded; otherwise
  the empty card, which boots to SET DATE/TIME. An attached server cannot be
  restarted by the app: it shows the command line to run instead.
- **File > Reload** (cmd-R): reloads the page when the server is the app's
  own (or keeps polling while it boots). When the app is attached to someone
  else's server it probes again: still answering, its page is reloaded;
  gone, a fresh server is spawned on the first Reload. A page load that
  fails on its own (server killed under a shown page) only goes back to the
  placeholder and polls -- it does not spawn, so a server the user is
  restarting by hand (what the Open Project alert asks for) is not raced for
  the port.
- **File > Add Samples to Card...** (cmd-shift-A): an open panel (several
  files; anything whose type conforms to `public.audio` -- wav, aif/aiff,
  mp3, m4a, flac, ogg, and caf, aac, aifc, mp2 ... since the server's pool
  converts whatever afconvert reads; the seven named extensions are also
  taken when the type database does not know one). The same thing happens
  for files dropped on the window, on the Dock icon, or opened with the
  app from Finder (`CFBundleDocumentTypes`: `public.audio` and folders,
  rank Alternate -- listed under Open With, never the default); a folder
  gives its audio files, one level deep. A batch first waits for `/status`
  phase `ready` (logged as the phase changes: `add (Dock / Finder):
  waiting for phase ready (now: booting the port ...)`): a Dock drop can
  launch the app before its server exists, and during the boot the server
  takes adds but refuses the re-insert ("the unit is still booting"), so a
  batch added then used to end in "The card could not be re-inserted";
  a batch queued behind a re-insert waits for that reboot the same way.
  Then each file is `GET /samples/add?path=<abs>` (the server copies it
  into the card's AUDIO pool, converting what is not 16/24-bit 44.1 kHz
  WAV/AIFF with afconvert; the path is percent-encoded down to the RFC
  3986 unreserved set plus `/`, so `&`, `=`, `+` and spaces in a name
  survive). The replies are logged (`add ok: <path> -> <name>
  converted=...`, `add failed: ...`), then an alert: "N files added to the
  card. Re-insert the card now? (the unit reboots, ~40 s)" with Re-insert
  / Later, the details (renamed, converted, failed, skipped non-audio)
  below it. Re-insert is `GET /samples/commit`: the card image is rebuilt
  from the pool and the unit rebooted, the way a CF card put back in a
  unit is; the page shows the phase. One batch at a time: files that
  arrive while one is waiting or running are queued (`queued behind the
  running batch`) and start when its alert, and the re-insert it may have
  started, are done. Every alert after launch is a sheet on the window,
  never a modal `runModal()`: a modal loop entered from a URLSession
  completion (a block on the main queue) left the main queue undrained
  until the click -- other replies, the ready poll and the signal handlers
  all waited on the "could not be re-inserted" alert (measured; as a sheet, a second batch was logged 40 ms after `open -a` and
  SIGUSR1 handled in 39 ms with it up).
- **File > Show Card Audio Folder**: `GET /samples` -> `pool`, opened in
  Finder. That is the staged folder the card is built from, not the
  project's own AUDIO: the server seeds it at start (and from `--audio`),
  so a file put there by hand is on the card after the next re-insert.
- `VIRTUAL_PANEL_ADD=/a.wav:/b.mp3` (paths separated by `:`) in the
  environment runs the add flow at launch, once `/status` says `ready`
  (the same wait every batch does), without the open panel;
  `VIRTUAL_PANEL_ADD_THEN=commit` or `later` answers the alert without
  showing it -- unset, empty or any other value shows the alert (another
  value is logged: `VIRTUAL_PANEL_ADD_THEN=x: neither commit nor later`).
  For scripts and the verification below.
- **Audio > Save Main Out Recording...** (cmd-shift-S): `GET
  /audio/status`, then the latest take (`/audio.wav?take=<n>`, suggested
  name `octatrack-take-NNN.wav`) -- or, with no take yet, the ring
  (`/audio.wav?from=<first>&to=<end>`, the last 180 s of the main output,
  `octatrack-main-out.wav`) when it holds anything -- through a save
  panel (a sheet on the window; the folder is remembered, UserDefaults
  `saveDir`) and a URLSession download task to the chosen file (replaced
  if it exists, mode 0644). A take still recording is saved as it is (the
  server keeps its header valid at every moment). Sheets say why when
  there is nothing: sound off (with the server's note), nothing captured
  yet, or a server without the audio endpoints (HTTP 404). A failed
  download is a sheet with the server's own error (`HTTP 404: no take 9`).
- **Audio > Show Takes Folder**: the folder of the takes `/audio/status`
  lists (`out/_panel_takes_<port>/`), in Finder; with no take yet, that
  folder if it exists, else a sheet.
- **Audio > Sound (DSP audio, slower sequencer)**: a checkbox that follows
  `/status` `sound` (polled every 2 s from launch, and once more when the
  menu opens); enabled only at phase `ready`, since a switch is a reboot
  the server refuses while it boots. Toggling asks first ("the unit
  reboots, ~1 min on / ~40 s off"), then `GET /audio/enable?on=1|0`; the
  checkbox stays disabled through the reboot and follows `/status` at
  `ready`. A refusal (already so, busy) is a sheet with the
  server's `note`.
- **Audio > Output Device**: the unit's outputs on a Mac
  audio device in real time -- BlackHole for a DAW, or the speakers
  (`tools/panel/README.md` "Recording into a DAW" has the server side and
  the numbers). The submenu is built from `GET /audio/devices` whenever
  the Audio menu or the submenu opens: Off, then each device as `<name>
  (<n> ch[, default])`, the checkmark on the running one (the same reply
  carries the server's `output` state); a pick sends `GET /audio/output?
  device=<name>` and is remembered (UserDefaults `outputDevice`; Off
  forgets it). The line under the submenu shows the channel map as the
  server reports it (`BlackHole 16ch: main L/R -> 1-2, cue L/R -> 3-4,
  track 1 L/R -> 5-6, ... track 6 L/R -> 15-16` -- since O23 the eight tracks follow main and cue as stereo stems on 5-20,
  per-track outputs the hardware does not have, then ESAI words 0/1 on
  21-22 and 6/7 on 23-24; a 2-channel device `main L/R -> 1-2`; `Output
  off -- ...` with the full map otherwise), and each device's tooltip
  says what its channel count gets.
  The remembered device is re-sent whenever `/status` returns to `ready`
  -- the first boot, every respawn, re-insert and sound switch, and a
  fresh server after Reload / Open Project, which knows nothing of it;
  the server itself keeps the stream across its child's reboots and
  answers `already on <name>`, logged as `output (ready again after
  <phase>): ... -- already on`. A refusal (an unknown device, no
  `sounddevice` package) is logged and, from the menu, a sheet.
  `VIRTUAL_PANEL_OUTPUT=<name|off>` is this launch's choice, not
  remembered, for scripts.
- **The page's own SAVE links** (`/audio.wav?take=N`, `target=_blank`): a
  `target=_blank` link or `window.open()` reaches the app's `WKUIDelegate`
  (`createWebViewWith`; without one WebKit drops them silently) and is
  loaded in the one web view; a reply of MIME `audio/wav` is cancelled at
  the navigation-response stage (`decidePolicyFor navigationResponse`) and
  becomes the same save flow, the name from its `Content-Disposition` --
  the page stays where it was (WebKit reports the cancelled load as
  `WebKitErrorDomain` 102, frame load interrupted by policy change, which
  `didFailProvisionalNavigation` ignores instead of showing the
  placeholder). A `/audio.wav` reply that is not audio (the 404 JSON of a
  missing take) is cancelled too and shown as a sheet, so the JSON never
  replaces the panel. The server serves the file twice this way: WebKit's
  own load, cancelled at the headers, then the download.
- The web view is configured with `mediaTypesRequiringUserActionForPlayback
  = []` so the page's WebAudio monitor keeps running after its own
  headphones click (inline playback is macOS's only mode --
  `allowsInlineMediaPlayback` is an iOS setting). With the UI delegate in
  place, JS `alert()`/`confirm()` are sheets now (they showed nothing and
  answered false before); quit ends them like any sheet.
- Hooks, in the style of `VIRTUAL_PANEL_ADD`: `VIRTUAL_PANEL_SAVE=<path>`
  saves the latest take to `<path>` (no panel) once `/status` is `ready`
  and `/audio/status` lists a take that is not recording -- polled every
  second, the state logged as it changes (`waiting for a take (now: no
  take yet)`, `(now: take 1, recording)`, `(now: take 1)`);
  `VIRTUAL_PANEL_SAVE_WAIT=<s>` (default 600) bounds the wait, at the
  deadline the latest take as it is, else the ring, else nothing.
  `VIRTUAL_PANEL_SOUND=0|1` switches the sound once ready, no sheet (a
  refusal is logged: `refused: sound is already on`).
  `VIRTUAL_PANEL_SAVE_DIR=<dir>` answers every save panel unattended (the
  file lands there under the suggested name). `VIRTUAL_PANEL_NAV=open:<p>`
  / `go:<p>` makes the page `window.open(<p>)` / set `location.href`
  once it has loaded and logs 4 s later whether the page was kept (a
  marker set before, `location.href`, the title): `VIRTUAL_PANEL_NAV: page
  kept (...)` or `PAGE NAVIGATED AWAY`.
- Window: Minimize, Zoom. Edit: the clipboard for the key-map drawer.

Measured (port 8588, the OTLIVE fixture, launched from a shell
with `VIRTUAL_PANEL_ADD` naming a `.caf`, a 16-bit 48 kHz WAV and a `.txt`,
`VIRTUAL_PANEL_ADD_THEN=commit`, plus a second batch sent with `open -a`
at +3 s, during the boot): the first batch logged `waiting for phase ready
(now: no answer)` at +0 s and `(now: booting the port ...)` at +1 s, the
second `queued behind the running batch` at +3 s; `/status` ready at
+42 s, when the caf came back `converted: true` as `plain.wav`, the 48 kHz
WAV converted under its own name, the `.txt` skipped before any request;
`/samples/commit` went out the same second, `/status` read `phase:
re-inserting the card (reboot, ~40 s)`, `card_busy: true`, and the second
batch logged `waiting for phase ready (now: re-inserting the card ...)`;
`ready` again at +86 s, the second batch's add answered at +85 s and its
sheet up; `/samples` then listed the three (the first two also in
`out/_panel_stage_8588/OTLIVE/AUDIO`, `mono24.wav` under `pending`);
SIGTERM at +88 s with the sheet up: `quit: ending the open sheet`, the
server stopped, the app gone within a second, no `panel_server.py --port
8588` and no `ot_emu` on `_panel_card_8588.img` left (`pgrep -fl ot_emu`:
the child's `--interactive` is not next to the binary name, so grep for
the card file), port free. An earlier run the same day with a 24-bit
48 kHz AIFF, an AAC `.m4a`, `my kick & snare.wav` (kept as `my kick _
snare.wav`), a folder and a missing path ("not a file" from the server)
measured the same boot (+41 s) and re-insert (39.4 s, the server's `card
re-inserted with 41 files` line; `/status` `restarts` counts watchdog
respawns, not re-inserts).

Audio, measured (a re-identified copy of the app,
`out/_agents/monitor-app/VPMon.app`, bundle id
`io.octabam.virtual-panel.monitor`; scripts, logs and the saved files under
`out/_agents/monitor-app/`, `run1..5.sh` / `.out`). Against the real
server on port 8591, spawned by the app with the OTLIVE fixture (sound on,
the server's default): `/status` `ready` at +63 s (`sound: true`, the
checkbox logged `checked, enabled` the same second); PLAY through
`/tap?row=0x25&bit=0&n=1` opened take 1 (`recording: true`), STOP
(`/tap?row=0x24&bit=7&n=1`) 13 s of wall later closed it at 60,638 frames
= 1.375 s of emulated audio (about 106 emulated ms per wall second while
the sequencer plays with the DSP cores, the ~9x of the port's O14k
numbers); `VIRTUAL_PANEL_SAVE` logged `waiting for a take (now: no take
yet)`, `(now: take 1, recording)`, `(now: take 1)` and saved
`octatrack-take-001.wav`, 242,596 bytes, `cmp`-identical to `curl
/audio.wav?take=1`, whose first non-zero sample is frame 81 (1.8 ms, the
fixture's step-1 trig as O14k measured it). A second instance launched on
the same port attached to that server, and its `VIRTUAL_PANEL_NAV=open:
/audio.wav?take=1` went `window.open` -> `createWebViewWith` -> the
navigation-response intercept (`intercepted an audio/wav navigation`,
then `navigation interrupted by the response policy ...; the page stays`)
-> the save, again byte-identical, with `page kept (<marker> |
http://127.0.0.1:8591/ | Virtual Panel)` 4 s later; its
`VIRTUAL_PANEL_SOUND=0` sent `/audio/enable?on=0` (`switching sound off
(reboot, ~40 s)`), the checkbox went `checked, disabled` for the reboot
and `unchecked, enabled` when `/status` read `ready` / `sound: false`
40.6 s later (the server's own line). SIGTERM to the attached instance:
gone in 26 ms, the server still answering; SIGTERM to the owner: gone in
95 ms, `server pid ... stopped (signal 15)`, no `panel_server.py --port
8591`, no `ot_emu` on `_panel_card_8591.img`, port free. Against the
contract stub (`stub_audio_server.py`, ports 8590-8592): the `go:`
variant (`location.href`) is intercepted the same way; a missing take
(`/audio.wav?take=9`, the 404 JSON) is cancelled before it can replace the
page and shown as a sheet, the page kept; `VIRTUAL_PANEL_SOUND=1` with
sound already on is refused and logged, nothing switched; a take that
appears 5 s after `ready` and reads `recording` for 4 s more is saved
only once it closes; the ring (`/audio.wav` without `take=`) is saved
under the `Content-Disposition` name `octatrack-main-out.wav`; SIGTERM
with the save panel's sheet up quit in 333 ms (`quit: ending the open
sheet`), with the "not available" sheet up in 296 ms. Build: 0 compiler
warnings, `codesign -vv` valid on the copy and on `out/Virtual Panel.app`.

Output device, measured (`out/_agents/output/verify_app.py`,
`verify_app.log`): the built app launched from a shell with
`VIRTUAL_PANEL_PORT=8598 VIRTUAL_PANEL_OUTPUT="BlackHole 2ch"
VIRTUAL_PANEL_CARD=out/_agents/output/cards/HOOK.img` (a new card from the
OTLIVE fixture) logged the hook at once, `/status` read `ready` 7.1 s
after the spawn and the same second the log had `output (ready): GET
/audio/output?device=BlackHole 2ch` and `output (ready): BlackHole 2ch
running, 2 channels, latency 11.6 ms, main L/R -> 1-2`, `/audio/status`
`capture: all`; a re-insert (`/samples/add` of a generated WAV, then
`/samples/commit`: `re-inserting the card (reboot, ~40 s)`, `ready`
again 7.6 s later) logged `output (ready again after re-inserting the
card (reboot, ~40 s)): ... -- already on BlackHole 2ch` and the stream
was still running on the fresh child's 8-word capture, with 1 underrun
(the reboot's gap), 18,369 frames of the boot burst trimmed while it
re-primed and 1,174 dropped as the fresh child's pacer caught up (all of
it the idle unit's silence); SIGTERM to
the app took its server with it (no `panel_server.py --port 8598` left).
Build: 0 compiler warnings, `codesign -vv` valid.

Window: 1440x860 to start, centered on the first launch, 960x560 minimum,
size and position remembered (`NSWindow Frame VirtualPanelWindow` in the
app's defaults; `defaults delete io.octabam.virtual-panel "NSWindow Frame
VirtualPanelWindow"` forgets it).

## Files

| file | is |
|---|---|
| `VirtualPanel.swift` | the whole app |
| `Info.plist` | bundle id `io.octabam.virtual-panel`, min macOS 13, the audio document types for Dock drops |
| `build.sh` | swiftc -O (explicit arm64 target + SDK: a Rosetta shell otherwise loses both), bundle assembly, `repo_root`, icon, `codesign -s -` |
| `make_icon.py` | draws the icon PNG (stdlib); `build.sh` runs sips + iconutil on it |

## Running a remix (your own firmware) in the app

`File > Open Firmware Image...` (cmd-I) boots a main-OS image instead of the
stock one and remembers it; `File > Use Stock Firmware` goes back. Build a
remix first, e.g. `REMIX=octatrick make bus` (DIRECT JUMP and SCALE
QUANTIZER together; docs/guide/COMPOSING.md on composing remixes) -> the
image lands at `out/mainos_bus.bin` (Elektron bytes: keep it under out/,
never in git). The unit reboots on the chosen image on the same card, so
your projects and samples stay. Scripts: `VIRTUAL_PANEL_IMAGE=<path>`.
