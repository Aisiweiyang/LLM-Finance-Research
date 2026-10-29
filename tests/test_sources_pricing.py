import pandas as pd
import pytest

from llm_finance.pricing import capability_frontier
from llm_finance.sources import filter_sec_items, normalize_litellm, fetch_companyfacts, fetch_litellm


def test_item105_requires_exact_structured_item():
    data = pd.DataFrame({"items": ["1.05;9.01", "2.02;9.01", "1.050", None, ["1.05"]], "id": range(5)})
    accepted, rejected = filter_sec_items(data)
    assert accepted.id.tolist() == [0, 4]
    assert rejected.id.tolist() == [1, 2, 3]
    with pytest.raises(ValueError, match="structured"):
        filter_sec_items(pd.DataFrame({"text": ["Item 1.05 was mentioned"]}))


def test_same_ability_cheaper_model_dominates():
    data = pd.DataFrame({"model": ["cheap", "expensive", "best", "bad"],
                         "ability": [20, 20, 30, 40], "price": [1, 2, 3, 0]})
    frontier, rejected = capability_frontier(data)
    assert frontier[frontier.on_frontier].model.tolist() == ["cheap", "best"]
    assert rejected.model.tolist() == ["bad"]


def test_price_normalization_preserves_aliases_and_units():
    source = {"alias": {"input_cost_per_token": .000005, "output_cost_per_token": .000015},
              "dated-version": {"input_cost_per_token": .0000025}, "metadata": "ignore"}
    table = normalize_litellm(source, "a" * 40)
    assert table.model.tolist() == ["alias", "dated-version"]
    assert table.price_in_per_1M.tolist() == [5., 2.5]
    assert table.price_out_per_1M.iloc[0] == 15.


def test_collection_is_opt_in_and_validates_before_any_request(tmp_path):
    with pytest.raises(ValueError, match="SEC_USER_AGENT"):
        fetch_companyfacts("789019", tmp_path / "sec.json", None)
    with pytest.raises(ValueError, match="immutable"):
        fetch_litellm("main", tmp_path / "prices.json")
    assert not list(tmp_path.iterdir())

