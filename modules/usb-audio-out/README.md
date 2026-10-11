# `usb-audio-out` — USB AUDIO OUT

The unit as a USB audio input (UAC2, 44.1 kHz, 24-bit), in one of five
layouts chosen by the module's LAYOUT setting. LAYOUT is a build-time
setting (`docs/proposals/BRAIN.md`): a remix pins it, for example
`settings={("octabam.usb-audio-out", "LAYOUT"): Pin("MASTER")}`. Needs USB
MIDI: the audio function is added to its composite device.

| LAYOUT | `USB_LAYOUT` | high speed | full speed |
|---|---|---|---|
| TRACKS MAIN CUE (the default) | 0 | 20 channels: tracks 1–16, MAIN, CUE | the tracks' stereo sum |
| TRACKS | 1 | 16 channels: the tracks | the tracks' stereo sum |
| MASTER | 2 | 2 channels: track 8's L/R | track 8's L/R |
| MAIN CUE | 3 | 4 channels: MAIN, CUE | MAIN |
| MAIN | 4 | 2 channels: MAIN | MAIN |

Until 6 Oct 2026 each layout was a module of its own (USB AUDIO OUT TRACKS
MAIN CUE, OUT TRACKS, OUT MASTER, OUT MAIN CUE, OUT MAIN); each remix's
image is byte-identical to the one it built with those modules. The
sections from here to *Layouts* describe TRACKS MAIN CUE, the twenty
channels; *Layouts* has the other four.

| USB speed | channels | content |
|---|---|---|
| high | 1–16 | track N's L/R on 2N−1/2N, post-FX, pre-fader |
| high | 17–18 | MAIN L/R |
| high | 19–20 | CUE L/R |
| full | 1–2 | the stereo sum of the eight tracks |

Channels 1–16 are taken before track LEVEL, the crossfader, MAIN volume
and the master effects. MAIN and CUE are the words sent to the DACs, so
they include all of those.

Based on markandrus's proof of concept
([octemu](https://github.com/markandrus/octemu) `custom/usb-audio.py` +
`custom/coldfire/usb-audio.s` at `6a9ff68`, MIT): the shims, producer,
packet builder, rate servo and UAC2 replies are his. MAIN/CUE on 17–20 are
Bryan T's (25 Sep 2026). The clock SET CUR handling (*UAC2 hosts that set the
clock*, below) is allmyfriendsaresynths's (@clickysteve), and the same change
is proposed to octemu, whose `audio_ctrl_shim` this one still is.

## Measured

Under the port, `verify_usb` (in `make check REMIX=usb-out-tracks-main-cue`) runs with no card and
silent tracks. It checks:

- EP `0x83` is isochronous, 960 bytes, bInterval 2.
- AS_GENERAL has 20 channels; FORMAT_TYPE_I has subslot 4 and 24 bits.
- A second open with the first poll held back 600 frames: `anchor` within
  that gap and `lastfill` within `AUD_TARGET` ± `AUD_TARGET`/2 (`AUD_TARGET`
  is 64 since 28 Sep 2026, 512 before); over the next 400 polls `minfill`
  stays at or above `AUD_TARGET`/2 with no underrun.
- Taps: with the read-back arena and MAIN/CUE re-poked before every poll
  with words that name their source, side and frame, channel N carries
  only its own source (tracks 1–8 L/R, MAIN L/R, CUE L/R), each seen.
- Full speed after re-enumeration: 1 ms packets of 44/45 8-byte frames.
- 880/960-byte packets at the 250 µs cadence, none empty after the first
  ten.
- Every subslot's low byte is zero, with 0 underruns and 0 overruns.
- After alt 0, every poll is empty.
- After a bus reset with the stream open and no alt 0 from the host,
  GET_INTERFACE(4) answers 0 and every poll is empty (`verify_usb`, port
  only; before `audio_reset_shim` it answered 1 and the stream went on).

A build with `MAIN_CUE_BASE` pointed at a frame- and channel-coded pattern
streamed 8,709 frames: every channel 17–20 subslot held the expected word
in order, and channels 1–16 were untouched.

The USBSIG tone project (`tools/harness/usb_sig_project.py`) on a card
under the port:

- **High speed.** All sixteen track channels carry their tone at the
  expected frequency, and 95.2–99.8% of samples have non-zero low 8 bits.
- **Full speed.** 360-byte packets at bInterval 1: the left sum carries
  every left tone, the right sum every right tone.

Overruns under the port follow the bench host's skipped polls, not the
device. The port logs them as `iso poll(s) with no IN waiting`.

The port cannot see the producer's timing against the eDMA's bank swap:
the emulator runs the frame interrupt and the eDMA in lock-step.

### MAIN/CUE against the tracks

The producer reads channels 1–16 from the read-back arena's previous bank
and 17–20 from the mixdown buffer's current pull. Measured under the port
(`tools/harness/usb_align.py`, 28 Sep 2026: the tone project on a staged
card, the producer's ring dumped at the end of the run, each tone's phase in
its track channel against MAIN): MAIN lagged the tracks by 16 samples, one
block, on every tone that reached MAIN (T8 both sides 15.95 / 16.03, T6
16.02 / 15.96, T3 15.91 / 16.09, T1 R 15.72; residues modulo periods from
42 to 126 samples, so 16 is the only lag under 882 that fits). Bryan T heard
MAIN lag on his unit (25 Sep 2026), the same direction. Since 28 Sep the
producer writes MAIN/CUE into the ring slot `MAIN_CUE_LAG_BLOCKS` = 1 block
behind the tracks' slot (the consumer runs `AUD_TARGET` = 64 frames behind (512 until 28 Sep
2026), which is more than one 16-frame block, so the slot is
unread), and `verify_usb_align` reads 0 under the port. On a unit the lag is 0:
a click on T1, three twenty-channel `tools/rec` takes (the USB cable
replugged between them) through `tools/hw/usb_offset.py take.wav --ref 1
--ch 17`, 0 samples on all 30 clicks, MAIN R likewise (allmyfriendsaresynths's
MKII, 7 Oct 2026, built from main `6f9e5bc9`;
[TRACKS POST](#tracks-post), *On the unit*).

## On the unit

**24-bit, 16 channels (image 69, Sam's MKII, 25 Sep 2026).** macOS lists a
16-channel 44.1 kHz input. Two takes with `tools/rec`, with the counters
read before and after each:

| take | project | length | tones | samples with non-zero low 8 of 24 bits | underruns / overruns / reprimes | events after 0.76 s |
|---|---|---|---|---|---|---|
| 1 | USBSIG | 60 s | all 16 at their frequency, −27.0 dBFS | 97.1–100% per channel | 0 / 0 / 0 | 0 |
| 2 | USBLOAD (locks every step, 200 BPM) | 120 s | all 16, −19.3 dBFS | 97.1–100% | 0 / 0 / 0 | 0 |

`lastn` 11 and `lastfill` 512–576 after each take (`AUD_TARGET` was 512 on
this image; 64 since 28 Sep 2026).

**20 channels (`usb-out-tracks-main-cue` image 90, Bryan T's MKII, 25 Sep 2026).**
Channels 17/18 carried MAIN and 19/20 CUE: an uncued track was on MAIN
and a cued track on CUE.

**16-bit, octemu's format (image 64, Sam's MKII, 25 Sep 2026).** Four
USBSIG takes and one USBLOAD take, 9.6 minutes in total. Every channel
carried its track's tone, and there were no discontinuities after the
first 1.6 s of any take. Underruns and overruns stayed at 0, and
`bankdup` did not move. Takes 4 and 5 ran with 7,170 and 7,950 USB-MIDI
messages a second coming in (125 s and 185 s), with no stall and no
change in the stream. octemu's own image (image 65, `USBAUDIO.BIN` on
the card root) enumerated as the MIDI composite only; its payload never
installed. So there was no A/B against his build.

### CUE against MAIN with MASTER TRACK on

With MASTER TRACK on, CUE led MAIN by 32 samples (two blocks); with it off
they are sample-aligned. Measured on Bryan T's MKII (29 Sep 2026: a
transient on a track sent to both, recorded over USB in Logic; master off
0, master on CUE 43976 vs MAIN 44008). The cause is the mixdown, not USB:
payload A tests bit 10 of `x:(X:$207+$7e)` at `P:0x257` and on the master
path (`P:0x292`) builds the cue bus from slots 0-6 of this frame's blocks
but MAIN from slot 7 alone, track 8's output of the mix it was sent two
frames earlier. The ColdFire sets that bit from the MASTER TRACK byte
`0x80000034` (the frame record builder, `0x4000498c`). The read-back's two
packs (`P:0x2df` MAIN, `P:0x2e2` the cue bus) read the same ring half and
samples, so the offset is already in the words.

The producer writes CUE `CUE_MASTER_LAG_BLOCKS` = 2 blocks ahead of MAIN's
slot while `0x80000034` is nonzero, and in MAIN's slot otherwise (channels
19/20 here, 3/4 in OUT MAIN CUE). After it, on the same unit, CUE and MAIN
land on the same sample with the master on and with it off. With the
master on, CUE keeps its alignment with MAIN and leaves the tracks' by 32
samples; MAIN itself sits 32 samples behind the tracks, which
`MAIN_CUE_LAG_BLOCKS` does not cover. No gate covers the master-on case:
`usb_align.py` stages the tone project with `MASTER_TRACK=0`, as
`verify_set` does ([tools/emu/README.md](../../tools/emu/README.md)). With
the master off the producer's words are unchanged and `verify_usb_align`
reads 0. Toggling the master leaves up to 32 frames of stale CUE in the
ring once.

**What the layout costs the ColdFire (Bryan T's MKII, 4 Oct 2026,
`docs/firmware/ARCHITECTURE.md` "ColdFire time per frame on a unit").**
Against OUT MAIN CUE in an otherwise identical image (IN ABCD, USB MIDI,
USB CROSSBAR, the stock effects), fresh-loaded FLEX projects, frame
interrupt mean per frame:

| | this layout, cable out | this layout, streaming | OUT MAIN CUE, streaming |
|---|---|---|---|
| no voices | 106.5 µs | 120.5 µs | 93.8 µs |
| T1 playing | 121.1 µs | 144.8 µs | 110.3 µs |
| T1–T7 playing | 220.1 µs | 245.5 µs | 195.3 µs |
| per voice | 16.5 µs | 16.8 µs | 14.2 µs |

The frame is 362.8 µs: ~27 µs more than MAIN CUE with nothing playing,
~50 µs with seven voices (about three voices of headroom), most of it
paid with no host connected. Each voice also costs ~2.5 µs more under this
layout; cache pressure from the 320 read-back words per block is the
candidate, not measured.

### A MK1 into Ableton Live (erreye, 5–7 Oct 2026)

erreye's Octatrack MK1, an M1 Mac mini, Live 12.4, a Behringer UMC404HD at
44.1 kHz as the output interface. The image is their `felipe` remix with
USB AUDIO OUT TRACKS POST (this source, layout 5), built from main
`faa32663` + #625 with `AUD_TARGET` raised locally from 64 to 256 (which
also needs the `moveq` in `audio_cushion_zero` made a `movel`).

- With a 2 m cable straight into the Mac: 0 transaction errors on EP 0x83,
  0 underruns, 0 overruns, 0 `bankdup`, fill 238–271 at a target of 256.
  A 240 s `tools/rec` take of all sixteen channels has no discontinuity.
- **Live with the unit as input and another interface as output** puts a
  dropped or repeated buffer into the recording about every 1–2 minutes:
  in a 170 s take of T7 and T8, every jump sits on a multiple of Live's
  128-sample buffer, on both tracks at once (8 outliers on buffer
  boundaries against 0.4 by chance), with the device counters clean, no
  USB errors and no CoreAudio overload. A `tools/rec` take overlapping it
  in time (one device, one clock) is clean. 🟡 Inferred: Live reconciles
  the two devices' clocks by a whole buffer. Workaround: Live's output on
  "No Device" and monitoring on the unit.
- **An aggregate device** (the UMC as clock, drift correction on the
  unit) does not start: CoreAudio logs 12 failed starts of the unit in
  about a second (`Initialize failed`, `_StartIO(): Start failed ...
  error 35`), and the unit froze later (`docs/contributing/FAILURE_MODES.md`,
  "Two SET_INTERFACE requests 40 ms apart"). The unit as the aggregate's
  clock has not been tried.
- `AUD_TARGET` 256 adds 192 frames (about 4.4 ms) over 64. erreye raised
  it for glitches on 2 Oct (through a hub) that they now attribute to the
  cable, the hub and Live's clock slips; a take at 64 is to come.

### UAC2 hosts that set the clock

The clock is fixed at 44.1 kHz and declares its frequency control read-only,
but a UAC2 host may still SET it to the rate it has just read. The Elektron
Outbox 8 does, right after GET RANGE and GET CUR of the clock, and its audio
setup stopped there: the request (SET CUR of CS_SAM_FREQ_CONTROL, a 4-byte
data stage) fell to the stock "unknown request" tail, which stalls only EP0
IN, and the stock EP0 stack has no control OUT data stage. Under the port's
bench the data stage is never accepted and the host times out. macOS does not
send the request to a read-only clock.

`audio_ctrl_shim` now takes that SET: it primes the stock EP0 OUT dTD for the
data stage, waits for it (bounded; `audio_isr_shim` finishes a slower host),
acknowledges 44100 and STALLs the status stage for any other rate. The rate
never changes and no other rate is offered.

On the unit: with the SET acknowledged, an Octatrack MKII on an Outbox 8
completes audio setup and streams. That was tested before the rate check was
added (the build acknowledged any 4-byte SET CUR); the Outbox asks for 44100,
which the check passes. Rejecting another rate is measured under the port
only (`verify_usb`).

## Open

- **A burst of reordered samples 0.5–1.5 s after a host opens the
  stream**, then in order for good; no frames are lost. At 24 bits it is
  on the right channel of every pair only. It was absent on one take in
  five. Whether it is the device's queue at stream start or the host's
  stream start is not known. `docs/contributing/FAILURE_MODES.md` has the
  entry.
- **Two SET_INTERFACE requests 40 ms apart freeze the unit** (alt 1, then
  alt 0, whose status stage never completes): erreye's MK1, from a buffer
  size change in Live; not reproduced under the port.
  `docs/contributing/FAILURE_MODES.md` has the entry.
- Not measured: Windows and Linux hosts; USB controller load from the
  250 µs packet rate beyond the takes above. The rejection of a SET CUR to
  an unoffered rate on a unit (the port only).
- The first-poll anchor on a unit: `anchor` over `usb_counters.py` after
  an open (expected about 460 on macOS), and the two rings' `lastfill` sum
  with USB AUDIO IN beside it (expected about 896, was about 1,355).
- `minfill`/`maxfill` on a unit under a busy project and DISK MODE churn:
  the host poll jitter the OUT ring absorbs, which is the floor for a
  lower `AUD_TARGET`.
- The gated producer (5 Oct 2026) on a unit: the 13–25 µs of frame
  interrupt the always-on producer cost with the cable out (*On the unit*
  above, Bryan T) should be gone with nothing streaming, and the stream
  start should show no underruns on macOS (the anchor lands 460 frames
  after alt 1). Port only so far: `verify_usb` and `verify_usb_align`.
  While streaming the cost stands; a producer that copies once into the
  packet buffers instead of ring then packet is the lever there. The voice
  path is memory-bound, so the 320 read-back words count more than the
  2,710 instructions.

## Gates

- `verify_usb` (`make check REMIX=usb-out-tracks-main-cue`): the checks under *Measured*,
  and SET CUR of the sample frequency: 44100 acknowledged, 48000 a status-stage STALL,
  EP0 answering after each.
- `verify_usb` also resets the bus with the stream open: GET_INTERFACE(4) answers 0, the polls are empty, and SET_INTERFACE alt 1 brings the stream back.
- `tools/verify/verify_usb_align.py` (the manifest's gate): MAIN/CUE against the tracks.

## Layouts

The layout is a `.set` in the `remix.inc` the `usbaudio` unit writes
(`layout_inc` in the manifest). Every `USB_LAYOUT = 0` path is the source as
it was before the layouts (27 Sep 2026). The four below take the same hook
sites; the producer detour's note in the build report names the layout.

### TRACKS

The unit as a USB audio input (UAC2, 44.1 kHz, 24-bit), sixteen channels:
track N's L/R on channels 2N−1/2N, post-FX, pre-fader. MAIN and CUE are
left out. Full speed: the stereo sum of the eight tracks. Needs USB MIDI.

USB AUDIO OUT TRACKS MAIN CUE's source,
`usbaudio.s` (markandrus/octemu, MIT), assembled with `USB_LAYOUT = 1`:
the producer skips the MAIN/CUE reads and writes a 64-byte slot per frame;
packets are 11/12 frames, at most 768 bytes, every 250 µs. Everything else
(the shims, the rate servo, the counters, the descriptors' shape) is that
module's. It takes the same hook sites, so a remix carries one of the three
audio modules.

#### Measured

Under the port, `verify_usb` with `REMIX=usb-out-tracks` (27 Sep 2026):

- EP `0x83` isochronous, 768 bytes, bInterval 2; AS_GENERAL 16 channels.
- 704/768-byte packets, none empty after the first ten; every subslot's
  low byte zero; counters: 0 overruns, 0 underruns.
- Taps: with the read-back arena re-poked before every poll with words that
  name their source, side and frame, channels 1–16 carry tracks 1–8 L/R,
  each only its own.
- Full speed: 1 ms packets of 44/45 8-byte frames.

#### On the unit

Image 69 (Sam's MKII, 25 Sep 2026) ran sixteen channels at 24 bits, every
channel its track's tone, 0 underruns / overruns
(USB AUDIO OUT TRACKS MAIN CUE "On the unit"). This build is not that one: it is the current source, which
has since gained MAIN/CUE (#435) and lost dead diagnostic code (#446), with
the MAIN/CUE reads assembled out. It has not run on a unit.

#### Gates

- `verify_usb` (`make check REMIX=usb-out-tracks`).

#### Per block

The producer runs 16 frames per frame interrupt. Instructions executed per
block at high speed, counted from the source (not cycles):

| module | per frame | per block | read-back words read per block |
|---|---|---|---|
| OUT TRACKS MAIN CUE | 167 | ~2,710 | 320 (256 track + 64 MAIN/CUE) |
| OUT TRACKS | 146 | ~2,370 | 256 |
| OUT MASTER | 10 | ~180 | 32 |

The port's `--profile` samples the PC every 64 instructions and gives no
exact per-block count; cycles on the chip depend on memory timing the port
does not model. `modules/cfmeter` (CF METER) measures the frame
interrupt's duration and main's idle time on a unit.

### MASTER

The unit as a USB audio input (UAC2, 44.1 kHz, 24-bit), two channels:
track 8's L/R, post-FX, pre-fader, on channels 1/2 at both USB speeds.
With MASTER TRACK on, track 8 is the mix through T8's effects, before T8's
LEVEL and MAIN volume. Needs USB MIDI.

USB AUDIO OUT TRACKS MAIN CUE's source,
`usbaudio.s` (markandrus/octemu, MIT), assembled with `USB_LAYOUT = 2`.
The variant is Sam Banks's (27 Sep 2026):

- **Producer.** Reads T8's two read-back words per frame (the same words
  as OUT TRACKS MAIN CUE's channels 15/16, the same 24-bit format) and writes one
  8-byte slot per frame into a 1,024-frame ring. No other track, no
  MAIN/CUE, no stereo sum.
- **Both speeds send the same ring.** High speed polls every 250 µs
  (bInterval 2) like the other out layouts: 11/12 frames, at most 96 bytes;
  full speed every 1 ms: 44/45 frames, at most 360 bytes. Until 28 Sep 2026
  high speed polled every 1 ms too (360-byte packets, the form on Sam's MKII
  as image 88); the 250 µs cadence is what lets a USB AUDIO IN module take
  this stream as its implicit-feedback source. Not on a unit at 250 µs.
- **Descriptors.** USB MIDI's descriptor unit declares a two-channel input
  with bmChannelConfig front left + front right (`0x3`, the standard stereo
  cluster) in the input terminal and AS_GENERAL, at both speeds; 24-bit
  samples in 4-byte subslots, a fixed 44.1 kHz clock, as OUT TRACKS MAIN CUE.
- It takes the same hook sites as OUT TRACKS MAIN CUE and OUT TRACKS, so a remix carries
  one of the three.

#### Measured

Under the port, `verify_usb` with `REMIX=usb-out-master` and `REMIX=bottleservice`
(27 Sep 2026):

- EP `0x83` isochronous, 96 bytes, bInterval 2; AS_GENERAL 2 channels,
  bmChannelConfig `0x3`.
- 88/96-byte packets at high speed, none empty after the first ten;
  every subslot's low byte zero; counters: 0 overruns, 0 underruns.
- Taps: with the read-back arena re-poked before every poll with words that
  name their source, side and frame, channel 1 carries T8 L and channel 2
  T8 R, only those, at high speed and at full speed.

#### On the unit

Image 88 (Sam's MKII, 27 Sep 2026) carried the 1 ms high-speed form (above); nothing about the stream was
measured there. The 250 µs form: not flashed.

#### Open

- Which channels an iOS app records by default. The descriptor declares a
  plain two-channel front L/R input; an app that takes the first two
  channels gets T8.
- Full speed on a phone: whether an iPhone or its adapter connects at high
  or full speed. Both carry T8.

#### Gates

- `verify_usb` (`make check REMIX=usb-out-master`, `REMIX=bottleservice`).

#### Per block and per millisecond

Counted from the source, instructions executed (not cycles):

| | OUT TRACKS MAIN CUE | OUT MASTER |
|---|---|---|
| producer, per block (16 frames) | ~2,710 | ~180 |
| read-back words read per block | 320 | 32 |
| packets built per ms (high speed) | 4 | 4 |
| bytes copied into packets per ms | ~3,530 | ~353 |
| packet builder + copy per ms | ~750 | ~250 |

`modules/cfmeter` (CF METER) measures the frame interrupt's duration and
main's idle time on a unit; the port's `--profile` samples every 64
instructions and gives no exact count.

### MAIN CUE

The unit as a USB audio input (UAC2, 44.1 kHz, 24-bit), four channels:
MAIN L/R on channels 1/2 and CUE L/R on 3/4, the DAC feed itself, at high
speed. Full speed carries MAIN alone. Needs USB MIDI.

USB AUDIO OUT TRACKS MAIN CUE's source,
`usbaudio.s` (markandrus/octemu, MIT), assembled with `USB_LAYOUT = 3`.
The variant is Bryan T's (27 Sep 2026), from usbin-test's `AUD_IN4`:

- **Producer.** Reads MAIN's and CUE's words straight from `MAIN_CUE_BASE`
  (`0x80005e60`, the same buffer OUT TRACKS MAIN CUE's channels 17-20 read and the
  stock recorder's MAIN/CUE sources read) and writes one 16-byte slot per
  frame into a 1,024-frame ring. `MAIN_CUE_BASE` is not ping-ponged, so there is
  no bank bookkeeping; no track is read and there is no stereo sum.
- **CUE with MASTER TRACK on** is written two blocks later than MAIN, so
  the two stay sample-aligned: the mixdown's master path gives CUE a
  32-sample lead
  ([OUT TRACKS MAIN CUE](#cue-against-main-with-master-track-on)).
- **High speed polls every 250 µs**, as OUT TRACKS MAIN CUE and OUT TRACKS do (not
  OUT MASTER's 1 ms): 11.025 frames × 16 bytes a packet, at most 12 frames =
  192 bytes.
- **Full speed carries MAIN alone**, two channels, 44/45 frames × 8 bytes
  every 1 ms, into the same `aud_sum` ring OUT TRACKS MAIN CUE and OUT TRACKS use for their
  stereo sum (skipped at high speed as theirs is). Every layout sends two
  channels at full speed; MAIN is the natural pair here.
- **Descriptors.** USB MIDI's descriptor unit (`HS_LAYOUT`) declares four
  channels and 192-byte packets at bInterval 2; bmChannelConfig 0 as
  OUT TRACKS MAIN CUE and OUT TRACKS; 24-bit samples in 4-byte subslots, a fixed 44.1 kHz
  clock.
- It takes the same hook sites as OUT TRACKS MAIN CUE, OUT TRACKS and OUT MASTER, so a remix
  carries one of the four.

#### Measured

Under the port, `verify_usb` with `REMIX=usb-out-main-cue` (27 Sep 2026), all checks passing:

- EP `0x83` isochronous, 192 bytes, bInterval 2; AS_GENERAL 4 channels.
- Packets of 10-12 frames × 16 bytes at high speed, none empty after the
  first ten; every subslot's low byte zero; the vendor counters read back
  with no overrun.
- Taps: with `MAIN_CUE_BASE` re-poked before every poll with words that name
  their source, side and frame, channels 1-4 carry MAIN L, MAIN R, CUE L,
  CUE R, each only its own source's words.
- Full speed: 352/360-byte packets (44/45 two-channel frames), none empty
  after the first ten.

#### On the unit

Build 16, `usb-io` (this layout beside USB AUDIO IN), Bryan T's MKII and
Mac, 27 Sep 2026: macOS lists the four inputs; MAIN L/R and CUE L/R reach
the Mac on channels 1-4; the vendor counters show no underrun while
streaming. At the start of a session the ring's fill was above its band
(884), and the servo had it back inside (632) within a second.
Overruns were counted only when macOS closed the stream (USB AUDIO IN's
README, *Latency*, has the trace).

Frame-interrupt cost (Bryan T's MKII, 4 Oct 2026, beside IN ABCD, USB
MIDI and USB CROSSBAR, host streaming, fresh-loaded FLEX projects): 93.8 µs
with no voices, 110.3 with T1, 195.3 with T1–T7, 14.2 µs per voice; OUT
TRACKS MAIN CUE in the same image reads 120.5 / 144.8 / 245.5 µs and 16.8
per voice (`docs/firmware/ARCHITECTURE.md` "ColdFire time per frame on a
unit"). Not measured with the cable out.

#### Open

- Full speed on a unit.
- What the full-speed packets contain. The gate checks their size only
  (it checks content for OUT MASTER alone, as for OUT TRACKS MAIN CUE and OUT TRACKS), so
  "full speed carries MAIN" is from the source, not a measurement.
- The producer's cost per block. It reads 64 words a block (4 per frame),
  where OUT TRACKS MAIN CUE reads the same 64 plus 256 track words; instructions not
  counted.
- USB AUDIO IN beside OUT TRACKS or OUT TRACKS MAIN CUE's larger packets on one bus.

#### Gates

- `verify_usb` (`make check REMIX=usb-out-main-cue`).

#### Why it exists

usbin-test (Bryan T, 26 Sep 2026) put the host -> A-D
stream (USB AUDIO IN) beside a MAIN+CUE-only input by forcing the
twenty-channel build down to four channels with an `AUD_IN4` flag: the
producer still made all twenty and the packet builder copied out the last
16 bytes of each slot. This module is that four-channel input as a layout
of its own, so USB AUDIO IN can be paired with it, or with OUT TRACKS or
OUT TRACKS MAIN CUE, independently. Only the four-in/four-out combination has run on
hardware, and there as the slice, not this producer.

### MAIN

MAIN L/R from the unit to the host (UAC2, 44.1 kHz, 24-bit), two channels,
a front left / front right cluster. Needs USB MIDI.

USB AUDIO OUT TRACKS MAIN CUE's
source, `usbaudio.s` (markandrus/octemu, MIT), assembled with
`USB_LAYOUT = 4`:

- **Producer.** Reads MAIN's words from `MAIN_CUE_BASE` (`0x80005e60`, the
  buffer the stock recorder's MAIN source reads; not ping-ponged, so no bank
  bookkeeping) and writes one 8-byte slot per frame into a 1,024-frame ring.
  Both speeds send that ring (the USB AUDIO OUT MASTER shape): no stereo sum,
  no per-block speed test.
- **High speed polls every 250 µs** (bInterval 2): 11.025 frames × 8 bytes a
  packet, at most 12 frames = 96 bytes. That cadence is what lets USB AUDIO
  IN use this stream as its implicit-feedback source; with USB AUDIO IN AB
  the unit is a two-in, two-out interface (remix `usb-io-main-ab`).
- **Full speed**: 44/45 frames × 8 bytes every 1 ms, at most 360 bytes.
- **Descriptors.** USB MIDI's descriptor unit (`HS_LAYOUT`) declares two
  channels, 96-byte packets at bInterval 2, `bmChannelConfig` front L/R,
  24-bit samples in 4-byte subslots, a fixed 44.1 kHz clock.
- It takes the same hook sites as the other out layouts, so a remix carries
  one of the five.

#### Measured

Under the port: `verify_usb` (`make check REMIX=usb-out-main`): EP 0x83 isochronous, 96
bytes, bInterval 2; AS_GENERAL two channels, front L/R; packets at the
250 µs cadence; the counters after the stream.

#### On the unit

Not on a unit.

#### Gates

- `verify_usb` (`make check REMIX=usb-out-main`).

#### Ground

| what | where |
|---|---|
| code | DRAM unit `usbaudio` (`USB_LAYOUT = 4`) |
| ring | 1,024 × 8 B, the unit's data |
| source | `MAIN_CUE_BASE` `0x80005e60`, MAIN at +0 |
| hooks | USB AUDIO OUT TRACKS MAIN CUE's six detours |

### TRACKS POST

The unit as a USB audio input (UAC2, 44.1 kHz, 24-bit), sixteen channels:
track N's L/R on channels 2N−1/2N, **after that track's own MAIN gain** —
track LEVEL, mute, solo and XLV (the crossfader's scene level), with core
0's 16-sample ramp — and **without MAIN_LEVEL**. Full speed: the stereo sum
of those stems. Needs USB MIDI.

`USB_LAYOUT = 5`: TRACKS' sixteen-channel stream (same descriptors, packets
and rate servo), with each track's block multiplied by the gain core 0
gives it in the MAIN mix. Choose it or TRACKS for pre-fader stems. The
POST layout is allmyfriendsaresynths's (@clickysteve); until 8 Oct 2026 it
was the module USB AUDIO OUT TRACKS POST (`usb-audio-out-tracks-post`).

#### What a channel carries

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

#### How it works

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

#### Measured

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

#### On the unit

On allmyfriendsaresynths's (@clickysteve) MKII. erreye's MK1 takes with
this layout into Ableton Live are under TRACKS MAIN CUE, *A MK1 into
Ableton Live*, above.

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

#### Cost

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

#### Open

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

#### Gates

- `verify_usb` (`make check REMIX=usb-out-tracks-post`).
- `tools/verify/verify_usb_post.py` (the manifest's gate; needs a source
  project, `OT_PROJECT` or `~/.octabam_project`).

## How it works

- **Source, tracks.** The read-back arena at SRAM `0x80003190`. The eDMA
  writes every track's post-FX pre-fader block there each frame, in
  ping-pong banks. The stock delay and Tape Echo read the same memory.
- **Source, MAIN/CUE.** Core 0's mixdown packs ESAI TX slots 2/3 (MAIN)
  and 0/1 (CUE) into the host read-back (`P:0x2df`, `P:0x2e2`). The frame
  ISR's eDMA chain ch1 → ch6 → ch7 lands them at `0x80005e60` (MAIN) and
  `0x80005ee0` (CUE), 16 × (L,R) each. The stock recorder reads the same
  buffer for SRC3 = MAIN / CUE.
- **Producer.** Runs from the frame interrupt's last instruction
  (`0x4000d9a0`), every 16-sample block while the host asks for the stream
  (alt 1 requested; since 5 Oct 2026, before that every block). It reads
  the previous bank, keeps the top 24 bits of each 32-bit sample, and
  writes one 80-byte slot per frame (20 channels × 4 bytes) into a
  1,024-frame ring, plus an 8-byte stereo sum into a second ring for full
  speed. At the first produced block after a closed spell the 64 slots the
  stream will start from are zeroed, so the packets queued at bring-up
  carry silence rather than the previous session's tail; the first-poll
  anchor (below) then puts the cursor behind live audio. A host that polls
  within 64 frames of alt 1 hears up to 64 frames of silence first. With
  the cable out the bank record is still kept, so `bankdup` counts only
  producing blocks.
- **Endpoint.** EP3 IN, isochronous, asynchronous, bInterval 2 (250 µs).
  Packets carry 11 or 12 frames, at most 960 bytes, one high-speed
  transaction. A rate servo moves the packet size ±0.2 frame (`SERVO_MAX`) against a
  `AUD_TARGET` = 64-frame target fill (512 and a deadband until 28 Sep 2026), so the stream is a gap-free copy of the ring.
  Four transfer descriptors are kept queued (1 ms of polls). The frame
  interrupt (every 363 µs) is the only context that queues packets.
- **The first poll sets the cushion.** SET_INTERFACE alt 1 queues four
  packets and then nothing more until one has retired, the controller's
  own record that the host polled. At that block the consumer is set `AUD_TARGET` (64)
  frames behind the producer and the frames produced in between are
  skipped once (`anchor` in the counters). A host that starts polling late
  (macOS: about 460 frames after alt 1, Bryan T's unit, 27 Sep 2026) had
  otherwise started the stream that much further behind for good, since
  the servo holds whatever fill it finds.
  Full speed: the stereo sum, 44 or 45 frames per 1 ms packet.
- **Descriptors.** Two functions under interface associations: the MIDI
  function, then a UAC2 AudioControl with a fixed 44.1 kHz clock source
  and an AudioStreaming interface 4 (alt 0 idle, alt 1 streaming). USB
  MIDI's descriptor unit generates this configuration when this module is
  in the remix. The clock source's CUR/RANGE/validity requests are
  answered by a shim on the stock "unknown request" STALL tail, and a SET
  CUR of its rate is taken there too (44100 acknowledged).
- **DMA memory.** The USB controller does not snoop the data cache, so the
  four dTDs and four 960-byte packet buffers are read and written only
  through the uncached SDRAM alias (address + `0x08000000`,
  `docs/contributing/PLACEMENT.md`).
- **Placement.** A DRAM unit: the loader places it in the platform reserve
  and zeroes its data, and every hook is a build-time detour. The unit is
  running before a host can enumerate, so no re-plug is needed. octemu's
  card-loaded payload, page allocator and runtime hook installer are not
  used. The ISR site is USB MIDI's; this module's shim retires EP3
  completions and chains to USB MIDI's by symbol (`Override`).

## Counters

A vendor control request (bmRequestType `0xc0`, bRequest `0x55`) returns
fifteen counters as 60 big-endian bytes: consumed, acc, overruns,
underruns, lastn, lastfill, lastbank, bankdup, lastsamp, srcjump,
reprimes, minfill, maxfill, anchor, produced. minfill/maxfill are the
ring's low and high water at packet builds since the host's first poll of
this open; anchor is the frames skipped at that poll.

- `tools/hw/usb_counters.py [--watch 1]` reads them from a unit
  (`brew install libusb`, `.venv/bin/pip install pyusb`).
- `usb_host.py … counters` reads them under the port.
- `verify_usb` checks them after its stream.

### Bus reset and session end

The stock USBSTS.URI handler (`jsr 0x4001d6b8` at `0x4001e91c`: flush, dTD
tokens cleared, ENDPTCTRL1 cleared) and the OTGSC.BSVIS session-end path
(`0x4001e952`: USBCMD.RS and USBINTR cleared) write neither `usbaudio_alt`
nor ENDPTCTRL3. USB 2.0 9.1.1.5 puts every interface back to alternate
setting 0 on a reset. Before `audio_reset_shim` and `audio_sessend_shim`, a
cable pull or host crash with the stream open left `usbaudio_alt = 1`: the
producer kept running, `usbaudio_kick` re-primed EP3 IN before the device was
configured, the next SET_INTERFACE(4, 1) took `.Lep3_same` (no flush, no
cushion zero, no anchor), and GET_INTERFACE(4) answered 1. Both shims clear
`usbaudio_alt` (and USB AUDIO IN's `in_alt` when `USB_IN`); the frame ISR
tears EP3 down. They are in every USB AUDIO OUT variant's `DETOURS` and
displace one instruction pair each (`jsr 0x4001d6b8; moveq #64,%d0`, and
`movel 0xfc0b0140,%d0`). USB MIDI hooks the same two sites to take EP2
down (`usbmidi_rx_reset_shim`, `usbmidi_rx_sessend_shim`); this module
overrides those detours and its shims call `usbmidi_rx_bus_end` after the
alt 0 request (`modules/usb-midi/README.md`, "Bus reset and session end").
Ignorato's MKII ran these shims in OCTABAM21 (9 Oct 2026): USB MIDI transmit
came back after each of three replugs on macOS and Windows 10, which is the
`usbmidi_rx_bus_end` call. The alt 0 request itself is measured under the
port only. On the session-end path the frame ISR's `audio_ep3_flush` runs
with USBCMD.RS already clear; the port's flush completes at once, so that
case is unmeasured.

## Ground

| what | where |
|---|---|
| code | DRAM unit `usbaudio` |
| rings | 1,024 × 80 B (20 channels) + 1,024 × 8 B (stereo sum), the unit's data |
| DMA memory | `aud_dtds` + `aud_bufs`, 4 × 32 B + 4 × 960 B, through the uncached alias (+`0x08000000`) |
| hooks | `0x4001e91c` bus reset (USBSTS.URI handler), `0x4001e952` session end (OTGSC.BSVIS) (both USB MIDI's, overridden), `0x4001dd04` SET_INTERFACE, `0x4001d824` GET_INTERFACE, `0x4001de64` class requests, `0x4001d4b2` EP0 page fix, `0x4000d9a0` producer, `0x4001e606` USB ISR (USB MIDI's, overridden) |
| poke | `0x400e2004` device class → `ef 02 01` |
| descriptors | USB MIDI's `usbmidi_cfg` unit, generated with the audio function when this module is in the remix |
