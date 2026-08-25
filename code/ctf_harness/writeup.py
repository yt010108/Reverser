"""Private and Git-safe CTF write-up handling."""

from pathlib import Path

from .security import redact_flags, slug
from .storage import ChallengeStore, atomic_write_json


class WriteupManager:
    def __init__(self, project_root: Path, store: ChallengeStore) -> None:
        self.project_root = project_root.resolve()
        self.store = store

    def save(self, challenge_id: str, markdown: str) -> dict[str, str]:
        state = self.store.load(challenge_id)
        if not markdown.strip():
            raise ValueError("Write-up content is required")
        root = self.store.challenge_dir(challenge_id)
        private_path = root / "reports" / "writeup.private.md"
        private_path.write_text(markdown.rstrip() + "\n", encoding="utf-8", newline="\n")
        self.store.register_artifact(state, private_path, "private-writeup")

        event = slug(state.get("event") or "unknown-event")
        title = slug(state["title"])
        export_dir = self.project_root / "writeups" / event / f"{title}-{challenge_id[-8:]}"
        export_dir.mkdir(parents=True, exist_ok=True)
        public_path = export_dir / "writeup.md"
        private_values = state.get("flags", []) + state.get("flag_candidates", [])
        public_text = redact_flags(markdown, private_values)
        public_path.write_text(public_text.rstrip() + "\n", encoding="utf-8", newline="\n")
        metadata = {
            "title": state["title"],
            "event": state["event"],
            "category": "reverse",
            "architecture": state.get("architecture"),
            "bits": state.get("bits"),
            "source_url": state["platform_url"],
            "challenge_id": challenge_id,
            "attachments": [
                {
                    "name": Path(item["path"]).name,
                    "size": item["size"],
                    "sha256": item["sha256"],
                }
                for item in state["artifacts"]
                if item["kind"] == "original"
            ],
        }
        atomic_write_json(export_dir / "metadata.json", metadata)

        solve_files = []
        for pattern in ("solve*", "*.py", "*.sh"):
            for source in sorted((root / "work").glob(pattern)):
                if not source.is_file() or source.name in solve_files:
                    continue
                text = source.read_text(encoding="utf-8", errors="replace")
                destination = export_dir / source.name
                destination.write_text(
                    redact_flags(text, private_values),
                    encoding="utf-8",
                    newline="\n",
                )
                solve_files.append(source.name)

        self.store.save(state)
        return {
            "private": str(private_path),
            "public": str(public_path),
            "export_dir": str(export_dir),
        }
