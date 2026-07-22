# Data Sources

Reddit is currently gated: self-service OAuth app creation (reddit.com/prefs/apps
issuing an instant client_id/secret) was discontinued; new Data API access now
requires manual review under Reddit's Responsible Builder Policy, with real
rejection risk for small/non-commercial projects. Devvit (Reddit's alternative
developer platform) doesn't fit this use case either — Devvit apps are designed
to run *inside* Reddit and must be installed on a subreddit by that subreddit's
moderators to interact with it; there's no clean path for an outside pipeline to
read across subreddits it doesn't moderate. Given that, this project's live daily
ingestion runs on Stack Exchange and Hacker News instead, both of which are
open, free, and unauthenticated (or lightly authenticated) by design.

All three "live" clients below should normalize into the shared post record
defined in `docs/architecture.md`.

## Stack Exchange API — PRIMARY live source

- Official REST API. Free for this scale: 300 requests/day unauthenticated,
  10,000/day with a registered app key.
- Optional key: register at https://stackapps.com/apps/oauth/register (just an
  app name + description, no approval wait — different from Reddit's process).
  Store as `STACKEXCHANGE_KEY` in `.env` if used; the client should work without
  it, just at the lower quota.
- Base URL: `https://api.stackexchange.com/2.3`
- Target sites: `security` (security.stackexchange.com) as primary; consider
  relevant tags on `serverfault` and `superuser` as secondary sites within the
  same client.
- Key endpoint: `GET /questions` — params: `site`, `order`, `sort`
  (e.g. `activity`, `creation`), `pagesize`, optionally `tagged` (e.g.
  `phishing`, `siem`) and `fromdate` (unix timestamp, for incremental daily
  pulls). Add `filter=withbody` to get question body text in the response
  (without it, body is omitted by default).
- To get answer text (candidate "workaround" content), batch-fetch via
  `GET /questions/{ids}/answers` with semicolon-joined question IDs (up to 100
  per call), `filter=withbody`, `order=desc`, `sort=votes` to prioritize
  accepted/top answers.
- Response bodies are HTML — strip tags before handing to the extraction agent.
- The API returns a `backoff` field in some responses when you're calling too
  fast; respect it (sleep that many seconds before the next call).
- Why this is a strong primary source: Q&A format inherently forces posters to
  state a specific problem, and answers often state the workaround/fix
  directly — less noise-filtering needed than a general discussion feed.

## Hacker News (Algolia Search API) — SECONDARY live source

- Free, no authentication, near-real-time index of all HN content.
- Base URL: `https://hn.algolia.com/api/v1`
- Key endpoints:
  - `GET /search_by_date` — best for daily incremental pulls, sorted by
    recency. Params: `query`, `tags` (e.g. `story`, `ask_hn`, `show_hn`),
    `hitsPerPage`.
  - `GET /search` — relevance-ranked, better for broad one-off discovery than
    daily incremental pulls.
  - `GET /items/{id}` — full item detail including nested comment tree
    (`children`), useful for pulling a few top-level comments as corroboration
    context. This is a separate call per story — be mindful of call volume if
    pulling comments for every hit.
- No documented hard rate limit; informal guidance is to stay well under
  ~10,000 requests/hour and add small delays between paginated calls.
- Story/comment text may contain HTML — strip tags before extraction.
- Why this is useful despite lower "pain signal density" than a Q&A site:
  catches broader industry discussion (Ask HN threads, comments on
  security-adjacent posts) that a Q&A format won't surface. Extraction
  confidence should generally weight HN corroboration lower than Stack
  Exchange's accepted-answer signal, since HN comments are more often opinion
  than a stated fix.

## Reddit — DORMANT, pending official API approval

- Submit an application through Reddit's Data API approval process
  (Responsible Builder Policy review) in parallel with everything else — it's
  free, just gated by manual review.
- If/when approved: standard OAuth2 "script" app via reddit.com/prefs/apps
  (client_id, client_secret, descriptive user_agent), read-only access via
  PRAW or direct OAuth calls. No username/password needed for read-only use.
- Build this client to the same shared post record shape as the others so it
  drops in without touching `sense_agent.py` once credentials exist.
- Do not attempt unauthenticated `.json` endpoint scraping as a workaround —
  Reddit closed that path in 2026 specifically to stop this pattern.

## Arctic Shift — historical Reddit backfill (NOT a live daily source)

- Open-source, community-maintained archive of historical Reddit posts/comments
  back to 2005: https://github.com/ArthurHeitmann/arctic_shift
- Free API + bulk downloadable dumps, no Reddit OAuth needed at all.
- Updates roughly monthly — treat as a batch backfill for building/labeling the
  eval sets with real historical data, not as part of the daily ingestion cron.
- Useful specifically for getting real (not synthetic) historical Reddit
  threads into `evals/signal-extraction.md` without waiting on Reddit's
  approval process.

## Rate limit / politeness baseline for all sources
Respect documented limits, add short delays between paginated calls, and log
enough about each ingestion run (source, query/params, count fetched, any
backoff hit) to debug quota issues later.
