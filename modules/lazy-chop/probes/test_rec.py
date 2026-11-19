"""LAZY CHOP on a recorder buffer: T1 FLEX plays R1; record a take; [REC AB]+[BANK]; chop."""
import pathlib, re, struct, sys
ROOT = pathlib.Path(__file__).resolve().parents[2]
for p in ("tools", "tools/verify", "tools/panel"):
    sys.path.insert(0, str(ROOT / p))
import toolpath  # noqa
import verify_repitch as vr
from stems_panel import MenuPort
otp = vr.otp
OUT = ROOT / "out/lc"; work = OUT / "wr"; work.mkdir(parents=True, exist_ok=True)
src = ROOT / "out/_src/om/src-tauri/tests/fixtures/real_device"
vr.build_project(src, work / "project", 0, 0, 120.0, 64, 127, "flex")
def mut(data):
    for pt in range(otp.NPARTS_ALL):
        base = otp.PART_BASE + pt * otp.PART_STRIDE
        data[base + 0x2d3 + 1] = 128                 # T1 FLEX slot: recorder buffer 1 (FLEX 129)
otp._bank_write(work / "project", 1, mut, guard=False)
card = work / "card.img"; vr.stage(work / "project", card, OUT / "REPITCH_440_120.wav")

m = (ROOT / "out/platform/runtime/runtime.map").read_text()
sym = lambda n: int(re.search(rf"(0x[0-9a-f]+)\s+{n}\n", m).group(1), 16)
ST, NXT, LREC = sym("lc_state"), sym("lc_next"), sym("lc_rec")
R1 = 0x100b14f0 + 128 * 1096                          # recorder buffer 1's record
CTRL = 0x46c922c4 + 44 * 128                           # its control record
fails = []
def check(c, what):
    print(("PASS " if c else "FAIL ") + what)
    if not c: fails.append(what)
def slices(p, rec):
    n = p.long(rec + 1092)
    return n, [struct.unpack(">IIi", p.peek(rec + 312 + 12 * k, 12)) for k in range(min(n, 64))]
def tap(p, k, gap=200):
    p.key(k, True); p.run(20); p.key(k, False); p.run(gap - 20)
def text(p):
    return "\n".join("".join("#" if c else "." for c in r) for r in p.screen())
with MenuPort(ROOT / "out/mainos_bus.bin", card, "OCTABAM", "RIG", mkii=False, log_path=OUT / "port_rec.log") as p:
    p.settle()
    p.press("t1", settle=200)
    print("before take: ctrl len", p.long(CTRL + 16), "state@8", p.long(CTRL + 8), "trim end", p.long(R1 + 304))
    p.chord("t1", "recab", settle=200)                   # [TRACK 1] + [REC AB]: record into R1
    for i in range(3):
        p.run(1000)
        print(f"t+{i+1}s: ctrl len {p.long(CTRL + 16)} trim end {p.long(R1 + 304)} ctrl", p.peek(CTRL, 44).hex())
    name = lambda: p.peek(CTRL + 24, 16).split(b"\0")[0].decode("latin1")
    p.chord("t1", "recab", settle=300)                   # again: stop the take
    print("after second [T1]+[REC AB]: name", name(), "trim end", p.long(R1 + 304))
    for i in range(16):
        if not name().startswith("RECORDING"): break
        p.run(1000)
    print("take done:", name(), "trim end", p.long(R1 + 304), "after", i, "more s")
    took = p.long(R1 + 304)
    check(took > 44100, f"a take of {took} samples in R1")
    p.png(OUT / "r0_after_take.png")
    p.chord("recab", "bank", settle=600)                 # MKI: [REC AB] + [BANK]: the editor on the track's buffer
    print("editor slot", p.long(0x46c8d19c), "kind", p.long(0x46c8d1a0))
    check(p.long(0x46c8d19c) == 128, "[REC AB]+[BANK] opens the editor on recorder buffer 1")
    (OUT / "r1_aed.txt").write_text(text(p)); p.png(OUT / "r1_aed.png")
    p.press("pg_amp", settle=400)
    p.png(OUT / "r1_slice.png")
    on = p.long(0x400ceb3c) < 0x80000000
    selw, last = (0x460e5f58, 5) if on else (0x460e5f54, 2)
    p.chord("func", "bank", settle=500)
    lp = p.long(0x460e5e2c)
    print("menu labels ptr", hex(lp), "first label", p.cstr(p.long(lp)) if 0x40000000 <= lp < 0x48000000 else "-", "sel", p.long(selw))
    (OUT / "r1_menu.txt").write_text(text(p)); p.png(OUT / "r1_menu.png")
    for _ in range(11):
        p.press("up", settle=80)                  # the list stops at the top
    for _ in range(last):
        p.press("down", settle=120)
    p.press("yes", settle=400)
    check(p.long(ST) == 1 and p.long(LREC) == R1, "LAZY CHOP arms on the recorder buffer's record")
    print("after LAZY CHOP row: state", p.long(ST))
    tap(p, "trig1")
    v = 0x800049d8
    print("voice T1: active", p.peek(v, 1)[0], "settings", hex(p.long(v + 8)), "pos", p.long(v + 68))
    check(p.long(v + 8) == R1 and p.long(ST) == 2, "TRIG 1 plays T1 from R1")
    for k in range(2, 9):
        tap(p, f"trig{k}")
    p.press("yes", settle=400)
    n, s = slices(p, R1)
    print("R1 slices:", n, s)
    check(n == 8 and all(s[i][1] == s[i + 1][0] for i in range(7)) and s[-1][1] == p.long(R1 + 304),
          "8 slices on the take, chained to its end")
    check(all(abs((s[i + 1][0] - s[i][0]) - 8820) < 400 for i in range(1, 7)), "markers 200 ms apart (8,820 samples)")
    p.png(OUT / "r2_done.png")
print("FAILED:", fails if fails else "none")
