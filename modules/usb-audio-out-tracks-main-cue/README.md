# `usb-audio-out-tracks-main-cue` — USB AUDIO OUT TRACKS MAIN CUE

The unit as a USB audio input (UAC2, 44.1 kHz, 24-bit), twenty channels.
Needs USB MIDI: the audio function is added to its composite device.

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
[USB AUDIO OUT TRACKS POST](../usb-audio-out-tracks-post/README.md), *On the unit*).

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

## Variants

`usbaudio.s` is assembled once per module, one layout each; a remix carries one
(they take the same hook sites, and the build refuses two by name):

| module | `USB_LAYOUT` | high speed | full speed |
|---|---|---|---|
| USB AUDIO OUT TRACKS MAIN CUE (this) | 0 | 20 channels: tracks 1–16, MAIN, CUE | the tracks' stereo sum |
| [USB AUDIO OUT TRACKS](../usb-audio-out-tracks/README.md) | 1 | 16 channels: the tracks | the tracks' stereo sum |
| [USB AUDIO OUT MASTER](../usb-audio-out-master/README.md) | 2 | 2 channels: track 8's L/R | track 8's L/R |
| [USB AUDIO OUT TRACKS POST](../usb-audio-out-tracks-post/README.md) | 5 | 16 channels: the tracks after their own MAIN gain | the stems' stereo sum |

The layout is a `.set` in the `remix.inc` each module's `Linked` unit
writes. Every `USB_LAYOUT = 0` path is the source as it was; this module's
image is byte-identical to the one built before the variants (27 Sep 2026).

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
`movel 0xfc0b0140,%d0`). Port only. On the session-end path the frame ISR's
`audio_ep3_flush` runs with USBCMD.RS already clear; the port's flush
completes at once, so that case is unmeasured.

## Ground

| what | where |
|---|---|
| code | DRAM unit `usbaudio` |
| rings | 1,024 × 80 B (20 channels) + 1,024 × 8 B (stereo sum), the unit's data |
| DMA memory | `aud_dtds` + `aud_bufs`, 4 × 32 B + 4 × 960 B, through the uncached alias (+`0x08000000`) |
| hooks | `0x4001e91c` bus reset (USBSTS.URI handler), `0x4001e952` session end (OTGSC.BSVIS), `0x4001dd04` SET_INTERFACE, `0x4001d824` GET_INTERFACE, `0x4001de64` class requests, `0x4001d4b2` EP0 page fix, `0x4000d9a0` producer, `0x4001e606` USB ISR (USB MIDI's, overridden) |
| poke | `0x400e2004` device class → `ef 02 01` |
| descriptors | USB MIDI's `usbmidi_cfg` unit, generated with the audio function when this module is in the remix |
