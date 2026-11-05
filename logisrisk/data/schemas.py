"""운영 데이터 도메인 스키마 (업로드·검증·저장의 단일 진실 원천).

- 각 엔터티: 기본키, 필드(타입·필수·단위·허용값·별칭), 외래키.
- 별칭(aliases)은 자동 컬럼 매핑에 사용 (한글/영문/약어).
- 고속도로 영업소(외부 위험 데이터)는 여기 포함되지 않는다: 기업 거점과 별도 엔터티.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

FieldType = Literal["str", "int", "float", "date", "bool", "time"]


@dataclass(frozen=True)
class FieldSpec:
    name: str
    type: FieldType
    required: bool = False
    label: str = ""
    unit: str = ""
    aliases: tuple[str, ...] = ()
    allowed: tuple[str, ...] | None = None
    min: float | None = None
    max: float | None = None
    description: str = ""


@dataclass(frozen=True)
class ForeignKey:
    column: str
    ref_entity: str
    ref_column: str


@dataclass(frozen=True)
class EntitySpec:
    name: str
    label: str
    primary_key: tuple[str, ...]
    fields: tuple[FieldSpec, ...]
    foreign_keys: tuple[ForeignKey, ...] = ()
    description: str = ""
    coord_fields: tuple[str, str] | None = None  # (lat, lon)

    @property
    def field_names(self) -> list[str]:
        return [f.name for f in self.fields]

    @property
    def required_fields(self) -> list[str]:
        return [f.name for f in self.fields if f.required]

    def field(self, name: str) -> FieldSpec:
        for f in self.fields:
            if f.name == name:
                return f
        raise KeyError(name)


ORDER_STATUSES = ("created", "allocated", "picked", "shipped", "delivered", "cancelled")
SHIPMENT_STATUSES = ("planned", "dispatched", "in_transit", "delivered", "failed", "cancelled")

# 주문 상태 전이 (현재 → 허용되는 다음 상태)
ORDER_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "created": ("allocated", "picked", "cancelled"),
    "allocated": ("picked", "cancelled"),
    "picked": ("shipped", "cancelled"),
    "shipped": ("delivered",),
    "delivered": (),
    "cancelled": (),
}

F = FieldSpec

WAREHOUSES = EntitySpec(
    name="warehouses", label="물류센터(창고)", primary_key=("warehouse_id",),
    coord_fields=("lat", "lon"),
    description="출고 거점. 고속도로 영업소와는 별개 엔터티.",
    fields=(
        F("warehouse_id", "str", True, "센터ID", aliases=("센터id", "센터코드", "창고코드", "창고id", "dc_id", "wh_id", "warehouse")),
        F("name", "str", True, "센터명", aliases=("센터명", "창고명", "warehouse_name")),
        F("lat", "float", True, "위도", "deg", ("위도", "latitude", "y", "yvalue"), min=-90, max=90),
        F("lon", "float", True, "경도", "deg", ("경도", "longitude", "lng", "x", "xvalue"), min=-180, max=180),
        F("region", "str", False, "권역", aliases=("권역", "지역", "시도")),
        F("daily_capacity_orders", "float", False, "일 처리용량", "주문/일", ("처리용량", "capacity"), min=0),
    ),
)

STORES = EntitySpec(
    name="stores", label="배송지(점포·거래처)", primary_key=("store_id",),
    coord_fields=("lat", "lon"),
    fields=(
        F("store_id", "str", True, "배송지ID", aliases=("점포코드", "거래처코드", "배송지코드", "customer_id", "store", "점포id", "거래처id")),
        F("name", "str", True, "배송지명", aliases=("점포명", "거래처명", "배송지명", "customer_name", "store_name")),
        F("lat", "float", True, "위도", "deg", ("위도", "latitude", "y"), min=-90, max=90),
        F("lon", "float", True, "경도", "deg", ("경도", "longitude", "lng", "x"), min=-180, max=180),
        F("region", "str", False, "권역", aliases=("권역", "지역", "시도")),
        F("customer_group", "str", False, "거래처군", aliases=("거래처군", "채널", "channel", "segment")),
        F("tw_start", "time", False, "배송 시작 가능시각", aliases=("시간창시작", "time_window_start")),
        F("tw_end", "time", False, "배송 마감시각", aliases=("시간창종료", "time_window_end")),
        F("service_min", "float", False, "하역 소요시간", "분", ("하역시간", "service_time"), min=0),
    ),
)

SKUS = EntitySpec(
    name="skus", label="상품(SKU)", primary_key=("sku_id",),
    fields=(
        F("sku_id", "str", True, "SKU", aliases=("sku", "상품코드", "품목코드", "item_id", "product_id")),
        F("name", "str", True, "상품명", aliases=("상품명", "품목명", "item_name", "product_name")),
        F("category", "str", False, "상품군", aliases=("상품군", "카테고리", "분류")),
        F("unit_weight_kg", "float", False, "단위중량", "kg", ("중량", "weight", "weight_kg", "단위중량"), min=0),
        F("unit_volume_m3", "float", False, "단위부피", "m³", ("부피", "volume", "cbm", "volume_m3"), min=0),
        F("unit_cost", "float", False, "단가", "원", ("단가", "원가", "cost"), min=0),
    ),
)

VEHICLES = EntitySpec(
    name="vehicles", label="차량", primary_key=("vehicle_id",),
    foreign_keys=(ForeignKey("home_warehouse_id", "warehouses", "warehouse_id"),),
    fields=(
        F("vehicle_id", "str", True, "차량ID", aliases=("차량번호", "차량코드", "vehicle", "truck_id")),
        F("home_warehouse_id", "str", True, "소속센터", aliases=("소속센터", "센터코드", "warehouse_id", "depot")),
        F("carrier", "str", False, "운송사", aliases=("운송사", "운수사", "carrier_name")),
        F("vehicle_type", "str", False, "차종", aliases=("차종", "톤급", "type")),
        F("capacity_kg", "float", True, "적재중량", "kg", ("적재중량", "최대적재량", "capacity", "payload_kg"), min=0),
        F("capacity_m3", "float", False, "적재용적", "m³", ("적재용적", "용적", "cbm"), min=0),
        F("fuel_efficiency_km_per_l", "float", True, "연비", "km/L", ("연비", "fuel_efficiency", "km_per_l"), min=0.1, max=50),
        F("fixed_cost_per_day", "float", False, "일 고정비", "원/일", ("고정비", "fixed_cost"), min=0),
        F("variable_cost_per_km", "float", False, "km당 변동비(연료 제외)", "원/km", ("변동비", "variable_cost"), min=0),
        F("max_hours", "float", False, "최대 운행시간", "시간", ("근무시간", "최대근무시간", "max_hours"), min=0, max=24),
        F("available", "bool", False, "가용여부", aliases=("가용", "가용여부", "available")),
    ),
)

ORDERS = EntitySpec(
    name="orders", label="주문", primary_key=("order_id",),
    foreign_keys=(ForeignKey("store_id", "stores", "store_id"), ForeignKey("warehouse_id", "warehouses", "warehouse_id")),
    fields=(
        F("order_id", "str", True, "주문번호", aliases=("주문번호", "주문id", "order_no", "order")),
        F("order_date", "date", True, "주문일", aliases=("주문일", "주문일자", "date")),
        F("store_id", "str", True, "배송지ID", aliases=("점포코드", "거래처코드", "배송지코드", "customer_id")),
        F("warehouse_id", "str", True, "출고센터", aliases=("출고센터", "센터코드", "창고코드")),
        F("requested_date", "date", False, "납기요청일", aliases=("납기일", "요청일", "due_date")),
        F("status", "str", False, "주문상태", aliases=("상태", "주문상태"), allowed=ORDER_STATUSES),
    ),
)

ORDER_LINES = EntitySpec(
    name="order_lines", label="주문상세", primary_key=("order_id", "sku_id"),
    foreign_keys=(ForeignKey("order_id", "orders", "order_id"), ForeignKey("sku_id", "skus", "sku_id")),
    fields=(
        F("order_id", "str", True, "주문번호", aliases=("주문번호", "order_no")),
        F("sku_id", "str", True, "SKU", aliases=("sku", "상품코드", "품목코드")),
        F("qty", "float", True, "주문수량", "EA", ("수량", "주문수량", "quantity"), min=0),
    ),
)

SHIPMENTS = EntitySpec(
    name="shipments", label="배송(운송장)", primary_key=("shipment_id",),
    foreign_keys=(ForeignKey("order_id", "orders", "order_id"), ForeignKey("vehicle_id", "vehicles", "vehicle_id")),
    description="1 주문 = 1 배송을 기본으로 가정. 분할배송은 shipment 를 여러 건으로 등록.",
    fields=(
        F("shipment_id", "str", True, "운송장번호", aliases=("운송장번호", "송장번호", "배송번호", "waybill")),
        F("order_id", "str", True, "주문번호", aliases=("주문번호", "order_no")),
        F("vehicle_id", "str", False, "차량ID", aliases=("차량번호", "차량코드")),
        F("carrier", "str", False, "운송사", aliases=("운송사",)),
        F("ship_date", "date", True, "출고일", aliases=("출고일", "출하일", "dispatch_date")),
        F("planned_delivery_date", "date", True, "약속 배송일", aliases=("약속일", "예정배송일", "promised_date", "due_date")),
        F("actual_delivery_date", "date", False, "실제 배송일", aliases=("배송완료일", "실제배송일", "delivered_date")),
        F("delivered_qty", "float", False, "배송수량", "EA", ("배송수량", "납품수량"), min=0),
        F("load_kg", "float", False, "적재중량", "kg", ("적재중량", "중량"), min=0),
        F("distance_km", "float", False, "운행거리", "km", ("운행거리", "거리", "distance"), min=0),
        F("fuel_l", "float", False, "연료사용량", "L", ("연료량", "주유량", "fuel_liters"), min=0),
        F("fuel_cost", "float", False, "연료비", "원", ("연료비", "유류비"), min=0),
        F("toll_cost", "float", False, "통행료", "원", ("통행료", "톨비", "toll"), min=0),
        F("other_cost", "float", False, "기타비용", "원", ("기타비용", "기타"), min=0),
        F("total_cost", "float", False, "총 운송비", "원", ("운송비", "총운송비", "freight_cost", "cost"), min=0),
        F("status", "str", False, "배송상태", aliases=("배송상태", "상태"), allowed=SHIPMENT_STATUSES),
    ),
)

INVENTORY = EntitySpec(
    name="inventory", label="재고 스냅샷", primary_key=("snapshot_date", "warehouse_id", "sku_id"),
    foreign_keys=(ForeignKey("warehouse_id", "warehouses", "warehouse_id"), ForeignKey("sku_id", "skus", "sku_id")),
    fields=(
        F("snapshot_date", "date", True, "기준일", aliases=("기준일", "재고일자", "date")),
        F("warehouse_id", "str", True, "센터ID", aliases=("센터코드", "창고코드")),
        F("sku_id", "str", True, "SKU", aliases=("sku", "상품코드")),
        F("on_hand", "float", True, "현재고", "EA", ("현재고", "재고수량", "on_hand_qty"), min=0),
        F("allocated", "float", False, "할당재고", "EA", ("할당", "예약재고"), min=0),
        F("inbound_qty", "float", False, "입고예정량", "EA", ("입고예정", "입고예정량"), min=0),
        F("lead_time_days", "float", False, "리드타임", "일", ("리드타임", "lead_time"), min=0),
    ),
)

FUEL_PRICES = EntitySpec(
    name="fuel_prices", label="유가(기업 구매가)", primary_key=("date", "region"),
    fields=(
        F("date", "date", True, "일자", aliases=("일자", "날짜")),
        F("region", "str", False, "지역", aliases=("지역", "권역")),
        F("diesel_price", "float", True, "경유가", "원/L", ("경유가", "경유", "diesel"), min=0),
    ),
)

TRANSPORT_RATES = EntitySpec(
    name="transport_rates", label="운송 단가표", primary_key=("carrier", "vehicle_type"),
    fields=(
        F("carrier", "str", True, "운송사", aliases=("운송사",)),
        F("vehicle_type", "str", True, "차종", aliases=("차종", "톤급")),
        F("base_fee", "float", False, "기본요금", "원/회", ("기본요금",), min=0),
        F("per_km", "float", False, "km당 요금", "원/km", ("km단가",), min=0),
    ),
)

ENTITIES: dict[str, EntitySpec] = {
    e.name: e for e in (WAREHOUSES, STORES, SKUS, VEHICLES, ORDERS, ORDER_LINES, SHIPMENTS,
                        INVENTORY, FUEL_PRICES, TRANSPORT_RATES)
}

# 업로드 권장 순서 (외래키 의존성)
UPLOAD_ORDER = ["warehouses", "stores", "skus", "vehicles", "orders", "order_lines",
                "shipments", "inventory", "fuel_prices", "transport_rates"]


def template_frame(entity: str):
    """업로드 템플릿(헤더만)."""
    import pandas as pd
    return pd.DataFrame(columns=ENTITIES[entity].field_names)
