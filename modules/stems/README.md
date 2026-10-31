# STEM REC

UP + REC opens STEMS and records to the card while the sequencer plays:
every track after its fader, the main mix (MAIN), the cue mix (CUE) and
the four inputs, 16 or 24 bits. It writes the take while it records, so a
take can run until you stop it, up to 60 minutes. Each take gets a
folder of its own in `<set>/AUDIO/!STEMS/`, named after the take
(`YYMMDD-HHMM`), and each source lands in it as its own file at 44,100
Hz. The `!` puts `!STEMS` first in the file browser, which sorts by
character code (`_` sorted after the letters on Yves's MKII, 27 Oct
2026). The take's name starts each file's name too, so a stem stays
identifiable outside its folder: `YYMMDD-HHMM-T1.wav` to `-T8.wav`,
`-MAIN.wav`, `-CUE.wav`, and the inputs as `-AB.wav` and `-CD.wav`
(stereo) or `-A.wav` to `-D.wav` (mono). A second take in the same minute
is named `YYMMDD-HHMM-2`, a third `YYMMDD-HHMM-3`, and so on up to 99, so
no take overwrites another. A name counts as taken when its log
(`/BRAIN/STEMS/<take>.TXT`, see STATS.TXT below) or its folder is on the
card. Every take that ends writes a log, so a second take with other
sources gets a number too. Takes already on a card in an older layout
(flat in `AUDIO/!STEMS/` from STEMS8 to STEMS10, `AUDIO/_STEMS/`,
`AUDIO/STEMS/<project>/YYMMDD-HHMM/`, or `AUDIO/YYMMDD-HHMM/`) stay
where they are.

**Why a folder for each take.** From STEMS8 to STEMS10 every take's files
sat in `!STEMS` itself. On Yves's MKII (27 Oct 2026, eleven files at 24
bits, on an emptied folder) each take's ring peaked higher as the folder
filled: 36%, 37%, 60%, 89%, and with 88 files in it the next take filled
the ring before its first card write, `RING FULL` after 2.9 s. A take
starts by creating its files, and that got slower with every file
already there (why each create slowed, a name alias searched among the
others, is inferred, not measured). In a folder of its own a take
creates its files among none. `verify_stems`' `crowded` run measures it
under the port.

Beside each WAV, STEM REC writes an attributes file with the same name
and the extension `.ot`, as the stock recorder does for its own
recordings. It holds the tempo when the take started (`0x8000181c`, the
word the stock recorder stores), so the unit timestretches the file at
that tempo instead of guessing one from the file's length. It also holds
the file's length in bars and a gain of +12 dB, the gain stock gives its
own recordings, on every file, MAIN and CUE too. A file with no samples
gets no `.ot`. The fields follow the firmware's writer
(`docs/firmware/SAMPLE_SAVE.md` section 8); a stock `.ot` from the unit
hasn't checked them yet. A track's file is
its share of MAIN: the track's audio times the gain the mix gives it, so
the level, MAIN LEVEL, the scenes and the crossfader are in it. At every
boot T1 alone is on, at 24 bits, both input pairs stereo (Yves, 27 Oct
2026; all eight tracks at 16 bits before); the menu changes each. STEMS opens
with UP + REC (no MAIN MENU row) so stock menus stay stock and BRAIN can
own the root's fifth slot. The port has run every source, both widths and
the menu key by key on the MKII and MKI panels (STEM_REC.md sections 15,
16 and 18).

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
- The menu's rows, read from memory during and after takes: STEM REC's
  time rising from `00:00` to `00:01`, `DONE`, also at the cap, `NO CARD`,
  `RING FULL` in place of `STEM REC`, and YES pressed while a take saves
  changing nothing. The time also rises while the card falls behind.
- A mono pair with an input left out: B and C out of their pairs, the take
  is `T1.wav`, `A.wav` and `D.wav`, each input every sample.
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
presses the keys under the port, once as an MKII and once as an MKI. It
checks that SYSTEM still reaches OS UPGRADE from the root (MAIN MENU is
also the recovery screen), opens STEMS with UP+REC, turns tracks off and
on, turns MAIN on and checks the last source stays on, flips 24 BIT,
splits AB and leaves B out, arms and cancels, records a take with T3 off
from PLAY to STOP, and checks the seven track files, `MAIN.wav` and
`A.wav` on the card. It checks that every text STEMS can show fits its
column, by the firmware font's own widths. A third boot compares STEMS
with what it must look like, pixel for pixel: stock PERSONALIZE drawn by
the firmware with STEMS's rows in place (`tools/verify/stems_reference.py`),
opened, scrolled, with a pair split and an input left out, and recording.
A picture of the screen at each step lands in `out/stems_runs/menu-*.png`
and `looks-*.png`.

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
| The frame hook, not recording (the gain mirror) | 394 instructions per frame | 1,001 | 20.1 |
| The frame hook, eight tracks at 16 bits | 3,401 instructions per frame | 5,579 | 20.7 |
| The frame hook, eight tracks at 24 bits | 3,969 instructions per frame | 6,219 | 20.7 |
| The frame hook, everything at 24 bits | 4,972 instructions per frame | 7,415 | 20.7 |
| The writer's copy | none: the card reads each file's ring (zero copy) | 737 a frame at eight tracks, 16 bits; 1,067 everything at 24 bits | 20.7 |
| The writer task's stack peak | 1,560 of 8,192 bytes (the most seen; `full`, 8 Oct 2026) | 1,244 | 20.3 |

The figures are zero copy's (STEM_REC.md 20.7; STEMS5 had 3,427, 3,995
and 5,012 for the hook and a copy of 206 and 284; STEMS4, flash D,
3,299, 4,059, 5,188, 502 and 807). The hook's figures are instruction
counts. On the unit, `STATS.TXT` measures its time in every take: flash
D measured 28 µs a frame on average (43 at most) at eight tracks, 24
bits, 4,059 instructions then, about 1.8 cycles an instruction on the
266 MHz core. Since zero copy the hook's stores go to uncached memory and
each waits for the RAM: 🟡 about 10 to 13 µs more a frame at eight tracks,
24 bits, estimated from flash E's copy, so about 37 µs, and about 45 µs
with everything at 24 bits.
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

Hold UP and press REC (UP first). The same chord again closes STEMS.
REC alone stays stock grid recording. MAIN MENU is unchanged.

STEMS looks like SYSTEM > PERSONAL SETTINGS: the set and project in the
band at the top, the STEMS title with its icon, and five rows at a time,
each a name and a value. UP and DOWN move between the rows, YES changes
the value under the cursor, and NO closes STEMS. Its fifteen rows, top
to bottom:

| Row | Shows | YES |
|---|---|---|
| 1 | `STEM REC` and its state: `READY`, `ARMED`, the take's time (`01:23`), `SAVING`, `DONE` or `NO CARD`. After a take that failed, the failure's name stands in for `STEM REC` | Arms a take, cancels an armed one, or stops a running one |
| 2 | `PEAK` and the take's highest ring fill (`12%`) | Nothing: the cursor skips this row |
| 3-10 | `T1` to `T8`, each with a checkbox. T8's reads `MASTER` while MASTER TRACK is on | Turns the track on or off. Nothing while T8 reads `MASTER` |
| 11-12 | `MAIN`, `CUE`, each with a checkbox | Turns the source on or off |
| 13-14 | The input pairs, AB and CD, each on one row (below) | Toggles the checkbox under the cursor |
| 15 | `24 BIT` with a checkbox | Switches between 16-bit and 24-bit files |

A pair row holds more than one checkbox, as stock MIDI SYNC does: LEFT
and RIGHT pick one, and its name is inverted.
- In stereo it reads `AB` and `STEREO`, each with a checkbox. AB on
  records the pair as one stereo file, `AB.wav`.
- With STEREO off it reads `A`, `B` and `STEREO`, each with a checkbox,
  and each input that's on records its own mono file, `A.wav` or
  `B.wav`. So A can record alone.
- Turning STEREO off starts A and B as AB was. Turning it on again
  turns AB on if A or B was on.
- The CD row works the same way, with C and D. The two rows' first
  checkboxes line up whatever each pair is set to, and STEREO's sits in
  the value column.

1. Choose the sources and the format. At boot T1 alone is on, at 24
   bits, and both pairs are stereo. The last
   source that's on stays on, and rows 3 to 15 are locked while a take
   records or saves.
   - With MASTER TRACK on, T8 is the master bus: MAIN is T8 alone, and
     `T8.wav` would equal `MAIN.wav` sample for sample. So T8's value
     reads `MASTER`, a take leaves T8 out, and a take with only T8 on
     records `MAIN.wav` instead. Turn MAIN on for the master bus. T8's own
     choice comes back when MASTER TRACK goes off.
2. Press **YES** on STEM REC.
   - If the sequencer is stopped, STEM REC arms. Recording starts on the
     first frame the sequencer plays. Press it again to cancel.
   - If the sequencer is running, recording starts at once.
   - **Or, without opening STEMS:** press **YES** twice within 0.5 s on
     the main page. It does the same as STEM REC's YES: it arms, or starts a take
     while the sequencer plays, and the message reads `STEMS ARMED`. YES
     still does its stock job on both presses (it arms every track for
     recording, `ARM ALL`). A double tap never stops or cancels a take:
     use STEMS or STOP for that. With a track key held, YES is stock's
     alone (`ARM TRK`). 0.4 s missed Yves's double taps on his MKII (27 Oct
     2026), so it is 0.5 s; the log's `yes gap` line shows what a tap measured.
3. The take stops when the sequencer stops, when you press **STOP**, after
   60 minutes, or when the ring fills. The menu can be closed while it
   records.
4. The writer finishes the files a moment after the stop: the last audio,
   then each file's real header and exact length. **Pull the card or power
   off only when the status reads `DONE`.** The folder isn't a signal: it
   appears when the take starts.

**The status updates by itself.** STEMS opens on what the take is doing,
and while it's open the window redraws whenever its labels change: the
time, `SAVING` to `DONE`, `RING FULL`. The redraw runs in the UI task, at
its next message after the change (the detour at `0x40056c7c`, after the
loop's head that TUNER and SCOPE claim). Until 27 Oct 2026 the status
changed only at a key (STEM_REC.md 16.1). How often the unit's UI task
gets a message isn't measured on the unit.

The error names: `RING FULL` (the card fell behind; the files still play),
`SAME MINUTE` (99 takes in this minute already), `WRITE FAILED`,
`OPEN FAILED`, `PATH FAILED` (no set mounted, or its path too long),
`SEEK FAILED`,
`CLOSE FAILED` and `TASK FAILED`.

### STATS.TXT, the take's log

Each take also gets a log, `/BRAIN/STEMS/<take>.TXT` at the card's root,
where BRAIN keeps its files. It's a few lines of text about the take,
written after its audio files are closed (not when a card write failed).
STEM REC makes `/BRAIN` and `/BRAIN/STEMS` when they're missing. If it
can't (a file in the way, or the card refuses), only the log is missing:
the take's status and files don't change. The log is still called
STATS.TXT in this document, its name before 27 Oct 2026, when it sat in
the take's folder. It's there to tell why a take fell behind, without an
emulator:

```
STEM REC STATS 261007-2015
status OK
165375 frames, 60 s, 11 files, 24 bits
ring peak 1234 of 7922 frames
card writes 2584, 41234 ms in all, longest 62300 us
card fastest write 21000 KB/s
card rec 36800 ms 81500 KB 451 us/KB
card save 4434 ms 9300 KB 476 us/KB
writer longest sleep 12000 us, asks 10000
hook mean 41 us, longest 88 us
hook and frame routine mean 290 us, longest 335 us, 165375 frames
card udma 4 mwdma 0, cluster 64 sectors
yes gap 312 ms, double taps 1
```

- **Yes gap** is the time between the last two presses of YES on the main
  page that the double tap saw, in ms, and **double taps** how many armed
  STEM REC since boot. A double tap counts when the gap is under 500 ms.
- **Card writes** fill most of the take's time, with long outliers: the
  card is the limit. The card takes one command a cluster (the file
  layer's), so a card formatted with larger clusters takes fewer, larger
  commands.
- **The writer's longest sleep** far above the 10 ms it asks for: it
  waited for the processor. It runs at priority 1, in turn with the engine,
  the UI and one more stock task, below three tasks that by their code most
  likely include the Static machines' card reader (STEM_REC.md 20.6).
- **Card rec and card save** split the card's writes into the take
  (recording) and the rest after STOP (saving), each in ms, KB and µs a
  KB. There is no copy to time: the card reads each file's ring where the
  hook wrote it (zero copy, STEM_REC.md 20.7). Each counts its bytes in
  32 bits, so its KB and µs a KB are wrong past 4 GiB: after about 22
  minutes with every source at 24 bits, or 34 with eight tracks at 24
  bits. The files aren't affected.
- **The fastest write** is a write that nothing interrupted: the card's
  own speed. A mean far below it (1,024 over the µs a KB, in KB/s) spent
  its time waiting for the processor, not for the card.
- **The hook and frame routine** near the frame's 362.8 µs: the audio
  interrupt left little for any task.
- **The card line** gives the DMA modes the card's driver chose (both 0
  is likely the PIO path) and the volume's sectors a cluster.

The times come from DMA timer 3, the counter the firmware itself
timestamps with (7.58 ns a count).

### The log against BRAIN's PERFORMANCE page

BRAIN's PERFORMANCE page shows the unit's load live, since it opened. The
log shows one take's figures, written after the take. Read from the code
on 27 Oct 2026 (`modules/brain/brain.c`: `build_load`, `build_card`,
`cpu_update`; `stems.s`: `stems_stats`), no figure in the log repeats one
on the page, so the log keeps every line (note 3 of 26 Oct 2026):

| In the log, for one take | On PERFORMANCE, live | Same figure? |
|---|---|---|
| The ring's peak, and the PEAK row | Nothing | No. BRAIN lacks it |
| Card writes: count, total ms, longest | CARD: WRITES (commands and KB) and SLOWEST (any command, in ms) | Close, but not the same. The log counts STEM REC's own writes in one take; CARD counts every command since the page opened |
| The card's fastest write, the rec and save rates | Nothing | No |
| The writer's longest sleep | Nothing | No |
| The hook's mean and longest | Nothing | No. The hook runs in the level-6 DMA chain (`0x40004840`, STEM_REC.md 2.5), so BRAIN's CPU tab charges it to the task it interrupts |
| The frame routine's mean and longest | LOAD: WORST FRAME, the level-5 frame interrupt (`0x4000aad0`) | No. A different routine. And LOAD's figures come from LOAD METER, which refuses STEM REC, so in a STEM REC image LOAD shows `-` |
| The card's DMA modes and its cluster size | Nothing | No |
| The writer task | CPU: not one of the eleven named tasks, so it counts in OTHER | No. BRAIN doesn't name it |

What BRAIN could add (a proposal for its author, not yet sent): a STEMS row on PERFORMANCE
with the ring's fill and the hook's longest frame (`stems_peak` against
`stems_rframes`, `stems_st_hmax`), when the image carries STEM REC,
and STEM REC's writer named on the CPU tab (its task control block is
`stems_tcb`).

## Limits

- The choices reset at every boot. Nothing is saved.
- **Set path length.** STEM REC's path buffers are `PATH_MAX` = 256 bytes.
  The set path may be up to 183 bytes (under `PATH_MAX` − 72). That leaves room
  for the longest take file,
  `/AUDIO/!STEMS/YYMMDD-HHMM-99/YYMMDD-HHMM-99-MAIN.wav` (52 characters
  and the NUL). A longer set path fails with `PATH FAILED`.
- **99 takes in one minute.** A hundredth take in the same minute is
  refused with `SAME MINUTE`, and nothing is written.
- At most 60 minutes.
- **T8's row shows the next take, not the one recording.** A take keeps
  the sources it started with. If MASTER TRACK changes while a take
  records, T8's row follows it at once (`MASTER`, or T8's own
  checkbox), but the take doesn't.
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
  hook runs 3,401 to 4,972 instructions per frame (eight tracks at 16
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
  RING FULL, cause open (STEM_REC.md 17.3). BuMa measured a MKI's card
  writes at 4.7–5.7 MB/s with the sequencer stopped and 1.4–2.1 MB/s with
  Static tracks streaming (STEM_REC.md 19.1).
- **On a busy project, eight tracks at 24 bits is the most that keeps
  up.** Zero copy on Yves's MKII, a project of eight Static tracks
  playing (STEM_REC.md 17.6): T1 to T8 at 24 bits ran a minute with the
  ring at most 21% full; twelve files at 24 bits (MAIN, CUE, AB and CD
  added, 3.17 MB/s) stopped with `RING FULL` after 4.3 s, the card taking
  2.1 MB/s while the writer, at priority 1, waited for the processor. A
  lighter project leaves the writer more of it (not measured with zero
  copy). The writer at priority 2 is built and kept as the next step
  (`stems-prio2`, STEM_REC.md 20.6).
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
    out each track's share one frame early, straight into the track
    file's ring: the samples times their gains on the EMAC unit, limited
    as MAIN is, the limit skipped for a track whose gains are all at or
    below a quarter (it can't act then). Then MAIN and CUE from the
    buffer the audio processor fills, and the inputs from the page of the
    input ring that frame filled, go into their files' rings, and the
    frame is published (18.5-18.7). At 16 bits it keeps each result's top
    16 bits; at 24 bits all of them. Each file has its own ring, holding
    the file's bytes in order from its header on, written through the
    uncached alias, so the card reads them where they are: zero copy
    (STEM_REC.md 20.7). A frame that crosses a ring's end has its tail
    moved to the ring's start before it's published. When a take starts
    it latches the file table (the sources, the format, each file's bytes
    per frame and routine), cuts the 8 MiB into the files' rings, and
    sets the capacity in frames.
- **The peak ring fill.** Each recorded frame the hook also keeps the
  take's largest ring fill in frames, `stems_peak`. Arming resets it to 0,
  and it keeps its value after the take ends. Its share of the ring is
  `stems_peak` over the ring's capacity at the take's sources and width. It's
  for the menu's PEAK row, and for measuring the card on the unit.
- **The writer task.** The module's own RTOS task at priority 1, created
  the first time REC is pressed. It wakes every 10 ms. At a take's
  start it names the take from the clock, creates the folder, refuses a
  folder that exists, writes each file's placeholder header into its
  ring, and opens one file per entry of the file table. While recording,
  it writes each file's whole published sectors straight from its ring,
  a 512-frame chunk's at most a pass, and refreshes the menu's labels
  between passes. It times its card writes and its sleeps for
  `STATS.TXT`. At the end it writes the rest, the last sector padded with
  zeros, rewrites each file's first sector with the real header, sets the
  exact length, and closes.
- **The raw file routines.** The writer calls the file layer's own
  sector-level routines, from the rings, and never the buffered API
  (STEM_REC.md 12.1). The processor reaches the rings only through the
  uncached address alias, so a card DMA reads what was written (11.8).
- **The first-sector fix.** A detour in the stock PIO write routine at
  `0x40014cfe`. It advances the card handler's data pointer and sector
  count before the first sector goes out, not after, so a card interrupt
  can never find them stale (STEM_REC.md 11.7).
- **The memory.** The rings, the task's 8 KB stack, and the sector-0
  copies (7 KB) are DRAM regions at the free top of the platform's arena
  reserve. So the module costs no sample memory beyond what any DRAM remix
  already gives up.
- **The menu.** STEMS is its own window, not a MAIN MENU page, drawn
  with the calls MAIN MENU and PERSONALIZE make: MAIN MENU's window (118
  by 64) and its title band, then PERSONALIZE's icon, title, rule, rows
  and scroll arrows (`0x40064d7c`, `0x40068e00`). Its fifteen rows are a
  label and a value each. Both are pointers: a press switches a value to
  another fixed string at once, and the writer task formats the numbers
  (the time, `PEAK`'s percentage) into a spare buffer before it switches
  the pointer, so a redraw never catches a half-written value. The pair
  rows draw their fields from the source and format bits. The frame hook
  points T8's value at `MASTER` when the MASTER TRACK byte (`0x80000034`)
  turns on, and back when it turns off.
- **The gain table.** Core 0's gain table is copied out of your own stock
  image at build time, because the OS reuses the memory it sits in after
  the audio processor's start-up (STEM_REC.md 18.4).

No module upstream hooks the frame site or grows MAIN MENU's root (29 Sep
2026). The ledger refuses one that does, by name.
