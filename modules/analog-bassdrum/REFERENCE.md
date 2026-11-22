# Drumazon 2 reference, 28 September 2026

The user initialized **SCENE > Init** in their installed Drumazon 2 and
closed the hosted editor. The saved component state identifies `- Init -`,
version 2.0.4. It contains BD Attack 25%, Tune 50%, Decay 25%, Pitch 50%,
and Tune Depth 50%; BD and master levels are 0 dB.

The reference harness restores this state for each capture, disables the
internal sequencer and BD processing, and routes the bass drum directly to
Master with its send off. Note 36, velocity 100, arrives at 100 ms in a
three-second, 44.1 kHz render. No reference gain normalization is applied.
References use float32 WAV to preserve peaks above full scale at high ATTACK.
A repeated init capture is bit-identical. A control with note-off at 200 ms
and one without it produced identical init audio; the reproducible host
omits note-off.

The first Pedalboard audio render crashed inside Drumazon. The companion
JUCE host succeeds with all **16 stereo buses** enabled and backed by real
buffers. Pedalboard was used to open/save the initialized editor state.
No plugin binary, state, preset data or reference recording is included in
the module. All such artifacts are local to ignored `out/`.

## What the synthesis now models

The captures informed independent base pitch, pitch-envelope time, pitch
excursion and amplitude release curves. The body appears after an
approximately 3 ms reset interval; its amplitude is nearly flat until
about 60 ms, followed by the DECAY-controlled release. The original
triangle shaper remains; the trigger transient now has a negative pulse,
a short positive rebound and a filtered noise contribution. The short VCO
release ramp is an empirical fit, not a claim about Drumazon's code or a
particular transistor circuit.

`generate.py` contains the original coefficient fits. The center value 64
maps to 50%, and endpoints 0/127 reach the full reference control range.
The fastest TUNE extrapolation is ill-conditioned: its excursion is capped
and that extreme is not claimed as a match.
