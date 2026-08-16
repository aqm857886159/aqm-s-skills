#!/usr/bin/env python3
"""Validate and rank evidence-backed creator opportunity cards."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any


WEIGHTS = {"relevance": 0.30, "timeliness": 0.20, "evidence": 0.20, "differentiation": 0.15, "feasibility": 0.15}
REQUIRED_FIELDS = (
    "id", "title", "audienceTension", "whyNow", "whyNowDate", "promise", "differentiation",
    "formatHypothesis", "validationAction", "stopCondition",
)


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


def _parse_date(value: object, label: str) -> date:
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise ValueError(f"{label} must be YYYY-MM-DD") from exc


def _evidence_catalog(payload: dict[str, Any], as_of: date) -> tuple[dict[str, dict[str, str]], list[dict[str, object]], bool]:
    if "evidence" in payload and not isinstance(payload["evidence"], list):
        raise ValueError("evidence must be an array")
    provided = isinstance(payload.get("evidence"), list)
    catalog: dict[str, dict[str, str]] = {}
    rejected: list[dict[str, object]] = []
    for index, item in enumerate(payload.get("evidence") or []):
        try:
            if not isinstance(item, dict):
                raise ValueError("evidence must be an object")
            evidence_id = str(item.get("id") or "").strip()
            source_type = str(item.get("sourceType") or "").strip()
            captured_at = _parse_date(item.get("capturedAt"), "evidence capturedAt")
            if not evidence_id or not source_type:
                raise ValueError("evidence requires id and sourceType")
            if evidence_id in catalog:
                raise ValueError(f"duplicate evidence id: {evidence_id}")
            if captured_at > as_of:
                raise ValueError(f"evidence is dated after asOfDate: {evidence_id}")
            catalog[evidence_id] = {
                "id": evidence_id,
                "sourceType": source_type,
                "capturedAt": captured_at.isoformat(),
                "sourceUrl": str(item.get("sourceUrl") or ""),
            }
        except (TypeError, ValueError) as exc:
            rejected.append({"index": index, "id": item.get("id") if isinstance(item, dict) else None, "reason": str(exc)})
    return catalog, rejected, provided


def rank_opportunities(payload: dict[str, Any]) -> dict[str, object]:
    if not isinstance(payload, dict):
        raise ValueError("input must be a JSON object")
    if "opportunities" in payload and not isinstance(payload["opportunities"], list):
        raise ValueError("opportunities must be an array")
    as_of = _parse_date(payload.get("asOfDate"), "asOfDate")
    catalog, evidence_rejected, catalog_provided = _evidence_catalog(payload, as_of)
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
            unknown_evidence = [evidence_id for evidence_id in evidence_ids if evidence_id not in catalog]
            if catalog_provided and unknown_evidence:
                raise ValueError(f"unknown evidence ids: {', '.join(unknown_evidence)}")
            source_types = (
                list(dict.fromkeys(catalog[evidence_id]["sourceType"] for evidence_id in evidence_ids))
                if catalog_provided
                else list(dict.fromkeys(str(value) for value in item.get("sourceTypes") or [] if value))
            )
            why_now_date = _parse_date(item.get("whyNowDate"), "whyNowDate")
            if why_now_date > as_of:
                raise ValueError("whyNowDate must not be after asOfDate")
            why_now_age_days = (as_of - why_now_date).days
            score = _score(item.get("scores") or {})
            if catalog_provided and why_now_age_days <= 180 and len(source_types) >= 2 and len(evidence_ids) >= 3 and score >= 4:
                confidence = "high"
            elif catalog_provided and why_now_age_days <= 365 and len(source_types) >= 2 and len(evidence_ids) >= 2 and score >= 3:
                confidence = "medium"
            else:
                confidence = "low"
            gaps = []
            if not catalog_provided:
                gaps.append("needs a verifiable evidence catalog")
            if len(source_types) < 2:
                gaps.append("needs independent source confirmation")
            if len(evidence_ids) < 2:
                gaps.append("needs more direct evidence")
            if why_now_age_days > 180:
                gaps.append("why-now evidence is older than 180 days")
            ranked.append({
                **item,
                "id": item_id,
                "whyNowDate": why_now_date.isoformat(),
                "whyNowAgeDays": why_now_age_days,
                "evidenceIds": evidence_ids,
                "sourceTypes": source_types,
                "score": score,
                "confidence": confidence,
                "gaps": gaps,
            })
            seen_ids.add(item_id)
        except (TypeError, ValueError) as exc:
            rejected.append({"index": index, "id": item.get("id") if isinstance(item, dict) else None, "reason": str(exc)})
    ranked.sort(key=lambda item: (-float(item["score"]), str(item["id"])))
    for index, item in enumerate(ranked, start=1):
        item["rank"] = index
    return {
        "status": "complete",
        "asOfDate": as_of.isoformat(),
        "ranked": ranked,
        "rejected": rejected,
        "evidenceRejected": evidence_rejected,
        "evidenceStats": {"catalogProvided": catalog_provided, "accepted": len(catalog), "rejected": len(evidence_rejected)},
        "weights": WEIGHTS,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Rank creator opportunities from a structured JSON file.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = rank_opportunities(json.loads(args.input.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        result = {"status": "failed", "ranked": [], "rejected": [], "evidenceRejected": [], "errors": [f"input:{type(exc).__name__}:{exc}"]}
    body = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(body, encoding="utf-8")
    else:
        sys.stdout.write(body)
    return 0 if result["status"] == "complete" and not result["rejected"] and not result["evidenceRejected"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
