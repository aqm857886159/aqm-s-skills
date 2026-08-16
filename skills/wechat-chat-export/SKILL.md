---
name: wechat-chat-export
description: Set up and export authorized local WeChat 4.x group-chat records on Apple Silicon macOS into private, structured JSON. Use when the user starts without a connection or key, asks how to connect AI to their own WeChat, needs a risk-reviewed key setup, wants to verify current access, or asks to export, read, archive, search, or analyze local chats; including "接入微信", "导出微信聊天记录", "读取微信群", "检查微信能不能导出", and "把群聊交给 AI 分析". Includes an explicit-consent, manual high-risk setup path and a read-only exporter; never run privileged capture automatically.
---

# WeChat Chat Export

Take a user from no connection to a verified local export. Treat analysis, feedback triage, and summarization as downstream work that must consume the exported artifact.

## Workflow

1. Confirm that the user is exporting data they are authorized to access. Keep processing local.
   State plainly: first-time key setup is a high-risk, unsupported debugging workflow. Do not recommend trying it for casual use; continue only when the user has a necessary, lawful purpose and personally accepts the risks.
2. Run the zero-to-one setup check:

   ```bash
   python3 scripts/wechat_setup.py check
   ```

   If `status` is `ready_to_export`, skip key capture. Never recapture a working key.
3. If `status` is `manual_risk_setup_available`, read [references/security-and-setup.md](references/security-and-setup.md) in full and show the user all returned warnings. Do not proceed by interpreting general approval as risk acknowledgement.
4. Show the non-mutating preparation plan:

   ```bash
   python3 scripts/wechat_setup.py prepare
   ```

   The plan creates and ad-hoc signs a user-directory copy; it must never modify `/Applications/WeChat.app`. Only the user may decide to rerun with `--execute --ack-risk I_ACCEPT_WECHAT_ACCOUNT_AND_PRIVACY_RISKS`. Never supply that acknowledgement on the user's behalf.
5. After the user personally prepares, launches, and signs in to exactly one debug copy, generate the capture command with `python3 scripts/wechat_setup.py capture-command`. Show it and stop. The user must personally run the printed `sudo lldb` command, then sign out and sign back in while LLDB is waiting; opening chats alone does not reliably trigger key derivation. The Skill must not execute LLDB or account actions through an agent tool.
6. After the user reports completion, run the readiness check:

   ```bash
   python3 scripts/wechat_export.py doctor
   ```

   Continue only when `status` is `ready`. Do not treat a generated key file or old JSON export as proof that current contact and message databases work.

7. If the target group is unclear, list a bounded set of names:

   ```bash
   python3 scripts/wechat_export.py list-chats --match "group keyword"
   ```

   Keep names out of shared logs and reports. If names collide, use the returned opaque `conversationId`.

8. Export a specific range to a location outside every Git worktree:

   ```bash
   python3 scripts/wechat_export.py export \
     --group "exact group name" \
     --since "2026-08-01T00:00:00+08:00" \
     --until "2026-08-17T23:59:59+08:00" \
     --limit 5000 \
     --output /private/output/wechat-export.json
   ```

   Prefer a date range plus an explicit limit. Use `--all` only when the user clearly requests the full matching history. Use `--force` only after confirming that replacing the named export is intended.

9. Report the export summary: destination, exported/available counts, truncation, date range, decode failures, author-redaction state, and media limitations. Do not paste message bodies or participant identifiers into the response unless the user explicitly requests them.
10. Pass the JSON path to the downstream analysis Skill. Preserve the source artifact until the requested work is complete, then follow the user's retention preference.

## Privacy Defaults

- Keep sender identifiers stable but pseudonymous by default.
- Add `--keep-authors` only when the user explicitly needs local identity for an authorized workflow.
- Write exports with file mode `0600`.
- Refuse output paths inside Git worktrees.
- Never print database keys, database paths, raw chatroom IDs, or media AES keys.
- Never upload the export or send messages back to WeChat without separate user authorization.
- Never run `sudo`, LLDB capture, risk acknowledgement, or WeChat launch/quit actions on the user's behalf.

## Capability Boundary

The Skill can:

- diagnose a from-zero Apple Silicon macOS environment;
- present a reviewed debug-copy and CommonCrypto login-time passphrase capture method with explicit consent gates;
- verify that existing contact and message keys decrypt current databases;
- list group names and opaque conversation IDs;
- export text, image/video/voice markers, quote/link summaries, timestamps, stable evidence IDs, and image MD5 metadata;
- filter by time and limit, show coverage, and disclose decoding gaps.

The Skill cannot:

- guarantee that key capture works on a new WeChat/macOS version or Intel Mac;
- make key capture safe, compliant, or account-risk-free merely because warnings were shown;
- perform privileged capture autonomously or accept its risks for the user;
- decrypt WeChat 4.x media files or claim that an image marker contains the image pixels;
- prove that a sample is complete when `truncated` is true or decode failures are nonzero.

Read [references/security-and-setup.md](references/security-and-setup.md) when `doctor` is not ready, the user asks how keys work, media is required, or an export will be shared.

## Failure Handling

- `missing_key_bundle`: return to `wechat_setup.py check`; offer only the documented risk-gated setup path.
- `unsupported_platform`: explain that the reviewed capture register map currently supports Apple Silicon only; do not guess register mappings.
- `risk_not_acknowledged`: stop. Never generate the acknowledgement automatically.
- `no_match` or `partial` after manual capture: preserve the diagnostic, run `doctor`, and do not claim connection success.
- `decryption_failed`: the key bundle does not verify against the current databases. Report this as a connection/readiness failure; do not delete retained exports.
- `ambiguous_chat`: run `list-chats` and retry with `conversationId`.
- `message_table_not_found`: report that the contact was found but message storage was not; do not return an empty export as success.
- `decodeFailures > 0`: keep the successful messages, mark coverage partial, and recommend installing a supported zstd backend when relevant.
- `mediaFileDecryption: false`: state that media messages were located but their files were not exported.

## Final Check

Before finishing, verify:

- the result came from a real `export` run, not only a fixture or old JSON;
- a from-zero setup claim distinguishes dry-run/pure-function tests from a manually executed privileged capture;
- the output exists outside Git, has mode `0600`, and parses as JSON;
- `coverage.exportedCount` equals the number of `messages`;
- truncation, decode failures, author handling, and media-file limitations are visible;
- no key, raw database path, raw chatroom ID, or media AES key appears in the artifact or response.
