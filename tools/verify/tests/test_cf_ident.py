"""tools/verify/verify_cf_ident.py's comparison on synthetic samples and WAV files (no image, no port)."""
import pathlib
import random
import sys
import tempfile
import unittest
import wave

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/verify"))
import verify_cf_ident as V  # noqa: E402


def noise(n, seed):
    r = random.Random(seed)
    return [r.randrange(-30000, 30000) for _ in range(n)]


def started(at, content, length):
    """Silence, then `content` from sample `at`: a transport start."""
    return ([0] * at + content + [0] * length)[:length]


def write_wav(path, chans):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(len(chans))
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"".join(chans[c][i].to_bytes(2, "little", signed=True)
                               for i in range(len(chans[0])) for c in range(len(chans))))


class Align(unittest.TestCase):
    def test_identical(self):
        a = noise(20000, 1)
        self.assertEqual(V.align(a, list(a)), ([], []))

    def test_an_earlier_start_is_one_shift(self):
        x = noise(16000, 2)
        a, b = started(1000, x, 20000), started(997, x, 20000)
        shifts, bad = V.align(a, b)
        self.assertEqual(bad, [])
        self.assertEqual([s for _, s in shifts], [-3])

    def test_a_changed_sample_is_a_content_difference(self):
        x = noise(16000, 3)
        a = started(1000, x, 20000)
        b = list(a)
        b[9000] += 1
        shifts, bad = V.align(a, b)
        self.assertTrue(bad, "one sample changed must be found")

    def test_a_shift_beyond_the_limit_is_a_difference(self):
        x = noise(16000, 4)
        _, bad = V.align(started(1000, x, 20000), started(600, x, 20000), max_shift=256)
        self.assertTrue(bad)

    def test_a_short_tail_is_compared_as_it_lies(self):
        a = noise(5000, 5)
        b = list(a)
        b[-10] += 1
        self.assertTrue(V.align(a, b)[1])


class Compare(unittest.TestCase):
    def setUp(self):
        self.d = pathlib.Path(tempfile.mkdtemp())
        self.x, self.y = noise(16000, 6), noise(16000, 7)

    def pair(self, cand_l, cand_r, midi_b=b"\x90\x3c\x64"):
        write_wav(self.d / "base_core0.wav", [started(1000, self.x, 20000), started(1000, self.y, 20000)])
        write_wav(self.d / "cand_core0.wav", [cand_l, cand_r])
        (self.d / "base_midi.bin").write_bytes(b"\x90\x3c\x64")
        (self.d / "cand_midi.bin").write_bytes(midi_b)
        return V.compare(self.d, self.d)[0]

    def test_identical(self):
        self.assertEqual(self.pair(started(1000, self.x, 20000), started(1000, self.y, 20000)), "IDENTICAL")

    def test_each_channel_its_own_shift(self):
        # an event between two slots of the frame: one slot moves 3 samples, the next 2
        self.assertEqual(self.pair(started(997, self.x, 20000), started(998, self.y, 20000)), "EQUAL UP TO TIME SHIFTS")

    def test_content(self):
        r = started(1000, self.y, 20000)
        r[12000] = -r[12000] or 1
        self.assertEqual(self.pair(started(1000, self.x, 20000), r), "CONTENT DIFFERS")

    def test_midi(self):
        self.assertEqual(self.pair(started(1000, self.x, 20000), started(1000, self.y, 20000), b"\x90\x3c\x65"),
                         "CONTENT DIFFERS")

    def test_no_audio_is_a_fail(self):
        empty = pathlib.Path(tempfile.mkdtemp())
        self.assertEqual(V.compare(empty, empty)[0], "FAIL")


if __name__ == "__main__":
    unittest.main()
