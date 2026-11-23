"""V4 ColdFire core instruction execution times, transcribed from the MCF54455 Reference Manual, Rev 6
(MCF54455RM), section 3.3.5, Tables 3-13 to 3-20 (pages 3-29 to 3-35).

Each entry is (cycles, reads, writes), the manual's C(R/W). The manual's assumptions (3.3.5.1) hold for every
figure here: the OEP has the opword and extensions ready; no instruction pairing (a folded pair costs its first
instruction's time); no sequence stalls; zero-wait memory; aligned operands. What the model adds on top of these
tables (the stalls) lives in cf_scan.py's `price`, not here (docs/contributing/CF_SCAN.md).

Effective-address column keys (the manual's headings):
  Rn, (An), (An)+, -(An), (d16,An), (d8,An,Xi*SF), xxx.wl, #xxx
PC-relative forms cost as their An forms (the note at 3.3.5.2): (d16,PC) = (d16,An), (d8,PC,Xi*SF) = (d8,An,Xi*SF).
A missing key is the manual's dash: the form does not exist.
"""

EA = ("Rn", "(An)", "(An)+", "-(An)", "(d16,An)", "(d8,An,Xi*SF)", "xxx.wl", "#xxx")

# --- Table 3-13 (MOVE.B, MOVE.W) and Table 3-14 (MOVE.L): source row -> destination column.
# The two tables print the same figures for every cell; one table serves both sizes.
MOVE_DST = ("Rx", "(Ax)", "(Ax)+", "-(Ax)", "(d16,Ax)", "(d8,Ax,Xi*SF)", "xxx.wl")
_REG = [(1, 0, 0), (1, 0, 1), (1, 0, 1), (1, 0, 1), (1, 0, 1), (2, 0, 1), (1, 0, 1)]
_IND = [(1, 1, 0), (2, 1, 1), (2, 1, 1), (2, 1, 1), (2, 1, 1), (3, 1, 1), (2, 1, 1)]
_D16 = [(1, 1, 0), (2, 1, 1), (2, 1, 1), (2, 1, 1), (2, 1, 1), None, None]
_D8 = [(2, 1, 0), (3, 1, 1), (3, 1, 1), (3, 1, 1), None, None, None]
_ABS = [(1, 1, 0), (2, 1, 1), (2, 1, 1), (2, 1, 1), None, None, None]
MOVE_BW = {
    "Dy": _REG, "Ay": _REG, "(Ay)": _IND, "(Ay)+": _IND, "-(Ay)": _IND,
    "(d16,Ay)": _D16, "(d8,Ay,Xi*SF)": _D8, "xxx.w": _ABS, "xxx.l": _ABS,
    "(d16,PC)": _D16, "(d8,PC,Xi*SF)": _D8,
    "#xxx": [(1, 0, 0), (1, 0, 1), (1, 0, 1), (1, 0, 1), (1, 0, 1), None, None],   # (d16,Ax): MOVEI, ISA_C
}
MOVE_L = dict(MOVE_BW)
MOVE_L["#xxx"] = [(1, 0, 0), (1, 0, 1), (1, 0, 1), (1, 0, 1), None, None, None]

# --- Table 3-15: one-operand instructions. Value: a tuple in EA order (None = the manual's dash).
_RN_ONLY = ((1, 0, 0),) + (None,) * 7
_CLR = ((1, 0, 0), (1, 0, 1), (1, 0, 1), (1, 0, 1), (1, 0, 1), (2, 0, 1), (1, 0, 1), None)
_TST = ((1, 0, 0), (1, 1, 0), (1, 1, 0), (1, 1, 0), (1, 1, 0), (2, 1, 0), (1, 1, 0), (1, 0, 0))
ONE_OPERAND = {
    **{op: _RN_ONLY for op in ("bitrev", "byterev", "ext.w", "ext.l", "extb.l", "ff1", "neg.l", "negx.l",
                               "not.l", "sats.l", "scc", "swap")},
    "clr.b": _CLR, "clr.w": _CLR, "clr.l": _CLR,
    "tas.b": (None, (1, 1, 1), (1, 1, 1), (1, 1, 1), (1, 1, 1), (2, 1, 1), (1, 1, 1), None),
    "tst.b": _TST, "tst.w": _TST, "tst.l": _TST,
}

# --- Table 3-16: two-operand instructions, keyed (opcode, operand form).
_EA_RX = ((1, 0, 0), (1, 1, 0), (1, 1, 0), (1, 1, 0), (1, 1, 0), (2, 1, 0), (1, 1, 0), (1, 0, 0))
_DY_EA = (None, (1, 1, 1), (1, 1, 1), (1, 1, 1), (1, 1, 1), (2, 1, 1), (1, 1, 1), None)
_Q_EA = ((1, 0, 0), (1, 1, 1), (1, 1, 1), (1, 1, 1), (1, 1, 1), (2, 1, 1), (1, 1, 1), None)
_SHIFT = ((1, 0, 0),) + (None,) * 6 + ((1, 0, 0),)
_BIT_DY = ((2, 0, 0), (2, 1, 1), (2, 1, 1), (2, 1, 1), (2, 1, 1), (3, 1, 1), (2, 1, 1), None)
_BIT_IMM = ((2, 0, 0), (2, 1, 1), (2, 1, 1), (2, 1, 1), (2, 1, 1), None, None, None)
_DIVW = ((20, 0, 0), (20, 1, 0), (20, 1, 0), (20, 1, 0), (20, 1, 0), (21, 1, 0), (20, 1, 0), (20, 0, 0))
_DIVL = ((35, 0, 0), (35, 1, 0), (35, 1, 0), (35, 1, 0), (35, 1, 0), None, None, None)   # "<=35": an upper bound
TWO_OPERAND = {
    **{(op, "<ea>,Rx"): _EA_RX for op in ("add.l", "and.l", "or.l", "sub.l", "cmp.b", "cmp.w", "cmp.l")},
    **{(op, "Dy,<ea>"): _DY_EA for op in ("add.l", "and.l", "or.l", "sub.l")},
    ("eor.l", "Dy,<ea>"): ((1, 0, 0),) + _DY_EA[1:],
    **{(op, "#imm,Dx"): _RN_ONLY for op in ("addi.l", "andi.l", "eori.l", "ori.l", "subi.l",
                                             "cmpi.b", "cmpi.w", "cmpi.l")},
    ("addq.l", "#imm,<ea>"): _Q_EA, ("subq.l", "#imm,<ea>"): _Q_EA,
    ("addx.l", "Dy,Dx"): _RN_ONLY, ("subx.l", "Dy,Dx"): _RN_ONLY,
    **{(op, "<ea>,Dx"): _SHIFT for op in ("asl.l", "asr.l", "lsl.l", "lsr.l")},
    **{(op, "Dy,<ea>"): _BIT_DY for op in ("bchg", "bclr", "bset")},
    **{(op, "#imm,<ea>"): _BIT_IMM for op in ("bchg", "bclr", "bset")},
    ("btst", "Dy,<ea>"): ((2, 0, 0), (1, 1, 0), (1, 1, 0), (1, 1, 0), (1, 1, 0), (2, 1, 0), (1, 1, 0), None),
    ("btst", "#imm,<ea>"): ((1, 0, 0), (1, 1, 0), (1, 1, 0), (1, 1, 0), (1, 1, 0), None, None, None),
    ("divs.w", "<ea>,Dx"): _DIVW, ("divu.w", "<ea>,Dx"): _DIVW,
    ("divs.l", "<ea>,Dx"): _DIVL, ("divu.l", "<ea>,Dx"): _DIVL,
    ("rems.l", "<ea>,Dx"): _DIVL, ("remu.l", "<ea>,Dx"): _DIVL,
    ("lea", "<ea>,Ax"): (None, (1, 0, 0), None, None, (1, 0, 0), (2, 0, 0), (1, 0, 0), None),
    ("moveq.l", "#imm,Dx"): (None,) * 7 + ((1, 0, 0),),
}

# --- Table 3-17: miscellaneous. Same tuple layout as above.
_MV = ((1, 0, 0), (1, 1, 0), (1, 1, 0), (1, 1, 0), (1, 1, 0), (2, 1, 0), (1, 1, 0), (1, 0, 0))
MISC = {
    ("cpushl", "(Ax)"): (None, (9, 0, 1)) + (None,) * 6,
    ("cpushl", "bc,Ax"): (None, (18, 0, 1)) + (None,) * 6,
    ("cpushl", "dc,Ax"): (None, (12, 0, 1)) + (None,) * 6,
    ("cpushl", "ic,Ax"): (None, (18, 0, 1)) + (None,) * 6,
    ("intouch", "(Ay)"): (None, (19, 1, 0)) + (None,) * 6,
    ("link.w", "Ay,#imm"): ((2, 0, 1),) + (None,) * 7,
    ("mov3q.l", "#imm,<ea>"): ((1, 0, 0), (1, 0, 1), (1, 0, 1), (1, 0, 1), (1, 0, 1), (2, 0, 1), (1, 0, 1), None),
    ("move.l", "Ay,USP"): ((3, 0, 0),) + (None,) * 7,
    ("move.l", "USP,Ax"): ((3, 0, 0),) + (None,) * 7,
    ("move.w", "CCR,Dx"): ((1, 0, 0),) + (None,) * 7,
    ("move.w", "<ea>,CCR"): ((1, 0, 0),) + (None,) * 6 + ((1, 0, 0),),
    ("move.w", "SR,Dx"): ((1, 0, 0),) + (None,) * 7,
    ("move.w", "<ea>,SR"): ((4, 0, 0),) + (None,) * 6 + ((4, 0, 0),),   # #imm with imm[13] = 1: 1(0/0) (note 2)
    ("movec", "Ry,Rc"): ((20, 0, 1),) + (None,) * 7,
    ("mvs", "<ea>,Dx"): _MV, ("mvz", "<ea>,Dx"): _MV,
    ("nop", ""): ((6, 0, 0),) + (None,) * 7,
    ("pea", "<ea>"): (None, (1, 0, 1), None, None, (1, 0, 1), (2, 0, 1), (1, 0, 1), None),
    ("pulse", ""): ((1, 0, 0),) + (None,) * 7,
    ("stop", "#imm"): (None,) * 7 + ((6, 0, 0),),
    ("trap", "#imm"): (None,) * 7 + ((18, 1, 2),),
    ("tpf", ""): ((1, 0, 0),) + (None,) * 7,
    ("tpf.w", ""): ((1, 0, 0),) + (None,) * 7,
    ("tpf.l", ""): ((1, 0, 0),) + (None,) * 7,
    ("unlk", "Ax"): ((1, 1, 0),) + (None,) * 7,
    ("wddata", "<ea>"): (None, (1, 1, 0), (1, 1, 0), (1, 1, 0), (1, 1, 0), (2, 1, 0), (1, 1, 0), None),
    ("wdebug", "<ea>"): (None, (3, 2, 0), None, None, (3, 2, 0), None, None, None),
}


def movem(n, store):
    """Table 3-17, MOVEM.L with (An) or (d16,An): n cycles for n registers, n reads or n writes."""
    return (n, 0, n) if store else (n, n, 0)


# --- Table 3-18: EMAC.
_MAC_LOAD = (None, (1, 1, 0), (1, 1, 0), (1, 1, 0), (1, 1, 0), None, None, None)   # (d16,PC) not supported (note 1)
_MUL_L = ((4, 0, 0), (4, 1, 0), (4, 1, 0), (4, 1, 0), (4, 1, 0), None, None, None)
_MUL_W = ((4, 0, 0), (4, 1, 0), (4, 1, 0), (4, 1, 0), (4, 1, 0), (5, 1, 0), (4, 1, 0), (4, 0, 0))
_TO_REG = ((1, 0, 0),) + (None,) * 6 + ((1, 0, 0),)
EMAC = {
    ("mac.l", "Ry,Rx,Raccx"): _RN_ONLY, ("mac.w", "Ry,Rx,Raccx"): _RN_ONLY,
    ("msac.l", "Ry,Rx,Raccx"): _RN_ONLY, ("msac.w", "Ry,Rx,Raccx"): _RN_ONLY,
    ("mac.l", "Ry,Rx,<ea>,Rw,Raccx"): _MAC_LOAD, ("mac.w", "Ry,Rx,<ea>,Rw,Raccx"): _MAC_LOAD,
    ("msac.l", "Ry,Rx,<ea>,Rw,Raccx"): _MAC_LOAD, ("msac.w", "Ry,Rx,<ea>,Rw,Raccx"): _MAC_LOAD,
    ("move.l", "<ea>y,Raccx"): _TO_REG,
    ("move.l", "Raccy,Raccx"): _RN_ONLY,
    ("move.l", "<ea>y,MACSR"): ((8, 0, 0),) + (None,) * 6 + ((8, 0, 0),),
    ("move.l", "<ea>y,Rmask"): ((7, 0, 0),) + (None,) * 6 + ((7, 0, 0),),
    ("move.l", "<ea>y,Raccext01"): _TO_REG, ("move.l", "<ea>y,Raccext23"): _TO_REG,
    ("move.l", "Raccx,<ea>x"): _RN_ONLY,   # +1 with saturation or rounding (MACSR[7:4] 1---, -11-, --11); see EMAC_STORE_AFTER_MAC
    ("move.l", "MACSR,<ea>x"): _RN_ONLY, ("move.l", "Rmask,<ea>x"): _RN_ONLY,
    ("move.l", "Raccext01,<ea>x"): _RN_ONLY, ("move.l", "Raccext23,<ea>x"): _RN_ONLY,
    ("muls.l", "<ea>y,Dx"): _MUL_L, ("mulu.l", "<ea>y,Dx"): _MUL_L,
    ("muls.w", "<ea>y,Dx"): _MUL_W, ("mulu.w", "<ea>y,Dx"): _MUL_W,
}
# The note under Table 3-18: a store of Racc, Raccext, MACSR or Rmask right after a load, MAC or MSAC
# exposes the EMAC pipeline: 4 cycles instead of 1.
EMAC_STORE_AFTER_MAC = 4
EMAC_STORE_ROUNDING_EXTRA = 1

# --- Tables 3-19 and 3-20: branches.
# BRA, JMP xxx.wl, BSR, JSR xxx.wl: the branch acceleration logic; 1 to 3 cycles by the IFP/OEP decoupling
# (notes 1 and 2). The model charges ACCEL_MIN..ACCEL_MAX; the tables print the minimum.
BRANCH = {
    ("bra", "(d16,PC)"): (1, 0, 1),    # printed 1(0/1) for BRA, as for BSR; the write looks like a misprint
    ("bsr", "(d16,PC)"): (1, 0, 1),
    ("jmp", "(An)"): (5, 0, 0), ("jmp", "(d16,An)"): (5, 0, 0), ("jmp", "(d8,An,Xi*SF)"): (6, 0, 0),
    ("jmp", "xxx.wl"): (1, 0, 0),
    ("jsr", "(An)"): (5, 0, 1), ("jsr", "(d16,An)"): (5, 0, 1), ("jsr", "(d8,An,Xi*SF)"): (6, 0, 1),
    ("jsr", "xxx.wl"): (1, 0, 1),
    ("rte", ""): (15, 2, 0),
}
ACCEL_MIN, ACCEL_MAX = 1, 3
RTS = {"predicted": (2, 1, 0), "mispredicted": (9, 1, 0), "not_predicted": (8, 1, 0)}   # 4-entry return stack
RETURN_STACK_DEPTH = 4
BCC = {"cache_taken": 0, "table_taken": 1, "not_taken": 1, "mispredicted": 8}
BRANCH_CACHE_ENTRIES = 8          # direct-mapped, 2-bit states (3.1.1.1)
PREDICTION_TABLE_ENTRIES = 128    # second level, direct-mapped, 2-bit states

# --- 3.3.5.1 assumption 3: a register written in EX and used to form the next instruction's address.
STALL_BASE_OR_INDEX_SF1 = 2       # as a base, or an index with scale factor 1
STALL_INDEX_SF24 = 3              # as an index with scale factor 2 or 4 (the muls.l / move.l (a0,d0.l*4) example)
# Post-increment and pre-decrement address results reach the next instruction with no stall (the note there).

# --- Table 3-12: misaligned operands, the extra C(R/W) on top of the aligned figure.
MISALIGNED = {("word", "odd", "read"): (2, 1, 0), ("word", "odd", "write"): (1, 0, 1),
              ("long", "odd", "read"): (3, 2, 0), ("long", "odd", "write"): (2, 0, 2),
              ("long", "2mod4", "read"): (2, 1, 0), ("long", "2mod4", "write"): (1, 0, 1)}
