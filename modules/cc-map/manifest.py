"""CC MAP -- MIDI CC numbers stock ignores, mapped to parameters stock CC
cannot reach. Today: CC 102-107 -> the FX2 effect's page-2 slots 6-11, CC
108-111, 14, 15 -> the FX1 effect's (62-67 and 68-73 until 1 Nov 2026,
issue #981: they held the sustain and hold pedals). README.md lists the
free CC numbers.

Stock incoming CC reaches page 1 only (CC 16-45; the handler admits
cc-16 < 30, docs/firmware/MIDI.md appendix A). The MIDI dispatch table entry
0x400d6474[0xB] (the CC vector) is repointed from the stock handler
0x4000e79c to the cave. The cave reads the CC number; anything outside its
blocks tail-calls CC_NEXT (the stock handler) with the argument intact. Inside a block it rebuilds the
channel->track map, gates on AUDIO CC IN, and on every audio track whose
trig channel matches makes the stores of that page's editor: FX2 page 2
as 0x4003aab2 (Part +0x8f084, shadow 0x100a51d2, lane +0x38), FX1 page 2
as 0x4003abe4 (Part +0x8f07e, shadow 0x100a51cc, lane +0x32), plus the four
dirty flags. FX2 writes only on BusDelay/BusVerb, clamped by the cave's
count tables; FX1 writes on any id but NONE (0), clamped by the FX1
descriptor's min/count. Selects are clamped to their count: an over-count
stored value is used as an index and stalls the sequencer.

Source is the truth: the build links cc_map.s into the DRAM runtime;
`legacy_bytes()` is the hand-assembled oracle the linked source is
compared against (Linked.reference, and
tools/verify/verify_cc_map.py, which also proves the write for all eight
tracks in the emulator against the firmware editor)."""

import pathlib

import hashlib

from remix.schema import Gate, Category, Evidence, Level, Kind, Linked, Module, SymbolRef
from remix.midi_cc import refuse_stateful

# The CC numbers, slot 6..11 order. cc_map.s's CAVE decodes them (102..111
# -> cc-102, 14/15 -> 10/11), CC FEEDBACK's cf_map sends them, and the two
# gates check both against these tuples. Every one is undefined in the MIDI
# spec; none is in midi_cc.STATEFUL.
FX2_CCS = refuse_stateful("CC MAP FX2 page 2", (102, 103, 104, 105, 106, 107))
FX1_CCS = refuse_stateful("CC MAP FX1 page 2", (108, 109, 110, 111, 14, 15))

# Page-2 clamp counts, slots 6..11: selects carry their count, knobs 128.
# Must match modules/busverb and modules/busdelay.
VERB_COUNTS = bytes((3, 128, 128, 128, 128, 128))  # MODE, TONE, DIFF, GATE, DLY, TIME (slot 9 was SHFT, count 4, until 15 Sep 2026)
DLY_COUNTS = bytes((3, 128, 128, 4, 128, 128))  # MODE, SCTR, DENS, SIZE(select), PTCH, TIME

# The CC dispatch vector (status>>4 == 0xB) and its stock target.
DISPATCH_CC = 0x400d64a0
STOCK_CC = 0x4000e79c
STOCK_RTS = 0x40027e1a           # a bare `rts` in stock (the tail of 0x40027e00)

# The hand-assembled form of cc_map.s, with 0x40bad000/4 placeholders
# for its two count tables; legacy_bytes(addr) patches them in. The oracle
# the linked source is compared against every build.
CODE = bytes.fromhex(
    "206f0004700010280001726690817209b28064180680000000587201b2806506720ad081"
    "60064ef94000e79c4fefffe448d704fc28002448263946104cf44eb9400018547a001a2a"
    "000202850000007f4a398000004967287000101202800000000f41f946c7febe2e300c00"
    "7c007001eda8c0876702611252867008b0866eee4cd704fc4fef001c4e757206b2846f00"
    "0114203946c824567200123980000003263c000018b24c031000d0812040d1fc0008ed88"
    "d1c6700010107206b28067107207b28067024e7543f940bad000600643f940bad0047200"
    "1231480053812405b4816f022401203946c824567200123980000003263c000018b24c03"
    "1000d0817200d0812040d1fc0008f0842206761e4c031000d1c1d1c410822040d1fc0008"
    "f084d1c1d1c41082220676484c03100041f980000810d1c1d1fc00000038d1c410822606"
    "721e4c013000220092b946c82456d2830681100a51d22041d1c410827200123980000003"
    "7601e3ab207946c824562248d3fc000950481211828312811239100b145e828313c1100b"
    "145ed1fc0009b3327201208123c1100f8598610000ea4e75203946c82456720012398000"
    "0003263c000018b24c031000d0812040d1fc0008ed80d1c672001210670000ba43f9400d"
    "5f5822711c00260441f13c002228009a2628006ad28353812405b4836c022403b4816f02"
    "24012206761e4c03100026045d832040d1c1d1c3d1fc0008f07e1082224093f946c82456"
    "d3c1d3c3d3fc100a51cc128272001239800000037601e3ab207946c824562248d3fc0009"
    "50481211828312811239100b145e828313c1100b145ed1fc0009b3327201208123c1100f"
    "8598220676484c03100026045d8341f980000810d1c1d1fc00000032d1c3108261000028"
    "4e754feffff048d70470244428067a001a39800000034eb940027e1a4cd704704fef0010"
    "4e754feffff048d704702a045d85244528067a001a39800000034eb940027e1a4cd70470"
    "4fef00104e75"
)

VCOUNT_MARK = bytes.fromhex("40bad000")
DCOUNT_MARK = bytes.fromhex("40bad004")


def legacy_bytes(addr):
    """CODE at `addr` with its two placeholders patched to the appended
    tables: the oracle for the linked source. The build never writes these
    bytes itself."""
    code = bytearray(CODE)
    vcount_at = addr + len(code)
    dcount_at = vcount_at + len(VERB_COUNTS)
    for mark, target in ((VCOUNT_MARK, vcount_at), (DCOUNT_MARK, dcount_at)):
        i = code.find(mark)
        assert i >= 0, "placeholder %s missing" % mark.hex()
        assert code.find(mark, i + 4) < 0, "placeholder %s not unique" % mark.hex()
        code[i:i + 4] = target.to_bytes(4, "big")
    return bytes(code) + VERB_COUNTS + DLY_COUNTS


# Where the oracle links the hand-assembled form: the address the ROM cave
# last landed at (bottleservice, 2f89c186).
ORACLE_AT = 0x400d26bc


MODULE = Module(
    name="cc-map",
    key="CC MAP",
    kind=Kind.CF_PATCH,
    category=Category.MIDI_USB, author="sambanks", author_url="https://github.com/sambanks",
    evidence=(Evidence(Level.UNIT, unit="MKII", who="sambanks", date="2026-09-13",
        note="(image 96, 13 Sep 2026), on CC 62-73; the 1 Nov 2026 numbers are not flashed yet"),),
    doc="MIDI CC 102-107 drive the FX2 engine's page-2 slots 6-11; CC 108-111, 14 and 15 the FX1 station's.",
    # A DRAM unit (8 Oct 2026; a floating ROM cave until then): the CC
    # dispatch entry points at its entry symbol.
    linked=(Linked("ccmap", "modules/cc-map/cc_map.s", dram=True,
                   reference=(ORACLE_AT, hashlib.sha256(legacy_bytes(ORACLE_AT)).hexdigest()),
                   # Where other CCs go: stock's handler.
                   # CC_MODEDEF2 / CC_MODEDEF1: a stock `rts` unless MODE DEFAULTS is in
                   # the image, whose unit exports them.
                   defsyms=(("CC_NEXT", STOCK_CC), ("CC_MODEDEF2", STOCK_RTS),
                            ("CC_MODEDEF1", STOCK_RTS))),),
    symbol_refs=(SymbolRef(DISPATCH_CC, STOCK_CC, "ccmap", "ccm_entry",
                           "MIDI dispatch: the CC vector (CC 102-107 reach FX2 page 2, CC 108-111, 14, 15 FX1 page 2)"),),
    gates=(Gate('tools/verify/verify_cc_map.py', remix_arg=False, venv=True),),
)
