"""페이지 레지스트리 (st.page_link 에서 공용 참조)."""
from __future__ import annotations

import streamlit as st

_PAGES: dict[str, st.Page] = {}


def build() -> dict[str, list]:
    from .pages import (control_tower, copilot_page, data_hub, fuel_risk, inventory_page, network, reports,
                        scenario_lab, settings_page, transportation)
    spec = [
        ("운영", [("control_tower", control_tower.render, "01 Control Tower", ":material/space_dashboard:", True),
                ("network", network.render, "02 Network Intelligence", ":material/hub:", False),
                ("transportation", transportation.render, "03 Transportation", ":material/local_shipping:", False),
                ("inventory", inventory_page.render, "04 Demand & Inventory", ":material/inventory_2:", False)]),
        ("분석", [("fuel_risk", fuel_risk.render, "05 Fuel & Risk", ":material/local_gas_station:", False),
                ("scenario_lab", scenario_lab.render, "06 Scenario Lab", ":material/science:", False),
                ("copilot", copilot_page.render, "07 AI Copilot", ":material/smart_toy:", False)]),
        ("관리", [("data_hub", data_hub.render, "08 Data Hub", ":material/database:", False),
                ("reports", reports.render, "09 Reports & Alerts", ":material/summarize:", False),
                ("settings", settings_page.render, "10 Settings", ":material/settings:", False)]),
    ]
    out = {}
    for sec, items in spec:
        out[sec] = []
        for key, fn, title, icon, default in items:
            p = st.Page(fn, title=title, icon=icon, url_path=key, default=default)
            _PAGES[key] = p
            out[sec].append(p)
    return out


def page(key: str):
    return _PAGES.get(key)
