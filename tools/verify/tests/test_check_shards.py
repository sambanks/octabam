"""check_shards --by-gate: the job list mirrors `make verify-remix`."""
import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE.parents[2]))
import check_shards  # noqa: E402
from reach import recipe_scripts  # noqa: E402

ROOT = HERE.parents[3]


class ByGate(unittest.TestCase):
    def jobs(self, remix="octabam-bus"):
        return check_shards.remix_jobs(remix, ROOT / "out/shards/0")

    def test_every_recipe_script_has_a_job(self):
        jobs = self.jobs()
        check_shards.check_recipe(jobs)          # raises SystemExit on drift
        recipe = recipe_scripts((ROOT / "Makefile").read_text(), "verify-remix")
        named = set().union(*(scripts for _n, _c, _e, scripts in jobs)) | {"tools/verify/step.py", "tools/verify/card_retention.py"}
        self.assertTrue(recipe <= named, recipe - named)

    def test_drift_is_refused(self):
        jobs = [j for j in self.jobs() if j[0] != "usb"]
        with self.assertRaises(SystemExit) as cm:
            check_shards.check_recipe(jobs)
        self.assertIn("verify_usb.py", str(cm.exception))

    def test_image_stage_stages_its_own_card(self):
        """TEMPO BUS boots the card verify_set stages: its job stages it
        (--stage-only) and runs apart from verify_set's own run."""
        (_n, cmds, _e, _s), = [j for j in self.jobs() if j[0] == "set"]
        self.assertEqual([c[1] for c in cmds], ["tools/verify/verify_set.py"])
        staged = [j for j in self.jobs() if j[0].startswith("image:") and j[1][0][1].endswith("verify_set.py")]
        self.assertTrue(staged, "an image-stage gate that boots the staged card stages it first")
        for _n, cmds, _e, _s in staged:
            self.assertIn("--stage-only", cmds[0])
            self.assertEqual(cmds[1][cmds[1].index("--stage") + 1], "image")
            self.assertIn("--only-script", cmds[1])

    def test_image_stage_gates_are_one_job_each(self):
        image = [j for j in self.jobs() if j[0].startswith("image:")]
        self.assertGreater(len(image), 1)
        for _n, cmds, _e, _s in image:
            scripts = [c[cmds[-1].index("--only-script") + 1] for c in cmds[-1:]]
            self.assertEqual(len(scripts), 1)
        self.assertNotIn("image", [j[0] for j in self.jobs()])

    def test_module_gates_are_one_job_each(self):
        names = [j[0] for j in self.jobs()]
        self.assertIn("scenes-p2", names)
        self.assertEqual(len(names), len(set(names)))

    def test_every_job_carries_the_remix(self):
        for _n, _c, env, _s in self.jobs():
            self.assertEqual(env["REMIX"], "octabam-bus")

    def test_without_a_venv_the_skip_jobs_still_stand_for_their_scripts(self):
        real = check_shards.ROOT
        try:
            check_shards.ROOT = pathlib.Path("/nonexistent-tree")   # no .venv there
            jobs = [j for j in check_shards.remix_jobs("octabam-bus", ROOT / "out/shards/0") if j[0] == "labels"]
        finally:
            check_shards.ROOT = real
        self.assertEqual(jobs[0][1][0][0], "echo")
        self.assertEqual(jobs[0][3], {"tools/verify/verify_labels.py"})


class FailureExcerpt(unittest.TestCase):
    def test_keeps_failure_lines_and_the_tail_once_each_in_order(self):
        log = "\n".join([f"ok {i}" for i in range(100)] + ["  [FAIL] verify_x: boom"]
                        + [f"ok {i}" for i in range(100, 200)] + ["make: *** [x] Error 2"])
        out = check_shards.failure_excerpt(log, fails=5, tail=3)
        self.assertEqual(out, ["  [FAIL] verify_x: boom", "ok 198", "ok 199", "make: *** [x] Error 2"])

    def test_a_short_log_is_returned_whole(self):
        self.assertEqual(check_shards.failure_excerpt("a\nb", tail=40), ["a", "b"])


if __name__ == "__main__":
    unittest.main()


class PickJobs(unittest.TestCase):
    """--only-jobs / --skip-jobs: two parts of one remix cover every gate job once."""

    def test_the_two_parts_are_a_partition_of_the_jobs(self):
        jobs = [(n, [], {}, set()) for n in ("cycles", "image", "usb", "remix-switch")]
        long = {j[0] for j in check_shards.pick_jobs(jobs, ["remix-switch", "image"], [])}
        rest = {j[0] for j in check_shards.pick_jobs(jobs, [], ["remix-switch", "image"])}
        self.assertEqual(long, {"remix-switch", "image"})
        self.assertEqual(rest, {"cycles", "usb"})

    def test_a_name_that_is_no_job_is_refused_in_either_part(self):
        jobs = [("cycles", [], {}, set())]
        for only, skip in ((["nope"], []), ([], ["nope"])):
            with self.assertRaises(SystemExit) as e:
                check_shards.pick_jobs(jobs, only, skip)
            self.assertIn("no gate job nope", str(e.exception))

    def test_a_job_outside_the_scoped_list_is_left_out_not_refused(self):
        # --modules BRAIN: jobs holds BRAIN's; plocks-p2 is another module's job of the same remix
        jobs = [(n, [], {}, set()) for n in ("set", "mode-defaults", "image")]
        known = {j[0] for j in jobs} | {"plocks-p2"}
        got = {j[0] for j in check_shards.pick_jobs(jobs, ["set", "mode-defaults", "plocks-p2"], [], known)}
        self.assertEqual(got, {"set", "mode-defaults"})
        got = {j[0] for j in check_shards.pick_jobs(jobs, [], ["set", "plocks-p2"], known)}
        self.assertEqual(got, {"mode-defaults", "image"})
        with self.assertRaises(SystemExit):      # a name no job has is still refused
            check_shards.pick_jobs(jobs, [], ["nope"], known)

    def test_extra_units_run_a_script_of_a_module_the_remix_carries(self):
        import reach
        from remix import registry
        for remix, units in reach.SPLIT_EXTRA_UNITS.items():
            for unit, (module, command) in units.items():
                self.assertIn(module, registry.remix(remix).modules, unit)
                script = next(w for w in command.split() if w.endswith(".py"))
                self.assertTrue((ROOT / script).is_file(), unit)
                self.assertIn(script, {g.script for g in registry.by_key(module).gates}, unit)

    def test_octabams_long_share_names_real_jobs(self):
        import reach
        names = {j[0] for j in check_shards.remix_jobs("octabam", ROOT)}
        parts = reach.SPLIT_REMIX_JOBS["octabam"]
        every = [n for jobs in parts.values() for n in jobs]
        self.assertLessEqual(set(every), names)
        self.assertEqual(len(every), len(set(every)))      # no job in two parts


class Split(unittest.TestCase):
    """Which remixes run as gate jobs (check_shards.choose_split)."""

    def test_none_and_named(self):
        self.assertEqual(check_shards.choose_split(["a", "b"], "none", {}, 3), set())
        self.assertEqual(check_shards.choose_split(["a", "b"], "b,zz", {}, 3), {"b"})

    def test_recorded_times_pick_the_long_pole(self):
        times = {"octabam-bus": 780.0, "usb": 140.0, "miniverb": 80.0, "euclid": 130.0}
        self.assertEqual(check_shards.choose_split(list(times), "auto", times, 3), {"octabam-bus"})
        # nothing over 300 s: nothing split
        small = {k: 100.0 for k in times}
        self.assertEqual(check_shards.choose_split(list(small), "auto", small, 3), set())

    def test_without_a_record_nothing_is_split(self):
        got = check_shards.choose_split(["octabam-bus", "usb-midi", "octatrick"], "auto", {}, 3)
        self.assertEqual(got, set())
