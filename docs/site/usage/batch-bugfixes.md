Three fixes to stock behaviour: a MIDI track's Plays-Free trig could
play a garbage scale byte, a pattern whose only content is parameter locks
showed as empty, and
a Part change could carry over state from the previous Part. There is
nothing to operate and nothing on the panel.

## Pattern LEDs

A pattern whose only content is parameter locks, trigless locks with a
locked parameter included, lights its LED under `[PTN]`, and its bank's
LED under `[BANK]`. A trigless lock with nothing locked lights neither.
