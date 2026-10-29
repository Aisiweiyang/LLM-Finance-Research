"""Conservative SEC cash-flow de-cumulation, derived from the original project."""

from datetime import date, timedelta
import math

import pandas as pd


def quarterly_from_cumulative(units, as_of=None):
    """Return complete-prefix fiscal quarters; annual-only facts yield no quarters.

    Supports USD duration facts anchored by 10-K fiscal years. 10-Q trailing
    twelve-month facts never establish a fiscal-year boundary. This is a helper
    for cumulative cash-flow tags, not a universal income-statement/IFRS mapper.
    """
    cutoff = date.fromisoformat(as_of) if as_of else None
    best = {}
    for fact in units:
        if not all(fact.get(k) is not None for k in ("start", "end", "val", "filed", "form")):
            continue
        start, end, filed = (date.fromisoformat(fact[k]) for k in ("start", "end", "filed"))
        form = str(fact["form"]).removesuffix("/A")
        if form not in ("10-Q", "10-K") or not 60 <= (end - start).days <= 400:
            continue
        value = float(fact["val"])
        if not math.isfinite(value):
            raise ValueError("Nonfinite XBRL fact")
        if cutoff and filed > cutoff:
            continue
        row = {**fact, "val": value, "_start": start, "_end": end, "_filed": filed}
        key = (start, end)
        if key in best and filed == best[key]["_filed"] and value != best[key]["val"]:
            raise ValueError("Conflicting XBRL values for the same period and filing date")
        if key not in best or filed > best[key]["_filed"]:
            best[key] = row
    facts = list(best.values())
    annual = sorted((f for f in facts if str(f["form"]).startswith("10-K") and 300 <= (f["_end"] - f["_start"]).days <= 400),
                    key=lambda f: f["_end"])
    windows = [(f["_start"], f["_end"], f) for f in annual]
    if annual:
        windows.append((annual[-1]["_end"] + timedelta(days=1), date.max, None))
    output = {}
    for start, end, annual_fact in windows:
        cumulative, discrete = {}, {}
        for fact in facts:
            if not start <= fact["_start"] <= fact["_end"] <= end:
                continue
            span = (fact["_end"] - fact["_start"]).days
            elapsed = (fact["_end"] - start).days
            quarter = int(round((elapsed + 1) / 91.3125))
            if quarter not in (1, 2, 3, 4):
                continue
            if 60 <= span <= 120:
                old = discrete.get(quarter)
                if old is None or fact["_filed"] > old["_filed"]:
                    discrete[quarter] = fact
            if abs((fact["_start"] - start).days) <= 7 and quarter <= 3:
                old = cumulative.get(quarter)
                if old is None or fact["_filed"] > old["_filed"]:
                    cumulative[quarter] = fact
        if annual_fact:
            cumulative[4] = annual_fact
        previous_value, previous_end, prefix = 0.0, start - timedelta(days=1), []
        for quarter in range(1, 5):
            if quarter == 4 and annual_fact is None:
                break
            current = cumulative.get(quarter)
            direct = discrete.get(quarter)
            if current is not None:
                value = current["val"] - previous_value
                used = prefix + [current]
            elif direct is not None:
                value, current, used = direct["val"], direct, prefix + [direct]
            else:
                break
            if not 60 <= (current["_end"] - previous_end).days <= 120:
                break
            filed = max(f["_filed"] for f in used)
            output[current["end"]] = {
                "quarter_end": current["end"], "period_start": (previous_end + timedelta(days=1)).isoformat(),
                "value": value, "filed": filed.isoformat(), "fiscal_start": start.isoformat(),
                "accessions": ";".join(sorted({f.get("accn", "") for f in used if f.get("accn")})),
            }
            previous_value += value
            previous_end, prefix = current["_end"], used
    return output


def extract_cashflow_quarters(companyfacts, tag, unit="USD", taxonomy="us-gaap", as_of=None):
    try:
        facts = companyfacts["facts"][taxonomy][tag]["units"][unit]
    except KeyError as exc:
        raise ValueError("Requested taxonomy/tag/unit is absent; no inferred fallback") from exc
    rows = quarterly_from_cumulative(facts, as_of=as_of)
    return pd.DataFrame(rows.values(), columns=["quarter_end", "period_start", "value", "filed", "fiscal_start", "accessions"])

