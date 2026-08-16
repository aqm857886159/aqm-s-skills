# Feedback Radar Contract

## Evidence record

Keep one normalized record per unique signal:

```json
{
  "id": "source-stable-hash",
  "source": "github|bilibili|wechat|support|unknown",
  "sourceId": "source-native-id-or-null",
  "author": "a***z",
  "text": "minimal evidence text",
  "createdAt": "ISO-8601-or-null",
  "url": "source-link-if-shareable",
  "context": "thread, release, or product surface"
}
```

Do not add inferred labels to the evidence file. Keep interpretation in the radar so the raw normalized layer can be re-evaluated.

## Radar sections

1. **Scope and coverage**: decision, capture time, included/missing sources, time window, limits, input/unique/duplicate counts, privacy mode.
2. **What changed**: new, growing, shrinking, resolved, or unknown themes compared with a named prior snapshot. Omit when there is no comparable baseline.
3. **Priority themes**: type, impact, recurrence, source diversity, confidence, evidence IDs, affected workflow, and recommended validation.
4. **Isolated signals**: high-impact single reports and unconfirmed observations. Keep them visible but do not call them trends.
5. **Gaps and bias**: connector failures, inaccessible threads, sampling/order effects, stale sources, or missing user segments.
6. **Next actions**: owner suggestion, smallest reversible action, and success evidence. Clearly mark all actions as proposed.

## Theme confidence

- **High**: direct, unambiguous evidence from at least two independent source types, or a reproducible defect plus user evidence.
- **Medium**: at least two distinct signals with adequate context, but only one source type or an unresolved causal question.
- **Low**: one signal, ambiguous wording, missing context, or likely duplicate/community amplification.

Never convert confidence into a fake numeric precision. Identity and engagement counts do not establish truth.
