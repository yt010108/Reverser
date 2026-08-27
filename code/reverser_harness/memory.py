"""Solution notes for unsolved challenges."""

import re
from pathlib import Path

from .security import contains_flag, slug
from .storage import ChallengeStore, solve_elapsed_seconds


class MemoryError(ValueError):
    """Raised when a solution note is not eligible or invalid."""


class TechniqueMemory:
    # project_root와 ChallengeStore로 TechniqueMemory 초기화 — 로컬 기법 인덱스 경로 설정
    def __init__(self, project_root: Path, store: ChallengeStore) -> None:
        self.project_root = project_root.resolve()
        self.store = store
        self.techniques_dir = self.project_root / "memory" / "techniques"
        self.techniques_dir.mkdir(parents=True, exist_ok=True)

    # 미해결 문제의 재사용 기법을 memory/techniques/에 저장 — 플래그 포함은 거부
    def save_lesson(self, challenge_id: str, content: str) -> Path:
        state = self.store.load(challenge_id)
        if state.get("status") != "unsolved":
            raise MemoryError("Only unsolved challenges create solution notes")
        if not content.strip():
            raise MemoryError("Solution note is empty")
        if contains_flag(content):
            raise MemoryError("Solution note contains a flag-like value")
        title_match = re.search(r"(?m)^title:\s*[\"']?(.+?)[\"']?\s*$", content)
        heading_match = re.search(r"(?m)^#\s+(.+?)\s*$", content)
        title = (
            title_match.group(1)
            if title_match
            else heading_match.group(1)
            if heading_match
            else state.get("title", challenge_id)
        )
        path = self.techniques_dir / f"{slug(title)}-{challenge_id[-8:]}.md"
        body = (
            content.rstrip()
            + "\n\n## Provenance\n\n"
            + f"- Challenge ID: `{challenge_id}`\n"
            + f"- Final status: `{state.get('status')}`\n"
            + f"- Solve elapsed: `{solve_elapsed_seconds(state)}s`\n"
        )
        path.write_text(body, encoding="utf-8", newline="\n")
        return path
