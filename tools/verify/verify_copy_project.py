#!/usr/bin/env python3
"""COPY PROJECT under the ColdFire port: card-to-card folder duplicate.

    python3 tools/verify/verify_copy_project.py [REMIX]
    make check REMIX=copy-project   # runs this as the module gate

1. Success: stage SRC, PROJECT > CHANGE > FUNC+BANK > COPY, stock default
   name under a pinned RTC, confirm, OPEN IT? NO — destination matches
   source.
2. Failure / cleanup: SRC with more than 256 entries in one directory
   forces COPY FAILED; destination is removed; source untouched; a retry
   with the same name does not hit NAME ALREADY IN USE! (dest still gone
   after the name editor YES).

SKIPs without the port or a project. Copy while the sequencer plays is
hardware only.
"""
from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import toolpath  # noqa: E402,F401
from remix import registry  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
EMU = ROOT / "out/emu/ot_emu"
PY = ROOT / ".venv/bin/python3"
OUT = ROOT / "out/copy_project_verify"
# 2026-10-14 12:00:00 UTC — same epoch as verify_rnd_name
RTC_EPOCH = 1791979200
DST = "PROJECT 261014"
# copyproj.c EMAX — one more than kept entries refuses the scan
EMAX = 256


def press(p, name, n=1, settle=80):
    for _ in range(n):
        p.press(name, settle=settle)


def menu_copy_project(p):
    """PROJECT > CHANGE > highlight SRC > FUNC+BANK > COPY."""
    from panel_server import popup_geometry  # noqa: PLC0415

    if popup_geometry(p.rt.uc) != (5, 0, 0xf6, 0x40):
        p.open_menu()
    press(p, "left")
    press(p, "up", 5)
    press(p, "down", 0)  # PROJECT
    press(p, "right")
    press(p, "up", 20)
    press(p, "down", 0)  # CHANGE
    press(p, "yes", settle=400)  # CHOOSE PROJECT
    press(p, "down", 1)  # SRC under <CREATE EMPTY PROJECT>
    p.chord("func", "bank", settle=400)
    press(p, "down", 2)  # RENAME, DELETE, COPY
    # YES on COPY is the caller's first press


def build_image(remix: str) -> pathlib.Path:
    OUT.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, REMIX=remix, XBUS="1", SPEC="1")
    env.setdefault("BUILD", "0")
    r = subprocess.run([sys.executable, str(ROOT / "tools/build/build_bus.py")],
                       env=env, capture_output=True, text=True, cwd=ROOT)
    if r.returncode:
        sys.exit(f"verify_copy_project: build failed:\n{(r.stdout + r.stderr)[-1500:]}")
    image = OUT / "mainos.bin"
    image.write_bytes((ROOT / "out/mainos_bus.bin").read_bytes())
    return image


def stage(fixture: pathlib.Path, card: pathlib.Path, tree: pathlib.Path) -> None:
    if tree.exists():
        shutil.rmtree(tree)
    if card.exists():
        card.unlink()
    r = subprocess.run(
        [str(PY), str(ROOT / "tools/emu/ot_emu/stage_card.py"),
         str(fixture), "OCTABAM", "SRC", "--tree", str(tree), "--out", str(card)],
        cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"verify_copy_project: stage_card failed:\n{r.stdout[-800:]}{r.stderr[-800:]}")


def card_files(card: pathlib.Path) -> dict:
    import emu_card  # noqa: E402

    return emu_card.extract_image(card.read_bytes())


def project_keys(files: dict, name: str) -> list[str]:
    needle = f"/{name}/"
    return [k for k in files if needle in k.replace("\\", "/")]


def assert_success(files: dict, src_work: bytes, log: pathlib.Path) -> None:
    dst_key = next((k for k in files if k.endswith(f"/{DST}/project.work")), None)
    if not dst_key:
        sample = sorted(k for k in files if "project.work" in k)[:12]
        sys.exit(f"verify_copy_project: no {DST}/project.work on card; "
                 f"project.work paths={sample} -- {log}")
    if files[dst_key] != src_work:
        sys.exit(f"verify_copy_project: {dst_key} differs from source "
                 f"({len(files[dst_key])} vs {len(src_work)} bytes) -- {log}")
    src_key = next((k for k in files if k.endswith("/SRC/project.work")), None)
    if not src_key:
        sys.exit(f"verify_copy_project: SRC/project.work missing after copy -- {log}")
    src_prefix = src_key[: -len("project.work")]
    dst_prefix = dst_key[: -len("project.work")]
    missing = []
    for k in files:
        if not k.startswith(src_prefix):
            continue
        peer = dst_prefix + k[len(src_prefix):]
        if peer not in files:
            missing.append(peer)
    if missing:
        sys.exit(f"verify_copy_project: destination missing {missing[:8]} -- {log}")
    print(f"  [PASS] verify_copy_project: {DST!r} matches SRC "
          f"({len(src_work)}-byte project.work, "
          f"{sum(1 for k in files if k.startswith(src_prefix))} files)")


def wait_job(p, slice_ms=5000, limit_ms=180000):
    """Run until the screen changes from the confirm box (the engine job ended: OPEN IT?, or COPY FAILED), at most
    limit_ms. A fixed 20 s ended before the copy of a generated project (tools/hw/ot_fresh.py, 29 MB, 90 files)
    did: it finished between 20 and 40 s of the port's time, 15 Nov 2026, the first run CI gave this gate a
    project (sambanks/octabam#1051)."""
    before = p.screen()
    for _ in range(limit_ms // slice_ms):
        p.run(slice_ms)
        if p.screen() != before:
            p.run(1000)                      # the new prompt drawn and its keys live
            return
    raise SystemExit(f"verify_copy_project: the engine job's dialog did not change in {limit_ms // 1000} s")


def run_success(image: pathlib.Path, pdir: pathlib.Path) -> None:
    fixture = OUT / "src"
    if fixture.exists():
        shutil.rmtree(fixture)
    shutil.copytree(pdir, fixture)
    src_work = (fixture / "project.work").read_bytes()
    card, tree = OUT / "card.img", OUT / "tree"
    stage(fixture, card, tree)

    sys.path.insert(0, str(ROOT / "tools/verify"))
    from stems_panel import MenuPort  # noqa: E402

    log = OUT / "port.log"
    with MenuPort(image.resolve(), card.resolve(), "OCTABAM", "SRC", True,
                  log_path=log, extra=("--rtc", str(RTC_EPOCH))) as p:
        p.settle()
        menu_copy_project(p)
        press(p, "yes", settle=600)          # COPY -> name editor
        press(p, "yes", settle=400)          # accept PROJECT YYMMDD
        press(p, "yes", settle=400)          # confirm COPY SRC -> DST?
        wait_job(p)                          # engine job 21
        press(p, "no", settle=400)           # OPEN IT? -> leave live project
        p.card_flush()

    assert_success(card_files(card), src_work, log)


def run_fail_cleanup(image: pathlib.Path, pdir: pathlib.Path) -> None:
    """SRC with EMAX+1 files in one directory -> COPY FAILED + rm_tree."""
    fixture = OUT / "src_fat"
    if fixture.exists():
        shutil.rmtree(fixture)
    shutil.copytree(pdir, fixture)
    src_work = (fixture / "project.work").read_bytes()
    for i in range(EMAX + 1):
        (fixture / f"pad{i:04d}.bin").write_bytes(b"x")

    card, tree = OUT / "card_fat.img", OUT / "tree_fat"
    stage(fixture, card, tree)

    sys.path.insert(0, str(ROOT / "tools/verify"))
    from stems_panel import MenuPort  # noqa: E402

    log = OUT / "port_fat.log"
    with MenuPort(image.resolve(), card.resolve(), "OCTABAM", "SRC", True,
                  log_path=log, extra=("--rtc", str(RTC_EPOCH))) as p:
        p.settle()
        menu_copy_project(p)
        press(p, "yes", settle=600)          # COPY -> name editor
        press(p, "yes", settle=400)          # accept PROJECT YYMMDD
        press(p, "yes", settle=400)          # confirm
        wait_job(p)                          # COPY FAILED + rm_tree
        p.card_flush()

    files = card_files(card)
    if project_keys(files, DST):
        sys.exit(f"verify_copy_project: {DST!r} still on card after COPY FAILED "
                 f"-- cleanup missed -- {log}")
    src_key = next((k for k in files if k.endswith("/SRC/project.work")), None)
    if not src_key or files[src_key] != src_work:
        sys.exit(f"verify_copy_project: SRC damaged after COPY FAILED -- {log}")
    pad = sum(1 for k in files if "/SRC/pad" in k.replace("\\", "/"))
    if pad < EMAX + 1:
        sys.exit(f"verify_copy_project: SRC lost pad files "
                 f"({pad} < {EMAX + 1}) -- {log}")
    print(f"  [PASS] verify_copy_project: COPY FAILED cleaned {DST!r}; "
          f"SRC untouched ({pad} pad files)")

    # Fresh port: re-enter after COPY FAILED left UI state that mangled a
    # second FUNC+BANK pass in the same session (dest name grew a '%').
    log2 = OUT / "port_fat_retry.log"
    with MenuPort(image.resolve(), card.resolve(), "OCTABAM", "SRC", True,
                  log_path=log2, extra=("--rtc", str(RTC_EPOCH))) as p:
        p.settle()
        menu_copy_project(p)
        press(p, "yes", settle=600)          # COPY -> name editor
        press(p, "yes", settle=400)          # accept PROJECT YYMMDD again
        p.card_flush()
        files = card_files(card)
        if project_keys(files, DST):
            sys.exit(f"verify_copy_project: retry hit NAME ALREADY IN USE! "
                     f"({DST!r} present after name YES) -- {log2}")
        print(f"  [PASS] verify_copy_project: retry name {DST!r} not in use "
              f"(dest still absent after name YES)")

        press(p, "yes", settle=400)          # confirm again -> FAIL + cleanup
        wait_job(p)
        p.card_flush()

    files = card_files(card)
    if project_keys(files, DST):
        sys.exit(f"verify_copy_project: {DST!r} left after second COPY FAILED -- {log2}")
    src_key = next((k for k in files if k.endswith("/SRC/project.work")), None)
    if not src_key or files[src_key] != src_work:
        sys.exit(f"verify_copy_project: SRC damaged after retry -- {log2}")
    print("  [PASS] verify_copy_project: second COPY FAILED still cleans dest; "
          "SRC intact")


def main() -> int:
    remix = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("REMIX")
    if not remix:
        sys.exit("verify_copy_project: remix name required")
    if "COPY PROJECT" not in registry.remix(remix).modules:
        print(f"  [ -- ] verify_copy_project: {remix} carries no COPY PROJECT")
        return 0
    if not EMU.is_file():
        print("  [SKIP] verify_copy_project: no port binary (make emu-cf)")
        return 0
    pdir = pathlib.Path(os.environ.get(
        "OT_PROJECT", str(ROOT / "template_project/!DEF_N1"))).expanduser()
    if not (pdir / "project.work").is_file():
        print(f"  [SKIP] verify_copy_project: no project at {pdir}")
        return 0

    image = build_image(remix)
    run_success(image, pdir)
    run_fail_cleanup(image, pdir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
