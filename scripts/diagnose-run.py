#!/usr/bin/env python3
"""Explain retained run outcomes, checkpoints, cleanup, and diagnostic logs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from ncc.run_diagnostics import RunDiagnosticError, diagnose_run, render_diagnostic


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result", type=Path, help="one smoke or terminal result directory")
    parser.add_argument("--json", action="store_true", help="print the structured diagnostic")
    args = parser.parse_args()
    try:
        report = diagnose_run(args.result)
    except RunDiagnosticError as error:
        print(f"cannot inspect run: {ascii(str(error))}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))
    else:
        sys.stdout.write(render_diagnostic(report))
    return int(report["status"] in ("unavailable", "inconsistent"))


if __name__ == "__main__":
    raise SystemExit(main())
