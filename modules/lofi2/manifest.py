"""LOFI2 -- one modulator, then sample-rate and bit reduction.

A per-track INSERT on a free id (0x1f), so it displaces no stock effect and
LO-FI stays exactly where it is.

  * MODE picks the modulator: RING, SHIFT UP or SHIFT DOWN. Ring mod and
    frequency shifting are mutually exclusive by design -- summing both
    sidebands of a shifter IS ring modulation, so offering them together
    would be offering the same thing twice.
  * FREQ drives whichever modulator MODE selected, and RANGE scales it:
    LOW for the sub-audio region (a ring mod there is an inverting tremolo
    rather than a sideband generator; a shift there is the slow through-zero
    swirl) and HIGH for the audio range. The MF-102's switch, and for the
    same reason -- no single taper reaches both usefully.
  * FDBK is the shifter's feedback: the output re-enters the input and
    stacks an arithmetic ladder at f, f+d, f+2d, climbing or descending with
    MODE. In RING the same slot is GAIN, make-up on the ring product (ring
    feedback would be a harmonic-order generator rather than a ladder, and
    was not wanted).
  * AMPH is the ring carrier's L/R phase offset, LO-FI's own control,
    bipolar: -90..+88.6 degrees, 0 at the centre. At +-90 the two channels
    are in quadrature and the modulation walks across the image. RING MODE
    ONLY.
  * SRR / BRR are the reduction pair, continuous, after the modulator: our
    own code on stock LO-FI's measured rates and curve.
  * LPF is our own first-order high shelf (-12 dB, no resonance), LAST in
    the chain so it tames the whole module and not just the dry. It is the one
    control whose no-op is at the TOP of its travel.

Chain order is fixed: modulator -> MIX -> SRR -> BRR -> LPF.

THE SHIFTER IS STEREO -- two Hilbert pairs sharing one oscillator, not
BodeShift's mono sum. BodeShift computes its analytic pair on (L+R)/4 and
gets away with it because WIDE derives its stereo from the two DIRECTIONS;
with WIDE dropped, a mono wet would collapse the image at MIX=127 and place
every shifted partial dead centre below it. The cost is a second 16-word
allpass chain plus per-channel aPrev/lastwet. Ring mod needs none of this:
one carrier value multiplies both channels, so the image survives untouched
at any mix.

DEFAULTS ARE A PASSTHROUGH: MIX 0, FREQ 0, FDBK 0, SRR 0, BRR 0, AMPH at
its centre, LPF 127.
A freshly selected LOFI2 does nothing until a knob moves.

Chain order in the code is dry -> modulator -> MIX -> SRR -> BRR -> LPF ->
out. MIX is the MODULATOR's depth, not a global wet/dry: the reduction pair
and the shelf run after it and stay live at MIX=0, which is how stock
behaves. There is therefore no single-knob bypass -- a passthrough is MIX 0
AND SRR 0 AND BRR 0 AND LPF 127, which is the default state.

RANGE's bases are MODE-dependent: RING follows the MF-102 (2 Hz / 60 Hz),
SHIFT follows the Bode 1630 (2 Hz / 31.25 Hz, six octaves to 2 kHz).
"""

import math

from remix.schema import (BusRole, Category, DspSection, Formatter, Gate, Harness,
                          Kind, MenuEntry, ModeView, Module, Param, Evidence, Level, YBase)


def _srr_inc(k):
    """SRR's per-sample phase step at knob k, 1.0 = $400000: the hold lasts
    1/inc samples. The hold length is stock LO-FI's as measured on the unit
    (10 Oct 2026, a 1 kHz tone over USB, the rate read from the image
    positions: 8,018 Hz at 64, 3,564 Hz at 127), L = (k+128)^2/4096 - 3.5,
    floored at 1 sample. Entry 128 is the interpolation's upper neighbour."""
    hold = max(1.0, (k + 128) ** 2 / 4096 - 3.5)
    return min(0x400000, round(0x400000 / hold))


SRR_INC = tuple(_srr_inc(k) for k in range(129))


def _brr_e(k):
    """BRR's step exponent at knob k, in bits above the LSB, held as
    bits * 2^17: 23 t - 1, floored at 0, with u = 1 - 0.78125 k/128 and
    t = 1 - u^2 (stock's curve as its arithmetic reads, 0x5c00 t / 1024 bits) less the
    one bit stock's own arithmetic carries (its quantiser runs on a doubled
    signal). Measured against stock from DC plateaus (10 Oct 2026): stock's
    step sat exactly 1.00 bit under 23 t at every setting from 16 to 127.
    0 through BRR 3, 13.46 at 64, 20.84 at 127; verify_lofi2 checks it
    against stock's, rendered from the user's image."""
    t = 1 - (1 - 0.78125 * k / 128) ** 2
    return round(max(0.0, 0x5C00 * t / 1024 - 1) * (1 << 17))


BRR_E = tuple(_brr_e(k) for k in range(129))
# The step's mantissa 2^-(j/128), j = 0..128. Its reciprocal needs no table
# of its own: 1/(2m) = 2^((j-128)/128) = M[128-j], read from the far end
# (m * 2r is unity within 1.2e-7).
BRR_M = tuple(min(0x7FFFFF, round(2 ** (-j / 128) * (1 << 23))) for j in range(129))


def _lpf_c(k):
    """The LPF shelf's allpass coefficient at knob k, as a 24-bit word: the
    break frequency swept exponentially from 100 Hz at 0 to 16 kHz at 126
    (7.3 octaves, about 17 knob steps an octave), c = (1 - t)/(1 + t) with
    t = tan(pi f / fs). 127 repeats 126 (the shelf is out at 127; its depth
    goes to 0, not its corner), and 128 is the interpolation's end point.
    The shelf's -2.7 dB point is the break; its -6 dB point about twice it."""
    f = 100.0 * 160.0 ** (min(k, 126) / 126)
    t = math.tan(math.pi * f / 44100)
    return round((1 - t) / (1 + t) * (1 << 23)) & 0xFFFFFF


LPF_C = tuple(_lpf_c(k) for k in range(129))

_PLAIN = Formatter.PLAIN
_BIP = Formatter.BIPOLAR
_STEP = Formatter.STEPPED

MODULE = Module(
    name="lofi2",
    key="LOFI2",
    kind=Kind.DSP_EFFECT,
    category=Category.TRACK, author="Bryan T", author_url="https://github.com/bryantysinger",
    evidence=(Evidence(Level.UNIT, unit="MKII", who="Bryan T", date="2026-10-12",
        note="images 96-99 (Oct 2026, this tree): tracks 1 and 5, five instances at once; `_bt_oct` build 11 (12 "
             "Oct 2026, the 414-cycle loop): eight in SHIFT at once, four per core, UP/DOWN switched while playing"),),
    doc="Ring mod or frequency shifter, then sample-rate and bit reduction.",

    menu=MenuEntry(
        # 0x1f: read out of the pristine image 5 Sep 2026 -- FX1_IDS and
        # FX2_IDS point 0x1e and 0x1f at NONE (0x400d4618), so both are free
        # on both menus. NOT a stock id, so no `replaces=` and nothing of the
        # unit's is taken. Not 0x1e: the selftest's placement probes build
        # their scratch fixtures there, and the registry refuses two modules
        # on one id.
        fx2_id=0x1f,
        # DARK REV, the template's donor and Character's: twelve slots and
        # page-2 selects already present. Every field not written below
        # stays DARK REV's, which is why the formatter is stated on EVERY
        # active slot rather than inherited (the 17 Aug BusDelay flash).
        donor_desc=0x400d58b8,
        abbr=b"LOF2",             # <=4 chars, 5-byte field
        fullname=b"LOFI2",        # <=12 chars, 13-byte field
        build_tag=False,
    ),

    # Page 1 is slots 0-5, drawn as two rows of three: the modulator on top,
    # the reduction pair beneath. Page 2 is 6-11; the three page-2 controls
    # sit on the EVEN slots so each arrives in the knob field of its own
    # word (r6+$c / $d / $e) with nothing to unpack from a companion field.
    params=(
        # ---- page 1, top row ----------------------------------------------
        Param(b"FREQ", 0, active=True, formatter=_PLAIN,
              doc="modulator frequency, scaled by RANGE; used by whichever MODE is selected"),
        Param(b"MIX", 0, active=True, formatter=_PLAIN,
              doc="modulator depth; SRR, BRR and LPF still act at 0"),
        # One knob, read per MODE: FDBK in SHIFT, GAIN in RING (ModeView
        # renames it below). GAIN 0 is unity, 64 +6 dB, 127 +11.9 dB.
        Param(b"FDBK", 0, active=True, formatter=_PLAIN,
              doc="shift modes: feedback (an f, f+d, f+2d ladder); RING: gain, 0 to +12 dB"),
        # ---- page 1, bottom row -------------------------------------------
        Param(b"SRR", 0, active=True, formatter=_PLAIN,
              doc="sample-rate reduction, continuous; 0 is off"),
        Param(b"BRR", 0, active=True, formatter=_PLAIN,
              doc="bit-depth reduction; 0 is full depth"),
        # Our own first-order high shelf, LAST in the chain so it tames
        # everything the module does: -12 dB above a corner swept from 100 Hz
        # (0) to 16 kHz (126), and out of circuit bit for bit at 127, which is
        # why the default is 127 and not 0 -- the ONLY control here whose
        # passthrough is at the top of its travel.
        Param(b"LPF", 127, active=True, formatter=_PLAIN,
              doc="high-shelf cut; 127 has no effect, turn down to darken"),
        # ---- page 2 --------------------------------------------------------
        Param(b"RANGE", 1, 2, active=True, formatter=_STEP,
              labels=("LOW", "HIGH"),
              doc="FREQ range: LOW is sub-audio, HIGH is audio"),
        Param(),
        # Short labels: "SHIFT DOWN" (ten characters) faulted the unit when
        # MODE was turned (VEC:04, ADDR 4E007890; docs/contributing/
        # FAILURE_MODES.md). Five characters run on hardware; the limit in
        # between is unmeasured, and the schema does not bound label length.
        Param(b"MODE", 0, 3, active=True, formatter=_STEP,
              labels=("RING", "DOWN", "UP"),
              doc="RING modulator, or frequency shift DOWN or UP; ring and shift are exclusive"),
        Param(),
        # Bipolar: the knob's centre (64) is 0 degrees.
        Param(b"AMPH", 64, 128, active=True, formatter=_BIP,
              doc="RING only: L/R carrier phase, -90 to +88.6 deg; 0 none, positive puts R ahead"),
        Param(),
    ),

    # MODE is slot 8; in RING slot 2 is GAIN, in SHIFT it keeps FDBK. No
    # defaults: a per-mode default for slot 2 would also reset FDBK on every
    # DOWN <-> UP turn.
    mode_slot=8,
    mode_views=(ModeView(mode=0, names={2: b"GAIN"}),   # RING
                ModeView(mode=1),                       # DOWN: FDBK stays
                ModeView(mode=2)),                      # UP: FDBK stays

    dsp=DspSection(
        asm="modules/lofi2/lofi2.asm",
        # BYTE-LOAD-BEARING: the donor region is packed in this order, so
        # changing it moves every module after it. 15 is after modulation
        # (14), i.e. last, which takes the region's trailing free words.
        priority=15,
        bus_role=BusRole.NONE,
        # No shared-window buffers, and no stock allocator use. Those two
        # facts are what keep this module eligible for an FX1 row
        # (state.fx1_hazard): an FX1 slot is 3,072 words against FX2's
        # 16,384, and every stage here is per-sample arithmetic over r7
        # state words with no delay line at all.
        ybase=YBase.NEVER,
        # Our own tables, one block read through the $fab1e0 literal:
        # SRR_INC at +0, BRR_E at +129, BRR_M at +258, LPF_C at +387. No
        # stock table is read, so nothing differs between the payloads.
        ptable=SRR_INC + BRR_E + BRR_M + LPF_C,
    ),

    # "X" was LOFI2's letter on the tree it was written on; VOCODER holds it
    # now, and "L" is stock LO-FI's (tools/remix/stock.py).
    harness=Harness(layout_char="F", is_server=False),
    gates=(Gate("tools/verify/verify_lofi2.py", remix_arg=False),),
    # Dearest: a SHIFT mode (the two Hilbert pairs, the dear loop), every
    # continuous knob at the end that does the most work, the shelf in band.
    dear={"FREQ": 127, "MIX": 127, "FDBK": 127, "SRR": 127, "BRR": 127,
          "LPF": 0, "RANGE": 1, "MODE": 2, "AMPH": 127},
)
