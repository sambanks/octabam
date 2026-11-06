"""Cards from passing gates leave no disk residue; failures retain evidence."""
import os
import json
import shutil
import pathlib
import shlex
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

HERE = pathlib.Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[1]))
import card_retention  # noqa: E402
import step  # noqa: E402
import module_gates  # noqa: E402
import acceptance  # noqa: E402
import check_shards  # noqa: E402


class CardRetention(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        (self.root / ".gitignore").write_text("out/\n")
        (self.root / "out").mkdir()

    def card(self, name, data=b"card"):
        path = self.root / "out" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def test_success_removes_new_cards_and_preserves_prior_cards(self):
        prior = self.card("prior.img")
        before = card_retention.snapshot(self.root)
        created = self.card("gate/card.img")
        count, size = card_retention.clean_new(self.root, before, "gate")
        self.assertEqual((count, size), (1, 4))
        self.assertTrue(prior.is_file())
        self.assertFalse(created.exists())
        self.assertEqual(__import__("json").loads((self.root / "out/card-retention.json").read_text())["files"],
                         {"out/gate/card.img": 4})

    def test_complete_suite_can_remove_changed_cards(self):
        card = self.card("reused.img", b"old")
        before = card_retention.snapshot(self.root)
        card.write_bytes(b"new-longer")
        self.assertEqual(card_retention.clean_new(self.root, before, include_modified=True), (1, 10))
        self.assertFalse(card.exists())

    def test_failed_gate_and_keep_cards_retain_images(self):
        with card_retention.Gate(self.root, "failed") as cards:
            failed = self.card("failure.img")
            cards.finish(False)
        self.assertTrue(failed.exists())
        with card_retention.Gate(self.root, "kept", dict(os.environ, KEEP_CARDS="1")) as cards:
            kept = self.card("kept.img")
            cards.finish(True)
        self.assertTrue(kept.exists())

    def test_open_card_is_kept_but_an_open_log_does_not_block_cleanup(self):
        before = card_retention.snapshot(self.root)
        card = self.card("open.img")
        with card.open("rb"):
            with self.assertRaises(card_retention.RetentionError):
                card_retention.clean_new(self.root, before)
        self.assertTrue(card.exists())
        log = self.root / "out/gate.log"
        with log.open("w"):
            self.assertEqual(card_retention.clean_new(self.root, before), (1, 4))
        self.assertFalse(card.exists())

    def test_pin_nested_repo_and_non_regular_cards_are_protected(self):
        pinned = self.root / "out/pinned"
        pinned.mkdir()
        (pinned / ".keep-cards").touch()
        self.card("pinned/card.img")
        nested = self.root / "out/shards/0"
        nested.mkdir(parents=True)
        (nested / ".git").write_text("gitdir: elsewhere\n")
        self.card("shards/0/card.img")
        real = self.card("real.img")
        (self.root / "out/link.img").symlink_to(real)
        os.link(real, self.root / "out/hard.img")
        self.assertEqual(card_retention.snapshot(self.root), {})

    def test_step_cleans_success_and_keeps_failure(self):
        script = "import pathlib,sys;pathlib.Path(sys.argv[1]).write_bytes(b'card');sys.exit(int(sys.argv[2]))"
        with mock.patch.object(card_retention, "ROOT", self.root):
            passed = self.root / "out/passed.img"
            failed = self.root / "out/failed.img"
            self.assertEqual(step.main(["--cards", sys.executable, "-c", script, str(passed), "0"]), 0)
            self.assertFalse(passed.exists())
            self.assertEqual(step.main(["--cards", sys.executable, "-c", script, str(failed), "2"]), 2)
            self.assertTrue(failed.exists())

    def test_later_gate_failure_does_not_keep_earlier_gate_cards(self):
        scripts = []
        for name, code in (("passed", 0), ("failed", 1)):
            rel = pathlib.Path("tools/verify") / f"{name}.py"
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("from pathlib import Path\n"
                            f"Path('out/{name}.img').write_bytes(b'card')\n"
                            f"raise SystemExit({code})\n")
            scripts.append(SimpleNamespace(script=str(rel), remix_arg=False, venv=False))
        gates = [(name, gate) for name, gate in zip(("PASS", "FAIL"), scripts)]
        with (mock.patch.object(module_gates, "ROOT", self.root),
              mock.patch.object(module_gates.registry, "remix", return_value=SimpleNamespace(name="fake")),
              mock.patch.object(module_gates.registry, "selected", return_value=[]),
              mock.patch.object(module_gates, "collect", return_value=gates),
              mock.patch.object(module_gates, "port_built", return_value=True),
              mock.patch.object(module_gates, "command",
                                side_effect=lambda gate, name: [sys.executable, str(self.root / gate.script)]),
              mock.patch.object(module_gates.gate_ledger, "record")):
            self.assertEqual(module_gates.main(["fake", "--stage", "image"]), 1)
        self.assertFalse((self.root / "out/passed.img").exists())
        self.assertTrue((self.root / "out/failed.img").exists())

    def child(self, code, env=None, pass_fds=()):
        return subprocess.run([sys.executable, "-c", "import sys;sys.path.insert(0," +
                               repr(str(HERE.parents[1])) + ");import card_retention as c;" + code],
                              cwd=self.root, env=env, pass_fds=pass_fds, capture_output=True, text=True)

    def test_missing_lsof_fails_before_command_starts(self):
        sentinel = self.root / "started"
        rc = card_retention.run([sys.executable, "-c", f"open({str(sentinel)!r}, 'w').close()"],
                                self.root, dict(os.environ, PATH="/no-tools"))
        self.assertEqual(rc, 2)
        self.assertFalse(sentinel.exists())

    def test_nested_runner_shares_ownership_but_independent_runner_is_refused(self):
        with card_retention.Gate(self.root, "outer") as outer:
            code = "\nwith c.Gate('.', 'inner') as g: pass"
            nested = self.child(code, outer.env, outer.pass_fds)
            self.assertEqual(nested.returncode, 0, nested.stderr)
            # Inner exit must not unlock the outer file description.
            other = self.child(code)
            self.assertNotEqual(other.returncode, 0)
            self.assertIn("another gate run owns", other.stderr)
        self.assertEqual(self.child(code).returncode, 0)

    def test_other_worktree_can_run_and_keep_cards_still_locks(self):
        other = self.root / "other"
        other.mkdir()
        with card_retention.Gate(self.root, "outer", dict(os.environ, KEEP_CARDS="1")):
            with card_retention.Gate(other, "other"):
                pass
            with self.assertRaisesRegex(card_retention.RetentionError, "another gate run"):
                with card_retention.Gate(self.root, "competitor"):
                    pass

    def test_lock_survives_shard_replacement(self):
        shard = self.root / "shard"
        with card_retention.Gate(shard, "setup", snapshot_cards=False):
            shard.mkdir()
            shutil.rmtree(shard)
            shard.mkdir()
            with self.assertRaisesRegex(card_retention.RetentionError, "another gate run"):
                with card_retention.Gate(shard, "competitor"):
                    pass

    def test_nested_make_preserves_lock_and_card_until_consumer_finishes(self):
        helper = str(HERE.parents[1])
        child = self.root / "child.py"
        child.write_text("import sys\nsys.path.insert(0, " + repr(helper) + ")\n"
                         "import card_retention as c\n"
                         "from pathlib import Path\n"
                         "with c.Gate('.', 'consumer') as g:\n"
                         "    assert Path('out/staged.img').read_bytes() == b'card'\n"
                         "    Path('out/new.img').write_bytes(b'new')\n"
                         "    g.finish(True)\n"
                         "assert Path('out/staged.img').exists()\n"
                         "assert not Path('out/new.img').exists()\n")
        (self.root / "Makefile").write_text(f"all:\n\t{shlex.quote(sys.executable)} child.py\n")
        with card_retention.Gate(self.root, "sequence") as outer:
            self.card("staged.img")
            result = subprocess.run(["make", "-j1"], cwd=self.root, env=outer.env,
                                    pass_fds=outer.pass_fds, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            outer.finish(True, include_modified=True)
        self.assertFalse((self.root / "out/staged.img").exists())
        events = [json.loads(line) for line in (self.root / "out/card-retention.jsonl").read_text().splitlines()]
        self.assertEqual([e["files"] for e in events], [{"out/new.img": 3}, {"out/staged.img": 4}])

    def test_cleanup_failure_is_a_runner_failure_and_retains_card(self):
        card = self.card("open.img")
        with card.open("rb"):
            cmd = [sys.executable, "-c", "open('out/open.img','wb').write(b'updated')"]
            rc = card_retention.run(cmd, self.root)
            self.assertEqual(rc, 2)
            result = acceptance.run_gate("held-card", cmd, self.root / "out", dict(os.environ), 5, self.root)
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["gate_status"], "passed")
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["card_retention"], "failed")
        self.assertTrue(card.exists())

    def test_shard_in_use_is_refused_before_setup(self):
        shards = self.root / "out/shards"
        (self.root / "out/raw").mkdir()
        (self.root / "out/raw/section_3_MAIN_OS.bin").touch()
        with (card_retention.Gate(shards / "0", "other driver", snapshot_cards=False),
              mock.patch.object(check_shards, "ROOT", self.root),
              mock.patch.object(check_shards, "make_shard") as setup):
            rc = check_shards.main(["--jobs", "1", "--split", "none", "--no-cache",
                                    "--shards", str(shards), "fake"])
        self.assertEqual(rc, 2)
        setup.assert_not_called()

    def test_shard_coordinator_overlaps_shared_gates_but_not_another_coordinator(self):
        shards = self.root / "out/shards"
        (self.root / "out/raw").mkdir()
        (self.root / "out/raw/section_3_MAIN_OS.bin").touch()
        result = dict(remix="fake", rc=0, seconds=0, skips=[],
                      log=self.root / "out/check_shards/fake.log")
        args = ["--jobs", "1", "--split", "none", "--no-cache", "--shards", str(shards), "fake"]
        with (card_retention.Gate(self.root, "shared gates"),
              mock.patch.object(check_shards, "ROOT", self.root),
              mock.patch.object(check_shards, "times_path", return_value=self.root / "times.json"),
              mock.patch.object(check_shards, "make_shard") as setup,
              mock.patch.object(check_shards, "run_remix", return_value=result)):
            self.assertEqual(check_shards.main(args), 0)
            setup.assert_called_once()
            with card_retention.Gate(self.root, "another coordinator", snapshot_cards=False,
                                     scope="shard-coordinator"):
                self.assertEqual(check_shards.main(args), 2)
            setup.assert_called_once()  # the refused coordinator did not refresh a shard

    def test_shard_job_keeps_staged_card_through_consumer_then_cleans_it(self):
        (self.root / "Makefile").write_text("bus:\n\t@true\n")
        producer = [sys.executable, "-c", "open('out/staged.img','wb').write(b'card')"]
        consumer = [sys.executable, "-c", "assert open('out/staged.img','rb').read() == b'card'"]
        job = ("image", [producer, consumer], {}, set())
        with card_retention.Gate(self.root, "shard owner", snapshot_cards=False) as owner:
            with mock.patch.object(check_shards.gate_ledger, "record"):
                result = check_shards.run_job(self.root, "fake", job, self.root / "out", owner=owner)
        self.assertEqual(result["rc"], 0, result["log"].read_text())
        self.assertFalse((self.root / "out/staged.img").exists())

    def test_tracked_card_is_never_a_candidate(self):
        self.card("fixture.img")
        subprocess.run(["git", "add", "-f", "out/fixture.img"], cwd=self.root, check=True)
        self.assertEqual(card_retention.snapshot(self.root), {})

    def test_exception_releases_ownership_without_cleaning(self):
        with self.assertRaisesRegex(RuntimeError, "interrupted"):
            with card_retention.Gate(self.root, "failed"):
                self.card("failure.img")
                raise RuntimeError("interrupted")
        with card_retention.Gate(self.root, "next"):
            self.assertTrue((self.root / "out/failure.img").exists())


if __name__ == "__main__":
    unittest.main()
