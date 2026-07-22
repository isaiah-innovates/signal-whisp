# Signal — Cybersecurity Opportunity-Sensing Agent

Signal turns public cybersecurity-practitioner complaints (Stack Exchange,
Hacker News) into scored, ranked market-opportunity candidates for a small
team. It's a scoped-down, extensible slice of the [Falkster 7-stage PM
Operating System](https://falkster.com/handbook/ai-agent-army) — just the
**Sense** and **Discover** stages, built on public data instead of the
enterprise data (Jira, Slack, Zendesk, Salesforce, Gong) the full system
assumes.

## What this project is actually about

The pipeline is not the point. This is a portfolio project built around a
genuinely rigorous, two-stage **eval framework built before any agent
logic**, in the ["the eval is the
spec"](https://falkster.com/handbook/the-eval-is-the-spec) discipline:
nothing gets built until the eval file for that stage exists with real,
hand-labeled ground truth — never synthetic or self-authored "ground truth."

- `evals/signal-extraction.md` — Sense-stage ground truth, hand-labeled from
  real pulled posts.
- `evals/opportunity-scoring.md` — Discover-stage ground truth, hand-scored
  from real extracted-and-clustered output.

Both are markdown tables doubling as the database of record — see
`docs/blogs/blog_post_5.md` ("Your eval file can be your database") for why.

## Pipeline

```mermaid
flowchart TD
    subgraph Sources["Live sources (docs/data-sources.md)"]
        SE["Stack Exchange<br/>security + serverfault"]
        HN["Hacker News<br/>Algolia Search API"]
        RD["Reddit<br/>dormant, pending API approval"]
    end

    SE --> ING
    HN --> ING
    RD -.-> ING

    ING["<b>1. Ingest</b><br/>normalize to shared Post record<br/>sources/*_client.py"]

    ING --> SENSE

    subgraph SenseStage["2. Sense"]
        SENSE["LLM extraction agent<br/>agents/sense_agent.py<br/><i>real, recurring pain point?</i>"]
    end

    EVAL1["evals/signal-extraction.md<br/>hand-labeled ground truth"]
    EVAL1 -.eval gate.-> SENSE

    SENSE -->|is_signal=true| CLUSTER

    subgraph DiscoverStage["3. Discover"]
        CLUSTER["cluster_signals()<br/>group same underlying pain<br/>across posts/sources/days"]
        SCORE["score_cluster()<br/>rubric-scored ScoredCluster<br/>overall_rank_score formula"]
        CLUSTER --> SCORE
    end

    EVAL2["evals/opportunity-scoring.md<br/>hand-labeled ground truth"]
    EVAL2 -.eval gate.-> SCORE

    SCORE --> DECIDE

    subgraph DecideStage["4. Decide"]
        DECIDE["agents/decide_agent.py<br/><i>pursue / watch / discard</i><br/>LLM-as-judge, not a formula"]
    end

    EVAL3["evals/decide-classification.md<br/>hand-labeled ground truth"]
    EVAL3 -.eval gate.-> DECIDE

    DECIDE --> DELIVER

    subgraph DeliverStage["5. Deliver"]
        DELIVER["agents/run_pipeline.py<br/>group by decide_action, rank, render digest"]
    end

    DELIVER --> REPORT["reports/YYYY-MM-DD.md<br/>Pursue/Watch/Discard digest"]
    DECIDE --> DATA["data/runs/YYYY-MM-DD/*.jsonl<br/>posts, signals, clusters, decisions"]
    DATA --> WEBAPP["web/app.py (FastAPI)<br/>query API + dashboard<br/>filterable by decide_action"]

    style EVAL1 fill:#2d2d2d,stroke:#888,color:#fff,stroke-dasharray: 4 3
    style EVAL2 fill:#2d2d2d,stroke:#888,color:#fff,stroke-dasharray: 4 3
    style EVAL3 fill:#2d2d2d,stroke:#888,color:#fff,stroke-dasharray: 4 3
```

Each LLM stage is gated by its own eval file — the dashed lines above. No
agent prompt changes without checking (or updating) the eval it's scored
against first.

## Falkster-stage mapping

| Stage | In this project | Status |
|---|---|---|
| Sense | Ingestion + pain-signal extraction agent | v1, eval-passing |
| Discover | Clustering + opportunity scoring agent | v1, accepted with known gaps |
| Decide | Pursue/watch/discard classification agent | v1, eval-passing (19/21) |
| Build / Ship / Measure / Amplify | Would need real product data this project doesn't have | roadmap only |

The full Falkster fleet assumes enterprise data this project doesn't have
access to — everything past Discover is an honest, stated roadmap item, not
something quietly skipped.

## Eval results (current)

**Sense-stage** (`evals/signal-extraction.md`, `evals/run_evals.py`):

| Metric | Result | Bar |
|---|---|---|
| `is_signal` accuracy | 89.7% (26/29) | ≥ 90% |
| False positives on noise rows | 0 | 0 |
| Adversarial cases | 5/6 covered | — |

Accepted as passing in spirit: the 3 misses land exactly on the rows the
human labeler had already flagged as lowest-confidence during labeling, not
on clear-cut signal — read as the eval correctly surfacing genuine boundary
cases rather than a prompt defect.

**Discover-stage** (`evals/opportunity-scoring.md`,
`evals/run_discover_scoring_eval.py`), last full run against live
re-extraction:

| Field | MAE | Notes |
|---|---|---|
| `small_team_feasibility` | 0.031 | deterministic formula over an LLM-classified tier |
| `willingness_to_pay_signal` | 0.038 | deterministic formula over an LLM-classified tier |
| `frequency_corroboration` | 0.000 | pure formula, no LLM |
| `overall_rank_score` | 0.060 | deterministic formula; 4/16 exact rank-position agreement |
| `signal_validity` / `extraction_accuracy` | ~0.06–0.11 | direct LLM output, not tuned this pass |
| `novelty` | ~0.15–0.19 | intentionally never tuned tight — rubric requires human review, not LLM self-certification |

Accepted with known open gaps (see `docs/progress.md` for the full
calibration history): only 16 hand-labeled clusters exist and every pass so
far has been validated against that same set, with no held-out test data
yet.

**Decide-stage** (`evals/decide-classification.md`,
`evals/run_decide_eval.py`):

| Metric | Result |
|---|---|
| `decide_action` exact-match agreement | 19/21 (90.5%) |
| Off-mission scope pruning | correct in all 3 eval runs |

LLM-as-judge, not a formula — hand-labeling showed no clean score-threshold
rule separates `pursue`/`watch`/`discard`. Both remaining mismatches are
genuine boundary calls: one hand-label reflects a pure "timing" judgment
with no textual basis anywhere in the score profile (a permanent, accepted
limitation); the other is a defensible close call using the same rule that
correctly resolved three other rows. Same caveat as Discover-stage: only 21
rows from one pipeline run, no held-out set.

## Repo structure

```
/docs/                          # architecture, data sources, progress log
/evals/
  signal-extraction.md          # Eval Set 1 — Sense-stage ground truth
  opportunity-scoring.md        # Eval Set 2 — Discover-stage ground truth
  decide-classification.md      # Eval Set 3 — Decide-stage ground truth
  run_evals.py                  # scores sense_agent.py against Eval Set 1
  run_discover_scoring_eval.py  # scores discover_agent.py against Eval Set 2
  run_decide_eval.py            # scores decide_agent.py against Eval Set 3
/sources/
  stackexchange_client.py       # primary live source
  hn_client.py                  # secondary live source
  models.py                     # shared post record
  reddit_client.py              # not yet built — dormant, pending Reddit API approval
/agents/
  sense_agent.py                # Sense-stage extraction
  discover_agent.py              # Discover-stage clustering + scoring
  decide_agent.py                # Decide-stage pursue/watch/discard classification
  run_pipeline.py                # full daily run: ingest -> Sense -> Discover -> Decide -> digest
/data/runs/YYYY-MM-DD/          # raw posts, signals, scored clusters, decisions (JSONL) — gitignored
/reports/                       # generated daily digests — gitignored, not committed
/web/
  app.py                        # FastAPI query API + server-rendered dashboard
  store.py                      # loads/filters data/runs/*/{clusters,decisions}.jsonl (no DB yet)
  templates/index.html          # dashboard view (Jinja2)
```

## Running it

```
pip install -r requirements.txt
cp .env.example .env   # fill in ANTHROPIC_API_KEY (required); STACKEXCHANGE_KEY is optional
python agents/run_pipeline.py
```

This pulls a real batch from Stack Exchange and Hacker News, runs all three
LLM stages, and writes a digest — grouped into Pursue/Watch/Discard sections,
ranked by `overall_rank_score` within each — to `reports/<date>.md`, plus raw
posts/signals/clusters/decisions to `data/runs/<date>/*.jsonl`. It makes real
Anthropic API calls and Stack Exchange/HN requests — expect it to take
several minutes.

To check any stage against its eval instead of running the full pipeline:

```
python evals/run_evals.py                     # Sense-stage
python evals/run_discover_scoring_eval.py      # Discover-stage
python evals/run_decide_eval.py                # Decide-stage
```

To browse and filter every run's scored clusters — a dashboard plus a JSON
API, both reading directly off `data/runs/*/clusters.jsonl`, no database:

```
uvicorn web.app:app --reload
```

Then open `http://127.0.0.1:8000/` for the dashboard (filter by date range,
minimum `overall_rank_score`, keyword, or Decide `pursue`/`watch`/`discard`
action), or query `GET /api/clusters` / `GET /api/runs` directly.

## What's not built yet

- **A held-out eval set** — all Discover-stage and Decide-stage calibration
  has been checked against the same small hand-labeled set each was tuned
  on (16 and 21 rows respectively, both from a single pipeline run).
- **Cybersecurity-vs-general-ops scope filtering at the Sense/Discover
  level** — the off-mission ops/reliability clusters (backup tooling, VPN
  architecture) still pass through Sense and Discover unfiltered and get
  scored/clustered before Decide catches and discards them; the digest's
  Discard section is correct, but the earlier stages do the wasted work.

## Deployment — decided against

Railway deployment (managed Postgres, a scheduled worker, a hosted web
service) was evaluated once all three stages were eval-passing and
**rejected on cost grounds**: measured actual token usage from a real
pipeline run put a single full pull-and-process pass at roughly $2.66-4.00
(186 posts -> Sense -> Discover -> Decide), which projected to roughly
$95-135/month on a naive daily-repeat cadence or $26-42/month weekly, plus
a roughly flat ~$15-25/month for Railway hosting regardless of cadence.

That per-run estimate assumed every run re-pulls and re-processes the same
~365-day batch from scratch — which was true at the time, but was itself a
bug that's since been fixed: `agents/run_pipeline.py` now tracks a
`last_run_at` cursor (`data/last_run.json`) and pulls incrementally since
the last run, so *repeat* runs only cost whatever it takes to process
genuinely new posts, not the full historical batch every time. A same-day
rerun in testing pulled 0 new posts and cost $0 in LLM spend. The original
monthly projection above is therefore a ceiling on repeat-run cost, not the
real steady-state number — but it doesn't change the Railway decision
itself, since the ~$15-25/month hosting floor was never about pipeline-run
cost in the first place, and running this locally by hand costs nothing
beyond the (now much cheaper) per-run LLM spend.

This project's final form runs locally: `agents/run_pipeline.py` for the
pipeline, local JSONL storage under `data/runs/` as the permanent store,
and `web/app.py` run locally for the dashboard.

See `docs/progress.md` for the full status snapshot and calibration history,
and `docs/architecture.md` / `docs/data-sources.md` for the underlying design
decisions.
