#!/usr/bin/env python3
"""THE ONE AUX BUS, measured on both cores (the hardwired rig, 7 Sep 2026).

Sam's direction of 6 Sep 2026: emulate a live mixer -- ONE aux send per
track (AUX, slot 0, hosts included), a chain hardwired delay -> reverb, the
wet returned on TRACK 8 by a Character station in BUS mode (RET), the send
REFUSED on track 8 so the master loop that silenced the unit is impossible by
construction, stations without sends, and a MIX knob on each engine so a
stage passes its input through at 0. Each stage stamps itself live and the
next stage (and the return) takes the LAST LIVE stage's output, so delay
only, reverb only, both, or neither all work and no project setting can
silence the aux.

Every case below renders through tools/dsp_host with BOTH payloads booted
(docs/HARNESS.md "Two cores"): the senders and the delay on payload B where
the unit runs them, the reverb and the return on payload A, so the chain
buffer, the liveness stamps and the return all cross the real core boundary.
The image is the rig remix (bamsep27) as SPEC -- the stations must be in it.

  chain        both engines + T8 return: the return IS the reverb's stage
               output; T5 and T1 print nothing (a return is live)
  delay only   no reverb in the layout: the return falls through to the
               delay's output
  reverb only  no delay: the reverb reads the aux accumulator directly
  neither      no engine: the return is digital silence (not garbage)
  passthrough  delay MIX 0 with both engines == reverb only, two blocks
               later (the chain buffer's own latency), within -60 dB
  reverb MIX 0 reverb only, MIX 0: the return is the aux itself (x0.999)
  hosts print  no return station: T5 prints wet*MIX under its dry
  T8 refused   a SEND at core-0 position 3 with AUX 127 changes nothing
  T4 sends     the mirror position on core 1 DOES send (payload gate)
  no station   a station with the old send bytes (slots 4/5 = 127) stored
               contributes nothing to the bus
  skew         the chain case under four interleaves: identical

What this cannot show: the chip's timing (lock-step, or a guessed -skew),
and anything the ColdFire does (knobs are poked into r6).

    make verify-onebus            # ~2 min
"""
import filecmp
import math
import os
import pathlib
import shutil
import struct
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import send_probe  # noqa: E402
from remix import registry  # noqa: E402

REMIX = "bamsep27"
OUT = ROOT / "out/dsp"
SCRATCH = OUT / "_onebus"
IMAGE = ROOT / "out/mainos_bus.bin"
FRAMES = send_probe.FRAMES
PAD = send_probe.WARMUP_BLOCKS * FRAMES
SR = 44100
BLOCKS = 900
TONE_HZ = 438.75
SKEWS = (1, 37, 333, -250)


def knobs(key, **kw):
    m = registry.by_key(key)
    v = [(p.default or 0) & 0x7f for p in m.params] + [0] * 12
    km = m.knob_map_all()
    for n, x in kw.items():
        if n not in km:
            sys.exit(f"{key} has no knob {n!r}")
        v[km[n]] = x
    return v[:12]


def build(env, log):
    r = subprocess.run([sys.executable, "tools/build_bus.py"], cwd=ROOT,
                       env={**os.environ, "REMIX": REMIX, **env}, capture_output=True, text=True)
    log.write_text(r.stdout + r.stderr)
    if r.returncode != 0:
        sys.exit(f"build failed ({env}): see {log}")


def tone_file(path, blocks, amp=0.4, start=0):
    """a tone from sample PAD + start on; `start` shifts it later"""
    w = 2 * math.pi * TONE_HZ / SR
    with open(path, "wb") as f:
        for i in range(blocks * FRAMES):
            v = amp * math.sin(w * (i - PAD - start)) if i >= PAD + start else 0.0
            f.write(struct.pack("<i", int(v * 8388607)))


class Inst:
    """one effect instance: key, core, fx slot (1|2), position on its core"""
    def __init__(self, key, core, pos, fx=2, fed=False, **kw):
        self.key, self.core, self.pos, self.fx, self.fed = key, core, pos, fx, fed
        self.params = knobs(key, **kw)


def run(mems, insts, skew=None, tag="r", tone="tone.raw"):
    ep = {}
    for c, m in mems.items():
        ep[c] = {}
        for i in insts:
            fid = registry.by_key(i.key).menu.fx2_id
            ep[c][i.key] = send_probe.entry_points(m, fid)
        sid = send_probe.entry_points(m, send_probe.SERVER_ID["S"])
        for i in insts:
            if i.core == c and i.key != "SEND" and ep[c][i.key] == sid:
                sys.exit(f"{i.key} is not in payload {'AB'[c]} (its entry is SEND's)")
    out = SCRATCH / f"{tag}.raw"
    cmd = [str(send_probe.HOST), "-mem", str(mems[0]), "-memB", str(mems[1]),
           "-init", ",".join(f"{ep[i.core][i.key][0]:x}" for i in insts),
           "-proc", ",".join(f"{ep[i.core][i.key][1]:x}" for i in insts),
           "-inst", str(len(insts)),
           "-core", ",".join(str(i.core) for i in insts),
           "-alloc", ",".join(str(2 * i.pos + (i.fx - 1)) for i in insts),
           "-r7", ",".join(str(1 + 2 * i.pos + (i.fx - 1)) for i in insts),
           "-audioidx", ",".join(str(k) for k, _ in enumerate(insts)),
           "-audio", "9000",
           "-inmask", str(sum(1 << k for k, i in enumerate(insts) if i.fed)),
           "-frames", str(FRAMES), "-blocks", str(BLOCKS),
           "-in", str(SCRATCH / tone), "-out", str(out)]
    for i in insts:
        cmd += ["-params", ",".join(map(str, i.params))]
    if skew is not None:
        cmd += ["-skew", str(skew)]
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"dsp_host failed:\n{r.stdout[-2500:]}{r.stderr[-1000:]}")
    streams = []
    for k in range(len(insts)):
        p = out if k == 0 else pathlib.Path(f"{out}.i{k}")
        raw = p.read_bytes()
        a = struct.unpack(f"<{len(raw) // 4}i", raw)
        streams.append((list(a[0::2])[PAD:], list(a[1::2])[PAD:]))
    return streams


def rms_db(x):
    return 20 * math.log10(max(1e-9, math.sqrt(sum((v / 8388607) ** 2 for v in x) / max(1, len(x)))))


def peak(x):
    return max((abs(v) for v in x), default=0)


def best_lag(ref, got, scale=1.0, lo=0, hi=96):
    best = None
    for lag in range(lo, hi + 1):
        n = min(len(ref) - lag, len(got) - lag)
        if n <= 0:
            continue
        r, g = ref[:n], got[lag:lag + n]
        res = sum((gi - ri * scale) ** 2 for gi, ri in zip(g, r))
        den = sum(ri * ri for ri in r) or 1
        db = 10 * math.log10(max(1e-12, res / den))
        if best is None or db < best[1]:
            best = (lag, db)
    return best


fails = 0


def check(label, ok, detail=""):
    global fails
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}{'  ' + detail if detail else ''}")
    fails += 0 if ok else 1


def main():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    snap = SCRATCH / "mainos_bus.snapshot.bin"
    had = IMAGE.is_file()
    if had:
        shutil.copy2(IMAGE, snap)
    try:
        build({"XBUS": "1", "SPEC": "1"}, SCRATCH / "build_spec.log")
        A = send_probe.dump_mem(IMAGE, SCRATCH / "spec_A.mem", "A")
        B = send_probe.dump_mem(IMAGE, SCRATCH / "spec_B.mem", "B")
    finally:
        if had:
            shutil.copy2(snap, IMAGE)
    mems = {0: A, 1: B}
    tone_file(SCRATCH / "tone.raw", BLOCKS)
    tone_file(SCRATCH / "tone30.raw", BLOCKS, start=2 * FRAMES)

    # the rig's shape: T5 reverb (core 0 pos 0), T6 send, T8 Character BUS on
    # FX1 (core 0 pos 3), T1 delay (core 1 pos 0), T2 send
    # MOD 0 makes the reverb time-invariant, so a 30-sample-shifted copy of
    # its input gives a 30-sample-shifted output (the passthrough compare);
    # PING 0 keeps the delay's repeats on one channel, so the chain's MONO
    # average of a 438 Hz tone does not cancel between alternate repeats
    # (measured -9 dB at PING 127 with TIME 40: test artefact, not engine).
    R = lambda **k: Inst("REVERB SERVER", 0, 0, MOD=0, **k)   # noqa: E731
    D = lambda **k: Inst("DELAY SERVER", 1, 0, PING=0, **k)   # noqa: E731
    S6 = lambda **k: Inst("SEND", 0, 1, fed=True, AUX=100, **k)   # noqa: E731
    S2 = lambda **k: Inst("SEND", 1, 1, fed=True, AUX=100, **k)   # noqa: E731
    RET = lambda **k: Inst("CHARACTER", 0, 3, fx=1, SAT=3, RET=127, **k)  # noqa: E731

    print("== the chain: T2/T6 send, T1 delay -> T5 reverb -> T8 return ==")
    both = [R(), S6(), RET(), D(), S2()]
    st = run(mems, both, tag="both")
    ret, t5, t1 = st[2], st[0], st[3]
    check("the return carries audio", rms_db(ret[0]) > -45, f"rms {rms_db(ret[0]):.1f} dB")
    check("the return is stereo (L != R)", ret[0] != ret[1])
    check("T5 (reverb host) prints nothing while the return is live",
          peak(t5[0] + t5[1]) == 0, f"peak {peak(t5[0] + t5[1])}")
    check("T1 (delay host) prints nothing while the return is live",
          peak(t1[0] + t1[1]) == 0, f"peak {peak(t1[0] + t1[1])}")
    for sk in SKEWS:
        s2 = run(mems, both, skew=sk, tag="bothsk")
        check(f"chain under skew {sk:5d}: return identical", s2[2] == ret)

    print("\n== the chain is real: the delay's repeats reach the reverb ==")
    # delay MIX 127 (repeats only), delay TIME long, reverb MIX 127: the return
    # (reverb output) must differ from the reverb-only return -- the reverb
    # is fed the repeats, not the aux.
    ronly = [R(), S6(), RET(), S2()]
    st_r = run(mems, ronly, tag="ronly")
    check("reverb-only return carries audio", rms_db(st_r[2][0]) > -40)
    check("both != reverb only (the reverb hears the delay)", st[2] != st_r[2])

    print("\n== the passthrough: delay MIX 0 == no delay, two blocks later ==")
    # The chain buffer costs two blocks, and the reverb is time-variant even
    # at MOD 0 (a fixed-depth allpass modulator), so the reference is NOT the
    # reverb-only output shifted -- it is the reverb-only run fed the SAME
    # tone two blocks later, which the chain then reproduces sample for
    # sample. What is left is the delay's (1 - MIX) at MIX 0 = 0.99999988
    # and one auto-gain table against the other: rounding, -100 dB or so.
    pt = [R(), S6(), RET(), D(MIX=0), S2()]
    st_p = run(mems, pt, tag="pass")
    st_r30 = run(mems, ronly, tag="ronly30", tone="tone30.raw")
    lag, db = best_lag(st_r30[2][0], st_p[2][0], lo=0, hi=2)
    check(f"delay MIX 0 return == reverb-only fed the tone 2 blocks later (lag {lag})",
          lag == 0 and db < -80, f"residual {db:.1f} dB")

    print("\n== last live stage ==")
    donly = [S6(), RET(), D(), S2()]
    st_d = run(mems, donly, tag="donly")
    check("delay only: the return carries the delay's output", rms_db(st_d[1][0]) > -40,
          f"rms {rms_db(st_d[1][0]):.1f} dB")
    check("delay only: the delay host prints nothing (RETD stamped too)",
          peak(st_d[2][0] + st_d[2][1]) == 0)
    none = [S6(), RET(), S2()]
    st_n = run(mems, none, tag="none")
    check("no engine: the return is digital silence", peak(st_n[1][0] + st_n[1][1]) == 0,
          f"peak {peak(st_n[1][0] + st_n[1][1])}")

    print("\n== reverb MIX 0: the stage passes the aux through ==")
    rm0 = [R(MIX=0), S6(), RET(), S2()]
    st_m = run(mems, rm0, tag="rmix0")
    # the aux is the two senders' mono sum at 100/128, /sqrt(2) auto-gain
    src = struct.unpack(f"<{BLOCKS * FRAMES}i", (SCRATCH / "tone.raw").read_bytes())[PAD:]
    expect = 2 * (100 / 128) / math.sqrt(2)          # two senders, 1/sqrt(N)
    lag, db = best_lag(list(src), st_m[2][0], scale=expect * (127 / 128) * (127 / 128) * 0.9999)
    check(f"reverb MIX 0 return == the aux itself (x{expect:.3f}, RET 127/128), lag {lag}",
          db < -40, f"residual {db:.1f} dB")

    print("\n== the hosts print when nobody returns ==")
    nr = [R(), S6(), D(), S2()]
    st_h = run(mems, nr, tag="noret")
    check("T5 prints the reverb (no station)", rms_db(st_h[0][0]) > -45, f"rms {rms_db(st_h[0][0]):.1f} dB")
    check("T1 prints the delay (no station)", rms_db(st_h[2][0]) > -40, f"rms {rms_db(st_h[2][0]):.1f} dB")
    nr0 = [R(MIX=0), S6(), D(MIX=0), S2()]
    st_h0 = run(mems, nr0, tag="noret0")
    check("T5 with MIX 0 prints nothing but its (silent) dry", peak(st_h0[0][0]) == 0)
    check("T1 with MIX 0 prints nothing but its (silent) dry", peak(st_h0[2][0]) == 0)

    print("\n== the send is refused on track 8, and only there ==")
    t8 = [R(), S6(), RET(), Inst("SEND", 0, 3, fed=True, AUX=127), D(), S2()]
    # (a SEND on T8's FX2 beside the return on its FX1: the hardware shape)
    st_8 = run(mems, t8, tag="t8")
    check("a SEND on T8 (core 0 pos 3) at AUX 127 changes the return NOT AT ALL",
          st_8[2] == ret)
    t4 = [R(), S6(), RET(), D(), S2(), Inst("SEND", 1, 3, fed=True, AUX=127)]
    st_4 = run(mems, t4, tag="t4")
    check("a SEND on T4 (core 1 pos 3, the mirror) DOES change it", st_4[2] != ret)

    print("\n== the stations have no sends ==")
    # a Spectrum station on T6's FX1 with the OLD send bytes stored (slots 4
    # and 5 at 127, what a pre-rig part holds) beside T6's SEND at AUX 100
    stn = [R(), Inst("SPECTRUM", 0, 1, fx=1, fed=True), S6(), RET(), D(), S2()]
    stn[1].params[4] = 127
    stn[1].params[5] = 127
    st_s = run(mems, stn, tag="station")
    check("a station with stored send bytes 127/127 contributes nothing (return identical)",
          st_s[3] == ret)

    if fails:
        sys.exit(f"\none-aux gate: {fails} FAILURE(S)")
    print("\none-aux gate: every property holds on both cores.")
    print("  ⚠️  Lock-step and a guessed skew are not the chip's timing; the")
    print("     ColdFire is not here at all. Stamp every project before play.")


if __name__ == "__main__":
    main()
