"""Checksummed run receipts. Integrity is distinct from scientific validity."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def seal_run(directory, inputs, parameters, evidence_kind):
    root = Path(directory)
    if (root / "manifest.json").exists():
        raise ValueError("Run is already sealed")
    inputs = [Path(p) for p in inputs]
    if len({p.name for p in inputs}) != len(inputs):
        raise ValueError("Input basenames must be unique in a receipt")
    files = {p.relative_to(root).as_posix(): sha256(p) for p in sorted(root.rglob("*"))
             if p.is_file() and p.relative_to(root).as_posix() != "manifest.json"}
    receipt = {"schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
               "evidence_kind": evidence_kind, "parameters": parameters,
               "inputs": [{"name": p.name, "sha256": sha256(p)} for p in inputs],
               "files": files, "historical_availability_certified": False,
               "causal_identification": "not_established"}
    write_json(root / "manifest.json", receipt)
    return receipt


def verify_run(directory, input_root=None):
    root = Path(directory)
    receipt = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if receipt.get("schema_version") != 1 or not isinstance(receipt.get("files"), dict):
        raise ValueError("Unsupported run manifest")
    for relative in receipt["files"]:
        target = (root / relative).resolve()
        if not target.is_relative_to(root.resolve()) or target == root.resolve():
            raise ValueError("Manifest contains a path outside the run")
    actual = {p.relative_to(root).as_posix(): sha256(p) for p in root.rglob("*")
              if p.is_file() and p.relative_to(root).as_posix() != "manifest.json"}
    if actual != receipt["files"]:
        raise ValueError("Run inventory or output checksum changed")
    if input_root:
        for entry in receipt["inputs"]:
            if Path(entry["name"]).name != entry["name"]:
                raise ValueError("Invalid input basename")
            if sha256(Path(input_root) / entry["name"]) != entry["sha256"]:
                raise ValueError("Input checksum changed")
    return {"outputs_verified": True, "inputs_verified": input_root is not None,
            "evidence_kind": receipt["evidence_kind"], "scientific_validity_certified": False}

