# `host-lock` — HOST LOCK

A ColdFire patch for the rig: on T1 and T5 the FX2 chooser changes nothing,
so the bus servers [RIG HOSTS](../rig-hosts/README.md) puts there
(BusDelay on T1, BusVerb on T5) stay. The servers are hidden from the
chooser and locked to their host slot, so before this a pick on T1 or T5
replaced the server and nothing on the unit brought it back
(`ot_project.py host` on the card, or a new part, did).

The FX2 chooser's input layer has one record per key, 0x1a bytes apart;
YES's handler word (`0x400bc374`, stock value `0x40052474`: the FX2 machine
select, which Octakit's recipe wraps) is repointed to `hostlock.s`. On T1
or T5 (the current-track byte `0x100b14cc` = 0 or 4) it jumps to the NO
handler (`0x4003d440`: the chooser closes, nothing changed); on any other
track to the select, as before. Octakit's runtime and the sites her recipe
claims are untouched.

## Measured

- Under the port (30 Sep 2026, `tools/verify/verify_hostlock.py`,
  `bottleservice-pf` with a stress project): FUNC + FX2, DOWN, YES on T1
  and T5 runs NO and never the select; on T2 and T8 it runs the select
  (through Octakit's wrapper) and never NO; no halt.

## On the unit

- RIGPF8BP (`bottleservice-pf`, BUILD=16), an MKII, 30 Sep 2026: a pick on
  T1 or T5 changes nothing and their servers stay.

## Open

- A project whose T1 or T5 FX2 is already something else keeps it: the
  lock keeps whatever is there. `ot_project.py host` puts the servers back.
