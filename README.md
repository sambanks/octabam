# octabam

**Custom DSP effects for the Elektron Octatrack MKII.**

The Octatrack has two effect slots per track and a fixed menu of algorithms to
put in them. This project writes new ones — original DSP56300 assembly — and
delivers them by patching the stock OS image.

What runs today:

| | |
|---|---|
| **ChonVerb** | An eight-line FDN reverb with ROOM/PLATE/HALL/BIG modes, modulated taps, mid/side width and pre-delay. Voiced by ear. It takes over the three stock reverb slots, which is where the program space for it came from. |
| **BongDelay** | A delay you can route *into* the reverb. **Currently an untested first draft** — treat it as unwritten. |
| **The send bus** | All eight tracks feed one shared reverb and one shared delay, across both DSP cores. This is the part the hardware was not designed to do. |

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

| resource | per core | state |
|---|---|---|
| Cycles | 4,535/sample | 1,392 spare, measured on hardware under full load |
| Program space | 8,192 words | 494 free on payload A, 1,998 on B |
| Delay memory | 65,536 words | 1.49 s per server |

`docs/CHIP.md` carries every one of these numbers with a confidence marker,
and keeps retracted values next to current ones — knowing what a figure *used
to be* is how you spot a document that has not caught up.

---

## ⚠️ Before you flash anything

**Writing a non-official OS to an Octatrack can leave it unusable, and it puts
your warranty in question.** Nothing here is endorsed by, supported by, or
affiliated with Elektron. If you flash a modified image you do so entirely at
your own risk.

Reading and disassembling firmware is harmless. Writing it to hardware is not.
`docs/FLASHING.md` has the recovery path — read it *before* you need it.

**No Elektron binary is redistributed here.** You download your own copy of the
official OS with `make os`; every build is derived from that copy,
reproducibly, and the tooling regenerates Elektron's own image byte-for-byte
before it will produce a modified one.

---

## Quick start

```bash
make setup     # toolchain: DSP56300 assembler, emulator, firmware tool
make os        # download the official Elektron OS (your own copy)
make recon     # unpack it -> out/raw/section_3_MAIN_OS.bin
make bus       # build the effects into it
make image     # repack as a card-flashable .bin
```

`make help` lists everything.

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

## License

[MIT](LICENSE), covering this repository's own code and documentation. It does
not extend to Elektron's firmware, which is not distributed here.
