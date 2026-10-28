import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from reverser_harness.config import Settings
from reverser_harness.docker_backend import DockerWorker


PROJECT_ROOT = Path(__file__).resolve().parent.parent


@unittest.skipUnless(
    os.environ.get("REVERSER_DOCKER_INTEGRATION") == "1",
    "set REVERSER_DOCKER_INTEGRATION=1 to exercise the local Docker image",
)
class DockerIntegrationTests(unittest.TestCase):
    def test_intent_workspace_and_verifier_shared_readonly(self):
        with tempfile.TemporaryDirectory() as temporary:
            challenge = Path(temporary) / "challenge"
            for name in ("original", "work", "output"):
                (challenge / name).mkdir(parents=True)
            (challenge / "work" / "intents" / "i1").mkdir(parents=True)
            (challenge / "work" / "intents" / "i1" / "proof.txt").write_text("sample", encoding="utf-8")
            worker = DockerWorker(Settings.load(PROJECT_ROOT))
            with patch.dict(os.environ, {"REVERSER_ROLE": "worker", "REVERSER_INTENT_ID": "i1"}):
                result = worker.run(profile="core", challenge_dir=challenge,
                    command="cat /challenge/work/proof.txt; test ! -e /challenge/shared", timeout_seconds=30)
            self.assertEqual(result.exit_code, 0, result.stderr)
            self.assertIn("sample", result.stdout)
            with patch.dict(os.environ, {"REVERSER_ROLE": "verifier", "REVERSER_INTENT_ID": "v1"}):
                review = worker.run(profile="core", challenge_dir=challenge,
                    command="cat /challenge/shared/intents/i1/proof.txt; ! sh -c 'printf x >> /challenge/shared/intents/i1/proof.txt'", timeout_seconds=30)
            self.assertEqual(review.exit_code, 0, review.stderr)
            self.assertIn("sample", review.stdout)

    def test_angr_worker_imports(self):
        with tempfile.TemporaryDirectory() as temporary:
            challenge = Path(temporary) / "challenge"
            for name in ("original", "work", "output"):
                (challenge / name).mkdir(parents=True)
            worker = DockerWorker(Settings.load(PROJECT_ROOT))
            result = worker.run(
                profile="angr",
                challenge_dir=challenge,
                command="python -c 'import angr; print(angr.__version__)'",
                timeout_seconds=60,
            )
            self.assertEqual(result.exit_code, 0, result.stderr)
            self.assertIn("9.2.213", result.stdout)

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
