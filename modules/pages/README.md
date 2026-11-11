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
the key `("PAGES", "EVENTS", "DRUMMER")`). PLOCKS P2 and SCENES P2 detour
the same stock sites privately, so they do not share a remix with PAGES'
locks until they register on those boundaries.

### Measured (port, MKII, 11 Nov 2026)

- With a trig held in GRID RECORDING, stock installs its held-step editor
  `0x400508e4` over the encoders; with a scene held, `0x40053498` (SCENE A)
  or `0x40052e98` (SCENE B) ✅ (`--watch-pc`, the encoder table
  `0x46c7dede + 20·encoder` dumped).
- Trig mask `track + 0x00..0x07`, trigless `track + 0x10..0x17` (step s:
  byte `7 − s/8`, bit `s % 8`) ✅ (RAM diffed after a tap and a FUNC +
  TRIG). Taking a trig off runs `0x4006036e`; placing one does not ✅.
- Under the port the load's rebuilds decide a pattern's step 1 before a
  `--poke` lands, so `verify_port`'s lock cases lock step 2.

Gates: `verify_locks.py` (20 panel runs on KIT BALANCE, the saved card
booted), DRUMMER's `verify_port.py` cases `lockmix` and `lockscene`,
EVENTS' `verify_system_events.py` (every new site). On the author's MKII:
LIVEBAM images 86-90 (11 Nov 2026).

## Detours

| site | stock | |
| --- | --- | --- |
| `0x400322f0` | `movel %sp@(4),%d0; moveq #3,%d1` | the page key's setup opener `(code, mode)`: mode 1 on a key with clients steps to the next page; anything else runs stock |
| `0x40052208` | `movel 0x460d5de0,%d0` | the display loop (UI task): every client's tick |

## Measured

The page keys go to `0x4005578c(code, edge)` ✅. On a press, the same key
again within 14 ticks of `0x460d5de0` (last key `0x400c0aac`) is a double
press, `0x40055720(code, 3)` ✅; otherwise `0x40055720(code, 1)` ✅, which
calls `0x400322f0(code, mode)` when the key's page is the one shown
(`0x460d1684`) or a setup window is open, else switches page
(`0x400554e0`) ✅.

Under the port (1 Nov 2026, MKII, MIDI mode, SRC pressed once, then twice
more at a gap) ✅:

| gap between the two presses | screen |
| --- | --- |
| 60 ms | MIDI NOTE SETUP (CHAN, BANK, PROG, SBNK) |
| 300 ms | MIDI NOTE, unchanged |
| 800 ms | MIDI NOTE, unchanged |

Audio mode, under the port (7 Nov 2026, MKII, a FLEX track, SRC then SRC
again; `--watch-pc 0x400322f0`) 🟡: the opener is called with mode 1 at a
300 ms and an 800 ms gap and the PLAYBACK page stays as it was; at 60 ms
with mode 3, and SRC SETUP opens. A track's selection already shows its SRC
page, so SRC once is the press again. Gate: `modules/drummer/verify_live2.py`
(KIT BALANCE opens on a DRUMMER track, closes on SRC again or AMP, a FLEX track
gets nothing, the double press still opens SRC SETUP).

So a second single press of SRC on MIDI NOTE does nothing visible in stock
and a double press opens NOTE SETUP: PAGES takes the single press
(`0x400322f0(SRC, 1)`, no setup window open, FUNC clear) and leaves the
double press to stock. A double press shows the next page for the gap
before the second press opens NOTE SETUP 🟡. What `0x400322f0(code, 1)`
does on the other pages is not read.

## Status

On the owner's MKII in the live-djib rig (Oct-Nov 2026): SRC again on MIDI
NOTE steps through its pages. Gate: `tools/verify/verify_chords.py` (SRC
once, twice, three times through PAGES).
