# TEMPO-SYNC contribution notes

The installed-hook gate executes the writer on all eight tracks and checks
FX2 IDs, held-note publication, release, surrounding bytes and register
preservation. It also checks the OFF and REPLAY diagnostic selections.
This is emulator coverage, not a new hardware result.

Upstream commit `b2a35a5` fixed same-named local symbols shadowing the
TEMPO SYNC target by resolving symbols within their owning linked unit.
This gate checks the installed firmware behavior alongside that linker's
unit tests. It adds regression coverage; it is not a prerequisite for
MIDI Scales or the later MIDI modules and does not change the firmware.
