import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from reverser_harness.config import Settings
from reverser_harness.docker_backend import DockerWorker


PROJECT_ROOT = Path(__file__).resolve().parent.parent


@unittest.skipUnless(
    os.environ.get("HERMES_DOCKER_INTEGRATION") == "1",
    "set HERMES_DOCKER_INTEGRATION=1 to exercise the local Docker image",
)
class DockerIntegrationTests(unittest.TestCase):
    def test_core_worker_mounts_and_triages_amd64_elf(self):
        with tempfile.TemporaryDirectory() as temporary:
            challenge = Path(temporary) / "challenge"
            for name in ("original", "work", "output"):
                (challenge / name).mkdir(parents=True)
            worker = DockerWorker(Settings.load(PROJECT_ROOT))
            created = worker.run(
                profile="core",
                challenge_dir=challenge,
                command="cp /bin/true /challenge/work/true",
                timeout_seconds=60,
            )
            self.assertEqual(created.exit_code, 0, created.stderr)
            shutil.copyfile(challenge / "work" / "true", challenge / "original" / "true")
            result = worker.run(
                profile="core",
                challenge_dir=challenge,
                command="reverser-triage /challenge/input /challenge/output/triage.json",
                timeout_seconds=120,
            )
            self.assertEqual(result.exit_code, 0, result.stderr)
            report = json.loads((challenge / "output" / "triage.json").read_text(encoding="utf-8"))
            self.assertEqual(report["files"][0]["format"], "elf")
            self.assertEqual(report["files"][0]["architecture"], "amd64")


if __name__ == "__main__":
    unittest.main()
