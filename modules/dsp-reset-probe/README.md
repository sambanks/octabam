# DSP RESET PROBE

**Can the ColdFire reset the DSP?** If it can, OS SWITCH stops costing 40
DSP words in both payloads and every image can switch away, not only into.
If it cannot, the park code stays and the answer is the placement work
instead (move it into the payload's unused interrupt vectors).

Markers as `docs/firmware/CHIP.md`: ✅ measured (under the port where it
says so, else read from the user's image), 🟡 inferred, ❓ open.

## Why the question is worth a probe

OS SWITCH's soft reset restarts the ColdFire and **not** the DSP ✅ (on the
unit, BOOT TRACE build 4, 29 Sep 2026: the staged OS starts its upload at
`0x40001e50` and never returns from it). So each core is told to park itself
in a boot-ROM loader of its own first — `modules/os-switch/dsp_park.asm`,
40 words in **both** payloads. Payload A of a full remix cannot spare them:
`bottleservice-ret`'s stage-B builds are switch TARGETS only.

A reset line would remove the park, the words, and the asymmetry.

## The candidates

| # | candidate | status |
|---|---|---|
| A | **RSTOUT**, the reset controller's output to the board: RCR bit 6, FRCRSTOUT, `0xfc0a0000` | ❓ what this probe asks |
| B | the GPIO pin the bootstrap drives once at `0x400e0dce`, right after it selects DSP core 0 | ❌ **retracted** |

**Why B is retracted.** The write is `moveq #1,%d0 / move.b %d0,(0xfc0a4024)`
and `0xfc0a4024` is the **data direction** register of the port whose output
register `0xfc0a400c` is the DSP core select: the bootstrap drives the select
pin low and then makes it an output. Not a reset line. The GPIO block's map,
and the three sites that fix it, are in `docs/firmware/ARCHITECTURE.md`
("The GPIO block").

**What lowers the odds on A.** Two devices are known to keep their state
across the soft reset: the DSP ✅ (above) and the panel controller ✅ (build
1: the bootstrap's first panel exchange never completes, which is why the
switcher sends `60 02` first). If `SOFTRST` asserts RSTOUT, then nothing on
RSTOUT reset either, and forcing it will not help. If it does not, RSTOUT is
untested and A is open. Which of the two the MCF54455 does is the fact that
would settle it without a probe 🟡 — the reference manual, not this repo.

## What the probe does

The instrument is the boot ROM's own protocol: seven words (`micro.asm`)
that answer with a magic **only if a ROM is listening**. `probe.s` has the
full procedure, the note table and the risk; in short, at `0x40000518` (the
boot, after the DSP upload, before the panel link, the card and the RTOS):

1. **the control** — probe core 0 with no pulse. A running payload must not
   answer. If it does, the probe says so (note 48) and stops: an instrument
   that answers when nothing happened cannot report that something did.
2. **the pulse** — RCR bit 6 set then cleared; pass 2 holds it ~1 ms.
3. **the test** — probe core 0 and core 1.
4. **the restore** — if a core answered, pulse again (back into the ROM) and
   re-run the stock upload, so audio comes back in the same boot.

Every step sends its MIDI note **before** it acts, so if a pulse takes the
unit down the last note names the step.

## Run it — no flash needed

The probe image is a **switch target**, so an already-flashed image with OS
SWITCH boots it without writing the flash, and a power-cycle comes home.

```bash
make obi REMIX=dsp-reset OBI=DSPRESET      # -> out/DSPRESET.OBI
# copy it to the card root, then on the unit: MAIN MENU > OS > DSPRESET > YES
python3 tools/hw/ot_midi.py listen 60      # MIDI OUT, while it boots
```

Read the notes with `probe.s`'s table. The short version:

| what came back | what it means |
|---|---|
| 43 and 44 with velocity **1** | **the DSP is in its boot ROM: RSTOUT resets it.** OS SWITCH can drop the park |
| 43/44 velocity 0 or 3, note 47 velocity 0 | the pulse did nothing. The park stays |
| note 48 | the control pass answered: the instrument is untrustworthy, nothing is concluded |
| 45 then 46 | a core answered and both payloads were uploaded again — audio should work |
| nothing after 42 | the pulse took the unit down. Power-cycle; that pass's candidate is dangerous, not viable |

**After a "no" the image may have no audio until a power-cycle.** The
control pass leaves the probe's first words unread in a running payload's
receive register, which is enough to put its frame protocol out of step,
and the only way back into a boot ROM is the very reset the probe is
asking about (`probe.s`, "the restore", says why the alternative -- OS
SWITCH's park command -- is worse: a park that does not take leaves the
stock uploader waiting forever, a boot that never ends). After a "yes"
both payloads are uploaded again and the boot ends as it started.

A `.bin` build (`make image REMIX=dsp-reset BUILD=<nn>`) works the same way
if you would rather flash it.

## Measured ✅ (under the port, `tools/verify/verify_dspreset.py`)

- **The instrument answers both ways.** The same image, booted twice: plain,
  every probe comes back with no answer, nothing is re-uploaded and the boot
  reaches the RTOS handoff; with `ot_emu --dsp-reset-on 0xfc0a0000:6` (the
  port modelling a reset line on that bit, `dsp.h bootReset`), the control
  pass is still empty and then **both cores answer with their own magic**
  (`0x5a3c60`, `0x5a3c61`), the probe re-pulses, the stock upload runs again
  (bootstrap A's 50 words to `P:0x31000`, B's 58 to `P:0x32000`) and the
  boot still reaches the handoff.
- **The boot survives either way**: the plain run reaches the RTOS handoff
  with the probe's report intact.
- **The seven words are `micro.asm`'s**, assembled by `dsp_asm` on every run
  and disassembled back.

The model is **not** evidence about the hardware — it exists so that a "no"
from the unit means "no", and not "the probe cannot see a yes".

## Not measured ❓

1. **The unit.** Nobody has run this yet. That is the point of it.
2. **Whether RSTOUT is asserted by the soft reset already** (above).
3. **What else is on RSTOUT.** The probe runs before the panel link, the
   card and the RTOS precisely so that a reset of the panel or the
   converters is harmless — but if RSTOUT reaches something the running
   ColdFire needs, the pulse ends the boot. A power-cycle is the way out;
   the flash is never written.
