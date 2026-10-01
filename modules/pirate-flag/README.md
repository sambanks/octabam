# PIRATE FLAG

The OS's boot animation replaced by a waving Jolly Roger.

## What changes and what cannot

A boot draws on the panel in two stages:

1. **The bootstrap in NOR** shows the Octatrack logo and the version line
   before any OS runs. Those are NOR's, the same whatever image boots
   (`docs/proposals/FIRMWARE_SWITCHER.md` step 4). This module does not
   touch them, and nothing short of a bootstrap reflash could. That is not
   worth the recovery path.
2. **The MAIN OS's own animation**: 2.8 s of a sprite field on DTIM3's
   clock, in the LED/key-scan task (`0x400559c6..0x40055b7a`; the port
   skips it unless given `--boot-logo`). This module takes over this one.

Each OS image plays its own animation. So:

- an image carrying PIRATE FLAG shows the flag every time it boots;
- after an OS SWITCH, the flag shows on the way into an image that carries
  it (DOOM.OBI does);
- for the whole system, the flashed image has to carry it. The way to try
  that without a flash is an `.OBI` of your home remix with `"PIRATE FLAG"`
  added, booted through OS SWITCH.

## How

One `jsr` detour at the animation's per-frame flush (`0x40055aa2`,
`jsr 0x40013abc`). `pirate_frame` writes the flag's 128 columns into the
surface's plane (`d6 + 12`) and then jumps to the flush stock called. The
cloth, from column 12 on, moves 32·sin((x − frame)·2π/64)·(x − 12)/1200
rows: the hoist stays still and the fly swings about ±3 rows. The frame
number is `d2` (0..559; set at `0x40055b72`, untouched from `0x40055a24`
to the flush). The LEDs fade as stock fades them.

The art is made from shapes in `art.py` (a circle cranium, eye and nose
holes, knuckled bones) and written into `remix.inc` at build time.

## Measured (verify_pirateflag, under the port with `--boot-logo`)

- ✅ The detour runs every frame to the last (559).
- ✅ Frame 280 (kept in `pirate_snap` for the gate) equals `art.py` waved by
  the same integer arithmetic, bit for bit. The PNG goes to
  `out/pirate-flag/frame280.png`.

🟡 Upright on the unit: the column layout is PANEL.md's measured one
(column 63 − y from the MSB, which is bit y from the LSB). `art.py` was
first written with the opposite bit order and drew upside down under the
port.
