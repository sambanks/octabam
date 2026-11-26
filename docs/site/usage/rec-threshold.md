REC THRESHOLD adds a recorder TRIG mode that waits for incoming audio: arm the
recorder, and recording starts automatically when the input crosses the
track's threshold, similar to the Digitakt 2.

## Access

1. Hold **FUNC** and press **REC AB** (RECORDING SETUP 1). Turn **TRIG**
   past ONE, ONE2, and HOLD to **THR**.
2. Hold **FUNC** and press **REC CD** (RECORDING SETUP 2). On a THR track,
   two parameters change: QREC becomes **LEV** and QPL becomes **IN**.
3. Play the input source, read **IN**, and set **LEV** a few dB below it.
4. To arm the track, hold **TRACK** and press **REC** (or press **REC** alone
   for the active track). While armed and waiting, the track's status icon at
   the screen edge blinks.

REC THRESHOLD and REC TRIG MUTE both modify the same part of the stock
firmware; HOOKS (see Behind the scenes) lets them share it.

## Operation

- LEV sets the threshold from -60 to -8 dB in 4 dB steps, then -6, -4, -2, and
  0 dB. It is saved per track with the Part. Switching TRIG to THR initializes
  LEV to -40 dB if it has not been set before.
- IN displays the live input level in dB (the loudest of inputs A–D), holding
  peaks for about 0.5 s before falling at about 29 dB/s, and reading `---`
  below -60 dB. Turning its knob has no effect.
- Recording starts as soon as the input reaches or exceeds LEV (so 0 dB can
  still trigger) and stops at RLEN as usual. When RLEN is set to MAX, press
  REC to stop recording. Arm the track again for the next take.
- Recording starts immediately without applying QREC, so quantization cannot
  cut off the initial attack that crossed the threshold.
- Pressing REC again while armed cancels the arm. Pressing REC while recording
  stops the take.
- An armed track is disarmed without recording if its TRIG mode is changed
  away from THR, or if the recorder is already running when the input arrives.
- While GRID RECORDING is active, stock REC keys do nothing inside RECORDING
  SETUP, so arm the track outside that screen.
- On tracks not set to THR, RECORDING SETUP 2 shows QREC and QPL and edits as
  on stock firmware.
- A Part saved with THR loads on stock 1.40C as TRIG HOLD, with its LEV value
  interpreted as QREC.
