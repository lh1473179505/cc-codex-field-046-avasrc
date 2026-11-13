"""PCM WAV / RF64 reader. Probe uses this; please reuse it. Only LPCM is supported."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path


class WavError(ValueError):
    pass


@dataclass
class WavFile:
    path: str
    sample_rate: int
    channels: int
    sample_width: int  # bytes
    frames: int
    samples: list[list[float]]  # channel-major, range [-1, 1)
    rf64: bool


def _decode_pcm(raw: bytes, width: int, channels: int) -> list[list[float]]:
    if width not in (2, 3, 4):
        raise WavError(f"unsupported sample width {width}")
    n = len(raw) // width
    if n % channels:
        raise WavError("truncated frame")
    frames = n // channels
    chans = [[] for _ in range(channels)]
    le = "little"
    i = 0
    for _ in range(frames):
        for c in range(channels):
            chunk = raw[i : i + width]
            i += width
            if width == 2:
                v = int.from_bytes(chunk, le, signed=True) / 32768.0
            elif width == 3:
                # 24-bit little-endian signed
                u = int.from_bytes(chunk, le, signed=False)
                if u & 0x800000:
                    u -= 0x1000000
                v = u / 8388608.0
            else:
                v = int.from_bytes(chunk, le, signed=True) / 2147483648.0
            chans[c].append(v)
    return chans


def _find_chunks(blob: bytes, rf64: bool) -> dict[str, tuple[int, int]]:
    # returns id -> (data_offset, size)
    if rf64:
        if blob[:4] != b"RF64" or blob[8:12] != b"WAVE":
            raise WavError("not RF64 WAVE")
        pos = 12
    else:
        if blob[:4] != b"RIFF" or blob[8:12] != b"WAVE":
            raise WavError("not RIFF WAVE")
        pos = 12
    out = {}
    ds64 = None
    while pos + 8 <= len(blob):
        cid = blob[pos : pos + 4]
        size = int.from_bytes(blob[pos + 4 : pos + 8], "little")
        data_off = pos + 8
        if cid == b"ds64":
            ds64 = blob[data_off : data_off + size]
        out[cid.decode("ascii", "replace")] = (data_off, size)
        pos = data_off + size + (size & 1)
    if rf64:
        if not ds64 or len(ds64) < 28:
            raise WavError("RF64 missing ds64")
        riff_size, data_size, sample_count = struct.unpack_from("<QQQ", ds64, 0)
        if "data" in out:
            off, _ = out["data"]
            out["data"] = (off, data_size)
        out["_ds64_sample_count"] = (0, sample_count)  # type: ignore
    return out


def read_wav(path: str) -> WavFile:
    blob = Path(path).read_bytes()
    rf64 = blob[:4] == b"RF64"
    chunks = _find_chunks(blob, rf64)
    if "fmt " not in chunks:
        raise WavError("missing fmt chunk")
    off, size = chunks["fmt "]
    fmt = blob[off : off + size]
    audio_format, channels, rate, _byte_rate, _block, bits = struct.unpack_from("<HHIIHH", fmt)
    if audio_format != 1:
        raise WavError(f"only PCM (format=1) is supported, got {audio_format}")
    width = bits // 8
    if "data" not in chunks:
        raise WavError("missing data chunk")
    doff, dsize = chunks["data"]
    raw = blob[doff : doff + dsize]
    samples = _decode_pcm(raw, width, channels)
    frames = len(samples[0]) if samples else 0
    return WavFile(path, rate, channels, width, frames, samples, rf64)


def write_wav(path: str, sample_rate: int, samples: list[list[float]], width: int = 2) -> None:
    """Write a classic RIFF WAV. samples is channel-major, range [-1, 1)."""
    channels = len(samples)
    frames = len(samples[0]) if samples else 0
    for ch in samples:
        if len(ch) != frames:
            raise WavError("channel length mismatch")
    scale = {2: 32767, 3: 8388607, 4: 2147483647}[width]
    raw = bytearray()
    for i in range(frames):
        for c in range(channels):
            v = max(-1.0, min(0.999999, samples[c][i]))
            n = int(round(v * scale))
            raw.extend(int(n).to_bytes(width, "little", signed=True))
    block = channels * width
    fmt = struct.pack("<HHIIHH", 1, channels, sample_rate, sample_rate * block, block, width * 8)
    riff_size = 4 + (8 + 16) + (8 + len(raw))
    out = b"RIFF" + riff_size.to_bytes(4, "little") + b"WAVE"
    out += b"fmt " + (16).to_bytes(4, "little") + fmt
    out += b"data" + len(raw).to_bytes(4, "little") + bytes(raw)
    Path(path).write_bytes(out)
