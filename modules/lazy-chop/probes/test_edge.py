"""LAZY CHOP edge cases: a STATIC slot, played by T5 (DSP core 0), with a trimmed start."""
import pathlib, re, struct, sys
ROOT = pathlib.Path(__file__).resolve().parents[2]
for p in ("tools", "tools/verify", "tools/panel"):
    sys.path.insert(0, str(ROOT / p))
import toolpath  # noqa
import verify_repitch as vr
from stems_panel import MenuPort
otp = vr.otp
OUT = ROOT / "out/lc"; work = OUT / "we"; work.mkdir(parents=True, exist_ok=True)
src = ROOT / "out/_src/om/src-tauri/tests/fixtures/real_device"
TRIM = 11025
vr.build_project(src, work / "project", 0, 0, 120.0, 64, 127, "static")
def mut(data):
    for pt in range(otp.NPARTS_ALL):
        base = otp.PART_BASE + pt * otp.PART_STRIDE
        data[base + otp.MTYPE_OFF + 4] = data[base + otp.MTYPE_OFF]          # T5 = T1's machine (STATIC)
        for k in range(5):
            data[base + 0x2d3 + 4 * 5 + k] = data[base + 0x2d3 + k]           # T5's slot bytes = T1's
        for off in (vr.SETUP_OFF, vr.VALUES_OFF):
            data[base + off + 4 * 30:base + off + 5 * 30] = data[base + off:base + off + 30]
otp._bank_write(work / "project", 1, mut, guard=False)
mrec = vr.MACHINES["static"][1]
for suffix in ("work", "strd"):
    pm = work / "project" / f"markers.{suffix}"
    if pm.is_file():
        d = bytearray(pm.read_bytes()); at = 0x16 + 784 * mrec
        d[at:at + 4] = struct.pack(">I", TRIM)
        d[-2:] = (sum(d[0x10:-2]) & 0xFFFF).to_bytes(2, "big")
        pm.write_bytes(bytes(d))
card = work / "card.img"; vr.stage(work / "project", card, OUT / "REPITCH_440_120.wav")

m = (ROOT / "out/platform/runtime/runtime.map").read_text()
sym = lambda n: int(re.search(rf"(0x[0-9a-f]+)\s+{n}\n", m).group(1), 16)
ST, LREC, TRK = sym("lc_state"), sym("lc_rec"), None
REC = 0x100d5b30                                        # STATIC slot 1's record
V5 = 0x800049d8 + 4 * 0xa8
fails = []
def check(c, what):
    print(("PASS " if c else "FAIL ") + what)
    if not c: fails.append(what)
def slices(p):
    n = p.long(REC + 1092)
    return n, [struct.unpack(">IIi", p.peek(REC + 312 + 12 * k, 12)) for k in range(min(n, 64))]
def tap(p, k, gap=150):
    p.key(k, True); p.run(20); p.key(k, False); p.run(gap - 20)
with MenuPort(ROOT / "out/mainos_bus.bin", card, "OCTABAM", "RIG", mkii=False, log_path=OUT / "port_e.log") as p:
    p.settle()
    p.chord("t5", "bank", settle=600)
    print("editor slot", p.long(0x46c8d19c), "kind", p.long(0x46c8d1a0), "trim", p.long(REC + 300), p.long(REC + 304), "count", p.long(REC + 1092))
    check(p.long(0x46c8d1a0) == 0 and p.long(0x46c8d19c) == 0, "[T5]+[BANK] opens the editor on STATIC slot 1")
    check(p.long(REC + 300) == TRIM, f"the slot's trim start is {TRIM}")
    p.press("pg_amp", settle=400)
    p.chord("func", "bank", settle=500)
    for _ in range(11): p.press("up", settle=80)
    for _ in range(2): p.press("down", settle=120)
    p.press("yes", settle=400)
    check(p.long(ST) == 1 and p.long(LREC) == REC, "LAZY CHOP arms on the STATIC record")
    tap(p, "trig1", 100)
    print("voice T5: active", p.peek(V5, 1)[0], "settings", hex(p.long(V5 + 8)), "pos", p.long(V5 + 68))
    check(p.peek(V5, 1)[0] and p.long(V5 + 8) == REC, "TRIG 1 plays T5 (core 0) from the STATIC slot")
    for k in range(2, 7):
        tap(p, f"trig{k}")
    p.press("yes", settle=400)
    n, s = slices(p)
    print("slices:", n, s)
    check(n == 6, f"6 slices ({n})")
    check(s and s[0][0] == TRIM and all(x[0] >= TRIM for x in s), "the first starts at the trimmed start; none before it")
    check(all(s[i][1] == s[i + 1][0] for i in range(n - 1)) and s[-1][1] == p.long(REC + 304), "chained to the trim end")
    check(all(abs((s[i + 1][0] - s[i][0]) - 6615) < 400 for i in range(1, n - 1)), "markers 150 ms apart")
print("FAILED:", fails if fails else "none")
