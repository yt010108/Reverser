import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from reverser_harness.config import Settings
from reverser_harness.docker_backend import DockerWorker


class DockerBackendTests(unittest.TestCase):
    def test_ghidra_wrapper_reuses_project_and_limits_default_export(self):
        root = Path(__file__).resolve().parents[1]
        wrapper = (root / "docker" / "ghidra" / "reverser-ghidra").read_text(encoding="utf-8")
        script = (root / "docker" / "ghidra" / "ExportDecompile.java").read_text(encoding="utf-8")

        self.assertIn('-process "$program_name" -noanalysis', wrapper)
        self.assertIn("DEFAULT_FUNCTION_LIMIT = 20", script)
        self.assertIn("DECOMPILE_TIMEOUT_SECONDS = 20", script)
        self.assertIn('"--all"', script)

    def test_worker_is_networkless_and_ptrace_is_dynamic_only(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "config.toml").write_text("""
[project]
name="test"
[images]
core="test/core:1"
dynamic="test/dynamic:1"
ghidra="test/ghidra:1"
angr="test/angr:1"
[limits]
timeout_seconds=60
memory="1g"
cpus="1"
pids=64
max_output_bytes=65536
""", encoding="utf-8")
            challenge = root / "challenge"
            for name in ("original", "work", "output"):
                (challenge / name).mkdir(parents=True)
            calls = []
            def fake_run(command, **kwargs):
                calls.append(command)
                return subprocess.CompletedProcess(command, 0, "ok", "")
            with patch("reverser_harness.docker_backend.shutil.which", return_value="docker"), patch("reverser_harness.docker_backend.subprocess.run", side_effect=fake_run):
                worker = DockerWorker(Settings.load(root))
                worker.run(profile="core", challenge_dir=challenge, command="file /challenge/input/a")
                core = calls[-1]
                self.assertIn("none", core)
                self.assertIn("ALL", core)
                self.assertNotIn("SYS_PTRACE", core)
                worker.run(profile="dynamic", challenge_dir=challenge, command="gdb --version")
                dynamic = calls[-1]
                self.assertIn("SYS_PTRACE", dynamic)
                self.assertIn("seccomp=unconfined", dynamic)


if __name__ == "__main__":
    unittest.main()
