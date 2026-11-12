"""성능 회귀 가드 — 1차·2차 개선(docs/IMPROVEMENT_PLAN.md)이 되돌아가지 않도록.

시간 단언은 기기 편차를 감안해 개선 전 대비 '자릿수' 차이만 잡는 넉넉한 상한을 쓰고,
가능하면 호출 횟수처럼 결정적인 값으로 확인한다.
"""
import time

import pandas as pd

from logisrisk.analytics import cost, kpi
from logisrisk.views import analysis as A
from logisrisk.views import control_tower as CT


def _scaled(fact: pd.DataFrame, mult: int) -> pd.DataFrame:
    parts = []
    for i in range(mult):
        c = fact.copy()
        if i:
            for col in ("shipment_id", "order_id", "vehicle_id"):
                c[col] = c[col].astype(str) + f"_{i}"
        parts.append(c)
    return pd.concat(parts, ignore_index=True)


def test_sensitivity_prepares_trips_once(demo_wb, monkeypatch):
    """민감도 12개 시나리오가 파라미터 무관 집계(prepare_trips)를 1회만 계산한다 (이전: 12회)."""
    calls = []
    real = cost.prepare_trips
    monkeypatch.setattr(cost, "prepare_trips", lambda *a, **k: calls.append(1) or real(*a, **k))
    rows = A.sensitivity_view(demo_wb, CT.default_filters(demo_wb))
    assert len(rows) == 12 and len(calls) == 1


def test_scenario_compare_prepares_trips_once(demo_wb, monkeypatch):
    calls = []
    real = cost.prepare_trips
    monkeypatch.setattr(cost, "prepare_trips", lambda *a, **k: calls.append(1) or real(*a, **k))
    A.scenario_compare(demo_wb, CT.default_filters(demo_wb), cost.ScenarioParams(diesel_pct=10), cost.ScenarioParams(demand_pct=30))
    assert len(calls) == 1


def test_filter_positions_reused_across_views(demo_wb, monkeypatch):
    """같은 필터로 여러 화면 API 를 부르면 필터 마스크 계산은 1회 (나머지는 위치 캐시)."""
    calls = []
    real = kpi._filter_positions
    monkeypatch.setattr(kpi, "_filter_positions", lambda *a, **k: calls.append(1) or real(*a, **k))
    fact = demo_wb.fact.copy()  # 새 객체 = 빈 캐시
    flt = CT.default_filters(demo_wb)
    for _ in range(5):
        kpi.apply_filters(fact, flt)
    assert len(calls) == 1


def test_sensitivity_scales(demo_wb):
    """배송 ~4.9만 행(DEMO ×20) 민감도 — 개선 후 0.1초대(개선 전은 ×40 에서 15.8초 실측, ×20 은 그 절반 수준 추정). 상한은 넉넉하게 2초."""
    big = _scaled(demo_wb.fact, 20)
    t = time.perf_counter()
    cost.sensitivity(big, CT.default_filters(demo_wb), demo_wb.frames.get("vehicles"),
                     demo_wb.frames.get("fuel_prices"), demo_wb.external_diesel())
    assert time.perf_counter() - t < 2.0
