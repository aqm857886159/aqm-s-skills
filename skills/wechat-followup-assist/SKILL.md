---
name: wechat-followup-assist
description: Turn an approved followup list (from wechat-group-insights or the user) into real replies inside the WeChat desktop app via computer-use UI automation, one message at a time with per-item user confirmation. Use when the user says 帮我把这几条回了、把跟进话术发到群里、用电脑帮我发微信、按周报跟进客户. Paste-first by default (the user presses send); the agent presses send only with explicit per-item authorization. Never bulk-broadcasts, never touches WeChat data or binaries, and falls back to a clipboard checklist when computer-use tools are unavailable.
---

# WeChat Followup Assist

Close the loop from report to action: take followup items the user already
saw, and place each approved reply into the right WeChat conversation. This
Skill automates the visible UI of the user's own logged-in WeChat desktop app
and nothing else.

## Workflow

1. Collect the followup items: from a `wechat-group-insights` insights JSON
   (`followups[].suggestedReply`) or from the user directly. Read
   [references/sending-safety.md](references/sending-safety.md) before any
   automation.
2. Present the plan as a numbered list — target group, recipient, exact final
   text — and ask the user to pick which numbers to send. Apply any wording
   edits the user requests, then show the final text again. What the user
   approved is what gets pasted, verbatim.
3. Ask the user to choose an execution mode:
   - **放入输入框（默认）**: the agent navigates and pastes; the user presses
     send for each message.
   - **代为发送**: the agent presses send, but only for items the user
     explicitly named after seeing the final text. General approval ("都发吧")
     covers pressing send only for the exact drafts already shown.
4. Check tooling: computer-use tools must be available and the user must grant
   access to WeChat when prompted. If unavailable, fall back to the clipboard
   checklist (step 8) instead of degrading silently.
5. For each approved item, one at a time and at a human pace:
   - bring WeChat to the foreground and screenshot to confirm the app state
     (logged in, no dialogs, no update prompts);
   - open search, type the exact group name, open the conversation;
   - **verify the open chat's title matches the target group exactly** in a
     fresh screenshot before touching the input box; on any mismatch or
     ambiguity, stop and ask;
   - place the approved text in the input box via the clipboard; do not
     retype or reword;
   - in default mode, stop here and tell the user this item is ready to send;
     in 代为发送 mode, press send, then screenshot to confirm the message
     appears in the conversation.
6. After each send attempt, record the outcome (sent / placed / skipped /
   failed and why). Never move on past a failed verification.
7. Report the per-item results in chat and suggest ticking 已跟进 on the
   report's followup cards. Offer to save a send log next to the insights file
   (outside Git, mode `0600`) if the user wants a record.
8. Clipboard fallback (no computer use): copy each approved reply to the
   clipboard one at a time, telling the user exactly which group to paste it
   into, and wait for their go-ahead between items.

## Hard limits

- At most 10 messages per run; one conversation at a time; no timers, no
  scheduled or unattended sending.
- Only conversations the user names. Refuse "发到我所有群" style broadcast and
  any marketing blast to groups the user does not operate — suggest per-group
  review instead.
- Send only to recipients whose messages prompted the followup, with content
  responsive to what they asked. No cold outreach lists.
- Never dismiss WeChat security prompts, login dialogs, or verification
  screens on the user's behalf — stop and hand control back.
- Never modify the WeChat app, read its databases (that is
  `wechat-chat-export`'s reviewed read-only path), install plugins, or use
  webhooks/protocol tricks. Visible UI automation of the user's own session
  only.
- If the user asks to send anything deceptive, harassing, or spammy, decline
  that content while continuing legitimate followups.

## Capability Boundary

The Skill can: navigate the WeChat desktop UI, find a named conversation,
paste approved text, optionally press send per explicit authorization, verify
results visually, and report honestly.

The Skill cannot: guarantee the UI layout of every WeChat version (it stops
when the screen does not match expectations); send while WeChat is logged
out; verify delivery beyond what is visible on screen; or make automated
sending risk-free — heavy automation of a personal account can look bot-like,
which is why paste-first is the default and batches stay small.

## Failure Handling

- Computer-use tools missing or access denied: use the clipboard fallback;
  never claim a message was sent.
- Group not found or multiple matches in search: stop, show what was found,
  let the user choose; never guess between similar group names.
- Chat title mismatch after opening: abort the item, screenshot, report.
- Send pressed but message not visible in the follow-up screenshot: report as
  unverified, do not retry automatically.
- WeChat shows a dialog, update screen, or logged-out state: stop the run and
  return control to the user.

## Final Check

Before finishing, verify:

- every sent or placed message matches a draft the user explicitly approved,
  word for word;
- 代为发送 was used only for items the user named after seeing the final text;
- the per-item outcome list distinguishes sent, placed-awaiting-send, skipped,
  and failed — with no unverified success claims;
- no broadcast behavior occurred and the 10-message cap was respected;
- any saved log lives outside Git worktrees with mode `0600`.
