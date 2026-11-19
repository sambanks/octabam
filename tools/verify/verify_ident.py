#!/usr/bin/env python3
"""Prove a rewritten insert renders BIT-IDENTICALLY to a saved reference,
across a knob matrix: every mode with two knob sets, all zeros, all max.

    python3 tools/verify/verify_ident.py <module> ref     # stamp from the current build
    python3 tools/verify/verify_ident.py <module> check   # compare the current build

The reference is out/ident_<module>_ref.json (gitignored, per worktree).
Every 0..127 knob is driven off its default so each stage carries signal;
the select (MODE / SAT) is swept over its count. The Spectrum-specific
matrix stays in verify_spectrum_ident.py.

It renders on the module's own slot (schema.render_slot): VOCODER runs at
r7 5 only, and on slot 1 its dry pass hashed the same before and after any
change. A control fails the run when `defaults` and `max` render the same
audio: the render never reached the module.
"""
import hashlib, json, math, pathlib, struct, subprocess, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
import send_probe
from remix import registry, schema

if len(sys.argv) < 2:
    sys.exit(__doc__)
MOD = registry.by_name(sys.argv[1])
SEND = registry.by_name("send")
K = MOD.knob_map()
MEM = f"out/dsp/_audition_{MOD.name}_A.mem"
HOST = "vendor/dsp56300/build/source/dsp_host/dsp_host"
FXID = MOD.menu.fx2_id
FRAMES, N = 15, 6000
SR = 44100
TMP = pathlib.Path(f"out/_identgate_{MOD.name}")
TMP.mkdir(parents=True, exist_ok=True)
REF = pathlib.Path(f"out/ident_{MOD.name}_ref.json")

# Rebuild the dump every run: a stale audition cache measures the STOCK
# effect on this id (verify_spectrum_ident.py's note).
pathlib.Path(MEM).unlink(missing_ok=True)
subprocess.run([sys.executable, "tools/remix/audition.py", MOD.name,
                "out/dry/drums_110.wav"], capture_output=True)
if not pathlib.Path(MEM).exists():
    sys.exit(f"no {MEM}: python3 tools/remix/audition.py {MOD.name} out/dry/drums_110.wav")
init, proc = send_probe.entry_points(MEM, FXID)
if (init, proc) == send_probe.entry_points(MEM, SEND.menu.fx2_id):
    sys.exit(f"fx id 0x{FXID:02x} resolves to SEND's entry points -- {MOD.name} is NOT in this dump")

DEFAULTS = [(p.default or 0) for p in MOD.params]
NAMES = [p.name.decode() for p in MOD.params]


def params(**kw):
    v = list(DEFAULTS)
    for name, val in kw.items():
        v[K[name]] = val
    return v


OWN = schema.render_slot(MOD)


def render(samples, **kw):
    src = TMP / "in.raw"
    src.write_bytes(b"".join(struct.pack("<i", m) for m in samples))
    out = TMP / "out.raw"
    cmd = [HOST, "-mem", MEM, "-init", f"{init:x}", "-proc", f"{proc:x}",
           "-inst", "1", "-r7", str(OWN[0]), "-alloc", str(OWN[1]), "-inmask", "1",
           "-frames", str(FRAMES), "-blocks", str(len(samples) // FRAMES),
           "-in", str(src), "-out", str(out),
           "-params", ",".join(str(x) for x in params(**kw))]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"dsp_host failed for {kw}:\n{r.stdout}\n{r.stderr}")
    d = out.read_bytes()
    w = struct.unpack(f"<{len(d)//4}i", d)
    return list(w[0::2])[:len(samples)], list(w[1::2])[:len(samples)]


def signal():
    a = [0.30 * math.sin(2 * math.pi * 440 * i / SR) for i in range(N)]
    b = [0.15 * math.sin(2 * math.pi * 2500 * i / SR) for i in range(N)]
    return [max(-8388608, min(8388607, int(8388607 * (x + y) + (838860 if i > N // 2 else 0))))
            for i, (x, y) in enumerate(zip(a, b))]


def settings():
    sel = next((p for p in MOD.params if p.name and 2 <= (p.count or 128) <= 8), None)
    plain = [p.name.decode() for p in MOD.params if p.name and (p.count or 128) == 128]
    hot = {n: 90 for n in plain}
    cool = {n: 40 for n in plain}
    out = {"defaults": {}}
    modes = range(sel.count) if sel else [None]
    for mode in modes:
        m = {sel.name.decode(): mode} if sel else {}
        out[f"mode{mode}_hot"] = dict(hot, **m)
        out[f"mode{mode}_cool"] = dict(cool, **m)
    out["zeros"] = {n: 0 for n in NAMES if n}
    out["max"] = {n: ((MOD.params[NAMES.index(n)].count or 128) - 1) for n in NAMES if n}
    return out


def hashes():
    sig = signal(); out = {}
    h = lambda v: hashlib.sha1(b"".join(int(x).to_bytes(4, "little", signed=True) for x in v)).hexdigest()[:16]
    for label, kw in settings().items():
        L, R = render(sig, **kw)
        out[label] = [h(L), h(R), max(abs(x) for x in L + R)]
    return out


if __name__ == "__main__":
    mode = sys.argv[2] if len(sys.argv) > 2 else "check"
    got = hashes()
    print(f"  slot r7 {OWN[0]} / alloc {OWN[1]}")
    if got["defaults"][:2] == got["max"][:2]:
        sys.exit(f"  [CONTROL FAIL] defaults and max render the same audio: the render does not "
                 f"reach {MOD.name} (a wrong slot, a dry pass, the SEND alias?)")
    if mode == "ref":
        REF.write_text(json.dumps(got, indent=1))
        print(f"reference saved: {len(got)} settings -> {REF}")
        for k, v in got.items():
            print(f"  {k:24s} peak {v[2]}")
    else:
        ref = json.loads(REF.read_text())
        bad = [k for k in ref if got.get(k) != ref[k]]
        for k in ref:
            print(f"  [{'PASS' if k not in bad else 'FAIL'}] {k}")
        print(f"\n{'IDENTICAL' if not bad else 'DIFFERS'}: {len(ref)-len(bad)}/{len(ref)} settings bit-identical")
        sys.exit(1 if bad else 0)
