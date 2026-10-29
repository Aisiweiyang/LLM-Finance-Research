"""Explicit, bounded collection. No network operations at module import."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

import pandas as pd
import requests


def item_tokens(value):
    if isinstance(value, (list, tuple, set)):
        return {str(x).strip() for x in value}
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return set()
    return {x.strip() for x in re.split(r"[;,]", str(value))}


def filter_sec_items(data, item="1.05"):
    if "items" not in data:
        raise ValueError("SEC structured items column is required; keywords are insufficient")
    mask = data["items"].map(lambda value: item in item_tokens(value))
    accepted, rejected = data.loc[mask].copy(), data.loc[~mask].copy()
    rejected["reason"] = "structured_item_not_present"
    return accepted, rejected


def _download_json(url, output, user_agent, timeout=30):
    path = Path(output)
    receipt = path.with_suffix(path.suffix + ".source.json")
    if path.exists() or receipt.exists():
        raise ValueError("Collection output already exists; use a new source snapshot path")
    response = requests.get(url, headers={"User-Agent": user_agent}, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("Expected a JSON object")
    body = response.content
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    receipt.write_text(json.dumps({"url": url, "retrieved_at": datetime.now(timezone.utc).isoformat(),
                                  "sha256": hashlib.sha256(body).hexdigest(),
                                  "historical_availability_certified": False}, indent=2), encoding="utf-8")
    return payload


def fetch_companyfacts(cik, output, user_agent):
    digits = str(cik)
    if not digits.isdigit() or not 1 <= int(digits) <= 9_999_999_999:
        raise ValueError("CIK must be a positive integer with at most ten digits")
    if not user_agent or "@" not in user_agent or "example." in user_agent.lower():
        raise ValueError("Set a real identifying SEC_USER_AGENT including a contact address")
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{int(digits):010d}.json"
    return _download_json(url, output, user_agent)


def fetch_litellm(commit, output):
    if not re.fullmatch(r"[0-9a-fA-F]{40}", commit):
        raise ValueError("An immutable full 40-character Git commit SHA is required")
    url = f"https://raw.githubusercontent.com/BerriAI/litellm/{commit}/model_prices_and_context_window.json"
    return _download_json(url, output, "llm-finance-research/0.1")


def normalize_litellm(snapshot, commit):
    if not re.fullmatch(r"[0-9a-fA-F]{40}", commit):
        raise ValueError("A full source commit SHA is required")
    rows = []
    for key, value in snapshot.items():
        if not isinstance(value, dict):
            continue
        if "input_cost_per_token" not in value and "output_cost_per_token" not in value:
            continue
        row = {"model": key, "source_commit": commit, "provider": value.get("litellm_provider"),
               "mode": value.get("mode")}
        for source, target in [("input_cost_per_token", "price_in_per_1M"), ("output_cost_per_token", "price_out_per_1M")]:
            rate = value.get(source)
            if rate is not None:
                rate = float(rate)
                if not 0 <= rate < float("inf"):
                    raise ValueError("Token prices must be finite and nonnegative")
            row[target] = rate * 1e6 if rate is not None else None
        rows.append(row)
    return pd.DataFrame(rows, columns=["model", "source_commit", "provider", "mode", "price_in_per_1M", "price_out_per_1M"])

