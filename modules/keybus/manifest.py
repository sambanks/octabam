"""KEYBUS -- every track's key level, each block, in eight shared words any DSP reader on either core can read.

One DSP hook at the dispatcher's per-track site (payload A P:$4a7, payload B P:$29c, `move x:>$208,r6`, the
site SIDECHAIN_COMPRESSOR's sctap also hooks): the peak of |(L + R) / 2| over the track's 16-frame input block,
stored at X:$37F60 + track (0..7) in the shared window. CHARACTER's KEY reads it for T1..T8 (modules/character).
17 words of code, one copy for both cores; no ColdFire part, no menu, no settings.

Beside SIDECHAIN_COMPRESSOR loaded on demand, SC KEYBUS BRIDGE shares the site (SC's resident stub runs sctap,
then this hook). Beside SIDECHAIN_COMPRESSOR in its per-core form there is no bridge (schema.DspOverride needs a
demand module), so the build refuses the two hooks at one site.
"""
from remix.schema import Category, Claims, DspHook, DspRange, DspSection, Gate, Kind, Module, Proof

KEY_WORDS = 0x37F60                     # X, shared window: track t's key word at KEY_WORDS + t
SITE = {"A": 0x4A7, "B": 0x29C}
SITE_STOCK = (0x66F000, 0x000208)       # move x:>$208,r6, the same on both payloads

MODULE = Module(
    name="keybus",
    key="KEYBUS",
    kind=Kind.HYBRID,
    category=Category.REFERENCE, author="sambanks", author_url="https://github.com/sambanks",
    proof=Proof.CHECK, proof_note="",
    doc="Every track's key level (block peak of |mono|) each block, in eight shared words for DSP readers on either core.",
    claims=Claims(dsp_ranges=(
        DspRange("x", KEY_WORDS, 8, "every track's key word, track t at +t, rewritten each block"),
    )),
    dsp=DspSection(
        asm="modules/keybus/keybus.asm",
        priority=25,
        payloads=frozenset({"A", "B"}),
        hooks=(DspHook(SITE, SITE_STOCK, "kbus_tap",
                       "dispatcher, per track: the block's key level to X:$37F60 + track"),),
    ),
    gates=(Gate("tools/verify/verify_keybus.py"),),
)
