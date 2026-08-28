> **This is the architecture record** — how the cross-core bus works, and why
> it is shaped the way it is. The plan and work order live in `PLAN.md`. The
> full development log this file was distilled from — every dated finding,
> retraction and price — is `docs/history/XBUS_LOG.md`, with the complete
> trail in git history.

# The cross-core bus: one reverb, one delay, all eight tracks

Stock, an FX2 effect is an insert: it lives on one track and hears only that
track. This project turns the FX2 slot into a **bus**: one track hosts a
server (the reverb or the delay), every other track can select SEND and
contribute to it, and the two servers — one per DSP core — can feed each
other across the core boundary. This document is the mechanism.

## The design

```
CORE 0   track 5    ChonVerb    Y:0x4000-0xBFFF (private) + Y:0x30000-0x37FFF (shared lo) = 65,536 words = 1.49 s
         6, 7, 8    Send
CORE 1   track 1    BongDelay   Y:0x4000-0xBFFF (private) + Y:0x38000-0x3FFFF (shared hi) = 65,536 words = 1.49 s
         2, 3, 4    Send

         every track sends to both buses, through accumulators in the shared window
         delay wet -> reverb   (series, over the bus — the route stock has no path for)
```

✅ **The track↔core mapping is measured, and inverted from the natural
assumption**: payload A / core 0 serves **tracks 5–8**, payload B / core 1
serves **tracks 1–4** (marker-flash test, 10 Aug 2026). Kept deliberately —
the delay on the low tracks puts it upstream of the reverb, which is the
topology wanted anyway. Host the reverb on track 5, the delay on 1–4.

**Hosting is bank-bound; serving is not.** Under specialization (`SPEC=1`)
each server exists in only one payload, so it can only be *hosted* on its
own core's bank — but any of the eight tracks can send into it. Picking a
server on the wrong bank runs a SEND instead: the absent server's dispatch
id is deliberately aliased to the SEND client on that payload, so the wrong
menu pick degrades to a send rather than silence or a wild jump.

**Each server's memory is 65,536 words (1.49 s at 44.1 kHz)**: its core's
two private FX2 slots plus half of the 64K shared window at
`0x30000–0x3FFFF`, where P, X and Y all alias ✅. The halves are not an
invention of this project — the stock allocator's slot table (`X:0x255`,
dumped from both payloads of the *raw* image ✅) already hands the low half
to core 0 and the high half to core 1, so the split agrees with the machine
rather than fighting it. The two cores' shared-window slots cannot collide
even with all four taken.

## What a send is

A track on SEND runs a small client with two independent level knobs —
`x:(r6+0)` drives **→DELAY**, `x:(r6+1)` drives **→REVERB**. Driving the
wrong one renders silence, which reads as a broken algorithm; it is the
first thing to check. Each block, the client adds its (level-scaled) audio
into the current write accumulator of each bus it feeds and registers
itself in that bus's client count. Servers consume the *summed previous*
work — the bus is deliberately block-late.

BongDelay's own wet can be sent onward into the reverb (`-VRB`, default 0):
a **core-1 writer into core-0's reverb accumulator**, the series route. The
reverse route (reverb → delay) is forbidden by design — it closes a
feedback loop across both cores.

**Total bus latency is exactly 2 blocks** — 32 samples on hardware, 30 in
the emulator's 15-frame blocks — measured to the sample
(`docs/TESTPASS.md`). One block from write-then-read, one from the
four-buffer read-two-back below.

## The accumulators: four rotating buffers

Each bus keeps **four accumulator buffers**, rotated once per block, with
the read pointed **two buffers back** from the write. This is the cross-core
race fix, and the shape is forced:

- **Two buffers cannot be made safe at any clear time.** At every instant
  one is the write target and one the read target, so the only clearable
  buffer is the one transitioning read→write — and that transition *is* the
  flip a skewed reader on the other core may still be inside. Structural,
  not tunable.
- **Four, not three, because the count is a power of two.** The rotation is
  two instructions (`+16 & $30`) and the read offset two more, no compare,
  no clamp — and the mask sanitises boot garbage for free. Four is cheaper
  than the two-buffer code it replaced.
- **Read-two-back is the part that does the work**: it puts an idle block on
  each side of the reader, so either core may lead or lag the other by up to
  a full block. Cost: the second block of the latency above.
- **It covers both directions at once** — core 1 reading core 0's clears
  (the delay bus) and core 1 writing into core 0's reverb bus (`-VRB`) ride
  the same rotation.

All bus state — the rotation word, the four buffer sets for both buses, the
client counts, the reciprocal tables and both role locks — lives in the
**bus scratch block at `Y:0x36000`**, carved out of core 0's half of the
shared window (`docs/CHIP.md` for the exact extent). Role locks make the
first instance of a server the *only* one: a second instance of the same
server returns as a passthrough, so one server per bank is enforced, and a
server's cycle cost is charged once per bank however many tracks select it.

## Housekeeping and the rotation

Someone has to flip the rotation and clear buffers, exactly once per block,
on one core. All housekeeping is **gated to payload A** (core 0); every bus
participant carries the housekeeping block, and an election makes the
first-dispatched core-0 instance — position 0, i.e. **track 5** — run it,
so the mechanism survives whatever occupies track 5. Three rules the
defects below burned in:

- **Clients never read the shared rotation word directly.** Each core tracks
  the rotation privately, advancing once per block, so all clients on a core
  agree — a core-1 client that read the shared word at its own dispatch time
  would straddle core 0's flip and land contributions in a dead buffer on
  random blocks.
- **The tracked rotation is seeded at `init`, and is NOT self-healing.**
  Unseeded, a client booting one step out of phase sticks there — and writes
  exactly the buffer being cleared, metallic on every core-1 sender after
  every power cycle.
- **The housekeeper clears the buffer that will be written NEXT block**, not
  the one just vacated — the four-buffer rotation leaves an idle slot so the
  clear can never race a skewed writer.

## Auto-gain: eight senders drive a server exactly as hard as one

The naive bus rails: senders sum, and five tracks at moderate level clip
the shared word. Instead every writer contributes with **3 bits of headroom**
(`asr #3`, so eight full-scale clients sum to exactly 1.0) and registers in
a per-block client count; the server multiplies the summed block by **1/N**
from a reciprocal table and shifts back up. Measured flat: 1 through 7
senders render identically (THD −44.6 dB at every count where the
un-gained bus had railed to −0.6). Two hard-won rules:

- **Registration must be gated on the send knob.** A client that registers
  and contributes nothing dilutes every real sender by N/(N+1) — **−6 dB
  with a single sender** — and the symptom shows up in a *different*
  effect's level. Both effects had a variant of this; both are gated now.
- **Every writer registers, including the cross-core one.** `-VRB` applies
  the same `asr #3` and increments the reverb count like any client; a
  "fixed" full-scale writer whose effective gain varies as 8/N with the
  sender count is not fixed at all.

Perceptual consequence, by design: the law is 1/N across *registered*
senders, so a quiet sender turns a loud sender's reverb down (measured to
the dB against the 1/√N alternative — `docs/CAPTURE.md`, capture E).

## The three cross-core defects — why all of the above

Each was found on hardware, each only became visible once the previous one
was fixed, and all three are hardware-confirmed closed (sweep of core-1
tracks × delay modes, all clean):

| # | defect | fix |
|---|---|---|
| 1 | **clear-vs-read** — core 0 zeroing a buffer core 1 was still reading: zeros spliced in at block boundaries, +18 to +31 dB of broadband hash on the bus path only | four buffers, read two back |
| 2 | **the rotation read** — each client read the shared rotation at its own dispatch time; the core-1 client straddling core 0's flip disagreed with the rest, block-rate amplitude jitter | per-core rotation tracking |
| 3 | **clear-vs-write** — core 0's clear racing core 1's writers | clear the next-block buffer |

Plus one defect in the fixes themselves: the unseeded rotation tracking
(above). The full diagnostic trail — including the measurement that cracked
it, swapping what ran on track 5 — is in `docs/history/XBUS_LOG.md`.

## Standing caveats — what any future claim must respect

- 🟡 **The fix assumes the cores are rate-locked** (same sample clock,
  constant phase offset). Unverified, and nothing local can verify it. The
  symptom of drift would be a slow return of the artifact over minutes.
- ⚠️ **A single clean configuration proves nothing.** These artifacts
  RELOCATE: exactly one (core-1 track, delay mode) pairing is bad at a
  time, and it moves when the mode or core 0's load changes. Spot-checks
  have passed builds that a sweep then failed — any "fixed" claim needs a
  track × mode sweep.
- ⚠️ **No local test is evidence about a cross-core race.** `dsp_host` is
  single-core and always trivially in lockstep. The bit-identity gate
  proves a change preserved behaviour; only the unit can say a timing
  defect is gone, and the decisive configuration is the one that exposed
  it: BongDelay on track 1, fed over the bus.
- **The free diagnostic lever, costing no flash: change what is on track
  5.** T5 is core 0's position 0 — the housekeeper — so swapping ChonVerb
  for a Send there moves the flip in time and nothing else. It has isolated
  core-1 defects repeatedly.
- Characterised, unexplained residual: at 6–7 senders, 2 samples in 16,305
  differ by ≤33 LSB (−105 dB) versus the lag-0 control. It does not scale
  with amplitude (the falsifier for a clip boundary), so it is filed as
  rounding under the added latency and not chased.

## Verification

`make verify-bus` is the gate for any bus-layout change: **17 layouts** —
all three carriers of the housekeeping block, the election, 1–7 senders per
bus, both cross-sends, split blocks — rendered and compared **bit-for-bit**
against a stamp taken before the edit (`SAVE=1` first). The four-buffer
restructure itself was proven exact by pointing the candidate's read at the
same buffer *generation* as the reference — 17/17 bit-identical at lag 0 —
separating the layout change from the latency change completely. See
`docs/HARNESS.md` for where this sits in the wider rig.

## The shared window, mapped

| range | what | notes |
|---|---|---|
| `0x30000–0x30047` | stock's per-frame parameter staging ✅ | rewritten every frame — never usable |
| `0x30000–0x37FFF` | core 0's half: ChonVerb's relocated buffers (`0x30000`, `0x34000`), shimmer line, tank state | fully owned — no free ground (`CLAUDE.md`) |
| `0x31000` / `0x32000` | stock bootstraps A and B ✅ | dead after boot |
| `0x36000+` | **bus scratch** — rotation, 4×2 accumulator sets, counts, reciprocals, role locks | the one region both cores touch |
| `0x38000–0x3FFFF` | core 1's half: BongDelay's LineL + LineR, 16,384 words each | ping-pong, ~371 ms per line |

Constraints that shaped it: AGU modulo addressing needs power-of-2
alignment, so big buffers start at `0x30000`/`0x34000`/`0x38000`/`0x3C000`;
the private and shared regions are not contiguous (`0xC000–0x2FFFF` is
absent), so no single 128K buffer; and the DSP56720 manual guarantees no
bus contention while the cores touch different 8K blocks ✅ — the half/half
split satisfies that everywhere except the scratch, which both cores must
touch by definition and which is a few hundred words in one block.

A delay line must never be based in core 0's half: it would sweep the
rotation word, all four accumulator sets and both role locks every 16,384
samples and blow up any multi-server layout (measured, 12 Aug 2026 — the
DEV build places the delay at its shipping `0x38000` base for exactly this
reason).

## Program space: the payloads are different programs

Specialization (`SPEC=1`) is what pays for all of this: each payload
carries SEND plus *its* server only, so the donor region (2,724 words per
core, from the three stock FX2 reverb slots — which were never on the FX1
menu, so FX1 lost nothing) is spent once per effect instead of twice.
`SPEC=1` requires `XBUS=1` — without the bus, each half of the tracks can
reach only its own core's server, **and the broken build still makes
sound**, which is why the build guards the combination. The build report is
the live free-word ledger — `make bus` prints it; numbers quoted in prose
go stale (several did in this file's own history).
