---
name: wechat-chat-export
description: Export authorized local WeChat 4.x group-chat records on macOS from an existing per-database key bundle into private, structured JSON. Use when the user asks to export, read, archive, search, or analyze their own local WeChat chats; verify whether WeChat records are actually exportable; list available groups; create a bounded date-range export; or says "导出微信聊天记录", "读取微信群", "检查微信能不能导出", or "把群聊交给 AI 分析". This Skill does not acquire keys, modify or attach to WeChat, decrypt media files, or upload chat data.
---

# WeChat Chat Export

Export real records first. Treat analysis, feedback triage, and summarization as downstream work that must consume the exported artifact.

## Workflow

1. Confirm that the user is exporting data they are authorized to access. Keep processing local.
2. Run the readiness check:

   ```bash
   python3 scripts/wechat_export.py doctor
   ```

   Read the structured result. Continue only when `status` is `ready`. Do not treat an old JSON export as proof that the current database connection works.

3. If the target group is unclear, list a bounded set of names:

   ```bash
   python3 scripts/wechat_export.py list-chats --match "group keyword"
   ```

   Keep names out of shared logs and reports. If names collide, use the returned opaque `conversationId`.

4. Export a specific range to a location outside every Git worktree:

   ```bash
   python3 scripts/wechat_export.py export \
     --group "exact group name" \
     --since "2026-08-01T00:00:00+08:00" \
     --until "2026-08-17T23:59:59+08:00" \
     --limit 5000 \
     --output /private/output/wechat-export.json
   ```

   Prefer a date range plus an explicit limit. Use `--all` only when the user clearly requests the full matching history. Use `--force` only after confirming that replacing the named export is intended.

5. Report the export summary: destination, exported/available counts, truncation, date range, decode failures, author-redaction state, and media limitations. Do not paste message bodies or participant identifiers into the response unless the user explicitly requests them.
6. Pass the JSON path to the downstream analysis Skill. Preserve the source artifact until the requested work is complete, then follow the user's retention preference.

## Privacy Defaults

- Keep sender identifiers stable but pseudonymous by default.
- Add `--keep-authors` only when the user explicitly needs local identity for an authorized workflow.
- Write exports with file mode `0600`.
- Refuse output paths inside Git worktrees.
- Never print database keys, database paths, raw chatroom IDs, or media AES keys.
- Never upload the export or send messages back to WeChat without separate user authorization.

## Capability Boundary

The exporter can:

- verify that existing contact and message keys decrypt current databases;
- list group names and opaque conversation IDs;
- export text, image/video/voice markers, quote/link summaries, timestamps, stable evidence IDs, and image MD5 metadata;
- filter by time and limit, show coverage, and disclose decoding gaps.

The exporter cannot:

- obtain the first database key or repair an invalid key bundle;
- attach LLDB, re-sign WeChat, bypass app protections, or perform `sudo` operations;
- decrypt WeChat 4.x media files or claim that an image marker contains the image pixels;
- prove that a sample is complete when `truncated` is true or decode failures are nonzero.

Read [references/security-and-setup.md](references/security-and-setup.md) when `doctor` is not ready, the user asks how keys work, media is required, or an export will be shared.

## Failure Handling

- `missing_key_bundle`: stop. Explain that an existing authorized per-database key bundle is required. Do not improvise a key-extraction workflow.
- `decryption_failed`: the key bundle does not verify against the current databases. Report this as a connection/readiness failure; do not delete retained exports.
- `ambiguous_chat`: run `list-chats` and retry with `conversationId`.
- `message_table_not_found`: report that the contact was found but message storage was not; do not return an empty export as success.
- `decodeFailures > 0`: keep the successful messages, mark coverage partial, and recommend installing a supported zstd backend when relevant.
- `mediaFileDecryption: false`: state that media messages were located but their files were not exported.

## Final Check

Before finishing, verify:

- the result came from a real `export` run, not only a fixture or old JSON;
- the output exists outside Git, has mode `0600`, and parses as JSON;
- `coverage.exportedCount` equals the number of `messages`;
- truncation, decode failures, author handling, and media-file limitations are visible;
- no key, raw database path, raw chatroom ID, or media AES key appears in the artifact or response.
