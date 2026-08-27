import tempfile
import unittest
from pathlib import Path

from reverser_harness.dashboard import build_dashboard
from reverser_harness.storage import ChallengeStore


class DashboardTests(unittest.TestCase):
    def test_single_html_dashboard_does_not_expose_flags(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = ChallengeStore(root / "runs")
            state = store.create(title="Dashboard", platform_url="")
            flag = "TEST" + "{private}"
            state["flags"] = [flag]
            store.save(state)

            dashboard = build_dashboard(store)
            text = dashboard.read_text(encoding="utf-8")
            self.assertEqual(dashboard.parent, store.root)
            self.assertIn("Dashboard", text)
            self.assertIn("1", text)
            self.assertNotIn(flag, text)


if __name__ == "__main__":
    unittest.main()
