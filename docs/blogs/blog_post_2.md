# Your eval score is probably broken, and you don't even know why

The most common approach to eval scoring is a scale from 0.0 to 1.0 per criterion. Seems reasonable: score each dimension for each input/output pair, roll it up, compare outcomes.

But your 0.1 and an LLM's 0.1 are almost certainly different things. How do you trust a score of 0.5 on some criterion when you'd have called it 0.2? You have to close that gap somehow.

Hand-labeling more examples is the start. From that data, an LLM can reverse-engineer your actual rationale. From there, you can turn the rationale into checklists that constrain the LLM-as-judge. Something subtle happens along the way: your seemingly numerical 0-1 scale — which was actually ordinal all along — becomes categorical. You just changed the entire nature of the eval.

Now it's probably more accurate and definitely more predictable. Is it the right measurement tool for your AI-first feature? Can't answer that for you. But I can show you how I approached it — including the parts that didn't go cleanly, because those are the more useful parts.

## The setup

I'm building a small eval harness that pulls posts from Stack Exchange and Hacker News and extracts unsolved cybersecurity pain points a small team could plausibly build a product around. The pipeline has two stages: Sense (is this a real, recurring problem?) and Discover (cluster related signals across posts/sources/days, then score whether the cluster is worth pursuing). Everything below is about scoring Discover-stage clusters — different schema, different rubric than the initial extraction step.

The scoring criteria for a cluster:

* small-team feasibility (buildable by 1-3 people, not "someone would need a whole regulator or platform vendor to fix this")
* willingness to pay
* novelty
* overall rank score (subjective by design, I know)

I hand-labeled 16 real clusters — pulled live, not invented, per the eval-is-the-spec discipline I'm following (https://falkster.com/handbook/the-eval-is-the-spec) — across all four dimensions, with written reasoning for each score. Ideally this would be more like 100+ pairs; 16 is what a non-production side project buys you. Keep that number in mind, it matters later. Then I had Claude Code build an LLM-as-judge scoring agent and run it against those labels.

## Round one: freehand floats, and where they broke

Version one just asked the model to freehand a 0-1 float, same as I had. The results were bad in an informative way: feasibility was off by 0.22 on average (mean absolute error, 0-1 scale), and the model's overall ranking agreed with mine on only 4 of 16 clusters. The systematic pattern: the model treated "a wrapper tool could technically be built around this" as high feasibility, when my actual bar was stricter — if the real fix needs an OS vendor, a browser vendor, a carrier, or a database engine's own internals to change, no wrapper makes it a small-team product.

My 0.1 on feasibility and the model's 0.1 were built on different assumptions. Neither of us was wrong. We were measuring different things and calling them the same name.

## Turning vibes into checklists

The fix: have Claude Code reverse-engineer my actual reasoning from all 16 rationales into an ordered checklist of concrete yes/no facts (does the fix require a platform vendor? does an incumbent already serve this exact need? is this a reliably-funded vertical like GRC or incident response?), then compute the score from the answers instead of asking the model to invent a number.

First pass at that: independent yes/no flags, first-match-wins. Feasibility got much better (0.22 → 0.09 MAE). Willingness to pay got worse (0.18 → 0.26). Turned out the checklist items weren't actually independent — they were different framings of the same decision, and the model kept marking several conflicting flags true, letting my first-match logic silently grab the wrong one. Fix: collapse each checklist into one mutually-exclusive choice instead of a pile of booleans. One decision, one answer, no conflicts possible.

That fixed willingness to pay (0.175) and broke feasibility again (0.181 — worse than the independent-boolean version) — a few boundary cases turned out to be genuinely ambiguous under an abstract rule alone. Every fix in isolation revealed a new failure mode. That's not the approach failing; that's what calibrating a subjective rubric against a real human actually looks like.

## Worked examples: progress, and a new kind of damage

Next fix: worked examples. Six real clusters, spelled out with the exact reasoning for why one boundary case applies and its lookalike neighbor doesn't — the same technique I'd already used for adversarial cases in the Sense-stage eval. Feasibility MAE down to 0.05 (13/16 exact matches). Willingness to pay down to 0.125. But I have to be straight about what that number means: those six examples are also six of my sixteen ground-truth rows. Scoring well against your own answer key doesn't prove generalization — it might just mean the model can follow an explicit example. With only 16 labeled clusters I don't have room for a real held-out test set, so I genuinely can't separate "learned the rule" from "memorized the example." No clean win, and I'm not going to pretend otherwise.

Worked examples also caused a specific, nameable failure: negative transfer. Two of my clusters were both "Cyber Essentials" compliance friction, but scored completely differently on willingness to pay — one was real, dollar-driving compliance pain (0.6), the other had zero signal at all (0.1). The moment I added the first one as a worked example, the model pattern-matched on the words "Cyber Essentials" and pushed the second cluster to 0.9 — an 0.8-point miss, the single worst error across every run I did. A worked example that fixes one case can bleed into a superficially similar one and actively make it worse.

## What I left alone, on purpose

Two dimensions I left alone, on purpose. `frequency_corroboration` was already a clean formula from day one — count of independent posts, bonus for spanning multiple sources, zero LLM judgment involved — and it never produced a single point of error across any run. It's the proof this whole approach works when a criterion is fully operationalized. `novelty`, on the other hand, I deliberately kept as a human-only call. Not a bug to fix later — an LLM doesn't get to certify its own novelty. That's exactly the kind of judgment this harness exists to keep a human in the loop on.

## The metric that didn't move

And the metric that actually matters — does the model's ranking of "best opportunity" agree with mine — barely moved across the whole exercise, even as the individual sub-scores got dramatically better. Better ingredients didn't automatically make a better final ranking, because `overall_rank_score` is still a freehand LLM number guided by prompt instructions, not a formula. That's the next thing to fix, not the thing I already fixed.

## Where that leaves things

So: a categorical scoring mechanism for two dimensions that now matches my judgment far better than a freehand float ever did, solid proof that "turn vibes into formulas" is the right instinct, and equally solid proof that doing this properly surfaces new failure modes faster than it resolves old ones. That's not a failure — that's what a real eval harness is supposed to do. Next up: either more hand-labeled data, so I can actually test generalization instead of memorization, or turning `overall_rank_score` into its own formula the same way I did the other two.
