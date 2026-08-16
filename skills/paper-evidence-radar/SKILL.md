---
name: paper-evidence-radar
description: Search, verify, and triage recent academic papers into actionable methods, architecture lessons, and evaluation benchmarks. Use whenever the user asks for papers, literature review, arXiv research, latest/SOTA work, research radar, academic evidence, or wants to know what research can be applied to a real project; also trigger for Chinese requests such as “搜论文”“论文雷达”“最近有什么研究可以落地”.
---

# Paper Evidence Radar

Requirements: Python 3.9+ for the bundled collector and network access for live research. Fixture parsing works offline and uses no third-party package.

## Mission

Turn a research question into a small set of current, verified decisions. The job is not to produce a long bibliography. It is to distinguish work the user can apply now, work that should change system design, and work that provides a useful benchmark.

Answer in the user's language. Preserve original paper titles and links.

## Success bar

A strong result:

- starts from the user's real decision or bottleneck;
- searches recent primary sources and records the search window;
- verifies claims on the paper page, project page, and official code when available;
- separates paper claims from your inference;
- names maturity, reproduction requirements, and what is unavailable;
- ends with one or two concrete next actions instead of an unread inbox.

## Workflow

1. **Frame the decision.** Restate the practical question, target system, constraints, and time horizon. Ask only when a missing constraint would materially change the search.
2. **Define a search matrix.** Use 3-8 focused query lanes: task, failure mode, method family, benchmark, and relevant synonyms. Default to the last six months for fast-moving AI topics; widen only when foundational work is needed.
3. **Collect candidates.** Use the runtime's web research tools. For a bounded arXiv starting set, run `python3 scripts/arxiv_search.py "<query>" --max-results 20 --since YYYY-MM-DD`. Natural multi-word queries default to term-wise `AND`; use `--query-mode phrase`, `any`, or `raw` only deliberately. Inspect `coverage.apiQuery`, pre/post-filter counts, and errors. The script discovers candidates; it does not prove importance.
4. **Verify primary evidence.** Open the original abstract/paper and, when claimed, the official project or code repository. Record submission/update date, authors or lab, code/data availability, license, and reproduction boundary.
5. **Deduplicate.** Collapse paper versions and compare against previous radar reports or the user's known list. A new arXiv version is an update, not automatically a new finding.
6. **Triage every retained paper.** Read `references/evidence-rubric.md` and place each item in exactly one lane: actionable now, architecture lesson, or evaluation benchmark. Exclude weakly related items rather than creating a fourth “interesting” pile.
7. **Map to the user's system.** Name the module, workflow, experiment, or decision affected. If the codebase is available, verify the target path before citing it.
8. **Deliver the radar.** State the search window and coverage, present the three lanes, list screened-out noise as a count, and show what changed from the previous run when one exists.

## Decision rules

- **“Latest” and “SOTA” require current verification.** A recent date alone does not establish quality; an old benchmark win may no longer be current.
- **Actionable now** requires a plausible path under the user's constraints. Training-free, public code, available weights, stable APIs, or a method that can be implemented outside the model are stronger signals.
- **Architecture lesson** is for mechanisms that matter but cannot be directly integrated, such as methods requiring inaccessible model internals or expensive retraining.
- **Evaluation benchmark** is for datasets, rubrics, or metrics the user can actually run or adapt. State license and input requirements.
- Prefer one paper supported by code and a relevant experiment over five papers sharing fashionable keywords.
- If primary evidence conflicts with a blog or repository README, report the conflict and use the narrower claim.

## Boundaries

- Do not invent citation counts, star counts, affiliations, benchmark scores, code availability, or publication status.
- Do not cite a search-result snippet as proof. Use it only to locate the primary source.
- Do not call a method production-ready because a repository exists.
- Do not recommend copying code before checking its license and dependencies.
- Do not silently expand a user's topic into medical, legal, financial, or safety claims that require domain review.

## Common failure modes

- A bibliography with no decision attached.
- Treating the abstract's strongest sentence as independently verified truth.
- Calling a method “open source” when only a project page or inference patch exists.
- Mixing papers from different tasks because they share “agent” or “video” keywords.
- Filling a report with weak items so every query lane appears productive.

## Gotchas

- arXiv dates distinguish first submission from later revisions; record both when an update changes the result.
- Very new papers have weak citation signals. Use official code, project evidence, author/lab context, and reproducibility instead of pretending citation counts are meaningful.
- The bundled arXiv script uses the official Atom API and may be rate-limited. Keep queries bounded and do not retry aggressively.

## Final review

Before returning, verify:

- every retained item has a primary link and date;
- paper claims and your recommendations are visibly separate;
- each item belongs to one triage lane and names a user consequence;
- limitations, missing code, and reproduction cost are explicit;
- the first recommended action can be attempted without reading the whole report again.

Use the output contract in `references/evidence-rubric.md`.
