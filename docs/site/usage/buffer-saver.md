## What it does

On stock OS, saving a project does not save audio held in the recorder buffers. If you forget to run SAVE THIS RECORDING before turning the unit off, those recordings are lost when you reload the project. BUFFER SAVER prompts you to save unsaved recorder buffers during SAVE PROJECT so your recordings are preserved with the project.

## How to use it

Record as usual, then save the project using PROJECT > SAVE, [FUNC] + [PROJ], or PROJECT > SAVE TO NEW. If any recorder buffer contains an unsaved recording, a prompt appears first:

- **[YES]**: Saves each new recording to the card and assigns it back to its recorder buffer, then proceeds with the standard SAVE PROJECT confirmation. When you reload the project later, the recordings are still there.
- **[NO]**: Skips saving the buffers and saves the project as usual.
- With **SAVE TO NEW**, pressing **[YES]** saves the recordings first so the new project includes them as well.

Additional details:

- There is no naming prompt; each recording uses the Octatrack's default naming scheme, `R1-YYMMDD-HHMM` (where R1–R8 is the buffer number). If a file with that name already exists, `-2`, `-3`, and so on are appended so existing files are never overwritten.
- Files are saved to the directory configured under PERSONALIZE > SAVE SAMPLES TO, along with their `.ot` settings files, matching SAVE THIS RECORDING.
- If there are no unsaved recordings, SAVE PROJECT behaves normally without prompting. Once a recording is saved, it will not trigger a prompt again unless you record into that buffer again.
- Any buffer that is still actively recording is skipped until the next save.

## Screens

![After a take, SAVE PROJECT asks first](../../img/buffer-saver/ask.png)
