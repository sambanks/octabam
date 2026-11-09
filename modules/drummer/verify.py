#!/usr/bin/env python3
"""DRUMMER engine gate: the rules of drummer.h on the host, and the ColdFire compile.

    python3 modules/drummer/verify.py

1. Host (cc): drummer.c as a shared library, driven through ctypes (engine.py):
   - HUMAN 0 (ORN 0): the groove untouched (equal levels per zone, no micro-timing, no
     ghost, no ornament, first slice of the role), the same every bar; ORN alone (HUMAN 0)
     reaches every ornament;
   - same SEED, same performance; another SEED, another one;
   - a track trig always plays (every style, every BRK, every HUMAN);
   - BRK back to 0 is the groove again;
   - collisions: a COMBO slice holding exactly the colliding zones plays it,
     else the priority wins; SHIFT carries a light loser to a free next step;
   - bounds: slice < count and in the kit, vel 1..127, micro-timing -23..12,
     retrigs only with an interval; an empty kit never plays.
2. ColdFire (m68k-elf-gcc -mcpu=5475, the module flags): compiles freestanding,
   calls nothing outside itself, no .bss / common.
"""
import ctypes
import itertools
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

CF_FLAGS = ['-mcpu=5475', '-msoft-float', '-O2', '-ffreestanding', '-fno-builtin', '-fno-common',
            '-fno-tree-loop-distribute-patterns', '-fno-jump-tables', '-fno-asynchronous-unwind-tables',
            '-fno-ident', '-fomit-frame-pointer', '-std=c11', '-Wall', '-Wextra', '-Werror']

FAILS = []


def check(name, cond, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" -- {detail}" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


def full_kit():
    """Two slices per playing zone (ACCENT, NORMAL, SOFT spread), a KICK+HATC combo."""
    sl, i = {}, 0
    for z in E.ZONES:
        for role in ("ACCENT", "NORMAL", "SOFT"):
            sl[i] = (z, role)
            i += 1
    sl[i] = ("COMBO", "NORMAL", ["KICK", "HATC"])
    return E.make_kit(i + 1, sl), i + 1


def main():
    kit, n = full_kit()
    print("DRUMMER engine (host)")

    # HUMAN 0
    for style in range(len(E.STYLES)):
        p = E.params(style=style, human=0, seed=7, orn=0, ghost=0)   # ORN (64) and GHST (65) are their own knobs
        run = E.play(kit, p, 8)
        hits = [h for _, _, h in run if h[0]]
        bars = [[h for b, _, h in run if b == bar] for bar in range(8)]
        vel_by_zone = {}
        for h in hits:
            vel_by_zone.setdefault(h[6], set()).add(h[2])
        check(f"{E.STYLES[style]}: HUMAN 0 plays, every bar the same",
              hits and all(b == bars[0] for b in bars))
        check(f"{E.STYLES[style]}: HUMAN 0 no micro-timing, no ghost, no ornament",
              all(h[3] == 0 and h[4] == 0 and not (h[7] & 2) for h in hits))
        check(f"{E.STYLES[style]}: HUMAN 0 one level per zone", all(len(v) == 1 for v in vel_by_zone.values()),
              str(vel_by_zone))
        check(f"{E.STYLES[style]}: bars of {E.lib().dr_style_len(style)} steps", len(run) == 8 * E.lib().dr_style_len(style))

    # determinism
    p = E.params(style=2, human=100, seed=11)
    a = E.play(kit, p, 16)
    b = E.play(kit, E.params(style=2, human=100, seed=11), 16)
    c = E.play(kit, E.params(style=2, human=100, seed=12), 16)
    check("same SEED: the same performance", a == b)
    check("another SEED: another performance", a != c)
    check("HUMAN 100 varies from bar to bar",
          len({tuple(h for bb, _, h in a if bb == bar) for bar in range(16)}) > 4)

    # forced trigs always play
    forced = {(bar, st) for bar in range(4) for st in range(16)}   # every step of every style's bar
    ok = True
    for style, human, brk in itertools.product(range(len(E.STYLES)), (0, 64, 127), (0, 40, 70, 90, 100, 127)):
        run = E.play(kit, E.params(style=style, human=human, brk=brk, seed=3), 4, forced=forced)
        ok &= all(h[0] and h[7] & 1 for _, _, h in run)
    check("a track trig always plays (3 styles x HUMAN x BRK, every step)", ok)
    empty_k = E.make_kit(16, {})
    run = E.play(empty_k, E.params(human=127, brk=127), 4)
    check("an empty kit never plays (no trig)", not any(h[0] for _, _, h in run))
    run = E.play(empty_k, E.params(human=127), 1, forced={(0, 0)})
    check("an empty kit with a trig plays slice 0", run[0][2][0] == 1 and run[0][2][1] == 0)

    # BRK back to 0
    groove = E.play(kit, E.params(style=0, human=0, seed=5), 8)
    curve = lambda bar, st: (0, 127, 50, 0, 90, 20, 0, 0)[bar]
    swept = E.play(kit, E.params(style=0, human=0, seed=5), 8, brk_curve=curve)
    landed = lambda bar, st: st < 3 and bar and 32 <= curve(bar - 1, 0) < 64   # image 76: the fill's crash, rung (no hat)
    back = [h for (bar, st, h) in swept if curve(bar, 0) == 0 and not landed(bar, st)]
    ref = [h for (bar, st, h) in groove if curve(bar, 0) == 0 and not landed(bar, st)]
    check("BRK changes the bars it is up on", [h for (bar, _, h) in swept if bar == 1] !=
          [h for (bar, _, h) in groove if bar == 1])
    check("BRK back to 0: the groove again (but the fill's landing)", back == ref)
    C, K_ = E.ZONES.index("CRASH"), E.ZONES.index("KICK")
    check("BRK 50 then 0: the fill lands on a crash, the next bar's 1 (image 76)",
          [h[6] for (bar, st, h) in swept if bar == 3 and st == 0] == [C]
          and [h[2] for (bar, st, h) in swept if bar == 3 and st == 0][0] >= 116)

    # the landing (image 76): a fill of a beat or more, not half a beat; a held whole-bar fill lands when it stops
    def first_of(style, curve, bars, kitx=None, **kw):
        run = E.play(kitx or kit, E.params(style=style, human=0, orn=0, ghost=0, seed=5, **kw), bars, brk_curve=curve)
        return {bar: h for bar, st, h in run if st == 0}
    lands = {}
    for brk in (32, 40, 48, 56):
        f = first_of(0, lambda b, st, brk=brk: brk if b == 0 else 0, 2)
        lands[brk] = f[1][6] == C
    check("BRK 32 no landing (half a beat); 40 / 48 / 56 land on the crash", lands == {32: False, 40: True, 48: True,
          56: True}, str(lands))
    f = first_of(0, lambda b, st: 56 if b < 3 else 0, 4)
    check("BRK 56 held: no crash inside the rolling fill, the crash when it stops",
          [f[b][6] == C for b in (1, 2, 3)] == [False, False, True], str([f[b][6] for b in range(4)]))
    f = first_of(0, lambda b, st: 40 if b == 0 else 0, 2, mix=[64, 64, 64, 0, 64, 64])
    check("KIT BALANCE CYMB 0: no landing crash", f[1][6] != C, str(f[1]))
    sl, i = {}, 0
    for z in ("KICK", "SNARE", "HATC", "CRASH", "TOM"):
        sl[i] = (z, "NORMAL"); i += 1
    sl[i] = ("COMBO", "NORMAL", ["KICK", "CRASH"])
    combo_k = E.make_kit(i + 1, sl)
    f = first_of(0, lambda b, st: 40 if b == 0 else 0, 2, kitx=combo_k)
    check("a KICK+CRASH combo slice: the landing plays it (the kick kept)", f[1][1] == i and f[1][7] & 16, str(f[1]))
    sl = {0: ("KICK", "NORMAL"), 1: ("SNARE", "NORMAL"), 2: ("HATC", "NORMAL")}
    f = first_of(0, lambda b, st: 40 if b == 0 else 0, 2, kitx=E.make_kit(3, sl))
    check("a kit with no crash: the 1 as it was (the kick)", f[1][6] == K_, str(f[1]))
    f = first_of(0, lambda b, st: 40 if b == 0 else 0, 2, fill=[2, 0, 0, 0, 0, 0])
    check("a library fill (FILL RUDI) lands too", f[1][6] == C, str(f[1]))

    # ORN alone (image 64): HUMAN 0, ORN 127 -> flams, fill rolls, ruffs, doubled/tripled hats
    kinds = set()
    for style in range(len(E.STYLES)):
        for brk in (0, 40):                      # BRK 32-63: a fill at every bar's end (no HUMN, no VAR fill)
            for _, step, h in E.play(kit, E.params(style=style, human=0, seed=3, orn=127, brk=brk), 16):
                if h[0] and h[4]:
                    kinds.add((h[4], h[5]))
    check("ORN 127 with HUMAN 0: flams, rolls, ruffs, tripled hats, each at its three spacings (image 68): "
          "flams 1/2 1/3 1/4, rolls 3/4 3/6 3/8, ruffs 2/3, tripled 2/4 2/6 2/8",
          {(1, 2), (1, 3), (1, 4), (3, 4), (3, 6), (3, 8), (2, 3), (2, 4), (2, 6), (2, 8)} <= kinds, str(sorted(kinds)))
    dbl = {(h[4], h[5]) for style in range(len(E.STYLES))
           for _, _, h in E.play(kit, E.params(style=style, human=0, seed=3, orn=90, brk=0), 16) if h[0] and h[4] == 1 and h[6] in (3, 4, 5, 8)}
    check("ORN 90: doubled hats at 6, 8 and 12 (1/6 1/8 1/12)", {(1, 6), (1, 8), (1, 12)} <= dbl, str(sorted(dbl)))
    quiet = all(not h[4] for st in range(len(E.STYLES))
                for _, _, h in E.play(kit, E.params(style=st, human=127, seed=3, orn=0, brk=0), 8) if h[0])
    check("ORN 0 with HUMAN 127: no ornament", quiet)
    # GHST alone (image 65): HUMAN 0, GHST 127 -> ghost notes; GHST 0 with HUMAN 127 -> none
    gh = sum(1 for st in range(len(E.STYLES)) for _, _, h in E.play(kit, E.params(style=st, human=0, seed=3, ghost=127), 8)
             if h[0] and h[7] & 2)
    gq = sum(1 for st in range(len(E.STYLES)) for _, _, h in E.play(kit, E.params(style=st, human=127, seed=3, ghost=0), 8)
             if h[0] and h[7] & 2)
    check("GHST 127 with HUMAN 0: ghost notes; GHST 0 with HUMAN 127: none", gh > 50 and gq == 0, f"{gh} / {gq}")

    # bounds
    ok, worst = True, None
    for style, human, brk, seed in itertools.product(range(len(E.STYLES)), (0, 127), (0, 31, 50, 70, 90, 110, 127), (1, 99)):
        for _, _, h in E.play(kit, E.params(style=style, human=human, brk=brk, seed=seed, orn=127, ghost=127), 8):
            if not h[0]:
                continue
            good = h[1] < n and kit.zone[h[1]] != E.OUT and 1 <= h[2] <= 127 and -23 <= h[3] <= 12 \
                and (h[4] == 0) == (h[5] == 0)
            if not good:
                ok, worst = False, h
    check("bounds: slice in the kit, vel 1..127, micro-timing -23..12, retrig with an interval", ok, str(worst))

    # collisions
    lib = E.lib()
    k2 = E.make_kit(4, {0: ("KICK", "NORMAL"), 1: ("HATC", "NORMAL"), 2: ("COMBO", "NORMAL", ["KICK", "HATC"]),
                        3: ("SNARE", "NORMAL")})
    p = E.params(style=0, human=0, seed=0)          # SEED 0: the style's table
    run = E.play(k2, p, 1)
    st0 = run[0][2]
    check("KICK + HATC on step 1 with a KICK+HATC combo: the combo slice", st0[1] == 2 and st0[7] & 16, str(st0))
    k3 = E.make_kit(3, {0: ("KICK", "NORMAL"), 1: ("HATC", "NORMAL"), 3 - 1: ("SNARE", "NORMAL")})
    run = E.play(k3, p, 1)
    check("no combo: KICK (priority) wins over HATC", run[0][2][6] == 0, str(run[0][2]))
    k3.prio[0], k3.prio[4] = 3, 0          # HATC (zone 3) first, KICK where HATC was
    run = E.play(k3, p, 1)
    check("priority changed: HATC wins", run[0][2][6] == 3, str(run[0][2]))
    k4 = E.make_kit(3, {0: ("KICK", "NORMAL"), 1: ("HATC", "NORMAL"), 2: ("SNARE", "NORMAL")})
    run = E.play(k4, E.params(style=0, human=0, seed=0, shift=1), 1)
    st1 = run[1][2]
    check("SHIFT: the HATC loser of step 1 moves to free step 2", st1[0] and st1[6] == 3 and st1[7] & 32, str(st1))

    # SEED: 0 the table, others its variants, the backbone kept
    lib = E.lib()
    table = []
    for st in range(16):
        table.append(lib.dr_groove_hits(None, ctypes.byref(E.params(style=0, dens=64, cplx=0, seed=0)), st))
    want_t = [(1 if st in (0, 10) else 0) | (2 if st in (4, 12) else 0) | (8 if st % 2 == 0 else 0)
              for st in range(16)]
    check("SEED 0: the BREAKBEAT table (kick 1 and 11, snare 5 and 13, 8th hats)", table == want_t,
          f"{table} vs {want_t}")
    variants = set()
    backbone_ok = True
    for sd in range(1, 9):
        v = tuple(lib.dr_groove_hits(None, ctypes.byref(E.params(style=0, dens=64, cplx=0, seed=sd)), st)
                  for st in range(16))
        variants.add(v)
        backbone_ok &= bool(v[0] & 1) and bool(v[4] & 2) and bool(v[12] & 2)
    check("SEED 1-8 (band 1, variants 1-8): eight different grooves, the backbone kept", len(variants) == 8 and backbone_ok,
          f"{len(variants)} distinct")
    # SEED in bands (image 62): the same variant in every band, each band touching more, nested (CPLX 0: the
    # BASIC level, cells all or nothing, so a change from the table is a touched cell)
    def cells(sd, style):
        return [lib.dr_groove_hits(None, ctypes.byref(E.params(style=style, dens=64, cplx=0, seed=sd)), st)
                for st in range(16)]
    nested, grows, worst = True, True, None
    for style in range(len(E.STYLES)):
        base = cells(0, style)
        for var in range(1, 17):
            prev, prev_n = None, -1
            for band in range(8):
                sd = 1 + band * 16 + var - 1
                if sd > 127:
                    continue
                cur = cells(sd, style)
                diff = {(st, z) for st in range(16) for z in range(9) if (cur[st] ^ base[st]) >> z & 1}
                if prev is not None and not prev <= diff:
                    nested, worst = False, (E.STYLES[style], var, band)
                prev = diff
                prev_n = len(diff)
            grows &= prev_n > 0
    check("SEED bands: a variant's changes in a band are kept in every band above (all styles, 16 variants)",
          nested, f"first break {worst}")
    check("SEED bands: every variant changes the table by band 8", grows)
    check("SEED 1 and 17 (variant 1, bands 1 and 2): the same variant, the second further",
          len({(st, z) for st in range(16) for z in range(9) if (cells(1, 0)[st] ^ cells(0, 0)[st]) >> z & 1})
          <= len({(st, z) for st in range(16) for z in range(9) if (cells(17, 0)[st] ^ cells(0, 0)[st]) >> z & 1}))
    # CPLX: the written levels, BASIC at 0 to COMPLEX at 127, for every style
    ok_c, bad_c = True, []
    for st in range(len(E.STYLES)):
        L = lib.dr_style_len(st)
        def hits(c):
            return [lib.dr_groove_hits(None, ctypes.byref(E.params(style=st, dens=64, cplx=c, seed=0)), x)
                    for x in range(L)]
        lo, mid, hi = hits(0), hits(64), hits(127)
        n = lambda h: sum(bin(v).count("1") for v in h)
        good = lo != hi and n(lo) <= n(mid) <= n(hi) and (hi[0] & 1) >= (lo[0] & 1)   # one drop: no kick on 1
        ok_c &= bool(good)
        if not good:
            bad_c.append(E.STYLES[st])
    check(f"CPLX: {len(E.STYLES)} styles grow from BASIC (0) through STANDARD (64) to COMPLEX (127), the 1 kept",
          ok_c, str(bad_c))

    # the aspects reach far at HUMN 127
    loud = E.play(kit, E.params(style=2, human=127, vel=127, time=127, var=127, seed=4), 8)
    vels = [h[2] for _, _, h in loud if h[0]]
    mts = [h[3] for _, _, h in loud if h[0]]
    check("HUMN 127, VEL 127: levels from soft to full (range >= 80)", max(vels) - min(vels) >= 80,
          f"{min(vels)}..{max(vels)}")
    check("HUMN 127, SWNG 127: off-16ths shuffled by a third of a step or more", max(mts) >= 8, f"max {max(mts)}")
    bars = {tuple(h for b, _, h in loud if b == bar) for bar in range(8)}
    check("HUMN 127, VAR 127: the groove changes every bar", len(bars) == 8, f"{len(bars)} distinct bars")

    # KIT BALANCE: the zones' mix (zone of a hit: h[6]; KICK 0, HATC 3, HATO 4)
    def zones(mix, style=11, bars=8, forced=()):
        return [h[6] for _, _, h in E.play(kit, E.params(style=style, human=64, seed=7, mix=mix), bars, forced=forced)
                if h[0]]
    base = E.play(kit, E.params(style=11, human=64, seed=7), 8)
    same = E.play(kit, E.params(style=11, human=64, seed=7, mix=[64] * 6), 8)
    check("KIT BALANCE all at 64: the performance unchanged", base == same)
    hz = zones([64] * 6)
    check("KIT BALANCE KICK 0: no kick (hits remain)", 0 not in zones([0, 64, 64, 64, 64, 64]) and 0 in hz)
    kicks = [zones([m, 64, 64, 64, 64, 64]).count(0) for m in (0, 32, 64, 127)]
    check("KIT BALANCE KICK 0 / 32 / 64 / 127: more kicks each time", kicks == sorted(kicks) and kicks[0] < kicks[1] < kicks[2] < kicks[3],
          f"{kicks}")
    hats = [sum(z in (3, 4) for z in zones([64, 64, m, 64, 64, 64])) for m in (64, 127)]
    check("KIT BALANCE HATS 127: more hats than at 64", hats[1] > hats[0], f"{hats}")
    run = E.play(kit, E.params(style=11, human=64, seed=7, mix=[0] * 6), 4, forced={(b, 0) for b in range(4)})
    check("KIT BALANCE all at 0: only the track's trigs play", all(h[0] == ((s == 0)) for _, s, h in run),
          f"{[(b, s) for b, s, h in run if h[0] != (s == 0)][:6]}")

    # A kit of three zones plays every style; a full kit uses all its zones (image 58)
    k3z = E.make_kit(3, {0: ("KICK", "NORMAL"), 1: ("SNARE", "NORMAL"), 2: ("HATC", "NORMAL")})
    thin = []
    for st in range(len(E.STYLES)):
        p = E.params(style=st, cplx=127, human=64, var=64, seed=4)
        full_n = sum(1 for _, _, h in E.play(kit, p, 8) if h[0])
        few = [h for _, _, h in E.play(k3z, p, 8) if h[0]]
        bars = {b for b, _, h in E.play(k3z, p, 8) if h[0]}
        if len(few) < full_n * 0.7 or len(bars) < 8:
            thin.append((E.STYLES[st], len(few), full_n))
    check("a KICK / SNARE / HAT C kit plays every style (>= 70 % of a full kit's hits, every bar)", not thin, f"{thin}")
    used = set()
    for st in range(len(E.STYLES)):
        for cplx in (64, 127):
            for _, _, h in E.play(kit, E.params(style=st, cplx=cplx, human=64, var=100, seed=4), 16):
                if h[0]:
                    used.add(h[6])
    check("a full kit: every zone plays somewhere (29 styles, CPLX 64 / 127, VAR 100)",
          set(range(9)) <= used, f"zones {sorted(used)}")

    # the fill library (image 72): ORN sends fills to it; TIME 0 (no humanisation of the timing), so a
    # micro-timing on a fill hit is the fill's own triplet
    def fill_runs(style, orn, seeds=range(1, 17), bars=32):
        """A bar's fill hits, per bar: BRK in its fill zone (image 75), a beat, two, a bar, two in turn."""
        runs = []
        for seed in seeds:
            p = E.params(style=style, human=64, var=127, orn=orn, time=0, ghost=0, vel=0, round=0, seed=seed)
            per = {}
            for bar, step, h in E.play(kit, p, bars, brk_curve=lambda b, st: (40, 48, 56, 48)[b % 4]):
                if h[0] and h[7] & 4:
                    per.setdefault(bar, []).append((bar, step, h))
            runs += [per[b] for b in sorted(per)]
        return runs
    rock, six8 = E.STYLES.index("ROCK"), E.STYLES.index("SIX8")
    quiet = [h for st in range(len(E.STYLES)) for run in fill_runs(st, 0, seeds=(1, 2), bars=16)
             for _, _, h in run if h[3] or h[4]]
    check("ORN 0: the written fills only (no triplet place, no retrig)", not quiet, str(quiet[:3]))
    funk = E.STYLES.index("FUNK")
    runs = fill_runs(rock, 127) + fill_runs(funk, 127)
    T, S = E.ZONES.index("TOM"), E.ZONES.index("SNARE")
    toms = {h[1] for r in runs for _, _, h in r if h[6] == T}
    check("a rudiment fill goes round the toms (the kit's 3 TOM slices)", len(toms) == 3, str(sorted(toms)))
    kicks = sum(1 for r in runs for _, _, h in r if h[6] == 0 and r[0][1] <= 8)
    check("linear and 3-over-4 fills play their kicks (image 73: KICK, zone 0, was taken for a rest)", kicks > 0,
          f"{kicks} kicks in the long fills")
    long_ = sum(1 for r in runs if r[0][1] <= 8)
    check("BRK 48 / 56: two-beat and whole-bar fills", long_ > 0 and any(r[0][1] == 0 for r in runs), f"{long_} long")
    starts = {}
    for brk in (32, 40, 48, 56):
        run = E.play(kit, E.params(style=rock, human=0, orn=0, seed=3, brk=brk), 2)
        starts[brk] = min(st for b, st, h in run if b == 1 and h[0] and h[7] & 4)
    check("BRK 32 / 40 / 48 / 56 (FILLS AUTO): the fill from step 15 / 13 / 9 / 1 (half a beat, one, two, a bar)",
          starts == {32: 14, 40: 12, 48: 8, 56: 0}, str(starts))
    nofill = [b for st in range(len(E.STYLES)) for b, _, h in
              E.play(kit, E.params(style=st, human=127, var=127, orn=64, seed=3, fill=[0, 1, 0, 0, 0, 0]), 16)
              if h[0] and h[7] & 4]
    check("FREQ BRK: no fill without BRK (image 75), HUMN 127 VAR 127 ORN 64, every style", not nofill, str(nofill[:5]))
    trip = [h for st in range(len(E.STYLES)) if E.lib().dr_style_len(st) == 16
            for r in fill_runs(st, 127, seeds=range(1, 9)) for _, _, h in r]
    places = {h[3] for h in trip if h[5] != 16}  # ORN's flams and rolls may sit on a triplet hit too
    sext = any(h[3] == -8 and (h[4], h[5]) == (1, 16) for h in trip)
    check("16-step styles: 8th triplets (+8 / -8, 1/3 step) and sextuplets (-8, a retrig 16/24 later)",
          {8, -8} <= places and sext, f"places {sorted(places)} sextuplets {sext}")
    dbl = {(h[4], h[5]) for r in fill_runs(six8, 127) for _, _, h in r if h[4]}
    check("SIX8 (12/8): triplet fills doubled (a retrig half a step later)", (1, 12) in dbl, str(sorted(dbl)))
    lib_share = lambda st: sum(1 for r in fill_runs(st, 72, seeds=range(1, 9)) for _, _, h in r if h[3] or h[4]) / \
        max(1, sum(len(r) for r in fill_runs(st, 72, seeds=range(1, 9))))
    afro, mini = E.STYLES.index("AFRO"), E.STYLES.index("MINI")
    a_, m_ = lib_share(afro), lib_share(mini)
    check("the style's colour: AFRO's fills more triplets than MINI's", a_ > m_, f"AFRO {a_:.2f} MINI {m_:.2f}")
    nf = tf = 0                                  # image 73: a 4/4 style's 6/8 fills heard (the user's FUNK)
    for seed in range(1, 17):
        bars = {}
        for b, _, h in E.play(kit, E.params(style=funk, human=64, var=100, orn=40, time=0, seed=seed, brk=48), 32):
            if h[0] and h[7] & 4:
                bars.setdefault(b, []).append(h)
        nf += len(bars)
        tf += sum(1 for hs in bars.values() if any(h[3] in (8, -8) or h[5] == 16 for h in hs))
    check("FUNK, ORN 40, BRK 48: a fifth of the fills or more in triplets (6/8 over 4/4)", nf and tf * 5 >= nf, f"{tf} / {nf}")

    # FILLS (image 74): each control set by hand. FREQ 1BAR, LONG BAR: a whole-bar fill every bar
    def bar_fill(style, fill, bars=2, **kw):
        kw.setdefault("brk", 40)
        p = E.params(style=style, human=0, orn=0, ghost=0, time=0, seed=3, fill=fill, **kw)
        return [(b, st, h) for b, st, h in E.play(kit, p, bars)]
    names = {fam: [E.lib().dr_fill_stick_name(fam, i).decode() for i in range(E.lib().dr_fill_sticks(fam))]
             for fam in (1, 2, 3)}
    bad = []
    src = (HERE / "drummer.c").read_text()
    import re as _re
    rud = _re.search(r"RUDIMENTS\[\] = \{([^}]*)\}", src).group(1)
    stickings = _re.findall(r'"([^"]*)"', rud)
    for i, stick in enumerate(stickings):
        run = bar_fill(rock, [2, 1, 3, i + 1, 1, 0])
        got = "".join("T" if h[6] == T else "S" if h[6] == S else "K" if h[6] == 0 else "." for b, _, h in run if b == 1)
        want = "".join(("T" if c in "RrFD" else "S" if c in "LlGE" else "K") for c in (stick * 16)[:16])
        orn = [(h[4], h[5]) for b, _, h in run if b == 1]
        want_orn = [((1, 3) if c in "FG" else (1, 6) if c in "DE" else (0, 0)) for c in (stick * 16)[:16]]
        if got != want or orn != want_orn:
            bad.append((names[1][i], got, want, orn))
    check(f"FILL RUDI, STIK 1..{len(stickings)}, ORCH TOMS: each sticking round the kit, its flams (3/24) and doubles "
          f"(6/24): {' '.join(names[1])}", not bad, str(bad[:2]))
    run = bar_fill(rock, [2, 0, 3, 3, 2, 0])
    check("ORCH SNR: the paradiddle all on the snare, accents loud, taps soft",
          all(h[6] == S for b, _, h in run if b == 1)
          and [h[2] >= 100 for b, _, h in run if b == 1][:8] == [True, False, False, False, True, False, False, False],
          str([(h[6], h[2]) for b, _, h in run if b == 1][:8]))
    run = bar_fill(rock, [2, 0, 3, 3, 3, 0])
    check("ORCH SWAP: the hands swapped (right on the snare)", [h[6] for b, _, h in run if b == 1][:4] == [S, T, S, S],
          str([h[6] for b, _, h in run if b == 1][:4]))
    starts = {}
    for lng, name in ((1, "1BT"), (2, "2BT"), (3, "BAR")):
        run = bar_fill(rock, [2, 0, lng, 1, 1, 0])
        starts[name] = min(st for b, st, h in run if b == 1 and h[0] and h[7] & 4)
    check("LONG 1BT / 2BT / BAR: the fill from step 13 / 9 / 1", starts == {"1BT": 12, "2BT": 8, "BAR": 0}, str(starts))
    fbars = {}
    for freq, brk, name in ((1, 0, "BRK, no BRK"), (1, 40, "BRK"), (2, 40, "2BAR"), (3, 40, "PHRS"), (0, 0, "AUTO, no BRK"),
                            (0, 40, "AUTO")):
        run = [(b, st, h) for b, st, h in E.play(kit, E.params(style=rock, human=127, var=127, orn=0, seed=3, brk=brk,
                                                                fill=[2, freq, 1, 0, 0, 0]), 8)]
        fbars[name] = sorted({b for b, st, h in run if h[0] and h[7] & 4})
    check("FREQ (HUMN 127, VAR 127): BRK every bar with BRK 40, none without; 2BAR every 2nd; PHRS bars 4 and 8; "
          "AUTO VAR's own without BRK, every bar with it",
          fbars["BRK, no BRK"] == [] and fbars["BRK"] == list(range(8)) and fbars["2BAR"] == [1, 3, 5, 7]
          and fbars["PHRS"] == [3, 7] and len(fbars["AUTO, no BRK"]) >= 2 and fbars["AUTO"] == list(range(8)), str(fbars))
    trips = {}
    for tk, name in ((1, "8TH"), (2, "6LET"), (3, "8>6")):
        run = bar_fill(rock, [3, 0, 2, 1, 1, tk])
        trips[name] = [(h[3], h[4], h[5]) if h[0] else None for b, st, h in run if b == 1 and st >= 8]
    e8 = [(0, 0, 0), (8, 0, 0), None, (-8, 0, 0)]
    s6 = [(0, 0, 0), (-8, 1, 16), (0, 0, 0), (-8, 1, 16)]
    check("TRIP 8TH / 6LET / 8>6 (two beats): 8th triplets / sextuplets / 8ths into sextuplets on the last beat",
          trips == {"8TH": e8 * 2, "6LET": s6 * 2, "8>6": e8 + s6}, str(trips))
    run = bar_fill(E.STYLES.index("SIX8"), [3, 0, 2, 1, 1, 2])
    check("12/8, TRIP 6LET: every step of the fill doubled half a step later",
          all((h[4], h[5]) == (1, 12) for b, st, h in run if b == 1 and st >= 6), "")
    run = bar_fill(rock, [4, 0, 3, 3, 1, 0])
    check("FILL 3:4, STIK KSS: kick, snare, snare across the bar",
          "".join("K" if h[6] == 0 else "S" if h[6] == S else "." for b, _, h in run if b == 1) == ("KSS" * 6)[:16])
    a0 = E.play(kit, E.params(style=rock, human=64, var=100, orn=64, seed=5, brk=44), 16)
    a1 = E.play(kit, E.params(style=rock, human=64, var=100, orn=64, seed=5, brk=44, fill=[0, 0, 0, 5, 0, 0]), 16)
    check("STIK ignored under FILL AUTO (the drawn sticking stays)", a0 == a1)
    check("the sticking names: 13 rudiments, 7 triplets, 4 groups of three",
          [len(names[f]) for f in (1, 2, 3)] == [13, 7, 4] and all(len(n) <= 4 for f in names for n in names[f]),
          str(names))

    # REDRUM (image 77): the sample's own loop as the groove
    LZ = ["KICK", "HATC", "HATC", "GHOST", "SNARE", "HATC", "KICK", "HATC",
          "HATC", "KICK", "HATC", "GHOST", "SNARE", "HATC", "KICK", "HATC"]
    lsl = {i: (z, "SOFT" if z == "GHOST" else "NORMAL") for i, z in enumerate(LZ)}
    lsl[16] = ("KICK", "NORMAL"); lsl[17] = ("SNARE", "NORMAL"); lsl[18] = ("HATC", "NORMAL")   # other hits to redrum with
    lkit = E.make_kit(19, lsl)
    lp = E.loop([i * 1000 for i in range(16)], 16000)
    check("loop: 16 slices on a bar, slice n on step n, on the grid",
          lp.len == 16 and list(lp.slice[:16]) == list(range(1, 17)) and not any(lp.mt[:16]))
    l2 = E.loop([i * 1000 for i in range(16)], 16000, bars100=200)
    check("loop: 16 slices on two bars (TRIM 2 bars), slice n on step 2n",
          l2.len == 32 and [l2.slice[2 * i] for i in range(16)] == list(range(1, 17)) and not any(l2.slice[1::2][:16]))
    off = E.loop([i * 1000 + 300 for i in range(16)], 16000)
    check("loop: off the grid, the place kept (300 frames of 1000 a step: +7/24)",
          list(off.slice[:16]) == list(range(1, 17)) and set(off.mt[:16]) == {7}, str(list(off.mt[:16])))
    al = E.loop([i * 1000 for i in range(16)], 16000, bars100=100, align=[0, 10] + [0] * 62)
    check("loop: ALIGN moves the hit's place (10 ms = 441 frames: +10/24)", al.mt[1] == 10, str(al.mt[1]))
    tb = E.loop([i * 5512 for i in range(16)], 88200, bars100=0, tempo24=2880)
    check("loop: no TRIM_BARS, the tempo's (2 s at 120 BPM: a bar)", tb.len == 16, str(tb.len))
    tw = E.loop([0, 100, 2000], 16000)
    check("loop: two slices on one step, the first kept", tw.slice[0] == 1 and tw.slice[2] == 3)
    ts = E.loop([0, 4000, 8000, 12000, 16000, 20000], 24000, trim=(4000, 20000))
    check("loop: the trim's start is step 0 (a slice before it, none)", list(ts.slice[:16:4]) == [2, 3, 4, 5])

    def rd(loop_, kitx=None, bars=4, **kw):
        kw.setdefault("human", 0); kw.setdefault("orn", 0); kw.setdefault("ghost", 0); kw.setdefault("style", funk)
        kw.setdefault("seed", 0); kw.setdefault("cplx", 64)
        return E.play(kitx or lkit, E.params(**kw), bars, redrum=loop_)
    run = rd(lp)
    check("REDRUM, HUMN 0: the loop itself, every bar (slice n on step n, level 100, on the grid)",
          all(h[0] and h[1] == st and h[2] == 100 and h[3] == 0 for b, st, h in run), str(run[:3]))
    run = rd(off)
    check("REDRUM, HUMN 0: the loop's places off the grid kept", all(h[3] == 7 for b, st, h in run))
    run = rd(l2, bars=2)
    check("REDRUM, two bars: bar 1 slices 0-7, bar 2 slices 8-15, every 8th",
          [h[1] for b, st, h in run if b % 2 == 0 and h[0]] == list(range(8))
          and [h[1] for b, st, h in run if b % 2 == 1 and h[0]] == list(range(8, 16)))
    run = rd(lp, human=64, round=64, bars=16)
    swapped = [(st, h[1]) for b, st, h in run if h[0] and h[1] != st and not h[7] & 4]   # fills aside
    check("REDRUM, ALT x HUMN: some hits redrummed with another slice of their zone",
          swapped and all(lkit.zone[sl] == lkit.zone[st] for st, sl in swapped)
          and len(swapped) < len(run) / 2, f"{len(swapped)} of {len(run)}")
    a, b_ = rd(lp, seed=40), rd(lp)
    check("REDRUM, SEED: another groove from the loop", [h[:2] for _, _, h in a] != [h[:2] for _, _, h in b_])
    thin = sum(1 for _, _, h in rd(lp, dens=10) if h[0])
    check("REDRUM, DENS 10: the loop thinned (the backbone kept)", thin < 40, f"{thin} hits of 64")
    basic = [h[1] for b, st, h in rd(lp, cplx=0, bars=1) if h[0]]
    check("REDRUM, CPLX 0: no soft slice (the ghosts out)", 3 not in basic and 11 not in basic, str(basic))
    full = sum(1 for _, _, h in rd(lp, cplx=64, style=rock) if h[0])
    l8 = E.loop([i * 2000 for i in range(8)], 16000)        # the 8ths: the odd steps free
    hous = E.STYLES.index("HOUS")
    std, cx = rd(l8, cplx=64, style=hous, bars=1), rd(l8, cplx=127, style=hous, bars=1)
    added = [st for b, st, h in cx if h[0] and st % 2]
    check("REDRUM, CPLX 127: the style's COMPLEX cells on the loop's free steps, its own hits kept (HOUS)",
          full == 64 and not any(h[0] for b, st, h in std if st % 2) and added
          and all(h[1] == st // 2 for b, st, h in cx if st % 2 == 0), f"added on {added}")
    okit = E.make_kit(19, {**lsl, 2: ("OUT", "NORMAL")}) if False else None
    sl_out = dict(lsl); del sl_out[2]
    okit = E.make_kit(19, sl_out)
    run = rd(lp, kitx=okit, bars=1)
    check("REDRUM: a slice OUT of the kit (a SIMILAR copy) still plays on its step",
          run[2][2][0] and run[2][2][1] == 2, str(run[2]))
    run = rd(lp, brk=40, bars=2)
    check("REDRUM, BRK 40: a fill closes the bar, and lands on the next 1",
          any(h[7] & 4 for b, st, h in run if b == 0 and st >= 12) and not any(h[7] & 4 for b, st, h in run if st < 12))
    w_rock = [h[6] for b, st, h in rd(lp, brk=56, style=rock, fill=[1, 0, 0, 0, 0, 0], bars=1) if h[0]]
    w_funk = [h[6] for b, st, h in rd(lp, brk=56, style=funk, fill=[1, 0, 0, 0, 0, 0], bars=1) if h[0]]
    check("REDRUM: the style's written fill (ROCK's and FUNK's differ)", w_rock != w_funk)
    six = rd(lp, style=six8, bars=1)
    check("REDRUM on a 12/8 style: 16-step bars, the loop", len(six) == 16 and all(h[1] == st for _, st, h in six))

    # image 78: whole bars (1 2 4 8, the nearest), the forced LOOP, an unset trim; TRIP; BRK's top
    s32 = [i * 17640 for i in range(32)]                 # the user's loop: 12.8 s, 32 slices
    l64 = E.loop(s32, 564480, bars100=640, tempo24=2880)
    check("loop: 6.4 bars (a 150 BPM loop on a 120 BPM slot) laid on 8 bars, slice n on step 4n",
          l64.len == 128 and [l64.slice[4 * i] for i in range(32)] == list(range(1, 33)), str(l64.len))
    check("loop: 3 bars -> 4, 5 bars -> 4, 0.6 bar -> 1, no TRIM_BARS at 120 BPM -> 8",
          [E.loop(s32, 564480, bars100=b).len for b in (300, 500, 60)] == [64, 64, 16]
          and E.loop(s32, 564480, bars100=0, tempo24=2880).len == 128)
    f4 = E.loop(s32, 564480, bars100=400, tempo24=2880)
    check("loop: LOOP forced to 4 bars (the slot's tempo aside), slice n on step 2n",
          f4.len == 64 and [f4.slice[2 * i] for i in range(32)] == list(range(1, 33)))
    un = E.loop(s32, 564480, bars100=400, trim=(0, 64))
    check("loop: a trim with no slice in it (unset): the slices' own extent",
          un.len == 64 and [un.slice[2 * i] for i in range(32)] == list(range(1, 33)), str(list(un.slice[:8])))
    sx = [h for b, st, h in E.play(kit, E.params(style=rock, human=0, orn=0, brk=56, fill=[0, 0, 0, 0, 0, 2]), 2)
          if b == 0 and h[0] and h[4] == 1 and h[5] == 16]
    wr = [h for b, st, h in E.play(kit, E.params(style=rock, human=0, orn=0, brk=56, fill=[1, 0, 0, 0, 0, 2]), 2)
          if b == 0 and h[0] and h[4] == 1 and h[5] == 16]
    check("TRIP 6LET under FILL AUTO: sextuplets (TRIP asks for triplets); FILL WRIT keeps the written fill",
          sx and not wr, f"{len(sx)} pairs, {len(wr)} written")
    g0 = E.play(kit, E.params(style=rock, human=0, brk=0), 16)
    g1 = E.play(kit, E.params(style=rock, human=0, brk=127), 16)
    beats = [(b, q) for b in range(16) for q in range(4)]
    empty = {(b, q) for b, q in beats if not any(h[0] for bb, st, h in g1 if bb == b and st // 4 == q)}
    hits0, hits1 = sum(1 for *_, h in g0 if h[0]), sum(1 for *_, h in g1 if h[0])
    check("BRK 127: more filled than emptied (the 1 plays, no two holes running, a hole in six beats at most)",
          not any(q == 0 for _, q in empty) and not any((b, q + 1) in empty for b, q in empty)
          and len(empty) <= len(beats) // 6 and hits1 >= hits0, f"{len(empty)} holes, hits {hits0} -> {hits1}")

    # ColdFire
    print("DRUMMER engine (ColdFire)")
    gcc = shutil.which("m68k-elf-gcc")
    if not gcc:
        print("  [SKIP] m68k-elf-gcc not on PATH")
    else:
        with tempfile.TemporaryDirectory() as td:
            out = pathlib.Path(td) / "d.s"
            r = subprocess.run([gcc, *CF_FLAGS, "-S", str(HERE / "drummer.c"), "-o", str(out)],
                               capture_output=True, text=True)
            check("compiles freestanding for -mcpu=5475", r.returncode == 0, r.stderr[-500:])
            if r.returncode == 0:
                src = out.read_text()
                labels = set(re.findall(r"^([A-Za-z_][\w.]*):", src, re.M))
                calls = {m for m in re.findall(r"^\s+(?:jsr|jbsr|bsr|jmp|jra)\s+([A-Za-z_][\w.]*)", src, re.M)}
                check("calls nothing outside itself", calls <= labels, str(calls - labels))
                check("no .bss / common", not re.search(r"\.(bss|comm|lcomm)\b", src))
    print(f"{'PASS' if not FAILS else 'FAIL'}: DRUMMER engine" + (f" ({len(FAILS)} failed)" if FAILS else ""))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
