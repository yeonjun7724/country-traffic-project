# DEMO 데이터 (가상) — 운영 통계 아님

이 폴더의 `DEMO_*.csv` 는 `scripts/generate_demo_data.py` 가 고정 시드로 생성한 **가상 데이터**입니다.

- 실제 기업·점포·차량·주문과 무관합니다. 이름에 모두 `DEMO` 접두어가 붙어 있습니다.
- 앱에서는 **DEMO 워크스페이스**에만 적재할 수 있습니다 (일반 워크스페이스 적재는 서비스 계층에서 거부).
- 화면·리포트·AI 답변에 "DEMO(가상) 데이터" 표시가 붙습니다.
- `DEMO_invalid_orders_for_validation.csv` 는 업로드 검증 동작 확인용으로 일부러 오류를 넣은 파일입니다
  (날짜 형식, 미존재 배송지, 기본키 중복, 허용값 위반, 필수값 누락).

재생성: `python scripts/generate_demo_data.py`
