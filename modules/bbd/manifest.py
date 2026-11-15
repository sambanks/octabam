"""BBD -- a clocked bucket-brigade delay, one tap, FX2.

The mono sum goes through the chain: a Pade tanh folded into a 2:1 feedback
compressor, an 8th-order Butterworth anti-alias filter at a third of the
clock, a bucket line clocked at 5.1..20.5 kHz (1,023 / 4,095 buckets
read through a charge-transfer polynomial plus noise, held between ticks), a
7th + 2nd order reconstruction filter at the same cutoff, a DC blocker and
the expander. FDBK returns the wet through a feedback tilt (TONE, FREQ),
governed by LIM; FRZ fades the input and sustains the loop, 127 loops the line; HPF is a
20..400 Hz high-pass on the input (0 off).
Free-running TIME: the DSP side has no tempo word.

Reads the allocator at init (x:>$213) and uses 8,250 words of an FX2 slot's
16,384-word Y buffer: the ring at base + $0000..$0FFF, the filter
coefficients at base + $2000..$2039 (README, "Memory"); an FX1 slot (3,072
words) is too small, so FX2 only.
State lives in r7 + $00..$5a. bbd_ref.py is the float model the DSP is
proven against (tools/verify/verify_bbd.py).

The stop kill (STOP, STOP, STOP) reaches BBD as it reaches the stock reverbs:
kill.s adds BBD's id to the ColdFire pass that zeroes their slots, BBD's only
(hidden slot 11, 127 otherwise), and BBD cuts to dry and clears its line."""

from remix.schema import (Gate, Category, Evidence, Level, BusRole, Claims, Detour, DspSection, Formatter, Harness,
                          Kind, Linked, MenuEntry, Module, Param, YBase)

FX2_ID = 0x1b


def id_inc(modules, remix):
    """BBD's id in this remix (`registry.assign_ids`), for kill.s."""
    return f"        .set    BBD_ID, {modules['BBD'].menu.fx2_id}\n"

MODULE = Module(
    name="bbd", key="BBD", kind=Kind.DSP_EFFECT,
    category=Category.TRACK, author="JamCones", author_url="https://github.com/JamCones",
    evidence=(Evidence(Level.UNIT, unit="MKII", who="JamCones", date="2026-10-17",
        note="JamCones' MKII, BBDOB4 (remixes/test/bbd, BUILD 4), 17 Oct 2026"),),
    doc="Clocked BBD delay: compander, clock/3 filters, bucket noise, freeze, governor; FX2.",
    menu=MenuEntry(fx2_id=FX2_ID, donor_desc=0x400d58b8,
                   abbr=b"BBD", fullname=b"BBD DELAY", build_tag=False),
    params=(
        Param(b"TIME", 64, active=True, formatter=Formatter.PLAIN,
              doc="delay time: 50-200 ms with STGS 1024, 200-800 ms with 4096"),
        Param(b"FDBK", 0, active=True, formatter=Formatter.PLAIN,
              doc="feedback through TONE; centred TONE rings long, full TONE oscillates from ~45"),
        Param(b"FRZ", 0, active=True, formatter=Formatter.PLAIN,
              doc="freeze: the input fades out and FDBK holds the repeats; 127 loops the line exactly"),
        Param(b"TONE", 64, 128, active=True, formatter=Formatter.BIPOLAR,
              doc="feedback tilt: up = treble up, bass down; down = 9 dB bandpass peak at FREQ"),
        Param(b"FREQ", 64, active=True, formatter=Formatter.PLAIN,
              doc="centre of TONE's bandpass peak, 400 Hz to 2 kHz; heard only with TONE below centre"),
        Param(b"MIX", 40, active=True, formatter=Formatter.PLAIN,
              doc="0 to 64 raises the wet up to unity over the whole dry; 64 to 127 fades the dry out"),
        Param(b"STGS", 0, count=2, active=True, formatter=Formatter.STEPPED,
              labels=("1024", "4096"),
              doc="BBD stages, 1024 or 4096: sets the delay range; a change fades out and clears the line"),
        Param(b"", 0),
        Param(b"LIM", 127, active=True, formatter=Formatter.PLAIN,
              doc="feedback limiter, 0 is off; higher settings hold self-oscillation at a lower level"),
        Param(b"", 0),
        Param(b"HPF", 0, active=True, formatter=Formatter.PLAIN,
              doc="0 is off; above that, a 12 dB/oct high-pass on the signal entering the line, 20 to 400 Hz"),
        Param(b"", 127),                     # hidden: the stop kill's flag, 0 while it holds (kill.s)
    ),
    dsp=DspSection(asm="modules/bbd/bbd.asm", priority=16,
                   bus_role=BusRole.NONE, ybase=YBase.NEVER,
                   r7_latch_slot=None, gate_label=None),
    claims=Claims(stock_instance_buffer=True, buffer_words=0x203A),   # 8,250: up to the FREQ bandpass at +$2039
    linked=(Linked("bbd_kill", "modules/bbd/kill.s", include=id_inc),),
    detours=(Detour(0x40004d0c, bytes.fromhex("302a00380680ffffffec"), "bbd_kill", "bbd_kill",
                    "the stop kill's reverb test: BBD's id too, slot 11 only", pad_to=10),),
    harness=Harness(layout_char=None, is_server=False),
    gates=(Gate("tools/verify/verify_bbd.py", remix_arg=False),
           Gate("tools/verify/verify_ids64_load.py", remix_arg=False, venv=True)),     # BBD is the module the 64-id test image carries on 0x25
    dear={"TIME": 0, "FDBK": 127, "TONE": 0, "FREQ": 127, "MIX": 64, "STGS": 1, "HPF": 64},
)
