#!/usr/bin/env python3
"""MACHINES's gate (docs/specs/MACHINES.md).

1. Under Unicorn, MACHINES's unit linked with two test clients (TA plays its
   base's slot, with a tick and a keep hook; TB does not), for one client and
   for two: each track's row, the names, the list's drawer and box over every
   top row, the commits from every starting machine (the Part and its battery
   copy, the defaults on a first signing only), SRC SETUP's pick of the
   base's slot list, SETUP's editor and drawer, the page resolver, LFO
   SETUP's names, the UI tick and the Part validator.
2. With the real clients (DRUMMER): every hook MACHINES's tables name
   links.
3. Installed (when out/mainos_bus.bin is a remix carrying MACHINES, given as
   the argument): each site holds MACHINES's write.
"""
import dataclasses
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools/verify"))
import toolpath  # noqa: E402,F401
from remix import registry, schema  # noqa: E402
import verify_hooks as vh  # noqa: E402

DECL = runpy.run_path(str(ROOT / "modules/machines/manifest.py"))
MC = registry.modules()["MACHINES"]
UNIT = MC.linked[0]
BASE_IMG = 0x40000400
FLEX = 1

TEST_CLIENTS = (
    ("TA", "ta", b"TA\x01", "TESTA", FLEX, True, ("page", "tick", "keep")),
    ("TB", "tb", b"TB\x02", "TESTB", FLEX, False, ("page",)),
)
PAGES = {"TA": 0x41A00000, "TB": 0x41B00000}
TICKS, KEEPS, SEEN = 0x41C00000, 0x41C00004, 0x41C00008
TEST_UNIT = f"""
        .text
        .global ta_mc_page, ta_mc_tick, ta_mc_keep, ta_mc_defaults, tb_mc_page, tb_mc_defaults
ta_mc_page:
        move.l  #0x{PAGES['TA']:08x},%d0
        rts
tb_mc_page:
        move.l  #0x{PAGES['TB']:08x},%d0
        rts
ta_mc_tick:
        addq.l  #1,(0x{TICKS:08x}).l
        rts
ta_mc_keep:
        addq.l  #1,(0x{KEEPS:08x}).l
        rts
ta_mc_defaults:
        .byte   1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12
tb_mc_defaults:
        .byte   21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32
"""
# The stock validator's body (0x40002320, after the prologue mc_stock_validate replays):
# record track 2's first knob byte as stock saw it, clamp it, return as stock returns.
VALIDATOR = f"""
        movea.l 100(%sp),%a0
        move.b  0x30+60(%a0),%d0
        move.b  %d0,(0x{SEEN:08x}).l
        move.b  #0x7f,0x30+60(%a0)
        movem.l (%sp),%d2-%d7/%a2-%fp
        lea     96(%sp),%sp
        moveq   #1,%d0
        rts
"""
BANK, PARTX, SRAM = 0x42000000, 0x42000000 + 0x8ED80, 0x100A4ECE
STACK, DONE = 0x47008000, 0x4700FFF0
PB_TABLE, FLEX_DEFAULTS = 0x400D5F38, 0x400D320C
SRC_CURSOR, SRC_FOCUS, LIST, CUR_TRACK = 0x460D5C30, 0x460D1A48, 0x460E7386, 0x100B14CC
STOPS = (0x400334DE, 0x4003D722, 0x4004C374, 0x4003C986, 0x400786A2, 0x400786D4, 0x400786FC, 0x400585E6,
         0x40078890, 0x4003A536, 0x4003A624, 0x4003CDA0, 0x40079822, 0x4005A61C, 0x4005A856, 0x40031ED6,
         0x40031ECE, 0x4003C058, 0x4003C054, 0x4003D1CC, 0x40052228, DONE)

fails = 0


def check(ok, what):
    global fails
    print(f"  [{'PASS' if ok else 'FAIL'}] {what}")
    fails += not ok


def asm(work, name, text):
    src, obj, out = work / f"{name}.s", work / f"{name}.o", work / f"{name}.bin"
    src.write_text(text)
    subprocess.run(["m68k-elf-as", "-mcpu=54455", "-o", str(obj), str(src)], check=True, capture_output=True)
    subprocess.run(["m68k-elf-objcopy", "-O", "binary", "-j", ".text", str(obj), str(out)], check=True)
    return out.read_bytes()


def unicorn(clients):
    from unicorn import UC_HOOK_CODE
    from unicorn import m68k_const as mc
    keys = {c[0] for c in clients}
    # MACHINES's tables for these clients: its own machines_inc with CLIENTS replaced
    inc = DECL["machines_inc"]
    saved = inc.__globals__["CLIENTS"]
    inc.__globals__["CLIENTS"] = clients
    try:
        with tempfile.TemporaryDirectory(prefix="octabam-machines-") as td:
            work = Path(td)
            (work / "client.s").write_text(TEST_UNIT)
            client = schema.Linked("testclient", str(work / "client.s"), dram=True)
            unit = dataclasses.replace(UNIT, include=inc)        # this manifest's tables, not the registry's
            segs, sym = vh._link_units(work, keys, [("MACHINES", unit), ("TEST", client)])
            validator = asm(work, "validator", VALIDATOR)
    finally:
        inc.__globals__["CLIENTS"] = saved
    u = vh._uc(segs)
    regs = [getattr(mc, f"UC_M68K_REG_D{i}") for i in range(8)] + [getattr(mc, f"UC_M68K_REG_A{i}") for i in range(7)]
    wr = lambda a, v: u.mem_write(a, v.to_bytes(4, "big"))                       # noqa: E731
    rd = lambda a: int.from_bytes(u.mem_read(a, 4), "big")                      # noqa: E731
    rb = lambda a, n=1: bytes(u.mem_read(a, n))                                 # noqa: E731
    for stop in STOPS:
        u.mem_write(stop, b"\x4e\x71")
    for stub in (0x4005213C, 0x4007E940):                                       # the tick's two stock calls
        u.mem_write(stub, b"\x4e\x75")
    u.mem_write(0x40002320, validator)
    u.mem_write(FLEX_DEFAULTS, bytes(range(0x40, 0x4C)))
    stock_pages = [0x400D301C, 0x400D31AE, 0x400D3340, 0x400D34D2, 0x400D3664, 0x400D34D2, 0x400D34D2, 0]
    n = len(clients)
    name = " + ".join(c[0] for c in clients)
    rows = {c[0]: 5 + i for i, c in enumerate(clients)}

    def reset():
        u.mem_write(PARTX, bytes(0x18B2))
        u.mem_write(SRAM, bytes(0x18B2))
        wr(0x46C82456, BANK)
        u.mem_write(0x100B14CF, b"\x00")
        u.mem_write(CUR_TRACK, b"\x02")
        for i, p in enumerate(stock_pages):
            wr(PB_TABLE + 4 * i, p)
        for a in (TICKS, KEEPS, SEEN, SRC_CURSOR, SRC_FOCUS):
            wr(a, 0)
        u.mem_write(sym["mc_pick"], b"\x00")
        u.mem_write(sym["mc_pb_held"], b"\x00")

    def track(t, kind, part=PARTX):
        u.mem_write(part + 0x22 + t, b"\x00" if kind == "static" else b"\x01")
        sig = {"static": bytes(3), "flex": bytes(3), "stray": b"TA\x01"}.get(kind) or \
            next(c[2] for c in clients if c[0] == kind)
        u.mem_write(part + 0x3C + 30 * t, sig)

    def run(entry, stop, r=None, stack=()):
        for x in regs:
            u.reg_write(x, 0)
        for i, v in (r or {}).items():
            u.reg_write(regs[i], v)
        u.reg_write(mc.UC_M68K_REG_SR, 0x2000)
        sp = STACK - 4 * len(stack)
        u.mem_write(sp, b"".join(v.to_bytes(4, "big") for v in stack))
        u.reg_write(mc.UC_M68K_REG_A7, sp)
        u.emu_start(entry, stop, count=400000)
        return (u.reg_read(mc.UC_M68K_REG_PC), [u.reg_read(x) for x in regs],
                u.reg_read(mc.UC_M68K_REG_A7) - sp)

    kinds = {"static": 0, "flex": 1, **rows}
    # 1. the row of a track's machine
    reset()
    got = {}
    for kind in kinds:
        track(3, kind)
        got[kind] = run(sym["mc_row_type"], DONE, {0: kinds[kind] and 1, 8: PARTX + 0x22 + 3}, (DONE,))[1][0]
    reset()
    track(3, "stray")
    u.mem_write(PARTX + 0x22 + 3, b"\x00")                  # a client's signature on a STATIC track
    stray = run(sym["mc_row_type"], DONE, {0: 0, 8: PARTX + 0x22 + 3}, (DONE,))[1][0]
    check(got == kinds and stray == 0, f"[{name}] mc_row_type: STATIC 0, FLEX 1, each client its row; a "
                                       f"signature on a STATIC track is STATIC ({got}, {stray})")

    # 2. the names
    names = {}
    for r in (1,) + tuple(range(5, 5 + n)):
        pc, x, _ = run(sym["mc_machine_name"], 0x400334DE if r < 5 else DONE, stack=(DONE, r))
        names[r] = (pc, bytes(u.mem_read(x[0], 10)).split(b"\0")[0] if r >= 5 else None)
    check(names[1][0] == 0x400334DE and all(names[5 + i] == (DONE, c[3].encode()) for i, c in enumerate(clients)),
          f"[{name}] mc_machine_name: stock rows to stock's formatter, each client's row its name")
    table = [rd(sym["mc_src_names"] + 4 * r) for r in range(5 + n)]
    check(table[:5] == list(DECL["STOCK_NAMES"])
          and [bytes(u.mem_read(a, 10)).split(b"\0")[0] for a in table[5:]] == [c[3].encode() for c in clients],
          f"[{name}] SRC SETUP's name table: stock's five, then each client's name")
    reset()
    track(2, clients[-1][0])
    pc, x, _ = run(sym["mc_name_a"], 0x4003D722, {0: 1, 8: PARTX + 0x22 + 2})
    check(pc == 0x4003D722 and x[1] == table[4 + n], f"[{name}] mc_name_a: a signed track's name")

    # 3. the list's drawer and box, every top row and screen row
    FMT, DRAW = 0x4700F000, 0x4700F100
    u.mem_write(FMT, bytes.fromhex("202f0004" "06800000" "1000" "4e75"))       # d0 = 4(sp) + 0x1000
    u.mem_write(DRAW, b"\x4e\x75")
    drawn = []
    hook = u.hook_add(UC_HOOK_CODE, lambda uc, pc, size, _d: drawn.append(
        [int.from_bytes(uc.mem_read(uc.reg_read(mc.UC_M68K_REG_A7) + 4 + 4 * i, 4), "big") for i in range(6)]),
        begin=DRAW, end=DRAW)
    n_rows, cases, bad = 5 + n, 0, 0
    for top in range(n_rows - 5 + 1):
        for d2 in range(6):
            wr(LIST, top)
            wr(LIST + 16, n_rows)
            drawn.clear()
            pc, _x, dsp = run(sym["mc_chooser_name"], 0x400786A2, {2: d2, 3: FMT, 4: 0x4444, 7: DRAW, 10: 0x30})
            row = top + d2
            want = [[0x400BA876, 0x4444, 5, 0x31, 0xFFFFFFFF, 0x1000 + row]] if row < n_rows else []
            cases += 1
            bad += pc != 0x400786A2 or dsp != 0 or drawn != want
            for kind, typ in kinds.items():
                reset()
                wr(LIST, top)
                wr(LIST + 16, n_rows)
                track(2, kind)
                stop = 0x400786D4 if typ == row and row < n_rows else 0x400786FC
                cases += 1
                bad += run(sym["mc_chooser_box"], stop, {2: d2, 8: PARTX + 0x22 + 2})[0] != stop
    u.hook_del(hook)
    check(bad == 0, f"[{name}] the list's drawer and box: {cases} cases -- row top + d2 on screen row d2, none "
                    f"past row {n_rows - 1}; the box on the track's row")

    # 4. the list's commit, from every starting machine to every row
    res, bad = 0, []
    for row in (1, 2) + tuple(range(5, 5 + n)):
        for start in ("flex",) + tuple(rows):
            reset()
            track(4, start)
            track(4, start, SRAM)
            u.mem_write(PARTX + 0x30 + 120, b"\x55")              # a knob already set
            pc, x, _ = run(sym["mc_main_commit"], 0x40079822, {0: 0, 1: 4, 4: row, 8: PARTX + 0x22 + 4,
                                                               9: BANK})
            client = clients[row - 5] if row >= 5 else None
            sig = client[2] if client else bytes(3)
            first = client is not None and start != client[0]
            knobs = rb(PARTX + 0x30 + 120, 6) + rb(PARTX + 0x1E0 + 120, 6)
            want_knobs = bytes(range(1, 13)) if first and client[0] == "TA" else \
                bytes(range(21, 33)) if first else b"\x55" + bytes(11)
            ok = (pc == 0x40079822 and rb(PARTX + 0x22 + 4)[0] == (FLEX if client else row)
                  and rb(PARTX + 0x3C + 120, 3) == sig and rb(SRAM + 0x3C + 120, 3) == sig
                  and knobs == want_knobs)
            res += 1
            if not ok:
                bad.append((row, start, rb(PARTX + 0x22 + 4)[0], rb(PARTX + 0x3C + 120, 3), knobs.hex()))
    check(not bad, f"[{name}] mc_main_commit: {res} cases -- a client's row stores FLEX and signs the Part and its "
                   f"battery copy, its defaults on a first signing only; any other row clears it"
                   f"{f' {bad}' if bad else ''}")

    # 5. SRC SETUP: the commit, and RIGHT on TA's row picking FLEX's slot list
    reset()
    track(2, "flex")
    wr(SRC_CURSOR, 5)
    pc, x, _ = run(sym["mc_src_commit"], 0x4005A61C, {0: 0, 2: 2, 9: BANK})
    check(pc == 0x4005A61C and x[1] == FLEX and rb(PARTX + 0x3C + 60, 3) == clients[0][2],
          f"[{name}] mc_src_commit: the cursor on a client's row signs it and stores FLEX")
    reset()
    wr(SRC_CURSOR, 5)
    run(sym["mc_setup_key"], 0x4003D1CC, stack=(DONE, 0x21))                   # RIGHT on TA's row
    picked = (rd(SRC_CURSOR), rb(sym["mc_pick"])[0], rd(PB_TABLE + 4))
    wr(SRC_FOCUS, 1)
    track(2, "flex")
    pc, x, _ = run(sym["mc_src_commit2"], 0x4005A856, {0: 0, 2: 2, 9: BANK})  # the slot list commits
    signed = rb(PARTX + 0x3C + 60, 3)
    run(sym["mc_setup_key"], 0x4003D1CC, stack=(DONE, 0x34))                   # LEFT back to the row
    back = (rd(SRC_CURSOR), rb(sym["mc_pick"])[0])
    run(sym["mc_tick"], 0x40052228)
    check(picked == (FLEX, 5, PAGES["TA"]) and x[1] == FLEX and signed == clients[0][2] and back == (5, 0)
          and rd(PB_TABLE + 4) == stock_pages[1],
          f"[{name}] RIGHT on TA's row opens FLEX's slot list with TA's page, the commit signs TA, LEFT returns "
          f"to its row and FLEX's page comes back ({picked}, {signed}, {back})")
    if n > 1:
        reset()
        wr(SRC_CURSOR, 6)
        run(sym["mc_setup_key"], 0x4003D1CC, stack=(DONE, 0x21))
        check((rd(SRC_CURSOR), rb(sym["mc_pick"])[0]) == (6, 0),
              f"[{name}] RIGHT on TB's row (no slot) is stock's")

    # 6. SETUP's editor and drawer
    out = {}
    for d2, a3 in ((1, 0), (3, 0), (5, 0)) + (((6, 0), (6, 0x41000000)) if n > 1 else ()):
        stop = 0x4003A624 if d2 == 6 and not a3 else 0x4003A536
        pc, x, _ = run(sym["mc_setup_edit6"], stop, {2: d2, 11: a3})
        out[(d2, a3)] = (pc, x[0] if pc == 0x4003A536 else None)
    want = {(1, 0): (0x4003A536, 6), (3, 0): (0x4003A536, 18), (5, 0): (0x4003A536, 6),
            (6, 0): (0x4003A624, None), (6, 0x41000000): (0x4003A536, 6)}
    check(all(out[k] == want[k] for k in out), f"[{name}] mc_setup_edit6: a client's row edits FLEX's bytes; "
                                               f"a client without the slot leaves an empty slot field ({out})")
    pc, x, _ = run(sym["mc_setup_draw6"], 0x4003CDA0, {6: 4 + n})
    pc1, x1, _ = run(sym["mc_setup_draw6"], 0x4003CDA0, {6: 3})
    check((pc, x[7], pc1, x1[7]) == (0x4003CDA0, 6, 0x4003CDA0, 18),
          f"[{name}] mc_setup_draw6: a client's row draws FLEX's bytes, a stock row its own")

    # 7. the page resolver and LFO SETUP's names
    reset()
    track(2, clients[-1][0])
    track(3, "flex")
    pc, x, _ = run(sym["mc_resolve_pb"], 0x40031ED6, {5: 1, 8: PARTX + 0x22 + 2})
    pc1, x1, _ = run(sym["mc_resolve_pb"], 0x40031ECE, {5: 1, 8: PARTX + 0x22 + 3})
    check((pc, x[0], pc1, x1[8]) == (0x40031ED6, PAGES[clients[-1][0]], 0x40031ECE, PB_TABLE),
          f"[{name}] mc_resolve_pb: a client's track its client's page, a FLEX track stock's table")
    pc, x, _ = run(sym["mc_lfo_pb"], 0x4003C058, {1: 0x1234, 8: PARTX + 0x22 + 2})
    pc1, x1, _ = run(sym["mc_lfo_pb"], 0x4003C054, {8: PARTX + 0x22 + 3})
    check((pc, x[1], x[10], pc1, x1[8]) == (0x4003C058, 0x1234, PAGES[clients[-1][0]], 0x4003C054, PB_TABLE),
          f"[{name}] mc_lfo_pb: a client's track names its client's knobs (d1 kept), a FLEX track stock's")

    # 8. the UI tick
    reset()
    run(sym["mc_tick"], 0x40052228)
    check([rd(PB_TABLE + 4 * r) for r in range(5, 5 + n)] == [PAGES[c[0]] for c in clients]
          and rd(TICKS) == 1 and rd(PB_TABLE + 4) == stock_pages[1],
          f"[{name}] mc_tick: each client's page as its row's, TA's tick once, FLEX's page untouched")

    # 9. the Part validator
    reset()
    track(2, "TA")
    u.mem_write(PARTX + 0x30 + 60, b"\x33")
    track(3, "flex")
    u.mem_write(PARTX + 0x30 + 90, b"\x44")
    wr(STACK - 0x400, PARTX)
    pc, x, _ = run(sym["mc_validate_entry"], DONE, stack=(DONE, PARTX))
    check(pc == DONE and x[0] == 1 and rb(SEEN)[0] == 0x40 and rb(PARTX + 0x30 + 60)[0] == 0x33
          and rd(KEEPS) == 2,
          f"[{name}] mc_validate: stock sees FLEX's defaults on a client's knobs, they are put back after, the "
          f"client's keep hook runs before and after, stock's result returned")


def real_clients():
    """The real clients as linked by the build: every name MACHINES's tables give resolves."""
    keys = {c[0] for c in DECL["CLIENTS"]} | {"MACHINES", "STORE", "PAGES", "MEMORY"}
    inc = DECL["machines_inc"](keys)
    words = {w.strip() for line in inc.splitlines() if ".long" in line for w in line.split(".long")[1].split(",")}
    want = sorted(w for w in words if w and not w.isdigit() and not w.startswith(("0x", "mc_name_")))
    known = registry.modules()
    defined = set()
    for k in (c[0] for c in DECL["CLIENTS"]):
        for u in known[k].linked:
            text = (ROOT / u.source).read_text()
            defined |= {w for w in want if f"{w}:" in text}
    check(set(want) == defined, f"the real clients define every hook their entries name ({', '.join(want)})")


def installed(remix):
    img_path, elf = ROOT / "out/mainos_bus.bin", ROOT / "out/platform/runtime/runtime.elf"
    if not img_path.exists() or not elf.exists():
        print("  [SKIP] installed: no built image")
        return
    r = registry.remix(remix)
    if "MACHINES" not in r.modules:
        print(f"  [SKIP] installed: remix {remix} has no MACHINES")
        return
    img = img_path.read_bytes()
    sym = {f[2]: int(f[0], 16) for f in (line.split() for line in
           subprocess.check_output(["m68k-elf-nm", str(elf)], text=True).splitlines()) if len(f) == 3}
    if "mc_machine_name" not in sym:
        print("  [SKIP] installed: the built image is not this remix's")
        return
    rd = lambda a: int.from_bytes(img[a - BASE_IMG:a - BASE_IMG + 4], "big")   # noqa: E731
    bad = [hex(d.site) for d in MC.detours
           if img[d.site - BASE_IMG:d.site - BASE_IMG + 2] not in (b"\x4e\xf9", b"\x4b\xf9")
           or rd(d.site + 2) != sym[d.symbol]]
    check(not bad, f"[{remix}] each of MACHINES's {len(MC.detours)} sites reaches its stub{f' {bad}' if bad else ''}")
    n = len(DECL["present"](set(r.modules)))
    check(img[0x40079248 - BASE_IMG:0x40079248 - BASE_IMG + 4] == bytes.fromhex(f"487800{5 + n:02x}"),
          f"[{remix}] the machine list has {5 + n} rows")


def main():
    print("machines: MACHINES under Unicorn, one client")
    unicorn(TEST_CLIENTS[:1])
    print("machines: MACHINES under Unicorn, two clients")
    unicorn(TEST_CLIENTS)
    print("machines: the real clients")
    real_clients()
    print("machines: the installed image")
    installed(sys.argv[1] if len(sys.argv) > 1 else "drummer")
    print(f"machines: {'FAIL' if fails else 'PASS'}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
