#!/usr/bin/env python3
"""Prove the CC->FX2 (CC 62-67) and CC->FX1 (CC 68-73) page-2 cave (modules/cc-map) in the emulator.

1. Re-assemble modules/cc-map/cc_map.s and check it matches the pinned
   CODE in the manifest (drifted source cannot pass).
2. Place the emitted cave at a test address; for each audio track 0..7 on its
   own trig channel, feed a CC 62 (slot 6 = page-2 MODE) message and confirm
   the value lands, count-clamped, at the traced Part / live / mirror bytes.
3. Feed an over-count value into a select slot and confirm it clamps (the
   over-count store is the sequencer-stall trap).
4. Feed a page-1 CC (40) and confirm the cave tail-calls the stock handler
   (reached via a stub) and writes no page-2 byte.

Single-core emu: this proves the WRITE and the DECISION. The CC->queue->main
-task->DSP path runs under the ColdFire port: verify_set sends CC 68 over
UART0 and reads the FX1 page-2 lane and the DSP record back (15 Sep 2026;
hardware-confirmed on image 96/97 before that).
"""
import importlib.util
import os
import pathlib
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401  (every tools/ dir on sys.path)
try:
    import emu_bringup as emu
    from unicorn import UC_HOOK_CODE
    from unicorn.m68k_const import UC_M68K_REG_PC
except ImportError:
    print("  [SKIP] verify_ccmap: no unicorn (the .venv: make emu-setup)")
    sys.exit(0)

ROOT = pathlib.Path(__file__).resolve().parents[2]
CAVE_AT = 0x40300000            # a fresh RWX page, away from the OS image
STOCK_CC = 0x4000e79c
MSG_AT = 0x47e00000            # scratch for the 3-byte MIDI message
from remix import registry  # noqa: E402
# CC MAP on the two hosts and a station, under unicorn: no DRAM runtime.
FIXTURE_REMIX = registry.fixture("CC MAP", "REVERB SERVER", "DELAY SERVER", "CHARACTER")


def _build(remix):
    """Build `remix` at out/mainos_bus.bin and return the path."""
    env = dict(os.environ, REMIX=remix, XBUS="1", SPEC="1")
    r = subprocess.run([sys.executable, str(ROOT / "tools/build/build_bus.py")],
                       env=env, capture_output=True, text=True, cwd=ROOT)
    if r.returncode:
        sys.exit(f"verify_ccmap: building {remix} failed:\n{(r.stdout + r.stderr)[-1500:]}")
    return ROOT / "out/mainos_bus.bin"

AUDIO_CC_IN = 0x80000049
AUTO_CH = 0x80000047
TRIG_CH = 0x8000003f           # +track = the channel that track listens on
IDLIVE = 0x80000ecc            # +track = live FX2 id
PARTB = 0x80000003
DBPTR = 0x46c82456

VERB_COUNTS = (3, 128, 128, 128, 128, 128)
DLY_COUNTS = (3, 128, 128, 4, 128, 128)


def _manifest():
    spec = importlib.util.spec_from_file_location(
        "ccmap_manifest", ROOT / "modules/cc-map/manifest.py")
    m = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401  (every tools/ dir on sys.path)
    spec.loader.exec_module(m)
    return m


def check_source_matches(m):
    """The source is the truth (its count tables are labels,
    linked wherever the cave lands); the hand-patched CODE+tables it replaced
    is kept in the manifest as legacy_bytes(addr) and is the ORACLE here:
    linked at any address, the two must be byte-identical."""
    shutil = __import__("shutil")
    if not all(shutil.which(t) for t in ("m68k-elf-as", "m68k-elf-ld", "m68k-elf-objcopy")):
        print("  (skip source link check: no m68k-elf toolchain)")
        return
    for addr in (0x40a955e0, 0x400d24d0):       # the DRAM runtime base, and a ROM run
        with tempfile.TemporaryDirectory() as d:
            o, e, b = (pathlib.Path(d) / n for n in ("cc.o", "cc.elf", "cc.bin"))
            subprocess.run(["m68k-elf-as", "-mcpu=54455", "-o", str(o),
                            str(ROOT / "modules/cc-map/cc_map.s")], check=True)
            # The cave's fall-through is a link-time symbol (CC_NEXT); the
            # manifest's default is stock's handler, and that is what the
            # ratified bytes carry.
            subprocess.run(["m68k-elf-ld", f"-Ttext=0x{addr:x}",
                            *[f"--defsym={n}=0x{v:x}" for n, v in m.MODULE.linked[0].defsyms],
                            "-o", str(e), str(o)], check=True)
            subprocess.run(["m68k-elf-objcopy", "-O", "binary", "-j", ".text",
                            str(e), str(b)], check=True)
            linked = b.read_bytes()
        want = m.legacy_bytes(addr)
        assert linked == want, (f"cc_map.s linked at 0x{addr:08x} differs from the "
                                f"hand-patched legacy bytes ({len(linked)} vs {len(want)} B)")
        assert linked[-12:] == m.VERB_COUNTS + m.DLY_COUNTS, "count tables drifted"
    print("  source links to the legacy bytes at two addresses (%d bytes, tables intact)" % len(linked))


def _part_base(uc):
    db = int.from_bytes(uc.mem_read(DBPTR, 4), "big")
    part = uc.mem_read(PARTB, 1)[0]
    return db + part * 6322


def _addrs(uc, track, slot2):
    base = _part_base(uc)
    return (base + 0x8f084 + track * 30 + slot2,        # Part: the FX2 page-2 editor's own store (0x4003aaaa)
            0x80000810 + track * 72 + 0x38 + slot2,       # live: the FX2 page-2 lane the copier delivers (0x4003ab00)
            0x100a51d2 + track * 30 + slot2)              # shadow: 0x100a51d2+part*6322+track*30+slot2 (0x4003aab2), part 0


def _addrs1(uc, track, slot2):
    """The FX1 page-2 editor's stores (0x4003abe4, disassembled)."""
    base = _part_base(uc)
    return (base + 0x8f07e + track * 30 + slot2,        # Part (0x4003acb2)
            0x80000810 + track * 72 + 0x32 + slot2,       # live lane +0x32 (0x4003ad08)
            0x100a51cc + track * 30 + slot2)              # shadow (0x4003acba), part 0


FX1_ID_OFF = 0x8ed80                                    # Part: +track, the FX1 id (0x4003ac1e)
    # Until these were 0x8ef5a / +0x20 / 0x100a50a8 -- the PLAYBACK
    # page-2 editor's arrays (0x4003a474; its "staged index" is the machine type).


def main():
    m = _manifest()
    check_source_matches(m)
    # run the ORACLE form (== the linked source, proven above) at the test address
    blob = m.legacy_bytes(CAVE_AT)
    ref = m.MODULE.symbol_refs[0]
    assert (ref.addr, ref.expect, ref.unit, ref.symbol) == (
        0x400d64a0, 0x4000e79c, "ccmap", "ccm_entry"), "dispatch repoint wrong"

    # The checks below read BusVerb's, BusDelay's and Character's descriptor
    # counts, and the Unicorn boot reaches the RTOS handoff only on an image
    # without the DRAM platform: build the rig, test it, then put the selected
    # remix back so the gates after this one read their own image.
    r = emu.boot(str(_build(FIXTURE_REMIX)))
    uc = r.uc
    assert r.clean, f"{FIXTURE_REMIX} did not boot to the RTOS handoff: {r.stopped}"
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

    # 4. FX1 page 2 via CC 68-73: every track, Character (0x1c)
    #    on FX1, CC 68 (page-2 slot 6 = SAT, count 3; top left since 16 Sep
    #    2026) value 1 -> lands as 1
    print("CC 68 (FX1 page-2 slot 6) on each track's own channel, FX1 = Character:")
    CHAR = 0x1c
    def send1(track, fx1_id, cc, value, channel=3):
        emu.assign_fx2(r, track=track, effect_id=9)             # SEND on FX2, irrelevant here
        uc.mem_write(_part_base(uc) + FX1_ID_OFF + track, bytes([fx1_id]))
        uc.mem_write(PARTB, b"\x00"); uc.mem_write(AUDIO_CC_IN, b"\x01"); uc.mem_write(AUTO_CH, b"\xff")
        for t in range(8):
            uc.mem_write(TRIG_CH + t, b"\xff")
        uc.mem_write(TRIG_CH + track, bytes([channel]))
        pa, la, ma = _addrs1(uc, track, cc - 68)
        for a in (pa, la, ma):
            uc.mem_write(a, b"\x00")
        # the FX2 lane of the same slot must stay untouched
        _, la2, _ = _addrs(uc, track, cc - 68)
        uc.mem_write(la2, b"\x00")
        uc.mem_write(MSG_AT, bytes([0xB0 | channel, cc & 0x7f, value & 0x7f]))
        reached["stock"] = False
        emu._call(uc, CAVE_AT, (MSG_AT,), count=5_000_000)
        return pa, la, ma, la2
    for track in range(8):
        pa, la, ma, la2 = send1(track, CHAR, 68, 1)
        p, l, mm, l2 = (uc.mem_read(a, 1)[0] for a in (pa, la, ma, la2))
        good = (p == 1 and l == 1 and mm == 1 and l2 == 0 and not reached["stock"])
        ok &= good
        print(f"  t{track} Character: Part={p} live={l} mirror={mm} fx2lane={l2} "
              f"stock={reached['stock']}  {'ok' if good else 'FAIL'}")
    # the clamp from the DESCRIPTOR: SAT (slot 6, count 3) -> 99 clamps to 2; TONE (slot 7, count 128) passes 120
    pa, la, ma, _ = send1(2, CHAR, 68, 99)
    l = uc.mem_read(la, 1)[0]; good = (l == 2); ok &= good
    print(f"  clamp: Character SAT (count 3) value 99 -> live={l} (want 2)  {'ok' if good else 'FAIL'}")
    pa, la, ma, _ = send1(2, CHAR, 70, 120)
    l = uc.mem_read(la, 1)[0]; good = (l == 120); ok &= good
    print(f"  knob: Character KLVL (slot 8, count 128) value 120 -> live={l} (want 120)  {'ok' if good else 'FAIL'}")
    pa, la, ma, _ = send1(2, CHAR, 69, 99)
    l = uc.mem_read(la, 1)[0]; good = (l == 1); ok &= good
    print(f"  clamp: Character KEY (slot 7, count 2) value 99 -> live={l} (want 1)  {'ok' if good else 'FAIL'}")
    # FX1 = NONE (id 0): nothing written anywhere
    pa, la, ma, _ = send1(5, 0x00, 69, 77)
    vals = [uc.mem_read(a, 1)[0] for a in (pa, la, ma)]
    good = (vals == [0, 0, 0]); ok &= good
    print(f"  FX1 NONE: CC 69 writes nothing  Part/live/mirror={vals}  {'ok' if good else 'FAIL'}")
    # CC 74 (past the range) tail-calls stock
    pa, la, ma, _ = send1(2, CHAR, 74, 5)
    good = reached["stock"]; ok &= good
    print(f"  CC 74 -> stock={reached['stock']}  {'ok' if good else 'FAIL'}")

    print("\nALL PASS" if ok else "\nFAILURES ABOVE")
    selected = os.environ.get("REMIX")
    if selected and selected != FIXTURE_REMIX:
        _build(selected)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
