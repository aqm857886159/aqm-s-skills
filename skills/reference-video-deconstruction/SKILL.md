---
name: reference-video-deconstruction
description: Deconstruct a local or user-authorized reference video into timestamped visual, audio, text, editing, and narrative evidence, then translate observed mechanisms into an original production plan. Use whenever the user asks to analyze a reference video, break down shots or pacing, inspect missing audio/black frames, reproduce a content structure, or says “拆解参考视频”“分析镜头节奏”“看看这条视频为什么有效”.
---

# Reference Video Deconstruction

Requirements: FFmpeg and FFprobe for local extraction. Optional ASR/OCR needs runtime-provided tools; keep media local unless the user explicitly approves an upload-capable tool.

## Mission

Turn an authorized video into timestamped, inspectable evidence and reusable creative mechanisms. The goal is to understand structure, not to imitate protected expression or infer content from a thumbnail.

## Success bar

A strong deconstruction:

- records source identity, duration, dimensions, codecs, and whether an audio stream exists;
- samples enough visual evidence to establish shot and layout changes without extracting the entire video;
- keeps observed image, audible speech, on-screen text, editing pattern, and interpretation separate;
- maps hook, promise, progression, proof, payoff, and CTA to timestamps when present;
- identifies what can be adapted as a mechanism and what should not be copied;
- turns the analysis into an original shot/material plan for the user's goal.

## Workflow

1. **Confirm source and purpose.** Use a local file or user-authorized media. Establish whether the task is debugging playback, studying narrative, planning an edit, or recreating a general mechanism.
2. **Probe before viewing.** From this Skill directory run `python3 scripts/extract_video_evidence.py /path/video.mp4 --output-dir /tmp/video-evidence --max-frames 24`. Check duration, orientation, codec, and `hasAudio` before making claims about silence or rendering.
3. **Inspect extraction status.** Read `coverage`, `analysisStatus`, `visualSignal`, and `audioSignal`. The bundled script checks bounded luma samples and audio volume locally; the thresholds identify near-black/digital-silence evidence, not human-perceived quality. ASR and OCR remain `not_run` until an actual runtime tool performs them.
4. **Build evidence lanes.** Read `references/deconstruction-contract.md`. Keep visual observations, audio/speech, on-screen text, edit transitions, and narrative interpretation in separate columns with timestamps.
5. **Diagnose playback problems when relevant.** Compare source probe, decoded sample frames, canvas/preview behavior, mute/volume state, and application logs. A valid local decode plus a black canvas usually narrows the issue to rendering or asset delivery; it does not prove the exact cause.
6. **Segment by meaningful change.** Use scene frames as candidates, then inspect around cuts. Do not equate every extracted frame with a shot or infer precise cut time when the evidence is sparse.
7. **Explain mechanisms.** Identify attention shifts, information density, pacing, proof placement, sound-image relationship, and transitions. Cite timestamps for each claim.
8. **Translate, do not clone.** Preserve the user's subject, voice, branding, assets, and constraints. Convert mechanisms into an original beat sheet, shot list, and asset requirements.
9. **Deliver.** Start with source and coverage, then timeline, mechanisms, playback findings if any, adaptation plan, and evidence gaps.

## Decision rules

- `hasAudio: false` proves there is no detected audio stream; `hasAudio: true` does not prove it is audible or correctly mixed.
- `audioSignal.signalAboveMinus60Db: false` means the bounded FFmpeg volume scan found no signal above its declared threshold; it does not diagnose mute state in the target app.
- `visualSignal.blackFrameRatio` describes bounded decoded samples under the declared luma rule; it is not proof that every frame is black.
- Successfully extracted frames prove FFmpeg can decode sampled source frames. They do not prove the target application's browser renderer can display them.
- ASR text is a transcript candidate, not proof of exact wording. Mark confidence and language/tool when available.
- OCR and subtitles describe text evidence; they do not replace visual inspection of placement, hierarchy, or occlusion.
- A pacing claim needs timestamps and at least two comparable segments.
- Adapt generic techniques such as delayed payoff or proof-first ordering; do not copy scripts, footage, creator identity, or distinctive protected sequences.

## Boundaries

- Do not download restricted media, bypass DRM/paywalls, or assume the user owns a public video.
- Do not upload a local or private video without explicit user approval.
- Do not extract more frames or audio than the task needs.
- Do not invent dialogue, text, transitions, or sound when ASR/OCR/audio inspection was not run.
- Do not overwrite a non-empty evidence directory unless the user explicitly chooses `--force` after checking its contents.

## Common failure modes

- Summarizing the title and calling it video deconstruction.
- Claiming “no sound” without checking for an audio stream, mute state, and decode path.
- Treating scene-detection output as a finished edit decision list.
- Mixing observations and creative interpretation in one confident paragraph.
- Turning mechanism analysis into a near-copy of the source.

## Gotchas

- Variable-frame-rate video and edit transitions can make exact cut timestamps approximate.
- Rotation metadata, alpha formats, HDR color, unusual codecs, CORS, object URL lifetime, and GPU/browser paths can cause a black application canvas even when local decode works.
- Very static videos may produce few scene frames; the extractor adds uniform samples and reports both under one bound.
- `--force` replaces named evidence outputs but does not make an arbitrary shared output directory safe. Prefer a new directory per source hash.

## Final review

Before returning, verify:

- source hash, probe, extraction bound, and missing lanes are stated;
- each timeline claim has a timestamp and evidence type;
- observed facts and interpretation are visibly separate;
- audio and black-frame diagnoses do not exceed the checks actually run;
- the adaptation plan is original and names required assets;
- no restricted media or private data was uploaded or republished.

Use `references/deconstruction-contract.md` for the evidence timeline and delivery format.
