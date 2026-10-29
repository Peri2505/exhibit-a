# Feedback — building on Nebius Token Factory + NVIDIA Nemotron

These are my honest notes from building Exhibit A over the hackathon, mostly aimed at
whoever's reading the feedback form.

## What a real run looked like
A full scan of the bundled demo app (`demo_target`, one Flask file), with every model
call going through Token Factory:

- **Cost: $0.1275** for the whole scan. Nano's triage was basically free; Super did the
  analysis; Ultra ate most of the budget writing the tests and patches.
- **Time: ~2 minutes** end to end. Ultra calls were the slow part (~4–18s each); Nano and
  Super were quick.
- **Result: 6 issues found** — 5 proven with a failing test, 4 of those auto-fixed and
  verified (IDOR, missing admin auth, hardcoded secret, open CORS). One more (unsalted
  SHA-256 password hashing) it proved but couldn't patch cleanly, so it flagged it for me
  instead — and I hadn't even planted that one. One SQL-injection candidate got dropped
  because it couldn't produce a test that reliably failed.
- Those last two are the point, not bugs in my code: nothing gets reported without a test
  behind it, and nothing gets called "fixed" unless the proof and the existing tests both pass.

## What went well
- **One endpoint for three models.** The OpenAI-compatible `/v1/chat/completions` meant my
  whole Nano/Super/Ultra setup was just a config table — no juggling three SDKs. Switching
  tiers for a given step was a single argument.
- **The tier lineup fits an agent really well.** Nano's cheap enough to run over a whole
  repo, and Ultra was actually strong enough to write a failing test *and* a patch that
  passes it. Being able to pick the model per step is what kept a full scan down to cents.
- **Structured output was solid.** I asked each tier for strict JSON (findings, test code,
  diffs) and it held up well enough to build a pipeline on. I still wrote a forgiving parser
  for the odd case, but it rarely needed it.

## What tripped me up (and a few suggestions)
- **The model IDs are easy to get wrong.** The full `nvidia/...` id has to match the catalog
  exactly, and the casing isn't consistent between models — Ultra is lowercase, Super is
  lowercase, Nano is mixed. I burned some time on a "model not found" before I added a
  `python -m exhibit_a models` command to diff my config against what the account serves. A
  copy-pasteable list of current IDs per account in the console would save newcomers that loop.
- **Reasoning text leaking into the answer.** The reasoning-tuned models sometimes put a
  `<think>…</think>` block before the JSON, so I strip it before parsing. A flag to turn that
  off, or a separate field for it in the response, would be cleaner than parsing around it.
- **Rate limits.** Clear retry-after info on 429s would let an agent back off precisely
  instead of guessing with a fixed delay.
- **Docs.** The thing I'd have wanted on day one is a single "agent quickstart" page: the
  base URL, one `curl` that works, and the current Nemotron tiers with their IDs, context
  windows, and prices in one place.

## Would I use it again?
Yes. For this kind of agent — lots of cheap calls, with a big model held back for the hard
steps — one endpoint serving the whole Nemotron range turned out to be exactly the right shape.
