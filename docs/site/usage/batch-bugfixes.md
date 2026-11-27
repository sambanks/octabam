This module applies three fixes to stock OS behavior: it stops a MIDI track's Plays-Free trig from reading a corrupted scale byte, ensures patterns containing only parameter locks do not appear empty, and prevents a Part change from carrying over state from the previous Part. These fixes run automatically with no settings or menu entries.

## Pattern LEDs

A pattern containing only parameter locks (including trigless locks that lock at least one parameter) lights its pattern LED under `[PTN]` and its bank LED under `[BANK]`. A trigless lock with no locked parameters does not light either LED.
