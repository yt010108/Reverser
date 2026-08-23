"""브라우저로 다운로드한 파일을 로컬 문제 저장소에 가져온다."""

from pathlib import Path
from typing import Any

from .security import validate_http_url
from .storage import ChallengeStore


class ChallengeImporter:
    def __init__(self, store: ChallengeStore) -> None:
        self.store = store

    def import_local(
        self,
        *,
        title: str,
        files: list[Path],
        platform_url: str = "",
        event: str = "",
        description: str = "",
    ) -> dict[str, Any]:
        if platform_url:
            validate_http_url(platform_url)
        if not title.strip():
            raise ValueError("Challenge title is required")
        if not files:
            raise ValueError("At least one local attachment is required")
        resolved = [path.expanduser().resolve() for path in files]
        missing = [str(path) for path in resolved if not path.is_file()]
        if missing:
            raise ValueError(f"Attachment does not exist: {missing[0]}")
        state = self.store.create(
            title=title,
            platform_url=platform_url,
            event=event,
        )
        try:
            for path in resolved:
                self.store.add_original(state, path)
            if description.strip():
                description_path = (
                    self.store.challenge_dir(state["challenge_id"])
                    / "original"
                    / "description.md"
                )
                description_path.write_text(
                    description.rstrip() + "\n", encoding="utf-8", newline="\n"
                )
                self.store.register_artifact(state, description_path, "description")
            state["status"] = "imported"
            self.store.save(state)
            return state
        except Exception:
            state["status"] = "failed"
            self.store.save(state)
            raise
