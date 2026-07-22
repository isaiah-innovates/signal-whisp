# Eval Set 1: Signal Extraction (Sense Stage)

**Feature under test:** the agent that reads a normalized post (from any source
— Stack Exchange, Hacker News, eventually Reddit) and decides (a) whether it
contains a genuine cybersecurity pain point, and (b) if so, extracts it into
structured fields.

**Status:** IN PROGRESS — real, hand-labeled rows from live Stack Exchange and
Hacker News pulls, replacing the original synthetic placeholders. Currently
**21 signal rows**, within the ~20-25 target range. Two gaps below were
deliberately accepted rather than closed — see "Known gaps." Do not start
building `sense_agent.py` against this file until the human labeler confirms
it's ready to build against as-is.

**Known gaps (accepted, not closed — revisit in a future labeling pass if
these themes turn out to matter more than expected once Discover-stage
clustering is running):**
- **MSP theme is thin** — only 1 solid signal row (row 7). Several close
  calls (password vaults for MSPs, vendor over-permissioning trust, MDR/MSSP
  buying decisions, MSP billing/RMM/PSA tooling) were tried across multiple
  pulls and either rejected for weak/no corroboration or didn't surface at
  all — HN's Ask HN search in particular returned almost nothing relevant
  for MSP-specific terms (RMM, PSA, co-managed IT). Reddit's r/msp via
  Arctic Shift (see `docs/data-sources.md`) was identified as a likely
  better source for this theme but not pursued this round.
- **Phishing theme is thin** — 2 signal rows (8, 21), both weak/unconfirmed,
  plus the adjacent spam-filter cluster (row 18).
- **Adversarial case 14 (below) has no real example.** Two candidates were
  found across multiple pulls (an incoherent buzzword-heavy pitch, and a
  raw-creation-stream pull aimed specifically at surfacing ambiguous/ESL
  posts) but neither was usable — the human labeler rejected the first, and
  the second pull mostly surfaced coherent-but-jargon-dense technical
  questions rather than genuinely ambiguous ones. Cases 9, 10, 11, 12, and 13
  all have real examples. Do not fabricate a case-14 example.

---

## 1. Target schema (what extraction must output per post)

```json
{
  "permalink": "string",
  "source": "stackexchange | hackernews | reddit",
  "is_signal": true | false,
  "problem_statement": "string | null",
  "affected_role": "string | null",
  "current_workaround": "string | null",
  "workaround_type": "manual" | "ai_tool_hack" | "none" | null,
  "corroboration_signal": "string | null",
  "confidence": 0.0-1.0
}
```

## 2. Labeling criteria (what "good" means)

- **is_signal = true** requires: a specific, recurring problem (not a one-off
  complaint), stated by someone who actually does the work (not a student,
  recruiter, or vendor), with enough detail to know what "solved" would look
  like.
- **is_signal = false** covers: career/certification/homework questions,
  venting with no specific problem, vendor/marketing posts disguised as
  questions, pure news-sharing with no personal pain attached.
- `problem_statement` should read like a sentence a PM could hand to an
  engineer — not a paraphrase of the title.
- `confidence` is *your* labeled confidence as the ground-truth annotator, not
  a stand-in for the model's later score.
- Weight source when labeling `corroboration_signal`: a Stack Exchange accepted
  or highly-voted answer is stronger corroboration than an HN comment agreeing
  in passing. Annotator domain expertise can also serve as corroboration when
  a post's own replies are thin or absent — note explicitly when this is the
  basis, since it isn't source-native evidence (see row 11 below).

## 3. Signal rows (real, hand-labeled)

| # | permalink | source | is_signal | problem_statement | affected_role | current_workaround | workaround_type | corroboration_signal | confidence |
|---|---|---|---|---|---|---|---|---|---|
| 1 | [security.se/210949](https://security.stackexchange.com/questions/210949/windows-kerberos-pre-auth-failed-4771) | stackexchange | true | Security teams relying on Windows event ID 4771 (Kerberos pre-auth failure) for attack detection can't distinguish real credential-attack attempts from routine stale-password/expired-password noise, without ingesting logs from every endpoint. | SOC/security analyst monitoring Windows Active Directory environments | Abandoned 4771/4625 event correlation entirely; switched to alerting on account-lockout events with X-lockouts-in-Y-hours correlation rules instead | manual | Top answer confirms 4771 is commonly noisy due to password expiry; a second independent answer describes having made the same workaround switch | 0.7 |
| 2 | [security.se/286827](https://security.stackexchange.com/questions/286827/how-should-a-small-security-team-prioritize-cves-when-cvss-scores-dont-reflect) | stackexchange | true | Small security teams triaging hundreds of monthly vulnerability-scanner findings can't afford commercial threat-intel feeds, so CVSS-only prioritization wastes patching effort on high-CVSS-but-unexploited CVEs while actively-exploited medium-CVSS CVEs (per CISA KEV) get delayed. | 3-person IT security team managing ~200 servers/endpoints | Prioritizing strictly by raw CVSS score, with no supplementary exploit-probability data | manual | No direct replies on the post itself, but corroborated by market reality: CVSS-vs-exploitability triage has an entire vendor category built around it (risk-based vulnerability management — e.g. Tenable VPR, Vulcan Cyber, Nucleus Security), and affects large teams as well as small ones, not just resource-constrained shops. Annotator domain knowledge, not post-native evidence. | 0.9 |
| 3 | [security.se/277153](https://security.stackexchange.com/questions/277153/how-to-manage-a-lot-of-vulnerability-scanners-from-cicd-pipelines) | stackexchange | true | Small dev shops running multiple vulnerability scanners (Trivy, npm audit, SAST, etc.) across many client projects in CI/CD have no unified way to track findings, so vulnerabilities accumulate unnoticed on projects that go quiet, especially since remediation isn't prioritized unless tied to a user story. | Developer/security-adjacent engineer at a small software consultancy serving multiple clients | None stated — scanners run independently per project/stage with no aggregation; reliance on user-story-driven backlog for prioritization | none | No answers at time of pull — no corroboration available; flag as unconfirmed | 0.6 |
| 4 | [security.se/254962](https://security.stackexchange.com/questions/254962/how-to-manage-my-vulnerability-scan-reports-efficiently) | stackexchange | true | Companies running several disconnected vulnerability-scanning tools (network, SCA, SAST, DAST) have no consolidated way to produce audit/executive-ready evidence of scanning efficiency, and resort to manually filing reports into shared-drive folders by period. | Security/compliance-adjacent staff responsible for audit evidence at a company serving enterprise clients | Manually storing periodic scan reports in Google Drive folders organized by tool/period | manual | Two replies present but low-quality: one generic process-documentation suggestion, one appears to misread the question as being about test-automation frameworks rather than report management — weak corroboration, not independent confirmation | 0.5 |
| 5 | [security.se/261591](https://security.stackexchange.com/questions/261591/is-there-a-way-to-check-if-vulnerability-introduced-by-npm-package-is-reachable) | stackexchange | true | Teams triaging hundreds of npm-dependency vulnerabilities across many repositories can't get proof that a flagged vulnerability is actually reachable/exploitable in their code, which engineering requires before they'll prioritize patching. | Security engineer managing vulnerability findings across a large multi-repo codebase | Manually prioritizing by severity score alone, absent reachability data; aware of but not fully satisfied with Snyk's `--reachable` feature | manual | Answer engages directly with the reachability-analysis problem and confirms it's not practical to definitively prove exploitability in most vulnerability-management programs | 0.75 |
| 6 | [security.se/278858](https://security.stackexchange.com/questions/278858/logging-strategy-high-costs-for-storing-all-logs) | stackexchange | true | Organizations generating high-volume firewall/security logs (e.g. GCP/Kubernetes) face high storage costs to retain logs long enough for attack detection, despite the logs rarely being used for troubleshooting, and lack a clear strategy to cut costs without losing detection capability. | Security/infra engineer responsible for log retention and cost in a cloud-native (GCP/K8s) environment | Storing all logs at full retention by default; no tiering or filtering strategy yet in place | manual | Two substantive answers engage with the actual tradeoff — one recommends splitting operational vs. auditable log types, the other recommends cold/archive storage tiers and filtering | 0.7 |
| 7 | [HN 47333997](https://news.ycombinator.com/item?id=47333997) | hackernews | true | Software/service agencies supporting many clients end up with each engineer juggling 20+ separate client VPNs from incompatible vendors, with no unified way to manage credentials, versions, and expirations across them. | Developer/engineer at a software services agency doing maintenance across multiple client environments | Manually managing many individual VPN client installs and credentials per developer, per client | manual | No replies at time of pull — no corroboration available; flag as unconfirmed, though this closely matches the MSP-tooling-fragmentation pain this project specifically targets | 0.65 |
| 8 | [HN 31835519](https://news.ycombinator.com/item?id=31835519) | hackernews | true | Individual users hit by a sudden, sustained wave of phishing/spam email find that reporting messages as phishing doesn't stop the campaign, as spammers appear to adapt their templates/sending patterns faster than the filter's crowdsourced detection can catch up. | Individual email user (non-enterprise) experiencing a personal phishing/spam surge | Manually reporting each phishing email as spam/phishing; also relying on Gmail's automatic delayed detection | manual | A reply independently confirms the same experience and separately notes spam filters producing false positives on legitimate password-reset emails | 0.55 |
| 9 | [HN 36898968](https://news.ycombinator.com/item?id=36898968) (duplicate: [HN 36979698](https://news.ycombinator.com/item?id=36979698)) | hackernews | true | Despite mature tools like Dependabot, practitioners find open-source vulnerability management still fails on code-smell-style issues, build-time-only vulnerabilities, and judging when an upgrade is safe versus risky to apply. | Developer/security-adjacent engineer evaluating why existing OSS vulnerability tooling falls short | Using Dependabot-class tools for baseline coverage, with no solution for the named gaps | none | Same question posted twice by the same author seeking more responses; each thread drew an independent, substantive answer naming different specific gaps — the second post is a duplicate per adversarial case #12, not a second independent signal | 0.6 |
| 10 | [security.se/24195](https://security.stackexchange.com/questions/24195/how-do-you-explain-the-necessity-of-nuke-it-from-orbit-to-management-and-users) | stackexchange | true | Security practitioners struggle to get management/user buy-in for full wipe-and-rebuild after a malware infection, since stakeholders default to wanting to keep using the machine without understanding the cost of leaving a compromised system in place. | Security practitioner responsible for incident remediation who must justify the decision to non-technical management/users | Ad hoc persuasion tactics — framing risk in dollar/hour cost-to-business terms, avoiding technical analogies, presenting tabular risk/cost/option breakdowns | manual | Very high engagement (score 167, 10 answers) with multiple independent, concrete strategies for making this case to management | 0.75 |
| 11 | [security.se/230888](https://security.stackexchange.com/questions/230888/third-party-risk-management-validating-responses-from-vendors) | stackexchange | true | Companies building a third-party/vendor risk management process lack a standard way to validate vendor security questionnaire responses, and have to design their own ad hoc tiering scheme. | Risk/security professional designing a 3PRM process, e.g. at a financial services company | Manually designing a custom tiering system with no standard framework or tool to lean on | manual | Only one reply, fairly generic and not strongly validating — but annotator (SME) confirms from direct domain knowledge that standardized, trustworthy vendor-questionnaire validation remains a genuinely unsolved industry problem, not just this poster's gap. Annotator domain knowledge, not post-native evidence. | 0.8 |
| 12 | [security.se/214562](https://security.stackexchange.com/questions/214562/how-can-one-centrally-manage-audit-aws-resource-based-policies) | stackexchange | true | Cloud security teams that let users self-serve AWS resources (S3, SQS, KMS) with attached resource-based IAM policies have no built-in way to find and audit all such policies in bulk to check compliance with internal standards. | Cloud/security administrator responsible for AWS account governance | Manually cross-referencing AWS's list of resource-policy-supporting services, or restricting the underlying API calls non-admins can use as a preventive stopgap | manual | Two substantive answers propose different partial fixes (AWS Config compliance rules vs. API-call restriction plus a structured request interface), indicating no single tool fully solves this yet | 0.65 |
| 13 | [serverfault/1198279](https://serverfault.com/questions/1198279/monitor-expiration-of-openssh-certificates-users-and-hosts) | stackexchange | true | Teams using OpenSSH certificates for host/user auth have no built-in way to proactively monitor certificate expiration before it causes login failures or outages, forcing manual scripted checks against each host. | Sysadmin/infra engineer managing SSH certificate-based authentication | Self-built partial script using `ssh-keyscan` piped through `ssh-keygen`/`awk` to extract and check expiration per host manually | manual | Poster found and shared their own partial workaround after determining no complete existing solution covers this — self-corroborating, not independently confirmed by a second party | 0.55 |
| 14 | [security.se/211879](https://security.stackexchange.com/questions/211879/centralized-brute-force-login-detection-using-netflow-data) | stackexchange | true | Ops teams protecting hundreds of Linux hosts want a centralized way to detect brute-force login attempts, but netflow data lacks payload and login-success/failure detail, making it only a coarse, unreliable detection method with no clean full-fidelity alternative discussed. | Sysadmin/security engineer responsible for centralized auth-attack detection across a large Linux fleet | Attempting to infer brute-force attempts from packet-count thresholds per destination port in netflow data | manual | Two independent answers confirm the same limitation — netflow can only detect unusually high connection volume, not distinguish real brute-force from normal traffic | 0.65 |
| 15 | [security.se/278306](https://security.stackexchange.com/questions/278306/basic-monitoring-of-web-applications-http-headers-hsts) | stackexchange | true | Teams want to continuously verify security-relevant HTTP response headers (CSP, HSTS) and TLS cipher compliance across AWS-hosted web apps/APIs, but AWS Security Hub's built-in checks don't support the needed customization, leaving no off-the-shelf tool for this specific monitoring need. | Security/cloud engineer responsible for web app security posture on AWS | Proposed to build a custom solution (ALB + Lambda inspecting headers on each request) since no existing tool fits | manual | Answer confirms there's no ready-made tool and walks through the custom build path as the practical option | 0.6 |
| 16 | [HN 45647577](https://news.ycombinator.com/item?id=45647577) | hackernews | true | Developers responsible for on-call/infra monitoring lose significant time investigating alerts (e.g. "High CPU" pages) that turn out to be transient, non-actionable noise rather than real issues, and lack confidence that better alert design is achievable. | Solo/small-team developer handling ops and on-call responsibilities without dedicated SRE support | Manually investigating each alert (digging through logs/dashboards) with no filtering or tuning strategy in place | manual | High engagement (22 score, 40 replies), with top replies directly validating the pain ("useful alerts are a devilishly hard problem," "you're not wrong") | 0.75 |
| 17 | [security.se/10799](https://security.stackexchange.com/questions/10799/what-to-consider-in-an-sla-to-ensure-secure-software-when-outsourcing-software-d) | stackexchange | true | Companies outsourcing software development to offshore/third-party teams lack a standard template for what security terms to write into the SLA/contract (audit rights, testing requirements, security ownership), and have to piece this together from scratch. | Security/engineering lead responsible for vetting an offshore development contract | Searching for informal reference articles and asking peers for templates/sample documents; no standard reference exists | manual | Two substantive answers (lawyer engagement, early-stage security involvement in vendor selection) confirm there's no off-the-shelf template — both offer partial frameworks rather than pointing to an existing standard | 0.55 |
| 18 | [HN 34609449](https://news.ycombinator.com/item?id=34609449) (cluster: [HN 17140179](https://news.ycombinator.com/item?id=17140179), [HN 19500357](https://news.ycombinator.com/item?id=19500357), [HN 2555964](https://news.ycombinator.com/item?id=2555964), [HN 44844533](https://news.ycombinator.com/item?id=44844533)) | hackernews | true | Individuals and small companies relying on major email providers' (Gmail, Outlook) built-in spam filtering have no visibility or control when the filter regresses — either blocking legitimate mail as spam or letting a rising volume of spam/AI-generated junk through — and no practical alternative besides tolerating it or building custom rules. | Individual user / small-company email admin with no dedicated email security tooling | None consistent — mostly just noticing and tolerating the regression; one poster considered a legacy third-party plugin (Cloudmark SpamNet) but found it unnecessary until recently | none | Five independent posts spanning 2010 to 2025, each reporting the same unresolved pattern (spam filter false positives/negatives with SPF/DKIM/DMARC passing correctly) with no provider fix in the interim — corroboration via persistence across years rather than a single thread's replies | 0.6 |
| 19 | [security.se/273568](https://security.stackexchange.com/questions/273568/security-incident-response-tracking) | stackexchange | true | Security teams using Splunk Enterprise Security for incident response tracking find it lacks a least-privilege model — anyone with incident access can view all incidents — and existing standalone alternatives (ServiceNow SIR, Everbridge xMatters, Resolver, RTIR) are hard to evaluate since most public comparisons/reviews are outdated or reference discontinued tools. | Security analyst/SOC lead responsible for IR tooling evaluation and incident visibility controls | Manually researching outdated forum threads and vendor pages to compare standalone IR tracking tools, with no current, reliable comparison available | manual | No replies at time of pull, but the post itself demonstrates independent research (references older, partially-obsolete community threads on the same tool gap), suggesting persistence of this problem over time rather than isolated confusion | 0.6 |
| 20 | [HN 39982198](https://news.ycombinator.com/item?id=39982198) | hackernews | true | Engineers report that their internal security org functions as a checkbox/compliance-theater operation — creating friction and false confidence without measurably reducing risk — and lack a clear path to push back on or reform this without it reading as undermining security. **Adversarial case #13 example** — the post itself blends this operational complaint with frustrated personal venting ("fail factory," "jumped the shark"); the fields here extract only the operational pain, per the case's stated correct behavior. | Engineer at a company with an established but ineffective internal security function | None — currently just tolerating the friction; seeking advice on how to intervene | none | 8 replies, several independently naming the same dynamic (information asymmetry rewarding security theater over real practice) | 0.6 |
| 21 | [HN 40701410](https://news.ycombinator.com/item?id=40701410) | hackernews | true | Developers want structured security-awareness training focused on personal practices (credential handling, protecting their own devices, recognizing phishing) rather than the application-security-focused material (e.g. OWASP Top 10) that most existing developer security training covers. | Individual developer seeking personal security-hygiene training | None found — searching for resources without success at time of posting | none | No replies at time of pull — no corroboration available; kept as a thin, explicitly weak signal row given how underrepresented the phishing/security-training theme is in this set | 0.4 |

## 4. Noise rows (real, hand-labeled — must be correctly rejected)

| # | permalink | source | is_signal | rationale for rejection |
|---|---|---|---|---|
| 1 | [security.se/286926](https://security.stackexchange.com/questions/286926/cloudflare-is-asking-me-to-run-a-command-in-powershell-on-visiting-my-friends-s) | stackexchange | false | One-off personal "is this a scam" incident question (ClickFix attack recognition), not a recurring operational pain |
| 2 | [security.se/286609](https://security.stackexchange.com/questions/286609/what-makes-certificate-based-authentication-phishing-resistant) | stackexchange | false | Conceptual/how-does-this-work question about cert-based auth vs. MITM; no stated operational pain or workaround |
| 3 | [security.se/281413](https://security.stackexchange.com/questions/281413/logs-not-appearing-in-wazuh-dashboard-for-mimikatz-sharphound-attacks) | stackexchange | false | Explicitly framed as a lab setup for an MSc dissertation — student/coursework context, not a production practitioner's pain |
| 4 | [HN 13997064](https://news.ycombinator.com/item?id=13997064) | hackernews | false | Pure news-sharing (Siemens/Mentor Graphics acquisition) with no personal operational commentary; also an example of the "SIEM" vs. "Siemens" keyword-collision noise this project's queries are prone to |
| 5 | [HN 22686913](https://news.ycombinator.com/item?id=22686913) | hackernews | false | Vendor/founder "Show HN" launch post (Panther SIEM) — vendor pitching their own product, not a practitioner's stated pain |
| 6 | [HN 26107454](https://news.ycombinator.com/item?id=26107454) | hackernews | false | Explicit student ("cyber security student working toward CCNA/CISSP") asking a career/learning question, not a practitioner's operational pain |
| 7 | [HN 19747841](https://news.ycombinator.com/item?id=19747841) | hackernews | false | Certification/interview-prep question ("how do I prepare for my SOC interview"), squarely a career-question rejection per §2 |
| 8 | [HN 46776065](https://news.ycombinator.com/item?id=46776065) | hackernews | false | Reads as a plausible ops complaint (existing monitoring stacks feel "heavyweight and overkill" for simple website-availability checks), but builds directly toward the poster promoting their own side project, with 0 replies and no independent corroboration — labeled false per adversarial case #11 (polished complaint, suspected self-promotion) |

## 5. Adversarial cases (must be handled deliberately, not just missed)

| # | scenario | correct behavior | real example |
|---|---|---|---|
| 9 | Post describes a problem that's already a mature, well-solved product category, restated | `is_signal = false` or low confidence — not a fresh opportunity | [security.se/227416](https://security.stackexchange.com/questions/227416/where-to-store-tokens-for-analysis-team-members) — "where to store tokens for analysis team" answered immediately with password-vault products (KeePass/LastPass/Bitwarden) |
| 10 | Sarcastic/joking tone with no concrete ask | Should not extract a literal problem statement | [HN 31512631](https://news.ycombinator.com/item?id=31512631) — "Are faster queries on your SIEM a vitamin or a painkiller?", no body text, sarcastic reply mocking SIEM vendors, no concrete ask |
| 11 | Polished complaint with no independent corroborating replies (possible astroturf) | Annotator judgment call: the spec's default is lower confidence + noted suspicion, but when the self-promotional angle is this clear-cut, label `is_signal = false` outright rather than a discounted true | [HN 46776065](https://news.ycombinator.com/item?id=46776065) — "Lightweight, Non-Intrusive Website Monitoring" reads as a genuine ops complaint but builds toward the poster's own side project; labeled `false` (see noise row 8) |
| 12 | Duplicate of a problem already captured in an earlier post | Flag as duplicate, don't double-count as a new signal | [HN 36898968](https://news.ycombinator.com/item?id=36898968) / [HN 36979698](https://news.ycombinator.com/item?id=36979698) — same author, same question, reposted for more responses (see signal row 9) |
| 13 | Post mixes a real operational problem with unrelated venting | Extract only the operational pain point | [HN 39982198](https://news.ycombinator.com/item?id=39982198) — "How to deal with a cybersecurity org that has jumped the shark?" blends a legitimate complaint (checkbox/compliance-theater security function that doesn't reduce real risk) with frustrated personal venting; see signal row 20, where only the operational pain is extracted |
| 14 | Ambiguous, non-English, or heavily jargon-coded post | Low confidence rather than a forced guess | **Gap — no usable real example yet.** A candidate was found ([HN 29216673](https://news.ycombinator.com/item?id=29216673), an incoherent buzzword-heavy pitch) but the human labeler rejected using it. Do not fabricate a substitute — pull more real candidates until a usable one surfaces. |

## 6. Scoring method for this eval

- **is_signal classification:** exact match vs. label (precision/recall; false
  positives penalized harder than false negatives, since Discover filters again
  downstream)
- **Extracted fields:** semantic similarity vs. labeled `problem_statement`
  (threshold TBD after first real run)
- **Adversarial rows 9–14:** LLM-as-judge against stated correct behavior,
  spot-checked by human review
- **Run cadence:** on every prompt change during build; daily once ingestion is
  live

## 7. Definition of done for this stage

Extraction is "ready" when: `is_signal` accuracy ≥ 90% on the labeled set, zero
false positives on the noise rows, and adversarial rows 9–14 handled per their
stated correct behavior on manual review. Don't start the Discover/scoring eval
until this one is passing. **Current status: 21 signal rows, 8 noise rows, 5
of 6 adversarial cases covered with real examples. Case 14 and the MSP/phishing
theme thinness are documented, accepted gaps (see Status note above), not
oversights.**

**First real run of `run_evals.py` against `agents/sense_agent.py`:**

- **is_signal accuracy: 89.7%** (26/29 rows) — 1 row under the literal 90%
  bar.
- **False positives on noise rows: 0** — meets the harder bar (§6: false
  positives are penalized more than false negatives).
- **Adversarial case #11** (noise row 8): correctly predicted `false`.
- **Adversarial case #13** (signal row 20): correctly predicted `true`, but
  the extracted `problem_statement` diverged from the ground-truth framing
  (pulled out different specific complaints from the same post rather than
  the checkbox/compliance-theater framing labeled). Not re-litigated this
  round — flagged for attention if case 13 accuracy matters more once
  Discover-stage clustering is running.
- **All 3 false negatives were rows the human annotator had already flagged
  as the lowest-confidence signal rows during labeling** (0.4–0.6): row 9
  (HN 36898968, OSS vuln management), row 17 (SE 10799, outsourcing SLA),
  row 21 (HN 40701410, security awareness training — the row explicitly
  added as "thin" per the Known gaps note above).

**Human labeler decision: accepted as passing in spirit, despite being under
the literal 90% threshold.** The misses land exactly on the eval's own
weakest-confidence rows rather than on clear-cut signal — read as the eval
correctly surfacing genuine boundary cases, not a prompt defect. Proceeding to
Discover-stage work on this basis, per the build order in CLAUDE.md.
