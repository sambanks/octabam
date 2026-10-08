#!/usr/bin/env python3
"""
Verify the built image's FX2/FX1 chooser tables against the chooser
mechanism as decompiled from the firmware:

  FUN_40052474 (id-store, fires when the cursor is confirmed on a new
  position):
      pcVar11 = &Part[track].fx2_id                    ; (bank*0x18b2 + track
                                                         ; + _base + 0x8ed88)
      if (*(int*)FX2_LIST[cursor] != *pcVar11) {
          *pcVar11 = (char)*(int*)FX2_LIST[cursor]      ; store the id byte
          ...
          puVar3 = FX2_IDS[ *(int*)FX2_LIST[cursor] ]   ; INDEPENDENT lookup,
                                                         ; must agree with
                                                         ; FX2_LIST[cursor]
          ... apply puVar3's page-1/page-2 DEFAULT bytes, stage the page ...
      }

  FUN_4005996c (menu-open, one-time init branch, DAT_400bc48c == 0):
      ppuVar5 = &FX2_LIST; iVar4 = -1;
      do { iVar4++; puVar1 = *ppuVar5++; } while (puVar1 != 0);   ; length
      FUN_4007ec60(..., 7, iVar4)                                ; UI bound
      FUN_4007edb0(..., *(int*)(ID2POS + fx2_id*4))               ; cursor seed
      FUN_400326d4(FX2_IDS[fx2_id], ...)                          ; stage page

Both are data computations over the five tables; this script replicates
that logic in Python against the built image rather than driving the
emulator through the real function (the init branch also calls the widget
setup pointers that draw the menu UI). It also checks every cloned
descriptor's formatter against its value count and the strings the build
writes against their fields.
"""
import hashlib
import os, pathlib, subprocess, sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401  (every tools/ dir on sys.path)
from dsp_modmap import BASE  # noqa: E402
from remix import registry as _reg  # noqa: E402
from remix import rig as _rig  # noqa: E402
from remix.schema import NO_FALLBACK as _NO_FALLBACK  # noqa: E402

STOCK = pathlib.Path("out/raw/section_3_MAIN_OS.bin")
BUILT = pathlib.Path("out/mainos_bus.bin")

FX2_IDS = 0x400d5fdc
# Where the list lives: NEW_LIST (0x400d6b00, seven rows) or the LONG list
# at the tail of the zero run (0x400d7bbc, up to 32) when a remix keeps
# stock rows. Read from the image's own list refs rather than assumed.
LIST_CAVES = (0x400d6b00, 0x400d7bbc)
CHOOSER_ROWS = 7                        # the screen's rows; longer lists scroll
ID2POS = 0x400d6150
LIST_REFS = [0x400375f4, 0x40052496, 0x40059a42]
FX1_ID_LOOKUP = 0x400d5f58
FX1_CHOOSER = 0x400d6060
# 11 entries + the NUL terminator = 12 words; 0x400d6090 is FX2_LIST, so a
# wider window reads that table as FX1 damage.
FX1_CHOOSER_LEN = 0x30
FX1_ID2POS = 0x400d60d0                 # FX1's own cursor-row table
FX1_LIST_REFS = [0x40037990, 0x40052706, 0x40059bd2]
FX1_NONE = 0x400d4618
FX1_ROWCOUNT_AT = 0x40059be6            # FX1's viewport literal

REMIX = _reg.remix(os.environ.get("REMIX"))
_MODS = _reg.modules()
NO_WIDGET = 0x4005692e          # build_bus.NO_WIDGET: a stock rts, past a host page's slots
# A HIDDEN module (schema.Remix.hidden) is carried but takes no chooser row,
# so it is not in the order the list, the positions or the row count are
# checked against. Its own gate is tools/verify/verify_hidden.py, which checks the
# things this file would otherwise have to invert: no row, blank names, and
# the writer still reaching it.
_ORDER = [k for k in REMIX.modules
          if _MODS[k].menu is not None and k not in REMIX.hidden]
EXPECT = {k: (_MODS[k].menu.fx2_id, i) for i, k in enumerate(_ORDER)}
# WITH NO FALLBACK the firmware's own NONE goes back at row 0, as a stock
# unit has it, so the list is one longer than the modules and every position
# shifts by one.
_NONE_ROW = 1 if REMIX.fallback == _NO_FALLBACK else 0
if _NONE_ROW:
    EXPECT = {k: (i, p + 1) for k, (i, p) in EXPECT.items()}
N_REAL = len(EXPECT) + _NONE_ROW
# STOCK rows (tools/remix/stock.py): the build writes their list row and
# cursor position only, so what is checked for them is that everything
# else -- descriptor bytes, FX2_IDS entry -- is byte-identical to stock.
STOCK_KEYS = {k for k in _ORDER if _MODS[k].is_stock}
FALLBACK = REMIX.fallback               # id 0 and every absent id alias here
ROWCOUNT_AT = 0x40059a56
NONE_ID = 0x00                          # aliased to SEND

# P-relative offsets (PARAM_PAGES.md section 5b: record base is P = E+0x38)
P_PARAM_NAMES = 0x16
P_PENABLE_LO = 0x18e                    # params 0..7, one nibble each
P_PENABLE_HI = 0x18a                    # params 8..11
ACTIVE_PARAMS = {k: _MODS[k].active_params for k in _ORDER
                 if k not in STOCK_KEYS}
LINKED_PARAMS = {k: _MODS[k].linked_params for k in _ORDER
                 if k not in STOCK_KEYS}
# Param(active=None) on a stock_dsp clone: the slot's nibble is the donor's
# (schema.Module.inherited_enable), checked against the pristine donor.
INHERITED = {k: _MODS[k].inherited_enable for k in _ORDER
             if k not in STOCK_KEYS}


def _nibble(lo, hi, i):
    return ((lo if i < 8 else hi) >> (4 * (i if i < 8 else i - 8))) & 0xf
# a host page's link elements stop at its last drawn slot (build_bus.py)
for _k, _n in REMIX.host_slots:
    if _k in LINKED_PARAMS:
        LINKED_PARAMS[_k] = tuple(i for i in LINKED_PARAMS[_k] if i < _n)


# P-relative: the per-parameter value-COUNT array and the defaults array.
# tools/build/build_bus.py writes both; PARAM_PAGES.md section 5b has the record map.
P_COUNTS = 0x9a
P_DEFAULTS = 0x5e

# The per-parameter DISPLAY FORMATTER arrays. A cloned descriptor inherits the
# DONOR's formatter for every slot, and the formatter overrides the value count
# entirely when deciding how a value is DRAWN -- so a slot can carry a perfectly
# correct count, default and enable bit and still render as something else, or
# as nothing at all.
P_FMT1, P_FMT2, P_FMT3 = 0x0ca, 0x0fa, 0x12a
# The enumerated-selector pair, taken from stock CHORUS.TAPS (count 5). Stock
# uses all-zeros for a plain numeric knob.
STEPPED_FMT = (0x4003c718, 0x40047254)
# The ColdFire cave region (docs/firmware/PARAM_PAGES.md section 7): clones, the tempo
# caves and the mode-select label formatters all live in here and nowhere else.
CAVE_LO, CAVE_HI = 0x400d6b20, 0x400d7c3c
OVF_LO, OVF_HI = 0x400d24d0, 0x400d2ce0
ISL_LO, ISL_HI = 0x400c45b0, 0x400c4702    # the 338 B zero run (Spectrum's SHPE formatter)
REG_FMT = {(_c.registers_formatter.module, _c.registers_formatter.slot):
           (_c.pinned, _c.registers_formatter.offset)
           for _k in REMIX.modules for _c in _MODS[_k].cf_patches
           if _c.registers_formatter is not None}
# DRAM label formatters (Linked.registers_formatter): A is the unit's symbol
# in the platform runtime the same build linked (out/platform/runtime).
RUNTIME_SYMS: dict = {}
REG_DRAM = {(_u.registers_formatter.module, _u.registers_formatter.slot):
            (_u.registers_formatter.symbol, _u.registers_formatter.offset)
            for _k in REMIX.modules for _u in _MODS[_k].linked
            if _u.registers_formatter is not None}


def _runtime_syms() -> dict:
    elf = pathlib.Path("out/platform/runtime/runtime.elf")
    if not elf.exists():
        return {}
    out = subprocess.run(["m68k-elf-nm", str(elf)], capture_output=True, text=True).stdout
    return {f[2]: int(f[0], 16) for f in (l.split() for l in out.splitlines()) if len(f) == 3}


def _built_for(img: bytes) -> str | None:
    """Which remix wrote BUILT, from the sidecar build_bus leaves beside it --
    None when there is no sidecar or it describes different bytes (an image
    restored by hand, or a build older than the sidecar)."""
    side = BUILT.with_suffix(".remix")
    if not side.exists():
        return None
    parts = side.read_text().split()
    if len(parts) != 2 or parts[1] != hashlib.sha256(img).hexdigest():
        return None
    return parts[0]


def main():
    stock = STOCK.read_bytes()
    img = BUILT.read_bytes()
    global RUNTIME_SYMS
    RUNTIME_SYMS = _runtime_syms()
    # ⚠️ THE IMAGE ON DISK IS WHATEVER BUILT LAST, and this check reads its
    # expectations from REMIX. Checking one remix's image against another's
    # list prints dozens of FAILs whose "garbage" entries are the other
    # remix's descriptor text -- say the one true thing instead.
    built = _built_for(img)
    if built is not None and built != REMIX.name:
        print(f"  [FAIL] {BUILT} was built for remix '{built}', but REMIX="
              f"{REMIX.name} -- run `make bus REMIX={REMIX.name}` first "
              f"(or `make check REMIX={REMIX.name}`, which does)")
        sys.exit(1)

    def rd32(buf, a):
        i = a - BASE
        return int.from_bytes(buf[i:i + 4], "big")

    fails = []

    def check(cond, msg):
        print(("  ok  " if cond else "  FAIL"), msg)
        if not cond:
            fails.append(msg)

    print("=== FUN_40052474 / FUN_4005996c both embed 0x400d6090 as an "
          "absolute operand at these 3 sites (GhidraChooser.java found them "
          "inside those two functions); confirm all three now read the SAME "
          "relocated list, in one of the two list caves ===")
    FX2_LIST_LIVE = rd32(img, LIST_REFS[0])
    check(FX2_LIST_LIVE in LIST_CAVES,
          f"list ref 0x{LIST_REFS[0]:08x} points into a list cave "
          f"(0x{FX2_LIST_LIVE:08x})")
    for r in LIST_REFS:
        check(rd32(img, r) == FX2_LIST_LIVE,
              f"list-ref operand at 0x{r:08x} == 0x{FX2_LIST_LIVE:08x}")

    print("\n=== FUN_4005996c's list-length scan: walk FX2_LIST to the "
          "terminator, exactly as the decompiled do/while does ===")
    a, length = FX2_LIST_LIVE, -1
    positions = []
    while True:
        length += 1
        v = rd32(img, a)
        positions.append(v)
        if v == 0:
            break
        a += 4

    print("\n=== list is exactly the three real entries, and the chooser's "
          "viewport was shrunk to match so no row can read past the "
          "terminator (the hardware-test-1 garbage) ===")
    check(length == N_REAL, f"list length == {N_REAL} (got {length})")
    rows = int.from_bytes(img[ROWCOUNT_AT - BASE:ROWCOUNT_AT - BASE + 2], "big")
    want_rows = min(CHOOSER_ROWS, N_REAL)
    check(rows == want_rows, f"viewport row count == {want_rows} (got {rows})"
          + (" -- the list scrolls" if N_REAL > CHOOSER_ROWS else ""))

    print(f"\n=== id 0 (a fresh/unassigned track) is aliased to the remix's "
          f"fallback ({FALLBACK}), so every track degrades to it by default ===")
    # ⚠️ A REMIX WITH NO BUS NAMES NO MODULE AS ITS FALLBACK (schema.NO_FALLBACK)
    # and gets the firmware's own NONE instead, restored at list row 0. This
    # script assumed a module every time and died with a KeyError on `warped`
    # and every other no-bus remix -- a traceback, not a failed check, so
    # `REMIX=warped make verify` reported nothing at all. Found.
    # A HIDDEN fallback is not in EXPECT (it has no chooser row), and its
    # cursor parks at 0 because there is no row to point at. Its descriptor
    # is still cloned and its id still resolves to it, which is the half
    # that matters -- an unassigned track has to dispatch to real code.
    if FALLBACK == _NO_FALLBACK:
        fb_p, fb_pos = FX1_NONE, 0
    elif FALLBACK in REMIX.hidden:
        fb_p, fb_pos = rd32(img, FX2_IDS + _MODS[FALLBACK].menu.fx2_id * 4), 0
    else:
        fb_p, fb_pos = rd32(img, FX2_IDS + EXPECT[FALLBACK][0] * 4), \
            EXPECT[FALLBACK][1]
    check(rd32(img, FX2_IDS + NONE_ID * 4) == fb_p,
          f"FX2_IDS[0x00] == {FALLBACK}'s descriptor (0x{fb_p:08x})")
    check(rd32(img, ID2POS + NONE_ID * 4) == fb_pos,
          f"ID2POS[0x00] == {FALLBACK}'s position ({fb_pos})")

    print("\n=== FUN_40052474: list[cursor] and FUN_4005996c/FUN_400326d4's "
          "independent FX2_IDS[id] lookup must resolve to the SAME "
          "descriptor pointer, for every position ===")
    for name, (fx_id, pos) in EXPECT.items():
        list_ptr = rd32(img, FX2_LIST_LIVE + pos * 4)
        ids_ptr = rd32(img, FX2_IDS + fx_id * 4)
        check(list_ptr == ids_ptr and list_ptr != 0,
              f"{name}: FX2_LIST[{pos}]=0x{list_ptr:08x} == "
              f"FX2_IDS[0x{fx_id:02x}]=0x{ids_ptr:08x}")

        # *(int*)FX2_LIST[cursor] -- the descriptor's own id WORD, P+0. Low
        # byte is what FUN_40052474 actually stores into Part[track].fx2_id.
        id_word = rd32(img, list_ptr)
        check((id_word & 0xff) == fx_id,
              f"{name}: low byte of *FX2_LIST[{pos}] == 0x{fx_id:02x} "
              f"(id word 0x{id_word:08x})")

    print("\n=== FUN_4005996c's cursor-seed: ID2POS[id] must equal the "
          "position that id actually sits at in the list ===")
    for name, (fx_id, pos) in EXPECT.items():
        seeded = rd32(img, ID2POS + fx_id * 4)
        check(seeded == pos, f"{name}: ID2POS[0x{fx_id:02x}] == {pos} (got {seeded})")

    print("\n=== per-parameter ENABLE BITMAP (P+0x18e params 0-7, P+0x18a "
          "params 8-11, one nibble each, bit 0 = draw this knob). Both "
          "FUN_400326d4 and FUN_40037590 gate on it via FUN_400a6994 -- all "
          "zeros means 'this effect has no parameters', which is what the "
          "first two hardware flashes shipped by copying the descriptor from "
          "E instead of P and losing the record's last 0x38 bytes ===")
    for name, (fx_id, pos) in EXPECT.items():
        P = rd32(img, FX2_IDS + fx_id * 4)
        if name in STOCK_KEYS:
            # Nothing of a stock row is ours to check but its untouchedness.
            check(P == rd32(stock, FX2_IDS + fx_id * 4),
                  f"{name}: FX2_IDS[0x{fx_id:02x}] is stock's own descriptor")
            check(img[P - BASE:P - BASE + 0x192] == stock[P - BASE:P - BASE + 0x192],
                  f"{name}: stock descriptor bytes at P=0x{P:08x} unchanged")
            continue
        lo, hi = rd32(img, P + P_PENABLE_LO), rd32(img, P + P_PENABLE_HI)
        got = {i for i in range(12)
               if ((lo if i < 8 else hi) >> (4 * (i if i < 8 else i - 8))) & 1}
        want = set(ACTIVE_PARAMS[name])
        wantl = set(LINKED_PARAMS[name])
        _inh = INHERITED[name]
        if _inh:
            _dP = _MODS[name].menu.donor_desc + 0x38
            _dlo = rd32(stock, _dP + P_PENABLE_LO)
            _dhi = rd32(stock, _dP + P_PENABLE_HI)
            for i in _inh:
                _dn, _gn = _nibble(_dlo, _dhi, i), _nibble(lo, hi, i)
                check(_gn == _dn,
                      f"{name}: p{i} (active=None, stock_dsp) keeps the donor's "
                      f"enable nibble 0x{_dn:x} (got 0x{_gn:x})")
                want |= {i} if _dn & 1 else set()
                wantl |= {i} if _dn & 2 else set()
        check(got == want,
              f"{name}: enabled knobs {sorted(got)} == expected {sorted(want)} "
              f"(lo=0x{lo:08x} hi=0x{hi:08x})")
        # bit 1 = the link element to the left neighbour (PARAM_PAGES.md 3b):
        # exactly the manifest's, and no other bit anywhere in a nibble
        linked = {i for i in range(12)
                  if ((lo if i < 8 else hi) >> (4 * (i if i < 8 else i - 8))) & 2}
        check(linked == wantl,
              f"{name}: linked knobs {sorted(linked)} == expected {sorted(wantl)}")
        stray = {i for i in range(12)
                 if i not in _inh
                 and ((lo if i < 8 else hi) >> (4 * (i if i < 8 else i - 8))) & 0xc}
        check(not stray, f"{name}: no nibble carries bits 2/3 (stock's PLAYBACK-only flags) {sorted(stray)}")
        # a knob that is enabled but unnamed would render as a blank row
        for i in sorted(got):
            a = P + P_PARAM_NAMES + i * 6
            nm = img[a - BASE:a - BASE + 6].split(b"\0")[0]
            check(bool(nm), f"{name}: enabled knob p{i} has a non-empty name "
                            f"({nm.decode('latin1')!r})")

        # DEFAULT MUST LIE INSIDE THE VALUE COUNT. This invariant did not
        # exist and a build that violated it shipped: page-2 value counts were
        # narrowed (slot 7 -> 5) without narrowing the matching defaults (slot
        # 7 was 64), and an out-of-range default is used as an index. On
        # hardware the sequencer ran two steps and stopped, tracks rendered as
        # the wrong effect, and there was no audio. It was harmless right up
        # until those slots were ENABLED, which is why it survived earlier
        # builds -- nothing read a disabled slot.
        for i in sorted(got):
            cnt = rd32(img, P + P_COUNTS + i * 4)
            dflt = img[P + P_DEFAULTS + i - BASE]
            check(cnt > 0 and dflt < cnt,
                  f"{name}: p{i} default {dflt} is inside its value count "
                  f"{cnt}")

        _host_n = dict(REMIX.host_slots).get(name)
        for i in sorted(got):
            cnt = rd32(img, P + P_COUNTS + i * 4)
            f1 = rd32(img, P + P_FMT1 + i * 4)
            f2 = rd32(img, P + P_FMT2 + i * 4)
            f3 = rd32(img, P + P_FMT3 + i * 4)
            if _host_n is not None and i >= _host_n:
                # past a host page's slots: no widget (a bare rts), 0x12a 0;
                # A stays whatever the slot's own rules made it
                check(f2 == NO_WIDGET and f3 == 0,
                      f"{name}: p{i} is past the host page's {_host_n} slots, so its "
                      f"widget is the rts 0x{NO_WIDGET:08x} and 0x12a is 0 "
                      f"(got 0x{f2:08x}/0x{f3:08x})")
                continue
            _pr = _MODS[name].params[i] if i < len(_MODS[name].params) else None
            if _pr is not None and _pr.has_raw_words:
                # Param.formatter_word/widget_word/word_12a: the declaration
                # is the rule. An int is checked exactly; a (unit, symbol)
                # word is non-zero and not the donor's; None is the donor's.
                _dP = _MODS[name].menu.donor_desc + 0x38
                for _lbl, _off, _w, _got in (("A", P_FMT1, _pr.formatter_word, f1),
                                              ("B", P_FMT2, _pr.widget_word, f2),
                                              ("0x12a", P_FMT3, _pr.word_12a, f3)):
                    _don = rd32(stock, _dP + _off + i * 4)
                    if _w is None:
                        ok, want = _got == _don, f"the donor's 0x{_don:08x}"
                    elif isinstance(_w, tuple):
                        ok, want = _got not in (0, _don), f"{_w[0]}:{_w[1]}"
                    else:
                        ok, want = _got == _w, f"0x{_w:08x}"
                    check(ok, f"{name}: p{i} {_lbl} is {want} as declared "
                              f"(got 0x{_got:08x})")
                continue
            if cnt < 128:
                # The "A" callback may be one of our label
                # caves instead of stock's 0x4003c718 -- that is the whole
                # point: A decides WHAT IS PRINTED, and a select that prints
                # ROOM/PLATE/BIG rather than 1/2/3 still has to be DRAWN as a
                # select. So the invariant this check exists for is B and
                # 0x12a, not A: B is the tick widget, and a non-zero 0x12a
                # forces plain-knob drawing even with the right pair (which
                # is the defect it was written for).
                #
                # A is still constrained -- stock's enumerated formatter or
                # an address inside the cave region, never anything else.
                # What each cave PRINTS is proven separately, by asking the
                # emulated firmware: tools/verify/verify_labels.py.
                a_ok = (f1 == STEPPED_FMT[0] or CAVE_LO <= f1 < CAVE_HI
                        or OVF_LO <= f1 < OVF_HI
                        or f1 in {v for k, v in RUNTIME_SYMS.items() if k.startswith("lfmt_")})
                want_b = STEPPED_FMT[1] if cnt <= 5 else 0
                check(a_ok and f2 == want_b and f3 == 0,
                      f"{name}: p{i} count {cnt} is a SELECT, so it carries "
                      f"{'the tick widget' if want_b else 'a plain dial'} and "
                      f"0x12a=0, with A either stock's "
                      f"enumerated formatter or a label cave "
                      f"(got 0x{f1:08x}/0x{f2:08x}/0x{f3:08x})")
            elif ((name, i) in REG_FMT
                  and (CAVE_LO <= f1 < CAVE_HI or OVF_LO <= f1 < OVF_HI
                       or ISL_LO <= f1 < ISL_HI)
                  and img[f1 - REG_FMT[(name, i)][1] - BASE:
                          f1 - REG_FMT[(name, i)][1] - BASE
                          + len(REG_FMT[(name, i)][0])]
                  == REG_FMT[(name, i)][0]):
                # A registered label formatter (time_fmt.s;
                # cfprobe.s): a knob with A = our cave's entry
                # and B = 0 -- stock DELAY TIME's own shape (A = 0x4003c718,
                # B = 0). Without the cave (NOTEMPO=1) the slot falls through
                # to the plain-knob rule below, as before.
                check(f2 == 0,
                      f"{name}: p{i} carries a registered label formatter at "
                      f"0x{f1:08x}, so B is 0 (got 0x{f2:08x})")
            elif ((name, i) in REG_DRAM and REG_DRAM[(name, i)][0] in RUNTIME_SYMS
                  and f1 == RUNTIME_SYMS[REG_DRAM[(name, i)][0]] + REG_DRAM[(name, i)][1]):
                # A DRAM label formatter: the same shape, A in the runtime.
                check(f2 == 0,
                      f"{name}: p{i} carries a DRAM label formatter at "
                      f"0x{f1:08x}, so B is 0 (got 0x{f2:08x})")
            elif i in getattr(_MODS[name], "bipolar_slots", ()):
                # A BIPOLAR knob: SPRING BAL's dial, drawn
                # -64..+63 -- A = 0x4003c7a0, B = 0, 0x12a = the signed number
                # renderer 0x400328e4, read from the stock descriptor at
                # donor_desc + 0x38. Build-time bytes only until a flash shows
                # the dial (the descriptor trap family, AGENTS.md).
                check(f1 == 0x4003c7a0 and f2 == 0 and f3 == 0x400328e4,
                      f"{name}: p{i} count {cnt} is a BIPOLAR knob, so it carries "
                      f"SPRING BAL's dial (got 0x{f1:08x}/0x{f2:08x}/0x{f3:08x})")
            else:
                check(f1 == 0 and f2 == 0,
                      f"{name}: p{i} count {cnt} is a KNOB, so both formatters "
                      f"are 0 (got 0x{f1:08x}/0x{f2:08x})")

    print("\n=== FX1: its own id lookup and chooser list, and every "
          "donor's OWN descriptor bytes outside our clone caves, are "
          "byte-identical to the pristine image ===")
    # A DECLARED REPLACEMENT owns its target's two FX1 entries and nothing
    # else may move. Without a replacement in the remix these are exact
    # equality, which is what they were written as -- the exception is
    # enumerated from the manifests rather than loosened to a range, so an
    # undeclared change to FX1 still fails.
    _rep_ids = {m.menu.fx2_id for m in _MODS.values()
                if m.menu is not None and m.menu.replaces
                and m.key in REMIX.modules}
    # A REMIX MAY ALSO ASK FOR FX1 ROWS OUTRIGHT (Remix.fx1), which relocates
    # the list and writes FX1's id and cursor tables. Those edits are checked
    # in full below; the byte-equality sweep skips exactly the entries the
    # remix declared, so an UNdeclared change to FX1 still fails.
    _fx1_ids = {_MODS[k].menu.fx2_id for k in REMIX.fx1}
    _skip = set()
    for _eid in _fx1_ids:
        _a = FX1_ID_LOOKUP + _eid * 4 - BASE
        _skip.update(range(_a, _a + 4))
    if REMIX.fx1:
        # The stock list is left where it is; the refs point elsewhere. The
        # cursor table is rewritten WHOLE (every dropped id clamped to row
        # 0), which the FX1 section above checks entry by entry.
        _skip.update(range(FX1_CHOOSER - BASE, FX1_CHOOSER - BASE + FX1_CHOOSER_LEN))
        _skip.update(range(FX1_ID2POS - BASE, FX1_ID2POS - BASE + 0x80))
    for _eid in _rep_ids:
        _a = FX1_ID_LOOKUP + _eid * 4 - BASE
        _skip.update(range(_a, _a + 4))
        _stock_P = next((m.menu.donor_desc + 0x38 for m in _MODS.values()
                         if m.is_stock and m.menu.fx2_id == _eid), None)
        for _o in range(0, FX1_CHOOSER_LEN, 4):
            if int.from_bytes(stock[FX1_CHOOSER - BASE + _o:
                                    FX1_CHOOSER - BASE + _o + 4], "big") == _stock_P:
                _skip.update(range(FX1_CHOOSER - BASE + _o,
                                   FX1_CHOOSER - BASE + _o + 4))

    def _same(lo, ln, what):
        bad = [i for i in range(lo, lo + ln)
               if i not in _skip and img[i] != stock[i]]
        check(not bad, what + (f" -- {len(bad)} byte(s) moved that no "
                               f"replacement declared" if bad else ""))
    _except = ([" apart from declared replacements"] if _rep_ids else []) \
        + ([" apart from the rows this remix asked for"] if REMIX.fx1 else [])
    _except = " and".join(_except)
    _same(FX1_ID_LOOKUP - BASE, 0x80,
          "FX1 id lookup table (0x400d5f58, 32 entries) unchanged" + _except)
    _same(FX1_CHOOSER - BASE, FX1_CHOOSER_LEN,
          "FX1 chooser list (0x400d6060, 11 entries) unchanged" + _except)
    # ==== FX1 rows this remix asked for ==================================
    # The same shape as the FX2 checks above, because it is the same
    # mechanism one table along: three `lea` sites must agree on a relocated
    # list, and FX1's own id lookup must resolve each row to the SAME
    # descriptor the list does -- "a slot can draw a knob and publish
    # nothing" is what a disagreement between them looks like on the unit.
    print("\n=== FX1 chooser (Remix.fx1): the list relocated and composed, "
          "its three refs in agreement, the viewport sized to it, and FX1's "
          "own id and cursor tables written ===")
    if not REMIX.fx1:
        print("  --   this remix composes no FX1 chooser; the checks above "
              "prove FX1 is byte-identical to stock")
    else:
        _live = rd32(img, FX1_LIST_REFS[0])
        check(_live != FX1_CHOOSER,
              f"FX1 list relocated out of 0x{FX1_CHOOSER:08x} "
              f"(to 0x{_live:08x}) -- it cannot grow in place")
        for _r in FX1_LIST_REFS:
            check(rd32(img, _r) == _live,
                  f"FX1 list-ref operand at 0x{_r:08x} == 0x{_live:08x}")
        _list, _i = [], 0
        while rd32(img, _live + _i * 4):
            _list.append(rd32(img, _live + _i * 4))
            _i += 1
        # ROW 0 IS THE FIRMWARE'S OWN NONE, always. It is how the slot is
        # turned off, and a remix naming effects must not be able to lose it
        # by omission.
        check(_list[:1] == [FX1_NONE],
              f"row 0 is the firmware's own NONE (0x{FX1_NONE:08x})")
        check(len(_list) == len(REMIX.fx1) + 1,
              f"FX1 list is NONE + {len(REMIX.fx1)} = {len(REMIX.fx1) + 1} "
              f"rows (got {len(_list)})")
        # THE VIEWPORT IS WHAT MAKES A SHORT LIST SAFE: the draw loop
        # iterates this literal independently of the real length, so an
        # unshrunk viewport over a short list reads past the terminator and
        # renders raw memory as text.
        _rows = int.from_bytes(img[FX1_ROWCOUNT_AT - BASE:
                                   FX1_ROWCOUNT_AT - BASE + 2], "big")
        _want = min(CHOOSER_ROWS, len(_list))
        check(_rows == _want,
              f"FX1 viewport row count == {_want} (got {_rows})"
              + (" -- it scrolls" if len(_list) > CHOOSER_ROWS else ""))
        _listed = set()
        for _n, _k in enumerate(REMIX.fx1):
            _m = _MODS[_k]
            _eid = _m.menu.fx2_id
            _listed.add(_eid)
            _pos = _n + 1                        # past NONE at row 0
            _ids = rd32(img, FX1_ID_LOOKUP + _eid * 4)
            check(_ids != FX1_NONE and _ids == _list[_pos],
                  f"{_k}: FX1_IDS[0x{_eid:02x}] and FX1 list row {_pos} "
                  f"resolve to the same descriptor (0x{_ids:08x})")
            check(rd32(img, FX1_ID2POS + _eid * 4) == _pos,
                  f"{_k}: FX1's cursor table puts id 0x{_eid:02x} on row "
                  f"{_pos} -- without it the chooser opens on row 0")
            if not _m.is_stock:
                # THE SAME DESCRIPTOR BOTH MENUS USE. FX1 and FX2 keep
                # separate id tables; pointing them at different clones
                # would draw two different pages for one effect.
                check(_ids == rd32(img, FX2_IDS + _eid * 4),
                      f"{_k}: FX1 and FX2 resolve id 0x{_eid:02x} to the "
                      f"SAME descriptor, as stock does for the ten shared")
        # ⚠️ AND EVERY OTHER ID IS CLAMPED TO ROW 0. A composed FX1 list can
        # be SHORTER than stock's eleven, so a stale cursor position from an
        # old project holding a dropped id would seed the chooser past the
        # last row.
        _stale = [i for i in range(0x20)
                  if i not in _listed and rd32(img, FX1_ID2POS + i * 4)]
        check(not _stale,
              "every id this list drops has its cursor row clamped to 0"
              + (f" -- {len(_stale)} still point past the list" if _stale
                 else ""))

    # ==== the descriptor each module's id RESOLVES TO ======================
    # ⚠️ THE FIELDS A CLONE INHERITS FROM ITS DONOR. A cloned descriptor is
    # copied whole and then written over, so anything the build does not
    # write stays the donor's -- and some of those fields outrank the ones it
    # does write. A slot can carry the right count, default, name and enable
    # bit and still draw as something else entirely, or as nothing at all:
    # three of six page-2 slots drew wrong on the flash and every
    # check then in place passed, because every field they checked was right.
    #
    # So the built descriptor is read BACK and compared to the manifest that
    # asked for it. This lived in the remixer's UNIT pane for a day (3 Sep
    # 2026) and does not belong there: it is a check, and a check belongs
    # where a mismatch FAILS THE BUILD rather than where it has to be
    # noticed in the corner of a pane.
    print("\n=== every module's descriptor, read back out of the image: the "
          "name and abbreviation the panel will print, and the twelve slot "
          "names -- all fields a clone inherits from its donor ===")
    for name in _ORDER:
        mod = _MODS[name]
        if mod.is_stock:
            continue
        got = _rig.drawn_as(mod.menu.fx2_id, img)
        if got is None:
            check(False, f"{name}: its id resolves to no descriptor")
            continue
        want_name = mod.menu.fullname.decode("latin1")
        check(got["name"].startswith(want_name),
              f"{name}: the panel prints {got['name']!r}, which starts with "
              f"the declared {want_name!r} (the build tag follows it)")
        check(got["abbr"] == mod.menu.abbr.decode("latin1"),
              f"{name}: its abbreviation is "
              f"{got['abbr']!r} == {mod.menu.abbr.decode('latin1')!r}")
        # an inherited slot (active=None, stock_dsp) draws as its donor's
        # does: its expected name is the manifest's, else the donor's
        _inh = INHERITED.get(name, ())
        _dP = mod.menu.donor_desc + 0x38
        _dlo = rd32(stock, _dP + P_PENABLE_LO)
        _dhi = rd32(stock, _dP + P_PENABLE_HI)
        want_slots = []
        for i, p in enumerate(mod.params):
            if i in _inh:
                if not _nibble(_dlo, _dhi, i) & 1:
                    continue
                _a = _dP + P_PARAM_NAMES + i * 6 - BASE
                nm = (p.name if p.name is not None
                      else stock[_a:_a + 6].split(b"\0")[0])
            elif p.active:
                nm = p.name
            else:
                continue
            if nm:
                want_slots.append(nm.decode("latin1"))
        drew = [x for x in got["slots"] if x]
        check(drew == want_slots,
              f"{name}: its {len(want_slots)} drawn slot names are the "
              f"manifest's, in order"
              + ("" if drew == want_slots else f" -- got {drew}"))

    for name, donor_E in (("SPRING", 0x400d5726), ("DARK", 0x400d58b8),
                           ("FILTER", 0x400d4772)):
        check(img[donor_E - BASE:donor_E - BASE + 0x192] ==
              stock[donor_E - BASE:donor_E - BASE + 0x192],
              f"{name}'s own descriptor (E=0x{donor_E:08x}) unchanged -- "
              f"any menu that still lists it shows its original name/knobs "
              f"(NB: the reverbs are FX2-only; FX1 never listed them)")

    print(f"\n{'ALL CHECKS PASSED' if not fails else f'{len(fails)} CHECK(S) FAILED'}")
    if fails:
        sys.exit(1)


if __name__ == "__main__":
    main()
