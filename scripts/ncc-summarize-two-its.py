#!/usr/bin/env python3
"""Print a read-only NCC summary for one completed formal two-ITS result."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from ncc.two_its_summary import TwoItsSummaryError, summarize_two_its_result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("results_dir", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        summary = summarize_two_its_result(args.results_dir)
    except TwoItsSummaryError as error:
        print(f"cannot summarize two-ITS result: {error}", file=sys.stderr)
        return 1
    sys.stdout.write(summary.to_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
