On PROJECT SAVE, each non-empty recorder buffer is written to
`BUFFERS/REC1.wav`..`REC8.wav` under the project folder (the folder is
created if missing) and assigned back to that recorder slot without
re-reading the WAV, so the UI updates as soon as the write finishes. On
PROJECT LOAD or RELOAD, those files are loaded into the same slots when
present.

Empty buffers are skipped. Nothing on the panel. It rides the stock
project save and load. Keep the folder name free of a leading `!` so the
stock slot loader accepts the path.
