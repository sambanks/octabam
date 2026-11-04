BRAIN keeps its settings, defaults and templates on the CF card, and creates its folder and files when it needs them.

| Where | What |
|---|---|
| `BRAIN/` at the card root | settings, saved defaults and templates shared by every project |
| `brain.work`, `brain.strd` in a project folder | that project's settings |

Each pair has a working copy (`.work`) and the last saved one (`.strd`). A damaged working copy falls back to the saved one; if both are damaged, the image's own defaults are used and nothing is overwritten.

At project load and power-up, effects start with the image's own defaults, then take any valid defaults you saved on the card. **SAVE FX DEFAULT** stores the current FX page. **SAVE PROJECT** updates the saved copy.

Back these files up with the rest of the card.
