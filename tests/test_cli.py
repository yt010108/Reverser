import io
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from reverser_harness.cli import main, parser


class CliTests(unittest.TestCase):
    def test_exec_keeps_action_separate_from_worker_command(self):
        args = parser().parse_args(["exec", "abc-123", "--profile", "core", "--command", "file a"])
        self.assertEqual(args.action, "exec")
        self.assertEqual(args.command, "file a")

    def test_flag_requires_evidence_run(self):
        args = parser().parse_args(
            ["flag", "abc-123", "--value", "flag", "--evidence-run", "7"]
        )
        self.assertEqual(args.evidence_run, 7)

    def test_main_uses_utf8_output(self):
        buffer = io.BytesIO()
        stdout = io.TextIOWrapper(buffer, encoding="cp949")
        with patch("reverser_harness.cli.sys.stdout", stdout), \
             patch("reverser_harness.cli.Settings.load", return_value=SimpleNamespace(research_after_seconds=1800)), \
             patch("reverser_harness.cli.ChallengeStore") as store:
            store.return_value.list.return_value = [{"title": "dash — test", "status": "imported"}]
            self.assertEqual(main(["list"]), 0)
            stdout.flush()
            output = buffer.getvalue().decode("utf-8")
        self.assertIn("—", output)


if __name__ == "__main__":
    unittest.main()
