import numpy as np
import pandas as pd
import pytest

from llm_finance.regression import fit_ols


def test_intercept_and_hc1_match_independent_matrix_calculation():
    rng = np.random.default_rng(4)
    x = rng.normal(size=80)
    y = 7 + 2 * x + rng.normal(size=80)
    data = pd.DataFrame({"x": x, "y": y}, index=np.arange(80) * 9)
    data.iloc[4, 0] = np.nan
    table, metadata = fit_ols(data, "y", ["x"])
    keep = np.isfinite(data.x.to_numpy())
    design = np.column_stack([np.ones(keep.sum()), x[keep]])
    coefficients = np.linalg.inv(design.T @ design) @ design.T @ y[keep]
    error = y[keep] - design @ coefficients
    bread = np.linalg.inv(design.T @ design)
    meat = design.T @ np.diag(error ** 2) @ design
    covariance = bread @ meat @ bread * len(error) / (len(error) - 2)
    np.testing.assert_allclose(table.coefficient, coefficients, rtol=1e-12)
    np.testing.assert_allclose(table.standard_error, np.sqrt(np.diag(covariance)), rtol=1e-12)
    assert metadata["excluded_row_positions"] == [4]
    assert metadata["intercept"] is True


def test_cluster_groups_follow_excluded_rows():
    rng = np.random.default_rng(17)
    data = pd.DataFrame({"x": rng.normal(size=60), "y": rng.normal(size=60), "firm": np.repeat(["a", "b", "c"], 20)})
    data.loc[3, "x"] = np.nan
    table, meta = fit_ols(data, "y", ["x"], cluster="firm")
    assert meta["n_used"] == 59 and meta["n_clusters"] == 3
    assert meta["small_cluster_warning"] is True
    assert np.isfinite(table.standard_error).all()


def test_singular_and_outcome_regressor_are_rejected():
    data = pd.DataFrame({"x": [1., 2., 3., 4.], "copy": [2., 4., 6., 8.], "y": [3., 4., 5., 7.]})
    with pytest.raises(ValueError, match="rank"):
        fit_ols(data, "y", ["x", "copy"])
    with pytest.raises(ValueError, match="outcome"):
        fit_ols(data, "y", ["y"])

