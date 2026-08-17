# Sending Safety

Why this Skill is deliberately slower than it could be.

## The consent chain

A message leaves the user's account only after all four links hold:

1. the user saw the exact final text;
2. the user picked that specific item (a number, not a vibe);
3. the user chose the execution mode for this run;
4. for 代为发送, the user named the item again after the final text was shown.

If any link is missing, the correct behavior is to paste and wait, or to stop.
"他刚才说都行" does not satisfy link 4 for newly added or edited drafts.

## Why paste-first is the default

- **Account risk.** WeChat's terms do not welcome automation. A human pressing
  send after an agent pastes is materially different — in pace, in burst
  pattern, and in who made the final call. Small batches at human pace exist
  for the same reason.
- **Wrong-window risk.** The most damaging failure is a right message in a
  wrong group. That is why the chat-title check happens on a fresh screenshot
  after navigation, immediately before pasting, and why similar group names
  (1号院 vs 2号院) are never resolved by guessing.
- **Attribution.** Everything sent is in the user's name, to their real
  customers. The user owns the relationship; the agent only saves them the
  typing.

## What this Skill refuses by design

- Broadcasts: the same text to many groups, marketing sprays, "所有群都发一遍".
- Unattended operation: scheduled sends, retry loops, sending while the user
  is away.
- Content that misleads (fake urgency, invented stock or prices), harasses a
  non-responding customer, or impersonates anyone.
- Working around WeChat's own controls: dismissing security dialogs, logging
  in, automating verification, or touching app files and databases.

## Relationship to the other WeChat Skills

`wechat-chat-export` reads (risk-gated, read-only). `wechat-group-insights`
judges (local, evidence-verified). This Skill acts — which is exactly why it
holds the strictest consent rules of the three. Failure or refusal here never
justifies loosening the other two.
