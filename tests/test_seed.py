"""DEMO 자동 채우기: DEMO 워크스페이스만 채우고, 한 번만 실행되며, 저장 값이 엔진 계산과 일치하는지."""
import json

import pytest

from logisrisk.analytics import cost, kpi
from logisrisk.data.external import load_external
from logisrisk.data.seed import ensure_demo_seeded
from logisrisk.data.store import Store
from logisrisk.services import Workbench


@pytest.fixture(scope="module")
def seeded():
    s = Store("sqlite:///:memory:")
    ext = load_external()
    assert ensure_demo_seeded(s, ext) is True
    return s, ext


def test_only_demo_workspace_filled(seeded):
    s, _ = seeded
    assert s.data_versions(s.context_for("local", "default")) == {}
    assert s.list_scenarios(s.context_for("local", "default")).empty
    demo = s.context_for("local", "demo")
    assert all(v["demo"] for v in s.data_versions(demo).values())


def test_idempotent(seeded):
    s, ext = seeded
    c = s.context_for("local", "demo")
    n_sc, n_ac = len(s.list_scenarios(c)), len(s.list_actions(c))
    assert ensure_demo_seeded(s, ext) is False
    assert (len(s.list_scenarios(c)), len(s.list_actions(c))) == (n_sc, n_ac)


def test_work_items_present(seeded):
    s, _ = seeded
    c = s.context_for("local", "demo")
    sc = s.list_scenarios(c)
    assert {"cost_scenario", "warehouse_outage", "route_plan"} <= set(sc["kind"])
    assert {"approved", "proposed", "draft"} <= set(sc["status"])
    assert len(s.list_actions(c)) >= 2


def test_saved_numbers_match_engine(seeded):
    """저장된 시나리오 수치는 같은 데이터·필터로 엔진을 다시 돌린 값과 같아야 한다 (지어낸 값 없음)."""
    s, ext = seeded
    c = s.context_for("local", "demo")
    wb = Workbench.load(s, c, ext)
    sc = s.list_scenarios(c, "cost_scenario")
    rec = s.get_scenario(c, int(sc[sc["name"] == "경유가 +10%"]["id"].iloc[0]))
    b = wb.date_bounds()
    import pandas as pd
    flt = kpi.Filters(start=(b[1] - pd.Timedelta(days=29)).date(), end=b[1].date())
    r = cost.scenario_engine(wb.fact, flt, cost.ScenarioParams(name="경유가 +10%", diesel_pct=10),
                             wb.frames.get("vehicles"), wb.frames.get("fuel_prices"), wb.external_diesel())
    assert rec["result"]["scenario"]["total"] == pytest.approx(r["scenario"]["total"])
    assert json.dumps(rec["assumptions"], ensure_ascii=False) == json.dumps(r["assumptions"], ensure_ascii=False)


def test_viewer_cannot_seed():
    s = Store("sqlite:///:memory:")
    s.add_user("v1")
    s.grant("v1", "demo", "viewer")
    assert ensure_demo_seeded(s, load_external(), user_id="v1") is False
    assert s.data_versions(s.context_for("local", "demo")) == {}
