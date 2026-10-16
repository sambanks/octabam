On PROJECT SAVE, each non-empty recorder buffer is written to
`BUFFERS/REC1.wav`..`REC8.wav` under the project folder (the folder is
created if missing) and assigned back to that recorder slot. On PROJECT
LOAD or RELOAD, those files are assigned again when present.

Empty buffers are skipped. Nothing on the panel — it rides the stock
project save and load. The folder name must not start with `!` (that
prefix makes the stock slot loader reject the path).
