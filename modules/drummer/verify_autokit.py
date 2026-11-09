#!/usr/bin/env python3
"""DRUMMER's AUTO kit on the host: autokit.c on a sliced sample (NAME.wav + NAME.ot).

    .venv/bin/python3 modules/drummer/verify_autokit.py --sample DIR/NAME.wav [--expect user-loop]

Prints each slice's features and the kit AUTO makes. With --expect user-loop (the user's 93 BPM 16-slice
loop), checks the zones the hand analysis of phase 3 found (1-based: kicks 1 6 9 14, snares 3 7 11 15,
hats 5 13), an ACCENT and a SOFT in every zone of three slices or more, and ALIGN ~160 ms on slices 2
and 10 (a kick 160 ms into each); then SIMILAR at its default tolerance 6: OUT keeps slices 3 4 5 8 9 10 15 16
(8 copies: the second bar repeats the first), LINK links the same 8 and puts none OUT, the repeats
6/14 7/15 4/12 3/11 5/13 in one group each. The sample stays on the user's disk.
"""
import argparse, ctypes, pathlib, shutil, struct, subprocess, sys, tempfile, wave

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402


class Features(ctypes.Structure):
    _fields_ = [(n, ctypes.c_uint32) for n in ("peak", "low_pct", "high_pct", "onset_ms", "hold_pct", "level")] + [
        ("band", ctypes.c_uint16 * 4), ("env", ctypes.c_uint8 * 8), ("decay_ms", ctypes.c_uint32)]


READ = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32)


def lib():
    cc = shutil.which("cc") or shutil.which("gcc")
    out = pathlib.Path(tempfile.mkdtemp(prefix="autokit_")) / "libak.so"
    subprocess.run([cc, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror", "-shared", "-fPIC",
                    str(HERE / "autokit.c"), str(HERE / "drummer.c"), "-o", str(out)], check=True)
    return ctypes.CDLL(str(out))


def port(a, kit, align, count, link):
    """The firmware's AUTO on the same sample: verify_port.py's groove project without drummer.work (T1 a
    DRUMMER track, no kit), T1's SIMILAR set to --tol / --mode (poked), T1 pressed on the panel, YES to the KIT
    question; T1's kit and SIMILAR groups dumped and compared, every GAIN (poked to -5 dB) back to 0 and
    every ALIGN (poked to 40 ms) back to AUTO's. With --mode link, the KIT is then opened on
    the first linked slice (TRIG + BANK), page 2, B -2: its whole group's GAIN at -2 dB, the others 0."""
    import shutil as sh
    root = HERE.parents[1]
    out = root / "out/drummer/autokit"
    proj = out / "project"
    if proj.exists():
        sh.rmtree(proj)
    sh.copytree(root / "out/drummer/port/groove/project", proj)
    for name in ("drummer.work", "drummer.strd"):
        (proj / name).unlink(missing_ok=True)
    card = out / "card.img"
    wav = pathlib.Path(a.sample).expanduser().resolve()
    r = subprocess.run([str(root / ".venv/bin/python3"), str(root / "tools/emu/ot_emu/stage_card.py"), str(proj),
                        "OCTABAM", "RIG", "--tree", str(out / "tree"), "--out", str(card),
                        "--audio", f"{wav}:AUDIO/DRUMMER_TEST.wav"], cwd=root, capture_output=True, text=True)
    if r.returncode:
        print("  [FAIL] stage_card", r.stderr[-400:])
        return 1
    syms = {}
    for line in (root / "out/platform/runtime/runtime.map").read_text().splitlines():
        w = line.split()
        if len(w) == 2 and w[0].startswith("0x"):
            syms[w[1]] = int(w[0], 16)
    events = [(1500, "key 0x10 down"), (1540, "key 0x10 up"), (4000, "key 0x31 down"), (4040, "key 0x31 up")]
    first = next((i for i in range(count) if link[i]), None)
    if a.mode == "link" and first is not None:
        events += [(6000, f"key {first:#x} down"), (6100, "key 0x2f down"), (6200, "key 0x2f up"),
                   (6500, f"key {first:#x} up"), (7000, "key 0x21 down"), (7040, "key 0x21 up"),
                   (7500, "enc 1 -1"), (7800, "enc 1 -1")]
    events += [(10000, "quit")]
    (out / "auto.script").write_text("".join(f"{t} {e}\n" for t, e in events))
    dump = (f"{syms['dr_kit']:#x},268={out}/kit.bin;{syms['dr_align']:#x},64={out}/align.bin;"
            f"{syms['dr_kit_ready']:#x},8={out}/ready.bin;{syms['dr_link']:#x},64={out}/link.bin;"
            f"{syms['dr_gain']:#x},64={out}/gain.bin")
    poke = (f"{syms['dr_simtol']:#x}={a.tol};{syms['dr_simmode']:#x}={int(a.mode == 'link')};"
            + ";".join(f"{syms['dr_gain'] + i:#x}=0xfb;{syms['dr_align'] + i:#x}=40" for i in range(count)))
    # GAIN -5 dB and ALIGN 40 ms by hand before: AUTO puts GAIN 0 and its own ALIGN (0, or the hit found) back
    cmd = [str(root / "out/emu/ot_emu"), "--image", a.image, "--card", str(card), "--set", "OCTABAM", "--project", "RIG",
           "--mkii", "--load-ms", "90000", "--main-level", "64", "--live-script", str(out / "auto.script"),
           "--lcd", str(out / "auto.lcd"), "--mem-dump", dump, "--poke", poke]
    with open(out / "port.txt", "w") as f:
        rc = subprocess.run(cmd, cwd=root, stdout=f, stderr=subprocess.STDOUT).returncode
    k = (out / "kit.bin").read_bytes() if (out / "kit.bin").is_file() else b""
    if rc or len(k) != 268:
        print(f"  [FAIL] port run (exit {rc}) -- {out / 'port.txt'}")
        return 1
    ready = (out / "ready.bin").read_bytes()[0]
    al = (out / "align.bin").read_bytes()
    zones_ok = list(k[:count]) == [kit.zone[i] for i in range(count)]
    roles_ok = list(k[64:64 + count]) == [kit.role[i] for i in range(count)]
    align_ok = list(al[:count]) == [align[i] for i in range(count)]
    lk = (out / "link.bin").read_bytes()
    link_ok = list(lk[:count]) == [link[i] for i in range(count)]
    ok = ready == 1 and zones_ok and roles_ok and align_ok and link_ok
    if a.mode != "link":                         # (link: the GAIN case below turns them after AUTO)
        g0 = (out / "gain.bin").read_bytes()[:count]
        zero = not any(g0)
        print(f"  [{'PASS' if zero else 'FAIL'}] AUTO puts every GAIN back to 0 dB (all -5 before): {list(g0)}")
        ok = ok and zero
    print(f"  [{'PASS' if ok else 'FAIL'}] the firmware's AUTO (YES to the question, SIMILAR {a.tol} {a.mode}) = the "
          f"host's: kit flag {ready}, zones {zones_ok}, roles {roles_ok}, ALIGN {align_ok}, groups {link_ok}")
    if a.mode == "link" and first is not None:
        g = [b - 256 if b > 127 else b for b in (out / "gain.bin").read_bytes()[:count]]
        want = [-2 if link[i] == link[first] else 0 for i in range(count)]
        gok = g == want
        print(f"  [{'PASS' if gok else 'FAIL'}] GAIN -2 on slice {first + 1} turns its group "
              f"{[i + 1 for i in range(count) if want[i]]}: {g}")
        ok = ok and gok
    if not ok:
        print("    unit zones", list(k[:count]), "roles", list(k[64:64 + count]), "align", list(al[:count]),
              "links", list(lk[:count]))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sample", required=True)
    ap.add_argument("--expect", choices=("user-loop",))
    ap.add_argument("--tol", type=int, default=0, help="SIMILAR's tolerance, 0 off (the KIT's default is 6)")
    ap.add_argument("--mode", choices=("out", "link"), default="out")
    ap.add_argument("--port", action="store_true", help="also run the firmware's AUTO under the port and compare")
    ap.add_argument("--image", default=str(HERE.parents[1] / "out/drummer/drummer_4e.bin"))
    a = ap.parse_args()
    wav = pathlib.Path(a.sample).expanduser().resolve()
    d = wav.with_suffix(".ot").read_bytes()
    count, = struct.unpack(">I", d[0x33a:0x33e])
    slices = [struct.unpack(">II", d[0x3a + 12 * i:0x42 + 12 * i]) for i in range(count)]
    with wave.open(str(wav)) as w:
        ch, raw = w.getnchannels(), w.readframes(w.getnframes())
    pcm = struct.unpack(f"<{len(raw) // 2}h", raw)
    mono = [(pcm[i] + pcm[i + 1]) // 2 for i in range(0, len(pcm), 2)] if ch == 2 else list(pcm)

    L = lib()
    read = READ(lambda ctx, frame: mono[frame] if frame < len(mono) else 0)
    feats = (Features * 64)()
    for i, (s, e) in enumerate(slices):
        L.ak_features(read, None, s, e, ctypes.byref(feats[i]))
    kit = E.Kit()
    L.dr_kit_init(ctypes.byref(kit), count)
    align = (ctypes.c_uint8 * 64)()
    link = (ctypes.c_uint8 * 64)()
    copies = L.ak_kit(feats, count, ctypes.byref(kit), align, a.tol, a.mode == "link", link)
    names = E.ZONES + ["COMBO"] + ["?"] * 5 + ["OUT"]
    print(" sl  peak level low% high% onset hold%   zone   role  align link")
    for i in range(count):
        f = feats[i]
        print(f" {i + 1:2d} {f.peak:5d} {f.level:5d} {f.low_pct:4d} {f.high_pct:5d} {f.onset_ms:5d} {f.hold_pct:5d}   "
              f"{names[kit.zone[i]]:6s} {E.ROLES[kit.role[i]]:6s} {align[i]:3d}  {('=' + str(link[i])) if link[i] else ''}")
    print(f"similar (tolerance {a.tol}, {a.mode}): {copies} copies")
    if a.expect == "user-loop":
        kit = E.Kit()                            # the hand analysis is of every slice: SIMILAR off
        L.dr_kit_init(ctypes.byref(kit), count)
        L.ak_kit(feats, count, ctypes.byref(kit), align, 0, 0, (ctypes.c_uint8 * 64)())
        want = {0: "KICK", 5: "KICK", 8: "KICK", 13: "KICK", 2: "SNARE", 6: "SNARE", 10: "SNARE", 14: "SNARE",
                4: "HATC", 12: "HATC"}
        bad = [i for i, z in want.items() if names[kit.zone[i]] != z]
        roles = all({0, 2} <= {kit.role[i] for i in range(count) if kit.zone[i] == z}
                    for z in range(9) if sum(kit.zone[i] == z for i in range(count)) >= 3)
        late = all(150 <= align[i] <= 170 for i in (1, 9))
        k2, al2, l2 = E.Kit(), (ctypes.c_uint8 * 64)(), (ctypes.c_uint8 * 64)()
        L.dr_kit_init(ctypes.byref(k2), count)
        out = L.ak_kit(feats, count, ctypes.byref(k2), al2, 6, 0, l2)
        kept = [i + 1 for i in range(count) if k2.zone[i] != E.OUT]
        L.dr_kit_init(ctypes.byref(k2), count)
        linked = L.ak_kit(feats, count, ctypes.byref(k2), al2, 6, 1, l2)
        pairs = all(l2[a - 1] and l2[a - 1] == l2[b - 1] for a, b in ((6, 14), (7, 15), (4, 12), (3, 11), (5, 13)))
        alive = all(k2.zone[i] != E.OUT for i in range(count))
        sim = out == 8 and kept == [3, 4, 5, 8, 9, 10, 15, 16] and linked == 8 and pairs and alive
        print(f"  [{'PASS' if sim else 'FAIL'}] SIMILAR at 6: OUT keeps {kept} ({out} copies); LINK links {linked}, "
              f"the bar's repeats together {pairs}, none OUT {alive}")
        ok = not bad and roles and late and sim
        print(f"{'PASS' if ok else 'FAIL'}: AUTO kit on the user's loop"
              + (f" -- slices {[b + 1 for b in bad]} differ" if bad else "")
              + ("" if roles else " -- a zone of 3+ slices lacks an ACCENT or a SOFT")
              + ("" if late else " -- slices 2 and 10 (a kick at 160 ms) are not aligned ~160 ms"))
        if not ok:
            return 1
    if a.port:
        kit = E.Kit()
        L.dr_kit_init(ctypes.byref(kit), count)
        L.ak_kit(feats, count, ctypes.byref(kit), align, a.tol, a.mode == "link", link)
        return port(a, kit, align, count, link)
    return 0


if __name__ == "__main__":
    sys.exit(main())
