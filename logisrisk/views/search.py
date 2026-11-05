"""전역 검색 (⌘K): 배송지·SKU·차량·센터·주문·배송·외부 영업소."""
from __future__ import annotations

import pandas as pd

from ..services import Workbench
from .serialize import jsonable

TARGETS = (("stores", "배송지", "store_id", ["store_id", "name", "region"], "name"),
           ("skus", "SKU", "sku_id", ["sku_id", "name", "category"], "name"),
           ("vehicles", "차량", "vehicle_id", ["vehicle_id", "carrier"], "carrier"),
           ("warehouses", "센터", "warehouse_id", ["warehouse_id", "name"], "name"),
           ("orders", "주문", "order_id", ["order_id"], "store_id"),
           ("shipments", "배송", "shipment_id", ["shipment_id", "order_id"], "order_id"))


def search(wb: Workbench, q: str, per_group: int = 8) -> list[dict]:
    q = (q or "").strip().lower()
    if len(q) < 1:
        return []
    groups = []
    for ent, label, key, cols, sub in TARGETS:
        df = wb.frames.get(ent)
        if df is None:
            continue
        m = pd.Series(False, index=df.index)
        for c in cols:
            if c in df.columns:
                m |= df[c].astype(str).str.lower().str.contains(q, regex=False, na=False)
        hit = df[m]
        if len(hit):
            items = [{"id": jsonable(r[key]), "title": str(r.get("name", r[key]) if "name" in hit.columns else r[key]),
                      "subtitle": jsonable(r.get(sub)) if sub in hit.columns else None}
                     for _, r in hit.head(per_group).iterrows()]
            groups.append({"entity": ent, "label": label, "total": int(len(hit)), "items": items})
    u = wb.ext.units
    if u is not None:
        m = u["unitName"].astype(str).str.lower().str.contains(q, regex=False, na=False) | \
            u["routeName"].astype(str).str.lower().str.contains(q, regex=False, na=False)
        hit = u[m]
        if len(hit):
            groups.append({"entity": "external_units", "label": "고속도로 영업소 (외부 지표)", "total": int(len(hit)),
                           "items": [{"id": jsonable(r["unitCode"]), "title": str(r["unitName"]),
                                      "subtitle": str(r["routeName"])} for _, r in hit.head(per_group).iterrows()]})
    return groups
