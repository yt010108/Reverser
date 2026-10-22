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
    def __init__(self, store: ChallengeStore, worker: DockerWorker) -> None:
        self.store = store
        self.worker = worker

    def triage(self, challenge_id: str) -> tuple[dict[str, Any], CommandResult]:
        state = self.store.load(challenge_id)
        root = self.store.challenge_dir(challenge_id)
        result = self.worker.run(
            profile="core",
            challenge_dir=root,
            command="reverser-triage /challenge/input /challenge/output/triage.json",
            timeout_seconds=300,
        )
        if result.exit_code != 0 or result.timed_out:
            self._record_run(state, "triage", result)
            state["status"] = "failed"
            detail = result.stderr.strip() or result.stdout.strip() or "Triage failed"
            if "reverser-triage: command not found" in detail:
                detail = "Core worker image is missing reverser-triage; rebuild the Reverser core image"
            state["blocker"] = detail
            self.store.save(state)
            raise AnalysisError(detail)
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
        if state.get("status") in {"solved", "unsolved", "failed", "local_verified"}:
            state["solve_started_at"] = utc_now()
            state["research_started_at"] = None
            state["solved_at"] = None
        elif not state.get("solve_started_at"):
            state["solve_started_at"] = utc_now()
        state["status"] = "solving"
        state["blocker"] = ""
        state["exit_reason"] = None
        state["finished_at"] = None
        self._record_run(state, "triage", result)
        self.store.register_artifact(state, triage_path, "triage")
        self.store.save(state)
        return state, result

    def run_command(
        self,
        challenge_id: str,
        profile: str,
        command: str,
        timeout_seconds: int | None = None,
        hypothesis_id: str | None = None,
    ) -> tuple[dict[str, Any], CommandResult]:
        if profile not in PROFILES:
            raise AnalysisError(f"Unknown profile: {profile}")
        state = self.store.load(challenge_id)
        if state.get("status") not in {"solving", "researching"}:
            raise AnalysisError("Run triage before free-form analysis")
        hypotheses = state.get("hypotheses", [])
        active = next((item for item in hypotheses if item.get("status") == "testing"), None)
        if hypotheses and not active:
            raise AnalysisError("Propose the next hypothesis before running analysis")
        if active and active.get("id") != hypothesis_id:
            raise AnalysisError("Verification commands require the active hypothesis_id")
        root = self.store.challenge_dir(challenge_id)
        result = self.worker.run(
            profile=profile,
            challenge_dir=root,
            command=command,
            timeout_seconds=timeout_seconds,
        )
        self._record_run(state, profile, result, hypothesis_id)
        self.store.save(state)
        return state, result

    def review_command(
        self, challenge_id: str, profile: str, command: str,
        timeout_seconds: int | None = None,
    ) -> tuple[dict[str, Any], CommandResult]:
        if profile not in PROFILES:
            raise AnalysisError(f"Unknown profile: {profile}")
        state = self.store.load(challenge_id)
        if state.get("status") not in {"solved", "local_verified", "unsolved", "failed"}:
            raise AnalysisError("Review execution requires a finished challenge")
        result = self.worker.run(
            profile=profile,
            challenge_dir=self.store.challenge_dir(challenge_id),
            command=command,
            timeout_seconds=timeout_seconds,
        )
        self._record_run(state, "review", result)
        state["tool_runs"][-1]["phase"] = "review"
        self.store.save(state)
        return state, result

    def record_flag(
        self, challenge_id: str, flag: str, evidence_run: int, kind: str
    ) -> dict[str, Any]:
        state = self.store.load(challenge_id)
        previous_status = state.get("status")
        value = flag.strip()
        if kind not in {"flag", "local_solution"}:
            raise AnalysisError("kind must be flag or local_solution")
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
            or run.get("profile") == "triage"
        ):
            raise AnalysisError("Invalid evidence run")
        root = self.store.challenge_dir(challenge_id)
        output = "\n".join(
            (root / str(run[name])).read_text(encoding="utf-8", errors="replace")
            for name in ("stdout", "stderr")
        )
        if value not in output:
            raise AnalysisError("Flag not found in evidence run")
        evidence = state.setdefault("result_evidence", [])
        if not any(item.get("kind") == kind and item.get("value") == value and item.get("evidence_run") == evidence_run for item in evidence):
            evidence.append({"kind": kind, "value": value, "evidence_run": evidence_run})
        if kind == "flag":
            if value not in state["flags"]:
                state["flags"].append(value)
            state["status"] = "solved"
            state["solved_at"] = state.get("solved_at") or utc_now()
            state["finished_at"] = state["solved_at"] if previous_status != "solved" else state.get("finished_at") or state["solved_at"]
        else:
            answers = state.setdefault("local_answers", [])
            if value not in answers:
                answers.append(value)
            if state.get("status") != "solved":
                state["status"] = "local_verified"
                state["finished_at"] = state.get("finished_at") if previous_status == "local_verified" else utc_now()
        state["blocker"] = ""
        state["exit_reason"] = None
        self.store.save(state)
        return state

    def terminate(self, challenge_id: str, exit_reason: str) -> dict[str, Any]:
        state = self.store.load(challenge_id)
        state["exit_reason"] = exit_reason
        if state.get("status") not in {"solved", "local_verified", "unsolved"}:
            state["status"] = "failed"
            state["finished_at"] = state.get("finished_at") or utc_now()
        self.store.save(state)
        return state

    def mark_unsolved(self, challenge_id: str, blocker: str) -> dict[str, Any]:
        state = self.store.load(challenge_id)
        if not blocker.strip():
            raise AnalysisError("An unsolved blocker summary is required")
        state["status"] = "unsolved"
        state["blocker"] = blocker.strip()
        state["finished_at"] = state.get("finished_at") or utc_now()
        self.store.save(state)
        return state

    def _record_run(
        self, state: dict[str, Any], label: str, result: CommandResult,
        hypothesis_id: str | None = None,
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
        if hypothesis_id:
            record["hypothesis_id"] = hypothesis_id
        state["tool_runs"].append(record)
