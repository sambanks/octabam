# The workbench — `make remix`

The interactive front end of the project, organized the way an Octatrack
user thinks: **tracks and effects**, not modules and payloads. Shipped
31 Aug 2026 (PRs #40–#44), replacing the curses composer; PLAN.md §5 is the
decision record, this page is the manual.

What it is for, in priority order (Sam's, stated when the redesign was
commissioned):

1. **Trial sounds** — put an effect on a track, dial its real knobs, render
   a wav through the actual DSP code and hear it. A/B alternatives.
2. **Build and save remixes** — compose the firmware image with collision
   and fit feedback.
3. **No-flash confidence** — boot the built image in the local ColdFire
   emulator and see the firmware draw its own screens.

Audio comes from the local DSP emulator (~6× real time, `docs/HARNESS.md`);
the ColdFire emulator (`docs/EMU.md`) provides the screens. Nothing in the
workbench touches hardware.

## Setup

```bash
make emu-setup      # uv provisions .venv with unicorn + textual
make remix          # the workbench (make bus first if out/mainos_bus.bin
                    # doesn't exist yet — the EMU view boots it)
```

The frontend is `tools/remix/app.py` (Textual). `make remix` prefers
`.venv/bin/python3`; on bare `python3` it exits with the setup hint. The
build and every check remain dependency-free — only the interactive
workbench lives in the venv.

Playback is `afplay`, so hearing renders is macOS-only; everything else
works anywhere the DSP toolchain does.

## One page, three panes

`make remix` opens a single screen. `tab` moves between panes, `up`/`down`
moves within one, `?` opens this page's short form, `esc` stops audio, `q`
quits. **There is no per-track view** — the eight-track rig was retired 2 Sep
2026 because it was a second place to say what a remix already says, and
knob values belong to the effect rather than to a track.

```
┌ AVAILABLE ───────┬ LOADED · chongbong ────┬ ChonVerb ────────────────────┐
│ ── server ──     │ ▸1 ChonVerb  FX2  2411w│ server · id 0x07 · tracks 5-8│
│    BongDelay FX2 │  2 BongDelay FX2  2469w│ TIME  64  [######......] p1  │
│    ChonVerb  FX2 │  3 Send      FX2   250w│ MOD   30  [###.........] p1  │
│ ── insert ──     │  · tempo-sync −     ◀fb│ …                            │
│    WarpFold  FX2 │ —  PLATE, SPRING, DARK │ preview  FX1 FX2 MENU        │
│ ── stock ──      │                        │ .--------------------------. │
│  ✓ FILTER FX1+FX2│ A 74 free · B 5 free   │ | EFFECT 2 SETUP           | │
└──────────────────┴────────────────────────┴──────────────────────────────┘
```

### AVAILABLE — the library

Everything that *could* be in an image: your modules grouped **server** /
**insert** / **system**, then the stock effects the unit already ships. `✓`
marks what the current selection holds.

**`enter` ADDS the highlighted module to the image.** It displaces nothing.
`left`/`right` in LOADED moves a row afterwards; `enter` in LOADED removes
the row you are on. The library only ever adds — `enter` on something already
in the image just points at its row.

⚠️ **`enter` used to SWAP** (2 Sep 2026, reverted the same day): the module
took the highlighted row's slot and that row was dropped, with a `▸` caret
marking where it would land. The stated justification was "an image is a
fixed budget, so putting something in means taking something out" — which is
**the ledger's scarcity applied to the operator's gesture, where it does not
belong**. Rows are not the scarce thing: the long-list cave holds **31** of
them (`build_bus.py` LONG_LIST), and a **stock row costs zero words** — no
code placed, no descriptor cloned. Only *words* are scarce, and only for
modules of ours. Two things went wrong in practice: a chongbong user pressed
`enter` on a server and lost the other one (the caret had moved onto it), and
the caret itself was a second cursor in a pane you were not standing in.

**Rows are not the currency — words are.** The pane's one status line shows
the budget the way the build reports it — **per payload**, `A 74 free · B 5
free` — and this is the thing to watch, because:

- a **chooser row costs nothing** (seven fit in place, up to 32 in the long
  cave), and
- a **stock effect costs nothing at all** — its code is already in the image
  whether or not it has a row. **Swapping a stock effect out frees zero
  words.** The swap gesture is about the panel SLOT, not about space.

⚠️ **There are TWO 2,724-word regions, one per payload**, and `SPEC=1` puts
each server on its own. Summing every module's words against a single region
is wrong, and the pane used to do it: it read `chongbong`, the *shipping*
remix, as `5130 words exceeds the 2724-word donor region by 2406` when the
truth was A 2,650/74 free and B 2,719/5 free. Fixed 2 Sep 2026 by reporting
the build's own per-payload figures and deleting the reimplemented check
(`state.problems`). An overrun now arrives as the build's own refusal, which
names the payload: `payload B: RUNGS overruns the region (3599 > 2724
words)`.

So the words are spent only by modules of ours, and a swap is only
1-for-1 in *rows*: Nimbus (500) could equally be Streamz (255) + WarpFold
(322), or Hello World (27) + Ripple (347). Measured costs, payload A:
Hello World 27, Streamz 255, WarpFold 322, Ripple 347, BodeShift 391,
Nimbus 500, Rungs 880, Send 215, ChonVerb 2,411 (+24 LFO table), BongDelay
2,469 (payload B).

**One trade is often not enough**, and the status line names the next one
rather than leaving it to the build to refuse:

| after you add | what happens |
|---|---|
| no safe fallback | **SEND is added** — the status line says `added Send as the fallback`. A row is free, so sacrificing an effect for it would be this UI's invention, not the image's constraint |
| a buffer clash | the ⚠ line reads `x removes Flanger, Chorus, Spatializer, Comb Filter — they need the same buffer`, and **`x` does it** |
| past a payload's region | the build refuses and names it: `payload B: RUNGS overruns the region (3599 > 2724 words)` |

**The ⚠ offers its own fix.** `x` applies whatever it just advised — and it
names **every** row that has to go, not the first. The build used to `exit`
on the first offending donor row, so clearing a selection meant iterating:
remove PLATE, rebuild, fail on SPRING, remove that, rebuild. It knows all of
them the moment it knows the cursor, and the one-key fix can only remove what
the build named.

⚠️ The ⚠ describes the **image**, not the cursor, so it does not change as
you scroll. That is deliberate — it is the state of what you are composing —
but it means a warning naming an effect you have scrolled away from is still
current.

It names the **cause and the count**, not the list: `Nimbus pins the buffer 7
stock effects allocate — x removes them`. Naming all seven took four wrapped
lines of a 40-column pane and still said neither *which* module was doing it
nor *why*, which is exactly the question it produced ("why did adding nimbus
remove so many?"). The list is one keystroke away; the reason is what you
actually want.

⚠️ **Seven, not four, since the reverbs became listable.** PLATE, SPRING and
DARK REV take a per-track instance buffer like FLANGER, CHORUS, SPATIALIZER
and COMB — measured, they read `x:>$213`. **The image you end up with is
unchanged**: Nimbus plus the seven stock effects that allocate nothing, plus
SEND. The trade only *looks* bigger because the chooser now starts at
fourteen rows instead of eleven. And two of the three would have gone anyway
on words — Nimbus (500) + SEND (215) reaches into SPRING, so only DARK REV is
refused purely for the buffer.

**The consequence goes on the ⚠ line, not in the status bar.** Appending it
to "swapped X → Y" produced a run-on the status bar then truncated — and the
half it cut was the only actionable one. The ⚠ line sits under the rows it
is about and is re-derived every render rather than being a snapshot of the
moment one swap happened.

**The buffer clash is the expensive one, and it is why adding ChonVerb to a
stock chooser costs four effects.** FLANGER, CHORUS, SPATIALIZER and COMB
each take a per-track instance buffer from the host's bump allocator, at
exactly the addresses ChonVerb's tank hardcodes — so the ledger refuses each
pair, and the chooser is one list for all eight tracks so the image cannot
keep them apart. The ledger states it one PAIR at a time, which is four
near-identical walls of text; the pane aggregates them into the sentence
above. What you are left with — ChonVerb, the seven stock effects that can
coexist, and Send — *is* `remixes/restored.py`.

The three stock **reverbs** are not here — they are in LOADED, because they
are part of a stock chooser. See below.

The `FX1+FX2` column is which **chooser** the effect has a row on, derived
from the pristine image rather than written down (`stock.fx1_ids()`). Stock
gives the two slots different lists: ten effects on FX1, those ten plus
DELAY and the three reverbs on FX2 — which is why taking the reverbs as
donors cost FX1 nothing. **Our own modules are FX2-only, and that is a build
limit, not a hardware one**: the DSP dispatch tables are indexed by the raw
id and shared between the menus, so a module's code already runs from FX1
the moment FX1 selects its id. What is missing is the panel side — FX1's
15-entry chooser cannot grow in place and must be relocated to a cave
(`tools/build_fx1.py` proved it can be), and no manifest field asks for a
row. The real ceiling is cycles ×4 (`PLAN.md` §2).

### LOADED — the image being composed

The selection, **in chooser order** — the order here *is* the order of rows
on the panel, so `left`/`right` is a real edit, not a view preference. The
number column is the panel row; `·` means no chooser row at all (a ColdFire
patch). `◀fb` marks the fallback. Each module's word cost comes from the real
assembly the background rebuild runs, so it is always filled in.

**The three reverbs live here, and you can keep them.** An unmodified unit
shows **fourteen** FX2 effects and PLATE, SPRING and DARK REV are three of
them, so a stock selection lists all fourteen. Their code *is* the donor
region — but the build packs it **from PLATE upward**, so a selection only
loses the reverbs it actually reached, and the pane shows which
(`— Plate Rev   donor, taken`), read from the build's own report rather than
assumed.

The smallest buildable image is `remixes/restock.py`: **thirteen** stock
effects including SPRING and DARK REV, plus SEND. SEND's 215 words land on
the first 215 of PLATE's 594, so the minimum costs the *smallest* reverb and
nothing else.

⚠️ Until 2 Sep 2026 all three were nulled **unconditionally** — a build that
placed 250 words silenced 2,724 words' worth of reverb — so the honest answer
to "why can I never get the stock verbs back?" was "you cannot, ever". PLAN
§7, now closed. The precedent was CHORUS, a donor until v98, which got its
stock dispatch back the moment the build stopped taking its code.

**Two guards make listing them safe.** The **build** refuses a donor row
whose words this selection took, naming it — only the placement knows where
the cursor stopped, so nothing predicts it, and `x` applies the fix. The
**ledger** refuses a reverb beside a module with fixed Y buffers: all three
take a per-track instance buffer, which is **measured** — each reads
`x:>$213`, the host's bump allocator, within ~25 words of its entry (PLATE
`0x01018`, SPRING `0x01267`, DARK `0x01692`) — exactly like SPATIALIZER,
FLANGER, CHORUS and COMB.

⚠️ It used to be three lines, one per reverb, each reading `– PLATE REV
taken by BongDelay +1`. That said one thing three times; it named an
arbitrary module as the taker (`eats[0]` is just the first selection with DSP
code — **nothing computes a per-reverb attribution**, and the `+1` was SEND);
and at 40 columns the ` +1` wrapped onto its own line, so it read as a fourth
mystery row. Corrected 2 Sep 2026.

**You start at `stock`** — the chooser an unmodified unit shows, no modules
of ours. You add to what the box already does rather than to somebody else's
remix. That selection deliberately cannot build as it stands: a remix must
name a fallback for the ids it does not implement, and no stock effect is a
safe one (it would *process* the unknown id), so the moment you add a module
you add SEND too. The pane says so.

`l` loads a remix (or `stock`), `s` saves the selection as one, `k` resets to
stock, `f` picks the fallback explicitly, `c` runs `make check`. **There is no
build key** — see below.

**The pane closes with ONE line**, which is either the per-payload budget, a
`⚠` naming what to remove, or `building…`. It used to close with five — a
budget, a `●` legend, a "dim = stock" legend, a keys hint and a `⚠` — which
was roughly half the pane's height spent explaining constraints rather than
showing the image. The explanations are in `?`.

### UNIT — the selected effect

Follows the cursor, so pointing at something in the library previews it
before you add it. Shows its kind, id, menus and track range, its one-line
doc, and its drawn parameters with values — `left`/`right` adjusts,
`shift` for ×10. **Values live per module**, seeded from the manifest
defaults (a stale default polluted every shimmer measurement until Round 12).

### What an effect COSTS, while you are choosing

The UNIT pane carries a resource line under the doc, and the status line
carries the same facts while you scroll (`rig.resources()`):

```
ChonVerb   — bus · id 0x07 · 2411 of 2,724 words ·
             needs the whole FX2 buffer region (blocks 7 stock effects) ·
             2 core-private Y words · not in the image
Dark Rev   — stock · id 0x16 · free while your modules stay under 1,657 words ·
             takes 1 of the 4 FX2 buffer slots · in the image
```

"Will this fit beside what I already have" is what the library pane is really
being asked, and every answer used to arrive only as a **refusal after adding
it**.

**It says the CONSEQUENCE, not the address.** `pins Y:0x4000-0xBFFF` is where
a buffer lives; what you are deciding is what it costs you — and because that
set is FIXED, it names them: `pins all 4 FX2 buffer slots — costs Flanger,
Chorus, Spatializer, Comb Filter and the 3 reverbs`. A count ("blocks 7
stock effects") just makes you go and find out which seven, and the answer
never changes. The addresses are in `docs/DSP.md` §10 and belong there —
**the pane carries consequences, the docs carry mechanism.**

How many slots differs by module, and it is **measured** — `X:0x255` read
from both payloads:

| | core 0 FX2 | core 1 FX2 |
|---|---|---|
| allocator hands out | `0x4000 0x8000 0x30000 0x34000` | `0x4000 0x8000 0x38000 0x3c000` |

ChonVerb is **all four** of core 0's — tank in the core-private pair,
relocated buffers in the shared-window pair. Nimbus is the core-private pair
only. BongDelay is core 1's shared-window pair only (its lines are based at
`0x38000`), so a stock effect there collides *only if* the allocator hands it
slot 3 or 4 — which depends on how many FX2 effects the dispatcher has
already walked this block. **Unpredictable is still a refusal**, and each
works perfectly alone, which is the worst shape a defect can have.

### One line per menu

FX1 and FX2 have **separate allocator tables**, so a cost on one is not a cost
on the other — and saying that in a subordinate clause ("FX2 rows only, FX1
keeps its 4") made a simple fact read as a caveat. There is a line each:

```
Nimbus          500 of 2,724 words
                FX1  no row — takes nothing
                FX2  pins 2 core-private slots — costs the rows of
                     Flanger, Chorus, Spatializer, Comb Filter and the 3 reverbs

Flanger         free — already in the image
                FX1  takes 1 of the 4 slots (3,072 words each)
                FX2  takes 1 of the 4 slots (16,384 words each)
```

**Nothing of ours takes an FX1 slot.** Our modules have no FX1 row, so the FX1
allocator never hands them anything; FX1 slots go to stock effects only. A
module with no chooser row at all (a ColdFire patch like tempo-sync) shows
neither line.

⚠️ **The list of effects a pinner costs you is NOT on the module line**, and
that is deliberate: it is the same seven for every pinner, so printing it per
module made ChonVerb and BongDelay show identical lists and read as two bills
for one debt. It belongs to the **image** — the ledger refuses an allocating
stock effect beside *any* pinner — so the LOADED pane says it once:

```
no room for Flanger, Chorus, Spatializer, Comb Filter and the 3 reverbs
— ChonVerb and BongDelay pin their slots
```

What genuinely differs per module is which slots, on which core, for which
tracks:

```
ChonVerb   FX2  pins all 4 buffer slots on the core serving tracks 5-8
BongDelay  FX2  pins 2 shared-window buffer slots on the core serving tracks 1-4
Nimbus     FX2  pins 2 core-private buffer slots on whichever core hosts it
```

**They are two effects, not one.** ChonVerb serves tracks 5-8 and BongDelay
tracks 1-4, on different cores, and each ships alone: `verbonly` is ChonVerb
without the delay, and a delay-only remix builds too (BongDelay lands on
payload B and its id aliases to SEND on A, so selecting it on tracks 5-8
makes a send rather than silence). Showing them as one "bus" would hide the
track range, which is the thing you have to know to use either.

### It costs the FX2 ROW, not the effect

**FLANGER, CHORUS, SPATIALIZER and COMB are still on FX1, and still work.**
Leaving a stock effect out of a remix takes its FX2 chooser row and nothing
else — its code, descriptor and dispatch stay stock on both cores, which
`verify_menu` and `verify_replaces` both assert.

**And the collision cannot follow them to FX1.** The allocator keeps two
separate tables, and the FX1 one is nowhere near a module's buffers:

| | bases | each | tops out at |
|---|---|---|---|
| FX1 | `0x1000 0x1c00 0x2800 0x3400` | 3,072 words | `0x3fff` |
| FX2 | `0x4000 0x8000` + the shared-window pair | 16,384 words | — |

Every FX2 buffer a module of ours pins starts at `0x4000` or in the shared
window, so an FX1 allocation **physically cannot reach one**. (It is also why
the reverbs are FX2-only in stock: they do not fit in an FX1 allocation.)

So of the seven, four cost you a row on one menu and the three reverbs are
lost outright — and only because FX1 never listed them in the first place.

A donor reverb states the budget you have left before it goes, because that
is arithmetic rather than a rule: the region is packed from PLATE upward, so
PLATE goes first and DARK survives while your modules stay under 1,657 words.
The three figures sum to exactly the 2,724 the build asserts, which is the
cross-check that keeps them honest.

Everything is derived where it can be — private Y scanned from the source,
caves and hooks counted from the manifest, the seven counted rather than
written down (it was four until the reverbs became listable).

⚠️ **Words used to read `build to measure`**, which was both jargon and
circular: the build only reports what it PLACED, so a module you had not
added had no number — and the cost is exactly what you want *before* adding
it. Every module of ours is now assembled once beside SEND (0.19 s each,
~2 s for all eleven) in a background worker at startup, cached to
`out/_audition/words.json` against the newest module source, and re-measured
when you edit one.

### The budget, standing under the effect

The third column is two stacked panes: the selected effect, and **what is left
of the image** under it. Every other number is read against this one — "500
words" means nothing without "and 313 are free" — and it used to be something
you inferred from a refusal.

```
Budget
 words A   ###################.    74 free
 words B   ####################     5 free
 FX2 buf A ####################  0 of 4  tracks 5-8
 FX2 buf B ##########..........  2 of 4  tracks 1-4
 rows      10 of 31 (the long chooser cave)
 cave      2,202 B free
```

**Every row is: what exists, minus what this selection loaded.** Nothing is a
constant and nothing is a leftover from an earlier build. Four scarce things
and only four — the **two donor regions** (one per payload), the **FX2 buffer
slots** per core, the **chooser rows**, and the **ColdFire cave**. Everything
else is unbounded in practice.

⚠️ **A listed reverb is LOADED.** The build reports the whole 2,724 as free
because nothing of *ours* is placed yet — but PLATE, SPRING and DARK REV's
code is what occupies the region, so a reverb you keep in the chooser is
spending its own words. A stock chooser holding all three therefore has **0
free**, not 2,724, and the row names the one you would lose first.

⚠️ **One place the plain subtraction is too generous.** The region packs from
PLATE upward, so holding a *low* reverb makes the space above it unreachable
even though it is unoccupied — keeping PLATE alone leaves 2,130 words by size
and **0 you can actually place**. The figure shown is the placeable one; it
equals the subtraction for every other combination (checked for all four).

⚠️ **The buffer rows count what a MODULE pins, not slots in use.** ChonVerb
holds all four of its core's, BongDelay two of its core's, Nimbus two of
whichever core hosts it. A **stock** effect never appears there: it takes a
slot from the allocator *at runtime*, per instantiated effect per block, which
no image can reserve — and that runtime contest is exactly what the ledger
refuses a pinner beside an allocating stock effect for.

The four slots are drawn as four groups so the picture and the number agree,
and the number says what it counts: `0 pinned of 4`. Two earlier forms were
worse — `4 of 4` against an empty bar says "all four used" and meant the
opposite, and `4 of 4 free` still invited "free for *what*?".

⚠️ **A stock chooser reports its real figures, not `????`.** A stock row
places no code — no clone, no words, its dispatch is already in the image —
so a selection with no modules of ours uses **zero** of either donor region
and leaves the cave untouched, and no build is needed to say so. The `????`
only ever appeared there, because that is the one selection the build
refuses:

```
 words A   ....................  2724 free  = the 3 reverbs' code
 words B   ....................  2724 free  = the 3 reverbs' code
 FX2 buf A .... .... .... ....  0 pinned of 4  tracks 5-8  +7 stock share
 rows      14 of 31 (the long chooser cave)
 cave      untouched — nothing of ours is placed
```

⚠️ **"Free" does not mean empty, and stock is not idle.** The donor region is
never unoccupied — it holds PLATE + SPRING + DARK's own code, which is
*why* it is the donor region. `2724 free` means "yours to overwrite", and the
row says whose code that is. Likewise `0 pinned of 4` is true and would read
as "nothing is using these": every allocating stock effect in the chooser
takes a slot **at runtime**, so the row names how many are waiting. What stock
genuinely does not touch is the **cave** (free space we found) — and it does
use **rows**, 14 of 31.

⚠️ **A selection that cannot build reports `not built`, not the last one's
numbers.** `State.forget_build()` drops them when the selection stops being
buildable — a budget that silently belongs to the image you had two edits ago
is worse than no budget at all. Rows are countable without a build, so they
are still shown; the cave and the words are not.

⚠️ **A build that FAILS still reports what it got to.** `measure()` used to
return the moment the return code was non-zero, so every build-derived number
kept the last *successful* build's value — a failed selection showed the
budget of an image it was not. It parses the report first now, and a failure
is usually still informative: a chooser-row refusal happens *after* the
region line is printed, so `726 used, 1998 free` is exactly the fact that
tells you the failure is not about space. Only the payload the build reached
is shown.

The pane dividers run the **full height** of the screen: a `Static` is only as
tall as its text, so they used to stop wherever the shortest column ran out.

### A / B compares two EFFECTS

Not "two renders ago against now", which is what the marks used to hold. `r`
hears the effect the cursor is on, `a` parks it as A, then point at the rival
and `b` — which **re-renders it on the same source** — and `,` / `.` flip
between them. That is the question a remixer exists to answer: *is mine
better than the one the box came with?* It is also exactly the question an
upgraded stock effect asks, which is why the pair is two effects rather than
two accidents of history.

**`SOURCE` is the first row**: `left`/`right` cycles the wavs in the source
folder, so choosing what you audition on is one keypress from the knobs. `r`
renders the effect over it and plays it; `space` replays.

**`d` points the source folder somewhere else** and remembers it in
`out/_audition/workbench.json`; `WORKBENCH_SOURCES` overrides both. The
default is `out/dry/`, the curated dry set — a good default, not a permanent
one, since a bench gets used on whatever material is to hand. A path that is
not a directory, or holds no wavs, is refused and the old one stands.

⚠️ **Six of the eleven stock effects render DRY at their defaults** —
PHASER, FLANGER, CHORUS and COMB sit at `MIX 0`, SPATIALIZER and DELAY at
`SEND 0` — so pressing `r` on one plays the source back unchanged, which
reads as "this effect does nothing" (it cost a report on 2 Sep 2026). **That
is faithful and is not fixed by seeding a different value**: stock defaults
are read from the firmware's own descriptor (`tools/remix/stock.py`), an
unmodified unit really does start them fully dry, and inventing a value here
would make the bench lie about the page it draws beside. The UNIT pane says
`⚠ MIX is 0 — this renders DRY` instead. None of *our* modules default this
way.

**Stepping knobs**: `left`/`right` is ±1 and **`shift`+`left`/`right` is
±10**. Holding the key runs; ~280 steps/second is sustainable (below), so
key repeat is the limit, not the workbench.

⚠️ **Holding an arrow key used to lag, and the cause was the emulated
panel.** `rerender()` called `render_fx2` on *every* keystroke — 15–96 ms,
mean 32 (`render_fx1` 16, `render_menu` 8; measured 2 Sep 2026) — plus three
independent `problems()` calls at 2.4 ms each. Under key repeat the work per
key exceeded the repeat interval, so the UI fell behind the held key and kept
stepping after release; single presses always felt fine, which is why it
presented as "slow when holding" rather than as latency. **Nothing a keystroke
does can change that picture** — knob *values* draw as dial graphics the
string-capture hook cannot read — so the panel is now cached on (page,
effect id, build) and `problems()` is computed once per pass. Measured
A/B: **18.1 ms → 3.6 ms per step, 55/s → 281/s.**

Below that, `p` cycles the **preview** in the unit's own order — `FX1`,
`FX2`, then `MENU` — showing the firmware's own draw of that page.

⚠️ **The FX and MENU page entry points TOGGLE**: calling one opens the page,
calling it again closes it, so consecutive renders used to alternate between
a full screen and an empty one (26 draws, 0, 26, 0). A workbench that
re-renders on every keystroke therefore showed a blank LCD about half the
time, and the MAIN MENU never drew at all — FX2 is the default view, so the
menu render was always the second call and an FX page had already taken the
window. `emu_bringup` now re-issues the call when nothing was captured
(`_call_page`, `_open_menu_window`). Found 2 Sep 2026 by rendering each view
four times in a row and counting the draws.

**The image follows the selection.** Every selection change rebuilds and
re-boots on a worker thread after a 0.35 s debounce, so the preview always
draws what LOADED says. There is no build key and no staleness to reason
about.

⚠️ This replaced a `stale()` gate that refused to draw when the image on disk
was not the selection, printing a bold `the image on disk is not this
selection / b builds it`. The gate's *reasoning* was right — the FX2 page
includes the firmware's own chooser list, so a stale image puts a different
set of effects on screen beside LOADED and reads as "why are those loaded?"
— but **every fresh launch is stale**, so the headline feature opened showing
a disclaimer, and what it was guarding is a **0.26 s build** plus a 4.6 s
ColdFire boot, both already on a worker thread (measured 2 Sep 2026). Changed
the same day: rebuild instead of explaining.

The build is `state.measure()`, which is the same `REMIX=x XBUS=1 SPEC=1
build_bus.py` that `make bus` runs and which parses the per-module word
counts out of the build report on the way past — so one call does what the
old `b` (build) and `w` (word cost) keys did separately. A selection that
cannot build is not drawn: the `⚠` line says why, and `c` still runs the full
`make check` with its log.

- **MAIN MENU** is the no-flash gate for ColdFire cave work — a patched-in
  top-level row draws here exactly as the unit would draw it.
- **FX1** shows that chooser as stock ships it, which is what FX1 rows would
  have to be added to.
- **FX2** draws the selected effect's page — *unless it is one of ours that
  is not in the image*, in which case it is deliberately not drawn. An id the
  image does not implement resolves to the fallback and the firmware would
  draw a convincing picture of the wrong effect (`CLAUDE.md`, 12 Aug 2026).
  Rare now that the image follows the selection, but kept: it is a real
  safety property, not a staleness message. A **stock** effect always draws:
  a remix that leaves one out does not remove it — its code, descriptor and
  dispatch stay stock and an old project that selects it still runs it; it
  only loses its chooser row.

The rebuild is 0.26 s and the boot 4.6 s (measured 2 Sep 2026), both on a
worker thread; a run of swaps costs one rebuild, not one per keystroke.

⚠️ **An untouched `stock` selection is not previewed, and that is not the
staleness gate coming back.** It genuinely cannot build: a remix must name a
fallback for the ids it does not implement, and no stock effect is a safe one
(it would *process* the unknown id) — `state.load_stock` is explicit that it
"should not pretend to". So the launch state says `stock — swap a module in
to build it` rather than `⚠`, because it is where the bench opens, not a
mistake. One swap resolves it: SEND comes with the first module of ours.

Honest limits (`docs/EMU.md`): no audio and no key matrix in the emulator —
navigation is poking state and re-calling draw functions. Knob **values**
draw as dial graphics the string-capture hook cannot read, so the numbers in
this pane are the truth for values, not the picture. In a SPEC image the
delay's DSP in payload A is the SEND alias, so its page can draw empty.
Item-level menu descent needs the real key handler (`FUN_40064e64`) and is
not built. The PLAYBACK page render was dropped with the rig — it proved the
detour could draw a non-FX page and had no role in composing an image.

## The audition backend

`tools/remix/audition.py` is the one render entry point; the UI never knows
which harness ran. All knobs are addressed by **manifest names** —
`Module.knob_map()` (schema.py) is the single source of the name→slot map.

| effect | path |
|---|---|
| chonverb | `tools/render_reverb.py` — manifest slot → its positional param name (the two tables are proven slot-aligned by the selftest); MODE via `--mode`, wet via `--wet` |
| bongdelay | the DEV hatch (`DEV=1 XBUS=1` build → `out/dsp/mem_dev_A.mem`, rebuilt when stale) then `send_probe --layout DS --in … --wav …` |
| inserts | a per-insert scratch image (`_audition` remix = the insert + SEND), dumped to `out/dsp/_audition_<name>_A.mem`; the build saves and restores `out/mainos_bus.bin` so the EMU view never silently boots a scratch |

Knob overrides ride `send_probe --set=NAME=VAL` (one token — the delay's
`-VRB` begins with a dash), resolved through the rendered module's own
`knob_map()`; an unknown name dies rather than driving the wrong slot.

**The SEND-alias guard is general.** An id absent from an image dispatches
to the fallback, which renders a *plausible dry passthrough* — peak equals
the input amplitude, THD at the noise floor, no error anywhere (this cost a
session on 12 Aug 2026 and was reproduced live on 31 Aug with `--pick B`
against a chongbong image). `send_probe` now refuses to render **any**
module whose dispatch entry equals SEND's.

Renders land in `out/_audition/`.

## The journal

Every render — and every A/B mark — appends one JSON line to
`out/_audition/log.jsonl`:

```json
{"t": "2026-08-31T12:45:41", "event": "render", "label": "T5",
 "effect": "chonverb", "source": "bass.wav", "wet": false,
 "knobs": {"TIME": 80, "...": 0}, "out": "T5_bass_chonverb_BIG.wav"}
```

That makes a listening session addressable: "this sounds boxy" plus the
journal tail is a full repro — track, effect, source, every knob. It is
also how demo takes get captioned after the fact.

## Knob values

Values live **per module**, in the session, seeded from that module's
manifest defaults the first time you look at it. They are a bench fixture,
not a firmware statement: a remix file says what the image *contains*, never
what the operator had a knob set to. Nothing about them is written into the
image, and a render is the only thing that consumes them.

⚠️ `out/_rig.json` and the per-track rig it persisted are **gone** (2 Sep
2026). Eight tracks with an effect on each was a second place to say what a
remix already says, and it forced a knob set per track when what an operator
actually tunes is an effect. An old `_rig.json` on disk is inert and can be
deleted.

## Colour

Colour carries meaning here; it does not decorate. Three axes, and nothing
else gets any:

| what | colour | why |
|---|---|---|
| **whose it is** | aqua `#8ec07c` = one of *ours*, plain = the box's own | in a remixer this is what you scan for, and nothing carried it |
| **state** | green `#b8bb26` fits · ochre `#d79921` is a trade or caution · red `#fb4934` blocks | the free-word count is coloured by its own answer |
| **a knob's level** | a warm ramp, green → ochre → orange `#fe8019`, by where the value sits in its own range | the variety comes from the values, so a row's colour means something |
| **the source wav** | muted blue `#83a598` | what you are auditioning on, distinct from what you are auditioning |
| **one-of-a-kind** | soft purple `#d3869b` | `◀fb`, the fallback |
| **the panel** | grey `#665c54` frame | chrome, so the firmware's own words stay plain |

The free-word thresholds come from what this project actually lives with:
payload A has shipped at `FREE 4` and B at `FREE 5`, so **double digits is
already spent** and gets the alarm colour; over 400 is comfortable.

⚠️ **These were ANSI names first, and that was wrong twice over.** `cyan`
rendered as `#00ffff` and `yellow` as `#ffff00` — Rich resolves a colour NAME
to its standard value rather than delegating to the terminal, so the "it
wears your palette" reasoning did not hold, and against a warm dark ground it
read as a wall of electric blue. They are gruvbox's own tones now.

**No red in the knob ramp**, deliberately: a filter cutoff at full is not an
alarm. And the bars were briefly *neutral* — one flat tint across twelve rows
made the accent the largest thing on screen and told you nothing, but taking
the colour out entirely went too far the other way. Grading them by value is
what makes them worth colouring at all.

## Editing in another window

**The bench follows the source.** Edit a module's `.asm` or manifest in your
editor, or build in another terminal, and the image rebuilds and the panel
re-boots on its own — the status line says `module source changed —
rebuilding`. Polled, not watched: one stat sweep of `modules/` is **0.7 ms**,
so a 1.5 s tick costs nothing and a filesystem-event dependency is not worth
adding to a venv that already carries unicorn and textual.

Audio is **not** re-rendered on a source change — it plays out loud, and
firing on every save would be intolerable. The image and the panel refresh;
`r` is one key.

## Theming

The app renders in the **terminal's own 16-color ANSI palette** (Textual's
`ansi-dark` theme), so it wears whatever colorscheme the terminal wears,
background included. `WORKBENCH_THEME=<name> make remix` picks any
built-in Textual theme (`gruvbox`, `nord`, `tokyo-night`, `textual-dark`
for Textual's stock look, …); unknown names fall back to `ansi-dark`.

## Architecture and guarantees

The UI is a shell; the model layers are headless and importable:

| layer | file | job |
|---|---|---|
| composer | `tools/remix/state.py` | selection, `problems()`, `measure()`, scratch builds (extracted unchanged from the old TUI) |
| tracks | `tools/remix/rig.py` | category + track-range derivation, per-track state, knob docs/labels/maxima |
| rendering | `tools/remix/audition.py` | the per-effect dispatch above, the journal, a `__main__` for headless renders |
| shell | `tools/remix/app.py` | Textual only — screens, keys, workers |

Categories and track ranges are **derived from manifests**, never declared
in the UI: `harness.is_server` + `dsp.payloads` (each server declares its
single payload; a server without one is refused, not guessed at) →
SERVER/T5-8 or T1-4; `DSP_EFFECT` with a menu → INSERT/any track;
`Kind.STOCK` → STOCK/any track (no knobs, no render); everything else →
SYSTEM/no track.

Three `Param` fields exist purely for the workbench and are **proven
display-only** — `scripts/refhash.sh check` ran bit-identical (26/26)
after each manifest change that introduced them:

- `payloads` (on `DspSection`) — the server's core, hence its tracks.
- `doc` — the one-line "what is this knob?" shown under the cursor.
- `labels` — per-value labels for a stepped select (length pinned to
  `count` by the schema).

`tools/remix/selftest.py` (in `make verify`) holds the lines: the
category/track-range derivation matches the measured facts for every
module; a payload-less server is refused; chonverb's manifest slots stay
aligned with `render_reverb`'s positional table; and **every named, drawn
param of every menu-bearing module must carry a `doc`** — an undocumented
knob fails the build's checks.

UI regressions are caught headlessly with Textual's Pilot (`run_test`):
scripts drive keys and assert on rendered text. The markup-artifacting fix
(PR #42 — literal `[x]` parsed as a Rich style tag and bled styling across
rows) is pinned that way; anything data-driven that reaches markup goes
through `rich.markup.escape`.

## Known gaps

- DELAY (stock) has no local render (ColdFire-side); LO-FI renders at
  +6 dB at zero settings (unexplained).
- A/B marks attach only to the most recent render (no history cursor).
- The source picker takes one directory at a time (`d`), not a tree —
  no recursion into subfolders and no in-TUI file browser.
- Wet-only rendering is ChonVerb-only.
- The emulator limits listed above (values, key injection, delay page
  under SPEC).
