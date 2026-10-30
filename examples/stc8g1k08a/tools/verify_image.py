#!/usr/bin/env python3
"""Decode an Intel HEX/BIN image, find the FWID, and print hashes."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from fwidlib import find_fwids, parse, read_image, sha256_bytes, sha256_file


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--expect", help="expected FWID; fail if not found")
    parser.add_argument(
        "--bin-out",
        type=Path,
        help="write the decoded payload to this .bin file",
    )
    args = parser.parse_args()

    try:
        payload, base, kind = read_image(args.image)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    found = find_fwids(payload)
    if not found:
        print("error: no valid FWID string found in the image", file=sys.stderr)
        return 1

    expected = None
    if args.expect:
        try:
            expected = parse(args.expect)
        except ValueError as exc:
            print(f"error: bad --expect value: {exc}", file=sys.stderr)
            return 1

    if expected and not any(info["fwid"] == expected["fwid"] for _, info in found):
        print(f"error: expected {expected['fwid']} not found", file=sys.stderr)
        return 1

    print(f"image: {args.image} ({kind}), base=0x{base:04X}, size={len(payload)}")
    print(f"payload_sha256: {sha256_bytes(payload)}")
    print(f"file_sha256:    {sha256_file(args.image)}")
    for offset, info in found:
        print(f"found: {info['fwid']} at payload offset 0x{offset:X}")

    if args.bin_out:
        args.bin_out.parent.mkdir(parents=True, exist_ok=True)
        args.bin_out.write_bytes(payload)
        print(f"wrote {args.bin_out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
