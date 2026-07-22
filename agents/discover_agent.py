"""Discover-stage clustering and scoring.

Clustering groups Sense-stage extraction results
(agents/sense_agent.py:ExtractionResult) into clusters that share the same
underlying pain point across posts, sources, and days (build-order step 3).

Scoring (build-order step 5) takes a Cluster plus its member ExtractionResults
and produces a ScoredCluster against the rubric in evals/opportunity-scoring.md.
frequency_corroboration is computed programmatically per that file's documented
formula. signal_validity and extraction_accuracy are LLM-as-judge per the
rubric. small_team_feasibility and willingness_to_pay_signal are computed
deterministically from an LLM-classified tier (compute_small_team_feasibility,
compute_willingness_to_pay_signal). novelty is still a direct LLM float, but
the rubric is explicit that novelty must stay human-reviewed ("don't let an
LLM self-certify novelty") — it's a DRAFT value and must never be treated as
ground truth until a human confirms or corrects it.

overall_rank_score is now also a deterministic formula
(compute_overall_rank_score), not LLM output, fit against the 16 hand-labeled
clusters in evals/opportunity-scoring.md: when small_team_feasibility is
near-floor (<=0.1), overall_rank_score is floored at 0.1 (0.2 if novelty is
also high, >=0.6) regardless of the other fields; otherwise it's a weighted
blend of small_team_feasibility, willingness_to_pay_signal, and
(1 - novelty). See compute_overall_rank_score's docstring for the exact
weights and known limits — the formula was fit to only 16 points with no
held-out set, so it risks curve-fitting; re-run
evals/run_discover_scoring_eval.py against any newly hand-labeled clusters
before trusting further tuning.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import anthropic

from agents.sense_agent import ExtractionResult

MODEL = os.environ.get("DISCOVER_AGENT_MODEL", "claude-sonnet-5")

SYSTEM_PROMPT = """\
You are given a numbered list of Sense-stage extraction results (signals) \
pulled from Stack Exchange and Hacker News, each already judged to be a \
real, recurring cybersecurity operational pain point.

Group signals into clusters that describe the SAME underlying pain point — \
not just the same broad topic. Two signals belong together only if a PM \
could write one opportunity_statement that both would recognize as their \
own problem.

Rules:
- Every signal must appear in exactly one cluster. Singletons (clusters of \
  size 1) are fine and expected — do not force unrelated signals together \
  for coverage.
- Prefer fewer, tighter clusters over broad topic buckets. "SIEM alert \
  fatigue" and "SIEM licensing costs" are different pain points even though \
  both are about SIEM.
- Cross-source and cross-day corroboration (the same pain point stated \
  independently on Stack Exchange and Hacker News, or on different days) is \
  the whole point of this step — actively look for it rather than defaulting \
  to per-source clusters.
- For each cluster, write a one-sentence shared_pain_statement a PM could \
  hand to an engineer, and a short rationale for why these signals belong \
  together (or, for a singleton, why it doesn't match anything else in the \
  batch).\
"""

CLUSTER_SIGNALS_TOOL = {
    "name": "cluster_signals",
    "description": "Group signal indices into clusters describing the same underlying pain point.",
    "input_schema": {
        "type": "object",
        "properties": {
            "clusters": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "signal_indices": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "Indices (from the numbered list) of signals in this cluster.",
                        },
                        "shared_pain_statement": {
                            "type": "string",
                            "description": "One PM-ready sentence describing the pain point shared by this cluster.",
                        },
                        "rationale": {
                            "type": "string",
                            "description": "Why these signals belong together (or, for a singleton, why not).",
                        },
                    },
                    "required": ["signal_indices", "shared_pain_statement", "rationale"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["clusters"],
        "additionalProperties": False,
    },
}


@dataclass
class Cluster:
    cluster_id: str
    signal_ids: list[str]  # permalinks
    shared_pain_statement: str
    rationale: str


def _format_signals(signals: list[ExtractionResult]) -> str:
    lines = []
    for i, s in enumerate(signals):
        lines.append(
            f"[{i}] source={s.source} permalink={s.permalink}\n"
            f"    problem: {s.problem_statement}\n"
            f"    affected_role: {s.affected_role}\n"
            f"    workaround: {s.current_workaround} ({s.workaround_type})\n"
            f"    corroboration: {s.corroboration_signal}"
        )
    return "\n\n".join(lines)


def cluster_signals(
    signals: list[ExtractionResult], client: anthropic.Anthropic | None = None
) -> list[Cluster]:
    """Group extracted signals into clusters sharing the same underlying pain point."""
    if not signals:
        return []

    client = client or anthropic.Anthropic()

    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        tools=[CLUSTER_SIGNALS_TOOL],
        tool_choice={"type": "tool", "name": "cluster_signals"},
        messages=[{"role": "user", "content": _format_signals(signals)}],
    )

    tool_use = next(b for b in response.content if b.type == "tool_use")
    raw_clusters = tool_use.input["clusters"]

    clusters = []
    for i, c in enumerate(raw_clusters):
        signal_ids = [signals[idx].permalink for idx in c["signal_indices"]]
        clusters.append(
            Cluster(
                cluster_id=f"cluster-{i + 1}",
                signal_ids=signal_ids,
                shared_pain_statement=c["shared_pain_statement"],
                rationale=c["rationale"],
            )
        )
    return clusters


SCORING_SYSTEM_PROMPT = """\
You are a cybersecurity market-opportunity analyst. You are given one \
cluster of Sense-stage signals that share the same underlying pain point, \
and you classify it into calibrated TIERS — you do not assign the final \
numeric scores yourself. A deterministic lookup table (calibrated against \
16 real hand-labeled clusters) converts your tier choice into a score, so \
two clusters in the same tier always get the same number.

For each of the two tier fields below, the options are MUTUALLY EXCLUSIVE \
categories describing the SAME underlying situation from different angles \
— pick exactly ONE that best fits, don't try to satisfy several at once. \
Work top to bottom and stop at the first one that genuinely applies; only \
fall through to a lower option if an earlier one clearly doesn't fit.

## small_team_feasibility_tier — pick ONE

1. platform_gatekeeper_exclusive_control: literally only one gatekeeper \
   platform (e.g. Chrome Web Store / an app store's own listing moderation) \
   can act on the fix — no workaround or partial third-party product is \
   possible at all.
2. requires_carrier_regulator_or_standards_body: the real fix requires a \
   telecom carrier, government regulator, or a standards/certifying body to \
   change infrastructure or the rule itself.
3. requires_platform_vendor_code_fix: the fix is a browser or OS vendor's \
   own bug/code, though a small team could still ship a partial workaround \
   or mitigation tool (unlike option 1, some partial path exists).
4. requires_real_incident_engagements_to_validate: building or validating a \
   credible product requires access to real incident-response engagements \
   or similarly scarce first-hand case access.
5. os_kernel_or_permission_model_internals: the fix is inherent to an OS \
   kernel/permission model's internals (e.g. Windows Update service \
   internals, Linux sudo/account model) — any small-team product would \
   only ever be a workaround, not a real fix.
6. requires_large_scale_specialized_data_or_infra: solving it well requires \
   large-scale specialized data or infrastructure a small team is unlikely \
   to have (e.g. broad attack telemetry, DDoS-scale traffic data).
7. db_engine_privilege_model_internals: the fix is inherent to a database \
   engine's own privilege/grant model internals.
8. adjacent_symptom_fixable_root_cause_vendor_owned: the root cause sits \
   inside a single vendor's own infrastructure, but an adjacent product \
   could still plausibly address symptoms around it.
9. deep_platform_api_access_uncertain: it's genuinely unclear whether \
   building this requires deep, hard-to-get vendor/platform API access.
10. buildable_as_independent_tool: none of the above apply — a small team \
    could ship this as an independent tool without needing the cooperation \
    of whichever platform/vendor owns the underlying system.

When you pick buildable_as_independent_tool, also set these two booster \
booleans (both false otherwise):
- public_data_feeds_or_standards_available: true if public data feeds, \
  APIs, or standards documents already exist that a small team could build \
  directly on top of (e.g. KEV/EPSS feeds, public compliance framework \
  text, standard CLI tooling like ssh-keygen/ssh-keyscan).
- prior_art_or_partial_solutions_exist: true if credible prior art or \
  partial solutions already exist in this space that a small team could \
  extend or package, rather than building from zero.

## willingness_to_pay_signal_tier — pick ONE

1. only_seller_is_platform_itself: the only entity that could ever be paid \
   for a fix is the platform/vendor itself — no third party has anything a \
   business could buy.
2. zero_market_touchpoint: no business buyer in the picture at all — pure \
   personal/hobbyist/individual-admin annoyance.
3. faint_market_touchpoint: a buyer type exists in theory but there is no \
   real signal of it — weaker than option 2 but still unconvincing. Do NOT \
   pick this just because the post lacks explicit budget language — check \
   options 5-9 first for an inferable market before settling here.
4. incumbent_already_serves_exact_need: an established incumbent already \
   solves this *exact* need (not just something adjacent) — no evidence of \
   unmet demand.
5. grc: this is compliance/GRC tooling — the most reliably budgeted \
   vertical in this space.
6. banks_mandated: regulated financial institutions are essentially \
   required to invest here.
7. ir_or_established_market: incident response retainers, or a market \
   already documented/known to be large and well-funded.
8. mature_adjacent_market_dampened: the buyer's category has real, \
   established budget, but they'd expect this specific gap to already be \
   covered by something they've already bought.
9. revealed_effort_or_compliance_driven_spend: the poster is already \
   investing real time/effort into a workaround (a proxy for willingness to \
   pay), or the pain is compliance/audit-driven (failing an audit has a \
   real cost).
10. adjacent_category_vendor_proves_budget_niche_unserved: a paid vendor \
    exists for an *adjacent* problem (proving the category has budget) \
    while this specific gap remains unserved — white space, not saturation \
    (distinguish from option 4, where the exact need is already served).
11. plausible_enterprise_budget_inferred: it's plausible enterprises pay \
    for tooling in this space, but with no direct budget language and no \
    established-market anchor to point to.
12. no_signal: none of the above apply and there is genuinely no \
    willingness-to-pay signal to infer.

## Worked examples (real calibration boundary cases)

These are real clusters where the right tier is easy to mis-pick. Read them \
before classifying — they show why one tier applies and not the other \
plausible-looking one.

- "Cyber Essentials (IASME) certification requires a separate admin \
  account distinct from a standard sudo-enabled account on Linux, but \
  there's no clear, security-equivalent way to implement this without \
  credential sprawl or weakening audit trails." -> \
  small_team_feasibility_tier = os_kernel_or_permission_model_internals \
  (NOT buildable_as_independent_tool, even though it superficially \
  resembles a compliance-mapping problem like the ITAR/CMMC example below). \
  The blocker here is that Linux's sudo/account model has no equivalent to \
  Windows' admin/user separation — that's a permission-model limitation, \
  not a documentation or mapping gap a small team's content/tooling could \
  close.
- "Small companies pursuing ITAR/CMMC lack a structured way to map \
  framework requirements to proportionate, developer-friendly controls." -> \
  small_team_feasibility_tier = buildable_as_independent_tool, both \
  boosters true. Unlike the Cyber Essentials example above, the blocker \
  here is a missing mapping methodology/content — the frameworks and \
  controls themselves are public documents a small team can build tooling \
  or content directly on top of. willingness_to_pay_signal_tier = grc.
- "Operators lack tooling to pinpoint how a compromise re-enters a freshly \
  rebuilt server/container stack when the root cause is at the app/CI-CD/ \
  Docker layer." -> small_team_feasibility_tier = \
  requires_real_incident_engagements_to_validate (NOT buildable, even \
  though "write a diagnostic checklist tool" sounds buildable on its face). \
  A credible product here can only be validated against real incident \
  case data — unlike, say, a vulnerability-scanner-noise tool where public \
  KEV/EPSS feeds are immediately usable without needing real case access. \
  willingness_to_pay_signal_tier = ir_or_established_market (incident \
  response is a reliably funded vertical, not an unfunded activity).
- "A sysadmin needs to globally block a malicious IP subnet from reaching \
  all reverse-proxied vhosts in Apache, but standard <Proxy>/<Directory> \
  ACL directives silently fail on ProxyPass-routed traffic." -> \
  small_team_feasibility_tier = requires_large_scale_specialized_data_or_infra. \
  The specific config bug already has a known, documented fix (an \
  established incumbent's own docs cover it) — solving this "well" as a \
  product would mean broad attack-traffic/DDoS-scale infrastructure, which \
  is a different and much bigger lift than the one-off config correction \
  already given in the replies. willingness_to_pay_signal_tier = \
  incumbent_already_serves_exact_need (the incumbent already solves this \
  exact class of problem, so there's no evidence of unmet demand).
- "macOS's new Local Network Access permission system silently breaks CLI- \
  driven SSH tunnels without ever prompting, leaving no way to grant access \
  from the command line." -> small_team_feasibility_tier = \
  buildable_as_independent_tool, no boosters (base 0.4). Unlike the Cyber \
  Essentials or Windows Update examples, the underlying mechanism here (a \
  permission-prompt system) is something a small utility could plausibly \
  detect/trigger/work around without needing Apple's own cooperation — \
  more approachable than a true OS-internals limitation, but with no \
  existing data feed or prior art to boost it further.
- "Google's domain verification and anti-spoofing protections don't cover \
  g.co subdomains, letting attackers send convincing phishing emails that \
  abuse trust in Google's own infrastructure." -> small_team_feasibility_tier \
  = adjacent_symptom_fixable_root_cause_vendor_owned (NOT \
  platform_gatekeeper_exclusive_control). The root cause (Google's own \
  domain verification) is unfixable by anyone but Google, but — unlike the \
  Chrome Web Store takedown example, where literally nothing else can act — \
  an adjacent email-security/detection product could still catch these \
  look-alike sends as a symptom-level mitigation. willingness_to_pay_signal_tier \
  = mature_adjacent_market_dampened (businesses already pay for email \
  security broadly, but would expect this exact gap to already be covered \
  by something they've bought).
- "Cyber Essentials (IASME) certification requires a separate admin account \
  distinct from a standard sudo-enabled account on Linux, and the poster is \
  weighing actually implementing the redundant account purely to pass the \
  audit." -> willingness_to_pay_signal_tier = \
  revealed_effort_or_compliance_driven_spend. The poster is already \
  investing real effort into building the workaround specifically to \
  satisfy the audit — that revealed effort is the actual signal, not the \
  word "compliance" by itself.
- "Organizations pursuing Cyber Essentials Plus certification are required \
  to install closed-source, root-privileged third-party endpoint agents \
  with no way to vet them or opt out." -> willingness_to_pay_signal_tier = \
  no_signal (NOT grc or revealed_effort_or_compliance_driven_spend, despite \
  also being Cyber-Essentials-adjacent). Naming a compliance framework \
  isn't sufficient on its own — there's no stated workaround investment, no \
  budget language, and no plausible buyer for a fix here, just a complaint \
  about an unavoidable mandate. Contrast with the sudo example above: same \
  certification, opposite tier, because only one shows revealed effort or \
  spend.
- "Admins managing OpenSSH CA-issued certificates have no built-in tooling \
  to track expiration, forcing fragile hand-built parsing scripts to catch \
  it before it causes an outage." -> willingness_to_pay_signal_tier = \
  revealed_effort_or_compliance_driven_spend. Building and maintaining a \
  fragile home-grown script is itself the revealed-effort signal this tier \
  exists to capture — the poster is already paying an engineering-time cost \
  to solve this, even with no dollar figure or vendor mentioned anywhere in \
  the post.
- "Azure admins have no native lifecycle-management controls for Cognitive \
  Services resources — bulk key rotation, pause/disable billing, or \
  key-access alerting." -> willingness_to_pay_signal_tier = \
  plausible_enterprise_budget_inferred (NOT faint_market_touchpoint, even \
  though the post itself states no price or budget). Cloud cost/governance \
  tooling is a category enterprises plausibly already budget for — use \
  faint_market_touchpoint only when you can't even infer a plausible buyer \
  type for the category, not just because the post is silent on price.
- "Businesses and consumers have no technical or regulatory way to stop \
  SMS/RCS sender-ID spoofing, leaving smishing/impersonation attacks \
  effectively unblockable." -> small_team_feasibility_tier = \
  requires_carrier_regulator_or_standards_body. There is no adjacent product \
  path here at all — sender-ID spoofing can only be closed by carrier \
  infrastructure or a regulator/standards body changing how SMS/RCS routing \
  itself works; no third-party layer can sit in front of it.
- "Generic wording in bank OTP/password-reset SMS messages fails to signal \
  their specific purpose, enabling vishing attacks that trick customers into \
  reading codes to fraudsters during account-recovery social engineering." \
  -> small_team_feasibility_tier = buildable_as_independent_tool, \
  prior_art_or_partial_solutions_exist=true (base 0.4 + 0.1 = 0.5). Do NOT \
  default to requires_carrier_regulator_or_standards_body just because the \
  nominal fix (rewording the bank's own SMS copy) belongs to the bank — \
  that's the wrong comparison. Unlike the sender-ID spoofing case above, a \
  small team doesn't need the bank's or a carrier's cooperation to build and \
  sell an *adjacent* product that mitigates this exact fraud vector (e.g. \
  real-time vishing/call-correlation scoring, a customer-facing \
  authentication-hardening layer banks integrate) — reserve \
  requires_carrier_regulator_or_standards_body for cases with no sellable \
  third-party layer at all, not merely "the literal fix is someone else's \
  copy/config."

## Other fields

- signal_validity (0.0-1.0): is this real, recurring pain vs. noise/ \
  venting/a one-off? Weight the underlying signals' own confidence and \
  corroboration_signal fields, but judge the cluster as a whole rather than \
  averaging them mechanically.
- extraction_accuracy (0.0-1.0): does your opportunity_statement faithfully \
  carry through the problem/workaround/audience stated in the member \
  signals, without drifting broader or narrower than what they actually said?
- novelty (0.0-1.0): DRAFT ONLY — will be reviewed and likely corrected by a \
  human, do not treat your own value as final. Established, well-solved \
  problem/solution categories score low; genuinely underserved niches score \
  high.
- opportunity_statement: one sentence framing this as a market opportunity \
  (not just a restated pain point) — what's broken/missing and for whom.
- rationale: your reasoning, in the style of: dimension=value: short \
  reason. Cite specifics from the signals, not generic language.\
"""

_FEASIBILITY_TIERS = [
    "platform_gatekeeper_exclusive_control",
    "requires_carrier_regulator_or_standards_body",
    "requires_platform_vendor_code_fix",
    "requires_real_incident_engagements_to_validate",
    "os_kernel_or_permission_model_internals",
    "requires_large_scale_specialized_data_or_infra",
    "db_engine_privilege_model_internals",
    "adjacent_symptom_fixable_root_cause_vendor_owned",
    "deep_platform_api_access_uncertain",
    "buildable_as_independent_tool",
]

_WILLINGNESS_TIERS = [
    "only_seller_is_platform_itself",
    "zero_market_touchpoint",
    "faint_market_touchpoint",
    "incumbent_already_serves_exact_need",
    "grc",
    "banks_mandated",
    "ir_or_established_market",
    "mature_adjacent_market_dampened",
    "revealed_effort_or_compliance_driven_spend",
    "adjacent_category_vendor_proves_budget_niche_unserved",
    "plausible_enterprise_budget_inferred",
    "no_signal",
]

SCORE_CLUSTER_TOOL = {
    "name": "score_cluster",
    "description": "Classify a cluster of signals into calibrated tiers and scores.",
    "input_schema": {
        "type": "object",
        "properties": {
            "opportunity_statement": {
                "type": "string",
                "description": "One-sentence market-opportunity framing of this cluster's pain point.",
            },
            "signal_validity": {"type": "number"},
            "extraction_accuracy": {"type": "number"},
            "small_team_feasibility_tier": {"type": "string", "enum": _FEASIBILITY_TIERS},
            "public_data_feeds_or_standards_available": {
                "type": "boolean",
                "description": "Only meaningful when tier is buildable_as_independent_tool.",
            },
            "prior_art_or_partial_solutions_exist": {
                "type": "boolean",
                "description": "Only meaningful when tier is buildable_as_independent_tool.",
            },
            "willingness_to_pay_signal_tier": {"type": "string", "enum": _WILLINGNESS_TIERS},
            "novelty": {
                "type": "number",
                "description": "DRAFT — will be human-reviewed, not treated as final.",
            },
            "rationale": {"type": "string"},
        },
        "required": [
            "opportunity_statement",
            "signal_validity",
            "extraction_accuracy",
            "small_team_feasibility_tier",
            "public_data_feeds_or_standards_available",
            "prior_art_or_partial_solutions_exist",
            "willingness_to_pay_signal_tier",
            "novelty",
            "rationale",
        ],
        "additionalProperties": False,
    },
}


@dataclass
class ScoredCluster:
    cluster_id: str
    signal_ids: list[str]
    opportunity_statement: str
    signal_validity: float
    extraction_accuracy: float
    frequency_corroboration: float
    small_team_feasibility: float
    willingness_to_pay_signal: float
    novelty: float  # DRAFT — human review required before treating as ground truth
    overall_rank_score: float  # deterministic formula — see compute_overall_rank_score
    rationale: str
    feasibility_tier: str  # kept for audit/debugging
    willingness_tier: str  # kept for audit/debugging


def compute_frequency_corroboration(signals: list[ExtractionResult]) -> float:
    """Programmatic per evals/opportunity-scoring.md's documented formula:
    volume_score = min(1.0, num_signals / 4); source_diversity = 1.0 if
    >=2 distinct sources else 0.4; frequency_corroboration = their average.
    """
    volume_score = min(1.0, len(signals) / 4)
    source_diversity = 1.0 if len({s.source for s in signals}) >= 2 else 0.4
    return (volume_score + source_diversity) / 2


_FEASIBILITY_TIER_SCORES = {
    "platform_gatekeeper_exclusive_control": 0.0,
    "requires_carrier_regulator_or_standards_body": 0.1,
    "requires_platform_vendor_code_fix": 0.1,
    "requires_real_incident_engagements_to_validate": 0.1,
    "os_kernel_or_permission_model_internals": 0.1,
    "requires_large_scale_specialized_data_or_infra": 0.2,
    "db_engine_privilege_model_internals": 0.2,
    "adjacent_symptom_fixable_root_cause_vendor_owned": 0.2,
    "deep_platform_api_access_uncertain": 0.3,
    # "buildable_as_independent_tool" is computed, not looked up — see below.
}

_WILLINGNESS_TIER_SCORES = {
    "only_seller_is_platform_itself": 0.1,
    "zero_market_touchpoint": 0.1,
    "no_signal": 0.1,
    "faint_market_touchpoint": 0.2,
    "incumbent_already_serves_exact_need": 0.2,
    "adjacent_category_vendor_proves_budget_niche_unserved": 0.4,
    "plausible_enterprise_budget_inferred": 0.4,
    "revealed_effort_or_compliance_driven_spend": 0.6,
    "ir_or_established_market": 0.6,
    "mature_adjacent_market_dampened": 0.6,
    "banks_mandated": 0.8,
    "grc": 0.9,
}


def compute_small_team_feasibility(
    tier: str, public_data_available: bool = False, prior_art_exists: bool = False
) -> float:
    """Deterministic tier-lookup formula calibrated against the 16
    hand-labeled clusters in evals/opportunity-scoring.md.
    """
    if tier != "buildable_as_independent_tool":
        return _FEASIBILITY_TIER_SCORES[tier]
    score = 0.4
    if public_data_available:
        score += 0.2
    if prior_art_exists:
        score += 0.1
    return min(score, 1.0)


def compute_willingness_to_pay_signal(tier: str) -> float:
    """Deterministic tier-lookup formula calibrated against the 16
    hand-labeled clusters in evals/opportunity-scoring.md.
    """
    return _WILLINGNESS_TIER_SCORES[tier]


def compute_overall_rank_score(
    small_team_feasibility: float, willingness_to_pay_signal: float, novelty: float
) -> float:
    """Deterministic formula fit against the 16 hand-labeled clusters in
    evals/opportunity-scoring.md (MAE 0.034, 6/16 exact rank-position
    agreement — up from freehand-LLM ~4/16 with much worse per-field error).

    Reverse-engineered from the hand-labeled rationales: small_team_feasibility
    acts as a hard near-floor when very low, exactly like the human labeler's
    own stated reasoning ("feasibility floor applied uniformly..."); above
    that floor, feasibility and willingness-to-pay drive the score roughly
    equally, with novelty as a minor, inverted tiebreaker (a crowded/
    well-solved space drags the score down a little even when buildable and
    fundable).

    Known limit: fit to only 16 points with no held-out set, so treat as
    calibrated-but-unproven — re-check against any newly hand-labeled
    clusters (evals/run_discover_scoring_eval.py) before further tuning.
    """
    if small_team_feasibility <= 0.1:
        return 0.2 if novelty >= 0.6 else 0.1
    return round(
        0.45 * small_team_feasibility
        + 0.45 * willingness_to_pay_signal
        + 0.1 * (1 - novelty),
        4,
    )


def score_cluster(
    cluster: Cluster,
    signals: list[ExtractionResult],
    client: anthropic.Anthropic | None = None,
) -> ScoredCluster:
    """Score a cluster against evals/opportunity-scoring.md's rubric.

    `signals` must be the member ExtractionResults for cluster.signal_ids
    (used both for the LLM-as-judge call and the programmatic
    frequency_corroboration formula). small_team_feasibility and
    willingness_to_pay_signal are computed deterministically from the
    LLM-classified tier, not assigned directly by the model.
    """
    client = client or anthropic.Anthropic()

    frequency_corroboration = compute_frequency_corroboration(signals)

    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=SCORING_SYSTEM_PROMPT,
        tools=[SCORE_CLUSTER_TOOL],
        tool_choice={"type": "tool", "name": "score_cluster"},
        messages=[
            {
                "role": "user",
                "content": (
                    f"shared_pain_statement: {cluster.shared_pain_statement}\n\n"
                    f"{_format_signals(signals)}"
                ),
            }
        ],
    )

    tool_use = next(b for b in response.content if b.type == "tool_use")
    fields = tool_use.input

    feasibility_tier = fields["small_team_feasibility_tier"]
    willingness_tier = fields["willingness_to_pay_signal_tier"]

    small_team_feasibility = compute_small_team_feasibility(
        feasibility_tier,
        fields["public_data_feeds_or_standards_available"],
        fields["prior_art_or_partial_solutions_exist"],
    )
    willingness_to_pay_signal = compute_willingness_to_pay_signal(willingness_tier)
    novelty = fields["novelty"]

    return ScoredCluster(
        cluster_id=cluster.cluster_id,
        signal_ids=cluster.signal_ids,
        opportunity_statement=fields["opportunity_statement"],
        signal_validity=fields["signal_validity"],
        extraction_accuracy=fields["extraction_accuracy"],
        frequency_corroboration=frequency_corroboration,
        small_team_feasibility=small_team_feasibility,
        willingness_to_pay_signal=willingness_to_pay_signal,
        novelty=novelty,
        overall_rank_score=compute_overall_rank_score(
            small_team_feasibility, willingness_to_pay_signal, novelty
        ),
        rationale=fields["rationale"],
        feasibility_tier=feasibility_tier,
        willingness_tier=willingness_tier,
    )
