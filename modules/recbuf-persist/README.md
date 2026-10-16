# RECBUF PERSIST

On **PROJECT SAVE**, each non-empty recorder buffer (slots 128–135) is
written with the stock synchronous WAV writer (`0x40020f04`) to
`BUFFERS/RECn.wav` under the project (folder created if missing), PATH’d
to that name, then run through stock slot load + post-load
(`0x40093980` / `0x40099148`) so the control record and UI show the
assignment.

On **PROJECT LOAD** / **RELOAD**, existing `BUFFERS/RECn.wav` files get
the same PATH + slot-load treatment.

Empty buffers (control-record length ≤ 64) are skipped.

## Status

`Proof.CHECK`. `verify_recbuf` covers symbols and a port save/load
round-trip.

Hardware (author's MKII, personal remix, 16–17 Oct 2026):

| BUILD | measured |
|---|---|
| R1 | only the last slot assigned (async SAVE/ASSIGN shared scratch) |
| R2 | sync `wav_write` wrote all eight WAVs |
| R3 | slot load + post-load bound the UI assignment (`REC*.wav` at project root) |
| R4–R5 | paths under `!BUFFERS/`: WAVs + `PATH=` in `project.work`, UI stayed unassigned (`SLOT_LOAD` status −0x10 INVALID FILENAME — inferred from symptom + status table; falsify: assigned UI with a `!` PATH) |
| R6 | folder renamed to `BUFFERS/` (no `!`) |

## Remix

Listed next to STORE (required). Carrier:
`remixes/test/recbuf-persist`.
