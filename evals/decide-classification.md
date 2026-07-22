# Eval Set 3: Decide Classification (Decide Stage)

**Status: all 21 rows hand-labeled** by the human labeler on 2026-07-22
(4 `pursue`, 9 `watch`, 8 `discard`) — real `ScoredCluster` output from
`data/runs/2026-07-22/clusters.jsonl` (one full pipeline run), each with a
written rationale. See "Patterns observed" below for what the labeling
revealed about the draft rubric's open questions. `agents/decide_agent.py`
can now be built against this file.

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

**Patterns observed from the 21 labeled rows (read before building the
agent):**

- **Single-signal high score CAN be `pursue`.** cluster-16 (0.765, 1 signal)
  and cluster-5 (0.63, 1 signal) both got `pursue` — low
  `frequency_corroboration` alone did not force `watch`. `small_team_feasibility`
  and `willingness_to_pay_signal` being strong outweighed thin
  corroboration in both cases. Contrast cluster-18 (0.635, 1 signal, also
  strong feasibility/willingness) which got `watch` anyway — not for a
  corroboration reason but an explicit timing judgment ("not the right
  timing") outside anything Discover-stage scores capture.
- **No hard `overall_rank_score` floor forces `discard`.** All 6 rows at
  the 0.10 floor (`small_team_feasibility<=0.10`) split 3 `discard` /
  3 `watch` — the score alone doesn't separate them. What did: whether the
  blocker is a true platform-gatekeeper dead end ("have to be
  Microsoft/a carrier/the browser company to solve" → `discard`) versus a
  blocker the labeler judged could plausibly change or be worked around
  later ("look for feasibility to change, then evaluate again", "a
  compliance-related issue that could turn into a solution" → `watch`).
  This is a forward-looking judgment about whether the *reason* for low
  feasibility is durable or not — not something `small_team_feasibility`'s
  current tier system distinguishes.
- **`novelty` was never cited** as a driver in any of the 21 rationales.
  Willingness-to-pay and (at the floor) the durability of the feasibility
  blocker did the real work.
- **Off-mission scope pruning happened naturally at this stage.** All 3
  clusters flagged as off-mission ops/reliability noise in
  `docs/progress.md` (cluster-8 DR/RTO, cluster-9 WireGuard multi-site VPN,
  cluster-7 mariadb-backup hang) were labeled `discard` — explicitly "off-mission"
  each time. This suggests Decide-stage classification is in fact where that
  scope gap gets enforced, per the question raised when this file was
  scaffolded.

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
| cluster-16 | 2026-07-22 | [HN 35991269](https://news.ycombinator.com/item?id=35991269) | Small tech companies pursuing ITAR/CMMC and similar enterprise/government compliance frameworks lack a structured, developer-friendly methodology or tooling to map required controls to proportionate, BYOD/Mac-compatible implementations instead of defaulting to heavyweight Windows/AD/MDM stacks pushed by compliance leads and MSPs. | 0.765 | pursue | Clear compliance-mapping gap, strong willingness to pay. |
| cluster-3 | 2026-07-22 | [HN 32737886](https://news.ycombinator.com/item?id=32737886), [HN 30128872](https://news.ycombinator.com/item?id=30128872) | Open-source maintainers and downstream security teams need a reachability/exploitability-aware vulnerability scanner that filters CVE noise from lockfile-based tools like Dependabot/Snyk by verifying whether flagged vulnerable code paths are actually called, reducing wasted triage time and CVE disputes. | 0.65 | pursue | Clear technology gap. |
| cluster-18 | 2026-07-22 | [HN 21200914](https://news.ycombinator.com/item?id=21200914) | Banks and fintechs lack an adjacent tooling layer (e.g., vishing-call correlation/scoring or context-aware OTP messaging templates) to counter social-engineering attacks that exploit generic, purpose-less OTP/PIN reset SMS messages to trick customers into reading out codes. | 0.635 | watch | Not the right timing. |
| cluster-5 | 2026-07-22 | [SF 1198279](https://serverfault.com/questions/1198279/monitor-expiration-of-openssh-certificates-users-and-hosts) | Provide a lightweight monitoring/alerting tool that centrally tracks OpenSSH CA-issued host and user certificate expiration across fleets and automated service accounts, replacing fragile hand-rolled ssh-keyscan/ssh-keygen/awk scripts. | 0.63 | pursue | Clear path to productize an existing workaround. |
| cluster-2 | 2026-07-22 | [SE 286827](https://security.stackexchange.com/questions/286827/how-should-a-small-security-team-prioritize-cves-when-cvss-scores-dont-reflect), [HN 45997568](https://news.ycombinator.com/item?id=45997568) | Small security/engineering teams need an affordable tool that reprioritizes the flood of CVE/dependency alerts using real-world exploitability signals (CISA KEV, EPSS, contextual risk) instead of raw CVSS scores, to stop wasting patching effort on low-risk high-CVSS findings while actively-exploited vulnerabilities linger. | 0.56 | pursue | Clear path to productize KEV and EPSS in the context of this problem, and willingness to pay. |
| cluster-8 | 2026-07-22 | [SF 1190750](https://serverfault.com/questions/1190750/fast-server-restore-through-virtualization-container-os-on-single-dedicated-mach) | Solo sysadmins and small businesses running a single dedicated server lack an affordable, pre-tested disaster-recovery/rebuild playbook (backup format + restore automation + RTO validation) that doesn't require enterprise failover infrastructure. | 0.56 | discard | Off-mission. |
| cluster-11 | 2026-07-22 | [SF 1197794](https://serverfault.com/questions/1197794/how-can-i-bulk-rotate-renew-all-the-keys-of-all-my-resources-in-my-azure-subscri), [SF 1197698](https://serverfault.com/questions/1197698/how-can-one-disable-pause-an-azure-cognitive-services-resource-to-prevent-furthe), [SF 1197808](https://serverfault.com/questions/1197808/how-can-i-configure-azure-so-that-i-get-an-email-alert-when-someone-accesses-vie) | Azure admins managing Cognitive Services (and similar) resources at scale need a third-party tool to bulk-rotate keys, pause billing, and alert on key access — capabilities Azure's own portal/CLI don't natively provide. | 0.545 | watch | Azure most likely builds this themselves, evaporating the market overnight. |
| cluster-6 | 2026-07-22 | [SF 1193229](https://serverfault.com/questions/1193229/monitor-backend-of-httpds-load-balancer) | Sysadmins running Apache httpd as a reverse proxy/load balancer lack out-of-the-box per-backend traffic visibility in access logs, forcing manual LogFormat/env-var configuration or impractical per-container agent installs to monitor backend distribution. | 0.49 | watch | Low willingness to pay. |
| cluster-21 | 2026-07-22 | [HN 25178752](https://news.ycombinator.com/item?id=25178752) | Ops teams managing large EC2 fleets lack a scalable, reliable third-party alternative to AWS Systems Manager for patch management and ad-hoc command execution. | 0.485 | watch | Low willingness to pay and low frequency, but large market which could be eaten up by AWS Systems Manager improvements. |
| cluster-9 | 2026-07-22 | [SF 1199132](https://serverfault.com/questions/1199132/how-can-a-mobile-client-access-nvrs-at-multiple-sites-through-a-single-wireguard) | IT admins managing self-hosted multi-site infrastructure (e.g., NVR surveillance networks) lack a packaged, easy-to-deploy VPN architecture/tooling that lets a single mobile connection reach multiple isolated sites simultaneously without adopting vendor cloud remote-access services like UniFi UI.com. | 0.475 | discard | Off-mission. |
| cluster-12 | 2026-07-22 | [SF 1198518](https://serverfault.com/questions/1198518/postgresql-how-restrict-database-creation) | DBAs running shared/multi-tenant PostgreSQL instances lack a way to grant application users limited, pattern-restricted database-creation rights, forcing manual pre-provisioning or custom gatekeeping scripts as a workaround. | 0.42 | watch | Low feasibility, but higher willingness to pay suggests we don't throw it away. |
| cluster-20 | 2026-07-22 | [HN 42810252](https://news.ycombinator.com/item?id=42810252) | Google's domain-verification gap on legacy short domains like g.co lets attackers spin up seemingly-legitimate Workspace accounts and send convincing spoofed emails, creating an opening for adjacent email-security/anti-phishing vendors to add detection for look-alike Google-infrastructure sends since Google itself is unlikely to prioritize fixing legacy domain coverage. | 0.41 | discard | Basically have to be Google to fix this. |
| cluster-14 | 2026-07-22 | [SF 1197895](https://serverfault.com/questions/1197895/in-macos-tahoe-and-sequoia-who-do-you-trigger-the-local-network-access-popup-fr) | System administrators managing macOS fleets lack a reliable way to detect, trigger, or programmatically grant the new Local Network Access permission for CLI-driven SSH tunnels and network tools, causing silent breakage of critical workflows. | 0.31 | watch | Semi-handled by tools like Kandji; they're most likely to solve it as an extension of existing capabilities. |
| cluster-15 | 2026-07-22 | [SF 1197831](https://serverfault.com/questions/1197831/block-ip-subnet-for-all-vhost) | Sysadmins running Apache reverse proxies lack clear tooling/guidance to enforce IP-level access control on ProxyPass-routed traffic, since standard Directory/Proxy ACL contexts silently don't apply there, leaving them exposed to floods until they discover the fix (Location/LocationMatch or iptables) after the fact. | 0.265 | discard | Low signals across the board, especially frequency, willingness to pay, and novelty. |
| cluster-7 | 2026-07-22 | [SF 1193110](https://serverfault.com/questions/1193110/mariadb-backup-hanging-set-global-innodb-log-checkpoint-now-on) | Database engineers and sysadmins running mariadb-backup against busy, high-write MariaDB production instances need a reliable backup/checkpoint mechanism that doesn't hang indefinitely at the innodb_log_checkpoint_now step. | 0.24 | discard | Off-mission. |
| cluster-1 | 2026-07-22 | [SE 282206](https://security.stackexchange.com/questions/282206/can-rcs-messages-have-a-spoofed-sender-id), [HN 31862994](https://news.ycombinator.com/item?id=31862994) | Businesses and individuals relying on SMS/RCS sender IDs for customer communication or authentication have no reliable third-party or carrier-backed way to prevent or detect sender-ID spoofing, leaving both phishing/smishing at scale and impersonation of legitimate short codes largely unaddressed. | 0.1 | discard | Have to be a carrier to solve the problem. |
| cluster-4 | 2026-07-22 | [SE 287083](https://security.stackexchange.com/questions/287083/why-is-the-linux-sudo-model-non-compliant-with-cyber-essentials-account-separati), [SE 283238](https://security.stackexchange.com/questions/283238/security-risks-of-endpoint-agents) | Organizations pursuing Cyber Essentials/CE Plus certification on Linux face rigid, prescriptive controls (mandatory account-separation models, opaque root-privileged endpoint agents) that don't map to actual Linux security practice, forcing IT/security teams into compliance theater or unverifiable trust decisions. | 0.1 | watch | A compliance-related issue that could turn into a solution. |
| cluster-10 | 2026-07-22 | [SF 1199054](https://serverfault.com/questions/1199054/least-privilege-setup-for-windows-exporter-and-wuaserv) | Sysadmins running Windows monitoring agents (e.g. windows_exporter) under least-privilege gMSA service accounts have no documented way to grant COM-API access to Windows Update history without granting full local admin rights. | 0.1 | discard | Have to be Microsoft to solve. |
| cluster-13 | 2026-07-22 | [SF 1197939](https://serverfault.com/questions/1197939/digitalocean-droplet-compromised) | Small ops teams running self-managed Docker/cloud apps lack diagnostic tooling to pinpoint app/container/CI-CD-layer root causes of repeated server compromise once standard OS/network hardening has already been applied. | 0.1 | watch | Look for feasibility to change, then evaluate again. |
| cluster-17 | 2026-07-22 | [HN 13329525](https://news.ycombinator.com/item?id=13329525) | Browser users have no protection against malicious pages that exploit browser autofill to silently harvest personal/payment data via hidden form fields, a longstanding unpatched cross-browser gap that leaves an opening for a third-party detection/blocking tool. | 0.1 | watch | Feasibility will change if this becomes a browser addon problem, but willingness to pay likely not to move. |
| cluster-19 | 2026-07-22 | [HN 27192997](https://news.ycombinator.com/item?id=27192997) | Security-conscious users and IT teams have no reliable way to get malicious extensions impersonating trusted security products removed from official app/browser stores, since reporting mechanisms are ineffective and only the platform (e.g., Google) can act. | 0.1 | discard | Have to be the browser company to solve. |

Note: three of these (cluster-8, cluster-9, cluster-7 above) are the
off-mission ops/reliability clusters already flagged as a known scope gap in
`docs/progress.md` (DR/RTO rebuild, WireGuard multi-site VPN,
mariadb-backup hang) — worth deciding here too whether Decide should be
where that scope filter finally gets enforced (e.g. an automatic `discard`
for off-mission clusters regardless of score), since Sense/Discover
currently don't catch it.

## Definition of done for this stage

The "Patterns observed" section above answers the question this section
used to leave open: a pure threshold/floor rule over existing
Discover-stage fields does **not** cleanly fall out of the 21 real
labels — the floor group split 3/3 on a judgment (is the feasibility
blocker durable or not?) that no existing field encodes. So
`agents/decide_agent.py` likely needs an LLM-as-judge approach reading the
full context (`opportunity_statement`, rationale-worthy detail from the
signals, plus the numeric sub-scores) rather than a formula — closer to how
`small_team_feasibility_tier`/`willingness_to_pay_signal_tier` work in
`discover_agent.py` than to `compute_overall_rank_score`.

**Status: MET, 2026-07-22.** `agents/decide_agent.py` (LLM-as-judge, see its
docstring) scored **19/21 (90.5%)** exact-match on `evals/run_decide_eval.py`
against these rows, after two tuning passes (71.4% → 85.7% → 90.5%). Both
remaining mismatches read as genuine boundary calls, not bugs: cluster-18 is
the documented "not the right timing" outlier with no textual basis
anywhere in the score profile (an accepted, permanent limitation — see the
agent's docstring); cluster-3 is a defensible disagreement using the same
rule that correctly fixed three other rows, just landing on the more
conservative side of a close call. Off-mission scope pruning
(cluster-7/8/9 → `discard`) held correctly across all three eval runs, in
the agent's own stated reasoning each time, not by coincidence.

Same caveat as `evals/opportunity-scoring.md`: only 21 rows from one
pipeline run, no held-out set — a second, later pipeline run's output
would be a better real test than re-splitting these same 21.
