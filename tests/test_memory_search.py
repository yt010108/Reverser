import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from reverser_harness.memory import TechniqueMemory
from reverser_harness.storage import ChallengeStore


class MemorySearchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = ChallengeStore(self.root / "runs")
        self.memory = TechniqueMemory(self.root, self.store)

    def tearDown(self):
        self.temp.cleanup()

    def test_search_prefers_most_recently_modified_card(self):
        older = self.memory.techniques_dir / "z-older.md"
        newer = self.memory.techniques_dir / "a-newer.md"
        older.write_text("xor older", encoding="utf-8")
        newer.write_text("xor newer", encoding="utf-8")
        os.utime(older, ns=(1_000_000_000, 1_000_000_000))
        os.utime(newer, ns=(2_000_000_000, 2_000_000_000))

        results = self.memory.search("xor", limit=2)

        self.assertEqual([item["path"] for item in results], ["a-newer.md", "z-older.md"])

    def test_solution_search_records_actual_search_time(self):
        state = self.store.create(title="Search Time", platform_url="")
        state["status"] = "unsolved"
        self.store.save(state)

        with patch("reverser_harness.memory.utc_now", return_value="2026-09-04T12:34:56+00:00"):
            self.memory.search_for_challenge(state["challenge_id"], "xor", 1800, 5)

        saved = self.store.load(state["challenge_id"])
        self.assertEqual(saved["solution_searches"][-1]["time"], "2026-09-04T12:34:56+00:00")
        self.assertEqual(saved["solution_searches"][-1]["query"], "xor")


if __name__ == "__main__":
    unittest.main()
