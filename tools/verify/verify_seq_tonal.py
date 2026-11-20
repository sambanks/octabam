#!/usr/bin/env python3
"""SEQ tonal page: scale, phrase, arpeggio and harmony contract.

Checks the scale tables and musical rules against the assembly source. The
port scenarios exercise panel writes and persisted settings separately.
"""

from __future__ import annotations

import pathlib
import math
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
    if phrase == 0:
        return (1664525 * (step + 1) + 1013904223) % count
    if phrase == 2:
        return count - 1 - (step % count)
    if phrase == 3:
        period = max(1, 2 * count - 2)
        pos = step % period
        return pos if pos < count else period - pos
    if phrase == 4:
        period = 2 * count
        pos = step % period
        return pos if pos < count else 2 * count - 1 - pos
    return step % count


def pitch_jump(step: int, count: int, phrase: int, jump: int,
               *, anchor: int = 0, pulses: int = 8) -> int:
    """Mirror anchored cyclic UP/DOWN and ALT/TRI rank stepping."""
    if phrase in (1, 2):
        if count <= 2 or jump <= 0:
            multiplier = 1
        else:
            multiplier = jump * ((count - 1) // 2) // 127 + 1
            while math.gcd(multiplier, count) != 1:
                multiplier += 1
        direction = 1 if phrase == 1 else -1
        return (anchor + direction * (step * multiplier % count)) % count
    if phrase == 0:
        return rand_walk(count, jump, max(step + 1, 1))[step]
    if count <= 2 or jump <= 0:
        return phrase_rank(step, count, phrase)
    stride = jump * ((count - 1) // 2) // 127
    multiplier = stride + 1
    period = count if phrase in (1, 2) else (
        2 * (count - 1) if phrase == 3 else 2 * count)
    while multiplier > 1 and math.gcd(multiplier, period) != 1:
        multiplier += 1
    return phrase_rank(step * multiplier, count, phrase)


def rand_walk(count: int, jump: int, hits: int, seed: int = 1) -> list[int]:
    """Model RAND's seeded starting rank and random-direction JUMP walk."""
    if count <= 1 or hits <= 0:
        return [0] * max(0, hits)

    def rng() -> int:
        nonlocal seed
        seed = (1664525 * seed + 1013904223) & 0xFFFFFFFF
        return seed

    stride = 1 + jump * ((count - 1) // 2) // 127
    rank = rng() % count
    result = [rank]
    for _ in range(hits - 1):
        rank = (rank + (stride if rng() < 0x80000000 else -stride)) % count
        result.append(rank)
    return result


def degree_interval(mask: int, degree: int) -> int:
    """The assembly helper's 1-based scale-degree to semitone conversion."""
    selected = notes(mask)
    return selected[degree - 1] if 0 < degree <= len(selected) else 12


def migrate_v9_tonal(payload: bytes) -> bytes:
    """Model v9 migration: clear RANG and rotate the old PHRS values."""
    out = bytearray(payload)
    for track in range(16):
        out[track * 8 + 3] = 0
        old = out[track * 8 + 4]
        out[track * 8 + 4] = (old + 1) % 5 if old < 5 else 0
    return bytes(out)


def migrate_v10_phrases(payload: bytes) -> bytes:
    """Model v10->v11 migration: RAND moves from PHRS value 4 to 0."""
    out = bytearray(payload)
    for track in range(16):
        pos = track * 8 + 4
        old = out[pos]
        out[pos] = (old + 1) % 5 if old < 5 else 0
    return bytes(out)


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
        up = [pitch_jump(s, 9, 1, 0, anchor=4, pulses=5) for s in range(5)]
        down = [pitch_jump(s, 9, 2, 0, anchor=4, pulses=5) for s in range(5)]
        alt = [phrase_rank(s, 5, 3) for s in range(9)]
        tri = [phrase_rank(s, 5, 4) for s in range(10)]
        check("UP starts on the Part pitch and wraps at the top of the range",
              up == [4, 5, 6, 7, 8])
        check("DOWN starts on the Part pitch and wraps at the bottom of the range",
              down == [4, 3, 2, 1, 0])
        major_notes = [n for n in range(12, 109) if on_scale(n, 0, major)]
        anchor = major_notes.index(60)
        up_notes = [major_notes[pitch_jump(s, len(major_notes), 1, 0,
                                            anchor=anchor, pulses=8)]
                    for s in range(8)]
        down_notes = [major_notes[pitch_jump(s, len(major_notes), 2, 0,
                                              anchor=anchor, pulses=8)]
                      for s in range(8)]
        check("MIDI UP starts on Part NOTE and wraps through the DEPTH range",
              up_notes == [60, 62, 64, 65, 67, 69, 71, 72]
              and len({b-a for a, b in zip(up_notes, up_notes[1:])}) > 1,
              f"notes={up_notes}")
        check("MIDI DOWN starts on Part NOTE and wraps through the DEPTH range",
              down_notes == [60, 59, 57, 55, 53, 52, 50, 48]
              and len({a-b for a, b in zip(down_notes, down_notes[1:])}) > 1,
              f"notes={down_notes}")
        wide_up = [major_notes[pitch_jump(s, len(major_notes), 1, 127,
                                           anchor=anchor, pulses=8)]
                   for s in range(8)]
        wide_down = [major_notes[pitch_jump(s, len(major_notes), 2, 127,
                                             anchor=anchor, pulses=8)]
                     for s in range(8)]
        check("maximum JUMP still wraps UP and DOWN from Part NOTE",
              wide_up[0] == wide_down[0] == 60
              and wide_up == [major_notes[pitch_jump(s, len(major_notes), 1, 127,
                                                      anchor=anchor, pulses=8)]
                              for s in range(8)]
              and wide_down == [major_notes[pitch_jump(s, len(major_notes), 2, 127,
                                                        anchor=anchor, pulses=8)]
                                for s in range(8)],
              f"up={wide_up} down={wide_down}")
        check("UP and DOWN continue wrapping on sequences longer than the range",
              all(pitch_jump(s, 5, phrase, 127, anchor=2, pulses=20)
                  == pitch_jump(s % 5, 5, phrase, 127, anchor=2, pulses=20)
                  for phrase in (1, 2) for s in range(20)))
        check("JUMP remains inside small candidate sets",
              all(0 <= pitch_jump(s, n, 1, 127) < n
                  for n in range(1, 13) for s in range(64)))
        check("ALT/TRI/RAND retain bounded phrase behavior with JUMP",
              all(0 <= pitch_jump(s, n, phrase, jump) < n
                  for phrase in (0, 3, 4) for n in range(1, 65)
                  for s in range(2 * n) for jump in (0, 127)))
        check("UP and DOWN cycle through candidates when the phrase exceeds DEPTH",
              all(pitch_jump(s + n, n, phrase, j, anchor=n // 2, pulses=64)
                  == pitch_jump(s, n, phrase, j, anchor=n // 2, pulses=64)
                  for n in range(1, 65) for j in range(128)
                  for phrase in (1, 2) for s in range(64)))
        check("ALT/TRI still cover every candidate at maximum JUMP",
              all(len({pitch_jump(s, n, phrase, 127) for s in range(
                       2 * (n - 1) if phrase == 3 else 2 * n)}) == n
                  for phrase in (3, 4) for n in range(3, 65)))
        rand_rolls = {jump: rand_walk(15, jump, 64)
                      for jump in (0, 64, 127)}
        rand_strides = {jump: 1 + jump * 7 // 127
                        for jump in (0, 64, 127)}
        check("RAND JUMP sets every neighboring scale-degree distance",
              all(all((b - a) % 15 in (stride, 15 - stride)
                      for a, b in zip(rand_rolls[jump], rand_rolls[jump][1:]))
                  for jump, stride in rand_strides.items()))
        check("RAND stays random while JUMP controls interval size",
              all(len(set(roll)) > 1 for roll in rand_rolls.values())
              and all(len(set((b - a) % 15
                              for a, b in zip(roll, roll[1:]))) == 2
                      for roll in rand_rolls.values())
              and len({tuple(roll) for roll in rand_rolls.values()}) == 3)
        legacy = bytes(value for track in range(16)
                       for value in (track, track + 1, track + 2, 127,
                                     track % 5, track + 4, track + 5, 0))
        migrated = migrate_v9_tonal(legacy)
        check("v9 migration clears legacy RANG, rotates PHRS, and preserves other fields",
              len(migrated) == 128
              and all(migrated[t * 8 + 3] == 0
                      and migrated[t * 8 + 4] == (legacy[t * 8 + 4] + 1) % 5
                      and migrated[t * 8:t * 8 + 3] == legacy[t * 8:t * 8 + 3]
                      and migrated[t * 8 + 5:t * 8 + 8] == legacy[t * 8 + 5:t * 8 + 8]
                      for t in range(16)))
        v10 = bytes(value for track in range(16)
                    for value in (track, track + 1, track + 2, track + 3,
                                  track % 5, track + 5, track + 6, 0))
        migrated_v10 = migrate_v10_phrases(v10)
        check("v10 migration rotates all PHRS values and preserves other settings",
              len(migrated_v10) == 128
              and all(migrated_v10[t * 8 + 4] == (v10[t * 8 + 4] + 1) % 5
                      and migrated_v10[t * 8:t * 8 + 4] == v10[t * 8:t * 8 + 4]
                      and migrated_v10[t * 8 + 5:t * 8 + 8] == v10[t * 8 + 5:t * 8 + 8]
                      for t in range(16)))
        check("ALT and TRI have distinct repeating contours",
              alt == [0, 1, 2, 3, 4, 3, 2, 1, 0]
              and tri == [0, 1, 2, 3, 4, 4, 3, 2, 1, 0])
        offsets = [degree_interval(major, d) for d in range(1, 8)]
        check("scale degrees resolve unison through seventh",
              offsets == [0, 2, 4, 5, 7, 9, 11])
        arp = [60 + degree_interval(major, d) for d in range(1, 8)]
        check("scale degree helper remains available to audio pitch generation",
              arp == [60, 62, 64, 65, 67, 69, 71]
              and all(on_scale(n, 0, major) for n in arp))
        chord = offsets[2], offsets[4], offsets[6]
        interval_map = [degree_interval(major, d) for d in range(1, 8)]
        check("legacy scale intervals are still calculated for audio INTV",
              chord == (4, 7, 11) and interval_map[:3] == [0, 2, 4])
        check("audio INTV selects unison through seventh scale degrees",
              interval_map == [0, 2, 4, 5, 7, 9, 11])

    draw = block(src, "ef_draw:", "d9:")
    page = block(src, "ef_page_left:", "ef_enc:")
    enc = block(src, "ef_enc:", "ef_level:")
    save = block(src, "ef_tone_save:", "ef_tone_load:")
    tonal = block(src, "ef_write_midi_pitch:", "ef_midi_chord_locks:")
    jump = block(src, "ef_pitch_step:", "ef_snap_note:")
    jump_draw = block(src, "edt_jump:", "| d0=index 0..5")
    chord = block(src, "ef_midi_chord_locks:", "ef_midi_clear_chord_locks:")
    chord_clear = block(src, "ef_midi_clear_chord_locks:", "ef_write_ptch:")
    ptch = block(src, "\nef_write_ptch:\n", "\nef_part_flat:\n")
    page_right = block(src, "ef_page_right:", "ef_enc:")
    check("RIGHT is pitch-gated and page labels use padded arrows",
          "bsr.w   ef_pitch_selected" in page_right and "beq.s   9f" in page_right
          and '.asciz " 1>"' in src and '.asciz "<2 "' in src
          and "bsr.w   ef_pitch_selected" in draw)
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
          and "ef_tone_harm" in block(src, "ef_tonal_nudge:", "ef_grid:")
          and "ef_tone_jump" in block(src, "ef_tonal_nudge:", "ef_grid:"))
    check("numeric tonal cells restore their index after SPRINTF",
          "movel   ef_tonal_index,%d3" in block(src, "ef_tonal_draw_cell:", "ef_tonal_nudge:"))
    check("audio and MIDI pitch generation use phrase rank, JUMP, and DEPTH",
          "bsr.w   ef_pitch_step" in ptch
          and "ef_pitch_rank" in tonal and "ef_depth" in tonal
          and "bsr.w   ef_pitch_step" in tonal
          and "ef_tone_range" not in tonal
          and "ewmp_arp:" in tonal and "ef_degree_interval" in tonal
          and "ef_tonal_index" in tonal and "ef_tonal_value" in tonal)
    check("JUMP display formats its value numerically on both pages",
          "movel   ef_tone_jump,-(%sp)" in jump_draw
          and "pea     VFMT" in jump_draw and "pea     ef_buf" in jump_draw
          and "jsr     SPRINTF" in jump_draw and "moveq   #4,%d0" in jump_draw)
    check("JUMP is bounded by DEPTH; RAND uses a random-direction stride",
          "ef_tone_jump" in jump and "ef_jump_index" in tonal
          and "eps_gcd" in jump and "bsr.w   ef_pitch_step" in tonal
          and "mulu.w  %d0,%d2" in jump
          and "epr_rand_next" in src and "ef_rand_rank" in src
          and "ef_rand_valid" in src and "ef_pitch_rank" in tonal
          and "ef_pitch_rank:" in src)
    chord_table = block(src, "ef_chord_shapes:", "ef_scale_masks:")
    chord_names = block(src, "ef_chord_names:", "ef_scale_masks:")
    check("MIDI VOIC uses all 31 FM SYNTH chord shapes",
          len(re.findall(r"CH_[A-Z0-9]+", chord_names)) == 31
          and "ef_chord_shapes" in src and "ef_tone_style" in block(src, "ef_midi_chord_locks:", "ef_midi_clear_chord_locks:")
          and "0,10,14,4" in chord_table)
    check("MIDI VOIC 1 clears NOT2..NOT4 and higher counts write shape tones",
          "bsr.w   ef_midi_chord_locks" in block(src, "ewmp_arp:", "ef_midi_chord_locks:")
          and "ef_tone_harm" in block(src, "ef_midi_chord_locks:", "ef_midi_clear_chord_locks:")
          and "moveq   #-1,%d0" in block(src, "ef_midi_chord_locks:", "ef_midi_clear_chord_locks:"))
    check("MIDI pitch and chord helpers preserve the fill pulse count",
          "movem.l %d4-%d7,%sp@" in tonal
          and "movem.l %sp@,%d4-%d7" in tonal
          and "movel   %d4,-(%sp)" in chord
          and "movel   (%sp)+,%d4" in chord
          and "movel   %d4,-(%sp)" in chord_clear
          and "movel   (%sp)+,%d4" in chord_clear)
    check("audio pitch ignores MIDI-only harmony and mode settings",
          "ef_tone_harm" not in ptch
          and "ef_tone_mode" not in block(src, "ef_pitch_rank:", "ef_snap_note:"))
    check("tonal settings persist per audio and MIDI track with v11 PHRS migration",
          "EF_TONE_B, 16*EF_TONE_REC" in src
          and "EF_VER,    11" in src and "ef_tone_addr:" in src
          and "addil   #8,%d0" in block(src, "ef_tone_addr:", "ef_tone_save:")
          and "el_v8:" in src and "TON_STYLE" in block(src, "el_v8:", "el_v7:")
          and "el_v9:" in src and "clrb    %a0@(TON_JUMP)" in block(src, "el_v9:", "el_v8:")
          and "bsr.w   ef_tone_phrase_v10_to_v11" in block(src, "el_v9:", "el_v10:")
          and "el_v10:" in src
          and "bsr.w   ef_tone_phrase_v10_to_v11" in block(src, "el_v10:", "el_v8:")
          and "moveq   #15,%d0" in block(src, "ef_tone_phrase_v10_to_v11:", "ef_store_slot:"))
    check("RAND is the first PHRS option and the default value",
          ".long P_RAND,P_UP,P_DOWN,P_ALT,P_TRI" in src
          and "clrb    %a0@(TON_PHRASE)" in block(src, "ef_tone_defaults:", "ef_tone_phrase_v10_to_v11:")
          and "ef_tone_phrase:.long 0" in src)
    check("32-bit working values save their low byte to the tonal record",
          all(f"movel   ef_tone_{field},%d1" in save
              for field in ("scale", "root", "mode", "jump", "phrase", "harm", "style")))
    check("audio scale generation has no SCALE QUANTIZER address dependency",
          "SCALE_AT" not in ptch and "NV_ROOT" not in ptch
          and "NV_SCALE" not in ptch)

    print(f"SEQ tonal: {FAILS} failed checks")
    return FAILS


if __name__ == "__main__":
    sys.exit(main())
