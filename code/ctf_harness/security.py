"""Input validation and tracked-output sanitization."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlsplit


class SecurityError(ValueError):
    """Raised when an input violates a harness boundary."""


_SAFE_ID = re.compile(r"[a-z0-9][a-z0-9.-]{0,95}")
_FLAG = re.compile(r"\b[A-Za-z][A-Za-z0-9_]{0,31}\{[^}\r\n]{1,512}\}")


def slug(value: str, limit: int = 64) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9.-]+", "-", value).strip("-.").lower()
    return (normalized[:limit] or "challenge").rstrip("-.")


def validate_id(value: str) -> str:
    if not _SAFE_ID.fullmatch(value):
        raise SecurityError("Invalid challenge id")
    return value


def validate_http_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
        _ = parsed.port
    except ValueError as exc:
        raise SecurityError(f"Invalid URL: {value}") from exc
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise SecurityError("Only absolute HTTP(S) challenge URLs are accepted")
    if parsed.username is not None or parsed.password is not None:
        raise SecurityError("Credentials must not be embedded in URLs")
    return value


def safe_filename(value: str, fallback: str = "attachment.bin") -> str:
    name = Path(value.replace("\\", "/")).name
    name = re.sub(r"[^a-zA-Z0-9._()+@ -]+", "_", name).strip(" .")
    return name[:180] or fallback


def redact_flags(text: str, known_flags: list[str] | None = None) -> str:
    result = text
    for flag in sorted(set(known_flags or []), key=len, reverse=True):
        if flag:
            result = result.replace(flag, "[FLAG REDACTED]")
    return _FLAG.sub("[FLAG REDACTED]", result)


def contains_flag(text: str) -> bool:
    return bool(_FLAG.search(text))
