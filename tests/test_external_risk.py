from datetime import date

import numpy as np
import pandas as pd
import pytest

from logisrisk.analytics import risk
from logisrisk.data.external import load_external


@pytest.fixture(scope="module")
def ext():
    return load_external(today=date(2026, 11, 5))


def test_existing_outputs_load_and_population(ext):
    assert ext.units is not None and len(ext.units) == 374
    assert ext.units["unitCode"].is_unique
    assert ext.provenance["traffic"].period_start == "2025-01-01"
    assert ext.provenance["fuel_history"].n == 455


def test_vulnerability_reproduced_exactly(ext):
    rep = risk.verify_vulnerability(ext.units)
    assert rep["max_abs_diff"] < 1e-9


def test_quartile_grade_matches_existing(ext):
    g = risk.quartile_grade(ext.units["vulnerability_score"])
    assert (g == ext.units["vulnerability_grade"]).mean() > 0.99


def test_reweight_changes_rank_and_is_deterministic(ext):
    w = {"freight_share": 0.1, "freight_volume": 0.1, "volatility": 0.4, "imbalance": 0.4}
    a, b = risk.recompute_units(ext.units, w), risk.recompute_units(ext.units, w)
    assert np.allclose(a["sim_vulnerability"], b["sim_vulnerability"])
    assert (a["rank_change"] != 0).any()
    assert risk.scenario_id({"weights": w}) == risk.scenario_id({"weights": dict(reversed(list(w.items())))})


def test_weight_validation():
    with pytest.raises(ValueError):
        risk.normalize_weights({"freight_share": -1, "freight_volume": 1, "volatility": 1, "imbalance": 1})
    with pytest.raises(ValueError):
        risk.normalize_weights({"freight_share": 0, "freight_volume": 0, "volatility": 0, "imbalance": 0})
    assert sum(risk.normalize_weights({"freight_share": 3, "freight_volume": 3, "volatility": 2, "imbalance": 2}).values()) == pytest.approx(1)


def test_minmax_zero_variance():
    assert (risk.minmax(pd.Series([5.0, 5.0])) == 0).all()


def test_ensemble_weight_inferred_and_reweight(ext):
    f = ext.forecast
    assert risk.infer_ensemble_weight(f) == pytest.approx(0.4, abs=1e-4)
    assert np.allclose(risk.reweight_ensemble(f, 0.4), f["diesel_price_ensemble"], atol=1e-3)
    with pytest.raises(ValueError):
        risk.reweight_ensemble(f, 1.5)


def test_shock_index_reproduced(ext):
    f = ext.forecast
    assert np.allclose(risk.shock_index_minmax(f["diesel_change_rate"]), f["diesel_shock_index"])


def test_audit_flags_known_issues(ext):
    titles = {x["title"]: x for x in ext.findings}
    assert "유가 예측 기간 경과" in titles
    assert "Fuel Shock Impact Score 해석 주의" in titles
    assert "위험 등급 의미 불일치" in titles
    assert titles["취약성 점수 재현성"]["level"] == "ok"
    assert "476" in titles["공간분석 모집단"]["detail"]


def test_period_comparison_is_labelled_observational(ext):
    r = risk.period_comparison(ext.traffic, "2026-02-28")
    assert r["status"] == "ok" and "인과" in r["caveat"]
    t = ext.traffic
    pre = t[t["date"] < "2026-02-28"]["freight_345_traffic"].mean()
    assert r["pre_mean"] == pytest.approx(pre)
    assert "yoy_pct" in r


def test_missing_files_reported(tmp_path):
    e = load_external(dirs=[tmp_path])
    assert e.units is None and len(e.missing) == 4
