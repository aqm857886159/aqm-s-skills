# Security, Setup, and Export Contract

Read this reference when readiness fails, the user asks about key setup, media is required, or the export will leave the local machine.

## Supported Path

The public Skill supports this sequence:

```text
authorized local WeChat 4.x databases
  + existing per-database key bundle
  -> read-only temporary SQLCipher page decryption
  -> bounded structured JSON export (0600)
  -> optional local analysis
```

The exporter checks these key-bundle locations in order unless `--key-file` or `WECHAT_KEYS_PATH` is supplied:

1. `~/.wechat-bridge/keys.json`
2. `~/welive/wechat_keys.json`

The JSON must contain a `keys` object mapping current encrypted `.db` paths to 32-byte hexadecimal keys. Never pass a key on the command line, paste one into a prompt, or include one in an eval fixture.

## Key Acquisition Is Separate

This repository intentionally does not distribute a first-key acquisition script. Known approaches may require app re-signing, privileged debugger attachment, and interception of cryptographic calls. Those actions can:

- weaken the integrity of the installed app;
- expose a key that unlocks a broad set of private records;
- violate platform or app terms and create account restrictions;
- stop working across WeChat or macOS versions;
- create privacy and legal obligations for other participants' messages.

When `doctor` reports `missing_key_bundle`, stop and ask the user to provide an existing key bundle produced by a method they have separately reviewed and authorized. Do not download, generate, or execute a hook as an automatic fallback.

## Read-Only Guarantees

The bundled exporter:

- opens encrypted source databases without modifying them;
- writes decrypted SQLite pages only to a private temporary directory;
- deletes that temporary directory when the command exits normally or raises a handled error;
- writes the requested JSON atomically with permission mode `0600`;
- rejects export destinations inside Git worktrees;
- emits only a coverage summary to standard output after export.

An unexpected machine crash can leave operating-system temporary data behind. For high-sensitivity work, use an encrypted local volume and follow the user's retention policy.

## Export Schema

The JSON root contains:

- `schemaVersion`, `source`, and `exportedAt`;
- `conversation.name` and an opaque `conversationId`;
- `coverage` with range, available/exported counts, truncation, scanned databases, matched tables, and decode failures;
- `privacy` with author, path, media-key, and upload state;
- `capabilities` and `warnings`;
- `messages` with stable `id`, local `sourceId`, type, author, text, timestamp, and optional non-secret media metadata.

Default author values are deterministic pseudonyms so repeated messages can be grouped without exposing the local sender identifier. `--keep-authors` retains the identifier available in the message database; it does not resolve a person's real identity.

## Media Boundary

The export records that an image, video, or voice message occurred and retains safe locating metadata when available. It does not decrypt or copy the media file. In particular, WeChat 4.x image storage can use a separate V2 format and keys not provided by the chat database export. Never describe `[image]` as a successfully exported image.

## Sharing Checklist

Before moving an export off the local machine:

1. Confirm the purpose, recipients, retention period, and participant authority.
2. Keep default author pseudonyms unless identity is required.
3. Remove message bodies not needed for the decision.
4. Re-check for phone numbers, email addresses, tokens, private links, and quoted third-party content.
5. Share a derived, minimal report instead of the raw export whenever possible.

## Status Interpretation

- `ready`: current contact and message databases were actually decrypted and opened.
- `not_ready`: no export claim is allowed; follow `nextAction`.
- retained JSON plus `not_ready`: historical evidence remains present, but new capture freshness and coverage are unavailable.
- `truncated: true`: the export is a newest-first bounded sample, not full history.
- `decodeFailures > 0`: some compressed bodies were not recovered; treat analysis as partial.
