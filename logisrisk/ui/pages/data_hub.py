"""08 Data Hub — 업로드 · 컬럼 매핑 · 검증 · 저장 · 버전 · 품질 · 템플릿 · 커넥터."""
from __future__ import annotations

import hashlib

import pandas as pd
import streamlit as st

from ...data import ingest
from ...data.connectors import available_statuses
from ...data.schemas import ENTITIES, UPLOAD_ORDER, template_frame
from ...data.validation import auto_map, read_table
from ...security import PermissionDenied
from ...reports.export import csv_bytes
from ...views import data_hub as DV
from .. import common as C

NONE = "(매핑 안 함)"


def _entity_status(wb) -> pd.DataFrame:
    return pd.DataFrame([{"순서": r["order"], "엔터티": r["label"], "코드": r["entity"],
                          "상태": "적재됨" if r["loaded"] else "없음", "버전": r["version"], "행수": r["rows"],
                          "기간": r["period"] or "", "업로드": r["uploaded_at"] or "", "DEMO": "예" if r["demo"] else ""}
                         for r in DV.entity_status(wb)])


def _upload_tab(wb):
    c = wb.ctx
    if not c.can("data.upload"):
        C.callout("업로드는 <b>분석가 이상</b> 권한이 필요합니다.", "warn")
        return
    if c.is_demo_workspace:
        C.callout("현재 <b>DEMO 워크스페이스</b>입니다. 업로드·DEMO 적재 데이터는 가상 데이터로 표시되며 내 워크스페이스와 분리됩니다.", "warn")
        if st.button("DEMO 데이터 전체 불러오기 (9개 엔터티)", type="primary", icon=":material/science:"):
            with st.spinner("DEMO 데이터 검증·적재 중…"):
                rep = ingest.load_demo(C.get_store(), c)
            C.invalidate()
            st.success("DEMO 데이터 적재 완료: " + ", ".join(f"{k} {v['rows']:,}행" for k, v in rep.items()))
    st.dataframe(_entity_status(wb), hide_index=True, use_container_width=True)
    st.caption("외래키 검증을 위해 위 순서(센터 → 배송지 → SKU → 차량 → 주문 → 주문상세 → 배송 …)대로 업로드하세요.")

    c1, c2 = st.columns([1, 2])
    with c1:
        ent = st.selectbox("업로드할 데이터", UPLOAD_ORDER, format_func=lambda e: f"{ENTITIES[e].label} ({e})", key="up_ent")
    with c2:
        f = st.file_uploader("CSV 또는 Excel(.xlsx)", type=["csv", "xlsx", "xls"], key=f"up_file_{ent}")
    if f is None:
        C.empty("파일을 선택하세요", "Templates 탭에서 표준 양식을 내려받을 수 있습니다. 한글/영문 컬럼명은 자동 매핑됩니다.")
        return
    data = f.getvalue()
    sheet = 0
    if f.name.lower().endswith((".xlsx", ".xls")):
        try:
            xl = pd.ExcelFile(f)
            sheet = st.selectbox("시트", xl.sheet_names, key="up_sheet")
        except Exception as e:
            st.error(f"Excel 파일을 읽을 수 없습니다: {e}")
            return
    try:
        raw = read_table(data, f.name, sheet)
    except Exception as e:
        st.error(str(e))
        return
    fid = hashlib.md5(data).hexdigest()[:10] + f"_{ent}_{sheet}"
    st.markdown(f"**원본 미리보기** — {len(raw):,}행 × {len(raw.columns)}열")
    st.dataframe(raw.head(15), use_container_width=True, hide_index=True)

    C.section("컬럼 매핑", "* 필수 · 자동 매핑 결과를 확인·수정하세요")
    spec = ENTITIES[ent]
    auto = {v: k for k, v in auto_map(list(raw.columns), ent).items()}
    opts = [NONE] + list(raw.columns)
    mapping = {}
    cols = st.columns(3)
    for i, fld in enumerate(spec.fields):
        with cols[i % 3]:
            dflt = auto.get(fld.name, NONE)
            sel = st.selectbox(f"{fld.label}{' *' if fld.required else ''}  ·  {fld.name}"
                               + (f" [{fld.unit}]" if fld.unit else ""), opts, index=opts.index(dflt),
                               key=f"map_{fid}_{fld.name}")
            if sel != NONE:
                mapping[sel] = fld.name
    dup_src = pd.Series(list(mapping.keys())).duplicated()
    if len(set(mapping.values())) != len(mapping.values()) or dup_src.any():
        st.error("하나의 원본 컬럼을 여러 필드에 매핑할 수 없습니다.")
        return

    if st.button("검증 실행", type="primary", icon=":material/fact_check:", key=f"val_{fid}"):
        res = ingest.validate_upload(C.get_store(), c, ent, raw, mapping)
        st.session_state["val"] = {"fid": fid, "res": res, "mapping": mapping, "name": f.name}
    v = st.session_state.get("val")
    if not v or v["fid"] != fid:
        return
    if v["mapping"] != mapping:  # 검증 후 매핑을 바꾸면 이전 결과로 저장되지 않도록 차단
        C.callout("검증 이후 컬럼 매핑이 변경되었습니다. <b>검증을 다시 실행</b>하세요.", "warn")
        return
    res = v["res"]
    C.section("검증 결과")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("입력 행", f"{res.n_input:,}")
    m2.metric("유효 행", f"{res.n_valid:,}")
    m3.metric("오류 행", f"{res.n_error_rows:,}")
    m4.metric("경고", f"{len(res.warnings)}")
    for fm in res.fatal:
        C.callout(f"<b>저장 불가</b> — {C.E(fm)}", "bad")
    for w in res.warnings:
        C.callout(f"⚠ {C.E(w)}", "warn")
    if len(res.errors):
        st.markdown("**오류 상세** (행번호는 파일 기준, 헤더=1행)")
        summ = res.errors.groupby(["column", "message"]).size().reset_index(name="건수")
        st.dataframe(summ, hide_index=True, use_container_width=True)
        st.dataframe(res.errors.head(500), hide_index=True, use_container_width=True, height=220)
        er = res.error_rows(raw)
        st.download_button("오류 행 다운로드 (CSV)", csv_bytes(er),
                           file_name=f"errors_{ent}.csv", mime="text/csv", key=f"err_{fid}")
    if res.ok and res.n_valid:
        st.markdown("**저장될 데이터 미리보기**")
        st.dataframe(res.clean.head(10), hide_index=True, use_container_width=True)
        agree = True
        if res.n_error_rows:
            agree = st.checkbox(f"오류 행 {res.n_error_rows:,}건을 제외하고 유효 행 {res.n_valid:,}건만 저장합니다.",
                                key=f"agree_{fid}")
        prev = wb.versions.get(ent)
        if prev:
            st.caption(f"저장 시 새 버전 v{prev['version'] + 1} 이 활성화되고 기존 v{prev['version']} 은 보존(비활성)됩니다.")
        if st.button("저장 (새 버전)", disabled=not agree, icon=":material/save:", key=f"commit_{fid}"):
            try:
                ds = ingest.commit(C.get_store(), c, res, filename=v["name"], mapping=v["mapping"],
                                   is_demo=c.is_demo_workspace)
                C.invalidate()
                st.session_state.pop("val", None)
                st.success(f"저장 완료 — dataset #{ds}. 실패 시 전체 롤백되는 단일 트랜잭션으로 처리되었습니다.")
            except (PermissionDenied, ValueError) as e:
                st.error(str(e))
            except Exception as e:
                st.error(f"저장 실패 — 전체 롤백됨: {type(e).__name__}: {e}")


def _versions_tab(wb):
    df = C.get_store().list_datasets(wb.ctx)
    if df.empty:
        C.empty("저장된 데이터셋이 없습니다", "업로드 탭에서 데이터를 저장하면 버전 이력이 표시됩니다.")
        return
    show = df[["id", "entity", "version", "is_active", "filename", "source", "uploaded_by", "uploaded_at",
               "row_count", "input_rows", "rejected_rows", "is_demo", "period_start", "period_end"]]
    st.dataframe(show, hide_index=True, use_container_width=True)
    if wb.ctx.can("dataset.activate"):
        c1, c2 = st.columns(2)
        with c1:
            ds = st.selectbox("활성화할 버전 (롤백)", df["id"].tolist(),
                              format_func=lambda i: f"#{i} {df.set_index('id').loc[i, 'entity']} v{df.set_index('id').loc[i, 'version']}")
            if st.button("이 버전 활성화"):
                C.get_store().activate_dataset(wb.ctx, int(ds))
                C.invalidate()
                st.rerun()
        with c2:
            ent = st.selectbox("엔터티 비활성화 (삭제 아님)", sorted(df["entity"].unique()))
            if st.button("비활성화"):
                C.get_store().deactivate_entity(wb.ctx, ent)
                C.invalidate()
                st.rerun()
    else:
        st.caption("버전 활성화/비활성화는 관리자 권한이 필요합니다.")


def _quality_tab(wb):
    if not wb.frames:
        C.empty("활성 데이터 없음", "업로드 후 컬럼별 결측률·기간·경고가 표시됩니다.")
        return
    ds = C.get_store().list_datasets(wb.ctx)
    for ent, df in wb.frames.items():
        with st.expander(f"{ENTITIES[ent].label} — {len(df):,}행", expanded=False):
            row = ds[(ds["entity"] == ent) & ds["is_active"]].iloc[0]
            import json
            for w in json.loads(row["warnings_json"] or "[]"):
                C.callout(f"⚠ {C.E(w)}", "warn")
            q = pd.DataFrame({"필드": df.columns, "결측": df.isna().sum().values,
                              "결측률": (df.isna().mean().values * 100).round(1),
                              "고유값": [df[c].nunique() for c in df.columns]})
            st.dataframe(q, hide_index=True, use_container_width=True)
    if wb.fact is not None:
        f = wb.fact
        C.section("배송 원장 연결 품질")
        st.dataframe(pd.DataFrame([{"점검": r["check"], "건수": r["count"]} for r in DV.linkage_quality(f)]),
                     hide_index=True, use_container_width=True)


def _templates_tab():
    ent = st.selectbox("스키마", UPLOAD_ORDER, format_func=lambda e: ENTITIES[e].label, key="tpl_ent")
    spec = ENTITIES[ent]
    st.caption(spec.description or "")
    st.dataframe(pd.DataFrame([{"필드": f.name, "이름": f.label, "타입": f.type, "필수": "●" if f.required else "",
                                "단위": f.unit, "허용값": "/".join(f.allowed) if f.allowed else "",
                                "범위": f"{f.min if f.min is not None else ''}~{f.max if f.max is not None else ''}"
                                if (f.min is not None or f.max is not None) else "",
                                "자동매핑 별칭": ", ".join(f.aliases)} for f in spec.fields]),
                 hide_index=True, use_container_width=True)
    st.caption(f"기본키: {', '.join(spec.primary_key)}"
               + (" · 외래키: " + ", ".join(f"{k.column}→{k.ref_entity}" for k in spec.foreign_keys) if spec.foreign_keys else ""))
    st.download_button(f"{spec.label} 템플릿 CSV", csv_bytes(template_frame(ent)),
                       file_name=f"template_{ent}.csv", mime="text/csv")


def render():
    wb = C.workbench()
    C.header("08 · Data Hub", "데이터 허브", "업로드 → 컬럼 매핑 → 검증 → 원자적 저장 · 버전 관리", wb)
    t1, t2, t3, t4, t5 = st.tabs(["업로드", "데이터셋·버전", "데이터 품질", "템플릿·스키마", "외부 연동"])
    with t1:
        _upload_tab(wb)
    with t2:
        _versions_tab(wb)
    with t3:
        _quality_tab(wb)
    with t4:
        _templates_tab()
    with t5:
        C.callout("ERP/WMS/TMS 실시간 연동은 <b>아직 구현되지 않았습니다</b>. 고객사 시스템 정보와 계정이 필요합니다. "
                  "커넥터 인터페이스(<code>logisrisk/data/connectors.py</code>)만 정의되어 있으며, 연동 데이터도 업로드와 동일한 검증을 거치게 됩니다.", "warn")
        st.dataframe(pd.DataFrame([s.__dict__ for s in available_statuses()]).rename(
            columns={"name": "커넥터", "system": "시스템", "configured": "구성됨", "detail": "상태"}),
            hide_index=True, use_container_width=True)
        C.section("외부 위험 데이터 (기존 분석 산출물)")
        st.dataframe(C.provenance_table(wb.ext.provenance), hide_index=True, use_container_width=True)
        if wb.ext.missing:
            C.callout("누락: " + C.E(", ".join(wb.ext.missing)), "bad")
