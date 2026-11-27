This module keeps each feature's extra data files (the Kits file, the page-2
lock files, and the MIDI scenes file) in sync with the active project. Those
files are written, copied, or cleared automatically whenever you load a bank,
create a new project, or save and reload a project.

In the Copy Project list, turning LEVEL scrolls only that list, matching the
behavior of the Kits lists.

Harmony's degree/chord files stay with the project. If a companion file cannot
be safely saved, STORE refuses the save before overwriting its bank. A failed
bank copy leaves the companions alone; a companion-copy failure is reported.
The added Harmony callbacks have not been tested on hardware.

STORE also provides optional retained memory for modules that register a
reservation. It is included automatically when a selected feature needs it;
there is no extra storage module to enable. Clients keep their own data format
and recovery policy. Conflicting reservations are refused during the build.
Harmony currently occupies this pool's full capacity, so another feature cannot
share that same pool with it without a separate storage-layout change.
