"""Demand-loader scenarios bound port concurrency and clean up failed runs."""
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import verify_dlload


class LoaderRunner(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.out = pathlib.Path(tmp.name)
        patch = mock.patch.object(verify_dlload, "OUT", self.out)
        patch.start()
        self.addCleanup(patch.stop)

    def test_concurrency_is_bounded_and_every_scenario_runs(self):
        active = set()
        peak = 0
        processes = []

        def launch(command, **kwargs):
            nonlocal peak
            process = mock.Mock(pid=len(processes) + 1)
            processes.append(process)
            active.add(process.pid)
            peak = max(peak, len(active))
            kwargs["stdout"].write("ended on quit\n")
            polls = 0

            def poll():
                nonlocal polls
                polls += 1
                if polls < 2:
                    return None
                active.discard(process.pid)
                return 0

            process.poll.side_effect = poll
            return process

        with mock.patch.object(verify_dlload.subprocess, "Popen", side_effect=launch), \
                mock.patch.object(verify_dlload.time, "sleep"):
            texts = verify_dlload.run_scenarios({f"case{i}": ["port"] for i in range(5)}, 2, 30)
        self.assertEqual(len(texts), 5)
        self.assertEqual(peak, 2)
        self.assertFalse(active)

    def test_timeout_terminates_every_active_child_and_retains_logs(self):
        processes = [mock.Mock(pid=i, poll=mock.Mock(return_value=None)) for i in (1, 2)]
        with mock.patch.object(verify_dlload.subprocess, "Popen", side_effect=processes), \
                mock.patch.object(verify_dlload.time, "time", side_effect=[0, 0, 2]):
            with self.assertRaisesRegex(RuntimeError, "first timed out"):
                verify_dlload.run_scenarios({"first": ["port"], "second": ["port"]}, 2, 1)
        for process in processes:
            process.terminate.assert_called_once()
            process.wait.assert_called_once_with(timeout=10)
        self.assertTrue((self.out / "first.txt").exists())
        self.assertTrue((self.out / "second.txt").exists())

    def test_failed_scenario_stops_its_active_sibling(self):
        failed = mock.Mock(pid=1, poll=mock.Mock(return_value=1))
        sibling = mock.Mock(pid=2, poll=mock.Mock(return_value=None))
        with mock.patch.object(verify_dlload.subprocess, "Popen", side_effect=[failed, sibling]):
            with self.assertRaisesRegex(RuntimeError, "first run did not finish"):
                verify_dlload.run_scenarios({"first": ["port"], "second": ["port"]}, 2, 30)
        sibling.terminate.assert_called_once()
        sibling.wait.assert_called_once_with(timeout=10)

    def test_interruption_stops_children_already_started(self):
        process = mock.Mock(pid=1, poll=mock.Mock(return_value=None))
        with mock.patch.object(verify_dlload.subprocess, "Popen", side_effect=[process, KeyboardInterrupt]):
            with self.assertRaises(KeyboardInterrupt):
                verify_dlload.run_scenarios({"first": ["port"], "second": ["port"]}, 2, 30)
        process.terminate.assert_called_once()
        process.wait.assert_called_once_with(timeout=10)


if __name__ == "__main__":
    unittest.main()
