"""SPECTRUM -- two filters in one insert, and a bus sender.

The first BamSep26 station. A per-track INSERT that REPLACES stock FILTER
(id 0x04, both menus, and every saved part that chose FILTER), built the way
the Digitakt II / Digitone II pair a multimode filter with a base/width
filter -- plus the Sherman-filterbank moves that fit in twelve slots:

  * filter A -- Ripple's driven Chamberlin SVF: LP / BP / HP / NOTCH, and a
    VOWEL mode (five formant pairs morphed by FREQ, A's band-pass at F1 and
    filter B as a band at F2);
  * filter B -- a base/width pair: two cascaded one-poles of HP at BASE and
    two of LP at WDTH (12 dB/oct each side);
  * routing -- SER (A into B), PAR (A + B), RING (A x B), FM (B's output
    modulates A's cutoff at audio rate, one sample late);
  * modulation -- one bipolar DPTH onto A's cutoff, from an envelope follower
    (block-peak, instant attack, RATE = release), an LFO (RATE = speed), or
    both;
  * ->DEL / ->VRB -- the station is a BUS CLIENT: the processed signal is
    sent onto both buses, page 1, scene-lockable. It registers only when a
    send is non-zero (the N/(N+1) dilution trap) and NEVER HOUSEKEEPS: the
    election is the FX2 participants' business, so an FX1 station on track 5
    cannot double-flip the rotation with its own FX2.

DEFAULTS ARE A BIT-EXACT PASSTHROUGH (FREQ 127, RES 0, BASE 0, WDTH 127,
DRV 0, DPTH 64, LP, SER, sends 0): the engine detects that block and copies
nothing, because after the flash every part that ever chose FILTER runs
this on FX1. ⚠️ A part's STORED bytes are stock FILTER's, not these defaults
(DEC=64 lands on ->VRB): the project stamper writes ours (plan A6).

Every mpy is `mpy x0,y1`, the audited-signed form; every clip is the store
limiter. Cycles: the whole loop is straight-line and priced by `make cycles`.
"""

from remix.schema import (BusRole, DspSection, Formatter, Harness, Kind,
                          MenuEntry, Module, Param, YBase)

_PLAIN = Formatter.PLAIN
_STEP = Formatter.STEPPED

MODULE = Module(
    name="spectrum",
    key="SPECTRUM",
    kind=Kind.DSP_EFFECT,
    doc="BamSep26 station: dual filter (SVF + base/width), LFO/env, SER/PAR/RING/FM, sends.",
    menu=MenuEntry(
        fx2_id=0x04,
        replaces="FILTER",            # stock FILTER's id: both menus, every part
        donor_desc=0x400d58b8,        # DARK REV: 12 active slots, selects on 7/9/11
        abbr=b"SPEC",
        fullname=b"Spectrum",
        build_tag=True,
    ),
    params=(
        # ---- page 1: the performance surface, scene/CC-reachable -----------
        Param(b"FREQ", 127, active=True, formatter=_PLAIN,
              doc="filter A cutoff, ~24 Hz..7.2 kHz squared taper; in VOWEL the vowel A-E-I-O-U"),
        Param(b"RES", 0, active=True, formatter=_PLAIN,
              doc="filter A resonance, up to Q~30"),
        Param(b"BASE", 0, active=True, formatter=_PLAIN,
              doc="filter B high-pass corner (12 dB/oct); 0 = open"),
        Param(b"WDTH", 127, active=True, formatter=_PLAIN,
              doc="filter B low-pass corner above BASE (12 dB/oct); 127 = open"),
        Param(b"-DEL", 0, active=True, formatter=_PLAIN,
              doc="send the processed signal onto the DELAY bus; 0 = not a client"),
        Param(b"-VRB", 0, active=True, formatter=_PLAIN,
              doc="send the processed signal onto the REVERB bus; 0 = not a client"),
        # ---- page 2: knob / select / knob / select / knob / select ----------
        Param(b"DRV", 0, 128, active=True, formatter=_PLAIN,
              doc="drive into filter A, 1..4x, clipped at the rail; 0 = unity"),
        Param(b"MODE", 0, 5, active=True, formatter=_STEP,
              labels=("LP", "BP", "HP", "NTCH", "VOWL"),
              doc="filter A response; VOWL = formant pair morphed by FREQ, forces PAR"),
        Param(b"DPTH", 64, 128, active=True, formatter=_PLAIN,
              doc="modulation depth onto A's cutoff, bipolar around 64 = none"),
        Param(b"ROUT", 0, 4, active=True, formatter=_STEP,
              labels=("SER", "PAR", "RING", "FM"),
              doc="SER A into B; PAR A+B; RING A*B; FM B's output modulates A's cutoff"),
        Param(b"RATE", 64, 128, active=True, formatter=_PLAIN,
              doc="LFO speed ~0.08..9 Hz, and the envelope release (0 slow .. 127 fast)"),
        Param(b"SRC", 0, 3, active=True, formatter=_STEP,
              labels=("ENV", "LFO", "BOTH"),
              doc="what DPTH applies: the envelope follower, the LFO, or half of each"),
    ),
    dsp=DspSection(
        asm="modules/spectrum/spectrum.asm",
        priority=12,                  # after every existing module
        bus_role=BusRole.NONE,        # an insert that also WRITES the bus
        ybase=YBase.NEVER,
        r7_latch_slot=0x69,           # ROTLATCH parks this block's offset here
        gate_label=None,              # no housekeeping, so no XBUS gate
    ),
    # bus_client: it writes the shared accumulators, so an image with it has a
    # bus and needs SEND as the fallback (schema.on_the_bus).
    harness=Harness(layout_char="1", is_server=False, bus_client=True),
)
