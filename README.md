# ct_contest — 실데이터 기반 (수정판)

국가교통공모전 · 고속도로 물류 취약성 & 유류충격 분석 대시보드

## 변경 사항 (실데이터 검증/정비)
- ❌ 모의(mock) 데이터 생성 함수 5종 완전 제거 (load_energy_data / build_forecast /
  build_unit_data / build_impact_score / build_tcs_timeseries) — 약 500줄 삭제
- ✅ 실데이터 CSV가 없으면 모의 생성 대신 **에러 안내 후 중단** (st.stop)
- ✅ 누락돼 크래시 나던 `agent_think()` 를 **실데이터 규칙 기반 라우터**로 구현
  (6개 도구 모두 로드된 실제 데이터프레임에서 실수치 산출 — 가짜 없음)
- ✅ 데이터 탐색 경로에 `./output` 추가

## 실행
```bash
pip install -r requirements.txt
streamlit run app.py
```
실데이터 CSV는 `app.py` 와 같은 폴더 또는 `./output/` 에 두면 됩니다.
