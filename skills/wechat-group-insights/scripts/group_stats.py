#!/usr/bin/env python3
"""Deterministic statistics over wechat-chat-export JSON files.

Reads one export file per group and emits objective counts only: message
volume, per-day activity, participants, message types, and question-like
volume. Semantic judgments (what was answered, what is a lead) belong to the
Skill, not this script. No network, no third-party dependencies.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

QUESTION_MARKS = ("?", "？")


def _parse_offset(value: str) -> timezone:
    sign = 1 if value.startswith("+") else -1
    hours, _, minutes = value[1:].partition(":")
    return timezone(sign * timedelta(hours=int(hours), minutes=int(minutes or 0)))


def _local_day(created_at: str, offset: timezone) -> str | None:
    try:
        parsed = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed.astimezone(offset).date().isoformat()


def summarize_export(payload: dict[str, Any], offset: timezone) -> dict[str, Any]:
    messages = payload.get("messages") or []
    days: Counter[str] = Counter()
    authors: Counter[str] = Counter()
    types: Counter[str] = Counter()
    question_like = 0
    undated = 0
    for message in messages:
        day = _local_day(str(message.get("createdAt") or ""), offset)
        if day is None:
            undated += 1
        else:
            days[day] += 1
        author = str(message.get("author") or "unknown")
        authors[author] += 1
        types[str(message.get("type") or "other")] += 1
        if message.get("type") == "text" and any(mark in str(message.get("text") or "") for mark in QUESTION_MARKS):
            question_like += 1
    coverage = payload.get("coverage") or {}
    return {
        "group": (payload.get("conversation") or {}).get("name", "unknown"),
        "conversationId": (payload.get("conversation") or {}).get("conversationId", "unknown"),
        "messageCount": len(messages),
        "availableCount": coverage.get("availableCount"),
        "truncated": bool(coverage.get("truncated")),
        "decodeFailures": int(coverage.get("decodeFailures") or 0),
        "since": coverage.get("since"),
        "until": coverage.get("until"),
        "participantCount": len(authors),
        "topAuthors": [{"author": author, "count": count} for author, count in authors.most_common(5)],
        "messageTypes": dict(sorted(types.items())),
        "questionLikeCount": question_like,
        "perDay": [{"date": day, "count": count} for day, count in sorted(days.items())],
        "undatedCount": undated,
        "authorsRedacted": bool((payload.get("privacy") or {}).get("authorsRedacted", True)),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Objective statistics over wechat-chat-export JSON files.")
    parser.add_argument("exports", nargs="+", type=Path, help="Export JSON files, one per group")
    parser.add_argument("--timezone", default="+08:00", help="Display offset for per-day grouping (default: +08:00)")
    parser.add_argument("--output", type=Path, help="Write JSON here instead of stdout")
    args = parser.parse_args(argv)

    try:
        offset = _parse_offset(args.timezone)
    except (ValueError, IndexError):
        print(json.dumps({"status": "error", "error": {"code": "invalid_timezone", "message": "Use +HH:MM or -HH:MM."}}))
        return 2

    groups: list[dict[str, Any]] = []
    warnings: list[str] = []
    for path in args.exports:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            warnings.append(f"unreadable:{path.name}")
            continue
        if payload.get("source") != "wechat-local" or "messages" not in payload:
            warnings.append(f"notAnExport:{path.name}")
            continue
        groups.append(summarize_export(payload, offset))

    if not groups:
        print(json.dumps({"status": "error", "error": {"code": "no_exports", "message": "No readable export files."}, "warnings": warnings}, ensure_ascii=False))
        return 2

    all_days = sorted({entry["date"] for group in groups for entry in group["perDay"]})
    result = {
        "status": "ok",
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "timezone": args.timezone,
        "totals": {
            "groupCount": len(groups),
            "messageCount": sum(group["messageCount"] for group in groups),
            "questionLikeCount": sum(group["questionLikeCount"] for group in groups),
            "dateRange": {"first": all_days[0], "last": all_days[-1]} if all_days else None,
            "anyTruncated": any(group["truncated"] for group in groups),
            "decodeFailures": sum(group["decodeFailures"] for group in groups),
        },
        "groups": groups,
        "warnings": warnings,
    }
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
        print(json.dumps({"status": "ok", "output": str(args.output), "groupCount": len(groups)}, ensure_ascii=False))
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
