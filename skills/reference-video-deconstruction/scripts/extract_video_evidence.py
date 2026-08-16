#!/usr/bin/env python3
"""Extract bounded local video metadata and visual evidence with FFmpeg."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


def _ratio(value: object) -> float | None:
    text = str(value or "")
    try:
        left, right = text.split("/", 1)
        return float(left) / float(right) if float(right) else None
    except (ValueError, ZeroDivisionError):
        return None


def parse_probe(raw: dict[str, Any]) -> dict[str, object]:
    streams = raw.get("streams") or []
    video = next((stream for stream in streams if stream.get("codec_type") == "video"), {})
    audio = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)
    width, height = int(video.get("width") or 0), int(video.get("height") or 0)
    orientation = "unknown"
    if width and height:
        orientation = "portrait" if height > width else "landscape" if width > height else "square"
    return {
        "durationSeconds": float((raw.get("format") or {}).get("duration") or 0),
        "format": (raw.get("format") or {}).get("format_name"),
        "hasVideo": bool(video),
        "videoCodec": video.get("codec_name"),
        "width": width or None,
        "height": height or None,
        "orientation": orientation,
        "frameRate": _ratio(video.get("avg_frame_rate")),
        "hasAudio": audio is not None,
        "audioCodec": audio.get("codec_name") if audio else None,
        "audioSampleRate": int(audio.get("sample_rate")) if audio and str(audio.get("sample_rate", "")).isdigit() else None,
        "audioChannels": audio.get("channels") if audio else None,
    }


def sample_times(duration_seconds: float, max_frames: int = 12) -> list[float]:
    if duration_seconds <= 0 or max_frames <= 0:
        return []
    count = min(max_frames, max(1, int(duration_seconds // 2) + 1))
    return [round((index + 0.5) * duration_seconds / count, 3) for index in range(count)]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _run(command: list[str], timeout: float = 180.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=True, capture_output=True, text=True, timeout=timeout)


def _clear_generated_evidence(output_dir: Path) -> None:
    frames_dir = output_dir / "frames"
    if frames_dir.is_symlink():
        raise ValueError(f"frames directory must not be a symbolic link: {frames_dir}")
    evidence_file = output_dir / "evidence.json"
    if evidence_file.is_file():
        evidence_file.unlink()
    if frames_dir.is_dir():
        for pattern in ("scene-*.jpg", "sample-*.jpg"):
            for frame in frames_dir.glob(pattern):
                if frame.is_file():
                    frame.unlink()


def extract(video: Path, output_dir: Path, threshold: float = 0.32, max_frames: int = 24, force: bool = False) -> dict[str, object]:
    video = video.resolve()
    output_dir = output_dir.resolve()
    if not video.is_file():
        raise ValueError(f"video does not exist: {video}")
    if not shutil.which("ffprobe") or not shutil.which("ffmpeg"):
        raise RuntimeError("ffprobe and ffmpeg are required")
    if output_dir.exists() and any(output_dir.iterdir()) and not force:
        raise ValueError(f"output directory is not empty: {output_dir}; pass --force to overwrite named evidence files")
    output_dir.mkdir(parents=True, exist_ok=True)
    if force:
        _clear_generated_evidence(output_dir)
    frames_dir = output_dir / "frames"
    frames_dir.mkdir(exist_ok=True)
    probe_raw = json.loads(_run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(video)]).stdout)
    probe = parse_probe(probe_raw)
    if not probe["hasVideo"]:
        raise ValueError(f"no video stream detected: {video}")
    scene_pattern = frames_dir / "scene-%04d.jpg"
    scene = _run([
        "ffmpeg", "-y", "-hide_banner", "-i", str(video),
        "-vf", f"select=gt(scene\\,{threshold}),scale=640:-2,format=yuvj420p,showinfo",
        "-fps_mode", "vfr", "-frames:v", str(max_frames), str(scene_pattern),
    ])
    times = [float(value) for value in re.findall(r"pts_time:([0-9.]+)", scene.stderr)]
    frame_paths = sorted(frames_dir.glob("scene-*.jpg"))
    evidence: list[dict[str, object]] = [
        {"index": index + 1, "timeSeconds": round(times[index], 3) if index < len(times) else None, "relativePath": str(path.relative_to(output_dir))}
        for index, path in enumerate(frame_paths)
    ]
    if len(evidence) < min(3, max_frames):
        for index, timestamp in enumerate(sample_times(float(probe["durationSeconds"]), min(max_frames, 8)), start=1):
            target = frames_dir / f"sample-{index:04d}.jpg"
            _run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", str(timestamp), "-i", str(video), "-frames:v", "1", "-vf", "scale=640:-2,format=yuvj420p", str(target)])
            evidence.append({"index": len(evidence) + 1, "timeSeconds": timestamp, "relativePath": str(target.relative_to(output_dir))})
            if len(evidence) >= max_frames:
                break
    result = {
        "schemaVersion": 1,
        "source": {"fileName": video.name, "contentHash": _sha256(video)},
        "probe": probe,
        "visualEvidence": evidence,
        "coverage": {"sceneThreshold": threshold, "maxFrames": max_frames, "framesExtracted": len(evidence)},
        "analysisStatus": {"visualEvidence": "ready", "asr": "not_run", "ocr": "not_run"},
    }
    (output_dir / "evidence.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract local, bounded video evidence without uploading media.")
    parser.add_argument("video", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--scene-threshold", type=float, default=0.32)
    parser.add_argument("--max-frames", type=int, default=24)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if not 0 <= args.scene_threshold <= 1:
        parser.error("--scene-threshold must be between 0 and 1")
    if not 1 <= args.max_frames <= 100:
        parser.error("--max-frames must be between 1 and 100")
    result = extract(args.video, args.output_dir, args.scene_threshold, args.max_frames, args.force)
    sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
