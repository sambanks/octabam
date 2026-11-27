This module lets you duplicate a project folder on the CompactFlash card without loading it first. The copy includes everything in the folder: standard project files as well as data stored by added features (Kits, scenes, page 2 locks, and BRAIN settings). SAVE TO NEW also carries over any extra files present in the old folder on the card that do not already exist in the new folder. Saved `.strd` snapshot files are not copied; running SAVE PROJECT creates them for the new project.

## Access

Navigate to MAIN MENU → PROJECT → CHANGE, highlight a project, and press **`[FUNC]` + `[BANK]`** → **COPY** (located below RENAME and DELETE). Make sure the set containing the source project is mounted first (use CHANGE SET if needed). COPY is unavailable when `<CREATE EMPTY PROJECT>` is highlighted.

## Operation

1. Open the CHANGE project list and highlight the source project.
2. Press **`[FUNC]` + `[BANK]`** and choose **COPY**.
3. Edit the suggested name (`PROJECT` plus the date); the name editor accepts up to 32 characters.
4. Confirm the `"COPY SRC -> DST?"` prompt.
5. On success, the screen shows `"PROJECT COPIED"` and `"OPEN IT?"`. Press **`[YES]`** to load the copy and close CHOOSE PROJECT, or **`[NO]`** to stay in the current project. If an error occurs, `"COPY FAILED"` is shown and any partially created destination folder is removed.

## Disk only. What SAVE is for

COPY duplicates the **folder on the card**, not unsaved changes held in RAM. Because stock OS saves banks as you edit, most trig edits are already written to the card without an explicit SAVE. Selecting OPEN IT? does not prompt you to save the currently open project.

Copying only works within the currently mounted set. To avoid truncating data, the operation is cancelled if the set contains more than 64 projects, if a folder has more than 256 entries, or if any name inside the project exceeds 32 characters.
