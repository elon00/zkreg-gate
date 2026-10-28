"""Real filesystem/subprocess regression cases, not ZK cryptographic tests."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from zkreg_gate import GateError, verify


def sha(data):
    return hashlib.sha256(data).hexdigest()


class IntegrityGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.artifacts = {}
        for kind in ("proof", "verification_key", "public_inputs"):
            raw = json.dumps({"artifact": kind}, sort_keys=True).encode()
            (self.base / f"{kind}.json").write_bytes(raw)
            self.artifacts[kind] = {"path": f"{kind}.json", "sha256": sha(raw)}
        self.manifest = self.base / "manifest.json"
        self.write_manifest()

    def write_manifest(self, artifacts=None, **extra):
        payload = {"schema_version": 1, "artifacts": artifacts if artifacts is not None else self.artifacts, **extra}
        raw = json.dumps(payload, sort_keys=True).encode()
        self.manifest.write_bytes(raw)
        self.pin = sha(raw)

    def test_valid_manifest(self):
        verify(self.manifest, self.pin)

    def test_invalid_trusted_pin(self):
        with self.assertRaises(GateError):
            verify(self.manifest, "0" * 64)

    def test_missing_pin(self):
        with self.assertRaises(GateError):
            verify(self.manifest, "")

    def test_tampered_artifact(self):
        (self.base / "proof.json").write_text('{"tampered":true}')
        with self.assertRaisesRegex(GateError, "digest mismatch"):
            verify(self.manifest, self.pin)

    def test_missing_artifact(self):
        (self.base / "proof.json").unlink()
        with self.assertRaises(GateError):
            verify(self.manifest, self.pin)

    def test_traversal(self):
        self.artifacts["proof"]["path"] = "../outside.json"
        self.write_manifest()
        with self.assertRaises(GateError):
            verify(self.manifest, self.pin)

    def test_absolute_path(self):
        self.artifacts["proof"]["path"] = str(self.base / "proof.json")
        self.write_manifest()
        with self.assertRaises(GateError):
            verify(self.manifest, self.pin)

    def test_symlink(self):
        target = self.base / "proof.json"
        target.rename(self.base / "real-proof.json")
        try:
            target.symlink_to(self.base / "real-proof.json")
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable")
        with self.assertRaises(GateError):
            verify(self.manifest, self.pin)

    def test_oversized_file(self):
        (self.base / "proof.json").write_bytes(b"x" * (1024 * 1024 + 1))
        with self.assertRaises(GateError):
            verify(self.manifest, self.pin)

    def test_malformed_manifest_json(self):
        self.manifest.write_bytes(b"{")
        with self.assertRaises(GateError):
            verify(self.manifest, sha(b"{"))

    def test_missing_role(self):
        self.artifacts.pop("proof")
        self.write_manifest()
        with self.assertRaises(GateError):
            verify(self.manifest, self.pin)

    def test_duplicate_paths(self):
        self.artifacts["proof"]["path"] = "verification_key.json"
        self.write_manifest()
        with self.assertRaises(GateError):
            verify(self.manifest, self.pin)

    def test_invalid_digest(self):
        self.artifacts["proof"]["sha256"] = "A" * 64
        self.write_manifest()
        with self.assertRaises(GateError):
            verify(self.manifest, self.pin)

    def test_unrecognized_manifest_field(self):
        self.write_manifest(unverified="100/100")
        with self.assertRaises(GateError):
            verify(self.manifest, self.pin)

    def test_invalid_artifact_json(self):
        raw = b"not-json"
        (self.base / "proof.json").write_bytes(raw)
        self.artifacts["proof"]["sha256"] = sha(raw)
        self.write_manifest()
        with self.assertRaises(GateError):
            verify(self.manifest, self.pin)

    def test_cli_success_and_fail_closed(self):
        script = Path(__file__).resolve().parents[1] / "zkreg_gate.py"
        cmd = [sys.executable, str(script), "--manifest", str(self.manifest), "--expected-manifest-sha256", self.pin]
        good = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(good.returncode, 0, good.stderr)
        self.assertIn("proof NOT verified", good.stdout)
        bad = subprocess.run(cmd[:-1] + ["0" * 64], capture_output=True, text=True)
        self.assertNotEqual(bad.returncode, 0)
        self.assertIn("FAILED", bad.stderr)


if __name__ == "__main__":
    unittest.main()
