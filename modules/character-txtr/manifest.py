"""CHARACTER TXTR -- Character with a texture stage, for testing on units.

modules/character (the station in bottleservice) plus TXTR: Airwindows
Pockey2 after FOLD. The source is character.asm as of 0ab4e46c with the
TXTR block. On DJ EQ's id 0x0d (Character keeps LO-FI's 0x1c), so
remixes/test/character-txtr swaps it in for Character. The cost (TXTR is 163 of 403 cycles per sample,
four of these beside the reverb price a core at 2,751 against 3,120) has
not been measured on hardware; remixes/test/character-txtr is the image
for that.


A per-track insert on stock LO-FI's id 0x1c (FX1 only; an FX2 instance runs
as a dry pass, decided from the allocator base at init). Chain order:
fold -> texture -> saturate -> tilt -> compress -> width.

  * FOLD -- a wrap-and-reflect wavefolder at a held level;
  * TXTR -- Airwindows Pockey2 (MIT): mu-law bit reduction and a sample
    hold on one knob, with Pockey2's blur. 0 skips the stage, bit-exact;
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

Page 1: DRV FOLD WDTH COMP TONE MIX; page 2: SAT KEY KLVL TXTR (5 Oct 2026:
TXTR, Pockey2; 29 Sep 2026:
KEY and KLVL; 22 Sep 2026: TXTR removed,
WDTH in its slot; 20 Sep 2026: TONE back on page 1 in the return's slot)."""

from remix.schema import (Gate, Category, Evidence, Level, BusRole, Claims, DspSection, Formatter, Harness,
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
# TXTR (Airwindows Pockey2, MIT): its mu-law codec as two 257-point tables
# over [0, 1] (index = the top 8 bits, linearly interpolated), then T, the 32
# mantissas floor(2^(21 + j/32)) the resolution is built from per block.
POCKEY_ENC = tuple(round(8388607 * min(1.0, _m.log(1 + 255 * i / 256) / _m.log(255))) for i in range(257))
POCKEY_DEC = tuple(round(8388607 * (256 ** (i / 256) - 1) / 255) for i in range(257))
POCKEY_T = tuple(int(_m.floor(2 ** (21 + j / 32))) for j in range(32))
TAPE_D8 = (0x0ccccd, 0x0ec7fd, 0x1111af, 0x13b608, 0x16c311, 0x1a48fe, 0x1e5a84, 0x230d41, 0x287a27, 0x2ebe07, 0x35fa27, 0x3e54f4, 0x47facd, 0x531ef0, 0x5ffc89, 0x6ed7eb, 0x7fffff)


MODULE = Module(
    name="character-txtr",
    key="CHARACTER TXTR",
    kind=Kind.DSP_EFFECT,
    category=Category.TRACK, author="sambanks", author_url="https://github.com/sambanks",
    evidence=(Evidence(Level.UNIT, unit="MKII", who="sambanks", date="2026-10-16",
        note="cursory testing on Sam's MKII (owner report, 16 Oct 2026)"),),
    doc="Character plus TXTR (Airwindows Pockey2): fold, texture, saturation, tilt, compressor, width.",
    menu=MenuEntry(
        fx2_id=0x0d,                  # DJ EQ's: Character keeps LO-FI's 0x1c
        replaces="DJ EQ",
        donor_desc=0x400d58b8,        # DARK REV: 12 active slots, selects 7/9/11
        abbr=b"CHRT",
        fullname=b"CharTxtr",
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
        Param(b"KEY", 0, 2, active=True, formatter=_STEP,
              labels=("SELF", "T1"),
              doc="compressor key: SELF is this track's input, T1 is track 1's level (not on master)"),
        Param(b"KLVL", 64, 128, active=True, formatter=_PLAIN,
              doc="how hard T1 drives the compressor when KEY is T1: 64 is unity, 127 is x2"),
        Param(b"TXTR", 0, active=True, formatter=_PLAIN,
              doc="Airwindows Pockey2 (MIT): mu-law 16 to 4 bits, 0 to 31 sample hold; 0 is off"),
        _BLANK, _BLANK,
    ),
    # SAT names itself by its value (tools/build/mode_names.with_selfname).
    # No knob changes meaning by mode.
    mode_slot=6,                      # SAT names itself (TAPE / TUBE / INFL)
    dsp=DspSection(
        asm="modules/character-txtr/character_txtr.asm",
        ptable=TUBE_UP + TAPE_D8 + POCKEY_ENC + POCKEY_DEC + POCKEY_T,
        priority=13,                  # after the Spectrum station
        bus_role=BusRole.NONE,        # an insert; never on the bus
        ybase=YBase.NEVER,            # an FX1 module may own no buffers; the
                                      # master's payload test reads the
                                      # dispatch table instead
        r7_latch_slot=None,           # never reads the rotation
        gate_label=None,              # no housekeeping: a station never elects
    ),
    # FX1 only: the rig's cycle envelope closes only with the stations on
    # FX1 (four Characters on both slots priced a core at 4,830 against
    # 3,120). The FX2 chooser hides the row; verify_character proves the
    # dry pass.
    claims=Claims(fx1_only=True),
    # bus_client: KEY reads two words of the bus scratch (y:$990/$991), so
    # the build moves its `$9xx` literals to the shared window under XBUS.
    # It writes nothing there and never registers.
    harness=Harness(layout_char="8", is_server=False, bus_client=True),
    gates=(Gate('modules/character-txtr/verify_character_txtr.py', remix_arg=False),
           Gate('modules/character-txtr/verify_char_key_txtr.py', remix_arg=False)),
    dear={'DRV': 127, 'FOLD': 127, 'COMP': 127, 'MIX': 127, 'WDTH': 127, 'SAT': 0, 'TXTR': 127},
)
