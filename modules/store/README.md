# STORE

Platform module. Holds the stock sites where a project's side files are
written, read, copied and cleared, and where a Part is saved or cleared. The
ledger allows one detour on a site; KITS and PLOCKS P2 each hooked some of
these sites, so the sites are held once here and each module is a client that
STORE calls at the event.

## Events

| event | stock site | arguments to a handler |
|---|---|---|
| loadall_pre / post | `0x40090504` (load of every bank) | none |
| loadmask_pre / post | `0x400905d4` (masked bank load) | d1 = mask, d2 = return address |
| newproj | `0x400909d8` (new, empty project) | none |
| bankw_pre | `0x400918aa` (inside the bank writer, after the project directory exists) | d1 = mask of banks written |
| bankw_post | `0x400917c8` (bank writer, after it returns) | none |
| pstore_pre / post | `0x4008ee74` (project store) | none |
| preload_post | `0x4008f180` (project reload) | none |
| bankcopy | `0x4008ee42`, `0x4008f14e`, and the four `d5` loads at `0x4008ef9a`, `0x4008f02e`, `0x4008f2a6`, `0x4008f33a` (stock `.work` / `.strd` file copy) | d0 = destination path, d1 = source path; after stock's copy |
| tocs1 | `0x4000faf0` (current bank into CS1) | d0 = bank; before stock's copy |
| fromcs1 | `0x40025808` (power-up bank from CS1) | d0 = bank; after stock's call |
| partsaved | `0x4004a9c4` (Part Save tail) | d0 = part |
| partclear | `0x4004a9d0` (Part Clear entry) | d0 = part |
| ctl (not an event) | `0x40061e00` (the encoder dispatch call) | opens the refusal prompt, scrolls it; else KITS' list scroll or stock's dispatch |

A handler may clobber every register. Handlers of one event run in the order
of `CLIENTS` in `manifest.py`. Wrappers keep one return slot per event and do
not re-enter.

## Clients

`CLIENTS` in `manifest.py` lists, per module key, the symbol prefix and the
events it handles; the handler for event `e` is `<prefix>_st_<e>`. A client not
in the remix is left out of the tables, and a handler named there that the
link cannot find stops the build. A client declares `requires=("STORE",)`.

| client | events |
|---|---|
| PLOCKS P2 (`plk`) | loadall_pre, loadmask_pre, newproj, bankw_pre, bankcopy, tocs1, fromcs1 |
| KITS (`kits`) | loadall_pre/post, loadmask_pre/post, newproj, bankw_post, pstore_pre/post, preload_post, partsaved, partclear |

## Caller census

Every caller of `0x40090504` (1), `0x400905d4` (3), `0x400909d8` (5, one
pc-relative), `0x400917c8` (5, one pc-relative), `0x4008ee74` (3) and
`0x4008f180` (1) in the stock image is a direct call; a byte search of the image
for each address finds only those call operands (10 Oct 2026). PLOCKS P2's
call-site hooks covered every caller of the load and new-project routines, so
an entry hook sees the same calls.

## File calls

`store_path`, `store_fopen`, `store_fread`, `store_fwrite`, `store_fclose`
and `store_crc32` (running value in d1, 0 to start). A client owns a 4,120-byte
context (stock file object and its 4 KB buffer), so one client's open file is
never another's. `scenes.work` uses them; KITS and PLOCKS P2 keep their own
copies.

## Refused files

A client that cannot use a file (unknown version, bad length or CRC) calls
`store_refuse(client id, argument)` and leaves the file alone: it is never
written over. STORE lists up to 16 refusals (`store_pend`, `store_npend`,
cleared at a load of every bank). At the first encoder turn after the load
(the only UI-task site STORE holds; a list cannot be opened from the engine
task) a three-row list opens, each row naming the file:

| row | answer | what the client does |
|---|---|---|
| IGNORE | `ANS_IGNORE` | nothing: the client stays off for the session |
| OVERWRITE | `ANS_OVERWRITE` | starts empty (KITS: as a missing file, the stock Parts become Kits); the next save writes |
| BACKUP | `ANS_BACKUP` | as OVERWRITE, and that save first copies the file to `.bak` |

LEVEL scrolls the list; YES answers; NO closes it without an answer, leaving the
entries listed and asking no more until the next load. No answer touches the
card: the callbacks run in the UI task and the save in the engine task (a file
copy called through the port's `--call` never returned). Client ids: 0 PLOCKS P2
(argument = the bank), 1 KITS, 2 MIDI SCENES. PLOCKS P2 used to read a refused
`p2lkNN.work` as empty and overwrite it at the next bank write.

## Measured

Under the port (10 Oct 2026): `verify_kits` (the refused `kits.work`: listed; OVERWRITE
and BACKUP read it as a missing file; the list opens at an encoder turn, LEVEL + YES
answers OVERWRITE, YES on row 0 answers IGNORE), `verify_plocksp2` (a bad `p2lk` header is
listed and survives SAVE PROJECT), `verify_scenes --persist` (a bad `scenes.work` stays byte
for byte under IGNORE; OVERWRITE and BACKUP give a good file, BACKUP also `scenes.bak`).
Not covered: the rows' text on the LCD, a list opened over another window, the prompt on a unit.
