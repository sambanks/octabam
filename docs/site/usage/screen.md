The unit answers Elektron's screenshot SysEx request with the 128 × 64 screen, so
[elektron-screen-tool](https://github.com/Fadedlimes/elektron-screen-tool) (`screendump`) can show it on a
computer, for example as an OBS source.

## Show the screen on a computer

What is needed:

- An image with the SCREENSHOT module and, for USB, the USB module.
- A USB cable (or DIN MIDI).
- A computer with Python 3.10 or newer, git and tkinter.
- OBS Studio, optional.

Tested on macOS. Other platforms have not been tried.

### Automated

From the octabam checkout:

```bash
python3 tools/hw/screen_stream.py
```

On the first run it clones elektron-screen-tool at a pinned commit into `~/.cache/octabam/elektron-screen-tool`
(`OCTABAM_SCREEN_DIR` changes the place), creates a Python environment there and installs `python-rtmidi`. It then
finds the Octatrack's MIDI input and output and opens the window. Later runs go straight to the window.

| Option | Does |
|---|---|
| `--list` | Prints the MIDI ports the tool sees. |
| `--port NAME` | Part of the MIDI port name, for both directions. Default `Octatrack`. |
| `--no-gui` | Draws in the terminal. |
| `--update` | Checks out the pinned commit again (`--ref` takes another). |
| `-- ARGS` | Passes the rest to `screendump`, for example `-- --framerate 10 --save-video out.mp4`. |

The window needs tkinter. On macOS: `brew install python-tk`.

### By hand

The steps are from a guide by Tapepusher, who first ran the screen capture on a real Octatrack MKII.

```bash
brew install python python-tk
git clone https://github.com/Fadedlimes/elektron-screen-tool.git ~/Downloads/elektron-screen-tool
cd ~/Downloads/elektron-screen-tool
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip python-rtmidi
.venv/bin/python ./screendump --list-midi
```

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

- USB: **PROJ > BRAIN > SETTINGS > USB > MIDI** is ON (MIDI OFF leaves the computer storage and audio only).
- The flashed image contains the SCREENSHOT module, and the USB module for the USB cable.
- DIN: a MIDI interface connects the Octatrack's MIDI OUT and IN to the computer.

## Operation

`screendump` is pointed at the Octatrack's ports with the instrument id `10 00` (`--probe-id 10 00`; `05 00` is
answered too). The reply goes back on the transport the request came on.

## Wire format

| | |
|---|---|
| Request | `F0 00 20 3C 10 00 00 00 01 00 00 04 F7` (13 bytes) |
| Reply | 1,194 bytes: `F0 00 20 3C 10 00`, 7-bit-encoded body, `F7` |
| Body | msgId, replyTo, cmd `84`, version 1, width 128, height 64, length 1024, 1,024 pixel bytes |

The picture is the frame the panel was last sent, so MIXER, the PROJECT menu, SETUP windows and popups are in
it, not only the page underneath.

On USB the reply is one 1,592-byte EP2 IN transfer. On DIN it takes 0.38 s at 31,250 baud, so about 2.6
screens per second; USB has no such limit.
