# STEM REC

MAIN MENU › CONTROL › STEM REC records track 1 to the card while the
sequencer plays. A take is 16-bit stereo at 44,100 Hz, at most 15 seconds
long, and it lands as `<set>/AUDIO/YYMMDD-HHMM/T1.wav`. This is a proof of
concept: the first step of `docs/proposals/MULTITRACK_TO_CARD.md`.

- The design: `docs/superpowers/specs/2026-09-10-stem-rec-poc-design.md`.
- Every stock address the module uses, with its evidence:
  `docs/firmware/STEM_REC.md`.
- The remix: `stems`, STEM REC alone. `make image REMIX=stems` builds it.

## Status

**Measured under the ColdFire port, unflashed.** `tools/verify/verify_stems.py`,
part of `make check REMIX=stems`, runs the module on a fixture project with a
kick on T1. It reads each take back off the port's card and checks the
header, the sizes and every sample. Every sample equals T1's post-FX2
read-back block at a fixed lag. `--long` adds a whole 15-second take, whose
file must equal the ring byte for byte (about 15 minutes, outside
`make check`).

| measured under the port | value | STEM_REC.md |
|---|---|---|
| the frame hook, IDLE | 2 instructions per frame | 10.2 |
| the frame hook, ARMED | 17 instructions per frame | 10.2 |
| the frame hook, RECORDING | 122 instructions per frame | 10.2 |
| the writer task's stack peak | 1,048 of 8,192 bytes | 11.6 |
| writing a 15-second take after it stops | 1,892 frames, 0.69 s of port time | 11.7 |
| writing the whole 4 MiB ring after a take | 2,879 frames, 1.04 s of port time | 11.5 |

The hook's figures are instruction counts. Its time on the unit is not
measured. The write time is the port's: its card model answers at once, so
the unit's card will be slower.

Known from the port, before any flash:

- **Every port take is named `000000-0000`**, because the port's clock
  reads 0. The name comes from the unit's own clock, and the order of its
  fields is first checked on the unit (STEM_REC.md 11.2).
- **T1 sits about 24 dB below its source sample** in the read-back block
  under the port, unexplained (STEM_REC.md section 9). A quiet take is a
  known possibility.
- **A card that aborts a write command hangs the writer** inside the stock
  card driver, which has no timeout. Recovery is a power cycle. The stock
  sample save shares this (STEM_REC.md 11.4).
- **The stock PIO card write has a race, and the module fixes it.** The
  first 15-second take under the port stalled the whole unit: an interrupt
  landed between the stock routine sending a write's first sector and
  updating the card handler's pointer and count, and the handler then
  waited forever with the frame interrupt blocked. On the rarer writes of
  more than one sector, the same race can instead write a sector twice
  without an error. The module patches the stock
  routine to update both first (STEM_REC.md 11.7). The patch changes every
  PIO card write, not only STEM REC's. A card that reports DMA takes a
  different stock path, where the patch never runs.

## How to use it

1. Open MAIN MENU › CONTROL and select **STEM REC**.
   - If the sequencer is stopped, STEM REC arms. Recording starts on the
     first frame the sequencer plays.
   - If the sequencer is running, recording starts at once.
2. The take stops when the sequencer stops, after 15 seconds, or when you
   select STEM REC again. Selecting it while armed cancels the arm.
3. The take is then written to the card. Nothing is on the card until that
   write ends. Wait until the take's folder shows in the audio pool before
   you pull the card or power off.

The screen shows nothing. You know a take worked when its folder is on the
card.

## Limits

- T1 only, 16-bit, at most 15 seconds.
- No screen feedback, and no error report on the unit.
- The name has no seconds. A second take in the same minute is refused, and
  the first stays intact.
- A power cut or a card pull before the write ends loses the take.
- Loading a project while recording is not detected. Do not do it.
- Two risks accepted for the proof of concept (Yves, 12 Sep 2026):
  - The writer task sleeps on a shared timer that holds one waiter
    (STEM_REC.md 4.7). Once STEM REC has been selected since power-on, do
    not run CF PROBE or an OS upgrade until you have power cycled.
  - The file layer's staging buffer is shared and unlocked (STEM_REC.md
    7.5). Do not save a sample while a take is being written.

## How it works

- **The frame hook.** A detour at the per-frame routine's only call site,
  `0x40004b12`, in the audio interrupt. While recording, it copies T1's
  16 stereo samples from the read-back block into a 4 MiB ring each frame,
  keeping the top 16 bits of each 24-bit sample. It calls nothing and uses
  no RTOS service.
- **The writer task.** The module's own RTOS task at priority 1, created the
  first time STEM REC is selected. It sleeps 10 ms a pass. Once a take has
  stopped, it names it from the clock, creates the folder, refuses a file
  that exists, and writes the header with its final sizes, then the ring,
  then closes. It never seeks: the file layer's seek does not flush and its
  close sets the file's length to the write position (STEM_REC.md 7.10).
- **The first-sector fix.** A detour in the stock PIO write routine at
  `0x40014cfe`. It advances the card handler's data pointer and sector
  count before the first sector goes out, not after, so a card interrupt
  can never find them stale (STEM_REC.md 11.7).
- **The memory.** The ring and the task's 8 KB stack are DRAM regions at
  the free top of the platform's arena reserve, so the module costs no
  sample memory beyond what any DRAM remix already gives up.

It shares the frame site with CF PROBE and the CONTROL list with MENU
SHORTCUT. The ledger refuses both pairings by name.
