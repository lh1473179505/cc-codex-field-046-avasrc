"""Inventory an independent audio take against a video clock."""

from __future__ import annotations

import json

from . import video, wavio


def _peak_index(samples: list[float]) -> int:
    best_i = 0
    best = -1.0
    for i, v in enumerate(samples):
        a = abs(v)
        if a > best:
            best = a
            best_i = i
    return best_i


def probe_paths(audio_path: str, clock_path: str) -> dict:
    wav = wavio.read_wav(audio_path)
    clock = video.load_clock(clock_path)
    mono = wav.samples[0]
    peak = _peak_index(mono)
    video_span = clock.pts_seconds[-1] - clock.pts_seconds[0]
    # nominal span of frames at declared fps
    nominal = (clock.frame_count - 1) / clock.fps if clock.fps else None
    return {
        "audio": audio_path,
        "clock": clock_path,
        "sample_rate_label": wav.sample_rate,
        "channels": wav.channels,
        "audio_frames": wav.frames,
        "audio_duration_s": wav.frames / wav.sample_rate,
        "video_fps": clock.fps,
        "video_frames": clock.frame_count,
        "video_span_s": video_span,
        "video_nominal_s": nominal,
        "clap_frame": clock.clap_frame,
        "clap_label": clock.clap_label,
        "audio_peak_sample": peak,
        "audio_peak_s": peak / wav.sample_rate,
    }


def format_probe(info: dict) -> str:
    return json.dumps(info, ensure_ascii=False, indent=2)
