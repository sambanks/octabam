# Original 909 circuit review — 28 September 2026

## Implementation and scope

LPF uses an 88.2 kHz matched-pole RC discretization. It normalizes DC gain so AMP remains the volume control. Position 64 selects the calculated nominal cutoff; 0 bypasses; the remaining range is an intentional 500 Hz–18 kHz extension. The state tracks the signal even in bypass. No resonance or arbitrary master saturation is added.

The existing empirical 4 kHz voice pole remains separate: it softened an attack judged too sharp by the user. It is **not** claimed as a value read from the original schematic.

The 31-bit sequence advances at an approximate 300 kHz rate and averages three/four bit levels per internal sample before the existing noise-color pole. This is a reduced-bandwidth approximation, not an exact analog reconstruction. Each machine instance owns a generator; it does not reproduce the original shared generator's correlation with snare/tom voices. Its state and filter continue through silence. Quiet voice retirement no longer resets them. The trigger shaper discharges between hits rather than resetting its capacitor on every trigger.

The tonal VCO still resets at a hit. There is no random pitch wobble, arbitrary tolerance drift, added mains hum, or claimed hardware-measured leakage floor. Physical-unit recordings are still needed for those claims. 808 synthesis is unchanged by the 909-only output control.
