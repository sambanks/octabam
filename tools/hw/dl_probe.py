#!/usr/bin/env python3
"""Read a stalled DSP on an image built with tools/hw/dlprobe.patch applied.

  .venv/bin/python3 tools/hw/dl_probe.py log      # the last 22 frame interrupts (safe on a running unit)
  .venv/bin/python3 tools/hw/dl_probe.py window   # the shared window through core A (a STALLED DSP only)

dlprobe.patch is a test edit (`git apply`, build, never commit applied; the image cannot switch remixes: REMIX
SWITCH's park is replaced). It carries framelog.patch's frame log, never frozen, with per frame the pump's state, a
bad-DSP-record flag, the FRAME GUARD flag and each core's busy; and three host commands on each core ($03: a pointer
to X:$30000; $0F, $10, $11: the low, middle and high byte of the word there, $11 stepping the pointer), run by USB
request 0xc0/0x57 block 4 with interrupts masked (wValue high << 8 | wIndex high = the first word, 63 words a reply).
The handlers clobber a, r2, r3 and m3 on the core that takes them: `window` on a running unit stops it.

`window` prints the host-port registers as found (HF2 and HF3 are free for breadcrumbs: ISR bits 3 and 4), the demand
loader's entries (X:$33da3 + 8 k), LOAD METER's blocks, the words both cores exchange at X:$30000 and X:$38000, and
compares each bound effect's code with out/dsp/demand_records.json. It reads the image last built in this tree.
"""
import json
import pathlib
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import load_meter as lm  # noqa: E402

BASE = 0x30000


def frame_log(dev):
    ctrl = lambda w, off, n: bytes(dev.ctrl_transfer(0xc0, 0x57, w, off, n, timeout=1000))  # noqa: E731
    w = struct.unpack(">64I", lm.read_block(ctrl, 2, 256))
    nxt = w[2] if 20 <= w[2] <= 62 else 20
    fr = [(w[i], w[i + 1]) for i in list(range(nxt, 64, 2)) + list(range(20, nxt, 2)) if w[i]]
    ends = sorted(x for x in w[4:20] if x)
    print(w[0], "frame interrupts; entry us, duration us, pump state, B bad record, G guarded, DSP busy % core 0 / 1, chain end us")
    for k, (t, pk) in enumerate(fr):
        nt = fr[k + 1][0] if k + 1 < len(fr) else None
        ce = [e for e in ends if (e - t) & 0xffffffff < 132000 and (nt is None or (nt - e) & 0xffffffff < 0x80000000)]
        hi = pk >> 16
        print(f"{((t - fr[0][0]) & 0xffffffff) / 132.0:8.1f}  dur {(hi & 0xfff) * 64 / 132.0:6.1f}  pump {(hi >> 12) & 3}"
              f" {'B' if hi & 0x4000 else '-'}{'G' if hi & 0x8000 else '-'}  dsp {((pk >> 8) & 0xff) * 256 / 362.56:5.1f}"
              f" {(pk & 0xff) * 256 / 362.56:5.1f}  chain {'-' if not ce else round((ce[0] - t) / 132.0)}")


def window(dev):
    status = [0]

    def peek(addr, n):
        out = []
        while len(out) < n:
            off, raw = addr + len(out) - BASE, b""
            while len(raw) < 256:
                got = bytes(dev.ctrl_transfer(0xc0, 0x57, (off >> 8) << 8 | 4, (off & 0xff) << 8 | len(raw), 256 - len(raw), timeout=20000))
                if not got:
                    break
                raw += got
            w = struct.unpack(">64I", raw)
            status[0] = w[0]
            out += w[1:]
        return out[:n]

    f = lambda v: "not-taken" if v == 0xffffffff else "no-reply" if v == 0xfffffffe else f"{v:06x}"  # noqa: E731
    ent = peek(0x33da3, 40)
    st = status[0]
    for name, cvr, isr in (("A", st >> 24, st >> 16 & 0xff), ("B", st >> 8 & 0xff, st & 0xff)):
        print(f"core {name}: CVR {cvr:02x} ISR {isr:02x} (HF2 {'set' if isr & 8 else 'clear'}, HF3 {'set' if isr & 16 else 'clear'})")
    for k in range(5):
        e = ent[8 * k:8 * k + 8]
        print(f"entry {k}: bound {f(e[0])} init {f(e[1])} proc {f(e[2])} span {f(e[3])}..{f(e[4])} received {f(e[5])} refused {f(e[6])} published {f(e[7])}")
    cells = peek(0x37f10, 64)
    for c in (0, 1):
        b = cells[8 * c:8 * c + 8]
        print(f"core {c}: frame start {f(b[0])} busy {f(b[1])} period {f(b[2])} slot start {f(b[3])} next cost cell {f(b[4])}")
        print("  cost cells " + " ".join(f(x) for x in cells[0x30 + 8 * c:0x38 + 8 * c]))
    print("X:$30000.. " + " ".join(f(x) for x in peek(0x30000, 80)))
    print("X:$38000.. " + " ".join(f(x) for x in peek(0x38000, 32)))
    recs = pathlib.Path("out/dsp/demand_records.json")
    if not recs.is_file():
        return
    for k in range(5):
        e = ent[8 * k:8 * k + 8]
        if e[0] != 0xb0a5ed:
            continue
        for name, rec in json.loads(recs.read_text()).items():
            for h in rec["homes"]:
                if h["addr"] == e[3] and h["addr"] + len(h["words"]) == e[4]:
                    got = peek(h["addr"], len(h["words"]))
                    bad = [(h["addr"] + i, g, x) for i, (g, x) in enumerate(zip(got, h["words"])) if g != x]
                    print(f"entry {k} = {name} at P:${h['addr']:05x}, {len(h['words'])} words: {len(bad)} differ from the staged block"
                          + "".join(f"\n   ${a:05x}: read {f(g)} staged {x:06x}" for a, g, x in bad[:12]))


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("log", "window"):
        sys.exit(__doc__)
    (frame_log if sys.argv[1] == "log" else window)(lm.libusb_device())
