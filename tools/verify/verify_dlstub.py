#!/usr/bin/env python3
"""The stub and the copier under dsp_host: dry until a demand-loaded effect's code is published, then the real code, bit for bit.

    python3 tools/verify/verify_dlstub.py [REMIX]       (default test/dlspike)

For each Remix.window_demand effect k the same input is rendered through the effect's own code (the reference),
through the stock null stub (the dry reference: dsp_host shapes its input, so a pass-through does not return it bit
for bit), through its stub unbound (must equal the null stub) and bound (must equal the reference, from the first
block); with the entry's words written into a copy of the dump. Each effect's dump carries its own block: two demand
effects may share one (DLPUMP loads one at a time), and dsp_modmap's dump carries only the first. Then the copier (modules/dlcopy/dlcopy.asm) is run as
an init over a staged block: with the doorbell it publishes the code and the stub runs it, without the doorbell it
leaves the stub dry, and a block with a wrong sum is not published, and a withdraw message (N = 0) makes the stub dry again. dsp_host maps P and X separately outside
the window's alias, so this proves the stub's and the copier's logic and register handling, not the hardware.

ON FX2. An effect that is live on an FX2 slot (its Claims.fx1_only lifted: the stations with SLOTS FX1+FX2, as in octabam) is
also rendered at the FX2 position (-r7 2 -alloc 1, as verify_stations_fx2 does): its own code there renders what it renders on
FX1 and is not the dry pass; its stub bound renders that; and the copier-loaded code renders it from block 0. What this cannot
see: dsp_host places the FX2 slot by its own model of the dispatcher (AGENTS.md, trap-dispatcher-model), and it maps P apart
from the window's alias, so whether an FX2 instance's own buffer overlaps the code loaded into the window of one of the four
FX2 buffer slots is the port's (verify_dlload) and the unit's to show, not this gate's.
"""
import json
import math
import pathlib
import struct
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
import dlbuild  # noqa: E402
import send_probe  # noqa: E402
from remix import registry  # noqa: E402

MAGIC = 0xB0A5ED
ENTRY = 0x33DA3                          # effect 0's entry; 8 words each (modules/dlcopy/dlcopy.asm)
STAGE, WIN = 0x2900, 0x30000
HOST = "vendor/dsp56300/build/source/dsp_host/dsp_host"
FRAMES, BLOCKS = 16, 200
TMP = pathlib.Path("out/_dlstub")
TMP.mkdir(parents=True, exist_ok=True)
fails = 0


def check(label, ok, detail=""):
    global fails
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}{'  ' + detail if detail else ''}")
    fails += 0 if ok else 1


REMIX = sys.argv[1] if len(sys.argv) > 1 else "test/dlspike"
R = registry.remix(REMIX)
DLC = dict(R.window)["DLCOPY"]           # DLCOPY's hook entry, called as an init
IMAGE = dlbuild.build(REMIX, "dlstub")
BOUND = registry.bound(R)
mem = send_probe.dump_mem(str(IMAGE), TMP / "A.mem", "A")
RECS = json.loads(pathlib.Path("out/dsp/demand_records.json").read_text())
init_n, proc_n = send_probe.entry_points(mem, 0x08)      # an unassigned id: the stock null stub

samples = []
for i in range(FRAMES * BLOCKS):
    v = int(0.4 * 8388607 * math.sin(2 * math.pi * 220 * i / 44100) + 0.1 * 8388607 * math.sin(2 * math.pi * 3100 * i / 44100))
    samples += [v, -v // 2]
(TMP / "in.raw").write_bytes(b"".join(struct.pack("<i", v) for v in samples))
src = list(struct.unpack(f"<{len(samples)}i", (TMP / "in.raw").read_bytes()))


def records(path):
    """[(space, address, [words])] of a dump, without the terminator."""
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


base_recs = records(mem)


def own_dump(key, tag):
    """The dump with `key`'s own block in it. Two demand effects may share a block (DLPUMP loads one at a time), and dsp_modmap carries only the first of them, so
    the other's entry points would land in its neighbour's code (octabam-full, retired 9 Nov 2026, put MODULATION
    and DISTORX both at P:0x3b820: `git show 07568af:remixes/test/octabam-full/remix.py`). Any other demand effect's record over the block is
    taken out and this one's put in; an overlap with anything else is resident code under a demand block, refused."""
    a0, w0 = RECS[key]["addr"], RECS[key]["words"]
    ours = {(r["addr"], len(r["words"])) for k, r in RECS.items() if k != key}
    recs, foreign = [], []
    for sp, a, w in base_recs:
        if sp == 0 and a < a0 + len(w0) and a0 < a + len(w):
            if (a, len(w)) not in ours and (a, w) != (a0, list(w0)):
                foreign.append(f"P:0x{a:05x}+{len(w)}")
            continue
        recs.append((sp, a, w))
    check("the block overlaps no resident code (another demand effect's block only)", not foreign, ", ".join(foreign))
    recs.append((0, a0, list(w0)))
    path = TMP / f"own_{tag}.mem"
    write_records(path, recs)
    return path, recs


def run(memfile, init, proc, tag, vals, slot="fx1"):
    r7, alloc = {"fx1": ("1", "0"), "fx2": ("2", "1")}[slot]
    out = TMP / f"{tag}.raw"
    cmd = [HOST, "-mem", str(memfile), "-init", f"{init:x}", "-proc", f"{proc:x}", "-inst", "1", "-r7", r7, "-alloc", alloc,
           "-inmask", "1", "-frames", str(FRAMES), "-blocks", str(BLOCKS), "-in", str(TMP / "in.raw"),
           "-out", str(out), "-params", ",".join(str(v) for v in vals)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"dsp_host failed ({tag}):\n{r.stdout[-600:]}\n{r.stderr[-600:]}")
    d = out.read_bytes()
    return list(struct.unpack(f"<{len(d) // 4}i", d))


for k, key in enumerate(R.window_demand):
    if registry.by_key(key).dsp.hooks:
        print(f"{key} (effect {k}): reached by hooks, not by an id stub -- verify_dlhook's")
        continue
    print(f"{key} (effect {k}):")
    mod = registry.modules()[key]
    rec = RECS[key]
    kmem, krecs = own_dump(key, f"{k}")
    init_m, proc_m = rec["init"], rec["proc"]                          # the real code, loaded on demand
    init_s, proc_s = send_probe.entry_points(mem, BOUND[key].menu.fx2_id)   # its id in this remix dispatches to the stub
    entry = ENTRY + 8 * k
    code_at, n = rec["addr"], len(rec["words"])
    vals = [(p.default or 0) if p.name else 0 for p in mod.params]
    direct = run(kmem, init_m, proc_m, f"direct{k}", vals)
    dry = run(kmem, init_n, proc_n, f"null{k}", vals)
    if direct == dry:                                                  # an identity at its defaults: turn the knobs up
        vals = [100 if p.name else 0 for p in mod.params]
        direct = run(kmem, init_m, proc_m, f"direct{k}", vals)
    check("the reference is not a pass-through", direct != dry)

    unbound = run(kmem, init_s, proc_s, f"unbound{k}", vals)
    check("unbound: the stub's output equals the null stub's", unbound == dry)

    def with_words(name, words):
        write_records(TMP / f"{name}.mem", krecs + [(1, entry, words)])
        return TMP / f"{name}.mem"

    bound = run(with_words(f"bound{k}", [MAGIC, init_m, proc_m]), init_s, proc_s, f"bound{k}", vals)
    check("bound: the output equals the effect's direct render, sample for sample", bound == direct,
          f"{sum(a != b for a, b in zip(bound, direct))} of {len(direct)} samples differ")
    check("wrong magic: still dry", run(with_words(f"wrongmagic{k}", [MAGIC ^ 1, init_m, proc_m]), init_s, proc_s,
                                         f"wrongmagic{k}", vals) == dry)

    code = next(w for sp, a, w in krecs if sp == 0 and a == code_at)
    check("the build's record holds the effect's code, and its dump carries it", len(code) == n and n > 100,
          f"{n} words at P:0x{code_at:05x}")
    gone = [(sp, a, [0] * len(w) if (sp == 0 and a == code_at) else w) for sp, a, w in krecs]    # not resident at boot
    halves = []
    for w in code:
        halves += [w >> 8, w & 0xFF]
    total = sum(code) & 0xFFFFFF
    staged = [0xA55A, k, code_at - WIN, n, init_m - WIN, proc_m - WIN] + halves + [total >> 8, total & 0xFF]

    def variant(name, doorbell=True, stage=True, extra=()):
        words = list(staged)
        if not doorbell:
            words[0] = 0
        write_records(TMP / f"{name}.mem", gone + ([(1, STAGE, words)] if stage else []) + list(extra))
        return TMP / f"{name}.mem"

    stale = [w | 0x400000 for w in staged]                              # the byte above a host word's 16 bits is stale on the unit (0x40)
    write_records(TMP / f"stale{k}.mem", gone + [(1, STAGE, stale)])
    check("every staged word with a stale high byte (0x40): the copier still binds it and the stub runs the real code",
          run(TMP / f"stale{k}.mem", DLC, proc_s, f"stale{k}", vals) == direct)
    check("not staged, code absent: the stub stays dry", run(variant(f"cold{k}", stage=False), init_s, proc_s, f"cold{k}", vals) == dry)
    check("staged without the doorbell: still dry", run(variant(f"nobell{k}", doorbell=False), init_s, proc_s, f"nobell{k}", vals) == dry)
    check("staged without the doorbell: the copier leaves the stub dry",
          run(variant(f"nobellc{k}", doorbell=False), DLC, proc_s, f"nobellc{k}", vals) == dry)
    loaded = run(variant(f"loaded{k}"), DLC, proc_s, f"loaded{k}", vals)
    check("staged with the doorbell: the copier binds it and the stub runs the real code from block 0",
          loaded == direct, f"{sum(x != y for x, y in zip(loaded, direct))} of {len(direct)} samples differ")
    bad = list(staged)
    bad[6 + n] ^= 1                                                    # one bit of one code word
    write_records(TMP / f"badsum{k}.mem", gone + [(1, STAGE, bad)])
    check("staged with one bit wrong: the copier does not publish it, the stub stays dry",
          run(TMP / f"badsum{k}.mem", DLC, proc_s, f"badsum{k}", vals) == dry)
    claims = BOUND[key].claims
    if claims is not None and claims.fx1_only:
        print("  (FX1 only here: no FX2 render)")
    else:
        direct2 = run(kmem, init_m, proc_m, f"direct2_{k}", vals, "fx2")
        dry2 = run(kmem, init_n, proc_n, f"null2_{k}", vals, "fx2")
        check("FX2: the effect's own code renders what it renders on FX1, sample for sample", direct2 == direct,
              f"{sum(a != b for a, b in zip(direct2, direct))} of {len(direct)} samples differ")
        check("FX2: the render is not the dry pass", direct2 != dry2)
        check("FX2: bound, the stub runs the real code",
              run(TMP / f"bound{k}.mem", init_s, proc_s, f"bound2_{k}", vals, "fx2") == direct2)
        loaded2 = run(variant(f"loaded2_{k}"), DLC, proc_s, f"loaded2_{k}", vals, "fx2")
        check("FX2: staged with the doorbell, the copier binds it and the stub runs the real code from block 0",
              loaded2 == direct2, f"{sum(x != y for x, y in zip(loaded2, direct2))} of {len(direct2)} samples differ")
        check("FX2: unbound, the stub is the dry pass", run(kmem, init_s, proc_s, f"unbound2_{k}", vals, "fx2") == dry2)
    others = [(1, ENTRY + 8 * j, [MAGIC, 1, 2, 3, 4]) for j in range(len(R.window_demand)) if j != k]
    write_records(TMP / f"withdraw{k}.mem", krecs + [(1, entry, [MAGIC, init_m, proc_m, code_at, code_at + n])]
                  + others + [(1, STAGE, [0xA55A, k, 0, 0, 0, 0])])
    check("withdrawn after a bind: the stub is dry again",
          run(TMP / f"withdraw{k}.mem", DLC, proc_s, f"withdraw{k}", vals) == dry)

print("PASS" if not fails else f"{fails} FAIL")
sys.exit(1 if fails else 0)
