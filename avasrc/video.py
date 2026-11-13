"""Video clock list loader. Probe uses this; please reuse it."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


class VideoError(ValueError):
    pass


@dataclass
class VideoClock:
    fps: float
    frame_count: int
    # pts_seconds[i] is the capture time of frame i, in recorder seconds
    pts_seconds: list[float]
    clap_frame: int | None
    clap_label: str | None
    tail_mark_frame: int | None = None


def load_clock(path: str) -> VideoClock:
    doc = json.loads(Path(path).read_text())
    pts = [float(x) for x in doc["pts_seconds"]]
    if len(pts) < 2:
        raise VideoError("video clock needs at least two timestamps")
    return VideoClock(
        fps=float(doc["fps"]),
        frame_count=len(pts),
        pts_seconds=pts,
        clap_frame=doc.get("clap_frame"),
        clap_label=doc.get("clap_label"),
        tail_mark_frame=doc.get("tail_mark_frame"),
    )
