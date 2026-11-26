STUTTR is a probabilistic grain repeater and buffer stutter effect. The input
continuously writes into the stock FX ring buffer. On each **RATE** tick,
**CHNC** sets the probability of grabbing a grain of length **SIZE** and
looping it according to **HOLD**; when a tick misses, the dry signal passes
through. **MODE** selects 1×, ½×, ¼×, or random playback rate, **REV** sets
the probability that each repeat plays in reverse, and **MIX** at 0 outputs
the exact dry signal.

![STUTTR: RATE → CHNC hit/miss → grab+HOLD or dry → MIX.](../../img/stuttr/path.svg)

## Access

Select a track, press **`[FX2]`** (or **`[FX1]`** when the remix lists it
there), and choose **Stuttr**.

## Operation

By default, **CHNC** starts at 0 so no grabs occur until you raise it.
**RATE** sets how often grab attempts happen, and **HOLD** controls how long
a grain keeps repeating after a hit. Both engagement and release crossfade
over roughly 2 ms to avoid clicks. Use **HALF** or **QUART** in **MODE** for
pitched-down repeats, or **RND** to vary the playback rate on each wrap. With
**REV** at 0, repeats always play forward. **SYNC** defaults to 8.

## Parameters

| Knob | Default | What it does |
|---|---|---|
| SIZE | 64 | Grain length ((kn+1)² words; ~0.1-186 ms on FX2) |
| RATE | 64 | How often CHNC attempts a grab |
| CHNC | 0 | Grab probability (0 = never, 127 = always on every tick) |
| HOLD | 64 | How long to keep repeating after a hit |
| REV | 0 | Per-repeat reverse probability |
| MIX | 127 | Dry/wet mix of the stutter against the live signal |
| MODE | FWD | Playback rate: FWD, HALF, QUART, or RND |
| SYNC | 8 | Attempt clock division: FREE, 16, 8, or 4 |
