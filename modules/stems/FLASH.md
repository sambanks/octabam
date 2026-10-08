# STEM REC: flashes A to G, and crosscheck's flash plan as a record

## Flash G — `stems`: zero copy, the writer at priority 1 (staged 8 Oct 2026)

Flash E's `STATS.TXT` (STEM_REC.md 17.5) showed the writer waiting for
the processor at priority 1, and about half its time was the copy. STEMS7
drops the copy: the frame hook writes each file's bytes into that file's
own ring, through the uncached alias, and the writer hands the card whole
sectors straight from the rings (STEM_REC.md 19.7). The writer stays at
priority 1. Flash F (STEMS6, the writer at priority 2, branch
`stems-prio2`) is built and kept as the fallback; it isn't flashed.

**The image.** IMAGE_G

**Before you flash.** As flash E: power cycle first if REC was pressed
since power-on, the stock `.syx` and a DIN MIDI interface at hand, the
card backed up; power cycle once after the upgrade.

**The tests, in order.**

1. Boot; MAIN MENU › SYSTEM › OS UPGRADE still opens.
2. Flash D's project (T1 to T8 Static, the bell), T1 to T8 at 24 bits,
   at least a minute: `DONE` or `RING FULL`, and its `STATS.TXT` either
   way, with the files. The hook line shows the cost of the uncached
   stores; `card rec` shows the card's speed during the take.
3. Seven tracks at 24 bits, then every source at 24 bits (MAIN, CUE and
   the inputs too), if 2 holds.
4. Listen to one take's files against the project: no clicks or gaps
   (the files are checked byte for byte under the port, but a unit can
   only be checked by ear and by `STATS.TXT`).

## Flash E — `stems`: the writer's copy in whole longs (staged 8 Oct 2026)

**Flashed** on Yves's MKII, reported 8 Oct 2026, six takes on flash D's
project: eight tracks at 24 bits ran 18 s before `RING FULL` (6.75 s in
flash D); seven at 24 bits filled slowly (47% after 70 s); six, four,
and eight at 16 bits held. `STATS.TXT` says why eight at 24 bits still
fills: the copy's own work is small (768 bytes in 12.6 µs), but its mean
is 15 to 18 times that, and the card's 5 to 7 times its fastest write.
The writer waits for the processor (STEM_REC.md 17.5).

Flash D's `STATS.TXT` (STEM_REC.md 17.4) put the limit in the writer's
copy into its uncached buffers: 8.5 s to copy 6.75 s of audio, one
stall a byte at 24 bits, plus time the writer wasn't running (how much
is not measured). STEMS5 writes every sample into the ring in its file's
byte order and copies whole longs: a quarter of the stores and about a
third of the instructions (STEM_REC.md 19.5). `STATS.TXT` splits the
copy into recording and saving and adds the copy's fastest frame and the
card's fastest write, which tell the work from the waiting.

**The image.** Built 8 Oct 2026 from branch `stems-perf` at `19a3a113` (a
clean tree; the commits after it change docs only), with the bare-metal
`m68k-elf` toolchain: `make image REMIX=stems BUILD=5 VERSION=STEMS5`.
The unit's OS version reads `STEMS5`.

| file | path | bytes | sha256 |
|---|---|---|---|
| card image | `out/OCTATRACK_STEMS5.bin` | 452,100 | `cd36f267825dd1b1b907ed0ab5dd5e41927acd876ba93765b5f22a9e9028e2be` |
| MIDI image | `out/OCTATRACK_OS1.40C_STEMS5.syx` | 631,504 | `50c648ee2bd3b01ae1bfaa5c332a22e067347788f2a58560664f6a98db0a876f` |

Both are built from your own 1.40C and never enter the repository. Copies
are in `/home/yvez/xcheck/stems5`. The checks on that code: the unit
tests, 71 PASS, 0 FAIL; under the port, first the checks the copy and
the byte order reach on the draft (170 PASS; its one FAIL, `cost` at
5,764, is what `PACK12A`/`PACK12B` fixed), then the 24-bit takes byte for
byte, all fourteen files, `STATS.TXT` and `cost` again on the final code
(77 PASS, 0 FAIL, `cost` 5,012); `verify_stems --long --fat32` on
`19a3a113`: 453 PASS, 0 FAIL, 0 SKIP.

**Before you flash.** As flash D: power cycle first if REC was pressed
since power-on (STEMS4 included), the stock `.syx` and a DIN MIDI
interface at hand, the card backed up; power cycle once after the
upgrade.

**The tests, in order.**

1. Boot; MAIN MENU › SYSTEM › OS UPGRADE still opens.
2. Flash D's project (T1 to T8 Static, the bell), T1 to T8 at 24 bits,
   a minute: `DONE` or `RING FULL`, and its `STATS.TXT` either way, with
   the files.
3. The same at 16 bits.
4. Flash D's tests 3 and 5 (T8 MASTER; the cluster line), if not done.


## Flash D — `stems`: the perf round, STATS.TXT, T8 MASTER (staged 8 Oct 2026)

**Flashed** on Yves's MKII, reported 8 Oct 2026: it boots and records;
on a new project of eight Static tracks (one bell sample each) T1 to T8
at 24 bits stopped with `RING FULL` after 6.75 s, every file whole and
intact. `STATS.TXT` put the limit in the writer's copy, not the card or
the audio interrupt (STEM_REC.md 17.4). Flash E is the fix.


The perf round (PR #644; the design:
`git show 15703f7a:docs/superpowers/specs/2026-10-07-stem-rec-perf-design.md`;
`docs/firmware/STEM_REC.md` section 19). A take's files are what the code
before the round wrote, sample for sample, with two exceptions by design:
REC pressed while the sequencer plays starts one frame (0.36 ms) later,
and T8 isn't recorded while MASTER TRACK is on. New for the unit: less work in the audio
interrupt, `STATS.TXT` in each take's folder, and T8's row reading
`T8 MASTER` while MASTER TRACK is on.

**The image.** Built 8 Oct 2026 from branch `stems-perf` at `ad73ee89` (a
clean tree, the PR's head), with the bare-metal `m68k-elf` toolchain:
`make image REMIX=stems BUILD=4 VERSION=STEMS4`. The unit's OS version
reads `STEMS4`.

| file | path | bytes | sha256 |
|---|---|---|---|
| card image | `out/OCTATRACK_STEMS4.bin` | 451,852 | `c7a8cb78e3a03728a631dd6ab1bf8f3f1f3f2ace0a0da24f78cc8b0395101795` |
| MIDI image | `out/OCTATRACK_OS1.40C_STEMS4.syx` | 631,155 | `4ad3812f89643a366f606c008eb7cc971b2fd3eb632360f0dfbc69eeb983cd5d` |

Both are built from your own 1.40C and never enter the repository. Copies
are in `/home/yvez/xcheck/stems4`. The gates on that code: `make reach
RUN=1 KEEP=1 TESTS=1` every gate ok, `verify_stems --long --fat32` 449
PASS, 0 FAIL, 0 SKIP (the PR). The wrapped OS itself (`out/mainos_bus.bin`,
`dcefe88f…6d420f9f`) booted under the port and recorded an eight-track
take and a MASTER TRACK take (IDLE, `T1.wav`, `MAIN.wav` and `CUE.wav`, no
`T8.wav`).

**Before you flash.**

- **If REC was pressed since power-on (STEMS3 included), power cycle
  first, then OS UPGRADE.** The writer task sleeps on the timer the
  upgrade uses, which holds one sleeper (STEM_REC.md 4.7).
- As flash A: the stock `.syx` and a DIN MIDI interface at hand for the
  Startup Menu (`docs/guide/BUILDING.md` section 7), the card backed up.
- After the upgrade, power cycle once more (flash A's silent first boot).

**The tests, in order.** Stop at the first that fails.

1. Boot; MAIN MENU › SYSTEM › OS UPGRADE still opens (the recovery path);
   MAIN MENU › STEMS shows its eighteen rows.
2. A light project, T1 to T8 at 16 bits, 30 s: the take saves (`DONE`),
   the files play, and the folder holds `STATS.TXT`. Send it.
3. MASTER TRACK on: T8's row reads `T8 MASTER` and YES does nothing; a
   take with T1, T8 and MAIN on holds `T1.wav` and `MAIN.wav`, no
   `T8.wav`. MASTER TRACK off again: T8's row reads as before.
4. Flash C's busy project (T2 to T8 Static, all trigs; eleven stereo
   files at 24 bits) for a minute: `DONE` or `RING FULL`, and the take's
   `STATS.TXT` either way. It tells the card from the processor: card
   writes filling most of the take's time point at the card; a writer
   sleep far above 10,000 µs, or a hook and frame routine near 362 µs,
   point at the processor.
5. The card's cluster: the `card ... cluster N sectors` line, or `chkdsk`
   on a computer (bytes in each allocation unit).
6. Flash C's tests not reported yet still stand: the null tests, the
   inputs mono and CD, and a 5-minute take at eight tracks and 16 bits.

**After the flash.** Every result goes into `docs/firmware/STEM_REC.md`
section 17, as flash D.

## Flash C — `stems`: stems after the fader, the buses and 24 bits (staged 5 Oct 2026)

**Flashed** on Yves's MKII, reported 6 Oct 2026: it records T1 to T8,
MAIN, and AB, and a stem follows its track's LEVEL, AMP VOL, and BAL. On a
busy project, eleven files at 24 bits filled the ring (RING FULL). Results
in `docs/firmware/STEM_REC.md` section 17.3, with the tests not reported
yet.

Piece 5 (`git show 4d2d6456:docs/superpowers/specs/2026-10-01-stem-rec-sources-design.md`),
on Yves's MKII. A track's file is now its share of MAIN, after its fader.
MAIN, CUE and the inputs are sources of their own, the input pairs can be
stereo or mono, and 24 BIT switches the files to 24 bits. The ring is
8 MiB. Flash C checks all of that on the unit, and how the unit copes with
the extra work in its audio interrupt.

**The image.** Built 5 Oct 2026 from branch `stem-rec-p5` at `fc7baad`
(a clean tree; it differs from the gated `3780665` in docs only), with the
bare-metal `m68k-elf` toolchain: `make image REMIX=stems BUILD=3
VERSION=STEMS3`. The unit's OS version reads `STEMS3`.

| file | path | bytes | sha256 |
|---|---|---|---|
| card image | `out/OCTATRACK_STEMS3.bin` | 450,676 | `96b3e5d1348508a04af9f67e64d0758348ca272929a445e1b20601e7a5a0236a` |
| MIDI image | `out/OCTATRACK_OS1.40C_STEMS3.syx` | 629,523 | `13cb5a6438eba058a14013767b88eecd536a55cb18857190a728d4fe3c0b4a9f` |

Both are built from your own 1.40C and never enter the repository. Copies
are in `/home/yvez/xcheck/stems3`. Every gate passed on that code:
`make check-remix REMIX=stems` 317 PASS, 0 FAIL, the only SKIP
`verify_set`'s, which needs a project; the menu gate's walks on the MKII
and the MKI are in it. `verify_stems --long` 363 PASS, `--fat32` 95,
the unit tests 54 and 12, all 0 FAIL (`docs/firmware/STEM_REC.md` 18.9;
`/home/yvez/xcheck/v5-p5-big2.log`, `v5-p5-big2-long.log`). Never
flashed. The card path is flash A's.

**What's new for the unit: more work every frame.** The frame hook runs
inside the audio interrupt. It now redoes core 0's gain arithmetic every
frame (1,001 instructions per frame while nothing records, against 2
before) and multiplies every sample it records by its gain (5,579
instructions per frame at eight tracks and 16 bits, 7,415 with everything
on at 24 bits, against 743 for STEMS2's eight tracks). Its time on the unit
isn't measured. Sam Banks's CF METER takes on Bryan T's MKII (4 Oct 2026)
give the room it has: the frame interrupt takes 244 to 285 µs of the
362.8 µs frame with seven voices playing, 291 to 335 µs in its worst
frames, and about 17 µs more for each voice that plays. At one to three
cycles an instruction, the hook adds roughly 6 to 11 µs always, 31 to
63 µs recording eight tracks at 16 bits, and 42 to 84 µs with everything at
24 bits. That's an estimate, not a measurement, but it's the size of the
worst frames' slack on a busy project. So tests 8 and 9 load the unit on
purpose. What running out of time would look like: clicks in what you
hear or in the files, a slow screen, the sequencer or MIDI drifting, at
worst a hang. None of it touches the Startup Menu, so recovery is always
flash A's step 1.

**Before you flash.** As flash A: the stock `.syx` and a MIDI interface at
hand, the card backed up. Once REC has been pressed since power-on, don't
run an OS upgrade without a power cycle first (STEM_REC.md 4.7). For the
null tests, a DAW that can invert a file's polarity and sum files.

**The tests, in order.** Photograph the screen where a test says so.

1. **The first boot.** Before you power-cycle: does the unit play audio?
   **Report** yes or no, and whether you loaded a saved project or made a
   new one first. Then power-cycle anyway. STEMS1's first boot was silent;
   STEMS2's played (STEM_REC.md 17.1, 17.2).
2. **The menu.** Open STEMS. **Report, with a photo:** REC, READY,
   `T1 [X]` to `T8 [X]`, `MAIN [ ]`, `CUE [ ]`, `AB [ ]`, `CD [ ]`,
   `AB STEREO [X]`, `CD STEREO [X]`, `24 BIT [ ]`, and PEAK at the bottom
   (scroll down). Turn every source off: the last one stays on. Turn the
   eight tracks back on.
3. **After the fader, one track.** T1 alone playing a steady sample, every
   other track muted, the mixer's DIR AB and DIR CD at 0, MAIN on. Record
   30 s and move T1's LEVEL during it. **Report:** `T1.wav` follows the
   fader. In the DAW, `T1.wav` with its polarity inverted, summed with
   `MAIN.wav`: silence, or how loud the rest is. Under the port the two
   are equal sample for sample.
4. **After the fader, every track.** All eight tracks playing, MAIN on,
   DIR AB and DIR CD at 0, MASTER TRACK off, 60 s. **Report:** the eight
   track files summed, inverted, against `MAIN.wav`: how loud the rest is.
   Under the port it's 0 to 7 steps of 16 bits, except where MAIN itself
   clips. Then the level by ear: does each stem sound as loud as its track
   does in the mix?
5. **The inputs.** A stereo source into A and B (a synth, say). AB on, the
   tracks off except T1: a take with AB STEREO on, then one with it off.
   **Report:** `AB.wav` is stereo and `A.wav` and `B.wav` are mono, each
   the input as it went in, and their level against the stock recorder's
   INAB of the same input. Then the same for C and D, if you have a
   source for them.
6. **24 bits.** 24 BIT on, T1 and MAIN, 30 s. **Report:** the DAW reads
   both files as 24-bit, they play, and their level matches a 16-bit take
   of the same pattern.
7. **The card's speed.** First one take of 5 minutes, eight tracks at
   16 bits, the sequencer playing. Under the port the writer falls a
   little behind at this rate: the ring fills by about 1% every 2 s and
   `RING FULL` ends the take near 2:40 (STEM_REC.md 18.9). Your card
   takes a path the port doesn't run, so it may keep up. **Report:** how
   long the take ran, PEAK after it, and any `RING FULL`. Then takes of
   60 s: eight tracks at 24 bits (2.12 MB/s), everything at 16 bits
   (2.12 MB/s), and everything at 24 bits (3.18 MB/s). Everything means
   the eight tracks, MAIN, CUE, AB and CD. **Report:** PEAK after each,
   and any `RING FULL`. The ring rides out a stall of 4.0 s, 4.0 s and
   2.6 s at those rates.
8. **The load, while recording.** A busy project: seven or more tracks
   playing samples at once, the sequencer running. First without a take,
   to know how it sounds and feels. Then the same with a take of eight
   tracks at 16 bits, then everything at 24 bits, 2 minutes each. During
   each take, listen and touch:
   - clicks or dropouts in what you hear;
   - the screen: turn knobs, change pages, open and close menus. Is it
     slower than without the take?
   - timing: a MIDI device clocked from the unit, or the metronome. Does
     it drift or stutter?

   **Report** each, per take, and then clicks in the files themselves. If
   static machines are at hand, run one take with seven static tracks too:
   the CF METER takes saw static machines add the largest worst-frame
   spikes.
9. **The load, not recording.** The gain mirror runs every frame, even
   without a take. On the busy project of test 8 with no take: anything
   different from STEMS2 on the same project? Only if you notice
   something in test 8 that you didn't on STEMS2.
10. **Stock saves.** After the takes: save the project, save a sample,
    power cycle, and load both. **Report:** both save and both load.
    Flash A's test 7, not reported yet.

**Stop conditions.** Flash A's, and:

- **Clicks or a slow screen in test 8** aren't a reason to stop the
  session. Stop the take, note how many tracks were playing and which
  sources and width were on, and go on with fewer.
- **A hang during a take:** power cycle, stop the session, and report the
  project's voice count and the sources and width.

**After the flash.** Every result goes into `docs/firmware/STEM_REC.md`
(section 17.3), any new failure into
`docs/contributing/FAILURE_MODES.md`, and the image into `CHANGELOG.md`.
If test 8 shows strain, the next steps are a timer probe that reports the
hook's time on the unit, and a cheaper hook (spec section 4.6).

## Flash B — `stems`: the stock effects back (staged 1 Oct 2026)

**Flashed 1 Oct 2026** on Yves's MKII: no error, and FX2's page shows the
stock effects. Results in `docs/firmware/STEM_REC.md` section 17.2.

STEMS1 ran on Yves's MKII on 30 Sep 2026 (`docs/firmware/STEM_REC.md`
section 17.1). STEMS2 is the same STEM REC code on the stock effects: the
remix now lists the 14 stock effects, so FX2's chooser is stock's and PLATE,
SPRING and DARK REV are back. It also carries upstream `363861e` (the build's
pre-boot regions and placement). `modules/stems/stems.s` is unchanged.

**The image.** Built 1 Oct 2026 from branch `stem-rec-p3` at `d646e83`
(a clean tree), with the bare-metal `m68k-elf` toolchain: `make image
REMIX=stems BUILD=2 VERSION=STEMS2`. The unit's OS version reads `STEMS2`.
The build at `18a46fd` (the remix change alone) gave the same bytes.

| file | path | bytes | sha256 |
|---|---|---|---|
| card image | `out/OCTATRACK_STEMS2.bin` | 448,576 | `6a02db5e2a6afbe4dc1a98dd075b5e89c65f8dd99b31ecbef6d6da61e8fc8519` |
| MIDI image | `out/OCTATRACK_OS1.40C_STEMS2.syx` | 626,582 | `204105583d99fc34030066d184ddfb2b05466d0ed1dd75c0e4eb57517fa399b5` |

Both are built from your own 1.40C and never enter the repository. Every
gate passed on that commit: `make check-remix REMIX=stems` 209 PASS, 0
FAIL, with the menu gate's 28 panel checks (MKII and MKI) and
`verify_stems` in it; the only SKIP is `verify_set`'s, which needs a
project (`/home/yvez/xcheck/v3-stems2-gates.log`, 1 Oct 2026). Never
flashed. The card path is flash A's.

**Before you flash.** As flash A: the stock `.syx` and a MIDI interface at
hand, the card backed up.

**The tests, in order.**

1. **The first boot.** Before you power-cycle: does the unit play audio?
   **Report** yes or no. Then power-cycle anyway (`docs/guide/BUILDING.md`
   section 5 step 5). STEMS1's first boot was silent
   (`docs/contributing/FAILURE_MODES.md`).
2. **The FX2 chooser.** Open FX2 on any track. **Report:** NONE and the 14
   stock effects, FILTER to DARK REV.
3. **The level.** One track alone, a steady sample, LEVEL and pan as they
   are, the same pattern three times: with the stock recorder on T1 as
   its source, with the stock recorder on MAIN, and with STEMS. **Report:**
   each file's peak in a DAW, and T1's LEVEL. Section 17.1 has why.
4. **Flash A's tests not yet reported:** the card's speed (60 s takes at
   1, 2, 4 and 8 tracks: PEAK after each, any `RING FULL`), a take while a
   static machine streams from the card, and stock saves (save the project
   and a sample, power-cycle, load both).

The stop conditions are flash A's.

## Flash A — `stems`: STEMS in MAIN MENU (staged 30 Sep 2026)

Piece 4 of the roadmap (`git show 4d2d6456:docs/superpowers/specs/2026-09-26-stem-rec-upstream-port-design.md`,
section 0), on Yves's MKII. It proves the menu, measures the card at 1, 2, 4
and 8 tracks from the peak fill, records with a static machine playing, and
compares a take's level with the stock recorder's.

**The image.** Built 30 Sep 2026 from branch `stem-rec-p3` at `4ec1276`
(a clean tree), with the bare-metal `m68k-elf` toolchain (binutils 2.47,
GCC 16.1.0; `docs/guide/BUILDING.md` 1a): `make image REMIX=stems
BUILD=1 VERSION=STEMS1`. The unit's OS version reads `STEMS1`.

| file | path | bytes | sha256 |
|---|---|---|---|
| card image | `out/OCTATRACK_STEMS1.bin` | 448,580 | `da54aad5cc29778972c1ba87ee0dcef2caa5998c67993409fb2efbcae55a5654` |
| MIDI image | `out/OCTATRACK_OS1.40C_STEMS1.syx` | 626,601 | `36b145b88ca1ca5d8455f62dd934c7b21208c7a0035623b5bed1fa7ce4a78517` |

Both are built from your own 1.40C and never enter the repository. Under
the port on that code: `verify_stems` 168 checks and the menu gate 28 on
the MKII and MKI, 0 failures; `make check-remix REMIX=stems` 208
(`docs/firmware/STEM_REC.md` 16.2). Never flashed. The card path
(`docs/guide/BUILDING.md` section 5): copy the `.bin` to the root of the card, then
PROJECT → OS UPGRADE → [YES].

**Before you flash.**

1. **Know the way back** (`docs/guide/BUILDING.md` section 7). Hold [FUNC] and
   power on for the STARTUP MENU; [TRIG 3] is MIDI UPGRADE; send
   `downloads/extracted/OCTATRACK_OS1.40C.syx` over a 5-pin MIDI interface.
   The Startup Menu doesn't need MAIN MENU, so an image whose MAIN MENU
   won't draw is still recoverable this way. Have the interface, the app
   and the `.syx` ready before you start.
2. **A spare card, with its contents backed up.** Your SanDisk Extreme
   64 GB reports DMA, so every take goes through the stock WRITE DMA path,
   which no emulator has run (crosscheck's notes below).
3. **A `BUILD` number you haven't flashed**, so the unit's version maps to
   one commit.
4. **Once REC has been pressed since power-on, don't run an OS upgrade
   without a power cycle first** (STEM_REC.md 4.7).

**The tests, in order.** Photograph the screen where a test says so.

1. **The menu.** Open MAIN MENU (the MAIN MENU key). **Report, with a
   photo:** five categories, STEMS fifth under MIDI with a round dot for
   its icon; SYSTEM still lists OS UPGRADE (don't press it); CONTROL shows
   its six stock rows (AUDIO to METRONOME) and no STEM REC row. In STEMS:
   REC, READY, T1 [X] to T8 [X], and PEAK 0% at the bottom. DOWN from REC
   lands on T1, UP from T1 on REC, and DOWN from T8 stays on T8.
2. **The track rows.** Turn T3 off and on: `T3 [ ]`, then `T3 [X]`. Turn
   every track off: T8 stays on. Turn them back on.
3. **A take from the menu.** REC (the status reads ARMED, the row CANCEL),
   close the menu, PLAY, and let it record 60 s. Reopen STEMS: STOP and
   `REC 01:0x`; press UP or DOWN and the time moves on. Press STOP (row 1):
   SAVING, then, after a key, `DONE 01:0x`. **Report:** the folder name
   against the unit's clock (the field order is checked for the first
   time here, STEM_REC.md 11.2), one file per track, each file's length,
   and whether each plays whole in a DAW.
4. **The card's speed.** Takes of 60 s at 1, 2, 4 and 8 tracks (turn the
   others off). **Report:** PEAK after each take, and any `RING FULL`. At
   eight tracks the card must keep 1.41 MB/s; the ring holds about 3 s
   (STEM_REC.md 15.4).
5. **A static machine playing.** A take while a static machine streams
   from the card. **Report:** whether its playback glitched, and whether
   the take is whole.
6. **The level.** Record the same pattern with the stock recorder
   (resampling T1) and with STEMS. **Report:** the two levels. Under the
   port T1 sits about 24 dB below its source (STEM_REC.md section 9,
   unexplained).
7. **Stock saves.** After the takes: save the project, save a sample,
   power cycle, and load both. **Report:** both save and both load.

**Stop conditions.**

- **MAIN MENU won't open, draws wrong, or hangs:** power cycle. If the unit
  won't come back to a working screen, go to the Startup Menu and send the
  stock `.syx` (step 1 above).
- **A hang when REC is pressed:** power cycle and stop the session
  ("The unit hangs when STEM REC's REC is pressed" below).
- **A take that never appears while card access stops working:**
  STEM_REC.md 11.4. Power cycle, and don't use that card for this test
  again.
- **The whole unit freezing during or after a take:** power cycle, stop the
  session, and report the card's make and model.

**After the flash.** Every result, good and bad, goes into
`docs/firmware/STEM_REC.md` (a new "Hardware" section), any new failure
into `docs/contributing/FAILURE_MODES.md`, the image into `CHANGELOG.md`, and
the Status of `remixes/test/stems/README.md` is updated.

## What the first flash could hit, predicted 🔮

Carried from `git show 7935fd9c:docs/remixer/FAILURE_MODES.md` (30 Sep 2026), which upstream
replaced by `docs/contributing/FAILURE_MODES.md`, a register of modes seen
on hardware. These are predictions for a module not yet flashed; an entry
moves to that register the moment its mode is seen on a unit.

None of these has been seen on hardware: STEM REC is unflashed as of 13 Sep
2026. Each entry is predicted from the port or known by design, and says
which. Move an entry out of this block, with its **Seen** line, the moment
it happens on the unit. Background for all of them:
`docs/firmware/STEM_REC.md` sections 10 and 11, and `modules/stems/README.md`.

#### No file after a take

**Symptom.** A take was made, and no `YYMMDD-HHMM` folder with a `T1.wav`
appears in the set's AUDIO folder.

**Cause.** Predicted. The unit shows no error, but the module keeps one in
its status word: 1 overflow, 2 path (no set mounted, or the set path is too
long), 3 open, 4 the file exists, 5 write, 6 seek, 7 close, 8 task. The likeliest
on a working card is 4: a second take in the same minute is refused by
design, and the first take is left intact.

**First check.** Was there an earlier take in the same minute? Is a set
mounted, with its AUDIO folder present? Then reproduce under the port with
the same project and read the status word from `--mem-dump` of
`stems_state` (the second of the six words): its value names the step that
failed.

#### The unit hangs when STEM REC's REC is pressed

**Symptom.** Pressing REC in MAIN MENU › STEMS freezes the unit. (Until
29 Sep 2026 the row was MAIN MENU › CONTROL › STEM REC.)

**Cause.** Predicted, and untested on the unit. The first press creates the
writer task (STEM_REC.md section 3), and every press changes the state with
interrupts masked for a few instructions. Under the port both run and
return (STEM_REC.md 11.1), from the port's call and from the real key
(`verify_stems_menu`, section 16).

**First check.** Does it happen on the first press after power-on only?
Then it is task creation. Run the same image under the port with the same
project and `--call-before-play` of `stems_action`, and look for a fault or
a hang in the port's report.

#### Audio drops or clicks while recording

**Symptom.** Dropouts or clicks in the unit's own output while a take runs.

**Cause.** Predicted, unmeasured on the unit. The frame hook runs 130
instructions per frame while recording T1, and 739 for eight tracks, in the
audio interrupt (STEM_REC.md 12.2). Its time on the unit isn't measured.
The streaming build also writes to the card during the take, from the
writer task at priority 1. Whether those writes disturb the audio isn't
measured either.

**First check.** Does it happen only while RECORDING, and not while ARMED
(17 instructions) or IDLE (2)? Compare with the same project in the stock
OS.

#### The take never appears, and card access stops working

**Symptom.** After a take, its file never appears. Loading or saving
anything on the card afterwards does not finish. Audio already playing
continues.

**Cause.** Predicted from the port (STEM_REC.md 11.4). If the card aborts a
write command, the stock card driver waits for it forever, with no error
check and no timeout, inside the writer task, which holds the file layer's
lock. Main, at priority 0, never runs again. It is a stock limitation: the
stock sample save goes through the same routine. Whether a real card ever
aborts a write this way is not measured.

**Fix.** Power cycle. Then check the card on a computer, and do not use it
for STEM REC again until it passes.

#### The whole unit freezes while a take is written

**Symptom.** During a take, or after it stops, the unit freezes: the
audio stops or sticks, and the screen and the keys stop answering. The take
never appears.

**Cause.** Seen under the port before the module's fix, and not expected
since (STEM_REC.md 11.7). The stock PIO card write updates the card
handler's data pointer and sector count only after it has sent a write's
first sector. An interrupt landing in between left the handler one sector
short of the card, waiting forever at level 5, so no audio frame was
taken again. The module patches the routine to update both first. If this
is seen on the unit, either the patch did not take, or the card uses the
stock DMA write path, which the patch does not touch and which is not
analysed.

**First check.** Does `0x40014cfe` in the flashed image hold `jmp
stems_ata_first` (`verify_stems.py` checks it)? Does the card report DMA?
Then power cycle, and try the same take with another card.

#### A take plays with a repeated or missing 512-byte block

**Symptom.** A take has one 512-byte stretch, about 3 ms, repeated, or the
audio after some point is shifted by 512 bytes, with no error reported.

**Cause.** The other outcome of the same stock race (STEM_REC.md 11.7),
possible only on a write command of more than one sector: if the interrupt
lands before the routine has updated the pointer, the handler sends the
first sector twice. Under the port, 3 of a 15-second take's 2,656 write
commands had more than one sector. On a single sector, the same race is the
freeze above. The fix covers both, and under the port the 15-second take's
file equals the ring byte for byte. Not expected on the unit, for the same
reasons as the freeze.

**First check.** Where in the file is the repeat? A write command starts on
a sector boundary, so the repeat starts at a multiple of 512 bytes from
the start of the file.

#### A take with foreign bytes in it, or a bank that loads wrong after a take

**Retired for STEM REC's streaming build** (22 Sep 2026): STEM REC no
longer uses the shared buffer. Kept for the tag 27 image and for stock's
own saves.

**Symptom.** A take has a stretch of noise or non-audio data, or after a
take a bank (not the current one) loads with wrong or garbled content.

**Cause.** Predicted from the code, not seen (STEM_REC.md 7.5a). The file
layer stages every buffered read and write through one unlocked buffer,
`0x4ecd3000`. About 1 s after every STOP, stock saves each dirty bank other
than the current one through that layer, on the engine task. STEM REC
writes its take at STOP, on its own task at the same priority. If the two
overlap, either file can get the other's bytes. The trigger is a bank other
than the current one having been edited since it was last saved.

**First check.** Was a bank other than the current one edited before the
take? Compare the damaged bank's `.work` with a backup: audio-like bytes
in it point here. Then reproduce under the port with a second bank dirty
and a write watch on `0x4ecd3000`.

#### After a power cut or a card pull, a take's files are empty

**Symptom.** A take's `Tn.wav` files exist but have zero length.

**Cause.** Measured under the port (STEM_REC.md 12.3). The audio is
streamed while recording, but each file's length is set only at the end,
with its real header. A take cut off before the end leaves a 0-byte file:
under the port, 1,024 frames streamed and the directory entry still said
0 bytes. The streamed sectors are on the card, but no file reaches them.

**Fix.** None in this build. Wait at least 5 seconds after the stop
before you pull the card or power off. Setting the length every few
chunks would keep a cut-off take playable; it isn't built.

#### A take on a nearly full card

**Symptom.** A take on a nearly full card is shorter than the performance,
won't open, or reports more data than it plays.

**Cause.** Not analysed. When the card runs out of space, the raw write's
answer is unknown: STEM_REC.md 12.1 found its return value isn't a sector
or byte count, and the writer checks only its sign. If a write that found
no space still returns a non-negative value, the header can claim data
that isn't there.

**First check.** The card's free space against the take's length: a T1
take needs about 10.6 MB a minute. Reproduce under the port on a small
card image.

## Crosscheck's flash plan, a record

Carried from crosscheck's flash plan, `git show 7dee174:docs/effects/FLASHPLAN.md` (branch `crosscheck`), which upstream does not have: upstream records flashed images in `CHANGELOG.md`, and this one was never flashed.

⚠️ **A record, not the plan for this branch.** It builds tag 28 from branch `crosscheck`, and what it says about the emulator is about crosscheck's port, which could not draw the screen; upstream's can (`--lcd`, `--live`). Flash A, piece 4 of the roadmap (`git show 4d2d6456:docs/superpowers/specs/2026-09-26-stem-rec-upstream-port-design.md`), gets its own plan on this branch, built from this record.

### Flash 13 — `stems`, tag 28: STEM REC streams T1 to the card (staged 13 Sep 2026, restaged 14 Sep, restaged for streaming 23 Sep)

STEM REC alone (`modules/stems`, `modules/stems/README.md`), so a first
flash can only fail in one module's ways. This is the streaming build: it
writes the take to the card while it records, so a take runs until it's
stopped, up to 60 minutes (STEM_REC.md section 12). Build it from branch
`crosscheck` at the streaming plan's last commit, with
`make image REMIX=stems BUILD=28` → `out/OCTATRACK_OCTABAM28.bin` /
`out/OCTATRACK_OS1.40C_OCTABAM28.syx`. Yves builds it; the hashes are his
to record here. `make check REMIX=stems` and `verify_stems.py --long` (a
20-second take) pass on that branch; every claim below was measured under
the ColdFire port first (`docs/firmware/STEM_REC.md` sections 10 to 12).
Tag 27's images are withdrawn, for the two reasons below. ❌ The 13 Sep image
(`22d98c51…` / `0488b824…`, OS `c3cf29d9…`) is withdrawn: under the port its
15-second take froze the whole unit (STEM_REC.md 11.7). Do not flash it.

❌ **The 14 Sep image above is withdrawn too (22 Sep 2026): it records T3,
not T1.** Its module read T1 from the read-back block's third slot. Stock
puts track k at k × 0x80, so the third slot is T3 (STEM_REC.md 9.2,
corrected; the fixture's NEIGHBOR chain on T2 and T3 had hidden it). The
fix is `T1_OFFSET = 0x00` on branch `crosscheck`. **Rebuild the image from
that branch and take the new hashes before this flash. Do not flash
`e1596682…`.**

⚠️ **Confirm 28 is unused before you copy it.** The last tag flashed in
this series on any branch this clone has fetched is 26 (Flash 12), and 27
was built but withdrawn. If another machine flashed a 28 since, rebuild
with the next free number.

⚠️ **Use a spare card, not a backed-up working card.** Two risks were
accepted for the proof of concept (Yves, 12 Sep 2026). The first still has
a do-not; the streaming build retires the second:

1. The writer task sleeps on the kernel's shared timer, which holds one
   waiter (STEM_REC.md 4.7). **Once STEM REC has been selected since
   power-on, do not run an OS upgrade without a power cycle first.**
2. STEM REC no longer uses the shared staging buffer (STEM_REC.md 12.0).
   Stock's own saves still share it with each other, as in stock.

⚠️ **The STEM REC row may not show.** STEM REC reaches CONTROL the way the
bus screen and MENU SHORTCUT did: count 6 → 7 at `0x400cbd54` and the row
pointer at `+0x18` repointed. That worked on the unit for the bus screen
(tags 85–90), and it failed on tag 16 with the right bytes in the image.
`FAILURE_MODES.md`, "CONTROL menu shows its stock six rows", is still open
🔴 with no known cause. The port tests call STEM REC's action directly and
have never opened the menu. main's copy of that entry says to open CONTROL
in the ColdFire emulator's own menu before any flash that appends rows.
main's port can now draw the screen and take keys (`ot_emu --live`,
18 Sep 2026); this branch's port can't. If the row is missing on the unit,
the flash tests nothing else. (Added 22 Sep 2026, cross-check.)

⚠️ **This image patches a stock card routine.** The stock PIO card write
has a race (STEM_REC.md 11.7): an interrupt at the wrong instruction either
writes a sector twice with no error, or leaves the card handler waiting
forever with the audio frame blocked, which freezes the unit. The first
15-second take under the port hit the freeze. STEM REC patches the routine
(`stems_ata_first`), and that changes every PIO write on the unit, stock
saves included. A card that reports DMA takes the stock DMA path instead,
where the patch never runs; that path is not analysed. Yves chose to ship
the patch in this flash (14 Sep 2026) rather than leave the race in. Test 4
below checks that stock saves still work.

⚠️ **Yves's card takes the DMA path.** The card for this flash is a SanDisk
Extreme 64 GB, UDMA 7. A card that lists any UDMA mode gets the driver's DMA
table (STEM_REC.md 11.7), so on this card the patch never runs. Every take
goes through the stock WRITE DMA path, which the port cannot run. So on this
card, test 4 checks stock saves but not the patch. 🟡 Inferred from the
card's rating: its IDENTIFY data has not been read.
✅ Read 22 Sep 2026 (STEM_REC.md 11.8): the WRITE DMA path has no
counterpart to the PIO race. The hardware moves every sector, one interrupt
ends the command, and transmission errors are retried. A card that refuses
a write does not hang it, but the error may not be reported, so check
test 1's file length. It has still never been run by any emulator.

**How a take behaves.** The take is written to the card while it runs, in
512-frame chunks (about 0.19 s of audio each). At the end, the writer
writes the rest, then each file's real header and exact length. **Wait
at least 5 seconds after the stop before you pull the card or power
off.** The folder isn't a signal: it appears when the take starts. A take
cut off before the end leaves 0-byte files (STEM_REC.md 12.3). Under the
port the end took under 2 ms, but the port's card answers at once; the
5 seconds is a margin, not a measurement. The screen shows nothing, and
STEM REC ignores a select while the end is written. Use a card with
plenty of free space: a full card isn't analysed (FAILURE_MODES.md). If the card falls behind
and the 4 MiB ring fills (about 24 s of T1), the take stops by itself at
the last whole frame. The folder is `YYMMDD-HHMM` from the unit's clock. Under the
port every take is `000000-0000`, because the port's clock reads 0.

**One expectation.** Under the port, T1 sits in the read-back block about
24 dB below its source sample (STEM_REC.md section 9, unexplained). A quiet
take is a known possibility. Record the same pattern with the stock
recorder, resampling T1, and compare the two levels.

The three tests of the spec's section 11, then one for the patch, in order:

1. **Record at least 60 s** with Flex machines only, stopped with STEM
   REC. **Report:** the folder name and the unit's clock, `T1.wav`'s
   length (data bytes = frames × 64), whether it plays whole in a DAW, and
   any dropout heard live. Also the card's make, model and size: whether it
   reports DMA decides which stock write path ran.
2. **The same with a static machine playing.** A static machine streams
   from the card, and the take now writes to the card while it records, so
   the two overlap for the whole take. **Report:** whether the static
   machine's playback glitched during the take, and whether the take is
   intact.
3. **Arm while stopped, then press PLAY.** Then a second take stopped with
   the sequencer's STOP, and a third stopped with STEM REC, each in a new
   minute. **Report:** that the first take starts on the first step, and
   that all three files are there and play. Then select STEM REC twice in
   one minute: the second take must be refused, and the first must stay
   intact.
4. **Stock saves still work.** On this image, after the takes: save the
   project, save a sample (the stock recorder's take from test 1 will do),
   power cycle, and load both back. **Report:** that both saved and both
   load. This is the patch's test: it changes the stock routine those saves
   use on a PIO card.

**Stop conditions.** A hang when STEM REC is selected: power cycle, and
stop the session. A take that never appears while card access stops
working: this is STEM_REC.md 11.4, a card that aborts a write hanging the
stock driver. Power cycle, and do not use that card again for this test.
The whole unit freezing, audio and keys, during or after a take: the race of
STEM_REC.md 11.7, which the patch should prevent. Power cycle, stop the
session, and report the card's make and model. A stock save that fails in
test 4: power cycle, stop the session, and go back to a stock OS for that
card.
Every new failure goes into `docs/contributing/FAILURE_MODES.md` the moment
it is seen; what is predicted is in this file's own block above.

**After the flash:** every result, good and bad, goes into
`docs/firmware/STEM_REC.md` (a new "Hardware" section) and
`FAILURE_MODES.md`, and the Status of `remixes/test/stems/README.md` is updated.
