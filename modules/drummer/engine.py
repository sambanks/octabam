"""DRUMMER's engine on the host: drummer.c compiled into a shared library and driven through ctypes.

Used by verify.py (the rules) and render.py (the WAV renders). Reads no firmware.
"""
import ctypes
import pathlib
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
ZONES = ["KICK", "SNARE", "GHOST", "HATC", "HATO", "RIDE", "CRASH", "TOM", "PERC"]
COMBO, OUT = 9, 15
ROLES = ["ACCENT", "NORMAL", "SOFT"]
import styles as _styles  # noqa: E402
STYLES = [s[0] for s in _styles.STYLES]
FLAGS = {1: "FORCED", 2: "GHOST", 4: "FILL", 8: "BREAK", 16: "COMBO", 32: "SHIFT"}


class Kit(ctypes.Structure):
    _fields_ = [("zone", ctypes.c_uint8 * 64), ("role", ctypes.c_uint8 * 64), ("combo", ctypes.c_uint16 * 64),
                ("count", ctypes.c_uint8), ("prio", ctypes.c_uint8 * 9), ("reserved", ctypes.c_uint8 * 2)]


class Params(ctypes.Structure):
    _fields_ = [(n, ctypes.c_uint8) for n in ("style", "dens", "cplx", "human", "brk", "seed",
                                              "vel", "round", "time", "ghost", "orn", "var", "shift", "phrase")] + \
               [("mix", ctypes.c_uint8 * 6), ("fill", ctypes.c_uint8 * 6), ("reserved", ctypes.c_uint8 * 2),
                ("loop", ctypes.c_void_p), ("bar", ctypes.c_void_p)]


class Loop(ctypes.Structure):
    """REDRUM (image 77): the sample's loop, dr_loop_build's."""
    _fields_ = [("len", ctypes.c_uint8), ("slice", ctypes.c_uint8 * 128), ("mt", ctypes.c_int8 * 128),
                ("pad", ctypes.c_uint8)]


class LoopBar(ctypes.Structure):
    _fields_ = [("row", ((ctypes.c_char * 17) * 9) * 3), ("lv", (ctypes.c_void_p * 9) * 3),
                ("fill", ctypes.c_void_p * 9), ("late", ctypes.c_uint8), ("swing", ctypes.c_uint8),
                ("len", ctypes.c_uint8), ("fam", ctypes.c_uint8 * 4)]


_BAR = None


def loop(starts, total, bars100=100, tempo24=0, align=None, trim=None):
    """A Loop from slice starts (frames) in a trim of `total` frames (or trim=(start, end))."""
    global _BAR
    l = Loop()
    n = len(starts)
    b = (ctypes.c_uint32 * (3 * max(1, n)))()
    for i, s in enumerate(starts):
        b[3 * i] = s
        b[3 * i + 1] = starts[i + 1] if i + 1 < n else total
    al = (ctypes.c_uint8 * 64)(*(align or [0] * 64))
    ts, te = trim or (0, total)
    lib().dr_loop_build(ctypes.byref(l), b, n, ts, te, bars100, tempo24, al)
    if _BAR is None:
        _BAR = LoopBar()
    return l


class State(ctypes.Structure):
    _fields_ = [("last", (ctypes.c_uint8 * 3) * 9), ("carry", ctypes.c_uint8), ("prev_zone", ctypes.c_uint8),
                ("prev_slice", ctypes.c_uint8), ("since_crash", ctypes.c_uint8),
                ("fill_len", ctypes.c_uint8)]


class Hit(ctypes.Structure):
    _fields_ = [("play", ctypes.c_uint8), ("slice", ctypes.c_uint8), ("vel", ctypes.c_uint8), ("mtime", ctypes.c_int8),
                ("rtrg", ctypes.c_uint8), ("rtim", ctypes.c_uint8), ("zone", ctypes.c_uint8), ("flags", ctypes.c_uint8)]

    def as_tuple(self):
        return (self.play, self.slice, self.vel, self.mtime, self.rtrg, self.rtim, self.zone, self.flags)


_LIB = None


def lib():
    global _LIB
    if _LIB is None:
        cc = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
        out = pathlib.Path(tempfile.mkdtemp(prefix="drummer_")) / "libdrummer.so"
        subprocess.run([cc, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror", "-shared", "-fPIC",
                        str(HERE / "drummer.c"), "-o", str(out)], check=True)
        _LIB = ctypes.CDLL(str(out))
        _LIB.dr_step.argtypes = [ctypes.POINTER(Kit), ctypes.POINTER(Params), ctypes.POINTER(State),
                                 ctypes.c_uint32, ctypes.c_uint, ctypes.c_uint, ctypes.POINTER(Hit)]
        _LIB.dr_groove_hits.restype = ctypes.c_uint
        _LIB.dr_fill_sticks.restype = ctypes.c_uint
        _LIB.dr_fill_stick_name.restype = ctypes.c_char_p
    return _LIB


def make_kit(count, slices):
    """slices: {index: (zone name or 'COMBO', role name, [combo zone names])}"""
    k = Kit()
    lib().dr_kit_init(ctypes.byref(k), count)
    for i, (zone, role, *combo) in slices.items():
        k.zone[i] = COMBO if zone == "COMBO" else ZONES.index(zone)
        k.role[i] = ROLES.index(role)
        if combo and combo[0]:
            k.combo[i] = sum(1 << ZONES.index(z) for z in combo[0])
    return k


def params(**kw):
    p = Params(style=0, dens=64, cplx=0, human=0, brk=0, seed=1, vel=64, round=64, time=64, ghost=64,
               orn=16, var=64, shift=0, phrase=4)
    p.mix[:] = [64] * 6                     # KIT BALANCE: every zone as the style plays it
    for name, v in kw.items():
        if name == "mix":
            p.mix[:] = list(v)
        elif name == "fill":                 # FILLS: FILL FREQ LONG STIK ORCH TRIP (0 AUTO each)
            p.fill[:] = list(v)
        else:
            setattr(p, name, v)
    return p


def play(kit, p, bars, forced=(), brk_curve=None, redrum=None):
    """Run the engine over `bars` bars from the transport start: a list of (bar, step, Hit tuple).
    forced: set of (bar, step) with a track trig. brk_curve(bar, step) -> BRK (a crossfader move)."""
    s = State()
    out = []
    h = Hit()
    steps = lib().dr_style_len(p.style)
    if redrum is not None and redrum.len:   # REDRUM: the loop, 4/4 bars
        p.loop = ctypes.addressof(redrum)
        p.bar = ctypes.addressof(_BAR)
        steps = 16
    for bar in range(bars):
        for step in range(steps):
            if brk_curve:
                p.brk = brk_curve(bar, step)
            lib().dr_step(ctypes.byref(kit), ctypes.byref(p), ctypes.byref(s), bar, step,
                          1 if (bar, step) in forced else 0, ctypes.byref(h))
            out.append((bar, step, h.as_tuple()))
    return out
