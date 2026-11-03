# SCREENSHOT

Answers Elektron's screenshot SysEx request on MIDI OUT with the 128 x 64 screen, so
[elektron-screen-tool](https://github.com/Fadedlimes/elektron-screen-tool) (`screendump`) can read the unit.

## Wire format

Request, 13 bytes: `F0 00 20 3C <id0> 00 00 00 01 00 00 04 F7`. `id0` is `05` (the OT's own) or `10`
(`screendump`'s default probe, the id the Digitakt, Analog Four MKII and Rytm MKII answer). The 7-bit body is
msgId:u16, replyTo:u16, cmd:u8 = `04`.

Reply, 1,194 bytes: `F0 00 20 3C <id0> 00`, the 7-bit encoding of msgId:u16, replyTo:u16 (the request's
msgId), cmd `84`, ver `01`, w `0080`, h `0040`, len `00000400`, 1,024 pixel bytes, then `F7`.

The pixels are the firmware's LCD plane (`0x46c7e0ea`) as it stands. The plane is already in the tool's
column-major order: 128 columns of two big-endian 32-bit words, row y at bit y, a set bit lit
(`docs/firmware/PANEL.md`).

## What stock does

Stock's SysEx entry (`0x40001918`) takes `F0 00 20 3C 05 00 <b6>` only for b6 in `0x50..0x73`; every other message
returns without a reply (tested on an OT MKII, OS 1.40C, over DIN with ids `05 00`, `05 01`, `00 05`: no reply).

## What the module changes

One jmp detour on that entry. A message that is not this request goes on to stock unchanged. The reply is
queued in the MIDI OUT ring the way `0x40010bc8` queues bytes, honours stock's MIDI OUT hold (`0x460ba978`),
and clears the running-status byte (`0x460ba988`) so the next channel message carries its status.

The reply goes back on the transport the request came on. `usbmidi_rx.s` (USB module) sets `usbmidi_rx_sysex`
when it enqueues an `F0`; the hook reads and clears it at every SysEx. On USB the 1,194 bytes go through the
firmware's USB-MIDI encoder (`0x4001d204`) in one call: one EP2 IN transfer of 1,592 bytes, after claiming
`usbmidi_tx_busy`. The USB symbols are weak, so an image without the USB module answers on DIN only. If the host
does not read EP2 IN, the reply is dropped after a bounded wait.

Cost: 558 B of code, 2,242 B `.bss`. The reply is 1,194 bytes; DIN takes 0.38 s per reply at 31,250 baud.
The msgId field is a counter in `.bss`, which the DRAM reserve does not zero.

## Tested

`tools/verify/verify_screenshot.py` under the port (23 checks): both ids draw one 1,194-byte reply on DIN; the
header fields; the pixels equal the plane and the PANEL.md reading; a wrong cmd, another manufacturer id and a
stock-range message draw none. In the `screenshot-usb` remix: a request as USB-MIDI events is answered on EP2 IN
only (1,592 bytes, pixels equal the plane), and a DIN request is still answered on DIN only.
`verify_usbmidi_rx` passes on that image. Not run on a unit.

## Open

- Hardware: the tool's own port matching on a real OT; `screendump` needs `Instrument("Octatrack", "OT", ident=(0x10, 0x00), width=128, height=64)` (or `--probe-id`).
- A request arriving on both transports at once is answered on the transport whose `F0` came first in the read-and-clear window.
- Cost at `--framerate 30` is not measured (DIN carries about 2.6 replies per second; USB is not rate-limited by the wire).
