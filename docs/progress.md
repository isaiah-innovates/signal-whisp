# Progress

Status snapshot for picking this project back up in a new session. See
`CLAUDE.md` for the non-negotiable principles and build order this all
follows — this file is "where are we against that plan," not a replacement
for it.

## Build order status (per CLAUDE.md)

1. **Pull real candidate posts + hand-label `evals/signal-extraction.md`** — DONE.
2. **Build Sense-stage extraction agent (`agents/sense_agent.py`)** — DONE,
   eval-passing (~89.7%, accepted in spirit — see `evals/signal-extraction.md` §7).
3. **Build clustering across posts/sources/days** — DONE (`agents/discover_agent.py:cluster_signals`,
   pipeline in `agents/run_discover_pipeline.py`).
4. **Hand-label `evals/opportunity-scoring.md` from real extracted/clustered output** — DONE.
   All 16 real candidate clusters scored across every rubric dimension.
5. **Build Discover-stage scoring agent against that eval** — ACCEPTED, per
   user decision on 2026-07-21. `overall_rank_score` is a deterministic
   formula (`compute_overall_rank_score`) with `overall_rank_score` MAE
   0.060 and 4/16 exact rank-position agreement on the last full live run
   (up from MAE 0.114-0.115 and 1-2/16 before this session's tuning pass —
   see "Scoring design" below for the full history). Known open gaps
   accepted as-is rather than blocking further work: `signal_validity` and
   `novelty` remain noisier than the other dimensions (`novelty` by design
   — the rubric requires it stay human-review-only, never tuned tight);
   cluster-10's `small_team_feasibility` is a known remaining outlier
   (truth 0.30 vs. predicted 0.70); and all calibration to date has only
   ever been validated against the same 16 hand-labeled clusters it was
   fit to, with no held-out set. None of these blocked the decision to
   move on — they're open follow-ups if this stage gets revisited.
6. **Delivery layer (digest + query interface)** — DONE. Digest half:
   `agents/run_pipeline.py` (ingest -> Sense -> Discover -> ranked markdown
   digest). Run end-to-end on real data on 2026-07-22: 186 posts pulled, 27
   judged `is_signal=true`, clustered into 21, all 21 scored — output at
   `reports/2026-07-22.md` and `data/runs/2026-07-22/*.jsonl`
   (posts/signals/clusters). Top-ranked opportunity scored 0.77
   (ITAR/CMMC compliance-mapping tooling for small teams); formula/floor
   logic behaved as designed throughout.

   Query interface half, built 2026-07-22: `web/app.py` (FastAPI) +
   `web/store.py` (loads/filters `data/runs/*/clusters.jsonl` — no database
   yet, per CLAUDE.md's stack conventions) + `web/templates/index.html`
   (server-rendered dashboard, Jinja2). `GET /api/clusters` (filterable by
   `date_from`/`date_to`/`min_score`/`q`) and `GET /api/runs` for the JSON
   API; `GET /` for the HTML dashboard, same filters as GET query params.
   Verified with FastAPI's `TestClient` against the real 2026-07-22 data
   (21 clusters): unfiltered listing, `min_score` filter (21 → 7),
   keyword search (`q=compliance` → 10), combined filters, and the
   empty-results state all render correctly. Also smoke-tested with a live
   `uvicorn` process on port 8420. Not visually eyeballed in a browser this
   session (no browser tool available) — only checked programmatically.
7. **Hand-label `evals/decide-classification.md`** — DONE, 2026-07-22. All 21
   real candidate rows (from the 2026-07-22 pipeline run) labeled by the
   human labeler conversationally, batch by batch: 4 `pursue`, 9 `watch`,
   8 `discard`, each with a written rationale. Key finding from the labeling
   (see the file's "Patterns observed" section): the draft score-threshold
   rubric does **not** cleanly hold — the 6 rows at the
   `small_team_feasibility` floor split 3 `discard`/3 `watch` on a judgment
   no existing field encodes (is the feasibility blocker durable, e.g.
   "have to be Microsoft/a carrier to solve" → `discard`, or possibly
   temporary, e.g. "look for feasibility to change, then evaluate again"
   → `watch`). `novelty` was never cited as a driver in any of the 21.
   All 3 previously-flagged off-mission ops/reliability clusters
   (cluster-7/8/9 — mariadb-backup, DR/RTO, WireGuard multi-site VPN) were
   independently labeled `discard` as off-mission, suggesting Decide is
   where that scope gap naturally gets enforced.
8. **Build the Decide-stage classification agent** (`agents/decide_agent.py`)
   — DONE, eval-passing, 2026-07-22. LLM-as-judge (not a formula — see
   below for why), scored 19/21 (90.5%) on `evals/run_decide_eval.py`
   after two tuning passes (71.4% → 85.7% → 90.5%). Both remaining
   mismatches are genuine boundary calls: the documented "timing" outlier
   with no textual basis (permanent, accepted limitation), and one
   defensible close-call disagreement using the same rule that fixed
   three other rows. Off-mission scope pruning held correctly across all
   three eval runs. **Wired into `agents/run_pipeline.py`** the same day:
   `decide_clusters()` classifies every `ScoredCluster`, persists
   `data/runs/<date>/decisions.jsonl`, and `render_digest()` now groups the
   digest into Pursue/Watch/Discard sections (ranked by `overall_rank_score`
   within each) instead of one flat list. Re-ran the full pipeline on real
   data: 21/21 clusters classified with no failures (4 pursue / 11 watch /
   6 discard) — output at `reports/2026-07-22.md` (overwritten) and
   `data/runs/2026-07-22/decisions.jsonl`.
9. **Railway deployment (Postgres + scheduled worker + web service)** — NOT
   STARTED, now unblocked (Decide is eval-passing). Per user decision on
   2026-07-22: nothing currently runs on a schedule (confirmed by
   inspection: no cron/GitHub Actions/Railway config exists;
   `run_pipeline.py`'s "daily" naming describes intent, not an actual
   schedule), so there was no cost to sequencing Decide first — this is
   the next real step.

## What exists right now

- `agents/sense_agent.py` — Sense-stage extraction. One post in, `ExtractionResult`
  out (`is_signal`, `problem_statement`, `affected_role`, `current_workaround`,
  `workaround_type`, `corroboration_signal`, `confidence`). Forced tool use,
  passing its eval.
- `agents/discover_agent.py` — Discover-stage clustering *and* scoring:
  - `cluster_signals()` — groups `ExtractionResult`s into `Cluster`s sharing
    the same underlying pain point (LLM-as-judge, forced tool use).
  - `score_cluster()` — scores a `Cluster` into a `ScoredCluster` against
    `evals/opportunity-scoring.md`'s rubric. `frequency_corroboration` is a
    pure formula (no LLM). `small_team_feasibility` and
    `willingness_to_pay_signal` are computed deterministically from an
    LLM-classified single-choice tier (`compute_small_team_feasibility`,
    `compute_willingness_to_pay_signal` — see "Scoring design" below).
    `overall_rank_score` is now also a deterministic formula
    (`compute_overall_rank_score` — floor when `small_team_feasibility`
    is near-zero, else a weighted blend of feasibility, willingness-to-pay,
    and inverted novelty), fit to the 16 hand-labeled clusters. `signal_validity`
    and `extraction_accuracy` are still direct LLM output. `novelty` is
    still a direct LLM float and explicitly DRAFT-only per the rubric
    (human-review-only by design — the formula consumes it as an input but
    never treats it as final).
- `agents/run_discover_pipeline.py` — pulls a real multi-day/multi-source
  batch (SE `security` + `serverfault` tags, HN relevance search over a
  365-day window), runs Sense-stage extraction, clusters. Does **not** write
  to the eval file — that stays a manual human step.
- `agents/run_pipeline.py` — the full daily driver: ingest -> Sense ->
  Discover (cluster + score) -> Decide (classify) -> persist
  `data/runs/<date>/*.jsonl` (posts/signals/clusters/decisions) -> render
  `reports/<date>.md`, grouped into Pursue/Watch/Discard sections. Reuses
  `pull_batch`/`extract_signals` from `run_discover_pipeline.py` rather than
  duplicating them.
- `web/` — query API + minimal dashboard over everything `run_pipeline.py`
  has ever persisted. `store.py` loads/filters `data/runs/*/clusters.jsonl`;
  `app.py` (FastAPI) exposes `GET /api/clusters` and `GET /api/runs`, plus
  `GET /` for a server-rendered HTML dashboard (Jinja2,
  `templates/index.html`) with the same date-range/min-score/keyword
  filters as GET params. No database — reads the JSONL files directly, per
  CLAUDE.md's stack conventions (Postgres arrives at Railway deployment,
  not before). Run with `uvicorn web.app:app --reload` from the repo root.
  **Does not yet read `decisions.jsonl`** — `decide_action` isn't
  filterable/visible in the dashboard yet, only in the rendered digest.
- `agents/decide_agent.py` — Decide-stage classification. One `ScoredCluster`
  in, `DecideResult` out (`decide_action`, `rationale`). Forced tool use,
  LLM-as-judge (not a formula — see "Decide-stage design" below), passing
  its eval at 19/21 (90.5%).
- `evals/run_decide_eval.py` — scores `decide_agent.py:classify_cluster`
  against `evals/decide-classification.md`. Reconstructs each row's exact
  `ScoredCluster` from the already-persisted `data/runs/<run_id>/clusters.jsonl`
  rather than re-running Sense/Discover, so the only variance in this eval
  is the Decide agent's own classification.
- `evals/decide-classification.md` — Decide-stage ground truth, DONE. 21
  real clusters (from `data/runs/2026-07-22/clusters.jsonl`), each hand-labeled
  `pursue`/`watch`/`discard` with written rationale (4/9/8 split). Read
  this file's "Patterns observed" section before touching `decide_agent.py`
  — a pure score-threshold rubric didn't hold, which is why the agent is
  LLM-as-judge, not a formula.
- `evals/signal-extraction.md` — Sense-stage ground truth, real hand-labeled
  rows, passing.
- `evals/opportunity-scoring.md` — Discover-stage ground truth. 16 real
  clusters (3 more were pulled and explicitly pruned as off-mission
  ops/reliability noise — see rationale in the file's status paragraph),
  every rubric dimension hand-scored with written reasoning per row.
- `evals/run_evals.py` — scores `sense_agent.py` against
  `evals/signal-extraction.md`.
- `evals/run_discover_scoring_eval.py` — scores `discover_agent.py:score_cluster`
  against `evals/opportunity-scoring.md`. Re-fetches each row's posts live,
  re-runs Sense-stage extraction, reports per-field MAE and rank-ordering
  agreement.
- `docs/blogs/` — five drafts on lessons learned building this so far (see
  below).

## Scoring design — how we got here (read before touching the scoring prompt)

`small_team_feasibility` and `willingness_to_pay_signal` used to be direct
LLM floats. That failed badly against hand labels (MAE 0.22 / 0.18, and the
model's overall ranking only agreed with the human ranking on 4/16
clusters) — the model and the human were using different implicit
assumptions for the same 0-1 number. Fix, in the order it actually
happened (each step is in `agents/discover_agent.py`'s `SCORING_SYSTEM_PROMPT`
and the `compute_*` functions):

1. Reverse-engineered the human's actual reasoning from all 16 rationales
   into an explicit checklist of concrete yes/no facts per dimension.
2. First attempt: independent booleans, first-match-wins priority order.
   Fixed feasibility (MAE 0.22 → 0.09) but broke willingness-to-pay
   (0.18 → 0.26) — the checklist items weren't independent, they were
   different framings of the same decision, and the model set conflicting
   flags true.
3. Fix: collapsed each checklist into one mutually-exclusive enum tier per
   dimension (`small_team_feasibility_tier`, `willingness_to_pay_signal_tier`
   in `SCORE_CLUSTER_TOOL`). Fixed willingness-to-pay (→ 0.175) but
   re-broke feasibility (→ 0.181) on a few genuinely ambiguous boundary
   cases.
4. Fix: added six worked examples (real clusters, spelled out with why one
   boundary tier applies and its lookalike neighbor doesn't) to the system
   prompt. Feasibility MAE → 0.05 (13/16 exact), willingness-to-pay → 0.125.

**Known, deliberately-unresolved issues in the current scoring agent:**

- The six worked examples are six of the sixteen ground-truth rows. Scoring
  well on them isn't proof of generalization — could be memorization. With
  only 16 labeled clusters total there's no room for a real held-out set.
  If more clusters get hand-labeled later, re-running
  `evals/run_discover_scoring_eval.py` on the *new, unseen* ones is the real
  test.
- Worked examples caused a real negative-transfer failure: two "Cyber
  Essentials" clusters that should score very differently on
  willingness-to-pay got conflated after one was added as a worked example
  (0.8-point miss, the worst single error across every run). Worth
  remembering if more worked examples get added — a lookalike pair can
  bleed into each other.
- `overall_rank_score` is now `compute_overall_rank_score` in
  `agents/discover_agent.py`: if `small_team_feasibility <= 0.1`, floor at
  0.1 (0.2 if `novelty >= 0.6`); else
  `0.45*feasibility + 0.45*willingness_to_pay + 0.1*(1-novelty)`, rounded.
  Reverse-engineered the same way feasibility/willingness were — the floor
  rule was an exact match for all 7 near-zero-feasibility rows in the hand
  labels. Fit to the 16 hand-labeled clusters: MAE 0.034 and correct
  floor/bump behavior on every row *when fed ground-truth sub-scores*
  offline. Run against live re-extraction (`evals/run_discover_scoring_eval.py`),
  MAE only rose to 0.115, but exact rank-position agreement dropped to
  2/16 — worse than the previous freehand-LLM baseline (~4/16). Root cause
  isn't the formula: `overall_rank_score` now inherits noise directly from
  `willingness_to_pay_signal` (live MAE 0.169) and `novelty` (live MAE
  0.181), both pre-existing weak points. One bad live tier classification
  (cluster-17's small_team_feasibility tier scored 0.1 vs. truth 0.5) alone
  produced the single worst overall_rank_score miss (0.55 off) and knocked
  it to the bottom of the predicted ranking. Fit to only 16 points with no
  held-out set — risk of overfitting to this exact set is real and
  unresolved. Next natural step, if this keeps getting worked: reduce
  willingness/novelty classification noise (more worked examples? explicit
  tiers for novelty the way feasibility/willingness got?) before trusting
  the rank-agreement number further — not yet decided.
- Fixed a separate bug hit while running the above: `evals/run_discover_scoring_eval.py`
  intermittently skipped clusters with `fetch/extraction failed: 'is_signal'`.
  Root cause: `agents/sense_agent.py:extract_signal` used `max_tokens=1024`
  against a ~550-590-token typical response — a verbose post could
  occasionally push the model's tool-call JSON right up to that ceiling and
  get cut off mid-write, leaving `fields` missing required keys and raising
  a raw `KeyError`. Fixed by raising `max_tokens` to 2048 and adding
  validation-with-retry (`_MAX_ATTEMPTS = 3`) that checks all required
  fields are present before accepting the response, raising a clear
  `ValueError` (not a bare `KeyError`) if all attempts come back malformed.
  Re-ran `evals/run_evals.py` after the fix: 89.7% accuracy, same known
  false-negative pattern as before (rows 9/17/21) — no regression.
- Reduced willingness-to-pay/feasibility classification noise via three
  new worked examples in `SCORING_SYSTEM_PROMPT`, each targeting a specific
  observed live miss rather than a hypothetical one: (1) the Cyber
  Essentials sudo-account cluster (revealed-effort spend, 0.6) vs. the
  Cyber Essentials Plus endpoint-agent cluster (no signal, 0.1) — the model
  had been over-triggering `grc`/compliance-driven tiers just because
  "Cyber Essentials" was named, regardless of whether any effort/spend was
  actually shown; (2) the OpenSSH cert-monitoring cluster, where building a
  fragile hand-rolled script *is* the revealed-effort signal; (3) the Azure
  Cognitive Services lifecycle cluster, clarifying `plausible_enterprise_
  budget_inferred` vs. `faint_market_touchpoint` (a plausible buyer
  category counts even with zero budget language in-post). Result:
  `willingness_to_pay_signal` MAE dropped from 0.169/0.143 (prior two live
  runs) to 0.037-0.038 on the next two runs, all 16 rows within tolerance.
  A fourth worked example fixed a separate, consistently-reproduced
  `small_team_feasibility` miss: cluster-17 (bank OTP/vishing wording) was
  misclassified as `requires_carrier_regulator_or_standards_body` (0.1) in
  every run so far, because the model treated "the literal fix is the
  bank's own SMS copy" as equivalent to "only a carrier/regulator can act"
  — conflating it with the RCS sender-ID spoofing cluster (cluster-1),
  which genuinely has no adjacent-product path. Added a contrasting pair
  (cluster-1 vs. cluster-17) clarifying that a small team can build and
  sell an *adjacent* product without the bank's cooperation. Verified with
  3 isolated repeat calls on cluster-17 alone (feasibility landed on the
  correct tier, 0.5, all 3 times — previously wrong 3/3) and then a full
  16-cluster run: `small_team_feasibility` MAE 0.031, `willingness_to_pay_signal`
  MAE 0.038, `overall_rank_score` MAE **0.060** (down from 0.115 →0.093 →
  0.060 across the three tuning passes), exact rank-position agreement
  4/16 — the best result of any run to date on every tracked metric except
  `novelty` (still untouched, still noisy, by design — see below) and
  `signal_validity` (also untouched, MAE ~0.06-0.11, not a focus of this
  pass).
- `novelty` is intentionally never converted to a formula — the rubric
  requires it stay human-review-only ("don't let an LLM self-certify
  novelty"). The LLM still drafts a value for convenience, but it's marked
  DRAFT and isn't meant to be trusted as-is.
- `signal_validity` and `extraction_accuracy` are still direct LLM floats,
  performing acceptably (MAE ~0.05-0.09) — not touched by the checklist
  refactor, no known issue.

## Decide-stage design — how we got here (read before touching decide_agent.py)

`agents/decide_agent.py` classifies a `ScoredCluster` into
`pursue`/`watch`/`discard`. Unlike Discover-stage's `overall_rank_score`,
this was never attempted as a formula — the hand-labeling itself showed a
pure score-threshold rule doesn't hold (see
`evals/decide-classification.md`'s "Patterns observed": the floor-scoring
group split evenly between `watch` and `discard` on a durability judgment
no numeric field encodes). So this went straight to LLM-as-judge, prompted
with the real patterns found in the 21 labeled rows.

Tuning history against `evals/run_decide_eval.py`:

1. First version: off-mission scope check, a "durable dead-end feasibility
   tier -> discard" rule, and a loosely-worded "weigh the profile
   holistically" step for everything else. **71.4% (15/21).**
2. Diagnosed two real bugs from the mismatches: (a) the off-mission check's
   examples (backup/DR, VPN, DB backup) were generalizing too broadly,
   misclassifying an Apache traffic-visibility gap as off-mission when the
   human hadn't flagged it that way at all; (b) the model was collapsing
   `watch` into `discard` whenever either `small_team_feasibility` or
   `willingness_to_pay_signal` alone looked weak, when the real pattern was
   that discard requires **both** to be weak (or an explicit override).
   Narrowed the off-mission examples and replaced the holistic step with an
   explicit both-weak-required rule, plus real contrastive examples for
   each. **85.7% (18/21)**, fixing all three `watch`->`discard` bugs.
3. That fix introduced one new regression: a cluster with
   `requires_platform_vendor_code_fix`/`faint_market_touchpoint` (both
   weak) got discarded, when the human said `watch` because this tier's
   own definition already grants a partial-workaround path — the new
   both-weak rule didn't know to exempt tiers that carry that built-in
   allowance. Added an explicit exception for
   `requires_platform_vendor_code_fix` and
   `requires_real_incident_engagements_to_validate`. **90.5% (19/21)**,
   no further regressions.

**Remaining 2 mismatches, both read as acceptable:**

- One cluster was hand-labeled `watch` purely on a "not the right timing"
  judgment with zero textual basis in the cluster's own data — not
  learnable from `ScoredCluster`, called out as a permanent, accepted
  limitation in the agent's own docstring rather than something to keep
  chasing.
- One cluster (strong `buildable_as_independent_tool` feasibility, dampened
  `willingness_to_pay_signal` from incumbent competition) is a genuinely
  close boundary call — the model's reasoning is internally consistent
  with the same rule that correctly fixed three *other* rows, it just
  lands on the more conservative side here. Read as a defensible
  disagreement, not a bug.

Same caveat as Discover-stage scoring: only 21 rows from one pipeline run,
no held-out set. A second real pipeline run's output, hand-labeled fresh,
would be a much better test than anything done against these same 21 rows.

## Documentation written alongside the build

`docs/blogs/` — five drafts, not yet finalized for publishing:
- `blog_post_1.md` — user's original draft on the eval-scoring rework.
- `blog_post_2.md` — corrected/expanded rewrite (user's preferred version,
  now has Substack-ready headers). Covers the scoring-calibration story
  above in narrative form.
- `blog_post_3.md` — "The bug that looked like a data problem" (the HN
  `by_date=True` relevance-ranking bug that looked like a market-thinness
  finding).
- `blog_post_4.md` — "When broadening your data sources breaks your eval's
  scope" (the ServerFault-noise pruning episode).
- `blog_post_5.md` — "Your eval file can be your database" (the
  markdown-table-as-ground-truth pattern used throughout).

None of these have been finalized/published yet — that's a pending
decision for the user, not a task in progress.

## Open questions / natural next steps (not yet decided)

- Fix `overall_rank_score` the same way feasibility/willingness were fixed
  (deterministic formula over the now-reliable sub-scores), or hand-label
  more clusters first to get a genuine held-out test set before trusting
  any further calibration work? Both were named as options; nothing chosen.
  Discussed in the eval status writeup in `evals/opportunity-scoring.md`.
- Finalize/merge the blog post drafts (which pieces from post 1 vs. post 2
  make the final cut) and decide on/edit posts 3-5 before anything gets
  published externally.
- Everything downstream of scoring (delivery layer, Railway deployment) is
  untouched and blocked on this stage being called "done" per CLAUDE.md's
  stage discipline.

## Where to pick this up

**Immediate next step (as of 2026-07-22):** Railway deployment (build order
step 9) — Sense, Discover, and Decide are all eval-passing now, and nothing
currently runs on a schedule, so this is the first real gap left. Read
`docs/architecture.md`'s "Deployment target" section before starting.

If Decide-stage classification itself gets revisited: read
`evals/decide-classification.md`'s "Patterns observed" section and
`docs/progress.md`'s "Decide-stage design" section above first — a pure
score-threshold rubric doesn't cleanly separate `watch` from `discard`, so
`decide_agent.py` is LLM-as-judge, currently 19/21 (90.5%) with two
accepted, non-bug mismatches. The real open gap is the lack of a held-out
set (same as Discover) — a second real pipeline run's output, hand-labeled
fresh, would be the actual next test, not more tuning against these same
21 rows.

For the Discover-stage scoring work (lower priority right now, not
blocking): read `evals/opportunity-scoring.md`'s status paragraph and
"## Rows" section for the ground truth, then `agents/discover_agent.py`'s
module docstring and `SCORING_SYSTEM_PROMPT` for the current scoring
design, before touching any scoring logic. Ask before assuming which open
question to tackle first — none has been decided yet.
