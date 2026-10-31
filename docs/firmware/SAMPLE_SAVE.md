# How a recording becomes a `.wav` on the card

The firmware writes WAV files itself. This page is the save path: the
routine that emits the header, the loop that streams the audio out of the
sample pool, the file API underneath, and the clock that names the file.
Section 8 is the attribute file (`.ot`) a save writes beside the WAV, and
the tempo a sample gets without one.

**Method.** Read from `out/raw/section_3_MAIN_OS.bin`, SHA-256
`164f31224bf61181e3f50e7dec40df9afcae5b16dbf6e4c0d0cc5e986af0a84e`, load base
`0x40000400`. Disassembled with `scripts/disasm.sh emac`, that is
`objdump -m m68k:cfv4e`.

r2 cannot decode this region (`scripts/disasm.sh`); every claim below was
derived with cfv4e. Confidence markers as in `CHIP.md`: ✅ measured, 🟡
inferred with a falsifier stated, ❌ retracted.

The writer is at `0x40020f04`; anything that wants to put samples on the
card can call it.


## 1. The path, end to end

✅ All addresses below are measured, unless a row says otherwise.

| step | address | what happens |
|---|---|---|
| build the path | `0x40013a08` (sprintf) | formats `%s/AUDIO/%s.wav` (`0x400b3a85`) or `../AUDIO/%s.wav` (`0x400b3a11`); project directory from `0x40025230` |
| open for write | `0x40016864` | mode string `"w"` at `0x400b328b`, I/O buffer `0x460263e0`, buffer size `0x10000` |
| write header and audio | **`0x40020f04`** | the subject of this page |
| close | `0x4001677c` | |

The one call site of the writer is `0x40084e46`, inside the save routine that
opens the file 34 bytes earlier at `0x40084e24`. That routine passes the
**trim points**, not the whole slot:

```
d0 = state@(266)          start sample
d1 = state@(270) - d0     sample count
a4 = state@(2)            slot id
wav_write(handle, d0, d1, a4)
```

So a save writes the trimmed region of the slot, not its full contents.

---

## 2. The writer `0x40020f04`

✅ Signature, from the prologue and the caller:

```
long wav_write(void *handle,      sp@(48)   open file object
               long  startSample, sp@(52)
               long  sampleCount, sp@(56)
               long  slotId)      sp@(60)
```

✅ Two guards, both taken before anything is written:

| guard | address | effect |
|---|---|---|
| `0x46105408` must be non-zero | `0x40020f1c` | returns `-2` |
| `slotId` must be `<= 135` | `0x40020f26` (`cmpal #135,%a4`) | returns `-2` |

**135 is `0x87`, the last recorder buffer.** `RECORDER.md` records that
recorder buffers are object ids 128 to 135 in the same arena as the sample
slots. This writer accepts them. It is not restricted to sample slots.

✅ The slot's control record is `0x46c922c4 + slotId * 44`, which is the same
base and stride `RECORDER.md` gives for the state arena. Two flag bits in the
first word of that record drive the whole format:

| bit | clear | set |
|---|---|---|
| 0 | mono, 1 channel | stereo, 2 channels |
| 1 | 24 bit, 3 bytes per sample | 16 bit, 2 bytes per sample |

Bit 1 is read twice, once for the byte count at `0x40020f48` and once for the
`bits` field at `0x40020ff6`, and the two agree.

✅ Return codes: `1` success, `-2` a guard failed, `-51` a chunk of zero
length was computed, or the negative value the write primitive returned.

---

## 3. The 44 byte header

✅ Built in a scratch buffer at `0x46c2d980`, then written in one call. The
CPU is big endian and RIFF is little endian, so every numeric field goes
through `byterev.l` first. `byterev` is ColdFire ISA_A+ (opcode `0x02C0 |
reg`). Under the `m68k:cfv4e` profile objdump prints it as `.short 0x02c0`;
the `m68k:isa-aplus` and `m68k:isa-c` profiles print `byterev %d0` but drop
the EMAC instructions (the `msacl` gate at `0x40003664` comes out as `btst`
and `.short`). No single profile decodes both; this page reads the header
builder under `cfv4e` and decodes the `.short 0x02c0` words by hand.

Let `A` be the block align, that is bytes per sample times channels. Let `D`
be `sampleCount * A`, the audio byte count. Let `P` be `D & 1`, the RIFF pad.

| offset | size | content |
|---|---|---|
| `+0x00` | 4 | `RIFF` |
| `+0x04` | 4 | `D + P + 44` |
| `+0x08` | 4 | `WAVE` |
| `+0x0c` | 4 | `fmt ` |
| `+0x10` | 4 | 16 |
| `+0x14` | 2 | 1, PCM |
| `+0x16` | 2 | channels |
| `+0x18` | 4 | 44100 |
| `+0x1c` | 4 | `44100 * A`, byte rate |
| `+0x20` | 2 | `A`, block align |
| `+0x22` | 2 | 24 or 16, bits per sample |
| `+0x24` | 4 | `data` |
| `+0x28` | 4 | `D + P` |

Total 44 bytes, `0x2c`, matching the `pea 0x2c` at `0x40021026`.

The sample rate is the literal `44100` at `0x40020fca` and `0x40020fd8`. It is
not read from the slot. ✅

### 🟡 The RIFF size field looks eight bytes too large

The RIFF specification puts the total file size minus 8 in the field at
`+0x04`. Here that is `D + P + 36`. The firmware computes `D + P + 44`, at
`0x40020f78`, as `lea %a0@(2c,%d1:l),%a0` with `a0` holding `P` and `d1`
holding `D`. Nothing is appended after the pad byte, so there is no extra
chunk to account for the difference.

Either the firmware writes a value 8 too large, which most decoders ignore
because they trust the `data` chunk size, or the `lea` is being misread.

**Falsifier, and it needs no tools:** take any `.wav` the Octatrack saved,
read bytes 4 to 7 as a little endian integer, and compare with the file size
minus 8. If they differ by 8, the firmware is off by 8.

---

## 4. The audio loop

✅ The same `0x46c2d980` scratch buffer is reused as a **3,072 byte** staging
area. The count of sample frames that fit is computed once, at `0x4002105a`:

```
d6 = 3072 / A          remul %d4,%d6,%d6
```

That is 512 frames at 24 bit stereo, 768 at 16 bit stereo, 1,024 at 24 bit
mono (3,072 is bytes; ❌ an earlier reading said "3,072 sample chunks").

objdump prints that instruction as `remul`; it is a divide and the value
is the quotient. The encoding `4c44 6006` is ambiguous: `m68k-linux-gnu-as
-mcpu=5407` assembles both `divu.l %d4,%d6` and `remul %d4,%d6,%d6` to
those bytes (destination and remainder registers the same), and binutils
prefers the `remul` spelling. `A` is 2, 3, 4 or 6 and 3,072 is divisible by
all four, so a remainder would be 0 in every configuration and the loop
would abort with `-51`; the quotient is what the surrounding code compares
against the contiguous run to pick a chunk size.

Each pass:

1. `0x4009499c(slotId, position, 1)` returns a pointer in `d0` and the
   contiguous run available at that position in `d1`. ✅ This is the pool page
   walk. It has exactly two callers, this loop and `0x4008e4f4`, and it
   branches on `slotId - 128 <= 7`, that is on whether the slot is a recorder
   buffer.
2. The frame count for this pass is `min(d6, d1, remaining)`. A result of zero
   aborts with `-51`.
3. The converter runs, chosen by the 16 bit flag at `0x40021042`:
   `0x40097b54` for 16 bit, `0x40097f8c` for 24 bit. It is called as
   `(dest, src, valueCount, 1)` where `valueCount` is frames shifted left by
   the stereo bit.
4. The write primitive `0x400166b8` writes `frames * A` bytes.
5. `remaining -= frames`, `position += frames`.

After the loop, at `0x400210cc`, a zero byte is staged and `0x400166b8` is
called UNCONDITIONALLY with length `d5 = P` — one byte when `P` is 1, a
zero-length write when `P` is 0 — and its return is range-checked either
way (`blt` at `0x400210ea`). That is the RIFF pad, and it is correct; a
copy of the writer's shape onto a file API that rejects zero-length writes
must gate the call, and the port watch in section 7 will see one extra
`0x400166b8` call per save.

**Why this matters for anything that streams to the card:** the loop is
already page aware and already chunked. It walks a block chained pool, it
never assumes the audio is contiguous, and it writes in bounded pieces.

---

## 5. The file API underneath

✅ Corroborated by two other projects that traced it independently, which is
stronger evidence than either alone.

| routine | address | named by |
|---|---|---|
| open | `0x40016864` | ems-octakit `runtime/abi.inc` (a submodule here until 6 Oct 2026), octamax's `NOTES.md` (octamax's notes, not in this repo) |
| read | `0x40016564` | both |
| seek | `0x4001660c` | ems-octakit |
| write | `0x400166b8` | both |
| close | `0x4001677c` | both |
| project directory | `0x40025230` | both |
| sprintf | `0x40013a08` | octamax |

Mode strings: `"w"` at `0x400b328b`, `"r"` at `0x400b3289`.

octamax also reports two working patches that create files on the card from a
detour using this API, so the write side is proven in practice and not only in
disassembly.

---

## 6. The recording auto-name, and the clock

Recordings are named `YYMMDD-HHMM`. Two recordings saved in the same minute
collide, and the user has to rename one by hand. This section is why.

✅ The name builder is `0x400819fc`. It formats
`%02d%02d%02d-%02d%02d` (`0x400b77bb`, referenced from this one site only)
into a buffer at `0x460faab4`.

It reads the clock through two helpers:

- `0x4001c4d8(index)` reads one field. It is a **DSPI** (SPI) transaction:
  `0xfc05c000` is the MCF5445x DSPI (route A, retired 26 Sep 2026, 60509404;
  `git show 3ceba41:docs/history/RTOS_FORK.md` section 4). Under a mutex (`0x400009f4`/`0x40000ab4` on
  `0x46c8c5f4`) it pushes two frames to PUSHR (`+0x34`: `0x90020000 | index`,
  then `0x10020000`), polls SR (`+0x2c`) until RXCTR (bits 7:4) reads 2, pops
  POPR (`+0x38`) twice and keeps the second byte. ✅ (❌ was "an I2C
  transaction": the I2C block is `0xfc058000`; the clock is on SPI.)
- `0x4001c31c(value)` converts BCD to binary, as
  `(v >> 4) * 10 + (v & 15)`. ✅ So the clock returns BCD.

### The field map

✅ Measured, by comparing the name builder against its sibling at
`0x40081968`, 148 bytes earlier, which formats
`%04d-%02d-%02d %02d:%02d:%02d` (`0x400b779d`) and therefore prints seconds.

| index | field | used by the timestamp `0x40081968` | used by the name `0x400819fc` |
|---|---|---|---|
| 1 | second | yes | **no** |
| 2 | minute | yes | yes |
| 3 | hour | yes | yes |
| 4 | 🟡 day of week | no | no |
| 5 | day of month | yes | yes |
| 6 | month | yes | yes |
| 7 | year, two digits (the timestamp routine adds 2000 at `0x400819d0` before its `%04d`; the name builder passes it as read) | yes | yes |

Index 4 is skipped by both routines. Day of week is the one calendar field
neither a filename nor a timestamp needs, which is the reading, but nothing
here reads it, so it is inferred. Falsifier: call `0x4001c4d8(4)` and compare
against a known date.

Index 0 is never read by either routine and is unidentified.

**So the collision is not a missing capability.** Seconds are available at
index 1, and the sibling routine 148 bytes away already reads them. The name
builder simply does not ask.

---

## 7. What is not known

- **The writer has not been executed here.** Everything above is a static
  read with a correct decoder. Running it means driving SAVE SAMPLE under
  `tools/emu/` route A and watching for the `0x400166b8` call with length
  `0x2c` from `0x40021032`. Falsifier: if no 44 byte write precedes the audio
  chunks, the header builder is not what it looks like. A stock save path
  HAS run on hardware by another caller: octalab's CAPTURE (nordseele, MKI,
  21 Sep 2026 ✅) drives the storage-job entry `0x40024168`, which reads the
  object to save from `0x460be9ec` (`movel` at `+0x08`, re-read here) and its
  kind from `0x460be9e8` — the pair `MAINMENU.md` section 7's select committer
  writes its pending edit to. With the pair unset on one path the job wrote
  header-only WAVs; set before each job, real audio. Whether that job reaches
  `0x40084e46` → `0x40020f04` is not traced.
- **The converters `0x40097b54` and `0x40097f8c` are not disassembled.** Their
  argument shape is known from the call site, their internals are not.
- **The FAT layer is still unmapped.** `0x40016864` and `0x400166b8` are used
  as black boxes here, exactly as `git show 3ceba41:docs/history/COVERAGE.md` says. File creation, directory
  entries and cluster allocation are all behind them.
- **`0x46105408`, the guard word, is unidentified.** It gates the whole writer.
- **The reader is a separate routine at `0x400210fc`**, with two call sites,
  `jsr` at `0x40093b12` and at `0x4009670e`. ✅ Both verified. 🟡 Those sit
  inside what octamax names the static loader `0x40093980` and the flex loader
  `0x40096548`, but the function boundaries were not checked here. The reader
  parses `RIFF`, `WAVE`, `fmt `, `data`, `cue ` and `smpl` from `0x400213ec`
  onward. Not covered here.
- **Card write throughput has never been measured**, in this project or in
  any of the three others surveyed. Every figure that exists is a sector count
  from an emulator. Nothing on this page should be read as a statement about
  how fast the card can be written.

---

## 8. The attribute file (`.ot`) and the tempo

A sample's attributes (its tempo, trim, loop, timestretch, gain and
slices) live in a 1,096-byte record per slot. A save also writes them to a
file beside the WAV, with the same name and the extension `.ot`. This
section is how that file is written, where a recording's tempo comes from,
and what tempo a sample gets when it has no `.ot`.

Read from the image named at the top of this page, 9 Oct 2026. Nothing in
this section has run under the port.

### 8.1 The writer `0x40089940` ✅

```
long ot_write(void *handle, long kind, long id)
```

- Kind 0: the record at `0x100d5b30 + id × 1096`, id at most 128.
- Kinds 1 and 4: the record at `0x100b14f0 + id × 1096`, id at most 135.
  That's the arena with the recorder buffers, ids 128 to 135
  (`RECORDER.md` section 1).
- Any other kind returns 0. A write that fails returns its negative code,
  and success returns 1.

✅ Kind 0 is a Static slot and kind 1 a Flex slot: the project parser
sets kind 1 for `TYPE=FLEX` and 0 for `TYPE=STATIC` (`0x400868a4..d8`)
before it calls 8.3's defaults routine with that kind. The Static arena
starts 136 records after the Flex one. Kind 4 isn't named.

Its one caller is the engine job at `0x40084e7a`. The job opens the path
at its own `+10`, then calls the writer with its `+6` as the kind and its
`+2` as the id. The WAV save is the job beside it, at `0x40084ddc`
(section 1). The storage job `0x40024168` builds the WAV path and queues
the WAV job (type 22). It then swaps the path's extension for `ot`
(`0x400b3a9f`) and passes the new path to `0x40022a28`. 🟡 That call
queues the `.ot` job; `0x40022a28` isn't read.

The file is 832 bytes. Every number is big endian, the CPU's own order:
the writer passes the record's bytes straight to the write primitive
`0x400166b8`, with no `byterev`.

| offset | size | content | from the record |
|---|---|---|---|
| 0 | 4 | `FORM` (`0x400d1670`) | |
| 4 | 4 | the long at `0x460fab54` (not traced) | |
| 8 | 4 | `DPS1` | |
| 12 | 4 | `SMPA` (`0x400d167e`) | |
| 16 | 4 | the long at `0x460fab5e` (not traced) | |
| 20 | 2 | version, `0x0002` (`0x400d1682`) | |
| 22 | 1 | a flag (8.3) | `+296` |
| 23 | 4 | tempo, BPM × 24 | `+276` |
| 27 | 4 | trim length, bars × 100 | `+284` |
| 31 | 4 | loop length, bars × 100 | `+288` |
| 35 | 4 | timestretch mode 🟡 | `+272` |
| 39 | 4 | loop mode | `+292` |
| 43 | 2 | gain 🟡 | `+268` |
| 45 | 1 | trig quantization 🟡 | `+297` |
| 46 | 4 | trim start, in samples | `+300` |
| 50 | 4 | trim end, in samples | `+304` |
| 54 | 4 | loop point, in samples | `+308` |
| 58 | 768 | 64 slices, 12 bytes each | `+312` |
| 826 | 4 | slice count | `+1092` |
| 830 | 2 | checksum | |

The checksum is the 16-bit sum of bytes 20 to 829. The writer clears it at
`0x40089a22`, just before the version, and adds every byte it writes after
that.

How the fields are named:

- ✅ The tempo is BPM × 24 because the recorder stores the published tempo
  there (8.2), and that word is BPM × 24 (`RECORDER.md` section 1).
- ✅ The lengths are bars × 100, and the trim and loop points samples,
  from the converters in 8.3: they turn `+304 − +300` and `+304 − +308`
  into `+284` and `+288`.
- ✅ The loop mode is `RECORDER.md`'s "LOOP at state `+292`".
- 🟡 The timestretch mode, gain and trig quantization are named by order
  alone. The project file's sample keys run in the same order
  (`0x400b8617..0x400b866d`): `BPMx24`, `TRIM_BARSx100`, `LOOP_BARSx100`,
  `TSMODE`, `LOOPMODE`, `GAIN`, `TRIGQUANTIZATION`. Falsifier: a stock
  `.ot` saved with known attributes.

### 8.2 A recording carries the project's tempo ✅

The routine at `0x4000432c` sets recorder buffer n's record
(`0x100d38f0 + n × 1096`, the arena's id 128 + n). With interrupts masked
it writes:

- the trim start, trim end and loop point (`+300`, `+304`, `+308`);
- the flag `+296` = 0;
- the tempo `+276` = the long at `0x8000181c`, the published tempo
  (BPM × 24);
- `+280` = −`[0x80001820]`, that is 2³¹ / tempo24, a reciprocal the file
  doesn't carry.

So a stock recording keeps the tempo the project had when it recorded, and
its `.ot` carries it. The routine's callers aren't read.

### 8.3 The tempo a sample gets without attributes ✅ read, 🟡 when it runs

`0x40099148(kind, id, length)` sets a slot's defaults. The project parser
calls it at each `SLOT` key (`0x40086940`) and then applies the keys that
follow, so a project's saved tempo overrides it. 🟡 A sample
loaded with no `.ot` keeps these defaults. The routine's other callers
(`0x400255a0`, `0x40084b66`, `0x40084c34`) aren't read.

For a sample longer than 50,000 samples (1.13 s) it guesses a bar count
(`0x40020ad8`). Then it sets the tempo from that count and the trim
length (`0x40098fa8`, which also sets the flag `+296` to 1), the
timestretch mode to 2, and the loop mode to 1 for kinds 1 and 4, 0 for
kind 0. The guess:

- **The bar count comes from the length alone.** Below 65,536 samples
  it's half a bar. Otherwise it's 2^(k − 16) bars, where
  2^k ≤ length < 2^(k + 1): `ff1` at `0x40020aea` finds k, and the count
  is 50 shifted left by k − 15, in bars × 100.
- **The name can move it by one step.** When the caller passes a name,
  the routine tries half, once and twice that count. It keeps the first
  whose whole BPM, printed with `"%d"` (`0x400b465d`), appears in the name
  (`strstr`, `0x40014158`). With no match it keeps the count.
- **The tempo follows from the count.** tempo24 = 2,540,160 × bars×100 /
  length, rounded (`0x40020a94`). The reverse, at `0x40020a24`, is bars ×
  100 = length × tempo24 / 2,540,160, rounded, with tempo24 clamped to
  720..7,200 (30 to 300 BPM). 254,016,000 / tempo24 is one bar of four
  beats in samples.

So the guessed tempo always lies between 80.75 and 161.5 BPM, and the
guess never reads the project's tempo. A 61 s file recorded at 120 BPM
(2,690,100 samples) loads as 32 bars at 125.9 BPM.

🟡 Falsifier, on the unit: STEM REC's take `261008-1858` (189,872 frames,
4.31 s) predicts 2 bars at 111.5 BPM, and take `261008-1131` (297,632
frames, 6.75 s) 4 bars at about 142.2 BPM, whatever the project's tempo
was. Load one file from each into a Flex slot and read TEMPO on the AUDIO
EDITOR's ATTRIBUTES page.
