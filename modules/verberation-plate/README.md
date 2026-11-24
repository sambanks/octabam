# `verberation-plate` — VERB PLATE

[VERBERATION](../verberation/README.md) on PLATE REV's id `0x14`, in **PLATE** mode. In
[`octabam-verbs`](../../remixes/octabam-verbs/README.md) it is hidden (`Remix.hidden`): no chooser row and no knob
names. It has no DSP code of its own: `MenuEntry(dsp_of="VERBERATION")` points its id at VERBERATION's init and proc
on both payloads, so an id that reaches the engine runs VERBERATION. Its defaults are PLATE's knob values;
[VERB PARTS](../verb-parts/README.md) writes them, with VERBERATION's id, over a Part saved with PLATE REV.

Knobs, modes, measurements and costs are VERBERATION's.
