# Security and Zero-to-One Setup

Read this file in full before guiding a user who has no working key bundle.

## Scope

The reviewed setup path supports Apple Silicon macOS, WeChat 4.1.x, and records the user is authorized to access. It may stop working on any update. It is not legal advice and does not make collection of other participants' data automatically lawful.

This is a high-risk, unsupported debugging workflow. Do not try it for casual exploration. Use it only when the export is necessary, the account and device are yours or explicitly authorized, the purpose is lawful, and you personally accept every warning below.

## Non-Negotiable Warnings

- LLDB attachment and cryptographic-call interception may trigger WeChat account restrictions.
- An ad-hoc signed app copy loses official signature guarantees.
- A database key can unlock broad private history, not only one selected group.
- Chat records may contain third-party personal information, secrets, files, links, and quoted content.
- Similar tooling has faced platform enforcement and removal requests.

Show all warnings before any mutating step. The Agent must never type the acknowledgement, run `sudo lldb`, quit WeChat, launch the debug copy, or decide that the risk is acceptable for the user.

## Method

```text
read-only environment check
  -> dry-run plan
  -> user explicitly accepts risks
  -> create ad-hoc signed copy under ~/.wechat-chat-export
  -> user quits official app and launches the copy
  -> generate, but do not execute, a PID-bound LLDB command
  -> user personally runs command, then signs out and signs back in
  -> capture the 32-byte passphrase at CCKeyDerivationPBKDF
  -> derive per-database keys with PBKDF2-HMAC-SHA512 (256,000 rounds)
  -> HMAC-verify candidates against encrypted database page one
  -> atomically write ~/.wechat-bridge/keys.json with mode 0600
  -> doctor decrypts and opens current contact/message databases
  -> bounded export
```

The official `/Applications/WeChat.app` is never re-signed. The capture-command generator refuses PIDs that do not belong to the prepared debug copy. The hook detaches after success, timeout, or failure; does not print the passphrase or full keys; accepts candidates only after SQLCipher 4 HMAC verification; and writes only a single account's verified contact/message key set.

The login-time trigger and 256,000-round derivation follow the macOS 4.1.x method documented by [`TANGandXUE/wcdb-key-tool`](https://github.com/TANGandXUE/wcdb-key-tool). This Skill independently gates consent, avoids modifying the official app, verifies candidates, and limits output scope. Upstream success reports are evidence for the method, not a guarantee for a future WeChat or macOS release.

## Commands

Run the read-only check:

```bash
python3 scripts/wechat_setup.py check
```

Inspect the dry-run plan:

```bash
python3 scripts/wechat_setup.py prepare
```

Only after personally accepting every warning, the user may create the copy:

```bash
python3 scripts/wechat_setup.py prepare \
  --execute \
  --ack-risk I_ACCEPT_WECHAT_ACCOUNT_AND_PRIVACY_RISKS
```

The user then quits the official app, launches the printed debug-copy command, logs in if required, and asks the Skill to generate a PID-bound capture command:

```bash
python3 scripts/wechat_setup.py capture-command
```

The Agent displays the returned `shellCommand` but does not run it. After LLDB reports that the breakpoint is ready, the user personally signs out and signs back in using the debug copy. Login is the required trigger for `CCKeyDerivationPBKDF`; opening chats alone is not a reliable trigger. This can interrupt the current session and may invoke account security controls.

After capture, verify rather than trust the file's existence:

```bash
python3 scripts/wechat_export.py doctor
```

`ready` means current contact and message databases were decrypted and opened. `partial`, `no_match`, a key file alone, or an old export is not success.

## Data Handling

- Keep `~/.wechat-bridge` at mode `0700` and `keys.json` at `0600`.
- Never paste, log, commit, sync, or upload the key bundle.
- Export outside Git and keep default participant pseudonyms.
- Prefer a date range and limit over full history.
- Delete the debug app copy through a user-controlled, recoverable action after verification; do not automate deletion.
- Prefer a derived minimal report over sharing the raw export.

## Tested Versus Documented

The repository can safely automate tests for environment checks, consent gates, HMAC verification, secure key-file writing, command construction, current-key database verification, and real export. It must not rerun privileged capture merely to satisfy CI or an Agent test. Report manual privileged capture as a separate, version-specific step whose prior success does not guarantee future versions.
