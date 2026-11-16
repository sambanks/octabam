#!/usr/bin/env python3
"""LAZY CHOP stress under the ColdFire port: seeded random use across slots, tracks, Parts/Kits,
pattern changes (direct jump too), the sequencer, ZERO SNAP, audition, undo, YES/NO/leave.

    python3 tools/verify/stress_lazy_chop.py SEED [--cycles N] [--wall SECONDS]

Reads out/mainos_bus.bin and its runtime map (`make bus REMIX=...` with LAZY CHOP first).
Writes one JSON line per cycle to out/lazy_chop_stress/SEED.jsonl, then a summary line.
Not a module gate (minutes per run): run several seeds, and replay a failure by its seed.

Project (built once, cached in out/lazy_chop_stress/_project):
  six WAVs, every format the arena holds (16/24-bit, mono/stereo), 0.5-6 s, sums of
  incommensurate sines (no repeats), in FLEX slots 1 2 17 64 100 128 and STATIC 1 9 50 77 128;
  bank 1's four Parts map T1-T8 to different machines/slots (one THRU: LAZY CHOP must refuse);
  patterns 1-4 play Parts 1-4 with a trig on every track's step 1 (KITS migrates them).
After every cycle (the invariants):
  the port answers; with LAZY CHOP ended: lc_state 0, its playback range cleared (lc_tmod 0),
  the track's live SLIC and STRT as before the cycle;
  the slot records (trim + slice table, all 136 FLEX and 128 STATIC): after YES only the
  chopped slot may differ and its table is valid (count 1-64, chained, inside its trim, entry
  0 at the trim start); after NO, a leave or a refusal: none differs;
  ZERO SNAP's cost on sampled taps under the limit.
"""
from __future__ import annotations

import json
import math
import os
import pathlib
import random
import shutil
import struct
import subprocess
import sys
import time
import wave

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/verify")); sys.path.insert(0, str(ROOT / "tools/hw"))
import verify_lazy_chop as V        # noqa: E402
import ot_project as op             # noqa: E402

OUT = ROOT / "out/lazy_chop_stress"
FLEX0, STATIC0, REC = 0x100B14F0, 0x100D5B30, 1096
SNAP_TAP_LIMIT = V.SNAP_TAP_LIMIT

WAVS = {  # name: (channels, bits, seconds)
    "S16ST": (2, 16, 2.0), "S16MO": (1, 16, 1.5), "S24ST": (2, 24, 1.0),
    "S24MO": (1, 24, 3.0), "SHORT": (2, 16, 0.5), "LONG": (2, 16, 6.0),
}
FLEX_SLOTS = {1: "S16ST", 2: "S16MO", 17: "S24ST", 64: "S24MO", 100: "SHORT", 128: "LONG"}
STATIC_SLOTS = {1: "S16ST", 9: "S24ST", 50: "S24MO", 77: "S16MO", 128: "LONG"}
COMBOS = [("flex", 1), ("static", 1), ("flex", 2), ("static", 9), ("flex", 17), ("static", 50),
          ("flex", 64), ("static", 77), ("flex", 100), ("static", 128), ("flex", 128), ("thru", 0)]
MT = {"static": 0, "flex": 1, "thru": 2}


def make_wav(path, ch, bits, secs, seed):
    n = int(44100 * secs)
    rnd = random.Random(seed)
    fs = [rnd.uniform(70, 900) for _ in range(3)]
    ph = [rnd.uniform(0, 6.28) for _ in range(6)]
    with wave.open(str(path), "wb") as w:
        w.setnchannels(ch); w.setsampwidth(bits // 8); w.setframerate(44100)
        out = bytearray()
        for i in range(n):
            t = i / 44100
            for c in range(ch):
                v = sum(math.sin(2 * math.pi * fs[k] * t + ph[k + 3 * c]) for k in range(3)) / 3
                x = int(v * (2 ** (bits - 1) - 1) * 0.6)
                out += x.to_bytes(bits // 8, "little", signed=True)
        w.writeframes(bytes(out))
    return n


def build_project():
    proj = OUT / "_project" / "project"; card = OUT / "_project" / "card.img"
    if card.is_file():
        return card, json.loads((OUT / "_project" / "frames.json").read_text())
    shutil.rmtree(OUT / "_project", ignore_errors=True); (OUT / "_project" / "audio").mkdir(parents=True)
    V.build_projects(V.OUT / "_projects")                 # the fresh project, cached
    src = V.OUT / "fresh" / "image" / "NOPROJ"
    proj.mkdir(parents=True)
    for f in src.iterdir():
        if f.is_file() and f.suffix.lower() in (".work", ".strd"):
            shutil.copy2(f, proj / f.name)
    frames = {}
    for k, (name, (ch, bits, secs)) in enumerate(WAVS.items()):
        frames[name] = make_wav(OUT / "_project" / "audio" / f"{name}.wav", ch, bits, secs, 100 + k)
    blocks = []
    for kind, table in (("FLEX", FLEX_SLOTS), ("STATIC", STATIC_SLOTS)):
        for slot, name in table.items():
            bars = round(frames[name] / 88200 * 100)
            blocks.append(f"[SAMPLE]\r\nTYPE={kind}\r\nSLOT={slot:03d}\r\nPATH=../AUDIO/{name}.wav\r\n"
                          f"TRIM_BARSx100={bars}\r\nLOOP_BARSx100={bars}\r\nBPMx24=2880\r\nTSMODE=0\r\n"
                          f"LOOPMODE=0\r\nGAIN=48\r\nTRIGQUANTIZATION=-1\r\n[/SAMPLE]\r\n\r\n")
    for suffix in ("work", "strd"):
        pw = proj / f"project.{suffix}"
        raw = pw.read_bytes().decode("latin1")
        at = raw.find("[SAMPLE]")
        raw = raw.rstrip("\r\n") + "\r\n\r\n" + "".join(blocks) if at < 0 else raw[:at] + "".join(blocks) + raw[at:]
        pw.write_bytes(raw.encode("latin1"))
        pm = proj / f"markers.{suffix}"
        if pm.is_file():
            d = bytearray(pm.read_bytes())
            for kind, table in ((0, FLEX_SLOTS), (136, STATIC_SLOTS)):
                for slot, name in table.items():
                    at = 0x16 + 784 * (kind + slot - 1)
                    d[at:at + 784] = struct.pack(">III", 0, frames[name], 0) + bytes(768) + bytes(4)
            d[-2:] = (sum(d[0x10:-2]) & 0xFFFF).to_bytes(2, "big")
            pm.write_bytes(bytes(d))
    plan = {}

    def mut(data):
        for p in range(4):
            for t in range(8):
                kind, slot = COMBOS[(p * 8 + t * 5 + p) % len(COMBOS)]
                plan[f"{p}.{t}"] = [kind, slot]
                for pb in (p, p + 4):
                    base = op.PART_BASE + pb * op.PART_STRIDE
                    data[base + op.MTYPE_OFF + t] = MT[kind]
                    if kind in ("flex", "static"):
                        data[base + 0x2d3 + t * 5 + op.SLOT_KIND[kind]] = slot - 1
        for k in range(4):
            data[op.PTRN0 + k * op.PTRN_FSTRIDE + op.PTRN_FSTRIDE - 5] = k   # pattern k+1 -> Part k+1
            for t in range(8):
                data[op.trac_off(k, t) + 7] |= 1                              # step 1
    op._bank_write(proj, 1, mut, guard=False)
    args = [str(V.VENV), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(proj), "OCTABAM", "LC",
            "--tree", str(OUT / "_project" / "tree"), "--out", str(card)]
    for name in WAVS:
        args += ["--audio", f"{OUT / '_project' / 'audio' / (name + '.wav')}:AUDIO/{name}.wav"]
    r = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"stage_card failed\n{(r.stdout + r.stderr)[-1500:]}")
    (OUT / "_project" / "frames.json").write_text(json.dumps({"frames": frames, "plan": plan}))
    return card, {"frames": frames, "plan": plan}


def records(p):
    """Per slot: the trim (+300..+311), the 64 slice entries (+312..+1079) and the count (+1092..+1095):
    what LAZY CHOP writes. +1080..+1091 (the editor's marker and two words stock writes itself when a
    sample becomes active, e.g. +1084 = its length) are left out."""
    f = p.peek(FLEX0, 136 * REC); s = p.peek(STATIC0, 128 * REC)
    cut = lambda b, i: b[i * REC + 300:i * REC + 1080] + bytes(12) + b[i * REC + 1092:i * REC + 1096]
    return [cut(f, i) for i in range(136)] + [cut(s, i) for i in range(128)]


def table_ok(rec):
    ts, te = struct.unpack(">II", rec[0:8])
    n = struct.unpack(">I", rec[792:796])[0]
    if not 1 <= n <= 64:
        return f"count {n}"
    sl = [struct.unpack(">IIi", rec[12 + 12 * k:24 + 12 * k]) for k in range(n)]
    if sl[0][0] != ts:
        return f"slice 1 starts at {sl[0][0]}, trim start {ts}"
    for k in range(n - 1):
        if not (sl[k][0] < sl[k + 1][0] and sl[k][1] == sl[k + 1][0]):
            return f"slice {k + 1} {sl[k][:2]} / {k + 2} {sl[k + 1][:2]} not chained"
    if sl[-1][1] != te:
        return f"last slice ends at {sl[-1][1]}, trim end {te}"
    return None


def main():
    seed = int(sys.argv[1]); cycles = 10 ** 6; wall = 165.0
    if "--cycles" in sys.argv: cycles = int(sys.argv[sys.argv.index("--cycles") + 1])
    if "--wall" in sys.argv: wall = float(sys.argv[sys.argv.index("--wall") + 1])
    OUT.mkdir(parents=True, exist_ok=True)
    card0, meta = build_project()
    w = OUT / f"run_{seed}"; shutil.rmtree(w, ignore_errors=True); w.mkdir(parents=True)
    card = w / "card.img"; shutil.copy(card0, card)
    log = (OUT / f"{seed}.jsonl").open("w")
    rnd = random.Random(seed)
    t0 = time.time()
    r = V.Run(f"stress{seed}", card, "OCTABAM", "LC")
    p = r.p
    sym = r.sym
    ST, NXT, TMOD, SNAP = sym("lc_state"), sym("lc_next"), sym("lc_aud") + 4, sym("lc_snap")   # lc_tmod follows lc_aud in .data (G3 unchanged)
    sf, sd = sym("lc_snapfix"), sym("lc_snapdone")
    stats = dict(cycles=0, yes=0, no=0, leave=0, refused=0, wrong=0, fails=0, taps=0, snapcost_max=0)
    playing = False
    TRACE = os.environ.get("STRESS_TRACE")
    with p:
        p.settle()
        for c in range(cycles):
            if time.time() - t0 > wall:
                break
            acts = []
            fail = []
            try:
                # before: maybe a pattern change (direct jump toggled sometimes), the sequencer
                if rnd.random() < 0.15:
                    p.key("pattern", True); p.run(60); p.press("yes", settle=60); p.key("pattern", False); p.run(200)
                    acts.append("PTN+YES (direct jump toggle)")
                if rnd.random() < 0.35:
                    k = rnd.randint(1, 4)
                    p.key("pattern", True); p.run(60); p.press(f"trig{k}", settle=60); p.key("pattern", False); p.run(400)
                    acts.append(f"pattern {k}")
                if rnd.random() < 0.3:
                    p.press("stop" if playing else "play", settle=200); playing = not playing
                    acts.append("STOP" if not playing else "PLAY")
                t = rnd.randint(1, 8)
                live = p.peek(0x80000810 + 72 * (t - 1), 0x22)
                p.press(f"t{t}", settle=150)
                r.editor((f"t{t}", "bank"))
                before = records(p)              # after the editor opens: stock writes +1084 (the sample length) itself
                kind, slot = p.long(V.EDITOR_KIND), p.long(V.EDITOR_SLOT)
                target = (slot if kind == 1 else 136 + slot) if kind in (0, 1) else None
                acts.append(f"T{t} editor kind {kind} slot {slot + 1}")
                r.arm()
                if p.long(ST) != 1:
                    stats["refused"] += 1; acts.append("arm refused")
                    for _ in range(3): p.press("no", settle=150)
                    after = records(p)
                    diff = [i for i in range(264) if after[i] != before[i]]
                    if diff: fail.append(f"refused, yet slots changed: {diff}")
                else:
                    if rnd.random() < 0.3:
                        p.press("page", settle=200); acts.append(f"SNAP {p.long(SNAP)}")
                    snap_on = p.long(SNAP) == 1
                    watch = snap_on and rnd.random() < 0.3
                    if watch:
                        p.proc.command(f"watch {sf:#x},{sd:#x}", "ok"); p.proc.command("hits", "hits")
                    r.tap("trig1", rnd.randint(60, 200)); acts.append("TRIG 1")
                    live = p.peek(0x80000810 + 72 * (t - 1), 0x22)   # what LAZY CHOP saves from (stock refreshes it at the track select / trigger)
                    for _ in range(rnd.randint(0, 40)):
                        if p.long(ST) != 2: break
                        n = p.long(NXT); green = n % 16; last = (n - 1) % 16
                        x = rnd.random()
                        if x < 0.58:
                            r.tap(f"trig{green + 1}", rnd.randint(40, 250)); acts.append(f"green T{green + 1}"); stats["taps"] += 1
                        elif x < 0.66:
                            k = rnd.randint(1, 16); r.tap(f"trig{k}", rnd.randint(40, 150)); acts.append(f"any T{k}")
                        elif x < 0.76 and n % 16:
                            k = rnd.randint(1, n % 16); r.tap(f"trig{k}", rnd.randint(60, 200)); acts.append(f"audition T{k}")
                        elif x < 0.81:
                            V.hold(p, f"trig{last + 1}", rnd.choice((300, 700))); acts.append(f"hold last T{last + 1}")
                        elif x < 0.84 and n and n % 16 == 0:
                            V.hold(p, "trig1", 700); acts.append("hold page-start T1")
                        elif x < 0.87:
                            k = rnd.randint(1, 4)
                            p.key("pattern", True); p.run(60); p.press(f"trig{k}", settle=60); p.key("pattern", False); p.run(300)
                            acts.append(f"mid-chop pattern {k}")
                            # a Part change loads that Part's STRT/SLIC into the lane at stock's next
                            # refresh (a trigger), so the cycle has no fixed baseline: its lane check is off
                            live = None
                        elif x < 0.91:
                            p.press("stop" if playing else "play", settle=150); playing = not playing; acts.append("mid-chop STOP/PLAY")
                        elif x < 0.94:
                            p.press("page", settle=150); acts.append("mid-chop SNAP toggle")
                        else:
                            p.run(rnd.randint(100, 900)); acts.append("wait")
                        if TRACE:
                            lv = p.peek(0x80000810 + 72 * (t - 1), 0x22)
                            acts[-1] += f" [STRT {lv[1]} SLIC {lv[0x21]} tmod {p.long(TMOD)} rec {p.long(sym('lc_rec')):#x} ed {p.long(V.EDITOR_SLOT)}]"
                    if watch:
                        out = p.proc.command("hits", "hits").split()[2:]; p.proc.command("watch off", "ok")
                        st0 = None
                        for rec in out:
                            f = rec.split(":"); n_, pc = int(f[0], 16), int(f[1], 16)
                            if pc == sf: st0 = n_
                            elif pc == sd and st0 is not None:
                                cost = n_ - st0; st0 = None
                                stats["snapcost_max"] = max(stats["snapcost_max"], cost)
                                if cost >= SNAP_TAP_LIMIT: fail.append(f"snap cost {cost}")
                    state = p.long(ST)
                    if state == 0:
                        stats["wrong"] += 1; acts.append("ended by itself (wrong sample / 64)")
                        end = "self"
                    else:
                        x = rnd.random()
                        end = "yes" if x < 0.7 else "no" if x < 0.9 else "leave"
                    nxt = p.long(NXT)
                    if end == "yes": p.press("yes", settle=400); stats["yes"] += 1
                    elif end == "no": p.press("no", settle=400); stats["no"] += 1
                    elif end == "leave": p.press("pg_playback", settle=400); stats["leave"] += 1
                    acts.append(f"end {end} (next {nxt})")
                    if p.long(ST) != 0: fail.append(f"still open after {end} (state {p.long(ST)})")
                    if p.long(TMOD) != 0: fail.append("playback range left in place (lc_tmod)")
                    now = p.peek(0x80000810 + 72 * (t - 1), 0x22)
                    if live is not None and (now[1], now[0x21]) != (live[1], live[0x21]):
                        fail.append(f"live STRT/SLIC {now[1]}/{now[0x21]}, were {live[1]}/{live[0x21]}")
                    after = records(p)
                    diff = [i for i in range(264) if after[i] != before[i]]
                    if end == "yes" and acts[-1].endswith(f"(next {nxt})"):
                        other = [i for i in diff if i != target]
                        if other:
                            i = other[0]
                            offs = [300 + j for j in range(796) if after[i][j] != before[i][j]]
                            fail.append(f"YES changed other slots: {other}; slot {i} at record +{offs[:12]}")
                        if target is not None and target in diff:
                            bad = table_ok(after[target])
                            if bad: fail.append(f"chopped table invalid: {bad}")
                            if after[target][0:8] != before[target][0:8]: fail.append("trim changed")
                    elif end in ("no", "leave"):
                        if diff:
                            i = diff[0]
                            offs = [300 + j for j in range(796) if after[i][j] != before[i][j]]
                            fail.append(f"{end} left slots changed: {diff}; slot {i} bytes at record +{offs[:12]}")
                    for _ in range(3): p.press("no", settle=120)
                    if p.long(ST) != 0: fail.append("LAZY CHOP open after the exit presses")
            except Exception as e:
                fail.append(f"{type(e).__name__}: {e}")
            stats["cycles"] += 1
            if fail: stats["fails"] += 1
            log.write(json.dumps({"seed": seed, "cycle": c, "fail": fail, "acts": acts}) + "\n"); log.flush()
            if fail and any("PortDied" in f or "PortError" in f for f in fail):
                break
    stats["wall"] = round(time.time() - t0, 1)
    log.write(json.dumps({"seed": seed, "summary": stats}) + "\n"); log.close()
    print(json.dumps({"seed": seed, **stats}))


if __name__ == "__main__":
    main()
