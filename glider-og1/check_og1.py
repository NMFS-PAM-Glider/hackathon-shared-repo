"""
File: glider-og1/check_og1.py

What it does: Runs the OG1.0 compliance and sanity checks on one or more
    NetCDF files, whether they were made by convert.py or by another tool.

How to run (from the repository root):
    python glider-og1/check_og1.py data/og1/*.nc

Inputs: paths to OG1 NetCDF files
Outputs: a report per file printed to the terminal; exit code 1 if any file has errors
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from glider_og1.validate import check, summarize  # noqa: E402


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    any_errors = False
    for path in sys.argv[1:]:
        results = check(path)
        print(path)
        print(summarize(results))
        any_errors |= any(level == "ERROR" for level, _ in results)
    sys.exit(1 if any_errors else 0)


if __name__ == "__main__":
    main()
