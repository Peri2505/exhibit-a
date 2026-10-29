# 3-minute demo video — record-ready script

**Record a LIVE run, not the "Replay demo" button.** A live scan runs at a natural ~2-minute
pace (perfect to fill the video) and it's authentic — the models are really working. The
replay button plays back too fast to narrate over.

## Setup (once, before you hit record)
In your project folder, with your `.env` key in place:
```bash
source venv/bin/activate
python -m exhibit_a serve
```
Open **http://127.0.0.1:8000** in your browser. Have the repo page
(github.com/Peri2505/exhibit-a) open in a second tab to show at the end.

## How to record on a Mac
- **Cmd + Shift + 5** → "Record Selected Portion" (or Entire Screen) → Record.
- Speak into your Mac mic as it runs. Keep it under 3:00.
- Stop with the menu-bar ■ icon. The file saves to your Desktop.
- Upload to **YouTube as Public** (Unlisted is not accepted), paste the link into Devpost.

---

## The script (what to do + what to say)

### 0:00–0:20 — Hook
*(UI open, empty "evidence locker" on screen)*
> "This is a notes app with a handful of security holes — the kind AI writes and ships every
> day. Most scanners would bury those in a hundred warnings you'd never trust. Exhibit A does
> the opposite: it **proves** each bug with a failing test before it fixes it. Watch."

*Action:* type `./demo_target` in the box, click **Open case**.

### 0:20–1:50 — The live run (let it play, narrate)
> "First, **Nano** triages the code for risk on Nebius Token Factory. Then **Super** turns the
> risky file into concrete findings. And **Ultra** writes a unit test that asserts the *secure*
> behavior."

*Action:* point to a card as it hits **Proven** — red strip: *PROOF FAILS ON VULNERABLE CODE.*
> "Red means the test failed on the current code — that's the evidence the bug is real. If a
> test can't fail, the finding gets dropped. No unproven warnings."

*Action:* cards flip to **Fixed**, strips turn green.
> "Then Ultra writes the smallest patch, re-runs the proof **and** the existing test suite, and
> only marks it Fixed when both are green. Red to green — proven, then verified."

*(If it finds the unsalted-password bug or drops the SQL one, call it out — it's a great moment:)*
> "Notice it even flagged a vulnerability I never planted — unsalted password hashing — and it
> **refused** to auto-claim the one it couldn't prove. That honesty is the whole point."

### 1:50–2:25 — The evidence (click one card open)
*Action:* open a verified case in the drawer; scroll to the proof test, then the diff.
> "Here's the actual exhibit — the failing test. And here's the fix as a clean diff, ready for
> a pull request. Every finding ships with both."

### 2:25–2:45 — The engine (point at the model panel + cost)
> "All the reasoning runs on NVIDIA Nemotron, served on Nebius Token Factory — Nano for breadth,
> Super for analysis, Ultra for the hard steps. One endpoint, routed by task. This whole scan
> cost about **thirteen cents**, shown live right here."

### 2:45–3:00 — Close
*(show the full board, then the GitHub repo tab)*
> "Scanners give you warnings. Exhibit A gives you evidence. Don't trust the warning — trust
> the exhibit."

---

## Tips
- Do one practice run first so you know the pacing and what the models find (it varies slightly).
- The **red→green flip** is the money shot — don't rush past it.
- If you're nervous narrating live, record the screen silently, then add a voiceover after.
- Keep the terminal visible somewhere too — it reinforces that this is a real run on Token Factory.
