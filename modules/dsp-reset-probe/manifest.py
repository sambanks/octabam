"""DSP RESET PROBE -- a probe: can the ColdFire reset the DSP in hardware?

OS SWITCH's cost is 40 DSP words in BOTH payloads: the soft reset restarts
the ColdFire and not the DSP, so each core has to park itself in a loader
before the reset or the next OS's upload finds no boot ROM (measured on the
unit, BOOT TRACE build 4). Payload A of a full remix has no room for them,
which is why `bottleservice-ret`'s stage-B builds are boot-only targets:
you can switch INTO them, never out of them.

If the ColdFire can reset the DSP the park disappears -- no DSP words, no
per-payload budget, every image switchable both ways. One candidate is
left: RSTOUT, the reset controller's output to the board (RCR bit 6,
FRCRSTOUT). The other, the pin the bootstrap drives once at 0x400e0dce, is
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

MODULE = Module(
    name="dsp-reset-probe",
    key="DSP RESET PROBE",
    kind=Kind.CF_PATCH,
    category=Category.REFERENCE, author="sanderlegit", author_url="https://github.com/sanderlegit",
    proof=Proof.PORT,
    proof_note="`verify_dspreset`: the probe reports no reset on the plain port and both "
               "cores in their ROM when the port models the pin -- the instrument fires "
               "both ways. The candidate itself is unmeasured: only a unit can answer it",
    doc="Probe: does RSTOUT (RCR bit 6) reset the DSP? A boot-time report on MIDI OUT, "
        "so OS SWITCH could drop its 40 words of DSP park code.",
    linked=(Linked("dsp_reset_probe", "modules/dsp-reset-probe/probe.s", cpu="5475"),),
    detours=(
        Detour(0x40000518, H("207c46025de0"), "dsp_reset_probe", "dr_entry",
               "the boot after the DSP upload returned, before the panel link, the card "
               "and the RTOS: the whole probe"),
    ),
    gates=(Gate("tools/verify/verify_dspreset.py"),),
)
