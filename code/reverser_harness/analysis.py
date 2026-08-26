"""Challenge triage and isolated worker command orchestration."""

import json
from pathlib import Path
from typing import Any

from .config import PROFILES
from .docker_backend import CommandResult, DockerWorker
from .storage import ChallengeStore, utc_now


class AnalysisError(RuntimeError):
    """Raised when an analysis action fails validation."""


class Analyzer:
    # ChallengeStore와 DockerWorker를 주입받아 Analyzer 초기화
    def __init__(self, store: ChallengeStore, worker: DockerWorker) -> None:
        self.store = store
        self.worker = worker

    # core 워커에서 reverser-triage를 실행해 triage.json 생성, ELF/PE 아키텍처 파싱 후 성공 시 solving, 실패 시 failed로 전환
    def triage(self, challenge_id: str) -> tuple[dict[str, Any], CommandResult]:
        state = self.store.load(challenge_id)
        root = self.store.challenge_dir(challenge_id)
        result = self.worker.run(
            profile="core",
            challenge_dir=root,
            command="reverser-triage /challenge/input /challenge/output/triage.json",
            timeout_seconds=300,
        )
        triage_path = root / "output" / "triage.json"
        if not triage_path.is_file():
            raise AnalysisError(result.stderr.strip() or "Triage did not produce output")
        try:
            triage = json.loads(triage_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise AnalysisError("Invalid triage output") from exc
        state["triage"] = triage
        primary = next(
            (
                item
                for item in triage.get("files", [])
                if item.get("format") in {"elf", "pe"}
            ),
            None,
        )
        if primary:
            state["architecture"] = primary.get("architecture")
            state["bits"] = primary.get("bits")
        state["status"] = "solving" if result.exit_code == 0 else "failed"
        if result.exit_code == 0 and not state.get("solve_started_at"):
            state["solve_started_at"] = utc_now()
        self._record_run(state, "triage", result)
        self.store.register_artifact(state, triage_path, "triage")
        self.store.save(state)
        return state, result

    # 지정 프로필(core/dynamic/ghidra/angr)로 격리 워커에서 명령 실행 — triage 후 solving/researching 상태에서만 허용
    def run_command(
        self,
        challenge_id: str,
        profile: str,
        command: str,
        timeout_seconds: int | None = None,
    ) -> tuple[dict[str, Any], CommandResult]:
        if profile not in PROFILES:
            raise AnalysisError(f"Unknown profile: {profile}")
        state = self.store.load(challenge_id)
        if state.get("status") not in {"solving", "researching"}:
            raise AnalysisError("Run triage before free-form analysis")
        root = self.store.challenge_dir(challenge_id)
        result = self.worker.run(
            profile=profile,
            challenge_dir=root,
            command=command,
            timeout_seconds=timeout_seconds,
        )
        self._record_run(state, profile, result)
        self.store.save(state)
        return state, result

    # 증거 run의 stdout/stderr에 플래그가 찍혀있는지 검증 후 flags에 추가하고 solved로 전환
    def record_flag(
        self, challenge_id: str, flag: str, evidence_run: int
    ) -> dict[str, Any]:
        state = self.store.load(challenge_id)
        value = flag.strip()
        if not value or len(value) > 1024:
            raise AnalysisError("Invalid flag candidate")
        run = next(
            (
                item
                for item in state.get("tool_runs", [])
                if item.get("sequence") == evidence_run
            ),
            None,
        )
        if (
            run is None
            or run.get("exit_code") != 0
            or run.get("timed_out", False)
        ):
            raise AnalysisError("Invalid evidence run")
        root = self.store.challenge_dir(challenge_id)
        output = "\n".join(
            (root / str(run[name])).read_text(encoding="utf-8", errors="replace")
            for name in ("stdout", "stderr")
        )
        if value not in output:
            raise AnalysisError("Flag not found in evidence run")
        if value not in state["flags"]:
            state["flags"].append(value)
        state["status"] = "solved"
        state["solved_at"] = state.get("solved_at") or utc_now()
        state["finished_at"] = state.get("finished_at") or state["solved_at"]
        self.store.save(state)
        return state

    # 에이전트 비정상 종료 시 failed로 마킹하고 exit_reason을 남김 — solved/unsolved는 유지
    def terminate(self, challenge_id: str, exit_reason: str) -> dict[str, Any]:
        state = self.store.load(challenge_id)
        state["exit_reason"] = exit_reason
        if state.get("status") not in {"solved", "unsolved"}:
            state["status"] = "failed"
            state["finished_at"] = state.get("finished_at") or utc_now()
        self.store.save(state)
        return state

    # 풀이 불가 시 blocker 요약을 기록하고 unsolved로 마킹
    def mark_unsolved(self, challenge_id: str, blocker: str) -> dict[str, Any]:
        state = self.store.load(challenge_id)
        if not blocker.strip():
            raise AnalysisError("An unsolved blocker summary is required")
        state["status"] = "unsolved"
        state["blocker"] = blocker.strip()
        state["finished_at"] = state.get("finished_at") or utc_now()
        self.store.save(state)
        return state

    # 워커 결과를 output/0001-profile.stdout.log 형태로 저장하고 tool_runs 메타를 state에 추가
    def _record_run(
        self, state: dict[str, Any], label: str, result: CommandResult
    ) -> None:
        root = self.store.challenge_dir(state["challenge_id"])
        sequence = len(state["tool_runs"]) + 1
        stem = f"{sequence:04d}-{label}"
        stdout_path = root / "output" / f"{stem}.stdout.log"
        stderr_path = root / "output" / f"{stem}.stderr.log"
        stdout_path.write_text(result.stdout, encoding="utf-8", newline="\n")
        stderr_path.write_text(result.stderr, encoding="utf-8", newline="\n")
        record = {
            "sequence": sequence,
            "profile": result.profile,
            "command": result.command,
            "exit_code": result.exit_code,
            "timed_out": result.timed_out,
            "truncated": result.truncated,
            "stdout": stdout_path.relative_to(root).as_posix(),
            "stderr": stderr_path.relative_to(root).as_posix(),
            "time": utc_now(),
        }
        state["tool_runs"].append(record)
