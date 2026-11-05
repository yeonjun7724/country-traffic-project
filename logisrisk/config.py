"""환경 설정. 비밀값은 환경변수로만 읽는다 (코드에 하드코딩 금지)."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"            # 기존 분석 결과 CSV (외부 위험 데이터)
FIXTURE_DIR = ROOT / "fixtures" / "demo"  # DEMO(가상) 데이터 — 운영 통계 아님
DATA_DIR = Path(os.environ.get("LOGISRISK_DATA_DIR", ROOT / "data"))

# 기본 SQLite. 운영에서는 DATABASE_URL=postgresql+psycopg://... 로 교체.
DATABASE_URL = os.environ.get("DATABASE_URL") or f"sqlite:///{(DATA_DIR / 'logisrisk.db').as_posix()}"

# 외부 위험 데이터의 기준 이벤트. 원인이 검증되지 않았으므로 중립 명칭을 사용한다.
REFERENCE_EVENT_DATE = "2026-02-28"
REFERENCE_EVENT_LABEL = "기준 이벤트(2026-02-28)"

# AI Copilot
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
AI_TIMEOUT_SEC = float(os.environ.get("LOGISRISK_AI_TIMEOUT_SEC", "30"))
AI_MAX_TOOL_ROUNDS = int(os.environ.get("LOGISRISK_AI_MAX_TOOL_ROUNDS", "4"))
AI_MAX_CALLS_PER_SESSION = int(os.environ.get("LOGISRISK_AI_MAX_CALLS_PER_SESSION", "40"))


def access_code() -> str | None:
    """설정 시 앱 진입에 공용 접근 코드 요구 (SSO 대체 아님 — 공개 URL 무단 접근 방지용 최소 장치)."""
    v = os.environ.get("LOGISRISK_ACCESS_CODE", "").strip()
    return v or None


def local_mode() -> bool:
    """로컬 모드에서만 역할 전환 테스트 기능을 노출. 배포 환경에서는 LOGISRISK_LOCAL_MODE=0."""
    default = "0" if os.environ.get("RAILWAY_ENVIRONMENT") else "1"
    return os.environ.get("LOGISRISK_LOCAL_MODE", default) == "1"


def openai_api_key() -> str | None:
    """환경변수에서만 키를 읽는다. (Streamlit secrets 는 UI 계층이 env 로 주입)"""
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    return key or None


def default_workspace() -> str:
    """첫 화면 워크스페이스. 기본은 샘플 데이터가 채워진 DEMO (실데이터 운영 시 'default')."""
    return os.environ.get("LOGISRISK_DEFAULT_WORKSPACE", "demo").strip() or "demo"


def auto_seed_demo() -> bool:
    """기동 시 DEMO 워크스페이스를 샘플 데이터·예시 작업물로 자동 채울지 (기본 1)."""
    return os.environ.get("LOGISRISK_AUTO_DEMO", "1") == "1"
