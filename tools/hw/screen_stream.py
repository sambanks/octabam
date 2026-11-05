#!/usr/bin/env python3
"""Show the Octatrack's screen in a window (an OBS source) with elektron-screen-tool.

    python3 tools/hw/screen_stream.py                  # set up on first run, then open the window
    python3 tools/hw/screen_stream.py --list           # the MIDI ports the tool sees
    python3 tools/hw/screen_stream.py --update         # fetch and check out the pinned ref again
    python3 tools/hw/screen_stream.py -- --framerate 10 --save-video out.mp4
                                                       # everything after -- goes to screendump

Needs an image with the SCREENSHOT module (modules/screenshot/README.md) and, over USB, the USB module.

First run: clones https://github.com/Fadedlimes/elektron-screen-tool at PINNED_REF into
~/.cache/octabam/elektron-screen-tool (OCTABAM_SCREEN_DIR overrides), makes a venv there and
installs python-rtmidi. Later runs reuse both. The window needs tkinter (macOS: brew install
python-tk). Python 3.10 or newer; the standard library only.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys

REPO = "https://github.com/Fadedlimes/elektron-screen-tool.git"
# 8081d4f is the first commit with --instrument OT.
PINNED_REF = "8081d4f1724b7dd9a0d1705b44fb5d27b2ef149c"
DEFAULT_PORT = "Octatrack"


def die(msg, code=1):
    print(f"screen_stream: {msg}", file=sys.stderr)
    sys.exit(code)


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, **kw)


def tool_dir():
    return os.environ.get("OCTABAM_SCREEN_DIR") or os.path.expanduser("~/.cache/octabam/elektron-screen-tool")


def checkout(d, ref):
    """Clone into d when absent, then check out ref."""
    if not shutil.which("git"):
        die("git is not installed")
    if not os.path.isdir(os.path.join(d, ".git")):
        os.makedirs(os.path.dirname(d), exist_ok=True)
        print(f"cloning {REPO} -> {d}")
        run(["git", "clone", "--quiet", REPO, d])
    head = subprocess.run(["git", "-C", d, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    if not head.startswith(ref):
        print(f"checking out {ref[:12]}")
        run(["git", "-C", d, "fetch", "--quiet", "origin"])
        run(["git", "-C", d, "checkout", "--quiet", ref])


def venv_python(d):
    return os.path.join(d, ".venv", "bin", "python")


def ensure_venv(d):
    py = venv_python(d)
    if not os.path.exists(py):
        print("creating the Python environment")
        run([sys.executable, "-m", "venv", os.path.join(d, ".venv")])
    if subprocess.run([py, "-c", "import rtmidi"], capture_output=True).returncode != 0:
        print("installing python-rtmidi")
        run([py, "-m", "pip", "install", "--quiet", "--upgrade", "pip"])
        run([py, "-m", "pip", "install", "--quiet", "python-rtmidi"])
    return py


def check_tk(py):
    if subprocess.run([py, "-c", "import tkinter"], capture_output=True).returncode != 0:
        hint = "brew install python-tk" if sys.platform == "darwin" else "sudo apt install python3-tk"
        die(f"this Python has no tkinter, which the window needs. Install it ({hint}), delete "
            f"{os.path.join(tool_dir(), '.venv')} and run again.")


def midi_ports(py, d):
    """(inputs, outputs): the port names `screendump --list-midi` prints."""
    out = subprocess.run([py, os.path.join(d, "screendump"), "--list-midi"], capture_output=True, text=True)
    ins, outs, cur = [], [], None
    for line in (out.stdout + out.stderr).splitlines():
        if line.startswith("MIDI inputs"):
            cur = ins
        elif line.startswith("MIDI outputs"):
            cur = outs
        else:
            m = re.match(r"\s*\[\d+\]\s+(.*\S)", line)
            if m and cur is not None:
                cur.append(m.group(1))
    return ins, outs, out.stdout + out.stderr


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--list", action="store_true", help="print the MIDI ports and exit")
    ap.add_argument("--update", action="store_true", help="fetch and check out --ref again")
    ap.add_argument("--ref", default=PINNED_REF, help="elektron-screen-tool commit (default: the pinned one)")
    ap.add_argument("--port", default=DEFAULT_PORT,
                    help=f"substring of the MIDI port name, for both directions (default: {DEFAULT_PORT})")
    ap.add_argument("--no-gui", action="store_true", help="draw in the terminal instead of a window")
    ap.add_argument("rest", nargs=argparse.REMAINDER, help="after --: more screendump options")
    a = ap.parse_args()
    extra = a.rest[1:] if a.rest[:1] == ["--"] else a.rest

    if sys.version_info < (3, 10):
        die(f"Python 3.10 or newer is needed; this is {sys.version.split()[0]}")

    d = tool_dir()
    if a.update or not os.path.isdir(os.path.join(d, ".git")):
        checkout(d, a.ref)
    py = ensure_venv(d)
    if not a.no_gui:
        check_tk(py)

    ins, outs, listing = midi_ports(py, d)
    if a.list:
        print(listing, end="")
        return
    mi = [p for p in ins if a.port.lower() in p.lower()]
    mo = [p for p in outs if a.port.lower() in p.lower()]
    if len(mi) != 1 or len(mo) != 1:
        print(listing, end="", file=sys.stderr)
        die(f"expected one MIDI input and one output containing '{a.port}', found {len(mi)} and {len(mo)}. "
            "Check the USB cable, that BRAIN > SETTINGS > USB > MIDI is ON, and that the image has the SCREENSHOT "
            "and USB modules. With several matches, pass --port with more of the name.", 2)

    cmd = [py, os.path.join(d, "screendump"), "--external", "--instrument", "OT",
           "--midi-in", mi[0], "--midi-out", mo[0]]
    if not a.no_gui:
        cmd.append("--gui")
    cmd += extra
    print("running:", " ".join(cmd))
    try:
        sys.exit(subprocess.run(cmd, cwd=os.getcwd()).returncode)
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
