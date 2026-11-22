"""Offline artifact-integrity gate; DOES NOT verify zero-knowledge proofs."""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys

HASH = re.compile(r"[0-9a-f]{64}\Z")
KINDS = frozenset({"proof", "verification_key", "public_inputs"})
MAX_MANIFEST = 64 * 1024
MAX_ARTIFACT = 1024 * 1024


class GateError(ValueError):
    pass


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_bounded(path: Path, limit: int) -> bytes:
    if path.is_symlink():
        raise GateError("symlink not allowed")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise GateError("not a bounded regular file")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            data = stream.read(limit + 1)
        if len(data) > limit:
            raise GateError("file exceeds size limit")
        return data
    finally:
        os.close(fd)


def _artifact_path(base: Path, name: str) -> Path:
    if not isinstance(name, str) or not name or "\\" in name or "\x00" in name:
        raise GateError("invalid artifact path")
    rel = PurePosixPath(name)
    if rel.is_absolute() or any(p in ("", ".", "..") for p in name.split("/")):
        raise GateError("artifact path must be canonical relative path")
    target = base
    for component in rel.parts:
        target = target / component
        if target.is_symlink():
            raise GateError("symlink in artifact path")
    if not target.resolve().is_relative_to(base.resolve()):
        raise GateError("artifact path escapes manifest directory")
    return target


def verify(manifest_path: Path, expected_manifest_sha256: str) -> None:
    if not isinstance(expected_manifest_sha256, str) or not HASH.fullmatch(expected_manifest_sha256):
        raise GateError("trusted expected manifest SHA-256 required")
    manifest_path = Path(manifest_path)
    raw = _read_bounded(manifest_path, MAX_MANIFEST)
    if not hmac.compare_digest(_digest(raw), expected_manifest_sha256):
        raise GateError("manifest digest mismatch")
    try:
        manifest = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise GateError("manifest is not valid JSON") from exc
    if not isinstance(manifest, dict) or set(manifest) != {"schema_version", "artifacts"}:
        raise GateError("invalid manifest keys")
    if type(manifest["schema_version"]) is not int or manifest["schema_version"] != 1:
        raise GateError("unsupported manifest version")
    artifacts = manifest["artifacts"]
    if not isinstance(artifacts, dict) or set(artifacts) != KINDS:
        raise GateError("all three artifact roles are required")
    seen = set()
    for kind in sorted(KINDS):
        entry = artifacts[kind]
        if not isinstance(entry, dict) or set(entry) != {"path", "sha256"}:
            raise GateError(f"invalid {kind} entry")
        path_name, expected = entry["path"], entry["sha256"]
        if not isinstance(expected, str) or not HASH.fullmatch(expected):
            raise GateError(f"invalid {kind} digest")
        target = _artifact_path(manifest_path.parent, path_name)
        if target in seen:
            raise GateError("duplicate artifact path")
        seen.add(target)
        try:
            data = _read_bounded(target, MAX_ARTIFACT)
        except (OSError, GateError) as exc:
            raise GateError(f"cannot read bounded {kind} artifact") from exc
        try:
            json.loads(data)
        except (ValueError, UnicodeDecodeError) as exc:
            raise GateError(f"{kind} artifact is not valid JSON") from exc
        if not hmac.compare_digest(_digest(data), expected):
            raise GateError(f"{kind} digest mismatch")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline ZK artifact integrity only (NOT cryptographic proof verification)")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--expected-manifest-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        verify(args.manifest, args.expected_manifest_sha256)
    except (GateError, OSError) as exc:
        print(f"INTEGRITY GATE FAILED: {exc}", file=sys.stderr)
        return 1
    print("INTEGRITY GATE PASS (offline artifact digests only; proof NOT verified)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
