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
from urllib.parse import unquote, urlsplit

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .importer import ChallengeImporter
from .engine import WebEngine
from .orchestration import TaskDB
from .security import safe_filename, validate_id
from .site_import import download_attachment, preview_site
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
API_KEY_AGENT_DIR = PRIVATE / "pi-api-key-agent"
AUTH_SOURCE = Path(os.environ.get("REVERSER_PI_AUTH_SOURCE", PRIVATE / "pi-auth-seed"))
MAX_UPLOAD = 128 * 1024 * 1024


def configured() -> dict[str, str]:
    try:
        value = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        if isinstance(value, dict):
            return {key: str(item) for key, item in value.items() if isinstance(item, str)}
    except (OSError, ValueError):
        pass
    return {"auth_mode": "oauth", "oauth_model": "openai-codex/gpt-6-sol",
            "chatgpt_model": "openai/gpt-6-sol", "api_model": "openai/gpt-5.1"}


def has_provider(path: Path, provider: str) -> bool:
    try:
        return isinstance(json.loads(path.read_text(encoding="utf-8")).get(provider), dict)
    except (OSError, ValueError, AttributeError):
        return False


def has_oauth() -> bool:
    return has_provider(PI_AGENT_DIR / "auth.json", "openai-codex") or has_provider(AUTH_SOURCE / "auth.json", "openai-codex")


def has_chatgpt() -> bool:
    return has_provider(PI_AGENT_DIR / "auth.json", "openai")


def provider_ready(provider: str) -> bool:
    if not shutil.which("pi"):
        return False
    try:
        env = os.environ.copy()
        env["PI_CODING_AGENT_DIR"] = str(PI_AGENT_DIR)
        result = subprocess.run(
            ["pi", "auth", "check", "--provider", provider, "--json"],
            cwd=ROOT, env=env, capture_output=True, text=True, timeout=20, check=False,
        )
        return json.loads(result.stdout).get("status") == "ready"
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return False


def oauth_ready() -> bool:
    if not has_oauth():
        return False
    try:
        prepare_oauth()
        return provider_ready("openai-codex")
    except HTTPException:
        return False


def chatgpt_ready() -> bool:
    return has_chatgpt() and provider_ready("openai")


def visible_config() -> dict[str, Any]:
    value = configured()
    return {
        "auth_mode": value.get("auth_mode", "oauth"),
        "oauth_model": value.get("oauth_model", "openai-codex/gpt-6-sol"),
        "chatgpt_model": value.get("chatgpt_model", "openai/gpt-6-sol"),
        "api_model": value.get("api_model", "openai/gpt-5.1"),
        "has_api_key": bool(value.get("api_key")),
        "oauth_available": has_oauth(),
        "oauth_ready": oauth_ready(),
        "chatgpt_available": has_chatgpt(),
        "chatgpt_ready": chatgpt_ready(),
    }


def prepare_oauth() -> None:
    PI_AGENT_DIR.mkdir(parents=True, exist_ok=True)
    for name in ("auth.json",):
        source = AUTH_SOURCE / name
        target = PI_AGENT_DIR / name
        if source.is_file() and not target.exists():
            shutil.copyfile(source, target)
            target.chmod(0o600)
        elif source.is_file() and source.stat().st_mtime_ns > target.stat().st_mtime_ns:
            try:
                source_auth = json.loads(source.read_text(encoding="utf-8"))
                local_auth = json.loads(target.read_text(encoding="utf-8"))
                local_auth.update({key: item for key, item in source_auth.items() if key != "openai"})
                atomic_write_json(target, local_auth)
                target.chmod(0o600)
            except (OSError, ValueError, AttributeError):
                pass
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
    elif mode == "chatgpt":
        if not chatgpt_ready():
            raise HTTPException(409, "ChatGPT 연결이 필요합니다. LLM 설정에서 ChatGPT로 로그인해 주세요.")
        env.pop("OPENAI_API_KEY", None)
        model = value.get("chatgpt_model", "openai/gpt-6-sol").strip()
        if not model.startswith("openai/"):
            raise HTTPException(400, "ChatGPT 모델은 openai/ 형식이어야 합니다.")
    elif mode == "api_key":
        key = value.get("api_key", "")
        if not key:
            raise HTTPException(409, "API 키를 먼저 저장해 주세요.")
        env["OPENAI_API_KEY"] = key
        API_KEY_AGENT_DIR.mkdir(parents=True, exist_ok=True)
        env["PI_CODING_AGENT_DIR"] = str(API_KEY_AGENT_DIR)
        model = value.get("api_model", "").strip()
        if not model.startswith("openai/"):
            raise HTTPException(400, "API 키 모델은 openai/ 형식이어야 합니다.")
    else:
        raise HTTPException(400, "알 수 없는 인증 방식입니다.")
    return env, model


class ConfigUpdate(BaseModel):
    auth_mode: str
    oauth_model: str = "openai-codex/gpt-6-sol"
    chatgpt_model: str = "openai/gpt-6-sol"
    api_model: str = "openai/gpt-5.1"
    api_key: str = ""
    clear_api_key: bool = False


class ChatMessage(BaseModel):
    message: str


class SitePreviewRequest(BaseModel):
    url: str


DB = TaskDB()
ENGINE = WebEngine(ROOT, PRIVATE, STORE, DB, solver_environment)
app = FastAPI(title="Reverser", docs_url=None, redoc_url=None)
CHATGPT_LOGIN_TASK: asyncio.Task[None] | None = None
CHATGPT_LOGIN_STATE: dict[str, str] = {"status": "idle", "error": ""}
CHATGPT_LOGIN_LOCK = asyncio.Lock()


async def finish_chatgpt_login(process: asyncio.subprocess.Process) -> None:
    try:
        assert process.stdout
        line = await asyncio.wait_for(process.stdout.readline(), timeout=310)
        outcome = json.loads(line) if line else {}
        await asyncio.wait_for(process.wait(), timeout=10)
        if outcome.get("type") != "success" or process.returncode != 0:
            raise RuntimeError(str(outcome.get("message") or "ChatGPT 로그인이 완료되지 않았습니다."))
        if not await asyncio.to_thread(chatgpt_ready):
            raise RuntimeError("ChatGPT 인증을 저장했지만 사용 가능한 상태가 아닙니다.")
        value = configured()
        value["auth_mode"] = "chatgpt"
        value.setdefault("chatgpt_model", "openai/gpt-6-sol")
        atomic_write_json(SETTINGS_PATH, value)
        SETTINGS_PATH.chmod(0o600)
        CHATGPT_LOGIN_STATE.update(status="ready", error="")
    except asyncio.CancelledError:
        CHATGPT_LOGIN_STATE.update(status="idle", error="")
        raise
    except (OSError, ValueError, asyncio.TimeoutError, RuntimeError) as exc:
        CHATGPT_LOGIN_STATE.update(status="error", error=str(exc)[:240])
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()


@app.on_event("startup")
async def restore_tasks() -> None:
    await ENGINE.restore()


@app.on_event("shutdown")
async def stop_tasks() -> None:
    if CHATGPT_LOGIN_TASK and not CHATGPT_LOGIN_TASK.done():
        CHATGPT_LOGIN_TASK.cancel()
        await asyncio.gather(CHATGPT_LOGIN_TASK, return_exceptions=True)
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


@app.post("/api/chatgpt/login/start", dependencies=[Depends(require_token)])
async def start_chatgpt_login() -> dict[str, str]:
    global CHATGPT_LOGIN_TASK
    async with CHATGPT_LOGIN_LOCK:
        if CHATGPT_LOGIN_TASK and not CHATGPT_LOGIN_TASK.done():
            raise HTTPException(409, "ChatGPT 로그인이 이미 진행 중입니다.")
        env = os.environ.copy()
        env["PI_CODING_AGENT_DIR"] = str(PI_AGENT_DIR)
        env["PI_OAUTH_CALLBACK_HOST"] = "0.0.0.0"
        process = await asyncio.create_subprocess_exec(
            "node", str(ROOT / "code" / "reverser_harness" / "chatgpt_login.mjs"),
            cwd=ROOT, env=env, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        try:
            assert process.stdout
            line = await asyncio.wait_for(process.stdout.readline(), timeout=15)
            event = json.loads(line) if line else {}
            if event.get("type") != "auth_url" or not str(event.get("url", "")).startswith("https://auth.openai.com/api/accounts/authorize?"):
                raise ValueError(str(event.get("message") or "ChatGPT 로그인 창을 열 수 없습니다."))
        except (OSError, ValueError, asyncio.TimeoutError) as exc:
            if process.returncode is None:
                process.kill()
                await process.wait()
            raise HTTPException(502, str(exc)[:240]) from exc
        CHATGPT_LOGIN_STATE.update(status="pending", error="")
        CHATGPT_LOGIN_TASK = asyncio.create_task(finish_chatgpt_login(process))
        return {"url": event["url"]}


@app.get("/api/chatgpt/login/status")
def chatgpt_login_status() -> dict[str, str]:
    return CHATGPT_LOGIN_STATE.copy()


@app.post("/api/chatgpt/login/cancel", dependencies=[Depends(require_token)])
async def cancel_chatgpt_login() -> dict[str, str]:
    if CHATGPT_LOGIN_TASK and not CHATGPT_LOGIN_TASK.done():
        CHATGPT_LOGIN_TASK.cancel()
        await asyncio.gather(CHATGPT_LOGIN_TASK, return_exceptions=True)
    CHATGPT_LOGIN_STATE.update(status="idle", error="")
    return CHATGPT_LOGIN_STATE.copy()


@app.put("/api/config", dependencies=[Depends(require_token)])
def put_config(request: ConfigUpdate) -> dict[str, Any]:
    if request.auth_mode not in {"oauth", "chatgpt", "api_key"}:
        raise HTTPException(400, "인증 방식을 선택해 주세요.")
    if request.oauth_model and not re.fullmatch(r"openai-codex/[A-Za-z0-9_.:-]+", request.oauth_model):
        raise HTTPException(400, "Pi 로그인 모델 형식이 올바르지 않습니다.")
    if not re.fullmatch(r"openai/[A-Za-z0-9_.:-]+", request.chatgpt_model):
        raise HTTPException(400, "ChatGPT 모델 형식이 올바르지 않습니다.")
    if request.auth_mode == "chatgpt" and not chatgpt_ready():
        raise HTTPException(409, "먼저 ChatGPT로 로그인해 주세요.")
    if not re.fullmatch(r"openai/[A-Za-z0-9_.:-]+", request.api_model):
        raise HTTPException(400, "API 키 모델 형식이 올바르지 않습니다.")
    value = configured()
    value.update({"auth_mode": request.auth_mode, "oauth_model": request.oauth_model.strip(),
                  "chatgpt_model": request.chatgpt_model.strip(), "api_model": request.api_model.strip()})
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


@app.post("/api/site/preview", dependencies=[Depends(require_token)])
async def site_preview(request: SitePreviewRequest) -> dict[str, object]:
    return await asyncio.to_thread(preview_site, request.url.strip())


@app.post("/api/challenges", dependencies=[Depends(require_token)])
async def create_challenge(title: str = Form(...), event: str = Form(""), description: str = Form(""),
                           platform_url: str = Form(""), site_files: str = Form("[]"),
                           files: list[UploadFile] | None = File(default=None)) -> dict[str, Any]:
    files = [file for file in (files or []) if file.filename]
    if len(site_files) > 16_000:
        raise HTTPException(400, "사이트 파일 목록이 너무 깁니다.")
    try:
        selected = json.loads(site_files)
    except json.JSONDecodeError as exc:
        raise HTTPException(400, "사이트 파일 목록이 올바르지 않습니다.") from exc
    if not isinstance(selected, list) or any(not isinstance(item, dict) or
            not isinstance(item.get("url"), str) or not isinstance(item.get("name"), str)
            for item in selected):
        raise HTTPException(400, "사이트 파일 목록이 올바르지 않습니다.")
    if len(files) + len(selected) > 8:
        raise HTTPException(400, "파일은 8개까지 첨부할 수 있습니다.")
    if any(len(item["url"]) > 4096 or len(item["name"]) > 180 for item in selected):
        raise HTTPException(400, "사이트 파일 주소나 이름이 너무 깁니다.")
    if not platform_url and (selected or not files):
        raise HTTPException(400, "문제 URL이나 파일을 입력해 주세요.")
    if not files and not selected and not description.strip():
        raise HTTPException(400, "문제 설명이나 파일을 입력해 주세요.")
    if len(title) > 160 or len(event) > 100 or len(description) > 20_000 or len(platform_url) > 4096:
        raise HTTPException(400, "입력 내용이 너무 깁니다.")
    uploaded: list[Path] = []
    with tempfile.TemporaryDirectory(prefix="upload-", dir=PRIVATE) as temporary:
        total = 0
        def unique_destination(name: str) -> Path:
            destination = Path(temporary) / safe_filename(name)
            counter = 1
            while destination.exists():
                destination = Path(temporary) / f"{destination.stem}-{counter}{destination.suffix}"
                counter += 1
            return destination
        for number, file in enumerate(files):
            destination = unique_destination(file.filename or f"attachment-{number}")
            with destination.open("wb") as stream:
                while chunk := await file.read(1024 * 1024):
                    total += len(chunk)
                    if total > MAX_UPLOAD:
                        raise HTTPException(413, "첨부 파일 총 크기는 128 MiB까지 허용됩니다.")
                    stream.write(chunk)
            uploaded.append(destination)
        for number, item in enumerate(selected):
            destination = unique_destination(item["name"] or
                Path(unquote(urlsplit(item["url"]).path)).name or f"attachment-{number + 1}.bin")
            total += await asyncio.to_thread(download_attachment, item["url"], destination, MAX_UPLOAD - total)
            uploaded.append(destination)
        state = ChallengeImporter(STORE).import_local(title=title, files=uploaded,
            platform_url=platform_url, event=event, description=description,
            allow_empty=bool(platform_url))
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
