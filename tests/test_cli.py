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

    def test_hypothesis_parser_keeps_cli_action(self):
        args = parser().parse_args([
            "hypothesis", "abc-123", "propose", "--target", "check_flag",
            "--parent-id", "h1", "--claim", "xor",
        ])
        self.assertEqual(args.action, "hypothesis")
        self.assertEqual(args.hypothesis_action, "propose")
        self.assertEqual(args.target, "check_flag")
        self.assertEqual(args.parent_id, "h1")

    def test_recon_parser_accepts_repeated_evidence_runs(self):
        args = parser().parse_args([
            "recon", "abc-123", "--entry-point", "0x401000", "--evidence-run", "2",
            "--evidence-run", "3", "--candidates-json", "[]",
        ])
        self.assertEqual(args.action, "recon")
        self.assertEqual(args.evidence_run, [2, 3])

    def test_main_uses_utf8_output(self):
        buffer = io.BytesIO()
        stdout = io.TextIOWrapper(buffer, encoding="cp949")
        with patch("reverser_harness.cli.sys.stdout", stdout), \
             patch("reverser_harness.cli.Settings.load", return_value=SimpleNamespace(project_name="Reverser", project_root="C:/Reverser")), \
             patch("reverser_harness.cli.ChallengeStore") as store:
            store.return_value.list.return_value = [{"title": "dash — test", "status": "imported"}]
            self.assertEqual(main(["list"]), 0)
            stdout.flush()
            output = buffer.getvalue().decode("utf-8")
        self.assertIn("—", output)


if __name__ == "__main__":
    unittest.main()
