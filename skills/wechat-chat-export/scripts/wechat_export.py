#!/usr/bin/env python3
"""Read-only export for authorized local WeChat 4.x databases on macOS.

This read-only exporter does not attach to WeChat, alter the app, or upload
data. First-time setup is handled separately by the risk-gated
``wechat_setup.py`` workflow. This script consumes its verified per-database
key bundle and writes a bounded JSON export outside Git worktrees with mode
0600.
"""

from __future__ import annotations

import argparse
import json
import os
import plistlib
import re
import sqlite3
import stat
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

try:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    hashes = Cipher = algorithms = modes = None  # type: ignore[assignment]
    CRYPTOGRAPHY_AVAILABLE = False

try:
    from compression import zstd as _stdlib_zstd

    def _zstd_decompress(data: bytes) -> bytes:
        return _stdlib_zstd.decompress(data)

    ZSTD_BACKEND = "stdlib"
except ImportError:
    try:
        import zstandard as _third_party_zstd

        def _zstd_decompress(data: bytes) -> bytes:
            return _third_party_zstd.ZstdDecompressor().decompress(data)

        ZSTD_BACKEND = "zstandard"
    except ImportError:
        ZSTD_BACKEND = None


PAGE_SIZE = 4096
RESERVE_SIZE = 80
SALT_SIZE = 16
IV_SIZE = 16
ZSTD_MAGIC = b"\x28\xb5\x2f\xfd"
DEFAULT_KEY_FILES = (
    Path("~/.wechat-bridge/keys.json").expanduser(),
    Path("~/welive/wechat_keys.json").expanduser(),
)
WECHAT_PLIST = Path("/Applications/WeChat.app/Contents/Info.plist")
HEX_KEY = re.compile(r"^[0-9a-fA-F]{64}$")


class ExportError(RuntimeError):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


def _json_print(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _digest(name: str, value: str) -> str:
    if not CRYPTOGRAPHY_AVAILABLE:
        raise ExportError("missing_dependency", "Install the cryptography Python package.")
    algorithm = hashes.MD5() if name == "md5" else hashes.SHA256()
    digest = hashes.Hash(algorithm)
    digest.update(value.encode("utf-8"))
    return digest.finalize().hex()


def _key_file_candidates(explicit: str | None) -> list[Path]:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    elif os.environ.get("WECHAT_KEYS_PATH"):
        candidates.append(Path(os.environ["WECHAT_KEYS_PATH"]).expanduser())
    else:
        candidates.extend(DEFAULT_KEY_FILES)
    return [path.resolve() for path in candidates if path.is_file()]


def _load_keys(explicit: str | None) -> tuple[Path, dict[Path, str]]:
    candidates = _key_file_candidates(explicit)
    if not candidates:
        raise ExportError(
            "missing_key_bundle",
            "No verified WeChat key bundle was found. Run wechat_setup.py check for the risk-gated first-time setup.",
        )
    failures: list[str] = []
    for path in candidates:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            raw_keys = payload.get("keys") if isinstance(payload, dict) else None
            if not isinstance(raw_keys, dict):
                raise ValueError("missing keys object")
            keys: dict[Path, str] = {}
            invalid_count = 0
            for raw_path, raw_key in raw_keys.items():
                if isinstance(raw_path, str) and isinstance(raw_key, str) and HEX_KEY.fullmatch(raw_key):
                    keys[Path(raw_path).expanduser().resolve()] = raw_key.lower()
                else:
                    invalid_count += 1
            if invalid_count or not keys:
                raise ValueError(f"valid={len(keys)}, invalid={invalid_count}")
            return path, keys
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            failures.append(type(exc).__name__)
    raise ExportError(
        "invalid_key_bundle",
        "No discovered key bundle contained a valid keys object.",
        {"candidateCount": len(candidates), "failureTypes": failures},
    )


def _key_mode(path: Path) -> str:
    return oct(stat.S_IMODE(path.stat().st_mode))


def _wechat_version() -> str | None:
    try:
        with WECHAT_PLIST.open("rb") as handle:
            value = plistlib.load(handle).get("CFBundleShortVersionString")
        return str(value) if value else None
    except (OSError, plistlib.InvalidFileException):
        return None


def _database_entries(keys: dict[Path, str], kind: str) -> list[tuple[Path, str]]:
    result: list[tuple[Path, str]] = []
    for path, key in keys.items():
        name = path.name.lower()
        normalized = str(path).replace("\\", "/").lower()
        if kind == "contact" and name == "contact.db" and "fts" not in normalized:
            result.append((path, key))
        if kind == "message" and name.startswith("message_") and name.endswith(".db") and "fts" not in normalized:
            result.append((path, key))
    return sorted(result, key=lambda item: str(item[0]))


def decrypt_database(source: Path, key_hex: str, destination: Path) -> None:
    """Decrypt SQLCipher 4 pages into a temporary SQLite database."""
    if not CRYPTOGRAPHY_AVAILABLE:
        raise ExportError("missing_dependency", "Install the cryptography Python package.")
    if not source.is_file():
        raise ExportError("missing_database", "A database referenced by the key bundle is missing.")
    size = source.stat().st_size
    if size < PAGE_SIZE or size % PAGE_SIZE:
        raise ExportError("invalid_database", "An encrypted database has an invalid page-aligned size.")
    key = bytes.fromhex(key_hex)
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with source.open("rb") as encrypted, os.fdopen(descriptor, "wb") as plain:
            descriptor = -1
            page_number = 0
            while True:
                page = encrypted.read(PAGE_SIZE)
                if not page:
                    break
                offset = SALT_SIZE if page_number == 0 else 0
                ciphertext = page[offset:PAGE_SIZE - RESERVE_SIZE]
                iv = page[PAGE_SIZE - RESERVE_SIZE:PAGE_SIZE - RESERVE_SIZE + IV_SIZE]
                if len(ciphertext) % 16 or len(iv) != IV_SIZE:
                    raise ExportError("invalid_database", "An encrypted database page is malformed.")
                decryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
                plaintext = decryptor.update(ciphertext) + decryptor.finalize()
                if page_number == 0:
                    plain.write(b"SQLite format 3\x00")
                plain.write(plaintext)
                plain.write(page[PAGE_SIZE - RESERVE_SIZE:])
                page_number += 1
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _open_read_only(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _tables(connection: sqlite3.Connection) -> list[str]:
    return [str(row[0]) for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")]


def _columns(connection: sqlite3.Connection, table: str) -> list[str]:
    try:
        return [str(row[1]) for row in connection.execute(f"PRAGMA table_info({_quote_identifier(table)})")]
    except sqlite3.Error:
        return []


def _first(columns: Iterable[str], *candidates: str) -> str | None:
    lookup = {column.casefold(): column for column in columns}
    return next((lookup[candidate.casefold()] for candidate in candidates if candidate.casefold() in lookup), None)


def _conversation_id(chatroom: str) -> str:
    return f"conversation-{_digest('sha256', chatroom)[:12]}"


def discover_chats(keys: dict[Path, str], temporary: Path) -> list[dict[str, str]]:
    chats: dict[str, dict[str, str]] = {}
    failures = 0
    for index, (source, key) in enumerate(_database_entries(keys, "contact")):
        plain = temporary / f"contact-{index}.db"
        try:
            decrypt_database(source, key, plain)
            connection = _open_read_only(plain)
        except (ExportError, sqlite3.Error, ValueError):
            failures += 1
            continue
        try:
            for table in _tables(connection):
                columns = _columns(connection, table)
                username_column = _first(columns, "username", "user_name", "strUsrName", "m_nsUsrName")
                name_column = _first(
                    columns,
                    "nick_name",
                    "nickname",
                    "remark",
                    "group_name",
                    "session_title",
                    "strNickName",
                    "m_nsRemark",
                )
                if not username_column or not name_column:
                    continue
                query = (
                    f"SELECT {_quote_identifier(username_column)} AS username, "
                    f"{_quote_identifier(name_column)} AS display_name FROM {_quote_identifier(table)}"
                )
                try:
                    rows = connection.execute(query)
                    for row in rows:
                        username = str(row["username"] or "")
                        display_name = str(row["display_name"] or "").strip()
                        if "@chatroom" in username and display_name:
                            chats[username] = {
                                "name": display_name,
                                "conversationId": _conversation_id(username),
                                "_chatroom": username,
                            }
                except sqlite3.Error:
                    continue
        finally:
            connection.close()
    if not chats and failures:
        raise ExportError("decryption_failed", "Contact databases could not be decrypted with the existing key bundle.")
    return sorted(chats.values(), key=lambda item: (item["name"].casefold(), item["conversationId"]))


def choose_chat(chats: list[dict[str, str]], group: str | None, conversation_id: str | None) -> dict[str, str]:
    if conversation_id:
        matches = [chat for chat in chats if chat["conversationId"] == conversation_id]
    else:
        needle = (group or "").casefold()
        exact = [chat for chat in chats if chat["name"].casefold() == needle]
        matches = exact or [chat for chat in chats if needle in chat["name"].casefold()]
    if not matches:
        raise ExportError("chat_not_found", "No chat matched the requested group name or conversation ID.")
    if len(matches) > 1:
        raise ExportError(
            "ambiguous_chat",
            "More than one chat matched. Re-run with a conversation ID from list-chats.",
            {"matches": [{"name": item["name"], "conversationId": item["conversationId"]} for item in matches]},
        )
    return matches[0]


def _decode_content(value: object) -> tuple[str, bool]:
    if value is None:
        return "", True
    if isinstance(value, (bytes, bytearray)):
        data = bytes(value)
        if data.startswith(ZSTD_MAGIC):
            if ZSTD_BACKEND is None:
                return "[compressed message unavailable: install zstandard or use Python 3.14+]", False
            try:
                data = _zstd_decompress(data)
            except Exception:
                return "[compressed message could not be decoded]", False
        return data.decode("utf-8", "replace"), True
    return str(value), True


def _element(root: ET.Element, name: str) -> ET.Element | None:
    return next((node for node in root.iter() if node.tag.rsplit("}", 1)[-1] == name), None)


def _element_text(root: ET.Element, name: str) -> str:
    node = _element(root, name)
    return " ".join("".join(node.itertext()).split())[:500] if node is not None else ""


def _split_sender(value: str) -> tuple[str, str]:
    prefix, separator, body = value.partition(":\n")
    if separator and (prefix.startswith("wxid_") or prefix.endswith("@chatroom") or len(prefix) < 128):
        return prefix, body
    return "", value


def classify_message(raw: str) -> tuple[str, str, dict[str, str]]:
    body = raw.strip()
    if not body.startswith("<"):
        return "text", body, {}
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return "other", "[non-text message]", {}
    image = _element(root, "img")
    if image is not None:
        media_id = image.attrib.get("md5", "")
        return "image", "[image]", {"mediaId": media_id} if media_id else {}
    if _element(root, "videomsg") is not None:
        return "video", "[video]", {}
    if _element(root, "voicemsg") is not None or "voicelength" in body:
        return "voice", "[voice]", {}
    if _element(root, "refermsg") is not None:
        title = _element_text(root, "title")
        quoted = _element_text(root, "content")
        text = "[quote]" + (f" {title}" if title else "") + (f" | {quoted}" if quoted else "")
        return "quote", text, {}
    if _element(root, "appmsg") is not None or _element(root, "appinfo") is not None:
        title = _element_text(root, "title")
        return "link", "[link]" + (f" {title}" if title else ""), {}
    return "other", "[non-text message]", {}


def _parse_time(value: str | None, option: str) -> int | None:
    if not value:
        return None
    if value.isdigit():
        return int(value)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ExportError("invalid_time", f"{option} must be an ISO 8601 value or Unix timestamp.") from exc
    if parsed.tzinfo is None:
        parsed = parsed.astimezone()
    return int(parsed.timestamp())


def _iso_time(value: object) -> str | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value) if value not in (None, "") else None
    if number > 10_000_000_000:
        number /= 1000
    try:
        return datetime.fromtimestamp(number, timezone.utc).isoformat().replace("+00:00", "Z")
    except (OverflowError, OSError, ValueError):
        return str(value)


def _masked_author(sender: str) -> str:
    return f"participant-{_digest('sha256', sender or 'anonymous')[:10]}"


def _message_id(chatroom: str, source_id: object, created_at: object, text: str) -> str:
    seed = f"{chatroom}|{source_id}|{created_at}|{text}"
    return f"wechat-{_digest('sha256', seed)[:16]}"


def _is_truncated(available_count: int, limit: int | None) -> bool:
    return limit is not None and available_count > limit


def export_messages(
    keys: dict[Path, str],
    chat: dict[str, str],
    temporary: Path,
    since: int | None,
    until: int | None,
    limit: int | None,
    keep_authors: bool,
) -> dict[str, Any]:
    chatroom = chat["_chatroom"]
    table_hash = _digest("md5", chatroom)
    messages: list[dict[str, Any]] = []
    available_count = 0
    databases_scanned = 0
    tables_matched = 0
    decode_failures = 0
    warnings: list[str] = []
    for index, (source, key) in enumerate(_database_entries(keys, "message")):
        databases_scanned += 1
        plain = temporary / f"message-{index}.db"
        try:
            decrypt_database(source, key, plain)
            connection = _open_read_only(plain)
        except (ExportError, sqlite3.Error, ValueError):
            warnings.append(f"messageDatabase:{index}:unreadable")
            continue
        try:
            table = next((name for name in _tables(connection) if table_hash in name.casefold()), None)
            if not table:
                continue
            tables_matched += 1
            columns = _columns(connection, table)
            content_column = _first(columns, "message_content", "content", "StrContent", "m_nsContent")
            time_column = _first(columns, "create_time", "createTime", "CreateTime", "m_uiCreateTime")
            sender_column = _first(columns, "sender_username", "sender", "talker", "m_nsFromUsr", "strTalker")
            id_column = _first(columns, "local_id", "localId", "MesLocalID", "m_uiMesLocalID")
            if not content_column:
                warnings.append(f"messageDatabase:{index}:missingContentColumn")
                continue
            where: list[str] = []
            parameters: list[Any] = []
            if since is not None or until is not None:
                if not time_column:
                    warnings.append(f"messageDatabase:{index}:missingTimeColumn")
                    continue
                if since is not None:
                    where.append(f"{_quote_identifier(time_column)} >= ?")
                    parameters.append(since)
                if until is not None:
                    where.append(f"{_quote_identifier(time_column)} <= ?")
                    parameters.append(until)
            suffix = f" WHERE {' AND '.join(where)}" if where else ""
            available_count += int(
                connection.execute(f"SELECT COUNT(*) FROM {_quote_identifier(table)}{suffix}", parameters).fetchone()[0]
            )
            order = f" ORDER BY {_quote_identifier(time_column)} DESC" if time_column else ""
            query_limit = "" if limit is None else f" LIMIT {limit + 1}"
            query = f"SELECT * FROM {_quote_identifier(table)}{suffix}{order}{query_limit}"
            for row in connection.execute(query, parameters):
                item = dict(row)
                decoded, decode_ok = _decode_content(item.get(content_column))
                if not decoded.strip():
                    continue
                embedded_sender, body = _split_sender(decoded)
                sender = str(item.get(sender_column) or embedded_sender or "") if sender_column else embedded_sender
                kind, text, media = classify_message(body)
                if not decode_ok:
                    decode_failures += 1
                created_raw = item.get(time_column) if time_column else None
                source_id = item.get(id_column) if id_column else None
                record: dict[str, Any] = {
                    "id": _message_id(chatroom, source_id, created_raw, text),
                    "sourceId": str(source_id) if source_id is not None else None,
                    "type": kind,
                    "author": sender if keep_authors else _masked_author(sender),
                    "text": text,
                    "createdAt": _iso_time(created_raw),
                }
                if media:
                    record["media"] = media
                if not decode_ok:
                    record["decodeStatus"] = "unavailable"
                messages.append(record)
        finally:
            connection.close()
    messages.sort(key=lambda item: (str(item.get("createdAt") or ""), str(item["id"])))
    if limit is not None and len(messages) > limit:
        messages = messages[-limit:]
    return {
        "schemaVersion": 1,
        "source": "wechat-local",
        "exportedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "conversation": {"name": chat["name"], "conversationId": chat["conversationId"]},
        "coverage": {
            "since": _iso_time(since),
            "until": _iso_time(until),
            "requestedLimit": limit,
            "availableCount": available_count,
            "exportedCount": len(messages),
            "truncated": _is_truncated(available_count, limit),
            "messageDatabasesScanned": databases_scanned,
            "messageTablesMatched": tables_matched,
            "decodeFailures": decode_failures,
        },
        "privacy": {
            "authorsRedacted": not keep_authors,
            "databasePathsIncluded": False,
            "mediaKeysIncluded": False,
            "uploaded": False,
        },
        "capabilities": {"mediaMetadata": True, "mediaFileDecryption": False},
        "warnings": warnings,
        "messages": messages,
    }


def _git_root_for(path: Path) -> Path | None:
    current = path.resolve().parent
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def write_private_json(path: Path, payload: dict[str, Any], force: bool) -> None:
    destination = path.expanduser().resolve()
    if _git_root_for(destination):
        raise ExportError("unsafe_output", "Refusing to write private chat records inside a Git worktree.")
    if destination.exists() and not force:
        raise ExportError("output_exists", "The output file exists. Use --force to replace it explicitly.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            descriptor = -1
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temporary, destination)
        os.chmod(destination, 0o600)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def doctor(explicit_key_file: str | None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": "not_ready",
        "platform": {"macOS": sys.platform == "darwin", "wechatVersion": _wechat_version()},
        "dependencies": {"cryptography": CRYPTOGRAPHY_AVAILABLE, "zstd": ZSTD_BACKEND or False},
        "keyBundle": {"found": False, "permissionMode": None, "entryCount": 0, "missingDatabaseCount": 0},
        "database": {"contactCount": 0, "messageCount": 0, "contactDecryptable": False, "messageDecryptable": False},
        "capabilities": {
            "exportText": False,
            "exportMediaMetadata": False,
            "decryptMediaFiles": False,
            "acquireKeys": False,
            "guidedFirstTimeSetup": True,
            "automaticKeyCapture": False,
        },
        "warnings": [],
    }
    if not CRYPTOGRAPHY_AVAILABLE:
        result["nextAction"] = "Install cryptography, then run doctor again."
        return result
    try:
        key_path, keys = _load_keys(explicit_key_file)
    except ExportError as exc:
        result["error"] = {"code": exc.code, "message": exc.message}
        result["nextAction"] = "Run wechat_setup.py check, or provide an existing authorized key bundle with --key-file."
        return result
    missing_count = sum(not path.is_file() for path in keys)
    mode = _key_mode(key_path)
    contact_entries = _database_entries(keys, "contact")
    message_entries = _database_entries(keys, "message")
    result["keyBundle"] = {
        "found": True,
        "permissionMode": mode,
        "entryCount": len(keys),
        "missingDatabaseCount": missing_count,
    }
    result["database"]["contactCount"] = len(contact_entries)
    result["database"]["messageCount"] = len(message_entries)
    if mode != "0o600":
        result["warnings"].append("keyBundlePermissionsShouldBe0600")
    if missing_count:
        result["warnings"].append("keyBundleReferencesMissingDatabases")
    with tempfile.TemporaryDirectory(prefix="wechat-export-doctor-") as temporary_name:
        temporary = Path(temporary_name)
        for label, entries in (("contactDecryptable", contact_entries), ("messageDecryptable", message_entries)):
            for index, (source, key) in enumerate(entries):
                plain = temporary / f"{label}-{index}.db"
                try:
                    decrypt_database(source, key, plain)
                    connection = _open_read_only(plain)
                    try:
                        connection.execute("SELECT name FROM sqlite_master LIMIT 1").fetchone()
                    finally:
                        connection.close()
                    result["database"][label] = True
                    break
                except (ExportError, sqlite3.Error, ValueError):
                    result["database"][label] = False
    ready = (
        sys.platform == "darwin"
        and bool(contact_entries)
        and bool(message_entries)
        and result["database"]["contactDecryptable"]
        and result["database"]["messageDecryptable"]
    )
    result["status"] = "ready" if ready else "not_ready"
    result["capabilities"]["exportText"] = bool(ready)
    result["capabilities"]["exportMediaMetadata"] = bool(ready)
    result["nextAction"] = "Run list-chats, then export a bounded conversation." if ready else "Resolve the reported database or key-bundle issue."
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export authorized local WeChat chat records without modifying WeChat.")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--key-file", help="Existing per-database key bundle; defaults to approved local paths")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser(
        "doctor",
        parents=[common],
        help="Check export readiness without exposing keys, paths, chats, or messages",
    )

    list_parser = subparsers.add_parser(
        "list-chats",
        parents=[common],
        help="List exportable group names and opaque conversation IDs",
    )
    list_parser.add_argument("--match", help="Optional case-insensitive group-name filter")

    export_parser = subparsers.add_parser(
        "export",
        parents=[common],
        help="Export one group to a private JSON file",
    )
    target = export_parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--group", help="Exact or unique partial group name")
    target.add_argument("--conversation-id", help="Opaque ID returned by list-chats")
    export_parser.add_argument("--since", help="ISO 8601 or Unix timestamp, inclusive")
    export_parser.add_argument("--until", help="ISO 8601 or Unix timestamp, inclusive")
    amount = export_parser.add_mutually_exclusive_group()
    amount.add_argument("--limit", type=int, default=1000, help="Newest messages to export (default: 1000)")
    amount.add_argument("--all", action="store_true", help="Explicitly export every matching message")
    export_parser.add_argument("--output", required=True, type=Path, help="Destination outside any Git worktree")
    export_parser.add_argument("--keep-authors", action="store_true", help="Keep local sender identifiers in the private export")
    export_parser.add_argument("--force", action="store_true", help="Replace an existing output file")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "doctor":
            result = doctor(args.key_file)
            _json_print(result)
            return 0 if result["status"] == "ready" else 2

        _, keys = _load_keys(args.key_file)
        with tempfile.TemporaryDirectory(prefix="wechat-chat-export-") as temporary_name:
            temporary = Path(temporary_name)
            chats = discover_chats(keys, temporary)
            if args.command == "list-chats":
                if args.match:
                    needle = args.match.casefold()
                    chats = [chat for chat in chats if needle in chat["name"].casefold()]
                _json_print(
                    {
                        "status": "ok",
                        "count": len(chats),
                        "chats": [{"name": chat["name"], "conversationId": chat["conversationId"]} for chat in chats],
                    }
                )
                return 0

            if args.limit is not None and args.limit < 1:
                raise ExportError("invalid_limit", "--limit must be at least 1; use --all for an unbounded export.")
            since = _parse_time(args.since, "--since")
            until = _parse_time(args.until, "--until")
            if since is not None and until is not None and since > until:
                raise ExportError("invalid_time_range", "--since must not be later than --until.")
            chat = choose_chat(chats, args.group, args.conversation_id)
            payload = export_messages(
                keys,
                chat,
                temporary,
                since,
                until,
                None if args.all else args.limit,
                args.keep_authors,
            )
            if payload["coverage"]["messageTablesMatched"] == 0:
                raise ExportError("message_table_not_found", "The chat was found, but its message table was not found in the keyed databases.")
            write_private_json(args.output, payload, args.force)
            _json_print(
                {
                    "status": "ok",
                    "output": str(args.output.expanduser().resolve()),
                    "count": payload["coverage"]["exportedCount"],
                    "availableCount": payload["coverage"]["availableCount"],
                    "truncated": payload["coverage"]["truncated"],
                    "authorsRedacted": payload["privacy"]["authorsRedacted"],
                    "decodeFailures": payload["coverage"]["decodeFailures"],
                    "mediaFileDecryption": False,
                }
            )
            return 0
    except ExportError as exc:
        _json_print({"status": "error", "error": {"code": exc.code, "message": exc.message, **exc.details}})
        return 2
    except (OSError, sqlite3.Error, ValueError) as exc:
        _json_print(
            {
                "status": "error",
                "error": {"code": "export_failed", "message": f"Local export failed: {type(exc).__name__}."},
            }
        )
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
