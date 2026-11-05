"""업로드 데이터 읽기 · 컬럼 매핑 · 검증.

검증 원칙
- 필수 컬럼 누락 → 치명(fatal): 저장 불가
- 행 단위 오류(타입, 필수값, 범위, 허용값, 중복키, 외래키, 날짜 논리) → 해당 행 제외 대상, 오류 행 다운로드 제공
- 경고(이상치, 국내 범위 밖 좌표, 미검증 참조) → 저장은 가능하나 화면·리포트에 노출
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime

import numpy as np
import pandas as pd

from .schemas import ENTITIES, EntitySpec

KOREA_BBOX = {"lat": (33.0, 38.7), "lon": (124.5, 131.9)}
_TRUE = {"true", "1", "y", "yes", "t", "예", "가용", "o", "사용"}
_FALSE = {"false", "0", "n", "no", "f", "아니오", "불가", "x", "미사용"}
# 결측으로 간주하는 토큰 (대문자 비교). 'NA' 는 지역코드 등과 충돌 가능성이 낮아 포함.
NA_TOKENS = {"", "NAN", "NONE", "NULL", "N/A", "NA", "#N/A", "-", "NAT"}
_FORMULA_PREFIX = ("=", "+", "-", "@", "\t", "\r")


def _norm(s: str) -> str:
    return re.sub(r"[\s_\-\(\)\[\]/.]", "", str(s).strip().lower())


# ── 파일 읽기 ──────────────────────────────────────────────────────────────
def read_table(data: bytes, filename: str, sheet: str | int | None = 0) -> pd.DataFrame:
    """CSV(UTF-8/UTF-8-SIG/CP949) 또는 Excel 을 문자열 그대로 읽는다 (ID 의 선행 0 보존)."""
    name = filename.lower()
    if name.endswith((".xlsx", ".xlsm", ".xls")):
        df = pd.read_excel(io.BytesIO(data), sheet_name=sheet, dtype=str)
    elif name.endswith((".csv", ".txt")):
        last_err: Exception | None = None
        for enc in ("utf-8-sig", "cp949", "euc-kr"):
            try:
                df = pd.read_csv(io.BytesIO(data), dtype=str, encoding=enc, keep_default_na=False)
                break
            except UnicodeDecodeError as e:
                last_err = e
        else:
            raise ValueError(f"인코딩을 판별할 수 없습니다 (UTF-8/CP949 시도): {last_err}")
    else:
        raise ValueError("지원하지 않는 파일 형식입니다. CSV 또는 Excel(.xlsx)만 업로드하세요.")
    df.columns = [str(c).strip() for c in df.columns]
    return df


# ── 컬럼 매핑 ──────────────────────────────────────────────────────────────
def auto_map(columns: list[str], entity: str) -> dict[str, str]:
    """{원본컬럼: 표준필드} 자동 매핑. 매칭되지 않은 컬럼은 포함하지 않는다."""
    spec = ENTITIES[entity]
    mapping: dict[str, str] = {}
    used: set[str] = set()
    normcols = {c: _norm(c) for c in columns}
    for f in spec.fields:
        cands = [_norm(f.name), _norm(f.label)] + [_norm(a) for a in f.aliases]
        for c, nc in normcols.items():
            if c in mapping or f.name in used:
                continue
            if nc in cands:
                mapping[c] = f.name
                used.add(f.name)
                break
    return mapping


def apply_mapping(df: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
    keep = {src: dst for src, dst in mapping.items() if dst and src in df.columns}
    out = df[list(keep)].rename(columns=keep)
    out = out.loc[:, ~out.columns.duplicated()]
    return out


# ── 검증 결과 ──────────────────────────────────────────────────────────────
@dataclass
class ValidationResult:
    entity: str
    clean: pd.DataFrame
    errors: pd.DataFrame  # columns: row, column, code, message, value
    warnings: list[str] = field(default_factory=list)
    fatal: list[str] = field(default_factory=list)
    n_input: int = 0

    @property
    def ok(self) -> bool:
        return not self.fatal

    @property
    def n_valid(self) -> int:
        return len(self.clean)

    @property
    def n_error_rows(self) -> int:
        return int(self.errors["row"].nunique()) if len(self.errors) else 0

    def error_rows(self, original: pd.DataFrame) -> pd.DataFrame:
        """원본 행 + 오류 사유 (다운로드용). row 는 파일 기준 행번호(헤더=1)."""
        if not len(self.errors):
            return original.iloc[0:0].assign(오류행번호=[], 오류내용=[])
        msgs = (self.errors.assign(txt=lambda d: d["column"].astype(str) + ": " + d["message"])
                .groupby("row")["txt"].apply(lambda s: " | ".join(s)))
        idx = [r - 2 for r in msgs.index]
        out = original.iloc[idx].copy()
        out.insert(0, "오류내용", msgs.values)
        out.insert(0, "오류행번호", msgs.index.values)
        return out.reset_index(drop=True)


class _Errors:
    def __init__(self):
        self.items: list[dict] = []

    def add(self, mask: pd.Series, column: str, code: str, message: str, values: pd.Series | None = None):
        if mask is None or not mask.any():
            return
        for i in mask[mask].index:
            v = None if values is None else values.get(i)
            self.items.append({"row": int(i) + 2, "column": column, "code": code, "message": message,
                               "value": None if v is None or (isinstance(v, float) and np.isnan(v)) else str(v)})

    def frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.items, columns=["row", "column", "code", "message", "value"])


def _to_bool(s: pd.Series) -> pd.Series:
    low = s.astype("string").str.strip().str.lower()
    out = pd.Series(pd.NA, index=s.index, dtype="boolean")
    out[low.isin(_TRUE)] = True
    out[low.isin(_FALSE)] = False
    return out


def _to_time(s: pd.Series) -> pd.Series:
    t = pd.to_datetime(s.astype("string"), format="%H:%M", errors="coerce")
    t2 = pd.to_datetime(s.astype("string"), format="%H:%M:%S", errors="coerce")
    t = t.fillna(t2)
    return t.dt.strftime("%H:%M").where(t.notna(), None)


def _to_date(s: pd.Series) -> pd.Series:
    st = s.astype("string").str.strip()
    out = pd.to_datetime(st, format="%Y-%m-%d", errors="coerce")
    rest = out.isna() & st.notna()
    if rest.any():
        out.loc[rest] = pd.to_datetime(st[rest], errors="coerce", format="mixed")
    return out.dt.normalize()


def validate(entity: str, df: pd.DataFrame, refs: dict[str, set[str]] | None = None,
             today: date | None = None) -> ValidationResult:
    """매핑 완료된 df(표준 컬럼명) 를 검증한다. refs: {참조엔터티: 키 집합}."""
    spec: EntitySpec = ENTITIES[entity]
    refs = refs or {}
    today = today or datetime.now().date()
    df = df.reset_index(drop=True).copy()
    n = len(df)
    warnings: list[str] = []
    fatal: list[str] = []

    missing = [f for f in spec.required_fields if f not in df.columns]
    if missing:
        fatal.append("필수 컬럼 누락: " + ", ".join(f"{m}({spec.field(m).label})" for m in missing))
        return ValidationResult(entity, df.iloc[0:0], _Errors().frame(), warnings, fatal, n)
    if n == 0:
        fatal.append("데이터 행이 없습니다.")
        return ValidationResult(entity, df, _Errors().frame(), warnings, fatal, n)

    extra = [c for c in df.columns if c not in spec.field_names]
    if extra:
        warnings.append(f"스키마에 없는 컬럼 {len(extra)}개는 저장하지 않습니다: {', '.join(extra[:8])}")
        df = df.drop(columns=extra)

    # 문자열 정리 · 결측 토큰 → NA
    for c in df.columns:
        s = df[c].astype("string").str.strip()
        df[c] = s.mask(s.str.upper().isin(NA_TOKENS))

    err = _Errors()
    out = pd.DataFrame(index=df.index)
    for f in spec.fields:
        if f.name not in df.columns:
            out[f.name] = pd.Series([None] * n, index=df.index, dtype="object")
            continue
        raw = df[f.name]
        if f.type in ("float", "int"):
            val = pd.to_numeric(raw.str.replace(",", "", regex=False), errors="coerce")
            if f.type == "int":
                bad_int = val.notna() & (val % 1 != 0)
                err.add(bad_int, f.name, "type", "정수가 아닙니다", raw)
            val = val.astype("float64")
        elif f.type == "date":
            val = _to_date(raw)
        elif f.type == "bool":
            val = _to_bool(raw)
        elif f.type == "time":
            val = _to_time(raw)
        else:
            val = raw
        bad_type = raw.notna() & pd.isna(val)
        err.add(bad_type, f.name, "type", f"형식 오류({f.type})", raw)
        if f.required:
            err.add(raw.isna(), f.name, "required", "필수값 누락", raw)
        if f.type in ("float", "int"):
            if f.min is not None:
                err.add(val.notna() & (val < f.min), f.name, "range", f"{f.min} 미만", raw)
            if f.max is not None:
                err.add(val.notna() & (val > f.max), f.name, "range", f"{f.max} 초과", raw)
        if f.allowed is not None:
            low = raw.str.lower()
            err.add(raw.notna() & ~low.isin(f.allowed), f.name, "enum",
                    "허용값 아님 (" + "/".join(f.allowed) + ")", raw)
            val = low
        out[f.name] = val

    # 복합키 내 선택 필드 결측은 'ALL' 로 표준화 (예: 지역 미지정 유가)
    for k in spec.primary_key:
        if not spec.field(k).required:
            out[k] = out[k].fillna("ALL")

    # 기본키 중복
    pk = list(spec.primary_key)
    dup = out.duplicated(subset=pk, keep=False) & out[pk].notna().all(axis=1)
    if dup.any():
        err.add(dup, "+".join(pk), "duplicate", "기본키 중복 (모든 중복 행 표시)",
                out[pk].astype(str).agg("|".join, axis=1))

    # 외래키
    for fk in spec.foreign_keys:
        if fk.column not in out.columns:
            continue
        col = out[fk.column]
        if fk.ref_entity in refs:
            bad = col.notna() & ~col.astype(str).isin(refs[fk.ref_entity])
            err.add(bad, fk.column, "foreign_key",
                    f"{ENTITIES[fk.ref_entity].label}에 없는 값", col)
        elif col.notna().any():
            warnings.append(f"'{fk.column}' 참조 대상({ENTITIES[fk.ref_entity].label})이 아직 업로드되지 않아 "
                            "참조 무결성을 검증하지 못했습니다.")

    # 좌표
    if spec.coord_fields:
        la, lo = spec.coord_fields
        zero = (out[la] == 0) & (out[lo] == 0)
        err.add(zero, f"{la},{lo}", "coord", "(0,0) 좌표는 유효하지 않습니다", out[la])
        swapped = out[lo].between(*KOREA_BBOX["lat"]) & out[la].between(*KOREA_BBOX["lon"])
        err.add(swapped, f"{la},{lo}", "coord_swapped", "위도·경도가 서로 바뀐 것으로 보입니다 (열 매핑 확인)",
                out[la].astype(str) + "," + out[lo].astype(str))
        outside = out[la].notna() & out[lo].notna() & ~zero & ~swapped & ~(
            out[la].between(*KOREA_BBOX["lat"]) & out[lo].between(*KOREA_BBOX["lon"]))
        if outside.any():
            warnings.append(f"대한민국 범위 밖 좌표 {int(outside.sum())}건 (해외 거점이 아니라면 확인 필요)")

    # 날짜 논리
    def _before(a: str, b: str, msg: str):
        if a in out.columns and b in out.columns:
            m = out[a].notna() & out[b].notna() & (out[a] < out[b])
            err.add(m, a, "date_logic", msg, out[a].astype(str))

    if entity == "shipments":
        _before("actual_delivery_date", "ship_date", "실제 배송일이 출고일보다 빠릅니다")
        _before("planned_delivery_date", "ship_date", "약속 배송일이 출고일보다 빠릅니다")
        if "status" in out.columns:
            no_date = (out["status"] == "delivered") & out["actual_delivery_date"].isna()
            if no_date.any():
                warnings.append(f"상태가 delivered 이지만 실제 배송일이 없는 건 {int(no_date.sum())}건 — OTIF 분모에서 제외됩니다")
    if entity == "orders":
        _before("requested_date", "order_date", "납기요청일이 주문일보다 빠릅니다")
    for f in spec.fields:
        if f.type == "date":
            fut = out[f.name].notna() & (out[f.name] > pd.Timestamp(today) + pd.Timedelta(days=365))
            if fut.any():
                warnings.append(f"'{f.label}' 1년 이상 미래 날짜 {int(fut.sum())}건")

    # 이상치 (경고만, 제거하지 않음) — robust z = 0.6745·|x-median|/MAD > 6
    for f in spec.fields:
        if f.type in ("float", "int") and f.name in out.columns and f.name not in ("lat", "lon"):
            x = out[f.name].dropna()
            if len(x) >= 20:
                dev = (x - x.median()).abs()
                mad = dev.median()
                # MAD=0(대부분 동일값)이면 평균절대편차 기반 대체 척도 (Iglewicz–Hoaglin)
                scale = mad / 0.6745 if mad > 0 else 1.253314 * dev.mean()
                if scale and scale > 0:
                    rz = dev / scale
                    k = int((rz > 6).sum())
                    if k:
                        warnings.append(f"'{f.label}' 이상치 의심 {k}건 (robust z>6, 제거하지 않음)")

    errors = err.frame()
    bad_rows = set(r - 2 for r in errors["row"].unique()) if len(errors) else set()
    clean = out.loc[[i for i in out.index if i not in bad_rows]].reset_index(drop=True)
    for f in spec.fields:  # 문자열 컬럼은 object 로 정규화 (DB 저장 호환)
        if f.type == "str":
            clean[f.name] = clean[f.name].astype(object).where(clean[f.name].notna(), None)
        elif f.type == "bool":
            clean[f.name] = clean[f.name].astype(object).where(clean[f.name].notna(), None)
    return ValidationResult(entity, clean, errors, warnings, fatal, n)


def neutralize_formulas(df: pd.DataFrame) -> pd.DataFrame:
    """CSV/Excel 수식 주입 방지: '=,+,-,@' 로 시작하는 문자열 셀 앞에 ' 를 붙인다 (숫자형은 그대로)."""
    x = df.copy()
    for c in x.columns:
        if x[c].dtype == object or pd.api.types.is_string_dtype(x[c]):
            x[c] = x[c].map(lambda v: "'" + v if isinstance(v, str) and v.startswith(_FORMULA_PREFIX) else v)
    return x


def dangling_references(entity: str, new_keys: set[str], frames: dict[str, pd.DataFrame]) -> list[str]:
    """참조되는 엔터티(예: 배송지)를 새 버전으로 교체할 때, 기존 활성 데이터가 사라지는 키를 참조하는지 점검."""
    out = []
    for name, spec in ENTITIES.items():
        df = frames.get(name)
        if df is None or name == entity:
            continue
        for fk in spec.foreign_keys:
            if fk.ref_entity != entity or fk.column not in df:
                continue
            refs = df[fk.column].dropna().astype(str)
            miss = refs[~refs.isin(new_keys)]
            if len(miss):
                out.append(f"기존 {spec.label} {len(miss):,}건이 새 {ENTITIES[entity].label}에 없는 "
                           f"{fk.column} 를 참조하게 됩니다 (예: {', '.join(miss.unique()[:3])})")
    return out


def key_set(df: pd.DataFrame | None, column: str) -> set[str]:
    if df is None or column not in df.columns:
        return set()
    return set(df[column].dropna().astype(str))
