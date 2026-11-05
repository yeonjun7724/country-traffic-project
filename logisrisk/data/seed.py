"""DEMO 워크스페이스 자동 채우기.

첫 화면이 빈 상태로 보이지 않도록, DEMO 워크스페이스에 가상 데이터와 예시 작업물을 넣는다.
- 운영 데이터: fixtures/demo 의 DEMO_*.csv (일반 업로드와 같은 검증·저장 경로 사용)
- 예시 작업물: 비용 시나리오, 센터 중단 분석, 배송 계획 제안, 알림에서 만든 조치 항목.
  수치는 모두 위 가상 데이터로 실제 엔진을 돌려 계산하며, 직접 적어 넣은 값은 없다.

'내 워크스페이스'(실데이터용)는 건드리지 않는다. 여러 번 호출해도 한 번만 적재된다.
"""
from __future__ import annotations

import pandas as pd

from ..analytics import alerts, cost, inventory, kpi, routing
from ..services import Workbench
from .external import ExternalData
from .ingest import load_demo
from .store import Store

DEMO_WS = "demo"
SEED_KEY = "demo_seed_version"
SEED_VERSION = 1


def ensure_demo_seeded(store: Store, ext: ExternalData, user_id: str = "local") -> bool:
    """DEMO 워크스페이스가 비어 있으면 채운다. 새로 채웠으면 True."""
    try:
        ctx = store.context_for(user_id, DEMO_WS)
    except Exception:
        return False
    if not ctx.is_demo_workspace or ctx.role != "admin":
        return False
    loaded = False
    if not store.data_versions(ctx):
        load_demo(store, ctx)
        loaded = True
    if store.get_setting(ctx, SEED_KEY) == SEED_VERSION:
        return loaded
    wb = Workbench.load(store, ctx, ext)
    _seed_work_items(store, wb)
    store.set_setting(ctx, SEED_KEY, SEED_VERSION)
    return True


def _seed_work_items(store: Store, wb: Workbench):
    ctx = wb.ctx
    if wb.fact is None:
        return
    b = wb.date_bounds()
    flt = kpi.Filters(start=(b[1] - pd.Timedelta(days=29)).date(), end=b[1].date()) if b else kpi.Filters()
    args = (wb.frames.get("vehicles"), wb.frames.get("fuel_prices"), wb.external_diesel())

    # 1) 비용·운행 시나리오 (UI 'A·B 저장' 과 같은 형식)
    sids = []
    for p, status in ((cost.ScenarioParams(name="경유가 +10%", diesel_pct=10), "proposed"),
                      (cost.ScenarioParams(name="경유가 +10% · 수요 +30%", diesel_pct=10, demand_pct=30), "draft"),
                      (cost.ScenarioParams(name="운송단가 +5% · 차량 -2대", rate_pct=5, fleet_change=-2), "draft")):
        r = cost.scenario_engine(wb.fact, flt, p, *args)
        if r.get("status") != "ok":
            continue
        sids.append(store.save_scenario(ctx, p.name, "cost_scenario", {**p.to_dict(), "filters": flt.describe()},
                                        {k: v for k, v in r.items() if k != "assumptions"}, r["assumptions"],
                                        wb.versions, status=status))
    if sids:
        store.set_scenario_status(ctx, sids[0], "approved", "예시: 운영 관리자 승인")

    # 2) 센터 중단 분석
    whs = wb.options("warehouse_id")
    if whs:
        r = cost.warehouse_outage(wb.frames, whs[0], flt=flt)
        if r.get("status") == "ok":
            store.save_scenario(ctx, f"센터 중단 {whs[0]}", "warehouse_outage", {"warehouse_id": whs[0]},
                                {"stores": r["stores"].to_dict(orient="records"),
                                 "capacity": r["capacity"].to_dict(orient="records")}, r["assumptions"], wb.versions)

    # 3) 배송 계획 제안 (납기일 기준 미출고 주문)
    days = routing.planning_days(wb.frames, wb.fact, "orders")
    if days and whs:
        day = days[-1]
        params = routing.RoutingParams()
        for wid in whs:
            depot, stops, _, veh = routing.build_day_inputs(wb.frames, wb.fact, day, wid, source="orders")
            if stops.empty or veh is None or veh.empty:
                continue
            prop = routing.plan_routes(depot, stops, veh, params)
            store.save_scenario(
                ctx, f"배송계획 {pd.Timestamp(day).date()} {wid}", "route_plan",
                {"date": str(pd.Timestamp(day).date()), "warehouse_id": wid, **params.to_dict()},
                {"summary_proposed": prop.summary, "summary_baseline": None, "source": "orders",
                 "comparison": [prop.summary], "routes": prop.routes.to_dict(orient="records"),
                 "stops": prop.stops.to_dict(orient="records"), "unassigned": prop.unassigned.to_dict(orient="records"),
                 "violations": prop.violations},
                prop.warnings, wb.versions, status="proposed")
            break

    # 4) 알림 → 조치 항목 (Reports 화면 '조치 생성' 과 같은 경로)
    ms = kpi.compute_with_comparison(wb.frames, wb.fact, flt, wb.targets)
    inv = inventory.replenishment(wb.frames) if "inventory" in wb.frames else None
    fired = alerts.evaluate(ms, wb.rules, wb.versions, inv, period_days=flt.days)
    aids = [store.create_action(ctx, f"[{a['rule']}] {a['message']}", f"알림:{a['source']}", flt.describe())
            for a in fired[:4]]
    aids.append(store.create_action(ctx, "경유가 +10% 시나리오 기준 4분기 운송 예산 재검토", "시나리오:경유가 +10%"))
    for aid, (status, owner) in zip(aids, (("in_progress", "운영팀"), ("open", None), ("done", "물류기획"))):
        if status != "open":
            store.set_action_status(ctx, aid, status, owner)
