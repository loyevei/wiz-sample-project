# read_page_results 기반 플로팅 챗봇 최종답변 재구축

- **ID**: 002
- **날짜**: 2026-03-23
- **유형**: 기능 추가

## 작업 요약
플로팅 챗봇이 페이지로 이동하기 전에 해당 페이지가 실제로 보여줄 결과 데이터를 서버에서 직접 읽어오도록 `read_page_results` Tool을 추가했다.
`research/discover`, `prediction/predict`, `theory/equation` 범위에서 페이지 API 공용 함수가 반환한 JSON을 Agent가 OpenAI 최종 정제 입력으로 활용하도록 연결해, 최종 답변이 페이지 결과 기반 한글 요약으로 나오도록 재구축했다.

## 변경 파일 목록
- `src/app/page.research/api.py`
  - `run_discover_data()` 공용 함수 추가
  - `discover()`가 공용 함수를 사용하도록 변경
- `src/app/page.prediction/api.py`
  - `run_predict_data()` 공용 함수 추가
  - `predict()`가 공용 함수를 사용하도록 변경
- `src/app/page.theory/api.py`
  - `run_search_equations_data()` 공용 함수 추가
  - `search_equations()`가 공용 함수를 사용하도록 변경
- `src/model/struct/agent/tools/read_page_results.py`
  - 페이지 결과 JSON을 읽어오는 신규 Tool 추가
- `src/model/struct/agent.py`
  - `read_page_results` 사용 가이드, 예시, 추천 도구 흐름 연결

## 검증
- `python -m py_compile /opt/app/project/main/src/model/struct/agent.py /opt/app/project/main/src/model/struct/agent/tools/read_page_results.py /opt/app/project/main/src/app/page.research/api.py /opt/app/project/main/src/app/page.prediction/api.py /opt/app/project/main/src/app/page.theory/api.py`
- `cd /opt/app/project/main && wiz project build --project=main`
- 서버 재시작 없이 normal build 완료
