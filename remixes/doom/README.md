# doom

An `.OBI` that boots into Doom: stock's fourteen effects and OS SWITCH (as
`base`), plus DOOM and PIRATE FLAG.

```bash
make obi REMIX=doom OBI=DOOM      # out/DOOM.OBI; with DOOM1.WAD in the card root
```

Boot it from the flashed image's MAIN MENU > OS or its boot picker, never
by flashing it: flashed, it would boot into Doom at every power-on.
Doom's QUIT, or FUNC + STOP, resets back to the flashed image.
`modules/doom/README.md` has the controls.

## Where it has run

- Under the ColdFire port (30 Sep 2026): `verify_doom` (title to E1M1,
  fire, the exit, the chainload) and `verify_pirateflag`.
- Not yet on a unit.
