# SEND

The bus client. Two knobs, one per bus: `-DEL` into BusDelay, `-VRB` into
BusVerb. Driving the wrong one renders silence, which reads as a broken
algorithm — they are separate knobs on separate accumulators.

It never writes the audio buffer, only taps it, so a SEND with both levels at
zero is indistinguishable from "no effect". That is why a fresh, unassigned
track (FX2 id 0) is aliased to this rather than to NONE: unlike NONE it does
the per-block bus housekeeping, so making every unassigned track a SEND
removes the "first track set to NONE stalls the bus" hazard by construction.

It is also the default **fallback**: an id a remix does not implement resolves
here, so selecting a missing effect makes the track a send.

## The auto-gain, and the thing to know about it

The accumulator is divided by the number of registered clients (1/√N), so
eight senders drive a server as hard as one. The consequence worth knowing:
**a quiet sender turns the loud sender's reverb down.** Three senders, two of
them 10–15 dB quieter, measured 4.8 dB below the loud sender alone.

A client that registers and then contributes nothing steals everyone else's
level, which is why every level knob gates its own registration.

See [`docs/XBUS.md`](../../docs/XBUS.md).
