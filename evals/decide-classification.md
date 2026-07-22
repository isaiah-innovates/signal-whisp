# Eval Set 3: Decide Classification (Decide Stage)

**Status: SKELETON.** Target schema and rubric structure are drafted below;
**no row has a human-assigned `decide_action` yet.** Per `CLAUDE.md`
principle 2, nothing in the `## Rows` table below is ground truth until a
human fills in `decide_action` and `rationale` — the values pulled in are
real `ScoredCluster` output from `data/runs/2026-07-22/clusters.jsonl`
(21 real clusters, one full pipeline run), not synthetic. Do not build or
change `agents/decide_agent.py` (not yet created) against this file until
it's actually hand-labeled.

**Feature under test:** the agent that takes one Discover-stage
`ScoredCluster` (all its sub-scores plus `overall_rank_score`) and classifies
it into an action bucket a PM would actually act on: **pursue** (build/
investigate now), **watch** (real but not yet actionable — keep tracking for
more corroboration or a score change), or **discard** (not worth further
attention).

Per user decision on 2026-07-22: this stage's rubric should be a genuine
decision derived from the score thresholds Discover already computes — not a
new judgment dimension the LLM has to independently assess. The exact
thresholds/floors below are a **draft starting point**, not settled; the
real spec is whatever a human labeler actually picks per row once looking at
each cluster's full score profile, with the reasoning written out — same
process `evals/opportunity-scoring.md` used to arrive at
`compute_overall_rank_score`'s floor rule.

## Target schema

```json
{
  "cluster_id": "string",
  "run_id": "string",
  "opportunity_statement": "string",
  "overall_rank_score": 0.0-1.0,
  "decide_action": "pursue" | "watch" | "discard",
  "rationale": "string — human-written, cites which score(s) drove the call"
}
```

## Rubric (draft — confirm or correct against real rows before building)

| Action | Draft criteria | Method |
|---|---|---|
| `pursue` | High `overall_rank_score` **and** no disqualifying floor on `small_team_feasibility` or `willingness_to_pay_signal` — a small team could plausibly act on this today. | Threshold/floor over existing Discover-stage fields — TBD exact numbers pending hand-labeling. |
| `watch` | Moderate `overall_rank_score`, or a high score undercut by thin `frequency_corroboration` (single signal, not yet corroborated) — real signal, not yet enough to commit to. | Same. |
| `discard` | Low `overall_rank_score`, typically floored by `small_team_feasibility` (per `compute_overall_rank_score`'s existing floor logic) or clearly not a fit regardless of other dimensions. | Same. |

Open questions for the human labeler to resolve while labeling real rows
(don't guess — pick per row and let the pattern emerge):

- Does a single-signal cluster with a high score (e.g. cluster-16 below,
  `overall_rank_score=0.77` on 1 signal) get `pursue`, or does low
  `frequency_corroboration` alone force it to `watch` regardless of score?
- Is there a hard `overall_rank_score` floor below which something is always
  `discard`, independent of any other field?
- Should `novelty` (DRAFT/human-review-only per `opportunity-scoring.md`)
  factor into this call at all, given it's explicitly not meant to be
  trusted as agent output?

## Building this eval set

1. For each row below, decide the `decide_action` you'd actually choose
   looking at the full score profile (linked signals included), and write
   the `rationale` — be explicit about which field(s) drove the call.
2. Once ~15-20 rows are labeled, look for the pattern across `pursue` vs.
   `watch` vs. `discard` calls the same way `compute_overall_rank_score`'s
   floor rule was reverse-engineered from hand labels — resolve the open
   questions above from what you actually did, not from a rule decided in
   advance.
3. Add adversarial/boundary rows deliberately once real data suggests them
   (e.g. a high-score single-signal cluster that should clearly be `watch`
   despite the score, to test that corroboration count isn't ignored).

## Rows

All 21 rows below are real `ScoredCluster` output from the 2026-07-22
pipeline run (`data/runs/2026-07-22/clusters.jsonl`), sorted by
`overall_rank_score` descending. `decide_action` and `rationale` are
**PENDING** — fill these in by hand; do not treat any placeholder as ground
truth.

| cluster_id | run_id | signal_ids | opportunity_statement | overall_rank_score | decide_action | rationale |
|---|---|---|---|---|---|---|
| cluster-16 | 2026-07-22 | [HN 35991269](https://news.ycombinator.com/item?id=35991269) | Small tech companies pursuing ITAR/CMMC and similar enterprise/government compliance frameworks lack a structured, developer-friendly methodology or tooling to map required controls to proportionate, BYOD/Mac-compatible implementations instead of defaulting to heavyweight Windows/AD/MDM stacks pushed by compliance leads and MSPs. | 0.765 | PENDING | PENDING |
| cluster-3 | 2026-07-22 | [HN 32737886](https://news.ycombinator.com/item?id=32737886), [HN 30128872](https://news.ycombinator.com/item?id=30128872) | Open-source maintainers and downstream security teams need a reachability/exploitability-aware vulnerability scanner that filters CVE noise from lockfile-based tools like Dependabot/Snyk by verifying whether flagged vulnerable code paths are actually called, reducing wasted triage time and CVE disputes. | 0.65 | PENDING | PENDING |
| cluster-18 | 2026-07-22 | [HN 21200914](https://news.ycombinator.com/item?id=21200914) | Banks and fintechs lack an adjacent tooling layer (e.g., vishing-call correlation/scoring or context-aware OTP messaging templates) to counter social-engineering attacks that exploit generic, purpose-less OTP/PIN reset SMS messages to trick customers into reading out codes. | 0.635 | PENDING | PENDING |
| cluster-5 | 2026-07-22 | [SF 1198279](https://serverfault.com/questions/1198279/monitor-expiration-of-openssh-certificates-users-and-hosts) | Provide a lightweight monitoring/alerting tool that centrally tracks OpenSSH CA-issued host and user certificate expiration across fleets and automated service accounts, replacing fragile hand-rolled ssh-keyscan/ssh-keygen/awk scripts. | 0.63 | PENDING | PENDING |
| cluster-2 | 2026-07-22 | [SE 286827](https://security.stackexchange.com/questions/286827/how-should-a-small-security-team-prioritize-cves-when-cvss-scores-dont-reflect), [HN 45997568](https://news.ycombinator.com/item?id=45997568) | Small security/engineering teams need an affordable tool that reprioritizes the flood of CVE/dependency alerts using real-world exploitability signals (CISA KEV, EPSS, contextual risk) instead of raw CVSS scores, to stop wasting patching effort on low-risk high-CVSS findings while actively-exploited vulnerabilities linger. | 0.56 | PENDING | PENDING |
| cluster-8 | 2026-07-22 | [SF 1190750](https://serverfault.com/questions/1190750/fast-server-restore-through-virtualization-container-os-on-single-dedicated-mach) | Solo sysadmins and small businesses running a single dedicated server lack an affordable, pre-tested disaster-recovery/rebuild playbook (backup format + restore automation + RTO validation) that doesn't require enterprise failover infrastructure. | 0.56 | PENDING | PENDING |
| cluster-11 | 2026-07-22 | [SF 1197794](https://serverfault.com/questions/1197794/how-can-i-bulk-rotate-renew-all-the-keys-of-all-my-resources-in-my-azure-subscri), [SF 1197698](https://serverfault.com/questions/1197698/how-can-one-disable-pause-an-azure-cognitive-services-resource-to-prevent-furthe), [SF 1197808](https://serverfault.com/questions/1197808/how-can-i-configure-azure-so-that-i-get-an-email-alert-when-someone-accesses-vie) | Azure admins managing Cognitive Services (and similar) resources at scale need a third-party tool to bulk-rotate keys, pause billing, and alert on key access — capabilities Azure's own portal/CLI don't natively provide. | 0.545 | PENDING | PENDING |
| cluster-6 | 2026-07-22 | [SF 1193229](https://serverfault.com/questions/1193229/monitor-backend-of-httpds-load-balancer) | Sysadmins running Apache httpd as a reverse proxy/load balancer lack out-of-the-box per-backend traffic visibility in access logs, forcing manual LogFormat/env-var configuration or impractical per-container agent installs to monitor backend distribution. | 0.49 | PENDING | PENDING |
| cluster-21 | 2026-07-22 | [HN 25178752](https://news.ycombinator.com/item?id=25178752) | Ops teams managing large EC2 fleets lack a scalable, reliable third-party alternative to AWS Systems Manager for patch management and ad-hoc command execution. | 0.485 | PENDING | PENDING |
| cluster-9 | 2026-07-22 | [SF 1199132](https://serverfault.com/questions/1199132/how-can-a-mobile-client-access-nvrs-at-multiple-sites-through-a-single-wireguard) | IT admins managing self-hosted multi-site infrastructure (e.g., NVR surveillance networks) lack a packaged, easy-to-deploy VPN architecture/tooling that lets a single mobile connection reach multiple isolated sites simultaneously without adopting vendor cloud remote-access services like UniFi UI.com. | 0.475 | PENDING | PENDING |
| cluster-12 | 2026-07-22 | [SF 1198518](https://serverfault.com/questions/1198518/postgresql-how-restrict-database-creation) | DBAs running shared/multi-tenant PostgreSQL instances lack a way to grant application users limited, pattern-restricted database-creation rights, forcing manual pre-provisioning or custom gatekeeping scripts as a workaround. | 0.42 | PENDING | PENDING |
| cluster-20 | 2026-07-22 | [HN 42810252](https://news.ycombinator.com/item?id=42810252) | Google's domain-verification gap on legacy short domains like g.co lets attackers spin up seemingly-legitimate Workspace accounts and send convincing spoofed emails, creating an opening for adjacent email-security/anti-phishing vendors to add detection for look-alike Google-infrastructure sends since Google itself is unlikely to prioritize fixing legacy domain coverage. | 0.41 | PENDING | PENDING |
| cluster-14 | 2026-07-22 | [SF 1197895](https://serverfault.com/questions/1197895/in-macos-tahoe-and-sequoia-who-do-you-trigger-the-local-network-access-popup-fr) | System administrators managing macOS fleets lack a reliable way to detect, trigger, or programmatically grant the new Local Network Access permission for CLI-driven SSH tunnels and network tools, causing silent breakage of critical workflows. | 0.31 | PENDING | PENDING |
| cluster-15 | 2026-07-22 | [SF 1197831](https://serverfault.com/questions/1197831/block-ip-subnet-for-all-vhost) | Sysadmins running Apache reverse proxies lack clear tooling/guidance to enforce IP-level access control on ProxyPass-routed traffic, since standard Directory/Proxy ACL contexts silently don't apply there, leaving them exposed to floods until they discover the fix (Location/LocationMatch or iptables) after the fact. | 0.265 | PENDING | PENDING |
| cluster-7 | 2026-07-22 | [SF 1193110](https://serverfault.com/questions/1193110/mariadb-backup-hanging-set-global-innodb-log-checkpoint-now-on) | Database engineers and sysadmins running mariadb-backup against busy, high-write MariaDB production instances need a reliable backup/checkpoint mechanism that doesn't hang indefinitely at the innodb_log_checkpoint_now step. | 0.24 | PENDING | PENDING |
| cluster-1 | 2026-07-22 | [SE 282206](https://security.stackexchange.com/questions/282206/can-rcs-messages-have-a-spoofed-sender-id), [HN 31862994](https://news.ycombinator.com/item?id=31862994) | Businesses and individuals relying on SMS/RCS sender IDs for customer communication or authentication have no reliable third-party or carrier-backed way to prevent or detect sender-ID spoofing, leaving both phishing/smishing at scale and impersonation of legitimate short codes largely unaddressed. | 0.1 | PENDING | PENDING |
| cluster-4 | 2026-07-22 | [SE 287083](https://security.stackexchange.com/questions/287083/why-is-the-linux-sudo-model-non-compliant-with-cyber-essentials-account-separati), [SE 283238](https://security.stackexchange.com/questions/283238/security-risks-of-endpoint-agents) | Organizations pursuing Cyber Essentials/CE Plus certification on Linux face rigid, prescriptive controls (mandatory account-separation models, opaque root-privileged endpoint agents) that don't map to actual Linux security practice, forcing IT/security teams into compliance theater or unverifiable trust decisions. | 0.1 | PENDING | PENDING |
| cluster-10 | 2026-07-22 | [SF 1199054](https://serverfault.com/questions/1199054/least-privilege-setup-for-windows-exporter-and-wuaserv) | Sysadmins running Windows monitoring agents (e.g. windows_exporter) under least-privilege gMSA service accounts have no documented way to grant COM-API access to Windows Update history without granting full local admin rights. | 0.1 | PENDING | PENDING |
| cluster-13 | 2026-07-22 | [SF 1197939](https://serverfault.com/questions/1197939/digitalocean-droplet-compromised) | Small ops teams running self-managed Docker/cloud apps lack diagnostic tooling to pinpoint app/container/CI-CD-layer root causes of repeated server compromise once standard OS/network hardening has already been applied. | 0.1 | PENDING | PENDING |
| cluster-17 | 2026-07-22 | [HN 13329525](https://news.ycombinator.com/item?id=13329525) | Browser users have no protection against malicious pages that exploit browser autofill to silently harvest personal/payment data via hidden form fields, a longstanding unpatched cross-browser gap that leaves an opening for a third-party detection/blocking tool. | 0.1 | PENDING | PENDING |
| cluster-19 | 2026-07-22 | [HN 27192997](https://news.ycombinator.com/item?id=27192997) | Security-conscious users and IT teams have no reliable way to get malicious extensions impersonating trusted security products removed from official app/browser stores, since reporting mechanisms are ineffective and only the platform (e.g., Google) can act. | 0.1 | PENDING | PENDING |

Note: three of these (cluster-8, cluster-9, cluster-7 above) are the
off-mission ops/reliability clusters already flagged as a known scope gap in
`docs/progress.md` (DR/RTO rebuild, WireGuard multi-site VPN,
mariadb-backup hang) — worth deciding here too whether Decide should be
where that scope filter finally gets enforced (e.g. an automatic `discard`
for off-mission clusters regardless of score), since Sense/Discover
currently don't catch it.

## Definition of done for this stage

**Not yet defined** — draft once enough rows are hand-labeled to see
whether a clean threshold/floor rule (like `compute_overall_rank_score`'s)
actually falls out of real judgment calls, or whether `decide_action`
needs richer signal than the existing Discover-stage fields provide.
