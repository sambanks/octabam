"""The gate cache's key parts and store rules, and the machine's gate slots:
no firmware, no port."""
import os
import pathlib
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import gate_cache
import slots


class CacheTests(unittest.TestCase):
    def test_closure_follows_the_graph(self):
        deps = {"a.py": {"b.py"}, "b.py": {"c.py"}, "c.py": set(), "d.py": {"a.py"}}
        self.assertEqual(gate_cache.closure(["a.py"], deps), {"a.py", "b.py", "c.py"})

    def test_tracked_leaves_out_markdown(self):
        with tempfile.TemporaryDirectory() as d:
            import subprocess
            d = pathlib.Path(d)
            (d / "m").mkdir()
            (d / "m/a.s").write_text("x"); (d / "m/README.md").write_text("y")
            subprocess.run(["git", "init", "-q"], cwd=d, check=True)
            subprocess.run(["git", "add", "."], cwd=d, check=True)
            self.assertEqual(gate_cache.tracked(d, "m"), ["m/a.s"])

    def test_shared_key_ignores_the_image_and_moves_with_a_module_file(self):
        import subprocess
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d)
            (d / "modules/x").mkdir(parents=True)
            (d / "modules/x/a.s").write_text("1"); (d / "out/raw").mkdir(parents=True)
            (d / "out/raw/section_3_MAIN_OS.bin").write_text("os")
            subprocess.run(["git", "init", "-q"], cwd=d, check=True)
            subprocess.run(["git", "add", "-A", "-f"], cwd=d, check=True)
            args = (d, "g", ["python3", "g.py"], set(), ["modules/x"])
            with mock.patch("reach.port_digest", return_value="p", create=True):
                import reach  # noqa: F401
                one = gate_cache.shared_key(*args, deps={}, env={})
                self.assertEqual(one, gate_cache.shared_key(*args, deps={}, env={}))
                (d / "modules/x/a.s").write_text("2")
                self.assertNotEqual(one, gate_cache.shared_key(*args, deps={}, env={}))
                (d / "modules/x/a.s").write_text("1")
                (d / "modules/y").mkdir(); (d / "modules/y/manifest.py").write_text("m")
                subprocess.run(["git", "add", "-A", "-f"], cwd=d, check=True)
                two = gate_cache.shared_key(*args, deps={}, env={})
                (d / "modules/y/manifest.py").write_text("m2")
                self.assertEqual(two, gate_cache.shared_key(*args, deps={}, env={}))   # an unrelated module's manifest
                (d / "out/raw/section_3_MAIN_OS.bin").write_text("os2")
                self.assertNotEqual(two, gate_cache.shared_key(*args, deps={}, env={}))

    def test_shared_key_takes_the_build_trees_python_only_where_the_build_reaches(self):
        import subprocess
        import reach
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d)
            (d / "tools/build").mkdir(parents=True); (d / "tools/remix").mkdir(parents=True)
            (d / "out/raw").mkdir(parents=True); (d / "out/raw/section_3_MAIN_OS.bin").write_text("os")
            root = reach.BUILD_ROOTS[0]
            files = {root: "1", "tools/remix/lib.py": "1", "tools/remix/selftest.py": "1", "tools/remix/t.json": "1"}
            for f, v in files.items():
                (d / f).write_text(v)
            subprocess.run(["git", "init", "-q"], cwd=d, check=True)
            subprocess.run(["git", "add", "-A", "-f"], cwd=d, check=True)
            deps = {root: {"tools/remix/lib.py"}, "tools/remix/lib.py": set(), "tools/remix/selftest.py": {"tools/remix/lib.py"}}
            with mock.patch("reach.port_digest", return_value="p"):
                k = lambda scripts=(): gate_cache.shared_key(d, "g", ["python3", "g.py"], set(scripts), [], deps=deps, env={})
                one = k()
                for f, moves in (("tools/remix/selftest.py", False), ("tools/remix/lib.py", True),
                                 ("tools/remix/t.json", True), (root, True)):
                    (d / f).write_text("2")
                    self.assertEqual(k() != one, moves, f)
                    (d / f).write_text("1")
                # the gate's own closure still takes a script the build does not reach
                two = k({"tools/remix/selftest.py"})
                (d / "tools/remix/selftest.py").write_text("2")
                self.assertNotEqual(two, k({"tools/remix/selftest.py"}))

    def test_project_stamp_moves_with_a_file(self):
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d)
            (d / "bank01.work").write_text("x")
            one = gate_cache.project_stamp(d)
            (d / "bank01.work").write_text("xy")
            self.assertNotEqual(one, gate_cache.project_stamp(d))
        self.assertEqual(gate_cache.project_stamp(None), "none")

    def test_a_fresh_project_is_keyed_by_its_marker_not_its_file_times(self):
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d)
            (d / "NOPROJ").mkdir()
            (d / "NOPROJ" / "project.work").write_text("x")
            (d / "fresh.key").write_text("abc")
            one = gate_cache.project_stamp(d / "NOPROJ")
            os.utime(d / "NOPROJ" / "project.work", (1, 1))
            self.assertEqual(one, gate_cache.project_stamp(d / "NOPROJ"))
            (d / "fresh.key").write_text("abd")
            self.assertNotEqual(one, gate_cache.project_stamp(d / "NOPROJ"))
            (d / "NOPROJ" / "project.work").write_text("xy")
            (d / "fresh.key").write_text("abc")
            self.assertNotEqual(one, gate_cache.project_stamp(d / "NOPROJ"))

    def test_a_pass_is_stored_with_its_skips_and_the_switch_turns_it_off(self):
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(gate_cache, "store_dir", lambda root=None: pathlib.Path(d)), \
                mock.patch.dict(os.environ, {"OCTABAM_GATE_CACHE": "1"}):
            gate_cache.store("k2", dict(remix="r", job="set", seconds=1.0, skips=["[SKIP] midi: x"]))
            self.assertEqual(gate_cache.lookup("k2")["skips"], ["[SKIP] midi: x"])
            with mock.patch.dict(os.environ, {"OCTABAM_GATE_CACHE": "0"}):
                self.assertIsNone(gate_cache.lookup("k2"))

    def test_the_key_covers_every_manifest_and_the_remix_data_files(self):
        sys.path.insert(0, str(gate_cache.ROOT / "tools"))
        from remix import registry
        carried = {m.name for m in registry.selected(registry.remix("octabam"))}
        other = next(p.parent.name for p in sorted((gate_cache.ROOT / "modules").glob("*/manifest.py"))
                     if p.parent.name not in carried)
        files = gate_cache.inputs(gate_cache.ROOT, "octabam", set(), {})
        self.assertIn(f"modules/{other}/manifest.py", files)
        self.assertIn("tools/remix/stock_labels.json", files)


class SlotTests(unittest.TestCase):
    def test_one_slot_makes_the_second_holder_wait(self):
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(slots, "slot_dir", lambda root=None: pathlib.Path(d)), \
                mock.patch.dict(os.environ, {"OCTABAM_SLOTS": "1"}):
            os.environ.pop("OCTABAM_SLOT", None)
            said, order = [], []

            def second():
                with slots.slot("second", poll=0.05, say=lambda *a, **k: said.append(a[0])):
                    order.append("second")
            with slots.slot("first", say=lambda *a, **k: None) as env:
                self.assertEqual(env["OCTABAM_SLOT"], "0")
                t = threading.Thread(target=second)
                t.start()
                time.sleep(0.3)
                order.append("first done")
            t.join(5)
            self.assertEqual(order, ["first done", "second"])
            self.assertTrue(any("busy" in s and "first" in s for s in said), said)

    def test_a_holder_child_takes_no_second_slot(self):
        with mock.patch.dict(os.environ, {"OCTABAM_SLOT": "2"}):
            with slots.slot("child") as env:
                self.assertEqual(env["OCTABAM_SLOT"], "2")


if __name__ == "__main__":
    unittest.main()
