---
name: community-feedback-radar
description: Merge and triage feedback from GitHub, Bilibili, WeChat-like exports, support logs, or other community sources into a privacy-aware evidence radar. Use whenever the user wants to consolidate comments, issues, chats, requests, complaints, or praise; identify repeated user problems; or says “整理用户反馈”“看看大家在抱怨什么”“把群聊和评论做成反馈雷达”.
license: MIT
compatibility: Normalization works offline with Python 3.9+ and JSON exports. Source collection is separate and may require the runtime's authorized connectors.
metadata:
  author: aqm857886159
  version: "0.1.0"
---

# Community Feedback Radar

## Mission

Turn scattered community messages into a traceable product or content decision without exposing people, flattening different sources, or pretending a partial sample represents the whole audience.

## Success bar

A strong radar:

- states which sources and time windows are included or missing;
- preserves a stable evidence ID and source link for every retained signal;
- redacts personal identity by default and quotes only what is necessary;
- separates bugs, requests, questions, praise, and noise;
- distinguishes repeated themes from isolated reports;
- produces an owner-ready next action without sending messages or changing external systems.

## Workflow

1. **Frame the decision.** Identify whether the user needs product triage, content questions, launch monitoring, support themes, or a change-over-time view. Define the relevant audience and time window.
2. **Inventory access.** List requested sources as available, unavailable, stale, or not authorized. Existing local data is not proof that its connector is still active. Never erase prior evidence merely because a connection disappeared.
3. **Collect read-only exports.** Use authorized runtime connectors or source-specific Skills to create bounded JSON exports. Keep raw private exports outside this repository and any shareable report.
4. **Normalize and redact.** From this Skill directory run `python3 scripts/merge_signals.py export-a.json export-b.json --output /tmp/feedback-evidence.json`. Authors are masked unless the user explicitly needs a local, restricted identity mapping.
5. **Inspect coverage.** Check source counts, input count, unique count, duplicates, oldest/newest evidence, and missing lanes before interpreting themes.
6. **Triage signals.** Read `references/radar-contract.md`. Give each signal one primary type: bug, feature request, question, praise, or noise. Add severity and confidence only when supported by the text and context.
7. **Cluster cautiously.** A repeated theme needs at least two distinct evidence IDs. Track source diversity separately: twenty replies in one thread are not twenty independent discoveries.
8. **Map action.** For each priority theme, name the affected workflow, evidence, open question, suggested owner, and the smallest validation or response action.
9. **Deliver the radar.** Lead with coverage and changes since the last run, then priority themes, representative redacted evidence, isolated signals, gaps, and next actions.

## Decision rules

- Connection state and retained data are different facts. Report both separately.
- A connector outage reduces current coverage; it does not invalidate previously captured evidence.
- Bugs describe observed or reproducible broken behavior. A user's proposed solution remains a request until the underlying need is verified.
- Frequency is not severity. One data-loss report may outrank a common cosmetic complaint.
- Cross-source recurrence raises confidence only when the sources are independently collected.
- Keep exact wording for evidence, but summarize themes in neutral language.
- If identity is necessary for support follow-up, keep the mapping in a restricted local artifact and exclude it from the shareable radar.

## Boundaries

- Do not extract encryption keys, bypass app protections, scrape private accounts, or access chats without the user's authority.
- Do not publish raw chat exports, usernames, email addresses, phone numbers, tokens, or private repository links.
- Do not reply, open Issues, assign owners, edit roadmaps, or change product state unless the user separately authorizes that action.
- Do not classify sentiment, urgency, or intent from a username or demographic assumption.
- Do not hide missing connectors, failed imports, sample limits, or stale capture times.

## Common failure modes

- Showing a polished theme board with no evidence IDs or coverage statement.
- Treating the loudest commenter as the largest customer segment.
- Merging duplicate cross-posts into a fake trend.
- Calling a connector “connected” because old rows are still visible.
- Keeping names in a report when the decision does not require identity.

## Gotchas

- GitHub's Issues API may include pull requests; filter them when the task is issue feedback.
- Bilibili comments are ordered and moderated by platform behavior; a bounded sample is not a random sample.
- Chat exports may contain quoted messages, forwarded content, bots, and duplicate sync records.
- The bundled normalizer accepts common JSON shapes but does not fetch data or determine triage labels.

## Final review

Before returning, verify:

- included and missing source lanes are visible;
- capture dates, sample limits, and deduplication counts are stated;
- every theme links to distinct evidence IDs;
- author identity is masked in shareable output;
- priority combines impact, recurrence, and confidence rather than frequency alone;
- proposed next actions do not imply they were already executed.

Use `references/radar-contract.md` for the final report and evidence schema.
