"""MODULATION -- a modulation pedal, five modes, on id 0x0e (stock CHORUS keeps 0x12).

A per-track insert (FX1 only). Each mode transcribes a published,
permissively licensed source (sources: modules/modulation/README.md, licences THIRD_PARTY.md;
the float reference the DSP is proven against: modulation_ref.py):

    JUNO  the Juno-60 chorus (jpcima HeraChorus.dsp, ISC + the Juno-60
          measurements): two BBD lines on one triangle LFO, R inverted;
          I 0.513 Hz / II 0.863 Hz over 1.5..5.4 ms
    DIM   the Roland Dimension D (SDD-320): antiphase lines, cross-mixed
          through a highpass, a bass lift on the dry; 0.25 / 0.5 Hz, 5..12
          ms. The amounts are unpublished: ours
    FLNG  Dattorro's flanger (JAES 1997, Table 6): through-zero, the dry
          read from the sweep's centre, feedforward and feedback -0.7071
    COMB  Rings' string loop (Mutable Instruments, MIT): Hermite-read,
          FIR damping, the per-pass gain from a decay TIME so every pitch
          rings for the same time; FDBK's sign = the polarity (ours)
    PHSR  ChowPhaser (BSD-3), the Schulte Compact Phasing A: a feedback
          section of two RC allpasses, then 2/4/6/8 allpasses on the LDR's
          law. Last in the select so dropping it moves no stored byte

FX1 only, enforced by the module: it needs a per-track delay line, and
beside the servers the only free per-track buffer is the FX1 slot. It reads
its base from the host's bump allocator at init (docs/firmware/DSP.md
section 10); if that base is an FX2 slot (>= 0x4000) it runs as a dry pass
and writes nothing. `Claims(fx1_only=True)` declares that and the render
gate proves it. Two lines of 1,024 words out of the 3,072 an FX1 slot
gives, each a modulo-1024 ring.

Not a bus client: does not housekeep, does not write the bus."""

import importlib.util
import pathlib

from remix import stations
from remix.schema import (Store, Gate, Category, Proof, BusRole, Claims, DspSection, Formatter, Harness,
                          Kind, MenuEntry, ModeView, Module, Param, YBase)

# The float reference is also the source of the P table and the MODE labels,
# so the build, the DSP and the gate read one copy (vibrato's manifest does
# the same).
_spec = importlib.util.spec_from_file_location("modulation_ref",
                                               pathlib.Path(__file__).with_name("modulation_ref.py"))
_ref = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ref)

_PLAIN = Formatter.PLAIN
_STEP = Formatter.STEPPED
_BIPOL = Formatter.BIPOLAR   # drawn -64..+63 around 64

_BLANK = Param(b"", 0)

# The P table, _ref.TABLE (33 words a table, read at idx = u >> 18 and
# interpolated on the 18 bits under it; the masks are read whole):
#   PHSR_MOD   ChowPhaser's mod-stage allpass coefficient b0 = (RCK-1)/(RCK+1)
#              over lfo = -1..1, R = 100k (light/0.1)^-0.75, light = 20.1 -
#              20 lfo, C = 25 nF, K = 2 fs
#   PHSR_FB    the same for the feedback stages, C = 15 nF
#   PERIOD     COMB's period in Q11.12 samples: 1,000 .. 8, exponential
#   POW2       T(u) = 2^(-8u): COMB's decay (rt60 and the per-pass gain)
#   LOFI_MASK  LOFI's bit mask by k >> 3: 24 bits below 64, then 16 12 10 9
#              8 7 6 5 (16 words)

MODULE = Module(
    name="modulation",
    key="MODULATION",
    kind=Kind.DSP_EFFECT,
    category=Category.TRACK, author="sambanks", author_url="https://github.com/sambanks",
    proof=Proof.HARDWARE, proof_note="Sam's MKII",
    doc="FX1 station: a modulation pedal -- Juno, Dimension, flanger, phaser, comb; FX1 only.",
    menu=MenuEntry(
        fx2_id=0x0e,
        donor_desc=0x400d58b8,        # DARK REV: 12 active slots, selects 7/9/11
        abbr=b"MODU",
        fullname=b"Modulation",
        build_tag=True,
    ),
    params=(
        # ---- page 1 (16 Sep 2026): the sweep's three knobs together, RATE
        # and DPTH drawn as a linked pair; LOFI, then MIX bottom right.
        Param(b"RATE", 26, active=True, formatter=_PLAIN,
              doc="LFO speed, 0.08 to 10 Hz on a squared taper (26 is the Juno's 0.5 Hz)"),
        Param(b"DPTH", 21, active=True, formatter=_PLAIN, link=True,
              doc="sweep depth, up to 480 samples either side of DLY; in PHSR how far the LFO reaches"),
        Param(b"DLY", 18, active=True, formatter=_PLAIN,
              doc="sweep centre, 0.2 to 23 ms; in COMB the pitch, in PHSR the stages (2, 4, 6, 8)"),
        Param(b"FDBK", 64, 128, active=True, formatter=_BIPOL,
              doc="64 is none: feedback from the swept tap; PHSR regen; COMB decay time and polarity"),
        Param(b"LOFI", 0, active=True, formatter=_PLAIN,
              doc="coarse clock and bit depth on the line: hold up to 65 samples, 24 bits then 16 to 5"),
        # MIX bottom right, as on every effect (Sam, image 29)
        Param(b"MIX", 0, active=True, formatter=_PLAIN,
              doc="dry/wet; 0 is exact passthrough, 127 is the wet alone"),
        # ---- page 2, filled from the top left: MODE (slot 6 as on every
        # effect), TONE, WDTH ----------------------------------------------
        Param(b"MODE", 0, 5, active=True, formatter=_STEP,
              labels=tuple(_ref.MODES),      # JUNO DIM FLNG COMB PHSR, the gate's names too
              doc="which pedal: JUNO, DIM, FLNG, COMB or PHSR"),
        Param(b"TONE", 80, 128, active=True, formatter=_PLAIN,
              doc="BBD filters in and out of the line: 0 dark (2 kHz), 127 open; COMB brightness; not PHSR"),
        Param(b"WDTH", 127, 128, active=True, formatter=_PLAIN,
              doc="right-channel LFO lag: 0 mono, 64 quadrature, 127 antiphase (JUNO, DIM); not COMB"),
        _BLANK, _BLANK, _BLANK,
    ),
    # ---- what each MODE renames and re-defaults ---------------------------
    # The defaults are each source's own numbers: the Juno's I (0.513 Hz,
    # +-1.8 ms about 3.35 ms, antiphase, dry 0.83 + wet 1.0 ~ MIX 70), the
    # Dimension's mode 1 (0.25 Hz, 5..12 ms),
    # Dattorro's flanger (0..10 ms; his 0.15 Hz slowed to 0.12 by ear), ChowPhaser's defaults (4 Hz,
    # depth 0.95 -> 121, 8 stages), Rings at a mid pitch with a 2 s ring.
    mode_slot=6,
    mode_views=(
        ModeView(mode=0,                        # JUNO
                 defaults={0: 26, 1: 21, 2: 18, 3: 64, 5: 70, 7: 80, 8: 127}),
        ModeView(mode=1,                        # DIM
                 defaults={0: 18, 1: 41, 2: 47, 3: 64, 5: 127, 7: 80, 8: 127}),
        ModeView(mode=2,                        # FLNG
                 names={2: b"MANL"},
                 defaults={0: 8, 1: 59, 2: 27, 3: 19, 5: 127, 7: 127, 8: 0}),   # RATE 8 = 0.12 Hz (Sam, 16 Sep: 14 too fast)
        ModeView(mode=3,                        # COMB: no LFO (RATE DPTH WDTH `---`)
                 names={0: b"---", 1: b"---", 3: b"DCAY", 2: b"PTCH", 7: b"BRIT", 8: b"---"},   # TONE = the FIR's brightness
                 defaults={0: 0, 1: 0, 2: 64, 3: 82, 5: 64, 7: 100, 8: 0}),   # FDBK 82: rt60 ~ 1 s
        ModeView(mode=4,                        # PHSR (last: dropping it
                 names={2: b"STGS", 7: b"---"},  # would move no other mode); no line filter: TONE `---`
                 defaults={0: 28, 1: 121, 2: 127, 3: 64, 5: 64, 7: 127, 8: 64}),
    ),
    dsp=DspSection(
        asm="modules/modulation/modulation.asm",
        ptable=_ref.TABLE,            # PHSR_MOD PHSR_FB PERIOD POW2 (33 words each), LOFI_MASK (16)
        priority=14,                  # after the Character station
        bus_role=BusRole.NONE,        # an insert; it writes nothing to the bus
        ybase=YBase.NEVER,
        r7_latch_slot=None,           # no ROTLATCH/ROTINIT: not a bus client
        gate_label=None,              # no housekeeping: a station never elects
    ),
    # The default; the build setting SLOTS = FX1+FX2 lifts fx1_only and the
    # dry flag (tools/remix/stations.py, verify_stations_fx2).
    # Two 1,024-word lines out of the 3,072 an FX1 slot gives. `fx1_only`
    # is the promise that an FX2 instance writes nothing; the ledger admits
    # it beside a server on that basis and verify_modulation proves it.
    claims=Claims(stock_instance_buffer=True, buffer_words=2048, fx1_only=True),
    harness=Harness(layout_char="3", is_server=False, bus_client=False),
    store=Store("octabam.modulation"),
    settings=(stations.setting(),),
    variant=stations.variant(lambda: MODULE),
    gates=(Gate('tools/verify/verify_modulation.py', remix_arg=False),
           Gate('tools/verify/verify_stations_fx2.py', remix_arg=False),),
    dear={'MIX': 127, 'FDBK': 127, 'DPTH': 127, 'MODE': 4, 'LOFI': 127},
)
