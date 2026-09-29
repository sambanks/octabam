#!/usr/bin/env python3
"""Prove the RIG BURN image is the shipping image plus an inert, exact knob
(SEND's page-2 slot 6 since 16 Sep 2026; P6 below).

  1. INERT WHEN OFF.   BURN=1 SPEC=1 at BURN 0 renders BIT-IDENTICALLY to
     the shipping build. Not "sounds the same" -- byte for byte, the mix
     and every track.
  2. INERT WHEN ON.    At BURN 127 the audio is still bit-identical. The
     burn is nops; if it perturbs the audio it is touching a live register.
  3. EXACT.            The meter's instructions/sample rise by 24 * 127 =
     3,048 on EACH core between BURN 0 and 127 (+-1: the knob decode and
     the zero guard are the only other words, and they run at 0 too).
  4. THE HARNESS CAN SEE. AUX 0 vs AUX 100 on the same layout must DIFFER,
     or "bit-identical" is a claim about a blind comparison (the control
     the bit-identity rule demands).
  5. FX2 ONLY.         A SEND on an FX1 slot at BURN 127 adds NOTHING to the
     meter. Id 0 is aliased to SEND, so on the unit this proc runs on every
     FX1 slot set to NONE with that page's stale bytes as its knobs -- the
     first rig-burn image hung the sequencer on step 1 with every effect
     turned off.

The old probe shape (BURN=1 without SPEC: the reverb's own burn blocks,
the alias probe in the delay's slot) is not tested here; it is a
diagnostic image the rig cannot build any more (payload A has no words
for the reverb blocks) and the sweep does not need it.

    python3 tools/verify/verify_burn.py [REMIX]
"""
import hashlib, os, pathlib, re, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401

SCRATCH = ROOT / "out" / "burnverify"
STEP = 24


def run(cmd, env=None):
    e = dict(os.environ); e.update(env or {})
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, env=e)
    if r.returncode:
        sys.exit(f"FAILED: {' '.join(str(c) for c in cmd)}\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}")
    return r.stdout


def build(remix, burn):
    # Both builds without OS SWITCH: its 40-word DSP park (host command
    # only, no per-sample cycles) does not fit beside the burn splice in a
    # full payload (bottleservice-ret: 6177 > 6158), and ship and burn must
    # differ by the burn alone.
    # ... and without USB AUDIO IN (its inject runs once a frame, no
    # per-sample cycles), which does not fit beside the splice either once
    # RETURNS fills payload A (bottleservice-pf: 5 words free).
    env = {"REMIX": remix, "XBUS": "1", "SPEC": "1", "OCTABAM_NO_OS_SWITCH": "1",
           "OCTABAM_NO_USB_IN": "1"}
    if burn:
        env["BURN"] = "1"
    run([sys.executable, "tools/build/build_bus.py"], env)
    dst = SCRATCH / ("burn.bin" if burn else "ship.bin")
    dst.write_bytes((ROOT / "out/mainos_bus.bin").read_bytes())
    return dst


def render(image, remix, out, burn, aux=100):
    out.mkdir(parents=True, exist_ok=True)
    txt = run([sys.executable, "tools/harness/rig_render.py", "--image", str(image), "--remix", remix,
               "--tracks", "T1=DELAY SERVER,T2=SEND,T5=REVERB SERVER,T6=SEND",
               "--stem", "T2=out/test_audio/loop.wav", "--stem", "T6=out/test_audio/pad.wav",
               "--tail", "0.5", "--seconds", "1.5", "--frames", "16",
               "--set", f"T2:DEL={aux}", "--set", f"T6:DEL={aux}",
               "--set", f"T2:REV={aux}", "--set", f"T6:REV={aux}",
               "--set", f"T2:FX2:P6={burn}", "--set", f"T6:FX2:P6={burn}", "--out", str(out)])
    meters = {}
    for m in re.finditer(r"core (\d) meter: max (\d+) instructions", txt):
        meters[int(m.group(1))] = int(m.group(2))
    return meters


def render_fx1(image, remix, out, burn):
    out.mkdir(parents=True, exist_ok=True)
    txt = run([sys.executable, "tools/harness/rig_render.py", "--image", str(image), "--remix", remix,
               "--tracks", "T1=DELAY SERVER,T2=SEND+SEND",
               "--stem", "T2=out/test_audio/loop.wav", "--tail", "0", "--seconds", "1", "--frames", "16",
               "--set", "T2:DEL=100", "--set", "T2:REV=100", "--set", f"T2:FX1:P6={burn}", "--out", str(out)])
    return {int(m.group(1)): int(m.group(2)) for m in re.finditer(r"core (\d) meter: max (\d+) instructions", txt)}


def digest(d):
    h = hashlib.md5()
    for f in sorted(d.glob("*.wav")):
        h.update(f.name.encode()); h.update(f.read_bytes())
    return h.hexdigest()


def main():
    remix = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("REMIX")
    # The rig burn is a knob on SEND rendered through the bus rig (DELAY
    # SERVER, SEND, REVERB SERVER). A remix without them (recfix, midi-scenes,
    # mods) has nothing to burn and nothing to render: a loud SKIP, never a
    # failure -- the old alias probe had the same policy, and dropping it
    # broke make check on every such remix the morning the rig burn landed.
    from remix import registry
    mods = set(registry.remix(remix).modules)
    need = {"SEND", "DELAY SERVER", "REVERB SERVER"}
    if not need <= mods:
        print(f"  SKIPPED: the rig burn needs {sorted(need - mods)}, which remix "
              f"{remix!r} does not carry -- nothing to burn")
        return 0
    if not (ROOT / "out/test_audio/loop.wav").is_file():
        run([sys.executable, "scripts/make_test_audio.py"])
    SCRATCH.mkdir(parents=True, exist_ok=True)
    ship = build(remix, burn=False)
    burn = build(remix, burn=True)
    render(ship, remix, SCRATCH / "ship", burn=0)
    m_b0 = render(burn, remix, SCRATCH / "b0", burn=0)
    m_b127 = render(burn, remix, SCRATCH / "b127", burn=127)
    render(ship, remix, SCRATCH / "ctl", burn=0, aux=0)
    d_ship, d_b0, d_b127, d_ctl = (digest(SCRATCH / k) for k in ("ship", "b0", "b127", "ctl"))
    ok = True

    def check(cond, label, detail=""):
        nonlocal ok
        ok &= bool(cond)
        print(f"  [{'PASS' if cond else 'FAIL'}] {label}{('  ' + detail) if detail else ''}")

    check(d_ship == d_b0, "inert when off: BURN 0 == the shipping build, byte for byte", d_b0[:12])
    check(d_ship == d_b127, "inert when on: BURN 127 == the shipping build, byte for byte", d_b127[:12])
    for core in (0, 1):
        delta = (m_b127.get(core, 0) - m_b0.get(core, 0)) / 16.0
        check(abs(delta - STEP * 127) <= 1.0, f"exact: core {core} rises by {STEP} * 127 instructions/sample",
              f"{delta:+.1f} (want {STEP * 127:+d})")
    check(d_ship != d_ctl, "the harness can see: AUX 0 vs AUX 100 differ")
    m_f0 = render_fx1(burn, remix, SCRATCH / "fx1_0", burn=0)
    m_f127 = render_fx1(burn, remix, SCRATCH / "fx1_127", burn=127)
    check(m_f0.get(1) == m_f127.get(1), "FX2 only: a SEND on an FX1 slot at BURN 127 adds nothing",
          f"{m_f0.get(1)} vs {m_f127.get(1)} instructions in the worst block")
    (ROOT / "out/mainos_bus.bin").write_bytes(ship.read_bytes())   # leave the shipping build on disk
    print("\nOK" if ok else "\nFAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
