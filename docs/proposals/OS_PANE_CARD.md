# What each image IS: a card in the image, and a pane that reads it

A follow-on to OS SWITCH (`modules/os-switch`, on an MKII 29 Sep 2026,
`docs/proposals/FIRMWARE_SWITCHER.md`). MAIN MENU > OS lists filenames;
this says how it could say what each file *is*. Nothing here is built.

Confidence markers as `docs/firmware/CHIP.md`: ✅ measured (under the
ColdFire port, or read from the user's own image by disassembly — the two
are named where it matters), 🟡 inferred, with what would falsify it, ❓
open, with what would answer it.

---

## 1. What changes for the player

Today the pane is two headings and a list of names
(`modules/os-switch/README.md`): `NOW OCTABAM14`, `HOME OCTABAM14`, then
`BASE1`, `BSRETVEC`, `STOCK140`. Which of those has the reverb? Which one
was the good one? The names are whatever you typed into `make obi`.

With a card:

- **the highlighted row says what it is** — its build, its date and how
  many modules it carries, and eventually which ones;
- **an image not built here says so, truthfully**: stock 1.40C carries no
  card and the pane says `NO CARD`, not a guess;
- **nothing else changes.** The list, the dialog, the switch and every
  refusal are the ones already on the unit.

The end state is a two-panel pane: the file list on the left, the
highlighted image's details on the right. The recommendation (section 7) is to get
there in two steps, because the two halves of the work have very different
risk.

---

## 2. The easy half: a stock-style two-box screen already runs here ✅

`modules/tempo-bus` (sambanks) draws exactly the screen this pane wants,
from stock's own primitives, and it is the template. Measured under the port
(`verify_set`) and carried by image 88 on Sam's MKII.

What it reuses, and how:

- **the window.** Two `Poke`s widen stock's TEMPO window from 73 × 48 to
  **118 × 64, "the menu window's"** (`modules/tempo-bus/manifest.py`, the
  `pokes=` pair on `0x40059F04` / `0x40059F08`). So the menu window's size
  is a measured 118 × 64.
- **the draw.** A `Detour` on the TEMPO draw (`0x4004B528`) replaces stock's
  big-digit render with its own, and the opener (`0x40059F2C`) and close
  (`0x40056930`) push and pop an input layer (`LPUSH 0x40031494`,
  `LPOP 0x4003146c`, `tempobus.s:38-39,75,87`).
- **the primitives, all of them stock's, and all of them calls the stock
  CONTROL INPUT (`0x40065674`) and MIDI SYNC (`0x4006730c`) screens already
  make** (`tempobus.s:27-31`):
  | routine | signature as tempo-bus calls it |
  |---|---|
  | titled box `0x4007efd0` | `(surf, x, y, w, h, title, 0, focused)` |
  | text `0x40012bd8` | `(font, surf, x, y, limit, str)` |
  | text width `0x40012f30` | `(font, limit, str) -> pixels` |
  | rule `0x40011910` | `(surf, x, y, x2, 1)` |
  | invert bar `0x40012254` | `(surf, x1, y1, x2, y2, -1)` |
  | icon `0x400128a8` | `(icon, surf, x, y)` |
  the font is `0x400ba876`, the small UI one.
- **the geometry** (`tempobus.s:63-65,323-338`): boxes **53 wide × 41 tall
  from y 4**, box *n* at **x = 57n + 4** (so x 4 and x 61, ending at 114);
  **5 rows per box at a 7-px pitch** from y `BOXH-7` = 34; each row's name
  at `boxx+4` and its value right-aligned at `boxx+BOXW-3`; the invert bar
  spans `boxx+3 .. boxx+BOXW-3` over 7 px.
- **the interaction.** UP/DOWN move the cursor in the focused box,
  LEFT/RIGHT switch boxes, **and each box keeps its own cursor and scroll**
  (`SEL`/`SCR`, one byte per box). That is precisely the two-panel
  behaviour this pane needs.

So the drawing is a solved problem with a working precedent in the tree.

### And the pane we already have has a right column ✅

Read here from the user's image, 29 Sep 2026: the menu draw/nav body is
`0x40064908..0x40064fb2` (`docs/firmware/MAINMENU.md` section 4) and the child
pane's row loop is `0x40064a76..0x40064af0`:

- the **label** is `0x40012bd8(font 0x400ba876, surf, x = 0x37 = 55,
  y, limit = 0xf = 15, rows[i]+0x00)`;
- then, **if `rows[i]+0x0c` is non-zero, it is called and its return is
  drawn** as `0x40012bd8(font, surf, x = *(surf) - 17, y, limit = 0xe = 14,
  d0)` — the "right-column value getter" `MAINMENU.md` section 1 names;
- `y` starts at 47 (`moveq #47,%d3`) and steps **−7 per row**;
- the loop draws `min(descriptor+0x14 count, descriptor+0x10 visible)` rows.

**So a 14-character right column per row already exists and is already
drawn**, for every visible row, on every draw, with no new drawing code at
all. ❓ its x: `*(surf) - 17` is 101 if the surface's first long is its
width (🟡 — tempo-bus uses `a5@` as the rule's right edge,
`tempobus.s:274-286`), which leaves about five glyphs before a 118-px right
edge, not fourteen. What would answer it: draw a 14-character value on one
row and render the frame (`ot_emu --lcd`, `tools/emu/lcd_view.py --png`) and
count the glyphs.

---

## 3. The hard half: an `.OBI` says nothing about itself

An `.OBI` is the raw image the bootstrap would depack to `0x40000400`
(`tools/build/make_obi.py`) — Elektron's OS with our changes. Nothing in it
says which modules a build carries. The three things the unit can already
learn from a file are the three `make_obi` and `osw_load` check: the entry's
first instruction (`OS_FIRST 0x4fefffe4`), the length, and the bootstrap
version word at `OS_VEROFF` (`modules/os-switch/osw.inc`). None of them is
an identity.

So this proposal is really about a **card**: a small record the build
embeds in every octabam image, at an offset the pane can find.

---

## 4. What goes in the card, and how big it can be

### The line budget, measured ✅

The small UI font `0x400ba876` is a 20-byte metrics record: default advance
3, height 6, yOffset 1 (`docs/firmware/PANEL.md` section 2), width table
`0x400c246a`, per-glyph offsets `0x400c256a`, bitmaps `0x400c276a`. Read
here 29 Sep 2026 from `out/raw/section_3_MAIN_OS.bin`: **every `A`–`Z` and
`0`–`9` advances exactly 3 px**; space 2, `.` 1, `-` 3, and the separator
glyph `0x17` 3.

Hence:

| field | pixels | uppercase glyphs |
|---|---|---|
| a tempo-bus box's text field (53 wide, text at +4, right edge −3) | 46 | **15** |
| the existing pane's label (x 55, limit 15) | 45 | **15** (the limit and the pixels agree) |
| the existing pane's right column (limit 14) | ❓ (section 2) | 14 claimed |

**15 characters a line is the budget**, in the pane today and in either box
of a two-panel version.

### Module keys against that budget ✅

From `registry.modules()` and `registry.remix()` (read here 29 Sep 2026):
61 modules; key lengths 4–29 characters, median 10; **8 of the 61 are over
15** (longest `USB AUDIO OUT TRACKS MAIN CUE`, 29). A remix carries 2–29
modules across the 43 remixes: `base` 15 (132 B of keys with NULs),
`bottleservice-ret` 25 (304 B), `mods` 29 (318 B).

Two consequences, and they pull in opposite directions:

- **512 bytes of card holds every remix in the tree today** (318 B of keys
  plus a header). There is no space problem.
- **8 of 61 keys cannot be shown on one line.** So either the card carries
  a short form per module (a new field every manifest would have to supply
  — note `MenuEntry.abbr` is a 5-byte / 4-character field and only DSP
  modules with a page have one), or the pane truncates and **says** it
  truncated. Truncating is the honest cheap answer for stage 1; a short
  form is a change to 61 manifests and should not be bundled with this.

### The fields

```
magic   "OBAM"                      4    a fixed offset needs a magic anyway
len     the record's own length      2    so a longer card is skippable by an older reader
fmt     format version              1
name    the build's VERSION        13    A-Z 0-9 _ - , 12 + NUL, exactly make_obi's rule
build   BUILD                       2    one or two digits (build_bus.py:145-148)
remix   the remix directory name   18    <= 17 today ("bottleservice-rec-plen" is 22 -- see below)
date    ...                             see the refhash trap below
nmod    module count                1
keys    NUL-separated keys        rest    318 B is the largest remix today
```

Two snags found while writing that list, both worth having up front:

- `bottleservice-rec-plen` is 22 characters, so the remix name field is 23,
  not 18. Sizing a field from the longest thing in the tree today is how a
  name that exactly fills its field happens (`AGENTS.md`: `abbr`,
  `fullname`, a faulting PC of `"HELL"`). **Every field here is
  length-checked in the build, not trusted.**
- **a build date breaks `scripts/refhash.sh`.** It compares 24
  configurations' artifacts and build reports bit for bit; a field taken
  from the clock makes every artifact differ every day. So the date must
  either come from the build's inputs (the newest mtime of the selected
  manifests, or nothing) or the card must be excluded from the refhash
  comparison — and excluding it means the gate never proves the card is
  stable. Prefer a date derived from inputs, or no date at all.

---

## 5. Where it lives, and how it is found

What the build appends today, ✅ read from `tools/remix/platform_build.py`
and `tools/build/build_bus.py:1188-1346`: `LOADER_AT = 0x4010fdf0`
(`platform_build.py:21`) is the byte after the stock OS image — **image
offset `0x10f9f0` = 1,112,560, which is exactly the length of
`out/raw/section_3_MAIN_OS.bin`** ✅. The append is the linked loader
(`loader.S` plus every `Linked(loader=True)` unit — `chain.s` is one), the
payload table, and the packed DRAM runtimes. The boot site is poked to
`jsr LOADER_AT` (`platform_build.py:155`).

Measured `.OBI` lengths in `out/` today ✅:

| file | bytes | append |
|---|---|---|
| stock `section_3_MAIN_OS.bin` | 1,112,560 | — |
| `BASE1.OBI` (`base`) | 1,114,766 | 2,206 B |
| `BSRETVEC.OBI` (`bottleservice-ret`) | 1,195,525 | 82,965 B |
| `DSPRESET.OBI` (`dsp-reset`) | 1,112,560 | **none** |

The last row matters: a remix with no DRAM runtime and `os_switch=False`
appends nothing at all, so its image is byte-length-identical to stock's.
A card cannot be assumed to be "wherever the append is".

Three placements:

1. **The first record of the append, at the fixed image offset `0x10f9f0`
   (address `0x4010fdf0`).** One seek, one read, no file length needed, and
   a build check can assert the magic at a constant offset in every image.
   Costs: the loader's entry moves to its symbol (`octabam_bootstrap`,
   already in `platform_build._nm(elf)`'s symbols) and the boot poke targets
   that instead of the constant; and a remix that appends nothing today
   starts appending a card, with no loader behind it — so the card must be
   its own append step and the boot poke must only be written when there is
   a loader.
2. **A trailer at the end**, found from the file's length minus the record
   length. Touches no boot code at all. Costs: the reader needs the length
   (`FS_SIZE 0x46c8241e`, which `osw_load` already calls,
   `switch.s:652-657`) and a truncated copy reads as "no card" rather than
   as damage.
3. **Somewhere after the payload blobs** — a variable offset needing a scan.
   Rejected: nothing a gate can assert in one line.

**Proposed: (1).** Both (1) and (2) change every image's bytes, so the
refhash baseline is re-saved once the diff has been shown to be exactly the
card and nothing else (`AGENTS.md`, "If you change the BUILD rather than a
module").

**A seek is a hard requirement either way.** The FS vtable slots the module
uses have none — `FS_READ 0x46c82426` reads forward in 8-sector chunks — and
reading forward to `0x10f9f0` is out of the question (the chainloader's walk
over 1.1 MB costs ✅ ~8.9 M instructions, `verify_osswitch`). The buffered
file API has one: open `0x40016864`, **seek `0x4001660c`**, read
`0x40016564`, close `0x4001677c` (✅ named independently by ems-octakit and
octamax, `docs/firmware/SAMPLE_SAVE.md` section 5). ❓ its signature and whether it
works on these files. What would answer it: call it under the port on a
card file and read back a known byte at a known offset — one `--interactive`
`call` line.

---

## 6. Who reads it, when, and what that costs

The pane lists the root's `.OBI` files with the stock dir scan
(`DIRSCAN 0x4007f598`) at every MAIN MENU opening, from the detour at
`0x40064c32`; it keeps up to `NMAX 32` files and `NLEN 24` bytes of each
name (`switch.s:41-42,72-73`).

**Read every card once, inside `osw_scan`, into the module's own table.**
Not per cursor move: section 2 shows the right-column getter is called for every
visible row on every draw, so a card read there is up to seven file reads a
frame. A footer rebuilt at draw time has the same problem. Reading at scan
time makes the getter and the footer pure formatting from RAM.

- ❓ **the cost.** Up to 32 × (open + seek + read 512 B + close), at every
  MAIN MENU opening, possibly during playback. What would answer it:
  instruction counts across `osw_scan` under the port with a 1-, 8- and
  32-file card (`--pcwatch` on its entry and return), against the bare dir
  scan today. If it is large, the answer is to read a card lazily on the
  first draw that needs it and cache it for the pane's lifetime.
- **the risk to respect.** `osw_scan` borrows the stock dir scan's *global*
  64 KB name pool and its cache (`SCAN_STATE 0x460e76ac`,
  `SCAN_STATE_LEN 0x10154`) and puts them back byte for byte, because build
  15 on the unit listed through the browsers' pool and threw VEC:04 (PC
  `0x2007e788`) on a later file load — and the port did not reproduce it
  (`switch.s:173-186`). **New file opens go after the pool is restored**,
  never inside the borrowed window. This is the single most likely way for
  this feature to break a unit, and it is a hardware-only failure.

---

## 7. The honest unknown states

- **stock 1.40C has no card**, and neither does any image not built here,
  nor a remix that appends nothing (section 5). The pane must say `NO CARD`.
- **do not print `STOCK` from a length match.** 1,112,560 B identifies
  stock's length, not stock; a foreign build can match it.
- **a card is a claim the build makes, not a property of the code.** A
  hand-edited image keeps a stale card and the pane would repeat it.
  Binding the card to a hash over the image-without-the-card is affordable
  at PICK time — the switcher already hashes the whole file once for the
  mailbox (✅ ~8.9 M instructions) — and unaffordable per row. Stage 1 does
  not do it, and the pane should not imply the card is verified.
- three states, then: a card; a valid OS image with no card; and a file
  that is not an OS image at all, which `make_obi` and `osw_load` already
  refuse on three grounds (section 3) but the pane does not distinguish today.

---

## 8. Staging — the recommendation

**Stage 1: the card, and ONE line under the existing single list.** Same
metadata work, no second panel, no cursor handling, no input layer, no
menu-state table surgery.

Two shapes for that one line, both needing no new drawing:

- **(a) the row's own right column** (section 2): 14 characters per row, drawn for
  every visible row already, the getter formatting from the scan-time table.
  No cursor handling whatsoever. Blocked on the ❓ about its x.
- **(b) a footer**: an inert row at the bottom of the pane (15 characters)
  whose label is rebuilt from the descriptor's selection before each draw,
  by one detour inside `0x40064908..0x40064fb2` guarded on the focus pointer
  `0x400cbda8` (✅ `MAINMENU.md` section 4) so no other category is touched.
  Costs one of the pane's visible rows: `osw_list` ships `+0x10 = 7`
  (`switch.s:105`), two headings and an optional refusal line already take
  2–3, so the files go from 4–5 visible to 3–4.

**Stage 2: the two-panel pane, as a pure drawing change**, once the card
has earned a second panel.

Why this order. The card is the risky half: a build format that a gate has
to pin, a fixed image offset that a build change can move, and a card read
per file at menu-open time on a path that has already thrown VEC:04 once on
the unit (section 6). The drawing is the half with a working precedent — tempo-bus
runs it under the port. Staging puts the whole risk behind a change that
costs one line of screen and can be abandoned without losing anything, and
it produces the ❓ read-cost
measurement before any layout depends on it.

### The end state, in tempo-bus's numbers

- left box `IMAGES`, 53 × 41 at x 4, y 4: five names of ≤15 glyphs at a 7-px
  pitch, the invert bar on the selection.
- right box titled with the highlighted name: `BUILD nn`, the date,
  `n MODULES`, then the keys — **five lines at a time**, which for a
  25-module remix is five screens, so the right box needs its own cursor
  and scroll (tempo-bus keeps one per box) or a digest instead of a list.
- a header line and the rule above both boxes (`0x40012bd8`, `0x40011910`),
  as CONTROL INPUT and MIDI SYNC do.
- its own input layer (`0x40031494` / `0x4003146c`) and its own draw.
  ❓ **whether a menu category can hand its pane to an own draw.** The
  category's pane belongs to the menu engine; tempo-bus replaced a *window's*
  draw, which is not the same thing. `MAINMENU.md` section 3: the menu-state table
  `0x400cbdac` is 16 × 0x14 and all 15 usable states are occupied, and
  `busscreen` added a 17th by copying the table to a cave and patching three
  `lea` operands (tags 85–90 on the unit). What would answer it: try the
  draw detour first (guarded on `0x400cbda8`, as stage 1's footer is) and
  fall back to the 17th state.

---

## 9. Gates

**Build side** — a new `tools/verify/verify_oscard.py` in `make check`:

- every image the build writes carries a well-formed card at the fixed
  offset: magic, a self-consistent length, `fmt` known;
- its `name` equals the build's `VERSION` and its `build` equals `BUILD`
  (the same rule `make_obi.py` and `modules/os-switch/manifest.py:62-74`
  apply — this is where "the pane said `OCTABAM79` for `BASE1.OBI`" came
  from, and a card must not reintroduce it);
- its module list equals `registry.remix(<name>).modules`, for every one of
  the 43 remixes;
- every field is length-checked against its own capacity, with a case for a
  string that exactly fills it (the `abbr`/`fullname` family in
  `AGENTS.md`);
- the record is **byte-identical across two builds of the same remix with
  the same `BUILD`/`VERSION`**, which is the check that catches a clock-fed
  date before `refhash` does (section 4).
- `make_obi.py` prints whether the `.OBI` it writes has a card, so a
  card-less file is named rather than silently blank.

**Pane side** — `verify_osswitch`'s `ui` case gains a card holding three
files: an octabam image with a card, one without, and stock.

- the module's own table after `osw_scan`, by `--mem-dump`: three rows, the
  right names, the right module counts, and `NO CARD` for two of them;
- the scan's borrow-and-restore still intact (the existing check that the
  dir scan's cached extension is not `"OBI"` after the rescan);
- an assertion on `osw_scan`'s instruction count with a 32-file card, so a
  later change that makes the scan ten times slower is caught rather than
  noticed on the unit;
- **the pixels.** Today `verify_osswitch` asserts memory only — its 16
  checks contain no pixel check, and the screens in the OS SWITCH PR were
  rendered with `ot_emu --lcd` and `tools/emu/lcd_view.py --png` and read by
  eye. A pixel assertion is new work and needs no OCR: the plane is
  `0x46c7e0ea`, 1,024 bytes, 64 columns × 128 rows, 8 bytes per row, MSB
  left, and screen pixel (x, y) is column 63−y of row x
  (`tools/emu/README.md`, "The screen itself"); the expected string renders
  from the font's own width, offset and bitmap tables (`0x400c246a`,
  `0x400c256a`, `0x400c276a`) for a direct comparison.

**What none of them can see**: whether a real unit survives 32 card reads
inside a MAIN MENU opening during playback. Build 15's VEC:04 is precedent
that this exact path fails on hardware while the port stays green
(`switch.s:173-186`), so stage 1 is one flash, with the card read on and a
32-file card on it, before stage 2 is designed.

---

## 10. Not designed here

- What the card says about a module beyond its key. `Module.doc` is a
  sentence; author, `Proof` level and FX2 id are each a field, and none of
  them fits beside a 15-character name.
- A short form per module for the 8 keys that do not fit — a new manifest
  field, 61 files, and not this change.
- Reading the card from a computer. A magic at a fixed offset means a
  twenty-line script tells you what an `.OBI` is, which may be worth more
  than the pane and costs nothing extra; it also makes the card the answer
  to "which build is this `.bin` on my card?".
- Whether the card belongs to OS SWITCH or to the platform. Every image
  would carry one, including remixes that set `os_switch=False` and remixes
  that append nothing at all today.
- An MKI. Everything measured for OS SWITCH and TEMPO BUS is an MKII.
