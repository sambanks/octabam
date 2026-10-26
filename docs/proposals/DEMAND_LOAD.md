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

**Collisions.** A block is held by whoever has it first. A stock reverb (PLATE, DARK, SPRING) and a demand effect never
share one; neither is moved for the other.

| route | effect X chosen, block's FX2 is a reverb | reverb chosen on the FX2 slot of a loaded X's block |
|---|---|---|
| FX1 / FX2 chooser | refused, toast `NEEDS Tn FX2 FREE` (an FX2 choice on that very track goes through: it replaces the reverb) | refused, toast `Tn HOLDS <effect>` |
| any other route (song load, pattern, Part, paste) | X is not loaded and stays dry; toast `NEEDS Tn FX2 FREE` at the next page key | X stays loaded, the reverb runs dry; toast `Tn HOLDS <effect>` at the next page key |

Both toasts are shown once per collision. When the holder goes away (X unused and withdrawn, or the reverb replaced) the other
takes the block: the pump loads X, and a dry reverb resumes (it runs the stock init first if its init never ran).

- **DLPUMP** (ColdFire, `modules/dlpump`), called from LOAD METER's entry code (`lm_in`, weak symbol) every frame interrupt.
  Idle: on ping-0 frames it compares the ids on the 16 live FX slots with the effects loaded and arms one message: a load when
  an effect is used, not loaded, and its block is not under a reverb; a withdrawal when it is loaded and no slot uses it for 10 s in a row (a project load leaves every id at its default for about 4 s, measured on a unit; the `GRACE` build setting, 2 S for the port gates), or at once when a stock reverb is on the FX2 slot of its block.
  Sending: 100 halfwords per ping-0 frame to core B's `X:0x2901..`, then the doorbell `0xa55a` to `X:0x2900` two frames later.
  A load is sent twice, 30 idle calls apart, if the effect is still loaded then. The table of effects, their blocks and the toast
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
| slot offset `0x1000` | the effects: SPECTRUM `0x31000`, MODULATION `0x35000`, CHARACTER `0x39000`, TRANSIENT `0x3d000`, not uploaded |

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
- A repeat send that is refused leaves the effect unbound: the copier clears BOUND before it copies and publishes nothing for a bad sum, and the ColdFire cannot see the counters to send again. Not seen with the ping-0 gate. The unit did freeze once during the first rounds (13:27); it was on `DLPROBEJ3`, the build with the stale-byte bug, and the cause was not found.

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
- Silent input: a knob that lengthens a delay line only when signal runs through it is not exercised.

## Open

- The unit: the stock extents with signal on T8, the audible dropout while an effect loads (about 25 ms), and a reverb meeting a loaded effect's block.
- Core A's stall when sent to, and the mask at the frames that lose their chunk.
- The wording of the toasts and how long the deferred ones wait for a page key.
- A dry instance that had run its init (state 3) resuming is not covered by a gate: `dsp_host` cannot change the published span between blocks.
- The check is blind to a block lost in transit on the unit beyond what the sum catches: the sum is 24 bits.
- Audio at a load: the stub is dry until the code arrives, about 70 frames (25 ms) for MODULATION.
- Load cost on the ColdFire frame interrupt: LOAD METER figures.
