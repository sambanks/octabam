"""USB configuration descriptors: every generated table's counts agree with
what follows them (descriptors.check_config, #1039)."""
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
import toolpath  # noqa: E402,F401
sys.path.insert(0, str(ROOT / "modules" / "usb"))
import descriptors  # noqa: E402


def interfaces(cfg):
    """(interface, alt, bNumEndpoints, endpoint addresses that follow) per interface descriptor."""
    out, i = [], 9
    while i < len(cfg):
        if cfg[i + 1] == 4:
            out.append([cfg[i + 2], cfg[i + 3], cfg[i + 4], []])
        elif cfg[i + 1] == 5:
            out[-1][3].append(cfg[i + 2])
        i += cfg[i]
    return out


class Descriptors(unittest.TestCase):
    def test_every_set_passes_the_check(self):
        descriptors._blob()                     # raises naming the set on any mismatch

    def test_msc_declares_its_two_endpoints_with_midi_off(self):
        for hs in (False, True):
            for cfg in (descriptors.msc_only_config(hs),
                        descriptors.audio_config(hs, nch=20, midi=False),
                        descriptors.audio_config(hs, nch=20, midi=True)):
                num, alt, n, eps = interfaces(cfg)[0]
                self.assertEqual((num, alt, n, eps), (0, 0, 2, [0x81, 0x01]))

    def test_the_check_refuses_the_old_count(self):
        old = bytearray(descriptors.msc_only_config(True))
        old[9 + 4] = 1                          # bNumEndpoints as before #1039
        with self.assertRaisesRegex(ValueError, "declares 1 endpoint"):
            descriptors.check_config(bytes(old))

    def test_the_check_refuses_a_wrong_total_and_interface_count(self):
        cfg = bytearray(descriptors.midi_config(True))
        cfg[2] += 1
        with self.assertRaisesRegex(ValueError, "wTotalLength"):
            descriptors.check_config(bytes(cfg))
        cfg = bytearray(descriptors.midi_config(True))
        cfg[4] += 1
        with self.assertRaisesRegex(ValueError, "bNumInterfaces"):
            descriptors.check_config(bytes(cfg))


if __name__ == "__main__":
    unittest.main()
