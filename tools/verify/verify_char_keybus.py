#!/usr/bin/env python3
"""Character's KEY = T1..T8 from SIDECHAIN_COMPRESSOR's keybus.

The master (T8 ignores KEY) is not covered: the image has no BusVerb, so no
track is the master. dsp_host calls each effect's proc directly, so the dispatcher hook that
publishes the keybus (sctap) never runs. The words sctap would write are
planted with -pokey instead: a 32-word block (L = R = A) in the key track's
keybus slot (core A: Y:$800 + track * $40; core B's private Y is not reachable
from -pokey) or in the other core's shared-window slot (all four generations).
This proves the read: the slot address, the same-core / foreign branch on both
payloads, the 16-frame peak, KLVL. It does not prove sctap's writes or the
timing between the cores (the build of the tap is SIDECHAIN_COMPRESSOR's).

Every fed instance hears one 0.05 tone. Ducking is the station's gain at
KEY = SELF minus its gain at the key under test, COMP 127.

  A T6 <- T5       keybus on the same core:                 ducks
  A T6 <- T1       window slot of the other core:           ducks
  B T3 <- T5       window slot, polarity of payload B:      ducks
  B T3 <- T1       own-core track, window slots planted:    no duck (not read)
  A T6 <- T7       a keybus slot nothing planted:           no duck
  KLVL             key 0.125 at KLVL 127 ducks like 0.25 at KLVL 64
  SELF             KEY = SELF is bit-identical whatever is planted
  KEY 9            a KEY byte above 8 reads as SELF

    python3 tools/verify/verify_char_keybus.py      # ~1 min
"""
import pathlib
import shutil
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
import send_probe  # noqa: E402
import verify_one_bus as ob  # noqa: E402

ob.REMIX = "character-key"
ob.SCRATCH = ob.OUT / "_charkeybus"
KEY = "CHARACTER"
GR_MIN, GR_IDLE = 6.0, 0.5
GEN_ADDR = {"A": 0x33e00, "B": 0x3be00}      # a core's own shared-window half


def plant(addr, amp):
    w = int(amp * 8388607) & 0xffffff
    return ",".join(f"{addr + i:x}={w:06x}" for i in range(32))


def keybus(track0, amp):
    """core A's private keybus slot for absolute track 0..7"""
    return plant(0x800 + track0 * 0x40, amp)


def window(owner, local, amp):
    """`owner`'s shared-window slots for its local track, all four generations"""
    return ",".join(plant(GEN_ADDR[owner] + (local * 4 + g) * 0x20, amp) for g in range(4))


def check_layout():
    """the tap's addresses Character substitutes are the tap module's own"""
    from remix import registry
    sc = registry.by_key("SIDECHAIN_COMPRESSOR").dsp.subst
    ch = registry.by_key(KEY).dsp.subst
    for pl in "AB":
        for tok, val in ch[pl].items():
            if tok == "@CK_FOREIGN@":
                want = sc[pl]["@FOREIGN_BR@"].replace("zz24", "ch_kfor")
            else:
                want = sc[pl][tok]
            if want != val:
                sys.exit(f"payload {pl}: {tok} is {val!r} here, {want!r} in SIDECHAIN_COMPRESSOR")


def main():
    check_layout()
    ob.SCRATCH.mkdir(parents=True, exist_ok=True)
    snap = ob.SCRATCH / "mainos_bus.snapshot.bin"
    had = ob.IMAGE.is_file()
    if had:
        shutil.copy2(ob.IMAGE, snap)
    try:
        ob.build({}, ob.SCRATCH / "build.log")
        A = send_probe.dump_mem(ob.IMAGE, ob.SCRATCH / "A.mem", "A")
        B = send_probe.dump_mem(ob.IMAGE, ob.SCRATCH / "B.mem", "B")
    finally:
        if had:
            shutil.copy2(snap, ob.IMAGE)
    mems = {0: A, 1: B}
    ob.tone_file(ob.SCRATCH / "t.raw", ob.BLOCKS, amp=0.05)

    def gain(core, pos, extra="", **k):
        i = ob.Inst(KEY, core, pos, fx=1, fed=True, **{"COMP": 127, "KLVL": 64, **k})
        st = ob.run(mems, [i], tone="t.raw", tag=f"c{core}p{pos}",
                    extra=("-pokey", extra) if extra else ())[0][0]
        return st, ob.rms_db(st[len(st) // 2:])

    bad = []

    def check(ok, what):
        print(f"  [{'PASS' if ok else 'FAIL'}] {what}")
        if not ok:
            bad.append(what)

    def duck(core, pos, extra, **k):
        s, g = gain(core, pos, extra, **k)
        _, g0 = gain(core, pos, extra, KEY=0)
        return g0 - g

    # core A = tracks 5-8 (T6 = position 1), core B = tracks 1-4 (T3 = position 2)
    print("== the key is read from the keybus ==")
    d = duck(0, 1, keybus(4, 0.25), KEY=5)
    check(d >= GR_MIN, f"A T6 <- T5, same core: ducks {d:.1f} dB (>= {GR_MIN})")
    d = duck(0, 1, window("B", 0, 0.25), KEY=1)
    check(d >= GR_MIN, f"A T6 <- T1, other core: ducks {d:.1f} dB (>= {GR_MIN})")
    d = duck(1, 2, window("A", 0, 0.25), KEY=5)
    check(d >= GR_MIN, f"B T3 <- T5, other core: ducks {d:.1f} dB (>= {GR_MIN})")
    d = duck(1, 2, window("B", 0, 0.25) + "," + window("A", 0, 0.25), KEY=1)
    check(abs(d) <= GR_IDLE, f"B T3 <- T1, own core (window planted, not read): {d:.2f} dB (|x| <= {GR_IDLE})")
    d = duck(0, 1, keybus(4, 0.25), KEY=7)
    check(abs(d) <= GR_IDLE, f"A T6 <- T7, nothing planted: {d:.2f} dB (|x| <= {GR_IDLE})")

    print("== KLVL ==")
    a = duck(0, 1, keybus(4, 0.25), KEY=5, KLVL=64)
    b = duck(0, 1, keybus(4, 0.125), KEY=5, KLVL=127)
    check(abs(a - b) <= 1.0, f"0.25 at KLVL 64 ducks {a:.1f} dB, 0.125 at KLVL 127 ducks {b:.1f} dB")

    print("== SELF and a KEY above 8 ==")
    p = keybus(4, 0.25)
    s1 = gain(0, 1, p, KEY=0)[0]
    s2 = gain(0, 1, "", KEY=0)[0]
    check(s1 == s2, "KEY = SELF: bit-identical with the keybus planted or empty")
    s1 = gain(0, 1, p, KEY=9)[0]
    s2 = gain(0, 1, p, KEY=0)[0]
    check(s1 == s2, "KEY 9: bit-identical with KEY = SELF")

    print(f"\n{'PASS' if not bad else 'FAIL'}: {len(bad)} failing")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
