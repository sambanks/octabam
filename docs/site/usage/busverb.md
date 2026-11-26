BUSVERB is the bus reverb engine, permanently assigned to track 5's FX2 slot (locked so the FX2 chooser cannot replace it). It is an eight-line reverb featuring ROOM, PLATE, and BIG modes, modulated taps, shimmer, a gate, and mid/side width. It receives audio from every track's REV send as well as the bus delay's repeats via the DLY knob, and mixes its reverb tail onto track 5 alongside track 5's dry signal.

## Access

Track 5's FX2 page displays only DEL and REV. All other parameters are in the TEMPO window: press [TEMPO], then use LEFT and RIGHT to select the REVERB box.

## Adjust the sound

- On track 5, DEL sends track 5's dry signal into the delay, and REV sends it into the reverb.
- Across TIME 0–127, decay times span 0.87–3.9 s in ROOM mode, 0.9–4.4 s in PLATE mode, and 1.6–11.7 s in BIG mode.
- TONE combines low-pass and high-pass filtering on one knob: 0–64 acts as a low-pass filter, 64 is flat, and 64–127 acts as a high-pass filter.
- SHMR sets the shimmer amount, and SHFT chooses its pitch interval (-12, +5, +7, +12, +19, or +24 semitones).
- GATE is off at 0. Above 0, it cuts the wet signal 52 ms (GATE 1) to 784 ms (GATE 127) after the reverb input drops quiet, producing a 1980s-style gated reverb cutoff.
- DLY controls how much of the bus delay's repeats feed into the reverb: 0 runs both engines in parallel, and higher values send more delay repeats into the reverb tail.

## Parameters

| Page | Knob | Default | Function |
|---|---|---|---|
| 1 | DEL | 0 | This track's dry send into the delay |
| 1 | REV | 0 | This track's dry send into the reverb |
| 1 | SIZE | 100 | Scales the taps within the selected mode |
| 1 | SHMR | 0 | Shimmer amount; 0 is off |
| 1 | SHFT | +12 | Shimmer interval: -12 / +5 / +7 / +12 / +19 / +24 |
| 1 | WET | 127 | Wet level over the chain input |
| 2 | MODE | PLATE | ROOM / PLATE / BIG |
| 2 | TONE | 64 | 0–64 = low-pass, 64–127 = high-pass; 64 is flat |
| 2 | DIFF | 80 | Diffusion (allpass smear) |
| 2 | GATE | 0 | Gated cut after the input falls quiet: 52–784 ms; 0 is off |
| 2 | DLY | 127 | Delay repeats fed into the reverb; 0 runs both engines in parallel |
| 2 | TIME | 64 | Tail length |
