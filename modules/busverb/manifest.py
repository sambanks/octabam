"""BusVerb -- an eight-line FDN reverb with shimmer, gating and mode select.

Clones DARK REV's descriptor. Every slot states its name, including the ones
the donor already carries, because the harness reads these names.
"""

from remix.schema import (Gate, Category, Proof, BusRole, Claims, YBase, DspSection, Formatter,
                          Harness, Kind, MenuEntry, Module, Param)

_PLAIN = Formatter.PLAIN
_STEP = Formatter.STEPPED
_BLANK = Param(b"", 0)             # an undrawn slot


# ---- the module's P table ---------------------------------------------------
# Read by reverb_server.asm through one table literal; build_bus.py rewrites
# it to the table's address and parks the words in the stock curve bank
# X:0x4840 (see modules/spectrum for the mechanism).
#
# 1. The reciprocal table, first: 1/sqrt(N) for N = 8 (index 0: a count of 8
#    wraps to it), 1..7 -- the bus auto-gain, indexed by the client count.
_RECIP = (0x2d413c, 0x7fffff, 0x5a8279, 0x49e69d, 0x400000, 0x393e4b,
          0x34417a, 0x306123)
RECIP_WORDS = len(_RECIP)             # 8 -- `move #8,n5` in the engine
#
# 2. The MODE rows, after them. Each MODE is seventeen (r7 slot, value) pairs
#    the engine copies into its r7 block after warm-up, at a 64-word stride
#    (the index arrives MSB-aligned, $010000 per step; `asr #$a` makes the
#    row offset).
_MODE_SLOTS = (
    0x1e,   # k_mode: the TIME law's mode constant
    0x20,   # wet gain/2 (BIG carries its own -3 dB trim)
    0x00, 0x01, 0x02, 0x03,   # lines 0-3 taps as fractions of the 4096-word line
    0x6f,   # tap scale: SIZE moves within a character rather than replacing it
    0x3f,   # diffusion offset, added to DIFF's span
    0x72,   # damping scale: multiplies the TONE-derived coefficient; smaller = darker
    0x73,   # mod depth scale: only ever scales down, BIG sits at unity
    0x04,   # wet high-cut coefficient
    0x6c,   # lines 4-7 tap scale, the interleave (not $0c: that is the bus gain)
    0x05, 0x06, 0x07, 0x3e,   # input diffuser taps 641/1051/1511/1949 as 2048-tap
    0x2f,   # MODE's LFO RATE scale (1.0 for all three)
)
_MODE_ROWS = {
    # ROOM: k_mode 0.5; taps 3958/3386/2894/2474; tap scale 0.60; damping
    # 0.953 (the loop barely damps, tone lives in the wet high-cut); high-cut
    # 0.523; interleave 0.71875.
    "ROOM":  (0x400000, 0x7e8000, 0x3DD800, 0x34E800, 0x2D3800, 0x26A800,
              0x4CCCCD, 0x100000, 0x7A0000, 0x7fffff, 0x430000, 0x5c0000),
    # PLATE: k_mode 0.4 (set against VintageVerb plate's decay rate at
    # TIME~32); taps 3528/3283/3056/2845; tap scale 0.5625; damping 0.78;
    # high-cut 0.68, the bright one; interleave 0.765625.
    "PLATE": (0x333333, 0x7e8000, 0x372000, 0x334C00, 0x2FC000, 0x2C7400,
              0x480000, 0x100000, 0x640000, 0x7fffff, 0x570000, 0x620000),
    # BIG: k_mode 0.25; wet gain/2 -3 dB vs the others; taps 4050/3403/2860/
    # 2403; tap scale 1.0, the largest space; damping 0.90 (BIG's longer
    # lines damp less often); mod depth 0.60; high-cut 0.60 ~6.4 kHz, below
    # PLATE; interleave 0.789.
    "BIG":   (0x200000, 0x5a0000, 0x3F4800, 0x352C00, 0x2CB000, 0x258C00,
              0x7fffff, 0x0c0000, 0x733333, 0x4CCCCD, 0x4CCCCD, 0x650000),
}
_MODE_COMMON = (1407, 997, 537, 99, 0x7fffff)
_MODE_STRIDE = 64


def _table():
    words = list(_RECIP)
    for name in ("ROOM", "PLATE", "BIG"):        # MODE index 0, 1, 2
        row = []
        for slot, value in zip(_MODE_SLOTS, _MODE_ROWS[name] + _MODE_COMMON,
                               strict=True):
            row += [slot, value]
        assert len(row) == 2 * 17 <= _MODE_STRIDE
        words += row
        if name != "BIG":                        # the last row needs no padding
            words += [0] * (_MODE_STRIDE - len(row))
    assert len(words) == RECIP_WORDS + 2 * _MODE_STRIDE + 2 * 17   # 170
    return tuple(words)

MODULE = Module(
    name="busverb",
    key="REVERB SERVER",
    kind=Kind.DSP_EFFECT,
    category=Category.BUS, author="sambanks", author_url="https://github.com/sambanks",
    proof=Proof.HARDWARE, proof_note="Sam's MKII",
    doc="Eight-line FDN reverb: ROOM/PLATE/BIG, shimmer, gate, mid/side width.",
    menu=MenuEntry(
        fx2_id=0x07,
        donor_desc=0x400d58b8,        # DARK REV
        abbr=b"BVRB",
        fullname=b"BusVerb",
        build_tag=True,
    ),
    params=(
        # ---- page 1 -------------------------------------------------------
        # DEL / REV on slots 0 / 1, SEND's layout (26 Sep 2026): the host
        # page draws these two and nothing else; the rest is the TEMPO
        # window's. DEL is this host's own dry send into the delay's aux; REV
        # its dry send into the REV accumulator (slot 0 until 26 Sep 2026).
        # Default 0 is load-bearing: a non-zero default registers every idle
        # host as a client and dilutes the real senders (-3.0 dB with one
        # sender under the 1/sqrt(N) law, XBUS.md).
        Param(b"DEL", 0, active=True, formatter=_PLAIN,
              doc="this host's own send into the delay"),
        Param(b"REV", 0, active=True, formatter=_PLAIN,
              doc="this host's own send into the reverb (the REV bus)"),
        # SHMR-SHFT are drawn as a linked pair; TIME moved to page-2 slot 11.
        Param(b"SIZE", 100, active=True, formatter=_PLAIN,
              doc="room size -- scales the eight tank lines (taps up to ~89 ms)"),
        # SHMR 0 is bit-identical to the engine without shimmer (the tank
        # modulation is pinned at MOD 30 / RATE 1x inside the engine).
        Param(b"SHMR", 0, active=True, formatter=_PLAIN,
              doc="shimmer -- pitch-shifted regeneration in the tail; 0 = off"),
        # SHFT selects the shimmer interval; width is pinned wide.
        Param(b"SHFT", 3, 6, active=True, formatter=_STEP, link=True,
              labels=("-12", "+5", "+7", "+12", "+19", "+24"),
              doc="shimmer interval, -12 +5 +7 +12 +19 +24; heard once SHMR is up"),
        # WET: the reverb's level. The tank hears the REV sends plus the
        # delay's repeats x DLY; the host prints wet*WET under its own dry.
        Param(b"WET", 127, active=True, formatter=_PLAIN,
              doc="the reverb's level on this host (127 = the wet at +6 dB)"),
        # ---- page 2 ---------------------------------------------------------
        # MODE on slot 6: an even slot is the one the panel's page-2 knob
        # editor writes (docs/firmware/MAINMENU.md 9c-ii); the DSP reads $c's
        # KNOB field (bits 16-23). PLATE by default; the three wet levels sit
        # within 2 dB (ROOM -10.9, PLATE -13.1, BIG -13.0 dBFS at defaults,
        # SEND 100, README.md).
        Param(b"MODE", 1, 3, active=True, formatter=_STEP,
              labels=("ROOM", "PLATE", "BIG"),
              doc="voicing: ROOM / PLATE / BIG; BIG clips first"),
        # TONE is HP + LP on one knob: 0..64 closes the high cut (dark),
        # 64..127 opens the low cut inside the loop (thin); 64 = HP 0 / LP 127.
        # Slot 7 = $c's companion field (bits 8-15).
        Param(b"TONE", 64, 128, active=True, formatter=_PLAIN,
              doc="tail tone: below 64 darkens (high cut), above 64 thins (low cut); 64 = flat"),
        # DIFF 80: the VintageVerb match point bracketed at ~80-90.
        Param(b"DIFF", 80, 128, active=True, formatter=_PLAIN,
              doc="diffusion -- low = discrete repeats, high = smooth wash"),
        # GATE on slot 9 ($d's companion field): page 2 fills from the top left
        Param(b"GATE", 0, 128, active=True, formatter=_PLAIN,
              doc="gated-reverb hold -- higher holds longer; the useful range is low (8-20)"),
        # DLY on slot 10 ($e's KNOB field): published to y:$982, read by the
        # delay, which writes wet*DLY into the chain.
        Param(b"DLY", 127, 128, active=True, formatter=_PLAIN,
              doc="how much of the delay's repeats go into the reverb; 0 = the two in parallel"),
        # TIME on slot 11, $e's companion field (page-1 slot 1 until 26 Sep
        # 2026).
        Param(b"TIME", 64, 128, active=True, formatter=_PLAIN,
              doc="decay time -- how long the tail rings"),
    ),
    mode_slot=6,                      # MODE names itself (ROOM / PLATE / BIG)
    dsp=DspSection(
        asm="modules/busverb/reverb_server.asm",
        priority=1,                       # after SEND, before the delay
        payloads=frozenset({"A"}),        # the core serving tracks 5-8
        bus_role=BusRole.SERVER,
        # The relocated tank buffers at 0x30000/0x34000, rewritten per
        # payload once the bus lives in the shared window.
        ybase=YBase.XBUS,
        r7_latch_slot=None,               # payload A is in lockstep with the
                                          # rotation flip and latches nothing
        gate_label="bus_notfirst",
        override_markers=("; MODE_OVERRIDE",),
        ptable=_table(),                  # the reciprocals + MODE rows, above
    ),
    # The eight tank lines are hardcoded into Y:0x4000-0xBFFF, the per-core
    # FX2 instance buffer region; the ledger refuses anything else that owns
    # memory there on the same core.
    # y:$e00..$e26, core 0: the return buffer and RETURNS' flags and gains
    # (docs/proposals/RETURNS.md). BusVerb owns them: it touches them in
    # every remix, with or without RETURNS.
    claims=Claims(owns_fx2_buffers=True,
                  reserved_private_y=tuple(range(0x0e00, 0x0e27))),
    harness=Harness(layout_char="R", is_server=True),
    # the bus's two-core and one-aux gates (shared with BusDelay; run once)
    gates=(Gate('tools/verify/verify_twocore.py', remix_arg=False),
           Gate('tools/verify/verify_onebus.py', remix_arg=False)),
    dear={'REV': 100, 'MODE': 2, 'SHMR': 127, 'DIFF': 127, 'GATE': 0, 'WET': 127},
)
