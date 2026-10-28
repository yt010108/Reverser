"""문제 파일과 progress.md 하나로 상태를 보존한다."""

import hashlib
import json
import os
import re
import shutil
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .security import safe_filename, slug, validate_id


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
        os.replace(temporary_name, path)
    finally:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass


def atomic_write_json(path: Path, payload: Any) -> None:
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def public_state(state: dict[str, Any]) -> dict[str, Any]:
    """화면과 CLI에는 실제 플래그 값을 내보내지 않는다."""
    secrets = [str(value) for key in ("flags", "local_answers") for value in state.get(key, []) if value]
    def redact(value: Any) -> Any:
        if isinstance(value, str):
            for secret in secrets:
                value = value.replace(secret, "[비공개 결과]")
            return re.sub(r"\b[A-Za-z][A-Za-z0-9_]{0,31}\{[^}\r\n]{1,512}\}", "[비공개 결과]", value)
        if isinstance(value, list):
            return [redact(item) for item in value]
        if isinstance(value, dict):
            return {key: redact(item) for key, item in value.items()}
        return value
    result = redact({key: value for key, value in state.items() if key not in {"flags", "local_answers", "result_evidence"}})
    result["flag_candidates"] = len(state.get("flags", []))
    result["local_answer_count"] = len(state.get("local_answers", []))
    result["result_runs"] = [item["evidence_run"] for item in state.get("result_evidence", [])]
    result["elapsed_seconds"] = solve_elapsed_seconds(state)
    return result


def solve_elapsed_seconds(state: dict[str, Any]) -> int:
    """Return wall-clock solve time without requiring a background timer."""
    started = state.get("solve_started_at")
    if not started:
        return 0
    try:
        beginning = datetime.fromisoformat(str(started))
        ending = (
            datetime.fromisoformat(str(state.get("finished_at")))
            if state.get("finished_at")
            else datetime.now(UTC)
        )
    except ValueError:
        return 0
    return max(0, int((ending - beginning).total_seconds()))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class ChallengeStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._locations: dict[str, Path] = {}

    def challenge_dir(self, challenge_id: str) -> Path:
        validate_id(challenge_id)
        cached = self._locations.get(challenge_id)
        if cached and cached.is_dir():
            return cached
        direct = (self.root / challenge_id).resolve()
        if (direct / "progress.md").is_file():
            self._locations[challenge_id] = direct
            return direct
        # search recursively for existing challenge (supports runs/<event>/<id>)
        root_resolved = self.root.resolve()
        for path in self.root.rglob("progress.md"):
            if path.parent.name == challenge_id:
                try:
                    candidate = path.parent.resolve()
                    candidate.relative_to(root_resolved)
                    self._locations[challenge_id] = candidate
                    return candidate
                except ValueError:
                    continue
        # also check for directory named challenge_id without progress yet (create -> save window)
        for candidate in self.root.rglob(challenge_id):
            if candidate.is_dir() and candidate.name == challenge_id:
                try:
                    resolved = candidate.resolve()
                    resolved.relative_to(root_resolved)
                    # ensure it's a challenge dir (has original/work/output subdirs or is under event)
                    self._locations[challenge_id] = resolved
                    return resolved
                except ValueError:
                    continue
        # not found yet — return direct path (legacy flat) with escape check
        try:
            direct.relative_to(root_resolved)
        except ValueError:
            raise ValueError("Challenge path escapes store")
        return direct

    def create(
        self,
        *,
        title: str,
        platform_url: str,
        event: str = "",
    ) -> dict[str, Any]:
        challenge_id = f"{slug(title)}-{uuid.uuid4().hex[:8]}"
        event_slug = slug(event) if event.strip() else ""
        if event_slug:
            root = (self.root / event_slug / challenge_id).resolve()
            try:
                root.relative_to(self.root.resolve())
            except ValueError:
                raise ValueError("Challenge path escapes store")
        else:
            root = self.challenge_dir(challenge_id)
        for name in ("original", "work", "output", "reports"):
            (root / name).mkdir(parents=True)
        self._locations[challenge_id] = root
        state: dict[str, Any] = {
            "challenge_id": challenge_id,
            "title": title.strip() or "Untitled challenge",
            "event": event.strip(),
            "category": "reverse",
            "architecture": None,
            "bits": None,
            "platform_url": platform_url,
            "status": "importing",
            "created_at": utc_now(),
            "updated_at": utc_now(),
            "solve_started_at": None,
            "research_started_at": None,
            "solved_at": None,
            "finished_at": None,
            "blocker": "",
            "exit_reason": None,
            "flags": [],
            "local_answers": [],
            "result_evidence": [],
            "artifacts": [],
            "tool_runs": [],
            "solution_searches": [],
            "hypotheses": [],
            "intents": [],
            "facts": [],
        }
        self.save(state)
        return state

    def load(self, challenge_id: str) -> dict[str, Any]:
        return self._read_state(self.challenge_dir(challenge_id) / "progress.md")

    @staticmethod
    def _read_state(path: Path) -> dict[str, Any]:
        try:
            text = path.read_text(encoding="utf-8")
            payload = text.split("<!-- reverser-state\n", 1)[1].split("\n-->", 1)[0]
            value = json.loads(payload)
        except (OSError, IndexError, json.JSONDecodeError) as exc:
            raise FileNotFoundError(f"Unknown or invalid challenge: {path.parent.name}") from exc
        if not isinstance(value, dict):
            raise FileNotFoundError(f"Invalid challenge state: {path.parent.name}")
        return value

    def save(self, state: dict[str, Any]) -> None:
        state["updated_at"] = utc_now()
        tools = state.get("tool_runs", [])
        clean = lambda value: str(value).replace("\r", " ").replace("\n", " ").strip()
        lines = [
            f"# CTF progress: {state['title']}",
            "",
            f"- ID: `{state['challenge_id']}`",
            f"- Status: `{state['status']}`",
            f"- Target: `{state.get('architecture') or '-'} / {state.get('bits') or '-'}`",
            f"- Commands: `{len(tools)}`",
            f"- Flag candidates: `{len(state.get('flags', []))}`",
            f"- Local answers: `{len(state.get('local_answers', []))}`",
            f"- Elapsed: `{solve_elapsed_seconds(state)}s`",
            f"- Research started: `{state.get('research_started_at') or '-'}`",
            f"- Updated: `{state['updated_at']}`",
        ]
        hypotheses = state.get("hypotheses", [])
        active = next((item for item in hypotheses if item.get("status") == "testing"), None)
        phase = ("done" if state.get("status") in {"solved", "local_verified", "unsolved", "failed"}
                 else "verify" if active else "hypothesize" if hypotheses else "recon")
        lines.extend(["", "## Solver", "", f"- Phase: `{phase}`"])
        if active:
            lines.extend([
                "", "## Current hypothesis", "", f"### {clean(active.get('id', '-'))}",
                f"- Claim: {clean(active.get('claim', ''))}",
                f"- Parent: {clean(active.get('parent_id') or '-')} (basis run: {active.get('basis_run', '-')})",
                f"- Test: {clean(active.get('test', ''))}",
                f"- Falsifier: {clean(active.get('falsifier', ''))}",
                f"- Exhaustion: {clean(active.get('exhaustion', ''))}",
                f"- Evidence: {', '.join(map(str, active.get('evidence_runs', []))) or '-'}",
                "- Status: `testing`",
            ])
        history = [item for item in hypotheses if item.get("status") != "testing"]
        if history:
            lines.extend(["", "## Hypothesis history", ""])
            by_id = {item.get("id"): item for item in hypotheses}
            for item in history:
                runs = ", ".join(map(str, item.get("evidence_runs", []))) or "-"
                depth, parent = 0, item.get("parent_id")
                while parent in by_id and depth < len(hypotheses):
                    depth += 1
                    parent = by_id[parent].get("parent_id")
                lines.append(f"{'  ' * depth}- `{clean(item.get('id', '-'))}` `{clean(item.get('status', '-'))}` — {clean(item.get('claim', ''))} — {clean(item.get('observation', ''))} (basis: {item.get('basis_run', '-')}; runs: {runs})")
        intents = state.get("intents", [])
        if intents:
            lines.extend(["", "## Intent chain", ""])
            for item in intents:
                lines.append(f"- `{clean(item['id'])}` `{clean(item['status'])}` ← `{clean(item.get('parent_id') or '-')}`: {clean(item['summary'])}")
        facts = state.get("facts", [])
        if facts:
            lines.extend(["", "## Facts", ""])
            for item in facts:
                lines.append(f"- `{clean(item['id'])}` ({clean(item.get('confidence', 'observed'))}, run {item['evidence_run']}): {clean(item['summary'])}")
        evidence = state.get("result_evidence", [])
        if evidence:
            lines.extend(["", "## Result evidence", ""])
            for item in evidence:
                lines.append(f"- `{clean(item.get('kind', '-'))}` from run {item.get('evidence_run', '-')} (value private)")
        if state.get("blocker"):
            lines.extend(["", "## Blocker", "", str(state["blocker"])])
        searches = state.get("solution_searches", [])
        if searches:
            lines.extend(["", "## Solution searches", ""])
            for item in searches:
                lines.append(f"- `{item.get('time', '-')}` {item.get('query', '')}")
        lines.extend(
            [
                "",
                "## Commands",
                "",
                "| # | Profile | Exit | Command |",
                "|---:|---|---:|---|",
            ]
        )
        for item in tools:
            command = str(item.get("command", "")).replace("|", "\\|").replace("\n", " ")
            lines.append(f"| {item['sequence']} | {item['profile']} | {item['exit_code']} | `{command}` |")
        metadata = json.dumps(state, ensure_ascii=False, separators=(",", ":"))
        atomic_write_text(
            self.challenge_dir(str(state["challenge_id"])) / "progress.md",
            f"<!-- reverser-state\n{metadata}\n-->\n\n" + "\n".join(lines) + "\n",
        )

    def list(self) -> list[dict[str, Any]]:
        items = []
        for path in self.root.rglob("progress.md"):
            try:
                value = self._read_state(path)
            except FileNotFoundError:
                continue
            self._locations[str(value["challenge_id"])] = path.parent.resolve()
            items.append(value)
        return sorted(items, key=lambda item: item.get("updated_at", ""), reverse=True)

    def start_solver(self, challenge_id: str, terminal: str) -> dict[str, Any]:
        self.load(challenge_id)
        path = self.challenge_dir(challenge_id) / "solver.json"
        value = {"challenge_id": challenge_id, "status": "running", "terminal": terminal, "result": None}
        atomic_write_json(path, value)
        return {**value, "path": str(path)}

    def finish_solver(self, challenge_id: str) -> dict[str, Any]:
        result = str(self.load(challenge_id).get("status", ""))
        if result not in {"solved", "local_verified", "unsolved", "failed"}:
            raise RuntimeError("Solver must record a terminal challenge state before finishing")
        path = self.challenge_dir(challenge_id) / "solver.json"
        try:
            terminal = str(json.loads(path.read_text(encoding="utf-8")).get("terminal", ""))
        except (OSError, json.JSONDecodeError):
            terminal = ""
        value = {"challenge_id": challenge_id, "status": "done", "terminal": terminal, "result": result}
        atomic_write_json(path, value)
        return {**value, "path": str(path)}

    def update_hypothesis(
        self,
        challenge_id: str,
        action: str,
        *,
        intent_id: str = "",
        hypothesis_id: str = "",
        parent_id: str = "",
        basis_run: int | None = None,
        claim: str = "",
        test: str = "",
        falsifier: str = "",
        exhaustion: str = "",
        outcome: str = "",
        evidence_run: int | None = None,
        observation: str = "",
    ) -> dict[str, Any]:
        state = self.load(challenge_id)
        hypotheses = state.setdefault("hypotheses", [])
        active = next((item for item in hypotheses if item.get("status") == "testing"
                       and (not intent_id or item.get("intent_id") == intent_id)), None)
        if action == "propose":
            if state.get("status") not in {"solving", "researching"}:
                raise RuntimeError("Run triage before proposing a hypothesis")
            if active:
                raise RuntimeError("Resolve the active hypothesis before proposing another")
            values = [claim.strip(), test.strip(), falsifier.strip(), exhaustion.strip()]
            if any(not value or len(value) > 1000 for value in values):
                raise ValueError("claim, test, falsifier, and exhaustion are required")
            if basis_run not in {item.get("sequence") for item in state.get("tool_runs", [])}:
                raise ValueError("A valid basis_run is required")
            parent = next((item for item in hypotheses if item.get("id") == parent_id), None) if parent_id else None
            if parent_id and (parent is None or parent.get("status") in {"testing", "rejected"}):
                raise ValueError("parent_id must name a resolved, non-rejected hypothesis")
            active = {
                "id": f"h{len(hypotheses) + 1}", "claim": values[0], "test": values[1],
                "falsifier": values[2], "exhaustion": values[3], "status": "testing", "evidence_runs": [],
                "parent_id": parent_id or None, "basis_run": basis_run, "intent_id": intent_id or None,
            }
            hypotheses.append(active)
        elif action == "resolve":
            if not active or active.get("id") != hypothesis_id:
                raise RuntimeError("Unknown active hypothesis")
            if outcome not in {"confirmed", "rejected", "inconclusive"} or evidence_run is None or not observation.strip():
                raise ValueError("outcome, evidence_run, and observation are required")
            runs = [item for item in state.get("tool_runs", []) if item.get("hypothesis_id") == hypothesis_id]
            if evidence_run not in {item.get("sequence") for item in runs}:
                raise RuntimeError("Evidence run does not belong to the active hypothesis")
            active["status"] = outcome
            active["observation"] = observation.strip()
            active["evidence_runs"] = [item["sequence"] for item in runs]
        else:
            raise ValueError("Unknown hypothesis action")
        self.save(state)
        return {"phase": "verify" if action == "propose" else "hypothesize", "hypothesis": active}

    def add_intent(self, challenge_id: str, summary: str, parent_id: str = "") -> dict[str, Any]:
        state = self.load(challenge_id)
        if state.get("status") not in {"solving", "researching"}:
            raise RuntimeError("Run triage before adding an intent")
        summary = summary.strip()
        if not summary or len(summary) > 1000:
            raise ValueError("Intent summary is required (maximum 1000 characters)")
        intents = state.setdefault("intents", [])
        if parent_id and not any(item["id"] == parent_id for item in intents):
            raise ValueError("Unknown parent intent")
        intent = {"id": f"i{len(intents) + 1}", "summary": summary, "parent_id": parent_id or None,
                  "status": "open", "created_at": utc_now(), "evidence_runs": []}
        intents.append(intent)
        self.save(state)
        return intent

    def finish_intent(self, challenge_id: str, intent_id: str, status: str, evidence_run: int | None = None) -> dict[str, Any]:
        state = self.load(challenge_id)
        intent = next((item for item in state.get("intents", []) if item["id"] == intent_id), None)
        if intent is None or intent["status"] != "open":
            raise ValueError("Unknown open intent")
        if status not in {"done", "blocked"}:
            raise ValueError("Intent status must be done or blocked")
        if evidence_run is not None:
            run = next((item for item in state.get("tool_runs", []) if item["sequence"] == evidence_run), None)
            if run is None or run.get("intent_id") != intent_id:
                raise ValueError("Evidence run must belong to the intent")
            intent["evidence_runs"] = sorted(set([*intent.get("evidence_runs", []), evidence_run]))
        intent["status"] = status
        intent["finished_at"] = utc_now()
        self.save(state)
        return intent

    def record_fact(self, challenge_id: str, summary: str, detail: str, evidence_run: int,
                    intent_id: str = "", confidence: str = "observed") -> dict[str, Any]:
        state = self.load(challenge_id)
        if confidence not in {"observed", "inferred"}:
            raise ValueError("Confidence must be observed or inferred")
        if not summary.strip() or len(summary) > 1000 or len(detail) > 8000:
            raise ValueError("Invalid fact summary or detail")
        run = next((item for item in state.get("tool_runs", []) if item["sequence"] == evidence_run), None)
        if run is None:
            raise ValueError("Unknown evidence run")
        if intent_id and not any(item["id"] == intent_id for item in state.get("intents", [])):
            raise ValueError("Unknown intent")
        if intent_id and run.get("intent_id") != intent_id:
            raise ValueError("Evidence run must belong to the intent")
        facts = state.setdefault("facts", [])
        fact = {"id": f"f{len(facts) + 1}", "summary": summary.strip(), "detail": detail.strip(),
                "confidence": confidence, "evidence_run": evidence_run, "intent_id": intent_id or None,
                "created_at": utc_now()}
        facts.append(fact)
        self.save(state)
        return fact

    def add_original(self, state: dict[str, Any], source: Path, name: str | None = None) -> Path:
        source = source.resolve()
        if not source.is_file():
            raise FileNotFoundError(source)
        destination_dir = self.challenge_dir(state["challenge_id"]) / "original"
        filename = safe_filename(name or source.name)
        destination = destination_dir / filename
        counter = 1
        while destination.exists():
            destination = destination_dir / f"{Path(filename).stem}-{counter}{Path(filename).suffix}"
            counter += 1
        shutil.copyfile(source, destination)
        self.register_artifact(state, destination, "original")
        return destination

    def register_artifact(
        self, state: dict[str, Any], path: Path, kind: str
    ) -> dict[str, Any]:
        root = self.challenge_dir(state["challenge_id"])
        resolved = path.resolve()
        if root not in resolved.parents:
            raise ValueError("Artifact is outside challenge directory")
        entry = {
            "path": resolved.relative_to(root).as_posix(),
            "kind": kind,
            "size": resolved.stat().st_size,
            "sha256": sha256_file(resolved),
        }
        state["artifacts"] = [
            item for item in state["artifacts"] if item["path"] != entry["path"]
        ]
        state["artifacts"].append(entry)
        return entry
