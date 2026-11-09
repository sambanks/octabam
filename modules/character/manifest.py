"""CHARACTER -- the station that dirties or tightens.

A per-track insert on stock LO-FI's id 0x1c (FX1 only; an FX2 instance runs
as a dry pass, decided from the allocator base at init). Chain order:
fold -> saturate -> tilt -> compress -> width.

  * FOLD -- a wrap-and-reflect wavefolder at a held level;
  * SAT -- three JClones (MIT) characters: TAPE = TapeHead (a state-variable
    split at TONE, the low and band parts through a cubic smoothstep, the
    top clean), TUBE = DaTube (u - u^P, the negative half driven twice as
    hard, level-compensated), INFL = OInflator (a signed cubic; DRV is its
    Effect). DRV 0 skips the stage, bit-exact;
  * TONE -- a tilt after the saturator, drawn -64..+63; 0 flat, bit-exact;
  * COMP -- JClones AC1's console channel law: GLUE (slow) on the master
    by position, COMP (fast) elsewhere; the detector's key is the station's
    own input, or with KEY = T1 the BusDelay host's level of T1 x KLVL/64
    (never on the master, which receives T1 itself);
  * WDTH -- mid/side width, drawn -64..+63: -64 mono, +63 2x side.

Page 1: DRV FOLD WDTH COMP TONE MIX; page 2: SAT KEY KLVL (29 Sep 2026:
KEY and KLVL; 22 Sep 2026: TXTR removed,
WDTH in its slot; 20 Sep 2026: TONE back on page 1 in the return's slot)."""

from remix import stations
from remix.schema import (Store, Gate, Category, Proof, BusRole, Claims, DspSection, Formatter, Harness,
                          Kind, MenuEntry, ModeView, Module, Param, YBase)

_PLAIN = Formatter.PLAIN
_STEP = Formatter.STEPPED
_BIPOL = Formatter.BIPOLAR   # drawn -64..+63 around 64

_BLANK = Param(b"", 0)

import math as _m
_P = _m.log(10.0) + 1.0
def _q(v): return min(0x7FFFFF, max(0, round(v * (1 << 23))))

# DaTube's curve: u^P over u in [0, 1], stored as u^P / 2 at 17 points, then
# the 17 slopes to the next point (the last 0): chtube indexes both halves
# with one idx, interpolating over u/2 in 1/32 steps. T(u) = u - u^P applied
# to u = 1 - |x|; past |x| = 1 the JSFX goes linear, which is the same
# formula with u^P dropped -- the lookup clamps u at 0. TUBE's post gain is
# a per-block division in the source.
def _tube_up(n=16):
    t = [0.5 * (i / n) ** _P for i in range(n + 1)]
    return (tuple(_q(v) for v in t)
            + tuple(_q(t[i + 1] - t[i]) if i < n else 0 for i in range(n + 1)))


TUBE_UP = _tube_up()
# TapeHead's drive: d/8 with d = 0.8 * 10^(i/16) (0.8x .. 8x over DRV/128),
# 17 words, interpolated (idx = knob >> 19, frac = the 19 bits under it),
# placed after TUBE_UP's 34 in the P table:
TAPE_D8 = (0x0ccccd, 0x0ec7fd, 0x1111af, 0x13b608, 0x16c311, 0x1a48fe, 0x1e5a84, 0x230d41, 0x287a27, 0x2ebe07, 0x35fa27, 0x3e54f4, 0x47facd, 0x531ef0, 0x5ffc89, 0x6ed7eb, 0x7fffff)


MODULE = Module(
    name="character",
    key="CHARACTER",
    kind=Kind.DSP_EFFECT,
    category=Category.TRACK, author="sambanks", author_url="https://github.com/sambanks",
    proof=Proof.HARDWARE, proof_note="Sam's MKII",
    doc="FX1 station: fold, saturation, tilt, compressor, width.",
    menu=MenuEntry(
        fx2_id=0x17,
        donor_desc=0x400d58b8,        # DARK REV: 12 active slots, selects 7/9/11
        abbr=b"CHAR",
        fullname=b"Character",
        build_tag=True,
    ),
    params=(
        # ---- page 1: the performance surface, scene/CC-reachable -----------
        Param(b"DRV", 0, active=True, formatter=_PLAIN,
              doc="drive into the curve, +12 dB at 127 (TUBE/INFL output-compensated); 0 skips"),
        Param(b"FOLD", 0, active=True, formatter=_PLAIN,
              doc="wavefolder drive, 1x to 48x into the fold; 0 is no folding"),
        Param(b"WDTH", 64, 128, active=True, formatter=_BIPOL,
              doc="stereo width, drawn -64 to +63: 0 untouched, -64 mono, +63 doubles the sides"),
        Param(b"COMP", 0, active=True, formatter=_PLAIN,
              doc="compression amount; 0 is no gain reduction at any level"),
        # TONE: a tilt after the saturator, drawn -64..+63.
        Param(b"TONE", 64, 128, active=True, formatter=_BIPOL,
              doc="a tilt after the saturator in every mode: 64 flat, 127 bright, 0 dark"),
        # MIX on page 1 since 16 Sep 2026 (Sam's knob pass); TONE back beside it 20 Sep.
        Param(b"MIX", 127, active=True, formatter=_PLAIN,
              doc="dry/wet across the whole chain; 0 is exact passthrough"),
        # ---- page 2: SAT (the mode, slot 6 as on every effect) --------------
        Param(b"SAT", 0, 3, active=True, formatter=_STEP,
              labels=("TAPE", "TUBE", "INFL"),
              doc="saturation: TAPE (TapeHead), TUBE (DaTube, asymmetric) or INFL (OInflator); JClones, MIT"),
        Param(b"KEY", 0, 9, active=True, formatter=Formatter.WIDE_STEPPED,
              labels=("SELF", "T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8"),
              doc="key: SELF (own input) or T1..T8's level, not on master; T2..T8 need KEYBUS"),
        Param(b"KLVL", 64, 128, active=True, formatter=_PLAIN,
              doc="how hard the keyed track drives the compressor: 64 is unity, 127 is x2"),
        _BLANK, _BLANK, _BLANK,
    ),
    # SAT names itself by its value (tools/build/mode_names.with_selfname).
    # No knob changes meaning by mode.
    mode_slot=6,                      # SAT names itself (TAPE / TUBE / INFL)
    dsp=DspSection(
        asm="modules/character/character.asm",
        ptable=TUBE_UP + TAPE_D8,
        priority=13,                  # after the Spectrum station
        bus_role=BusRole.NONE,        # an insert; never on the bus
        ybase=YBase.NEVER,            # an FX1 module may own no buffers; the
                                      # master's payload test reads the
                                      # dispatch table instead
        r7_latch_slot=None,           # never reads the rotation
        gate_label=None,              # no housekeeping: a station never elects
    ),
    # The default; the build setting SLOTS = FX1+FX2 lifts fx1_only and the
    # dry flag (tools/remix/stations.py, verify_stations_fx2).
    # FX1 only: the rig's cycle envelope closes only with the stations on
    # FX1 (four Characters on both slots priced a core at 4,830 against
    # 3,120). The FX2 chooser hides the row; verify_character proves the
    # dry pass.
    claims=Claims(fx1_only=True),
    # bus_reader: KEY reads two words of the bus scratch (y:$990/$991), so
    # the build moves its `$9xx` literals to the shared window under XBUS.
    # It writes nothing there and never registers.
    harness=Harness(layout_char="2", is_server=False, bus_reader=True,
                    key_tap="KEYBUS"),
    store=Store("octabam.character"),
    settings=(stations.setting(),),
    variant=stations.variant(lambda: MODULE),
    gates=(Gate('tools/verify/verify_character.py', remix_arg=False),
           Gate('tools/verify/verify_stations_fx2.py', remix_arg=False),
           Gate('tools/verify/verify_char_key.py', remix_arg=False),
           Gate('tools/verify/verify_char_keybus.py', remix_arg=False)),
    dear={'DRV': 127, 'FOLD': 127, 'COMP': 127, 'MIX': 127, 'WDTH': 127, 'SAT': 0},
)
