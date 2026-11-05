# PAGES

A page key pressed again on its own page opens nothing in stock. PAGES owns
that press and steps through the extra pages that modules register on the
key: the stock page, the first client's page, the next one's ... then the
stock page again. Each client keeps its own window, key layer and drawing;
PAGES only asks it whether its page is shown, and opens, closes and ticks it.
PAGES enters a remix only with a client in it.

Today one key is declared: **SRC on a MIDI track** (MIDI NOTE), with CHORDS
FACTORY as its client. The mechanism is the same for every page key (AMP,
LFO, FX1, FX2 ...) and for audio mode; each new key is declared when a
client needs it and a gate has measured what stock does with it there.

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
