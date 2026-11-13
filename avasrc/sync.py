"""Lock independent audio to a video clock via windowed-sinc resampling."""

from __future__ import annotations

import json
import math
from pathlib import Path

from . import video, wavio


class NotImplementedSync(NotImplementedError):
    pass


DEFAULT_POLICY = {
    "output_rate": 48000,
    "clap_search_s": 3.0,
    "max_clap_error_ms": 2.0,
    "max_tail_error_ms": 2.0,
    "sinc_zero_crossings": 12,
}


def _load_policy(path: str) -> dict:
    policy = dict(DEFAULT_POLICY)
    doc = json.loads(Path(path).read_text())
    for key in policy:
        if key in doc:
            policy[key] = doc[key]
    return policy


def _abs_peak_index(samples: list[float], start: int, stop: int) -> int:
    start = max(0, start)
    stop = min(len(samples), stop)
    best_i = -1
    best = -1.0
    for i in range(start, stop):
        a = abs(samples[i])
        if a > best:
            best = a
            best_i = i
    return best_i


def _refine_peak(samples: list[float], i: int) -> float:
    """Parabolic interpolation on |x| around sample i for sub-sample position."""
    if i <= 0 or i >= len(samples) - 1:
        return float(i)
    y0 = abs(samples[i - 1])
    y1 = abs(samples[i])
    y2 = abs(samples[i + 1])
    denom = y0 - 2.0 * y1 + y2
    if denom == 0.0:
        return float(i)
    offset = 0.5 * (y0 - y2) / denom
    if abs(offset) > 1.0:
        offset = 0.0
    return i + offset


def _hann(d: float, half_width: float) -> float:
    return 0.5 * (1.0 + math.cos(math.pi * d / half_width))


def _sinc(d: float) -> float:
    if d == 0.0:
        return 1.0
    x = math.pi * d
    return math.sin(x) / x


def _resample_channel(
    src: list[float],
    positions: list[float],
    zero_crossings: int,
) -> list[float]:
    """Windowed-sinc interpolation of src at fractional positions.

    Kernel spans 2 * zero_crossings taps (zero_crossings on each side),
    weighted by a Hann window. Positions outside the input yield 0.
    """
    n = len(src)
    k = zero_crossings
    out = []
    for pos in positions:
        base = math.floor(pos)
        acc = 0.0
        norm = 0.0
        for j in range(base - k + 1, base + k + 1):
            if 0 <= j < n:
                d = pos - j
                w = _sinc(d) * _hann(d, k)
                acc += src[j] * w
                norm += w
        if norm != 0.0:
            acc /= norm
        out.append(acc)
    return out


def _write_report(path: str, report: dict) -> None:
    Path(path).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")


def sync(audio_path: str, clock_path: str, policy_path: str, out_wav: str, report_path: str) -> int:
    report = {
        "audio": audio_path,
        "clock": clock_path,
        "decision": "reject",
        "reason_codes": [],
        "clap_error_ms": None,
        "tail_error_ms": None,
        "drift_ppm": None,
        "output_rate": None,
        "output_frames": None,
    }
    try:
        policy = _load_policy(policy_path)
        wav = wavio.read_wav(audio_path)
        clock = video.load_clock(clock_path)
    except Exception as e:
        report["reason_codes"].append("read_error")
        try:
            _write_report(report_path, report)
        except OSError:
            pass
        print(f"avasrc sync: failed to read inputs: {e}")
        return 2

    output_rate = int(policy["output_rate"])
    pts = clock.pts_seconds
    if clock.clap_frame is None:
        report["reason_codes"].append("no_clap_frame")
        _write_report(report_path, report)
        return 1
    clap_video_t = pts[clock.clap_frame]

    mono = wav.samples[0]
    label_rate = wav.sample_rate

    # Locate the clap: absolute peak within the first clap_search_s seconds.
    search_end = int(policy["clap_search_s"] * label_rate)
    clap_i = _abs_peak_index(mono, 0, search_end)
    if clap_i < 0 or abs(mono[clap_i]) < 1e-3:
        report["reason_codes"].append("clap_not_found")
        _write_report(report_path, report)
        return 1
    clap_pos = _refine_peak(mono, clap_i)

    # Drift: linear fit anchored at the clap, using the tail mark pulse when
    # the clock file names a tail_mark_frame and the pulse is readable.
    drift_ppm = 0.0
    tail_video_t = None
    tail_frame = getattr(clock, "tail_mark_frame", None)
    if tail_frame is not None and 0 <= tail_frame < len(pts):
        tail_video_t = pts[tail_frame]
        # second pulse: absolute peak well after the clap
        tail_i = _abs_peak_index(mono, clap_i + label_rate // 2, len(mono))
        if tail_i >= 0 and abs(mono[tail_i]) >= 1e-3:
            tail_pos = _refine_peak(mono, tail_i)
            span_in = tail_pos - clap_pos
            span_video = tail_video_t - clap_video_t
            if span_in > 0 and span_video > 0:
                # seconds of camera time per input sample
                sec_per_sample = span_video / span_in
                drift_ppm = (1.0 / (sec_per_sample * label_rate) - 1.0) * 1e6
    report["drift_ppm"] = drift_ppm

    # Camera time per input sample from the fit (clap is the zero point).
    # Recorder runs fast by drift_ppm, so its real rate is label_rate*(1+drift).
    sec_per_sample = 1.0 / (label_rate * (1.0 + drift_ppm * 1e-6))

    # Output sample n lands on camera time pts[0] + n / output_rate.
    video_span = pts[-1] - pts[0]
    output_frames = int(math.ceil(video_span * output_rate)) + 1
    positions = []
    for n in range(output_frames):
        t = pts[0] + n / output_rate
        positions.append(clap_pos + (t - clap_video_t) / sec_per_sample)

    zero_crossings = max(12, int(policy["sinc_zero_crossings"]))
    out_channels = [
        _resample_channel(wav.samples[c], positions, zero_crossings)
        for c in range(wav.channels)
    ]
    wavio.write_wav(out_wav, output_rate, out_channels, width=wav.sample_width)

    # Verify: clap and tail marks in the output must land on their video times.
    out_mono = out_channels[0]
    ok = True
    expected_clap_n = (clap_video_t - pts[0]) * output_rate
    win = int(0.05 * output_rate)
    oi = _abs_peak_index(out_mono, int(expected_clap_n) - win, int(expected_clap_n) + win)
    if oi < 0:
        report["reason_codes"].append("clap_verify_failed")
        ok = False
    else:
        out_clap_pos = _refine_peak(out_mono, oi)
        clap_error_ms = abs(out_clap_pos - expected_clap_n) / output_rate * 1000.0
        report["clap_error_ms"] = clap_error_ms
        if clap_error_ms > float(policy["max_clap_error_ms"]):
            report["reason_codes"].append("clap_error_exceeded")
            ok = False

    if tail_video_t is not None:
        expected_tail_n = (tail_video_t - pts[0]) * output_rate
        oi = _abs_peak_index(out_mono, int(expected_tail_n) - win, int(expected_tail_n) + win)
        if oi < 0:
            report["reason_codes"].append("tail_verify_failed")
            ok = False
        else:
            out_tail_pos = _refine_peak(out_mono, oi)
            tail_error_ms = abs(out_tail_pos - expected_tail_n) / output_rate * 1000.0
            report["tail_error_ms"] = tail_error_ms
            if tail_error_ms > float(policy["max_tail_error_ms"]):
                report["reason_codes"].append("tail_error_exceeded")
                ok = False

    report["output_rate"] = output_rate
    report["output_frames"] = output_frames
    if ok:
        report["decision"] = "ok"
        report["reason_codes"] = []
    _write_report(report_path, report)
    return 0 if ok else 1
