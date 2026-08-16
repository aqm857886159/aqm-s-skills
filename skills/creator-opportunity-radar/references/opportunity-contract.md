# Creator Opportunity Contract

## Input card

```json
{
  "asOfDate": "2026-08-17",
  "evidence": [
    {"id": "feedback-1", "sourceType": "community", "capturedAt": "2026-08-16", "sourceUrl": "local-or-public-evidence-link"}
  ],
  "opportunities": [{
  "id": "stable-opportunity-id",
  "title": "specific working title",
  "audienceTension": "who struggles, when, and consequence",
  "whyNow": "dated change that makes this timely",
  "whyNowDate": "2026-08-16",
  "evidenceIds": ["feedback-1", "paper-2", "video-3"],
  "promise": "what the audience will understand or achieve",
  "differentiation": "access, proof, perspective, workflow, or format",
  "formatHypothesis": "channel, format, length, and proof device",
  "validationAction": "smallest test before full production",
  "stopCondition": "evidence that should pause or reject the idea",
  "scores": {
    "relevance": 0,
    "timeliness": 0,
    "evidence": 0,
    "differentiation": 0,
    "feasibility": 0
  }
  }]
}
```

All scores use 0-5. Set `asOfDate` for deterministic ranking. Every evidence ID must resolve through the root evidence catalog; source diversity is derived from that catalog rather than trusted from the opportunity card. Preserve detailed evidence in its originating artifact; catalog entries are references, not substitutes for citations.

## Scoring anchors

- **0**: contradicted, irrelevant, or infeasible.
- **1**: weak relationship with major unresolved assumptions.
- **2**: plausible but evidence or fit is thin.
- **3**: useful candidate with a credible path and known gaps.
- **4**: strong, specific support and realistic delivery.
- **5**: unusually strong direct evidence or fit; explain why this is not score inflation.

Weights: relevance 30%, timeliness 20%, evidence 20%, differentiation 15%, feasibility 15%.

## Delivery card

For each recommended opportunity show:

1. rank, weighted score, and confidence;
2. audience tension and dated why-now;
3. promise and differentiated proof;
4. evidence IDs grouped by source type;
5. format and production requirements;
6. assumptions, risks, and evidence gaps;
7. validation action, success check, and stop condition.

End with a production portfolio rather than one winner by decimal score alone.
