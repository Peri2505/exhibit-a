<div align="center">

# ⚖️ Exhibit A

### A security agent that proves every bug before it fixes it.

*If it can't prove a bug with a failing test, it doesn't report it.*

Nebius × NVIDIA Global AI Hackathon · Coding & Agentic Engineering track
Built with **NVIDIA Nemotron** on **Nebius Token Factory**

![CI](https://github.com/Peri2505/exhibit-a/actions/workflows/ci.yml/badge.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-f6a821.svg)
![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)

🎥 **[Watch the 2-minute demo](https://youtu.be/YF88f0MTJ0Y)**

</div>

---

## Why I built this

A lot of code now gets written by AI and shipped by people who don't have time to read all of it, and it ships with the same handful of security holes every time: missing auth checks, broken access control, hardcoded secrets, injectable queries, open CORS.

The tools that are supposed to catch this tend to make it worse. A scanner throws a few hundred warnings, most of them false alarms, and after a while you stop reading any of them. A warning you can't trust is just noise.

So I tried the opposite idea: what if the tool had to *prove* a bug was real before it was allowed to tell you about it?

## How it works

Exhibit A treats each suspected vulnerability like a case it has to make. For every finding it:

1. **Writes a test that proves the bug is real** — for example, "an unauthenticated request to `/api/admin/users` comes back `200` when it should be `401`." That failing test is the evidence — the "Exhibit A."
2. **Runs that test in an isolated sandbox** and checks that it really does fail on the current code.
3. **Writes the smallest patch it can**, then re-runs the proof *and* the project's existing tests until the proof passes and nothing else broke.
4. **Hands back a diff and a short plain-English case file** you can drop straight into a pull request.

If it can't come up with a test that reliably fails, it drops the finding instead of reporting it. That one rule — prove it before you patch it — is really the whole point. You end up with no unproven findings, and every fix checked by actually running code.

![Exhibit A case board](assets/ui-overview.png)

---

## What it's good at, and where it isn't

**What works**
- **It's grounded in execution, not guesses.** Every reported bug has a test that ran and failed on the real code, and every fix is re-checked against that test and the existing suite before it's marked Fixed.
- **It spends money where it matters.** Three Nemotron tiers on Token Factory — Nano for breadth, Super for analysis, Ultra only for the hard reasoning. A full scan of the demo app came to about **$0.13** on a real run.
- **It's an actual product, not a script dump.** The case-file UI shows each finding move Suspected → Proven → Fixed, the failing test turning green, the generated test, and the diff, with a live cost/latency panel for the models.
- **It handles code it's never seen.** On a real run it flagged a bug I hadn't planted (unsalted password hashing) and dropped one it couldn't prove — so the discipline isn't just a scripted happy path.

**What it doesn't do (yet)**
- It only reads **Python** right now. JS/TS and Go are the obvious next step.
- **Docker is the real isolation boundary.** There's a local fallback that's network-free, has a scrubbed environment, and caps CPU/memory/file size, but I'd only trust it for development — a real deployment should use the Docker sandbox.
- It runs a test per finding, so a huge repo would need batching and caching. That's a deliberate trade — it spends compute to earn trust.

---

## I ran it on a real repo, not just my demo

To check it wasn't just working on my own toy app, I pointed it at **[videvelopers/Vulnerable-Flask-App](https://github.com/videvelopers/Vulnerable-Flask-App)**, an OWASP-referenced vulnerable Flask app it had never seen:

- It **proved and auto-fixed two real bugs** — a **SQL injection** in `/user/<name>` and a **server-side template injection** in `/hello` — each with a test that failed first and passed after the patch, without breaking the rest of the app.
- It **dropped the ones it couldn't prove** — two pickle-deserialization leads and a command-injection guess — rather than reporting them.
- The whole scan cost about **$0.13**.

That's the behavior I was after: on code it didn't write, it only reported what it could actually demonstrate.

---

## Which Nemotron model does what

Each step goes to the cheapest Nemotron model that can handle it, all served through one OpenAI-compatible Token Factory endpoint. The UI shows live cost, tokens, and latency per tier.

| Tier | Model (Token Factory ID) | What it does | Why this one |
|---|---|---|---|
| **Nano** | `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` | Triage every file by risk | Fast and nearly free, so it can read the whole repo |
| **Super** | `nvidia/nemotron-3-super-120b-a12b` | Turn risky files into concrete, testable findings | Good analysis for a fraction of Ultra's price |
| **Ultra** | `nvidia/Nemotron-3-Ultra-550b-a55b` | Write the proof test, then the patch | The hard reasoning, where getting it right matters most |

> Ultra only gets called for the two hardest steps, which is why a small scan runs a few cents. Check the exact IDs your account serves with `python -m exhibit_a models`.

---

## Architecture

```
                         ┌─────────────────────────────────────────────┐
  repo / local dir  ───▶ │  CLONE → copy into an isolated workdir        │
                         └─────────────────────────────────────────────┘
                                          │
        NANO   ─────────────▶   1. TRIAGE   rank files by security risk
        SUPER  ─────────────▶   2. ANALYZE  risky file → concrete findings
                                          │   (each finding is just a hypothesis)
        ULTRA  ─────────────▶   3. PROVE    write a test asserting secure behaviour
                                          │
                    ┌─────────────────────▼─────────────────────┐
                    │  SANDBOX: run pytest (Docker, no network,  │
                    │  dropped caps / mem+cpu caps; local        │
                    │  subprocess fallback with scrubbed env)    │
                    └─────────────────────┬─────────────────────┘
                              test FAILS? ─┤─ no ─▶  DROP (unproven, never reported)
                                     yes   │
                                           ▼  finding is now PROVEN
        ULTRA  ─────────────▶   4. PATCH   smallest fix; re-run proof + full suite
                                           ▼
                              proof green + suite green ─▶  VERIFIED  (diff + case file)
```

Everything streams to the UI over Server-Sent Events, so you watch the case get built in real time.

### A note on safety
Exhibit A is a defensive tool meant to run on code you own. It doesn't attack anything live — tests run against a local copy in a sandbox with no network. The proof payloads are minimal and only touch the local code path (a classic auth-bypass check, an id that isn't yours, an untrusted `Origin` header). It finds and fixes; it doesn't weaponize.

---

## Quickstart

```bash
git clone https://github.com/Peri2505/exhibit-a
cd exhibit-a
pip install -r requirements.txt

cp .env.example .env            # add your NEBIUS_API_KEY
python -m exhibit_a models      # confirm the Nemotron model IDs your account serves

# recommended: build the sandbox image for isolated test runs
docker build -t exhibit-a-sandbox:latest -f sandbox.Dockerfile .

# open the case-file UI
python -m exhibit_a serve       # → http://127.0.0.1:8000
```

From there, paste a path or a public GitHub URL and click **Open case**, or hit **Replay demo** to watch a recorded run against the bundled app (no API key needed).

Or from the command line:

```bash
python -m exhibit_a scan --local ./demo_target          # scan the bundled target
python -m exhibit_a scan --repo https://github.com/you/project
```

### The bundled target
`demo_target/` is **NoteVault**, a tiny Flask API I made intentionally vulnerable (five planted bugs). It's the safe thing to try first. A recorded run of all five getting proven and fixed lives in `runs/demo/`, and that's what the **Replay demo** button plays back.

---

## What runs where (Nebius & NVIDIA)

- **NVIDIA Nemotron** (Nano / Super / Ultra) does all the reasoning — triage, analysis, writing the proof tests, and writing the patches.
- **Nebius Token Factory** serves all three models behind one OpenAI-compatible endpoint (`/v1/chat/completions`), which is the reason the three-tier routing is a few lines of config instead of three separate integrations.
- The sandbox and UI are plain Python and aren't tied to any host, so you can run the agent wherever and point it at Token Factory.

See [`FEEDBACK.md`](FEEDBACK.md) for my honest notes on building with Token Factory and Nemotron — what went smoothly and what didn't.

## About this project
I built Exhibit A from scratch for this hackathon — the agent, the three-tier Nemotron routing, the sandbox, the case-file UI, and the bundled vulnerable app are all new, written during the submission period.

## License
[MIT](LICENSE)
