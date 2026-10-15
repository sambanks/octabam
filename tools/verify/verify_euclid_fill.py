#!/usr/bin/env python3
"""EUCLID FILL: Euclidean bit patterns + UI contract (fast, no port).

Math matches modules/euclid/control.c. UI checks audit euclid_fill.s so the
popup keeps filter-EUCLID names (STEPS / PULSE / ROT / RAND VEL / RAND PTCH), STEPS
locked to pattern length, encoder A=PULSE / B=ROT / C=RAND VEL / D=RAND PTCH /
LEVEL=focused, and the key layer.
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


def vel_lock(pct: int, r: int) -> int:
    """AMP VOL lock from RAND VEL and r in 0..63 → display delta -63..0."""
    return 64 - (r * pct) // 100


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


def pitch_rad(pct: int, max_rad: int) -> int:
    """RAND PTCH range: rad = max(1, max_rad*pct/100) when pct>0."""
    if pct <= 0:
        return 0
    return max(1, (max_rad * pct) // 100)


def pitch_candidates(rad: int, root: int, mask: int) -> list[int]:
    """In-scale st in [-rad..+rad]; PC = (root+st) mod 12 (SCALE_AT / po_snap)."""
    out: list[int] = []
    for st in range(-rad, rad + 1):
        pc = (root + st) % 12
        if mask & (1 << pc):
            out.append(st)
    return out


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
        ("L_STEPS", "STEPS"),
        ("L_PULSES", "PULSE (A)"),
        ("L_ROT", "ROT (B)"),
        ("L_VEL", "RAND VEL (C)"),
        ("L_PIT", "RAND PTCH (D)"),
    ):
        m = re.search(rf"{lab}:\s*\.asciz\s+\"([^\"]*)\"", src)
        check(f"label {lab}", m is not None and m.group(1) == text,
              m.group(1) if m else "missing")
    check("no ROTATION string", "ROTATION" not in src)

    for name, val in (
        ("WINW", 92), ("WINH", 64),
        ("Y_ROW0", 41), ("Y_ROW1", 34), ("Y_ROW2", 27), ("Y_ROW3", 20),
        ("Y_ROW4", 13),
        ("LOCK0", 0x59), ("LOCK_STEP", 32), ("LOCK_VOL", 15), ("LOCK_PTCH", 0),
    ):
        m = re.search(rf"\.set\s+{name},\s*(0x[0-9a-fA-F]+|\d+)", src)
        got = int(m.group(1), 0) if m else None
        check(f"layout {name}={val}", got == val, str(got) if got is not None else "missing")

    check("default ef_pulses=5",
          re.search(r"ef_pulses:\s*\.long\s+5\b", src) is not None)
    check("default ef_rot=0",
          re.search(r"ef_rot:\s*\.long\s+0\b", src) is not None)
    check("default ef_steps=16",
          re.search(r"ef_steps:\s*\.long\s+16\b", src) is not None)
    check("default ef_velrnd=0",
          re.search(r"ef_velrnd:\s*\.long\s+0\b", src) is not None)
    check("default ef_pitrnd=0",
          re.search(r"ef_pitrnd:\s*\.long\s+0\b", src) is not None)

    for site in ("ef_open", "ef_draw", "ef_fill", "ef_nudge"):
        i = src.find(f"{site}:")
        check(f"{site} calls ef_sync_len",
              i >= 0 and "ef_sync_len" in src[i:i + 800])

    nudge = _block(src, "ef_nudge:", "ef_nudge_rts:")
    check("ef_nudge edits PULSE/ROT/RAND VEL/RAND PTCH",
          "lea     ef_pulses" in nudge and "lea     ef_rot" in nudge
          and "lea     ef_velrnd" in nudge and "lea     ef_pitrnd" in nudge
          and "lea     ef_steps" not in nudge)
    check("ef_nudge parks delta across ef_sync_len",
          re.search(
              r"movel\s+%d0,-\(%sp\).*?bsr\.w\s+ef_sync_len.*?movel\s+\(%sp\)\+,%d2",
              nudge, re.S) is not None)
    check("editing PULSE clears ef_free", "clrl    ef_free" in nudge)
    check("RAND VEL/RAND PTCH clamps to 100",
          re.search(r"moveq\s+#100,%d3", nudge) is not None)

    # Cursor wraps 0..3 (PULSE/ROT/RAND VEL/RAND PTCH)
    down = _block(src, "ef_down:", "ef_left:")
    check("cursor cycles 0..3",
          "addql   #1,%d0" in down and "moveq   #4,%d1" in down)
    up = _block(src, "ef_up:", "ef_down:")
    check("cursor wrap to RAND PTCH",
          re.search(r"moveq\s+#3,%d0", up) is not None)

    keys = _block(src, "EF_KEYS:", "EF_ENCS:")
    for code, handler in (
        ("0x1b", "ef_close"),
        ("0x31", "ef_yes"),
        ("0x32", "ef_no"),
        ("0x33", "ef_up"),
        ("0x20", "ef_down"),
        ("0x34", "ef_left"),
        ("0x21", "ef_right"),
        ("0x2a", "ef_cue"),
    ):
        check(f"key {code} -> {handler}",
              re.search(rf"\.byte\s+{code},.*?\n\s*\.long\s+{handler}\b", keys, re.S)
              is not None)

    cue = _block(src, "ef_cue:", "ef_rng:")
    check("ef_cue fills ef_mask", "ef_mask" in cue)
    check("ef_cue sets ef_free", "ef_free" in cue)
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
    check("encoder C (2) -> ef_enc",
          re.search(r"\.byte\s+2,\s*0[^\n]*\n\s*\.long\s+ef_enc\b", encs) is not None)
    check("encoder D (3) -> ef_enc",
          re.search(r"\.byte\s+3,\s*0[^\n]*\n\s*\.long\s+ef_enc\b", encs) is not None)
    check("encoder LEVEL (6) -> ef_level",
          re.search(r"\.byte\s+6,\s*0[^\n]*\n\s*\.long\s+ef_level\b", encs) is not None)
    check("ef_enc accepts A/B/C/D",
          re.search(r"ef_enc:.*?moveq\s+#3,%d0", src, re.S) is not None)

    draw = _block(src, "ef_draw:", "ef_fill:")
    for lab in ("L_STEPS", "L_PULSES", "L_ROT", "L_VEL", "L_PIT"):
        check(f"draw uses {lab}", f"lea     {lab}" in draw or f"lea\t{lab}" in draw)
    check("RAND VEL/RAND PTCH values use %d%%",
          "VFMT_PCT" in draw and '"%d%%"' in src)

    write = _block(src, "ef_write_mask:", "ef_bit_addr:")
    check("write_mask writes LOCK_VOL", "LOCK_VOL" in write)
    check("write_mask reads ef_velrnd", "ef_velrnd" in write)
    check("write_mask uses r 0..63 (andil #0x3f)",
          "0x3f" in write or "#0x3f" in write)
    check("write_mask VOL = 64 - drop",
          re.search(r"moveq\s+#64,%d1", write) is not None
          and re.search(r"subl\s+%d0,%d1", write) is not None)
    check("write_mask calls ef_write_ptch", "ef_write_ptch" in write)
    check("ef_write_ptch guards SCALE_AT",
          "SCALE_AT" in write and "0x4ef9" in write)
    check("ef_write_ptch writes LOCK_PTCH", "LOCK_PTCH" in write)
    ptch = _block(src, "ef_write_ptch:", "ef_bit_addr:")
    check("ef_write_ptch is a range knob (rad = max_rad*pct/100)",
          re.search(r"mulu\.w\s+%d3,%d0", ptch) is not None
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
    check("ef_write_ptch encodes sample 64+5·st and synth 64+st",
          "ef_is_synth" in ptch
          and "ep_samp:" in ptch
          and re.search(r"muls\.l\s+%d1,%d0", ptch) is not None
          and re.search(r"addi\.l\s+#64,%d0", ptch) is not None)
    check("ef_write_ptch clamps raw to 0..127",
          "ep_clamp:" in ptch and re.search(r"moveq\s+#127,%d1", ptch) is not None)
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

    print("RAND VEL math:")
    check("0% -> 64 (display 0)", vel_lock(0, 0) == 64 and vel_lock(0, 63) == 64)
    check("100% -> 64..1 (display 0..-63)",
          vel_lock(100, 0) == 64 and vel_lock(100, 63) == 1)
    check("50% half drop", vel_lock(50, 0) == 64 and vel_lock(50, 63) == 33)


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
    """RAND PTCH range + encoding + ROOT-relative scale filter."""
    print("RAND PTCH behavior:")
    check("rad 0% -> 0 (no locks)", pitch_rad(0, 24) == 0)
    check("rad 1% -> at least 1", pitch_rad(1, 24) == 1)
    check("rad 100% synth -> 24", pitch_rad(100, 24) == 24)
    check("rad 100% sample -> 12", pitch_rad(100, 12) == 12)
    check("rad 50% synth -> 12", pitch_rad(50, 24) == 12)

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
