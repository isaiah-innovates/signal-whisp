Your eval score is probably broken, and you don’t even know why. 

The most common approach to eval scores is a scale from 0.1 to 1.0 on relevant criteria. Seems reasonable. Score each criterion for each input/output pair numerically, and get an overall numerical result that lets you compare outcomes. 

But your 0.1 and an LLM's 0.1 are almost certainly different! How can you trust an eval system that scores criterion A = 0.5 when you would score it at 0.2? You have to address that gap somehow.

Hand-labeling more input/output pairs is the start. From that data, an LLM can reverse-engineer your rationale. From there, you can turn it into checklists that reflect your beliefs for the LLM-as-judge. Something subtle happens along the way: your seemingly numerical scale from .1 - 1, which is actually ordinal, becomes categorical. You just changed the entire nature of the eval harness! 

Now, it’s probably more accurate and definitely more predictable, but is it the right measurement tool for the quality of your AI-first feature? I can’t answer that for you. But I can show you how I approached it. 

I’m building a simple eval harness example that takes posts from Stack Exchange, Hacker News, and other sources and pulls out signals of unsolved problems that could be addressed with a new solution. 

Criteria like these are all categories that make sense in my signal extraction schema, among others:

* feasibility (could a team of 1 approach it?)
* willingness to pay
* novelty
* overall score (crazy subjective, I know)

Using Claude Code, I built a system with scripts that pull posts and extract signals. I hand-labeled the evals and ran the harness. Then I noticed the problem: my 0.1 on feasibility was based on completely different assumptions than the LLMs.

To address it, I had Claude Code reverse-engineer my approach into a set of reusable checklists that act as gates when evaluating each criterion. For instance, feasibility and willingness to pay became stepwise checks that led to categorical values (.2, .6, etc.).

Correctly, Claude Code converted the willingness/feasibility checklists from independent booleans to single, mutually exclusive tier choices (the previous design let the model set conflicting flags to true and let first-match-wins silently pick the wrong tier -yikes!).

One thing of note: I was targeting 20 input/output pairs for what “good” looks like, as well as a few failure modes. (I’m applying Falkster’s eval-as-spec approach found here: https://falkster.com/handbook/the-eval-is-the-spec). Ideally, this system would have over 100 pairs. More data would be helpful too, because it would mean a richer eval rubric when reverse-engineering the criteria. But it’s not a real product, so I didn’t want to spend the time hand-labeling 100 things. :D As a result, I can't fully separate "generalizes" from "memorized the example." So, no clear win. 

The end result is a nominal (categorical) scoring mechanism that more closely matches my judgment. Assuming I have good judgment- and we must be careful on that one- I have a more accurate eval harness that has fewer broken measurement techniques. yay! 

It’s not perfect, and I’m working on a model that changes how this works to make the eval process stronger. But it will have to do for now.