import json
import tempfile
import unittest
from pathlib import Path

from reverser_harness.analysis import Analyzer
from reverser_harness.config import Settings
from reverser_harness.docker_backend import CommandResult
from reverser_harness.importer import ChallengeImporter
from reverser_harness.memory import MemoryError, TechniqueMemory
from reverser_harness.storage import ChallengeStore, public_state
from reverser_harness.writeup import WriteupManager


CONFIG = """
[project]
name = "test"
[solve]
research_after_seconds = 1800
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
[memory]
search_limit = 5
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

    def test_local_import_private_state_and_public_projection(self):
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
        self.assertNotIn("flags", projected)
        self.assertEqual(projected["flag_candidates"], 1)

    def test_solution_notes_are_only_for_researched_or_unsolved_challenges(self):
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
        self.assertTrue(memory.search("XOR"))

    def test_solver_json_tracks_running_and_done(self):
        state = self.store.create(title="Tracked", platform_url="")
        running = self.store.start_solver(state["challenge_id"], "term-1")
        self.assertEqual(json.loads(Path(running["path"]).read_text(encoding="utf-8"))["status"], "running")
        with self.assertRaises(RuntimeError):
            self.store.finish_solver(state["challenge_id"])
        state["status"] = "solved"
        self.store.save(state)
        done = self.store.finish_solver(state["challenge_id"])
        self.assertEqual(done["result"], "solved")
        self.assertEqual(done["terminal"], "term-1")

    def test_hypothesis_is_visible_and_gates_verification(self):
        class Worker:
            def run(self, *, profile, command, **_kwargs):
                return CommandResult(profile, command, 0, "verified", "")

        state = self.store.create(title="Hypothesis", platform_url="", event="Event")
        state["status"] = "solving"
        self.store.save(state)
        proposed = self.store.update_hypothesis(
            state["challenge_id"], "propose", claim="input is XORed", test="trace three inputs",
            falsifier="trace differs", exhaustion="all 16 bytes",
        )
        hypothesis_id = proposed["hypothesis"]["id"]
        analyzer = Analyzer(self.store, Worker())
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
        saved = self.store.load(state["challenge_id"])
        self.assertEqual(saved["hypotheses"][0]["status"], "confirmed")
        self.assertEqual(saved["hypotheses"][0]["evidence_runs"], [run])
        progress = (self.store.challenge_dir(state["challenge_id"]) / "progress.md").read_text(encoding="utf-8")
        self.assertIn("## Hypothesis history", progress)
        self.assertIn("input is XORed", progress)

    def test_solution_search_waits_for_budget_or_unsolved_status(self):
        state = self.store.create(title="Search Test", platform_url="")
        state["status"] = "solving"
        state["solve_started_at"] = state["created_at"]
        self.store.save(state)
        memory = TechniqueMemory(self.root, self.store)
        with self.assertRaises(MemoryError):
            memory.search_for_challenge(state["challenge_id"], "xor", 1800, 5)
        state["status"] = "unsolved"
        self.store.save(state)
        self.assertEqual(
            memory.search_for_challenge(state["challenge_id"], "xor", 1800, 5), []
        )

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
        self.assertNotIn("flags", public_state(solved))

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

    def test_writeup_keeps_private_and_redacts_export(self):
        state = self.store.create(title="Writeup Test", platform_url="https://ctf.example/challenge")
        flag = "TEST" + "{private-value}"
        state["flags"].append(flag)
        self.store.save(state)
        paths = WriteupManager(self.root, self.store).save(state["challenge_id"], f"# Solve\n\nFlag: {flag}\n")
        self.assertIn(flag, Path(paths["private"]).read_text(encoding="utf-8"))
        self.assertNotIn(flag, Path(paths["public"]).read_text(encoding="utf-8"))
        metadata = json.loads((Path(paths["export_dir"]) / "metadata.json").read_text(encoding="utf-8"))
        self.assertNotIn("flags", metadata)

    def test_writeup_paths_do_not_collide_for_duplicate_titles(self):
        first = self.store.create(title="Same Title", platform_url="", event="Event")
        second = self.store.create(title="Same Title", platform_url="", event="Event")
        manager = WriteupManager(self.root, self.store)
        first_path = manager.save(first["challenge_id"], "# First")["export_dir"]
        second_path = manager.save(second["challenge_id"], "# Second")["export_dir"]
        self.assertNotEqual(first_path, second_path)
        self.assertEqual(Path(first_path).parent.name, "event")
        self.assertEqual(Path(first_path).name, first["challenge_id"])


if __name__ == "__main__":
    unittest.main()
