# Signal — Cybersecurity Opportunity-Sensing Agent

## Mission
A small, rigorously-evaluated pipeline that turns public cybersecurity-practitioner
complaints into scored, ranked market-opportunity candidates for a small team.
Built as a scoped-down, extensible slice of the Falkster 7-stage PM Operating
System (falkster.com/handbook/ai-agent-army) — Sense, Discover, and (as of
2026-07-22) Decide stages. See `docs/architecture.md` for the full pipeline
design.

This is a portfolio project. The centerpiece is not the data pipeline — it's a
genuinely rigorous, two-stage eval framework built *before* the pipeline logic,
in the "eval is the spec" discipline (falkster.com/handbook/the-eval-is-the-spec).

## Non-negotiable principles

1. **The eval is the spec.** Nothing gets built until the eval file for that
   stage exists with real, hand-labeled ground truth. Do not write extraction
   or scoring logic first and backfill an eval file — read the relevant
   `evals/*.md` file before writing or changing any agent logic, and if it
   doesn't exist yet or is still full of placeholder/synthetic rows, stop and
   say so rather than proceeding on invented data.
2. **Never fabricate eval labels.** If a human hasn't labeled a row, it isn't
   ground truth. It's fine to propose candidate rows pulled from a live source
   for the human to review and correct — it is not fine to write "real" labeled
   rows yourself and treat them as ground truth.
3. **Stage discipline.** Don't start Discover-stage (clustering/scoring) work
   until Sense-stage (extraction) is passing its eval bar defined in
   `evals/signal-extraction.md`. Don't start Decide-stage work until
   `evals/decide-classification.md` has real hand-labeled rows (not the
   PENDING placeholders it currently has). Don't build Railway deployment
   until Decide is eval-passing — per user decision on 2026-07-22, one
   deployment after Decide lands beats deploying now and redeploying later.
4. **Keep prompts traceable to their eval file.** If an agent's prompt changes,
   the corresponding eval file's labeling criteria should be updated first (or
   the change explained against the existing criteria), then the eval re-run
   to check for regressions.
5. **Ask before assuming on ambiguous specs.** `docs/data-sources.md` and the
   eval files are the source of truth. Where they're silent on something
   material (e.g. exact rate-limit backoff behavior), ask rather than guess
   silently — but don't ask about things already answered in these docs.

## Data sources — read `docs/data-sources.md` before writing any ingestion code
Reddit is currently gated (manual approval process, real rejection risk) and
Devvit doesn't fit this use case (apps must be installed per-subreddit by that
subreddit's moderators). Primary/secondary live sources are Stack Exchange and
Hacker News; Reddit ingestion is a dormant/future client; Arctic Shift is a
separate historical-backfill path, not a live daily source. Full technical
specs (auth, endpoints, rate limits, field mapping) are in `docs/data-sources.md`.

## Stack conventions
- Python 3.11+, type hints throughout, dataclasses for structured records.
- One shared post record shape across all sources (defined in
  `docs/data-sources.md`) so the Sense-stage agent doesn't care which source a
  post came from.
- All secrets via `.env`, never hardcoded, never committed. `.env.example`
  should list every variable a source or agent needs, with a comment on where
  to get it.
- LLM calls: Anthropic SDK, structured output via forced tool use rather than
  prompting for raw JSON.
- Plain `requests` for REST APIs unless a source specifically requires an SDK
  (e.g. PRAW for the dormant Reddit client).
- Local file/JSONL storage is fine through the build-out phase. Postgres
  arrives at the Railway deployment step, not before — don't introduce a
  database dependency earlier than that unless asked.

## Build order
1. Pull real candidate posts from Stack Exchange and Hacker News (per
   `docs/data-sources.md`), hand-label them into `evals/signal-extraction.md`,
   replacing the synthetic placeholder rows.
2. Build the Sense-stage extraction agent against that eval file. Iterate
   until it passes the eval's stated definition of done.
3. Build clustering across posts/sources/days.
4. Hand-label `evals/opportunity-scoring.md` from real extracted output.
5. Build the Discover-stage scoring agent against that eval file.
6. Delivery layer (digest + query interface).
7. Hand-label `evals/decide-classification.md` from real Discover-stage
   output (added 2026-07-22).
8. Build the Decide-stage classification agent (`agents/decide_agent.py`,
   not yet created) against that eval file.
9. Railway deployment (Postgres + scheduled worker + web service) — build
   and deploy once Decide is eval-passing, not before, so there's one
   deployment instead of two.

No dates attached to this — it's sequence, not a schedule.

## What not to do
- Don't scaffold a Devvit app for this — see `docs/data-sources.md` for why
  it doesn't fit.
- Don't add unauthenticated/undocumented Reddit scraping as a workaround.
- Don't introduce a paid third-party data vendor without flagging the cost
  and terms-of-service tradeoffs explicitly and getting a decision first.
