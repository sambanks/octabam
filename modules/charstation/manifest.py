"""CHARACTER STATION -- everything that dirties or tightens, and a bus sender.

The second BamSep26 station. A per-track INSERT that REPLACES stock LO-FI
(id 0x1c, both menus, and every saved part that chose LO-FI):

  * CRUSH -- sample-rate reduction (hold N samples) and bit depth, LO-FI's
    own pair, on one knob each way (CRSH = bits, SRR = the rate divider);
  * FOLD + RING -- WarpFold's wavefolder and its parabolic carrier, so the
    fold and the ring mod are here rather than needing a second insert;
  * SATURATE -- BongDelay's satdrv curve (w - w^3/3, unity small-signal) in
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
"""

from remix.schema import (BusRole, DspSection, Formatter, Harness, Kind,
                          MenuEntry, Module, Param, YBase)

_PLAIN = Formatter.PLAIN
_STEP = Formatter.STEPPED

MODULE = Module(
    name="charstation",
    key="CHARACTER STATION",
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
              doc="bit depth: 0 = 24 bits, 127 = about 3; the quantiser is mid-tread"),
        Param(b"COMP", 0, active=True, formatter=_PLAIN,
              doc="compression amount; 0 = no gain reduction at any level"),
        Param(b"-DEL", 0, active=True, formatter=_PLAIN,
              doc="send the processed signal onto the DELAY bus; 0 = not a client"),
        Param(b"-VRB", 0, active=True, formatter=_PLAIN,
              doc="send the processed signal onto the REVERB bus; 0 = not a client"),
        # ---- page 2: knob / select / knob / select / knob / select ----------
        Param(b"MIX", 127, 128, active=True, formatter=_PLAIN,
              doc="dry/wet across the whole chain; 0 = exact passthrough"),
        Param(b"SAT", 0, 4, active=True, formatter=_STEP,
              labels=("TAPE", "TUBE", "FUZZ", "BUS"),
              doc="saturation character; BUS is the gentle one for a master chain"),
        Param(b"RING", 0, 128, active=True, formatter=_PLAIN,
              doc="ring-mod carrier, ~5 Hz..3 kHz; 0 = off (no carrier at all)"),
        Param(b"CMOD", 0, 3, active=True, formatter=_STEP,
              labels=("COMP", "GLUE", "TRNS"),
              doc="COMP fast 4:1 - GLUE slow soft-knee 2:1 (the master) - TRNS transient shaper"),
        Param(b"WDTH", 64, 128, active=True, formatter=_PLAIN,
              doc="mid/side width: 64 = untouched, 0 = mono, 127 = double the sides"),
        Param(b"SRR", 0, 4, active=True, formatter=_STEP,
              labels=("OFF", "/2", "/4", "/8"),
              doc="sample-rate reduction: hold each sample 2, 4 or 8 times"),
    ),
    dsp=DspSection(
        asm="modules/charstation/char_station.asm",
        priority=13,                  # after the filter station
        bus_role=BusRole.NONE,        # an insert that also WRITES the bus
        ybase=YBase.NEVER,
        r7_latch_slot=0x69,           # ROTLATCH parks this block's offset here
        gate_label=None,              # no housekeeping: a station never elects
    ),
    harness=Harness(layout_char="2", is_server=False, bus_client=True),
)
