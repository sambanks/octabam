"""HELLO-DRAM -- the reference minimal ColdFire build: one DRAM unit, alone.

The smallest image the DRAM platform can produce: HELLO DRAM and nothing
else. No chooser row of ours, no DSP words, one boot-site redirect and an
append of a few hundred bytes. It is the loader path's pipeline canary the
way `hello` is the DSP path's: if this stops building, or the boot
verifier stops finding the unit at its linked address, the platform moved
under everyone.
"""

from remix.schema import Remix

REMIX = Remix(
    name="hello-dram",
    doc="Reference minimal ColdFire build: the HELLO DRAM unit, alone.",
    modules=("HELLO DRAM",),
    fallback="NONE",
)
