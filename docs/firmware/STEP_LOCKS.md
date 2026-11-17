# Step locks (p-locks)

OS 1.40C, ColdFire side. Where the sequencer's per-step parameter locks
live, how they are recorded, played, copied and saved. Measured under the
ColdFire port on the stock image with a real project (OCTABAM89_setgate,
bank index 2) unless marked; ✅ measured or read from the code.

## 1. Storage

| what | address | |
|---|---|---|
| bank blob in RAM | `0x400e21e0 + bank·0x9b340`; the UI's bank pointer `0x46c82456` | ✅ |
| pattern | blob + `p·0x8ed8` (16 patterns, then the Parts at `+0x8ed80`) | ✅ |
| audio track record | pattern + `t·0x91a` (the file's TRAC less its 8-byte tag and length) | ✅ |
| step lock byte | track + `0x59 + step·32 + flat` | ✅ |
| MIDI track record | pattern + `0x48d0 + t·0x8b0`, locks at pattern + `0x4900 + …` | ✅ |
| battery-backed copy of the current bank's patterns | `0x1001614e` + the same offsets (filled by `memcpy(0x1001614e, bank, 0x8ed80)` at `0x4000fb20` on load) | ✅ |

`flat` is the page-1 slot index 0..29 (PLAYBACK, LFO, AMP, FX1, FX2 × 6);
30 and 31 carry no knob. `0xff` = not locked. Every byte of the track
record is used (`0x62 + 64·32 + 0xc0 = 0x922` in the file); there is no
byte for page 2.

## 2. Recording

`0x400508e4(slot, delta)`, the page-1 knob path with a trig held (✅
writer pc `0x40050e60`, sys task). It sits in its own input layer
(`0x400bedxx`, six encoder records); the SETUP pages' editors sit in
theirs (FX2 `0x400bc3c2`, FX1 `0x400bc198`, AMP `0x400bb8c8`). With a
SETUP window open and a trig held, a knob turn reaches `0x400508e4`, not
the SETUP page's editor (✅ AMP SETUP, `--watch-pc`), and locks the
page-1 slot behind the window. A SETUP window open: `0x460d175c` = the
window record (`0x46c7d34c`), 0 with none (✅ AMP, FX1, FX2 SETUP);
`0x460d1684` the page (2 AMP, 3 FX1, 4 FX2). Held trigs: `0x460d174a` (u16, one bit a
trig key; step = 31 − ff1 + `0x460d174c`, the step page). Writes the lock
in the bank blob and the battery-backed copy, sets `DB + 0x9b332` and
`0x100f8598` (edited), calls `0x40027e00`. The MIDI-track branch is taken
on `0x80000012`.

## 3. Playback

| stage | where | |
|---|---|---|
| step → per-track staging `0x46c7aa24 + t·32` (n = −1) or pending slot n | the record builder `0x4009d1e8(track, bank, pattern, step, n)`: plain path `0x4009d8c6` (fill `0xff` at `0x4009d8d0`, lock bytes at `0x4009d90a`), slide path `0x4009d704` (locks plus the slide deltas into `0x46c7(6ac0/7c32) + …`, which the frame ISR copies to `0x80001658`) | ✅ |
| staging → pending `0x46c7ab30 + (n·8 + t)·32` | `0x4009b862`, `0x4009c042` copy loops (slot 0); `0x4009b220` resets slots 0..2 to `0xff` | ✅ |
| pending → frame record `0x80001558 + t·32` | `0x4000bae8..0x4000bb02` (frame ISR) | ✅ |
| apply | `0x4000c5ac..0x4000c612`: each byte ≠ `0xff` → live lane `0x80000810 + 72t + k` and DSP halfword `0x80000a50 + 64t + 2k` (`value << 8`); bit k set in `0x80001538[t]`; the byte consumed (`0xff`) unless flag bit 2 | ✅ |
| restore at the next trig | `0x4000c4a8..0x4000c562`: every bit of `0x80001538[t]` → the Part's byte back into the live lane | ✅ |

The live lane's page-2 bytes start at `+0x20`; no stage carries them. All
32 bits of `0x80001538[t]` are taken. Locks reach the live lane before the
frame builder's scene morph, which reads the live value as the knob.

## 4. Operations that move locks

| operation | routine | |
|---|---|---|
| remove a trig (clears the step's 32 bytes; placing one leaves them) | `0x4005fb44`, store at `0x400603a8` | ✅ |
| trig copy + paste (grid rec: hold trig, REC; hold trig, STOP) | `0x4002c89c`, lock store at `0x4002cb5e` | ✅ |
| clear a trig's locks (hold trig, PLAY) | `0x40040e14`, store at `0x40040e82` | ✅ |
| track copy / paste (FUNC held with the trig chords) | `memcpy` `0x40020898`, 0x91a bytes; track write `0x40029754(src, pattern, track)`, track snapshot `0x40026664` | ✅ |
| clear track | `0x40039df4(pattern, track)` | ✅ |
| clear pattern (FUNC+PLAY) | `0x4003a2e8` calls `0x40039df4` per track | ✅ |
| copy pattern (FUNC+REC) | `0x40026dbc`: `memcpy(0x460c8122, pattern, 0x8ed8)` at `0x40026ed4` | ✅ |
| paste pattern (FUNC+STOP) | `0x40026dbc` snapshots the target into `0x460bf218` (`0x40026f64`); `0x4002b9b0` writes clipboard → pattern and its battery-backed copy | ✅ |
| undo restore | `0x4002b3b4` (from `0x460bf218`, gated on clipboard kind `0x460c80f0 == 5`) | ✅ |

The clipboard `0x460c8122` and undo buffer `0x460bf218` are shared with
the Part and scene operations; `0x460c80f0` holds the clipboard's kind.

The paste routines take the buffer as an argument: trig paste
`0x4002c89c(clip, pattern, track, page, mask)` reads 40-byte records
(clip + 2 + 40·b: four bytes, the 32 lock bytes, four bytes; b = the
step's bit on its page, the u16 at clip + 0 the source mask); trig copy
`0x4002bf38(clip, pattern, track, page, mask)` writes them (✅ watch on
the clipboard). Clear track `0x40039df4(pattern, track, flags)` clears
the steps and their locks only with flags bit 0. memcpy `0x40020898` runs
before the octabam loader (an entry detour into DRAM faulted at boot).

## 5. Files

Format strings in the image: `%s/bank%02d.work`, `%s/bank%02d.strd`,
`%s/project.work`, `%s/project.strd`.

| routine | does | |
|---|---|---|
| `0x400917c8(?, mask, progress)` | write `bankNN.work` for each bank in the u16 mask: open, serialize `0x4008b278(fo, bank RAM)`, close (callers: background save `0x40084dc2` with the dirty mask less the current bank `0x80000002`, save-as `0x4008505c`, new project `0x400851e0`, card sync `0x400919e4` = SAVE PROJECT, ✅) | ✅ ✅ |
| `0x4008eda4(?, mask, …)` | bank store: per bank in the mask, `0x40016388(dst .strd, src .work, 0)` (the stock file copy) | ✅ |
| `0x4008f0b0` | bank reload: `.strd` → `.work` | ✅ |
| `0x4008ee74` | project store: `project.work` → `.strd`, then every bank's `.work` → `.strd` through d5 = the copy (loaded at `0x4008ef9a`, `0x4008f02e`); SAVE PROJECT runs it after the bank write (✅) | ✅ ✅ |
| `0x4008f180` | project reload: the reverse, d5 loaded at `0x4008f2a6`, `0x4008f33a` | ✅ |
| `0x40090504` | load all 16 `bankNN.work` (the project load, caller `0x400852c8`) | ✅ |
| `0x400905d4(?, mask, …)` | load the masked banks' `.work` (callers `0x40084d60`, `0x400853d8`, `0x40085452`) | ✅ |
| `0x400909d8` | the empty project's RAM (callers `0x40085170`, `0x4008534c`, `0x4008548e`, `0x400854c2`, `0x4009159a`) | ✅ (Octakit's name) |
| `0x4008ded0` | bank deserialize | ✅ (Octakit) |
| `0x40016864` / `0x40016564` / `0x400166b8` / `0x4001660c` / `0x4001677c` | buffered open / read / write / seek / close; `0x40025230` the project directory | ✅ (Octakit) |

## 6. The current bank over a power-off

CS1 (`0x10000000`, 1 MB decode) holds the current bank: `0x4000faf0(bank)`
copies its patterns (`0x1001614e`), Parts (`0x100a4ece`), saved Parts and
marks there (callers `0x40025b00`, `0x400622b2`, `0x400907c4`); edits
write through (the lock editor's second store). At power-up `0x40025770`
range-checks the UI state there (`0x4000fda8`) and validates every Part
copy and pattern, then `0x4000fbb4(bank)` copies the bank back
(`0x40025808`), and the firmware's own load reads every other bank from
the card (`0x400905d4` with mask `0xfffb`, from `0x40084d60`). ✅ Under the
port with `--cs1-in` and `--no-post`, 2 Oct 2026: a page-1 lock recorded
and never saved is in the pattern after the power-up. That CS1 keeps its
contents with the power off on the unit is inferred from this use.

Stock references nothing in `0x100f859c..0x100fff00`; its whole-CS1
initialise (`0x4001fa76`) writes it. `0x100fff00..` is a checksummed
settings record (`0x4001f218..`); `0x10000004..0x10016143` is filled by a
file read at load.

## 7. Octakit's patches on these paths (until 6 Oct 2026)

Octakit (removed from octabam 6 Oct 2026; `docs/firmware/PARTS.md` is
what KITS does instead) patched the call sites of every routine in
section 5, the entry of `0x400905d4`, `0x4002b9b0`'s entry, `0x40026eb0`
(in the pattern copy), both page-2 editor entries and stores, and
the frame ISR's trig path at 49 sites `0x4000b408..0x4000c590`, one of
them (`0x4000c502`) inside the restore loop. None covered the routines'
own bodies in section 5, `0x4000bae8..0x4000bb0e`, `0x4000c5ac..0x4000c614`,
`0x4009b862` or `0x4009d8d0..0x4009d90a`.
