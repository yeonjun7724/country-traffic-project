"""UI 스모크: 모든 페이지가 빈 워크스페이스·DEMO 워크스페이스에서 예외 없이 렌더링되는지 (Streamlit AppTest)."""
import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

PAGES = ["control_tower", "network", "transportation", "inventory", "fuel_risk", "scenario_lab", "copilot",
         "data_hub", "reports", "settings"]


def _script(page_key, ws, dburl):
    import streamlit as st

    import logisrisk.data.store as S
    S.DATABASE_URL = dburl
    from logisrisk.ui import common as C
    from logisrisk.ui import nav, theme
    st.session_state.setdefault("workspace_id", ws)
    st.markdown(theme.css("light"), unsafe_allow_html=True)
    pages = nav.build()
    st.navigation(pages)
    mod = {"inventory": "inventory_page", "copilot": "copilot_page", "settings": "settings_page"}.get(page_key, page_key)
    import importlib
    importlib.import_module(f"logisrisk.ui.pages.{mod}").render()
    _ = C


@pytest.fixture(scope="module")
def dburl(demo_store):
    from logisrisk.ui import common as C
    C.get_store.clear()
    _, p = demo_store
    return f"sqlite:///{p.as_posix()}"


@pytest.mark.parametrize("ws", ["default", "demo"])
@pytest.mark.parametrize("page", PAGES)
def test_page_renders(page, ws, dburl):
    at = AppTest.from_function(_script, args=(page, ws, dburl), default_timeout=120)
    at.run()
    assert not at.exception, [e.value for e in at.exception]


def test_demo_banner_and_kpis(dburl):
    at = AppTest.from_function(_script, args=("control_tower", "demo", dburl), default_timeout=120)
    at.run()
    html = " ".join(m.value for m in at.markdown)
    assert "DEMO 워크스페이스" in html and "OTIF" in html
    assert html.count('class="lr-kpi-val"') == 9  # 9개 KPI 모두 계산됨 (계산 불가 0)


def test_empty_workspace_shows_no_fake_numbers(dburl):
    at = AppTest.from_function(_script, args=("control_tower", "default", dburl), default_timeout=120)
    at.run()
    html = " ".join(m.value for m in at.markdown)
    assert "운영 데이터가 아직 없습니다" in html
    assert 'class="lr-kpi-val' not in html  # 기업 KPI 카드 미표시


def test_copilot_fallback_roundtrip(dburl):
    at = AppTest.from_function(_script, args=("copilot", "demo", dburl), default_timeout=120)
    at.run()
    at.chat_input[0].set_value("배송 지연이 잦은 권역").run()
    assert not at.exception
    assert any("권역별 배송 지연율" in m.value for m in at.markdown)
