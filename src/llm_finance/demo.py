"""Deterministic synthetic examples, never paper results or live market data."""

import numpy as np
import pandas as pd

from .events import EventConfig, event_study
from .pricing import capability_frontier
from .regression import fit_ols
from .provenance import seal_run, write_json


def make_demo(root):
    rng = np.random.default_rng(42)
    dates = pd.bdate_range("2020-01-01", periods=240)
    market = rng.normal(0.0003, 0.009, len(dates))
    residual = rng.normal(0, 0.004, len(dates))
    outcome = 0.0001 + 1.1 * market + residual
    outcome[180] += 0.04
    prices = pd.concat([pd.DataFrame({"date": dates.strftime("%Y-%m-%d"), "ticker": ticker,
                                     "adjusted_close": 100 * np.exp(np.cumsum(values))})
                        for ticker, values in [("DEMO_MARKET", market), ("DEMO_FIRM", outcome)]], ignore_index=True)
    events = pd.DataFrame([{"event_id": "synthetic-shock", "event_date": str(dates[180].date()),
                            "ticker": "DEMO_FIRM"}])
    ability = rng.uniform(20, 80, 80)
    open_weights = rng.integers(0, 2, 80)
    vendor = rng.choice(["synthetic-a", "synthetic-b"], 80)
    price = np.exp(-2 + 0.04 * ability - 0.5 * open_weights +
                   0.2 * (vendor == "synthetic-b") + rng.normal(0, 0.1, 80))
    capability = pd.DataFrame({"model": [f"synthetic-{i}" for i in range(80)],
                               "ability": ability, "price": price,
                               "open_weights": open_weights, "vendor": vendor})
    input_dir = root / "inputs"
    input_dir.mkdir()
    paths = []
    for name, frame in [("synthetic_prices.csv", prices), ("synthetic_events.csv", events),
                         ("synthetic_capability.csv", capability)]:
        path = input_dir / name
        frame.to_csv(path, index=False)
        paths.append(path)
    cfg = EventConfig(benchmark="DEMO_MARKET", window_start=-1, window_end=1)
    accepted, rejected = event_study(prices, events, cfg)
    accepted.to_csv(root / "event_results.csv", index=False)
    rejected.to_csv(root / "event_rejections.csv", index=False)
    frontier, _ = capability_frontier(capability)
    frontier.to_csv(root / "frontier.csv", index=False)
    table, diagnostics = fit_ols(frontier, "ln_price", ["ability", "open_weights"], ["vendor"])
    table.to_csv(root / "hedonic_regression.csv", index=False)
    write_json(root / "diagnostics.json", diagnostics)
    return seal_run(root, paths, {"command": "demo", "seed": 42, "event_config": cfg.to_dict()},
                    "SYNTHETIC_DEMO")

