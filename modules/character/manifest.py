"""CHARACTER -- everything that dirties or tightens, and a bus sender.

The second BamSep26 station. A per-track INSERT that REPLACES stock LO-FI
(id 0x1c, both menus, and every saved part that chose LO-FI):

  * CRUSH -- sample-rate reduction (hold N samples) and bit depth, LO-FI's
    own pair, on one knob each way (CRSH = bits, SRR = the rate divider);
  * FOLD + RING -- WarpFold's wavefolder and its parabolic carrier, so the
    fold and the ring mod are here rather than needing a second insert;
  * SATURATE -- BusDelay's satdrv curve (w - w^3/3, unity small-signal) in
    four flavours: TAPE (the curve alone), TUBE (asymmetric: positive half
    driven harder), FUZZ (hard clip after the curve) and BUS (soft, gentle,
    for the master);
  * COMPRESS -- a feedforward peak compressor with three characters: COMP
    (fast, 4:1), GLUE (slow attack and release, 2:1, soft knee -- the
    mastering setting) and TRNS (a transient shaper: the difference of two
    followers, so the knob adds attack rather than removing it);
  * WIDTH -- mid/side width, 64 = untouched, 0 = mono, 127 = 2x side. This
    is what makes the station a master chain on T8's FX1;
  * ->DEL / ->VRB -- the station is a BUS CLIENT, exactly as the filter
    station is: knob-gated registration, no housekeeping.

Chain order is fixed: crush -> fold/ring -> saturate -> compress -> width.
Distortion before dynamics is the order that makes a compressor useful on a
dirty signal rather than a fader for the dirt.

DEFAULTS ARE A BIT-EXACT PASSTHROUGH (DRV 0, FOLD 0, CRSH 0, COMP 0, MIX
127, RING 0, WDTH 64, SRR OFF, sends 0), because a part that stored LO-FI
runs this after the flash. ⚠️ A part's STORED bytes are stock LO-FI's --
the stamper (plan A6) writes ours.

The compressor's detector reads a KEY that is the station's own input today;
the ->KEY bus send on the backlog swaps in another track's, which is the
only change needed for sidechain ducking.

BUS MODE IS ALSO THE RETURN (3 Sep 2026, docs/effects/BUS.md "The returns"). With
SAT = BUS the station is the master's glue chain, and on a master chain
CRSH and RING are knobs nobody turns -- so BUS repurposes them as the RVRB
and DLY RETURN LEVELS: the panel prints those names (the ModeView below),
the crush and ring stages go neutral, and each sample the two shared wet
buffers are added in AFTER the send taps. While a return level is up the
station stamps that bus's liveness word every block, and the engine on the
other end stops printing its wet on its own host: the reverb leaves T5 and
enters the mix here. Levels down, or any other SAT, and the engines print on
their hosts exactly as before -- a wrong setting on the master can never
make the reverb vanish from the set.
"""

from remix.schema import (BusRole, Claims, DspSection, Formatter, Harness, Kind,
                          MenuEntry, ModeView, Module, Param, YBase)

_PLAIN = Formatter.PLAIN
_STEP = Formatter.STEPPED

_BLANK = Param(b"", 0)

# post-gain compensation for DRV, 1/sqrt(1 + 15*DRV/128) at DRV 0, 8, .., 128:
# the drive's 1x..16x pre-gain read as a +16 dB fader at the unit's level
# (12 Sep 2026); with this a saturated signal comes out near unity and a
# quiet one gains ~+12 dB at full drive. Read with p:(r5)+, interpolated.
DRIVE_COMP = (
    0x7fffff, 0x5bf53a, 0x4b7d83, 0x418e0d, 0x3abafd, 0x35ac14,
    0x31bad7, 0x2e8ba3, 0x2be755, 0x29aa7d, 0x27bd29, 0x260e81,
    0x249249, 0x233f5e, 0x220ec8, 0x20fb17, 0x200000,
)

# The saturation curve, tanh(4w) over w in [0, 1] (driven 0..4) as 33 pairs
# (value, slope to the next value) interpolated per sample -- read with
# (r1)+n1 / p:(r1)+ / p:(r1) at n1 = 2*idx. tanh never goes flat: the cubic
# it replaced (12 Sep 2026) was a hard clip above |w| = 1 and read as digital.
def _tanh_td(n=32, span=4.0):
    import math
    t = [math.tanh(span * i / n) for i in range(n + 1)]
    q = lambda v: min(0x7FFFFF, round(v * (1 << 23)))
    out = []
    for i in range(n + 1):
        out.append(q(t[i]))
        out.append(q(t[i + 1] - t[i]) if i < n else 0)
    return tuple(out)


TANH_TD = _tanh_td()

MODULE = Module(
    name="character",
    key="CHARACTER",
    kind=Kind.DSP_EFFECT,
    doc="BamSep26 station: crush, fold/ring, saturation, compressor, width, sends.",
    menu=MenuEntry(
        fx2_id=0x1c,
        replaces="LO-FI",
        donor_desc=0x400d58b8,        # DARK REV: 12 active slots, selects 7/9/11
        abbr=b"CHAR",
        fullname=b"Character",
        build_tag=True,
    ),
    params=(
        # ---- page 1: the performance surface, scene/CC-reachable -----------
        Param(b"DRV", 0, active=True, formatter=_PLAIN,
              doc="saturation amount; 0 = clean, the curve is unity small-signal"),
        Param(b"FOLD", 0, active=True, formatter=_PLAIN,
              doc="wavefolder drive, 1x..8x into the fold; 0 = no folding"),
        Param(b"CRSH", 0, active=True, formatter=_PLAIN,
              doc="bit depth: 0 = 24 bits, 127 = about 3; in SAT=BUS it is RVRB, the reverb return"),
        Param(b"COMP", 0, active=True, formatter=_PLAIN,
              doc="compression amount; 0 = no gain reduction at any level"),
        _BLANK,   # -DEL: the stations lost their sends in the one-aux rig (7 Sep 2026)
        _BLANK,   # -VRB: the stations lost their sends in the one-aux rig (7 Sep 2026)
        # ---- page 2: knob / select / knob / select / knob / select ----------
        Param(b"MIX", 127, 128, active=True, formatter=_PLAIN,
              doc="dry/wet across the whole chain; 0 = exact passthrough"),
        Param(b"SAT", 0, 4, active=True, formatter=_STEP,
              labels=("TAPE", "TUBE", "FUZZ", "BUS"),
              doc="saturation character; BUS = the master chain, and the returns come in"),
        Param(b"RING", 0, 128, active=True, formatter=_PLAIN,
              doc="ring-mod carrier, ~5 Hz..3 kHz; 0 = off; in SAT=BUS it is DLY, the delay return"),
        Param(b"CMOD", 0, 3, active=True, formatter=_STEP,
              labels=("COMP", "GLUE", "TRNS"),
              doc="COMP fast 4:1 - GLUE slow soft-knee 2:1 (the master) - TRNS transient shaper"),
        Param(b"WDTH", 64, 128, active=True, formatter=_PLAIN,
              doc="mid/side width: 64 = untouched, 0 = mono, 127 = double the sides"),
        Param(b"SRR", 0, 4, active=True, formatter=_STEP,
              labels=("OFF", "/2", "/4", "/8"),
              doc="sample-rate reduction: hold each sample 2, 4 or 8 times"),
    ),
    # SAT = BUS renames the two knobs it repurposes and brings them up at
    # unity: the engines' wet used to land on their hosts at exactly 1.
    mode_slot=7,
    mode_views=(
        ModeView(mode=3,                        # BUS
                 names={2: b"RET", 8: b"----"},      # one return (7 Sep 2026); RING inert
                 defaults={2: 127, 8: 127}),
    ),
    dsp=DspSection(
        asm="modules/character/character.asm",
        ptable=DRIVE_COMP + TANH_TD,
        priority=13,                  # after the Spectrum station
        bus_role=BusRole.NONE,        # an insert that also WRITES the bus
        ybase=YBase.NEVER,                # (an FX1 module may own no buffers;
                                          # the return's payload test reads the
                                          # dispatch table instead -- see the source)
        r7_latch_slot=0x69,           # ROTLATCH parks this block's offset here
        gate_label=None,              # no housekeeping: a station never elects
    ),
    # FX1 ONLY (12 Sep 2026): an FX2 instance runs as a dry pass -- the
    # station reads its allocator base at init and returns before touching
    # a frame when it is an FX2 slot. The rig's cycle envelope only closes
    # with the stations on FX1 (tools/harness/pressure.py: four Characters
    # on both slots priced a core at 4,830 against 3,120), the FX2 chooser
    # hides the row, and tools/verify/verify_character.py proves the dry pass.
    claims=Claims(fx1_only=True),
    harness=Harness(layout_char="2", is_server=False, bus_client=True),
)
