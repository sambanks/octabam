# DOOM

id Software's Doom on the Octatrack's panel, booted as an OS image of its
own through OS SWITCH, and quit back to the flashed OS.

Markers as in `docs/firmware/CHIP.md`: ✅ measured (under the ColdFire port
unless it says the unit), 🟡 inferred, with what would falsify it.
On an MKII: boots into Doom from the picker, picture upright, Doom's speed
(30 Sep 2026); the music from the card and the faster turning (1 Oct 2026,
ffa6ff78, after two freezes found by bisect: `docs/contributing/FAILURE_MODES.md`).

## Use

```bash
make obi REMIX=doom OBI=DOOM          # out/DOOM.OBI (1.3 MB)
```

1. Copy `out/DOOM.OBI` **and your `DOOM1.WAD`** to the card root. The WAD
   is yours, like the stock image, and never goes in the repo. The
   shareware v1.9 `DOOM1.WAD` (4,196,020 B, sha1 `5b2e249b9c51...`) is the
   one this was built and gated against. Name it `DOOM1.WAD`. For music,
   also copy `/DOOMMUS/` (below).
2. On the flashed image (any build with OS SWITCH), either pick `DOOM` in
   the boot picker at power-on, or go to MAIN MENU > OS > `DOOM` > YES.
3. The unit resets into the DOOM image. You'll see the Jolly Roger (PIRATE
   FLAG, the OS's boot animation), then `LOADING DOOM1.WAD`, then Doom's
   title screen. The project is not loaded.
4. To leave: Doom's own menu, QUIT GAME > YES, or **FUNC + STOP** at any
   time. Either resets the unit with no switch pending, which boots the
   flashed image. A power-cycle does the same.

With no `DOOM1.WAD` on the card, the DOOM image boots on as a normal OS
(stock effects, OS SWITCH), so it is never a dead end.

## Controls

| Octatrack | Doom |
|---|---|
| UP / DOWN | forward / back |
| LEFT / RIGHT | turn (~1.75x Doom's keyboard rate in a level) |
| YES | fire; ENTER and `y` in menus and prompts |
| NO | use / open; back and `n` in menus |
| FUNC (held) | run |
| CUE (held) | strafe with LEFT / RIGHT |
| PATTERN / BANK | strafe left / right |
| trigs 1-7 | weapons 1-7 |
| TEMPO | automap |
| STOP or PROJ | menu (ESC) |
| PLAY | ENTER |
| knob A | turn, ~3.5 degrees a detent |
| **FUNC + STOP** | **leave Doom: back to the flashed OS** |

Every other key and knob is swallowed while Doom has the panel.

## Sound

- **Effects** are mixed live on the ColdFire (`octa/doom_audio.c`): the
  WAD's DMX lumps (8-bit, mostly 11,025 Hz), eight channels with Doom's own
  volume and separation, stepped to 44.1 kHz into a 186 ms stereo ring kept
  ~70 ms ahead.
- **Music** is the WAD's own MUS, rendered once on your machine by
  `modules/doom/music.py`: libADLMIDI's OPL3 emulator with bank 16, "DMX
  (Bobby Prince v1)" (Doom's instrument set, the Sound Blaster sound),
  then ffmpeg to IMA ADPCM, mono, 22,050 Hz (about 20 MB for the
  shareware's 13 songs). Copy the folder to the card as `/DOOMMUS/`. Doom
  streams each song from there in 4 KB reads and loops it. No folder, no
  music; everything else is the same. The files are yours, like the WAD,
  never the repo's.
- **The path out.** Once per DSP frame, the frame interrupt's state 7
  (`0x40004bc0`, USB AUDIO IN's site, so a remix carries one of the two)
  takes 16 frames from the ring and sends them to core 0 by host-port DMA.
  On the next frame, `doom_mix.asm` (33 words, hooked at `P:0x2d5`, right
  after the mixdown) adds them into the ring words that are MAIN L/R, with
  the store's limiter. So the sound is on MAIN and the cue (which is mixed
  from MAIN) whatever the mixer says, with no project and no track.
  Every DSP instruction form in it has a site in stock payload A.

## The screen

The panel is 128 × 64 at one bit per pixel. It has a second plane nobody
understands yet, so there are no greys (`docs/firmware/PANEL.md` section 1).
Doom's 8-bit frame (doomgeneric built `CMAP256`) is box-filtered to
luminance through a per-palette table, run through a 3 × 3 unsharp mask,
contrast-stretched ((v − 20) × 1.6) and ordered-dithered 4 × 4. Doom
renders at low detail (160 columns, each doubled): the panel shows 128, so
nothing visible is lost.

- **In a level**, with the status bar up (screen size 10, the default),
  only the 3D view's 168 rows are drawn, into the top 56 panel rows. The
  bottom 8 rows are a line of text: `HP 100  AR 0  AMMO 50`. The status
  bar itself is unreadable at 128 pixels wide.
- **Everything else** (the title, menus, the automap, intermissions) is the
  whole 200 rows scaled to 64.
- **A menu or a prompt** is drawn on black: d_main's calls to `M_Drawer`
  go to `octa_M_Drawer` (an objcopy symbol redirect in the Makefile, so the
  upstream stays untouched). It clears the frame first, and the luminance
  table is tripled for that frame. Over the dithered scene the menu was
  unreadable. On black, NEW GAME ... QUIT GAME and the skull cursor read
  clearly (checked under the port).

Chosen by eye against a 320 × 200 frame dumped from the port (E1M1's first
room): error diffusion crawls from frame to frame, gamma ½ washes the walls
out, and a plain stretch loses the pillars against their own textures.

## How it works

- **Build.** doomgeneric (`upstream/`, a submodule at `dcb7a8d`, GPL-2.0)
  and `octa/` compile with `m68k-elf-gcc -mcpu=54455 -O2`. No libc for
  m68k-elf is installed here, so `octa/libc.c` is a small freestanding one,
  with only what `nm -u` asks for. Everything is partially linked
  (`ld -r`, with libgcc) into one object, `doom.o`. Its `.bss` is renamed
  to data so the loader's depack zeroes it.
  `tools/remix/platform_build.py` links a `Linked` source ending in `.o` as
  its Makefile makes it. That was the one change to the build, and refhash
  checked all 24 configurations bit-identical after it.
- **Boot.** The detours are OS SWITCH's two boot-picker sites (`0x4002574c`,
  the LOAD PROJECT post, and `0x4002573e`, the LOADING FILES post), taken
  over with `Override` and handed to `osw_bootpick` / `osw_bootfiles` when
  DOOM passes. The first to fire reads `/DOOM1.WAD` and holds the load: it
  returns without posting, as the picker does. ✅ Both paths are gated.
- **Memory.** 2,728 pages off the top of the audio page arena
  (`0x45029de0..0x46025de0`). Doom uses the lower 2,200: the WAD at the base,
  then the heap (the 6 MB zone, the 256 KB frame), then a 256 KB stack at
  `0x45d0dde0`. The top 528 pages are left alone because stock zero-fills
  them at every project load (Octakit's window, `docs/contributing/PLACEMENT.md`).
  Code and data (740 KB) sit in the platform runtime at `0x40a955e0`, below
  OS SWITCH's mailbox. The arena keeps 59 MB for samples.
- **Running.** A soft timer on the sys tick (~120 Hz on the unit, measured
  by the boot picker) counts out 35 calls a second. Each call is posted to
  the UI task as a deferred call, with never more than one outstanding.
  There `doom_run` switches to Doom's own stack (the UI task's is 2 KB) and
  runs one tic (`-singletics`). Doom's waits (the screen wipe) sleep on
  virtual time, so nothing spins.
- **Keys.** An input layer with a record for every code `0x00..0x3f`, so
  nothing reaches the stock layers. While FUNC is held, the dispatch uses
  the layer its record's `+0xe` names (stock FUNC's is `0x400bfa32`, read
  from the image). DOOM's names one where STOP goes home. ✅ Without it,
  FUNC + STOP never reached Doom's handler at all.
- **Leaving.** `osw_reset` from OS SWITCH: the DSP parked, the MKII panel's
  `60 02`, the RCR soft reset. There is no mailbox, so the flashed image
  boots. ✅ The call is reached. The reset itself is OS SWITCH's
  hardware-proven path.

## Measured (verify_doom, under the port)

- ✅ Sound: under `--dsp`, one block per DSP frame reaches core 0 (24,805 in
  a 9 s session), with 3 % underruns (the start and the level load). MAIN
  L/R carry -30 dBFS rms where no project plays, and the music opens from
  the card.

- ✅ Boots on fresh SRAM (the LOAD PROJECT post) and on SRAM that knows the
  card (the LOADING FILES post). Either way, DOOM takes the first post.
- ✅ D_DoomMain runs to the game loop, and PLAY × 4 gets from the title to
  E1M1. It is our own game, not the title demo, and YES fires the pistol
  (clip below a new game's 50).
- ✅ With no WAD, the boot is handed to OS SWITCH's hook and Doom never runs.
- ✅ FUNC + STOP reaches `osw_reset`.
- ✅ Staged by OS SWITCH (the mailbox, body and stage as `osw_load` writes
  them), the image chainloads (status RUN) and goes straight into Doom.
- ✅ A tic costs ~2.5 M ColdFire instructions, from the watch timestamps
  in the port, median over 200 tics in E1M1, interrupts included: 1.6 M
  for the game and render, 0.95 M for the downscale. The first draft (high
  detail, 32-bit frame, a divide per pixel) cost 10 M: 5.5 M and 4.5 M.

## Not known until it runs on the unit

- ✅ **The sound on the unit** (1 Oct 2026): the music plays through the
  frame transfer and the DSP hook. Not yet reported: clicks or gaps over a
  long session, and the effects' levels against the music.

- 🟡 **Frame rate.** 2.5 M instructions a tic is ~10 ms at one instruction
  a cycle at 264 MHz. Doom's renderer misses a 32 KB cache a lot, so
  15–20 ms is likelier, which is still inside 35 tics/s (28.6 ms). A slow
  tic slows the game; it never skips. Falsified by a visibly slow game.
- 🟡 **The panel.** The window's plane layout is the one `lcd_view.py`
  composites and PANEL.md measured for the page. Upside down or mirrored on
  the unit would falsify it (one line in `mono.c`, `b = 63 - y`, flips it).
- 🟡 **Starvation.** A tic runs in the UI task (priority 3) for tens of
  milliseconds. Lower-priority tasks (the engine, idle) only run between
  tics. Nothing needs them while Doom plays, but that is inferred.
- 🟡 **Flush tearing.** The frame is built off-screen and copied in one
  `memcpy`. The panel flush runs in another task and could still catch
  half a copy.
- 🟡 **Card reads at boot.** 4 MB at 8 sectors a call, like OS UPGRADE, is
  expected to take a few seconds on a real card.

## Decisions (30 Sep 2026)

- **In the OS, not bare metal.** Doom runs inside the stock OS it boots
  with: RTOS, window system, input layers, card driver. Replacing those
  would mean writing a panel driver, and the switch only needs an image
  the bootstrap accepts. The DOOM image is still "an OS": it never loads a
  project, and QUIT leaves it.
- **A freestanding libc, not newlib.** The repo's only toolchain dependency
  stays `m68k-elf-gcc`, which it already needs.
- **WAD from the card, read whole.** The `.OBI` stage is 2.6 MB, so the
  4.2 MB WAD cannot be appended to the image. Reading it whole at boot
  keeps Doom's file layer to a memory `FILE`.
- **Singletics from a UI-task deferred call.** Key handlers and the tic run
  in the same task, so no locks are needed. A slow unit slows the game
  instead of dropping input.
- **Arena top, 528 pages spare.** A bottom reservation would sit under the
  platform runtime and move OS SWITCH's fixed mailbox. The top 528 are
  zero-filled at project load.
- **GPL-2.0 for `octa/`.** It links with doomgeneric. The upstream stays a
  submodule, credited to its authors (id Software, Chocolate Doom, ozkl).
