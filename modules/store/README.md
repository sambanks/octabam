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

## Measured

Not yet. `verify_kits` and `verify_plocksp2` are the gates for the move.
