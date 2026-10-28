const token = document.querySelector('meta[name="reverser-token"]').content;
const $ = (id) => document.getElementById(id);
const app = { challenges: [], selected: null, current: null, graph: null, candidates: [], activities: [], activityCursor: 0, eventSource: null, sseLive: false, tab: "sessions", selectedSession: "main:0", selectedNode: null, graphZoom: null, busy: false, refreshing: false, lastListAt: 0 };
const statusNames = { importing: "가져오는 중", imported: "준비됨", solving: "풀이 중", researching: "조사 중", solved: "해결", local_verified: "로컬 검증", unsolved: "미해결", failed: "실패", running: "실행 중", verifying: "검증 중", paused: "일시정지", ready: "준비됨", idle: "대기", open: "대기", done: "완료", blocked: "막힘", pending: "검증 대기", verified: "검증 성공", rejected: "검증 실패" };
const kindNames = { challenge: "시작점", goal: "목표", intent: "의도", fact: "사실", hypothesis: "가설", candidate: "후보", verdict: "검증" };
const roleNames = { main: "메인 에이전트", planner: "플래너", worker: "작업자", verifier: "검증자", system: "시스템" };

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (options.method && options.method !== "GET") headers.set("X-Reverser-Token", token);
  if (options.body && !(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const response = await fetch("/api" + path, { ...options, headers, cache: "no-store" });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof body.detail === "string" ? body.detail : `요청 실패 (${response.status})`);
  return body;
}

let toastTimer;
function toast(message) {
  const element = $("toast");
  element.textContent = message;
  element.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => element.classList.remove("show"), 4200);
}

function plainDate(value) {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : date.toLocaleString("ko-KR", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function select(id) {
  if (app.eventSource) { app.eventSource.close(); app.eventSource = null; }
  app.selected = id;
  app.selectedNode = null;
  app.graphZoom = null;
  app.selectedSession = "main:0";
  app.activities = []; app.activityCursor = 0; app.candidates = [];
  document.body.classList.remove("sidebar-open");
  location.hash = id ? `challenge/${encodeURIComponent(id)}` : "";
  refresh().catch((error) => toast(error.message));
}

function renderSidebar() {
  const list = $("challengeList");
  list.replaceChildren();
  $("challengeCount").textContent = String(app.challenges.length);
  if (!app.challenges.length) {
    const message = document.createElement("p");
    message.className = "muted pad";
    message.textContent = "등록된 문제가 없습니다.";
    list.append(message);
    return;
  }
  for (const challenge of app.challenges) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "challenge-item" + (challenge.challenge_id === app.selected ? " active" : "");
    const title = document.createElement("strong");
    title.textContent = challenge.title;
    const meta = document.createElement("span");
    meta.textContent = `${statusNames[challenge.status] || challenge.status} · ${challenge.event || plainDate(challenge.created_at)}`;
    button.append(title, meta);
    button.addEventListener("click", () => select(challenge.challenge_id));
    list.append(button);
  }
}

function setText(id, value) { $(id).textContent = String(value); }

function renderDetail() {
  const challenge = app.current;
  $("emptyView").hidden = !!challenge;
  $("detailView").hidden = !challenge;
  if (!challenge) return;
  setText("detailTitle", challenge.title);
  setText("detailId", challenge.challenge_id);
  setText("detailMeta", challenge.description || [challenge.event, challenge.platform_url, challenge.architecture ? `${challenge.architecture} / ${challenge.bits || "?"} bit` : null].filter(Boolean).join(" · ") || "제공된 문제 파일에서 목표와 검증 근거를 찾습니다.");
  const status = $("detailStatus");
  const taskState = challenge.solver?.state || "idle";
  const shownStatus = ["running", "verifying", "paused"].includes(taskState) ? taskState : challenge.status;
  status.className = "status " + shownStatus;
  status.textContent = statusNames[shownStatus] || shownStatus;
  setText("intentCount", (challenge.intents || []).length);
  setText("factCount", (challenge.facts || []).length);
  setText("hypothesisCount", (challenge.hypotheses || []).length);
  setText("runCount", (challenge.tool_runs || []).length);
  const running = ["running", "verifying"].includes(taskState);
  $("solveButton").hidden = running;
  $("stopButton").hidden = !running;
  $("solveButton").disabled = app.busy || challenge.status === "solved" || challenge.status === "local_verified";
  $("solveButton").textContent = taskState === "paused" ? "▷ 재개" : "▷ 풀이 시작";
  $("stopButton").disabled = app.busy;
  renderTabs();
}

function renderTabs() {
  document.querySelectorAll(".tab").forEach((button) => button.classList.toggle("active", button.dataset.tab === app.tab));
  for (const tab of ["sessions", "overview", "graph", "facts", "activity", "candidates", "files", "report"]) $(tab + "Tab").hidden = app.tab !== tab;
  if (!app.current) return;
  if (app.tab === "sessions") renderSessions();
  if (app.tab === "overview") renderOverview();
  if (app.tab === "graph") renderGraph();
  if (app.tab === "facts") renderFacts();
  if (app.tab === "activity") renderActivity();
  if (app.tab === "candidates") renderCandidates();
  if (app.tab === "files") renderFiles();
  if (app.tab === "report") renderReport();
}

function renderSessions() {
  const sessions = app.current.solver?.sessions || [];
  const state = app.current.solver?.state || "idle";
  setText("sessionState", app.sseLive ? "실시간" : statusNames[state] || state);
  const usage = app.activities.reduce((total, item) => {
    const row = item.tokens || {};
    total.input += Number(row.input || 0);
    total.output += Number(row.output || 0);
    total.cache += Number(row.cacheRead || 0);
    return total;
  }, { input: 0, output: 0, cache: 0 });
  const compact = (n) => n >= 1000000 ? `${(n / 1000000).toFixed(1)}M` : n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n);
  setText("sessionTokens", `작업 합계 · 입 ${compact(usage.input)} · 캐 ${compact(usage.cache)} · 출 ${compact(usage.output)}`);
  const rail = $("sessionList"); rail.replaceChildren();
  for (const role of ["main", "planner", "system", "worker", "verifier"]) {
    const group = sessions.filter((item) => item.role === role);
    if (!group.length) continue;
    const label = document.createElement("div"); label.className = "session-group"; label.dataset.role = role;
    label.textContent = role === "main" ? "메인 에이전트" : role === "planner" ? "플래너" : role === "worker" ? "Workers" : role === "verifier" ? "검증 작업자" : "시스템 감사";
    rail.append(label);
    for (const session of group) {
      const button = document.createElement("button"); button.type = "button";
      button.className = "session-item" + (app.selectedSession === session.id ? " active" : "");
      const marker = document.createElement("span"); marker.className = `session-marker ${session.status}`;
      marker.textContent = ["done", "verified"].includes(session.status) ? "✓" : session.status === "running" ? "◌" : ["blocked", "rejected"].includes(session.status) ? "×" : " ";
      const text = document.createElement("span"); text.className = "session-item-text";
      if (session.intent_id) { const id = document.createElement("span"); id.className = "intent-pill"; id.textContent = `#${session.intent_id}`; text.append(id); }
      const title = document.createElement("strong"); title.textContent = session.role === "main" ? "메인 에이전트 · 세션 #1" : session.role === "planner" ? "플래너 · 상황 판단" : session.role === "system" ? "시스템 이벤트" : session.title;
      text.append(title);
      if (session.status === "running") { const live = document.createElement("small"); live.textContent = "• 실시간"; text.append(live); }
      button.append(marker, text);
      button.addEventListener("click", () => { app.selectedSession = session.id; renderSessions(); });
      rail.append(button);
    }
  }
  const selected = sessions.find((item) => item.id === app.selectedSession) || sessions[0];
  if (!selected) return;
  setText("sessionTitle", selected.role === "main" ? "메인 에이전트 · 대화 세션" : selected.role === "worker" ? "작업자 · 실행 세션" : selected.role === "planner" ? "플래너 · 상황 판단" : selected.title);
  setText("sessionSubtitle", selected.role === "main" ? "목표와 힌트를 전달하세요. 다른 세션에서는 실제 실행 과정을 볼 수 있습니다." : `${roleNames[selected.role]} · ${selected.intent_id || "작업 전체"}`);
  const badge = $("sessionBadge"); badge.className = "status " + selected.status; badge.textContent = statusNames[selected.status] || selected.status;
  $("chatForm").hidden = selected.role !== "main";
  const feed = $("sessionFeed");
  const nearBottom = feed.scrollHeight - feed.scrollTop - feed.clientHeight < 70;
  feed.replaceChildren();
  const items = app.activities.filter((item) => item.session === selected.id);
  if (!items.length) {
    const blank = document.createElement("div"); blank.className = "session-empty";
    blank.textContent = selected.role === "main" ? "메인 에이전트에게 목표나 힌트를 보내면 여기에 대화가 쌓입니다." : "아직 이 세션의 활동이 없습니다.";
    feed.append(blank);
  }
  for (const item of items) {
    const entry = document.createElement("article"); entry.className = `session-entry role-${item.role} ${item.kind}`;
    const header = document.createElement("div"); header.className = "session-entry-header";
    const who = document.createElement("strong"); who.textContent = item.role === "user" ? "사용자" : roleNames[item.role] || item.role;
    const when = document.createElement("time"); when.textContent = plainDate(item.created_at);
    header.append(who, when);
    const body = document.createElement("div"); body.className = "session-entry-body"; body.textContent = item.summary;
    entry.append(header, body);
    if (item.detail) { const detail = document.createElement("div"); detail.className = "session-entry-detail"; detail.textContent = item.detail; entry.append(detail); }
    if (item.tokens && Object.keys(item.tokens).length) { const usage = document.createElement("small"); usage.className = "session-usage"; usage.textContent = `토큰 ${JSON.stringify(item.tokens)}`; entry.append(usage); }
    feed.append(entry);
  }
  if (nearBottom) feed.scrollTop = feed.scrollHeight;
}

function renderOverview() {
  const box = $("overviewContent"); box.replaceChildren();
  const rows = [
    ["목표", app.current.solver?.goal || "제공된 자료에서 문제를 해결합니다."],
    ["설명", app.current.description || "제공된 설명이 없습니다."],
    ["플랫폼", app.current.platform_url || "없음"],
    ["계획 라운드", String(app.current.solver?.round || 0)],
    ["자료", `${(app.current.artifacts || []).length}개`],
  ];
  for (const [label, value] of rows) {
    const row = document.createElement("div"); row.className = "overview-row";
    const title = document.createElement("strong"); title.textContent = label;
    const content = document.createElement("p"); content.textContent = value;
    row.append(title, content); box.append(row);
  }
}

function renderCandidates() {
  const list = $("candidateList"); list.replaceChildren();
  if (!app.candidates.length) { const p = document.createElement("p"); p.className = "muted"; p.textContent = "아직 검증 후보가 없습니다."; list.append(p); return; }
  for (const candidate of app.candidates) {
    const card = document.createElement("article"); card.className = "candidate-card";
    const title = document.createElement("strong"); title.textContent = `후보 #${candidate.id} · ${candidate.kind === "flag" ? "플래그" : "로컬 입력"}`;
    const badge = document.createElement("span"); badge.className = "status " + candidate.status; badge.textContent = statusNames[candidate.status] || candidate.status;
    const info = document.createElement("p"); info.textContent = `의도 ${candidate.intent_id} · 제안 근거 #${candidate.evidence_run}` + (candidate.verify_run ? ` · 재검증 #${candidate.verify_run}` : "");
    card.append(title, badge, info); list.append(card);
  }
}

function renderFacts() {
  const list = $("factList"); list.replaceChildren();
  const facts = [...(app.current.facts || [])].reverse();
  const hypotheses = [...(app.current.hypotheses || [])].reverse();
  if (!facts.length && !hypotheses.length) {
    const p = document.createElement("p"); p.className = "muted"; p.textContent = "아직 기록된 사실이나 가설이 없습니다."; list.append(p); return;
  }
  for (const fact of facts) {
    const card = document.createElement("article"); card.className = "fact-card";
    const heading = document.createElement("h3"); heading.textContent = `사실 · ${fact.summary}`;
    const detail = document.createElement("p"); detail.textContent = fact.detail || "";
    const meta = document.createElement("small"); meta.textContent = `${fact.intent_id || "작업 전체"} · ${fact.confidence === "inferred" ? "추론" : "관찰"} · 근거 #${fact.evidence_run}`;
    card.append(heading, detail, meta);
    if (fact.evidence_run) { const button = document.createElement("button"); button.type = "button"; button.className = "inspector-run"; button.textContent = "근거 보기"; button.addEventListener("click", () => openRun(fact.evidence_run)); card.append(button); }
    list.append(card);
  }
  for (const hypothesis of hypotheses) {
    const card = document.createElement("article"); card.className = "fact-card";
    const heading = document.createElement("h3"); heading.textContent = `가설 · ${hypothesis.claim}`;
    const detail = document.createElement("p"); detail.textContent = hypothesis.observation || hypothesis.test || "";
    const meta = document.createElement("small"); meta.textContent = `${statusNames[hypothesis.status] || hypothesis.status} · ${hypothesis.intent_id || "작업 전체"}`;
    card.append(heading, detail, meta); list.append(card);
  }
}

function renderReport() {
  const box = $("reportContent"); box.replaceChildren();
  const status = app.current.solver?.state || app.current.status;
  const cards = [
    ["결과", statusNames[status] || status, `확정 플래그 ${app.current.flag_candidates || 0}개 · 로컬 입력 ${app.current.local_answer_count || 0}개`],
    ["작업 현황", `의도 ${(app.current.intents || []).length}개 · 사실 ${(app.current.facts || []).length}개`, `분석 실행 ${(app.current.tool_runs || []).length}회`],
  ];
  if (app.current.blocker) cards.push(["막힌 이유", app.current.blocker, ""]);
  for (const [title, value, detail] of cards) {
    const card = document.createElement("article"); card.className = "report-card";
    const heading = document.createElement("h3"); heading.textContent = title;
    const body = document.createElement("p"); body.textContent = value;
    card.append(heading, body);
    if (detail) { const small = document.createElement("p"); small.textContent = detail; card.append(small); }
    box.append(card);
  }
  const runs = app.current.result_runs || [];
  if (runs.length) {
    const card = document.createElement("article"); card.className = "report-card";
    const heading = document.createElement("h3"); heading.textContent = "결과 근거"; card.append(heading);
    for (const sequence of runs) { const button = document.createElement("button"); button.type = "button"; button.className = "inspector-run"; button.textContent = `실행 #${sequence}`; button.addEventListener("click", () => openRun(sequence)); card.append(button); }
    box.append(card);
  }
}

function graphPositions(graph) {
  const nodeMap = new Map(graph.nodes.map((node) => [node.id, node]));
  const parents = new Map(graph.edges.map((edge) => [edge.to, edge.from]));
  const depthCache = new Map([["challenge", 0]]);
  function depth(id, seen = new Set()) {
    if (depthCache.has(id)) return depthCache.get(id);
    if (seen.has(id)) return 1;
    seen.add(id);
    const parent = parents.get(id);
    const value = parent && nodeMap.has(parent) ? Math.min(6, depth(parent, seen) + 1) : 1;
    depthCache.set(id, value);
    return value;
  }
  const rows = new Map();
  const positions = new Map();
  for (const node of graph.nodes) {
    const column = depth(node.id);
    const row = rows.get(column) || 0;
    rows.set(column, row + 1);
    positions.set(node.id, { x: 34 + column * 276, y: 166 + row * 115 });
  }
  return { positions, width: Math.max(760, (Math.max(...[...positions.values()].map((p) => p.x), 34)) + 264),
           height: Math.max(520, (Math.max(...[...positions.values()].map((p) => p.y), 166)) + 126) };
}

function renderGraph() {
  const viewport = $("graphViewport");
  const oldX = viewport.scrollLeft, oldY = viewport.scrollTop;
  viewport.replaceChildren();
  const graph = app.graph;
  if (!graph?.nodes?.length) return;
  const { positions, width, height } = graphPositions(graph);
  if (app.graphZoom === null) app.graphZoom = Math.max(0.55, Math.min(1, (viewport.clientWidth - 32) / width, (viewport.clientHeight - 32) / height));
  const canvas = document.createElement("div");
  canvas.className = "graph-canvas";
  canvas.style.width = width + "px";
  canvas.style.height = height + "px";
  canvas.style.zoom = String(app.graphZoom);
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("width", width);
  svg.setAttribute("height", height);
  const edgeColors = {goal:"#10b981",planned:"#6366f1",observed:"#f59e0b",derived:"#10b981",proposed:"#f59e0b",verified:"#ef4444"};
  const edgeNames = {goal:"파생",planned:"의도 체인",observed:"산출",derived:"파생",proposed:"산출",verified:"검증"};
  const defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");
  for (const [kind, color] of Object.entries(edgeColors)) {
    const marker = document.createElementNS("http://www.w3.org/2000/svg", "marker");
    marker.setAttribute("id", `arrow-${kind}`); marker.setAttribute("markerWidth", "8"); marker.setAttribute("markerHeight", "8"); marker.setAttribute("refX", "8"); marker.setAttribute("refY", "3"); marker.setAttribute("orient", "auto");
    const tip = document.createElementNS("http://www.w3.org/2000/svg", "path");
    tip.setAttribute("d", "M 0 0 L 8 3 L 0 6 Z"); tip.setAttribute("fill", color);
    marker.append(tip); defs.append(marker);
  }
  svg.append(defs);
  for (const edge of graph.edges) {
    const start = positions.get(edge.from), end = positions.get(edge.to);
    if (!start || !end) continue;
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    const x1 = start.x + 226, y1 = start.y + 40, x2 = end.x, y2 = end.y + 40;
    path.setAttribute("d", `M ${x1} ${y1} C ${x1 + 25} ${y1}, ${x2 - 25} ${y2}, ${x2} ${y2}`);
    path.setAttribute("fill", "none");
    path.setAttribute("stroke", edgeColors[edge.kind] || "#c5d1e1");
    path.setAttribute("stroke-width", "1.6");
    path.setAttribute("marker-end", `url(#arrow-${edgeColors[edge.kind] ? edge.kind : "derived"})`);
    svg.append(path);
    if (edge.kind && x2 - x1 > 25) {
      const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
      text.setAttribute("x", String((x1 + x2) / 2)); text.setAttribute("y", String((y1 + y2) / 2 - 7)); text.setAttribute("text-anchor", "middle"); text.setAttribute("fill", edgeColors[edge.kind] || "#888"); text.setAttribute("font-size", "9");
      text.textContent = edgeNames[edge.kind] || edge.kind; svg.append(text);
    }
  }
  canvas.append(svg);
  for (const node of graph.nodes) {
    const point = positions.get(node.id);
    const button = document.createElement("button");
    button.type = "button";
    button.className = `graph-node ${node.kind}` + (app.selectedNode === node.id ? " selected" : "");
    button.style.left = point.x + "px";
    button.style.top = point.y + "px";
    const kind = document.createElement("span"); kind.className = "node-kind";
    const icon = document.createElement("i"); icon.textContent = ({challenge:"⚑",goal:"◎",intent:"⊙",fact:"♙",hypothesis:"◇",candidate:"✦",verdict:"✓"})[node.kind] || "•";
    kind.append(icon, document.createTextNode(kindNames[node.kind] || node.kind));
    const label = document.createElement("span"); label.className = "node-label"; label.textContent = node.label;
    const status = document.createElement("span"); status.className = "node-status"; status.textContent = statusNames[node.status] || node.status || "";
    button.append(kind, label, status);
    button.addEventListener("click", () => { app.selectedNode = node.id; renderGraph(); });
    canvas.append(button);
  }
  viewport.append(canvas);
  viewport.scrollLeft = oldX; viewport.scrollTop = oldY;
  const mini = $("graphMiniMap"); mini.replaceChildren();
  for (const node of graph.nodes) {
    const point = positions.get(node.id);
    const dot = document.createElement("button"); dot.type = "button"; dot.className = `graph-mini-dot ${node.kind}`;
    dot.style.left = `${8 + point.x / width * (mini.clientWidth - 16)}px`;
    dot.style.top = `${8 + point.y / height * (mini.clientHeight - 16)}px`;
    dot.title = node.label;
    dot.addEventListener("click", () => { viewport.scrollLeft = point.x * app.graphZoom - viewport.clientWidth / 2; viewport.scrollTop = point.y * app.graphZoom - viewport.clientHeight / 2; });
    mini.append(dot);
  }
  renderInspector(graph.nodes.find((node) => node.id === app.selectedNode));
}

function renderInspector(node) {
  const inspector = $("nodeInspector");
  inspector.replaceChildren();
  inspector.hidden = !node;
  if (!node) return;
  const close = document.createElement("button"); close.type = "button"; close.className = "inspector-close"; close.textContent = "×"; close.setAttribute("aria-label", "닫기"); close.addEventListener("click", () => { app.selectedNode = null; renderGraph(); }); inspector.append(close);
  const kind = document.createElement("div"); kind.className = "kind"; kind.textContent = kindNames[node.kind] || node.kind;
  const title = document.createElement("h3"); title.textContent = node.label;
  inspector.append(kind, title);
  const entries = [];
  if (node.status) entries.push(["상태", statusNames[node.status] || node.status, "status"]);
  const data = node.data || {};
  for (const [label, key] of [["설명", "detail"], ["검사", "test"], ["반증 조건", "falsifier"], ["관찰", "observation"], ["정찰 근거", "basis_run"], ["근거 실행", "evidence_run"], ["재검증 실행", "verify_run"], ["실행 목록", "evidence_runs"], ["상위 의도", "parent_id"], ["연결된 의도", "intent_id"]]) {
    if (data[key] !== undefined && data[key] !== null && data[key] !== "") entries.push([label, data[key], key]);
  }
  const list = document.createElement("dl");
  for (const [label, value, key] of entries) {
    const dt = document.createElement("dt"); dt.textContent = label;
    const dd = document.createElement("dd");
    const runs = key === "evidence_runs" ? value : [value];
    if (["basis_run", "evidence_run", "verify_run", "evidence_runs"].includes(key) && Array.isArray(runs)) {
      for (const sequence of runs) {
        const button = document.createElement("button"); button.type = "button"; button.className = "inspector-run";
        button.textContent = `실행 #${sequence}`; button.addEventListener("click", () => openRun(Number(sequence)));
        dd.append(button);
      }
    } else dd.textContent = String(value);
    list.append(dt, dd);
  }
  inspector.append(list);
}

function renderActivity() {
  const challenge = app.current;
  const events = $("liveEvents"); events.replaceChildren();
  const recent = app.activities.slice(-8).reverse();
  if (recent.length) for (const event of recent) {
    const item = document.createElement("span"); item.className = "live-chip";
    item.textContent = `${plainDate(event.created_at)} · ${event.summary}`; events.append(item);
  }
  const list = $("runList"); list.replaceChildren();
  const runs = [...(challenge.tool_runs || [])].reverse();
  if (!runs.length) { const p = document.createElement("p"); p.className = "muted"; p.textContent = "아직 실행 기록이 없습니다."; list.append(p); }
  for (const run of runs) {
    const row = document.createElement("div"); row.className = "run-item";
    const button = document.createElement("button"); button.type = "button";
    const title = document.createElement("strong"); title.textContent = `#${run.sequence} · ${run.profile}`;
    const command = document.createElement("code"); command.textContent = run.command;
    const meta = document.createElement("small"); meta.textContent = [run.intent_id, run.hypothesis_id, plainDate(run.time)].filter(Boolean).join(" · ");
    button.append(title, command, meta);
    button.addEventListener("click", () => openRun(run.sequence));
    const exit = document.createElement("span"); exit.className = "exit" + (run.exit_code ? " bad" : ""); exit.textContent = run.exit_code === 0 ? "성공" : `종료 ${run.exit_code}`;
    row.append(button, exit); list.append(row);
  }
}

function renderFiles() {
  const list = $("fileList"); list.replaceChildren();
  const files = app.current.artifacts || [];
  if (!files.length) { const p = document.createElement("p"); p.className = "muted"; p.textContent = "등록된 파일이 없습니다."; list.append(p); }
  for (const file of files) {
    const row = document.createElement("div"); row.className = "file-item";
    const text = document.createElement("div");
    const title = document.createElement("strong"); title.textContent = file.path;
    const meta = document.createElement("small"); meta.textContent = `${file.kind} · ${Math.ceil(file.size / 1024)} KiB · SHA-256 ${file.sha256.slice(0, 12)}…`;
    text.append(title, meta); row.append(text); list.append(row);
  }
}

async function openRun(sequence) {
  try {
    const result = await api(`/challenges/${encodeURIComponent(app.selected)}/runs/${sequence}`);
    setText("runDialogTitle", `실행 #${sequence}`);
    setText("runOutput", `명령: ${result.run.command}\n\n표준 출력\n${result.stdout || "(없음)"}\n\n표준 오류\n${result.stderr || "(없음)"}`);
    $("runDialog").showModal();
  } catch (error) { toast(error.message); }
}

async function refresh(forceList = false) {
  if (app.busy || app.refreshing) { if (forceList) app.lastListAt = 0; return; }
  app.refreshing = true;
  try {
    if (forceList || !app.lastListAt || Date.now() - app.lastListAt > 30000) {
      app.challenges = await api("/challenges");
      app.lastListAt = Date.now();
      if (app.selected && !app.challenges.some((item) => item.challenge_id === app.selected)) app.selected = null;
    }
    if (app.selected) {
      const selected = app.selected;
      const [challenge, graph, candidates] = await Promise.all([
        api(`/challenges/${encodeURIComponent(app.selected)}`),
        api(`/challenges/${encodeURIComponent(app.selected)}/graph`),
        api(`/challenges/${encodeURIComponent(app.selected)}/candidates`),
      ]);
      if (selected !== app.selected) return;
      app.current = challenge; app.graph = graph; app.candidates = candidates;
      await syncActivity();
      connectStream();
      const row = app.challenges.find((item) => item.challenge_id === challenge.challenge_id);
      if (row) row.status = challenge.status;
    } else { app.current = null; app.graph = null; }
    renderSidebar();
    renderDetail();
  } finally { app.refreshing = false; }
}

async function syncActivity() {
  if (!app.selected) return;
  for (let page = 0; page < 20; page++) {
    const result = await api(`/challenges/${encodeURIComponent(app.selected)}/activity?since=${app.activityCursor}&limit=500`);
    for (const item of result.items) {
      if (item.seq > app.activityCursor) { app.activities.push(item); app.activityCursor = item.seq; }
    }
    if (!result.items.length || app.activityCursor >= result.last_seq) break;
  }
}

let refreshTimer;
function connectStream() {
  if (!app.selected || app.eventSource) return;
  const selected = app.selected;
  const stream = new EventSource(`/api/challenges/${encodeURIComponent(selected)}/activity/stream?since=${app.activityCursor}`);
  app.eventSource = stream;
  stream.onopen = () => { app.sseLive = true; if (app.tab === "sessions" && app.current) renderSessions(); };
  stream.onerror = () => { app.sseLive = false; if (app.tab === "sessions" && app.current) renderSessions(); };
  stream.addEventListener("activity", (event) => {
    if (app.selected !== selected) return;
    try {
      const item = JSON.parse(event.data);
      if (item.seq <= app.activityCursor) return;
      app.activities.push(item); app.activityCursor = item.seq;
      if (app.tab === "sessions") renderSessions();
      clearTimeout(refreshTimer);
      refreshTimer = setTimeout(() => refresh().catch(() => {}), 350);
    } catch { /* The next refresh can replay this event. */ }
  });
}

async function createChallenge(event) {
  event.preventDefault();
  app.busy = true;
  const submit = $("newForm").querySelector('button[type="submit"].primary');
  submit.disabled = true;
  try {
    const body = new FormData($("newForm"));
    const challenge = await api("/challenges", { method: "POST", body });
    $("newDialog").close(); $("newForm").reset();
    if (app.eventSource) { app.eventSource.close(); app.eventSource = null; }
    app.activities = []; app.activityCursor = 0; app.candidates = [];
    app.selectedSession = "main:0";
    app.selectedNode = null; app.graphZoom = null;
    app.selected = challenge.challenge_id;
    location.hash = `challenge/${encodeURIComponent(app.selected)}`;
    toast("문제를 만들었습니다.");
  } catch (error) { toast(error.message); }
  finally { app.busy = false; submit.disabled = false; await refresh(true).catch((error) => toast(error.message)); }
}

async function openSettings() {
  try {
    const value = await api("/config");
    setModelLabel(value);
    const form = $("settingsForm");
    form.elements.auth_mode.value = value.auth_mode;
    form.elements.oauth_model.value = value.oauth_model || "";
    form.elements.api_model.value = value.api_model || "openai/gpt-5.1";
    form.elements.api_key.value = "";
    form.elements.clear_api_key.checked = false;
    setText("oauthState", value.oauth_ready ? "연결 가능" : value.oauth_available ? "다시 로그인 필요" : "인증 파일 없음");
    setText("apiKeyState", value.has_api_key ? "저장된 API 키가 있습니다." : "저장된 API 키가 없습니다.");
    showAuthFields();
    $("settingsDialog").showModal();
  } catch (error) { toast(error.message); }
}

function setModelLabel(value) {
  const model = value.auth_mode === "oauth" ? value.oauth_model : value.api_model;
  setText("detailModel", model ? model.split("/").pop() : "기본 설정 따름");
}

function showAuthFields() {
  const mode = $("settingsForm").elements.auth_mode.value;
  $("oauthFields").hidden = mode !== "oauth";
  $("apiFields").hidden = mode !== "api_key";
}

async function saveSettings(event) {
  event.preventDefault();
  const form = $("settingsForm");
  const body = {
    auth_mode: form.elements.auth_mode.value,
    oauth_model: form.elements.oauth_model.value.trim(),
    api_model: form.elements.api_model.value.trim(),
    api_key: form.elements.api_key.value.trim(),
    clear_api_key: form.elements.clear_api_key.checked,
  };
  try {
    const value = await api("/config", { method: "PUT", body: JSON.stringify(body) });
    setModelLabel(value);
    $("settingsDialog").close();
    toast("모델 설정을 저장했습니다.");
  } catch (error) { toast(error.message); }
}

function toggleSidebar() {
  if (window.innerWidth <= 800) document.body.classList.toggle("sidebar-open");
  else document.body.classList.toggle("sidebar-collapsed");
}

function adjustGraphZoom(factor) {
  app.graphZoom = Math.max(0.4, Math.min(2, (app.graphZoom || 1) * factor));
  renderGraph();
}

async function solverAction(action) {
  if (!app.selected || app.busy) return;
  app.busy = true; renderDetail();
  try {
    await api(`/challenges/${encodeURIComponent(app.selected)}/${action}`, { method: "POST" });
    toast(action === "solve" ? "작업을 시작했습니다." : action === "resume" ? "작업을 재개했습니다." : "작업을 일시정지했습니다.");
  } catch (error) { toast(error.message); }
  finally { app.busy = false; await refresh().catch((error) => toast(error.message)); }
}

async function sendChat(event) {
  event.preventDefault();
  if (!app.selected) return;
  const input = $("chatMessage");
  const message = input.value.trim();
  if (!message) return;
  const submit = $("chatForm").querySelector('button[type="submit"]');
  submit.disabled = true;
  try {
    await api(`/challenges/${encodeURIComponent(app.selected)}/chat`, { method: "POST", body: JSON.stringify({ message }) });
    input.value = "";
    await syncActivity(); renderSessions();
  } catch (error) { toast(error.message); }
  finally { submit.disabled = false; }
}

function bind() {
  $("newButton").addEventListener("click", () => $("newDialog").showModal());
  $("emptyNewButton").addEventListener("click", () => $("newDialog").showModal());
  $("tasksNav").addEventListener("click", () => select(null));
  $("backButton").addEventListener("click", () => select(null));
  $("sidebarToggle").addEventListener("click", toggleSidebar);
  $("emptySidebarToggle").addEventListener("click", toggleSidebar);
  $("sidebarClose").addEventListener("click", () => document.body.classList.remove("sidebar-open"));
  $("cancelNew").addEventListener("click", () => $("newDialog").close());
  $("newForm").addEventListener("submit", createChallenge);
  $("settingsButton").addEventListener("click", openSettings);
  $("detailSettingsButton").addEventListener("click", openSettings);
  $("cancelSettings").addEventListener("click", () => $("settingsDialog").close());
  $("settingsForm").addEventListener("submit", saveSettings);
  $("settingsForm").querySelectorAll('input[name="auth_mode"]').forEach((input) => input.addEventListener("change", showAuthFields));
  $("solveButton").addEventListener("click", () => solverAction(app.current?.solver?.state === "paused" ? "resume" : "solve"));
  $("stopButton").addEventListener("click", () => solverAction("stop"));
  $("chatForm").addEventListener("submit", sendChat);
  $("chatMessage").addEventListener("keydown", (event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); $("chatForm").requestSubmit(); } });
  $("graphZoomIn").addEventListener("click", () => adjustGraphZoom(1.25));
  $("graphZoomOut").addEventListener("click", () => adjustGraphZoom(0.8));
  $("graphFit").addEventListener("click", () => { app.graphZoom = null; $("graphViewport").scrollTo(0, 0); renderGraph(); });
  $("closeRun").addEventListener("click", () => $("runDialog").close());
  document.querySelectorAll(".tab").forEach((button) => button.addEventListener("click", () => { app.tab = button.dataset.tab; renderTabs(); }));
  document.querySelectorAll(".modal .close-button").forEach((button) => button.addEventListener("click", () => button.closest("dialog").close()));
}

async function boot() {
  bind();
  const match = location.hash.match(/^#challenge\/([a-z0-9.-]+)$/);
  if (match) app.selected = match[1];
  try {
    await api("/health");
    $("serviceStatus").classList.add("online");
    $("serviceStatus").lastChild.textContent = "연결됨";
    api("/config").then(setModelLabel).catch(() => {});
    await refresh();
  } catch (error) { toast(error.message); }
  setInterval(() => refresh().catch(() => {}), 3000);
}

boot();
