"""Lock independent audio to a video clock. Not implemented in the initial snapshot."""

from __future__ import annotations


class NotImplementedSync(NotImplementedError):
    pass


def sync(audio_path: str, clock_path: str, policy_path: str, out_wav: str, report_path: str) -> int:
    raise NotImplementedSync(
        "avasrc.sync.sync is not implemented yet; wav / video-clock probe already work"
    )
