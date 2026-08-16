---
name: creator-opportunity-radar
description: Synthesize audience feedback, creator/competitor content, repository capabilities, and current research into ranked, evidence-backed content or product opportunities. Use whenever the user asks what to make next, wants topic selection or creator positioning, needs to combine research into opportunity cards, or says “下一个选题做什么”“找内容机会”“结合评论和趋势给我方向”.
license: MIT
compatibility: Ranking works offline with Python 3.9+ and structured JSON. Evidence collection may use other installed research Skills and authorized public sources.
metadata:
  author: aqm857886159
  version: "0.1.0"
---

# Creator Opportunity Radar

## Mission

Find the few content or product opportunities where a real audience tension, a timely reason, differentiated evidence, and the creator's ability to deliver overlap. The output is a decision portfolio, not a trend list or an automatic content mill.

## Success bar

A strong radar:

- starts from the creator's audience, promise, strengths, constraints, and current goals;
- preserves evidence IDs from independent source lanes;
- states the audience tension and why now in concrete terms;
- distinguishes an opportunity from a ready-to-publish claim;
- ranks a small portfolio by relevance, timeliness, evidence, differentiation, and feasibility;
- assigns a cheap validation action and a stop condition to each top opportunity.

## Workflow

1. **Define the creator system.** Establish audience, existing promise, formats, channels, strengths, prohibited topics, production capacity, and current objective. One person may be researcher, builder, teacher, founder, and creator; do not force one permanent persona.
2. **Build evidence lanes.** Use available research Skills or user-provided artifacts. Typical lanes are community questions, creator/competitor content, product/repository capability, current papers/news, and prior performance. Keep provenance and capture dates.
3. **Find tensions, not keywords.** Look for costly misunderstandings, repeated unanswered questions, changing capabilities, newly feasible demonstrations, and gaps between what people want and what existing content proves.
4. **Draft opportunity cards.** Read `references/opportunity-contract.md`. Each card needs title, audience tension, why now, evidence IDs, source types, a differentiated promise, format hypothesis, feasibility, risk, and validation action.
5. **Check independence.** Three comments in one thread remain one source type. A competitor repeating a paper claim is not independent confirmation of the claim.
6. **Score explicitly.** Put 0-5 values for relevance, timeliness, evidence, differentiation, and feasibility into JSON, then run `python3 scripts/rank_opportunities.py opportunities.json --output /tmp/ranked-opportunities.json`.
7. **Challenge the ranking.** Inspect rejected cards and gaps. A high weighted score without independent evidence remains low confidence. Keep one exploratory bet when its learning value is high, but label it.
8. **Build a portfolio.** Default to three choices: one reliable audience need, one timely differentiated bet, and one low-cost experiment. Avoid six near-identical topics competing for the same production slot.
9. **Deliver.** Lead with the recommended portfolio, then evidence cards, confidence/gaps, discarded ideas, and the next validation sequence. Do not publish or schedule content.

## Decision rules

- Audience tension must name who struggles, in what situation, and what the consequence is.
- “Why now” needs a dated change: new capability, release, regulation, behavior, event, or evidence. General popularity is not enough.
- High confidence requires at least three evidence IDs across two independent source types and a weighted score of 4 or above.
- Relevance asks whether the opportunity serves the creator's audience and promise, not whether the topic is broadly popular.
- Differentiation should come from access, proof, perspective, workflow, or format; novelty wording alone does not count.
- Feasibility includes rights, source access, production time, technical cost, and the ability to demonstrate the claim honestly.
- Separate scoring from judgment. The script sorts valid cards; the Agent explains tradeoffs and may recommend a lower-scored learning bet with a reason.

## Boundaries

- Do not invent trend volume, audience demand, competitor performance, or evidence IDs.
- Do not treat personal or private chat data as publishable quotes.
- Do not recommend copying another creator's script, thumbnail, voice, footage, or identity.
- Do not turn preliminary research into medical, financial, legal, or other high-stakes advice without appropriate evidence and review.
- Do not post, schedule, message collaborators, buy ads, or change a content calendar without separate user authorization.

## Common failure modes

- Repackaging trending keywords as audience opportunities.
- Scoring ideas before defining the creator's actual constraints.
- Counting many records from one source as independent validation.
- Ranking only safe ideas and offering no learning bet.
- Giving a title list with no proof, production fit, or stop condition.

## Gotchas

- Platform metrics are affected by distribution, age, creator scale, and format; they are not direct measures of unmet need.
- Recent research may create a timely demonstration but still be too immature for an instructional claim.
- Community questions can reflect onboarding/documentation gaps rather than demand for a full new product or content series.
- The bundled ranker validates and sorts structured cards. It does not collect evidence, judge source quality, or write the creative concept.

## Final review

Before returning, verify:

- creator context and production constraints are stated;
- every top card has a concrete audience tension and dated why-now;
- confidence matches independent source diversity and evidence count;
- scoring inputs are visible and gaps are not hidden;
- the portfolio balances reliability, differentiation, and learning value;
- validation actions are reversible and no publishing action was taken.

Use `references/opportunity-contract.md` for input fields and the delivery format.
