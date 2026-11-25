#!/usr/bin/env python3
"""Two images, one staged card, the same scenario under the port: is what a listener and a MIDI device receive the
same? The check for a ColdFire change meant to leave the output alone (docs/contributing/CF_SCAN.md).

    python3 tools/verify/verify_cf_ident.py BASE.bin CAND.bin CARD.img [--frames N | --live-script FILE]
                                            [--set NAME] [--project NAME] [--max-shift N] [--out DIR] [-- ARGS...]
    python3 tools/verify/verify_cf_ident.py --self BASE.bin CARD.img [...]     # the control: BASE against itself
    python3 tools/verify/verify_cf_ident.py --compare DIR_A DIR_B [--max-shift N]

Each image boots the card (a copy each: the run may write it), loads the project and runs the scenario: N frames of
the internal clock from the transport start (default 2000), or a live script. Both DSP cores' outputs
(`--audio-out`) and the MIDI output (`--midi-out`) are kept and compared.

Verdicts:
  IDENTICAL                every file byte for byte (exit 0);
  EQUAL UP TO TIME SHIFTS  every WAV channel equal once shifted, and the same MIDI messages (exit 0);
  CONTENT DIFFERS          a stretch of some channel that no shift within --max-shift explains, or different MIDI
                           messages (exit 1);
  FAIL                     a run that did not load its project or wrote no audio (exit 2).

Why shifts: the port runs the DSP in step with the ColdFire's instructions, so code that runs fewer instructions
moves an external event (the transport start) by a few samples, and an event landing between two slots of the frame
moves the slots by different amounts. Each channel is therefore walked on its own: where it stops matching, the
shift that makes the next WINDOW samples match is found and kept, and every re-alignment is reported. The stock MIDI
sender repeats a running status byte on a timer, so the same messages can come out with the status byte repeated at
other places: MIDI that differs in its bytes is decoded (midi_messages) and compared message by message.

What it cannot see: state that never reaches the audio or the MIDI within the run; a path the scenario does not
take; the chip's timing (the port is not cycle-exact). `--self` is the control that the port is deterministic for
the scenario: BASE against BASE must be IDENTICAL.
"""
import hashlib
import pathlib
import shutil
import subprocess
import sys
import tempfile
import wave

ROOT = pathlib.Path(__file__).resolve().parents[2]
EMU = ROOT / "out/emu/ot_emu"
WINDOW = 4096
LOADED = "load run ended: LOAD PROJECT handled"


def align(a, b, max_shift=256, window=WINDOW):
    """Walk two sample lists. Returns (shifts, bad): shifts [(index in a, shift)] for every re-alignment, bad [index
    in a] where no shift within max_shift makes the next `window` samples match (at most 20 kept). A tail shorter
    than the window is compared as it lies."""
    i = j = 0
    shifts, bad = [], []
    while i < len(a) and j < len(b):
        if a[i] == b[j]:
            i += 1
            j += 1
            continue
        found = None
        for s in sorted(range(-max_shift, max_shift + 1), key=abs):
            jj = j + s
            if 0 <= jj and i + window <= len(a) and jj + window <= len(b) and b[jj] == a[i] \
                    and a[i:i + window] == b[jj:jj + window]:
                found = s
                break
        if found is None:
            if len(a) - i < window or len(b) - j < window:
                n = min(len(a) - i, len(b) - j)
                if a[i:i + n] != b[j:j + n]:
                    bad.append(i)
                break
            bad.append(i)
            if len(bad) > 20:
                break
            i += 16
            j += 16
            continue
        shifts.append((i, found))
        j += found
    return shifts, bad


def channels(path):
    with wave.open(str(path)) as w:
        n, ch, sw = w.getnframes(), w.getnchannels(), w.getsampwidth()
        raw = w.readframes(n)
    v = [int.from_bytes(raw[k:k + sw], "little", signed=True) for k in range(0, len(raw), sw)]
    return [v[c::ch] for c in range(ch)]


def digest(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()[:16]


_DATA = {0x80: 2, 0x90: 2, 0xA0: 2, 0xB0: 2, 0xC0: 1, 0xD0: 1, 0xE0: 2}     # data bytes a channel message takes
_COMMON = {0xF1: 1, 0xF2: 2, 0xF3: 1, 0xF6: 0}                           # system common messages


def midi_messages(data):
    """The messages a device receives from a raw MIDI byte stream: running status applied, a real-time byte (0xF8 and
    up) kept where it starts and never ending a message, a system exclusive whole. A data byte with no status is kept
    as ("stray", byte)."""
    out, status, need, cur, sysex = [], None, 0, [], None
    for x in data:
        if x >= 0xF8:
            out.append((x,))
        elif x == 0xF0:
            sysex, status = [x], None
        elif sysex is not None:
            sysex.append(x)
            if x == 0xF7:
                out.append(tuple(sysex))
                sysex = None
        elif x & 0x80:
            status, cur = x, []
            need = _COMMON.get(x, _DATA.get(x & 0xF0, 0))
            if need == 0:
                out.append((x,))
                status = None
        elif status is None:
            out.append(("stray", x))
        else:
            cur.append(x)
            if len(cur) == need:
                out.append((status, *cur))
                cur = []
                if status >= 0xF0:              # system common messages cancel running status
                    status = None
    return out


def compare(da, db, max_shift=256, prefix=("base", "cand")):
    """(verdict, lines) for the outputs in da (prefix[0]_*) against db (prefix[1]_*)."""
    lines, verdict = [], "IDENTICAL"
    wavs = sorted(pathlib.Path(da).glob(f"{prefix[0]}_core*.wav"))
    if not wavs:
        return "FAIL", [f"no {prefix[0]}_core*.wav in {da}"]
    for fa in wavs + sorted(pathlib.Path(da).glob(f"{prefix[0]}_midi.bin")):
        fb = pathlib.Path(db) / fa.name.replace(prefix[0], prefix[1], 1)
        if not fb.exists():
            return "FAIL", lines + [f"{fb} is missing"]
        if digest(fa) == digest(fb):
            lines.append(f"  {fa.name}: identical ({digest(fa)})")
            continue
        if fa.suffix == ".bin":
            ma, mb = midi_messages(fa.read_bytes()), midi_messages(fb.read_bytes())
            if ma == mb:                            # a sender repeats running status on a timer: it moves with time
                lines.append(f"  {fa.name}: the same {len(ma)} messages, the status byte repeated at other places")
                if verdict == "IDENTICAL":
                    verdict = "EQUAL UP TO TIME SHIFTS"
            else:
                k = next((k for k, (x, y) in enumerate(zip(ma, mb)) if x != y), min(len(ma), len(mb)))
                lines.append(f"  {fa.name}: MIDI DIFFERS ({digest(fa)} against {digest(fb)}; {len(ma)} and "
                             f"{len(mb)} messages, the first difference at message {k})")
                verdict = "CONTENT DIFFERS"
            continue
        moved = False
        for c, (x, y) in enumerate(zip(channels(fa), channels(fb))):
            shifts, bad = align(x, y, max_shift)
            if bad:
                lines.append(f"  {fa.name} ch{c}: CONTENT DIFFERS at samples {bad[:8]}")
                verdict = "CONTENT DIFFERS"
                moved = True
            elif shifts:
                lines.append(f"  {fa.name} ch{c}: equal up to shifts {shifts[:6]}{' ...' if len(shifts) > 6 else ''}")
                moved = True
        if not moved:                               # every channel sample for sample, the bytes not: the length
            lines.append(f"  {fa.name}: the samples match, the files differ in length")
        if verdict == "IDENTICAL":
            verdict = "EQUAL UP TO TIME SHIFTS"
    return verdict, lines


def run(image, card, out, side, scenario, set_name, project, extra):
    c = out / f"card_{side}.img"
    shutil.copyfile(card, c)
    cmd = [str(EMU), "--image", str(image), "--card", str(c), "--set", set_name, "--project", project, *scenario,
           "--load-ms", "90000", "--dsp", "--main-level", "64", "--audio-out", str(out / side),
           "--midi-out", str(out / f"{side}_midi.bin"), *extra]
    log = out / f"run_{side}.log"
    with open(log, "w") as f:
        rc = subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT).returncode
    text = log.read_text(errors="replace")
    ok = LOADED in text and any(out.glob(f"{side}_core*.wav"))
    return ok, f"  {side}: {image} exit {rc}, {'loaded' if LOADED in text else 'NOT LOADED'}"


def main(argv):
    extra = argv[argv.index("--") + 1:] if "--" in argv else []
    argv = argv[:argv.index("--")] if "--" in argv else argv

    def opt(name, default=None):
        return argv[argv.index(name) + 1] if name in argv else default
    max_shift = int(opt("--max-shift", "256"))
    if "--compare" in argv:
        i = argv.index("--compare")
        verdict, lines = compare(argv[i + 1], argv[i + 2], max_shift)
    else:
        pos = [a for k, a in enumerate(argv) if not a.startswith("--") and (k == 0 or argv[k - 1] not in (
            "--frames", "--live-script", "--set", "--project", "--max-shift", "--out"))]
        if "--self" in argv:
            base, cand, card = pos[0], pos[0], pos[1]
        else:
            base, cand, card = pos[0], pos[1], pos[2]
        if not EMU.exists():
            print(f"  [SKIP] verify_cf_ident: {EMU} is not built (make emu-cf)")
            return 0
        scenario = (["--live-script", opt("--live-script")] if opt("--live-script") else
                    ["--sequencer", "--internal-clock", "--frames", opt("--frames", "2000")])
        out = pathlib.Path(opt("--out") or tempfile.mkdtemp(prefix="cf_ident_"))
        out.mkdir(parents=True, exist_ok=True)
        lines = []
        for side, image in (("base", base), ("cand", cand)):
            ok, line = run(pathlib.Path(image), pathlib.Path(card), out, side, scenario,
                           opt("--set", "OCTABAM"), opt("--project", "PROF"), extra)
            lines.append(line)
            if not ok:
                print("\n".join(lines))
                print(f"FAIL: the {side} run did not load its project or wrote no audio ({out / f'run_{side}.log'})")
                return 2
        verdict, more = compare(out, out, max_shift)
        lines += more
        if "--self" in argv and verdict != "IDENTICAL":
            lines.append("  the control: an image against itself must be IDENTICAL; the port is not deterministic "
                         "for this scenario, so no verdict on a change can be trusted")
            verdict = "FAIL"
        lines.append(f"  outputs in {out}")
    print("\n".join(lines))
    print(verdict)
    return {"IDENTICAL": 0, "EQUAL UP TO TIME SHIFTS": 0, "CONTENT DIFFERS": 1}.get(verdict, 2)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
