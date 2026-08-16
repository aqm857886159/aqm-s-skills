#!/usr/bin/env python3
"""Create a bounded, read-only inventory of a local source repository."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.parse
from collections import Counter
from pathlib import Path


IGNORED = {".git", "node_modules", "dist", "build", ".next", "target", "vendor", ".venv", "__pycache__"}
MANIFESTS = {
    "package.json", "pyproject.toml", "requirements.txt", "Cargo.toml", "go.mod",
    "pom.xml", "build.gradle", "Gemfile", "composer.json", "mix.exs", "Package.swift",
}
SOURCE_NAMES = {"src", "app", "apps", "lib", "packages", "cmd", "crates", "server", "client"}
TEST_NAMES = {"test", "tests", "spec", "specs", "__tests__", "e2e", "evals"}
EXTENSIONS = {
    ".ts": "TypeScript", ".tsx": "TypeScript", ".js": "JavaScript", ".jsx": "JavaScript",
    ".py": "Python", ".rs": "Rust", ".go": "Go", ".java": "Java", ".kt": "Kotlin",
    ".swift": "Swift", ".rb": "Ruby", ".php": "PHP", ".c": "C", ".cpp": "C++",
}


def _git(root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args], check=True, capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip()
    except (FileNotFoundError, subprocess.SubprocessError):
        return None


def _safe_remote(value: str | None) -> str | None:
    if not value:
        return value
    if "://" in value:
        parsed = urllib.parse.urlsplit(value)
        host = parsed.hostname or ""
        try:
            port = parsed.port
        except ValueError:
            port = None
        if port:
            host = f"{host}:{port}"
        return urllib.parse.urlunsplit((parsed.scheme, host, parsed.path, "", ""))
    if "@" in value:
        return value.split("@", 1)[-1]
    return value.split("?", 1)[0].split("#", 1)[0]


def build_snapshot(root: Path) -> dict[str, object]:
    root = root.resolve()
    if not root.is_dir():
        raise ValueError(f"repository path is not a directory: {root}")
    top = sorted(path.name for path in root.iterdir() if path.name not in IGNORED)
    directories = sorted(path.name for path in root.iterdir() if path.is_dir() and path.name not in IGNORED)
    files = sorted(path.name for path in root.iterdir() if path.is_file())
    language_counts: Counter[str] = Counter()
    file_count = 0
    for path in root.rglob("*"):
        if not path.is_file() or any(part in IGNORED for part in path.relative_to(root).parts):
            continue
        file_count += 1
        language = EXTENSIONS.get(path.suffix.lower())
        if language:
            language_counts[language] += 1
        if file_count >= 50_000:
            break
    readmes = sorted(name for name in files if name.lower().startswith("readme"))
    snapshot: dict[str, object] = {
        "rootName": root.name,
        "topLevelEntries": top,
        "fileCountScanned": file_count,
        "scanTruncated": file_count >= 50_000,
        "manifests": sorted(name for name in files if name in MANIFESTS),
        "readmeFiles": readmes,
        "licenseFiles": sorted(name for name in files if name.upper().startswith(("LICENSE", "COPYING"))),
        "ruleFiles": sorted(name for name in files if name in {"AGENTS.md", "CLAUDE.md", "CODEX.md"}),
        "sourceDirectories": sorted(name for name in directories if name.lower() in SOURCE_NAMES),
        "testDirectories": sorted(name for name in directories if name.lower() in TEST_NAMES),
        "languagesByFileCount": dict(language_counts.most_common()),
        "git": {
            "branch": _git(root, "branch", "--show-current"),
            "head": _git(root, "rev-parse", "--short", "HEAD"),
            "remote": _safe_remote(_git(root, "remote", "get-url", "origin")),
            "status": (_git(root, "status", "--short") or "").splitlines(),
        },
    }
    return snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description="Inventory a local repository without modifying it.")
    parser.add_argument("repository", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    exit_code = 0
    try:
        payload = {"status": "complete", **build_snapshot(args.repository)}
    except (OSError, ValueError) as exc:
        exit_code = 2
        payload = {
            "status": "failed",
            "error": {"code": "snapshot_failed", "message": f"{type(exc).__name__}: {exc}"},
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
