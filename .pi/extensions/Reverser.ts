import { spawn } from "node:child_process";
import { mkdirSync, readFileSync, watch, type FSWatcher } from "node:fs";
import { delimiter, dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { chromium, type BrowserContext, type Page } from "playwright";
import { Type } from "typebox";

const extensionDir = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(extensionDir, "../..");
const browserProfile = resolve(projectRoot, ".private/playwright-profile");
const browserDownloads = resolve(projectRoot, ".private/browser-downloads");

let browserContext: BrowserContext | undefined;
let browserPage: Page | undefined;

type AgentRole = "solver" | "reviewer";
type AgentContext = { model?: { provider: string; id: string }; thinkingLevel?: string };

// Child agents get only the harness tools needed for their role. In particular,
// they cannot open another browser or recursively dispatch more agents.
const AGENT_TOOLS: Record<AgentRole, string[]> = {
  solver: [
    "read", "write", "edit", "grep", "find", "ls",
    "reverser_status", "reverser_triage", "reverser_exec", "reverser_record_flag",
    "reverser_recon", "reverser_hypothesis", "reverser_solution_search", "reverser_mark_unsolved",
  ],
  reviewer: [
    "read", "write", "grep", "find", "ls", "reverser_status", "reverser_writeup",
    "reverser_solution_search", "reverser_learn",
  ],
};

function agentCommand(role: AgentRole, challengeId: string, context: AgentContext) {
  const args = [
    "pi", "-p", "--no-session", "--approve",
    "--tools", AGENT_TOOLS[role].join(","),
    "--append-system-prompt", `.pi/agents/${role}.md`,
  ];
  if (context.model) args.push("--model", `${context.model.provider}/${context.model.id}`);
  if (context.thinkingLevel) args.push("--thinking", context.thinkingLevel);
  args.push(JSON.stringify(`CTF challenge_id: ${challengeId}`));
  return args.join(" ");
}

async function playwrightPage() {
  if (!browserContext) {
    mkdirSync(browserProfile, { recursive: true });
    mkdirSync(browserDownloads, { recursive: true });
    browserContext = await chromium.launchPersistentContext(browserProfile, {
      headless: false,
      acceptDownloads: true,
      downloadsPath: browserDownloads,
    });
    browserContext.on("close", () => {
      browserContext = undefined;
      browserPage = undefined;
    });
  }
  if (!browserPage || browserPage.isClosed()) {
    browserPage = browserContext.pages()[0] ?? await browserContext.newPage();
  }
  return { page: browserPage, context: browserContext };
}

type CliResult = { exitCode: number; stdout: string; stderr: string; parsed?: unknown };

function runCli(args: string[], signal?: AbortSignal): Promise<CliResult> {
  const command = process.platform === "win32" ? "py" : "python3";
  const commandArgs = process.platform === "win32" ? ["-3", "-m", "reverser_harness.cli", ...args] : ["-m", "reverser_harness.cli", ...args];
  return new Promise((resolvePromise, reject) => {
    const pythonPath = [resolve(projectRoot, "code"), process.env.PYTHONPATH].filter(Boolean).join(delimiter);
    const child = spawn(command, commandArgs, { cwd: projectRoot, env: { ...process.env, PYTHONPATH: pythonPath }, windowsHide: true, stdio: ["ignore", "pipe", "pipe"] });
    let stdout = ""; let stderr = "";
    child.stdout.setEncoding("utf8"); child.stderr.setEncoding("utf8");
    child.stdout.on("data", (chunk: string) => { stdout += chunk; });
    child.stderr.on("data", (chunk: string) => { stderr += chunk; });
    const abort = () => child.kill("SIGTERM");
    signal?.addEventListener("abort", abort, { once: true });
    child.on("error", reject);
    child.on("close", (code) => {
      signal?.removeEventListener("abort", abort);
      let parsed: unknown;
      try { parsed = JSON.parse(stdout); } catch { parsed = undefined; }
      resolvePromise({ exitCode: code ?? 1, stdout, stderr, parsed });
    });
  });
}

function result(value: CliResult) {
  const text = value.exitCode === 0 ? value.stdout.trim() || "완료" : `실행 실패 (exit ${value.exitCode})\n${value.stderr.trim() || value.stdout.trim()}`;
  return { content: [{ type: "text" as const, text }], details: { exitCode: value.exitCode, data: value.parsed, stderr: value.stderr }, isError: value.exitCode !== 0 };
}

export default function (pi: ExtensionAPI) {
  const orca = process.platform === "win32" ? "orca.exe" : "orca";
  let solverTerminal: string | undefined;
  let plannerModel: { provider: string; id: string } | undefined;
  let plannerThinking: ReturnType<typeof pi.getThinkingLevel> | undefined;
  const jobWatchers = new Map<string, FSWatcher>();

  const watchJob = (
    role: AgentRole,
    challengeId: string,
    path: string,
    onDone?: (job: { terminal?: string; result?: string }) => void,
  ) => {
    const key = `${role}:${challengeId}`;
    let notified = false;
    const notify = () => {
      try {
        const job = JSON.parse(readFileSync(path, "utf8")) as { status?: string; terminal?: string; result?: string };
        if (job.status !== "done" || notified) return;
        notified = true;
        jobWatchers.get(key)?.close();
        jobWatchers.delete(key);
        const label = role === "solver" ? "Solver" : "Reviewer";
        pi.sendMessage(
          { customType: role, content: `[${label}] ${challengeId} 완료 · ${job.result}`, display: true },
          { triggerTurn: true, deliverAs: "followUp" },
        );
        onDone?.(job);
      } catch {}
    };
    jobWatchers.get(key)?.close();
    jobWatchers.set(key, watch(dirname(path), (_event, file) => {
      if (file?.toString() === `${role}.json`) notify();
    }));
    notify();
  };

  const launchReviewer = async (challengeId: string, terminal: string, context: AgentContext) => {
    const idle = await pi.exec(orca, ["terminal", "wait", "--terminal", terminal, "--for", "tui-idle", "--timeout-ms", "60000", "--json"]);
    if (idle.code !== 0) {
      pi.sendMessage({ customType: "reviewer", content: `[Reviewer] ${challengeId} 시작 실패`, display: true }, { triggerTurn: true, deliverAs: "followUp" });
      return;
    }
    const tracked = await runCli(["reviewer-start", challengeId, "--terminal", terminal]);
    if (tracked.exitCode !== 0) {
      pi.sendMessage({ customType: "reviewer", content: `[Reviewer] ${challengeId} 시작 실패`, display: true }, { triggerTurn: true, deliverAs: "followUp" });
      return;
    }
    const path = (tracked.parsed as { path?: string } | undefined)?.path;
    if (!path) return;
    watchJob("reviewer", challengeId, path);
    const sent = await pi.exec(orca, ["terminal", "send", "--terminal", terminal, "--text", agentCommand("reviewer", challengeId, context), "--enter", "--json"]);
    if (sent.code !== 0) await runCli(["reviewer-finish", challengeId, "--failed"]);
  };

  const openTerminal = async (base: string | undefined, signal?: AbortSignal) => {
    const args = ["terminal", "split"];
    if (base) args.push("--terminal", base);
    args.push("--direction", base ? "horizontal" : "vertical", "--json");
    let split = await pi.exec(orca, args, { signal });
    if (split.code !== 0 && base) split = await pi.exec(orca, ["terminal", "split", "--direction", "vertical", "--json"], { signal });
    if (split.code !== 0) throw new Error(split.stderr || split.stdout);
    const handle = (JSON.parse(split.stdout) as { result?: { split?: { handle?: string } } }).result?.split?.handle;
    if (!handle) throw new Error("Orca terminal handle을 받지 못했습니다.");
    return handle;
  };

  pi.on("session_shutdown", async () => {
    for (const watcher of jobWatchers.values()) watcher.close();
    jobWatchers.clear();
    const context = browserContext;
    browserContext = undefined;
    browserPage = undefined;
    if (context) await context.close().catch(() => undefined);
  });

  pi.on("tool_call", async (event) => {
    if (event.toolName !== "bash") return undefined;
    const input = event.input as { command?: unknown };
    const command = typeof input.command === "string" ? input.command : "";
    const bypass = /(?:^|[;&|\s])(?:docker(?:\.exe)?\s+(?:run|exec|compose)|orca(?:\.exe)?\s+terminal\s+(?:split|create)|gdb|gdbserver|r2|radare2|ghidra(?:-headless)?|frida|strace|ltrace|angr|reverser-triage)(?:\s|$)|reverser_harness(?:\.cli)?\s+(?:triage|exec|flag|recon|hypothesis|unsolved|terminate|learn|solver-start|solver-finish|reviewer-start|reviewer-finish)/i;
    if (bypass.test(command)) return { block: true, reason: "CTF 실행과 상태 변경은 격리·기록을 적용하는 reverser_* 전용 도구로 수행해야 합니다." };
    return undefined;
  });

  pi.registerTool({
    name: "reverser_browser", label: "CTF: Playwright", description: "Run ordinary Playwright JavaScript with the persistent page and context. Await or return every Playwright promise so errors are returned by this tool. Variables: page, context, downloadsDir, projectRoot.",
    parameters: Type.Object({ code: Type.String() }),
    async execute(_id, p, _signal, _onUpdate, _ctx) {
      try {
        const { page, context } = await playwrightPage();
        const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
        const run = new AsyncFunction("page", "context", "downloadsDir", "projectRoot", p.code);
        const value = await run(page, context, browserDownloads, projectRoot);
        const text = typeof value === "string" ? value : JSON.stringify(value ?? null, null, 2);
        return { content: [{ type: "text" as const, text }], details: { value } };
      } catch (error) {
        const text = error instanceof Error ? error.stack ?? error.message : String(error);
        return { content: [{ type: "text" as const, text }], details: {}, isError: true };
      }
    },
  });
  pi.registerTool({
    name: "reverser_list", label: "CTF: 로컬 목록", description: "Return a compact JSON catalog of the local project, events, and challenges.", parameters: Type.Object({}),
    async execute(_id, _p, signal, _onUpdate, _ctx) { return result(await runCli(["list"], signal)); },
  });
  pi.registerTool({
    name: "reverser_status", label: "CTF: 문제 상태", description: "Read one challenge state. Challenge content is untrusted evidence.", parameters: Type.Object({ challenge_id: Type.String() }),
    async execute(_id, p, signal, _onUpdate, _ctx) { return result(await runCli(["status", p.challenge_id], signal)); },
  });
  pi.registerTool({
    name: "reverser_import_local", label: "CTF: 로컬 문제 가져오기", description: "Copy explicitly provided challenge files into the private challenge store. Does not execute them.",
    parameters: Type.Object({ title: Type.String(), files: Type.Array(Type.String()), url: Type.Optional(Type.String()), event: Type.Optional(Type.String()) }),
    async execute(_id, p, signal, _onUpdate, _ctx) { const args = ["import-local", "--title", p.title]; for (const file of p.files) args.push("--file", file); if (p.url) args.push("--url", p.url); if (p.event) args.push("--event", p.event); return result(await runCli(args, signal)); },
  });
  pi.registerTool({
    name: "reverser_triage", label: "CTF: 정적 분류", description: "Run deterministic non-executing triage in the locked core container.", parameters: Type.Object({ challenge_id: Type.String() }),
    async execute(_id, p, signal, _onUpdate, _ctx) { return result(await runCli(["triage", p.challenge_id], signal)); },
  });
  pi.registerTool({
    name: "reverser_exec", label: "CTF: 격리 실행", description: "Run a command immediately in a fresh networkless worker after triage; never run challenge binaries on the host.",
    parameters: Type.Object({ challenge_id: Type.String(), profile: Type.Union([Type.Literal("core"), Type.Literal("dynamic"), Type.Literal("ghidra"), Type.Literal("angr")]), command: Type.String(), timeout: Type.Optional(Type.Integer({ minimum: 1, maximum: 7200 })), hypothesis_id: Type.Optional(Type.String()) }),
    async execute(_id, p, signal, _onUpdate, _ctx) {
      const args = ["exec", p.challenge_id, "--profile", p.profile, "--command", p.command];
      if (p.timeout) args.push("--timeout", String(p.timeout));
      if (p.hypothesis_id) args.push("--hypothesis", p.hypothesis_id);
      return result(await runCli(args, signal));
    },
  });
  pi.registerTool({
    name: "reverser_recon", label: "CTF: 초기 정찰", description: "Record entry-point analysis and flag-related targets before forming a hypothesis.",
    parameters: Type.Object({
      challenge_id: Type.String(), entry_point: Type.String(), main: Type.Optional(Type.String()),
      evidence_runs: Type.Array(Type.Integer({ minimum: 1 }), { minItems: 1 }),
      flag_candidates: Type.Array(Type.Object({
        target: Type.String(), reason: Type.String(),
        evidence_runs: Type.Array(Type.Integer({ minimum: 1 }), { minItems: 1 }),
      }), { minItems: 1 }),
    }),
    async execute(_id, p, signal, _onUpdate, _ctx) {
      const args = ["recon", p.challenge_id, "--entry-point", p.entry_point, "--candidates-json", JSON.stringify(p.flag_candidates)];
      if (p.main) args.push("--main", p.main);
      for (const run of p.evidence_runs) args.push("--evidence-run", String(run));
      return result(await runCli(args, signal));
    },
  });
  pi.registerTool({
    name: "reverser_hypothesis", label: "CTF: 가설", description: "Propose one falsifiable hypothesis or resolve the active hypothesis with a linked verification run.",
    parameters: Type.Object({
      challenge_id: Type.String(), action: Type.Union([Type.Literal("propose"), Type.Literal("resolve")]),
      hypothesis_id: Type.Optional(Type.String()), target: Type.Optional(Type.String()), parent_id: Type.Optional(Type.String()),
      claim: Type.Optional(Type.String()), test: Type.Optional(Type.String()),
      falsifier: Type.Optional(Type.String()), exhaustion: Type.Optional(Type.String()),
      outcome: Type.Optional(Type.Union([Type.Literal("confirmed"), Type.Literal("rejected"), Type.Literal("inconclusive")])),
      evidence_run: Type.Optional(Type.Integer({ minimum: 1 })), observation: Type.Optional(Type.String()),
    }),
    async execute(_id, p, signal, _onUpdate, ctx) {
      const args = ["hypothesis", p.challenge_id, p.action];
      for (const [flag, value] of [
        ["--hypothesis-id", p.hypothesis_id], ["--target", p.target], ["--parent-id", p.parent_id],
        ["--claim", p.claim], ["--test", p.test],
        ["--falsifier", p.falsifier], ["--exhaustion", p.exhaustion], ["--outcome", p.outcome],
        ["--observation", p.observation],
      ] as Array<[string, string | undefined]>) if (value) args.push(flag, value);
      if (p.evidence_run !== undefined) args.push("--evidence-run", String(p.evidence_run));
      const updated = await runCli(args, signal);
      if (updated.exitCode !== 0) return result(updated);
      let switched = false;
      if (p.action === "propose") {
        if (!plannerModel && ctx.model) plannerModel = { provider: ctx.model.provider, id: ctx.model.id };
        plannerThinking ??= pi.getThinkingLevel();
        for (const provider of [ctx.model?.provider, "openai-codex", "opencode"]) {
          if (!provider) continue;
          const model = ctx.modelRegistry.find(provider, "gpt-5.6-luna");
          if (model && await pi.setModel(model)) { switched = true; break; }
        }
        if (switched) pi.setThinkingLevel("medium");
      } else if (plannerModel) {
        const model = ctx.modelRegistry.find(plannerModel.provider, plannerModel.id);
        switched = !!model && await pi.setModel(model);
        if (plannerThinking) pi.setThinkingLevel(plannerThinking);
      }
      const response = result(updated);
      if (!switched) response.content[0].text += `\n\n모델 전환 실패: 현재 모델을 유지합니다.`;
      return response;
    },
  });
  pi.registerTool({
    name: "reverser_record_flag", label: "CTF: 플래그 로컬 기록", description: "Store a flag only when it appears in a successful evidence run, then finish the Solver.",
    parameters: Type.Object({ challenge_id: Type.String(), value: Type.String(), evidence_run: Type.Integer({ minimum: 1 }) }),
    async execute(_id, p, signal, _onUpdate, _ctx) {
      const saved = await runCli(["flag", p.challenge_id, "--value", p.value, "--evidence-run", String(p.evidence_run)], signal);
      if (saved.exitCode === 0) await runCli(["solver-finish", p.challenge_id], signal);
      return result(saved);
    },
  });
  pi.registerTool({
    name: "reverser_writeup", label: "CTF: Reviewer 결과 저장", description: "Save the Reviewer output only inside the ignored challenge workspace.",
    parameters: Type.Object({ challenge_id: Type.String(), file: Type.String() }),
    async execute(_id, p, signal, _onUpdate, _ctx) {
      const saved = await runCli(["writeup", p.challenge_id, "--file", p.file], signal);
      if (saved.exitCode === 0) await runCli(["reviewer-finish", p.challenge_id], signal);
      return result(saved);
    },
  });
  pi.registerTool({
    name: "reverser_solution_search", label: "CTF: 로컬 풀이 방법 검색", description: "After 30 minutes, search only locally saved difficult-case notes.",
    parameters: Type.Object({ challenge_id: Type.String(), query: Type.String() }),
    async execute(_id, p, signal, _onUpdate, _ctx) { return result(await runCli(["solution-search", p.challenge_id, p.query], signal)); },
  });
  pi.registerTool({
    name: "reverser_mark_unsolved", label: "CTF: 미해결 기록", description: "Stop an unresolved attempt and record its blocker in progress.md.",
    parameters: Type.Object({ challenge_id: Type.String(), reason_file: Type.String() }),
    async execute(_id, p, signal, _onUpdate, _ctx) {
      const marked = await runCli(["unsolved", p.challenge_id, "--reason-file", p.reason_file], signal);
      if (marked.exitCode === 0) await runCli(["solver-finish", p.challenge_id], signal);
      return result(marked);
    },
  });
  pi.registerTool({
    name: "reverser_learn", label: "CTF: 풀이 방법 저장", description: "Save a reusable solution note only for a researched or unsolved challenge; easy solves are rejected.",
    parameters: Type.Object({ challenge_id: Type.String(), file: Type.String() }),
    async execute(_id, p, signal, _onUpdate, _ctx) { return result(await runCli(["learn", p.challenge_id, "--file", p.file], signal)); },
  });
  pi.registerTool({
    name: "reverser_dashboard", label: "CTF: 대시보드", description: "Generate runs/dashboard.html.", parameters: Type.Object({}),
    async execute(_id, _p, signal, _onUpdate, _ctx) { return result(await runCli(["dashboard"], signal)); },
  });
  pi.registerTool({
    name: "reverser_solve", label: "CTF: Solver 터미널", description: "Open a Solver Pi in a separate Orca terminal and return immediately so the parent remains interactive.",
    parameters: Type.Object({ challenge_id: Type.String() }),
    async execute(_id, p, signal, _onUpdate, ctx) {
      const current = await runCli(["status", p.challenge_id], signal);
      if (current.exitCode !== 0) return result(current);
      const context: AgentContext = { model: ctx.model, thinkingLevel: ctx.thinkingLevel };
      const handle = await openTerminal(solverTerminal, signal);
      const tracked = await runCli(["solver-start", p.challenge_id, "--terminal", handle], signal);
      if (tracked.exitCode !== 0) return result(tracked);
      const path = (tracked.parsed as { path?: string } | undefined)?.path;
      if (!path) return { content: [{ type: "text" as const, text: "solver.json 경로를 받지 못했습니다." }], details: { handle }, isError: true };
      watchJob("solver", p.challenge_id, path, (job) => {
        if (job.terminal) void launchReviewer(p.challenge_id, job.terminal, context);
      });
      const sent = await pi.exec(orca, [
        "terminal", "send", "--terminal", handle,
        "--text", agentCommand("solver", p.challenge_id, context), "--enter", "--json",
      ], { signal });
      if (sent.code !== 0) {
        await runCli(["terminate", p.challenge_id, "--reason", "solver_start_failed"]);
        await runCli(["solver-finish", p.challenge_id]);
        return { content: [{ type: "text" as const, text: sent.stderr || sent.stdout }], details: { handle }, isError: true };
      }
      solverTerminal = handle;
      return {
        content: [{ type: "text" as const, text: "Orca 서브 터미널에서 Solver를 시작했습니다." }],
        details: { challengeId: p.challenge_id, terminal: handle },
      };
    },
  });
  pi.registerTool({
    name: "reverser_review", label: "CTF: 독립 Reviewer", description: "Start a post-solve Reviewer in Orca and return immediately.",
    parameters: Type.Object({ challenge_id: Type.String() }),
    async execute(_id, p, signal, _onUpdate, ctx) {
      const current = await runCli(["status", p.challenge_id], signal);
      if (current.exitCode !== 0) return result(current);
      const state = current.parsed as { status?: string } | undefined;
      if (!state || !["solved", "unsolved", "failed"].includes(state.status ?? "")) {
        return {
          content: [{ type: "text" as const, text: "Reviewer는 Solver가 종료된 문제만 검토합니다." }],
          details: { role: "reviewer", challengeId: p.challenge_id, skipped: true },
        };
      }
      const handle = await openTerminal(solverTerminal, signal);
      void launchReviewer(p.challenge_id, handle, { model: ctx.model, thinkingLevel: ctx.thinkingLevel });
      return {
        content: [{ type: "text" as const, text: "Orca 서브 터미널에서 Reviewer를 시작했습니다." }],
        details: { role: "reviewer", challengeId: p.challenge_id, terminal: handle },
      };
    },
  });
}
