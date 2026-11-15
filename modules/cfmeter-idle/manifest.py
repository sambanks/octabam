"""CF METER IDLE -- main's idle loop timed on DMA timer 3, added into CF
METER's idle counter (`idle.s`). Replaces main's last init call and the
`bras .` after it.

The ColdFire port advances its clock only at main's stock `bras .`
(`tools/emu/ot_emu/rtos.cpp`, `g_mainSpin`), so an image carrying this
loop does not load a project under the port; CF METER alone is port-gated.
"""

from remix.schema import Category, Detour, Kind, Linked, Module, Evidence, Level

MODULE = Module(
    name="cfmeter-idle",
    key="CF METER IDLE",
    kind=Kind.CF_PATCH,
    category=Category.REFERENCE, author="sambanks", author_url="https://github.com/sambanks",
    evidence=(Evidence(Level.UNIT, unit="MKII", who="sambanks", date="2026-10-16",
        note="cursory testing on Sam's MKII (owner report, 16 Oct 2026); boots and loads a project under the port "
             "(28 Sep 2026)"),),
    doc="Probe: main's idle loop timed, for CF METER's idle-time slot.",
    requires=("CF METER",),
    linked=(Linked("cfmeter_idle", "modules/cfmeter-idle/idle.s", dram=True),),
    detours=(
        Detour(0x4001fc96, bytes.fromhex("4eb940098a2c"), "cfmeter_idle", "m_idle",
               "main's last init call; the stub never returns (it replaces the idle `bras .`)"),
    ),
)
