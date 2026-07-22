# The bug that looked like a data problem

I pulled 53 Hacker News posts across 12 security-adjacent search queries — alert fatigue, SIEM, vulnerability management, that kind of thing — and ran them through my signal-extraction agent. One came back as a real signal. One out of fifty-three.

The tempting story writes itself: *turns out cybersecurity practitioner pain isn't that common on Hacker News, or my extraction criteria are too strict, or this whole market is thinner than I thought.* I almost wrote that down as a finding.

Instead I looked at the code.

I was calling Hacker News's Algolia search with `by_date=True`, reasoning that I wanted results spread across different days to prove the same pain point shows up more than once, on more than one occasion. Sorting by date seemed like the obvious way to get that spread.

What `by_date=True` actually does is disable relevance ranking entirely. It's not "relevance, tie-broken by date" — it's pure recency, full stop. My twelve carefully chosen search queries were doing almost nothing; the API was just handing back whatever was posted most recently, whether or not it matched. Fifty-two irrelevant recent stories and one that happened to be about SIEM by coincidence.

Switched one keyword argument, `by_date=False`, back to relevance ranking. Signal count went from 1 to double digits immediately. And the date spread I actually wanted was never in danger — relevance-ranked results still span days, weeks, years, because the *matching* posts were written whenever they were written. I didn't need to sort by date to get date diversity; I needed to stop throwing away relevance to get it.

Here's the part worth generalizing: an extraction agent auditing each of those 53 posts one at a time will confidently, correctly say "not a signal" 52 times. Each individual judgment is true. The bug isn't visible anywhere in the per-item output — every single verdict is defensible. It's only visible at the aggregate level, where the retrieval step upstream of the model was quietly broken and nobody was looking at *that* layer, because the model's job was to judge posts, not to judge whether the batch of posts it received made sense.

When an agentic pipeline returns almost nothing, or almost everything, resist the pull toward "interesting finding about the world" before you've ruled out "boring bug in my retrieval code." The fix here took thirty seconds. The wrong conclusion would have gone straight into an eval file as if it were ground truth about the market.
