#!/usr/bin/env python3
"""Deterministic, non-executing first-pass file triage."""

from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
import sys
from pathlib import Path

import lief


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def entropy(path: Path) -> float:
    counts = [0] * 256
    total = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            total += len(block)
            for value in block:
                counts[value] += 1
    if not total:
        return 0.0
    return round(-sum((count / total) * math.log2(count / total) for count in counts if count), 4)


def command(*parts: str) -> str:
    result = subprocess.run(parts, capture_output=True, text=True, errors="replace", timeout=20, check=False)
    return (result.stdout or result.stderr).strip()[:32_768]


def lief_info(path: Path) -> dict[str, object]:
    try:
        binary = lief.parse(str(path))
    except Exception:
        return {}
    if binary is None:
        return {}
    fmt = str(binary.format).split(".")[-1].lower()
    header = getattr(binary, "header", None)
    machine = str(getattr(header, "machine_type", getattr(header, "machine", "unknown"))).split(".")[-1].lower()
    bits = 64 if "64" in machine or "x86_64" in machine or "amd64" in machine else 32 if machine else None
    return {
        "format": "pe" if fmt == "pe" else "elf" if fmt == "elf" else fmt,
        "architecture": "amd64" if any(value in machine for value in ("x86_64", "amd64")) else "x86" if any(value in machine for value in ("i386", "x86")) else machine,
        "bits": bits,
        "entrypoint": hex(int(getattr(binary, "entrypoint", 0))),
    }


def inspect(path: Path, root: Path) -> dict[str, object]:
    stat = path.stat()
    info: dict[str, object] = {
        "path": path.relative_to(root).as_posix(),
        "size": stat.st_size,
        "sha256": sha256(path),
        "entropy": entropy(path),
        "file": command("file", "-b", str(path)),
    }
    info.update(lief_info(path))
    if info.get("format") == "elf":
        info["security"] = command("pwn", "checksec", "--file", str(path))
    info["strings_preview"] = command("strings", "-a", "-n", "6", str(path)).splitlines()[:80]
    return info


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: ctf-triage INPUT_DIR OUTPUT_JSON", file=sys.stderr)
        return 2
    root = Path(sys.argv[1]).resolve()
    output = Path(sys.argv[2]).resolve()
    files = [path for path in root.rglob("*") if path.is_file() and not path.is_symlink()]
    payload = {"schema": 1, "files": [inspect(path, root) for path in sorted(files)]}
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
