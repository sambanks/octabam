Direct Jump switches patterns immediately. When you cue a pattern, it takes
over on the next step, locked to the master clock. It plays from the position
it would have reached had it been running since the last restart, regardless of
its track lengths, scales, or master settings. A restart happens when you press
PLAY or on any normal pattern change (with Direct Jump off, in a chain, or in
the arranger), so subsequent jumps stay in phase with the pattern that started
there.

## Operation

Press [PTN] + [YES] to toggle Direct Jump on or off. It is always OFF when the
unit powers on.

## What changes at a jump

The new pattern's Part and START SILENT settings apply just as they do on a
stock pattern change, but each track's sound settings only take effect on that
track's first trig that plays. Any sample still ringing from the previous
pattern keeps its settings until then.

With SILENCE TRACKS enabled, a track silenced by a jump fades out just before
the step instead of cutting abruptly, avoiding clicks or pops.

The last MIDI Program Change sent always matches the active pattern. Chains and
the arranger are unaffected.

## Trig conditions

Trig conditions continue as if the new pattern had been playing since the last
restart (PLAY or the last normal pattern change). Conditions such as `1:2` or
`1:4` stay in sync across a jump, a held [FILL] remains active, and a PRE trig
immediately after a jump still plays. A track reloaded from the card after a
jump counts from the same restart, so it stays in sync as well.
