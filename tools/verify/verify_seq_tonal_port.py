#!/usr/bin/env python3
"""Port checks for SEQ page gating, labels, and per-track tonal persistence."""

from __future__ import annotations

import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "tools/verify"), str(ROOT / "tools/panel")]

import verify_seq_scenarios as seq  # noqa: E402
from stems_panel import MenuPort  # noqa: E402
from seq_port_fixture import stage_project  # noqa: E402
from panel_server import popup_geometry  # noqa: E402


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="seq-tonal-port-") as tmp:
        card = pathlib.Path(tmp) / "card.img"
        tree = pathlib.Path(tmp) / "tree"
        # CI has no template_project (this gate SKIPped there): the image makes its own project.
        stage_project(seq.IMAGE, card, tree)
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
            dest = seq.local_sym("ef_dest")
            check("audio SEQ opens on SRC PTCH by default",
                  p.long(dest) == 0, f"dest={p.long(dest)}")
            part = (p.long(seq.DBPTR_ADDR)
                    + p.peek(seq.UI_PART, 1)[0] * seq.PART_STR)
            machine = part + 0x8eda2
            original_machine = p.peek(machine, 1)
            s.prime(lane=0, dest=0, depth=0, pulses=3, trig_pulses=3)
            p.poke(machine, b"\x02")  # THRU slot A is INAB, not PTCH.
            p.press("left", settle=150)
            no_pitch_hint = p.link.lcd_rows()
            p.press("right", settle=150)
            check("THRU INAB cannot open Harmony",
                  p.long(page) == 0 and p.long(dest) == 0)
            p.poke(machine, b"\x01")  # FLEX slot A is PTCH.
            p.press("left", settle=150)
            pitch_hint = p.link.lcd_rows()
            check("RIGHT hint appears for PTCH but not THRU INAB",
                  any(pitch_hint[y][x] != no_pitch_hint[y][x]
                      for y in range(2, 8) for x in range(47, 59)))
            s.prime(lane=0, dest=15, depth=0, pulses=3, trig_pulses=3)
            p.press("right", settle=150)
            check("RIGHT stays on Rhythm for non-pitch destination",
                  p.long(page) == 0 and p.long(dest) == 15,
                  f"page={p.long(page)} dest={p.long(dest)}")
            s.prime(lane=0, dest=0, depth=0, pulses=3, trig_pulses=3)
            s.yes()
            grid = seq.mask_of(p)
            p.press("right", settle=150)
            check("RIGHT opens Harmony for NOTE/PTCH without changing the grid",
                  p.long(page) == 1 and seq.mask_of(p) == grid,
                  f"grid={seq.mask_of(p).hex()} original={grid.hex()}")
            phrase_value = seq.local_sym("ef_tone_phrase")
            jump_value = seq.local_sym("ef_tone_jump")
            tonal_buf = seq.local_sym("ef_buf")

            def phrase_pixels() -> int:
                rows = p.link.lcd_rows()
                return sum(rows[y][x] for y in range(32, 39) for x in range(50, 67))

            default_phrase_pixels = phrase_pixels()
            check("new audio settings default to first PHRS option RAND",
                  p.long(phrase_value) == 0 and default_phrase_pixels > 0,
                  f"phrase={p.long(phrase_value)} pixels={default_phrase_pixels}")
            p.proc.command("knob 0x33 1", "ok")
            p.run(250)
            up_pixels = phrase_pixels()
            check("PHRS next option after RAND is UP",
                  p.long(phrase_value) == 1 and up_pixels > 0
                  and up_pixels != default_phrase_pixels,
                  f"phrase={p.long(phrase_value)} pixels={up_pixels}")
            p.proc.command("knob 0x33 -1", "ok")
            p.run(250)
            check("PHRS returns to RAND at its first value",
                  p.long(phrase_value) == 0)
            p.proc.command("knob 0x34 127", "ok")
            p.run(250)
            check("audio E JUMP reaches 127",
                  p.long(jump_value) == 127
                  and p.peek(tonal_buf, 4) == b"127\0",
                  f"jump={p.long(jump_value)} display={p.peek(tonal_buf, 4)!r}")
            p.proc.command("knob 0x34 -127", "ok")
            p.run(250)
            check("audio JUMP clamps at zero and displays 0",
                  p.long(jump_value) == 0
                  and p.peek(tonal_buf, 2) == b"0\0",
                  f"jump={p.long(jump_value)} display={p.peek(tonal_buf, 2)!r}")
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
            check("MIDI SEQ opens on NOTE by default",
                  p.long(dest) == 0, f"dest={p.long(dest)}")
            p.press("right", settle=150)
            for enc, delta in ((0, 1), (1, 2), (2, 2), (3, -12), (4, 127)):
                p.proc.command(f"knob {0x30 + enc:#x} {delta}", "ok")
                p.run(250)
            tone_mem = seq.local_sym("ef_tone_mem")
            midi_record = tone_mem + 64
            check("MIDI tonal controls persist scale/root/mode/JUMP/PHRS/VOIC",
                  p.peek(midi_record, 7) == bytes((1, 2, 0, 127, 0, 3, 0)),
                  p.peek(midi_record, 7).hex())
            check("MIDI E JUMP display is numeric",
                  p.peek(tonal_buf, 4) == b"127\0",
                  repr(p.peek(tonal_buf, 4)))
            p.proc.command("knob 0x34 -127", "ok")
            p.run(250)
            check("JUMP clamps at zero", p.long(jump_value) == 0,
                  f"jump={p.long(jump_value)}")
            p.proc.command("knob 0x34 127", "ok")
            p.run(250)
            p.proc.command("knob 0x32 -127", "ok")
            p.run(250)
            check("MIDI VOIC stops at one when turned below minimum",
                  p.long(seq.local_sym("ef_tone_harm")) == 1)
            p.proc.command("knob 0x32 127", "ok")
            p.run(250)
            check("MIDI VOIC stops at four when turned above maximum",
                  p.long(seq.local_sym("ef_tone_harm")) == 4)
            p.proc.command("knob 0x32 -1", "ok")
            p.run(250)
            s.close_seq()
            s.open_seq("t2")
            check("MIDI tonal settings are isolated per track",
                  p.long(seq.local_sym("ef_tone_scale")) == 0
                  and p.long(seq.local_sym("ef_tone_root")) == 0
                  and p.long(seq.local_sym("ef_tone_mode")) == 0
                  and p.long(jump_value) == 0
                  and p.long(seq.local_sym("ef_tone_phrase")) == 0)
            s.close_seq()
            s.open_seq("t1")
            check("reopening MIDI T1 restores tonal settings",
                  p.long(seq.local_sym("ef_tone_scale")) == 1
                  and p.long(seq.local_sym("ef_tone_root")) == 2
                  and p.long(seq.local_sym("ef_tone_mode")) == 0
                  and p.long(seq.local_sym("ef_tone_harm")) == 3
                  and p.long(jump_value) == 127
                  and p.long(seq.local_sym("ef_tone_phrase")) == 0)

            s.close_seq()

            # Return to audio mode and verify its independent record.
            p.press("midi", settle=300)
            s.open_seq("t1")
            p.press("right", settle=150)
            for enc, delta in ((1, 2), (2, 127), (4, 127), (5, 127)):
                p.proc.command(f"knob {0x30 + enc:#x} {delta}", "ok")
                p.run(250)
            check("audio tonal controls use a separate T1 record",
                  p.peek(tone_mem, 7) == bytes((0, 2, 0, 127, 0, 0, 0)),
                  p.peek(tone_mem, 7).hex())
            rows = p.link.lcd_rows()
            check("audio C and F cells are blank",
                  not any(rows[y][x] for y in (*range(3, 18), *range(23, 38))
                          for x in range(101, 118)))
            check("audio E JUMP remains active at 127",
                  p.long(jump_value) == 127,
                  f"jump={p.long(jump_value)}")
            s.close_seq()
            s.open_seq("t2")
            check("audio JUMP is isolated per track",
                  p.long(jump_value) == 0, f"jump={p.long(jump_value)}")
            s.close_seq()
            s.open_seq("t1")
            check("audio JUMP reloads from its own track record",
                  p.long(jump_value) == 127, f"jump={p.long(jump_value)}")
            s.close_seq()
            p.poke(machine, original_machine)

        print(f"SEQ tonal port: {fails} failed checks")
        return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
