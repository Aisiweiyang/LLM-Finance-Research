"""Cross-sectional price/ability frontier; no inferred historical efficiency trend."""

import numpy as np
import pandas as pd


def capability_frontier(data):
    if not {"model", "ability", "price"} <= set(data):
        raise ValueError("Need model, ability, price (USD per 1M tokens)")
    frame = data.copy()
    if frame.model.isna().any() or frame.model.duplicated().any():
        raise ValueError("Model keys must be non-null and unique")
    for column in ("ability", "price"):
        frame[column] = pd.to_numeric(frame[column], errors="raise")
    keep = np.isfinite(frame.ability) & np.isfinite(frame.price) & (frame.price > 0)
    rejected = frame.loc[~keep].copy()
    rejected["reason"] = "missing_or_nonfinite_ability_or_nonpositive_price"
    frame = frame.loc[keep].copy()
    points = frame[["price", "ability"]].to_numpy(dtype=float)
    frontier = []
    for price, score in points:
        dominates = (points[:, 0] <= price) & (points[:, 1] >= score)
        strict = (points[:, 0] < price) | (points[:, 1] > score)
        frontier.append(not bool((dominates & strict).any()))
    frame["on_frontier"] = frontier
    frame["ln_price"] = np.log(frame.price)
    return frame.reset_index(drop=True), rejected.reset_index(drop=True)

