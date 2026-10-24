import hashlib
import json
from pathlib import Path
import shutil

import pytest

from ml.src.artifact_checksums import (
    DEFAULT_SUMS_PATH,
    REPO_ROOT,
    TEXT_SUFFIXES,
    ChecksumFileError,
    checksum_of,
    main,
    parse_sums,
    verify_checksums,
)

ARTIFACTS = DEFAULT_SUMS_PATH.parent


def write_sums(directory, files, *, newline="\n"):
    lines = [f"{hashlib.sha256(data).hexdigest().upper()}  {name}" for name, data in files.items()]
    (directory / "SHA256SUMS.txt").write_bytes(newline.join(lines).encode() + newline.encode())


def test_text_files_hash_identically_with_lf_or_crlf_and_binary_files_are_raw():
    assert checksum_of("a.json", b'{"a": 1}\n') == checksum_of("a.json", b'{"a": 1}\r\n')
    assert checksum_of("a.zip", b"PK\r\n") != checksum_of("a.zip", b"PK\n")
    assert checksum_of("a.zip", b"PK\r\n") == hashlib.sha256(b"PK\r\n").hexdigest()


def test_lone_carriage_returns_are_not_normalized():
    assert checksum_of("a.json", b"a\rb") == hashlib.sha256(b"a\rb").hexdigest()


def test_verification_detects_tampering_and_missing_files(tmp_path):
    files = {"doc.json": b'{"a": 1}\n', "model.zip": b"PK\x03\x04\r\nbinary"}
    for name, data in files.items():
        (tmp_path / name).write_bytes(data)
    write_sums(tmp_path, {**files, "gone.json": b"{}\n"})

    statuses = {result.path: result.status for result in verify_checksums(tmp_path / "SHA256SUMS.txt")}
    assert statuses == {"doc.json": "ok", "model.zip": "ok", "gone.json": "missing"}

    (tmp_path / "doc.json").write_bytes(b'{"a": 2}\n')
    (tmp_path / "model.zip").write_bytes(b"PK\x03\x04\nbinary")  # a binary's line endings are content
    statuses = {result.path: result.status for result in verify_checksums(tmp_path / "SHA256SUMS.txt")}
    assert statuses["doc.json"] == "mismatch" and statuses["model.zip"] == "mismatch"


def test_crlf_text_file_and_crlf_sums_file_still_verify(tmp_path):
    (tmp_path / "doc.json").write_bytes(b'{"a": 1}\r\n')
    write_sums(tmp_path, {"doc.json": b'{"a": 1}\n'}, newline="\r\n")

    assert [result.status for result in verify_checksums(tmp_path / "SHA256SUMS.txt")] == ["ok"]


@pytest.mark.parametrize(
    "line",
    [
        "not a checksum line",
        "abc  file.json",
        f"{'0' * 64} file.json",
        f"{'0' * 64}  ../outside.json",
        f"{'0' * 64}  /etc/passwd",
        f"{'0' * 64}  C:\\x.json",
        f"{'0' * 64}  a\\b.json",
    ],
)
def test_malformed_or_unsafe_lines_are_rejected(line):
    with pytest.raises(ChecksumFileError):
        parse_sums(line + "\n")


def test_empty_and_duplicate_entries_are_rejected():
    with pytest.raises(ChecksumFileError):
        parse_sums("\n\n")
    with pytest.raises(ChecksumFileError):
        parse_sums(f"{'0' * 64}  a.json\n{'1' * 64}  a.json\n")


def test_command_line_exit_codes(tmp_path, capsys):
    (tmp_path / "doc.json").write_bytes(b"{}\n")
    write_sums(tmp_path, {"doc.json": b"{}\n"})
    sums = str(tmp_path / "SHA256SUMS.txt")
    assert main(["--sums", sums]) == 0

    (tmp_path / "doc.json").write_bytes(b"[]\n")
    assert main(["--sums", sums]) == 1
    assert "MISMATCH: doc.json" in capsys.readouterr().out

    (tmp_path / "SHA256SUMS.txt").write_text("garbage\n")
    assert main(["--sums", sums]) == 2


def test_committed_artifacts_verify_on_this_checkout():
    results = verify_checksums()

    assert {result.path for result in results} == {
        path.relative_to(ARTIFACTS).as_posix()
        for path in ARTIFACTS.rglob("*")
        if path.is_file() and path != DEFAULT_SUMS_PATH
    }
    assert {"ppo/final_model.zip", "dqn/final_model.zip"} <= {result.path for result in results}
    assert [result.path for result in results if result.status != "ok"] == []


def test_frozen_checkpoint_checksum_matches_the_frozen_manifest():
    manifest = json.loads((REPO_ROOT / "ml" / "frozen_ppo_manifest.json").read_text(encoding="utf-8"))
    sums = REPO_ROOT / "artifacts/frozen/public-data-v2/SHA256SUMS.txt"
    relative = (REPO_ROOT / manifest["checkpoint"]["path"]).relative_to(sums.parent).as_posix()
    recorded = {path: digest for digest, path in parse_sums(sums.read_text(encoding="utf-8-sig"))}

    assert recorded[relative] == manifest["checkpoint"]["sha256"].lower()
    assert checksum_of(relative, (sums.parent / relative).read_bytes()) == manifest["checkpoint"]["sha256"].lower()


@pytest.mark.parametrize("newline", [b"\n", b"\r\n"])
def test_policy_holds_for_lf_and_crlf_checkouts_of_every_text_file(tmp_path, newline):
    for source in ARTIFACTS.rglob("*"):
        if not source.is_file():
            continue
        target = tmp_path / source.relative_to(ARTIFACTS)
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.suffix.lower() in TEXT_SUFFIXES:
            lf = source.read_bytes().replace(b"\r\n", b"\n")
            target.write_bytes(lf if newline == b"\n" else lf.replace(b"\n", b"\r\n"))
        else:
            shutil.copyfile(source, target)

    assert [r.path for r in verify_checksums(tmp_path / "SHA256SUMS.txt") if r.status != "ok"] == []
