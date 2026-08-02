# Two-track freeze — state of the investigation

**Symptom.** The reverb works on one track and sounds right. The moment it is
enabled on a second track the machine freezes, sequencer stuck on step one,
regardless of knob positions and regardless of whether the second track is
playing.

**Not solved.** Sixteen builds, zero correct hypotheses. Everything below is
either measured on hardware or read out of the dispatcher listing.

## The one build that survives two tracks

`dsp/stageprobe.asm` — never freezes on two tracks. It escalates every ~3 s:

| stage | what runs |
|---|---|
| 0 | `rts`, nothing at all |
| 1 | recover base from the stash, write 4 r7 slots |
| 2 | load and save the state block at base+0x3800 |
| 3 | read all four delay lines every sample |
| 4 | write all four delay lines every sample |

Stage 4 is 8 Y accesses a sample per instance and it survives. Build up from
this, not down from the reverb — every attempt to subtract from a working
reverb broke something else.

## Best remaining lead: Y traffic with TWO instances

|  | Y/sample | across two tracks | two tracks |
|---|---|---|---|
| stageprobe | 8 | 16 | survives |
| v50 | 18 | 36 | freezes |

`dsp/yburn.asm` sustained 66 Y accesses a sample with **no break at all**, but
that was one instance. Two-instance Y traffic is the one axis never measured,
and it is the difference between the survivor and every failure.

## READY TO FLASH: `dsp/stageprobe2.asm` / `OCTATRACK_STAGES2.bin`

Built up from the survivor, one axis every ~3 s. Y traffic is in it, but it is
not first: two *structural* things v50 does and stageprobe never does at all are
cheaper to test, so they go ahead of the ramp.

| stage | adds | Y/sample | instr/sample |
|---|---|---|---|
| 0 | stageprobe's stage 4, verbatim | 8 | 79 |
| 1 | **AUDIO** — read/write x:(r0), walk r0 per frame | 8 | 95 |
| 2 | **PARAMS** — the eight x:(r6+n) reads v50 does | 8 | 95 |
| 3 | Y to 16 | 16 | 109 |
| 4 | Y to 24 | 24 | 121 |
| 5 | Y to 36 (twice v50's) | 36 | 137 |
| 6 | 80 instructions a sample of pure arithmetic | 36 | 223 |

Stage 1 is the one the old handoff never listed: **r0 was eliminated for the Y
buffer, never for the audio buffer.** Both instances are handed r0 = x:0x20e,
which is 0 in steady state — the same pointer.

Stage 6 closes the cycles axis *for two instances*; cycleburn only ever measured
one. 223 a sample is 446 across the pair, still under the ~806 it measured.

**Two readouts, so the stage is not timed blind.** From stage 1 the track goes
MONO, and from stage 1 it drops **6 dB per stage** (stage 2 half, stage 3 a
quarter … stage 6 −30 dB). Count the drops: the level you last heard is the
stage it died in. This matters because the counter advances once per *proc
call* — if the dispatcher makes both the control and the audio call, escalation
is ~1.5 s a stage, not 3 s. Trust the drops, not the clock.

Unlike stageprobe, the counter is initialised once against a sentinel in
r7+$82, so the escalation starts from a known point instead of from whatever
garbage the slot held. init cannot do it — the dispatcher re-invokes init most
blocks and the counter would never leave stage 0.

**Run it on one track first** and let it pass 21 s, to prove the escalation is
harmless. Then enable both tracks in QUICK SUCCESSION — each instance counts its
own blocks, so the two escalations run offset by however long you take.

A freeze inside the first three seconds means the *baseline* broke, not that a
null effect is fatal — stageprobe already proved a null effect is not.

Emulator, `-inst 2 -guard`, all seven stages: guard clean, and the only stray
writes are the two intended base stashes at Y:0x862 / Y:0x864 — byte-identical
to what the known-good stageprobe produces.

## Eliminated, with the evidence

| ruled out | how |
|---|---|
| base delivery, the init stash | `dsp/instprobe.asm`: r7 = 0x6200/0x6500, bases 0x4000/0x8000, distinct and valid. The probe itself runs on two tracks. |
| r7 state blocks | same, plus the dispatcher advances x:0x20a three times a track |
| buffer extent | `dsp/ownprobe.asm`: every word of the 0x4000 allocation still holds that instance's own signature a block later, at every offset, both tracks |
| Y bandwidth (one instance) | `dsp/yburn.asm`: no break at 66 accesses a sample |
| cycles | v40 and v41 are both 135 instr/sample; one freezes, one does not |
| parameters reaching an address | v38: taps as compile-time constants, still froze |
| r7 slot region | v39: scratch moved into DARK REV's own $1a..$4x, still froze |
| the A mode flag | v44 honours it; still froze |
| **modulo addressing** | v50 has none anywhere, every M register linear, **still froze** |

## Dispatcher ABI, read from payload A

* `P:0x372` resets x:0x418, x:0x20a=0x6000, x:0x213=0x255, falls into the track
  loop at `P:0x385`, four iterations (x:0x418 steps 0x20 to 0x80), exits 0x53e.
  Four tracks per payload, two payloads, eight tracks.
* Per track: x:0x20a advances 0x100 three times (0x4ae, 0x4e4, 0x51e), x:0x213
  advances 1 twice (0x4d8, 0x526). Reproduces the measured r7 and bases exactly.
* `x:0x415 + t*0x20` is a track's PENDING config, `x:0x416 + t*0x20` its CURRENT.
  FX1 id at `+$1b`, FX2 id at `+$1c`, as value<<8.
* `+$1e` bits 8..11 are an effect-change SPLIT POINT, not a block size.
  x:0x20c = split, x:0x20d = 16 - split, x:0x20e = split*2.
* **Both proc calls are audio.** A block is 16 frames and it is split: the
  CURRENT effect gets [0, split) at r0=0 with a=0, the PENDING effect gets
  [split, 16) at r0=split*2 with a=1. A crossfade across an effect change. In
  steady state split is 0, the outgoing call is skipped, and the effect gets the
  whole block at r0=0.
* FX2 is handed `r6 = x:0x208 + 12`; FX1 gets +6.
* init is re-invoked whenever a slot's effect id differs from the previous
  slot's, which is most blocks — this is why "init runs more often than once".

## Harness

`tools/dsp_host/dsp_host.cpp`:

* `-inst N` — N instances with correct per-instance r7, base and audio
* `-dispatch N` — **runs the host's own dispatcher** rather than imitating it.
  Configures N tracks with the effect on FX2 and executes `P:0x372` onward.
  `-split N` models the effect-change transition. Stock DARK REV completes at
  one and two tracks, so a negative from it means something.
* `-guard [words]` — shadows Y:0x0000..0xBFFF and loaded P from before the first
  init; separates a stray write from one landing on a loaded module
* `-dirty SEED` — fill Y with garbage first; hardware does not hand out zeroed
  buffers
* It does **not** reproduce the freeze, at either instance count, steady state or
  transition. Time is the thing it cannot model.

Three things about it that cost half a session to rediscover:

* **`-dispatch N` never completes** once the context is real. It hangs at any
  block count, and it hangs identically for `stageprobe`, which is the build that
  survives on hardware — so a hang there says nothing about the effect. Use
  `-inst N`, which is what the guard section of `DSP.md` documents anyway.
* **`instructions/sample` and `-trace` cannot see inside a `do` loop.** The
  emulator's `do_exec` runs the whole loop within a single `execInterpreter`
  step, so the harness counts a 15-frame sample loop as one instruction and the
  trace jumps straight from the `do` to the epilogue. A reported "6.8
  instructions/sample" is an artifact, **not** an effect that is idling — do not
  read it as one. The guard is unaffected: it still sees every in-loop write.
* **`-proc` is per source file.** `build_reverb.py` prints the address; a stale
  one silently runs whatever bytes are at the old offset and reports a plausible
  number. Copy it from the build output every time.

Feeding it: `python3 tools/dsp_modmap.py --dumpmem A <out.mem>` reads the
hardcoded stock image, so for a patched build call `dsp_modmap.dumpmem()`
directly against `out/mainos_reverb.bin`.

## Standing rules for the engine, learned by freezing the machine

* two instructions between writing r5 and using it — and they must be **data
  moves**, never M-register writes (an M load interlocks with its address
  register; this froze one track in v47)
* no M-register write inside the sample loop
* a modulo offset larger than the buffer is undefined: silent, not an error
* absolute Y scratch must sit at 0x800 or above — payload B loads modules to
  Y:0x7a4 where payload A stops at 0x794 (this was the v30/v31 hang)
* X:0x213 is only valid during init; reading it in process gives whatever the
  last init left (this was the v33 hang)
* check the generated assembly and the assembler's exit status, not the
  generator. `build_reverb.py | grep` masks a failed assemble and the emulator
  will then happily "verify" a stale image.

## Builds worth keeping

| file | what it is |
|---|---|
| `dsp/reverb46.asm` | computed tank, modulo pre-delay. **Works on track 1**, freezes on 2. The reference good build. |
| `dsp/reverb50.asm` | v46 with the pre-delay removed. No modulo anywhere. Freezes on 2 — the result that killed the modulo theory. |
| `dsp/stageprobe.asm` | the two-track survivor. Start here. |
| `dsp/stageprobe2.asm` | built up from it: audio, params, a Y ramp to 36, then cycles. **The one to flash next.** |
| `dsp/instprobe.asm` `dsp/ownprobe.asm` `dsp/yburn.asm` | the measurement probes, all safe to run |

`RV_DROP=` drops stages subtractively (`pre,diff,mod,size,lines`);
`RV_TANK_ADDR=modulo|computed`; `RV_LINE_LEN=` shrinks the lines.
