#!/usr/bin/env python3
"""Prove the ledger catches what it claims to catch.

A guard nobody has watched fail is a guard nobody knows works. Each case
below builds two modules that collide in one specific way and asserts the
ledger names both of them; the last case asserts a clean pair stays clean,
because a checker that fires on everything is no better than one that fires
on nothing.

    python3 tools/remix/selftest.py
"""

import os
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
ROOT = pathlib.Path(__file__).resolve().parents[2]

from remix import ledger, registry, schema, state, stock  # noqa: E402
from remix.schema import (CavePatch, Claims, DspSection, Kind, MenuEntry,  # noqa: E402
                          Module, Param, YBase)


def _effect(name, fx2_id, priority=0, reserved=(), buffers=False,
            ybase=YBase.NEVER):
    return Module(
        name=name, key=name.upper(), kind=Kind.DSP_EFFECT,
        doc="fixture",
        menu=MenuEntry(fx2_id=fx2_id, donor_desc=0x400d58b8,
                       abbr=b"FIX", fullname=b"Fixture"),
        params=tuple([Param(b"A", 0, active=True)] + [Param()] * 11),
        # No asm path on disk, so the ledger's scan finds nothing and only
        # the reserved words below are claimed -- which is what lets these
        # fixtures test the claim path in isolation.
        dsp=DspSection(asm="does/not/exist.asm", priority=priority,
                       ybase=ybase),
        claims=Claims(reserved_private_y=reserved,
                      owns_fx2_buffers=buffers),
    )


def _stock(name, fx2_id, buffer):
    """A stock FX2 effect as the registry carries it (tools/remix/stock.py)."""
    return Module(
        name=name, key=name.upper(), kind=Kind.STOCK, doc="fixture",
        menu=MenuEntry(fx2_id=fx2_id, donor_desc=0x400d4772,
                       abbr=b"STK", fullname=b"Stock"),
        claims=Claims(stock_instance_buffer=buffer) if buffer else None,
    )


def _cave(name, cave_addr, length=16, hook_addr=None):
    return Module(
        name=name, key=name.upper(), kind=Kind.CF_PATCH, doc="fixture",
        cf_patches=(CavePatch(label=f"{name} cave", cave_addr=cave_addr,
                              pinned=b"\x4e\x71" * (length // 2),
                              hook_addr=hook_addr,
                              hook_stock=b"\x00" * 10 if hook_addr else b""),),
    )


CASES = [
    ("two modules claiming one FX2 id",
     [_effect("alpha", 0x07), _effect("beta", 0x07)], "fx2 id"),
    ("two caves overlapping in memory",
     [_cave("alpha", 0x400d7000, 64), _cave("beta", 0x400d7020, 64)],
     "ColdFire cave"),
    ("two modules hooking the same instruction",
     [_cave("alpha", 0x400d7000, hook_addr=0x40004d40),
      _cave("beta", 0x400d7100, hook_addr=0x40004d40)], "hook site"),
    ("two effects claiming one core-private Y word",
     [_effect("alpha", 0x07, reserved=(0x0905,)),
      _effect("beta", 0x1e, reserved=(0x0905,))], "core-private Y"),
    # The shape this one guards is a module that works perfectly in every
    # test done alone: ChonVerb's tank and Nimbus's granular line are both
    # hardcoded into Y:0x4000-0xBFFF, which is per CORE.
    ("two effects owning the FX2 instance buffer region",
     [_effect("alpha", 0x07, buffers=True),
      _effect("beta", 0x1e, buffers=True)], "FX2 instance buffers"),
    # A BUFFERED stock effect takes a per-track base from the host's
    # allocator, and those bases are the addresses the servers hardcode:
    # CHORUS on T6 beside ChonVerb on T5 writes into the tank. Refused
    # beside a module that owns the region ...
    ("a buffered stock effect beside a module owning FX2 buffers",
     [_stock("chorus", 0x12, True), _effect("beta", 0x07, buffers=True)],
     "stock instance buffer"),
    # ... and beside one whose lines live in the shared window (BongDelay:
    # ybase ALWAYS), which is core 1's tracks 3-4 slots.
    ("a buffered stock effect beside a shared-window module",
     [_stock("comb", 0x13, True), _effect("beta", 0x07, ybase=YBase.ALWAYS)],
     "stock instance buffer"),
]

CLEAN = [_effect("alpha", 0x07, reserved=(0x0905,)),
         _effect("beta", 0x1e, reserved=(0x0906,), buffers=True),
         _cave("gamma", 0x400d7000, 64, hook_addr=0x40004d40),
         _cave("delta", 0x400d7040, 64, hook_addr=0x40004d50),
         # Stock effects with NO buffer sit beside anything, and two
         # buffered stock effects sit beside each other (the allocator
         # keeps them apart -- that is what it is for).
         _stock("filter", 0x04, False),
         _stock("compressor", 0x18, False)]
CLEAN_STOCK_PAIR = [_stock("chorus", 0x12, True), _stock("comb", 0x13, True),
                    _effect("alpha", 0x07)]


def main():
    bad = 0
    for label, mods, expect in CASES:
        found = ledger.check(mods)
        hit = [p for p in found if p.startswith(expect)]
        names = hit and all(m.name in hit[0] for m in mods[:2])
        if hit and names:
            print(f"  [PASS] {label}")
            print(f"         -> {hit[0]}")
        else:
            bad += 1
            print(f"  [FAIL] {label}: expected a {expect!r} collision naming "
                  f"both modules, got {found}")
    for label, mods in (("modules that do not collide", CLEAN),
                        ("two buffered stock effects + a zero-buffer insert",
                         CLEAN_STOCK_PAIR)):
        found = ledger.check(mods)
        if found:
            bad += 1
            print(f"  [FAIL] {label} were reported: {found}")
        else:
            print(f"  [PASS] {label} are left alone")

    # A module on a STOCK id would hijack that effect on BOTH menus (the
    # dispatch tables are shared with FX1). Rungs shipped on EQUALIZER's
    # 0x0c and Nimbus on DJ EQ's 0x0d before this line existed (2 Sep 2026).
    try:
        _effect("hijack", 0x0c)
        bad += 1
        print("  [FAIL] a module on a stock FX2 id (0x0c, EQUALIZER) was accepted")
    except ValueError:
        print("  [PASS] a module on a stock FX2 id is refused")

    # ---- the rig's derivations (tools/remix/rig.py) ---------------------
    # The track model is DERIVED, so hold the derivation to the measured
    # facts: payload A serves TRACKS 5-8, B serves 1-4 (10 Aug 2026), an
    # insert runs anywhere, SYSTEM modules never sit on a track.
    from remix import rig
    for mod in registry.modules().values():
        cat = rig.category(mod)
        tr = rig.track_range(mod)
        if cat == rig.SERVER:
            want = (rig.PAYLOAD_TRACKS["A"]
                    if mod.dsp.payloads == frozenset({"A"})
                    else rig.PAYLOAD_TRACKS["B"])
            ok = len(mod.dsp.payloads) == 1 and tr == want
        elif cat in (rig.INSERT, rig.STOCK):
            ok = tr == rig.TRACKS
        else:
            ok = len(tr) == 0
        if ok:
            print(f"  [PASS] {mod.name}: {cat}, tracks "
                  f"{f'{tr.start}-{tr.stop - 1}' if len(tr) else 'none'}")
        else:
            bad += 1
            print(f"  [FAIL] {mod.name}: category {cat} derived tracks {tr}")
    # A server that never declared its payload must refuse, not guess: the
    # field's default is {"A","B"} and a guess would put the effect on all
    # eight tracks of the picker.
    from remix.schema import BusRole, DspSection, Harness
    vague = Module(
        name="vague", key="VAGUE", kind=Kind.DSP_EFFECT, doc="fixture",
        menu=MenuEntry(fx2_id=0x1f, donor_desc=0x400d58b8,
                       abbr=b"VAG", fullname=b"Vague"),
        dsp=DspSection(asm="does/not/exist.asm", priority=0,
                       bus_role=BusRole.SERVER),
        harness=Harness(layout_char=None, is_server=True))
    try:
        rig.track_range(vague)
        bad += 1
        print("  [FAIL] a server with undeclared payload was given tracks")
    except ValueError:
        print("  [PASS] a server with undeclared payload is refused")

    # ---- one knob-name universe -----------------------------------------
    # The audition path drives render_reverb, whose PARAMS list predates the
    # manifest and keeps two historical labels (MIX for IN, SPEED for SHMR).
    # The bridge is positional -- manifest slot -> PARAMS[slot] -- so prove
    # the two tables stay slot-for-slot aligned; a slot that moves in one and
    # not the other is exactly the wrapper drift that has burned renders
    # before (the harness-knob-drift rule).
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
    import render_reverb
    cv = registry.by_key("REVERB SERVER")
    for name, slot in sorted(cv.knob_map().items(), key=lambda kv: kv[1]):
        if slot == 7:
            ok = render_reverb.PARAMS[slot][0] == "_C"   # MODE goes via --mode
        else:
            rr_name = render_reverb.PARAMS[slot][0]
            ok = rr_name in render_reverb.NAMES and \
                render_reverb.NAMES[rr_name] == slot
        if not ok:
            bad += 1
            print(f"  [FAIL] chonverb {name}@{slot} has no aligned "
                  f"render_reverb param")
    else:
        print("  [PASS] chonverb's manifest slots align with render_reverb")

    # ---- every drawn knob answers "what is this?" -----------------------
    # The remixer shows Param.doc as the help line under the knob cursor,
    # and a select's labels beside its value. A knob with neither is a knob
    # the operator has to reverse-engineer by ear, so hold the line: every
    # named, drawn param of every menu-bearing module carries a doc.
    # (Length is capped so the help row stays one line; the schema already
    # pins labels to the declared count.)
    for mod in registry.modules().values():
        if mod.menu is None:
            continue
        undocumented = [p.name.decode() for p in mod.params
                        if p.name and p.active and not p.doc]
        toolong = [p.name.decode() for p in mod.params
                   if p.name and p.doc and len(p.doc) > 90]
        if undocumented or toolong:
            bad += 1
            print(f"  [FAIL] {mod.name}: undocumented knobs {undocumented}, "
                  f"over-long docs {toolong}")
        else:
            print(f"  [PASS] {mod.name}: every drawn knob has a doc")

    # ---- stock rows carry their descriptor's knobs -----------------------
    # Read from the pristine image, so the rig shows a stock effect's real
    # controls and send_probe can drive them by name. Only checkable when
    # the image is on disk (make setup); a fresh clone gets params=().
    from remix import stock
    if stock.STOCK_IMAGE.exists():
        for mod in stock.MODULES:
            names = sorted(mod.knob_map())
            if not names or len(mod.params) != 12:
                bad += 1
                print(f"  [FAIL] {mod.name}: no knobs read from its descriptor")
            elif len(set(names)) != len(names):
                bad += 1
                print(f"  [FAIL] {mod.name}: duplicate knob names {names}")
            else:
                print(f"  [PASS] {mod.name}: {len(names)} stock knobs read "
                      f"({' '.join(names)})")
    else:
        print("  [SKIP] stock knobs: out/raw/section_3_MAIN_OS.bin not on disk")
    # ---- stock selects carry the firmware's own labels ---------------------
    # tools/stock_labels.py asked each select's display formatter what it
    # prints; the JSON it wrote must cover every select at the right length,
    # and -- when the emulator is on hand -- still match the firmware.
    if stock.STOCK_IMAGE.exists():
        missing = [f"{m.key}.{p.name.decode()}" for m in stock.MODULES
                   for p in m.params
                   if p.name and p.active and p.count is not None and not p.labels]
        if missing:
            bad += 1
            print(f"  [FAIL] stock selects without firmware labels: {missing} "
                  f"-- run: make stock-labels")
        else:
            n = sum(1 for m in stock.MODULES for p in m.params if p.labels)
            print(f"  [PASS] all {n} stock selects carry the firmware's labels")
        _venv = ROOT / ".venv/bin/python3"
        if _venv.exists():
            r = subprocess.run([str(_venv), "tools/stock_labels.py", "--check"],
                               cwd=ROOT, capture_output=True, text=True)
            if r.returncode == 0:
                print("  [PASS] stock_labels.json matches what the emulated "
                      "firmware prints")
            else:
                bad += 1
                print("  [FAIL] stock_labels.json is stale: "
                      + (r.stdout + r.stderr).strip().splitlines()[-1])
        else:
            print("  [SKIP] label check against the firmware: no .venv "
                  "(make emu-setup)")

    # Every module in the registry needs a distinct layout letter or the
    # send_probe alphabet silently drops one.
    chars = [m.harness.layout_char for m in registry.modules().values()
             if m.harness is not None and m.harness.layout_char]
    if len(set(chars)) != len(chars):
        bad += 1
        print(f"  [FAIL] duplicate layout letters: {sorted(chars)}")
    else:
        print(f"  [PASS] {len(chars)} distinct layout letters")

    # ---- the stock-render harness puts the audio block where hardware does --
    # The dispatcher's `move #$0,r0`: the audio block is at X:0 and stock
    # effects use the X right after it as scratch (the flanger writes
    # X:0x20-0xff every block). dsp_host's default of X:0x80 sat inside that
    # scratch and turned FLANGER into a Nyquist-rate alternation while EQ,
    # DJ EQ, PHASER, SPATIALIZER and COMB were quietly 5-17 dB dirtier than
    # they should be (2 Sep 2026). Hold the line with the sharpest of them:
    # FLANGER at MIX=0 is a BIT-EXACT dry passthrough at the right address.
    _host = ROOT / "vendor/dsp56300/build/source/dsp_host/dsp_host"
    _dump = ROOT / "out/dsp/_stock_A.mem"
    if _host.exists() and stock.STOCK_IMAGE.exists():
        if not _dump.exists():
            import dsp_modmap
            _dump.parent.mkdir(parents=True, exist_ok=True)
            dsp_modmap.dumpmem(stock.STOCK_IMAGE.read_bytes(), ["A", str(_dump)])
        r = subprocess.run([sys.executable, "tools/send_probe.py", "--mem",
                            str(_dump), "--direct", "--pick", "flanger",
                            "--dur", "0.45", "--tail", "0.05", "--set=MIX=0"],
                           cwd=ROOT, capture_output=True, text=True)
        import re as _re
        m = _re.search(r"THD \(2f\.\.9f\) = *(-?[\d.]+) dB", r.stdout)
        pk = _re.search(r"peak +([\d.]+) FS", r.stdout)
        thd = float(m.group(1)) if m else None
        peak = float(pk.group(1)) if pk else None
        # The tone metric floors around -54 dB in send_probe's window (a
        # unity pass of the 0.5 FS tone reads -53.8); the broken state read
        # peak 1.000 / THD -2 dB. Either number alone discriminates.
        if (r.returncode == 0 and thd is not None and peak is not None
                and thd < -50 and abs(peak - 0.5) < 0.005):
            print(f"  [PASS] stock FLANGER at MIX=0 is a dry pass (peak "
                  f"{peak:.3f} FS, THD {thd:.0f} dB) -- the audio block is at X:0")
        else:
            bad += 1
            print(f"  [FAIL] stock FLANGER at MIX=0 is not dry (peak {peak}, "
                  f"THD {thd}) -- is dsp_host's audio block back inside "
                  f"stock scratch?")
    else:
        print("  [SKIP] stock render harness: dsp_host or the stock image is missing")

    # THE BUDGET'S TOTALS ARE NOT THE BUDGET'S TO DECIDE. The remixer
    # states "N free of TOTAL" for the ColdFire cave, and the build reports
    # only what is LEFT of it -- so the total is written down in state.py and
    # would go stale silently the day the cave's bounds move. Pin it to
    # build_bus's own constants by reading them out of the source: a total
    # that is quietly wrong is exactly the kind of confident stale number
    # this project keeps getting burned by.
    _bb = (ROOT / "tools/build_bus.py").read_text()
    _bounds = {}
    for _name in ("NEW_LIST", "ZERO_RUN_END"):
        _m = re.search(rf"^{_name} = (0x[0-9a-f]+)", _bb, re.M)
        if _m:
            _bounds[_name] = int(_m.group(1), 16)
    if len(_bounds) != 2:
        bad += 1
        print("  [FAIL] could not read NEW_LIST/ZERO_RUN_END out of "
              "build_bus.py -- the cave total cannot be pinned")
    elif _bounds["ZERO_RUN_END"] - _bounds["NEW_LIST"] == state.CAVE_BYTES:
        print(f"  [PASS] the cave total ({state.CAVE_BYTES:,} B) matches "
              f"build_bus's own bounds")
    else:
        bad += 1
        print(f"  [FAIL] state.CAVE_BYTES is {state.CAVE_BYTES:,} B but "
              f"build_bus's cave is "
              f"{_bounds['ZERO_RUN_END'] - _bounds['NEW_LIST']:,} B")

    # THE NONE FALLBACK IS ONLY SAFE WITHOUT A BUS, and that is a refusal,
    # not a convention -- an unassigned track then runs nothing at all, so
    # nobody flips the rotation or clears the accumulators. dsp_host is
    # single-core and can never reproduce the defect, so this check is the
    # only thing standing between the two. See schema.NO_FALLBACK.
    _probe = ROOT / "remixes/_selftest_nofb.py"
    try:
        _probe.write_text(
            "from remix.schema import Remix\n\n"
            "REMIX = Remix(name='_selftest_nofb', doc='scratch',\n"
            "              modules=('WARPFOLD', 'SEND'), fallback='NONE')\n")
        registry.remix("_selftest_nofb")
        bad += 1
        print("  [FAIL] fallback='NONE' was accepted beside SEND -- an "
              "unassigned track would leave the bus unhousekept")
    except SystemExit as e:
        if "no bus participant" in str(e):
            print("  [PASS] fallback='NONE' is refused beside a bus participant")
        else:
            bad += 1
            print(f"  [FAIL] fallback='NONE' beside SEND was refused for the "
                  f"wrong reason: {e}")
    finally:
        _probe.unlink(missing_ok=True)
        for junk in (ROOT / "remixes/__pycache__").glob("_selftest_nofb*"):
            junk.unlink(missing_ok=True)

    # And the same rule read off the SHIPPED remixes, which is where it would
    # actually go wrong: nothing may pair NO_FALLBACK with a bus module.
    for _n in registry.remix_names():
        _r = registry.remix(_n)
        _bus = [k for k in _r.modules
                if schema.on_the_bus(registry.modules()[k])]
        if _r.fallback == schema.NO_FALLBACK and _bus:
            bad += 1
            print(f"  [FAIL] remix {_n!r} falls back to NONE but carries "
                  f"{', '.join(_bus)}")
    print(f"  [PASS] every remix's fallback matches whether it has a bus")

    # ---- dynamic donor regions (Remix.harvest) ---------------------------
    # The property the whole idea rests on: the thirteen DSP effects are
    # CONTIGUOUS in both payloads and their record sizes match what stock.py
    # says they cost. Derived from the module map every run, so a firmware
    # whose layout differs fails here rather than being written over.
    for _pay in ("A", "B"):
        try:
            _sp = stock.p_spans(_pay)
        except Exception as e:                       # noqa: BLE001
            bad += 1
            print(f"  [FAIL] payload {_pay}: no effect run found -- {e}")
            continue
        _run = sorted(_sp.values())
        _lo, _hi = _run[0][0], _run[-1][0] + _run[-1][1]
        _gap = [a for (a, n), (a2, _n) in zip(_run, _run[1:]) if a + n != a2]
        if _gap:
            bad += 1
            print(f"  [FAIL] payload {_pay}: effect code is not contiguous")
        _wrong = [k for k, (_a, n) in _sp.items()
                  if k in stock.WORDS and stock.WORDS[k] != n
                  and k != "PHASER"]
        if _wrong:
            bad += 1
            print(f"  [FAIL] payload {_pay}: {_wrong} disagree with "
                  f"stock.WORDS")
        # ⚠️ AND EVERY SPAN KEY MUST BE A REAL STOCK KEY. `COMB` against the
        # registry's `COMB FILTER` made `h` answer "it runs on the ColdFire"
        # for an effect with 277 words of DSP code -- a silent miss, because
        # a missing key looks exactly like an effect with no code.
        _reg = {m.key for m in stock.MODULES}
        _orphan = sorted(set(_sp) - _reg)
        if _orphan:
            bad += 1
            print(f"  [FAIL] payload {_pay}: span keys not in the registry: "
                  f"{_orphan}")
        elif not _wrong:
            print(f"  [PASS] payload {_pay}: {len(_sp)} effects contiguous, "
                  f"P:0x{_lo:05x}..0x{_hi:05x} = {_hi - _lo:,} words")
    # ⚠️ AND THE DERIVED HARVEST MUST REPRODUCE WHAT THE BUILD HAS ALWAYS
    # DONE. "On neither chooser" gives every shipped remix exactly the three
    # reverbs -- FX1 lists ten of the thirteen and the reverbs are FX2-only
    # -- which is the whole reason removing the explicit field was safe.
    # restock lists all fourteen and places nothing, so it gives up nothing.
    _sp = stock.p_spans("A")
    _fx1_all = {k for k in _sp
                if registry.modules()[k].menu.fx2_id in stock.fx1_ids()}
    # The three that differ, and why -- a remix reaching this list by
    # accident is the thing being guarded against.
    _want = {"restock": (),                       # lists all fourteen
             "nimbuslite": ("PLATE REV", "SPRING REV"),   # keeps DARK REV
             # deliberately gives up two more, to put a non-reverb donor on
             # the unit for the first time (docs/FLASHPLAN.md)
             "fieldtest": ("FLANGER", "CHORUS", "PLATE REV", "SPRING REV",
                           "DARK REV"),
             # THREE runs on purpose -- the multi-run worked example. Its
             # placement is checked for real below, not just its harvest.
             "scattered": ("SPATIALIZER", "FLANGER", "CHORUS", "PLATE REV",
                           "SPRING REV", "DARK REV", "COMB FILTER"),
             # the BamSep26 stations beside the reverb: FILTER is REPLACED
             # (its words are the station's ground) and the FX1 list keeps
             # only DJ EQ, COMPRESSOR and LO-FI, so ten of thirteen go
             # the three stations take FILTER, LO-FI and CHORUS by name and
             # nothing else is listed, so all thirteen go: one 6,158-word run.
             # bamsep26 is the rig and has the same shape (stock DELAY is on
             # its chooser, but it has no DSP code to give up).
             "bamsep26": ("FILTER", "SPATIALIZER", "EQUALIZER", "PHASER",
                          "FLANGER", "CHORUS", "PLATE REV", "SPRING REV",
                          "DARK REV", "COMPRESSOR", "LO-FI", "DJ EQ",
                          "COMB FILTER"),
             # cfprobe is the rig plus HELLO WORLD and the ColdFire probe
             # cave: the same harvest, 27 more words placed.
             "cfprobe": ("FILTER", "SPATIALIZER", "EQUALIZER", "PHASER",
                         "FLANGER", "CHORUS", "PLATE REV", "SPRING REV",
                         "DARK REV", "COMPRESSOR", "LO-FI", "DJ EQ",
                         "COMB FILTER"),
             "stations": ("FILTER", "SPATIALIZER", "EQUALIZER", "PHASER",
                          "FLANGER", "CHORUS", "PLATE REV", "SPRING REV",
                          "DARK REV", "COMPRESSOR", "LO-FI", "DJ EQ",
                          "COMB FILTER")}
    for _n in registry.remix_names():
        _r = registry.remix(_n)
        _hv = stock.region_of(stock.harvested(
            set(_r.modules) | set(_r.fx1 or _fx1_all)))
        _exp = _want.get(_n, stock.CONSUMED)
        if _n == "bothslots":
            continue                     # its curated FX1 list gives it more
        if tuple(_hv) != tuple(_exp):
            bad += 1
            print(f"  [FAIL] remix {_n!r} gives up {_hv}, expected {_exp}")
        # ⚠️ RUNS, NOT ONE RUN. Since 3 Sep 2026 a gap is two placeable
        # openings rather than a refusal, so what has to hold is that the
        # grouping is sound: every run internally contiguous, and the runs
        # together covering exactly the harvested set.
        _runs = stock.regions_of(_hv)
        for _g in _runs:
            _run = [_sp[k] for k in _g]
            if any(a + n != a2 for (a, n), (a2, _x) in zip(_run, _run[1:])):
                bad += 1
                print(f"  [FAIL] remix {_n!r}: run {_g} is not contiguous")
        if sorted(k for g in _runs for k in g) != sorted(_hv):
            bad += 1
            print(f"  [FAIL] remix {_n!r}: the runs do not cover {_hv}")
    print(f"  [PASS] every remix's given-up effects group into contiguous "
          f"runs, and the shipped ones give up exactly what they always did")

    # ---- MULTI-RUN PLACEMENT, actually built --------------------------
    # ⚠️ THE GROUPING ABOVE IS ARITHMETIC; THIS IS THE BUILD. Nothing else
    # here would notice the placer quietly reverting to one bump cursor:
    # `scattered` would still assemble, still pass every other check, and
    # simply leave its two smaller runs empty -- which is exactly the defect
    # this replaced (3 Sep 2026, "when I remove some reverb it only shows
    # the free reverb space"). So: build it, and require that two modules
    # landed in two DIFFERENT runs.
    r = subprocess.run([sys.executable, "tools/build_bus.py"],
                       cwd=ROOT, capture_output=True, text=True,
                       env={**os.environ, "REMIX": "scattered",
                            "XBUS": "1", "SPEC": "1"})
    if r.returncode:
        bad += 1
        print(f"  [FAIL] remix 'scattered' does not build:\n"
              f"{r.stdout[-600:]}{r.stderr[-400:]}")
    else:
        # ⚠️ PER PAYLOAD. The two payloads put the same effects at
        # DIFFERENT addresses, so merging their run lines checks neither --
        # and "one instance is one payload" is exactly how this codebase
        # has been bitten before (docs/DSP.md s11).
        _by_pay, _pay = {}, None
        for line in r.stdout.splitlines():
            m = re.match(r"-- payload (\w+) --", line.strip())
            if m:
                _pay = m.group(1)
                _by_pay[_pay] = {"runs": [], "at": {}}
            if _pay is None:
                continue
            m = re.match(r"\s+run \d+ P:0x([0-9a-f]+)\.\.0x([0-9a-f]+)", line)
            if m:
                _by_pay[_pay]["runs"].append((int(m.group(1), 16),
                                              int(m.group(2), 16)))
            m = re.match(r"\s{2}(STREAMZ|WARPFOLD)\s+P:0x([0-9a-f]+)", line)
            if m:
                _by_pay[_pay]["at"][m.group(1)] = int(m.group(2), 16)
        if sorted(_by_pay) != ["A", "B"]:
            bad += 1
            print(f"  [FAIL] 'scattered': expected both payloads, saw "
                  f"{sorted(_by_pay)}")
        else:
            _ok = True
            for _p, _d in sorted(_by_pay.items()):
                _rs, _at = _d["runs"], _d["at"]
                _in = {k: next((i for i, (lo, hi) in enumerate(_rs)
                                if lo <= a < hi), None)
                       for k, a in _at.items()}
                if len(_rs) != 3:
                    bad += 1; _ok = False
                    print(f"  [FAIL] 'scattered' payload {_p}: {len(_rs)} "
                          f"runs, expected 3")
                elif sorted(_at) != ["STREAMZ", "WARPFOLD"]:
                    bad += 1; _ok = False
                    print(f"  [FAIL] 'scattered' payload {_p}: placed "
                          f"{sorted(_at)}, expected both modules")
                elif None in _in.values():
                    bad += 1; _ok = False
                    print(f"  [FAIL] 'scattered' payload {_p}: a module "
                          f"landed outside every run -- {_at} vs {_rs}")
                elif len(set(_in.values())) < 2:
                    bad += 1; _ok = False
                    print(f"  [FAIL] 'scattered' payload {_p}: both modules "
                          f"landed in the SAME run ({_in}) -- the placer is "
                          f"not filling the smaller openings")
                elif _in["STREAMZ"] != 0:
                    # STREAMZ is 255 words and run 1 holds 261: first-fit
                    # MUST take it. Anywhere else means the small opening
                    # was skipped, which is the whole defect.
                    bad += 1; _ok = False
                    print(f"  [FAIL] 'scattered' payload {_p}: STREAMZ went "
                          f"to run {_in['STREAMZ'] + 1}, not the 261-word "
                          f"opening it fits")
            if _ok:
                print(f"  [PASS] 'scattered' fills 2 of its 3 non-contiguous "
                      f"runs in BOTH payloads (STREAMZ into the 261-word "
                      f"opening, WarpFold into the big run)")

    # ---- FX1 rows (Remix.fx1) -------------------------------------------
    # The schema half. The BUILD half -- the relocated list, FX1's own id and
    # cursor tables, and stock's eleven rows unchanged and still first -- is
    # tools/verify_menu.py, which needs a built image and so runs there.
    try:
        schema.Remix(name="_x", doc="_", modules=("WARPFOLD",),
                     fallback=schema.NO_FALLBACK, fx1=("WARPFOLD", "WARPFOLD"))
        bad += 1
        print("  [FAIL] Remix(fx1=...) accepted a duplicate key")
    except ValueError:
        print("  [PASS] Remix(fx1=...) refuses a duplicate key")
    # A STOCK effect may be on the FX1 list without an FX2 row -- the two
    # lists are independent -- so the schema deliberately does NOT require
    # every fx1 key to be in `modules`. Pinned, because it was required for
    # one day and that would have made a curated FX1 chooser impossible.
    try:
        schema.Remix(name="_x", doc="_", modules=("WARPFOLD",),
                     fallback=schema.NO_FALLBACK, fx1=("FILTER", "WARPFOLD"))
        print("  [PASS] an fx1 row may be a stock effect with no FX2 row")
    except ValueError as e:
        bad += 1
        print(f"  [FAIL] Remix(fx1=...) refused a stock key: {e}")
    # A module of ours is FX2-only until a remix says otherwise, and then it
    # is on both -- this is the derivation the remixer's menus column and
    # every resource line read.
    _wf = registry.modules()["WARPFOLD"]
    if rig.menus(_wf) != (rig.FX2,):
        bad += 1
        print(f"  [FAIL] WarpFold is {rig.menus(_wf)} with no fx1 row")
    elif rig.menus(_wf, {"WARPFOLD"}) != (rig.FX1, rig.FX2):
        bad += 1
        print(f"  [FAIL] WarpFold is {rig.menus(_wf, {'WARPFOLD'})} with one")
    else:
        print("  [PASS] an fx1 row moves a module from FX2 to FX1+FX2")
    # ⚠️ ONLY A BUFFER-FREE INSERT MAY TAKE AN FX1 ROW. The measured reason
    # is docs/DSP.md's "wrong claim 1": a 16K layout at an FX1 base runs
    # through the other FX1 buffers and into FX2 slot 0. Pinned per module so
    # a manifest that starts reading the allocator cannot quietly become
    # eligible.
    _want = {"NIMBUS LITE": "sizes its buffer", "NIMBUS": "fixed FX2",
             "REVERB SERVER": "bus server", "DELAY SERVER": "bus server",
             "WARPFOLD": None, "RIPPLE": None, "RUNGS": None,
             "STREAMZ": None, "BODESHIFT": None, "HELLO WORLD": None}
    for _k, _frag in _want.items():
        _why = state.fx1_hazard(registry.modules()[_k])
        if (_frag is None) != (_why is None) or (_frag and _frag not in _why):
            bad += 1
            print(f"  [FAIL] fx1_hazard({_k}) = {_why!r}, wanted "
                  f"{_frag!r}")
    print(f"  [PASS] {len(_want)} modules classified for an FX1 row "
          f"({sum(v is None for v in _want.values())} eligible)")

    # WHAT EVERY SHIPPED FX1 CHOOSER MAY HOLD. A stock effect must be one
    # FX1 already lists (DELAY and the reverbs are FX2-only because they do
    # not fit a 3,072-word FX1 allocation); a module of ours must have an FX2
    # row -- that is where its descriptor clone comes from -- must not be a
    # `replaces` (which already inherits an FX1 row) and must clear
    # fx1_hazard.
    from remix import stock as _stk
    for _n in registry.remix_names():
        _r = registry.remix(_n)
        for _k in _r.fx1:
            _m = registry.modules().get(_k)
            if _m is None or _m.menu is None:
                bad += 1
                print(f"  [FAIL] remix {_n!r}: fx1={_k!r} is not an effect")
                continue
            if _m.is_stock:
                if _m.menu.fx2_id not in _stk.fx1_ids():
                    bad += 1
                    print(f"  [FAIL] remix {_n!r}: stock {_k} is FX2-only")
                _rep = [x for x in _r.modules if registry.modules()[x].menu is not None
                        and registry.modules()[x].menu.replaces == _k]
                if _rep:
                    bad += 1
                    print(f"  [FAIL] remix {_n!r}: fx1 lists stock {_k}, "
                          f"which {_rep[0]} replaces -- list the "
                          f"replacement")
                continue
            if _k not in _r.modules:
                bad += 1
                print(f"  [FAIL] remix {_n!r}: {_k} has no FX2 row, so there "
                      f"is no descriptor clone for FX1 to point at")
            _why = state.fx1_hazard(_m)
            if _why:
                bad += 1
                print(f"  [FAIL] remix {_n!r}: {_k} on FX1 -- {_why}")
    print("  [PASS] every shipped FX1 chooser holds only what FX1 can host")

    # And the real thing: every shipped remix must be clean.
    for name in registry.remix_names():
        r = registry.remix(name)
        found = ledger.check(registry.selected(r))
        if found:
            bad += 1
            print(f"  [FAIL] remix {name!r} has collisions: {found}")
        else:
            print(f"  [PASS] remix {name!r} is clean")

    print("\nOK" if not bad else f"\n{bad} FAILED")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
