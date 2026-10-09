# fxlive: hear one effect live

A WAV on loop through a module's real code, with a slider for every knob it
draws, in a browser. Saving the module's source rebuilds it and the loop
crossfades onto the new code without stopping. It is for dialling in a
sound while writing an effect: what you hear here is the module's
instruction stream, but a sound found here is not a result until it is
rendered and `make check` passes.

```bash
make fxlive                                  # nothing selected, stopped
make fxlive MODULE=MINIVERB WAV=loop.wav     # pre-select; still waits for Play
make fxlive MODULE=SPECTRUM REMIX=bottleservice   # build it in a particular remix
```

Then open http://127.0.0.1:8573. Needs `make emu-setup` (numpy,
sounddevice) and, for ColdFire effects, `make emu-cf` (`ot_cf_host`).
`FXLIVEARGS` passes `--port N`, `--device NAME` or `--no-audio`.

fxlive needs a `dsp_host` with `-stream`. If yours predates it,
`scripts/setup.sh` rebuilds it; a branch that changes `dsp_host.cpp` points
`DSP_HOST` at its own build instead (AGENTS.md). fxlive says which when
the host is missing or too old.

## Using it

1. **Choose an effect.** The list has every module with an FX chooser row,
   grouped: DSP effects, CPU effects (ColdFire), stock effects, and the ones
   it cannot play, greyed with the reason (bus servers and clients). Choosing
   one builds it (about 2 s).
2. **Play** (the button, or the space bar). The page starts stopped; Play
   before an effect is built runs the loop dry. Stop fades out over one
   chunk and pauses the engines; Play restarts the loop from the top.
3. **Turn knobs.** A knob lands on the next 16-sample block, about 50 ms
   after you move it (the render-ahead buffer).
4. **Load a loop:** drop a WAV on the page or give a path. Any PCM or float
   WAV, resampled to 44.1 kHz. Without one, a built-in two-bar demo plays.

Wet/dry, input gain and bypass are monitor controls on the page, not part
of the module.

## Where a module is built

A module is not standalone code: the build places it into the stock
firmware image (its address in the DSP program, its dispatch entry, its
cloned menu descriptor, its buffers), and the emulators run that image. So
fxlive builds a remix that carries the module. It picks the **smallest**
one (usually the module's own `remixes/test/<name>/`) and shows it beside
the picker; when more than one remix carries the module you can choose
another there.

The choice is not expected to change the sound, and where it was tested it
did not. The build moves a module's address, not its code, and fxlive runs
one instance alone, so the neighbours a remix brings in never run beside
it. Measured 9 Oct 2026: MODULATION built in `bottleservice` (P:0x01984)
and in `character-txtr` (P:0x01a11) rendered bit-identical with every knob
up, and so did SPECTRUM in the same two. That is two modules, not a proof.
A module that hard-codes an address the build moves between remixes,
instead of one the build rewrites, could differ between carriers (the same
class of bug as AGENTS.md's payload-relative stock-table trap, which is
between payloads A and B rather than between remixes). If two carriers
sound different, that difference is a finding, not a matter of taste.
The smallest carrier is the default because it builds fastest. Every
module arrives with a remix (the selftest refuses one that no remix
carries), so a new module can be picked as soon as it builds.

fxlive builds to `out/fxlive/<remix>.bin` (`BUS_OUT`), never
`out/mainos_bus.bin`. A DRAM build also rewrites the fixed `out/platform/`,
so fxlive copies the runtime to `out/fxlive/<remix>.runtime.raw` (and
`.base`) right after its own build. A gate run in the same worktree at the
same time can still race it there; do not run both at once.

## What runs

- **DSP effects:** `dsp_host -stream` runs the module's init/proc from the
  dispatch table, as `send_probe --direct` does: one FX2 instance at
  `schema.render_slot`, `r0 = 0`, 16 frames a block, payload A. Each block
  carries its twelve knob values and samples over a pipe. The stream's
  output is bit-identical to a file render of the same input and knobs
  (MINIVERB, 3,000 blocks). About 4-26x real time through fxlive, by module.
- **CPU effects** (`CF_AUDIO` in `fxlive.py`: TAPE ECHO, and the stock
  DELAY of `stock.NO_DSP`): after the DSP stage, `ot_cf_host` runs the
  ColdFire's delay routine `0x400031a0` on T5 ("cf_host" below). It equals
  Tape Echo's native oracle bit for bit (`make fxlive-check`). About
  1.6-2.3x real time through fxlive, 7,500-8,800 CPU instructions a block.
- **Hot swap.** Every file under the module's directory and the host
  remix's `remix.py` is watched. A save rebuilds, boots a new engine, warms
  it on silence and crossfades the loop onto it. The new engine starts from
  init, so a tail restarts. Knob values survive a rebuild of the same
  module. A build that fails leaves the previous one playing and shows the
  assembler's message with the offending line.
- **Nothing to hear is measured, not guessed.** On every load the chain
  renders noise at the defaults and with every knob at minimum, middle and
  maximum; four outputs bit-identical to the input put a box on the page.
  That is a module whose sound is made somewhere fxlive does not run, or
  one that ignores its knobs. The header pill "output = input" says the
  same about the last half second at the current knobs: several stock
  effects (EQUALIZER, PHASER, FLANGER, CHORUS, COMB FILTER) are exactly dry
  at their defaults.
- **Knobs** are the module's drawn slots; a clone's unwritten fields are
  its donor's (SIDECHAIN_COMPRESSOR shows COMPRESSOR's page 1). The stock
  DELAY at its defaults sends nothing (SEND 0): raise SEND to hear repeats.
  Its SYNC (on by default) times them from the tempo, 120 BPM here.

## cf_host: the ColdFire stage

`out/emu/ot_cf_host` (`make emu-cf`; source `cf_host.cpp` here):
the ColdFire's per-frame delay routine `0x400031a0` on one track, one
16-sample block per call, from a built image and its DRAM runtime. It is
`tools/harness/tapeecho_cpu_probe.cpp`'s benchmark setup made a tool:
`docs/firmware/COLDFIRE_DELAY.md` is the map.

- **Per block:** the track's DSP voice record (`0x80000110 + 0x200·ping +
  64·track`; halfword = DSP word >> 8 at r6 offset + 12, the id at +56)
  is staged by stock's own producer copy `0x4000d0ea..0x4000d15a`, which
  fills the routine's snapshot (`0x80001a00`, `0x80001b80`). The tempo
  words are set as the frame code sets them: `0x80001814` and
  `0x8000181c` = BPM × 24, and `0x80001820 = −2³¹/tempo24`, the
  multiplier the delay's TIME uses with SYNC on. The samples (DSP word
  << 8) go to the read-back block `0x80003190 + 1024·ping + 128·track`,
  the routine runs all eight tracks over a synchronous eDMA model, and the
  block comes back processed in place.
- **`--stream`** speaks `dsp_host -stream`'s packets; `--selftest` sends
  an impulse and prints where it returns and the speed.
- **Measured** (9 Oct 2026, `make fxlive-check`, which builds its own
  `tapeecho` image): TAPE ECHO through `cf_host` equals
  `modules/tapeecho/cpu.c` bit for bit, 3,000 blocks with every control
  moving, on T1 and T5; the stock DELAY's SYNC repeat at 60 BPM lands
  twice as late as at 120 (16,537 and 33,075 samples). Alone it runs
  about 3.5x real time (about 10,000 blocks a second).
- **Not modelled:** the frame of latency the read-back adds on the unit,
  the transfer state machine, the sequencer, LFOs and everything else in
  the frame, and the CPU's cache, bus and DMA timing. Its instruction
  count is a floor, never the budget (six Tape Echoes run on the author's
  unit and a seventh freezes it).
- **The ColdFire effects list** is `CF_AUDIO` in `fxlive.py`, not a
  manifest field: declaring it in the module schema is a decision for the
  schema and module owners (`SUGGESTIONS.md`).

## Checking it

`make fxlive-check` (about 10 s; needs `make emu-setup` and `make
emu-cf`) builds its own `tapeecho` image and holds `cf_host` to Tape
Echo's native oracle and the stock DELAY's tempo law, as above. It is
fxlive's check, not a module gate: nothing in `make check` runs it. Run it
after changing `cf_host.cpp` or anything it stages.

## The API

Everything on the page is JSON, so a Claude session editing a module can
set knobs, rebuild and read the result:

| | |
|---|---|
| `GET /api/state` | status, build log and error, knobs, meters, the module index, `dsp_params` as a `dsp_host -params` list |
| `POST /api/load` | `{"module": KEY}`, optionally `"remix"` to choose the host; `{"wav": path}` |
| `POST /api/knob` | `{"slot": 0, "value": 64}` or `{"values": {"0": 64, "5": 127}}` |
| `POST /api/mix` | `{"wet": 0.5, "bypass": false, "gain_db": 0}` |
| `POST /api/transport` | `{"playing": false}`; an empty body toggles |
| `POST /api/defaults`, `/api/reload` | knobs to the module's defaults; rebuild now |
| `POST /api/upload` | a WAV as the body, its name in `X-Filename` |

## What it cannot show

Everything a `dsp_host` render cannot (`../README.md` "What the harness
cannot see"), including the stock reverbs' wet signal (`SUGGESTIONS.md`,
item 3). Also:

- knob words are clean: an LFO leaves bits 8-15 set, which no local render
  writes (AGENTS.md);
- RAM starts zeroed (`verify_dirtystate` covers uncleared state);
- the dispatcher is modelled, not run: anything keyed on r7, r6 or
  `X:0x213` is measured under the port;
- AMP VOL and LEVEL are not applied;
- for a CPU effect, the rest of the frame around the routine, the frame of
  latency the read-back adds, and the CPU budget: the instruction count is
  a floor, not a measure of whether the unit keeps up;
- bus servers and clients (they need both cores and the rotation:
  `rig_render.py`).

## Suggestions for other areas

Things building fxlive turned up that belong to other people's code (a
manifest flag for ColdFire effects, the build's assembler message, the
stock reverbs under `dsp_host`, and more) are in
[`SUGGESTIONS.md`](SUGGESTIONS.md), not changed from here.

## Later: two effects on a track (FX1 into FX2)

Not built; noted here so the design is not rediscovered. On the unit a
track runs FX1 then FX2 on the same DSP core, in one buffer, and the
harness already models it (`rig_render.py --tracks T3=L+S`; `dsp_host
-audioidx` chains a second instance on the first one's output). What
changes is the remix's role:

- **Both effects must be in one built image**, so a chain needs a remix
  that carries both. The build refusing a pair (overlapping memory, ids,
  hooks or a declared conflict) is a real answer about the unit and should
  reach the page as such.
- **The remix's menus decide what can go where.** FX1 lists fewer effects
  than FX2; a module that replaces an FX2-only stock effect is not offered
  on FX1 (the build says "replaces DARK REV, which FX1 does not list"), and
  `Claims.fx1_only` modules are FX1-only. Each slot's list should come from
  the remix.
- **A CPU effect sits after FX2 only**, keyed by the FX2 id, so at most one
  per track, followed by the `cf_host` stage.
- **Slot placement in `dsp_host` is a model.** Its r7 for each slot is
  computed, not measured, and was once wrong (three r7 bumps per track,
  AGENTS.md); a chain whose behaviour depends on its slot is checked under
  the port.

The likely shape: keep the module-first picker for one effect, and add a
chain mode that asks for a remix and fills FX1 and FX2 from its menus, or
that takes two modules and finds (or composes) a remix carrying both,
showing the build's refusal when they cannot share an image.
