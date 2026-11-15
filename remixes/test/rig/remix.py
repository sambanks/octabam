"""rig -- the rig's selection with no ColdFire runtime, for the gates that
build it.

octabam-bus without USB, Octakit and the scene modules:
the bus, the three stations, TEMPO SYNC, CC MAP, MODE DEFAULTS, RIG HOSTS.
registry.fixture picks it for verify_cc_map and verify_ccfeedback (CC MAP on
the hosts under unicorn, no Runtime), verify_character and verify_one_bus.
Until 30 Sep 2026 the `usb` remix was this selection plus USB MIDI.
"""

from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    name="rig",
    family="rig", evidence=(Evidence(Level.EMULATOR),),
    doc="octabam-bus's delay and reverb bus and FX1 stations, without USB, Octakit or the scene modules: the fixture of the CC MAP, Character and one-aux gates.",
    modules=("REVERB SERVER", "DELAY SERVER", "SEND",
             "SPECTRUM", "CHARACTER", "MODULATION",
             "TEMPO SYNC", "CC MAP", "MODE DEFAULTS", "RIG HOSTS"),
    fallback="SEND",
    hidden=("REVERB SERVER", "DELAY SERVER"),
    named=("REVERB SERVER", "DELAY SERVER"),
    locked=("REVERB SERVER", "DELAY SERVER"),
    fx1=("SPECTRUM", "CHARACTER", "MODULATION"),
)
