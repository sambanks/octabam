"""XF CURVE -- the crossfader's curve: LINEAR (stock), four S-curves, their four inverses, CUT, CUT A, CUT B, SLOW A or SLOW B.

Stock turns the crossfader position xf (0..127, 127 = scene A) into scene
weights through one table of 128 signed shorts at 0x400bcd90, linear:
w[x] = -round(32768 x / 127), the share of scene A in Q15, negated. Nine
reads of it in the image (`lea 0x400bcd90`), all keyed by the position
0x460d16c8: the panel and MIDI CC 48 handlers' per-track weight longs
0x80003c60.. (0x40061e40, 0x400626ba), which the frame builder's scene
morph and XVOL read every frame (0x4000cca4..0x4000cf04), the STRT/LEN/RATE
morph 0x4003f1b4 and its siblings (0x4003ee46, 0x4003f0ca, 0x4006ff2e,
0x400935ae), and two more (0x4009dd2a, 0x400a3122). MORPH reads it too
(modules/morph/morph.s CURVE). So rewriting the table changes the curve
everywhere the crossfader reaches, in step, and costs nothing per frame.

Sites, from the user's 1.40C (base 0x40000400), disassembled with
m68k-elf-objdump -m m68k:cfv4e:
  * 0x40061e34 `lea 0x80003c60,%a0` (41f9 8000 3c60), the panel handler
    (event type 4, 0x40061e0a), after it stores xf and before it rebuilds
    the ten weight longs from the table.
  * 0x400626ae, the same instruction in the MIDI CC 48 handler (type 0x44,
    0x4006269a).
Both become a jsr to xfc_hook, which writes the chosen curve over the table
when the CURVE setting has changed since the last write, then replays the
lea. The table is data in cached SDRAM (no MMU, PLACEMENT.md), read by the
CPU only.

The curves are generated here, f(u) with u = xf/127 the share of scene A:
  LINEAR   u                          stock's table, bit for bit
  S SOFT, S-CURVE, S FIRM, S HARD     one normalized logistic family
                                      (s_curve), slope at the middle 1.25,
                                      1.5, 2 and 3 times stock's: the
                                      scenes hold longer near both ends
  INV SOFT, INV-CURVE, INV FIRM, INV HARD  the inverses of those four:
                                      slope at the middle 0.8, 0.67, 0.5,
                                      0.33 times stock's, steep near the
                                      ends: fine control around the blend
  CUT      0 to u 0.45, 1 from 0.55   the fader as a scene switch, a short
                                      linear blend in the middle
  CUT A    scene B except at the A    the fader as a momentary switch (a
  CUT B    end, and the mirror        scratch-style cut): one step of dead
                                      travel at that end, a three-step ramp
  SLOW A   1 - (1 - u)^2              fine control near scene A
  SLOW B   u^2                        fine control near scene B
and stored as -round(32768 f). LINEAR's table is the formula stock's
satisfies (checked against the image by tools/verify/verify_xfcurve.py), so
no stock byte is carried.

Not covered: MIDI SCENES mixes the MIDI tracks from the raw position with
its own linear weight (modules/midi-scenes/scenes.s `mix`), so MIDI tracks
stay linear. A CURVE change lands on the next crossfader move: until then
the table and the weights keep the previous curve.
"""

import os

from remix.schema import (Apply, Category, Detour, Gate, Kind, Linked, Module, Option, Proof, Scope,
                          Setting, Store)

H = bytes.fromhex
_HERE = os.path.relpath(os.path.dirname(os.path.realpath(__file__)))

STORE_ID = "octabam.xfcurve"
LEA_WEIGHTS = H("41f980003c60")              # lea 0x80003c60,%a0
PANEL_SITE = 0x40061E34
MIDI_SITE = 0x400626AE

def s_curve(mid_slope, inverse=False):
    """A normalized logistic through (0,0) and (1,1) whose slope at the
    middle is `mid_slope` (1 = LINEAR, larger = steeper middle, flatter ends):
    f(u) = (L(k(u - 1/2)) - L(-k/2)) / (L(k/2) - L(-k/2)), k solved for the
    slope by bisection. `inverse` gives that curve's inverse function: the
    same shape mirrored about the diagonal, slope 1/mid_slope at the middle
    (a flatter middle, steeper ends)."""
    import math
    L = lambda z: 1 / (1 + math.exp(-z))
    slope = lambda k: (k / 4) / (L(k / 2) - L(-k / 2))
    lo, hi = 1e-9, 80.0
    for _ in range(200):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if slope(mid) < mid_slope else (lo, mid)
    k = (lo + hi) / 2
    a, b = L(-k / 2), L(k / 2)
    if not inverse:
        return lambda u: (L(k * (u - 0.5)) - a) / (b - a)
    # the inverse function: slope 1/mid_slope at the middle, steep at the ends
    return lambda u: 0.5 + math.log((p := a + u * (b - a)) / (1 - p)) / k


def end_cut(x):
    """A cut at one end, by distance x in fader steps from that end: that
    end's scene for x <= 1 (one step of dead travel), a ramp over x = 2..4
    (0.25, 0.5, 0.75), the other scene from x = 5 on. Returned as the share
    of the other scene."""
    return min(1.0, max(0.0, (round(x) - 1) / 4))


CURVES = (
    ("LINEAR", lambda u: u),
    ("S SOFT", s_curve(1.25)),
    ("S-CURVE", s_curve(1.5)),
    ("S FIRM", s_curve(2.0)),
    ("S HARD", s_curve(3.0)),
    ("INV SOFT", s_curve(1.25, inverse=True)),
    ("INV-CURVE", s_curve(1.5, inverse=True)),
    ("INV FIRM", s_curve(2.0, inverse=True)),
    ("INV HARD", s_curve(3.0, inverse=True)),
    ("CUT", lambda u: 0.0 if u <= 0.45 else 1.0 if u >= 0.55 else (u - 0.45) / 0.10),
    ("CUT A", lambda u: 1 - end_cut(127 - u * 127)),
    ("CUT B", lambda u: end_cut(u * 127)),
    ("SLOW A", lambda u: 1 - (1 - u) ** 2),
    ("SLOW B", lambda u: u * u),
)
LABELS = tuple(name for name, _ in CURVES)


def table(f):
    """128 Q15 shorts, -round(32768 f(x/127)), f clamped to 0..1."""
    return [-round(32768 * min(1.0, max(0.0, f(x / 127)))) for x in range(128)]


def curves_inc(modules, remix):
    """remix.inc: the get_curve macro and the curve tables."""
    import sys, pathlib
    from remix import schema
    sys.path.insert(0, str(pathlib.Path(schema.__file__).resolve().parents[1]))
    from remix import brain
    mods = modules if isinstance(modules, dict) else {}
    out = ["| remix.inc -- XF CURVE (modules/xfcurve/manifest.py)",
           brain.read_macro(remix, mods, STORE_ID, "CURVE", "get_curve").rstrip("\n"),
           f"        .set    xfc_n, {len(CURVES)}",
           "        .section .rodata", "        .balign 4", "xfc_tables:"]
    for name, f in CURVES:
        t = table(f)
        out.append(f"| {name}")
        for i in range(0, 128, 16):
            out.append("        .short  " + ", ".join(str(v) for v in t[i:i + 16]))
    out.append("        .text")
    return "\n".join(out) + "\n"


MODULE = Module(
    name="xfcurve",
    key="XF CURVE",
    kind=Kind.CF_PATCH,
    category=Category.PARTS,
    author="bryantysinger",
    author_url="https://github.com/bryantysinger",
    doc=("The crossfader's curve, chosen in BRAIN: LINEAR (stock), four S-curves (S SOFT to S HARD), their inverses (INV SOFT to INV HARD), CUT, CUT A, CUT B, SLOW A or SLOW B. "
         "Applies to scene locks, XVOL and the playback morph alike."),
    proof=Proof.HARDWARE,
    proof_note=("on hardware: Bryan's MKII, remix _bt_mtrx_io_vib, 6 Nov 2026 (panel crossfader, every curve "
                "including CUT A / CUT B); port gate tools/verify/verify_xfcurve.py"),
    linked=(
        Linked("xfcurve", os.path.join(_HERE, "xfcurve.s"), dram=True, include=curves_inc),
    ),
    detours=(
        Detour(PANEL_SITE, LEA_WEIGHTS, "xfcurve", "xfc_hook",
               "panel crossfader handler, before the weight rebuild: write the chosen curve",
               kind="jsr"),
        Detour(MIDI_SITE, LEA_WEIGHTS, "xfcurve", "xfc_hook",
               "MIDI CC 48 crossfader handler, before the weight rebuild: write the chosen curve",
               kind="jsr"),
    ),
    gates=(Gate("tools/verify/verify_xfcurve.py", stage="image"),),
    store=Store(STORE_ID),
    settings=(Setting(1, "CURVE", Option(*LABELS), default="LINEAR", scope=Scope.CARD,
                      apply=Apply.LIVE,
                      doc="the crossfader's curve: LINEAR is stock; S SOFT, S-CURVE, S FIRM, S HARD hold near both scenes, "
                          "steeper in the middle in that order; INV SOFT, INV-CURVE, INV FIRM, INV HARD are their inverses, "
                          "flatter in the middle; "
                          "CUT A / CUT B cut at that scene's end (scene B / A everywhere else); "
                          "CUT switches in the middle; SLOW A / SLOW B give fine control near that scene"),),
)
