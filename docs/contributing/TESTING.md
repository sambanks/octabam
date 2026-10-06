# How the testing works

Every claim in this repository is checked on the developer's machine,
without hardware, against the developer's own copy of OS 1.40C. This page
is the whole mechanism: what runs, what each gate proves, how a change is
routed to the gates it can affect, how the gates are made fast, how to
write one, and what none of it can see. `CONTRIBUTING.md` is the contract
a pull request signs; this page is how it is met.

```
make check REMIX=<name>          one remix: build, cycles, the shared gates, the remix's own gates
make reach [RUN=1] [FULL=1]      the gates this branch's diff reaches, in order; RUN=1 runs them; quick unless FULL=1
make accept REMIXES="..." ...    the same gates under a strict runner that writes a JSON report
make test-acceptance             the runner's, the classifier's and the shard runner's own tests, and the OBAM store's
                                 (container corpus, settings, lock file, ot_store round trip; no firmware)
make identity                    which remixes' images this branch moved, byte for byte
scripts/refhash.sh check         a build change produced bit-identical artifacts and reports
make ci                          what GitHub Actions runs (no firmware, so no remix)
```

## 1. The instruments

| instrument | what it runs | built by | used by |
|---|---|---|---|
| **the build** (`tools/build/build_bus.py`) | assembles every selected DSP module, links every ColdFire unit, places both, writes `out/mainos_bus.bin` and a build report; refuses on a collision, an overrun or oracle drift; round-trips every assembled DSP word through the disassembler | `make setup` | every gate |
| **`dsp_host`** (`tools/harness/dsp_host/`) | the assembled DSP code on the dsp56300 emulator: renders audio, meters instructions per block, polices memory (`-guard`, `-dirty`), both cores in one process with the shared window (`-memB`), instruction interleave fuzz (`-skew`) | `make setup` | render gates, bit-identity gates, the knob census, the dirty-state gate |
| **the port** (`tools/emu/ot_emu`) | the whole machine: the ColdFire firmware booting the built image, a staged CF card with a real project, the sequencer, both DSP cores, MIDI in and out, USB device and a scripted host, the panel link | `make emu-cf` (per worktree, ~1 min) | the DRAM boot, the set gates, USB, every ColdFire module's behaviour gate |
| **Tier-0** (`tools/emu/emu_bringup.py`, Unicorn with the EMAC patch) | boots the firmware to its scheduler handoff and calls its draw and formatter routines directly | `make emu-setup` (the `.venv`) | label gates, CC MAP, CC FEEDBACK, REPITCH's page gate |

Inputs every gate assumes: `out/raw/section_3_MAIN_OS.bin` (`make os && make
recon`, from your own 1.40C), the submodules (`git submodule update
--init`), and for the set gates a real project directory in `OT_PROJECT`
or `~/.octabam_project`. `tools/harness/README.md` is `dsp_host` in depth,
`tools/emu/README.md` the port and Tier-0.

**The hardware lab's MIDI.** The Rytm is clock master over its own USB port
(`ot_midi.py -p "Elektron Analog Rytm MKII" start|stop`); start/stop is
never sent to the OT's own port. A Midihub reverts to its stored preset on
a power or USB blip, so its session pipes are saved (FROM A →
drop-realtime-only → OCTATRACK).

**The verdict vocabulary.** A gate prints `[ok]`/`[PASS]` per check and
exits non-zero on any `[FAIL]`. `[SKIP]` means an instrument, a project
or a toolchain is missing: `make check` still exits 0, `make accept`
refuses the run. `[ -- ]` or `[N/A]` means the gate's subject is not in the
remix (a MODE DEFAULTS gate on a remix without MODE DEFAULTS): passed, not
skipped.

## 2. `make check`: the two halves

`make check REMIX=<name>` is `bus`, `cycles`, then `verify`, and `verify`
is two halves (`Makefile`: `verify-shared`, `verify-remix`). There is no
default remix.

**The shared half** (`make check-shared REMIXES="a b c"`) does not depend
on which remix is selected, so a run over several remixes does it once:

| step | proves |
|---|---|
| `tools/remix/selftest.py` | the ledger refuses every collision it claims to (FX2 id, declared conflict, cave, hook and detour span, poke, table and symbol ref, runtime write, kept bytes, grown table, private Y word, FX2 buffer region, DSP data range, DSP hook site), every shipped remix is clean, the placer fills non-contiguous runs in both payloads |
| `verify_slots` | no dead store in BusVerb's per-instance state block |
| `verify_replaces --static` | a declared replacement names a real stock effect and carries its id (the registry only) |
| `verify_docs` | the README module table and the remix index match the manifests and selections (`make docs`); every remix has a README; every relative Markdown link and anchor, and every `docs/…`, `tools/…`, `modules/…` or `remixes/….md` path written in a tracked text file, resolves (`tools/verify/doclinks.py`); no section sign in a `.md` |
| `verify_descdefaults` (on demand: `python3 tools/verify/verify_descdefaults.py [REMIX]`) | the FX2 and FX1 choosers' select lands the effect's descriptor defaults, and the poked bytes when those twelve are poked in RAM after the load: what the store's card-layer defaults rest on (`docs/proposals/STORE.md` section 5.1); port, project |
| `store.py check` | no two modules share a store id; every module with a `Store` or a keyed `Param` has a current `store.lock` and breaks no released key; every remix's `settings` names a selected setting and a value inside its bounds, a module that `requires_core` has the core, early settings fit the remix's free CS1 run (`docs/proposals/STORE.md` section 4.3) |
| `verify_remixer` (`Makefile` verify-shared) | the remixer (`make remix`) opens and draws headless under Textual's test pilot for stock and every remix (three panes, cursor in each); `k` moves the cursor up in AVAILABLE and `K` resets to stock. SKIPs without textual |
| `tools/build/label_fmt.py` | the select formatter caves re-derive from their sources (with `m68k-elf-as` on PATH) |
| `verify_knob_clicks` | the knob census: every continuous knob of the fixture remix's DSP modules moved mid-render, the block-rate step in dBFS; a garbage start stays quiet |
| `module_gates.py --shared` | every manifest gate declared `remix_arg=False` by a module in the selection, once for the union; every `once=True` gate, once, on the named remix with the fewest modules that carries its module |

**The per-remix half** (`make check-remix REMIX=<name>`), in recipe order:

| step | proves | needs |
|---|---|---|
| `bus`, `cycles` | the image builds; static per-sample cycles of every module and the worst load one core can be asked for, against the measured wall; an insert is priced at four copies, or at its declared `max_per_core` (declared, not enforced by the unit) | |
| `verify_dirtystate` | each DSP module rendered from a garbage-filled instance block on silence is silent or identical to the zeroed render | `dsp_host` |
| `verify_initregs` | no module's `init` writes r1/n1/m1 (the dispatcher keeps the effect id there) | |
| `verify_dram_boot` | the image boots under the port; the loader runs once, its `fatal` never, every DRAM window reads back equal to the linked runtime | port |
| `verify_labels`, `verify_modenames`, `verify_hidden` | the firmware's own formatter code prints each select's words; the MODE formatter renames its neighbours; a hidden engine is placed, dispatched, off the chooser and draws nothing | `.venv` |
| `module_gates.py --stage isolated --remix-only` | the manifest gates declared `remix_arg=True` and not `once` | per gate |
| `verify_menu` | the FX1/FX2 choosers and every cloned descriptor against the chooser logic decompiled from the firmware: row order, formatter vs value count, name-field lengths, link bits | |
| `verify_replaces --image` | on this image, every stock effect id is stock's or declared by `replaces`, on both menus (until 29 Sep 2026 the shared half built all 35 remixes for this: 41 s warm, 402 s on a cold build memo) | |
| `verify_set` | a real project on the image under the port: the load completes, live ids equal the part's, page-2 lanes reach the DSP record, every track with audio has chain output, CCs over MIDI IN move the right bytes, CC FEEDBACK's wire and cache, the load rewrote no project file, the firmware's log is clean | port, `.venv`, project |
| `verify_usb` | the image enumerates under the port with the descriptors its USB modules declare; the streams run at their cadence; mass storage still answers | port |
| `module_gates.py --stage image` | the manifest gates that read the finished image | per gate |

`make bus` runs again between steps that leave a probe build at
`out/mainos_bus.bin` and at the end, so the shipping image is on disk after
a green run.

## 3. Every gate

### Run by `make check` for every remix

The two tables above.

### Declared by modules (`schema.Gate`), run only for remixes that carry the module

| gate | owners | half | proves | needs |
|---|---|---|---|---|
| `verify_twocore` | REVERB SERVER, DELAY SERVER | shared | the servers on their real cores render bit-identical to the one-core DEV hatch, and under four interleave skews; fixture `remixes/test/bus` | `dsp_host` |
| `verify_onebus` | REVERB SERVER, DELAY SERVER | shared | both sends on both cores: each host's wet print, WET passthrough sample-exact, the T8 refusal, stored old bytes inert, four skews | `dsp_host` |
| `verify_grains` | DELAY SERVER | per remix | `Remix.grains` changes GRAIN only: the pricer sees it, every other case bit-identical | `dsp_host` |
| `verify_tempo` | DELAY SERVER | per remix | the delay's tempo snap lands on the tempo word the frame builder publishes | `dsp_host` |
| `verify_burn` | SEND | per remix | the RIG BURN probe image is the shipping one plus an inert, exact knob | `dsp_host` |
| `verify_character`, `verify_spectrum`, `verify_modulation` | the three stations | shared | each station against arithmetic you can predict or a float reference: bypass bit-exact, every mode, bounded resonance, the FX1-only promise | `dsp_host` |
| `verify_miniverb` | MINIVERB | image | eight instances isolated, dirty memory, buffer guards, audio gates | `dsp_host` |
| `verify_euclid` | EUCLID | image | control math, the ColdFire hooks, DSP renders, playback under the port | `.venv`, port, project |
| `verify_tapeecho_cpu` | TAPE ECHO | image | the C reference against the compiled ColdFire port, through the stock delay routine and its DMA protocol | `.venv`, `cc`, port |
| `verify_modedefaults` | MODE DEFAULTS | per remix | a MODE turn through the panel's editor, and a MODE over CC MAP, lands that mode's view in the live lane (one boot, `--step`) | port, project |
| `verify_scenesp2` | SCENES P2 | per remix | page-2 scene locks reach the DSP frame through the crossfader (snap for a select, lerp for a knob); a page-2 turn with a scene held writes the pool, not the Part (one load, four forked scenarios, `--scenario`) | port, project |
| `verify_tempobus` | TEMPO BUS | image | the TEMPO key opens the bus window, its rows edit the hosts, LEVEL and FUNC + LEVEL set the BPM, the window closes clean (a panel script, `--live-script`, on the image and card `verify_set` stages; `verify_set --stage-only` stages them without running) | port |
| `verify_repitch` | REPITCH | per remix | the hook contracts, the page (Tier-0), and playback pitch and position speed through a live tempo change, seven cases | port, `.venv`, project |
| `verify_ccmap` | CC MAP | shared | the CC cave re-assembles to its pinned bytes; CC 62-73 write page 2 and clamp to the count; page-1 CCs reach stock | `.venv` |
| `verify_ccfeedback` | CC FEEDBACK | shared | the knob-change sweep enters the stock CC emitter once per changed byte, gated as stock gates | `.venv` |
| `verify_kits` | KITS | once, on the smallest carrier | staging through the Part slots, LOAD/SAVE KIT and the list ops, kits.work over a save, reboot and power cycle, migration, Octakit import, a rejected bank file | a project (OT_PROJECT), the port |
| `verify_scenes` | MIDI SCENES | once, on the smallest carrier | MIDI lock scenarios (hold-to-lock, readout, unlock, XF morph, scene apply and release, Part clear / copy / paste) with MIDI OUT bytes and frames, against stock and, with `--oracle`, against bkkbrls-del's MIDISC2.1 image; `--persist` (final gate, not in `make check`): `scenes.work` / `.strd` over a save, reboot and power cycle with CS1, a refused file under IGNORE / OVERWRITE / BACKUP, a 2.x project read once, Kits carrying the locks. Cannot see: the hardware, the sequencer sites (phase 3) | port, project |
| `verify_usb_in` | USB AUDIO IN AB, CD, ABCD | image | the host's channels land bit-exact on their RX slots, the others stay the jacks', the recorder ring fills, the jacks return at alt 0 | port, `.venv` |
| `verify_usb_align` | USB AUDIO OUT TRACKS MAIN CUE | image | MAIN and CUE are in phase with the tracks in the twenty-channel stream (lag 0) | port, `.venv` |
| `verify_cfmeter` | CF METER | per remix | the DSP meter under the port with T8's FX2 = CF METER: frames counted within 8 of the frames run; spin min <= max and > 0; period min <= max and > 0; DBRN 40 lowers the spin minimum with the period maximum unchanged (within 10 %); DBRN 127 raises the period maximum past 1.5 x run 1's. Cannot see: the unit's cycle costs (the port prices each instruction at one step) and the ESAI's real underrun behaviour | `.venv`, port, project |
| `verify_charkey` | CHARACTER | shared | KEY = T1 on both cores: a host-fed T3 (core 1) and T6 (core 0, also under four skews) duck in a burst; KEY = T1 with the host unfed holds no gain reduction; no host holds none; SELF is bit-identical fed or not; the master at KEY = T1 equals KEY = SELF; the host's own output is unchanged by Characters reading it. Cannot see: the chip's timing, anything the ColdFire does (knobs are poked into r6) | `dsp_host` |
| `verify_character_txtr`, `verify_charkey_txtr` (`modules/character-txtr/`) | CHARACTER TXTR | shared | `verify_character` and `verify_charkey` run on the TXTR module (a `Gate` takes no arguments, so each names the module) | `dsp_host` |
| `verify_fx2lock` | FX2 LOCK | image | T2, FX2 twice, DOWN, YES leaves the live FX2 ids (`0x80000ec4`) as a run that pressed nothing; with the poke undone in RAM the ids change; the poke is in the image. Without the module the same sequence turns T2's SEND into the stock DELAY | `.venv`, port, project |
| `verify_plocksp2` | PLOCKS P2 | per remix | under the port: page-2 locks recorded from the panel (record, copy and paste, clear, pattern copy / paste / clear, undo), played on trigs, saved to the card (`p2lkNN.work`, `.strd`) and loaded back, including a power-up load from CS1 (`--cs1-in`, `--no-post`). Cannot see: the dial draw (the LCD is not decoded), the hardware, a slide trig | port, project |
| `verify_testgen` | TESTGEN | shared | SINE against `sin(2 pi n inc / 2^24)` within 4 LSB, frequency within 0.003 Hz, FINE within 1 ppm, THD below −120 dB, LEVL steps of 0.5 dB within 0.01 dB, CHAN; SWEEP, WHITE, PINK, IMPULSE, NEEDLE and DC against `testgen_ref.py`; silent at LEVL 0; an invalid MODE byte is SINE | `dsp_host` |
| `verify_transient` | TRANSIENT | shared | defaults and MIX 0 bit-exact passthrough; a negated input gives the negated output within 4 LSB; the per-sample gain matches the float reference within 0.1 dB across ATCK and SUST extremes and three levels; SUST +63 raises no onset peak and steps under 0.5 dB between samples on a decaying tail; a steady 1 kHz tone moves under 0.25 dB | `dsp_host` |
| `verify_wave` | WAVE | image | pitch from the carrier, the chord, a pitch step, the envelope, silence, eight instances and the instruction bound, on the remix's own image, both payloads. Counts executed instructions, not hardware cycles | `dsp_host` |
| `verify_analog_bassdrum` | ANALOG BD | shared | the generated descriptor helpers | |
| `bd909.py`, `bd808.py` (`tools/harness/`) | ANALOG BD | shared | the 909 engine in `bd909_host` against `dsp909.Voice` (a mismatch is a DSP bug; a mismatch with Drumazon is a model limit); the 808 reference, retrigger, automation and desk stability | `bd909_host` built into `out/bd909` |
| `verify_analog_bd_exact.py`, `verify_analog_bd_levels.py` (`tools/harness/`) | ANALOG BD | shared | the original DSP output and state pinned by hash (all trigger offsets, rapid retriggers, long tails, control extremes, random block-rate automation) with both post-desk output gains verified; the shipped 808/909 defaults compared by fixed-window hit RMS | `dsp_host` |
| `verify_analog_bd_reverbs.py` (`tools/harness/`) | ANALOG BD | image | PLATE and DARK stay bit-identical to stock after SPRING is harvested, on both cores, with fixed and moving controls, at the hardware audio address X:0 | `dsp_host` |
| `verify_analog_bassdrum_cf` | ANALOG BD | image | the built ColdFire control transport and source setup ABI. Instruction counts are diagnostics, not hardware timing | `.venv` |
| `verify_analog_bassdrum_port` | ANALOG BD | image | the real source transport and main output, 808 on T1 and 909 on T5, with no audio sample staged: integration, not 808/909 timbre | port |
| `verify_analog_bassdrum_ui` | ANALOG BD | image | choosing Analog Bassdrum and selecting its engine with actual stock panel events | port |

`verify_repitch_ui` is called by `verify_repitch`; `verify_repitch_reference`
is an offline specification test nothing runs.

### On demand (own `make` target, not in `make check`)

| target | proves |
|---|---|
| `make verify-bus` (`SAVE=1` first) | a bus-layout change is behaviour-preserving over every layout in its case list: stamp, edit, compare |
| `make verify-delay CAND=...`, `make verify-roll CAND=...` | an alternate delay or reverb engine is bit-identical to the shipping one |
| `make verify-ident MOD=<station>`, `make verify-spectrum-ident` (`SAVE=1` first) | a rewritten station is bit-identical across a knob matrix |
| `make verify-midi` | the note to PITCH path, through a build override |
| `make verify-twocore`, `make verify-onebus`, `make verify-knobs`, `make verify-miniverb` | the gates of the tables above, alone |

### The port's own tests

`tools/emu/ot_emu` carries unit tests (`ctest --test-dir out/emu`): `emac`
(both ACCext layouts, the fractional modes, MAC-with-load), `periph`, and
three that read the stock OS (`rtos`, `dsp`, `repitch-stock`/`-patch`).
`make ci-emu` runs the two that need no firmware.

## 4. Module gates: a module carries its own tests

A module declares its gates in its manifest:

```python
gates=(Gate("tools/verify/verify_character.py", remix_arg=False),          # shared half, once
       Gate("tools/verify/verify_grains.py"),                              # per remix, gets the remix name as argv[1]
       Gate("tools/verify/verify_euclid.py", venv=True, stage="image"),    # per remix, after the image is final
)
dear={"DRV": 127, "FOLD": 127, "COMP": 127, "MIX": 127, "WDTH": 127, "SAT": 0},
```

- `remix_arg=False`: the gate builds its own fixture (`registry.fixture`,
  the smallest remix carrying what it needs) and runs once in the shared
  half. `True` (the default): it takes the remix name and runs in the
  per-remix half.
- `stage="isolated"` (default) runs before the menu and set gates;
  `"image"` runs last, on the finished `out/mainos_bus.bin` (and after
  `verify_set` has staged its card).
- `venv=True` runs it under `.venv/bin/python3` when the venv exists.
- `once=True` (with `remix_arg=True`, isolated): the gate checks the
  module's own code, the same in every carrier, so it runs once per run
  in the shared half, on the named remix with the fewest modules that
  carries the module, not once per carrying remix. `make check REMIX=x`
  on its own still runs it on x. For a ColdFire module's port scenarios
  (KITS: 29 scenarios, 371 s emulated, two carriers).
- A missing script is `[FAIL]`. The same script may not be listed twice.
- `dear` is every knob at its dearest setting by name; the stress fixture
  and the pressure render read it, and `make accept` is blocked by name for
  a DSP module without it.

## 5. Writing a gate

1. **Say what it proves and what it cannot see** in the docstring's first
   paragraph and a closing "What it cannot see" line. The catalogue above
   is built from those.
2. **Print a verdict per check** (`[ok]`/`[FAIL]`), a summary line, and
   exit non-zero on any failure. `[SKIP]` only for a missing instrument,
   project or toolchain, naming what to install; `[ -- ]` when the subject
   is absent from the remix.
3. **Pin arithmetic you can predict.** A render gate compares against a
   number derived from the algorithm or a float reference, never against
   "it sounds right". Prove the gate can fail: a positive control that
   makes the forbidden write, or an input that must change the output.
4. **Build into your own scratch** (`tempfile.mkdtemp` or `out/<gate>/`),
   never fixed `/tmp` names: two builds on one machine read each other's
   files (AGENTS.md).
5. **Under the port, load as few times as you can.** An Octakit project
   load is ~32 s emulated, about a minute of wall time. Three port features
   exist so a gate pays for one:

| need | option | example |
|---|---|---|
| several calls, pokes and memory dumps on one load | `--step FRAME:call\|poke\|dump:SPEC`, repeatable; `-` = after the load before the transport, `N` = frame N after the transport start | `verify_modedefaults`: two editor calls, their lane dumps and a MIDI case on one load |
| a panel sequence (keys, encoders, the level pot) | `--live-script FILE`: lines of `<emulated ms> key\|enc\|pot\|midi\|quit ...`, transport stopped, applied at emulated times | `verify_tempobus`: 65 panel lines, 7.1 s emulated, no wall-clock sleeps, the same on a loaded machine |
| several runs that each need the machine exactly as it was after the load | `--scenario "LOG ARGS..."`, repeatable, `--scenario-jobs N` (default 3): the port loads once and forks one child per scenario; each child writes its stdout to LOG and takes ARGS as its post-load options (`--sequencer`, `--frames`, `--step`, `--poke`, `--call`, `--midi`, `--mem-dump`, `--live-script`, ...) | `verify_scenesp2`: three frame runs and the editor pass from one load |

   Boot-time options (`--dsp`, `--audio-in`, `--audio-out`'s capture, the
   image, the card) belong in the shared part of a `--scenario` command,
   not inside a scenario. `--block-dump` is opened at boot: the scenario
   that names the same path keeps writing it, every other child closes its
   copy. A scenario inherits the DSP cores: a panel-only run forked from a
   `--dsp` load emulates both cores throughout, which cost more than a
   separate load for `verify_tempobus` (measured 29 Sep 2026, 115 s against
   109 s), and detaching the cores after the fork stalls the frame engine. The fork is the snapshot: after `fork()` the port
   copies the DSP cores' shared memory into private objects
   (`unshareRanges` in `tools/emu/ot_emu/main.cpp`; the vendored DSP memory
   is a `shm` object mapped several times, which forked children would
   otherwise share), so each child starts from the identical loaded state
   and none sees another's writes.
6. **Declare it** in the owning module's manifest (`Gate(...)`), or, for a
   gate every remix needs, in the Makefile's `verify-shared` or
   `verify-remix` recipe. `make reach` and `check_shards --by-gate` read
   both; `test_check_shards` refuses a recipe script the shard runner does
   not cover.

## 6. `make reach`: which gates a change reaches

**The test remixes are left out** (30 Sep 2026): no remix under
`remixes/test/` is picked by `make reach` in either tier, as a carrier, the
floor, the cover or identity. A change to a module that only test remixes
carry (CF METER, EUCLID, MINIVERB, TAPE ECHO, most USB AUDIO IN/OUT
variants) reaches the selftest and no remix check, and the listing says
so; `TESTS=1` brings the test remixes back.

**Two tiers.** The default is QUICK, for working without losing the
machine: a module change checks the remixes users flash that carry it
(`remixes/`), or the smallest test remix when only test remixes do; the
floor for tool and build changes is the one cover remix carrying the most
modules; a build change runs refhash but not `make identity`; no
`make accept`; two shards; every command at nice 10 (the performance cores,
below the desktop; measured on the M3: a CPU task 2.8 s at nice 0 and at
nice 10, 19.9 s under background QoS, `taskpolicy -b`). `FULL=1` is everything below at
full speed. What QUICK gives up: the pressure stages (the dearest layouts
priced and rendered, which catch a module that overruns beside others),
identity's image comparison, and the test remixes and other cover remixes
a change also reaches. `FULL=1` is a manual choice, never required: use it
when you want those, before a flash for instance.

`tools/verify/reach.py` reads the branch's diff against `origin/main`
(`BASE=` for another base) and prints the gates in run order. `RUN=1` runs
them, `KEEP=1` runs every one and prints a table instead of stopping at
the first failure, `JOBS=n` runs the per-remix work over n worktrees. It
refuses a tree that is not rebased onto the base, and before running it
rebuilds `out/emu/ot_emu` when a source under `tools/emu/ot_emu` is newer
than the binary.

| changed | reaches |
|---|---|
| `modules/<name>/` | `make check` and `make accept` for every remix that carries the module |
| `modules/<name>/README.md`, or a manifest edit to display fields only (`doc`, `proof`, `proof_note`, `author`, `author_url`, `category`, docstrings) | `verify_docs` |
| `remixes/<name>/remix.py` (or `remixes/test/...`) | `make check` and `make accept` for that remix; an edit to `doc`, `proof`, `proof_note` or a docstring only, or a README alone, reaches `verify_docs`; a removed remix the selftest and `verify_docs` |
| the build (`build_bus.py`, `cycle_count.py`, `dsp/`) or anything it imports | `scripts/refhash.sh check`, `make identity`, `make test-acceptance`, `make check-shared` for the cover |
| a gate of the shared half | `make check-shared` for the cover |
| a gate of the per-remix half | `make check-remix` for the cover |
| a manifest gate | its owners' remixes |
| the acceptance runner, the stress generator, `pressure.py` | `make test-acceptance`, the cover, `make accept` on the cover |
| `tools/harness/dsp_host/`, `tools/patches/`, `scripts/setup.sh`, `scripts/vendor.sh` | `make ci-dsp`, then the cover (rebuild the toolchain first) |
| `tools/emu/ot_emu/` | `make ci-emu`, `make emu-cf`, the cover's per-remix half |
| `Makefile` | by target: the check graph reaches identity, the cover and `make ci`; the runner targets `test-acceptance`; others nothing |
| `*.md`, `docs/` | `verify_docs` |
| `.github/` | `make ci` |
| a file no gate depends on | nothing, and the listing says so |

Files under `tools/` are placed by dependency: the Python imports and the
`tools/x/y.py` paths the code runs or reads form a graph; a path in a
comment, docstring or message is not an edge.

**The cover** is the fewest remixes that between them carry every module,
computed from the registry each run (9 of 35 on 29 Sep 2026: bottleservice,
cfmeter, euclid, miniverb, mods, tapeecho, usb-io-main-ab,
usb-io-main-cue-abcd, usb-io-tracks-ab). `REACHARGS=--all` makes the floor
every remix.

**Identity** (`make identity`, `tools/verify/image_identity.py`) builds
every remix from the merge-base (a kept worktree under `out/identity/base`)
and from this tree with the shipping flags and compares image and report
byte for byte. With `RUN=1`, the remixes whose bytes moved are planned into
the same accept line and the same shards as the rest.

With `STRESS_SOURCE=<a local project>` the accept lines run and replace the
check lines for the same remixes. Without it, accept is listed as blocked
and the check lines stay.

## 7. Parallel runs: shards

`tools/verify/check_shards.py` (`make check-remixes REMIXES="a b" JOBS=4`,
and what `make reach JOBS=4` uses) runs each remix's per-remix half in its
own worktree under `out/shards/<i>`: a detached checkout of HEAD with this
tree's uncommitted diff applied, `vendor/` and `.venv/` symlinked, the
stock slice copied in, submodules initialised, its own port built. Shards
are kept between runs and refreshed in place (seconds; `--fresh`
recreates, `--rm` removes). Remixes are handed out from one queue. Logs:
`out/check_shards/<remix>.log`.

**The long pole is split.** A remix whose half would set the wall time
runs as its gate jobs in the same queue as the other remixes' whole
halves, and the queue runs longest first. check_shards records every job's
duration in `out/check_shards/times.json` after each run; `--split auto`
(the default) splits a remix whose last time exceeds both 300 s and the
run's total over the shard count, and with no record the remixes carrying
OCTAKIT. `--split none` or `--split a,b` overrides. Measured on the cover
with three shards (29 Sep 2026): 681 s whole, 574 s split, for 1,621 s of
work (the floor for three shards is 540 s). The image-stage module gates
then became their own job (`verify_set.py --stage-only` stages the image and
card without running; TEMPO BUS reads its host ids from its own run): 530 s
for 1,585 s of work, at the three-shard floor of 528 s.

`make check-remix-gates REMIX=<name>` (`--by-gate`) splits one remix's
half into one job per gate over the shards and prints each gate's time:
the instrument for finding the expensive gate.

**Cores.** The development Mac has four performance cores. Four port
boots at once contend and run slower than three (measured 28 Sep 2026);
`JOBS=3` is the better default when another run shares the machine.

## 8. `make accept`: the strict runner

`make accept` (`tools/verify/acceptance.py`) runs the same gates as `make
check` and refuses missing evidence, writing a versioned JSON report
(`out/acceptance/<timestamp>/`, schema `tools/verify/acceptance.schema.json`,
validated by `make test-acceptance`).

`make check REMIX=<name>` is the development floor. It can skip checks
when local prerequisites are absent. `make accept` is the stricter
evidence-producing workflow: a nonzero command, failure marker, timeout,
missing prerequisite, or applicable `[SKIP]` prevents acceptance.
A verifier's explicit `[N/A]` means the tested behavior is absent, not
that its tools or fixture are missing.

### Run locally

Use your own stock 1.40C, initialized submodules, the documented assembler
toolchain, DSP host, emulator venv and a worktree-local `make emu-cf`
build. Nothing flashes hardware. Any remix:

```sh
make accept REMIX=<name> STRESS_SOURCE="/path/to/local/project"
# Several remixes in one run: the remix-independent half of make check once
make accept REMIXES="<name> <name> ..." STRESS_SOURCE="/path/to/local/project"
# Or supply a project you prepared for this remix:
make accept REMIX=<name> OT_PROJECT="/path/to/local/project"
# Optional fresh destination and per-command timeout:
make accept REMIX=<name> OT_PROJECT="/path/to/local/project" \
  ACCEPTARGS='--out out/acceptance/review-1 --timeout 3600'
```

`STRESS_SOURCE` names a locally saved project whose `.work`/`.strd`
files seed the fixture; `tools/harness/stress_project.py` derives the
placement from the remix's selection and writes eight FLEX tracks, three
LFOs per track, dense parameter locks and four Parts/patterns
([tools/harness/README.md](../../tools/harness/README.md), stress_project.py). FX2 slot 0
on T2 and on every server's track carries no lock or LFO: `verify_set`
sends CC 40 there and reads the value back. The generated fixture is the
pressure fixture: a remix with no DSP module of ours has nothing to
place, and one whose profile is blocked (below) has a module with no
`dear` to place it at, so either takes the source project as-is (the
report says so). Only the generator is
distributed; project bytes stay local. The sample path is
project-relative, so `verify_set` can find and stage the generated audio.

Acceptance runs these stages, serially:

1. `preflight`, per remix: prerequisites and the pressure profile (below).
2. `fixture`, per remix: generate or fingerprint the project fixture.
3. `check_shared`, ONCE for every remix past stage 2: `make check-shared`,
   the remix-independent half of `make check` (the ledger selftest, the
   knob census, the isolated module gates that build their own image);
   its one result is every report's `check_shared` gate and its log sits
   above the reports.
4. `check_remix`, per remix: `make check-remix` with the exact remix, build
   and project (its build, cycles, dirty state, init regs, DRAM boot,
   labels, its own module gates, menu, the set under the port, USB);
   refuse missing evidence even when a verifier returns zero.
5. `cycles`: save the restored shipping image's fingerprint and price the
   selected remix. Reject a static estimate above its declared DSP wall.
6. `pressure_price`: price the selection's layouts; reject any layout
   over the wall.
7. `pressure_render`: render the six dearest and four seeded random
   layouts per core using deterministic input on all eight tracks, dirty
   memory and write guards, `--jobs` layouts side by side (the cores, at
   most 8; the meter is an instruction count, so a loaded machine changes
   no result). Record the per-layout flags and instruction meters.

A failed stage stops that remix's dependent stages, which stay `not_run`
in its report; a failed or skipped `check_shared` stops every remix. Use
a fresh output directory for each run; old output is never accepted as
new evidence. Existing checks and pressure tools still use their
worktree's `out/`, so run one acceptance job per worktree.

### Coverage is explicit

The pressure stages (5, 6) and the fixture's knob values read each
module's dearest settings from its manifest (`schema.Module.dear`: the
mode the pricer calls the worst loop, work-gating knobs at maximum,
checked against the module's own knobs when the manifest loads). The
profile is **ready** when every DSP module in the selection declares
one, **blocked** with the missing modules' names otherwise (the check,
cycles and project stages still run and their evidence is in the report;
the two pressure stages are recorded `blocked` by name), and
**not applicable** for a selection with no DSP module (the image, oracle
and project gates still apply). A module is never rendered at default
settings and called covered; a module PR that wants the pressure stages
adds `dear` beside its gates.

Declared on 27 Sep 2026: SEND, DELAY SERVER, REVERB SERVER, CHARACTER,
SPECTRUM, MODULATION. Blocked until their authors declare one: MINIVERB,
TAPE ECHO, EUCLID, CF METER.

A generated project's automated playback checks A01 through the existing
`verify_set`. A02-A04 exist for further testing; this workflow does not
claim automated pattern/Part transitions, long soaks, or recording/storage
stress. Operator-supplied projects are fingerprinted but their workload
coverage is the operator's responsibility.

A result below the static DSP wall is not proof of real-time headroom.
The counter omits contention and has known error. ColdFire instruction
counts, DSP static costs and emulator meters are different measurements.
No calibrated CPU deadline or storage budget is introduced by this PR.

`passed` means the required local stages passed for these inputs.
It does not mean safe on every combination or verified on hardware.
Reports always carry `hardware_validated: false` and the known
limitations. Hardware captures, listening and timing remain separate
evidence; unresolved upstream burst failures are not waived.

### Report v2

A run of one remix writes `out/acceptance/<timestamp>/report.json`, logs
and local artifacts; a run of several writes
`out/acceptance/<timestamp>/<remix>/report.json` each, the shared half's
`check_shared.log` beside them and `summary.json` (remix to status) over
all. [acceptance.schema.json](../../tools/verify/acceptance.schema.json) defines the
versioned interchange envelope. Consumers must check `schema_version`
before reading it: v1 had one `check` gate where v2 has `check_shared`
and `check_remix`.

- `status`: `running` until finalization, then `passed`, `blocked`, or
  `failed`. A pass is published only after the measurement files validate.
- `gates`: command, exit code, elapsed time, log references, skip/N/A
  messages and one of `passed`, `failed`, `blocked`, `not_applicable`,
  `not_run`. Stages without a command carry their reason instead.
- `provenance`: repository revision, dirty state, source/diff hashes,
  submodule revisions, tool fingerprints, Python/platform, stock and
  tested image hashes. Uncommitted source is identifiable too.
- `modules`: selected keys, kinds and manifest hashes.
- `fixtures`: relative filenames and hashes, never project/audio bytes.
  Referenced samples outside the project (including their `.ot` metadata)
  are fingerprinted too; missing referenced files have null hashes.
- `parameters`: build/bank and pressure sampling settings.
- `measurements`: existing cycle/price/render JSON, preserving its units
  and per-layout findings rather than translating it to a CPU percentage.

Firmware, generated projects, audio and raw logs remain local in ignored
`out/`. Do not attach the output directory to a PR. Review reports/logs
before sharing: filenames and paths can reveal local project information.

### PR checks

`make test-acceptance` runs firmware-free negative controls: successful
commands that skip, stderr skips, swallowed failures, timeouts, a module
without `dear`, missing prerequisites, stale destinations, absent
meters, incomplete sampling and budget overruns; and the `make reach`
path classifier against a fake registry. The CI job tests this machinery
only; a green job does not replace a local acceptance report. CI also
prints `make reach`'s gate list for every pull request.

Submit the command, source revision, report status, coverage, skipped or
blocked stages, and outstanding hardware evidence with a module PR.
A new module's gates, `dear` and behavioral tests belong in that same PR.

## 9. Bit-identity: proving a change changed nothing

- **`scripts/refhash.sh save` then `check`**: 24 build configurations of
  `remixes/test/bus` (the shipping flags, the plain build, the DEV hatch,
  the probes, the overrides); every artifact and every build report
  hashed. Save on main, check on the branch. A path in the report is part
  of the report. Three cases (`probe`, `xprobe`, `tprobe`: the probes in a plain
  layout, where the real delay overruns the region) refuse to build and the
  refusal is pinned the same way (`scripts/refhash.sh`).
- **`make identity`**: every remix, base against head.
- **`make verify-bus`, `verify-ident`, `verify-roll`, `verify-delay`,
  `verify-spectrum-ident`**: a rewrite against a saved reference.

## 10. What it costs

Measured on the development Mac (8 cores, 4 of them performance cores),
with the load average noted because it moves every number:

| run | wall |
|---|---|
| `make check-shared` for a cover | 250-375 s |
| per-remix half, a USB test remix | 115-260 s |
| per-remix half, bottleservice | 468 s (29 Sep 2026, 3 shards; 788 s before the scenesp2 fork, 1,143 s on 27 Sep) |
| per-remix half, mods | 432-627 s (2,580 s before `verify_repitch` stopped loading seven times) |
| the cover's per-remix halves, `JOBS=3` | 530 s (574 s before the image job was split out, 681 s whole, 986 s before the scenesp2 fork) |
| `verify_scenesp2` on bottleservice, quiet machine | 109-111 s one load per run, 73-74 s one load and forked scenarios |
| `verify_tempobus`, quiet machine | 49 s wall-clock paced, 34 s scripted |
| `verify_kits` on bottleservice, quiet machine | 630 s: 29 scenarios, 371 s emulated, no DSP cores, 3 at a time, native binary (6 Oct 2026; the first reach run took 3,375 s for the whole per-remix half with the cores on, 6 at a time on two shards, under Rosetta) |

Typical changes (with `JOBS=4`, kept shards):

| change | remixes | wall |
|---|---|---|
| a module or remix README, or a manifest's or `remix.py`'s display fields | none | seconds (`verify_docs`) |
| one USB IN or OUT module | its few `usb-io-*` remixes (+ bottleservice if it carries it) | 5-15 min |
| USB MIDI (every USB remix) | ~24 | 15-20 min, floored by bottleservice |
| the build | the cover + identity's moved remixes | 25-40 min |

The floor of most runs is bottleservice's half, and inside it the Octakit
project loads (`verify_set`, `verify_tempobus`, `verify_modedefaults`,
`verify_scenesp2`).

## 11. What GitHub Actions checks

`.github/workflows/ci.yml` runs on every PR, on `main` and by hand, on
Ubuntu and macOS, with no Elektron bytes (`make ci` runs the same checks):

| job | target | proves |
|---|---|---|
| gates the PR reaches | `make reach` (dry run) | the diff classifies and the branch is rebased |
| acceptance runner tests | `make test-acceptance` | the runner refuses skipped, failed, incomplete and over-budget evidence; `reach` routes as documented; the shard runner covers the recipe |
| dsp56300 + our patch | `make ci-dsp` | the vendored DSP emulator at its pin takes our patch, builds, passes upstream's runner; `dsp_asm` emits the one-word displaced move |
| ColdFire port unit tests | `make ci-emu` | `ot_emu` builds on both hosts (the fork unshare has a macOS and a Linux path) and passes `emac` and `periph` |
| docs and links | `make verify-docs` | the rendered tables are current, every remix has a README, every link between tracked files resolves |

**A green CI run says nothing about a remix.** Building, booting and
playing one needs 1.40C; that is why the gates run on your machine and
their results go in the PR body.

## 12. What none of this can see

- **Hardware timing between the two DSP cores.** `dsp_host` runs them
  lock-step or under a chosen interleave; a clean result under every skew
  is not evidence a race is gone. A local red is a defect.
- **The cycle budget.** The emulator renders an engine the chip cannot
  afford; `make cycles` bounds it statically (instructions, no contention).
  Hook-only DSP sections (USB AUDIO IN's inject) are not in the price.
- **The dispatcher's facts.** `dsp_host` hands each effect an r7 and r6 it
  computes; logic keyed on them is measured under the port
  (`--dsp-pcwatch`).
- **The panel against the DSP.** `dsp_host` pokes knob values directly; a
  slot can draw a knob and publish nothing. `verify_menu` and the Tier-0
  gates cover the descriptor side, `verify_set` the delivery.
- **Stored project data.** A part saved under an older layout feeds the new
  one its old bytes. Stamp projects after a layout change.
- **The port's audio and DMA gaps.** The stock DELAY's rings and the
  recorder's DMA are not modelled; the port's main mixdown reads a gain of
  0, so playback gates skip their audio checks (`tools/emu/README.md`).
- **The bench's clock under load.** `verify_usb` and `verify_usb_in` count
  overruns and underruns against a scripted host; with shards and another
  run on the machine the host falls behind and a remix fails that passes
  alone. Rerun a USB red alone before believing it.
- **The USB stream's timing on a unit.** The port runs the frame
  interrupt and the eDMA in lock-step, so `verify_usb_align` and
  `usb_align.py` give the alignment the producer's code makes, not the
  unit's. On a unit: a click on one track, a `tools/rec` take, and
  `tools/hw/usb_offset.py` for the offset between its channel and MAIN's.
- **Whatever the metric cannot represent.** A harmonic metric cannot see
  an inharmonic block-rate step; an AC-coupled capture cannot see DC; a
  reverb smears a per-sample fault. Ask what the instrument cannot see
  before trusting a null result.
- **Ears.** GRAIN's right-channel hiss passed every gate and was found by
  listening (`tools/harness/README.md`, the listening protocol).

`docs/contributing/FAILURE_MODES.md` is the register of what has gone wrong on a
unit; `AGENTS.md` the traps that produced clean assembly of wrong machine
code.

## 13. Before a pull request

[CONTRIBUTING.md "Before you open a PR"](../../CONTRIBUTING.md#before-you-open-a-pr)
is the list. Flashing your own unit is a separate step:
[BUILDING.md section 5](../guide/BUILDING.md#5-flash-from-the-card).
