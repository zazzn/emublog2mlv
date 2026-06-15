"""Command-line interface for emublog2mlv."""
from __future__ import annotations

import argparse
import json
import os
import sys

from . import __version__
from .core import VALID_FORMATS, convert, summarize


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="emublog2mlv",
        description="Convert ECU Master EMU Black .emublog logs to a MegaLogViewer HD "
                    "log (.msl tab-delimited, or .csv).",
    )
    ap.add_argument("inputs", nargs="+", help=".emublog file(s) to convert")
    ap.add_argument("-o", "--output", help="output path (single input only)")
    ap.add_argument("-f", "--format", choices=VALID_FORMATS, default="msl",
                    help="output format (default: msl)")
    ap.add_argument("--csv", action="store_true", help="shorthand for --format csv")
    ap.add_argument("--summary", action="store_true",
                    help="print a JSON summary (channels, ranges) instead of converting")
    ap.add_argument("--version", action="version", version=f"emublog2mlv {__version__}")
    args = ap.parse_args(argv)

    fmt = "csv" if args.csv else args.format
    if args.output and len(args.inputs) > 1:
        ap.error("-o/--output cannot be used with multiple inputs")
    if args.summary and args.output:
        ap.error("-o/--output is not used with --summary (the summary prints to stdout)")

    rc = 0
    for in_path in args.inputs:
        try:
            if args.summary:
                print(json.dumps(summarize(in_path), indent=2))
            else:
                st = convert(in_path, args.output, fmt)
                print(f"  {os.path.basename(st['input'])} -> {os.path.basename(st['output'])}  "
                      f"({st['records']} samples, {st['duration_s']:.1f}s, "
                      f"{st['channels']} channels)")
        except (OSError, ValueError) as e:
            print(f"  error: {e}", file=sys.stderr)
            rc = 1
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
