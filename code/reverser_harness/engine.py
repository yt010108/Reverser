"""Artex-style planner/intent worker loop for local reversing tasks."""

import asyncio
import json
import os
import re
import shutil
import signal
import sys
import uuid
from pathlib import Path
from typing import Any, Callable

from .orchestration import TaskDB
from .storage import ChallengeStore


ROLE_TOOLS = {
    "main": "reverser_status",
    "planner": "reverser_status,reverser_intent",
    "worker": "reverser_status,reverser_exec,reverser_fact,reverser_hypothesis,"
              "reverser_candidate,reverser_read_file,reverser_write_file",
    "verifier": "reverser_status,reverser_candidate_context,reverser_review_exec,"
                "reverser_verify_candidate,reverser_read_file,reverser_write_file",
}
ROLE_PROMPTS = {
    "main": "web-main.md", "planner": "web-planner.md",
    "worker": "web-worker.md", "verifier": "web-verifier.md",
}
FLAG_PATTERN = re.compile(r"\b[A-Za-z][A-Za-z0-9_]{0,31}\{[^}\r\n]{1,512}\}")


class WebEngine:
    def __init__(self, root: Path, private: Path, store: ChallengeStore, db: TaskDB,
                 credentials: Callable[[], tuple[dict[str, str], str]]) -> None:
        self.root, self.private, self.store, self.db = root, private, store, db
        self.credentials = credentials
        self.runners: dict[str, asyncio.Task[None]] = {}
        self.processes: dict[tuple[str, str], asyncio.subprocess.Process] = {}
        self.chats: dict[str, asyncio.Task[None]] = {}

    def view(self, challenge_id: str) -> dict[str, Any]:
        task = self.db.task(challenge_id)
        if not task:
            return {"state": "idle", "round": 0, "goal": "", "sessions": self.sessions(challenge_id)}
        return {"state": task["status"], "round": task["round"], "goal": task["goal"],
                "sessions": self.sessions(challenge_id)}

    def sessions(self, challenge_id: str) -> list[dict[str, Any]]:
        task = self.db.task(challenge_id)
        fixed = [
            {"id": "main:0", "role": "main", "title": "메인 에이전트", "status": "ready"},
            {"id": "plan", "role": "planner", "title": "플래너", "status": task["status"] if task else "ready"},
            {"id": "system", "role": "system", "title": "시스템 감사", "status": "ready"},
        ]
        return fixed + [
            {"id": f"intent:{item['intent_id']}", "role": "worker", "title": item["summary"],
             "status": item["status"], "intent_id": item["intent_id"]}
            for item in self.db.intents(challenge_id)
        ] + [
            {"id": f"verify:{item['id']}", "role": "verifier",
             "title": f"후보 #{item['id']} 검증", "status": item["status"]}
            for item in self.db.candidates(challenge_id)
        ]

    async def restore(self) -> None:
        for challenge_id in self.db.active_tasks():
            self.db.reopen_running(challenge_id)
            self.db.append(challenge_id, "system", "system", "restart", "서버 재시작 후 작업을 복구했습니다.")
            self._launch(challenge_id)

    async def start(self, challenge_id: str) -> dict[str, Any]:
        state = self.store.load(challenge_id)
        if state.get("status") in {"solved", "local_verified"}:
            raise ValueError("이미 검증이 완료된 문제입니다.")
        if not shutil.which("pi"):
            raise RuntimeError("Pi 실행 파일을 찾지 못했습니다.")
        self.credentials()  # validate the selected auth before starting the task
        goal = f"{state['title']}: 제공된 자료에서 정답 또는 검증된 로컬 입력을 찾는다."
        self.db.ensure_task(challenge_id, goal)
        running = self.runners.get(challenge_id)
        if running and not running.done():
            raise ValueError("이미 실행 중인 작업입니다.")
        if state.get("triage") and state.get("status") in {"failed", "unsolved"}:
            state["status"] = "solving"
            state["finished_at"] = None
            state["exit_reason"] = None
            self.store.save(state)
        self.db.sync_intents(challenge_id, state.get("intents", []))
        self.db.reopen_running(challenge_id)
        self.db.set_task(challenge_id, "running", goal)
        self.db.append(challenge_id, "system", "system", "start", "작업을 시작했습니다.")
        self._launch(challenge_id)
        return self.view(challenge_id)

    def _launch(self, challenge_id: str) -> None:
        self.runners[challenge_id] = asyncio.create_task(self._loop(challenge_id))

    async def pause(self, challenge_id: str) -> dict[str, Any]:
        if not self.db.task(challenge_id):
            raise ValueError("시작된 작업이 없습니다.")
        self.db.set_task(challenge_id, "paused")
        self.db.pause_running(challenge_id)
        runner = self.runners.get(challenge_id)
        if runner and not runner.done():
            runner.cancel()
        self.db.append(challenge_id, "system", "system", "pause", "작업을 일시정지했습니다.")
        return self.view(challenge_id)

    async def shutdown(self) -> None:
        for runner in self.runners.values():
            if not runner.done():
                runner.cancel()
        for chat in self.chats.values():
            if not chat.done():
                chat.cancel()
        await asyncio.gather(*self.runners.values(), *self.chats.values(), return_exceptions=True)

    async def resume(self, challenge_id: str) -> dict[str, Any]:
        task = self.db.task(challenge_id)
        if not task or task["status"] != "paused":
            raise ValueError("일시정지된 작업이 없습니다.")
        runner = self.runners.get(challenge_id)
        if runner and not runner.done():
            try:
                await asyncio.wait_for(asyncio.shield(runner), timeout=10)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                raise ValueError("이전 작업이 아직 정리 중입니다.")
        self.db.reopen_running(challenge_id)
        self.db.set_task(challenge_id, "running")
        self.db.append(challenge_id, "system", "system", "resume", "작업을 재개했습니다.")
        self._launch(challenge_id)
        return self.view(challenge_id)

    async def chat(self, challenge_id: str, message: str) -> None:
        if not message.strip() or len(message) > 4000:
            raise ValueError("메시지는 1~4000자로 입력해 주세요.")
        self.store.load(challenge_id)
        self.credentials()
        self.db.ensure_task(challenge_id)
        prior = self.chats.get(challenge_id)
        if prior and not prior.done():
            raise ValueError("메인 에이전트가 응답 중입니다.")
        clean = message.strip()
        self.db.append(challenge_id, "main:0", "user", "message", clean)
        self.db.append(challenge_id, "system", "system", "hint", "사용자 힌트가 플래너에 전달되었습니다.", clean)
        self.chats[challenge_id] = asyncio.create_task(self._run_main(challenge_id, clean))

    async def _run_main(self, challenge_id: str, message: str) -> None:
        try:
            await self._run_pi(challenge_id, "main", "main:0", message)
        except Exception as exc:
            self.db.append(challenge_id, "system", "system", "error",
                           f"메인 에이전트 오류: {type(exc).__name__}")

    async def _loop(self, challenge_id: str) -> None:
        try:
            state = self.store.load(challenge_id)
            if not state.get("triage") and state.get("status") not in {"solved", "local_verified"}:
                self.db.append(challenge_id, "system", "system", "triage", "기본 정찰을 시작했습니다.")
                await self._triage(challenge_id)
                self.db.append(challenge_id, "system", "system", "triage", "기본 정찰을 마쳤습니다.")
            while self.db.task(challenge_id)["status"] in {"running", "verifying"}:
                state = self.store.load(challenge_id)
                if state["status"] in {"solved", "local_verified"}:
                    self.db.set_task(challenge_id, state["status"])
                    self.db.append(challenge_id, "system", "system", "done", "독립 검증을 마쳤습니다.")
                    return
                pending = next((x for x in self.db.candidates(challenge_id) if x["status"] == "pending"), None)
                if pending:
                    await self._verify(challenge_id, pending)
                    continue
                if not self.db.has_unplanned_hint(challenge_id):
                    claim = self.db.claim(challenge_id, "work#1")
                    if claim:
                        await self._work(challenge_id, claim)
                        continue
                # Planner wakes when the frontier is empty or a worker/verification returned.
                round_no = self.db.next_round(challenge_id)
                self.db.append(challenge_id, "plan", "planner", "round", f"계획 라운드 #{round_no}")
                hints = self.db.activities(challenge_id, max(0, self.db.last_seq(challenge_id) - 100), "system")
                latest_hint = next((x["detail"] for x in reversed(hints) if x["kind"] == "hint"), "")
                prompt = f"CTF challenge_id: {challenge_id}. 현재 목표: {self.db.task(challenge_id)['goal']}"
                if latest_hint:
                    prompt += f"\n최근 사용자 힌트: {latest_hint}"
                outcome = await self._run_pi(challenge_id, "planner", "plan", prompt)
                if not outcome["ok"]:
                    self.db.set_task(challenge_id, "failed")
                    self.db.append(challenge_id, "system", "system", "error", "플래너 실행이 실패했습니다.")
                    return
                created = self.db.sync_intents(challenge_id, self.store.load(challenge_id).get("intents", []))
                for intent_id in created:
                    item = next(x for x in self.db.intents(challenge_id) if x["intent_id"] == intent_id)
                    self.db.append(challenge_id, "plan", "planner", "intent",
                                   item["summary"], intent_id=intent_id)
                if not created and not self.db.has_claimable(challenge_id):
                    self.db.set_task(challenge_id, "unsolved")
                    self.db.append(challenge_id, "system", "system", "unsolved",
                                   "플래너가 새 분석 의도를 만들지 않아 작업을 미해결로 마쳤습니다.")
                    return
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if self.db.task(challenge_id)["status"] != "paused":
                self.db.set_task(challenge_id, "failed")
                self.db.append(challenge_id, "system", "system", "error",
                               f"작업 오류: {type(exc).__name__}")

    async def _triage(self, challenge_id: str) -> None:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(self.root / "code")
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "reverser_harness.cli", "triage", challenge_id,
            cwd=self.root, env=env, stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE, start_new_session=True,
        )
        self.processes[(challenge_id, "triage")] = process
        try:
            _stdout, stderr = await process.communicate()
            if process.returncode != 0:
                raise RuntimeError(stderr.decode("utf-8", errors="replace")[:2000] or "정찰 실행 실패")
        except asyncio.CancelledError:
            if process.returncode is None:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            await process.wait()
            raise
        finally:
            self.processes.pop((challenge_id, "triage"), None)

    async def _work(self, challenge_id: str, intent: dict[str, Any]) -> None:
        intent_id = intent["intent_id"]
        session = f"intent:{intent_id}"
        self.db.append(challenge_id, session, "worker", "intent", intent["summary"], intent_id=intent_id)
        before_runs = max((item["sequence"] for item in self.store.load(challenge_id).get("tool_runs", [])), default=0)
        outcome = await self._run_pi(challenge_id, "worker", session,
                                     f"CTF challenge_id: {challenge_id}\nintent_id: {intent_id}\n이번 의도: {intent['summary']}",
                                     intent_id=intent_id)
        if self.db.task(challenge_id)["status"] == "paused":
            return
        if not outcome["ok"]:
            self.db.set_intent(challenge_id, intent_id, "open")
            self.db.set_task(challenge_id, "failed")
            self.db.append(challenge_id, session, "worker", "error", "작업자 실행이 실패했습니다. 다시 시작하면 같은 의도를 재시도합니다.", intent_id=intent_id)
            return
        state = self.store.load(challenge_id)
        new_runs = [x for x in state.get("tool_runs", []) if x["sequence"] > before_runs
                    and x.get("intent_id") == intent_id]
        status = "done" if new_runs else "blocked"
        current = next((x for x in state.get("intents", []) if x["id"] == intent_id), None)
        if current and current["status"] == "open":
            self.store.finish_intent(challenge_id, intent_id, status, new_runs[-1]["sequence"] if new_runs else None)
        self.db.set_intent(challenge_id, intent_id, status)
        self.db.append(challenge_id, session, "worker", "result",
                       "의도 완료" if status == "done" else "의도 막힘",
                       intent_id=intent_id)

    async def _verify(self, challenge_id: str, candidate: dict[str, Any]) -> None:
        candidate_id = candidate["id"]
        session = f"verify:{candidate_id}"
        self.db.set_task(challenge_id, "verifying")
        self.db.append(challenge_id, session, "verifier", "start",
                       f"후보 #{candidate_id} 독립 검증 시작")
        outcome = await self._run_pi(
            challenge_id, "verifier", session,
            f"CTF challenge_id: {challenge_id}\ncandidate_id: {candidate_id}. "
            "reverser_candidate_context로 후보를 읽고 새 review 실행으로 검증하세요.",
            intent_id=f"v{candidate_id}",
        )
        if self.db.task(challenge_id)["status"] == "paused":
            return
        updated = self.db.candidate(challenge_id, candidate_id)
        if updated and updated["status"] == "pending":
            self.db.set_task(challenge_id, "failed")
            self.db.append(challenge_id, session, "verifier", "error",
                           "검증 실행이 실패했습니다." if not outcome["ok"] else "검증 작업자가 결과를 기록하지 않았습니다.")
            return
        state = self.store.load(challenge_id)
        if state["status"] in {"solved", "local_verified"}:
            self.db.set_task(challenge_id, state["status"])
            self.db.append(challenge_id, "system", "system", "done", "독립 검증을 마쳤습니다.")
        else:
            self.db.set_task(challenge_id, "running")

    async def _run_pi(self, challenge_id: str, role: str, session: str,
                      prompt: str, intent_id: str = "") -> dict[str, Any]:
        env, model = self.credentials()
        env["REVERSER_ROLE"] = role
        env["REVERSER_CHALLENGE_ID"] = challenge_id
        env["REVERSER_INTENT_ID"] = intent_id
        session_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"reverser:{challenge_id}:{session}"))
        args = ["pi", "--mode", "json", "-p", "--approve", "--no-mcp", "--no-builtin-tools",
                "--no-context-files", "--no-skills", "--no-prompt-templates",
                "--tools", ROLE_TOOLS[role], "--session-dir", str(self.private / "sessions"),
                "--session-id", session_uuid, "--append-system-prompt",
                str(self.root / ".pi" / "agents" / ROLE_PROMPTS[role])]
        if model:
            args += ["--model", model]
        args.append(prompt)
        process = await asyncio.create_subprocess_exec(
            *args, cwd=self.root, env=env, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE, start_new_session=True, limit=2 * 1024 * 1024,
        )
        self.processes[(challenge_id, session)] = process
        self.db.append(challenge_id, session, role, "agent_start", f"{role} 세션 시작", intent_id=intent_id or None)
        failed = False
        assert process.stdout and process.stderr
        stderr_task = asyncio.create_task(process.stderr.read())
        try:
            while line := await process.stdout.readline():
                try:
                    event = json.loads(line)
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue
                if not isinstance(event, dict):
                    continue
                kind = event.get("type")
                if kind == "tool_execution_start":
                    name = str(event.get("toolName", "도구"))
                    args_value = event.get("args") if isinstance(event.get("args"), dict) else {}
                    summary = name
                    if name in {"reverser_intent", "reverser_fact"}:
                        summary += ": " + str(args_value.get("summary", ""))[:180]
                    elif name in {"reverser_exec", "reverser_review_exec"}:
                        summary += ": " + str(args_value.get("profile", ""))
                    elif name == "reverser_candidate":
                        summary += ": 검증 후보 제안"
                    self.db.append(challenge_id, session, role, "tool_start",
                                   self._safe(challenge_id, summary), intent_id=intent_id or None)
                elif kind == "tool_execution_end":
                    name = str(event.get("toolName", "도구"))
                    self.db.append(challenge_id, session, role, "tool_end",
                                   name + (" 실패" if event.get("isError") else " 완료"),
                                   intent_id=intent_id or None)
                elif kind == "message_end":
                    msg = event.get("message")
                    if isinstance(msg, dict) and msg.get("role") == "assistant":
                        if msg.get("stopReason") == "error":
                            failed = True
                        parts = msg.get("content") or []
                        answer = "\n".join(str(x.get("text", "")) for x in parts
                                           if isinstance(x, dict) and x.get("type") == "text").strip()
                        if answer:
                            self.db.append(challenge_id, session, role, "message",
                                           self._safe(challenge_id, answer)[:2000],
                                           intent_id=intent_id or None, tokens=msg.get("usage"))
            exit_code = await process.wait()
            await stderr_task
            ok = exit_code == 0 and not failed
            if not ok:
                self.db.append(challenge_id, session, role, "error",
                               f"에이전트 실행 실패 (종료 코드 {exit_code})", intent_id=intent_id or None)
            return {"ok": ok, "exit_code": exit_code}
        except asyncio.CancelledError:
            if process.returncode is None:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            await process.wait()
            raise
        finally:
            self.processes.pop((challenge_id, session), None)

    def _safe(self, challenge_id: str, value: str) -> str:
        state = self.store.load(challenge_id)
        secrets = [*state.get("flags", []), *state.get("local_answers", []),
                   *(item["value"] for item in self.db.candidates(challenge_id, include_value=True))]
        for secret in secrets:
            if secret:
                value = value.replace(str(secret), "[비공개 결과]")
        return FLAG_PATTERN.sub("[비공개 결과]", value)

    def visible_activity(self, challenge_id: str, item: dict[str, Any]) -> dict[str, Any]:
        return {**item, "summary": self._safe(challenge_id, item["summary"]),
                "detail": self._safe(challenge_id, item["detail"])}
