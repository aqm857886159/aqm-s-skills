---
name: wechat-group-insights
description: Turn wechat-chat-export JSON files into an evidence-verified, single-file HTML weekly report (客户群经营周报) that lists unanswered customer questions, buying signals, complaint risks, and a prioritized followup list with ready-to-paste replies. Use when the user asks to 分析客户群、生成群周报、看看谁没被回复、找购买意向或投诉、"上周群里漏了什么", or right after a WeChat export completes. Deterministic stats and rendering are script-based; every conclusion must cite an evidence ID that exists in the exports.
---

# WeChat Group Insights

Consume private exports produced by `wechat-chat-export` and deliver one
artifact: a weekly customer-group operations report the user can act on the
same morning. Judgments come from you; every fact in the report is derived
from the export files and verified at render time.

## Workflow

1. Locate the export JSON files (one per group). If there are none, or the
   user has never connected WeChat, route to `wechat-chat-export` first — do
   not analyze fixture data as if it were the user's chats, and do not reuse a
   stale export without telling the user its date range.
2. Confirm two inputs before judging:
   - which exported groups belong in this report;
   - the merchant's own display name(s) in those groups (needed to decide
     what counts as "no reply"). If exports are author-redacted, show the top
     `participant-…` senders per group and let the user identify themselves;
     suggest a `--keep-authors` re-export only when the user wants named
     followups and accepts keeping local identities.
3. Run the deterministic statistics next to the exports (never inside a Git
   worktree):

   ```bash
   python3 scripts/group_stats.py /private/exports/*.json --output /private/exports/stats.json
   ```

4. Read [references/insights-contract.md](references/insights-contract.md) in
   full, then read the export messages and write the insights JSON to the same
   private directory. The contract's hard rules override brevity: no claim
   without a real evidence ID, no invented numbers, replies that never promise
   what the merchant did not say.
5. Render the report:

   ```bash
   python3 scripts/render_report.py \
     --insights /private/exports/insights.json \
     --stats /private/exports/stats.json \
     --exports /private/exports/*.json \
     --output /private/exports/weekly-report.html
   ```

   The renderer verifies every cited evidence ID, computes all times and
   waiting badges itself, embeds quoted messages with expandable context, and
   writes a self-contained `0600` HTML file. `--allow-inside-git` exists only
   for the synthetic demo fixtures in `evals/files/`.
6. If rendering fails with `unknown_evidence`, fix the insights file by
   removing or re-grounding the claim. Never fabricate an ID, never edit the
   renderer, never bypass the check.
7. Deliver in chat, briefly: the headline, the single most valuable followup,
   the most urgent risk, then `open` the report file for the user. Do not
   paste the full lists, message bodies, or participant rosters into chat.
8. Offer the two natural next steps: send replies from the followup list with
   `wechat-followup-assist` (per-item confirmation), and schedule the same
   export-plus-report run for next week.

## Chat delivery shape

```text
本周结论：<headline 一句话>
最值得马上做：<followup #1 标题>（建议话术已放进报告）
最需要灭火：<最高风险一条>
报告已生成：open /private/exports/weekly-report.html
要我帮你把跟进话术逐条发出去吗？（每条都会先经你确认）
```

## Privacy Defaults

- Keep stats, insights, and the report in the same private directory as the
  exports; never write any of them inside a Git worktree (the scripts refuse).
- The report embeds message excerpts; treat it like the export itself. It is
  written `0600` and must not be uploaded or shared without the user deciding
  to.
- Do not quote message bodies in the chat response beyond the single headline
  facts; the report is the place for quotes.
- Never modify the export files.

## Capability Boundary

The Skill can:

- compute per-group volume, participants, per-day activity, and message-type
  counts deterministically;
- judge unanswered questions, buying signals, and complaint risks from
  exported text, and draft replies in the merchant's voice;
- render a fixed-design, self-contained HTML report with verified evidence
  quotes, expandable context, copyable replies, and local done-checkboxes;
- state coverage, truncation, decode failures, and blind spots honestly.

The Skill cannot:

- read voice, image, or video content (exports carry markers only) or claim
  those messages were analyzed;
- see messages outside the exported groups and window, or prove a question was
  answered in a private chat;
- send messages, follow up, or write anything back to WeChat (that is
  `wechat-followup-assist`, with its own consent gates);
- rank groups by revenue or make claims the cited messages do not support.

## Failure Handling

- No export files: route to `wechat-chat-export`; do not improvise from
  memory or fixtures.
- `unknown_evidence`: remove or re-ground the claim; re-render.
- `unsafe_output`: choose a private path outside every Git worktree.
- Export `truncated` or `decodeFailures > 0`: keep going, but the gaps section
  and the chat summary must say what is missing.
- Merchant identity unclear: ask; wrong identity flips "answered" and
  "unanswered".
- An empty week (no unanswered questions, no risks) is a valid, reportable
  result — render it and say so plainly.

## Final Check

Before finishing, verify:

- the report came from a real `render_report.py` run on the user's own
  exports (not fixtures), and the run reported `evidenceVerified` equal to
  `evidenceCited`;
- the report file exists outside Git with mode `0600` and opens locally;
- the chat reply contains the headline and file path but no bulk message
  content, keys, database paths, or raw chatroom IDs;
- every followup card in the report carries at least one evidence quote and a
  reply that promises nothing the merchant never said;
- coverage, truncation, unreadable-media, and unexported-channel gaps are
  visible in the report's boundary section.
