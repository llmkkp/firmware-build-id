"""Shared FWID helpers for the STC8G1K08A example.

Only the Python standard library is used.
"""

from __future__ import annotations

import hashlib
import re
import secrets
from pathlib import Path

ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

# Canonical FWID: 14-18 Crockford Base32 characters (data + 2 check chars).
FWID_RE = re.compile(rb"FWID:([0-9A-HJKMNP-TV-Z]{14,18})")


def normalize(text: str) -> str:
    """Normalize user input to the archive key (uppercase body, no prefix)."""
    value = text.strip().upper().replace("-", "").replace(" ", "")
    if value.startswith("FWID:"):
        value = value[5:]
    value = value.replace("I", "1").replace("L", "1").replace("O", "0")
    if "U" in value:
        raise ValueError("U is not allowed in Crockford Base32")
    return value


def crc8_atm(data: bytes) -> int:
    """CRC-8/ATM: poly 0x07, init 0x00, refin/refout false, xorout 0x00."""
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) ^ 0x07) & 0xFF
            else:
                crc = (crc << 1) & 0xFF
    return crc


def check_chars(data: str) -> str:
    """Return the two check characters for the data part."""
    crc = crc8_atm(data.encode("ascii"))
    return ALPHABET[(crc >> 3) & 0x1F] + ALPHABET[crc & 0x07]


def parse(text: str) -> dict[str, str]:
    """Validate an FWID and return its canonical forms."""
    body = normalize(text)
    if not 14 <= len(body) <= 18:
        raise ValueError(f"body length must be 14-18, got {len(body)}")
    for char in body:
        if char not in ALPHABET:
            raise ValueError(f"invalid character {char!r}")
    data, check = body[:-2], body[-2:]
    expected = check_chars(data)
    if check != expected:
        raise ValueError(f"bad check characters: got {check}, expected {expected}")
    return {
        "fwid": "FWID:" + body,
        "body": body,
        "data": data,
        "check": check,
        "display": "FWID:" + "-".join(
            body[index : index + 4] for index in range(0, len(body), 4)
        ),
    }


def generate_body(data_chars: int = 12) -> str:
    """Generate a random body with 12-16 data characters plus check chars."""
    if not 12 <= data_chars <= 16:
        raise ValueError("data_chars must be 12-16")
    data = "".join(secrets.choice(ALPHABET) for _ in range(data_chars))
    return data + check_chars(data)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_image(path: Path) -> tuple[bytes, int, str]:
    """Return (payload, base_address, kind) for a BIN or Intel HEX image.

    Intel HEX files are decoded into a byte span; gaps are filled with 0xFF.
    """
    raw = path.read_bytes()
    if path.suffix.lower() == ".hex":
        return _read_ihex(raw.decode("ascii"))
    return raw, 0, "bin"


def _read_ihex(text: str) -> tuple[bytes, int, str]:
    data: dict[int, int] = {}
    base = 0
    saw_eof = False
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if not line.startswith(":"):
            raise ValueError(f"not an Intel HEX record: {line!r}")
        try:
            record = bytes.fromhex(line[1:])
        except ValueError as exc:
            raise ValueError(f"bad hex record: {line!r}") from exc
        if len(record) < 5:
            raise ValueError(f"short hex record: {line!r}")
        count = record[0]
        if len(record) != count + 5:
            raise ValueError(f"bad record length: {line!r}")
        address = (record[1] << 8) | record[2]
        record_type = record[3]
        payload = record[4 : 4 + count]
        checksum = record[4 + count]
        if (sum(record[:-1]) + checksum) & 0xFF:
            raise ValueError(f"bad record checksum: {line!r}")

        if record_type == 0x00:
            for offset, byte in enumerate(payload):
                data[base + address + offset] = byte
        elif record_type == 0x01:
            saw_eof = True
            break
        elif record_type == 0x02:
            if len(payload) != 2:
                raise ValueError("bad extended segment address record")
            base = int.from_bytes(payload, "big") << 4
        elif record_type == 0x04:
            if len(payload) != 2:
                raise ValueError("bad extended linear address record")
            base = int.from_bytes(payload, "big") << 16
        elif record_type in (0x03, 0x05):
            # Start address records do not affect the payload.
            continue
        else:
            raise ValueError(f"unsupported record type 0x{record_type:02X}")

    if not data:
        raise ValueError("no data records in Intel HEX file")
    if not saw_eof:
        raise ValueError("missing EOF record in Intel HEX file")

    low, high = min(data), max(data)
    payload = bytearray([0xFF]) * (high - low + 1)
    for address, byte in data.items():
        payload[address - low] = byte
    return bytes(payload), low, "hex"


def find_fwids(payload: bytes) -> list[tuple[int, dict[str, str]]]:
    """Find all valid FWID strings in a binary payload."""
    found: list[tuple[int, dict[str, str]]] = []
    for match in FWID_RE.finditer(payload):
        raw = match.group(1)
        # The regex is greedy; try lengths from longest to shortest so a
        # trailing alphabet character does not hide a shorter valid FWID.
        for length in range(len(raw), 13, -1):
            candidate = raw[:length].decode("ascii")
            try:
                info = parse("FWID:" + candidate)
            except ValueError:
                continue
            found.append((match.start(), info))
            break
    return found


def write_header(path: Path, fwid: str) -> None:
    """Write src/fwid_generated.h for the STC8G1K08A example."""
    info = parse(fwid)
    content = f"""\
#ifndef FWID_GENERATED_H
#define FWID_GENERATED_H

/*
 * Generated by tools/fwid.py. Regenerate for every build.
 * The body is 12 data characters + 2 CRC check characters.
 */
#define FWID_BODY   "{info['body']}"
#define FWID_STRING "FWID:" FWID_BODY

#endif
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="ascii", newline="\n")
