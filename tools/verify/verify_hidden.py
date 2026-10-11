#!/usr/bin/env python3
"""A HIDDEN engine is placed, dispatched, off the chooser and draws nothing.

    python3 tools/verify/verify_hidden.py [remix]      

`Remix.hidden` takes an effect off the panel without taking it out of the
image: the project's stored id still reaches it, and a main-menu screen edits
it through the firmware's own parameter writer. Four things have to hold at
once for that to be true, and three of them are invisible in the build report.

 1. THE IMAGE. The engine's clone exists and its id points at it; its twelve
    parameter NAMES are blank while its counts, defaults and enable bits are
    the manifest's; it is absent from the chooser list, which is exactly the
    listed modules and no more; and its cursor entry is the fallback's rather
    than stock's leftover.
 2. THE PAGE, on the booted machine. Rendering the host track's FX2 page
    draws no knob names at all -- and the same render with a LISTED module
    assigned draws its names, so the check can fail.
 3. THE WRITER, on the booted machine. The stock parameter writer still lands
    a value in the Part for a hidden engine's slot: blanking names must not
    cost the menu screen its edit path.
 4. THE CODE. The engine's DSP entry points are its own, not the fallback's
    -- the guard `send_probe` grew when a missing effect silently rendered as
    a SEND.
 5. THE HOST GUARD, rendered through dsp_host. A hidden engine runs on the
    bank's first FX2 state block and passes dry on every other, so an old
    part naming its id on another track cannot get a second instance sharing
    its hardcoded Y base. Both halves are rendered, because "it went dry" and
    "it never ran at all" look the same from one render.

What this CANNOT prove is the panel itself: that a real [FX2] press on the
host draws an empty page rather than a stale one. That is the flash's.
"""
import os
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401  (every tools/ dir on sys.path)
BASE = 0x40000400
IMAGE = pathlib.Path("out/mainos_bus.bin")
P_PARAM_NAMES, P_DEFAULTS = 0x16, 0x5e
P_PENABLE_LO, P_PENABLE_HI = 0x18e, 0x18a
FX2_IDS, ID2POS = 0x400d5fdc, 0x400d6150   # build_bus.py's own
NEW_LIST, LONG_LIST = 0x400d6b00, 0x400d7bbc
WRITER = 0x40054cd8


def main():
    from remix import registry
    name = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("REMIX")
    remix = registry.remix(name)
    mods = registry.modules()
    hidden = [k for k in remix.modules
              if mods[k].menu is not None and k in remix.hidden]
    listed = [k for k in remix.modules
              if mods[k].menu is not None and k not in remix.hidden]
    if not hidden:
        print(f"  [ -- ] {name} hides nothing -- nothing to check")
        return 0
    env = {**os.environ, "REMIX": name, "XBUS": "1", "SPEC": "1"}
    r = subprocess.run([sys.executable, "tools/build/build_bus.py"],
                       capture_output=True, text=True, env=env)
    if r.returncode != 0:
        tail = (r.stdout + r.stderr).strip().splitlines()
        sys.exit(f"{name}: build failed: {tail[-1] if tail else '?'}")
    from remix import booted
    img = booted.image(IMAGE.read_bytes())
    fails = 0

    def check(label, ok, detail=""):
        nonlocal fails
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}"
              f"{'  ' + detail if detail else ''}")
        fails += 0 if ok else 1

    def u32(a):
        return int.from_bytes(img[a - BASE:a - BASE + 4], "big")

    # ---- 1. the image ----------------------------------------------------
    # fallback NONE: the build points id 0 (the firmware's own NONE) and the
    # hidden modules' cursor entries at row 0 (build_bus.py, fb_pos)
    from remix.schema import NO_FALLBACK
    fb_id = 0x00 if remix.fallback == NO_FALLBACK else mods[remix.fallback].menu.fx2_id
    fb_pos = u32(ID2POS + fb_id * 4)
    clones = {}
    for key in hidden + listed:
        clones[key] = u32(FX2_IDS + mods[key].menu.fx2_id * 4)
    for key in hidden:
        P = clones[key]
        check(f"{key}: its id resolves to a clone of its own",
              (0x400d6b20 <= P < 0x400d7c3c or P >= 0x40a955e0) and P not in
              [clones[o] for o in clones if o != key], f"0x{P:08x}")
        names = [bytes(img[P - BASE + P_PARAM_NAMES + 6 * i:][:6]).split(b"\0")[0]
                 for i in range(12)]
        # ⚠️ A HIDDEN MODULE THAT IS ALSO ON FX1 KEEPS ITS NAMES. One
        # descriptor serves both menus, so blanking it would empty its FX1
        # page too -- the stations are hidden from the FX2 chooser and still
        # have to draw when they are selected on FX1.
        nhost = dict(remix.host_slots).get(key)
        if nhost is not None:
            want = [(p.name or b"") if i < nhost else b"" for i, p in enumerate(mods[key].params)]
            check(f"{key}: host_slots, so slots 0-{nhost - 1} keep their names and the rest are blank",
                  names == want,
                  " ".join(n.decode("latin1") or "-" for n in names))
        elif key not in remix.blanked:
            want = [(p.name or b"") for p in mods[key].params]
            why = "on FX1" if key in remix.fx1 else "NAMED"
            check(f"{key}: {why}, so its names are KEPT, not blanked",
                  names == want,
                  " ".join(n.decode("latin1") or "-" for n in names[:6]))
        else:
            check(f"{key}: all twelve parameter names are blank",
                  not any(names),
                  " ".join(n.decode("latin1") or "-" for n in names))
        # ⚠️ OVER THE ACTIVE SLOTS ONLY. A module need not use all twelve --
        # SEND has two knobs -- and an inactive slot keeps whatever byte the
        # cloned DONOR had there, which is not a defect and not the
        # manifest's. Checking all twelve reported SEND as broken.
        act = [i for i, p in enumerate(mods[key].params) if p.active]
        defaults = list(img[P - BASE + P_DEFAULTS:][:12])
        want = [(p.default or 0) & 0x7f for p in mods[key].params]
        check(f"{key}: its {len(act)} active defaults are the manifest's",
              all(defaults[i] == want[i] for i in act),
              " ".join(f"{defaults[i]}" for i in act[:6]))
        lo, hi = u32(P + P_PENABLE_LO), u32(P + P_PENABLE_HI)
        bits = ((hi & 0xffffffff) << 32) | (lo & 0xffffffff)
        on = [i for i in range(12) if (bits >> (4 * i)) & 1]
        check(f"{key}: exactly its active slots are enabled, so the DSP "
              f"still receives", on == act,
              f"enabled {on} vs active {act}")
        check(f"{key}: its cursor entry is the fallback's, not stock's",
              u32(ID2POS + mods[key].menu.fx2_id * 4) == fb_pos, f"{fb_pos}")

    # the chooser list is exactly the listed modules
    # ⚠️ AN EMPTY CHOOSER IS A VALID OUTCOME, and the loop below cannot find
    # a list that has no rows: with every module hidden the list is a bare
    # terminator. Check that shape directly rather than reporting "not found".
    listed_p = [clones[k] for k in listed]
    if not listed_p:
        check("the chooser list is empty: a bare terminator, no rows",
              u32(NEW_LIST) == 0, f"first word 0x{u32(NEW_LIST):08x}")
        for key in hidden:
            check(f"{key} is not in the chooser list", True)
        cand = None
    # fallback NONE: the build restores the firmware's NONE row at row 0
    # (build_bus.py, "with NONE at row 0"), so the listed modules start at 1
    skip = 1 if remix.fallback == NO_FALLBACK else 0
    for cand in ((NEW_LIST, LONG_LIST) if listed_p else ()):
        row = [u32(cand + 4 * (i + skip)) for i in range(16)]
        if row[0] in clones.values():
            entries = []
            for v in row:
                if v == 0:
                    break
                entries.append(v)
            check("the chooser lists exactly the modules that are not hidden",
                  entries == listed_p,
                  f"{len(entries)} rows at 0x{cand:08x}, expected {len(listed_p)}")
            for key in hidden:
                check(f"{key} is not in the chooser list",
                      clones[key] not in entries)
            break
    else:
        if listed_p:
            check("found the chooser list in the image", False)

    # ---- 2 and 3. the booted machine -------------------------------------
    import emu_bringup as emu
    from unicorn import UcError
    boot = emu.boot(str(IMAGE))
    uc = boot.uc
    uc.mem_map(0x100a0000, 0x10000)

    def texts(draws):
        return [t for _, _, t in draws if t.strip()]

    # ⚠️ THE CAPTURE INCLUDES THE PLAYBACK PAGE, whose own knobs (LEV PTCH
    # STRT LEN RATE RTRG RTIM) are redrawn with the FX2 page. RATE is also
    # BusVerb's slot 11, so comparing the engine's names against the raw
    # capture reports a knob that is not the engine's. Subtract a baseline
    # render -- the same track with an id that draws nothing of its own.
    base_texts = set(texts(emu.render_fx2(boot, track=4, effect_id=0x02)))

    def drawn_names(key):
        drew = set(texts(emu.render_fx2(boot, track=4,
                                        effect_id=mods[key].menu.fx2_id)))
        names = {p.name.decode("latin1") for p in mods[key].params if p.name}
        return names & (drew - base_texts)
    blanked = [k for k in hidden if k in remix.blanked]
    # the module sections 3-5 below exercise: a blanked one if any, else the
    # first hidden (a NAMED host in the rig)
    key = blanked[0] if blanked else hidden[0]
    hid_id = mods[key].menu.fx2_id
    if blanked:
        got = drawn_names(key)
        check(f"{key}'s page draws none of its knob names",
              not got, " ".join(sorted(got)) or "none drawn")
    for key, nhost in remix.host_slots:
        drew = set(texts(emu.render_fx2(boot, track=4,
                                        effect_id=mods[key].menu.fx2_id)))
        shown = {p.name.decode("latin1") for p in mods[key].params[:nhost] if p.name}
        others = {p.name.decode("latin1") for p in mods[key].params[nhost:] if p.name} - base_texts - shown
        check(f"{key}: host_slots, so its page draws {' '.join(sorted(shown))} and none of its other names",
              shown <= drew and not (others & drew),
              f"drew {' '.join(sorted(drew - base_texts)) or 'nothing'}")
    for key in [k for k in hidden if k in remix.named]:
        got = drawn_names(key)
        # a name the PLAYBACK page also draws (PTCH, RATE ...) is in the
        # baseline and cannot be proven by this capture -- leave it out
        want = {p.name.decode("latin1") for p in mods[key].params[:6]
                if p.name} - base_texts
        check(f"{key}: NAMED, so its host page DRAWS its page-1 knob names",
              want <= got, f"drew {' '.join(sorted(got)) or 'nothing'}; "
              f"missing {' '.join(sorted(want - got)) or 'none'}")
    # the control: a module whose names ARE drawn -- a listed one, or a
    # hidden one kept for FX1
    ctl = next((k for k in listed if not mods[k].is_stock),
               next((k for k in hidden if k in remix.fx1), None))
    if ctl:
        drew_listed = set(texts(emu.render_fx2(boot, track=4,
                                               effect_id=mods[ctl].menu.fx2_id)))
        ctl_names = {p.name.decode("latin1") for p in mods[ctl].params if p.name}
        check(f"the same render DOES draw {ctl}'s names, so the check can fail",
              bool(ctl_names & (drew_listed - base_texts)),
              " ".join(sorted(ctl_names & (drew_listed - base_texts))[:4]))

    emu.assign_fx2(boot, track=4, effect_id=hid_id)
    part = emu.FAKE_PART
    lo_a, hi_a = part + 0x8e000, part + 0x92000
    before = bytes(uc.mem_read(lo_a, hi_a - lo_a))
    try:
        # the call our modules make
        emu._call(uc, WRITER, (4, 0, 99))
    except UcError:
        pass
    after = bytes(uc.mem_read(lo_a, hi_a - lo_a))
    moved = [i for i in range(len(before)) if before[i] != after[i]]
    check(f"the stock writer still lands a value for {key} slot 0",
          any(after[i] == 99 for i in moved),
          f"{len(moved)} byte(s) changed")

    # ---- 4. the code -----------------------------------------------------
    import send_probe
    mem = "out/dsp/mem_dev_A.mem"
    if pathlib.Path(mem).exists():
        ent = send_probe.entry_points(mem, hid_id)
        fb = send_probe.entry_points(mem, fb_id)
        check(f"{key}'s DSP entry points are its own, not {remix.fallback}'s",
              ent != fb, f"init=P:0x{ent[0]:04x} vs 0x{fb[0]:04x}")

    # ---- 5. THE HOST GUARD, rendered ------------------------------------
    # A hidden engine gets build_bus.py's HOSTGUARD: it runs on the bank's
    # first FX2 state block (r7 = 0x6200, dsp_host's `-r7 2`) and passes dry
    # on every other. Both halves are rendered here, because "it went dry"
    # and "it never ran" look identical from one render.
    import struct
    HOST = "vendor/dsp56300/build/source/dsp_host/dsp_host"
    # The DEV hatch's dump: build_bus.py writes it with DEV=1 XBUS=1, and it
    # is what send_probe and every render gate here already use.
    mem_a = pathlib.Path("out/dsp/mem_dev_A.mem")
    scratch = pathlib.Path("out/_hidden")
    scratch.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, "tools/build/build_bus.py"],
                   capture_output=True, text=True,
                   env={**os.environ, "REMIX": name, "DEV": "1", "XBUS": "1"})
    if pathlib.Path(HOST).exists() and mem_a.exists():
        FRAMES, N = 15, 6000
        src = scratch / "in.raw"
        import math
        samples = [int(0.4 * 8388607 * math.sin(2 * math.pi * 220 * i / 44100))
                   for i in range(N)]
        src.write_bytes(b"".join(struct.pack("<i", v) for v in samples))

        def render(key, r7, **over):
            # The DELAY HATCH dump (DEV=1 XBUS=1, no SPEC): every server is
            # real in payload A, which is the only dump that can render the
            # delay at all -- a SPEC dump aliases its id to SEND and would
            # render a plausible dry pass for the wrong reason.
            mem = "out/dsp/mem_dev_A.mem"
            if not pathlib.Path(mem).exists():
                return None
            init, proc = send_probe.entry_points(mem, mods[key].menu.fx2_id)
            # ONE AUX: an engine's only input is the aux bus --
            # its own AUX goes round through the accumulator, and that
            # needs a rotation, i.e. a housekeeper. A lone delay under the
            # DEV hatch is never the housekeeper (it behaves as payload B),
            # so the engine renders with a SEND at the other slot, fed the
            # tone at DEL 127 and REV 127: SEND's self-healing election keeps the bus
            # turning whichever slot the engine is on, and "runs" means the
            # sent tone comes out of the engine as wet.
            sinit, sproc = send_probe.entry_points(mem, send_probe.SERVER_ID["S"])
            # 5 = 0x6500, position 1's FX2: 0x6400 is an FX1 slot, where SEND
            # returns at once since image 48 and nobody housekeeps
            other = 5 if r7 == 2 else 2
            out = scratch / f"out_{r7}.raw"
            vals = [(p.default or 0) & 0x7f for p in mods[key].params]
            kmap = {(p.name or b"").decode("latin1"): i
                    for i, p in enumerate(mods[key].params)}
            for n, v in over.items():
                vals[kmap[n]] = v
            params = ",".join(str(v) for v in vals)
            r = subprocess.run(
                [HOST, "-mem", mem, "-init", f"{init:x},{sinit:x}",
                 "-proc", f"{proc:x},{sproc:x}",
                 "-inst", "2", "-r7", f"{r7},{other}", "-alloc", "1,3",
                 "-inmask", "3",         # the engine's own track too: the
                                         # guard's dry pass is INPUT == OUTPUT
                 "-frames", str(FRAMES), "-blocks", str(N // FRAMES),
                 "-in", str(src), "-out", str(out), "-params", params,
                 "-params", "127,127,0,0,0,0,0,0,0,0,0,0"],   # SEND: DEL and REV
                capture_output=True, text=True)
            if r.returncode != 0:
                return None
            d = out.read_bytes()
            w = struct.unpack(f"<{len(d)//4}i", d)
            return list(w[0::2])[:N]

        for key in [k for k in hidden if k in ("REVERB SERVER", "DELAY SERVER")]:
            # ⚠️ AT ITS DEFAULTS AN ENGINE IS ALREADY A DRY PASS -- both
            # engines are RETURNS whose IN defaults to 0 (v5),
            # so a control render has to open the input, or "the guard went
            # dry" and "the engine is dry anyway" are the same picture.
            _names = [(p.name or b"").decode("latin1") for p in mods[key].params]
            # AUX since the one-aux rig: the host's own send
            # goes round through the accumulator and back into the engine
            wet = {} if "SEND" in _names else ({"IN": 127} if "IN" in _names else {})
            # The delay's default TIME (40 -> 5,184 samples) puts its first
            # repeat past this 6,000-sample window once the 256-call warm-up
            # is spent; TIME 0 (the 64-sample floor) brings the repeats in.
            if key == "DELAY SERVER" and "TIME" in _names:
                wet["TIME"] = 0
            host = render(key, 2, **wet)
            away = render(key, 5, **wet)
            if host is None or away is None:
                check(f"{key}: rendered at both slots", False, "dsp_host failed")
                continue
            check(f"{key} at r7=0x6500 is a BIT-EXACT dry pass",
                  away == samples,
                  f"{sum(1 for a, b in zip(away, samples) if a != b)} sample(s) differ")
            if host == samples and not wet:
                print(f"  [SKIP] {key} at r7=0x6200 really runs -- it has no "
                      f"own-track input (bus only), so this harness cannot "
                      f"tell a guarded instance from an unfed one")
            else:
                check(f"{key} at r7=0x6200 (its host) really runs",
                      host != samples,
                      f"{sum(1 for a, b in zip(host, samples) if a != b)} "
                      f"sample(s) differ")

    print(f"\n{fails} check(s) failed" if fails else "\nOK")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
