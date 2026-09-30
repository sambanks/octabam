# RETURNS: bus returns independent of the host tracks

29 Sep 2026, branch `bottleservice-rec`. Stage A (the reverb return) ran on an
MKII as BSRET3; stage B (the delay return) passes under the port. Status markers as
`docs/firmware/CHIP.md`: ✅ measured (port or unit) · 🟡 inferred · ❓ open.

## What changes for the player

Today each engine prints its wet under its host's dry: T1 carries the delay,
T5 the reverb, and the host's LEVEL, mute, crossfader, cue and USB pair act
on the return as well as on the track's own sound. With RETURNS:

- **T1 and T5 are ordinary tracks.** The engines still run in their FX2
  slots and still hear the host's DEL/REV sends, but print nothing onto them.
- **T8's FX2 is RETURNS**: a control-only effect whose page-1 knobs are the
  return levels (stage A: VRB; stage B adds DLY). Page-1 knobs take stock
  scene locks, the crossfader, LFOs and CC, like any effect knob.
- **Where the returns go**: with MASTER TRACK on, into T8's input, so T8's
  FX1 (a master filter), its FX2 page and its fader process the whole mix,
  returns included; with MASTER TRACK off, into MAIN directly.
- **Without RETURNS on T8** (an unconverted project, or T8's FX2 changed),
  nothing changes: the engines print on their hosts as they do today.

## Measured facts it rests on

- ✅ MASTER TRACK is `MASTER_TRACK=` in `project.work`, RAM byte
  `0x80000034`, published to core 0 as bit 10 of T8's record word `$7e`
  (`X:0x407e` / `0x207e` by bank); `P:0x257` branches on it (port, 29 Sep).
- ✅ Master path `P:0x292-0x2d3`: T1-T7 are summed per sample with their
  mix gains (`Y:0x4a+20j+k`) plus the input pairs, raw (no `asl #2`), into
  T8's record at `X:$209+0x1f8`, 32 words L/R; T8's chain processes it later
  in the frame (`P:0x39f -> 0x41f` copy); MAIN is T8 x its gain, `asl #2`.
  The sum was recomputed exactly under the port.
- ✅ Plain path `P:0x25b-0x28f`: MAIN is ring words 2/3 of `X:$203`, stride
  8 per sample, after `asl #2`; CUE is words 0/1.
- ✅ Both paths fall into `P:0x2d5` (`move x:>$206,r0`, two words), which
  precedes the recorder packers (`jsr P:0x55a` x4) and the metronome mix.
- ✅ T8's FX2 is dispatched with `r7 = $6b00` on core 0 (port; unit, flash 7).
- ✅ BusVerb's print (`reverb_server.asm` "THE HOST PRINT"): per sample,
  `wet*2` after the limiter, `+ x:(r0)` dry, stored in place through r0.
  r4 is rebuilt by `lua` before every use in the sample loop and is free at
  the print; n4 is unused in the loop.
- ✅ Core-private `Y:0x0795-0x0FFF` is free on stock (hardware sweep,
  `CHIP.md` 3); no module references `Y:0x0A00` or above.

## Stage A design

### Private Y on core 0 (claimed, `Claims.reserved_private_y`)

| word | writer | reader | meaning |
|---|---|---|---|
| `0x0e00-0x0e1f` | BusVerb | BusVerb (normal) / hook (returns) | the print buffer: 16 x (L, R). A private X:$3e00 buffer (30 Sep 2026, `a0f10ca`) crackled and stopped the DSP on the unit beside the delay return: FAILURE_MODES.md |
| `0x0e20` | RETURNS | BusVerb | ALIVE: RETURNS ran on T8 last frame (set by RETURNS, cleared by BusVerb) |
| `0x0e21` | RETURNS | hook | VRB target, the knob as published |
| `0x0e22` | BusVerb | hook | FRESH: the buffer holds this frame's wet (set by BusVerb, cleared by the hook) |
| `0x0e23` | hook | hook | VRB gain, ramped |

One writer and one reader per flag, all on core 0, which runs its FX slots
and its mixdown in one sequence: no cross-core state in stage A. The
Sept 2026 T8 return failed partly on flags two stations could clear; here
only RETURNS sets ALIVE, only BusVerb clears it, only BusVerb sets FRESH and
only the hook clears it.

### RETURNS (new module, FX2, payload A)

Proc: audio untouched. If `r7 == $6b00` (T8's FX2 on core 0): store
`x:(r6+0)` to `0x0e21` and 1 to `0x0e20`. Anywhere else: nothing. On the FX2
chooser (since RIGPF7BP, 30 Sep 2026; hidden and placed by the host command
before), id 0x1b: Octakit refuses a chooser pick past 28. Init
writes nothing and preserves r1 (`verify_initregs`).

### BusVerb: print into the buffer

Per block, on its first call: read and clear ALIVE into the mode (y:$e24).
The print writes through r4, loaded from n4 each sample, into
`Y:0x0e00 + 2 x the frame offset`, and r0 advances by `lua (r0+2),r0`.

- Normal: the range is prefilled with the dry (one loop; a Tcc off one
  compare zeroes it instead in returns mode) and copied back after the
  loop, so the block ends as `dry + wet*2`, bit-identical.
- Returns: the range starts at zero, the block keeps its dry, the buffer
  ends as `wet*2`, and FRESH is set.

The dispatcher may split a block into two calls (`r0 = 2 x split` on the
second); both halves land in their own range of the one buffer.

### The hook (`DspHook` at `P:0x2d5`, payload A)

Replays `move x:>$206,r0`, saves what it uses, and if FRESH: clears it,
ramps the VRB gain toward its target, and adds `gain x buffer` either into
T8's record (`X:$209+0x1f8`, raw scale, when bit 10 of `x:(X:$207+$7e)` is
set) or into MAIN ring words 2/3 of `X:$203` (x4, saturating, otherwise).
The frame after BusVerb wrote it: about 2 blocks earlier than the dry's
forwarded path, inaudible on a reverb return 🟡.

The hook reads the reverb's buffer with `y:` and the delay's (in the shared
window, which aliases X and Y) with `x:`.

Gain law: the track mix gains (`Y:0x4a...`) differ between master and plain
mode ✅; the hook maps VRB onto the same law so VRB 100 sounds like a track
at LEVEL 100. Master mode is exactly `(L/128)^2` (✅ `0x17a180` at LEVEL 55);
plain mode is 0.5618 of that before the `x4` (✅ `0xd4ad0` at LEVEL 55, one
point only 🟡). `verify_returns` checks the glided gain lands on
`(knob/128)^2` exactly.

### Tools

- `ot_project.py master-track <project> on|off`: the `[SETTINGS]` line,
  byte-exact (CRLF kept; a text re-save gives PARSE ERROR).
- `ot_project.py host` for a remix carrying RETURNS: T8's FX2 = RETURNS in
  place of stock DELAY. RIG HOSTS likewise for a new part.

## Gates

- A port gate: a staged project with MASTER TRACK on and off, RETURNS on
  T8, a SEND REV on T2: T5's output carries no wet; the wet appears in T8's
  record (on) or MAIN (off) at the VRB gain; VRB 0 silences it; with
  RETURNS off T8 the old print is back.
- `verify_onebus`, `verify_twocore` and the bus bit-identity gates without
  RETURNS in the fixture: the normal path must stay bit-identical.
- `verify_dirtystate`, `verify_initregs`, `dsp_host -guard` on the claimed
  words.

## Stage B: the delay return

BusDelay runs on core 1; its wet reaches core 0's hook through the shared
window. Implemented 29 Sep 2026; under the port it passes `verify_returns`.

| word | writer | reader | meaning |
|---|---|---|---|
| `0x36200-0x362ff` | BusDelay (core 1) | mixhook (core 0) | 8 buffers x 16 x (L, R): the wet, every block, at BusDelay's write rotation |
| `0x36300-0x36307` | BusDelay | mixhook (clears) | per buffer, `$5a0000 | write offset` once written in returns mode |
| `0x36308` | RETURNS (core 0) | BusDelay (clears) | ALIVE_D, stamped every block RETURNS runs |
| `y:$e25` / `$e26` | RETURNS / mixhook | mixhook | DLY as published / its glided gain (core 0) |

- ✅ `0x36200-0x363ff` is written by nothing else: `--dsp-writes` over 500
  frames of a rig project on the stage A image, both cores (29 Sep 2026).
- BusDelay (`delay_server.asm`, spelled `bus+$200/$300/$308` and relocated
  by the build) reads ALIVE_D on the block's first call with the reverb's
  clear-on-read pattern (3 blocks of grace, raw $62) and latches the mode in
  raw $65. Every sample it stores `wet x WET` into the buffer (pointer
  parked in raw $66: no register survives a sample); in returns mode it
  skips the in-place print, so T1 keeps its dry. After the loop it stamps
  the buffer. Normal mode is bit-identical (`verify_onebus`, `verify_twocore`).
- The hook reads the rotation word before this frame's flip and takes the
  buffer three back (`+$50 & $70`, as the servers read), adds it only if its
  stamp matches, and clears the stamp. Arithmetic: 3-4 blocks after it was
  written with the ROTLATCH label exact or one behind, and never the buffer
  core 1 is writing (🟡: the flip's phase on the unit is unmeasured; a wrong
  phase shows as a missing return, not a torn one).
- The delay warms up dry for longer than the reverb (~frame 584 after load
  under the port, measured), so the gate compares from frame 650.
- RETURNS' code is 149 words and REVERB SERVER 2,064. With USB AUDIO IN CD
  in the rig, payload A's donor region has 5 words free (6,153 of 6,158).
  To fit, `verify_burn` builds without USB IN (`OCTABAM_NO_USB_IN`, read by
  the registry): it measures the engines' cycles, and USB IN's DSP half is
  a separate budget.

## Risks

- The mixdown is where the bus's hardest defects lived (the Sept return:
  a 15-minute wedge and a "degraded" return on the unit, both unexplained).
  Stage A keeps everything on one core and flags single-writer.
- Every instruction form must have a stock site in payload A (AGENTS.md).
- Cycles: the hook's `make cycles` blind spot, like the USB inject.
