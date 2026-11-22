# Variable-speed playback: the firmware ground (REPITCH)

The stock 1.40C facts the REPITCH module (removed; `git show 0ac7db50:modules/repitch/README.md`)
stands on: the page descriptors, the select widgets, the TSTR resolution,
the voice renderer's readers of it and the playback increment. measured
from 1.40C unless marked; inferred.

**Page descriptors** (`PARAM_PAGES.md`): STATIC `P = 0x400d301c`, FLEX
`0x400d31ae`, PICKUP `0x400d3664`. TSTR is slot 10: count `P+0x9a+40`,
formatter `P+0xca+40` (`0x4003b6a4`), widget `P+0xfa+40` (`0x40046c28`).
PTCH is slot 0 with the knob `0x400479b4`.

**Widgets.** The select family (`0x40046f10` 2, `0x40046d9c` 3, `0x40046c28`
4, `0x40046ab4` 5 positions) share one body and differ in a `cmp #N-1`
bound and a 17x7 icon table (`0x400be2f2`, `0x400be2fa`, `0x400be306`,
`0x400be316`); a value past the bound returns having drawn nothing. The
five-position one is referenced by nothing in stock. The label is
`sprintf`ed into an 8-byte stack buffer (`sp+40`, the return address at
`sp+48`) and centred at the cell's x+9. The knob `0x400479b4` draws only
its frame for a negative value (`0x40047a0e`).

**The PLAYBACK SETUP window** is screen record `0x400bb7c8` (open
`0x400584d0`, draw `0x4003c830`); its editor is `0x4003a474(slot, delta)`.

**TSTR resolution** (`0x40007d7c`, in the voice renderer): SETUP TSTR from
the per-track record `0x80000510 + 48·t` byte 28; `AUTO` (1) takes the bound
sample's `TSMODE` (settings `+0x110`); a PICKUP (voice `+20` = 4) with 0
gets 2; a loop region under 6,144 frames gets 0. The result is voice
`+24` (voices `0x800049d8 + 168·t`, bound settings pointer at `+8`, machine
at `+20`). (Notes of 31 Jul, since removed, called voice `+0x18`
a channel count; it is this resolved TSTR. Their addresses are 0x400 low:
they assumed the image loads at `0x40000000`.)

**The voice renderer** (`0x40007960`, called once per track and chunk by the
increment builder at `0x400041c4` with the chunk's output samples `d3` and
the source frames the DSP will consume `d7 = increment x d3`) reads the
resolved TSTR at nine sites (scanned, `repitch_probe`), each as
zero/nonzero or against BEAT (3); what each does is read in objdump, the
position advance measured under the port:

| site | nonzero does |
|---|---|
| `0x40007ede` | sets the 64-bit position ratio from project tempo / sample tempo (dry: 1/1) |
| `0x40008210`, `0x400089de` (reverse) | takes the sample's tempo and its reciprocal (`+0x116`, `+0x118`) in place of the playing rate; they differ, so the chunk is read in pieces (unconfirmed the grain splice) |
| `0x400081b2`, `0x4000898a` (reverse) | sets voice `+3` when project tempo x rate exceeds twice the sample's (unconfirmed a stretch beyond 2x) |
| `0x4000886c`, `0x40008e42` (reverse) | **advances the sample position by the chunk's OUTPUT samples** through that ratio, where OFF advances it by the frames consumed (`d7`) |
| `0x400082a8`, `0x4000847e` | only for 3 (unconfirmed BEAT's transient handling) |

So the renderer's position moves at project / sample tempo for every
nonzero TSTR, whatever the increment. The project tempo it reads is
`fp-80`, from `0x80001824` (latched from `0x80001818` every frame,
`0x4000caa6`) scaled by voice `+38`.

**The playback increment** (Q26, `0x04000000` = 1.0) is built per track by
`0x40004008` (the table `0x400d6434` serves STATIC, FLEX and PICKUP), stored
at state `+36` (states `0x80004898 + 40·t`) and shared by the ColdFire
source supplier and the DSP voice command. The per-frame loop calls each
builder twice and the second call passes the recompute flag `0x10`
(`0x4000d518`), so the increment follows its inputs every frame. Inputs:
PTCH word at record `+0` (`0x4000` neutral, 0.2 semitone per raw step, one
octave per table half: +60 = 2.0, -60 = 0.5), RATE word at `+6` (applied
below `0x7f00` when the RATE mode byte `+27` is 0). The project tempo the
builder reads is `0x8000181c`, latched every frame from `0x80001814`
(`0x4000ca9a`), which both UI tempo setters write (`0x4009c7c4`,
`0x4009c708`).

**The audio editor ATTR page** draws with `0x4006e450`; TIMESTRETCH (row 2)
prints `OFF`/`NORMAL`/`BEAT` for 0/2/3 and `ERROR` otherwise
(`0x4006e6ec..0x4006e722`). Its value keys step `0 -> 2 -> 3` up
(`0x4006ee42`) and `3 -> 2 -> 0` down (`0x4006ef76`). A sample loaded
without a `.ot` gets NORMAL and a tempo from its length, or the project
tempo if it is short (`0x40095ee0`); the ATTR tempo editors clamp to
720..7200 (`0x40098ec0..`).
