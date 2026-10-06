"""bottleservice -- the rig plus USB MIDI, USB audio out (the master track), and KITS.

the rig's selection (the bus, three stations, hosts, TEMPO SYNC, CC MAP, CC FEEDBACK, MODE
DEFAULTS, TEMPO BUS, SCENES P2; `bamsep26` until 27 Sep 2026) and PLOCKS P2
(page-2 parameter locks, since 3 Oct 2026) with USB MIDI and
USB AUDIO OUT MASTER (two channels: track 8, the master track, post-FX
pre-fader), on the DRAM platform,
and KITS (255 Kits per project through the stock Part slots; Em's Octakit
with the SCENES KITS and SCENES P2 KITS bridges until 6 Oct 2026). On Sam's
MKII since image 88 (27 Sep 2026). USB AUDIO IN CD and USB CROSSBAR were in
it from 28 Sep to 4 Oct 2026 and were removed: with them and a computer on
the USB port, PLAY halted the unit in Octakit's pattern-apply check (images
95 and 97).
"""

from remix.schema import Pin, Proof, Remix

REMIX = Remix(
    name="bottleservice",
    family="rig", proof=Proof.HARDWARE, proof_note="Sam's MKII (image A6 with KITS, 6 Oct 2026; images A0-A3 with Octakit, 4 Oct 2026)",
    doc="The delay and reverb bus (BusDelay on T1's FX2, BusVerb on T5's FX2, SEND on every other track's FX2, the stock DELAY on T8) + SPECTRUM, CHARACTER and MODULATION on FX1 + USB MIDI + USB AUDIO OUT MASTER (T8 to the computer) + KITS.",
    modules=("REVERB SERVER", "DELAY SERVER", "SEND",
             "SPECTRUM", "CHARACTER", "MODULATION",
             "TEMPO SYNC", "CC MAP", "CC FEEDBACK", "MODE DEFAULTS", "RIG HOSTS", "TEMPO BUS",
             "USB MIDI", "USB AUDIO OUT",
             "STORE", "KITS",
             "SCENES P2", "PLOCKS P2",
             "DELAY",    # the stock DELAY keeps its chooser row: T8 hosts it (4 Oct 2026)
             "FX2 LOCK"),   # and the chooser cannot change any track's FX2 (4 Oct 2026, image A1)
    fallback="SEND",
    hidden=("REVERB SERVER", "DELAY SERVER"),
    host_slots=(("DELAY SERVER", 2), ("REVERB SERVER", 2)),
    locked=("REVERB SERVER", "DELAY SERVER"),
    fx1=("SPECTRUM", "CHARACTER", "MODULATION"),
    settings={("octabam.usb-audio-out", "LAYOUT"): Pin("MASTER")},
)
