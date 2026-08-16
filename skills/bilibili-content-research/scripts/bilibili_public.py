#!/usr/bin/env python3
"""Read public Bilibili metadata, subtitles, and a bounded comment sample."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


API = "https://api.bilibili.com"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36"
MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
    33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40, 61,
    26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36,
    20, 34, 44, 52,
]


def parse_bvid(value: str) -> str:
    match = re.search(r"(BV[0-9A-Za-z]{10})", value)
    if not match:
        raise ValueError("expected a Bilibili BV id or video URL")
    return match.group(1)


def build_wbi_query(params: dict[str, object], img_key: str, sub_key: str, timestamp: int | None = None) -> str:
    original = img_key + sub_key
    mixin_key = "".join(original[index] for index in MIXIN_KEY_ENC_TAB)[:32]
    signed = {**params, "wts": timestamp or round(time.time())}
    cleaned: dict[str, str] = {}
    for key, value in signed.items():
        cleaned[key] = re.sub(r"[!'()*]", "", str(value))
    query = urllib.parse.urlencode(sorted(cleaned.items()))
    return f"{query}&w_rid={hashlib.md5((query + mixin_key).encode()).hexdigest()}"


def _get_json(url: str, referer: str | None = None, timeout: float = 20.0) -> dict[str, Any]:
    headers = {"User-Agent": UA, "Accept": "application/json"}
    if referer:
        headers["Referer"] = referer
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _require_ok(payload: dict[str, Any], label: str) -> dict[str, Any]:
    if payload.get("code") != 0:
        raise RuntimeError(f"{label} returned code={payload.get('code')}: {payload.get('message', '')}")
    return payload.get("data") or {}


def _nav_data(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data") or {}
    if data.get("wbi_img"):
        return data
    return _require_ok(payload, "nav")


def _subtitle_url(value: object) -> str | None:
    url = str(value or "")
    if url.startswith("//"):
        url = "https:" + url
    parsed = urllib.parse.urlparse(url)
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not (
        hostname == "bilibili.com"
        or hostname.endswith(".bilibili.com")
        or hostname == "hdslb.com"
        or hostname.endswith(".hdslb.com")
    ):
        return None
    return url


def _normalize_comment(row: dict[str, Any], bvid: str) -> dict[str, object]:
    created = row.get("ctime")
    return {
        "source": "bilibili",
        "sourceId": f"reply-{row.get('rpid')}",
        "author": (row.get("member") or {}).get("uname") or "anonymous",
        "text": ((row.get("content") or {}).get("message") or "").strip(),
        "createdAt": datetime.fromtimestamp(created, timezone.utc).isoformat().replace("+00:00", "Z") if created else None,
        "likes": row.get("like", 0),
        "url": f"https://www.bilibili.com/video/{bvid}#reply{row.get('rpid')}",
    }


def _normalize(view: dict[str, Any], players: dict[str, Any], subtitle_bodies: dict[str, Any], comments: dict[str, Any], max_comments: int) -> dict[str, object]:
    video = _require_ok(view, "view")
    bvid = video.get("bvid")
    subtitles = []
    for page in video.get("pages") or []:
        player = _require_ok(players.get(str(page.get("cid"))) or players.get("default") or {"code": 0, "data": {}}, "player")
        for subtitle in ((player.get("subtitle") or {}).get("subtitles") or []):
            body = subtitle_bodies.get(str(subtitle.get("id"))) or {}
            subtitles.append({
                "id": subtitle.get("id"),
                "language": subtitle.get("lan"),
                "languageLabel": subtitle.get("lan_doc"),
                "pageCid": page.get("cid"),
                "segments": [
                    {"startSeconds": segment.get("from"), "endSeconds": segment.get("to"), "text": segment.get("content", "")}
                    for segment in body.get("body") or []
                ],
            })
    comment_rows = (_require_ok(comments, "comments").get("replies") or [])[:max_comments]
    normalized_comments = [_normalize_comment(row, bvid) for row in comment_rows if ((row.get("content") or {}).get("message") or "").strip()]
    return {
        "status": "complete",
        "capturedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "video": {
            "aid": video.get("aid"), "bvid": bvid, "title": video.get("title"), "description": video.get("desc"),
            "durationSeconds": video.get("duration"), "owner": video.get("owner"), "statistics": video.get("stat"),
            "url": f"https://www.bilibili.com/video/{bvid}",
        },
        "pages": video.get("pages") or [],
        "subtitles": subtitles,
        "comments": normalized_comments,
        "coverage": {"pageCount": len(video.get("pages") or []), "subtitleTrackCount": len(subtitles), "commentLimit": max_comments, "commentRowsSampled": len(comment_rows), "commentsReturned": len(normalized_comments)},
        "boundaries": {"authenticated": False, "downloadedVideo": False, "outboundActions": False},
        "errors": [],
    }


def normalize_fixture(payload: dict[str, Any], max_comments: int = 20) -> dict[str, object]:
    player = payload.get("player") or {"code": 0, "data": {}}
    pages = ((_require_ok(payload["view"], "view").get("pages")) or [])
    players = {str(page.get("cid")): player for page in pages}
    return _normalize(payload["view"], players, payload.get("subtitleBodies") or {}, payload.get("comments") or {"code": 0, "data": {}}, max_comments)


def collect_public(bvid: str, max_comments: int = 20) -> dict[str, object]:
    referer = f"https://www.bilibili.com/video/{bvid}"
    view = _get_json(f"{API}/x/web-interface/view?{urllib.parse.urlencode({'bvid': bvid})}", referer)
    video = _require_ok(view, "view")
    players: dict[str, Any] = {}
    subtitle_bodies: dict[str, Any] = {}
    errors: list[str] = []
    for page in video.get("pages") or []:
        cid = page.get("cid")
        try:
            player = _get_json(f"{API}/x/player/v2?{urllib.parse.urlencode({'bvid': bvid, 'cid': cid})}", referer)
            player_data = _require_ok(player, "player")
            players[str(cid)] = player
        except Exception as exc:
            errors.append(f"player:{cid}:{exc}")
            continue
        for subtitle in ((player_data.get("subtitle") or {}).get("subtitles") or []):
            subtitle_id = subtitle.get("id")
            url = _subtitle_url(subtitle.get("subtitle_url"))
            if not url:
                errors.append(f"subtitle:{cid}:{subtitle_id}:unsupported URL")
                continue
            try:
                subtitle_bodies[str(subtitle.get("id"))] = _get_json(url, referer)
            except Exception as exc:  # One missing subtitle track must not erase the metadata result.
                errors.append(f"subtitle:{cid}:{subtitle_id}:{exc}")
    comments: dict[str, Any] = {"code": 0, "data": {"replies": []}}
    if max_comments:
        try:
            nav = _nav_data(_get_json(f"{API}/x/web-interface/nav", referer))
            wbi = nav.get("wbi_img") or {}
            key = lambda url: url.rsplit("/", 1)[-1].split(".", 1)[0]
            query = build_wbi_query({"oid": video.get("aid"), "type": 1, "mode": 2, "plat": 1}, key(wbi["img_url"]), key(wbi["sub_url"]))
            fetched_comments = _get_json(f"{API}/x/v2/reply/wbi/main?{query}", referer)
            _require_ok(fetched_comments, "comments")
            comments = fetched_comments
        except Exception as exc:
            errors.append(f"comments:{exc}")
    result = _normalize(view, players, subtitle_bodies, comments, max_comments)
    result["errors"] = errors
    result["status"] = "partial" if errors else "complete"
    return result


def failure_result(bvid: str, max_comments: int, error: Exception) -> dict[str, object]:
    message = " ".join(str(error).split())[:500]
    return {
        "status": "failed",
        "capturedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "video": {"bvid": bvid, "url": f"https://www.bilibili.com/video/{bvid}"},
        "pages": [],
        "subtitles": [],
        "comments": [],
        "coverage": {"pageCount": 0, "subtitleTrackCount": 0, "commentLimit": max_comments, "commentRowsSampled": 0, "commentsReturned": 0},
        "boundaries": {"authenticated": False, "downloadedVideo": False, "outboundActions": False},
        "errors": [f"metadata:{type(error).__name__}:{message}"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Read public Bilibili evidence without cookies or outbound actions.")
    parser.add_argument("video", nargs="?", help="BV id or Bilibili video URL")
    parser.add_argument("--comments", type=int, default=20)
    parser.add_argument("--fixture", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not 0 <= args.comments <= 100:
        parser.error("--comments must be between 0 and 100")
    exit_code = 0
    if args.fixture:
        result = normalize_fixture(json.loads(args.fixture.read_text(encoding="utf-8")), args.comments)
    elif args.video:
        bvid = parse_bvid(args.video)
        try:
            result = collect_public(bvid, args.comments)
        except Exception as exc:
            result = failure_result(bvid, args.comments, exc)
            exit_code = 2
    else:
        parser.error("provide a BV id/URL or --fixture")
    body = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(body, encoding="utf-8")
    else:
        sys.stdout.write(body)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
