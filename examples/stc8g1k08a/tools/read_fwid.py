#!/usr/bin/env python3
"""Read an FWID from serial/stdin and optionally verify a local archive."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from fwidlib import parse, sha256_file

try:
    import serial  # type: ignore
except ImportError:
    serial = None


def read_line_from_serial(port: str, baud: int, timeout: float) -> str:
    if serial is None:
        raise RuntimeError(
            "pyserial is not installed; run: pip install -r requirements.txt"
        )
    with serial.Serial(port, baud, timeout=0.2) as stream:
        deadline = time.time() + timeout
        buffer = b""
        while time.time() < deadline:
            chunk = stream.read(256)
            if not chunk:
                continue
            buffer += chunk
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                text = line.decode("ascii", "replace").strip()
                if text.startswith("FWID:"):
                    return text
    raise RuntimeError("no FWID line found; press reset and retry")


def read_line_from_stdin() -> str:
    for line in sys.stdin:
        text = line.strip()
        if text:
            return text
    raise RuntimeError("no input line")


def verify_archive(archive: Path, info: dict[str, str]) -> None:
    record_path = archive / info["body"] / "record.json"
    if not record_path.is_file():
        raise RuntimeError(f"record not found: {record_path}")
    record = json.loads(record_path.read_text(encoding="utf-8"))
    if not isinstance(record, dict):
        raise RuntimeError("record is not a JSON object")
    if record.get("fwid") != info["fwid"]:
        raise RuntimeError(f"record fwid mismatch: {record.get('fwid')}")

    source = record.get("source")
    image = record.get("image")
    if not isinstance(source, dict) or not isinstance(image, dict):
        raise RuntimeError("record is missing source or image")

    bundle_path = record_path.parent / source["bundle"]
    if not bundle_path.is_file():
        raise RuntimeError(f"bundle not found: {bundle_path}")
    actual = sha256_file(bundle_path)
    if actual != source["snapshot_sha256"]:
        raise RuntimeError(
            f"bundle hash mismatch: {actual} != {source['snapshot_sha256']}"
        )

    image_path = record_path.parent / image["file"]
    if not image_path.is_file():
        raise RuntimeError(f"image not found: {image_path}")
    actual = sha256_file(image_path)
    if actual != image["sha256"]:
        raise RuntimeError(f"image hash mismatch: {actual} != {image['sha256']}")

    print(f"archive: {record_path.parent}")
    print(f"project: {record['project']['name']}")
    print(f"target:  {record['target']['mcu']}")
    print(f"bundle:  {bundle_path} (sha256 ok)")
    print(f"image:   {image_path} (sha256 ok)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", help="serial port, e.g. COM5 or /dev/ttyUSB0")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--stdin", action="store_true", help="read one line from stdin")
    parser.add_argument("--archive", type=Path, help="local archive root")
    parser.add_argument("--expect", help="expected FWID")
    args = parser.parse_args()

    try:
        if args.stdin:
            text = read_line_from_stdin()
        elif args.port:
            text = read_line_from_serial(args.port, args.baud, args.timeout)
        else:
            parser.error("use --port or --stdin")
    except (RuntimeError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    try:
        info = parse(text)
    except ValueError as exc:
        print(f"error: {text!r}: {exc}", file=sys.stderr)
        return 1

    print(f"read:    {text}")
    print(f"fwid:    {info['fwid']}")
    print(f"body:    {info['body']}")
    print(f"display: {info['display']}")

    if args.expect:
        try:
            expected = parse(args.expect)
        except ValueError as exc:
            print(f"error: bad --expect value: {exc}", file=sys.stderr)
            return 1
        if expected["fwid"] != info["fwid"]:
            print(f"error: expected {expected['fwid']}", file=sys.stderr)
            return 1

    if args.archive:
        try:
            verify_archive(args.archive, info)
        except (
            OSError,
            ValueError,
            KeyError,
            TypeError,
            RuntimeError,
            json.JSONDecodeError,
        ) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
