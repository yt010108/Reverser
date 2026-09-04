"""Command-line interface for the Reverser."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .analysis import Analyzer
from .config import PROFILES, Settings
from .docker_backend import BackendError, DockerWorker
from .importer import ChallengeImporter
from .memory import TechniqueMemory
from .storage import ChallengeStore, public_state
from .writeup import WriteupManager


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def emit(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def visible(state: dict[str, Any], settings: Settings) -> dict[str, Any]:
    value = public_state(state)
    value["research_after_seconds"] = settings.research_after_seconds
    value["research_due"] = (
        value["elapsed_seconds"] >= settings.research_after_seconds
        and state.get("status") not in {"solved", "unsolved", "failed"}
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
    hypothesis.add_argument("--claim", default="")
    hypothesis.add_argument("--test", default="")
    hypothesis.add_argument("--falsifier", default="")
    hypothesis.add_argument("--exhaustion", default="")
    hypothesis.add_argument("--outcome", default="")
    hypothesis.add_argument("--evidence-run", type=int)
    hypothesis.add_argument("--observation", default="")

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

    flag = sub.add_parser("flag")
    flag.add_argument("challenge_id")
    flag.add_argument("--value", required=True)
    flag.add_argument("--evidence-run", type=int, required=True)
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
            emit(store.update_hypothesis(
                args.challenge_id, args.hypothesis_action,
                hypothesis_id=args.hypothesis_id, claim=args.claim, test=args.test,
                falsifier=args.falsifier, exhaustion=args.exhaustion, outcome=args.outcome,
                evidence_run=args.evidence_run, observation=args.observation,
            ))
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
                args.challenge_id, args.file.read_text(encoding="utf-8")
            ))})
            return 0

        analyzer = Analyzer(store, DockerWorker(settings))
        if args.action == "triage":
            state, result = analyzer.triage(args.challenge_id)
            emit({"state": visible(state, settings), "exit_code": result.exit_code, "stdout": result.stdout, "stderr": result.stderr})
        elif args.action == "exec":
            state, result = analyzer.run_command(args.challenge_id, args.profile, args.command, args.timeout, args.hypothesis)
            emit({"state": visible(state, settings), "exit_code": result.exit_code, "stdout": result.stdout, "stderr": result.stderr, "timed_out": result.timed_out, "truncated": result.truncated})
        elif args.action == "flag":
            state = analyzer.record_flag(args.challenge_id, args.value, args.evidence_run)
            emit({"state": visible(state, settings), "recorded": True})
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
