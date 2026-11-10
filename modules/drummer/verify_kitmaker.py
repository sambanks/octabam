#!/usr/bin/env python3
"""DRUMMER's kit maker (kitmaker.py): its three files, then the firmware taking its .drk.

    .venv/bin/python3 modules/drummer/verify_kitmaker.py [--image out/mainos_bus.bin] [--no-port]

One-shots synthesized here (no third-party sound): kicks, snares, a clap, hats, an open hat, a tom, a
cowbell; one in a KICK/ sub-folder under a name that says nothing, one 48 kHz 24-bit, one stereo, one
named "thing" (AUTO decides it). kitmaker writes KITTEST.wav/.ot/.drk under out/drummer/kitmaker/.

Host checks:
  the WAV: 44.1 kHz, 24 bit (an input is), stereo (an input is), its frames = the last slice's end;
  the .ot: 832 bytes, FORM DPS1SMPA, version 2, its checksum (the 16-bit sum of bytes 20..829, what
           the firmware's reader 0x4008b8d0 compares), one slice per sound end to end, trim = the file;
  the .drk: DRKT version 1, 468 bytes, its CRC-32; n = the slice count, sig = the CRC-32 of the .ot's
           slice table; the zones the folder and names say, AUTO's for "thing"; roles ACCENT/SOFT from
           the words, the rest by level; GAIN 0, no links.
One WAV holding every sound: a chain with silences between (--names bd,sd,hh,oh,tom and one left to
AUTO), a 48 kHz chain with cue points, KITTEST.wav with its .ot (kept byte for byte), --grid 8.
Port (verify_port.py's project builder; FLEX slot 1 = KITTEST.wav, its slices in the project as the
.ot has them, KITTEST.drk beside it in AUDIO; T1 a DRUMMER track with no drummer.work): T1 shown ->
the kit from the file (dr_kit_ready 1, every zone and role the file's), no box asked. Then (image 70)
Part 1 on KITTEST, Part 2 on CHAIN (slot 2): a Part change loads CHAIN.drk and puts KITTEST's kit
aside; back to Part 1 its kit returns as it was left (an edit kept); with no CHAIN.drk the kit stays and
nothing is asked. The Part change is the Part index poked (what DRUMMER reads), not the panel's.
"""
import argparse, pathlib, shutil, struct, subprocess, sys, wave, zlib

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402
import kitmaker as K  # noqa: E402
import probe_slices as ps  # noqa: E402

OUT = ROOT / "out/drummer/kitmaker"
DIALOG_OPEN = 0x460E5CD0
FAILS = []


def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" -- {detail}" if detail else ""))
    if not ok:
        FAILS.append(name)


def symbol(name):
    for line in (ROOT / "out/platform/runtime/runtime.map").read_text().splitlines():
        w = line.split()
        if len(w) == 2 and w[1] == name and w[0].startswith("0x"):
            return int(w[0], 16)
    sys.exit(f"verify_kitmaker: {name} not in the runtime map")


def synth(kind, rate=44100, amp=0.8, seed=1):
    rng = np.random.default_rng(seed)
    n = int(rate * {"kick": 0.45, "snare": 0.3, "clap": 0.25, "hat": 0.08, "ohat": 0.5, "tom": 0.4,
                    "bell": 0.3}[kind])
    t = np.arange(n) / rate
    lead = np.zeros(int(rate * 0.004))                     # 4 ms of silence the trim takes off
    if kind == "kick":
        f = 48 + 70 * np.exp(-t * 40)
        x = np.sin(2 * np.pi * np.cumsum(f) / rate) * np.exp(-t * 7)
    elif kind == "tom":
        f = 110 + 60 * np.exp(-t * 20)
        x = np.sin(2 * np.pi * np.cumsum(f) / rate) * np.exp(-t * 9)
    elif kind in ("snare", "clap"):
        x = 0.35 * np.sin(2 * np.pi * 190 * t) * np.exp(-t * 25) + rng.uniform(-1, 1, n) * np.exp(-t * 18)
        x = np.concatenate([[0], np.diff(x)]) * 2.5         # brighter: the noise's highs
    elif kind in ("hat", "ohat"):
        x = np.diff(np.diff(rng.uniform(-1, 1, n + 2))) / 4 * np.exp(-t * (60 if kind == "hat" else 5))
    else:
        x = (np.sign(np.sin(2 * np.pi * 540 * t)) + np.sign(np.sin(2 * np.pi * 800 * t))) * 0.5 * np.exp(-t * 12)
    x = np.concatenate([lead, x])
    return (x / np.abs(x).max() * amp).astype(np.float32)


def write(path, x, rate=44100, bits=16, stereo=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    y = np.stack([x, x * 0.7], 1) if stereo else x[:, None]
    full = 2 ** (bits - 1)
    q = np.clip(np.round(y * full), -full, full - 1).astype(np.int32)
    data = q.astype("<i2").tobytes() if bits == 16 else q.astype("<i4").view(np.uint8).reshape(-1, 4)[:, :3].tobytes()
    with wave.open(str(path), "wb") as w:
        w.setnchannels(y.shape[1])
        w.setsampwidth(bits // 8)
        w.setframerate(rate)
        w.writeframes(data)


# the folder: path -> (sound, zone wanted, role wanted or None (by level))
SOUNDS = {
    "KICK/one.wav": ("kick", 0.9, "KICK", None),
    "BD_02 soft.wav": ("kick", 0.25, "KICK", "SOFT"),
    "kick-03.wav": ("kick", 0.6, "KICK", None),
    "Snare Accent.wav": ("snare", 0.9, "SNARE", "ACCENT"),
    "sd_ghost_1.wav": ("snare", 0.2, "GHOST", None),
    "Clap.wav": ("clap", 0.7, "SNARE", None),
    "hh_closed.wav": ("hat", 0.6, "HATC", None),
    "OpenHat.wav": ("ohat", 0.6, "HATO", None),
    "LowTom.wav": ("tom", 0.7, "TOM", None),
    "cowbell.wav": ("bell", 0.6, "PERC", None),
    "thing.wav": ("kick", 0.8, None, None),
}


def kit_of(path):
    d = path.read_bytes()[16:]
    return d[0], list(d[8:8 + d[0]]), struct.unpack(">I", d[4:8])[0]


def one_wav(src):
    """One WAV holding every sound: cut at silences (with --names), cue points (at 48 kHz), the unit's .ot
    kept, --grid."""
    order = ["kick", "snare", "hat", "ohat", "tom", "kick"]
    rng_gap = np.zeros(int(44100 * 0.12), np.float32)
    parts, starts, at = [], [], 0
    for i, k in enumerate(order):
        x = synth(k, seed=50 + i)
        starts.append(at)
        parts += [x, rng_gap]
        at += len(x) + len(rng_gap)
    chain = np.concatenate(parts)
    one = OUT / "one"
    write(one / "chain.wav", chain)
    r = subprocess.run([sys.executable, str(HERE / "kitmaker.py"), str(one / "chain.wav"), str(one / "CHAIN"),
                        "--names", "bd,sd,hh,oh,tom,"], capture_output=True, text=True)
    print(r.stdout.rstrip())
    ok = r.returncode == 0 and (one / "CHAIN.ot").is_file()
    check("one WAV, cut at silences: kitmaker ran", ok, r.stderr[-300:])
    if not ok:
        return
    ot = (one / "CHAIN.ot").read_bytes()
    n, = struct.unpack(">I", ot[0x33A:0x33E])
    sl = [struct.unpack(">II", ot[0x3A + 12 * i:0x42 + 12 * i]) for i in range(n)]
    # each start 1 ms before the sound's first loud frame (its 4 ms lead of silence then the hit)
    near = n == 6 and all(abs(sl[i][0] - (starts[i] + 176 - 44)) <= 3 for i in range(6)) \
        and sl[-1][1] == len(chain) and all(sl[i][1] == sl[i + 1][0] for i in range(5))
    check("one WAV, cut at silences: 6 slices at the sounds' starts, end to end", near,
          f"{[s0 for s0, _ in sl]} want ~{[st + 132 for st in starts]}")
    dn, zones, sig = kit_of(one / "CHAIN.drk")
    check("--names gives the zones (bd sd hh oh tom), the 6th (no name) AUTO's: a kick",
          zones == [0, 1, 3, 4, 7, 0] and sig == zlib.crc32(ot[0x3A:0x3A + 12 * n]), f"{zones}")

    # cue points, the file at 48 kHz: positions scaled to 44.1
    c48 = np.concatenate([synth(k, 48000, seed=60 + i) for i, k in enumerate(("kick", "snare", "hat"))])
    lens = [len(synth(k, 48000, seed=60 + i)) for i, k in enumerate(("kick", "snare", "hat"))]
    write(one / "cued.wav", c48, 48000, 24)
    raw = bytearray((one / "cued.wav").read_bytes())
    cues = [0, lens[0], lens[0] + lens[1]]
    body = struct.pack("<I", 3) + b"".join(struct.pack("<II4sIII", i + 1, c, b"data", 0, 0, c) for i, c in enumerate(cues))
    raw += b"cue " + struct.pack("<I", len(body)) + body
    raw[4:8] = struct.pack("<I", len(raw) - 8)
    (one / "cued.wav").write_bytes(bytes(raw))
    r = subprocess.run([sys.executable, str(HERE / "kitmaker.py"), str(one / "cued.wav"), str(one / "CUED")],
                       capture_output=True, text=True)
    ok = r.returncode == 0 and (one / "CUED.ot").is_file()
    check("one WAV, cue points: kitmaker ran", ok, (r.stdout + r.stderr)[-300:])
    if ok:
        ot = (one / "CUED.ot").read_bytes()
        n, = struct.unpack(">I", ot[0x33A:0x33E])
        sl = [struct.unpack(">II", ot[0x3A + 12 * i:0x42 + 12 * i]) for i in range(n)]
        want = [round(c * 44100 / 48000) for c in cues]
        check("one WAV, cue points at 48 kHz: 3 slices at the cues x 44.1/48", n == 3 and [s0 for s0, _ in sl] == want,
              f"{[s0 for s0, _ in sl]} want {want}")
        dn, zones, _ = kit_of(one / "CUED.drk")
        check("no names: AUTO's zones (kick, snare, hat)", zones[0] == 0 and zones[2] in (3, 4), f"{zones}")

    # the unit's own .ot beside: kept, byte for byte
    kt = OUT / "KITTEST"
    r = subprocess.run([sys.executable, str(HERE / "kitmaker.py"), str(kt.with_suffix(".wav")), str(one / "KEPT")],
                       capture_output=True, text=True)
    ok = r.returncode == 0 and (one / "KEPT.drk").is_file()
    check("one WAV with its .ot: kitmaker ran", ok, (r.stdout + r.stderr)[-300:])
    if ok:
        same = (one / "KEPT.wav").read_bytes() == kt.with_suffix(".wav").read_bytes() \
            and (one / "KEPT.ot").read_bytes() == kt.with_suffix(".ot").read_bytes()
        _, _, s1 = kit_of(one / "KEPT.drk")
        _, _, s0 = kit_of(kt.with_suffix(".drk"))
        check("one WAV with its .ot: the WAV and the .ot copied as they are, the .drk's slices theirs",
              same and s1 == s0, f"same {same} sig {s1:#x} / {s0:#x}")

    r = subprocess.run([sys.executable, str(HERE / "kitmaker.py"), str(one / "chain.wav"), str(one / "GRID"),
                        "--grid", "8"], capture_output=True, text=True)
    ok = r.returncode == 0
    if ok:
        ot = (one / "GRID.ot").read_bytes()
        n, = struct.unpack(">I", ot[0x33A:0x33E])
        sl = [struct.unpack(">II", ot[0x3A + 12 * i:0x42 + 12 * i]) for i in range(n)]
        ok = n == 8 and sl[1][0] == len(chain) // 8 and sl[7][1] == len(chain)
    check("--grid 8: 8 equal slices", ok, (r.stdout + r.stderr)[-200:] if not ok else "")


PART_IDX = 0x100B14CF


def add_slot2(proj, wav_rel, frames, slices):
    """FLEX slot 2 = wav_rel with its slices (project.work's [SAMPLE] block, markers' record 2)."""
    import re
    block = ("[SAMPLE]\r\nTYPE=FLEX\r\nSLOT=002\r\nPATH=../" + wav_rel + "\r\n"
             "TRIM_BARSx100=200\r\nLOOP_BARSx100=200\r\nBPMx24=2880\r\n"
             "TSMODE=0\r\nLOOPMODE=0\r\nGAIN=48\r\nTRIGQUANTIZATION=-1\r\n[/SAMPLE]\r\n\r\n").encode()
    for suffix in ("work", "strd"):
        pw = proj / f"project.{suffix}"
        if pw.is_file():
            raw = pw.read_bytes()
            at = raw.find(b"[SAMPLE]")
            pw.write_bytes(raw[:at] + block + raw[at:])
        pm = proj / f"markers.{suffix}"
        if pm.is_file():
            rec = struct.pack(">III", 0, frames, 0xFFFFFFFF)
            rec += b"".join(struct.pack(">III", *sl) for sl in slices) + struct.pack(">I", sum(1 for sl in slices if sl[1]))
            data = bytearray(pm.read_bytes())
            data[0x16 + 784:0x16 + 784 + 784] = rec
            data[-2:] = (sum(data[0x10:-2]) & 0xFFFF).to_bytes(2, "big")
            pm.write_bytes(bytes(data))


def part_case(a, ot_a, drk_a):
    """Part 1 plays KITTEST (slot 1), Part 2 CHAIN (slot 2), each with its .drk; T1 a DRUMMER track, no
    drummer.work. The Part index poked as a Part change does it (DRUMMER reads 0x100b14cf)."""
    one = OUT / "one"
    ot_b, drk_b = (one / "CHAIN.ot").read_bytes(), (one / "CHAIN.drk").read_bytes()
    nb, = struct.unpack(">I", ot_b[0x33A:0x33E])
    sl_b = [struct.unpack(">III", ot_b[0x3A + 12 * i:0x46 + 12 * i]) for i in range(64)]
    with wave.open(str(one / "CHAIN.wav")) as w:
        frames_b = w.getnframes()
    na, = struct.unpack(">I", ot_a[0x33A:0x33E])
    sl_a = [struct.unpack(">III", ot_a[0x3A + 12 * i:0x46 + 12 * i]) for i in range(64)]
    with wave.open(str(OUT / "KITTEST.wav")) as w:
        frames_a = w.getnframes()
    zones_a, zones_b = drk_a[16 + 8:16 + 72], drk_b[16 + 8:16 + 72]
    kit, ready, aside, kslot, seen = (symbol(n) for n in ("dr_kit", "dr_kit_ready", "dr_aside", "dr_kit_slot",
                                                          "dr_slot_seen"))
    jcase = symbol("dr_drk_case")
    results, jobs = {}, {}
    for case, with_b in (("part", True), ("back", True), ("nofile", False), ("setup", True)):
        out = OUT / case
        proj = out / "project"
        if out.exists():
            shutil.rmtree(out)
        ps.build_project(pathlib.Path(a.project), proj, frames_a, sl_a, na, 240)
        add_slot2(proj, "AUDIO/KIT_B.wav", frames_b, sl_b)

        def mut(data):
            for p in range(ps.otp.NPARTS_ALL):
                part = ps.otp.PART_BASE + p * ps.otp.PART_STRIDE
                data[part + 9 + 60:part + 9 + 63] = b"DR\x01"
                data[part + 0x2d3 + 1] = 1 if p % 4 == 1 else 0         # Part 2: slot 2
        ps.otp._bank_write(proj, 1, mut, guard=False)
        audio = ["--audio", f"{OUT / 'KITTEST.wav'}:{ps.SAMPLE_REL}",
                 "--audio", f"{OUT / 'KITTEST.drk'}:{ps.SAMPLE_REL[:-4]}.drk",
                 "--audio", f"{one / 'CHAIN.wav'}:AUDIO/KIT_B.wav"]
        if with_b:
            audio += ["--audio", f"{one / 'CHAIN.drk'}:AUDIO/KIT_B.drk"]
        card = out / "card.img"
        r = subprocess.run([str(ps.PY), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(proj), "OCTABAM", "RIG",
                            "--tree", str(out / "tree"), "--out", str(card), *audio], cwd=ROOT, capture_output=True, text=True)
        if r.returncode:
            check(f"{case}: card staged", False, (r.stdout + r.stderr)[-300:])
            continue
        ev = ["1500 key 0x10 down", "1540 key 0x10 up", f"4000 poke {PART_IDX:#x}=1"]
        if case == "back":                       # an edit on Part 1's kit first: slice 1 PERC, kept aside
            ev = ["1500 key 0x10 down", "1540 key 0x10 up", f"3500 poke {kit:#x}=8", f"4000 poke {PART_IDX:#x}=1",
                  f"7000 poke {PART_IDX:#x}=0"]
        if case == "setup":                      # Part 2's sample picked in SETUP (its window closed): asked, its
            ev = ["1500 key 0x10 down", "1540 key 0x10 up", f"3500 poke {kit:#x}=8",   # .drk found, applied
                  f"4000 poke {seen:#x}=0;{PART_IDX:#x}=1"]
        (out / "run.script").write_text("\n".join(ev + ["10000 quit"]) + "\n")
        dump = (f"{kit:#x},268={out}/kit.bin;{ready:#x},8={out}/ready.bin;{aside:#x},468={out}/aside.bin;"
                f"{kslot:#x},8={out}/kslot.bin;{jcase:#x},1={out}/jcase.bin")
        cmd = [str(ps.EMU), "--image", a.image, "--card", str(card), "--set", "OCTABAM", "--project", "RIG", "--mkii",
               "--load-ms", "90000", "--live-script", str(out / "run.script"), "--mem-dump", dump]
        with open(out / "port.txt", "w") as f:
            rc = subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT).returncode
        rd = lambda n: (out / f"{n}.bin").read_bytes() if (out / f"{n}.bin").is_file() else b""
        results[case] = (rc, rd("kit"), rd("ready"), rd("aside"), rd("kslot"))
        jobs[case] = rd("jcase")[:1].hex()
    za_edit = bytes([8]) + zones_a[1:]
    rc, k, rd_, asd, ks = results.get("part", (1, b"", b"", b"", b""))
    check("Part change to a sample with a .drk: its kit loaded (T1's kit = CHAIN.drk's, slot 2), "
          "KITTEST's put aside (slot 1)", rc == 0 and k[:64] == zones_b and ks[:1] == b"\1" and asd[:1] == b"\0"
          and asd[4:68] == zones_a, f"exit {rc} kit {list(k[:nb])} slot {ks[:1].hex()} aside slot {asd[:1].hex()}")
    rc, k, rd_, asd, ks = results.get("back", (1, b"", b"", b"", b""))
    check("and back to Part 1: its kit as it was left (slice 1 edited PERC, not the file's), CHAIN's aside",
          rc == 0 and k[:64] == za_edit and ks[:1] == b"\0" and asd[:1] == b"\1" and asd[4:68] == zones_b,
          f"exit {rc} kit {list(k[:na])} slot {ks[:1].hex()} aside slot {asd[:1].hex()}")
    rc, k, rd_, asd, ks = results.get("nofile", (1, b"", b"", b"", b""))
    check("Part change to a sample with no .drk: the kit stays (KITTEST's), nothing asked (ready 1)",
          rc == 0 and k[:64] == zones_a and rd_[:1] == b"\1", f"exit {rc} kit {list(k[:na])} ready {rd_[:1].hex()}")
    rc, k, rd_, asd, ks = results.get("setup", (1, b"", b"", b"", b""))
    check("Part 2's sample picked in SETUP (the new-sample job, case 2, its .drk taken): Part 1's kit put aside "
          "as it was left (slice 1 edited, slot 1), so Part 1 gets it back", rc == 0 and jobs.get("setup") == "02"
          and k[:64] == zones_b and ks[:1] == b"\1" and asd[:1] == b"\0" and asd[4:68] == za_edit,
          f"exit {rc} job {jobs.get('setup')} kit {list(k[:nb])} slot {ks[:1].hex()} aside slot {asd[:1].hex()} "
          f"aside {list(asd[4:4 + na])}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--image", default=str(ROOT / "out/mainos_bus.bin"))
    ap.add_argument("--project", default=str(ROOT / "out/drummer/slices/fresh/image/NOPROJ"))
    ap.add_argument("--no-port", action="store_true")
    a = ap.parse_args()
    if OUT.exists():
        shutil.rmtree(OUT)
    src = OUT / "sounds"
    for i, (rel, (kind, amp, _, _)) in enumerate(SOUNDS.items()):
        rate, bits = (48000, 24) if rel == "Clap.wav" else (44100, 16)
        write(src / rel, synth(kind, rate, amp, seed=i + 1), rate, bits, stereo=rel == "OpenHat.wav")
    r = subprocess.run([sys.executable, str(HERE / "kitmaker.py"), str(src), str(OUT / "KITTEST")],
                       capture_output=True, text=True)
    print(r.stdout.rstrip())
    check("kitmaker ran", r.returncode == 0, r.stderr[-400:])
    if FAILS:
        return 1

    with wave.open(str(OUT / "KITTEST.wav")) as w:
        rate, bits, ch, frames = w.getframerate(), 8 * w.getsampwidth(), w.getnchannels(), w.getnframes()
    ot = (OUT / "KITTEST.ot").read_bytes()
    drk = (OUT / "KITTEST.drk").read_bytes()
    n, = struct.unpack(">I", ot[0x33A:0x33E])
    sl = [struct.unpack(">III", ot[0x3A + 12 * i:0x46 + 12 * i]) for i in range(64)]
    check("WAV: 44.1 kHz, 24 bit, stereo", (rate, bits, ch) == (44100, 24, 2), f"{rate} {bits} {ch}")
    check(".ot: 832 bytes, FORM DPS1SMPA, version 2, its checksum",
          len(ot) == 832 and ot[:16] == b"FORM\0\0\0\0DPS1SMPA" and ot[20:22] == b"\0\2"
          and struct.unpack(">H", ot[830:])[0] == sum(ot[20:830]) & 0xFFFF)
    trim = struct.unpack(">II", ot[46:54])
    ends = n == len(SOUNDS) and sl[0][0] == 0 and all(sl[i][1] == sl[i + 1][0] for i in range(n - 1)) \
        and sl[n - 1][1] == frames and trim == (0, frames) and all(s == (0, 0, 0) for s in sl[n:])
    check(".ot: one slice per sound, end to end, trim = the file", ends, f"n {n} last {sl[n - 1]} frames {frames}")
    magic, ver, size, crc = struct.unpack(">4I", drk[:16])
    body = drk[16:]
    check(".drk: DRKT version 1, 468 bytes, its CRC-32",
          (magic, ver, size, len(body)) == (0x44524B54, 1, 468, 468) and zlib.crc32(body) == crc)
    dn, sig = body[0], struct.unpack(">I", body[4:8])[0]
    check(".drk: the slices it fits = the .ot's (count, CRC-32 of the table)",
          dn == n and sig == zlib.crc32(ot[0x3A:0x3A + 12 * n]), f"n {dn} sig {sig:#x}")

    lines = [ln for ln in r.stdout.splitlines() if ln[:4].strip().isdigit()]
    by_sound = {ln.split(None, 6)[-1]: int(ln.split()[0]) - 1 for ln in lines}
    zones, roles = body[8:72], body[72:136]
    bad = []
    for rel, (_, _, zw, rw) in SOUNDS.items():
        i = by_sound.get(rel)
        if i is None:
            bad.append(f"{rel} missing")
            continue
        if zw and E.ZONES[zones[i]] != zw:
            bad.append(f"{rel} zone {E.ZONES[zones[i]] if zones[i] < 9 else zones[i]} not {zw}")
        if rw and E.ROLES[roles[i]] != rw:
            bad.append(f"{rel} role {E.ROLES[roles[i]]} not {rw}")
    check("zones from the folder and the names, roles from the words", not bad, "; ".join(bad))
    thing = by_sound.get("thing.wav")
    check("AUTO decides the unnamed one (a kick, autokit.c's rule)", thing is not None and zones[thing] == 0,
          f"zone {zones[thing] if thing is not None else '?'}")
    check("the rest of the kit: OUT past the sounds, GAIN 0, no links, SIMILAR 6 OUT",
          all(z == 15 for z in zones[n:]) and not any(body[340:468]) and body[1:3] == bytes((6, 0)))
    kicks = [roles[by_sound[r]] for r in ("KICK/one.wav", "kick-03.wav", "thing.wav")]
    check("roles by level in a zone: the loudest kick ACCENT (one.wav, 0.9)", kicks[0] == 0, f"{kicks}")
    order = [zones[i] for i in range(n)]
    check("--order zone: KICK slices first, then SNARE ..", order == sorted(order), f"{order}")

    one_wav(src)
    if a.no_port:
        print("PASS: DRUMMER kit maker (host)" if not FAILS else f"FAIL: DRUMMER kit maker ({len(FAILS)})")
        return 1 if FAILS else 0

    # ---- the firmware takes the .drk ----
    proj = OUT / "project"
    ps.build_project(pathlib.Path(a.project), proj, frames, [s for s in sl[:n]] + [(0, 0, 0)] * (64 - n), n, 240)

    def mut(data):
        for p in range(ps.otp.NPARTS_ALL):
            part = ps.otp.PART_BASE + p * ps.otp.PART_STRIDE
            data[part + 9 + 60:part + 9 + 63] = b"DR\x01"            # T1 a DRUMMER track
        off = ps.otp.trac_off(0, 0)
        data[off:off + 64] = bytes(64)
        data[off + 0x59:off + 0x59 + 64 * 32] = bytes([0xff]) * (64 * 32)
    ps.otp._bank_write(proj, 1, mut, guard=False)
    card = OUT / "card.img"
    r = subprocess.run([str(ps.PY), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(proj), "OCTABAM", "RIG",
                        "--tree", str(OUT / "tree"), "--out", str(card),
                        "--audio", f"{OUT / 'KITTEST.wav'}:{ps.SAMPLE_REL}",
                        "--audio", f"{OUT / 'KITTEST.drk'}:{ps.SAMPLE_REL[:-4]}.drk"],
                       cwd=ROOT, capture_output=True, text=True)
    check("card staged (KITTEST.wav as AUDIO/DRUMMER_TEST.wav, its .drk beside it)", r.returncode == 0,
          (r.stdout + r.stderr)[-400:])
    if FAILS:
        return 1
    kit, ready = symbol("dr_kit"), symbol("dr_kit_ready")
    (OUT / "load.script").write_text("1500 key 0x10 down\n1540 key 0x10 up\n8000 quit\n")
    dump = (f"{kit:#x},268={OUT}/kit.bin;{ready:#x},8={OUT}/ready.bin;{DIALOG_OPEN:#x},4={OUT}/dialog.bin;"
            f"{0x100B14F0 + 312:#x},{12 * n}={OUT}/slices.bin")
    cmd = [str(ps.EMU), "--image", a.image, "--card", str(card), "--set", "OCTABAM", "--project", "RIG", "--mkii",
           "--load-ms", "90000", "--live-script", str(OUT / "load.script"), "--lcd", str(OUT / "load.lcd"),
           "--mem-dump", dump]
    with open(OUT / "port.txt", "w") as f:
        rc = subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT).returncode
    subprocess.run([str(ps.PY), str(ROOT / "tools/emu/lcd_view.py"), str(OUT / "load.lcd"), "--png",
                    str(OUT / "load.png")], cwd=ROOT, capture_output=True)
    rd = lambda s: (OUT / f"{s}.bin").read_bytes() if (OUT / f"{s}.bin").is_file() else b""
    k, rdy, dlg, ram = rd("kit"), rd("ready"), rd("dialog"), rd("slices")
    check("port run", rc == 0 and len(k) == 268, f"exit {rc}, {OUT / 'port.txt'}")
    if not FAILS:
        check("RAM's slice bounds = the .ot's (what drk_sig hashes)", ram == ot[0x3A:0x3A + 12 * n])
        check("T1 shown: the kit from the file, no box (ready 1, zones and roles the file's, DIALOG_OPEN 0)",
              rdy[:1] == b"\1" and k[:64] == zones and k[64:128] == roles and dlg == b"\0\0\0\0",
              f"ready {rdy[:1].hex()} zones {list(k[:n])} (file {list(zones[:n])}) dialog {dlg.hex()}")
    part_case(a, ot, drk)
    print("PASS: DRUMMER kit maker" if not FAILS else f"FAIL: DRUMMER kit maker ({len(FAILS)})")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
