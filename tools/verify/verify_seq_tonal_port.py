#!/usr/bin/env python3
"""Port checks for SEQ's two knob pages and per-track tonal persistence."""

from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "tools/verify"), str(ROOT / "tools/panel")]

import verify_seq_scenarios as seq  # noqa: E402
from stems_panel import MenuPort  # noqa: E402
from panel_server import popup_geometry  # noqa: E402


def main() -> int:
    template = next((parent / "template_project" for parent in ROOT.parents
                     if (parent / "template_project").is_dir()), None)
    if template is None:
        print("SEQ tonal port: skip (template_project unavailable)")
        return 0
    with tempfile.TemporaryDirectory(prefix="seq-tonal-port-") as tmp:
        card = pathlib.Path(tmp) / "card.img"
        tree = pathlib.Path(tmp) / "tree"
        subprocess.check_call([
            sys.executable, str(ROOT / "tools/emu/ot_emu/stage_card.py"),
            str(template), "OCTABAM", "A", "--tree", str(tree), "--out", str(card),
        ], cwd=ROOT)
        fails = 0

        def check(label: str, passed: bool, detail: str = "") -> None:
            nonlocal fails
            if not passed:
                fails += 1
            print(f"  [{'PASS' if passed else 'FAIL'}] {label}"
                  + (f" ({detail})" if detail else ""))

        with MenuPort(ROOT / "out/mainos_bus.bin", card, "OCTABAM", "A", mkii=True) as p:
            p.settle()
            for _ in range(3):
                p.press("no", settle=80)
            s = seq.SeqPort(p)

            # Audio track: page switch leaves the rhythm grid untouched.
            s.open_seq("t1")
            page = seq.local_sym("ef_page_no")
            s.prime(lane=0, dest=0, depth=0, pulses=3, trig_pulses=3)
            s.yes()
            grid = seq.mask_of(p)
            p.press("right", settle=150)
            check("RIGHT selects page 2/2 without changing the grid",
                  p.long(page) == 1 and seq.mask_of(p) == grid,
                  f"grid={seq.mask_of(p).hex()} original={grid.hex()}")
            range_value = seq.local_sym("ef_tone_range")

            def range_pixels() -> int:
                rows = p.link.lcd_rows()
                return sum(rows[y][x] for y in range(32, 39) for x in range(50, 67))

            for delta, expected in ((-3, 9), (-8, 1), (-1, 0)):
                p.proc.command(f"knob 0x33 {delta}", "ok")
                p.run(250)
                pixels = range_pixels()
                check(f"RANG value {expected} stays visible on screen",
                      p.long(range_value) == expected and pixels > 0,
                      f"value={p.long(range_value)} pixels={pixels}")
            p.proc.command("knob 0x33 12", "ok")
            p.run(250)
            p.press("left", settle=150)
            check("LEFT restores page 1/2 without changing the grid",
                  p.long(page) == 0 and seq.mask_of(p) == grid,
                  f"page={p.long(page)} grid={seq.mask_of(p).hex()} original={grid.hex()}")
            s.close_seq()

            # The stock Project menu must own arrows as soon as SEQ is closed.
            p.press("proj", settle=400)
            geo = popup_geometry(p.rt.uc)
            project_open = geo is not None and geo[1] == 0 and geo[3] == 0x40
            check("PROJECT opens immediately after SEQ closes", project_open,
                  f"geometry={geo}")
            if project_open:
                page_before = p.long(page)
                p.press("right", settle=150)
                check("Project RIGHT is not consumed by the closed SEQ layer",
                      p.long(page) == page_before and popup_geometry(p.rt.uc) == geo)
                p.press("no", settle=400)

            # MIDI T1 settings occupy their own record (audio records are 0..7).
            p.press("midi", settle=300)
            s.open_seq("t1")
            p.press("right", settle=150)
            for enc, delta in ((0, 1), (1, 2), (2, 2), (3, -12)):
                p.proc.command(f"knob {0x30 + enc:#x} {delta}", "ok")
                p.run(250)
            tone_mem = seq.local_sym("ef_tone_mem")
            midi_record = tone_mem + 64
            check("MIDI tonal controls persist scale/root/ARP/range",
                  p.peek(midi_record, 6) == bytes((1, 2, 2, 0, 0, 0)),
                  p.peek(midi_record, 6).hex())
            s.close_seq()
            s.open_seq("t2")
            check("MIDI tonal settings are isolated per track",
                  p.long(seq.local_sym("ef_tone_scale")) == 0
                  and p.long(seq.local_sym("ef_tone_root")) == 0
                  and p.long(seq.local_sym("ef_tone_mode")) == 0
                  and p.long(seq.local_sym("ef_tone_range")) == 12)
            s.close_seq()
            s.open_seq("t1")
            check("reopening MIDI T1 restores tonal settings",
                  p.long(seq.local_sym("ef_tone_scale")) == 1
                  and p.long(seq.local_sym("ef_tone_root")) == 2
                  and p.long(seq.local_sym("ef_tone_mode")) == 2
                  and p.long(seq.local_sym("ef_tone_range")) == 0)

            s.close_seq()

            # Return to audio mode and verify its independent record.
            p.press("midi", settle=300)
            s.open_seq("t1")
            p.press("right", settle=150)
            for enc, delta in ((1, 2), (2, 1)):
                p.proc.command(f"knob {0x30 + enc:#x} {delta}", "ok")
                p.run(250)
            check("audio tonal controls use a separate T1 record",
                  p.peek(tone_mem, 6) == bytes((0, 2, 1, 12, 0, 0)),
                  p.peek(tone_mem, 6).hex())
            s.close_seq()

        print(f"SEQ tonal port: {fails} failed checks")
        return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
