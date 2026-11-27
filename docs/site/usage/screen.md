The unit answers Elektron's screenshot SysEx request with the 128 × 64 screen, so
[elektron-screen-tool](https://github.com/Fadedlimes/elektron-screen-tool) (`screendump`) can show it on a
computer, for example as an OBS source.

## Show the screen on a computer

What is needed:

- An image with the SCREEN module and, for USB, the USB module.
- A USB cable (or DIN MIDI).
- A computer with git and either [uv](https://docs.astral.sh/uv/) or Python 3.10 or newer with tkinter.
- OBS Studio, optional.

### Automated

From the octabam checkout:

```bash
python3 tools/hw/screen_stream.py
```

On the first run, the script clones `elektron-screen-tool` at a pinned commit
into `~/.cache/octabam/elektron-screen-tool` (override the location with
`OCTABAM_SCREEN_DIR`), creates a Python virtual environment there, and
installs `python-rtmidi`. If `uv` is installed (`brew install uv`), it
downloads a managed Python 3.13 build (`--python-preference only-managed`)
that includes `tkinter` and matches your machine's architecture, avoiding a
mismatched Homebrew Python such as an Intel build on Apple Silicon. Without
`uv`, it uses the `python3` binary running the script. It then locates the
Octatrack's MIDI input and output ports and opens the display window.
Subsequent runs open the window directly.

| Option | Does |
|---|---|
| `--list` | Prints the MIDI ports the tool sees. |
| `--port NAME` | Part of the MIDI port name, for both directions. Default `Octatrack`. |
| `--no-gui` | Draws in the terminal. |
| `--update` | Checks out the pinned commit again (`--ref` takes another). |
| `-- ARGS` | Passes the rest to `screendump`, for example `-- --framerate 10 --save-video out.mp4`. |

Without uv the window needs tkinter in that `python3`. On macOS: `brew install python-tk`.

On an Apple Silicon Mac the script stops if the environment's Python is x86_64 (running under Rosetta) and says what to delete. `uname -m` in the terminal should print `arm64`.

### By hand

The steps are from a guide by Tapepusher, who first ran the screen capture on a real Octatrack MKII.

With uv (`brew install uv`), whose Python includes tkinter:

```bash
git clone https://github.com/Fadedlimes/elektron-screen-tool.git ~/Downloads/elektron-screen-tool
cd ~/Downloads/elektron-screen-tool
uv venv --python-preference only-managed --python 3.13 .venv
uv pip install --python .venv/bin/python python-rtmidi
.venv/bin/python ./screendump --list-midi
```

Without uv, using Homebrew's Python:

```bash
brew install python python-tk
git clone https://github.com/Fadedlimes/elektron-screen-tool.git ~/Downloads/elektron-screen-tool
cd ~/Downloads/elektron-screen-tool
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip python-rtmidi
.venv/bin/python ./screendump --list-midi
```

On an Apple Silicon Mac, `.venv/bin/python -c "import platform; print(platform.machine())"` should print `arm64`. `x86_64` means
the environment is running under Rosetta: delete `.venv` and recreate it from a terminal where `uname -m` prints `arm64`.

`--list-midi` shows the Octatrack as an input and an output (macOS: `Elektron Octatrack DPS-1`). Then:

```bash
.venv/bin/python ./screendump --external --gui --instrument OT \
  --midi-in "Elektron Octatrack DPS-1" --midi-out "Elektron Octatrack DPS-1"
```

A window opens with the Octatrack's display. Close the window or press Ctrl+C in the terminal to stop.

### In OBS

1. Under **Sources**, click **+** and choose **macOS Screen Capture**.
2. Choose **Create New**, then OK.
3. Set **Capture Type** to **Window** and select the window titled `[Python] screendump - Octatrack`.
4. Click OK. Resize and position it in the scene; hold Option while dragging an edge to crop the window's UI off.

### If no ports are listed

- Over USB, verify that **PROJ > BRAIN > SETTINGS > USB > MIDI** is set to ON
  (when MIDI is OFF, the computer sees only storage and audio).
- Verify that the flashed image includes the SCREEN module, plus the USB
  module if you are connecting over USB.
- Over DIN MIDI, make sure a MIDI interface connects both the Octatrack's MIDI
  OUT and MIDI IN to the computer.

## Operation

Point `screendump` at the Octatrack's MIDI ports using instrument ID `10 00`
(`--probe-id 10 00`; `05 00` is also accepted). Replies are returned over the
same transport that sent the request.

## Wire format

| | |
|---|---|
| Request | `F0 00 20 3C 10 00 00 00 01 00 00 04 F7` (13 bytes) |
| Reply | 1,194 bytes: `F0 00 20 3C 10 00`, 7-bit-encoded body, `F7` |
| Body | msgId, replyTo, cmd `84`, version 1, width 128, height 64, length 1024, 1,024 pixel bytes |

The captured image is the last frame sent to the display panel, so overlays
such as MIXER, the PROJECT menu, SETUP windows, and popups are included along
with the underlying page.

Over USB, each reply fits in a single 1,592-byte EP2 IN transfer. Over DIN
MIDI at 31,250 baud, a frame takes 0.38 s (about 2.6 frames per second); USB
does not have that bottleneck.
