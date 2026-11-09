#!/usr/bin/env python3
"""Character's KEY = T1..T8 from KEYBUS's key words (modules/keybus).

The master (T8 ignores KEY) is not covered: the image has no BusVerb, so no
track is the master. dsp_host calls each effect's proc directly, so the
dispatcher hook that publishes the key words (KEYBUS's kbus_tap, gated by
verify_keybus) does not run here. The words it would write are planted
instead, as an X record at X:$37F60 + track in a copy of each payload's
dump. This proves the read: the address on both payloads, the KEY byte to
track, KLVL. It does not prove the tap's writes (verify_keybus) or the
timing between the cores.

Every fed instance hears one 0.05 tone. Ducking is the station's gain at
KEY = SELF minus its gain at the key under test, COMP 127.

  A T6 <- T5       a key word of the same core:             ducks
  A T6 <- T1       a key word of the other core:            ducks
  B T3 <- T5       a key word of the other core, payload B: ducks
  B T3 <- T1       a key word of the same core, payload B:  ducks
  A T6 <- T7       a key word nothing planted:              no duck
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
KEY_WORDS = 0x37F60                          # KEYBUS: track t's key word at X:$37F60 + t


def records(path):
    blob, pos, out = pathlib.Path(path).read_bytes(), 0, []
    while pos + 9 <= len(blob):
        sp, addr, cnt = struct.unpack_from("<BII", blob, pos)
        pos += 9
        if sp == 0xFF:
            break
        out.append((sp, addr, list(struct.unpack_from(f"<{cnt}I", blob, pos))))
        pos += 4 * cnt
    return out


def write_records(path, recs):
    path.write_bytes(b"".join(struct.pack("<BII", sp, a, len(w)) + struct.pack(f"<{len(w)}I", *w) for sp, a, w in recs)
                     + struct.pack("<BII", 0xFF, 0, 0))


def main():
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
    base = {0: records(A), 1: records(B)}

    def planted(keys):
        """both dumps with the eight key words: {track 0..7: amplitude}"""
        words = [int(keys.get(t, 0.0) * 8388607) & 0xffffff for t in range(8)]
        tag = "_".join(f"{t}{int(a * 1000)}" for t, a in sorted(keys.items())) or "none"
        out = {}
        for c, recs in base.items():
            m = ob.SCRATCH / f"{'AB'[c]}_{tag}.mem"
            write_records(m, recs + [(1, KEY_WORDS, words)])
            out[c] = m
        return out
    ob.tone_file(ob.SCRATCH / "t.raw", ob.BLOCKS, amp=0.05)

    def gain(core, pos, keys=None, **k):
        i = ob.Inst(KEY, core, pos, fx=1, fed=True, **{"COMP": 127, "KLVL": 64, **k})
        st = ob.run(planted(keys or {}), [i], tone="t.raw", tag=f"c{core}p{pos}")[0][0]
        return st, ob.rms_db(st[len(st) // 2:])

    bad = []

    def check(ok, what):
        print(f"  [{'PASS' if ok else 'FAIL'}] {what}")
        if not ok:
            bad.append(what)

    def duck(core, pos, keys, **k):
        s, g = gain(core, pos, keys, **k)
        _, g0 = gain(core, pos, keys, KEY=0)
        return g0 - g

    # core A = tracks 5-8 (T6 = position 1), core B = tracks 1-4 (T3 = position 2)
    print("== the key is read from KEYBUS's words ==")
    d = duck(0, 1, {4: 0.25}, KEY=5)
    check(d >= GR_MIN, f"A T6 <- T5, same core: ducks {d:.1f} dB (>= {GR_MIN})")
    d = duck(0, 1, {0: 0.25}, KEY=1)
    check(d >= GR_MIN, f"A T6 <- T1, other core: ducks {d:.1f} dB (>= {GR_MIN})")
    d = duck(1, 2, {4: 0.25}, KEY=5)
    check(d >= GR_MIN, f"B T3 <- T5, other core: ducks {d:.1f} dB (>= {GR_MIN})")
    d = duck(1, 2, {0: 0.25}, KEY=1)
    check(d >= GR_MIN, f"B T3 <- T1, same core: ducks {d:.1f} dB (>= {GR_MIN})")
    d = duck(0, 1, {4: 0.25}, KEY=7)
    check(abs(d) <= GR_IDLE, f"A T6 <- T7, nothing planted: {d:.2f} dB (|x| <= {GR_IDLE})")

    print("== KLVL ==")
    a = duck(0, 1, {4: 0.25}, KEY=5, KLVL=64)
    b = duck(0, 1, {4: 0.125}, KEY=5, KLVL=127)
    check(abs(a - b) <= 1.0, f"0.25 at KLVL 64 ducks {a:.1f} dB, 0.125 at KLVL 127 ducks {b:.1f} dB")

    print("== SELF and a KEY above 8 ==")
    s1 = gain(0, 1, {4: 0.25}, KEY=0)[0]
    s2 = gain(0, 1, {}, KEY=0)[0]
    check(s1 == s2, "KEY = SELF: bit-identical with the key words planted or empty")
    s1 = gain(0, 1, {4: 0.25}, KEY=9)[0]
    s2 = gain(0, 1, {4: 0.25}, KEY=0)[0]
    check(s1 == s2, "KEY 9: bit-identical with KEY = SELF")

    print(f"\n{'PASS' if not bad else 'FAIL'}: {len(bad)} failing")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
