# RETURNS: bus returns independent of the host tracks

Draft, 29 Sep 2026. Stage A (the reverb return) is being prototyped on branch
`bottleservice-rec`; nothing here has run on a unit. Status markers as
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
| `0x0e00-0x0e1f` | BusVerb | BusVerb (normal) / hook (returns) | the print buffer: 16 x (L, R) |
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
`x:(r6+0)` to `0x0e21` and 1 to `0x0e20`. Anywhere else: nothing. Hidden,
named (its page draws VRB), placed on T8 by the rig's host command. Init
writes nothing and preserves r1 (`verify_initregs`).

### BusVerb: print into the buffer

Per call, before the sample loop: read and clear ALIVE. The print writes
through r4 (loaded from n4 each sample) into `Y:0x0e00 + r0_start` instead
of in place, and r0 advances by an explicit `lua (r0+2),r0`.

- Normal (ALIVE was 0): the buffer range is prefilled with this call's dry
  (X -> Y copy) before the loop and copied back to the block after it, so
  the block ends as `dry + wet*2`, bit-identical to today.
- Returns (ALIVE was 1): the range is prefilled with zeros, the block is
  left alone (the host keeps its dry), the buffer ends as `wet*2`, and
  FRESH is set.

The dispatcher may split a block into two calls (`r0 = 2 x split` on the
second); both halves land in their own range of the one buffer.

### The hook (`DspHook` at `P:0x2d5`, payload A)

Replays `move x:>$206,r0`, saves what it uses, and if FRESH: clears it,
ramps the VRB gain toward its target, and adds `gain x buffer` either into
T8's record (`X:$209+0x1f8`, raw scale, when bit 10 of `x:(X:$207+$7e)` is
set) or into MAIN ring words 2/3 of `X:$203` (x4, saturating, otherwise).
The frame after BusVerb wrote it: about 2 blocks earlier than the dry's
forwarded path, inaudible on a reverb return 🟡.

Gain law: the track mix gains (`Y:0x4a...`) differ between master and plain
mode ✅; the hook maps VRB onto the same law so VRB 100 sounds like a track
at LEVEL 100. The two constants are measured under the port ❓.

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

## Stage B (the delay return), not designed yet

BusDelay runs on core 1; its stereo wet must reach core 0's hook through a
new rotating buffer in the shared window, with the XBUS rotation and its
race lessons. Separate image.

## Risks

- The mixdown is where the bus's hardest defects lived (the Sept return:
  a 15-minute wedge and a "degraded" return on the unit, both unexplained).
  Stage A keeps everything on one core and flags single-writer.
- Every instruction form must have a stock site in payload A (AGENTS.md).
- Cycles: the hook's `make cycles` blind spot, like the USB inject.
