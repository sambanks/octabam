# `usb` — USB

Class-compliant USB-MIDI in and out on the Octatrack's own USB port,
mirroring the DIN ports, beside a UAC2 audio function at 44.1 kHz, 24-bit:
the unit into the host on EP3 IN (2 to 20 channels by the settings), the host
into the Octatrack's inputs on EP3 OUT (a stereo pair or four channels by
IN). The USB controller bursts first on the SDRAM and SRAM-backdoor
slaves (SCM BCR, XBS PRS/CRS), written once at the stock USB controller init
and left on; without it the controller's 16-byte RX FIFO loses packet tails
under a busy project.

One module since 14 Oct 2026, where four stood (USB MIDI, USB AUDIO OUT,
USB AUDIO IN, USB CROSSBAR): six NEXT_BOOT settings choose which channels
go to the host (TRACKS OFF/PRE/POST, MAIN, CUE, MASTER) and which inputs
the host's channels stand in for (IN). The defaults are TRACKS PRE, MAIN
and CUE on, MASTER off, IN off, MIDI on. Every combination carries USB
MIDI's units.

IN without an output stream is refused: EP3 IN is EP3 OUT's
implicit-feedback source, the stream the host sizes each EP3 OUT packet
from. The memory claims are the ABCD maxima in every combination with IN
on. The four sections below carry the four modules' documentation.

## Settings

The design of 14 Oct 2026, `git show 76fd8466:docs/proposals/USB.md`, proposed two settings (LAYOUT, INPUTS); the six below are what was built. Its section 9 listed what to find out: the order of card mount and USB enumeration at boot, the producer's size and per-frame dispatch cost with all six layouts, the parametric inject's cycles, re-enumeration after a replug with a changed value on each host OS, and the rule for an invalid combination. Their status was not re-checked when the page was removed.

The inject (`rx_inject.asm`, 29 words on payload A) is placed whenever IN could be on: a remix that fixes IN at OFF (a `Pin`, or no BRAIN) carries no DSP section. In a remix that gives up a stock effect it goes in the donor region; in one that keeps all fourteen it goes above payload A's code, `P:$1fdf`, in a load record of its own carried by a pre-boot copy of the payload (`DspSection.tail`, `docs/contributing/PLACEMENT.md`; `remixes/test/usb-io-stock14`, on Bryan T's MKII 22 Oct 2026). `octabam-core` carries it in the tail; IN is selectable there (default OFF).

Six NEXT_BOOT settings, early (`docs/specs/BRAIN.md` 6.4: the CS1
early block, read by cfgsel at the USB controller init, so they stand
from the first enumeration):

| setting (default) | value | meaning |
|---|---|---|
| TRACKS (PRE) | OFF | no audio to the host, whatever else is on |
| | PRE | 16 channels: the tracks |
| | POST | 16 channels: the tracks after their own MAIN gain |
| MAIN (ON) | Binary | 2 channels: MAIN |
| CUE (ON) | Binary | 2 channels: CUE |
| MASTER (OFF) | Binary | 2 channels: track 8's L/R (not with TRACKS) |
| IN (OFF) | OFF | no host -> device stream |
| | AB | host channels 1/2 = inputs A/B; C/D stay on the jacks |
| | CD | host channels 1/2 = inputs C/D; A/B stay on the jacks |
| | ABCD | host channels 1–4 = inputs A–D |
| MIDI (ON) | Binary | USB MIDI in/out; without it the audio interfaces renumber (AC 1 / AS 2 / IN 3) |

The pair rule: IN ≠ OFF requires TRACKS ≠ OFF or MAIN or CUE or MASTER
(the build refuses the combination, brain.c usb_pair_ok; cfgsel forces IN
off on a bad block). TRACKS with MASTER is refused the same three ways
(brain.c usb_master_ok; cfgsel clears MASTER): MASTER is track 8's L/R,
which TRACKS already carries. Scrubbed 27 Oct 2026 at Sam's request: it was
a layout from before the checkboxes, the only combination over 20
channels (it needed 125 µs polling), never run on a unit, and with TRACKS
on the old producer stored MASTER into the next frame's track 8 field, so
its channels never carried it. The channel count is 16 × TRACKS(≠ OFF) +
2 × (MAIN + CUE + MASTER): 20 at most, polled at 250 µs (bInterval 2). Every
combination's full-speed form is two channels, and IN is served at high
speed only.

### Descriptor counts with MIDI off (#1039, 4 Nov 2026)

Reported by yvesrosius (MKII, image STEMS11, two Windows 11 laptops). With
MIDI at OFF, DISK MODE did not mount on Windows: Device Manager showed "USB
Mass Storage Device" with Code 10, USBSTOR `0xC0000182`. The reporter read
the configuration descriptor off the hub port: the MSC interface declared
`bNumEndpoints` 1 and two endpoints (bulk IN `0x81`, bulk OUT `0x01`)
followed. Windows trusts the count, finds no bulk OUT, and the driver fails.

- `msc_only_config` and `audio_config` (MIDI off) declared 1. Stock 1.40C's
  four MSC interface descriptors declare 2 (read from the stock bytes at
  `0x400e2025..0x400e2085`); both builders now do, whatever MIDI is.
- `descriptors.check_config` walks a configuration and refuses it when
  `wTotalLength`, `bNumInterfaces` or an interface's `bNumEndpoints` disagree
  with what follows; `_blob` runs it over all four tables of all 256 sets, so
  a bad combination fails the build. It found a second count off by one:
  every audio configuration with MIDI off declared `bNumInterfaces` 2 (3 with
  IN) for MSC, AudioControl and AudioStreaming (+ the IN stream), now 3 (4).
  `verify_usb` had copied that formula; it expects the corrected counts.
- Inferred, not tried on a unit: the interface count could also stop a strict
  host from using the audio function with MIDI off. macOS and Linux were not
  tried by the reporter.
- Gate: `tools/verify/tests/test_usb_descriptors.py` (every set passes; MSC
  declares its two endpoints with MIDI off and on; the old count and a wrong
  total or interface count are refused). Not flashed.

## USB MIDI

Class-compliant USB-MIDI in and out on the Octatrack's own USB port,
mirroring the DIN ports. markandrus's work ([octemu](https://github.com/markandrus/octemu),
`custom/usb-midi.py` + `custom/coldfire/usb-midi.s` at `6a9ff68`, MIT),
carried onto octabam's DRAM platform.

### Receive path (port only, 5 Oct 2026)

Static review of `usbmidi_rx_decode` found no bound on the FIFO, then
measured under the port (`usb-midi` remix, `ot_emu --watch-mem` on the
FIFO and the framer's message buffer, one EP2 OUT packet per case):

| packet | before | after |
|---|---|---|
| 16 note-ons, 64 B (48 MIDI bytes) | FIFO count reached 48 of 32 slots; 16 messages parsed, notes `3b 3c 3d 3e 3f 35 36 37 38 39 3a 3b 3c 3d 3e 3f`; `30..34` never parsed | 16 messages, notes `30..3f` in order |
| 68-byte SysEx, 23 events, 92 B | dTD accepted 64 of 92 B; the 68 bytes did not arrive in the parser's buffer (`verify_usbmidi_rx`, first difference at byte 0) | 92 B accepted, `F0 01..42 F7` parsed intact |
| 128 note-ons, 512 B | dTD accepted 64 of 512 B; the 384 bytes did not arrive in order (first difference at byte 0) | 512 B accepted, 384 bytes parsed in order |
| 16 note-ons at full speed, 64 B | in order | in order |

Causes (read from the stock disassembly; the measurements above agree):

- `midi_rx_enqueue` (`0x40092bbc`) stores `ring[head]`, `head++` (wrap at 32),
  `count++` and forces INTC source 36, with no full check. The consumer, the
  framer `0x40092bf4`, pops one byte per interrupt. Its ICR (`0xfc048064`) and
  the USB OTG ICR (`0xfc04c06f`) are both written `4` by the firmware, so the
  framer cannot run inside the USB interrupt at any SR. The DIN path takes one
  byte per UART interrupt and never fills the ring; a packet of more than 32
  MIDI bytes overwrites unread ones.
- The RX dTD token is `0x00408080` (64 bytes) at the dormant init and in
  `usb_midi_rx_prime`, while the dQH and the descriptors advertise a 512-byte
  bulk max packet at high speed.
- The dTD token's status bits were not read.

The receive path in `usbmidi.s` (octabam's; the unit started as his text and
is no longer compared with his build) takes over the SET_CONFIGURATION and
usb_isr detours and hands on to the shims it started from:

- Before the bytes of each event are enqueued, `count + event bytes` must be
  at most 32; otherwise the framer is entered from the decoder with a
  fabricated exception frame (format 4, vector `0x64`, the current SR, over a
  return address), pops one byte, parses it and posts what it completes, as its
  interrupt would. The framer runs at the SR the USB ISR entered with; the
  enqueues of one event run at SR `0x2700`.
- Chosen over lowering the SR mask around each enqueue (the framer is the same
  INTC level as the USB interrupt and cannot preempt it; lowering the mask
  below 4 lets the USB interrupt re-enter) and over keeping the rest of the
  packet for a later interrupt (nothing wakes the module after the last USB
  interrupt of a burst).
- At high speed the RX dTD is re-sized to 512 bytes: flush EP2 OUT
  (ENDPTFLUSH bit 2), clear the dQH overlay token, prime with token
  `0x02008080`. Full speed keeps the firmware's 64-byte dTD (max packet 64: a
  dTD larger than the max packet does not complete on a full packet).
- A completed dTD with halted, data buffer error or transaction error status
  is counted in `usbmidi_rx_errs` and not decoded.

The port's flush completes at once and ignores the overlay; the controller's
behaviour on the flush/re-prime sequence is not measured. Hardware status:
port only.

`usbmidi_rx_sysex` (usbmidi.s) is set to 1 whenever the decoder enqueues an `F0`. SCREEN reads and
clears it at every SysEx to answer on the transport the request came on (`modules/screen/README.md`).

### Clock (6 Oct 2026)

Reported by Kazeko (MKI, Discord, 6 Oct 2026): with USB MIDI clock the
sequencer follows, time stretch, LFOs and FX do not; DIN clock drives all
of them. After the change (#633), the same unit: reported working; the
build number and which of the three were checked are not recorded.

- The UART0 ISR (`0x400106ec`) timestamps each `0xF8` before passing it on:
  DTCN0 (`0xfc07000c`) into `0x46c8345a`, the delta into `0x46c83466`
  (`0x4001070a..0x4001071e`). The clock handler (`0x40005a48`) builds the
  tempo from that delta: a 24-tick ring, `24 * 21,168,000 * 32 / sum`,
  clamped 600..7320, into `0x80001818` (and `0x80001814` every 24th tick).
  The decoder called `midi_rx_enqueue` directly and stored no timestamp.
- Measured under the port before the change (`usb-midi` remix, CLOCK
  RECEIVE set, 96 ticks per run): the handler ran on all 96 USB ticks; from
  cold the interval stayed 0, the ring sum stayed under the handler's
  threshold and `0x80001818` was never written (the project's 2880); after
  DIN clock it held the last DIN interval and the DIN tempo (2402) through a
  USB run at another rate. That the time stretch, LFOs and FX read this
  tempo is inferred.
- `usbmidi_rx_decode` now does the ISR's five instructions for each `0xF8`
  before it is enqueued. `verify_usb_midi_clock`: two USB runs at 50 and
  40 ms per tick read 1200 and 1498 (want 1200 and 1501); before the change
  both read 2400, the DIN run's tempo.
- DTIN0's clock is inferred: the handler's constant gives BPM × 24 only for
  256 fs (11.2896 MHz). The port counts DTCN0 at that rate (`rtos.h`);
  before this change it held at 0 and no MIDI clock tempo ran under the port.

### One clock source, DIN first (#944, 1 Nov 2026)

Measured under the port (#944, `origin/main` `3b62cdef`, no project
loaded, CLOCK RECEIVE set): DIN and USB clock at the same 120 BPM put
5267 to 6424 in `0x80001818` (want 2880); with USB bunched 4 per packet
it read the clamp, 7320. Both sources reach the one FIFO, framer and clock
handler, so together they are one stream of 48 ticks per beat: the
handler's interval ring reads the gaps between the two sources' ticks, and
the clocked tempo is copied into the project's `TEMPOx24` (`0x80000020`,
CS1 mirror `0x100b1480`) at each clock start (stock; a single source
moves it too). That the sequencer also steps on both is inferred; no
project was playing.

`usbmidi_rx_decode` now drops a USB clock or transport event (`0xF8`,
`0xFA`, `0xFB`, `0xFC`, `0xF2`) whole, counted in `usbmidi_rx_dropped`,
while DIN is clocking. That means `CLK_T` (`0x46c8345a`) differs from
`usbmidi_rx_clk_t`, the last stamp the decoder wrote, and is under
1,881,600 DTCN0 counts (167 ms, the clock handler's resync gap) old.
The first USB tick taken after DIN stops carries a delta past that gap,
so the handler starts a fresh ring. A stale foreign `CLK_T` is adopted,
so a DTCN0 wrap (380 s) cannot make an old DIN tick look recent. DIN
needs no detour: it wins whenever both run. The cost: a DIN device that
sends clock all the time locks USB clock out.

`verify_usb_midi_clock`: a DIN + USB run at DIN's rate (each USB tick
half a tick after a DIN one) must read DIN's tempo, with all 48 USB ticks
dropped; the USB runs after it start 250 ms after DIN's last tick and must
read USB's tempo; a USB STOP sent while DIN clocks must leave the transport
playing. Measured under the port (`test/usb-midi`, 1 Nov 2026): DIN + USB
at 1324 samples per tick read 1994 (want 1998), 48 of 48 USB ticks dropped,
the USB STOP left the transport at 1. With the previous `usbmidi_rx.s` the
same run read 4048, dropped none, and the USB STOP stopped the sequencer
(transport 2). Hardware status: port only.

### Bus reset and session end (9 Oct 2026)

Measured on a unit (Ignorato's MKII, OCTABAM14 = a test remix with this module,
USB AUDIO OUT TRACKS MAIN CUE and USB CROSSBAR; 7-9 Oct 2026): unit-to-host
USB MIDI works on the first connection after the unit boots and stops for
good after the cable is unplugged and plugged back in, on macOS (M1) and two
Windows 10 PCs (Intel, ASMedia and AMD xHCI); only a power cycle brings it
back. On Windows a USBPcap capture shows the host's 16 bulk IN reads on
`0x82` never completing. A bus reset with the cable left in (libusb
re-enumeration on macOS) does not do it. Host-to-unit MIDI is unaffected.

Read from `usbmidi.s`: `usbmidi_up` is set at SET_CONFIGURATION and never
cleared, and `usbmidi_tx_busy` is cleared only by an EP2 IN completion or by
SET_CONFIGURATION. The unit is mains powered, so both outlive a cable pull.

Under the port (`verify_usb_midi_replug`, the `usb-midi` remix; `ot_emu`'s
new `plug` command brings the session back after `unplug`), on this module
before the change:

- after a pull with EP2 IN idle, the next clock byte primes EP2 IN while
  USBCMD.RS is clear (the controller stopped, nobody to read it);
- the clock bytes queued while unplugged go out after the next
  SET_CONFIGURATION, ahead of the new session's first message;
- a bus reset with the cable in shows neither, which matches the unit.

The port does not hang: its prime re-reads the queue head every time, a
flush cancels anything, and it has no data toggles or NAK timing. How
silicon then loses EP2 IN for good is inferred, not measured: a prime the
controller has not taken is not cancelled by a flush, and the dormant
EP2_INIT at SET_CONFIGURATION rewrites the queue head of an endpoint that
may still be primed (the ChipIdea hazard `usbaudio.s` already guards EP3
against).

`usbmidi.s` now takes EP2 down on a bus reset (`0x4001e91c`, the
USBSTS.URI handler) and on session end (`0x4001e952`, OTGSC.BSVIS, before
the stock code clears USBCMD.RS), and again at SET_CONFIGURATION before
EP2_INIT: `usbmidi_up` and `usbmidi_tx_busy` cleared, the queued bytes
dropped, both EP2 directions flushed (wait for ENDPTPRIME, flush, repeat
while ENDPTSTAT shows a bit, every wait bounded), both overlay tokens
cleared, any EP2 completion dropped. The two sites are USB AUDIO's too:
with an output stream its `audio_reset_shim` and
`audio_sessend_shim` override these detours and call `usbmidi_rx_bus_end`.
After the change all 21 of `verify_usb_midi_replug`'s checks pass (five fail
before).

On a unit (Ignorato's MKII, 9 Oct 2026, image OCTABAM21 = the OCTABAM14
test remix plus this change; MIDI clock send on, the host only listening,
the unit sends clock about 48 times a second while stopped). Each run: a
power cycle with the cable in, then three unplug and replug cycles in the
same port:

| host | before (OCTABAM14) | after (OCTABAM21) |
|---|---|---|
| Mac mini M1, macOS 26.4.1, CoreMIDI | power cycle: 720 clocks in 15 s; replugs: 0, 0, 0, 0 (four in a row) | power cycle and all three replugs: 720 clocks in 15 s each |
| Lenovo laptop, Windows 10 22H2, AMD USB 3.1 xHCI, in-box driver | power cycle: 720; replug: 0 (2 of 2 each) | power cycle and all three replugs: 720 each |

Not measured on a unit: host-to-unit MIDI after a replug (port only), many
replugs, host sleep and wake, a hub.

### Open

- Not measured: clock jitter over USB against DIN (bulk transfers have no schedule; the
  gate sends one `0xF8` per transfer, a host can bunch several into one
  packet, and each then gets a near-zero interval); how late a clock byte
  goes out behind a ring backlog; the ring on a unit; DISK MODE entered with a MIDI session open; Windows.

### A completion between the two ENDPTCOMPLETE reads (#1017, 4 Nov 2026)

Reported by xynta, under the port on Octatrick 2.21's pin (`6e4aeb76`); the
path is unchanged on main. `usbmidi_rx_isr_shim` reads ENDPTCOMPLETE, takes an
EP2 OUT completion and re-primes the 512-byte dTD, then jumps to his
`usbmidi_isr_shim`, which reads ENDPTCOMPLETE again and still takes bit 2 the
64-byte way. A transfer completing between the two reads was cleared there with
`64 - remaining <= 0` bytes and not decoded, and the stock 64-byte
`usb_midi_rx_prime` left `usbmidi_rx_state` at 2, so the next transfer decoded
as `448 + n` bytes: the tail of an older transfer replayed. Measured by the
reporter, paced bench under the port: 174,012 bytes enqueued for 12,348 sent,
500 of 1,000 short transfers lost, 55,888 stale events. On a unit that is a lost
packet now and then (a lost note-off is a stuck note) and the rest of an earlier
chord after the next one (inferred).

- The fix: `usbmidi_rx_isr_shim` reads ENDPTCOMPLETE once, w1c's the EP2 bits
  it saw in one write and handles EP2 OUT and EP2 IN from that snapshot. The
  hand-over shim, its 64-byte decoder, the detour at `usb_midi_rx_prime`
  (`0x4001d184`) and the `usbmidi_rx_late` counter are gone. usb_isr's own tail
  handles EP0 and EP1 only, so nothing else reads the EP2 bits. A completion
  after the read raises a new UI interrupt, because stock w1c's USBSTS.UI at
  `0x4001e600`, before the hook (inferred from the code; not measured on a
  unit). With the session down (`usbmidi_up` = 0) the bits are cleared and not
  handled, as before. Masking the old second read could not close the window
  (the controller sets the bit, not an interrupt); owning the file is what
  allowed removing it.
- The reporter's form (a detour at `usb_midi_rx_prime`) ran 12,348 of 12,348
  bytes once each and in order on the same bench (late branch taken 500 times)
  and has been on their MKI since 2 Nov 2026. The single-read form replaces it
  and is not on a unit.
- Still open, from the same report: a transfer over 64 bytes sent between
  SET_CONFIGURATION and the next USB interrupt lands in the dormant init's
  64-byte dTD (port: taken as 64 bytes; on silicon a data buffer error,
  inferred). Not changed here.

### What it is

OS 1.40C ships a complete USB-MIDI transmit encoder (`0x4001d204`: raw
bytes to 4-byte event packets, running status, SysEx spans) and the EP2
primitives, reached by nothing, and no receive decoder. The module:

- grows the configuration descriptors to MSC + AudioControl + MIDIStreaming
  with EP2 bulk in/out (`descriptors.py`, generated per remix into the
  `usbmidi_cfg` unit; `cfg_len` is the length the two clamp shims read);
- brings EP2 up at SET_CONFIGURATION (512-byte packets at high speed),
  answers CLEAR_FEATURE(ENDPOINT_HALT) for it;
- dispatches EP2 completions from the USB ISR: IN completion frees the
  transmit slot and drains the queue, OUT completion runs the receive
  decoder, which feeds `midi_rx_enqueue` (`0x40092bbc`), the byte path DIN
  MIDI uses, then re-primes (`usbmidi.s`, see "Receive path");
- mirrors both senders into the encoder: `midi_send` (channel messages)
  and the priority byte sender (clock, transport). Messages are queued in
  a 256-byte accumulator behind one transfer, and behind that in a 4 KB
  ring of whole messages, moved into the accumulator at each kick, in
  order. A message longer than 255 bytes or one the ring has no room for
  is counted in `usbmidi_tx_drops`, never sent corrupt. Bus reset, session
  end and SET_CONFIGURATION empty both (`usbmidi_tx_reset`). Before the
  ring, a burst longer than the accumulator lost its tail (#1016: 86 of
  283 CCs under the port, `usbmidi_tx_drops` +197;
  `verify_usbmidi_tx_ring`: 283 of 283 in order, drops +0). The ring adds
  4,104 bytes of DRAM to the unit. The design is xynta's (#1016).

Eight detours, four descriptor-pointer rewrites, no pokes. `usbmidi` is one
unit, started from markandrus's `usb-midi.s` (`6a9ff68`, MIT) and octabam's
from the TX ring on; it is no longer compared with his blob. The clamps are a
second unit (`clamp.s`, his usb-audio.s shims reading `cfg_len`).

### Ground

| what | where |
|---|---|
| code + queues | DRAM units `usbmidi` (1,124 B, his bytes), `usbmidi_rx` and `usbmidi_clamp` in the platform reserve |
| descriptors | DRAM unit `usbmidi_cfg` (4 × 124 B, or 4 × 250 B with an output stream) |
| hooks | `0x4001d9ca` `0x4001daec` `0x4001e606` `0x40010bc8` `0x400108b0` `0x4001d858` `0x4001d896` `0x4001e91c` `0x4001e952` (the last two replaced by the audio shims, which call `usbmidi_rx_bus_end`) |
| pointer rewrites | the responder's four `pea` operands `0x4001d882` `0x4001d88a` `0x4001d8c0` `0x4001d8c8` |
| firmware memory it uses | the firmware's own EP2 dQHs, dTDs and buffers (`0x4ec94900..`, `0x4ecc8000`, `0x4ecc9000`; the RX buffer's 4 KB page has no other reference in the image) |

## Audio out (settings)

The unit as a USB audio input (UAC2, 44.1 kHz, 24-bit), the stream shaped
by five of the six NEXT_BOOT settings (TRACKS OFF/PRE/POST, MAIN, CUE,
MASTER; see *Settings* above): the checked boxes in slot order, summed at
full speed (sum priority: TRACKS > MAIN > CUE > MASTER). Needs USB MIDI:
the audio function is added to its composite device.

| settings | high speed | full speed |
|---|---|---|
| TRACKS MAIN CUE (the released defaults) | 20 channels: tracks 1–16, MAIN, CUE | the tracks' stereo sum |
| TRACKS | 16 channels: the tracks | the tracks' stereo sum |
| MASTER | 2 channels: track 8's L/R | track 8's L/R |
| MAIN CUE | 4 channels: MAIN, CUE | MAIN |
| MAIN | 2 channels: MAIN | MAIN |

Until 6 Oct 2026 each layout was a module of its own (USB AUDIO OUT TRACKS
MAIN CUE, OUT TRACKS, OUT MASTER, OUT MAIN CUE, OUT MAIN); each remix's
image is byte-identical to the one it built with those modules. The
sections from here to *Layouts* describe TRACKS MAIN CUE, the twenty
channels; *Layouts* has the other shapes.

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

### Open

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

### Layouts

The shapes are one runtime: cfgsel serves the settings at the USB
controller init (usb_trk, usb_nch), and the producer and the descriptor
builder branch on those bytes. The five below take the same hook sites;
the producer detour's note in the build report names the shape.

#### TRACKS

The unit as a USB audio input (UAC2, 44.1 kHz, 24-bit), sixteen channels:
track N's L/R on channels 2N−1/2N, post-FX, pre-fader. MAIN and CUE are
left out. Full speed: the stereo sum of the eight tracks. Needs USB MIDI.

USB AUDIO OUT TRACKS MAIN CUE's source,
`usbaudio.s` (markandrus/octemu, MIT), the TRACKS path:
the producer skips the MAIN/CUE reads and writes a 64-byte slot per frame;
packets are 11/12 frames, at most 768 bytes, every 250 µs. Everything else
(the shims, the rate servo, the counters, the descriptors' shape) is that
module's. It takes the same hook sites, so a remix pins one layout.

##### Per block

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

#### MASTER

The unit as a USB audio input (UAC2, 44.1 kHz, 24-bit), two channels:
track 8's L/R, post-FX, pre-fader, on channels 1/2 at both USB speeds.
With MASTER TRACK on, track 8 is the mix through T8's effects, before T8's
LEVEL and MAIN volume. Needs USB MIDI.

USB AUDIO OUT TRACKS MAIN CUE's source,
`usbaudio.s` (markandrus/octemu, MIT), the MASTER path.
The variant is Sam Banks's (27 Sep 2026):

- **Producer.** Reads T8's two read-back words per frame (the same words
  as OUT TRACKS MAIN CUE's channels 15/16, the same 24-bit format) and writes one
  8-byte slot per frame into a 1,024-frame ring. No other track, no
  MAIN/CUE, no stereo sum.
- **Both speeds send the same ring.** High speed polls every 250 µs
  (bInterval 2) like the other out layouts: 11/12 frames, at most 96 bytes;
  full speed every 1 ms: 44/45 frames, at most 360 bytes. Until 28 Sep 2026
  high speed polled every 1 ms too (360-byte packets, the form on Sam's MKII
  as image 88); the 250 µs cadence is what lets IN take this stream as
  its implicit-feedback source. Not on a unit at 250 µs.
- **Descriptors.** USB MIDI's descriptor unit declares a two-channel input
  with bmChannelConfig front left + front right (`0x3`, the standard stereo
  cluster) in the input terminal and AS_GENERAL, at both speeds; 24-bit
  samples in 4-byte subslots, a fixed 44.1 kHz clock, as OUT TRACKS MAIN CUE.
- It takes the same hook sites as OUT TRACKS MAIN CUE and OUT TRACKS, so a remix pins one layout.

##### Open

- Which channels an iOS app records by default. The descriptor declares a
  plain two-channel front L/R input; an app that takes the first two
  channels gets T8.
- Full speed on a phone: whether an iPhone or its adapter connects at high
  or full speed. Both carry T8.

##### Per block and per millisecond

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

#### MAIN CUE

The unit as a USB audio input (UAC2, 44.1 kHz, 24-bit), four channels:
MAIN L/R on channels 1/2 and CUE L/R on 3/4, the DAC feed itself, at high
speed. Full speed carries MAIN alone. Needs USB MIDI.

USB AUDIO OUT TRACKS MAIN CUE's source,
`usbaudio.s` (markandrus/octemu, MIT), the MAIN CUE path.
The variant is Bryan T's (27 Sep 2026), from usbin-test's `AUD_IN4`:

- **Producer.** Reads MAIN's and CUE's words straight from `MAIN_CUE_BASE`
  (`0x80005e60`, the same buffer OUT TRACKS MAIN CUE's channels 17-20 read and the
  stock recorder's MAIN/CUE sources read) and writes one 16-byte slot per
  frame into a 1,024-frame ring. `MAIN_CUE_BASE` is not ping-ponged, so there is
  no bank bookkeeping; no track is read and there is no stereo sum.
- **CUE with MASTER TRACK on** is written two blocks later than MAIN, so
  the two stay sample-aligned: the mixdown's master path gives CUE a
  32-sample lead.
- **High speed polls every 250 µs**, as OUT TRACKS MAIN CUE and OUT TRACKS do (not
  OUT MASTER's 1 ms): 11.025 frames × 16 bytes a packet, at most 12 frames =
  192 bytes.
- **Full speed carries MAIN alone**, two channels, 44/45 frames × 8 bytes
  every 1 ms, into the same `aud_sum` ring OUT TRACKS MAIN CUE and OUT TRACKS use for their
  stereo sum (skipped at high speed as theirs is). Every layout sends two
  channels at full speed; MAIN is the natural pair here.
- **Descriptors.** USB MIDI's descriptor unit declares four
  channels and 192-byte packets at bInterval 2; bmChannelConfig 0 as
  OUT TRACKS MAIN CUE and OUT TRACKS; 24-bit samples in 4-byte subslots, a fixed 44.1 kHz
  clock.
- It takes the same hook sites as OUT TRACKS MAIN CUE, OUT TRACKS and OUT MASTER, so a remix pins one layout.

##### Open

- Full speed on a unit.
- What the full-speed packets contain. The gate checks their size only
  (it checks content for OUT MASTER alone, as for OUT TRACKS MAIN CUE and OUT TRACKS), so
  "full speed carries MAIN" is from the source, not a measurement.
- The producer's cost per block. It reads 64 words a block (4 per frame),
  where OUT TRACKS MAIN CUE reads the same 64 plus 256 track words; instructions not
  counted.
- USB AUDIO IN beside OUT TRACKS or OUT TRACKS MAIN CUE's larger packets on one bus.

##### Why it exists

usbin-test (Bryan T, 26 Sep 2026) put the host -> A-D
stream (USB AUDIO IN) beside a MAIN+CUE-only input by forcing the
twenty-channel build down to four channels with an `AUD_IN4` flag: the
producer still made all twenty and the packet builder copied out the last
16 bytes of each slot. This is that four-channel input as a layout
of its own, so IN can be paired with it, or with the track or
OUT TRACKS MAIN CUE, independently. Only the four-in/four-out combination has run on
hardware, and there as the slice, not this producer.

#### MAIN

MAIN L/R from the unit to the host (UAC2, 44.1 kHz, 24-bit), two channels,
a front left / front right cluster. Needs USB MIDI.

USB AUDIO OUT TRACKS MAIN CUE's
source, `usbaudio.s` (markandrus/octemu, MIT), the MAIN path:

- **Producer.** Reads MAIN's words from `MAIN_CUE_BASE` (`0x80005e60`, the
  buffer the stock recorder's MAIN source reads; not ping-ponged, so no bank
  bookkeeping) and writes one 8-byte slot per frame into a 1,024-frame ring.
  Both speeds send that ring (the USB AUDIO OUT MASTER shape): no stereo sum,
  no per-block speed test.
- **High speed polls every 250 µs** (bInterval 2): 11.025 frames × 8 bytes a
  packet, at most 12 frames = 96 bytes. That cadence is what lets USB AUDIO
  IN use this stream as its implicit-feedback source; with IN AB
  the unit is a two-in, two-out interface (remix `usb-io-main-ab`).
- **Full speed**: 44/45 frames × 8 bytes every 1 ms, at most 360 bytes.
- **Descriptors.** USB MIDI's descriptor unit declares two
  channels, 96-byte packets at bInterval 2, `bmChannelConfig` front L/R,
  24-bit samples in 4-byte subslots, a fixed 44.1 kHz clock.
- It takes the same hook sites as the other out shapes; the settings choose the shape at the next boot.

##### Ground

| what | where |
|---|---|
| code | DRAM unit `usbaudio` (the MAIN path) |
| ring | 1,024 × 8 B, the unit's data |
| source | `MAIN_CUE_BASE` `0x80005e60`, MAIN at +0 |
| hooks | USB AUDIO OUT TRACKS MAIN CUE's six detours |

#### TRACKS POST

The unit as a USB audio input (UAC2, 44.1 kHz, 24-bit), sixteen channels:
track N's L/R on channels 2N−1/2N, **after that track's own MAIN gain** —
track LEVEL, mute, solo and XLV (the crossfader's scene level), with core
0's 16-sample ramp — and **without MAIN_LEVEL**. Full speed: the stereo sum
of those stems. Needs USB MIDI.

TRACKS POST: TRACKS' sixteen-channel stream (same descriptors, packets
and rate servo), with each track's block multiplied by the gain core 0
gives it in the MAIN mix. Choose it or TRACKS for pre-fader stems. The
POST shape is allmyfriendsaresynths's (@clickysteve); until 8 Oct 2026 it
was the module USB AUDIO OUT TRACKS POST (`usb-audio-out-tracks-post`).

##### What a channel carries

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

##### How it works

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

##### Cost

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

##### Open

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

### How it works

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
  writes each frame in the stream's own layout (the checked fields in wire
  order: 16 tracks × 4 B, then MAIN, CUE, MASTER, 8 B each; `usb_frame_bytes`
  a frame) into a 1,024-frame ring through the uncached alias, and each
  high-speed packet's dTD points into that ring, so nothing is copied
  (since 27 Oct 2026; before, 88-byte slots copied into packet buffers,
  5.9 µs a frame at OUT MAIN CUE on Bryan T's MKII). A packet that runs
  past the ring's end continues into 12 spill frames, filled from the
  ring's start just before it is queued. Plus an 8-byte stereo sum into a second ring for full
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
  MIDI's descriptor unit generates this configuration when an output
  stream is on. The clock source's CUR/RANGE/validity requests are
  answered by a shim on the stock "unknown request" STALL tail, and a SET
  CUR of its rate is taken there too (44100 acknowledged).
- **DMA memory.** The USB controller does not snoop the data cache, so the
  high-speed ring and the four full-speed packet buffers are read and
  written only through the uncached SDRAM alias (address + `0x08000000`,
  `docs/contributing/PLACEMENT.md`). The four dTDs are in on-chip SRAM at
  `0x800079c0` (since 27 Oct 2026, `Claims.sram`), as USB IN's are.
- **Placement.** A DRAM unit: the loader places it in the platform reserve
  and zeroes its data, and every hook is a build-time detour. The unit is
  running before a host can enumerate, so no re-plug is needed. octemu's
  card-loaded payload, page allocator and runtime hook installer are not
  used. The ISR site is USB MIDI's; this module's shim retires EP3
  completions and chains to USB MIDI's by symbol (`Override`).

### Counters

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

A second vendor GET, `0xc0/0x57`, returns LOAD METER's cells when the
remix carries it (`LM_STATS`, `LM_DSP`, `LM_OT` are `defsyms`, 0 without
the module, and a request then STALLs as stock does): wValue low 0 is
`lm_stats` (20 bytes), 1 `lm_dsp` (48), 2 `lm_ot` (256), big-endian longs,
from byte `wIndex` low on. The reply is copied into `lm_reply` through the
uncached alias (the controller does not see the CPU's cached stores: on a
unit `lm_stats`, stored every 0.5 s, stayed stale for minutes) and is never a
multiple of 64 bytes (such a reply made the next control request return 0
bytes, measured on a unit), so `lm_ot` comes as 255 bytes and 1.
`tools/hw/load_meter.py` reads and summarises them from a unit;
`verify_usb_load_meter` checks the request under the port (not the cache or
the stale status, which only a unit shows; `docs/contributing/TRAPS.md`).

REMOTE's three vendor GETs (`modules/remote`; `RMT_RING` and `RMT_COMMAND` are `defsyms`, 0 without the module,
and a request then STALLs as stock does), each through the same uncached `lm_reply` and clamped to 255 bytes:
`0xc0/0x5a` returns the event block from byte offset `wValue`; `0xc0/0x58` (PEEK) returns memory at
`wValue:wIndex` inside `0x40000000..0x48000000`, `0x80000000..0x80008000` and `0x10000000..0x10100000`, any
other address STALLs; `0xc0/0x59` (COMMAND) runs `RMT_COMMAND` with the id in `wValue` and the argument in
`wIndex` and returns one byte, 0 taken and 1 refused. The ids and the block are in
[`modules/remote/README.md`](../remote/README.md); `tools/hw/ot_events.py` reads them.

#### Bus reset and session end

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
down (`usbmidi_rx_reset_shim`, `usbmidi_rx_sessend_shim`); this module's
shims replace those detours and call `usbmidi_rx_bus_end` after the
alt 0 request ([USB MIDI](#usb-midi), "Bus reset and session end").
Ignorato's MKII ran these shims in OCTABAM21 (9 Oct 2026): USB MIDI transmit
came back after each of three replugs on macOS and Windows 10, which is the
`usbmidi_rx_bus_end` call. The alt 0 request itself is measured under the
port only. On the session-end path the frame ISR's `audio_ep3_flush` runs
with USBCMD.RS already clear; the port's flush completes at once, so that
case is unmeasured.

### Ground

| what | where |
|---|---|
| code | DRAM unit `usbaudio` |
| rings | 1,036 × 88 B reserved (1,024 frames of `usb_frame_bytes` + the spill), the packets themselves, through the uncached alias (+`0x08000000`); 1,024 × 8 B (stereo sum), cached |
| DMA memory | dTDs 4 × 32 B in on-chip SRAM `0x800079c0`; full speed's `aud_bufs`, 4 × 960 B, through the uncached alias |
| hooks | `0x4001e91c` bus reset (USBSTS.URI handler), `0x4001e952` session end (OTGSC.BSVIS) (both USB MIDI's, replaced), `0x4001dd04` SET_INTERFACE, `0x4001d824` GET_INTERFACE, `0x4001de64` class requests, `0x4001d4b2` EP0 page fix, `0x4000d9a0` producer, `0x4001e606` USB ISR (USB MIDI's, replaced) |
| poke | `0x400e2004` device class → `ef 02 01` |
| descriptors | USB MIDI's `usbmidi_cfg` unit, generated with the audio function when an output stream is on |

## Audio in (IN)

The host's channels into the Octatrack's inputs, by the IN setting
(NEXT_BOOT, see *Settings* above):

| IN | host channels | DSP inject | packet |
|---|---|---|---|
| AB | 1/2 = inputs A/B; C/D stay on the jacks | `rx_inject.asm`, RX slots 2/3 | 96 B |
| CD | 1/2 = inputs C/D; A/B stay on the jacks | `rx_inject.asm`, RX slots 0/1 | 96 B |
| ABCD | 1–4 = inputs A–D | `rx_inject.asm`, all four slots | 192 B |
| OFF (the default) | no host -> device stream | no inject | -- |

Until 6 Oct 2026 each was a module of its own (USB AUDIO IN AB, IN CD, IN
ABCD); each remix's image is byte-identical to the one it built with those
modules. The sections below describe AB; *Inputs* has CD and ABCD.

A stereo feed from the host into inputs A/B.

The Mac sends a stereo pair, 24-bit at 44.1 kHz, over UAC2 on EP3 OUT, and
it arrives on the Octatrack's inputs A and B in place of the jacks. Inputs C
and D stay on the jacks. When the stream is closed, A and B are the jacks
again. High speed only.

Bryan T's USB AUDIO OUT (usbin-test, 26 Sep 2026: four channels into A–D,
draft PR #468, then PR #495 as USB AUDIO IN) cut to a stereo pair and moved
onto the build's placed-section path, 28 Sep 2026. The USB endpoint keeps
USB's own host-centric name, EP3 OUT.

### Open

- This stereo form on a unit: `tools/hw/usb_probe.py` sustained and churn,
  then a host → A/B → recorder take.
- The MKI report above: half-speed playback and CoreAudio restarts, the
  drain rate under `usb_probe.py` on that unit.
- Beside OUT TRACKS or OUT TRACKS MAIN CUE on hardware: before the crossbar setting the
  twenty-channel EP3 IN stream beside EP3 OUT lost packet tails under load;
  the setting cured them with the four-channel pairing and the larger
  pairings have not been run since. `usb-io-tracks-main-cue-ab` pairs it with OUT TRACKS MAIN CUE.
- Packet buffers in SDRAM through the alias with USB CROSSBAR on.
- Latency lever 2 above, after the unit measurement.
- The skipped closed-stream transfer (5 Oct 2026) on a unit: what it
  saves per frame with no host (not measured; Bryan T's 4 Oct takes all
  streamed), and that the jacks stay live across open/close. Port only so
  far: `verify_usb_in`, `verify_set` with the IN remixes.

### How it works

**Descriptors** (`modules/usb/descriptors.py`, `with_in`):
- AudioStreaming interface 5, alt 0/1, with EP3 OUT: 2 ch × 24-bit in 4-byte
  subslots, front left / front right, 96 B every 250 µs. Iso asynchronous,
  fed by IT `0x13` → OT `0x14` on the one clock.
- EP3 OUT is the only free endpoint (EP1 mass storage, EP2 MIDI, EP3 IN
  audio), so there is none for explicit feedback. EP3 IN is marked as the
  **implicit-feedback** data endpoint (`bmAttributes 0x25`), and the host
  sizes each OUT packet from the IN stream's.
- It needs an output stream beside it for that feedback: EP3 IN is EP3
  OUT's implicit-feedback source, so the build refuses IN with every
  output off (brain.c usb_pair_ok; cfgsel forces IN off on a bad block).
- The full-speed configurations carry no interface 5: the unit serves the
  stream at high speed only, so a full-speed host is never offered one. One
  clamp (`cfg_len`) covers all four replies: a host asks for a
  configuration's own `wTotalLength`, so the shorter tables' zero pad is
  never requested.

**ColdFire** (`usbaudio_in.s`, a DRAM unit; `IN_CHANNELS` from `remix.inc`, shared with [IN CD](#cd) and [IN ABCD](#abcd)):
- `in_setiface_shim`, a detour after usbaudio's SET_INTERFACE shim:
  interface 5 alt 0 or 1 records the alt setting and ACKs; any other alt
  STALLs. usbaudio.s answers GET_INTERFACE(5) from the same byte
  (`USB_IN` in its `remix.inc`).
- Bus reset and session end: `in_alt` is cleared by usbaudio's
  `audio_reset_shim` (`0x4001e91c`, the USBSTS.URI handler) and
  `audio_sessend_shim` (`0x4001e952`, the OTGSC.BSVIS session end), which
  the audio path carries with IN on (`USB_IN`). Before
  them, a cable pull or a host crash with the stream open left `in_alt =
  in_running = 1`, `in_build` underran, and `rx_inject` wrote zeros over
  the module's jacks until a host sent SET_INTERFACE(5, 0) (USB 2.0
  9.1.1.5: alternate setting 0 after a reset). State 7 sees `in_alt = 0`
  and brings EP3 OUT down within one frame. Port only: `verify_usb_in` runs
  3 (URI) and 4 (session end); no unit has had a reset or a pulled cable
  with this build. The flush `in_down` issues runs with USBCMD.RS already
  clear on the session-end path; the port's flush completes at once, so
  that case is unmeasured.
- `in_state7_shim`, a detour on the frame-transfer state machine's state 7
  (`0x40004bc0`). It is the one owner of EP3 OUT:
  - brings it up and down;
  - retires completed dTDs into a 1,024-frame ring;
  - self-heals the queue;
  - then runs a **second eDMA transfer** per DSP frame to core 0: 96
    halfwords (a pair) or 160 (ABCD) to `$6320`, which the DSP's host-DMA
    mask lands at `r6 + $320` of the bank the frame works in. Two passes,
    each a flag word then, flag 1, 16 × (hi, lo) for two channels, hi =
    sample[23:8], lo = sample[7:0]: the CD pass (CD, ABCD: C, D) and the AB
    pass (AB, ABCD: A, B). A flag of 0 has no data after it.

  The stock frame-IRQ unmask runs on the second visit, our transfer's
  completion. While the stream is closed the transfer runs until four
  blocks with both flags 0 have completed (the DSP reads the block from its
  working bank and the banks alternate per frame, so one zero block clears
  one bank: `verify_usb_in` saw host words in every other block with a
  single one), then is skipped and the first visit runs the stock state 7
  itself (since 5 Oct 2026; before that every frame). `in_seconds` counts
  transfers, so it stops rising while closed.
- Cushion `IN_TARGET` = 96 frames (2.2 ms; 384 frames, 8.7 ms, until 28 Sep 2026).
- The **dTDs and packet buffers are in on-chip SRAM** at `0x80007c00`, and
  the EP0 reply buffer at `0x80007f80`, declared as `Claims.sram`; see
  *SRAM*.
- `in_ctrl_shim`, a detour on the EP0 stall store (`0x4001de6e`), answers
  vendor request `0x56` with the fifteen counters.

**DSP** (`rx_inject.asm`, 29 words on payload A, one inject for every IN value):
- Placed by the build in the donor region like any effect, with no dispatch
  entry: P:`0x88`'s `move r2,x:>$204` becomes `jsr >inject`
  (`schema.DspHook`) and the inject replays it. The ledger refuses a second
  section on the site.
- The CD pass writes slots 0/1 (inputs C/D) of the current RX block
  (`X:$202`), the AB pass slots 2/3 (A/B); a slot no pass writes is the
  jack's. Every stock
  reader of the block, the core 0 → core 1 handoff and the read-back the
  recorder takes included, runs after P:`0x88` in the frame, so one inject
  serves both cores and the recorder (`out/dsp/payload_A.asm`).
- Each sample is joined from its hi/lo halfwords with one `insert` and
  stored with `(r1)+`, and one outer `do #2` runs both passes: 9
  instructions a sample in the loop, 15 before (21 Oct 2026). Bit-exact
  against the previous inject in the emulator over every IN value. On
  Bryan T's MKII (21 Oct 2026, `usb-io-main-cue-abcd`, OCTABAM1 against
  OCTABAM2 built from main), `tools/hw/usb_in_tones.py` reads the same on
  both: each input at unity on its own side, the other side below -178 dB,
  the rest within +-1.5 LSB. Both carry a DC offset on MAIN R (about -410
  LSB, -86 dBFS; MAIN L under 10) while the host sends zeros: added after
  the inject, source not read. The other forms have a stock site in payload A or
  ran on Bryan T's unit; the source lists them.

**USB CROSSBAR** is required: without it the controller's 16-byte RX FIFO
loses packet tails under a busy project ([Crossbar](#crossbar)
has the measurement).

### The other IN values

#### CD

A stereo pair from the host into inputs C/D in place of the jacks
(host channel 1 = C, 2 = D; A/B stay on the jacks). High speed only, 24-bit,
96-byte packets every 250 µs.

The same ColdFire unit as USB AUDIO IN AB
(`usbaudio_in.s`, `IN_CHANNELS = 2`), the same hook sites, the same
counters on vendor request `0x56`; only the DSP inject differs
(the CD path: slots 0/1 of the RX block instead of 2/3). The AB README has the design, the
measurements and the open items; `verify_usb_in` checks this variant's
slots (coded on its own, zero on the others) under the port.

Requires an output stream (the 250 µs shapes). One IN value per boot
(shared detour sites).

#### ABCD

Four channels from the host into inputs A-D in place of the jacks
(host channels 1-4 = A, B, C, D). High speed only, 24-bit,
192-byte packets every 250 µs.

The same ColdFire unit as USB AUDIO IN AB
(`usbaudio_in.s`, `IN_CHANNELS = 4`), the same hook sites, the same
counters on vendor request `0x56`; only the DSP inject differs
(the ABCD path: all four slots, 49 words; the four-channel form Bryan T's usbin-test ran on his MKII, build 16, 27 Sep 2026, there poked into SPATIALIZER's words). The AB README has the design, the
measurements and the open items; `verify_usb_in` checks this variant's
slots (coded on its own, zero on the others) under the port.

Requires an output stream (the 250 µs shapes). One IN value per boot
(shared detour sites).

### SRAM

`0x80007c00`–`0x80007dff` holds the four dTDs and their 96-byte packet
buffers, `0x80007f80`–`0x80007fbf` the EP0 reply. Evidence that the top
1 KB is free (Bryan T, 26 Sep 2026):
- The stock image's highest static SRAM use is the 768-byte buffer at
  `0x80007574` (`0x40098890`), ending `0x80007874`.
- No module touches anything above `0x80006907`.
- Under the port, nothing touches `0x80007874`–`0x80007fff`: boot, frames
  and USB streaming, and a busy project via `tools/verify/verify_set.py
  --extra "--touch-map 0x80000000,0x8000=…"` plus
  `tools/verify/sram_census.py`.
- RAMBAR1 is `0x80000235`, so the backdoor is on for bus masters.

SRAM is not cached, so no alias is needed. Packet buffers in SDRAM through
the uncached alias (usbaudio's pattern) with USB CROSSBAR on has not been
measured; SRAM alone did not cure the lost tails, the crossbar setting did.

### Counters

Vendor request `0xc0`/`0x56` returns fifteen big-endian longs:
produced, consumed, pkts, lastn, lastfill, underruns, overruns, reprimes,
bad, frames, seconds, minfill, maxfill, err, partial.
`tools/hw/usb_counters.py --in` reads them from a unit; `verify_usb_in`
reads them under the port. `tools/hw/usb_probe.py` reads both rings'
counters through a host session and prints a verdict.

### Ground

| what | where |
|---|---|
| code | DRAM unit `usbaudio_in`; DSP section `rx_inject.asm`, payload A's donor region, 29 words |
| hooks | `0x4001e91c` bus reset and `0x4001e952` session end (usbaudio's shims, below), `0x4001dd0a` SET_INTERFACE (after usbaudio's), `0x40004bc0` frame transfer state 7, `0x4001de6e` EP0 stall store; DSP P:`0x88` (`DspHook`) |
| ring | 1,024 × 8 B, the unit's data |
| DMA memory | dTDs `0x80007c00` (128 B), packet buffers `0x80007c80` (384 B), EP0 reply `0x80007f80` (64 B): `Claims.sram` |
| host-port buffer | `SRAM_TX` `0x80007880` in on-chip SRAM (since 27 Oct 2026; `in_tx` in SDRAM through the uncached alias before) → core 0 X bank +`$320`..+`$380` |
| descriptors | USB MIDI's `usbmidi_cfg` unit, interface 5 in the high-speed configurations |

## Crossbar

The USB controller bursts over the crossbar and is served first on the
SDRAM and SRAM-backdoor slaves. Written once at the stock USB controller
init (`0x4001e030`) and left on.

| register | stock | this module | meaning |
|---|---|---|---|
| SCM BCR `0xfc040024` | `0` (reset; nothing sets it) | `0x3ff` | USB bursts to and from every slave |
| XBS PRS2 / PRS4 | `0x65403210` (USB level 6 of 7) | `0x60504321` (USB level 0) | master priority on SDRAM (slave 2) and the SRAM backdoor (slave 4) |
| XBS CRS2 / CRS4 | `0x110` (round robin) | `0x10` (fixed, park on last) | arbitration mode |

### Open

- CAPTURE and card writes under this priority on a MKI (nordseele's review
  of PR #468, 27 Sep 2026); DISK MODE ran on erreye's MK1.
- Whether a MK1 under a busy project shows the MKII's bad OUT packets with
  BCR 0: erreye's remix has no USB AUDIO IN, so their A/B streamed
  device to host (EP 0x83) only; the MKII's errors were on host-to-device
  packets.
- The stock DELAY on eight tracks with Flex playback (SDRAM-heavy DMA)
  under USB-first arbitration: four tracks with seven voices measured
  clean on the ISR mean (above); eight tracks, and the routine's own
  eDMA waits, not.

### Why

In device mode the controller has one 16-byte RX FIFO (MCF54455RM 10.4.3),
about 270 ns of slack at 480 Mbit/s. With BCR 0 it is emptied one beat at a
time; under a busy project it overflowed near the end of an isochronous OUT
packet and the controller flagged a transaction error (CRC), 2 to 12 bytes
short. Stock's own USB traffic is bulk and retried, so stock never showed
it.

### Ground

| what | where |
|---|---|
| code | DRAM unit `usbcrossbar`, 10 instructions |
| hook | `0x4001e030`, the USB controller init's `movel #0x08000000,%d0`, replayed |
