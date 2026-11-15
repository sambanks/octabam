from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    name="pattern-mute",
    family="test",
    evidence=(Evidence(Level.EMULATOR,
        note="PATTERN MUTE smoke"),),
    doc="smoke: PATTERN MUTE alone",
    modules=("PATTERN MUTE",),
    fallback="NONE",
)
