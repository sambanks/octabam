#!/usr/bin/env python3
"""Regenerate SEQ usage diagrams (SVG + optional PNG via Chrome).

Writes docs/site/img/seq/{notes-only,stack-vol,trig-reshape,plck-overwrite,clear-dest}.{svg,png}

PNG step needs Google Chrome headless + Pillow. SVG alone is enough for the site
if PNGs are already checked in; re-run with --png after layout edits.
"""
from __future__ import annotations

import argparse
import html
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/site/img/seq"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

W = 1100
CELL = 34
GAP = 8
N = 8
ROW_H = CELL + 18
GRID_W = N * CELL + (N - 1) * GAP
LAB_W = 62
MARGIN = 36
MID_W = 150
MID_GAP = 32
LEFT_X0 = MARGIN + LAB_W
MID_X = LEFT_X0 + GRID_W + MID_GAP
RIGHT_X0 = MID_X + MID_W + MID_GAP + LAB_W
assert RIGHT_X0 + GRID_W + MARGIN <= W


def esc(s: object) -> str:
    return html.escape(str(s))


def empty8() -> list[str]:
    return [""] * 8


def locks(s: set[int]) -> list[str]:
    return ["lock" if i + 1 in s else "" for i in range(8)]


def tls(s: set[int]) -> list[str]:
    return ["tl" if i + 1 in s else "" for i in range(8)]


def mix(lock_idxs: set[int] = frozenset(), tl_idxs: set[int] = frozenset()) -> list[str]:
    return [
        "lock" if i + 1 in lock_idxs else "tl" if i + 1 in tl_idxs else ""
        for i in range(8)
    ]


def knobs_svg(cells: list[dict], y0: int = 16) -> tuple[str, int]:
    pw, ph = 80, 48
    gx, gy = 6, 6
    panel_w = 3 * pw + 2 * gx + 14
    panel_h = 2 * ph + gy + 14
    px = (W - panel_w) // 2
    out = [f'<rect class="panel" x="{px}" y="{y0}" width="{panel_w}" height="{panel_h}" rx="2"/>']
    for i, c in enumerate(cells):
        col, row = i % 3, i // 3
        x = px + 7 + col * (pw + gx)
        y = y0 + 7 + row * (ph + gy)
        inv = c.get("inv", False)
        fill = "#111" if inv else "#fff"
        tc = "kn-inv" if inv else "kn"
        vc = "kn-val-inv" if inv else "kn-val"
        lc = "kn-inv" if inv else "t-xs"
        letter = "ABCDEF"[i]
        out.append(
            f'<rect x="{x}" y="{y}" width="{pw}" height="{ph}" fill="{fill}" stroke="#111" stroke-width="2"/>'
        )
        if c.get("lab"):
            out.append(f'<text class="{tc}" x="{x+6}" y="{y+15}">{esc(c["lab"])}</text>')
        if c.get("val") not in (None, ""):
            out.append(
                f'<text class="{vc}" x="{x+pw/2}" y="{y+35}" text-anchor="middle">{esc(c["val"])}</text>'
            )
        out.append(
            f'<text class="{lc}" x="{x+pw-8}" y="{y+ph-7}" text-anchor="end">{letter}</text>'
        )
    return "\n".join(out), y0 + panel_h


def grid_svg(x0: int, y0: int, rows: list, title: str) -> tuple[str, int]:
    parts = [f'<text class="t" x="{x0}" y="{y0 - 16}">{esc(title)}</text>']
    for ri, (lab, kinds) in enumerate(rows):
        y = y0 + ri * ROW_H
        parts.append(
            f'<text class="lab" x="{x0 - 12}" y="{y + CELL*0.68}" text-anchor="end">{esc(lab)}</text>'
        )
        for ci, kind in enumerate(kinds):
            x = x0 + ci * (CELL + GAP)
            if kind == "lock":
                parts.append(
                    f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" fill="#111" stroke="#111" stroke-width="2"/>'
                )
            elif kind == "tl":
                parts.append(
                    f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" fill="url(#hatch)" stroke="#111" stroke-width="2"/>'
                )
                parts.append(
                    f'<rect x="{x+7}" y="{y+9}" width="{CELL-14}" height="16" fill="#fff" opacity="0.92"/>'
                )
                parts.append(
                    f'<text class="tl" x="{x+CELL/2}" y="{y+CELL*0.68}" text-anchor="middle">TL</text>'
                )
            else:
                parts.append(
                    f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" fill="#fff" stroke="#111" stroke-width="2"/>'
                )
    y = y0 + len(rows) * ROW_H + 4
    for ci in range(N):
        x = x0 + ci * (CELL + GAP) + CELL / 2
        parts.append(
            f'<text class="t-xs" x="{x}" y="{y + 14}" text-anchor="middle">{ci+1}</text>'
        )
    return "\n".join(parts), y0 + len(rows) * ROW_H + 32


def mid_svg(y_mid: float, lines: list[str]) -> str:
    cx = MID_X + MID_W / 2
    parts = [f'<text class="t" x="{cx}" y="{y_mid - 22}" text-anchor="middle">YES</text>']
    x1, x2 = MID_X + 22, MID_X + MID_W - 22
    parts.append(f'<line class="arr" x1="{x1}" y1="{y_mid}" x2="{x2}" y2="{y_mid}"/>')
    for i, line in enumerate(lines):
        parts.append(
            f'<text class="t-sm" x="{cx}" y="{y_mid + 26 + i*18}" text-anchor="middle">{esc(line)}</text>'
        )
    return "\n".join(parts)


def legend_svg(y: float) -> str:
    items = [
        ("#111", None, "lock on a note"),
        ("url(#hatch)", "TL", "trigless lock (TL)"),
        ("#fff", None, "no lock"),
    ]
    x = MARGIN
    parts = []
    for fill, tl, lab in items:
        parts.append(
            f'<rect x="{x}" y="{y}" width="22" height="22" fill="{fill}" stroke="#111" stroke-width="2"/>'
        )
        if tl:
            parts.append(
                f'<rect x="{x+4}" y="{y+5}" width="14" height="12" fill="#fff" opacity="0.92"/>'
            )
            parts.append(
                f'<text class="tl" x="{x+11}" y="{y+16}" text-anchor="middle">{tl}</text>'
            )
        parts.append(f'<text class="t-sm" x="{x+30}" y="{y+16}">{esc(lab)}</text>')
        x += 250
    return "\n".join(parts)


def wrap(title: str, body: str, h: int) -> str:
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {h}" width="{W}" height="{h}" role="img">
  <title>{esc(title)}</title>
  <rect width="{W}" height="{h}" fill="#fff"/>
  <defs>
    <pattern id="hatch" patternUnits="userSpaceOnUse" width="5" height="5">
      <path d="M0 5 L5 0" stroke="#111" stroke-width="1.6"/>
    </pattern>
    <marker id="a" markerUnits="userSpaceOnUse" viewBox="0 0 10 10" refX="9" refY="5"
            markerWidth="10" markerHeight="10" orient="auto">
      <path d="M0 0 L10 5 L0 10 Z" fill="#111"/>
    </marker>
  </defs>
  <style>
    .t {{ font: 15px ui-monospace, Menlo, Consolas, monospace; fill:#111; font-weight:700; }}
    .t-sm {{ font: 13px ui-monospace, Menlo, Consolas, monospace; fill:#222; }}
    .t-xs {{ font: 12px ui-monospace, Menlo, Consolas, monospace; fill:#333; }}
    .lab {{ font: 13px ui-monospace, Menlo, Consolas, monospace; fill:#111; font-weight:700; }}
    .tl {{ font: 11px ui-monospace, Menlo, Consolas, monospace; fill:#111; font-weight:700; }}
    .kn {{ font: 11px ui-monospace, Menlo, Consolas, monospace; fill:#111; }}
    .kn-inv {{ font: 11px ui-monospace, Menlo, Consolas, monospace; fill:#fff; font-weight:700; }}
    .kn-val {{ font: 13px ui-monospace, Menlo, Consolas, monospace; fill:#111; font-weight:700; }}
    .kn-val-inv {{ font: 13px ui-monospace, Menlo, Consolas, monospace; fill:#fff; font-weight:700; }}
    .arr {{ fill:none; stroke:#111; stroke-width:2.5; marker-end:url(#a); }}
    .panel {{ fill:#fff; stroke:#111; stroke-width:2; }}
  </style>
{body}
</svg>
'''


def make(
    name: str,
    knobs: list[dict],
    headline: str,
    before: list,
    after: list,
    mid_lines: list[str],
    after_note: list[str],
    footer: str,
) -> Path:
    parts: list[str] = []
    kn, y = knobs_svg(knobs, 16)
    parts.append(kn)
    parts.append(
        f'<text class="t" x="{W/2}" y="{y+30}" text-anchor="middle">{esc(headline)}</text>'
    )
    y_grid = y + 80
    g1, yb = grid_svg(LEFT_X0, y_grid, before, "BEFORE")
    g2, ya = grid_svg(RIGHT_X0, y_grid, after, "AFTER")
    parts += [g1, g2]
    y_mid = y_grid + (3 * ROW_H - 18) / 2
    parts.append(mid_svg(y_mid, mid_lines))
    for i, line in enumerate(after_note):
        parts.append(
            f'<text class="t-sm" x="{RIGHT_X0}" y="{ya + 12 + i*18}">{esc(line)}</text>'
        )
    y_leg = max(yb, ya) + 22 + 18 * len(after_note) + 30
    parts.append(
        f'<text class="t-sm" x="{W/2}" y="{y_leg}" text-anchor="middle">{esc(footer)}</text>'
    )
    parts.append(legend_svg(y_leg + 24))
    h = y_leg + 66
    path = OUT / f"{name}.svg"
    path.write_text(wrap(name, "\n".join(parts), int(h)))
    print(f"{name}.svg h={int(h)}")
    return path


SPECS = [
    (
        "notes-only",
        [
            {"lab": "PULS", "val": "4", "inv": True},
            {"lab": "ROT", "val": "0", "inv": False},
            {"lab": "LANE", "val": "TRIG", "inv": True},
            {"lab": "DEST", "val": "PTCH", "inv": False},
            {"lab": "DPTH", "val": "0", "inv": True},
            {"lab": "", "val": "", "inv": False},
        ],
        "TRIG with DEPTH 0: rewrite notes, clear this DEST locks.",
        [("note", empty8()), ("PTCH", empty8()), ("VOL", empty8())],
        [("note", locks({1, 3, 5, 7})), ("PTCH", empty8()), ("VOL", empty8())],
        ["DPTH 0", "notes only"],
        ["notes on 1 3 5 7", "PTCH cleared (DEPTH 0)"],
        "DEPTH 0 means YES clears the current DEST while still baking notes.",
    ),
    (
        "stack-vol",
        [
            {"lab": "PULS", "val": "4", "inv": True},
            {"lab": "ROT", "val": "1", "inv": False},
            {"lab": "LANE", "val": "PLCK", "inv": True},
            {"lab": "DEST", "val": "VOL", "inv": True},
            {"lab": "DPTH", "val": "64", "inv": False},
            {"lab": "", "val": "", "inv": False},
        ],
        "PLCK writes only VOL. Notes and PTCH stay.",
        [
            ("note", locks({1, 3, 5, 7})),
            ("PTCH", locks({1, 3, 5, 7})),
            ("VOL", empty8()),
        ],
        [
            ("note", locks({1, 3, 5, 7})),
            ("PTCH", locks({1, 3, 5, 7})),
            ("VOL", tls({2, 4, 6, 8})),
        ],
        ["LANE=PLCK", "DEST=VOL"],
        ["VOL on 2 4 6 8 as TL (no note there)", "notes + PTCH untouched"],
        "Use PLCK to stack another DEST on its own rhythm.",
    ),
    (
        "trig-reshape",
        [
            {"lab": "PULS", "val": "2", "inv": True},
            {"lab": "ROT", "val": "0", "inv": False},
            {"lab": "LANE", "val": "TRIG", "inv": True},
            {"lab": "DEST", "val": "PTCH", "inv": True},
            {"lab": "DPTH", "val": "64", "inv": False},
            {"lab": "", "val": "", "inv": False},
        ],
        "Only PTCH (DEST) is rewritten onto the new notes. VOL is kept.",
        [
            ("note", locks({1, 3, 5, 7})),
            ("PTCH", locks({1, 3, 5, 7})),
            ("VOL", locks({1, 3, 5, 7})),
        ],
        [
            ("note", locks({1, 5})),
            ("PTCH", locks({1, 5})),
            ("VOL", mix(lock_idxs={1, 5}, tl_idxs={3, 7})),
        ],
        ["PULS 4 to 2", "notes 1+5"],
        ["PTCH: cleared on 3+7, written on 1+5", "VOL: still on 1+5; steps 3+7 kept as TL"],
        "DEST=PTCH follows the notes. Other DEST locks (VOL) survive as trigless.",
    ),
    (
        "plck-overwrite",
        [
            {"lab": "PULS", "val": "4", "inv": False},
            {"lab": "ROT", "val": "1", "inv": True},
            {"lab": "LANE", "val": "PLCK", "inv": True},
            {"lab": "DEST", "val": "PTCH", "inv": True},
            {"lab": "DPTH", "val": "64", "inv": False},
            {"lab": "", "val": "", "inv": False},
        ],
        "Notes stay put. PTCH is fully replaced by the PLCK rhythm.",
        [
            ("note", locks({1, 3, 5, 7})),
            ("PTCH", locks({1, 3, 5, 7})),
            ("VOL", tls({2, 4, 6, 8})),
        ],
        [
            ("note", locks({1, 3, 5, 7})),
            ("PTCH", tls({2, 4, 6, 8})),
            ("VOL", tls({2, 4, 6, 8})),
        ],
        ["ROT to 1", "hits 2 4 6 8"],
        [
            "PTCH: gone from notes 1 3 5 7; TL on 2 4 6 8",
            "VOL: unchanged (still TL on 2 4 6 8)",
        ],
        "PLCK YES overwrites this DEST even on notes. Other DEST stacks do not move.",
    ),
    (
        "clear-dest",
        [
            {"lab": "PULS", "val": "0", "inv": True},
            {"lab": "ROT", "val": "0", "inv": False},
            {"lab": "LANE", "val": "PLCK", "inv": True},
            {"lab": "DEST", "val": "PTCH", "inv": True},
            {"lab": "DPTH", "val": "0", "inv": False},
            {"lab": "", "val": "", "inv": False},
        ],
        "PLCK PULS=0 clears this DEST over the fill range.",
        [
            ("note", locks({1, 3, 5, 7})),
            ("PTCH", locks({1, 3, 5, 7})),
            ("VOL", tls({2, 4, 6, 8})),
        ],
        [
            ("note", locks({1, 3, 5, 7})),
            ("PTCH", empty8()),
            ("VOL", tls({2, 4, 6, 8})),
        ],
        ["PULS 0", "DEST=PTCH"],
        ["PTCH gone everywhere in range", "notes and VOL still there"],
        "PULSE 0 + YES on PLCK is a DEST eraser. Notes stay.",
    ),
]


def svg_to_png(svg: Path) -> None:
    from PIL import Image  # noqa: PLC0415

    text = svg.read_text()
    m = re.search(r'height="([0-9]+)"', text)
    if not m:
        raise SystemExit(f"no height in {svg}")
    h = int(m.group(1))
    with tempfile.TemporaryDirectory() as td:
        html_path = Path(td) / "d.html"
        html_path.write_text(
            "<!doctype html><html><head><meta charset=utf-8>"
            "<style>html,body{margin:0;padding:0;background:#fff;overflow:hidden}</style>"
            f"</head><body>{text}</body></html>"
        )
        raw = Path(td) / "raw.png"
        subprocess.run(
            [
                CHROME,
                "--headless=new",
                "--disable-gpu",
                "--hide-scrollbars",
                "--force-device-scale-factor=1",
                f"--screenshot={raw}",
                f"--window-size={W},{h}",
                f"file://{html_path}",
            ],
            check=True,
            capture_output=True,
        )
        im = Image.open(raw).convert("RGB")
        canvas = Image.new("RGB", (W, h), (255, 255, 255))
        canvas.paste(im.crop((0, 0, min(im.size[0], W), min(im.size[1], h))), (0, 0))
        out = OUT / f"{svg.stem}.png"
        canvas.save(out)
        print(f"{out.name} {canvas.size}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--png", action="store_true", help="also rasterize via Chrome")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    paths = [make(*spec) for spec in SPECS]
    if args.png:
        for p in paths:
            svg_to_png(p)


if __name__ == "__main__":
    main()
