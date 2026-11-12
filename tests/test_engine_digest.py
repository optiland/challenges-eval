"""The engine digest must not depend on the operating system or Git settings."""

import json
from pathlib import Path

from challenge_evaluator import engine_provenance, tree_digest


def _write_tree(root: Path, newline: bytes) -> None:
    files = {
        "a.py": b"x = 1" + newline + b"y = 2" + newline,
        "B.yml": b"name: B" + newline,
        "sub/c.yml": b"k: v" + newline,
        "sub/C_upper.csv": b"1,2" + newline,
        "data.npy": b"\x93NUMPY\r\n\x00binary",  # binary: never normalized
        "notes.txt": b"ignored suffix",
    }
    for name, data in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def test_crlf_checkout_gives_the_lf_digest(tmp_path):
    lf, crlf = tmp_path / "lf", tmp_path / "crlf"
    _write_tree(lf, b"\n")
    _write_tree(crlf, b"\r\n")
    assert tree_digest(lf) == tree_digest(crlf)
    assert tree_digest(lf)[1] == 5


def test_binary_files_are_hashed_unchanged(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    _write_tree(a, b"\n")
    _write_tree(b, b"\n")
    (b / "data.npy").write_bytes(b"\x93NUMPY\n\x00binary")
    assert tree_digest(a) != tree_digest(b)


def test_order_is_case_sensitive_posix_order(tmp_path):
    # PurePosixPath order puts "B.yml" before "a.py"; Windows Path order does not.
    _write_tree(tmp_path, b"\n")
    digest, _ = tree_digest(tmp_path)
    assert digest == tree_digest(tmp_path)[0]
    import hashlib

    expected = hashlib.sha256()
    names = sorted(["a.py", "B.yml", "sub/c.yml", "sub/C_upper.csv", "data.npy"])
    assert names[0] == "B.yml"  # uppercase sorts first in POSIX byte order
    for name in names:
        data = (tmp_path / name).read_bytes()
        expected.update(name.encode() + b"\0")
        expected.update(hashlib.sha256(data).digest())
    assert digest == expected.hexdigest()


def test_installed_engine_matches_the_published_lock():
    lock = json.loads((Path(__file__).parents[1] / "engine_lock.json").read_text())
    provenance = engine_provenance()
    assert provenance["source_catalog_sha256"] == lock["source_catalog_sha256"]
    assert provenance["hashed_files"] == lock["hashed_files"]
