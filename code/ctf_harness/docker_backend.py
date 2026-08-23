"""Locked, ephemeral Docker workers for CTF reversing."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path

from .config import Settings
from .models import PROFILES


class BackendError(RuntimeError):
    """Raised when a worker cannot be started safely."""


@dataclass(slots=True)
class CommandResult:
    profile: str
    command: str
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False
    truncated: bool = False


class DockerWorker:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.docker = shutil.which("docker")
        if not self.docker:
            raise BackendError("docker was not found on PATH")

    def doctor(self) -> dict[str, object]:
        profiles: dict[str, dict[str, object]] = {}
        for profile, image in self.settings.images.items():
            result = subprocess.run(
                [self.docker, "image", "inspect", image],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=20,
                check=False,
            )
            profiles[profile] = {
                "image": image,
                "available": result.returncode == 0,
                "error": result.stderr.strip() if result.returncode else "",
            }
        return {
            "docker": self.docker,
            "mode": "ephemeral-worker-per-command",
            "profiles": profiles,
            "core_ready": bool(profiles["core"]["available"]),
        }

    def run(
        self,
        *,
        profile: str,
        challenge_dir: Path,
        command: str,
        timeout_seconds: int | None = None,
        environment: dict[str, str] | None = None,
    ) -> CommandResult:
        if profile not in PROFILES:
            raise BackendError(f"Unknown worker profile: {profile}")
        if not command.strip() or "\x00" in command or len(command) > 32_768:
            raise BackendError("Invalid worker command")
        image = self.settings.images[profile]
        inspect = subprocess.run(
            [self.docker, "image", "inspect", image],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
            check=False,
        )
        if inspect.returncode != 0:
            raise BackendError(f"Worker image is unavailable: {image}")

        root = challenge_dir.resolve()
        original = (root / "original").resolve()
        work = (root / "work").resolve()
        output = (root / "output").resolve()
        if any(root not in path.parents for path in (original, work, output)):
            raise BackendError("Challenge workspace escapes its root")
        for path in (original, work, output):
            path.mkdir(parents=True, exist_ok=True)

        timeout = max(1, min(7200, timeout_seconds or self.settings.timeout_seconds))
        name = f"hermes-ctf-{profile}-{uuid.uuid4().hex[:12]}"
        docker_command = [
            self.docker,
            "run",
            "--rm",
            "--name",
            name,
            "--pull=never",
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges:true",
            "--pids-limit",
            str(self.settings.pids),
            "--memory",
            self.settings.memory,
            "--cpus",
            self.settings.cpus,
            "--tmpfs",
            "/tmp:rw,exec,size=1g,mode=1777",
            "--tmpfs",
            "/home/analyst:rw,exec,size=256m,mode=0700,uid=10001,gid=10001",
            "--mount",
            f"type=bind,source={original},target=/challenge/input,readonly",
            "--mount",
            f"type=bind,source={work},target=/challenge/work",
            "--mount",
            f"type=bind,source={output},target=/challenge/output",
            "--workdir",
            "/challenge/work",
        ]
        if profile == "dynamic":
            docker_command.extend(
                [
                    "--cap-add",
                    "SYS_PTRACE",
                    "--security-opt",
                    "seccomp=unconfined",
                ]
            )
        for key, value in (environment or {}).items():
            if not re.fullmatch(r"[A-Z_][A-Z0-9_]*", key) or "\x00" in value:
                raise BackendError(f"Invalid worker environment variable: {key}")
            docker_command.extend(["-e", f"{key}={value}"])
        docker_command.extend(
            [image, "timeout", "--signal=TERM", f"{timeout}s", "bash", "-c", command]
        )
        try:
            completed = subprocess.run(
                docker_command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout + 30,
                check=False,
                env=os.environ.copy(),
            )
            stdout, stdout_cut = self._clip(completed.stdout)
            stderr, stderr_cut = self._clip(completed.stderr)
            return CommandResult(
                profile=profile,
                command=command,
                exit_code=completed.returncode,
                stdout=stdout,
                stderr=stderr,
                timed_out=completed.returncode == 124,
                truncated=stdout_cut or stderr_cut,
            )
        except subprocess.TimeoutExpired as exc:
            subprocess.run(
                [self.docker, "rm", "-f", name],
                capture_output=True,
                timeout=20,
                check=False,
            )
            stdout, _ = self._clip(exc.stdout if isinstance(exc.stdout, str) else "")
            stderr, _ = self._clip(exc.stderr if isinstance(exc.stderr, str) else "")
            return CommandResult(
                profile=profile,
                command=command,
                exit_code=124,
                stdout=stdout,
                stderr=stderr,
                timed_out=True,
                truncated=True,
            )

    def _clip(self, value: str) -> tuple[str, bool]:
        encoded = value.encode("utf-8", errors="replace")
        if len(encoded) <= self.settings.max_output_bytes:
            return value, False
        clipped = encoded[: self.settings.max_output_bytes].decode(
            "utf-8", errors="replace"
        )
        return clipped + "\n[output truncated by harness]\n", True
