"""CX OSC -- Buchla-flavoured complex oscillator (marker-less machine list).

Choose CX OSC in FUNC+SRC / SELECT MACHINE TYPE (FLEX + Part signature "CX",1).
Mono only; stock LFO page (no VOIC/CHRD). PLAYBACK: PTCH RATO INDX FOLD SYMM DEC
(HOLD at 127; SYMM bipolar half-wave skew, 64 = even).

Machine list adapted from timhastie/octatrick-modules v2.15 SYNTH MACHINE
(MIT / Modwerk chooser lineage). Conflicts with SYNTH MACHINE and
BLACKPYRAMIDS_303. Beside ANALOG BD or OCTA303 it shares the machine list
through HOOKS (machine_rows): its row follows theirs.
"""

import os

from remix.schema import (
    Apply, CavePatch, Category, Detour, Gate, Kind, Linked, Module, Option,
    Proof, Setting, Store, SymbolRef,
)

_HERE = os.path.relpath(os.path.dirname(os.path.realpath(__file__)))

# PLACE: DRAM (default) links page.s into the platform runtime and leaves the
# stock DELAY curve table's last words alone (issue #771 / Keep on 0x400d24d0).
# CAVE is the pinned ROM form at PAGE_AT; refused where DELAY is listed.
PAGE_AT = 0x400d24d0
PAGE_LEN = 1780
PG_RESOLVE_AT = 16
RESOLVER_HOOK = 0x40031ece
RESOLVER_STOCK = bytes.fromhex("20300c00" "6002")
PLACES = ("CAVE", "DRAM")


def engine_abi():
    with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "engine_abi.inc"),
              encoding="utf-8") as f:
        return f.read()


def remix_include(modules, remix=None):
    return ".set HAVE_SYDRUM, 0\n" + engine_abi()


def machine_limits():
    with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "machine_limits.inc"),
              encoding="utf-8") as f:
        return f.read()


def _cxosc_place(modules) -> str:
    seq = modules.values() if isinstance(modules, dict) else modules
    for m in seq:
        if getattr(m, "name", None) == "cxosc":
            return dict(getattr(m, "build_values", {}) or {}).get("PLACE", "DRAM")
    return "DRAM"


def _hooks_inc(modules):
    """modules/hooks's flags and, beside another machine, CX OSC's place in the
    machine_rows chain (its row; the next machine's routines)."""
    from remix import hooks_flags
    if _cxosc_place(modules) != "DRAM" and "OCTA303" in modules:
        raise ValueError("CX OSC: PLACE=CAVE beside OCTA303 -- both take the PLAYBACK page "
                         "resolver 0x40031ece and the cave's jump there cannot be chained; "
                         "build with PLACE=DRAM")
    return hooks_flags.inc("CX OSC", modules)


def poly_include(modules, remix=None):
    return _hooks_inc(modules)


def machine_include(modules, remix=None):
    text = remix_include(modules, remix) + machine_limits() + _hooks_inc(modules)
    # CAVE: page.s is not linked; machine.s's .long fm_descriptor needs the
    # absolute cave base. DRAM: the Linked page unit exports the symbol.
    if _cxosc_place(modules) != "DRAM":
        text += f"\n        .set    fm_descriptor, {PAGE_AT:#x}\n"
    return text


KIND_TABLE_STATIC = 0x400d6434
KIND_TABLE_FLEX = 0x400d6438
KIND_TABLE_FLEX_START = 0x400d6458
FLEX_START = 0x4000f450
STOCK_RENDERER = bytes.fromhex("40004008")

# Keep MIDI / amp / envelope hooks from the v2.9 engine port
LFO_DEPTH_HOOK = 0x40003ca4
LFO_DEPTH_HOOK2 = 0x4000d03e
LFO_DEPTH_STOCK = bytes.fromhex("71722a12" "43f04a00")
LFO_PAGE_HOOK = 0x40031e62
LFO_PAGE_STOCK = bytes.fromhex("203c400d37f6" "606c")
MIDI_MAP_HOOK = 0x4000e746
MIDI_MAP_STOCK = bytes.fromhex("721d" "2b812c00")
MIDI_OFF_HOOK = 0x4000dfd4
MIDI_OFF_STOCK = bytes.fromhex("7310" "7113" "b081" "661c")
MIDI_GATE_HOOK = 0x4000e452
MIDI_GATE_STOCK = bytes.fromhex("2006" "5580" "7405" "b480")
RETRIG_HOOK = 0x4000c634
RETRIG_STOCK = bytes.fromhex("226f0072" "10309800")
STOP_HOOK = 0x4000b2c8
STOP_STOCK = bytes.fromhex("42b9" "46c80350")
KILL_HOOK = 0x4000685c
KILL_STOCK = bytes.fromhex("4200" "13808800")
REL_HOOK = 0x4000b51a
REL_STOCK = bytes.fromhex("266f0072" "2031bc00")
MIDI_OFFGATE_HOOK = 0x4000de10
MIDI_OFFGATE_STOCK = bytes.fromhex("5580" "7605" "b680")
MIDI_REC_HOOK = 0x400625e0
MIDI_REC_STOCK = bytes.fromhex("202a0004" "23c046c7e956")
MIDI_TRIG_HOOK = 0x4006262a
MIDI_TRIG_STOCK = bytes.fromhex("752a0002" "2042" "41f02c00")
AMP_STAGE_HOOK = 0x40059d56
AMP_STAGE_STOCK = bytes.fromhex("4879400d3988")
AMP_DRAW1_HOOK = 0x4003685a
AMP_DRAW1_STOCK = bytes.fromhex("49f9400d39c2" "47f9400d3a6a")
AMP_DRAW2_HOOK = 0x400368ac
AMP_DRAW2_STOCK = bytes.fromhex("2f39400d3b16" "2f39400d3b12")
AMP_DRAW3_HOOK = 0x40036946
AMP_DRAW3_STOCK = AMP_DRAW2_STOCK
AMP_EDIT_HOOK = 0x4003ae40
AMP_EDIT_STOCK = bytes.fromhex("0680400d3988" "2240" "2069012a")
AMP_LANE_HOOK = 0x4003af0a
AMP_LANE_STOCK = bytes.fromhex("41f98000083c" "11820800")
OCT_HOOK = 0x40051fce
OCT_STOCK = bytes.fromhex("4ab9400bebae")
ASSIGN_HOOK = 0x400795ba
ASSIGN_STOCK = bytes.fromhex("d1fc0008f04a" "1081")
MACHWIN_HOOK = 0x40079816
MACHWIN_STOCK = bytes.fromhex("d1fc0008eda2" "7710")
LISTWIN_HOOK = 0x4005a848
LISTWIN_STOCK = bytes.fromhex("d1fc0008eda2" "7910")
LOADSEL_HOOK = 0x40022686
LOADSEL_STOCK = bytes.fromhex("4eb940013a08")

# Machine list (v2.15)
FM_NAME_HOOK = 0x400334d8
FM_NAME_STOCK = bytes.fromhex("2f02" "222f0008")
FM_NAMES_HOOK = 0x4003c928
FM_NAMES_STOCK = bytes.fromhex("4bf9400a78c8")
FM_NAME_A_HOOK = 0x4003d718
FM_NAME_A_STOCK = bytes.fromhex("41f9400a78c8")
FM_SETUP_ROW_HOOK = 0x4003c980
FM_SETUP_ROW_STOCK = bytes.fromhex("7110" "4fef0018")
FM_CHOOSER_ROW_HOOK = 0x400786c8
FM_CHOOSER_ROW_STOCK = bytes.fromhex("7110" "b480" "662e")
FM_SETUP_OPEN_HOOK = 0x400585dc
FM_SETUP_OPEN_STOCK = bytes.fromhex("1610" "7903" "4879400bb704")
FM_CHOOSER_OPEN_HOOK = 0x40078886
FM_CHOOSER_OPEN_STOCK = bytes.fromhex("7110" "2f00" "4879460e7386")
FM_EDIT6_HOOK = 0x4003a52e
FM_EDIT6_STOCK = bytes.fromhex("2002" "e788" "d482" "9082")
FM_DRAW6_HOOK = 0x4003cd98
FM_DRAW6_STOCK = bytes.fromhex("2e06" "e78f" "dc86" "9e86")
FM_TICK_HOOK = 0x4005221e
FM_TICK_STOCK = bytes.fromhex("4ebaff1c" "4eb94007e940")
FM_SRC_COMMIT_HOOK = 0x4005a616
FM_SRC_COMMIT_STOCK = bytes.fromhex("2239460d5c30")
FM_SRC_COMMIT2_HOOK = 0x4005a850
FM_SRC_COMMIT2_STOCK = bytes.fromhex("2239460d5c30")
FM_VALIDATE_HOOK = 0x40002318
FM_VALIDATE_STOCK = bytes.fromhex("4fefffa0" "48d77cfc")
FM_SOURCE_HOOK = 0x4000d514
FM_SOURCE_STOCK = bytes.fromhex("205c" "26c8" "48780010")
ML_WIN_COUNT_HOOK = 0x40079248
ML_WIN_COUNT_STOCK = bytes.fromhex("48780005" "48780006")
ML_SRC_COUNT_HOOK = 0x400585fa
ML_SRC_COUNT_STOCK = bytes.fromhex("48780005" "48780005")
ML_NAME_BOUND_HOOK = 0x4003c950
ML_NAME_BOUND_STOCK = bytes.fromhex("7204" "b282" "6504")
ML_DRAW_BOUND_HOOK = 0x40078678
ML_DRAW_BOUND_STOCK = bytes.fromhex("7004" "b082" "6d24" "2f02" "2043" "4e90")
ML_HI_BOUND_HOOK = 0x400786ce
ML_HI_BOUND_STOCK = bytes.fromhex("7004" "b082" "6d28")
ML_CUR_BOUND_HOOK = 0x40079904
ML_CUR_BOUND_STOCK = bytes.fromhex("7604" "b684" "6c00fec2")
ML_CLAMP_HOOKS = (0x40078c22, 0x40078cb0, 0x40078d2e, 0x40078dee, 0x40078e7c)
ML_CLAMP_STOCK = bytes.fromhex("7205" "b280" "6c02" "7005")
PAGE_STORE_HOOK = 0x40027e98
PAGE_STORE_STOCK = bytes.fromhex("162a0013" "7d03" "1e2a0012")
TRACK_PASTE_HOOK = 0x4002b99e
TRACK_PASTE_STOCK = bytes.fromhex("4879460c8122" "4ebafcae")
TRACK_UNDO_HOOK = 0x4002b962
TRACK_UNDO_STOCK = bytes.fromhex("4879460bf218" "4ebafcea")
PART_PASTE_HOOK = 0x40029b8a
PART_PASTE_STOCK = bytes.fromhex("4879460c8122" "4ebafeba")
PART_UNDO_HOOK = 0x40029b54
PART_UNDO_STOCK = bytes.fromhex("4879460bf218" "4ebafef0")
PREVIEW_HOOK = 0x40096d22
PREVIEW_STOCK = bytes.fromhex("7710" "23c346105424" "10bc0001")

PINNED_PAGE = bytes.fromhex(
    "2079400d64382068fffc43fa00604ed020300c000c80400d31ae66000048243c"
    "000018b24c012800d48920422803c8fc001ed1c4d1fc0008edbc7bd00c850000"
    "4358660000207ba800020c8500000001660000122079400d64382068fffc43fa"
    "000c4e904ef940031ed6000000090009400d259c001c001e400d25a300610001"
    "400d25c2006a0004400d25c4009a0004400d25c800ca0018400d25cc00fe0008"
    "400d25e4010a0008400d25ec012a0004400d25c401360004400d25c4018e0004"
    "400d25f4ffff0000000000004358204f5343005241544f0000494e4458000046"
    "4f4c44000053594d4d00004644424b00000001000000000000000080400d25f8"
    "400d263e4003c1784003c1784003c1784003c178400d2784400d278a400d2790"
    "400d279655551551202f000804800000004041fa03c56e00000841f9400b465d"
    "2f002f082f2f000c4eb940013a084fef000c4e75202f000804800000004041fa"
    "039d6e00ffdc41fa039a6000ffd42f02202f000c41fa03c27200b03018006700"
    "002852810c81000000106500ffee223c000003c04c010000727f4c4100000680"
    "000000406000000a41fa036e71f01a002200e0880281000000ff74644c021000"
    "e0896700003e0c81000000326700001c2f012f00487a030a2f2f00144eb94001"
    "3a084fef0010600000302f00487a02fa2f2f00104eb940013a084fef000c6000"
    "00182f004879400b465d2f2f00104eb940013a084fef000c241f4e752f02202f"
    "000c6700007c22004c001000203c000007d04c010000068000001f80223c0000"
    "3f014c4100000c80000003e86400001c2f004879400b465d2f2f00104eb94001"
    "3a084fef000c60000048223c000003e824004c41200272644c4100002202e789"
    "d282d28290812f002f02487a02612f2f00144eb940013a084fef001060000012"
    "487a02522f2f000c4eb940013a08508f241f4e7570006000001470016000000e"
    "7002600000087003600000024fefffd448d77cfc2e002f2f00482f2f00482f2f"
    "00482f2f00482f2f00482f2f00482f2f00484eb9400479b44fef001c202f0040"
    "08000001660001902c2f003c4a87670000125387670000185387670000b26000"
    "00c841fa02c0610001786000012641fa03806100016c220670034c001000707f"
    "4c401001740b948170087201610001742406700a4c002000707f4c4020026700"
    "0012700672016100015a700a72016100015224060482000000146f0000227008"
    "4c002000706b4c40200267000012700472016100012e700c7201610001262406"
    "0482000000386f0000aa70064c00200070474c4020026700009a700272016100"
    "0102700e7201610000fa6000008641fa0258610000cc4a866700007841fa028e"
    "610000ce6000006c41fa02c6610000b270017201740b610000ca2a3c00007fff"
    "4a86670000122a06700d4c005000707f4c4050055485780b7e0224075382e98a"
    "4c4520020c82000000106f000004741041fa00d475b028002642200722022404"
    "61000080280b52870c870000000f6f00ffca202f0040080000006700001841fa"
    "0140701022100a81fff0000020c153806c00fff2202f00345e802f00202f0034"
    "52802f002f2f0050487a00be4eb9400128a84fef00104cd77cfc4fef002c4e75"
    "43fa00fe701022d853806c00fffa4e7543fa00ee70102218839953806c00fff8"
    "4e7541fa00dc41f00c00263c80000000e2ab8790e28b5281b4816c00fff64e75"
    "25642e253032640025642e350025642e25647300484f4c44002b2564002b2564"
    "6300256463000b09070605040303020201010101010101000040008000c00100"
    "01030140016a018001c00200020302800300038004000403000811191a22272a"
    "333b3c4c5d6e7f7f000000110000000d00000001400d2a70400d2a2cfff80000"
    "fff80000fff80000fff80000fff80000fff80000fff80000fff80000fff80000"
    "fff80000fff80000fff80000fff80000fff80000fff80000fff80000fff80000"
    "0000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000003f80000020800000208000003f80000004000000"
    "04000000150000000e000000040000003f80000020800000208000003f800000"
    "000000000000000000000000000000000000000000000000000000003f800000"
    "20800000208000002080000020800000208000003f8000000000000000000000"
    "000000000000000000000000000000000000000007f000000e10000004100000"
    "0010000000100000001000000010000000100000001000000010000004100000"
    "07f0000000000000000000000000000000000000800000008000000080000000"
    "8000000080000000800000008000000080000000800000008000000080000000"
    "8000000080000000800000008000000000000000"
)
assert len(PINNED_PAGE) == PAGE_LEN, len(PINNED_PAGE)
assert PINNED_PAGE[PG_RESOLVE_AT:PG_RESOLVE_AT + 4] == bytes.fromhex("20300c00")


def emit_page(addr: int):
    assert addr == PAGE_AT, "the page cave is pinned"
    return b"", ((RESOLVER_HOOK, RESOLVER_STOCK,
                  bytes.fromhex("4ef9") + (addr + PG_RESOLVE_AT).to_bytes(4, "big")),)


def _variant(values):
    """PLACE -> the page's placement (DRAM default avoids DELAY Keep #771)."""
    if values["PLACE"] != "DRAM":
        return {}
    return {
        "linked": MODULE.linked + (Linked("page", os.path.join(_HERE, "page.s"),
                                          cpu="5475", dram=True),),
        "cf_patches": (),
        "detours": MODULE.detours + (Detour(
            RESOLVER_HOOK, RESOLVER_STOCK, "page", "pg_resolve",
            "PLAYBACK page resolver: CX OSC track reads PTCH/RATO/INDX/FOLD/SYMM/DEC "
            "(DRAM form; leaves the stock DELAY table tail alone)", kind="jmp"),),
    }


MODULE = Module(
    name="cxosc",
    key="CX OSC",
    kind=Kind.CF_PATCH,
    category=Category.MACHINES,
    author="ilia-murzinov",
    author_url="https://github.com/ilia-murzinov",
    proof=Proof.HARDWARE,
    proof_note=(
        "MKII BUILD CS @ 052bb14d (author, cxosc-core): machine select; each PLAYBACK "
        "knob then (PTCH RATO INDX FOLD SYMM FDBK); FUNC RATO snaps; MIDI note-on; "
        "STOP/START; Part change. Port only since: Tim 2.20 AMP snap, DEC (HOLD@127) "
        "replacing FDBK, bipolar SYMM half-wave skew (64=even) + icon; verify_cxosc + "
        "make check REMIX=cxosc"
    ),
    doc="CX OSC in the machine list (no marker file): PTCH RATO INDX FOLD SYMM DEC (HOLD@127; SYMM half-wave skew 64=even), mono, stock LFOs. Local fork of FM SYNTH.",
    conflicts=(
        ("SYNTH MACHINE", "both own the FLEX/STATIC kind-table renderers, page cave 0x400d24d0, and machine-list sites"),
        ("BLACKPYRAMIDS_303", "shares ColdFire ROM hooks (e.g. MIDI note-on 0x4000e746) — build refuses the pair"),
    ),
    gates=(
        Gate("tools/verify/verify_cxosc.py", remix_arg=False, venv=True, stage="image"),
    ),
    linked=(
        Linked("poly", os.path.join(_HERE, "poly.s"), cpu="5475", dram=True, include=poly_include),
        Linked("fmmachine", os.path.join(_HERE, "machine.s"), cpu="5475", dram=True, include=machine_include),
    ),
    symbol_refs=(
        SymbolRef(KIND_TABLE_FLEX, int.from_bytes(STOCK_RENDERER, "big"), "poly", "sy_render",
                  "kind table FLEX renderer -> cxosc sy_render"),
        SymbolRef(KIND_TABLE_STATIC, int.from_bytes(STOCK_RENDERER, "big"), "poly", "sy_render",
                  "kind table STATIC renderer -> sy_render (sample glide)"),
        SymbolRef(KIND_TABLE_FLEX_START, FLEX_START, "poly", "po_fmstart",
                  "FLEX START -> po_fmstart (sample-free when CX OSC chosen)"),
    ),
    detours=(
        # LFO page/depth NOT stolen -- stock LFO 1/2/3 on a CX OSC track
        Detour(MIDI_MAP_HOOK, MIDI_MAP_STOCK, "poly", "po_mon",
               "MIDI IN note-on", kind="jmp"),
        Detour(MIDI_OFF_HOOK, MIDI_OFF_STOCK, "poly", "po_moff",
               "MIDI IN note-off", kind="jmp", pad_to=8),
        Detour(REL_HOOK, REL_STOCK, "poly", "po_rel",
               "AMP-release consumer", kind="jmp", pad_to=8),
        Detour(STOP_HOOK, STOP_STOCK, "poly", "po_stop",
               "STOP ends engine voices", kind="jmp"),
        Detour(RETRIG_HOOK, RETRIG_STOCK, "poly", "po_retrig",
               "sequencer START rewrite", kind="jmp", pad_to=8),
        Detour(KILL_HOOK, KILL_STOCK, "poly", "po_kill",
               "voice kill", kind="jmp"),
        Detour(MIDI_GATE_HOOK, MIDI_GATE_STOCK, "poly", "po_mgate",
               "MIDI note gate", kind="jmp", pad_to=8),
        Detour(MIDI_OFFGATE_HOOK, MIDI_OFFGATE_STOCK, "poly", "po_mogate",
               "MIDI note-off gate", kind="jmp"),
        Detour(MIDI_REC_HOOK, MIDI_REC_STOCK, "poly", "po_mrec",
               "MIDI live recorder", kind="jmp", pad_to=10),
        Detour(MIDI_TRIG_HOOK, MIDI_TRIG_STOCK, "poly", "po_mtrig",
               "MIDI with trig held", kind="jmp", pad_to=8),
        Detour(OCT_HOOK, OCT_STOCK, "poly", "po_octave",
               "FUNC+UP/DOWN octave", kind="jmp"),
        Detour(AMP_STAGE_HOOK, AMP_STAGE_STOCK, "poly", "po_ampstage",
               "AMP SETUP LEG staging", kind="jmp"),
        Detour(AMP_DRAW1_HOOK, AMP_DRAW1_STOCK, "poly", "po_ampdraw1",
               "AMP SETUP drawer names", kind="jmp", pad_to=12),
        Detour(AMP_DRAW2_HOOK, AMP_DRAW2_STOCK, "poly", "po_ampdraw2",
               "AMP SETUP drawer nibbles", kind="jmp", pad_to=12),
        Detour(AMP_DRAW3_HOOK, AMP_DRAW3_STOCK, "poly", "po_ampdraw3",
               "AMP SETUP drawer nibbles", kind="jmp", pad_to=12),
        Detour(AMP_EDIT_HOOK, AMP_EDIT_STOCK, "poly", "po_ampedit",
               "AMP page-2 LEG editor", kind="jmp", pad_to=12),
        Detour(AMP_LANE_HOOK, AMP_LANE_STOCK, "poly", "po_amplane",
               "AMP LEG live-lane suppress", kind="jmp", pad_to=10),
        Detour(ASSIGN_HOOK, ASSIGN_STOCK, "poly", "po_assign",
               "slot assign became-CXOSC", kind="jmp", pad_to=8),
        Detour(MACHWIN_HOOK, MACHWIN_STOCK, "fmmachine", "fm_main_commit",
               "machine window commit (CX OSC row) then po_machwin via fallthrough? -- shared site",
               kind="jmp", pad_to=8),
        # NOTE: v2.15 shares MACHWIN: fm_main_commit then calls into stock/po_machwin.
        # Check machine.s -- fm_main_commit is the detour target; po_machwin may be chained.
        Detour(LISTWIN_HOOK, LISTWIN_STOCK, "poly", "po_machlist",
               "sample-list window", kind="jmp", pad_to=8),
        Detour(LOADSEL_HOOK, LOADSEL_STOCK, "poly", "po_loadsel",
               "file browser", kind="jsr"),
        Detour(FM_NAME_HOOK, FM_NAME_STOCK, "fmmachine", "fm_machine_name",
               "machine-name formatter", kind="jmp"),
        Detour(FM_NAMES_HOOK, FM_NAMES_STOCK, "fmmachine", "fm_src_names",
               "SRC SETUP name table (stock lea abs -> our table; never jmp)",
               kind="lea"),
        Detour(FM_NAME_A_HOOK, FM_NAME_A_STOCK, "fmmachine", "fm_name_a",
               "track machine name", kind="jmp"),
        Detour(FM_SETUP_ROW_HOOK, FM_SETUP_ROW_STOCK, "fmmachine", "fm_setup_row",
               "SRC SETUP row highlight", kind="jmp"),
        Detour(FM_CHOOSER_ROW_HOOK, FM_CHOOSER_ROW_STOCK, "fmmachine", "fm_chooser_row",
               "chooser row highlight", kind="jmp", pad_to=6),
        Detour(FM_SETUP_OPEN_HOOK, FM_SETUP_OPEN_STOCK, "fmmachine", "fm_setup_open",
               "SRC SETUP open", kind="jmp", pad_to=10),
        Detour(FM_CHOOSER_OPEN_HOOK, FM_CHOOSER_OPEN_STOCK, "fmmachine", "fm_chooser_open",
               "chooser open", kind="jmp", pad_to=10),
        Detour(FM_EDIT6_HOOK, FM_EDIT6_STOCK, "fmmachine", "fm_setup_edit6",
               "SRC SETUP editor row*6", kind="jmp", pad_to=8),
        Detour(FM_DRAW6_HOOK, FM_DRAW6_STOCK, "fmmachine", "fm_setup_draw6",
               "SRC SETUP drawer row*6", kind="jmp", pad_to=8),
        Detour(FM_TICK_HOOK, FM_TICK_STOCK, "fmmachine", "fm_tick",
               "UI tick name table fill", kind="jmp", pad_to=10),
        Detour(FM_SRC_COMMIT_HOOK, FM_SRC_COMMIT_STOCK, "fmmachine", "fm_src_commit",
               "SRC SETUP commit", kind="jmp"),
        Detour(FM_SRC_COMMIT2_HOOK, FM_SRC_COMMIT2_STOCK, "fmmachine", "fm_src_commit2",
               "SRC SETUP commit path 2", kind="jmp"),
        Detour(FM_VALIDATE_HOOK, FM_VALIDATE_STOCK, "fmmachine", "fm_validate",
               "Part validator prologue", kind="jmp"),
        Detour(FM_SOURCE_HOOK, FM_SOURCE_STOCK, "poly", "po_fmsource",
               "frame builder supplier", kind="jmp", pad_to=8),
        Detour(ML_WIN_COUNT_HOOK, ML_WIN_COUNT_STOCK, "fmmachine", "ml_win_count",
               "machine window row count", kind="jmp"),
        Detour(ML_SRC_COUNT_HOOK, ML_SRC_COUNT_STOCK, "fmmachine", "ml_src_count",
               "SRC SETUP row count", kind="jmp"),
        Detour(ML_NAME_BOUND_HOOK, ML_NAME_BOUND_STOCK, "fmmachine", "ml_name_bound",
               "SRC SETUP name bound", kind="jmp", pad_to=6),
        Detour(ML_DRAW_BOUND_HOOK, ML_DRAW_BOUND_STOCK, "fmmachine", "ml_draw_bound",
               "chooser draw bound", kind="jmp", pad_to=12),
        Detour(ML_HI_BOUND_HOOK, ML_HI_BOUND_STOCK, "fmmachine", "ml_hi_bound",
               "chooser highlight bound", kind="jmp", pad_to=6),
        Detour(ML_CUR_BOUND_HOOK, ML_CUR_BOUND_STOCK, "fmmachine", "ml_cur_bound",
               "chooser cursor bound", kind="jmp", pad_to=8),
        *[Detour(h, ML_CLAMP_STOCK, "fmmachine", f"ml_clamp{i+1}",
                 "chooser row clamp", kind="jmp", pad_to=8)
          for i, h in enumerate(ML_CLAMP_HOOKS)],
        Detour(PAGE_STORE_HOOK, PAGE_STORE_STOCK, "fmmachine", "fm_page_store",
               "SRC page store guard", kind="jmp", pad_to=10),
        Detour(TRACK_PASTE_HOOK, TRACK_PASTE_STOCK, "fmmachine", "fm_track_paste",
               "track paste guard", kind="jmp", pad_to=10),
        Detour(TRACK_UNDO_HOOK, TRACK_UNDO_STOCK, "fmmachine", "fm_track_undo",
               "track undo guard", kind="jmp", pad_to=10),
        Detour(PART_PASTE_HOOK, PART_PASTE_STOCK, "fmmachine", "fm_part_paste",
               "Part paste guard", kind="jmp", pad_to=10),
        Detour(PART_UNDO_HOOK, PART_UNDO_STOCK, "fmmachine", "fm_part_undo",
               "Part undo guard", kind="jmp", pad_to=10),
        Detour(PREVIEW_HOOK, PREVIEW_STOCK, "fmmachine", "fm_preview",
               "FLEX preview guard", kind="jmp", pad_to=10),
    ),
    cf_patches=(
        CavePatch(
            label="cxosc page",
            cave_addr=PAGE_AT,
            pinned=PINNED_PAGE,
            source=os.path.join(_HERE, "page.s"),
            emit=emit_page,
            reference=lambda addr: PINNED_PAGE,
            report_note=" (resolver -> pg_resolve +16: CX OSC PLAYBACK; fm_descriptor at cave base)",
        ),
    ),
    store=Store("ilia.cxosc"),
    variant=_variant,
    settings=(Setting(1, "PLACE", Option(*PLACES), default="DRAM", apply=Apply.BUILD,
                      doc="DRAM: page in the platform runtime (leaves stock DELAY table tail alone); "
                          "CAVE: pinned ROM cave at 0x400d24d0, refused where DELAY is listed"),),
)
