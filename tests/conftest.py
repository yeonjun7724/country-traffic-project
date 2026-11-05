import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from logisrisk.data.schemas import ENTITIES  # noqa: E402
from logisrisk.data.store import Store  # noqa: E402


def mk(entity: str, rows: list[dict]) -> pd.DataFrame:
    """스키마 전체 컬럼을 갖춘 프레임 (누락 = NaN, 날짜 = datetime)."""
    spec = ENTITIES[entity]
    df = pd.DataFrame(rows)
    for f in spec.fields:
        if f.name not in df:
            df[f.name] = np.nan
        if f.type == "date":
            df[f.name] = pd.to_datetime(df[f.name])
        elif f.type in ("float", "int"):
            df[f.name] = pd.to_numeric(df[f.name]).astype(float)
    return df[spec.field_names]


@pytest.fixture
def mini_frames():
    """손으로 검산 가능한 소규모 데이터 (기대값은 test_kpi 주석 참조)."""
    return {
        "warehouses": mk("warehouses", [{"warehouse_id": "W1", "name": "센터1", "lat": 37.5, "lon": 127.0, "daily_capacity_orders": 10},
                                        {"warehouse_id": "W2", "name": "센터2", "lat": 35.1, "lon": 129.0, "daily_capacity_orders": 4}]),
        "stores": mk("stores", [{"store_id": "S1", "name": "점포1", "lat": 37.55, "lon": 127.05, "region": "수도권"},
                                {"store_id": "S2", "name": "점포2", "lat": 37.40, "lon": 126.90, "region": "수도권"},
                                {"store_id": "S3", "name": "점포3", "lat": 35.20, "lon": 129.10, "region": "영남"}]),
        "skus": mk("skus", [{"sku_id": "K1", "name": "상품1", "category": "A", "unit_weight_kg": 2.0},
                            {"sku_id": "K2", "name": "상품2", "category": "B", "unit_weight_kg": 10.0}]),
        "vehicles": mk("vehicles", [{"vehicle_id": "V1", "home_warehouse_id": "W1", "carrier": "C1", "capacity_kg": 100,
                                     "fuel_efficiency_km_per_l": 5, "fixed_cost_per_day": 1000, "variable_cost_per_km": 10},
                                    {"vehicle_id": "V2", "home_warehouse_id": "W1", "carrier": "C2", "capacity_kg": 50,
                                     "fuel_efficiency_km_per_l": 10, "fixed_cost_per_day": 500, "variable_cost_per_km": 5}]),
        "orders": mk("orders", [{"order_id": "O1", "order_date": "2026-01-01", "store_id": "S1", "warehouse_id": "W1"},
                                {"order_id": "O2", "order_date": "2026-01-02", "store_id": "S2", "warehouse_id": "W1"},
                                {"order_id": "O3", "order_date": "2026-01-03", "store_id": "S1", "warehouse_id": "W1"}]),
        "order_lines": mk("order_lines", [{"order_id": "O1", "sku_id": "K1", "qty": 10},
                                          {"order_id": "O2", "sku_id": "K1", "qty": 5},
                                          {"order_id": "O3", "sku_id": "K2", "qty": 2}]),
        "shipments": mk("shipments", [
            {"shipment_id": "H1", "order_id": "O1", "vehicle_id": "V1", "ship_date": "2026-01-01", "planned_delivery_date": "2026-01-02",
             "actual_delivery_date": "2026-01-02", "delivered_qty": 10, "distance_km": 10, "fuel_l": 2, "fuel_cost": 40, "total_cost": 100},
            {"shipment_id": "H2", "order_id": "O2", "vehicle_id": "V1", "ship_date": "2026-01-01", "planned_delivery_date": "2026-01-02",
             "actual_delivery_date": "2026-01-03", "delivered_qty": 5, "distance_km": 30, "fuel_l": 6, "fuel_cost": 120, "total_cost": 200},
            {"shipment_id": "H3", "order_id": "O3", "vehicle_id": "V2", "ship_date": "2026-01-03", "planned_delivery_date": "2026-01-04",
             "actual_delivery_date": "2026-01-04", "delivered_qty": 1, "distance_km": 20, "total_cost": 300},
        ]),
    }


@pytest.fixture
def store():
    return Store("sqlite:///:memory:")


@pytest.fixture(scope="session")
def demo_store(tmp_path_factory):
    from logisrisk.data.ingest import load_demo
    p = tmp_path_factory.mktemp("db") / "demo.db"
    s = Store(f"sqlite:///{p.as_posix()}")
    load_demo(s, s.context_for("local", "demo"))
    return s, p


@pytest.fixture(scope="session")
def demo_wb(demo_store):
    from logisrisk.data.external import load_external
    from logisrisk.services import Workbench
    s, _ = demo_store
    return Workbench.load(s, s.context_for("local", "demo"), load_external())
