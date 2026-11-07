#!/usr/bin/env python3
"""A hooked demand module's resident stubs under dsp_host: the displaced instruction while the code is not loaded, the body once it is.

    python3 tools/verify/verify_dlhook.py [REMIX]       (default octabam)

For every hook stub the build placed (out/dsp/window_records.json, "hook stub ...": docs/contributing/DEMAND_LOADER.md),
on each payload it serves, a wrapper in the window seeds x:$420 (the core's first track) and X:0..$1f (a counter, the
track's block), calls the stub, and parks r0, r6, n6, r4, x0 and r1 in Y. The run must equal, word for word in
all of X and Y and in those registers, a reference wrapper that does what the stub should:

  BOUND clear (0), or a wrong magic   the displaced stock instruction alone; at a bridged site, the overridden
                                      hook's entry alone (it replays the instruction itself)
  BOUND set ($b0a5ed)                 the body, called directly; at a bridged site, the body and then the entry

and the BOUND-set run must differ from the clear one, so the body is known to have run. The module's block is added
to the dump (dsp_modmap leaves out a demand record that overlaps another's). At a site bridged to LOAD METER, the
cost cells its otop_e2 stamps from the frame timer (x:$37f40..$37f4f) differ with the cycles the stub adds and are
not compared; the pointer to the next one, which otop_e2 advances, is. dsp_host maps P, X and Y separately, so this
proves the stubs' logic and register handling, not the hardware's aliasing of the window.
"""
import json
import pathlib
import struct
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
import dlbuild  # noqa: E402
import send_probe  # noqa: E402
from remix import registry  # noqa: E402

MAGIC = 0xB0A5ED
ENTRY = 0x33DA3                          # effect k's entry is x:$33da3 + 8 k (modules/dlcopy/dlcopy.asm)
HOST = "vendor/dsp56300/build/source/dsp_host/dsp_host"
ASM = "vendor/dsp56300/build/source/dsp_host/dsp_asm"
DIS = "vendor/dsp56300/build/source/disassemble/dsp56kDisassemble"
WRAP = 0x30100                           # the wrapper, in window P no record of the remix uses
PARK = 0x6F00                            # Y words the wrapper parks the registers in
LM_COST = range(0x37F40, 0x37F50)        # LOAD METER's timer-stamped cost cells
TMP = pathlib.Path("out/_dlhook")
TMP.mkdir(parents=True, exist_ok=True)
fails = 0


def check(label, ok, detail=""):
    global fails
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}{'  ' + detail if detail else ''}")
    fails += 0 if ok else 1


REMIX = sys.argv[1] if len(sys.argv) > 1 else "octabam"
R = registry.remix(REMIX)
IMAGE = dlbuild.build(REMIX, "dlhook")
WIN = json.loads(pathlib.Path("out/dsp/window_records.json").read_text())
DEM = json.loads(pathlib.Path("out/dsp/demand_records.json").read_text())
STUBS = {k: v for k, v in WIN.items() if k.startswith("hook stub ")}


def records(path):
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


def assemble(src, org):
    a, o = TMP / "w.asm", TMP / "w.bin"
    a.write_text(src)
    r = subprocess.run([ASM, "-in", str(a), "-org", f"{org:x}", "-out", str(o)], capture_output=True, text=True)
    if r.returncode or not o.exists():
        sys.exit(f"dsp_asm failed:\n{src}\n{r.stdout}{r.stderr}")
    raw = o.read_bytes()
    return [int.from_bytes(raw[i:i + 3], "little") for i in range(0, len(raw), 3)]


def displaced(words):
    """The two stock words as source text (the build's own disassembly route)."""
    f = TMP / "d.txt"
    f.write_text(" ".join(f"{w:06x}" for w in words))
    out = subprocess.run([DIS, "-in", str(f), "-pc", "0"], capture_output=True, text=True).stdout
    lines = [" ".join(l.split(":", 1)[1].split(";", 1)[0].split()) for l in out.splitlines()
             if len(l) > 8 and l[6] == ":" and all(c in "0123456789abcdef" for c in l[:6])]
    return "".join(f"        {l}\n" for l in lines)


def wrapper(track, calls):
    """calls: [("bsr", target) | ("text", source)], in order. Each bsr's displacement is a number (the brclr trap)."""
    head = (f"zwrp:\n        move    #>${track:x},x0\n        move    x0,x:>$420\n        move    #0,r0\n"
            f"        move    #>$5a0000,r5\n        do      #<$20,zwfl\n        move    r5,x:(r0)+\n        move    (r5)+\nzwfl:\n"
            f"        move    #0,r0\n")
    tail = "".join(f"        move    {r},y:>${PARK + i:x}\n" for i, r in enumerate(("r0", "r6", "n6", "r4", "x0", "r1"))) + "        rts\n"
    body = ""
    for kind, v in calls:
        body += f"        bsr     >$0\n" if kind == "bsr" else v
    words = assemble(head + body + tail, WRAP)          # sizing pass: every bsr is two words
    at, body = WRAP + len(assemble(head, WRAP)), ""
    for kind, v in calls:
        if kind == "bsr":
            body += f"        bsr     >${(v - at) & 0xFFFFFF:x}\n"
            at += 2
        else:
            body += v
            at += len(assemble(v, at)) if v.strip() else 0
    out = assemble(head + body + tail, WRAP)
    if len(out) != len(words):
        sys.exit("verify_dlhook: the wrapper changed length between passes")
    return out


def run(base, extra, wrap, tag):
    m = TMP / f"{tag}.mem"
    write_records(m, base + extra + [(0, WRAP, wrap)])
    rts = WRAP + len(wrap) - 1
    dumps = {}
    for space, lo, hi in (("x", 0, 0x40000), ("y", 0, 0x40000)):
        f = TMP / f"{tag}.{space}"
        r = subprocess.run([HOST, "-mem", str(m), "-init", f"{rts:x}", "-proc", f"{WRAP:x}", "-inst", "1", "-r7", "1",
                            "-alloc", "0", "-frames", "15", "-blocks", "1", "-params", "64,64,64,64,64,64,0,2,1,64,0,127",
                            "-dumpy", f"{lo:x},{hi:x},{'@' if space == 'x' else ''}{f}"], capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit(f"dsp_host failed ({tag}):\n{r.stdout[-800:]}\n{r.stderr[-800:]}")
        raw = f.read_bytes()
        dumps[space] = [int.from_bytes(raw[j:j + 4], "little") & 0xFFFFFF for j in range(0, len(raw), 4)]
    return dumps


def same(a, b, mask_cost):
    dx = [i for i, (u, v) in enumerate(zip(a["x"], b["x"])) if u != v and not (mask_cost and i in LM_COST)]
    dy = [i for i, (u, v) in enumerate(zip(a["y"], b["y"])) if u != v]
    return not dx and not dy, f"X differs at {[hex(i) for i in dx[:4]]}, Y at {[hex(i) for i in dy[:4]]}" if dx or dy else ""


def main():
    hooked = [k for k in R.window_demand if registry.by_key(k).dsp.hooks]
    if not hooked:
        print(f"{REMIX}: no hooked demand module -- nothing to check")
        print("PASS")
        return
    for key in hooked:
        k = list(R.window_demand).index(key)
        mod = registry.by_key(key)
        rec = DEM[key]
        block = [(0, rec["addr"], list(rec["words"]))]
        bodies = None
        for tag in ("A", "B"):
            base = records(send_probe.dump_mem(str(IMAGE), TMP / f"{tag}.mem", tag))
            track = 4 if tag == "A" else 0
            for h in mod.dsp.hooks:
                if not h.on(tag):
                    continue
                name = next((n for n in STUBS if n.startswith(f"hook stub {key} {h.label} ") and tag in n.rsplit(" ", 1)[1]), None)
                check(f"{key} {h.label}, payload {tag}: the build placed a stub", name is not None)
                if name is None:
                    continue
                stub, sw = STUBS[name]
                # the body's address, read back from the stub's own branch: a plain stub's beq is its third
                # instruction (P:stub+4, the displacement at +5); a bridge's bsr its fourth (+6), its bra the fifth (+8)
                bridged = len(sw) == 10
                body = (stub + 4 + sw[5]) & 0xFFFFFF
                if bridged:
                    body = (stub + 6 + sw[7]) & 0xFFFFFF
                    chain = (stub + 8 + sw[9]) & 0xFFFFFF
                    unbound_ref = [("bsr", chain)]
                    bound_ref = [("bsr", body), ("bsr", chain)]
                else:
                    unbound_ref = [("text", displaced(tuple(h.stock_on(tag))))]
                    bound_ref = [("bsr", body)]
                site = h.site_on(tag)
                what = f"{key} {h.label}, payload {tag} (P:0x{site:05x}, stub P:0x{stub:05x}{', bridged' if bridged else ''})"
                runs = {}
                for state, word in (("clear", 0), ("wrong", MAGIC ^ 1), ("set", MAGIC)):
                    runs[state] = run(base, block + [(1, ENTRY + 8 * k, [word])], wrapper(track, [("bsr", stub)]),
                                      f"{h.label}{tag}{state}")
                # each reference runs with the same BOUND word as the run it is compared with
                ref = {state: run(base, block + [(1, ENTRY + 8 * k, [word])],
                                  wrapper(track, bound_ref if state == "set" else unbound_ref), f"{h.label}{tag}ref{state}")
                       for state, word in (("clear", 0), ("wrong", MAGIC ^ 1), ("set", MAGIC))}
                for state in ("clear", "wrong"):
                    ok, d = same(runs[state], ref[state], bridged)
                    check(f"{what}: BOUND {state}: equals {'the bridged entry' if bridged else 'the displaced instruction'} alone", ok, d)
                ok, d = same(runs["set"], ref["set"], bridged)
                check(f"{what}: BOUND set: equals the body{' then the bridged entry' if bridged else ''}", ok, d)
                check(f"{what}: BOUND set differs from clear (the body ran)", not same(runs["set"], runs["clear"], bridged)[0])
    print("PASS" if not fails else f"{fails} FAIL")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
