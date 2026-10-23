"""EUCLID -- a swung, track-clocked filter/amp sequencer."""
import math

from remix.schema import (Gate, Category, Proof, BusRole, Detour, DspSection, Formatter, Harness,
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
    proof=Proof.HARDWARE, proof_note="Cursory testing on Sam's MKII (owner report, 16 Oct 2026); radiohagen's MKII: start/resume recovery with one instance, several tracks and both FX slots (owner report, 21 Oct 2026; [PR #851](https://github.com/sambanks/octabam/pull/851)).; shared EVENTS migration is software-only, not hardware-tested",
    doc="Euclidean LP/BP/HP/notch/amp sequencer: swing, envelope, gate, random and loop.",
    menu=MenuEntry(fx2_id=0x1d, donor_desc=0x400d58b8,
                   abbr=b"EUCL", fullname=b"Euclid"),
    params=(
        Param(b"FREQ", 48, 128, True, P, doc="Base filter cutoff or AMP level; cutoff is 30 Hz..15 kHz logarithmic"),
        Param(b"RES", 48, 128, True, P, doc="Filter resonance; inert for AMP"),
        Param(b"DEPTH", 100, 128, True, B, doc="Cutoff or gain modulation: negative/down, zero/static, positive/up"),
        Param(b"DECAY", 48, 128, True, P, doc="Envelope decay up to eight steps / gate length; inert for random"),
        Param(b"STEPS", 15, 64, True, W, labels=tuple(str(i) for i in range(1, 65)),
              doc="Euclidean cycle length 1..64 (stored as length minus one)"),
        Param(b"PULSE", 5, 65, True, W, labels=tuple(str(i) for i in range(65)),
              doc="Pulse count; values above STEPS are clamped to STEPS"),
        Param(b"ROT", 0, 64, True, W, labels=tuple(str(i) for i in range(64)),
              doc="Shift rhythm and captured values right, modulo STEPS"),
        Param(b"RATE", 1, 5, True, S, labels=("1/32", "1/16", "1/8", "1/4", "1/2"),
              doc="Division relative to the track speed; 1/16 = one track step"),
        Param(b"TYPE", 0, 5, True, S, labels=("LP", "BP", "HP", "AMP", "NOTCH"),
              doc="Two-pole low/high/band/notch filter response, or amplitude modulation"),
        Param(b"ATK", 0, 128, True, P, doc="Attack / gate edge / random slew, 0..one step"),
        Param(b"OUT", 0, 4, True, S, labels=("ENV", "GATE", "RAND", "LOOP"),
              doc="Pulse envelope, timed gate, random sample-and-hold, captured random"),
        Param(b"MIX", 127, 128, True, P, doc="Dry/wet; zero is exact passthrough"),
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
