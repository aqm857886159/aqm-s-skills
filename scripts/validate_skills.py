#!/usr/bin/env python3
"""Validate the repository's Agent Skills without third-party dependencies."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
REF_RE = re.compile(r"(?<![\w/])((?:scripts|references)/[A-Za-z0-9._/-]+)")


def frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n") or "\n---\n" not in text[4:]:
        raise ValueError("missing YAML frontmatter delimiters")
    raw, body = text[4:].split("\n---\n", 1)
    data: dict[str, str] = {}
    for line in raw.splitlines():
        match = re.match(r"^([a-z][a-z0-9-]*):\s*(.*)$", line)
        if match and match.group(2):
            data[match.group(1)] = match.group(2).strip().strip('"')
    return data, body


def validate_skill(directory: Path) -> list[str]:
    errors: list[str] = []
    skill_file = directory / "SKILL.md"
    if not skill_file.is_file():
        return [f"{directory.name}: missing SKILL.md"]
    try:
        data, body = frontmatter(skill_file.read_text(encoding="utf-8"))
    except ValueError as exc:
        return [f"{directory.name}: {exc}"]
    name = data.get("name", "")
    description = data.get("description", "")
    if name != directory.name:
        errors.append(f"{directory.name}: frontmatter name must match directory")
    if not NAME_RE.fullmatch(name) or len(name) > 64:
        errors.append(f"{directory.name}: invalid Agent Skills name")
    if not description or len(description) > 1024:
        errors.append(f"{directory.name}: description must be 1-1024 characters")
    if len(body.splitlines()) >= 500:
        errors.append(f"{directory.name}: SKILL.md body must stay below 500 lines")
    for reference in REF_RE.findall(body):
        target = directory / reference.rstrip("`.,)")
        if not target.exists():
            errors.append(f"{directory.name}: missing referenced file {reference}")
    eval_path = directory / "evals" / "evals.json"
    if not eval_path.is_file():
        errors.append(f"{directory.name}: missing evals/evals.json")
    else:
        try:
            evals = json.loads(eval_path.read_text(encoding="utf-8"))
            cases = evals.get("evals") or []
            if evals.get("skill_name") != name or len(cases) < 2:
                errors.append(f"{directory.name}: eval set must match name and contain at least two cases")
            ids: set[object] = set()
            for case in cases:
                if not isinstance(case, dict):
                    errors.append(f"{directory.name}: each eval must be an object")
                    continue
                case_id = case.get("id")
                if case_id in ids:
                    errors.append(f"{directory.name}: duplicate eval id {case_id}")
                ids.add(case_id)
                for relative in case.get("files") or []:
                    target = (directory / relative).resolve()
                    try:
                        target.relative_to(directory.resolve())
                    except ValueError:
                        errors.append(f"{directory.name}: eval file escapes skill directory: {relative}")
                        continue
                    if not target.is_file():
                        errors.append(f"{directory.name}: missing eval file {relative}")
        except json.JSONDecodeError as exc:
            errors.append(f"{directory.name}: invalid eval JSON: {exc}")
    return errors


def main() -> int:
    directories = sorted(path for path in SKILLS.iterdir() if path.is_dir())
    errors = [error for directory in directories for error in validate_skill(directory)]
    if len(directories) != 8:
        errors.append(f"repository must contain eight skills, found {len(directories)}")
    if errors:
        print("Skill validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(f"Validated {len(directories)} skills: structure, metadata, references, and eval sets are present.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
