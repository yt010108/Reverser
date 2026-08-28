"""Command-line interface for the Reverser."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .analysis import Analyzer
from .config import PROFILES, Settings
from .dashboard import build_dashboard
from .docker_backend import BackendError, DockerWorker
from .importer import ChallengeImporter
from .memory import TechniqueMemory
from .storage import ChallengeStore, public_state
from .writeup import WriteupManager


PROJECT_ROOT = Path(__file__).resolve().parents[2]


# JSON을 pretty-print로 stdout에 출력
def emit(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def visible(state: dict[str, Any]) -> dict[str, Any]:
    return public_state(state)


def catalog(store: ChallengeStore, settings: Settings) -> dict[str, Any]:
    challenges = []
    for item in store.list():
        state = visible(item)
        challenges.append({
            key: state.get(key)
            for key in ("challenge_id", "title", "event", "status", "architecture", "bits", "updated_at", "elapsed_seconds")
        } | {"flag_count": len(state.get("flags", []))})
    events = sorted({str(item.get("event")) for item in challenges if item.get("event")})
    return {
        "project": {"name": settings.project_name, "root": str(settings.project_root)},
        "events": events,
        "challenges": challenges,
    }


# reverser CLI의 argparse 파서 구성
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
    reviewer_start = sub.add_parser("reviewer-start")
    reviewer_start.add_argument("challenge_id")
    reviewer_start.add_argument("--terminal", required=True)
    reviewer_finish = sub.add_parser("reviewer-finish")
    reviewer_finish.add_argument("challenge_id")
    reviewer_finish.add_argument("--failed", action="store_true")

    status = sub.add_parser("status")
    status.add_argument("challenge_id")

    recon = sub.add_parser("recon")
    recon.add_argument("challenge_id")
    recon.add_argument("--entry-point", required=True)
    recon.add_argument("--main", default="")
    recon.add_argument("--evidence-run", action="append", type=int, required=True)
    recon.add_argument("--candidates-json", required=True)

    hypothesis = sub.add_parser("hypothesis")
    hypothesis.add_argument("challenge_id")
    hypothesis.add_argument("hypothesis_action", choices=("propose", "resolve"))
    hypothesis.add_argument("--hypothesis-id", default="")
    hypothesis.add_argument("--target", default="")
    hypothesis.add_argument("--parent-id", default="")
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
    learn = sub.add_parser("learn")
    learn.add_argument("challenge_id")
    learn.add_argument("--file", type=Path, required=True)

    sub.add_parser("dashboard")
    return result


# CLI 진입점 — Settings/ChallengeStore 로드 후 각 액션별로 Analyzer/Importer 등을 호출해 JSON으로 응답
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
            emit(catalog(store, settings))
            return 0
        if args.action == "status":
            state = visible(store.load(args.challenge_id))
            state["workspace"] = str(store.challenge_dir(args.challenge_id))
            emit(state)
            return 0
        if args.action == "recon":
            candidates = json.loads(args.candidates_json)
            if not isinstance(candidates, list):
                raise ValueError("candidates-json must be an array")
            emit(store.update_recon(
                args.challenge_id, entry_point=args.entry_point, main=args.main,
                evidence_runs=args.evidence_run, flag_candidates=candidates,
            ))
            return 0
        if args.action == "hypothesis":
            emit(store.update_hypothesis(
                args.challenge_id, args.hypothesis_action,
                hypothesis_id=args.hypothesis_id, target=args.target, parent_id=args.parent_id,
                claim=args.claim, test=args.test,
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
        if args.action == "reviewer-start":
            emit(store.start_reviewer(args.challenge_id, args.terminal))
            return 0
        if args.action == "reviewer-finish":
            emit(store.finish_reviewer(args.challenge_id, args.failed))
            return 0
        if args.action == "import-local":
            description = args.description_file.read_text(encoding="utf-8") if args.description_file else ""
            state = ChallengeImporter(store).import_local(title=args.title, files=args.file, platform_url=args.url, event=args.event, description=description)
            emit(visible(state))
            return 0
        if args.action == "dashboard":
            emit({"dashboard": str(build_dashboard(store))})
            return 0
        if args.action == "learn":
            emit({"saved_path": str(TechniqueMemory(PROJECT_ROOT, store).save_lesson(
                args.challenge_id, args.file.read_text(encoding="utf-8")
            ))})
            return 0

        analyzer = Analyzer(store, DockerWorker(settings))
        if args.action == "triage":
            state, result = analyzer.triage(args.challenge_id)
            emit({"state": visible(state), "exit_code": result.exit_code, "stdout": result.stdout, "stderr": result.stderr})
        elif args.action == "exec":
            state, result = analyzer.run_command(args.challenge_id, args.profile, args.command, args.timeout, args.hypothesis)
            emit({"state": visible(state), "exit_code": result.exit_code, "stdout": result.stdout, "stderr": result.stderr, "timed_out": result.timed_out, "truncated": result.truncated})
        elif args.action == "flag":
            state = analyzer.record_flag(args.challenge_id, args.value, args.evidence_run)
            emit({"state": visible(state), "recorded": True})
        elif args.action == "unsolved":
            state = analyzer.mark_unsolved(
                args.challenge_id, args.reason_file.read_text(encoding="utf-8")
            )
            emit(visible(state))
        elif args.action == "terminate":
            state = analyzer.terminate(args.challenge_id, args.reason)
            emit(visible(state))
        elif args.action == "writeup":
            emit(WriteupManager(store).save(args.challenge_id, args.file.read_text(encoding="utf-8")))
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
