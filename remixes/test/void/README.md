# remix `void`

Carries VOID and KEYBUS beside the stock FX set minus PLATE REV (VOID's DSP
host).

## Hardware

- **VOID V7** (20 Oct 2026): `void-handoff` working tree (not a git commit) —
  BAL/AC-FDBK; four `mpy` sites still on `y0`. COLR floor was 200 Hz; HPF to 2 kHz.
- **VOID V8** (`471c7d5b` asm, signed `mpy x0,y1`): same COLR/HPF tables as V7.
  Not the tip after the darker-COLR commit.
- **VOID V9** (tip `dd89e2e2`+): same `void.asm` as V8, new coefficient tables —
  COLR 30 Hz..16 kHz, HPF 20 Hz..8 kHz. BRAIN tag `VOID V9.RMX`
  (`latest` + VOID + sidechain). This is the hardware report for the tip.

### Knobs on V9 (Ilia's MKII, 21 Oct 2026)

| knob | tried |
|---|---|
| BAL | default 0 = full input; raised toward noise |
| RATE / SHPE / DPTH | AM scrape |
| DRV + FDBK | high FDBK+DRV scrapes (AC), not DC-silent |
| COLR | across range; closed darkens; with HPF up, closed body kills (~−60 dB) |
| HPF | across range; thins; with COLR closed pinches hard |
| WID | mono → stereo grit (SETUP) |
| two instances | exercised on separate tracks |

### Neighbour AM — V215 N7 / N8 (22 Oct 2026, MKII)

Non-first same-core slots: RATE/SHPE idle; DPTH×neighbour env AM the
**noise** only. Y-direct SC keybus (no X:$500). Current tip law:

```
noise'  = FDBK+DRV(white → HPF/COLR)
noise'' = noise' · ((1−DPTH)+DPTH·uni)   # then WID
wet     = (1−BAL)·dry + BAL·noise''
```

BAL=0 exact dry; BAL=127 pure noise''. DIV removed.

| check | expect |
|---|---|
| T1 VOID LFO | scrape unchanged |
| T2 BAL=0, T1 playing | exact dry (DRV/FDBK/DPTH/WID ignored) |
| T2 BAL mid, T1 hits | dry↔noise crossfade; grit opens on hits |
| T2 BAL=127, T1 silent + DPTH high | mute |
| T2 RATE/SHPE | idle under nbr AM |
| T2 HPF/COLR | grit only; BAL=0 dry unchanged |
| FM on T1 | pitch OK (ML_FM_MAX=3) |
| T5 / T6 | other core same |

### WID — LATEST NL → NN (22 Oct 2026, MKII)

| tag | what was on the card | listen |
|---|---|---|
| LATEST NL | WID second **white** only (pre HPF/COLR) | harsh / wrong tone |
| LATEST NM | filtered side, `L=mid`, R opens | left pull |
| LATEST NN | `L/R=(1−w)·mid±w·side` | mono sum nulls mid → LFO scrape dies |
| **LATEST NO** | `L/R = mid ± (w/2)·side` | current — WID up keeps LFO in mono |

Confirm on NO: T1 LFO RATE/SHPE/DPTH with BAL up; WID=0 mono; WID up
stereo without killing scrape in mono/cue; BAL=0 exact dry.
