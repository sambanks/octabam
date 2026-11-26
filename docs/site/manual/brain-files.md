BRAIN stores its settings, defaults, and templates on the CF card, creating the
required folders and files automatically as needed.

| Location | Contents |
|---|---|
| `BRAIN/` at the CF card root | Global settings, saved effect defaults, and templates shared across all projects |
| `brain.work`, `brain.strd` inside a project folder | Per-project BRAIN settings |

Each file comes in a pair: a working copy (`.work`) and the last saved copy
(`.strd`). If the working copy is damaged, BRAIN falls back to the saved copy.
If both are damaged, BRAIN uses the firmware's built-in defaults without
overwriting your files.

When you power on the unit or load a project, effects start with the firmware's
built-in defaults and then apply any valid defaults saved on your CF card.
**SAVE FX DEFAULT** writes the current FX page defaults, and **SAVE PROJECT**
updates the `.strd` backup copy.

Back up these files along with the rest of your CF card.
