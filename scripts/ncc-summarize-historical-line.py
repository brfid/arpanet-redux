#!/usr/bin/env python3
"""Render one supported completed historical-line result as summary JSON."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from ncc.historical_summary import (
    HistoricalLineSummaryError,
    summarize_historical_line_result,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "results_dir",
        type=Path,
        help="read-only completed fault or loopback result directory",
    )
    parser.add_argument(
        "--topology",
        required=True,
        type=Path,
        help="project-authored shared topology used by the run",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        summary = summarize_historical_line_result(args.results_dir, args.topology)
    except HistoricalLineSummaryError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    sys.stdout.write(summary.to_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
