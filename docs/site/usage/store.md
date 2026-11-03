Keeps each feature's extra files with the project: the Kits file, the page 2
lock files and the MIDI scenes file. They are written, copied and cleared at
the right moments: every bank load, a new project, project save and reload.

In the Copy Project list, LEVEL scrolls only that list, as it does in the Kits
lists.

Harmony's degree/chord files stay with the project. If a companion file cannot
be safely saved, STORE refuses the save before overwriting its bank. A failed
bank copy leaves the companions alone; a companion-copy failure is reported.
The added Harmony callbacks have not been tested on hardware.
