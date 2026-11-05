"""ERP/WMS/TMS 커넥터 인터페이스 (P2 — 현재 실제 연동 구현 없음).

실 연동은 고객사 시스템·계정·네트워크 정보가 필요하므로 이 저장소에는 인터페이스만 정의한다.
구현체는 fetch() 로 표준 스키마(schemas.ENTITIES) 컬럼의 DataFrame 을 반환하고,
반환값은 업로드와 동일한 validate → commit 파이프라인을 거쳐야 한다 (검증 우회 금지).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import pandas as pd


@dataclass
class ConnectorStatus:
    name: str
    system: str  # ERP | WMS | TMS | FUEL
    configured: bool
    detail: str


class Connector(ABC):
    name: str = "base"
    system: str = "ERP"
    entities: tuple[str, ...] = ()

    @abstractmethod
    def status(self) -> ConnectorStatus: ...

    @abstractmethod
    def fetch(self, entity: str, since: str | None = None) -> pd.DataFrame:
        """표준 스키마 컬럼명으로 반환. 읽기 전용."""


REGISTRY: list[type[Connector]] = []  # 구현 시 등록


def available_statuses() -> list[ConnectorStatus]:
    st = [c().status() for c in REGISTRY]
    if not st:
        st = [ConnectorStatus("ERP (주문·상품·거래처)", "ERP", False, "미구현 — 시스템 정보·API 계정 필요"),
              ConnectorStatus("WMS (재고·출고)", "WMS", False, "미구현 — 시스템 정보·API 계정 필요"),
              ConnectorStatus("TMS (배차·운송장·운송비)", "TMS", False, "미구현 — 시스템 정보·API 계정 필요"),
              ConnectorStatus("유가 API (Opinet 등)", "FUEL", False, "미구현 — API 키 필요. 현재는 CSV 업로드로 대체")]
    return st
