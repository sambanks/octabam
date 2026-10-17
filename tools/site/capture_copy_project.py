#!/usr/bin/env python3
"""Capture COPY PROJECT panel shots into docs/site/img/copy-project/."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import toolpath  # noqa: E402,F401
from stems_panel import MenuPort  # noqa: E402
from panel_server import popup_geometry  # noqa: E402

OUT = ROOT / "out/manual-captures/copy-project"
IMG = ROOT / "docs/site/img/copy-project"
RECORDS = ROOT / "docs/site/screenshots.json"
REMIX = "copy-project"


def shot(p, name, caption):
    IMG.mkdir(parents=True, exist_ok=True)
    path = IMG / f"{name}.png"
    path.write_bytes(p.link.render_png(scale=4, dark=0, light=255))
    records = json.loads(RECORDS.read_text()) if RECORDS.exists() else {}
    records.setdefault("copy-project", {})[name] = {
        "image": f"copy-project/{name}.png",
        "caption": caption,
        "remix": REMIX,
        "source": "emulator panel UART",
        "firmware_sha256": hashlib.sha256((OUT / "image.bin").read_bytes()).hexdigest(),
    }
    RECORDS.write_text(json.dumps(records, indent=2) + "\n")
    print(f"Captured copy-project/{name}: {caption}", flush=True)


def press(p, name, n=1):
    for _ in range(n):
        p.press(name, settle=80)


def menu_project_row(p, downs):
    if popup_geometry(p.rt.uc) != (5, 0, 0xf6, 0x40):
        p.open_menu()
    press(p, "left")
    press(p, "up", 5)
    press(p, "down", 0)  # PROJECT
    press(p, "right")
    press(p, "up", 20)
    press(p, "down", downs)


def main():
    cfg = Path.home() / ".octabam_project"
    project = Path(
        os.environ.get("OT_PROJECT")
        or (cfg.read_text().strip() if cfg.is_file() else "")
        or str(ROOT / "template_project/!DEF_N1")
    ).expanduser()
    if not (project / "project.work").exists():
        sys.exit(f"no project.work at {project}")

    OUT.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, REMIX=REMIX, XBUS="1", SPEC="1", BUILD="91")
    r = subprocess.run(
        [sys.executable, str(ROOT / "tools/build/build_bus.py")],
        env=env, capture_output=True, text=True, cwd=ROOT,
    )
    if r.returncode:
        sys.exit(f"build failed:\n{(r.stdout + r.stderr)[-2000:]}")
    shutil.copy2(ROOT / "out/mainos_bus.bin", OUT / "image.bin")

    fixture = OUT / "project"
    if fixture.exists():
        shutil.rmtree(fixture)
    shutil.copytree(project, fixture)
    with (OUT / "stage.log").open("w") as f:
        subprocess.run(
            [
                str(ROOT / ".venv/bin/python3"),
                "tools/emu/ot_emu/stage_card.py",
                str(fixture), "MANUAL", "SCREENS",
                "--tree", str(OUT / "tree"),
                "--out", str(OUT / "card.img"),
            ],
            cwd=ROOT, stdout=f, stderr=subprocess.STDOUT, check=True,
        )

    with MenuPort(
        (OUT / "image.bin").resolve(),
        (OUT / "card.img").resolve(),
        "MANUAL", "SCREENS", True,
        log_path=OUT / "port.log",
    ) as p:
        p.settle()
        # Selectable PROJECT rows (separators skipped): CHANGE=0 … SAVE TO NEW=4,
        # COPY PROJECT=5, EXPORT TO SET=6.
        menu_project_row(p, 5)
        shot(p, "menu", "PROJECT menu with COPY PROJECT under SAVE TO NEW.")
        press(p, "yes")
        shot(p, "list", "Source project list (LEVEL scrolls).")
        press(p, "yes")
        shot(p, "name", "NAME THE NEW PROJECT (stock PROJECT+date; FUNC+CUE with RND NAME).")
        press(p, "yes")
        shot(p, "confirm", "Confirm COPY source -> destination.")
        press(p, "yes")  # start the copy (engine/UI job type 21)
        # Template project is tiny; give the dir copy + OPEN IT? popup time.
        p.run(20000)
        shot(p, "open", "After copy: PROJECT COPIED / OPEN IT?")


if __name__ == "__main__":
    main()
