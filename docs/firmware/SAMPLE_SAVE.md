# How a recording becomes a `.wav` on the card

The firmware writes WAV files itself. This page is the save path: the
routine that emits the header, the loop that streams the audio out of the
sample pool, the file API underneath, and the clock that names the file.

**Method.** Read from `out/raw/section_3_MAIN_OS.bin`, SHA-256
`164f31224bf61181e3f50e7dec40df9afcae5b16dbf6e4c0d0cc5e986af0a84e`, load base
`0x40000400`. Disassembled with `scripts/disasm.sh emac`, that is
`objdump -m m68k:cfv4e`.

⚠️ **Do not read this region with r2.** `scripts/disasm.sh` records why:
6,757 instructions below `0x40098000` that r2 cannot decode, 4,543 of them
longer than two bytes, so the stream desynchronises and invents plausible
code. An earlier reading of this same routine with r2 got the staging buffer
wrong by a factor of the block size, and turned a `mulsl` and a `remul` into
`invalid`. Every claim below was re-derived with cfv4e.

Confidence markers as in `CHIP.md`: ✅ measured, 🟡 inferred with a falsifier
stated, ❌ retracted.

---

## 0. Why this page exists

Two independent projects list this path as unmapped. `docs/history/COVERAGE.md`
here, and octamax's `COVERAGE.md`, both record that no WAV writer and no
sample-save path had been located. Both were wrong. The writer is at
`0x40020f04` and it has always been in the image.

The practical consequence: **writing audio to the card is not new machinery.**
Anything that wants to put samples on the card can call what is already there.

---

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

**135 is `0x87`, the last recorder buffer.** `EXTERNAL.md` §6 records that
recorder buffers are object ids 128 to 135 in the same arena as the sample
slots. This writer accepts them. It is not restricted to sample slots.

✅ The slot's control record is `0x46c922c4 + slotId * 44`, which is the same
base and stride `EXTERNAL.md` gives for the state arena. Two flag bits in the
first word of that record drive the whole format:

| bit | clear | set |
|---|---|---|
| 0 | mono, 1 channel | stereo, 2 channels |
| 1 | 24 bit, 3 bytes per sample | 16 bit, 2 bytes per sample |

Bit 1 is read twice, once for the byte count at `0x40020f48` and once for the
`bits` field at `0x40020ff6`, and the two agree. That internal consistency is
why the mapping is marked measured rather than inferred.

✅ Return codes: `1` success, `-2` a guard failed, `-51` a chunk of zero
length was computed, or the negative value the write primitive returned.

---

## 3. The 44 byte header

✅ Built in a scratch buffer at `0x46c2d980`, then written in one call. The
CPU is big endian and RIFF is little endian, so every numeric field goes
through `byterev.l` first. `byterev` is ColdFire ISA_C, opcode `0x02C0 | reg`.
Neither r2 nor binutils `m68k:cfv4e` decodes it; objdump prints `.short 0x02c0`.
It is decoded here by hand, and the little endian requirement makes the
reading certain.

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
mono. ❌ An earlier note here said "3,072 sample chunks". That was the r2
misreading, and it is wrong: 3,072 is bytes.

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

After the loop, a single zero byte is written if `P` is 1, at `0x400210cc`.
That is the RIFF pad, and it is correct.

**Why this matters for anything that streams to the card:** the loop is
already page aware and already chunked. It walks a block chained pool, it
never assumes the audio is contiguous, and it writes in bounded pieces.

---

## 5. The file API underneath

✅ Corroborated by two other projects that traced it independently, which is
stronger evidence than either alone.

| routine | address | named by |
|---|---|---|
| open | `0x40016864` | ems-octakit `runtime/abi.inc`, octamax `NOTES.md` |
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

- `0x4001c4d8(index)` reads one field. It is an I2C transaction against the
  peripheral registers `0xfc05c02c`, `0xfc05c034` and `0xfc05c038`, polling
  until a status nibble reads 2. ✅
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
| 7 | year, plus 2000 | yes | yes |

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

- **The writer has not been executed.** Everything above is a static read with
  a correct decoder. Running it means driving SAVE SAMPLE under `tools/emu/`
  route A and watching for the `0x400166b8` call with length `0x2c` from
  `0x40021032`. Falsifier: if no 44 byte write precedes the audio chunks, the
  header builder is not what it looks like.
- **The converters `0x40097b54` and `0x40097f8c` are not disassembled.** Their
  argument shape is known from the call site, their internals are not.
- **The FAT layer is still unmapped.** `0x40016864` and `0x400166b8` are used
  as black boxes here, exactly as `COVERAGE.md` says. File creation, directory
  entries and cluster allocation are all behind them.
- **`0x46105408`, the guard word, is unidentified.** It gates the whole writer.
- **The reader is a separate routine at `0x400210fc`**, called from the static
  and flex loaders `0x40093b14` and `0x40096710`. It parses `RIFF`, `WAVE`,
  `fmt `, `data`, `cue ` and `smpl` at `0x400213ec` onward. Not covered here.
- **Card write throughput has never been measured**, in this project or in
  any of the three others surveyed. Every figure that exists is a sector count
  from an emulator. Nothing on this page should be read as a statement about
  how fast the card can be written.
