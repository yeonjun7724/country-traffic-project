"""AI Copilot 도구 (읽기 전용 · 권한 검사 · 출처 메타데이터 포함).

- 모든 도구는 Workbench(사용자 컨텍스트)를 통해서만 데이터에 접근 → 워크스페이스 격리·권한이 AI 레벨에서도 강제됨.
- 쓰기 작업(배차 확정·데이터 변경·외부 발송) 도구는 제공하지 않는다.
- 반환값은 JSON 직렬화 가능한 dict: {tool, as_of, scope, data_versions, filters, assumptions, result}
"""
from __future__ import annotations

import math
import re
from datetime import date, datetime

import numpy as np
import pandas as pd

from ..analytics import cost, inventory, kpi, risk, routing
from ..config import REFERENCE_EVENT_DATE
from ..security import PermissionDenied, require
from ..services import Workbench

DIMENSIONS = {"store_id": "배송지(거래처)", "carrier": "운송사", "vehicle_id": "차량", "region": "권역",
              "warehouse_id": "센터", "customer_group": "거래처군"}
MAX_ROWS = 15


def _clean(o):
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, pd.DataFrame):
        return _clean(o.head(MAX_ROWS).to_dict(orient="records"))
    if isinstance(o, (pd.Timestamp, datetime, date)):
        return str(o)[:10] if isinstance(o, (pd.Timestamp,)) and o == o.normalize() else str(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating, float)):
        f = float(o)
        return None if math.isnan(f) or math.isinf(f) else round(f, 4)
    if isinstance(o, np.bool_):
        return bool(o)
    if o is pd.NaT or o is pd.NA:
        return None
    return o


def _date(s: str | None):
    if not s:
        return None
    try:
        return pd.Timestamp(s).date()
    except Exception:
        raise ValueError(f"날짜 형식 오류: {s} (YYYY-MM-DD)")


def _filters(wb: Workbench, a: dict) -> kpi.Filters:
    start, end = _date(a.get("start")), _date(a.get("end"))
    if start is None and end is None:
        b = wb.date_bounds()
        if b:  # 기본: 데이터 마지막 30일
            end = b[1].date()
            start = (b[1] - pd.Timedelta(days=29)).date()
    f = kpi.Filters(start=start, end=end)
    for key, attr in (("warehouse_id", "warehouses"), ("region", "regions"), ("carrier", "carriers"),
                      ("vehicle_id", "vehicles"), ("store_id", "stores"), ("category", "categories")):
        v = a.get(key)
        if v:
            setattr(f, attr, [v] if isinstance(v, str) else list(v))
    return f


def _wrap(wb: Workbench, tool: str, result, *, scope="internal", flt: kpi.Filters | None = None,
          assumptions: list[str] | None = None, kind="observed"):
    return _clean({
        "tool": tool, "as_of": datetime.now().isoformat(timespec="seconds"),
        "scope": "기업 업로드 데이터" if scope == "internal" else "외부 위험 지표(고속도로·유가, 기업 실적 아님)",
        "data_kind": kind, "demo_data": wb.is_demo if scope == "internal" else False,
        "data_versions": wb.versions if scope == "internal" else {k: v.to_dict() for k, v in wb.ext.provenance.items()},
        "filters": flt.describe() if flt else None, "assumptions": assumptions or [], "result": result})


def _need_ops(wb: Workbench, *entities):
    miss = [e for e in entities if e not in wb.frames]
    if miss:
        return {"status": "not_computable", "reason": f"필요 데이터 미업로드: {', '.join(miss)} (Data Hub 에서 업로드)"}
    return None


# ── 도구 구현 ──────────────────────────────────────────────────────────────
def t_get_kpis(wb, a):
    flt = _filters(wb, a)
    if (e := _need_ops(wb, "orders")) and "shipments" not in wb.frames:
        return _wrap(wb, "get_kpis", e, flt=flt)
    ms = kpi.compute_with_comparison(wb.frames, wb.fact, flt, wb.targets)
    res = {k: {"label": m.label, "value": m.value if m.ok else None, "unit": m.unit,
               "status": m.status, "reason": m.reason, "formula": m.formula, "n": m.n,
               "previous_period_value": m.previous, "delta_pct": m.delta_pct, "target": m.target,
               "warnings": m.warnings} for k, m in ms.items()}
    return _wrap(wb, "get_kpis", res, flt=flt, assumptions=["직전기간 = 선택 기간과 같은 길이의 바로 앞 기간"])


def t_cost_change_ranking(wb, a):
    dim = a.get("dimension", "store_id")
    if dim not in DIMENSIONS:
        raise ValueError(f"dimension 은 {list(DIMENSIONS)} 중 하나")
    flt = _filters(wb, a)
    if e := _need_ops(wb, "shipments", "orders"):
        return _wrap(wb, "cost_change_ranking", e, flt=flt)
    t = kpi.cost_change_by(wb.fact, flt, dim)
    if t.empty:
        return _wrap(wb, "cost_change_ranking", {"status": "not_computable", "reason": "비교 기간 데이터 없음"}, flt=flt)
    if dim == "store_id" and "stores" in wb.frames:
        t = t.merge(wb.frames["stores"][["store_id", "name"]], on="store_id", how="left")
    n = int(a.get("top_n", 5))
    return _wrap(wb, "cost_change_ranking",
                 {"dimension": DIMENSIONS[dim], "previous_period": f"{flt.shifted().start}~{flt.shifted().end}",
                  "top_increase": t.head(n), "top_decrease": t.tail(n).iloc[::-1]}, flt=flt)


def t_late_delivery_by(wb, a):
    dim = a.get("dimension", "region")
    if dim not in DIMENSIONS:
        raise ValueError(f"dimension 은 {list(DIMENSIONS)} 중 하나")
    flt = _filters(wb, a)
    if e := _need_ops(wb, "shipments"):
        return _wrap(wb, "late_delivery_by", e, flt=flt)
    t = kpi.by_dimension(wb.fact, flt, dim)
    if t.empty:
        return _wrap(wb, "late_delivery_by", {"status": "not_computable", "reason": "대상 배송 없음"}, flt=flt)
    t = t[t["on_time_n"] > 0].sort_values(["late_rate", "late"], ascending=False)
    return _wrap(wb, "late_delivery_by", {"dimension": DIMENSIONS[dim],
                                          "table": t[[dim, "shipments", "on_time_n", "late", "late_rate"]],
                                          "map_hint": "Control Tower 또는 Network 화면 지도에서 지연율 레이어로 확인"},
                 flt=flt, assumptions=["지연 = 실제 배송일 > 약속 배송일. 실제 배송일 없는 건은 분모 제외"])


def t_diesel_cost_scenario(wb, a):
    pct = float(a.get("diesel_pct", 10))
    if not -90 <= pct <= 300:
        raise ValueError("diesel_pct 범위 -90~300")
    by = a.get("by", "vehicle_id")
    flt = _filters(wb, a)
    if e := _need_ops(wb, "shipments"):
        return _wrap(wb, "diesel_cost_scenario", e, flt=flt)
    r = cost.diesel_sensitivity(wb.fact, flt, [pct], wb.frames.get("fuel_prices"), wb.external_diesel(), by=by)
    return _wrap(wb, "diesel_cost_scenario", {k: v for k, v in r.items() if k != "assumptions"}, flt=flt,
                 assumptions=r["assumptions"], kind="assumption")


def t_scenario_compare(wb, a):
    flt = _filters(wb, a)
    if e := _need_ops(wb, "shipments"):
        return _wrap(wb, "scenario_compare", e, flt=flt)
    p = cost.ScenarioParams(name="AI 질의", diesel_pct=float(a.get("diesel_pct", 0)),
                            demand_pct=float(a.get("demand_pct", 0)), rate_pct=float(a.get("rate_pct", 0)),
                            fleet_change=int(a.get("fleet_change", 0)))
    r = cost.scenario_engine(wb.fact, flt, p, wb.frames.get("vehicles"), wb.frames.get("fuel_prices"), wb.external_diesel())
    return _wrap(wb, "scenario_compare", {k: v for k, v in r.items() if k != "assumptions"}, flt=flt,
                 assumptions=r.get("assumptions", []), kind="assumption")


def t_capacity_check(wb, a):
    if e := _need_ops(wb, "warehouses", "stores", "vehicles", "orders"):
        return _wrap(wb, "capacity_check", e)
    note = []
    day = _date(a.get("date"))
    open_days = routing.planning_days(wb.frames, wb.fact, "orders")
    if day is None:
        if open_days:
            day = pd.Timestamp(open_days[0]).date()
            note.append(f"일자 미지정 → 미출고 주문의 가장 이른 납기일({day}) 기준")
        elif wb.fact is not None:
            day = wb.fact["ship_date"].max().date()
            note.append(f"미출고 주문 없음 → 최신 출고일({day}) 실적을 재계획해 검토")
        else:
            return _wrap(wb, "capacity_check", {"status": "not_computable", "reason": "계획할 주문·배송 데이터 없음"})
    source = "orders" if any(pd.Timestamp(d) == pd.Timestamp(day) for d in open_days) else "shipments"
    if source == "shipments" and wb.fact is None:
        return _wrap(wb, "capacity_check", {"status": "not_computable", "reason": f"{day} 납기 미출고 주문 없음"})
    wid = resolve_warehouse(wb, a.get("warehouse_id"))
    if wid is None:
        return _wrap(wb, "capacity_check", {"status": "not_computable", "reason": f"센터 '{a.get('warehouse_id')}' 를 찾을 수 없음"})
    if not a.get("warehouse_id"):
        cands = [w for w in wb.options("warehouse_id")
                 if not routing.build_day_inputs(wb.frames, wb.fact, day, w, source=source)[1].empty]
        if cands:
            wid = cands[0]
        note.append(f"센터 미지정 → {wid} 기준 (다른 센터: {', '.join(c for c in cands if c != wid) or '없음'})")
    note.append("계획 대상: " + ("해당일 납기 미출고 주문" if source == "orders" else "해당일 출고 실적 재계획"))
    depot, stops, assign, veh = routing.build_day_inputs(wb.frames, wb.fact, day, wid, source=source)
    if stops.empty:
        return _wrap(wb, "capacity_check", {"status": "not_computable",
                                            "reason": f"{day} {wid} 계획 대상 주문·배송이 없습니다."})
    price = _price_for(wb, day)
    pr = routing.plan_routes(depot, stops, veh, routing.RoutingParams(diesel_price=price))
    return _wrap(wb, "capacity_check", {"date": str(day), "warehouse_id": wid, "available_vehicles": len(veh),
                                        "summary": pr.summary, "violations": pr.violations,
                                        "unassigned": pr.unassigned, "routes": pr.routes},
                 assumptions=note + pr.warnings + ["1차량 1회전 가정", f"비용 산정 경유가 {price}원/L" if price else "경유가 없음 → 연료비 미산정"],
                 kind="simulated")


def _price_for(wb, day):
    fp = wb.frames.get("fuel_prices")
    if fp is not None and len(fp):
        x = fp[fp["date"] <= pd.Timestamp(day)].sort_values("date")
        if len(x):
            return float(x["diesel_price"].iloc[-1])
    ed = wb.external_diesel()
    if ed is not None:
        x = ed[ed["date"] <= pd.Timestamp(day)]
        if len(x) and (pd.Timestamp(day) - x["date"].iloc[-1]).days <= 7:
            return float(x["diesel_price"].iloc[-1])
    return None


def resolve_warehouse(wb, key: str | None) -> str | None:
    """센터 ID 또는 이름(부분 일치)으로 해석. 미지정이면 첫 센터."""
    ids = wb.options("warehouse_id")
    if not key:
        return ids[0] if ids else None
    if key in ids:
        return key
    wh = wb.frames.get("warehouses")
    if wh is not None:
        k = str(key).strip().lower()
        m = wh[wh["warehouse_id"].str.lower().str.endswith(k) | wh["name"].str.lower().str.contains(k, regex=False)]
        if len(m) == 1:
            return m.iloc[0]["warehouse_id"]
    return None


def find_warehouse_in_text(wb, text: str) -> str | None:
    """질문 문장 안의 센터 ID·이름(‘센터’·‘DEMO’ 등 제거한 핵심어) 탐색. 정확히 1개일 때만 반환."""
    wh = wb.frames.get("warehouses")
    if wh is None:
        return None
    hits = set()
    for r in wh.itertuples():
        core = re.sub(r"(DEMO|물류센터|센터|창고|\s)", "", str(r.name))
        for cand in (str(r.warehouse_id), str(r.name), core):
            if len(cand) >= 2 and cand in text:
                hits.add(r.warehouse_id)
    return hits.pop() if len(hits) == 1 else None


def t_warehouse_outage(wb, a):
    if not a.get("warehouse_id"):
        raise ValueError("warehouse_id 필요")
    wid = resolve_warehouse(wb, a.get("warehouse_id"))
    if wid is None:
        return _wrap(wb, "warehouse_outage", {"status": "not_computable",
                                              "reason": f"센터 '{a.get('warehouse_id')}' 를 ID·이름으로 특정할 수 없습니다. "
                                                        f"가능한 센터: {', '.join(wb.options('warehouse_id'))}"})
    r = cost.warehouse_outage(wb.frames, wid)
    return _wrap(wb, "warehouse_outage", {k: v for k, v in r.items() if k != "assumptions"},
                 assumptions=r.get("assumptions", []), kind="simulated")


def t_inventory_risk(wb, a):
    r = inventory.replenishment(wb.frames, service_level=float(a.get("service_level", 0.95)))
    if r["status"] != "ok":
        return _wrap(wb, "inventory_risk", r)
    t = r["table"]
    t = t[t["stockout_risk"].isin(["결품", "높음"])]
    return _wrap(wb, "inventory_risk", {"snapshot_date": r["snapshot_date"], "summary": r["summary"],
                                        "at_risk": t.head(int(a.get("top_n", 10)))},
                 assumptions=r["assumptions"], kind="derived")


def t_external_risk_units(wb, a):
    u = wb.ext.units
    if u is None:
        return _wrap(wb, "external_risk_units", {"status": "not_computable", "reason": "외부 영업소 파일 없음"}, scope="external")
    x = u if not a.get("route") else u[u["routeName"].str.contains(str(a["route"]), na=False)]
    x = x.sort_values("vulnerability_score", ascending=False)
    cols = ["unitCode", "unitName", "routeName", "vulnerability_score", "vulnerability_grade", "lisa_cluster"]
    return _wrap(wb, "external_risk_units", {"population": len(u), "matched": len(x),
                                             "top": x[cols].head(int(a.get("top_n", 10))),
                                             "hh_cluster_count": int((u["lisa_cluster"] == "High-High").sum())},
                 scope="external", kind="derived",
                 assumptions=["취약성 = 0.3·화물비율 + 0.3·화물량 + 0.2·변동계수 + 0.2·불균형 (min-max 정규화)",
                              "Fuel Shock Impact Score 는 취약성 × 상수(전 영업소 동일 Shock Index) 이므로 순위가 취약성과 동일"])


def t_external_fuel_status(wb, a):
    h, f = wb.ext.fuel_history, wb.ext.forecast
    if h is None:
        return _wrap(wb, "external_fuel_status", {"status": "not_computable"}, scope="external")
    res = {"last_observed_date": h["date"].max(), "last_diesel_price": float(h["diesel_price"].iloc[-1]),
           "diesel_30d_ago": float(h["diesel_price"].iloc[-31]) if len(h) > 31 else None,
           "wti_last": float(h["wti"].iloc[-1])}
    if f is not None:
        res["forecast_period"] = f"{f['date'].min().date()}~{f['date'].max().date()}"
        res["forecast_is_stale"] = bool(f["date"].max() < pd.Timestamp(datetime.now().date()))
        res["forecast_ensemble_mean"] = float(f["diesel_price_ensemble"].mean())
    return _wrap(wb, "external_fuel_status", res, scope="external", kind="observed",
                 assumptions=["외부 전국 평균 유가이며 기업 구매 단가가 아님", "예측은 저장된 산출물이며 재학습하지 않음"])


def t_traffic_event_comparison(wb, a):
    t = wb.ext.traffic
    if t is None:
        return _wrap(wb, "traffic_event_comparison", {"status": "not_computable"}, scope="external")
    r = risk.period_comparison(t, REFERENCE_EVENT_DATE)
    return _wrap(wb, "traffic_event_comparison", r, scope="external", kind="observed",
                 assumptions=[r.get("caveat", "")])


def t_list_saved_scenarios(wb, a):
    s = wb.store.list_scenarios(wb.ctx)
    return _wrap(wb, "list_saved_scenarios", {"scenarios": s.head(20) if len(s) else []})


TOOLS = {
    "get_kpis": (t_get_kpis, "기간·센터·권역·운송사 필터로 물류 KPI(주문수, 운송비, 지연율, OTIF, 적재율, km당·주문당 운송비)와 직전기간 대비를 조회",
                 {"start": "str", "end": "str", "warehouse_id": "str", "region": "str", "carrier": "str"}),
    "cost_change_ranking": (t_cost_change_ranking, "직전 동일 길이 기간 대비 운송비 증감 순위 (거래처·운송사·차량·권역·센터별)",
                            {"dimension": "str", "start": "str", "end": "str", "top_n": "int"}),
    "late_delivery_by": (t_late_delivery_by, "권역·배송지·운송사별 배송 지연율",
                         {"dimension": "str", "start": "str", "end": "str"}),
    "diesel_cost_scenario": (t_diesel_cost_scenario, "경유가 변화율(%)에 따른 연료비 변화 (차량·운송사·배송지별)",
                             {"diesel_pct": "number", "by": "str", "start": "str", "end": "str"}),
    "scenario_compare": (t_scenario_compare, "경유가·운송단가·물동량·차량 증감 복합 시나리오의 Baseline 대비 총비용·운행·차량 부족 추정",
                         {"diesel_pct": "number", "rate_pct": "number", "demand_pct": "number", "fleet_change": "int",
                          "start": "str", "end": "str"}),
    "capacity_check": (t_capacity_check, "특정 일자·센터의 배송 수요를 현재 가용 차량으로 처리 가능한지 CVRP 휴리스틱으로 검토",
                       {"date": "str", "warehouse_id": "str"}),
    "warehouse_outage": (t_warehouse_outage, "센터 중단 시 배송지별 대체 센터(직선거리)와 처리용량 검토", {"warehouse_id": "str"}),
    "inventory_risk": (t_inventory_risk, "재고 부족(결품·재주문점 이하) 위험 SKU 와 보충 추천", {"top_n": "int", "service_level": "number"}),
    "external_risk_units": (t_external_risk_units, "[외부] 고속도로 영업소 취약성·LISA 클러스터 상위 목록", {"top_n": "int", "route": "str"}),
    "external_fuel_status": (t_external_fuel_status, "[외부] 전국 평균 경유가 최근값과 저장된 예측의 기간·최신성", {}),
    "traffic_event_comparison": (t_traffic_event_comparison, "[외부] 기준 이벤트 전후 전국 화물 교통량 관측 비교(인과 아님)", {}),
    "list_saved_scenarios": (t_list_saved_scenarios, "저장된 시나리오 목록", {}),
}


def openai_tool_specs() -> list[dict]:
    specs = []
    for name, (_, desc, params) in TOOLS.items():
        props = {}
        for p, typ in params.items():
            js = {"str": "string", "int": "integer", "number": "number"}[typ]
            props[p] = {"type": js}
            if p == "dimension":
                props[p]["enum"] = list(DIMENSIONS)
            if p == "by":
                props[p]["enum"] = ["vehicle_id", "carrier", "store_id", "region", "warehouse_id"]
            if p in ("start", "end", "date"):
                props[p]["description"] = "YYYY-MM-DD"
        specs.append({"type": "function", "function": {"name": name, "description": desc,
                                                        "parameters": {"type": "object", "properties": props}}})
    return specs


def run_tool(wb: Workbench, name: str, args: dict) -> dict:
    require(wb.ctx, "data.read")
    require(wb.ctx, "ai.use")
    if name not in TOOLS:
        return {"tool": name, "error": "알 수 없는 도구"}
    try:
        return TOOLS[name][0](wb, args or {})
    except PermissionDenied:
        raise
    except Exception as e:  # 도구 실패는 오류 객체로 반환 (모델이 수치를 지어내지 않도록)
        return {"tool": name, "error": f"{type(e).__name__}: {e}"}
