"""LogisRisk Enterprise — Logistics & Distribution Intelligence Platform.

UI(Streamlit)와 분리된 도메인·검증·계산·저장 서비스 패키지.
이 패키지의 core 모듈(data/analytics/copilot/reports)은 streamlit 을 import 하지 않는다.
→ 향후 FastAPI 등 다른 프런트엔드에서 그대로 재사용 가능.
"""

__version__ = "0.1.0"
CALC_VERSION = "calc-2026.11.0"  # 계산 로직 버전 (시나리오·리포트 메타데이터에 기록)
