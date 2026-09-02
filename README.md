# octabam

**Custom DSP effects and firmware patches for the Elektron Octatrack MKII.**

The Octatrack has two effect slots per track and a fixed menu of algorithms to
put in them. This project writes new ones — original DSP56300 assembly — and
delivers them by patching the stock OS image. It also patches the ColdFire
side, where the sequencer, the menus and the parts live.

---

## Modules and remixes

**A module is one contribution. A remix is a named selection of them, composed
into one firmware image.** That is the whole model, and everything else here
follows from it.

A remix is a file. This one is the granular-texture card:

```python
# remixes/nimbus.py
REMIX = Remix(
    name="nimbus",
    doc="Nimbus granular texture + send bus. One instance per core.",
    modules=("NIMBUS", "SEND"),
    fallback="SEND",
)
```

```bash
make bus REMIX=nimbus       # -> a flashable image containing exactly that
```

Modules left out are **not built, not placed and not listed**, and their FX2
ids fall back to the module you nominate — so a saved project that still
selects a missing effect makes that track a send, rather than dispatching into
whatever code now occupies the address. There is no central list to edit:
`modules/*/manifest.py` *is* the registry, so **adding a module is adding a
directory**.

The build refuses to start if two selected modules collide — same FX2 id,
ColdFire cave, hook site, core-private word or buffer region — and names both.
Program space is finite and shared (2,724 words per payload), so a remix is a
real budget decision, not a label.

### What ships

| remix | contains | why you would build it |
|---|---|---|
| **`chongbong`** | ChonVerb + BongDelay + send bus + tempo sync | the shipping image, and the default |
| **`mutables`** | five inserts + send | a card of stacking effects, no servers |
| **`nimbus`** | Nimbus + send | the granular texture, which needs a buffer region to itself |
| **`warped`** | WarpFold + send | the smallest real selection |
| **`verbonly`** | ChonVerb + send | the reverb alone; proves selection works |

```bash
make remix                  # the workbench: 8 tracks, hear effects, compose
make modules                # the index of what exists
make bus REMIX=<name>       # build a selection
```

`make remix` is the workbench, organized like the unit: eight tracks, an
effect on each, its real knobs to dial and render and hear (every effect
renders locally). Its composer view shows what would collide, what the FX2
chooser ends up looking like on the panel — including which **stock**
effects the image keeps, hides or consumes (only the three reverbs are
consumed; the rest can be kept for free) — and what the selection costs
against the donor region — then builds or saves it.
**[docs/WORKBENCH.md](docs/WORKBENCH.md)** is the manual.

See **[docs/MODULES.md](docs/MODULES.md)** to write a module.

---

## The modules

**Ten ship today.** Two are bus *servers*, six are per-track *inserts*, one is
the bus client they all lean on, and one patches the ColdFire rather than the
audio at all.

### Effects that serve a bus

| | |
|---|---|
| **ChonVerb** | An eight-line FDN reverb with ROOM/PLATE/BIG modes, modulated taps, shimmer, a gate, and mid/side width. Voiced by ear. |
| **BongDelay** | A multi-mode delay — CLEAN, PITCH (a once-per-repeat harmoniser), GRAIN (a granular cloud) and REVERSE — with tape-style wow/flutter, drive, and a FREEZE hold available in **every** mode. Its wet can be sent on into the reverb, across cores. |
| **Send** | The bus client: any track can select it and feed `-DEL` / `-VRB`. It is also the fallback an unimplemented id degrades to. |

### Effects that run on one track

Six inserts, Mutable-Instruments-flavoured. They need no bus, sit in both
payloads, run on any track, and **stack** — `make bus REMIX=mutables` puts
five of them on one card.

| | |
|---|---|
| **WarpFold** | A wavefolder into a ring modulator. FOLD / RING / BOTH. |
| **Ripple** | A driven state-variable filter, LP / BP / HP, resonance to Q≈30. The drive clip is the character. |
| **Rungs** | Eight tuned resonators struck by the audio itself. STRING / BELL / GLASS, plus a stretch control. |
| **Streamz** | A vactrol lowpass gate: the envelope opens a filter and an amplifier *together*, so quiet is dark as well as quiet. LPG / VCF / VCA. |
| **BodeShift** | A Bode frequency shifter — every partial moves by the same number of *hertz*, so it is not a pitch shifter. UP / DOWN / WIDE, plus a feedback spiral. |
| **Nimbus** | Four grains reading back out of a continuously-recorded 743 ms buffer, with a freeze. |

### Firmware behaviour, not audio

| | |
|---|---|
| **Tempo sync** | Two ColdFire code caves: one publishes the project tempo, crossfader and held MIDI note where the DSP can read them; the other draws a TIME knob as a tempo division. The worked example of patching what the firmware *does*. |

⚠️ **ChonVerb, BongDelay, Send and Tempo sync are confirmed on hardware. The
six inserts are not** — they are verified by local render and measurement and
have never been flashed. Whoever flashes them is the first to run them on a
real machine.

The reverse-engineering in `docs/` is infrastructure, not the product. It
exists because you cannot write an effect for a machine whose memory map,
cycle budget and parameter plumbing you do not know.

---

## Two kinds of effect

This is the distinction to understand before writing anything, because it
decides how hard your module is to build.

An **insert** processes its own track's frames in place. It has no bus role,
claims no shared memory, is placed in *both* payloads, and therefore runs on
any of the eight tracks — several at once, all different, or four copies of
the same one. Nothing negotiates with anything, so inserts **stack**: one
image can carry a whole set of them. This is far the easier thing to
contribute, and the six above are all of this kind.

A **server** owns a bus accumulator and is *bank-bound*. ChonVerb exists only
on core 0 and BongDelay only on core 1, one per core by design rule. That
asymmetry is what bought each of them a whole donor region's worth of program
space, and it is why they can be big.

## What a server buys: the send bus

Stock, every effect is an insert — it lives on one track and hears only that
track. A reverb used that way is one reverb per track, each with its own
memory and cycles, and you cannot feed several tracks into a single space.

octabam turns the FX2 slot into a **bus server**. One track hosts the reverb;
the others select SEND and contribute to it. Because the two payloads run on
separate cores and each carries a different server, the delay's output can
cross into the reverb — a route the stock firmware has no path for at all.

Both servers are **returns**: a track hosting one outputs its own dry at
unity plus the wet, fed by the other tracks' sends.

---

## The machine, and what there is to spend

Every module in a remix competes for the same three budgets, and they are
measured rather than estimated:

| resource | per core | state |
|---|---|---|
| Cycles | 4,535/sample | derived (200 MIPS ÷ 44.1 kHz). `make cycles` prints the worst load the selected remix can be asked for; the real ceiling is a cliff and only a hardware burn sweep measures it |
| Program space | 8,192 words | donor region **2,724 words per payload**, shared by every module in the remix. `make bus` prints the live ledger |
| Y memory | 65,536 words | 1.49 s, pooled from the private FX2 slots + the shared window. A module that wants a big buffer claims it, and only one per core may |

`docs/CHIP.md` carries every one of these numbers with a confidence marker —
measured or inferred, and what would falsify it.

### The memory map, on one page

The Octatrack's audio DSP is one **DSP56721**: two DSP5636x cores, each
serving four tracks. Each core boots its own payload, and each payload gives
its effects the same 8,192 words of program memory (an OMR setting — the
chip has more, stock runs the map that grants the least):

```
              DSP56721 — two cores @ 200 MHz, 44.1 kHz audio
              4,535 cycles per sample per core (200 MIPS ÷ 44.1 kHz)

   CORE 0 / payload A · tracks 5–8      CORE 1 / payload B · tracks 1–4
   ─────────────────────────────────    ─────────────────────────────────
P  8,192 words                          8,192 words
   ├─ stock: dispatch, FX1, mixing…     ├─ stock: dispatch, FX1, mixing…
   └─ donor region, 2,724 words         └─ donor region, 2,724 words
      (was PLATE+SPRING+DARK)              (this core's copy of the same
      the remix's modules go here           three slots)
      -- `make bus` prints who got          same, for this core's half of
      what and how much is left             the selection

Y  private 0x4000–0xBFFF (32 K)         private 0x4000–0xBFFF (32 K)
   └─ two FX2 instance slots -- where a └─ same. At most ONE module per
      module that needs a big buffer       core may claim this, and the
      puts it. Only one per core.         build refuses a remix where two do

   shared half 0x30000–0x37FFF (32 K)   shared half 0x38000–0x3FFFF (32 K)
   └─ this payload's half of the 64 K   └─ the other half, likewise
      window, plus the BUS SCRATCH at
      0x36000 -- the one region BOTH
      cores touch
```

Below, what the *shipping* remix does with that space — one arrangement of
many, not a property of the machine:

```
   payload A (ChonVerb)                 payload B (BongDelay)
   ├─ the tank: 8 lines x 4,096         └─ LineL + LineR, 16,384 each
   ├─ 4 input + 2 in-loop allpasses        (ping-pong, ~371 ms per line)
   ├─ shimmer pitch-shift line (2 K)
   ├─ dead pre-delay buffer (4 K --
   │  PRE became GATE; still mapped)
   └─ tank state tables
```

The shared window `0x30000–0x3FFFF` is 64 K that both cores address (P, X
and Y all alias there); stock's own allocator already hands its low half to
core 0 and its high half to core 1, so the split above agrees with the
machine rather than fighting it.

The bus itself lives in that scratch block — and it is the whole trick:

```
 any track
   SEND ──→DELAY ─────────►┌────────────────┐
   SEND ──→REVERB ────┐    │ DELAY bus acc  │──► BONGDELAY ─► wet out on its
                      │    └────────────────┘        │         track (1–4)
                      ▼                              │ -VRB send — this
              ┌────────────────┐                     ▼ write CROSSES CORES
              │ REVERB bus acc │◄────────────────────┘
              └────────────────┘──► CHONVERB ─► wet out on its track (5–8)
```

Every writer accumulates per block; each bus keeps **four rotating
accumulator buffers** (the cross-core race fix — see `docs/XBUS.md`)
plus client counts for the ÷N auto-gain, so eight senders drive a server
exactly as hard as one. Cycles follow the same split: a core pays its one
server (role-locked, charged once per bank however many tracks select it)
plus its tracks' send taps; the delay's worst mode (GRAIN, 2,338 cycles by
`make cycles`) is the deepest path in the shipping image. Note that FX2
effects are charged once per track that selects them, while **FX1 inserts pay
×4 per core** — which is the real ceiling on FX1 ambition, and the reason
nothing here is an FX1 effect yet.

---

## ⚠️ Before you flash anything

**Writing a non-official OS to an Octatrack can leave it unusable, and it puts
your warranty in question.** Nothing here is endorsed by, supported by, or
affiliated with Elektron. If you flash a modified image you do so entirely at
your own risk.

Reading and disassembling firmware is harmless. Writing it to hardware is not.
`docs/FLASHING.md` has the recovery path — read it *before* you need it.

**No Elektron binary is redistributed here — and none may be.** You download
your own copy of the official OS with `make os`; every build is derived from
that copy, reproducibly, and the tooling regenerates Elektron's own image
byte-for-byte before it will produce a modified one. The same rule binds you
onward: **a built `.bin` or `.syx` contains Elektron's copyrighted OS — do not
share built images.** Share the repo; everyone builds their own.

*Octatrack* and *Elektron* are trademarks of Elektron Music Machines MAV AB,
used here only to identify the hardware this project targets.

---

## Quick start

```bash
make setup     # toolchain: DSP56300 assembler, emulator, firmware tool
make os        # download the official Elektron OS (your own copy)
make recon     # unpack it -> out/raw/section_3_MAIN_OS.bin
make bus       # build the effects into it
make image     # repack as a card-flashable .bin
```

`make remix` opens the workbench (`make emu-setup` provisions it): a rig of
eight tracks to trial effects on by ear, a composer showing collisions, the
panel your choice produces and its word cost against the donor region, and
the built image booted in the local ColdFire emulator — the manual is
**[docs/WORKBENCH.md](docs/WORKBENCH.md)**.

`make help` lists everything. The setup script assumes **macOS + Homebrew**;
on Linux the substitutions are the obvious ones (the DSP toolchain itself is
plain CMake — see `scripts/setup.sh`).

### Hearing it without a hardware flash

This matters more than it sounds. A flash cycle is slow and manual, so the
project is built around **not needing one** to make a judgement:

```bash
make render                      # the send bus: SEND -> ChonVerb
make render-delay                # the delay hatch, all servers real
make reverb IN=loop.wav          # push audio through ChonVerb
make reverb IN=loop.wav ARGS='--sweep SIZE=0,64,127 --wet'
```

Those wrappers drive the two servers. **An insert has no bus accumulator to
measure**, so it is rendered on its own track instead — `send_probe.py
--direct` with the module's layout letter, or `dsp_host` directly. The layout
alphabet comes from the manifests, so your module joins it by declaring a
`harness.layout_char`; ask for a layout the tool cannot analyse and it says
so, with the alternative. `docs/HARNESS.md` has the recipes.

All of it runs the *real assembled instruction stream* on a DSP56300
emulator, at roughly 6× real time. What you hear is what the chip will do, which is why
voicing decisions in `docs/VOICING.md` are recorded as listening results
rather than as guesses about coefficients.

`scripts/make_test_audio.py` generates synthetic source material to audition
with — or feed it your own.

### Checking it without a hardware flash

```bash
make check     # build + cycle budget + ledger selftest + menu verification
```

### Building a different selection

See **[Modules and remixes](#modules-and-remixes)** above — `make remix` to
compose one, `make bus REMIX=<name>` to build it.

---

## Repository layout

```
PLAN.md          Read this first. End state, resource ledger, work order.
modules/         The contributions. One directory each — this is the product.
remixes/         Named selections of modules. chongbong is the shipping one.
dsp/             Shared DSP infrastructure: the null stub and the probes.
tools/           Build, render, measure, verify.
tools/remix/     The module schema, registry, ledger and build engine.
scripts/         Toolchain setup and firmware recon.
docs/            Architecture and reference (see below).
docs/history/    Closed records. Kept for provenance, not for guidance.
```

The documents that stay current:

| | |
|---|---|
| `PLAN.md` | The cold-start document — what is being built and in what order |
| `docs/MODULES.md` | **Writing a module** — the schema, the traps, the gates |
| `docs/HARNESS.md` | Rendering and measuring a module without hardware |
| `docs/XBUS.md` | How the cross-core bus works, and why |
| `docs/CHIP.md` | Cycles and memory, every number with a confidence marker |
| `docs/REVERB.md` | ChonVerb: structure, parameters, memory layout |
| `modules/*/README.md` | Each module's own notes: what it is, what was measured, what is open |
| `docs/VOICING.md` | What was decided by listening, and why |
| `docs/FLASHING.md` | Getting an image onto hardware, and back off it |
| `docs/CAPTURE.md` | Hardware capture protocol — predictions committed before measuring |
| `docs/TESTPASS.md` | The functional test matrix and what the emulator can prove |
| `docs/DSP.md` | The DSP56300 module load map — which bytes land where |
| `docs/PARAM_PAGES.md` | Parameter-page descriptors: how a knob reaches the DSP |
| `docs/ARCHITECTURE.md` | The firmware as a whole |
| `docs/EXTERNAL.md` | Findings from outside this project, and what they retract |
| `docs/TABLES.md` | The DSP data tables the ColdFire uploads at boot — free lookup curves |
| `docs/BUS.md` | The FX2 menu and descriptor work behind the bus |

---

## Credit

This began as a fork of **[mxldyn/octamax](https://github.com/mxldyn/octamax)**
by Maxolydian, whose reverse engineering of the Octatrack's OS format, memory
map and parameter tables is what made any of the DSP work reachable. The
ColdFire archaeology in `docs/ARCHITECTURE.md` and `docs/PARAM_PAGES.md`
started there.

That project studies the firmware. This one uses that understanding to write
effects, so the two diverged rather than merged — by agreement, findings flow
back as notes rather than pull requests. The upstream history is preserved in
this repository's commit log.

**Bryan T** answered the project's oldest open question — where the stock
Echo Freeze Delay actually lives — along with the timestretch architecture,
a shape-level atlas of the boot-uploaded DSP data tables, and the track
recorders' control path from parameter page to engine. That work also
retracted claims of ours, several of which we then confirmed against our own
disassembly. It is recorded, with its own confidence markers and ours, in
`docs/EXTERNAL.md`.

`vendor/` pulls in [dsp56300](https://github.com/dsp56300/dsp56300) (the
emulator and disassembler this project assembles and auditions against) and
[elektron-firmware-tool](https://github.com/mischa85/elektron-firmware-tool).

---

## Contributing

Issues, listening reports and findings are welcome, and so are modules.

**To add one**, copy `modules/_template/` and read
**[docs/MODULES.md](docs/MODULES.md)**. Your module declares what it is and
what it claims; the build refuses to start if two selected modules claim the
same FX2 id, cave, hook site, core-private word, or the per-core FX2 buffer
region, and names both.

**An insert is the easiest first module** — no bus role, no shared window, no
payload asymmetry to reason about. The six above were each built against
`docs/MODULES.md` alone.

If you open a PR: `make check` is the floor, and read the traps in
`CLAUDE.md` first — several are the kind that assemble clean and do the wrong
thing. If you changed the *build* rather than adding a module, prove it
changed nothing with `scripts/refhash.sh` (26 configurations, artifacts and
build reports, bit-identical).

**Never attach a built image, an OS file, or any Elektron-derived binary to
an issue or PR** — describe it, hash it, or reference the commit that built
it instead.

---

## License

[MIT](LICENSE), covering this repository's own code and documentation. It does
not extend to Elektron's firmware, which is not distributed here.
