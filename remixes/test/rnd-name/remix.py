from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    name="rnd-name",
    family="test",
    evidence=(Evidence(Level.RENDER,
        note="RND NAME smoke"),),
    doc="smoke: RND NAME alone",
    modules=("RND NAME",),
    fallback="NONE",
)
