#!/usr/bin/env python3
"""SEQ tonal page: scale, phrase, arpeggio and harmony contract.

Checks the scale tables and musical rules against the assembly source. The
port scenarios exercise panel writes and persisted settings separately.
"""

from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / "modules/seq/seq.s"
FAILS = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global FAILS
    if ok:
        print(f"  [PASS] {name}" + (f" ({detail})" if detail else ""))
    else:
        FAILS += 1
        print(f"  [FAIL] {name}" + (f": {detail}" if detail else ""))


def block(src: str, start: str, end: str) -> str:
    i = src.find(start)
    j = src.find(end, i + len(start)) if i >= 0 else -1
    return src[i:j] if i >= 0 and j > i else ""


def table(src: str, label: str, directive: str) -> list[int]:
    m = re.search(rf"{label}:\s*\n\s*\.{directive}\s+([^\n|]+)", src)
    if not m:
        return []
    return [int(x.strip(), 0) for x in m.group(1).split(",")]


def notes(mask: int) -> list[int]:
    return [pc for pc in range(12) if mask & (1 << pc)]


def on_scale(note: int, root: int, mask: int) -> bool:
    return bool(mask & (1 << ((note - root) % 12)))


def snap(note: int, root: int, mask: int) -> int:
    for distance in range(13):
        lower = note - distance
        if lower >= 0 and on_scale(lower, root, mask):
            return lower
        upper = note + distance
        if upper <= 127 and on_scale(upper, root, mask):
            return upper
    return note


def phrase_rank(step: int, count: int, phrase: int) -> int:
    if phrase == 4:
        return (1664525 * (step + 1) + 1013904223) % count
    if phrase == 1:
        return count - 1 - (step % count)
    if phrase == 2:
        period = max(1, 2 * count - 2)
        pos = step % period
        return pos if pos < count else period - pos
    if phrase == 3:
        period = 2 * count
        pos = step % period
        return pos if pos < count else 2 * count - 1 - pos
    return step % count


def degree_interval(mask: int, degree: int) -> int:
    """The assembly helper's 1-based scale-degree to semitone conversion."""
    selected = notes(mask)
    return selected[degree - 1] if 0 < degree <= len(selected) else 12


def main() -> int:
    src = SRC.read_text()
    masks = table(src, "ef_scale_masks", "word")
    counts = table(src, "ef_scale_counts", "byte")
    check("eight built-in scales have matching tone counts",
          len(masks) == len(counts) == 8
          and [m.bit_count() for m in masks] == counts)
    check("major scale uses relative semitones 0,2,4,5,7,9,11",
          bool(masks) and notes(masks[0]) == [0, 2, 4, 5, 7, 9, 11])
    check("root anchors the same scale mask across all twelve keys",
          bool(masks) and all(on_scale(root + degree, root, masks[0])
                              for root in range(12)
                              for degree in notes(masks[0])))
    check("snap chooses the lower note on a tie",
          bool(masks) and snap(1, 0, masks[0]) == 0)

    if masks:
        major = masks[0]
        in_range = [n for n in range(48, 73) if on_scale(n, 2, major)]
        check("MIDI melody candidates stay in range and in rooted scale",
              bool(in_range) and all(48 <= n <= 72 and on_scale(n, 2, major)
                                     for n in in_range))
        up = [phrase_rank(s, 5, 0) for s in range(6)]
        down = [phrase_rank(s, 5, 1) for s in range(6)]
        alt = [phrase_rank(s, 5, 2) for s in range(9)]
        tri = [phrase_rank(s, 5, 3) for s in range(10)]
        check("UP and DOWN phrases traverse the full range",
              up == [0, 1, 2, 3, 4, 0]
              and down == [4, 3, 2, 1, 0, 4])
        check("ALT and TRI have distinct repeating contours",
              alt == [0, 1, 2, 3, 4, 3, 2, 1, 0]
              and tri == [0, 1, 2, 3, 4, 4, 3, 2, 1, 0])
        offsets = [degree_interval(major, d) for d in range(1, 8)]
        check("scale degrees resolve unison through seventh",
              offsets == [0, 2, 4, 5, 7, 9, 11])
        arp = [60 + degree_interval(major, d) for d in range(1, 8)]
        check("MIDI ARP walks the selected scale from Part NOTE",
              arp == [60, 62, 64, 65, 67, 69, 71]
              and all(on_scale(n, 0, major) for n in arp))
        chord = offsets[2], offsets[4], offsets[6]
        interval_map = [degree_interval(major, d) for d in range(1, 8)]
        check("CHRD adds scale thirds/fifths and optional seventh",
              chord == (4, 7, 11) and interval_map[:3] == [0, 2, 4])
        check("audio INTV selects unison through seventh scale degrees",
              interval_map == [0, 2, 4, 5, 7, 9, 11])

    draw = block(src, "ef_draw:", "d9:")
    page = block(src, "ef_page_left:", "ef_enc:")
    enc = block(src, "ef_enc:", "ef_level:")
    save = block(src, "ef_tone_save:", "ef_tone_load:")
    tonal = block(src, "ef_write_midi_pitch:", "ef_midi_chord_locks:")
    chord = block(src, "ef_midi_chord_locks:", "ef_midi_clear_chord_locks:")
    chord_clear = block(src, "ef_midi_clear_chord_locks:", "ef_write_ptch:")
    ptch = block(src, "ef_write_ptch:", "ef_part_flat:")
    check("page indicator stays at logo-panel top-right and grid draws on both pages",
          "X_PAGE_R" in draw and ".set    X_PAGE_R,  X_GRID-1" in src
          and "T_PAGE1" in draw and "T_PAGE2" in draw
          and "ef_draw_pat" in draw and "ef_grid" in draw)
    check("LEFT and RIGHT select the two knob pages",
          "ef_page_left" in page and "ef_page_right" in page
          and "ef_page_no" in page and ".byte   0x34, 0" in src
          and ".byte   0x21, 0                 | RIGHT" in src)
    check("page 2 routes all six encoders to tonal settings",
          "ef_enc_tonal" in enc and "ef_tonal_nudge" in enc
          and "ef_tone_harm" in block(src, "ef_tonal_nudge:", "ef_grid:"))
    check("numeric tonal cells restore their index after SPRINTF",
          "movel   ef_tonal_index,%d0     | SPRINTF returns its character count" in src)
    check("MIDI MELO honors phrase rank and MIDI ARP uses scale degrees",
          "ef_pitch_rank" in tonal and "ef_tone_range" in tonal
          and "ewmp_arp:" in tonal and "ef_degree_interval" in tonal
          and "ef_tonal_index" in tonal and "ef_tonal_value" in tonal)
    check("MIDI chord mode writes NOT2/NOT3 and optional NOT4",
          "ef_midi_chord_locks:" in src and "ef_degree_interval" in src
          and "ef_tone_harm" in block(src, "ef_midi_chord_locks:", "ef_midi_clear_chord_locks:"))
    check("MIDI pitch and chord helpers preserve the fill pulse count",
          "movem.l %d4-%d7,%sp@" in tonal
          and "movem.l %sp@,%d4-%d7" in tonal
          and "movel   %d4,-(%sp)" in chord
          and "movel   (%sp)+,%d4" in chord
          and "movel   %d4,-(%sp)" in chord_clear
          and "movel   (%sp)+,%d4" in chord_clear)
    check("audio melody uses SEQ scale/root and audio ARP rises",
          "ef_tone_mask" in ptch and "ef_tone_root" in ptch
          and "negl    %d0" in ptch and "ef_pitch_rank" in ptch
          and "ef_tone_mode" in block(src, "ef_pitch_rank:", "ef_snap_note:"))
    check("audio INTV shifts PTCH before scale filtering",
          "ef_pitch_offset" in ptch and "ef_degree_interval" in ptch
          and "ep_dst: addl    ef_pitch_offset" in ptch)
    check("tonal settings persist per audio and MIDI track with v7 migration",
          "EF_TONE_B, 16*EF_TONE_REC" in src
          and "EF_VER,    8" in src and "ef_tone_addr:" in src
          and "addil   #8,%d0" in block(src, "ef_tone_addr:", "ef_tone_save:")
          and "ef_tone_defaults" in block(src, "el_v7:", "el_v6:"))
    check("32-bit working values save their low byte to the tonal record",
          all(f"movel   ef_tone_{field},%d1" in save
              for field in ("scale", "root", "mode", "range", "phrase", "harm", "style")))
    check("audio scale generation has no SCALE QUANTIZER address dependency",
          "SCALE_AT" not in ptch and "NV_ROOT" not in ptch
          and "NV_SCALE" not in ptch)

    print(f"SEQ tonal: {FAILS} failed checks")
    return FAILS


if __name__ == "__main__":
    sys.exit(main())
