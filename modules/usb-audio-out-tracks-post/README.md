# `usb-audio-out-tracks-post` — USB AUDIO OUT TRACKS POST

The unit as a USB audio input (UAC2, 44.1 kHz, 24-bit), sixteen channels:
track N's L/R on channels 2N−1/2N, **after that track's own MAIN gain** —
track LEVEL, mute, solo and XLV (the crossfader's scene level), with core
0's 16-sample ramp — and **without MAIN_LEVEL**. Full speed: the stereo sum
of those stems. Needs USB MIDI.

[USB AUDIO OUT TRACKS MAIN CUE](../usb-audio-out-tracks-main-cue/README.md)'s source,
`usbaudio.s` (markandrus/octemu, MIT), assembled with `USB_LAYOUT = 5`:
[USB AUDIO OUT TRACKS](../usb-audio-out-tracks/README.md)'s sixteen-channel
stream (same descriptors, packets and rate servo), with each track's block
multiplied by the gain core 0 gives it in the MAIN mix. It takes the same
hook sites as the other USB AUDIO OUT modules, so a remix carries one of
them; choose this one or USB AUDIO OUT TRACKS for pre-fader stems. The POST
layout is allmyfriendsaresynths's (@clickysteve).

## What a channel carries

For track t, sample n of a block:

    stem = floor(8 · g_t[n] · x_t[n] / 2^24)

- `x_t` is the track's post-FX, pre-fader block, the words USB AUDIO OUT
  TRACKS sends (the read-back arena: the voice, AMP envelope, AMP
  VOL/BAL/XVOL, FX1, FX2 and the stock DELAY mixed in place).
- `g_t` is core 0's MAIN gain for that track, computed on the ColdFire as
  payload A computes it (P:0xfa–0x165, P:0x203–0x237) with MAIN_LEVEL fixed
  at 64, where its factor is exactly 1 once the mixdown's `asl #2` is
  counted:

      sq = floor(w² / 2^7)                 w = the snapshot's MAIN word (LEVEL << 8, smoothed; 0 when muted or soloed out)
      T  = X:0x6c00[XLV >> 7]              the first quarter of payload A's sine: XLV's curve, sin(π/2 · XLV/128)
      G  = floor(sq · floor(T/4) / 2^23)   the target
      g  = core 0's ramp toward G: the last block's increment continues for min(split, last split)
           samples, holds for the rest of the split, then floor((G − g)/16) per sample to the block's end

So at the defaults (LEVEL 108, XLV unlocked) a stem is the track × 0.7119;
at LEVEL 127, × 0.9844 (the `(L/128)²` law, `docs/firmware/LEVEL_LAW.md`).

The stem is the track's own term of core 0's MAIN sum, before that sum's
one truncation. With MAIN_LEVEL at 64 the eight stems sum to MAIN within
0..7 LSB; at any other MAIN_LEVEL, MAIN is that sum times the MAIN_LEVEL
factor, which these channels leave out.

| control | in the stems? | how |
|---|---|---|
| sample playback, AMP envelope, AMP VOL, BAL, XVOL | yes | already in the pre-fader block |
| FX1, FX2, the stock DELAY | yes | already in the pre-fader block |
| scene locks / crossfader on page-1 parameters | yes | already in the pre-fader block |
| track LEVEL (knob, CC 46/7) | yes | the MAIN word: `(L/128)²`, the ColdFire's 1/16-per-block smoothing, core 0's ramp |
| mute (key, CC 49) | yes | the MAIN word is 0 from the next block; core 0's 16-sample ramp. FX tails are cut with the track, as on MAIN (the stock mute) |
| solo (CC 50) | yes | every other track's MAIN word is 0 |
| XLV (scene-only track level, crossfader) | yes | the XLV word through the sine curve; steps per fader event, core 0's ramp |
| PERSONALIZE "CUE MUTES TRK" | yes | a cued track's MAIN word is 0 when it is on |
| MUTE MODE (the `mute-modes` module) | follows it | whatever that module leaves in the MAIN word is what is applied |
| MAIN_LEVEL | no | the stems are the mix at MAIN_LEVEL 64 |
| CUE level, cue routing, CUE_LEVEL | no | the cue bus has its own gains |
| the headphone mix, the metronome, the inputs' DIR | no | not a track |

**MASTER TRACK on** (checked under the port and against the model; not
tested on a unit). Core 0 sums T1–T7 (and the inputs' DIR) into T8's input
instead of into MAIN, and MAIN is T8 alone. Then:

- **T1–T7** carry their contribution to the master bus: the track times its
  LEVEL/mute/solo/XLV gain, before the master track's effects. Core 0
  computes that sum's gains as `floor(sq · T / 2^23)` without the
  MAIN_LEVEL `mpy`, about 4 G; the stems use G from the plain-mode formula,
  so the two agree to within the gain's last 2 bits (the model, not a
  comparison with core 0's master bus, which is not read).
- **T8** carries the master bus after T8's effects, times T8's own gain:
  MAIN without MAIN_LEVEL. Under the port, equal to MAIN sample for sample
  at MAIN_LEVEL 64.
- The T1–T7 stems lead T8's by two blocks (32 samples): T8's block is the
  master bus core 0 made two frames earlier (the offset that makes CUE
  lead MAIN with MASTER TRACK on, `usb-audio-out-tracks-main-cue` README).
  The stream does not correct it.
- Each track after the master track's effects exists nowhere in the unit:
  the master effects run once, on the sum.

## How it works

- **The gains.** Every block frame_isr builds a gain snapshot
  (`0x40004db8`, called from `0x4000d0de`) into a four-entry ring at
  `0x80005460`, 0x80 bytes an entry; per track eight bytes: cue, MAIN, XLV,
  split. The transfer machine sends core 0 the entry three blocks old with
  the read-back block it forwards; the producer reads that block one frame
  later. So **the block this producer reads was mixed with the snapshot
  built four frames earlier**, and by the time the producer runs frame_isr
  has rebuilt that ring entry. `post_frame` keeps its own four-slot history
  (`post_hist`) and reads the slot for this block before overwriting it
  with this frame's snapshot (`0x80003c10`).
- **The ramp state** (`post_state`: core 0's `X:0x3dd` state, the MAIN
  half) advances every block, stream or not (the closed-stream path runs
  `post_frame` without the per-sample table), so the first block a host
  receives is already core 0's and the stems are exact from the start.
- **The multiply.** The EMAC in fractional mode: one `macl` of the word
  (low byte cleared, as the DSP's hi/lo join drops it) by `g << 10`, so the
  accumulator holds `floor(g · x / 2^13)` and its top 24 bits are the stem.
  `G` is an EMAC `macl` too (`sq << 8` by `floor(T/4) << 8`). The
  interrupted context's MACSR, ACC0 and ACCEXT01 are saved the way
  frame_isr saves them and restored before the hook returns (the hook runs
  after frame_isr's own restore at `0x4000d968`).
- **The XLV curve** is payload A's `X:0x6c00..0x6cff`, extracted from the
  user's own stock image when the remix is built (`manifest.py`,
  `xlv_table`, which refuses the build unless the 256 words are the first
  quarter of a sine). No stock bytes are in the repo.
- **At high speed** the stereo sum is not made (it is only sent at full
  speed).

## Measured

Under the port, 5 Oct 2026:

- **Against core 0's own MAIN** (`tools/verify/verify_usb_post.py`, the
  module's gate): the tone project (`tools/harness/usb_sig_project.py`,
  every track its own tone, staged as `usb_align.py` stages it) loaded and
  playing, both DSP cores live, 365 blocks (2,710 track-blocks with signal)
  while T1's LEVEL moves (CC 46), T2 mutes and unmutes, T3 solos, T4's XLV
  is locked and the crossfader moves to A, B and the middle, T6's split
  word goes 7, 3, 12 and 0 under a running LEVEL ramp with a mute and an
  unmute inside it, and T5 mutes while T7's LEVEL moves:
  - MAIN − Σ stems over 11,680 samples: 0..6 LSB, never outside 0..7.
  - Every stem and every block's ramp state equal
    `tools/harness/usb_post_model.py`'s, exactly, from the read-back block
    the producer read (reassembled from the logged writes).
  - Pairing the gains with the snapshot one frame earlier or later instead
    breaks the MAIN sum on ~5,200 samples: the run exercises the pairing.
  - MASTER TRACK on (102 blocks, T8 LEVEL, mute, unmute): MAIN − T8's stem
    = 0 on every one of 3,264 samples.
  The gate skips without a source project (`OT_PROJECT` or
  `~/.octabam_project`).
- **The stream** (`verify_usb`, `make check REMIX=usb-out-tracks-post`):
  EP 0x83 isochronous, 768 bytes, 16 channels; 704/768-byte packets, none
  empty after the first ten; 0 overruns, 0 underruns; with the read-back
  arena re-poked before every poll with an amplitude per source, channels
  1–16 carry tracks 1–8 L/R, each only its own, at the model's boot gain
  (G = 0x16c78e, LEVEL 108); full speed: 1 ms packets of 44/45 8-byte frames.
- **A stock quirk, reproduced:** core 0's ramp rounds its increment down,
  so after a mute the gain can settle a few LSB below zero (a stem of
  ±4 LSB, about −126 dBFS); MAIN carries the same.
- **Every other layout unchanged:** every remix carrying a USB module,
  built cold before and after, gives the same image and the same build
  report (the remixes that fail to build on the base tree fail identically).

## On the unit

On allmyfriendsaresynths's (@clickysteve) MKII. erreye's MK1 takes with
this layout into Ableton Live are in the
[USB AUDIO OUT TRACKS MAIN CUE README](../usb-audio-out-tracks-main-cue/README.md),
*A MK1 into Ableton Live*.

**This module** (P3, `usb-out-tracks-post` built from this module's source
on main `faa32663`; the platform under it has changed since, so today's
build is not that binary): a smoke test, 5 Oct 2026. The unit booted and
ran normally; the host saw sixteen channels, each track on its own stereo
pair; each track's LEVEL, mute and unmute, solo, and the scene/crossfader
level followed in its stem; no instability or audio fault was heard. A
listening test, not a null: the null is the diagnostic build below. Not
run on a unit: MASTER TRACK, a long soak.

**Latency, tracks against MAIN** (7 Oct 2026). The stems come from the
same read-back block, in the same frame, as USB AUDIO OUT TRACKS MAIN
CUE's track channels, so that layout's track-to-MAIN offset is this
module's. `usb-out-tracks-main-cue` built from main `6f9e5bc9` (BUILD L1),
a click on T1 every 2 s, nothing else playing, MASTER TRACK off, T1 not
cued; three 20 s takes (`tools/rec`), the USB cable unplugged and
replugged between them, each through `tools/hw/usb_offset.py --ref 1 --ch
17`:

| take | clicks | MAIN L against T1 L | corr |
|---|---|---|---|
| 1 | 10 | 0 samples on every click (xcorr and onset) | 1.000 |
| 2 | 10 | 0 samples on every click | 1.000 |
| 3 | 10 | 0 samples on every click | 1.000 |

MAIN R against T1 R (channels 18 / 2) is 0 on every click too; only T1
and MAIN carried signal, MAIN at 0.61 of T1's peak. The port's 0
(`verify_usb_align`) holds on the unit.

**CPU, POST against OUT TRACKS while streaming** (7 Oct 2026):
`cfmeter-post` (BUILD C2) and `cfmeter-tracks` (BUILD C1), the same
selection but for the USB layout, built from this branch on `6f9e5bc9`;
each loaded fresh with the same project (T1-T7 playing looping tones, T8
FX2 = CF METER at a fixed LEVEL, unmuted); three 8 s takes on each over
USB, `tools/harness/cfmeter.py --lr 14,15`. The frame interrupt's mean
duration alternates between consecutive 2 s cycles on a playing unit;
"balanced" is the two phases' average:

| image | take | low phase | high phase | balanced | TUE / ROE |
|---|---|---|---|---|---|
| OUT TRACKS | 1 | 230.0 µs | 246.0 µs | 238.0 µs | 0 / 0 |
| | 2 | 230.2 | 246.0 | 238.1 | 0 / 0 |
| | 3 | 230.6 | 246.4 | 238.5 | 0 / 0 |
| OUT TRACKS POST | 1 | 233.7 | 248.7 | 241.2 | 0 / 0 |
| | 2 | 233.5 | 248.2 | 240.8 | 0 / 0 |
| | 3 | 233.3 | 248.4 | 240.9 | 0 / 0 |

POST minus OUT TRACKS: **+2.8 µs** a frame (balanced means 241.0 − 238.2;
+3.2 on the low phase, +2.3 on the high), 0.8% of the 362.8 µs frame;
frame period 362.8 µs on every take. A first POST take with the
sequencer stopped (T1-T7 silent) read 123 µs and is not counted.

The difference is smaller than the port's count predicts: on these two
images the hook runs 1,737 more instructions a block (median 4,503 against
2,766, below), and 2.8 µs is ~730 core cycles at 264 MHz, about 0.4 cycles
an instruction, where the unit's other frame-interrupt work measures 1.1 to
4.4 (`docs/firmware/ARCHITECTURE.md`). CF METER's exit stamp is the
epilogue at `0x4000d9a6`, where the USB hook rejoins, so the hook is inside
the span it times. Why the unit is this much cheaper is not found.

No host (USB cable out, CUE into an interface): not run.

**The gain engine** and the per-sample multiply this module uses ran on a
MKII (5 Oct 2026, allmyfriendsaresynths (@clickysteve)) in a 20-channel
diagnostic build, not part of this module:
this layout's sixteen stems plus MAIN and CUE in one stream, so the stems
could be nulled against core 0's own MAIN. A 196 s take at 44.1 kHz / 24
bits while LEVEL, mutes, solo and the crossfader moved:

- 99.995% of the 17.3 M samples had MAIN − Σ stems inside 0..7 LSB.
- At the ~16,700 places a track's level changed by 4× or more within 128
  samples (the mutes, LEVEL and crossfader moves, and drum hits), the
  residual stayed within −1..9 LSB everywhere outside the stock mix's
  overload bursts: no gain/block misalignment.
- 775 samples (0.0045%) were one LSB outside the bound (−1, 8 or 9; about
  −138 dBFS); where every stem was exactly 0, MAIN was exactly 0. Their
  cause is not found.
- The large residuals all fell where the eight tracks summed to full scale
  or beyond: MAIN saturates (stock), the stems do not.

## Cost

Instructions in the producer hook per block, counted under the port
(`--watch-pc` on the hook's entry and its rejoin `0x4000d9a6`, the steady
state of 1,300+ blocks), a bench host streaming at high speed (packet
building included) and with no host:

| layout | streaming (high speed) | no host |
|---|---|---|
| OUT MAIN CUE | 827 | 17 |
| OUT TRACKS | 2,639 | 17 |
| OUT TRACKS MAIN CUE | 3,438 | 17 |
| **OUT TRACKS POST** | **4,278** (+1,639 on OUT TRACKS) | **447** |

On `cfmeter-post` and `cfmeter-tracks` (CF METER and SYNTH MACHINE beside
the USB module) the same count gives 4,503 and 2,766 (medians; minimums
4,278 and 2,631).

**Time, measured on a unit while streaming: +2.8 µs a frame over OUT
TRACKS** (0.8% of the frame; *On the unit*, above). This replaces the
earlier estimate of about 17 µs, which scaled the instruction count by
Bryan T's ~10 ns an instruction for OUT TRACKS MAIN CUE's read-back work;
the unit runs POST's extra instructions far faster than that, and faster
than the port's count suggests (not explained). **With no host, not
measured** (the 447 instructions a block that run whether or not a host
is connected); the same scaling's ~4.5 µs is not carried over, since it
overstated the streaming cost about sixfold.

Memory: the `usbaudio` unit grows by 428 B of code (2,434 → 2,862) and 1,920 B of
data (the four-block history, the ramp state, the per-block gain table and
the 1 KB XLV table), in the platform reserve.

## Open

- MASTER TRACK and the no-host CPU cost have not been measured on a unit.
- The streaming cost on the unit (+2.8 µs for ~1,740 more instructions a
  block under the port) means about 0.4 core cycles an instruction, below
  the 1.1 to 4.4 measured for the unit's other frame-interrupt work; not
  explained.
- The split word (`0x8000485a + 8t`, a sample offset in the block) was
  exercised under the port by poking it; what the sequencer writes there
  on a unit was not observed (the diagnostic take nulled, but which splits
  it carried is not known).
- A MAIN or XLV word above 0x7fff (nothing in the firmware writes one) is
  wrapped here where core 0 would read outside its table.
- `srcjump` is not counted in this layout.

## Gates

- `verify_usb` (`make check REMIX=usb-out-tracks-post`).
- `tools/verify/verify_usb_post.py` (the manifest's gate; needs a source
  project, `OT_PROJECT` or `~/.octabam_project`).
