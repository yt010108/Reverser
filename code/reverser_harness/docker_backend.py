"""Locked, ephemeral Docker workers for CTF reversing."""

import os
import json
import shutil
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path

from .config import PROFILES, Settings
from .security import validate_id


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
    # Settings의 이미지/리소스 제한으로 DockerWorker 초기화 — docker 바이너리 존재 확인
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.docker = shutil.which("docker")
        if not self.docker:
            raise BackendError("docker was not found on PATH")

    # docker image inspect로 각 프로필(core/dynamic/ghidra/angr) 이미지 가용성 점검
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
        core = profiles["core"]
        if core["available"]:
            probe = subprocess.run(
                [self.docker, "run", "--rm", "--pull=never", "--network", "none",
                 "--entrypoint", "sh", self.settings.images["core"], "-c",
                 "command -v reverser-triage >/dev/null"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
                check=False,
            )
            core["ready"] = probe.returncode == 0
            if probe.returncode:
                core["error"] = "Core image is missing reverser-triage; rebuild with docker compose -f docker/compose.yaml build core"
        return {
            "docker": self.docker,
            "mode": "ephemeral-worker-per-command",
            "profiles": profiles,
            "core_ready": bool(core["available"] and core.get("ready")),
        }

    # 격리 컨테이너를 1회용으로 띄워 명령 실행 — network none, read-only, cap-drop, pids/memory 제한, /challenge 마운트
    def run(
        self,
        *,
        profile: str,
        challenge_dir: Path,
        command: str,
        timeout_seconds: int | None = None,
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
        intent_id = os.environ.get("REVERSER_INTENT_ID", "").strip()
        if intent_id:
            validate_id(intent_id)
        original = (root / "original").resolve()
        work_name = f"work/intents/{intent_id}" if intent_id else "work"
        output_name = f"output/intents/{intent_id}" if intent_id else "output"
        work = (root / work_name).resolve()
        output = (root / output_name).resolve()
        if any(root not in path.parents for path in (original, work, output)):
            raise BackendError("Challenge workspace escapes its root")
        for path in (original, work, output):
            path.mkdir(parents=True, exist_ok=True)

        runs_volume = os.environ.get("REVERSER_RUNS_VOLUME", "").strip()
        shared_bind = os.environ.get("REVERSER_RUNS_SHARED_BIND", "") == "1"
        if runs_volume and shared_bind:
            raise BackendError("Choose one shared runs mount mode")
        relative_path = ""
        if runs_volume or shared_bind:
            runs_root = Path(os.environ.get("REVERSER_RUNS_ROOT", "/app/runs")).resolve()
            try:
                relative_path = root.relative_to(runs_root).as_posix()
            except ValueError as exc:
                raise BackendError("Challenge is outside shared runs") from exc
        host_runs = self._shared_bind_source() if shared_bind else ""

        timeout = max(1, min(7200, timeout_seconds or self.settings.timeout_seconds))
        name = f"reverser-{profile}-{uuid.uuid4().hex[:12]}"
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
        ]
        for directory, target, readonly in (("original", "/challenge/input", True),
                                            (work_name, "/challenge/work", False),
                                            (output_name, "/challenge/output", False)):
            if runs_volume:
                mount = f"type=volume,source={runs_volume},volume-subpath={relative_path}/{directory},target={target}"
            elif shared_bind:
                mount = f"type=bind,source={host_runs}/{relative_path}/{directory},target={target}"
            else:
                mount = f"type=bind,source={root / directory},target={target}"
            if readonly:
                mount += ",readonly"
            docker_command.extend(["--mount", mount])
        if intent_id and os.environ.get("REVERSER_ROLE") == "verifier":
            if runs_volume:
                shared = f"type=volume,source={runs_volume},volume-subpath={relative_path}/work,target=/challenge/shared,readonly"
            elif shared_bind:
                shared = f"type=bind,source={host_runs}/{relative_path}/work,target=/challenge/shared,readonly"
            else:
                shared = f"type=bind,source={root / 'work'},target=/challenge/shared,readonly"
            docker_command.extend(["--mount", shared])
        docker_command.extend(["--workdir", "/challenge/work"])
        if profile == "dynamic":
            docker_command.extend(
                [
                    "--cap-add",
                    "SYS_PTRACE",
                    "--security-opt",
                    "seccomp=unconfined",
                ]
            )
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

    def _shared_bind_source(self) -> str:
        """Resolve the host side of the web container's runs bind mount."""
        container = os.environ.get("HOSTNAME") or os.uname().nodename
        inspected = subprocess.run(
            [self.docker, "inspect", container, "--format", "{{json .Mounts}}"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=20, check=False,
        )
        if inspected.returncode:
            raise BackendError("Cannot inspect the web container's runs mount")
        try:
            mounts = json.loads(inspected.stdout)
        except json.JSONDecodeError as exc:
            raise BackendError("Invalid web container mount metadata") from exc
        runs_root = os.environ.get("REVERSER_RUNS_ROOT", "/app/runs")
        match = next((item for item in mounts if item.get("Destination") == runs_root
                      and item.get("Type") == "bind"), None)
        if not match:
            raise BackendError("Web runs directory is not a Docker bind mount")
        return str(match["Source"]).rstrip("/")

    # 출력을 max_output_bytes로 자르고 truncate 플래그 반환
    def _clip(self, value: str) -> tuple[str, bool]:
        encoded = value.encode("utf-8", errors="replace")
        if len(encoded) <= self.settings.max_output_bytes:
            return value, False
        clipped = encoded[: self.settings.max_output_bytes].decode(
            "utf-8", errors="replace"
        )
        return clipped + "\n[output truncated by harness]\n", True
