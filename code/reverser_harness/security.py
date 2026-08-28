"""Input validation helpers."""

import re
from pathlib import Path
from urllib.parse import urlsplit


class SecurityError(ValueError):
    """Raised when an input violates a harness boundary."""


_SAFE_ID = re.compile(r"[a-z0-9][a-z0-9.-]{0,95}")
_FLAG = re.compile(r"\b[A-Za-z][A-Za-z0-9_]{0,31}\{[^}\r\n]{1,512}\}")


# 문자열을 소문자-하이픈 slug로 정규화 — 파일/폴더명 생성에 사용
def slug(value: str, limit: int = 64) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9.-]+", "-", value).strip("-.").lower()
    return (normalized[:limit] or "challenge").rstrip("-.")


# challenge_id가 [a-z0-9][a-z0-9.-]{0,95} 패턴인지 검증 — 경로 탈출 방지
def validate_id(value: str) -> str:
    if not _SAFE_ID.fullmatch(value):
        raise SecurityError("Invalid challenge id")
    return value


# http/https URL만 허용, 크리덴셜 포함 거부 — 플랫폼 URL 검증
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


# 경로 조작을 방지해 안전한 파일명으로 정규화 — 180자 제한
def safe_filename(value: str, fallback: str = "attachment.bin") -> str:
    name = Path(value.replace("\\", "/")).name
    name = re.sub(r"[^a-zA-Z0-9._()+@ -]+", "_", name).strip(" .")
    return name[:180] or fallback


# 텍스트에 FLAG 패턴이 포함되어 있는지 검사
def contains_flag(text: str) -> bool:
    return bool(_FLAG.search(text))
