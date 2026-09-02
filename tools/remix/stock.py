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

Two of them are special:

  DELAY (0x08)   the Echo Freeze delay. Its DSP dispatch is stock's null
                 stub -- a passthrough -- because the delay itself runs on
                 the ColdFire (DMA over SDRAM rings, docs/EXTERNAL.md). It
                 works from this row exactly as it does on a stock unit.
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

from remix.schema import Claims, Kind, MenuEntry, Module


def _stock(key, name, fx2_id, desc, abbr, fullname, words, doc, buffer=False):
    return Module(
        name=name, key=key, kind=Kind.STOCK, doc=doc,
        menu=MenuEntry(fx2_id=fx2_id, donor_desc=desc, abbr=abbr,
                       fullname=fullname),
        claims=Claims(stock_instance_buffer=buffer) if buffer else None,
    )


# Chooser order here is stock's own (docs/PARAM_PAGES.md: FLTR->1 ... DARK->14).
MODULES = (
    _stock("FILTER", "filter", 0x04, 0x400d4772, b"FLTR", b"FILTER", 727,
           "Stock multimode filter, the default FX1 effect. 727 words, "
           "~192 cycles measured."),
    _stock("EQUALIZER", "equalizer", 0x0c, 0x400d4c28, b"EQ", b"EQUALIZER", 282,
           "Stock two-band parametric EQ."),
    _stock("DJ EQ", "djeq", 0x0d, 0x400d4dba, b"DJEQ", b"DJ EQUALIZER", 345,
           "Stock three-band DJ kill EQ."),
    _stock("PHASER", "phaser", 0x10, 0x400d4f4c, b"PHSR", b"PHASER", 207,
           "Stock phaser."),
    _stock("FLANGER", "flanger", 0x11, 0x400d50de, b"FLNG", b"FLANGER", 289,
           "Stock flanger. Allocates an instance buffer.", buffer=True),
    _stock("CHORUS", "chorus", 0x12, 0x400d5270, b"CHOR", b"CHORUS", 329,
           "Stock chorus. Allocates an instance buffer.", buffer=True),
    _stock("SPATIALIZER", "spatializer", 0x05, 0x400d4904, b"SPAT",
           b"SPATIALIZER", 261,
           "Stock stereo spatializer. Allocates an instance buffer.",
           buffer=True),
    _stock("COMB FILTER", "comb", 0x13, 0x400d5402, b"COMB", b"COMB FILTER", 277,
           "Stock comb filter. Allocates an instance buffer.", buffer=True),
    _stock("COMPRESSOR", "compressor", 0x18, 0x400d5a4a, b"COMP", b"COMPRESSOR",
           180, "Stock compressor."),
    _stock("LO-FI", "lofi", 0x1c, 0x400d5d6e, b"LOFI", b"LO-FI", 537,
           "Stock lo-fi (bit/rate reduction, distortion)."),
    _stock("DELAY", "delay", 0x08, 0x400d4a96, b"DEL", b"DELAY", 0,
           "Stock Echo Freeze delay -- runs on the ColdFire, so it costs the "
           "DSP nothing; the row works as on a stock unit."),
)

# What every remix consumes, whether it lists anything or not: the three
# reverbs whose code IS the donor region. Named here so the composer can
# say so rather than leaving it to be inferred from a manifest comment.
CONSUMED = ("PLATE REV", "SPRING REV", "DARK REV")

BY_KEY = {m.key: m for m in MODULES}
