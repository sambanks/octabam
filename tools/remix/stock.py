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
the workbench shows a stock effect's real page-1/page-2 controls and
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


def fx1_ids() -> frozenset[int]:
    """Effect ids the STOCK FX1 chooser lists, read from the pristine image."""
    global _fx1_ids
    if _fx1_ids is None:
        _fx1_ids = _chooser_ids(FX1_CHOOSER)
    return _fx1_ids


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
        # one gets its page number appended for the workbench and the
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


def _stock(key, name, fx2_id, desc, abbr, fullname, words, doc, char,
           buffer=False):
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
# that; the build reports which survived and the workbench reads its answer
# (state.measure). Kept as a tuple because the ORDER is the meaning.
CONSUMED = ("PLATE REV", "SPRING REV", "DARK REV")

# The one stock row with nothing on the DSP to render.
NO_DSP = frozenset({"DELAY"})

BY_KEY = {m.key: m for m in MODULES}
