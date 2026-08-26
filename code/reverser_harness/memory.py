"""Solution notes for challenges that exceeded the direct-solve budget."""

import re
import sqlite3
from pathlib import Path
from typing import Any

from .security import contains_flag, slug
from .storage import ChallengeStore, solve_elapsed_seconds, utc_now


class MemoryError(ValueError):
    """Raised when a solution note is not eligible or invalid."""


class TechniqueMemory:
    # project_root와 ChallengeStore로 TechniqueMemory 초기화 — 로컬 기법 인덱스 경로 설정
    def __init__(self, project_root: Path, store: ChallengeStore) -> None:
        self.project_root = project_root.resolve()
        self.store = store
        self.techniques_dir = self.project_root / "memory" / "techniques"
        self.index_path = self.project_root / "memory" / "index.sqlite"
        self.techniques_dir.mkdir(parents=True, exist_ok=True)

    # research_due(30분 경과 또는 unsolved)일 때만 로컬 기법 검색을 허용 — 시간 가드 후 researching으로 전환
    def search_for_challenge(
        self, challenge_id: str, query: str, research_after_seconds: int, limit: int
    ) -> list[dict[str, Any]]:
        state = self.store.load(challenge_id)
        elapsed = solve_elapsed_seconds(state)
        if elapsed < research_after_seconds and state.get("status") != "unsolved":
            remaining = research_after_seconds - elapsed
            raise MemoryError(f"Direct solve budget has {remaining} seconds remaining")
        if state.get("status") not in {"solving", "researching", "unsolved"}:
            raise MemoryError("Solution search is only available for an active or unsolved challenge")
        if state.get("status") != "unsolved":
            state["status"] = "researching"
        state["research_started_at"] = state.get("research_started_at") or utc_now()
        state.setdefault("solution_searches", []).append(
            {"query": query.strip(), "time": utc_now()}
        )
        self.store.save(state)
        return self.search(query, limit)

    # 30분 이상 또는 unsolved 문제의 재사용 기법을 memory/techniques/에 저장 — solved는 거부, 플래그 포함도 거부
    def save_lesson(self, challenge_id: str, content: str) -> Path:
        state = self.store.load(challenge_id)
        if not state.get("research_started_at") and state.get("status") != "unsolved":
            raise MemoryError("Only researched or unsolved challenges create solution notes")
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
        self.rebuild_index()
        return path

    # memory/techniques/*.md를 FTS5 가상 테이블로 인덱싱 — 제목/본문으로 검색 가능하게 함
    def rebuild_index(self) -> int:
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.index_path)
        try:
            connection.execute("DROP TABLE IF EXISTS cards")
            connection.execute(
                "CREATE VIRTUAL TABLE cards USING fts5(path UNINDEXED, title, body)"
            )
            count = 0
            for path in sorted(self.techniques_dir.glob("*.md")):
                text = path.read_text(encoding="utf-8")
                match = re.search(r"(?m)^title:\s*[\"']?(.+?)[\"']?\s*$", text)
                title = match.group(1) if match else path.stem
                connection.execute(
                    "INSERT INTO cards(path, title, body) VALUES (?, ?, ?)",
                    (path.relative_to(self.project_root).as_posix(), title, text),
                )
                count += 1
            connection.commit()
            return count
        finally:
            connection.close()

    # FTS5 인덱스에서 키워드로 검색 — bm25 정렬, snippet 반환
    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        if not query.strip():
            return []
        if not self.index_path.exists():
            self.rebuild_index()
        connection = sqlite3.connect(self.index_path)
        connection.row_factory = sqlite3.Row
        try:
            rows = connection.execute(
                "SELECT path, title, snippet(cards, 2, '[', ']', ' … ', 24) AS snippet "
                "FROM cards WHERE cards MATCH ? ORDER BY bm25(cards) LIMIT ?",
                (query, max(1, min(20, limit))),
            ).fetchall()
            return [dict(row) for row in rows]
        except sqlite3.OperationalError:
            return []
        finally:
            connection.close()
