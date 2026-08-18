# Functional test pass — 17 Aug 2026, on the R28-equivalent tree

The consolidation matrix run after the day's bus/knob work, kept as the
baseline for "what the sim can prove works". Harness: the DEV hatch
(`make render-delay` flow), dsp_host WITH the real page-2 map (`cd8964a`) —
companion fields drivable for the first time. Re-run rule: any FAIL here is a
lead, not a verdict; three of the original eight "failures" were the
instrument, not the code (see the lessons at the bottom).

## Verdict: 24/24 functional checks pass. No code defect found.

### Reverb (ChonVerb)
| check | result |
|---|---|
| 3 modes render distinct, no rail at defaults | ✅ peaks .22/.19/.55 FS |
| BIG decay slows with TIME | ✅ 18.4 → 9.4 dB/0.8s across the knob |
| LP shapes HF DECAY RATE | ✅ −7.9 → −33.2 dB/s (127→0), BIG TIME 100 |
| HP shapes LF decay rate | ✅ −5.4 → −22.3 dB/s (0→127); ⚠️ 127 also drags MF (documented "annihilates") |
| MOD / SIZE / DIFF alter the render | ✅ |
| SHMR grows octave-up | ✅ 2f−f: −36.3 → −7.3 dB |
| WIDTH select (companion, first local drive) | ✅ corr +1.000 (W0) → −0.790 (W3) |
| GATE chops the tail | ✅ late tail −39.2 → silence |
| →DEL select feeds the delay | ✅ 0.375 FS at 3; digital silence at 0 |

### Delay (BongDelay)
| check | result |
|---|---|
| 5 modes distinct, no rail | ✅ peaks .12–.39 FS |
| CLEAN tap position | ✅ EXACT at `TIME·128+64` **+ 2 blocks** (see below) |
| FDBK per-repeat ratio constant | ✅ 0.611/0.611/0.611 at FDBK 90 (incl. TONE-127 loss) |
| TONE darkens repeats | ✅ 30 dB HF swing on echo 3 |
| PING decorrelates | ✅ corr +1.000 → −0.587 |
| PTCH intervals (companion) | ✅ 875/665/221/441 Hz vs 877/658/219/439 predicted |
| TAPE WOW / GRAIN set / REVERSE size respond | ✅ |
| FRZE decode reaches engine | ✅ (mid-run engage still hardware-only) |

### Levels (steady 438.75 Hz tone, 0.5 FS = −9.0 dBFS rms, send 100)
| path | rms |
|---|---|
| reverb MIX 0 / 32 / 64 | −9.0 / −9.0 / −8.9 dBFS (flat) |
| reverb MIX 96 / 127 | −14.0 / **−19.9** — the wet-makeup item is **−10.9 dB**, not the old "−7" |
| reverb per mode (MIX 127) | ROOM −23.0, PLATE −24.9, **BIG −16.1** (§1.4's 7–9 dB spread, at the output) |
| delay return (CLEAN defaults) | −12.7 dBFS, peak 0.390 |
| →VERB wash into reverb | −27.2 dBFS |

Deliberately NOT adjusted here: wet makeup (a flat +6 dB would rail BIG —
must land per-mode or after §1.4) and mode balance (voicing, by ear).

## Constants worth pinning
- **Bus latency is exactly 2 blocks (30 samples in dsp_host's 15-frame blocks;
  32 on hardware's 16)** — one from write-then-read, one from the four-buffer
  read-two-back. Measured to the sample at three TIME values.
- FDBK 90/128 = 0.703 coefficient → 0.611 measured per repeat; the difference
  is the TONE one-pole at 127, applied once per pass. Constant, so correct.

## Instrument lessons (three test bugs found before any code was blamed)
1. An in-loop filter shapes a decay **rate**; a static band-ratio snapshot is
   structurally blind to it. Measure successive windows.
2. The reverb's →DEL taps **dry** — a layout whose reverb track carries no
   audio proves nothing about the send.
3. The old FDBK check left PING at its ping-pong default, so single-channel
   echo ratios alternated by construction.


---

## Addendum, same day: ChonVerb v4 (the RETURN conversion) — gate results

The MIX rows above describe the pre-v4 insert and are HISTORICAL as of
`5924c8b`. The v4 gate, all measured:

| check | result |
|---|---|
| host audio + IN=0, no senders | digital silence (peak 0.000000) |
| IN 64→127 | **+5.95 dB at 0.1 FS** (exact); +6.80 at 0.5 FS — the extra is the §1.4 tank knee, isolated by the low-level control |
| sender auto-gain curve | identical to pre-v4 **to 0.01 dB** (the √N wobble is pre-existing tank nonlinearity, proven on both images) |
| wet continuity | pre-v4 MIX 127 −22.98 dBFS = v4 −22.98 (the constant is the ear-passed voicing) |
| →DEL at IN=0 | still feeds the delay, 0.375 FS — taps dry PRE-IN, deliberate |
| new mpy encodings | `mpy x1,y1` IS mpysu (safe: 2nd operand = IN ≥ 0); `mpy y0,x0` genuine signed — both disassembled |

⚠️ Harness bug found on the way: `REV_PARAMS[5]` still carried MIX's 127, which
under v4 registered a silent host client in every render — the phantom-client
defect reborn in the test harness, costing exactly the −3.01 dB it predicts.
