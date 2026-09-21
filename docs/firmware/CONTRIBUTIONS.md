# Contributions received: the dated index

Reverse-engineering results and notes contributed by others, by date, with
where each now lives. The facts themselves are in the
topical docs with their status markers (✅ re-verified here · 🟡 adopted on
the author's evidence · ❌ retracts something written here) and the
author's name beside them. Until 22 Sep 2026 this file held the findings
in full, fourteen sections; that text is the topical docs now, and the
ingest record with the notes exchanged verbatim is
`git show 3ceba41:docs/history/EXTERNAL_INGEST.md`. All were derived from
the officially distributed OS 1.40C (`section_3_MAIN_OS.bin` SHA-256
`164f3122…`, base `0x40000400`).

| received | from | what | where it lives |
|---|---|---|---|
| 30 Aug 2026 | Bryan T | the Echo Freeze DELAY is a ColdFire routine over SDRAM rings | `COLDFIRE_DELAY.md` §1 🟡 |
| 30 Aug 2026 | Bryan T | the ESAI carries audio ("does not" retracted) | `DSP.md` §6c ✅ |
| 30 Aug 2026 | Bryan T | timestretch is a ColdFire feature; `P:0x3a1` / `P:0x2bf` / `func_00055a` relabelled | `DSP.md` §3 🟡 |
| 30 Aug 2026 | Bryan T | the data-table atlas (Q23 decode of every X/Y module) | `TABLES.md` 🟡, evaluated 31 Aug |
| 30 Aug 2026 | Bryan T | `objdump -m m68k:cfv4e` for EMAC regions; radare2 cannot decode this CPU | `docs/remixer/TOOLING.md` §3 ✅ |
| 2–6 Sep 2026 | Bryan T | the track recorders, five sessions: descriptor, storage tiers, length arithmetic, pool, write path, loop point | `RECORDER.md` §1–2 ✅ bytes, 🟡 reading |
| 4 Sep 2026 | Bryan T | `bryantysinger/octa-bt-pt` (stock-effect defaults patcher; its parameter registry) | `PARAM_PAGES.md` §5g |
| 4 Sep 2026 | June Kiff | `emuyia/ems-octakit` (256 kits) | `modules/octakit`, a submodule (`THIRD_PARTY.md`) |
| 6 Sep 2026 | Bryan T | *Sound-on-Sound Looping with the Octatrack* (PDF) and `octatrack_clickless_loops.xlsx`; not in this repo | `RECORDER.md` §3 |
| 13 Sep 2026 | nordseele | [`octalab-notes`](https://github.com/nordseele/octalab-notes) at `40ffa53` (MIT, findings only), from an Octatrack MKI running our loader: FS layer, slot loading, Parts, the card's files, step records and lock stores, the input layer, menus, the platform reserve on hardware | `STORAGE.md`; `PARAM_PAGES.md` §5g; `PANEL.md` §4b; `MAINMENU.md` §2, §5; `PLACEMENT.md`; `MIDI.md` (PLAYBACK `machine*6`); `tools/hw/ot_project.py` (trig masks `0x40`/`0x48`) |
| 14 Sep 2026 | Bryan T | absolute X addresses are payload-relative (his LOFI2 mistuned on tracks 1–4) | `TABLES.md` "Payload-relative addresses" ✅; `FAILURE_MODES.md` |
| 16 Sep 2026 | Bryan T | the parameter enable bitmaps | `PARAM_PAGES.md` §3b ✅, with retractions |
| 21 Sep 2026 | Bryan T | the track LFO engine | `LFO.md` (§8 what was checked) ✅, with retractions both ways |
| 21 Sep 2026 | Bryan T (hardware) | MAIN/CUE are `(L/128)²` | `LEVEL_LAW.md` (§7 what was checked) ✅ |
| 22 Sep 2026 | Jannik Aßfalg (repeat98) | beside Tape Echo (PR #357): the delay routine's frame, seam and per-frame protocol; benchmarking practice for a ColdFire module | `COLDFIRE_DELAY.md` §2–4 ✅, with a retraction; `docs/remixer/MODULES.md` "Pricing a ColdFire module"; `FAILURE_MODES.md` |
| 22 Sep 2026 | markandrus (public repo, not sent to us) | [`octemu`](https://github.com/markandrus/octemu) at `8ccdd84`'s dsp56300 pin (QEMU 11.1 + dsp56300 + SDL2 Octatrack emulator, credits this project as inspiration): three MAC-with-load decode defects in Unicorn's vendored QEMU, confirmed against Unicorn's own source; that `vendor/dsp56300` was 144 commits behind upstream, absorbing several of our own fixes independently; the DMA "de-renewal" semantics for a same-value DCR rewrite mid-window. His three ColdFire firmware customisations (RECEIVE machine, USB-MIDI, USB-Audio) and `re/*.syms` (768 ColdFire + 150 DSP symbols) were reviewed but not adopted; his QEMU and dsp56300 patches beyond the three above did not apply to our Unicorn/dsp56300 or were JIT-only, N/A to `execInterpreter()` | `tools/patches/unicorn_emac_fractional.patch` ✅ (PR #360); `CLAUDE.md` History (the re-pin, PR #365; the DE-renewal, PR #367); `docs/remixer/EMU.md` (the "no MAC-with-parallel-load form" retraction) |

Modules that arrived as code rather than notes (midisc, Octakit,
octalab, REPITCH) are the README's module table and `THIRD_PARTY.md`.
