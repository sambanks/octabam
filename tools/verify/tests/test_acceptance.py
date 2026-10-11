"""Failure-path tests use tiny subprocesses, not proprietary firmware."""
import contextlib
import io
import json
import os
import pathlib
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import acceptance as a



TYPES = {"object": dict, "array": list, "string": str, "boolean": bool,
         "integer": int, "number": (int, float), "null": type(None)}


def schema_errors(v, s, root, at="$"):
    """Every violation of the JSON Schema subset acceptance.schema.json uses
    (type, const, enum, required, properties, items, minItems, minimum,
    $ref, allOf, if/then), stdlib only."""
    if "$ref" in s:
        s = root["$defs"][s["$ref"].rsplit("/", 1)[1]]
    errs = []
    if "type" in s:
        want = s["type"] if isinstance(s["type"], list) else [s["type"]]
        if not any(isinstance(v, TYPES[w]) and not (w in ("integer", "number") and isinstance(v, bool))
                   for w in want):
            return [f"{at}: {type(v).__name__}, want {s['type']}"]
    if "const" in s and v != s["const"]:
        errs.append(f"{at}: {v!r}, want {s['const']!r}")
    if "enum" in s and v not in s["enum"]:
        errs.append(f"{at}: {v!r} not in {s['enum']}")
    if "minimum" in s and v < s["minimum"]:
        errs.append(f"{at}: {v} < {s['minimum']}")
    if isinstance(v, dict):
        errs += [f"{at}: no {k!r}" for k in s.get("required", ()) if k not in v]
        for k, sub in s.get("properties", {}).items():
            if k in v:
                errs += schema_errors(v[k], sub, root, f"{at}.{k}")
    if isinstance(v, list):
        if len(v) < s.get("minItems", 0):
            errs.append(f"{at}: {len(v)} items < {s['minItems']}")
        if "items" in s:
            for i, x in enumerate(v):
                errs += schema_errors(x, s["items"], root, f"{at}[{i}]")
    for sub in s.get("allOf", ()):
        errs += schema_errors(v, sub, root, at)
    if "if" in s and not schema_errors(v, s["if"], root, at):
        errs += schema_errors(v, s.get("then", {}), root, at)
    return errs


class SourcePressureTests(unittest.TestCase):
    def test_cf_registered_dsp_cannot_report_not_applicable(self):
        source = SimpleNamespace(key="SOURCE", dsp=None,
                                 pressure_blocker="source load needs separate metering")
        status, reason = a.pressure_profile([source])
        self.assertEqual(status, "blocked")
        self.assertIn("SOURCE", reason)
        self.assertIn("separate metering", reason)

    def test_plain_cf_remains_not_applicable(self):
        self.assertEqual(a.pressure_profile([SimpleNamespace(key="CF", dsp=None)])[0],
                         "not_applicable")


class GateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.out = pathlib.Path(self.tmp.name)

    def run_child(self, code, timeout=5):
        with contextlib.redirect_stdout(io.StringIO()):
            return a.run_gate("probe", [sys.executable, "-c", code],
                              self.out, dict(os.environ), timeout)

    def test_skip_with_zero_exit_blocks(self):
        result = self.run_child("print('  [SKIP] missing emulator')")
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["skips"], ["[SKIP] missing emulator"])

    def test_run_gate_runs_in_the_given_tree(self):
        with contextlib.redirect_stdout(io.StringIO()):
            a.run_gate("probe", [sys.executable, "-c", "import os; print(os.getcwd())"],
                       self.out, dict(os.environ), 5, cwd=self.out)
        self.assertEqual((self.out / "probe.stdout").read_text().strip(), str(self.out.resolve()))

    def test_stderr_skip_also_blocks(self):
        result = self.run_child("import sys; print('SKIP: missing project', file=sys.stderr)")
        self.assertEqual(result["status"], "blocked")

    def test_not_applicable_is_explicit_and_allowed(self):
        result = self.run_child("print('[N/A] no DRAM code'); print('[PASS] audio')")
        self.assertEqual(result["status"], "passed")
        self.assertEqual(len(result["not_applicable"]), 1)

    def test_summary_mentioning_skip_is_not_a_skipped_check(self):
        result = self.run_child("print('all runnable checks passed (a [SKIP] line names omissions)')")
        self.assertEqual(result["status"], "passed")

    def test_failure_marker_cannot_hide_behind_zero_exit(self):
        self.assertEqual(self.run_child("print('[FAIL] memory guard')")["status"], "failed")

    def test_nonzero_exit_overrides_skip(self):
        result = self.run_child("print('[SKIP] optional'); raise SystemExit(7)")
        self.assertEqual((result["status"], result["exit_code"]), ("failed", 7))

    def test_timeout_is_not_a_pass(self):
        result = self.run_child("import time; time.sleep(30)", timeout=0.1)
        self.assertEqual(result["status"], "failed")
        self.assertIn("timed out", result["reason"])

    def test_missing_executable_is_reported(self):
        with contextlib.redirect_stdout(io.StringIO()):
            result = a.run_gate("absent", [str(self.out / "nonexistent")],
                                self.out, dict(os.environ), 5)
        self.assertEqual(result["status"], "failed")
        self.assertIsNone(result["exit_code"])

    def test_json_stdout_is_separate_from_diagnostics(self):
        code = "import sys, json; print(json.dumps(dict(worst_core=100))); print('diagnostic', file=sys.stderr)"
        result = self.run_child(code)
        self.assertEqual(json.loads((self.out / result["stdout"]).read_text())["worst_core"], 100)
        self.assertIn("diagnostic", (self.out / result["log"]).read_text())

    def test_budget_rejects_overrun(self):
        self.assertEqual(a.budget_result(dict(worst_core=3121, usable=3120)), "failed")
        self.assertEqual(a.budget_result(dict(worst_core=3120, usable=3120)), "passed")
        with self.assertRaises(ValueError):
            a.budget_result(dict(worst_core=1))
        with self.assertRaises(ValueError):
            a.budget_result(dict(worst_core=1, usable=0))

    def test_unrun_checks_cannot_be_accepted(self):
        self.assertEqual(a.aggregate([dict(status="passed"), dict(status="not_run")]), "blocked")
        self.assertEqual(a.aggregate([dict(status="blocked"), dict(status="failed")]), "failed")
        self.assertEqual(a.aggregate([dict(status="passed"), dict(status="not_applicable")]), "passed")

    def test_module_without_dear_settings_blocks_instead_of_using_defaults(self):
        known = SimpleNamespace(key="KNOWN", dsp=object(), params=(1,), dear={"MIX": 127})
        new = SimpleNamespace(key="NEW EFFECT", dsp=object(), params=(1,), dear={})
        status, reason = a.pressure_profile([known, new])
        self.assertEqual(status, "blocked")
        self.assertIn("NEW EFFECT", reason)
        self.assertNotIn("KNOWN", reason)
        status, _ = a.pressure_profile([known])
        self.assertEqual(status, "ready")
        status, _ = a.pressure_profile([SimpleNamespace(key="CF PATCH", dsp=None)])
        self.assertEqual(status, "not_applicable")
        # a DSP section with no chooser row (a hook-only inject) is not an effect
        status, _ = a.pressure_profile([SimpleNamespace(key="USB AUDIO IN", dsp=object(), menu=None, params=(), dear={})])
        self.assertEqual(status, "not_applicable")

    def test_missing_prerequisites_produce_partial_json_and_nonzero_exit(self):
        out = self.out / "run"
        with patch.object(a, "ROOT", self.out), patch.object(a, "provenance", return_value={}), \
                patch.object(a.registry, "remix", return_value=object()), \
                patch.object(a.registry, "selected", return_value=[]), \
                patch.dict(os.environ, {}, clear=True), contextlib.redirect_stdout(io.StringIO()):
            rc = a.main(["--remix", "test", "--out", str(out)])
        report = json.loads((out / "report.json").read_text())
        self.assertEqual(rc, 1)
        self.assertEqual(report["status"], "blocked")
        self.assertFalse(report["hardware_validated"])
        self.assertEqual(report["gates"][0]["status"], "blocked")
        self.assertTrue(all(g["status"] == "not_run" for g in report["gates"][1:]))

    def test_existing_report_directory_cannot_be_reused(self):
        marker = self.out / "report.json"
        marker.write_text("old evidence")
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            a.main(["--out", str(self.out)])
        self.assertEqual(marker.read_text(), "old evidence")

    def test_missing_pressure_meter_is_not_evidence(self):
        price = dict(cores={"core 0 (T5-8)": {"layouts": 1}, "core 1 (T1-4)": {"layouts": 1}})
        rows = [dict(core=c, rc=0, flags=[], meter={str(c): [1600, 100]}) for c in (0, 1)]
        self.assertIsNone(a.pressure_evidence_error(rows, price))
        rows[0]["meter"] = {}
        self.assertIn("meter", a.pressure_evidence_error(rows, price))
        self.assertIn("incomplete", a.pressure_evidence_error(rows[1:], price))

    def test_pass_is_not_published_until_report_is_final(self):
        report = dict(gates=[dict(name="last", status="passed")])
        a.write_report(self.out, report)
        self.assertEqual(json.loads((self.out / "report.json").read_text())["status"], "running")
        report["finished_at"] = "2026-01-01T00:00:00+00:00"
        a.write_report(self.out, report)
        self.assertEqual(json.loads((self.out / "report.json").read_text())["status"], "passed")

    def test_external_project_audio_and_metadata_are_fingerprinted(self):
        project = self.out / "project"
        project.mkdir()
        (project / "project.work").write_text(
            "[SAMPLE]\nTYPE=FLEX\nSLOT=001\nPATH=../sample.wav\n[/SAMPLE]\n")
        sample = self.out / "sample.wav"
        metadata = self.out / "sample.ot"
        sample.write_bytes(b"first fixture")
        metadata.write_bytes(b"sample metadata")
        first = a.sample_inventory(project)
        self.assertEqual(first["../sample.wav"]["metadata_sha256"], a.sha256(metadata))
        sample.write_bytes(b"changed fixture")
        self.assertNotEqual(first, a.sample_inventory(project))
        sample.unlink()
        self.assertIsNone(a.sample_inventory(project)["../sample.wav"]["sha256"])

    def test_generated_audio_is_repeatable_stereo_and_nonzero(self):
        import wave
        from stress_project import make_sample
        first, second = self.out / "a.wav", self.out / "b.wav"
        make_sample(first)
        make_sample(second)
        self.assertEqual(a.sha256(first), a.sha256(second))
        with wave.open(str(first)) as wav:
            self.assertEqual((wav.getnchannels(), wav.getframerate(), wav.getnframes()),
                             (2, 44100, 88200))
            self.assertTrue(any(wav.readframes(88200)))

class WorkflowTests(unittest.TestCase):
    """Exercise the orchestration without an OS image or emulator."""
    def run_workflow(self, stop_at=None, over=False, empty_render=False, remixes=("test",), blocked=False,
                     profile=None, stress=False):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp).resolve()   # macOS: /var is /private/var; the runner resolves
            project = root / "project"
            project.mkdir()
            (project / "project.work").write_text("private fixture")
            (project / "bank01.work").write_text("private bank")
            for rel in ("out/raw/section_3_MAIN_OS.bin", "out/emu/ot_emu",
                        ".venv/bin/python3", "out/mainos_bus.bin"):
                p = root / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text("synthetic test input")
            calls = []
            unique = list(dict.fromkeys(remixes))

            def gate(name, command, out, env, timeout):
                calls.append((name, env["REMIX"]))
                self.assertNotIn("MAKEFLAGS", env)
                if name == "check_shared":
                    self.assertEqual(env["REMIXES"], " ".join(unique))
                    self.assertIn(f"REMIXES={' '.join(unique)}", command)
                else:
                    self.assertEqual(env["OT_PROJECT"], str(project))
                if name == "check_remix":
                    self.assertIn(f"REMIX={env['REMIX']}", command)
                if name == "cycles":
                    (out / "cycles.stdout").write_text(json.dumps(
                        dict(worst_core=3121 if over else 100, usable=3120)))
                if name == "pressure_price":
                    dest = pathlib.Path(command[command.index("--out") + 1])
                    self.assertTrue(dest.is_relative_to(out))
                    dest.mkdir()
                    (dest / f"{env['REMIX']}_price.json").write_text(json.dumps(
                        dict(cores={"core 0 (T5-8)": {"over": 0, "layouts": 1},
                                    "core 1 (T1-4)": {"over": 0, "layouts": 1}})))
                if name == "pressure_render":
                    dest = pathlib.Path(command[command.index("--out") + 1])
                    rows = [] if empty_render else [
                        dict(core=c, rc=0, flags=[], meter={str(c): [1600, 100]})
                        for c in (0, 1)]
                    (dest / f"{env['REMIX']}_render.json").write_text(json.dumps(rows))
                return dict(name=name, status="blocked" if name == stop_at else "passed",
                            exit_code=0, log=name + ".log", stdout=name + ".stdout",
                            skips=["missing fixture"] if name == stop_at else [])

            out = root / "result"
            profile = profile or (("blocked", "no dearest settings") if blocked else ("ready", "test profile"))
            source = ["--stress-source", str(project)] if stress else ["--project", str(project)]
            with patch.object(a, "ROOT", root), patch.object(a, "provenance", return_value={}), \
                    patch.object(a.registry, "remix", return_value=object()), \
                    patch.object(a.registry, "selected", return_value=[]), \
                    patch.object(a, "pressure_profile", return_value=profile), \
                    patch.object(a, "run_gate", side_effect=gate), \
                    patch.dict(os.environ, {"MAKEFLAGS": "-j8"}, clear=True), \
                    contextlib.redirect_stdout(io.StringIO()):
                rc = a.main(["--remix", *remixes, *source, "--out", str(out)])
            if len(unique) == 1:
                return rc, json.loads((out / "report.json").read_text()), calls
            reports = {r: json.loads((out / r / "report.json").read_text()) for r in unique}
            reports["summary"] = json.loads((out / "summary.json").read_text())
            reports["shared_log"] = (out / "check_shared.log").exists() or None
            return rc, reports, calls

    def test_complete_and_blocked_reports_match_the_schema(self):
        schema = json.loads((pathlib.Path(a.__file__).parent / "acceptance.schema.json").read_text())
        for stop in (None, "check_remix"):
            _, report, _ = self.run_workflow(stop_at=stop)
            self.assertEqual(schema_errors(report, schema, schema), [], stop)

    def test_complete_report_contains_measurements_and_fingerprints(self):
        rc, report, calls = self.run_workflow()
        self.assertEqual((rc, report["status"]), (0, "passed"))
        self.assertEqual([c for c, _ in calls],
                         ["check_shared", "check_remix", "cycles", "pressure_price", "pressure_render"])
        self.assertEqual(report["schema_version"], 2)
        self.assertEqual([g["name"] for g in report["gates"]], list(a.GATES))
        self.assertEqual(len(report["fixtures"]["stems"]), 8)
        self.assertEqual(len(report["provenance"]["image_sha256"]), 64)
        self.assertIn("pressure_render", report["measurements"])

    def test_zero_exit_skip_stops_dependent_stages(self):
        rc, report, calls = self.run_workflow(stop_at="check_remix")
        self.assertEqual((rc, report["status"]), (1, "blocked"))
        self.assertEqual([c for c, _ in calls], ["check_shared", "check_remix"])
        self.assertEqual(report["gates"][-1]["status"], "not_run")

    def test_shared_skip_stops_every_remix(self):
        rc, reports, calls = self.run_workflow(stop_at="check_shared", remixes=("one", "two"))
        self.assertEqual(rc, 1)
        self.assertEqual(calls, [("check_shared", "one")])
        for r in ("one", "two"):
            self.assertEqual(reports[r]["status"], "blocked")
            self.assertEqual(reports[r]["gates"][2]["status"], "blocked")
            self.assertEqual(reports[r]["gates"][3]["status"], "not_run")

    def test_cycle_overrun_stops_before_pressure(self):
        rc, report, calls = self.run_workflow(over=True)
        self.assertEqual((rc, report["status"]), (1, "failed"))
        self.assertEqual([c for c, _ in calls], ["check_shared", "check_remix", "cycles"])

    def test_empty_render_cannot_be_accepted(self):
        rc, report, _ = self.run_workflow(empty_render=True)
        self.assertEqual((rc, report["status"]), (1, "failed"))
        self.assertEqual(report["gates"][-1]["status"], "failed")

    def test_several_remixes_share_one_shared_half(self):
        rc, reports, calls = self.run_workflow(remixes=("one", "two"))
        self.assertEqual(rc, 0)
        self.assertEqual(calls, [("check_shared", "one"),
                                 ("check_remix", "one"), ("cycles", "one"), ("pressure_price", "one"), ("pressure_render", "one"),
                                 ("check_remix", "two"), ("cycles", "two"), ("pressure_price", "two"), ("pressure_render", "two")])
        self.assertEqual(reports["summary"], {"one": "passed", "two": "passed"})
        for r in ("one", "two"):
            self.assertEqual(reports[r]["status"], "passed")
            self.assertEqual(reports[r]["remix"], r)
            # the shared gate's log is the one file above both reports
            self.assertEqual(reports[r]["gates"][2]["log"], "../check_shared.log")

    def test_blocked_profile_still_checks_and_blocks_the_pressure_stages(self):
        rc, reports, calls = self.run_workflow(remixes=("one", "two"), blocked=True, stress=True)
        self.assertEqual(rc, 1)
        self.assertEqual(calls, [("check_shared", "one"), ("check_remix", "one"), ("cycles", "one"),
                                 ("check_remix", "two"), ("cycles", "two")])
        self.assertEqual(reports["summary"], {"one": "blocked", "two": "blocked"})
        gates = {g["name"]: g for g in reports["one"]["gates"]}
        self.assertEqual(gates["preflight"]["status"], "passed")
        self.assertEqual(gates["check_remix"]["status"], "passed")
        self.assertEqual((gates["pressure_price"]["status"], gates["pressure_render"]["status"]), ("blocked", "blocked"))
        self.assertIn("no dearest settings", gates["pressure_render"]["reason"])
        # no stress fixture without a profile: the source project as-is
        self.assertIn("source project as-is", gates["fixture"]["reason"])

    def test_no_dsp_module_takes_the_stress_source_as_is(self):
        rc, report, calls = self.run_workflow(profile=("not_applicable", "remix has no DSP modules"), stress=True)
        self.assertEqual((rc, report["status"]), (0, "passed"))
        self.assertEqual([c for c, _ in calls], ["check_shared", "check_remix", "cycles"])
        gates = {g["name"]: g for g in report["gates"]}
        self.assertIn("source project as-is", gates["fixture"]["reason"])
        self.assertEqual(gates["pressure_render"]["status"], "not_applicable")

    def test_repeated_remix_runs_once(self):
        rc, report, calls = self.run_workflow(remixes=("test", "test"))
        self.assertEqual((rc, report["status"]), (0, "passed"))
        self.assertEqual(sum(c == "check_remix" for c, _ in calls), 1)


if __name__ == "__main__":
    unittest.main()
