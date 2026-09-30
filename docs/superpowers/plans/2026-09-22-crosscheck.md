# Cross-check: STEM REC against the other five repos

**Goal.** Check every firmware claim in our work against what the other
repos say about the same code. Settle each disagreement from the stock
image, not from either repo.

**Our work** is the 70 commits on `stem-rec-poc` (Yves Rosius, 10 to 14
Sep 2026): `docs/firmware/STEM_REC.md`, `modules/stems/`, the STEM REC
spec and plan, and their entries in `FAILURE_MODES.md`, `FLASHPLAN.md`,
and `PLAN.md`.

**The references** (pulled 22 Sep 2026):

| Ref | Repo | Head | What it knows about |
|---|---|---|---|
| M | Octabam `main` | `5b03d11` | Sam's docs since the branch point: `STORAGE.md`, `KERNEL.md`, `RECORDER.md`, `SAMPLE_SAVE.md`, `CHIP.md`, `ARCHITECTURE.md` |
| K | ems-octakit | pulled | a DRAM runtime that loads and saves files, menus, the arena |
| O | octamax | pulled | the kernel, static streaming from the card, the arena, hot-swap |
| L | octalab | cloned | the file layer (`FS_LAYER.md`), slot loading, menus, trigs |
| S | midisc | pulled | scene locks, part apply, a memory map |
| B | octa-bt-pt | pulled | DSP parameter defaults; little overlap expected |

**A reference is a lead, not evidence.** The oracle is
`out/raw/section_3_MAIN_OS.bin` (base `0x40000400`, SHA-256
`164f3122…af0a84e`), disassembled with `scripts/disasm.sh emac` in WSL
(`/home/yvez/octabam-stems`), and the ColdFire port where behaviour
matters.

## Verdicts

Each checked item gets one verdict.

- **AGREE**: the reference says the same thing.
- **EXTENDS**: the reference knows more, and it doesn't contradict us.
- **CONFLICT**: the reference says something incompatible with us.
- **NO OVERLAP**: the reference cites the address for an unrelated reason.

Each CONFLICT is settled from the image. It ends as either "we were right"
(with the evidence) or a correction to our docs, committed on its own.
An EXTENDS that changes a claim of ours is handled the same way.

## Steps

1. **Census tool.** A script that pulls every 8-digit firmware address,
   with its line, from our work and from each reference. It folds the
   uncached alias (`0x48…` to `0x4f…`) onto `0x40…` to `0x47…`. Output:
   one table per reference of the addresses we share.
2. **Claim inventory.** From STEM_REC.md, the module, and the spec: every
   claim that rests on stock firmware, with its address and our
   confidence marker.
3. **Address pass.** For each shared address, read both sides and give a
   verdict.
4. **Topic pass.** Some overlaps have no shared address, only a shared
   subject. Read the references by topic:
   - the file layer: open, write, seek, close, mkdir, and the file lock
   - the card driver: PIO and DMA, UDMA modes, aborts, sector bounce buffers
   - the kernel: task creation, the TCB, sleeping, queues
   - the transport word and the step clock
   - the recorder and the read-back block (T1's slot)
   - the clock chip and file names
   - CONTROL menu rows
   - DRAM: the platform reserve, the arena, the top window
5. **Settle.** Re-derive every CONFLICT from the image. Commit each
   correction on its own, with the evidence in the message.
6. **Report.** `docs/firmware/CROSSCHECK.md`: the verdict table, what
   changed, and what stays open. Written to the Microsoft style guide.

**Done** when every shared address and every topic has a verdict with
evidence, and each correction is committed. Nothing is pushed.

## Progress

Updated as the work goes.

- [x] 1 census tool (1,893 of our addresses; 306 shared)
- [x] 2 claim inventory (the module's 27 stock facts first)
- [x] 3 address pass (a seventh reference, markandrus/octemu, added mid-run)
- [x] 4 topic pass (file layer, card driver, kernel, read-back, CONTROL rows)
- [x] 5 settle (one commit per correction; the T1 slot fixed in code)
- [x] 6 report (`docs/firmware/CROSSCHECK.md`)
