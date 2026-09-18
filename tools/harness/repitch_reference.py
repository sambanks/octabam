"""Offline variable-speed loop reference. This is NOT a firmware implementation."""
import math
from fractions import Fraction


def render(samples, channels, source_bpm, target_bpm):
    """Return interleaved PCM with periodic linear interpolation.

    No antialias filter, live tempo changes, or hardware fixed-point model.
    Output keeps the input sample rate. Neutral PTCH/RATE only.
    """
    source, target = Fraction(str(source_bpm)), Fraction(str(target_bpm))
    if source <= 0 or target <= 0:
        raise ValueError("Both tempos must be positive")
    if channels <= 0 or len(samples) % channels:
        raise ValueError("Invalid interleaved samples")
    frames = len(samples) // channels
    if not frames:
        return []
    ratio = target / source
    result = []
    for frame in range(math.ceil(frames / ratio)):
        position = frame * ratio
        index = position.numerator // position.denominator
        fraction = float(position - index)
        following = (index + 1) % frames
        for channel in range(channels):
            a = samples[index * channels + channel]
            b = samples[following * channels + channel]
            result.append(round(a + (b - a) * fraction))
    return result
