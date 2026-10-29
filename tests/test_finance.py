import pytest

from llm_finance.finance import quarterly_from_cumulative, extract_cashflow_quarters


def fact(start, end, value, form="10-Q", filed="2026-02-01"):
    return {"start": start, "end": end, "val": value, "form": form, "filed": filed, "accn": "synthetic"}


def annual_facts():
    return [fact("2025-01-01", "2025-03-31", 25),
            fact("2025-01-01", "2025-06-30", 57),
            fact("2025-01-01", "2025-09-30", 92),
            fact("2025-01-01", "2025-12-31", 131, "10-K")]


def test_ytd_decumulation_conserves_full_year():
    out = quarterly_from_cumulative(annual_facts())
    assert [r["value"] for r in out.values()] == [25, 32, 35, 39]
    assert sum(r["value"] for r in out.values()) == 131


def test_ttm_cannot_create_open_year_or_fake_q1():
    facts = annual_facts() + [fact("2025-04-01", "2026-03-31", 150),
                              fact("2026-01-01", "2026-03-31", 30, filed="2026-05-01")]
    out = quarterly_from_cumulative(facts)
    assert out["2026-03-31"]["value"] == 30
    assert len(out) == 5


def test_missing_q2_stops_prefix_and_annual_only_yields_no_quarters():
    facts = annual_facts()
    out = quarterly_from_cumulative([facts[0], facts[2], facts[3]])
    assert list(out) == ["2025-03-31"]
    assert quarterly_from_cumulative([facts[3]]) == {}


def test_filing_date_cutoff_does_not_use_later_restatement():
    facts = annual_facts()
    facts += [fact("2025-01-01", "2025-03-31", 40, filed="2027-02-01")]
    old = quarterly_from_cumulative(facts, as_of="2026-12-31")
    assert old["2025-03-31"]["value"] == 25
    new = quarterly_from_cumulative(facts)
    assert new["2025-03-31"]["value"] == 40
    assert new["2025-06-30"]["value"] == 17
    assert new["2025-06-30"]["filed"] == "2027-02-01"


def test_conflicts_and_unsupported_tags_are_explicit():
    facts = annual_facts()
    with pytest.raises(ValueError, match="Conflicting"):
        quarterly_from_cumulative(facts + [fact("2025-01-01", "2025-03-31", 900)])
    with pytest.raises(ValueError, match="absent"):
        extract_cashflow_quarters({"facts": {}}, "Unknown")

