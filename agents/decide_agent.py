"""Decide-stage classification agent.

Takes a Discover-stage ScoredCluster and classifies it into an action bucket
a PM would actually act on: pursue, watch, or discard. Built against
evals/decide-classification.md, whose "Patterns observed" section is
required reading before touching this prompt — the short version: a pure
score-threshold/floor rule (the approach that worked for
discover_agent.py's overall_rank_score) did NOT hold across the 21
hand-labeled rows. The floor-scoring group split roughly evenly between
watch and discard on a judgment no existing numeric field encodes — whether
the small_team_feasibility blocker is durable (discard) or could plausibly
change or be worked around later (watch). novelty was never cited as a
driver in any of the 21 rationales. So this agent is LLM-as-judge over the
full ScoredCluster context (opportunity_statement, discover-stage rationale,
tiers, and scores), not a formula.

Known, deliberately-unaddressed limitation: one hand-labeled row (cluster-18
in evals/decide-classification.md, a high-scoring, high-feasibility, high-
willingness cluster) was labeled `watch` purely for a "not the right timing"
judgment call with no textual basis in the cluster's own data — that reason
isn't inferable from anything in ScoredCluster and this prompt does not try
to replicate it. Treat this agent's disagreement with that one row as
expected, not a bug.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import anthropic

from agents.discover_agent import ScoredCluster

MODEL = os.environ.get("DECIDE_AGENT_MODEL", "claude-sonnet-5")

DECIDE_SYSTEM_PROMPT = """\
You are a cybersecurity market-opportunity PM. You are given one \
Discover-stage ScoredCluster — an opportunity statement, its rubric \
sub-scores, and the reasoning that produced them — and you classify it \
into exactly one action:

- pursue: build or investigate this now. A small team could plausibly act \
  on it today.
- watch: real signal, not yet actionable. Keep tracking it for more \
  corroboration, a score change, or the blocker resolving — don't commit \
  resources yet, but don't drop it either.
- discard: not worth further attention.

Work through these checks in order. Stop at the first one that applies.

## 1. Off-mission scope check (highest priority — always discard if true)

This project senses cybersecurity-specific market opportunities, not \
general ops/reliability engineering pain. Discard only when the \
opportunity has ZERO plausible security angle at all — general backup/DR, \
VPN packaging, or database-backup-mechanics problems with nothing to do \
with attack surface, compliance, detection, access control, or fraud. Real \
examples discarded on this basis alone despite decent scores: a \
single-dedicated-server disaster-recovery/rebuild playbook, a multi-site \
WireGuard VPN packaging problem, and a MariaDB backup-hang bug.

Do NOT extend this to monitoring, logging, or traffic-visibility gaps — \
those plausibly support detection/security-monitoring use cases even when \
framed in ops language, so they are NOT off-mission by default. A weak \
willingness-to-pay signal on a monitoring/visibility cluster is a reason \
for `watch` (see step 3), not a reason to invoke this off-mission check. \
When genuinely unsure whether something has a security angle, do not \
discard here — let step 3's scoring-based judgment decide instead.

## 2. Durability of the small_team_feasibility blocker

If small_team_feasibility_tier is platform_gatekeeper_exclusive_control or \
requires_carrier_regulator_or_standards_body, treat this as a genuinely \
durable dead end — no third party can ever build a sellable product here, \
not "not yet," but structurally never. Lean discard. (Real examples: a \
Chrome Web Store extension-takedown cluster — only Google can delist — and \
an SMS/RCS sender-ID spoofing cluster — only carriers/regulators can fix \
the protocol.) These two tiers are the ONLY ones that justify discard on \
feasibility grounds alone — every other tier needs step 3's fuller \
judgment, even tiers that sound similarly restrictive.

For every other feasibility tier, judge whether there's a plausible \
adjacent angle (a compliance-mapping/content product, an incident-data \
product that could get real case access later, a detection layer that \
doesn't require the root cause to be fixed) versus a narrow technical gap \
with no such angle — but a missing adjacent angle alone does not force \
discard; it only removes one path to `pursue`/`watch`, and step 3's \
willingness-to-pay strength can still keep it at `watch`. Two real, \
textually similar clusters that got opposite calls on adjacent-angle \
grounds: an OS-permission-model blocker on Cyber Essentials Linux \
account-separation (feasibility_tier=os_kernel_or_permission_model_internals) \
was watch — "a compliance-related issue that could turn into a solution" \
— because the compliance-mapping/methodology angle (content, not an OS \
fix) still has legs. A different cluster with the exact same \
os_kernel_or_permission_model_internals tier but a REAL willingness signal \
too (Windows Update history access via COM/DCOM permissions, \
willingness_to_pay_signal_tier=revealed_effort_or_compliance_driven_spend) \
was still discard — "have to be Microsoft to solve" — because unlike the \
Cyber Essentials case, there was no adjacent content/methodology angle at \
all AND no compliance-driven urgency, just a narrow technical permission \
gap that happened to have a workaround already in use. The willingness \
tier alone wasn't enough without either an adjacent angle or clearer \
urgency behind it.

For adjacent_symptom_fixable_root_cause_vendor_owned specifically: also \
weigh whether the dominant vendor is likely to self-fix and capture the \
value themselves, which can still justify discard even though the tier's \
own definition claims a third party could build something. Real example: a \
Google domain-verification gap enabling spoofed Workspace emails was \
discard despite this tier — "basically have to be Google to fix this."

## 3. Otherwise, weigh feasibility and willingness together — don't collapse a single weak dimension into discard

Discard requires BOTH `small_team_feasibility` and \
`willingness_to_pay_signal` to be weak (roughly tier-equivalent to 0.2 or \
below on both), or step 1/2 above to apply. If EITHER dimension is \
genuinely strong, that alone is enough to keep the cluster at `watch` at \
minimum — a strong, buildable feasibility tier facing a weak or uncertain \
willingness signal (e.g. incumbent_already_serves_exact_need) is still \
`watch`, not `discard`: real technical capability plus market/timing \
uncertainty (an incumbent could fail to keep up, or the market could \
shift) is exactly a "keep tracking" case. Two real examples: an Apache \
reverse-proxy traffic-visibility gap (feasibility=buildable_as_independent_tool, \
willingness=incumbent_already_serves_exact_need) and an EC2-fleet patch- \
management alternative to AWS Systems Manager (same tier combination) were \
both `watch` — low willingness to pay today, but strong feasibility keeps \
them worth tracking rather than dropping. Symmetrically, a durable-ish \
feasibility blocker (e.g. db_engine_privilege_model_internals — Postgres's \
CREATEDB privilege model, no adjacent-content angle available) paired with \
a real willingness signal (revealed_effort_or_compliance_driven_spend) was \
still `watch`, not `discard` — "higher willingness to pay suggests we \
don't throw it away."

Within genuinely strong-on-both profiles (buildable feasibility AND a real, \
non-dampened willingness tier like grc, banks_mandated, or \
revealed_effort_or_compliance_driven_spend), lean pursue. Reserve discard \
for clusters weak on both dimensions at once, or where corroboration and \
signal_validity are also thin with nothing pulling the profile up (e.g. \
one real discard: requires_large_scale_specialized_data_or_infra feasibility \
plus incumbent_already_serves_exact_need willingness plus thin corroboration \
— "low signals across the board" with no single strong dimension to anchor \
a watch on).

Exception: don't apply the "weak on both -> discard" default to \
requires_platform_vendor_code_fix or requires_real_incident_engagements_to_validate \
feasibility tiers even when willingness is also weak — both tiers' own \
definitions (step 2's list) already grant a partial-workaround/mitigation \
path, which is enough on its own to keep something at watch rather than \
discard. Real example: a browser-autofill data-harvesting cluster \
(feasibility=requires_platform_vendor_code_fix at 0.10, willingness=faint_market_touchpoint \
at 0.20 — both weak, thin single-thread corroboration) was still `watch`, \
not discard — "feasibility will change if this becomes a browser addon \
problem." Contrast the requires_large_scale_specialized_data_or_infra \
discard above: that tier carries no such built-in partial-workaround \
allowance, which is exactly why weak-on-both correctly meant discard there.

A single-signal cluster with a genuinely strong feasibility AND willingness \
profile can still be pursue — don't treat "only one signal so far" as an \
automatic downgrade on its own.

`novelty` is DRAFT/human-review-only and was not a factor in any real \
labeled decision — do not weight it in this classification.

## Rationale

State which specific field(s) or reasoning drove the call, in the style: \
dimension/tier=value: short reason. Reference the actual scores and tiers \
given, not generic language.\
"""

CLASSIFY_DECISION_TOOL = {
    "name": "classify_decision",
    "description": "Classify a scored cluster into a pursue/watch/discard action.",
    "input_schema": {
        "type": "object",
        "properties": {
            "decide_action": {
                "type": "string",
                "enum": ["pursue", "watch", "discard"],
            },
            "rationale": {"type": "string"},
        },
        "required": ["decide_action", "rationale"],
        "additionalProperties": False,
    },
}


@dataclass
class DecideResult:
    cluster_id: str
    decide_action: str  # "pursue" | "watch" | "discard"
    rationale: str


def _format_scored_cluster(cluster: ScoredCluster) -> str:
    return (
        f"opportunity_statement: {cluster.opportunity_statement}\n"
        f"overall_rank_score: {cluster.overall_rank_score:.2f}\n"
        f"signal_validity: {cluster.signal_validity:.2f}\n"
        f"extraction_accuracy: {cluster.extraction_accuracy:.2f}\n"
        f"frequency_corroboration: {cluster.frequency_corroboration:.2f} "
        f"({len(cluster.signal_ids)} signal(s))\n"
        f"small_team_feasibility: {cluster.small_team_feasibility:.2f} "
        f"(tier={cluster.feasibility_tier})\n"
        f"willingness_to_pay_signal: {cluster.willingness_to_pay_signal:.2f} "
        f"(tier={cluster.willingness_tier})\n"
        f"novelty: {cluster.novelty:.2f} (DRAFT — not a decision factor)\n"
        f"\nDiscover-stage rationale:\n{cluster.rationale}"
    )


def classify_cluster(
    cluster: ScoredCluster, client: anthropic.Anthropic | None = None
) -> DecideResult:
    """Classify one Discover-stage ScoredCluster into pursue/watch/discard.

    Built against evals/decide-classification.md — see that file and this
    module's docstring before changing DECIDE_SYSTEM_PROMPT.
    """
    client = client or anthropic.Anthropic()

    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=DECIDE_SYSTEM_PROMPT,
        tools=[CLASSIFY_DECISION_TOOL],
        tool_choice={"type": "tool", "name": "classify_decision"},
        messages=[{"role": "user", "content": _format_scored_cluster(cluster)}],
    )

    tool_use = next(b for b in response.content if b.type == "tool_use")
    fields = tool_use.input

    return DecideResult(
        cluster_id=cluster.cluster_id,
        decide_action=fields["decide_action"],
        rationale=fields["rationale"],
    )
