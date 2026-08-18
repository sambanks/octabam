# octabam

**Custom DSP effects for the Elektron Octatrack MKII.**

The Octatrack has two effect slots per track and a fixed menu of algorithms to
put in them. This project writes new ones — original DSP56300 assembly — and
delivers them by patching the stock OS image.

What runs today:

| | |
|---|---|
| **ChonVerb** | An eight-line FDN reverb with ROOM/PLATE/BIG modes, modulated taps, shimmer, a gate, and mid/side width. Voiced by ear, confirmed on hardware. It takes over the three stock FX2 reverb slots, which is where the program space for it came from. |
| **BongDelay** | A five-mode delay — CLEAN, PITCH (a once-per-repeat harmoniser), TAPE (wow/flutter + saturation), GRAIN and REVERSE — plus a FREEZE hold, routed *into* the reverb over the bus. Its program space is the **other core's copy of the same three donor slots** — the stock FX2 delay itself has no DSP code to take. Confirmed on hardware, every knob live and audible. |
| **The send bus** | All eight tracks feed one shared reverb and one shared delay, across both DSP cores. Both effects are **returns**: a track running one outputs wet only, fed by the other tracks' SEND knobs. This is the part the hardware was not designed to do. |

The reverse-engineering in `docs/` is infrastructure, not the product. It
exists because you cannot write an effect for a machine whose memory map,
cycle budget and parameter plumbing you do not know.

---

## Why the send bus is the interesting part

Stock, an effect is an *insert*: it lives on one track and hears only that
track. A reverb used that way is one reverb per track, each with its own
memory and its own cycles, and you cannot feed several tracks into a single
space.

octabam turns the FX2 slot into a **bus server**. One track hosts the reverb;
the others select SEND and contribute to it. Because the two payloads run on
separate cores, and each carries a different server, the delay's output can
cross into the reverb — a route the stock firmware has no path for at all.

The costs are all measured, not estimated:

| resource | per core | state (Aug 2026 build) |
|---|---|---|
| Cycles | 4,535/sample | measured ceiling; worst mode fits its core with margin |
| Program space | 8,192 words | donor region 2,724 words/payload: A 55 free, B 1 free |
| Delay memory | 65,536 words | 1.49 s per server |

`docs/CHIP.md` carries every one of these numbers with a confidence marker —
measured or inferred, and what would falsify it.

### The machine, on one page

The Octatrack's audio DSP is one **DSP56721**: two DSP5636x cores, each
serving four tracks. Each core boots its own payload, and each payload gives
its effects the same 8,192 words of program memory (an OMR setting — the
chip has more, stock runs the map that grants the least):

```
              DSP56721 — two cores @ 200 MHz, 44.1 kHz audio
              4,535 cycles per sample per core (measured)

   CORE 0 / payload A · tracks 5–8      CORE 1 / payload B · tracks 1–4
   ─────────────────────────────────    ─────────────────────────────────
P  8,192 words                          8,192 words
   ├─ stock: dispatch, FX1, mixing…     ├─ stock: dispatch, FX1, mixing…
   └─ donor region, 2,724 words         └─ donor region, 2,724 words
      (was PLATE+SPRING+DARK)              (this core's copy of the same
      now SEND + CHONVERB                   three slots)
      used 2,669 · free 55                 now SEND + BONGDELAY
                                           used 2,723 · free 1

Y  private 0x4000–0xBFFF (32 K)         private 0x4000–0xBFFF (32 K)
   └─ the tank: 8 lines × 4,096         └─ pooled, unclaimed by the delay

   shared half 0x30000–0x37FFF (32 K)   shared half 0x38000–0x3FFFF (32 K)
   ├─ 4 input + 2 in-loop allpasses     └─ LineL + LineR, 16,384 each
   ├─ shimmer line, retired pre-delay      (ping-pong, ~371 ms per line)
   ├─ tank state tables
   └─ BUS SCRATCH at 0x36000 — the
      one region both cores touch
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
                      ▼                              │ →VERB, hardwired —
              ┌────────────────┐                     ▼ this write CROSSES CORES
              │ REVERB bus acc │◄────────────────────┘
              └────────────────┘──► CHONVERB ─► wet out on its track (5–8)
```

Every writer accumulates per block; each bus keeps **four rotating
accumulator buffers** (the cross-core race fix — see `docs/XBUS.md`)
plus client counts for the ÷N auto-gain, so eight senders drive a server
exactly as hard as one. Cycles follow the same split: a core pays its one
server (role-locked, charged once per bank however many tracks select it)
plus its tracks' send taps; the delay's worst mode (GRAIN, ~1,750 cycles) is
the deepest path, and FX1 inserts pay **×4 per core** — which is the real
ceiling on FX1 ambition, not program space.

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

`make help` lists everything. The setup script assumes **macOS + Homebrew**;
on Linux the substitutions are the obvious ones (the DSP toolchain itself is
plain CMake — see `scripts/setup.sh`).

### Hearing it without a hardware flash

This matters more than it sounds. A flash cycle is slow and manual, so the
project is built around **not needing one** to make a judgement:

```bash
make render                      # render the whole bus locally
make reverb IN=loop.wav          # push audio through ChonVerb
make reverb IN=loop.wav ARGS='--sweep SIZE=0,64,127 --wet'
```

These run the *real assembled instruction stream* on a DSP56300 emulator, at
roughly 6× real time. What you hear is what the chip will do, which is why
voicing decisions in `docs/VOICING.md` are recorded as listening results
rather than as guesses about coefficients.

`scripts/make_test_audio.py` generates synthetic source material to audition
with — or feed it your own.

### Checking it without a hardware flash

```bash
make check     # build + cycle budget + menu and burn-probe verification
```

---

## Layout

```
PLAN.md          Read this first. End state, resource ledger, work order.
dsp/             The effects. DSP56300 assembly — this is the product.
tools/           Build, render, measure, verify.
scripts/         Toolchain setup and firmware recon.
docs/            Architecture and reference (see below).
docs/history/    Closed records. Kept for provenance, not for guidance.
```

The documents that stay current:

| | |
|---|---|
| `PLAN.md` | The cold-start document — what is being built and in what order |
| `docs/XBUS.md` | How the cross-core bus works, and why |
| `docs/CHIP.md` | Cycles and memory, every number with a confidence marker |
| `docs/REVERB.md` | ChonVerb: structure, parameters, memory layout |
| `docs/VOICING.md` | What was decided by listening, and why |
| `docs/FLASHING.md` | Getting an image onto hardware, and back off it |
| `docs/CAPTURE.md` | Hardware capture protocol — predictions committed before measuring |
| `docs/TESTPASS.md` | The functional test matrix and what the emulator can prove |
| `docs/DSP.md` | The DSP56300 module load map — which bytes land where |
| `docs/PARAM_PAGES.md` | Parameter-page descriptors: how a knob reaches the DSP |
| `docs/ARCHITECTURE.md` | The firmware as a whole |
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

`vendor/` pulls in [dsp56300](https://github.com/dsp56300/dsp56300) (the
emulator and disassembler this project assembles and auditions against) and
[elektron-firmware-tool](https://github.com/mischa85/elektron-firmware-tool).

---

## Contributing

Issues, listening reports and findings are welcome. If you open a PR: `make
check` is the floor, and read the traps in `CLAUDE.md` first — several of
them are the kind that assemble clean and do the wrong thing. **Never attach
a built image, an OS file, or any Elektron-derived binary to an issue or
PR** — describe it, hash it, or reference the commit that built it instead.

---

## License

[MIT](LICENSE), covering this repository's own code and documentation. It does
not extend to Elektron's firmware, which is not distributed here.
