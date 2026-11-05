import pandas as pd

from logisrisk.config import FIXTURE_DIR
from logisrisk.data.validation import apply_mapping, auto_map, read_table, validate


def _v(entity, rows, refs=None):
    df = pd.DataFrame(rows).astype(str).replace({"None": ""})
    return validate(entity, df, refs)


def test_auto_map_korean_headers():
    cols = ["주문번호", "주문일자", "거래처코드", "출고센터", "납기일", "주문상태", "메모"]
    m = auto_map(cols, "orders")
    assert m == {"주문번호": "order_id", "주문일자": "order_date", "거래처코드": "store_id",
                 "출고센터": "warehouse_id", "납기일": "requested_date", "주문상태": "status"}


def test_missing_required_column_is_fatal():
    r = _v("orders", [{"order_id": "1", "order_date": "2026-01-01"}])
    assert not r.ok and "store_id" in r.fatal[0]
    assert r.n_valid == 0


def test_invalid_fixture_reports_exact_rows():
    p = FIXTURE_DIR / "DEMO_invalid_orders_for_validation.csv"
    raw = read_table(p.read_bytes(), p.name)
    df = apply_mapping(raw, auto_map(list(raw.columns), "orders"))
    stores = read_table((FIXTURE_DIR / "DEMO_stores.csv").read_bytes(), "s.csv")
    whs = read_table((FIXTURE_DIR / "DEMO_warehouses.csv").read_bytes(), "w.csv")
    r = validate("orders", df, {"stores": set(stores["store_id"]), "warehouses": set(whs["warehouse_id"])})
    codes = {(e.row, e.code) for e in r.errors.itertuples()}
    # 파일 행번호 = index + 2 (헤더 1행)
    assert (3, "type") in codes            # 날짜 형식 오류 (index 1)
    assert (4, "foreign_key") in codes     # 미존재 배송지 (index 2)
    assert (5, "duplicate") in codes and (6, "duplicate") in codes  # 중복키: 모든 중복 행
    assert (7, "enum") in codes            # 허용값 아님
    assert (8, "required") in codes        # 필수값 누락
    assert r.n_valid == 2 and r.n_error_rows == 6
    er = r.error_rows(raw)
    assert list(er["오류행번호"]) == [3, 4, 5, 6, 7, 8]


def test_numeric_range_and_commas():
    r = _v("vehicles", [
        {"vehicle_id": "V1", "home_warehouse_id": "W", "capacity_kg": "1,500", "fuel_efficiency_km_per_l": "5"},
        {"vehicle_id": "V2", "home_warehouse_id": "W", "capacity_kg": "-1", "fuel_efficiency_km_per_l": "5"},
        {"vehicle_id": "V3", "home_warehouse_id": "W", "capacity_kg": "abc", "fuel_efficiency_km_per_l": "5"},
    ])
    assert r.clean["capacity_kg"].tolist() == [1500.0]
    assert set(r.errors["code"]) == {"range", "type"}


def test_coordinates_swapped_zero_and_outside_warning():
    r = _v("stores", [
        {"store_id": "A", "name": "a", "lat": "37.5", "lon": "127.0"},
        {"store_id": "B", "name": "b", "lat": "127.0", "lon": "37.5"},  # 범위 초과(lat>90) → range
        {"store_id": "C", "name": "c", "lat": "0", "lon": "0"},
        {"store_id": "D", "name": "d", "lat": "40.7", "lon": "-74.0"},  # 해외 → 경고만
    ])
    assert set(r.clean["store_id"]) == {"A", "D"}
    assert any("범위 밖" in w for w in r.warnings)
    assert "coord" in set(r.errors["code"])


def test_swapped_lat_lon_within_valid_ranges():
    r = _v("warehouses", [{"warehouse_id": "W", "name": "w", "lat": "127.0", "lon": "37.5"}])
    assert r.n_valid == 0  # lat 127 → range 오류
    r2 = _v("warehouses", [{"warehouse_id": "W", "name": "w", "lat": "36.0", "lon": "36.5"}])
    assert r2.n_valid == 1 and r2.warnings  # 국내 범위 밖 경고


def test_shipment_date_logic():
    r = _v("shipments", [
        {"shipment_id": "1", "order_id": "O", "ship_date": "2026-01-05", "planned_delivery_date": "2026-01-06",
         "actual_delivery_date": "2026-01-04"},
        {"shipment_id": "2", "order_id": "O", "ship_date": "2026-01-05", "planned_delivery_date": "2026-01-06",
         "actual_delivery_date": "2026-01-06", "status": "delivered"},
        {"shipment_id": "3", "order_id": "O", "ship_date": "2026-01-05", "planned_delivery_date": "2026-01-06",
         "status": "delivered"},
    ])
    assert r.errors["code"].tolist() == ["date_logic"]
    assert r.n_valid == 2
    assert any("OTIF 분모" in w for w in r.warnings)


def test_outlier_is_warning_not_removed():
    rows = [{"shipment_id": str(i), "order_id": "O", "ship_date": "2026-01-01", "planned_delivery_date": "2026-01-02",
             "distance_km": "10"} for i in range(30)]
    rows[0]["distance_km"] = "5000"
    r = _v("shipments", rows)
    assert r.n_valid == 30 and any("이상치" in w for w in r.warnings)


def test_cp949_csv_and_excel_roundtrip(tmp_path):
    df = pd.DataFrame({"센터코드": ["W1"], "센터명": ["수원"], "위도": [37.2], "경도": [127.0]})
    b = df.to_csv(index=False).encode("cp949")
    assert read_table(b, "a.csv").iloc[0]["센터명"] == "수원"
    p = tmp_path / "a.xlsx"
    df.to_excel(p, index=False)
    x = read_table(p.read_bytes(), "a.xlsx")
    assert auto_map(list(x.columns), "warehouses") == {"센터코드": "warehouse_id", "센터명": "name", "위도": "lat", "경도": "lon"}


def test_id_leading_zeros_preserved():
    b = "store_id,name,lat,lon\n00123,a,37.5,127\n".encode()
    raw = read_table(b, "s.csv")
    r = validate("stores", raw)
    assert r.clean.iloc[0]["store_id"] == "00123"


def test_unsupported_file_type():
    import pytest
    with pytest.raises(ValueError):
        read_table(b"x", "a.json")
