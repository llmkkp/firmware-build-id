#!/usr/bin/env python3
"""Generate, validate, and write FWID headers."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from fwidlib import generate_body, parse, write_header


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    new_parser = sub.add_parser("new", help="generate a random FWID")
    new_parser.add_argument(
        "--data-chars",
        type=int,
        default=12,
        help="data characters, 12-16 (default: 12)",
    )
    new_parser.add_argument(
        "--header",
        type=Path,
        help="write src/fwid_generated.h to this path",
    )

    check_parser = sub.add_parser("check", help="validate an FWID")
    check_parser.add_argument("fwid")

    header_parser = sub.add_parser("header", help="write a header for an existing FWID")
    header_parser.add_argument("fwid")
    header_parser.add_argument("--out", type=Path, required=True)

    args = parser.parse_args()

    if args.command == "new":
        try:
            body = generate_body(args.data_chars)
        except ValueError as exc:
            parser.error(str(exc))
        info = parse("FWID:" + body)
        print(info["fwid"])
        print(info["display"])
        if args.header:
            write_header(args.header, info["fwid"])
            print(f"wrote {args.header}")
        return 0

    if args.command == "check":
        try:
            info = parse(args.fwid)
        except ValueError as exc:
            print(f"invalid: {exc}", file=sys.stderr)
            return 1
        print(info["fwid"])
        print(info["display"])
        return 0

    if args.command == "header":
        try:
            write_header(args.out, args.fwid)
        except ValueError as exc:
            print(f"invalid: {exc}", file=sys.stderr)
            return 1
        print(f"wrote {args.out}")
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
