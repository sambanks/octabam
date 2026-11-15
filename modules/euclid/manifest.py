"""EUCLID -- a swung, track-clocked filter/amp sequencer."""
import math

from remix.schema import (Gate, Category, Evidence, Level, BusRole, Detour, DspSection, Formatter, Harness,
                          Kind, Linked, MenuEntry, ModeView, Module, NameSelect,
                          Param, YBase)

P, S, W, B = (Formatter.PLAIN, Formatter.STEPPED,
              Formatter.WIDE_STEPPED, Formatter.BIPOLAR)
# Spectrum's TPT SVF coefficient convention: g/2, logarithmic 30 Hz..15 kHz.
G2 = tuple(round(math.tan(math.pi * 30 * 500 ** (i / 32) / 44100) * (1 << 22))
           for i in range(33))
MODULE = Module(
    name="euclid", key="EUCLID", kind=Kind.HYBRID,
    category=Category.TRACK, author="repeat98", author_url="https://github.com/repeat98",
    evidence=(Evidence(Level.UNIT, unit="MKII", who="sambanks", date="2026-10-16",
        note="Tested on Sam's MKII (16 Oct 2026) and radiohagen's MKII (21 and 25 Oct 2026): start/resume, "
             "multiple tracks and both FX slots."),),
    doc="Euclidean LP/BP/HP/notch/amp sequencer: swing, envelope, gate, random and loop.",
    menu=MenuEntry(fx2_id=0x1d, donor_desc=0x400d58b8,
                   abbr=b"EUCL", fullname=b"Euclid"),
    params=(
        Param(b"FREQ", 48, 128, True, P, doc="base filter cutoff, 30 Hz to 15 kHz logarithmic; the base level in AMP"),
        Param(b"RES", 48, 128, True, P, doc="filter resonance; no effect in AMP"),
        Param(b"DEPTH", 100, 128, True, B, doc="cutoff or level modulation: below centre down, centre none, above centre up"),
        Param(b"DECAY", 48, 128, True, P, doc="envelope decay up to eight steps, or the gate length; no effect on RAND"),
        Param(b"STEPS", 15, 64, True, W, labels=tuple(str(i) for i in range(1, 65)),
              doc="length of the Euclidean cycle, 1 to 64"),
        Param(b"PULSE", 5, 65, True, W, labels=tuple(str(i) for i in range(65)),
              doc="number of pulses; a value above STEPS is clamped to STEPS"),
        Param(b"ROT", 0, 64, True, W, labels=tuple(str(i) for i in range(64)),
              doc="rotates the rhythm and the captured values right, wrapping at STEPS"),
        Param(b"RATE", 1, 5, True, S, labels=("1/32", "1/16", "1/8", "1/4", "1/2"),
              doc="speed against the track: 1/16 is one track step"),
        Param(b"TYPE", 0, 5, True, S, labels=("LP", "BP", "HP", "AMP", "NOTCH"),
              doc="two-pole filter response (LP, BP, HP, NOTCH), or AMP for amplitude modulation"),
        Param(b"ATK", 0, 128, True, P, doc="attack, gate edge or random slew, from 0 to one step"),
        Param(b"OUT", 0, 4, True, S, labels=("ENV", "GATE", "RAND", "LOOP"),
              doc="each pulse makes an ENV envelope, a GATE, a RAND sample-and-hold or a LOOP of random"),
        Param(b"MIX", 127, 128, True, P, doc="dry/wet; 0 is exact passthrough"),
    ),
    mode_slot=10,
    mode_views=(
        ModeView(0, names={3: b"DEC", 9: b"ATK"}),
        ModeView(1, names={3: b"LEN", 9: b"EDGE"}),
        ModeView(2, names={3: b"--", 9: b"SLEW"}),
        ModeView(3, names={3: b"--", 9: b"SLEW"}),
    ),
    name_selects=(
        NameSelect(8, (
            ModeView(0, names={0: b"FREQ", 1: b"RES", 2: b"DEPTH"}),
            ModeView(1, names={0: b"FREQ", 1: b"RES", 2: b"DEPTH"}),
            ModeView(2, names={0: b"FREQ", 1: b"RES", 2: b"DEPTH"}),
            ModeView(3, names={0: b"LEVEL", 1: b"--", 2: b"AMT"}),
            ModeView(4, names={0: b"FREQ", 1: b"RES", 2: b"DEPTH"}),
        )),
    ),
    dsp=DspSection(asm="modules/euclid/filter.asm", priority=16,
                   bus_role=BusRole.NONE, ybase=YBase.NEVER, ptable=G2),
    requires=("EVENTS",),
    linked=(Linked("euclid", "modules/euclid/control.s", cpu="5475", dram=True),),
    detours=(
        Detour(0x4000d562, bytes.fromhex("43f9800000f0"), "euclid", "eu_frame_hook",
               "Publish Euclid's cutoff after the final scene and LFO writes"),
    ),
    harness=Harness(layout_char="Q", is_server=False),
    gates=(Gate('tools/verify/verify_euclid.py', venv=True, stage='image'),),
)
