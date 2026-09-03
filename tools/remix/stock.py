"""The stock FX2 effects, as things a remix can keep in the chooser.

Every octabam image replaces the FX2 chooser wholesale with the remix's
modules. Until 2 Sep 2026 that hid all fourteen stock FX2 effects, although
only three of them are actually CONSUMED -- PLATE, SPRING and DARK REV,
whose 2,724 words of DSP code are the donor region every module packs into.
The other eleven keep their code, their descriptor and their dispatch
entries in every image; they merely had no chooser row. This table makes
them first-class so a remix can list them by name, in chooser order, next
to the modules -- and so the composer can say what is kept, what is hidden
and what is replaced instead of leaving the operator to guess.

A stock entry costs NOTHING: no clone (its descriptor is where stock put
it), no placement (its code is where stock put it), no words, no cycles
charged by `make cycles` (which cannot see it -- the FILTER figure of 192
cycles is the only one measured, docs/CHIP.md). What the build writes for
it is its list row and its cursor position, and nothing else.

ITS KNOBS ARE READ FROM THE STOCK DESCRIPTOR, not declared: names, defaults,
value counts and the enable bitmap come out of the pristine image
(out/raw/section_3_MAIN_OS.bin, the same record the panel draws from), so
the remixer shows a stock effect's real page-1/page-2 controls and
`send_probe --set` can drive them by name. The build never writes these
params back (a stock row is not cloned), and when the image is absent --
a fresh clone before `make setup` -- the entry simply carries no params.

A SELECT'S LABELS COME FROM THE FIRMWARE ITSELF: the words a stock select
draws ("12dB|24dB", "NONE|HP|LP|BOTH", "A#0".."A 9") are not data in the
image, they are printed by the slot's display-formatter FUNCTION, so
tools/stock_labels.py runs each formatter on the emulated ColdFire for every
value and checks the result in as stock_labels.json (2 Sep 2026). The
registry reads that file; the selftest proves it still matches the firmware
whenever the emulator is available.

RENDERING. A stock effect renders locally the way an insert does: dsp_host
runs its code straight from a dump of the STOCK image's payload A
(tools/remix/audition.py), with `-alloc 1` so an effect that takes an
instance buffer gets Y:0x4000 as the hardware would give track 1. Measured
2 Sep 2026: FILTER passes at unity and a narrow LP takes a tone down 27 dB,
CHORUS at MIX=127 modulates, COMPRESSOR passes at defaults. The one that
cannot render is DELAY: its DSP dispatch is stock's null stub because the
Echo Freeze delay runs on the ColdFire (DMA over SDRAM rings,
docs/EXTERNAL.md), so there is no DSP code to run.

Two of them are special:

  DELAY (0x08)   works from its row exactly as on a stock unit, costs the
                 DSP nothing, and has no local render (above).
  the four with  SPATIALIZER, FLANGER, CHORUS, COMB allocate an FX2
  a buffer       instance buffer through the host's bump allocator (they
                 read X:0x213 at init; docs/DSP.md section 10), and the
                 allocator hands out per-TRACK bases that are exactly the
                 addresses ChonVerb, Nimbus and BongDelay hardcode. The
                 ledger refuses them beside any module with fixed Y
                 buffers; see Claims.stock_instance_buffer.

Addresses are the descriptors' E addresses from docs/PARAM_PAGES.md
section 2 (P = E + 0x38 is what the chooser list holds). Words are the
module spans from docs/DSP.md section 7c, for the index only.
"""

from __future__ import annotations

import pathlib

from remix.schema import Claims, Harness, Kind, MenuEntry, Module, Param

ROOT = pathlib.Path(__file__).resolve().parents[2]
STOCK_IMAGE = ROOT / "out/raw/section_3_MAIN_OS.bin"
BASE = 0x40000400                      # dsp_modmap.BASE, without the cwd-relative path

# P-relative descriptor offsets (docs/PARAM_PAGES.md section 5b; the same
# constants tools/build_bus.py writes through).
_P_NAMES, _P_DEFAULTS, _P_COUNTS = 0x16, 0x5e, 0x9a
_P_PENABLE_LO, _P_PENABLE_HI = 0x18e, 0x18a

_img: bytes | None = None
LABELS_FILE = pathlib.Path(__file__).with_name("stock_labels.json")
_labels: dict | None = None


def _label_table():
    global _labels
    if _labels is None:
        try:
            import json
            _labels = json.loads(LABELS_FILE.read_text())
        except (OSError, ValueError):
            _labels = {}
    return _labels


def _image():
    global _img
    if _img is None and STOCK_IMAGE.exists():
        _img = STOCK_IMAGE.read_bytes()
    return _img


# ---- which MENU a stock effect appears on ----------------------------------
# FX1 and FX2 are two slots on the same track, and stock gives them DIFFERENT
# chooser lists: FX1 offers ten effects, FX2 offers those ten plus DELAY and
# the three reverbs. That asymmetry is why taking the reverbs as donors cost
# FX1 nothing -- they were never on its menu.
#
# Read from the pristine image rather than written down, so it cannot drift.
# (Both stock lists open with a NONE row, id 0x00 -- which our rebuilt FX2
# list drops. Noted 2 Sep 2026 from an outside report; see PLAN.)
FX1_CHOOSER, FX2_CHOOSER = 0x400d6060, 0x400d6090
_fx1_ids: frozenset[int] | None = None


def _chooser_ids(addr: int, limit: int = 32) -> frozenset[int]:
    img = _image()
    if img is None:
        return frozenset()

    def rd32(a):
        i = a - BASE
        return int.from_bytes(img[i:i + 4], "big") if 0 <= i <= len(img) - 4 else 0

    out, a = set(), addr
    for _ in range(limit):
        ptr = rd32(a)
        if not ptr:
            break
        out.add(rd32(ptr) & 0xff)       # the descriptor's own id word, P+0
        a += 4
    return frozenset(out)


def _chooser_order(addr: int, limit: int = 32) -> tuple[int, ...]:
    """The same ids IN ROW ORDER. Membership answers "is it on FX1"; order
    answers "where", which is what a remixer composing the list needs."""
    img = _image()
    if img is None:
        return ()

    def rd32(a):
        i = a - BASE
        return int.from_bytes(img[i:i + 4], "big") if 0 <= i <= len(img) - 4 else 0

    out, a = [], addr
    for _ in range(limit):
        ptr = rd32(a)
        if not ptr:
            break
        out.append(rd32(ptr) & 0xff)    # the descriptor's own id word, P+0
        a += 4
    return tuple(out)


def fx1_ids() -> frozenset[int]:
    """Effect ids the STOCK FX1 chooser lists, read from the pristine image."""
    global _fx1_ids
    if _fx1_ids is None:
        _fx1_ids = _chooser_ids(FX1_CHOOSER)
    return _fx1_ids


def fx1_order() -> tuple[int, ...]:
    """Those ids in stock's own row order, NONE (0x00) included at row 0 --
    which is where the remixer's default FX1 chooser comes from."""
    return _chooser_order(FX1_CHOOSER)


def _params(desc_E: int, effect: str, key: str) -> tuple[Param, ...]:
    """The twelve slots as the stock descriptor declares them, or () when
    the image is not on disk."""
    img = _image()
    if img is None:
        return ()
    P = desc_E + 0x38 - BASE

    def rd32(off):
        return int.from_bytes(img[P + off:P + off + 4], "big")

    lo, hi = rd32(_P_PENABLE_LO), rd32(_P_PENABLE_HI)
    out, seen = [], set()
    for i in range(12):
        active = bool(((lo if i < 8 else hi) >> (4 * (i if i < 8 else i - 8))) & 1)
        name = img[P + _P_NAMES + i * 6:P + _P_NAMES + i * 6 + 6].split(b"\0")[0]
        count = rd32(_P_COUNTS + i * 4)
        default = img[P + _P_DEFAULTS + i]
        if not active or not name:
            out.append(Param())
            continue
        # Two slots can share a panel label (FILTER draws Q on page 1 and a
        # 4-step Q select on page 2). knob_map() is name-keyed, so the later
        # one gets its page number appended for the remixer and the
        # harness; the panel itself is untouched (nothing here is written).
        if name in seen:
            name = name[:5] + b"2"
        seen.add(name)
        kind = (f"{count}-way select" if count < 128 else "knob")
        # The firmware's own words for each value, when the table has them
        # for exactly this count (a stale table must not mislabel a value).
        lbl = _label_table().get(key, {}).get(name.decode("latin1"))
        labels = tuple(lbl) if (count < 128 and lbl and len(lbl) == count) else None
        out.append(Param(
            name=name, default=min(default, max(count - 1, 0)),
            count=count if count < 128 else None, active=True,
            labels=labels,
            doc=f"stock {effect} {name.decode('latin1')}: {kind}, page "
                f"{1 if i < 6 else 2} -- see the Octatrack manual"))
    return tuple(out)


# key -> the words its DSP code occupies, from the payload module map. Only
# the three donors' figures are load-bearing (the region is packed from PLATE
# upward, so each survives while our modules stay under its offset); the rest
# are recorded because the call sites already carried them and dropping them
# on the floor is how a number goes stale unnoticed.
WORDS: dict[str, int] = {}


def _stock(key, name, fx2_id, desc, abbr, fullname, words, doc, char,
           buffer=False):
    WORDS[key] = words
    return Module(
        name=name, key=key, kind=Kind.STOCK, doc=doc,
        menu=MenuEntry(fx2_id=fx2_id, donor_desc=desc, abbr=abbr,
                       fullname=fullname),
        params=_params(desc, fullname.decode("latin1"), key),
        claims=Claims(stock_instance_buffer=buffer) if buffer else None,
        # The letter is what send_probe's layout alphabet and --pick use;
        # every module in the registry needs a distinct one, and R D S W F
        # M N G B are the modules'.
        harness=Harness(layout_char=char, is_server=False),
    )


# Chooser order here is stock's own (docs/PARAM_PAGES.md: FLTR->1 ... DARK->14).
MODULES = (
    _stock("FILTER", "filter", 0x04, 0x400d4772, b"FLTR", b"FILTER", 727,
           "Stock multimode filter, the default FX1 effect. 727 words, "
           "~192 cycles measured.", "L"),
    _stock("EQUALIZER", "equalizer", 0x0c, 0x400d4c28, b"EQ", b"EQUALIZER", 282,
           "Stock two-band parametric EQ.", "E"),
    _stock("DJ EQ", "djeq", 0x0d, 0x400d4dba, b"DJEQ", b"DJ EQUALIZER", 345,
           "Stock three-band DJ kill EQ.", "J"),
    _stock("PHASER", "phaser", 0x10, 0x400d4f4c, b"PHSR", b"PHASER", 207,
           "Stock phaser.", "P"),
    _stock("FLANGER", "flanger", 0x11, 0x400d50de, b"FLNG", b"FLANGER", 289,
           "Stock flanger. Allocates an instance buffer.", "A", buffer=True),
    _stock("CHORUS", "chorus", 0x12, 0x400d5270, b"CHOR", b"CHORUS", 329,
           "Stock chorus. Allocates an instance buffer.", "C", buffer=True),
    _stock("SPATIALIZER", "spatializer", 0x05, 0x400d4904, b"SPAT",
           b"SPATIALIZER", 261,
           "Stock stereo spatializer. Allocates an instance buffer.", "Z",
           buffer=True),
    _stock("COMB FILTER", "comb", 0x13, 0x400d5402, b"COMB", b"COMB FILTER", 277,
           "Stock comb filter. Allocates an instance buffer.", "O", buffer=True),
    _stock("COMPRESSOR", "compressor", 0x18, 0x400d5a4a, b"COMP", b"COMPRESSOR",
           180, "Stock compressor.", "K"),
    _stock("LO-FI", "lofi", 0x1c, 0x400d5d6e, b"LOFI", b"LO-FI", 537,
           "Stock lo-fi (bit/rate reduction, distortion).", "I"),
    _stock("DELAY", "delay", 0x08, 0x400d4a96, b"DEL", b"DELAY", 0,
           "Stock Echo Freeze delay -- runs on the ColdFire, so it costs the "
           "DSP nothing; the row works as on a stock unit. No local render.",
           "Y"),
    # ---- THE THREE REVERBS, listable since 2 Sep 2026 -------------------
    # Their code IS the donor region, so they are the only stock rows whose
    # availability depends on the rest of the selection: the build packs from
    # PLATE upward and nulls a donor id ONLY where words actually landed
    # (build_bus.py), so a light selection keeps the ones it never reached.
    # It refuses a row whose words were taken, which is the guard that makes
    # listing them safe.
    #
    # buffer=True is MEASURED, not assumed: all three read x:>$213 -- the
    # host's bump allocator -- within the first ~25 words of their entry
    # (PLATE 0x01018, SPRING 0x01267, DARK 0x01692; payload A disassembly,
    # 2 Sep 2026), exactly like the four stock effects already flagged. So
    # the ledger refuses them beside any module with fixed Y buffers, on the
    # same grounds and with the same evidence.
    _stock("PLATE REV", "plate", 0x14, 0x400d5594, b"PLTE", b"PLATE REV", 594,
           "Stock plate reverb. Its 594 words are the FIRST of the donor "
           "region, so it is the first row any module of ours takes.",
           "T", buffer=True),
    _stock("SPRING REV", "spring", 0x15, 0x400d5726, b"SPRG", b"SPRING REV",
           1063,
           "Stock spring reverb. 1,063 words, second in the donor region.",
           "U", buffer=True),
    _stock("DARK REV", "dark", 0x16, 0x400d58b8, b"DARK", b"DARK REV", 1067,
           "Stock dark reverb. 1,067 words, last in the donor region -- so "
           "it is the one a small selection is most likely to keep.",
           "V", buffer=True),
)

# The donor region, IN PLACEMENT ORDER. The build packs from PLATE upward,
# so a selection loses them in this order and keeps the tail it never
# reached -- which is why they are listable at all. Nothing here decides
# that; the build reports which survived and the remixer reads its answer
# (state.measure). Kept as a tuple because the ORDER is the meaning.
# ---- where each effect's CODE lives, per payload ---------------------------
# The thirteen DSP effects are laid out CONTIGUOUSLY and every one of them is
# self-contained: no control flow leaves its own span and nothing enters it
# but its own dispatch entry (measured 3 Sep 2026, tools/dsp_reach.py over
# both payloads; the one apparent exception is PLATE's `do #<$6,>$1267`,
# whose operand is a loop END and therefore exclusive). That is what makes
# any of them harvestable for its words, not just the three reverbs.
#
#   payload A  P:0x007d1..0x01fdf     payload B  P:0x00591..0x01d9f
#   6,158 words each, same effects, same sizes, different bases.
#
# ⚠️ DERIVED FROM THE MODULE MAP, not written down. The record SIZES in P
# order are the fingerprint, and PHASER is four records past its own -- its
# true extent runs 41 words past what its record claims (docs/DSP.md s8), so
# it is matched as a group. A firmware whose layout differs fails to match
# and raises rather than handing back plausible addresses.
_P_ORDER = (("FILTER", (727,)), ("SPATIALIZER", (261,)), ("EQUALIZER", (282,)),
            ("PHASER", (157, 6, 6, 6, 32)), ("FLANGER", (289,)),
            ("CHORUS", (329,)), ("PLATE REV", (594,)), ("SPRING REV", (1063,)),
            ("DARK REV", (1067,)), ("COMPRESSOR", (180,)), ("LO-FI", (537,)),
            ("DJ EQ", (345,)), ("COMB FILTER", (277,)))
_spans: dict[str, dict[str, tuple[int, int]]] = {}


def p_spans(payload: str) -> dict[str, tuple[int, int]]:
    """{effect key: (P address, words)} for one payload's DSP effect code.

    The run is found by matching the record-size fingerprint above, so the
    addresses come from the image every time and a layout change is a
    KeyError rather than a wrong write.
    """
    if payload in _spans:
        return _spans[payload]
    import sys as _sys, pathlib as _pl
    _sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[1]))
    import dsp_modmap as dm
    img = dm.IMG.read_bytes()
    va, ln = [(v, l) for t, v, l in dm.PAYLOADS if t == payload][0]
    mods, _b = dm.modules(img, va, ln)
    recs = [(a, c) for sp, a, c, _o in sorted(mods, key=lambda m: m[1])
            if sp == 0]
    want = [n for _k, g in _P_ORDER for n in g]
    sizes = [c for _a, c in recs]
    for i in range(len(sizes) - len(want) + 1):
        if sizes[i:i + len(want)] != want:
            continue
        out, j = {}, i
        for key, group in _P_ORDER:
            out[key] = (recs[j][0], sum(group))
            j += len(group)
        # Contiguity is the property the whole idea rests on -- assert it
        # rather than trusting that adjacent records are adjacent addresses.
        run = sorted(out.values())
        for (a, n), (a2, _n2) in zip(run, run[1:]):
            if a + n != a2:
                raise ValueError(f"payload {payload}: effect code is not "
                                 f"contiguous at P:0x{a:05x}+{n}")
        _spans[payload] = out
        return out
    raise ValueError(f"payload {payload}: no run matches the effect layout")


CONSUMED = ("PLATE REV", "SPRING REV", "DARK REV")


def harvest_order(harvest=CONSUMED) -> tuple[str, ...]:
    """A harvested set in P-ADDRESS order, which is placement order.

    The region is packed from its lowest address upward, so the effect at the
    bottom goes first and the one at the top survives longest. Written down
    for the three reverbs until 3 Sep 2026; sorted from the image now,
    because any run of effects can be harvested and nothing says a remix
    lists them in address order.
    """
    sp = p_spans("A")
    return tuple(sorted(harvest, key=lambda k: sp[k][0]))


def consumed_at(key: int | str, harvest=CONSUMED) -> int:
    """Words our modules may place before this effect's code is overwritten.

    build_bus.py asserts the harvested run is contiguous and places from its
    lowest address, so a drift here cannot pass quietly.
    """
    at = 0
    for c in harvest_order(harvest):
        if c == key:
            return at
        at += WORDS[c]
    raise KeyError(key)


def harvest_neighbours(harvest=CONSUMED) -> frozenset[str]:
    """The effects that could JOIN a harvested run without breaking it.

    A module of ours is one code stream, so the run has to stay contiguous:
    only the effect immediately below the bottom of it and the one
    immediately above the top can be added.
    """
    sp = p_spans("A")
    run = sorted(sp[k] for k in harvest if k in sp)
    if not run:
        return frozenset(sp)
    lo, (ha, hn) = run[0][0], run[-1]
    return frozenset(k for k, (a, n) in sp.items()
                     if a + n == lo or a == ha + hn)


def region_words(harvest=CONSUMED) -> int:
    """The whole placeable region for a harvested set. 2,724 for the three
    reverbs, which is the figure every document quoted as a constant."""
    return sum(WORDS[k] for k in harvest)

# The one stock row with nothing on the DSP to render.
NO_DSP = frozenset({"DELAY"})

BY_KEY = {m.key: m for m in MODULES}
