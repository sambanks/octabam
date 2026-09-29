"""The DSP reset probe: does RSTOUT reset the DSP, so OS SWITCH could drop
its DSP park code? Stock effects and the probe, nothing else."""

from remix.schema import Proof, Remix

# os_switch=False, and no BOOT TRACE: the probe's question is the DSP's reset
# line, and every variable that is not that one is left at stock. The probe
# reports on MIDI OUT itself, and when nothing answers it leaves the DSP out
# of step until a power-cycle (modules/dsp-reset-probe/probe.s, "the
# restore") -- which OS SWITCH's own gates would rightly refuse to call a
# working boot. The image is still a switch TARGET, since a target needs no
# OS SWITCH of its own, so trying it costs no flash cycle:
# `make obi REMIX=dsp-reset OBI=DSPRESET`.
REMIX = Remix(
    name="dsp-reset",
    family="probes", proof=Proof.PORT,
    proof_note="the probe reports both ways under the port (verify_dspreset)",
    doc="probe: RSTOUT (RCR bit 6) against the DSP's boot ROM, reported on MIDI OUT at boot.",
    modules=("DSP RESET PROBE", "FILTER", "EQUALIZER", "DJ EQ", "PHASER",
             "FLANGER", "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
    os_switch=False,
)
