# STEM REC: the cleanup inventory (29 Oct 2026)

A review of STEM REC's code for later rounds. Applied so far: 1.1's flat
case and 1.6 for the track loops (branch `stems-gainflat`, 4 Nov 2026,
STEM_REC.md 20.10), and 2.1's whole-cluster writes (20.11).

- **What was reviewed:** the hook path (`stems_frame_hook` to
  `stems_hook_end`, with the macros it uses) and the writer and card code
  (`stems_ata_first` to the end of `stems.s`, without `stems_ui`). The
  review read branch `stems-hookparts` with the 29 Oct cleanup in its
  working tree.
- **How:** four angles, as `/simplify` runs them: reuse, simplification,
  efficiency and altitude (a problem solved at the right depth, not
  patched with a special case).
- **The numbers:** savings are estimates. Instruction counts come from
  reading the code. Times use Bryan T's unit costs
  (`docs/firmware/CHIP.md`): a register op or cache hit ~2.9 ns, an
  uncached store 36 ns, a cached miss ~80 ns. Only items marked
  "confirmed" were checked against the code by a second reading.
- **Routines, not lines:** items name routines because line numbers move.

The hook's measured cost on Yves's MKII (STEMS11, 28 Oct 2026, 24 bits) is
a mean of 8 µs with T1 alone, 24 µs with seven files and 32 µs with eleven.
STEMS12's hook parts (STEM_REC.md 20.9) will say where it goes; items 1.1
and 1.3 depend on them.

## 0. Bugs and loose ends: first

1. **Confirmed: a failed header write doesn't stop the log.**
   - In `stems_finish`, a failed write at `.Lz_werr` sets `stems_status`
     to WRITE FAILED but not `stems_wfail`, and neither does `.Lz_seekerr`.
   - So `stems_stats` and `stems_otfiles` still write the log and the
     `.ot` files to a card that has just refused a write. README says the
     log isn't written when a card write failed.
   - The take's audio isn't affected.
   - Fix: set `stems_wfail` in both tails, or apply 2.4. Small.
2. **Possible, not verified: a take started while playing may begin on
   stale gains.**
   - On REC pressed while playing, the start edge skips staging while
     `stems_gqok` < 2. The next frame stages without testing it again.
   - If that frame's hook reads the sent index's transient 4 (STEM_REC.md
     18.1), no page is queued. The first staged frame then reads a gains
     frame written before IDLE.
   - It would be rare. Check under the port by poking `LV_SENT` to 4 on
     that frame. 1.12 removes the case.
3. **Test seam only:** `stems_probe_run` writes the ring's start without
   checking that the state is IDLE, and copies `SET_PATH` with no length
   bound.
4. **Doc:** README's Limits say the hook runs "394 while nothing records".
   That holds while the sequencer plays. While it's stopped, the mirror
   writes every slot's gains (about 968 instructions under the port; see
   1.10).

## 1. The hook (per frame)

Ranked by value. The gates named are those that would catch a mistake.

| # | Change | What it buys (estimated) | Risk and gate | Size |
|---|---|---|---|---|
| 1.1 | **Gains in a register while a fader rests.** For a slot whose ramp is flat this page, the mirror stores a flag and `g << 8` instead of 16 gains, and the track loops keep `g` in a register. This takes in "pre-shifted gains" from FLASH.md's list. **Applied** (4 Nov 2026, STEM_REC.md 20.10): the mirror stores the flag and `g`, and the loops shift it once. Left: a ramp slot's 16 gains (a descriptor the loops expand) | About 800 instructions (~2.3 µs) at eight tracks. Gain-queue lines touched fall from 80 to 16: up to ~5 µs more if STEMS12's `gains` part shows misses | Must stay bit-exact: the track units, `mirror_mask` | Medium |
| 1.2 | **Imprecise stores to the rings.** While a take records, ACR1 covers the rings' block as cache-inhibited, imprecise (the store buffer is on), with a `nop` before the tail copy and before the publish | Most of the ~9.5 µs that 264 precise stores cost at eleven files: 4 to 8 µs | High. Is ACR1 free in stock, and what else lies in that 16 MB block? Is the store order kept for the card's DMA? Needs a hardware probe. USB OUT writes its ring the same way (#956), so Bryan would gain too | Small code, large proof |
| 1.3 | **Hot state in the free on-chip SRAM.** A 16-byte record per file (routine, argument, write pointer, end), one gain state with its target cache: 384 of the 416 B left at `0x80007a60` | About 50 instructions, up to ~2.6 µs of line misses | It's the last free SRAM since #956: Sam's call. Tests poke `stems_wpos` and `stems_gsel` | Medium |
| 1.4 | **EMAC stalls.** The second sample in `acc2`/`acc3`, all four `mac.l`s before the first `movclr` (MCF54455RM 5.3.3: 3 cycles each now). `stems_emac_in`/`out` then keep `acc2`, `acc3` and `accext23` too | ~0.9 µs at eight tracks | Low: the track units | Small |
| 1.5 | **MAC with load.** `mac.l` that also loads the next sample | Up to 48 instructions a track (~1.1 µs at eight) | Medium: the port's MAC-with-load decode has known defects (TRAPS.md, trap-unicorn-macload). Registers are tight beside PACK12 | Medium |
| 1.6 | **One loop macro for the 16- and 24-bit families.** `stems_track16`/`24` and `stems_bus16`/`24` are eight hand-written loops that differ in shift, pack and limit. The 16-bit limited loop also does one sample a pass and reloads its shift. **Applied for the track loops** (4 Nov 2026): `TRACK_LOOP` writes all eight, and the 16-bit limited loop does two samples a pass with its shift in a register. Left: the bus loops | About 100 source lines. 32 instructions per limited 16-bit track. 1.1 then edits one place, not eight | Low: `HOOK_CEILING` must come out identical, and the units compare samples | Medium |
| 1.7 | **The half selection in `stems_half`.** `TRACK_IN` loses its `eori`, and `stems_half`'s `eori` of `PING_XOR` (0) goes | 2 a track and 2 (18 at eight tracks) | 18.5's half choice: the sample-exact port takes | Small |
| 1.8 | **MASTER TRACK out of the hook.** `stems_m8check` moves to `stems_ui_tick`; T8's label comes from `stems_lsrc` during a take. That also settles FLASH.md's two T8 rows (held mid-take, the label race) | ~8 instructions every frame, idle included | UI only: `master`, `master8`, the menu gates, `master_t8` | Small |
| 1.9 | **Bus kinds decided at the layout.** Entry points for stereo, mono and inputs, with MAIN and CUE as absolute addresses in `stems_farg`. The input page computed once a frame, not per input file | 6 to 10 per bus file | The `ffn`/`farg` units | Medium |
| 1.10 | **No gains queued while IDLE and stopped.** Queue only when not IDLE | ~590 instructions (~1.7 µs) on every stopped frame of any unit carrying STEM REC | A take armed less than two frames before play starts a frame later (the existing fallback). Start-edge gates, `mirror_idle` | Small |
| 1.11 | **Fewer counters.** Keep `stems_tfr` and `stems_zdone`, with a pokeable `stems_cap` for the cap. Drop `stems_frames` (always `stems_wr`), `stems_wr`, `stems_rd` and its delta update | 3 words, 2 to 5 instructions | Many gates poke `stems_wr`/`stems_rd`: cap, overflow, `stems_sweep.py`, the 24-byte dump. Minimal step: drop `stems_frames` | Medium to large |
| 1.12 | **One start-edge rule.** Drop `stems_staged`: stay ARMED while `stems_gqok` < 2, and latch the layout on the frame that stages. Removes 0.2 | 1 word, 4 instructions | The start edge is hardware-proven: verify_stems' Review Focus 1 | Small |
| 1.13 | **State dispatch.** `subq #ST_RECORDING / bgt / beq`, and the register save first, so no `d0` push around the first mark | About 6 | Low: the stop and finish takes | Small |
| 1.14 | **Small hoists.** `GQ_READ` once for probe and stage. The mirror's own 15-register save sits inside the hook's. `stems_emac_in`/`out` skipped when there's no track file | About 100 instructions (~0.3 µs) | Low (units call `stems_stage` alone, so pass the frame in a way they can set) | Small |
| 1.15 | **16-bit mono buses, two samples a long.** As `LE16PAIR` does | 8 uncached stores and ~32 instructions per such file | Low | Small |
| 1.16 | **After STEMS12:** remove the probe and the t1-t3 marks, or put them behind the debug-build symbol (FLASH.md "For later") | ~100 instructions, 3 timer reads | None | Small |
| 1.17 | **Macros for readability.** The hook's entry and exit sequence (written twice), the mirror's core-0 multiplies (`SQ23`, `MUL23`: four copies, the model in `stems_gain.py`), the trace seam's constants (`LV_SENT`, `BUS`, the half and the input page) | One place for the 18.5 arithmetic | None | Small |

Leftovers: dead labels `.Lh_stock` and `.Ll_rd`, and `.Lg_sel` beside
`.Lg_slot`. The hook's header says eight tracks where there can be fourteen
files. The `bus16` header sits above `stems_bus_src`. Local label prefixes
(`.Lt_`, `.Lq_`, `.Lp_`, `.Lc_`, `.Lb_`) are reused across routines.

**Don't:** unroll the two-sample loops (14 instructions a track for about
seven more instruction-cache lines a routine, ~80 ns a miss).

## 2. The writer and the card

| # | Change | What it buys (estimated) | Risk and gate | Size |
|---|---|---|---|---|
| 2.1 | **Writes in whole clusters.** While recording, write whole clusters (`CARD_SPC`), and round each ring to a cluster | About 25% fewer card commands at 24-bit stereo, ~50% for mono, and ~25% fewer `RAW_WRITE` calls. Inferred: that the file layer sends a command for every cluster a call touches, partial ones too (STEM_REC.md 20.2). Measure under the port first | Low to medium: each ring holds one cluster less; the `stems_zlead` seam. Combines with FLASH.md's "bigger writes when behind" | Small. **Applied** (4 Nov 2026, STEM_REC.md 20.11): writes end on a cluster while recording; the rings stay as they were |
| 2.2 | **One fix for the first-sector race, on the platform.** `stems_ata_first` (detour at `0x40014cfe`) and ATA WRITE GUARD (poke `0x40014cf2`, detour `0x40014d58`) fix the same stock race. With both in one image (octabam with STEM REC), STEM REC's code runs inside the guard's mask and returns through the guard's SR restore. That works only because it leaves `d3`, the guard's saved SR, alone (confirmed by reading both manifests). Either STEM REC requires the guard and drops its detour, or the guard takes STEM REC's reordering | One detour less, no hidden coupling | Neither form has run with a PIO card on hardware (Yves's card writes by DMA). `verify_ata_write`. The guard is Sam's | Small |
| 2.3 | **`stems_drain`, one pass.** It returns the sectors written; the task loops without sleeping while that's above 0, and `stems_finish` loops `drain(1)`. Today it repeats the task's per-pass duties (`stems_ui`, the hold seam), keyed on `d1 == CHUNK_FRAMES` | One loop owns the duties | Writer throughput is hardware-proven: overflow, `slow8`, wrap | Small |
| 2.4 | **One error rule.** `stems_fail(code)`: the first error wins, and "the card refused" (`stems_wfail`) follows from it. Today the last error wins, and five places test `stems_wfail` (which only `stems_zput` sets). Fixes 0.1 | One rule | The hook's OVERFLOW store against the writer's test-and-set, which must be masked | Small |
| 2.5 | **A record per file.** One pointer per file, with offsets as `ZR_*` already gives the hook, instead of seven parallel arrays (`stems_handle`, `fpos`, `rbase`, `rpos`, `rsize`, `ftab`, `fsmp`). Helpers for "the ring's base plus the writer's place" (three copies) and "44 + frames × bytes" (two). `stems_finish` loads the handle four times | About 32 `lea` and indexed-load pairs | Low | Medium |
| 2.6 | **Helpers for the logs.** A line macro for `stems_stats`' 13 sprintf lines and their hand-counted pops (`stems_st_cline` already does two). One small-file writer (open, two sectors, set length, close) for the log and the `.ot`. One fill routine for seven clear loops (not stock's memset at `0x40020984`, which writes a long past some lengths) | About 50 lines | None | Medium |
| 2.7 | **Names and paths.** One name table by file kind with `"-%s.wav"` (nine strings and a branch of `stems_make_file` go). Build `<set>/AUDIO/!STEMS` once, check its length once (today twice, at different limits), then append. One `stems_exists`. `stems_ensure_parents` cuts `stems_path` instead of copying `SET_PATH` again | Three copy loops, nine strings | The log's place was Yves's choice | Medium |
| 2.8 | **The `.ot` built once a take.** Rebuild only when a file's sample count differs | ~0.7 ms a take | Low | Small |
| 2.9 | **Folder lookups remembered across takes** (`/AUDIO/!STEMS`, `/BRAIN`, `/BRAIN/STEMS`), forgotten when the set or the card changes | One lookup less before the first write | Card swaps | Small |
| 2.10 | **The capacity from the real layout.** `stems_zlayout` derives it, instead of `ZC_SLACK`'s padded constant | One source of truth | The 32,768-layout unit | Small |
| 2.11 | **Derived twice.** Block align is the file table's bytes a frame shifted right by 4; the published bytes are computed in two routines. The layout's sum loop can fold into its build loop. `stems_tbytes` is read only by the units. `.Lt_drop` is byte for byte `.Lt_idle` | Fewer copies | Low | Small |

**Leave as is:** `stems_zrd`'s divide, `stems_zwrite`'s multiply,
`stems_st_write`'s divides, the sector-0 copy and the header fix-up. They
cost microseconds against card commands that take milliseconds.

## Where to start

1. 0.1, the confirmed bug: small, and it matches what README promises.
2. STEMS12's verdict. If the gain queue misses, 1.1 and 1.3 first;
   if it doesn't, 1.2's probe is the larger prize. 1.2 also matters to
   Bryan's USB OUT.
3. 2.1, measured under the port first.
4. 2.2, with Sam.
5. 1.10 and 1.12: small, and they remove 0.2.
