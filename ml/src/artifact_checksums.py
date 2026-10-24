"""Verify the frozen PPO/DQN release in artifacts/frozen/public-data-v2.

Each line is ``<sha256>  <path>`` with the path relative to the sums file. Files with a text suffix are hashed
after CRLF -> LF normalization, so one checksum holds for LF checkouts (Linux, Git blobs) and for CRLF checkouts
(Windows with core.autocrlf). Every other file, notably final_model.zip, is hashed as raw bytes.

Usage (repository root): python -m ml.src.artifact_checksums [--sums PATH]
Exit codes: 0 all verified, 1 mismatch or missing file, 2 malformed sums file.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
from pathlib import Path, PurePosixPath
import re
import sys
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SUMS_PATH = REPO_ROOT / "artifacts" / "frozen" / "public-data-v2" / "SHA256SUMS.txt"
TEXT_SUFFIXES = frozenset({".json", ".txt", ".csv", ".md"})
_LINE = re.compile(r"^([0-9A-Fa-f]{64})  (\S.*)$")


class ChecksumFileError(ValueError):
    """The sums file is malformed or names an unsafe path."""


@dataclass(frozen=True)
class ChecksumResult:
    path: str
    status: str  # "ok", "mismatch" or "missing"
    expected: str
    actual: str | None


def checksum_of(path: str | Path, data: bytes) -> str:
    """SHA-256 of ``data`` under the repository policy for ``path``'s suffix."""
    if Path(path).suffix.lower() in TEXT_SUFFIXES:
        data = data.replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def parse_sums(text: str) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    seen: set[str] = set()
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        match = _LINE.match(line)
        if match is None:
            raise ChecksumFileError(f"Line {number} is not '<sha256>  <path>'.")
        relative = match.group(2)
        pure = PurePosixPath(relative)
        if pure.is_absolute() or ".." in pure.parts or "\\" in relative or ":" in relative:
            raise ChecksumFileError(f"Line {number} has an unsafe path.")
        if relative in seen:
            raise ChecksumFileError(f"Line {number} repeats a path.")
        seen.add(relative)
        entries.append((match.group(1).lower(), relative))
    if not entries:
        raise ChecksumFileError("The sums file has no entries.")
    return entries


def verify_checksums(sums_path: str | Path = DEFAULT_SUMS_PATH) -> list[ChecksumResult]:
    sums_path = Path(sums_path)
    base = sums_path.parent
    results = []
    for expected, relative in parse_sums(sums_path.read_text(encoding="utf-8-sig")):
        target = base / relative
        if not target.is_file():
            results.append(ChecksumResult(relative, "missing", expected, None))
            continue
        actual = checksum_of(relative, target.read_bytes())
        results.append(ChecksumResult(relative, "ok" if actual == expected else "mismatch", expected, actual))
    return results


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify artifact checksums under the repository policy.")
    parser.add_argument("--sums", default=str(DEFAULT_SUMS_PATH))
    args = parser.parse_args(argv)
    try:
        results = verify_checksums(args.sums)
    except (ChecksumFileError, OSError) as error:
        print(f"Cannot read checksums: {error}", file=sys.stderr)
        return 2
    failures = [result for result in results if result.status != "ok"]
    for result in failures:
        print(f"{result.status.upper()}: {result.path} expected {result.expected} actual {result.actual}")
    print(f"{len(results) - len(failures)} of {len(results)} files verified.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
