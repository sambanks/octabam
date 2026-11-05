"""Shared helpers for the port gates of MIDI-track pages (CHORDS FACTORY's,
PAGES' clients): the image's empty project, a timed panel script, a key tap
and a sequencer run's MIDI notes.

    import page_port as pp
"""
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/verify"))
import midi_fixture  # noqa: E402

FRAMES = 30000                            # two bars of midi_fixture's pattern (measured: 12,500 frames hold one)


def fresh(out, image):
    """The image's own empty project (cached by ot_fresh)."""
    dest = out / "fresh"
    subprocess.run([sys.executable, "tools/hw/ot_fresh.py", "--image", str(image), "--out", str(dest)],
                   cwd=ROOT, stdout=subprocess.DEVNULL, check=True)
    found = sorted(p.parent for p in dest.rglob("project.work"))
    assert found, f"ot_fresh left no project under {dest}"
    return found[0]


def play(out, image, name, poke, project, frames=FRAMES):
    """The sequencer from the card's `project` for `frames`, MIDI OUT captured: its note events."""
    capture = out / f"{name}.midi"
    cmd = [str(ROOT / "out/emu/ot_emu"), "--image", str(image), "--card", str(out / "card.img"),
           "--set", "OCTABAM", "--project", project, "--sequencer", "--internal-clock",
           "--frames", str(frames), "--load-ms", "90000", "--mkii", "--midi-out", str(capture)]
    if poke:
        cmd += ["--poke", poke]
    with (out / f"{name}.log").open("w") as f:
        subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT, check=True)
    events = midi_fixture.notes(capture.read_bytes())
    (out / f"{name}-notes.json").write_text(json.dumps(events, indent=2) + "\n")
    return events


def page_script(path, lines, midi=True):
    """A timed panel script: NO (the date prompt), MIDI, then `lines`, each
    (ms after the start, text)."""
    head = [(1500, "key 0x32 down"), (1540, "key 0x32 up")]
    if midi:
        head += [(1840, "key 0x35 down"), (1880, "key 0x35 up")]
    out = head + list(lines)
    out.append((out[-1][0] + 1500, "quit"))
    path.write_text("".join(f"{t} {x}\n" for t, x in out))


def tap(t, code):
    return [(t, f"key {code:#x} down"), (t + 40, f"key {code:#x} up")]
