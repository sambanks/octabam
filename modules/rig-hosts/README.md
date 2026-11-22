# `rig-hosts` — RIG HOSTS

A ColdFire patch: a new part is born hosted. The part-defaults
initialiser (`0x40005638`, the routine that gives a new part FX1 = FILTER
and FX2 = DELAY on every track) is detoured three times: the FX2 default
load jumps to `righosts.s`, which writes FX1 = NONE and the FX2 id by
track (BusDelay on T1, BusVerb on T5, the stock DELAY, Echo Freeze, for
its beat repeat, on T8 the master, SEND on every other track); and each
track's FX2 page-1 and page-2 defaults come from that track's own
descriptor through the id table instead of the stock DELAY's. The ids
come from the manifests at build time.

With the engines hidden from the FX2 chooser and locked to their host
slot, this is what makes a project made on the unit host the bus without
a chooser row or a stamp. An older project keeps its stored ids: host it
with `python3 tools/hw/ot_project.py host <project>`.

## Open

- A project born on the unit under the current module.
