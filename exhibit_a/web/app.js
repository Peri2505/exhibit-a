/* Exhibit A — case-file UI. Consumes the agent's SSE event stream. */
const $ = (s, r = document) => r.querySelector(s);
const el = (t, c, h) => { const e = document.createElement(t); if (c) e.className = c; if (h != null) e.innerHTML = h; return e; };
const esc = s => (s ?? "").replace(/[&<>]/g, m => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[m]));
const money = n => "$" + Number(n || 0).toFixed(4);

const state = { findings: {}, models: {}, totals: { cost: 0, calls: 0 }, source: null };
let es = null;

/* ---------- model routing panel ---------- */
async function loadConfig() {
  const cfg = await fetch("/api/config").then(r => r.json()).catch(() => null);
  if (!cfg) return;
  state.models = cfg.models;
  const box = $("#models");
  box.innerHTML = "";
  for (const [role, m] of Object.entries(cfg.models)) {
    const row = el("div", `mrow ${role}`); row.id = `m-${role}`;
    row.innerHTML = `
      <div class="mhead"><span class="mtier ${role}">${role.toUpperCase()}</span>
        <span class="mcost" style="font-family:var(--mono);font-size:12px">$0.0000</span></div>
      <div class="mid">${esc(m.model_id)}</div>
      <div class="mjob">${esc(m.job)}</div>
      <div class="mstats"><span>calls <b data-calls>0</b></span>
        <span>tok <b data-tok>0</b></span><span><b data-lat>—</b></span></div>
      <div class="spark" style="color:var(--${role === 'nano' ? 'blue' : role === 'super' ? 'amber' : 'violet'})"><i></i></div>`;
    box.appendChild(row);
  }
  if (!cfg.has_api_key) $("#repoInput").placeholder = "Demo mode (no API key) — click Replay demo";
}

/* ---------- case cards ---------- */
const STEPS = [["suspected", "Suspected"], ["proven", "Proven"], ["patched", "Patched"], ["verified", "Fixed"]];
const STAGE_RANK = { suspected: 0, proven: 1, patched: 2, verified: 3, dismissed: 0 };

function cardHTML(f) {
  const rank = STAGE_RANK[f.stage] ?? 0;
  const track = STEPS.map(([key, lbl], i) => {
    let cls = "step";
    if (f.stage === "verified" && i <= 3) cls += i === 3 ? " ok" : " done";
    else if (i < rank) cls += " done";
    else if (i === rank && f.stage !== "dismissed") cls += " active";
    return `<div class="${cls}"><div class="dot"></div><label>${lbl}</label></div>`;
  }).join("");

  const proven = ["proven", "patched", "verified"].includes(f.stage);
  const evCls = f.stage === "verified" ? "pass" : proven ? "fail" : "";
  const verdict = f.stage === "verified" ? "ALL TESTS GREEN"
    : proven ? "PROOF FAILS ON VULNERABLE CODE" : "awaiting proof";
  const evidence = proven ? `
    <div class="evidence ${evCls}">
      <div class="ehead"><span>exhibit · ${esc(f.test_path || "proof test")}</span>
        <span class="verdict">${f.stage === "verified" ? "✓" : "✗"} ${verdict}</span></div>
      <div class="ebody">${esc((f.claim || "")).slice(0, 240)}</div>
    </div>` : "";

  return `
    <div class="cardtop">
      <div><div class="cid">${f.id} · ${esc(f.cwe)}</div><h3>${esc(f.title)}</h3></div>
      <span class="sev ${f.severity}">${f.severity}</span>
    </div>
    <div class="meta"><b>${esc(f.path)}</b>${f.line ? ":" + f.line : ""} · ${esc(f.category)}</div>
    <div class="track">${track}</div>
    ${evidence}`;
}

function upsertCard(f) {
  state.findings[f.id] = { ...state.findings[f.id], ...f };
  f = state.findings[f.id];
  $("#emptyState").style.display = "none";
  let card = $("#card-" + f.id);
  if (!card) {
    card = el("div", "card"); card.id = "card-" + f.id;
    card.onclick = () => openDrawer(f.id);
    $("#cards").appendChild(card);
  }
  card.className = "card open-ev" + (f.stage === "dismissed" ? " dismissed-card" : "");
  card.innerHTML = cardHTML(f);
  refreshStats();
}

function refreshStats() {
  const all = Object.values(state.findings);
  const count = p => all.filter(p).length;
  $("#statSuspected").textContent = all.length;
  $("#statProven").textContent = count(f => ["proven", "patched", "verified"].includes(f.stage));
  $("#statVerified").textContent = count(f => f.stage === "verified");
  $("#statDismissed").textContent = count(f => f.stage === "dismissed");
}

/* ---------- drawer ---------- */
function colorDiff(diff) {
  return esc(diff).split("\n").map(l => {
    if (l.startsWith("+") && !l.startsWith("+++")) return `<span class="add">${l}</span>`;
    if (l.startsWith("-") && !l.startsWith("---")) return `<span class="del">${l}</span>`;
    if (l.startsWith("@@")) return `<span class="hunk">${l}</span>`;
    return l;
  }).join("\n");
}
function openDrawer(id) {
  const f = state.findings[id];
  $("#drawerBody").innerHTML = `
    <div class="dpad">
      <div class="cid" style="font-family:var(--mono);color:var(--muted)">${f.id} · ${esc(f.cwe)} · ${esc(f.category)}</div>
      <h2>${esc(f.title)}</h2>
      <div class="dmeta">${esc(f.path)}${f.line ? ":" + f.line : ""} · severity ${f.severity} · stage ${f.stage}</div>
      <div class="claimbox">${esc(f.explanation || "")}</div>
      ${f.claim ? `<div class="dsec"><h4>The claim this exhibit proves</h4><div class="claimbox">${esc(f.claim)}</div></div>` : ""}
      ${f.evidence ? `<div class="dsec"><h4>Vulnerable code</h4><pre>${esc(f.evidence)}</pre></div>` : ""}
      ${f.test_code ? `<div class="dsec"><h4>Exhibit A — the proof test</h4><pre>${esc(f.test_code)}</pre></div>` : ""}
      ${f.diff ? `<div class="dsec"><h4>The fix${f.patch_summary ? " — " + esc(f.patch_summary) : ""}</h4><pre class="diff">${colorDiff(f.diff)}</pre></div>` : ""}
      ${f.note ? `<div class="dsec"><h4>Note</h4><div class="claimbox">${esc(f.note)}</div></div>` : ""}
    </div>`;
  $("#drawer").classList.add("open"); $("#scrim").classList.add("on");
}
function closeDrawer() { $("#drawer").classList.remove("open"); $("#scrim").classList.remove("on"); }

/* ---------- live feed ---------- */
function feed(msg, hi) {
  const ul = $("#feed");
  const li = el("li", hi ? "hi" : "");
  li.innerHTML = `<span class="ts">${(performance.now() / 1000).toFixed(0)}»</span><span>${esc(msg)}</span>`;
  ul.insertBefore(li, ul.firstChild);
  while (ul.children.length > 60) ul.removeChild(ul.lastChild);
}

/* ---------- event handling ---------- */
function markActive(role) {
  document.querySelectorAll(".mrow").forEach(r => r.classList.remove("active"));
  const row = $("#m-" + role); if (row) row.classList.add("active");
}
function onLLM(e) {
  const m = state.models[e.role]; if (!m) return;
  const row = $("#m-" + e.role);
  const calls = +row.querySelector("[data-calls]").textContent + 1;
  const tok = +row.querySelector("[data-tok]").textContent.replace(/,/g, "") + e.input_tokens + e.output_tokens;
  row.querySelector("[data-calls]").textContent = calls;
  row.querySelector("[data-tok]").textContent = tok.toLocaleString();
  row.querySelector("[data-lat]").textContent = Math.round(e.latency_ms) + " ms";
  const prev = parseFloat(row.querySelector(".mcost").textContent.slice(1)) || 0;
  row.querySelector(".mcost").textContent = money(prev + e.cost);
  state.totals.cost += e.cost; state.totals.calls += 1;
  $("#totalCost").textContent = money(state.totals.cost);
  $("#totalCalls").textContent = state.totals.calls;
  markActive(e.role);
  const maxTok = Math.max(...[...document.querySelectorAll("[data-tok]")].map(x => +x.textContent.replace(/,/g, "") || 1));
  document.querySelectorAll(".mrow").forEach(r => {
    const t = +r.querySelector("[data-tok]").textContent.replace(/,/g, "") || 0;
    r.querySelector(".spark i").style.width = (100 * t / maxTok) + "%";
  });
}

const HANDLERS = {
  "scan.start": e => { resetBoard(); feed(`Opening case on ${e.source}`, true); },
  "scan.loaded": e => feed(`Loaded ${e.file_count} source files`),
  "sandbox.ready": e => { $("#sandboxBadge").textContent = "sandbox: " + e.mode; feed(`Sandbox ready (${e.mode})`); },
  "sandbox.deps": e => feed(`Dependencies: ${e.status}`),
  "suite.baseline": e => feed(`Baseline suite: ${e.summary}`, true),
  "stage": e => { if (e.role) markActive(e.role); feed(e.message, true); },
  "stage.warn": e => feed("⚠ " + e.message),
  "triage.result": e => feed(`Triage picked ${e.suspects.length} suspects`),
  "llm.call": onLLM,
  "finding.suspected": e => { upsertCard(e.finding); feed(`Suspected: ${e.finding.title}`); },
  "finding.proven": e => { upsertCard(e.finding); feed(`⚖ PROVEN: ${e.finding.title}`, true); },
  "finding.verified": e => { upsertCard(e.finding); feed(`✓ FIXED & VERIFIED: ${e.finding.title}`, true); },
  "finding.dismissed": e => { upsertCard(e.finding); feed(`dropped (unproven): ${e.finding.title}`); },
  "finding.patch_failed": e => { upsertCard(e.finding); feed(`proven, manual fix needed: ${e.finding.title}`); },
  "prove.run": e => feed(`  proof run → ${e.status}`),
  "patch.run": e => feed(`  patch run → proof ${e.proof_status}, suite ${e.suite_status}`),
  "scan.done": e => { markActive(null); feed(`Case closed: ${e.verified} fixed, ${e.proven} proven of ${e.total}`, true); },
  "usage.final": () => {},
  "error": e => feed("ERROR: " + e.message, true),
};

function resetBoard() {
  state.findings = {}; state.totals = { cost: 0, calls: 0 };
  $("#cards").innerHTML = ""; $("#feed").innerHTML = "";
  $("#totalCost").textContent = "$0.0000"; $("#totalCalls").textContent = "0";
  document.querySelectorAll(".mrow .mcost").forEach(x => x.textContent = "$0.0000");
  document.querySelectorAll("[data-calls]").forEach(x => x.textContent = "0");
  document.querySelectorAll("[data-tok]").forEach(x => x.textContent = "0");
  document.querySelectorAll("[data-lat]").forEach(x => x.textContent = "—");
  document.querySelectorAll(".spark i").forEach(x => x.style.width = "0");
  refreshStats();
}

function startStream(url) {
  if (es) es.close();
  $("#emptyState").style.display = "none";
  es = new EventSource(url);
  es.onmessage = ev => {
    const data = JSON.parse(ev.data);
    (HANDLERS[data.type] || (() => {}))(data);
  };
  es.addEventListener("end", () => es.close());
  es.onerror = () => { feed("stream closed"); es.close(); };
}

/* ---------- wire up ---------- */
$("#scanForm").addEventListener("submit", e => {
  e.preventDefault();
  const v = $("#repoInput").value.trim();
  if (!v) { startStream("/api/scan?demo=true"); return; }
  const p = v.startsWith("http") ? "repo=" + encodeURIComponent(v) : "local=" + encodeURIComponent(v);
  startStream("/api/scan?" + p);
});
$("#demoBtn").addEventListener("click", () => startStream("/api/scan?demo=true"));
$("#drawerClose").addEventListener("click", closeDrawer);
$("#scrim").addEventListener("click", closeDrawer);
document.addEventListener("keydown", e => { if (e.key === "Escape") closeDrawer(); });

loadConfig();
