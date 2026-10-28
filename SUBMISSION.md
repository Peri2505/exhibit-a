# Devpost submission — copy/paste pack

Everything you need to fill in the Devpost form. Edit anything in **[brackets]**.

---

## Project name
**Exhibit A — the security agent that proves every bug before it fixes it**

## Elevator pitch (one line)
A coding agent that writes a failing test to *prove* each security bug is real, fixes it, and re-runs the tests to verify — so it reports zero unproven findings.

## Track
Coding and Agentic Engineering

---

## Inspiration
So much code today is written by AI and shipped by people who can't fully review it, and the scanners meant to catch the security holes drown you in false positives. A warning you can't trust gets ignored. I wanted the opposite: an agent that has to *prove* a bug is real — with a test that actually fails — before it's allowed to tell you about it.

## What it does
Exhibit A scans a repo and, for every suspected vulnerability, builds a case:
1. Writes a unit test asserting the **secure** behavior, which **fails** on the current code — the evidence.
2. Runs it in an isolated sandbox to confirm it fails.
3. Writes the smallest patch, then re-runs the proof **and** the project's existing tests until the proof is green and nothing else broke.
4. Hands you a diff and a plain-English case file ready for a pull request.

If it can't produce a reliable failing test, it **drops** the finding instead of reporting it. The UI shows each finding as a case card moving Suspected → Proven → Patched → Fixed, with the red failing test turning green, plus a live cost/latency panel for each model.

## How we built it
- **NVIDIA Nemotron on Nebius Token Factory**, routed by task:
  - **Nano** (`nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`) triages every file by risk.
  - **Super** (`nvidia/nemotron-3-super-120b-a12b`) turns risky files into concrete, testable findings.
  - **Ultra** (`nvidia/Nemotron-3-Ultra-550B-A55B`) writes the proof test and the patch.
- A **sandbox** runs pytest against a copy of the target — Docker with no network and dropped capabilities, or a scrubbed local subprocess.
- **FastAPI + Server-Sent Events** stream the agent's reasoning to a **case-file UI** (vanilla JS/CSS).
- A bundled intentionally-vulnerable Flask app (**NoteVault**) is the safe demo target.

## Challenges we ran into
Getting a model to write a test that fails for the *right* reason (a real security assertion, not an import error) took careful prompting and an automatic retry that feeds the pytest output back to the model. Keeping fixes from breaking the existing suite meant verifying every patch against the full test run and reverting on regressions.

## Accomplishments we're proud of
Every reported finding is backed by a test that executed. The whole loop — triage, analysis, proof, sandboxed run, patch, re-verification — runs end to end and fixes all five planted bugs in the demo for a few cents.

## What we learned
Execution-grounded feedback is what makes an agent trustworthy. Routing cheap models for breadth and a big model for the hard steps keeps cost sane without losing quality.

## What's next
Auto-opening pull requests, more languages (JS/TS, Go), and a GitHub Action that runs Exhibit A on every PR so only *proven* issues ever reach a human.

## Built with
`python` · `nvidia-nemotron` · `nebius-token-factory` · `fastapi` · `flask` · `pytest` · `docker` · `server-sent-events`

---

## Links to paste into the form
- **Repository:** https://github.com/Peri2505/exhibit-a  *(make it public, MIT license is already at the repo root)*
- **Demo video (YouTube, ≤3 min, public):** **[paste link]**
- **Working demo / test build:** the case-file UI — run `python -m exhibit_a serve` and click **Replay demo** (no API key needed).
  *If a hosted URL is required, note in the field that it runs locally in one command; optionally deploy per DEPLOY.md.*

## Required checklist (from the rules)
- [x] Runs on Nebius Token Factory (all inference) — ✔
- [x] Uses at least one NVIDIA open source model (Nemotron Nano/Super/Ultra) — ✔
- [x] Public repo with an OSS license visible at the top (MIT) — ✔
- [x] README with setup + how Nemotron/Token Factory are used — ✔
- [x] Feedback on Token Factory / NVIDIA tools — see FEEDBACK.md — ✔
- [ ] 3-minute demo video on YouTube (public) — **record & paste link**
- [ ] Working demo URL — **the UI (local one-command) or your deployment**
- [x] Explanation that the project was built during the submission period — in README — ✔
