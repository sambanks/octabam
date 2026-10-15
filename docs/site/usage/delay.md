## What it does

Stock's Echo Freeze delay: a 4-second stereo loop per track, with
feedback, a band filter on the loop, ping-pong, tape glide, tempo sync
and a repeater (LOCK). In octabam-bus it is the master track's FX2,
there for its beat repeat.

## Where to find it

FX2 on any track, as on a stock unit. In octabam-bus: T8's FX2, locked;
every other track's FX2 is SEND.

## How to use it

- TIME is the delay length, in 256th notes: 64 is one beat (four 16th
  notes). With SYNC on it follows the tempo; with SYNC off it is free.
- FB is the feedback, VOL the delay output volume, SEND how much of the
  signal is sent to the delay.
- BASE and WDTH filter the loop: BASE the high-pass, WDTH the low-pass
  relative to BASE.
- X on makes it a ping-pong delay.
- TAPE on glides between delay times when TIME changes; off jumps.
- DIR is the dry mix; at minimum only the delay signal is heard.

## The repeater (LOCK)

LOCK on makes the delay a repeater: with FB 127 and SEND 0 the buffer
repeats endlessly; lower FB fades out gradually. TIME sets the repeat
length. Any SEND above 0 stops the repeats. PASS routes the dry signal
while LOCK is on: 1 mixes it in, 0 plays only the buffer (and VOL then
does not affect the buffer signal).

On T8 in octabam-bus this is the beat repeat: send a beat into the
delay, then LOCK on with SEND 0 and PASS 0. The buffer holds whatever
was sent in before the lock.

## Knobs

| page | knob | range | default | what it does |
|---|---|---|---|---|
| 1 | TIME | 0–127 | 47 | delay length, 256th notes; 64 = one beat |
| 1 | FB | 0–127 | 0 | feedback |
| 1 | VOL | 0–127 | 127 | delay output volume |
| 1 | BASE | 0–127 | 0 | high-pass on the loop |
| 1 | WDTH | 0–127 | 127 | low-pass on the loop, relative to BASE |
| 1 | SEND | 0–127 | 0 | how much is sent to the delay |
| 2 | X | OFF / ON | OFF | ping-pong |
| 2 | TAPE | OFF / ON | ON | glide between delay times |
| 2 | DIR | 0–127 | 127 | dry mix; minimum = delay only |
| 2 | SYNC | OFF / ON | ON | tempo sync |
| 2 | LOCK | OFF / ON | OFF | repeater mode |
| 2 | PASS | OFF / ON | OFF | in LOCK: 1 mixes dry in, 0 buffer only |
