#!/usr/bin/env python3
"""RECBUF PERSIST: symbols + a light port proof (no PROJECT menu, no DSP).

  1. Links rbp_st_*.
  2. Save smoke: `--call rbp_st_pstore_pre` right after load on empty
     buffers — must return; card has no REC*.wav (empty skip).
  3. Load: stage a 256-frame REC1.wav, boot, dump slot 128 settings and
     the control record — PATH is REC1.wav and ctl length is 256 (flex
     load ran). Settings +266/+270 stay virgin garbage; flex writes the
     frame count elsewhere (+304) and into 0x46c922c4+44·slot.

A full record→save under DSP still needs the PROJECT menu (callAsMain while
the frame ISR owns the PC aborts). That path is not this gate.

    python3 tools/verify/verify_recbuf.py [REMIX]
"""
from __future__ import annotations

import os
import pathlib
import shutil
import struct
import subprocess
import sys
import wave

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import toolpath  # noqa: E402,F401
from remix import registry  # noqa: E402

EMU = ROOT / "out/emu/ot_emu"
STAGE = ROOT / "tools/emu/ot_emu/stage_card.py"
PY = ROOT / ".venv/bin/python3"
if not PY.is_file():
    PY = pathlib.Path(sys.executable)

NEED = (
    "rbp_st_pstore_pre",
    "rbp_st_loadall_post",
    "rbp_st_loadmask_post",
    "rbp_st_preload_post",
    "rbp_st_answer",
)

SETTINGS1 = 0x100B14F0 + 128 * 0x448
CTL1 = 0x46C922C4 + 128 * 44
WAV_FRAMES = 256


def check(msg, ok):
    print(f"  [{'PASS' if ok else 'FAIL'}] verify_recbuf: {msg}")
    return bool(ok)


def build(remix_name: str) -> pathlib.Path:
    env = dict(os.environ, REMIX=remix_name, XBUS="1", SPEC="1")
    env.setdefault("BUILD", "0")
    r = subprocess.run(
        [sys.executable, str(ROOT / "tools/build/build_bus.py")],
        env=env, capture_output=True, text=True, cwd=ROOT,
    )
    if r.returncode:
        print((r.stdout + r.stderr)[-2000:])
        sys.exit(f"verify_recbuf: build {remix_name} failed")
    return ROOT / "out/mainos_bus.bin"


def symbols(elf: pathlib.Path) -> dict[str, int]:
    nm = subprocess.run(
        ["m68k-elf-nm", str(elf)], capture_output=True, text=True, cwd=ROOT,
    )
    return {
        f[2]: int(f[0], 16)
        for f in (l.split() for l in nm.stdout.splitlines())
        if len(f) == 3
    }


def tiny_wav(path: pathlib.Path, frames: int = WAV_FRAMES):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(44100)
        buf = bytearray()
        for i in range(frames):
            v = (i * 17) & 0x7FFF
            buf += struct.pack("<hh", v, v)
        w.writeframes(bytes(buf))


def find_rec(files: dict, n: int = 1) -> bytes | None:
    needle = f"rec{n}.wav"
    for k, v in files.items():
        if k.lower().endswith("/" + needle) or k.lower().endswith(needle):
            return v
    return None


def boot(cmd: list, log: pathlib.Path, timeout: int = 180) -> int:
    with open(log, "w") as f:
        f.write(" ".join(map(str, cmd)) + "\n")
        f.flush()
        try:
            r = subprocess.run(list(map(str, cmd)), cwd=ROOT, stdout=f,
                               stderr=subprocess.STDOUT, timeout=timeout)
        except subprocess.TimeoutExpired:
            f.write(f"\n[verify_recbuf] TIMEOUT {timeout}s\n")
            return 99
    return r.returncode


def port_tests(image: pathlib.Path, out: pathlib.Path, rbp: int) -> int:
    sys.path.insert(0, str(ROOT / "tools/emu"))
    import emu_card  # noqa: E402

    fails = 0

    # ---- 1. save smoke: empty buffers, --call right after load ----
    project = out / "project"
    project.mkdir()
    (project / "project.work").write_text("[STATES]\nBANK=0\n\n")
    card = out / "card.img"
    staged = subprocess.run(
        [str(PY), str(STAGE), str(project), "OCTABAM", "RECBUF",
         "--tree", str(out / "tree"), "--out", str(card)],
        cwd=ROOT, capture_output=True, text=True,
    )
    if staged.returncode:
        print(staged.stdout[-600:], staged.stderr[-600:])
        return int(not check("stage empty card", False))

    rc = boot(
        [EMU, "--image", image, "--card", card, "--set", "OCTABAM",
         "--project", "RECBUF", "--mount", "--load-ms", "90000", "--mkii",
         "--call", f"{rbp:#x}", "--card-out", out / "smoke.img"],
        out / "smoke.txt",
    )
    log = (out / "smoke.txt").read_text(errors="replace")
    fails += not check(f"save-smoke run exited {rc}", rc == 0)
    fails += not check(
        "save-smoke: call rbp_st_pstore_pre returned",
        f"call       : {rbp:#x}(0 args) returned" in log,
    )
    if rc == 0:
        files = emu_card.extract_image((out / "smoke.img").read_bytes())
        fails += not check(
            "save-smoke: empty buffers wrote no REC*.wav",
            all(find_rec(files, n) is None for n in range(1, 9)),
        )
    else:
        print(log[-2000:])

    # ---- 2. load: staged REC1.wav (STORE load*_post runs on project load) ----
    wav = out / "REC1.wav"
    tiny_wav(wav)
    load_card = out / "load_card.img"
    staged = subprocess.run(
        [str(PY), str(STAGE), str(project), "OCTABAM", "RECBUF",
         "--tree", str(out / "load_tree"), "--out", str(load_card),
         "--audio", f"{wav}:RECBUF/BUFFERS/REC1.wav"],
        cwd=ROOT, capture_output=True, text=True,
    )
    if staged.returncode:
        print(staged.stdout[-600:], staged.stderr[-600:])
        return fails + int(not check("stage card with REC1.wav", False))

    dump = (
        f"{SETTINGS1:#x},280={out / 'slot128.bin'};"
        f"{CTL1:#x},44={out / 'ctl128.bin'}"
    )
    rc = boot(
        [EMU, "--image", image, "--card", load_card, "--set", "OCTABAM",
         "--project", "RECBUF", "--mount", "--load-ms", "90000", "--mkii",
         "--mem-dump", dump],
        out / "load.txt",
    )
    fails += not check(f"load run exited {rc}", rc == 0)
    if rc:
        print((out / "load.txt").read_text(errors="replace")[-2000:])
        return fails

    slot = (out / "slot128.bin").read_bytes() if (out / "slot128.bin").is_file() else b""
    path = slot.split(b"\x00", 1)[0] if slot else b""
    fails += not check(
        f"slot 128 PATH after load is BUFFERS/REC1.wav ({path!r})",
        path == b"BUFFERS/REC1.wav",
    )

    ctl = (out / "ctl128.bin").read_bytes() if (out / "ctl128.bin").is_file() else b""
    if len(ctl) >= 24:
        # Control record: +16 length, +24 name (seen REC1\\0wav after flex).
        length = struct.unpack_from(">I", ctl, 16)[0]
        name = ctl[24:32].split(b"\x00", 1)[0]
        fails += not check(
            f"slot 128 ctl length after load is {length} (want {WAV_FRAMES})",
            length == WAV_FRAMES,
        )
        fails += not check(f"slot 128 ctl name starts REC1 ({name!r})", name.startswith(b"REC1"))
    else:
        fails += not check("slot 128 control dump is 44 B", False)

    return fails


def main() -> int:
    remix_name = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("REMIX", "recbuf-persist")
    remix = registry.remix(remix_name)
    if "RECBUF PERSIST" not in remix.modules:
        print(f"  [ -- ] verify_recbuf: {remix.name} has no RECBUF PERSIST")
        return 0

    image = build(remix.name)
    elf = ROOT / "out/platform/runtime/runtime.elf"
    syms = symbols(elf)
    missing = [s for s in NEED if s not in syms]
    if missing:
        print(f"  [FAIL] verify_recbuf: missing symbols {missing}")
        return 1
    print(
        f"  [PASS] verify_recbuf: {remix.name} links "
        + ", ".join(f"{s}=0x{syms[s]:x}" for s in NEED)
    )

    if not EMU.is_file():
        print("  [SKIP] verify_recbuf: port tests (make emu-cf)")
        return 0

    out = ROOT / "out/recbuf_verify"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    ours = out / "ours.bin"
    ours.write_bytes(image.read_bytes())

    fails = port_tests(ours, out, syms["rbp_st_pstore_pre"])
    if fails:
        print(f"  [FAIL] verify_recbuf: {fails} port check(s) failed")
        return 1
    print("  [PASS] verify_recbuf: port (save-smoke + staged load)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
