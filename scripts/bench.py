"""성능 기준 측정 — 계산 경로(대용량 포함)와 선택적으로 실행 중인 API.

사용:
  .venv/Scripts/python.exe scripts/bench.py                 # 계산 경로: DEMO ×1, ×40 (≈9.7만 배송)
  .venv/Scripts/python.exe scripts/bench.py --scale 1 10 40
  .venv/Scripts/python.exe scripts/bench.py --api http://127.0.0.1:8600   # 실행 중인 서버의 엔드포인트별 p50/max/전송량

주의
- 대용량은 DEMO 팩트를 메모리에서 복제(배송·주문·차량 ID 에 접미사)한 것이다. 운행 수가 실제 분포보다 많을 수 있어
  절대값보다 '전후 비교' 용도. 기준값과 목표는 docs/IMPROVEMENT_PLAN.md.
- 로컬 API 측정은 127.0.0.1 을 쓴다 (Windows 에서 localhost 는 IPv6 폴백으로 요청마다 ~2초 추가).
- 저장소를 변경하지 않는다 (DEMO 워크스페이스가 비어 있으면 fixtures/demo 를 임시 메모리 DB 에 적재).
"""
from __future__ import annotations

import argparse
import gzip
import statistics
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

API_PATHS = [
    "/api/me", "/api/filters", "/api/control-tower/overview", "/api/control-tower/daily", "/api/control-tower/network",
    "/api/control-tower/ledger", "/api/network/units", "/api/transportation/cts", "/api/transportation/fuel",
    "/api/inventory/replenishment", "/api/fuel/market", "/api/scenarios/sensitivity", "/api/reports/preview",
    "/api/reports/excel", "/api/alerts", "/api/data/quality",
]


def _timeit(fn, repeat: int = 3) -> float:
    ts = []
    for _ in range(repeat):
        s = time.perf_counter()
        fn()
        ts.append((time.perf_counter() - s) * 1000)
    return statistics.median(ts)


def bench_compute(scales: list[int]) -> None:
    import pandas as pd

    from logisrisk.analytics import cost
    from logisrisk.data.external import load_external
    from logisrisk.data.ingest import load_demo
    from logisrisk.data.store import Store
    from logisrisk.services import Workbench
    from logisrisk.views import analysis as A
    from logisrisk.views import control_tower as CT

    store = Store("sqlite://")
    ctx = store.context_for("local", "demo")
    load_demo(store, ctx)
    wb = Workbench.load(store, ctx, load_external())
    base = wb.fact
    flt = CT.default_filters(wb)
    print(f"{'rows':>8}  {'path':28} {'ms':>9}")
    for mult in scales:
        parts = []
        for i in range(mult):
            c = base.copy()
            for col in ("shipment_id", "order_id", "vehicle_id"):
                if col in c and i:
                    c[col] = c[col].astype(str) + f"_{i}"
            parts.append(c)
        wb.fact = pd.concat(parts, ignore_index=True) if mult > 1 else base
        n = len(wb.fact)
        rows = [
            ("overview (KPI+직전)", lambda: CT.overview(wb, flt)),
            ("daily", lambda: CT.daily(wb, flt)),
            ("network", lambda: CT.network(wb, flt)),
            ("ledger(late)", lambda: CT.ledger(wb, flt, "late")),
            ("scenario_compare (A/B)", lambda: A.scenario_compare(wb, flt, cost.ScenarioParams(diesel_pct=10),
                                                                  cost.ScenarioParams(diesel_pct=10, demand_pct=30))),
            ("sensitivity (12 시나리오)", lambda: A.sensitivity_view(wb, flt)),
        ]
        for label, fn in rows:
            print(f"{n:>8,}  {label:28} {_timeit(fn, 1 if mult >= 20 else 3):9.0f}")
    wb.fact = base


def bench_api(base_url: str, workspace: str) -> None:
    import http.cookiejar

    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def get(path):
        req = urllib.request.Request(base_url + path, headers={"X-Workspace": workspace, "Accept-Encoding": "gzip"})
        s = time.perf_counter()
        with op.open(req) as r:
            body = r.read()
            enc = r.headers.get("Content-Encoding")
        return (time.perf_counter() - s) * 1000, len(body), len(gzip.decompress(body)) if enc == "gzip" else len(body)

    get("/api/auth/status")
    print(f"{'endpoint':38} {'p50':>7} {'max':>7} {'wire':>9} {'raw':>9}")
    for p in API_PATHS:
        get(p)  # 워밍업
        runs = [get(p) for _ in range(6)]
        ts = sorted(r[0] for r in runs)
        print(f"{p:38} {statistics.median(ts):7.0f} {ts[-1]:7.0f} {runs[0][1]:9,} {runs[0][2]:9,}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scale", type=int, nargs="+", default=[1, 40])
    ap.add_argument("--api", help="실행 중인 서버 주소 (예: http://127.0.0.1:8600). 지정 시 API 만 측정")
    ap.add_argument("--workspace", default="demo")
    a = ap.parse_args()
    if a.api:
        bench_api(a.api.rstrip("/"), a.workspace)
    else:
        bench_compute(a.scale)


if __name__ == "__main__":
    main()
