# ATA WRITE GUARD

Keeps the first PIO card sector and its pointer/count update in stock's
existing interrupt critical section. ColdFire only; no DSP code or state.
Author: Sam Banks. Port-proven; not tested on hardware.

## The observed failure

During a DSP-enabled project load, stock sent a one-sector WRITE to LBA
2301 and was preempted at `0x40014d34`, after the final word but before
advancing `0x46c8c594` and decrementing `0x46c8c592`. The completion
interrupt ran with the count still 1. The card had completed the command
(status `0x50`, DRQ clear), so the handler polled `0x4001551e..26` forever.
The engine could not resume to finish the bookkeeping.

Measured on 15 Oct 2026 while checking the USB merge: BUILD=0 failed,
BUILD=1 passed despite only server-name bytes changing in the runtime.
The names were not read during the failing load. Changing the packed bytes
changed boot timing and exposed this interruption window. Moving the
packed staging buffer out of BRAIN's scratch and disabling lazy DSP
stepping did not fix it. The same image with this guard completed LOAD
PROJECT in 20.24 seconds of emulated time.

The interruption window and the guard are measured under the port. Whether
it causes a hang on a physical card is untested. A hardware trace showing
that the completion cannot reach the handler before bookkeeping would
falsify that hardware inference.

## The change

Stock saves SR in d0 and raises the interrupt mask to 7 at `0x40014cdc`.
At `0x40014cf2`, retain that SR in d3 instead of restoring it immediately.
d3's command-state value has already been stored and the remaining loop
does not use d3. After the pointer/count stores, the ten-byte DRAM return
stub restores SR, returns the original status, restores d2/d3 and returns
to the original caller. The existing critical section now includes the
256 data-word writes and their bookkeeping. No wait or filesystem call is
added inside it. Its worst duration on hardware remains to be measured.
