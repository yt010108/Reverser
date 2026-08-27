"""문제 파일과 progress.md 하나로 상태를 보존한다."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .security import safe_filename, slug, validate_id


# 현재 UTC 시간을 ISO8601(초 단위)로 반환 — progress.md의 생성/갱신 시각에 사용
def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


# 임시 파일에 쓴 뒤 os.replace로 원자적으로 교체 — 쓰기 중 크래시에도 파일 무결성 보장
def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
        os.replace(temporary_name, path)
    finally:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass


# JSON을 원자적으로 저장 (indent 포함)
def atomic_write_json(path: Path, payload: Any) -> None:
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def public_state(state: dict[str, Any]) -> dict[str, Any]:
    """Add local-only derived fields to challenge state."""
    result = dict(state)
    result["elapsed_seconds"] = solve_elapsed_seconds(state)
    return result


# solve_started_at ~ finished_at(없으면 현재) 차이로 풀이 경과 초 계산 — 백그라운드 타이머 불필요
def solve_elapsed_seconds(state: dict[str, Any]) -> int:
    """Return wall-clock solve time without requiring a background timer."""
    started = state.get("solve_started_at")
    if not started:
        return 0
    try:
        beginning = datetime.fromisoformat(str(started))
        ending = (
            datetime.fromisoformat(str(state.get("finished_at")))
            if state.get("finished_at")
            else datetime.now(UTC)
        )
    except ValueError:
        return 0
    return max(0, int((ending - beginning).total_seconds()))


# 파일을 1MB씩 나눠 읽어 SHA256 해시를 계산 — artifact 무결성 검증용
def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class ChallengeStore:
    # runs 루트 경로를 받아 ChallengeStore를 초기화
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    # challenge_id로 실제 디렉터리 경로를 찾음 — rglob으로 runs/<event>/<id> 중첩과 레거시 flat 둘 다 지원, 없으면 flat 경로 반환
    def challenge_dir(self, challenge_id: str) -> Path:
        validate_id(challenge_id)
        direct = (self.root / challenge_id).resolve()
        if (direct / "progress.md").is_file():
            return direct
        # search recursively for existing challenge (supports runs/<event>/<id>)
        root_resolved = self.root.resolve()
        for path in self.root.rglob("progress.md"):
            if path.parent.name == challenge_id:
                try:
                    candidate = path.parent.resolve()
                    candidate.relative_to(root_resolved)
                    return candidate
                except ValueError:
                    continue
        # also check for directory named challenge_id without progress yet (create -> save window)
        for candidate in self.root.rglob(challenge_id):
            if candidate.is_dir() and candidate.name == challenge_id:
                try:
                    resolved = candidate.resolve()
                    resolved.relative_to(root_resolved)
                    # ensure it's a challenge dir (has original/work/output subdirs or is under event)
                    return resolved
                except ValueError:
                    continue
        # not found yet — return direct path (legacy flat) with escape check
        try:
            direct.relative_to(root_resolved)
        except ValueError:
            raise ValueError("Challenge path escapes store")
        return direct

    # 새 챌린지를 생성 — event가 있으면 runs/<slug(event)>/<id>에, 없으면 flat에 생성 후 progress.md 초기화
    def create(
        self,
        *,
        title: str,
        platform_url: str,
        event: str = "",
    ) -> dict[str, Any]:
        challenge_id = f"{slug(title)}-{uuid.uuid4().hex[:8]}"
        event_slug = slug(event) if event.strip() else ""
        if event_slug:
            root = (self.root / event_slug / challenge_id).resolve()
            try:
                root.relative_to(self.root.resolve())
            except ValueError:
                raise ValueError("Challenge path escapes store")
        else:
            root = self.challenge_dir(challenge_id)
        for name in ("original", "work", "output", "reports"):
            (root / name).mkdir(parents=True)
        state: dict[str, Any] = {
            "challenge_id": challenge_id,
            "title": title.strip() or "Untitled challenge",
            "event": event.strip(),
            "category": "reverse",
            "architecture": None,
            "bits": None,
            "platform_url": platform_url,
            "status": "importing",
            "created_at": utc_now(),
            "updated_at": utc_now(),
            "solve_started_at": None,
            "research_started_at": None,
            "solved_at": None,
            "finished_at": None,
            "blocker": "",
            "exit_reason": None,
            "flags": [],
            "flag_evidence": [],
            "artifacts": [],
            "tool_runs": [],
            "solution_searches": [],
            "recon": None,
            "hypotheses": [],
        }
        self.save(state)
        return state

    # progress.md의 <!-- reverser-state --> 주석 안 JSON을 파싱해 상태를 로드
    def load(self, challenge_id: str) -> dict[str, Any]:
        path = self.challenge_dir(challenge_id) / "progress.md"
        try:
            text = path.read_text(encoding="utf-8")
            payload = text.split("<!-- reverser-state\n", 1)[1].split("\n-->", 1)[0]
            value = json.loads(payload)
        except (OSError, IndexError, json.JSONDecodeError) as exc:
            raise FileNotFoundError(f"Unknown or invalid challenge: {challenge_id}") from exc
        if not isinstance(value, dict):
            raise FileNotFoundError(f"Invalid challenge state: {challenge_id}")
        return value

    # 상태를 progress.md에 저장 — 상단에 챌린지 메타, 하단에 tool_runs 테이블, JSON은 주석에 보관
    def save(self, state: dict[str, Any]) -> None:
        state["updated_at"] = utc_now()
        tools = state.get("tool_runs", [])
        clean = lambda value: str(value).replace("\r", " ").replace("\n", " ").strip()
        lines = [
            f"# CTF progress: {state['title']}",
            "",
            f"- ID: `{state['challenge_id']}`",
            f"- Status: `{state['status']}`",
            f"- Target: `{state.get('architecture') or '-'} / {state.get('bits') or '-'}`",
            f"- Commands: `{len(tools)}`",
            f"- Elapsed: `{solve_elapsed_seconds(state)}s`",
            f"- Research started: `{state.get('research_started_at') or '-'}`",
            f"- Updated: `{state['updated_at']}`",
        ]
        hypotheses = state.get("hypotheses", [])
        active = next((item for item in hypotheses if item.get("status") == "testing"), None)
        phase = "verify" if active else "hypothesize" if state.get("recon") else "recon"
        lines.extend(["", "## Solver", "", f"- Phase: `{phase}`"])
        recon = state.get("recon")
        if recon:
            lines.extend([
                "", "## Recon", "",
                f"- Entry point: {clean(recon.get('entry_point', ''))}",
                f"- Main: {clean(recon.get('main') or '-')}",
                f"- Evidence: {', '.join(map(str, recon.get('evidence_runs', []))) or '-'}",
                "- Flag candidates:",
            ])
            for candidate in recon.get("flag_candidates", []):
                runs = ", ".join(map(str, candidate.get("evidence_runs", []))) or "-"
                lines.append(f"  - `{clean(candidate.get('target', '-'))}` — {clean(candidate.get('reason', ''))} (runs: {runs})")
        if active:
            lines.extend([
                "", "## Current hypothesis", "", f"### {clean(active.get('id', '-'))}",
                f"- Target: {clean(active.get('target', ''))}",
                f"- Parent: {clean(active.get('parent_id') or '-')}",
                f"- Claim: {clean(active.get('claim', ''))}",
                f"- Test: {clean(active.get('test', ''))}",
                f"- Falsifier: {clean(active.get('falsifier', ''))}",
                f"- Exhaustion: {clean(active.get('exhaustion', ''))}",
                f"- Evidence: {', '.join(map(str, active.get('evidence_runs', []))) or '-'}",
                "- Status: `testing`",
            ])
        if hypotheses:
            lines.extend(["", "## Hypothesis tree", ""])
            children: dict[str | None, list[dict[str, Any]]] = {}
            for item in hypotheses:
                children.setdefault(item.get("parent_id"), []).append(item)

            def append_hypothesis(item: dict[str, Any], depth: int) -> None:
                runs = ", ".join(map(str, item.get("evidence_runs", []))) or "-"
                lines.append(f"{'  ' * depth}- `{clean(item.get('id', '-'))}` `{clean(item.get('status', '-'))}` `{clean(item.get('target', '-'))}` — {clean(item.get('claim', ''))} — {clean(item.get('observation', ''))} (runs: {runs})")
                for child in children.get(item.get("id"), []):
                    append_hypothesis(child, depth + 1)

            for root in children.get(None, []):
                append_hypothesis(root, 0)
        if state.get("blocker"):
            lines.extend(["", "## Blocker", "", str(state["blocker"])])
        searches = state.get("solution_searches", [])
        if searches:
            lines.extend(["", "## Solution searches", ""])
            for item in searches:
                lines.append(f"- `{item.get('time', '-')}` {item.get('query', '')}")
        lines.extend(
            [
                "",
                "## Commands",
                "",
                "| # | Profile | Exit | Command |",
                "|---:|---|---:|---|",
            ]
        )
        for item in tools:
            command = str(item.get("command", "")).replace("|", "\\|").replace("\n", " ")
            lines.append(f"| {item['sequence']} | {item['profile']} | {item['exit_code']} | `{command}` |")
        metadata = json.dumps(state, ensure_ascii=False, separators=(",", ":"))
        atomic_write_text(
            self.challenge_dir(str(state["challenge_id"])) / "progress.md",
            f"<!-- reverser-state\n{metadata}\n-->\n\n" + "\n".join(lines) + "\n",
        )

    # rglob로 모든 progress.md를 찾아 최신순(updated_at)으로 정렬해 반환
    def list(self) -> list[dict[str, Any]]:
        items = []
        for path in self.root.rglob("progress.md"):
            try:
                value = self.load(path.parent.name)
            except FileNotFoundError:
                continue
            if isinstance(value, dict):
                items.append(value)
        return sorted(items, key=lambda item: item.get("updated_at", ""), reverse=True)

    def start_solver(self, challenge_id: str, terminal: str) -> dict[str, Any]:
        self.load(challenge_id)
        path = self.challenge_dir(challenge_id) / "solver.json"
        value = {"challenge_id": challenge_id, "status": "running", "terminal": terminal, "result": None}
        atomic_write_json(path, value)
        return {**value, "path": str(path)}

    def finish_solver(self, challenge_id: str) -> dict[str, Any]:
        result = str(self.load(challenge_id).get("status", ""))
        if result not in {"solved", "unsolved", "failed"}:
            raise RuntimeError("Solver must record a terminal challenge state before finishing")
        path = self.challenge_dir(challenge_id) / "solver.json"
        try:
            terminal = str(json.loads(path.read_text(encoding="utf-8")).get("terminal", ""))
        except (OSError, json.JSONDecodeError):
            terminal = ""
        value = {"challenge_id": challenge_id, "status": "done", "terminal": terminal, "result": result}
        atomic_write_json(path, value)
        return {**value, "path": str(path)}

    def start_reviewer(self, challenge_id: str, terminal: str) -> dict[str, Any]:
        self.load(challenge_id)
        path = self.challenge_dir(challenge_id) / "reviewer.json"
        try:
            if json.loads(path.read_text(encoding="utf-8")).get("status") == "running":
                raise RuntimeError("Reviewer is already running")
        except (OSError, json.JSONDecodeError):
            pass
        value = {"challenge_id": challenge_id, "status": "running", "terminal": terminal, "result": None}
        atomic_write_json(path, value)
        return {**value, "path": str(path)}

    def finish_reviewer(self, challenge_id: str, failed: bool = False) -> dict[str, Any]:
        state = self.load(challenge_id)
        report = "writeup.md" if state.get("status") == "solved" else "review.md"
        if not failed and not (self.challenge_dir(challenge_id) / "reports" / report).is_file():
            raise RuntimeError("Reviewer must save its report before finishing")
        path = self.challenge_dir(challenge_id) / "reviewer.json"
        try:
            terminal = str(json.loads(path.read_text(encoding="utf-8")).get("terminal", ""))
        except (OSError, json.JSONDecodeError):
            terminal = ""
        value = {"challenge_id": challenge_id, "status": "done", "terminal": terminal, "result": "failed" if failed else report}
        atomic_write_json(path, value)
        return {**value, "path": str(path)}

    def update_recon(
        self,
        challenge_id: str,
        *,
        entry_point: str,
        main: str = "",
        evidence_runs: list[int],
        flag_candidates: list[dict[str, Any]],
    ) -> dict[str, Any]:
        state = self.load(challenge_id)
        if state.get("status") not in {"solving", "researching"}:
            raise RuntimeError("Run triage before recording recon")
        if any(item.get("status") == "testing" for item in state.get("hypotheses", [])):
            raise RuntimeError("Resolve the active hypothesis before updating recon")
        if not entry_point.strip() or len(entry_point) > 500 or len(main) > 500:
            raise ValueError("entry_point is required")
        runs = {item.get("sequence"): item for item in state.get("tool_runs", [])}
        if not evidence_runs or any(run not in runs or runs[run].get("exit_code") != 0 for run in evidence_runs):
            raise RuntimeError("Recon requires successful evidence runs")
        if not any(runs[run].get("profile") != "triage" for run in evidence_runs):
            raise RuntimeError("Inspect the entry point before recording recon")
        candidates = []
        for candidate in flag_candidates:
            if not isinstance(candidate, dict):
                raise ValueError("Each flag candidate must be an object")
            target = str(candidate.get("target", "")).strip()
            reason = str(candidate.get("reason", "")).strip()
            candidate_runs = candidate.get("evidence_runs", [])
            if not target or not reason or len(target) > 500 or len(reason) > 1000:
                raise ValueError("Each flag candidate requires target and reason")
            if not candidate_runs or any(run not in runs or runs[run].get("exit_code") != 0 for run in candidate_runs):
                raise RuntimeError("Flag candidates require successful evidence runs")
            candidates.append({"target": target, "reason": reason, "evidence_runs": list(dict.fromkeys(candidate_runs))})
        if not candidates:
            raise ValueError("At least one flag candidate is required")
        targets = {item["target"] for item in candidates}
        if any(item.get("target") not in targets for item in state.get("hypotheses", [])):
            raise RuntimeError("Recon must retain targets used by existing hypotheses")
        state["recon"] = {
            "entry_point": entry_point.strip(), "main": main.strip(),
            "evidence_runs": list(dict.fromkeys(evidence_runs)), "flag_candidates": candidates,
        }
        self.save(state)
        return state["recon"]

    def update_hypothesis(
        self,
        challenge_id: str,
        action: str,
        *,
        hypothesis_id: str = "",
        target: str = "",
        parent_id: str = "",
        claim: str = "",
        test: str = "",
        falsifier: str = "",
        exhaustion: str = "",
        outcome: str = "",
        evidence_run: int | None = None,
        observation: str = "",
    ) -> dict[str, Any]:
        state = self.load(challenge_id)
        hypotheses = state.setdefault("hypotheses", [])
        active = next((item for item in hypotheses if item.get("status") == "testing"), None)
        if action == "propose":
            if state.get("status") not in {"solving", "researching"}:
                raise RuntimeError("Run triage before proposing a hypothesis")
            recon = state.get("recon")
            if not recon:
                raise RuntimeError("Record entry-point recon before proposing a hypothesis")
            if active:
                raise RuntimeError("Resolve the active hypothesis before proposing another")
            target = target.strip()
            if target not in {item.get("target") for item in recon.get("flag_candidates", [])}:
                raise RuntimeError("Hypothesis target must be a recon flag candidate")
            parent = next((item for item in hypotheses if item.get("id") == parent_id), None) if parent_id else None
            if parent_id and not parent:
                raise RuntimeError("Unknown parent hypothesis")
            if parent and (parent.get("status") == "rejected" or parent.get("target") != target):
                raise RuntimeError("A child requires a non-rejected parent with the same target")
            values = [claim.strip(), test.strip(), falsifier.strip(), exhaustion.strip()]
            if any(not value or len(value) > 1000 for value in values):
                raise ValueError("claim, test, falsifier, and exhaustion are required")
            active = {
                "id": f"h{len(hypotheses) + 1}", "target": target, "parent_id": parent_id or None,
                "claim": values[0], "test": values[1],
                "falsifier": values[2], "exhaustion": values[3], "status": "testing", "evidence_runs": [],
            }
            hypotheses.append(active)
        elif action == "resolve":
            if not active or active.get("id") != hypothesis_id:
                raise RuntimeError("Unknown active hypothesis")
            if outcome not in {"confirmed", "rejected", "inconclusive"} or evidence_run is None or not observation.strip():
                raise ValueError("outcome, evidence_run, and observation are required")
            runs = [item for item in state.get("tool_runs", []) if item.get("hypothesis_id") == hypothesis_id]
            if evidence_run not in {item.get("sequence") for item in runs}:
                raise RuntimeError("Evidence run does not belong to the active hypothesis")
            active["status"] = outcome
            active["observation"] = observation.strip()
            active["evidence_runs"] = [item["sequence"] for item in runs]
        else:
            raise ValueError("Unknown hypothesis action")
        self.save(state)
        return {"phase": "verify" if action == "propose" else "hypothesize", "hypothesis": active}

    # 원본 첨부 파일을 original/에 복사하고 artifact 목록에 등록 — 중복 시 -1, -2 접미사
    def add_original(self, state: dict[str, Any], source: Path, name: str | None = None) -> Path:
        source = source.resolve()
        if not source.is_file():
            raise FileNotFoundError(source)
        destination_dir = self.challenge_dir(state["challenge_id"]) / "original"
        filename = safe_filename(name or source.name)
        destination = destination_dir / filename
        counter = 1
        while destination.exists():
            destination = destination_dir / f"{Path(filename).stem}-{counter}{Path(filename).suffix}"
            counter += 1
        shutil.copyfile(source, destination)
        self.register_artifact(state, destination, "original")
        return destination

    # 파일을 artifact 목록에 등록 — 상대경로, 크기, SHA256 기록, 기존 동일 path는 덮어씀
    def register_artifact(
        self, state: dict[str, Any], path: Path, kind: str
    ) -> dict[str, Any]:
        root = self.challenge_dir(state["challenge_id"])
        resolved = path.resolve()
        if root not in resolved.parents:
            raise ValueError("Artifact is outside challenge directory")
        entry = {
            "path": resolved.relative_to(root).as_posix(),
            "kind": kind,
            "size": resolved.stat().st_size,
            "sha256": sha256_file(resolved),
        }
        state["artifacts"] = [
            item for item in state["artifacts"] if item["path"] != entry["path"]
        ]
        state["artifacts"].append(entry)
        return entry
