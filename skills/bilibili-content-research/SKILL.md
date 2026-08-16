---
name: bilibili-content-research
description: Research a public Bilibili video from its metadata, subtitle tracks, bounded comment sample, and observable content structure, then separate audience evidence from interpretation. Use whenever the user provides a BV/video URL, asks to study a Bilibili creator or comments, wants content deconstruction or audience questions, or says “分析B站视频”“看评论区”“研究这个UP主/AV视频”.
license: MIT
compatibility: Public live collection requires network access. The bundled read-only collector uses Python 3.9+ with no cookies or third-party packages; Bilibili may change unofficial web endpoints.
metadata:
  author: aqm857886159
  version: "0.1.0"
---

# Bilibili Content Research

## Mission

Turn one public Bilibili video into a bounded evidence package and a useful content or audience analysis. Metadata, subtitles, comments, and visible video evidence answer different questions; never collapse them into one source of truth.

## Success bar

A strong result:

- resolves the exact BV and canonical video URL;
- records what was fetched, how many comments were sampled, and what was missing;
- treats subtitles as timed speech/text evidence, not guaranteed ground truth;
- distinguishes creator claims, audience comments, observable structure, and your inference;
- produces decisions for the user's goal, such as unanswered questions, hook mechanics, or follow-up content;
- performs no login, posting, liking, following, or bulk downloading.

## Workflow

1. **Clarify the job.** Determine whether the user wants content structure, audience research, factual extraction, competitor learning, or feedback triage. Ask for a BV/URL if none is available.
2. **Collect public evidence.** From this Skill directory run `python3 scripts/bilibili_public.py "<BV-or-URL>" --comments 20 --output /tmp/bilibili-evidence.json`. Start with 20 comments; raise the bound only when the user needs a broader sample.
3. **Inspect coverage before analysis.** Read `coverage`, `errors`, and `boundaries`. Missing subtitles or comments is a result to report, not content to reconstruct.
4. **Establish four layers.** Keep metadata, timed subtitles, comment evidence, and observed visual/audio evidence separate. If actual video inspection is necessary and permitted, sample it with the runtime's browser/media tools or `reference-video-deconstruction`.
5. **Analyze for the stated job.** For content structure, map hook, promise, proof, progression, and CTA to timestamps. For audience research, cluster repeated questions, misunderstandings, objections, and praise; include representative links, not usernames.
6. **Challenge sample bias.** Comments are self-selected and ordering can change. Do not infer the whole audience or creator performance from a small visible sample.
7. **Deliver.** Use `references/evidence-contract.md`: scope, evidence coverage, findings, representative evidence, gaps, and next actions.

## Decision rules

- Use subtitles for wording and timing only when a track is returned. Label auto-generated or unknown provenance when the API does not establish it.
- A repeated comment theme needs at least two distinct comment IDs. Otherwise call it an individual signal.
- High likes make a comment visible, not correct.
- Metadata can identify scale and format; it cannot prove why the video performed.
- Learning a mechanism is allowed; copying a creator's script, identity, or protected media is not the default outcome.
- When a conclusion needs full visual evidence, say so and switch to local/browser deconstruction rather than guessing from title and subtitles.

## Boundaries

- Read only public data. Do not request or reuse account cookies.
- Do not bypass login, region, payment, anti-bot, deleted-content, or privacy controls.
- Do not send comments, messages, likes, coins, favorites, or follows.
- Do not download or republish source video unless the user separately establishes permission.
- Do not expose commenters' names in a shareable report; quote minimally and link to source evidence.
- If the public endpoint blocks or changes, stop after a bounded attempt and report the missing lane.

## Common failure modes

- Calling a title/description summary a video analysis.
- Treating ten comments as audience statistics.
- Mixing the creator's words with commenter opinions.
- Reconstructing missing subtitles from memory or nearby text.
- Producing a “viral formula” with no timestamped evidence.

## Gotchas

- Bilibili's public web comment endpoint is not a stable official product API and currently requires WBI signing. Endpoint drift is expected.
- A video can have multiple pages and subtitle tracks. Preserve `cid` and language rather than merging silently.
- Public subtitle URLs can be protocol-relative and temporary.
- The collector intentionally retrieves one bounded comment page and reports its limit; it is not a crawler.

## Final review

Before returning, verify:

- BV, URL, capture time, and sample limits are present;
- every finding names its evidence layer;
- individual comments are not presented as population-level truth;
- missing lanes and endpoint errors are visible;
- no cookie, user identity, or outbound action was used;
- recommendations explain what to do next, not what to copy.

Use `references/evidence-contract.md` for the report.
