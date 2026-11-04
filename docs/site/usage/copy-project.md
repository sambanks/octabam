Duplicate a project folder on the CompactFlash card without loading it
first. The copy has everything in the folder: the stock files and what the
added features keep there (Kits, scenes, page 2 locks, BRAIN settings).
Stock SAVE TO NEW does not keep those extras.

## Access

MAIN MENU → PROJECT → CHANGE → highlight a project → FUNC+BANK → COPY
(under RENAME / DELETE). Mount the set that holds the source first
(CHANGE set if needed). Not available on `<CREATE EMPTY PROJECT>`.

## Operation

1. Open the CHANGE project list and highlight the source.
2. FUNC+BANK → COPY.
3. Edit the suggested name (`PROJECT` + date). The name editor caps at 32
   characters.
4. Confirm `COPY SRC -> DST?`.
5. On success: `PROJECT COPIED` / `OPEN IT?` — YES loads the copy and
   closes CHOOSE PROJECT. NO leaves the live project as it was.
   `COPY FAILED` on error; a partial destination folder is removed.

## Disk only — what SAVE is for

COPY copies the **folder on the card**, not what is in memory. Stock already
saves banks as you edit, so most trig edits are on the card without an
explicit SAVE. OPEN IT? does not ask to save the live project.

Copying works within the mounted set only. It refuses (rather than cut
anything short) when the set has more than 64 projects, a folder has more
than 256 entries, or a name inside the project is longer than 32 characters.
