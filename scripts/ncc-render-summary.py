#!/usr/bin/env python3
"""Print a self-contained local NCC viewer for one run-summary JSON file."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from ncc.run_summary import RunSummaryValidationError, load_run_summary
from ncc.viewer import render_summary_html


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("summary", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        summary = load_run_summary(args.summary)
    except RunSummaryValidationError as error:
        print(f"cannot render NCC summary: {error}", file=sys.stderr)
        return 1
    sys.stdout.write(render_summary_html(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
