"""문제 파일과 progress.md 하나로 상태를 보존한다."""

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
    """화면과 CLI에는 실제 플래그 값을 내보내지 않는다."""
    private_keys = {"flags"}
    result = {key: value for key, value in state.items() if key not in private_keys}
    result["flag_candidates"] = len(state.get("flags", []))
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
            "artifacts": [],
            "tool_runs": [],
            "solution_searches": [],
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

    # 상태를 progress.md에 저장 — 상단에 чел린지 메타, 하단에 tool_runs 테이블, JSON은 주석에 보관
    def save(self, state: dict[str, Any]) -> None:
        state["updated_at"] = utc_now()
        tools = state.get("tool_runs", [])
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
