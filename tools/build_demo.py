"""Record a demo run of Exhibit A against the NoteVault target.

Drives the REAL orchestrator and REAL sandbox, but with a scripted model so it
needs no API key and is deterministic. The proof tests and patches below are
genuine: the sandbox actually runs them, so each must fail on the vulnerable
code and pass after the fix, or this script reports it.

Output: runs/demo/events.jsonl  (replayed by the UI and used in the video)
"""
import asyncio
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from exhibit_a.agent import ExhibitAgent          # noqa: E402
from exhibit_a.config import settings             # noqa: E402
from exhibit_a.events import EventBus             # noqa: E402
from exhibit_a.llm import Usage                   # noqa: E402

TARGET = ROOT / "demo_target"

TRIAGE = {"files": [
    {"path": "app.py", "risk": 9, "reason": "auth, SQL, CORS, secrets all here"},
]}

ANALYSIS = {"findings": [
    {"title": "SQL injection in login", "cwe": "CWE-89", "category": "sqli",
     "severity": "critical", "line": 98,
     "evidence": "query = f\"SELECT * FROM users WHERE username = '{username}' ...\"",
     "expected_secure_behavior": "A crafted username must not bypass the password check; login returns 401.",
     "explanation": "The login SQL is built by string formatting, so input changes the query itself. A crafted username can make the WHERE clause always true and log in without a valid password."},
    {"title": "Any user can read any note (IDOR)", "cwe": "CWE-639", "category": "idor",
     "severity": "high", "line": 132,
     "evidence": "SELECT ... FROM notes WHERE id = ?  (no owner check)",
     "expected_secure_behavior": "Reading a note you do not own returns 404/403, not its contents.",
     "explanation": "get_note looks up a note by id but never checks who owns it. Any logged-in user can read everyone else's notes by changing the id."},
    {"title": "Admin user list has no authentication", "cwe": "CWE-306", "category": "missing-auth",
     "severity": "critical", "line": 143,
     "evidence": "@app.get('/api/admin/users')  def admin_users(): ... (no current_user check)",
     "expected_secure_behavior": "Request without a valid admin token returns 401/403.",
     "explanation": "The admin endpoint lists every user but never checks for a token or admin rights. Anyone on the internet can list all accounts."},
    {"title": "Hardcoded signing secret", "cwe": "CWE-798", "category": "hardcoded-secret",
     "severity": "high", "line": 20,
     "evidence": "SECRET_KEY = \"notevault-dev-secret-2026\"",
     "expected_secure_behavior": "The signing key is read from the environment, not a constant in source.",
     "explanation": "The token signing key is written directly in the code and in the public repo. Anyone who sees it can forge valid login tokens for any user."},
    {"title": "CORS reflects any origin with credentials", "cwe": "CWE-942", "category": "cors",
     "severity": "medium", "line": 86,
     "evidence": "resp.headers['Access-Control-Allow-Origin'] = origin  (+ credentials true)",
     "expected_secure_behavior": "An untrusted Origin is not echoed back when credentials are allowed.",
     "explanation": "The app echoes whatever Origin the browser sends and allows credentials. That lets any malicious website make authenticated requests on a logged-in user's behalf."},
]}


def _proof(body: str) -> str:
    return ("import os, sys\n"
            "sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))\n\n"
            + body)

PROOFS = {
    "sqli": (_proof(
        'def test_sql_injection_cannot_bypass_login(client):\n'
        '    """Proven if a crafted username logs in without a valid password."""\n'
        "    payload = \"' OR '1'='1' -- \"\n"
        '    resp = client.post("/api/login", json={"username": payload, "password": "wrong"})\n'
        '    assert resp.status_code == 401, "injection bypassed authentication"\n'),
     "A crafted username must not bypass the login password check."),
    "idor": (_proof(
        'def test_user_cannot_read_another_users_note(client, alice_token):\n'
        '    """Proven if Alice can read a note she does not own."""\n'
        '    r = client.get("/api/notes/2", headers={"Authorization": f"Bearer {alice_token}"})\n'
        '    assert r.status_code in (403, 404), "IDOR: read another user\'s note"\n'),
     "A user must not be able to read another user's note by id."),
    "missing-auth": (_proof(
        'def test_admin_endpoint_requires_auth(client):\n'
        '    """Proven if the admin user list is reachable with no token."""\n'
        '    r = client.get("/api/admin/users")\n'
        '    assert r.status_code in (401, 403), "admin list exposed without auth"\n'),
     "The admin user list must reject unauthenticated requests."),
    "hardcoded-secret": (_proof(
        'import app\n\n'
        'def test_secret_is_not_hardcoded():\n'
        '    """Proven if the signing key is the constant baked into source."""\n'
        '    assert app.SECRET_KEY != "notevault-dev-secret-2026", "hardcoded signing secret"\n'),
     "The signing key must not be the constant committed to source."),
    "cors": (_proof(
        'def test_cors_does_not_reflect_untrusted_origin(client, alice_token):\n'
        '    """Proven if an untrusted Origin is echoed back with credentials allowed."""\n'
        '    r = client.get("/api/notes", headers={"Authorization": f"Bearer {alice_token}",\n'
        '                                           "Origin": "https://evil.example"})\n'
        '    acao = r.headers.get("Access-Control-Allow-Origin")\n'
        '    assert acao != "https://evil.example", "CORS reflects any origin"\n'),
     "An untrusted Origin must not be reflected in CORS headers."),
}

# Each patch is a pure transform of the CURRENT source, so fixes are cumulative.
def _p_sqli(s):
    old = ('        query = (\n'
           '            f"SELECT * FROM users WHERE username = \'{username}\' "\n'
           '            f"AND password = \'{_hash(password)}\'"\n'
           '        )\n'
           '        user = db().execute(query).fetchone()\n')
    new = ('        user = db().execute(\n'
           '            "SELECT * FROM users WHERE username = ? AND password = ?",\n'
           '            (username, _hash(password)),\n'
           '        ).fetchone()\n')
    return s.replace(old, new), "Parameterize the login query so input can't change the SQL."

def _p_idor(s):
    old = ('        if row is None:\n'
           '            return jsonify(error="not found"), 404\n'
           '        return jsonify(dict(row))\n')
    new = ('        if row is None or row["owner_id"] != user["id"]:\n'
           '            return jsonify(error="not found"), 404\n'
           '        return jsonify({"id": row["id"], "title": row["title"], "body": row["body"]})\n')
    return s.replace(old, new), "Reject notes the caller does not own."

def _p_auth(s):
    old = ('    @app.get("/api/admin/users")\n'
           '    def admin_users():\n'
           '        rows = db().execute')
    new = ('    @app.get("/api/admin/users")\n'
           '    def admin_users():\n'
           '        user = current_user()\n'
           '        if user is None:\n'
           '            return jsonify(error="unauthorized"), 401\n'
           '        if not user["is_admin"]:\n'
           '            return jsonify(error="forbidden"), 403\n'
           '        rows = db().execute')
    return s.replace(old, new), "Require a valid admin token on the admin endpoint."

def _p_secret(s):
    old = ('# TODO: move to env before launch\n'
           'SECRET_KEY = "notevault-dev-secret-2026"\n')
    new = ('import os\n'
           'import secrets as _secrets\n\n'
           '# Read the signing key from the environment; use an ephemeral dev-only\n'
           '# key when it is unset so nothing secret lives in source.\n'
           'SECRET_KEY = os.environ.get("NOTEVAULT_SECRET_KEY") or _secrets.token_urlsafe(32)\n')
    return s.replace(old, new), "Read the signing key from the environment instead of source."

def _p_cors(s):
    old = ('    @app.after_request\n'
           '    def cors(resp):\n'
           '        # Make the frontend work from anywhere\n'
           '        origin = request.headers.get("Origin")\n'
           '        if origin:\n'
           '            resp.headers["Access-Control-Allow-Origin"] = origin\n'
           '            resp.headers["Access-Control-Allow-Credentials"] = "true"\n'
           '        return resp\n')
    new = ('    allowed_origins = {"http://localhost:3000", "http://127.0.0.1:3000"}\n\n'
           '    @app.after_request\n'
           '    def cors(resp):\n'
           '        origin = request.headers.get("Origin")\n'
           '        if origin in allowed_origins:\n'
           '            resp.headers["Access-Control-Allow-Origin"] = origin\n'
           '            resp.headers["Access-Control-Allow-Credentials"] = "true"\n'
           '            resp.headers["Vary"] = "Origin"\n'
           '        return resp\n')
    return s.replace(old, new), "Reflect only allow-listed origins."

PATCHES = {"sqli": _p_sqli, "idor": _p_idor, "missing-auth": _p_auth,
           "hardcoded-secret": _p_secret, "cors": _p_cors}


class ScriptedClient:
    """Implements the TokenFactoryClient interface with canned, content-matched replies."""
    def __init__(self, bus):
        self.bus = bus
        self.usage = {r: Usage() for r in settings.models}

    def _cat(self, text):
        # Match only the "Finding: <title> ..." line, never the embedded source.
        first = text.splitlines()[0].lower() if text else ""
        keywords = {
            "sqli": "sql injection",
            "idor": "idor",
            "missing-auth": "authentication",
            "hardcoded-secret": "hardcoded",
            "cors": "cors",
        }
        for cat, kw in keywords.items():
            if kw in first:
                return cat
        raise RuntimeError(f"could not categorize finding line: {first!r}")

    async def chat(self, role, purpose, system, user, max_tokens=4096, temperature=0.2):
        await asyncio.sleep(0.15)  # feel like a real call
        out = ""
        if purpose == "triage":
            out = json.dumps(TRIAGE)
        elif purpose.startswith("analyze"):
            out = json.dumps(ANALYSIS)
        elif purpose.startswith("prove"):
            cat = self._cat(user)
            code, claim = PROOFS[cat]
            out = json.dumps({"test_code": code, "claim": claim})
        elif purpose.startswith("patch"):
            cat = self._cat(user)
            m = re.search(r"Current source of .*?:\n(.*)", user, re.DOTALL)
            src = m.group(1)
            new, summary = PATCHES[cat](src)
            if new == src:
                raise RuntimeError(f"patch transform for {cat} matched nothing")
            out = json.dumps({"files": [{"path": "app.py", "content": new}], "summary": summary})
        # fake usage numbers so the cost panel has something real-ish to show
        tin = len(system + user) // 4
        tout = len(out) // 4
        spec = settings.models[role]
        u = self.usage[role]
        u.calls += 1; u.input_tokens += tin; u.output_tokens += tout
        cost = tin / 1e6 * spec.input_per_m + tout / 1e6 * spec.output_per_m
        u.cost += cost
        lat = {"nano": 420, "super": 1400, "ultra": 5200}[role] + tout % 500
        self.bus.emit("llm.call", role=role, model=spec.model_id, purpose=purpose,
                      input_tokens=tin, output_tokens=tout, cost=round(cost, 6), latency_ms=lat)
        return out

    async def aclose(self):
        pass


async def main():
    out_dir = ROOT / "runs" / "demo"
    out_dir.mkdir(parents=True, exist_ok=True)
    bus = EventBus(record_to=out_dir / "events.jsonl")
    client = ScriptedClient(bus)
    agent = ExhibitAgent(client, bus)
    findings = await agent.scan(local_path=str(TARGET))
    bus.close()

    verified = [f for f in findings if f.stage == "verified"]
    print("\n=== demo run complete ===")
    for f in findings:
        print(f"  {f.id} [{f.stage:9}] {f.title}")
    for f in verified:
        (out_dir / f"{f.id}.patch").write_text(f.diff)
    report = {"source": "demo_target (NoteVault)",
              "findings": [f.to_dict() for f in findings],
              "usage": {r: vars(u) for r, u in client.usage.items()}}
    (out_dir / "report.json").write_text(json.dumps(report, indent=2))
    print(f"\n{len(verified)}/{len(findings)} findings proven and fixed.")
    print(f"Recorded: {out_dir / 'events.jsonl'}")
    if len(verified) != 5:
        print("!! expected 5 verified findings")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
