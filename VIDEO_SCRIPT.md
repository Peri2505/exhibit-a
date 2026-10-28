# 3-minute demo video — shot list & script

Record at 1440×900+. Use **Replay demo** so timing is predictable and no key is needed.
Keep total under 3:00. Rough word budget per section is in the script.

---

### 0:00–0:20 — The hook (talking head or voiceover over the empty UI)
> "This is a notes app that was vibe-coded in an afternoon. It has five security holes.
> Most scanners would bury those in a hundred warnings you'd never trust.
> Exhibit A does something different — it **proves** each bug with a failing test before it fixes it.
> Watch."

*Action:* UI open, empty evidence locker on screen. Click **Replay demo** at ~0:18.

### 0:20–1:40 — The run (screen capture, let it play)
Narrate as the cards appear:
> "Nano triages every file for risk. Super turns the risky code into concrete findings —
> SQL injection, broken access control, a missing auth check, a hardcoded secret, open CORS.
> Then Ultra writes a test that asserts the *secure* behavior."

*Action:* Point at a card as it hits **Proven** — the red strip reads *PROOF FAILS ON VULNERABLE CODE.*
> "Red means the proof failed on the current code — that's the evidence the bug is real.
> If a test can't fail, the finding gets dropped. No unproven warnings."

*Action:* Cards flip to **Fixed**, strips turn green.
> "Ultra writes the smallest patch, re-runs the proof **and** the existing test suite,
> and only then marks it Fixed. Red to green — proven, then verified."

### 1:40–2:20 — The evidence (click one card open)
*Action:* Open the SQL-injection (or IDOR) case in the drawer. Scroll through: the proof test, then the diff.
> "Here's the actual exhibit — the failing test. And here's the fix, as a clean diff you can
> drop straight into a pull request. Every finding comes with both."

### 2:20–2:45 — The engine (point at the model panel)
> "All the reasoning runs on NVIDIA Nemotron, served on Nebius Token Factory — Nano for breadth,
> Super for analysis, Ultra for the hard steps. One endpoint, routed by task. The whole scan
> cost a few cents, shown live right here."

*Action:* Point at the cost/latency panel and the total.

### 2:45–3:00 — Close
> "Scanners give you warnings. Exhibit A gives you evidence.
> Don't trust the warning — trust the exhibit."

*Action:* End on the full board, 5/5 Fixed.

---

## Tips
- If you want a live (non-replay) run on camera, do a dry run first — model latency varies.
- Capture at 30fps; the red→green transition is the money shot, don't rush past it.
- Upload to YouTube as **Public** (Unlisted is not accepted by the rules), paste the link into Devpost and SUBMISSION.md.
