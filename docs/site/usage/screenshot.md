The unit answers Elektron's screenshot SysEx request with the 128 × 64 screen, so
[elektron-screen-tool](https://github.com/Fadedlimes/elektron-screen-tool) (`screendump`) can show it on a
computer, for example as an OBS source.

## Operation

Connect the unit to the computer over USB MIDI (an image with the USB module) or DIN MIDI. Point `screendump`
at the Octatrack's ports with the instrument id `10 00` (`--probe-id 10 00`; `05 00` is answered too). The
reply goes back on the transport the request came on.

## Wire format

| | |
|---|---|
| Request | `F0 00 20 3C 10 00 00 00 01 00 00 04 F7` (13 bytes) |
| Reply | 1,194 bytes: `F0 00 20 3C 10 00`, 7-bit-encoded body, `F7` |
| Body | msgId, replyTo, cmd `84`, version 1, width 128, height 64, length 1024, 1,024 pixel bytes |

The picture is the frame the panel was last sent, so MIXER, the PROJECT menu, SETUP windows and popups are in
it, not only the page underneath.

On USB the reply is one 1,592-byte EP2 IN transfer. On DIN it takes 0.38 s at 31,250 baud, so about 2.6
screens per second; USB has no such limit.
