from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    name="pattern-mute",
    family="test",
    evidence=(Evidence(Level.EMULATOR,
        note="PATTERN MUTE smoke"),),
    doc="smoke: PATTERN MUTE alone, with STORE (pmute.work)",
    modules=("PATTERN MUTE", "STORE"),
    fallback="NONE",
)
