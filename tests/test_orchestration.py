import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from reverser_harness.analysis import Analyzer
from reverser_harness.docker_backend import CommandResult
from reverser_harness.orchestration import TaskDB
from reverser_harness.storage import ChallengeStore


class OrchestrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db = TaskDB(self.root / "state.sqlite")

    def tearDown(self):
        self.temp.cleanup()

    def test_dependency_claim_restart_and_event_cursor(self):
        self.db.ensure_task("task-one", "문제 해결")
        added = self.db.sync_intents("task-one", [
            {"id": "i1", "summary": "입력 확인", "status": "open"},
            {"id": "i2", "summary": "역산", "status": "open", "parent_id": "i1"},
        ])
        self.assertEqual(added, ["i1", "i2"])
        self.assertEqual(self.db.claim("task-one", "worker-a")["intent_id"], "i1")
        self.assertIsNone(self.db.claim("task-one", "worker-b"))
        self.db.set_intent("task-one", "i1", "done")
        self.assertEqual(self.db.claim("task-one", "worker-b")["intent_id"], "i2")
        self.db.pause_running("task-one")
        self.assertEqual(self.db.intents("task-one")[1]["status"], "paused")
        self.db.reopen_running("task-one")
        self.assertEqual(self.db.claim("task-one", "worker-c")["intent_id"], "i2")
        first = self.db.append("task-one", "plan", "planner", "intent", "입력 확인")
        second = self.db.append("task-one", "intent:i2", "worker", "result", "역산 완료")
        self.assertEqual([item["seq"] for item in self.db.activities("task-one", first)], [second])
        self.db.append("task-one", "system", "system", "hint", "새 힌트", "입력 길이 확인")
        self.assertTrue(self.db.has_unplanned_hint("task-one"))
        self.db.append("task-one", "plan", "planner", "round", "계획 라운드")
        self.assertFalse(self.db.has_unplanned_hint("task-one"))

    def test_candidate_stays_private_until_independent_review(self):
        store = ChallengeStore(self.root / "runs")
        state = store.create(title="검증 문제", platform_url="")
        challenge_id = state["challenge_id"]
        state["status"] = "solving"
        store.save(state)
        intent = store.add_intent(challenge_id, "검사 루틴 확인")

        class Worker:
            def run(self, *, profile, command, **_kwargs):
                return CommandResult(profile, command, 0, "FLAG{trial}", "")

        analyzer = Analyzer(store, Worker())
        analyzer.run_command(challenge_id, "core", "check", intent_id=intent["id"])
        analyzer.check_candidate(challenge_id, "FLAG{trial}", 1, "flag")
        candidate_id = self.db.add_candidate(challenge_id, intent["id"], "flag", "FLAG{trial}", 1)
        self.assertNotIn("value", self.db.candidates(challenge_id)[0])
        self.assertEqual(store.load(challenge_id)["status"], "solving")
        with patch.dict(os.environ, {"REVERSER_ROLE": "verifier", "REVERSER_INTENT_ID": f"v{candidate_id}"}):
            analyzer.review_command(challenge_id, "core", "repeat check")
        self.assertEqual(store.load(challenge_id)["tool_runs"][-1]["intent_id"], f"v{candidate_id}")
        solved = analyzer.record_flag(challenge_id, "FLAG{trial}", 2, "flag")
        self.db.set_candidate(challenge_id, candidate_id, "verified", 2)
        self.assertEqual(solved["status"], "solved")
        self.assertEqual(self.db.candidate(challenge_id, candidate_id)["verify_run"], 2)


if __name__ == "__main__":
    unittest.main()
