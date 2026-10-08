# STEM REC

MAIN MENU › STEMS records to the card while the sequencer plays: every
track after its fader, the main mix (MAIN), the cue mix (CUE) and the four
inputs, 16 or 24 bits. It writes the take while it records, so a take can
run until you stop it, up to 60 minutes. Each source lands as its own file
in `<set>/AUDIO/YYMMDD-HHMM/` at 44,100 Hz: `T1.wav` to `T8.wav`,
`MAIN.wav`, `CUE.wav`, and the inputs as `AB.wav` and `CD.wav` (stereo) or
`A.wav` to `D.wav` (mono). A track's file is its share of MAIN: the
track's audio times the gain the mix gives it, so the level, MAIN LEVEL,
the scenes and the crossfader are in it. At every boot the eight tracks
are on, MAIN, CUE and the inputs off, both input pairs stereo, and the
width 16 bits; the menu changes each. The port has run every source, both
widths and the menu key by key on the MKII and MKI panels
(STEM_REC.md sections 15, 16 and 18).

- The design: `git show 4d2d6456:docs/superpowers/specs/2026-09-22-stem-rec-streaming-design.md`,
  over the proof of concept's `git show 4d2d6456:docs/superpowers/specs/2026-09-10-stem-rec-poc-design.md`.
  The menu: `git show 4d2d6456:docs/superpowers/specs/2026-09-28-stem-rec-menu-design.md`.
  After the fader, the buses and 24 bits:
  `git show 4d2d6456:docs/superpowers/specs/2026-10-01-stem-rec-sources-design.md`.
  The perf round (less CPU, less card traffic, STATS.TXT, T8 MASTER):
  `git show 15703f7a:docs/superpowers/specs/2026-10-07-stem-rec-perf-design.md`.
- Every stock address the module uses, with its evidence:
  `docs/firmware/STEM_REC.md`. Section 12 covers streaming, section 18
  the level path, the inputs and MASTER TRACK.
- The remix: `stems`, STEM REC and the 14 stock effects. `make image
  REMIX=stems` builds it.

## Status

**Measured under the ColdFire port, and run on Yves's MKII** (STEMS1 to
STEMS3, `docs/firmware/STEM_REC.md` section 17). The port is the project's
emulator of the unit's main processor. `tools/verify/verify_stems.py`, part
of `make check REMIX=stems`, runs the module on fixture projects. It reads
each take back off the port's card and checks the header, the sizes, and
every sample. A track's file equals its read-back block, the track's
finished audio the unit's audio processor hands back to the main
processor, times the gain core 0's mix gives it, at a fixed lag. The
runs cover:

- A take stopped by STEM REC, by the sequencer, and by the 60-minute cap.
- A take long enough that the writer writes while it records.
- A take across the ring's wrap, with the take's sound on both sides.
- A ring that fills because the card falls behind.
- Eight tracks, eight files, each equal to its own track.
- One take per track mask on the THRU fixture: 1, 2, 4 and 8 tracks, and
  T1, T3, T6 and T8 together. Each file matches its own track, with sound
  in every frame, and the ring's peak fill matches the watch log.
- A card that refuses a write: the run records that the writer hangs.
- A take cut off mid-way: the run records that its file is empty.
- The menu's labels, read from memory during and after takes: `REC 00:00`
  rising to `REC 00:01`, `DONE mm:ss`, `DONE 60:00` at the cap, `NO CARD`,
  `SAME MINUTE`, `RING FULL`, and REC pressed while a take saves changing
  nothing. The time also rises while the card falls behind.
- After the fader: the hook's copy of core 0's gain arithmetic equals the
  DSP's own, through level moves, a MAIN level change and dirty DSP RAM;
  `T1.wav` equals `MAIN.wav`'s mix sample for sample when T1 alone
  plays, through level moves and a take started mid-move.
- The buses: `MAIN.wav` and `CUE.wav` equal the mixes, `AB.wav` and the
  mono `A.wav` and `B.wav` equal the input exactly, and with every source
  on the eight track files sum to `MAIN.wav` within the arithmetic's own
  rounding (0 to 7 steps), at 16 and 24 bits.
- 24 bits: `T1.wav` equals MAIN's 24 bits, and a 16-bit take of the same
  run is its top 16 bits.

`tools/verify/verify_stems_menu.py`, also part of `make check REMIX=stems`,
presses the menu's keys under the port, once as an MKII and once as an
MKI. It walks the five categories and checks that SYSTEM still reaches OS
UPGRADE, because MAIN MENU is also the recovery screen. In STEMS it turns
tracks off and on, turns MAIN on and checks the last source stays on,
flips the three switches, arms and cancels, records a take with T3 off
from PLAY to STOP, and checks the seven track files and `MAIN.wav` on
the card. It also draws every text STEMS can show and checks that each
fits. A picture of the screen at each step lands in
`out/stems_runs/menu-*.png`.

The fixture projects come from a local copy of EZBot's Ultimate FX 1.5.3
template, which never enters the repository. The verifier builds them at
the start of every run, from the folder `STEMS_TEMPLATE` names (default
`out/projects/Ultimate FX 1.5.3`). A fresh tree, such as a shard of
`make check-remix-gates`, needs the variable. Without a template the
verifier skips the port runs and says why.

Under the port the FLEX fixtures' sounds play only their first four
frames, so most of each FLEX take is silence. The THRU fixture feeds four
channels of noise into inputs A to D, and each track plays its own mix of
them, so the mask takes have sound in every frame: a lost or repeated
sector would show there.

`--long` adds a 20-second take whose file must equal the ring byte for
byte, the masks of 3, 5, 6 and 7 tracks and T8 alone, a mask changed
mid-take (the take keeps the one it started with), an eight-track take
past the ring's wrap, the overflow at eight tracks, eight tracks on a card
at half the speed they need, where the ring fills to 90% and the take
still completes, and everything at 24 bits, which outruns the port's card
by itself and stops with `RING FULL`, every file whole. It takes about an
hour and a half and stays outside `make check`. `tools/verify/stems_sweep.py`
measures the ring against the emulated card's speed (STEM_REC.md 15.4).

| Measured under the port | Since the perf round | Before it | STEM_REC.md |
|---|---|---|---|
| The frame hook, not recording (the gain mirror) | 394 instructions per frame | 1,001 | 19.1 |
| The frame hook, eight tracks at 16 bits | 3,299 instructions per frame | 5,579 | 19.1 |
| The frame hook, eight tracks at 24 bits | 4,059 instructions per frame | 6,219 | 19.1 |
| The frame hook, everything at 24 bits | 5,188 instructions per frame | 7,415 | 19.1 |
| The writer's copy, eight tracks at 16 bits | 502 per recorded frame | 737 | 19.1 |
| The writer's copy, everything at 24 bits | 807 per recorded frame | 1,067 | 19.1 |
| The writer task's stack peak | 1,560 of 8,192 bytes (the most seen; `full`, 8 Oct 2026) | 1,244 | 19.3 |

The hook's figures are instruction counts. On the unit, `STATS.TXT`
measures its time in every take. Bryan T's CF METER takes put
compute-bound interrupt code at about 1.1 cycles an instruction on the
264 MHz core (`docs/firmware/ARCHITECTURE.md`), so about 22 µs a frame
with everything at 24 bits and under 2 µs idle: estimated.
STEMS3 recorded eleven files at 24 bits on the unit; clicks and the
screen's response during a take aren't reported yet (STEM_REC.md 17.3).
Before piece 5 the hook copied the tracks as they were and cost 743
instructions per frame at eight tracks.

Known from the port, before any flash:

- **Every port take is named `000000-0000`**, because the port's clock
  reads 0. The name comes from the unit's own clock, and the order of its
  fields is first checked on the unit (STEM_REC.md 11.2).
- **T1 sits about 24 dB below its source sample** in the read-back block
  under the port, unexplained (STEM_REC.md section 9). A quiet take is a
  known possibility.
- **A stem is as loud as the track is in MAIN**, not as loud as its
  source: the level, MAIN LEVEL and AMP VOL all apply, as they do to what
  you hear. AMP VOL at its default, 64, gives about 12 dB less than at
  127 (STEM_REC.md 18.7).
- **A card that refuses a write command hangs the writer** inside the stock
  card driver, which has no timeout. Recovery is a power cycle. The stock
  sample save shares this (STEM_REC.md 11.4).
- **The stock PIO card write has a race, and the module fixes it.** PIO is
  the mode where the processor copies each sector to the card itself. An
  interrupt could land between the stock routine sending a write's first
  sector and updating the card handler's pointer and count. The handler
  then either waited forever with the frame interrupt blocked, or wrote a
  sector twice without an error. The module patches the stock routine to
  update both first (STEM_REC.md 11.7). The patch changes every PIO card
  write, not only STEM REC's. A card that reports DMA takes a different
  stock path, where the patch never runs.

## How to use it

Open MAIN MENU: the MAIN MENU key on the MKII, FUNC+MIXER on the MKI.
STEMS is the fifth category, under MIDI, with a record dot for its icon.
Its rows, top to bottom:

| Row | Shows | YES |
|---|---|---|
| 1 | `REC`; `CANCEL` while armed; `STOP` while recording; `SAVING` while the files are finished | Arms, cancels or stops the take |
| 2 | The status: `READY`, `ARMED`, `REC 01:23`, `SAVING`, `DONE 01:23`, `NO CARD`, or an error by name | The cursor skips this row |
| 3-10 | `T1 [X]` to `T8 [X]`, `[ ]` when a track is off; `T8 MASTER` while MASTER TRACK is on | Turns the track on or off; `T8 MASTER` does nothing |
| 11-14 | `MAIN [ ]`, `CUE [ ]`, `AB [ ]`, `CD [ ]` | Turns the source on or off |
| 15-16 | `AB STEREO [X]`, `CD STEREO [X]` | Records the pair as one stereo file, or as two mono files (`A.wav` and `B.wav`, `C.wav` and `D.wav`) |
| 17 | `24 BIT [ ]` | Switches between 16-bit and 24-bit files |
| 18 | `PEAK 12%`: the take's highest ring fill | The cursor never reaches this row |

1. Choose the sources and the format. At boot the eight tracks are on,
   MAIN, CUE and the inputs off, both pairs stereo, and 16 bits. The last
   source that's on stays on, and rows 3 to 17 are locked while a take
   records or saves.
   - With MASTER TRACK on, T8 is the master bus: MAIN is T8 alone, and
     `T8.wav` would equal `MAIN.wav` sample for sample. So T8's row reads
     `T8 MASTER`, a take leaves T8 out, and a take with only T8 on records
     `MAIN.wav` instead. Turn MAIN on for the master bus. T8's own choice
     comes back when MASTER TRACK goes off.
2. Press **REC**.
   - If the sequencer is stopped, STEM REC arms. Recording starts on the
     first frame the sequencer plays. Press it again to cancel.
   - If the sequencer is running, recording starts at once.
3. The take stops when the sequencer stops, when you press **STOP**, after
   60 minutes, or when the ring fills. The menu can be closed while it
   records.
4. The writer finishes the files a moment after the stop: the last audio,
   then each file's real header and exact length. **Pull the card or power
   off only when the status reads `DONE`.** The folder isn't a signal: it
   appears when the take starts.

**The status updates when you press a key.** The menu redraws on keys,
not on its own (STEM_REC.md 16.1), so the time and `DONE` show when you
open the menu or press any key in it, UP or DOWN for example.

The error names: `RING FULL` (the card fell behind; the files still play),
`SAME MINUTE` (a take already exists for this minute), `WRITE FAILED`,
`OPEN FAILED`, `PATH FAILED` (no set mounted, or its path too long),
`SEEK FAILED`,
`CLOSE FAILED` and `TASK FAILED`.

### STATS.TXT

Each take's folder also gets `STATS.TXT`, a few lines of text about the
take, written after its audio files are closed (not when a card write
failed). It's there to tell why a take fell behind, without an emulator:

```
STEM REC STATS 261007-2015
status OK
165375 frames, 60 s, 11 files, 24 bits
ring peak 1234 of 7943 frames
card writes 2584, 41234 ms in all, longest 62300 us
writer copy 1902 ms in all, longest batch 5100 us
writer longest sleep 12000 us, asks 10000
hook mean 41 us, longest 88 us
hook and frame routine mean 290 us, longest 335 us, 165375 frames
card udma 4 mwdma 0, cluster 64 sectors
```

- **Card writes** fill most of the take's time, with long outliers: the
  card is the limit. The card takes one command a cluster (the file
  layer's), so a card formatted with larger clusters takes fewer, larger
  commands.
- **The writer's longest sleep** far above the 10 ms it asks for: it
  waited for the processor. It runs at priority 1, beside the task that
  streams Static samples.
- **The hook and frame routine** near the frame's 362.8 µs: the audio
  interrupt left little for any task.
- **The card line** gives the DMA modes the card's driver chose (both 0
  is likely the PIO path) and the volume's sectors a cluster.

The times come from DMA timer 3, the counter the firmware itself
timestamps with (7.58 ns a count).

## Limits

- The choices reset at every boot. Nothing is saved.
- At most 60 minutes.
- **A track's file is after its fader.** With MASTER TRACK on, T1 to T7's
  files hold each track as it would sit in MAIN through a T8 that passed
  it unchanged, and T8 isn't recorded (MAIN is T8 then), so the files
  don't sum to MAIN in that mode (STEM_REC.md 18.8).
- **With MASTER TRACK on, T1 to T7 and CUE are 32 samples early.** The
  audio processor builds MAIN from T8's output of a mix it sent two
  frames before, and CUE from T1 to T7 of the current frame. So in a DAW,
  `T1.wav` to `T7.wav` and `CUE.wav` sit 32 samples (two frames, 0.73 ms)
  ahead of `MAIN.wav`; delay them by 32 samples to line them up. Measured
  under the port for T1 and CUE (STEM_REC.md 18.8); upstream's USB
  modules measured the same lead (CUE on Bryan T's MKII). The inputs
  aren't affected. With MASTER TRACK off, every file lines up.
- **The inputs are recorded raw**, as the stock recorder records INAB and
  INCD: before any track's level. An input that also plays through a THRU
  track is in that track's file too, after its fader, 80 samples later
  (the THRU track's own delay, STEM_REC.md 18.7).
- **More work in the audio interrupt.** While a take records, the frame
  hook runs 3,299 to 5,188 instructions per frame (eight tracks at 16
  bits to everything at 24 bits), and 394 while nothing records.
  `STATS.TXT` gives its time on the unit.
- The status doesn't tick on its own: it's current as of the last key.
- The name has no seconds. A second take in the same minute is refused, and
  the first stays intact.
- If the card falls behind and the 8 MiB ring fills, the take stops by
  itself at the last whole frame. Its files still play. A slow or nearly
  full card is the likely cause.
- The card must keep up with every file: 176,400 bytes a second for a
  stereo file at 16 bits, 264,600 at 24 bits, a mono file half that.
  Eight tracks at 16 bits need 1.41 MB/s, eight at 24 bits 2.12 MB/s, and
  everything at 24 bits 3.18 MB/s. The ring rides out a stall of 5.9 s,
  4.0 s and 2.6 s at those three. Under the port's card model, eight
  tracks at 16 bits already fall slightly behind: the frame interrupt,
  longer with this piece's hook, leaves the emulated card one sector a
  frame, and the ring would fill in about 160 s (STEM_REC.md 18.9). On
  the unit (STEMS3), eleven stereo files at 24 bits, 2.91 MB/s, peaked
  the ring at 13 to 16% on a light project and filled it on a busy one:
  RING FULL, cause open (STEM_REC.md 17.3).
- A power cut or a card pull before the end loses the take: each file is
  left at 0 bytes, because its length is set only at the end
  (STEM_REC.md 12.3).
- A nearly full card isn't analysed. Leave room: a stereo file needs
  about 10.6 MB a minute at 16 bits and 15.9 MB at 24, so eight tracks
  at 16 bits need about 85 MB a minute.
- Loading a project while recording isn't detected. Don't do it.
- One risk accepted for the proof of concept (Yves, 12 Sep 2026): the
  writer task sleeps on a shared timer that holds one waiter (STEM_REC.md
  4.7). Once REC has been pressed since power-on, don't run an OS upgrade
  until you've power cycled.
- The same timer: after pulling and reinserting the card, power cycle
  before the next take. A card probe can take the timer from the writer,
  and the next take then fills the ring and stays at `SAVING` (`stems.s`
  line 1367; traced in the source, not tested on a unit).

The proof of concept also warned against saving or loading while a take
was written, because it wrote through the file layer's shared staging
buffer (STEM_REC.md 7.5 and 7.5a). This build doesn't use that buffer, so
the warning no longer applies to STEM REC. Stock's own saves still share
it with each other, as in stock.

## Flashing it

The remix is `stems` (`remixes/test/stems/`): STEM REC and the 14 stock
effects. [BUILDING.md](../../docs/guide/BUILDING.md) has every step.

1. Build: `make image REMIX=stems BUILD=N` writes
   `out/OCTATRACK_OCTABAMN.bin`. N becomes the OS version the unit shows.
2. Flash from the card ([BUILDING.md section 5](../../docs/guide/BUILDING.md#5-flash-from-the-card)),
   then power cycle once more: STEMS1's first boot after the upgrade had
   no audio until a power cycle
   ([FAILURE_MODES.md](../../docs/contributing/FAILURE_MODES.md)).
3. Existing projects need nothing: the remix adds no effects and moves no
   knobs.
4. Back to stock: [BUILDING.md section 8](../../docs/guide/BUILDING.md#8-back-to-stock-or-another-remix).

## How it works

- **The frame hook.** A detour at the per-frame routine's only call site,
  `0x40004b12`, in the audio interrupt. It calls nothing and uses no RTOS
  service. Each frame:
  - **The gain mirror.** It reads the level page the main processor sends
    core 0 that frame and redoes core 0's gain arithmetic for the eight
    tracks, bit for bit, so it holds each track's ramp state (STEM_REC.md
    18.2-18.3). This runs whether or not a take records. It writes each
    track's 16 per-sample gains only while a take is armed, recording or
    saving, or the sequencer is stopped, and enters the EMAC unit only
    when a level changed.
  - **The copy.** Core 0 mixes MAIN for frame f from the track samples
    and gains that are already there at frame f−1, so the hook works
    out each track's share one frame early, straight into the next ring
    frame: the samples times their gains on the EMAC unit, limited as
    MAIN is, the limit skipped for a track whose gains are all at or
    below a quarter (it can't act then). Then MAIN and CUE from the
    buffer the audio processor fills, and the inputs from the page of the
    input ring that frame filled, go into the ring frame staged the frame
    before, which is then published (18.5-18.7). At 16 bits it keeps each
    result's top 16 bits; at 24 bits all of them. When a take starts it
    latches the file table: the sources, the format, each file's bytes
    per frame and routine, and the ring's capacity.
- **The peak ring fill.** Each recorded frame the hook also keeps the
  take's largest ring fill in frames, `stems_peak`. Arming resets it to 0,
  and it keeps its value after the take ends. Its share of the ring is
  `stems_peak` over the ring's capacity at the take's sources and width. It's
  for the menu's PEAK row, and for measuring the card on the unit.
- **The writer task.** The module's own RTOS task at priority 1, created
  the first time REC is pressed. It wakes every 10 ms. At a take's
  start it names the take from the clock, creates the folder, refuses a
  folder that exists, and opens one file per entry of the file table.
  While recording, it moves the ring into each file in 512-frame chunks,
  one file at a time over the chunk, and refreshes the menu's labels
  between chunks. It times its card writes, its copies and its sleeps
  for `STATS.TXT`. At the end it writes
  the rest, rewrites each file's first sector with the real header, sets
  the exact length, and closes.
- **The raw file routines.** The writer calls the file layer's own
  sector-level routines, from its own buffers, and never the buffered API
  (STEM_REC.md 12.1). The processor reaches those buffers only through the
  uncached address alias, so a card DMA reads what was written (11.8).
- **The first-sector fix.** A detour in the stock PIO write routine at
  `0x40014cfe`. It advances the card handler's data pointer and sector
  count before the first sector goes out, not after, so a card interrupt
  can never find them stale (STEM_REC.md 11.7).
- **The memory.** The ring, the task's 8 KB stack, and the writer's
  buffers are DRAM regions at the free top of the platform's arena
  reserve. So the module costs no sample memory beyond what any DRAM remix
  already gives up.
- **The menu.** The manifest copies MAIN MENU's four stock categories from
  your own image and adds STEMS, a row that points at the category's icon
  and its list of eighteen rows, both in the module's DRAM. Each row's label
  is a pointer: a press switches it to another fixed string at once, and
  the writer task formats the numbers (`REC 01:23`, `DONE`, `PEAK`) into a
  spare buffer before it switches the pointer, so a redraw never catches a
  half-written label. The frame hook points T8's row at `T8 MASTER` when
  the MASTER TRACK byte (`0x80000034`) turns on, and back when it turns
  off.
- **The gain table.** Core 0's gain table is copied out of your own stock
  image at build time, because the OS reuses the memory it sits in after
  the audio processor's start-up (STEM_REC.md 18.4).

No module upstream hooks the frame site or grows MAIN MENU's root (29 Sep
2026). The ledger refuses one that does, by name.
