# bottleservice-pf-flag

`bottleservice-pf` plus PIRATE FLAG: the home rig, with its boot animation
as a waving Jolly Roger.

```bash
make obi REMIX=bottleservice-pf-flag OBI=PIRATE    # try it through OS SWITCH first
make image REMIX=bottleservice-pf-flag BUILD=<n>   # then, if wanted, flash it: the flag at every power-on
```

The bootstrap's logo and version line before the animation are NOR's and
do not change (`modules/pirate-flag/README.md`).

## Where it has run

- Built (30 Sep 2026). PIRATE FLAG is gated under the port in `pirate-flag`
  and `doom`, **not in this remix**. Under the port with `--boot-logo`, the
  rig's own animation does not run: the animation function (`0x4005596c`)
  is entered at ~54 M instructions, as in `base`, and never reaches its
  frame loop. Stock `bottleservice-pf`, without the flag, does the same,
  so the cause is in the rig's boot under the port, not the flag. Unknown
  which. On a unit the rig shows its boot animation, so the flag is
  expected to show there. 🟡 Falsified by the stock logo still showing
  after a switch to PIRATE.OBI.
- Not on a unit.
