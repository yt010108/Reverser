import json
import tempfile
import unittest
from pathlib import Path

from reverser_harness.analysis import Analyzer
from reverser_harness.cli import catalog
from reverser_harness.config import Settings
from reverser_harness.docker_backend import CommandResult
from reverser_harness.importer import ChallengeImporter
from reverser_harness.memory import MemoryError, TechniqueMemory
from reverser_harness.storage import ChallengeStore, public_state
from reverser_harness.writeup import WriteupManager


CONFIG = """
[project]
name = "test"
[images]
core = "test/core:1"
dynamic = "test/dynamic:1"
ghidra = "test/ghidra:1"
angr = "test/angr:1"
[limits]
timeout_seconds = 60
memory = "1g"
cpus = "1"
pids = 64
max_output_bytes = 65536
"""


CARD = """---
title: "XOR loop recognition"
category: "reverse"
preconditions: "A byte-wise loop"
signals: "Repeated xor and compare"
procedure: "Extract constants and invert the loop"
failure_modes: "Stateful or index-dependent transforms"
confidence: "medium"
---

Check all loop bounds and verify the recovered input in a clean worker.
"""


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "config.toml").write_text(CONFIG, encoding="utf-8")
        self.settings = Settings.load(self.root)
        self.store = ChallengeStore(self.root / "runs")

    def tearDown(self):
        self.temp.cleanup()

    def test_local_import_state(self):
        sample = self.root / "sample.bin"
        sample.write_bytes(b"\x7fELFtest")
        state = ChallengeImporter(self.store).import_local(title="Rev One", files=[sample])
        self.assertEqual(state["status"], "imported")
        run_dir = self.store.challenge_dir(state["challenge_id"])
        self.assertTrue((run_dir / "original" / "sample.bin").is_file())
        self.assertTrue((run_dir / "progress.md").is_file())
        self.assertFalse((run_dir / "state.json").exists())
        self.assertFalse((run_dir / "events.jsonl").exists())
        state["flags"] = ["SECRET"]
        projected = public_state(state)
        self.assertEqual(projected["flags"], ["SECRET"])

    def test_solution_notes_are_only_for_unsolved_challenges(self):
        state = self.store.create(title="Memory Test", platform_url="")
        memory = TechniqueMemory(self.root, self.store)
        with self.assertRaises(MemoryError):
            memory.save_lesson(state["challenge_id"], CARD)
        state["status"] = "unsolved"
        self.store.save(state)
        with self.assertRaises(MemoryError):
            memory.save_lesson(state["challenge_id"], CARD + "\n" + "TEST" + "{private}")
        destination = memory.save_lesson(
            state["challenge_id"], "# Faster XOR\n\nUse a short Z3 model first.\n"
        )
        self.assertTrue(destination.is_file())

    def test_solver_json_tracks_running_and_done(self):
        state = self.store.create(title="Tracked", platform_url="")
        running = self.store.start_solver(state["challenge_id"], "term-1")
        self.assertEqual(json.loads(Path(running["path"]).read_text(encoding="utf-8"))["status"], "running")
        with self.assertRaises(RuntimeError):
            self.store.start_solver(state["challenge_id"], "term-2")
        with self.assertRaises(RuntimeError):
            self.store.finish_solver(state["challenge_id"])
        state["status"] = "solved"
        self.store.save(state)
        done = self.store.finish_solver(state["challenge_id"])
        self.assertEqual(done["result"], "solved")
        self.assertEqual(done["terminal"], "term-1")

    def test_at_most_two_solvers_can_run(self):
        states = [self.store.create(title=f"Solver {index}", platform_url="") for index in range(3)]
        self.store.start_solver(states[0]["challenge_id"], "term-1")
        self.store.start_solver(states[1]["challenge_id"], "term-2")
        with self.assertRaises(RuntimeError):
            self.store.start_solver(states[2]["challenge_id"], "term-3")
        states[0]["status"] = "failed"
        self.store.save(states[0])
        self.store.finish_solver(states[0]["challenge_id"])
        self.store.start_solver(states[2]["challenge_id"], "term-3")

    def test_reviewer_json_requires_saved_report(self):
        state = self.store.create(title="Reviewed", platform_url="")
        state["status"] = "solved"
        self.store.save(state)
        self.store.start_reviewer(state["challenge_id"], "term-1")
        with self.assertRaises(RuntimeError):
            self.store.start_reviewer(state["challenge_id"], "term-2")
        with self.assertRaises(RuntimeError):
            self.store.finish_reviewer(state["challenge_id"])
        path = WriteupManager(self.store).save(state["challenge_id"], "# Solve")["path"]
        self.assertEqual(Path(path).name, "writeup.md")
        done = self.store.finish_reviewer(state["challenge_id"])
        self.assertEqual(done["result"], "writeup.md")

    def test_catalog_lists_project_events_and_challenges(self):
        state = self.store.create(title="Catalog", platform_url="", event="CTF 2026")
        result = catalog(self.store, self.settings)
        self.assertEqual(result["project"]["name"], "test")
        self.assertEqual(result["events"], ["CTF 2026"])
        self.assertEqual(result["challenges"][0]["challenge_id"], state["challenge_id"])

    def test_hypothesis_is_visible_and_gates_verification(self):
        class Worker:
            def run(self, *, profile, command, **_kwargs):
                return CommandResult(profile, command, 0, "verified", "")

        state = self.store.create(title="Hypothesis", platform_url="", event="Event")
        state["status"] = "solving"
        self.store.save(state)
        analyzer = Analyzer(self.store, Worker())
        with self.assertRaises(RuntimeError):
            self.store.update_hypothesis(
                state["challenge_id"], "propose", target="check_flag", claim="input is XORed",
                test="trace three inputs", falsifier="trace differs", exhaustion="all 16 bytes",
            )
        updated, _ = analyzer.run_command(state["challenge_id"], "core", "inspect entry point")
        recon_run = updated["tool_runs"][-1]["sequence"]
        self.store.update_recon(
            state["challenge_id"], entry_point="0x401000", main="0x401120",
            evidence_runs=[recon_run], flag_candidates=[{
                "target": "check_flag", "reason": "called before success string",
                "evidence_runs": [recon_run],
            }],
        )
        with self.assertRaises(RuntimeError):
            analyzer.run_command(state["challenge_id"], "core", "keep exploring")
        with self.assertRaises(RuntimeError):
            self.store.update_hypothesis(
                state["challenge_id"], "propose", target="unknown", claim="input is XORed",
                test="trace three inputs", falsifier="trace differs", exhaustion="all 16 bytes",
            )
        proposed = self.store.update_hypothesis(
            state["challenge_id"], "propose", target="check_flag",
            claim="input is XORed", test="trace three inputs",
            falsifier="trace differs", exhaustion="all 16 bytes",
        )
        hypothesis_id = proposed["hypothesis"]["id"]
        with self.assertRaises(RuntimeError):
            analyzer.run_command(state["challenge_id"], "dynamic", "trace")
        updated, _ = analyzer.run_command(
            state["challenge_id"], "dynamic", "trace", hypothesis_id=hypothesis_id
        )
        run = updated["tool_runs"][-1]["sequence"]
        self.store.update_hypothesis(
            state["challenge_id"], "resolve", hypothesis_id=hypothesis_id,
            outcome="confirmed", evidence_run=run, observation="trace matched",
        )
        sibling = self.store.update_hypothesis(
            state["challenge_id"], "propose", target="check_flag",
            claim="input is added", test="trace addition",
            falsifier="no addition", exhaustion="all 16 bytes",
        )["hypothesis"]
        sibling_state, _ = analyzer.run_command(
            state["challenge_id"], "dynamic", "trace addition", hypothesis_id=sibling["id"]
        )
        self.store.update_hypothesis(
            state["challenge_id"], "resolve", hypothesis_id=sibling["id"], outcome="rejected",
            evidence_run=sibling_state["tool_runs"][-1]["sequence"], observation="no addition",
        )
        child = self.store.update_hypothesis(
            state["challenge_id"], "propose", target="check_flag", parent_id=hypothesis_id,
            claim="XOR key is repeated", test="compare key positions",
            falsifier="positions differ", exhaustion="all 16 positions",
        )["hypothesis"]
        saved = self.store.load(state["challenge_id"])
        self.assertEqual(saved["hypotheses"][0]["status"], "confirmed")
        self.assertEqual(saved["hypotheses"][0]["evidence_runs"], [run])
        self.assertEqual(child["parent_id"], hypothesis_id)
        progress = (self.store.challenge_dir(state["challenge_id"]) / "progress.md").read_text(encoding="utf-8")
        self.assertIn("## Recon", progress)
        self.assertIn("## Hypothesis tree", progress)
        self.assertIn("input is XORed", progress)
        self.assertLess(progress.index("  - `h3`"), progress.index("- `h2`"))

    def test_exec_needs_triage_but_no_user_approval(self):
        class Worker:
            def run(self, *, profile, command, **_kwargs):
                return CommandResult(profile, command, 0, "ok", "")

        state = self.store.create(title="Direct Solve", platform_url="")
        analyzer = Analyzer(self.store, Worker())
        with self.assertRaises(RuntimeError):
            analyzer.run_command(state["challenge_id"], "core", "strings sample")
        state["status"] = "solving"
        state["solve_started_at"] = state["created_at"]
        self.store.save(state)
        updated, result = analyzer.run_command(
            state["challenge_id"], "core", "strings sample"
        )
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(updated["status"], "solving")

    def test_failed_analysis_command_does_not_fail_challenge(self):
        class Worker:
            def run(self, *, profile, command, **_kwargs):
                return CommandResult(profile, command, 1, "", "not found")

        state = self.store.create(title="Retryable", platform_url="")
        state["status"] = "solving"
        self.store.save(state)
        updated, result = Analyzer(self.store, Worker()).run_command(
            state["challenge_id"], "core", "strings missing"
        )
        self.assertEqual(result.exit_code, 1)
        self.assertEqual(updated["status"], "solving")
        self.assertEqual(updated["tool_runs"][-1]["exit_code"], 1)

    def test_flag_requires_successful_run_containing_candidate(self):
        flag = "TEST" + "{verified}"

        class Worker:
            def __init__(self, result):
                self.result = result

            def run(self, **_kwargs):
                return self.result

        state = self.store.create(title="Gate", platform_url="")
        state["status"] = "solving"
        self.store.save(state)
        analyzer = Analyzer(
            self.store, Worker(CommandResult("core", "check", 0, "wrong", ""))
        )
        analyzer.run_command(state["challenge_id"], "core", "check")
        with self.assertRaises(RuntimeError):
            analyzer.record_flag(state["challenge_id"], flag, 1)
        unchanged = self.store.load(state["challenge_id"])
        self.assertEqual(unchanged["status"], "solving")
        self.assertNotIn(flag, unchanged["flags"])

        analyzer.worker = Worker(CommandResult("core", "verify", 0, flag, ""))
        analyzer.run_command(state["challenge_id"], "core", "verify")
        solved = analyzer.record_flag(state["challenge_id"], flag, 2)
        self.assertEqual(solved["status"], "solved")
        self.assertIn(flag, public_state(solved)["flags"])
        self.assertEqual(solved["flag_evidence"], [{"flag": flag, "evidence_run": 2}])

    def test_failed_terminal_state_records_reason(self):
        state = self.store.create(title="Failed", platform_url="")
        state["status"] = "solving"
        self.store.save(state)
        updated = Analyzer(self.store, object()).terminate(
            state["challenge_id"], "agent_exited_without_terminal_state"
        )
        self.assertEqual(updated["status"], "failed")
        self.assertEqual(updated["exit_reason"], "agent_exited_without_terminal_state")

    def test_terminate_preserves_completed_challenge_status(self):
        for status in ("solved", "unsolved"):
            with self.subTest(status=status):
                state = self.store.create(title=f"Completed {status}", platform_url="")
                state["status"] = status
                state["finished_at"] = state["created_at"]
                self.store.save(state)
                updated = Analyzer(self.store, object()).terminate(
                    state["challenge_id"], "agent_process_error"
                )
                self.assertEqual(updated["status"], status)
                self.assertEqual(updated["exit_reason"], "agent_process_error")

    def test_writeup_stays_inside_runs(self):
        state = self.store.create(title="Writeup Test", platform_url="https://ctf.example/challenge")
        flag = "TEST" + "{private-value}"
        state["flags"].append(flag)
        state["status"] = "solved"
        self.store.save(state)
        path = Path(WriteupManager(self.store).save(state["challenge_id"], f"# Solve\n\nFlag: {flag}\n")["path"])
        self.assertIn(flag, path.read_text(encoding="utf-8"))
        self.assertEqual(path, self.store.challenge_dir(state["challenge_id"]) / "reports" / "writeup.md")
        self.assertFalse((self.root / "writeups").exists())

    def test_unsolved_reviewer_writes_review(self):
        state = self.store.create(title="Unsolved", platform_url="", event="Event")
        state["status"] = "unsolved"
        self.store.save(state)
        path = WriteupManager(self.store).save(state["challenge_id"], "# Blocker")["path"]
        self.assertEqual(Path(path).name, "review.md")


if __name__ == "__main__":
    unittest.main()
