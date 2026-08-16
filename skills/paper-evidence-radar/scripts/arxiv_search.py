#!/usr/bin/env python3
"""Fetch and normalize a bounded arXiv query using only the Python standard library."""

from __future__ import annotations

import argparse
import json
import re
import shlex
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path


ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV = "{http://arxiv.org/schemas/atom}"
ARXIV_ID = re.compile(r"/(\d{4}\.\d{4,5})(?:v(\d+))?$")


def _text(node: ET.Element | None) -> str:
    return " ".join((node.text if node is not None and node.text else "").split())


def parse_atom(raw: bytes) -> list[dict[str, object]]:
    root = ET.fromstring(raw)
    items: list[dict[str, object]] = []
    for entry in root.findall(f"{ATOM}entry"):
        identifier = _text(entry.find(f"{ATOM}id"))
        match = ARXIV_ID.search(identifier)
        if not match:
            continue
        links = {
            link.attrib.get("type", "page"): link.attrib.get("href", "")
            for link in entry.findall(f"{ATOM}link")
            if link.attrib.get("href")
        }
        primary_category = entry.find(f"{ARXIV}primary_category")
        items.append(
            {
                "arxivId": match.group(1),
                "version": int(match.group(2) or 1),
                "title": _text(entry.find(f"{ATOM}title")),
                "summary": _text(entry.find(f"{ATOM}summary")),
                "authors": [_text(author.find(f"{ATOM}name")) for author in entry.findall(f"{ATOM}author")],
                "categories": [category.attrib.get("term", "") for category in entry.findall(f"{ATOM}category")],
                "publishedAt": _text(entry.find(f"{ATOM}published")),
                "updatedAt": _text(entry.find(f"{ATOM}updated")),
                "url": f"https://arxiv.org/abs/{match.group(1)}",
                "pdfUrl": links.get("application/pdf", f"https://arxiv.org/pdf/{match.group(1)}"),
                "primaryCategory": primary_category.attrib.get("term") if primary_category is not None else None,
            }
        )
    return items


def filter_recent(items: list[dict[str, object]], cutoff: date) -> list[dict[str, object]]:
    return [item for item in items if date.fromisoformat(str(item["publishedAt"])[:10]) >= cutoff]


def build_search_query(query: str, mode: str = "all") -> str:
    if mode == "raw":
        return query.strip()
    if mode == "phrase":
        return f'all:"{query.strip().replace(chr(34), "")}"'
    terms = [term.replace('"', "").strip() for term in shlex.split(query) if term.replace('"', "").strip()]
    if not terms:
        raise ValueError("query must contain at least one searchable term")
    operator = " AND " if mode == "all" else " OR "
    return operator.join(f'all:"{term}"' for term in terms)


def fetch_arxiv(
    query: str,
    max_results: int,
    timeout: float = 20.0,
    query_mode: str = "all",
) -> tuple[list[dict[str, object]], str]:
    api_query = build_search_query(query, query_mode)
    params = urllib.parse.urlencode(
        {
            "search_query": api_query,
            "start": 0,
            "max_results": max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
    )
    request = urllib.request.Request(
        f"https://export.arxiv.org/api/query?{params}",
        headers={"User-Agent": "aqm-s-skills-paper-evidence-radar/1.0 (+https://github.com/aqm857886159/aqm-s-skills)"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return parse_atom(response.read()), api_query


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a bounded, read-only arXiv search.")
    parser.add_argument("query", nargs="?", help="Natural-language research query")
    parser.add_argument("--max-results", type=int, default=20)
    parser.add_argument("--since", help="Keep papers published on or after YYYY-MM-DD")
    parser.add_argument("--query-mode", choices=("all", "any", "phrase", "raw"), default="all")
    parser.add_argument("--fixture", type=Path, help="Parse a local Atom fixture instead of using the network")
    parser.add_argument("--output", type=Path, help="Write JSON to this path instead of stdout")
    args = parser.parse_args()
    if not 1 <= args.max_results <= 100:
        parser.error("--max-results must be between 1 and 100")
    exit_code = 0
    try:
        cutoff = date.fromisoformat(args.since) if args.since else None
        if args.fixture:
            items = parse_atom(args.fixture.read_bytes())
            api_query = None
            query_mode = "fixture"
        elif args.query:
            items, api_query = fetch_arxiv(args.query, args.max_results, query_mode=args.query_mode)
            query_mode = args.query_mode
        else:
            parser.error("provide a query or --fixture")
        collected_count = len(items)
        if cutoff:
            items = filter_recent(items, cutoff)
        payload = {
            "status": "complete",
            "query": args.query,
            "count": len(items),
            "papers": items,
            "coverage": {
                "queryMode": query_mode,
                "apiQuery": api_query,
                "requestedMaxResults": args.max_results,
                "collectedBeforeDateFilter": collected_count,
                "since": args.since,
                "returnedAfterDateFilter": len(items),
            },
            "errors": [],
        }
    except Exception as exc:  # Preserve a bounded, machine-readable failure instead of a traceback.
        exit_code = 2
        payload = {
            "status": "failed",
            "query": args.query,
            "count": 0,
            "papers": [],
            "coverage": {
                "queryMode": "fixture" if args.fixture else args.query_mode,
                "apiQuery": None,
                "requestedMaxResults": args.max_results,
                "collectedBeforeDateFilter": 0,
                "since": args.since,
                "returnedAfterDateFilter": 0,
            },
            "errors": [f"collection:{type(exc).__name__}:{' '.join(str(exc).split())[:300]}"],
        }
    body = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(body, encoding="utf-8")
    else:
        sys.stdout.write(body)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
