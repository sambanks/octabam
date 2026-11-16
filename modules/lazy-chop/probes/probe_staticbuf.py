#!/usr/bin/env python3
"""Where a playing STATIC sample's audio sits in RAM (the stream buffer), and how it
lines up with the voice's playhead (+68). T1 STATIC slot 1, a seeded-noise WAV (no repeats)."""
import pathlib, shutil, sys, struct, wave, random, subprocess
ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/verify")); sys.path.insert(0, str(ROOT / "tools"))
import verify_lazy_chop as V
import verify_repitch as vr
work = V.OUT / "_probe" / "staticbuf"; shutil.rmtree(work, ignore_errors=True); work.mkdir(parents=True)
V.build_projects(V.OUT / "_projects")                 # the fresh project (cached)
src = V.OUT / "fresh" / "image" / "NOPROJ"
N = vr.LOOP_FRAMES
rnd = random.Random(7)
L = [rnd.randint(-20000, 20000) for _ in range(N)]; R = [rnd.randint(-20000, 20000) for _ in range(N)]
wav = work / "noise.wav"
with wave.open(str(wav), "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(44100)
    w.writeframes(b"".join(struct.pack("<hh", L[i], R[i]) for i in range(N)))
proj = work / "project"
vr.build_project(src, proj, 0, 0, 120.0, 64, 127, "static")
card = work / "card.img"
r = subprocess.run([str(V.VENV), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(proj), "OCTABAM", "LC",
                    "--tree", str(work / "tree"), "--out", str(card), "--audio", f"{wav}:{vr.SAMPLE_REL}"],
                   cwd=ROOT, capture_output=True, text=True)
assert r.returncode == 0, r.stdout[-800:] + r.stderr[-800:]
def be(f, n=2): return b"".join(struct.pack(">hh", L[(f + i) % N], R[(f + i) % N]) for i in range(n))
regions = [(0x40000400, 0x40A955E0 - 0x40000400), (0x40A955E0, 14602 * 6144), (0x46000000, 0x00D00000), (0x80000000, 0x10000)]
run = V.Run("staticbuf", card, "OCTABAM", "LC")
with run.p as p:
    p.settle()
    p.press("play", settle=700)
    pos = p.long(V.VOICES + 68); act = p.peek(V.VOICES, 1)[0]
    print(f"playing: T1 voice act {act}, playhead {pos}, settings {p.long(V.VOICES + 8):#x} (STATIC rec 0x100d5b30)")
    print("voice record:", p.peek(V.VOICES, 0xa8).hex())
    BASE = p.long(V.VOICES + 0x68)
    print("voice +0x68..+0x77:", [hex(p.long(V.VOICES + o)) for o in (0x68, 0x6c, 0x70, 0x74)])
    buf = p.peek(BASE, 0x40000)
    smap = {}
    for c in range(0, N * 4 // 4096):
        f = c * 1024 + 7
        i = buf.find(be(f))
        if i >= 0 and (i - 28) % 4096 == 0:
            smap[(i - 28) // 4096] = c
    print("base", hex(BASE), "slot -> chunk:", dict(sorted(smap.items())))
    pos2 = p.long(V.VOICES + 68); print("playhead now", pos2, "chunk", pos2 * 4 // 4096)
    D = 0x46AA9E80
    for sl in range(0, 32):
        e = p.peek(D + sl * 8, 8)
        print(f"T1 compartment {sl}: chunk {smap.get(sl)} | +0 {int.from_bytes(e[0:4],'big')} id {e[4]} valid {e[5]} age {e[6]}")
    st = p.peek(0x46C90A78, 0x2C); print("STATIC slot 1 status rec:", st.hex())
    print("format table:", p.peek(0x80003C20, 64).hex())
    print("STATIC rec +300/+304:", p.long(0x100D5B30 + 300), p.long(0x100D5B30 + 304))
    # check the rule against the measured map, every chunk 0..86
    ok = bad = 0
    for c in range(0, 86):
        hit = None
        for k in (0, 1):
            idx = 2 * (c & 15) + k
            e = p.peek(D + idx * 8, 8)
            if e[5] and int.from_bytes(e[0:4], "big") == c >> 4:
                hit = idx
        f = c * 1024 + 7
        if hit is not None:
            if p.peek(0x46949E80 + hit * 4096 + 28, 8) == be(f): ok += 1
            else: bad += 1
    print(f"rule check: {ok} chunks found where the descriptors say, {bad} wrong")
    p.press("stop", settle=100)
