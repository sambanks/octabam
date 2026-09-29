"""DSP RESET PROBE -- a probe: can the ColdFire reset the DSP in hardware?

OS SWITCH's cost is 40 DSP words in BOTH payloads: the soft reset restarts
the ColdFire and not the DSP, so each core has to park itself in a loader
before the reset or the next OS's upload finds no boot ROM (measured on the
unit, BOOT TRACE build 4). They come out of the region modules place their
effects in, so a build that fills payload A has to give the switcher up and
becomes a target you can switch INTO but never out of.

If the ColdFire can reset the DSP the park disappears -- no DSP words, no
per-payload budget, every image switchable both ways. One candidate is
left: RSTOUT, the reset controller's output to the board (RCR bit 6,
FRCRSTOUT) -- ANSWERED NO on an MKII, 29 Sep 2026 (README.md). The other,
the pin the bootstrap drives once at 0x400e0dce, is
retracted -- 0xfc0a4024 is the data DIRECTION register of the port whose
output register 0xfc0a400c is the DSP core select, so that write makes the
select pin an output (docs/firmware/ARCHITECTURE.md, the GPIO block map).

The instrument is the boot ROM's own protocol: seven words (micro.asm) that
answer with a magic only if a ROM is listening, run once with no pulse (the
control -- a running payload must NOT answer) and then per core after it.
probe.s is the procedure, the MIDI notes and the risk; README.md is how to
run it on a unit without flashing anything.
"""

from remix.schema import Category, Detour, Gate, Kind, Linked, Module, Proof

H = bytes.fromhex


def _include(modules):
    """PARK: whether this remix carries OS SWITCH, whose DSP park (host
    command $12 on vector P:$24) is the only way to turn a running core
    into a boot-ROM loader. With it the probe can run a POSITIVE control on
    the unit -- park a core, ask it the same question, and it must answer
    -- which is what makes the negative result worth anything. Without it
    that step is assembled out."""
    return f"        .set    PARK, {1 if 'OS SWITCH' in modules else 0}\n"


MODULE = Module(
    name="dsp-reset-probe",
    key="DSP RESET PROBE",
    kind=Kind.CF_PATCH,
    category=Category.REFERENCE, author="sanderlegit", author_url="https://github.com/sanderlegit",
    proof=Proof.HARDWARE,
    proof_note="an MKII, 29 Sep 2026: RSTOUT (RCR bit 6) does NOT reset either DSP core "
               "-- both pulse widths reported no boot ROM, with BOTH controls clean on "
               "the same unit: a parked core answered (`dsp-reset-pc`, notes 50/1 51/1) "
               "and a running payload did not; `verify_dspreset` gates both remixes",
    doc="Probe: does RSTOUT (RCR bit 6) reset the DSP? A boot-time report on MIDI OUT, "
        "so OS SWITCH could drop its 40 words of DSP park code.",
    linked=(Linked("dsp_reset_probe", "modules/dsp-reset-probe/probe.s", cpu="5475",
                   include=_include),),
    detours=(
        Detour(0x40000518, H("207c46025de0"), "dsp_reset_probe", "dr_entry",
               "the boot after the DSP upload returned, before the panel link, the card "
               "and the RTOS: the whole probe"),
    ),
    gates=(Gate("tools/verify/verify_dspreset.py"),),
)
