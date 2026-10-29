import json
import subprocess
import sys

import pytest

from llm_finance.cli import main
from llm_finance.provenance import verify_run, write_json


def test_offline_demo_cli_and_output_tamper(tmp_path):
    root = tmp_path / "demo"
    assert main(["demo", "--output", str(root)]) == 0
    check = verify_run(root, root / "inputs")
    assert check["inputs_verified"] and check["outputs_verified"]
    assert check["evidence_kind"] == "SYNTHETIC_DEMO"
    assert check["scientific_validity_certified"] is False
    assert main(["demo", "--output", str(root)]) == 1
    (root / "event_results.csv").write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="checksum"):
        verify_run(root)


def test_manifest_extra_file_and_path_traversal_are_rejected(tmp_path):
    root = tmp_path / "demo"
    assert main(["demo", "--output", str(root)]) == 0
    (root / "extra.txt").write_text("unregistered", encoding="utf-8")
    with pytest.raises(ValueError, match="inventory"):
        verify_run(root)
    receipt = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    receipt["files"]["../escape.txt"] = "unused"
    write_json(root / "manifest.json", receipt)
    with pytest.raises(ValueError, match="outside"):
        verify_run(root)


def test_events_and_ols_entrypoints_use_supplied_inputs(tmp_path):
    demo = tmp_path / "demo"
    assert main(["demo", "--output", str(demo)]) == 0
    cfg = tmp_path / "config.json"
    write_json(cfg, {"benchmark": "DEMO_MARKET", "window_start": -1, "window_end": 1})
    event_out = tmp_path / "events"
    assert main(["events", "--prices", str(demo / "inputs/synthetic_prices.csv"),
                 "--events", str(demo / "inputs/synthetic_events.csv"), "--config", str(cfg),
                 "--output", str(event_out)]) == 0
    assert verify_run(event_out)["outputs_verified"]
    reg_out = tmp_path / "ols"
    assert main(["ols", "--input", str(demo / "frontier.csv"), "--outcome", "ln_price",
                 "--features", "ability", "open_weights", "--categorical", "vendor",
                 "--output", str(reg_out)]) == 0
    diagnostic = json.loads((reg_out / "diagnostics.json").read_text())
    assert diagnostic["intercept"] is True and diagnostic["n_used"] == 80


def test_import_has_no_network_or_file_side_effects(tmp_path):
    script = "import requests; requests.get=lambda *a,**k: (_ for _ in ()).throw(AssertionError('network')); import llm_finance.cli, llm_finance.sources"
    result = subprocess.run([sys.executable, "-B", "-c", script], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert list(tmp_path.iterdir()) == []

