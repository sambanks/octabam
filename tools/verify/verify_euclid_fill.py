#!/usr/bin/env python3
"""EUCLID FILL: Euclidean bit patterns + UI contract (fast, no port).

Math matches modules/euclid/control.c. UI checks audit euclid_fill.s so the
popup keeps filter-EUCLID names (PULSE / ROT) plus LANE / DEST / DEPTH,
length in the title, stock 3x2 dotted grid (A/B/C/D/E filled; F empty),
LEVEL noop; arrows unbound (no invert), and the key layer.
"""

from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "tools")]

SRC = ROOT / "modules/euclid-fill/euclid_fill.s"

FAILS = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global FAILS
    if ok:
        print(f"  [PASS] {name}" + (f" ({detail})" if detail else ""))
    else:
        FAILS += 1
        print(f"  [FAIL] {name}" + (f": {detail}" if detail else ""))


def eu_pulse(i: int, n: int, k: int) -> bool:
    """Same law as modules/euclid/control.c eu_pulse."""
    return bool(k and (i * k) % n < k)


def pattern(n: int, k: int, rot: int = 0) -> list[int]:
    out = []
    for i in range(n):
        idx = (i + n - (rot % n)) % n
        out.append(1 if eu_pulse(idx, n, k) else 0)
    return out


def depth_range(depth: int, base: int = 64) -> tuple[int, int]:
    """Generic DEST lock window: [Part-DEPTH .. Part+DEPTH] clamped 0..127."""
    lo = max(0, base - depth)
    hi = min(127, base + depth)
    return lo, hi


def depth_lock(depth: int, r: int, base: int = 64) -> int:
    """Uniform pick: lo + (r % span). r is any non-neg int (simulates remul)."""
    lo, hi = depth_range(depth, base)
    span = hi - lo + 1
    return lo + (r % span)


def vol_lock(depth: int, r: int, part_vol: int = 100) -> int:
    """AMP VOL: Part - r*DEPTH/127, clamp >= 0 (never above Part)."""
    drop = (r * depth) // 127
    return max(0, part_vol - drop)


class CueHang(Exception):
    """cwalk walked past n — the hardware hang when remul's divisor is wrong."""


def lcg(state: int) -> tuple[int, int]:
    """Numerical Recipes LCG matching ef_rng (same constants as RND NAME)."""
    if state == 0:
        state = 1
    state = (1664525 * state + 1013904223) & 0xFFFFFFFF
    return state, state


def cue_ksubset(
    n: int,
    k: int,
    seed: int = 1,
    *,
    clobber_d1: bool = False,
    mul_const: int = 1664525,
) -> list[int]:
    """Simulate ef_cue's uniform k-subset fill of n steps.

    clobber_d1=True models the bug: ef_rng leaves d1=mul_const and remul
    uses that as the free-count divisor, so the rank is usually unreachable
    and cwalk spins past n (YES-style hang on the unit).
    """
    if k < 0 or k > n or n < 1:
        raise ValueError(f"bad n={n} k={k}")
    mask = [0] * n
    state = seed
    placed = 0
    while placed < k:
        free = n - placed
        state, r = lcg(state)
        divisor = mul_const if clobber_d1 else free
        if divisor <= 0:
            raise CueHang(f"divisor {divisor} at placed={placed}")
        rank = r % divisor
        step = 0
        seen = 0
        while True:
            if step >= n:
                raise CueHang(
                    f"cwalk past n={n} rank={rank} free={free} "
                    f"divisor={divisor} placed={placed}"
                )
            if mask[step] == 0:
                if seen == rank:
                    mask[step] = 1
                    break
                seen += 1
            step += 1
        placed += 1
    return mask


def pitch_rad(depth: int, max_rad: int) -> int:
    """DEST=PTCH range: rad = max(1, max_rad*DEPTH/127) when DEPTH>0."""
    if depth <= 0:
        return 0
    return max(1, (max_rad * depth) // 127)


def pitch_candidates(
    rad: int, root: int, mask: int, *, base_st: int = 0
) -> list[int]:
    """Absolute st = base_st+delta for delta in [-rad..+rad] on-scale.

    PC = (root + st) mod 12. base_st is the Part PLAYBACK PTCH decoded to
    semitones (overall knob); 0 = unison / raw 64.
    """
    out: list[int] = []
    for delta in range(-rad, rad + 1):
        st = base_st + delta
        pc = (root + st) % 12
        if mask & (1 << pc):
            out.append(st)
    return out


def decode_ptch(raw: int, *, synth: bool) -> int:
    """Part/lock PTCH raw -> semitones (synth 64+st, sample 64+5·st)."""
    if synth:
        return raw - 64
    return (raw - 64) // 5


def encode_ptch(st: int, *, synth: bool) -> int:
    """PTCH lock byte after the 0..127 clamp."""
    raw = (64 + st) if synth else (64 + 5 * st)
    return max(0, min(127, raw))


def _block(src: str, start: str, end: str | None = None) -> str:
    i = src.find(start)
    if i < 0:
        return ""
    j = src.find(end, i + len(start)) if end else len(src)
    if j < 0:
        j = len(src)
    return src[i:j]


def check_ui(src: str) -> None:
    print("UI contract (euclid_fill.s):")

    for lab, text in (
        ("L_LEN", "LEN"),
        ("L_PULSES", "PULS"),
        ("L_ROT", "ROT"),
        ("L_LANE", "LANE"),
        ("L_TRIG", "TRIG"),
        ("L_PLOCK", "PLCK"),
        ("L_DEPTH", "DPTH"),
    ):
        m = re.search(rf"{lab}:\s*\.asciz\s+\"([^\"]*)\"", src)
        check(f"label {lab}", m is not None and m.group(1) == text,
              m.group(1) if m else "missing")
    check("no STEPS caption (LEN lives in the left gutter)",
          "L_STEPS" not in src and '.asciz "STEPS"' not in src)
    check("LEN stacked bottom-right after squares (no 1-16)",
          "L_LEN" in _block(src, "ef_draw:", "d9:")
          and "X_LEN_R" in _block(src, "ef_draw:", "d9:")
          and "Y_LEN_LAB" in _block(src, "ef_draw:", "d9:")
          and "Y_LEN_VAL" in _block(src, "ef_draw:", "d9:")
          and "ef_rtext" in _block(src, "ef_draw:", "d9:")
          and "FMT_LEN" not in src and "Y_FOOT" not in src
          and "ef_fmt_view" not in src
          and "X_VIEW_R" not in _block(src, "ef_draw:", "d9:"))
    check("EUCLID title top-left next to icon",
          "T_TITLE" in _block(src, "ef_draw:", "d9:")
          and "Y_TITLE" in _block(src, "ef_draw:", "d9:")
          and "X_TITLE" in _block(src, "ef_draw:", "d9:")
          and "ef_text" in _block(src, "ef_draw:", "d9:"))
    check("no ROTATION string", "ROTATION" not in src)
    check("no RAND VEL/PTCH labels",
          "RAND VEL" not in src and "RAND PTCH" not in src)

    # Panel strings: plain ASCII only. No invented unicode arrows/blocks.
    panel = re.findall(r"\.asciz\s+\"([^\"]*)\"", src)
    for s in panel:
        check(f"asciz ASCII {s!r}", s.isascii() and all(32 <= ord(c) <= 126 for c in s))
    check("no invented '>' caret (T_MARK gone)",
          "T_MARK" not in src and '.asciz ">"' not in src)
    check("no invert / cursor highlight",
          "INVERT" not in src and "X_INV" not in src
          and re.search(r"pea\s+-1", _block(src, "ef_draw:", "ef_fill:")) is None)
    check("no stock ARRUP/ARRDN icons (this window has no arrow legend)",
          "ARRUP" not in src and "ARRDN" not in src and "0x400b9d8c" not in src)

    # Arrow / nav keys: omit from EF_KEYS entirely. A 0 swallows; a -1
    # record still writes aux/sub-map 0 and can break DOWN after
    # Euclid → PROJECT. TEMPO BUS must still own the arrow codes.
    tb = (ROOT / "modules/tempo-bus/tempobus.s").read_text()
    tb_keys = re.search(r"TB_KEYS:(.*?)TB_ENCS:", tb, re.S)
    assert tb_keys, "TEMPO BUS key table missing"
    ef_keys = _block(src, "EF_KEYS:", "EF_ENCS:")
    for code, name in (("0x33", "UP"), ("0x20", "DOWN"), ("0x34", "LEFT"), ("0x21", "RIGHT")):
        check(f"arrow {name} {code} in TEMPO BUS",
              code in tb_keys.group(1))
        check(f"arrow {name} {code} unbound in EF_KEYS",
              not re.search(rf"\.byte\s+{code},", ef_keys))
    for code, name in (("0x1c", "PROJ"), ("0x1d", "PART"),
                       ("0x1e", "AED"), ("0x1f", "ARR")):
        check(f"nav {name} {code} unbound in EF_KEYS",
              not re.search(rf"\.byte\s+{code},", ef_keys))
    check("ef_layer_on LPOP on close (orphan layer)",
          "ef_layer_on" in _block(src, "ef_close:", "ef_no:")
          and "LPOP" in _block(src, "ef_close:", "ef_no:")
          and "ef_layer_on:" in src)

    pat_w = 16 * 4 + 15 * 1 + 3 * 3
    for name, val in (
        ("WINW", 109), ("WINH", 64), ("WINX", 0),
        ("CELL_W", 0x14), ("ROW_PITCH", 0x1b),
        ("X_GRID", 109 - 1 - 3 * 0x14),
        ("X_C0", (109 - 1 - 3 * 0x14) + 0x14 // 2),
        ("X_C1", (109 - 1 - 3 * 0x14) + 0x14 + 0x14 // 2),
        ("PAT_COLS", 16), ("PAT_ROWS", 4),
        ("PAT_SQ", 4), ("PAT_GAP", 1), ("PAT_SEP", 3), ("PAT_STRIDE", 5),
        ("PAT_W", pat_w), ("Y_PATT", 22),
        ("ICON_W", 29), ("ICON_H", 29),
        ("X_LEN_R", 109 - 2), ("Y_LEN_LAB", 14), ("Y_LEN_VAL", 5),
        ("X_PAT", 2),
        ("Y_LAB0", 0x38), ("Y_VAL0", 0x2f), ("Y_GMID", 0x2b),
        ("Y_LAB1", 0x24), ("Y_VAL1", 0x1e),
        ("Y_DEST_P", 0x24),
        ("Y_DEST_V", 0x24 - (0x38 - 0x2f)),
        ("Y_DEPTH_V", 0x24 - (0x38 - 0x2f)),
        ("Y_GRID1", 64 - 2),
        ("Y_GRID0", 23),
        ("LOCK0", 0x59), ("LOCK_STEP", 32), ("LOCK_VOL", 15), ("LOCK_PTCH", 0),
    ):
        m = re.search(rf"\.set\s+{name},\s*(.+)", src)
        if not m:
            check(f"layout {name}={val}", False, "missing")
            continue
        expr = m.group(1).split("|")[0].strip()
        env = {
            "WINW": 109, "WINH": 64, "CELL_W": 0x14, "ROW_PITCH": 0x1b,
            "X_GRID": 109 - 1 - 3 * 0x14,
            "Y_LAB0": 0x38, "Y_VAL0": 0x2f,
            "Y_LAB1": 0x24, "Y_VAL1": 0x1e,
            "Y_GMID": 0x2b, "Y_GRID1": 62, "Y_GRID0": 23,
            "PAT_SQ": 4, "PAT_GAP": 1, "PAT_SEP": 3, "PAT_COLS": 16,
            "PAT_W": pat_w,
        }
        try:
            got = int(eval(expr.replace("/", "//"), {"__builtins__": {}}, env))
        except Exception:
            try:
                got = int(expr, 0)
            except Exception:
                got = None
        check(f"layout {name}={val}", got == val, str(got) if got is not None else expr)
    check("stock dotted grid via HLINE 0x40012004",
          re.search(r"\.set\s+HLINE,\s*0x40012004", src) is not None
          and "EF_GRID:" in src and "jsr     HLINE" in src)
    check("ef_ctext centers on cell x",
          "ef_ctext:" in src and "asrl    #1" in _block(src, "ef_ctext:", "ef_grid:"))

    check("default ef_pulses=5",
          re.search(r"ef_pulses:\s*\.long\s+5\b", src) is not None)
    check("default ef_rot=0",
          re.search(r"ef_rot:\s*\.long\s+0\b", src) is not None)
    check("default ef_steps=16",
          re.search(r"ef_steps:\s*\.long\s+16\b", src) is not None)
    check("default ef_dest=LOCK_VOL",
          re.search(r"ef_dest:\s*\.long\s+LOCK_VOL\b", src) is not None)
    check("default ef_depth=0",
          re.search(r"ef_depth:\s*\.long\s+0\b", src) is not None)

    check("per-track bank SLOT_B=28",
          re.search(r"\.set\s+SLOT_B,\s*28\b", src) is not None)
    check("ef_bank has 8 slots",
          re.search(r"ef_bank:\s*\n\s*\.rept\s+8\b", src) is not None)
    check("per-DEST depth + plock tables + euclid.work v4",
          "ef_dep_mem:" in src and "ef_dep_load:" in src and "ef_dep_save:" in src
          and "ef_plk_mem:" in src and "ef_plk_load:" in src and "ef_plk_save:" in src
          and "ef_lane_mem:" in src and "ef_lane_load:" in src and "ef_lane_save:" in src
          and "ef_plk_expand_v3:" in src
          and re.search(r"\.set\s+EF_VER,\s*4\b", src) is not None
          and re.search(r"\.set\s+EF_PLK_SLOT,\s*12\b", src) is not None
          and "EF_FILE_B" in _block(src, "ef_write_due:", "ef_load_file:")
          and "ef_dep_load" in _block(src, "ef_nudge:", "ef_nudge_rts:")
          and "ef_plk_load" in _block(src, "ef_nudge:", "ef_nudge_rts:")
          and "ef_lane_save" in _block(src, "ef_nudge:", "ef_nudge_rts:")
          and "ef_dep_save" in _block(src, "ef_fill:", "ef_drop_clr_undo:")
          and "ef_plk_save" in _block(src, "ef_fill:", "ef_drop_clr_undo:")
          and "ef_dep_mem" in _block(src, "ef_defaults:", "ef_copy_file:")
          and "EF_PLK_B" in _block(src, "ef_defaults:", "ef_copy_file:")
          and "EF_LANE_B" in _block(src, "ef_defaults:", "ef_copy_file:"))
    check("ef_bank defaults DEST=LOCK_VOL",
          re.search(r"ef_bank:.*?\.long\s+5,\s*0,\s*LOCK_VOL,\s*0,\s*0",
                    src, re.S) is not None)
    check("ef_store_slot / ef_load_slot present",
          "ef_store_slot:" in src and "ef_load_slot:" in src)
    check("ef_store_slot saves dest/depth",
          "ef_dest" in _block(src, "ef_store_slot:", "ef_load_slot:")
          and "ef_depth" in _block(src, "ef_store_slot:", "ef_load_slot:"))
    # ColdFire 5407: no memory-to-memory move.l (illegal insn on open).
    store = _block(src, "ef_store_slot:", "ef_load_slot:")
    load = _block(src, "ef_load_slot:", "ef_follow_ui:")
    check("ef_store_slot stages longs through d1 (no mem-to-mem)",
          re.search(r"movel\s+ef_pulses,%a0@\+", store) is None
          and re.search(r"movel\s+ef_pulses,%d1", store) is not None
          and re.search(r"movel\s+%d1,%a0@\+", store) is not None)
    check("ef_load_slot stages longs through d1 (no mem-to-mem)",
          re.search(r"movel\s+%a0@\+,ef_pulses", load) is None
          and re.search(r"movel\s+%a0@\+,%d1", load) is not None
          and re.search(r"movel\s+%d1,ef_pulses", load) is not None)
    # Object-level: refuse MOVE.L (An)+,(xxx).L (0x23d8) in the packed unit.
    ef_objs = sorted((ROOT / "out/platform/runtime").glob("*_ef.o"))
    if ef_objs:
        newest = max(ef_objs, key=lambda p: p.stat().st_mtime)
        blob = newest.read_bytes()
        # after adda to bank: must stage via Dn (2218), never 23d8 mem-to-mem
        check(f"assembled {newest.name}: no load mem-to-mem 23d8",
              bytes.fromhex("23d8") not in blob,
              f"23d8 at {blob.find(bytes.fromhex('23d8'))}")
        check(f"assembled {newest.name}: load stages via d1 (2218)",
              bytes.fromhex("2218") in blob)
    else:
        print("  [ -- ] assembled ef.o absent (skip mem-to-mem opcode check)")
    check("ef_follow_ui avoids CUR_TRACK (HW brick; pending/UI_TRACK only)",
          "ef_follow_ui:" in src
          and "CUR_TRACK" not in _block(src, "ef_follow_ui:", "ef_sync_len:")
          and "UI_TRACK" in _block(src, "ef_follow_ui:", "ef_sync_len:"))
    draw_head = src[src.find("ef_draw:"): src.find("ef_draw:") + 400]
    check("ef_draw calls ef_follow_ui", "ef_follow_ui" in draw_head)
    check("ef_open avoids CUR_TRACK",
          "CUR_TRACK" not in _block(src, "ef_open:", "ef_first_target:"))
    check("ef_open focuses first HELD track (ef_first_target)",
          "ef_first_target" in _block(src, "ef_open:", "ef_first_target:"))
    check("ef_open calls SEL_TRACK for sequencer view",
          "SEL_TRACK" in _block(src, "ef_open:", "ef_first_target:"))
    check("draw shows LEN / n bottom-right via ef_rtext",
          "L_LEN" in _block(src, "ef_draw:", "d9:")
          and "X_LEN_R" in _block(src, "ef_draw:", "d9:")
          and "ef_rtext" in _block(src, "ef_draw:", "d9:")
          and "FMT_LEN" not in src and "Y_FOOT" not in src)
    check("ef_nudge write-through stores slot",
          "ef_store_slot" in _block(src, "ef_nudge:", "ef_nudge_rts:"))
    check("ef_fill loads per-target slot",
          "ef_load_slot" in _block(src, "ef_fill:", "ef_write_mask:"))

    for site in ("ef_open", "ef_draw", "ef_fill", "ef_nudge"):
        i = src.find(f"{site}:")
        check(f"{site} calls ef_sync_len",
              i >= 0 and "ef_sync_len" in src[i:i + 2800])

    nudge = _block(src, "ef_nudge:", "ef_nudge_rts:")
    check("PULSE/ROT gate through ef_rhythm_gate when baked",
          "ef_rhythm_gate" in nudge and "ARE YOU SURE?" in src)
    check("CUE gates through ef_rhythm_gate when baked",
          "ef_rhythm_gate" in _block(src, "ef_cue:", "cue_go:"))
    check("ARE YOU SURE? stock DIALOG; YES unlocks only; soft-restore",
          "DIALOG" in src and "ef_dlg_answer" in src and "ef_unlocked" in src
          and "ef_dlg_guard" in src and "ef_need_restore" in src
          and "ef_mkwin" in src
          and "ARE YOU SURE?" in src
          and "EXISTING TRIGS IN THE PATTERN" in src
          and "WILL BE CLEARED ON NEXT FILL" in src
          and "YES: UNLOCK" not in src and "NO: CANCEL" not in src
          and "ef_clr_trigs" not in src
          and "ef_soft_layer" not in src)
    close = _block(src, "ef_close:", "ef_no:")
    soft = re.search(
        r"tstl\s+ef_dlg_guard\s*\n\s*beq\.s\s+close_nosoft\n(.*?)close_nosoft:",
        close, re.S)
    check("soft dialog keeps EF_LAYER (knobs stay on ef_ask); user LPOP",
          soft is not None
          and "WDESTROY" in soft.group(1)
          and "ef_need_restore" in soft.group(1)
          and "LPOP" not in soft.group(1)
          and "soft_rts" in soft.group(1)
          and "close_orphan" in close
          and "ef_layer_on" in close and "LPOP" in close
          and "LPUSH" in _block(src, "ef_mkwin:", "mkw_rts:")
          and "ef_soft_layer" not in src)
    check("A–D / L/R dead while dialog (ef_ask) is up",
          "ef_ask" in _block(src, "ef_enc:", "ef_level:")
          and "ef_ask" in _block(src, "ef_nudge:", "nudge_go:"))
    check("ef_trk_baked scans mask 0 via ef_bit_addr",
          "ef_bit_addr" in _block(src, "ef_trk_baked:", "ef_seed_from_trk:"))
    check("ef_pull_mask reads TRAC via ef_bit_addr into ef_mask",
          "ef_pull_mask:" in src
          and "ef_bit_addr" in _block(src, "ef_pull_mask:", "ef_seed_from_trk:")
          and "ef_mask" in _block(src, "ef_pull_mask:", "ef_seed_from_trk:"))
    check("ef_seed_from_trk uses pull and sets free",
          "bsr.w   ef_pull_mask" in _block(src, "ef_seed_from_trk:", "EF_LAYER:")
          and "ef_free" in _block(src, "ef_seed_from_trk:", "EF_LAYER:"))
    check("open seeds grid from track after sync_len",
          "bsr.w   ef_seed_from_trk" in _block(src, "ef_open:", "ef_mkwin:")
          and "bsr.w   ef_store_slot" in _block(src, "ef_open:", "ef_mkwin:"))
    check("follow_ui seeds grid when retargeting",
          "bsr.w   ef_seed_from_trk" in _block(src, "ef_follow_ui:", "fu_rts:"))
    check("no live pad sync (no TRIG_DISP / soft timer / cell_lit)",
          "TRIG_DISP" not in src and "ef_trigkey" not in src
          and "ef_cell_lit" not in src and "ef_poll_trigs" not in src
          and "ef_arm_timer" not in src and "TIMER" not in src
          and ".byte   0x00, 0" not in _block(src, "EF_KEYS:", "EF_ENCS:"))
    check("draw_pat uses bake/preview ef_hit",
          "bsr.w   ef_hit" in _block(src, "ploop:", "phollow:"))
    check("NO still closes",
          ".byte   0x32, 0" in _block(src, "EF_KEYS:", "EF_ENCS:")
          and "ef_no" in _block(src, "EF_KEYS:", "EF_ENCS:")
          and "bra.w   ef_close" in _block(src, "ef_no:", "ef_yes:"))
    check("ef_nudge edits PULSE/ROT/DEST/DEPTH",
          "lea     ef_pulses" in nudge and "lea     ef_rot" in nudge
          and "lea     ef_dest" in nudge and "lea     ef_depth" in nudge
          and "lea     ef_steps" not in nudge)
    check("ef_nudge parks delta across ef_sync_len",
          re.search(
              r"movel\s+%d0,-\(%sp\).*?bsr\.w\s+ef_sync_len.*?movel\s+\(%sp\)\+,%d2",
              nudge, re.S) is not None)
    check("editing PULSE clears ef_free", "clrl    ef_free" in nudge)
    check("DEST clamps via ef_dest_max and skips XVOL (17)",
          "ef_dest_max" in nudge and "DEST_XVOL" in nudge
          and re.search(r"moveq\s+#18,%d0", nudge) is not None
          and re.search(r"moveq\s+#16,%d0", nudge) is not None)
    check("DEPTH clamps to 127",
          re.search(r"moveq\s+#127,%d3", nudge) is not None)

    # LEVEL encoder noop; arrows omitted from EF_KEYS (no local handlers).
    level = _block(src, "ef_level:", "ef_nudge:")
    check("ef_level is noop",
          re.search(r"ef_level:\s*\n\s*rts\b", src) is not None
          and "ef_nudge" not in level)
    check("no local arrow handlers / pat scroll",
          "ef_up:" not in src and "ef_down:" not in src
          and "ef_left:" not in src and "ef_right:" not in src
          and "ef_pat_scroll" not in src)
    draw_pat = _block(src, "ef_draw_pat:", "ef_fill:")
    check("pattern draws 4x16 top-left centered squares; SEP gap, no ticks",
          "PAT_COLS" in draw_pat
          and "PAT_SQ" in draw_pat
          and "Y_PATT" in draw_pat
          and "PAT_SEP" in draw_pat
          and "ef_box1:" in src
          and "ef_px1" in draw_pat
          and "pmark:" not in draw_pat
          and "pea     0" not in draw_pat
          and "ef_pat_off" not in draw_pat
          and "PAT_VIEW" not in src)
    check("ef_sync_len clears ef_pat_off",
          "ef_pat_off" in _block(src, "ef_sync_len:", "ef_close:"))
    check("ef_open clears ef_pat_off",
          "ef_pat_off" in _block(src, "ef_open:", "ef_mkwin:"))

    keys = _block(src, "EF_KEYS:", "EF_ENCS:")
    page = _block(src, "ef_page:", "ef_open:")
    check("PAGE 0x1b unbound; bare PAGE stock; TRACK+PAGE toggles",
          not re.search(r"\.byte\s+0x1b,", keys)
          and "ef_page:" in src
          and "HELD" in page
          and "ef_close" in page
          and "ef_open" in page
          and "PAGE_GO" in page
          and "any PAGE press closes" not in src)

    for code, handler in (
        ("0x31", "ef_yes"),
        ("0x32", "ef_no"),
        ("0x2a", "ef_cue"),
        ("0x10", "ef_trkkey"),
        ("0x17", "ef_trkkey"),
    ):
        check(f"key {code} -> {handler}",
              re.search(rf"\.byte\s+{code},.*?\n\s*\.long\s+{handler}\b", keys, re.S)
              is not None)
    check("ef_trkkey stashes ef_pending (no load/store on key path)",
          "ef_trkkey:" in src
          and "ef_pending" in _block(src, "ef_trkkey:", "ef_dest_label:")
          and "ef_load_slot" not in _block(src, "ef_trkkey:", "ef_dest_label:"))
    check("ef_trkkey calls stock SEL_TRACK (sequencer view)",
          ("0x40083bf8" in _block(src, "ef_trkkey:", "ef_dest_label:")
           or "SEL_TRACK" in _block(src, "ef_trkkey:", "ef_dest_label:")))
    check("ef_store_slot marks ef_dirty for euclid.work",
          "ef_dirty" in _block(src, "ef_store_slot:", "ef_load_slot:"))
    check("STORE handlers persist ef_bank",
          "ef_st_pstore_pre:" in src and "ef_write_due" in src
          and "ef_st_loadall_post:" in src and "ef_load_file" in src
          and "euclid.work" in src)
    check("ef_follow_ui applies ef_pending then load_slot",
          "ef_pending" in _block(src, "ef_follow_ui:", "ef_sync_len:")
          and "ef_load_slot" in _block(src, "ef_follow_ui:", "ef_sync_len:"))

    cue = _block(src, "ef_cue:", "ef_rng:")
    check("ef_cue fills focused mask", "ef_mask" in cue and "ef_pmask" in cue)
    check("ef_cue sets focused free", "ef_free" in cue and "ef_pfree" in cue)
    check("ef_cue uses LCG (ef_rng)", "ef_rng" in cue)
    check("ef_cue respects ef_pulses (k-subset)",
          "ef_pulses" in cue and "clrl    ef_pulses" not in cue)
    check("ef_hit serves free + Euclid",
          "ef_hit:" in src and "ef_free" in _block(src, "ef_hit:", "ef_enc:"))

    encs = _block(src, "EF_ENCS:", "T_TITLE:")
    check("encoder A (0) -> ef_enc",
          re.search(r"\.byte\s+0,\s*0[^\n]*\n\s*\.long\s+ef_enc\b", encs) is not None)
    check("encoder B (1) -> ef_enc",
          re.search(r"\.byte\s+1,\s*0[^\n]*\n\s*\.long\s+ef_enc\b", encs) is not None)
    check("encoder C (2) -> ef_enc (LANE)",
          re.search(r"\.byte\s+2,\s*0[^\n]*\n\s*\.long\s+ef_enc\b", encs) is not None
          and "L_LANE" in src and "ef_lane:" in src)
    check("encoder D (3) -> ef_enc",
          re.search(r"\.byte\s+3,\s*0[^\n]*\n\s*\.long\s+ef_enc\b", encs) is not None)
    check("encoder E (4) -> ef_enc",
          re.search(r"\.byte\s+4,\s*0[^\n]*\n\s*\.long\s+ef_enc\b", encs) is not None)
    check("encoder F (5) -> ef_enc (noop empty)",
          re.search(r"\.byte\s+5,\s*0[^\n]*\n\s*\.long\s+ef_enc\b", encs) is not None)
    check("encoder LEVEL (6) -> ef_level",
          re.search(r"\.byte\s+6,\s*0[^\n]*\n\s*\.long\s+ef_level\b", encs) is not None)
    enc = _block(src, "ef_enc:", "ef_level:")
    check("ef_enc rejects F only (C=LANE)",
          re.search(r"moveq\s+#5,%d0", enc) is not None
          and "C empty" not in enc)
    check("ef_enc keeps A..E as cursor 0..4 (no D/E remap)",
          "subql   #1,%d1" not in enc and "subql\t#1,%d1" not in enc
          and "ef_cursor" in enc)

    draw = _block(src, "ef_draw:", "d9:")
    for lab in ("L_PULSES", "L_ROT", "L_DEPTH"):
        check(f"draw uses {lab}", f"lea     {lab}" in draw or f"lea\t{lab}" in draw)
    check("draw is mid-gutter icon + bottom-right LEN + right 3x2 (C=LANE)",
          "X_LEN_R" in draw and "Y_LEN_LAB" in draw and "Y_LEN_VAL" in draw
          and "ef_draw_icon" in draw
          and "X_C0" in draw and "X_C1" in draw and "X_C2" in draw
          and "L_LANE" in draw and "L_TRIG" in draw and "L_PLOCK" in draw
          and "Y_LAB0" in draw and "Y_VAL0" in draw
          and "ef_ctext" in draw and "ef_grid" in draw
          and "ef_draw_pat" in draw
          and "WINX" in src)
    check("grid has 1px top+bottom RULE + left VLINE + divs + mid + floor",
          "VLINE" in _block(src, "ef_grid:", "ef_fmt_track:")
          and "moveq   #3,%d2" in _block(src, "ef_grid:", "ef_fmt_track:")
          and _block(src, "ef_grid:", "ef_fmt_track:").count("jsr     RULE") >= 3
          and "WINH-1" in _block(src, "ef_grid:", "ef_fmt_track:")
          and re.search(r"\.set\s+VLINE,\s*0x40011b94", src) is not None)
    mkw = _block(src, "ef_mkwin:", "mkw_rts:")
    check("window parked left (WINX=0, WINW=109) so T5-8 keep ~19px",
          re.search(r"\.set\s+WINX,\s*0\b", src) is not None
          and re.search(r"\.set\s+WINW,\s*109\b", src) is not None
          and mkw.count("clrl    %sp@-") >= 2
          and "jsr     WFRAME" not in mkw)

    check("LANE + plock free/mask persist via lane_mem / 12-byte plk slots",
          "ef_lane_load" in _block(src, "ef_load_slot:", "ef_dep_ptr:")
          and "ef_pfree" in _block(src, "ef_plk_load:", "ef_plk_save:")
          and "ef_pmask" in _block(src, "ef_plk_save:", "ef_lane_load:")
          and "el_v3:" in src)
    check("window title stays EUCLID regardless of LANE",
          re.search(r"lea\s+T_TITLE,%a0\s*\n\s*bsr\.w\s+ef_text", _block(src, "ef_draw:", "L_LEN")) is not None
          and "L_PLOCK" not in _block(src, "bsr.w   ef_draw_icon", "L_LEN"))
    check("focused LANE: A/B edit TRIG or PLOCK; grid follows ef_lane",
          "ef_lane" in _block(src, "ef_nudge:", "ef_nudge_rts:")
          and "ef_ppulses" in _block(src, "ef_nudge:", "ef_nudge_rts:")
          and "ef_phit" in _block(src, "ef_draw_pat:", "ef_fill:")
          and "ef_hit" in _block(src, "ef_draw_pat:", "ef_fill:"))
    check("YES writes trigless-lock mask (+0x10) on plock-only steps",
          "MASK_TL" in src and "ef_tl_set:" in src and "ef_tl_clr:" in src
          and "ef_tl_set" in _block(src, "ef_write_mask:", "ef_write_dest:")
          and "ef_phit" in _block(src, "ef_write_mask:", "ef_write_dest:")
          and "ef_plock_on" in _block(src, "ef_write_mask:", "ef_write_dest:"))
    check("LANE=TRIG: DEST on thit + plock recipe sync (ef_plk_save)",
          "wm_tclr:" in src
          and "ef_plk_save" in _block(src, "ef_write_mask:", "ef_tl_bit_addr:")
          and "ef_ppulses" in _block(src, "9:", "ef_tl_bit_addr:"))
    check("LANE=PLOCK: independent trigless via wm_plock / ef_tl_set",
          "wm_plock:" in _block(src, "ef_write_mask:", "ef_tl_bit_addr:")
          and "ef_tl_set" in _block(src, "wm_tl:", "wm_miss:")
          and "ef_phit" in _block(src, "wm_plock:", "wm_miss:"))
    check("PULSE0 / dest-clear drops orphan TL (ef_tl_reconcile, stack-safe)",
          "ef_tl_reconcile:" in src
          and "ef_tl_reconcile" in _block(src, "wm_mtl:", "9:")
          and "ef_cx_bits" in _block(src, "ef_tl_reconcile:", "ef_write_dest:")
          and "DEST_LAST" in _block(src, "ef_tl_reconcile:", "ef_write_dest:"))
    check("LANE switch re-seeds live sample trigs into TRIG grid",
          "ef_seed_from_trk" in _block(src, "ln1:", "nd_ab:"))
    check("draw empty-live drift drops stale free mask",
          "ef_mask_drift" in _block(src, "ef_draw:", "ef_draw_pat:")
          and "ef_mask_drift:" in src
          and "sf_empty:" in src)
    check("PTCH carry on bare note trigs after plock miss",
          "ef_ptch_carry" in _block(src, "ef_write_mask:", "ef_write_dest:")
          and "ef_part_ptch" in _block(src, "ef_write_mask:", "ef_write_dest:"))
    check("D/E live regardless of LANE (no auto-switch)",
          "ef_dep_load" in _block(src, "ef_nudge:", "ef_nudge_rts:")
          and "ef_lane" in _block(src, "ef_nudge:", "ef_nudge_rts:"))
    check("DEPTH value uses Y_DEPTH_V + ef_ctext (same gap as PULS/ROT)",
          "Y_DEPTH_V" in draw and "ef_ctext" in draw)
    check("Euclid icon blit above LEN (ef_draw_icon)",
          "ef_draw_icon" in draw
          and "ef_icon_bmp:" in src
          and re.search(r"\.set\s+BLIT,\s*0x400128a8", src) is not None
          and "ICON_X" in src and "ICON_Y" in src)
    check("DEST cell is PAGE/PARAM aligned with DEPTH (no PMTR caption)",
          "bsr.w   ef_dest_label" in draw
          and "df_skip:" in draw
          and "Y_DEST_P" in draw and "Y_DEST_V" in draw
          and "lea     L_DEST" not in draw
          and "Y_DEST_L" not in src
          and 'asciz "PMTR"' not in src)
    check("DEST uses ef_dest_label (PAGE\\0PARAM\\0)",
          "bsr.w   ef_dest_label" in draw
          and "ef_dest_name" in _block(src, "ef_dest_label:", "ef_draw_pat:")
          and "TITLE_OFF" in src and "ef_dpage_tab" in src and "ef_dparam_tab" in src
          and "clrb" in _block(src, "dn_sp:", "dn_cp:")
          and "0x20" not in _block(src, "dn_sp:", "dn_cp:"))
    check("ef_dest_label preserves d2/d3 (draw row)",
          "movel   %d2,-(%sp)" in _block(src, "ef_dest_label:", "ef_draw_pat:")
          and "movel   (%sp)+,%d2" in _block(src, "ef_dest_label:", "ef_draw_pat:"))
    check("PLAYBACK DEST names via page resolver (same as LFO PMTR)",
          "LFD_RESOLVER" in _block(src, "ef_dest_name:", "ef_is_synth:")
          and "FLEX_P" in _block(src, "ef_dest_name:", "ef_is_synth:")
          and "TITLE_OFF" in _block(src, "dn_got:", "dn_miss:"))
    check("CX DEST 30..34 SRC CAR..PWM via ef_cx_bank (stackable)",
          "ef_cxpriv_tab" in src and "DEST_CXLAST" in src and "ef_is_cx" in src
          and "ef_cx_bank" in src and "ef_cx_bits" in src
          and "ef_cx_store" in src and "ef_cx_clear" in src
          and "ef_part_setup" in src and "PLAY_SETUP" in src)
    check("DEST clamp uses ef_dest_max (29 / 34 on CX)",
          "ef_dest_max" in _block(src, "ef_nudge:", "ef_nudge_rts:")
          and "ef_dest_max" in _block(src, "ef_load_slot:", "ef_follow_ui:"))
    check("load_slot snaps XVOL (17) to BAL (16)",
          "DEST_XVOL" in _block(src, "ef_load_slot:", "ef_follow_ui:"))
    check("DEPTH values use plain %d",
          "VFMT" in draw and '"%d"' in src and "VFMT_PCT" not in src)

    write = _block(src, "ef_write_mask:", "ef_write_dest:")
    check("write_mask calls ef_write_dest", "ef_write_dest" in write)
    check("write_mask clears page-1 lock or CX bank slot only",
          "ef_cx_clear" in write
          and "addl    ef_dest,%d1" in write
          and "LOCK_VOL" not in write
          and "LOCK_PTCH" not in write)
    dest = _block(src, "ef_write_dest:", "ef_write_vol:")
    check("ef_write_dest reads ef_depth", "ef_depth" in dest)
    check("ef_write_dest branches PTCH to ef_write_ptch",
          "ef_write_ptch" in dest)
    check("ef_write_dest branches AMP VOL to ef_write_vol",
          "ef_write_vol" in dest and "LOCK_VOL" in dest)
    check("ef_write_dest generic: remul uniform in [Part±DEPTH]",
          "ef_part_flat" in dest
          and "remul" in dest
          and "ef_rng" in dest
          and "subi.l  #64,%d0" not in dest)
    check("sequential: page-1 lock or ef_cx_store (CX SETUP stacks)",
          "ef_cx_store" in dest and "ef_cx_clear" in dest
          and "LOCK_PTCH" not in dest)
    vol = _block(src, "ef_write_vol:", "ef_write_ptch:")
    check("ef_write_vol unipolar below Part VOL (r*DEPTH/127)",
          "ef_part_flat" in vol
          and "ef_depth" in vol
          and "ef_rng" in vol
          and re.search(r"moveq\s+#127,%d1", vol) is not None
          and "divul" in vol
          and "subl" in vol
          and "ed_store" in vol)
    ptch = _block(src, "ef_write_ptch:", "ef_part_flat:")
    check("ef_write_ptch guards SCALE_AT",
          "SCALE_AT" in ptch and "0x4ef9" in ptch)
    check("ef_write_ptch writes LOCK_PTCH", "LOCK_PTCH" in ptch)
    check("ef_write_ptch rad = max_rad*DEPTH/127",
          "ef_depth" in ptch
          and re.search(r"moveq\s+#127,%d1", ptch) is not None
          and re.search(r"mulu\.w\s+%d3,%d0", ptch) is not None
          and re.search(r"divu\.l\s+%d1,%d0", ptch) is not None
          and "ep_cnt:" in ptch
          and "ep_pk:" in ptch)
    check("ef_write_ptch parks n/rot/step across pick",
          re.search(r"movel\s+%d5,-\(%sp\)", ptch) is not None
          and re.search(r"movel\s+%d6,-\(%sp\)", ptch) is not None
          and re.search(r"movel\s+%d2,-\(%sp\)", ptch) is not None
          and "ep_clear_rad:" in ptch)
    check("ef_write_ptch window ±PIT_RAD synth / ±PIT_SAMP sample",
          re.search(r"\.set\s+PIT_RAD,\s*24", src) is not None
          and re.search(r"\.set\s+PIT_SAMP,\s*12", src) is not None
          and "PIT_RAD" in ptch and "PIT_SAMP" in ptch)
    check("ef_write_ptch uses ROOT for absolute pitch class",
          "NV_ROOT" in ptch and re.search(r"addl\s+%d6,%d0", ptch) is not None)
    check("ef_write_ptch centers on Part PLAYBACK PTCH (ef_part_ptch)",
          "ef_part_ptch" in ptch
          and re.search(r"\.set\s+PLAY_SLOTS,\s*0x8edaa", src) is not None
          and re.search(r"\.set\s+MACH_OFF,\s*0x8eda2", src) is not None
          and "ep_dst:" in ptch)
    check("ef_write_ptch encodes sample 64+5·st and synth 64+st",
          "ef_is_synth" in ptch
          and "ep_samp:" in ptch
          and re.search(r"muls\.l\s+%d1,%d0", ptch) is not None
          and re.search(r"addi\.l\s+#64,%d0", ptch) is not None)
    check("ef_write_ptch clamps raw to 0..127",
          "ep_clamp:" in ptch and re.search(r"moveq\s+#127,%d1", ptch) is not None)
    check("ef_dest_name reads LFO/AMP/FX descriptors + resolver",
          "ef_dest_name:" in src
          and "NAME_OFF" in src and "LFO_DESC" in src and "AMP_DESC" in src
          and "FX1_TBL" in src and "FX2_TBL" in src
          and "LFD_RESOLVER" in src)
    check("no divu.w insn (illegal on ColdFire 5407)",
          re.search(r"^\s*divu\.w\b", src, re.M) is None)
    cue = _block(src, "ef_cue:", "ef_rng:")
    check("ef_cue uses remul for k-subset pick", "remul" in cue)
    # The hang: free count lived in d1, ef_rng overwrote it with 1664525,
    # remul produced an unreachable rank, cwalk never stopped.
    check("ef_cue parks free-count across ef_rng (d1 clobber)",
          re.search(
              r"sub\.l\s+%d2,%d1.*?movel\s+%d1,-\(%sp\).*?bsr\.w\s+ef_rng"
              r".*?movel\s+\(%sp\)\+,%d1.*?remul",
              cue, re.S) is not None)
    check("ef_cue cwalk bounded by n",
          re.search(r"cwalk:.*?cmpl\s+%d5,%d6.*?bcc\.w\s+cdone",
                    cue, re.S) is not None)
    # No bare remul of d1 without a restore after bsr ef_rng in the pick.
    bare = re.search(
        r"bsr\.w\s+ef_rng\s*\n(?:(?!movel\s+\(%sp\)\+,%d1).)*?\n\s*remul\s+%d1,",
        cue, re.S)
    check("ef_cue never remuls live d1 straight after ef_rng", bare is None)

    rng = _block(src, "ef_rng:", "ef_hit:")
    check("ef_rng writes d1 (LCG mul — callers must not keep a divisor there)",
          re.search(r"move\.l\s+#1664525,%d1", rng) is not None
          and re.search(r"mulu\.l\s+%d1,%d0", rng) is not None)

    hit = _block(src, "ef_hit:", "ef_enc:")
    check("ef_hit Euclid uses remul", "remul" in hit)

    sync = _block(src, "ef_sync_len:", "ef_close:")
    check("sync reads PAT_LEN (+0x8e53)", "PAT_LEN" in sync)
    check("sync reads PAT_PER (+0x8e55)", "PAT_PER" in sync)
    check("sync reads TRK_LEN (+0x50)", "TRK_LEN" in sync)

    mirror = _block(src, "ef_fill:", "ef_write_mask:")
    check("fill mirror copies page-1 DEST locks only (CX uses bank)",
          "addl    ef_dest,%d1" in mirror
          and "DEST_LAST" in mirror
          and "LOCK_VOL" not in mirror
          and "LOCK_PTCH" not in mirror)
    check("fill drops CLEAR TRACK TRIGS undo (CLR_UNDO + kind 0xa)",
          "ef_drop_clr_undo" in src and "CLR_UNDO" in src
          and "0x1001614c" in src and "CLIP_KIND" in src
          and "KIND_CTRG" in src and "ef_drop_clr_undo" in mirror)
    check("open drops CLEAR TRACK TRIGS undo",
          "ef_drop_clr_undo" in src.split("ef_open:")[1].split("ef_close:")[0])

    print("DEPTH math (uniform [Part±DEPTH], non-VOL):")
    check("depth 0 -> base only",
          depth_lock(0, 0, 64) == 64 and depth_lock(0, 99, 64) == 64)
    check("depth 64 base 80: r=0 -> lo 16",
          depth_range(64, 80) == (16, 127) and depth_lock(64, 0, 80) == 16)
    check("depth 64 base 80: r=64 -> 80",
          depth_lock(64, 64, 80) == 80)
    check("depth 42 base 0: span 0..42",
          depth_range(42, 0) == (0, 42)
          and len({depth_lock(42, r, 0) for r in range(256)}) == 43)
    check("depth 127 clamps to full 0..127",
          depth_range(127, 100) == (0, 127)
          and depth_lock(127, 0, 10) == 0
          and depth_lock(127, 127, 100) == 127)
    print("AMP VOL math (unipolar below Part VOL):")
    check("vol depth 0 r any -> Part",
          vol_lock(0, 0, 100) == 100 and vol_lock(0, 127, 100) == 100)
    check("vol depth 64 r=0 -> Part",
          vol_lock(64, 0, 100) == 100)
    check("vol depth 64 r=127 -> Part-64",
          vol_lock(64, 127, 100) == 36)
    check("vol never above Part",
          all(vol_lock(d, r, 80) <= 80
              for d in (1, 64, 127) for r in (0, 64, 127)))
    check("vol depth 127 r=127 clamps at 0",
          vol_lock(127, 127, 50) == 0)


def check_cue_behavior() -> None:
    """Executable model of ef_cue — catches the d1/ef_rng hang without hardware."""
    print("CUE k-subset behavior:")
    for n, k in ((8, 3), (16, 5), (16, 1), (16, 16), (32, 7), (64, 9), (1, 1), (16, 0)):
        m = cue_ksubset(n, k, seed=0xC0FFEE ^ (n * 17 + k))
        check(f"cue E-free n={n} k={k} places exactly k",
              sum(m) == k and len(m) == n)

    # Many seeds: always terminates with correct popcount.
    hung = 0
    bad = 0
    for seed in range(1, 200):
        try:
            m = cue_ksubset(16, 5, seed=seed)
            if sum(m) != 5:
                bad += 1
        except CueHang:
            hung += 1
    check("cue 199 seeds n=16 k=5: no hang, always 5 hits",
          hung == 0 and bad == 0, f"hung={hung} bad={bad}")

    # The bug: divisor = 1664525 after ef_rng → unreachable rank → Hang.
    bug_hung = 0
    for seed in range(1, 50):
        try:
            cue_ksubset(16, 5, seed=seed, clobber_d1=True)
        except CueHang:
            bug_hung += 1
    check("cue with d1 clobber hangs (documents the bug the park fixes)",
          bug_hung >= 40, f"hung={bug_hung}/49")

    # k=0 is a no-op walk (cplace never entered) — must not hang either way.
    check("cue k=0 empty", cue_ksubset(16, 0) == [0] * 16)


def check_pitch_behavior() -> None:
    """DEST=PTCH range + encoding + ROOT-relative scale filter."""
    print("DEST=PTCH behavior:")
    check("rad DEPTH 0 -> 0 (no locks)", pitch_rad(0, 24) == 0)
    check("rad DEPTH 1 -> at least 1", pitch_rad(1, 24) == 1)
    check("rad DEPTH 127 synth -> 24", pitch_rad(127, 24) == 24)
    check("rad DEPTH 127 sample -> 12", pitch_rad(127, 12) == 12)
    check("rad DEPTH 63 synth -> 11", pitch_rad(63, 24) == 11)

    # Major on C: bits 0,2,4,5,7,9,11
    major_pcs = {0, 2, 4, 5, 7, 9, 11}
    major_c = sum(1 << p for p in major_pcs)
    cands = pitch_candidates(24, root=0, mask=major_c)
    check("major/C ±24: only scale PCs",
          all(((0 + st) % 12) in major_pcs for st in cands)
          and len(cands) > 0)
    # ROOT = D (2): SCALE_AT absolute mask = major degrees on D.
    major_d_mask = 0
    for bit in (2, 4, 6, 7, 9, 11, 1):  # D E F# G A B C#
        major_d_mask |= 1 << bit
    cands_d = pitch_candidates(12, root=2, mask=major_d_mask)
    check("major/D ±12: (ROOT+st)%12 in mask, includes unison",
          all(major_d_mask & (1 << ((2 + st) % 12)) for st in cands_d)
          and 0 in cands_d
          and len(cands_d) > 0)

    # Relative to Part PLAYBACK PTCH (overall knob), not unison.
    check("decode synth raw 71 -> +7", decode_ptch(71, synth=True) == 7)
    check("decode sample raw 64 -> 0", decode_ptch(64, synth=False) == 0)
    check("decode sample raw 94 -> +6", decode_ptch(94, synth=False) == 6)
    cands_rel = pitch_candidates(5, root=0, mask=major_c, base_st=7)
    check("major/C ±5 around Part +7: all abs st near 7, on scale",
          all(2 <= st <= 12 for st in cands_rel)
          and all((st % 12) in major_pcs for st in cands_rel)
          and 7 in cands_rel
          and 0 not in cands_rel)
    check("relative encode Part+7 delta0 -> synth 71",
          encode_ptch(7, synth=True) == 71)

    # Encoding: sample |st|>12 must not produce a byte that clamps to 0 (-64).
    check("synth st=-24 -> raw 40", encode_ptch(-24, synth=True) == 40)
    check("synth st=+24 -> raw 88", encode_ptch(24, synth=True) == 88)
    check("sample st=-12 -> raw 4", encode_ptch(-12, synth=False) == 4)
    check("sample st=+12 -> raw 124", encode_ptch(12, synth=False) == 124)
    # The -64 bug: sample encode of st=-24 wraps to a byte Part clamps to 0.
    raw_bad = 64 + 5 * (-24)  # -56
    check("unclamped sample st=-24 is negative (would become -64 on synth)",
          raw_bad < 0)
    check("clamped sample st=-24 -> 0 (still wrong musically — rad must be 12)",
          encode_ptch(-24, synth=False) == 0)


def main() -> int:
    print("Euclidean patterns:")
    check("E(3,8)", pattern(8, 3) == [1, 0, 0, 1, 0, 0, 1, 0])
    check("E(5,16) pulse count", sum(pattern(16, 5)) == 5)
    check("E(4,16) rot 1",
          pattern(16, 4, 1) == pattern(16, 4)[-1:] + pattern(16, 4)[:-1])
    check("E(0,16) empty", pattern(16, 0) == [0] * 16)
    check("E(16,16) full", pattern(16, 16) == [1] * 16)

    check_cue_behavior()
    check_pitch_behavior()

    remix = sys.argv[1] if len(sys.argv) > 1 else "euclid-fill"
    from remix import registry
    if "EUCLID FILL" not in registry.remix(remix).modules:
        print(f"  [ -- ] verify_euclid_fill: {remix} carries no EUCLID FILL")
        return FAILS

    if not SRC.is_file():
        check("euclid_fill.s present", False, str(SRC))
    else:
        check_ui(SRC.read_text())

    print(f"EUCLID FILL: {FAILS} failed checks")
    return FAILS


if __name__ == "__main__":
    sys.exit(main())
