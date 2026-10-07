# Landing in a chosen image at power-on

A follow-on to OS SWITCH (`modules/os-switch`, on an MKII 29 Sep 2026,
`docs/proposals/FIRMWARE_SWITCHER.md`). It asks whether the thing that
proposal deliberately left out can be had safely, and says what it would
cost. Nothing here is built.

Confidence markers as `docs/firmware/CHIP.md`: ✅ measured (on the unit
where it says so, else under the ColdFire port or read from the user's own
image by disassembly), 🟡 inferred, with what would falsify it, ❓ open,
with what would answer it, ❌ retracted.

**Status, 30 Sep 2026: a variant of section 7 is built** (`modules/os-switch`,
"At power-on: the boot picker"), measured under the port, not yet on the
unit. It is section 7 without the held key: every power-on with another image on
the card opens the picker at the point section 4 asked for -- the boot's own
LOAD PROJECT post (`0x4002574c`, sys's media case, after the card is
mounted and before the project loads) -- with a 3 s countdown that answers
NO. So it keeps section 7's properties (nothing boots unless chosen this boot, no
file, no flag, no loop) and costs at most 3 s on a boot that stays. section 4's
first ❓ is answered ✅ under the port: there is such a point, and it is
the post itself; the load, and the LOADING FILES job the set mount queues
behind it, are held and posted in stock's order on NO. The escape hatch of
section 5 is not needed by this variant; the full default of section 6 is still not built.

---

## 1. The wish, and the passage that refused it

Today every power-on lands in the flashed image, and reaching another one
is MAIN MENU > OS > `<NAME>` > YES. Four keypresses and a reboot, every
time, even when you have not run the flashed image for a week.

`FIRMWARE_SWITCHER.md` section 6 rejected the automatic version:

> **Not persistent.** A power-cycle forgets the switch. A "boot X at
> power-on" option would mean the flashed image reading a choice from the
> card and switching at once, which roughly doubles boot time. Deliberately
> left out.

That reasoning is correct and this document does not overturn it. It says
what the doubling actually costs, what an escape hatch would have to cover,
and it recommends a narrower feature that gets most of the benefit and
cannot double anything.

---

## 2. Why a boot default must cost two boots ✅

Read from the user's own image, 29 Sep 2026. Bootstrap addresses are
relative to its copy at `0x400dea4c` (linked at 0); the image address is
given where it matters.

- **The chainloader runs before there is a filesystem.** Its gate is a
  detour at the OS entry's second instruction, `0x40000412`
  (`modules/os-switch/manifest.py:119`), and the OS entry's own path is
  `0x4000050c` the DSP upload → `0x40000518` the globals/heap zero-fill →
  `0x4000053c jsr 0x40000db0` main (`FIRMWARE_SWITCHER.md` section 2.2). At the
  gate no DSP, no cache set-up, no interrupts and no ATA stack have run.
  The switcher's own load path needs the FS vtable
  (`modules/os-switch/switch.s:155-161` refuses to scan while
  `0x46c8240e` or `0x46c8242a` is still zero) and OS UPGRADE's
  stop/sync/wait-for-idle sequence `0x40080444..0x40080480`
  (`switch.s:621-633`). None of that exists at the gate. **Falsified by** a
  card read that succeeds from a detour at `0x40000412`.
- **The mailbox is DRAM and a power-on is treated as having none.** The
  stage lives at the top of the platform reserve, `OSW_MBOX 0x49200000`
  (`modules/os-switch/osw.inc`), and the gate's no-mailbox path records
  `ST_NONE` and resumes (`chain.s:55-64`). Whether a *quick* power-cycle
  keeps DRAM is unmeasured: `chain.s:11-12` says it does, and
  `docs/firmware/ARCHITECTURE.md:158-164` marks the refresh-gap question
  `~, unmeasured`. It does not matter for safety — the gate clears
  `MB_MAGIC` before anything below it can fail (`chain.s:38`) — but it
  means a boot default cannot be carried in the mailbox from one power-on
  to the next.

So a boot default is: the flashed image boots, reads a choice from the
card, stages the target and resets; the target boots. **Two boots per
power-on, always** — including the boots where you wanted the flashed image
anyway, unless the default can name it.

### What the doubling is worth, in numbers

| leg | cost | how |
|---|---|---|
| the chainload itself (gate, hash over the stage, copy, entry) | ✅ the staged image's entry runs ~190 ms after the flashed image's | the unit, build 14 (`modules/os-switch/README.md`); build 4 reported 103 ms for a 1.1 MB stage |
| the hash over 1.1 MB | ✅ ~8.9 M instructions | the port, `verify_osswitch` chain case |
| both DSP uploads after the switch | ✅ ~60 ms, final echo 3 on each core | the unit, build 14 |
| power-on → a point where the card is mounted, in the flashed image | ❓ | BOOT TRACE (`modules/boot-trace`) note at the candidate hook, timed on the Mac against note 1 at the gate |
| reading a 1.1–1.2 MB `.OBI` off the card | ❓ | the same trace, note before and after `osw_load`'s read loop (`switch.s:666-686`) |

Two of the five are unmeasured and they are the two that dominate. **No
recommendation should be made about the full default until those two
numbers exist**; the trace image that produces them already exists
(`remixes/os-switch-trace`).

---

## 3. What the boot path already gives: a held key at power-on ✅

This is the most useful thing this reading found, and it belongs to all
three designs below.

The bootstrap reads the panel before it unpacks the OS, and the results sit
in two SRAM bytes that nothing else touches:

- `0x128` (image `0x400deb74`) clears `0x80000200` and `0x80000508`, sends
  the panel `0x60 0x00`, then reads tagged pairs: tag `0x25`'s byte is
  stored at `0x80000200` (`0x170`), tag `0x26`'s at `0x80000508`
  (`0x17e`), tag `0x27` ends it. The loop exits when `0x80000200` is
  nonzero or the terminator arrives, **with no timeout** — the hazard
  `switch.s:29-31` names and build 1 hit from the other side.
- `0x2abc` (image `0x400e1508`): if `0x80000200` is `0x20` the bootstrap
  draws its own menu (strings at `0x305a` `"  STARTUP MENU  "` and
  `0x306b` `"\n1..TESTMODE\n2..EMPTY RESET\n3..MIDI UPGRADE\n4..SEND
  UPGRADE\n5..EXIT"`) and loops reading the panel, storing the selection
  masked with `0x1f` at `0x80000200` (`0x2b16`, `0x2b20`). **If the first
  byte is anything else, `0x2b40` clears `0x80000200`** — so a bare held
  key leaves no trace at all.
- `0x2b4c..0x2b8c` dispatches that byte: `1` → TESTMODE (`0x2846`), `2` →
  `orl #1,0x8000050a`, `4` → MIDI UPGRADE (`0x1f34`), `8` → SEND UPGRADE
  (`0x1d54`). `0x2b8e`: `0x80000508 == 2` → `orl #2,0x8000050a`.
- `0x2d30` sets RAMBAR1, `0x2d34` runs the panel/menu path, `0x2d38`
  unpacks NOR, and `0x2d3c` is `movel 0x8000050a,%sp@- ; jsr 0x40000400`.
  The OS entry parks that long at `0x400b9650` in the instruction
  immediately before our detour (`0x40000408 lea %sp@(32),%a0 ;
  0x4000040c movel %a0@,0x400b9650`).
- The OS reads the parked long at three sites: `0x4001fa2c` (`== 1` →
  clear `0x10000000..0x100fff00`, which is EMPTY RESET), `0x4001faec`,
  `0x4001fb6a`.
- ✅ **The MAIN OS image contains no code reference to `0x80000200`,
  `0x80000508` or `0x8000050a` outside the bootstrap's own copy** (a
  literal search of all four-byte occurrences: the nine other hits, at
  `0x400c401d`…`0x400c4069`, are odd-addressed and inside data). At the
  gate the cells are certainly the bootstrap's, since no OS instruction has
  run. **Falsified by** a write-watch on `0x80000200` under the port over a
  boot and a project load — the neighbourhood *is* live OS RAM
  (`0x80000003` the current part, `0x80000034` MASTER_TRACK,
  `0x80000810` the live block), so a computed write is entirely plausible
  and a literal search cannot see one. This is why the gate should copy the
  byte into the mailbox rather than let the OS read it later.

**The consequence.** `0x80000200 == 0x10` at the OS entry means the user
came through STARTUP MENU > 5 EXIT: a value the bootstrap has no case for,
which falls through `0x2b4c`'s dispatch and boots normally. 🟡 `0x10` is
EXIT's bit, inferred from the `0x1f` mask and the four cases the dispatch
does handle; **falsified by** a probe that reads the byte after EXIT and
finds something else. The gesture is two presses on a path the manual
already documents for recovery (`docs/contributing/FAILURE_MODES.md`, "Z"
screen: hold [FUNC], power on, then a TRIG).

❓ Whether a *bare* held key could serve instead — one press, no menu. The
gate could redo the bootstrap's own exchange on UART1 (`0xfc064004`
status, `0xfc06400c` transmit, the registers `switch.s:62-63` already
uses) and read the full rows. What would answer it: write the exchange with
a timeout (build 1's hang is exactly what a missing one costs) and measure
under the port with `--live-script` key lines, then on the unit with BOOT
TRACE reporting the byte as a velocity. Until it is measured, the STARTUP
MENU byte is the escape hatch that already exists.

---

## 4. How early could the switch fire? ❓

Somewhere after the FS vtable is installed (`0x40014524` / `0x40014636` /
`0x40014750`, `docs/firmware/STORAGE.md` section 1) and before the user has done
anything. Everything the switch does after that point is already built and
hardware-proven: the load path, the DSP park, the reset.

Two things are open:

- **Is there a point before the home image loads its project?** The
  switcher's load path runs OS UPGRADE's sync and wait-for-idle
  (`switch.s:621-633`) because it may run mid-session; at boot there may be
  nothing to sync, which would make the whole path cheaper. What would
  answer it: under the port, watch `0x46c8240e`/`0x46c8242a` becoming
  nonzero, the first successful root `open` and the project load
  (`0x4008445c`, `0x40093980`) with `--pcwatch`, and record the
  instruction counts between them; then confirm the same ordering on the
  unit with BOOT TRACE notes.
- **Is a switch safe there?** The DSP upload has already run (it is at
  `0x4000050c`, before main), so `osw_park` is still required — ✅ that
  part needs no new work. Whether the RTOS tolerates the reset sequence
  that early is untested; `switch.s:755-762` masks interrupts and flushes
  the panel queue first, which is stock's own order.

---

## 5. The escape hatch, which is the heart of it

A default naming an image that hangs gives: power on → switch → hang →
power-cycle → switch → hang. The flash is never written, so the unit is not
bricked, but without a hatch it is unusable until the card is taken to a
computer. **The flag cannot live in NOR**: OS SWITCH's whole claim is that
the bootstrap and NOR are untouched (`FIRMWARE_SWITCHER.md` section 6, "Not a
bootloader").

Three candidates, and what each does and does not cover.

**(a) A held key at power-on, read by the gate.** section 3: STARTUP MENU > EXIT
leaves `0x80000200 == 0x10`; the gate reads it and records "no default this
boot" in a new mailbox field, so the switcher in the running OS never needs
the SRAM cell again.

**(b) A one-shot attempt flag, written before the switch, cleared only by
the target.** The flashed image writes `ATTEMPT <NAME>` somewhere
persistent, switches, and the target clears it; a flag still set at the
next power-on means the last attempt did not finish, so skip it.

**(c) The narrow variant** (section 7): no default, so nothing to escape from.

| failure | (a) held key | (b) one-shot flag | (c) narrow |
|---|---|---|---|
| the target never reaches the OS (bad image, DSP wedge) | covered | covered | cannot happen |
| the target boots but cannot clear the flag — **stock 1.40C, or any image without OS SWITCH** | covered | **broken**: the default is skipped for good after one boot, and nothing says why | cannot happen |
| the target boots, then hangs minutes later (a wedge on play) | covered | not covered: the flag was already cleared | cannot happen |
| the card is unreadable, or the named file is gone | covered, and unnecessary: the switch refuses and the flashed image runs | same | cannot happen |
| the flashed image's own boot hook wedges (the card read, the sync) | covered — the gate reads the hatch *before* the FS exists | not covered: the flag is read at the hook | cannot happen |
| the user does not remember the gesture | the README and the pane's own text are the only defence | same | nothing to remember |

(b)'s second row is decisive: it makes stock 1.40C — the one target we most
want to be able to name, because it is the way back — the case the
mechanism gets wrong. (b) also needs a persistent write, which is a policy
step: today the module writes neither the flash nor the card. Two homes for
the flag were looked at:

- the card, through the buffered file API (open `0x40016864`, write
  `0x400166b8`, close `0x4001677c`, seek `0x4001660c`; ✅ named
  independently by ems-octakit and octamax, `docs/firmware/SAMPLE_SAVE.md`
  section 5, and octamax reports working file-creating patches 🟡). It is a write
  to the user's card at every power-on.
- the battery-backed SRAM. 🟡 `0x10000000..0x100fffff` survives a
  power-cycle (nordseele's MKI, `docs/firmware/STORAGE.md` section 3, adopted
  here). ✅ Only its last 252 bytes are checksummed: `0x4001fa48..0x4001fa6a`
  EORs `0x100fff04..0x100fffff` with a running index, adds 514 and
  compares with the long at `0x100fff00`; a mismatch clears the whole
  region and calls `0x4001f298`. So a flag below `0x100fff00` breaks no
  checksum. ❓ whether any long down there is never referenced — a sweep of
  the kind `CHIP.md` section 3 did for core-private Y would answer it — and ❓
  whether the region really survives on an MKII. EMPTY RESET wipes it, which
  is a feature here.

**Recommendation for the hatch, if a default is ever built: (a), and only
(a).** It is the only one that covers a target which cannot cooperate, and
the only one whose read happens before anything can wedge.

---

## 6. Where the name lives, and who writes it

- **A conventionally-named `.OBI`.** The default is whichever file is
  called `BOOT.OBI`. No writer, no new card-write path, no format; the
  user renames on the computer, and MAIN MENU > OS can mark the row.
  Costs: changing the default means leaving the unit, and the name is
  either a second copy of a 1.1 MB file or the only copy.
- **A small text file in the card root** (`/OSBOOT.TXT`, one line: the
  name). Set from MAIN MENU > OS (FUNC + YES on a row, say), written with
  the buffered API above. Costs: the first card write this module has ever
  made, on a path where a half-written file must still leave a bootable
  unit — write to a temporary name and rename, or accept that an
  unparseable file means "no default" (which it should mean anyway).
- **Not the mailbox** (section 2) and **not NOR** (section 5).

Either way `make_obi.py`'s checks stay the gate on what may be named: the
OS entry's first instruction, a length inside `OSW_MAXLEN` (2,706,400 B),
and the bootstrap version equal to NOR's.

---

## 7. The narrow variant: a held key opens the OS list

**Power on holding the key; instead of the normal boot continuing into
whatever it would, MAIN MENU > OS is already open.** Pick an image, YES,
and the unit reboots into it. Any image on the card in two presses plus the
pick, and:

- no default file, so no format, no writer, no card write;
- no flag, so nothing to go stale;
- **no boot loop is possible**, because nothing is ever booted without the
  user choosing it this boot;
- one boot per power-on when you want the flashed image, and the normal
  single switch when you do not.

What it costs: you still choose every time. There is no "it just comes up
in bottleservice".

What it needs:

- **the signal.** ✅ section 3: `0x80000200 == 0x10` after STARTUP MENU > EXIT,
  read at the gate and parked in the mailbox. The gesture is two presses
  and an existing, documented path. 🟡 the bit; ❓ the one-press variant.
- **somewhere to put the pane.** ❓ Two shapes. (i) Open MAIN MENU > OS
  from code: the root descriptor's cursor and the focus pointer
  `0x400cbda8` (✅ `docs/firmware/MAINMENU.md` section 4) are writable and the
  module's rescan detour at `0x40064c32` already runs at every opening, but
  whether the menu can be *opened* from code rather than by [PROJ] is
  untested. (ii) Offer each `.OBI` in turn in the stock confirm dialog
  `0x4006d57c` — which is exactly the shape of the retired first prototype
  (`FIRMWARE_SWITCHER.md` section 3, "❌ a seventh CONTROL row with a
  one-file-at-a-time dialog"), and needs no menu at all. What would answer
  it: drive both under the port with `verify_osswitch`'s `--live-script`
  path and render the result with `--lcd`.
- **a hook after the UI is up.** The same ❓ as section 4, but far weaker: showing
  a pane stops no playback, syncs no project and reads no file beyond the
  dir scan the module already does. A hook that is merely *late* is
  harmless here, where for a default it is the whole cost.

---

## 8. Gates

`verify_osswitch.py` (16 checks) already proves, for the machinery both
designs reuse: the row, the dialog, the deferred load, the mailbox's
contents, the stage reading back equal to the file, the chainload from
exactly the memory a switch leaves, the four refusals, the DSP park, and
that the runtime ends below the mailbox. None of that needs redoing.

New, for either design:

- **the escape byte.** A gate case that preloads `0x80000200` with `0`,
  `0x10` and each of `1/2/4/8` and asserts what the gate recorded in the
  mailbox — `--preload ADDR=FILE` already exists for exactly this kind of
  "memory as a reset leaves it" (`tools/emu/README.md`). And a write-watch
  case: boot with a project and show `0x80000200` is not written by the OS,
  or stop relying on it past the gate.
- **no boot loop, structurally.** With a default set and a target that
  hangs, two consecutive boots must land in the flashed image the second
  time. The port cannot reset, so this is two `--preload` runs chained the
  way the `chain` case already chains one.
- **the default's parser.** A missing file, an empty file, a name with no
  matching `.OBI`, a name that is the flashed image, and a 12-character
  name that exactly fills its field must each end in the flashed image.
  (`FIRMWARE_SWITCHER.md`'s field-length trap is a ColdFire-side one too:
  `abbr` and `fullname` are why `schema.MenuEntry` checks lengths.)
- **the unit.** Nothing here is believable from the port alone: the reset,
  SDRAM keeping the stage, and the doubled boot's real duration are all
  hardware. One flash of an `os-switch-trace` build gives the two missing
  numbers in section 2 and the escape byte at once.

---

## 9. Recommendation

**Build the narrow variant (section 7). Do not build the boot default yet.**

Reasons, in order: the full default's two dominating costs are unmeasured
(section 2); its only sound escape hatch is a held key, which is the narrow
variant's entire mechanism, so the narrow variant is the *prerequisite*,
not an alternative; and the failure it prevents — a card you have to take
to a computer to recover — is the one failure mode OS SWITCH was built to
remove.

**What would change it.** All three, together:

1. the two ❓ numbers in section 2 measured, and power-on → pane under about a
   second, so that the doubled boot is a few seconds rather than a wait;
2. `0x80000200 == 0x10` confirmed on the unit, and confirmed still intact
   at the point the switcher would read it (or read at the gate and parked,
   which is the design anyway);
3. someone living with the narrow variant and two images for a week and
   reporting that the pick is the annoyance — because if it is not, the
   default buys nothing but a second boot.

Falsifier for the recommendation itself: a measured hook where the flashed
image reaches a mounted card in, say, 300 ms and the whole doubled boot
lands under 4 s. Then the default is cheap and only the hatch matters.

---

## 10. Not designed here

- Naming the flashed image as the default (so the default can mean "stay"),
  which needs the pane to know its own name — it does: `str_self` /
  `OSW_SELF`, the build's `VERSION` (`modules/os-switch/manifest.py:62-74`).
- More than one default (a per-key choice at power-on: FUNC+1..4).
- Whether OS SWITCH should be the thing that owns a card-root settings
  file at all, or whether that belongs to a platform-level module.
- An MKI. Everything measured for OS SWITCH is an MKII, and the panel is
  where the two differ (`switch.s:32-36`).
