#!/usr/bin/env python3
"""Prove the CC->FX2 page-2 cave (modules/ccpage2) in the emulator.

1. Re-assemble modules/ccpage2/cc_page2.s and check it matches the pinned
   CODE in the manifest (drifted source cannot pass).
2. Place the emitted cave at a test address; for each audio track 0..7 on its
   own trig channel, feed a CC 62 (slot 6 = page-2 MODE) message and confirm
   the value lands, count-clamped, at the traced Part / live / mirror bytes.
3. Feed an over-count value into a select slot and confirm it clamps (the
   over-count store is the sequencer-stall trap).
4. Feed a page-1 CC (40) and confirm the cave tail-calls the stock handler
   (reached via a stub) and writes no page-2 byte.

Single-core emu: this proves the WRITE and the DECISION. The CC->queue->main
-task->DSP path only proves on hardware (docs/midi_re_cc.md).
"""
import importlib.util
import pathlib
import subprocess
import sys
import tempfile

sys.path.insert(0, "tools")
import emu_bringup as emu
from unicorn import UC_HOOK_CODE
from unicorn.m68k_const import UC_M68K_REG_PC

ROOT = pathlib.Path(__file__).resolve().parent.parent
CAVE_AT = 0x40300000            # a fresh RWX page, away from the OS image
STOCK_CC = 0x4000e79c
MSG_AT = 0x47e00000            # scratch for the 3-byte MIDI message

AUDIO_CC_IN = 0x80000049
AUTO_CH = 0x80000047
TRIG_CH = 0x8000003f           # +track = the channel that track listens on
IDLIVE = 0x80000ecc            # +track = live FX2 id
PARTB = 0x80000003
DBPTR = 0x46c82456

VERB_COUNTS = (3, 128, 128, 4, 128, 4)
DLY_COUNTS = (3, 128, 128, 4, 128, 2)


def _manifest():
    spec = importlib.util.spec_from_file_location(
        "ccpage2_manifest", ROOT / "modules/ccpage2/manifest.py")
    m = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(ROOT / "tools"))
    spec.loader.exec_module(m)
    return m


def check_source_matches(m):
    if not __import__("shutil").which("m68k-elf-as"):
        print("  (skip source re-assemble: no m68k-elf-as)")
        return
    with tempfile.TemporaryDirectory() as d:
        o = pathlib.Path(d) / "cc.o"
        b = pathlib.Path(d) / "cc.bin"
        subprocess.run(["m68k-elf-as", "-mcpu=5407", "-o", str(o),
                        str(ROOT / "modules/ccpage2/cc_page2.s")], check=True)
        subprocess.run(["m68k-elf-objcopy", "-O", "binary", "-j", ".text",
                        str(o), str(b)], check=True)
        asm = b.read_bytes()
    assert asm == m.CODE, "cc_page2.s no longer assembles to the pinned CODE"
    print("  source re-assembles to pinned CODE (%d bytes)" % len(asm))


def _part_base(uc):
    db = int.from_bytes(uc.mem_read(DBPTR, 4), "big")
    part = uc.mem_read(PARTB, 1)[0]
    return db + part * 6322


def _addrs(uc, track, slot2):
    base = _part_base(uc)
    return (base + 0x8ef5a + track * 30 + 0 + slot2,    # Part: page*6+slot2, FX2 stages index 0 (hw-measured 5 Sep, tag 12)
            0x80000810 + track * 72 + 0x20 + slot2,       # live
            0x100a50a8 + 0 + track * 30 + slot2)          # shadow: 0x100a50a8+part*6322+track*30+page*6+slot2 (P2EDIT 0x4003a5bc), part 0, index 0


def main():
    m = _manifest()
    check_source_matches(m)
    blob, pokes = m.emit(CAVE_AT)
    assert pokes[0] == (0x400d64a0, (0x4000e79c).to_bytes(4, "big"),
                        CAVE_AT.to_bytes(4, "big")), "dispatch poke wrong"

    r = emu.boot("out/mainos_bus.bin")
    uc = r.uc
    assert r.clean
    # the cave also writes the shadow (0x100a5xxx), the part-modified byte
    # (0x100b145e) and the global changed flag (0x100f8598): map those pages
    for b in (CAVE_AT, MSG_AT, 0x100a0000, 0x100b0000, 0x100f0000, 0x460d0000):
        try:
            uc.mem_map(b & ~0xFFFF, 0x10000)
        except Exception:
            pass
    uc.mem_write(CAVE_AT, blob)

    # a stub at the stock handler: record it was reached, then rts
    reached = {"stock": False}
    def stock_stub(u, a, s, x):
        reached["stock"] = True
        sp = u.reg_read(emu.UC_M68K_REG_A7)
        ret = int.from_bytes(u.mem_read(sp, 4), "big")
        u.reg_write(emu.UC_M68K_REG_A7, sp + 4)
        u.reg_write(UC_M68K_REG_PC, ret)
    uc.hook_add(UC_HOOK_CODE, stock_stub, begin=STOCK_CC, end=STOCK_CC + 2)

    def send(track, effect_id, cc, value, channel=3):
        emu.assign_fx2(r, track=track, effect_id=effect_id)
        uc.mem_write(PARTB, b"\x00")
        uc.mem_write(0x460d5c30, (0).to_bytes(4, "big"))   # staged page index 0 (the cave pins +0 anyway)
        uc.mem_write(AUDIO_CC_IN, b"\x01")
        uc.mem_write(AUTO_CH, b"\xff")
        # every track off, then our track listens on `channel`
        for t in range(8):
            uc.mem_write(TRIG_CH + t, b"\xff")
            uc.mem_write(IDLIVE + t, b"\x00")
        uc.mem_write(TRIG_CH + track, bytes([channel]))
        uc.mem_write(IDLIVE + track, bytes([effect_id]))
        pa, la, ma = _addrs(uc, track, cc - 62 if cc >= 62 else 0)
        for a in (pa, la, ma):
            uc.mem_write(a, b"\x00")
        uc.mem_write(MSG_AT, bytes([0xB0 | channel, cc & 0x7f, value & 0x7f]))
        reached["stock"] = False
        emu._call(uc, CAVE_AT, (MSG_AT,), count=5_000_000)
        return pa, la, ma

    ok = True

    # 1. every track, CC 62 (slot 6 = MODE, count 3) value 1 -> lands as 1
    print("CC 62 (page-2 slot 6) on each track's own channel:")
    for track in range(8):
        eid = 6 if track % 2 else 7
        pa, la, ma = send(track, eid, 62, 1)
        p, l, mm = uc.mem_read(pa, 1)[0], uc.mem_read(la, 1)[0], uc.mem_read(ma, 1)[0]
        good = (p == 1 and l == 1 and mm == 1 and not reached["stock"])
        ok &= good
        print(f"  t{track} id{eid}: Part={p} live={l} mirror={mm} "
              f"stock={reached['stock']}  {'ok' if good else 'FAIL'}")

    # 2. over-count clamp: CC 62 (MODE, count 3 -> max 2) value 99 -> clamps to 2
    print("clamp (select over-count):")
    for eid, cnts in ((7, VERB_COUNTS), (6, DLY_COUNTS)):
        pa, la, ma = send(4 if eid == 7 else 1, eid, 62, 99)
        want = cnts[0] - 1
        l = uc.mem_read(la, 1)[0]
        good = (l == want)
        ok &= good
        print(f"  id{eid} slot6 value 99 -> live={l} (want {want})  "
              f"{'ok' if good else 'FAIL'}")
    # a knob slot (count 128) passes full range
    pa, la, ma = send(4, 7, 63, 120)   # slot 7 = knob
    l = uc.mem_read(la, 1)[0]
    good = (l == 120)
    ok &= good
    print(f"  id7 slot7 (knob) value 120 -> live={l} (want 120)  "
          f"{'ok' if good else 'FAIL'}")

    # 3. page-1 CC 40 tail-calls stock, no page-2 write
    print("tail-call (page-1 CC 40 -> stock, no page-2 write):")
    pa, la, ma = _addrs(uc, 4, 0)
    uc.mem_write(la, b"\x00")
    send(4, 7, 40, 55)
    l = uc.mem_read(la, 1)[0]
    good = (reached["stock"] and l == 0)
    ok &= good
    print(f"  stock={reached['stock']} page2-live={l}  {'ok' if good else 'FAIL'}")

    print("\nALL PASS" if ok else "\nFAILURES ABOVE")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
