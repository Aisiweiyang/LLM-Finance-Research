"""Explicit-intercept OLS; inference settings and excluded rows stay inspectable."""

import numpy as np
import pandas as pd
import statsmodels.api as sm


def fit_ols(data, outcome, features, categorical=(), cluster=None):
    features, categorical = list(features), list(categorical)
    if not features and not categorical:
        raise ValueError("At least one regressor is required")
    predictors = features + categorical
    if len(set(predictors)) != len(predictors) or outcome in predictors:
        raise ValueError("Regressors must be unique and exclude the outcome")
    required = list(dict.fromkeys([outcome] + predictors + ([cluster] if cluster else [])))
    if not set(required) <= set(data):
        raise ValueError(f"Missing columns: {sorted(set(required) - set(data))}")
    frame = data[required].copy().reset_index(drop=True)
    for column in [outcome] + features:
        frame[column] = pd.to_numeric(frame[column], errors="raise")
        if np.isinf(frame[column].to_numpy(dtype=float)).any():
            raise ValueError("Infinite values are not allowed")
    keep = frame.notna().all(axis=1)
    excluded = np.flatnonzero(~keep.to_numpy()).tolist()
    frame = frame.loc[keep].reset_index(drop=True)
    design = frame[features].astype(float)
    for column in categorical:
        dummy = pd.get_dummies(frame[column].astype(str), prefix=column, drop_first=True, dtype=float)
        design = pd.concat([design, dummy], axis=1)
    design = sm.add_constant(design, has_constant="add")
    if design.columns.duplicated().any():
        raise ValueError("Regressor names collide with generated dummy/intercept names")
    if len(frame) <= design.shape[1] or np.linalg.matrix_rank(design.to_numpy()) != design.shape[1]:
        raise ValueError("Insufficient observations or rank-deficient regression")
    model = sm.OLS(frame[outcome].to_numpy(dtype=float), design)
    groups = int(frame[cluster].nunique()) if cluster else None
    if cluster and groups < 2:
        raise ValueError("Cluster inference requires at least two groups")
    fit = model.fit(cov_type="cluster", cov_kwds={"groups": frame[cluster].to_numpy()}, use_t=True) if cluster else model.fit(cov_type="HC1", use_t=True)
    table = pd.DataFrame({"term": design.columns, "coefficient": np.asarray(fit.params),
                          "standard_error": np.asarray(fit.bse), "t": np.asarray(fit.tvalues),
                          "p": np.asarray(fit.pvalues)})
    metadata = {"n_input": len(data), "n_used": len(frame), "excluded_row_positions": excluded,
                "intercept": True, "covariance": "cluster" if cluster else "HC1",
                "cluster": cluster, "n_clusters": groups, "small_cluster_warning": bool(cluster and groups < 30),
                "r_squared": float(fit.rsquared), "causal_identification": "not_established"}
    return table, metadata

