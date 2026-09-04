#!/usr/bin/env python3
"""A HIDDEN engine is placed, dispatched, off the chooser and draws nothing.

    python3 tools/verify_hidden.py [remix]      (default: bamsep27)

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

What this CANNOT prove is the panel itself: that a real [FX2] press on the
host draws an empty page rather than a stale one. That is the flash's.
"""
import os
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
BASE = 0x40000400
IMAGE = pathlib.Path("out/mainos_bus.bin")
P_PARAM_NAMES, P_DEFAULTS = 0x16, 0x5e
P_PENABLE_LO, P_PENABLE_HI = 0x18e, 0x18a
FX2_IDS, ID2POS = 0x400d5fdc, 0x400d6150   # build_bus.py's own
NEW_LIST, LONG_LIST = 0x400d6b00, 0x400d7bbc
WRITER = 0x40054cd8


def main():
    from remix import registry
    name = sys.argv[1] if len(sys.argv) > 1 else "bamsep27"
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
    r = subprocess.run([sys.executable, "tools/build_bus.py"],
                       capture_output=True, text=True, env=env)
    if r.returncode != 0:
        tail = (r.stdout + r.stderr).strip().splitlines()
        sys.exit(f"{name}: build failed: {tail[-1] if tail else '?'}")
    img = IMAGE.read_bytes()
    fails = 0

    def check(label, ok, detail=""):
        nonlocal fails
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}"
              f"{'  ' + detail if detail else ''}")
        fails += 0 if ok else 1

    def u32(a):
        return int.from_bytes(img[a - BASE:a - BASE + 4], "big")

    # ---- 1. the image ----------------------------------------------------
    fb_id = mods[remix.fallback].menu.fx2_id
    fb_pos = u32(ID2POS + fb_id * 4)
    clones = {}
    for key in hidden + listed:
        clones[key] = u32(FX2_IDS + mods[key].menu.fx2_id * 4)
    for key in hidden:
        P = clones[key]
        check(f"{key}: its id resolves to a clone of its own",
              0x400d6b20 <= P < 0x400d7c3c and P not in
              [clones[o] for o in clones if o != key], f"0x{P:08x}")
        names = [bytes(img[P - BASE + P_PARAM_NAMES + 6 * i:][:6]).split(b"\0")[0]
                 for i in range(12)]
        check(f"{key}: all twelve parameter names are blank",
              not any(names), " ".join(n.decode("latin1") or "-" for n in names))
        defaults = list(img[P - BASE + P_DEFAULTS:][:12])
        want = [(p.default or 0) & 0x7f for p in mods[key].params]
        check(f"{key}: its defaults are the manifest's, untouched by hiding",
              defaults == want, f"{defaults[:6]}...")
        lo, hi = u32(P + P_PENABLE_LO), u32(P + P_PENABLE_HI)
        check(f"{key}: its enable bits are set, so the DSP still receives",
              (lo & 0x11111111) == 0x11111111 and (hi & 0x11111111) != 0,
              f"lo={lo:08x} hi={hi:08x}")
        check(f"{key}: its cursor entry is the fallback's, not stock's",
              u32(ID2POS + mods[key].menu.fx2_id * 4) == fb_pos, f"{fb_pos}")

    # the chooser list is exactly the listed modules
    for cand in (NEW_LIST, LONG_LIST):
        row = [u32(cand + 4 * i) for i in range(16)]
        if row[0] in clones.values():
            entries = []
            for v in row:
                if v == 0:
                    break
                entries.append(v)
            listed_p = [clones[k] for k in listed]
            check("the chooser lists exactly the modules that are not hidden",
                  entries == listed_p,
                  f"{len(entries)} rows at 0x{cand:08x}, expected {len(listed_p)}")
            for key in hidden:
                check(f"{key} is not in the chooser list",
                      clones[key] not in entries)
            break
    else:
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
    key = hidden[0]
    hid_id = mods[key].menu.fx2_id
    base_texts = set(texts(emu.render_fx2(boot, track=4, effect_id=0x02)))
    drew_hidden = set(texts(emu.render_fx2(boot, track=4, effect_id=hid_id)))
    hid_names = {p.name.decode("latin1") for p in mods[key].params if p.name}
    check(f"{key}'s page draws none of its knob names",
          not (hid_names & (drew_hidden - base_texts)),
          " ".join(sorted(hid_names & (drew_hidden - base_texts))) or "none drawn")
    ctl = listed[0] if listed else None
    if ctl and not mods[ctl].is_stock:
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
    mem = "out/dsp/payload_A.mem"
    if pathlib.Path(mem).exists():
        ent = send_probe.entry_points(mem, hid_id)
        fb = send_probe.entry_points(mem, fb_id)
        check(f"{key}'s DSP entry points are its own, not {remix.fallback}'s",
              ent != fb, f"init=P:0x{ent[0]:04x} vs 0x{fb[0]:04x}")

    print(f"\n{fails} check(s) failed" if fails else "\nOK")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
