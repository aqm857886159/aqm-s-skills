# Insights Contract

The weekly report is produced in two strictly separated layers:

- **The Skill (LLM) judges**: which questions went unanswered, what counts as a
  buying signal or a risk, what to do about each, and how to say it.
- **Scripts state facts**: message counts, timestamps, weekday names, waiting
  durations, quotes, and context all come from the export files at render time.
  The renderer rejects the whole report if any cited evidence ID does not exist.

Never put a fact in the insights file that the renderer can derive. Never cite
an evidence ID you have not seen in an export file.

## File shape (`schemaVersion: 1`)

```json
{
  "schemaVersion": 1,
  "merchant": "store or operator name shown in the masthead",
  "period": {"since": "YYYY-MM-DD", "until": "YYYY-MM-DD", "label": "human label"},
  "headline": "one- or two-sentence weekly conclusion",
  "followups": [
    {
      "who": "display name as it appears in the export",
      "group": "group name as it appears in the export",
      "title": "action-oriented card title",
      "category": "intent | question | risk",
      "reason": "why this is worth doing today, grounded in the cited messages",
      "suggestedReply": "ready-to-paste reply in the merchant's voice",
      "evidence": ["wechat-…", "…"]
    }
  ],
  "unansweredQuestions": [{"who", "group", "summary", "evidence"}],
  "buyingSignals": [{"who", "group", "summary", "estimate?", "evidence"}],
  "risks": [{"who", "group", "summary", "severity": "high|medium|low", "status", "evidence"}],
  "groupNotes": [{"group", "note"}],
  "gaps": ["known blind spots of this report"]
}
```

## Hard rules

1. **Every item cites evidence.** At least one `evidence` ID per followup,
   question, signal, and risk. The renderer aborts on unknown IDs; fix the
   claim, never invent an ID and never bypass the check.
2. **`who` and `group` must match the export exactly** (including
   `participant-…` pseudonyms when authors are redacted). Do not "clean up"
   names.
3. **No invented numbers.** An `estimate` may only restate quantities and
   prices that appear in cited messages (20 盒 × 100 元 → 约 2000 元 is
   arithmetic, not invention). If the messages contain no numbers, omit
   `estimate`.
4. **No invented dates or waits.** Do not write "已等 N 天" style claims with
   concrete numbers unless you verified them against message timestamps; the
   renderer computes and displays waiting badges itself.
5. **`suggestedReply` may not promise what the merchant never said**: no
   invented prices, stock, delivery dates, or compensation amounts. When a
   price is unknown, the reply should promise to follow up with one, not state
   one.
6. **Unanswered means unanswered in the data.** Only claim a question got no
   reply if no plausible answer from the merchant appears after it inside the
   exported window. When the merchant's own display name is ambiguous, confirm
   it with the user before judging reply status.
7. **Bounded output**: at most 5 `followups`, ordered by priority; keep the
   three lists to what the evidence supports, not a fixed quota. Empty lists
   are valid and worth reporting.
8. **`gaps` is mandatory honesty**: voice/image/link messages that could not be
   read, truncated coverage, decode failures, and groups or channels not
   exported all belong there.

## Judgment guidance

- A question from a customer that the merchant answered late is still
  answered; do not pad the unanswered list.
- A buying signal is a concrete want (product + quantity, a standing "有货@我",
  an invoice/pricing question from a company buyer) — not general chatter.
- Risk severity: `high` when unresolved and customer-visible (public
  complaint, repeated pings); `low` when already handled and you are only
  recommending follow-through.
- Followup priority: money at risk first (large orders, unresolved
  complaints), then oldest waiting customers.
