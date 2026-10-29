# Feedback — building Exhibit A on Nebius Token Factory + NVIDIA Nemotron

## Real run on Token Factory (measured)
Full scan of the bundled demo target (`demo_target`, a single Flask file), with all
inference running on Nebius Token Factory using NVIDIA Nemotron:

- **Cost: $0.1275** for the entire scan. Nano triage was effectively free; Super handled
  analysis; Ultra did the proof-test and patch reasoning (most of the spend).
- **Latency:** ~2 minutes end to end — Ultra calls ran ~4–18s each, Nano/Super were quick.
- **Result:** 6 issues surfaced — 5 proven with a failing test; **4 auto-fixed and verified**
  (IDOR, missing admin auth, hardcoded secret, permissive CORS); 1 proven but left for a
  manual fix (unsalted SHA‑256 password hashing — a vulnerability we had **not** planted,
  so the models found it on their own); and 1 dropped because no reliable failing proof
  could be produced (a SQL-injection candidate).
- The dropped and manual-fix cases are the **"proof before patch" discipline working as
  intended**: nothing is reported unless a test demonstrates it, and nothing is claimed
  fixed unless the proof and the existing test suite both pass.

## What worked well
- **One endpoint, three models.** Token Factory's OpenAI-compatible `/v1/chat/completions`
  meant the whole Nano/Super/Ultra routing was just a config table — no three separate
  SDKs. Swapping tiers per task took one argument.
- **The tier spread is exactly right for an agent.** Nano is cheap enough to run across a
  whole repo for triage, and Ultra is strong enough to write a correct failing test *and*
  a patch that passes it. Being able to pick per step kept a full small-repo scan to a few cents.
- **Structured output held up.** Asking each tier for strict JSON (findings, test code,
  patches) was reliable enough to build a pipeline on, with a tolerant parser for the edges.

## What tripped us up (and suggestions)
- **Model-ID casing/prefix is easy to get wrong.** The full `nvidia/...` id must match the
  catalog exactly, and casing varies between models. We added `python -m exhibit_a models`
  to diff our configured IDs against what the account actually serves. A canonical,
  copy-pasteable list per account in the console would save newcomers a 401/"model not found" loop.
- **Reasoning traces in the content.** Reasoning-tuned Nemotron variants can emit `<think>…</think>`
  before the answer; we strip it before JSON parsing. A documented flag or a separate
  `reasoning` field in the response would be cleaner than parsing it out.
- **Rate-limit feedback.** Clear, machine-readable retry-after headers on 429s would let
  agents back off precisely instead of using a fixed schedule.
- **Docs discoverability.** The single most useful thing for a first-time builder would be a
  one-page "agent quickstart": the base URL, one working `curl`, and the exact IDs of the
  current Nemotron tiers with their context windows and prices.

## Would we build on it again?
Yes. For an agent that fans out cheap calls and reserves a big model for the hard steps,
a single endpoint serving the whole Nemotron range is the right shape.
