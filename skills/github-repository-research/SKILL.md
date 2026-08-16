---
name: github-repository-research
description: Investigate a GitHub repository or local clone and produce an evidence-backed architecture map, maintenance assessment, license/reuse boundary, and answer to a concrete technical question. Use whenever the user asks to inspect, understand, compare, audit, reuse, or learn from a GitHub repo, including “看一下这个仓库”“研究源码”“这个项目怎么实现的”“哪些代码能复用”.
license: MIT
compatibility: Requires git for repository history. Public remote research needs network access; local repository analysis works offline with Python 3.9+.
metadata:
  author: aqm857886159
  version: "0.1.0"
---

# GitHub Repository Research

## Mission

Answer a real question about a repository from its current source, tests, history, and license. A repository map is useful only when it explains what the code proves, what remains unverified, and what can safely be reused.

## Success bar

A strong investigation:

- identifies the exact revision and whether the working tree is dirty;
- reads repository instructions before interpreting code;
- traces behavior from entrypoint through implementation and tests;
- supports important claims with clickable file and line references;
- distinguishes implemented behavior, documentation intent, and your inference;
- checks maintenance and license before recommending reuse;
- directly answers the user's question before offering broader observations.

## Workflow

1. **Fix the question.** Identify whether the user needs architecture understanding, implementation discovery, health assessment, comparison, security review, or reuse guidance. Do not perform all six by default.
2. **Resolve the source.** Prefer an existing local clone. Record branch, commit, remote, and status. If only a URL exists, use a temporary shallow clone or official GitHub API after confirming network access; do not alter an unrelated checkout.
3. **Read repository rules.** Find root and nested `AGENTS.md`, `CLAUDE.md`, `CODEX.md`, contribution guides, and architecture docs relevant to the target path.
4. **Take a deterministic snapshot.** From this Skill directory, run `python3 scripts/repo_snapshot.py /path/to/repo`. Use it to find manifests, source/test directories, license files, and languages; it is an index, not the analysis.
5. **Trace the behavior.** Start at public entrypoints or user-facing calls, then follow data/control flow to the implementation and tests. Search symbols with `rg`; do not infer architecture from filenames alone.
6. **Check evidence layers.** Compare README claims, code, tests, release notes, open issues, and recent commits. Prefer behavior exercised by tests or real call sites.
7. **Assess reuse.** Check license, dependency weight, coupling, data/privacy assumptions, stable contracts, and the smallest independently reusable unit.
8. **Deliver.** Use `references/report-contract.md`. Lead with the answer, then architecture, evidence, risks, reuse boundary, and unresolved questions.

## Decision rules

- For a **how does it work** question, spend most effort on one end-to-end call path.
- For a **can we reuse it** question, license and dependency boundaries are blocking evidence, not footnotes.
- For a **project health** question, examine release cadence, recent commits, issue response, test/CI presence, and maintainer signals. Stars are adoption context, not health proof.
- For a **comparison**, use the same criteria and revision date for every repository.
- If the default branch and local branch differ, say which one supports each claim.
- If generated, vendored, fixture, or build output dominates a search result, exclude it and search the authored source.

## Boundaries

- Do not modify, build, install dependencies, execute repository scripts, or contact maintainers unless the user asked and the action is necessary.
- Do not print tokens embedded in remotes, config, logs, or fixtures. Sanitize evidence.
- Do not call documentation an implementation.
- Do not assume a repository is commercially reusable because it is public.
- Do not claim a test passes unless you ran it and report the exact command.

## Common failure modes

- Reciting the README with no source verification.
- Listing folders without explaining ownership or data flow.
- Searching only for keywords and missing indirect call paths.
- Recommending a large subsystem when one contract or algorithm is the reusable unit.
- Treating a busy commit graph or star count as product maturity.

## Gotchas

- A local worktree may contain user changes or conflicts. Read around them; never reset or clean them for research.
- GitHub's Issues API also returns pull requests unless explicitly filtered.
- Monorepos often have nested rules and licenses. Resolve instructions and license at the target package, not only the root.
- A passing unit test may validate a schema without proving the user-facing journey works.

## Final review

Before returning, verify:

- the repository revision and scope are stated;
- each major technical claim points to source or test evidence;
- docs, implementation, tests, and inference are not mixed;
- reuse advice includes license and coupling;
- commands reported as passing were actually run;
- the user's original question is answered in the opening section.

Use `references/report-contract.md` for the final shape.
