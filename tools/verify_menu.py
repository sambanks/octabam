#!/usr/bin/env python3
"""
BUS.md task 11: verify tools/build_menu.py's ColdFire edits against the REAL
chooser mechanism, decompiled straight out of the firmware (Ghidra 12.1.2,
tools/GhidraMenuFuncs.java against out/ghidra_fx's project):

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

Both are DATA computations over the five tables; this script replicates that
exact logic in Python against the built image rather than driving Unicorn
through the real function, because the init branch also calls several
indirect widget-setup function pointers (PTR_FUN_400bb7f0 etc.) that draw the
real menu UI -- stubbing those convincingly is its own project and orthogonal
to what task 11 needs to prove (the five tables agree with each other and
with what the two real functions read). This is "measure, don't guess" in the
form the ColdFire side allows without a full UI emulation harness.
"""
import pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from dsp_modmap import BASE  # noqa: E402

STOCK = pathlib.Path("out/raw/section_3_MAIN_OS.bin")
BUILT = pathlib.Path("out/mainos_bus.bin")

FX2_IDS = 0x400d5fdc
FX2_LIST_LIVE = 0x400d6b00              # NEW_LIST, after the 3 refs repoint
ID2POS = 0x400d6150
LIST_REFS = [0x400375f4, 0x40052496, 0x40059a42]
FX1_ID_LOOKUP = 0x400d5f58
FX1_CHOOSER = 0x400d6060

# name -> (effect id, chooser position). NONE occupies position 0.
EXPECT = {"REVERB SERVER": (0x07, 0), "DELAY SERVER": (0x06, 1), "SEND": (0x09, 2)}
N_REAL = len(EXPECT)                    # no NONE entry any more
ROWCOUNT_AT = 0x40059a56
NONE_ID = 0x00                          # aliased to SEND

# P-relative offsets (PARAM_PAGES.md section 5b: record base is P = E+0x38)
P_PARAM_NAMES = 0x16
P_PENABLE_LO = 0x18e                    # params 0..7, one nibble each
P_PENABLE_HI = 0x18a                    # params 8..11
# which knobs each effect's DSP code actually reads (mirrors build_menu.py)
ACTIVE_PARAMS = {
    "DELAY SERVER": [0, 1, 2, 3, 4, 5, 8],
    # v92 page-2 rejig: all twelve. Even page-2 slots are knob fields, odd ones
    # are companion fields of the same word (DSP.md section 9).
    "REVERB SERVER": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
    "SEND": [0, 1],
}


# P-relative: the per-parameter value-COUNT array and the defaults array.
# tools/build_bus.py writes both; PARAM_PAGES.md section 5b has the record map.
P_COUNTS = 0x9a
P_DEFAULTS = 0x5e


def main():
    stock = STOCK.read_bytes()
    img = BUILT.read_bytes()

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
          "inside those two functions); confirm the operand now reads NEW_LIST ===")
    for r in LIST_REFS:
        check(rd32(img, r) == FX2_LIST_LIVE,
              f"list-ref operand at 0x{r:08x} == NEW_LIST (0x{FX2_LIST_LIVE:08x})")

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
    check(rows == N_REAL, f"viewport row count == {N_REAL} (got {rows})")

    print("\n=== id 0 (a fresh/unassigned track) is aliased to SEND, so every "
          "track sends by default and always does the bus housekeeping ===")
    send_p = rd32(img, FX2_IDS + EXPECT["SEND"][0] * 4)
    check(rd32(img, FX2_IDS + NONE_ID * 4) == send_p,
          f"FX2_IDS[0x00] == SEND's descriptor (0x{send_p:08x})")
    check(rd32(img, ID2POS + NONE_ID * 4) == EXPECT["SEND"][1],
          f"ID2POS[0x00] == SEND's position ({EXPECT['SEND'][1]})")

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
        lo, hi = rd32(img, P + P_PENABLE_LO), rd32(img, P + P_PENABLE_HI)
        got = {i for i in range(12)
               if ((lo if i < 8 else hi) >> (4 * (i if i < 8 else i - 8))) & 1}
        want = set(ACTIVE_PARAMS[name])
        check(got == want,
              f"{name}: enabled knobs {sorted(got)} == expected {sorted(want)} "
              f"(lo=0x{lo:08x} hi=0x{hi:08x})")
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

    print("\n=== FX1 untouched: its own id lookup and chooser list, and every "
          "donor's OWN descriptor bytes outside our clone caves, are "
          "byte-identical to the pristine image ===")
    check(img[FX1_ID_LOOKUP - BASE:FX1_ID_LOOKUP - BASE + 0x80] ==
          stock[FX1_ID_LOOKUP - BASE:FX1_ID_LOOKUP - BASE + 0x80],
          "FX1 id lookup table (0x400d5f58, 32 entries) unchanged")
    check(img[FX1_CHOOSER - BASE:FX1_CHOOSER - BASE + 0x40] ==
          stock[FX1_CHOOSER - BASE:FX1_CHOOSER - BASE + 0x40],
          "FX1 chooser list (0x400d6060, 15 entries) unchanged")
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
