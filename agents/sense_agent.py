"""Sense-stage extraction agent.

Reads one normalized post (sources/models.py:Post) and decides whether it
contains a genuine, recurring cybersecurity pain point — extracting it into
structured fields if so. Built against evals/signal-extraction.md; any prompt
change here should be checked against that file's labeling criteria (§2) and
adversarial cases (§5) first.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import anthropic

from sources.models import Post

MODEL = os.environ.get("SENSE_AGENT_MODEL", "claude-sonnet-5")

SYSTEM_PROMPT = """\
You are a cybersecurity market-opportunity analyst. You read a single post \
from Stack Exchange or Hacker News and decide whether it states a genuine, \
recurring cybersecurity operational pain point worth tracking as a market \
signal.

is_signal = true requires ALL of:
- A specific, recurring problem — not a one-off incident or a single \
  question about something that already happened to the poster.
- Stated by someone who actually does the work day-to-day — not a student, \
  someone studying for a certification, a recruiter, or a vendor pitching \
  their own product.
- Enough detail that a PM could tell what "solved" would look like.

is_signal = false covers: career/certification/homework/interview-prep \
questions; venting with no specific extractable problem; vendor or \
marketing content (including "Show HN"/"Launch HN" posts, or posts that \
build toward promoting the poster's own product/side project) disguised as \
a question or complaint; pure news-sharing or acquisition announcements \
with no personal operational pain attached; one-off personal incident \
investigations ("did I get hacked", "is this a scam") with no recurring \
workflow gap; conceptual "how does X work" questions with no stated pain.

When is_signal is true, extract:
- problem_statement: one sentence a PM could hand to an engineer — not a \
  paraphrase of the title. Be specific about what's broken or missing.
- affected_role: who has this problem (role + rough team/company context if \
  stated).
- current_workaround: what the poster is doing today to cope, if anything.
- workaround_type: "manual" if a human process, "ai_tool_hack" if they're \
  improvising with an LLM/AI tool not built for this, "none" if no \
  workaround is stated.
- corroboration_signal: what in the post's own replies (if any) supports \
  this being a real, shared problem rather than a one-off. Weight a Stack \
  Exchange accepted or highly-voted answer more heavily than an HN comment \
  agreeing in passing. If there are no replies, say so explicitly rather \
  than inventing corroboration.
- confidence: your own calibrated confidence (0.0-1.0) that this is a real, \
  fresh market opportunity — not a stand-in for anything else.

Handle these patterns deliberately rather than missing them:
- A problem that's already a mature, well-solved product category restated \
  (e.g. "where do I store shared secrets" answered by "use a password \
  vault") — label is_signal false or use low confidence; it isn't a fresh \
  opportunity.
- Sarcastic or joking tone with no concrete ask — do not extract a literal \
  problem statement; label is_signal false.
- A polished, well-written complaint with no independent corroborating \
  replies that reads as if it's building toward the poster promoting their \
  own tool or side project — treat this as likely self-promotion. If the \
  self-promotional framing is clear-cut, label is_signal false rather than \
  a discounted true.
- A post that mixes a real operational problem with unrelated venting or \
  frustration — extract only the operational pain point, not the emotional \
  framing.
- An ambiguous, non-English, or heavily jargon-coded post where you can't \
  confidently tell what's being asked — use low confidence rather than a \
  forced guess at a problem statement.

You are given one post at a time. You are not responsible for deduplicating \
against other posts — that happens downstream during clustering.\
"""

EXTRACT_SIGNAL_TOOL = {
    "name": "extract_signal",
    "description": (
        "Record the signal-extraction decision and, if is_signal is true, "
        "the extracted fields for this post."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "is_signal": {
                "type": "boolean",
                "description": "Whether this post states a genuine, recurring cybersecurity pain point.",
            },
            "problem_statement": {
                "type": ["string", "null"],
                "description": "A PM-ready sentence describing the problem. Null if is_signal is false.",
            },
            "affected_role": {
                "type": ["string", "null"],
                "description": "Who has this problem. Null if is_signal is false.",
            },
            "current_workaround": {
                "type": ["string", "null"],
                "description": "What the poster does today to cope. Null if is_signal is false or none stated.",
            },
            "workaround_type": {
                "type": ["string", "null"],
                "enum": ["manual", "ai_tool_hack", "none", None],
                "description": "Category of current_workaround.",
            },
            "corroboration_signal": {
                "type": ["string", "null"],
                "description": "What in the post's replies supports this being a real, shared problem.",
            },
            "confidence": {
                "type": "number",
                "description": "Calibrated confidence, 0.0-1.0, that this is a real, fresh market opportunity.",
            },
        },
        "required": [
            "is_signal",
            "problem_statement",
            "affected_role",
            "current_workaround",
            "workaround_type",
            "corroboration_signal",
            "confidence",
        ],
        "additionalProperties": False,
    },
}


@dataclass
class ExtractionResult:
    permalink: str
    source: str
    is_signal: bool
    problem_statement: str | None
    affected_role: str | None
    current_workaround: str | None
    workaround_type: str | None
    corroboration_signal: str | None
    confidence: float


def _format_post(post: Post) -> str:
    replies = "\n\n".join(
        f"Reply {i}: {r}" for i, r in enumerate(post.top_replies, 1)
    ) or "(no replies)"
    return (
        f"Source: {post.source} ({post.subforum})\n"
        f"Title: {post.title}\n"
        f"Score: {post.score}, replies: {post.num_replies}\n\n"
        f"Body:\n{post.body}\n\n"
        f"{replies}"
    )


_REQUIRED_FIELDS = EXTRACT_SIGNAL_TOOL["input_schema"]["required"]
_MAX_ATTEMPTS = 3


def extract_signal(post: Post, client: anthropic.Anthropic | None = None) -> ExtractionResult:
    """Run the Sense-stage extraction agent against a single normalized post.

    Retries on a truncated/malformed tool call (seen intermittently as a
    KeyError on a missing field like 'is_signal') rather than failing the
    whole post outright: a long post's extraction can occasionally run the
    model right up against max_tokens, cutting off the tool-call JSON
    mid-write. max_tokens is set with headroom above the ~550-590 tokens a
    normal call uses, but a retry-with-validation is a cheaper, safer fix
    than pushing the ceiling up indefinitely.
    """
    client = client or anthropic.Anthropic()

    last_error: Exception | None = None
    for _attempt in range(_MAX_ATTEMPTS):
        response = client.messages.create(
            model=MODEL,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            tools=[EXTRACT_SIGNAL_TOOL],
            tool_choice={"type": "tool", "name": "extract_signal"},
            messages=[{"role": "user", "content": _format_post(post)}],
        )

        tool_use = next((b for b in response.content if b.type == "tool_use"), None)
        fields = tool_use.input if tool_use is not None else {}
        missing = [f for f in _REQUIRED_FIELDS if f not in fields]
        if not missing:
            return ExtractionResult(
                permalink=post.permalink,
                source=post.source,
                is_signal=fields["is_signal"],
                problem_statement=fields["problem_statement"],
                affected_role=fields["affected_role"],
                current_workaround=fields["current_workaround"],
                workaround_type=fields["workaround_type"],
                corroboration_signal=fields["corroboration_signal"],
                confidence=fields["confidence"],
            )
        last_error = ValueError(
            f"extract_signal: tool call missing required field(s) {missing} "
            f"for {post.permalink} (stop_reason={response.stop_reason})"
        )

    raise last_error
