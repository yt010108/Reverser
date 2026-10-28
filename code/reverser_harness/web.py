"""Local web interface for importing and following reversing challenges."""

import asyncio
import json
import os
import re
import secrets
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .importer import ChallengeImporter
from .engine import WebEngine
from .orchestration import TaskDB
from .security import safe_filename, validate_id
from .storage import ChallengeStore, atomic_write_json, public_state


ROOT = Path(os.environ.get("REVERSER_PROJECT_ROOT", Path(__file__).resolve().parents[2])).resolve()
RUNS = Path(os.environ.get("REVERSER_RUNS_ROOT", ROOT / "runs")).resolve()
PRIVATE = Path(os.environ.get("REVERSER_PRIVATE_DIR", ROOT / ".private" / "web")).resolve()
STATIC = ROOT / "web"
PRIVATE.mkdir(parents=True, exist_ok=True)
STORE = ChallengeStore(RUNS)
CSRF_TOKEN = secrets.token_urlsafe(32)
SETTINGS_PATH = PRIVATE / "settings.json"
PI_AGENT_DIR = PRIVATE / "pi-agent"
AUTH_SOURCE = Path(os.environ.get("REVERSER_PI_AUTH_SOURCE", PRIVATE / "pi-auth-seed"))
MAX_UPLOAD = 128 * 1024 * 1024


def configured() -> dict[str, str]:
    try:
        value = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        if isinstance(value, dict):
            return {key: str(item) for key, item in value.items() if isinstance(item, str)}
    except (OSError, ValueError):
        pass
    return {"auth_mode": "oauth", "oauth_model": "openai-codex/gpt-6-sol", "api_model": "openai/gpt-5.1"}


def has_oauth() -> bool:
    return (PI_AGENT_DIR / "auth.json").is_file() or (AUTH_SOURCE / "auth.json").is_file()


def oauth_ready() -> bool:
    if not has_oauth() or not shutil.which("pi"):
        return False
    try:
        prepare_oauth()
        env = os.environ.copy()
        env["PI_CODING_AGENT_DIR"] = str(PI_AGENT_DIR)
        result = subprocess.run(
            ["pi", "auth", "check", "--provider", "openai-codex", "--json"],
            cwd=ROOT, env=env, capture_output=True, text=True, timeout=20, check=False,
        )
        return json.loads(result.stdout).get("status") == "ready"
    except (OSError, ValueError, subprocess.TimeoutExpired, HTTPException):
        return False


def visible_config() -> dict[str, Any]:
    value = configured()
    return {
        "auth_mode": value.get("auth_mode", "oauth"),
        "oauth_model": value.get("oauth_model", "openai-codex/gpt-6-sol"),
        "api_model": value.get("api_model", "openai/gpt-5.1"),
        "has_api_key": bool(value.get("api_key")),
        "oauth_available": has_oauth(),
        "oauth_ready": oauth_ready(),
    }


def prepare_oauth() -> None:
    PI_AGENT_DIR.mkdir(parents=True, exist_ok=True)
    for name in ("auth.json",):
        source = AUTH_SOURCE / name
        target = PI_AGENT_DIR / name
        if source.is_file() and (not target.exists() or source.stat().st_mtime_ns > target.stat().st_mtime_ns):
            shutil.copyfile(source, target)
            target.chmod(0o600)
    if not (PI_AGENT_DIR / "auth.json").is_file():
        raise HTTPException(409, "기존 Pi 로그인 정보를 찾지 못했습니다. 인증 원본 경로를 설정해 주세요.")


def solver_environment() -> tuple[dict[str, str], str]:
    value = configured()
    mode = value.get("auth_mode", "oauth")
    env = os.environ.copy()
    env["PI_CODING_AGENT_DIR"] = str(PI_AGENT_DIR)
    env["PYTHONPATH"] = str(ROOT / "code")
    if mode == "oauth":
        prepare_oauth()
        if not oauth_ready():
            raise HTTPException(409, "Pi 로그인이 만료되었습니다. 호스트 터미널에서 Pi에 다시 로그인한 뒤 재시도해 주세요.")
        env.pop("OPENAI_API_KEY", None)
        model = value.get("oauth_model", "openai-codex/gpt-6-sol").strip()
        if model and not model.startswith("openai-codex/"):
            raise HTTPException(400, "Pi 로그인 모델은 openai-codex/ 형식이어야 합니다.")
    elif mode == "api_key":
        key = value.get("api_key", "")
        if not key:
            raise HTTPException(409, "API 키를 먼저 저장해 주세요.")
        env["OPENAI_API_KEY"] = key
        model = value.get("api_model", "").strip()
        if not model.startswith("openai/"):
            raise HTTPException(400, "API 키 모델은 openai/ 형식이어야 합니다.")
    else:
        raise HTTPException(400, "알 수 없는 인증 방식입니다.")
    return env, model


class ConfigUpdate(BaseModel):
    auth_mode: str
    oauth_model: str = "openai-codex/gpt-6-sol"
    api_model: str = "openai/gpt-5.1"
    api_key: str = ""
    clear_api_key: bool = False


class ChatMessage(BaseModel):
    message: str


DB = TaskDB()
ENGINE = WebEngine(ROOT, PRIVATE, STORE, DB, solver_environment)
app = FastAPI(title="Reverser", docs_url=None, redoc_url=None)


@app.on_event("startup")
async def restore_tasks() -> None:
    await ENGINE.restore()


@app.on_event("shutdown")
async def stop_tasks() -> None:
    await ENGINE.shutdown()


def require_token(x_reverser_token: str = Header(default="")) -> None:
    if not secrets.compare_digest(x_reverser_token, CSRF_TOKEN):
        raise HTTPException(403, "잘못된 요청 토큰입니다.")


def challenge_view(challenge_id: str) -> dict[str, Any]:
    validate_id(challenge_id)
    raw = STORE.load(challenge_id)
    candidate_values = [item["value"] for item in DB.candidates(challenge_id, include_value=True)]
    state = public_state({**raw, "flags": [*raw.get("flags", []), *candidate_values]})
    state["flag_candidates"] = len(raw.get("flags", []))
    state["solver"] = ENGINE.view(challenge_id)
    return state


def graph_of(state: dict[str, Any]) -> dict[str, Any]:
    challenge_id = state["challenge_id"]
    task = DB.task(challenge_id)
    task_intents = {item["intent_id"]: item for item in DB.intents(challenge_id)}
    nodes = [{"id": "challenge", "kind": "challenge", "label": state["title"], "status": state["status"]}]
    edges: list[dict[str, str]] = []
    if task:
        nodes.append({"id": "goal", "kind": "goal", "label": task["goal"] or "제공된 자료에서 문제 해결", "status": task["status"]})
        edges.append({"from": "challenge", "to": "goal", "kind": "goal"})
    run_by_sequence = {item.get("sequence"): item for item in state.get("tool_runs", [])}
    for item in state.get("intents", []):
        node_id = "intent:" + item["id"]
        nodes.append({"id": node_id, "kind": "intent", "label": item["summary"],
                      "status": task_intents.get(item["id"], {}).get("status", item["status"]), "data": item})
        edges.append({"from": "intent:" + item["parent_id"] if item.get("parent_id") else
                      "goal" if task else "challenge", "to": node_id, "kind": "planned"})
    for item in state.get("hypotheses", []):
        node_id = "hypothesis:" + item["id"]
        nodes.append({"id": node_id, "kind": "hypothesis", "label": item["claim"], "status": item["status"], "data": item})
        basis = run_by_sequence.get(item.get("basis_run"), {})
        parent = ("hypothesis:" + item["parent_id"] if item.get("parent_id") else
                  "intent:" + basis["intent_id"] if basis.get("intent_id") else "challenge")
        edges.append({"from": parent, "to": node_id, "kind": "derived"})
    for item in state.get("facts", []):
        node_id = "fact:" + item["id"]
        nodes.append({"id": node_id, "kind": "fact", "label": item["summary"], "status": item["confidence"], "data": item})
        edges.append({"from": "intent:" + item["intent_id"] if item.get("intent_id") else "challenge", "to": node_id, "kind": "observed"})
    for item in DB.candidates(challenge_id):
        node_id = f"candidate:{item['id']}"
        nodes.append({"id": node_id, "kind": "candidate", "label": f"{item['kind']} 후보 #{item['id']}",
                      "status": item["status"], "data": item})
        edges.append({"from": "intent:" + item["intent_id"], "to": node_id, "kind": "proposed"})
        if item["status"] in {"verified", "rejected"}:
            verdict = f"verdict:{item['id']}"
            nodes.append({"id": verdict, "kind": "verdict", "label": "검증 성공" if item["status"] == "verified" else "검증 실패",
                          "status": item["status"], "data": {"evidence_run": item["verify_run"]}})
            edges.append({"from": node_id, "to": verdict, "kind": "verified"})
    return {"nodes": nodes, "edges": edges}


@app.exception_handler(FileNotFoundError)
async def missing(_request: Request, _exc: FileNotFoundError) -> JSONResponse:
    return JSONResponse({"detail": "문제를 찾을 수 없습니다."}, status_code=404)


@app.exception_handler(ValueError)
async def invalid(_request: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse({"detail": str(exc)}, status_code=400)


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"ok": True, "service": "reverser"}


@app.get("/api/config")
def get_config() -> dict[str, Any]:
    return visible_config()


@app.put("/api/config", dependencies=[Depends(require_token)])
def put_config(request: ConfigUpdate) -> dict[str, Any]:
    if request.auth_mode not in {"oauth", "api_key"}:
        raise HTTPException(400, "인증 방식을 선택해 주세요.")
    if request.oauth_model and not re.fullmatch(r"openai-codex/[A-Za-z0-9_.:-]+", request.oauth_model):
        raise HTTPException(400, "Pi 로그인 모델 형식이 올바르지 않습니다.")
    if not re.fullmatch(r"openai/[A-Za-z0-9_.:-]+", request.api_model):
        raise HTTPException(400, "API 키 모델 형식이 올바르지 않습니다.")
    value = configured()
    value.update({"auth_mode": request.auth_mode, "oauth_model": request.oauth_model.strip(),
                  "api_model": request.api_model.strip()})
    if request.clear_api_key:
        value.pop("api_key", None)
    elif request.api_key.strip():
        value["api_key"] = request.api_key.strip()
    atomic_write_json(SETTINGS_PATH, value)
    SETTINGS_PATH.chmod(0o600)
    return visible_config()


@app.get("/api/challenges")
def list_challenges() -> list[dict[str, Any]]:
    fields = ("challenge_id", "title", "event", "status", "created_at", "updated_at", "architecture", "bits")
    items = []
    for state in STORE.list():
        summary = {key: state.get(key) for key in fields}
        summary["flags"] = state.get("flags", [])
        summary["local_answers"] = state.get("local_answers", [])
        visible = public_state(summary)
        items.append({key: visible.get(key) for key in fields})
    return items


@app.post("/api/challenges", dependencies=[Depends(require_token)])
async def create_challenge(title: str = Form(...), event: str = Form(""), description: str = Form(""),
                           platform_url: str = Form(""), files: list[UploadFile] = File(...)) -> dict[str, Any]:
    if not 1 <= len(files) <= 8:
        raise HTTPException(400, "파일은 1~8개 첨부할 수 있습니다.")
    if len(title) > 160 or len(event) > 100 or len(description) > 20_000:
        raise HTTPException(400, "입력 내용이 너무 깁니다.")
    uploaded: list[Path] = []
    with tempfile.TemporaryDirectory(prefix="upload-", dir=PRIVATE) as temporary:
        total = 0
        for number, file in enumerate(files):
            name = safe_filename(file.filename or f"attachment-{number}")
            destination = Path(temporary) / name
            counter = 1
            while destination.exists():
                destination = Path(temporary) / f"{Path(name).stem}-{counter}{Path(name).suffix}"
                counter += 1
            with destination.open("wb") as stream:
                while chunk := await file.read(1024 * 1024):
                    total += len(chunk)
                    if total > MAX_UPLOAD:
                        raise HTTPException(413, "첨부 파일 총 크기는 128 MiB까지 허용됩니다.")
                    stream.write(chunk)
            uploaded.append(destination)
        state = ChallengeImporter(STORE).import_local(title=title, files=uploaded,
            platform_url=platform_url, event=event, description=description)
    return public_state(state)


@app.get("/api/challenges/{challenge_id}")
def get_challenge(challenge_id: str) -> dict[str, Any]:
    return challenge_view(challenge_id)


@app.get("/api/challenges/{challenge_id}/graph")
def get_graph(challenge_id: str) -> dict[str, Any]:
    return graph_of(challenge_view(challenge_id))


@app.get("/api/challenges/{challenge_id}/sessions")
def get_sessions(challenge_id: str) -> list[dict[str, Any]]:
    STORE.load(validate_id(challenge_id))
    return ENGINE.sessions(challenge_id)


@app.get("/api/challenges/{challenge_id}/activity")
def get_activity(challenge_id: str, since: int = 0, session: str = "", limit: int = 200) -> dict[str, Any]:
    STORE.load(validate_id(challenge_id))
    if since < 0 or len(session) > 100:
        raise ValueError("잘못된 활동 커서 또는 세션입니다.")
    items = [ENGINE.visible_activity(challenge_id, item)
             for item in DB.activities(challenge_id, since, session, limit)]
    return {"items": items, "last_seq": DB.last_seq(challenge_id)}


@app.get("/api/challenges/{challenge_id}/activity/stream")
async def stream_activity(challenge_id: str, request: Request, since: int = 0) -> StreamingResponse:
    STORE.load(validate_id(challenge_id))
    last_event_id = request.headers.get("last-event-id", "")
    if last_event_id.isdecimal():
        since = max(since, int(last_event_id))
    if since < 0:
        raise ValueError("잘못된 활동 커서입니다.")

    async def events():
        cursor = since
        quiet = 0
        while True:
            items = DB.activities(challenge_id, cursor, limit=100)
            if items:
                for item in items:
                    cursor = item["seq"]
                    payload = json.dumps(ENGINE.visible_activity(challenge_id, item), ensure_ascii=False)
                    yield f"id: {cursor}\nevent: activity\ndata: {payload}\n\n"
                quiet = 0
            else:
                await asyncio.sleep(1)
                quiet += 1
                if quiet >= 15:
                    yield ": keepalive\n\n"
                    quiet = 0

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


@app.get("/api/challenges/{challenge_id}/candidates")
def get_candidates(challenge_id: str) -> list[dict[str, Any]]:
    STORE.load(validate_id(challenge_id))
    return DB.candidates(challenge_id)


@app.get("/api/challenges/{challenge_id}/runs/{sequence}")
def get_run(challenge_id: str, sequence: int) -> dict[str, Any]:
    state = STORE.load(validate_id(challenge_id))
    run = next((item for item in state.get("tool_runs", []) if item["sequence"] == sequence), None)
    if run is None:
        raise HTTPException(404, "실행 기록을 찾을 수 없습니다.")
    root = STORE.challenge_dir(challenge_id)
    output = {}
    for key in ("stdout", "stderr"):
        path = (root / run[key]).resolve()
        if root not in path.parents:
            raise HTTPException(400, "잘못된 실행 경로입니다.")
        output[key] = path.read_text(encoding="utf-8", errors="replace")[:100_000]
    candidate_values = [item["value"] for item in DB.candidates(challenge_id, include_value=True)]
    return public_state({"run": run, **output, "flags": [*state.get("flags", []), *candidate_values],
                         "local_answers": state.get("local_answers", [])})


@app.post("/api/challenges/{challenge_id}/solve", dependencies=[Depends(require_token)])
async def solve(challenge_id: str) -> dict[str, Any]:
    return await ENGINE.start(validate_id(challenge_id))


@app.post("/api/challenges/{challenge_id}/stop", dependencies=[Depends(require_token)])
async def stop(challenge_id: str) -> dict[str, Any]:
    return await ENGINE.pause(validate_id(challenge_id))


@app.post("/api/challenges/{challenge_id}/resume", dependencies=[Depends(require_token)])
async def resume(challenge_id: str) -> dict[str, Any]:
    STORE.load(validate_id(challenge_id))
    return await ENGINE.resume(challenge_id)


@app.post("/api/challenges/{challenge_id}/chat", dependencies=[Depends(require_token)])
async def chat(challenge_id: str, message: ChatMessage) -> dict[str, str]:
    await ENGINE.chat(validate_id(challenge_id), message.message)
    return {"status": "queued"}


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(html.replace("__REVERSER_TOKEN__", CSRF_TOKEN), headers={"Cache-Control": "no-store"})


app.mount("/static", StaticFiles(directory=STATIC), name="static")
