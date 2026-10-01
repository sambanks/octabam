"""POST FADER -- the bus sends follow each track's fader, mute and solo.

A DRAM unit on the frame routine's call to the per-track DSP record builder
(0x4000d0e4): after it, each track whose FX2 is a bus send (SEND, id 0,
BusDelay's and BusVerb's own DEL/REV) has its DEL and REV scaled by
(L/128)^2 in the DSP-bound record, L the mixer's MAIN gain for the track
with mute and solo applied -- the mixer's own law. The knobs on the panel,
the Part and the CC lanes are untouched. A muted track sends nothing and
does not register as a bus client. No DSP code: the sends see a smaller
knob. See postfader.s for the measured addresses.

Not measured on a unit. Under the port: tools/verify/verify_postfader.py.
"""

from remix.schema import Category, Detour, Gate, Kind, Linked, Module, Proof

H = bytes.fromhex


def ids_inc(modules):
    """The three send-carrying FX2 ids, from the manifests (SEND is always in
    a remix that carries this module; the engines may not be)."""
    from remix import registry
    every = dict(registry.modules()); every.update(modules)
    return "".join(f"        .set    {name}, {every[key].menu.fx2_id}\n"
                   for name, key in (("ID_SEND", "SEND"), ("ID_DELAY", "DELAY SERVER"),
                                     ("ID_VERB", "REVERB SERVER")))


MODULE = Module(
    name="post-fader",
    key="POST FADER",
    kind=Kind.CF_PATCH,
    category=Category.BUS, author="sambanks", author_url="https://github.com/sambanks",
    proof=Proof.CHECK, proof_note="make check, 29 Sep 2026; not flashed",
    doc="The bus sends follow each track's fader, mute and solo: DEL/REV x (LEVEL/128)^2 "
        "in the DSP-bound record; a muted track sends nothing.",
    linked=(Linked("postfader", "modules/post-fader/postfader.s", dram=True, include=ids_inc),),
    detours=(
        Detour(0x4000d0e4, H("4eb940004bd4"), "postfader", "pf_frame",
               "frame routine: the record builder, then the sends x the tracks' mix gains",
               kind="jsr"),
    ),
    requires=("SEND",),
    gates=(Gate("tools/verify/verify_postfader.py"),),
)
