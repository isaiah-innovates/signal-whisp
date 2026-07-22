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
   an explicit rubric. Spec: `evals/opportunity-scoring.md` (to be written
   after Sense is passing).
4. **Deliver** — ranked daily digest + an on-demand query interface over
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
| Decide | Ranked digest is a decision input, not an automated decision | partial |
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
  run_evals.py                  # scores agents against their eval file
/sources/
  stackexchange_client.py       # primary live source
  hn_client.py                  # secondary live source
  reddit_client.py              # dormant, pending official API approval
  models.py                     # shared post record
/agents/
  sense_agent.py                # extraction — named to match the 7-stage model
  discover_agent.py             # clustering + scoring
/data/runs/YYYY-MM-DD/          # raw posts, signals, scored clusters (JSONL) — gitignored
/reports/                       # generated daily digests — gitignored, not committed
/web/                           # query API + minimal dashboard
CLAUDE.md                       # persistent project brief and operating rules
README.md                       # public-facing: problem, architecture, eval
                                 # scores, honest Falkster-stage roadmap
```

## Deployment target (later — after both agent stages pass their evals)

Railway: managed Postgres (raw posts, extracted signals, clusters, scores,
eval run history), a scheduled worker service running ingest → extract →
cluster → score daily, and a lightweight web service for the query interface
and digest viewing. Secrets as Railway environment variables, never committed.
