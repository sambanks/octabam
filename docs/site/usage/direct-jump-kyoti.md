Changes pattern immediately. A cued pattern takes over on the next step,
locked to the master clock: it plays where it would be had it been
running since the last restart, whatever its track lengths, scales or
master settings. The last restart is PLAY, or the last normal pattern
change (Direct Jump off, a chain, the arranger): after one, a jump lands
in phase with the pattern that started there.

## Operation

Press [PTN] + [YES] to switch it on or off. It is OFF at every power-on.

## What changes at a jump

The new pattern's Part and START SILENT change as on a stock pattern
change, but each track's sound settings take over with that track's first
trig that actually plays. A sample still ringing from the old pattern keeps
its settings until then.

With SILENCE TRACKS on, a track the jump silences fades out just before the
step instead of being cut on it, so it does not pop.

The last MIDI Program Change sent always names the pattern that plays. The
arranger and chains are untouched.

## Trig conditions

Trig conditions carry on as if the new pattern had been playing since
the last restart: PLAY, or the last normal pattern change. A `1:2` or `1:4` trig stays in step across a jump, a held [FILL]
survives it, and a PRE trig right after a jump plays. A track reloaded
from the card after a jump counts from the same restart, so it stays in
step too.

## Not with CHAIN AFTER: DIRECT

This is not the same as the stock DIRECT chain setting (CHAIN AFTER: DIRECT).
Both change when a cued pattern takes over; use one or the other.
