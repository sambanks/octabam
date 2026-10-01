# doom

An `.OBI` that boots into Doom: OS SWITCH, DOOM and PIRATE FLAG. No stock
effect: their DSP words are where DOOM's sound hook is placed, and nothing
in a Doom image plays a track.

```bash
make obi REMIX=doom OBI=DOOM                           # out/DOOM.OBI; DOOM1.WAD in the card root
python3 modules/doom/music.py DOOM1.WAD out/doom/card/DOOMMUS   # the music, for the card's /DOOMMUS/
```

Boot it from the flashed image's MAIN MENU > OS or its boot picker, never
by flashing it: flashed, it would boot into Doom at every power-on.
Doom's QUIT, or FUNC + STOP, resets back to the flashed image.
`modules/doom/README.md` has the controls.

## Where it has run

- Under the ColdFire port (30 Sep 2026): `verify_doom` (title to E1M1,
  fire, the exit, the chainload, the sound on MAIN) and `verify_pirateflag`.
- On an MKII (30 Sep 2026, the image before sound): boots into Doom from the
  picker, the picture upright, the game at Doom's speed. The sound build has
  not run on a unit.
