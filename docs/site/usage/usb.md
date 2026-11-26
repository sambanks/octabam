Connect the Octatrack to a computer for USB MIDI and audio. USB storage mode
(DISK MODE) works as in stock OS. USB MIDI pauses while DISK MODE is on.

The computer sees one device with MIDI in and out, an audio input (the
Octatrack's output) and, with IN set, an audio output (the computer's
channels into the Octatrack's inputs). Audio is 44.1 kHz, 24-bit (UAC2).

## Settings

![BRAIN > SETTINGS, the USB group: CUE, IN and MAIN.](../../img/usb/settings.png)

*PROJ > BRAIN > SETTINGS, the USB group. `*` marks a value that takes effect
at the next boot.*

| Setting | Default | Values | What it does |
|---|---|---|---|
| TRACKS | PRE | OFF, PRE, POST | Sends the 16 track channels to the computer: tracks 1 to 8, track N on channels 2N-1 and 2N. PRE is before the track's LEVEL, the crossfader, MAIN volume and the master effects. POST is after each track's own LEVEL, mute and solo; MAIN volume is not applied. |
| MAIN | ON | OFF, ON | Sends the MAIN mix (2 channels), the signal sent to the MAIN outputs. It includes LEVEL, the crossfader, MAIN volume and the master effects. |
| CUE | ON | OFF, ON | Sends the CUE mix (2 channels). |
| MASTER | OFF | OFF, ON | Sends track 8's left and right (2 channels). |
| IN | OFF | OFF, AB, CD, ABCD | Takes the computer's channels in as Octatrack inputs. AB: computer channels 1 and 2 are inputs A and B, and C and D stay on the jacks. CD: the same on C and D. ABCD: computer channels 1 to 4 are inputs A to D. |
| MIDI | ON | OFF, ON | USB MIDI in and out. With MIDI OFF the computer sees storage and audio only, and the audio interface numbers change. |

The channels the computer receives are the ones switched on, in the order
TRACKS, MAIN, CUE, MASTER. The counts are 0, 2, 4, 6, 16, 18, 20 or 22
channels. With the defaults it is 20: channels 1 to 16 are the tracks, 17 and
18 are MAIN, 19 and 20 are CUE. At USB full speed the stream is two channels,
the stereo sum.

IN needs at least one of TRACKS, MAIN, CUE or MASTER switched on, because the
computer's stream is timed from the Octatrack's output. If none is on,
changing IN shows **IN NEEDS AN OUTPUT STREAM** and IN stays OFF. IN is
available at USB high speed only.

### Changing a setting

1. Open **PROJ > BRAIN > SETTINGS**. The USB group lists CUE, IN, MAIN, MASTER,
   MIDI and TRACKS.
2. Move to a row with **UP** and **DOWN**.
3. Press **YES** to step through the values, or **LEFT** and **RIGHT** to step
   down and up, stopping at the ends.
4. Leave SETTINGS: `REBOOT TO APPLY CHANGES` appears. Switch the Octatrack off
   and on; the USB values take effect at the next boot, and the computer sees
   the new device when it starts. The values are kept in `BRAIN/card.work` on
   the card.

![The end of the USB group: TRACKS, with * AT NEXT BOOT under the list.](../../img/usb/settings-end.png)

## USB MIDI

USB MIDI provides MIDI input and output over USB, mirroring the DIN ports. The
sequencer, time stretch, LFOs, and effects all follow USB MIDI clock.

Output bursts, such as the 283 CCs of a CC 61 dump, are queued and sent in
order. Up to about 4 KB can buffer while waiting for the computer to read;
messages past that limit are dropped and counted in the USB tab. (In earlier
builds, bursts longer than 256 bytes lost their tail.)

The Octatrack follows one clock source at a time, with DIN taking priority.
While MIDI clock is arriving on DIN, USB clock, START, STOP, CONTINUE, and song
position messages are ignored. USB takes over about one-sixth of a second after
the last DIN clock arrives. (In earlier builds, receiving both clocks together
doubled the tempo.)

USB MIDI is disabled while USB DISK MODE is on, including clock, and incoming
USB MIDI is not received during that time. DIN MIDI is unaffected. In earlier
builds with CLOCK SEND on, files copied off the card in DISK MODE could come
back with 4 bytes corrupted at 64 KB boundaries. Any file copied that way and
written back to the card retains those corrupted bytes, so re-copy anything
transferred with CLOCK SEND on and compare it against the card.

## Audio in

When IN is enabled, the computer's channels feed the Octatrack's inputs as
described under IN above. Whenever the computer's audio stream is closed, the
physical input jacks remain active.

## Reading USB activity

![BRAIN performance: USB counters.](../../img/usb/performance.png)

*PROJ > BRAIN > PERFORMANCE, the USB tab.*

The USB tab counts audio underruns and overruns and dropped MIDI output
messages. It reads **NOT IN THIS IMAGE** when the image has no USB module.
