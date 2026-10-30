#!/usr/bin/env python3
"""Create a local FWID archive entry for the STC8G1K08A example."""

from __future__ import annotations

import argparse
import gzip
import json
import shutil
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path

from fwidlib import (
    find_fwids,
    parse,
    read_image,
    sha256_bytes,
    sha256_file,
)

DEFAULT_SOURCE = Path(__file__).resolve().parents[1]
DEFAULT_OUT = DEFAULT_SOURCE / "archive"


def make_tar_gz(
    source_dir: Path,
    out_path: Path,
    excludes: set[str],
    skip_dir: Path | None = None,
) -> None:
    """Create a deterministic tar.gz (sorted paths, zeroed metadata)."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_out = out_path.resolve()
    resolved_skip = skip_dir.resolve() if skip_dir is not None else None
    paths = sorted(
        source_dir.rglob("*"),
        key=lambda item: item.relative_to(source_dir).as_posix(),
    )
    with out_path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
            with tarfile.open(fileobj=gz, mode="w") as tar:
                for path in paths:
                    rel = path.relative_to(source_dir)
                    if any(part in excludes for part in rel.parts):
                        continue
                    # Keil UI/scratch files are local state, not build inputs.
                    if (
                        path.name.endswith(".uvopt")
                        or ".uvgui" in path.name
                        or path.name.endswith(".uvproj.bak")
                    ):
                        continue
                    if path.resolve() == resolved_out:
                        continue
                    if (
                        resolved_skip is not None
                        and path.resolve().is_relative_to(resolved_skip)
                    ):
                        continue
                    info = tar.gettarinfo(str(path), arcname=rel.as_posix())
                    info.uid = 0
                    info.gid = 0
                    info.uname = ""
                    info.gname = ""
                    info.mtime = 0
                    if path.is_dir():
                        info.mode = 0o755
                        tar.addfile(info)
                    elif path.is_file():
                        info.mode = 0o644
                        with path.open("rb") as stream:
                            tar.addfile(info, stream)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--fwid", required=True)
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--project-name", default="stc8g1k08a-fwid-example")
    parser.add_argument("--mcu", default="STC8G1K08A")
    parser.add_argument("--build-command", default="Keil C51 build; see README.md")
    parser.add_argument("--toolchain", default="Keil C51")
    parser.add_argument("--toolchain-version", default="unknown")
    args = parser.parse_args()

    try:
        info = parse(args.fwid)
        payload, _base, kind = read_image(args.image)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    found = find_fwids(payload)
    if not any(item["fwid"] == info["fwid"] for _, item in found):
        print(f"error: {info['fwid']} not found in {args.image}", file=sys.stderr)
        return 1

    source_dir = args.source_dir.resolve()
    out_dir = args.out.resolve() / info["body"]
    out_dir.mkdir(parents=True, exist_ok=True)

    excludes = {
        ".git",
        "build",
        "archive",
        "__pycache__",
        ".venv",
        "venv",
        "Objects",
        "Listings",
        "STARTUP.A51",
    }

    bundle = out_dir / "source.tar.gz"
    tmp_bundle = out_dir / ".source.tar.gz.tmp"
    make_tar_gz(source_dir, tmp_bundle, excludes, skip_dir=out_dir)
    snapshot_sha = sha256_file(tmp_bundle)
    image_sha = sha256_bytes(payload)

    record_path = out_dir / "record.json"
    now = datetime.now(timezone.utc).replace(microsecond=0)
    created_at = now.isoformat().replace("+00:00", "Z")
    if record_path.exists():
        try:
            old = json.loads(record_path.read_text(encoding="utf-8"))
            if not isinstance(old, dict):
                raise ValueError("existing record is not a JSON object")
            old_source = old.get("source")
            old_image_entry = old.get("image")
            old_snapshot = (
                old_source.get("snapshot_sha256")
                if isinstance(old_source, dict)
                else None
            )
            old_image = (
                old_image_entry.get("sha256")
                if isinstance(old_image_entry, dict)
                else None
            )
        except (OSError, ValueError) as exc:
            tmp_bundle.unlink(missing_ok=True)
            print(f"error: cannot read existing record: {exc}", file=sys.stderr)
            return 2
        if (
            old.get("fwid") != info["fwid"]
            or old_snapshot != snapshot_sha
            or old_image != image_sha
        ):
            tmp_bundle.unlink(missing_ok=True)
            print(
                "error: archive entry already exists with different content; "
                "generate a new FWID for a new build",
                file=sys.stderr,
            )
            return 2
        existing_created = old.get("created_at")
        if isinstance(existing_created, str) and existing_created:
            created_at = existing_created

    tmp_bundle.replace(bundle)

    artifacts_dir = out_dir / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    bin_path = artifacts_dir / "main.bin"
    bin_path.write_bytes(payload)

    artifacts = []
    image_path = args.image.resolve()
    if kind == "hex":
        hex_path = artifacts_dir / "main.hex"
        if image_path != hex_path.resolve():
            shutil.copyfile(image_path, hex_path)
        artifacts.append(
            {
                "file": "artifacts/main.hex",
                "sha256": sha256_file(hex_path),
                "kind": "hex",
            }
        )

    record = {
        "spec_version": "0.1.0",
        "fwid": info["fwid"],
        "created_at": created_at,
        "project": {
            "name": args.project_name,
            "version": "0.1.0",
            "repository": "https://github.com/llmkkp/firmware-build-id",
        },
        "target": {
            "mcu": args.mcu,
            "board": "STC8G1K08A-8PIN",
            "config": "release",
        },
        "source": {
            "mode": "complete",
            "included_untracked": True,
            "snapshot_sha256": snapshot_sha,
            "bundle": "source.tar.gz",
        },
        "build": {
            "command": args.build_command,
            "toolchain": {
                "name": args.toolchain,
                "version": args.toolchain_version,
            },
            "environment": {
                "FOSC": "24000000",
                "BAUD": "115200",
            },
            "reproducible": False,
            "notes": (
                "Keil project settings: STC8G1K08A, Small memory model, "
                "24 MHz IRC, Create HEX File. Toolchain is not bundled."
            ),
        },
        "image": {
            "file": "artifacts/main.bin",
            "sha256": image_sha,
            "format": "bin",
            "size": len(payload),
        },
        "artifacts": artifacts,
        "access": {
            "visibility": "private",
            "contact": "https://github.com/llmkkp/firmware-build-id/issues",
        },
        "retention": {
            "until": "2036-10-31",
            "policy": "support-lifetime",
        },
        "notes": (
            "Generated by examples/stc8g1k08a/tools/make_archive.py. "
            "The demo FWID must be regenerated for every real build."
        ),
    }

    record_path.write_text(
        json.dumps(record, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    # read-after-write verification
    readback = json.loads(record_path.read_text(encoding="utf-8"))
    checks = [
        readback.get("fwid") == info["fwid"],
        sha256_file(out_dir / readback["source"]["bundle"])
        == readback["source"]["snapshot_sha256"],
        sha256_file(out_dir / readback["image"]["file"])
        == readback["image"]["sha256"],
    ]
    if not all(checks):
        print("error: read-after-write verification failed", file=sys.stderr)
        return 2

    print(f"FWID: {info['fwid']}")
    print(f"record: {record_path}")
    print(f"bundle: {bundle} ({bundle.stat().st_size} bytes)")
    print(f"image:  {bin_path} ({len(payload)} bytes)")
    print(f"snapshot_sha256: {record['source']['snapshot_sha256']}")
    print(f"image_sha256:    {record['image']['sha256']}")
    print("read-after-write: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
