#!/usr/bin/env python3
"""Validate and rank evidence-backed creator opportunity cards."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


WEIGHTS = {"relevance": 0.30, "timeliness": 0.20, "evidence": 0.20, "differentiation": 0.15, "feasibility": 0.15}
REQUIRED_FIELDS = ("id", "title", "audienceTension", "whyNow", "promise", "differentiation", "formatHypothesis", "validationAction", "stopCondition")


def _score(scores: dict[str, Any]) -> float:
    missing = [key for key in WEIGHTS if key not in scores]
    if missing:
        raise ValueError(f"missing score fields: {', '.join(missing)}")
    total = 0.0
    for key, weight in WEIGHTS.items():
        value = float(scores[key])
        if not 0 <= value <= 5:
            raise ValueError(f"{key} must be between 0 and 5")
        total += value * weight
    return round(total, 3)


def rank_opportunities(payload: dict[str, Any]) -> dict[str, object]:
    ranked = []
    rejected = []
    seen_ids: set[str] = set()
    for index, item in enumerate(payload.get("opportunities") or []):
        try:
            if not isinstance(item, dict):
                raise ValueError("opportunity must be an object")
            item_id = str(item.get("id") or "").strip()
            missing = [field for field in REQUIRED_FIELDS if not item.get(field)]
            if missing:
                raise ValueError(f"missing required fields: {', '.join(missing)}")
            if item_id in seen_ids:
                raise ValueError(f"duplicate opportunity id: {item_id}")
            evidence_ids = list(dict.fromkeys(str(value) for value in item.get("evidenceIds") or [] if value))
            source_types = list(dict.fromkeys(str(value) for value in item.get("sourceTypes") or [] if value))
            score = _score(item.get("scores") or {})
            if len(source_types) >= 2 and len(evidence_ids) >= 3 and score >= 4:
                confidence = "high"
            elif len(source_types) >= 2 and len(evidence_ids) >= 2 and score >= 3:
                confidence = "medium"
            else:
                confidence = "low"
            gaps = []
            if len(source_types) < 2:
                gaps.append("needs independent source confirmation")
            if len(evidence_ids) < 2:
                gaps.append("needs more direct evidence")
            ranked.append({**item, "id": item_id, "evidenceIds": evidence_ids, "sourceTypes": source_types, "score": score, "confidence": confidence, "gaps": gaps})
            seen_ids.add(item_id)
        except (TypeError, ValueError) as exc:
            rejected.append({"index": index, "id": item.get("id") if isinstance(item, dict) else None, "reason": str(exc)})
    ranked.sort(key=lambda item: (-float(item["score"]), str(item["id"])))
    for index, item in enumerate(ranked, start=1):
        item["rank"] = index
    return {"ranked": ranked, "rejected": rejected, "weights": WEIGHTS}


def main() -> int:
    parser = argparse.ArgumentParser(description="Rank creator opportunities from a structured JSON file.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = rank_opportunities(json.loads(args.input.read_text(encoding="utf-8")))
    body = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(body, encoding="utf-8")
    else:
        sys.stdout.write(body)
    return 0 if not result["rejected"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
