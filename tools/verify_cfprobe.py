#!/usr/bin/env python3
"""The ColdFire headroom probe does its arithmetic -- driven, not read.

    python3 tools/verify_cfprobe.py [remix]      (default: cfprobe)

 1. THE IMAGE. The hook at 0x40004b12 is `jsr cave ; nop` with the addq
    before it and the move.l after it untouched; the cave's bytes are the
    pinned ones; HELLO WORLD's slot-0 formatter points at cave+0x100 and its
    widget word is zero.
 2. THE PROBE, on the booted machine. The frame routine is stubbed to `rts`
    (its real body is DMA descriptor arithmetic against peripherals the
    emulator reads as all-ones) and DMA timer 3's counter is scripted, so
    every delta is known. The probe is called as the audio interrupt would
    call it: the first frame is discarded (no last_t0), 1,024 good frames
    publish a window with the expected sums and max, a counter reset is
    discarded, the burn loop runs fader*128 times, and the second window's
    max is the one spiked frame.
 3. THE READOUT. The formatter is called with a buffer and one value per
    band, before any window ("-") and after the second, and the strings are
    what the arithmetic in cfprobe.s predicts.

What this CANNOT prove: any number of ticks. Unicorn has no cycle model, so
the routine's real cost and the starvation point are the flash's to find.
modules/cfprobe/README.md is the procedure.
"""
import os
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
BASE = 0x40000400
IMAGE = pathlib.Path("out/mainos_bus.bin")
HOOK = 0x40004b12
FRAME_ROUTINE = 0x400031a0
DTCN3 = 0xfc07c00c
FADER = 0x460d16c8
SPRINTF_BUF = 0x47f10000
PERIOD, ROUTINE, WINDOW, LIMIT = 47891, 12000, 1024, 0x100000
ST = {"last": 0, "sum_r": 4, "sum_t": 8, "sum_p": 12, "max": 16, "n": 20,
      "pub_r": 24, "pub_t": 28, "pub_p": 32, "pub_max": 36, "pub_n": 40,
      "windows": 44}


def main():
    from remix import registry
    name = sys.argv[1] if len(sys.argv) > 1 else "cfprobe"
    remix = registry.remix(name)
    if "CF PROBE" not in remix.modules:
        print(f"  [ -- ] {name} does not carry CF PROBE -- nothing to check")
        return 0
    mod = registry.modules()["CF PROBE"]
    cave = mod.cf_patches[0]
    pinned, fmt_off = cave.pinned, cave.registers_formatter.offset
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

    def u32(buf, a):
        return int.from_bytes(buf[a - BASE:a - BASE + 4], "big")

    # ---- 1. the image ----------------------------------------------------
    at = img.find(pinned)
    check("the cave's pinned bytes are in the image exactly once",
          at >= 0 and img.find(pinned, at + 1) < 0)
    if at < 0:
        print(f"\n{fails} check(s) failed")
        return 1
    cave_addr = BASE + at
    site = img[HOOK - 6 - BASE:HOOK + 8 + 6 - BASE]
    want = (bytes.fromhex("46fc2500") + b"\x4e\xb9"
            + cave_addr.to_bytes(4, "big") + b"\x4e\x71"
            + bytes.fromhex("203946104d3e"))
    check("hook site: SR write, jsr cave, nop, then the stock move.l",
          site[2:] == want and site[:2] == bytes.fromhex("4d3e"),
          f"cave 0x{cave_addr:08x}")
    fmt_ptr = (cave_addr + fmt_off).to_bytes(4, "big")
    hits = [i for i in range(0, len(img) - 4, 2) if img[i:i + 4] == fmt_ptr]
    hello = BASE + hits[0] - 0x0ca if len(hits) == 1 else None
    check("HELLO WORLD slot 0's formatter is cave+0x%x, once" % fmt_off,
          hello is not None, f"descriptor 0x{hello:08x}" if hello else
          f"{len(hits)} hits")
    if hello:
        check("its widget word (B) is zero: a plain dial that prints A",
              u32(img, hello + 0x0fa) == 0)
    check("the formatter entry is the expected prologue (move.l d2,-(sp))",
          pinned[fmt_off:fmt_off + 2] == b"\x2f\x02")

    # ---- 2. the probe, driven --------------------------------------------
    import emu_bringup as emu
    from unicorn import UC_HOOK_CODE
    boot = emu.boot(str(IMAGE))
    uc = boot.uc
    uc.mem_write(FRAME_ROUTINE, b"\x4e\x75")          # rts: stub the routine
    try:
        uc.ctl_flush_tb()
    except Exception:
        pass
    script = {"t": 0x10000000, "reads": []}

    def dtcn_read(u, off, size, data):
        # Each read hands out the scripted counter and advances it by the
        # next scripted step: t0, then +routine, then +burn.
        v = script["t"]
        script["reads"].append(v)
        step = script["steps"].pop(0) if script.get("steps") else 0
        script["t"] = (v + step) & 0xffffffff
        return v

    uc.mem_unmap(0xfc07c000, 0x1000)
    uc.mmio_map(0xfc07c000, 0x1000, dtcn_read, None, None, None)
    check("DMA timer 3's page is now the scripted counter", True)
    calls = {"routine": 0, "burn": 0}
    uc.hook_add(UC_HOOK_CODE, lambda u, a, s, d: calls.__setitem__(
        "routine", calls["routine"] + 1), begin=FRAME_ROUTINE, end=FRAME_ROUTINE)
    burn_subq = cave_addr + pinned.find(bytes.fromhex("5380" "66f4"))
    uc.hook_add(UC_HOOK_CODE, lambda u, a, s, d: calls.__setitem__(
        "burn", calls["burn"] + 1), begin=burn_subq, end=burn_subq)
    st = cave_addr + pinned.rfind(b"-\x00") + 2
    st = (st + 3) & ~3

    def state(k):
        return int.from_bytes(uc.mem_read(st + ST[k], 4), "big")

    def frame(routine=ROUTINE, burn=0, gap=PERIOD, fader=0):
        # gap: this frame's t0 minus the last frame's t0.
        uc.mem_write(FADER, fader.to_bytes(4, "big"))
        t0 = (script["t0"] + gap) & 0xffffffff if "t0" in script else script["t"]
        script["t"], script["t0"] = t0, t0
        script["steps"] = [routine, burn, 0]
        emu._call(uc, cave_addr, ())

    frame()                                            # no last_t0 yet
    check("the first frame is discarded (no previous t0)",
          state("n") == 0 and state("last") == 0x10000000,
          f"n={state('n')} last=0x{state('last'):08x}")
    check("the frame routine was called once", calls["routine"] == 1)
    for _ in range(WINDOW):
        frame()
    check(f"{WINDOW} good frames publish a window",
          state("windows") == 1 and state("pub_n") == WINDOW
          and state("n") == 0 and state("sum_t") == 0,
          f"windows={state('windows')} pub_n={state('pub_n')}")
    check("published sums are frames x routine, frames x period, max = routine",
          state("pub_r") == WINDOW * ROUTINE and state("pub_t") == WINDOW * ROUTINE
          and state("pub_p") == WINDOW * PERIOD and state("pub_max") == ROUTINE)
    frame(gap=-5_000_000)                              # the counter was zeroed
    check("a counter reset under the probe is discarded",
          state("n") == 0, f"n={state('n')}")
    frame(gap=LIMIT + 1)                               # a stalled frame
    check("a period past the limit is discarded", state("n") == 0)
    frame(routine=PERIOD + 1)                          # busy longer than the period
    check("a frame busier than its period is discarded", state("n") == 0)
    before = calls["burn"]
    frame(burn=18000, fader=64)
    check("fader 64 burns 64 x 128 iterations", calls["burn"] - before == 64 * 128,
          f"{calls['burn'] - before}")
    check("the burn counts in total but not in routine",
          state("sum_t") == ROUTINE + 18000 and state("sum_r") == ROUTINE)
    for _ in range(WINDOW - 2):
        frame(burn=18000, fader=0)                     # scripted burn, no loop
    frame(burn=28000)                                  # the spike
    check("the second window's max is the spiked frame",
          state("windows") == 2 and state("pub_max") == ROUTINE + 28000,
          f"windows={state('windows')} max={state('pub_max')}")

    # ---- 3. the readout --------------------------------------------------
    def fmt(value):
        uc.mem_write(SPRINTF_BUF, b"\0" * 16)
        emu._call(uc, cave_addr + fmt_off, (SPRINTF_BUF, value))
        raw = bytes(uc.mem_read(SPRINTF_BUF, 16))
        return raw[:raw.find(b"\0")].decode("ascii", "replace")

    pub_t = (WINDOW - 1) * (ROUTINE + 18000) + ROUTINE + 28000
    pub_p = WINDOW * PERIOD
    want = {127: f"t{pub_t // (pub_p // 100)}", 96: f"t{pub_t // (pub_p // 100)}",
            95: f"r{WINDOW * ROUTINE // (pub_p // 100)}",
            63: f"x{(ROUTINE + 28000) * 100 // PERIOD}", 0: f"{PERIOD}"}
    for v, s in want.items():
        got = fmt(v)
        check(f"GAIN {v:3d} draws {s!r}", got == s, f"got {got!r}")
    # A machine with no window yet draws "-": zero the published block.
    uc.mem_write(st + ST["pub_n"], b"\0\0\0\0")
    check("before the first window every band draws '-'",
          all(fmt(v) == "-" for v in (0, 40, 70, 127)))

    print(f"\n{fails} check(s) failed" if fails else "\nOK")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
