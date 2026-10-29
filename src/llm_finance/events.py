"""Market-model event studies on the benchmark's trading-session calendar."""

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class EventConfig:
    benchmark: str = "SPY"
    estimation_sessions: int = 120
    gap_sessions: int = 10
    window_start: int = -10
    window_end: int = 10
    reject_overlaps: bool = True

    def __post_init__(self):
        for key in ("estimation_sessions", "gap_sessions", "window_start", "window_end"):
            if type(getattr(self, key)) is not int:
                raise ValueError(f"{key} must be an integer")
        if not isinstance(self.benchmark, str) or not self.benchmark.strip():
            raise ValueError("benchmark must be a nonempty ticker")
        if type(self.reject_overlaps) is not bool:
            raise ValueError("reject_overlaps must be boolean")
        if self.estimation_sessions < 10 or not self.window_start <= 0 <= self.window_end:
            raise ValueError("Need >=10 estimation sessions and an event window containing zero")
        if self.gap_sessions < max(0, -self.window_start):
            raise ValueError("Estimation and event windows must not overlap")

    def to_dict(self):
        return asdict(self)


def _dates(series):
    if not series.astype(str).str.fullmatch(r"\d{4}-\d{2}-\d{2}").all():
        raise ValueError("Dates must be local session dates in YYYY-MM-DD format")
    return pd.to_datetime(series, format="%Y-%m-%d", errors="raise")


def event_study(prices, events, config=None):
    """Return (accepted, rejected). Missing sessions never compress the calendar.

    Inputs: prices(date,ticker,adjusted_close), events(event_id,event_date,ticker).
    The supplied event_date must already reflect the relevant market's disclosure
    time. This function cannot infer after-close disclosure or certify PIT status.
    """
    cfg = config or EventConfig()
    if not {"date", "ticker", "adjusted_close"} <= set(prices):
        raise ValueError("prices needs date, ticker, adjusted_close")
    if not {"event_id", "event_date", "ticker"} <= set(events):
        raise ValueError("events needs event_id, event_date, ticker")
    p, e = prices.copy(), events.copy()
    if p[["date", "ticker", "adjusted_close"]].isna().any().any():
        raise ValueError("Price keys and values must not be null")
    if e[["event_id", "event_date", "ticker"]].isna().any().any():
        raise ValueError("Event keys must not be null")
    p["date"], e["event_date"] = _dates(p.date), _dates(e.event_date)
    if p.duplicated(["date", "ticker"]).any() or e.duplicated(["event_id", "ticker"]).any():
        raise ValueError("Duplicate price key or event/proxy key")
    p["adjusted_close"] = pd.to_numeric(p.adjusted_close, errors="raise")
    if not np.isfinite(p.adjusted_close.to_numpy(dtype=float)).all() or (p.adjusted_close <= 0).any():
        raise ValueError("Adjusted closes must be finite and positive")
    pivot = p.pivot(index="date", columns="ticker", values="adjusted_close").sort_index()
    if cfg.benchmark not in pivot:
        raise ValueError("Benchmark is absent")
    calendar = pivot[cfg.benchmark].dropna().index
    panel = pivot.reindex(calendar)
    returns = np.log(panel / panel.shift(1))
    market = returns[cfg.benchmark]
    accepted, rejected, last_end = [], [], {}
    columns = ["event_id", "ticker", "event_date", "event_session", "ar_0",
               "car", "car_se", "standardized_car", "estimation_sigma", "event_sessions"]
    for row in e.sort_values(["ticker", "event_date", "event_id"]).to_dict("records"):
        ticker, date = row["ticker"], row["event_date"]
        base = {"event_id": row["event_id"], "ticker": ticker, "event_date": str(date.date())}

        def reject(reason):
            rejected.append({**base, "reason": reason})

        if ticker == cfg.benchmark:
            reject("benchmark_as_outcome")
            continue
        if ticker not in returns:
            reject("missing_ticker")
            continue
        pos = int(calendar.searchsorted(date))
        est_start, est_end = pos - cfg.gap_sessions - cfg.estimation_sessions, pos - cfg.gap_sessions
        start, end = pos + cfg.window_start, pos + cfg.window_end + 1
        # Index 0 has no preceding return; keep full benchmark sessions throughout.
        if est_start < 1 or start < 1 or end > len(calendar):
            reject("insufficient_history_or_followup")
            continue
        y = returns[ticker].iloc[est_start:est_end].to_numpy(dtype=float)
        m = market.iloc[est_start:est_end].to_numpy(dtype=float)
        event_y = returns[ticker].iloc[start:end].to_numpy(dtype=float)
        event_m = market.iloc[start:end].to_numpy(dtype=float)
        if not all(np.isfinite(v).all() for v in (y, m, event_y, event_m)):
            reject("missing_session_return")
            continue
        if cfg.reject_overlaps and start <= last_end.get(ticker, -1):
            reject("overlapping_event_window")
            continue
        x = np.column_stack([np.ones(len(m)), m])
        if np.linalg.matrix_rank(x) != 2:
            reject("singular_market_model")
            continue
        beta = np.linalg.lstsq(x, y, rcond=None)[0]
        residual = y - x @ beta
        sigma2 = float(residual @ residual / (len(y) - 2))
        if sigma2 <= np.finfo(float).eps:
            reject("degenerate_estimation_residuals")
            continue
        xe = np.column_stack([np.ones(len(event_m)), event_m])
        abnormal = event_y - xe @ beta
        # CAR prediction error includes estimated alpha/beta uncertainty.
        sum_x = xe.sum(axis=0)
        variance = sigma2 * (len(abnormal) + sum_x @ np.linalg.inv(x.T @ x) @ sum_x)
        car, se = float(abnormal.sum()), float(np.sqrt(variance))
        accepted.append({**base, "event_session": str(calendar[pos].date()),
                         "ar_0": float(abnormal[-cfg.window_start]),
                         "car": car, "car_se": se, "standardized_car": car / se,
                         "estimation_sigma": float(np.sqrt(sigma2)), "event_sessions": len(abnormal)})
        last_end[ticker] = end - 1
    return (pd.DataFrame(accepted, columns=columns),
            pd.DataFrame(rejected, columns=["event_id", "ticker", "event_date", "reason"]))

