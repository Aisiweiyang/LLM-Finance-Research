"""Explicit file-based commands with sealed outputs and no workstation paths."""

import argparse
import json
import os
from pathlib import Path
import sys

import pandas as pd
import requests

from .demo import make_demo
from .events import EventConfig, event_study
from .finance import extract_cashflow_quarters
from .pricing import capability_frontier
from .provenance import seal_run, verify_run, write_json
from .regression import fit_ols
from .sources import fetch_companyfacts, fetch_litellm, filter_sec_items, normalize_litellm


def parser():
    p = argparse.ArgumentParser(description="Portable LLM-finance empirical research tools")
    sub = p.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo", help="Run an explicitly synthetic offline demonstration")
    demo.add_argument("--output", required=True, type=Path)
    verify = sub.add_parser("verify", help="Check run outputs; optionally recheck input bytes")
    verify.add_argument("directory", type=Path)
    verify.add_argument("--input-root", type=Path)
    ev = sub.add_parser("events", help="Market-model CAR on supplied adjusted-close data")
    ev.add_argument("--prices", required=True, type=Path)
    ev.add_argument("--events", required=True, type=Path)
    ev.add_argument("--config", type=Path)
    ev.add_argument("--item", help="Require this exact structured SEC item before estimation")
    ev.add_argument("--output", required=True, type=Path)
    front = sub.add_parser("frontier", help="Price/ability cross-sectional Pareto frontier")
    front.add_argument("--input", required=True, type=Path)
    front.add_argument("--output", required=True, type=Path)
    reg = sub.add_parser("ols", help="OLS with explicit intercept and HC1 or cluster SE")
    reg.add_argument("--input", required=True, type=Path)
    reg.add_argument("--outcome", required=True)
    reg.add_argument("--features", nargs="*", default=[])
    reg.add_argument("--categorical", nargs="*", default=[])
    reg.add_argument("--cluster")
    reg.add_argument("--output", required=True, type=Path)
    xbrl = sub.add_parser("xbrl", help="De-cumulate a specified SEC cash-flow tag")
    xbrl.add_argument("--input", required=True, type=Path)
    xbrl.add_argument("--tag", required=True)
    xbrl.add_argument("--unit", default="USD")
    xbrl.add_argument("--taxonomy", default="us-gaap")
    xbrl.add_argument("--as-of", help="Optional filing-date cutoff YYYY-MM-DD")
    xbrl.add_argument("--output", required=True, type=Path)
    sec = sub.add_parser("fetch-sec", help="Explicit network request: one companyfacts snapshot")
    sec.add_argument("--cik", required=True)
    sec.add_argument("--output", required=True, type=Path)
    llm = sub.add_parser("fetch-litellm", help="Explicit network request: one immutable price snapshot")
    llm.add_argument("--commit", required=True)
    llm.add_argument("--output", required=True, type=Path)
    norm = sub.add_parser("normalize-prices", help="Normalize a local LiteLLM JSON snapshot")
    norm.add_argument("--input", required=True, type=Path)
    norm.add_argument("--commit", required=True)
    norm.add_argument("--output", required=True, type=Path)
    return p


def execute(args):
    if args.command == "verify":
        return verify_run(args.directory, args.input_root)
    if args.command == "fetch-sec":
        fetch_companyfacts(args.cik, args.output, os.environ.get("SEC_USER_AGENT"))
        return {"saved": str(args.output), "historical_availability_certified": False}
    if args.command == "fetch-litellm":
        fetch_litellm(args.commit, args.output)
        return {"saved": str(args.output), "historical_availability_certified": False}
    # Create-only runs cannot quietly overwrite previous findings.
    args.output.mkdir(parents=True, exist_ok=False)
    try:
        if args.command == "demo":
            return make_demo(args.output)
        inputs, parameters = [], {"command": args.command}
        if args.command == "events":
            cfg = EventConfig(**json.loads(args.config.read_text(encoding="utf-8"))) if args.config else EventConfig()
            events = pd.read_csv(args.events, dtype={"event_id": str, "ticker": str})
            inputs = [args.prices, args.events]
            if args.config:
                inputs.append(args.config)
            if args.item:
                events, rejected_items = filter_sec_items(events, args.item)
                rejected_items.to_csv(args.output / "item_rejections.csv", index=False)
            accepted, rejected = event_study(pd.read_csv(args.prices, dtype={"ticker": str}), events, cfg)
            accepted.to_csv(args.output / "events.csv", index=False)
            rejected.to_csv(args.output / "rejected_events.csv", index=False)
            parameters.update({"event_config": cfg.to_dict(), "structured_sec_item": args.item,
                               "event_session_policy": "on_or_next_benchmark_session",
                               "n_accepted": len(accepted), "n_rejected_after_item_filter": len(rejected)})
        elif args.command == "frontier":
            frame, rejected = capability_frontier(pd.read_csv(args.input))
            frame.to_csv(args.output / "frontier.csv", index=False)
            rejected.to_csv(args.output / "rejected_models.csv", index=False)
            inputs = [args.input]
            parameters["price_unit"] = "USD_per_1M_tokens_user_selected_blend"
        elif args.command == "ols":
            table, diagnostics = fit_ols(pd.read_csv(args.input), args.outcome, args.features, args.categorical, args.cluster)
            table.to_csv(args.output / "regression.csv", index=False)
            write_json(args.output / "diagnostics.json", diagnostics)
            inputs = [args.input]
            parameters.update({"outcome": args.outcome, "features": args.features, "categorical": args.categorical,
                               "cluster": args.cluster, "intercept": True})
        elif args.command == "xbrl":
            frame = extract_cashflow_quarters(json.loads(args.input.read_text(encoding="utf-8")), args.tag,
                                               args.unit, args.taxonomy, args.as_of)
            frame.to_csv(args.output / "quarterly.csv", index=False)
            inputs = [args.input]
            parameters.update({"tag": args.tag, "unit": args.unit, "taxonomy": args.taxonomy,
                               "as_of_filed": args.as_of, "quarters": len(frame)})
        elif args.command == "normalize-prices":
            frame = normalize_litellm(json.loads(args.input.read_text(encoding="utf-8")), args.commit)
            frame.to_csv(args.output / "prices.csv", index=False)
            inputs = [args.input]
            parameters["source_commit"] = args.commit
        else:
            raise ValueError("Unsupported command")
        return seal_run(args.output, inputs, parameters, "USER_SUPPLIED_LOCAL_DATA")
    except Exception as exc:
        # Preserve a bounded failure record without publishing local input paths.
        write_json(args.output / "failure.json", {"status": "FAILED", "command": args.command,
                                                 "error_type": type(exc).__name__})
        raise


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        result = execute(args)
    except (ValueError, TypeError, OSError, KeyError, requests.RequestException) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0

