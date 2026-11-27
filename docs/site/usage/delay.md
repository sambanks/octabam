DELAY is the stock Echo Freeze delay: a 4-second stereo delay line per track with feedback, a bandpass filter in the feedback loop, ping-pong routing, tape-style pitch glide, tempo sync, and a repeater mode (LOCK). In Octabam Bus, it is permanently assigned to the master track's FX2 slot for beat-repeat performance.

## Access

Load DELAY in FX2 on any track just as on a stock unit. In Octabam Bus, DELAY is locked to T8's FX2 slot, while all other tracks use SEND in FX2.

## Operation

- TIME sets the delay length in 256th notes, where 64 equals one beat (four 16th notes). When SYNC is enabled, TIME follows the project tempo; when SYNC is off, it runs freely.
- FB controls feedback, VOL sets the delay output volume, and SEND sets how much input signal feeds into the delay.
- BASE and WDTH filter the feedback loop: BASE sets the high-pass cutoff, and WDTH sets the low-pass cutoff relative to BASE.
- Enabling X switches the delay to ping-pong mode.
- Enabling TAPE glides smoothly between delay times when TIME changes; disabling it jumps immediately.
- DIR controls the dry level; at 0, only the delayed signal is heard.

## The repeater (lock)

Turning LOCK on converts the delay into a buffer repeater. With FB at 127 and SEND at 0, the captured buffer loops indefinitely; lower FB values fade the repeats out gradually, and TIME controls the repeat length. Raising SEND above 0 stops the loop. PASS controls whether the dry signal passes through while LOCK is active: ON (1) mixes dry audio in, while OFF (0) outputs only the looping buffer (in which case VOL no longer affects the buffer level).

On T8 in Octabam Bus, this acts as a master beat repeat: feed a beat into the delay with SEND, then turn LOCK on with SEND at 0 and PASS at 0 to loop whatever was captured before locking.

## Parameters

| Page | Knob | Range | Default | What it does |
|---|---|---|---|---|
| 1 | TIME | 0–127 | 47 | Delay length in 256th notes; 64 = one beat |
| 1 | FB | 0–127 | 0 | Feedback |
| 1 | VOL | 0–127 | 127 | Delay output volume |
| 1 | BASE | 0–127 | 0 | High-pass filter on the feedback loop |
| 1 | WDTH | 0–127 | 127 | Low-pass filter on the feedback loop, relative to BASE |
| 1 | SEND | 0–127 | 0 | Input send level into the delay |
| 2 | X | OFF / ON | OFF | Ping-pong mode |
| 2 | TAPE | OFF / ON | ON | Pitch glide when changing delay time |
| 2 | DIR | 0–127 | 127 | Dry mix; 0 outputs delay only |
| 2 | SYNC | OFF / ON | ON | Tempo sync |
| 2 | LOCK | OFF / ON | OFF | Repeater mode |
| 2 | PASS | OFF / ON | OFF | In LOCK mode: ON (1) mixes dry in, OFF (0) outputs buffer only |
