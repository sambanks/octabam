# PAGES

A page key pressed again on its own page opens nothing in stock. PAGES owns
that press and steps through the extra pages that modules register on the
key: the stock page, the first client's page, the next one's ... then the
stock page again. Each client keeps its own window, key layer and drawing;
PAGES only asks it whether its page is shown, and opens, closes and ticks it.
PAGES enters a remix only with a client in it. A client's page can also take
step and scene locks (*Locks* below).

Two keys are declared: **SRC on a MIDI track** (MIDI NOTE), with CHORDS
FACTORY as its client, and **SRC on an audio track**, with DRUMMER (KIT BALANCE,
on a DRUMMER track only; its page_open does nothing on another track, which
is stock's answer to that press). The mechanism is the same for every page
key (AMP, LFO, FX1, FX2 ...); each new key is declared when a client needs it
and a gate has measured what stock does with it there.

## Clients

A client registers `(module key, prefix)` on a page in `manifest.py`
(`CLIENTS`, in the order the cycle shows them) and exports, C convention
(d0-d1/a0-a1 clobbered):

| symbol | |
| --- | --- |
| `<prefix>_page_shown` | d0 nonzero while its page is open |
| `<prefix>_page_open` | open its page |
| `<prefix>_page_close` | close it |
| `<prefix>_page_tick` | the display loop's tick: follow the track, close itself off its page |

Registration is build-time: `remix.inc` carries the cycle per key as direct
calls (`pg_cycle_<mode>_<key>`) and the ticks (`pg_ticks`), no table. Every
registration is validated (unique keys and prefixes, declared page keys),
present in the remix or not.

## Locks

A client can declare pages whose parameters take **step locks** and **scene
locks**, as a stock page's do. Today: DRUMMER's KIT BALANCE (page 1).

On the panel, with the page in front:

| gesture | |
| --- | --- |
| GRID RECORDING, a trig held, a knob turned | the held steps' lock (each step needs a trig: TRIG or FUNC + TRIG; in GRID RECORDING stock places one at the press) |
| SCENE A or B held, a knob turned | the scene's lock |
| FUNC held as well | the lock removed |

A step's locks play from their step to the track's next trig (hold
`'trig'`, stock's), or on their step only (`'step'`); scene locks morph on
the crossfader (SCENES P2's formula, `A·wA + B·(0x8000 − wA)`). The locks
follow the steps: a trig taken off takes its locks, trig + PLAY and a track
or pattern clear clear them, a trig, track or pattern copy and paste
carries them (the clipboard and the undo buffer keep their own). They are
saved with the project in `pglocks.work` (`pglocks.strd` at SAVE PROJECT).
With a trig or a scene held, a knob on any PAGES page that takes no lock is
dropped, rather than stock locking the page under the window.

### Limits

- **Parts and banks.** The locks follow steps, tracks and patterns, not
  Parts or banks: RELOAD PART, a Part copy and a bank copy leave PAGES'
  locks as they were (a Part's scene locks are not put back by its reload;
  a copied bank's step locks stay with the bank they were on). A follow-up.
- **Sizes.** 4096 locks for the project, 1024 each for the clipboard and
  the undo buffer. A turn on a full pool, and a copy that does not fit, are
  dropped whole (nothing changes) and counted in `pg_lk_full`.
- **Reading while writing.** The engine reads the pool at its steps while
  the UI task writes it (a knob, a copy, a clear). Every write of the
  project's pool runs between two increments of a generation counter
  (`pg_lk_gen`, odd while entries move); a read that saw it odd or changed
  is retried, then dropped for that step (the last step's locks stay).
  Measured under the port: DRUMMER's step builds run in a task the port
  names `main`, the knob turns in the UI task (`sys`).

### Declaring locks

In `manifest.py`, `LOCKS` lists `(module key, prefix, page id, page name,
hold)`; the page id (1..7) is part of every saved lock, so it never changes
once given. The client exports (C convention):

| symbol | |
| --- | --- |
| `<prefix>_lk_ctx()` | 0, or `0x8000 \| page << 8 \| track` while its lockable page is in front |
| `<prefix>_lk_turn(page, slot, value, delta)` | the value a turn gives; −1 for a slot that takes no lock (called with delta 0: pure) |
| `<prefix>_lk_part(page, track, slot)` | the edited Part's value of the slot (a new lock starts there) |
| `<prefix>_lk_redraw(page)` | draw the page again |

and plays the locks itself: `pg_lk_step(page, track, bank, pattern, step,
trig)` when its step is decided, `pg_lk_value(page, track, slot, base)` for
the value to play (`base` the Part's), `pg_lk_shown` / `pg_lk_where` for
its drawing (`locks.c`). A client that must work without the locks calls
them through thunks of its own (DRUMMER's `dr_pl_*`, `HAVE_PAGELOCKS`).

The locks unit (`locks.c` + `locks.s`, built by `generate.py` into
`locks_unit.s`) enters a remix with PAGES, EVENTS, STORE and a client that
declares locks. It uses EVENTS' `edit.held`, `edit.scene_held`,
`edit.copy_pre` and `edit.steps`, and STORE's side-file events (client 10,
the key `LOCKS_KEY`). `LOCKS_KEY` is built from `LOCKS` in PAGES' manifest
(PAGES, EVENTS, STORE and any one of the LOCKS clients); EVENTS' and
STORE's registrations and DRUMMER's `HAVE_PAGELOCKS` read it, so a client
added to `LOCKS` alone is wired everywhere. PLOCKS P2 and SCENES P2 detour
the same stock sites privately, so they do not share a remix with PAGES'
locks until they register on those boundaries.

## Detours

| site | stock | |
| --- | --- | --- |
| `0x400322f0` | `movel %sp@(4),%d0; moveq #3,%d1` | the page key's setup opener `(code, mode)`: mode 1 on a key with clients steps to the next page; anything else runs stock |
| `0x40052208` | `movel 0x460d5de0,%d0` | the display loop (UI task): every client's tick |
