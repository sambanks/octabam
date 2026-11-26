KITS adds a library of 255 Kits per project. A Kit is a named, saved Part, and
each pattern plays the Kit assigned to it. Loading a Kit loads its Part.

A Kit stores the Part's machines, FX1 and FX2 selections and parameter pages,
LFO and AMP pages, track levels and cue levels, all 16 scenes' locks, LFO
designer shapes, and MIDI track parameters.

Like a stock Part, a Kit does not store samples (it only references slot
numbers, while the files and slot settings belong to the project) or pattern
data such as trigs, parameter locks, track lengths, and scales. Tempo,
arrangements, track recorders, and project settings are also stored outside the
Kit.

## The keys

| Action | MKII | MKI |
|---|---|---|
| LOAD KIT | PART | FUNC+MIDI |
| SAVE KIT | FUNC+PART | FUNC+MIDI, then FUNC+BANK |
| Quick save the Kit under the cursor (keeps its name) | FUNC+PART, then FUNC+YES | FUNC+MIDI, FUNC+BANK, then FUNC+YES |
| Reload the current Kit from the library (`KIT RELOADED`) | FUNC+CUE | FUNC+CUE |
| Paste a pattern with a copy of its Kit in the next empty slot | FUNC+PASTE, then PART while STOP is held | FUNC+PASTE+MIDI |
| Save the Kit, copy it and the pattern to the next empty slots, and switch to the copy | PTN+FUNC+RIGHT | PTN+FUNC+RIGHT |
| Copy, paste, or clear an inactive pattern in the current bank (repeat paste or clear to undo) | Hold PTN and FUNC, press the pattern's TRIG, then REC / STOP / PLAY | Same as MKII |

## The lists

- **LOAD KIT** lists `UNDO KIT` (the Kit assigned to the current pattern before
  the last load), followed by the 255 Kits formatted as `NNN name`. A `*` marks
  any Kit not used by any pattern, and empty slots appear as `NNN ---`.
  Pressing YES loads the highlighted Kit immediately for the current pattern.
- **SAVE KIT** lists all 255 Kits with the cursor on the current Part's Kit (or
  on the first empty Kit if none is assigned). Pressing YES opens the 7-character
  name editor (defaulting to `NEW KIT` for an empty slot), saves the current
  Part into that Kit, and assigns it to the current pattern.
- Each list displays its title (`LOAD KIT` or `SAVE KIT`) when opened.
  FUNC+YES performs a quick save in SAVE KIT; in LOAD KIT it saves nothing and
  shows `LOAD KIT: NO SAVE`.
- In either list, turning LEVEL moves the cursor one row per detent, while UP
  and DOWN work as in stock OS.
- In either list, FUNC+REC copies the Kit under the cursor, FUNC+STOP pastes
  onto it, and FUNC+PLAY clears it. Repeating the paste or clear on the same
  Kit undoes the operation. Copying takes a snapshot of the Part including any
  unsaved live edits, and pasting, clearing, or undoing the current pattern's
  Kit takes effect immediately.
- If the pattern changes while a list is open, the cursor moves to the new
  pattern's Kit.
- The Part field on the status line displays the current pattern's Kit as
  `NNN name`, `NNN ---` if that Kit was cleared, or the stock Part number if no
  Kit is assigned.

## Notes

- Kits are stored per project in the project directory. When COPY PROJECT is
  installed, SAVE TO NEW copies the Kits file into the new project.
- When MIDI SCENES is installed, each Kit also includes the Part's MIDI scene
  locks.
