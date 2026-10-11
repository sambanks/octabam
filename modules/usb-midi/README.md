# `usb-midi` — USB MIDI

Class-compliant USB-MIDI in and out on the Octatrack's own USB port,
mirroring the DIN ports. markandrus's work ([octemu](https://github.com/markandrus/octemu),
`custom/usb-midi.py` + `custom/coldfire/usb-midi.s` at `6a9ff68`, MIT),
carried onto octabam's DRAM platform.

## Measured

Under the ColdFire port (25 Sep 2026), `make check REMIX=usb`, `verify_usb`:

- enumerates at high speed as Elektron 1935:0002, three interfaces, 124-byte
  configuration; INQUIRY and TEST UNIT READY still answered by the stock
  mass-storage stack;
- two channel messages sent to EP2 OUT → six bytes into the firmware's
  MIDI receive FIFO (`midi_rx_fifo_head` `0x46100b80`, six writes from
  `midi_rx_enqueue`);
- the firmware's own `midi_send` on a note-on → one event packet `09 90 3c 64`
  on EP2 IN.

His build from the same stock bytes, tested first under the port with his
own patch scripts, behaved the same (the ISR shim ran nine times, the
decoder once, the same six FIFO writes).

## Receive path (port only, 5 Oct 2026)

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

`usbmidi_rx.s` (octabam's; `usbmidi.s` is unchanged and still matches his
build) takes over the SET_CONFIGURATION and usb_isr detours and hands on to
his shims:

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

## Clock (6 Oct 2026)

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
  before it is enqueued. `verify_usbmidi_clock`: two USB runs at 50 and
  40 ms per tick read 1200 and 1498 (want 1200 and 1501); before the change
  both read 2400, the DIN run's tempo.
- DTIN0's clock is inferred: the handler's constant gives BPM × 24 only for
  256 fs (11.2896 MHz). The port counts DTCN0 at that rate (`rtos.h`);
  before this change it held at 0 and no MIDI clock tempo ran under the port.

## Bus reset and session end (9 Oct 2026)

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

Under the port (`verify_usbmidi_replug`, the `usb-midi` remix; `ot_emu`'s
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

`usbmidi_rx.s` now takes EP2 down on a bus reset (`0x4001e91c`, the
USBSTS.URI handler) and on session end (`0x4001e952`, OTGSC.BSVIS, before
the stock code clears USBCMD.RS), and again at SET_CONFIGURATION before
EP2_INIT: `usbmidi_up` and `usbmidi_tx_busy` cleared, the queued bytes
dropped, both EP2 directions flushed (wait for ENDPTPRIME, flush, repeat
while ENDPTSTAT shows a bit, every wait bounded), both overlay tokens
cleared, any EP2 completion dropped. The two sites are USB AUDIO's too:
with a USB AUDIO OUT module in the remix its `audio_reset_shim` and
`audio_sessend_shim` override these detours and call `usbmidi_rx_bus_end`.
After the change all 21 of `verify_usbmidi_replug`'s checks pass (five fail
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

## On the unit

Image 64, `usb-audio`, Sam's MKII, 25 Sep 2026:

- Enumerates on macOS as a MIDI port "Elektron Octatrack DPS-1", beside
  the USB AUDIO input.
- Receive: 896,760 messages (7,170/s, notes + CCs on channel 16) and then
  1,471,080 messages (7,950/s, 185 s) sent into the unit, with the audio
  stream running, without a stall or a change in the audio stream
  (`modules/usb-audio-out/README.md`, the image 64 takes).
- No USB MIDI transmit measurement from the unit is recorded.

Also carried on Tim Hastie's MKI (`octatrick-usb`, OCTATRICK9, 26 Sep 2026),
Bryan T's MKII (`usb-lean` image 90, 25 Sep 2026) and Sam's MKII as image 88
(`bottleservice`, 27 Sep 2026); none of those runs measured MIDI itself.
The `usb-midi` remix (this module on the stock effects) has not been flashed.

## Open

- Not measured: clock jitter over USB against DIN (bulk transfers have no schedule; the
  gate sends one `0xF8` per transfer, a host can bunch several into one
  packet, and each then gets a near-zero interval); a CC flood against the
  256-byte queue; DISK MODE entered with a MIDI session open; Windows.

## Gates

- `verify_usb` (`make check REMIX=usb`).
- `verify_usbmidi_rx` (image stage): the four packets of "Receive path",
  parsed bytes compared with sent bytes, and each packet accepted whole by
  the dTD. Five of its nine checks fail on the code before this change.
- `verify_usbmidi_replug` (image stage): the first connection, four cable
  pulls (two with a clock transfer in flight, two idle), each followed by
  `plug`, a reset and an enumeration, and a bus reset with the cable in; a
  note-on and a clock byte must arrive on EP2 IN after each, nothing queued
  for the old session may go out, EP2 IN must not be primed between a
  session end and the next SET_CONFIGURATION, and EP2 OUT must still
  deliver. Five of its checks fail on the code before the bus-reset and
  session-end shims.
- `verify_usbmidi_clock` (image stage): DIN clock, then USB clock at two
  other rates, under `--interactive` with each byte handed over at a known
  sample; `0x80001818` within 1% of the tick spacing's BPM × 24 after each
  run. Both USB checks fail without the timestamp.

## What it is

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
  MIDI uses, then re-primes (`usbmidi_rx.s`, see "Receive path");
- mirrors both senders into the encoder: `midi_send` (channel messages)
  and the priority byte sender (clock, transport). Messages are queued in
  a 256-byte accumulator behind one transfer; a message that would
  overflow it is counted in `usbmidi_tx_drops`, never sent corrupt.

Nine detours, four descriptor-pointer rewrites, no pokes. The `usbmidi`
unit is his file verbatim (two of the detours reach `usbmidi_rx` first, and two more, bus reset and session end, are `usbmidi_rx`'s own), and the build proves it: every build re-links
it at his zone address `0x400d24f0` and compares with the 1,124-byte blob
his `usb-midi.py` produced from our stock bytes (`Linked.reference`, the
port-is-a-proof rule). The clamps are a second unit (`clamp.s`, his
usb-audio.s shims reading `cfg_len`).

## Ground

| what | where |
|---|---|
| code + queues | DRAM units `usbmidi` (1,124 B, his bytes), `usbmidi_rx` and `usbmidi_clamp` in the platform reserve |
| descriptors | DRAM unit `usbmidi_cfg` (4 × 124 B, or 4 × 250 B with a USB AUDIO module) |
| hooks | `0x4001d9ca` `0x4001daec` `0x4001e606` `0x40010bc8` `0x400108b0` `0x4001d858` `0x4001d896` `0x4001e91c` `0x4001e952` (the last two overridden by a USB AUDIO OUT module, which calls `usbmidi_rx_bus_end`) |
| pointer rewrites | the responder's four `pea` operands `0x4001d882` `0x4001d88a` `0x4001d8c0` `0x4001d8c8` |
| firmware memory it uses | the firmware's own EP2 dQHs, dTDs and buffers (`0x4ec94900..`, `0x4ecc8000`, `0x4ecc9000`; the RX buffer's 4 KB page has no other reference in the image) |
