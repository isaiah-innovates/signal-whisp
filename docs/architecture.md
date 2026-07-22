# Architecture

## Pipeline stages

1. **Ingest** — pull raw posts from each configured source, normalize into a
   shared record shape, store immutably as ground truth (raw text should
   never be overwritten by downstream processing).
2. **Sense (extraction)** — an LLM agent reads one normalized post and
   decides: is this a genuine, recurring cybersecurity pain point? If so,
   extract it into structured fields. Spec: `evals/signal-extraction.md`.
3. **Discover (cluster & score)** — group related signals across posts,
   sources, and days into candidate "opportunities," then score each against
   an explicit rubric. Spec: `evals/opportunity-scoring.md`.
4. **Decide (classify)** — take a scored opportunity and classify it into an
   action bucket a PM would actually act on: pursue, watch, or discard.
   Spec: `evals/decide-classification.md`. LLM-as-judge
   (`agents/decide_agent.py`), not a formula — hand-labeling showed no
   clean score-threshold rule separates the three buckets. Eval-passing
   at 19/21 (90.5%).
5. **Deliver** — ranked daily digest + an on-demand query interface over
   stored history.

## Falkster PM Operating System mapping

The full agent fleet (falkster.com/handbook/ai-agent-army) assumes enterprise
data (Jira, Slack, Zendesk, Salesforce, Gong) that isn't available here. This
project implements only the stages reachable from public data, and treats the
rest as an honest, stated roadmap rather than pretending they're built.

| Stage | In this project | Status |
|---|---|---|
| Sense | Ingestion + pain-signal extraction agent | v1 |
| Discover | Clustering + opportunity scoring agent | v1 |
| Decide | Pursue/watch/discard classification agent | v1, eval-passing (19/21) |
| Build / Ship / Measure / Amplify | Would need real product data this project doesn't have | roadmap only |

## Shared post record

Every source normalizes into the same shape so the Sense-stage agent is
source-agnostic. Suggested fields (adjust as needed, but keep it one shared
shape used by every source client):

- `id` — source-native identifier
- `source` — e.g. `'stackexchange'`, `'hackernews'`, `'reddit'`
- `subforum` — e.g. `'security.stackexchange.com'`, `'hackernews'`, `'r/msp'`
- `title`
- `body` — plain text, HTML stripped where the source returns HTML
- `url`, `permalink`
- `score` — source-native vote/point count
- `num_replies` — answers or comments, source-appropriate
- `created_utc`
- `top_replies` — list of plain-text excerpts (top answers/comments), used as
  corroboration evidence during extraction

## Repo structure

```
/docs/                          # this file, data-sources.md
/evals/
  signal-extraction.md          # Eval Set 1 — spec for the Sense agent
  opportunity-scoring.md        # Eval Set 2 — spec for the Discover agent
  decide-classification.md      # Eval Set 3 — spec for the Decide agent
  run_evals.py                  # scores agents against their eval file
  run_decide_eval.py            # scores decide_agent.py against Eval Set 3
/sources/
  stackexchange_client.py       # primary live source
  hn_client.py                  # secondary live source
  reddit_client.py              # dormant, pending official API approval
  models.py                     # shared post record
/agents/
  sense_agent.py                # extraction — named to match the 7-stage model
  discover_agent.py             # clustering + scoring
  decide_agent.py               # pursue/watch/discard classification
/data/runs/YYYY-MM-DD/          # raw posts, signals, scored clusters (JSONL) — gitignored
/reports/                       # generated daily digests — gitignored, not committed
/web/                           # query API + minimal dashboard
CLAUDE.md                       # persistent project brief and operating rules
README.md                       # public-facing: problem, architecture, eval
                                 # scores, honest Falkster-stage roadmap
```

## Deployment target — decided against, 2026-07-22

Railway deployment (managed Postgres, a scheduled worker running the
pipeline, and a hosted web service for the dashboard) was considered once
all three agent stages became eval-passing, and rejected on cost grounds:
measured actual token usage from a real pipeline run put ongoing LLM spend
at roughly $95-135/month on a daily cadence or $26-42/month weekly, plus a
roughly flat ~$15-25/month for Railway hosting regardless of cadence
(estimate — Railway pricing itself wasn't verified live). Not worth it for
this project's scale.

**The project's final form runs locally**: `agents/run_pipeline.py` for the
pipeline (run by hand, or a local cron/launchd job if a schedule is
wanted), local JSONL storage under `data/runs/` as the permanent store (not
a stopgap awaiting Postgres), and `web/app.py` run locally
(`uvicorn web.app:app --reload`) for the dashboard.
