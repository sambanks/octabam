"""RIG HOSTS -- a new part is born hosted: T1's FX2 = BusDelay, T5's =
BusVerb, T8's (the master) = the stock DELAY (Echo Freeze, for its beat
repeat), every other track's = SEND.

Three detours in the part-defaults initialiser (0x40005638), the routine
that gives a new part FX1 = FILTER and FX2 = DELAY per track with DELAY's
page bytes: the id writes (0x4000567e..0x40005695) become FX1 = NONE and
the FX2 id by track, and the two FX2 page-default loads (0x40005830,
0x40005840) read the track's own descriptor through the id table instead
of the stock DELAY's (Spectrum's id with FILTER's bytes was "muted and
quiet and modulated" on the unit, image 52). With the engines hidden from the FX2 chooser (remix `hidden`) and
locked to their host slot (`locked`), this is what makes a project made on
the unit host the bus with no stamp; an older project still needs
`ot_project.py host <project>`.

Measured under the port (22 Sep 2026): loading a project name the card does
not carry makes the firmware create one; its live FX2 ids read
6 9 9 9 7 9 9 8, FX1 0 x8 (NONE).
"""

from remix.schema import Category, Proof, Detour, Kind, Linked, Module

H = bytes.fromhex


def ids_inc(modules):
    """The four ids the unit writes, from the manifests. The stock DELAY
    need not be in the remix (its dispatch stays stock either way), so its
    id comes from the registry. T8 takes RETURNS in a remix that carries it
    (docs/proposals/RETURNS.md), the stock DELAY otherwise."""
    from remix import registry
    every = dict(registry.modules()); every.update(modules)
    return "".join(f"        .set    {name}, {every[key].menu.fx2_id}\n"
                   for name, key in (("ID_DELAY", "DELAY SERVER"),
                                     ("ID_VERB", "REVERB SERVER"),
                                     ("ID_SEND", "SEND"),
                                     ("ID_ECHO", "RETURNS" if "RETURNS" in modules
                                      else "DELAY")))


MODULE = Module(
    name="rig-hosts",
    key="RIG HOSTS",
    kind=Kind.CF_PATCH,
    category=Category.BUS, author="sambanks", author_url="https://github.com/sambanks",
    proof=Proof.PORT, proof_note="a new project born hosted under the port",
    doc="A new part is born hosted: T1 FX2 = BusDelay, T5 = BusVerb, T8 = the stock DELAY, the rest SEND.",
    linked=(Linked("righosts", "modules/rig-hosts/righosts.s", include=ids_inc),),
    detours=(
        Detour(0x4000567E, H("41f9400d47ad15903800" "41f9400d4ad1226f004413500008"), "righosts", "fx_ids",
               "part-defaults initialiser: FX1 = NONE, FX2 by track", kind="jmp", pad_to=24),
        Detour(0x40005830, H("43f9400d4ace41f1285e"), "righosts", "fx2_page1",
               "part-defaults initialiser: FX2 page-1 defaults from the track's own descriptor", kind="jmp", pad_to=10),
        Detour(0x40005840, H("43f9400d4ace43f12864"), "righosts", "fx2_page2",
               "part-defaults initialiser: FX2 page-2 defaults from the track's own descriptor", kind="jmp", pad_to=10),
    ),
)
