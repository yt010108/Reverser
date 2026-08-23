"""Shared profile and challenge metadata."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WorkerProfile:
    name: str
    description: str
    executes_target: bool
    heavy: bool


PROFILES: dict[str, WorkerProfile] = {
    "core": WorkerProfile(
        "core", "Static binary triage and scripted analysis", False, False
    ),
    "dynamic": WorkerProfile(
        "dynamic", "GDB, tracing, and instrumentation", True, False
    ),
    "ghidra": WorkerProfile(
        "ghidra", "Headless Ghidra decompilation", False, True
    ),
    "angr": WorkerProfile(
        "angr", "Symbolic execution in an isolated Python environment", True, True
    ),
}

CHALLENGE_STATUSES = frozenset(
    {
        "importing",
        "imported",
        "solving",
        "researching",
        "solved",
        "unsolved",
        "failed",
    }
)
