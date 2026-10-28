"""Command-line interface for the Reverser."""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .analysis import Analyzer
from .config import PROFILES, Settings
from .docker_backend import BackendError, DockerWorker
from .importer import ChallengeImporter
from .memory import TechniqueMemory
from .orchestration import TaskDB
from .storage import ChallengeStore, public_state
from .writeup import WriteupManager


PROJECT_ROOT = Path(os.environ.get("REVERSER_PROJECT_ROOT", Path(__file__).resolve().parents[2])).resolve()


def emit(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def visible(state: dict[str, Any], settings: Settings) -> dict[str, Any]:
    private = []
    if os.environ.get("REVERSER_ROLE") and state.get("challenge_id"):
        private = [item["value"] for item in TaskDB().candidates(state["challenge_id"], include_value=True)]
    value = public_state({**state, "flags": [*state.get("flags", []), *private]})
    value["flag_candidates"] = len(state.get("flags", []))
    value["research_after_seconds"] = settings.research_after_seconds
    value["research_due"] = (
        value["elapsed_seconds"] >= settings.research_after_seconds
        and state.get("status") not in {"solved", "local_verified", "unsolved", "failed"}
    )
    return value


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="reverser-harness")
    result.add_argument("--version", action="version", version=__version__)
    sub = result.add_subparsers(dest="action", required=True)
    sub.add_parser("doctor")
    sub.add_parser("list")

    solver_start = sub.add_parser("solver-start")
    solver_start.add_argument("challenge_id")
    solver_start.add_argument("--terminal", required=True)
    solver_finish = sub.add_parser("solver-finish")
    solver_finish.add_argument("challenge_id")

    status = sub.add_parser("status")
    status.add_argument("challenge_id")

    hypothesis = sub.add_parser("hypothesis")
    hypothesis.add_argument("challenge_id")
    hypothesis.add_argument("hypothesis_action", choices=("propose", "resolve"))
    hypothesis.add_argument("--hypothesis-id", default="")
    hypothesis.add_argument("--parent-id", default="")
    hypothesis.add_argument("--basis-run", type=int)
    hypothesis.add_argument("--claim", default="")
    hypothesis.add_argument("--test", default="")
    hypothesis.add_argument("--falsifier", default="")
    hypothesis.add_argument("--exhaustion", default="")
    hypothesis.add_argument("--outcome", default="")
    hypothesis.add_argument("--evidence-run", type=int)
    hypothesis.add_argument("--observation", default="")

    intent = sub.add_parser("intent")
    intent.add_argument("challenge_id")
    intent.add_argument("intent_action", choices=("add", "finish"))
    intent.add_argument("--summary", default="")
    intent.add_argument("--parent-id", default="")
    intent.add_argument("--intent-id", default="")
    intent.add_argument("--status", default="")
    intent.add_argument("--evidence-run", type=int)

    fact = sub.add_parser("fact")
    fact.add_argument("challenge_id")
    fact.add_argument("--summary", required=True)
    fact.add_argument("--detail", default="")
    fact.add_argument("--evidence-run", type=int, required=True)
    fact.add_argument("--intent-id", default="")
    fact.add_argument("--confidence", choices=("observed", "inferred"), default="observed")

    file_read = sub.add_parser("file-read")
    file_read.add_argument("challenge_id")
    file_read.add_argument("--path", required=True)
    file_write = sub.add_parser("file-write")
    file_write.add_argument("challenge_id")
    file_write.add_argument("--path", required=True)
    file_write.add_argument("--content", required=True)

    candidate = sub.add_parser("candidate")
    candidate.add_argument("challenge_id")
    candidate.add_argument("--value", required=True)
    candidate.add_argument("--kind", choices=("flag", "local_solution"), required=True)
    candidate.add_argument("--evidence-run", type=int, required=True)
    candidate.add_argument("--intent-id", required=True)
    context = sub.add_parser("candidate-context")
    context.add_argument("challenge_id")
    context.add_argument("--candidate-id", type=int, required=True)
    verify = sub.add_parser("verify-candidate")
    verify.add_argument("challenge_id")
    verify.add_argument("--candidate-id", type=int, required=True)
    verify.add_argument("--evidence-run", type=int, required=True)
    verify.add_argument("--verdict", choices=("confirmed", "rejected"), required=True)

    local = sub.add_parser("import-local")
    local.add_argument("--title", required=True)
    local.add_argument("--file", action="append", type=Path, required=True)
    local.add_argument("--url", default="")
    local.add_argument("--event", default="")
    local.add_argument("--description-file", type=Path)

    triage = sub.add_parser("triage")
    triage.add_argument("challenge_id")
    execute = sub.add_parser("exec")
    execute.add_argument("challenge_id")
    execute.add_argument("--profile", choices=sorted(PROFILES), required=True)
    execute.add_argument("--command", required=True)
    execute.add_argument("--timeout", type=int)
    execute.add_argument("--hypothesis")
    execute.add_argument("--intent-id")

    review_exec = sub.add_parser("review-exec")
    review_exec.add_argument("challenge_id")
    review_exec.add_argument("--profile", choices=sorted(PROFILES), required=True)
    review_exec.add_argument("--command", required=True)
    review_exec.add_argument("--timeout", type=int)

    flag = sub.add_parser("flag")
    flag.add_argument("challenge_id")
    flag.add_argument("--value", required=True)
    flag.add_argument("--evidence-run", type=int, required=True)
    flag.add_argument("--kind", choices=("flag", "local_solution"), required=True)
    writeup = sub.add_parser("writeup")
    writeup.add_argument("challenge_id")
    writeup.add_argument("--file", type=Path, required=True)

    unsolved = sub.add_parser("unsolved")
    unsolved.add_argument("challenge_id")
    unsolved.add_argument("--reason-file", type=Path, required=True)
    terminate = sub.add_parser("terminate")
    terminate.add_argument("challenge_id")
    terminate.add_argument("--reason", required=True)
    search = sub.add_parser("solution-search")
    search.add_argument("challenge_id")
    search.add_argument("query")
    search.add_argument("--limit", type=int)
    learn = sub.add_parser("learn")
    learn.add_argument("challenge_id")
    learn.add_argument("--file", type=Path, required=True)

    return result


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    args = parser().parse_args(argv)
    try:
        assigned_challenge = os.environ.get("REVERSER_CHALLENGE_ID", "")
        if os.environ.get("REVERSER_ROLE") and assigned_challenge and getattr(args, "challenge_id", assigned_challenge) != assigned_challenge:
            raise ValueError("Tool call is outside the assigned challenge")
        settings = Settings.load(PROJECT_ROOT)
        store = ChallengeStore(PROJECT_ROOT / "runs")
        if args.action == "doctor":
            docker: dict[str, Any]
            try:
                docker = DockerWorker(settings).doctor()
            except BackendError as exc:
                docker = {"docker": None, "error": str(exc), "core_ready": False}
            emit({
                "project": settings.project_name,
                "python": sys.executable,
                "docker": docker,
            })
            return 0
        if args.action == "list":
            emit([visible(item, settings) for item in store.list()])
            return 0
        if args.action == "status":
            state = visible(store.load(args.challenge_id), settings)
            state["workspace"] = str(store.challenge_dir(args.challenge_id))
            emit(state)
            return 0
        if args.action == "hypothesis":
            if os.environ.get("REVERSER_ROLE") and os.environ["REVERSER_ROLE"] != "worker":
                raise ValueError("Only workers may record hypotheses")
            emit(store.update_hypothesis(
                args.challenge_id, args.hypothesis_action,
                intent_id=os.environ.get("REVERSER_INTENT_ID", ""),
                hypothesis_id=args.hypothesis_id, parent_id=args.parent_id, basis_run=args.basis_run,
                claim=args.claim, test=args.test,
                falsifier=args.falsifier, exhaustion=args.exhaustion, outcome=args.outcome,
                evidence_run=args.evidence_run, observation=args.observation,
            ))
            return 0
        if args.action == "intent":
            if os.environ.get("REVERSER_ROLE") and os.environ["REVERSER_ROLE"] != "planner":
                raise ValueError("Only the planner may create web task intents")
            if os.environ.get("REVERSER_ROLE") and args.intent_action != "add":
                raise ValueError("Web intent completion belongs to the scheduler")
            if args.intent_action == "add":
                emit(store.add_intent(args.challenge_id, args.summary, args.parent_id))
            else:
                emit(store.finish_intent(args.challenge_id, args.intent_id, args.status, args.evidence_run))
            return 0
        if args.action == "fact":
            if os.environ.get("REVERSER_ROLE") and os.environ["REVERSER_ROLE"] != "worker":
                raise ValueError("Only workers may record facts")
            active_intent = os.environ.get("REVERSER_INTENT_ID", "")
            if active_intent and args.intent_id != active_intent:
                raise ValueError("Fact must belong to the assigned intent")
            emit(store.record_fact(args.challenge_id, args.summary, args.detail, args.evidence_run,
                                   args.intent_id, args.confidence))
            return 0
        if args.action in {"file-read", "file-write"}:
            intent_id = os.environ.get("REVERSER_INTENT_ID", "")
            if os.environ.get("REVERSER_ROLE") not in {"worker", "verifier"} or not intent_id:
                raise ValueError("Scoped files require an assigned worker")
            rel = Path(args.path.replace("\\", "/"))
            if rel.is_absolute() or ".." in rel.parts or not rel.parts:
                raise ValueError("Invalid workspace path")
            root = store.challenge_dir(args.challenge_id)
            base = root / "work" / "intents" / intent_id
            if args.action == "file-read" and rel.parts[0] == "original":
                base = root
            target = (base / rel).resolve()
            if base.resolve() not in target.parents:
                raise ValueError("File is outside the assigned workspace")
            if args.action == "file-read":
                if target.stat().st_size > 1_000_000:
                    raise ValueError("Use reverser_exec for large or binary files")
                emit({"path": str(rel), "content": target.read_text(encoding="utf-8")})
            else:
                if len(args.content) > 100_000:
                    raise ValueError("File content is too large")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(args.content, encoding="utf-8", newline="\n")
                emit({"path": str(rel), "written": True})
            return 0
        if args.action == "candidate-context":
            if os.environ.get("REVERSER_ROLE") != "verifier":
                raise ValueError("Candidate context is verifier-only")
            value = TaskDB().candidate(args.challenge_id, args.candidate_id)
            if not value or value["status"] != "pending":
                raise ValueError("Unknown pending candidate")
            if os.environ.get("REVERSER_INTENT_ID") != f"v{args.candidate_id}":
                raise ValueError("Candidate is outside the assigned verifier session")
            emit({"candidate_id": value["id"], "kind": value["kind"], "value": value["value"],
                  "proposal_run": value["evidence_run"]})
            return 0
        if args.action == "solver-start":
            emit(store.start_solver(args.challenge_id, args.terminal))
            return 0
        if args.action == "solver-finish":
            emit(store.finish_solver(args.challenge_id))
            return 0
        if args.action == "import-local":
            description = args.description_file.read_text(encoding="utf-8") if args.description_file else ""
            state = ChallengeImporter(store).import_local(title=args.title, files=args.file, platform_url=args.url, event=args.event, description=description)
            emit(visible(state, settings))
            return 0
        if args.action == "solution-search":
            local_results = TechniqueMemory(PROJECT_ROOT, store).search_for_challenge(
                args.challenge_id,
                args.query,
                settings.research_after_seconds,
                args.limit or settings.memory_search_limit,
            )
            emit({"local": local_results})
            return 0
        if args.action == "learn":
            emit({"saved_path": str(TechniqueMemory(PROJECT_ROOT, store).save_lesson(
                args.challenge_id, args.file.read_text(encoding="utf-8"), settings.research_after_seconds
            ))})
            return 0

        analyzer = Analyzer(store, DockerWorker(settings))
        if args.action == "triage":
            state, result = analyzer.triage(args.challenge_id)
            emit({"state": visible(state, settings), "exit_code": result.exit_code, "stdout": result.stdout, "stderr": result.stderr})
        elif args.action == "exec":
            if os.environ.get("REVERSER_ROLE") and os.environ["REVERSER_ROLE"] != "worker":
                raise ValueError("Only workers may run analysis commands")
            active_intent = os.environ.get("REVERSER_INTENT_ID", "")
            if active_intent and args.intent_id != active_intent:
                raise ValueError("Command must belong to the assigned intent")
            state, result = analyzer.run_command(args.challenge_id, args.profile, args.command, args.timeout, args.hypothesis, args.intent_id)
            emit({"state": visible(state, settings), "exit_code": result.exit_code, "stdout": result.stdout, "stderr": result.stderr, "timed_out": result.timed_out, "truncated": result.truncated})
        elif args.action == "review-exec":
            if os.environ.get("REVERSER_ROLE") and os.environ["REVERSER_ROLE"] != "verifier":
                raise ValueError("Only verifiers may run review commands")
            state, result = analyzer.review_command(args.challenge_id, args.profile, args.command, args.timeout)
            emit({"state": visible(state, settings), "exit_code": result.exit_code, "stdout": result.stdout, "stderr": result.stderr, "timed_out": result.timed_out, "truncated": result.truncated})
        elif args.action == "flag":
            if os.environ.get("REVERSER_ROLE"):
                raise ValueError("Web candidates require independent verification")
            state = analyzer.record_flag(args.challenge_id, args.value, args.evidence_run, args.kind)
            emit({"state": visible(state, settings), "recorded": True})
        elif args.action == "candidate":
            if os.environ.get("REVERSER_ROLE") != "worker" or os.environ.get("REVERSER_INTENT_ID") != args.intent_id:
                raise ValueError("Candidate must belong to the assigned worker intent")
            analyzer.check_candidate(args.challenge_id, args.value, args.evidence_run, args.kind)
            run = next((item for item in store.load(args.challenge_id)["tool_runs"] if item["sequence"] == args.evidence_run), None)
            if not run or run.get("intent_id") != args.intent_id:
                raise ValueError("Candidate evidence must belong to the worker intent")
            candidate_id = TaskDB().add_candidate(args.challenge_id, args.intent_id, args.kind, args.value, args.evidence_run)
            emit({"candidate_id": candidate_id, "status": "pending"})
        elif args.action == "verify-candidate":
            if os.environ.get("REVERSER_ROLE") != "verifier":
                raise ValueError("Verification is verifier-only")
            if os.environ.get("REVERSER_INTENT_ID") != f"v{args.candidate_id}":
                raise ValueError("Candidate is outside the assigned verifier session")
            db = TaskDB()
            candidate = db.candidate(args.challenge_id, args.candidate_id)
            if not candidate or candidate["status"] != "pending":
                raise ValueError("Unknown pending candidate")
            run = next((item for item in store.load(args.challenge_id)["tool_runs"] if item["sequence"] == args.evidence_run), None)
            if (not run or run.get("phase") != "review" or
                    run.get("intent_id") != f"v{args.candidate_id}" or
                    args.evidence_run == candidate["evidence_run"]):
                raise ValueError("Independent review run is required")
            if args.verdict == "confirmed":
                state = analyzer.record_flag(args.challenge_id, candidate["value"], args.evidence_run, candidate["kind"])
                db.set_candidate(args.challenge_id, args.candidate_id, "verified", args.evidence_run)
                emit({"status": state["status"], "candidate_id": args.candidate_id})
            else:
                db.set_candidate(args.challenge_id, args.candidate_id, "rejected", args.evidence_run)
                emit({"status": "rejected", "candidate_id": args.candidate_id})
        elif args.action == "unsolved":
            state = analyzer.mark_unsolved(
                args.challenge_id, args.reason_file.read_text(encoding="utf-8")
            )
            emit(visible(state, settings))
        elif args.action == "terminate":
            state = analyzer.terminate(args.challenge_id, args.reason)
            emit(visible(state, settings))
        elif args.action == "writeup":
            emit(WriteupManager(store).save(args.challenge_id, args.file.read_text(encoding="utf-8")))
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
