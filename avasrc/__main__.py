from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import probe, sync


def cmd_probe(args: argparse.Namespace) -> int:
    info = probe.probe_paths(args.audio, args.clock)
    text = probe.format_probe(info)
    if args.out:
        Path(args.out).write_text(text + "\n")
    else:
        sys.stdout.write(text + "\n")
    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    try:
        return sync.sync(args.audio, args.clock, args.policy, args.output, args.report)
    except sync.NotImplementedSync as e:
        sys.stderr.write(str(e) + "\n")
        return 2


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="avasrc")
    sub = p.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("probe", help="inventory audio and a video clock list")
    sp.add_argument("--audio", required=True)
    sp.add_argument("--clock", required=True)
    sp.add_argument("--out", default=None)
    sp.set_defaults(func=cmd_probe)
    ss = sub.add_parser("sync", help="resample audio onto the video clock")
    ss.add_argument("--audio", required=True)
    ss.add_argument("--clock", required=True)
    ss.add_argument("--policy", required=True)
    ss.add_argument("--output", required=True)
    ss.add_argument("--report", required=True)
    ss.set_defaults(func=cmd_sync)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
