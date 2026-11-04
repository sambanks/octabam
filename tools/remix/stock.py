"""The stock FX2 effects, as things a remix can keep in the chooser.

Every octabam image replaces the FX2 chooser wholesale with the remix's
modules. Only three stock effects are consumed -- PLATE, SPRING and DARK
REV, whose 2,724 words of DSP code are the donor region modules pack into;
the other eleven keep their code, descriptor and dispatch entries in every
image. This table lets a remix list them by name, in chooser order, beside
the modules. A stock entry costs nothing: no clone, no placement, no words,
no cycles charged by `make cycles` (FILTER's 192 cycles is the only figure
measured, docs/firmware/CHIP.md); the build writes its list row and cursor
position.

Its knobs are read from the stock descriptor, not declared: names, defaults,
value counts and the enable bitmap come out of the pristine image
(out/raw/section_3_MAIN_OS.bin), so the remixer shows a stock effect's real
controls and `send_probe --set` can drive them by name. When the image is
absent the entry carries no params.

A select's labels come from the firmware: the words a stock select draws
("12dB|24dB", "NONE|HP|LP|BOTH") are printed by the slot's display-formatter
function, so tools/build/stock_labels.py runs each formatter on the emulated
ColdFire for every value and checks the result in as stock_labels.json. The
selftest proves it still matches whenever the emulator is available.

Rendering: a stock effect renders locally the way an insert does, dsp_host
running its code from a dump of the stock image's payload A
(tools/remix/audition.py) with `-alloc 1`, so an effect that takes an
instance buffer gets Y:0x4000 as the hardware gives track 1. DELAY cannot
render: its DSP dispatch is stock's null stub; the Echo Freeze delay runs
on the ColdFire (DMA over SDRAM rings, docs/firmware/COLDFIRE_DELAY.md).

  DELAY (0x08)   works from its row as on a stock unit, costs the DSP
                 nothing, no local render.
  SPATIALIZER, FLANGER, CHORUS, COMB allocate an FX2 instance buffer through
                 the host's bump allocator (X:0x213 at init;
                 docs/firmware/DSP.md section 10) at per-track bases that
                 are the addresses BusVerb and BusDelay hardcode.
                 The ledger refuses them beside any module with fixed Y
                 buffers (Claims.stock_instance_buffer).

Addresses are the descriptors' E addresses from docs/firmware/PARAM_PAGES.md
section 2 (P = E + 0x38 is what the chooser list holds). Words are the
module spans from docs/firmware/DSP.md section 7c, for the index only.
"""

from __future__ import annotations

import pathlib

from remix.schema import Category, Claims, Harness, Keep, Kind, MenuEntry, Module, Param

ROOT = pathlib.Path(__file__).resolve().parents[2]
STOCK_IMAGE = ROOT / "out/raw/section_3_MAIN_OS.bin"
BASE = 0x40000400                      # dsp_modmap.BASE, without the cwd-relative path

# P-relative descriptor offsets (docs/firmware/PARAM_PAGES.md section 5b; the same
# constants tools/build/build_bus.py writes through).
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
# list drops. Noted from an outside report.)
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

# The highest word each buffered stock effect writes above its FX2 slot's base,
# in the four slots of the shared window (Y:0x30000, 0x34000, 0x38000, 0x3c000;
# the allocator's per-track bases, ledger.py). Measured 13 Oct 2026 under the
# port: the `mods` image, all eight tracks THRU with tones on the inputs and
# the same stock effect on every track's FX2, 1,400 frames from transport
# start, `--dsp-dirty`, `--dsp-peek 0:Y:30000,65536` at the end. A non-zero
# word is a write; a zero write and a slot that got no signal are invisible,
# and knobs were at the stamped project's values. The extents match fixed
# buffer sizes (2,048, 3,072, 4,096 words), not a sweep that stopped.
# SLOT_EXTENT[key] = highest offset written (0 = base word).
# SIDECHAIN_COMPRESSOR's cross-core window is the last 0x202 words of the T3 and
# T7 slots (0x33dfe, 0x3bdfe): an effect that fills its slot must stop at
# +0x3DFD (buffer_words <= 15,870) to sit beside it; ledger.py refuses the rest.
SLOT_EXTENT: dict[str, int] = {
    "FLANGER": 0x7FF, "CHORUS": 0xBFD, "SPATIALIZER": 0xA5F, "COMB FILTER": 0xBFF,
    "PLATE REV": 0x37FF, "SPRING REV": 0xFFF, "DARK REV": 0x3DA2,
}
SLOT_BASES = (0x30000, 0x34000, 0x38000, 0x3C000)

# The stock DELAY (0x400031a0, gated on FX2 id 8) looks up two one-pole
# coefficients per track in the table at 0x400d1ce0: the HP pole at
# 0x4000351e (`mvz.w 6(a0),d1 / lsr.l #6` -> entry BASE >> 6, state +20) and
# the LP pole at 0x4000353c (`mvs.w 8(a0),d0 / add.l d1,d0 / asr.l #6` ->
# entry (BASE + WDTH) >> 6, state +24). BASE and WDTH are the staged page-1
# halfwords, the knob << 8, so the LP index reaches (0x7f00 + 0x7f00) >> 6 =
# 1016; the boot init at 0x40002f44 reads entry 1023 (`move.l $400d2cdc.l`)
# directly. The curve has 508 entries and ends at 0x400d24d0; entries
# 508..1023 are zero in 1.40C (0 = the filter open) and other data starts at
# entry 1024, 0x400d2ce0. So the whole zero run 0x400d24d0..0x400d2ce0 is
# read as table data, and a remix that lists DELAY keeps all of it: a module's
# bytes there change the DELAY's output (issue #771, measured under the port at
# entry 508; issue #1007, Zac Kyoti: entries 508 and 764 read on OT DEMO, and
# BASE + WDTH from 128 to 254 reaching 512..1016). Until 4 Nov 2026 only the
# first 16 bytes were kept, on the reading that the index stopped at 511
# (retracted: read from the routine above, against the stock bytes).
DELAY_TABLE_END = 0x400d24d0
DELAY_TABLE_READ_END = 0x400d2ce0    # entry 1024: past the last word DELAY reads
# ... less SCALE QUANTIZER's two pinned units (Tim Hastie's ABI, fixed
# addresses his SYNTH, EUCLID FILL and SCALES call): `qzs` at 0x400d2ca8
# (entries 1010-1011, `jmp qz_scale_mask`) and `qzk` at 0x400d2cb0..0x400d2cdd
# (entries 1012-1023, the paraphonic key mailbox, written at run time). Until
# they move out of the run, DELAY keeps 0x400d24d0..0x400d2ca8 and the rest is
# KNOWN EXPOSURE (inferred, not rendered): with knob words the LP index is
# (BASE + WDTH) * 4, so the reachable entries there are 1012 (qz_pkey[0..3],
# BASE + WDTH = 253) and 1016 (qz_pmask[1], 127/127), and only while CHROMATIC
# keys are held on a synth track; the boot init's entry 1023 is qz_oct's byte
# and three zeros. Other entries need a knob word with low bits (an LFO).
DELAY_KEEP_END = 0x400d2ca8


def _stock(key, name, fx2_id, desc, abbr, fullname, words, doc, char,
           buffer=False, keeps=()):
    WORDS[key] = words
    return Module(
        name=name, key=key, kind=Kind.STOCK, doc=doc, category=Category.STOCK,
        menu=MenuEntry(fx2_id=fx2_id, donor_desc=desc, abbr=abbr,
                       fullname=fullname),
        params=_params(desc, fullname.decode("latin1"), key),
        claims=Claims(stock_instance_buffer=buffer) if buffer else None,
        # The letter is what send_probe's layout alphabet and --pick use;
        # every module in the registry needs a distinct one, and R D S W F
        # M N G B are the modules'.
        harness=Harness(layout_char=char, is_server=False),
        keeps=keeps,
    )


# Chooser order here is stock's own (docs/firmware/PARAM_PAGES.md: FLTR->1 ... DARK->14).
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
           "Y", keeps=(Keep(DELAY_TABLE_END, bytes(DELAY_KEEP_END - DELAY_TABLE_END),
                            "the stock DELAY reads entries 508..1009 of its coefficient "
                            "table (zero: the filter open) as pole coefficients; "
                            "1010..1023 are SCALE QUANTIZER's pinned units (#1007)"),)),
    # Null DSP stub (docs/firmware/DSP.md); FX2-only. Listed so a buffer
    # insert can declare replaces="MULTIBCOMP" without taking DELAY/PHASER.
    _stock("MULTIBCOMP", "multibcomp", 0x19, 0x400d5bdc, b"MBC",
           b"MULTIBCOMP", 0,
           "Stock multiband compressor stub -- null DSP, not in the stock "
           "chooser. Kept here so a module may replace its id.",
           "B"),  # not W: RESONATOR; not H: GATE VERB
    # ---- THE THREE REVERBS, listable -------------------
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
# The thirteen DSP effects are laid out CONTIGUOUSLY, which is what makes
# any of them harvestable for its words, not just the three reverbs. They
# are NOT self-contained: five call routines in another effect's span
# (pinned(), below; measured 3 Oct 2026). "No control flow leaves its own
# span", which this comment said until then, was wrong.
#
#   payload A  P:0x007d1..0x01fdf     payload B  P:0x00591..0x01d9f
#   6,158 words each, same effects, same sizes, different bases.
#
# ⚠️ DERIVED FROM THE MODULE MAP, not written down. The record SIZES in P
# order are the fingerprint, and PHASER is four records past its own -- its
# true extent runs 41 words past what its record claims (docs/firmware/DSP.md s8), so
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
    import toolpath  # noqa: F401  (every tools/ dir on sys.path)
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


def harvested(listed) -> frozenset[str]:
    """Stock effects with DSP code that are on NEITHER chooser.

    ⚠️ HARVESTING IS NOT A SEPARATE GESTURE. Taking an effect off both of the
    unit's menus IS the decision to give it up -- there is no third thing to
    remember and no second key. What it costs is only paid where our code
    actually reaches: an unlisted effect the placer never gets to keeps its
    algorithm and its dispatch, exactly as it always has.

    ⚠️ BOTH choosers. An effect off FX2 but still on FX1 is still wanted, and
    the DSP dispatch is one table shared by the menus -- overwriting its code
    would take it off FX1 too.

    A selected module whose menu entry is `stock_dsp` runs the DSP of the
    stock effect it `replaces` (SIDECHAIN_COMPRESSOR on COMPRESSOR), so that
    effect's code is wanted and counts as listed.
    """
    from remix import registry
    mods = registry.modules()
    keep = set(listed)
    for k in listed:
        m = mods.get(k)
        if m is not None and m.menu is not None and m.menu.stock_dsp and m.menu.replaces:
            keep.add(m.menu.replaces)
    return frozenset(k for k in p_spans("A") if k not in keep)


def regions_of(harvest) -> tuple[tuple[str, ...], ...]:
    """Harvested effects grouped into CONTIGUOUS runs, in address order.

    A module of ours is one code stream, so it must fit inside ONE run --
    but different modules can sit in different runs, which is what
    build_bus.py's placer does. So every harvested effect is placeable
    ground, and the only cost of a gap is fragmentation: a module larger
    than the biggest run has nowhere to go even when the total is ample.

    Until this returned the LARGEST run alone and the rest were
    given up for nothing -- visible in the remixer as "drop two effects,
    free only the reverbs" (Sam, 3 Sep). A stranded run is now placeable.
    """
    sp = p_spans("A")
    runs, cur = [], []
    for a, k in sorted((sp[k][0], k) for k in harvest if k in sp):
        if cur and sp[cur[-1]][0] + sp[cur[-1]][1] != a:
            runs.append(tuple(cur))
            cur = []
        cur.append(k)
    if cur:
        runs.append(tuple(cur))
    return tuple(runs)


def region_of(harvest) -> tuple[str, ...]:
    """Every harvested effect with DSP code, in address order.

    Kept as the name the callers use for "the placeable set". It is no
    longer a single run -- see regions_of() for the grouping the placer
    needs.
    """
    return tuple(k for run in regions_of(harvest) for k in run)


def harvest_order(harvest=CONSUMED) -> tuple[str, ...]:
    """A harvested set in P-ADDRESS order, which is placement order.

    The region is packed from its lowest address upward, so the effect at the
    bottom goes first and the one at the top survives longest. Written down
    for the three reverbs until; sorted from the image now,
    because any run of effects can be harvested and nothing says a remix
    lists them in address order.
    """
    sp = p_spans("A")
    return tuple(sorted(harvest, key=lambda k: sp[k][0]))


def consumed_at(key: int | str, harvest=CONSUMED) -> int:
    """Words our modules may place before this effect's code is overwritten.

    ⚠️ ONLY MEANINGFUL FOR A SINGLE RUN. It walks the harvested set as one
    packed stream; the placer fills each contiguous run
    separately (regions_of), so with a gap this over-counts what precedes an
    effect in the later run. Callers gate on len(regions_of(...)) < 2.
    """
    at = 0
    for c in harvest_order(harvest):
        if c == key:
            return at
        at += WORDS[c]
    raise KeyError(key)


def region_words(harvest=CONSUMED) -> int:
    """The whole placeable region for a harvested set. 2,724 for the three
    reverbs, which is the figure every document quoted as a constant.
    Less the words a kept effect still runs (pinned(); the same counts on
    both payloads)."""
    return (sum(WORDS[k] for k in harvest)
            - sum(n for _a, n, _k, _c in pinned("A", harvest)))

# The one stock row with nothing on the DSP to render.
NO_DSP = frozenset({"DELAY"})

BY_KEY = {m.key: m for m in MODULES}

# ---- the stock curve bank at X:0x4840, and who reads it --------------------
# A 4,096-word data record (32 curves x 128, docs/firmware/TABLES.md) at the
# SAME X address in BOTH payloads -- the exception to the per-payload table
# shift AGENTS.md warns about (measured, dsp_modmap: A at image
# 0x400e7181, B at 0x400fa786, word for word identical) -- and immediately
# above the core's boot clear (P:0x300a6, `do #$7c0` from X:0x4080 ends at
# 0x4840 exactly), so nothing zeroes it and its image bytes are what the DSP
# reads. The build may park the modules' P tables there instead of in the
# donor region (build_bus.py, XTABLE) -- but only while nothing stock that
# reads it survives. WHO READS IT IS DERIVED FROM THE IMAGE, not written
# down: every P record of both payloads is scanned for a raw word inside the
# record's range and each hit is mapped to the effect whose span holds it.
# On the stock image that is DJ EQ alone (36 sites per payload, all
# `x:(r5+$xxx0),reg` reads of curve bases, 0 as a destination; measured
# over tools/build/dsp_disasm_all.py's output), which is why
# TABLES.md's "LO-FI AMPH table" label for the record is not repeated
# here -- LO-FI's code carries no address into it.
#
# ⚠️ STATIC SCAN, NOT A READ-WATCH. A reader that reaches the record through
# a pointer held in DATA is invisible to this: the boot hands the per-core
# staging bases 0x4000/0x4080/0x4400/0x4600/0x4800 out through X:0x205..
# 0x209 (P:0x54..0x90), and a scan cannot see how far they are indexed.
# What bounds it: 0x4800 is the last of them and the boot clear that covers
# them stops at 0x4840. Falsifier: a DSP read-watch on X:0x4840..0x583f
# under the ColdFire port, every stock effect harvested, reporting a hit.
CURVE_BANK = (0x4840, 4096)
_readers: dict[str, tuple[str, ...]] | None = None


def curve_bank_readers() -> dict[str, tuple[str, ...]]:
    """{payload: effect keys whose P code holds a word inside the curve
    bank's range}. A word in P code outside every effect span is reported
    under the key "OUTSIDE-DONOR": code no remix can harvest reads the
    record, and the build must leave it alone."""
    global _readers
    if _readers is not None:
        return _readers
    import sys as _sys, pathlib as _pl
    _sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[1]))
    import toolpath  # noqa: F401
    import dsp_modmap as dm
    img = dm.IMG.read_bytes()
    lo, hi = CURVE_BANK[0], CURVE_BANK[0] + CURVE_BANK[1]
    out = {}
    for tag, va, ln in dm.PAYLOADS:
        sp = p_spans(tag)
        mods, b = dm.modules(img, va, ln)
        hits = set()
        for space, addr, cnt, data in mods:
            if space != 0:
                continue
            for i in range(cnt):
                if lo <= dm.w24(b, data + i * 3) < hi:
                    pc = addr + i
                    hits.add(next((k for k, (a, n) in sp.items()
                                   if a <= pc < a + n), "OUTSIDE-DONOR"))
        out[tag] = tuple(sorted(hits))
    _readers = out
    return out


def curve_bank_record(img: bytes, tag: str):
    """(image byte offset, words) of the curve bank's X record in one
    payload, or None when the payload has no record at exactly that
    address and size."""
    import sys as _sys, pathlib as _pl
    _sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[1]))
    import toolpath  # noqa: F401
    import dsp_modmap as dm
    va, ln = [(v, l) for t, v, l in dm.PAYLOADS if t == tag][0]
    mods, _b = dm.modules(img, va, ln)
    for space, addr, cnt, data in mods:
        if space == 1 and addr == CURVE_BANK[0] and cnt == CURVE_BANK[1]:
            return va - dm.BASE + data, cnt
    return None



# ---- a given-up effect's own X data ------------------------------------------
# The third place for a module's table (build_bus.py XHARVEST), after the
# curve bank and P: an X record of a payload that only one stock effect's
# P code addresses belongs to that effect, and once the effect is on
# neither chooser nothing reads it. SPRING REV owns two such runs per
# payload (measured 5 Oct 2026, this scan, matching Zac Kyoti's 4 Oct
# canary run under his emulator: 0 reads and 0 writes from every other
# DSP effect, a real project playing):
#
#   payload A   X:0x89a4 216 words   X:0x8afc 500 words
#   payload B   X:0x8464 216 words   X:0x85bc 500 words
#
# and the 27-word record after them is read by DARK REV too, so it is not
# exclusive. ⚠️ STATIC SCAN, NOT A READ-WATCH: a record is attributed by
# the P words whose value falls inside it, so a reader that reaches it by
# indexing past another record, or through a pointer held in data, is
# invisible. A record no P word addresses belongs to nobody and is not
# offered. Falsifier: a DSP read-watch on a placed run under the ColdFire
# port, every other effect selected, reporting a hit.
_xreaders: dict[str, list] = {}


def x_records(img: bytes, tag: str) -> list[tuple[int, int, int]]:
    """(X address, words, image byte offset) of every X record of one
    payload, in address order."""
    import sys as _sys, pathlib as _pl
    _sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[1]))
    import toolpath  # noqa: F401
    import dsp_modmap as dm
    va, ln = [(v, l) for t, v, l in dm.PAYLOADS if t == tag][0]
    mods, _b = dm.modules(img, va, ln)
    return sorted((addr, cnt, va - dm.BASE + data)
                  for space, addr, cnt, data in mods if space == 1)


def x_readers(tag: str) -> list[tuple[int, int, dict[str, tuple[int, ...]]]]:
    """(X address, words, {owner: P addresses}) for every X record of one
    payload: which P words hold an address inside the record, keyed by the
    stock effect whose span holds them ("OUTSIDE-DONOR" for code outside
    every effect span)."""
    if tag in _xreaders:
        return _xreaders[tag]
    import sys as _sys, pathlib as _pl
    _sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[1]))
    import toolpath  # noqa: F401
    import dsp_modmap as dm
    img = dm.IMG.read_bytes()
    va, ln = [(v, l) for t, v, l in dm.PAYLOADS if t == tag][0]
    mods, b = dm.modules(img, va, ln)
    sp = p_spans(tag)
    recs = x_records(img, tag)
    starts = [r[0] for r in recs]
    import bisect
    hits: list[dict[str, list[int]]] = [{} for _ in recs]
    for space, addr, cnt, data in mods:
        if space != 0:
            continue
        for i in range(cnt):
            w = dm.w24(b, data + i * 3)
            j = bisect.bisect_right(starts, w) - 1
            if j < 0 or w >= recs[j][0] + recs[j][1]:
                continue
            pc = addr + i
            k = next((k for k, (a, n) in sp.items() if a <= pc < a + n),
                     "OUTSIDE-DONOR")
            hits[j].setdefault(k, []).append(pc)
    out = [(a, n, {k: tuple(v) for k, v in h.items()})
           for (a, n, _o), h in zip(recs, hits)]
    _xreaders[tag] = out
    return out


def x_exclusive_runs(tag: str, given_up, pinned_words=frozenset()
                     ) -> list[tuple[int, int, str]]:
    """(X address, words, owner) for each run of contiguous X records that
    only one effect in `given_up` addresses, none of whose readers is in
    `pinned_words` (a harvested word a kept effect still runs), in address
    order. Adjacent records of one owner join into one run."""
    given_up = set(given_up)
    runs: list[list] = []
    for a, n, rd in x_readers(tag):
        ok = (len(rd) == 1 and next(iter(rd)) in given_up
              and not any(pc in pinned_words for pcs in rd.values() for pc in pcs))
        if not ok:
            continue
        owner = next(iter(rd))
        if runs and runs[-1][0] + runs[-1][1] == a and runs[-1][2] == owner:
            runs[-1][1] += n
        else:
            runs.append([a, n, owner])
    return [tuple(r) for r in runs]

# ---- words a KEPT effect reaches inside a HARVESTED one ---------------------
# The thirteen spans are not self-contained. Stock effects call routines that
# sit in another effect's span (measured on both payloads, 3 Oct 2026, Zac
# Kyoti's report of DARK REV dying under REPITCH revs 10-13):
#
#   caller -> routine in    payload A             payload B
#   DARK   -> SPRING REV    P:0x1586..0x15a8      P:0x1346..0x1368
#   PLATE  -> DARK REV      P:0x1a47..0x1aa3      P:0x1807..0x1863
#   PLATE, SPRING, DARK, DJ EQ, and DARK's routine above -> FILTER
#                           P:0x09ad..0x09b8      P:0x076d..0x0778
#   SPATIALIZER -> FILTER   P:0x09c6..0x09d4      P:0x0786..0x0794
#
# so a harvest that takes the callee and keeps a caller would place module
# code over words the kept effect still runs. pinned() is what the placer
# leaves alone: every harvested word reached by control flow from a kept
# effect's two dispatch entries, from the interrupt vectors or from the
# bootstraps. It is a walk over the vendored disassembler's decode, so it
# follows jsr/bsr/jmp/bra/Bcc/Jcc/do targets and fall-through and nothing
# held in a register: a `jsr (rN)` into another span, or a P table read
# across spans, is invisible to it. Falsifier: a DSP PC-watch under the port
# with a remix that harvests a pinned routine's owner, reporting a PC in a
# placed word.
_XTAB = {"A": 0x400e2345, "B": 0x400f5a10}   # init[32] then proc[32], 24-bit words
_DIS = ROOT / "vendor/dsp56300/build/source/disassemble/dsp56kDisassemble"
_reach: dict[str, dict[str, frozenset[int]]] = {}


def _reached(payload: str) -> dict[str, frozenset[int]]:
    """{effect key, or "PLATFORM": every P word its code reaches}."""
    if payload in _reach:
        return _reach[payload]
    import re as _re, subprocess as _sp, sys as _sys, tempfile as _tf
    _sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
    import toolpath  # noqa: F401
    import dsp_modmap as dm
    img = dm.IMG.read_bytes()
    va, ln = [(v, l) for t, v, l in dm.PAYLOADS if t == payload][0]
    mods, b = dm.modules(img, va, ln)
    insn: dict[int, tuple[str, int]] = {}     # address -> (text, words)
    tmp = pathlib.Path(_tf.mkdtemp(prefix="stockreach"))
    line_re = _re.compile(r"^([0-9a-f]{6}):\s+(.*?)\s*;\s*([0-9a-f]{6})( [0-9a-f]{6})?\s*$")
    for space, addr, cnt, data in mods:
        if space != 0:
            continue
        (tmp / "m.bin").write_bytes(b[data:data + cnt * 3])
        out = _sp.run([str(_DIS), "-in", str(tmp / "m.bin"), "-pc", f"{addr:x}",
                       "-le"], capture_output=True, text=True, check=True).stdout
        for line in out.splitlines():
            m = line_re.match(line)
            if m:
                insn[int(m[1], 16)] = (m[2], 2 if m[4] else 1)
    if not insn:
        raise RuntimeError(f"payload {payload}: the disassembler decoded "
                           f"nothing ({_DIS})")
    stop = _re.compile(r"^(jmp|bra|rts|rti|stop)\b")
    target = _re.compile(r"func_([0-9a-f]+)|>\$([0-9a-f]+)")

    def walk(seeds):
        seen, work = set(), list(seeds)
        while work:
            a = work.pop()
            if a in seen or a not in insn:
                continue
            seen.add(a)
            text, n = insn[a]
            # func_ is the disassembler's name for a branch/call target;
            # `>$` is only a target as a `do` loop's end (a move's `>$` is
            # data).
            for m in target.finditer(text):
                if m[1] or text.startswith("do"):
                    work.append(int(m[1] or m[2], 16))
            if not stop.match(text):
                work.append(a + n)
        return frozenset(w for a in seen for w in range(a, a + insn[a][1]))

    def rd(i):
        o = _XTAB[payload] - dm.BASE + i * 3
        return img[o] | img[o + 1] << 8 | img[o + 2] << 16

    out = {}
    for mod in MODULES:
        if mod.key in p_spans(payload):
            fid = mod.menu.fx2_id
            out[mod.key] = walk((rd(fid), rd(32 + fid)))
    out["PLATFORM"] = walk([a for a in range(0x40) if a in insn]
                           + [a for a in (0x30000, 0x38000) if a in insn])
    _reach[payload] = out
    return out


def pinned(payload: str, harvest) -> tuple[tuple[int, int, str, str], ...]:
    """(P address, words, owner, callers) for each run of harvested words
    that code outside the harvest still reaches. The placer skips them."""
    sp = p_spans(payload)
    harvest = set(harvest)
    owner = {w: k for k in harvest if k in sp
             for w in range(sp[k][0], sp[k][0] + sp[k][1])}
    by_word: dict[int, set[str]] = {}
    for caller, words in _reached(payload).items():
        if caller in harvest:
            continue
        for w in words:
            if w in owner:
                by_word.setdefault(w, set()).add(caller)
    runs: list[list] = []
    for w in sorted(by_word):
        if runs and runs[-1][0] + runs[-1][1] == w and runs[-1][2] == owner[w]:
            runs[-1][1] += 1
            runs[-1][3] |= by_word[w]
        else:
            runs.append([w, 1, owner[w], set(by_word[w])])
    return tuple((a, n, k, ", ".join(sorted(c))) for a, n, k, c in runs)
