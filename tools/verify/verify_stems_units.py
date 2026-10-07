#!/usr/bin/env python3
"""STEM REC's ColdFire routines, one at a time, in Unicorn: no boot, no DSP.

    python3 tools/verify/verify_stems_units.py [test ...]

Loads the built runtime (out/platform/runtime/runtime.bin at its .text
base, inside the platform's DRAM reserve), maps the memory the routines read
(the SRAM at 0x80000000, the page holding the input ring's index, a stack),
and calls one routine with its registers set. The image's gain-table words
are deliberately not mapped: the OS reuses that RAM after the upload
(docs/firmware/STEM_REC.md 18.4), so a routine that reads them faults here.
The Unicorn is the one tools/emu/emu_bringup.py selects: the repository's
patched build, whose EMAC multiplies in fractional mode as the MCF5445x
does. The harness refuses to run when that self-test fails. Each test
compares a routine with tools/verify/stems_gain.py or a reference beside
it (git show 4d2d6456:docs/superpowers/plans/2026-10-01-stem-rec-sources.md, "Testing")."""
import pathlib
import random  # noqa: F401  (the tests that follow draw their inputs from it)
import struct
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
for p in ("tools/emu", "tools", "tools/verify"):
    sys.path.insert(0, str(ROOT / p))
import toolpath  # noqa: E402,F401
import emu_bringup  # noqa: E402  (exports LIBUNICORN_PATH before unicorn loads)
from unicorn import Uc, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN, UC_HOOK_INTR  # noqa: E402
from unicorn import m68k_const as K  # noqa: E402
import stems_gain as sg  # noqa: E402,F401

# The constants of modules/stems/stems.s these tests depend on. Each task
# that adds one to stems.s copies its value here.
GQ_N = 4
GQ_SLOT, GQ_FRAME = 0x80, 0x400                         # stems.s: a slot is its largest gain, then 16
LIM_FREE = 0x200000                                     # stems.s: gains in 0..this never limit (design 1.3)
SRC_BITS = 0xfff                                        # stems.s: every source (Task 8)
GAIN_LAG, TRACK_HALF, TRACK_DELAY = 1, 1, 0             # stems.s: staged a frame early (perf design 1.1)
IN_RING, IN_IDX = 0x80005660, 0x46104d00                # STEM_REC.md 18.7: eight frame pages, the index
IN_AB_OFF, IN_CD_OFF, IN_A_IS_LEFT = 0x80, 0x00, 1      # STEM_REC.md 18.7: within a page

RESERVE = (0x40a95000, 0x41496000)        # the platform reserve, page-aligned (docs/contributing/PLACEMENT.md)
SRAM = (0x80000000, 0x10000)
IDX_PAGE = (IN_IDX & ~0xfff, 0x1000)
TABLE = 0x400ea18a                        # X:0x6c00's words in the stock slice, 3 bytes LE (18.4)
STOP, STACK = 0x00010000, 0x00030000
fails = 0
UNITS = []


def check(label, ok, detail=""):
    global fails
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"  {detail}" if detail else ""))
    fails += 0 if ok else 1


def unit(f):
    UNITS.append(f)
    return f


_asm_cache = {}


def assemble(src):
    """ColdFire text -> bytes, assembled as the platform assembles a DRAM
    unit (-mcpu=54455), in a private scratch directory (AGENTS.md: never a
    fixed /tmp name)."""
    if src not in _asm_cache:
        import shutil
        import tempfile
        d = pathlib.Path(tempfile.mkdtemp(prefix="stems_units_"))
        try:
            (d / "s.s").write_text(src)
            subprocess.run(["m68k-elf-as", "-mcpu=54455", "-o", str(d / "s.o"), str(d / "s.s")], check=True)
            subprocess.run(["m68k-elf-objcopy", "-O", "binary", "-j", ".text", str(d / "s.o"), str(d / "s.bin")],
                           check=True)
            _asm_cache[src] = (d / "s.bin").read_bytes()
        finally:
            shutil.rmtree(d, ignore_errors=True)
    return _asm_cache[src]


class Rt:
    REGS = {**{f"d{i}": getattr(K, f"UC_M68K_REG_D{i}") for i in range(8)},
            **{f"a{i}": getattr(K, f"UC_M68K_REG_A{i}") for i in range(7)}}

    def __init__(self):
        ok, why = emu_bringup.emac_selftest()
        if not ok:
            sys.exit(f"the EMAC self-test fails ({why}): run scripts/build_unicorn.sh (plan Task 4b)")
        rt = ROOT / "out/platform/runtime"
        nm = subprocess.check_output(["m68k-elf-nm", str(rt / "runtime.elf")], text=True)
        self.s = {f[2]: int(f[0], 16) for f in (line.split() for line in nm.splitlines()) if len(f) == 3}
        hdr = subprocess.check_output(["m68k-elf-objdump", "-h", str(rt / "runtime.elf")], text=True)
        base = int(next(line.split()[3] for line in hdr.splitlines()
                        if len(line.split()) > 3 and line.split()[1] == ".text"), 16)
        self.uc = uc = Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN)
        uc.ctl_set_cpu_model(K.UC_CPU_M68K_CFV4E)
        uc.mem_map(RESERVE[0], RESERVE[1] - RESERVE[0])
        uc.mem_write(base, (rt / "runtime.bin").read_bytes())
        uc.mem_map(*SRAM)
        uc.mem_map(*IDX_PAGE)
        uc.mem_map(STOP & ~0xfff, STACK - (STOP & ~0xfff))
        img = (ROOT / "out/raw/section_3_MAIN_OS.bin").read_bytes()
        t0 = TABLE - 0x40000400
        self.table = [int.from_bytes(img[t0 + 3 * i:t0 + 3 * i + 3], "little") for i in range(258)]
        uc.reg_write(K.UC_M68K_REG_SR, 0x2700)
        self.trap = None
        uc.hook_add(UC_HOOK_INTR, self._on_intr)

    def _on_intr(self, uc, intno, user):
        self.trap = (intno, uc.reg_read(K.UC_M68K_REG_PC))
        uc.emu_stop()

    def _start(self, pc, until, count=2_000_000):
        """emu_start with the ISA C instructions Unicorn's CFV4E lacks (bitrev,
        byterev, ff1: vector 4) emulated by emu_bringup's shim, as the port
        runs them; any other trap is an error."""
        while True:
            self.trap = None
            self.uc.emu_start(pc, until, count=count)
            if self.trap is None:
                return
            npc = emu_bringup._isa_c_shim(self.uc, self)
            if npc is None:
                raise RuntimeError(f"trap vector {self.trap[0]} at {self.trap[1]:#x}")
            pc = npc

    def call(self, name, **regs):
        uc = self.uc
        for r, v in regs.items():
            uc.reg_write(self.REGS[r], v & 0xffffffff)
        uc.reg_write(K.UC_M68K_REG_A7, STACK - 4)
        uc.mem_write(STACK - 4, struct.pack(">I", STOP))
        self._start(self.s[name], STOP)
        assert uc.reg_read(K.UC_M68K_REG_PC) == STOP, f"{name} did not return"
        sp = uc.reg_read(K.UC_M68K_REG_A7)
        assert sp == STACK, f"{name}: the stack is off by {sp - STACK}"
        return {r: uc.reg_read(n) for r, n in self.REGS.items()}

    def wmem(self, a, b):
        self.uc.mem_write(a, bytes(b))

    def rmem(self, a, n):
        return bytes(self.uc.mem_read(a, n))

    def w32(self, a, v):
        self.wmem(a, (v & 0xffffffff).to_bytes(4, "big"))

    def r32(self, a):
        return int.from_bytes(self.rmem(a, 4), "big")

    def r32s(self, a):
        return int.from_bytes(self.rmem(a, 4), "big", signed=True)

    CODE, SAVE = 0x00020000, 0x00021000     # scratch code and its results, inside the stack's mapping

    def run(self, code):
        self.uc.mem_write(self.CODE, code)
        self._start(self.CODE, self.CODE + len(code))

    def set_emac(self, macsr, acc0, acc1, accext01):
        """The interrupted code's EMAC state, as the hook finds it: written in
        integer mode, then its MACSR."""
        self.run(assemble(f"""
        moveq   #0,%d0
        move.l  %d0,%macsr
        move.l  #{acc0:#x},%d0
        move.l  %d0,%acc0
        move.l  #{acc1:#x},%d0
        move.l  %d0,%acc1
        move.l  #{accext01:#x},%d0
        move.l  %d0,%accext01
        move.l  #{macsr:#x},%d0
        move.l  %d0,%macsr
"""))

    def get_emac(self):
        """(MACSR, ACC0, ACC1, ACCEXT01), the accumulators read in integer mode."""
        self.run(assemble(f"""
        move.l  %macsr,%d0
        move.l  %d0,{self.SAVE:#x}
        moveq   #0,%d1
        move.l  %d1,%macsr
        move.l  %acc0,%d1
        move.l  %d1,{self.SAVE + 4:#x}
        move.l  %acc1,%d1
        move.l  %d1,{self.SAVE + 8:#x}
        move.l  %accext01,%d1
        move.l  %d1,{self.SAVE + 12:#x}
        move.l  %d0,%macsr
"""))
        return tuple(self.r32(self.SAVE + 4 * i) for i in range(4))


def main():
    names = sys.argv[1:]
    rt = Rt()
    for f in UNITS:
        if not names or f.__name__ in names:
            print(f"== {f.__name__}")
            f(rt)
    print(f"verify_stems_units: {fails} failure(s)")
    return 1 if fails else 0


def layout_ref(src, fmt):
    """The file table a source word and a format should latch (spec section 3)."""
    src &= SRC_BITS
    src = src or 1
    w = 48 if fmt & 1 else 32
    files = []
    for k in range(12):
        if not src >> k & 1:
            continue
        if k >= 10 and not fmt >> (k - 9) & 1:
            a = 12 + 2 * (k - 10)
            files += [(a << 24) | 0x10000 | w, ((a + 1) << 24) | 0x10000 | w]
        else:
            files.append((k << 24) | 0x20000 | 2 * w)
    fb = sum(f & 0xffff for f in files)
    return files, fb, 0x800000 // fb, 0x800000 // fb * fb


@unit
def layout(rt):
    """stems_layout against layout_ref for every source word and format."""
    s = rt.s
    bad = badfn = None
    for src in range(4096):
        for fmt in range(8):
            rt.w32(s["stems_tracks"], src)
            rt.w32(s["stems_fmt"], fmt)
            rt.w32(s["stems_wr_off"], 0)
            rt.w32(s["stems_rd_off"], 0)
            rt.call("stems_layout")
            nf = rt.r32(s["stems_nf"])
            got = ([rt.r32(s["stems_ftab"] + 4 * i) for i in range(nf)], rt.r32(s["stems_fbytes"]),
                   rt.r32(s["stems_rframes"]), rt.r32(s["stems_rlimit"]))
            ref = layout_ref(src, fmt)
            if got != ref:
                bad = (hex(src), fmt, got, ref)
                break
            # each file's routine and argument, and the tracks' part (perf design 1.4)
            w = "24" if fmt & 1 else "16"
            want = ([s[f"stems_track{w}"] if f >> 24 < 8 else s[f"stems_bus{w}"] for f in ref[0]],
                    [(f >> 24) * 0x80 if f >> 24 < 8 else f >> 24 for f in ref[0]],
                    sum(1 for f in ref[0] if f >> 24 < 8), sum(f & 0xffff for f in ref[0] if f >> 24 < 8))
            have = ([rt.r32(s["stems_ffn"] + 4 * i) for i in range(nf)],
                    [rt.r32(s["stems_farg"] + 4 * i) for i in range(nf)],
                    rt.r32(s["stems_ntrk"]), rt.r32(s["stems_tbytes"]))
            if badfn is None and have != want:
                badfn = (hex(src), fmt, have, want)
        if bad:
            break
    check("layout: every source word and format (32,768 cases)", bad is None,
          f"first difference {bad}" if bad else "")
    check("layout: each file's routine and argument, the track files and their bytes", badfn is None,
          f"first difference {badfn}" if badfn else "")


@unit
def header(rt):
    """stems_hdr_fill for 16 and 24 bits, mono and stereo."""
    s = rt.s
    for fmt, entry, ch, bits in ((0, 0x00020040, 2, 16), (0, 0x0c010020, 1, 16),
                                 (1, 0x08020060, 2, 24), (1, 0x0d010030, 1, 24)):
        rt.w32(s["stems_lfmt"], fmt)
        rt.w32(s["stems_ftab"], entry)
        rt.call("stems_hdr_fill", d3=0, a2=s["stems_buf"])
        h = rt.rmem(s["stems_buf"], 44)
        got = struct.unpack_from("<HIIHH", h, 22)
        want = (ch, 44100, 44100 * ch * bits // 8, ch * bits // 8, bits)
        check(f"header: {ch} channel(s), {bits} bits", got == want and h[:4] == b"RIFF" and h[36:40] == b"data",
              f"{got}")


LV_PAGES, LV_SENT = 0x80005460, 0x80004804      # STEM_REC.md 18.1: four pages, the index sent
DIRTY_EMAC = (0x40, 0x5a5a5a5a, 0x3c3c3c3c, 0x00a5005a)   # an interrupted task's EMAC: MACSR, ACC0, ACC1, ACCEXT01


def random_page(rng):
    page = [0] * 64
    for k in range(8):
        page[4 * k + 1] = rng.choice((0, 0x4000, 0x7f00, 0x8000, rng.randrange(0x10000)))
        page[4 * k + 2] = rng.choice((0x7f00, 0, rng.randrange(0x8000)))
        page[4 * k + 3] = rng.randrange(16) if rng.random() < 0.4 else 0
    page[0x29] = rng.choice((0x40, 0x7f, 0x80, rng.randrange(0x100)))
    return page


def send_page(rt, idx, page):
    rt.wmem(LV_PAGES + 0x80 * idx, b"".join(w.to_bytes(2, "big") for w in page))
    rt.w32(LV_SENT, idx)


def mirror_reset(rt, state=1):
    s = rt.s
    rt.w32(s["stems_state"], state)                 # ARMED (1): the gains are written
    rt.w32(s["stems_lvlast"], 0xffffffff)
    rt.w32(s["stems_gqn"], 0)
    rt.w32(s["stems_gqok"], 0)
    rt.w32(s["stems_lvskip"], 0)
    rt.wmem(s["stems_gstate"], bytes(192))          # both states
    rt.w32(s["stems_gsel"], 0)
    rt.wmem(s["stems_gcache"], b"\xff" * 64)
    rt.w32(s["stems_gw29"], 0xffffffff)


def gq_frame(rt, back=1):
    """The address of the gains' frame `back` frames before the next one."""
    return rt.s["stems_gq"] + ((rt.r32(rt.s["stems_gqn"]) - back) % GQ_N) * GQ_FRAME


def mirror_read(rt):
    """The current state's eight slots, and the newest frame's gains: each
    slot's 16, and the largest the mirror wrote before them."""
    s = rt.s
    cur = s["stems_gstate"] + rt.r32(s["stems_gsel"])
    state = [[rt.r32s(cur + 12 * k + 4 * f) for f in range(3)] for k in range(8)]
    q = gq_frame(rt)
    gq = [[rt.r32s(q + GQ_SLOT * k + 4 + 4 * j) for j in range(16)] for k in range(8)]
    tops = [rt.r32(q + GQ_SLOT * k) for k in range(8)]
    return state, gq, tops


@unit
def mirror(rt, n=4000, seed=5):
    """stems_mirror against stems_gain.Mirror: n random pages through the
    four-page ring, a third of them repeated (the target cache), with the
    edges of the arithmetic (levels 0, 0x4000, 0x7f00, 0x8000 = -1.0, any;
    the MAIN level 0x40, 0x7f, 0x80 = -1.0, any; splits 0-15). Before every
    call the EMAC holds an interrupted task's state, ACC0 not zero. After
    every page: the state of all eight slots and their 16 gains equal the
    model's, the caller's EMAC state reads back as it went in, and every
    register is as it was."""
    s = rt.s
    model = sg.Mirror(rt.table)
    mirror_reset(rt)
    rt.set_emac(*DIRTY_EMAC)
    caller = rt.get_emac()
    regs = {r: (0x10203040 + 0x01010101 * i) & 0xffffffff for i, r in enumerate(rt.REGS)}
    rng = random.Random(seed)
    page, first, emac, kept, low, free = [0] * 64, None, None, None, None, 0
    for i in range(n):
        if i == 0 or rng.random() > 0.33:
            page = random_page(rng)
        send_page(rt, i % 4, page)
        rt.set_emac(*DIRTY_EMAC)
        out = rt.call("stems_mirror", **regs)
        if emac is None and rt.get_emac() != caller:
            emac = (i, rt.get_emac(), caller)
        if kept is None and any(out[r] != v for r, v in regs.items()):
            kept = (i, {r: hex(out[r]) for r, v in regs.items() if out[r] != v})
        want = model.step(page)
        state, gq, tops = mirror_read(rt)
        if state != model.state or gq != want:
            first = (i, state[0], model.state[0], gq[0][:4], want[0][:4])
            break
        for k in range(8):
            if tops[k] <= LIM_FREE:
                free += 1
                if low is None and not all(0 <= g <= LIM_FREE for g in gq[k]):
                    low = (i, k, hex(tops[k]), [hex(g & 0xffffffff) for g in gq[k]])
    check(f"mirror: {n} pages, every slot's state and gains equal the model", first is None,
          f"first difference (page, mirror, model, gains, model's): {first}" if first else "")
    check("mirror: a slot's bound is at most LIM_FREE only when all its gains are in 0..LIM_FREE",
          low is None and free > 0,
          f"first: page, slot, bound, gains {low}" if low else f"{free} of {8 * n} slots at most LIM_FREE")
    check("mirror: the caller's MACSR, ACC0, ACC1 and ACCEXT01 come back", emac is None,
          f"page, after, before: {emac}" if emac else f"{tuple(hex(v) for v in caller)}")
    check("mirror: every register comes back", kept is None, f"page, changed: {kept}" if kept else "")
    check("mirror: no page index jump counted", rt.r32(s["stems_lvskip"]) == 0)


@unit
def mirror_cache_mark(rt):
    """The target cache marks every entry stale with the key 0xffffffff when
    the MAIN level changes. A slot whose level and index words are both
    0xffff has that key for real: it must still get its own target (0: the
    index is below the table), not the stale one."""
    model = sg.Mirror(rt.table)
    mirror_reset(rt)
    page = [0] * 64
    for k in range(8):
        page[4 * k + 1], page[4 * k + 2] = 0x7f00, 0x7f00
    page[0x29] = 0x40
    send_page(rt, 0, page)
    rt.call("stems_mirror")
    model.step(page)
    page = list(page)
    page[1], page[2], page[0x29] = 0xffff, 0xffff, 0x7f      # slot 0's key is the stale mark
    send_page(rt, 1, page)
    rt.call("stems_mirror")
    model.step(page)
    state, _, _ = mirror_read(rt)
    check("mirror_cache_mark: a real key of 0xffffffff gets its own target", state[0] == model.state[0],
          f"mirror {state[0]}, model {model.state[0]}")


TRANSPORT = 0x800065b8                          # stems.s: 1 = the sequencer plays


@unit
def mirror_idle(rt, n=60, seed=12):
    """IDLE while the sequencer plays (perf design 1.2): the state still
    follows every page, but no gains are written and stems_gqok stays 0;
    armed, each page writes a frame of gains and counts it, IDLE again
    clears the count; IDLE with the sequencer stopped writes and counts
    them, so the frame before a take's first playing frame has them."""
    s = rt.s
    model = sg.Mirror(rt.table)
    mirror_reset(rt, state=0)
    rt.w32(TRANSPORT, 1)
    rng = random.Random(seed)
    for i in range(n):
        page = random_page(rng)
        send_page(rt, i % 4, page)
        rt.call("stems_mirror")
        model.step(page)
    state, _, _ = mirror_read(rt)
    check("mirror_idle: IDLE follows every page", state == model.state, f"slot 0 {state[0]} vs {model.state[0]}")
    check("mirror_idle: IDLE writes no gains and counts nothing",
          rt.r32(s["stems_gqn"]) == 0 and rt.r32(s["stems_gqok"]) == 0,
          f"gqn {rt.r32(s['stems_gqn'])}, gqok {rt.r32(s['stems_gqok'])}")
    rt.w32(s["stems_state"], 1)
    for i in range(n, n + 3):
        page = random_page(rng)
        send_page(rt, i % 4, page)
        rt.call("stems_mirror")
        want = model.step(page)
    state, gq, _ = mirror_read(rt)
    check("mirror_idle: armed, three pages write three frames, counted, equal to the model",
          rt.r32(s["stems_gqn"]) == 3 and rt.r32(s["stems_gqok"]) == 3 and gq == want and state == model.state,
          f"gqn {rt.r32(s['stems_gqn'])}, gqok {rt.r32(s['stems_gqok'])}")
    rt.w32(s["stems_state"], 0)
    page = random_page(rng)
    send_page(rt, (n + 3) % 4, page)
    rt.call("stems_mirror")
    model.step(page)
    check("mirror_idle: IDLE again clears the count", rt.r32(s["stems_gqok"]) == 0 and rt.r32(s["stems_gqn"]) == 3)
    for t in (0, 2):                                # stopped: 0 at the end or rewind, 2 after STOP
        rt.w32(TRANSPORT, t)
        page = random_page(rng)
        send_page(rt, (n + 4 + (t // 2)) % 4, page)
        rt.call("stems_mirror")
        want = model.step(page)
    state, gq, _ = mirror_read(rt)
    check("mirror_idle: IDLE with the sequencer stopped writes the gains and counts them",
          rt.r32(s["stems_gqn"]) == 5 and rt.r32(s["stems_gqok"]) == 2 and gq == want and state == model.state,
          f"gqn {rt.r32(s['stems_gqn'])}, gqok {rt.r32(s['stems_gqok'])}")
    rt.w32(TRANSPORT, 0)


@unit
def mirror_idx4(rt):
    """The fourth frame writes the sent index 4, then 0 (STEM_REC.md 18.1).
    A 4 seen between the two is not a page: nothing changes, nothing is
    counted, and the 0 that follows is mirrored as the wrap it is."""
    s = rt.s
    mirror_reset(rt)
    rng = random.Random(7)
    for i in range(4):
        send_page(rt, i, random_page(rng))
        rt.call("stems_mirror")
    before = (mirror_read(rt), rt.r32(s["stems_gqn"]), rt.r32(s["stems_lvlast"]))
    rt.w32(LV_SENT, 4)
    rt.call("stems_mirror")
    after = (mirror_read(rt), rt.r32(s["stems_gqn"]), rt.r32(s["stems_lvlast"]))
    check("mirror_idx4: an index of 4 changes nothing", after == before,
          f"gqn {before[1]} -> {after[1]}, lvlast {before[2]} -> {after[2]}")
    send_page(rt, 0, random_page(rng))
    rt.call("stems_mirror")
    check("mirror_idx4: the 0 after it is a page, and no jump", rt.r32(s["stems_gqn"]) == before[1] + 1
          and rt.r32(s["stems_lvskip"]) == 0, f"gqn {rt.r32(s['stems_gqn'])}, skip {rt.r32(s['stems_lvskip'])}")


def post16(g, x):
    return max(-0x8000, min(0x7fff, (g * x) >> 29))


def put_track(rt, k, gains, words):
    """A track's inputs as stems_stage hands them over (perf design 1.1): the
    slot's gains in the frame GAIN_LAG before the newest, after their largest
    (unsigned, as stems_mirror writes it), and the 32 sample longs where
    TRACK_HALF puts them. Returns the registers for a track routine but a1."""
    s = rt.s
    gqn = random.Random(k * 7919 + len(gains)).randrange(GQ_N + 1, 1000)
    rt.w32(s["stems_gqn"], gqn)
    frame = s["stems_gq"] + ((gqn - 1 - GAIN_LAG) % GQ_N) * GQ_FRAME
    top = max(g & 0xffffffff for g in gains)
    rt.wmem(frame + GQ_SLOT * k, b"".join((g & 0xffffffff).to_bytes(4, "big") for g in [top] + gains))
    assert not TRACK_DELAY
    src = 0x80003190 + (0x400 if TRACK_HALF else 0) + 0x80 * k
    rt.wmem(src, b"".join((w & 0xffffffff).to_bytes(4, "big") for w in words))
    return {"d4": 0x80003190, "d5": 0x80 * k, "d7": frame}


def _track(rt, name, out_bytes, conv, n=200, seed=6, junk=False, dirty=False, free=False):
    """One track routine against `conv` on n random frames: random gains (0
    and 0x7fffff among them; with `free`, every gain in 0..LIM_FREE, the
    loop without the limit) and random samples (both full scales), put
    where stems_stage puts them. `junk`: each long's low byte random, as the
    half core 0 mixes carries it (0xff on positive samples, STEM_REC.md
    18.5); the DSP takes only the top 24 bits. `dirty`: the interrupted
    task's EMAC, ACC1 included, before the caller's stems_emac_in. Returns
    the first difference, or None."""
    s = rt.s
    rng = random.Random(seed)
    for i in range(n):
        k = rng.randrange(8)
        if free:
            gains = [rng.choice((0, LIM_FREE, 0x1f7fe0, rng.randrange(LIM_FREE + 1))) for _ in range(16)]
        else:
            gains = [rng.choice((0, 0x7fffff, 0x1f7fe0, rng.randrange(0x800000))) for _ in range(16)]
        xs = [rng.choice((0x7fffff, -0x800000, 0, rng.randrange(-0x800000, 0x800000))) for _ in range(32)]
        lows = [rng.choice((0, 0xff, rng.randrange(256))) if junk else 0 for _ in range(32)]
        regs = put_track(rt, k, gains, [(x << 8) | lo for x, lo in zip(xs, lows)])
        if dirty:
            rt.set_emac(*DIRTY_EMAC)
        rt.call("stems_emac_in")
        rt.call(name, a1=s["stems_ring"], **regs)
        rt.call("stems_emac_out")
        got = rt.rmem(s["stems_ring"], out_bytes)
        want = b"".join(conv(gains[j], xs[2 * j + c]) for j in range(16) for c in (0, 1))
        if got != want:
            j = next(b for b in range(out_bytes) if got[b] != want[b])
            return (i, k, f"byte {j}", got[j & ~3:(j & ~3) + 4].hex(), want[j & ~3:(j & ~3) + 4].hex())
    return None


def _post16_bytes(g, x):
    return (post16(g, x) & 0xffff).to_bytes(2, "big")


@unit
def track16(rt):
    """stems_track16 against post16, big-endian halves L : R, on longs whose
    low byte is not zero: only the top 24 bits are the sample."""
    bad = _track(rt, "stems_track16", 64, _post16_bytes, junk=True)
    check("track16: 200 frames equal post16 of each long's top 24 bits", bad is None,
          f"first difference (frame, slot, where, got, want) {bad}" if bad else "")
    bad = _track(rt, "stems_track16", 64, _post16_bytes, seed=13, junk=True, free=True)
    check("track16: 200 frames with every gain in 0..LIM_FREE (no limit) equal post16", bad is None,
          f"first difference (frame, slot, where, got, want) {bad}" if bad else "")


def _main_top16_bytes(g, x):
    """MAIN's own arithmetic for one track (STEM_REC.md 18.2): the 24-bit
    mix limited, then its top 16 bits."""
    v = max(-0x800000, min(0x7fffff, (g * x) >> 21)) >> 8
    return (v & 0xffff).to_bytes(2, "big")


@unit
def track16_rails(rt):
    """Review Focus 2: past both rails, the stem is the top 16 bits of MAIN's
    limited 24-bit mix. Gains up to 0x7fffff times samples at both full
    scales reach four times full scale; one THRU track can't get there
    under the port (STEM_REC.md 18.7), so this is where the rails are shown."""
    s = rt.s
    rng = random.Random(9)
    bad, rails = None, 0
    for i in range(100):
        k = rng.randrange(8)
        gains = [rng.choice((0x7fffff, 0x7c0980, 0x400000, rng.randrange(0x200000, 0x800000))) for _ in range(16)]
        xs = [rng.choice((0x7fffff, -0x800000, 0x400000, -0x400000, rng.randrange(-0x800000, 0x800000)))
              for _ in range(32)]
        regs = put_track(rt, k, gains, [x << 8 for x in xs])
        rt.call("stems_emac_in")
        rt.call("stems_track16", a1=s["stems_ring"], **regs)
        rt.call("stems_emac_out")
        got = rt.rmem(s["stems_ring"], 64)
        want = b"".join(_main_top16_bytes(gains[j], xs[2 * j + c]) for j in range(16) for c in (0, 1))
        rails += sum(1 for b in range(0, 64, 2) if want[b:b + 2] in (b"\x7f\xff", b"\x80\x00"))
        if bad is None and got != want:
            bad = (i, k, got[:8].hex(), want[:8].hex())
    check("track16_rails: 100 frames past both rails equal MAIN's limited top 16 bits",
          bad is None and rails > 500, f"{rails} samples on a rail" if bad is None else f"first difference {bad}")


@unit
def track16_emac(rt):
    """stems_track16 with an interrupted task's EMAC state, ACC0 and ACC1 not
    zero, before stems_emac_in: the same samples as from a clean one."""
    bad = _track(rt, "stems_track16", 64, _post16_bytes, seed=8, dirty=True)
    check("track16_emac: 200 frames equal post16 after an interrupted task's EMAC", bad is None,
          f"first difference (frame, slot, where, got, want) {bad}" if bad else "")


@unit
def bus16(rt, seed=8):
    """stems_bus16 for each kind 8-15: MAIN and CUE from channel 6's buffer,
    the inputs from the page of channel 7's ring that the index names this
    frame (STEM_REC.md 18.7), stereo the L and R top 16 bits, mono the
    input's own channel. Two indexes, so a fixed or stale page fails."""
    s = rt.s
    rng = random.Random(seed)
    bus = [rng.randrange(1 << 32) & 0xffffff00 for _ in range(64)]
    ring = [rng.randrange(1 << 32) & 0xffffff00 for _ in range(8 * 64)]
    rt.wmem(0x80005e60, b"".join(v.to_bytes(4, "big") for v in bus))
    rt.wmem(IN_RING, b"".join(v.to_bytes(4, "big") for v in ring))
    for idx in (0x13, 0x26):                       # pages 3 and 6 after the mod-8 mask
        rt.w32(IN_IDX, idx)
        page = (idx & 7) * 64                      # in longs
        for kind in range(8, 16):
            rt.call("stems_bus16", d5=kind, a1=s["stems_ring"])
            if kind in (8, 9):
                base = (kind - 8) * 32
                want = b"".join((bus[base + 2 * j + c] >> 16).to_bytes(2, "big") for j in range(16) for c in (0, 1))
            elif kind in (10, 11):
                base = page + (IN_AB_OFF if kind == 10 else IN_CD_OFF) // 4
                want = b"".join((ring[base + 2 * j + c] >> 16).to_bytes(2, "big") for j in range(16) for c in (0, 1))
            else:
                pair = IN_AB_OFF if kind < 14 else IN_CD_OFF
                ch = 0 if ((kind - 12) % 2 == 0) == bool(IN_A_IS_LEFT) else 1
                want = b"".join((ring[page + pair // 4 + ch + 2 * j] >> 16).to_bytes(2, "big") for j in range(16))
            got = rt.rmem(s["stems_ring"], len(want))
            check(f"bus16: index {idx:#04x}, kind {kind}", got == want, f"{got[:8].hex()} vs {want[:8].hex()}")


def b24(v):
    return (v & 0xffffff).to_bytes(3, "big")


@unit
def track24(rt):
    """stems_track24 against stems_gain.stem24, six big-endian bytes a pair,
    on longs whose low byte is not zero: only the top 24 bits are the sample."""
    bad = _track(rt, "stems_track24", 96, lambda g, x: b24(sg.stem24(g, x)), seed=11, junk=True)
    check("track24: 200 frames equal stem24 of each long's top 24 bits", bad is None,
          f"first difference (frame, slot, where, got, want) {bad}" if bad else "")
    bad = _track(rt, "stems_track24", 96, lambda g, x: b24(sg.stem24(g, x)), seed=14, junk=True, free=True)
    check("track24: 200 frames with every gain in 0..LIM_FREE (no limit) equal stem24", bad is None,
          f"first difference (frame, slot, where, got, want) {bad}" if bad else "")


@unit
def bus24(rt, seed=10):
    """stems_bus24 for each kind 8-15: MAIN and CUE from channel 6's buffer,
    the inputs from this frame's page of channel 7's ring; the 24 bits, big-
    endian, stereo L R, mono the input's own channel. Two ring indexes."""
    s = rt.s
    rng = random.Random(seed)
    bus = [rng.randrange(1 << 32) & 0xffffff00 for _ in range(64)]
    ring = [rng.randrange(1 << 32) & 0xffffff00 for _ in range(8 * 64)]
    rt.wmem(0x80005e60, b"".join(v.to_bytes(4, "big") for v in bus))
    rt.wmem(IN_RING, b"".join(v.to_bytes(4, "big") for v in ring))
    sx = lambda v: (v - (1 << 32) if v & 0x80000000 else v) >> 8    # noqa: E731
    for idx in (0x13, 0x26):
        rt.w32(IN_IDX, idx)
        page = (idx & 7) * 64
        for kind in range(8, 16):
            rt.call("stems_bus24", d5=kind, a1=s["stems_ring"])
            if kind in (8, 9):
                base = (kind - 8) * 32
                want = b"".join(b24(sx(bus[base + 2 * j + c])) for j in range(16) for c in (0, 1))
            elif kind in (10, 11):
                base = page + (IN_AB_OFF if kind == 10 else IN_CD_OFF) // 4
                want = b"".join(b24(sx(ring[base + 2 * j + c])) for j in range(16) for c in (0, 1))
            else:
                pair = IN_AB_OFF if kind < 14 else IN_CD_OFF
                ch = 0 if ((kind - 12) % 2 == 0) == bool(IN_A_IS_LEFT) else 1
                want = b"".join(b24(sx(ring[page + pair // 4 + ch + 2 * j])) for j in range(16))
            got = rt.rmem(s["stems_ring"], len(want))
            check(f"bus24: index {idx:#04x}, kind {kind}", got == want, f"{got[:9].hex()} vs {want[:9].hex()}")


@unit
def actions(rt):
    """stems_source_action and stems_switch_action: each row flips its bit
    and its label follows; the last source stays on; every row is locked
    while recording (2) or saving (3); the status and PEAK rows do nothing."""
    s = rt.s

    def press(row, state=0):
        rt.w32(s["stems_list"] + 0x0c, row)
        rt.w32(s["stems_state"], state)
        rt.call("stems_source_action" if 2 <= row <= 13 else "stems_switch_action")

    def label(row):
        return rt.rmem(rt.r32(s["stems_rows"] + 24 * row), 16).split(b"\0")[0].decode()

    rt.w32(s["stems_tracks"], 0xff)
    rt.w32(s["stems_fmt"], 6)
    press(10)
    check("actions: MAIN on", rt.r32(s["stems_tracks"]) == 0x1ff and label(10) == "MAIN [X]",
          f"{rt.r32(s['stems_tracks']):#x} {label(10)}")
    for row in range(2, 10):
        press(row)
    check("actions: every track off while MAIN is on",
          rt.r32(s["stems_tracks"]) == 0x100 and label(9) == "T8 [ ]")
    press(10)
    check("actions: the last source stays on", rt.r32(s["stems_tracks"]) == 0x100 and label(10) == "MAIN [X]")
    for state in (2, 3):
        press(9, state)
        press(16, state)
    check("actions: locked while recording and saving",
          rt.r32(s["stems_tracks"]) == 0x100 and rt.r32(s["stems_fmt"]) == 6)
    press(16)
    press(14)
    press(15)
    check("actions: 24 BIT on, both STEREO rows off, the labels follow",
          rt.r32(s["stems_fmt"]) == 0b001
          and [label(r) for r in (14, 15, 16)] == ["AB STEREO [ ]", "CD STEREO [ ]", "24 BIT [X]"],
          f"{rt.r32(s['stems_fmt']):03b}")
    press(1)
    press(17)
    check("actions: the status and PEAK rows change nothing",
          rt.r32(s["stems_tracks"]) == 0x100 and rt.r32(s["stems_fmt"]) == 0b001)


if __name__ == "__main__":
    sys.exit(main())
