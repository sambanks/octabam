# The ColdFire emulators

There are two ways to run the Octatrack's OS without flashing it:

- **The port** (`tools/emu/ot_emu`, C++). Musashi runs the ColdFire, alongside both DSP56300
  cores, the card, the panel link, MIDI and USB. `make check`'s boot
  verifier and `verify_set` run on it, and so do `make panel` and `make
  emu-live`.
- **Tier-0** (`tools/emu/emu_bringup.py`, Unicorn). It boots to the RTOS
  handoff and calls the firmware's draw and formatter code directly. It is used by:
  - the label gates in `make check` (`verify_labels`, `verify_modenames`,
    `verify_hidden`) and CC MAP's `verify_ccmap`;
  - REPITCH's `verify_repitch_ui`;
  - `tools/build/stock_labels.py`;
  - the remixer's UNIT pane.

The records of how they were built:
- the port: `git show 3ceba41:docs/history/COLDFIRE_PORT.md` (O1–O14) and
  `git show 666b6154:docs/firmware/COLDFIRE_PORT.md` (O14i–O24, Tim
  Hastie's; what is still in the port is [Port features](#port-features));
- Tier-0: `git show 3ceba41:docs/history/EMU_BRINGUP.md` and `RTOS_FORK.md`.

Route A (`emu_rtos.py`) was retired on 26 Sep 2026 (60509404).

## Which one

| to | run | section |
|---|---|---|
| check a remix | `make check REMIX=<name>` (`OT_PROJECT=<dir>` adds a real project: `verify_set`) | [The port on a project](#the-port-on-a-project) |
| play a remix in a browser or a macOS app: screen, keys, knobs, sound | `make panel REMIX=<name>` / `make panel-app` | [`tools/panel/README.md`](../panel/README.md) |
| see the screen and press keys in a Tk window | `make emu-live REMIX=<name>` | [The panel from a FIFO](#the-panel-from-a-fifo) |
| a scripted run on a project: watches, dumps, MIDI in, audio out | `out/emu/ot_emu ...` | [The port on a project](#the-port-on-a-project) |
| USB: enumerate, MIDI, audio from a script | `ot_emu --usb-host SOCKET` + `tools/harness/usb_host.py` | [USB](#usb) |
| the firmware's own strings for a page, from Python | `emu_bringup` | [Tier-0](#tier-0-unicorn) |

`make panel` and `make emu-live` both take the project from `OT_PROJECT`
or from `~/.octabam_project`.
- `make panel` runs the port over `--interactive` with `--dsp-rt` (sound,
  paced to real time) and keeps its card in `out/cards/`.
- `make emu-live` runs it over `--live FIFO --lcd FILE` on a scratch card,
  with no sound.

## Build

Needs `make setup` and `make os && make recon` ([BUILDING.md sections 0–2](../../docs/guide/BUILDING.md)), plus `cmake`.

```sh
make emu-cf                          # cmake into out/emu, then boots stock 1.40C to the RTOS handoff
./out/emu/ot_emu --help              # every option, grouped
make emu-setup                       # .venv via uv: unicorn, textual, sounddevice (Tier-0, the panel's audio)
make emu-unicorn                     # the EMAC-fixed Unicorn for Tier-0
```

- In a worktree, run `make emu-cf` in that worktree. A symlinked `out/emu`
  builds the main checkout's sources (see `AGENTS.md`).
- After a change to `tools/patches/dsp56300.patch`, run `make dsp-repatch`,
  then `make emu-cf`.
- `make emu-cf` passes the host architecture to cmake. An Intel-Homebrew
  cmake configured x86_64 and ran the port under Rosetta.

## The port on a project

```sh
.venv/bin/python3 tools/emu/ot_emu/stage_card.py PROJECT_DIR OCTABAM RIG --out out/card.img \
    [--audio "SRC.wav:RIG/name.wav" --audio "SRC.ot:RIG/name.ot"]   # a sample the part plays
out/emu/ot_emu --image out/mainos_bus.bin --card out/card.img --set OCTABAM --project RIG \
    --sequencer --internal-clock --frames 600 --load-ms 90000 --dsp --main-level 64 \
    [--poke-trig 2] [--audio-in tone.wav] [--block-dump F] [--audio-out PREFIX] [--ata-latency SAMPLES]
```

- **Banks.** The project's `[STATES] BANK=` is the bank that plays.
  `--bank N` selects a bank live, but the transport start re-applies the
  saved bank's part over the live lane, so write a fixture into the saved
  bank.
- **Samples.** `stage_card.py` skips `.wav` and `.ot` files; `--audio`
  stages one at its card path. FLEX and STATIC both play.
  `--main-level` is required for any voice.
- **The load** runs until the engine is idle:
  - It ends when LOAD PROJECT's handler (`0x40085336`) has been entered and
    the engine sits at its queue receive (`0x4008484e`) with the queue
    count (`4(0x460d17ce)`) at zero.
  - The report prints `load run ended: LOAD PROJECT handled, N ms after
    the post`, or `STILL RUNNING at the budget (raise --load-ms)`.
  - `--load-ms` is a ceiling, 90 s in every harness.
  - Measured: 14.9 s on stock, 31.7 s under Octakit (bottleservice on
    OCTABAM89_setgate).
  - Under Octakit the post-load work queues a second engine command. A
    transport started inside it finds Octakit's page-1 wrapper busy for
    every CC.
- **ATA latency** defaults to 8 samples (~180 µs per data sector). At 1
  sample, `sys` consumed the engine's reset-time "select bank 0" after the
  `BANK=` parse. Under Octakit that ordering halted the load in
  `gk_lifecycle_activation_publication_report_fatal` (`0x45d173e4`).
  - Why the latency changes the order is inferred, not traced.
  - A module that adds interrupts or work during LOAD PROJECT under
    Octakit is exposed to this ordering: CC FEEDBACK's first build
    transmitted 272 CCs inside the load and tripped it.
- **Cost.** Wall time is about 2× the emulated time; about 15 frames/s with
  both cores live.
- **Panel actions and scripts:**
  - `--poke-early ADDR=BYTE` (before the call; `0x80000000` is the current
    track).
  - `--call ADDR,arg,...` runs a firmware routine as main, after the load.
  - `--call-at N` runs the same call N frames after the transport start.
  - `--poke` writes after the load, before the frames.
  - `--step FRAME:call|poke|dump:SPEC` is repeatable and runs in order:
    - `call`, a poke `addr=byte;...`, or a memory dump `addr,len=path;...`;
    - FRAME `-` means after the load and before the transport;
    - FRAME N means frame N after the transport start.
  - `--live-script FILE`: lines of `<emulated ms> key|enc|pot|midi|quit ...`,
    applied at those emulated times with the transport stopped.
  - `--scenario "LOG ARGS..."` (repeatable, with `--scenario-jobs N`) loads
    once and forks one child per scenario from the identical loaded
    machine. The DSP cores' shared memory is copied private in each child
    (`unshareRanges`, `main.cpp`).
- **Memory as a reset leaves it.** `--preload ADDR=FILE[;...]` puts a file's
  bytes in memory before the boot runs. The port boots zeroed RAM with NOR
  unmodelled: `0x3ffc` (NOR's bootstrap version) reads 0, so every boot takes
  the entry's bootstrap-upgrade branch where a flashed unit goes straight to
  `0x4000050c`; `--preload 0x3ffc=<04 08>` gives the hardware's path. A
  unit's power-on also finds battery SRAM from its last session: dump
  `0x10000000..0x100fffff` after a boot (`--mem-dump`) and preload it, or the
  port measures the first-ever power-on only (OS SWITCH's boot picker,
  `docs/contributing/FAILURE_MODES.md`).
- **A power-on's own load.** `--boot-load` writes the SET/PROJECT names
  before the mount, as a unit that has run a project has them, and posts
  nothing itself: the one LOAD PROJECT is the firmware's own (sys's media
  case, through `0x4002574c`). With a short `--load-ms` the run goes on to
  `--live-script` while the load is still held (`verify_osswitch`'s boot
  cases).
- **Three things the DSP emulator does that the chip does not** (found
  bringing up OS SWITCH's DSP park, 29 Sep 2026): `dsp peek <core> P <addr>`
  answers 0 for `0x30000..0x3ffff` (it reads the core's own array, not the
  shared window); `--dsp-pcwatch`'s a1/b1 print the accumulator shifted left
  by 8; and inside a long interrupt (a `jsr` vector) no peripheral runs until
  the handler's `rti`, so HI08 flags such as HTDE freeze.
- **MIDI IN.**
  - `--midi FILE` takes one event per line: `<frames after the transport
    start> <hex bytes>`, or `pre <hex bytes>` (before the transport start,
    with the transport stopped).
  - The bytes go onto UART0 (`0xfc060000`, INTC0 source 26) and through
    the firmware's own RX ISR, framer and MIDI thread.
  - A program change while playing waits for the pattern's end.
- **Dirty RAM.** `--dsp-dirty [SEED]` fills both cores' X/Y and the shared
  window with a xorshift stream before the boot, as on hardware.
  `dsp_host -dirty` covers Y only.
- **Watches and dumps:**
  - `--watch-mem ADDR,LEN[;...]` logs every write, with the PC. One range
    list per run; the last flag wins.
  - `--watch-read`, `--watch-pc`.
  - `--dsp-watch core:X|Y|P:addr`.
  - `--dsp-pcwatch core:pc` shows the last 24 arrivals with a, b, x, y, r0,
    r4, r6, n4, sp, r2, m2, r1, n1, r7, m7, m0 and n7 (n7 = the frame count
    of a call).
  - `--dsp-peek core:X|Y|P:addr,len` (upper-case space letter).
  - `--mem-dump addr,len=file`.
  - `--midi-out FILE` (UART0's transmit bytes).
- **Addresses.** A track's DSP instance record is `0x80000110 + 64·t` (32
  halfwords; see `docs/firmware/MIDI.md`). Its page-2 lane is
  `0x80000810 + 72·t`.
- **The card.**
  - `--card-out FILE` writes the card as the firmware left it.
  - `emu_card.extract_image(bytes[, out_dir])` reads a FAT16 image back as
    `{path: bytes}`.
  - The firmware writes `LOG 000000.txt` in the card root during a load,
    with one `ERROR` line per sample it could not open.
  - A wrong PART index byte shows there as `Couldn't read bank file ...
    ('PARSE ERROR')`, the unit's PARSE ERROR.
- **A detoured idle park.** `Rtos::install` reads `g_mainSpin-6`. A
  `jmp abs.l` there (CF METER IDLE's `m_idle`) makes `[target, target+0x80)`
  count as main's park.

`tools/verify/verify_set.py REMIX --project DIR [--bank N]` runs one part of
a real project. It is part of `make verify` when `OT_PROJECT` or
`~/.octabam_project` names a project, and takes ~80 s. It asserts:
- the load completed;
- the live FX1/FX2 id arrays equal the part's;
- every track's record halfwords 18–26 equal its page-2 lane;
- every track with record audio has a chain output;
- CC 40 over MIDI IN moves T2's SEND;
- (CC MAP) CC 68 reaches T1's FX1 page 2;
- on a bus remix, each engine's host carries T2's send on its chain
  output, and an engine on the wrong core is refused;
- the load rewrote no project file;
- the firmware's LOG has no error beyond the unstaged samples.

The tested bank is staged as bank A too, with `MASTER_TRACK=0`. The TX0
census of the main out is printed and not checked (below).

### Open: no track's dry audio reaches TX0 under the port

A card-sample voice plays, and its audio stops at core 0's summing mixdown
(`P:0x259..0x275`). The gain read from `Y:0x40` is 0 for every track
(`--dsp-pcwatch 0:0x25e`: x0 = the sample, y0 = 0), so the TX DMA ring at
`X:0x8000` stays zero. This was measured 28 Sep 2026 with `verify_repitch`'s
FLEX fixture on the repitch and bus images.

- **Upstream is fine.** The voice's position, fetch, format-3 copy, host
  port, core 1 render and post-FX read-back all carry the sample.
- **Where the zero comes from.** `Y:0x40` is written 0 each frame by the
  record unpack at `P:0x3c7`.
- **The only audible configuration** is `verify_set` on the stress project,
  and that audio is the engines' wet from the MIDI sends, not any track's
  dry.
- **Open question:** which record field the unpack (`P:0x3ac..0x3f7`) turns
  into that gain, and why it is 0. The candidates are the port's record
  delivery or the ColdFire level chain at `0x4000cc96`.
- **Poking the level bytes changes nothing.** Poking
  `0x8000005e/0x8000005f` (from `METRONOME_*_VOLUME`) or
  `0x80000035/0x80000036` (`MAIN_LEVEL` / `CUE_LEVEL`) after the load
  leaves the output the same.

## The screen

`ot_emu --lcd FILE` writes the firmware's 1-bpp plane (`0x46c7e0ea`, 1,024
bytes) to FILE:
- whenever it has changed, at most once per 2M ColdFire instructions;
- once more at exit (tmp + rename).

`tools/emu/lcd_view.py FILE` shows it in a Tk window. `--term` draws it
with half blocks, and `--png out.png` saves one frame.

The plane is 64 columns × 128 rows, 8 bytes per row, MSB left. Screen pixel
(x, y) is column 63−y of row x (see `docs/firmware/PANEL.md` section 1).

## The panel from a FIFO

`ot_emu --live FIFO` reads panel events while the RTOS runs:
- panel events go to the firmware over the panel link (UART1), in the
  controller's own framing (`docs/firmware/PANEL.md` section 4b);
- MIDI goes over UART0.

```
mkfifo out/panel.fifo
./out/emu/ot_emu --image out/raw/section_3_MAIN_OS.bin --card out/card.img --set OCTABAM --project RIG \
    --load-ms 90000 --dsp --lcd out/lcd.bin --live out/panel.fifo
.venv/bin/python3 tools/emu/lcd_view.py out/lcd.bin --panel out/panel.fifo     # other terminal
```

- **FIFO lines:** `key <code> down|up`, `enc <n> <delta>`, `pot <0..255>`,
  `midi <hex>...`, `quit`.
- **The transport.** Without `--sequencer` the transport is yours (PLAY is
  `0x28`).
- **The viewer's `--panel`** draws the keys, the seven encoders and the
  MAIN pot. Its keyboard shortcuts are the arrows, Return, Escape,
  space = PLAY, `1..8 q..i` = trigs and F1..F5 = pages.
- **Polling.** The FIFO is polled every 256 instructions and at most every
  10 ms of wall time.

## USB

`--usb-host SOCKET` gives the port the MCF5445x USB OTG module as the
firmware drives it (`tools/emu/ot_emu/usb.h`):
- the Chipidea device controller's registers at `0xfc0b0000`;
- the session and interrupt semantics;
- transfers through the firmware's queue heads and transfer descriptors;
- the completion interrupt on INTC1 source 47.

Without the option, the window reads all-ones and the firmware never brings
the controller up.

What the firmware does with it:
- **Bring-up** at `0x4001d630`: USBMODE 0x0e (device, big-endian), the
  endpoint list at `0x4ec94800`, and USBINTR 0x57 once OTGSC reports a
  session. The transceiver is ULPI.
- **The ISR** at `0x4001e594` answers GET_DESCRIPTOR from `0x400e2000`
  (Elektron 1935:0002: one MSC/SCSI/BOT interface on EP1). It answers "no
  medium" until USB DISK MODE unmounts the card.
- **Host mode.** Nothing in the image runs the controller as a host.

```sh
out/emu/ot_emu --image out/mainos_bus.bin --usb-host /tmp/ot-usb.sock &
tools/harness/usb_host.py /tmp/ot-usb.sock msc        # reset, enumerate, INQUIRY, TEST UNIT READY
tools/harness/usb_host.py /tmp/ot-usb.sock midi-send 903c64
tools/harness/usb_host.py /tmp/ot-usb.sock audio 3 2.0 capture.pcm 4
```

- **The socket protocol** is octemu's (`setup`/`in`/`out`/`reset`/`speed`;
  markandrus, MIT).
- **Holding for the client.** After every other phase, the port holds the
  machine until the client has connected and hung up (`--usb-hold-ms` caps
  it). A `reset` waits until the firmware has attached.
- **Other flags.**
  - `--usb-notify FILE` logs USB DISK MODE's attach/detach edges
    (`0x460e76a0`).
  - `--usb-fs` reports full speed.
- **Polling cadence.** The bench polls an isochronous endpoint on the
  endpoint's own schedule in device time: 250 µs at high speed for
  bInterval 2, 1 ms at full speed.
- **Gates.**
  - `verify_usb` enumerates the stock stack (INQUIRY `Elektron Octatrack
    DPS-1 0002`) and streams from the `usb-audio-*` modules.
  - `ot_periph_test` pins the register rules.
- **Limits.**
  - The port serialises the host's polls, the frame interrupt and the eDMA,
    so it cannot show timing races.
  - octemu's card-loaded payload does not install here. It hooks
    `fs_card_detect_poll` (`0x4003f174`), which the port's direct mount
    never runs. The `usb-*` modules carry that code on octabam's loader
    instead.

## Port features

Every option is in `./out/emu/ot_emu --help`. The `--interactive`
commands' reply formats are the header comment of `main.cpp`
(`serveInteractive`). All but `--mkii` came from Tim Hastie's fork
(O14i–O23, 11–13 Sep 2026; `THIRD_PARTY.md`).

- **`--interactive`** (what `make panel` runs). After the batch's boot and
  load the port prints `ready sample=<n> frames=<n>` and answers one line
  per command on stdin. Integers are decimal or `0x..` (a leading zero is
  not octal). Anything malformed answers `err <message>` and the loop
  continues; EOF exits 0. `--main-level` defaults to 64 here; the batch
  posts no level unless asked.
  - `run <ms> [wall <s>]` is the only command that advances emulated time;
    `stop=` in its reply is `time`, `gate`, `fault`, `illegal` or `wall`.
  - `key <row> <mask>`, `knob <row> <delta>` (two bytes into UART A's
    receive queue), `midi <hex>...` (UART0), `tx` (UART A's transmit bytes
    since the last `tx`), `peek`/`poke` (≤ 4096 bytes; unmapped answers
    `err`), `frame on|off`, `status`, `quit`.
  - `pace on [rate]` / `pace off` / `pacestatus`: while stdin is empty the
    port advances in 10 ms slices to track wall clock × rate, sleeping
    inside `poll()` on stdin when ahead and re-anchoring when more than
    250 ms behind.
  - `audio start [main|cue|all|tracks]`, `audio read [<maxframes>]`,
    `audio status`, `audio stop` (needs `--dsp`): core 0's ESAI TX0
    frames as little-endian 16-bit (the 24-bit word >> 8) in a 60 s ring
    (overwrites counted as `dropped`). `main` = ring words 2/3, `cue` =
    4/5, `all` = the eight words, `tracks` = the eight words then the
    sixteen per-track stems T1 L … T8 R, tapped at `P:0x2d5` (the buffers:
    `docs/firmware/DSP.md` "Core 0's frame").
  - `card status`, `card flush` (with a card).
  - Instruments: `watch <addr>[,…]` / `hits` (PC hits with registers and
    stack), `watchmem <addr> <len>` / `writes` (a watched SDRAM range is
    given as its cached alias `0x8xxxxxxx`), `dsp watch|pcwatch|peek`
    (lockstep only), `rtstatus` (`--dsp-rt`), `cfstatus`, `edmastatus`.
- **`--dsp-rt`** (needs `--interactive`): the two DSP cores run under the
  vendored JIT on worker threads, on the lockstep schedule (`dsp.cpp`,
  "THE REAL-TIME MODE"); the ColdFire stays the master of emulated time.
  On the clean OTLIVE fixture its capture was bit-identical to lockstep's
  (13 Sep 2026: 0 mismatches of 199,358 samples, three runs). The
  per-instruction DSP instruments do not observe it; every batch mode
  keeps the lockstep interpreter.
- **`--dsp-lazy N`**: the pair's ticks are booked and replayed in chunks
  of up to N DSP instructions at the ColdFire's touch points; the default
  in every mode, byte-identical to `0` (the per-tick path).
- **`--rtc host|off|EPOCH`**: DSPI chip-select 2 answers as a DS1390-style
  clock (BCD registers `0x01`–`0x07`, plus `0x00` and `0x0e`). `off`, the
  batch default, is the loopback (the dialog reads 2000-00-00); `host` is
  the `--interactive` default; an epoch is a frozen UTC instant. A
  written register is kept and stops advancing.
- **`--card-rw`** (needs `--card`): every committed sector is `pwrite()`n
  to the image file before its WRITE completes; `card flush`, `quit`, EOF
  and exit `fsync`. Without it the card lives in memory.
- **`--mkii`**: the GPIO loopback the boot probe tests and the MKII panel's
  replies (`docs/firmware/PANEL.md` section 4c).
- **DMA timers** DTIM0–3 (`0xfc070000 + 0x4000·n`, INTC0 sources 32–35);
  DTIM1 is the firmware's 8.333 ms UI/LED tick. The 2.8 s boot logo on
  DTIM3 is skipped unless `--boot-logo`.
- **The frame edge.** With `--dsp` the frame interrupt is the DSP's bank
  word (O9b), so a stalled core freezes the sequencer on trig 1;
  `--frame-timer` restores the 16-sample timer, and `--frame` uses the
  timer without the cores.
- **Memory-to-memory eDMA.** At the kick, a channel with neither end in the
  host-port window (`0x20000000–0x20000fff`) is copied per its TCD
  (`Rtos::copyMemToMem`: NBYTES per minor loop, SSIZE/DSIZE at
  SOFF/DOFF, SMOD/DMOD, CITER loops; TCD+4 is ATTR, +6 is SOFF). This
  carries the Echo Freeze Delay's tap fetches and ring writes
  (`docs/firmware/COLDFIRE_DELAY.md`), 32 blocks a frame. Counted under
  `--block-log` or `OT_M2M_REPORT=1`; `--edma-log FILE` logs every kick.
- **Build speed-ups**, all bit-exact under the oracle
  (`tools/emu/ot_emu/oracle/README.md`): event-horizon bursts, the
  page-table memory fast path, LTO, and opt-in profile-guided optimisation
  (`tools/emu/ot_emu/pgo.sh`).

## Speed

- The port runs in event-horizon bursts (bit-exact).
- `--dsp-rt` runs the DSP cores as JIT workers.
- The gates run in lockstep mode.
- Measured 25 Sep 2026 on a MacBook Air:
  - the panel, paced, with `--dsp-rt`: 1.000× real time;
  - unpaced on the OTLIVE fixture with both cores: 475–684 emulated ms per
    wall second.
- `--profile` prints the hottest PCs over the boot and over the frames.
- Where stock ColdFire time goes per frame: [`docs/firmware/ARCHITECTURE.md`
  section 6](../../docs/firmware/ARCHITECTURE.md).

## Emulator defects fixed (each has a test)

- **EMAC ACCext layouts.** The frame ISR saves and restores the accumulator
  extensions in integer mode (`0x4000ac96`, `0x4000d968`). The port's write
  knew only the fractional layout. Found by Jannik Aßfalg; `test_emac.cpp`
  holds both layouts.
- **MACSR S/U** is bit 6 and selects 16-bit rounding in fractional mode
  (see `AGENTS.md`); `test_emac.cpp`. The firmware sets `MACSR = 0x20`
  (fractional) at `0x4000cf60` and `0x4000d3ae`; the level chain at
  `0x4000ccae` runs at `0x60`.
- **The uncached aliases** `0x4F…` and `0x4E…` are folded onto the cached
  regions (`machine.h`).
- **EMAC −1.0 × −1.0** in fractional mode overflowed to −2³⁹; the product
  is `>> 23` in one shift now (`v4e.cpp`, Tim Hastie, 13 Sep 2026).
- **The eDMA TCD's ATTR and SOFF** were read swapped (ATTR is TCD+4, SOFF
  TCD+6), so every memory-to-memory copy moved single bytes (Tim Hastie,
  13 Sep 2026).

## Firmware behaviour an emulator has to reproduce

- The mount's INTRQ is not instantaneous and the firmware depends on it;
  a "stall" at 1,407 ATA commands was a line-A exception the UART hid
  (`git show 3ceba41:docs/history/COLDFIRE_PORT.md` O7).
- Route A did not fault on unmapped memory; the port's early "serial byte
  count" difference from it was memory the port had not mapped (O5 in the
  same record).

# Tier-0 (Unicorn)

`tools/emu/emu_bringup.py` boots a MAIN OS image to the RTOS multitasking
handoff (`trap #0`, ~7,000,000 instructions, ~4 s), then calls draw code
directly against the warm machine.

```sh
make emu-setup                       # .venv with unicorn + textual
make emu-unicorn                     # the EMAC-fixed Unicorn
.venv/bin/python3 tools/emu/emu_bringup.py [image]
```

- **CPU model.** `unicorn` must be given `UC_CPU_M68K_CFV4E`. The default
  68k core does not decode `mvz`/`mvs`/EMAC.
- **Architecture.** The `.venv` must be the host's native architecture: an
  x86_64 build under Rosetta crashed on its first `emu_start`.
- **The EMAC-fixed Unicorn.** `scripts/build_unicorn.sh` applies
  `tools/patches/unicorn_emac_fractional.patch` and builds the m68k-only
  library into `.venv/lib/unicorn-emac/`. `emu_bringup` loads it through
  `LIBUNICORN_PATH`. The patch fixes five defects of stock Unicorn 2.1.4;
  `AGENTS.md` has the detail:
  - the fractional-mode product is halved;
  - `msac` adds;
  - MAC-with-load reads Rx from the wrong word;
  - MAC-with-load decodes as a phantom dual-accumulate;
  - the MASK register resets to zero.
- **Self-test.** `emu_bringup.emac_selftest()` pins the semantics
  (`0xc00 × 0x200000` = 3, `−0xc00` = −3, `msacl` = −3).
- **The EMAC-with-load shim** (`_emac_load_shim`) keeps one trampoline slot
  per distinct instruction.

## What the boot needs

- **Reset state:** set `SR = 0x2700` before `A7 = 0x48000000`.
- **Peripheral MMIO** is modelled by callback. The default read is all-ones.
- **The PLL register** `0xfc0c4000` must return `0x16000000`. The firmware
  halts at `0x4000fa8c` unless `(reg>>24) × 12 MHz` equals 264 MHz.
- **Async completion flags** are poked after the write that starts each
  operation.

| region | what it is | notes |
|---|---|---|
| `0xfc0c4000` | clock/PLL config | load-bearing (above) |
| `0xfc0a4066/69` | serial/UART-ish | writes `0x43`, `0x33` |
| `0xfc064000..01c` | a serial/timer module | status polled at `+4` |
| `0xfc048018..05b` | another module | writes `0x1b`, `0x06` |
| `0xfc088000/02` | serial shift-out (shift-done in bit 2) | write datum, poll bit 2, 8× |

## Drawing the firmware's screens

The capture primitive is `FUN_40012bd8`: `(font, canvas, x, y, count, char
*str)`, cdecl, with 189 call sites. The recipe:

1. Boot to the handoff.
2. Install the string-capture hook and a map-on-fault hook.
3. Call `ctl_flush_tb()`.
4. Call the window open (`FUN_40064c18`).
5. Set `[0x400cbf40]=1` and `[0x400cbd9c]=6` (the visible-row clamp).
6. Poke `[0x400cbd98]` = the cursor row.
7. Call the draw (`FUN_40064d7c`).

The line pitch is 7 px, and a larger y is a higher row. The selection
highlight is an XOR rect (`FUN_40012254`) and is not captured.

The helpers:
- `render_menu(r, cursor)` returns the MAIN MENU as `(x, y, string)` tuples.
- `render_fx2(r, track, effect_id)` and `render_fx1(...)` render an FX
  parameter page with the effect assigned.
- `tools/build/stock_labels.py`, `verify_labels.py` and
  `verify_modenames.py` call the display formatters through the same
  machine.

Descending into a menu item needs the real key handler `FUN_40064e64`.

## The card (`emu_card`)

`tools/emu/emu_card.py` provides:
- `stage_project`: a project directory staged into a card tree;
- a FAT16 image builder (MBR + FAT16, VFAT long names);
- an ATA task-file model at `0x90000000`. IDENTIFY advertises PIO only.
  `attach()` hooks the queue primitive `0x40000818` and performs the data
  phase.

The set name needs a leading `/`. A WRITE's count byte is the remaining
count.

## Limits of Tier-0

- **No audio, no DSP and no keys.** It captures strings, not pixels.
- **Aliases.** The OS image's uncached alias at `0x48000000` is folded onto
  `0x40000000` (the DRAM loader depacks through it). The `0x46000000`
  region's alias at `0x4e000000` is separate here.
