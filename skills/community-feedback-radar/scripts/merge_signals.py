#!/usr/bin/env python3
"""Normalize, redact, and deduplicate read-only community feedback exports."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def mask_author(value: object) -> str:
    text = str(value or "anonymous").strip()
    if len(text) <= 1:
        return f"{text or 'a'}***"
    return f"{text[0]}***{text[-1]}"


def _iso_timestamp(value: object) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)) or str(value).isdigit():
        return datetime.fromtimestamp(float(value), timezone.utc).isoformat().replace("+00:00", "Z")
    return str(value)


def _stable_id(source: str, source_id: object, text: str, created_at: object) -> str:
    seed = f"{source}|{source_id or ''}|{' '.join(text.lower().split())}|{created_at or ''}"
    return f"{source}-{hashlib.sha256(seed.encode()).hexdigest()[:16]}"


def _rows(payload: object) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("signals", "items", "comments", "issues", "messages"):
        if isinstance(payload.get(key), list):
            return [row for row in payload[key] if isinstance(row, dict)]
    return []


def _source(path: Path, row: dict[str, Any]) -> str:
    explicit = row.get("source")
    if explicit:
        return str(explicit).lower()
    stem = path.stem.lower()
    for candidate in ("github", "bilibili", "wechat"):
        if candidate in stem or candidate in str(path.parent).lower():
            return candidate
    if "number" in row and "html_url" in row:
        return "github"
    if "rpid" in row:
        return "bilibili"
    if "local_id" in row:
        return "wechat"
    return "unknown"


def _normalize(path: Path, row: dict[str, Any], redact: bool) -> dict[str, object] | None:
    source = _source(path, row)
    title = str(row.get("title") or "").strip()
    body = str(row.get("text") or row.get("body") or ((row.get("content") or {}).get("message") if isinstance(row.get("content"), dict) else "") or "").strip()
    text = f"{title}\n\n{body}".strip() if title else body
    if not text:
        return None
    user = row.get("author") or row.get("sender")
    if not user and isinstance(row.get("user"), dict):
        user = row["user"].get("login")
    if not user and isinstance(row.get("member"), dict):
        user = row["member"].get("uname")
    source_id = row.get("sourceId") or row.get("number") or row.get("rpid") or row.get("local_id")
    created = row.get("createdAt") or row.get("created_at") or row.get("ctime") or row.get("create_time")
    return {
        "id": _stable_id(source, source_id, text, created),
        "source": source,
        "sourceId": str(source_id) if source_id is not None else None,
        "author": mask_author(user) if redact else str(user or "anonymous"),
        "text": re.sub(r"\s+", " ", text).strip(),
        "createdAt": _iso_timestamp(created),
        "url": row.get("url") or row.get("html_url") or "",
        "context": row.get("context") or "",
    }


def merge_inputs(paths: list[Path], redact: bool = True) -> dict[str, object]:
    signals: list[dict[str, object]] = []
    input_count = 0
    duplicate_count = 0
    skipped_count = 0
    seen: set[str] = set()
    source_counts: dict[str, int] = {}
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        for row in _rows(payload):
            input_count += 1
            item = _normalize(path, row, redact)
            if not item:
                skipped_count += 1
                continue
            if item["id"] in seen:
                duplicate_count += 1
                continue
            seen.add(str(item["id"]))
            signals.append(item)
            source = str(item["source"])
            source_counts[source] = source_counts.get(source, 0) + 1
    signals.sort(key=lambda item: str(item.get("createdAt") or ""), reverse=True)
    return {
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "stats": {"inputCount": input_count, "uniqueCount": len(signals), "duplicateCount": duplicate_count, "skippedCount": skipped_count, "bySource": source_counts},
        "signals": signals,
        "privacy": {"authorsRedacted": redact, "rawInputsEmbedded": False},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge read-only feedback exports into one redacted evidence file.")
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--keep-authors", action="store_true", help="Keep author names in the local output")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = merge_inputs(args.inputs, redact=not args.keep_authors)
    body = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(body, encoding="utf-8")
    else:
        sys.stdout.write(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
