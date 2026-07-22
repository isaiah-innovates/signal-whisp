# Eval Set 2: Opportunity Scoring (Discover Stage)

**Status:** All 16 real candidate clusters hand-scored. Rows below are built from real clustered output —
`agents/run_discover_pipeline.py` pulled 187 real posts (Stack Exchange
`security`/`serverfault` tags + Hacker News relevance search, 365-day
window), ran them through the working Sense-stage agent
(`agents/sense_agent.py`), and clustered the 25 resulting signals into 19
candidate opportunities via `agents/discover_agent.py`. 3 clusters
(mariadb-backup hang, single-server DR/RTO, WireGuard multi-site mobile VPN
access) were pruned as off-mission ops/reliability noise with no
cybersecurity angle — see conversation history for the human labeler's
reasoning. The remaining 16 clusters (22 signals) are the real candidate
pool this file scores from. Each row's `overall_rank_score` and the judgment
fields feeding it (`signal_validity`, `extraction_accuracy`,
`small_team_feasibility`, `willingness_to_pay_signal`, `novelty`) are
hand-scored by the human labeler per the rubric below — none are model
output. `frequency_corroboration` is derived programmatically per-row (see
formula below) rather than hand-scored, since the rubric assigns it to a
programmatic method.

**frequency_corroboration formula:** `volume_score = min(1.0, num_signals / 4)`;
`source_diversity = 1.0 if >=2 distinct sources else 0.4`;
`frequency_corroboration = average(volume_score, source_diversity)`.

**Feature under test:** the agent that takes a cluster of related signals
(same underlying pain point, corroborated across multiple posts/sources/days)
and decides whether it's a genuinely viable small-team opportunity, producing a
ranked score.

## Target schema

```json
{
  "cluster_id": "string",
  "signal_ids": ["permalink", "..."],
  "opportunity_statement": "string",
  "signal_validity": 0.0-1.0,
  "extraction_accuracy": 0.0-1.0,
  "frequency_corroboration": 0.0-1.0,
  "small_team_feasibility": 0.0-1.0,
  "willingness_to_pay_signal": 0.0-1.0,
  "novelty": "human_review_pending" | 0.0-1.0,
  "overall_rank_score": 0.0-1.0
}
```

## Rubric

| Dimension | What it checks | Method |
|---|---|---|
| Signal validity | Real pain vs. noise/venting, inherited from Sense-stage labels | LLM-as-judge, calibrated to hand-labels |
| Extraction accuracy | Correct problem/workaround/audience carried through from Sense stage | Exact/semantic match |
| Frequency / corroboration | Independent posts/sources confirming the same pain | Programmatic (dedup + cluster count across sources) |
| Small-team feasibility | Buildable by 1–3 people without deep compliance overhead (e.g. no FedRAMP-class requirement) | LLM-as-judge, explicit written rubric — write out concrete yes/no examples once real clusters exist |
| Willingness-to-pay signal | Budget language ("we pay for X and it still doesn't Y") vs. hobbyist/free-tool grumbling | LLM-as-judge |
| Novelty | Underserved vs. crowded/already-well-solved category | Human review — named "eyes" column, not automated. Don't let an LLM self-certify novelty. |

## Building this eval set (once Sense stage is ready)

1. Run the working extraction agent across a real batch of posts (mixed
   sources, at least a week's worth if possible).
2. Cluster related signals manually or with a first-pass clustering script.
3. For each cluster, hand-write the `overall_rank_score` you'd personally give
   it and why — this is the actual PM judgment call this eval exists to
   capture. Include at least a few clusters you'd rank low despite high
   frequency (e.g. a crowded, already-well-solved category) so the eval tests
   novelty discrimination, not just corroboration counting.
4. Add adversarial cases once real data surfaces them — e.g. a cluster that
   looks corroborated but is actually the same person posting in multiple
   places, or a high-frequency complaint about something outside a small
   team's realistic reach (e.g. requires an enterprise compliance
   certification to sell into).

## Rows

All 16 real clusters scored. `signal_ids` link to the underlying
Sense-stage eval permalinks; `opportunity_statement` is drafted from the
cluster's `shared_pain_statement` (produced by `agents/discover_agent.py`)
and accepted as-is by the human labeler unless noted.

| cluster_id | signal_ids | opportunity_statement | signal_validity | extraction_accuracy | frequency_corroboration | small_team_feasibility | willingness_to_pay_signal | novelty | overall_rank_score | rationale |
|---|---|---|---|---|---|---|---|---|---|---|
| cluster-2 | [SE 286827](https://security.stackexchange.com/questions/286827/how-should-a-small-security-team-prioritize-cves-when-cvss-scores-dont-reflect), [HN 32737886](https://news.ycombinator.com/item?id=32737886), [HN 30128872](https://news.ycombinator.com/item?id=30128872), [HN 45997568](https://news.ycombinator.com/item?id=45997568) | Small security teams and OSS maintainers waste triage effort because CVSS/vulnerability scanners flag issues without real-world exploitability context, forcing manual sifting of CVE and dependency-update noise. | 0.65 | 0.9 | 1.0 | 0.7 | 0.6 | 0.2 | 0.75 | Highest-corroboration cluster in the batch (4 independent posts, 2 sources, genuinely distinct contexts). small_team_feasibility=0.7: readily available data (KEV/EPSS feeds) and solid partial solutions already exist to build on. willingness_to_pay=0.6: the problem space is already worth several billion dollars. novelty=0.2: established market and problem set — low novelty is the deliberate counterweight to high frequency/feasibility. overall=0.75: high pain + willingness to pay + small-team-buildable outweighs low novelty. |
| cluster-1 | [SE 282206](https://security.stackexchange.com/questions/282206/can-rcs-messages-have-a-spoofed-sender-id), [HN 31862994](https://news.ycombinator.com/item?id=31862994) | Businesses and consumers have no technical or regulatory way to stop SMS/RCS sender-ID spoofing, leaving smishing/impersonation attacks effectively unblockable. | 0.5 | 0.8 | 0.75 | 0.1 | 0.1 | 0.9 | 0.2 | Real but thinner corroboration than cluster-2 (one business-specific RCS question, one general SMS complaint — same gap, different angles). small_team_feasibility=0.1: the actual fix lives with carriers/regulators, outside a small team's reach. willingness_to_pay=0.1: no budget language in either source. novelty=0.9: genuinely niche, would need novel infrastructure-level approaches to solve at scale. overall=0.2: floored by small_team_feasibility regardless of high novelty. |
| cluster-10 | [SF 1197794](https://serverfault.com/questions/1197794/how-can-i-bulk-rotate-renew-all-the-keys-of-all-my-resources-in-my-azure-subscri), [SF 1197698](https://serverfault.com/questions/1197698/how-can-one-disable-pause-an-azure-cognitive-services-resource-to-prevent-furthe), [SF 1197808](https://serverfault.com/questions/1197808/how-can-i-configure-azure-so-that-i-get-an-email-alert-when-someone-accesses-vie) | Azure admins have no native lifecycle-management controls for Cognitive Services resources — bulk key rotation, pause/disable billing, or key-access alerting — forcing manual CLI workarounds. | 0.45 | 0.75 | 0.58 | 0.3 | 0.4 | 0.3 | 0.4 | signal_validity=0.45: concrete real complaints, but this reads more as a cloud-ops/feature-gap pain than a cybersecurity pain specifically (only 2 of 3 sub-asks — key rotation, access alerting — lean security; billing pause doesn't). All 3 signals are same-source (serverfault), so frequency_corroboration=0.58 correctly ranks it below cluster-1 despite more raw signals. small_team_feasibility=0.3: genuinely unclear whether this is buildable by a small team without deep Azure platform access. willingness_to_pay=0.4: plausible that enterprises pay for cloud cost/key management tooling, but no direct budget language in-post. novelty=0.3: known problem/solution space (cloud governance tooling) applied to a specific platform. overall=0.4: dragged down by low small_team_feasibility and moderate novelty. |
| cluster-3 | [SE 287083](https://security.stackexchange.com/questions/287083/why-is-the-linux-sudo-model-non-compliant-with-cyber-essentials-account-separati) | Organizations pursuing Cyber Essentials certification with Linux infrastructure have no clear, security-equivalent way to satisfy the Windows-centric admin/user account-separation requirement, forcing superficial compliance workarounds that weaken audit trails. | 0.55 | 0.85 | 0.325 | 0.1 | 0.6 | 0.3 | 0.1 | small_team_feasibility=0.1: OS-level compliance-workaround problems aren't small-team-buildable products. willingness_to_pay=0.6: acute compliance pain drives real dollar spend. novelty=0.3: known problem with known (if imperfect) workarounds. overall=0.1: feasibility floor applied uniformly with clusters 1/4/9/12/18 (feasibility ~0.1) — willingness-to-pay alone doesn't overcome an unbuildable-by-a-small-team floor, and novelty isn't high enough here to earn the partial bump cluster-1/12 got. |
| cluster-4 | [SE 283238](https://security.stackexchange.com/questions/283238/security-risks-of-endpoint-agents) | Organizations pursuing Cyber Essentials Plus certification are required to install closed-source, root-privileged third-party endpoint agents with no way to vet them or opt out, creating unavoidable supply-chain trust risk. | 0.4 | 0.85 | 0.325 | 0.1 | 0.1 | 0.2 | 0.1 | small_team_feasibility=0.1: this is a regulatory problem, outside a small team's reach to fix. willingness_to_pay=0.1: no willingness-to-pay signal observed. novelty=0.2: mostly complaining about having to do something everyone ought to be doing for good security practice — low novelty. overall=0.1: nothing here for a small team to build; feasibility floor with no bump since novelty is also low. |
| cluster-5 | [SF 1198279](https://serverfault.com/questions/1198279/monitor-expiration-of-openssh-certificates-users-and-hosts) | Admins managing OpenSSH CA-issued certificates have no built-in or standard tooling to centrally track and alert on upcoming host/user certificate expiration, forcing fragile hand-built parsing scripts. | 0.55 | 0.85 | 0.325 | 0.6 | 0.6 | 0.5 | 0.6 | small_team_feasibility=0.6: a small team could build a solution that lives alongside existing OpenSSH cert management. willingness_to_pay=0.6: the poster is already willing to spend time/effort on a fragile workaround — a proxy for willingness to pay for a real fix. novelty=0.5: well-known problem space (cert lifecycle monitoring) applied to a specific niche. overall=0.6: willingness-to-spend drives this score above the midpoint. |
| cluster-9 | [SF 1199054](https://serverfault.com/questions/1199054/least-privilege-setup-for-windows-exporter-and-wuaserv) | There is no documented way to grant a least-privilege service account read-only access to Windows Update history, forcing admins to over-provision admin rights just for monitoring. | 0.4 | 0.8 | 0.325 | 0.1 | 0.1 | 0.3 | 0.1 | small_team_feasibility=0.1: OS-level problem, not small-team-buildable. willingness_to_pay=0.1: no signal. novelty=0.3: known problem with known workarounds. overall=0.1: low signal across the board; feasibility floor applied uniformly with clusters 1/3/4/12/18, no bump since novelty isn't high. |
| cluster-11 | [SF 1198518](https://serverfault.com/questions/1198518/postgresql-how-restrict-database-creation) | PostgreSQL's all-or-nothing CREATEDB privilege gives DBAs no native way to scope database-creation rights to a naming pattern for shared multi-tenant instances. | 0.5 | 0.85 | 0.325 | 0.2 | 0.4 | 0.5 | 0.4 | small_team_feasibility=0.2: a DB-level privilege-model problem, harder for a small team to own on its own. willingness_to_pay=0.4: EDB and similar already exist to solve adjacent problems, signaling some real willingness to pay. novelty=0.5: well-known problem space. overall=0.4: willingness-to-pay is the main driver given low feasibility. |
| cluster-12 | [SF 1197939](https://serverfault.com/questions/1197939/digitalocean-droplet-compromised) | Operators lack tooling to pinpoint how a compromise re-enters a freshly rebuilt server/container stack when the root cause is at the app/CI-CD/Docker layer rather than OS/SSH. | 0.55 | 0.85 | 0.325 | 0.1 | 0.6 | 0.7 | 0.2 | small_team_feasibility=0.1: hard for a small team to get access to this class of problem — needs real incident-response engagements to build/validate against. willingness_to_pay=0.6 (revised from an initial 0.3 — incident response is actually one of the more reliably-funded corners of security spend, not unfunded as first assumed). novelty=0.7: IR is a genuinely underserved/novel diagnostic space at this specific layer. overall=0.2: feasibility floor applied uniformly with clusters 1/3/4/9/18 — high novelty earns the same partial bump cluster-1 got (0.1→0.2). |
| cluster-13 | [SF 1197895](https://serverfault.com/questions/1197895/in-macos-tahoe-and-sequoia-who-do-you-trigger-the-local-network-access-popup-fr) | macOS's new Local Network Access permission system silently breaks CLI-driven SSH tunnels and local network tools without ever prompting for permission, leaving no way to grant access from the command line. | 0.45 | 0.85 | 0.325 | 0.4 | 0.2 | 0.5 | 0.3 | small_team_feasibility=0.4: more approachable for a small team than most clusters in this batch. willingness_to_pay=0.2: businesses don't pay for macOS SSH permission quirks — no market signal. novelty=0.5: working around a new OS permission change is somewhat novel. overall=0.3: willingness-to-pay drives the score down despite moderate feasibility/novelty. |
| cluster-14 | [SF 1197831](https://serverfault.com/questions/1197831/block-ip-subnet-for-all-vhost) | Standard Apache `<Proxy>`/`<Directory>` ACL directives silently fail to block malicious traffic on ProxyPass-routed reverse-proxy paths, letting abusive IP subnets crash the server. | 0.3 | 0.8 | 0.325 | 0.2 | 0.2 | 0.2 | 0.2 | small_team_feasibility=0.2: would require significant DDoS-relevant data/infra to solve well. willingness_to_pay=0.2: an established incumbent (Red Hat) already solves adjacent Apache problems. novelty=0.2: network security config space is rarely novel. overall=0.2: if the incumbent isn't already solving it, it's probably not worth solving — all dimensions converge low. |
| cluster-15 | [HN 35991269](https://news.ycombinator.com/item?id=35991269) | Small companies pursuing regulated-sector compliance (ITAR/CMMC) lack a structured way to map framework requirements to proportionate, developer-friendly controls, and instead face pressure to adopt heavy-handed one-size-fits-all endpoint management. | 0.55 | 0.85 | 0.325 | 0.7 | 0.9 | 0.3 | 0.6 | small_team_feasibility=0.7: small teams have real access to these frameworks and controls. willingness_to_pay=0.9: GRC is an established market that reliably drives budget. novelty=0.3: known problem/solution space (compliance mapping tooling). overall=0.6: approachable, open-source-able solution space with strong willingness-to-pay outweighs the low novelty. |
| cluster-16 | [HN 13329525](https://news.ycombinator.com/item?id=13329525) | Browser autofill can be exploited by malicious sites to silently harvest hidden/off-screen form fields, and mainstream browsers have failed to fix this known issue for over a year. | 0.5 | 0.85 | 0.325 | 0.1 | 0.1 | 0.1 | 0.1 | small_team_feasibility=0.1: a browser-vendor bug isn't approachable for a small team to fix. willingness_to_pay=0.1: enterprises don't pay third parties for browser bugs/fixes. novelty=0.1: this class of autofill bug shows up regularly — not novel. overall=0.1: not an approachable problem for a small team regardless of other scores. |
| cluster-17 | [HN 21200914](https://news.ycombinator.com/item?id=21200914) | Generic wording in bank OTP/password-reset SMS messages fails to signal their specific purpose, enabling vishing attacks that trick customers into reading codes to fraudsters during account-recovery social engineering. | 0.5 | 0.85 | 0.325 | 0.5 | 0.8 | 0.4 | 0.65 | small_team_feasibility=0.5: a small team could plausibly build a bank-OTP-wording/vishing-mitigation product. willingness_to_pay=0.8: banks all but have to pay for these systems. novelty=0.4: SMS/vishing space is well known. overall=0.65: approachable problem with widespread pain and strong willingness-to-pay, tempered by the compliance/security bar a small team would need to clear to sell into banks. |
| cluster-18 | [HN 27192997](https://news.ycombinator.com/item?id=27192997) | Malicious extensions impersonating security products remain listed in the Chrome Web Store despite repeated user reports, with no effective, timely takedown mechanism from Google. | 0.6 | 0.85 | 0.325 | 0.0 | 0.1 | 0.2 | 0.1 | small_team_feasibility=0.0: literally only solvable by Chrome/Google itself. willingness_to_pay=0.1: businesses don't pay third parties for Chrome Web Store moderation. novelty=0.2: well-known problem space, known not to have solutions outside Chrome's control. overall=0.1: not approachable regardless of other scores. |
| cluster-19 | [HN 42810252](https://news.ycombinator.com/item?id=42810252) | Google's domain verification and anti-spoofing protections fail to cover g.co subdomains, letting attackers send convincing phishing emails that abuse trust in Google's own infrastructure. | 0.45 | 0.85 | 0.325 | 0.2 | 0.6 | 0.8 | 0.3 | small_team_feasibility=0.2: email-gateway-adjacent problems are slightly approachable for a small team. willingness_to_pay=0.6: businesses pay for email security, though they'd expect this specific gap to already be fixed by an existing solution. novelty=0.8: the niche nature of the solution space makes it genuinely novel. overall=0.3: feasibility keeps the score low regardless of the money/novelty upside. |

All 16 real clusters are now scored.

## Definition of done for this stage

Scoring is "ready" when the agent's `overall_rank_score` ordering on a
held-out set roughly agrees with your own manual ranking of the same clusters.
Disagreements become new eval rows with a written rationale, not a debate.
