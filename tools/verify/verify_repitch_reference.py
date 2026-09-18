"""Offline specification tests only; no firmware behavior is tested."""
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "harness"))
from repitch_reference import render


class RepitchReference(unittest.TestCase):
    def test_unity(self):
        samples = [-32768, 32767, -123, 456, 0, 0]
        self.assertEqual(render(samples, 2, 120, 120), samples)

    def test_pitch_and_duration(self):
        # Four beats at 120 BPM; count crossings to measure rendered pitch.
        samples = [round(20000 * math.sin(2 * math.pi * 440 * n / 48000))
                   for n in range(96000)]
        for tempo, count, frequency in ((60, 192000, 220), (90, 128000, 330),
                                        (120, 96000, 440), (180, 64000, 660),
                                        (240, 48000, 880)):
            with self.subTest(tempo=tempo):
                output = render(samples, 1, 120, tempo)
                self.assertEqual(len(output), count)
                crossings = sum(a <= 0 < b for a, b in zip(output, output[1:]))
                self.assertAlmostEqual(crossings * 48000 / count, frequency, delta=1.1)

    def test_stereo_loop_boundary(self):
        self.assertEqual(render([100, -100, 300, -300], 2, 120, 60),
                         [100, -100, 200, -200, 300, -300, 200, -200])

    def test_invalid_tempos(self):
        for source, target in ((0, 120), (120, 0), (-1, 120), (120, -1)):
            with self.assertRaises(ValueError):
                render([0], 1, source, target)

    def test_fractional_tempos(self):
        self.assertEqual(len(render([0] * 960, 1, "120.5", "90.375")), 1280)


if __name__ == "__main__":
    unittest.main()
