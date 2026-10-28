# ZKReg Gate — QMOOSA-0970 (TESTS)

**Status: partial offline artifact-integrity implementation. Not a zero-knowledge verifier.**

This component checks that three JSON artifacts (`proof`, `verification_key`, `public_inputs`) match a separately trusted SHA-256 manifest digest. It rejects tampering, missing artifacts, noncanonical/escaping paths, symlinks, oversized inputs, invalid JSON and malformed metadata. It does **not** check Groth16/PLONK proof validity, public-input binding, trusted setup, authorization, ledger state or regulatory compliance.

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
python zkreg_gate.py --manifest /path/to/manifest.json --expected-manifest-sha256 <64-lowercase-hex-from-trusted-channel>
```

Manifest schema (digest pinned **out-of-band**, not computed from an untrusted manifest at verification time):

```json
{
  "schema_version": 1,
  "artifacts": {
    "proof": {"path": "proof.json", "sha256": "<64-lowercase-hex>"},
    "verification_key": {"path": "verification_key.json", "sha256": "<64-lowercase-hex>"},
    "public_inputs": {"path": "public_inputs.json", "sha256": "<64-lowercase-hex>"}
  }
}
```

All three artifacts must be JSON regular files <=1 MiB; manifest <=64 KiB. The gate uses no network, keys, gas, cycles or deployments. It is intended for a stable local filesystem; concurrent hostile filesystem mutation/TOCTOU is not covered. Hash integrity is **not** authenticity without a trusted digest source.

## Mandatory remaining release blockers

- Implement and independently validate genuine cryptographic proof verification against a pinned, authenticated verification key and correctly bound public inputs; add positive and adversarial proof fixtures.
- Define actual compliance policy, authorization and privacy requirements; complete security review and audit.
- Verify current default-HEAD CI after PR review/merge; PR-head checks alone are not default-HEAD acceptance.
- Obtain external production/security approval and any required NIST validation; no FIPS or `100/100` claim is made.

`cargo run` deliberately exits nonzero until a real ZK verifier is integrated; it does not claim network or cryptographic success.
