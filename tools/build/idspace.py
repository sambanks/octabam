"""The 64-id layout (`Remix.id_space = 64`).

Stock holds 32 effect ids: the DSP dispatches through two 32-entry tables
(`X:0x215` init, `X:0x235` process, one 64-word load record per payload) and
the ColdFire resolves descriptors and chooser rows through `FX2_IDS` and
`ID2POS`, 32 entries each. A build works on the stock layout throughout and
writes the tables it grows into a virtual window (`VIRT`); `convert` then
turns the finished image into the 64-id layout:

  * each payload gets one more X load record holding INIT[64], PROC[64] and
    a spare word, at `XADDR`; the six `move x:(r1+$215|$235),r2` words of the
    dispatcher are repointed at it.
  * payload B moves by the size of A's record and the boot code's copies and
    uploads take the new starts and lengths. B's end now covers the head of
    the SRAM-init image that follows it, so the routine that copies that
    image to on-chip SRAM is replaced by a cave that zeroes the covered
    head and copies from B's new end (the head holds eight non-zero bytes).
  * `FX2_IDS` and `ID2POS` are written at `FX2_IDS64` / `ID2POS64` and the
    stock `lea` sites that read them are repointed. FX1's tables stay put:
    a module on FX1 keeps an id below 32 (`registry.assign_ids`).

Nothing here is proven on hardware (docs/contributing/PLACEMENT.md,
"The 64-id layout").
"""
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import ab_records as ab  # noqa: E402

BASE = ab.BASE

# ---- the virtual window a 64-id build writes its tables to ------------------
VIRT = 0xE0000000
V_FX2_IDS = VIRT + 0x000            # 64 x 4 B
V_ID2POS = VIRT + 0x100             # 64 x 4 B
V_XTAB = {"A": VIRT + 0x200, "B": VIRT + 0x400}     # INIT[64], PROC[64]: 128 x 3 B
VIRT_SIZE = 0x600
PROC_OFF = 64                       # PROC[id] is word 64 + id of a table record

# ---- where the grown layout lives -------------------------------------------
XADDR = 0x8da0                      # X address of the new record, both payloads
K = 129                             # its words: INIT[64], PROC[64], one spare
D = 9 + 3 * K                       # bytes it adds to each payload (396)
N = 2 * D                           # bytes B's end moves into the SRAM-init image
RESERVE_END = 0x400d7bbc            # the long chooser list starts here (LONG_LIST)
CAVE = RESERVE_END - 576            # the SRAM-init cave, 64 B
FX2_IDS64 = RESERVE_END - 512
ID2POS64 = RESERVE_END - 256
RESERVE = (CAVE, RESERVE_END)

# ---- stock sites ------------------------------------------------------------
FX2_IDS_STOCK = 0x400d5fdc
ID2POS_STOCK = 0x400d6150
LEA_SITES = {
    FX2_IDS_STOCK: [0x40002406, 0x40031ec8, 0x40037794, 0x4003aa1e, 0x4003c04e, 0x40052528, 0x40059ab6],
    ID2POS_STOCK: [0x4003770a, 0x40059a84],
}
DISPATCH_PCS = {"A": [0x4b4, 0x4cb, 0x4ce, 0x4ea, 0x501, 0x504],
                "B": [0x2a9, 0x2c0, 0x2c3, 0x2df, 0x2f6, 0x2f9]}
A_LEN_SITES = (0x40000478, 0x4000048a, 0x400004d6)     # imm32 of pea / addil
B_LEN_SITES = (0x400004ac, 0x400004fa)
B_START_SITES = (0x400004b2, 0x40000502, 0x40001ed4)
# The Part validator (0x40002318) clamps each track's FX2 id byte to 31 with `moveq #31,%d1` / `moveq #31,%d3` at these two
# addresses, so a project's id of 32 or more loads as 31 (measured on a unit and under the port, 27 Oct 2026). The 64-id
# layout raises it to 63. FX1's pair (0x400023b6, 0x400023bc) stays: FX1's tables keep 32 entries.
VALIDATOR_FX2_CLAMP = ((0x400023de, "721f"), (0x400023e4, "761f"))
SRAM_INIT = 0x4000f938              # `lea 0x401086f4,%a1`, then the copy loop at 0x4000f944
SRAM_INIT_END = 0x4010c57c
SRAM_HEAD_NONZERO = (0xe8, 0xf0)    # the stock image's only non-zero bytes in the head


def fx2_ids(remix):
    """Where the FX2 descriptor-pointer table is in `remix`'s image."""
    return FX2_IDS64 if remix.id_space == 64 else FX2_IDS_STOCK


def id2pos(remix):
    """Where the FX2 id -> chooser-row table is in `remix`'s image."""
    return ID2POS64 if remix.id_space == 64 else ID2POS_STOCK


class Refusal(Exception):
    pass


def _w3(v):
    return v.to_bytes(3, "little")


def _rd3(img, off):
    return img[off] | img[off + 1] << 8 | img[off + 2] << 16


def new_virt(img):
    """The virtual window, filled from the stock layout in `img`."""
    v = bytearray(VIRT_SIZE)

    def r32(a):
        return int.from_bytes(img[a - BASE:a - BASE + 4], "big")
    for i in range(64):
        v[0x000 + 4 * i:0x000 + 4 * i + 4] = r32(FX2_IDS_STOCK + 4 * (i if i < 32 else 0)).to_bytes(4, "big")
        v[0x100 + 4 * i:0x100 + 4 * i + 4] = (r32(ID2POS_STOCK + 4 * i) if i < 32 else 0).to_bytes(4, "big")
    for tag, (va, ln) in (("A", ab.PAYLOAD_A), ("B", ab.PAYLOAD_B)):
        recs, _ = ab.records(img, va, ln)
        off = ab.word_at(recs, 1, 0x215)
        words = [_rd3(img, off + 3 * i) for i in range(64)]
        init, proc = words[:32], words[32:]
        base = V_XTAB[tag] - VIRT
        for i in range(64):
            i_w = init[i] if i < 32 else init[0]
            p_w = proc[i] if i < 32 else proc[0]
            v[base + 3 * i:base + 3 * i + 3] = _w3(i_w)
            v[base + 3 * (PROC_OFF + i):base + 3 * (PROC_OFF + i) + 3] = _w3(p_w)
    return v


def _wr32(img, va, old, new):
    cur = int.from_bytes(img[va - BASE:va - BASE + 4], "big")
    if cur != old:
        raise Refusal(f"{va:#x} holds {cur:#x}, expected {old:#x}: the boot code is not stock")
    img[va - BASE:va - BASE + 4] = new.to_bytes(4, "big")


def convert(img, virt, cache_dir):
    """Turn the finished 32-id image `img` (a bytearray) into the 64-id layout.
    Returns the report lines."""
    stock_len = len(img)
    (a_va, a_len), (b_va, b_len) = ab.PAYLOAD_A, ab.PAYLOAD_B
    a_off, b_off = a_va - BASE, b_va - BASE
    if a_off + a_len != b_off:
        raise Refusal("payload A does not end where B starts")
    recs_a, term_a = ab.records(img, a_va, a_len)
    recs_b, term_b = ab.records(img, b_va, b_len)
    if term_a + 6 != a_off + a_len or term_b + 6 != b_off + b_len:
        raise Refusal("a payload's last record is not followed by exactly its terminator: "
                      "a module grew a payload, which the 64-id layout does not expect")
    top = max(a + c for recs in (recs_a, recs_b) for sp, a, c, _ in recs if sp == 1)
    if XADDR < top:
        raise Refusal(f"X:{XADDR:#x} is inside a loaded X record (the highest ends at {top:#x})")

    def record(tag):
        base = V_XTAB[tag] - VIRT
        words = [_rd3(virt, base + 3 * i) for i in range(2 * 64)] + [0]
        return _w3(1) + _w3(XADDR) + _w3(K) + b"".join(_w3(w) for w in words)
    rec_a, rec_b = record("A"), record("B")
    assert len(rec_a) == D

    # ---- B's end is about to cover the head of the SRAM-init image ----------
    old_end = b_off + b_len
    head = img[old_end:old_end + N]
    if any(b for i, b in enumerate(head) if not SRAM_HEAD_NONZERO[0] <= i < SRAM_HEAD_NONZERO[1]):
        raise Refusal("the SRAM-init image's head holds data outside the eight known bytes")
    v1 = int.from_bytes(img[0x401087dc - BASE:0x401087dc - BASE + 4], "big")
    v2 = int.from_bytes(img[0x401087e0 - BASE:0x401087e0 - BASE + 4], "big")
    if img[SRAM_INIT - BASE:SRAM_INIT - BASE + 6] != bytes.fromhex("43f9401086f4"):
        raise Refusal("the SRAM-init routine is not stock")
    if any(img[o - BASE] for o in range(CAVE, RESERVE_END)):
        raise Refusal(f"the reserve {CAVE:#x}..{RESERVE_END:#x} is not zero: a cave was placed in it")

    # The legacy tables stay in the blob, dead (the dispatcher no longer reads them),
    # holding the entries for ids below 32 so tools that read X:0x215 still see them.
    for tag, recs in (("A", recs_a), ("B", recs_b)):
        base = V_XTAB[tag] - VIRT
        off = ab.word_at(recs, 1, 0x215)
        for i in range(32):
            img[off + 3 * i:off + 3 * i + 3] = virt[base + 3 * i:base + 3 * i + 3]
            img[off + 3 * (32 + i):off + 3 * (32 + i) + 3] = virt[base + 3 * (PROC_OFF + i):base + 3 * (PROC_OFF + i) + 3]

    blob_a = bytes(img[a_off:term_a]) + rec_a + bytes(img[term_a:b_off])
    blob_b = bytes(img[b_off:term_b]) + rec_b + bytes(img[term_b:old_end])
    new = blob_a + blob_b
    new_end = a_off + len(new)
    img[a_off:new_end] = new
    new_b_va = b_va + D
    new_end_va = BASE + new_end
    assert new_end - old_end == N and len(img) == stock_len

    # ---- boot copy lengths, starts; DSP upload pointer ------------------------
    for va in A_LEN_SITES:
        _wr32(img, va, a_len, a_len + D)
    for va in B_LEN_SITES:
        _wr32(img, va, b_len, b_len + D)
    for va in B_START_SITES:
        _wr32(img, va, b_va, new_b_va)

    # ---- the SRAM-init routine -> cave ---------------------------------------
    src = f"""
        .text
        lea     0x80000000,%a0
        move.l  #{N // 4},%d1
1:      clr.l   (%a0)+
        subq.l  #1,%d1
        bne.s   1b
        lea     0x800000e8,%a0
        move.l  #0x{v1:08x},%d1
        move.l  %d1,(%a0)
        move.l  #0x{v2:08x},%d1
        move.l  %d1,4(%a0)
        lea     0x{0x80000000 + N:08x},%a0
        lea     0x{new_end_va:08x},%a1
        jmp     0x4000f944
"""
    cave = _assemble(src, cache_dir)
    assert len(cave) <= 64, len(cave)
    img[SRAM_INIT - BASE:SRAM_INIT - BASE + 6] = bytes.fromhex("4ef9") + CAVE.to_bytes(4, "big")
    img[CAVE - BASE:CAVE - BASE + len(cave)] = cave

    # ---- the dispatcher words -------------------------------------------------
    for tag, (va, ln) in (("A", (a_va, a_len + D)), ("B", (new_b_va, b_len + D))):
        recs, _ = ab.records(bytes(img), va, ln)
        for pc in DISPATCH_PCS[tag]:
            op = ab.word_at(recs, 0, pc)
            ext = ab.word_at(recs, 0, pc + 1)
            if ab.rd(img, op) != 0x0a71d2:
                raise Refusal(f"payload {tag} P:{pc:#x} is not `move x:(r1+xxxx),r2`")
            old = ab.rd(img, ext)
            if old not in (0x215, 0x235):
                raise Refusal(f"payload {tag} P:{pc:#x} indexes X:{old:#x}")
            img[ext:ext + 3] = _w3(XADDR if old == 0x215 else XADDR + PROC_OFF)

    # ---- ColdFire tables --------------------------------------------------------
    img[FX2_IDS64 - BASE:FX2_IDS64 - BASE + 256] = virt[0x000:0x100]
    img[ID2POS64 - BASE:ID2POS64 - BASE + 256] = virt[0x100:0x200]
    repointed = 0
    for old_va, new_va in ((FX2_IDS_STOCK, FX2_IDS64), (ID2POS_STOCK, ID2POS64)):
        for pc in LEA_SITES[old_va]:
            if img[pc - BASE:pc - BASE + 2] == bytes.fromhex("41f9"):
                _wr32(img, pc + 2, old_va, new_va)
                repointed += 1
    for va, stock in VALIDATOR_FX2_CLAMP:
        if img[va - BASE:va - BASE + 2] != bytes.fromhex(stock):
            raise Refusal(f"the Part validator's FX2 id clamp at {va:#x} is not `{stock}` (moveq #31)")
        img[va - BASE + 1] = 0x3f
    return [f"  id space 64: X record of {K} words at X:{XADDR:#x} in both payloads "
            f"(+{D} B each), B now at {new_b_va:#x}",
            f"  id space 64: SRAM-init cave {len(cave)} B at {CAVE:#x}, FX2_IDS at {FX2_IDS64:#x}, "
            f"ID2POS at {ID2POS64:#x}, {repointed} of "
            f"{sum(len(v) for v in LEA_SITES.values())} lea sites repointed, the Part validator's FX2 id clamp raised to 63"]


def _assemble(src, cache_dir):
    d = pathlib.Path(cache_dir)
    d.mkdir(parents=True, exist_ok=True)
    (d / "sram_cave.s").write_text(src)
    subprocess.run(["m68k-elf-as", "-mcpu=5475", str(d / "sram_cave.s"), "-o", str(d / "sram_cave.o")],
                   check=True)
    subprocess.run(["m68k-elf-objcopy", "-O", "binary", "-j", ".text", str(d / "sram_cave.o"),
                    str(d / "sram_cave.bin")], check=True)
    return (d / "sram_cave.bin").read_bytes()


def layout_of(img):
    """32 or 64: which id layout `img` has (a 64-id image has the new record in payload A)."""
    (a_va, a_len), _ = payloads(img)
    recs, _ = ab.records(img, a_va, a_len)
    return 64 if any(sp == 1 and a == XADDR and c == K for sp, a, c, _ in recs) else 32


def dispatch_word(img, tag, kind, fxid):
    """The DSP dispatch word for `fxid` in payload `tag` ("A" or "B") of `img`:
    kind 0 is INIT, kind 1 is PROC; read from the layout `img` has."""
    pa, pb = payloads(img)
    va, ln = pa if tag == "A" else pb
    recs, _ = ab.records(img, va, ln)
    if layout_of(img) == 64:
        addr = XADDR + (PROC_OFF if kind else 0) + fxid
    else:
        if fxid >= 32:
            raise Refusal(f"id {fxid:#x} is outside a 32-id image")
        addr = 0x215 + (0x20 if kind else 0) + fxid
    return ab.rd(img, ab.word_at(recs, 1, addr))


def payloads(img):
    """((va, len) of A, (va, len) of B) in `img`, whichever layout it has."""
    a_va = ab.PAYLOAD_A[0]
    recs, term = ab.records(img, a_va, 1 << 20)
    a_len = term + 6 - (a_va - BASE)
    b_va = a_va + a_len
    recs, term = ab.records(img, b_va, 1 << 20)
    return (a_va, a_len), (b_va, term + 6 - (b_va - BASE))
