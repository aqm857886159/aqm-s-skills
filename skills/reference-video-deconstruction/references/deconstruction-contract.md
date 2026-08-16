# Video Deconstruction Contract

## Source and coverage

Always begin with:

- file name or authorized canonical source;
- content hash for local files;
- duration, orientation, dimensions, video codec, frame rate;
- audio stream presence and codec when detected;
- frame extraction method, threshold, maximum, and actual count;
- uniform luma sample count/rule and bounded audio-signal scan duration/threshold;
- ASR, OCR, subtitle, and full-playback status: ready, partial, not run, or failed.

## Timeline row

Use one row per meaningful beat or shot candidate:

| Time | Visual observation | Audio/speech | On-screen text | Edit | Narrative role | Confidence |
|---|---|---|---|---|---|---|

Observations describe only what the evidence shows. Narrative role is interpretation. Leave a lane blank or mark it unavailable instead of reconstructing missing information.

## Playback diagnosis

When the user reports silence or a black canvas, report checks independently:

1. source file exists and hash is stable;
2. probe detects video/audio streams;
3. FFmpeg decodes bounded sample frames;
4. decoded frames contain visible pixel variance;
5. target application receives the expected asset URL/blob;
6. media element readiness, mute/volume, errors, and canvas draw path;
7. browser codec/CORS/GPU constraints.

State which check first fails. Do not jump from symptom to root cause.

## Adaptation output

End with:

- mechanisms worth adapting and timestamp evidence;
- protected or source-specific expression not to copy;
- original beat sheet with target duration;
- shot and asset list;
- sound/text requirements;
- one low-cost prototype and its success check.
