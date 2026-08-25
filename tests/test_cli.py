import unittest

from ctf_harness.cli import parser


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


if __name__ == "__main__":
    unittest.main()
