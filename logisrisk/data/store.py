"""영속 저장소 (SQLAlchemy Core).

- 기본 SQLite(data/logisrisk.db). DATABASE_URL 로 PostgreSQL 전환 가능.
- 모든 조회·쓰기는 UserContext.workspace_id 로 격리되며 권한을 검사한다.
- 데이터셋 업로드는 단일 트랜잭션: 실패 시 전체 롤백 (원자성).
- 데이터셋은 버전 관리: 새 버전 업로드 시 이전 버전은 비활성(삭제하지 않음) → 롤백 가능.
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import (Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, MetaData, String,
                        Table, Text, and_, create_engine, func, insert, select, update)
from sqlalchemy.engine import Engine

from .. import CALC_VERSION
from ..config import DATABASE_URL
from ..security import ROLES, PermissionDenied, UserContext, require
from .schemas import ENTITIES, EntitySpec

SCHEMA_VERSION = 1
_TYPE = {"str": lambda: String(255), "int": Float, "float": Float, "date": Date,
         "bool": Boolean, "time": lambda: String(8)}

metadata = MetaData()

workspaces = Table("workspaces", metadata,
                   Column("id", String(64), primary_key=True),
                   Column("name", String(200), nullable=False),
                   Column("is_demo", Boolean, nullable=False, default=False),
                   Column("created_at", DateTime, default=datetime.now))

users = Table("users", metadata,
              Column("id", String(64), primary_key=True),
              Column("display_name", String(200)),
              Column("created_at", DateTime, default=datetime.now))

memberships = Table("memberships", metadata,
                    Column("user_id", String(64), ForeignKey("users.id"), primary_key=True),
                    Column("workspace_id", String(64), ForeignKey("workspaces.id"), primary_key=True),
                    Column("role", String(20), nullable=False))

datasets = Table("datasets", metadata,
                 Column("id", Integer, primary_key=True, autoincrement=True),
                 Column("workspace_id", String(64), ForeignKey("workspaces.id"), nullable=False, index=True),
                 Column("entity", String(40), nullable=False),
                 Column("version", Integer, nullable=False),
                 Column("filename", String(255)),
                 Column("source", String(100)),
                 Column("uploaded_by", String(64)),
                 Column("uploaded_at", DateTime, default=datetime.now),
                 Column("row_count", Integer),
                 Column("input_rows", Integer),
                 Column("rejected_rows", Integer),
                 Column("is_demo", Boolean, default=False),
                 Column("is_active", Boolean, default=True),
                 Column("checksum", String(64)),
                 Column("mapping_json", Text),
                 Column("warnings_json", Text),
                 Column("period_start", Date),
                 Column("period_end", Date))

scenarios = Table("scenarios", metadata,
                  Column("id", Integer, primary_key=True, autoincrement=True),
                  Column("workspace_id", String(64), ForeignKey("workspaces.id"), nullable=False, index=True),
                  Column("name", String(200), nullable=False),
                  Column("kind", String(40), nullable=False),
                  Column("status", String(20), nullable=False, default="draft"),
                  Column("params_json", Text),
                  Column("result_json", Text),
                  Column("assumptions_json", Text),
                  Column("data_versions_json", Text),
                  Column("calc_version", String(40)),
                  Column("created_by", String(64)),
                  Column("created_at", DateTime, default=datetime.now),
                  Column("updated_at", DateTime, default=datetime.now))

settings_t = Table("settings", metadata,
                   Column("workspace_id", String(64), primary_key=True),
                   Column("key", String(100), primary_key=True),
                   Column("value_json", Text),
                   Column("updated_by", String(64)),
                   Column("updated_at", DateTime, default=datetime.now))

actions_t = Table("action_items", metadata,
                  Column("id", Integer, primary_key=True, autoincrement=True),
                  Column("workspace_id", String(64), nullable=False, index=True),
                  Column("title", String(300), nullable=False),
                  Column("source", String(200)),
                  Column("detail", Text),
                  Column("status", String(20), default="open"),
                  Column("owner", String(64)),
                  Column("created_by", String(64)),
                  Column("created_at", DateTime, default=datetime.now),
                  Column("updated_at", DateTime, default=datetime.now))

audit_t = Table("audit_log", metadata,
                Column("id", Integer, primary_key=True, autoincrement=True),
                Column("workspace_id", String(64), index=True),
                Column("user_id", String(64)),
                Column("action", String(80), nullable=False),
                Column("target", String(200)),
                Column("detail_json", Text),
                Column("at", DateTime, default=datetime.now))

meta_t = Table("schema_meta", metadata,
               Column("key", String(40), primary_key=True),
               Column("value", String(200)))


def _entity_table(spec: EntitySpec) -> Table:
    cols = [Column("_rid", Integer, primary_key=True, autoincrement=True),
            Column("_dataset_id", Integer, ForeignKey("datasets.id"), nullable=False, index=True),
            Column("_workspace_id", String(64), nullable=False, index=True)]
    for f in spec.fields:
        t = _TYPE[f.type]
        cols.append(Column(f.name, t() if callable(t) and not isinstance(t, type) else t))
    return Table(f"ent_{spec.name}", metadata, *cols)


ENTITY_TABLES: dict[str, Table] = {name: _entity_table(spec) for name, spec in ENTITIES.items()}

SCENARIO_STATUSES = ("draft", "proposed", "approved", "rejected", "archived")
ACTION_STATUSES = ("open", "in_progress", "done", "dismissed")


def _jsonable(o: Any):
    if isinstance(o, (datetime, date, pd.Timestamp)):
        return o.isoformat()
    if isinstance(o, float) and (math.isnan(o) or math.isinf(o)):
        return None
    if hasattr(o, "item"):
        return o.item()
    if isinstance(o, pd.DataFrame):
        return o.to_dict(orient="records")
    raise TypeError(type(o))


def dumps(o: Any) -> str:
    return json.dumps(o, default=_jsonable, ensure_ascii=False)


def _records(df: pd.DataFrame, spec: EntitySpec) -> list[dict]:
    recs = []
    for row in df[spec.field_names].itertuples(index=False):
        r = {}
        for f, v in zip(spec.fields, row):
            if v is None or (isinstance(v, float) and math.isnan(v)) or v is pd.NaT or v is pd.NA:
                r[f.name] = None
            elif f.type == "date":
                r[f.name] = pd.Timestamp(v).date()
            elif f.type == "bool":
                r[f.name] = bool(v)
            elif f.type in ("float", "int"):
                r[f.name] = float(v)
            else:
                r[f.name] = str(v)
        recs.append(r)
    return recs


class Store:
    def __init__(self, url: str | None = None, engine: Engine | None = None):
        url = url or DATABASE_URL
        if engine is None:
            if url.startswith("sqlite:///") and ":memory:" not in url:
                Path(url.replace("sqlite:///", "")).parent.mkdir(parents=True, exist_ok=True)
            engine = create_engine(url, future=True)
        self.engine = engine
        metadata.create_all(self.engine)
        self._bootstrap()

    # ── 부트스트랩: 로컬 모드 기본 워크스페이스/사용자 ─────────────────────────
    def _bootstrap(self):
        with self.engine.begin() as c:
            if c.execute(select(meta_t.c.value).where(meta_t.c.key == "schema_version")).first() is None:
                c.execute(insert(meta_t).values(key="schema_version", value=str(SCHEMA_VERSION)))
            for wid, name, demo in (("default", "내 워크스페이스", False),
                                    ("demo", "DEMO 워크스페이스 (가상 데이터)", True)):
                if c.execute(select(workspaces.c.id).where(workspaces.c.id == wid)).first() is None:
                    c.execute(insert(workspaces).values(id=wid, name=name, is_demo=demo))
            if c.execute(select(users.c.id).where(users.c.id == "local")).first() is None:
                c.execute(insert(users).values(id="local", display_name="로컬 사용자"))
                for wid in ("default", "demo"):
                    c.execute(insert(memberships).values(user_id="local", workspace_id=wid, role="admin"))

    # ── 사용자·워크스페이스 ───────────────────────────────────────────────
    def add_user(self, user_id: str, display_name: str = ""):
        with self.engine.begin() as c:
            if c.execute(select(users.c.id).where(users.c.id == user_id)).first() is None:
                c.execute(insert(users).values(id=user_id, display_name=display_name or user_id))

    def add_workspace(self, wid: str, name: str, is_demo: bool = False):
        with self.engine.begin() as c:
            if c.execute(select(workspaces.c.id).where(workspaces.c.id == wid)).first() is None:
                c.execute(insert(workspaces).values(id=wid, name=name, is_demo=is_demo))

    def grant(self, user_id: str, workspace_id: str, role: str):
        if role not in ROLES:
            raise ValueError(role)
        with self.engine.begin() as c:
            c.execute(memberships.delete().where(and_(memberships.c.user_id == user_id,
                                                      memberships.c.workspace_id == workspace_id)))
            c.execute(insert(memberships).values(user_id=user_id, workspace_id=workspace_id, role=role))

    def context_for(self, user_id: str, workspace_id: str) -> UserContext:
        """멤버십이 없는 워크스페이스 접근은 거부."""
        with self.engine.connect() as c:
            row = c.execute(select(memberships.c.role, users.c.display_name, workspaces.c.is_demo)
                            .join(users, users.c.id == memberships.c.user_id)
                            .join(workspaces, workspaces.c.id == memberships.c.workspace_id)
                            .where(and_(memberships.c.user_id == user_id,
                                        memberships.c.workspace_id == workspace_id))).first()
        if row is None:
            raise PermissionDenied(f"워크스페이스 '{workspace_id}' 에 대한 접근 권한이 없습니다.")
        return UserContext(user_id, workspace_id, row.role, row.display_name or user_id, bool(row.is_demo))

    def workspaces_for(self, user_id: str) -> list[dict]:
        with self.engine.connect() as c:
            rows = c.execute(select(workspaces.c.id, workspaces.c.name, workspaces.c.is_demo, memberships.c.role)
                             .join(memberships, memberships.c.workspace_id == workspaces.c.id)
                             .where(memberships.c.user_id == user_id)
                             .order_by(workspaces.c.is_demo, workspaces.c.id)).all()
        return [dict(r._mapping) for r in rows]

    # ── 감사 로그 ────────────────────────────────────────────────────────
    def log(self, ctx: UserContext, action: str, target: str = "", detail: dict | None = None, conn=None):
        stmt = insert(audit_t).values(workspace_id=ctx.workspace_id, user_id=ctx.user_id, action=action,
                                      target=target[:200], detail_json=dumps(detail or {}))
        if conn is not None:
            conn.execute(stmt)
        else:
            with self.engine.begin() as c:
                c.execute(stmt)

    def audit_log(self, ctx: UserContext, limit: int = 200) -> pd.DataFrame:
        require(ctx, "audit.read")
        with self.engine.connect() as c:
            rows = c.execute(select(audit_t).where(audit_t.c.workspace_id == ctx.workspace_id)
                             .order_by(audit_t.c.id.desc()).limit(limit)).all()
        return pd.DataFrame([dict(r._mapping) for r in rows])

    # ── 데이터셋 ─────────────────────────────────────────────────────────
    def commit_dataset(self, ctx: UserContext, entity: str, clean: pd.DataFrame, *, filename: str = "",
                       source: str = "upload", mapping: dict | None = None, warnings: list[str] | None = None,
                       input_rows: int | None = None, rejected_rows: int = 0, is_demo: bool = False,
                       _fail_after_insert: bool = False) -> int:
        """검증 통과 행을 새 버전으로 저장. 하나라도 실패하면 전체 롤백."""
        require(ctx, "data.upload")
        if is_demo and not ctx.is_demo_workspace:
            raise PermissionDenied("DEMO 데이터는 DEMO 워크스페이스에만 적재할 수 있습니다.")
        spec = ENTITIES[entity]
        recs = _records(clean, spec)
        if not recs:
            raise ValueError("저장할 유효 행이 없습니다.")
        checksum = hashlib.sha256(dumps(recs).encode()).hexdigest()
        date_cols = [f.name for f in spec.fields if f.type == "date" and f.required]
        p0 = p1 = None
        if date_cols:
            s = pd.to_datetime(clean[date_cols[0]])
            p0, p1 = s.min().date(), s.max().date()
        table = ENTITY_TABLES[entity]
        with self.engine.begin() as c:  # 트랜잭션: 예외 시 자동 롤백
            ver = c.execute(select(func.coalesce(func.max(datasets.c.version), 0))
                            .where(and_(datasets.c.workspace_id == ctx.workspace_id,
                                        datasets.c.entity == entity))).scalar_one() + 1
            c.execute(update(datasets).where(and_(datasets.c.workspace_id == ctx.workspace_id,
                                                  datasets.c.entity == entity)).values(is_active=False))
            ds_id = c.execute(insert(datasets).values(
                workspace_id=ctx.workspace_id, entity=entity, version=ver, filename=filename, source=source,
                uploaded_by=ctx.user_id, row_count=len(recs), input_rows=input_rows or len(recs),
                rejected_rows=rejected_rows, is_demo=is_demo, is_active=True, checksum=checksum,
                mapping_json=dumps(mapping or {}), warnings_json=dumps(warnings or []),
                period_start=p0, period_end=p1)).inserted_primary_key[0]
            for r in recs:
                r["_dataset_id"] = ds_id
                r["_workspace_id"] = ctx.workspace_id
            c.execute(insert(table), recs)
            if _fail_after_insert:  # 테스트용: 원자적 롤백 검증
                raise RuntimeError("simulated failure")
            self.log(ctx, "dataset.commit", f"{entity} v{ver}",
                     {"rows": len(recs), "rejected": rejected_rows, "file": filename, "demo": is_demo}, conn=c)
        return int(ds_id)

    def list_datasets(self, ctx: UserContext, entity: str | None = None) -> pd.DataFrame:
        require(ctx, "data.read")
        q = select(datasets).where(datasets.c.workspace_id == ctx.workspace_id)
        if entity:
            q = q.where(datasets.c.entity == entity)
        with self.engine.connect() as c:
            rows = c.execute(q.order_by(datasets.c.entity, datasets.c.version.desc())).all()
        return pd.DataFrame([dict(r._mapping) for r in rows])

    def activate_dataset(self, ctx: UserContext, dataset_id: int):
        """특정 버전을 활성화 (이전 버전으로 롤백)."""
        require(ctx, "dataset.activate")
        with self.engine.begin() as c:
            row = c.execute(select(datasets.c.entity).where(and_(datasets.c.id == dataset_id,
                                                                 datasets.c.workspace_id == ctx.workspace_id))).first()
            if row is None:
                raise PermissionDenied("해당 워크스페이스의 데이터셋이 아닙니다.")
            c.execute(update(datasets).where(and_(datasets.c.workspace_id == ctx.workspace_id,
                                                  datasets.c.entity == row.entity)).values(is_active=False))
            c.execute(update(datasets).where(datasets.c.id == dataset_id).values(is_active=True))
            self.log(ctx, "dataset.activate", f"{row.entity}#{dataset_id}", conn=c)

    def deactivate_entity(self, ctx: UserContext, entity: str):
        require(ctx, "dataset.activate")
        with self.engine.begin() as c:
            c.execute(update(datasets).where(and_(datasets.c.workspace_id == ctx.workspace_id,
                                                  datasets.c.entity == entity)).values(is_active=False))
            self.log(ctx, "dataset.deactivate", entity, conn=c)

    def active_frame(self, ctx: UserContext, entity: str) -> pd.DataFrame | None:
        require(ctx, "data.read")
        spec = ENTITIES[entity]
        t = ENTITY_TABLES[entity]
        with self.engine.connect() as c:
            ds = c.execute(select(datasets.c.id).where(and_(
                datasets.c.workspace_id == ctx.workspace_id, datasets.c.entity == entity,
                datasets.c.is_active.is_(True)))).first()
            if ds is None:
                return None
            rows = c.execute(select(*[t.c[f] for f in spec.field_names]).where(and_(
                t.c._dataset_id == ds.id, t.c._workspace_id == ctx.workspace_id))).all()
        df = pd.DataFrame(rows, columns=spec.field_names)
        for f in spec.fields:
            if f.type == "date":
                df[f.name] = pd.to_datetime(df[f.name])
            elif f.type in ("float", "int"):
                df[f.name] = pd.to_numeric(df[f.name], errors="coerce").astype("float64")
        return df

    def active_frames(self, ctx: UserContext) -> dict[str, pd.DataFrame]:
        out = {}
        for e in ENTITIES:
            df = self.active_frame(ctx, e)
            if df is not None:
                out[e] = df
        return out

    def data_versions(self, ctx: UserContext) -> dict[str, dict]:
        """현재 활성 데이터셋 버전 요약 (시나리오·리포트·AI 답변 메타데이터)."""
        df = self.list_datasets(ctx)
        if df.empty:
            return {}
        act = df[df["is_active"]]
        return {r.entity: {"dataset_id": int(r.id), "version": int(r.version), "rows": int(r.row_count),
                           "uploaded_at": str(r.uploaded_at)[:19], "file": r.filename, "demo": bool(r.is_demo),
                           "period": f"{r.period_start or ''}~{r.period_end or ''}"}
                for r in act.itertuples()}

    # ── 시나리오 ─────────────────────────────────────────────────────────
    def save_scenario(self, ctx: UserContext, name: str, kind: str, params: dict, result: dict,
                      assumptions: list[str], data_versions: dict | None = None, status: str = "draft") -> int:
        require(ctx, "scenario.save")
        if status not in ("draft", "proposed"):
            raise PermissionDenied("저장 시 상태는 draft/proposed 만 가능합니다. 승인은 별도 절차입니다.")
        with self.engine.begin() as c:
            sid = c.execute(insert(scenarios).values(
                workspace_id=ctx.workspace_id, name=name[:200], kind=kind, status=status,
                params_json=dumps(params), result_json=dumps(result), assumptions_json=dumps(assumptions),
                data_versions_json=dumps(data_versions or {}), calc_version=CALC_VERSION,
                created_by=ctx.user_id)).inserted_primary_key[0]
            self.log(ctx, "scenario.save", f"{kind}:{name}", {"id": sid, "status": status}, conn=c)
        return int(sid)

    def list_scenarios(self, ctx: UserContext, kind: str | None = None) -> pd.DataFrame:
        require(ctx, "data.read")
        q = select(scenarios.c.id, scenarios.c.name, scenarios.c.kind, scenarios.c.status, scenarios.c.calc_version,
                   scenarios.c.created_by, scenarios.c.created_at, scenarios.c.updated_at) \
            .where(scenarios.c.workspace_id == ctx.workspace_id)
        if kind:
            q = q.where(scenarios.c.kind == kind)
        with self.engine.connect() as c:
            rows = c.execute(q.order_by(scenarios.c.id.desc())).all()
        return pd.DataFrame([dict(r._mapping) for r in rows])

    def get_scenario(self, ctx: UserContext, sid: int) -> dict | None:
        require(ctx, "data.read")
        with self.engine.connect() as c:
            r = c.execute(select(scenarios).where(and_(scenarios.c.id == sid,
                                                       scenarios.c.workspace_id == ctx.workspace_id))).first()
        if r is None:
            return None
        d = dict(r._mapping)
        for k in ("params_json", "result_json", "assumptions_json", "data_versions_json"):
            d[k.replace("_json", "")] = json.loads(d.pop(k) or "null")
        return d

    def duplicate_scenario(self, ctx: UserContext, sid: int, new_name: str) -> int:
        s = self.get_scenario(ctx, sid)
        if s is None:
            raise PermissionDenied("시나리오를 찾을 수 없습니다.")
        return self.save_scenario(ctx, new_name, s["kind"], s["params"], s["result"], s["assumptions"],
                                  s["data_versions"], status="draft")

    def set_scenario_status(self, ctx: UserContext, sid: int, status: str, note: str = ""):
        if status not in SCENARIO_STATUSES:
            raise ValueError(status)
        require(ctx, "plan.approve" if status in ("approved", "rejected") else "scenario.save")
        with self.engine.begin() as c:
            n = c.execute(update(scenarios).where(and_(scenarios.c.id == sid,
                                                       scenarios.c.workspace_id == ctx.workspace_id))
                          .values(status=status, updated_at=datetime.now())).rowcount
            if not n:
                raise PermissionDenied("시나리오를 찾을 수 없습니다.")
            self.log(ctx, f"scenario.{status}", str(sid), {"note": note}, conn=c)

    # ── 설정 ─────────────────────────────────────────────────────────────
    def get_setting(self, ctx: UserContext, key: str, default: Any = None) -> Any:
        require(ctx, "data.read")
        with self.engine.connect() as c:
            r = c.execute(select(settings_t.c.value_json).where(and_(
                settings_t.c.workspace_id == ctx.workspace_id, settings_t.c.key == key))).first()
        return default if r is None else json.loads(r.value_json)

    def settings_revision(self, ctx: UserContext) -> str:
        with self.engine.connect() as c:
            r = c.execute(select(func.max(settings_t.c.updated_at), func.count())
                          .where(settings_t.c.workspace_id == ctx.workspace_id)).first()
        return f"{r[0]}|{r[1]}"

    def set_setting(self, ctx: UserContext, key: str, value: Any, permission: str = "settings.manage"):
        require(ctx, permission)
        with self.engine.begin() as c:
            c.execute(settings_t.delete().where(and_(settings_t.c.workspace_id == ctx.workspace_id,
                                                     settings_t.c.key == key)))
            c.execute(insert(settings_t).values(workspace_id=ctx.workspace_id, key=key, value_json=dumps(value),
                                                updated_by=ctx.user_id))
            self.log(ctx, "setting.update", key, {"value": value}, conn=c)

    # ── 조치(Action) ─────────────────────────────────────────────────────
    def create_action(self, ctx: UserContext, title: str, source: str, detail: str = "") -> int:
        require(ctx, "scenario.save")  # 분석가도 조치 후보를 '제안' 할 수 있음
        with self.engine.begin() as c:
            aid = c.execute(insert(actions_t).values(workspace_id=ctx.workspace_id, title=title[:300], source=source,
                                                     detail=detail, status="open", created_by=ctx.user_id)
                            ).inserted_primary_key[0]
            self.log(ctx, "action.create", title[:100], {"id": aid}, conn=c)
        return int(aid)

    def list_actions(self, ctx: UserContext) -> pd.DataFrame:
        require(ctx, "data.read")
        with self.engine.connect() as c:
            rows = c.execute(select(actions_t).where(actions_t.c.workspace_id == ctx.workspace_id)
                             .order_by(actions_t.c.id.desc())).all()
        return pd.DataFrame([dict(r._mapping) for r in rows])

    def set_action_status(self, ctx: UserContext, aid: int, status: str, owner: str | None = None):
        require(ctx, "action.manage")
        if status not in ACTION_STATUSES:
            raise ValueError(status)
        vals: dict[str, Any] = {"status": status, "updated_at": datetime.now()}
        if owner is not None:
            vals["owner"] = owner
        with self.engine.begin() as c:
            n = c.execute(update(actions_t).where(and_(actions_t.c.id == aid,
                                                       actions_t.c.workspace_id == ctx.workspace_id)).values(**vals)).rowcount
            if not n:
                raise PermissionDenied("조치 항목을 찾을 수 없습니다.")
            self.log(ctx, "action.status", str(aid), vals, conn=c)
