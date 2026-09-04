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

    # techniques 디렉터리에서 쿼리 포함 카드를 대소문자 무시로 검색 — 최신순, limit개까지
    def search(self, query: str, limit: int = 5) -> list[dict[str, str]]:
        needle = query.strip().lower()
        if not needle:
            return []
        hits: list[dict[str, str]] = []
        for path in sorted(self.techniques_dir.glob("*.md"), reverse=True):
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if needle not in text.lower():
                continue
            idx = text.lower().find(needle)
            snippet = text[max(0, idx - 120):idx + 240].strip().replace("\n", " ")
            hits.append({"path": path.name, "snippet": snippet[:360]})
            if len(hits) >= max(1, limit):
                break
        return hits

    # 미해결이거나 research 예산을 넘긴 문제만 로컬 검색 허용 — gate 통과 못 하면 MemoryError
    def search_for_challenge(
        self, challenge_id: str, query: str, research_after_seconds: int, limit: int
    ) -> list[dict[str, str]]:
        state = self.store.load(challenge_id)
        if state.get("status") != "unsolved" and solve_elapsed_seconds(state) < research_after_seconds:
            raise MemoryError("Local search is allowed after 30 minutes or when unsolved")
        results = self.search(query, limit)
        searches = state.setdefault("solution_searches", [])
        searches.append({"time": state.get("updated_at", ""), "query": query})
        self.store.save(state)
        return results
