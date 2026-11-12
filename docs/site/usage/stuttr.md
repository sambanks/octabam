**Chance grain repeater.** Input always writes the stock FX ring. On each
**RATE** tick, **CHNC** may grab a **SIZE** grain and **HOLD**-loop it.
Miss stays dry. Probabilistic stutter / buffer grab. **MODE** sets 1× /
½× / ¼× / random playback rate. **REV** is reverse chance per repeat.
**MIX 0** is exact dry.

![STUTTR: RATE → CHNC hit/miss → grab+HOLD or dry → MIX.](../../img/stuttr/path.svg)

## Access

Select a track, press **`[FX2]`** (or **`[FX1]`** when the remix lists it
there), pick **Stuttr**.

## Operation

Defaults leave **CHNC** at 0 (never grabs). Raise **CHNC** so grabs can
fire. **RATE** sets how often attempts happen. **HOLD** keeps the grain
repeating after a hit. Engage/release each crossfade ~2 ms so edges stay
clean. Try **MODE** **HALF** or **QUART** for pitched-down repeats.
**RND** varies rate per wrap. **REV** at 0 is always forward. **SYNC**
defaults to 8.

## Parameters

| Knob | Default | What it does |
|---|---|---|
| SIZE | 64 | grain length ((kn+1)² words; ~0.1-186 ms on FX2) |
| RATE | 64 | how often CHNC may attempt a grab |
| CHNC | 0 | 0 = never; 127 = always grab on tick |
| HOLD | 64 | how long to keep repeating after a hit |
| REV | 0 | per-repeat reverse probability |
| MIX | 127 | dry/wet of the stutter vs live |
| MODE | FWD | FWD / HALF / QUART / RND |
| SYNC | 8 | FREE / 16 / 8 / 4 divisions of the attempt clock |
