# Demand loading of window effects

25-26 Oct 2026. ✅ measured (port, or unit where stated), 🟡 inferred, ⬜ not looked at. Nothing here has run on a unit.
Addresses are `P:` / `X:` / `Y:` DSP words, or ColdFire virtual addresses where they start `0x4`.

## What it does

Every stock effect stays and works as stock. SPECTRUM, CHARACTER, MODULATION and TRANSIENT are in the effect list and are
copied into the DSP's shared window while a track uses them, and withdrawn when no track does. Nothing of stock is removed,
replaced or shrunk. The window is stock's buffer memory, so the code goes only where no running stock effect writes.

`remixes/octabam` is built this way. `remixes/test/dlspike` is the same with one effect, for the gates.

## Constraints

| fact | status |
|---|---|
| P is 8K per core and full with the 13 stock DSP effects; P above `0x1fff` is absent | ✅ unit (`modules/pextprobe`) |
| Code written into the window ran from both cores; the window `0x30000..0x3ffff` is one memory, P, X and Y alias | ✅ unit |
| FX2 instance *k* of a core has its buffer at `Y:0x4000`, `Y:0x8000`, then two window slots: core A (tracks 7, 8) `0x30000`, `0x34000`; core B (tracks 3, 4) `0x38000`, `0x3c000` | ✅ (`DSP.md` section 7) |
| Highest word each stock effect writes above its slot base: FLANGER `0x7ff`, SPRING REV `0xfff`, CHORUS `0xbfd`, COMB `0xbff`, SPATIALIZER `0xa5f`, PLATE REV `0x37ff`, DARK REV `0x3da2` | ✅ port, default knobs (`stock.SLOT_EXTENT`); other settings ⬜ |
| So offset `0x1000` or higher in a slot is clear of every stock effect except PLATE REV and DARK REV (SPRING REV stops on the line); offset `0x3da3` or higher is clear of all | derived |
| Payload B's boot zero loop clears `Y:0x37f00..0x3ffff` after the pre-boot upload, so an uploaded record there is gone at boot | ✅ port (both cores faulted at boot with resident code at `0x3bda3`) |
| The dispatcher calls `INIT[id]` when an id changes and `PROCESS[id]` every frame through `jsr (r2)`; `proc` is entered with `a` = 0 or 1; `init` keeps `r1`; `x:$213` at `init` is the address of the slot's allocator entry | ✅ |
| The ColdFire writes DSP X by host command `$08` (`HOST+4` = `0x88`), reaching `X:0..0x3fff` only, 16 data bits a word | ✅ port |
| Payload B's frame loop stores `0x3fff` or `0x5fff` into the host handlers' address masks every frame (`P:0x70`, `0x72`, from the bank word); a chunk sent on a frame whose ping word (`0x800000e0`) is 1 is lost, one sent at ping 0 arrives whole | ✅ port: 0 of 3,126 halfwords differ at ping 0, 1,178 differ sending every frame. Why the lost chunks do not appear at `X:0x4901` is ⬜ |
| Sending to core A at the frame interrupt's entry stops the stock ping words alternating: core A's chain stalls. HC polling and a settle loop did not change it | ✅ port; cause ⬜ |
| `X:0x2840..0x3fff` was written by nothing in one project at two fill seeds | 🟡 |
| The live FX ids are `0x80000ec4[8]` (FX1) and `0x80000ecc[8]` (FX2), tracks 1-8 | ✅ |
| The FX1 and FX2 choosers' select handlers are `0x400526e4` and `0x40052474`; the "same effect" test is `0x4005272a` / `0x400524ba` | ✅ |

## Design

Core B loads for both cores. The window is one memory, so code copied by B's hook is resident for A's tracks, and the pump
never writes to core A.

**Homes and collisions.** A demand effect has one or more homes (`Remix.window_homes` beside its address in `Remix.window`):
the blocks of the window it fits in, the code assembled once per home. At most one demand effect holds a block. A stock reverb
reaches an effect's code in a home when the code starts at or below the highest word the reverb writes (`stock.SLOT_EXTENT`:
PLATE `0x37ff`, SPRING `0xfff`, DARK `0x3da2`, counted from the block's base); each home's record carries that mask, bit i for
`REVERBS[i]`. In octabam every effect's code sits at the top of its block (offset `0x3820`; TRANSIENT's at `0x3e00` in the third and
fourth), so only DARK REV reaches it, and not TRANSIENT's there.

The pump loads an effect into the first of its homes whose block holds no other demand effect and whose track's FX2 is not a
reverb that reaches the code. When such a reverb arrives on the block of a loaded effect that a track uses, and another home is
free, the pump withdraws the effect and loads it into that home (a short dry gap, no toast). A reverb on the FX2 of an
unused loaded effect's block takes the block at once.

| situation | what happens |
|---|---|
| the chooser picks effect X, and a home is free | goes through |
| the chooser picks X, no home is free | refused, toast `EVICT Tn FX2 1ST` (Tn: its first home's track). An FX2 choice on the track of one of its homes goes through: it replaces the reverb |
| the chooser picks a reverb on a loaded, used X's block, and X has another free home | goes through; X moves |
| the same, and X has nowhere to move | refused, toast `EVICT <effect> 1ST` |
| any other route (song load, pattern, Part, paste): X used, no home free | X is not loaded and stays dry; toast `EVICT Tn FX2 1ST` at the next page key |
| any other route: a reverb reaches a loaded X that cannot move | X stays loaded, the reverb runs dry; toast `EVICT <effect> 1ST` at the next page key |

Both toasts are shown once per collision. When the holder goes away the other takes the block: the pump loads X, and a dry reverb
resumes (it runs the stock init first if its init never ran).

- **DLPUMP** (ColdFire, `modules/dlpump`), called from LOAD METER's entry code (`lm_in`, weak symbol) every frame interrupt.
  Idle: on ping-0 frames it compares the ids on the 16 live FX slots with the effects loaded and arms one message: a load when
  an effect has been used, not loaded, and its block not under a reverb for 200 idle calls in a row (about 145 ms: a project load writes the ids over a stretch of frames, and a reverb that arrives within it keeps the block; `DEBOUNCE` in `pump.s`, port-gated by `verify_dlload` `race`, not measured on a unit); a withdrawal when it is loaded and no slot uses it for 10 s in a row (a project load leaves every id at its default for about 4 s, measured on a unit; the `GRACE` build setting, 2 S for the port gates), or at once when a stock reverb is on the FX2 slot of its block.
  Sending: 100 halfwords per ping-0 frame to core B's `X:0x2901..`, then the doorbell `0xa55a` to `X:0x2900` two frames later.
  A load is sent three times, 30 idle calls apart, if the effect is still loaded each time. The table of effects, their blocks and the toast
  strings is generated per remix (`remix.inc`, `Linked.include`) from `out/dsp/demand_records.json`; the unit reserves 2,600 code
  words an effect on every link. The FX1 and FX2 choosers' "same effect" test is detoured (the refusals above, with the popup
  `FUN_4005a2b8`, which runs in the key handler). The idle loop cannot call the popup, so it leaves its message in `dl_pend`,
  and a detour at the UI task's page-key handler (`FUN_4005578c`) shows it at the next press.
- **DLCOPY** (DSP, `modules/dlcopy/dlcopy.asm`), a hook on payload B at `P:0x76` (the frame head, after the masks are set), in
  the window. When the doorbell is set it clears the effect's BOUND word, copies the block to the window while summing the code
  words, compares the sum with the one staged after the code, and only then writes the effect's init and proc and BOUND last. A
  block whose sum is wrong is not published; the second send replaces it. A message with N = 0 only clears BOUND and the span.
- **The stub** (`modules/dlcopy/dlstub.asm`), assembled once by the build with a trampoline per effect. The effect's id
  dispatches to it. BOUND clear: the audio passes through (the stock null stub's loop). BOUND set: each instance runs the real
  init once, with `r0 n0 r6 r7 n7 m0 m1` kept, then jumps to the real proc.
- **The reverb guard** (`modules/dlcopy/dlwrap.asm`), one body in the window with a trampoline pair per reverb and payload (the
  stock entries differ). At init it reads the buffer base through `x:$213` and runs the stock init and proc only while
  `[base, base + extent)` misses the span of every loaded effect; otherwise the instance passes the audio through. The check is
  repeated every frame. A dry instance runs again as soon as the range is clear: after an init that never ran it runs the stock
  init from the proc (with `x:$213` pointed at the cell that holds its base), then the stock proc.

Layout (words are `X:` or `P:` as in the window, which aliases):

| where | what |
|---|---|
| `x:$33da3 + 8 k` (k = 0..3, in the clear gap) | effect k's entry: +0 BOUND (`$b0a5ed`), +1 real init, +2 real proc, +3 first window word, +4 the word after |
| `x:$2900` | staging: doorbell, k, destination offset, N, init offset, proc offset, then 2 N halfwords (code word as high 16 bits, then low 8), then the sum of the code words modulo 2^24 in the same form. Addresses are offsets into the window |
| `x:$3f00..$3f4c` | the stub's per-instance flags and saved registers; `x:$3f50..$3fea` the guard's, and the copier's saved `b` |
| `P:0x33dc3..0x33e34` | DLCOPY; the stub follows at `window_loader` (`0x33e40`), then the guard's trampolines for payload A and B, then its body (to `0x33fd2` in octabam) |
| `P:0x37da3..0x37eff` | LOAD METER's DSP half (A and B) |
| top of each slot | the effects, not uploaded: SPECTRUM `0x33820` (slot of T7), CHARACTER `0x37820` (T8), MODULATION `0x3b820` (T3), TRANSIENT `0x3fe00` (T4). The loader and LOAD METER sit above `0x33da3` and `0x37da3` in the first two slots, so those hold at most 1,411 words from `0x3820` (SPECTRUM, the larger of the two placed there, is 1,399); the third and fourth hold 2,016 |

The clear gaps are `0x33da3..0x33fff` (605 words) and `0x37da3..0x37eff` (349 words); resident code above `0x37f00` is wiped at
boot. octabam uses 559 and 340.

Builder: `Remix.window_demand` (keys), `Remix.window_guard` (stock keys), `Remix.window_loader` (address). The demand effects'
records are left out of payload A's upload and written to `out/dsp/demand_records.json`; the guards' addresses to
`out/dsp/guard_records.json`. The boot zero loop count ignores demand addresses.

## Checked

| gate | what | where |
|---|---|---|
| `verify_dlstub` | for each effect: the stub unbound equals the null stub, bound equals the effect's own render (0 of 6,400 samples differ), a wrong magic, a missing doorbell or a wrong block sum stays dry; DLCOPY binds a staged block and the stub runs it; a withdraw message makes it dry again | `dsp_host`, test/dlspike and octabam |
| `verify_dlwrap` | for each reverb, payload and published span: the guard equals the stock render and Y writes where the buffer is clear, passes the audio through and writes nothing where it covers the code; a dry instance whose init never ran runs the stock init when the range is clear and then equals the stock render | `dsp_host`, same |
| `verify_dlload` | with live ids poked: the four effects load (entry and every code word, read from both cores), one is withdrawn while the others stay, none loads unused, a reverb that arrives on a loaded effect's block leaves it loaded, none loads over a reverb's block, the choosers pick an effect that can load and refuse one that cannot, and refuse a reverb on the block of a loaded effect that a track uses (not on an unused one, which is withdrawn), each with a toast (counted at the popup call), the deferred toasts appear at the next page key and not when nothing collides, the loaded proc is reached on core B and on core A (`--dsp-pcwatch`) | port, test/dlspike and octabam |

`dsp_host` keeps P and Y apart, so the guard is shown to decide correctly, not to prevent an overwrite on the chip.

## Measured on a unit (26 Oct 2026, MKII, images DLPROBEJ1..J7, project MXDLPR01 / MXDLPR02)

- DLPUMP runs on the unit: the pump's counters (`tools/hw/dl_state.py`, USB request `0xc0/0x57` block 3) show the frame interrupt calling it 2,756 times a second, the ping word alternating 0 and 1 as in the port, and the loads, chunks and doorbells it armed and sent.
- The host write lands in core B's `X:0x2900..`: DLPROBE on T1 read `X:$2902` = `0x00d000` (TRANSIENT's destination offset).
- The byte above a host word's 16 bits is stale on the unit: the doorbell read `0x40a55a`. The port leaves it 0. The first image compared the doorbell as a full word and never took a block (received 0, doorbell non-zero for ~77,000 frames). The copier now masks the doorbell and header words (`verify_dlstub`, "stale high byte").
- With the mask: all four effects BOUND, every block's sum matched (refused 0), published equal to received.
- The code runs, from the per-slot costs of LOAD METER (`tools/hw/load_meter.py`; a dry slot costs 89..147 counts): CHARACTER on core A FX1 5,147; SPECTRUM on core B FX1 4,062; TRANSIENT on core A FX2 3,616; MODULATION on core B FX1 323 (module defaults). So code core B copied is executed by core A.
- SPECTRUM and CHARACTER on an FX2 slot cost a dry slot's 116..119 counts: they are `fx1_only` and render dry there. `octabam` had no FX1 list, so it offered them on FX2 only; it lists them on FX1 now.
- A project load leaves every id at its default for about 3.8 s (polled over USB every 0.25 s: ids reset at 36.2 s, back at 40.05 s). With a 2 s grace the pump withdrew all four effects at 38.3 s and loaded them again at 40.05 s; the grace is 10 s.
- Sending on every frame (`DLPANYJ9`, `test/dl-probe-any`, the same project): the copier refused blocks for their sum on the unit (MODULATION received 4, refused 3, published 1; SPECTRUM received 2, refused 2, published 0; TRANSIENT received 2, refused 1, published 1; CHARACTER received nothing) and ran no bad copy. The ping-0 rule holds on the unit as in the port; with it, no block was refused in the rounds on `DLPROBEJ5` and `J7` (about 16 blocks over several loads).
- A repeat send that is refused leaves the effect unbound: the copier clears BOUND before it copies and publishes nothing for a bad sum, and the ColdFire cannot see the counters to send again. Not seen with the ping-0 gate. The pump sends each load a third time since 26 Oct 2026: a refusal of the second send is followed by a good third; a refusal of the last send still leaves the effect unbound (dry). Each repeat holds the pump's idle comparison for 30 ping-0 frames, about 22 ms at 1,378 ping-0 frames a second (inferred from the frame rate, not measured). The unit did freeze once during the first rounds (13:27); it was on `DLPROBEJ3`, the build with the stale-byte bug, and the cause was not found.

- The collision toasts on the unit (27 Oct 2026, images T1 to T4, projects `MXTST_A`, `MXTST_B`): the firmware popup (`FUN_4005a2b8`) draws one line of about 23 characters, centred, and clips what does not fit at both edges. A newline in the text is dropped, not drawn as a break (`BUFFER SPACE IN USE` + newline + `BY MODULATION` read `ER SPACE IN USEBY MODUL`). Image T1's strings all read `T4` because the table's second loop reused the last effect's track; the gate now compares each string with its effect's block track and chooser name. `EVICT T8 FX2 FIRST` (18 characters) showed whole; `EVICT MODULATION FIRST` (22) ran slightly off the screen. Both now end in `1ST` (`EVICT MODULATION 1ST` is 20). The duration was 48 ticks (0.8 s) and read as too short; it is 120 (2 s) from image T5.
- `EVICT T8 FX2 FIRST` showed on the AMP page after a page key (text now `EVICT T8 FX2 1ST`); which of the two projects was loaded for that photo was not recorded.

## Stock reverb extents on a unit (26 Oct 2026, MKII, image `test/ext-probe` X1, projects MXEXT_{PL,DK,SP}_{MN,MX})

`modules/extprobe`: fills `X:0x34000..0x37da2` (T8 FX2's block) with `0xA5A5A5`, then counts the words that differ. T8 held the reverb with silent input and LEVEL 0; knobs all 0 (MN) or all 127 (MX); 8 s USB capture of T1 after each project load.

| reverb | knobs | highest differing offset | differing words in the last pass | `SLOT_EXTENT` |
|---|---|---|---|---|
| PLATE REV | 0 | 0x37ff | 12265 | 0x37ff |
| PLATE REV | 127 | 0x37ff | 12265 | 0x37ff |
| DARK REV | 0 | 0x3da2 | 13199 | 0x3da2 |
| DARK REV | 127 | 0x3da2 | 13199 | 0x3da2 |
| SPRING REV | 0 | 0xfff | 3502 | 0xfff |
| SPRING REV | 127 | 0xfff | 3502 | 0xfff |
| FLANGER | 0 and 127 | 0x7ff | 2048 | 0x7ff |
| CHORUS | 0 and 127 | 0xbfd | 3068 | 0xbfd |
| SPATIALIZER | 0 and 127 | 0xa5f | 2656 | 0xa5f |
| COMB FILTER | 0 and 127 | 0xbff | 3072 | 0xbff |

- Each reverb's bucket counts are the same at both knob settings.
- 0x3da2 is the last word the probe scans (LOAD METER's code starts at 0x37da3), so DARK REV's figure is a lower bound.
- The section after this table gives the same effects with signal on T8.

With signal on T8 (26 Oct 2026, projects `MXSG4_*`: T8 a FLEX slot playing a 31.7 s band-limited noise loop, started by MIDI Start and a note 43 on channel 8; knobs 127):

| effect | highest differing offset | differing words | silent input |
|---|---|---|---|
| PLATE REV | 0x37ff | 12265 | 0x37ff, 12265 |
| DARK REV | 0x3da2 (the scan limit) | 13199 | 0x3da2, 13199 |
| SPRING REV | 0xfff | 3502 | 0xfff, 3502 |
| FLANGER | 0x7ff | 2048 | 0x7ff, 2048 |
| CHORUS | 0xbfd | 3068 | 0xbfd, 3068 |
| SPATIALIZER | 0xa67 | 2664 | 0xa5f, 2656 |
| COMB FILTER | 0xbff | 3072 | 0xbff, 3072 |

- SPATIALIZER wrote 8 words past its silent-input extent. A run on an earlier project, whose sample slot had no trim record, read 0xa79; the figure depends on the signal.
- Every figure is below 0x1000, where the demand loader places effect code. SPATIALIZER's 0xa67 is 0x599 words below it.
- One capture per effect at knobs 127; knobs 0 with signal were not measured.

## Homes on a unit (28 Oct 2026, MKII, image `octabam` H1, projects `MXHOME_A`, `B`, `C`)

MODULATION on T1's FX1; T3 and T4's FX2 are the only slots that matter (its two homes are the T3 and T4 blocks). Pump state read with `tools/hw/dl_state.py` (word 11: bit 2 the T3 block, bit 3 the T4 block), the effect's cost from LOAD METER (4,535 counts a slot when loaded, a dry slot 76 to 147).

| case | result |
|---|---|
| T3 and T4 on DELAY | loaded into the T3 block (blocks holding code `4`); 1 load armed, 3 sends, T1 4,535 counts |
| then DARK REV picked on T3's FX2 | accepted, no toast; moved to the T4 block (`4` to `8`), 2 loads and 1 withdrawal armed, 7 doorbells; T1 4,535 counts |
| then DARK REV picked on T4's FX2 | refused, T4's FX2 stayed DELAY; toast `EVICT MODULATION 1ST`, whole inside the popup |
| `MXHOME_B` (DARK REV on T3), power-cycled | loaded straight into the T4 block (`8`), 1 load armed, 0 withdrawals, T1 4,535 counts |
| `MXHOME_C` (DARK REV on T3 and T4) loaded over a loaded MODULATION | stays loaded, toast `EVICT MODULATION 1ST` at the next page key (the effect cannot move) |
| `MXHOME_C`, power-cycled | nothing loaded (all counters 0, blocks `0`), T1 dry (147 counts); toast `EVICT T3 FX2 1ST` at the AMP key |

Not measured: the dry gap while an effect moves and whether it is audible; whether the DARK REV that arrives runs correctly (it is guarded, so it should pass the audio through until the code is gone); and whether the toast at a page key appears on keys other than AMP.

DSP 1's peak since reset read 99.8 % with an effect loaded (also 91.7 % and 99.8 % on cores 0 and 1 in an earlier round with four effects loaded, 26 Oct 2026) and 43.1 % when nothing had loaded. LOAD METER cannot reset the peak, so which frame made it is not measured: the load is the common factor, and the copy of a whole block in one frame hook (DLCOPY, up to 2,600 words) is the candidate.

## Open

- OPEN, hardware: a move from T4's block freezes the DSP frame loop (`FAILURE_MODES.md`, "DARK REV picked on T4's FX2 ..."). `octabam` still has `window_homes`. A poll caught DSP 1 at 99.8 % in a single frame at the copy of a send (15.544 s, 28 Oct 2026): copying a block in one frame takes core B close to a frame.
- The unit: the audible dropout while an effect loads (about 25 ms), and a reverb meeting a loaded effect's block.
- Core A's stall when sent to, and the mask at the frames that lose their chunk.
- How long the deferred toasts wait for a page key; whether 2 s (120 ticks) is long enough to read.
- A dry instance that had run its init (state 3) resuming is not covered by a gate: `dsp_host` cannot change the published span between blocks.
- The check is blind to a block lost in transit on the unit beyond what the sum catches: the sum is 24 bits.
- Audio at a load: the stub is dry until the code arrives, about 70 frames (25 ms) for MODULATION.
- Load cost on the ColdFire frame interrupt: LOAD METER figures.
