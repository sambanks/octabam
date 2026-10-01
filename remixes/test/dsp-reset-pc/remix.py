"""The DSP reset probe WITH its positive control: OS SWITCH's park makes a
listening boot ROM on the unit, so the probe's "no answer" can be trusted."""

from remix.schema import Proof, Remix

# The same probe as `dsp-reset`, plus OS SWITCH -- whose DSP park (host
# command $12) is the only way to turn a running core into a boot-ROM
# loader. The probe's last step parks core 0 and asks it the same question:
# it MUST answer. Without that, "no core answered" rests on the port's model
# for its other half, and a model is not the machine.
#
# DARK REV is off the chooser: its words hold OS SWITCH's DSP loader.
REMIX = Remix(
    name="dsp-reset-pc",
    family="probes", proof=Proof.PORT,
    proof_note="the negative, the modelled positive and the PARKED positive, all "
               "under the port (verify_dspreset)",
    doc="dsp-reset plus OS SWITCH: the probe's positive control, a parked core that "
        "must answer, so the no is worth something.",
    modules=("DSP RESET PROBE", "OS SWITCH", "FILTER", "EQUALIZER", "DJ EQ", "PHASER",
             "FLANGER", "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV"),
    fallback="NONE",
)
