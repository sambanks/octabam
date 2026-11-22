# TRACK PATTERNS testing

## ColdFire port (21 Oct 2026)

Image: native remix `trackpatterns-test` (TRACK PATTERNS + the 14 stock
effects) built in a Modwerk worktree at `c0f513b9` with `make bus`; the six
sites carry their jumps (the rebuild spans padded with `nop`). Emulator
`ot_emu` from the same tree. Project: a copy of the contributor's own,
clock and transport receive off, bank A with `ot_spec.py`: A01 T1 trigs on
steps 1, 5, 9, 13; A03 T1 on 3, 7, 11, 15; both 16 steps at 1X. Script:
NO (the date popup), PLAY, at 4 s a poke of T1's queue (`next[0] = 3`, A03;
no key gesture yet), STOP at 9 s. Watched: T1's counter `0x800064d0`, the
step handler's per-track trig entry `0x46c7a810` (a plain trig writes
`0x1d` at `0x4009d42a`) and `tp_state`.

| | result |
|---|---|
| T1's plain trigs before the change | steps 5, 9, 13, 1, 5, 9, 13 (A01) |
| the queue lands | at 15.97 s, the step T1's counter wraps to step 1: `src[T1] = A03`, `next` cleared |
| T1's plain trigs after it | steps 3, 7, 11, 15, round after round (A03), the global pattern still A01 |

Port evidence only, one track, queued by a poke.

## Gesture, MIDI track, global change (21 Oct 2026)

**Stock first.** On the image above (no gesture site yet, so the keys are
stock): hold TRACK 1, hold PATTERN, press TRIG 3 while playing. Stock
queued A03 for every track (`0x800065c0 <- 2` at `0x400a06dc`) and played
it at the pattern's end. TRACK 1's key state (`0x46c7d8ee + 24 * 0x10`)
went 1 on the press (pc `0x40031936`), then 2 when the PATTERN layer opened
over it (`0x400312e8`), and 0 on the release (`0x4003180c`). So the
combination has no meaning of its own in stock, and the trig still reaches
the PATTERN layer's handler with the TRACK key still marked as held.

**Image:** the same remix rebuilt with the seventh detour (`0x40056b50 ->
tp_pattern_key`) and the bank-aware tick. `tp_state` at `0x40a95f2c`.

**Project** `STEPTPM`: a copy of `STEPTP` plus A02 T1 trigs on 2 and 10
(`ot_spec.py`), and M1's trig mask written into the bank file's MTRA
records (tag + 9, as the TRAC records): A01 M1 on 1 and 9, A03 M1 on 5 and
13. `.work` and `.strd` checksummed and read back.

**Script:** NO, PLAY; at 3 s hold TRACK 1, hold PATTERN, TRIG 3; at 5 s the
MIDI key (MIDI mode), then the same gesture; at 6.8 s the MIDI key again; at
10 s PATTERN + TRIG 2 with no TRACK key held; STOP at 14 s. Watched: the
playing and queued pattern, `0x80000012`, `src`/`next` of T1 and M1, the
engine's global id, the per-track trig entry `0x46c7a810[0]` (a plain trig
writes `0x1d`: at `0x4009d42a` for T1, at `0x4009d0fc` in the MIDI step
handler for M1), the counters `0x800064d0` and `0x800064d8`.

| | result |
|---|---|
| before any change | T1 on steps 1, 5, 9, 13 and M1 on 1, 9 (A01) |
| TRACK 1 + PATTERN + TRIG 3 | `next[T1] = A03` (15.31 s); no global queue written; the toast reads `T1 ▸ A03` over the A01 screen (the display draws `>` as ▸) |
| T1's loop start | `src[T1] = A03` at 15.97 s; then T1 on 3, 7, 11, 15 round after round; M1 still on 1, 9 |
| MIDI mode, the same gesture | `0x80000012 = 1`; `next[M1] = A03` (17.81 s), T1 untouched |
| M1's loop start | `src[M1] = A03` at 19.13 s; then M1 on 5, 13; T1 still on A03 |
| PATTERN + TRIG 2, no TRACK held | stock's global queue (`0x800065c0 = 1`, 22.11 s); A02 plays at 22.27 s; at the next step the engine clears `src` and `next` of T1 and M1 and records A02 |
| after the global change | T1 on 2, 10 (A02's); M1 silent (A02 has no M1 trigs); no stray A03 step at the change |

Not run yet: MIDI out notes (M1 has no channel in the project copy, so
UART0 carried MIDI clock only) and note-offs across a switch; a bank change
under the port (host-tested only); the latched PATTERN (a tap, then TRACK +
TRIG); TRACK pressed after PATTERN; the rebuild path (an edit while a track
is on another pattern); a different length per track; Play Modes built
alongside; cycle counts; any unit.

## Unit build 1 (21 Oct 2026)

`make image REMIX=trackpatterns-test BUILD=1` in the Modwerk scratch
worktree (`c0f513b9`), module source = this repository at `3c581df`, from
the contributor's own OS 1.40C (`.syx` `0a8d2d2b35c2…`, `.bin`
`34695b606eb0…`, Elektron's files). Version string `OCTABAM1`.

| file | SHA-256 |
|---|---|
| `OCTATRACK_OCTABAM1.bin` (card path) | `ec04c849fb85513ba3d9c3863af501233bb61e7edd3387c2cea598506cce2db4` |
| `OCTATRACK_OS1.40C_OCTABAM1.syx` (MIDI path) | `a54d8d1810a198c93f8368b0f151ce69678cd1432e41744b87cc5ced9adad9d0` |
| `mainos_bus.bin` (the OS section the emulator runs) | `906085659919a8b41394f7e4ce253258cccb52418a63d34d6a8555b5e6aa7849` |

The card file's checksum validates (`bin_decode.py`). The gesture run above
repeated on this exact `mainos_bus.bin` gives the same 72 events at the same
times, booted as an MKI (the emulator's default, as every run above) and
with `--mkii`.

## Build 2: the trig LEDs (21 Oct 2026, emulator only)

`make image REMIX=trackpatterns-test BUILD=2`, same tree and OS; adds the
eighth detour `0x4007e9b6 -> tp_led_pass`. `tp_state` at `0x40a96304`.

| file | SHA-256 |
|---|---|
| `OCTATRACK_OCTABAM2.bin` | `53ccd9fe47002bc4a387a1bc343d77fc6f75f5bc5953172d6a45d7c041aa4ef3` |
| `OCTATRACK_OS1.40C_OCTABAM2.syx` | `f4ed7ea63a741b9818e13b4e623ec0c06e61e1520e6c0c7cf1f0aa957dda1ee2` |
| `mainos_bus.bin` | `56372a524128051a1eb5210a97a1cc678b1b03689a4867e47145a2afa3e03851` |

**Stock first** (`STEPTPM`, playing A01): outside GRID REC the trig keys
show only the running light (both LEDs of the playhead's key, moving every
100 ms at 152 BPM); GRID REC shows A01's T1 trigs on keys 1, 5, 9, 13 (first
LEDs) plus second LEDs the project's own data sets; with PATTERN held, A01's
key lights its first LED and A02, A03 their second (patterns with content).

**Run** (`--mkii`, then the same as an MKI): play; the gesture puts T1 on
A03 (lands at 15.97 s); 3 s later GRID REC on for 2 s, off; then TRACK 1 +
PATTERN held for 0.8 s. Watched: the trig LED bytes `0x460ba98c..f` (state
rebuilt every 50 ms), `src[T1]`, GRID REC, PATTERN held.

| | result |
|---|---|
| T1 on A03, outside GRID REC | A03's trigs (LEDs 4, 12, 20, 28: keys 3, 7, 11, 15) on for about 500 ms, off for about 500 ms; the running light moves through both halves |
| T1 on A03, GRID REC | stock's A01 view for about 500 ms, then about 500 ms with only the running light, repeating |
| TRACK 1 + PATTERN held | LEDs 1, 3, 4: A03 (key 3) as the current pattern, A01 and A02 as patterns with content |
| MKI against MKII | the same LED timeline (event times within 1 ms) |
| the gesture run of build 1, repeated (`--mkii`) | the same 72 events and values in the same order, trigs at the same times; the overrides clear 20 ms earlier at the global change (22.27 s, not 22.29 s), because the LED pass now notices the new pattern first |

Not run under the emulator: MIDI mode's LEDs (host-tested only), patterns
longer than 16 steps, the cycle cost of the LED pass.

## Build 3: from this tree (21 Oct 2026)

`make image REMIX=trackpatterns BUILD=3` in octabam at `828edcac` with this
module (branch `trackpatterns`), from the contributor's own OS 1.40C (MAIN
OS section `164f3122…`). The eight detours land on the same addresses as
build 2; `tp_state` at `0x40a96304`. The card file's checksum validates.

| file | SHA-256 |
|---|---|
| `OCTATRACK_OCTABAM3.bin` | `a3712dbb2cbefb26895ed42255f5e6e3809379a85bc8297516c5370398200569` |
| `OCTATRACK_OS1.40C_OCTABAM3.syx` | `bc205ce0868578a672939137ff147ebb9bbd17b4eacaa0e1c30fcd6752875ee0` |
| `mainos_bus.bin` | `70b0e299869f576525b33a753d0b5c434ebf789fde08ca68aa1ed7f50e90545c` |

Under this tree's `ot_emu --mkii`, the gesture run and the LED run of build
2 repeated on this exact image: the same 72 events and values in the same
order, every event about 30 ms later (the load ends later); the LEDs as
build 2's (A03's trigs blinking about 500 ms on, 500 ms off outside GRID
REC, A01's in GRID REC, the running light kept; TRACK 1 + PATTERN lighting
LEDs 1, 3, 4).

## Review round 1 (22 Oct 2026, emulator)

After the maintainer's review of `02d69e57`, on `4ba865a1` (main merged).

**Cost.** `ot_emu --mkii`, this build, the gesture, MIDI and global-change
script (`STEPTPM`); `--watch-pc` on each detour's entry and on the stock
instruction it returns to; the instruction count between the two, per
call (the replayed stock instructions included):

| detour | calls | min | median | 99th pct | max |
|---|---|---|---|---|---|
| audio tick | 1,096 | 85 | 86 | 89 | 95 |
| MIDI tick | 1,096 | 88 | 89 | 92 | 98 |
| audio advance | 1,088 | 60 | 60 | 84 | 186 |
| MIDI advance | 1,088 | 60 | 60 | 84 | 84 |
| the LED pass's own part (`0x40a962d2` to `0x4007e9bc`, the LED script) | 572 | 52 | 52 | 658 | 658 |

Memory: the build report's 3,457 B code + data, 0 B `.bss`; stack frames
from `-fstack-usage` (`tp_leds` 48 B, `tp_key` 24 B, `tp_seq_pattern` 20 B;
the tick's chain about 72 B below its caller).

**Beside KITS and DIRECT_JUMP_KYOTI.** `remixes/test/trackpatterns-core`
(`octabam-core` + TRACK PATTERNS) builds; the ledger reports no conflict.
The gesture, MIDI and global-change run: the same 72 events and values in
the same order as build 3. The LED run, anchored to its own events (the
image's load ends about 1.7 s later): A03's trigs blinking outside GRID
REC, A01's in GRID REC, TRACK 1 + PATTERN lighting LEDs 1, 3, 4, as build 3.

**Patterns over 16 steps.** A03 at 32 steps, T1 trigs 3, 7, 11, 15, 19, 23,
27, 31 (`STEPTP32`), T1 switched by the gesture:

| A01 (global) | T1's loop on A03 |
|---|---|
| SCALE MODE NORMAL, length 16 | wraps at 16; steps 3, 7, 11, 15 only |
| PER TRACK, MASTER LENGTH 16 | wraps at 16 (the master length restarts every track) |
| PER TRACK, MASTER LENGTH 32 | wraps at 32: 3, 7, ... 31; T2 (A01) still at 16 |

The trig LEDs then showed GRID REC's page, not the playhead's: fixed in
`adapter.c` (the page of the track's step counter), with a host test. With
A03's T1 on 3, 7, 11, 15, 18, 22 (`STEPTP32Q`), the rows sent to the panel
(`0x460ba99d`) showed keys 3, 7, 11, 15 while T1 played steps 1-16 and keys
2, 6 while it played 17-32, blinking.

**Other trig modes.** T1 on A03, then the trig mode written to CHROMATIC
(`poke 0x460d16f3=1`, not the panel's keys): no trig LED row changed after
it, with this build and with the build without the LED pass alike.

Not run: any of this on a unit.

## Build 8: beside KITS and DIRECT_JUMP_KYOTI (22 Oct 2026)

`make image REMIX=trackpatterns-core BUILD=8` in octabam at `f1eb1507`,
from the contributor's own OS 1.40C; rebuilt at `05d8701c` (main merged),
the card file is byte-identical.

| file | SHA-256 |
|---|---|
| `OCTATRACK_OCTABAM8.bin` | `2a698188558cf31b7d9c30b0cc978ec97bdcbb5da654e67347ddb272c41c9458` |
| `OCTATRACK_OS1.40C_OCTABAM8.syx` | `4b38d1aaf72b7a2cc25f8ce9303fe1dcee687e08384375b6225d47e0aab1a403` |

## CF METER with and without the module (22 Oct 2026)

Two images from `05d8701c`, made from local probe remixes that are not in
the tree. Both have USB (TRACKS PRE, MAIN 1, CUE 1, MASTER 0, IN OFF), CF
METER, CF METER IDLE and the stock effects except DARK REV, which gives up
its words to the meter:

- `OCTABAM10`: TRACK PATTERNS and the modules above.
- `OCTABAM11`: the same without TRACK PATTERNS.

| file | SHA-256 |
|---|---|
| `OCTATRACK_OCTABAM10.bin` | `2bab0a39c9019b020e0f190330354fd85ed0136ccb2042847d04be887fcfd382` |
| `OCTATRACK_OS1.40C_OCTABAM10.syx` | `bf715b8761f4498a736ce7d8075b560024d4b5da52a549f823d05af5bfd4b21a` |
| `OCTATRACK_OCTABAM11.bin` | `90fa968b70ae07cc81376b082f38c03b0e05a8f84778ee03a532d3c84379c916` |
| `OCTATRACK_OS1.40C_OCTABAM11.syx` | `75511ebe723d795ae3599f501fff5106b1f84a007d2938223fbbfcfefe83814c` |

## Build 9: over 16 steps and other trig modes (22 Oct 2026)

`make image REMIX=trackpatterns BUILD=9` in octabam at `f1eb1507`. Rebuilt
at `05d8701c`, the card file is byte-identical.

| file | SHA-256 |
|---|---|
| `OCTATRACK_OCTABAM9.bin` | `4fb7b88903d21f5ea90f524978c14a0d79e063cd986c0c9dbc93d406eb16d2e7` |
| `OCTATRACK_OS1.40C_OCTABAM9.syx` | `b382bfdcfdc7e40b81a1af816589634394ba59011a496eb6326002b92267d337` |

## Not yet

On the unit: a long run, more tracks at once. Anywhere: the track's speed
from its own pattern, persistence, chip cycles per detour.
