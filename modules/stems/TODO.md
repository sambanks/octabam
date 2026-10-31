# STEM REC: what's next

Six items from Yves's list of 9 Oct 2026. Each has what happens now, a few
ways to do it, and a recommendation. Nothing here is built.

Sizes are rough. **Small**: a change inside the module and a gate.
**Medium**: a new routine, a new gate and a flash. **Large**: a new part of
the module, or a new module.

The firmware facts behind items 1 and 2 are in
[SAMPLE_SAVE.md section 8](../../docs/firmware/SAMPLE_SAVE.md#8-the-attribute-file-ot-and-the-tempo),
read from the image on 9 Oct 2026.

## Yves's notes of 26 Oct 2026, for the next iteration

From four takes on his MKII (`261026-2133` to `2137`, in his own folder,
not the repository), on the local image `LMSTEMS1` (`octabam` + STEM REC,
LOAD METER's refusal lifted in the build only). Since 9 Oct, STEMS has
moved from MAIN MENU to its own window, opened by UP + REC (`47013ec7`), and
takes go to `<set>/AUDIO/STEMS/<project>/<YYMMDD-HHMM>/` (`5822ebcc`).

1. **The tempo is wrong and the gain is 0 dB: no `.ot` was written** (item
   1). `LMSTEMS1` was built from main, and the `.ot` writer exists only on
   the online session's branch (`claude/bold-feynman-5y3cli` on the fork:
   `5b175689` the tempo, `635b719b` the gain). The four take folders hold
   no `.ot`, so the unit guessed, as item 1 predicts: `2133` 16 bars,
   129.90 BPM; `2135` 8 bars, 83.83 BPM; `2136` 16 bars, 103.26 BPM;
   `2137` 1 bar, 119.90 BPM. "1.5 BPM too high" fits `2133` at a project
   tempo of 128.4, for example. Next: bring the writer in, with the tempo
   read from `0x8000181c` (the word the stock recorder stores, not
   `0x80001814`), and MAIN's and CUE's gain at the tracks' +12 dB until it's
   measured: a measured 8 Oct take has MAIN equal to the sum of the stems
   to within 7 steps, so +24 dB on MAIN would play it 12 dB above its stems.
   Check every field against a stock `.ot` first (item 2 A).
2. **UP + REC works, but the window doesn't refresh while recording**
   (item 3). Two faults. When the window opens, `stems_enter` resets rows 1
   and 2 to `REC` and `READY` whatever the take is doing, until a key is
   pressed (`47013ec7`; the version flashed as STEMS1 to STEMS7 didn't).
   And nothing redraws it on a timer. The window is TUNER-shaped now, so
   TUNER's redraw from the UI task is the precedent (item 3 A).
   `verify_stems_menu` needs a check on the screen itself: it reads the
   labels from memory, which is why it passed.
3. **Our own load figures, or BRAIN's?** STEM REC measures itself:
   `STATS.TXT` (the hook's mean and longest time, the card's writes and
   rates, the writer's longest sleep) and the PEAK row (the ring's largest
   fill). BRAIN's PERFORMANCE already shows the frame interrupt's share and
   WORST FRAME (LOAD, with LOAD METER), each task's share (CPU) and the
   card's reads, writes and slowest command (CARD). Compare the two field
   by field. What BRAIN lacks, propose there instead of keeping it here.
   Likely candidates: the ring's fill, the hook's own time (it runs in the
   level-6 transfer chain, so CPU charges it to the task it interrupts), and
   STEM REC's writer as a named task (it isn't among BRAIN's 11 TCBs, so it
   lands in OTHER).
4. **Double tap YES to arm when the sequencer is stopped** (item 4). One
   YES already arms the stock recorders' one-shot buffers, so a second tap
   arming STEMS follows from it. Item 4's design stands. Yves's scope:
   arming when stopped.
5. **Logs in one place, the way BRAIN keeps them.** BRAIN writes
   `/BRAIN/debug.txt` (its MIDI debug log) and keeps its settings in
   `/BRAIN/card.work`. STEM REC writes `STATS.TXT` into each take's folder.
   Options: `/BRAIN/STEMS/<YYMMDD-HHMM>.txt`, one file a take, or one
   appended log under `/BRAIN/`. Read first how BRAIN writes (through the
   engine task) against how STEM REC writes (its own task, through the
   file layer's raw sector routines), so a log write can't block a take.
6. **A flatter folder.** Now:
   `<set>/AUDIO/STEMS/<project>/<YYMMDD-HHMM>/T1.wav`. Yves wants a flat
   folder of files named by take: `/STEMS/<YYMMDD-HHMM>-T1.wav`, or
   `<set>/AUDIO/_STEMS/<YYMMDD-HHMM>-T1.wav` if that's easier. Yves
   decided this on 26 Oct 2026: we go for our layout, which replaces the
   nested one from `5822ebcc`. To settle first:
   - **Where the browser can reach.** `<set>/AUDIO/` is the set's own
     sample pool, which the unit's file browser shows. A folder at the
     card's root is outside the set; whether the browser reaches it is
     unknown. `_STEMS` under AUDIO is the safe choice if it doesn't.
   - **Large folders.** How the browser handles a folder that collects 14
     files a take.
   - **The project name.** Dropped from the path. Whether it goes into
     the file name instead.
   - **Takes already on cards.** Takes under `AUDIO/STEMS/<project>/` and
     `AUDIO/<YYMMDD-HHMM>/` stay where they are; only new takes use the
     new layout.

   A flat folder also needs fewer folders made per take. That may fix
   verify_stems' take runs, which have failed on main since `5822ebcc`
   (bisected 21 Oct 2026). The likely cause is inferred, not measured:
   each take now checks for two more folders, and on a fresh card creates
   them, before it records.

### Where the six notes stand (27 Oct 2026, branch `stems-next`)

All six are in the code, and every gate passes under the port: the take
runs (`verify_stems`) and the menu on both panels (`verify_stems_menu`).
The unit hasn't run any of it yet: flash H in FLASH.md lists what only the
unit can show.

- **Note 6, the flat folder,** then a folder for each take (27 Oct 2026,
  after flash J: a full `!STEMS` slowed each take's start until a take at
  24 bits filled its ring before its first write; README, "Why a folder for
  each take"): `<set>/AUDIO/!STEMS/<take>/<take>-T1.wav`. A
  second take in one minute is `<take>-2`, up to 99 (Yves, 27 Oct 2026: a
  number instead of `SAME MINUTE`). A name is taken by its log or any file
  the take writes (since the folders, by its log or its folder). Measured under the port: a check of all sixteen file
  kinds made 17 card lookups at every start, each as long as an open (1.6
  M instructions), and 36 checks ran out of frames, so the check is one
  lookup and one a file. On `stems-next` the take runs passed before the
  change (73 of 73, measured), so what fails them on main isn't here;
  that PR #927 fixed it is inferred, not bisected.
- **Note 5, the log:** `/BRAIN/STEMS/<take>.TXT`. STEM REC makes the two
  folders; a failure costs only the log.
- **Note 1, the `.ot`:** the online session's writer, with the tempo from
  `0x8000181c`, +12 dB on every file and the checksum from byte 20. Still
  to check against a stock `.ot` (item 2 A).
- **Note 2, the refresh:** `stems_enter` keeps the labels; a detour at
  `0x40056c7c` in the UI task's loop redraws STEMS when they changed.
- **Note 4, the double tap:** a detour on the main page's YES handler
  (`0x4005e4c8`); 0.5 s (0.4 s until STEMS9: it missed Yves's taps); it arms or starts, never stops. A first tap
  lapses after 0.5 s: DTCN3 wraps every 32.5 s, so a waiting tap could
  have paired with a press much later (found in review, 27 Oct 2026).

Left for later (the final review's minor findings): the `STEMS ARMED`
toast can miss when the hook starts the take in the instant after the
arm; a card error in the name check walks all 99 numbers and says `SAME
MINUTE`; no gate checks "no `.ot` for an empty file"; with a clock that
stops or resets each boot, takes share minutes, and each start checks one
more name per earlier take of that minute. The size of `!STEMS` is out of
scope (Yves, 27 Oct 2026).
- **Note 3, the figures:** no duplicate, so the log keeps every line
  (README, "The log against BRAIN's PERFORMANCE page"). A proposal for Sam
  is drafted, not sent.

**The window as PERSONALIZE (27 Oct 2026, after flash H).** Yves found
STEMS's window bigger and plainer than the stock dialogs, and chose SYSTEM
> PERSONAL SETTINGS as the model from firmware-drawn mockups. STEMS is now
fifteen rows of a label and a value, five at a time, in MAIN MENU's window
and title band. STEM REC's row carries the state as its value. The pairs
sit on one row each, `AB` and `STEREO`, which splits into `A`, `B` and
`STEREO`, with LEFT and RIGHT to pick a checkbox as on MIDI SYNC. So a
mono pair can record one input alone. The menu gate compares STEMS with
PERSONALIZE drawn with STEMS's rows, pixel for pixel. Not on the unit yet.

## 1. The tempo isn't written to the stems

**Now.** STEM REC writes a bare WAV and no `.ot` file. The `.ot` is the
Octatrack's attribute file beside a sample: tempo, trim, loop, timestretch,
gain and slices. Without one, the unit guesses when it loads the file. It
assumes a power of two bars, picked from the length alone, so the tempo it
shows always lands between 80.75 and 161.5 BPM. It never reads the
project's tempo. A 61 s take at 120 BPM loads as 32 bars at 125.9 BPM.

**Check it first.** The guess predicts each of the nine takes of 8 Oct
2026, from its length alone. Load one file from a take into a Flex slot
and read TEMPO on the AUDIO EDITOR's ATTRIBUTES page. If the unit shows
these tempos, though the project's tempo didn't change between takes, the
cause is confirmed.

| take | length | guess |
|---|---|---|
| `261008-1131` | 6.75 s | 4 bars, 142.25 BPM |
| `261008-1421` | 18.08 s | 8 bars, 106.21 BPM |
| `261008-1422` | 62.80 s | 32 bars, 122.29 BPM |
| `261008-1423` | 28.98 s | 16 bars, 132.50 BPM |
| `261008-1424` | 44.63 s | 16 bars, 86.04 BPM |
| `261008-1425` | 69.77 s | 32 bars, 110.08 BPM |
| `261008-1426` | 17.89 s | 8 bars, 107.29 BPM |
| `261008-1856` | 61.35 s | 32 bars, 125.17 BPM |
| `261008-1858` | 4.31 s | 2 bars, 111.50 BPM |

The unit shows tenths, so a guess such as 142.25 can read 142.2 or 142.3.

**Options.**

- **A. Write an `.ot` beside each file.** Recommended. When a take starts,
  STEM REC keeps the project's tempo, as the stock recorder does. When it
  ends, the writer adds `T1.ot` and the rest beside the WAVs: 832 bytes
  each, the tempo as BPM × 24, the trim and loop lengths in bars from the
  firmware's own formula, and the trim end at the file's last sample.
  Fourteen small files at most, after the audio. Item 2 settles the fields
  the tempo doesn't decide. Size: small to medium.
- **B. Put the BPM in the file name**, such as `T1 120.wav`. The loader
  looks for the BPM in the name, but only among half, once and twice its
  guessed bar count. That helps only when a take is exactly a power of two
  bars long. Not worth it.
- **C. Stop on a bar line.** A take of whole bars lets the guess land right
  when the bar count is a power of two and the tempo is in range. Good for
  loops, but it doesn't fix the tempo by itself. Size: small.
- **D. A tempo chunk in the WAV** (`acid`), for DAWs. The Octatrack's
  reader ignores it: it reads `fmt `, `data`, `cue ` and `smpl` only.
  Optional, after A.

**Open.** A tempo change during a take: A keeps the tempo the take started
at. `STATS.TXT` could note a change.

## 2. What else the stock recorder sets

**Now.** A stock SAVE SAMPLE writes two files: the WAV and its `.ot`. The
`.ot` holds the tempo, the trim and loop lengths in bars, the timestretch
mode, the loop mode, the gain, the trig quantization, the trim start and
end, the loop point, up to 64 slices and a checksum. The recorder stamps the
project's tempo into a buffer when it records. STEM REC sets none of these.
Its WAV header is the same 44 bytes as stock's, and its RIFF size is right,
where stock's looks 8 bytes too large (SAMPLE_SAVE.md section 3).

**Not known.** The values the stock recorder gives the timestretch mode, the
loop mode, the gain and the trig quantization. Also the two header longs
the writer copies from RAM.

**Options.**

- **A. A reference `.ot` from the unit.** Recommended, and first. Record
  four bars with the stock recorder at an odd tempo, such as 123.4 BPM, and
  save it from the AUDIO EDITOR. Copy the `.wav` and the `.ot` off the
  card. Decoding that `.ot` answers every field. It also becomes item 1's
  oracle: STEM REC's `.ot` must match it field for field, apart from the
  lengths. No flash and no code.
- **B. Save a recorder buffer under the port.** The same answer without the
  unit, but the save path hasn't run under the port yet. Size: medium.
- **C. Slices at bar lines.** The `.ot` holds up to 64 slices. One slice a
  bar would make a stem ready to slice when it loads. Optional, after
  item 1.

## 3. A status that refreshes by itself

**Now.** MAIN MENU redraws only on a key, so the time, `SAVING` and `DONE`
show at the next key press (STEM_REC.md section 16.1).

**Options.**

- **A. Redraw from the UI task.** Recommended. The UI task is the firmware
  task that reads the keys and draws the screen. TUNER already hooks the top
  of that task's loop and redraws its window from there, about seven times
  a second ([TUNER](../tuner/README.md)). STEM REC would redraw the STEMS
  list from the same place when a label changed and the list is on screen.
  The catch:
  TUNER claims that exact spot, and the build refuses two modules on one
  spot. A remix with both needs a shared hook or another spot in the same
  loop. Size: small to medium.
- **B. Wake the UI task from the writer,** with a message that makes it
  redraw. The UI task's message format must be read first. Size: medium.
- **C. Move to a screen of our own** (item 6). It needs A's hook anyway.

## 4. Double tap YES to arm

**The goal** (Yves, 9 Oct 2026). On the main page, outside any dialog or
menu, one YES arms the stock recording trigs. A double tap should arm STEM
REC as well.

**Now** (read from the image, 9 Oct 2026). Both stock keymaps send YES to
`0x4005e4c8`, on press and on release.

- With no key held, a press sets every one-shot arm bit and shows `ARM
  ALL`. With a track key held, it arms that track and shows `ARM TRK` or
  `ARM REC TRK`.
- The arm only sets bits; it never toggles them. So a second YES repeats
  the same arm and changes nothing. A double tap is safe for the stock
  half.
- A menu or a dialog pushes its own key layer over YES (MAINMENU.md
  section 6c). So this handler hears YES only on the main page, which is
  the scope Yves wants.
- KITS hooks FUNC + YES (`0x4005e3d8`), a different handler. Nothing hooks
  plain YES.

**The design.** A detour at the handler's first instruction. On each press
on the `ARM ALL` path, it reads DMA timer 3, the counter `STATS.TXT`
already uses. If the previous press was less than about 0.4 s earlier,
STEM REC does what its REC row does: it arms, or it starts at once when
the sequencer runs. The stock arm still runs on both taps. The second tap
shows `STEMS ARMED` through the same stock message call that shows `ARM
ALL`, so the two are easy to tell apart. A gate under the port presses YES
twice and checks the state. Size: small to medium, plus a flash.

**Open.**

- **What a double tap does while a take records.** Performers tap YES
  quickly to re-arm one-shots, so a double tap can happen by accident. The
  safe choice: a double tap only arms or starts, and never stops or
  cancels. STOP and the menu still end a take.
- **Track key held.** A double tap with a track key held stays stock
  (`ARM TRK`), unless you want it to arm STEM REC for that track only.

## 5. A stem player machine

**The goal.** One track plays up to 16 files from one folder together, all
starting on the trig, as a one-shot. Yves, 9 Oct 2026: it behaves like
Static tracks, streaming from the card. So there's no RAM limit on length,
and no control per stem.

**Now.** [SYNTH MACHINE](../synth/README.md) shows how a module replaces a
machine's sound. A Flex track whose sample has a marker name
(`FMSYNTH*.wav`) gets a renderer of the module's own in place of the stock
one, and the DSP shapes the result like a sample. SYNTH already references
the STATIC renderer entry too. What isn't known: which task refills a
Static track from the card (STEM_REC.md section 19.2), and how fast the
card reads on the unit.

**Options.**

- **A. Our own streamer, behind a STATIC renderer.** Recommended. A Static
  track whose sample is a marker plays the files in the marker's folder.
  This is STEM REC in reverse. A reader task fills a ring per file from the
  card, and the renderer sums the rings into the track's voice. When the
  track loads, each ring gets the start of its file, so a trig starts at
  once. In a STEM REC take the names are fixed (`T1.wav` to `D.wav`), so
  no folder listing is needed; any other folder needs the file browser's
  listing routine, which isn't read yet. The track's FX, AMP and level
  apply to the sum. It plays at the recorded speed, because the stock
  renderer's timestretch and pitch are bypassed. Size: large.
- **B. Drive the stock Static streamer** for several files on one track.
  This needs the stock streaming task found and read first. Size: large,
  most of it reading the firmware.
- **C. Today, with no code.** Up to eight stems on eight Static tracks, or
  `MAIN.wav`, the mix, on one.

**Measure first.** Sixteen stereo files need 2.8 MB/s from the card at 16
bits, 4.2 MB/s at 24 bits. Reads aren't measured on the unit, and they'd
share the card and its file lock with the Static tracks that play. On a
busy project the card already falls behind STEM REC's writes (STEM_REC.md
section 17.3). A probe that reads sixteen files in a loop while a busy
project plays, and writes its rate to a text file like `STATS.TXT`, says
whether A can work before any of it is built. Size: small to medium, plus
a flash.

**Open.** Static plays 24-bit files from a 16-bit cache (BuMa's reading of
the code, STEM_REC.md section 19.1). A stem player could do the same, or sum all 24 bits.

## 6. A STEM REC screen

**Since 27 Oct 2026** STEMS is a 15-row list drawn as PERSONALIZE, five
rows on screen, and the status refreshes by itself (above). What follows
was written for the 18-row list of 9 Oct.

**Then.** STEMS is an 18-row list with seven rows on screen. The sources,
the format, the status and the peak all sit in that list, and the status
refreshes only on a key.

**Options.**

- **A. A full screen of our own.** Recommended as the goal. octalab's
  CAPTURE page draws one with stock calls that octalab documents (its
  `INPUT.md` section 10), and it owns the keys while it's open. One screen
  could hold the sources as a grid, the format, the state, the time, the
  ring's fill as a bar, and the time left on the card. The 16 trig keys
  could toggle the sources, with their LEDs showing which are on
  ([KEYMAP.md](../../tools/panel/KEYMAP.md) has the key and LED map). It
  ticks from item 3's hook. Every part has a precedent. Size: large.
- **B. A status window only.** Recommended as the first step. A window the
  size of TEMPO's, over any page, as TUNER's is. It shows the state, the
  time and the ring's fill, and it opens when a take arms or starts. The
  settings stay in MAIN MENU. Size: medium.
- **C. Tidy the list.** Fold the sources into one row that opens a short
  list of its own. It doesn't fix the status by itself. Size: small to
  medium.

**Open.** STEM REC doesn't read the card's free space yet (README,
"Limits"). The time left needs it.

## Order of work

1. Item 2 A: a reference `.ot` from the unit. No code.
2. Item 1 A: write the `.ot`, checked against that reference.
3. Item 3 A: redraw from the UI task.
4. Item 4: the double tap of YES.
5. Item 6 B, then A: the status window, then the full screen.
6. Item 5: the card read probe on the unit, then A as its own module.

Items 1 to 3 build on PR #644 (zero copy): the writer that would write the
`.ot` files is the one in that PR.
