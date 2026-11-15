"""tools/hw/ot_events.py against a synthetic REMOTE block served by a fake transport (no unit, no image)."""
import pathlib
import struct
import sys
import threading
import time
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/hw"))
import ot_events as ev  # noqa: E402

TRACE = 0x46000000
NAMES = 0x46100000
COUNT = 0x46100400


class Unit:
    """A unit's block and memory. ctrl() and peek1() answer as the USB module does: at most 255 bytes, and one
    byte fewer when the request is a multiple of 64."""

    def __init__(self):
        self.head = 0
        self.screens = 0
        self.slots = [struct.pack(">HBBI", 0xffff, 0, 0, 0)] * ev.NREC
        self.mem = {}
        self.names = []
        self.calls = []
        self.on_call = None
        self.trace_count = 0
        self.trace = [(0, 0)] * ev.NTRACE
        self.sent = []

    def add(self, kind, arg=0, stamp=0):
        self.slots[self.head & 255] = struct.pack(">HBBI", self.head & 0xffff, kind, arg, stamp)
        self.head += 1

    def add_trace(self, pc, stamp):
        self.trace[self.trace_count & (ev.NTRACE - 1)] = (pc, stamp)
        self.trace_count += 1

    def block(self):
        hdr = struct.pack(">4s7I", ev.MAGIC, self.head, self.screens, 7, TRACE, NAMES if self.names else 0,
                          COUNT if self.names else 0, 0)
        return hdr + b"".join(self.slots)

    @staticmethod
    def size(n):
        n = min(n, 255)
        return n - 1 if n % 64 == 0 else n

    def ctrl(self, off, n):
        self.calls.append((off, n))
        out = self.block()[off:off + self.size(n)]
        if self.on_call:
            self.on_call(len(self.calls))
        return out

    def peek1(self, addr, n):
        n = self.size(n)
        if addr == TRACE:
            return struct.pack(">II", self.trace_count, 0)[:n]
        if TRACE + 8 <= addr < TRACE + 8 + 8 * ev.NTRACE:
            raw = b"".join(struct.pack(">II", *t) for t in self.trace)
            return raw[addr - TRACE - 8:addr - TRACE - 8 + n]
        if addr == COUNT:
            return struct.pack(">I", len(self.names))[:n]
        if addr >= NAMES:
            raw = b"".join(x.ljust(ev.NLEN, b"\0") for x in self.names)
            return raw[addr - NAMES:addr - NAMES + n]
        raise AssertionError(hex(addr))

    def cmd1(self, cid, arg):
        self.sent.append((cid, arg))
        return b"\x00" if cid & 0xff in (1, 2, 3, 4) else b"\x01"


class Poll(unittest.TestCase):
    def test_none_new(self):
        u = Unit()
        e = ev.Events(u.ctrl)
        self.assertEqual(e.poll(), [])
        self.assertEqual(e.lost, 0)

    def test_one_new(self):
        u = Unit()
        e = ev.Events(u.ctrl)
        u.add(ev.BY_NAME["PLAYING"], 1, 1234)
        r = e.poll()
        self.assertEqual(len(r), 1)
        self.assertEqual((r[0]["n"], r[0]["name"], r[0]["arg"], r[0]["stamp"]), (0, "PLAYING", 1, 1234))
        self.assertEqual(e.poll(), [])

    def test_300_new_loses_44(self):
        u = Unit()
        e = ev.Events(u.ctrl)
        for i in range(300):
            u.add(ev.BY_NAME["PATTERN"], i & 255)
        r = e.poll()
        self.assertEqual(e.lost, 44)
        self.assertEqual([x["n"] for x in r], list(range(44, 300)))
        self.assertEqual([x["arg"] for x in r], [i & 255 for i in range(44, 300)])

    def test_from_start_reads_what_the_ring_holds(self):
        u = Unit()
        for i in range(10):
            u.add(1)
        r = ev.Events(u.ctrl, from_start=True).poll()
        self.assertEqual([x["n"] for x in r], list(range(10)))

    def test_overwritten_between_head_and_record(self):
        u = Unit()
        e = ev.Events(u.ctrl)
        for i in range(5):
            u.add(2, i)

        u.calls.clear()

        def overwrite(call):
            if call == 1:                                   # after the header read: slot 3 now holds record 259
                u.slots[3] = struct.pack(">HBBI", 259, 2, 9, 0)
        u.on_call = overwrite
        r = e.poll()
        self.assertEqual([x["n"] for x in r], [0, 1, 2, 4])
        self.assertEqual(e.lost, 1)

    def test_seq_wraps_16_bits(self):
        u = Unit()
        u.head = 65534
        e = ev.Events(u.ctrl)
        for _ in range(4):
            u.add(3)
        self.assertEqual([x["n"] for x in e.poll()], [65534, 65535, 65536, 65537])

    def test_bad_magic(self):
        u = Unit()
        u.ctrl = lambda off, n: b"XXXX" + bytes(12)
        with self.assertRaises(RuntimeError):
            ev.Events(u.ctrl)

    def test_requests_are_never_a_multiple_of_64(self):
        u = Unit()
        e = ev.Events(u.ctrl)
        for _ in range(100):
            u.add(1)
        e.poll()
        self.assertTrue(u.calls)
        self.assertTrue(all(n <= 255 for _, n in u.calls))


class Waits(unittest.TestCase):
    def test_wait_for_with_tick(self):
        u = Unit()
        e = ev.Events(u.ctrl)
        ticks = []

        def tick():
            ticks.append(1)
            u.add(ev.BY_NAME["BANK"], 1)
            if len(ticks) == 3:
                u.add(ev.BY_NAME["PLAYING"], 1)
        r = e.wait_for("PLAYING", arg=1, timeout=5, tick=tick)
        self.assertEqual(r["name"], "PLAYING")
        self.assertEqual(len(ticks), 3)
        self.assertEqual([p["name"] for p in r["passed"]], ["BANK"] * 3)

    def test_wait_for_several_kinds_and_numbers(self):
        u = Unit()
        e = ev.Events(u.ctrl)
        u.add(ev.BY_NAME["LOADMASK"], 255)
        self.assertEqual(e.wait_for(("LOADALL", 2), timeout=1, tick=lambda: None)["name"], "LOADMASK")

    def test_wait_for_arg_filter(self):
        u = Unit()
        e = ev.Events(u.ctrl)
        u.add(ev.BY_NAME["PATTERN"], 3)
        u.add(ev.BY_NAME["PATTERN"], 5)
        self.assertEqual(e.wait_for("PATTERN", arg=5, timeout=1, tick=lambda: None)["n"], 1)

    def test_wait_for_times_out_and_names_what_passed(self):
        u = Unit()
        e = ev.Events(u.ctrl)
        u.add(ev.BY_NAME["BANK"], 2)
        with self.assertRaises(TimeoutError) as c:
            e.wait_for("PLAYING", timeout=0.05, tick=lambda: None)
        self.assertIn("PLAYING", str(c.exception))
        self.assertIn("BANK", str(c.exception))

    def test_strict_raises_on_lost(self):
        u = Unit()
        e = ev.Events(u.ctrl)
        for _ in range(300):
            u.add(1)
        with self.assertRaises(ev.Lost):
            e.wait_for("PLAYING", timeout=1, tick=lambda: None, strict=True)

    def test_wait_screen(self):
        u = Unit()
        e = ev.Events(u.ctrl)
        n = []

        def tick():
            n.append(1)
            if len(n) == 2:
                u.screens += 1
        self.assertEqual(e.wait_screen(timeout=1, tick=tick), 1)
        with self.assertRaises(TimeoutError):
            e.wait_screen(timeout=0.05, tick=lambda: None)

    def test_wait_screen_since(self):
        u = Unit()
        u.screens = 4
        e = ev.Events(u.ctrl)
        self.assertEqual(e.wait_screen(since=3, timeout=1, tick=lambda: None), 4)


class Trace(unittest.TestCase):
    def test_across_the_wrap(self):
        u = Unit()
        for i in range(600):
            u.add_trace(0x40000000 + i, 1000 + i)
        t = ev.trace(u.ctrl, u.peek1, last=100)
        self.assertEqual([e[0] for e in t], list(range(500, 600)))
        self.assertEqual(t[0][1:], (0x40000000 + 500, 1500))
        self.assertEqual(t[-1][1:], (0x40000000 + 599, 1599))

    def test_fewer_than_asked(self):
        u = Unit()
        for i in range(5):
            u.add_trace(0x40001000 + i, i)
        t = ev.trace(u.ctrl, u.peek1)
        self.assertEqual([e[0] for e in t], [0, 1, 2, 3, 4])

    def test_whole_ring_drops_the_slot_being_overwritten(self):
        u = Unit()
        for i in range(700):
            u.add_trace(i, i)
        t = ev.trace(u.ctrl, u.peek1)
        self.assertEqual([e[0] for e in t], list(range(700 - ev.NTRACE + 1, 700)))


class Remixes(unittest.TestCase):
    def test_name_hash(self):
        self.assertEqual(ev.name_hash(b""), 0)
        self.assertEqual(ev.name_hash(b"A"), 65)
        self.assertEqual(ev.name_hash(b"AB"), (65 * 33 + 66) & 0xffff)
        h = 0
        for c in b"STOCK140.RMX":
            h = (h * 33 + c) & 0xffff
        self.assertEqual(ev.name_hash(b"STOCK140.RMX"), h)

    def test_remixes_empty_without_the_module(self):
        u = Unit()
        self.assertEqual(ev.remixes(u.ctrl, u.peek1), [])

    def test_remixes_lists_names_in_the_unit_order(self):
        u = Unit()
        u.names = [b"A.RMX", b"B.RMX", b"LONGER-NAME.RMX"]
        self.assertEqual(ev.remixes(u.ctrl, u.peek1), u.names)

    def test_boot_sends_index_and_hash(self):
        u = Unit()
        u.names = [b"A.RMX", b"B.RMX"]
        self.assertTrue(ev.boot(u.cmd1, u.ctrl, u.peek1, "B.RMX"))
        self.assertEqual(u.sent, [(ev.CMD_BOOT | 1 << 8, ev.name_hash(b"B.RMX"))])

    def test_boot_absent_name_sends_nothing(self):
        u = Unit()
        u.names = [b"A.RMX"]
        self.assertFalse(ev.boot(u.cmd1, u.ctrl, u.peek1, b"C.RMX"))
        self.assertEqual(u.sent, [])

    def test_command_reply_byte(self):
        u = Unit()
        self.assertTrue(ev.command(u.cmd1, ev.CMD_DISK_ENTER))
        self.assertFalse(ev.command(u.cmd1, 9))

    def test_peek_chunks_to_255(self):
        calls = []

        def p(addr, n):
            calls.append((addr, n))
            return bytes(n)
        self.assertEqual(len(ev.peek(p, 0x40000000, 600)), 600)
        self.assertEqual([n for _, n in calls], [255, 255, 90])


class Stopped(unittest.TestCase):
    def remote(self, byte, bank=0, pattern=0):
        u = Unit()
        state = {"byte": byte, "bank": bank, "pattern": pattern}
        base = u.peek1

        def peek1(addr, n):
            if addr == ev.PLAYING_ADDR:
                return bytes([state["byte"]])
            if addr == ev.BANK_ADDR:
                return bytes([state["bank"], state["pattern"]])[:n]
            return base(addr, n)
        return ev.Remote(u.ctrl, peek1), state

    def test_playing_byte(self):
        r, st = self.remote(1)
        self.assertTrue(r.playing())
        st["byte"] = 2
        self.assertFalse(r.playing())

    def test_without_remote_it_sleeps_the_fallback(self):
        t = time.monotonic()
        self.assertFalse(ev.wait_stopped(None, 0.05))
        self.assertGreaterEqual(time.monotonic() - t, 0.05)

    def test_already_stopped_returns_at_once(self):
        r, _ = self.remote(2)
        t = time.monotonic()
        self.assertTrue(ev.wait_stopped(r, 5.0))
        self.assertLess(time.monotonic() - t, 0.5)

    def test_returns_when_the_byte_leaves_1(self):
        r, st = self.remote(1)
        threading.Timer(0.05, lambda: st.update(byte=2)).start()
        t = time.monotonic()
        self.assertTrue(ev.wait_stopped(r, 5.0))
        self.assertLess(time.monotonic() - t, 1.0)

    def test_still_playing_at_the_limit(self):
        r, _ = self.remote(1)
        t = time.monotonic()
        self.assertFalse(ev.wait_stopped(r, 0.1))
        self.assertGreaterEqual(time.monotonic() - t, 0.1)

    def test_an_unreadable_unit_sleeps_the_fallback(self):
        def bad(addr, n):
            raise OSError("pipe")
        r = ev.Remote(Unit().ctrl, bad)
        t = time.monotonic()
        self.assertFalse(ev.wait_stopped(r, 0.05))
        self.assertGreaterEqual(time.monotonic() - t, 0.05)

    def test_pattern_bytes(self):
        r, _ = self.remote(0, bank=2, pattern=5)
        self.assertEqual(r.pattern(), (2, 5))

    def test_wait_pattern_without_remote_sleeps_the_fallback(self):
        t = time.monotonic()
        self.assertFalse(ev.wait_pattern(None, 37, 0.05))
        self.assertGreaterEqual(time.monotonic() - t, 0.05)

    def test_wait_pattern_already_there_returns_at_once(self):
        r, _ = self.remote(0, bank=2, pattern=5)          # program 37 = bank 2, pattern 5
        t = time.monotonic()
        self.assertTrue(ev.wait_pattern(r, 37, 5.0))
        self.assertLess(time.monotonic() - t, 0.5)

    def test_wait_pattern_returns_when_both_bytes_match(self):
        r, st = self.remote(0, bank=0, pattern=5)         # the pattern matches, the bank does not yet
        threading.Timer(0.05, lambda: st.update(bank=2)).start()
        t = time.monotonic()
        self.assertTrue(ev.wait_pattern(r, 37, 5.0))
        self.assertLess(time.monotonic() - t, 1.0)

    def test_wait_pattern_never_arrives_at_the_limit(self):
        r, _ = self.remote(0, bank=0, pattern=0)
        t = time.monotonic()
        self.assertFalse(ev.wait_pattern(r, 37, 0.1))
        self.assertGreaterEqual(time.monotonic() - t, 0.1)

    def test_wait_pattern_unreadable_sleeps_the_fallback(self):
        def bad(addr, n):
            raise OSError("pipe")
        r = ev.Remote(Unit().ctrl, bad)
        t = time.monotonic()
        self.assertFalse(ev.wait_pattern(r, 3, 0.05))
        self.assertGreaterEqual(time.monotonic() - t, 0.05)

    def test_connect_without_a_unit_is_none(self):
        class Dev:
            def ctrl_transfer(self, *a, **k):
                raise OSError("STALL")
        self.assertIsNone(ev.connect(Dev()))

    def test_remote_wait_returns_none_at_the_timeout(self):
        r, _ = self.remote(1)
        self.assertIsNone(r.wait("PLAYING", 1, timeout=0.05))
        r.ev.ctrl.__self__.add(ev.BY_NAME["PLAYING"], 1)
        self.assertEqual(r.wait("PLAYING", 1, timeout=0.5)["arg"], 1)


if __name__ == "__main__":
    unittest.main()
