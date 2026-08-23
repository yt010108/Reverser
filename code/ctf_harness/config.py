"""Project configuration loading and validation."""

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path


class ConfigError(ValueError):
    """Raised when project configuration is invalid."""


PROFILES = ("core", "dynamic", "ghidra", "angr")


@dataclass(frozen=True, slots=True)
class Settings:
    project_root: Path
    project_name: str
    research_after_seconds: int
    images: dict[str, str]
    timeout_seconds: int
    memory: str
    cpus: str
    pids: int
    max_output_bytes: int
    memory_search_limit: int

    @classmethod
    def load(cls, project_root: Path) -> "Settings":
        root = project_root.resolve()
        path = root / "config.toml"
        try:
            raw = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError) as exc:
            raise ConfigError(f"Cannot load {path}: {exc}") from exc
        project = raw.get("project", {})
        solve = raw.get("solve", {})
        images = {str(key): str(value) for key, value in raw.get("images", {}).items()}
        limits = raw.get("limits", {})
        memory_config = raw.get("memory", {})
        if set(images) != set(PROFILES):
            raise ConfigError("[images] must define core, dynamic, ghidra, and angr")
        image_pattern = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/@-]{0,254}")
        if any(not image_pattern.fullmatch(value) for value in images.values()):
            raise ConfigError("Invalid Docker image name")
        return cls(
            project_root=root,
            project_name=str(project.get("name", "Hermes CTF Reverse Harness")),
            research_after_seconds=max(
                60, min(86_400, int(solve.get("research_after_seconds", 1800)))
            ),
            images=images,
            timeout_seconds=max(10, min(7200, int(limits.get("timeout_seconds", 900)))),
            memory=str(limits.get("memory", "4g")),
            cpus=str(limits.get("cpus", "2")),
            pids=max(64, min(2048, int(limits.get("pids", 512)))),
            max_output_bytes=max(
                65_536, min(16_777_216, int(limits.get("max_output_bytes", 2_097_152)))
            ),
            memory_search_limit=max(
                1, min(20, int(memory_config.get("search_limit", 5)))
            ),
        )
