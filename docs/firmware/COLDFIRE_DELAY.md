# The stock DELAY: a ColdFire routine over SDRAM rings

OS 1.40C. The Echo Freeze DELAY (FX2 id `0x08`) does not run on the DSP.
Its DSP dispatch is a passthrough; the audio goes to the ColdFire in the
post-FX2 read-back (`DSP.md` section 6c), a per-frame routine at `0x400031a0`
runs all eight tracks over per-track rings in SDRAM, and the result comes
back to core 0 at `X:0x4400`. The DSP side of that ruling is `DSP.md`
"The stock DELAY" (reachability, the id-8 substitution on hardware).

## 1. The routine

|  |  |
|---|---|
| frame routine | `0x400031a0..0x4000385a` (`rts` at `0x40003858`; "to ~`0x40003900`" until then) |
| ring base | SDRAM `0x4F502C10` (cached alias `0x477...`, `PLACEMENT.md`) |
| ring size | 1,411,200 bytes per track = 176,400 × 8 = 4 s × stereo × 4 bytes; stride 1,411,328 (`0x400037aa`–`b6`) |
| 4-second cap | `if (samples > 176400) samples = 176400` |
| read head | `read_pos = write_pos − delay_samples × 8`, wrapping at the ring size |
| DMA | `0xfc045040/50/60/70`, count/control `0xfc04505e/7e` |
| tap processing | EMAC loop `0x40003664`; two cascaded first-order sections, coefficients per track via `0x80006180` |
| mix and feedback | EMAC loop `0x40003734`; four gains, each linearly ramped across the frame |

No fractional-delay interpolation: whole 8-byte frames, time changes as a
two-tap crossfade between this frame's and last frame's positions (TAPE
off snaps, TAPE on glides). No recursive feedback code: the ring's write
stream contains a scaled copy of its filtered read stream. Eight tracks
sustain 4-second delays because each has its own ring in CPU SDRAM.

## 2. The frame, the snapshots and the track loop objdump

Re-read with `scripts/disasm.sh emac` against Jannik Aßfalg's note (section 3):

- Entry `0x400031a0`: `lea -148(%sp)`, `movem.l d2-d7/a2-fp`, the EMAC
  state (MACSR, ACCEXT01/23, acc0-3, MASK) saved at `sp+116`, then
  `MACSR = 0xa0`. The whole routine runs inside that save/restore.
- `0x400031ca`: `d4 = [0x80004804]`, the control-snapshot selector, four
  values (`addq #1` at `0x4000382c` after the track loop, `moveq #3`
  mask). `0x400031d0`: the ping `[0x800000e0]` into `sp+44`.
- Per-snapshot bases from `d4`: setup `a2 = 0x80001b80 + 64·slot + 7`
  (`lsl #6`, `addal #0x80001b87`), byte 7 the FX2 id, compared with 8 at
  `0x40003234`; knobs `d3 = 0x80001a00 + 96·slot` (`lsl #7 − lsl #5`).
  `sp+108 = 0x80000eb4 + 8·ping` (+ track), compared with 7 at
  `0x4000323c`.
- Track loop tail `0x400037e0`–`0x40003822`: `sp+112` counts 0..7; per
  track `sp+72 += 12` (knobs), `sp+76 += 8` and `sp+92 += 8` (setup),
  `sp+80/84/100/104 += 68` (state records), `sp+96 += d5` (audio),
  `sp+108 += 1`. So the routine walks all eight tracks every frame, and
  section 1's open "whether tracks 5–8 share the function" is closed.

The frame slots a hook sees:

| `sp+` | holds |
|---|---|
| 44 | ping |
| 48 | ring write pointer (bytes) |
| 72 | six staged page-1 control halfwords, `0x80001a00 + 96·snapshot + 12·track` |
| 76, 92 | eight setup bytes, `0x80001b80 + 64·snapshot + 8·track`; byte 7 = FX2 id |
| 80, 84, 100, 104 | per-track state records, 68 bytes, from `0x80005f60` |
| 96 | the track's 16-sample stereo block, `0x80003190 + 1024·ping + 128·track` unconfirmed |
| 108 | `0x80000eb4 + 8·ping + track` |
| 112 | track 0..7 |
| 116 | the saved EMAC state |

Per-track state record `0x80005f60 + 68·track`; ring byte position at
`+0x3c` (`0x80005f9c + 68·track`), advancing 128 B per 16-sample stereo
frame (his harness).

## 3. The seam a replacement can take (Jannik Aßfalg / repeat98)

From his note beside Tape Echo (the effect runs on the ColdFire inside this routine,
in the stock delay's own ring for the track; the DSP side is a 5-word
passthrough). The practice half of the note is `MODULES.md` "Pricing a
ColdFire module".

```text
0x400031a0  complete eight-track frame routine
     ...    ring address calculation, DMA read and wait
     ...    prefetch of the next track
0x4000361a  replaceable per-track filter/mix seam
0x40003624  displaced stock filter/mix path
     ...
0x4000377a  common continuation into ring DMA commit and loop bookkeeping
```

 objdump: `0x4000361a` `moveal 92(%sp),%a5` / `movel 0x800000e8,%d0`,
then `0x40003624` `eoril #imm,%d0` (the scratch-buffer toggle; his hook
reads the immediate from `0x40003626` at run time) and `moveal
0x80006180,%a4` / `movem.l 20(%a4),...` (the per-track filter state).
Rejoin `0x4000377a`: `tst.l 112(%sp)`, a spin on `0xfc0450be` (DMA
status) and `0x800000e8` → `0xfc045080`: the ring DMA commit. Reset seam
`0x40002f44`: `lea -16(%sp)`, `movem.l d2-d5`, stock continuing at
`0x40002f4c` (his detour replays both).

Unconfirmed: Adopted on his complete-routine harness (the stock routine run from
`0x400031a0` over all eight tracks with a synchronous eDMA model, original
against patched image; audio, ring bytes, the 68-byte state records, ring
positions, both ping buffers and all four snapshots compared after every
frame):

- A hook that declines the custom path must replay the displaced loads
  exactly and leave every other integer and EMAC register as stock left
  it; a non-target id gets a byte-for-byte equivalent fallback.
- Omitting the `0x800000e8` toggle overwrites an in-flight DMA read for
  later tracks. `0x80006180` must advance by 68 per track.
- Ring samples are not held across callbacks. The rings are read through
  the uncached alias and DMA can replace history between frames; reusing
  a neighbouring sample within one frame, in a register, reloaded after a
  discontinuity, is the one safe form.
- The detour's own cost: 7,628 → 7,892 instructions per eight-track frame
  with every track on the stock path (+264, 3.5%).
- The eDMA model moves bytes synchronously: it proves addresses, lengths,
  ordering and resulting bytes; it cannot show arbitration, overlap,
  coherency or stalls.

## 4. Cost

Tape Echo's instruction counts per frame against stock DELAY's, and what
the meter cannot see: `modules/tapeecho/README.md` "CPU integration" and
`git show 666b6154:modules/tapeecho/VOICING.md`.

On a unit (Bryan T's CF METER takes, `ARCHITECTURE.md`
section 6): DELAY on T1, on T1–T4, and on T1 with TIME swept by hand adds
nothing measurable to the frame interrupt against FX2 NONE (237–271 µs
either way, seven FLEX voices). The routine is called from transfer state
5 of the level-6 eDMA chain (`jsr %pc@(0x400031a0)` at `0x40004b12`), so
its time either nests inside the measured span as a fixed per-frame
amount or falls outside it; the takes cannot tell cheap from fixed. An
image with the routine bypassed would.

## 5. Consequences for the bus

- The routine's input is the read-back after FX2 and its output re-enters
  on core 0, so it sits after every FX slot on every track. A bus send
  taps its slot, before the read-back: SEND substituted on id 8 on
  hardware gave "the reverb receives dry" (`DSP.md`). No slot sees the
  ColdFire delay's output.
- The rings are ColdFire SDRAM. The DSP's only link to them is the
  host-port DMA, 16-sample blocks each way once per frame: a DSP effect
  cannot use them for delay lines.
- A ColdFire effect prices in this routine's budget: BusVerb at ~18,000
  DSP cycles per frame and four-grain GRAIN at ~28,400 sit at or above the
  seven-instance freeze point, in the cheaper unit.
