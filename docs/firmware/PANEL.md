# The panel: surface, fonts, text and regions (OS 1.40C, MKII)

Read out of `out/raw/section_3_MAIN_OS.bin` (SHA256 `164f3122…`), base
`0x40000400`, on 16 Sep 2026, while chasing why the arranger greys a field
out. This is the part of `MAINMENU.md` section 8's "drawing primitives behind the
state table's draw functions" now read: enough to draw text, boxes and
shading of your own.

Static reading unless marked ✅. The one hardware fact is negative and cost
a flash: the formatting drawer's two spare arguments are **not** a shade
(section 3). `0x40012368` (section 4) was re-read from objdump on 16 Sep, by hand, not
run (🟡 where marked).

---

## 1. The surface — 128 × 64, four grey levels

The descriptor every UI call passes (`0x400bf10a`):

| offset | value | meaning |
|---|---|---|
| `+0` | `0x80` | width, 128 |
| `+4` | `0x40` | height, 64 |
| `+8` | `0x02` | **bits per pixel** |
| `+12` | `0x46c7e0ea` | the buffer every drawer writes |
| `+16` | `0x46c7ca38` | a second buffer |
| `+20`, `+24` | `0x90000000`, `0x10004008` | 🟡 unidentified |

Both buffers are 1,024 bytes = 128 × 64 ÷ 8: two 1-bit planes. ✅ `+12`
is the picture, and it is stored a quarter turn round: 64 columns × 128
rows, 8 bytes per row, MSB left, screen pixel (x, y) = column 63−y of row
x (rendered from a port dump under every candidate layout, 17 Sep 2026;
`ot_emu --lcd` + `tools/emu/lcd_view.py`, `tools/emu/README.md`). `+16` read as all
`0xff` after a boot and a load; the UI init at `0x40063264` clears both
with `0x40020950(buf, 0x400)` (a memset — ~~the refresh or DMA setup~~,
retracted 17 Sep) and then fills a 1,024-byte block from `0x40011804`
with `-1`. Every drawing routine below writes only `+12`. ~~What sends the
plane to the panel controller over UART1 (`0xfc064000`; the byte queue is
`0x40010aa4`) is not located.~~ Located 4 Nov 2026: the diff flush
`0x40013abc` composites the plane with the windows into a back buffer and
sends that (section 9, "The composite"). `+12` is the page layer only: a
window (MIXER, a menu, a SETUP window, a popup) is not in it.

## 2. Fonts — metrics records, no colour

A font is a 20-byte record. Two are in use:

| | `0x400ba862` | `0x400ba876` |
|---|---|---|
| `+0` default advance | 5 | 3 |
| `+4` `(yOffset << 16) \| height` | `0/5` | `1/6` |
| `+8` | → per-glyph width table | ← |
| `+12` | → per-glyph offset table (signed words; negative = absent) | ← |
| `+16` | → the glyph bitmaps | ← |

Read off the **width-measuring** routine `0x40012f30(font, limit, str)`,
which walks a string adding `+8`'s per-glyph widths, falling back to `+0`
when a glyph has none, and skipping glyphs whose `+12` word is negative.

There is no colour or level anywhere in the record.

Eight such records sit at `0x400ba812 … 0x400ba89e` (nordseele, 22 Sep
2026): `0x400ba876` is the small UI font, 506 literal references in the
image (✅ counted here), `0x400ba83a` a large one (29 references). The two
in the table are the ones the text routines use; the other six are not
decoded.

## 3. Text — one bit, ORed, no intensity

Two entry points, both ultimately the same blitter:

```
0x40013904(font, surface, x, y, a, b, fmt, args…)   printf-style
0x40012bd8(font, surface, x, y, limit, str)         a plain string
```

⚠️ **The `-1` that every call passes is a maximum character count**, not a
shade: the blitter compares it against a character counter at `0x40012cea`
and `0x40012da4`.

The inner loop:

```
40012caa:  mvz.w (%a1)+,%d0      ; a row of glyph bits
40012cb0:  lsr.l %d5,%d0         ; shift to x
40012cb2:  or.l  %d0,(%a0)       ; OR into surface@(12)
```

One bit per pixel, ORed in, always into the same buffer. Text drawing takes
no intensity. ✅ Confirmed negatively on the unit: a probe module
(`ui-dimprobe`, not in this tree) recorded the two spare arguments of
`0x40013904` (`fp@(24)`, `fp@(28)`) and they never varied with what was
dimmed.

### 3b. The SETUP windows' calls, for a page of one's own (nordseele, MKI, 15 Sep 2026)

Run on a MKI by octalab; each entry point re-read here as a function
prologue with the reference count shown ✅. `0x4005829c(115, 64, 0, 0, 1,
closed)` the window; `0x400125ac(surface, 0, 1)` its planes cleared as the
SETUP windows do; `0x400570b8(object, title, "")` the frame and title band
(5 refs); `0x40011b94(surface, x, y0, y1, 1)` a solid vertical line;
`0x40011a58(surface, x0, y, x1)` a dotted horizontal line, one pixel in
two (26 refs); `0x40012004(surface, x0, y0, x1, y1, 1)` a line drawn pixel
by pixel with the ink toggling (15 refs); `0x40013904(font, surface, x, y,
align, invert, width, fmt, …)` formatted text, align 1 centred / 2 right,
its box cleared first, `width` a template string sizing the box (the
stock's `"XXXX"` at `0x400b451d`) (128 refs). Not reconciled: section 3 reads
`0x40013904` as `(font, surface, x, y, a, b, fmt, args…)`, six fixed
arguments before `fmt`; nordseele's read has seven. The stock example is
EFFECT 1 SETUP (opener `FUN_40059afc`, descriptor `0x400bc25a`, draw
`FUN_4003792c`): a solid line at x `0x34`, dotted verticals at `0x48` and
`0x5c`, a dotted horizontal at y `0x1c`, 20-px cells, labels centred at x
`col·0x14 + 0x3e`, y `0x30 − row·0x1b`; y runs up from the bottom row.

## 4. Regions — where shading lives

```
0x40012368(ctx, x1, y1, x2, y2, mode)     dithered rectangle: set / clear / invert
0x40012254(ctx, x1, y1, x2, y2, …)        boxes and lines — 224 callers
```

`0x40012368` normalises the corners (swaps so x1 ≤ x2, y1 ≤ y2, clips to
the surface), builds a per-word column mask from `-1 >> (x1 & 31)` and
`-1 << (31 − (x2 & 31))` (MSB = leftmost pixel), and branches on the
**sign of `mode`**:

| mode | operation | at |
|---|---|---|
| `< 0` | `eor.l` — invert | `0x40012442` |
| `> 0` | `or.l` — set | `0x40012460` |
| `= 0` | `and.l` — clear | `0x4001247a` |

**Every mode is dithered.** 🟡 The per-row loop starts from `0xaaaaaaaa`
(`0x55555555` for clear) and re-applies `not` + `and mask` each row, so the
phase alternates row by row: a true 50% checkerboard, not stripes. There is
no solid-fill path in this routine; solid boxes are `0x40012254`'s.

That is the panel's grey. To grey an area, invert a checkerboard over it
(the arranger's cursor); to light it, OR one; to dim what is already drawn,
AND one — the glyph loses every other lit pixel and the background stays
black. XOR over a black background lights half of it (a grey box).

🟡 **The AND path clears outside its rectangle.** `0x4001246e..0x40012484`
ANDs the surface word with `mask & 0xaaaaaaaa`, where `mask` is the
in-rectangle column mask, so every pixel of the same 32-pixel word that lies
outside the rectangle is cleared too. Whether stock only ever calls mode 0
on word-aligned spans is not checked. An overlay that dims one knob cell
(≈21 px of 128, never word-aligned) cannot use it as-is; a cave-side
`and ~(mask & 0x55555555)` is the fix if the reading holds.

## 4b. The panel link: what the controller sends (18 Sep 2026) ✅ under the port

UART1 (`0xfc064000`, 312,500 baud, ISR `0x400109bc`, `KERNEL.md`) carries
the panel controller's events to the OS. The ISR rings each byte
(`0x46100b28`, 32 deep, count `0x460ffda0`) and forces INTC0 source 37,
whose handler `0x4009228c` parses:

| header | payload | meaning |
|---|---|---|
| `0x2n` | 1 byte | key row `n` (0..7): bit `b` = key `n·8 + b` held. The parser XORs against the row's last state (`0x46100b18[n]`) and queues one event per changed bit from the keymap at `[0x46c901dc]` (12-byte records `{01, code, 01, 00, queue, 0}`, the identity map, so **key code = row·8 + bit**; a second table at `+0x302` is selected while the header's FUNCTION row/mask matches — `0xff`/`0x80` in 1.40C, never) |
| `0x3n` | 1 byte | encoder `n`: signed delta (A..F = 0..5, LEVEL = 6); coalesced into a pending event's delta if one is queued |
| `0x40` | 1 byte | the MAIN pot, 0..255, scaled by the calibration at `0x1ffffa..0x1ffffe` (magic `0x1234`) to 0..127 → `0x40092fac` |
| `0x7n` | 9 bytes | copied to `0x46100b48` (pointer `0x46100b52`); the controller's identity 🟡 |

Key events go through `0x40000c3c(queue 0x460d17ae, event)` — 8-byte
records `{code, 0, pressed, 0, ticks}` in the ring at `0x46c9026c` — to
the UI task, which reaches `FUN_4005578c(code, edge)` for a page key and
the key layers `0x46c7d8de + code·0x18`. Keymaps are layers (octalab,
MKI, 13 Sep 2026 ✅): `0x40031494(map)` / `0x4003146c(map)` register /
remove a 20-byte map `{next, keys, encoders, 0, marker}`; rebuild
(`FUN_4003125c`) into keys `0x46c7d8de + code·0x18` and encoders
`0x46c7dede + enc·0x14`; last registered wins; −1 lets the layer below
through; a null encoder handler swallows the turn. The image's keymaps
(section 4c): the MKI layer `0x400c090a` → keys `0x400bfc10` (57 records, no
`0x1c`) and the MKII layer `0x400c091e` → keys `0x400c01f4` (62: the same
57 plus `0x1c..0x1f`, `0x36`); ✅ which one `0x40061bc4` pushes follows
`0x46c8d18c`. (Until 25 Sep 2026 this read "`0x400bfbf6` (59 records)":
`0x400bfbf6` is 0x1a before the table the MKI layer points at, inside the
record before it.) Record, 0x1a bytes: `+0 code, +2 press, +6 release,
+0xa, +0xe sub-map, +0x12, +0x16`; the table ends at a code `0xff`.
FUNC's sub-map field is a 20-byte layer map `{next, keys, …}`: MKI keys
`0x400bf2b4`, MKII keys `0x400bf628`. BRAIN rewrites the MKII keys pointer
at `0x400bfa36` to a DRAM clone (`brain_func_keys`) with LEVEL push added;
ROM patches of the stock MKII FUNC key table do not affect that clone
(SEQ's FUNC+BANK clear menu Detours TRACK TRIG EDIT `0x4007c0d0` instead).
MKI FUNC+BANK press still lands on `0x40058a64` (`PARTS.md`). Double press: `0x400c0aac` last keycode,
`0x460d5de0` ticks (display loop `0x40052204`, reset `0x40033e20`), window
14 ticks. LEVEL press `0x3e` special-cased at `0x4004ecfc`. Popups: yes/no
`0x4006d57c(title, n, lines[], 3, handler)`; scrolling list
`0x4006d94c(count, sel, arg3, labels[], handlers[])` / close `0x4006d754`
/ refresh `0x4006d784`; live object `0x460e5e28` = `{callbacks, labels,
object, &selection}` (labels pointer also `0x460e5e2c`). Grid recording
`0x460d1736 != 0`; audio editor `0x4006de34(type, slot)` + `0x4006e160()`.
Measured under
the port: `0x24 0x08` (row 4 bit 3 = `0x23`) switched the page kind to 2
and the plane redrew as AMP.

### CHANGE project list → FUNC+BANK (RENAME / DELETE) ✅

On **PROJECT → CHANGE** (`CHOOSE PROJECT`, string `0x400b5ce0`), with a
project row selected (not `<CREATE EMPTY PROJECT>`), **FUNC+BANK** opens a
2-row `LISTPOP` (RENAME / DELETE) instead of PATTERN SETTINGS / SELECT BANK.
Measured under the port 27 Oct 2026 (`MenuPort.chord("func","bank")` on the
CHANGE list; a bare `press("bank")` loads the project / shows CHECKING
PROJECT; `press("func"); press("bank")` without a hold can fall through to
SELECT BANK).

| piece | address | notes |
|---|---|---|
| opener (gated) | `0x40064180` | `tst.l 0x460e435a`; beq skips when no selection name |
| `LISTPOP` call | `0x400641a4` | `pea #2` count at `0x400641a0` (`4878 0002`) |
| handlers[] | `0x400cbaac` | `[0]=0x40064290` RENAME, `[1]=0x400641b0` DELETE |
| labels[] | `0x400cbab4` | `[0]=0x400b46c0` `"RENAME"`, `[1]=0x400b3891` `"DELETE"` |
| selection word | `0x460e1348` | passed as sel and `&sel` |
| selection name gate | `0x460e435a` | nonzero before the list opens |
| BANK key record | `0x400cbbcc` | code `0x2f`, press → `0x40064180` |

Labels are tails of longer stock strings (no abs refs to the short forms):
`"RENAME"` is the tail of `"ARR RENAME"`, `"DELETE"` of `"DIRECTORY DELETE"`.
A usable `"COPY"` tail sits at `0x400b3882` (`"DIRECTORY COPY"`). RENAME's
handler pea's `"RENAME PROJECT"` (`0x400b5c5c`) into `POPUP` `0x4006d57c`;
DELETE pea's `"DELETE PROJECT"` (`0x400b3984`). Growing this popup 2→3 is two
4-byte pointer slots plus the count immediate — see issue #931 / module
`copy-project`.

Key codes (octalab's list, plus the probe of 18 Sep 2026 under the
port, each code alone in a fresh session): trigs `0x00..0x0f`, tracks
`0x10..0x17`, PROJ (MKII) `0x1c`, PART `0x1d`, AED `0x1e`, ARR `0x1f`
(section 4c), DOWN `0x20`, RIGHT `0x21`, page keys
`0x22..0x26` (SRC, AMP, LFO, FX1, FX2), STOP `0x27`, PLAY `0x28`, REC
`0x29`, CUE `0x2a`, FUNCTION `0x2d`, PATTERN `0x2e`, BANK `0x2f`, YES `0x31`, NO
`0x32`, UP `0x33`, LEFT `0x34`, MIDI `0x35`, encoder pushes `0x38..0x3d`,
LEVEL push `0x3e`. KEYPROBE ✅ STOP is `0x27`, not `0x2a` as this list
said until 25 Sep 2026: under the port (`--mkii`, bamsep26 +
OCTABAM89_setgate) PLAY `0x28` turned LED row 11 from `0x01` (stop) to
`0x08` (play), `0x2a` left it at `0x08`, `0x27` put it back to `0x01`
(`KEYMAP.md` has 0x24.7 = STOP and 0x25.2 = CUE from route A); in both
keymaps `0x27` has one handler `0x4004aca4` for press and repeat, `0x2a`
a press and a release handler (`0x4004e978`/`0x4004e968`) and a sub-map
(`0x400bf2a0`), the held-modifier shape.

`ot_emu --live FIFO` feeds these bytes from text lines and
`tools/emu/lcd_view.py --panel FIFO` draws a control surface (`tools/emu/README.md`).
What the OS sends BACK on the same link (LEDs, the plane) is unread.

## 4c. The MKII: model flag, panel loader, report, keys (25 Sep 2026) ✅ under the port

What makes the firmware run as an MKII, and what the port (`ot_emu
--mkii`) models so that it does. Read from the image (base `0x40000400`)
and measured on bamsep26 + OCTABAM89_setgate staged as `verify_set.py`
stages it; scratch drivers in `out/_agents/mkii/` (gitignored).

**The model flag `0x46c8d18c`.** The panel-link init at `0x4001f834` sets
it to 1 (`0x4001f8ce`), then ten times writes `0x20` to GPIO
`0xfc0a403a` (bit 5 high), reads bit 6, writes `0xdf` to `0xfc0a4052`
(bit 5 low), reads bit 6; bit 6 not following bit 5 clears the flag
(`0x4001f910`, MKI). ✅ With bit 6 tied to bit 5 (`--mkii`) the flag stays
1. 28 `tstl` sites read it; among them the keymap push
`0x40061bc4`, the loader call `0x4001f976`, the `74 00` / `43` choice
`0x4001f982`, the crossfader poll install `0x4001f9d2` (MKI only:
`0x40010ce8(0x7a12, 0x40092f88 | 0x40092fac)`), the `60 00` at
`0x4001fa08`, the report check `0x40061c94` and the OS-upgrade refusal
`0x4007f87a` (MKII refuses an OS string ≤ `"0155"`, a panel with report
byte 4 = 22 one ≤ `"0177"`).

**The panel loader handshake `0x4001f4dc`** (MKII only; interrupts off,
polled on `0xfc064004` bit 0 / `0xfc06400c`): send `60 02 70 00`, read 5
bytes. `70 05 v ..` with `v` = the long at `0x400d81a4` (8 in 1.40C) →
send `60 00`, return 0. `70 05` with another `v` → reflash the panel from
the image at `0x400d81a8..0x400db3d4` (erase `80 42`, five `ff` back, then
5-byte `cmd addr32` writes echoed by the panel through `0x4001f40c`, up to
3 tries), return `v`. Any other reply → `60 00`, return −1. ✅ With nothing
answering, the port's TX stream stopped at `60 02 70 00` and the boot sat
in the polled read `0x4001f540` (interrupts off) until the first bytes
arrived on the panel line. Inferred from that: in the WIP port the first
key report was taken as the loader's reply (return −1), which is why the
boot then continued, the `74 00` went unanswered and "UI NOT TESTED!"
appeared.

**The report.** On an MKII the CPU sends `74 00` (`0x4001f98a`) where an
MKI gets `43`. The RX parser `0x4009228c` has one format for both models
(no reference to `0x46c8d18c`): header `0x7n` + 9 bytes → `0x46100b48`,
pointer `0x46100b52`. Readers: `0x40061c94` (byte 3 == 0 → "UI NOT
TESTED!" `0x400b4e17`; byte 4 == 22 → `0x46c8d188` = 1) and the system
page `0x400698a6` ("UI VERSION" `1.<byte 1>.<byte 4 == 22>`, format
`0x400b64e7`).

**What the port answers** (`ot::MkiiPanel`, `tools/emu/ot_emu/periph.h`,
on the far end of `Uart@fc064000`, the TX stream framed by the
section 9 opcode lengths): `60 02` enters the loader state, `70 00`
there gets `70 05 v 00 00` with `v` read from the image, `60 00` leaves
it; `74 00` gets `70 00 v 00 01 00 00 00 00 00` (byte 1 = `v`, byte 3 = 1
tested, byte 4 = 0). 🟡 The report's values other than byte 3 are chosen,
not captured from an MKII panel. ✅ Measured order: loader entered at
instruction 10,198,954, returned 0 at 10,199,051, report parsed
(`0x40092608`) at 10,199,687, checked (`0x40061c94`) at 45,935,951;
`0x40061cbc` ("UI NOT TESTED!") never runs; `0x46100b48` =
`00 08 00 01 00 00 00 00 00`, `0x46c8d188` = 0.

**Keys.** The MKII panel's key, encoder and crossfader reports are the
MKI's `0x2r` / `0x3r` / `0x40` (the parser has one format), so the key
code is still `row·8 + bit`. What differs is the UI layer: the MKII key
table `0x400c01f4` = the MKI's `0x400bfc10` + five records:

| code | matrix | handler | measured under `--mkii` |
|---|---|---|---|
| `0x1c` | `0x23` bit 4 | `0x40064d78` | PROJ: the PROJECT menu (PROJECT / SYSTEM / CONTROL / MIDI) |
| `0x1d` | `0x23` bit 5 | `0x4002e7c8` | PART: the part chooser (ONE / TWO / THREE / FOUR) |
| `0x1e` | `0x23` bit 6 | `0x4006e274` | AED: the audio editor (`STATIC 001`, TRIM SLICE EDIT ATTR FILE) |
| `0x1f` | `0x23` bit 7 | `0x40058ab8` | ARR: the arranger menu (`ARR 1:` EDIT RENAME CHANGE CHAIN CLEAR SAVE RELOAD) |
| `0x36` | `0x26` bit 6 | `0x40030a6c` | REC3 🟡: beside REC AB `0x2b` (`0x40030e6c`) and REC CD `0x2c` (`0x40030c60`), same sub-map `0x400b9e02`; nothing drawn on a STATIC track |

PAGE is code `0x1b` (`0x23` bit 3), the MKI's SCALE key: the same handler
`0x4004ffc4` in both tables. ✅ FUNC + `0x1b` under `--mkii` draws
`SCALE, TRACK 3 64/64` (per-track scale). Every tap above hits the key
dispatcher `0x40031904` once (press) and the key-row path `0x400923c0`
twice (press, release), in both models; under MKI the same `0x23.4-7`
taps draw nothing (the MKI table has no record for them). Also measured
under `--mkii`: YES on the date prompt (`DATE/TIME STORED`), T2 then T1
(`0x80000000` 1 → 0), knob A +3 on T3's SRC page (`0x40170fc6` and
`0x800008a0` 64 → 66, PTCH draws `+0.4`), code `0x27` = STOP (above).

**LCD and LEDs under `--mkii`** ✅: the stream decodes with
`panel_link.PanelLink` as on an MKI (897 LCD blocks, 81 LED rows, 785 LED
levels after boot + 500 ms); new on the wire: `60 02 70 00`, `74 00`,
`60 00`, and 204 `0xb5` messages (`0x4003f430` called from
`0x40061af2` / `0x40061b22` only when the flag is set).

Where it is wired (the panel, `live.py`, the gates): `tools/panel/README.md`.

## 5. The cursor idiom — and the arranger's giant one

A screen highlights a cell by looking up its geometry in a per-type table
and inverting a rectangle around it. The arranger's (`0x40049896`):

```
a0 = x[type][column]            ; 0x400a775e
a1 = w[type][column]            ; 0x400a783c
pea -1                          ; mode: EOR
pea (1,%a0,%a1)                 ; x2 = x + w + 1
a0 = a0 - 1 - a1                ; x1 = x - w - 1
jsr 0x40012254
```

✅ **Those tables are (centre, half-width)**, not (left, width): the
arithmetic is symmetric about `x`, and a pattern row's column 0 (centre 12,
half 5 → 6..18) is a three-digit row number's span.

A REMINDER row appears to grey out when the cursor reaches its text column
because that cell is centre 82, half-width **38**: the inverted checkerboard
is 78 pixels of a 128-pixel line, against under 20 for every other cell on
every row type. Nothing is dimmed; XOR-ing a checkerboard over lit pixels
turns half of them off.

## 6. Greying a blanked parameter slot — what is still missing

A nibble-0 slot (`PARAM_PAGES.md` section 3b) draws an empty circle and `---` on
the unit (our image, 16 Sep 2026). To dim it with section 4 the following are
unread:

- which drawer puts the circle and `---` there and its per-slot geometry
  (x1, y1, x2, y2 for slots 0–5, pages 1 and 2). Candidates: the knob
  renderer `0x400479b4` and the list drawer `FUN_40037590` that calls it
  (section 3b's bit-2 reading), neither traced past the flags word;
- a hook site after the page draw and before the plane goes out over
  UART1 (the sender is unlocated), on every refresh; a one-shot overlay
  is redrawn away;
- a per-slot flag: every nibble bit is in use (section 3b: bit 1 = link bracket,
  bit 2 = the PLAYBACK page-2 layout flag, bit 3 = the scene-held XVOL);
- the cell geometry is a framebuffer read now: `ot_emu --lcd --live`
  with the page keys (section 4b) leaves a run on any page.

## 7. Not known

- `+20` / `+24` of the surface descriptor, and what `+16` (all `0xff`
  after a load) is for;
- how the two bits per pixel are composed for the display — every drawer
  here is 1-bit-per-pixel into one buffer, so the second bit comes from
  somewhere not yet found — and the UART1 sender;
- the window/geometry descriptor internals `MAINMENU.md` lists, a layer
  above these primitives.

## 8. Timers, LEDs and the UI tick (measured under the port, Tim Hastie, 12 Sep 2026)

From the panel work; the investigation logs are
`git show f5148320:tools/panel/KEYMAP.md` (the 12 Sep sections).

- **The OS image loads at `0x40000400`.** The file's offset `0x13220` is RAM
  `0x40013620`; a static scan adds 0x400 to file offsets and nothing to
  absolute operands.
- **The DMA timers.** DTIM0..3 at `0xfc070000 + 0x4000*n`, INTC0 sources
  32+n, clocked from the 132 MHz internal bus:
  - DTIM1: DTRR 68750, DTMR 0x1d = 8.333 ms, 120 Hz. Its handler
    `0x40055cb8` (vector 0x61) signals `0x46c7e0e2`, which the LED/key-scan
    task at `0x4005593c` pends on, and on every second tick posts `0x01` to
    the UI queue `0x460d1664` and `0x05` to sys: the firmware's 60 Hz UI and
    sys ticks.
  - DTIM2: DTMR 0x13, DTRR 132,000,000, free-run: the one-second idle poll
    of the MIDI note-length scheduler `0x400409f4`.
  - DTIM3: DTMR 0x0b, bus/1, no interrupt: a free-running timestamp. The
    boot logo loops until `int(DTCN3 / 660000.0) > 559` (2.8 s).
  - DTIM0: DTMR 7 = the DTIN0 pin: the MIDI RX ISR timestamps 0xF8 with it
    (`0x4001070a`).
- **LEDs are countdowns.** `set_led(id, n)` (`0x40013784`) writes n into a
  per-id countdown (`0x460ba9cc`, 136 longs), sets the bit in `0x460ba9ae`
  and flushes; `set_led_timed` (`0x400136f4`) adds instead. `0x4001387c`
  decrements every 120 Hz tick and clears the bit at zero. The beat LED is
  `set_led(38, 3)` from `0x40056f2a`, once per beat.
- **The trig-LED running light follows the UI's current track.** The pass
  `0x40043fdc` clears ids 0..31 and draws one pair for the track at
  `0x80000000` (+8 on the MIDI side), if `0x4009b290(track)` says running.
- **PLAYS FREE is the pattern byte `+0x54` per track** (`0x400e2234 +
  2330*t`). FW_TRANSPORT(0) (`0x4009b964`, the PLAY key's path) sets a track
  up only if it is zero; FW_START_TRACK(t) (`0x4009b5c8`, the trig-key
  start) acts only if it is set. Its UI writer is an encoder toggle for the
  current track (`0x400824fe`).
- **The popup slot `0x460d175c`** names the open popup record
  (`0x46c7d34c` for every popup the panel opens), a geometry: +0x08 x0,
  +0x0c y0, +0x18 x1, +0x20 flags (0x21 open, 0x01 closed), +0x28 rows. The
  page SETUP windows share x 7..0xf4, y 0, 0x40 rows; the PROJECT menu is
  5..0xf6, the MIXER 10..0xec, TEMPO 0x1c..0xca.
- **The boot mounts the last set.** The sys tick's startup step
  (`0x40052200` .. `0x4007ec5a`) reads the set name at `0x100f8480` after
  the media case; empty, it opens `NO SET IS MOUNTED!` over SET DATE/TIME.

## 9. The CPU → front-panel link (UART@fc064000), in detail

What the MAIN OS sends to the panel microcontroller, decoded far enough to
draw the LCD and the LEDs from the byte stream alone. Decoder:
`tools/panel/panel_link.py` (`PanelLink`, pure stdlib). Read 11 Sep 2026
from `out/raw/section_3_MAIN_OS.bin`; measured against route-A captures
(`rt.uart64.tx`) of a boot on an empty card, MIXER open/close, an encoder
turn, PATTERN SETTINGS, cursor-right, a trig key and a track key.

### Image base, first

The file loads at **0x40000400** (`emu_bringup.BASE`, a 0x400 header), so
`m68k-elf-objdump ... --adjust-vma=0x40000400` is the listing whose
addresses match the firmware's own `jsr` operands; every address in this
file is from that listing. With `--adjust-vma=0x40000000` the same code
sits 0x400 lower and every routine below lands mid-instruction (0x40010b1c
is then inside a `clrl`), which is how the earlier "0x10 <chunk>" reading
went wrong. (Until 11 Sep 2026 the producers table below quoted the ring
writer / byte pusher / drain as 0x4001071c / 0x400106a4 / 0x4001064c: those
are the 0x40000000-listing addresses of the same three routines, 0x400 low;
in the 0x40000400 listing the first two are mid-instruction and the third
is an unreferenced `bgtw`.)

### Producers: every path onto the wire

All traffic on the panel UART comes from six places (reference counts are
`grep -cE '0x4001....\b'` over the 0x40000400 listing):

| routine | what |
|---|---|
| `0x40010b1c` ring writer `(len, ptr)` | `moveal %sp@(16),%a2`, spins while the ring count `[0x400b96cc]` > 2046, pushes `len` bytes into the 2 KB ring at `[0x400b96bc]`, arms the TX interrupt (`UIMR := 3`). 5 references: `0x40013a6e` (clear), `0x40013d20` (flush), `0x4001f99e`, `0x4001fa1c`, `0x400926c6` |
| `0x40010aa4` byte pusher `(byte)` | one byte, same ring. 12 references; every builder loads it with `lea 0x40010aa4,%aN` and `jsr %aN@` |
| `0x40010a4c` polled drain | spins on TXRDY (`0xfc064004`) and empties the ring. 9 references: boot LED animation `0x4006308a`/`0x40063102`/`0x40063186`/`0x400633bc`, `0x4000fa86`, `0x4007fcfc`-`0x40080152` |
| `0x400109bc` UART1 ISR | drains the ring on TX-ready, hands RX bytes to `[0x460ba980]` |
| `0x4001f40c`, `0x4001f4dc` | boot-time polled handshake, direct `UTB` writes; the MKII panel loader (flag `0x46c8d18c`, `docs/firmware/PANEL.md` section 4c), taken under `ot_emu --mkii` |

Every message builder takes the mutex `0x400b96f4` (`0x40010db0` lock,
`0x40010d90` unlock) around its pushes, so messages never interleave: the
first byte of a message decides its length and nothing else is needed to
frame the stream.

### Opcode table (first byte -> length)

| first byte | len | builder | message |
|---|---|---|---|
| `0x10`-`0x17` | 10 | `0x40013abc` diff flush, `0x40013a24` clear | **LCD block**: `page = op & 7`, then the column start (only 0, 8, ..., 120: both builders step it by 8 to 128, `0x40013a92`/`0x40013d38`), then 8 column bytes (columns `col..col+7` of that page) |
| `0x20`-`0x2f` | 2 | `0x40013634`, `0x40062fec`, `0x400631fc` init | **LED bitmap row** `op & 0xf`, one byte of on/off bits (bit n = LED `row*8+n`) |
| `0xa0`-`0xaf` | 2 | `0x40013634` | LED bitmap row `16 + (op & 0xf)` (17 rows = 136 LEDs; the state array is `0x460ba9ae` XOR the blink phase `0x460ba98c`) |
| `0x30`-`0x3f` | 2 | `0x400135b0` (cache `0x400b9714`), `0x4006322c` init | **LED level**: nibble `op & 0xf`, then the LED id. Init sends `3f 00 .. 3f 57` (88 ids at 15) |
| `0x40`-`0x4f` | 1 | `0x400926d8` | one-byte command `0x40 | (n & 0xf)`; boot sends `0x43` (`0x4001f9ac`) |
| `0x60`, `0x70`, `0x74` | 2 | `0x4001f4dc`, `0x4001fa08`, `0x4001f98a` | MKII only (flag `0x46c8d18c`): `60 02 70 00` the loader query (reply `70 05 <version> ..`, polled), `60 00` leave the loader, `74 00` ask for the `0x7r` report (PANEL.md section 4c) |
| `0xb5` | 6 | `0x40013368` via `0x400133cc` | 16-bit index (`2*a+b`), then three bytes; sent when the LED brightness setting changes (`0x4003f430`). Palette/brightness table entry -- inferred from the caller, not measured |
| `0xb7` | 2 | `0x400926a8` | LCD backlight 0-255 (`0x4003f430` from the table at `0x400a7632`; the screen saver at `0x400523da` sends 0 and clears the LCD after 216000 ticks) |

Anything else is unknown: `PanelLink` skips one byte, counts it in
`stats["unknown"]`, keeps the last 16 in `unknown_tail`, and carries on; a
`0x1n` whose column byte is not one of 0, 8, .., 120 is skipped the same
way (also counted in `stats["lcd_badcol"]`). None occurred in 9429
captured bytes (1367 messages, 837 LCD blocks) or in the self-test's boot +
MIXER stream (6861 B).

Resync is by first byte only -- no length field, no checksum -- so what
junk does depends on whether it looks like an opcode (measured 11 Sep 2026
with `out/_agents/lcd/verify_fix.py`, junk inserted at the last message
boundary of the 9429-byte capture, offset 9419):

- not an opcode (`ff fe 00`, `99`, `50..5f`): skipped a byte at a time;
  final frame, LEDs and commands identical to the clean stream;
- a `0x1n` with a bad column byte (`12 03`): rejected, identical;
- a `0x1n` with a valid column byte (`10 00`, `17 78`): framed as an LCD
  block and eats the next 8 bytes (here the head of the last real block: 23
  / 19 pixels wrong, the 2 leftover bytes skipped as unknown). Because the
  firmware's flush is a diff, a misframed block stays on the decoded screen
  until the firmware next redraws it; the same junk inserted mid-stream
  (offset 3413, before the post-boot full draw) left no trace;
- a bare `3f`: takes the next byte as an LED id, then the block is misread
  (7 pixels wrong the same way).

What the naive pair parser saw: `00 ff`, `00 00`, `80 be`, `8a be` were LCD
column bytes; `0x11 08` is page 1, column 8; the "chunks 247/248" were LCD
bytes read as an opcode; the "id 0x00-0x5b, value 0x3f" pairs are really
`3f <id>` (level 15, ids 0-0x57) read one byte late after the bare `0x43`.

### LCD geometry (measured)

128x64, eight pages of 128 column bytes, exactly what the two builders walk
(`for page in 0..7: for col in 0,8,..,120`, column-major back buffers at
`[0x400b9710]`/`[0x400b970c]`, swapped after each flush). The panel shows
message **page p at screen rows `8*(7-p) .. 8*(7-p)+7`, bit 0 at the top of
the band**: page 7 is the top of the screen.

    pixel(x, y) = frame[(7 - y//8) * 128 + x] >> (y & 7) & 1

Evidence, from the decoded stream (PNGs `out/_agents/lcd/selftest_*.png`,
`mixer-open_B.png`, `boot+400ms_B.png`, `pattern-settings_B.png`):

- MIXER: inverted "MIXER" title bar rows 0-8, then MIX / OUT / MAIN / CUE /
  DIR / GAIN A B, C D, then "MUTE", "AUDIO" / "MIDI" with the 8+8 mute
  boxes along the bottom. With page 0 on top the same bytes put the title
  at rows 55-63 and the section headers under their contents.
- SET DATE/TIME: bar at rows 8-16, "FRIDAY", the RTC date/time, "LAST SET:"
  above its value `0000-00-00 00:00:00`; the main screen's "PLAYBACK>STATIC
  ... 01->09" bar along rows 57-63 and the BPM "120.0" top-left.
- PATTERN SETTINGS: "SELECT PATTERN" window, "A01", same footer.

There is no display-start-line / scroll opcode in the table, so the page
order on screen is fixed; the "rotated" renders from RAM at `0x460d1f80`
are that buffer's problem (it is not one of the two UART back buffers),
not the panel's. The stream is the ground truth.

Bit order within a page byte is the same as `panel_server.FB`'s formula
(`buf[x*8 + (63-y)//8]` bit `7-(63-y)%8` == page `7-y//8`, bit `y&7`).


### The composite: what the flush sends

Read from objdump of `0x40013abc` on 4 Nov 2026 (static, except where ✅):

1. Clear the back buffer `[0x400b9710]` (1,024 bytes).
2. Walk the layer list from `[0x460babf0]`, next at `+4`. A layer with
   `+32` bit 0 clear is skipped. For each, per 32-bit word, `dst = (dst &
   ~mask) | (mask & pix)`, mask at `[+52]` and pixels at `[+48]`, shifted
   by `+12 & 31` bits, with the row stride at `+44` (words) and the span
   from `+16`/`+20`/`+24`/`+28`. The page plane `0x46c7e0ea` is one layer,
   and each window is another, drawn over it in list order (🟡 the record
   fields beyond those the loop reads are not decoded).
3. For each page p and column block c (0, 8, .., 120), compare bytes
   `x*8 + p` of the back buffer with `[0x400b970c]` for x in c..c+7. If any
   differ, send `0x10|p, c` and the 8 bytes.
4. Swap `[0x400b9710]` and `[0x400b970c]`.

So between flushes `[0x400b970c]` holds the frame the panel shows. Its
layout is the plane's: 128 rows of 8 bytes, byte `x*8 + p` = page p of
column x, which is `+12`'s pixel (x, y) = column 63-y of row x. ✅ Under
the port (SCREEN, `verify_screen`), a copy of `[0x400b970c]` equals
the frame decoded from the UART1 stream to the pixel, with the boot's "NOT
WORKING IN ANY PROJECT" popup up (the plane then differs by 2,314 pixels)
and with MIXER up (3,132). On a unit, a copy of the plane showed the page
screens and none of the windows (SCREEN on Sam's MKII, 4 Nov 2026).

### Traffic per action (empty card, stock image)

| action | bytes | messages |
|---|---|---|
| boot + 400 ms | 5731 | `43`; 440 LED levels; 470 LCD blocks (full frame plus redraws); 76 LED rows |
| MIXER down | 1130 | 112 LCD blocks; `20 55`, `21 55`, `22 ff`, `23 ff`, `3f 66` |
| encoder row 0x30, +2 | 22 | 2 LCD blocks; `2c 40` |
| MIXER again (close) | 1130 | 112 LCD blocks; rows 0-3 and 0x2c back to 0 |
| PATTERN SETTINGS | 522 | 52 LCD blocks; `20 01` |
| cursor-right | 120 | 12 LCD blocks |
| trig 1 down / up | 520 / 2 | 52 LCD blocks / `20 00` |
| track 2 | 72 | 7 LCD blocks; `25 a6` |

A quiet screen sends nothing (0 bytes over 500 ms idle): the flush is a
diff against the previous frame, block by block.

### Self-test

    .venv/bin/python3 tools/panel/panel_link.py --selftest      # 15-20 s wall, exit 0

Boots the stock image on an empty card (the boot is most of the wall time:
15.4 s and 17.1 s measured 11 Sep 2026), feeds the stream in 7-byte
pieces, opens MIXER, and asserts: no unknown bytes, nothing left unframed,
the `0x43` hello and 88 LED levels at init, the MIXER title bar in rows 0-8
and nothing inverted in the bottom band, the boot footer bar ending on row
63 and the dialog bar in rows 8-16, and that the whole stream fed in one
call decodes to the same frame / LEDs / commands / stats as the 7-byte
pieces. It writes `selftest_boot.png` and `selftest_mixer.png` under
`--out` (default `out/_agents/lcd/`).

    .venv/bin/python3 tools/panel/panel_link.py --decode tx.bin --png lcd.png

### Panel -> CPU: the RX parser (13 Sep 2026)

`0x4009228c` (RAM, 0x40000400 listing) runs on the UART's receive
interrupt over the ring at `0x46100b28` (`0x40092254` fills it). The FIRST
byte of a report decides its class by its high nibble and its payload
length; the low nibble is the row:

| first byte | payload | class |
|---|---|---|
| `0x2r` | 1 byte | **key matrix row r**, bitmask (set = held); changed bits against the last mask (`0x46100b18[r]`) become key events from the descriptor table at `[0x46c901dc] + (r*8+bit)*12` (+770 with the modifier row's key held -- never: the table's modifier row is 0xff), posted to the UI/sys queues. Rows 0-7 are all live entries (key codes 0x00-0x3f); **row 7 (`0x27`) is the encoders' push switches**, bit = the encoder (A-F = 0-5, LEVEL = 6): with a TRIG key held it toggles the step's parameter lock (KEYMAP.md, 13 Sep 2026) |
| `0x3r` | 1 byte | **encoder r**, signed detent delta; if the previous report is still unread it is ADDED into the pending message (`0x4009250c`), else a 6-byte message `{type, sub, delta, stamp}` is posted (`0x40092526`) |
| `0x40` | 1 byte | **the crossfader**: the ADC byte 0..255. Scaled by the calibration record at `0x1ffffe` (magic `0x1234`: min `[0x1ffffc]+1`, span from `[0x1ffffa]`, `0x400925ac`), none under emulation so `pos = (byte >> 1) & 127`; `0x40092fac` drops a repeat of the last value (`0x400d16cc`) and `0x40092f2c` writes it into a 2-byte ping-pong message `04 <pos>` at `0x400d16c8/ca` (coalesced while one is pending) and posts it to the sys queue registered in `0x46104ca4`. Sys kind 4 -> `0x40061e0a`: gated on AUDIO CC OUT having INT (`0x8000004a` bit 0), stores `0x460d16c8`, rebuilds the 10 weight longs `0x80003c60`, echoes CC 48 = 127-pos if EXT, runs the STRT/LEN/RATE morph `0x4003f1b4` and redraws the fader icon (`0x4003577c`, five glyphs from `0x400bcd7c`, LCD x 104-108 / y 59-61). Rows `0x41`-`0x4f` are ignored (`0x4009256a` wants row 0) |
| `0x7r` | 9 bytes | a report copied to `0x46100b48` with its pointer in `0x46100b52`: the MKII panel's answer to `74 00` (byte 1 = UI version minor, byte 3 = UI tested, byte 4 == 22 sets `0x46c8d188`); `ot_emu --mkii` sends one (`docs/firmware/PANEL.md` section 4c) |
| anything else | -- | the parser stays in its header state |

Measured on the port (`out/_agents/panel-ctl/lab_params.py`, OTLIVE):
`0x40 255` -> `0x460d16c8` = 127, `0x40 0` -> 0, `128` -> 64, `64` -> 32,
`192` -> 96, `1` -> 0, `254` -> 127, `127` -> 63, `200` -> 100; each one
redraws the icon and rebuilds the weights (`0x80003c60` = `0x8000_0000` at
127 = scene A fully, `0x0000_8000` at 0 = scene B). Rows `0x27`-`0x2f`,
`0x37`-`0x3f`, `0x41`, `0x42`, `0x4f` with a value byte change nothing
(`0x27`/`0x37` nudge the tempo readout's redraw, as KEYMAP.md found for
`0x27`) -- alone: `0x27` with a TRIG key held is the encoder push, the
lock toggle (KEYMAP.md, 13 Sep 2026). The panel's own scaling of the pot to `0x40 <byte>` on the
hardware is not measured here (no unit); the message and the firmware's
side are.

### Not yet known

- The meaning of the `0xb5` five bytes and of `0x4n` for n != 3 (`60 xx`,
  `70 00`, `74 00` are the MKII's: `docs/firmware/PANEL.md` section 4c).
- Which physical LED each bitmap bit and each level id is (the boot
  animation at `0x4006307c`-`0x40063178` walks ids 0-15 with levels
  14-30, a starting point for a map).
- The `0x7r` report's bytes other than 1, 3 and 4 (no MKII panel capture)
  and the encoder message's type/sub bytes per row (the descriptor table at
  `[0x46c901dc]`); keys, encoders and the crossfader are decoded above.
