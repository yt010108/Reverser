"""Store Reviewer output inside the ignored challenge workspace."""

from .storage import ChallengeStore


class WriteupManager:
    def __init__(self, store: ChallengeStore) -> None:
        self.store = store

    # Reviewer 결과는 Git에서 제외된 challenge reports/에만 저장
    def save(self, challenge_id: str, markdown: str) -> dict[str, str]:
        state = self.store.load(challenge_id)
        if not markdown.strip():
            raise ValueError("Write-up content is required")
        root = self.store.challenge_dir(challenge_id)
        name = "writeup.md" if state.get("status") == "solved" else "review.md"
        path = root / "reports" / name
        path.write_text(markdown.rstrip() + "\n", encoding="utf-8", newline="\n")
        self.store.register_artifact(state, path, "reviewer-output")
        self.store.save(state)
        return {"path": str(path)}
